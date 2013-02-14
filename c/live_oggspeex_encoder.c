/*
#   live_oggspeex_encoder.c: encode speex from a live source into an ogg container
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
#include <string.h>
#include <speex/speex.h>
#include <speex/speex_header.h>
#include <speex/speex_stereo.h>
#include <ogg/ogg.h>

#include "sourceclient.h"
#include "live_ogg_encoder.h"
#include "live_oggspeex_encoder.h"
#include "vorbistagparse.h"

#define SUCCEEDED 1
#define FAILED 0
#define MAX_FRAME_BYTES 2000

enum speex_mode { SM_UWB, SM_WB, SM_NB };

struct lose_data
    {
    struct ogg_tag_data tag_data;
    void *enc_state;
    SpeexBits bits;
    int fsamples;              /* number of samples in a frame */
    float *inbuf;
    ogg_stream_state os;
    int pflags;
    int packetno;
    int frame;
    int frames_encoded;
    int total_samples;
    int samples_encoded;
    int lookahead;
    int eos;
    char vendor_string[64];
    size_t vs_len;
    struct SpeexMode const *mode;
    int quality;
    int complexity;
    struct vtag_block metadata_block;
    enum packet_flags flags;
    };

static void live_oggspeex_encoder_monomix(float *in, float *out, size_t n)
    {
    while (n--)
        *out++ = *in++ * 32768;
    }
    
static void live_oggspeex_encoder_stereomix(float *l, float *r, float *m, size_t n)
    {
    while (n--)
        {
        *m++ = *l++ * 32768;
        *m++ = *r++ * 32768;
        }
    }

