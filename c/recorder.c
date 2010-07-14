/*
#   recorder.c: the recording part of the streaming module of idjc
#   Copyright (C) 2007-2009 Stephen Fairchild (s-fairchild@users.sourceforge.net)
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
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include "live_ogg_encoder.h"
#include "sourceclient.h"
#include "id3.h"

#define TIMESTAMP_SIZ 23

#if 0
static void recorder_write_ogg_metaheader(struct recorder *self)
   {
   struct encoder *encoder = self->encoder_op->encoder;
   struct loe_data *s = encoder->encoder_private;
   vorbis_info vi;
   vorbis_dsp_state vd;
   vorbis_block vb;
   vorbis_comment vc;
   ogg_stream_state os;
   ogg_page og;
   ogg_packet op;
   ogg_packet header_main;
   ogg_packet header_comments;
   ogg_packet header_codebooks;

   void write_out(ogg_page *ogp)    /* output the ogg page */
      {
      fwrite(ogp->header, ogp->header_len, 1, self->fp);
      fwrite(ogp->body, ogp->body_len, 1, self->fp);
      if (ferror(self->fp))
         {
         fprintf(stderr, "recorder_write_ogg_metaheader: error writing the header\n");
         }
      }

   void encode_silent_samples(int n_samples)
      {
      float **buffer;
      int i;

      /* generate a silent buffer */
      buffer = vorbis_analysis_buffer(&vd, n_samples);
      for (i = 0; i < vi.channels; i++)
         memset(buffer[i], 0, n_samples * sizeof (float));
      vorbis_analysis_wrote(&vd, n_samples);

      /* encode it */
      while (vorbis_analysis_blockout(&vd, &vb) == 1)
         {
         vorbis_analysis(&vb, NULL);
         vorbis_bitrate_addblock(&vb);
         while (vorbis_bitrate_flushpacket(&vd, &op))
            {
            ogg_stream_packetin(&os, &op);
            while (ogg_stream_pageout(&os, &og))
               {
               write_out(&og);
               if (ogg_page_eos(&og))
                  break;
               }
            }
         }
      }

   vorbis_info_init(&vi);
   if (vorbis_encode_setup_managed(&vi, encoder->n_channels, encoder->target_samplerate, s->max_bitrate * 1000, encoder->bitrate * 1000, s->min_bitrate * 1000))
      {
      fprintf(stderr, "recorder_write_ogg_metaheader: mode initialisation failed\n");
      vorbis_info_clear(&vi);
      return;
      }
   vorbis_encode_setup_init(&vi);
   vorbis_analysis_init(&vd, &vi);
   vorbis_block_init(&vd, &vb);
   ogg_stream_init(&os, self->initial_serial - 1);
   vorbis_comment_init(&vc);

                                    /* write vorbis header */
   vorbis_analysis_headerout(&vd, &vc, &header_main, &header_comments, &header_codebooks);
   ogg_stream_packetin(&os, &header_main);
   ogg_stream_packetin(&os, &header_comments);
   ogg_stream_packetin(&os, &header_codebooks);
   while (ogg_stream_flush(&os, &og))
      write_out(&og);

   encode_silent_samples(1);        /* one sample is all we need */
   encode_silent_samples(0);

   ogg_stream_clear(&os);           /* cleanup */
   vorbis_block_clear(&vb);
   vorbis_dsp_clear(&vd);
   vorbis_comment_clear(&vc);
   vorbis_info_clear(&vi);
   }
#endif /* recorder_write_ogg_metaheader */

static int recorder_write_id3_tag(struct recorder *self, FILE *fp)
   {
   struct metadata_item *mi;
   struct id3_tag *tag;
   struct id3_frame *chap;
   struct id3_frame *tit2;
   struct id3_frame *tlen;

   tag = id3_tag_new(0, 512);
   tlen = id3_numeric_string_frame_new("TLEN", self->recording_length_ms);
   id3_add_frame(tag, tlen);
   for (mi = self->mi_first; mi; mi = mi->next)
      {
      chap = id3_chap_frame_new("", mi->time_offset, mi->time_offset_end, mi->byte_offset, mi->byte_offset_end);
      tit2 = id3_text_frame_new("TIT2", mi->artist_title, 3, 1);
      id3_embed_frame(chap, tit2);
      id3_add_frame(tag, chap);
      }
   id3_compile(tag);
   if (fwrite(tag->tag_data, 1, tag->tag_data_size, fp) != tag->tag_data_size)
      {
      fprintf(stderr, "recorder_write_id3_tag: error writing to file\n");
      id3_tag_destroy(tag);
      return FAILED;
      }
   id3_tag_destroy(tag);
   return SUCCEEDED;
   }
   
