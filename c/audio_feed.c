/*
#   audiofeed.c: jack connectivity for the streaming module of idjc
#   Copyright (C) 2007-2012 Stephen Fairchild (s-fairchild@users.sourceforge.net)
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
#include <jack/jack.h>
#include <jack/ringbuffer.h>
#include "sourceclient.h"
#include "main.h"

typedef jack_default_audio_sample_t sample_t;

static struct audio_feed *audio_feed;

int audio_feed_process_audio(jack_nframes_t n_frames, void *arg)
    {
    struct audio_feed *self = audio_feed;
    struct threads_info *ti = self->threads_info;
    struct encoder *e;
    struct recorder *r;
    sample_t *input_port_buffer[2];
    int i;
    
    input_port_buffer[0] = jack_port_get_buffer(g.port.output_in_l, n_frames);
    input_port_buffer[1] = jack_port_get_buffer(g.port.output_in_r, n_frames);
    
    /* feed pcm audio data to all encoders that request it */
    for (i = 0; i < ti->n_encoders; i++)
        {
        e = ti->encoder[i];
        switch (e->jack_dataflow_control)
            {
            case JD_OFF:
                break;
            case JD_ON:
                while (jack_ringbuffer_write_space(e->input_rb[1]) < n_frames * sizeof (sample_t))
                    nanosleep(&(struct timespec){0, 10000000}, NULL);
                    
                jack_ringbuffer_write(e->input_rb[0], (char *)input_port_buffer[0], n_frames * sizeof (sample_t));
                jack_ringbuffer_write(e->input_rb[1], (char *)input_port_buffer[1], n_frames * sizeof (sample_t));
                break;
            case JD_FLUSH:
                jack_ringbuffer_reset(e->input_rb[0]);
                jack_ringbuffer_reset(e->input_rb[1]);
                e->jack_dataflow_control = JD_OFF;
                break;
            default:
                fprintf(stderr, "jack_process_callback: unhandled jack_dataflow_control parameter\n");
            }
        }
        
    for (i = 0; i < ti->n_recorders; i++)
        {
        r = ti->recorder[i];
        switch (r->jack_dataflow_control)
            {
            case JD_OFF:
                break;
            case JD_ON:
                while (jack_ringbuffer_write_space(r->input_rb[1]) < n_frames * sizeof (sample_t))
                    nanosleep(&(struct timespec){0, 10000000}, NULL);                

                jack_ringbuffer_write(r->input_rb[0], (char *)input_port_buffer[0], n_frames * sizeof (sample_t));
                jack_ringbuffer_write(r->input_rb[1], (char *)input_port_buffer[1], n_frames * sizeof (sample_t));
                break;
            case JD_FLUSH:
                jack_ringbuffer_reset(r->input_rb[0]);
                jack_ringbuffer_reset(r->input_rb[1]);
                r->jack_dataflow_control = JD_OFF;
                break;
            default:
                fprintf(stderr, "jack_process_callback: unhandled jack_dataflow_control parameter\n");
            }   
        }
      
    return 0;
    }

int audio_feed_jack_samplerate_request(struct threads_info *ti, struct universal_vars *uv, void *param)
    {
    fprintf(g.out, "idjcsc: sample_rate=%ld\n", (long)ti->audio_feed->sample_rate);
    fflush(g.out);
    if (ferror(g.out))
        return FAILED;
    return SUCCEEDED;
    }

struct audio_feed *audio_feed_init(struct threads_info *ti)
    {
    struct audio_feed *self;

    if (!(self = audio_feed = calloc(1, sizeof (struct audio_feed))))
        {
        fprintf(stderr, "audio_feed_init: malloc failure\n");
        return NULL;
        }

    self->threads_info = ti;      
    self->sample_rate = jack_get_sample_rate(g.client);
    return self;
    }


void audio_feed_destroy(struct audio_feed *self)
    {
    self->threads_info->audio_feed = NULL;
    free(self);
    }
