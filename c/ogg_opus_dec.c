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
    int src_error;
        
    fprintf(stderr, "ogg_opusdec_init was called\n");

    ogg_stream_reset_serialno(&od->os, od->serial[od->ix]);
    fseeko(od->fp, od->bos_offset[od->ix], SEEK_SET);
    ogg_sync_reset(&od->oy);

    if (!(oggdec_get_next_packet(od) &&
                ogg_stream_packetout(&od->os, &od->op) == 0 &&
                od->op.bytes >= 19 &&
                !memcmp("OpusHead", (pkt = od->op.packet), 8)))
        {
        fprintf(stderr, "ogg_opusdec_init: failed to get opus header\n");
        goto cleanup1;
        }

    if (pkt[8] != 1)
        {
        fprintf(stderr, "ogg_opusdec_init: unsupported encapsulation version != 1\n");
        goto cleanup1;
        }

    if (!(self = calloc(1, sizeof (struct opusdec_vars))))
        {
        fprintf(stderr, "ogg_opusdec_init: malloc failure\n");
        goto cleanup1;
        }

    self->preskip = pkt[10] | (uint16_t)pkt[11] << 8;
    fprintf(stderr, "preskip %hd samples\n", self->preskip);
    self->origsr = pkt[12] | (uint32_t)pkt[13] << 8 |
                    (uint32_t)pkt[14] << 16 | (uint32_t)pkt[15] << 24;
    fprintf(stderr, "source material sample rate %d\n", self->origsr);
    self->opgain = (uint16_t)pkt[16] | (uint16_t)pkt[17] << 8;
    fprintf(stderr, "output gain %d\n", self->opgain);

    if ((self->channelmap = pkt[18]))
        {
        fprintf(stderr, "ogg_opusdec_init: channel map > 0 unsupported\n");
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
        /* seeked streams with less than 0.1 seconds left to be skipped */
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
        xlplayer->src_state = src_new(xlplayer->rsqual, (od->channels[od->ix] > 1) ? 2 : 1, &src_error);
        if (src_error)
            {
            fprintf(stderr, "ogg_vorbisdec_init: src_new reports %s\n", src_strerror(src_error));
            goto cleanup2;
            }

        xlplayer->src_data.output_frames = 0;
        xlplayer->src_data.data_in = xlplayer->src_data.data_out = NULL;
        xlplayer->src_data.src_ratio = (double)xlplayer->samplerate / (double)od->samplerate[od->ix];
        xlplayer->src_data.end_of_input = 0;
        self->resample = TRUE;
        }

    od->dec_data = self;
    od->dec_cleanup = ogg_opusdec_cleanup;
    xlplayer->dec_play = ogg_opusdec_play;

    return ACCEPTED;

    cleanup2:
        free(self);
    cleanup1:
        return REJECTED;
    }

#endif /* HAVE_OPUS */
