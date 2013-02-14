/*
#   oggdec.c: ogg file parser for xlplayer
#   Copyright (C) 2008-2012 Stephen Fairchild (s-fairchild@users.sourceforge.net)
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

#include "../config.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>

#include "xlplayer.h"
#include "oggdec.h"
#include "ogg_vorbis_dec.h"
#include "ogg_opus_dec.h"
#include "ogg_flac_dec.h"
#include "ogg_speex_dec.h"
#include "vorbistagparse.h"

#define ACCEPTED 1
#define REJECTED 0

int oggdec_get_next_packet(struct oggdec_vars *self)
    {
    char *buffer;
    size_t bytes;
    int retval;
    
    while ((retval = ogg_stream_packetout(&self->os, &self->op)) == 0)
        {
        while (ogg_sync_pageout(&self->oy, &self->og) != 1)
            {
            buffer = ogg_sync_buffer(&self->oy, 8192);
            bytes = fread(buffer, 1, 8192, self->fp);
            ogg_sync_wrote(&self->oy, bytes);
            if (bytes == 0)
                {
                fprintf(stderr, "oggdec_get_next_packet: the end of the file appears to have been reached, unexpectedly\n");
                return 0;
                }
            }
        if (ogg_stream_pagein(&self->os, &self->og))
            {
            fprintf(stderr, "oggdec_get_next_packet: call to ogg_stream_pagein failed, most likely this stream is either multiplexed or improperly terminated\n");
            return 0;
            }
        else
            if ((self->new_oggpage_callback))
                self->new_oggpage_callback(self, self->new_oggpage_cb_userdata);
        }
    
    if (retval == -1)
        {
        fprintf(stderr, "get_next_packet: hole in data detected - possibly not serious\n");
        }
    
    return 1;
    }

static unsigned vorbis_get_samplerate(struct oggdec_vars *self)  /* attempt to get ARTIST=, TITLE= also */
    {
    vorbis_info vi;
    vorbis_comment vc;
    unsigned samplerate;

    vorbis_info_init(&vi);
    vorbis_comment_init(&vc);

    void obtain_tag_info(char *name, char **target, int multiple)
        {
        int tags = vorbis_comment_query_count(&vc, name);
        int size, i;

        if (tags == 0)
            {
            *target = strdup("");
            return;
            }

        if (tags == 1)
            {
            *target = strdup(vorbis_comment_query(&vc, name, 0));
            return;
            }

        if (multiple)
            {
            /* calculate the space needed */
            size = tags;
            for (i = 0; i < tags; i++)
                size += strlen(vorbis_comment_query(&vc, name, i));

            if (!(*target = malloc(size)))
                {
                *target = strdup("");
                fprintf(stderr, "vorbis_get_samplerate: malloc failure\n");
                return;
                }
            *target[0] = '\0';

            /* collect a slash separated list of tags */
            for (i = 0; i < tags; i++)
                {
                strcat(*target, vorbis_comment_query(&vc, name, i));
                if (i < tags - 1)
                    strcat(*target, "/");
                }
            }
        else
            {
            /* grab the last comment when only a single will do */
            *target = strdup(vorbis_comment_query(&vc, name, tags - 1));
            }
        }

    /* enforce that first header yields the sample rate, that granule pos for the header is zero and */
    /* that the third and final header finishes on a page boundary */
    if (oggdec_get_next_packet(self) && vorbis_synthesis_headerin(&vi, &vc, &self->op) >= 0 && vi.rate &&
         oggdec_get_next_packet(self) && vorbis_synthesis_headerin(&vi, &vc, &self->op) >= 0 &&
         oggdec_get_next_packet(self) && vorbis_synthesis_headerin(&vi, &vc, &self->op) >= 0 &&
         self->op.granulepos == 0 && ogg_stream_packetout(&self->os, &self->op) == 0  &&
         oggdec_get_next_packet(self) && ogg_page_continued(&self->og) == 0)
        {
        samplerate = self->samplerate[self->ix] = vi.rate;
        self->channels[self->ix] = vi.channels;
        
        if (vorbis_comment_query_count(&vc, "trk-title"))
            {
            obtain_tag_info("trk-artist", &self->artist[self->ix], TRUE);
            obtain_tag_info("trk-title", &self->title[self->ix], TRUE);
            obtain_tag_info("trk-album", &self->album[self->ix], TRUE);
            }
        else
            {
            obtain_tag_info("artist", &self->artist[self->ix], TRUE);
            obtain_tag_info("title", &self->title[self->ix], TRUE);
            obtain_tag_info("album", &self->album[self->ix], TRUE);
            }
      
        obtain_tag_info("replaygain_track_gain", &self->replaygain[self->ix], FALSE);
        }
    else
        {
        fprintf(stderr, "vorbis_get_samplerate: non standard ogg/vorbis header found\n");
        samplerate = 0;
        self->channels[self->ix] = 0;
        }
    
    vorbis_comment_clear(&vc);
    vorbis_info_clear(&vi);

    return samplerate;
    }
    
#ifdef HAVE_OGGFLAC

