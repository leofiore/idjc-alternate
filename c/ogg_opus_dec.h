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

#include <opus/opus.h>
#include <opus/opus_multistream.h>
#include "xlplayer.h"

struct opusdec_vars
    {
    int resample;       /* do we need to resample? */
    int do_down;        /* do we need to downmix? */
    float *pcm;         /* decoder reads to here */
    float *down;        /* downmix buffer -- possible alias of pcm */
    uint16_t preskip;   /* dump this many samples from stream start */
    float opgain;       /* apply this much gain to all samples */
    int channel_count;  /* number of stream channels */
    int channelmap_family;
    int stream_count;           /* total stream count */
    int stream_count_2c;        /* qty stereo streams */
    unsigned char channel_map[8];
    OpusMSDecoder *odms;        /* decoder handle */
    int64_t gf_gp;              /* granule position values */
    int64_t f_gp;
    int64_t gp;
    int64_t dec_samples;
    };

int ogg_opusdec_init(struct xlplayer *xlplayer);

#endif /* HAVE_OPUS */
