/*
#   agc.c: a fast lookahead microphone AGC
#   Copyright (C) 2008 Stefan Fendt      (stefan@sfendt.de)
#   Copyright (C) 2008-2010 Stephen Fairchild (s-fairchild@users.sourceforge.net)
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
#include <glib.h>
#include <pthread.h>

#include "agc.h"

/* coefficients of agc_RC_Filter */   
struct agc_RC_Coe
    {
    float a;
    float b;
    float c;
    float f;
    float q;
    };

/* variables of agc_RC_Filter */
struct agc_RC_Var
    {
    float last_in;
    float lp;
    float bp;
    float hp;
    };

/* structure for an RC filter */
struct agc_RC_Filter
    {
    struct agc_RC_Coe coe;
    struct agc_RC_Var var;
    };
    
struct agc_RC_FilterGroup
    {
    struct agc_RC_Filter RC_HPF_initial[4];
    struct agc_RC_Filter RC_HPF_detail;
    struct agc_RC_Filter RC_LPF_detail;
    struct agc_RC_Filter RC_PHR[4];
    struct agc_RC_Filter RC_F_DS;
    };
    
struct agc
    {
    int id;
    struct agc *host;       /* points to self or partner for stereo implementation */
    struct agc *partner;
    float input;
    float ratio;
    float limit;
    float nr_gain;
    float nr_onthres;
    float nr_offthres;
    float gain_interval_amount; /* agc gain can move by this amount each interval */
    int nr_state;
    float *buffer;          /* eventual buffer size depends on sample rate */
    int buffer_len;
    int sRate;              /* the sample rate in use by JACK */
    int in_pos;
    int out_pos;
    float gain;
    float DC;
    float ds_bias;
    float ds_gain;
    int   ds_state;
    int   RR_reset_point[4];     /* reset intervals used by all the envelope followers */
    float RR_signal[4];
    float RR_DS_high[4];
    float RR_DS_low[4];
    int   use_ducker;
    float df;
    float ducker_attack;
    float ducker_release;
    int   ducker_hold_timer;
    int   ducker_hold_timer_resetval;
    float meter_signal_cap, meter_de_ess, meter_noise_gate;
    int hpstages;
    float hf_detail;
    float lf_detail;
    int use_phaserotator;   
    struct agc_RC_FilterGroup filters;
    };

static GHashTable *control_ht;  /* used for looking up control functions */


static float agc_12db_hpfilter(struct agc_RC_Coe *c, struct agc_RC_Var *v, float input)
    {
    input += c->q * v->bp;
    v->hp = c->c * (v->hp + input - v->last_in);
    v->bp = v->bp * c->a + v->hp * c->b;
    v->last_in = input;
    return v->hp;
    }

static float agc_6db_hpfilter(float detail, struct agc_RC_Coe *c, struct agc_RC_Var *v, float input)
    {
    v->hp = c->c * (v->hp + input - v->last_in);
    v->last_in = input;
    return input + v->hp * detail;
    }

static float agc_6db_lpfilter(float detail, struct agc_RC_Coe *c, struct agc_RC_Var *v, float input)
    {
    v->lp = v->lp * c->a + input * c->b;
    return input + v->lp * detail;
    }

static float agc_phaserotate(struct agc_RC_Filter *f, float input)
    {
    struct agc_RC_Coe *c = &f->coe;
    struct agc_RC_Var *v = &f->var;
        
    v->hp = c->c * (v->hp + input - v->last_in);
    v->lp = v->lp * c->a + input * c->b;
    v->last_in = input;
    return v->lp - v->hp;
    }

void agc_process_stage1(struct agc *s, float input)
    {
    /* An analog active RC-Highpassfilter network to remove DC and subsonic sounds
     * each stage has 12dB/octave of attenuation.
     */
    for (int i = 0, q = s->host->hpstages; i < q; ++i)
        input = agc_12db_hpfilter(&s->host->filters.RC_HPF_initial[i].coe, &s->filters.RC_HPF_initial[i].var, input);

    /* RC-Network (but with only one stage and without resonance/feedback (->6dB/octave))
     * used as HF-Detail-Filter 
     */
    input = agc_6db_hpfilter(s->host->hf_detail, &s->host->filters.RC_HPF_detail.coe, &s->filters.RC_HPF_detail.var, input);

    /* RC-Network (but with only one stage and without resonance/feedback)
     * used as LF-Detail-Filter 
     */
    input = agc_6db_lpfilter(s->host->lf_detail, &s->host->filters.RC_LPF_detail.coe, &s->filters.RC_LPF_detail.var, input); 

    /* Phase-rotator done with RC-simulation
     * for good reasons doesn't use Q/resonance either...
     */
    if (s->host->use_phaserotator)
        for (int i = 0; i < 4; ++i)
            input = agc_phaserotate(s->filters.RC_PHR + i, input);

    /* feed input into ring-buffer, store input */
    s->buffer[s->in_pos % s->buffer_len] = s->input = input;
    
    /* update pointers of the ring-buffer */  
    s->in_pos++;
    s->out_pos++;
    }

