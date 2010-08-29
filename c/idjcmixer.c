/*
#   idjcmixer.c: central core of IDJC's mixer.
#   Copyright (C) 2005-2007 Stephen Fairchild (s-fairchild@users.sourceforge.net)
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

#include "gnusource.h"
#include <stdlib.h>
#include <stdio.h>
#include <errno.h>
#include <unistd.h>
#include <math.h>
#include <jack/jack.h>
#include <jack/transport.h>
#include <jack/ringbuffer.h>
#include <jack/statistics.h>
#include <jack/midiport.h>
#include <getopt.h>
#include <string.h>
#include <fcntl.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <signal.h>
#include <locale.h>

#include "kvpparse.h"
#include "dbconvert.h"
#include "compressor.h"
#include "xlplayer.h"
#include "ialloc.h"
#include "speextag.h"
#include "sndfileinfo.h"
#include "avcodecdecode.h"
#include "oggdec.h"
#include "mic.h"
#include "bsdcompat.h"
#include "dyn_mad.h"
#include "peakfilter.h"

#define TRUE 1
#define FALSE 0

/* playlength of ring buffer contents */
#define RB_SIZE 10.0
/* number of samples in the fade (ring) buffer */
#define FB_SIZE (RB_SIZE * sr)
/* number of bytes in the MIDI queue buffer */
#define MIDI_QUEUE_SIZE 1024

/* the different VOIP modes */
#define NO_PHONE 0
#define PHONE_PUBLIC 1
#define PHONE_PRIVATE 2

typedef jack_default_audio_sample_t sample_t;

/* values of the volume sliders in the GUI */
int volume, volume2, crossfade, jinglesvolume, interludevol, mixbackvol, crosspattern;
/* back and forth status indicators re. jingles */
int jingles_playing, jingles_audio_f;
/* used for gapless playback to indicate an almost empty buffer */
int left_audio_runout = 0, right_audio_runout = 0;
/* the main-player unmute buttons */
int left_stream = 1, left_audio = 1, right_stream = 1, right_audio = 1;
/* status variables for the button cluster in lower right of main window */
int aux_on, mic_on, mixermode = NO_PHONE;
/* TRUE when the transitioning between on and off */
int aux_flux;
/* simple mixer mode: uses less space on the screen and less cpu as well */
int simple_mixer;
/* currentvolumes are used to implement volume smoothing */
int current_volume, current_volume2, current_jingles_volume, current_interlude_volume,
    current_crossfade, currentmixbackvol, current_crosspattern; 
/* the id. number microphone filter we are using */
int mic_filter;
/* value of the stream mon. button */
int stream_monitor = 0;
/* when this is set the end of track alarm is started */
int eot_alarm_set = 0;
/* set when end of track alarm is active */
int eot_alarm_f = 0;
/* threshold values for a premature indicator that a player is about to finish */
int jingles_samples_cutoff;
int player_samples_cutoff;
/* the number of samples processed this song - used to calculate the player progress bars */
int left_samples_total, right_samples_total;
/* used to implement interlude player fade in/out: true when playing a track */
int main_play;
/* if the main app segfaults or similar this counter will see that the mixer terminates */
int timeout;
int g_shutdown;
/* flag set when jack closes the client thread for example when the jackd is closed */
int jack_closed_f;
/* flag to indicate whether to use the player reading function which supports speed variance */
int speed_variance;
/* buffers that process_audio uses when reading media player data */
sample_t *lp_lc, *lp_rc, *rp_lc, *rp_rc, *jp_lc, *jp_rc, *ip_lc, *ip_rc;
sample_t *lp_lcf, *lp_rcf, *rp_lcf, *rp_rcf, *jp_lcf, *jp_rcf, *ip_lcf, *ip_rcf;
/* used for signal level silence threshold tracking */
sample_t left_peak = -1.0F, right_peak = -1.0F;
/* handle for beat processing */
/*struct beatproc *beat_lp, *beat_rp;*/
/* flag to indicate if audio is routed via dsp interface */
int using_dsp;
/* flag to indicate that stream audio be reduced for improved encode quality */
int twodblimit;
/* handles for mic processing function */
struct mic *mic_1, *mic_2, *mic_3, *mic_4;
/* flag for mp3 decode capability */
int have_mad;
/* size of the fade buffer */
int fb_size;
/* peakfilter handles for stream peak */
struct peakfilter *str_pf_l, *str_pf_r;

/* part of CTRL+C handling */
sigset_t mixersigset;

/* the number of samples worth of data in the fadeout buffer */
jack_nframes_t alarm_size;

float headroom_db;                      /* player muting level when mic is open */
float str_lpeak, str_rpeak;             /* used to store the peak levels */
float str_l_tally, str_r_tally;  /* used to calculate rms value */
int rms_tally_count;
float str_l_meansqrd, str_r_meansqrd;
int reset_vu_stats_f;                   /* when set the mixer will reset the above */
float *dblookup, *antidblookup;         /* a table for speeding up log / antilog operations */
float *fade_table;                      /* a table of values used for autofade */
float dfmod;                            /* used to reduce the ducking factor */
float dj_audio_level;                   /* used to reduce the level of dj audio */
float dj_audio_gain = 1.0;              /* same as above but not in dB */
float current_dj_audio_level = 0.0;

struct compressor stream_limiter =
   {
   0.0, -0.05, -0.2, INFINITY, 1, 1.0F/4000.0F, 0.0, 0.0, 1, 1, 0.0, 0.0
   }, audio_limiter =
   {
   0.0, -0.05, -0.2, INFINITY, 1, 1.0F/4000.0F, 0.0, 0.0, 1, 1, 0.0, 0.0
   }, phone_limiter =
   {
   0.0, -0.05, -0.2, INFINITY, 1, 1.0F/4000.0F, 0.0, 0.0, 1, 1, 0.0, 0.0
   };

struct normalizer str_normalizer =
   {
   0, 0.0F, -12.0F, 1.0F/120000.0F, 1.0F/90000.0F, 12.0
   }, new_normalizer;

int new_normalizer_stats = FALSE;

/* the different player's gain factors */
/* lp=left player, rp=right player, jp=jingles player, ip=interlude player */ 
/* lc=left channel, rc=right channel */
/* aud = the DJs audio, str = the listeners (stream) audio */
/* the initial settings are 'very' temporary */
sample_t lp_lc_aud = 1.0, lp_rc_aud = 1.0, rp_lc_aud = 1.0, rp_rc_aud = 1.0;
sample_t lp_lc_str = 1.0, lp_rc_str = 1.0, rp_lc_str = 0.0, rp_rc_str = 0.0;
sample_t jp_lc_str = 0.0, jp_rc_str = 0.0, jp_lc_aud = 0.0, jp_rc_aud = 0.0;
sample_t ip_lc_str = 0.0, ip_rc_str = 0.0, ip_lc_aud = 0.0, ip_rc_aud = 0.0;
                                /* like above but for fade */
sample_t lp_lc_audf = 1.0, lp_rc_audf = 1.0, rp_lc_audf = 1.0, rp_rc_audf = 1.0;
sample_t lp_lc_strf = 1.0, lp_rc_strf = 1.0, rp_lc_strf = 1.0, rp_rc_strf = 1.0;
sample_t jp_lc_strf = 1.0, jp_rc_strf = 1.0, jp_lc_audf = 1.0, jp_rc_audf = 1.0;
sample_t ip_lc_strf = 1.0, ip_rc_strf = 1.0, ip_lc_audf = 0.0, ip_rc_audf = 0.0;
         
/* used to apply the stereo mix of the microphones */
sample_t mic_l_lc = 1.0, mic_l_rc = 0.0, mic_r_lc = 0.0, mic_r_rc = 1.0;
/* aux input gain factor - typically 1.0=on or 0.0=off */
sample_t aux_lc = 0.0, aux_rc = 0.0;
/* media player mixback level for when in RedPhone mode */
sample_t mb_lc_aud = 1.0, mb_rc_aud = 1.0;
sample_t current_headroom;      /* the amount of mic headroom being applied */
sample_t *eot_alarm_table;      /* the wave table for the DJ alarm */
         
jack_client_t *client;          /* client handle to JACK */
jack_port_t *audio_left_port;   /* handles for the various jack ports */
jack_port_t *audio_right_port;
jack_port_t *dspout_left_port;   /* used for adding audio effects via external program */
jack_port_t *dspout_right_port;
jack_port_t *dspin_left_port;
jack_port_t *dspin_right_port;
jack_port_t *stream_left_port;
jack_port_t *stream_right_port;
jack_port_t *mic_channel_1;
jack_port_t *mic_channel_2;
jack_port_t *mic_channel_3;
jack_port_t *mic_channel_4;
jack_port_t *aux_left_channel;
jack_port_t *aux_right_channel;
jack_port_t *phone_left_send;   /* used for VOIP */
jack_port_t *phone_right_send;
jack_port_t *phone_left_recv;
jack_port_t *phone_right_recv;
jack_port_t *midi_port; /* midi_control */

char midi_queue[MIDI_QUEUE_SIZE];
size_t midi_nqueued= 0;
pthread_mutex_t midi_mutex;

unsigned long sr;               /* the sample rate reported by JACK */

int transport_aware = 0;
jack_transport_state_t transport_state;

struct xlplayer *plr_l, *plr_r, *plr_j, *plr_i; /* pipe reader instance stuctures */

/* these are set in the parse routine - the contents coming from the GUI */
char *mixer_string, *compressor_string, *gate_string, *microphone_string;
char *normalizer_string, *new_mic_string;
char *micl, *micr, *auxl, *auxr, *midi, *audl, *audr, *strl, *strr, *action;
char *mic1, *mic2, *mic3, *mic4;
char *dol, *dor, *dil, *dir;
char *oggpathname, *sndfilepathname, *avformatpathname, *speexpathname, *speextaglist, *speexcreatedby;
char *playerpathname, *seek_s, *size, *playerplaylist, *loop, *resamplequality;
char *mic_param, *fade_mode;
char *rg_db, *headroom;
char *flag;

/* dictionary look-up type thing used by the parse routine */
struct kvpdict kvpdict[] = {
         { "PLRP", &playerpathname },   /* The media-file pathname for playback */
         { "RGDB", &rg_db },            /* Replay Gain volume level controlled at the player end */
         { "SEEK", &seek_s },           /* Playback initial seek time in seconds */
         { "SIZE", &size },             /* Size of the file in seconds */
         { "PLPL", &playerplaylist },   /* A playlist for the media players */
         { "LOOP", &loop },             /* play in a loop */
         { "MIXR", &mixer_string },     /* Control strings */
         { "COMP", &compressor_string },/* packed full of data */
         { "GATE", &gate_string },
         { "MICS", &microphone_string },
         { "NORM", &normalizer_string },
         { "NMIC", &new_mic_string },
         { "MIC1", &mic1 },
         { "MIC2", &mic2 },
         { "MIC3", &mic3 },
         { "MIC4", &mic4 },
         { "AUXL", &auxl },
         { "AUXR", &auxr },
         { "MIDI", &midi },
         { "AUDL", &audl },
         { "AUDR", &audr },
         { "STRL", &strl },
         { "STRR", &strr },
         { "DOL", &dol   },
         { "DOR", &dor   },
         { "DIL", &dil   },
         { "DIR", &dir   },
         { "FADE", &fade_mode },
         { "OGGP", &oggpathname },
         { "SPXP", &speexpathname },
         { "SNDP", &sndfilepathname },
         { "AVFP", &avformatpathname },
         { "SPXT", &speextaglist },
         { "SPXC", &speexcreatedby },
         { "RSQT", &resamplequality },
         { "AGCP", &mic_param },
         { "HEAD", &headroom },
         { "FLAG", &flag },
         { "ACTN", &action },                   /* Action to take */
         { "", NULL }};

/* the rms filter currently in use */
struct rms_calc *lm_rms_filter, *rm_rms_filter;

