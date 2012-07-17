/*
#   live_mp3_encoder.c: encode mp3 files from a live source
#   Copyright (C) 2007 Stephen Fairchild (s-fairchild@users.sourceforge.net)
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

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include <jack/ringbuffer.h>
#include "sourceclient.h"
#include "live_mp3_encoder.h"

#define READSIZE 1024

typedef jack_default_audio_sample_t sample_t;

static void live_mp3_packetize_metadata(struct encoder *e, struct lm3e_data * const s)
    {
    size_t l = 4;
    
    pthread_mutex_lock(&e->metadata_mutex);
    
    l += strlen(e->custom_meta);
    l += strlen(e->artist);
    l += strlen(e->title);
    l += strlen(e->album);
    
    if ((s->metadata = realloc(s->metadata, l)))
        snprintf(s->metadata, l, "%s\n%s\n%s\n%s", e->custom_meta, e->artist, e->title, e->album);
    else
        fprintf(stderr, "malloc failure\n");
        
    e->new_metadata = FALSE;
    pthread_mutex_unlock(&e->metadata_mutex);
    }

static int live_mp3_write_packet(struct encoder *encoder, struct lm3e_data *s, unsigned char *buffer, size_t buffersize, int flags)
    {
    struct encoder_op_packet packet;

    packet.header.bit_rate = encoder->bitrate;
    packet.header.sample_rate = encoder->target_samplerate;
    packet.header.n_channels = encoder->n_channels;
    packet.header.flags = flags;
    packet.header.data_size = buffersize;
    packet.header.serial = encoder->oggserial;
    packet.header.timestamp = encoder->timestamp = s->lame_samples / (double)encoder->target_samplerate;
    packet.data = buffer;
    encoder_write_packet_all(encoder, &packet);
    return 1;
    }

static void live_mp3_encoder_main(struct encoder *encoder)
    {
    struct lm3e_data * const s = encoder->encoder_private;
    struct encoder_ip_data *id;
    int mp3bytes = 0;

    if (encoder->encoder_state == ES_STARTING)
        {
        if (!(s->mp3buf = malloc(s->mp3bufsize = (int)(1.25 * 8192.0 + 7200.0))))
            {
            fprintf(stderr, "live_mp3_encoder_main: malloc failure\n");
            goto bailout;
            }
            
        if (!(s->gfp = lame_init()))
            {
            fprintf(stderr, "live_mp3_encoder_main: failed to initialise LAME\n");
            free(s->mp3buf);
            goto bailout;
            }

        lame_set_num_channels(s->gfp, encoder->n_channels);
        lame_set_brate(s->gfp, encoder->bitrate);
        lame_set_in_samplerate(s->gfp, encoder->target_samplerate);
        lame_set_out_samplerate(s->gfp, encoder->target_samplerate);
        lame_set_mode(s->gfp, s->lame_mode);
        lame_set_quality(s->gfp, s->lame_quality);
        lame_set_bWriteVbrTag(s->gfp, 0);
        lame_set_scale(s->gfp, 32767.0f);
        if (lame_init_params(s->gfp) < 0)
            {
            fprintf(stderr, "live_mp3_encoder_main: LAME rejected the parameters given\n");
            lame_close(s->gfp);
            free(s->mp3buf);
            goto bailout;
            }

        ++encoder->oggserial;
        s->packetflags = PF_INITIAL;
        s->lame_samples = 0;
        if (encoder->run_request_f)
            encoder->encoder_state = ES_RUNNING;
        else
            encoder->encoder_state = ES_STOPPING;
        return;
        }
    if (encoder->encoder_state == ES_RUNNING)
        {
        if (encoder->flush || !encoder->run_request_f)
            {
            encoder->flush = FALSE;
            mp3bytes = lame_encode_flush_nogap(s->gfp, s->mp3buf, s->mp3bufsize);
            fprintf(stderr, "live_mp3_encoder_main: flushing %d bytes\n", mp3bytes);
            live_mp3_write_packet(encoder, s, s->mp3buf, mp3bytes, PF_MP3 | PF_FINAL);
            encoder->encoder_state = ES_STOPPING;
            }
        else
            {
            if ((id = encoder_get_input_data(encoder, 1024, 8192, NULL)))
                {
                mp3bytes = lame_encode_buffer_float(s->gfp, id->buffer[0], id->buffer[1], id->qty_samples, s->mp3buf, s->mp3bufsize);
                s->lame_samples += id->qty_samples;
                encoder_ip_data_free(id);
                live_mp3_write_packet(encoder, s, s->mp3buf, mp3bytes, PF_MP3 | s->packetflags);
                s->packetflags = PF_UNSET;
                }
            if (encoder->new_metadata && encoder->use_metadata)
                {
                live_mp3_packetize_metadata(encoder, s);
                if (s->metadata)
                    live_mp3_write_packet(encoder, s, (unsigned char *)s->metadata, strlen(s->metadata) + 1, PF_METADATA);
                }
            }
        return;
        }
    if (encoder->encoder_state == ES_STOPPING)
        {
        lame_close(s->gfp);
        free(s->mp3buf);
        if (encoder->run_request_f)
            {
            encoder->encoder_state = ES_STARTING;
            return;
            }
        }
    bailout:
    fprintf(stderr, "live_mp3_encoder_main: performing cleanup\n");
    encoder->run_request_f = FALSE;
    encoder->encoder_state = ES_STOPPED;
    encoder->run_encoder = NULL;
    encoder->flush = FALSE;
    encoder->encoder_private = NULL;
    if (s->metadata)
        free(s->metadata);
    free(s);
    fprintf(stderr, "live_mp3_encoder_main: finished cleanup\n");
    }

int live_mp3_encoder_init(struct encoder *encoder, struct encoder_vars *ev)
    {
    struct lm3e_data * const s = calloc(1, sizeof (struct lm3e_data));

    if (!s)
        {
        fprintf(stderr, "live_mp3_encoder: malloc failure\n");
        return FAILED;
        }
    if (!(strcmp("stereo", ev->mode)))
        s->lame_mode = 0;
    else if (!(strcmp("jointstereo", ev->mode)))
        s->lame_mode = 1;
    else if (!(strcmp("mono", ev->mode)))
        s->lame_mode = 3;
    s->lame_quality = atoi(ev->quality);
    encoder->encoder_private = s;
    encoder->run_encoder = live_mp3_encoder_main;
    return SUCCEEDED;
    }

