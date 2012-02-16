/*
#   mixer.c: the audio mix happens in here.
#   Copyright (C) 2005-2012 Stephen Fairchild (s-fairchild@users.sourceforge.net)
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
#include "mp3dec.h"
#include "ialloc.h"
#include "speextag.h"
#include "sndfileinfo.h"
#include "avcodecdecode.h"
#include "oggdec.h"
#include "mic.h"
#include "bsdcompat.h"
#include "dyn_mad.h"
#include "peakfilter.h"
#include "sig.h"
#include "main.h"

#define TRUE 1
#define FALSE 0

/* playlength of ring buffer contents in seconds */
#define RB_SIZE 10.0
/* number of bytes in the MIDI queue buffer */
#define MIDI_QUEUE_SIZE 1024

/* the different VOIP modes */
#define NO_PHONE 0
#define PHONE_PUBLIC 1
#define PHONE_PRIVATE 2

typedef jack_default_audio_sample_t sample_t;

/* values of the volume sliders in the GUI */
static int volume, volume2, crossfade, jinglesvolume, jinglesvolume2, interludevol, mixbackvol, crosspattern;
/* back and forth status indicators re. jingles */
static int jingles_playing, jingles_audio_f;
/* used for gapless playback to indicate an almost empty buffer */
static int left_audio_runout = 0, right_audio_runout = 0;
/* the main-player unmute buttons */
static int left_stream = 1, left_audio = 1, right_stream = 1, right_audio = 1;
/* status variables for the button cluster in lower right of main window */
static int mic_on, mixermode = NO_PHONE;
/* simple mixer mode: uses less space on the screen and less cpu as well */
static int simple_mixer;
/* currentvolumes are used to implement volume smoothing */
static int current_volume, current_volume2, current_jingles_volume, current_jingles_volume2, 
    current_interlude_volume, current_crossfade, currentmixbackvol, current_crosspattern;
/* value of the stream mon. button */
static int stream_monitor = 0;
/* when this is set the end of track alarm is started */
static int eot_alarm_set = 0;
/* set when end of track alarm is active */
static int eot_alarm_f = 0;
/* threshold values for a premature indicator that a player is about to finish */
static unsigned jingles_samples_cutoff;
static unsigned player_samples_cutoff;
/* used to implement interlude player fade in/out: true when playing a track */
static int main_play;
/* flag to indicate whether to use the player reading function which supports speed variance */
static int speed_variance;
/* buffers that process_audio uses when reading media player data */
static sample_t *lp_lc, *lp_rc, *rp_lc, *rp_rc, *jp_lc, *jp_rc, *ip_lc, *ip_rc;
static sample_t *lp_lcf, *lp_rcf, *rp_lcf, *rp_rcf, *jp_lcf, *jp_rcf, *ip_lcf, *ip_rcf;
/* used for signal level silence threshold tracking */
static sample_t left_peak = -1.0F, right_peak = -1.0F;
/* handle for beat processing */
/*struct beatproc *beat_lp, *beat_rp;*/
/* flag to indicate if audio is routed via dsp interface */
static int using_dsp;
/* flag to indicate that stream audio be reduced for improved encode quality */
static int twodblimit;
/* handles for microphone */
static struct mic **mics;
/* peakfilter handles for stream peak */
static struct peakfilter *str_pf_l, *str_pf_r;

static jack_nframes_t alarm_size;

static float headroom_db;                      /* player muting level when mic is open */
static float str_l_tally, str_r_tally;  /* used to calculate rms value */
static int rms_tally_count;
static float str_l_meansqrd, str_r_meansqrd;
static int reset_vu_stats_f;                   /* when set the mixer will reset the above */
static float dfmod;                            /* used to reduce the ducking factor */
static float dj_audio_level;                   /* used to reduce the level of dj audio */
static float dj_audio_gain = 1.0;              /* same as above but not in dB */
static float current_dj_audio_level = 0.0;

static struct compressor stream_limiter =
   {
   0.0, -0.05, -0.2, INFINITY, 1, 1.0F/4000.0F, 0.0, 0.0, 1, 1, 0.0, 0.0, 0.0
   }, audio_limiter =
   {
   0.0, -0.05, -0.2, INFINITY, 1, 1.0F/4000.0F, 0.0, 0.0, 1, 1, 0.0, 0.0, 0.0
   }, phone_limiter =
   {
   0.0, -0.05, -0.2, INFINITY, 1, 1.0F/4000.0F, 0.0, 0.0, 1, 1, 0.0, 0.0, 0.0
   };

/* the different player's gain factors */
/* lp=left player, rp=right player, jp=jingles player, ip=interlude player */ 
/* lc=left channel, rc=right channel */
/* aud = the DJs audio, str = the listeners (stream) audio */
/* the initial settings are 'very' temporary */
static sample_t lp_lc_aud = 1.0, lp_rc_aud = 1.0, rp_lc_aud = 1.0, rp_rc_aud = 1.0;
static sample_t lp_lc_str = 1.0, lp_rc_str = 1.0, rp_lc_str = 0.0, rp_rc_str = 0.0;
static sample_t jp_lc_str = 0.0, jp_rc_str = 0.0, jp_lc_aud = 0.0, jp_rc_aud = 0.0;
static sample_t ip_lc_str = 0.0, ip_rc_str = 0.0, ip_lc_aud = 0.0, ip_rc_aud = 0.0;
                                /* like above but for fade */