FLAC__StreamDecoderReadStatus oggflac_read_callback(const FLAC__StreamDecoder *decoder, FLAC__byte buffer[], size_t *bytes, void *client_data)
    {
    struct oggdec_vars *self = client_data;
    off_t bytes_remaining;

    if (self->ix == self->n_streams - 1)
        bytes_remaining = self->eos_offset - ftello(self->fp);
    else
        bytes_remaining = self->bos_offset[self->ix + 1] - ftello(self->fp);

    if (bytes_remaining < 0 || *bytes <= 0)
        return FLAC__STREAM_DECODER_READ_STATUS_ABORT;

    if (*bytes > (size_t)bytes_remaining)
        *bytes = bytes_remaining;

    *bytes = fread(buffer, sizeof (FLAC__byte), *bytes, self->fp);

    if (ferror(self->fp))
        return FLAC__STREAM_DECODER_READ_STATUS_ABORT;
        
    if (*bytes == 0)
        return FLAC__STREAM_DECODER_READ_STATUS_END_OF_STREAM;
        
    return FLAC__STREAM_DECODER_READ_STATUS_CONTINUE;
    }

FLAC__StreamDecoderSeekStatus oggflac_seek_callback(const FLAC__StreamDecoder *decoder, FLAC__uint64 absolute_byte_offset, void *client_data)
    {
    struct oggdec_vars *self = client_data;
    off_t start_bound, end_bound;

    start_bound = self->bos_offset[self->ix];
    
    if (self->ix == self->n_streams - 1)
        end_bound = self->eos_offset - start_bound;
    else
        end_bound = self->bos_offset[self->ix + 1] - start_bound;

    if (absolute_byte_offset > (FLAC__uint64)(end_bound - start_bound))
        {
        fprintf(stderr, "oggflac_seek_callback: seek error1\n");
        return FLAC__STREAM_DECODER_SEEK_STATUS_ERROR;
        }
    
    if (fseeko(self->fp, start_bound + (off_t)absolute_byte_offset, SEEK_SET) < 0)
        {
        fprintf(stderr, "oggflac_seek_callback: seek error2\n");
        return FLAC__STREAM_DECODER_SEEK_STATUS_ERROR;
        }

    return FLAC__STREAM_DECODER_SEEK_STATUS_OK;
    }

FLAC__StreamDecoderTellStatus oggflac_tell_callback(const FLAC__StreamDecoder *decoder, FLAC__uint64 *absolute_byte_offset, void *client_data)
    {
    struct oggdec_vars *self = client_data;
    off_t where;
    
    where = ftello(self->fp);
    
    if (where < self->bos_offset[self->ix])
        return FLAC__STREAM_DECODER_TELL_STATUS_ERROR;
    
    if (self->ix != self->n_streams - 1)
        {
        if (where > self->bos_offset[self->ix + 1])
            return FLAC__STREAM_DECODER_TELL_STATUS_ERROR;
        }
    else
        {
        if (where > self->eos_offset)
            return FLAC__STREAM_DECODER_TELL_STATUS_ERROR;
        }
    
    *absolute_byte_offset = (FLAC__uint64)(where - self->bos_offset[self->ix]);
    return FLAC__STREAM_DECODER_TELL_STATUS_OK;
    }

FLAC__StreamDecoderLengthStatus oggflac_length_callback(const FLAC__StreamDecoder *decoder, FLAC__uint64 *stream_length, void *client_data)
    {
    struct oggdec_vars *self = client_data;
    
    if (self->ix == self->n_streams - 1)
        *stream_length = self->eos_offset - self->bos_offset[self->ix];
    else
        *stream_length = self->bos_offset[self->ix + 1] - self->bos_offset[self->ix];
        
    return FLAC__STREAM_DECODER_LENGTH_STATUS_OK;
    }
    
FLAC__bool oggflac_eof_callback(const FLAC__StreamDecoder *decoder, void *client_data)
    {
    struct oggdec_vars *self = client_data;
    off_t offset;

    offset = ftello(self->fp) + self->bos_offset[self->ix];
    if (self->ix == self->n_streams - 1)
        return offset >= self->eos_offset;
    else
        return offset >= self->bos_offset[self->ix + 1];
    }

