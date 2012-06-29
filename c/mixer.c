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
#include <jack/session.h>
#include <getopt.h>
#include <string.h>
#include <fcntl.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <signal.h>
#include <locale.h>
#include <limits.h>

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

/* the sample rate reported by JACK -- initial value to prevent divide by 0 */
unsigned long sr = 44100;

/* values of the volume sliders in the GUI */
static int volume, volume2, crossfade, jinglesvolume, jinglesvolume2, interludevol, mixbackvol, crosspattern;
/* back and forth status indicators re. jingles */
static int jingles_playing;
/* the player audio feed buttons */
static int left_stream = 1, left_audio = 1, right_stream = 1, right_audio = 1;
static int inter_stream = 1, inter_audio = 0;
/* status variables for the button cluster in lower right of main window */
static int mic_on, mixermode = NO_PHONE;
/* simple mixer mode: uses less space on the screen and less cpu as well */
static int simple_mixer;
/* currentvolumes are used to implement volume smoothing */
static int current_crossfade, currentmixbackvol, current_crosspattern;
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
/* flag to indicate if audio is routed via dsp interface */
static int using_dsp;
/* handles for microphone */
static struct mic **mics;
/* peakfilter handles for stream peak */
static struct peakfilter *str_pf_l, *str_pf_r;
/* counts the number of times port connections have changed */
static unsigned int port_connection_count;
/* counts the number of times port connection counts have been reported */
static unsigned int port_reports;

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
            
/* media player mixback level for when in RedPhone mode */
static sample_t mb_lc_aud = 1.0, mb_rc_aud = 1.0;
static sample_t current_headroom;      /* the amount of mic headroom being applied */
static sample_t *eot_alarm_table;      /* the wave table for the DJ alarm */
            
static char midi_queue[MIDI_QUEUE_SIZE];
static size_t midi_nqueued= 0;
static pthread_mutex_t midi_mutex;

static struct xlplayer *plr_l, *plr_r, *plr_j, *plr_i; /* player instance stuctures */
static struct xlplayer *players[5];

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
static char *effect_ix;
static char *session_event_string, *session_commandline;

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
            { "EFCT", &effect_ix, NULL },
            { "ACTN", &action, NULL },                   /* Action to take */
            { "session_event", &session_event_string, NULL },
            { "session_command", &session_commandline, NULL },
            { "", NULL, NULL }};

