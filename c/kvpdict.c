/*
#   kvpdict.c: key-value pair functions to aid parsing and setting of values
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

#include "gnusource.h"
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <assert.h>
#include "kvpdict.h"
#include "bsdcompat.h"

/* kvp_extract_value: extract the value of a key value pair from a string. The value is a copy of the orignial and is allocated on the heap.  The returned "value" should be destroyed with free() when no longer needed.  The string supplied is truncated at the = sign */
char *kvp_extract_value(char *pair)
    {
    char *part2, *value;
    
    if (!(part2 = strchr(pair, '=')))    /* calling program must supply a Key Value Pair */
        {
        fprintf(stderr, "kvp_extract_value: not a key=value pair: %s\n", pair);
        return strdup("");
        }
    *part2++ = '\0';     /* point to the second half of the KVP and terminate the 1st also removing the \n character */
    *strchr(part2, '\n') = '\0';
    if (!(value = strdup(part2)))        /* make a separate copy of the value */
        {
        fprintf(stderr, "kvp_extract_value: malloc failure\n");
        exit(-5);
        }
    return value;
    }

/* dict_apply_to_target: sets a pointers object listed in a kvpdict to point to target when its key matches the one supplied to the function.  Target is not made a member of the dictionary, but rather one of the dictionary members, which is itself a pointer is set to point to target.  The memory used by the old target is freed */
int kvp_apply_to_dict(struct kvpdict *dp, char *key, char *target)
    {
    int append;
    size_t origtext_siz, newtext_siz;

    if ((append = (key[0] == '+')))      /* If key starts with a plus we will not replace -- we will append */
        ++key;

    for (; dp->target; dp++)             /* Iterate over NULL terminated dictionary */
        {
        if (!strcmp(key, dp->key))        /* If the key matches */
            {
            if (dp->pm)                    /* If a pthread mutex is supplied then use it */
                pthread_mutex_lock(dp->pm);
            if (!append)
                {
                if (*(dp->target))          /* Conditionally free the old target buffer */
                    free(*(dp->target));
                *(dp->target) = target;     /* Dictionary member's pointer gets a new target */
                }
            else
                {
                /* append mode -- multiple appends separated by a newline character */
                *(dp->target) = realloc(*(dp->target), (origtext_siz = strlen(*(dp->target))) + (newtext_siz = strlen(target)) + 2);
                if (!(*(dp->target)))
                    {
                    fprintf(stderr, "malloc failure\n");
                    exit(5);
                    }
                memcpy(*(dp->target) + origtext_siz, target, newtext_siz);
                memcpy(*(dp->target) + origtext_siz + newtext_siz, "\n", 2);
                free(target);
                }
            if (dp->pm)                    /* Unlock the pthread mutex if one was specified */
                pthread_mutex_unlock(dp->pm);
            return 1;                      /* We have a match so return 1 */
            }
        }
    return 0;                            /* No matches */
    }

void kvp_free_dict(struct kvpdict *dp)
    {
    while (dp->key)
        {
        if (*(dp->target))
            free(*(dp->target));
        *dp->target = NULL;
        dp++;
        }
    }
