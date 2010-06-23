/*
#   flacdecode.c: decodes flac file format for xlplayer
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
#ifdef HAVE_FLAC

#include <stdio.h>
#include <stdlib.h>
#include <FLAC/all.h>
#include <math.h>
#include "flacdecode.h"
#include "xlplayer.h"

#define TRUE 1
#define FALSE 0
#define ACCEPTED 1
#define REJECTED 0

void make_flac_audio_to_float(struct xlplayer *self, float *flbuf, const FLAC__int32 * const inputbuffer[], unsigned int numsamples, unsigned int bits_per_sample, unsigned int numchannels)
   {
   int sample, channel, shiftvalue = 32 - bits_per_sample;
   const float half_randmax = (float)(RAND_MAX >> 1);
   float dither;
   float dscale;
   
   if (!self->dither || bits_per_sample >= 20)
      {
      for (sample = 0; sample < numsamples; sample++)
         for (channel = 0; channel < numchannels; channel++)
            *flbuf++ = ((float)(inputbuffer[channel][sample] << shiftvalue)) / 2147483648.0F;
      }
   else
      {
      dscale = 0.25F / (half_randmax * powf(2.0F, (float)bits_per_sample));
      for (sample = 0; sample < numsamples; sample++)
         for (channel = 0; channel < numchannels; channel++)
            {
            dither = ((((float)rand_r(&self->seed)) - half_randmax) +
                     (((float)rand_r(&self->seed)) - half_randmax)) * dscale;
            *flbuf++ = ((float)(inputbuffer[channel][sample] << shiftvalue)) / 2147483648.0F + dither;
            }
      }
   }

#ifdef FLAC_PRE1_1_2
static FLAC__StreamDecoderWriteStatus flac_writer_callback(const FLAC__FileDecoder *decoder, const FLAC__Frame *frame, const FLAC__int32 * const inputbuffer[], void *client_data)
#endif
#ifdef FLAC_POST1_1_3
static FLAC__StreamDecoderWriteStatus flac_writer_callback(const FLAC__StreamDecoder *decoder, const FLAC__Frame *frame, const FLAC__int32 * const inputbuffer[], void *client_data)
#endif
   {
   struct xlplayer *xlplayer = client_data;
   struct flacdecode_vars *self = xlplayer->dec_data;
   SRC_DATA *src_data = &(xlplayer->src_data);
   int src_error;

   if (self->suppress_audio_output == FALSE)
      {
      if (xlplayer->src_state)
         {
         if (frame->header.number_type == FLAC__FRAME_NUMBER_TYPE_FRAME_NUMBER && frame->header.number.frame_number == 0)
            {
            fprintf(stderr, "flac_writer_callback: performance warning -- can't determine if a block is the last one or not for this file\n");
            }
         else
            {
            if (frame->header.number.sample_number + frame->header.blocksize == self->totalsamples)
               src_data->end_of_input = TRUE;
            }
         src_data->input_frames = frame->header.blocksize;
         src_data->data_in = realloc(src_data->data_in, src_data->input_frames * frame->header.channels * sizeof (float));
         src_data->output_frames = (int)(src_data->input_frames * src_data->src_ratio) + 2 + (512 * src_data->end_of_input);
         src_data->data_out = realloc(src_data->data_out, src_data->output_frames * frame->header.channels * sizeof (float));
         make_flac_audio_to_float(xlplayer, src_data->data_in, inputbuffer, frame->header.blocksize, frame->header.bits_per_sample, frame->header.channels);
         if ((src_error = src_process(xlplayer->src_state, src_data)))
            {
            fprintf(stderr, "flac_writer_callback: src_process reports %s\n", src_strerror(src_error));
            xlplayer->playmode = PM_EJECTING;
            return FLAC__STREAM_DECODER_WRITE_STATUS_ABORT;
            }
         xlplayer_demux_channel_data(xlplayer, src_data->data_out, src_data->output_frames_gen, frame->header.channels, 1.f);
         }
      else
         {
         if ((self->flbuf = realloc(self->flbuf, sizeof (float) * frame->header.blocksize * frame->header.channels)) == NULL)
            {
            fprintf(stderr, "flac_writer_callback: malloc failure\n");
            xlplayer->playmode = PM_EJECTING;
            return FLAC__STREAM_DECODER_WRITE_STATUS_ABORT;
            }
         make_flac_audio_to_float(xlplayer, self->flbuf, inputbuffer, frame->header.blocksize, frame->header.bits_per_sample, frame->header.channels);
         xlplayer_demux_channel_data(xlplayer, self->flbuf, frame->header.blocksize, frame->header.channels, 1.f);
         }
      xlplayer_write_channel_data(xlplayer);
      }
   return FLAC__STREAM_DECODER_WRITE_STATUS_CONTINUE;
   }

#ifdef FLAC_PRE1_1_2
static void flac_metadata_callback(const FLAC__FileDecoder *decoder, const FLAC__StreamMetadata *md, void *client_data)
   {
   /* do nothing with the metadata */
   }