static sample_t lp_lc_audf = 1.0, lp_rc_audf = 1.0, rp_lc_audf = 1.0, rp_rc_audf = 1.0;
static sample_t lp_lc_strf = 1.0, lp_rc_strf = 1.0, rp_lc_strf = 1.0, rp_rc_strf = 1.0;
static sample_t jp_lc_strf = 1.0, jp_rc_strf = 1.0, jp_lc_audf = 1.0, jp_rc_audf = 1.0;
static sample_t ip_lc_strf = 1.0, ip_rc_strf = 1.0, ip_lc_audf = 0.0, ip_rc_audf = 0.0;
         
/* media player mixback level for when in RedPhone mode */
static sample_t mb_lc_aud = 1.0, mb_rc_aud = 1.0;
static sample_t current_headroom;      /* the amount of mic headroom being applied */
static sample_t *eot_alarm_table;      /* the wave table for the DJ alarm */
         
static char midi_queue[MIDI_QUEUE_SIZE];
static size_t midi_nqueued= 0;
static pthread_mutex_t midi_mutex;

static unsigned long sr;               /* the sample rate reported by JACK */

static struct xlplayer *plr_l, *plr_r, *plr_j, *plr_i; /* player instance stuctures */

/* these are set in the parse routine - the contents coming from the GUI */
static char *mixer_string, *compressor_string, *gate_string, *microphone_string, *item_index;
static char *new_mic_string;
static char *midi, *audl, *audr, *strl, *strr, *action;
static char *target_port_name;
static char *dol, *dor, *dil, *dir;
static char *oggpathname, *sndfilepathname, *avformatpathname, *speexpathname, *speextaglist, *speexcreatedby;
static char *playerpathname, *seek_s, *size, *playerplaylist, *loop, *resamplequality;
static char *mic_param, *fade_mode;
static char *rg_db, *headroom;
static char *flag;
static char *channel_mode_string;
static char *use_jingles_vol_2;
static char *jackport, *jackport2, *jackfilter;

/* dictionary look-up type thing used by the parse routine */
static struct kvpdict kvpdict[] = {
         { "PLRP", &playerpathname, NULL },   /* The media-file pathname for playback */
         { "RGDB", &rg_db, NULL },            /* Replay Gain volume level controlled at the player end */
         { "SEEK", &seek_s, NULL },           /* Playback initial seek time in seconds */
         { "SIZE", &size, NULL },             /* Size of the file in seconds */
         { "PLPL", &playerplaylist, NULL },   /* A playlist for the media players */
         { "LOOP", &loop, NULL },             /* play in a loop */
         { "MIXR", &mixer_string, NULL },     /* Control strings */
         { "COMP", &compressor_string, NULL },/* packed full of data */
         { "GATE", &gate_string, NULL },
         { "MICS", &microphone_string, NULL },
         { "INDX", &item_index, NULL },
         { "NMIC", &new_mic_string, NULL },
         { "MIC",  &target_port_name, NULL },
         { "MIDI", &midi, NULL },
         { "AUDL", &audl, NULL },
         { "AUDR", &audr, NULL },
         { "STRL", &strl, NULL },
         { "STRR", &strr, NULL },
         { "DOL", &dol, NULL   },
         { "DOR", &dor, NULL   },
         { "DIL", &dil, NULL   },
         { "DIR", &dir, NULL   },
         { "VOL2", &use_jingles_vol_2, NULL },
         { "FADE", &fade_mode, NULL },
         { "OGGP", &oggpathname, NULL },
         { "SPXP", &speexpathname, NULL },
         { "SNDP", &sndfilepathname, NULL },
         { "AVFP", &avformatpathname, NULL },
         { "SPXT", &speextaglist, NULL },
         { "SPXC", &speexcreatedby, NULL },
         { "RSQT", &resamplequality, NULL },
         { "AGCP", &mic_param, NULL },
         { "HEAD", &headroom, NULL },
         { "FLAG", &flag, NULL },
         { "CMOD", &channel_mode_string, NULL },
         { "JFIL", &jackfilter, NULL },
         { "JPRT", &jackport, NULL },
         { "JPT2", &jackport2, NULL },
         { "ACTN", &action, NULL },                   /* Action to take */
         { "", NULL, NULL }};

/* handle_mute_button: soft on/off for the mute buttons */
static void handle_mute_button(sample_t *gainlevel, int switchlevel)
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

void mixer_stop_players()
   {
   plr_l->command = CMD_COMPLETE;
   plr_r->command = CMD_COMPLETE;
   plr_j->command = CMD_COMPLETE;
   plr_i->command = CMD_COMPLETE;
   }