/* Does this ever get run, or is it cruft? */
void process_silence(jack_nframes_t nframes)
   {
   sample_t *la_buffer = (sample_t *) jack_port_get_buffer(audio_left_port, nframes);
   sample_t *ra_buffer = (sample_t *) jack_port_get_buffer(audio_right_port, nframes);
   sample_t *ls_buffer = (sample_t *) jack_port_get_buffer(audio_left_port, nframes);
   sample_t *rs_buffer = (sample_t *) jack_port_get_buffer(audio_right_port, nframes);
   
   memset(la_buffer, 0, sizeof (jack_default_audio_sample_t) * nframes);
   memset(ra_buffer, 0, sizeof (jack_default_audio_sample_t) * nframes);
   memset(ls_buffer, 0, sizeof (jack_default_audio_sample_t) * nframes);
   memset(rs_buffer, 0, sizeof (jack_default_audio_sample_t) * nframes);
   }
   
/* handle_mute_button: soft on/off for the mute buttons */
void handle_mute_button(sample_t *gainlevel, int switchlevel)
   {
   if (switchlevel)
      {
      if (*gainlevel < 0.99F)           /* switching on */
         {
         *gainlevel += (1.0F - *gainlevel) * 0.09F * 44100.0F / sr;
         if (*gainlevel >= 0.99F)
            *gainlevel = 1.0F;
         }
      }
   else 
      {
      if (*gainlevel > 0.0F)            /* switching off */
         {
         *gainlevel -= *gainlevel * 0.075F * (2.0F - *gainlevel) * (2.0F - *gainlevel) * 44100.0F / sr;
         if (*gainlevel < 0.00002)
            *gainlevel = 0.0F;
         }
      }
   }

/* update_smoothed_volumes: stuff that gets run once every 32 samples */
void update_smoothed_volumes()
   {
   static sample_t vol_rescale = 1.0F, vol2_rescale = 1.0F, jingles_vol_rescale = 1.0F, interlude_vol_rescale = 1.0F;
   static sample_t cross_left = 1.0F, cross_right = 0.0F, mixback_rescale = 1.0F;
   static sample_t lp_listen_mute = 1.0F, rp_listen_mute = 1.0F, lp_stream_mute = 1.0F, rp_stream_mute = 1.0F;
   sample_t mic_target, diff;
   static float interlude_autovol = -128.0F, old_autovol = -128.0F;
   float vol, halfdelta;
   float xprop, yprop;
   const float bias = 0.35386F;

   timeout++;
   
   if (dj_audio_level != current_dj_audio_level)
      {
      current_dj_audio_level = dj_audio_level;
      dj_audio_gain = db2level(dj_audio_level);
      }
   
   if (crossfade != current_crossfade || crosspattern != current_crosspattern)
      {
      current_crosspattern = crosspattern;

      if (crossfade > current_crossfade)
         current_crossfade++;
      else
         current_crossfade--;

      if (current_crosspattern == 0)
         {
         /* This crossfader is based on a linear potentiometer with a pull-up resistor (bias) */
         xprop = current_crossfade * 0.01F;
         yprop = -xprop + 1.0F;
         cross_left = yprop / ((xprop * bias) / (xprop + bias) + yprop);
         cross_right = xprop / ((yprop * bias) / (yprop + bias) + xprop); 
         
         /* Okay, but now for stage 2 to add a steep slope. */
         if (xprop >= 0.5F)
            cross_left /= 1 + (xprop - 0.5) * 8.0F;
         else
            cross_right /= 1 + (yprop - 0.5) * 8.0F;
         }
      else if (current_crosspattern == 1)
         {
         if (current_crossfade > 55) 
            {
            if (current_crossfade < 100)
               {
               yprop = -current_crossfade + 55;
               cross_left = db2level(0.8f * yprop);
               }
            else
               cross_left = 0.0f;
            cross_right = 1.0;
            }
         else if (current_crossfade < 45)
            {
            if (current_crossfade > 0)
               {
               yprop = current_crossfade - 45;
               cross_right = db2level(0.8f * yprop);
               }
            else
               cross_right = 0.0f;
            cross_left = 1.0;
            }
         else
            cross_left = cross_right = 1.0;
         }
      }

   if (volume != current_volume)
      {
      if (volume > current_volume)
         current_volume++;
      else
         current_volume--;
      vol_rescale = 1.0F/powf(10.0F,current_volume/55.0F);      /* a nice logarithmic volume scale */
      }
   if (volume2 != current_volume2)
      {
      if (volume2 > current_volume2)
         current_volume2++;
      else
         current_volume2--;
      vol2_rescale = 1.0F/powf(10.0F,current_volume2/55.0F);
      }
      
   if (jinglesvolume != current_jingles_volume)
      {
      if (jinglesvolume > current_jingles_volume)
         current_jingles_volume++;
      else
         current_jingles_volume--;
      jingles_vol_rescale = 1.0F/powf(10.0F,current_jingles_volume/55.0F);
      }
      
   /* interlude_autovol rises and falls as and when no media players are playing */
   /* it indicates the playback volume in dB in addition to the one specified by the user */
   
   old_autovol = interlude_autovol;
   if (main_play == TRUE)
      {
      if (interlude_autovol > -128.0F)
         interlude_autovol -= 0.05F;
      }
   else
      {
      if (interlude_autovol < -20.0F)
         interlude_autovol = -20.0F;
      if (interludevol > -20.0F && interlude_autovol < -10.0F)
         interlude_autovol += 0.5F;
      if (interlude_autovol < 0.0F)
         interlude_autovol += 0.3F;
      }   
   
   if (interludevol != current_interlude_volume || interlude_autovol != old_autovol )
      {
      if (interludevol > current_interlude_volume)
         current_interlude_volume++;
      else
         current_interlude_volume--;
      interlude_vol_rescale = powf(10.0F, -(current_interlude_volume * 0.025 + interlude_autovol * -0.05F));
      }
      
   if (mixbackvol != currentmixbackvol)
      {
      if (mixbackvol > currentmixbackvol)
         currentmixbackvol++;
      else
         currentmixbackvol--;
      mixback_rescale = powf(10.0F, -(currentmixbackvol * 0.018181818F));
      }
   
   handle_mute_button(&lp_listen_mute, left_audio);
   handle_mute_button(&lp_stream_mute, left_stream);
   handle_mute_button(&rp_listen_mute, right_audio);
   handle_mute_button(&rp_stream_mute, right_stream);
   
   /* the factors that will be applied in the mix on the media players */
   lp_lc_aud = lp_rc_aud = vol_rescale * lp_listen_mute;
   rp_lc_aud = rp_rc_aud = vol2_rescale * rp_listen_mute;
   lp_lc_str = lp_rc_str = vol_rescale * cross_left * lp_stream_mute;
   rp_lc_str = rp_rc_str = vol2_rescale * cross_right * rp_stream_mute;
   jp_lc_str = jp_rc_str = jp_lc_aud = jp_rc_aud = jingles_vol_rescale;
   mb_lc_aud = mb_rc_aud = mixback_rescale;
   ip_lc_aud = ip_rc_aud = 0.0F;
   ip_lc_str = ip_rc_str = interlude_vol_rescale;
    
   mic_target = headroom_db * (mic_on ? -1.0F : 0.0F);
   if ((diff = mic_target - current_headroom))
      {
      current_headroom += diff * 0.0666666 * 44100.0 / sr;
      if (mic_target)
         {
         if (diff > -0.00001F)
            {
            current_headroom = mic_target;
            }
         }
      else
         if (diff < 0.0000004F)
            {
            current_headroom = 0.0F; 
            }
      }

   if (jingles_playing)
      vol = current_jingles_volume * 0.06666666F;
   else
      halfdelta = (current_volume - current_volume2) / 2.0F;
      vol = (current_volume - halfdelta) * 0.06666666F;
   dfmod = vol * vol + 1.0F;
   }

/* update_mic_and_aux: provide gradual mute/unmute for aux button */
void update_mic_and_aux()       /* aux mute/unmute smoothing */
   {
   const sample_t onfactor = 0.0006F * 44100.0F / (float)sr;
   const sample_t offfactor = 0.00028F * 44100.0F / (float)sr;
   const sample_t upper = 0.999999;     /* these values are to prevent cpu usage going ^^^^ */
   const sample_t lower = 0.0000004;    /* -120 dB */
   
   if (aux_flux)
      {
      if (aux_on)
         {
         if (aux_lc < upper)
            aux_lc = aux_rc += (1.0F - aux_lc) * onfactor;
         else
            {
            aux_lc = aux_rc = 1.0F;
            aux_flux = !aux_on;
            }
         }   
      else
         {
         if (aux_lc > lower)
            aux_lc = aux_rc -= aux_lc * offfactor;
         else
            {
            aux_lc = aux_rc = 0.0F;
            aux_flux = aux_on;
            }
         }
      }
   }

