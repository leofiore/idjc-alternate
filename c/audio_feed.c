/*
#   audiofeed.c: jack connectivity for the streaming module of idjc
#   Copyright (C) 2007-2010 Stephen Fairchild (s-fairchild@users.sourceforge.net)
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

#include "../config.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <jack/jack.h>
#include <jack/ringbuffer.h>
#include "sourceclient.h"

typedef jack_default_audio_sample_t sample_t;

static int jack_process_callback(jack_nframes_t n_frames, void *arg)
   {
   struct audio_feed *self = arg;
   struct threads_info *ti = self->threads_info;
   struct encoder *e;
   struct recorder *r;
   sample_t *input_port_buffer[2];
   int i;
   
   input_port_buffer[0] = jack_port_get_buffer(self->input_port[0], n_frames);
   input_port_buffer[1] = jack_port_get_buffer(self->input_port[1], n_frames);
   
   /* feed pcm audio data to all encoders that request it */
   for (i = 0; i < ti->n_encoders; i++)
      {
      e = ti->encoder[i];
      switch (e->jack_dataflow_control)
         {
         case JD_OFF:
            break;
         case JD_ON:
            if (jack_ringbuffer_write_space(e->input_rb[1]) >= n_frames * sizeof (sample_t))
               {
               jack_ringbuffer_write(e->input_rb[0], (char *)input_port_buffer[0], n_frames * sizeof (sample_t));
               jack_ringbuffer_write(e->input_rb[1], (char *)input_port_buffer[1], n_frames * sizeof (sample_t));
               }
            else
               /* normally this happens when the CPU is overloaded */
               e->performance_warning_indicator = PW_AUDIO_DATA_DROPPED;
            break;
         case JD_FLUSH:
            jack_ringbuffer_reset(e->input_rb[0]);
            jack_ringbuffer_reset(e->input_rb[1]);
            e->jack_dataflow_control = JD_OFF;
            break;
         default:
            fprintf(stderr, "jack_process_callback: unhandled jack_dataflow_control parameter\n");
         }
      }
      
   for (i = 0; i < ti->n_recorders; i++)
      {
      r = ti->recorder[i];
      switch (r->jack_dataflow_control)
         {
         case JD_OFF:
            break;
         case JD_ON:
            if (jack_ringbuffer_write_space(r->input_rb[1]) >= n_frames * sizeof (sample_t))
               {
               jack_ringbuffer_write(r->input_rb[0], (char *)input_port_buffer[0], n_frames * sizeof (sample_t));
               jack_ringbuffer_write(r->input_rb[1], (char *)input_port_buffer[1], n_frames * sizeof (sample_t));
               }
            else
               /* normally this happens when the CPU is overloaded */
               r->performance_warning_indicator = PW_AUDIO_DATA_DROPPED;
            break;
         case JD_FLUSH:
            jack_ringbuffer_reset(r->input_rb[0]);
            jack_ringbuffer_reset(r->input_rb[1]);
            r->jack_dataflow_control = JD_OFF;
            break;
         default:
            fprintf(stderr, "jack_process_callback: unhandled jack_dataflow_control parameter\n");
         }   
      }
     
   return 0;
   }

static void custom_jack_error_callback(const char *message)
   {
   fprintf(stderr, "jack error: %s\n", message);
   }

static void custom_jack_info_callback(const char *message)
   {
   fprintf(stderr, "jack info: %s\n", message);
   }

static void jack_shutdown_callback()
   {
   fprintf(stderr, "jack_shutdown_callback: jack was shut down\n");
   }

int audio_feed_jack_samplerate_request(struct threads_info *ti, struct universal_vars *uv, void *param)
   {
   printf("idjcsc: sample_rate=%ld\n", (long)ti->audio_feed->sample_rate);
   fflush(stdout);
   if (ferror(stdout))
      return FAILED;
   return SUCCEEDED;
   }

struct audio_feed *audio_feed_init(struct threads_info *ti)
   {
   struct audio_feed *self;
   size_t l;
   char *sc_client_name, *mx_client_name;

   if (!(self = calloc(1, sizeof (struct audio_feed))))
      {
      fprintf(stderr, "audio_feed_init: malloc failure\n");
      return NULL;
      }
      
   mx_client_name = getenv("mx_client_id");
   sc_client_name = getenv("sc_client_id");
   l = strlen(sc_client_name) + 11;
   self->mx_port_l = malloc(l);
   self->mx_port_r = malloc(l);
   --l;
   self->sc_port_l = malloc(l);
   self->sc_port_r = malloc(l);
   ++l;
   
   if (self->mx_port_l && self->mx_port_r && self->sc_port_l && self->sc_port_r)
      {
      snprintf(self->mx_port_l, l, "%s:%s", mx_client_name, "str_out_l");
      snprintf(self->mx_port_r, l, "%s:%s", mx_client_name, "str_out_r");
      --l;
      snprintf(self->sc_port_l, l, "%s:%s", sc_client_name, "str_in_l");
      snprintf(self->sc_port_r, l, "%s:%s", sc_client_name, "str_in_r");
      }
   else
      {
      fprintf(stderr, "malloc failure\n");
      return NULL;
      }
      
   if (!(self->jack_client_name = strdup(sc_client_name)))
      {
      fprintf(stderr, "audio_feed_init: malloc failure\n");
      return NULL;
      }
   self->threads_info = ti;
   jack_set_error_function(custom_jack_error_callback);
#ifdef HAVE_JACK_SET_INFO_FUNCTION
   jack_set_info_function(custom_jack_info_callback);
#endif

   if (!(self->jack_h = jack_client_open(self->jack_client_name, JackUseExactName | JackServerName, NULL, getenv("IDJC_JACK_SERVER"))))
      {
      fprintf(stderr, "audio_feed_init: creation of a new jack client failed\nthis could be due to jackd having not been started or another instance of idjcsourceclient is currently running\n");
      return NULL;
      }
   jack_set_process_callback(self->jack_h, jack_process_callback, self);
   jack_on_shutdown(self->jack_h, jack_shutdown_callback, NULL);
   
   self->input_port[0] = jack_port_register(self->jack_h, "str_in_l", JACK_DEFAULT_AUDIO_TYPE, JackPortIsInput, 0);
   self->input_port[1] = jack_port_register(self->jack_h, "str_in_r", JACK_DEFAULT_AUDIO_TYPE, JackPortIsInput, 0);
   
   self->sample_rate = jack_get_sample_rate(self->jack_h);
   if(jack_activate (self->jack_h))
      {
      fprintf(stderr, "audio_feed_init: could not activate jack client\n");
      return NULL;
      }
   jack_connect(self->jack_h, self->mx_port_l, self->sc_port_l);
   jack_connect(self->jack_h, self->mx_port_r, self->sc_port_r);
   return self;
   }

void audio_feed_destroy(struct audio_feed *self)
   {
   jack_deactivate(self->jack_h);
   jack_client_close(self->jack_h);
   self->threads_info->audio_feed = NULL;
   free(self->jack_client_name);
   free(self->mx_port_l);
   free(self->mx_port_r);
   free(self->sc_port_l);
   free(self->mx_port_r);
   free(self);
   }
