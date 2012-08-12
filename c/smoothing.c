/*
#   smoothing.c: Volume smoothing routines for IDJC.
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

#include <math.h>
#include "smoothing.h"

extern unsigned long sr;                /* jack sample rate */

void smoothing_mute_init(struct smoothing_mute *self, int *control)
    {
    self->level = 0.0f;
    self->control = control;
    }

void smoothing_mute_process(struct smoothing_mute *self)
    {
    if (!self->control || *self->control)
        {
        if (self->level < 0.99f)        /* switching on */
            {
            self->level += (1.0f - self->level) * 0.09f * 44100.0f / sr;
            if (self->level >= 0.99f)
                self->level = 1.0f;
            }
        }
    else 
        {
        if (self->level > 0.0F)         /* switching off */
            {
            self->level -= self->level * 0.075f * (2.0f - self->level) * (2.0f - self->level) * 44100.0f / sr;
            if (self->level < 0.00002f)
                self->level = 0.0f;
            }
        }
    }

void smoothing_volume_init(struct smoothing_volume *self, int *control, float scale)
    {
    static int nullcontrol = 0;
        
    /* default values */
    self->control = control ? control : &nullcontrol;
    self->scale = scale ? scale : 0.01775f;
    /* initial state */
    self->tracking = 127;
    self->level = 1.0f;
    }
    
void smoothing_volume_process(struct smoothing_volume *self)
    {
    if (*self->control != self->tracking)
        {
        self->tracking += (*self->control > self->tracking) ? 1 : -1;
        self->level = powf(10.0f, (self->tracking - 127) * self->scale);
        }
    }