/* process_audio: the JACK callback routine */
void process_audio(jack_nframes_t nframes)
   {
   int samples_todo;            /* The samples remaining counter in the main loop */
   static float df = 1.0;       /* the ducking factor - generated by the compressor */
   /* the following are used to calculate the microphone mix */
   sample_t lc_s_micmix = 0.0f, rc_s_micmix = 0.0f, d_micmix = 0.0f;
   /* the following are used to apply the output of the compressor code to the audio levels */
   sample_t compressor_gain = 1.0, str_normalizer_gain;
   /* a counter variable used to trigger the volume smoothing on a regular basis */
   static unsigned vol_smooth_count = 0;
   /* index values for reading from a table of fade gain values */
   static jack_nframes_t alarm_index = 0;
   /* pointers to buffers provided by JACK */
   sample_t *lap, *rap, *lsp, *rsp, *lxp, *rxp, *lpsp, *rpsp, *lprp, *rprp;
   sample_t *mp_1, *mp_2, *mp_3, *mp_4;
   sample_t *la_buffer, *ra_buffer, *ls_buffer, *rs_buffer, *lps_buffer, *rps_buffer;
   sample_t *dolp, *dorp, *dilp, *dirp, *dol_buffer, *dor_buffer, *dil_buffer, *dir_buffer;
   /* ponters to buffers for reading the media players */
   sample_t *lplcp, *lprcp, *rplcp, *rprcp, *jplcp, *jprcp, *iplcp, *iprcp;
   /* pointers to buffers for fading */
   sample_t *lplcpf, *lprcpf, *rplcpf, *rprcpf, *jplcpf, *jprcpf, *iplcpf, *iprcpf;
   /* temporary storage for processed fade values */
   sample_t lp_lc_fade, lp_rc_fade, rp_lc_fade, rp_rc_fade;
   sample_t jp_lc_fade, jp_rc_fade, ip_lc_fade, ip_rc_fade;
   /* midi_control */
   void *midi_buffer;
   jack_midi_event_t midi_event;
   jack_nframes_t midi_nevents, midi_eventi;
   int midi_command_type, midi_channel_id;
   int pitch_wheel;

   if (timeout > 8000)
      {
      if (!g_shutdown)
         {
         fprintf(stderr, "timeout exceeded\n");
         g_shutdown = TRUE;
         }
      plr_l->command = CMD_COMPLETE;
      plr_r->command = CMD_COMPLETE;
      plr_j->command = CMD_COMPLETE;
      plr_i->command = CMD_COMPLETE;
      }

   /* midi_control. read incoming commands forward to gui */
   midi_buffer = jack_port_get_buffer(midi_port, nframes);
   midi_nevents = jack_midi_get_event_count(midi_buffer);
   if (midi_nevents!=0)
      {
      pthread_mutex_lock(&midi_mutex);
      for (midi_eventi = 0; midi_eventi < midi_nevents; midi_eventi++)
         {
         if (jack_midi_event_get(&midi_event, midi_buffer, midi_eventi) != 0)
            {
            fprintf(stderr, "Error reading MIDI event from JACK\n");
            continue;
            }
         if  (midi_nqueued+12 > MIDI_QUEUE_SIZE) /* max length of command */
            {
            fprintf(stderr, "MIDI queue overflow, event lost\n");
            continue;
            }
         midi_command_type= midi_event.buffer[0] & 0xF0;
         midi_channel_id= midi_event.buffer[0] & 0x0F;
         switch (midi_command_type)
            {
            case 0xB0: /* MIDI_COMMAND_CHANGE */
               midi_nqueued+= snprintf(
                  midi_queue+midi_nqueued, MIDI_QUEUE_SIZE-midi_nqueued,
                  ",c%x.%x:%x", midi_channel_id, midi_event.buffer[1], midi_event.buffer[2]
               );
               break;
            case 0x80: /* MIDI_NOTE_OFF */
               midi_nqueued+= snprintf(
                  midi_queue+midi_nqueued, MIDI_QUEUE_SIZE-midi_nqueued,
                  ",n%x.%x:0", midi_channel_id, midi_event.buffer[1]
               );
               break;
            case 0x90: /* MIDI_NOTE_ON */
               midi_nqueued+= snprintf(
                  midi_queue+midi_nqueued, MIDI_QUEUE_SIZE-midi_nqueued,
                  ",n%x.%x:7F", midi_channel_id, midi_event.buffer[1]
               );
               break;
            case 0xFE: /* MIDI_PITCH_WHEEL_CHANGE */
               pitch_wheel= 0x2040 - midi_event.buffer[2] - midi_event.buffer[1]*128;
               if (pitch_wheel < 0) pitch_wheel = 0;
               if (pitch_wheel > 0x7F) pitch_wheel = 0x7F;
               midi_nqueued+= snprintf(
                  midi_queue+midi_nqueued, MIDI_QUEUE_SIZE-midi_nqueued,
                  ",p%x.0:%x", midi_channel_id, pitch_wheel
               );
               break;
            }
         }
      pthread_mutex_unlock(&midi_mutex);
      }

   /* get the data for the jack ports */
   la_buffer = lap = (sample_t *) jack_port_get_buffer (audio_left_port, nframes);
   ra_buffer = rap = (sample_t *) jack_port_get_buffer (audio_right_port, nframes);
   ls_buffer = lsp = (sample_t *) jack_port_get_buffer (stream_left_port, nframes);
   rs_buffer = rsp = (sample_t *) jack_port_get_buffer (stream_right_port, nframes);
   dol_buffer = dolp = (sample_t *) jack_port_get_buffer (dspout_left_port, nframes);
   dor_buffer = dorp = (sample_t *) jack_port_get_buffer (dspout_right_port, nframes);
   dil_buffer = dilp = (sample_t *) jack_port_get_buffer (dspin_left_port, nframes);
   dir_buffer = dirp = (sample_t *) jack_port_get_buffer (dspin_right_port, nframes);
   lps_buffer = lpsp = (sample_t *) jack_port_get_buffer (phone_left_send, nframes);
   rps_buffer = rpsp = (sample_t *) jack_port_get_buffer (phone_right_send, nframes);
   mp_1 = (sample_t *) jack_port_get_buffer (mic_channel_1, nframes);
   mp_2 = (sample_t *) jack_port_get_buffer (mic_channel_2, nframes);
   mp_3 = (sample_t *) jack_port_get_buffer (mic_channel_3, nframes);
   mp_4 = (sample_t *) jack_port_get_buffer (mic_channel_4, nframes);
   lxp = (sample_t *) jack_port_get_buffer (aux_left_channel, nframes);
   rxp = (sample_t *) jack_port_get_buffer (aux_right_channel, nframes);
   lprp = (sample_t *) jack_port_get_buffer (phone_left_recv, nframes);
   rprp = (sample_t *) jack_port_get_buffer (phone_right_recv, nframes);
   
   /* recreate buffers for data read from the pipes via the jack ringbuffer */
   lp_lc = lplcp = irealloc(lp_lc, nframes);
   lp_rc = lprcp = irealloc(lp_rc, nframes);
   rp_lc = rplcp = irealloc(rp_lc, nframes);
   rp_rc = rprcp = irealloc(rp_rc, nframes);
   jp_lc = jplcp = irealloc(jp_lc, nframes);
   jp_rc = jprcp = irealloc(jp_rc, nframes);
   ip_lc = iplcp = irealloc(ip_lc, nframes);
   ip_rc = iprcp = irealloc(ip_rc, nframes);
   
   /* recreate buffers and pointers for fade */
   lp_lcf = lplcpf = irealloc(lp_lcf, nframes);
   lp_rcf = lprcpf = irealloc(lp_rcf, nframes);
   rp_lcf = rplcpf = irealloc(rp_lcf, nframes);
   rp_rcf = rprcpf = irealloc(rp_rcf, nframes);
   jp_lcf = jplcpf = irealloc(jp_lcf, nframes);
   jp_rcf = jprcpf = irealloc(jp_rcf, nframes);
   ip_lcf = iplcpf = irealloc(ip_lcf, nframes);
   ip_rcf = iprcpf = irealloc(ip_rcf, nframes);

   if (!(lp_lc && lp_rc && rp_lc && rp_rc && jp_lc && jp_rc && ip_lc && ip_rc &&
         lp_lcf && lp_rcf && rp_lcf && rp_rcf && jp_lcf && jp_rcf && ip_lcf && ip_rcf))
      {
      if (!g_shutdown)
         {
         printf("Malloc failure in process audio\n");
         g_shutdown = TRUE;
         }
      plr_l->command = CMD_COMPLETE;
      plr_r->command = CMD_COMPLETE;
      plr_j->command = CMD_COMPLETE;
      plr_i->command = CMD_COMPLETE;
      }  

   if (speed_variance)
      read_from_player_sv(plr_l, lp_lc, lp_rc, lp_lcf, lp_rcf, nframes);
   else
      read_from_player(plr_l, lp_lc, lp_rc, lp_lcf, lp_rcf, nframes);
   if (plr_l->have_swapped_buffers_f)
      {
      lp_lc_audf = lp_lc_aud * df;      /* volume levels of player at stoppage time */
      lp_lc_strf = lp_lc_str * df;      /* these are used to modify the fade volume level */
      lp_rc_audf = lp_rc_aud * df;
      lp_rc_strf = lp_rc_str * df; 
      }
   left_audio_runout = (plr_l->avail < player_samples_cutoff);

   if (speed_variance)
      read_from_player_sv(plr_r, rp_lc, rp_rc, rp_lcf, rp_rcf, nframes);
   else
      read_from_player(plr_r, rp_lc, rp_rc, rp_lcf, rp_rcf, nframes);
   if (plr_r->have_swapped_buffers_f)
      {
      rp_lc_audf = rp_lc_aud * df;
      rp_lc_strf = rp_lc_str * df;
      rp_rc_audf = rp_rc_aud * df;
      rp_rc_strf = rp_rc_str * df;
      }
   right_audio_runout = (plr_r->avail < player_samples_cutoff);
      
   read_from_player(plr_j, jp_lc, jp_rc, jp_lcf, jp_rcf, nframes);
   if (plr_j->have_swapped_buffers_f)
      {
      jp_lc_audf = jp_lc_aud * df;
      jp_lc_strf = jp_lc_str * df;
      jp_rc_audf = jp_rc_aud * df;
      jp_rc_strf = jp_rc_str * df;
      } 
   jingles_audio_f = (plr_j->avail > jingles_samples_cutoff);

   read_from_player(plr_i, ip_lc, ip_rc, ip_lcf, ip_rcf, nframes);
   if (plr_i->have_swapped_buffers_f)
      {
      ip_lc_audf = ip_lc_aud * df;
      ip_lc_strf = ip_lc_str * df;
      ip_rc_audf = ip_rc_aud * df;
      ip_rc_strf = ip_rc_str * df;
      } 
      
   /* resets the running totals for the vu meter stats */      
   if (reset_vu_stats_f)
      {
      str_l_tally = str_r_tally = 0.0;
      rms_tally_count = 0;
      reset_vu_stats_f = FALSE;
      }

   if (new_normalizer_stats)
      {
      new_normalizer.level = str_normalizer.level;
      str_normalizer = new_normalizer;
      new_normalizer_stats = FALSE;
      }

   /* there are four mixer modes and the only seemingly efficient way to do them is */
   /* to basically copy a lot of code four times over hence the huge size */
   if (simple_mixer == FALSE && mixermode == NO_PHONE)  /* Fully featured mixer code */
      {
      memset(lps_buffer, 0, nframes * sizeof (sample_t)); /* send silence to VOIP */
      memset(rps_buffer, 0, nframes * sizeof (sample_t));
      for(samples_todo = nframes; samples_todo--; lap++, rap++, lsp++, rsp++, lxp++, rxp++,
                mp_1++, mp_2++, mp_3++, mp_4++,
                lplcp++, lprcp++, rplcp++, rprcp++, jplcp++, jprcp++, iplcp++, iprcp++, dilp++, dirp++, dolp++, dorp++)
         {       
         if (vol_smooth_count++ % 100 == 0) /* Can change volume level every so many samples */
            update_smoothed_volumes();
         mic_process(mic_1, *mp_1);
         mic_process(mic_2, *mp_2);
         mic_process(mic_3, *mp_3);
         mic_process(mic_4, *mp_4);
         lc_s_micmix = mic_1->lcm + mic_2->lcm + mic_3->lcm + mic_4->lcm;
         rc_s_micmix = mic_1->rcm + mic_2->rcm + mic_3->rcm + mic_4->rcm;
         d_micmix = mic_1->unpmdj + mic_2->unpmdj + mic_3->unpmdj + mic_4->unpmdj;
       
         /* ducking calculation - disabled mics have df of 1.0 always */
         {
             float df1 = mic_1->agc->df;
             float df2 = mic_2->agc->df;
             float df3 = mic_3->agc->df;
             float df4 = mic_4->agc->df;
             float hr = db2level(current_headroom);
             
             float w1 = (df1 < df2) ? df1 : df2;
             float w2 = (df3 < df4) ? df3 : df4;
             df = ((w1 < w2) ? w1 : w2) * dfmod;
             df = (df < hr) ? df : hr;
         }

         if (plr_l->fadeindex < FB_SIZE)
            {
            lp_lc_fade = fade_table[plr_l->fadeindex] * *lplcpf++; 
            lp_rc_fade = fade_table[plr_l->fadeindex] * *lprcpf++;
            plr_l->fadeindex += plr_l->fadeoutstep;
            }
         else
            lp_lc_fade = lp_rc_fade = 0.0;
            
         if (plr_r->fadeindex < FB_SIZE)
            {
            rp_lc_fade = fade_table[plr_r->fadeindex] * *rplcpf++; 
            rp_rc_fade = fade_table[plr_r->fadeindex] * *rprcpf++;
            plr_r->fadeindex += plr_r->fadeoutstep;
            }
         else
            rp_lc_fade = rp_rc_fade = 0.0;
         
         if (plr_j->fadeindex < FB_SIZE)
            {
            jp_lc_fade = fade_table[plr_j->fadeindex] * *jplcpf++; 
            jp_rc_fade = fade_table[plr_j->fadeindex] * *jprcpf++;
            plr_j->fadeindex += plr_j->fadeoutstep;
            }
         else
            jp_lc_fade = jp_rc_fade = 0.0;
            
         if (plr_i->fadeindex < FB_SIZE)
            {
            ip_lc_fade = fade_table[plr_i->fadeindex] * *iplcpf++; 
            ip_rc_fade = fade_table[plr_i->fadeindex] * *iprcpf++;
            plr_i->fadeindex += plr_i->fadeoutstep;
            }
         else
            ip_lc_fade = ip_rc_fade = 0.0;
            
         if (aux_flux)
            update_mic_and_aux();               /* mic fade in/out */
            
         if (fabs(*lplcp) > left_peak)          /* peak levels used for song cut-off */
            left_peak = fabs(*lplcp);
         if (fabs(*lprcp) > left_peak)
            left_peak = fabs(*lprcp);
         if (fabs(*rplcp) > right_peak)
            right_peak = fabs(*rplcp);
         if (fabs(*rprcp) > right_peak)
            right_peak = fabs(*rprcp);
         
         /* This is it folks, the main mix */
         *dolp = ((*lplcp * lp_lc_str) + (*rplcp * rp_lc_str) + (*lxp * aux_lc) + (*jplcp * jp_lc_str)) * df + lc_s_micmix + (*iplcp * ip_lc_str) + (ip_lc_fade * ip_lc_strf) + 
         (lp_lc_fade * lp_lc_strf) + (rp_lc_fade * rp_lc_strf) + (jp_lc_fade * jp_lc_strf);
         *dorp = ((*lprcp * lp_rc_str) + (*rprcp * rp_rc_str) + (*rxp * aux_rc) + (*jprcp * jp_rc_str)) * df + rc_s_micmix + (*iprcp * ip_rc_str) + (ip_rc_fade * ip_rc_strf) +
         (lp_rc_fade * lp_rc_strf) + (rp_rc_fade * rp_rc_strf) + (jp_rc_fade * jp_rc_strf);
         
         /* apply normalization */
         str_normalizer_gain = db2level(normalizer(&str_normalizer, *dolp, *dorp));
         
         *dolp *= str_normalizer_gain;
         *dorp *= str_normalizer_gain;
         
         /* hard limit the levels if they go outside permitted limits */
         /* note this is not the same as clipping */
         compressor_gain = db2level(limiter(&stream_limiter, *dolp, *dorp));

         *dolp *= compressor_gain;
         *dorp *= compressor_gain;

         if (using_dsp)
            {
            *lsp = *dilp;
            *rsp = *dirp;
            }
         else
            {
            *lsp = *dolp;
            *rsp = *dorp;
            }

         if (twodblimit)
            {
            *lsp *= 0.7943;
            *rsp *= 0.7943;
            }

         if (stream_monitor == FALSE)
            {
            *lap = ((*lplcp * lp_lc_aud) + (*rplcp * rp_lc_aud) + (*jplcp * jp_lc_aud)) * df + d_micmix + (*iplcp * ip_lc_aud) + (ip_lc_fade * ip_lc_aud) +
            (lp_lc_fade * lp_lc_audf) + (rp_lc_fade * rp_lc_audf) + (jp_lc_fade * jp_lc_audf);
            *rap = ((*lprcp * lp_rc_aud) + (*rprcp * rp_rc_aud) + (*jprcp * jp_rc_aud)) * df + d_micmix + (*iprcp * ip_rc_aud) + (ip_rc_fade * ip_rc_aud) +
            (lp_rc_fade * lp_rc_audf) + (rp_rc_fade * rp_rc_audf) + (jp_rc_fade * jp_rc_audf);
            compressor_gain = db2level(limiter(&audio_limiter, *lap, *rap));
            *lap *= compressor_gain;
            *rap *= compressor_gain;
            }
         else
            {
            *lap = *lsp;  /* allow the DJ to hear the mix that the listeners are hearing */
            *rap = *rsp;
            }
            
         if (eot_alarm_f)       /* mix in the end-of-track alarm tone */
            {
            if (alarm_index >= alarm_size)
               {
               alarm_index = 0;
               eot_alarm_f = 0;
               }
            else
               {
               *lap += eot_alarm_table[alarm_index];
               *lap *= 0.5;
               *rap += eot_alarm_table[alarm_index];
               *rap *= 0.5;
               alarm_index++;
               }
            }
                 
         *lap *= dj_audio_gain;
         *rap *= dj_audio_gain;  
                 
         /* make note of the peak volume levels */
         peakfilter_process(str_pf_l, *lsp);
         peakfilter_process(str_pf_r, *rsp);

         /* a running total of sound pressure levels used for rms calculation */
         str_l_tally += *lsp * *lsp;
         str_r_tally += *rsp * *rsp;
         rms_tally_count++;     /* the divisor for the above running counts */
         /* beat analysis */
         /*beat_add(beat_lp, *lplcp * *lplcp, *lprcp * *lprcp);
         beat_add(beat_rp, *rplcp * *rplcp, *rprcp * *rprcp);*/
         }
      str_l_meansqrd = str_l_tally/rms_tally_count;
      str_r_meansqrd = str_r_tally/rms_tally_count;
      }
   else
      if (simple_mixer == FALSE && mixermode == PHONE_PUBLIC)
         {
         for(samples_todo = nframes; samples_todo--; lap++, rap++, lsp++, rsp++, lxp++, rxp++,
                mp_1++, mp_2++, mp_3++, mp_4++,
                lplcp++, lprcp++, rplcp++, rprcp++, jplcp++, jprcp++,
                lpsp++, rpsp++, lprp++, rprp++, iplcp++, iprcp++, dilp++, dirp++, dolp++, dorp++)
            {    
            if (vol_smooth_count++ % 100 == 0) /* Can change volume level every so many samples */
               update_smoothed_volumes();
            mic_process(mic_1, *mp_1);
            mic_process(mic_2, *mp_2);
            mic_process(mic_3, *mp_3);
            mic_process(mic_4, *mp_4);
            /* All microphones to be soft unmuted by the user interface
             * no muting of the dj mix to ensure a full conference takes place.
             */
            lc_s_micmix = mic_1->lcm + mic_2->lcm + mic_3->lcm + mic_4->lcm;
            rc_s_micmix = mic_1->rcm + mic_2->rcm + mic_3->rcm + mic_4->rcm;
            d_micmix = mic_1->unpm + mic_2->unpm + mic_3->unpm + mic_4->unpm;

            /* No ducking */
            df = 1.0;
            
            if (plr_l->fadeindex < FB_SIZE)
               {
               lp_lc_fade = fade_table[plr_l->fadeindex] * *lplcpf++; 
               lp_rc_fade = fade_table[plr_l->fadeindex] * *lprcpf++;
               plr_l->fadeindex += plr_l->fadeoutstep;
               }
            else
               lp_lc_fade = lp_rc_fade = 0.0;
               
            if (plr_r->fadeindex < FB_SIZE)
               {
               rp_lc_fade = fade_table[plr_r->fadeindex] * *rplcpf++; 
               rp_rc_fade = fade_table[plr_r->fadeindex] * *rprcpf++;
               plr_r->fadeindex += plr_r->fadeoutstep;
               }
            else
               rp_lc_fade = rp_rc_fade = 0.0;
            
            if (plr_j->fadeindex < FB_SIZE)
               {
               jp_lc_fade = fade_table[plr_j->fadeindex] * *jplcpf++; 
               jp_rc_fade = fade_table[plr_j->fadeindex] * *jprcpf++;
               plr_j->fadeindex += plr_j->fadeoutstep;
               }
            else
               jp_lc_fade = jp_rc_fade = 0.0;
               
            if (plr_i->fadeindex < FB_SIZE)
               {
               ip_lc_fade = fade_table[plr_i->fadeindex] * *iplcpf++; 
               ip_rc_fade = fade_table[plr_i->fadeindex] * *iprcpf++;
               plr_i->fadeindex += plr_i->fadeoutstep;
               }
            else
               ip_lc_fade = ip_rc_fade = 0.0;
            
            /* do the phone send mix */
            *lpsp = lc_s_micmix + (*jplcp * jp_lc_str) + (jp_lc_fade * jp_lc_strf);
            *rpsp = rc_s_micmix + (*jprcp * jp_rc_str) + (jp_rc_fade * jp_rc_strf);
            
            if (aux_flux)
               update_mic_and_aux();            /* smooth mic rise and fall mute/unmute */

            if (fabs(*lplcp) > left_peak)               /* peak levels used for song cut-off */
               left_peak = fabs(*lplcp);
            if (fabs(*lprcp) > left_peak)
               left_peak = fabs(*lprcp);
            if (fabs(*rplcp) > right_peak)
               right_peak = fabs(*rplcp);
            if (fabs(*rprcp) > right_peak)
               right_peak = fabs(*rprcp);

            /* The main mix */
            *dolp = ((*lplcp * lp_lc_str) + (*rplcp * rp_lc_str) + (*lxp * aux_lc)) + *lprp + *lpsp +
            (lp_lc_fade * lp_rc_strf) + (rp_lc_fade * rp_lc_strf) + (*iplcp * ip_lc_str) + (ip_lc_fade * ip_lc_strf);
            *dorp = ((*lprcp * lp_rc_str) + (*rprcp * rp_rc_str) + (*rxp * aux_rc)) + *rprp + *rpsp +
            (lp_rc_fade * lp_rc_strf) + (rp_rc_fade * rp_rc_strf) + (*iprcp * ip_rc_str) + (ip_rc_fade * ip_rc_strf);
            
            compressor_gain = db2level(limiter(&phone_limiter, *lpsp, *rpsp));
            *lpsp *= compressor_gain;
            *rpsp *= compressor_gain;

            /* apply normalization at the stream level */
            str_normalizer_gain = db2level(normalizer(&str_normalizer, *dolp, *dorp));
            
            *dolp *= str_normalizer_gain;
            *dorp *= str_normalizer_gain;
            
            /* hard limit the levels if they go outside permitted limits */
            /* note this is not the same as clipping */
            compressor_gain = db2level(limiter(&stream_limiter, *dolp, *dorp));
   
            *dolp *= compressor_gain;
            *dorp *= compressor_gain;

            if (using_dsp)
               {
               *lsp = *dilp;
               *rsp = *dirp;
               }
            else
               {
               *lsp = *dolp;
               *rsp = *dorp;
               }

            if (twodblimit)
               {
               *lsp *= 0.7943;
               *rsp *= 0.7943;
               }

            if (stream_monitor == FALSE)
               {
               *lap = ((*lplcp * lp_lc_aud) + (*rplcp * rp_lc_aud)) + *lprp +
               (lp_lc_fade * lp_rc_audf) + (rp_lc_fade * rp_lc_audf) + (*iplcp * ip_lc_aud) + (ip_lc_fade * ip_lc_audf) + d_micmix + (*jplcp * jp_lc_str) + (jp_lc_fade * jp_lc_strf);
               *rap = ((*lprcp * lp_rc_aud) + (*rprcp * rp_rc_aud)) + *rprp +
               (lp_rc_fade * lp_rc_audf) + (rp_rc_fade * rp_rc_audf) + (*iprcp * ip_rc_aud) + (ip_rc_fade * ip_rc_audf) + d_micmix + (*jprcp * jp_rc_str) + (jp_rc_fade * jp_rc_strf);
               compressor_gain = db2level(limiter(&audio_limiter, *lap, *rap));
               *lap *= compressor_gain;
               *rap *= compressor_gain;
               }
            else
               {
               *lap = *lsp;  /* allow the DJ to hear the mix that the listeners are hearing */
               *rap = *rsp;
               }
               
            if (eot_alarm_f)    /* mix in the end-of-track alarm tone */
               {
               if (alarm_index >= alarm_size)
                  {
                  alarm_index = 0;
                  eot_alarm_f = 0;
                  }
               else
                  {
                  *lap += eot_alarm_table[alarm_index];
                  *lap *= 0.5;
                  *rap += eot_alarm_table[alarm_index];
                  *rap *= 0.5;
                  alarm_index++;
                  }
               }
                  
            *lap *= dj_audio_gain;
            *rap *= dj_audio_gain;       
                  
            /* make note of the peak volume levels */
            peakfilter_process(str_pf_l, *lsp);
            peakfilter_process(str_pf_r, *rsp);
            
            /* a running total of sound pressure levels used for rms calculation */
            str_l_tally += *lsp * *lsp;
            str_r_tally += *rsp * *rsp;
            rms_tally_count++;  /* the divisor for the above running counts */
            }
         str_l_meansqrd = str_l_tally/rms_tally_count;
         str_r_meansqrd = str_r_tally/rms_tally_count;
         }
      else
         if (simple_mixer == FALSE && mixermode == PHONE_PRIVATE && mic_on == 0)
            {
            for(samples_todo = nframes; samples_todo--; lap++, rap++, lsp++, rsp++, lxp++, rxp++,
            mp_1++, mp_2++, mp_3++, mp_4++,
            lplcp++, lprcp++, rplcp++, rprcp++, jplcp++, jprcp++, lpsp++, rpsp++, 
            lprp++, rprp++, iplcp++, iprcp++, dilp++, dirp++, dolp++, dorp++)
               {         
               if (vol_smooth_count++ % 100 == 0) /* Can change volume level every so many samples */
                  update_smoothed_volumes();

               mic_process(mic_1, *mp_1);
               mic_process(mic_2, *mp_2);
               mic_process(mic_3, *mp_3);
               mic_process(mic_4, *mp_4);
               /* no muting of the dj mix to ensure a full conference takes place */
               lc_s_micmix = mic_1->lc + mic_2->lc + mic_3->lc + mic_4->lc;
               rc_s_micmix = mic_1->rc + mic_2->rc + mic_3->rc + mic_4->rc;
               d_micmix = mic_1->unpm + mic_2->unpm + mic_3->unpm + mic_4->unpm;
               
               /* No ducking */
               df = 1.0;
               
               if (plr_l->fadeindex < FB_SIZE)
                  {
                  lp_lc_fade = fade_table[plr_l->fadeindex] * *lplcpf++; 
                  lp_rc_fade = fade_table[plr_l->fadeindex] * *lprcpf++;
                  plr_l->fadeindex += plr_l->fadeoutstep;
                  }
               else
                  lp_lc_fade = lp_rc_fade = 0.0;
                  
               if (plr_r->fadeindex < FB_SIZE)
                  {
                  rp_lc_fade = fade_table[plr_r->fadeindex] * *rplcpf++; 
                  rp_rc_fade = fade_table[plr_r->fadeindex] * *rprcpf++;
                  plr_r->fadeindex += plr_r->fadeoutstep;
                  }
               else
                  rp_lc_fade = rp_rc_fade = 0.0;
               
               if (plr_j->fadeindex < FB_SIZE)
                  {
                  jp_lc_fade = fade_table[plr_j->fadeindex] * *jplcpf++; 
                  jp_rc_fade = fade_table[plr_j->fadeindex] * *jprcpf++;
                  plr_j->fadeindex += plr_j->fadeoutstep;
                  }
               else
                  jp_lc_fade = jp_rc_fade = 0.0;
                  
               if (plr_i->fadeindex < FB_SIZE)
                  {
                  ip_lc_fade = fade_table[plr_i->fadeindex] * *iplcpf++; 
                  ip_rc_fade = fade_table[plr_i->fadeindex] * *iprcpf++;
                  plr_i->fadeindex += plr_i->fadeoutstep;
                  }
               else
                  ip_lc_fade = ip_rc_fade = 0.0;

               if (aux_flux)
                  update_mic_and_aux();         /* smooth mic rise and fall mute/unmute */
               
               if (fabs(*lplcp) > left_peak)            /* peak levels used for song cut-off */
                  left_peak = fabs(*lplcp);
               if (fabs(*lprcp) > left_peak)
                  left_peak = fabs(*lprcp);
               if (fabs(*rplcp) > right_peak)
                  right_peak = fabs(*rplcp);
               if (fabs(*rprcp) > right_peak)
                  right_peak = fabs(*rprcp);
               
               /* This is it folks, the main mix */
               *dolp = (*lplcp * lp_lc_str) + (*rplcp * rp_lc_str) + (*lxp * aux_lc) +
               (lp_lc_fade * lp_rc_strf) + (rp_lc_fade * rp_lc_strf) + (*iplcp * ip_lc_str) + (ip_lc_fade * ip_lc_strf);
               *dorp = (*lprcp * lp_rc_str) + (*rprcp * rp_rc_str) + (*rxp * aux_rc) +
               (lp_rc_fade * lp_rc_strf) + (rp_rc_fade * rp_rc_strf) + (*iprcp * ip_rc_str) + (ip_rc_fade * ip_rc_strf);
               
               /* apply normalization at the stream level */
               str_normalizer_gain = db2level(normalizer(&str_normalizer, *dolp, *dorp));
               
               *dolp *= str_normalizer_gain;
               *dorp *= str_normalizer_gain;
               
               /* hard limit the levels if they go outside permitted limits */
               /* note this is not the same as clipping */
               compressor_gain = db2level(limiter(&stream_limiter, *dolp, *dorp));
      
               *dolp *= compressor_gain;
               *dorp *= compressor_gain;
               
               /* The mix the voip listeners receive */
               *lpsp = (*dolp * mb_lc_aud) + (*jplcp * jp_lc_aud) + lc_s_micmix + 
               (jp_lc_fade * jp_lc_strf);
               *rpsp = (*dorp * mb_lc_aud) + (*jprcp * jp_rc_aud) + rc_s_micmix +
               (jp_rc_fade * jp_rc_strf);
               compressor_gain = db2level(limiter(&phone_limiter, *lpsp, *rpsp));
               *lpsp *= compressor_gain;
               *rpsp *= compressor_gain;
               
               if (using_dsp)
                  {
                  *lsp = *dilp;
                  *rsp = *dirp;
                  }
               else
                  {
                  *lsp = *dolp;
                  *rsp = *dorp;
                  }

               if (twodblimit)
                  {
                  *lsp *= 0.7943;
                  *rsp *= 0.7943;
                  }

               if (stream_monitor == FALSE) /* the DJ can hear the VOIP phone call */
                  {
                  *lap = (*lsp * mb_lc_aud) + (*jplcp * jp_lc_aud) + d_micmix + (jp_lc_fade * jp_lc_strf) + *lprp;
                  *rap = (*rsp * mb_lc_aud) + (*jprcp * jp_rc_aud) + d_micmix + (jp_rc_fade * jp_rc_strf) + *rprp;
                  compressor_gain = db2level(limiter(&audio_limiter, *lap, *rap));
                  *lap *= compressor_gain;
                  *rap *= compressor_gain;
                  }
               else
                  {
                  *lap = *lsp;  /* allow the DJ to hear the mix that the listeners are hearing */
                  *rap = *rsp;
                  }
                  
               if (eot_alarm_f) /* mix in the end-of-track alarm tone */
                  {
                  if (alarm_index >= alarm_size)
                     {
                     alarm_index = 0;
                     eot_alarm_f = 0;
                     }
                  else
                     {
                     *lap += eot_alarm_table[alarm_index];
                     *lap *= 0.5;
                     *rap += eot_alarm_table[alarm_index];
                     *rap *= 0.5;
                     alarm_index++;
                     }
                  }
                     
               *lap *= dj_audio_gain;
               *rap *= dj_audio_gain;    
                     
               /* make note of the peak volume levels */
               peakfilter_process(str_pf_l, *lsp);
               peakfilter_process(str_pf_r, *rsp);
               
               /* a running total of sound pressure levels used for rms calculation */
               str_l_tally += *lsp * *lsp;
               str_r_tally += *rsp * *rsp;
               rms_tally_count++;       /* the divisor for the above running counts */
               }
            str_l_meansqrd = str_l_tally/rms_tally_count;
            str_r_meansqrd = str_r_tally/rms_tally_count;
            }
         else
            if (simple_mixer == FALSE && mixermode == PHONE_PRIVATE) /* note: mic is on */
               {
               for(samples_todo = nframes; samples_todo--; lap++, rap++, lsp++, rsp++, lxp++, rxp++,
                     mp_1++, mp_2++, mp_3++, mp_4++,
                     lplcp++, lprcp++, rplcp++, rprcp++, jplcp++, jprcp++, lpsp++, rpsp++,
                        iplcp++, iprcp++, dilp++, dirp++, dolp++, dorp++)
                  {
                  if (vol_smooth_count++ % 100 == 0) /* Can change volume level every so many samples */
                     update_smoothed_volumes();
                  mic_process(mic_1, *mp_1);
                  mic_process(mic_2, *mp_2);
                  mic_process(mic_3, *mp_3);
                  mic_process(mic_4, *mp_4);
                  lc_s_micmix = mic_1->lcm + mic_2->lcm + mic_3->lcm + mic_4->lcm;
                  rc_s_micmix = mic_1->rcm + mic_2->rcm + mic_3->rcm + mic_4->rcm;
                  d_micmix = mic_1->unpmdj + mic_2->unpmdj + mic_3->unpmdj + mic_4->unpmdj;
                
                  /* ducking calculation - disabled mics have df of 1.0 always */
                  {
                      float df1 = mic_1->agc->df;
                      float df2 = mic_2->agc->df;
                      float df3 = mic_3->agc->df;
                      float df4 = mic_4->agc->df;
                      float hr = db2level(current_headroom);
                      
                      float w1 = (df1 < df2) ? df1 : df2;
                      float w2 = (df3 < df4) ? df3 : df4;
                      df = ((w1 < w2) ? w1 : w2) * dfmod;
                      df = (df < hr) ? df : hr;
                  }
                     
                  if (plr_l->fadeindex < FB_SIZE)
                     {
                     lp_lc_fade = fade_table[plr_l->fadeindex] * *lplcpf++; 
                     lp_rc_fade = fade_table[plr_l->fadeindex] * *lprcpf++;
                     plr_l->fadeindex += plr_l->fadeoutstep;
                     }
                  else
                     lp_lc_fade = lp_rc_fade = 0.0;
                     
                  if (plr_r->fadeindex < FB_SIZE)
                     {
                     rp_lc_fade = fade_table[plr_r->fadeindex] * *rplcpf++; 
                     rp_rc_fade = fade_table[plr_r->fadeindex] * *rprcpf++;
                     plr_r->fadeindex += plr_r->fadeoutstep;
                     }
                  else
                     rp_lc_fade = rp_rc_fade = 0.0;
                  
                  if (plr_j->fadeindex < FB_SIZE)
                     {
                     jp_lc_fade = fade_table[plr_j->fadeindex] * *jplcpf++; 
                     jp_rc_fade = fade_table[plr_j->fadeindex] * *jprcpf++;
                     plr_j->fadeindex += plr_j->fadeoutstep;
                     }
                  else
                     jp_lc_fade = jp_rc_fade = 0.0;
                     
                  if (plr_i->fadeindex < FB_SIZE)
                     {
                     ip_lc_fade = fade_table[plr_i->fadeindex] * *iplcpf++; 
                     ip_rc_fade = fade_table[plr_i->fadeindex] * *iprcpf++;
                     plr_i->fadeindex += plr_i->fadeoutstep;
                     }
                  else
                     ip_lc_fade = ip_rc_fade = 0.0;

                  if (aux_flux)
                     update_mic_and_aux();      /* smooth mic rise and fall mute/unmute */

                  if (fabs(*lplcp) > left_peak)         /* peak levels used for song cut-off */
                     left_peak = fabs(*lplcp);
                  if (fabs(*lprcp) > left_peak)
                     left_peak = fabs(*lprcp);
                  if (fabs(*rplcp) > right_peak)
                     right_peak = fabs(*rplcp);
                  if (fabs(*rprcp) > right_peak)
                     right_peak = fabs(*rprcp);

                  /* This is it folks, the main mix */
                  *dolp = ((*lplcp * lp_lc_str) + (*rplcp * rp_lc_str) + (*lxp * aux_lc) + (*jplcp * jp_lc_str)) * df + lc_s_micmix + (*iplcp * ip_lc_str) + (ip_lc_fade * ip_lc_strf) +
                  (lp_lc_fade * lp_lc_strf) + (rp_lc_fade * rp_lc_strf) + (jp_lc_fade * jp_lc_strf);
                  *dorp = ((*lprcp * lp_rc_str) + (*rprcp * rp_rc_str) + (*rxp * aux_rc) + (*jprcp * jp_rc_str)) * df + rc_s_micmix + (*iprcp * ip_rc_str) + (ip_rc_fade * ip_rc_strf) +
                  (lp_rc_fade * lp_rc_strf) + (rp_rc_fade * rp_rc_strf) + (jp_rc_fade * jp_rc_strf);
                  
                  /* apply normalization at the stream level */
                  str_normalizer_gain = db2level(normalizer(&str_normalizer, *dolp, *dorp));
                  
                  *dolp *= str_normalizer_gain;
                  *dorp *= str_normalizer_gain;
                  
                  /* hard limit the levels if they go outside permitted limits */
                  /* note this is not the same as clipping */
                  compressor_gain = db2level(limiter(&stream_limiter, *dolp, *dorp));
         
                  *dolp *= compressor_gain;
                  *dorp *= compressor_gain;
                  
                  *lpsp = *dolp * mb_lc_aud;    /* voip callers get stream mix at a certain volume */ 
                  *rpsp = *dorp * mb_rc_aud;

                  if (using_dsp)
                     {
                     *lsp = *dilp;
                     *rsp = *dirp;
                     }
                  else
                     {
                     *lsp = *dolp;
                     *rsp = *dorp;
                     }

                  if (twodblimit)
                     {
                     *lsp *= 0.7943;
                     *rsp *= 0.7943;
                     }

                  if (stream_monitor == FALSE)
                     {
                     *lap = ((*lplcp * lp_lc_aud) + (*rplcp * rp_lc_aud) + (*jplcp * jp_lc_aud)) * df + d_micmix + (*iplcp * ip_lc_aud) + (ip_lc_fade * ip_lc_audf) +
                     (lp_lc_fade * lp_lc_audf) + (rp_lc_fade * rp_lc_audf) + (jp_lc_fade * jp_lc_audf);
                     *rap = ((*lprcp * lp_rc_aud) + (*rprcp * rp_rc_aud) + (*jprcp * jp_rc_aud)) * df + d_micmix + (*iprcp * ip_rc_aud) + (ip_rc_fade * ip_rc_audf) +
                     (lp_rc_fade * lp_rc_audf) + (rp_rc_fade * rp_rc_audf) + (jp_rc_fade * jp_rc_audf);
                     compressor_gain = db2level(limiter(&audio_limiter, *lap, *rap));
                     *lap *= compressor_gain;
                     *rap *= compressor_gain;
                     }
                  else
                     {
                     *lap = *lsp;  /* allow the DJ to hear the mix that the listeners are hearing */
                     *rap = *rsp;
                     }
                     
                  if (eot_alarm_f)      /* mix in the end-of-track alarm tone */
                     {
                     if (alarm_index >= alarm_size)
                        {
                        alarm_index = 0;
                        eot_alarm_f = 0;
                        }
                     else
                        {
                        *lap += eot_alarm_table[alarm_index];
                        *lap *= 0.5;
                        *rap += eot_alarm_table[alarm_index];
                        *rap *= 0.5;
                        alarm_index++;
                        }
                     }
                        
                  *lap *= dj_audio_gain;
                  *rap *= dj_audio_gain;         
                        
                  /* make note of the peak volume levels */
                  peakfilter_process(str_pf_l, *lsp);
                  peakfilter_process(str_pf_r, *rsp);
                  
                  /* a running total of sound pressure levels used for rms calculation */
                  str_l_tally += *lsp * *lsp;
                  str_r_tally += *rsp * *rsp;
                  rms_tally_count++;    /* the divisor for the above running counts */
                  }
               str_l_meansqrd = str_l_tally/rms_tally_count;
               str_r_meansqrd = str_r_tally/rms_tally_count;
               }
            else
               if (simple_mixer == TRUE)
                  {
                  if (left_audio)
                     {
                     if (dj_audio_level != current_dj_audio_level)
                        {
                        current_dj_audio_level = dj_audio_level;
                        dj_audio_gain = db2level(dj_audio_level);
                        }
                     samples_todo = nframes;
                     while(samples_todo--)
                        {
                        *lap++ = *lplcp++ * dj_audio_gain;
                        *rap++ = *lprcp++ * dj_audio_gain;
                        }
                     }
                  else
                     {
                     memset(la_buffer, 0, nframes * sizeof (sample_t));
                     memset(ra_buffer, 0, nframes * sizeof (sample_t));
                     }
                  if (left_stream)
                     {
                     memcpy(ls_buffer, lp_lc, nframes * sizeof (sample_t));
                     memcpy(rs_buffer, lp_rc, nframes * sizeof (sample_t));
                     }
                  else
                     {
                     memset(ls_buffer, 0, nframes * sizeof (sample_t));
                     memset(rs_buffer, 0, nframes * sizeof (sample_t));
                     }
                  }
               else
                  fprintf(stderr,"Error: no mixer mode was chosen\n");
   }
 
