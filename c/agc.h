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

struct agc_RC_Filter
   {
   float f;
   float q;
   float last_in;
   float lp;
   float bp;
   float hp;
   float a;
   float b;
   float c;
   };
   
struct agc
   {
   struct agc *host;       /* points to self or partner for stereo implementation */
   struct agc *partner;
   float input;
   float ratio;
   float limit;
   float nr_gain;
   float nr_onthres;
   float nr_offthres;
   float gain_interval_amount; /* agc gain can move by this amount each interval */
   int nr_state;
   float *buffer;          /* eventual buffer size depends on sample rate */
   int buffer_len;
   int sRate;              /* the sample rate in use by JACK */
   int in_pos;
   int out_pos;
   float gain;
   float DC;
   
   float ds_bias;
   float ds_gain;
   int   ds_state;

   int   RR_reset_point[4];     /* reset intervals used by all the envelope followers */
   float RR_signal[4];
   float RR_DS_high[4];
   float RR_DS_low[4];

   int   use_ducker;
   float df;
   float ducker_attack;
   float ducker_release;
   int   ducker_hold_timer;
   int   ducker_hold_timer_resetval;

   /* microphone attenuation meter levels for the GUI */
   float meter_red, meter_yellow, meter_green;
   
   /* Data for the highpass-filter. This is a simulated active RC-network.
    * It is the first operation the microphone-audio-signal is processed 
    * with. Removes DC as well as subsonic sounds...
    */ 
   struct agc_RC_Filter RC_HPF_initial[4];
   int hpstages;
   
   /* Just another RC-highpass used for enhancing HF-Detail */
   float hf_detail;
   struct agc_RC_Filter RC_HPF_detail;
   
   /* Just another RC-filter this time a lowpass used for enhancing LF-Detail */
   float lf_detail;
   struct agc_RC_Filter RC_LPF_detail;

   /* Data for the rc-phase-rotator-network */
   int use_phaserotator;   
   struct agc_RC_Filter RC_PHR[4];
   
   /* Data for the de-esser-filter-chain */
   struct agc_RC_Filter RC_F_DS;
   };

struct agc *agc_init(int sample_rate, float lookahead);
void agc_set_as_partners(struct agc *agc1, struct agc *agc2);
void agc_process_stage1(struct agc *self, float input);
void agc_process_stage2(struct agc *self, int mic_is_mute);
float agc_process_stage3(struct agc *self);
void agc_get_meter_levels(struct agc *self, int *red, int *yellow, int *green);
void agc_free(struct agc *self);
void agc_valueparse(struct agc *s, char *key, char *value);

