/*
#   ogg_vorbis_dec.c: vorbis decoder for oggdec.c
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

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "oggdec.h"
#include "ogg_vorbis_dec.h"

#define ACCEPTED 1
#define REJECTED 0
#define TRUE 1
#define FALSE 0

static void ogg_vorbisdec_cleanup(struct xlplayer *xlplayer)
    {
    struct oggdec_vars *od = xlplayer->dec_data;
    struct vorbisdec_vars *self = od->dec_data;

    fprintf(stderr, "ogg_vorbisdec_cleanup was called\n");
    if (self->resample)
        {
        if (xlplayer->src_data.data_in)
            free(xlplayer->src_data.data_in);
        if (xlplayer->src_data.data_out)
            free(xlplayer->src_data.data_out);
        xlplayer->src_state = src_delete(xlplayer->src_state);
        }
        
    vorbis_block_clear(&self->vb);
    vorbis_dsp_clear(&self->v);
    vorbis_comment_clear(&self->vc);
    vorbis_info_clear(&self->vi);
    free(self);
    /* prevent double free or continued codec use */
    od->dec_cleanup = NULL;
    od->dec_data = NULL;
    }

static void ogg_vorbisdec_play(struct xlplayer *xlplayer)
    {
    struct oggdec_vars *od = xlplayer->dec_data;
    struct vorbisdec_vars *self = od->dec_data;
    int samples, i, wi = 0;
    size_t bsiz = 8192, block = 4096, bytes = 0;
    float **pcm, *li, *lo, *ri, *ro, *out, gain;
    int vorbis_retcode, src_error;
    int channels = (od->channels[od->ix] > 1) ? 2 : 1;

    if (!(oggdec_get_next_packet(od)))
        {
        fprintf(stderr, "oggdec_get_next_packet says no more packets\n"); 
        oggdecode_playnext(xlplayer);
        return;
        }
        
    if ((vorbis_retcode = vorbis_synthesis(&self->vb, &od->op)))
        {
        fprintf(stderr, "vorbis synthesis reports problem %d\n", vorbis_retcode);
        }
     
    vorbis_synthesis_blockin(&self->v, &self->vb);
    
    if ((self->resample))
        {
        xlplayer->src_data.data_in = out = realloc(xlplayer->src_data.data_in, bsiz *= channels);
        
        while ((samples = vorbis_synthesis_pcmout(&self->v, &pcm)) > 0)
            {
            bytes += samples * sizeof (float) * channels;
            if (bytes > bsiz)
                {
                bsiz += ((bytes - bsiz) / (block * channels) + 1) * block * channels;
                xlplayer->src_data.data_in = realloc(xlplayer->src_data.data_in, bsiz);
                out = xlplayer->src_data.data_in + wi * channels;
                }

            li = pcm[0];
            if (channels > 1)
                for (i = 0, ri = pcm[1]; i < samples; i++)
                    {
                    *out++ = *li++;
                    *out++ = *ri++;
                    }
            else
                for (i = 0; i < samples; i++)
                    *out++ = *li++;

            wi += samples;
            vorbis_synthesis_read(&self->v, samples);
            }
            
        xlplayer->src_data.input_frames = wi;
        xlplayer->src_data.output_frames = wi * xlplayer->src_data.src_ratio + 512;
        xlplayer->src_data.data_out = realloc(xlplayer->src_data.data_out, xlplayer->src_data.output_frames * channels * sizeof (float));
        xlplayer->src_data.end_of_input = od->op.e_o_s;
        
        if ((src_error = src_process(xlplayer->src_state, &xlplayer->src_data)))
            {
            fprintf(stderr, "ogg_vorbisdec_play: %s src_process reports - %s\n", xlplayer->playername, src_strerror(src_error));
            oggdecode_playnext(xlplayer);
            return;
            }
            
        xlplayer_demux_channel_data(xlplayer, xlplayer->src_data.data_out, xlplayer->src_data.output_frames_gen, channels, 1.f);
        }
    else
        {
        xlplayer->leftbuffer = lo = realloc(xlplayer->leftbuffer, bsiz);
        xlplayer->rightbuffer = ro = realloc(xlplayer->rightbuffer, bsiz);
    
        while ((samples = vorbis_synthesis_pcmout(&self->v, &pcm)) > 0)
            {
            bytes += samples * sizeof (float);
            if (bytes > bsiz)
                {
                bsiz += ((bytes - bsiz) / block + 1) * block;
                xlplayer->leftbuffer = realloc(xlplayer->leftbuffer, bsiz);
                lo = xlplayer->leftbuffer + wi;
                xlplayer->rightbuffer = realloc(xlplayer->rightbuffer, bsiz);
                ro = xlplayer->rightbuffer + wi;
                }
                
            li = pcm[0];
            if (od->channels[od->ix] > 1)
                ri = pcm[1];
            else
                ri = pcm[0];
            for (i = 0; i < samples; i++)
                {
                gain = xlplayer_get_next_gain(xlplayer);
                *lo++ = *li++ * gain;
                *ro++ = *ri++ * gain;
                }
    
            wi += samples;
            vorbis_synthesis_read(&self->v, samples);
            }
    
        xlplayer->op_buffersize = bytes;
        if (od->channels[od->ix] == 1)
            memcpy(xlplayer->rightbuffer, xlplayer->leftbuffer, bytes);
        }
        
    xlplayer_write_channel_data(xlplayer);
    if (od->op.e_o_s)
        {
        fprintf(stderr, "end of stream\n");
        oggdecode_playnext(xlplayer);
        }
    }

