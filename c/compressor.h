/*
#   compressor.h: Audio dynamic range compression code from IDJC.
#   Copyright (C) 2005-2007 Stephen Fairchild (s-fairchild@users.sourceforge.net)
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

#include <jack/jack.h>

typedef jack_default_audio_sample_t compaudio_t;

struct compressor
    {
    compaudio_t gain_db;
    compaudio_t k1;
    compaudio_t k2;
    compaudio_t ratio;
    compaudio_t attack;
    compaudio_t release;
    compaudio_t opgain;
    compaudio_t ducking;
    compaudio_t curve;
    int ducking_hold;
    int ducking_hold_count;
    compaudio_t ducking_db;
    compaudio_t de_ess_db;
    };

struct normalizer
    {
    int active;
    compaudio_t level;
    compaudio_t ceiling;
    compaudio_t rise;
    compaudio_t fall;
    compaudio_t maxlevel;
    };

compaudio_t compressor(struct compressor *self, compaudio_t signal, int skip_rms);
compaudio_t limiter(struct compressor *self, compaudio_t left, compaudio_t right);
compaudio_t normalizer(struct normalizer *self, compaudio_t left, compaudio_t right);
