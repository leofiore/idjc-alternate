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
#include "sig.h"
#include "mixer.h"
#include "sourceclient.h"

#define FALSE 0
#define TRUE (!FALSE)

sig_atomic_t app_shutdown;
int main_timeout = -1;  /* Negative number means not active. */

static void alarm_handler(int sig)
    {
    if (app_shutdown)
       exit(5);

    if (!mixer_keepalive())
       app_shutdown = TRUE;

   /* One second grace to shut down naturally. */
   alarm(1);
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
            setenv("mx_client_id", "idjc-mx_nofrontend", o) ||
            setenv("sc_client_id", "idjc-sc_nofrontend", o) ||
            setenv("mx_mic_qty", "4", o) ||
            setenv("sc_num_streamers", "6", o) ||
            setenv("sc_num_encoders", "6", o) ||
            setenv("sc_num_recorders", "2", o) ||
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
      main_timeout = 0;
      signal(SIGALRM, alarm_handler);
      }
   
   /* Signal handling. */
   sig_init();

   /* Submodule initialization. */
   mixer_init();
   sourceclient_init();

   printf("idjc backend ready\n");
   fflush(stdout);

   while (keep_running && getline(&buffer, &n, stdin) > 0 && !app_shutdown)
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
      
   return 0;
   }
