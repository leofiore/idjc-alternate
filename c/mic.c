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

static void mic_process_start(struct mic *self, jack_nframes_t nframes)
   {
   self->nframes = nframes;
   self->jadp = jack_port_get_buffer(self->jack_port, nframes);
   }

void mic_process_start_all(struct mic **mics, jack_nframes_t nframes)
   {
   while (*mics)   
      mic_process_start(*mics++, nframes);
   }

static void mic_process(struct mic *self)
   {
   float input = *self->jadp++;

   if (self->mode)
      {
      if (self->open && self->mute < 0.999999f)
         self->mute += (1.0f - self->mute) * 26.46f / self->sample_rate;
      else if (!self->open && self->mute > 0.0000004f)
         self->mute -= self->mute * 12.348f / self->sample_rate;
      else
         self->mute = self->open ? 1.0f : 0.0f;
         
      if (isunordered(input, input))
         input = 0.0f;
        
      self->unp = input * self->mgain;
      self->unpm = self->unp * self->mute;
      self->unpmdj = self->unpm * self->djmute;

      if (self->mode == 2)
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

float mic_process_all(struct mic **mics)
   {
   float df, agcdf;   
      
   for (df = 1.0f; *mics; mics++)
      {
      mic_process(*mics);
      df = (df > (agcdf = (*mics)->agc->df)) ? agcdf : df;
      }
      
   return df;
   }

static int mic_getpeak(struct mic *self)
   {
   int peakdb;
   
   peakdb = (int)level2db(self->peak);
   self->peak = peak_init;
   return (peakdb < 0) ? peakdb : 0;
   }

static void mic_stats(struct mic *self)
   {
   fprintf(stdout, "mic_%d_levels=%d,%d,%d,%d\n", self->id, mic_getpeak(self),
                  (int)(log10f(self->agc->red) * -20.0f),
                  (int)(log10f(self->agc->yellow) * -20.0f),
                  (int)(log10f(self->agc->green) * -20.0f));
   }

void mic_stats_all(struct mic **mics)
   {
   while (*mics)
      mic_stats(*mics++);
   }

static struct mic *mic_init(jack_client_t *client, int sample_rate, int id)
   {
   struct mic *self;
   char port_name[10];
   
   if (!(self = calloc(1, sizeof (struct mic))))
      {
      fprintf(stderr, "mic_init: malloc failure\n");
      return NULL;
      }

   self->id = id;
   self->sample_rate = (float)sample_rate;   
   self->pan = 50;
   self->mode = 2;
   self->peak = peak_init;
   if (!(self->agc = agc_init(sample_rate, 0.01161f)))
      {
      fprintf(stderr, "mic_init: agc_init failed\n");
      free(self);
      return NULL;
      }
   snprintf(port_name, 10, "mic_in_%d", id);  
   self->jack_port = jack_port_register(client, port_name,
                     JACK_DEFAULT_AUDIO_TYPE, JackPortIsInput, 0); 
   calculate_gain_values(self);   
      
   return self;
   }
   
struct mic **mic_init_all(int n_mics, jack_client_t *client)
   {
   struct mic **mics;
   int i, sr;
   /* used to map suitable port names from the audio back-end as default connection targets */
   const char **defaults, **dp;
      
   if (!(mics = calloc(n_mics + 1, sizeof (struct mic *))))
      {
      fprintf(stderr, "malloc failure\n");
      exit(5);
      }
   
   sr = jack_get_sample_rate(client);
   defaults = dp = jack_get_ports(client, NULL, NULL, JackPortIsPhysical | JackPortIsOutput);
   
   for (i = 0; i < n_mics; i++)
      {
      mics[i] = mic_init(client, sr, i + 1);
      if (!mics[i])
         {
         fprintf(stderr, "mic_init failed\n");
         exit(5);
         }
      mics[i]->default_mapped_port_name = (dp && *dp) ? strdup(*dp++) : NULL;
      }
   if (defaults)
      jack_free(defaults);
   return mics;
   }

static void mic_free(struct mic *self)
   {
      
   agc_free(self->agc);
   self->agc = NULL;
   if (self->default_mapped_port_name)
      {
      free(self->default_mapped_port_name);
      self->default_mapped_port_name = NULL;
      } 
   free(self);
   }
   
void mic_free_all(struct mic **mics)
   {
   struct mic **mp = mics;   
      
   while (*mp)
      {
      mic_free(*mp);
      *mp++ = NULL;
      }
   free(mics);
   }
   
void mic_valueparse(struct mic *self, char *param)
   {
   char *save = NULL, *key, *value;

   key = strtok_r(param, "=", &save);
   value = strtok_r(NULL, "=", &save);  
   
   if (!strcmp(key, "mode"))
      {
      self->mode = value[0] - '0';
      calculate_gain_values(self);
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
