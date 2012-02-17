/*
#   kvpparse.c: the mixer and server command parsing mechanism used by IDJC.
#   Copyright (C) 2005-2012 Stephen Fairchild (s-fairchild@users.sourceforge.net)
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

#include "gnusource.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "kvpparse.h"
#include "bsdcompat.h"

static char *buffer;

static void kvp_cleanup()
    {
    if (buffer)
        free(buffer);
    }

int kvp_parse(struct kvpdict *kvpdict, FILE *fp)
    {
    static size_t n = 5000;
    char *value;
    ssize_t rv;

    if (!buffer)
        {
        if (!(buffer = malloc(n)))
            {
            fprintf(stderr, "malloc failure\n");
            exit(5);
            }
        atexit(kvp_cleanup);
        } 

    while (rv = getline(&buffer, &n, fp), rv > 0 && strcmp(buffer, "end\n"))
        {
        /* the following function is fed a key value pair e.g. key=value */
        value = kvp_extract_value(buffer); /* key is truncated at the = */
        /* value = a pointer to a copy of the value part after the '=' allocated on the heap */
        if(!(kvp_apply_to_dict(kvpdict, buffer, value)))
            fprintf(stderr, "kvp_parse: %s=%s, key missing from dictionary\n", buffer, value);
        /* assuming the error message wasn't printed the associated pointer in the dictionary will have been updated */
        }

    if (!buffer)
        fprintf(stderr, "getline failed to allocate a buffer in function kvp_parse\n");
    return rv > 0;
    }