static int recorder_create_mp3_cuesheet(struct recorder *self)
   {
   struct metadata_item *mi;
   char *cuepathname, *bp;
   FILE *fp;
   int i;
   
   i = strrchr(self->pathname, '.') - self->pathname + 1;
   if (!(cuepathname = malloc(i + 4)))
      {
      fprintf(stderr, "recorder_write_mp3_cue_sheet: malloc failure\n");
      return FAILED;
      }
   else
      strcpy(strncpy(cuepathname, self->pathname, i) + i, "cue");
   
   if (!(fp = fopen(cuepathname, "wb")))
      {
      fprintf(stderr, "recorder_write_mp3_cue_sheet: failed to open cue sheet file for writing\n");
      free(cuepathname);
      return FAILED;
      }

   fprintf(fp, "TITLE \"%s\"\r\n", self->title);
   fprintf(fp, "PERFORMER \"Recorded with IDJC\"\r\n");
   fprintf(fp, "FILE \"%s\" MP3\r\n", strrchr(self->pathname, '/') + 1);
   
   for (i = 1, mi = self->mi_first; mi; i++, mi = mi->next)
      {
      fprintf(fp, "  TRACK %02d AUDIO\r\n", i);
      if ((bp = strstr(mi->artist_title, " - ")))
         {
         fprintf(fp, "    TITLE \"%s\"\r\n", bp + 3);
         fprintf(fp, "    PERFORMER \"");
         if (!(fwrite(mi->artist_title, bp - mi->artist_title, 1, fp)))
            fprintf(stderr, "error writing cuesheet\n");
         fputc('"', fp);
         fputc('\r', fp);
         fputc('\n', fp);
         }
      else
         fprintf(fp, "    TITLE \"%s\"\r\n", mi->artist_title);
      fprintf(fp, "    INDEX 01 %02d:%02d:00\r\n", mi->time_offset / 60000, mi->time_offset / 1000 % 60);
      }
   
   fclose(fp);
   free(cuepathname);
   return SUCCEEDED;
   }
      
