/*
#   live_oggspeex_encoder.h: encode speex from a live source into an ogg container
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

#include "sourceclient.h"
#include <speex/speex.h>
#include <speex/speex_header.h>
#include <speex/speex_stereo.h>
#include <ogg/ogg.h>
#include "live_ogg_encoder.h"

enum speex_mode { SM_UWB, SM_WB, SM_NB };

struct lose_data
    {
    struct ogg_tag_data tag_data;
    void *enc_state;
    SpeexBits bits;
    int fsamples;              /* number of samples in a frame */
    float *inbuf;
    ogg_stream_state os;
    int pflags;
    int packetno;
    int frame;
    int frames_encoded;
    int total_samples;
    int samples_encoded;
    int lookahead;
    int eos;
    char vendor_string[64];
    size_t vs_len;
    struct SpeexMode const *mode;
    int quality;
    int complexity;
    char *metadata_vc;
    size_t metadata_vclen;
    enum packet_flags flags;
    };

int live_oggspeex_encoder_init(struct encoder *encoder, struct encoder_vars *ev);

#endif