static void oggflac_metadata_callback(const FLAC__StreamDecoder *decoder, const FLAC__StreamMetadata *metadata, void *client_data)
    {
    struct oggdec_vars *self = client_data;
    const FLAC__StreamMetadata_StreamInfo *si;
    const FLAC__StreamMetadata_VorbisComment *vc;
    int use_alt_tags;
    
    int match(char *t, char *comment)
        {
        return !strncasecmp(t, comment, strlen(t));
        }
    
    char *end(char *t)
        {
        while (*t++ != '=');
        while (isspace(*t) && t != '\0')
            t++;
        return t;
        }

    void copy_tag(char *t, char **target, int multiple)
        {
        char *old, *new;
        
        for (unsigned j = 0; j < vc->num_comments; j++)
            {
            if (match(t, (char *)vc->comments[j].entry))
                {
                old = strdup(*target);
                new = end((char *)vc->comments[j].entry);
                *target = realloc(*target, strlen(old) + strlen(new) + 2);
                if (old[0] && multiple)
                    sprintf(*target, "%s/%s", old, new);
                else
                    strcpy(*target, new);
                free(old);
                }
            }
        if (*target == NULL)
            *target = strdup("");
        }
    
    if (metadata->type == FLAC__METADATA_TYPE_STREAMINFO)
        {
        fprintf(stderr, "oggflac_metadata_callback: got streaminfo metadata block\n");
        si = &metadata->data.stream_info;
        fprintf(stderr, "Sample rate in comment block is %u\n", si->sample_rate);
        fprintf(stderr, "Number of channels in comment block is %u\n", si->channels);
        self->samplerate[self->ix] = si->sample_rate;
        self->channels[self->ix] = si->channels;
        }
    else
        if (metadata->type == FLAC__METADATA_TYPE_VORBIS_COMMENT)
            {
            fprintf(stderr, "oggflac_metadata_callback: got vorbis comment metadata block\n");
            vc = &metadata->data.vorbis_comment;
            fprintf(stderr, "There are %u comment tags\n", (unsigned)vc->num_comments);
            use_alt_tags = FALSE;
            for (unsigned i = 0; i < vc->num_comments; i++)
                {
                if (match("trk-title", (char *)vc->comments[i].entry))
                    use_alt_tags = TRUE;
                fprintf(stderr, "%s\n", vc->comments[i].entry);
                }

            if (use_alt_tags)
                {
                copy_tag("trk-artist=", &self->artist[self->ix], TRUE);
                copy_tag("trk-title=", &self->title[self->ix], TRUE);
                copy_tag("trk-album=", &self->album[self->ix], TRUE);
                }
            else
                {
                copy_tag("artist=", &self->artist[self->ix], TRUE);
                copy_tag("title=", &self->title[self->ix], TRUE);
                copy_tag("album=", &self->album[self->ix], TRUE);
                }
            copy_tag("replaygain_track_gain=", &self->replaygain[self->ix], FALSE);
            }
        else
            fprintf(stderr, "oggflac_metadata_callback: unhandled FLAC metadata type\n");
    fprintf(stderr, "oggflac_metadata_callback: finished\n");
    }

static FLAC__StreamDecoderWriteStatus oggflac_write_callback(const FLAC__StreamDecoder *decoder, const FLAC__Frame *frame, const FLAC__int32 *const buffer[], void *client_data)
    {
    return FLAC__STREAM_DECODER_WRITE_STATUS_CONTINUE;
    }
    
void oggflac_error_callback(const FLAC__StreamDecoder *decoder, FLAC__StreamDecoderErrorStatus se, void *client_data)
    {
    switch (se)
        {
        case FLAC__STREAM_DECODER_ERROR_STATUS_LOST_SYNC:
            fprintf(stderr, "oggflac_error_callback: flac decoder error, lost sync\n");
            break;
        case FLAC__STREAM_DECODER_ERROR_STATUS_BAD_HEADER:
            fprintf(stderr, "oggflac_error_callback: flac decoder error, bad header\n");
            break;
        case FLAC__STREAM_DECODER_ERROR_STATUS_FRAME_CRC_MISMATCH:
            fprintf(stderr, "oggflac_error_callback: flac decoder error, frame crc mismatch\n");
            break;
        default:
            fprintf(stderr, "oggflac_error_callback: flac decoder error, unknown error\n");
        }
    }

static int flac_get_samplerate(struct oggdec_vars *self)
    {
    FLAC__StreamDecoder *decoder;

    if (!(decoder = FLAC__stream_decoder_new()))
        {
        fprintf(stderr, "flac_get_samplerate: call to FLAC__stream_decoder_new failed\n");
        return 0;
        }
    
    FLAC__stream_decoder_set_metadata_respond(decoder, FLAC__METADATA_TYPE_VORBIS_COMMENT);
    
    if (FLAC__stream_decoder_init_ogg_stream(decoder,
        oggflac_read_callback, oggflac_seek_callback, 
        oggflac_tell_callback, oggflac_length_callback,
        oggflac_eof_callback,  oggflac_write_callback,
        oggflac_metadata_callback, oggflac_error_callback,
        self) != FLAC__STREAM_DECODER_INIT_STATUS_OK)
        {
        fprintf(stderr, "flac_get_samplerate: call to FLAC__stream_decoder_init_stream failed\n");
        FLAC__stream_decoder_delete(decoder);
        return 0;
        }
        
    FLAC__stream_decoder_process_until_end_of_metadata(decoder);
    FLAC__stream_decoder_delete(decoder);

    return self->samplerate[self->ix];
    }
#endif /* HAVE_OGGFLAC */

#ifdef HAVE_SPEEX