static void custom_jack_port_connect_callback(jack_port_id_t a, jack_port_id_t b, int connect, void *arg)
    {
    ++port_connection_count;
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
    static sample_t cross_left = 1.0F, cross_right = 0.0F;
    sample_t mic_target, diff;
    static float interlude_autovol = -128.0F, old_autovol = -128.0F;
    float vol;
    float xprop, yprop;
    const float bias = 0.35386f;
    const float pat3 = 0.9504953575f;

    xlplayer_smoothing_process_all(players);

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

    plr_l->cf_l_gain = cross_left;
    plr_l->cf_r_gain = cross_left;
    plr_r->cf_l_gain = cross_right;
    plr_r->cf_r_gain = cross_right;

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
        if (interlude_autovol > 0.0f)
            interlude_autovol = 0.0f;
        }   

    plr_i->cf_l_gain = plr_i->cf_r_gain = powf(10.0f, interlude_autovol * 0.05f);

    if (mixbackvol != currentmixbackvol)
        {
        if (mixbackvol > currentmixbackvol)
            currentmixbackvol++;
        else
            currentmixbackvol--;
        mb_lc_aud = mb_rc_aud = powf(10.0F, (currentmixbackvol - 127) * 0.0141F);
        }

    /* mic headroom application */
    mic_target = -headroom_db;
    if ((diff = mic_target - current_headroom))
        {
        current_headroom += diff * 1600.0f / (sr * powf(headroom_db + 10.0f, 0.93f));
        if (fabsf(diff) < 0.000001F)
            current_headroom = mic_target;
        }

    /* ducking effect reduces as the player volume is backed off */
    if (jingles_playing)
        vol = plr_j->volume.level * 0.06666666F;
    else
        vol = (plr_l->volume.level - (plr_l->volume.level - plr_r->volume.level) / 2.0f) * 0.06666666f;
    dfmod = vol * vol + 1.0f;
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
    sample_t *plolp, *plorp, *prolp, *prorp, *piolp, *piorp, *pjolp, *pjorp;
    sample_t *plilp, *plirp, *prilp, *prirp, *piilp, *piirp, *pjilp, *pjirp;
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
        
        la_buffer = lap = (sample_t *) jack_port_get_buffer(p->dj_out_l, nframes);
        ra_buffer = rap = (sample_t *) jack_port_get_buffer(p->dj_out_r, nframes);
        ls_buffer = lsp = (sample_t *) jack_port_get_buffer(p->str_out_l, nframes);
        rs_buffer = rsp = (sample_t *) jack_port_get_buffer(p->str_out_r, nframes);
        lps_buffer = lpsp = (sample_t *) jack_port_get_buffer(p->voip_out_l, nframes);
        rps_buffer = rpsp = (sample_t *) jack_port_get_buffer(p->voip_out_r, nframes);
        lprp = (sample_t *) jack_port_get_buffer(p->voip_in_l, nframes);
        rprp = (sample_t *) jack_port_get_buffer(p->voip_in_r, nframes);
        dolp = (sample_t *) jack_port_get_buffer(p->dsp_out_l, nframes);
        dorp = (sample_t *) jack_port_get_buffer(p->dsp_out_r, nframes);
        dilp = (sample_t *) jack_port_get_buffer(p->dsp_in_l, nframes);
        dirp = (sample_t *) jack_port_get_buffer(p->dsp_in_r, nframes);
        plolp = (sample_t *) jack_port_get_buffer(p->pl_out_l, nframes);
        plorp = (sample_t *) jack_port_get_buffer(p->pl_out_r, nframes);
        prolp = (sample_t *) jack_port_get_buffer(p->pr_out_l, nframes);
        prorp = (sample_t *) jack_port_get_buffer(p->pr_out_r, nframes);
        piolp = (sample_t *) jack_port_get_buffer(p->pi_out_l, nframes);
        piorp = (sample_t *) jack_port_get_buffer(p->pi_out_r, nframes);
        pjolp = (sample_t *) jack_port_get_buffer(p->pj_out_l, nframes);
        pjorp = (sample_t *) jack_port_get_buffer(p->pj_out_r, nframes);
        plilp = (sample_t *) jack_port_get_buffer(p->pl_in_l, nframes);
        plirp = (sample_t *) jack_port_get_buffer(p->pl_in_r, nframes);
        prilp = (sample_t *) jack_port_get_buffer(p->pr_in_l, nframes);
        prirp = (sample_t *) jack_port_get_buffer(p->pr_in_r, nframes);
        piilp = (sample_t *) jack_port_get_buffer(p->pi_in_l, nframes);
        piirp = (sample_t *) jack_port_get_buffer(p->pi_in_r, nframes);
        pjilp = (sample_t *) jack_port_get_buffer(p->pj_in_l, nframes);
        pjirp = (sample_t *) jack_port_get_buffer(p->pj_in_r, nframes);
    }
            
    /* resets the running totals for the vu meter stats */      
    if (reset_vu_stats_f)
        {
        str_l_tally = str_r_tally = 0.0;
        rms_tally_count = 0;
        reset_vu_stats_f = FALSE;
        }

    mic_process_start_all(mics, nframes);
    xlplayer_read_start_all(players, nframes);

    /* there are four mixer modes and the only seemingly efficient way to do them is */
    /* to basically copy a lot of code four times over hence the huge size */
    if (simple_mixer == FALSE && mixermode == NO_PHONE)  /* Fully featured mixer code */
        {
        memset(lps_buffer, 0, nframes * sizeof (sample_t)); /* send silence to VOIP */
        memset(rps_buffer, 0, nframes * sizeof (sample_t));
        for(samples_todo = nframes; samples_todo--; lap++, rap++, lsp++, rsp++,
                    dilp++, dirp++, dolp++, dorp++,
                    plolp++, plorp++, prolp++, prorp++, piolp++, piorp++, pjolp++, pjorp++,
                    plilp++, plirp++, prilp++, prirp++, piilp++, piirp++, pjilp++, pjirp++)
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

            #define COMMON_MIX() \
                do { \
                xlplayer_read_next_all(players); \
                \
                /* player audio routing through jack ports */ \
                *plolp = plr_l->ls; \
                *plorp = plr_l->rs; \
                *prolp = plr_r->ls; \
                *prorp = plr_r->rs; \
                *piolp = plr_i->ls; \
                *piorp = plr_i->rs; \
                *pjolp = plr_j->ls; \
                *pjorp = plr_j->rs; \
                plr_l->ls = *plilp; \
                plr_l->rs = *plirp; \
                plr_r->ls = *prilp; \
                plr_r->rs = *prirp; \
                plr_i->ls = *piilp; \
                plr_i->rs = *piirp; \
                plr_j->ls = *pjilp; \
                plr_j->rs = *pjirp; \
                } while(0)
                
            COMMON_MIX();
            
            /* the stream mix */
            *dolp = (plr_l->ls_str + plr_r->ls_str + plr_j->ls_str) * df + lc_s_micmix + lc_s_auxmix + plr_i->ls_str;
            *dorp = (plr_l->rs_str + plr_r->rs_str + plr_j->rs_str) * df + rc_s_micmix + rc_s_auxmix + plr_i->rs_str;
            
            /* hard limit the levels if they go outside permitted limits */
            /* note this is not the same as clipping */
            compressor_gain = db2level(limiter(&stream_limiter, *dolp, *dorp));
            *dolp *= compressor_gain;
            *dorp *= compressor_gain;

            #define COMMON_MIX2() \
                do  { \
                    if (using_dsp) \
                        { \
                        *lsp = *dilp; \
                        *rsp = *dirp; \
                        } \
                    else \
                        { \
                        *lsp = *dolp; \
                        *rsp = *dorp; \
                        } \
                } while(0)
                
            COMMON_MIX2();

            if (stream_monitor == FALSE)
                {
                *lap = (plr_l->ls_aud + plr_r->ls_aud + plr_j->ls_aud) * df + d_micmix + lc_s_auxmix + plr_i->ls_aud;
                *rap = (plr_l->rs_aud + plr_r->rs_aud + plr_j->rs_aud) * df + d_micmix + rc_s_auxmix + plr_i->rs_aud;
                compressor_gain = db2level(limiter(&audio_limiter, *lap, *rap));
                *lap *= compressor_gain;
                *rap *= compressor_gain;
                }
            else
                {
                *lap = *lsp;  /* allow the DJ to hear the mix that the listeners are hearing */
                *rap = *rsp;
                }
                
            #define COMMON_MIX3() \
                do  { \
                    if (eot_alarm_f) /* mix in the end-of-track alarm tone */ \
                        { \
                        if (alarm_index >= alarm_size) \
                            { \
                            alarm_index = 0; \
                            eot_alarm_f = 0; \
                            } \
                        else \
                            { \
                            *lap += eot_alarm_table[alarm_index]; \
                            *lap *= 0.5; \
                            *rap += eot_alarm_table[alarm_index]; \
                            *rap *= 0.5; \
                            alarm_index++; \
                            } \
                        } \
                    \
                    /* apply dj audio sound level */ \
                    *lap *= dj_audio_gain; \
                    *rap *= dj_audio_gain; \
                    \
                    /* make note of the peak volume levels */ \
                    peakfilter_process(str_pf_l, *lsp); \
                    peakfilter_process(str_pf_r, *rsp); \
                    \
                    /* used for rms calculation */ \
                    str_l_tally += *lsp * *lsp; \
                    str_r_tally += *rsp * *rsp; \
                    rms_tally_count++; \
                }while(0)
                
            COMMON_MIX3();
            }
        str_l_meansqrd = str_l_tally/rms_tally_count;
        str_r_meansqrd = str_r_tally/rms_tally_count;
        }
    else
        if (simple_mixer == FALSE && mixermode == PHONE_PUBLIC)
            {
            for(samples_todo = nframes; samples_todo--; lap++, rap++, lsp++, rsp++,
                    lpsp++, rpsp++, lprp++, rprp++, dilp++, dirp++, dolp++, dorp++,
                    plolp++, plorp++, prolp++, prorp++, piolp++, piorp++, pjolp++, pjorp++,
                    plilp++, plirp++, prilp++, prirp++, piilp++, piirp++, pjilp++, pjirp++)


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

                COMMON_MIX();

                /* do the phone send mix */
                *lpsp = lc_s_micmix + plr_j->ls_str;
                *rpsp = rc_s_micmix + plr_j->rs_str;

                /* The main mix */
                *dolp = (plr_l->ls_str + plr_r->ls_str) * df + *lprp + *lpsp + lc_s_auxmix + plr_i->ls_str;
                *dorp = (plr_l->rs_str + plr_r->rs_str) * df + *rprp + *rpsp + rc_s_auxmix + plr_i->rs_str;
                
                compressor_gain = db2level(limiter(&phone_limiter, *lpsp, *rpsp));
                *lpsp *= compressor_gain;
                *rpsp *= compressor_gain;

                /* hard limit the levels if they go outside permitted limits */
                /* note this is not the same as clipping */
                compressor_gain = db2level(limiter(&stream_limiter, *dolp, *dorp));
                *dolp *= compressor_gain;
                *dorp *= compressor_gain;

                COMMON_MIX2();

                if (stream_monitor == FALSE)
                    {
                    *lap = (plr_l->ls_aud + plr_r->ls_aud) * df + *lprp + lc_s_auxmix + plr_i->ls_aud + d_micmix + plr_j->ls_str;
                    *rap = (plr_l->rs_aud + plr_r->rs_aud) * df + *rprp + rc_s_auxmix + plr_i->rs_aud + d_micmix + plr_j->rs_str;
                    compressor_gain = db2level(limiter(&audio_limiter, *lap, *rap));
                    *lap *= compressor_gain;
                    *rap *= compressor_gain;
                    }
                else
                    {
                    *lap = *lsp;  /* allow the DJ to hear the mix that the listeners are hearing */
                    *rap = *rsp;
                    }
                    
                COMMON_MIX3();
                }
            str_l_meansqrd = str_l_tally/rms_tally_count;
            str_r_meansqrd = str_r_tally/rms_tally_count;
            }
        else
            if (simple_mixer == FALSE && mixermode == PHONE_PRIVATE && mic_on == 0)
                {
                for(samples_todo = nframes; samples_todo--; lap++, rap++, lsp++, rsp++,
                    lpsp++, rpsp++, lprp++, rprp++, dilp++, dirp++, dolp++, dorp++,
                    plolp++, plorp++, prolp++, prorp++, piolp++, piorp++, pjolp++, pjorp++,
                    plilp++, plirp++, prilp++, prirp++, piilp++, piirp++, pjilp++, pjirp++)
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

                    COMMON_MIX();
                    
                    /* the main mix */
                    *dolp = plr_l->ls_str + plr_r->ls_str + lc_s_auxmix + plr_i->ls_str;
                    *dorp = plr_l->rs_str + plr_r->rs_str + rc_s_auxmix + plr_i->rs_str;
                    
                    /* hard limit the levels if they go outside permitted limits */
                    /* note this is not the same as clipping */
                    compressor_gain = db2level(limiter(&stream_limiter, *dolp, *dorp));
                    *dolp *= compressor_gain;
                    *dorp *= compressor_gain;
                    
                    /* the mix the voip listeners receive */
                    *lpsp = (*dolp * mb_lc_aud) + plr_j->ls_aud + lc_s_micmix;
                    *rpsp = (*dorp * mb_lc_aud) + plr_j->rs_aud + rc_s_micmix;
                    compressor_gain = db2level(limiter(&phone_limiter, *lpsp, *rpsp));
                    *lpsp *= compressor_gain;
                    *rpsp *= compressor_gain;
                    
                    COMMON_MIX2();

                    if (stream_monitor == FALSE) /* the DJ can hear the VOIP phone call */
                        {
                        *lap = (*lsp * mb_lc_aud) + plr_j->ls_aud + d_micmix + (lc_s_auxmix *mb_lc_aud) + *lprp;
                        *rap = (*rsp * mb_lc_aud) + plr_j->rs_aud + d_micmix + (rc_s_auxmix *mb_rc_aud) + *rprp;
                        compressor_gain = db2level(limiter(&audio_limiter, *lap, *rap));
                        *lap *= compressor_gain;
                        *rap *= compressor_gain;
                        }
                    else
                        {
                        *lap = *lsp;  /* allow the DJ to hear the mix that the listeners are hearing */
                        *rap = *rsp;
                        }
                        
                    COMMON_MIX3();
                    }
                str_l_meansqrd = str_l_tally/rms_tally_count;
                str_r_meansqrd = str_r_tally/rms_tally_count;
                }
            else
                if (simple_mixer == FALSE && mixermode == PHONE_PRIVATE) /* note: mic is on */
                    {
                    for(samples_todo = nframes; samples_todo--; lap++, rap++, lsp++, rsp++, 
                            lpsp++, rpsp++, dilp++, dirp++, dolp++, dorp++,
                            plolp++, plorp++, prolp++, prorp++, piolp++, piorp++, pjolp++, pjorp++,
                            plilp++, plirp++, prilp++, prirp++, piilp++, piirp++, pjilp++, pjirp++)
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

                        COMMON_MIX();

                        /* the main mix */
                        *dolp = (plr_l->ls_str + plr_r->ls_str + plr_j->ls_str) * df + lc_s_micmix + lc_s_auxmix + plr_i->ls_str;
                        *dorp = (plr_l->rs_str + plr_r->rs_str + plr_j->rs_str) * df + rc_s_micmix + rc_s_auxmix + plr_i->rs_str;
                        
                        /* hard limit the levels if they go outside permitted limits */
                        /* note this is not the same as clipping */
                        compressor_gain = db2level(limiter(&stream_limiter, *dolp, *dorp));
                        *dolp *= compressor_gain;
                        *dorp *= compressor_gain;
                        
                        *lpsp = *dolp * mb_lc_aud;    /* voip callers get stream mix at a certain volume */ 
                        *rpsp = *dorp * mb_rc_aud;

                        COMMON_MIX2();

                        if (stream_monitor == FALSE)
                            {
                            *lap = (plr_l->ls_aud + plr_r->ls_aud + plr_j->ls_aud) * df + d_micmix + lc_s_auxmix + plr_i->ls_aud;
                            *rap = (plr_l->rs_aud + plr_r->rs_aud + plr_j->rs_aud) * df + d_micmix + rc_s_auxmix + plr_i->rs_aud;
                            compressor_gain = db2level(limiter(&audio_limiter, *lap, *rap));
                            *lap *= compressor_gain;
                            *rap *= compressor_gain;
                            }
                        else
                            {
                            *lap = *lsp;  /* allow the DJ to hear the mix that the listeners are hearing */
                            *rap = *rsp;
                            }
                            
                        COMMON_MIX3();
                        }
                    str_l_meansqrd = str_l_tally/rms_tally_count;
                    str_r_meansqrd = str_r_tally/rms_tally_count;
                    }
                else
                    if (simple_mixer == TRUE)
                        {
                        int la = left_audio;
                        int ls = left_stream;

                        if (dj_audio_level != current_dj_audio_level)
                            {
                            current_dj_audio_level = dj_audio_level;
                            dj_audio_gain = db2level(dj_audio_level);
                            }
                        
                        if (la || ls)
                            {
                            samples_todo = nframes;
                            while (samples_todo--)
                                {
                                xlplayer_read_next(plr_l);                                    
                                if (la)
                                    {
                                    *lap++ = plr_l->ls * dj_audio_gain;
                                    *rap++ = plr_l->rs * dj_audio_gain;
                                    }
                                if (ls)
                                    {
                                    *lsp++ = plr_l->ls;
                                    *rsp++ = plr_l->rs;
                                    }
                                }
                            }
                            
                        if (!la)
                            {
                            memset(la_buffer, 0, nframes * sizeof (sample_t));
                            memset(ra_buffer, 0, nframes * sizeof (sample_t));
                            }
                        if (!ls)
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
   
static void jackportread(const char *portname, const char *filter)
    {
    unsigned long flags = 0;
    const char *type = JACK_DEFAULT_AUDIO_TYPE;
    const char **ports, **cons;
    const jack_port_t *port = jack_port_by_name(g.client, portname);
    int i, j;

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

    cons = jack_port_get_all_connections(g.client, port);
    ports = jack_get_ports(g.client, NULL, type, flags);
    fputs("jackports=", stdout);
    if (ports)
        for (i = 0; ports[i]; ++i)
            {
            if (i)
                fputs(" ", stdout);
                
            /* connected ports are prefaced with an @ character */
            if (cons)
                for (j = 0; cons[j]; ++j)
                    if (!(strcmp(cons[j], ports[i])))
                        {
                        putchar('@');
                        break;
                        }
            
            fputs(ports[i], stdout);
            }

    putchar('\n');
    fflush(stdout);

    if (cons)
        jack_free(cons);

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
    int new_left_pause, new_right_pause, new_inter_pause;
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
    int n = 0;

    if(! ((players[n++] = plr_l = xlplayer_create(sr, RB_SIZE, "left", &g.app_shutdown, &volume, 0, &left_stream, &left_audio, 0.25f)) &&
            (players[n++] = plr_r = xlplayer_create(sr, RB_SIZE, "right", &g.app_shutdown, &volume2, 0, &right_stream, &right_audio, 0.25f))))
        {
        fprintf(stderr, "failed to create main player modules\n");
        exit(5);
        }
    
    if (!(players[n++] = plr_j = xlplayer_create(sr, RB_SIZE, "jingles", &g.app_shutdown, NULL, 0, NULL, NULL, 1.0f / 12.0f)))
        {
        fprintf(stderr, "failed to create jingles player module\n");
        exit(5);
        }

    if (!(players[n++] = plr_i = xlplayer_create(sr, RB_SIZE, "interlude", &g.app_shutdown, &interludevol, 0, &inter_stream, &inter_audio, 0.25f)))
        {
        fprintf(stderr, "failed to create interlude player module\n");
        exit(5);
        }
    plr_i->cf_aud = 1;  /* crossfader values to apply in dj audio -- the crossfader interface is used to implement the soft fade in/out */

    players[n++] = NULL;
    if (n != sizeof players / sizeof players[0])
        {
        fprintf(stderr, "players array is the wrong size\n");
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
        for (unsigned i = 0; i < alarm_size ; i++)
            {
            eot_alarm_table[i] = 0.83F * sinf((i % (sr/900)) * 6.283185307F / (sr/900));
            eot_alarm_table[i] += 0.024F * sinf((i % (sr/900)) * 12.56637061F / (sr/900) + 3.141592654F / 4.0F);
            }
        }
            
    str_pf_l = peakfilter_create(115e-6f, sr);
    str_pf_r = peakfilter_create(115e-6f, sr);

    /* allocate microphone resources */
    mics = mic_init_all(atoi(getenv("mic_qty")), g.client);
        
    jack_set_port_connect_callback(g.client, custom_jack_port_connect_callback, NULL);
                
    atexit(mixer_cleanup);
    g.mixer_up = TRUE;
    }
        
int mixer_main()
    {
    unsigned int lead, ports_diff;
    jack_session_event_t *session_event;
    
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

    if (!strcmp(action, "session_reply"))
        {
        sscanf(session_event_string, "%p", &session_event);
        session_event->command_line = session_commandline;
        /* Transfer of ownership of heap allocated string. */
        session_commandline = NULL;
        jack_session_reply(g.client, session_event);
        jack_session_event_free(session_event);
        /* Unblock the user interface which is waiting on a reply. */
        fprintf(stdout, "session event handled\n");
        fflush(stdout);
        }

    if (!strcmp(action, "playeffect"))
        {
        fprintf(stderr, "play effect placeholder for effect %s\n", effect_ix);
        }

    if (!strcmp(action, "stopeffect"))
        {
        fprintf(stderr, "stop effect placeholder for effect %s\n", effect_ix);
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

    if (!strcmp(action, "fademode_interlude"))
        plr_i->fade_mode = atoi(fade_mode);

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
    if (!strcmp(action, "playinterlude"))
        {
        fprintf(stdout, "context_id=%d\n", xlplayer_play(plr_i, playerpathname, atoi(seek_s), atoi(size), atof(rg_db)));
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
    if (!strcmp(action, "playnoflushinterlude"))
        {
        fprintf(stdout, "context_id=%d\n", xlplayer_play_noflush(plr_i, playerpathname, atoi(seek_s), atoi(size), atof(rg_db)));
        fflush(stdout);
        }
 
    if (!strcmp(action, "playmanyjingles"))
        {
        fprintf(stdout, "context_id=%d\n", xlplayer_playmany(plr_j, playerplaylist, loop[0]=='1'));
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
                 ":%03d:%03d:%03d:%03d:%03d:%03d:%03d:%d:%1d%1d%1d%1d%1d:%1d"
                 "%1d:%1d%1d%1d%1d:%1d:%1d:%1d:%1d:%1d:%f:%f:%1d:%f:%d:%d:"
                 "%1d:%1d:%1d:",
                 &volume, &volume2, &crossfade, &jinglesvolume, &jinglesvolume2 , &interludevol, &mixbackvol, &jingles_playing,
                 &left_stream, &left_audio, &right_stream, &right_audio, &stream_monitor,
                 &s.new_left_pause, &s.new_right_pause, &s.flush_left, &s.flush_right, &s.flush_jingles, &s.flush_interlude,
                 &simple_mixer, &eot_alarm_set, &mixermode, &s.fadeout_f, &main_play, &(plr_l->newpbspeed), &(plr_r->newpbspeed),
                 &speed_variance, &dj_audio_level, &crosspattern, &s.use_dsp, &s.new_inter_pause,
                 &inter_stream, &inter_audio) !=33)
            {
            fprintf(stderr, "mixer got bad mixer string\n");
            return TRUE;
            }
        eot_alarm_f |= eot_alarm_set;

        plr_l->fadeout_f = plr_r->fadeout_f = plr_j->fadeout_f = plr_i->fadeout_f = s.fadeout_f;
        plr_l->use_sv = plr_r->use_sv = speed_variance;

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

        if (s.new_inter_pause != plr_i->pause)
            {
            if (s.new_inter_pause)
                xlplayer_pause(plr_i);
            else
                xlplayer_unpause(plr_i);
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
            {
            if (g.session_event_rb && jack_ringbuffer_read_space(g.session_event_rb) >= sizeof session_event)
                {
                jack_ringbuffer_read(g.session_event_rb, (char *)&session_event, sizeof session_event);
                switch (session_event->type) {
                    case JackSessionSave:
                        s.session_command = "save_JACK";
                        break;
                    case JackSessionSaveAndQuit:
                        s.session_command = "saveandquit_JACK";
                        break;
                    case JackSessionSaveTemplate:
                        s.session_command = "savetemplate_JACK";
                    }

                fprintf(stdout, "session_event=%p\n"
                                "session_directory=%s\n"
                                "session_uuid=%s\n",
                                 session_event,
                                 session_event->session_dir,
                                 session_event->client_uuid);
                }
            else
                s.session_command = "";
            }

        lead = port_connection_count;
        if (lead - port_reports > UINT_MAX << 1)
            ports_diff = UINT_MAX - lead + port_reports + 1;    /* handle wrap */
        else
            ports_diff = lead - port_reports;

        xlplayer_stats_all(players);

        fprintf(stdout, 
                    "str_l_peak=%d\nstr_r_peak=%d\n"
                    "str_l_rms=%d\nstr_r_rms=%d\n"
                    "midi=%s\n"
                    "session_command=%s\n"
                    "ports_connections_changed=%d\n"
                    "effects_playing=%d\n"
                    "end\n",
                    s.str_l_peak_db, s.str_r_peak_db,
                    s.str_l_rms_db, s.str_r_rms_db,
                    s.midi_output,
                    s.session_command,
                    ports_diff,
                    3 /* placeholder for effects playing */);

        if (ports_diff)
            {
            port_reports += ports_diff;
            fprintf(stderr, "%d JACK port connection(s) changed\n", ports_diff);
            }
            
        /* tell the jack mixer it can reset its vu stats now */
        reset_vu_stats_f = TRUE;
        fflush(stdout);
        }
        
    return TRUE;
    }