static float agc_quad_rr(float *storage, int *reset_point, int phase, float input)
    {
    float highest = 0.0f; 
    
    input = fabsf(input);
    
    for (int i = 0; i < 4; ++i, ++storage, ++reset_point)
        {
        if (*reset_point == phase)
            *storage = 0.0f;
        if (input > *storage)
            *storage = input;
        if (*storage > highest)
            highest = *storage;
        }
    return highest;
    }

void agc_process_stage2(struct agc *s, int mic_is_mute)
    {
    /* audio signal for sidechain use - possibly combined */
    float input;
    /* phase for use by all of the envelope-followers */
    float phase;
    /* de-esser values */
    float ds_amph, ds_ampl;
    /* the input signal level as computed by the envelope follower */
    float amp;
    /* the amplification factor */
    float factor, orig_factor;
    /* the computed ducker amplification factor - used externally */
    float duck_amp;

    if (s == s->host)
        {
        input = (s->partner->host == s) ? (s->input + s->partner->input) * 0.5 : s->input;
        phase = s->in_pos % (2 * s->buffer_len);   
      
        /* De-Esser sidechain-filter - does high and low pass filtering
         */
        {
            float ds_input;
            struct agc_RC_Coe *c = &s->filters.RC_F_DS.coe;
            struct agc_RC_Var *v = &s->filters.RC_F_DS.var;
            
            ds_input = input;
            ds_input += c->q * v->bp;
            v->lp = v->lp * c->a + ds_input * c->b;
            v->hp = c->c * (v->hp + input - v->last_in );
            v->bp = v->bp * c->a + v->hp * c->b;
            v->last_in = ds_input;
        }
        
        /* follow the envelope of the de-esser high and low pass filtered signal */
        ds_amph = agc_quad_rr(s->RR_DS_high, s->RR_reset_point, phase, s->filters.RC_F_DS.var.hp);
        ds_ampl = agc_quad_rr(s->RR_DS_low, s->RR_reset_point, phase, s->filters.RC_F_DS.var.lp);
        
        /* round-robin-4-peak-envelope-follower tracking the general signal level */
        amp = agc_quad_rr(s->RR_signal, s->RR_reset_point, phase, input);

        /* raw-amplification-factor limited to maximum allowed ratio */
        factor = s->limit / (amp + 0.0001f);
        if (factor > s->ratio)
            factor = s->ratio;

        /* so we can know how much attenuation was applied this is stored */
        orig_factor = factor;

        /* if below noise-floor, attenuate signal */
        if (amp < s->nr_onthres)
            s->nr_state = 1;

        if (amp > s->nr_offthres)
            s->nr_state = 0;

        if (s->nr_state==1)
            factor *= s->nr_gain;

        /* if de-esser says there are only high frequencies, attenuate signal */
        if (ds_amph * s->ds_bias > ds_ampl * 1.3333333f)
             s->ds_state = 1;
 
        if (ds_amph * s->ds_bias < ds_ampl * 0.75f)
             s->ds_state = 0;
 
        if (s->ds_state == 1)
             factor *= s->ds_gain;
 
        /* modulate gain-factor */
        if (s->gain < factor)
            s->gain += s->gain_interval_amount;

        if (s->gain > factor)
            s->gain -= s->gain_interval_amount;

        /* ducking is optional and must not work when the mic is closed */
        if (mic_is_mute || s->use_ducker == 0)
            {
            if (s->df < 1.0f)
                s->df += s->ducker_release;
            else
                s->df = 1.0f;
            }
        else
            {
            /* calculate ducking factor */
            duck_amp = 1.0f - factor * amp;
        
            /* if duck-amp is below the minimum-allowed level (limit enforces some headroom)
             * then limit duck-amp to that minimum-allowed level. This ensures, that if the
             * microphone-headroom is set to a sensible value (-2..-3dB) there still is some
             * music audiable in the background...
             */
            if (duck_amp < 1.0f - s->limit)
                {
                duck_amp = 1.0f - s->limit;
                }

            /* ducker is "opened" fast (same rate as agc -> 10ms)
             * but closed more slowly...
             */
            if (s->df < duck_amp)
                {
                if (s->ducker_hold_timer == 0)
                    {
                    s->df += s->ducker_release;
                    if (s->df > 1.0f)
                        s->df = 1.0f;
                    }
                else
                    s->ducker_hold_timer--;
                }
            if (s->df > duck_amp)
                {
                s->df -= s->ducker_attack;
                s->ducker_hold_timer = s->ducker_hold_timer_resetval;
                if (s->df < 0.00000001f)
                    s->df = 0.00000001f;
                }
            }

        /* maintain a peak hold gain figure for the GUI compression meter
         * essentially this is metadata 
         */
        if ((s->out_pos & 0x7) == 0)
            {
            s->meter_signal_cap = orig_factor / s->ratio;
            s->meter_de_ess = s->ds_state ? s->ds_gain : 1.0f;
            s->meter_noise_gate = s->nr_state ? s->nr_gain : 1.0f;
            }
        }
    }

