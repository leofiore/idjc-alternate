/*
#   ogg_flac_dec.h: flac decoder for oggdec.c
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

#ifdef HAVE_OGGFLAC

#include <FLAC/all.h>
#include "xlplayer.h"

struct oggflacdec_vars
    {
    FLAC__StreamDecoder *dec;
    int resample;
    int suppress_audio_output;
    float *flbuf;
    };

int ogg_flacdec_init(struct xlplayer *xlplayer);

#endif /* HAVE_OGGFLAC */
