/*
#   watchdog.c: keeps a eye on the threads of the streaming module of idjc
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
#include <unistd.h>
#include <time.h>
#include "sourceclient.h"

#define NO_WATCHDOG

#ifndef NO_WATCHDOG

static void watchdog_check(struct watchdog_info *wi, char *device, int devnum)
   {
   if (wi->tick == wi->oldtick)
      fprintf(stderr, "watchdog_check: device %s%d frozen\n", device, devnum);
   wi->oldtick = wi->tick;
   }

static void *watchdog_main(void *args)
   {
   struct watchdog *self = args;
   struct threads_info *ti = self->ti;
   struct timespec ms100 = { 0, 100000000 };
   int i, infotick = 0;
   
   while (!self->exit)
      {
      if (!(infotick++ & 0xF))
         {
         for (i = 0; i < ti->n_encoders; i++)
            watchdog_check(&ti->encoder[i]->watchdog_info, "encoder", i);
         for (i = 0; i < ti->n_streamers; i++)
            watchdog_check(&ti->streamer[i]->watchdog_info, "streamer", i);
         for (i = 0; i < ti->n_recorders; i++)
            watchdog_check(&ti->recorder[i]->watchdog_info, "recorder", i);
         }
      nanosleep(&ms100, NULL);
      }
   return NULL;
   }

#endif

struct watchdog *watchdog_init(struct threads_info *ti)
   {
   struct watchdog *self = (void *)1;
   
#ifndef NO_WATCHDOG
   if (!(self = calloc(1, sizeof (struct watchdog))))
      {
      fprintf(stderr, "watchdog_init: malloc failure\n");
      return NULL;
      }
   self->ti = ti;
   if ((pthread_create(&self->thread_h, NULL, watchdog_main, self)))
      {
      fprintf(stderr, "watchdog_init: thread creation failed\n");
      return NULL;
      }
   fprintf(stderr, "watchdog_init: watchdog thread created\n");
#endif
   return self;
   }

void watchdog_destroy(struct watchdog *self)
   {
#ifndef NO_WATCHDOG
   self->exit = TRUE;
   pthread_join(self->thread_h, NULL);
   free(self);
   fprintf(stderr, "watchdog_destroy: watchdog thread terminated\n");
#endif
   }
