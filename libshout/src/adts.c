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

/* the possible adts header sizes */
#define MAX_HEADER (9)
#define MIN_HEADER (7)

static int count = 0;

/* -- local datatypes -- */
typedef struct {
	unsigned int frames;
	/* the number of samples for the current frame */
	int frame_samples;
	/* the samplerate of the current frame */
	int frame_samplerate;
	/* how many bytes for the rest of this frame */
	unsigned int frame_left;
	/* is the header bridged?? */
	int header_bridges;
	/* put part of header here if it spans a boundary */
	unsigned char header_bridge[MAX_HEADER - 1];
} adts_data_t;

typedef struct {
    int syncword;   /* always 0xFFF */
    int version;    /* 0 for mpeg4, 1 for mpeg 2 */
    int layer;      /* always 0 */
    int protection_absent;
    int profile;    /* the mpeg audio object type minus 1 */
    int sampling_frequency_index; /* see sample_rates */
    int private_stream;
    int channel_configuration;
    int originality;
    int home;
    int copyrighted_stream;
    int copyright_start;
    int frame_length; /* in bytes -- includes header */
    int buffer_fullness;
    int extra_frames; /* number of additional aac frames (RDBs) */
    uint16_t crc;     /* crc or 0 if protection absent */
    unsigned int samplerate;
    unsigned int samples;
} adts_header_t;

static uint32_t sample_rates[] = {
    96000, 88200, 64000, 48000, 44100, 32000, 24000,
    22050, 16000, 12000, 11025, 8000, 7350, -1, -1, -1
};

/* -- static prototypes -- */
static int send_adts(shout_t *self, const unsigned char *buff, size_t len);
static void close_adts(shout_t *self);
static void parse_header(adts_header_t *ah, const uint8_t *header);
static int adts_header(const uint8_t *head, adts_header_t *ah);

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

static int send_adts(shout_t *self, const unsigned char *buff, size_t len)
{
	adts_data_t* adts_data = (adts_data_t*) self->format_data;
	unsigned long pos;
	int ret, count;
	int start, end, error, i;
	unsigned char *bridge_buff;
	adts_header_t ah;

	bridge_buff = NULL;
	pos = 0;
	start = 0;
	error = 0;
	end = len - 1;
	memset(&ah, 0, sizeof(ah));

	/* finish the previous frame */
	if (adts_data->frame_left > 0) {
		/* is the rest of the frame here? */
		if (adts_data->frame_left <= len) {
			self->senttime += (int64_t)((double)adts_data->frame_samples / (double)adts_data->frame_samplerate * 1000000.0);
			adts_data->frames++;
			pos += adts_data->frame_left;
			adts_data->frame_left = 0;
		} else {
			adts_data->frame_left -= len;
			pos = len;
		}
	}

	/* header was over the boundary, so build a new build a new buffer */
	if (adts_data->header_bridges) {
		bridge_buff = (unsigned char *)malloc(len + adts_data->header_bridges);
		if (bridge_buff == NULL) {
			return self->error = SHOUTERR_MALLOC;
		}

        memcpy(bridge_buff, adts_data->header_bridge, adts_data->header_bridges);
		memcpy(&bridge_buff[adts_data->header_bridges], buff, len);

		buff = bridge_buff;
		len += adts_data->header_bridges;
		end = len - 1;

		adts_data->header_bridges = 0;
	}

	/** this is the main loop
	*** we handle everything except the last MAX_HEADER bytes...
	**/
	while ((pos + MAX_HEADER) <= len) {
		/* is this a valid header? */
		if (adts_header(&buff[pos], &ah)) {
			if (error) {
				start = pos;
				end = len - 1;
				error = 0;
			}

			adts_data->frame_samples = ah.samples;
			adts_data->frame_samplerate = ah.samplerate;

			/* do we have a complete frame in this buffer? */
			if (len - pos >= ah.frame_length) {
				self->senttime += (int64_t)((double)adts_data->frame_samples / (double)adts_data->frame_samplerate * 1000000.0);
				adts_data->frames++;
				pos += ah.frame_length;
			} else {
				adts_data->frame_left = ah.frame_length - (len - pos);
				pos = len;
			}
		} else {
			/* there was an error
			** so we send all the valid data up to this point 
			*/
            
			if (!error) {
				error = 1;
				end = pos - 1;
				count = end - start + 1;
				if (count > 0)
					ret = (int)shout_send_raw(self, (unsigned char *)&buff[start], count);
				else
					ret = 0;

				if (ret != count) {
					if (bridge_buff != NULL)
						free(bridge_buff);
					return self->error = SHOUTERR_SOCKET;
				}
			}
			pos++;
		}
	}

	/* catch the tail if there is one */
	if ((pos > (len - MAX_HEADER)) && (pos < len)) {
		end = pos - 1;

		i = 0;
		while (pos < len) {
			adts_data->header_bridge[i] = buff[pos];
			pos++;
			i++;
		} 
		adts_data->header_bridges = i;
	}

	if (!error) {
		/* if there's no errors, lets send the frames */
		count = end - start + 1;
		if (count > 0)
			ret = (int)shout_send_raw(self, (unsigned char *)&buff[start], count);
		else
			ret = 0;

		if (bridge_buff != NULL)
			free(bridge_buff);

		if (ret == count) {
			return self->error = SHOUTERR_SUCCESS;
		} else {
			return self->error = SHOUTERR_SOCKET;
		}
	}

	if (bridge_buff != NULL)
		free(bridge_buff);

	return self->error = SHOUTERR_SUCCESS;
}