static int speex_get_samplerate(struct oggdec_vars *self)
    {
    SpeexHeader *h;

    /* enforce that the speex header packet be in it's own ogg page */
    if (oggdec_get_next_packet(self) && ogg_stream_packetout(&self->os, &self->op) == 0 && (h = speex_packet_to_header((char *)self->op.packet, self->op.bytes)))
        {
        switch (self->channels[self->ix] = h->nb_channels)
            {
            case 1:
            case 2:
                self->samplerate[self->ix] = h->rate;
                speex_header_free(h);
                if (oggdec_get_next_packet(self) && ogg_stream_packetout(&self->os, &self->op) == 0)
                    {
                    struct vtag *tag;
                    int error;

                    if ((tag = vtag_parse((char *)self->op.packet, self->op.bytes, &error)))
                        {
                        if (!(self->artist[self->ix] = vtag_lookup(tag, "trk-author", VLM_MERGE, "/")))
                            if (!(self->artist[self->ix] = vtag_lookup(tag, "trk-artist", VLM_MERGE, "/")))
                                if (!(self->artist[self->ix] = vtag_lookup(tag, "author", VLM_MERGE, "/")))
                                    if (!(self->artist[self->ix] = vtag_lookup(tag, "artist", VLM_MERGE, "/")))
                                        self->artist[self->ix] = strdup("");
                        if (!(self->title[self->ix] = vtag_lookup(tag, "trk-title", VLM_MERGE, "/")))
                            if (!(self->title[self->ix] = vtag_lookup(tag, "title", VLM_MERGE, "/")))
                                self->title[self->ix] = strdup("");
                        if (!(self->album[self->ix] = vtag_lookup(tag, "trk-album", VLM_MERGE, "/")))
                            if (!(self->album[self->ix] = vtag_lookup(tag, "album", VLM_MERGE, "/")))
                                self->album[self->ix] = strdup("");

                        vtag_cleanup(tag);
                        }
                    else
                        {
                        fprintf(stderr, "%s\n", vtag_strerror(error));
                        return 0;
                        }
                    }
                else
                    return 0;
                
                return self->samplerate[self->ix];
            default:
                speex_header_free(h);
                fprintf(stderr, "speex_get_samplerate: header indicates an unsupported number of audio channels\n");
                return 0;
            }
        }
    else
        {
        fprintf(stderr, "speex_get_samplerate: failed to get speex header\n");
        return 0;
        }
    }

#endif /* HAVE_SPEEX */

#ifdef HAVE_OPUS

static int opus_get_samplerate(struct oggdec_vars *self)
    {
    int channels, chanmap, streamcount, streamcount_2c, frames, samples;
    unsigned granule_count;
    uint16_t preskip;
    char const *reason;
    
    #define FAIL(x) do {reason = x; goto fail_point;} while(0)

    if ((granule_count = self->granule_count[self->ix]) == 0)
        FAIL("stream final packet granule count is zero");

    if (oggdec_get_next_packet(self) && ogg_stream_packetout(&self->os, &self->op) == 0)
        {
        if (ogg_page_granulepos(&self->og) != 0)
            FAIL("non zero granule position");

        if (ogg_page_packets(&self->og) != 1 || ogg_page_continued(&self->og) || ogg_page_pageno(&self->og) != 0)
            FAIL("bad header page alignment");

        if (self->op.bytes < 19)
            FAIL("packet too small to be version 1");
            
        if (self->op.packet[8] > 15)
            FAIL("encapsulation version unsupported");
            
        if ((channels = ((unsigned char *)self->op.packet)[9]) == 0)
            FAIL("number of channels is zero");
        
        self->channels[self->ix] = (channels == 1) ? 1 : 2;
        chanmap = ((unsigned char *)self->op.packet)[18];

        if (chanmap > 1)
            FAIL("unsupported channel map");

        if ((chanmap == 0 && channels > 2) || (chanmap == 1 && channels > 8))
            FAIL("too many channels for given channel mapping");

        if (chanmap == 0 && self->op.bytes != 19)
            FAIL("OpusHead packet size wrong");

        if (chanmap == 1)
            {
            if (self->op.bytes != 21 + channels)
                FAIL("OpusHead packet size wrong");
            
            streamcount = ((unsigned char *)self->op.packet)[19];
            streamcount_2c = ((unsigned char *)self->op.packet)[20];
            if (streamcount == 0)
                FAIL("streamcount is zero");
            if (streamcount_2c > streamcount)
                FAIL("two channel streamcount > total streamcount");
            if (streamcount_2c + streamcount > 255)
                FAIL("combined streamcount quantity exceeds 255");
                
            unsigned char *cm = self->op.packet + 21;
            int index;
            for (int i = 0; i < channels; ++i)
                {
                index = *cm++;
                if (index != 255 && index >= streamcount + streamcount_2c)
                    FAIL("bad channel map");
                }
            }

        preskip = self->op.packet[10] | (uint16_t)((unsigned char *)self->op.packet)[11] << 8;
        if (preskip >= granule_count)
            FAIL("no samples to decode after preskip");

        if (oggdec_get_next_packet(self) && ogg_stream_packetout(&self->os, &self->op) == 0)
            {
            if (ogg_page_packets(&self->og) != 1 || ogg_page_continued(&self->og) || ogg_page_pageno(&self->og) < 1)
                FAIL("bad header page alignment");

            if (ogg_page_granulepos(&self->og) != 0)
                FAIL("non zero granule position");

            if (self->op.bytes >= 8 && !memcmp(self->op.packet, "OpusTags", 8))
                {
                struct vtag *tag;
                int error;

                if ((tag = vtag_parse((char *)self->op.packet + 8, self->op.bytes - 8, &error)))
                    {
                    if (!(self->artist[self->ix] = vtag_lookup(tag, "trk-author", VLM_MERGE, "/")))
                        if (!(self->artist[self->ix] = vtag_lookup(tag, "trk-artist", VLM_MERGE, "/")))
                            if (!(self->artist[self->ix] = vtag_lookup(tag, "author", VLM_MERGE, "/")))
                                if (!(self->artist[self->ix] = vtag_lookup(tag, "artist", VLM_MERGE, "/")))
                                    self->artist[self->ix] = strdup("");
                    if (!(self->title[self->ix] = vtag_lookup(tag, "trk-title", VLM_MERGE, "/")))
                        if (!(self->title[self->ix] = vtag_lookup(tag, "title", VLM_MERGE, "/")))
                            self->title[self->ix] = strdup("");
                    if (!(self->album[self->ix] = vtag_lookup(tag, "trk-album", VLM_MERGE, "/")))
                        if (!(self->album[self->ix] = vtag_lookup(tag, "album", VLM_MERGE, "/")))
                            self->album[self->ix] = strdup("");

                    vtag_cleanup(tag);
                    }
                else
                    FAIL(vtag_strerror(error));
                }
            else
                FAIL("bad or missing OpusTags packet");
            }
        else
            FAIL("failed to get OpusTags packet");
            
        if (oggdec_get_next_packet(self))
            {
            if ((frames = opus_packet_get_nb_frames(self->op.packet, self->op.bytes)) < 1)
                FAIL("first packet has no frames");
            samples = opus_packet_get_samples_per_frame(self->op.packet, 48000) * frames;

            while (self->op.granulepos == -1)
                {
                oggdec_get_next_packet(self);
                if ((frames = opus_packet_get_nb_frames(self->op.packet, self->op.bytes)) < 1)
                    FAIL("packet with no frames detected");
                
                samples += opus_packet_get_samples_per_frame(self->op.packet, 48000) * frames;
                }
                                            
            if (self->op.granulepos < samples && !self->op.e_o_s)
                FAIL("first page granule position less than number of samples, end of stream not set");
            }
        else
            FAIL("failed to get first data packet");
        }
    else
        FAIL("failed to get OpusHead packet");

    return self->samplerate[self->ix] = 48000;  /* Opus always uses this rate */

    #undef FAIL

    fail_point:
        fprintf(stderr, "opus_get_samplerate: opus header sanity check failed: %s\n", reason);
        return 0;
    }

