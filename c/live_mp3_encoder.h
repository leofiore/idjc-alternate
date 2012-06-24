/*
#   live_mp3_encoder.h: encode mp3 files from a live source
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

#ifdef HAVE_LAME_LAME_H
#include <lame/lame.h>
#else 
#include "lame.h"
#endif /* HAVE_LAME_LAME_H */

#include "sourceclient.h"

struct lm3e_data
    {
    lame_global_flags *gfp;
    int lame_mode;
    int lame_channels;
    int lame_quality;
    char *metadata;
    int lame_samples;
    unsigned char *mp3buf;
    size_t mp3bufsize;
    enum packet_flags packetflags;
    };

int live_mp3_encoder_init(struct encoder *encoder, struct encoder_vars *ev);

