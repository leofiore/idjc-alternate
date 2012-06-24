/*
#   avcodec_encoder.c: encode using libavcodec
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
#ifdef HAVE_AVCODEC
#ifdef HAVE_AVUTIL

#include <stdio.h>
#include "main.h"
#include "avcodec_encoder.h"

#define BYTE_ALIGNMENT (8)

static const struct timespec time_delay = { .tv_nsec = 10 };

static void packetize_metadata(struct encoder *e, struct avenc_data * const s)
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

static int write_packet(struct encoder *encoder, struct avenc_data *s, unsigned char *buffer, size_t buffersize, int flags)
    {
    struct encoder_op_packet packet;

    packet.header.bit_rate = encoder->bitrate;
    packet.header.sample_rate = encoder->target_samplerate;
    packet.header.n_channels = encoder->n_channels;
    packet.header.flags = flags;
    packet.header.data_size = buffersize;
    packet.header.serial = encoder->oggserial;
    packet.header.timestamp = encoder->timestamp = s->samples_written / (double)encoder->target_samplerate;
    packet.data = buffer;
    encoder_write_packet_all(encoder, &packet);
    return 1;
    }

static void live_avcodec_encoder_main(struct encoder *encoder)
{
    struct avenc_data * const s = encoder->encoder_private;
    AVCodecContext *c;
    int final;
    struct encoder_ip_data *id;
    
    if (encoder->encoder_state == ES_STARTING) {
        av_init_packet(&s->avpkt);

        if (!(s->c = c = avcodec_alloc_context3(s->codec))) {
            fprintf(stderr, "avcodec_encoder_main: call to avcodec_alloc_context3 failed\n");
            goto bailout;
        }

        // assign codec parameters
        c->bit_rate = encoder->bitrate;
        c->sample_rate = encoder->target_samplerate;
        c->channels = encoder->n_channels;
        c->sample_fmt = AV_SAMPLE_FMT_FLT;
        if (s->pkt_flags & (PF_AAC | PF_AACP2))
            c->profile = FF_PROFILE_AAC_LOW;

        // start the codec preferably with float inputs else signed 16 bit integer inputs
        while (pthread_mutex_trylock(&g.avc_mutex))
            nanosleep(&time_delay, NULL);
        if (avcodec_open2(c, s->codec, NULL) < 0) {
            fprintf(stderr, "live_avcodec_encoder_main: will retry with signed 16 bit: %s\n", s->codec->name);
            c->sample_fmt = AV_SAMPLE_FMT_S16;
            if (avcodec_open2(c, s->codec, NULL) < 0) {
                fprintf(stderr, "live_avcodec_encoder_main: could not open codec: %s\n", s->codec->name);
                pthread_mutex_unlock(&g.avc_mutex);
                goto bailout;
            }
        }
        pthread_mutex_unlock(&g.avc_mutex);

        // allocate the input buffer
        s->inbufsize = c->frame_size * c->channels * av_get_bytes_per_sample(c->sample_fmt);
        if (posix_memalign((void *)&s->inbuf, BYTE_ALIGNMENT, s->inbufsize + FF_INPUT_BUFFER_PADDING_SIZE)) {
            fprintf(stderr, "live_avcodec_encoder_main: malloc failure\n");
            goto bailout;
        }
        memset(s->inbuf + s->inbufsize, '\0', FF_INPUT_BUFFER_PADDING_SIZE); 
        
        // allocate the output buffer
        if (posix_memalign((void *)&s->avpkt.data, BYTE_ALIGNMENT, FF_MIN_BUFFER_SIZE)) {
            fprintf(stderr, "live_avcodec_encoder_main: malloc failure\n");  
            goto bailout;
        }

        s->pkt_flags = (s->pkt_flags | PF_INITIAL) & ~PF_FINAL;
        ++encoder->oggserial;
        encoder->encoder_state = ES_RUNNING;
        return;
        
    bailout:
        encoder->encoder_state = ES_STOPPING;
        encoder->run_request_f = FALSE;
        return;
    }

    if (encoder->encoder_state == ES_RUNNING) {
        final = encoder->flush || !encoder->run_request_f;
        c = s->c;
        size_t out_samples = c->frame_size;
        size_t in_samples = final ? 0 : out_samples;
        int got_packet;

        while ((id = encoder_get_input_data(encoder, in_samples, in_samples, NULL)) || final) {
            // id now has exactly one frame's worth of input data or is NULL

            // prepare an AVFrame to put that data
            if (!s->decoded_frame) {
                if (!(s->decoded_frame = avcodec_alloc_frame())) {
                    fprintf(stderr, "avcodec_encoder_main: failed to allocate frame\n");
                    encoder->encoder_state = ES_STOPPING;
                }
            } else
                avcodec_get_frame_defaults(s->decoded_frame);
            s->decoded_frame->nb_samples = in_samples;
            
            if (id) {
                // audio data is interwoven
                switch (s->c->sample_fmt) {
                    case AV_SAMPLE_FMT_S16:
                        // todo: add dither
                        {
                            float *lp = id->buffer[0], *rp = id->buffer[1];
                            int16_t *op = (int16_t *)s->inbuf;
                            for (int i = 0; i < in_samples; ++i) {
                                *op++ = (int16_t)(*lp++ * 32767.0);
                                if (id->channels == 2)
                                    *op++ = (int16_t)(*rp++ * 32767.0);
                            }
                        }
                        break;
                    case AV_SAMPLE_FMT_FLT:
                        {
                            float *lp = id->buffer[0], *rp = id->buffer[1];
                            float *op = (float *)s->inbuf;
                            for (int i = 0; i < in_samples; ++i) {
                                *op++ = (float)*lp++;
                                if (id->channels == 2)
                                    *op++ = (float)*rp++;
                            }
                        }
                        break;
                    default:
                        fprintf(stderr, "avcodec_encoder_main: unhandled sample format\n");
                        encoder->encoder_state = ES_STOPPING;
                        return;
                    }

                encoder_ip_data_free(id);
            } else {
                memset(s->inbuf, '\0', FF_INPUT_BUFFER_PADDING_SIZE);
                s->pkt_flags |= PF_FINAL;
            }

            if (final && (s->codec->capabilities | CODEC_CAP_DELAY)) {
                av_free(s->decoded_frame);
                s->decoded_frame = NULL;
            } else {
                // audio data is fed into an AVFrame
                if (avcodec_fill_audio_frame(s->decoded_frame, s->c->channels, s->c->sample_fmt,
                                                s->inbuf, s->inbufsize, BYTE_ALIGNMENT) < 0) {
                    fprintf(stderr, "avcodec_encoder_main: encoding failed\n");
                    encoder->encoder_state = ES_STOPPING;
                    return;
                }
            }
            
            if (!final || s->codec->capabilities & (CODEC_CAP_DELAY | CODEC_CAP_VARIABLE_FRAME_SIZE | CODEC_CAP_SMALL_LAST_FRAME)) {
                // decode as much data is this encoder wants to
                s->avpkt.size = FF_MIN_BUFFER_SIZE;
                if (avcodec_encode_audio2(c, &s->avpkt, s->decoded_frame, &got_packet) < 0) {
                    fprintf(stderr, "avcodec_encoder_main: encoding failed\n");
                    encoder->encoder_state = ES_STOPPING;
                    return;
                }
                
                if (got_packet) {
                    s->samples_written += out_samples;
                    write_packet(encoder, s, s->avpkt.data, s->avpkt.size, s->pkt_flags);
                    av_free_packet(&s->avpkt);
                    s->pkt_flags &= ~PF_INITIAL;
                }
            } else {
                // write out an empty last packet rather than flush the codec with digital silence
                write_packet(encoder, s, (unsigned char *)"", 0, s->pkt_flags);
            }

            if (encoder->new_metadata && encoder->use_metadata && !(s->pkt_flags & (PF_INITIAL | PF_FINAL))) {
                packetize_metadata(encoder, s);
                if (s->metadata)
                    write_packet(encoder, s, (unsigned char *)s->metadata, strlen(s->metadata) + 1, PF_METADATA);
            }
            
            // perform flush action cleanup
            if (final) {
                encoder->encoder_state = ES_STOPPING;
                return;
            }
		}     
        return;
    }

    if (encoder->encoder_state == ES_STOPPING) {
        if (s->c) {
            if (avcodec_is_open(s->c))
                avcodec_close(s->c);
            av_free(s->c);
            s->c = NULL;
        }
        
        if (s->decoded_frame) {
            av_free(s->decoded_frame);
            s->decoded_frame = NULL;
        }
        
        if (s->avpkt.data) {
            free(s->avpkt.data);
            s->avpkt.data = NULL;
        }
            
        if (s->inbuf) {
            free(s->inbuf);
            s->inbuf = NULL;
        }

        encoder->flush = FALSE;
        s->samples_written = 0;
            
        if (encoder->run_request_f)
            encoder->encoder_state = ES_STARTING;
        else {
            if (s->metadata)
                free(s->metadata);
            encoder->encoder_state = ES_STOPPED;
            encoder->run_encoder = NULL;
            encoder->encoder_private = NULL;
            free(s);
        }
    }
}

static const char *aac = "libfaac";
static const char *aacpv2 = "libaacplus";

int live_avcodec_encoder_init(struct encoder *encoder, struct encoder_vars *ev)
{
    struct avenc_data * const s = calloc(1, sizeof (struct avenc_data));
    const char *codecname;

    if (!s)
        {
        fprintf(stderr, "avcodec_encoder: malloc failure\n");
        return FAILED;
        }

    if (!strcmp(ev->codec, "aac")) {
        codecname = aac;
        s->pkt_flags = PF_AAC;
        }
    else {
        if (!strcmp(ev->codec, "aacpv2")) {
            codecname = aacpv2;
            s->pkt_flags = PF_AACP2;
        } else {
            fprintf(stderr, "avcodec_encoder: unsupported codec\n");
            goto clean1;
        }
    }

    if (!(s->codec = avcodec_find_encoder_by_name(codecname))) {
        fprintf(stderr, "live_avcodec_encoder_init: codec not found: %s\n", codecname);
        goto clean1;
    }

    encoder->bitrate = atoi(ev->bitrate);
    encoder->target_samplerate = atoi(ev->samplerate);
    encoder->n_channels = strcmp(ev->mode, "mono") ? 2 : 1;
    encoder->encoder_private = s;
    encoder->run_encoder = live_avcodec_encoder_main;
    return SUCCEEDED;

clean1:
    free(s);
    return FAILED;
}

int live_avcodec_encoder_aac_functionality()
{
    //int aac_f = avcodec_find_encoder_by_name(aac) ? 1 : 0;
    //int aacpv2_f = avcodec_find_encoder_by_name(aacpv2) ? 1 : 0;
    int aac_f = 1;
    int aacpv2_f = 1;
    
    fprintf(stdout, "idjcsc: aac_functionality=%d:%d\n", aac_f, aacpv2_f);
    fflush(stdout);
    if (ferror(stdout))
        return FAILED;
    
    return SUCCEEDED;
}

#endif /* HAVE_AVUTIL */
#endif /* HAVE_AVCODEC */
