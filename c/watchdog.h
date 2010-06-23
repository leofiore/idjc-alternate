/*
#   watchdog.h: keeps a eye on the threads of the streaming module of idjc
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

#ifndef WATCHDOG_H
#define WATCHDOG_H

#include <pthread.h>
#include "sourceclient.h"

struct watchdog
   {
   pthread_t thread_h;
   struct threads_info *ti;
   int exit;
   };
   
struct watchdog_info
   {
   int tick;
   int oldtick;
   };

struct watchdog *watchdog_init(struct threads_info *ti);
void watchdog_destroy(struct watchdog *self);

#endif /* WATCHDOG_H */