static void live_oggspeex_encoder_main(struct encoder *encoder)
    {
    struct lose_data * const s = encoder->encoder_private;
    ogg_page og;
    ogg_packet op;
    
    if (encoder->encoder_state == ES_STARTING)
        {
        SpeexHeader header;
        char *packet;
        int packet_size;
        int error;
        
        speex_bits_init(&s->bits);
        if (!(s->enc_state = speex_encoder_init(s->mode)))
            {
            fprintf(stderr, "live_oggspeex_encoder_main: failed to initialise speex encoder\n");
            goto bailout;
            }
            
        speex_encoder_ctl(s->enc_state, SPEEX_GET_FRAME_SIZE, &s->fsamples);
        speex_encoder_ctl(s->enc_state, SPEEX_SET_QUALITY, &s->quality);
        speex_encoder_ctl(s->enc_state, SPEEX_SET_COMPLEXITY, &s->complexity);
        speex_encoder_ctl(s->enc_state, SPEEX_GET_LOOKAHEAD, &s->lookahead);
        
        if (!(s->inbuf = realloc(s->inbuf, s->fsamples * encoder->n_channels * sizeof (float))))
            {
            fprintf(stderr, "live_oggspeex_encoder_main: malloc failure\n");
            goto bailout;
            }
        
        speex_init_header(&header, encoder->target_samplerate, encoder->n_channels, s->mode);
        header.frames_per_packet = 1;
        if (!(packet = speex_header_to_packet(&header, &packet_size)))
            {
            fprintf(stderr, "live_oggspeex_encoder_main: failed to make header packet\n");
            goto bailout;
            }
            
        ogg_stream_init(&s->os, ++encoder->oggserial);
        op.packet = (unsigned char *)packet;
        op.bytes = packet_size;
        op.b_o_s = 1;
        op.e_o_s = 0;
        op.granulepos = 0;
        op.packetno = 0;
        ogg_stream_packetin(&s->os, &op);
        speex_header_free(packet);
        s->pflags = PF_INITIAL | PF_OGG | PF_HEADER;
        
        while (ogg_stream_flush(&s->os, &og))
            {
            if (!(live_ogg_write_packet(encoder, &og, s->pflags)))
                {
                fprintf(stderr, "live_ogg_write_packet: failed to write header\n");
                goto bailout;
                }
            s->pflags = PF_OGG | PF_HEADER;
            }

        if (encoder->new_metadata || !s->metadata_block.data)
            {
            struct vtag *tag;
            
            if (!(tag = vtag_new(s->vendor_string, &error)))
                {
                fprintf(stderr, "live_oggspeex_encoder_main: error: failed to initialise empty vtag: %s\n", vtag_strerror(error));
                goto bailout;
                }
            
            vtag_append(tag, "encoder", getenv("app_name"));
                        
            if (encoder->use_metadata)
                {
                struct ogg_tag_data t = {};

                fprintf(stderr, "live_oggspeex_encoder_main: info: making metadata\n");
                live_ogg_capture_metadata(encoder, &t);
                if (t.custom && t.custom[0])
                    {
                    vtag_append(tag, "title", t.custom);
                    vtag_append(tag, "trk-author", t.artist);
                    vtag_append(tag, "trk-title", t.title);
                    vtag_append(tag, "trk-album", t.album);
                    }
                else
                    {
                    vtag_append(tag, "author", t.artist);
                    vtag_append(tag, "title", t.title);
                    vtag_append(tag, "album", t.album);
                    }

                live_ogg_free_metadata(&t);
                }
            else
                fprintf(stderr, "live_oggspeex_encoder_main: info: making bare-bones metadata\n");

            if ((error = vtag_serialize(tag, &s->metadata_block, NULL)))
                {
                fprintf(stderr, "live_oggspeex_encoder_main: vtag_serialize failed: %s\n", vtag_strerror(error));
                goto bailout;
                }

            vtag_cleanup(tag);
            encoder->new_metadata = FALSE;
            }
        else
            fprintf(stderr, "live_oggspeex_encoder_main: info: using previous metadata\n");

        op.packet = (unsigned char *)s->metadata_block.data;
        op.bytes = s->metadata_block.length;
        op.b_o_s = 0;
        op.e_o_s = 0;
        op.granulepos = 0;
        op.packetno = 1;
        ogg_stream_packetin(&s->os, &op);
        
        while (ogg_stream_flush(&s->os, &og))
            {
            if (!(live_ogg_write_packet(encoder, &og, s->pflags)))
                {
                fprintf(stderr, "live_ogg_write_packet: failed to write header\n");
                goto bailout;
                }
            }
        
        s->pflags = PF_OGG;
        s->packetno = 2;
        s->frame = 0;
        s->total_samples = 0;
        s->samples_encoded = -s->lookahead;
        s->eos = FALSE;
        encoder->timestamp = 0.0;
        encoder->encoder_state = ES_RUNNING;
        return;
        }
        
    if (encoder->encoder_state == ES_RUNNING)
        {
        struct encoder_ip_data *id;
        char wb[MAX_FRAME_BYTES];
        int ws;
        int (*ogg_paging_function)(ogg_stream_state *, ogg_page *);
 
        if (s->eos == FALSE)
            {
            if (encoder->new_metadata || !encoder->run_request_f || encoder->flush)
                {
                s->eos = TRUE;
                memset(s->inbuf, '\0', s->fsamples * encoder->n_channels * sizeof (float));
                return;
                }
            else
                {
                if((id = encoder_get_input_data(encoder, s->fsamples, s->fsamples, NULL)))
                    {
                    if (encoder->n_channels == 2)
                        {
                        live_oggspeex_encoder_stereomix(id->buffer[0], id->buffer[1], s->inbuf, s->fsamples);
                        speex_encode_stereo(s->inbuf, s->fsamples, &s->bits);
                        }
                    else
                        live_oggspeex_encoder_monomix(id->buffer[0], s->inbuf, s->fsamples);
                    
                    encoder_ip_data_free(id);
                    s->total_samples += s->fsamples;
                    }
                else
                    return;     /* no new audio data available */
                }
            }
        else
            if (encoder->n_channels == 2)
                speex_encode_stereo(s->inbuf, s->fsamples, &s->bits);
         
        speex_encode(s->enc_state, s->inbuf, &s->bits);
        speex_bits_insert_terminator(&s->bits);
        ws = speex_bits_write(&s->bits, wb, MAX_FRAME_BYTES);
        speex_bits_reset(&s->bits);
        s->samples_encoded += s->fsamples;
 
        op.packet = (unsigned char *)wb;
        op.bytes = ws;
        op.b_o_s = 0;
        op.packetno = s->packetno++;
        if (s->samples_encoded >= s->total_samples)
            {
            op.e_o_s = 1;
            op.granulepos = s->total_samples;
            }
        else
            {
            op.e_o_s = 0;
            op.granulepos = s->samples_encoded;
            }
 
        if (op.e_o_s || ++s->frame == 10)
            ogg_paging_function = ogg_stream_flush;
        else
            ogg_paging_function = ogg_stream_pageout;

        ogg_stream_packetin(&s->os, &op);

        while (ogg_paging_function(&s->os, &og))
            {
            s->frame = 0;
            if (ogg_page_eos(&og))
                {
                s->pflags |= PF_FINAL;
                encoder->flush = FALSE;
                encoder->encoder_state = ES_STOPPING;
                }
            if (!live_ogg_write_packet(encoder, &og, s->pflags))
                {
                fprintf(stderr, "live_oggspeex_encoder_main: failed to write packet\n");
                goto bailout;
                }
            }
        return;
        }

    if (encoder->encoder_state == ES_STOPPING)
        {
        speex_bits_destroy(&s->bits);
        speex_encoder_destroy(s->enc_state);
        s->enc_state = NULL;
        ogg_stream_clear(&s->os);
        if (!encoder->run_request_f)
            goto bailout;
        else
            encoder->encoder_state = ES_STARTING;
        return;
        }
        
    fprintf(stderr, "live_oggspeex_encoder_main: unhandled encoder state\n");
    return;
    
    bailout:
    fprintf(stderr, "live_oggspeex_encoder_main: performing cleanup\n");
    encoder->run_request_f = FALSE;
    encoder->encoder_state = ES_STOPPED;
    encoder->run_encoder = NULL;
    encoder->flush = FALSE;
    encoder->new_metadata = FALSE;
    encoder->encoder_private = NULL;
    if (s->enc_state)
        {
        speex_bits_destroy(&s->bits);
        speex_encoder_destroy(s->enc_state);
        }
        
    if (s->inbuf)
        free(s->inbuf);
    vtag_block_cleanup(&s->metadata_block);
    free(s);
    fprintf(stderr, "live_oggspeex_encoder_main: finished cleanup\n");
    return;
    }

