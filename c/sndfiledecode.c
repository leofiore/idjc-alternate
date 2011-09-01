/*
#   sndfiledecode.c: decodes wav file format for xlplayer
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

#include <stdio.h>
#include <string.h>
#include <sndfile.h>
#include "xlplayer.h"
#include "sndfiledecode.h"

#define TRUE 1
#define FALSE 0
#define ACCEPTED 1
#define REJECTED 0

static const sf_count_t sndfile_frameqty = 4096;

static void sndfiledecode_init(struct xlplayer *xlplayer)
   {
   struct sndfiledecode_vars *self = xlplayer->dec_data;
   int src_error;
   
   if (!(self->flbuf = malloc(sizeof (float) * sndfile_frameqty * self->sf_info.channels)))
      {
      fprintf(stderr, "sndfiledecode_init: unable to allocate sndfile frames buffer\n");
      sf_close(self->sndfile);
      xlplayer->playmode = PM_STOPPED;
      xlplayer->command = CMD_COMPLETE;
      return;
      }
   if (self->sf_info.samplerate != (int)xlplayer->samplerate)
      {
      fprintf(stderr, "sndfiledecode_init: configuring resampler\n");
      xlplayer->src_state = src_new(xlplayer->rsqual, self->sf_info.channels, &src_error);
      if (src_error)
         {
         fprintf(stderr, "sndfiledecode_init: %s src_new reports - %s\n", xlplayer->playername, src_strerror(src_error));
         sf_close(self->sndfile);
         xlplayer->playmode = PM_STOPPED;
         xlplayer->command = CMD_COMPLETE;
         return;
         }
      xlplayer->src_data.output_frames = 0;
      xlplayer->src_data.data_in = self->flbuf;
      xlplayer->src_data.data_out = NULL;
      xlplayer->src_data.src_ratio = (double)xlplayer->samplerate / (double)self->sf_info.samplerate;
      xlplayer->src_data.end_of_input = 0;
      self->resample = TRUE;
      }
   else
      self->resample = FALSE;
   sf_seek(self->sndfile, ((sf_count_t)xlplayer->seek_s) * ((sf_count_t)self->sf_info.samplerate), SEEK_SET);
   }
   
static void sndfiledecode_play(struct xlplayer *xlplayer)
   {
   struct sndfiledecode_vars *self = xlplayer->dec_data;
   sf_count_t sf_count;
   int src_error;

   sf_count = sf_readf_float(self->sndfile, self->flbuf, sndfile_frameqty);
   if (self->resample)
      {
      xlplayer->src_data.end_of_input = (sf_count == 0);
      xlplayer->src_data.input_frames = sf_count;
      xlplayer->src_data.output_frames = (int)(xlplayer->src_data.input_frames * xlplayer->src_data.src_ratio) + 2 + (512 * xlplayer->src_data.end_of_input);
      xlplayer->src_data.data_out = realloc(xlplayer->src_data.data_out, xlplayer->src_data.output_frames * self->sf_info.channels * sizeof (float));
      if ((src_error = src_process(xlplayer->src_state, &(xlplayer->src_data))))
         {
         fprintf(stderr, "sndfiledecode_play: %s\n", src_strerror(src_error));
         xlplayer->playmode = PM_EJECTING;
         return;
         }
      xlplayer_demux_channel_data(xlplayer, xlplayer->src_data.data_out, xlplayer->src_data.output_frames_gen, self->sf_info.channels, 1.f);
      }
   else
      xlplayer_demux_channel_data(xlplayer, self->flbuf, sf_count, self->sf_info.channels, 1.f);
   xlplayer_write_channel_data(xlplayer);
   if (sf_count == 0)
      {
      xlplayer->playmode = PM_EJECTING;
      return;
      }
   }
   
static void sndfiledecode_eject(struct xlplayer *xlplayer)
   {
   struct sndfiledecode_vars *self = xlplayer->dec_data;
   
   sf_close(self->sndfile);
   if (self->resample)
      {
      if (xlplayer->src_data.data_out)
         free(xlplayer->src_data.data_out);
      xlplayer->src_state = src_delete(xlplayer->src_state);
      }
   free(self->flbuf);
   free(self);
   }

int sndfiledecode_reg(struct xlplayer *xlplayer)
   {
   struct sndfiledecode_vars *self;
   
   if (!(self = xlplayer->dec_data = malloc(sizeof (struct sndfiledecode_vars))))
      {
      fprintf(stderr, "sndfiledecode_reg: malloc failure\n");
      return REJECTED;
      }
   self->sf_info.format = 0;
   if (!(self->sndfile = sf_open(xlplayer->pathname, SFM_READ, &(self->sf_info))))
      {
      free(self);
      return REJECTED;
      }
   xlplayer->dec_init = sndfiledecode_init;
   xlplayer->dec_play = sndfiledecode_play;
   xlplayer->dec_eject = sndfiledecode_eject;
   return ACCEPTED;
   }
