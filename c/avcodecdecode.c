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
#include "main.h"
#include "xlplayer.h"
#include "avcodecdecode.h"

#define TRUE 1
#define FALSE 0
#define ACCEPTED 1
#define REJECTED 0

extern int dynamic_metadata_form[];

static const struct timespec time_delay = { .tv_nsec = 10 };

static void avcodecdecode_eject(struct xlplayer *xlplayer)
    {
    struct avcodecdecode_vars *self = xlplayer->dec_data;
    
    if (self->resample)
        {
        xlplayer->src_state = src_delete(xlplayer->src_state);
        free(xlplayer->src_data.data_out);
        }
    if (self->floatsamples)
        free(self->floatsamples);
    while (pthread_mutex_trylock(&g.avc_mutex))
        nanosleep(&time_delay, NULL);
    avcodec_close(self->c);
    pthread_mutex_unlock(&g.avc_mutex);
    avformat_close_input(&self->ic);
    if (self->frame)
        av_free(self->frame);
    free(self);
    fprintf(stderr, "finished eject\n");
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
            case CODEC_ID_MUSEPACK8:
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
    int channels = self->c->channels;
    SRC_DATA *src_data = &xlplayer->src_data;
    
    if (xlplayer->write_deferred)
        {
        xlplayer_write_channel_data(xlplayer);
        return;
        }
    
    if (self->size <= 0)
        {
        if (av_read_frame(self->ic, &self->pkt) < 0 || (self->size = self->pkt.size) == 0)
            {
            if (self->pkt.data)
                av_free_packet(&self->pkt);

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
        self->pktcopy = self->pkt;
        }

    if (self->pkt.stream_index != (int)self->stream)
        {
        if (self->pkt.data)
            av_free_packet(&self->pkt);
        self->size = 0;
        return;
        }

    do
        {
        int len, frames, got_frame = 0;
        
        if (!self->frame)
            {
            if (!(self->frame = avcodec_alloc_frame()))
                {
                fprintf(stderr, "avcodecdecode_play: malloc failure\n");
                exit(1);
                }
            else
                avcodec_get_frame_defaults(self->frame);
            }

        while (pthread_mutex_trylock(&g.avc_mutex))
            nanosleep(&time_delay, NULL);
        len = avcodec_decode_audio4(self->c, self->frame, &got_frame, &self->pktcopy);
        pthread_mutex_unlock(&g.avc_mutex);

        if (len < 0)
            {
            fprintf(stderr, "avcodecdecode_play: error during decode\n");
            break;
            }

        self->pktcopy.data += len;
        self->pktcopy.size -= len;
        self->size -= len;

        if (!got_frame)
            {
            continue;
            }

        int buffer_size = av_samples_get_buffer_size(NULL, channels,
                            self->frame->nb_samples, self->c->sample_fmt, 1);

        switch (self->c->sample_fmt) {
            case AV_SAMPLE_FMT_FLT:
                frames = (buffer_size >> 2) / channels;
                memcpy(self->floatsamples, self->frame->data[0], buffer_size);
                break;
            case AV_SAMPLE_FMT_S16:
                frames = (buffer_size >> 1) / channels;
                xlplayer_make_audio_to_float(xlplayer, self->floatsamples,
                                self->frame->data[0], frames, 16, channels);
                break;
            case AV_SAMPLE_FMT_NONE:
            default:
                fprintf(stderr, "avcodecdecode_play: unexpected data format\n");
                xlplayer->playmode = PM_EJECTING;
                return;
            }
        
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
            xlplayer_write_channel_data(xlplayer);
        } while (!xlplayer->write_deferred && self->size > 0);

    if (self->size <= 0)
        {
        if (self->pkt.data)
            av_free_packet(&self->pkt);
        int delay = xlplayer_calc_rbdelay(xlplayer);
        struct chapter *chapter = mp3_tag_chapter_scan(&self->taginfo, xlplayer->play_progress_ms + delay);
        if (chapter && chapter != self->current_chapter)
            {
            self->current_chapter = chapter;
            xlplayer_set_dynamic_metadata(xlplayer, dynamic_metadata_form[chapter->title.encoding], chapter->artist.text, chapter->title.text, chapter->album.text, delay);
            }
        }
    }

int avcodecdecode_reg(struct xlplayer *xlplayer)
    {
    struct avcodecdecode_vars *self;
    FILE *fp;
    struct chapter *chapter;
    
    if (!(xlplayer->dec_data = self = calloc(1, sizeof (struct avcodecdecode_vars))))
        {
        fprintf(stderr, "avcodecdecode_reg: malloc failure\n");
        return REJECTED;
        }
    else
        xlplayer->dec_data = self;
    
    if ((fp = fopen(xlplayer->pathname, "r")))
        {
        mp3_tag_read(&self->taginfo, fp);
        if ((chapter = mp3_tag_chapter_scan(&self->taginfo, xlplayer->play_progress_ms + 70)))
            {
            self->current_chapter = chapter;
            xlplayer_set_dynamic_metadata(xlplayer, dynamic_metadata_form[chapter->title.encoding], chapter->artist.text, chapter->title.text, chapter->album.text, 70);
            }
        fclose(fp);
        }
    
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
        
    self->c->request_sample_fmt = AV_SAMPLE_FMT_FLT;

    if (self->stream == self->ic->nb_streams)
        {
        fprintf(stderr, "avcodecdecode_reg: codec not found 1\n");
        avformat_close_input(&self->ic);
        free(self);
        return REJECTED;
        }

    if (avformat_find_stream_info(self->ic, NULL) < 0)
        {
        fprintf(stderr, "avcodecdecode_reg: call to avformat_find_stream_info failed\n");
        avformat_close_input(&self->ic);
        free(self);
        return REJECTED;
        }

    while (pthread_mutex_trylock(&g.avc_mutex))
        nanosleep(&time_delay, NULL);
    self->codec = avcodec_find_decoder(self->c->codec_id);
    pthread_mutex_unlock(&g.avc_mutex);
    if (!self->codec)
        {
        fprintf(stderr, "avcodecdecode_reg: codec not found 2\n");
        avformat_close_input(&self->ic);
        free(self);
        return REJECTED;
        }
    
    while (pthread_mutex_trylock(&g.avc_mutex))
        nanosleep(&time_delay, NULL);
    if (avcodec_open2(self->c, self->codec, NULL) < 0)
        {
        pthread_mutex_unlock(&g.avc_mutex);
        fprintf(stderr, "avcodecdecode_reg: could not open codec\n");
        avformat_close_input(&self->ic);
        free(self);
        return REJECTED;
        }
    pthread_mutex_unlock(&g.avc_mutex);

    if (!(self->floatsamples = malloc(AVCODEC_MAX_AUDIO_FRAME_SIZE * 2)))
        {
        fprintf(stderr, "avcodecdecode_reg: malloc failure\n");
        avcodecdecode_eject(xlplayer);
        return REJECTED;
        }

    xlplayer->dec_init = avcodecdecode_init;
    xlplayer->dec_play = avcodecdecode_play;
    xlplayer->dec_eject = avcodecdecode_eject;
    
    return ACCEPTED;
    }
    
#endif /* HAVE_AVUTIL */
#endif /* HAVE_AVFORMAT */
#endif /* HAVE_AVCODEC */
