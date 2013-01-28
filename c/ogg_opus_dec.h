/*
#   ogg_opus_dec.h: opus decoder for oggdec.c
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

#ifdef HAVE_OPUS

#include <opus/opus_multistream.h>
#include "xlplayer.h"

struct opusdec_vars
    {
    int resample;    
    uint16_t preskip;
    float opgain;
    int channel_count;
    int channelmap_family;
    int stream_count;
    int stream_count_2c;
    unsigned char channel_map[8];
    OpusMSDecoder *odms;
    };

int ogg_opusdec_init(struct xlplayer *xlplayer);

#endif /* HAVE_OPUS */
