/*
#   mic.c: wrapper for AGC and provides mixing to stereo
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

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

#include "mic.h"
#include "dbconvert.h"
#include "main.h"

#define FALSE 0
#define TRUE (!FALSE)

static const float peak_init = 4.46e-7f; /* -127dB */

static void calculate_gain_values(struct mic *self)
    {
    self->mgain = powf(10.0f, self->gain / 20.0f);
    if (self->pan_active)
        {
        self->lgain = cosf((float)self->pan / 63.66197724f);
        self->rgain = sinf((float)self->pan / 63.66197724f);
        }
    else
        self->lgain = self->rgain = 1.0f;
    }

static void mic_process_start(struct mic *self, jack_nframes_t nframes)
    {
    int mode_request = self->mode_request;   
        
    /* mic mode changes are handled here */
    if (mode_request != self->mode)
        {
        if (self->mode == 0)
            fprintf(stderr, "activated ch %d\n", self->id);
            
        if (self->mode == 2)
            {
            fprintf(stderr, "leaving fully processed mode, ch %d\n", self->id);
            agc_reset(self->agc);
            }

        if (mode_request == 3)
            {
            fprintf(stderr, "entering stereo mode, ch %d\n", self->id);
            self->host = self->partner;
            agc_set_partnered_mode(self->agc, TRUE);
            }

        if (self->mode == 3)
            {
            fprintf(stderr, "leaving stereo mode, ch %d\n", self->id);
            self->host = self;
            agc_set_partnered_mode(self->agc, FALSE);
            }

        if (mode_request == 0)
            {
            fprintf(stderr, "deactivated ch %d\n", self->id);
            self->open = 0;
            self->mute = 0.0f;
            self->unp = self->unpm = self->unpmdj = 0.0f;
            self->lc = self->rc = self->lrc = self->lcm = self->rcm = 0.0f;
            self->peak = peak_init;
            }

        self->mode = mode_request;
        }

    if (self->mode)
        {
        /* initialisation for later mic stages */
        self->nframes = nframes;
        self->jadp = jack_port_get_buffer(self->jack_port, nframes);
        }
    }

void mic_process_start_all(struct mic **mics, jack_nframes_t nframes)
    {
    while (*mics)   
        mic_process_start(*mics++, nframes);
    }

static void mic_process_stage1(struct mic *self)
    {
    float sample = *self->jadp++;
    
    if (isunordered(sample, sample))
        sample = 0.0f;

    if (self->mode == 3)
        sample *= self->rel_igain * self->rel_gain;
    self->sample = sample;
    }

static void mic_process_stage2(struct mic *self)
    {
    struct mic *host = self->host;
    float sample = self->sample * host->igain;

    /* mic open/close perform fade */
    if (self->open && self->mute < 0.999999f)
        self->mute += (1.0f - self->mute) * 26.46f / self->sample_rate;
    else if (!self->open && self->mute > 0.0000004f)
        self->mute -= self->mute * 12.348f / self->sample_rate;
    else
        self->mute = self->open ? 1.0f : 0.0f;
     
    /* unprocessed audio */  
    self->unp = sample * host->mgain;
    /* unprocessed audio + mute */
    self->unpm = self->unp * self->mute;
    /* unprocessed audio + mute for the DJ mix */
    self->unpmdj = self->unpm * host->djmute;

    if (host->mode == 2)
        agc_process_stage1(self->agc, sample);
    }

static void mic_process_stage3(struct mic *self)
    {
    /* agc side-channel stuff */
    if (self->host->mode == 2)
        agc_process_stage2(self->agc, self->mute < 0.75f);
    }

static void mic_process_stage4(struct mic *self)
    {
    float m = self->mic_g;
    float a = self->aux_g;
    struct mic *host = self->host;   
        
    if (host->mode == 2)
        self->lrc = agc_process_stage3(self->agc);
    else
        self->lrc = self->unp;

    /* left and right channel audio no mute - could be procesesed or not */
    self->lc = self->lrc * self->lgain;
    self->rc = self->lrc * self->rgain;
    /* the same but with muting */
    self->lcm = self->lc * self->mute;
    self->rcm = self->rc * self->mute;
    
    /* record peak levels */
    float l = fabsf(self->lrc);
    if (l > self->peak)
        self->peak = l;
        
    self->munp = self->unp * m;
    self->munpm = self->unpm * m;
    self->munpmdj = self->unpmdj * m;
    self->mlrc = self->lrc * m;
    self->mlc = self->lc * m;
    self->mrc = self->rc * m;
    self->mlcm = self->lcm * m;
    self->mrcm = self->rcm * m;

    self->aunp = self->unp * a;
    self->aunpm = self->unpm * a;
    self->aunpmdj = self->unpmdj * a;
    self->alrc = self->lrc * a;
    self->alc = self->lc * a;
    self->arc = self->rc * a;
    self->alcm = self->lcm * a;
    self->arcm = self->rcm * a;
    }

float mic_process_all(struct mic **mics)
    {
    static void (*mic_process[])(struct mic *) = {mic_process_stage1,
            mic_process_stage2, mic_process_stage3, mic_process_stage4, NULL };
    void (**mpp)(struct mic *);
    struct mic **mp;
    float df, agcdf;   

    /* processing broken up into stages to allow state sharing between
     * stereo pairs of microphones
     */
    for (mpp = mic_process; *mpp; mpp++)
        for (mp = mics; *mp; mp++)
            if ((*mp)->mode)
                (*mpp)(*mp);
            
    /* ducking factor tally - lowest wins */
    for (df = 1.0f, mp = mics; *mp; mp++)
        df = (df > (agcdf = agc_get_ducking_factor((*mp)->agc))) ? agcdf : df;
          
    return df;
    }

