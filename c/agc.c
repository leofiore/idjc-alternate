/*
#   agc.c: a fast lookahead microphone AGC
#   Copyright (C) 2008 Stefan Fendt      (stefan@sfendt.de)
#   Copyright (C) 2008-2010 Stephen Fairchild (s-fairchild@users.sourceforge.net)
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
#include <string.h>
#include <math.h>

#include "agc.h"

#if 0
void agc_process_OLD(struct agc *s, float input, int mic_is_mute)
   {
   /* Signal flow in this AGC-Code is as follows :
    * ============================================
    *
    *  input-signal
    *       |
    *  steep HP-Filter (modelled active RC-network, this is what is usually found
    *       |           in decent analog hardware-devices... so it hopefully gives
    *       |           an analog sound...)
    *       |
    *  HF+LF-Detail    (the same RC-network without resonance)
    *       |
    *  phase-rotator   (as we already have the analog RC-modeling-filter, it's reused
    *       |           for this, too, as it is in a real hardware-device)
    *       |
    *  lookahead-agc
    *  with de-esser  -----> ducker-signal
    *  and noise-gate
    *       |
    *  output-signal
    */
    
   const float max_amp=1.0f; // IDJC has a 0dB-level of +/- 1.0 not +/-32767.0 
   
   float amp = 0;
   float factor, f2;

   float ds_amph = 0;
   float ds_ampl = 0;
   float ds_input, ds_lp, ds_hp;
   float phase, ai;
   
   float duck_amp;

   /* digital model of an analog active RC-Highpassfilter network
    * removes DC and subsonic sounds... one stage has 12dB/octave
    * so we badly need to cascade it to make it steep enough ...
    */
   input += s->RC_HPF1.q * s->RC_HPF1.bp;
   s->RC_HPF1.hp = s->RC_HPF1.c * ( s->RC_HPF1.hp + input - s->RC_HPF1.last_in );
   s->RC_HPF1.bp = s->RC_HPF1.bp * s->RC_HPF1.a + s->RC_HPF1.hp * s->RC_HPF1.b;
   s->RC_HPF1.last_in = input;
   input = s->RC_HPF1.hp;
   
   if (s->hpstages > 1)
      {
      input += s->RC_HPF2.q * s->RC_HPF2.bp;
      s->RC_HPF2.hp = s->RC_HPF2.c * ( s->RC_HPF2.hp + input - s->RC_HPF2.last_in );
      s->RC_HPF2.bp = s->RC_HPF2.bp * s->RC_HPF2.a + s->RC_HPF2.hp * s->RC_HPF2.b;
      s->RC_HPF2.last_in = input;
      input = s->RC_HPF2.hp;
      }
   
   if (s->hpstages > 2)
      {
      input += s->RC_HPF3.q * s->RC_HPF3.bp;
      s->RC_HPF3.hp = s->RC_HPF3.c * ( s->RC_HPF3.hp + input - s->RC_HPF3.last_in );
      s->RC_HPF3.bp = s->RC_HPF3.bp * s->RC_HPF3.a + s->RC_HPF3.hp * s->RC_HPF3.b;
      s->RC_HPF3.last_in = input;
      input = s->RC_HPF3.hp;
      }
         
   if (s->hpstages > 3)
      {
      input += s->RC_HPF4.q * s->RC_HPF4.bp;
      s->RC_HPF4.hp = s->RC_HPF4.c * ( s->RC_HPF4.hp + input - s->RC_HPF4.last_in );
      s->RC_HPF4.bp = s->RC_HPF4.bp * s->RC_HPF4.a + s->RC_HPF4.hp * s->RC_HPF4.b;
      s->RC_HPF4.last_in = input;
      input = s->RC_HPF4.hp;
      }

   /* same RC-Network (but with only one stage and without resonance/feedback (->6dB/octave))
    * used as HF-Detail-Filter 
    */
   s->RC_HPF5.hp = s->RC_HPF5.c * ( s->RC_HPF5.hp + input - s->RC_HPF5.last_in );
   s->RC_HPF5.last_in = input;
   input += s->RC_HPF5.hp*s->hf_detail;
   
   /* same RC-Network (but with only one stage and without resonance/feedback)
    * used as LF-Detail-Filter 
    */
   s->RC_LPF1.lp = s->RC_LPF1.lp * s->RC_LPF1.a + input * s->RC_LPF1.b;
   input += s->RC_LPF1.lp*s->lf_detail;
   
   /* Phase-rotator done with RC-simulation
    * for good reasons doesn't use Q/resonance either...
    */
   if (s->use_phaserotator)
      {
      /* stage 1 */
      s->RC_PHR1.hp = s->RC_PHR1.c * ( s->RC_PHR1.hp + input - s->RC_PHR1.last_in );
      s->RC_PHR1.lp = s->RC_PHR1.lp * s->RC_PHR1.a + input * s->RC_PHR1.b;
      s->RC_PHR1.last_in = input;
      input = s->RC_PHR1.lp - s->RC_PHR1.hp;

      /* stage 2 */
      s->RC_PHR2.hp = s->RC_PHR2.c * ( s->RC_PHR2.hp + input - s->RC_PHR2.last_in );
      s->RC_PHR2.lp = s->RC_PHR2.lp * s->RC_PHR2.a + input * s->RC_PHR2.b;
      s->RC_PHR2.last_in = input;
      input = s->RC_PHR2.lp - s->RC_PHR2.hp;

      /* stage 3 */
      s->RC_PHR3.hp = s->RC_PHR3.c * ( s->RC_PHR3.hp + input - s->RC_PHR3.last_in );
      s->RC_PHR3.lp = s->RC_PHR3.lp * s->RC_PHR3.a + input * s->RC_PHR3.b;
      s->RC_PHR3.last_in = input;
      input = s->RC_PHR3.lp - s->RC_PHR3.hp;

      /* stage 4 */
      s->RC_PHR4.hp = s->RC_PHR4.c * ( s->RC_PHR4.hp + input - s->RC_PHR4.last_in );
      s->RC_PHR4.lp = s->RC_PHR4.lp * s->RC_PHR4.a + input * s->RC_PHR4.b;
      s->RC_PHR4.last_in = input;
      input = s->RC_PHR4.lp - s->RC_PHR4.hp;
      }

   /* feed input into ring-buffer */
   s->buffer[s->in_pos % s->buffer_len] = input;
   
   /* update pointers into ring-buffer */  
   s->in_pos++;
   s->out_pos++;
   
   /* derive phase for the envelope-followers */
   phase = s->in_pos % (2 * s->buffer_len);

   /* De-Esser sidechain-filter,... you wont believe it,... the next RC-Network...
    * this time we want a more "clever" de-esser. It doesn't just only check for
    * the presence of high frequencies. It does check for the absence of low-frequencies, too...
    *
    * this way it can destinguish sharp sylables and mouseclicks from usual vocals
    * with a higher frequency-amount...
    */
    
   ds_input = input;
   ds_input += s->RC_HPF6.q * s->RC_HPF6.bp;
   s->RC_HPF6.lp = s->RC_HPF6.lp * s->RC_HPF6.a + ds_input * s->RC_HPF6.b;
   s->RC_HPF6.hp = s->RC_HPF6.c * ( s->RC_HPF6.hp + input - s->RC_HPF6.last_in );
   s->RC_HPF6.bp = s->RC_HPF6.bp * s->RC_HPF6.a + s->RC_HPF6.hp * s->RC_HPF6.b;
   s->RC_HPF6.last_in = ds_input;
   ds_hp = fabsf(s->RC_HPF6.hp);   
   ds_lp = fabsf(s->RC_HPF6.lp);
   
   /* round-robin-4-peak-envelope-follower for the hp-sidechain of the de-esser */
   if (s->ds_amp0h < ds_hp) s->ds_amp0h = ds_hp;
   if (s->ds_amp1h < ds_hp) s->ds_amp1h = ds_hp;
   if (s->ds_amp2h < ds_hp) s->ds_amp2h = ds_hp;
   if (s->ds_amp3h < ds_hp) s->ds_amp3h = ds_hp;
   
   if (phase == s->p0) s->ds_amp0h = 0.0f;
   else
   if (phase == s->p1) s->ds_amp1h = 0.0f;
   else
   if (phase == s->p2) s->ds_amp2h = 0.0f;
   else
   if (phase == s->p3) s->ds_amp3h = 0.0f;
   
   if (ds_amph < s->ds_amp0h) ds_amph = s->ds_amp0h;
   if (ds_amph < s->ds_amp1h) ds_amph = s->ds_amp1h;
   if (ds_amph < s->ds_amp2h) ds_amph = s->ds_amp2h;
   if (ds_amph < s->ds_amp3h) ds_amph = s->ds_amp3h;

   /* round-robin-4-peak-envelope-follower for the lp-sidechain of the de-esser */
   if (s->ds_amp0l < ds_lp) s->ds_amp0l = ds_lp;
   if (s->ds_amp1l < ds_lp) s->ds_amp1l = ds_lp;
   if (s->ds_amp2l < ds_lp) s->ds_amp2l = ds_lp;
   if (s->ds_amp3l < ds_lp) s->ds_amp3l = ds_lp;
   
   if (phase == s->p0) s->ds_amp0l = 0.0f;
   else
   if (phase == s->p1) s->ds_amp1l = 0.0f;
   else
   if (phase == s->p2) s->ds_amp2l = 0.0f;
   else
   if (phase == s->p3) s->ds_amp3l = 0.0f;
   
   if (ds_ampl < s->ds_amp0l) ds_ampl = s->ds_amp0l;
   if (ds_ampl < s->ds_amp1l) ds_ampl = s->ds_amp1l;
   if (ds_ampl < s->ds_amp2l) ds_ampl = s->ds_amp2l;
   if (ds_ampl < s->ds_amp3l) ds_ampl = s->ds_amp3l;
 
   /* round-robin-4-peak-envelope-follower for the agc */
   ai = fabsf(input);
   if (s->amp0 < ai) s->amp0 = ai;
   if (s->amp1 < ai) s->amp1 = ai;
   if (s->amp2 < ai) s->amp2 = ai;
   if (s->amp3 < ai) s->amp3 = ai;
   
   if (phase == s->p0) s->amp0 = 0.0f;
   else
   if (phase == s->p1) s->amp1 = 0.0f;
   else
   if (phase == s->p2) s->amp2 = 0.0f;
   else
   if (phase == s->p3) s->amp3 = 0.0f;

   if (amp < s->amp0) amp = s->amp0;
   if (amp < s->amp1) amp = s->amp1;
   if (amp < s->amp2) amp = s->amp2;
   if (amp < s->amp3) amp = s->amp3;

   /* raw-amplification-factor limited to maximum allowed ratio */
   factor = max_amp * s->limit / (amp + 0.0001f);
   if (factor > s->ratio)
      {
      factor = s->ratio;
      }
   f2 = factor;

   /* if below noise-floor, attenuate signal */
   if (amp < max_amp * s->nr_onthres)
      {
      s->nr_state=1;
      }
   if (amp > max_amp * s->nr_offthres)
      {
      s->nr_state=0;
      }
   if (s->nr_state==1)
      {
      factor *= s->nr_gain;
      }

   /* if de-esser says there are only high frequencies, attenuate signal */
   if (ds_amph * s->ds_bias > ds_ampl * 1.3333333f)
      {
      s->ds_state = 1;
      }
   if (ds_amph * s->ds_bias < ds_ampl * 0.75f)
      {
      s->ds_state = 0;
      }
   if (s->ds_state == 1)
      {
      factor *= s->ds_gain;
      }

   /* modulate gain-factor */
   if (s->gain < factor) s->gain += s->roverb;
   if (s->gain > factor) s->gain -= s->roverb;

   /* ducking is optional and must not work when the mic is closed */
   if (mic_is_mute || s->use_ducker == 0)
      {
      if (s->df < 1.0f)
         s->df += s->ducker_release;
      else
         s->df = 1.0f;
      }
   else
      {
      /* calculate ducking factor */
      duck_amp = 1.0f - factor * amp;
   
      /* if duck-amp is below the minimum-allowed level (limit enforces some headroom)
      * then limit duck-amp to that minimum-allowed level. This ensures, that if the
      * microphone-headroom is set to a sensible value (-2..-3dB) there still is some
      * music audiable in the background...
      */
      if (duck_amp < 1.0f - (max_amp * s->limit))
         {
         duck_amp = 1.0f - (max_amp * s->limit);
         }
      
      /* ducker is "opened" fast (same rate as agc -> 10ms)
      * but closed more slowly...
      */
      if (s->df < duck_amp)
         {
         if (s->ducker_hold_timer == 0)
            s->df += s->ducker_release;
         else
            s->ducker_hold_timer--;
         }
      if (s->df > duck_amp)
         {
         s->df -= s->ducker_attack;
         s->ducker_hold_timer = s->ducker_hold_timer_resetval;
         }
      }

   /* maintain a peak hold gain figure for the GUI compression meter
    * essentially this is metadata 
    */
   if ((s->out_pos & 0x7) == 0)
      {
      s->red = f2 / s->ratio;
      s->yellow = s->ds_state ? s->ds_gain : 1.0f;
      s->green = s->nr_state ? s->nr_gain : 1.0f;
      }

   /* modulate delayed signal with gain */
   return s->buffer[s->out_pos % s->buffer_len] * s->gain;
   }
