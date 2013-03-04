/*
#   live_oggopus_encoder.c: encode Ogg/Opus format streams
#   Copyright (C) 2013 Stephen Fairchild (s-fairchild@users.sourceforge.net)
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
#include <jack/ringbuffer.h>
#include <ogg/ogg.h>
#include <opus/opus.h>

#include "sourceclient.h"
#include "live_ogg_encoder.h"
#include "live_oggopus_encoder.h"
#include "vorbistagparse.h"


struct local_data {
    OpusEncoder *enc_st;
    int complexity;
    int postgain;
    int framesamples;
    int lookahead;
    int vbr;
    int vbr_constraint;
    opus_int32 pagepackets;
    opus_int32 pagepackets_max;
    ogg_int64_t granulepos;
    ogg_int64_t packetno;
    ogg_stream_state os;
    int pflags;
    float *inbuf;
    size_t outbuf_siz;
    unsigned char *outbuf;
    struct vtag_block metadata_block;
    int fillbytes;
};

/* create a multiplexed pcm stream */
static void stereomix(float *l, float *r, float *m, size_t n)
    {
    while (n--)
        {
        *m++ = *l++;
        *m++ = *r++;
        }
    }

static void live_oggopus_encoder_main(struct encoder *encoder)
    {
    struct local_data * const s = encoder->encoder_private;
    ogg_page og, og2;
    ogg_packet op;

    if (encoder->encoder_state == ES_STARTING)
        {
        const opus_int32 la_fallback = 196;
        int error;
            
        fprintf(stderr, "live_ogg_encoder_main: info: writing headers\n");

        encoder->timestamp = 0.0;
        ogg_stream_init(&s->os, ++encoder->oggserial);
       
        if (!(s->enc_st = opus_encoder_create(48000, encoder->n_channels, OPUS_APPLICATION_AUDIO, &error)))
            {
            fprintf(stderr, "live_oggopus_encoder_main: failure: encoder_create: %s\n", opus_strerror(error));
            goto bailout;
            }

        if (opus_encoder_ctl(s->enc_st, OPUS_SET_BITRATE(encoder->bitrate * 1000)) != OPUS_OK)
            {
            fprintf(stderr, "live_oggopus_encoder_main: failure: failed to set bitrate\n");
            goto bailout;
            }
           
        if (opus_encoder_ctl(s->enc_st, OPUS_SET_VBR(s->vbr)) != OPUS_OK)
            {
            fprintf(stderr, "live_oggopus_encoder_main: failure: failed to set cbr/vbr\n");
            goto bailout;
            }
            
        if (opus_encoder_ctl(s->enc_st, OPUS_SET_VBR_CONSTRAINT(s->vbr_constraint)) != OPUS_OK)
            {
            fprintf(stderr, "live_oggopus_encoder_main: failure: failed to set vbr constraint\n");
            goto bailout;
            }
            
        if (opus_encoder_ctl(s->enc_st, OPUS_SET_COMPLEXITY(s->complexity)) != OPUS_OK)
            fprintf(stderr, "live_oggopus_encoder_main: warning: failed to set complexity\n");

        if (opus_encoder_ctl(s->enc_st, OPUS_GET_LOOKAHEAD(&s->lookahead)) != OPUS_OK)
            {
            fprintf(stderr, "live_oggopus_encoder_main: warning: failed to get lookahead value -- using %d\n", la_fallback);
            s->lookahead = la_fallback;
            }

        char header_packet_data[20];
        size_t header_packet_size = snprintf(header_packet_data, sizeof header_packet_data,
            "OpusHead\x1%c%c%c\x80\xbb%c%c%c%c%c",
            encoder->n_channels,
            s->lookahead & 0xFF, (s->lookahead >> 8) & 0xFF,
            '\0', '\0',
            s->postgain & 0xFF, (s->postgain >> 8) & 0xFF,
            '\0');

        op.packet = (unsigned char *)header_packet_data;
        op.bytes = header_packet_size;
        op.b_o_s = 1;
        op.e_o_s = 0;
        op.granulepos = 0;
        op.packetno = s->packetno++;
        ogg_stream_packetin(&s->os, &op);
        s->pflags = PF_INITIAL | PF_OGG | PF_HEADER;

        if (ogg_stream_flush(&s->os, &og))
            {
            if (ogg_stream_flush(&s->os, &og2))
                {
                fprintf(stderr, "live_oggopus_encoder_main: error: initial header spans page boundary\n");
                goto bailout;
                }

            if (!(live_ogg_write_packet(encoder, &og, s->pflags)))
                {
                fprintf(stderr, "live_oggopus_encoder_main: error: failed to write header\n");
                goto bailout;
                }

            s->pflags = PF_OGG | PF_HEADER;
            }

        if (encoder->new_metadata || !s->metadata_block.data)
            {
            struct vtag *tag;
            
            if (!(tag = vtag_new(opus_get_version_string(), &error)))
                {
                fprintf(stderr, "live_oggopus_encoder_main: error: failed to initialise empty vtag: %s\n", vtag_strerror(error));
                goto bailout;
                }
            
            vtag_append(tag, "encoder", getenv("app_name"));

            if (encoder->use_metadata)
                {
                struct ogg_tag_data t = {};
                    
                fprintf(stderr, "live_oggopus_encoder_main: info: making metadata\n");
                live_ogg_capture_metadata(encoder, &t);
                if (t.custom && t.custom[0])
                    {
                    vtag_append(tag, "title", t.custom);
                    vtag_append(tag, "trk-artist", t.artist);
                    vtag_append(tag, "trk-title", t.title);
                    vtag_append(tag, "trk-album", t.album);
                    }
                else
                    {
                    vtag_append(tag, "artist", t.artist);
                    vtag_append(tag, "title", t.title);
                    vtag_append(tag, "album", t.album);
                    }

                live_ogg_free_metadata(&t);
                }
            else
                fprintf(stderr, "live_oggopus_encoder_main: info: making bare-bones metadata\n");

            if ((error = vtag_serialize(tag, &s->metadata_block, "OpusTags")))
                {
                fprintf(stderr, "live_oggopus_encoder_main: vtag_serialize failed: %s\n", vtag_strerror(error));
                goto bailout;
                }

            vtag_cleanup(tag);
            encoder->new_metadata = FALSE;
            }
        else
            fprintf(stderr, "live_oggopus_encoder_main: info: using previous metadata\n");

        op.packet = (unsigned char *)s->metadata_block.data;
        op.bytes = s->metadata_block.length;
        op.b_o_s = 0;
        op.e_o_s = 0;
        op.granulepos = 0;
        op.packetno = s->packetno++;
        ogg_stream_packetin(&s->os, &op);

        while (ogg_stream_flush(&s->os, &og))
            {
            if (!(live_ogg_write_packet(encoder, &og, s->pflags)))
                {
                fprintf(stderr, "live_oggopus_encoder_main: error: failed to write header\n");
                goto bailout;
                }

            s->pflags = PF_OGG;
            }
       
        encoder->encoder_state = ES_RUNNING;
        fprintf(stderr, "live_ogg_encoder_main: info: encoding\n");
        return;
        }

    if (encoder->encoder_state == ES_RUNNING)
        {
        struct encoder_ip_data *id;
        opus_int32 enc_bytes;
        float *inbuf;

        if (encoder->new_metadata || !encoder->run_request_f || encoder->flush)
            {
            encoder->flush = FALSE;
            encoder->encoder_state = ES_STOPPING;
            return;
            }

        if((id = encoder_get_input_data(encoder, s->framesamples, s->framesamples, NULL)))
            {
            if (encoder->n_channels == 2)
                stereomix(id->buffer[0], id->buffer[1], inbuf = s->inbuf, s->framesamples);
            else
                inbuf = id->buffer[0];
            enc_bytes = opus_encode_float(s->enc_st, inbuf, s->framesamples, s->outbuf, s->outbuf_siz);
            encoder_ip_data_free(id);

            if (enc_bytes > 0)
                {
                op.packet = s->outbuf;
                op.bytes = enc_bytes;
                op.b_o_s = 0;
                op.e_o_s = 0;
                op.granulepos = (s->granulepos += s->framesamples);
                op.packetno = s->packetno++;
                ogg_stream_packetin(&s->os, &op);
                
                s->fillbytes += enc_bytes;
                if (++s->pagepackets == s->pagepackets_max)
                    {
                    s->pagepackets = 0;
                    if (ogg_stream_flush_fill(&s->os, &og, s->fillbytes))
                        {
                        if (!live_ogg_write_packet(encoder, &og, s->pflags))
                            {
                            fprintf(stderr, "live_oggopus_encoder_main: failed to write packet\n");
                            goto bailout;
                            }
                            
                        if ((s->fillbytes -= og.body_len))
                            fprintf(stderr, "!!! packet size limit exceeded\n");
                        }
                    else
                        fprintf(stderr, "live_oggopus_encoder_main: failed to flush page\n");
                    }
                }
            else
                {
                fprintf(stderr, "live_oggopus_encoder_main: failed to encode packet: %s\n", opus_strerror(enc_bytes));
                goto bailout;
                }
            }

        return;
        }

    if (encoder->encoder_state == ES_STOPPING)
        {
        opus_int32 enc_bytes;

        fprintf(stderr, "live_oggopus_encoder_main: flushing\n");

        /* fill input buffer with silence */
        memset(s->inbuf, '\0', sizeof (float) * s->framesamples * encoder->n_channels);

        do
            {
            enc_bytes = opus_encode_float(s->enc_st, s->inbuf, s->framesamples, s->outbuf, s->outbuf_siz);
            if (enc_bytes > 0)
                {
                if (s->framesamples < s->lookahead)
                    {
                    op.granulepos += s->framesamples;
                    op.e_o_s = 0;
                    s->lookahead -= s->framesamples;
                    }
                else
                    {
                    op.granulepos += s->lookahead;
                    op.e_o_s = 1;
                    s->lookahead = 0;
                    s->pflags |= PF_FINAL;
                    }
                    
                op.packet = s->outbuf;
                op.bytes = enc_bytes;
                op.b_o_s = 0;
                op.packetno = s->packetno++;
                ogg_stream_packetin(&s->os, &op);

                s->fillbytes += enc_bytes;
                if (++s->pagepackets == s->pagepackets_max || op.e_o_s)
                    {
                    s->pagepackets = 0;
                    if (ogg_stream_flush_fill(&s->os, &og, s->fillbytes))
                        {
                        if (!live_ogg_write_packet(encoder, &og, s->pflags))
                            {
                            fprintf(stderr, "live_oggopus_encoder_main: failed to write packet\n");
                            goto bailout;
                            }
                            
                        if ((s->fillbytes -= og.body_len))
                            fprintf(stderr, "!!! packet size limit exceeded\n");
                        }
                    else
                        fprintf(stderr, "live_oggopus_encoder_main: failed to flush page\n");
                    }
                }
            else
                {
                fprintf(stderr, "live_oggopus_encoder_main: failed to encode packet: %s\n", opus_strerror(enc_bytes));
                goto bailout; 
                }
            } while (!op.e_o_s);

        
        if (!encoder->run_request_f)
            goto bailout;
        else
            {
            opus_encoder_destroy(s->enc_st);
            ogg_stream_clear(&s->os);
            s->granulepos = s->packetno = s->pagepackets = s->fillbytes = 0;
            fprintf(stderr, "live_oggopus_encoder_main: minimal clean up\n");
            encoder->encoder_state = ES_STARTING;
            }

        return;
        }

    fprintf(stderr, "live_oggopus_encoder_main: unhandled encoder state\n");
    return;

    bailout:
    fprintf(stderr, "live_oggopus_encoder_main: cleanup\n");
    encoder->run_request_f = FALSE;
    encoder->encoder_state = ES_STOPPED;
    encoder->run_encoder = NULL;
    encoder->flush = FALSE;
    encoder->encoder_private = NULL;
    vtag_block_cleanup(&s->metadata_block);
    if (s->enc_st)
        opus_encoder_destroy(s->enc_st);
    ogg_stream_clear(&s->os);
    free(s->inbuf);
    free(s->outbuf);
    free(s);
    fprintf(stderr, "live_oggopus_encoder_main: finished cleanup\n");
    return;
    }