/* update_smoothed_volumes: stuff that gets run once every 32 samples */
static void update_smoothed_volumes()
   {
   static sample_t vol_rescale = 1.0F, vol2_rescale = 1.0F, jingles_vol_rescale = 1.0F;
   static sample_t jingles_vol_rescale2 = 1.0F, interlude_vol_rescale = 1.0F;
   static sample_t cross_left = 1.0F, cross_right = 0.0F, mixback_rescale = 1.0F;
   static sample_t lp_listen_mute = 1.0F, rp_listen_mute = 1.0F, lp_stream_mute = 1.0F, rp_stream_mute = 1.0F;
   sample_t mic_target, diff;
   static float interlude_autovol = -128.0F, old_autovol = -128.0F;
   float vol;
   float xprop, yprop;
   const float bias = 0.35386f;
   const float pat3 = 0.9504953575f;

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
      else if (current_crosspattern == 2)
         {
         if (current_crossfade == 100)
            cross_left = 0.0f;
         else
            cross_left = powf(pat3, current_crossfade);
            
         if (current_crossfade == 0)
            cross_right = 0.0f;
         else
            cross_right = powf(pat3, 100 - current_crossfade);
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

   if (jinglesvolume2 != current_jingles_volume2)
      {
      if (jinglesvolume2 > current_jingles_volume2)
         current_jingles_volume2++;
      else
         current_jingles_volume2--;
      jingles_vol_rescale2 = 1.0F/powf(10.0F,current_jingles_volume2/55.0F);
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
   jp_lc_str = jp_rc_str = jp_lc_aud = jp_rc_aud = (use_jingles_vol_2 && use_jingles_vol_2[0] == '1') ? jingles_vol_rescale2 : jingles_vol_rescale;
   mb_lc_aud = mb_rc_aud = mixback_rescale;
   ip_lc_aud = ip_rc_aud = 0.0F;
   ip_lc_str = ip_rc_str = interlude_vol_rescale;
    
   mic_target = -headroom_db;
   if ((diff = mic_target - current_headroom))
      {
      current_headroom += diff * 1600.0f / (sr * powf(headroom_db + 10.0f, 0.93f));
      if (fabsf(diff) < 0.000001F)
         current_headroom = mic_target;
      }

   if (jingles_playing)
      vol = current_jingles_volume * 0.06666666F;
   else
      vol = (current_volume - (current_volume - current_volume2) / 2.0F) * 0.06666666F;
   dfmod = vol * vol + 1.0F;
   }

/* process_audio: the JACK callback routine */
int mixer_process_audio(jack_nframes_t nframes, void *arg)
   {
   int samples_todo;            /* The samples remaining counter in the main loop */
   static float df = 1.0;       /* the ducking factor - generated by the compressor */
   /* the following are used to calculate the microphone mix */
   sample_t lc_s_micmix = 0.0f, rc_s_micmix = 0.0f, d_micmix = 0.0f;
   sample_t lc_s_auxmix = 0.0f, rc_s_auxmix = 0.0f;
   /* the following are used to apply the output of the compressor code to the audio levels */
   sample_t compressor_gain = 1.0;
   /* a counter variable used to trigger the volume smoothing on a regular basis */
   static unsigned vol_smooth_count = 0;
   /* index values for reading from a table of fade gain values */
   static jack_nframes_t alarm_index = 0;
   /* pointers to buffers provided by JACK */
   sample_t *lap, *rap, *lsp, *rsp, *lpsp, *rpsp, *lprp, *rprp;
   sample_t *la_buffer, *ra_buffer, *ls_buffer, *rs_buffer, *lps_buffer, *rps_buffer;
   sample_t *dolp, *dorp, *dilp, *dirp;
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
   struct mic **micp;

   /* midi_control. read incoming commands forward to gui */
   midi_buffer = jack_port_get_buffer(g.port.midi_port, nframes);
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
   {
      struct jack_ports *p = &g.port;
      
      la_buffer = lap = (sample_t *) jack_port_get_buffer (p->dj_out_l, nframes);
      ra_buffer = rap = (sample_t *) jack_port_get_buffer (p->dj_out_r, nframes);
      ls_buffer = lsp = (sample_t *) jack_port_get_buffer (p->str_out_l, nframes);
      rs_buffer = rsp = (sample_t *) jack_port_get_buffer (p->str_out_r, nframes);
      lps_buffer = lpsp = (sample_t *) jack_port_get_buffer (p->voip_out_l, nframes);
      rps_buffer = rpsp = (sample_t *) jack_port_get_buffer (p->voip_out_r, nframes);
      lprp = (sample_t *) jack_port_get_buffer (p->voip_in_l, nframes);
      rprp = (sample_t *) jack_port_get_buffer (p->voip_in_r, nframes);
      dolp = (sample_t *) jack_port_get_buffer (p->dsp_out_l, nframes);
      dorp = (sample_t *) jack_port_get_buffer (p->dsp_out_r, nframes);
      dilp = (sample_t *) jack_port_get_buffer (p->dsp_in_l, nframes);
      dirp = (sample_t *) jack_port_get_buffer (p->dsp_in_r, nframes);
   }
   
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
      if (!g.app_shutdown)
         {
         alarm(1);
         printf("Malloc failure in process audio\n");
         g.app_shutdown = TRUE;
         }
      mixer_stop_players();
      return -1;
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

   mic_process_start_all(mics, nframes);

   /* there are four mixer modes and the only seemingly efficient way to do them is */
   /* to basically copy a lot of code four times over hence the huge size */
   if (simple_mixer == FALSE && mixermode == NO_PHONE)  /* Fully featured mixer code */
      {
      memset(lps_buffer, 0, nframes * sizeof (sample_t)); /* send silence to VOIP */
      memset(rps_buffer, 0, nframes * sizeof (sample_t));
      for(samples_todo = nframes; samples_todo--; lap++, rap++, lsp++, rsp++,
                lplcp++, lprcp++, rplcp++, rprcp++, jplcp++, jprcp++, iplcp++, iprcp++, dilp++, dirp++, dolp++, dorp++)
         {       
         if (vol_smooth_count++ % 100 == 0) /* Can change volume level every so many samples */
            update_smoothed_volumes();
         
         df = mic_process_all(mics) * dfmod;
         for (micp = mics, lc_s_micmix = rc_s_micmix = lc_s_auxmix = rc_s_auxmix = d_micmix = 0.0f; *micp; micp++)
            {
            lc_s_micmix += (*micp)->mlcm;
            rc_s_micmix += (*micp)->mrcm;
            lc_s_auxmix += (*micp)->alcm;
            rc_s_auxmix += (*micp)->arcm;
            d_micmix += (*micp)->munpmdj;
            }
       
         /* ducking calculation - disabled mics have df of 1.0 always */
         {
             float hr = db2level(current_headroom);
             df = (df < hr) ? df : hr;
         }

         #define FM(fl, fr, plr, sl, sr) \
            do { \
               float l = fade_get(plr->fadeout); \
               fl = l * *sl++; \
               fr = l * *sr++; \
            }while(0)

         FM(lp_lc_fade, lp_rc_fade, plr_l, lplcpf, lprcpf);
         FM(rp_lc_fade, rp_rc_fade, plr_r, rplcpf, rprcpf);
         FM(jp_lc_fade, jp_rc_fade, plr_j, jplcpf, jprcpf);
         FM(ip_lc_fade, ip_rc_fade, plr_i, iplcpf, iprcpf);

         if (fabs(*lplcp) > left_peak)          /* peak levels used for song cut-off */
            left_peak = fabs(*lplcp);
         if (fabs(*lprcp) > left_peak)
            left_peak = fabs(*lprcp);
         if (fabs(*rplcp) > right_peak)
            right_peak = fabs(*rplcp);
         if (fabs(*rprcp) > right_peak)
            right_peak = fabs(*rprcp);
         
         /* This is it folks, the main mix */
         *dolp = ((*lplcp * lp_lc_str) + (*rplcp * rp_lc_str) + (*jplcp * jp_lc_str)) * df + lc_s_micmix + lc_s_auxmix + (*iplcp * ip_lc_str) + (ip_lc_fade * ip_lc_strf) + 
         (lp_lc_fade * lp_lc_strf) + (rp_lc_fade * rp_lc_strf) + (jp_lc_fade * jp_lc_strf);
         *dorp = ((*lprcp * lp_rc_str) + (*rprcp * rp_rc_str) + (*jprcp * jp_rc_str)) * df + rc_s_micmix + rc_s_auxmix + (*iprcp * ip_rc_str) + (ip_rc_fade * ip_rc_strf) +
         (lp_rc_fade * lp_rc_strf) + (rp_rc_fade * rp_rc_strf) + (jp_rc_fade * jp_rc_strf);
         
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
            *lap = ((*lplcp * lp_lc_aud) + (*rplcp * rp_lc_aud) + (*jplcp * jp_lc_aud)) * df + d_micmix + lc_s_auxmix + (*iplcp * ip_lc_aud) + (ip_lc_fade * ip_lc_aud) +
            (lp_lc_fade * lp_lc_audf) + (rp_lc_fade * rp_lc_audf) + (jp_lc_fade * jp_lc_audf);
            *rap = ((*lprcp * lp_rc_aud) + (*rprcp * rp_rc_aud) + (*jprcp * jp_rc_aud)) * df + d_micmix + rc_s_auxmix + (*iprcp * ip_rc_aud) + (ip_rc_fade * ip_rc_aud) +
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
         for(samples_todo = nframes; samples_todo--; lap++, rap++, lsp++, rsp++,
                lplcp++, lprcp++, rplcp++, rprcp++, jplcp++, jprcp++,
                lpsp++, rpsp++, lprp++, rprp++, iplcp++, iprcp++, dilp++, dirp++, dolp++, dorp++)
            {    
            if (vol_smooth_count++ % 100 == 0) /* Can change volume level every so many samples */
               update_smoothed_volumes();
         
            mic_process_all(mics);
            for (micp = mics, lc_s_micmix = rc_s_micmix = lc_s_auxmix = rc_s_auxmix = d_micmix = 0.0f; *micp; micp++)
               {
               lc_s_micmix += (*micp)->mlcm;
               rc_s_micmix += (*micp)->mrcm;
               lc_s_auxmix += (*micp)->alcm;
               rc_s_auxmix += (*micp)->arcm;
               d_micmix += (*micp)->munpmdj;
               }

            /* No ducking but headroom still must apply */
            df = db2level(current_headroom);

            FM(lp_lc_fade, lp_rc_fade, plr_l, lplcpf, lprcpf);
            FM(rp_lc_fade, rp_rc_fade, plr_r, rplcpf, rprcpf);
            FM(jp_lc_fade, jp_rc_fade, plr_j, jplcpf, jprcpf);
            FM(ip_lc_fade, ip_rc_fade, plr_i, iplcpf, iprcpf);
            
            /* do the phone send mix */
            *lpsp = lc_s_micmix + (*jplcp * jp_lc_str) + (jp_lc_fade * jp_lc_strf);
            *rpsp = rc_s_micmix + (*jprcp * jp_rc_str) + (jp_rc_fade * jp_rc_strf);
            
            if (fabs(*lplcp) > left_peak)               /* peak levels used for song cut-off */
               left_peak = fabs(*lplcp);
            if (fabs(*lprcp) > left_peak)
               left_peak = fabs(*lprcp);
            if (fabs(*rplcp) > right_peak)
               right_peak = fabs(*rplcp);
            if (fabs(*rprcp) > right_peak)
               right_peak = fabs(*rprcp);

            /* The main mix */
            *dolp = ((*lplcp * lp_lc_str) + (*rplcp * rp_lc_str)) * df + *lprp + *lpsp + lc_s_auxmix +
            (lp_lc_fade * lp_rc_strf) + (rp_lc_fade * rp_lc_strf) + (*iplcp * ip_lc_str) + (ip_lc_fade * ip_lc_strf);
            *dorp = ((*lprcp * lp_rc_str) + (*rprcp * rp_rc_str)) * df + *rprp + *rpsp + rc_s_auxmix +
            (lp_rc_fade * lp_rc_strf) + (rp_rc_fade * rp_rc_strf) + (*iprcp * ip_rc_str) + (ip_rc_fade * ip_rc_strf);
            
            compressor_gain = db2level(limiter(&phone_limiter, *lpsp, *rpsp));
            *lpsp *= compressor_gain;
            *rpsp *= compressor_gain;

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
               *lap = ((*lplcp * lp_lc_aud) + (*rplcp * rp_lc_aud)) * df + *lprp + lc_s_auxmix +
               (lp_lc_fade * lp_rc_audf) + (rp_lc_fade * rp_lc_audf) + (*iplcp * ip_lc_aud) + (ip_lc_fade * ip_lc_audf) + d_micmix + (*jplcp * jp_lc_str) + (jp_lc_fade * jp_lc_strf);
               *rap = ((*lprcp * lp_rc_aud) + (*rprcp * rp_rc_aud)) * df + *rprp + rc_s_auxmix +
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
            for(samples_todo = nframes; samples_todo--; lap++, rap++, lsp++, rsp++,
            lplcp++, lprcp++, rplcp++, rprcp++, jplcp++, jprcp++, lpsp++, rpsp++, 
            lprp++, rprp++, iplcp++, iprcp++, dilp++, dirp++, dolp++, dorp++)
               {         
               if (vol_smooth_count++ % 100 == 0) /* Can change volume level every so many samples */
                  update_smoothed_volumes();

               mic_process_all(mics);
               for (micp = mics, lc_s_micmix = rc_s_micmix = lc_s_auxmix = rc_s_auxmix = d_micmix = 0.0f; *micp; micp++)
                  {
                  lc_s_micmix += (*micp)->mlc;
                  rc_s_micmix += (*micp)->mrc;
                  lc_s_auxmix += (*micp)->alcm;
                  rc_s_auxmix += (*micp)->arcm;
                  d_micmix += (*micp)->munpm;
                  }
               
               /* No ducking */
               df = 1.0;

               FM(lp_lc_fade, lp_rc_fade, plr_l, lplcpf, lprcpf);
               FM(rp_lc_fade, rp_rc_fade, plr_r, rplcpf, rprcpf);
               FM(jp_lc_fade, jp_rc_fade, plr_j, jplcpf, jprcpf);
               FM(ip_lc_fade, ip_rc_fade, plr_i, iplcpf, iprcpf);

               if (fabs(*lplcp) > left_peak)            /* peak levels used for song cut-off */
                  left_peak = fabs(*lplcp);
               if (fabs(*lprcp) > left_peak)
                  left_peak = fabs(*lprcp);
               if (fabs(*rplcp) > right_peak)
                  right_peak = fabs(*rplcp);
               if (fabs(*rprcp) > right_peak)
                  right_peak = fabs(*rprcp);
               
               /* This is it folks, the main mix */
               *dolp = (*lplcp * lp_lc_str) + (*rplcp * rp_lc_str) + lc_s_auxmix + 
               (lp_lc_fade * lp_rc_strf) + (rp_lc_fade * rp_lc_strf) + (*iplcp * ip_lc_str) + (ip_lc_fade * ip_lc_strf);
               *dorp = (*lprcp * lp_rc_str) + (*rprcp * rp_rc_str) + rc_s_auxmix +
               (lp_rc_fade * lp_rc_strf) + (rp_rc_fade * rp_rc_strf) + (*iprcp * ip_rc_str) + (ip_rc_fade * ip_rc_strf);
               
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
                  *lap = (*lsp * mb_lc_aud) + (*jplcp * jp_lc_aud) + d_micmix + (lc_s_auxmix *mb_lc_aud) + (jp_lc_fade * jp_lc_strf) + *lprp;
                  *rap = (*rsp * mb_lc_aud) + (*jprcp * jp_rc_aud) + d_micmix + (rc_s_auxmix *mb_rc_aud) + (jp_rc_fade * jp_rc_strf) + *rprp;
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
               for(samples_todo = nframes; samples_todo--; lap++, rap++, lsp++, rsp++, 
                     lplcp++, lprcp++, rplcp++, rprcp++, jplcp++, jprcp++, lpsp++, rpsp++,
                        iplcp++, iprcp++, dilp++, dirp++, dolp++, dorp++)
                  {
                  if (vol_smooth_count++ % 100 == 0) /* Can change volume level every so many samples */
                     update_smoothed_volumes();

                  df = mic_process_all(mics) * dfmod;
                  for (micp = mics, lc_s_micmix = rc_s_micmix = lc_s_auxmix = rc_s_auxmix = d_micmix = 0.0f; *micp; micp++)
                     {
                     lc_s_micmix += (*micp)->mlcm;
                     rc_s_micmix += (*micp)->mrcm;
                     lc_s_auxmix += (*micp)->alcm;
                     rc_s_auxmix += (*micp)->arcm;
                     d_micmix += (*micp)->munpmdj;
                     }

                  /* ducking calculation - disabled mics have df of 1.0 always */
                  {
                      float hr = db2level(current_headroom);
                      df = (df < hr) ? df : hr;
                  }

                  FM(lp_lc_fade, lp_rc_fade, plr_l, lplcpf, lprcpf);
                  FM(rp_lc_fade, rp_rc_fade, plr_r, rplcpf, rprcpf);
                  FM(jp_lc_fade, jp_rc_fade, plr_j, jplcpf, jprcpf);
                  FM(ip_lc_fade, ip_rc_fade, plr_i, iplcpf, iprcpf);

                  if (fabs(*lplcp) > left_peak)         /* peak levels used for song cut-off */
                     left_peak = fabs(*lplcp);
                  if (fabs(*lprcp) > left_peak)
                     left_peak = fabs(*lprcp);
                  if (fabs(*rplcp) > right_peak)
                     right_peak = fabs(*rplcp);
                  if (fabs(*rprcp) > right_peak)
                     right_peak = fabs(*rprcp);

                  /* This is it folks, the main mix */
                  *dolp = ((*lplcp * lp_lc_str) + (*rplcp * rp_lc_str) + (*jplcp * jp_lc_str)) * df + lc_s_micmix + lc_s_auxmix + (*iplcp * ip_lc_str) + (ip_lc_fade * ip_lc_strf) +
                  (lp_lc_fade * lp_lc_strf) + (rp_lc_fade * rp_lc_strf) + (jp_lc_fade * jp_lc_strf);
                  *dorp = ((*lprcp * lp_rc_str) + (*rprcp * rp_rc_str) + (*jprcp * jp_rc_str)) * df + rc_s_micmix + rc_s_auxmix + (*iprcp * ip_rc_str) + (ip_rc_fade * ip_rc_strf) +
                  (lp_rc_fade * lp_rc_strf) + (rp_rc_fade * rp_rc_strf) + (jp_rc_fade * jp_rc_strf);
                  
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
                     *lap = ((*lplcp * lp_lc_aud) + (*rplcp * rp_lc_aud) + (*jplcp * jp_lc_aud)) * df + d_micmix + lc_s_auxmix + (*iplcp * ip_lc_aud) + (ip_lc_fade * ip_lc_audf) +
                     (lp_lc_fade * lp_lc_audf) + (rp_lc_fade * rp_lc_audf) + (jp_lc_fade * jp_lc_audf);
                     *rap = ((*lprcp * lp_rc_aud) + (*rprcp * rp_rc_aud) + (*jprcp * jp_rc_aud)) * df + d_micmix + rc_s_auxmix + (*iprcp * ip_rc_aud) + (ip_rc_fade * ip_rc_audf) +
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
   return 0;
   }
 
static int peak_to_log(float peak)
   {
   if (peak <= 0.0)
      return -127;
   if (peak >= 1.0)
      return 0;
   return (int)level2db(peak);
   }

int mixer_keepalive()
   { 
   ++plr_l->watchdog_timer;
   ++plr_r->watchdog_timer;
   ++plr_i->watchdog_timer;
   ++plr_j->watchdog_timer;

   #define TEST(x) (x->watchdog_timer >= 9)
   return !(TEST(plr_l) || TEST(plr_r) || TEST(plr_i) || TEST(plr_j));
   #undef TEST
   }

static void send_metadata_update(struct xlp_dynamic_metadata *dm)
   {
   pthread_mutex_lock(&(dm->meta_mutex));
   fprintf(stderr, "new dynamic metadata\n");
   if (dm->data_type != DM_JOINED_UC)
      {
      fprintf(stdout, "new_metadata=d%d:%sd%d:%sd%d:%sd9:%09dd9:%09dx\n", (int)strlen(dm->artist), dm->artist, (int)strlen(dm->title), dm->title, (int)strlen(dm->album), dm->album, dm->current_audio_context, dm->rbdelay);
      fprintf(stderr, "new_metadata=d%d:%sd%d:%sd%d:%sd9:%09dd9:%09dx\n", (int)strlen(dm->artist), dm->artist, (int)strlen(dm->title), dm->title, (int)strlen(dm->album), dm->album, dm->current_audio_context, dm->rbdelay);
      }
   else
      {
      fprintf(stderr, "send_metadata_update: utf16 chapter info not supported\n");
      }
   dm->data_type = DM_NONE_NEW;
   pthread_mutex_unlock(&(dm->meta_mutex));
   }
   
static void jackportread(const char *portname, const char *filter)
   {
   unsigned long flags = 0;
   const char *type = JACK_DEFAULT_AUDIO_TYPE;
   const char **ports;
   const jack_port_t *port = jack_port_by_name(g.client, portname);
   int i;

   if (!strcmp(filter, "inputs"))
      flags = JackPortIsInput;
   else
      {
      if (!strcmp(filter, "outputs"))
         flags = JackPortIsOutput;
      else
         if (!strcmp(filter, "midioutputs"))
            {
            flags = JackPortIsOutput;
            type = JACK_DEFAULT_MIDI_TYPE;
            }
      }

   ports = jack_get_ports(g.client, NULL, type, flags);
   fputs("jackports=", stdout);
   for (i = 0; ports && ports[i]; ++i)
      {
      if (i)
         fputs(" ", stdout);
      if (jack_port_connected_to(port, ports[i]))
         fputs("@", stdout);
      fputs(ports[i], stdout);
      }
   fputs("\n", stdout);
   fflush(stdout);
   if (ports)
      jack_free(ports);
   }
  
static struct mixer {
   const char **outport;
   int str_l_peak_db, str_r_peak_db;
   int str_l_rms_db, str_r_rms_db;
   float normrise, normfall;
   int fadeout_f;
   int flush_left, flush_right, flush_jingles, flush_interlude;
   int new_left_pause, new_right_pause;
   jack_nframes_t nframes;
   char *artist, *title, *album, *replaygain;
   double length;
   int use_dsp;
   char midi_output[MIDI_QUEUE_SIZE];
   char *our_sc_str_in_l;
   char *our_sc_str_in_r;
   int l;
   char *session_command;
   char *sc_client_name;
   } s;

static void mixer_cleanup()
   {
   free(eot_alarm_table);
   free_signallookup_table();
   free_dblookup_table();
   if (s.outport)
      jack_free(s.outport);
   free(s.our_sc_str_in_l);
   free(s.our_sc_str_in_r);
   mic_free_all(mics);
   peakfilter_destroy(str_pf_l);
   peakfilter_destroy(str_pf_r);
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
   }

void mixer_init(void)
   {
   sr = jack_get_sample_rate(g.client);
   jingles_samples_cutoff = sr / 12;            /* A twelfth of a second early */
   player_samples_cutoff = sr * 0.25;           /* for gapless playback */

   if(! ((plr_l = xlplayer_create(sr, RB_SIZE, "leftplayer", &g.app_shutdown)) &&
         (plr_r = xlplayer_create(sr, RB_SIZE, "rightplayer", &g.app_shutdown))))
      {
      printf("failed to create main player modules\n");
      exit(5);
      }
   
   if (!(plr_j = xlplayer_create(sr, RB_SIZE, "jinglesplayer", &g.app_shutdown)))
      {
      printf("failed to create jingles player module\n");
      exit(5);
      }

   if (!(plr_i = xlplayer_create(sr, RB_SIZE, "interludeplayer", &g.app_shutdown)))
      {
      printf("failed to create interlude player module\n");
      exit(5);
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
      for (unsigned i = 0; i < alarm_size ; i++) /* note it has a nice 2nd harmonic added */
         {
         eot_alarm_table[i] = 0.83F * sinf((i % (sr/900)) * 6.283185307F / (sr/900));
         eot_alarm_table[i] += 0.024F * sinf((i % (sr/900)) * 12.56637061F / (sr/900) + 3.141592654F / 4.0F);
         }
      }
         
   str_pf_l = peakfilter_create(115e-6f, sr);
   str_pf_r = peakfilter_create(115e-6f, sr);

   /* allocate microphone resources */
   mics = mic_init_all(atoi(getenv("mic_qty")), g.client);

   s.nframes = sr * 1.0f;
   lp_lc = ialloc(s.nframes);
   lp_rc = ialloc(s.nframes);
   rp_lc = ialloc(s.nframes);
   rp_rc = ialloc(s.nframes);
   jp_lc = ialloc(s.nframes);
   jp_rc = ialloc(s.nframes);
   ip_lc = ialloc(s.nframes);
   ip_rc = ialloc(s.nframes);
   lp_lcf = ialloc(s.nframes);
   lp_rcf = ialloc(s.nframes);
   rp_lcf = ialloc(s.nframes);
   rp_rcf = ialloc(s.nframes);
   jp_lcf = ialloc(s.nframes);
   jp_rcf = ialloc(s.nframes);
   ip_lcf = ialloc(s.nframes);
   ip_rcf = ialloc(s.nframes);

   if (!(lp_lc && lp_rc && rp_lc && rp_rc && jp_lc && jp_rc && ip_lc && ip_rc &&
       lp_lcf && lp_rcf && rp_lcf && rp_rcf && jp_lcf && jp_rcf && ip_lcf && ip_rcf))
      {
      fprintf(stderr, "Failed to allocate read-buffers for player_reader reading\n");
      exit(5);
      }
            
   atexit(mixer_cleanup);
   g.mixer_up = TRUE;
   }
      
int mixer_main()
   {
   if (!(kvp_parse(kvpdict, stdin)))
      return FALSE;

   if (!strcmp(action, "jackportread"))
      jackportread(jackport, jackfilter);

   void dis_connect(char *str, int (*fn)(jack_client_t *, const char *, const char *))
      {
      const char **jackports, **jp;
      
      if (!strcmp(action, str))
         {
         if (strlen(jackport2))
            {
            if (jack_port_flags(jack_port_by_name(g.client, jackport)) & JackPortIsOutput)
               fn(g.client, jackport, jackport2);
            else
               fn(g.client, jackport2, jackport);
            }
         else
            {
            /* do regular expression lookup of ports then disconnect them */
            if (!strcmp(str, "jackdisconnect"))
               {
               if ((jackports = jack_get_ports(g.client, jackport, NULL, 0L)))
                  {
                  for (jp = jackports; *jp; ++jp)
                     jack_port_disconnect(g.client, jack_port_by_name(g.client, *jp));

                  jack_free(jackports);
                  }
               }
            }
         }
      }
   dis_connect("jackconnect", jack_connect);
   dis_connect("jackdisconnect", jack_disconnect);

   if (!strcmp(action, "mp3status"))
      {
      fprintf(stdout, "IDJC: mp3=%d\n", mp3decode_cap());
      fflush(stdout);
      }

   if (!strcmp(action, "mic_control"))
      {
      mic_valueparse(mics[atoi(item_index)], mic_param);
      }

   if (!strcmp(action, "new_channel_mode_string"))
      {
      mic_set_role_all(mics, channel_mode_string);
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
      if (oggdecode_get_metainfo(oggpathname, &s.artist, &s.title, &s.album, &s.length, &s.replaygain))
         {
         fprintf(stdout, "OIR:ARTIST=%s\nOIR:TITLE=%s\nOIR:ALBUM=%s\nOIR:LENGTH=%f\nOIR:REPLAYGAIN_TRACK_GAIN=%s\nOIR:end\n", s.artist, s.title, s.album, s.length, s.replaygain);
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

   if (!strcmp(action, "mixstats"))
      {
      if(sscanf(mixer_string,
             ":%03d:%03d:%03d:%03d:%03d:%03d:%03d:%d:%1d%1d%1d%1d%1d:%1d%1d:%1d%1d%1d%1d:%1d:%1d:%1d:%1d:%1d:%f:%f:%1d:%f:%d:%d:%d:",
             &volume, &volume2, &crossfade, &jinglesvolume, &jinglesvolume2 , &interludevol, &mixbackvol, &jingles_playing,
             &left_stream, &left_audio, &right_stream, &right_audio, &stream_monitor,
             &s.new_left_pause, &s.new_right_pause, &s.flush_left, &s.flush_right, &s.flush_jingles, &s.flush_interlude, &simple_mixer, &eot_alarm_set, &mixermode, &s.fadeout_f, &main_play, &(plr_l->newpbspeed), &(plr_r->newpbspeed), &speed_variance, &dj_audio_level, &crosspattern, &s.use_dsp, &twodblimit) !=31)
         {
         fprintf(stderr, "mixer got bad mixer string\n");
         return TRUE;
         }
      eot_alarm_f |= eot_alarm_set;

      plr_l->fadeout_f = plr_r->fadeout_f = plr_j->fadeout_f = plr_i->fadeout_f = s.fadeout_f;

      if (s.use_dsp != using_dsp)
         using_dsp = s.use_dsp;

      if (s.new_left_pause != plr_l->pause)
         {
         if (s.new_left_pause)
            xlplayer_pause(plr_l);
         else
            xlplayer_unpause(plr_l);
         }
         
      if (s.new_right_pause != plr_r->pause)
         {
         if (s.new_right_pause)
            xlplayer_pause(plr_r);
         else
            xlplayer_unpause(plr_r);
         }
      }

   if (!strcmp(action, "requestlevels"))
      {
      /* make logarithmic values for the peak levels */
      s.str_l_peak_db = peak_to_log(peakfilter_read(str_pf_l));
      s.str_r_peak_db = peak_to_log(peakfilter_read(str_pf_r));
      /* set reply values for a totally blank signal */
      s.str_l_rms_db = s.str_r_rms_db = 120;
      /* compute the rms values */
      if (str_l_meansqrd)
         s.str_l_rms_db = (int) fabs(level2db(sqrt(str_l_meansqrd)));
      if (str_r_meansqrd)
         s.str_r_rms_db = (int) fabs(level2db(sqrt(str_r_meansqrd)));
         
      /* send the meter and other stats to the main app */
      mic_stats_all(mics);

      /* forward any MIDI commands that have been queued since last time */
      pthread_mutex_lock(&midi_mutex);
      s.midi_output[0]= '\0';
      if (midi_nqueued>0) /* exclude leading `,`, include trailing `\0` */
         memcpy(s.midi_output, midi_queue+1, midi_nqueued*sizeof(char));
      midi_queue[0]= '\0';
      midi_nqueued= 0;
      pthread_mutex_unlock(&midi_mutex);

      if (sig_recent_usr1())
         s.session_command = "save_L1";
      else
         s.session_command = "";

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
                "silence_l=%f\n"
                "silence_r=%f\n"
                "session_command=%s\n"
                "end\n",
                s.str_l_peak_db, s.str_r_peak_db,
                s.str_l_rms_db, s.str_r_rms_db,
                jingles_audio_f | (plr_j->current_audio_context & 0x1),
                plr_l->play_progress_ms / 1000,
                plr_r->play_progress_ms / 1000,
                plr_l->have_data_f | (plr_l->current_audio_context & 0x1),
                plr_r->have_data_f | (plr_r->current_audio_context & 0x1),
                plr_i->have_data_f | (plr_i->current_audio_context & 0x1),
                left_peak > 0.001F || left_peak < 0.0F || plr_l->pause,
                right_peak > 0.001F || right_peak < 0.0F || plr_r->pause,
                plr_l->current_audio_context,
                plr_r->current_audio_context,
                plr_j->current_audio_context,
                plr_i->current_audio_context,
                left_audio_runout && (!(plr_l->current_audio_context & 0x1)),
                right_audio_runout && (!(plr_r->current_audio_context & 0x1)),
                plr_l->dynamic_metadata.data_type,
                plr_r->dynamic_metadata.data_type,
                s.midi_output,
                plr_l->silence,
                plr_r->silence,
                s.session_command);
                
      /* tell the jack mixer it can reset its vu stats now */
      reset_vu_stats_f = TRUE;
      left_peak = right_peak = -1.0F;
      if (plr_l->dynamic_metadata.data_type)
         send_metadata_update(&(plr_l->dynamic_metadata));
      if (plr_r->dynamic_metadata.data_type)
         send_metadata_update(&(plr_r->dynamic_metadata));
      fflush(stdout);
      }
      
   return TRUE;
   }
