/*
#   xlplayer.h: player decoder module for idjc
#   Copyright (C) 2006-2009 Stephen Fairchild (s-fairchild@users.sourceforge.net)
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

#ifndef XLPLAYER_H
#define XLPLAYER_H

#include "../config.h"
#include <jack/jack.h>
#include <jack/ringbuffer.h>
#include <pthread.h>
#include <stdlib.h>
#include <samplerate.h>
#include <sndfile.h>
#include <signal.h>

#ifdef HAVE_FLAC
#include <FLAC/all.h>
#endif

#include "fade.h"
#include "smoothing.h"

enum command_t {CMD_COMPLETE, CMD_PLAY, CMD_EJECT, CMD_CLEANUP, CMD_THREADEXIT, CMD_PLAYMANY};

enum playmode_t {PM_STOPPED, PM_INITIATE, PM_PLAYING, PM_EJECTING };

enum metadata_t {DM_NONE_NEW, DM_SPLIT_U8, DM_JOINED_U8, DM_SPLIT_L1, DM_JOINED_L1, DM_JOINED_UC, DM_JOINED_UCBE, DM_NOTAG};

struct xlp_dynamic_metadata     /* song titles can change mid-file */
    {                            /* this structure facilitates transmission */
    pthread_mutex_t meta_mutex;  /* back to the user interface */
    char *artist;
    char *title;
    char *album;
    int current_audio_context;
    int rbdelay;
    enum metadata_t data_type;
    };

struct xlplayer
    {
    struct fade *fadein;                /* fade level computation */
    struct fade *fadeout;
    jack_ringbuffer_t *left_ch;         /* main playback buffer */
    jack_ringbuffer_t *right_ch;
    jack_ringbuffer_t *left_fade;       /* buffers used for fade - swapped with above when needed */
    jack_ringbuffer_t *right_fade;
    size_t rbsize;                      /* the size of the jack ringbuffers in bytes */
    int rbdelay;                        /* rough time lag of the ringbuffers in ms */
    size_t op_buffersize;               /* the current size of the player output buffers */
    char *pathname;                     /* the pathname of the music file being played */
    char **playlist;                    /* the playlist as an array of pointers */
    float gain;                         /* amount of gain to apply to the playback */
    int loop;                           /* flag indicating if we loop or come to a stop */
    int seek_s;                         /* the initial seek time of the song in seconds */
    int size;                           /* size of the file in seconds */
    int playlistmode;                   /* set when we are using a local playlist */
    int playlistindex;                  /* current track number we are playing */
    int playlistsize;                   /* the number of tracks in the playlist */
    jack_default_audio_sample_t *leftbuffer;     /* the output buffers */
    jack_default_audio_sample_t *rightbuffer;
    int fade_mode;                      /* deferred fade mode */
    int fadeout_f;                      /* flag indicated if fade is applied upon stopping */
    int jack_flush;                     /* tells the jack callback to flush the ringbuffers */
    int jack_is_flushed;                /* indicates true when jack callback has done the flush */
    unsigned samplerate;                /* the audio sample rate in use by jack */
    int pause;                          /* flag controlling the player paused state */
    int write_deferred;                 /* suppress further generation of audio data */
    u_int64_t samples_written;          /* number of samples written to the ringbuffer */
    int32_t play_progress_ms;           /* the playback progress in milliseconds */
    char *playername;                   /* the name of this player e.g. "left", "right" etc. */
    enum playmode_t playmode;           /* indicates the player mode or state */
    enum command_t command;             /* the command mode */
    size_t avail;                       /* the number of samples available in the ringbuffer */
    int have_data_f;                    /* indicates the presence of audio data */
    int current_audio_context;          /* bumps when started, bumps when stopped. Odd=playing */
    int initial_audio_context;          /* return code placeholder variable for above */
    int dither;                         /* whether to add dither to player output FLAC, MP4, WAV only */
    unsigned int seed;                  /* used for dither */
    pthread_t thread;                   /* thread pointer for the player main loop */
    u_int32_t sleep_samples;            /* used to count off when it is appropriate to call sleep */
    SRC_STATE *src_state;               /* used by resampler */
    SRC_DATA src_data;
    int rsqual;                         /* resample quality */   
    int noflush;                        /* suppresses ringbuffer flushes for gapless playback */
    int *jack_shutdown_f;               /* inidcator that jack has shut down */
    volatile sig_atomic_t watchdog_timer;
    int up;                             /* set to true when the player is fully initialised */
    double pbspeed;                     /* the playback speed as a factor */
    float newpbspeed;                   /* the value the above is updated with */
    SRC_STATE *pbspeed_conv_l;          /* libsamplerate handle for playback speed control - left channel */
    SRC_STATE *pbspeed_conv_r;
    SRC_STATE *pbspeed_conv_lf;         /* as above but for fade buffer */
    SRC_STATE *pbspeed_conv_rf;
    float *pbsrb_l;                     /* input buffers for the playback speed converter */
    float *pbsrb_r;
    float *pbsrb_lf;
    float *pbsrb_rf;
    long pbs_norm_read_qty;             /* the number of normal samples which will be read from left and right channels */
    long pbs_fade_read_qty;             /* the number of fadeout samples which will be read */
    int pbs_exchange;                   /* keeps correct association for input buffers after a buffer swap occurs */
    void *dec_data;                     /* points to audio decoder data */
    void (*dec_init)(struct xlplayer *);/* audio decoder init function */
    void (*dec_play)(struct xlplayer *);/* function that decodes one frame of audio data */
    void (*dec_eject)(struct xlplayer *);/* function that cleans up after the decoder */
    struct xlp_dynamic_metadata dynamic_metadata;
    int usedelay;                       /* client to delay dynamic metadata display */
    float silence;                      /* the number of seconds of silence */
    int samples_cutoff;                 /* audio cutoff imminent when fewer than this value samples remain */
    
    int use_sv;                         /* speed variance version of read function will be used */
    
    float *lcb;                         /* left channel buffer */
    float *rcb;                         /* right channel buffer */
    float *lcfb;                        /* left channel fade buffer */
    float *rcfb;                        /* right channel fade buffer */
    
    float *lcp, *rcp, *lcfp, *rcfp;     /* pointers into the above buffers */
    
    float ls, rs;                       /* the current audio sample stereo pair -- prior to gain adjustment */
    float peak;                         /* peak = MAX(peak, MAX(ABS(ls), ABS(rs))) */
    
    struct smoothing_mute mute_aud;
    struct smoothing_mute mute_str;
    struct smoothing_volume volume;

    float cf_l_gain, cf_r_gain;         /* per channel gain adjustment -- e.g. for apply crossfade */
    int cf_aud;                         /* apply crossfade on dj audio */
    float ls_aud, ls_str;               /* the gain adjusted audio samples */
    float rs_aud, rs_str;
    uint32_t id;                        /* player identity e.g. player 3 = 1 << 3 */
    };

