/*
#   id3.h: the id3 tag reading/writing part of idjc
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


enum { ID3_LATIN1=0x00, ID3_UTF_8=0x3 };

struct id3_frame_header
    {
    char frame_id[5];
    unsigned int size;
    unsigned char status_flags;
    unsigned char format_flags;
    };

struct id3_frame
    {
    char *compiled_data;
    int compiled_data_size;
    int compiled_non_embedded_data_size;
    struct id3_frame_header frame_header;
    struct id3_frame *first_embedded_frame;
    struct id3_frame *next;
    struct id3_frame *prev;
    struct id3_tag *tag;
    void *data;          /* eg. points to struct id3_text_frame_data */
    };

struct id3_chap_frame_data
    {
    char *identifier;
    unsigned char start_ms[4];
    unsigned char end_ms[4];
    unsigned char start_byte[4];
    unsigned char end_byte[4];
    };

struct id3_text_frame_data
    {
    unsigned char text_encoding;
    char *text;
    int null_terminator;
    };

struct id3_extended_header
    {
    unsigned int size;
    int n_flagbytes;
    unsigned char data[1];
    };

struct id3_header
    {
    unsigned short int version;
    unsigned int size;
    unsigned char flags;
    };

struct id3_tag
    {
    void *tag_data;
    size_t tag_data_size;
    struct id3_header header;
    struct id3_extended_header *extended_header;
    struct id3_frame *first_frame;
    int padding;
    };

struct id3_tag *id3_tag_new(int flags, int padding);
struct id3_frame *id3_text_frame_new(char *identifier, char *text, unsigned char encoding, int null_terminator);
struct id3_frame *id3_numeric_string_frame_new(char *identifier, int value);
void   id3_add_frame(struct id3_tag *tag, struct id3_frame *frame);
void   id3_embed_frame(struct id3_frame *parent, struct id3_frame *child);
struct id3_frame *id3_chap_frame_new(char *unique_id, uint32_t start_ms, uint32_t end_ms, uint32_t start_byte, uint32_t end_byte);
void id3_compile(struct id3_tag *tag);
void id3_decompile(struct id3_tag *tag);
void id3_remove_frame(struct id3_frame *frame);
void id3_frame_destroy(struct id3_frame *frame);
void id3_tag_destroy(struct id3_tag *tag);
