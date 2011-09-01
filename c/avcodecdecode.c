/*
#   avcodecdecode.c: decodes wma file format for xlplayer
#   Copyright (C) 2007, 2011 Stephen Fairchild (s-fairchild@users.sourceforge.net)
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

#ifdef HAVE_AVCODEC
#ifdef HAVE_AVFORMAT
#ifdef HAVE_AVUTIL

#include <stdio.h>
#include <stdlib.h>
#include <pthread.h>
#include "xlplayer.h"
#include "avcodecdecode.h"

#define TRUE 1
#define FALSE 0
#define ACCEPTED 1
#define REJECTED 0

static pthread_once_t once_control = PTHREAD_ONCE_INIT;
static pthread_mutex_t mutex;

void once_init()
   {
   pthread_mutex_init(&mutex, NULL);
   avcodec_init();
   avcodec_register_all();
   av_register_all();
   }

static void avcodecdecode_eject(struct xlplayer *xlplayer)
   {
   struct avcodecdecode_vars *self = xlplayer->dec_data;
   
   if (self->resample)
      {
      xlplayer->src_state = src_delete(xlplayer->src_state);
      free(xlplayer->src_data.data_out);
      }
   if (self->outbuf)
      free(self->outbuf);
   if (self->floatsamples)
      free(self->floatsamples);
   pthread_mutex_lock(&mutex);
   avcodec_close(self->c);
   pthread_mutex_unlock(&mutex);
   av_close_input_file(self->ic);
   }

static void avcodecdecode_init(struct xlplayer *xlplayer)
   {
   struct avcodecdecode_vars *self = xlplayer->dec_data;
   int src_error;
   
   if (xlplayer->seek_s)
      {
      av_seek_frame(self->ic, -1, (int64_t)xlplayer->seek_s * AV_TIME_BASE, 0);
      switch (self->c->codec_id)
         {
         case CODEC_ID_MUSEPACK7:   /* add formats here that glitch when seeked */
#ifdef CODEC_ID_MUSEPACK8
         case CODEC_ID_MUSEPACK8:
#endif /* CODEC_ID_MUSEPACK8 */
            self->drop = 1.6;
            fprintf(stderr, "dropping %0.2f seconds of audio\n", self->drop);
         default:
            break;
         }
      }
   if ((self->resample = (self->c->sample_rate != (int)xlplayer->samplerate)))
      {
      fprintf(stderr, "configuring resampler\n");
      xlplayer->src_data.src_ratio = (double)xlplayer->samplerate / (double)self->c->sample_rate;
      xlplayer->src_data.end_of_input = 0;
      xlplayer->src_data.data_in = self->floatsamples;
      xlplayer->src_data.output_frames = (AVCODEC_MAX_AUDIO_FRAME_SIZE / 2 * xlplayer->src_data.src_ratio + 512) / self->c->channels;
      if (!(xlplayer->src_data.data_out = malloc(AVCODEC_MAX_AUDIO_FRAME_SIZE * 2 * xlplayer->src_data.src_ratio + 512)))
         {
         fprintf(stderr, "avcodecdecode_init: malloc failure\n");
         self->resample = FALSE;
         avcodecdecode_eject(xlplayer);
         xlplayer->playmode = PM_STOPPED;
         xlplayer->command = CMD_COMPLETE;
         return;
         }
      if ((xlplayer->src_state = src_new(xlplayer->rsqual, self->c->channels, &src_error)), src_error)
         {
         fprintf(stderr, "avcodecdecode_init: src_new reports %s\n", src_strerror(src_error));
         free(xlplayer->src_data.data_out);
         self->resample = FALSE;
         avcodecdecode_eject(xlplayer);
         xlplayer->playmode = PM_STOPPED;
         xlplayer->command = CMD_COMPLETE;
         return;
         }
      }
fprintf(stderr, "avcodecdecode_init: completed\n");
   }
   
