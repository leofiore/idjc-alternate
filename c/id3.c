/*
#   id3.c: generater of id3 tags for the recorder - emphasis on chapter tags
#   Copyright (C) 2007 Stephen Fairchild (s-fairchild@users.sourceforge.net)
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
#include <stdint.h>
#include "id3.h"
#include "main.h"

static void id3_frame_extra_cleanup(struct id3_frame *frame)
    {
    struct id3_text_frame_data *tdptr = frame->data;
    struct id3_chap_frame_data *cdptr = frame->data;

    if (!strcmp(frame->frame_header.frame_id, "TLEN"))
        return;
    if (frame->frame_header.frame_id[0] == 'T' && strcmp(frame->frame_header.frame_id, "TXXX"))
        { 
        free(tdptr->text);
        return;
        }
    if (!strcmp(frame->frame_header.frame_id, "CHAP"))
        {
        free(cdptr->identifier);
        return;
        }
    }

static void id3_frame_destroy_recursive(struct id3_frame *frame)
    {
    if (frame->first_embedded_frame)
        {
        id3_frame_destroy_recursive(frame->first_embedded_frame);
        if (frame->first_embedded_frame->data)
            {
            id3_frame_extra_cleanup(frame->first_embedded_frame);
            free(frame->first_embedded_frame->data);
            }
        free(frame->first_embedded_frame);
        }
    if (frame->next)
        {
        id3_frame_destroy_recursive(frame->next);
        if (frame->next->data)
            {
            id3_frame_extra_cleanup(frame->next);
            free(frame->next->data);
            }
        free(frame->next);
        }
    }

void id3_tag_destroy(struct id3_tag *tag)
    {
    if (tag->first_frame)
        {
        id3_frame_destroy_recursive(tag->first_frame);
        if (tag->first_frame->data)
            free(tag->first_frame->data);
        free(tag->first_frame);
        }
    free(tag);
    }

static int id3_syncsafe_int(uint32_t value, uint32_t *ssvalue)
    {
    unsigned char *ssint = (unsigned char *)ssvalue;
    
    ssint[0] = (value >> 21) & 0xFF;
    ssint[1] = (value >> 14) & 0xFF;
    ssint[2] = (value >> 7 ) & 0xFF;
    ssint[3] = (value >> 0 ) & 0xFF;
    return *ssvalue;
    }

static void id3_make_be(unsigned char *byte, uint32_t value)
    {
    byte[3] = value & 0xFF;
    byte[2] = (value >> 8) & 0xFF;
    byte[1] = (value >> 16) & 0xFF;
    byte[0] = value >> 24;
    }

static int id3_compile_text_frame(struct id3_frame *ptr, int embedded_size)
    {
    struct id3_text_frame_data *dptr;
    char *body;
    int body_size;
    uint32_t ssint;
    
    if (embedded_size != 0)
        {
        fprintf(stderr, "id3_compile_text_frame: WARNING: text frames do not support frame embedding\n");
        }
    dptr = ptr->data;
    body = calloc(1, body_size = strlen(dptr->text) + 1 + dptr->null_terminator);
    body[0] = dptr->text_encoding;
    memcpy(body + 1, dptr->text, body_size - 1 - dptr->null_terminator);
    if (!(ptr->compiled_data = malloc(body_size + 10)))
        {
        fprintf(stderr, "id3_compile_text_frame: malloc failure\n");
        return 0;
        }
    memcpy(ptr->compiled_data, ptr->frame_header.frame_id, 4);
    id3_syncsafe_int(body_size, &ssint);
    memcpy(ptr->compiled_data + 4, &ssint, 4);
    ptr->compiled_data[8] = ptr->frame_header.status_flags;
    ptr->compiled_data[9] = ptr->frame_header.format_flags;
    memcpy(ptr->compiled_data + 10, body, body_size);
    free(body);
    return ptr->compiled_data_size = ptr->compiled_non_embedded_data_size = body_size + 10;
    }

static int id3_compile_numeric_frame(struct id3_frame *ptr, int embedded_size)
    {
    char *body;
    int body_size;
    uint32_t ssint;
    
    if (embedded_size != 0)
        {
        fprintf(stderr, "id3_compile_text_frame: WARNING: text frames do not support frame embedding\n");
        }
    if (!(body = malloc(body_size = strlen(ptr->data))))
        {
        fprintf(stderr, "id3_compile_text_frame: malloc failure\n");
        return 0;
        }
    memcpy(body, ptr->data, body_size);
    if (!(ptr->compiled_data = malloc(body_size + 10)))
        {
        fprintf(stderr, "id3_compile_text_frame: malloc failure\n");
        return 0;
        }
    memcpy(ptr->compiled_data, ptr->frame_header.frame_id, 4);
    id3_syncsafe_int(body_size, &ssint);
    memcpy(ptr->compiled_data + 4, &ssint, 4);
    ptr->compiled_data[8] = ptr->frame_header.status_flags;
    ptr->compiled_data[9] = ptr->frame_header.format_flags;
    memcpy(ptr->compiled_data + 10, body, body_size);
    free(body);
    return ptr->compiled_data_size = ptr->compiled_non_embedded_data_size = body_size + 10;
    }

static int id3_compile_chap_frame(struct id3_frame *ptr, int embedded_size)
    {
    struct id3_chap_frame_data *dptr;
    char *body, *bptr;
    int body_size, text_size;
    uint32_t ssint;
    
    dptr = ptr->data;
    if (!(body = bptr = malloc(body_size = 17 + (text_size = strlen(dptr->identifier)) + embedded_size)))
        {
        fprintf(stderr, "id3_compile_chap_frame: malloc failure\n");
        return 0;
        }
    strcpy(bptr, dptr->identifier);
    bptr += (text_size + 1);
    memcpy(bptr, dptr->start_ms, 16);
    if (!(ptr->compiled_data = malloc(body_size + 10)))
        {
        fprintf(stderr, "id3_compile_chap_frame: malloc failure\n");
        return 0;
        }
    memcpy(ptr->compiled_data, ptr->frame_header.frame_id, 4);
    id3_syncsafe_int(body_size, &ssint);
    memcpy(ptr->compiled_data + 4, &ssint, 4);
    ptr->compiled_data[8] = ptr->frame_header.status_flags;
    ptr->compiled_data[9] = ptr->frame_header.format_flags;
    memcpy(ptr->compiled_data + 10, body, body_size);
    free(body);
    ptr->compiled_non_embedded_data_size = body_size + 10 - embedded_size;
    return ptr->compiled_data_size = body_size + 10;
    }

static int id3_compile_frames(struct id3_frame *ptr)
    {
    int embedded_size = 0, chained_size = 0;
    
    if (ptr->first_embedded_frame)
        embedded_size = id3_compile_frames(ptr->first_embedded_frame);
    if (ptr->next)
        chained_size = id3_compile_frames(ptr->next);
    if (!strcmp(ptr->frame_header.frame_id, "TLEN"))
        return chained_size + id3_compile_numeric_frame(ptr, embedded_size);
    if (ptr->frame_header.frame_id[0] == 'T' && strcmp(ptr->frame_header.frame_id, "TXXX"))
        return chained_size + id3_compile_text_frame(ptr, embedded_size);
    if (!strcmp(ptr->frame_header.frame_id, "CHAP"))
        return chained_size + id3_compile_chap_frame(ptr, embedded_size);
    fprintf(stderr, "id3_compile_frames: this frame is unsupported: %s\n", ptr->frame_header.frame_id);
    return chained_size;
    }

static void id3_collect_frame_data(struct id3_frame *frame, char **wp)
    {
    if (frame->next)
        id3_collect_frame_data(frame->next, wp);
    if (frame->compiled_data)
        {
        memcpy(*wp, frame->compiled_data, frame->compiled_data_size);
        *wp += frame->compiled_non_embedded_data_size;
        if (frame->first_embedded_frame)
            {
            id3_collect_frame_data(frame->first_embedded_frame, wp);
            }
        free(frame->compiled_data);
        }
    }

void id3_compile(struct id3_tag *tag)
    {
    struct id3_frame *ptr;
    int chained_size;
    uint32_t ssint;
    char *wp;
    
    fflush(g.out);
    ptr = tag->first_frame;
    if (ptr)
        chained_size = id3_compile_frames(tag->first_frame);
    else
        return;
    if (!(tag->tag_data = calloc(1, tag->tag_data_size = chained_size + 10 + tag->padding)))
        {
        fprintf(stderr, "id3_compile: malloc failure\n");
        tag->tag_data = NULL;
        tag->tag_data_size = 0;
        return;
        }
    memcpy(tag->tag_data, "ID3\x04\x00\x00", 6);
    id3_syncsafe_int(tag->tag_data_size - 10, &ssint);
    memcpy(tag->tag_data + 6, &ssint, 4);
    wp = tag->tag_data + 10;
    id3_collect_frame_data(tag->first_frame, &wp);
    }

void id3_embed_frame(struct id3_frame *parent, struct id3_frame *child)
    {
    child->next = parent->first_embedded_frame;
    if (child->next)
        child->next->prev = parent;
    parent->first_embedded_frame = child;
    }

void id3_add_frame(struct id3_tag *tag, struct id3_frame *frame)
    {
    frame->next = tag->first_frame;
    if (frame->next)
        frame->next->prev = frame;
    tag->first_frame = frame;
    }

struct id3_frame *id3_numeric_string_frame_new(char *identifier, int value)
    {
    struct id3_frame *frame;
    char string[20];
    
    if (!(frame = calloc(1, sizeof (struct id3_frame))))
        {
        fprintf(stderr, "id3_text_frame_new: malloc failure\n");
        return NULL;
        }
    strcpy(frame->frame_header.frame_id, identifier);
    snprintf(string, 20, "%d", value);
    frame->data = strdup(string);
    return frame;
    }

struct id3_frame *id3_text_frame_new(char *identifier, char *text, unsigned char encoding, int null_terminator)
    {
    struct id3_frame *frame;
    struct id3_text_frame_data *tframe_data;
    
    if (!(frame = calloc(1, sizeof (struct id3_frame))))
        {
        fprintf(stderr, "id3_text_frame_new: malloc failure\n");
        return NULL;
        }
    strcpy(frame->frame_header.frame_id, identifier);
    if (!(tframe_data = calloc(1, sizeof (struct id3_text_frame_data))))
        {
        fprintf(stderr, "id3_text_frame_new: malloc failure\n");
        return NULL;
        }
    frame->data = tframe_data;
    tframe_data->text = strdup(text);
    tframe_data->text_encoding = encoding;
    tframe_data->null_terminator = null_terminator;
    return frame;
    }

struct id3_frame *id3_chap_frame_new(char *unique_id, uint32_t start_ms, uint32_t end_ms, uint32_t start_byte, uint32_t end_byte)
    {
    struct id3_frame *frame;
    struct id3_chap_frame_data *cframe_data;

    if (!(frame = calloc(1, sizeof (struct id3_frame))))
        {
        fprintf(stderr, "id3_chap_frame_new: malloc failure\n");
        return NULL;
        }
    strcpy(frame->frame_header.frame_id, "CHAP");
    if (!(cframe_data = calloc(1, sizeof (struct id3_chap_frame_data))))
        {
        fprintf(stderr, "id3_chap_frame_new: malloc failure\n");
        return NULL;
        }
    frame->data = cframe_data;
    cframe_data->identifier = strdup(unique_id);
    id3_make_be(cframe_data->start_ms, start_ms);
    id3_make_be(cframe_data->end_ms, end_ms);
    id3_make_be(cframe_data->start_byte, start_byte);
    id3_make_be(cframe_data->end_byte, end_byte);
    return frame;
    }

struct id3_tag *id3_tag_new(int flags, int padding)
    {
    struct id3_tag *tag;
    
    if (!(tag = calloc(1, sizeof (struct id3_tag))))
        {
        fprintf(stderr, "id3_tag_new: malloc failure\n");
        return NULL;
        }
    tag->header.flags = flags;
    tag->padding = padding;
    return tag;
    }
