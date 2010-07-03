/*
#   live_mp3_encoder.c: encode mp3 files from a live source
#   Copyright (C) 2007 Stephen Fairchild (s-fairchild@users.sourceforge.net)
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
#include <jack/ringbuffer.h>
#include "sourceclient.h"
#include "live_mp3_encoder.h"

#define READSIZE 1024

typedef jack_default_audio_sample_t sample_t;

static void live_mp3_build_metadata(struct encoder *encoder, struct lme_data *s)
   {
   char *r, *w, *e, *marker;    /* read, write, end, the placemarker string */
   int count;   /* the number of occurrences of marker in metaformat */
   int len;     /* the length of the substitute string */
   size_t size;

   if (s->metadata)
      free(s->metadata);
   pthread_mutex_lock(&encoder->metadata_mutex);
   for (count = 0, r = encoder->metaformat_mp3; (r = strstr(r, "%s")); count++, r += 2);
   if (count == 0)
      s->metadata = strdup(encoder->metaformat_mp3);
   else
      { 
      /* handle metadata only contains artist - title */
      if (count == 1 && !strcmp(encoder->metaformat_mp3, "%s"))
         {
         if (encoder->artist_title_mp3)
            s->metadata = strdup(encoder->artist_title_mp3);
         else
            s->metadata = strdup("");
         }
      else
         {
         /* handle a mix of possible multiple "artist - title" and or other text */
         /* in python: artist_title = metaformat.replace("%s", artist_title) */
         /* in C see below LOL */
         s->metadata = malloc(size = count * strlen(encoder->artist_title_mp3) + strlen(encoder->metaformat_mp3) - count * strlen(marker = "%s") + 1);
         if (!s->metadata)
            fprintf(stderr, "live_mp3_build_metadata: malloc failure\n");
         else
            {
            len = strlen(encoder->artist_title_mp3);
            r = encoder->metaformat_mp3;
            w = s->metadata;
            for (;;)
               {
               if ((e = strstr(r, marker)))
                  {
                  memcpy(w, r, e - r);  /* copy the text before the %s */
                  w += e - r;           /* advance write pointer */
                  memcpy(w, encoder->artist_title_mp3, len); /* copy artist - title */
                  w += len;             /* advance the write pointer */
                  r = e + 2;            /* skip over the %s */
                  }
               else
                  {
                  strcpy(w, r); /* copy the remaining text and null terminate */
                  break;        /* finished */
                  }
               }
            }
         if (strlen(s->metadata) != size - 1)
            fprintf(stderr, "WARNING live_mp3_build_metadata: size allocated does not match data\n");
         }
      }
   encoder->new_metadata = FALSE;
   pthread_mutex_unlock(&encoder->metadata_mutex);
   fprintf(stderr, "live_mp3_build_metadata: metadata for encoder %d\nmetadata=%s\n", encoder->numeric_id, s->metadata);
   }

static int live_mp3_write_packet(struct encoder *encoder, struct lme_data *s, unsigned char *buffer, size_t buffersize, int flags)
   {
   struct encoder_op_packet packet;

   packet.header.bit_rate = encoder->bitrate;
   packet.header.sample_rate = encoder->target_samplerate;
   packet.header.n_channels = encoder->n_channels;
   packet.header.flags = flags;
   packet.header.data_size = buffersize;
   packet.header.serial = encoder->oggserial;
   packet.header.timestamp = encoder->timestamp = s->lame_samples / (double)encoder->target_samplerate;
   packet.data = buffer;
   encoder_write_packet_all(encoder, &packet);
   return 1;
   }