#endif /* HAVE_OPUS */

/* oggscan_eos: perform a binary search on the ogg file for the e_o_s page
 * and log details of the current logical stream when it is found */
static off_t oggscan_eos(struct oggdec_vars *self, off_t offset, off_t offset_end, int serial, int depth)
    {
    char  *buffer;
    size_t bytes;
    off_t  retval;
    off_t  midpoint = (offset_end - offset) / 2 + offset;
    off_t  stored_mid = midpoint;
    int eos = FALSE, terminate = FALSE;
    
    if (++depth >= 40)
        {
        fprintf(stderr, "maximum recursion depth %d reached on oggscan_eos\n", depth);
        return -1;
        } 

    fseeko(self->fp, midpoint, SEEK_SET);
    ogg_sync_reset(&self->oy);

    while ((retval = ogg_sync_pageseek(&self->oy, &self->og)) <= 0)
        {
        if (retval < 0)
            {
            midpoint -= retval;
            if (midpoint >= offset_end)
                return oggscan_eos(self, offset, stored_mid, serial, depth);
            }
        else
            {
            buffer = ogg_sync_buffer(&self->oy, 8192);
            bytes = fread(buffer, 1, 8192, self->fp);
            ogg_sync_wrote(&self->oy, bytes);
            if (bytes == 0)
                {
                if (offset_end > midpoint)
                    return oggscan_eos(self, offset, midpoint, serial, depth);
                fprintf(stderr, "oggscan_eos: unexpected file io error, the file is probably truncated\n");
                terminate = TRUE;
                midpoint = offset_end;
                retval = 0;
                break;
                }
            }
        }
 
    if (terminate || ogg_page_serialno(&self->og) == serial)
        {
        if (terminate || (eos = ogg_page_eos(&self->og)) || offset + 1 >= offset_end)
            {
            /* we have found the last packet in the logical stream */
            /* make space for data about this logical stream */
            self->n_streams++;
            self->bos_offset = realloc(self->bos_offset, self->n_streams * sizeof (off_t));
            self->granule_count = realloc(self->granule_count, self->n_streams * sizeof (unsigned));
            self->samplerate = realloc(self->samplerate, self->n_streams * sizeof (int));
            self->channels = realloc(self->channels, self->n_streams * sizeof (int));
            self->serial = realloc(self->serial, self->n_streams * sizeof (int));
            self->artist = realloc(self->artist, self->n_streams * sizeof (char *));
            self->artist[self->n_streams - 1] = strdup("");
            self->title  = realloc(self->title,  self->n_streams * sizeof (char *));
            self->title[self->n_streams - 1] = strdup("");
            self->album  = realloc(self->album,  self->n_streams * sizeof (char *));
            self->album[self->n_streams - 1] = strdup("");
            self->replaygain = realloc(self->replaygain, self->n_streams * sizeof (char *));
            self->replaygain[self->n_streams - 1] = strdup("");
            self->streamtype = realloc(self->streamtype, self->n_streams * sizeof (enum streamtype_t));
            self->start_time = realloc(self->start_time, self->n_streams * sizeof (double));
            self->duration = realloc(self->duration, self->n_streams * sizeof (double));
            if (!(self->bos_offset && self->granule_count && self->serial))
                {
                fprintf(stderr, "oggscan_eos: malloc failure\n");
                self->n_streams = 0;
                return -1;
                }
          
            self->granule_count[self->n_streams - 1] = ogg_page_granulepos(&self->og);
            self->serial[self->n_streams - 1] = serial; 
            if (!eos)
                fprintf(stderr, "oggscan_eos: an unterminated stream was detected\n");
            return midpoint + retval;
            }
        
        /* seek to the right next time */
        return oggscan_eos(self, midpoint, offset_end, serial, depth);
        }
    else
        {
        if (midpoint >= offset_end)
            {
            fprintf(stderr, "oggscan_eos: warning, end of stream page appears to be missing for ogg serial %d\n", serial);
            return -1;
            }
        /* seek to the left next time */
        return oggscan_eos(self, offset, midpoint, serial, depth);
        }
    }

