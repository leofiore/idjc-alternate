/*
#   mixer.h: the audio mix happens in here.
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

#include <jack/jack.h>

void mixer_init();
int mixer_main();
int mixer_control(char *command);
int mixer_healthcheck();
int mixer_process_audio(jack_nframes_t n_frames, void *arg);
void mixer_stop_players();
int mixer_new_buffer_size(jack_nframes_t n_frames);
