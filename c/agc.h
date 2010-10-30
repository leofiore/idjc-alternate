/*
#   agc.h: a fast lookahead microphone AGC
#   Copyright (C) 2008 Stefan Fendt      (stefan@sfendt.de)
#   Copyright (C) 2008 Stephen Fairchild (s-fairchild@users.sourceforge.net)
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

/* opaque pointer */
struct agc;

/* initialisation */
struct agc *agc_init(int sample_rate, float lookahead, int id);

/* declare another agc to be pairable for stereo */
void agc_set_as_partners(struct agc *agc1, struct agc *agc2);

/* initiate or cancel stereo mode - called on subordinate */
void agc_set_partnered_mode(struct agc *self, int boolean);

/* run each of these in turn, intersperse paired mics
 * parameter mic_is_mute toggles ducker operation
 */
void agc_process_stage1(struct agc *self, float input);
void agc_process_stage2(struct agc *self, int mic_is_mute);
float agc_process_stage3(struct agc *self);

/* the amount of attenuation broken down into three parts */
void agc_get_meter_levels(struct agc *self, int *signal_cap, int *de_ess, int *noise_gate);

/* the amount of ducking to apply */
float agc_get_ducking_factor(struct agc *self);

/* call this when going idle for a while - accumulated data is flushed */
void agc_reset(struct agc *self);

/* take down */
void agc_free(struct agc *self);

/* configuration from control strings */
void agc_control(struct agc *s, char *key, char *value);
