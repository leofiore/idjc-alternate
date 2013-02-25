/*
#   dbconvert.c: fast table based conversion for db to sig level and vice-versa from IDJC.
#   Copyright (C) 2005-2006 Stephen Fairchild (s-fairchild@users.sourceforge.net)
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
#include <math.h>
#include "dbconvert.h"

#define TRUE 1
#define FALSE 0

/* Comment this out to avoid using the lookup table */
#define USING_LOOKUP

#ifdef USING_LOOKUP

static float *dblookup;
static float *signallookup;

int init_dblookup_table()
    {
    int i;
    /* build a decibel lookup table to save on cpu usage */
    if (!(dblookup = malloc(sizeof (float) * 131072)))
        {
        fprintf(stderr, "Failed to allocate space for signal to db lookup table\n");
        return FALSE;
        }
    else
        {
        for (i = 0 ; i < 131072 ; i++)
            dblookup[i] = log10f((i+1) / 131072.0F) * 20.0F;
        }
    return TRUE;
    }
        
int init_signallookup_table()
    {
    int i;
    /* the opposite of the decibel lookup table */
    if (!(signallookup = malloc(sizeof (float) * 65536)))
        {
        fprintf(stderr, "Failed to allocate space for db to signal table\n");
        return FALSE;
        }
    else
        {
        for (i=0; i < 65536; i++)
            signallookup[i] = 1.0F / powf(10.0F, (float)i / 10240.0F);
        }
    return TRUE;
    }
    
void free_dblookup_table()
    {
    free(dblookup);
    }
    
void free_signallookup_table()
    {
    free(signallookup);
    }

/* a table based db lookup function - considerably faster than using the maths co-processor */
inline float level2db(float signal)
    {
    int index;
    float adjustment = 0.0F;
     
    if (signal > 1.0F)
        return ((index = (int)(131072.0005F / signal) - 1) >= 0) ? -dblookup[index] : 102.3501985F;
    else
        {
        if (signal < 3.16227766e-3F)      /* use a more accurate part of the lookup table for low values */
            {
            signal *= 316.227766;
            adjustment = -50.0F;           /* compensate for the 50dB boost in signal level */
            }
        return (((index = (int)(signal * 131072.0005F) - 1) >= 0) ? dblookup[index] : -102.3501985F) + adjustment;
        }
    }
    
/* table based level lookup function taking a db level as input */
inline float db2level(float signal)
    {
    int index;
        
    if (signal < 0.0F)
        return ((index = signal * (-512.0F)) < 65536) ? signallookup[index] : signallookup[65535];
    else
        return ((index = signal * 512.0F) < 65536) ? 1.0F / signallookup[index] : 1.0F / signallookup[65535];
    }

#else

/* These cause the maths co-processor to be used */
int init_dblookup_table()
    {
    return TRUE;
    }
    
int init_signallookup_table()
    {
    return TRUE;
    }
    
void free_dblookup_table() {};
    
void free_signallookup_table() {};

/* the more accurate but more cpu intensive method */
float level2db(float signal)
    {
    return log10f(signal) * 20.0f;
    }

float db2level(float signal)
    {
    return powf(10.0f, signal * 0.05f);
    }
    
#endif