int process (jack_nframes_t nframes, void *arg)
   {
   if(transport_aware)
      {
      jack_position_t pos;
      
      if(jack_transport_query(client, &pos) != JackTransportRolling)
         {
         process_silence(nframes);
         return 0;
         }
      }
   process_audio(nframes);
   return 0;
   }
   
int peak_to_log(float peak)
   {
   if (peak <= 0.0)
      return -127;
   if (peak >= 1.0)
      return 0;
   return (int)level2db(peak);
   }
   
void interrupt_handler(int data)        /* eats the first ^C */
   {
   static int count = 0;
   
   /* each thread running will call this handler so the number */
   /* needs to be high if we mean to exit in an orderly fashion */
   if (count++ > 7)
      {
      fprintf(stderr, "Mixer exiting due to ^C interrupt.\n");      
      exit(130);
      }
   else
      {
      if (count == 1)
         fprintf(stderr, "Mixer got ^C interrupt.\n");
      /* ignore this interrupt and wait instead for idjc to clean exit */
      //sigdelset(&mixersigset, SIGINT);
      }
   }

void segfault_handler(int data)
   {
   printf("Segmentation Fault\n");
   fflush(stdout);
   exit(5);
   }

void jack_shutdown_handler(void *data)
   {
   jack_closed_f = TRUE;
   }