#endif


/**************************************************************************/

static float agc_12db_hpfilter(struct agc_RC_Filter *c, struct agc_RC_Filter *h, float input)
   {
   input += h->q * c->bp;
   c->hp = h->c * ( c->hp + input - c->last_in );
   c->bp = c->bp * h->a + c->hp * h->b;
   c->last_in = input;
   return c->hp;
   }

static float agc_6db_hpfilter(float detail, struct agc_RC_Filter *c, struct agc_RC_Filter *h, float input)
   {
   c->hp = h->c * (c->hp + input - c->last_in);
   c->last_in = input;
   return input + c->hp * detail;
   }

static float agc_6db_lpfilter(float detail, struct agc_RC_Filter *c, struct agc_RC_Filter *h, float input)
   {
   c->lp = c->lp * h->a + input * h->b;
   return input + c->lp * detail;
   }

static float agc_phaserotate(struct agc_RC_Filter *c, float input)
   {
   c->hp = c->c * (c->hp + input - c->last_in);
   c->lp = c->lp * c->a + input * c->b;
   c->last_in = input;
   return c->lp - c->hp;
   }

void agc_process_stage1(struct agc *s, float input)
   {
   /* An analog active RC-Highpassfilter network to remove DC and subsonic sounds
    * each stage has 12dB/octave of attenuation.
    */
   for (int i = 0, q = s->host->hpstages; i < q; ++i)
      input = agc_12db_hpfilter(s->RC_HPF_initial + i, s->host->RC_HPF_initial + i, input);

   /* RC-Network (but with only one stage and without resonance/feedback (->6dB/octave))
    * used as HF-Detail-Filter 
    */
   input = agc_6db_hpfilter(s->hf_detail, &s->RC_HPF_detail, &s->host->RC_HPF_detail, input);

   /* RC-Network (but with only one stage and without resonance/feedback)
    * used as LF-Detail-Filter 
    */
   input = agc_6db_lpfilter(s->lf_detail, &s->RC_LPF_detail, &s->host->RC_LPF_detail, input); 

   /* Phase-rotator done with RC-simulation
    * for good reasons doesn't use Q/resonance either...
    */
   if (s->use_phaserotator)
      for (int i = 0; i < 4; ++i)
         input = agc_phaserotate(s->RC_PHR + i, input);

   /* feed input into ring-buffer, store input */
   s->buffer[s->in_pos % s->buffer_len] = s->input = input;
   
   /* update pointers of the ring-buffer */  
   s->in_pos++;
   s->out_pos++;
   }