static int mic_getpeak(struct mic *self)
    {
    int peakdb;
    
    peakdb = (int)level2db(self->peak);
    self->peak = peak_init;
    return (peakdb < 0) ? peakdb : 0;
    }

static void mic_stats(struct mic *self)
    {
    int red, yellow, green;
    
    agc_get_meter_levels(self->host->agc, &red, &yellow, &green);
    fprintf(g.out, "mic_%d_levels=%d,%d,%d,%d\n", self->id,
                                    mic_getpeak(self), red, yellow, green);
    }

void mic_stats_all(struct mic **mics)
    {
    while (*mics)
        mic_stats(*mics++);
    }

static void mic_set_role(struct mic *self, int role)
    {
    if (role == 'm')
        {
        self->mic_g = 1.0f;
        self->aux_g = 0.0f;
        }
    else // if role == 'a'
        {
        self->mic_g = 0.0f;
        self->aux_g = 1.0f;
        }
    }

void mic_set_role_all(struct mic **mics, const char *role)
    {
    while (*mics)
        mic_set_role(*mics++, *role++);
    }

static struct mic *mic_init(jack_client_t *client, int sample_rate, int id)
    {
    struct mic *self;
    char port_name[10];
    
    if (!(self = calloc(1, sizeof (struct mic))))
        {
        fprintf(stderr, "mic_init: malloc failure\n");
        return NULL;
        }

    self->host = self;
    self->id = id;
    self->sample_rate = (float)sample_rate;   
    self->pan = 50;
    self->aux_g = 1.0f;
    self->peak = peak_init;
    if (!(self->agc = agc_init(sample_rate, 0.01161f, id)))
        {
        fprintf(stderr, "mic_init: agc_init failed\n");
        free(self);
        return NULL;
        }
    snprintf(port_name, 10, "ch_in_%d", id);  
    self->jack_port = jack_port_register(client, port_name,
                            JACK_DEFAULT_AUDIO_TYPE, JackPortIsInput, 0); 
    calculate_gain_values(self);   
        
    return self;
    }
    
struct mic **mic_init_all(int n_mics, jack_client_t *client)
    {
    struct mic **mics;
    int i, sr;
    /* used to map suitable port names from the audio back-end as default connection targets */
    const char **defaults, **dp;
        
    if (!(mics = calloc(n_mics + 1, sizeof (struct mic *))))
        {
        fprintf(stderr, "malloc failure\n");
        exit(5);
        }
    
    sr = jack_get_sample_rate(client);
    defaults = dp = jack_get_ports(client, NULL, NULL, JackPortIsPhysical | JackPortIsOutput);
    
    for (i = 0; i < n_mics; i++)
        {
        mics[i] = mic_init(client, sr, i + 1);
        if (!mics[i])
            {
            fprintf(stderr, "mic_init failed\n");
            exit(5);
            }
        mics[i]->default_mapped_port_name = (dp && *dp) ? strdup(*dp++) : NULL;
        }
        
    for (i = 0; i < n_mics; i += 2)
        {
        mics[i]->partner = mics[i + 1];
        mics[i + 1]->partner = mics[i];
        agc_set_as_partners(mics[i]->agc, mics[i + 1]->agc);
        }
        
    if (defaults)
        jack_free(defaults);
    return mics;
    }

static void mic_free(struct mic *self)
    {
    agc_free(self->agc);
    self->agc = NULL;
    if (self->default_mapped_port_name)
        {
        free(self->default_mapped_port_name);
        self->default_mapped_port_name = NULL;
        } 
    free(self);
    }
    
void mic_free_all(struct mic **mics)
    {
    struct mic **mp = mics;   
        
    while (*mp)
        {
        mic_free(*mp);
        *mp++ = NULL;
        }
    free(mics);
    }
    
void mic_valueparse(struct mic *self, char *param)
    {
    char *save = NULL, *key, *value;

    key = strtok_r(param, "=", &save);
    value = strtok_r(NULL, "=", &save); 
    
    if (!strcmp(key, "mode"))
        {
        self->mode_request = value[0] - '0';
        }
    else if (!strcmp(key, "pan"))
        {
        self->pan = atoi(value);
        calculate_gain_values(self);
        }
    else if (!strcmp(key, "pan_active"))
        {
        self->pan_active = (value[0] == '1') ? 1 : 0;
        calculate_gain_values(self);
        }
    else if(!strcmp(key, "open"))
        {
        self->open = (value[0] == '1') ? 1 : 0;
        }
    else if(!strcmp(key, "invert"))
        {
        self->invert = (value[0] == '1') ? 1 : 0;
        self->igain = self->invert ? -1.0f : 1.0f;
        }
    else if(!strcmp(key, "indjmix"))
        {
        self->djmute = (value[0] == '1') ? 1.0f : 0.0f;
        }
    else if(!strcmp(key, "pairedinvert"))
        {
        self->rel_igain = (value[0] == '1') ? -1.0f : 1.0f;
        }
    else if(!strcmp(key, "pairedgain"))
        {
        self->rel_gain = powf(10.0f, atof(value) * 0.05);
        }
    else
        {
        if (!strcmp(key, "gain"))
            {
            self->gain = atof(value);
            calculate_gain_values(self);
            }
        agc_control(self->agc, key, value);
        }
    }
