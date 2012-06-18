/*
#   avcodec_encoder.h: encode using libavcodec
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

#ifdef HAVE_AVCODEC

#ifdef FFMPEG_AVCODEC
#include <ffmpeg/avcodec.h>
#else
#include <libavcodec/avcodec.h>
#endif

#include "sourceclient.h"

struct avenc_data {
    AVCodec *codec;
    AVCodecContext *c;
    AVPacket avpkt;
	AVFrame *decoded_frame;
    size_t inbufsize;
    uint8_t *inbuf;
    unsigned long samples_written;
    enum packet_flags pkt_flags;
    char *metadata;
};

int live_avcodec_encoder_init(struct encoder *encoder, struct encoder_vars *ev);
int live_avcodec_encoder_aac_functionality();

#endif /* HAVE_AVCODEC */