int ogg_vorbisdec_init(struct xlplayer *xlplayer)
    {
    struct oggdec_vars *od = xlplayer->dec_data;
    struct vorbisdec_vars *self;
    int src_error;

    fprintf(stderr, "ogg_vorbisdec_init was called\n");
    if (!(self = calloc(1, sizeof (struct vorbisdec_vars))))
        {
        fprintf(stderr, "ogg_vorbisdec_init: malloc failure\n");
        return REJECTED;
        }

    ogg_stream_reset_serialno(&od->os, od->serial[od->ix]);
    fseeko(od->fp, od->bos_offset[od->ix], SEEK_SET);
    ogg_sync_reset(&od->oy);
    
    vorbis_info_init(&self->vi);
    vorbis_comment_init(&self->vc);

    if (!(oggdec_get_next_packet(od) && vorbis_synthesis_headerin(&self->vi, &self->vc, &od->op) >= 0 &&
         oggdec_get_next_packet(od) && vorbis_synthesis_headerin(&self->vi, &self->vc, &od->op) >= 0 &&
         oggdec_get_next_packet(od) && vorbis_synthesis_headerin(&self->vi, &self->vc, &od->op) >= 0 &&
         ogg_stream_packetout(&od->os, &od->op) == 0))
        {
        fprintf(stderr, "ogg_vorbisdec_init: failed vorbis header read\n");
        goto cleanup2;
        }

    if (vorbis_synthesis_init(&self->v, &self->vi))
        {
        fprintf(stderr, "ogg_vorbisdec_init: call to vorbis_synthesis_init failed\n");
        goto cleanup2;
        }

    if (vorbis_block_init(&self->v, &self->vb))
        {
        fprintf(stderr, "ogg_vorbisdec_init: call to vorbis_block_init failed\n");
        goto cleanup1;
        }

    if (od->seek_s)
        {
        /* seeked streams with less than 0.1 seconds left to be skipped */
        if (od->seek_s > (od->duration[od->ix] - 0.5))
            {
            fprintf(stderr, "ogg_vorbisdec_init: seeked stream virtually over - skipping\n");
            goto cleanup0;
            }

        oggdecode_seek_to_packet(od);
        }

    if (od->samplerate[od->ix] != xlplayer->samplerate)
        {
        fprintf(stderr, "ogg_vorbisdec_init: configuring resampler\n");
        xlplayer->src_state = src_new(xlplayer->rsqual, (od->channels[od->ix] > 1) ? 2 : 1, &src_error);
        if (src_error)
            {
            fprintf(stderr, "ogg_vorbisdec_init: src_new reports %s\n", src_strerror(src_error));
            goto cleanup0;
            }

        xlplayer->src_data.output_frames = 0;
        xlplayer->src_data.data_in = xlplayer->src_data.data_out = NULL;
        xlplayer->src_data.src_ratio = (double)xlplayer->samplerate / (double)od->samplerate[od->ix];
        xlplayer->src_data.end_of_input = 0;
        self->resample = TRUE;
        }

    od->dec_data = self;
    od->dec_cleanup = ogg_vorbisdec_cleanup;
    xlplayer->dec_play = ogg_vorbisdec_play;

    return ACCEPTED;

    cleanup0:
        vorbis_block_clear(&self->vb);
    cleanup1:
        vorbis_dsp_clear(&self->v);
    cleanup2:
        vorbis_comment_clear(&self->vc);
        vorbis_info_clear(&self->vi);
        free(self);
    return REJECTED;
    }
