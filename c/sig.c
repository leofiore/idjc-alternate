/*
#   sig.c: signal masking for pthreads + general handling
#   Copyright (C) 2011-2012 Stephen Fairchild (s-fairchild@users.sourceforge.net)
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
#include <signal.h>

static sigset_t mask;
static int working;
static volatile sig_atomic_t sigusr1count, sigusr1oldcount;

static void do_exit(int sig)
    {
    exit(5);
    }

static void usr1_handler(int sig)
    {
    ++sigusr1count;
    signal(sig, usr1_handler);
    }

#define A(s) && sigaddset(&mask, s)

void sig_init()
    {
    if (sigemptyset(&mask) A(SIGINT) A(SIGTERM) A(SIGHUP) A(SIGALRM) A(SIGSEGV) A(SIGUSR1) A(SIGUSR2))
        fprintf(stderr, "sigmask_init: mask creation failed\n");
    else
        {
        working = 1;
        signal(SIGINT, do_exit);
        signal(SIGTERM, do_exit);
        signal(SIGHUP, do_exit);
        if (!strcmp(getenv("session_type"), "L1"))
            signal(SIGUSR1, usr1_handler);
        else
            signal(SIGUSR1, SIG_IGN);
        signal(SIGUSR2, SIG_IGN);
        }
    }

#undef A  

void sig_mask_thread()
    {
    if (working && pthread_sigmask(SIG_BLOCK, &mask, NULL))
        fprintf(stderr, "sig_mask_thread: pthread_sigmask() failed\n");
    }

int sig_recent_usr1()
    {
    if (sigusr1count != sigusr1oldcount)
        {
        sigusr1oldcount = sigusr1count;
        return 1;
        }
    return 0;
    }
