/*
#   encoder.h: the encoder for the streaming module of idjc
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

#ifndef ENCODER_H
#define ENCODER_H

#include <stdint.h>
#include <stdlib.h>
#include <samplerate.h>
#include <jack/ringbuffer.h>
#include <pthread.h>
#include "sourceclient.h"

enum jack_dataflow { JD_OFF, JD_ON, JD_FLUSH };
enum performance_warning { PW_OK, PW_AUDIO_DATA_DROPPED };
enum data_format { DF_UNHANDLED, DF_JACK_MP3, DF_JACK_OGG, DF_FILE_MP3, DF_FILE_OGG };
enum encoder_state { ES_STOPPED, ES_STARTING, ES_RUNNING, ES_STOPPING, ES_PAUSED };
enum packet_flags {     PF_UNSET    = 0x00,
                        PF_INITIAL  = 0x01, 
                        PF_FINAL    = 0x02,
                        PF_OGG      = 0x04,
                        PF_MP3      = 0x08,
                        PF_METADATA = 0x10,
                        PF_HEADER   = 0x20 };

struct encoder_vars
   {
   char *encode_source;
   char *sample_rate;
   char *resample_quality;
   char *format;
   char *subformat;
   char *bit_rate;
   char *bit_rate_min;
   char *bit_rate_max;
   char *bit_width;
   char *speex_mode;
   char *speex_quality;
   char *speex_complexity;
   char *stereo;
   char *encode_quality;
   char *use_metadata;
   char *filename;              /* for streaming a pre-recorded file */
   char *offset;
   char *metaformat;            /* extra/replacement information to use for metadata */
   char *metaformat_mp3;        /* as above but could be latin1 encoded */
   char *artist;                /* used for ogg metadata - always utf-8 */
   char *title;
   char *album;
   char *artist_title;
   char *artist_title_mp3;
   char *freeformat_mp3;
   };

struct encoder_ip_data
   {
   int caller_supplied_buffer;   /* indicator of self ownership of buffers */
   int channels;
   size_t qty_samples;
   float *buffer[2];
   };

struct encoder_op_packet_header
   {
   uint32_t magic;                      /* the magic number to check packet sync with */
   enum data_format encoding_data_format;/* the audio compression format in use */
   uint16_t bit_rate;                   /* bit rate in kb/s */
   uint32_t sample_rate;                /* sample rate - typically 44100 or 48000 */
   uint16_t n_channels;                 /* number of audio channels 1 or 2 for mono/stereo */
   enum packet_flags flags;             /* first, last, metadata, mp3, ogg, etc */
   int serial;                          /* the ogg serial number */
   double timestamp;                    /* time in seconds for this serial */
   size_t data_size;                    /* how much data follows in bytes */
   };

struct encoder_op_packet
   {
   struct encoder_op_packet_header header;
   void *data;
   };

struct encoder_op                       /* encoder output object */
   {
   struct encoder *encoder;             /* parent encoder */
   struct encoder_op *next;             /* the next encoder output object */
   jack_ringbuffer_t *packet_rb;        /* ringbuffer containing ogg or mp3 packets */
   enum performance_warning performance_warning_indicator; /* indicates ringbuffer overflow condition */
   pthread_mutex_t mutex;               /* this enables the encoder to expire old output packets safely */
   };

struct encoder_header_buffer
   {
   char *data;
   size_t size;
   pthread_mutex_t mutex;
   };

struct encoder
   {
   struct watchdog_info watchdog_info;  /* used by the watchdog */
   struct threads_info *threads_info;   /* link to the global data structure */
   int numeric_id;                      /* identitity of this encoder from 0 */
   pthread_t thread_h;                  /* this encoder's pthread handle */
   int thread_terminate_f;              /* signal the encoder thread to exit */
   int run_request_f;                   /* to run or not to run... */
   enum encoder_state encoder_state;    /* indicate what the encoder should be doing */
   enum jack_dataflow jack_dataflow_control;    /* tells the jack callback routine what we want it to do */
   jack_ringbuffer_t *input_rb[2];      /* circular buffer containing pcm audio data */
   enum data_format data_format;
   int n_channels;              /* stream parameters information... */
   int bitrate;
   long samplerate;
   long target_samplerate;
   double sr_conv_ratio;
   SRC_STATE *src_state[2];     /* resampler variables */
   float *rs_input[2];          /* buffer used by resampler input callback */
   int rs_channel;              /* resampler callback channel control */
   int resample_f;              /* true or false to resampling required */
   int client_count;            /* number of streamers/recorders connected */
   pthread_mutex_t flush_mutex; /* to block encoder so it's in a known state before flush */
   pthread_mutex_t mutex;/* for blocking encoder_unregister_client while the encoder is writing out data */
   pthread_mutex_t metadata_mutex;      /* used when metadata is read or written */
   struct encoder_op *output_chain;     /* one output buffer per client connection */
   struct encoder_header_buffer *header_buffer; /* point to needed headers or NULL */
   enum performance_warning performance_warning_indicator; /* indicates ringbuffer overflow condition */
   char *metaformat;            /* extra/replacement information to use for metadata */
   char *metaformat_mp3;        /* as above but could be latin1 encoded */
   char *artist;                /* used for ogg metadata - always utf-8 */
   char *title;
   char *album;
   char *artist_title;
   char *artist_title_mp3;      /* used for mp3 metadata */
   int new_metadata;
   int flush;
   int oggserial;               /* n.b. not restricted to ogg useage */
   double timestamp;            /* running counter in seconds for current serial */
   void (*run_encoder)(struct encoder *);       /* pointer to the encoder in use */
   void *encoder_private;               /* used by the specific encoder */
   };

struct encoder *encoder_init(struct threads_info *ti, int numeric_id);
int encoder_init_lame(struct threads_info *ti, struct universal_vars *uv, void *param);
void encoder_destroy(struct encoder *self);
struct encoder_op_packet *encoder_client_get_packet(struct encoder_op *op);
void encoder_client_free_packet(struct encoder_op_packet *packet);
int encoder_client_set_flush(struct encoder_op *op);
size_t encoder_write_packet(struct encoder_op *op, struct encoder_op_packet *packet);
void encoder_write_packet_all(struct encoder *enc, struct encoder_op_packet *packet);
struct encoder_op *encoder_register_client(struct threads_info *ti, int numeric_id);
void encoder_unregister_client(struct encoder_op *op);
int encoder_start(struct threads_info *ti, struct universal_vars *uv, void *other);
int encoder_stop(struct threads_info *ti, struct universal_vars *uv, void *other);
int encoder_update(struct threads_info *ti, struct universal_vars *uv, void *other);
int encoder_new_metadata(struct threads_info *ti, struct universal_vars *uv, void *other);
int encoder_new_metaformat(struct threads_info *ti, struct universal_vars *uv, void *other);
void encoder_src_data_cleanup(struct encoder *self);
struct encoder_ip_data *encoder_get_input_data(struct encoder *encoder, int min_samples_needed, int max_samples, float **caller_supplied_buffer);
void encoder_ip_data_free(struct encoder_ip_data *id);
#endif