void alarm_handler(int data)
   {
   struct xlplayer *cause;
   
   if ((cause = plr_l)->watchdog_timer++ == 9 ||
       (cause = plr_r)->watchdog_timer++ == 9 ||
       (cause = plr_i)->watchdog_timer++ == 9 ||
       (cause = plr_j)->watchdog_timer++ == 9) 
      {
      if (cause->playmode == PM_INITIATE)
         {
         cause->initial_audio_context = cause->current_audio_context;
         cause->playmode = PM_STOPPED;
         cause->command = CMD_COMPLETE;
         }
      fprintf(stderr, "watchdog timer frozen for one of the media players -- possible bad media file\nshutting down the mixer in one second\n");
      signal(SIGALRM, segfault_handler);
      }
   alarm(1);
   }

void atexit_handler()
   {
   if (client)
      jack_client_close(client);
   }

void send_metadata_update(struct xlp_dynamic_metadata *dm)
   {
   pthread_mutex_lock(&(dm->meta_mutex));
   fprintf(stderr, "new dynamic metadata\n");
   if (dm->data_type != DM_JOINED_UC)
      {
      fprintf(stdout, "new_metadata=d%d:%sd%d:%sd%d:%sd9:%09dd9:%09dx\n", (int)strlen(dm->artist), dm->artist, (int)strlen(dm->title), dm->title, (int)strlen(dm->artist_title), dm->artist_title, dm->current_audio_context, dm->rbdelay);
      }
   else
      {
      fprintf(stderr, "send_metadata_update: utf16 chapter info not supported\n");
      }
   dm->data_type = DM_NONE_NEW;
   pthread_mutex_unlock(&(dm->meta_mutex));
   }