int live_oggopus_encoder_init(struct encoder *encoder, struct encoder_vars *ev)
    {    
    struct local_data * const s = calloc(1, sizeof (struct local_data));

    if (!s)
        {
        fprintf(stderr, "live_oggopus_encoder: malloc failure\n");
        return FAILED;
        }

    s->complexity = atoi(ev->complexity);
    s->postgain = atoi(ev->postgain);
    s->framesamples = atoi(ev->framesize) * 48;
    s->pagepackets_max = 48000 / s->framesamples / 5;
    if (!strcmp(ev->variability, "cbr"))
        s->vbr = 0;
    else
        {
        s->vbr = 1;
        if (!strcmp(ev->variability, "cvbr"))
            s->vbr_constraint = 1;
        else
            {
            s->vbr_constraint = 0;
            if (strcmp(ev->variability, "vbr"))
                {
                fprintf(stderr, "live_gggopus_encoder: bad variability setting\n");
                free(s);
                return FAILED;
                }
            }
        }
    
    if (!(s->inbuf = malloc(sizeof (float) * encoder->n_channels * s->framesamples)))
        {
        fprintf(stderr, "live_oggopus_encoder: malloc failure\n");
        free(s);
        return FAILED;
        }

    s->outbuf_siz = encoder->bitrate * s->framesamples / 174;
    if (!(s->outbuf = malloc(s->outbuf_siz)))
        {
        fprintf(stderr, "live_oggopus_encoder: malloc failure\n");
        free(s->inbuf);
        free(s);
        return FAILED;
        }
        
    if (!vtag_block_init(&s->metadata_block))
        {
        fprintf(stderr, "live_oggopus_encoder: malloc failure\n");
        free(s->outbuf);
        free(s->inbuf);
        free(s);
        return FAILED;
        }

    encoder->encoder_private = s;
    encoder->run_encoder = live_oggopus_encoder_main;
    return SUCCEEDED;
    }

#endif /* HAVE_OPUS */
