/*
#   live_oggflac_encoder.h: encode oggflac from a live source
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

#include "sourceclient.h"
#include <FLAC/all.h>
#include "live_ogg_encoder.h"

struct lofe_data
    {
    struct ogg_tag_data tag_data;
    FLAC__StreamEncoder *enc;
    int bits_per_sample;
    FLAC__StreamMetadata *metadata[1];
    FLAC__byte *pab;
    size_t pab_rqd;
    size_t pab_size;
    size_t pab_head_size;
    int n_writes;
    unsigned samples;
    enum packet_flags flags;
    unsigned int seedp;
    int uclip;
    int lclip;
    };

int live_oggflac_encoder_init(struct encoder *encoder, struct encoder_vars *ev);

#endif /* HAVE_OGGFLAC */
