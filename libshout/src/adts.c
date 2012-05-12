/* -*- c-basic-offset: 8; -*- */
/* adts.c: libshout AAC/ADTS format handler
 *
 *  Copyright (C) 2012 Stephen Fairchild <s-fairchild@users.sourceforge.net>
 *
 *  This library is free software; you can redistribute it and/or
 *  modify it under the terms of the GNU Library General Public
 *  License as published by the Free Software Foundation; either
 *  version 2 of the License, or (at your option) any later version.
 *
 *  This library is distributed in the hope that it will be useful,
 *  but WITHOUT ANY WARRANTY; without even the implied warranty of
 *  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 *  Library General Public License for more details.
 *
 *  You should have received a copy of the GNU Library General Public
 *  License along with this library; if not, write to the Free
 *  Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
 */
 

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <shout/shout.h>
#include "shout_private.h"

/* -- local datatypes -- */
typedef struct {

} adts_data_t;

/* -- static prototypes -- */
static int send_adts(shout_t *self, const unsigned char *buf, size_t len);
static void close_adts(shout_t *self);

int shout_open_adts(shout_t *self)
{
	adts_data_t *adts_data;
    
	if (!(adts_data = (adts_data_t *)calloc(1, sizeof(adts_data_t))))
		return SHOUTERR_MALLOC;
	self->format_data = adts_data;

	self->send = send_adts;
	self->close = close_adts;

	return SHOUTERR_SUCCESS;
}

static int send_adts(shout_t *self, const unsigned char *buf, size_t len)
{
    ssize_t ret;

    /* Really basic at the moment. No frame analysis, etc. */
    ret = shout_send_raw(self, (unsigned char *)buf, len);
    if (ret == len)
        return SHOUTERR_SUCCESS;
    else
        return SHOUTERR_SOCKET;
}

static void close_adts(shout_t *self)
{
	adts_data_t *adts_data = (adts_data_t *)self->format_data;

	free(adts_data);
}