static int recorder_write_vbr_tag(struct recorder *self, FILE *fp)
   {
   int mpeg1_f, mono_f;
   int xing_offset, initial_offset;
   int side_info_table[2][2] = { { 17, 9 } , { 32, 17 } };
   int i, total_frames, samples_per_frame, framelength, padding, frame_fill;
   double seek, look_ms, seg_prop;
   unsigned char seek_table[100], *ptr;
   struct metadata_item2 *mi2;
   
   if (self->mi2_first == NULL)
      {
      fprintf(stderr, "recorder_write_vbr_tag: no metadata collected, skipping vbr tag\n");
      return SUCCEEDED;
      }
   fprintf(stderr, "recorder_write_vbr_tag: commencing\n");
   initial_offset = ftell(fp);
   padding = (self->first_mp3_header[2] & 0x2) ? 1 : 0;
   mpeg1_f = ((self->first_mp3_header[1] & 0x18) == 0x18) ? 1 : 0;
   mono_f = ((self->first_mp3_header[3] & 0xC0) == 0xC0) ? 1 : 0;
   samples_per_frame = mpeg1_f ? 1152 : 576;
   framelength = samples_per_frame / 8 * self->mi2_first->bit_rate * 1000 / self->mi2_first->sample_rate + padding;
   xing_offset = side_info_table[mpeg1_f][mono_f];
   if (!fwrite(self->first_mp3_header, 4, 1, fp))
      return FAILED;

   for (i = 0; i < xing_offset; i++)
      {
      fputc(0x00, fp);
      if (ferror(fp))
         return FAILED;
      }
   if (self->is_vbr)
      {
      if (!(fwrite("Xing\x00\x00\x00\x07", 8, 1, fp)))
         return FAILED;
      }
   else
      if (!(fwrite("Info\x00\x00\x00\x03", 8, 1, fp)))
         return FAILED;
   /* the following calculation is fake for files with varying sample rates
    * however the players which use this value will probably only use it 
    * for calclulating the play duration which will yield the intended result */
   total_frames = (int)(self->mi2_first->sample_rate * (double)self->recording_length_ms / (samples_per_frame * 1000.0) + 0.5);
   fputc((total_frames >> 24) & 0xFF, fp);
   fputc((total_frames >> 16) & 0xFF, fp);
   fputc((total_frames >> 8 ) & 0xFF, fp);
   fputc( total_frames        & 0xFF, fp);
   fputc((self->bytes_written >> 24) & 0xFF, fp);
   fputc((self->bytes_written >> 16) & 0xFF, fp);
   fputc((self->bytes_written >> 8 ) & 0xFF, fp);
   fputc( self->bytes_written        & 0xFF, fp);
   if (self->is_vbr)
      {
      fprintf(stderr, "recorder_write_vbr_tag: creating a seek table\n");
      /* generate a vbr seek table with 100 entries in it */
      for (seek = 0.0, ptr = seek_table, mi2 = self->mi2_first; seek < 1.0; seek += 0.01, ptr++)
         {
         look_ms = seek * self->recording_length_ms;
         while (look_ms > mi2->finish_offset_ms)
            {
            mi2 = mi2->next;
            if (mi2 == NULL)    /* this should never ever happen */
               {
               fprintf(stderr, "recorder_write_vbr_tag: WARNING: bad metadata, failed creation of seek table\n");
               return FAILED;
               }
            }
         seg_prop = (look_ms - mi2->start_offset_ms) / (double)(mi2->finish_offset_ms - mi2->start_offset_ms);
         *ptr = (((seg_prop * mi2->size_bytes) + mi2->byte_offset) / self->bytes_written * 255);
         }
      if (!(fwrite(seek_table, 100, 1, fp)))
         return FAILED;
      if (seek_table[99] == 0xFF)
         fputc('\0', fp);
      }
   frame_fill = framelength - ftell(fp) + initial_offset;
   while (frame_fill-- > 0)     /* this frame is allowed to overrun its bounds */
      fputc('\0', fp);          /* and can do so with very low bitrate, high sample rate */
   if (ferror(fp))
      return FAILED;
   return SUCCEEDED;
   }

static void recorder_apply_mp3_tags(struct recorder *self)
   {
   char *tmpname;
   FILE *fpr, *fpw;
   char buffer[2048];
   int bytes;
   
   if (!(tmpname = malloc(strlen(self->pathname) + 5)))
      {
      fprintf(stderr, "recorder_apply_mp3_tags: malloc failure\n");
      return;
      }
   strcpy(tmpname, self->pathname);
   strcat(tmpname, ".tmp");
   if (!(fpw = fopen(tmpname, "w+")))
      {
      fprintf(stderr, "recorder_apply_mp3_tags: failed to open temporary file\n");
      free(tmpname);
      return;
      }
   if (!(fpr = fopen(self->pathname, "r")))
      {
      fprintf(stderr, "recorder_apply_mp3_tags: failed to open the mp3 file\n");
      fclose(fpw);
      unlink(tmpname);
      free(tmpname);
      return;
      }
      
   if (!fread(self->first_mp3_header, 4, 1, fpr))
      {
      fprintf(stderr, "failed to obtain the first four bytes of the recording\n");
      fclose(fpr);
      fclose(fpw);
      unlink(tmpname);
      free(tmpname);
      return;
      } 
   rewind(fpr);
      
   if (!(recorder_write_id3_tag(self, fpw) && recorder_write_vbr_tag(self, fpw)))
      {
      fprintf(stderr, "recorder_apply_mp3_tags: failed to tag the mp3 file\n");
      fclose(fpr);
      fclose(fpw);
      unlink(tmpname);
      free(tmpname);
      return;
      }
   for (;;)             /* copy the mp3 file's data onto the end of the tagged file */
      {
      bytes = fread(buffer, 1, 2048, fpr);
      if (bytes == 0)
         break;
      if (!(fwrite(buffer, bytes, 1, fpw)))
         {
         fprintf(stderr, "recorder_apply_mp3_tags: error copying the mp3 file\n");
         fclose(fpr);
         fclose(fpw);
         unlink(tmpname);
         free(tmpname);
         return;
         }
      }
   fclose(fpr);
   fclose(fpw);
   if (rename(tmpname, self->pathname))
      {
      fprintf(stderr, "recorder_apply_mp3_tags: failed to rename the temporary file\n");
      free(tmpname);
      return;
      }
   free(tmpname);
   fprintf(stderr, "recorder_apply_mp3_tags: successfully tagged the mp3 file\n");
   }

