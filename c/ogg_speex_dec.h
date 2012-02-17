/*
#   ogg_speex_dec.h: speex decoder for oggdec.c
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

#include <speex/speex.h>
#include <speex/speex_header.h>
#include <speex/speex_stereo.h>
#include <speex/speex_callbacks.h>

#include "xlplayer.h"

struct speexdec_vars
    {
    SpeexHeader *header;
    int stereo;
    int channels;
    void *dec_state;
    SpeexBits bits;
    float *frame;
    int frame_size;
    int nframes;
    SpeexStereoState stereo_state;
    int page_granule;
    int last_granule;
    int page_nb_packets;
    int skip_samples;
    int packet_no;
    int lookahead;
    int seek_dump_samples;
    };

int ogg_speexdec_init(struct xlplayer *xlplayer);

#endif /* HAVE_SPEEX */
