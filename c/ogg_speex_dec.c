/*
#   ogg_speex_dec.c: speex decoder for oggdec.c
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

#ifdef HAVE_SPEEX

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "oggdec.h"
#include "ogg_speex_dec.h"

#define ACCEPTED 1
#define REJECTED 0
#define TRUE 1
#define FALSE 0

static void ogg_speexdec_cleanup(struct xlplayer *xlplayer)
    {
    struct oggdec_vars *od = xlplayer->dec_data;
    struct speexdec_vars *self = od->dec_data;
    
    fprintf(stderr, "ogg_speexdec_cleanup was called\n");
    oggdecode_remove_new_oggpage_callback(od);
    src_delete(xlplayer->src_state);
    free(self->frame);
    free(xlplayer->src_data.data_out);
    speex_bits_destroy(&self->bits);
    speex_decoder_destroy(self->dec_state);
    free(self);
    /* prevent this being called again */
    od->dec_cleanup = NULL;
    od->dec_data = NULL;
    }

/* ogg_speexdec_new_oggpage: a callback routine from oggdec_get_next_packet */
static void ogg_speexdec_new_oggpage(struct oggdec_vars *od, void *user_data)
    {
    struct speexdec_vars *self = user_data;
    
    self->page_granule = ogg_page_granulepos(&od->og);
    if (self->last_granule == -1)
        self->last_granule = self->page_granule;
    self->page_nb_packets = ogg_page_packets(&od->og);
    if (self->page_granule > 0 && self->frame_size)
        {
        self->skip_samples = self->page_nb_packets * self->frame_size * self->nframes - (self->page_granule - self->last_granule);
        if (ogg_page_eos(&od->og))
            self->skip_samples = -self->skip_samples;
        }
    else
        self->skip_samples = 0;
    
    self->last_granule = self->page_granule;
    self->packet_no = 0;
    }

static void ogg_speexdec_play(struct xlplayer *xlplayer)
    {
    struct oggdec_vars *od = xlplayer->dec_data;
    struct speexdec_vars *self = od->dec_data;
    int src_error, i, frame_offset, new_frame_size, packet_length;
    
    if (oggdec_get_next_packet(od))
        {
        self->packet_no++;
        speex_bits_read_from(&self->bits, (char *)od->op.packet, od->op.bytes);
        for (i = 0; i < self->nframes; i++)
            {
            switch (speex_decode(self->dec_state, &self->bits, self->frame))
                {
                case 0:
                    if (speex_bits_remaining(&self->bits) < 0)
                        {
                        fprintf(stderr, "ogg_speexdec_play: decoding overflow\n");
                        oggdecode_playnext(xlplayer);
                        return;
                        }

                    if (self->stereo)
                        speex_decode_stereo(self->frame, self->frame_size, &self->stereo_state);

                    frame_offset = 0;
                    new_frame_size = self->frame_size;

                    if (self->packet_no == 1 && i == 0 && self->skip_samples > 0)
                        {
                        fprintf(stderr, "chopping first packet\n");
                        new_frame_size -= self->skip_samples + self->lookahead;
                        frame_offset = self->skip_samples + self->lookahead;
                        }

                    if (self->packet_no == self->page_nb_packets && self->skip_samples < 0)
                        {
                        packet_length = self->nframes * self->frame_size + self->skip_samples + self->lookahead;
                        new_frame_size = packet_length - i * self->frame_size;
                        if (new_frame_size < 0)
                            new_frame_size = 0;
                        if (new_frame_size > self->frame_size)
                            new_frame_size = self->frame_size;

                        xlplayer->src_data.end_of_input = 1;

                        fprintf(stderr, "chopping end: %d %d %d\n", new_frame_size, packet_length, self->packet_no);
                        }

                    if (new_frame_size > 0)
                        {
                        if (self->seek_dump_samples > 0)
                            self->seek_dump_samples -= self->frame_size;
                        else
                            {
                            xlplayer->src_data.data_in = self->frame + frame_offset * self->channels;
                            xlplayer->src_data.input_frames = new_frame_size;
    
                            if ((src_error = src_process(xlplayer->src_state, &xlplayer->src_data)))
                                {
                                fprintf(stderr, "ogg_speexdec_play: %s src_process reports - %s\n", xlplayer->playername, src_strerror(src_error));
                                oggdecode_playnext(xlplayer);
                                return;
                                }
        
                            xlplayer_demux_channel_data(xlplayer, xlplayer->src_data.data_out, xlplayer->src_data.output_frames_gen, self->header->nb_channels, 3.051757813e-05);
                            do
                                {
                                xlplayer_write_channel_data(xlplayer);
                                } while (xlplayer->write_deferred && i + 1 < self->nframes);
                            }
                        }

                    if (xlplayer->src_data.end_of_input)
                        {
                        oggdecode_playnext(xlplayer);
                        return;
                        }

                    break;
                case -2:
                    fprintf(stderr, "ogg_speexdec_play: stream corruption detected\n");
                    oggdecode_playnext(xlplayer);
                    return;
                case -1:                /* end of stream */
                    fprintf(stderr, "ogg_speexdec_play: end of stream detected\n");
                    oggdecode_playnext(xlplayer);
                    return;
                default:
                    fprintf(stderr, "ogg_speexdec_play: unhandled return code\n");
                    oggdecode_playnext(xlplayer);
                    return;
                }
            }
        }
    else
        {
        fprintf(stderr, "no more packets available\n");
        oggdecode_playnext(xlplayer);
        return;
        }
    }

