/*
#   live_ogg_encoder.h: encode ogg files from a live source
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

#ifndef HAVE_OGGENC
#define HAVE_OGGENC

#include <ogg/ogg.h>
#include "sourceclient.h"

struct ogg_tag_data
    {
    char *custom;
    char *artist;
    char *title;
    char *album;
    };

int live_ogg_encoder_init(struct encoder *encoder, struct encoder_vars *ev);
int live_ogg_write_packet(struct encoder *encoder, ogg_page *op, int flags);
void live_ogg_capture_metadata(struct encoder *e, struct ogg_tag_data *td);
void live_ogg_free_metadata(struct ogg_tag_data *td);

#endif