void display_error_to_stderr(const char *message)
   {
   fprintf(stderr, "JACK ERROR MESSAGE: %s\n", message);
   }

void display_info_to_stderr(const char *message)
   {
   fprintf(stderr, "JACK INFO MESSAGE: %s\n", message);
   }

static void jack_free_ports(const char **p)
   {
   if (p)
      free(p);
   }
   
int main(int argc, char **argv)
   {
   FILE *fp =stdin;
   const char **inport;
   const char **outport;
   int str_l_peak_db, str_r_peak_db;
   int str_l_rms_db, str_r_rms_db;
   float normrise, normfall;
   int fadeout_f;
   int flush_left, flush_right, flush_jingles, flush_interlude;
   int i, new_left_pause, new_right_pause;
   static int old_aux_on = 0;
   jack_nframes_t nframes;
   char *artist = NULL, *title = NULL, *replaygain = NULL;
   double length;
   int sync = FALSE;
   int use_dsp;
   jack_status_t status;
   char *server_name = getenv("IDJC_JACK_SERVER");
   char midi_output[MIDI_QUEUE_SIZE];

   setenv("LC_ALL", "C", 1);            /* ensure proper sscanf operation */

   signal(SIGINT, interrupt_handler);
   signal(SIGALRM, alarm_handler); 
   signal(SIGSEGV, segfault_handler);

   atexit(atexit_handler);

#ifdef DYN_MAD
   have_mad = dyn_mad_init();
#else
   have_mad = 1;
#endif /* DYN_MAD */

   if((client = jack_client_open("idjc-mx", JackUseExactName | JackServerName, &status, server_name)) == 0)
      {
      printf("IDJC: Error\n");
      fflush(stdout);
      return 1;
      }
      
   jack_set_process_callback(client, process, NULL);
      
   jack_set_error_function(display_error_to_stderr);
   jack_set_info_function(display_info_to_stderr);
      
   /* create the jack ports by which sound is communicated through the jack system */
   /* this one normally connects to the sound card output */
   audio_left_port = jack_port_register(client, "dj_out_l", JACK_DEFAULT_AUDIO_TYPE, 
                                        JackPortIsOutput, 0);
   audio_right_port = jack_port_register(client, "dj_out_r", JACK_DEFAULT_AUDIO_TYPE, 
                                        JackPortIsOutput, 0);
   dspout_left_port = jack_port_register(client, "dsp_out_l", JACK_DEFAULT_AUDIO_TYPE, 
                                        JackPortIsOutput, 0);
   dspout_right_port = jack_port_register(client, "dsp_out_r", JACK_DEFAULT_AUDIO_TYPE, 
                                        JackPortIsOutput, 0);
   dspin_left_port = jack_port_register(client, "dsp_in_l", JACK_DEFAULT_AUDIO_TYPE, 
                                        JackPortIsInput, 0);
   dspin_right_port = jack_port_register(client, "dsp_in_r", JACK_DEFAULT_AUDIO_TYPE, 
                                        JackPortIsInput, 0);
   /* this one connects to the server module which in turn streams to the internet */
   stream_left_port = jack_port_register(client, "str_out_l", JACK_DEFAULT_AUDIO_TYPE, 
                                        JackPortIsOutput, 0);
   stream_right_port = jack_port_register(client, "str_out_r", JACK_DEFAULT_AUDIO_TYPE, 
                                        JackPortIsOutput, 0);
   /* connects to the capture port normally, which can be set to things other than just mic */
   mic_channel_1 = jack_port_register(client, "mic_in_1", JACK_DEFAULT_AUDIO_TYPE,
                                        JackPortIsInput, 0);
   mic_channel_2 = jack_port_register(client, "mic_in_2", JACK_DEFAULT_AUDIO_TYPE,
                                        JackPortIsInput, 0);
   mic_channel_3 = jack_port_register(client, "mic_in_3", JACK_DEFAULT_AUDIO_TYPE,
                                        JackPortIsInput, 0);
   mic_channel_4 = jack_port_register(client, "mic_in_4", JACK_DEFAULT_AUDIO_TYPE,
                                        JackPortIsInput, 0);
   /* intended as a spare for connection to almost any jack app you like */
   aux_left_channel = jack_port_register(client, "aux_in_l", JACK_DEFAULT_AUDIO_TYPE,
                                        JackPortIsInput, 0);
   aux_right_channel = jack_port_register(client, "aux_in_r", JACK_DEFAULT_AUDIO_TYPE,
                                        JackPortIsInput, 0);
   /* inteneded for connection to a VOIP application */
   phone_left_send = jack_port_register(client, "voip_out_l", JACK_DEFAULT_AUDIO_TYPE,
                                        JackPortIsOutput, 0);
   phone_right_send = jack_port_register(client, "voip_out_r", JACK_DEFAULT_AUDIO_TYPE,
                                        JackPortIsOutput, 0);
   phone_left_recv = jack_port_register(client, "voip_in_l", JACK_DEFAULT_AUDIO_TYPE,
                                        JackPortIsInput, 0);
   phone_right_recv = jack_port_register(client, "voip_in_r", JACK_DEFAULT_AUDIO_TYPE,
                                        JackPortIsInput, 0);

   /* midi_control */
   midi_port = jack_port_register(client, "midi_control", JACK_DEFAULT_MIDI_TYPE, JackPortIsInput, 0);

   sr = jack_get_sample_rate(client);
   fb_size = FB_SIZE;
   jingles_samples_cutoff = sr / 12;            /* A twelfth of a second early */
   player_samples_cutoff = sr * 0.25;           /* for gapless playback */

   if(! ((plr_l = xlplayer_create(sr, RB_SIZE, "leftplayer", &jack_closed_f)) &&
         (plr_r = xlplayer_create(sr, RB_SIZE, "rightplayer", &jack_closed_f))))
      {
      printf("failed to create main player modules\n");
      return 1;
      }
   
   if (!(plr_j = xlplayer_create(sr, RB_SIZE, "jinglesplayer", &jack_closed_f)))
      {
      printf("failed to create jingles player module\n");
      return 1;
      }

   if (!(plr_i = xlplayer_create(sr, RB_SIZE, "interludeplayer", &jack_closed_f)))
      {
      printf("failed to create interlude player module\n");
      return 1;
      }

   if (!init_dblookup_table())
      {
      fprintf(stderr, "Failed to allocate space for signal to db lookup table\n");
      exit(5);
      }
      
   if (!init_signallookup_table())
      {
      fprintf(stderr, "Failed to allocate space for db to signal lookup table\n");
      exit(5);
      } 
      
   /* generate the wave table for the DJ alarm */
   if (!(eot_alarm_table = calloc(sizeof (sample_t), sr)))
      {
      fprintf(stderr, "Failed to allocate space for end of track alarm wave table\n");
      exit(5);
      }
   else
      {
      alarm_size = (sr / 900) * 900;    /* builds the alarm tone wave table */
      for (i = 0; i < alarm_size ; i++) /* note it has a nice 2nd harmonic added */
         {
         eot_alarm_table[i] = 0.83F * sinf((i % (sr/900)) * 6.283185307F / (sr/900));
         eot_alarm_table[i] += 0.024F * sinf((i % (sr/900)) * 12.56637061F / (sr/900) + 3.141592654F / 4.0F);
         }
      }
         
   /* computes the decay curve for track fadeouts */
   if (!(fade_table = malloc(FB_SIZE * sizeof(float))))
      {
      fprintf(stderr, "Failed to allocate space for fade table\n");
      exit(5);
      }
   else
      {
      plr_l->fadeindex = FB_SIZE;
      plr_r->fadeindex = FB_SIZE;
      plr_j->fadeindex = FB_SIZE;
      plr_i->fadeindex = FB_SIZE;
      for (i = 0; i < FB_SIZE; i++)
         {
         fade_table[i] = pow10f(i / -20000.0 * 44100.0 / FB_SIZE);
         /*fade_table[i] = powf(fade_table[i], 0.1f);*/
         }
      }

   str_pf_l = peakfilter_create(115e-6f, sr);
   str_pf_r = peakfilter_create(115e-6f, sr);

   mic_1 = mic_init(sr);
   mic_2 = mic_init(sr);
   mic_3 = mic_init(sr);
   mic_4 = mic_init(sr);
   
   if (!(mic_1 && mic_2 && mic_3 && mic_4))
      {
      fprintf(stderr, "mic_init failed\n");
      exit(5);
      }   
         
   nframes = jack_get_sample_rate (client);
   lp_lc = ialloc(nframes);
   lp_rc = ialloc(nframes);
   rp_lc = ialloc(nframes);
   rp_rc = ialloc(nframes);
   jp_lc = ialloc(nframes);
   jp_rc = ialloc(nframes);
   ip_lc = ialloc(nframes);
   ip_rc = ialloc(nframes);
   lp_lcf = ialloc(nframes);
   lp_rcf = ialloc(nframes);
   rp_lcf = ialloc(nframes);
   rp_rcf = ialloc(nframes);
   jp_lcf = ialloc(nframes);
   jp_rcf = ialloc(nframes);
   ip_lcf = ialloc(nframes);
   ip_rcf = ialloc(nframes);

   if (!(lp_lc && lp_rc && rp_lc && rp_rc && jp_lc && jp_rc && ip_lc && ip_rc &&
       lp_lcf && lp_rcf && rp_lcf && rp_rcf && jp_lcf && jp_rcf && ip_lcf && ip_rcf))
      {
      fprintf(stderr, "Failed to allocate read-buffers for player_reader reading\n");
      exit(5);
      }
         
#if 0
   beat_lp = beat_init(sr, 2.4, 48);    /* initialise beat analysis engine */
   beat_rp = beat_init(sr, 2.4, 48);
#endif

   jack_on_shutdown(client, jack_shutdown_handler, NULL);

   if (jack_activate(client))
      {
      fprintf(stderr, "Failed to activate client\n");
      return 1;
      }
   
   /* report the sample rate back to the main app where it is used to calibrate mplayer */
   /* the main app waits on this signal in order to prevent a race with the server code */
   fprintf(stdout, "IDJC: Sample rate %d\n", (int)sr);
   fflush(stdout);
 
                /* Scan for physical audio IO ports to use as defaults */
   inport = jack_get_ports(client, NULL, NULL, JackPortIsPhysical | JackPortIsOutput);
   outport = jack_get_ports(client, NULL, NULL, JackPortIsPhysical | JackPortIsInput);
 
   /* Make voip input audio available on the voip output so you can hear your own voice */
   /* and hear jingles and mixed back audio too */
   /* If the voip app provides this you can break the connection automatically */
   /* using the events feature in idjc prefs and the jack_disconnect program */
   /*jack_connect(client, "idjc-mx:voip_send_lt", "idjc-mx:voip_recv_lt");
   jack_connect(client, "idjc-mx:voip_send_rt", "idjc-mx:voip_recv_rt");*/
      
   alarm(3);            /* handles timeouts on media player worker threads */
      
   while (kvp_parse(kvpdict, fp))
      {
      if (jack_closed_f == TRUE || g_shutdown == TRUE)
         break;
         
      if (!strcmp(action, "sync"))
         {
         fprintf(stdout, "IDJC: sync reply\n");
         fflush(stdout);
         sync = TRUE;
         }
      if (sync == FALSE)
         continue;

      if (!strcmp(action, "mp3status"))
         {
         fprintf(stdout, "IDJC: mp3=%d\n", have_mad);
         fflush(stdout);
         }

      if (!strcmp(action, "mic_control_0"))
         {
         mic_valueparse(mic_1, mic_param);
         }

      if (!strcmp(action, "mic_control_1"))
         {
         mic_valueparse(mic_2, mic_param);
         }

      if (!strcmp(action, "mic_control_2"))
         {
         mic_valueparse(mic_3, mic_param);
         }

      if (!strcmp(action, "mic_control_3"))
         {
         mic_valueparse(mic_4, mic_param);
         }

      if (!strcmp(action, "headroom"))
         {
         headroom_db = strtof(headroom, NULL);
         }

      if (!strcmp(action, "anymic"))
         {
         mic_on = (flag[0] == '1') ? 1 : 0;
         }

      if (!strcmp(action, "fademode_left"))
         plr_l->fade_mode = atoi(fade_mode);
         
      if (!strcmp(action, "fademode_right"))
         plr_r->fade_mode = atoi(fade_mode);

      if (!strcmp(action, "playleft"))
         {
         fprintf(stdout, "context_id=%d\n", xlplayer_play(plr_l, playerpathname, atoi(seek_s), atoi(size), atof(rg_db)));
         fflush(stdout);
         }
      if (!strcmp(action, "playright"))
         {
         fprintf(stdout, "context_id=%d\n", xlplayer_play(plr_r, playerpathname, atoi(seek_s), atoi(size), atof(rg_db)));
         fflush(stdout);
         }
      if (!strcmp(action, "playnoflushleft"))
         {
         fprintf(stdout, "context_id=%d\n", xlplayer_play_noflush(plr_l, playerpathname, atoi(seek_s), atoi(size), atof(rg_db)));
         fflush(stdout);
         }
      if (!strcmp(action, "playnoflushright"))
         {
         fprintf(stdout, "context_id=%d\n", xlplayer_play_noflush(plr_r, playerpathname, atoi(seek_s), atoi(size), atof(rg_db)));
         fflush(stdout);
         }
    
      if (!strcmp(action, "playmanyjingles"))
         {
         fprintf(stdout, "context_id=%d\n", xlplayer_playmany(plr_j, playerplaylist, loop[0]=='1'));
         fflush(stdout);
         }
      if (!strcmp(action, "playmanyinterlude"))
         {
         fprintf(stdout, "context_id=%d\n", xlplayer_playmany(plr_i, playerplaylist, loop[0]=='1'));
         fflush(stdout);
         }

      if (!strcmp(action, "stopleft"))
         xlplayer_eject(plr_l);
      if (!strcmp(action, "stopright"))
         xlplayer_eject(plr_r);
      if (!strcmp(action, "stopjingles"))
         xlplayer_eject(plr_j);
      if (!strcmp(action, "stopinterlude"))
         xlplayer_eject(plr_i);
 
      if (!strcmp(action, "dither"))
         {
         xlplayer_dither(plr_l, TRUE);
         xlplayer_dither(plr_r, TRUE);
         xlplayer_dither(plr_j, TRUE);
         xlplayer_dither(plr_i, TRUE);
         }

      if (!strcmp(action, "dontdither"))
         {
         xlplayer_dither(plr_l, FALSE);
         xlplayer_dither(plr_r, FALSE);
         xlplayer_dither(plr_j, FALSE);
         xlplayer_dither(plr_i, FALSE);
         }
      
      if (!strcmp(action, "resamplequality"))
         {
         plr_l->rsqual = plr_r->rsqual = plr_j->rsqual = plr_i->rsqual = resamplequality[0] - '0';
         }
      
      if (!strcmp(action, "ogginforequest"))
         {
         if (oggdecode_get_metainfo(oggpathname, &artist, &title, &length, &replaygain))
            {
            fprintf(stdout, "OIR:ARTIST=%s\nOIR:TITLE=%s\nOIR:LENGTH=%f\nOIR:REPLAYGAIN_TRACK_GAIN=%s\nOIR:end\n", artist, title, length, replaygain);
            fflush(stdout);
            }
         else
            {
            fprintf(stdout, "OIR:NOT VALID\n");
            fflush(stdout);
            }
         }
      
      if (!strcmp(action, "sndfileinforequest"))
         sndfileinfo(sndfilepathname);

#ifdef HAVE_AVCODEC
#ifdef HAVE_AVFORMAT
      if (!strcmp(action, "avformatinforequest"))
         avformatinfo(avformatpathname);
#endif
#endif

#ifdef HAVE_SPEEX
      if (!(strcmp(action, "speexreadtagrequest")))
         speex_tag_read(speexpathname);
      if (!(strcmp(action, "speexwritetagrequest")))
         speex_tag_write(speexpathname, speexcreatedby, speextaglist);
#endif

      if (!strcmp(action, "normalizerstats"))
         {
         if (sscanf(normalizer_string, ":%f:%f:%f:%f:%d:", &new_normalizer.maxlevel,
                &new_normalizer.ceiling, &normrise, &normfall, &new_normalizer.active) != 5)
            {
            fprintf(stderr, "mixer got bad normalizer string\n");
            break;
            }
         new_normalizer.rise = 1.0F / normrise;
         new_normalizer.fall = 1.0F / normfall;
         new_normalizer_stats = TRUE;
         }

      if (!strcmp(action, "mixstats"))
         {
         if(sscanf(mixer_string,
                ":%03d:%03d:%03d:%03d:%03d:%03d:%d:%1d%1d%1d%1d%1d:%1d%1d:%1d:%1d%1d%1d%1d:%1d:%1d:%1d:%1d:%1d:%f:%f:%1d:%f:%d:%d:%d:",
                &volume, &volume2, &crossfade, &jinglesvolume, &interludevol, &mixbackvol, &jingles_playing,
                &left_stream, &left_audio, &right_stream, &right_audio, &stream_monitor,
                &new_left_pause, &new_right_pause, &aux_on, &flush_left, &flush_right, &flush_jingles, &flush_interlude, &simple_mixer, &eot_alarm_set, &mixermode, &fadeout_f, &main_play, &(plr_l->newpbspeed), &(plr_r->newpbspeed), &speed_variance, &dj_audio_level, &crosspattern, &use_dsp, &twodblimit) !=31)
            {
            fprintf(stderr, "mixer got bad mixer string\n");
            break;
            }
         eot_alarm_f |= eot_alarm_set;

         plr_l->fadeout_f = plr_r->fadeout_f = plr_j->fadeout_f = plr_i->fadeout_f = fadeout_f;

         if (use_dsp != using_dsp)
            using_dsp = use_dsp;

         if (new_left_pause != plr_l->pause)
            {
            if (new_left_pause)
               xlplayer_pause(plr_l);
            else
               xlplayer_unpause(plr_l);
            }
            
         if (new_right_pause != plr_r->pause)
            {
            if (new_right_pause)
               xlplayer_pause(plr_r);
            else
               xlplayer_unpause(plr_r);
            }

         if (aux_on != old_aux_on)
            aux_flux = TRUE;
         old_aux_on = aux_on;
         }
      /* the means by which the jack ports are connected to the soundcard */
      /* notably the main app requests the connections */
      if (!strcmp(action, "remakemic1"))
         {
         jack_port_disconnect(client, mic_channel_1);
         if (strcmp(mic1, "default"))
            {
            if (mic1[0] != '\0')
               jack_connect(client, mic1, "idjc-mx:mic_in_1");
            }
         else
            if (inport && inport[0])
               jack_connect(client, inport[0], "idjc-mx:mic_in_1");
         }
         
      if (!strcmp(action, "remakemic2"))
         {
         jack_port_disconnect(client, mic_channel_2);
         if (strcmp(mic2, "default"))
            {
            if (mic2[0] != '\0')
               jack_connect(client, mic2, "idjc-mx:mic_in_2");
            }
         else
            if (inport && inport[0] && inport[1])
               jack_connect(client, inport[1], "idjc-mx:mic_in_2");
         }

      if (!strcmp(action, "remakemic3"))
         {
         jack_port_disconnect(client, mic_channel_3);
         if (strcmp(mic3, "default"))
            {
            if (mic3[0] != '\0')
               jack_connect(client, mic3, "idjc-mx:mic_in_3");
            }
         else
            if (inport && inport[0] && inport[1] && inport[2])
               jack_connect(client, inport[2], "idjc-mx:mic_in_3");
         }
         
      if (!strcmp(action, "remakemic4"))
         {
         jack_port_disconnect(client, mic_channel_4);
         if (strcmp(mic4, "default"))
            {
            if (mic4[0] != '\0')
               jack_connect(client, mic4, "idjc-mx:mic_in_4");
            }
         else
            if (inport && inport[0] && inport[1] && inport[2] && inport[3])
               jack_connect(client, inport[3], "idjc-mx:mic_in_4");
         }

      if (!strcmp(action, "remakeaudl"))
         {
         jack_port_disconnect(client, audio_left_port);
         if (strcmp(audl, "default"))
            {
            if (audl[0] != '\0')
               jack_connect(client, "idjc-mx:dj_out_l", audl);
            }
         else
            if (outport)
               jack_connect(client, "idjc-mx:dj_out_l", outport[0]);
         }
      if (!strcmp(action, "remakeaudr"))
         {
         jack_port_disconnect(client, audio_right_port);
         if (strcmp(audr, "default"))
            {
            if (audr[0] != '\0')
               jack_connect(client, "idjc-mx:dj_out_r", audr);
            }
         else
            if (outport && outport[1])
               jack_connect(client, "idjc-mx:dj_out_r", outport[1]);
         }
      if (!strcmp(action, "remakestrl"))
         {
         jack_port_disconnect(client, stream_left_port);
         jack_connect(client, "idjc-mx:str_out_l", "idjc-sc:str_in_l");
         if (strcmp(strl, "default"))
            {
            if (strl[0] != '\0')
               jack_connect(client, "idjc-mx:str_out_l", strl);
            }
         else
            if (outport && outport[1] && outport[2] && outport[3] && outport[4])
               jack_connect(client, "idjc-mx:str_out_l", outport[4]);
            else
               if(outport && outport[1] && outport[2])
                  jack_connect(client, "idjc-mx:str_out_l", outport[2]);
         }
      if (!strcmp(action, "remakestrr"))
         {
         jack_port_disconnect(client, stream_right_port);
         jack_connect(client, "idjc-mx:str_out_r", "idjc-sc:str_in_r");
         if (strcmp(strr, "default"))
            {
            if (strr[0] != '\0')
               jack_connect(client, "idjc-mx:str_out_r", strr);
            }
         else
            if (outport && outport[1] && outport[2] && outport[3] && outport[4] && outport[5])
               jack_connect(client, "idjc-mx:str_out_r", outport[5]);
            else
               if (outport && outport[1] && outport[2] && outport[3])
                  jack_connect(client, "idjc-mx:str_out_r", outport[3]);
         }
      if (!strcmp(action, "remakeauxl"))
         {
         jack_port_disconnect(client, aux_left_channel);
         if (auxl[0] != '\0')
            jack_connect(client, auxl, "idjc-mx:aux_in_l");
         }
      if (!strcmp(action, "remakeauxr"))
         {
         jack_port_disconnect(client, aux_right_channel);
         if (auxr[0] != '\0')
            jack_connect(client, auxr, "idjc-mx:aux_in_r");
         }
      if (!strcmp(action, "remakemidi"))
         {
         jack_port_disconnect(client, midi_port);
         if (midi[0] != '\0')
            jack_connect(client, midi, "idjc-mx:midi_control");
         }
      if (!strcmp(action, "remakedol"))
         {
         jack_port_disconnect(client, dspout_left_port);
         if (dol[0] != '\0')
            jack_connect(client, "idjc-mx:dsp_out_l" , dol);
         }
      if (!strcmp(action, "remakedor"))
         {
         jack_port_disconnect(client, dspout_right_port);
         if (dor[0] != '\0')
            jack_connect(client, "idjc-mx:dsp_out_r" , dor);
         }
      if (!strcmp(action, "remakedil"))
         {
         jack_port_disconnect(client, dspin_left_port);
         if (dil[0] != '\0')
            jack_connect(client, dil, "idjc-mx:dsp_in_l");
         }
      if (!strcmp(action, "remakedir"))
         {
         jack_port_disconnect(client, dspin_right_port);
         if (dir[0] != '\0')
            jack_connect(client, dir, "idjc-mx:dsp_in_r");
         }
      if (!strcmp(action, "serverbind"))
         {
         fprintf(stderr, "remaking connection to server\n");
         jack_connect(client, "idjc-mx:str_out_l", "idjc-sc:str_in_l"); 
         jack_connect(client, "idjc-mx:str_out_r", "idjc-sc:str_in_r");
         }
      if (!strcmp(action, "requestlevels"))
         {
         timeout = 0;           /* the main app has proven it is alive */
         /* make logarithmic values for the peak levels */
         str_l_peak_db = peak_to_log(peakfilter_read(str_pf_l));
         str_r_peak_db = peak_to_log(peakfilter_read(str_pf_r));
         /* set reply values for a totally blank signal */
         str_l_rms_db = str_r_rms_db = 120;
         /* compute the rms values */
         if (str_l_meansqrd)
            str_l_rms_db = (int) fabs(level2db(sqrt(str_l_meansqrd)));
         if (str_r_meansqrd)
            str_r_rms_db = (int) fabs(level2db(sqrt(str_r_meansqrd)));
            
         /* send the meter and other stats to the main app */
         mic_stats("mic_1_levels", mic_1);
         mic_stats("mic_2_levels", mic_2);
         mic_stats("mic_3_levels", mic_3);
         mic_stats("mic_4_levels", mic_4);

         /* forward any MIDI commands that have been queued since last time */
         pthread_mutex_lock(&midi_mutex);
         midi_output[0]= '\0';
         if (midi_nqueued>0) /* exclude leading `,`, include trailing `\0` */
            memcpy(midi_output, midi_queue+1, midi_nqueued*sizeof(char));
         midi_queue[0]= '\0';
         midi_nqueued= 0;
         pthread_mutex_unlock(&midi_mutex);

         fprintf(stdout, 
                   "str_l_peak=%d\nstr_r_peak=%d\n"
                   "str_l_rms=%d\nstr_r_rms=%d\n"
                   "jingles_playing=%d\n"
                   "left_elapsed=%d\n"
                   "right_elapsed=%d\n"
                   "left_playing=%d\n"
                   "right_playing=%d\n"
                   "interlude_playing=%d\n"
                   "left_signal=%d\n"
                   "right_signal=%d\n"
                   "left_cid=%d\n"
                   "right_cid=%d\n"
                   "jingles_cid=%d\n"
                   "interlude_cid=%d\n"
                   "left_audio_runout=%d\n"
                   "right_audio_runout=%d\n"
                   "left_additional_metadata=%d\n"
                   "right_additional_metadata=%d\n"
                   "midi=%s\n"
                   "end\n",
                   str_l_peak_db, str_r_peak_db,
                   str_l_rms_db, str_r_rms_db,
                   jingles_audio_f | (plr_j->current_audio_context & 0x1),
                   plr_l->play_progress_ms / 1000,
                   plr_r->play_progress_ms / 1000,
                   plr_l->have_data_f | (plr_l->current_audio_context & 0x1),
                   plr_r->have_data_f | (plr_r->current_audio_context & 0x1),
                   plr_i->have_data_f | (plr_i->current_audio_context & 0x1),
                   left_peak > 0.02F || left_peak < 0.0F || plr_l->pause,
                   right_peak > 0.02F || right_peak < 0.0F || plr_r->pause,
                   plr_l->current_audio_context,
                   plr_r->current_audio_context,
                   plr_j->current_audio_context,
                   plr_i->current_audio_context,
                   left_audio_runout && (!(plr_l->current_audio_context & 0x1)),
                   right_audio_runout && (!(plr_r->current_audio_context & 0x1)),
                   plr_l->dynamic_metadata.data_type,
                   plr_r->dynamic_metadata.data_type,
                   midi_output);

         /* tell the jack mixer it can reset its vu stats now */
         reset_vu_stats_f = TRUE;
         if (plr_l->dynamic_metadata.data_type)
            send_metadata_update(&(plr_l->dynamic_metadata));
         if (plr_r->dynamic_metadata.data_type)
            send_metadata_update(&(plr_r->dynamic_metadata));
         fflush(stdout);
         }
      }
   alarm(0);
   jack_client_close(client);
   client = NULL;
   free(fade_table);
   free(eot_alarm_table);
   free_signallookup_table();
   free_dblookup_table();
   jack_free_ports(inport);
   jack_free_ports(outport);
   mic_free(mic_1);
   mic_free(mic_2);
   mic_free(mic_3);
   mic_free(mic_4);
   peakfilter_destroy(str_pf_l);
   peakfilter_destroy(str_pf_r);
   /*beat_free(beat_lp);
   beat_free(beat_rp);*/
   ifree(lp_lc);
   ifree(lp_rc);
   ifree(rp_lc);
   ifree(rp_rc);
   ifree(jp_lc);
   ifree(jp_rc);
   ifree(ip_lc);
   ifree(ip_rc);
   ifree(lp_lcf);
   ifree(lp_rcf);
   ifree(rp_lcf);
   ifree(rp_rcf);
   ifree(jp_lcf);
   ifree(jp_rcf);
   ifree(ip_lcf);
   ifree(ip_rcf);
   xlplayer_destroy(plr_l);
   xlplayer_destroy(plr_r);
   xlplayer_destroy(plr_j);
   xlplayer_destroy(plr_i);
   fprintf(stderr, "Mixer module has closed\n");
   return 0;
   }