static float agc_quad_rr(float *storage, int *reset_point, int phase, float input)
   {
   float highest = 0.0f; 
   
   input = fabsf(input);
   
   for (int i = 0; i < 4; ++i, ++storage, ++reset_point)
      {
      if (*reset_point == phase)
         *storage = 0;
      if (input > *storage)
         *storage = input;
      if (*storage > highest)
         highest = *storage;
      }
   return highest;
   }

void agc_process_stage2(struct agc *s, int mic_is_mute)
   {
   /* audio signal for sidechain use - possibly combined */
   float input = (s->input + s->host->input) / 2.0f;
   /* phase for use by all of the envelope-followers */
   float phase = s->in_pos % (2 * s->buffer_len);
   /* de-esser values */
   float ds_input, ds_amph, ds_ampl;
   /* the input signal level as computed by the envelope follower */
   float amp = 0;
   /* the amplification factor */
   float factor, orig_factor;
   /* the computed ducker amplification factor - used externally */
   float duck_amp;

   if (s == s->host)
      {
      /* De-Esser sidechain-filter - does high and low pass filtering
       */
      ds_input = input;
      ds_input += s->RC_F_DS.q * s->RC_F_DS.bp;
      s->RC_F_DS.lp = s->RC_F_DS.lp * s->RC_F_DS.a + ds_input * s->RC_F_DS.b;
      s->RC_F_DS.hp = s->RC_F_DS.c * ( s->RC_F_DS.hp + input - s->RC_F_DS.last_in );
      s->RC_F_DS.bp = s->RC_F_DS.bp * s->RC_F_DS.a + s->RC_F_DS.hp * s->RC_F_DS.b;
      s->RC_F_DS.last_in = ds_input;
      /* follow the envelope of the de-esser high and low pass filtered signal */
      ds_amph = agc_quad_rr(s->RR_DS_high, s->RR_reset_point, phase, s->RC_F_DS.hp);
      ds_ampl = agc_quad_rr(s->RR_DS_low, s->RR_reset_point, phase, s->RC_F_DS.lp);
      
      /* round-robin-4-peak-envelope-follower tracking the general signal level */
      amp = agc_quad_rr(s->RR_signal, s->RR_reset_point, phase, input);

      /* raw-amplification-factor limited to maximum allowed ratio */
      factor = s->limit / (amp + 0.0001f);
      if (factor > s->ratio)
         factor = s->ratio;

      /* so we can know how much attenuation was applied this is stored */
      orig_factor = factor;

      /* if below noise-floor, attenuate signal */
      if (amp < s->nr_onthres)
         s->nr_state = 1;

      if (amp > s->nr_offthres)
         s->nr_state = 0;

      if (s->nr_state==1)
         factor *= s->nr_gain;

      /* if de-esser says there are only high frequencies, attenuate signal */
      if (ds_amph * s->ds_bias > ds_ampl * 1.3333333f)
          s->ds_state = 1;
 
      if (ds_amph * s->ds_bias < ds_ampl * 0.75f)
          s->ds_state = 0;
 
      if (s->ds_state == 1)
          factor *= s->ds_gain;
 
      /* modulate gain-factor */
      if (s->gain < factor)
         s->gain += s->gain_interval_amount;

      if (s->gain > factor)
         s->gain -= s->gain_interval_amount;

      /* ducking is optional and must not work when the mic is closed */
      if (mic_is_mute || s->use_ducker == 0)
         {
         if (s->df < 1.0f)
            s->df += s->ducker_release;
         else
            s->df = 1.0f;
         }
      else
         {
         /* calculate ducking factor */
         duck_amp = 1.0f - factor * amp;
      
         /* if duck-amp is below the minimum-allowed level (limit enforces some headroom)
          * then limit duck-amp to that minimum-allowed level. This ensures, that if the
          * microphone-headroom is set to a sensible value (-2..-3dB) there still is some
          * music audiable in the background...
          */
         if (duck_amp < 1.0f - s->limit)
            {
            duck_amp = 1.0f - s->limit;
            }
         
         /* ducker is "opened" fast (same rate as agc -> 10ms)
          * but closed more slowly...
          */
         if (s->df < duck_amp)
            {
            if (s->ducker_hold_timer == 0)
               s->df += s->ducker_release;
            else
               s->ducker_hold_timer--;
            }
         if (s->df > duck_amp)
            {
            s->df -= s->ducker_attack;
            s->ducker_hold_timer = s->ducker_hold_timer_resetval;
            }


         }

      /* maintain a peak hold gain figure for the GUI compression meter
       * essentially this is metadata 
       */
      if ((s->out_pos & 0x7) == 0)
         {
         s->meter_red = orig_factor / s->ratio;
         s->meter_yellow = s->ds_state ? s->ds_gain : 1.0f;
         s->meter_green = s->nr_state ? s->nr_gain : 1.0f;
         }
      }
      
   /* modulate delayed signal with gain */
   }

