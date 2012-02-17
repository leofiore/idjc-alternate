/*
#   flacdecode.h: decodes flac file format for xlplayer
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
#ifdef HAVE_FLAC

#include "xlplayer.h"

struct flacdecode_vars
    {
    FLAC__StreamDecoder *decoder;
    FLAC__StreamMetadata metainfo;
    int decoderstate;
    int resample_f;
    int suppress_audio_output;
    FLAC__uint64 totalsamples;
    float *flbuf;
    };

int flacdecode_reg(struct xlplayer *xlplayer);

void make_flac_audio_to_float(struct xlplayer *self, float *flbuf, const FLAC__int32 * const inputbuffer[], unsigned int numsamples, unsigned int bits_per_sample, unsigned int numchannels);

#endif
