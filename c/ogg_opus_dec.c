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

static void ogg_opusdec_cleanup(struct xlplayer *xlplayer)
    {
    struct oggdec_vars *od = xlplayer->dec_data;
    struct opusdec_vars *self = od->dec_data;

    opus_multistream_decoder_destroy(self->odms);

    fprintf(stderr, "ogg_opusdec_cleanup was called\n");
    if (self->resample)
        {
        if (xlplayer->src_data.data_in)
            free(xlplayer->src_data.data_in);
        if (xlplayer->src_data.data_out)
            free(xlplayer->src_data.data_out);
        xlplayer->src_state = src_delete(xlplayer->src_state);
        }
        
    free(self);
    /* prevent double free or continued codec use */
    od->dec_cleanup = NULL;
    od->dec_data = NULL;
    }

static void ogg_opusdec_play(struct xlplayer *xlplayer)
    {
    oggdecode_playnext(xlplayer);
    return;
    }

int ogg_opusdec_init(struct xlplayer *xlplayer)
    {
    struct oggdec_vars *od = xlplayer->dec_data;
    struct opusdec_vars *self;
    unsigned char *pkt;
    float opgain_db;
    int error;
        
    fprintf(stderr, "ogg_opusdec_init was called\n");

    ogg_stream_reset_serialno(&od->os, od->serial[od->ix]);
    fseeko(od->fp, od->bos_offset[od->ix], SEEK_SET);
    ogg_sync_reset(&od->oy);

    /* sanity checking was pre-done in opus_get_samplerate() */
    if (!(oggdec_get_next_packet(od) && ogg_stream_packetout(&od->os, &od->op) == 0))
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
    fprintf(stderr, "preskip %hd samples\n", self->preskip);
    opgain_db = ((uint16_t)pkt[16] | (uint16_t)pkt[17] << 8) / 256.0f;
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
        
    if (!(oggdec_get_next_packet(od) &&
                ogg_stream_packetout(&od->os, &od->op) == 0 &&
                od->op.bytes >= 9 &&
                !memcmp("OpusTags", (pkt = od->op.packet), 8)))
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

    if (od->samplerate[od->ix] != xlplayer->samplerate)
        {
        fprintf(stderr, "ogg_opusdec_init: configuring resampler\n");
        xlplayer->src_state = src_new(xlplayer->rsqual, od->channels[od->ix], &error);
        if (error)
            {
            fprintf(stderr, "ogg_vorbisdec_init: src_new reports %s\n", src_strerror(error));
            goto cleanup2;
            }

        xlplayer->src_data.output_frames = 0;
        xlplayer->src_data.data_in = xlplayer->src_data.data_out = NULL;
        xlplayer->src_data.src_ratio = (double)xlplayer->samplerate / (double)od->samplerate[od->ix];
        xlplayer->src_data.end_of_input = 0;
        self->resample = TRUE;
        }

    if (!(self->odms = opus_multistream_decoder_create(48000, self->channel_count,
                    self->stream_count, self->stream_count_2c, self->channel_map, &error)))
        {
        fprintf(stderr, "ogg_opusdec_init: failed to create multistream decoder: %s\n", opus_strerror(error));
        
        goto cleanup3;
        }

    od->dec_data = self;
    od->dec_cleanup = ogg_opusdec_cleanup;
    xlplayer->dec_play = ogg_opusdec_play;

    return ACCEPTED;

    cleanup3:
        if (self->resample)
            xlplayer->src_state = src_delete(xlplayer->src_state);
    cleanup2:
        free(self);
    cleanup1:
        return REJECTED;
    }

#endif /* HAVE_OPUS */