float agc_process_stage3(struct agc *s)
    {
    /* modulate delayed signal with gain */
    return s->buffer[s->out_pos % s->buffer_len] * s->host->gain;
    }

void agc_get_meter_levels(struct agc *s, int *signal_cap, int *de_ess, int *noise_gate)
    {
    int level2db(float level)
        {
        return (int)(log10f(level) * -20.0f);
        }
        
    *signal_cap = (int)level2db(s->meter_signal_cap);
    *de_ess = (int)level2db(s->meter_de_ess);
    *noise_gate = (int)level2db(s->meter_noise_gate);
    }
    
float agc_get_ducking_factor(struct agc *s)
    {
    return s->df;
    }
    
void agc_reset(struct agc *s)
    {
    struct agc_RC_Filter *f, *end;

    /* wipe variables of all filters */
    for (f = (struct agc_RC_Filter *)&s->filters,
        end = (struct agc_RC_Filter *)((&s->filters) + 1); f < end; ++f)
        {
        memset(&f->var, 0, sizeof f->var); 
        }

    /* wipe audio buffer */
    memset(s->buffer, 0, s->buffer_len);
 
    /* wipe indicator settings */
    s->df = s->meter_signal_cap = s->meter_de_ess = s->meter_noise_gate = 1.0f;
    }

static void setup_ratio(struct agc *s, float ratio_db)
    {
    s->ratio = powf(10.0f, ratio_db / 20.0f);
    s->gain_interval_amount = s->ratio / s->buffer_len;
    }

static void setup_subsonic(struct agc *s, float fCutoff)
    {
    struct agc_RC_Coe *c;
    
    for (int i = 0; i < 4; ++i)
        {
        c = &s->filters.RC_HPF_initial[i].coe;
    
        c->f = fCutoff;
        c->q = 0.375f;
        c->a = 1.0f - (1.0f/s->sRate) / ((1.0f / (c->f * 2.0f * M_PI)) + (1.0f/s->sRate));
        c->b = 1.0f - c->a;
        c->c = (1.0f/(c->f * 2.0f * M_PI)) / ((1.0f/(c->f * 2.0f * M_PI)) + (1.0f/s->sRate));
        }
    }

static void setup_lfdetail(struct agc *s, float multi, float fCutoff)
    {
    struct agc_RC_Coe *c = &s->filters.RC_LPF_detail.coe;
        
    s->lf_detail = multi;
    c->f = fCutoff;
    c->q = 0.375f;
    c->a = 1.0f - (1.0f/s->sRate) / ((1.0f / (c->f * 2.0f * M_PI)) + (1.0f/s->sRate));
    c->b = 1.0f - c->a;
    c->c = (1.0f / (c->f * 2.0f * M_PI)) / ((1.0f / (c->f * 2.0f * M_PI)) + (1.0f / s->sRate));
    }

