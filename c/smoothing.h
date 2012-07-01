/*
#   smoothing.h: Volume smoothing routines for IDJC.
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

#ifndef SMOOTHING_H
#define SMOOTHING_H

struct smoothing_mute
    {
    int *control;
    float level;
    };

void smoothing_mute_init(struct smoothing_mute *, int *control);
void smoothing_mute_process(struct smoothing_mute *);

struct smoothing_volume
    {
    int *control;
    int tracking;
    float scale;
    float level;
    };
    
void smoothing_volume_init(struct smoothing_volume *self, int *control, float scale);
void smoothing_volume_process(struct smoothing_volume *self);

#endif /* SMOOTHING_H */