/* oggscan: linear search looking for beginnings of logical ogg bitstreams */
static off_t oggscan(struct oggdec_vars *self, off_t *offset, off_t offset_end)
    {
    char  *buffer;
    size_t bytes;
    int    serial;
    off_t  retval;
    
    fseeko(self->fp, *offset, SEEK_SET);
    
    ogg_sync_reset(&self->oy);
    while ((retval = ogg_sync_pageseek(&self->oy, &self->og)) <= 0 || ogg_page_bos(&self->og) == 0)
        {
        if (retval < 0)
            *offset -= retval;
        else
            if (retval == 0)
                {
                buffer = ogg_sync_buffer(&self->oy, 8192);
                bytes = fread(buffer, 1, 8192, self->fp);
                ogg_sync_wrote(&self->oy, bytes);
                if (bytes == 0)
                    return -1;     /* was offset_end */
                }
            else
                *offset += retval;
        }

    serial = ogg_page_serialno(&self->og);
    return oggscan_eos(self, *offset, offset_end, serial, 0);
    }

static struct oggdec_vars *oggdecode_get_metadata(char *pathname)
    {
    struct oggdec_vars *self;
    long   id3size = 0;
    off_t  offset = 0, offset_end, offset_new;
    size_t bytes;
    char  *buffer;
    int i;
    unsigned samplerate = 0;
    double start_time = 0.0;
    
    /* allocate storage space */
    if (!(self = calloc(1, sizeof (struct oggdec_vars))))
        {
        fprintf(stderr, "oggdecode_reg: malloc failure\n");
        return NULL;
        }
    
    self->magic = 4747;
    
    /* open the media file */
    if (!(self->fp = fopen(pathname, "r")))
        {
        fprintf(stderr, "oggdecode_reg: unable to open media file %s\n", pathname);
        free(self);
        return NULL;
        }

    /* jump past the ID3 version 2 tag if one is found */
    if (fgetc(self->fp) == 'I' && fgetc(self->fp) == 'D' && fgetc(self->fp) == '3' && fgetc(self->fp) != '\xFF' && fgetc(self->fp) != '\xFF')
        {
        fprintf(stderr, "ID3 tag detected\n");
        fgetc(self->fp);
        id3size =  fgetc(self->fp);
        id3size <<= 7;
        id3size |= fgetc(self->fp);
        id3size <<= 7;
        id3size |= fgetc(self->fp);
        id3size <<= 7;
        id3size |= fgetc(self->fp);
        offset += id3size;
        }

    if (ogg_sync_init(&self->oy))
        {
        fprintf(stderr, "oggdecode_reg: call to ogg_sync_init_failed\n");
        fclose(self->fp);
        free(self);
        return NULL;
        }
        
    if (ogg_stream_init(&self->os, 0))
        {
        fprintf(stderr, "oggdecode_reg: call to ogg_stream_init failed\n");
        ogg_sync_clear(&self->oy);
        fclose(self->fp);
        free(self);
        return NULL;
        }

    fseek(self->fp, 0, SEEK_END);
    offset_end = self->eos_offset = ftello(self->fp);

    while (offset < offset_end)
        {
        offset_new = oggscan(self, &offset, offset_end);
        
        if (offset_new == -1)
            break;
        self->bos_offset[self->n_streams -1] = offset;
        offset = offset_new;
        }

    for (self->ix = i = 0; i < self->n_streams; i++, self->ix++)
        {
        ogg_stream_reset_serialno(&self->os, self->serial[i]);
        fseeko(self->fp, self->bos_offset[i], SEEK_SET);
        ogg_sync_reset(&self->oy);
        while (ogg_sync_pageout(&self->oy, &self->og) != 1)
            {
            buffer = ogg_sync_buffer(&self->oy, 8192);
            bytes = fread(buffer, 1, 8192, self->fp);
            ogg_sync_wrote(&self->oy, bytes);
            }

        ogg_stream_pagein(&self->os, &self->og);
        ogg_stream_packetpeek(&self->os, &self->op);

        do {
            if (self->op.bytes >= 7 && !memcmp(self->op.packet, "\x01vorbis", 7))
                {
                self->streamtype[i] = ST_VORBIS;
                samplerate = vorbis_get_samplerate(self);
                break;
                }

#ifdef HAVE_OGGFLAC
            if (self->op.bytes >= 5 && !memcmp(self->op.packet, "\x7F""FLAC", 5))
                {
                self->streamtype[i] = ST_FLAC;
                fseeko(self->fp, self->bos_offset[i], SEEK_SET);
                samplerate = flac_get_samplerate(self);
                break;
                }
#endif /* HAVE_OGGFLAC */
#ifdef HAVE_SPEEX
            if (self->op.bytes >= 5 && !memcmp(self->op.packet, "Speex", 5))
                {
                self->streamtype[i] = ST_SPEEX;
                samplerate = speex_get_samplerate(self);
                break;
                }
#endif /* HAVE_SPEEX */
#ifdef HAVE_OPUS
            if (self->op.bytes >= 8 && !memcmp(self->op.packet, "OpusHead", 8))
                {
                self->streamtype[i] = ST_OPUS;
                samplerate = opus_get_samplerate(self);
                break;
                }
#endif /* HAVE_OPUS */

            self->streamtype[i] = ST_UNHANDLED;
            fprintf(stderr, "??? unhandled ogg stream type ???\n");
            } while (0);

        self->start_time[i] = start_time;
        if (samplerate == 0)
            {
            self->streamtype[i] = ST_UNHANDLED;
            self->duration[i] = 0;
            }
        else
            {
            start_time += self->duration[i] = self->granule_count[i] / (double)samplerate;
            self->total_duration += self->duration[i];
            }
#if 0
        fprintf(stderr,
            "#####################\n"
            "beginning offset %d\n"
            "granule_count    %d\n"
            "serial number    %d\n"
            "artist           %s\n"
            "title            %s\n"
            "album            %s\n"
            "samplerate       %d\n"
            "channels         %d\n"
            "start time (s)   %lf\n"
            "duration (s)     %lf\n",
            (int)self->bos_offset[i], self->granule_count[i],
            self->serial[i], self->artist[i], self->title[i], self->album[i], samplerate,
            self->channels[i], self->start_time[i], self->duration[i]);
#endif
        }
    fprintf(stderr, "total_duration   %lf\n", self->total_duration);
    return self;
    }

