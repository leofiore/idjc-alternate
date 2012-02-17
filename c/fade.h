/*
#   fade.h: fade in/out progressive gain adjustment
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

#ifndef FADE_H
#define FADE_H

enum fade_startpos { FADE_SET_LOW, FADE_SET_SAME, FADE_SET_HIGH };
enum fade_direction { FADE_IN, FADE_OUT, FADE_DIRECTION_UNCHANGED };

struct fade
    {
    float level;
    enum fade_direction direction;
    float rate;
    float baselevel;
    int samplerate;
    int moving;
    int newdata;
    enum fade_startpos startpos;
    int samples;
    enum fade_direction newdirection;
    pthread_mutex_t mutex;
    };

/* fade level l stands before -infinity dB */
struct fade *fade_init(int samplerate, float l);

void fade_destroy(struct fade *s);

/* initiate a fade that would take t seconds to complete from one end of the range to the other */
void fade_set(struct fade *s, enum fade_startpos, float t, enum fade_direction);

/* obtain the next fade value */
float fade_get(struct fade *s);

#endif /* FADE_H */