int ogg_speexdec_init(struct xlplayer *xlplayer)
    {
    struct oggdec_vars *od = xlplayer->dec_data;
    struct speexdec_vars *self;
    SpeexMode const *mode;
    int src_error, i, s_granule, e_granule, p_granule, t_granule;
    SpeexCallback callback;

    fprintf(stderr, "ogg_speexdec_init was called\n");
    if (!(self = calloc(1, sizeof (struct speexdec_vars))))
        {
        fprintf(stderr, "ogg_speexdec_init: malloc failure\n");
        goto cleanup3;
        }

    ogg_stream_reset_serialno(&od->os, od->serial[od->ix]);
    fseeko(od->fp, od->bos_offset[od->ix], SEEK_SET);
    ogg_sync_reset(&od->oy);

    if (!(oggdec_get_next_packet(od) && ogg_stream_packetout(&od->os, &od->op) == 0 && (self->header = speex_packet_to_header((char *)od->op.packet, od->op.bytes))))
        {
        fprintf(stderr, "ogg_speexdec_init: failed to get speex header\n");
        goto cleanup2;
        }
        
    mode = speex_lib_get_mode(self->header->mode);

    if (self->header->speex_version_id > 1)
        {
        fprintf (stderr, "This file was encoded with Speex bit-stream version %d, which I don't know how to decode\n", self->header->speex_version_id);
        goto cleanup1;
        }

    if (mode->bitstream_version < self->header->mode_bitstream_version)
        {
        fprintf (stderr, "The file was encoded with a newer version of Speex. You need to upgrade in order to play it.\n");
        goto cleanup1;
        }
        
    if (mode->bitstream_version > self->header->mode_bitstream_version) 
        {
        fprintf (stderr, "The file was encoded with an older version of Speex. You would need to downgrade the version in order to play it.\n");
        goto cleanup1;
        }

    for (i = 0; i < self->header->extra_headers + 1; i++)
        {
        oggdec_get_next_packet(od);
        if (i != 0)
            fprintf(stderr, "extra header dumped\n");
        }

    if (!(self->dec_state = speex_decoder_init(mode)))
        {
        fprintf(stderr, "ogg_speexdec_init: failed to initialise speex decoder\n");
        goto cleanup1;
        }

    if (speex_decoder_ctl(self->dec_state, SPEEX_GET_FRAME_SIZE, &self->frame_size))
        {
        fprintf(stderr, "ogg_speexdec_init: unable to obtain frame size\n");
        goto cleanup0;
        }
    else
        fprintf(stderr, "frame size is %d samples\n", self->frame_size);
        
    speex_decoder_ctl(self->dec_state, SPEEX_GET_LOOKAHEAD, &self->lookahead);
        
    if ((self->nframes = self->header->frames_per_packet) < 1)
        {
        fprintf(stderr, "ogg_speexdec_init: header frames_per_packet must be greater than zero\n");
        goto cleanup0;
        }
    
    if (!(self->frame = malloc(self->frame_size * self->header->nb_channels * sizeof (float))))
        {
        fprintf(stderr, "ogg_speexdec_init: malloc failure\n");
        goto cleanup0;
        }
    
    if ((self->channels = self->header->nb_channels) == 2)
        {
        self->stereo = TRUE;
        self->stereo_state = (SpeexStereoState)SPEEX_STEREO_STATE_INIT;
        callback.callback_id = SPEEX_INBAND_STEREO;
        callback.func = speex_std_stereo_request_handler;
        callback.data = &self->stereo_state;
        speex_decoder_ctl(self->dec_state, SPEEX_SET_HANDLER, &callback);
        }
    else
        if (self->channels != 1)
            {
            fprintf(stderr, "ogg_speexdec_init: unsupported number of audio channels\n");
            goto cleanupA;
            }

    xlplayer->src_state = src_new(xlplayer->rsqual, self->header->nb_channels, &src_error);
    if (src_error)
        {
        fprintf(stderr, "ogg_speexdec_init: src_new reports %s\n", src_strerror(src_error));
        goto cleanupA;
        }
        
    xlplayer->src_data.end_of_input = 0;
    xlplayer->src_data.input_frames = self->frame_size;
    xlplayer->src_data.data_in = self->frame;
    xlplayer->src_data.src_ratio = (double)xlplayer->samplerate / (double)od->samplerate[od->ix];
    xlplayer->src_data.output_frames = self->frame_size * self->header->nb_channels * xlplayer->src_data.src_ratio + 512;
    if (!(xlplayer->src_data.data_out = malloc(xlplayer->src_data.output_frames * sizeof (float))))
        {
        fprintf(stderr, "ogg_speexdec_init: malloc failure\n");
        goto cleanupB;
        }
    
    speex_bits_init(&self->bits);

    if (od->seek_s)
        {
        /* seeked streams with less than 0.1 seconds left to be skipped */
        if (od->seek_s > (od->duration[od->ix] - 0.5))
            {
            fprintf(stderr, "ogg_speexdec_init: seeked stream virtually over - skipping\n");
            goto cleanupB;
            }

        oggdecode_seek_to_packet(od);

        /* calculate how many samples we need to drop for accurate seeking */
        t_granule = od->seek_s * od->samplerate[od->ix];
        e_granule = ogg_page_granulepos(&od->og);
        p_granule = self->frame_size * self->nframes;
        if ((s_granule = e_granule - (ogg_page_packets(&od->og) - ogg_page_continued(&od->og)) * p_granule) < 0)
            s_granule = 0;
        self->seek_dump_samples = t_granule - s_granule - self->frame_size * 26;
 
        self->last_granule = -1;
        }
    
    od->dec_data = self;
    od->dec_cleanup = ogg_speexdec_cleanup;
    xlplayer->dec_play = ogg_speexdec_play;
    oggdecode_set_new_oggpage_callback(od, ogg_speexdec_new_oggpage, self);

    return ACCEPTED;

    cleanupB:
        src_delete(xlplayer->src_state);
    cleanupA:
        free(self->frame);
    cleanup0:
        speex_decoder_destroy(self->dec_state);
    cleanup1:
        speex_header_free(self->header);
    cleanup2:
        free(self);
    cleanup3:
        return REJECTED;
    }

#endif /* HAVE_SPEEX */
