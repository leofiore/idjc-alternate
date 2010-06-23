/*
#   mp3dec.h: decodes mp3 file format for xlplayer
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

#include <jack/ringbuffer.h>
#include "xlplayer.h"
#include "mp3tagread.h"

struct mp3decode_vars
   {
   FILE *fp;
   struct mad_synth synth;
   struct mad_stream stream;
   struct mad_frame frame;
   unsigned char *read_buffer;
   size_t bytes_in_buffer;
   float playduration;
   int resample;
   int nchannels;
   int samplerate;
   struct mp3taginfo taginfo;
   struct chapter *current_chapter;
   jack_ringbuffer_t *lrb;
   jack_ringbuffer_t *rrb;
   int initial_data;
   int errors;
   };

int mp3decode_reg(struct xlplayer *xlplayer);
