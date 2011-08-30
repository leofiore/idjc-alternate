/*
#   avcodecdecode.h: decodes wma file format for xlplayer
#   Copyright (C) 2007, 2011 Stephen Fairchild (s-fairchild@users.sourceforge.net)
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
#ifdef HAVE_AVFORMAT
#ifdef HAVE_AVUTIL

#ifdef FFMPEG_AVCODEC
#include <ffmpeg/avcodec.h>
#include <ffmpeg/avformat.h>
#else
#include <libavcodec/avcodec.h>
#include <libavformat/avformat.h>
#include <libavutil/dict.h>
#endif

#include "xlplayer.h"

struct avcodecdecode_vars
   {
   AVCodec *codec;
   AVPacket pkt;
   AVCodecContext *c;
   AVFormatContext *ic;
   int resample;
   unsigned int stream;
   uint8_t *outbuf;
   float *floatsamples;
   float drop;
   };

int avcodecdecode_reg(struct xlplayer *xlplayer);
void avformatinfo(char *pathname);

#endif /* HAVE_AVUTIL */
#endif /* HAVE_AVFORMAT */
#endif /* HAVE_AVCODEC */
