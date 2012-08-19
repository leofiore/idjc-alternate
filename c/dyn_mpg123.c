/*
#   dyn_mpg123.c: dynamic linking for MPG123
#   Copyright (C) 2009 Stephen Fairchild (s-fairchild@users.sourceforge.net)
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

#ifdef DYN_MPG123

#include <stdio.h>
#include <stdlib.h>
#include <dlfcn.h>

#ifdef HAVE_MPG123_H
#include <mpg123.h>
#else
#include "mpg123.h"
#endif

#include "dyn_mpg123.h"


static void *handle;

static int (*open)(mpg123_handle *, const char *);
static mpg123_handle *(*new)(const char *, int *);
static void (*exit_)();
static int (*getformat)(mpg123_handle *, long *, int *, int *);
static void (*delete)(mpg123_handle *);
static int (*close)(mpg123_handle *);
static int (*format)(mpg123_handle *, long, int, int);
static off_t (*seek)(mpg123_handle *, off_t, int);
static int (*open_fd)(mpg123_handle *, int);
static int (*format_none)(mpg123_handle *);
static int (*param)(mpg123_handle *, enum mpg123_parms, long, double);
static int (*init)();
static int (*decode_frame)(mpg123_handle *, off_t *, unsigned char **, size_t *);

static void dyn_mpg123_close()
    {
    dlclose(handle);
    }

int dyn_mpg123_init()
    {
    char *libname = getenv("libmpg123_filename");

    fprintf(stderr, "dyn_mpg123_init: using library '%s'\n", libname);
    if (libname == NULL || libname[0] == '\0' || !(handle = dlopen(libname, RTLD_LAZY)))
        {
        fprintf(stderr, "dyn_mpg123_init: failed to open library\n");
        return 0;
        }

    if (!(      (open = dlsym(handle, "mpg123_open")) &&
                (new = dlsym(handle, "mpg123_new")) &&
                (exit_ = dlsym(handle, "mpg123_exit")) &&
                (getformat = dlsym(handle, "mpg123_getformat")) &&
                (delete = dlsym(handle, "mpg123_delete")) &&
                (close = dlsym(handle, "mpg123_close")) &&
                (format = dlsym(handle, "mpg123_format")) &&
                (seek = dlsym(handle, "mpg123_seek")) &&
                (open_fd = dlsym(handle, "mpg123_open_fd")) &&
                (format_none = dlsym(handle, "mpg123_format_none")) &&
                (param = dlsym(handle, "mpg123_param")) &&
                (init = dlsym(handle, "mpg123_init")) &&
                (decode_frame = dlsym(handle, "mpg123_decode_frame"))))
        {
        fprintf(stderr, "dyn_mpg123_init: missing symbol in %s: %s\n", libname, dlerror());
        return 0;
        }

    atexit(dyn_mpg123_close);
    return 1;
    }

int mpg123_open(mpg123_handle *mh, const char *path)
    {
    return open(mh, path);
    }

mpg123_handle *mpg123_new(const char* decoder, int *error)
    {
    return new(decoder, error);
    }

void mpg123_exit()
    {
    exit_();
    }
    
int mpg123_getformat(mpg123_handle *mh, long *rate, int *channels, int *encoding)
    {
    return getformat(mh, rate, channels, encoding);
    }

void mpg123_delete(mpg123_handle *mh)
    {
    delete(mh);
    }

int mpg123_close(mpg123_handle *mh)
    {
    return close(mh);
    }

int mpg123_format(mpg123_handle *mh, long rate, int channels, int encodings)
    {
    return format(mh, rate, channels, encodings);
    }

off_t mpg123_seek(mpg123_handle *mh, off_t sampleoff, int whence)
    {
    return seek(mh, sampleoff, whence);
    }

int mpg123_open_fd(mpg123_handle *mh, int fd)
    {
    return open_fd(mh, fd);
    }

int mpg123_format_none(mpg123_handle *mh)
    {
    return format_none(mh);
    }
    
int mpg123_param(mpg123_handle *mh, enum mpg123_parms type, long value, double fvalue)
    {
    return param(mh, type, value, fvalue);
    }

int mpg123_init()
    {
    return init();
    }

int mpg123_decode_frame(mpg123_handle *mh, off_t *num, unsigned char **audio, size_t *bytes)
    {
    return decode_frame(mh, num, audio, bytes);
    }
    
#endif /* DYN_MPG123 */
