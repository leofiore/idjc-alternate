/*
#   peakfilter.c: finds a peak level from a filtered signal source
#   Copyright (C) 2010 Stephen Fairchild (s-fairchild@users.sourceforge.net)
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

#define _GNU_SOURCE
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <math.h>
#include "peakfilter.h"
#include "dbconvert.h"

struct peakfilter *peakfilter_create(float window, int sample_rate)
    {
    struct peakfilter *self;
    int n_stages;
    
    if (!(self = malloc(sizeof (struct peakfilter))))
        {
        fprintf(stderr, "malloc failure\n");
        exit(-5);
        }
    
    if ((n_stages = (int)(window * sample_rate)) < 1)
        n_stages = 1;
    
    if (!(self->ptr = self->start = calloc(n_stages, sizeof (float))))
        {
        fprintf(stderr, "malloc failure\n");
        exit(-5);
        }
        
    self->end = self->start + n_stages;   
    self->peak = 0.0f;
    
    return self;
    }

void peakfilter_destroy(struct peakfilter *self)
    {
    free(self->start);
    free(self);
    }

void peakfilter_process(struct peakfilter *self, float sample)
    {
    float least;
    float *p;
    
    *self->ptr++ = fabsf(sample);
    if (self->ptr == self->end)
        self->ptr = self->start;
        
    for (p = self->start, least = HUGE_VALF; p < self->end; p++)
        if (*p < least)
            least = *p;
    
    if (least > self->peak)
        self->peak = least;
    }

float peakfilter_read(struct peakfilter *self)
    {
    float ret;
    
    ret = self->peak;
    self->peak = 0.0f;
    return ret;
    }

