/*
#   sigmask.c: global signal masking for pthreads + general handling
#   Copyright (C) 2011 Stephen Fairchild (s-fairchild@users.sourceforge.net)
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
#include <signal.h>

static sigset_t mask;
static int working;

static void interrupt_handler(int sig)
   {
   static int count = 0;
   int ec = (sig == SIGINT) ? 130 : 5;
   
   if (sig == SIGINT || sig == SIGTERM)
      {
      if (++count >= 1)
         exit(ec);
      }
   else
      exit(5);  // SIGHUP and whatever else
   }

#define A(s) && sigaddset(&mask, s)

void sigmask_init()
   {
   if (sigemptyset(&mask) A(SIGINT) A(SIGTERM) A(SIGHUP) A(SIGALRM) A(SIGSEGV))
      fprintf(stderr, "sigmask_init: mask creation failed\n");
   else
      {
      working = 1;
      signal(SIGINT, interrupt_handler);
      signal(SIGTERM, interrupt_handler);
      signal(SIGHUP, interrupt_handler);
      signal(SIGUSR1, SIG_IGN);
      signal(SIGUSR2, SIG_IGN);
      }
   }
   
#undef A  

void sigmask_perform()
   {
   if (working && pthread_sigmask(SIG_BLOCK, &mask, NULL))
      fprintf(stderr, "sigmask_perform: pthread_sigmask() failed\n");
   }
