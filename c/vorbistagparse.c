/*
#   vorbistagparse.c: parse vorbis tags 
#   Copyright (C) 2013 Stephen Fairchild (s-fairchild@users.sourceforge.net)
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
#include <stdint.h>
#include <string.h>
#include <ctype.h>
#include "vorbistagparse.h"

/* READINT: read little endian uint32_t value pointed to by p and advance p */
#define GET(p, ind, shift)  ((uint32_t)((unsigned const char *)p)[ind] << shift)
#define READINT(p)          (p += 4, GET(p, -1, 24) | GET(p, -2, 16) | \
                                    GET(p, -3, 8) | GET(p, -4, 0))

struct vtag {
    GHashTable *hash_table; /* table of g_slists of key=value pairs */
    char *vendor_string;
};

static int
key_valid(char const *key, size_t n)
    {
    while (n--)
        if (*key < 0x20 || *key > 0x7D || *key == '=')
            return 0;
    return !0;
    }

static char *strlwr(char *s)
    {
    if (s == NULL)
        return NULL;

    for (char *p = s; *p; ++p)
        *p = tolower(*p);
    return s;
    }

static enum vtag_error
parse(struct vtag *s, char const * const data, size_t bytes)
    {
    char const *p = data, *end = p + bytes;
    uint32_t len, to_do;
    int const min_vorbis_tag_size = 8;

    if (bytes < min_vorbis_tag_size)
        return VE_CROPPED;
    
    len = READINT(p);
    if (p + len + 4 > end)
        return VE_CROPPED;
    if (!(s->vendor_string = strndup(p, len)))
        return VE_ALLOCATION;
    p += len;

    to_do = READINT(p);

    while (to_do--) {
        if (p + 4 > end)
            return VE_CROPPED;
        
        len = READINT(p);
        if (p + len > end)
            return VE_CROPPED;
            
        switch (len) {
            case 0:
            case 1:
            case 2:
                return VE_SHORT_COMMENT;
            default:
                {
                char const * const sep = memchr(p + 1, '=', len - 1);
                if (!sep)
                    return VE_MISSING_SEPARATOR;
                if (sep + 1 - p == len)
                    return VE_MISSING_VALUE;
                if (!key_valid(p, sep - p))
                    return VE_INVALID_KEY;
                
                char *key = strlwr(strndup(p, sep - p));
                if (!key)
                    return VE_ALLOCATION;
                char *value = strndup(sep + 1, len - (sep + 1 - p));
                if (!value)
                    {
                    free(key);
                    return VE_ALLOCATION;
                    }

                GSList *slist = NULL;
                gpointer orig_key = NULL;
                if (g_hash_table_lookup_extended(s->hash_table, key, &orig_key, (gpointer *)&slist))
                    {
                    g_hash_table_steal(s->hash_table, key);
                    free(orig_key);
                    }
                
                slist = g_slist_append(slist, (gpointer)value);
                g_hash_table_insert(s->hash_table, key, (gpointer)slist);
                }
            }
        p += len;
        }
        
    return VE_OK;
    }

static void free_value(GSList *slist)
    {
    g_slist_free_full(slist, free);
    }

struct vtag *
vtag_parse(void *data, size_t bytes, int *error)
    {
    struct vtag *s;
    int error_;
    
    if (!error)
        error = &error_;
    
    if (!(s = calloc(1, sizeof (struct vtag))))
        {
        fprintf(stderr, "vtag_parse: malloc failure\n");
        *error = VE_ALLOCATION;
        return NULL;
        }
    
    if (!(s->hash_table = g_hash_table_new_full(g_str_hash, g_str_equal,
                                        free, (GDestroyNotify)free_value)))
        {
        fprintf(stderr, "vtag_parse: failed to create new hash table\n");
        free(s);
        *error = VE_ALLOCATION;
        return NULL;
        }

    *error = parse(s, data, bytes);
    if (*error != VE_OK)
        {
        vtag_cleanup(s);
        return NULL;
        }

    return s;
    }

struct valuestore {
    size_t length;
    int count;
};

static void slist_data_length(gpointer data1, gpointer data2)
    {
    struct valuestore *vs = (struct valuestore *)data2;    
        
    vs->length += strlen(data1);
    ++vs->count;
    }

char *
vtag_lookup(struct vtag *s, char const *key, enum vtag_lookup_mode mode, char *sep)
    {
    char *value, *lcase_key;
    GSList *slist;
    size_t length = 0;
    struct valuestore vs = {0, 0};

    if (!(lcase_key = strlwr(strdup(key))))
        {
        fprintf(stderr, "vtag_lookup: malloc failure\n");
        return NULL;
        }

    if ((slist = g_hash_table_lookup(s->hash_table, lcase_key)) == NULL)
        return NULL;
        
    switch (mode) {
        case VLM_FIRST:
            return strdup(slist->data);

        case VLM_LAST:
            return strdup(g_slist_last(slist)->data);

        case VLM_MERGE:
            if (!sep)
                sep = "";
                
            g_slist_foreach(slist, slist_data_length, &vs);
            length = vs.length + (vs.count - 1) * strlen(sep) + 1;
            if (!(value = malloc(length)))
                {
                fprintf(stderr, "vtag_lookup: malloc failure\n");
                return NULL;
                }
            strcpy(value, slist->data);
            while (slist->next)
                {
                strcat(value, sep);
                slist = slist->next;
                strcat(value, slist->data);
                }
            return value;

        default:
            fprintf(stderr, "vtag_lookup: unknown lookup mode\n");
        }

    return NULL;
    }

char const *
vtag_vendor_string(struct vtag *s)
    {
    return s->vendor_string;
    }

void
vtag_cleanup(struct vtag *s)
    {
    if (s->vendor_string)
        free(s->vendor_string);
    g_hash_table_destroy(s->hash_table);
    free(s);
    }

char const *
vtag_error_string(int error)
    {
    switch ((enum vtag_error) error) {
        case VE_OK:
            return "no error";
        case VE_ALLOCATION:
            return "malloc failure";
        case VE_CROPPED:
            return "vorbis comment block larger than supplied data";
        case VE_TRAILING:
            return "vorbis comment block finished before end of data";
        case VE_SHORT_COMMENT:
            return "vorbis comment too short to express key=value";
        case VE_MISSING_SEPARATOR:
            return "vorbis comment separator missing";
        case VE_MISSING_VALUE:
            return "vorbis comment value missing";
        case VE_INVALID_KEY:
            return "vorbis comment key contains illegal characters";
        default:
            return "unknown error code";
        }
    }
