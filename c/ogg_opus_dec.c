/*
#   ogg_opus_dec.c: opus decoder for oggdec.c
#   Copyright (C) 2012 Stephen Fairchild (s-fairchild@users.sourceforge.net)
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

#ifdef HAVE_OPUS

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

#include "oggdec.h"
#include "ogg_opus_dec.h"

#define ACCEPTED 1
#define REJECTED 0
#define TRUE 1
#define FALSE 0
#define MAX_FRAME_SIZE 5760

static void ogg_opusdec_cleanup(struct xlplayer *xlplayer)
    {
    struct oggdec_vars *od = xlplayer->dec_data;
    struct opusdec_vars *self = od->dec_data;

    free(self->pcm);
    if (self->do_down)
        free(self->down);

    opus_multistream_decoder_destroy(self->odms);

    fprintf(stderr, "ogg_opusdec_cleanup was called\n");
    if (self->resample)
        xlplayer->src_state = src_delete(xlplayer->src_state);
        
    free(self);
    /* prevent double free or continued codec use */
    od->dec_cleanup = NULL;
    od->dec_data = NULL;
    }

static void ogg_opusdec_play(struct xlplayer *xlplayer)
    {    
    struct oggdec_vars *od = xlplayer->dec_data;
    struct opusdec_vars *self = od->dec_data;
    int error;
    int samples;
    int end_trim = 0;

    if (!(oggdec_get_next_packet(od)))
        {
        fprintf(stderr, "oggdec_get_next_packet says no more packets\n"); 
        oggdecode_playnext(xlplayer);
        return;
        }
        
    samples = opus_multistream_decode_float(self->odms, od->op.packet, od->op.bytes, self->pcm, MAX_FRAME_SIZE, 0);
    self->dec_samples += samples;

    if (od->op.granulepos != -1)
        {
        self->gf_gp = self->f_gp;
        self->f_gp = self->gp;
        self->gp = od->op.granulepos;
        
        if (self->gp < self->f_gp)
            {
            fprintf(stderr, "ogg_opusdec_play: bad granule pos\n");
            oggdecode_playnext(xlplayer);
            return;
            }
        
        if (od->op.e_o_s)
            {
            if (self->f_gp > self->gf_gp)
                end_trim = self->f_gp - self->gf_gp - (self->gp - self->f_gp);
            else
                end_trim = self->dec_samples - self->gp;

            if (end_trim < 0)
                end_trim = 0;
            }
        }

    samples -= end_trim;

    if (self->preskip)
        {
        if (samples > self->preskip)
            {
            samples -= self->preskip;
            memmove(self->pcm, self->pcm + self->preskip * self->channel_count, samples * sizeof (float) * self->channel_count);
            self->preskip = 0;
            }
        else
            {
            self->preskip -= samples; 
            samples = 0;
            }
        }

    if (samples > 0)
        {
        if (self->do_down)
            {
            static const float table[6][8][2] =
                {
                    {{0.7f, 0.0f}, {0.7f, 0.7f}, {0.0f, 0.7f}},
                    {{0.7f, 0.0f}, {0.0f, 0.7f}, {0.7f, 0.0f}, {0.0f, 0.7f}},
                    {{0.7f, 0.0f}, {0.7f, 0.7f}, {0.0f, 0.7f}, {0.7f, 0.0f}, {0.0f, 0.7f}},
                    {{0.7f, 0.0f}, {0.7f, 0.7f}, {0.0f, 0.7f}, {0.7f, 0.0f}, {0.0f, 0.7f}, {0.5f, 0.5f}},
                    {{0.7f, 0.0f}, {0.7f, 0.7f}, {0.0f, 0.7f}, {0.7f, 0.0f}, {0.0f, 0.7f}, {0.7f, 0.7f}, {0.5f, 0.5f}},
                    {{0.7f, 0.0f}, {0.7f, 0.7f}, {0.0f, 0.7f}, {0.7f, 0.0f}, {0.0f, 0.7f}, {0.7f, 0.0f}, {0.0f, 0.7f}, {0.5f, 0.5f}}
                };
                
                
            int cc = self->channel_count;    
            float *p = self->pcm;
            float *d = self->down;
            float sample, lc, rc;
                
            for (int i = 0; i < samples; ++i)
                {
                lc = rc = 0.0;

                for (int j = 0; j < cc; ++j)
                    {
                    sample = *p++;
                    lc += sample * table[cc - 3][j][0];
                    rc += sample * table[cc - 3][j][1];
                    }
                
                *d++ = lc;
                *d++ = rc;
                }
            }
            
        if (self->resample)
            {
            xlplayer->src_data.input_frames = samples;
            xlplayer->src_data.end_of_input = od->op.e_o_s;
            if ((error = src_process(xlplayer->src_state, &xlplayer->src_data)))
                {
                fprintf(stderr, "ogg_opusdec_play: %s src_process reports - %s\n", xlplayer->playername, src_strerror(error));
                oggdecode_playnext(xlplayer);
                return;
                }

            xlplayer_demux_channel_data(xlplayer, xlplayer->src_data.data_out, xlplayer->src_data.output_frames_gen, od->channels[od->ix], self->opgain);
            }
        else
            xlplayer_demux_channel_data(xlplayer, self->down, samples, od->channels[od->ix], self->opgain);
            
        xlplayer_write_channel_data(xlplayer);
        }

    if (od->op.e_o_s)
        {
        fprintf(stderr, "end of stream\n");
        oggdecode_playnext(xlplayer);
        }
    }

