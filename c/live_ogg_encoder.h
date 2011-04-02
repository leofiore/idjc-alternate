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

#include <vorbis/vorbisenc.h>
#include <jack/jack.h>
#include "sourceclient.h"

struct ogg_tag_data
   {
   char *custom;
   char *artist;
   char *title;
   char *album;
   };

struct loe_data
   {
   struct ogg_tag_data tag_data;
   long max_bitrate;            /* ogg upper and lower bitrate settings */
   long min_bitrate;
   vorbis_info      vi;
   vorbis_block     vb;
   vorbis_dsp_state vd;
   vorbis_comment   vc;
   ogg_stream_state os;
   ogg_page         og;
   ogg_packet       op;
   int pagesamples;
   int (*owf)(ogg_stream_state *os, ogg_page *og);
   };

int live_ogg_encoder_init(struct encoder *encoder, struct encoder_vars *ev);
int live_ogg_test_values(struct threads_info *ti, struct universal_vars *uv, void *other);
int live_ogg_write_packet(struct encoder *encoder, ogg_page *op, int flags);
void live_ogg_capture_metadata(struct encoder *e, struct ogg_tag_data *td);
void live_ogg_free_metadata(struct ogg_tag_data *td);