static void avcodecdecode_play(struct xlplayer *xlplayer)
   {
   struct avcodecdecode_vars *self = xlplayer->dec_data;
   AVPacket pkt, pktcopy;
   int size, out_size, len, frames, channels = self->c->channels, ret;
   uint8_t *inbuf_ptr;
   SRC_DATA *src_data = &xlplayer->src_data;
   
   if ((ret = av_read_frame(self->ic, &pkt)) < 0 || (size = pkt.size) == 0)
      {
      if (pkt.data)
         av_free_packet(&pkt);

      if (self->resample)       /* flush the resampler */
         {
         src_data->end_of_input = TRUE;
         src_data->input_frames = 0;
         if (src_process(xlplayer->src_state, src_data))
            {
            fprintf(stderr, "avcodecdecode_play: error occured during resampling\n");
            xlplayer->playmode = PM_EJECTING;
            return;
            }
         xlplayer_demux_channel_data(xlplayer, src_data->data_out, src_data->output_frames_gen, channels, 1.f);
         xlplayer_write_channel_data(xlplayer);
         }
      xlplayer->playmode = PM_EJECTING;
      return;
      }
   inbuf_ptr = pkt.data;
   pktcopy = pkt;

   if (pkt.stream_index != (int)self->stream)
      {
      if (pkt.data)
         av_free_packet(&pkt);
      return;
      }

   while(size > 0 && xlplayer->command != CMD_EJECT)
      {
      out_size = AVCODEC_MAX_AUDIO_FRAME_SIZE;
      pthread_mutex_lock(&mutex);
#ifdef DECODE_AUDIO_3
      len = avcodec_decode_audio3(self->c, (short *)self->outbuf, &out_size, &pktcopy);
#else
      len = avcodec_decode_audio2(self->c, (short *)self->outbuf, &out_size, inbuf_ptr, size);
#endif
      pthread_mutex_unlock(&mutex);
      frames = (out_size >> 1) / channels;

      if (len < 0)
         {
         fprintf(stderr, "avcodecdecode_play: error during decode\n");
         break;
         }

      pktcopy.data += len;
      pktcopy.size -= len;
      inbuf_ptr += len;
      size -= len;

      if (out_size <= 0)
         {
         continue;
         }

      xlplayer_make_audio_to_float(xlplayer, self->floatsamples, self->outbuf, frames, 16, channels); 
      if (self->resample)
         {
         src_data->input_frames = frames;
         if (src_process(xlplayer->src_state, src_data))
            {
            fprintf(stderr, "avcodecdecode_play: error occured during resampling\n");
            xlplayer->playmode = PM_EJECTING;
            return;
            }
         xlplayer_demux_channel_data(xlplayer, src_data->data_out, frames = src_data->output_frames_gen, channels, 1.f);
         }
      else
         xlplayer_demux_channel_data(xlplayer, self->floatsamples, frames, channels, 1.f);
      if (self->drop > 0)
         self->drop -= frames / (float)xlplayer->samplerate;
      else
         {
         do {
            xlplayer_write_channel_data(xlplayer);
            } while(xlplayer->write_deferred && xlplayer->command != CMD_EJECT);
         }
      }

   if (pkt.data)
      av_free_packet(&pkt);
   }
   
int avcodecdecode_reg(struct xlplayer *xlplayer)
   {
   struct avcodecdecode_vars *self;
   int error;
   
   pthread_once(&once_control, once_init);
   if (!(xlplayer->dec_data = self = calloc(1, sizeof (struct avcodecdecode_vars))))
      {
      fprintf(stderr, "avcodecdecode_reg: malloc failure\n");
      return REJECTED;
      }
   else
      xlplayer->dec_data = self;
   
   if (avformat_open_input(&self->ic, xlplayer->pathname, NULL, NULL) < 0)
      {
      fprintf(stderr, "avcodecdecode_reg: failed to open input file %s\n", xlplayer->pathname);
      free(self);
      return REJECTED;
      }
   
   for(self->stream = 0; self->stream < self->ic->nb_streams; self->stream++)
      {
      self->c = self->ic->streams[self->stream]->codec;
      if(self->c->codec_type == AVMEDIA_TYPE_AUDIO)
         break;
      }

   if (self->stream == self->ic->nb_streams)
      {
      fprintf(stderr, "avcodecdecode_reg: codec not found 1\n");
      av_close_input_file(self->ic);
      free(self);
      return REJECTED;
      }
   
   av_find_stream_info(self->ic);

   pthread_mutex_lock(&mutex);
   self->codec = avcodec_find_decoder(self->c->codec_id);
   pthread_mutex_unlock(&mutex);
   if (!self->codec)
      {
      fprintf(stderr, "avcodecdecode_reg: codec not found 2\n");
      av_close_input_file(self->ic);
      free(self);
      return REJECTED;
      }
   
   pthread_mutex_lock(&mutex);
   if (avcodec_open(self->c, self->codec) < 0)
      {
      pthread_mutex_unlock(&mutex);
      fprintf(stderr, "avcodecdecode_reg: could not open codec\n");
      av_close_input_file(self->ic);
      free(self);
      return REJECTED;
      }
   pthread_mutex_unlock(&mutex);
    
   error = posix_memalign((void *)&self->outbuf, 64, AVCODEC_MAX_AUDIO_FRAME_SIZE);
   self->floatsamples = malloc(AVCODEC_MAX_AUDIO_FRAME_SIZE * 2);
   if (error || !self->floatsamples)
      {
      fprintf(stderr, "avcodecdecode_reg: malloc failure\n");
      avcodecdecode_eject(xlplayer);
      return REJECTED;
      }
   
   xlplayer->dec_init = avcodecdecode_init;
   xlplayer->dec_play = avcodecdecode_play;
   xlplayer->dec_eject = avcodecdecode_eject;
   
fprintf(stderr, "avcodecdecode_reg: registered\n");

   return ACCEPTED;
   }

void avformatinfo(char *pathname)
   {
   AVFormatContext *ic = NULL;
   AVDictionary *mc;
   AVDictionaryEntry *tag;
   const int flags = AV_METADATA_DONT_STRDUP_KEY | AV_METADATA_DONT_STRDUP_VAL;
   char *keys[] = {"artist", "title", "album", NULL}, **kp;
   
   pthread_once(&once_control, once_init);
   if (avformat_open_input(&ic, pathname, NULL, NULL) >= 0)
      {
      av_find_stream_info(ic);
      mc = ic->metadata;

      for(kp = keys; *kp; kp++)
         {
         if ((tag = av_dict_get(mc, *kp, NULL, flags)))
            printf("avformatinfo: %s=%s\n", tag->key, tag->value);
         }
     
      printf("avformatinfo: duration=%d\n", (int)(ic->duration / AV_TIME_BASE));
      av_close_input_file(ic);
      }
   printf("avformatinfo: end\n");
   fflush(stdout);
   }
   
#endif /* HAVE_AVUTIL */
#endif /* HAVE_AVFORMAT */
#endif /* HAVE_AVCODEC */