static void setup_hfdetail(struct agc *s, float multi, float fCutoff)
    {
    struct agc_RC_Coe *c = &s->filters.RC_HPF_detail.coe;   
        
    s->hf_detail = multi;
    c->f = fCutoff;
    c->q = 0.375f;
    c->a = 1.0f - (1.0f / s->sRate) / ((1.0f / (c->f * 2.0f * M_PI)) + (1.0f / s->sRate));
    c->b = 1.0f - c->a;
    c->c = (1.0f / (c->f * 2.0f * M_PI)) / ((1.0f / (c->f * 2.0f * M_PI)) + (1.0f / s->sRate));
    }

static void control_phaserotate(struct agc *s, char *value)
    {
    s->use_phaserotator = (value[0] == '1');
    } 

static void control_gain(struct agc *s, char *value)
    {
    setup_ratio(s, strtof(value, NULL));
    }
    
static void control_limit(struct agc *s, char *value)
    {
    s->limit = powf(2.0f, strtof(value, NULL) / 6.0f);
    }

static void control_ngthresh(struct agc *s, char *value)
    {
    s->nr_onthres = powf(2.0f, (strtof(value, NULL) - 1.0f) / 6.0f);
    s->nr_offthres = powf(2.0f, (strtof(value, NULL) + 1.0f) / 6.0f);
    }

static void control_nggain(struct agc *s, char *value)
    {
    s->nr_gain = powf(2.0f, strtof(value, NULL) / 6.0f);
    }

static void control_duckenable(struct agc *s, char *value)
    {
    s->use_ducker = (value[0] == '1');
    }

static void control_duckrelease(struct agc *s, char *value)
    {
    s->ducker_release = 1000.0f / (strtof(value, NULL) * s->sRate);
    }

static void control_duckhold(struct agc *s, char *value)
    {
    s->ducker_hold_timer_resetval = atoi(value) * s->sRate / 1000;
    }
    
static void control_deessbias(struct agc *s, char *value)
    {
    s->ds_bias = strtof(value, NULL);
    }

static void control_deessgain(struct agc *s, char *value)
    {
    s->ds_gain = powf(2.0f, strtof(value, NULL) / 6.0f);
    }

static void control_hpcutoff(struct agc *s, char *value)
    {
    setup_subsonic(s, strtof(value, NULL));
    }

static void control_hpstages(struct agc *s, char *value)
    {
    s->hpstages = (int)(strtof(value, NULL) + 0.5f);
    }

static void control_hfmulti(struct agc *s, char *value)
    {
    setup_hfdetail(s, strtof(value, NULL), s->filters.RC_HPF_detail.coe.f);
    }

static void control_hfcutoff(struct agc *s, char *value)
    {
    setup_hfdetail(s, s->hf_detail, strtof(value, NULL));
    }

static void control_lfmulti(struct agc *s, char *value)
    {
    setup_lfdetail(s, strtof(value, NULL), s->filters.RC_LPF_detail.coe.f);
    }

static void control_lfcutoff(struct agc *s, char *value)
    {
    setup_lfdetail(s, s->lf_detail, strtof(value, NULL));
    }

static void free_control_hash_table()
    {
    g_hash_table_destroy(control_ht);
    }

static void setup_control_hash_table()
    {
    struct
    {
    char *key;
    void (*value)(struct agc *, char *);
    } *htdp, htdata[] = {
        {"phaserotate", control_phaserotate},
        {"gain", control_gain},
        {"limit", control_limit},
        {"ngthresh", control_ngthresh},
        {"nggain", control_nggain}, 
        {"duckenable", control_duckenable},
        {"duckrelease", control_duckrelease},
        {"duckhold", control_duckhold},
        {"deessbias", control_deessbias},
        {"deessgain", control_deessgain},
        {"hpcutoff", control_hpcutoff},
        {"hpstages", control_hpstages},
        {"hfmulti", control_hfmulti},
        {"hfcutoff", control_hfcutoff},
        {"lfmulti", control_lfmulti},
        {"lfcutoff", control_lfcutoff},
        {NULL, NULL}};

    if (!(control_ht = g_hash_table_new(g_str_hash, g_str_equal)))
        {
        fprintf(stderr, "agc setup_control_hash_table failed\n");
        return;
        }
    
    for (htdp = htdata; htdp->key; ++htdp)
        g_hash_table_insert(control_ht, htdp->key, htdp->value);
        
    atexit(free_control_hash_table);
    }

void agc_control(struct agc *s, char *key, char *value)
    {
    void (*fn)(struct agc *, char *);
    
    if (!(fn = g_hash_table_lookup(control_ht, key)))
        fprintf(stderr, "agc_control: lookup error for key %s\n", key);
    else
        fn(s, value);
    }

