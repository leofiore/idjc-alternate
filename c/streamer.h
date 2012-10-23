/*
#   streamer.h: the streaming module of idjc
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

#ifndef STREAMER_H
#define STREAMER_H

#include "sourceclient.h"

struct streamer_vars
    {
    char *stream_source;
    char *server_type;
    char *host;
    char *port;
    char *mount;
    char *login;
    char *password;
    char *useragent;
    char *dj_name;
    char *listen_url;
    char *description;
    char *genre;
    char *irc;
    char *aim;
    char *icq;
    char *make_public;
    };

enum stream_mode { SM_DISCONNECTED, SM_CONNECTING, SM_CONNECTED, SM_DISCONNECTING };

struct shout; 
struct _util_dict;

struct streamer
    {
    struct threads_info *threads_info;
    int numeric_id;
    pthread_t thread_h;
    int thread_terminate_f;
    int disconnect_request;
    int disconnect_pending;
    struct encoder_op *encoder_op;
    struct shout *shout;
    struct _util_dict *shout_meta;
    enum stream_mode stream_mode;
    int brand_new_connection;    /* used for triggering actions in the gui */
    long shout_status;
    int initial_serial;  /* the enocoder serial number we commence streaming from */
    int final_serial;    /* the serial number to cease streaming at the end of */
    ssize_t max_shout_queue;     /* how much audio data we are willing to stockpile */
    pthread_mutex_t mode_mutex;
    pthread_cond_t mode_cv;
    };

struct streamer *streamer_init(struct threads_info *ti, int numeric_id);
void streamer_destroy(struct streamer *self);
int streamer_connect(struct threads_info *ti, struct universal_vars *uv, void *other);
int streamer_disconnect(struct threads_info *ti, struct universal_vars *uv, void *other);
int streamer_make_report(struct streamer *self);

#endif