float agc_process_stage3(struct agc *s)
   {
   return s->buffer[s->out_pos % s->buffer_len] * s->host->gain;
   }

static void setup_ratio(struct agc *s, float ratio_db)
   {
   s->ratio = powf(10.0f, ratio_db / 20.0f);
   s->gain_interval_amount = s->ratio / s->buffer_len;
   }

static void setup_subsonic(struct agc *s, float fCutoff)
   {
   s->RC_HPF_initial[0].f = fCutoff;
   s->RC_HPF_initial[0].q = 0.375f;
   s->RC_HPF_initial[0].a = 1.0f - (1.0f/s->sRate) / ((1.0f / (s->RC_HPF_initial[0].f * 2.0f * M_PI)) + (1.0f/s->sRate));
   s->RC_HPF_initial[0].b = 1.0f - s->RC_HPF_initial[0].a;
   s->RC_HPF_initial[0].c = (1.0f/(s->RC_HPF_initial[0].f*2.0f*M_PI)) / ( (1.0f/(s->RC_HPF_initial[0].f*2.0f*M_PI)) + (1.0f/s->sRate));
   
   s->RC_HPF_initial[3] = s->RC_HPF_initial[2] = s->RC_HPF_initial[1] = s->RC_HPF_initial[0];
   }

static void setup_lfdetail(struct agc *s, float multi, float fCutoff)
   {
   s->lf_detail = multi;
   s->RC_LPF_detail.f = fCutoff;
   s->RC_LPF_detail.q = 0.375f;
   s->RC_LPF_detail.a = 1.0f - (1.0f/s->sRate) / ( (1.0f/(s->RC_LPF_detail.f*2.0f*M_PI)) + (1.0f/s->sRate) );
   s->RC_LPF_detail.b = 1.0f - s->RC_LPF_detail.a;
   s->RC_LPF_detail.c = (1.0f/(s->RC_LPF_detail.f*2.0f*M_PI)) / ( (1.0f/(s->RC_LPF_detail.f*2.0f*M_PI)) + (1.0f/s->sRate) );
   }

