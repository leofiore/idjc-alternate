/*
#   avcodec_encoder.c: encode using libavcodec
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
#ifdef HAVE_AVCODEC
#ifdef HAVE_AVUTIL

#include <stdio.h>
#include "avcodec_encoder.h"


static void avcodec_encoder_main(struct encoder *encoder)
{
    struct avenc_data * const s = encoder->priv_data;
    
     if (encoder->encoder_state == ES_STARTING) {
        
         
     }
     
     if (encoder->encoder_state == ES_RUNNING) {
         
     }
     
     if (encoder->encoder_state == ES_STOPPING) {
         
     }
}





int live_avcodec_encoder_init(struct encoder *encoder, struct encoder_vars *ev)
{
    struct avenc_data * const s = calloc(1, sizeof (struct avenc_data));

    if (!s)
        {
        fprintf(stderr, "avcodec_encoder: malloc failure\n");
        return FAILED;
        }
        
    encoder->encoder_private = s;
    encoder->run_encoder = avcodec_encoder_main;
    return SUCCEEDED;
}

#endif /* HAVE_AVUTIL */
#endif /* HAVE_AVCODEC */
