/*
#   live_ogg_encoder.c: encode ogg files from a live source
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

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include <math.h>
#include <vorbis/vorbisenc.h>
#include <jack/ringbuffer.h>
#include "sourceclient.h"
#include "live_ogg_encoder.h"

#define READSIZE 1024

typedef jack_default_audio_sample_t sample_t;

struct loe_data
    {
    struct ogg_tag_data tag_data;
    long max_bitrate;            /* ogg upper and lower bitrate settings */
    long min_bitrate;
    vorbis_info      vi;
    vorbis_block     vb;
    vorbis_dsp_state vd;
    vorbis_comment   vc;
    ogg_stream_state os;
    ogg_page         og;
    ogg_packet       op;
    int pagesamples;
    int (*owf)(ogg_stream_state *os, ogg_page *og);
    };

void live_ogg_capture_metadata(struct encoder *e, struct ogg_tag_data *t)
    {
    live_ogg_free_metadata(t);

    pthread_mutex_lock(&e->metadata_mutex);
    t->custom = strdup(e->custom_meta);
    t->artist = strdup(e->artist);
    t->title  = strdup(e->title);
    t->album  = strdup(e->album);
    e->new_metadata = FALSE;
    pthread_mutex_unlock(&e->metadata_mutex);
    }

void live_ogg_free_metadata(struct ogg_tag_data *t)
    {
    if (t->custom)
        free(t->custom);
    if (t->artist)
        free(t->artist);
    if (t->title)
        free(t->title);
    if (t->album)
        free(t->album);
    memset(t, '\0', sizeof (struct ogg_tag_data));
    }

int live_ogg_write_packet(struct encoder *encoder, ogg_page *op, int flags)
    {
    struct encoder_op_packet packet;
    char *buffer;

    if (!(buffer = malloc(op->header_len + op->body_len)))
        {
        fprintf(stderr, "live_ogg_write_packet: malloc failure\n");
        return 0;
        }
    memcpy(buffer, op->header, op->header_len);
    memcpy(buffer + op->header_len, op->body, op->body_len);
    packet.header.bit_rate = encoder->bitrate;
    packet.header.sample_rate = encoder->target_samplerate;
    packet.header.n_channels = encoder->n_channels;
    packet.header.flags = flags;
    packet.header.data_size = op->header_len + op->body_len;
    packet.header.timestamp = encoder->timestamp = (double)ogg_page_granulepos(op) / (double)encoder->samplerate;
    packet.data = buffer;
    encoder_write_packet_all(encoder, &packet);
    free(buffer);
    return 1;
    }