#endif

#ifdef FLAC_PRE1_1_2
static void flac_error_callback(const FLAC__FileDecoder *decoder,FLAC__StreamDecoderErrorStatus se, void *client_data)
#endif
#ifdef FLAC_POST1_1_3
static void flac_error_callback(const FLAC__StreamDecoder *decoder,FLAC__StreamDecoderErrorStatus se, void *client_data)
#endif
   {
   struct xlplayer *xlplayer = client_data;
         
   switch (se)
      {
      case FLAC__STREAM_DECODER_ERROR_STATUS_LOST_SYNC:
         fprintf(stderr, "xlplayer: %s: flac decoder error: lost sync\n%s\n", xlplayer->playername, xlplayer->pathname);
         break;
      case FLAC__STREAM_DECODER_ERROR_STATUS_BAD_HEADER:
         fprintf(stderr, "xlplayer: %s: flac decoder error: bad header\n%s\n", xlplayer->playername, xlplayer->pathname);
         break;
      case FLAC__STREAM_DECODER_ERROR_STATUS_FRAME_CRC_MISMATCH:
         fprintf(stderr, "xlplayer: %s: flac decoder error: frame crc mismatch\n%s\n", xlplayer->playername, xlplayer->pathname);
         break;
      default:
         fprintf(stderr, "xlplayer: %s: flac decoder error: unknown error\n%s\n", xlplayer->playername, xlplayer->pathname);
      }
   }