int live_oggspeex_encoder_init(struct encoder *encoder, struct encoder_vars *ev)
    {
    struct lose_data * const s = calloc(1, sizeof (struct lose_data));
    char *speex_version;

    if (!s)
        {
        fprintf(stderr, "live_oggspeex_encoder: malloc failure\n");
        return FAILED;
        }

    if (!vtag_block_init(&s->metadata_block))
        {
        fprintf(stderr, "live_oggspeex_encoder: malloc failure\n");
        free(s);
        return FAILED;
        }

    speex_lib_ctl(SPEEX_LIB_GET_VERSION_STRING, (void *)&speex_version);
    snprintf(s->vendor_string, sizeof(s->vendor_string), "Encoded with Speex %s", speex_version); 
    s->vs_len = strlen(s->vendor_string);
    s->quality = atoi(ev->quality);
    s->complexity = atoi(ev->complexity);

    switch (encoder->target_samplerate) {
        case 32000:
            s->mode = &speex_uwb_mode;
            break;
        case 16000:
            s->mode = &speex_wb_mode;
            break;
        case 8000:
            s->mode = &speex_nb_mode;
            break;
        default:
            fprintf(stderr, "unsupported sample rate\n");
            vtag_block_cleanup(&s->metadata_block);
            free(s);
            return FAILED;
        }

    encoder->encoder_private = s;
    encoder->run_encoder = live_oggspeex_encoder_main;
    return SUCCEEDED;
    }

#endif
