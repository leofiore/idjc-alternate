/*
#   mp3dec.c: decodes mp3 file format for xlplayer
#   Copyright (C) 2012 Stephen Fairchild (s-fairchild@users.sourceforge.net)
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
#include <pthread.h>
#include <unistd.h>
#include "xlplayer.h"
#include "mp3dec.h"
#include "bsdcompat.h"

#define TRUE 1
#define FALSE 0
#define ACCEPTED 1
#define REJECTED 0

static int decoder_library_ok;

int dynamic_metadata_form[4] = { DM_SPLIT_L1, DM_NOTAG, DM_NOTAG, DM_SPLIT_U8 };

static void mp3decode_eject(struct xlplayer *xlplayer)
    {
    struct mp3decode_vars *self = xlplayer->dec_data;

    if (self->resample)
        {
        if (xlplayer->src_data.data_out)
            free(xlplayer->src_data.data_out);
        xlplayer->src_state = src_delete(xlplayer->src_state);
        }

    mp3_tag_cleanup(&self->taginfo);
    mpg123_close(self->mh);
    mpg123_delete(self->mh);
    fclose(self->fp);
    free(self);
    fprintf(stderr, "finished eject\n");
    }


static void mp3decode_init(struct xlplayer *xlplayer)
    {
    }


static void mp3decode_play(struct xlplayer *xlplayer)
    {
    struct mp3decode_vars *self = xlplayer->dec_data;
    struct chapter *chapter;
    long rate;
    int channels, encoding, samples, rv, delay;
    off_t num;
    float *fppcm;
    size_t len;
    int src_error;

    switch(rv = mpg123_decode_frame(self->mh, &num, (unsigned char **)&fppcm, &len))
        {
        case MPG123_DONE:
            if (self->resample)
                {
                xlplayer->src_data.input_frames = 0;
                xlplayer->src_data.end_of_input = 1;
                if ((src_error = src_process(xlplayer->src_state, &xlplayer->src_data)))
                    fprintf(stderr, "mp3decode_play: %s src_process reports - %s\n", xlplayer->playername, src_strerror(src_error));
                
                xlplayer_demux_channel_data(xlplayer, xlplayer->src_data.data_out, xlplayer->src_data.output_frames_gen, 2, 1.f);
                xlplayer_write_channel_data(xlplayer);
                }
            break;

        case MPG123_NEW_FORMAT:
            if (mpg123_getformat(self->mh, &rate, &channels, &encoding) != MPG123_OK)
                {
                fprintf(stderr, "mp3decode_play: mpg123_getformat failed\n");
                break;
                }

            if (channels != MPG123_STEREO || encoding != MPG123_ENC_FLOAT_32)
                {
                fprintf(stderr, "mp3decode_play: unusable data format\n");
                break;
                }

        case MPG123_OK:
            if ((samples = len / (2 * sizeof (float))) > 0)
                {
                if (self->resample)
                    {
                    xlplayer->src_data.data_in = fppcm;
                    xlplayer->src_data.input_frames = samples;

                    if ((src_error = src_process(xlplayer->src_state, &xlplayer->src_data)))
                        {
                        fprintf(stderr, "mp3decode_play: %s src_process reports - %s\n", xlplayer->playername, src_strerror(src_error));
                        break;
                        }
                        
                    xlplayer_demux_channel_data(xlplayer, xlplayer->src_data.data_out, xlplayer->src_data.output_frames_gen, 2, 1.f);
                    }
                else
                    xlplayer_demux_channel_data(xlplayer, fppcm, samples, 2, 1.f);

                delay = xlplayer_calc_rbdelay(xlplayer);
                chapter = mp3_tag_chapter_scan(&self->taginfo, xlplayer->play_progress_ms + delay);
                if (chapter && chapter != self->current_chapter)
                    {
                    self->current_chapter = chapter;
                    xlplayer_set_dynamic_metadata(xlplayer, dynamic_metadata_form[chapter->title.encoding], chapter->artist.text, chapter->title.text, chapter->album.text, delay);
                    }
                xlplayer_write_channel_data(xlplayer);
                }

            return;

        default:
            fprintf(stderr, "mp3decode_play: mpg123_decode_frame unexpected return code %d\n", rv);
            break;
        }

    xlplayer->playmode = PM_EJECTING;
    }


static void decoder_library_init()
    {
    if((decoder_library_ok = (mpg123_init() == MPG123_OK)))
        atexit(mpg123_exit);
    }


int mp3decode_reg(struct xlplayer *xlplayer)
    {
    static pthread_once_t once_control = PTHREAD_ONCE_INIT;
    struct mp3decode_vars *self;
    struct chapter *chapter;
    int fd, rv;
    long rate;
    int channels, encoding;
    int src_error;

    pthread_once(&once_control, decoder_library_init);
    if (!decoder_library_ok)
        {
        fprintf(stderr, "mp3decode_reg: decoder library is not ok\n");
        goto rej;
        }


    if (!(self = xlplayer->dec_data = calloc(1, sizeof (struct mp3decode_vars))))
        {
        fprintf(stderr, "mp3decode_reg: malloc failure\n");
        goto rej;
        }


    if (!(self->mh = mpg123_new(NULL, NULL)))
        {
        fprintf(stderr, "mp3decode_reg: handle not okay");
        goto rej_;
        }

#ifdef MPG123_AUTO_RESAMPLE
    if (mpg123_param(self->mh, MPG123_REMOVE_FLAGS, MPG123_AUTO_RESAMPLE, 0.0) != MPG123_OK)
        {
        fprintf(stderr, "mpgdecode_reg: failed to turn off auto resampling\n");
        goto rej_;
        }
#endif

    if (mpg123_param(self->mh, MPG123_ADD_FLAGS, MPG123_FORCE_STEREO, 0.0) != MPG123_OK)
        {
        fprintf(stderr, "mpgdecode_reg: failed to set flags");
        goto rej_;
        }

    if (mpg123_format_none(self->mh) != MPG123_OK)
        {
        fprintf(stderr, "mp3decode_reg: failed to clear output formats");
        goto rej_;
        }

    /* all the permitted mp3 sample rates are enabled
     * forced stereo is in effect so no need to add mono formats
     */
    mpg123_format(self->mh, 48000, MPG123_STEREO, MPG123_ENC_FLOAT_32);
    mpg123_format(self->mh, 44100, MPG123_STEREO, MPG123_ENC_FLOAT_32);
    mpg123_format(self->mh, 32000, MPG123_STEREO, MPG123_ENC_FLOAT_32);
    mpg123_format(self->mh, 24000, MPG123_STEREO, MPG123_ENC_FLOAT_32);
    mpg123_format(self->mh, 22050, MPG123_STEREO, MPG123_ENC_FLOAT_32);
    mpg123_format(self->mh, 16000, MPG123_STEREO, MPG123_ENC_FLOAT_32);
    mpg123_format(self->mh, 12000, MPG123_STEREO, MPG123_ENC_FLOAT_32);
    mpg123_format(self->mh, 11025, MPG123_STEREO, MPG123_ENC_FLOAT_32);
    mpg123_format(self->mh, 8000, MPG123_STEREO, MPG123_ENC_FLOAT_32);

    if (!(self->fp = fopen(xlplayer->pathname, "r")))
        {
        fprintf(stderr, "mp3decode_reg: failed to open %s\n", xlplayer->pathname);
        goto rej_;
        }

    mp3_tag_read(&self->taginfo, self->fp);
    lseek(fd = fileno(self->fp), 0, SEEK_SET);

    if ((rv = mpg123_open_fd(self->mh, fd)) != MPG123_OK)
        {
        fprintf(stderr, "mp3decode_reg: mpg123_open_fd failed with return value %d\n", rv);
        goto rej__;
        }
        
    if (mpg123_getformat(self->mh, &rate, &channels, &encoding) != MPG123_OK || channels != 2)
        {
        fprintf(stderr, "mp3decode_reg: mpg123_getformat returned unexpected value\n");
        goto rej___;
        }
    
    if (rate != xlplayer->samplerate)
        {
        fprintf(stderr, "mp3decode_reg: configuring resampler\n");

        xlplayer->src_state = src_new(xlplayer->rsqual, channels, &src_error);
        if (src_error)
            {
            fprintf(stderr, "mp3decode_reg: src_new reports %s\n", src_strerror(src_error));
            goto rej___;
            }

        xlplayer->src_data.src_ratio = (double)xlplayer->samplerate / (double)rate;
        xlplayer->src_data.end_of_input = 0;
        
        size_t output_frames = (size_t)(xlplayer->src_data.src_ratio * 1.1 * 1152);
        xlplayer->src_data.output_frames = (long)output_frames;
        if (!(xlplayer->src_data.data_out = malloc(output_frames * 2 * sizeof (float))))
            {
            fprintf(stderr, "mp3decode_reg: malloc failure\n");
            goto rej____;
            }

        self->resample = TRUE;
        }

    xlplayer->dec_init = mp3decode_init;
    xlplayer->dec_play = mp3decode_play;
    xlplayer->dec_eject = mp3decode_eject;


    if ((chapter = mp3_tag_chapter_scan(&self->taginfo, xlplayer->play_progress_ms + 70)))
        {
        self->current_chapter = chapter;
        xlplayer_set_dynamic_metadata(xlplayer, dynamic_metadata_form[chapter->title.encoding], chapter->artist.text, chapter->title.text, chapter->album.text, 0);
        }

    if (xlplayer->seek_s)
        if (mpg123_seek(self->mh, (off_t)rate * xlplayer->seek_s, SEEK_SET) < 0)
            {
            fprintf(stderr, "mp3decode_init: seek failed\n");
            mp3decode_eject(xlplayer);
            xlplayer->playmode = PM_STOPPED;
            xlplayer->command = CMD_COMPLETE;
            }

    return ACCEPTED;

    rej____:
    xlplayer->src_state = src_delete(xlplayer->src_state);
    rej___:
    mpg123_delete(self->mh);
    rej__:
    mp3_tag_cleanup(&self->taginfo);
    fclose(self->fp);
    rej_:
    free(self);
    rej:
    return REJECTED;
    }
