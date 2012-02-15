/*
#   main.c: backend unificaction module.
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

#include <stdio.h>
#include <stdlib.h>
#include <locale.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>
#include "sig.h"
#include "mixer.h"
#include "sourceclient.h"
#include "main.h"

#define FALSE 0
#define TRUE (!FALSE)

struct globs g = {.main_timeout = -1};

static void alarm_handler(int sig)
    {
    if (g.app_shutdown)
       exit(5);

    if (!mixer_keepalive())
       g.app_shutdown = TRUE;

   /* One second grace to shut down naturally. */
   alarm(1);
   }

static void custom_jack_error_callback(const char *message)
   {
   fprintf(stderr, "jack error: %s\n", message);
   }

static void custom_jack_info_callback(const char *message)
   {
   fprintf(stderr, "jack info: %s\n", message);
   }

static void custom_jack_on_shutdown_callback()
   {
   g.app_shutdown = TRUE;
   }

static void cleanup_jack()
   {
   if (g.client)
      {
      jack_deactivate(g.client);
      jack_client_close(g.client);
      }
   }

static int main_process_audio(jack_nframes_t n_frames, void *arg)
   {
   return mixer_process_audio(n_frames, arg) || audio_feed_process_audio(n_frames, arg);
   }

int main(void)
   {
   char *buffer = NULL;
   size_t n = 5000;
   int keep_running = TRUE;

   /* Without these being set the backend will segfault. */
      {
      int o = FALSE;    /* Overwrite flag */
      if (setenv("session_type", "L0", o) ||
            setenv("client_id", "idjc_nofrontend", o) ||
            setenv("mic_qty", "4", o) ||
            setenv("num_streamers", "6", o) ||
            setenv("num_encoders", "6", o) ||
            setenv("num_recorders", "2", o) ||
            setenv("jack_parameter", "default", o) ||
            setenv("headless", "1", o) ||
            /* C locale required for . as radix character. */
            setenv("LC_ALL", "C", 1))
         {
         perror("main: failed to set environment variable");
         exit(5);
         }
      }

   setlocale(LC_ALL, getenv("LC_ALL"));
   if (atoi(getenv("headless")))
      signal(SIGALRM, SIG_IGN);
   else
      {
      g.main_timeout = 0;
      signal(SIGALRM, alarm_handler);
      }
   
   /* Signal handling. */
   sig_init();

   if ((g.client = jack_client_open(getenv("client_id"), JackUseExactName | JackServerName, NULL, getenv("jack_parameter"))) == 0)
      {
      fprintf(stderr, "main.c: jack_client_open failed");
      exit(5);
      }

   jack_set_error_function(custom_jack_error_callback);
   jack_set_info_function(custom_jack_info_callback);
   jack_on_shutdown(g.client, custom_jack_on_shutdown_callback, NULL);
   
   jack_set_process_callback(g.client, main_process_audio, NULL);

   /* Registration of JACK ports. */
   #define MK_AUDIO_INPUT(var, name) var = jack_port_register(g.client, name, JACK_DEFAULT_AUDIO_TYPE, JackPortIsInput, 0)
   #define MK_AUDIO_OUTPUT(var, name) var = jack_port_register(g.client, name, JACK_DEFAULT_AUDIO_TYPE, JackPortIsOutput, 0)
   
      {
      struct jack_ports *p = &g.port;

      /* Mixer ports. */
      MK_AUDIO_OUTPUT(p->dj_out_l, "dj_out_l");
      MK_AUDIO_OUTPUT(p->dj_out_r, "dj_out_r");
      MK_AUDIO_OUTPUT(p->dsp_out_l, "dsp_out_l");
      MK_AUDIO_OUTPUT(p->dsp_out_r, "dsp_out_r");
      MK_AUDIO_INPUT(p->dsp_in_l, "dsp_in_l");
      MK_AUDIO_INPUT(p->dsp_in_r, "dsp_in_r");
      MK_AUDIO_OUTPUT(p->str_out_l, "str_out_l");
      MK_AUDIO_OUTPUT(p->str_out_r, "str_out_r");
      MK_AUDIO_OUTPUT(p->voip_out_l, "voip_out_l");
      MK_AUDIO_OUTPUT(p->voip_out_r, "voip_out_r");
      MK_AUDIO_OUTPUT(p->voip_in_l, "voip_in_l");
      MK_AUDIO_OUTPUT(p->voip_in_r, "voip_in_r");
      /* Not really a mixer port but handled in the mixer code. */
      p->midi_port = jack_port_register(g.client, "midi_control", JACK_DEFAULT_MIDI_TYPE, JackPortIsInput, 0);

      /* Sourceclient ports. */
      MK_AUDIO_INPUT(p->output_in_l, "output_in_l");
      MK_AUDIO_INPUT(p->output_in_r, "output_in_r");
      }

   #undef MK_AUDIO_INPUT
   #undef MK_AUDIO_OUTPUT

   /* Submodule initialization. */
   mixer_init();
   sourceclient_init();

   if (jack_activate(g.client))
      {
      fprintf(stderr, "main.c: failed to activate JACK client.\n");
      jack_client_close(g.client);
      g.client = NULL;
      exit(5);
      }
   atexit(cleanup_jack);

   printf("idjc backend ready\n");
   fflush(stdout);

   while (keep_running && getline(&buffer, &n, stdin) > 0 && !g.app_shutdown)
      {
      /* Filter commands to submodules. */
      if (!strcmp(buffer, "mx\n"))
         keep_running = mixer_main();
      else
         {
         if (!strcmp(buffer, "sc\n"))
            keep_running = sourceclient_main();
         else
            {
            fprintf(stderr, "main.c: expected module name, got: %s", buffer);
            exit(5);
            }
         }
      }

   jack_deactivate(g.client);
   jack_client_close(g.client);
   g.client = NULL;

   alarm(0);
   
   if (buffer)
      free(buffer);

   return 0;
   }
