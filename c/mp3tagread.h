/*
#   mp3tagread.h: reads id3 tag + chapter info + Xing header
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

#ifndef MP3TAGREAD_H
#define MP3TAGREAD_H

#include "../config.h"

#include <stdio.h>

struct id3data
    {
    unsigned char *data;
    int size;
    };

struct chapter_text
    {
    char *text;
    int encoding;
    size_t length;
    };

struct chapter
    {
    struct chapter *next;
    unsigned int time_begin;
    unsigned int time_end;
    unsigned int byte_begin;
    unsigned int byte_end;
    struct chapter_text artist;
    struct chapter_text title;
    struct chapter_text album;
    };

struct mp3taginfo
    {
    /* from the ID3 tag */
    int version;
    int flags;
    int tlen;
    struct chapter *first_chapter;
    struct chapter *last_chapter;
    /* from the Xing tag */
    int have_frames;
    int frames;
    int have_bytes;
    int bytes;
    int have_toc;
    unsigned char toc[100];
    int first_byte;
    int start_frames_drop;
    int end_frames_drop;
    };

struct tag_lookup
    {
    char *id;
    void (*fn)(struct mp3taginfo *, unsigned char *);
    };

void mp3_tag_read(struct mp3taginfo *ti, FILE *fp);
void mp3_tag_cleanup(struct mp3taginfo *ti);
struct chapter *mp3_tag_chapter_scan(struct mp3taginfo *ti, unsigned time_ms);

#endif /* MP3TAGREAD_H */