static void oggdecode_free_metadata(struct oggdec_vars *self)
    {
    int i;
    
    ogg_stream_clear(&self->os);
    ogg_sync_clear(&self->oy);
    fclose(self->fp);
    if (self->n_streams)
        {
        for (i = 0; i < self->n_streams; i++)
            {
            if (self->artist[i])
                free(self->artist[i]);
            if (self->title[i])
                free(self->title[i]);
            if (self->album[i])
                free(self->album[i]);
            }
            
        free(self->bos_offset);
        free(self->granule_count);
        free(self->serial);
        free(self->artist);
        free(self->title);
        free(self->album);
        free(self->streamtype);
        free(self->start_time);
        free(self->duration);
        }
    
    free(self);
    }

void oggdecode_seek_to_packet(struct oggdec_vars *self)
    {
    off_t start, end, mid;
    long retval;
    int target;
    ogg_int64_t granulepos = 0;
    char *buffer;
    size_t bytes;
     
    start = self->bos_offset[self->ix];
    if (self->ix == self->n_streams - 1)
        end = self->eos_offset;
    else
        end = self->bos_offset[self->ix + 1];
    target = self->seek_s * self->samplerate[self->ix];

    while (start + 1 < end)
        {
        mid = (end - start) / 2 + start;
        fseeko(self->fp, mid, SEEK_SET);
        ogg_sync_reset(&self->oy);

        for (;;)
            { 
            while ((retval = ogg_sync_pageseek(&self->oy, &self->og)) <= 0)
                {
                if (retval < 0)
                    {
                    if (mid > end)
                        {
                        fprintf(stderr, "ogg_vorbisdec_seek: mid > end ???\n");
                        return;
                        }
                    }
                else
                    {
                    buffer = ogg_sync_buffer(&self->oy, 8192);
                    bytes = fread(buffer, 1, 8192, self->fp);
                    ogg_sync_wrote(&self->oy, bytes);
                    if (bytes == 0)
                        {
                        fprintf(stderr, "ogg_vorbisdec_seek: unexpected file io error\n");
                        return;
                        }
                    }
                }

            if ((granulepos = ogg_page_granulepos(&self->og)) >= 0)
                break;
            }

        if (granulepos < target)
            start = mid + retval;
        else
            end = mid;
        }

    ogg_stream_reset(&self->os);
    }