static void live_mp3_encoder_main(struct encoder *encoder)
   {
   struct lme_data * const s = encoder->encoder_private;
   struct encoder_ip_data *id;
   int mp3bytes = 0;
   float *l, *r, *endp;

   if (encoder->encoder_state == ES_STARTING)
      {
      if (!(s->mp3buf = malloc(s->mp3bufsize = (int)(1.25 * 8192.0 + 7200.0))))
         {
         fprintf(stderr, "live_mp3_encoder_main: malloc failure\n");
         goto bailout;
         }
      if (!(s->gfp = lame_init()))
         {
         fprintf(stderr, "live_mp3_encoder_main: failed to initialise LAME\n");
         free(s->mp3buf);
         goto bailout;
         }
      lame_set_num_channels(s->gfp, encoder->n_channels);
      lame_set_brate(s->gfp, encoder->bitrate);
      lame_set_in_samplerate(s->gfp, encoder->target_samplerate);
      lame_set_out_samplerate(s->gfp, encoder->target_samplerate);
      lame_set_mode(s->gfp, s->lame_mode);
      lame_set_quality(s->gfp, s->lame_quality);
      lame_set_free_format(s->gfp, s->lame_freeformat);
      lame_set_bWriteVbrTag(s->gfp, 0);
      if (lame_init_params(s->gfp) < 0)
         {
         fprintf(stderr, "live_mp3_encoder_main: LAME rejected the parameters given\n");
         lame_close(s->gfp);
         free(s->mp3buf);
         goto bailout;
         }

      ++encoder->oggserial;
      s->packetflags = PF_INITIAL;
      s->lame_samples = 0;
      if (encoder->run_request_f)
         encoder->encoder_state = ES_RUNNING;
      else
         encoder->encoder_state = ES_STOPPING;
      return;
      }
   if (encoder->encoder_state == ES_RUNNING)
      {
      if (!(encoder->watchdog_info.tick & 127))
         fprintf(stderr, "encoder %d running\n", encoder->numeric_id);
      if (encoder->flush || !encoder->run_request_f)
         {
         encoder->flush = FALSE;
         mp3bytes = lame_encode_flush_nogap(s->gfp, s->mp3buf, s->mp3bufsize);
         fprintf(stderr, "live_mp3_encoder_main: flushing %d bytes\n", mp3bytes);
         live_mp3_write_packet(encoder, s, s->mp3buf, mp3bytes, PF_MP3 | PF_FINAL);
         encoder->encoder_state = ES_STOPPING;
         }
      else
         {
         if ((id = encoder_get_input_data(encoder, 1024, 8192, NULL)))
            {
            if (id->channels == 1)      /* mono and stereo audio rescaling */
               for (l = id->buffer[0], endp = l + id->qty_samples; l < endp;)
                  *l++ *= 32768.0F;
            else
               for (l = id->buffer[0], r = id->buffer[1], endp = l + id->qty_samples; l < endp;)
                  {
                  *l++ *= 32768.0F;
                  *r++ *= 32768.0F;
                  }
            mp3bytes = lame_encode_buffer_float(s->gfp, id->buffer[0], id->buffer[1], id->qty_samples, s->mp3buf, s->mp3bufsize);
            encoder_ip_data_free(id);
            s->lame_samples += id->qty_samples;
            live_mp3_write_packet(encoder, s, s->mp3buf, mp3bytes, PF_MP3 | s->packetflags);
            s->packetflags = PF_UNSET;
            }
         if (encoder->new_metadata)
            {
            live_mp3_build_metadata(encoder, s);
            if (s->metadata)
               live_mp3_write_packet(encoder, s, (unsigned char *)s->metadata, strlen(s->metadata) + 1, PF_METADATA | s->packetflags);
            s->packetflags = PF_UNSET;
            }
         }
      return;
      }
   if (encoder->encoder_state == ES_STOPPING)
      {
      lame_close(s->gfp);
      free(s->mp3buf);
      if (encoder->run_request_f)
         {
         encoder->encoder_state = ES_STARTING;
         return;
         }
      }
   bailout:
   fprintf(stderr, "live_mp3_encoder_main: performing cleanup\n");
   encoder->run_request_f = FALSE;
   encoder->encoder_state = ES_STOPPED;
   encoder->run_encoder = NULL;
   encoder->flush = FALSE;
   encoder->encoder_private = NULL;
   free(s);
   fprintf(stderr, "live_mp3_encoder_main: finished cleanup\n");
   }

int live_mp3_encoder_init(struct encoder *encoder, struct encoder_vars *ev)
   {
   struct lme_data * const s = calloc(1, sizeof (struct lme_data));

   if (!s)
      {
      fprintf(stderr, "live_mp3_encoder: malloc failure\n");
      return FAILED;
      }
   if (!(strcmp("stereo", ev->stereo)))
      s->lame_mode = 0;
   else if (!(strcmp("jstereo", ev->stereo)))
      s->lame_mode = 1;
   else if (!(strcmp("mono", ev->stereo)))
      s->lame_mode = 3;
   s->lame_quality = atoi(ev->encode_quality);
   s->lame_freeformat = ev->freeformat_mp3[0] == '1';
   encoder->encoder_private = s;
   encoder->run_encoder = live_mp3_encoder_main;
   return SUCCEEDED;
   }

