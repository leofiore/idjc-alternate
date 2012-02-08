/*
#   dyn_mad.c: dynamic linking for libmad
#   Copyright (C) 2009-2012 Stephen Fairchild (s-fairchild@users.sourceforge.net)
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

#ifdef DYN_MAD

#include <stdio.h>
#include <stdlib.h>
#include <dlfcn.h>
#include "dyn_mad.h"
#include "mad.h"

static void *handle;

static int (*frame_decode)(struct mad_frame *, struct mad_stream *);
static void (*stream_buffer)(struct mad_stream *, unsigned char const *, unsigned long);
static void (*stream_finish)(struct mad_stream *);
static void (*frame_finish)(struct mad_frame *);
static void (*synth_init)(struct mad_synth *);
static void (*stream_init)(struct mad_stream *);
static void (*frame_init)(struct mad_frame *);
static void (*synth_frame)(struct mad_synth *, struct mad_frame const *);

static void dyn_mad_close()
   {
   dlclose(handle);
   }

static void dyn_mad_init()
   {
   char *error;

   if (!((handle = dlopen("libmad.so", RTLD_LAZY)) || (handle = dlopen("libmad.dylib", RTLD_LAZY))))
      {
      fprintf(stderr, "failed to locate libmad dynamic library\n");
      return;
      }
   dlerror();

   if (!(   (frame_decode = dlsym(handle, "mad_frame_decode")) &&
            (stream_buffer = dlsym(handle, "mad_stream_buffer")) &&
            (stream_finish = dlsym(handle, "mad_stream_finish")) &&
            (frame_finish = dlsym(handle, "mad_frame_finish")) &&
            (synth_init = dlsym(handle, "mad_synth_init")) &&
            (stream_init = dlsym(handle, "mad_stream_init")) &&
            (frame_init = dlsym(handle, "mad_frame_init")) &&
            (synth_frame = dlsym(handle, "mad_synth_frame"))))
      {
      fprintf(stderr, "missing symbols in libmad");
      } 

   if ((error = dlerror()))
      {
      fprintf(stderr, "dlsym failed with: %s\n", error);
      dlclose(handle);
      handle = NULL;
      }

   atexit(dyn_mad_close);
   }
   
int dyn_mad_onceinit()
   {
   static pthread_once_t once_control = PTHREAD_ONCE_INIT;
   
   pthread_once(&once_control, dyn_mad_init);
   return handle != NULL;
   }

int mad_frame_decode(struct mad_frame *frame, struct mad_stream *stream)
   {
   return frame_decode(frame, stream);
   }

void mad_stream_buffer(struct mad_stream *stream, unsigned char const *buffer, unsigned long length)
   {
   stream_buffer(stream, buffer, length);
   }

void mad_stream_finish(struct mad_stream *stream)
   {
   stream_finish(stream);
   }

void mad_frame_finish(struct mad_frame *frame)
   {
   frame_finish(frame);
   }

void mad_synth_init(struct mad_synth *synth)
   {
   synth_init(synth);
   }

void mad_stream_init(struct mad_stream *stream)
   {
   stream_init(stream);
   }

void mad_frame_init(struct mad_frame *frame)
   {
   frame_init(frame);
   }

void mad_synth_frame(struct mad_synth *synth, struct mad_frame const *frame)
   {
   synth_frame(synth, frame);
   }

#endif /* DYN_LAME */