void oggdecode_dynamic_dispatcher(struct xlplayer *xlplayer)
    {
    struct oggdec_vars *s = xlplayer->dec_data;
    int success = 0, delay;
    
    while (s->ix < s->n_streams)
        {
        /* skip over empty (read unplayable) streams */
        while (s->duration[s->ix] == 0.0)
            if (++(s->ix) >= s->n_streams)
                goto bugout;

        /* choose our decoder */
        switch (s->streamtype[s->ix])
            {
            case ST_VORBIS:
                success = ogg_vorbisdec_init(xlplayer);
                break;
            case ST_FLAC:
#ifdef HAVE_OGGFLAC
                success = ogg_flacdec_init(xlplayer);
#endif
                break;
            case ST_SPEEX:
#ifdef HAVE_SPEEX
                success = ogg_speexdec_init(xlplayer);
#endif
                break;
            case ST_OPUS:
#ifdef HAVE_OPUS
                success = ogg_opusdec_init(xlplayer);
#endif
                break;
            case ST_UNHANDLED:
            default:
                break;
            }

        if (success)
            {
            if (xlplayer->usedelay)
                delay = xlplayer_calc_rbdelay(xlplayer);
            else
                delay = 0;
            
            if (s->artist[s->ix][0] || s->title[s->ix][0])
                xlplayer_set_dynamic_metadata(xlplayer, DM_SPLIT_U8, s->artist[s->ix], s->title[s->ix], s->album[s->ix], delay);
            else
                {
                fprintf(stderr, "oggdecode_dynamic_dispatcher: insufficient metadata\n");
                xlplayer_set_dynamic_metadata(xlplayer, DM_NOTAG, "", "", "", delay);
                }
            
            xlplayer->usedelay = TRUE;
            return;
            }
        else
            {
            xlplayer->play_progress_ms += 1000 * (int32_t)(s->duration[s->ix] - s->seek_s);
            s->seek_s = 0.0;
            s->ix++;
            }
        }
 
    bugout:
    xlplayer->playmode = PM_EJECTING;
    }

static void oggdecode_eject(struct xlplayer *xlplayer)
    {
    struct oggdec_vars *self = xlplayer->dec_data;

    if (self->dec_cleanup)
        self->dec_cleanup(xlplayer);
    oggdecode_free_metadata(self);
    xlplayer->playmode = PM_STOPPED;
    }

static void oggdecode_init(struct xlplayer *xlplayer)
    {
    struct oggdec_vars *self = xlplayer->dec_data;
    int i;
    
    /* calculate where we seek to */
    for (i = 0; i < self->n_streams; i++)
        {
        if (self->start_time[i] <= xlplayer->seek_s && xlplayer->seek_s < self->start_time[i] + self->duration[i])
            {
            /* note which stream to play first and the time offset within */
            self->ix = i;
            self->seek_s = xlplayer->seek_s - self->start_time[i];
            break;
            }
        if (i + 1 >= self->n_streams)
            xlplayer->playmode = PM_EJECTING;
        }
    }

void oggdecode_set_new_oggpage_callback(struct oggdec_vars *self, void (*cb)(struct oggdec_vars *, void *), void *user_data)
    {
    self->new_oggpage_callback = cb;
    self->new_oggpage_cb_userdata = user_data;
    }

void oggdecode_remove_new_oggpage_callback(struct oggdec_vars *self)
    {
    self->new_oggpage_callback = NULL;
    self->new_oggpage_cb_userdata = NULL;
    }

void oggdecode_playnext(struct xlplayer *xlplayer)
    {
    struct oggdec_vars *od = xlplayer->dec_data;

    od->dec_cleanup(xlplayer); /* dispose of decoder */
    /* proceed with decoding the next stream */
    od->seek_s = 0.0;
    od->ix++;
    xlplayer->dec_play = oggdecode_dynamic_dispatcher;
    }

int oggdecode_reg(struct xlplayer *xlplayer)
    {
    struct oggdec_vars *self;

    if (!(self = oggdecode_get_metadata(xlplayer->pathname)))
        return REJECTED;
    else
        {
        self->xlplayer = xlplayer;
        xlplayer->dec_data = self;
        xlplayer->dec_init = oggdecode_init;
        xlplayer->dec_play = oggdecode_dynamic_dispatcher;
        xlplayer->dec_eject = oggdecode_eject;
        
        return ACCEPTED;
        }
    }

int oggdecode_get_metainfo(char *pathname, char **artist, char **title, char **album, double *length, char **replaygain)
    {
    struct oggdec_vars *self;
    int has_pbtime;
    
    if(!(self = oggdecode_get_metadata(pathname)))
        {
        fprintf(stderr, "call to oggdecode_get_metadata failed for %s\n", pathname);
        return REJECTED;
        }
        
    if ((has_pbtime = (*length = self->total_duration)))
        {
        if (self->n_streams > 1 && self->duration[0] > 0.1)
            {
            /* only read the initial tags of chained ogg streams when they
             * possess a metaheader */
            *artist = realloc(*artist, 1);
            *title  = realloc(*title, 1);
            *album  = realloc(*album, 1);
            *artist[0] = *title[0] = *album[0] = '\0';
            }
        else
            {
            if (self->artist[0])
                {
                if (*artist)
                    free(*artist);
                *artist = strdup(self->artist[0]);
                }
            else
                {
                *artist = realloc(*artist, 1);
                *artist[0] = '\0';
                }
        
            if (self->title[0])
                { 
                if (*title)
                    free(*title);
                *title = strdup(self->title[0]);
                }
            else
                {
                *title = realloc(*title, 1);
                *title[0] = '\0';
                }

            if (self->album[0])
                { 
                if (*album)
                    free(*album);
                *album = strdup(self->album[0]);
                }
            else
                {
                *album = realloc(*album, 1);
                *album[0] = '\0';
                }

            if (self->replaygain[0])
                {
                if (*replaygain)
                    free(*replaygain);
                *replaygain = strdup(self->replaygain[0]);
                }
            else
                {
                *replaygain = realloc(*replaygain, 1);
                *replaygain[0] = '\0';
                }
            }
        }

    oggdecode_free_metadata(self);
    return has_pbtime ? ACCEPTED : REJECTED;
    }
