/*
#   sourceclient.h: the streaming module of idjc
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

#ifndef SOURCECLIENT_H
#define SOURCECLIENT_H

enum { FAILED, SUCCEEDED }; /* use for return values to commandmap(pped) functions */
enum { FALSE, TRUE };

struct encoder;
struct streamer;
struct recorder;
struct audio_feed;

struct threads_info
    {
    int n_encoders;
    int n_streamers;
    int n_recorders;
    struct encoder **encoder;
    struct streamer **streamer;
    struct recorder **recorder;
    struct audio_feed *audio_feed;
    };

struct universal_vars
    {
    char *command;
    char *dev_type;
    char *tab_id;
    int tab;
    };

struct commandmap
    {
    char *key;
    int (*function)(struct threads_info *ti, struct universal_vars *uv, void *other_parameter);
    void *other_parameter;
    };
    
#include "encoder.h"
#include "streamer.h"
#include "recorder.h"
#include "audio_feed.h"

void sourceclient_init();
int sourceclient_main();
void comms_send(char *message);

#endif
