/*
#   mic.h: wrapper for microphone agc that provides mixing/muting
#   Copyright (C) 2010 Stephen Fairchild (s-fairchild@users.sourceforge.net)
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

#include <jack/jack.h>
#include "agc.h"

struct mic
   {
   /* outputs */
   float unp;       /* barely processed audio without muting */
   float unpm;      /* barely processed audio with muting */
   float unpmdj;    /* barely processed audio for the dj mix */
   float lrc;       /* both audio channels without muting */
   float lc;        /* audio left channel without muting */
   float rc;        /* audio right channel without muting */
   float lcm;       /* audio left channel with muting */
   float rcm;       /* audio right channel with muting */
   
   /* control inputs */
   int open;        /* mic open/close */
   int invert;      /* mic signal is inverted */
   float gain;      /* amount of signal boost in db */
   int mode;        /* 0 = off, 1 = simple, 2 = complex, 3 = subordinate */
   int pan;         /* stereo panning on a scale 1-100 */
   int pan_active;  /* whether to pan at all */
   int mode_request;/* request to change mode */
   
   /* state variables and resources */
   int id;          /* numeric identifier */
   struct mic *host;/* the dominant mic in a pairing */
   struct mic *partner; /* the partnerable mic */
   struct agc *agc; /* automatic gain control and much more */
   float sample;    /* storage for the audio sample undergoing processing */
   float sample_rate; /* used for smoothed mute timing */
   float mgain;   /* mono gain value (absolute gain) */
   float lgain;   /* left gain value (pan relative) */
   float rgain;   /* right gain value (pan relative) */
   float igain;   /* inversion gain value (inversion relative) */
   float mute;    /* gain applied by soft mute control */
   float djmute;  /* gain applied for muting from the dj mix */
   float peak;    /* highest signal level since last call to mic_getpeak */
   jack_port_t *jack_port; /* jack port handle */
   jack_default_audio_sample_t *jadp; /* jack audio data pointer */
   jack_nframes_t nframes; /* jack buffer size */
   char *default_mapped_port_name; /* the natural partner port or NULL*/
   };

void mic_process_start_all(struct mic **mics, jack_nframes_t nframes);
float mic_process_all(struct mic **mics);
void mic_stats_all(struct mic **mics);
struct mic **mic_init_all(int n_mics, jack_client_t *client);
void mic_free_all(struct mic **self);
void mic_valueparse(struct mic *s, char *param);