static void live_ogg_encoder_main(struct encoder *encoder)
    {
    struct loe_data * const s = encoder->encoder_private;
    struct ovectl_ratemanage2_arg ai;
    struct encoder_ip_data *input_data;
    ogg_packet header_main;
    ogg_packet header_comments;
    ogg_packet header_codebooks;
    int cycle_restart = FALSE, cycle_restart2 = FALSE, packet_flags = PF_INITIAL | PF_OGG | PF_HEADER;
    float **buffer;
    ogg_int64_t oldgranulepos;
    struct ogg_tag_data *t = &s->tag_data;
    
    if (encoder->encoder_state == ES_STARTING)
        {
        fprintf(stderr, "live_ogg_encoder_main: first pass of the encoder\n");
        vorbis_info_init(&s->vi);
        if (vorbis_encode_setup_managed(&s->vi, encoder->n_channels, encoder->target_samplerate, s->max_bitrate, encoder->bitrate, s->min_bitrate))
            {
            fprintf(stderr, "live_ogg_encoder_main: mode initialisation failed\n");
            vorbis_info_clear(&s->vi);
            goto bailout;
            }

        vorbis_encode_ctl(&s->vi, OV_ECTL_RATEMANAGE2_GET, &ai);
        ai.bitrate_limit_min_kbps = s->min_bitrate / 1000;
        if (vorbis_encode_ctl(&s->vi, OV_ECTL_RATEMANAGE2_SET, &ai))
            fprintf(stderr, "live_ogg_encoder_main: failed to set hard bitrate floor\n");
            
        vorbis_encode_setup_init(&s->vi);
        vorbis_analysis_init(&s->vd, &s->vi);
        vorbis_block_init(&s->vd, &s->vb);
        ogg_stream_init(&s->os, ++encoder->oggserial);
        encoder->timestamp = 0.0;
        vorbis_comment_init(&s->vc);
        /* this function takes raw metadata and does something type specific with it */
        if (encoder->new_metadata)
            live_ogg_capture_metadata(encoder, t);
        
        if (t->custom && t->custom[0])
            {
            vorbis_comment_add_tag(&s->vc, "TITLE", t->custom);
            if (t->artist && t->artist[0])
                vorbis_comment_add_tag(&s->vc, "TRK-ARTIST", t->artist);
            if (t->title && t->title[0])
                vorbis_comment_add_tag(&s->vc, "TRK-TITLE", t->title);
            if (t->album && t->album[0])
                vorbis_comment_add_tag(&s->vc, "TRK-ALBUM", t->album);
            }
        else
            {
            if (t->artist && t->artist[0])
                vorbis_comment_add_tag(&s->vc, "ARTIST", t->artist);
            if (t->title && t->title[0])
                vorbis_comment_add_tag(&s->vc, "TITLE", t->title);
            if (t->album && t->album[0])
                vorbis_comment_add_tag(&s->vc, "ALBUM", t->album);
            }
        vorbis_analysis_headerout(&s->vd, &s->vc, &header_main, &header_comments, &header_codebooks);
        ogg_stream_packetin(&s->os, &header_main);
        ogg_stream_packetin(&s->os, &header_comments);
        ogg_stream_packetin(&s->os, &header_codebooks);
        while (ogg_stream_flush(&s->os, &s->og))
            {
            if (!(live_ogg_write_packet(encoder, &s->og, packet_flags)))
                {
                fprintf(stderr, "live_ogg_encoder_main: failed writing header to stream\n");
                encoder->run_request_f = FALSE;
                encoder->encoder_state = ES_STOPPING;
                return;
                }
            packet_flags = PF_OGG | PF_HEADER;
            }
        s->pagesamples = 0;
        s->owf = ogg_stream_pageout;
        encoder->encoder_state = ES_RUNNING;
        return;
        }
    if (encoder->encoder_state == ES_RUNNING)
        {
        if (encoder->flush)
            {
            cycle_restart = TRUE;
            encoder->flush = FALSE;
            }
        cycle_restart |= encoder->new_metadata | !encoder->run_request_f;
        if (cycle_restart)
            {
            fprintf(stderr, "live_ogg_encoder_main: cycle restart\n");
            buffer = vorbis_analysis_buffer(&s->vd, 0);
            vorbis_analysis_wrote(&s->vd, 0);
            }
        else
            {
            buffer = vorbis_analysis_buffer(&s->vd, 8192);
            input_data = encoder_get_input_data(encoder, 1024, 8192, buffer);
            if (input_data)
                {
                vorbis_analysis_wrote(&s->vd, input_data->qty_samples);
                encoder_ip_data_free(input_data);
                }
            else
                return;
            }
        while (vorbis_analysis_blockout(&s->vd, &s->vb) == 1)
            {
            vorbis_analysis(&s->vb, NULL);
            vorbis_bitrate_addblock(&s->vb);
            while (vorbis_bitrate_flushpacket(&s->vd, &s->op))
                {
                oldgranulepos = s->os.granulepos;
                ogg_stream_packetin(&s->os, &s->op);
                s->pagesamples += s->os.granulepos - oldgranulepos;
                /* write out a new ogg page at least 10 times a second */
                if (s->pagesamples > encoder->samplerate / 10)
                    s->owf = ogg_stream_flush;
                while (s->owf(&s->os, &s->og))
                    {
                    s->owf = ogg_stream_pageout;
                    s->pagesamples = 0;
                    if (ogg_page_eos(&s->og))
                        {
                        fprintf(stderr, "live_ogg_encoder_main: writing final packet\n");
                        live_ogg_write_packet(encoder, &s->og, PF_OGG | PF_FINAL);
                        cycle_restart2 = TRUE;
                        break;
                        }
                    else
                        live_ogg_write_packet(encoder, &s->og, PF_OGG);
                    }
                }
            }
        if (cycle_restart2)
            encoder->encoder_state = ES_STOPPING;
        return;
        }
    if (encoder->encoder_state == ES_STOPPING)
        {
        fprintf(stderr, "live_ogg_encoder_main: last pass of the encoder, freeing libvorbis structures\n");
        ogg_stream_clear(&s->os);
        vorbis_block_clear(&s->vb);
        vorbis_dsp_clear(&s->vd);
        vorbis_comment_clear(&s->vc);
        vorbis_info_clear(&s->vi);
        fprintf(stderr, "live_ogg_encoder_main: libvorbis structures freed\n");
        if (!encoder->run_request_f)
            goto bailout;
        else
            encoder->encoder_state = ES_STARTING;
        return;
        }
    fprintf(stderr, "live_ogg_encoder_main: unhandled encoder state\n");
    return;
    bailout:
    fprintf(stderr, "live_ogg_encoder_main: performing cleanup\n");
    encoder->run_request_f = FALSE;
    encoder->encoder_state = ES_STOPPED;
    encoder->run_encoder = NULL;
    encoder->flush = FALSE;
    encoder->encoder_private = NULL;
    live_ogg_free_metadata(&s->tag_data);
    free(s);
    fprintf(stderr, "live_ogg_encoder_main: finished cleanup\n");
    return;
    }

int live_ogg_encoder_init(struct encoder *encoder, struct encoder_vars *ev)
    {
    struct loe_data * const s = calloc(1, sizeof (struct loe_data));

    if (!s)
        {
        fprintf(stderr, "live_ogg_encoder: malloc failure\n");
        return FAILED;
        }

    if (!strcmp(ev->variability, "constant"))
        s->max_bitrate = s->min_bitrate = encoder->bitrate;
    else
        {
        long var = encoder->bitrate * atol(ev->variability) / 100;
        
        s->max_bitrate = encoder->bitrate + var;
        s->min_bitrate = encoder->bitrate - var;
        }

    encoder->encoder_private = s;
    encoder->run_encoder = live_ogg_encoder_main;
    return SUCCEEDED;
    }
