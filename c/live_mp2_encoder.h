/*
#   live_mp2_encoder.h: encode mp2 files from a live source
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

#ifdef HAVE_TWOLAME

#include "twolame.h"
#include "sourceclient.h"

struct lm2e_data
    {
    twolame_options *gfp;
    TWOLAME_MPEG_version mpeg_version;
    TWOLAME_MPEG_mode mpeg_mode;
    char *metadata;
    int twolame_samples;
    unsigned char *mp2buf;
    size_t mp2bufsize;
    enum packet_flags packetflags;
    };

int live_mp2_encoder_init(struct encoder *encoder, struct encoder_vars *ev);

#endif /* HAVE_TWOLAME */
