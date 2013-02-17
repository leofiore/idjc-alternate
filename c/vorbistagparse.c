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

#define SET(p, ind, shift, v)   do {((unsigned char *)p)[ind] = v >> shift;} while (0)
#define WRITEINT(p, v)      do {p += 4; SET(p, -1, 24, v); SET(p, -2, 16, v); \
                                SET(p, -3, 8, v); SET(p, -4, 0, v);} while (0)

struct vtag {
    GHashTable *hash_table; /* table of g_slists of key=value pairs */
    char *vendor_string;
};

struct vtag_block_private {
    size_t blocklen;
};

static int
key_valid(char const *key, size_t n)
    {
    if (n == 0)
        return 0;
        
    while (n--)
        {
        if (*key < 0x20 || *key > 0x7D || *key == '=')
            return 0;
        ++key;
        }

    return !0;
    }

static char *
strlwr(char *s)
    {
    if (s == NULL)
        return NULL;

    for (char *p = s; *p; ++p)
        *p = tolower(*p);
    return s;
    }

/* key and value must be dedicated copies and heap allocated */
static void
insert_value(GHashTable *hash_table, char *key, char *value)
    {
    GSList *slist = NULL;
    gpointer orig_key = NULL;
    
    if (g_hash_table_lookup_extended(hash_table, key, &orig_key, (gpointer *)&slist))
        {
        g_hash_table_steal(hash_table, key);
        free(orig_key);
        }
    
    slist = g_slist_append(slist, (gpointer)value);
    g_hash_table_insert(hash_table, key, (gpointer)slist);
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

                insert_value(s->hash_table, key, value);
                }
            }
        p += len;
        }
        
    return VE_OK;
    }

static void
free_slist_value(GSList *slist)
    {
    g_slist_free_full(slist, free);
    }

static struct vtag *
vtag_create(int *error)
    {
    struct vtag *s;
    
    if (!(s = calloc(1, sizeof (struct vtag))))
        {
        *error = VE_ALLOCATION;
        return NULL;
        }
    
    if (!(s->hash_table = g_hash_table_new_full(g_str_hash, g_str_equal,
                                    free, (GDestroyNotify)free_slist_value)))
        {
        free(s);
        *error = VE_ALLOCATION;
        return NULL;
        }
        
    return s;
    }

struct vtag *
vtag_parse(void *data, size_t bytes, int *error)
    {
    struct vtag *s;
    int error_;
    
    if (!error)
        error = &error_;

    if (!(s = vtag_create(error)))
        return NULL;

    *error = parse(s, data, bytes);
    if (*error != VE_OK)
        {
        vtag_cleanup(s);
        return NULL;
        }

    return s;
    }

struct vtag *
vtag_new(const char *vendor_string, int *error)
    {
    struct vtag *s;
    int error_;
    
    if (!error)
        error = &error_;
    
    if (!(s = vtag_create(error)))
        return NULL;

    if (!(s->vendor_string = strdup(vendor_string)))
        {
        vtag_cleanup(s);
        *error = VE_ALLOCATION;
        return NULL;
        }

    return s;
    }

struct valuestore {
    size_t length;
    int count;
};

static void
slist_storage_calc(gpointer data, gpointer user_data)
    {
    struct valuestore *vs = user_data;
    
    vs->length += strlen(data);
    ++vs->count;
    }

static void
ht_storage_calc(gpointer key, gpointer value, gpointer user_data)
    {
    struct valuestore *vs = user_data;
    int count = vs->count;
    GSList *slist = value;

    g_slist_foreach(slist, slist_storage_calc, vs);
    vs->length += (vs->count - count) * (5 + strlen(key));
    }

struct valuestore2 {
    char **p;
    char *key;
};

static void
slist_dump(gpointer data, gpointer user_data)
    {
    struct valuestore2 *vs = user_data;
    char **p = vs->p;
    size_t len1, len2;
    
    len1 = strlen(vs->key);
    len2 = strlen(data);
    WRITEINT((*p), (len1 + 1 + len2)); 
    memcpy(*p, vs->key, len1);
    *p += len1;
    *(*p)++ = '=';
    memcpy(*p, data, len2);
    *p += len2;
    }

static void
ht_dump(gpointer key, gpointer value, gpointer user_data)
    {
    GSList *slist = value;
    struct valuestore2 vs = {user_data, key};
    
    g_slist_foreach(slist, slist_dump, &vs);
    }

int
vtag_block_init(struct vtag_block *block)
    {
    block->data = NULL;
    block->length = 0;
    if (!(block->private = malloc(sizeof (struct vtag_block_private))))
        {
        fprintf(stderr, "malloc failure\n");
        return 0;
        }
    block->private->blocklen = 0;
    return 1;
    }

void
vtag_block_cleanup(struct vtag_block *block)
    {
    if (block->data)
        free(block->data);
    free(block->private);
    };

int
vtag_serialize(struct vtag *s, struct vtag_block *block, char const *prefix)
    {
    size_t len;
    char *p;
    struct valuestore vs = {0, 0};
    
    if (!prefix)
        prefix = "";
    
    /* determine how much space to allocate */
    g_hash_table_foreach(s->hash_table, ht_storage_calc, &vs);
    len = vs.length + 8 + strlen(s->vendor_string) + strlen(prefix);

    if (len > block->private->blocklen)
        {
        if (!(block->data = realloc(block->data, len)))
            return VE_ALLOCATION;
        block->private->blocklen = len;
        }
    
    block->length = len;
    p = block->data;

    strncpy(p, prefix, len = strlen(prefix));
    p += len;
    len = strlen(s->vendor_string);
    WRITEINT(p, len);
    strncpy(p, s->vendor_string, len);
    p += len;
    WRITEINT(p, vs.count);

    g_hash_table_foreach(s->hash_table, ht_dump, &p);

    return VE_OK;
    }

static void
slist_data_length(gpointer data1, gpointer data2)
    {
    struct valuestore *vs = (struct valuestore *)data2;    
        
    vs->length += strlen(data1);
    ++vs->count;
    }

static GSList *
slist_lookup(struct vtag *s, char const *key)
    {
    GSList *slist;
    char *lcase_key;
    
    if (!(lcase_key = strlwr(strdup(key))))
        {
        fprintf(stderr, "slist_lookup: malloc failure\n");
        return NULL;
        }

    slist = g_hash_table_lookup(s->hash_table, lcase_key);
    free(lcase_key);
    return slist;
    }

int
vtag_comment_count(struct vtag *s, char const *key)
    {
    GSList *slist;
    struct valuestore vs = {0, 0};
    
    if (!(slist = slist_lookup(s, key)))
        return 0;
    
    g_slist_foreach(slist, slist_data_length, &vs);
    return vs.count;
    }

char *
vtag_lookup(struct vtag *s, char const *key, enum vtag_lookup_mode mode, char *sep)
    {
    char *value;
    GSList *slist;
    size_t length = 0;
    struct valuestore vs = {0, 0};

    if (!(slist = slist_lookup(s, key)))
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

int
vtag_append(struct vtag *s, char const *key, char const *value)
    {
    char *lcase_key, *value_copy;

    if (!key_valid(key, strlen(key)))
            return VE_INVALID_KEY;
            
    if (strlen(value) == 0)
        return VE_MISSING_VALUE;
        
    if (!(lcase_key = strlwr(strdup(key))))
        return VE_ALLOCATION;
        
    if (!(value_copy = strdup(value)))
        return VE_ALLOCATION;

    insert_value(s->hash_table, lcase_key, value_copy);

    return VE_OK;
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
vtag_strerror(int error)
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