int ogg_opusdec_init(struct xlplayer *xlplayer)
    {
    struct oggdec_vars *od = xlplayer->dec_data;
    struct opusdec_vars *self;
    unsigned char *pkt;
    float opgain_db;
    int error;
    size_t down_siz = MAX_FRAME_SIZE * sizeof (float) * od->channels[od->ix];
        
    fprintf(stderr, "ogg_opusdec_init was called\n");

    ogg_stream_reset_serialno(&od->os, od->serial[od->ix]);
    fseeko(od->fp, od->bos_offset[od->ix], SEEK_SET);
    ogg_sync_reset(&od->oy);

    /* sanity checking was pre-done in opus_get_samplerate() */
    if (!(oggdec_get_next_packet(od)))
        {
        fprintf(stderr, "ogg_opusdec_init: failed to get opus header\n");
        goto cleanup1;
        }

    if (!(self = calloc(1, sizeof (struct opusdec_vars))))
        {
        fprintf(stderr, "ogg_opusdec_init: malloc failure\n");
        goto cleanup1;
        }

    pkt = od->op.packet;

    self->channel_count = pkt[9];
    self->preskip = pkt[10] | (uint16_t)pkt[11] << 8;
    fprintf(stderr, "preskip %hu samples\n", self->preskip);
    opgain_db = (int16_t)((uint16_t)pkt[16] | ((uint16_t)((unsigned char *)pkt)[17] << 8)) / 256.0f;
    fprintf(stderr, "output gain %0.1lf (dB)\n", opgain_db);
    self->opgain = powf(10.0f, opgain_db / 20.0f); 

    switch ((self->channelmap_family = pkt[18]))
        {
        case 0:    
            self->stream_count = 1;
            self->stream_count_2c = self->channel_count - 1;
            self->channel_map[0] = 0;
            self->channel_map[1] = 1;
            break;
        case 1:
            self->stream_count = pkt[19];
            self->stream_count_2c = pkt[20];
            memcpy(self->channel_map, pkt + 21, self->channel_count);
            break;
        default:
            goto cleanup2;
        }
        
    if (!(oggdec_get_next_packet(od)))
        {
        fprintf(stderr, "ogg_opusdec_init: missing OpusTags packet\n");
        goto cleanup2;
        }

    if (od->seek_s)
        {
        if (od->seek_s > (od->duration[od->ix] - 0.5))
            {
            fprintf(stderr, "ogg_opusdec_init: seeked stream virtually over - skipping\n");
            goto cleanup2;
            }

        oggdecode_seek_to_packet(od);
        }
    else
        self->gf_gp = self->f_gp = self->gp = od->initial_granulepos[od->ix];

    if (!(self->odms = opus_multistream_decoder_create(48000, self->channel_count,
                    self->stream_count, self->stream_count_2c, self->channel_map, &error)))
        {
        fprintf(stderr, "ogg_opusdec_init: failed to create multistream decoder: %s\n", opus_strerror(error));
        goto cleanup2;
        }

    if (!(self->pcm = malloc(MAX_FRAME_SIZE * sizeof (float) * self->channel_count)))
        {
        fprintf(stderr, "ogg_opusdec_init: malloc failure -- pcm\n");
        goto cleanup3;
        }

    if ((self->do_down = od->channels[od->ix] != self->channel_count))
        {
        if (!(self->down = malloc(down_siz)))
            {
            fprintf(stderr, "ogg_opusdec_init: malloc failure -- down\n");
            goto cleanup4;
            }
        }
    else
        self->down = self->pcm;     /* no need to downmix for mono/stereo */

    if (od->samplerate[od->ix] != xlplayer->samplerate)
        {
        fprintf(stderr, "ogg_opusdec_init: configuring resampler\n");
        self->resample = TRUE;
        xlplayer->src_state = src_new(xlplayer->rsqual, od->channels[od->ix], &error);
        if (error)
            {
            fprintf(stderr, "ogg_opusdec_init: src_new reports %s\n", src_strerror(error));
            goto cleanup5;
            }

        xlplayer->src_data.data_in = self->down;
        xlplayer->src_data.src_ratio = (double)xlplayer->samplerate / (double)od->samplerate[od->ix];
        xlplayer->src_data.end_of_input = 0;
        
        size_t opframes = MAX_FRAME_SIZE * xlplayer->src_data.src_ratio + 4096;
        
        xlplayer->src_data.output_frames = opframes;
        if (!(xlplayer->src_data.data_out = malloc(opframes * sizeof (float) * od->channels[od->ix])))
            {
            fprintf(stderr, "ogg_opusdec_init: malloc failure -- data_out\n");
            goto cleanup6;
            }
        }

    od->dec_data = self;
    od->dec_cleanup = ogg_opusdec_cleanup;
    xlplayer->dec_play = ogg_opusdec_play;

    return ACCEPTED;

    cleanup6:
        if (self->resample)
            xlplayer->src_state = src_delete(xlplayer->src_state);
    cleanup5:
        if (self->do_down)
            free(self->down);
    cleanup4:
        free(self->pcm);
    cleanup3:
        opus_multistream_decoder_destroy(self->odms);
    cleanup2:
        free(self);
    cleanup1:
        return REJECTED;
    }

#endif /* HAVE_OPUS */
