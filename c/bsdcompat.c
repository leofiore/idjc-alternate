/*
#   bsdcompat.c: library functions that are missing from BSD
#   Copyright (C) 2005-2007 Stephen Fairchild (s-fairchild@users.sourceforge.net)
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

#include "bsdcompat.h"

#ifdef USE_BSD_COMPAT

#include <limits.h>
#include <stdlib.h>
#include <math.h>
#include <string.h>
#include <errno.h>

float bsd_pow10f(float x)
    {
    return powf(10.f, x);
    }

char *bsd_strndup(const char *s, size_t n)
    {
    size_t l;
    char *r, *p;

    if ((l = strlen(s)) < n)
        n = l;

    if ((p = r = malloc(n + 1)) == NULL)
        errno = ENOMEM;
    else
        {
        while (n--)
            *p++ = *s++;
        *p = '\0';
        }

    return r;
    }

ssize_t bsd_getline(char **lineptr, size_t *n, FILE *stream)
    {
    const size_t growby = 64;
    ssize_t i = 0;
    int eol = 0, c;

    if (lineptr == NULL || n == NULL || fileno(stream) == -1)
        {
        errno = EINVAL;
        return -1;
        }

    if (*lineptr == NULL)
        *n = 0;

    for (;;)
        {
        if (i == *n)
            if ((*lineptr = realloc(*lineptr, *n += growby + i / 8)) == NULL)
                {
                perror("getline: malloc failure\n");
                *n = 0;
                return -1;
                }

        if (eol)
            break;

        c = fgetc(stream);
        if (feof(stream) || ferror(stream))
            eol = 1;
        else
            {
            (*lineptr)[i++] = c;
            if (c == '\n')
                eol = 1;
            }
        }

    (*lineptr)[i] = '\0';

    if (i == 0)
        fprintf(stderr, "line length was zero\n");

    return i;
    }

char *bsd_canonicalize_file_name(const char *path)
    {
    return realpath(path, NULL);
    }

#endif /* USE_BSD_COMPAT */