static void recorder_append_metadata2(struct recorder *self, struct encoder_op_packet *packet)
   {
   struct metadata_item2 *mi2;
   
   if (!(mi2 = calloc(1, sizeof (struct metadata_item2))))
      {
      fprintf(stderr, "recorder_append_metadata2: malloc failure\n");
      return;
      }
   if (!(self->mi2_first))
      {
      mi2->start_offset_ms = 0;
      mi2->byte_offset = 0;
      if (packet)
         {
         mi2->bit_rate = packet->header.bit_rate;
         mi2->sample_rate = packet->header.sample_rate;
         }
      self->mi2_first = mi2;
      self->mi2_last = mi2;
      }
   else
      {
      mi2->start_offset_ms = self->recording_length_ms;
      mi2->byte_offset = self->bytes_written;
      if (packet)
         {
         mi2->bit_rate = packet->header.bit_rate;
         mi2->sample_rate = packet->header.sample_rate;
         }
      self->mi2_last->finish_offset_ms = mi2->start_offset_ms;
      self->mi2_last->size_bytes = mi2->byte_offset - self->mi2_last->byte_offset;
      if (packet)
         {
         self->mi2_last->next = mi2;
         self->mi2_last = mi2;
         }
      else
         free(mi2);
      }
   if (packet && (packet->header.bit_rate != self->oldbitrate || packet->header.sample_rate != self->oldsamplerate) && (packet->header.flags & PF_MP3))
      {
      if (self->oldbitrate && self->oldsamplerate)
         {
         self->is_vbr = TRUE;
         fprintf(stderr, "recorder_append_metadata2: the mp3 frame length altered\n");
         }
      self->oldbitrate = packet->header.bit_rate;
      self->oldsamplerate = packet->header.sample_rate;
      }
   }

static void recorder_free_metadata2(struct recorder *self)
   {
   struct metadata_item2 *mi2, *oldmi2;
   
   for (mi2 = self->mi2_first; mi2;)
      {
      oldmi2 = mi2;
      mi2 = mi2->next;
      free(oldmi2);
      }
   self->mi2_first = NULL;
   self->mi2_last = NULL;
   }

static void recorder_display_logged_metadata2(struct metadata_item2 *mi2)
   {
   if (mi2)
      {
      fprintf(stderr, "The following metadata was also logged.\n");
      do {
         fprintf(stderr, "Start(ms): %06d  Finish(ms): %06d  Byte offset: %06d  Size(bytes): %06d\n", mi2->start_offset_ms, mi2->finish_offset_ms, mi2->byte_offset, mi2->size_bytes);
         } while ((mi2 = mi2->next));
      }
   else
      fprintf(stderr, "No start position for the stream was logged!\n");
   }

static void recorder_append_metadata(struct recorder *self, struct encoder_op_packet *packet)
   {
   struct metadata_item *mi;

   if (packet && self->mi_last && !strcmp(self->mi_last->artist_title, packet->data))
      {
      fprintf(stderr, "recorder_append_metadata: duplicate artist-title, skipping\n");
      return;
      }
   if (!(mi = calloc(1, sizeof (struct metadata_item))))
      {
      fprintf(stderr, "recoder_append_metadata: malloc failure\n");
      return;
      }
   if (packet)
      {
      if (!(mi->artist_title = malloc(packet->header.data_size)))
         {
         fprintf(stderr, "recorder_append_metadata: malloc failure\n");
         free(mi);
         return;
         }
      strcpy(mi->artist_title, packet->data);
      }
   else
      mi->artist_title = strdup("");
   mi->time_offset = self->recording_length_ms;
   mi->byte_offset = self->bytes_written;
   if (!(self->mi_first))
      {
      self->mi_first = mi;
      self->mi_last = mi;
      }
   else
      {
      self->mi_last->time_offset_end = mi->time_offset;
      self->mi_last->byte_offset_end = mi->byte_offset;
      if (packet)
         {
         self->mi_last->next = mi;
         self->mi_last = mi;
         }
      else
         free(mi);
      }
   }

