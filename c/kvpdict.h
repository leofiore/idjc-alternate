/*
#   kvpdict.h: key-value pair header file for kvpdict.c, part of the IDJC project
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
#ifndef KVPDICT_H
#define KVPDICT_H

#include <pthread.h>

struct kvpdict
    {
    char *key;           /* the key from a key value pair to match against */
    char **target;       /* the aim here is to set another pointer to the new value
                                rather than to make the new value a member of the dictionary */
    pthread_mutex_t *pm; /* if a lock is supplied here it will be used */
    };
    
char *kvp_extract_value(char *keyvaluepair);
int kvp_apply_to_dict(struct kvpdict *kvpdict, char *key, char *newtarget);
void kvp_free_dict(struct kvpdict *dp);

#endif
