/*
#   compressor.c: Audio dynamic range compression code from IDJC.
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

#include "gnusource.h"
#include <stdio.h>
#include <math.h>
#include <assert.h>
#include "dbconvert.h"
#include "compressor.h"
#include "bsdcompat.h"

/* limiter: a basic hard knee compressor - called limiter because that is the mode */
/* in which IDJC uses it */
compaudio_t limiter(struct compressor *self, compaudio_t left, compaudio_t right) 
    {
    compaudio_t gots, gain_target_db, diff;

    gots = level2db(fabs((fabs(left) > fabs(right)) ? left : right));
    if (!isfinite(gots))
        gots = -100.0;

    if (gots <= self->k1)
        gain_target_db = 0.0F;
    else
        gain_target_db = (gots - self->k1) / self->ratio + self->k1 - gots;

    if (fabs(diff = gain_target_db - self->gain_db) > 0.0000004)
        {  
        if (self->gain_db > gain_target_db)
            self->gain_db += diff * self->attack;
        else
            self->gain_db += diff * self->release;
        }
    return self->gain_db;
    }

/* the variable maxlevel dictates the amount by which the volume can be turned up */
/* when the ceiling level is breached the volume level is reduced */
compaudio_t normalizer(struct normalizer *self, compaudio_t left, compaudio_t right)
    {
    compaudio_t gots;

    gots = level2db(fabs((fabs(left) > fabs(right)) ? left : right));
    if (!isfinite(gots))
        gots = -90.3089987F;

    if (gots + self->level > self->ceiling && self->active != 0)
        {
        self->level -= (self->level - self->ceiling) * self->fall;
        }
    else
        {
        if (self->active)
            self->level += (self->maxlevel - self->level) * self->rise;
        else
            self->level += (0.0F - self->level) * self->rise;
        if (self->level > self->maxlevel)
            self->level = self->maxlevel;
        }
    return self->level;
    }
