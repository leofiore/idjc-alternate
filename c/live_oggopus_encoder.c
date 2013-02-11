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
    struct ogg_tag_data tag_data;
    OpusEncoder *enc_st;
    int complexity;
    int postgain;
    opus_int32 lookahead;
    ogg_stream_state os;
    int pflags;

};

#if 0
#define readint(buf, base) (((buf[base+3]<<24)&0xff000000)| \
                                    ((buf[base+2]<<16)&0xff0000)| \
                                    ((buf[base+1]<<8)&0xff00)| \
                                     (buf[base]&0xff))

#define writeint(buf, base, val) do{ buf[base+3]=((val)>>24)&0xff; \
                                                 buf[base+2]=((val)>>16)&0xff; \
                                                 buf[base+1]=((val)>>8)&0xff; \
                                                 buf[base]=(val)&0xff; \
                                            }while(0)

static char *prepend(char *before, char *after)
    {
    char *new;
    
    if (!(new = malloc(strlen(before) + strlen(after) + 1)))
        {
        fprintf(stderr, "malloc failure\n");
        return NULL;
        }
        
    strcpy(new, before);
    strcat(new, after);
    free(after);
    return new;
    }

#define PREPEND(b, a) do {a = prepend(b, a); items++; s->metadata_vclen += (4 + strlen(a));} while (0)
#define CPREPEND(b, a) do {if (a && a[0]) { PREPEND(b, a); }} while (0)
#define APPEND(a) do {if (a && a[0]) { writeint(s->metadata_vc, base, (len = strlen(a))); memcpy(s->metadata_vc + base + 4, a, len); base += 4 + len; }} while (0)

static void live_oggopus_build_metadata(struct encoder *encoder, struct local_data *s)
    {
    int len;
    int items = 0;
    size_t base;
    struct ogg_tag_data *t = &s->tag_data;

    /* build a vorbis comment block */
    s->metadata_vclen = 8 + s->vs_len;
    if (encoder->new_metadata)
        live_ogg_capture_metadata(encoder, t);

    if (t->custom && t->custom[0])
        {
        PREPEND("title=", t->custom);
        CPREPEND("trk-artist=", t->artist);
        CPREPEND("trk-title=", t->title);
        CPREPEND("trk-album=", t->album);
        }
    else
        {
        CPREPEND("artist=", t->artist);
        CPREPEND("title=", t->title);
        CPREPEND("album=", t->album);
        }

    if (!(s->metadata_vc = realloc(s->metadata_vc, s->metadata_vclen)))
        {
        fprintf(stderr, "live_oggopus_build_metadata: malloc failure\n");
        s->metadata_vclen = 0;
        return;
        }

    writeint(s->metadata_vc, 0, s->vs_len);
    memcpy(s->metadata_vc + 4, s->vendor_string, s->vs_len);
    writeint(s->metadata_vc, 4 + s->vs_len, items);
    base = 8 + s->vs_len;
    
    APPEND(t->custom);
    APPEND(t->artist);
    APPEND(t->title);
    APPEND(t->album);
    
    if (base != s->metadata_vclen)
        fprintf(stderr, "live_oggopus_build_metadata: incorrect size assumption %d, %d\n", base, s->metadata_vclen);
    else
        fprintf(stderr, "vorbis comment created successfully\n");
    }
#endif /* 0 */

static void live_oggopus_encoder_main(struct encoder *encoder)
    {
    struct local_data * const s = encoder->encoder_private;
    ogg_page og, og2;
    ogg_packet op;

    if (encoder->encoder_state == ES_STARTING)
        {
        const opus_int32 la_fallback = 196;
        int error;
            
        fprintf(stderr, "live_ogg_encoder_main: info: first pass of the encoder\n");

        encoder->timestamp = 0.0;
        ogg_stream_init(&s->os, ++encoder->oggserial);
       
        if (!(s->enc_st = opus_encoder_create(48000, encoder->n_channels, OPUS_APPLICATION_AUDIO, &error)))
            {
            fprintf(stderr, "live_oggopus_encoder_main: failure: encoder_create: %s\n", opus_strerror(error));
            goto bailout;
            }

        if (opus_encoder_ctl(s->enc_st, OPUS_SET_BITRATE(1000 * encoder->bitrate) != OPUS_OK))
            {
            fprintf(stderr, "live_oggopus_encoder_main: failure: failed to set bitrate\n");
            goto bailout;
            }
            
        if (opus_encoder_ctl(s->enc_st, OPUS_SET_VBR(0)) != OPUS_OK)
            {
            fprintf(stderr, "live_oggopus_encoder_main: failure: failed to set cbr/vbr\n");
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
            "OpusHead\x1%c%c%c%c%c\xb0\xbb%c%c%c",
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
        op.packetno = 0;
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
            
        struct vtag *tag;
        struct ogg_tag_data *t = &s->tag_data;
        
        if (!(tag = vtag_new(opus_get_version_string(), &error)))
            {
            fprintf(stderr, "live_oggopus_encoder_main: error: failed to initialise empty vtag: %s\n", vtag_error_string(error));
            goto bailout;
            }
            
        live_ogg_capture_metadata(encoder, t);
        if (t->custom && t->custom[0])
            {
            vtag_append(tag, "title", t->custom);
            vtag_append(tag, "trk-artist", t->artist);
            vtag_append(tag, "trk-title", t->title);
            vtag_append(tag, "trk-album", t->album);
            }
        else
            {
            vtag_append(tag, "artist", t->artist);
            vtag_append(tag, "title", t->title);
            vtag_append(tag, "album", t->album);
            }

        live_ogg_free_metadata(t);
        char *tags_packet_data;
        size_t tags_packet_size;
        
        if ((error = vtag_serialize(tag, &tags_packet_data, &tags_packet_size, "OpusTags")))
            {
            fprintf(stderr, "live_oggopus_encoder_main: vtag_serialize failed: %s\n", vtag_error_string(error));
            goto bailout;
            }

        vtag_cleanup(tag);

        op.packet = (unsigned char *)tags_packet_data;
        op.bytes = tags_packet_size;
        op.b_o_s = 0;
        op.e_o_s = 0;
        op.granulepos = 0;
        op.packetno = 1;
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

        goto bailout;
       

#if 0
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
#endif
        encoder->encoder_state = ES_RUNNING;

        return;
        }

    if (encoder->encoder_state == ES_RUNNING)
        {

        return;
        }

    if (encoder->encoder_state == ES_STOPPING)
        {
        fprintf(stderr, "live_oggopus_encoder_main: last pass of the encoder\n");
        ogg_stream_clear(&s->os);
        // other cleanup here

        fprintf(stderr, "live_oggopus_encoder_main: libvorbis structures freed\n");
        if (!encoder->run_request_f)
            goto bailout;
        else
            encoder->encoder_state = ES_STARTING;

        return;
        }

    fprintf(stderr, "live_oggopus_encoder_main: unhandled encoder state\n");
    return;

    bailout:
    fprintf(stderr, "live_oggopus_encoder_main: performing cleanup\n");
    encoder->run_request_f = FALSE;
    encoder->encoder_state = ES_STOPPED;
    encoder->run_encoder = NULL;
    encoder->flush = FALSE;
    encoder->encoder_private = NULL;
    if (s->enc_st)
        opus_encoder_destroy(s->enc_st);
    ogg_stream_clear(&s->os);
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
    encoder->encoder_private = s;
    encoder->run_encoder = live_oggopus_encoder_main;
    return SUCCEEDED;
    }

#endif /* HAVE_OPUS */