void agc_set_as_partners(struct agc *agc1, struct agc *agc2)
    {
    agc1->partner = agc2;
    agc2->partner = agc1;
    } 

void agc_set_partnered_mode(struct agc *s, int boolean)
    {
    if (boolean)
        s->host = s->partner;
    else
        s->host = s;
    }

struct agc *agc_init(int sRate, float lookahead, int id)
    {
    struct agc *s;
    struct agc_RC_Coe *c;
    static pthread_once_t control_hash_table_once = PTHREAD_ONCE_INIT;
    
    pthread_once(&control_hash_table_once, setup_control_hash_table);

    if (!(s = calloc(1, sizeof (struct agc))))
        {
        fprintf(stderr, "agc_init: malloc failure\n");
        return NULL;
        }

    if (!(s->buffer = calloc((s->buffer_len = (s->sRate = sRate) * lookahead), sizeof (float))))
        {
        fprintf(stderr, "agc_init: malloc failure\n");
        free(s);
        return NULL;
        }

    s->id = id;
    s->host = s->partner = s;

    {
        /* determine the phase points for the envelope followers */
        int p4 = s->buffer_len * 2;

        s->RR_reset_point[0] = 0;
        s->RR_reset_point[1] = p4 * 1 / 4;
        s->RR_reset_point[2] = p4 * 2 / 4;
        s->RR_reset_point[3] = p4 * 3 / 4;
    }

    setup_ratio(s, 3.0f);/* 3:1 "compression" */
    s->limit = 0.707f;   /* signal level to top out at */
    s->in_pos = s->buffer_len - 1;
    s->out_pos = 1;
    s->gain = 0.0f;
    s->nr_onthres = 0.1f;      /* silence detection level */
    s->nr_offthres = 0.1001f;  /* non-silence detection level */
    s->nr_gain = 0.5f;         /* if silence detected reduce gain by 6dB */
    
    s->ds_bias  =  0.35f; /* lpf * bias / hpf exceeds 1 for de-esser to go active */
    s->ds_gain  =  0.5f;  /* attenuate signal by this amount */
    s->meter_signal_cap = s->meter_de_ess = s->meter_noise_gate = 1.0f;
    
    /* setup coefficients for the ducker */
    s->ducker_release = 1.0f / (0.250f * s->sRate); /* 250ms */
    s->ducker_attack  = 1.0f / s->buffer_len;    /* same as lookahead delay */
    s->ducker_hold_timer_resetval = 0.500f * s->sRate; /* 500ms */
    s->df = 1.0f;
    
    /* setup coefficients for the subsonic-and-DC-killer-RC-highpass */
    setup_subsonic(s, 100.0f);
    s->hpstages = 4;
    
    /* setup coefficients for the HF-Detail highpass */
    setup_hfdetail(s, 4.0f, 2000.0f);
    
    /* setup coefficients for the LF-Detail lowpass */
    setup_lfdetail(s, 4.0f, 150.0f);
    
    /* setup coefficients for the phase rotator */
    s->use_phaserotator = 1;
    for (int i = 0; i < 4; ++i)
        {
        c = &s->filters.RC_PHR[i].coe;
        
        c->f = 300.0f;
        c->q = 0.0f;
        c->a = 1.0f - (1.0f / s->sRate) / ((1.0f/(c->f * 2.0f * M_PI)) + (1.0f / s->sRate));
        c->b = 1.0f - c->a;
        c->c = (1.0f / (c->f * 2.0f * M_PI)) / ((1.0f / (c->f * 2.0f * M_PI)) + (1.0f / s->sRate));
        }
    
    /* setup coefficients for the de-esser-sidechain highpass/lowpass filter */
    c = &s->filters.RC_F_DS.coe;
    c->f = 1000.0f;
    c->q = 1.000f;
    c->a = 1.0f - (1.0f / s->sRate) / ((1.0f / (c->f * 2.0f * M_PI)) + (1.0f / s->sRate));
    c->b = 1.0f - c->a;
    c->c = (1.0f / (c->f * 2.0f * M_PI)) / ((1.0f / (c->f * 2.0f * M_PI)) + (1.0f / s->sRate));

    return s;
    }

void agc_free(struct agc *s)
    {
    free(s->buffer);
    free(s);
    }
