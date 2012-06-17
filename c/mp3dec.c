/*
#   mp3dec.c: decodes mp3 file format for xlplayer
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

#include "gnusource.h"
#include <stdio.h>
#include <string.h>
#include <math.h>
#include <jack/jack.h>
#include <mad.h>
#include "xlplayer.h"
#include "mp3dec.h"
#include "bsdcompat.h"

#define TRUE 1
#define FALSE 0
#define ACCEPTED 1
#define REJECTED 0

#define BSIZ 16384
#define MAD_SCALE ((float)(1L << (MAD_F_SCALEBITS - 18)))

int dynamic_metadata_form[4] = { DM_SPLIT_L1, DM_NOTAG, DM_NOTAG, DM_SPLIT_U8 };

static inline float scale(struct xlplayer *xlplayer, mad_fixed_t sample)
    {
    float ret;
    
    if (xlplayer->dither)
        {
        ret = floorf((float)sample / (float)(1L << (MAD_F_SCALEBITS - 18)));
    
        if (rand_r(&xlplayer->seed) < (RAND_MAX >> 1))
            ret -= 1.0f;
        if (rand_r(&xlplayer->seed) > (RAND_MAX >> 1))
            ret += 1.0f;
        return ret / 262144.0f;
        }
    else
        return sample / (float)(1L << MAD_F_SCALEBITS);
    }   

static int mp3decode_get_frame(struct xlplayer *xlplayer)
    {
    struct mp3decode_vars *self = xlplayer->dec_data;
    size_t nb;

    if (mad_frame_decode(&(self->frame), &(self->stream)) != 0)
        {
        if (self->stream.next_frame)
            {
            nb = self->read_buffer + self->bytes_in_buffer - self->stream.next_frame;
            memmove(self->read_buffer, self->stream.next_frame, nb);
            self->bytes_in_buffer = nb;
            }
        switch (self->stream.error)
            {
            case MAD_ERROR_BUFLEN:
                self->bytes_in_buffer += (nb = fread(self->read_buffer + self->bytes_in_buffer, 1, BSIZ - self->bytes_in_buffer, self->fp));
                if (nb == 0 || ferror(self->fp))
                    {
                    return 0;
                    break;
                    }
                mad_stream_buffer(&(self->stream), self->read_buffer, self->bytes_in_buffer);
                break;
            default:
                if (self->stream.error)
                    {
                    //fprintf(stderr, "got error code 0x%04X\n", self->stream.error);
                    mad_stream_buffer(&(self->stream), self->read_buffer, self->bytes_in_buffer);
                    return -1;
                    }
                mad_stream_buffer(&(self->stream), self->read_buffer, self->bytes_in_buffer);
            }
        return -1;
        }
    else
        return 1;
    }

static void mp3decode_eject(struct xlplayer *xlplayer)
    {
    struct mp3decode_vars *self = xlplayer->dec_data;
 
    if (self->lrb)
        jack_ringbuffer_free(self->lrb);
    if (self->rrb)
        jack_ringbuffer_free(self->rrb);
    if (self->resample)
        {
        if (xlplayer->src_data.data_in)
            free(xlplayer->src_data.data_in);
        if (xlplayer->src_data.data_out)
            free(xlplayer->src_data.data_out);
        xlplayer->src_state = src_delete(xlplayer->src_state);
        }
    mad_synth_finish(&(self->synth));
    mad_stream_finish(&(self->stream));
    mad_frame_finish(&(self->frame));
    mp3_tag_cleanup(&self->taginfo);
    fclose(self->fp);
    free(self->read_buffer);
    free(self);
    fprintf(stderr, "finished eject\n");
    }

static void mp3decode_init(struct xlplayer *xlplayer)
    {
    struct mp3decode_vars *self = xlplayer->dec_data;
    struct mp3taginfo *ti = &self->taginfo;
    off_t start, end, offset;
    int retcode, dump, index, rbsize, goterror;
    int src_error, luv1, luv2, samples;
    float size, seek_pc, frac, scale;

    if (xlplayer->seek_s)
        {
        if (ti->tlen)
            size = (float)ti->tlen / 1000.0F;
        else
            size = (float)xlplayer->size;
            
        if (ti->have_bytes)
            {
            start = ti->first_byte;
            end = start + ti->bytes;
            }
        else
            {
            start = (float)ftell(self->fp);
            fseek(self->fp, 0, SEEK_END);
            end = (float)ftell(self->fp);
            }
            
        if (ti->have_toc)
            {
            fprintf(stderr, "mp3decode_init: calculating seek offset using VBR TOC\n");
            seek_pc = (float)xlplayer->seek_s / size * 100.0F;
            if (seek_pc > 99.95F)
                seek_pc = 99.95F;
            index = (int)seek_pc;
            frac = seek_pc - index;
            luv1 = ti->toc[index];
            if (index < 99)
                luv2 = ti->toc[index + 1];
            else
                luv2 = 256;
            scale = ((luv2 - luv1) * frac + luv1) / 256.0F;
            offset = (end - start) * scale + start;
            }
        else
            offset = (end - start) * (float)xlplayer->seek_s / (float)size + start;

        fseek(self->fp, (long)offset, SEEK_SET);
        
        self->bytes_in_buffer = fread(self->read_buffer, 1, BSIZ, self->fp);
        if (self->bytes_in_buffer == 0 || ferror(self->fp))
            {
            fprintf(stderr, "mp3decode_init: seeked to end of input file\n");
            mp3decode_eject(xlplayer);
            xlplayer->playmode = PM_STOPPED;
            xlplayer->command = CMD_COMPLETE;
            return;
            }
        mad_stream_buffer(&(self->stream), self->read_buffer, self->bytes_in_buffer);
        
        for (dump = goterror = 0; dump < 3 || goterror; dump++)
            {
            goterror = 0;
            while ((retcode = mp3decode_get_frame(xlplayer)) < 0)
                goterror = TRUE;
            if (retcode == 0 || dump == 15)
                {
                mp3decode_eject(xlplayer);
                xlplayer->playmode = PM_STOPPED;
                xlplayer->command = CMD_COMPLETE;
                return;
                }
            }
        }
    else
        if (self->errors)
            {
            fprintf(stderr, "skipping past errors at start of file\n");
            for (dump = goterror = 0; dump < 3 || goterror; dump++)
                {
                goterror = 0;
                while ((retcode = mp3decode_get_frame(xlplayer)) < 0)
                    goterror = TRUE;
                if (retcode == 0 || dump == 15)
                    {
                    fprintf(stderr, "giving up\n");
                    mp3decode_eject(xlplayer);
                    xlplayer->playmode = PM_STOPPED;
                    xlplayer->command = CMD_COMPLETE;
                    return;
                    }
                }
            }

    mad_synth_frame(&(self->synth), &(self->frame));
    self->nchannels = self->synth.pcm.channels;
    self->samplerate = self->synth.pcm.samplerate;
    if ((self->resample = self->samplerate != xlplayer->samplerate))
        {
        fprintf(stderr, "Configuring resampler\n");
        xlplayer->src_data.output_frames = 0;
        xlplayer->src_data.data_in = NULL;
        xlplayer->src_data.data_out = NULL;
        xlplayer->src_data.src_ratio = (double)xlplayer->samplerate / (double)self->samplerate;
        xlplayer->src_data.end_of_input = 0;
        xlplayer->src_state = src_new(xlplayer->rsqual, self->nchannels, &src_error);
        if (src_error)
            {
            fprintf(stderr, "mp3decode_init: %s src_new reports - %s\n", xlplayer->playername, src_strerror(src_error));
            self->resample = 0;
            mp3decode_eject(xlplayer);
            xlplayer->playmode = PM_STOPPED;
            xlplayer->command = CMD_COMPLETE;
            }
        }
    samples = self->synth.pcm.length;
    rbsize = (samples * 2 + ti->end_frames_drop) * sizeof (float);
    self->lrb = jack_ringbuffer_create(rbsize);
    self->rrb = jack_ringbuffer_create(rbsize);
    }

static void mp3decode_play(struct xlplayer *xlplayer)
    {
    struct mp3decode_vars *self = xlplayer->dec_data;
    struct mp3taginfo *ti = &self->taginfo;
    struct mad_pcm *pcm;
    jack_default_audio_sample_t *lp, *rp, *dp, gain;
    mad_fixed_t *left_ch, *right_ch, *lc, *rc;
    int nchannels, nsamples, frame_code, pcmlength, toskip, delay;
    SRC_DATA *src_data = &(xlplayer->src_data);
    struct chapter *chapter;

    pcm = &(self->synth.pcm);
    left_ch = lc = pcm->samples[0];
    if ((nchannels = pcm->channels) == 2)
        right_ch = rc = pcm->samples[1];
    else
        right_ch = rc = NULL;
    pcmlength = pcm->length;

    if (ti->end_frames_drop)
        {
        if (ti->start_frames_drop)        /* calculate initial frame droppage for gapless playback */
            {
            if (pcmlength <= ti->start_frames_drop)
                {
                toskip = pcmlength;
                pcmlength = 0;
                ti->start_frames_drop -= toskip;
                }
            else
                {
                toskip = ti->start_frames_drop;
                pcmlength -= toskip;
                ti->start_frames_drop = 0;
                }
            }
        else
            toskip = 0;
    
        /* this ringbuffer prevents the last ti->end_frames_drop frames from being used */
        /* resulting in gapless playback, provided the lame tag was present */
        jack_ringbuffer_write(self->lrb, (char *)(left_ch + toskip), pcmlength << 2);
        if (nchannels == 2)
            jack_ringbuffer_write(self->rrb, (char *)(right_ch + toskip), pcmlength << 2);
        else
            jack_ringbuffer_write(self->rrb, (char *)(left_ch + toskip), pcmlength << 2);
    
        pcmlength = (jack_ringbuffer_read_space(self->lrb) >> 2) - ti->end_frames_drop;
        if (pcmlength < 0)
            pcmlength = 0;
        if (!self->initial_data && pcmlength)
            self->initial_data = TRUE;
        
        left_ch = lc = malloc(pcmlength << 2);
        right_ch = rc = malloc(pcmlength << 2);
    
        if (!left_ch || !right_ch)
            {
            fprintf(stderr, "mp3decode_play: malloc failure\n");
            exit(5);
            }
    
        jack_ringbuffer_read(self->lrb, (char *)left_ch, pcmlength << 2);
        jack_ringbuffer_read(self->rrb, (char *)right_ch, pcmlength << 2);
        }
    else
        self->initial_data = TRUE;

    if (self->initial_data)
        {
        if (self->resample)
            {
            src_data->end_of_input = (pcmlength == 0);
            src_data->input_frames = pcmlength;
            src_data->data_in = dp = realloc(src_data->data_in, pcmlength * nchannels * sizeof (float));
            src_data->output_frames = (int)(src_data->input_frames * src_data->src_ratio) + 2 + (512 * src_data->end_of_input);
            src_data->data_out = realloc(src_data->data_out, src_data->output_frames * nchannels * sizeof (float));
            for (nsamples = pcmlength; nsamples; nsamples--)
                {
                *dp++ = scale(xlplayer, *(lc++));
                if (nchannels == 2)
                    *dp++ = scale(xlplayer, *(rc++));
                }
            if (src_process(xlplayer->src_state, src_data))
                {
                fprintf(stderr, "mp3decode_play: error occured during resampling\n");
                xlplayer->playmode = PM_EJECTING;
                if (ti->end_frames_drop)
                    {
                    free(left_ch);
                    free(right_ch);
                    }
                return;
                }
            xlplayer_demux_channel_data(xlplayer, src_data->data_out, src_data->output_frames_gen, pcm->channels, 1.f);
            }
        else
            {
            xlplayer->op_buffersize = (nsamples = pcmlength) * sizeof (float);
            if (!(xlplayer->leftbuffer = lp = realloc(xlplayer->leftbuffer, xlplayer->op_buffersize)) && xlplayer->op_buffersize)
                {
                fprintf(stderr, "mp3decode_play: malloc failure\n");
                exit(5);
                }
            if (!(xlplayer->rightbuffer = rp = realloc(xlplayer->rightbuffer, xlplayer->op_buffersize)) && xlplayer->op_buffersize)
                {
                fprintf(stderr, "mp3decode_play: malloc failure\n");
                exit(5);
                }
            while (nsamples--)
                {
                gain = xlplayer_get_next_gain(xlplayer);
                *lp++ = gain * scale(xlplayer, *(lc++));
                if (nchannels == 2)
                    *rp++ = gain * scale(xlplayer, *(rc++));
                }
            if (nchannels == 1)
                memcpy(xlplayer->rightbuffer, xlplayer->leftbuffer, xlplayer->op_buffersize);
            }
        }

    if (ti->end_frames_drop)
        {
        free(left_ch);
        free(right_ch);
        }
    if (self->initial_data)
        xlplayer_write_channel_data(xlplayer);
    while((frame_code = mp3decode_get_frame(xlplayer)) == -1);
    if(frame_code)
        mad_synth_frame(&(self->synth), &(self->frame));
    else
        xlplayer->playmode = PM_EJECTING;

    delay = xlplayer_calc_rbdelay(xlplayer);
    chapter = mp3_tag_chapter_scan(&self->taginfo, xlplayer->play_progress_ms + delay);
    if (chapter && chapter != self->current_chapter)
        {
        self->current_chapter = chapter;
        xlplayer_set_dynamic_metadata(xlplayer, dynamic_metadata_form[chapter->title.encoding], chapter->artist.text, chapter->title.text, chapter->album.text, delay);
        }
    }

