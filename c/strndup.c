/*
 * Copyright (C) 2002     Manuel Novoa III
 * Copyright (C) 2000-2005 Erik Andersen <andersen@uclibc.org>
 *
 * Licensed under the LGPL v2.1, see the file COPYING.LIB in this tarball.
 */

#include <stdlib.h>
#include <string.h>

char *strndup(register const char *s1, size_t n)
{
	register char *s, *end;

	end = memchr(s1, '\n', n);
    n = end ? (size_t) (end - s1) : n;

    if ((s = malloc(n + 1)) != NULL) {
		memcpy(s, s1, n);
		s[n] = 0;
	}

	return s;
}