static void recorder_free_metadata(struct recorder *self)
   {
   struct metadata_item *mi, *oldmi;
   
   for (mi = self->mi_first; mi;)
      {
      oldmi = mi;
      mi = mi->next;
      free(oldmi->artist_title);
      free(oldmi);
      }
   self->mi_first = NULL;
   self->mi_last = NULL;
   }

static void recorder_display_logged_metadata(struct metadata_item *mi)
   {
   if (mi)
      {
      fprintf(stderr, "The following metadata was logged.\n");
      do {
         fprintf(stderr, "Start(ms): %06d Byte: %08d Text: %s\nFinish(ms): %06d Finish byte %08d\n", mi->time_offset, mi->byte_offset, mi->artist_title, mi->time_offset_end, mi->byte_offset_end);
         } while ((mi = mi->next));
      }
   else
      fprintf(stderr, "No metadata was logged for the recording.\n");
   }

static void *recorder_main(void *args)
   {
   struct recorder *self = args;
   struct timespec ms10 = { 0, 10000000 };
   struct encoder_op_packet *packet;
      
   while (!self->thread_terminate_f)
      {
      nanosleep(&ms10, NULL);
      self->watchdog_info.tick++;
      switch (self->record_mode)
         {
         case RM_STOPPED:
            continue;
         case RM_RECORDING:
            if (!(self->watchdog_info.tick & 0x3F))
               fprintf(stderr, "recorder_main: recorder %d is recording\n", self->numeric_id);
            if ((packet = encoder_client_get_packet(self->encoder_op)))
               {
               if (packet->header.serial >= self->initial_serial)
                  {
                  if ((packet->header.flags & PF_INITIAL) && self->mp3_mode)
                     recorder_append_metadata2(self, packet);
                  if (packet->header.flags & (PF_OGG | PF_MP3))
                     {
                     if (packet->header.data_size != fwrite(packet->data, 1, packet->header.data_size, self->fp))
                        {
                        fprintf(stderr, "recorder_main: failed writing to file %s\n", self->pathname);
                        self->record_mode = RM_STOPPING;
                        }
                     else
                        {
                        self->recording_length_s = (int)(self->accumulated_time + packet->header.timestamp);
                        self->recording_length_ms = (int)((self->accumulated_time + packet->header.timestamp) * 1000.0);
                        self->bytes_written = ftell(self->fp);
                        }
                     }
                  if (packet->header.flags & PF_FINAL)
                     {
                     self->accumulated_time += packet->header.timestamp;
                     if (self->pause_pending && packet->header.serial >= self->final_serial)
                        {
                        self->record_mode = RM_PAUSED;
                        self->pause_pending = FALSE;
                        fprintf(stderr, "recorder_main: entering pause mode\n");
                        }
                     }
                  }
               if (packet->header.flags & PF_METADATA)
                  recorder_append_metadata(self, packet);
               encoder_client_free_packet(packet);
               }
            if (self->stop_request)
               {
               self->stop_pending = TRUE;
               self->pause_request = TRUE;
               self->stop_request = FALSE;
               }
            if (self->pause_request)
               {
               self->pause_pending = TRUE;
               self->final_serial = encoder_client_set_flush(self->encoder_op);
               self->pause_request = FALSE;
               }
            break;
         case RM_PAUSED:
            if (self->stop_request || self->stop_pending)
               self->record_mode = RM_STOPPING;
            else
               if (self->unpause_request)
                  {
                  self->initial_serial = encoder_client_set_flush(self->encoder_op) + 1;
                  self->record_mode = RM_RECORDING;
                  self->unpause_request = FALSE;
                  }
            break;
         case RM_STOPPING:
            fclose(self->fp);
            if (self->mp3_mode)
               {
               recorder_append_metadata(self, NULL);
               recorder_append_metadata2(self, NULL);
               recorder_display_logged_metadata(self->mi_first);
               recorder_display_logged_metadata2(self->mi2_first);
               recorder_apply_mp3_tags(self);
               recorder_create_mp3_cuesheet(self);
               recorder_free_metadata(self);
               recorder_free_metadata2(self);
               }
            free(self->pathname);
            free(self->title);
            encoder_unregister_client(self->encoder_op);
            memset(self->first_mp3_header, 0x00, 4);
            self->oldbitrate = 0;
            self->oldsamplerate = 0;
            self->mp3_mode = FALSE;
            self->is_vbr = FALSE;
            self->recording_length_s = 0;
            self->recording_length_ms = 0;
            self->accumulated_time = 0.0;
            self->bytes_written = 0;
            self->fp = NULL;
            self->pathname = NULL;
            self->encoder_op = NULL;
            self->stop_request = FALSE;
            self->stop_pending = FALSE;
            self->pause_request = FALSE;
            self->pause_pending = FALSE;
            self->record_mode = RM_STOPPED;
            break;
         default:
            fprintf(stderr, "recorder_main: unhandled record mode\n");
         }
      }
   return NULL;
   }