static void flacdecode_init(struct xlplayer *xlplayer)
   {
   struct flacdecode_vars *self = xlplayer->dec_data;
   int src_error;
   
#ifdef FLAC_PRE1_1_2
   if (!(self->decoder = FLAC__file_decoder_new()))
      {
      fprintf(stderr, "flacdecode_init: %s could not initialise flac decoder\n", xlplayer->playername);
      goto cleanup;
      }
   FLAC__file_decoder_set_client_data(self->decoder, xlplayer);
   FLAC__file_decoder_set_write_callback(self->decoder, flac_writer_callback);
   FLAC__file_decoder_set_error_callback(self->decoder, flac_error_callback);
   FLAC__file_decoder_set_metadata_callback(self->decoder, flac_metadata_callback);
   FLAC__file_decoder_set_filename(self->decoder, xlplayer->pathname);
   if ((self->decoderstate = FLAC__file_decoder_init(self->decoder)) != FLAC__FILE_DECODER_OK)
      {
      fprintf(stderr, "flacdecode_init: %s error during flac player initialisation\n", xlplayer->playername);
      FLAC__file_decoder_delete(self->decoder);
      goto cleanup;
      }
   if (xlplayer->seek_s)
      {
      self->suppress_audio_output = TRUE;               /* prevent seek noise */
      FLAC__file_decoder_seek_absolute(self->decoder, ((FLAC__uint64)xlplayer->seek_s) * ((FLAC__uint64)self->metainfo.data.stream_info.sample_rate));
      self->suppress_audio_output = FALSE;
      }
#endif
#ifdef FLAC_POST1_1_3
   if (!(self->decoder = FLAC__stream_decoder_new()))
      {
      fprintf(stderr, "flacdecode_init: %s could not initialise flac decoder\n", xlplayer->playername);
      goto cleanup;
      }
   if (FLAC__stream_decoder_init_file(self->decoder, xlplayer->pathname, flac_writer_callback, NULL, flac_error_callback, xlplayer) != FLAC__STREAM_DECODER_INIT_STATUS_OK)
      {
      fprintf(stderr, "flacdecode_init: %s error during flac player initialisation\n", xlplayer->playername);
      FLAC__stream_decoder_delete(self->decoder);
      goto cleanup;
      }
   if (xlplayer->seek_s)
      {
      self->suppress_audio_output = TRUE;               /* prevent seek noise */
      FLAC__stream_decoder_seek_absolute(self->decoder, ((FLAC__uint64)xlplayer->seek_s) * ((FLAC__uint64)self->metainfo.data.stream_info.sample_rate));
      self->suppress_audio_output = FALSE;
      }
#endif
   if ((self->resample_f = (self->metainfo.data.stream_info.sample_rate != xlplayer->samplerate)))
      {
      fprintf(stderr, "flacdecode_init: %s configuring resampler\n", xlplayer->playername);
      xlplayer->src_state = src_new(xlplayer->rsqual, self->metainfo.data.stream_info.channels, &src_error);
      if (src_error)
         {
         fprintf(stderr, "flacdecode_init: %s src_new reports - %s\n", xlplayer->playername, src_strerror(src_error));
#ifdef FLAC_PRE1_1_2
         FLAC__file_decoder_delete(self->decoder);
#endif
#ifdef FLAC_POST1_1_3
         FLAC__stream_decoder_delete(self->decoder);
#endif
         goto cleanup;
         }
      xlplayer->src_data.output_frames = 0;
      xlplayer->src_data.data_in = xlplayer->src_data.data_out = NULL;
      xlplayer->src_data.src_ratio = (double)xlplayer->samplerate / (double)self->metainfo.data.stream_info.sample_rate;
      xlplayer->src_data.end_of_input = 0;
      self->totalsamples = self->metainfo.data.stream_info.total_samples; 
      }
   else
      xlplayer->src_state = NULL;
   self->suppress_audio_output = FALSE;
   self->flbuf = NULL;
   return;
cleanup:
   free(self);
   xlplayer->playmode = PM_STOPPED;
   xlplayer->command = CMD_COMPLETE;
   }

static void flacdecode_play(struct xlplayer *xlplayer)
   {
   struct flacdecode_vars *self = xlplayer->dec_data;

#ifdef FLAC_PRE1_1_2
   FLAC__file_decoder_process_single(self->decoder);
   if (FLAC__file_decoder_get_state(self->decoder) != FLAC__FILE_DECODER_OK) 
      xlplayer->playmode = PM_EJECTING;
#endif
#ifdef FLAC_POST1_1_3
   FLAC__stream_decoder_process_single(self->decoder);
   if (FLAC__stream_decoder_get_state(self->decoder) == FLAC__STREAM_DECODER_END_OF_STREAM)
      xlplayer->playmode = PM_EJECTING;
#endif
   }

static void flacdecode_eject(struct xlplayer *xlplayer)
   {
   struct flacdecode_vars *self = xlplayer->dec_data;

#ifdef FLAC_PRE1_1_2
   FLAC__file_decoder_finish(self->decoder);
   FLAC__file_decoder_delete(self->decoder);
#endif
#ifdef FLAC_POST1_1_3
   FLAC__stream_decoder_finish(self->decoder);
   FLAC__stream_decoder_delete(self->decoder);
#endif
   if (self->flbuf)
      free(self->flbuf);
   if (self->resample_f)
      {
      free(xlplayer->src_data.data_in);
      free(xlplayer->src_data.data_out);
      xlplayer->src_state = src_delete(xlplayer->src_state);
      }
   free(self);
   }

int flacdecode_reg(struct xlplayer *xlplayer)
   {
   struct flacdecode_vars *self;
   
   if (!(self = xlplayer->dec_data = malloc(sizeof (struct flacdecode_vars))))
      {
      fprintf(stderr, "flacdecode_reg: malloc failure\n");
      return REJECTED;
      }
   if (FLAC__metadata_get_streaminfo(xlplayer->pathname, &(self->metainfo)))
      {
      xlplayer->dec_init = flacdecode_init;
      xlplayer->dec_play = flacdecode_play;
      xlplayer->dec_eject = flacdecode_eject;
      return ACCEPTED;
      }
   return REJECTED;
   }
#endif
