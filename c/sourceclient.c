/*
#   sourceclient.c: the streaming module of idjc
#   Copyright (C) 2007 Stephen Fairchild (s-fairchild@users.sourceforge.net)
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
#include <locale.h>
#include <unistd.h>
#include <jack/jack.h>
#include <jack/ringbuffer.h>
#include <signal.h>
#include "sourceclient.h"
#include "kvpparse.h"
#include "live_ogg_encoder.h"

int keepalive = FALSE;
int timeout_duration = 15;
int debugmode = FALSE;

static int threads_up;

static int threads_init(struct threads_info *ti, struct universal_vars *uv, void *other)
   {
   struct threads_vars *tv = other;
   int i;
   
   ti->n_encoders = atoi(tv->num_encoders);
   ti->n_streamers = atoi(tv->num_streamers);
   ti->n_recorders = atoi(tv->num_recorders);
   ti->encoder = calloc(ti->n_encoders, sizeof (struct encoder *));
   ti->streamer = calloc(ti->n_streamers, sizeof (struct streamer *));
   ti->recorder = calloc(ti->n_recorders, sizeof (struct recorder *));
   if (!(ti->encoder && ti->streamer && ti->recorder))
      {
      fprintf(stderr, "threads_init: malloc failure\n");
      return FAILED;
      }
   for (i = 0; i < ti->n_encoders; i++)
      if (!(ti->encoder[i] = encoder_init(ti, i)))
         {
         fprintf(stderr, "threads_init: encoder initialisation failed\n");
         return FAILED;
         }
   for (i = 0; i < ti->n_streamers; i++)
      if (!(ti->streamer[i] = streamer_init(ti, i)))
         {
         fprintf(stderr, "threads_init: streamer initialisation failed\n");
         return FAILED;
         }
   for (i = 0; i < ti->n_recorders; i++)
      if (!(ti->recorder[i] = recorder_init(ti, i)))
         {
         fprintf(stderr, "threads_init: recorder initialisation failed\n");
         return FAILED;
         }
   if (!(ti->audio_feed = audio_feed_init(ti)))
      {
      fprintf(stderr, "threads_init: audio feed initialisation failed\n");
      return FAILED;
      }
   if (!(ti->watchdog = watchdog_init(ti)))
      {
      fprintf(stderr, "threads_init: failed to start watchdog\n");
      return FAILED;
      }
   fprintf(stderr, "started %d encoders, %d streamers, %d recorders\n", ti->n_encoders, ti->n_streamers, ti->n_recorders);
   threads_up = TRUE;
   return SUCCEEDED;
   }

static void threads_shutdown(struct threads_info *ti)
   {
   int i;
   
   if (threads_up)
      {
      fprintf(stderr, "threads_shutdown commencing\n");
      watchdog_destroy(ti->watchdog);
      audio_feed_destroy(ti->audio_feed);
      for (i = 0; i < ti->n_recorders; i++)
         recorder_destroy(ti->recorder[i]);
      for (i = 0; i < ti->n_streamers; i++)
         streamer_destroy(ti->streamer[i]);
      for (i = 0; i < ti->n_encoders; i++)
         encoder_destroy(ti->encoder[i]);
      free(ti->recorder);
      free(ti->streamer);
      free(ti->encoder);
      }
   fprintf(stderr, "threads_shutdown finished\n");
   }

static int get_report(struct threads_info *ti, struct universal_vars *uv, void *other)
   {
   if (!strcmp(uv->dev_type, "streamer"))
      {
      if (uv->tab >= 0 && uv->tab < ti->n_streamers)
         return streamer_make_report(ti->streamer[uv->tab]);
      fprintf(stderr, "get_report: streamer %s does not exist\n", uv->tab_id);
      return FAILED;
      }
   if (!strcmp(uv->dev_type, "recorder"))
      {
      if (uv->tab >= 0 && uv->tab < ti->n_recorders)
         return recorder_make_report(ti->recorder[uv->tab]);
      fprintf(stderr, "get_report: recorder %s does not exist\n", uv->tab_id); 
      return FAILED;
      }
   if (!strcmp(uv->dev_type, "encoder"))
      return FAILED;
   fprintf(stderr, "get_report: unhandled dev_type %s\n", uv->dev_type);
   return FAILED;
   }

static int debug_command(struct threads_info *ti, struct universal_vars *uv, void *other)
   {
   struct debug_vars *dv = other;

   if (!(strcmp(uv->command, "keep_alive")))
      {
      keepalive = TRUE;
      while (keepalive == TRUE)
         sleep(1);
      return SUCCEEDED;
      }
   if (!(strcmp(uv->command, "debug")))
      {
      debugmode = TRUE;
      return SUCCEEDED;
      }
   if (!(strcmp(uv->command, "nodebug")))
      {
      debugmode = FALSE;
      return SUCCEEDED;
      }
   if (!(strcmp(uv->command, "set_timeout")))
      {
      timeout_duration = atoi(dv->timeout_duration);
      alarm(timeout_duration);
      return SUCCEEDED;
      }
   return FAILED;
   }

static int command_parse(struct commandmap *map, struct threads_info *ti, struct universal_vars *uv)
   {
   for (; map->key; map++)
      if (!(strcmp(uv->command, map->key)))
         {
         if (uv->tab_id)
            uv->tab = atoi(uv->tab_id);
         return map->function(ti, uv, map->other_parameter);
         }
   fprintf(stderr, "command_parse: unhandled command %s\n", uv->command);
   return FAILED;
   }

void comms_send(char *message)
   {
   if (debugmode)
      fprintf(stdout, "%s\n", message);
   else
      fprintf(stdout, "idjcsc: %s\n", message);
   fflush(stdout);
   }

int main()
   {
   /* declaration of the variables to capture incoming communications */
   static struct threads_info ti;
   static struct threads_vars tv;
   static struct encoder_vars ev;
   static struct streamer_vars sv;
   static struct recorder_vars rv;
   static struct universal_vars uv;
   static struct debug_vars dv;

   static struct kvpdict kvpdict[] = {
      { "encoders",         &tv.num_encoders },         /* threads_info */
      { "streamers",        &tv.num_streamers },
      { "recorders",        &tv.num_recorders },
      { "encode_source",    &ev.encode_source },        /* encoder_vars */
      { "sample_rate",      &ev.sample_rate },
      { "resample_quality", &ev.resample_quality },
      { "format",           &ev.format },
      { "subformat",        &ev.subformat },
      { "bit_rate",         &ev.bit_rate },
      { "bit_rate_min",     &ev.bit_rate_min },
      { "bit_rate_max",     &ev.bit_rate_max },
      { "bit_width",        &ev.bit_width },
      { "stereo",           &ev.stereo },
      { "use_metadata",     &ev.use_metadata },
      { "encode_quality",   &ev.encode_quality },
      { "speex_mode",       &ev.speex_mode },
      { "speex_quality",    &ev.speex_quality },
      { "speex_complexity", &ev.speex_complexity },
      { "filename",         &ev.filename },
      { "offset",           &ev.offset },
      { "metaformat",       &ev.metaformat },
      { "metaformat_mp3",   &ev.metaformat_mp3 },
      { "artist",           &ev.artist },
      { "title",            &ev.title },
      { "album",            &ev.album },
      { "artist_title_lat1", &ev.artist_title_lat1 },
      { "freeformat_mp3",   &ev.freeformat_mp3 },
      { "stream_source",    &sv.stream_source },        /* streamer_vars */
      { "server_type",      &sv.server_type },
      { "host",             &sv.host },
      { "port",             &sv.port },
      { "mount",            &sv.mount },
      { "login",            &sv.login },
      { "password",         &sv.password },
      { "dj_name",          &sv.dj_name },
      { "listen_url",       &sv.listen_url },
      { "description",      &sv.description },
      { "genre",            &sv.genre },
      { "irc",              &sv.irc },
      { "aim",              &sv.aim },
      { "icq",              &sv.icq },
      { "make_public",      &sv.make_public },
      { "record_source",    &rv.record_source },        /* recorder_vars */
      { "record_folder",    &rv.record_folder },
      { "pause_button",     &rv.pause_button },
      { "auto_pause_button",&rv.auto_pause_button },
      { "timeout_duration", &dv.timeout_duration },
      { "command",  &uv.command},
      { "dev_type", &uv.dev_type},
      { "tab_id",   &uv.tab_id},
      { NULL } };

   static struct commandmap commandmap[] = {
      { "threads_init", threads_init, &tv },
      { "jack_samplerate_request", audio_feed_jack_samplerate_request, NULL },
      { "encoder_lame_availability", encoder_init_lame, NULL},
      { "get_report", get_report, NULL },
      { "encoder_start", encoder_start, &ev },
      { "encoder_stop", encoder_stop, NULL },
      { "encoder_update", encoder_update, &ev },
      { "test_ogg_values", live_ogg_test_values, &ev },
      { "new_metadata", encoder_new_metadata, &ev },
      { "new_metaformat", encoder_new_metaformat, &ev },
      { "recorder_start", recorder_start, &rv },
      { "recorder_stop", recorder_stop, NULL },
      { "recorder_pause", recorder_pause, &rv },
      { "recorder_unpause", recorder_unpause, &rv },
      { "server_connect", streamer_connect, &sv },
      { "server_disconnect", streamer_disconnect, NULL },
      { "keep_alive", debug_command, NULL },
      { "debug", debug_command, NULL },
      { "nodebug", debug_command, NULL },
      { "set_timeout", debug_command, &dv },
      { NULL } }; 

   setenv("LC_ALL", "C", 1);
   setlocale(LC_ALL, "C");

   comms_send("succeeded");
   srand(time(NULL));
   while (kvp_parse(kvpdict, stdin) || debugmode)
      {
      if (uv.command && command_parse(commandmap, &ti, &uv))
         comms_send("succeeded");
      else
         {
         fprintf(stderr, "command failed for command: %s\n", uv.command);
         comms_send("failed");
         }
      if (uv.command)
         {
         free(uv.command);
         uv.command = NULL;
         }
      }
      
   threads_shutdown(&ti);
   kvp_free_dict(kvpdict);
   return 0;
   }
