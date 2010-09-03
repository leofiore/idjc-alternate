/*
#   bsdcompat.h: library functions that are missing from BSD
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

#ifndef BSD_COMPAT_H
#define BSD_COMPAT_H

#include "gnusource.h"

#ifdef USE_BSD_COMPAT

#include <stdio.h>
#include <sys/types.h>

float bsd_pow10f(float x);
char *bsd_strndup(const char *s, size_t n);
ssize_t bsd_getline(char **lineptr, size_t *n, FILE *stream);
char *bsd_canonicalize_file_name(const char *path);

#ifndef _GNU_SOURCE

#define pow10f(x) bsd_pow10f(x)
#define strndup(s, n) bsd_strndup(s, n)
#define getline(l, n, s) bsd_getline(l, n, s)
#define canonicalize_file_name(p) bsd_canonicalize_file_name(p)

#endif /* _GNU_SOURCE */
#endif /* USE_BSD_COMPAT */
#endif /* BSD_COMPAT_H */
