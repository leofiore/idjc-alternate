/*
#   streamer.c: the streaming part of the streaming module of idjc
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

#define _POSIX_C_SOURCE 200112L
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <pthread.h>
#include <shoutidjc/shout.h>
#include "sourceclient.h"
#include "sig.h"

/* other versions of libshout define SHOUT_FORMAT_VORBIS instead */
#ifndef SHOUT_FORMAT_OGG
#define SHOUT_FORMAT_OGG SHOUT_FORMAT_VORBIS
#endif  /*SHOUT_FORMAT_OGG*/

/* the number of seconds of audio to stockpile before packet dumping takes place */
static const int shout_buffer_seconds = 9;

static void *streamer_main(void *args)
    {
    struct streamer *self = args;
    struct timespec ms10 = { 0, 10000000 };
    struct encoder_op_packet *packet;
    char buffer[10];
    size_t data_size;
    
    char *s_conv(unsigned long value)
        {
        snprintf(buffer, 10, "%lu", value);
        return buffer;
        }
        
    sig_mask_thread();
    while (!self->thread_terminate_f)
        {
        nanosleep(&ms10, NULL);

        switch (self->stream_mode)
            {
            case SM_DISCONNECTED:
                continue;
            case SM_CONNECTING:
                switch(self->shout_status)
                    {
                    case SHOUTERR_BUSY:
                        self->shout_status = shout_get_connected(self->shout);

                        if (self->disconnect_request)
                            self->stream_mode = SM_DISCONNECTING;
                        break;
                    case SHOUTERR_CONNECTED:
                        /* lock the encoder, grab the serial number and issue encoder flush */
                        /* this makes the encoder contemporaneous with the stream */
                        self->initial_serial = encoder_client_set_flush(self->encoder_op) + 1;
                        fprintf(stderr, "streamer_main: connected to server - awaiting serial %d\n", self->initial_serial);
                        self->brand_new_connection = TRUE;
                        self->stream_mode = SM_CONNECTED;
                        break;
                    default:
                        fprintf(stderr, "streamer_main: connection failed, shout_get_error reports %ld %s\n", self->shout_status, shout_get_error(self->shout));
                        self->stream_mode = SM_DISCONNECTING;
                    }
                break;
            case SM_CONNECTED:
                /* check the connection is still on */
                if ((self->shout_status = shout_get_connected(self->shout)) != SHOUTERR_CONNECTED)
                    {
                    fprintf(stderr, "streamer_main: shout_get_error reports %ld %s\n", self->shout_status, shout_get_error(self->shout));
                    self->stream_mode = SM_DISCONNECTING;
                    }
                if (self->disconnect_request && (!self->disconnect_pending))
                    {
                    self->disconnect_pending = TRUE;
                    fprintf(stderr, "streamer_main: disconnect_pending is set\n");
                    self->final_serial = encoder_client_set_flush(self->encoder_op);
                    fprintf(stderr, "streamer_main: issued flush to mixer, disconnecting from server when final packet of serial=%d arrives\n", self->final_serial);
                    }
                if ((packet = encoder_client_get_packet(self->encoder_op)))
                    {
                    if (packet->header.serial >= self->initial_serial)
                        {
                        if (packet->header.flags & PF_INITIAL)
                            {
                            int br = packet->header.bit_rate;
                            
                            /* determine how much audio to hold in the send buffer */
                            self->max_shout_queue = (shout_buffer_seconds * ((br > 1000) ? br / 1000 : br)) << 7;
                            }
                        if (packet->header.flags & (PF_OGG | PF_MP3 | PF_MP2 | PF_AAC | PF_AACP2))
                            {
                            if ((packet->header.flags & (PF_HEADER | PF_FINAL)) || shout_queuelen(self->shout) < self->max_shout_queue)
                                data_size = packet->header.data_size;
                            else
                                {
                                data_size = 0;
                                fprintf(stderr, "streamer_main: **** packet dumped due to buffer being full ****\n");
                                }
#if 1                           
                            switch(shout_send(self->shout, packet->data, data_size))
                                {
                                case SHOUTERR_SUCCESS:
                                case SHOUTERR_BUSY:
                                    break;
                                default:
                                    fprintf(stderr, "streamer_main: failed writing to stream, shout_get_error reports: %s\n", shout_get_error(self->shout));
                                    self->stream_mode = SM_DISCONNECTING;
                                }
#else
                            if (shout_send_raw(self->shout, packet->data, data_size) != data_size)
                                {
                                fprintf(stderr, "streamer_main: failed writing to stream, shout_get_error reports: %s\n", shout_get_error(self->shout));
                                self->stream_mode = SM_DISCONNECTING;
                                }
#endif
                            }
                        if (packet->header.flags & PF_FINAL)
                            fprintf(stderr, "streamer_main: final packet with serial %d\n", packet->header.serial);
                        if (self->disconnect_pending && (packet->header.serial > self->final_serial || ((packet->header.flags & PF_FINAL) && self->final_serial == packet->header.serial)))
                            {
                            fprintf(stderr, "streamer_main: last packet wrote, disconnecting\n");
                            self->stream_mode = SM_DISCONNECTING;
                            }
                        }
                    if (packet->header.flags & PF_METADATA)  /* tell server about new metadata */
                        {
                        *strpbrk(packet->data, "\n") = '\0';
                        fprintf(stderr, "streamer_main: packet is metadata: %s\n", (char *)packet->data);
                        shout_metadata_add(self->shout_meta, "song", packet->data);
                        switch (shout_set_metadata(self->shout, self->shout_meta))
                            {
                            case SHOUTERR_SUCCESS:
                            case SHOUTERR_BUSY:
                                break;
                            default:
                                fprintf(stderr, "streamer_main: failed writing metadata to stream, shout_get_error reports: %s\n", shout_get_error(self->shout));
                                self->stream_mode = SM_DISCONNECTING;
                            }
                        }
                    encoder_client_free_packet(packet);
                    }
                break;
            case SM_DISCONNECTING:
                fprintf(stderr, "streamer_main: disconencting from server\n");
                shout_close(self->shout);
                shout_free(self->shout);
                shout_metadata_free(self->shout_meta);
                encoder_unregister_client(self->encoder_op);
                self->shout = NULL;
                self->shout_meta = NULL;
                self->encoder_op = NULL;
                self->max_shout_queue = 0;
                self->disconnect_request = FALSE;
                self->disconnect_pending = FALSE;
                self->stream_mode = SM_DISCONNECTED;
                fprintf(stderr, "streamer_main: disconnection complete\n");
                break;
            }
        }
    return NULL;
    }

