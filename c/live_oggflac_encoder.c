/*
#   live_oggflac_encoder.c: encode oggflac from a live source
#   Copyright (C) 2008 Stephen Fairchild (s-fairchild@users.sourceforge.net)
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

#ifdef HAVE_OGGFLAC

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ogg/ogg.h>
#include "live_oggflac_encoder.h"

#define TRUE 1
#define FALSE 0
#define SUCCEEDED 1
#define FAILED 0


static FLAC__int32 **live_oggflac_encoder_make_pcm(struct encoder_ip_data *id, struct lofe_data *s)
    {
    const float mul = (float)(1 << (s->bits_per_sample - 1));
    const float scale = 1.0f / RAND_MAX;
    const FLAC__int32 ul = mul - 0.5;
    const FLAC__int32 ll = ~ul;
    FLAC__int32 val;
    FLAC__int32 **pcm;
    int i;
    unsigned j;

    if (!(pcm = malloc(sizeof (FLAC__int32 *) * id->channels)))
        {
        fprintf(stderr, "live_oggflac_encoder_make_pcm: malloc failure\n");
        return NULL;
        }

    for (i = 0; i < id->channels; i++)
        {
        if (!(pcm[i] = malloc(sizeof (FLAC__int32) * id->qty_samples)))
            {
            fprintf(stderr, "live_oggflac_encoder_make_pcm: malloc failure\n");
            free(pcm);
            return NULL;
            }

        for(j = 0; j < id->qty_samples; j++)
            {
            if (s->bits_per_sample <= 20)
                val = id->buffer[i][j] * mul + (float)rand_r(&s->seedp) * scale + (float)rand_r(&s->seedp) * scale - 1.0f;
            else
                val = id->buffer[i][j] * mul;

            if (val > ul)
                {
                pcm[i][j] = ul;
                s->uclip++;
                }
            else
                if (val < ll)
                    {
                    pcm[i][j] = ll;
                    s->lclip++;
                    }
                else
                    pcm[i][j] = val;
            }
        }

    return pcm;
    }

static void live_oggflac_encoder_free_pcm(FLAC__int32 *pcm[], int channels)
    {
    int i;

    for (i = 0; i < channels; i++)
        free(pcm[i]);
    free(pcm);
    }

static FLAC__StreamEncoderWriteStatus live_oggflac_encoder_write_cb(const FLAC__StreamEncoder *enc, const FLAC__byte buffer[], size_t bytes, unsigned samples, unsigned current_frame, void *client_data)
    {
    struct encoder *encoder = client_data;
    struct lofe_data *s = encoder->encoder_private;
    struct encoder_op_packet packet;
    ogg_page og;
    int granulepos;

    if ((s->n_writes & 0x1) == 0)
        {
        /* writing ogg header */
        s->pab_rqd = s->pab_head_size = bytes;
        
        if (s->pab_size < s->pab_rqd)
            if (!(s->pab = realloc(s->pab, s->pab_size = s->pab_rqd)))
                {
                fprintf(stderr, "live_oggflac_encoder_write_cb: malloc failure\n");
                return FLAC__STREAM_ENCODER_WRITE_STATUS_FATAL_ERROR;
                }
        
        memcpy(s->pab, buffer, bytes);
        
        s->flags = PF_OGG;
        if (s->n_writes == 0)
            s->flags |= PF_INITIAL;
        if (buffer[5] & 0x4)
            s->flags |= PF_FINAL;
            
        og.header = (unsigned char *)buffer;
        og.header_len = bytes;
        og.body = NULL;
        og.body_len = 0;
        switch ((granulepos = ogg_page_granulepos(&og)))
            {
            case -1:
                break;
            case 0:
                s->flags |= PF_HEADER;
                break;
            default:
                s->samples = granulepos;
            }
        }
    else
        {
        /* writing ogg body */
        if (s->pab_size < (s->pab_rqd += bytes))
            if (!(s->pab = realloc(s->pab, s->pab_size = s->pab_rqd)))
                {
                fprintf(stderr, "live_oggflac_encoder_write_cb: malloc failure\n");
                return FLAC__STREAM_ENCODER_WRITE_STATUS_FATAL_ERROR;
                }
        
        memcpy(s->pab + s->pab_head_size, buffer, bytes);
        
        packet.header.bit_rate = encoder->bitrate;
        packet.header.sample_rate = encoder->target_samplerate;
        packet.header.n_channels = encoder->n_channels;
        packet.header.flags = s->flags;
        packet.header.data_size = s->pab_rqd;
        packet.header.timestamp = encoder->timestamp = (double)s->samples / (double)encoder->samplerate;
        packet.data = s->pab;
        encoder_write_packet_all(encoder, &packet);
        }
        
    s->n_writes++;
    return FLAC__STREAM_ENCODER_WRITE_STATUS_OK;
    }

static char *prepend(char *before, char *after)
    {
    char *new;
    
    if (!(new = malloc(strlen(before) + strlen(after) + 1)))
        {
        fprintf(stderr, "malloc failure\n");
        return NULL;
        }
        
    strcpy(new, before);
    strcat(new, after);
    free(after);
    return new;
    }

#define PREPEND(b, a) a = prepend(b, a); nmeta++; dlen += strlen(a);
#define CPREPEND(b, a) if (a && a[0]) { PREPEND(b, a); }
#define APPEND(a) if (a && a[0]) { vc->comments[i].length = strlen(a); vc->comments[i].entry = (FLAC__byte *)a; i++; }

