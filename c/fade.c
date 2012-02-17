/*
#   fade.c: fade in/out progressive gain adjustment
#   Copyright (C) 2011 Stephen Fairchild (s-fairchild@users.sourceforge.net)
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

#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include <pthread.h>
#include "fade.h"

struct fade *fade_init(int samplerate, float level)
    {
    struct fade *s;
        
    if (!(s = malloc(sizeof (struct fade))))
        {
        fprintf(stderr, "fade_init: malloc failure\n");
        exit(5);
        }

    s->samplerate = samplerate;
    s->baselevel = level;
    if (pthread_mutex_init(&s->mutex, NULL))
        {
        fprintf(stderr, "fade_init: mutex creation failed\n");
        exit(5);
        }

    fade_set(s, FADE_SET_HIGH, 0.0f, FADE_IN);
    
    return s;
    }
    
void fade_destroy(struct fade *s)
    {
    pthread_mutex_destroy(&s->mutex);
    free(s);
    }

void fade_set(struct fade *s, enum fade_startpos sp, float t, enum fade_direction d)
    {
    pthread_mutex_lock(&s->mutex);

    s->startpos = sp;
    if (t >= 0.0f)
        s->samples = floorf(s->samplerate * t);
    if (d != FADE_DIRECTION_UNCHANGED)
        s->newdirection = d;
    
    s->newdata = 1;
    pthread_mutex_unlock(&s->mutex);
    }
    
float fade_get(struct fade *s)
    {
    if (s->newdata)   
        {
        pthread_mutex_lock(&s->mutex);
        
        if (s->startpos == FADE_SET_HIGH)
            s->level = 1.0f;
        if (s->startpos == FADE_SET_LOW)
            s->level = 0.0f;
        if ((s->direction = s->newdirection) == FADE_IN)
            s->rate = powf(s->baselevel, -1.0f / s->samples);
        else
            s->rate = powf(s->baselevel, 1.0f / s->samples);
        
        s->moving = 1;
        s->newdata = 0;
        pthread_mutex_unlock(&s->mutex);
        }
        
    if (s->moving)
        {
        if (s->direction == FADE_IN)
            {
            if (s->level < s->baselevel)
                s->level = s->baselevel;
            else
                if ((s->level *= s->rate) >= 1.0f)
                    {
                    s->level = 1.0f;
                    s->moving = 0;
                    }
            }
            
        if (s->direction == FADE_OUT)
            {
            if (s->level > s->baselevel)
                s->level *= s->rate;
            else
                {
                s->level = 0.0f;
                s->moving = 0;
                }
            }
        }
        
    return s->level;
    }