int streamer_make_report(struct streamer *self)
    {
    int buffer_fill_pc = 0;
    int new_connection = self->brand_new_connection; /* for thread safety */
    int max_shout_queue = self->max_shout_queue;

    if (self->stream_mode == SM_CONNECTED && max_shout_queue)
        buffer_fill_pc = (int)(shout_queuelen(self->shout) * 100 / max_shout_queue);
    fprintf(stdout, "idjcsc: streamer%dreport=%d:%d:%d\n", self->numeric_id, (int)self->stream_mode, buffer_fill_pc, new_connection);
    if (new_connection)
        self->brand_new_connection = FALSE;
    fflush(stdout);
    return SUCCEEDED;
    }

int streamer_connect(struct threads_info *ti, struct universal_vars *uv, void *other)
    {
    struct streamer_vars *sv = other;
    struct streamer *self = ti->streamer[uv->tab];
    int protocol, data_format = -1;
    char channels[2];
    char bitrate[4];
    char samplerate[6];

    void sce(char *parameter)    /* stream connect error */
        {
        fprintf(stderr, "streamer_connect: failed to set parameter %s\n", parameter);
        }

    if (!(self->encoder_op = encoder_register_client(ti, atoi(sv->stream_source))))
        {
        fprintf(stderr, "streamer_start: failed to register with encoder\n");
        return FAILED;
        }
    if (!self->encoder_op->encoder->run_request_f)
        {
        fprintf(stderr, "streamer_start: encoder is not running\n");
        encoder_unregister_client(self->encoder_op);
        return FAILED;
        }
    else
        {
        const struct encoder_data_format *df = &self->encoder_op->encoder->data_format;            
        int failed = FALSE;

        switch (df->family) {
            case ENCODER_FAMILY_OGG:
                data_format = SHOUT_FORMAT_OGG;
                break;
            case ENCODER_FAMILY_MPEG:
                switch (df->codec) {
                    case ENCODER_CODEC_MP3:
                    case ENCODER_CODEC_MP2:
                        data_format = SHOUT_FORMAT_MP3;
                        break;
                    case ENCODER_CODEC_AAC:
                        data_format = SHOUT_FORMAT_AAC;
                        break;
                    case ENCODER_CODEC_AACPLUSV2:
                        data_format = SHOUT_FORMAT_AACPLUS;
                        break;
                    case ENCODER_CODEC_UNHANDLED:
                    default:
                        failed = TRUE;
                    }
                    break;
            case ENCODER_FAMILY_UNHANDLED:
                failed = TRUE;
            }
            
        if (failed)
            {
            fprintf(stderr, "streamer_start: unhandled encoder data format\n");
            encoder_unregister_client(self->encoder_op);
            return FAILED;
            }
        }
        
    if (!strcmp(sv->server_type, "Shoutcast"))
        protocol = SHOUT_PROTOCOL_ICY;
    else if (!strcmp(sv->server_type, "Icecast 2"))
        protocol = SHOUT_PROTOCOL_HTTP;
    else if (!strcmp(sv->server_type, "Icecast"))
        protocol = SHOUT_PROTOCOL_XAUDIOCAST;
    else
        {
        fprintf(stderr, "streamer_connect: server_type unhandled value %s\n", sv->server_type);
        encoder_unregister_client(self->encoder_op);
        return FAILED;
        }
    if (!(self->shout_meta = shout_metadata_new()))
        {
        fprintf(stderr, "streamer_connect: failed to allocate a shout metadata object\n");
        encoder_unregister_client(self->encoder_op);
        }
    if (!(self->shout = shout_new()))
        {
        fprintf(stderr, "streamer_connect: call to shout_new failed\n");
        encoder_unregister_client(self->encoder_op);
        return FAILED;
        }
    if (shout_set_protocol(self->shout, protocol) != SHOUTERR_SUCCESS)
        {
        sce("protocol");
        goto error;
        }
    if (shout_set_format(self->shout, data_format) != SHOUTERR_SUCCESS)
        {
        sce("format");
        goto error;
        }
    if (shout_set_host(self->shout, sv->host) != SHOUTERR_SUCCESS)
        {
        sce("host");
        goto error;
        }
    if (shout_set_port(self->shout, atoi(sv->port)) != SHOUTERR_SUCCESS)
        {
        sce("port");
        goto error;
        }
    if (shout_set_mount(self->shout, sv->mount) != SHOUTERR_SUCCESS)
        {
        sce("mount");
        goto error;
        }
    if (shout_set_user(self->shout, sv->login) != SHOUTERR_SUCCESS)
        {
        sce("login");
        goto error;
        }
    if (shout_set_password(self->shout, sv->password) != SHOUTERR_SUCCESS)
        {
        sce("password");
        goto error;
        }
    if (sv->useragent[0])
        {
        if (shout_set_agent(self->shout, sv->useragent) != SHOUTERR_SUCCESS)
            {
            sce("useragent");
            goto error;
            }
        else
            fprintf(stderr, "user agent is set\n");
        }
    if (shout_set_name(self->shout, sv->dj_name) != SHOUTERR_SUCCESS)
        {
        sce("stream/dj name");
        goto error;
        }
    if (shout_set_url(self->shout, sv->listen_url) != SHOUTERR_SUCCESS)
        {
        sce("url");
        goto error;
        }
    if (shout_set_description(self->shout, sv->description) != SHOUTERR_SUCCESS)
        {
        sce("description");
        goto error;
        }
    if (shout_set_genre(self->shout, sv->genre) != SHOUTERR_SUCCESS)
        {
        sce("genre");
        goto error;
        }

    if (shout_set_irc(self->shout, sv->irc) != SHOUTERR_SUCCESS)
        {
        sce("irc");
        goto error;
        }
    if (shout_set_aim(self->shout, sv->aim) != SHOUTERR_SUCCESS)
        {
        sce("aim");
        goto error;
        }
    if (shout_set_icq(self->shout, sv->icq) != SHOUTERR_SUCCESS)
        {
        sce("icq");
        goto error;
        }

    if (shout_set_public(self->shout, !strcmp(sv->make_public, "True")) != SHOUTERR_SUCCESS)
        {
        sce("make public");
        goto error;
        }
        
    snprintf(channels,   sizeof channels  , "%d",  self->encoder_op->encoder->n_channels);
    {
        int br = self->encoder_op->encoder->bitrate;
        snprintf(bitrate, sizeof bitrate   , "%d",  ((br < 1000) ? br : br/1000));
    }
    snprintf(samplerate, sizeof samplerate, "%ld", self->encoder_op->encoder->target_samplerate);
        
    if (shout_set_audio_info(self->shout, SHOUT_AI_BITRATE, bitrate) != SHOUTERR_SUCCESS)
        {
        sce("set_audio_info bitrate");
        goto error;
        }
    if (shout_set_audio_info(self->shout, SHOUT_AI_SAMPLERATE, samplerate) != SHOUTERR_SUCCESS)
        {
        sce("set_audio_info samplerate");
        goto error;
        }
    if (shout_set_audio_info(self->shout, SHOUT_AI_CHANNELS, channels) != SHOUTERR_SUCCESS)
        {
        sce("set_audio_info channels");
        goto error;
        }
        
    if (shout_set_nonblocking(self->shout, 1) != SHOUTERR_SUCCESS)
        {
        sce("non-blocking");
        goto error;
        }
    switch(self->shout_status = shout_open(self->shout))
        {
        case SHOUTERR_SUCCESS:
            self->shout_status = SHOUTERR_CONNECTED;
        case SHOUTERR_BUSY:
        case SHOUTERR_CONNECTED:
            self->stream_mode = SM_CONNECTING;
            fprintf(stderr, "streamer_connect: established connection to the server\n");
            return SUCCEEDED;
        }
    error:
    fprintf(stderr, "streamer_connect: shout_get_error reports: %s\n", shout_get_error(self->shout));
    shout_free(self->shout);
    shout_metadata_free(self->shout_meta);
    encoder_unregister_client(self->encoder_op);
    return FAILED;
    }