int recorder_make_report(struct recorder *self)
   {
   fprintf(stdout, "idjcsc: recorder%dreport=%d:%d\n", self->numeric_id, self->record_mode, self->recording_length_s);
   fflush(stdout);
   return SUCCEEDED;
   }

int recorder_start(struct threads_info *ti, struct universal_vars *uv, void *other)
   {
   struct recorder_vars *rv = other;
   struct recorder *self = ti->recorder[uv->tab];
   time_t t;
   struct tm *tm;
   char *file_extension;
   size_t pathname_size;
   char timestamp[TIMESTAMP_SIZ];

   if (!strcmp(rv->record_source, "-1"))
      {
      file_extension = ".flac";
      self->encoder_op = NULL;
      }
   else
      {      
      if (!(self->encoder_op = encoder_register_client(ti, atoi(rv->record_source))))
         {
         fprintf(stderr, "recorder_start: failed to register with encoder\n");
         return FAILED;
         }
      if (!self->encoder_op->encoder->run_request_f)
         {
         fprintf(stderr, "recorder_start: encoder is not running\n");
         encoder_unregister_client(self->encoder_op);
         return FAILED;
         }
      switch (self->encoder_op->encoder->data_format)
         {
         case DF_JACK_MP3:
         case DF_FILE_MP3:
            self->mp3_mode = TRUE;
            file_extension = ".mp3";
            break;
         case DF_JACK_OGG:
         case DF_FILE_OGG:
            file_extension = ".oga";
            break;
         default:
            fprintf(stderr, "recorder_start: data_format is not set to a handled value\n");
            encoder_unregister_client(self->encoder_op);
            return FAILED;
         }
      }

   if (!(self->pathname = malloc(pathname_size = strlen(rv->record_folder) + strlen(file_extension) + TIMESTAMP_SIZ + 10)))
      {
      fprintf(stderr, "recorder_start: malloc failure\n");
      if (self->encoder_op)
         encoder_unregister_client(self->encoder_op);
      return FAILED;
      }
   /* generate a timestamp filename */
   t = time(NULL);
   tm = localtime(&t);
   strftime(timestamp, TIMESTAMP_SIZ, "[%Y-%m-%d][%H:%M:%S]", tm);
   self->title = strdup(timestamp);
   snprintf(self->pathname, pathname_size, "%s/idjc.%s.%02d%s", rv->record_folder, timestamp, uv->tab+1, file_extension);
   if (!(self->fp = fopen(self->pathname, "w")))
      {
      fprintf(stderr, "recorder_start: failed to open file %s\nuser should check file permissions on the particular directory\n", rv->record_folder);
      free(self->pathname);
      free(self->title);
      if (self->encoder_op)
         encoder_unregister_client(self->encoder_op);
      return FAILED;
      }
   if (self->encoder_op)
      {
      self->initial_serial = encoder_client_set_flush(self->encoder_op) + 1;
      fprintf(stderr, "recorder_start: awaiting serial %d to commence\n", self->initial_serial);
      }
   else
      {
      /* no encoder implies we are encoding in this module */
      self->sfinfo.samplerate = ti->audio_feed->sample_rate;
      self->sfinfo.channels = 2;
      self->sfinfo.format = SF_FORMAT_FLAC | SF_FORMAT_PCM_24;
      if (!(self->sf = sf_open_fd(fileno(self->fp), SFM_WRITE, &self->sfinfo, 0)))
         {
         free(self->pathname);
         free(self->title);
         fclose(self->fp);
         fprintf(stderr, "recorder_start: unable to initialise FLAC encoder\n");
         return FAILED;
         }
      self->initial_serial = -1;
      fprintf(stderr, "recorder_start: in FLAC mode\n");
      }
   //if (file_extension == ".oga")
   //   recorder_write_ogg_metaheader(self);
   if (self->pause_request == TRUE)
      self->record_mode = RM_PAUSED;
   else 
      self->record_mode = RM_RECORDING;
   fprintf(stderr, "recorder_start called\n");
   return SUCCEEDED;
   }
   
