/*
#   mic.c: wrapper for AGC and provides mixing to stereo
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

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

#include "mic.h"
#include "dbconvert.h"

static const float peak_init = 4.46e-7f; /* -127dB */

static void calculate_gain_values(struct mic *self)
   {
   self->mgain = powf(10.0f, self->gain / 20.0f);
   if (self->pan_active)
      {
      self->lgain = cosf((float)self->pan / 63.66197724f);
      self->rgain = sinf((float)self->pan / 63.66197724f);
      }
   else
      self->lgain = self->rgain = 1.0f;
   
   if (self->invert)
      {
      self->mgain *= -1.0f;
      self->lgain *= -1.0f;
      self->rgain *= -1.0f;
      }
   }

void mic_process(struct mic *self, float input)
   {
   if (self->active)
      {
      if (self->open && self->mute < 0.999999)
         self->mute += (1.0f - self->mute) * 26.46 / self->sample_rate;
      else if (!self->open && self->mute > 0.0000004)
         self->mute -= self->mute * 12.348 / self->sample_rate;
      else
         self->mute = self->open ? 1.0f : 0.0f;
         
      if (isunordered(input, input))
         input = 0.0f;
        
      self->unp = input * self->mgain;
      self->unpm = self->unp * self->mute;
      self->unpmdj = self->unpm * self->djmute;

      if (self->complexity)
         self->lrc = agc_process(self->agc, input, self->mute < 0.75f);
      else
         {
         self->lrc = self->unp;
         self->agc->df = self->agc->red = self->agc->yellow = self->agc->green = 1.0f;
         }

      self->lc = self->lrc * self->lgain;
      self->rc = self->lrc * self->rgain;
      self->lcm = self->lc * self->mute;
      self->rcm = self->rc * self->mute;
      
      /* record peak levels */
      float l = fabsf(self->lrc);
      if (l > self->peak)
         self->peak = l;
      }
   else
      {
      self->unp = self->unpm = self->unpmdj;
      self->lc = self->rc = self->lrc = self->lcm = self->rcm = 0.0f;
      self->agc->df = self->agc->red = self->agc->yellow = self->agc->green = 1.0f;
      self->peak = peak_init;
      }
   }

static int mic_getpeak(struct mic *self)
   {
   int peakdb;
   
   peakdb = (int)level2db(self->peak);
   self->peak = peak_init;
   return (peakdb < 0) ? peakdb : 0;
   }

void mic_stats(char *key, struct mic *self)
   {
   fprintf(stdout, "%s=%d,%d,%d,%d\n", key, mic_getpeak(self),
                  (int)(log10f(self->agc->red) * -20.0f),
                  (int)(log10f(self->agc->yellow) * -20.0f),
                  (int)(log10f(self->agc->green) * -20.0f));
   }

struct mic *mic_init(int sample_rate)
   {
   struct mic *self;
   
   if (!(self = calloc(1, sizeof (struct mic))))
      {
      fprintf(stderr, "mic_init: malloc failure\n");
      return NULL;
      }
   
   self->sample_rate = (float)sample_rate;   
   self->pan = 50;
   self->complexity = 1;
   self->peak = peak_init;
   if (!(self->agc = agc_init(sample_rate, 0.01161f)))
      {
      fprintf(stderr, "mic_init: agc_init failed\n");
      free(self);
      return NULL;
      }
      
   calculate_gain_values(self);   
      
   return self;
   }
   
void mic_free(struct mic *self)
   {
   agc_free(self->agc);
   free(self);
   }
   
void mic_valueparse(struct mic *self, char *param)
   {
   char *save = NULL, *key, *value;

   key = strtok_r(param, "=", &save);
   value = strtok_r(NULL, "=", &save);  
   
   if (!strcmp(key, "complexity"))
      {
      self->complexity = (value[0] == '1') ? 1 : 0;
      calculate_gain_values(self);
      }
   else if (!strcmp(key, "active"))
      {
      self->active = (value[0] == '1') ? 1 : 0;
      }
   else if (!strcmp(key, "pan"))
      {
      self->pan = atoi(value);
      calculate_gain_values(self);
      }
   else if (!strcmp(key, "pan_active"))
      {
      self->pan_active = (value[0] == '1') ? 1 : 0;
      calculate_gain_values(self);
      }
   else if(!strcmp(key, "open"))
      {
      self->open = (value[0] == '1') ? 1 : 0;
      }
   else if(!strcmp(key, "invert"))
      {
      self->invert = (value[0] == '1') ? 1 : 0;
      calculate_gain_values(self);
      }
   else if(!strcmp(key, "indjmix"))
      {
      self->djmute = (value[0] == '1') ? 1.0f : 0.0f;
      }
   else
      {
      if (!strcmp(key, "gain"))
         {
         self->gain = atof(value);
         calculate_gain_values(self);
         }
      agc_valueparse(self->agc, key, value);
      }
   }