static void close_adts(shout_t *self)
{
	adts_data_t *adts_data = (adts_data_t *)self->format_data;

	free(adts_data);
}

static void parse_header(adts_header_t *ah, const uint8_t *header)
{
    ah->syncword = (int)header[0] << 4 | header[1] >> 4;
    ah->version = header[1] >> 3 & 0x1;
    ah->layer = header[1] >> 1 & 0x3;
    ah->protection_absent = header[1] & 0x1;
    ah->profile = header[2] >> 6;
    ah->sampling_frequency_index = header[2] >> 2 & 0xF;
    ah->private_stream = header[2] >> 1 & 0x1;
    ah->channel_configuration = ((int)header[2] << 2 | header[3] >> 6) & 0x7;
    ah->originality = header[3] >> 5 & 0x1;
    ah->home = header[3] >> 4 & 0x1;
    ah->copyrighted_stream = header[3] >> 3 & 0x1;
    ah->copyright_start = header[3] >> 2 & 0x1;
    ah->frame_length = ((int)header[3] << 11 | (int)header[4] << 3 | header[5] >> 5) & 0x1FFF;
    ah->buffer_fullness = ((int)header[5] << 6 | header[6] >> 2) & 0x7FF;
    ah->extra_frames = header[6] & 0x3;
    if (ah->protection_absent)
        ah->crc = 0;
    else
        ah->crc = (uint16_t)header[7] << 8 | header[8];
    ah->samplerate = sample_rates[ah->sampling_frequency_index];
    ah->samples = 1024 * (1 + ah->extra_frames);    
}

static int adts_header(const uint8_t *head, adts_header_t *ah)
{
    /* fill out the header struct */
    parse_header(ah, head);
    
    /* check for syncword */
    if (ah->syncword != 0xFFF)
        return 0;
    
    /* check that layer is valid */
    if (ah->layer != 0)
        return 0;
        
    /* make sure sample rate is sane */
    if (ah->sampling_frequency_index > 12)
        return 0;
        
    /* make sure frame length is sane */
    if (ah->frame_length < (ah->protection_absent ? MIN_HEADER : MAX_HEADER))
        return 0;
        
    return 1;
}
