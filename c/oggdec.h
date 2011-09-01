/*
#   oggdec.h: ogg file parser/decoder for xlplayer
#   Copyright (C) 2008-2009 Stephen Fairchild (s-fairchild@users.sourceforge.net)
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
#include <ogg/ogg.h>
#include "xlplayer.h"

enum streamtype_t { ST_UNHANDLED, ST_VORBIS, ST_FLAC, ST_SPEEX };

struct oggdec_vars
   {
   int magic;              /* 4545 */
   FILE  *fp;              /* file handle */
   double seek_s;          /* time offset for first stream to be played */
   void *dec_data;         /* decoder state variables live here */
   void (*dec_cleanup)(struct xlplayer *xlplayer); /* decoder cleanup function */
   struct xlplayer *xlplayer;

   ogg_sync_state   oy;    /* various ogg decoding variables */
   ogg_page         og;
   ogg_stream_state os;
   ogg_packet       op;

   /* a callback routine for when a new ogg page is obtained */
   void (*new_oggpage_callback)(struct oggdec_vars *self, void *cb_userdata);
   void *new_oggpage_cb_userdata;

   /* stream info */

   off_t  *bos_offset;      /* file position where each stream starts */
   unsigned *granule_count;   /* number of samples in this stream */
   int    *serial;          /* the ogg serial numbers */
   unsigned *samplerate;    /* sample rate per channel */
   int    *channels;        /* number of audio channels */
   char  **artist;          /* artist and title metadata */
   char  **title;
   char  **album;
   char  **replaygain;      /* specifically replaygain_track_gain */
   enum streamtype_t *streamtype;    /* indicate which type ie vorbis, flac */
   double *start_time;      /* the time when each stream starts */
   double *duration;        /* playback time */
   int     n_streams;       /* number of logical streams found */
   int     ix;              /* index of the stream of interest */
   off_t   eos_offset;      /* offset to the end of file */
   double  total_duration;  /* sum total playback time */
   };

int oggdecode_reg(struct xlplayer *xlplayer);
int oggdecode_get_metainfo(char *pathname, char **artist, char **title, char **album, double *length, char **replaygain);
int oggdec_get_next_packet(struct oggdec_vars *self);
void oggdecode_dynamic_dispatcher(struct xlplayer *xlplayer);
void oggdecode_playnext(struct xlplayer *xlplayer);
void oggdecode_seek_to_packet(struct oggdec_vars *self);
void oggdecode_set_new_oggpage_callback(struct oggdec_vars *self, void (*cb)(struct oggdec_vars *, void *), void *user_data);
void oggdecode_remove_new_oggpage_callback(struct oggdec_vars *self);

#ifdef HAVE_OGGFLAC
#ifdef FLAC_POST1_1_3

FLAC__StreamDecoderReadStatus oggflac_read_callback(const FLAC__StreamDecoder *decoder, FLAC__byte buffer[], size_t *bytes, void *client_data);

FLAC__StreamDecoderSeekStatus oggflac_seek_callback(const FLAC__StreamDecoder *decoder, FLAC__uint64 absolute_byte_offset, void *client_data);

FLAC__StreamDecoderTellStatus oggflac_tell_callback(const FLAC__StreamDecoder *decoder, FLAC__uint64 *absolute_byte_offset, void *client_data);

FLAC__StreamDecoderLengthStatus oggflac_length_callback(const FLAC__StreamDecoder *decoder, FLAC__uint64 *stream_length, void *client_data);

FLAC__bool oggflac_eof_callback(const FLAC__StreamDecoder *decoder, void *client_data);

void oggflac_error_callback(const FLAC__StreamDecoder *decoder, FLAC__StreamDecoderErrorStatus se, void *client_data);

#endif /* FLAC_POST1_1_3 */
#endif /* HAVE_OGGFLAC */