static void live_oggflac_encoder_main(struct encoder *encoder)
    {
    struct lofe_data * const s = encoder->encoder_private;
    struct ogg_tag_data *t = &s->tag_data;

    if (encoder->encoder_state == ES_STARTING)
        {
        if (!(s->enc = FLAC__stream_encoder_new()))
            {
            fprintf(stderr, "live_oggflac_encoder_main: failed to create new encoder\n");
            goto bailout;
            }

        if (encoder->new_metadata)
            {
            int nmeta = 0, i = 0;
            size_t dlen = 0;
            FLAC__StreamMetadata_VorbisComment *vc;
            
            live_ogg_capture_metadata(encoder, t);
            
            if (t->custom && t->custom[0])
                {
                PREPEND("title=", t->custom)
                CPREPEND("trk-artist=", t->artist)
                CPREPEND("trk-title=", t->title)
                CPREPEND("trk-album=", t->album)
                }
            else
                {
                CPREPEND("artist=", t->artist)
                CPREPEND("title=", t->title)
                CPREPEND("album=", t->album)
                }

            if (nmeta)
                {
                if (s->metadata[0] == NULL)
                    if (!(s->metadata[0] = calloc(1, sizeof (FLAC__StreamMetadata))))
                        {
                        fprintf(stderr, "live_oggflac_encoder_main: malloc failure\n");
                        goto bailout;
                        }
                    
                vc = &s->metadata[0]->data.vorbis_comment;
                vc->num_comments = nmeta;
                vc->vendor_string.entry = (FLAC__byte *)FLAC__VENDOR_STRING;
                dlen += vc->vendor_string.length = strlen(FLAC__VENDOR_STRING);
                s->metadata[0]->type = FLAC__METADATA_TYPE_VORBIS_COMMENT;
                s->metadata[0]->is_last = TRUE;
                s->metadata[0]->length = nmeta * 4 + dlen + 8;
                
                vc->comments = realloc(vc->comments, nmeta * sizeof (FLAC__StreamMetadata_VorbisComment_Entry));
                
                APPEND(t->custom)
                APPEND(t->artist)
                APPEND(t->title)
                APPEND(t->album)
                }
            }

        encoder->bitrate = 0.00085034 * encoder->n_channels * s->bits_per_sample * encoder->target_samplerate;
        s->n_writes = 0;
        FLAC__stream_encoder_set_channels(s->enc, encoder->n_channels);
        FLAC__stream_encoder_set_bits_per_sample(s->enc, s->bits_per_sample);
        FLAC__stream_encoder_set_sample_rate(s->enc, encoder->target_samplerate);
        FLAC__stream_encoder_set_ogg_serial_number(s->enc, ++encoder->oggserial);
        if (encoder->use_metadata && s->metadata[0])
            FLAC__stream_encoder_set_metadata(s->enc, s->metadata, 1);
        FLAC__stream_encoder_init_ogg_stream(s->enc, NULL, live_oggflac_encoder_write_cb, NULL, NULL, NULL, encoder);
        encoder->timestamp = 0.0;
        encoder->encoder_state = ES_RUNNING;
        return;
        }

    if (encoder->encoder_state == ES_RUNNING)
        {
        struct encoder_ip_data *id;

        if (encoder->new_metadata || !encoder->run_request_f || encoder->flush)
            {
            FLAC__stream_encoder_finish(s->enc);
            encoder->flush = FALSE;
            encoder->encoder_state = ES_STOPPING;
            }
        else
            {
            id = encoder_get_input_data(encoder, 1024, 8192, NULL);
            if (id)
                {
                FLAC__int32 **pcm;

                pcm = live_oggflac_encoder_make_pcm(id, s);
                FLAC__stream_encoder_process(s->enc, (const FLAC__int32 ** const)pcm, id->qty_samples);
                live_oggflac_encoder_free_pcm(pcm, id->channels);
                encoder_ip_data_free(id);
                }
            }
        return;
        }
        
    if (encoder->encoder_state == ES_STOPPING)
        {
        FLAC__stream_encoder_delete(s->enc);
        if (!encoder->run_request_f)
            goto bailout;
        else
            encoder->encoder_state = ES_STARTING;
        return;
        }

    fprintf(stderr, "live_oggflac_encoder_main: unhandled encoder state\n");
    return;
    
    bailout:
    fprintf(stderr, "live_oggflac_encoder_main: performing cleanup\n");
    encoder->run_request_f = FALSE;
    encoder->encoder_state = ES_STOPPED;
    encoder->run_encoder = NULL;
    encoder->flush = FALSE;
    encoder->new_metadata = FALSE;
    encoder->encoder_private = NULL;
    if (s)
        {
        fprintf(stderr, "Clipping detected on upper %d times and lower %d times.\n", s->uclip, s->lclip);
        
        if (s->metadata[0])
            {
            if (s->metadata[0]->data.vorbis_comment.comments)
                free(s->metadata[0]->data.vorbis_comment.comments);
            free(s->metadata[0]);
            }
        live_ogg_free_metadata(t);
        free(s);
        }
    
    fprintf(stderr, "live_oggflac_encoder_main: finished cleanup\n");
    return;
    }

int live_oggflac_encoder_init(struct encoder *encoder, struct encoder_vars *ev)
    {
    struct lofe_data * const s = calloc(1, sizeof (struct lofe_data));

    if (!s)
        {
        fprintf(stderr, "live_oggflac_encoder: malloc failure\n");
        return FAILED;
        }

    s->bits_per_sample = atoi(ev->bitwidth);
    encoder->use_metadata = strcmp(ev->metadata_mode, "suppressed") ? 1 : 0;
    encoder->encoder_private = s;
    encoder->run_encoder = live_oggflac_encoder_main;
    return SUCCEEDED;
    }

#endif /* HAVE_OGGFLAC */