static void setup_hfdetail(struct agc *s, float multi, float fCutoff)
   {
   s->hf_detail = multi;
   s->RC_HPF_detail.f = fCutoff;
   s->RC_HPF_detail.q = 0.375f;
   s->RC_HPF_detail.a = 1.0f - (1.0f/s->sRate) / ( (1.0f/(s->RC_HPF_detail.f*2.0f*M_PI)) + (1.0f/s->sRate) );
   s->RC_HPF_detail.b = 1.0f - s->RC_HPF_detail.a;
   s->RC_HPF_detail.c = (1.0f/(s->RC_HPF_detail.f*2.0f*M_PI)) / ( (1.0f/(s->RC_HPF_detail.f*2.0f*M_PI)) + (1.0f/s->sRate) );
   }

struct agc *agc_init(int sRate, float lookahead)
   {
   struct agc *s;

   if (!(s = calloc(1, sizeof (struct agc))))
      {
      fprintf(stderr, "agc_init: malloc failure\n");
      return NULL;
      }

   if (!(s->buffer = calloc((s->buffer_len = (s->sRate = sRate) * lookahead), sizeof (float))))
      {
      fprintf(stderr, "agc_init: malloc failure\n");
      free(s);
      return NULL;
      }

   s->host = s;  /* can set this to another agc for this to be the junior of a stereo pair */

   {
      /* determine the phase points for the envelope followers */
      int p4 = s->buffer_len * 2;

      s->RR_reset_point[0] = 0;
      s->RR_reset_point[1] = p4 * 1 / 4;
      s->RR_reset_point[2] = p4 * 2 / 4;
      s->RR_reset_point[3] = p4 * 3 / 4;
   }

   setup_ratio(s, 3.0f);/* 3:1 "compression" */
   s->limit = 0.707f;   /* signal level to top out at */
   s->in_pos = s->buffer_len - 1;
   s->out_pos = 1;
   s->gain = 0.0f;
   s->nr_onthres = 0.1f;      /* silence detection level */
   s->nr_offthres = 0.1001f;  /* non-silence detection level */
   s->nr_gain = 0.5f;         /* if silence detected reduce gain by 6dB */
   
   s->ds_bias  =  0.35f; /* lpf * bias / hpf exceeds 1 for de-esser to go active */
   s->ds_gain  =  0.5f;  /* attenuate signal by this amount */
   s->meter_red = s->meter_yellow = s->meter_green = 1.0f;  /* initial meter info */
   
   /* setup coefficients for the ducker */
   s->ducker_release = 1.0f / (0.250f * s->sRate); /* 250ms */
   s->ducker_attack  = 1.0f / s->buffer_len;    /* same as lookahead delay */
   s->ducker_hold_timer_resetval = 0.500f * s->sRate; /* 500ms */
   s->df = 1.0f;
   
   /* setup coefficients for the subsonic-and-DC-killer-RC-highpass */
   setup_subsonic(s, 100.0f);
   s->hpstages = 4;
   
   /* setup coefficients for the HF-Detail highpass */
   setup_hfdetail(s, 4.0f, 2000.0f);
   
   /* setup coefficients for the LF-Detail lowpass */
   setup_lfdetail(s, 4.0f, 150.0f);
   
   /* setup coefficients for the phase-rotator, first stage */
   s->use_phaserotator = 1;
   s->RC_PHR[0].f = 300.0f;
   s->RC_PHR[0].q = 0.000f;
   s->RC_PHR[0].a = 1.0f - (1.0f/s->sRate) / ( (1.0f/(s->RC_PHR[0].f*2.0f*M_PI)) + (1.0f/s->sRate) );
   s->RC_PHR[0].b = 1.0f - s->RC_PHR[0].a;
   s->RC_PHR[0].c = (1.0f/(s->RC_PHR[0].f*2.0f*M_PI)) / ( (1.0f/(s->RC_PHR[0].f*2.0f*M_PI)) + (1.0f/s->sRate) );
   /* copy settings for the further three stages */
   s->RC_PHR[3] = s->RC_PHR[2] = s->RC_PHR[1] = s->RC_PHR[0];
   
   /* setup coefficients for the de-esser-sidechain highpass/lowpass filter */
   s->RC_F_DS.f = 1000.0f;
   s->RC_F_DS.q = 1.000f;
   s->RC_F_DS.a = 1.0f - (1.0f/s->sRate) / ( (1.0f/(s->RC_F_DS.f*2.0f*M_PI)) + (1.0f/s->sRate) );
   s->RC_F_DS.b = 1.0f - s->RC_F_DS.a;
   s->RC_F_DS.c = (1.0f/(s->RC_F_DS.f*2.0f*M_PI)) / ( (1.0f/(s->RC_F_DS.f*2.0f*M_PI)) + (1.0f/s->sRate) );

   return s;
   }