/* xlplayer_create: create an instance of the player */
struct xlplayer *xlplayer_create(int samplerate, double duration, char *playername, sig_atomic_t *shutdown_f, int *vol_c, float vol_scale, int *strmute_c, int *audmute_c, float cutoff_s);
/* xlplayer_destroy: the opposite of xlplayer_create */
void xlplayer_destroy(struct xlplayer *);

/* xlplayer_play: starts the player on a particular track immediately
* if a track is currently playing eject is called
* return value: a context-id for this track */
int xlplayer_play(struct xlplayer *self, char *pathname, int seek_s, int size, float gain_db, int id);

/* xlplayer_playmany: starts the player on a playlist
* if a track is currently playing eject is called, also can set looping with this function
* return value: a context-id for this playlist */
int xlplayer_playmany(struct xlplayer *self, char *playlist, int loop_f);

/* xlplayer_play_noflush: starts the player without flushing out old data from the ringbuffer */
int xlplayer_play_noflush(struct xlplayer *self, char *pathname, int seek_s, int size, float gain_db, int id);

/* xlplayer_cancelplaynext: cancels the automatic playing of the next track 
* the current track is allowed to continue playing */
void xlplayer_cancelplaynext(struct xlplayer *self);

/* xlplayer_pause: pauses the current track */
void xlplayer_pause(struct xlplayer *self);
/* xlplayer_unpause: unpause the current track */
void xlplayer_unpause(struct xlplayer *self);
/* xlplayer_dither: turns on/off dither on players */
void xlplayer_dither(struct xlplayer *self, int dither_f);
/* xlplayer_eject: stops the current track with a fadeout unless the track is paused */
/* this call will also cancel any track cued with playnext command */
/* to suppress fadeout call pause beforehand */
void xlplayer_eject(struct xlplayer *self);

/* read_from_player: reads out the audio data from the buffers */
/* this is meant to be run inside the jack callback */
size_t read_from_player(struct xlplayer *self, jack_default_audio_sample_t *left_buf, jack_default_audio_sample_t *right_buf, jack_default_audio_sample_t *left_fbuf, jack_default_audio_sample_t *right_fbuf, jack_nframes_t nframes);

/* read_from_player_sv: reads out the audio data from the buffers but provides speed variance (pitch control) */
/* this is meant to be run inside the jack callback */
size_t read_from_player_sv(struct xlplayer *self, jack_default_audio_sample_t *left_buf, jack_default_audio_sample_t *right_buf, jack_default_audio_sample_t *left_fbuf, jack_default_audio_sample_t *right_fbuf, jack_nframes_t nframes);

/* calculate the gain for fading in - used when seeking to prevent clicks */
jack_default_audio_sample_t xlplayer_get_next_gain(struct xlplayer *self);

/* put audio data in format recognised by jack and libsamplerate */
float *xlplayer_make_audio_to_float(struct xlplayer *self, float *buffer, uint8_t *data, int num_samples, int bits_per_sample, int num_channels);

/* splits audio data into separate audio streams, ready for writing */
void xlplayer_demux_channel_data(struct xlplayer *self, jack_default_audio_sample_t *buffer, int num_samples, int num_channels, float scale);

/* cause the cached pcm data to be written out to the jack ringbuffer */
void xlplayer_write_channel_data(struct xlplayer *self);

/* provide data for sending back to the user interface */
void xlplayer_set_dynamic_metadata(struct xlplayer *xlplayer, enum metadata_t type, char *artist, char *title, char *album, int delay);

/* return the delay caused by the ringbuffer */
int xlplayer_calc_rbdelay(struct xlplayer *xlplayer);

/* this sets the speed of fading for a particular mode */
void xlplayer_set_fadesteps(struct xlplayer *self, int fade_step);

/* pull player audio from the ringbuffer into the readout buffers */
size_t xlplayer_read_start(struct xlplayer *self, jack_nframes_t nframes);

/* compute the next sample */
void xlplayer_read_next(struct xlplayer *self);

/* volume control and mute toggle smoothing single iteration */
void xlplayer_smoothing_process(struct xlplayer *self);

void xlplayer_stats(struct xlplayer *self);

/* group process all players from the list */
void xlplayer_read_start_all(struct xlplayer **list, jack_nframes_t nframes);
void xlplayer_read_next_all(struct xlplayer **list);
void xlplayer_smoothing_process_all(struct xlplayer **list);
void xlplayer_stats_all(struct xlplayer **list);

#endif /* XLPLAYER_H */
