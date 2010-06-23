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
      
/* needs more cleaning/comments */
struct agc
   {
   float ratio;
   float limit;
   float nr_gain;
   float nr_onthres;
   float nr_offthres;
   float roverb;           /* ratio divided by buffer_len */
   int nr_state;
   float *buffer;          /* eventual buffer size depends on sample rate */
   int buffer_len;
   int sRate;              /* the sample rate in use by JACK */
   int in_pos;
   int out_pos;
   int p0, p1, p2, p3;     /* phase points */
   float gain;
   float DC;
   float amp0;
   float amp1;
   float amp2;
   float amp3;
   
   float ds_bias;
   float ds_gain;
   int   ds_state;
   float ds_amp0h;
   float ds_amp1h;
   float ds_amp2h;
   float ds_amp3h;
   float ds_amp0l;
   float ds_amp1l;
   float ds_amp2l;
   float ds_amp3l;
      
   int   use_ducker;
   float df;
   float ducker_attack;
   float ducker_release;
   int   ducker_hold_timer;
   int   ducker_hold_timer_resetval;

   float red, yellow, green;  /* reflect amount of attenuation applied */
   
   /* Data for the highpass-filter. This is a simulated active RC-network.
    * It is the first operation the microphone-audio-signal is processed 
    * with. Removes DC as well as subsonic sounds...
    */ 
   struct agc_RC_Filter RC_HPF1;
   struct agc_RC_Filter RC_HPF2;
   struct agc_RC_Filter RC_HPF3;
   struct agc_RC_Filter RC_HPF4;
   int hpstages;
   
   /* Just another RC-highpass used for enhancing HF-Detail */
   float hf_detail;
   struct agc_RC_Filter RC_HPF5;
   
   /* Just another RC-filter this time a lowpass used for enhancing LF-Detail */
   float lf_detail;
   struct agc_RC_Filter RC_LPF1;

   /* Data for the rc-phase-rotator-network */
   int use_phaserotator;   
   struct agc_RC_Filter RC_PHR1;
   struct agc_RC_Filter RC_PHR2;
   struct agc_RC_Filter RC_PHR3;
   struct agc_RC_Filter RC_PHR4;
   
   /* Data for the de-esser-filter-chain */
   struct agc_RC_Filter RC_HPF6;
   struct agc_RC_Filter RC_LPF2;
   
   };

struct agc *agc_init(int sample_rate, float lookahead);
float agc_process(struct agc *self, float input, int mute);
void agc_free(struct agc *self);
void agc_valueparse(struct agc *s, char *key, char *value);

