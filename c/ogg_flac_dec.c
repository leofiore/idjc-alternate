/*
#   ogg_flac_dec.c: flac decoder for oggdec.c
#   Copyright (C) 2008 Stephen Fairchild (s-fairchild@users.sourceforge.net)
#
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 2 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program in the file entitled COPYING.
#   If not, see <http://www.gnu.org/licenses/>.
*/

#include "../config.h"

#ifdef HAVE_OGGFLAC

#include <stdio.h>
#include <stdlib.h>

#include "oggdec.h"
#include "ogg_flac_dec.h"
#include "flacdecode.h"

#define ACCEPTED 1
#define REJECTED 0
#define TRUE 1
#define FALSE 0

static void ogg_flacdec_cleanup(struct xlplayer *xlplayer)
    {
    struct oggdec_vars *od = xlplayer->dec_data;
    struct oggflacdec_vars *self = od->dec_data;
    
    fprintf(stderr, "ogg_flacdec_cleanup was called\n");
    if (self->resample)
        {
        if (xlplayer->src_data.data_in)
            free(xlplayer->src_data.data_in);
        if (xlplayer->src_data.data_out)
            free(xlplayer->src_data.data_out);
        xlplayer->src_state = src_delete(xlplayer->src_state);
        }

    FLAC__stream_decoder_delete(self->dec);
    free(self);
    /* prevent double free */
    od->dec_cleanup = NULL;
    od->dec_data = NULL;
    }

/* write callback to output data with resample */
FLAC__StreamDecoderWriteStatus
ogg_flacdec_write_resample_callback(const FLAC__StreamDecoder *dec, const FLAC__Frame *frame, const FLAC__int32 *const inputbuffer[], void *client_data)
    {
    struct oggdec_vars *od = client_data;
    struct oggflacdec_vars *self = od->dec_data;
    struct xlplayer *xlplayer = od->xlplayer;
    SRC_DATA *src_data = &xlplayer->src_data;
    int src_error;

    if (self->suppress_audio_output == FALSE)
        {
        if (frame->header.number_type == FLAC__FRAME_NUMBER_TYPE_FRAME_NUMBER && frame->header.number.frame_number == 0)
            {
            fprintf(stderr, "ogg_flacdec_write_resample_callback: performance warning -- can't determine if a block is the last one or not for this file\n");
            }
        else
            {
            if (frame->header.number.sample_number + frame->header.blocksize == od->final_granulepos[od->ix])
                src_data->end_of_input = TRUE;
            }

        src_data->input_frames = frame->header.blocksize;
        src_data->data_in = realloc(src_data->data_in, src_data->input_frames * frame->header.channels * sizeof (float));
        src_data->output_frames = ((int)(src_data->input_frames * src_data->src_ratio)) + 512;
        src_data->data_out = realloc(src_data->data_out, src_data->output_frames * frame->header.channels * sizeof (float));
        make_flac_audio_to_float(xlplayer, src_data->data_in, inputbuffer, frame->header.blocksize, frame->header.bits_per_sample, frame->header.channels);

        if ((src_error = src_process(xlplayer->src_state, src_data)))
            {
            fprintf(stderr, "flac_writer_callback: src_process reports %s\n", src_strerror(src_error));
            return FLAC__STREAM_DECODER_WRITE_STATUS_ABORT;
            }

        xlplayer_demux_channel_data(xlplayer, src_data->data_out, src_data->output_frames_gen, frame->header.channels, 1.f);

        xlplayer_write_channel_data(xlplayer);
        }

    return FLAC__STREAM_DECODER_WRITE_STATUS_CONTINUE;
    }

/* write callback to output data without resample */
FLAC__StreamDecoderWriteStatus
ogg_flacdec_write_callback(const FLAC__StreamDecoder *decoder, const FLAC__Frame *frame, const FLAC__int32 * const inputbuffer[], void *client_data)
    {
    struct oggdec_vars *od = client_data;
    struct oggflacdec_vars *self = od->dec_data;
    struct xlplayer *xlplayer = od->xlplayer;
    
    if (self->suppress_audio_output == FALSE)
        {
        if ((self->flbuf = realloc(self->flbuf, sizeof (float) * frame->header.blocksize * frame->header.channels)) == NULL)
            {
            fprintf(stderr, "flac_writer_callback: malloc failure\n");
            return FLAC__STREAM_DECODER_WRITE_STATUS_ABORT;
            }

        make_flac_audio_to_float(xlplayer, self->flbuf, inputbuffer, frame->header.blocksize, frame->header.bits_per_sample, frame->header.channels);
        xlplayer_demux_channel_data(xlplayer, self->flbuf, frame->header.blocksize, frame->header.channels, 1.f);
        
        xlplayer_write_channel_data(xlplayer);
        }

    return FLAC__STREAM_DECODER_WRITE_STATUS_CONTINUE;
    }