void agc_free(struct agc *s)
   {
   free(s->buffer);
   free(s);
   }

void agc_valueparse(struct agc *s, char *key, char *value)
   {
   if (!strcmp(key, "phaserotate"))
      {
      s->use_phaserotator = (value[0] == '1');
      return;
      }

   if (!strcmp(key, "gain"))
      {
      setup_ratio(s, strtof(value, NULL));
      return;
      }

   if (!strcmp(key, "limit"))
      {
      s->limit = powf(2.0f, strtof(value, NULL) / 6.0f);
      return;
      }

   if (!strcmp(key, "ngthresh"))
      {
      s->nr_onthres = powf(2.0f, (strtof(value, NULL) - 1.0f) / 6.0f);
      s->nr_offthres = powf(2.0f, (strtof(value, NULL) + 1.0f) / 6.0f);
      return;
      }

   if (!strcmp(key, "nggain"))
      {
      s->nr_gain = powf(2.0f, strtof(value, NULL) / 6.0f);
      return;
      }

   if (!strcmp(key, "duckenable"))
      {
      s->use_ducker = (value[0] == '1');
      return;
      }

   if (!strcmp(key, "duckrelease"))
      {
      s->ducker_release = 1000.0f / (strtof(value, NULL) * s->sRate);
      return;
      }

   if (!strcmp(key, "duckhold"))
      {
      s->ducker_hold_timer_resetval = atoi(value) * s->sRate / 1000;
      return;
      }

   if (!strcmp(key, "deessbias"))
      {
      s->ds_bias = strtof(value, NULL);
      return;
      }

   if (!strcmp(key, "deessgain"))
      {
      s->ds_gain = powf(2.0f, strtof(value, NULL) / 6.0f);
      return;
      }

   if (!strcmp(key, "hpcutoff"))
      {
      setup_subsonic(s, strtof(value, NULL));
      return;
      }

   if (!strcmp(key, "hpstages"))
      {
      s->hpstages = (int)(strtof(value, NULL) + 0.5f);
      }

   if (!strcmp(key, "hfmulti"))
      {
      setup_hfdetail(s, strtof(value, NULL), s->RC_HPF_detail.f);
      return;
      }

   if (!strcmp(key, "hfcutoff"))
      {
      setup_hfdetail(s, s->hf_detail, strtof(value, NULL));
      return;
      }

   if (!strcmp(key, "lfmulti"))
      {
      setup_lfdetail(s, strtof(value, NULL), s->RC_LPF_detail.f);
      return;
      }

   if (!strcmp(key, "lfcutoff"))
      {
      setup_lfdetail(s, s->lf_detail, strtof(value, NULL));
      return;
      }
   }