int recorder_stop(struct threads_info *ti, struct universal_vars *uv, void *other)
   {
   struct recorder *self = ti->recorder[uv->tab];
   struct timespec ms10 = { 0, 10000000 };

   if (self->record_mode == RM_STOPPED)
      {
      fprintf(stderr, "recorder_stop: recorder is already stopped\n");
      return FAILED;
      }
   self->stop_request = TRUE;
   while (self->record_mode != RM_STOPPED)
      nanosleep(&ms10, NULL);
   fprintf(stderr, "recorder_stop called\n");
   return SUCCEEDED;
   }
   
int recorder_pause(struct threads_info *ti, struct universal_vars *uv, void *other)
   {
   struct recorder *self = ti->recorder[uv->tab];
   struct timespec ms10 = { 0, 10000000 };

   self->unpause_request = FALSE;
   self->pause_request = TRUE;
   if (self->record_mode == RM_RECORDING)
      {
      fprintf(stderr, "recorder_pause: waiting for pause mode to be entered\n");
      while (self->record_mode != RM_PAUSED)
         nanosleep(&ms10, NULL);
      fprintf(stderr, "recorder_pause: in pause mode\n");
      }
   else
      {
      if (self->record_mode == RM_PAUSED)
         {
         fprintf(stderr, "recorder_pause: recorder is already paused\n");
         return FAILED;
         }
      else
         fprintf(stderr, "recorder_pause: not currenly recording\n");
      }
   return SUCCEEDED;
   }
   
int recorder_unpause(struct threads_info *ti, struct universal_vars *uv, void *other)
   {
   struct recorder *self = ti->recorder[uv->tab];
   struct timespec ms10 = { 0, 10000000 };
   
   self->pause_request = FALSE;
   self->unpause_request = TRUE;
   if (self->record_mode == RM_PAUSED)
      {
      fprintf(stderr, "recorder_unpause: waiting for pause mode to finish\n");
      while (self->record_mode == RM_PAUSED)
         nanosleep(&ms10, NULL);
      fprintf(stderr, "recorder_unpause: left pause mode\n");
      }
   else
      {
      fprintf(stderr, "recorder_unpause: wasn't paused in the first place\n");
      return FAILED;
      }
   return SUCCEEDED;
   }

struct recorder *recorder_init(struct threads_info *ti, int numeric_id)
   {
   struct recorder *self;
   
   if (!(self = calloc(1, sizeof (struct recorder))))
      {
      fprintf(stderr, "recorder_init: malloc failure\n");
      return NULL;
      }
   self->threads_info = ti;
   self->numeric_id = numeric_id;  
   pthread_create(&self->thread_h, NULL, recorder_main, self);
   return self;
   }

void recorder_destroy(struct recorder *self)
   {
   self->thread_terminate_f = TRUE;
   pthread_join(self->thread_h, NULL);
   free(self);
   }
