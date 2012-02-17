/*
#   audiofeed.h: jack connectivity for the streaming module of idjc
#   Copyright (C) 2007-2010 Stephen Fairchild (s-fairchild@users.sourceforge.net)
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

#ifndef AUDIO_FEED_H
#define AUDIO_FEED_H

#include <jack/jack.h>
#include "sourceclient.h"

struct audio_feed
    {
    struct threads_info *threads_info;
    jack_nframes_t sample_rate;
    };

struct audio_feed *audio_feed_init(struct threads_info *ti);
void audio_feed_deactivate(struct audio_feed *self);
void audio_feed_destroy(struct audio_feed *self);
int audio_feed_jack_samplerate_request(struct threads_info *ti, struct universal_vars *uv, void *param);
int audio_feed_process_audio(jack_nframes_t n_frames, void *arg);

#endif