int mp3decode_reg(struct xlplayer *xlplayer)
    {
    struct mp3decode_vars *self;
    long start;
    struct chapter *chapter;

    if (!(self = xlplayer->dec_data = calloc(1, sizeof (struct mp3decode_vars))))
        {
        fprintf(stderr, "mp3decode_vars: malloc failure\n");
        return REJECTED;
        }
    if (!(self->fp = fopen(xlplayer->pathname, "r")))
        {
        fprintf(stderr, "mp3decode_test_mp3ness: failed to open file\n");
        free(self);
        return REJECTED;
        }
    mp3_tag_read(&self->taginfo, self->fp);
    start = ftell(self->fp);

    if (!(self->read_buffer = malloc(BSIZ)))
        {
        fprintf(stderr, "mp3decode_test_mp3ness: malloc failure\n");
        fclose(self->fp);
        free(self);
        return REJECTED;
        }
    self->bytes_in_buffer = fread(self->read_buffer, 1, BSIZ, self->fp);
    if (self->bytes_in_buffer < 8192)
        {
        fprintf(stderr, "mp3decode_test_mp3ness: file too small\n");
        fclose(self->fp);
        free(self->read_buffer);
        free(self);
        return REJECTED;
        }
    mad_synth_init(&(self->synth));
    mad_stream_init(&(self->stream));
    mad_frame_init(&(self->frame));
    mad_stream_buffer(&(self->stream), self->read_buffer, self->bytes_in_buffer);
    self->playduration = 0.0F;
    for (;;)
        {
        switch (mp3decode_get_frame(xlplayer))
            {
            case -1:
                self->errors = TRUE;
                if (ftell(self->fp) - start < 32768L)
                    continue;
            case 0:
                mp3decode_eject(xlplayer);
                return REJECTED;
            default:
                xlplayer->dec_init = mp3decode_init;
                xlplayer->dec_play = mp3decode_play;
                xlplayer->dec_eject = mp3decode_eject;
                if ((chapter = mp3_tag_chapter_scan(&self->taginfo, xlplayer->play_progress_ms + 70)))
                    {
                    self->current_chapter = chapter;
                    xlplayer_set_dynamic_metadata(xlplayer, dynamic_metadata_form[chapter->title.encoding], chapter->artist.text, chapter->title.text, chapter->album.text, 0);
                    }
                return ACCEPTED;
            }
        }
    }
