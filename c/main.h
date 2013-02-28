/*
#   main.h: backend unification module
#   Copyright (C) 2011-2012 Stephen Fairchild (s-fairchild@users.sourceforge.net)
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

#include <pthread.h>
#include <signal.h>
#include <jack/jack.h>
#include <jack/ringbuffer.h>

struct jack_ports
    {
    /* mixer ports */
    jack_port_t *dj_out_l;
    jack_port_t *dj_out_r;
    jack_port_t *dsp_out_l;
    jack_port_t *dsp_out_r;
    jack_port_t *dsp_in_l;
    jack_port_t *dsp_in_r;
    jack_port_t *str_out_l;
    jack_port_t *str_out_r;
    jack_port_t *voip_out_l;
    jack_port_t *voip_out_r;
    jack_port_t *voip_in_l;
    jack_port_t *voip_in_r;
    jack_port_t *alarm_out;

    /* player breakout ports */
    jack_port_t *pl_out_l;
    jack_port_t *pl_out_r;
    jack_port_t *pr_out_l;
    jack_port_t *pr_out_r;
    jack_port_t *pi_out_l;
    jack_port_t *pi_out_r;
    jack_port_t *pe1_out_l;
    jack_port_t *pe1_out_r;
    jack_port_t *pe2_out_l;
    jack_port_t *pe2_out_r;
    jack_port_t *pl_in_l;
    jack_port_t *pl_in_r;
    jack_port_t *pr_in_l;
    jack_port_t *pr_in_r;
    jack_port_t *pi_in_l;
    jack_port_t *pi_in_r;
    jack_port_t *pe_in_l;
    jack_port_t *pe_in_r;
    
    jack_port_t *midi_port;
        
    /* streamer/recorder capture ports */
    jack_port_t *output_in_l;
    jack_port_t *output_in_r;
    };

struct globs
    {
    sig_atomic_t app_shutdown;
    int main_timeout;          /* Inactive when negative. */
    int jack_timeout;
    int has_head;
    int mixer_up;
    jack_client_t *client;     /* Client handle to JACK. */
    struct jack_ports port;    /* JACK port handles. */
    jack_ringbuffer_t *session_event_rb; /* Session event buffer */
    pthread_mutex_t avc_mutex;   /* lock for avcodec */
    FILE *in;                   /* comms stream with user interface */
    FILE *out;
    int freewheel;
    };

extern struct globs g;