int streamer_disconnect(struct threads_info *ti, struct universal_vars *uv, void *other)
    {
    struct streamer *self = ti->streamer[uv->tab];
    struct timespec ms10 = { 0, 10000000 };

    if (!self->shout)
        {
        fprintf(stderr, "streamer_disconnect: function called while not streaming\n");
        return FAILED;
        }
    self->disconnect_request = TRUE;
    fprintf(stderr, "streamer_disconnect: disconnection_request is set\n");
    while(self->stream_mode != SM_DISCONNECTED)
        nanosleep(&ms10, NULL);
    fprintf(stderr, "streamer_disconnect: disconnection complete\n");
    return SUCCEEDED;
    }

void shout_initialiser()
    {
    shout_init();
    }

struct streamer *streamer_init(struct threads_info *ti, int numeric_id)
    {
    struct streamer *self;
    static pthread_once_t once_control = PTHREAD_ONCE_INIT;
    
    pthread_once(&once_control, shout_initialiser);
    if (!(self = calloc(1, sizeof (struct streamer))))
        {
        fprintf(stderr, "streamer_init: malloc failure\n");
        exit(-5);
        }
    self->threads_info = ti;
    self->numeric_id = numeric_id;
    pthread_create(&self->thread_h, NULL, streamer_main, self);
    return self;
    }

void streamer_destroy(struct streamer *self)
    {
    static pthread_once_t once_control = PTHREAD_ONCE_INIT;
    void *thread_ret;

    pthread_once(&once_control, shout_shutdown);
    self->thread_terminate_f = TRUE;
    pthread_join(self->thread_h, &thread_ret);
    free(self);
    }
