/*
#   mp3dec.h: decodes mp3 file format for xlplayer
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

#include <stdio.h>
#include <mpg123.h>
#include "xlplayer.h"
#include "mp3tagread.h"

struct mp3decode_vars
   {
   FILE *fp;
   mpg123_handle *mh;
   struct mp3taginfo taginfo;
   struct chapter *current_chapter;
   int resample;
   };

int mp3decode_reg(struct xlplayer *xlplayer);