static void ogg_flacdec_play(struct xlplayer *xlplayer)
    {
    struct oggdec_vars *od = xlplayer->dec_data;
    struct oggflacdec_vars *self = od->dec_data;
    
    if (!(FLAC__stream_decoder_process_single(self->dec)))
        {
        fprintf(stderr, "ogg_flacdec_play: fatal error occurred reading oggflac stream\n");
        fprintf(stderr, "%s\n", FLAC__stream_decoder_get_resolved_state_string(self->dec));
        oggdecode_playnext(xlplayer);
        }
    else
        if (FLAC__stream_decoder_get_state(self->dec) == FLAC__STREAM_DECODER_END_OF_STREAM)
            {
            oggdecode_playnext(xlplayer);
            }
    }

int ogg_flacdec_init(struct xlplayer *xlplayer)
    {
    struct oggdec_vars *od = xlplayer->dec_data;
    struct oggflacdec_vars *self = od->dec_data;
    int src_error;
    FLAC__StreamDecoderInitStatus status;

    fprintf(stderr, "ogg_flacdec_init was called\n");
    if (!(self = calloc(1, sizeof (struct oggflacdec_vars))))
        {
        fprintf(stderr, "ogg_flacdec_init: malloc failure\n");
        return REJECTED;
        }

    fseeko(od->fp, od->bos_offset[od->ix], SEEK_SET);

    if (!(self->dec = FLAC__stream_decoder_new()))
        {
        fprintf(stderr, "ogg_flacdec_init: call to FLAC__stream_decoder_new failed\n");
        return REJECTED;
        }

    if (od->samplerate[od->ix] != xlplayer->samplerate)
        {
        self->resample = TRUE;

        status = FLAC__stream_decoder_init_ogg_stream(self->dec,
                            oggflac_read_callback, oggflac_seek_callback,
                            oggflac_tell_callback, oggflac_length_callback,
                            oggflac_eof_callback, ogg_flacdec_write_resample_callback,
                            NULL, oggflac_error_callback, od);
        }
    else
        {
        status = FLAC__stream_decoder_init_ogg_stream(self->dec,
                            oggflac_read_callback, oggflac_seek_callback,
                            oggflac_tell_callback, oggflac_length_callback,
                            oggflac_eof_callback, ogg_flacdec_write_callback,
                            NULL, oggflac_error_callback, od);
        }

    if (status != FLAC__STREAM_DECODER_INIT_STATUS_OK)
        {
        fprintf(stderr, "ogg_flacdec_init: failed to initialise OggFLAC decoder\n");
        FLAC__stream_decoder_delete(self->dec);
        return REJECTED;
        }

    if ((self->resample))
        {
        fprintf(stderr, "ogg_flacdec_init: configuring resampler\n");

        xlplayer->src_state = src_new(xlplayer->rsqual, (od->channels[od->ix] > 1) ? 2 : 1, &src_error);
        if (src_error)
            {
            fprintf(stderr, "ogg_flacdec_init: src_new reports %s\n", src_strerror(src_error));
            FLAC__stream_decoder_delete(self->dec);
            return REJECTED;
            }
            
        xlplayer->src_data.output_frames = 0;
        xlplayer->src_data.data_in = xlplayer->src_data.data_out = NULL;
        xlplayer->src_data.src_ratio = (double)xlplayer->samplerate / (double) od->samplerate[od->ix];
        xlplayer->src_data.end_of_input = 0;
        }

    if (!(FLAC__stream_decoder_process_until_end_of_metadata(self->dec)))
        {
        if (self->resample)
            src_delete(xlplayer->src_state);
        FLAC__stream_decoder_delete(self->dec);
        return REJECTED;
        }

    od->dec_data = self;
    od->dec_cleanup = ogg_flacdec_cleanup;
    xlplayer->dec_play = ogg_flacdec_play;

    if (od->seek_s)
        {
        self->suppress_audio_output = TRUE;
        if (!(FLAC__stream_decoder_seek_absolute(self->dec, (FLAC__uint64)od->seek_s * od->samplerate[od->ix])))
            fprintf(stderr, "ogg_flacdec_init: seek failed\n");
        self->suppress_audio_output = FALSE;
        }

    fprintf(stderr, "ogg_flacdec_init: completed\n");
    return ACCEPTED;
    }

#endif /* HAVE_OGGFLAC */
