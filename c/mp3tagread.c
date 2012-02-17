/*
#   mp3tagread.c: reads id3 tag including any chapter info + Xing header
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

#include "../config.h"

#include "gnusource.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "mp3tagread.h"
#include "bsdcompat.h"

#define TRUE 1
#define FALSE 0


#if 0
static void unsynchronise(struct mp3decode_id3data *us)
    {
    unsigned char *ptr, *end, *op;
    int count = 0;
    struct mp3decode_id3data out;

    for (ptr = us->data, end = ptr + us->size - 1; ptr < end; ptr++)
        if (ptr[0] == 0xFF && (ptr[1] == 0x00 || (ptr[1] & 0xE0) == 0xE0))
            count++;

    out.size = us->size + count;
    if (!(out.data = malloc(out.size)))
        {
        fprintf(stderr, "unsync: malloc failure\n");
        return;
        }

    for (ptr = us->data, op = out.data; ptr < end; ptr++)
        {
        *op++ = *ptr;
        if (ptr[0] == 0xFF && (ptr[1] == 0x00 || (ptr[1] & 0xE0) == 0xE0))
            *op++ = 0x00;
        }

    free(us->data);
    *us = out;
    }
#endif

static void resynchronise(struct id3data *us)
    {
    unsigned char *ptr, *end, *op;
    int count = 0;
    struct id3data out;

    for (ptr = us->data, end = ptr + us->size -1; ptr < end; ptr++)
        if (ptr[0] == 0xFF && ptr[1] == 0x00)
            count++;

    out.size = us->size - count;
    if (!(out.data = malloc(out.size)))
        {
        fprintf(stderr, "resynchronise: malloc failure\n");
        return;
        }

    for (ptr = us->data, op = out.data; ptr <= end; ptr++)
        {
        *op++ = *ptr;
        if (ptr[0] == 0xFF)
            ptr++;
        }

    free(us->data);
    *us = out;
    fprintf(stderr, "resynchronise: finished\n");
    }

static int get_frame_size(unsigned char *start, int id3version)
    {
    int size;

    switch (id3version)
        {
        case 3:
            size  = start[4];
            size <<= 8;
            size |= start[5];
            size <<= 8;
            size |= start[6];
            size <<= 8;
            size |= start[7];
            break;
        case 4:
            size = start[4] & 0x7F;
            size <<= 7;
            size |= start[5] & 0x7F;
            size <<= 7;
            size |= start[6] & 0x7F;
            size <<= 7;
            size |= start[7] & 0x7F;
            break;
        default:
            fprintf(stderr, "get_frame_size: unhandled id3v2 version %d\n", id3version);
            size = 0x7FFFFFFF;
        }
    return size;
    }

static void set_id3_data(struct id3data *us, unsigned char *start, int id3version)
    {
    us->size = get_frame_size(start, id3version);

    if (!(us->data = malloc(us->size)))
        {
        fprintf(stderr, "set_id3_data: malloc failure\n");
        return;
        }

    memcpy(us->data, start + 10, us->size);
    }

static unsigned int bigendianint(unsigned char *ptr)
    {
    unsigned int a;

    a = *ptr++;
    a = (a << 8) | *ptr++;
    a = (a << 8) | *ptr++;
    return (a << 8) | *ptr;
    }

#if 0
static int decode_tit2(struct mp3taginfo *ti, unsigned char *start, struct chapter *chap)
    {
    struct id3data us;

    set_id3_data(&us, start, ti->version);
    if (ti->version == 4 && (start[9] & 0x2))
        resynchronise(&us);
    if (((chap->encoding = us.data[0]) > 1 && ti->version == 3) || chap->encoding > 3)
        {
        fprintf(stderr, "decode_tit2: unsupported character encoding\n");
        goto bailout;
        }
    if (us.data[us.size - 1])  /* handle potential null termination */
        {
        chap->length = us.size - 1;
        fprintf(stderr, "not null terminated\n");
        }
    else
        {
        chap->length = us.size - 2;
        fprintf(stderr, "null terminated\n");
        }
    if (!(chap->text = calloc(1, chap->length + 1)))
        goto bailout;
    memcpy(chap->text, us.data + 1, chap->length);
    free(us.data);
    return 1;
    bailout:
    free(us.data);
    return 0;
    }
#endif

static int decode_text_tag(struct mp3taginfo *ti, unsigned char *start, struct chapter_text *ct)
    {
    struct id3data us;
    size_t l;
    char *src, *dest;

    if (ct->text)     /* start over if there is a duplicate tag */
        {
        free(ct->text);
        memset(ct, '\0', sizeof (struct chapter_text));
        }

    set_id3_data(&us, start, ti->version);
    if (ti->version == 4 && (start[9] & 0x2))
        resynchronise(&us);
    if (((ct->encoding = us.data[0]) > 1 && ti->version == 3) || ct->encoding > 3)
        {
        fprintf(stderr, "decode_tit2: unsupported character encoding\n");
        goto bailout;
        }
    if (us.data[us.size - 1])  /* handle potential null termination */
        {
        ct->length = us.size - 1;
        fprintf(stderr, "not null terminated\n");
        }
    else
        {
        ct->length = us.size - 2;
        fprintf(stderr, "null terminated\n");
        }
    if (!(ct->text = malloc(ct->length + 1)))
        {
        fprintf(stderr, "malloc failure\n");
        goto bailout;
        }

    /* copy, substituting separating nulls with / characters */
    for (src = (char *)us.data + 1, dest = ct->text, l = ct->length; l; --l, ++src, ++dest)
         if (*src != '\0')  
             *dest = *src;
         else
             *dest = '/';
    *dest = '\0';
    
    free(us.data);
    return 1;
    bailout:
    free(us.data);
    return 0;
    }

static void decode_chap(struct mp3taginfo *ti, unsigned char *start)
    {
    struct id3data us;
    unsigned char *ptr, *end;
    struct chapter *chapdata;
    struct chapter_text *chaptext;
    int adv;

    if (!(chapdata = calloc(1, sizeof (struct chapter))))
        {
        fprintf(stderr, "decode_chap: malloc failure\n");
        return;
        }
    
    set_id3_data(&us, start, ti->version);
    if (ti->version == 4 && ((ti->flags & 0x80) || (start[9] & 0x2)))
        resynchronise(&us);
    for (ptr = us.data, end = us.data + us.size; ptr < end && *ptr++;);
    if (ptr + 16 > end)
        {
        fprintf(stderr, "decode_chap: chapter tag is too small\n");
        free(us.data);
        return;
        }
    
    chapdata->time_begin = bigendianint(ptr);
    chapdata->time_end   = bigendianint(ptr += 4);
    chapdata->byte_begin = bigendianint(ptr += 4);
    chapdata->byte_end   = bigendianint(ptr += 4);
    ptr += 4;
    for (; (ptr + 10 < end) && (ptr + (adv = 10 + get_frame_size(ptr, ti->version)) <= end); ptr += adv)
        {
        if (!memcmp(ptr, "TPE1", 4))
            chaptext = &chapdata->artist;
        else if (!memcmp(ptr, "TIT2", 4))
            chaptext = &chapdata->title;
        else if (!memcmp(ptr, "TALB", 4))
            chaptext = &chapdata->album;
        else
            continue;
        
        if (!(decode_text_tag(ti, ptr, chaptext)))
            {
            free(us.data);
            return;
            }
        }

    if (!chapdata->artist.text)
        chapdata->artist.text = strdup("");
    if (!chapdata->title.text)
        chapdata->title.text = strdup("");
    if (!chapdata->album.text)
        chapdata->album.text = strdup("");

    if (!(ti->first_chapter))
        ti->first_chapter = ti->last_chapter = chapdata;
    else
        {
        ti->last_chapter->next = chapdata;
        ti->last_chapter = chapdata;
        }

    fprintf(stderr, "Chapter info\ntime begin %d\ntime end %d\nbyte begin %d\nbyte end %d\n", chapdata->time_begin, chapdata->time_end, chapdata->byte_begin, chapdata->byte_end);
    fprintf(stderr, "Artist: %s\nTitle : %s\nAlbum : %s\n", chapdata->artist.text, chapdata->title.text, chapdata->album.text);
    free(us.data);
    }

static void decode_tlen(struct mp3taginfo *ti, unsigned char *start)
    {
    struct id3data us;
    char *buffer;

    set_id3_data(&us, start, ti->version);
    if (ti->version == 4 && ((ti->flags & 0x80) || (start[9] & 0x2)))
        resynchronise(&us);
    if (us.size == 0)
        ti->tlen = 0;
    else
        {
        if (!(buffer = strndup((char *)us.data, us.size + 1)))
            {
            fprintf(stderr, "decode_tlen: malloc failure\n");
            ti->tlen = 0;
            return;
            }
        ti->tlen = atoi(buffer);
        free(buffer);
        }

    free(us.data);
    fprintf(stderr, "Track length according to TLEN: %dms\n\n", ti->tlen);
    }

static void decode_id3_frames(struct mp3taginfo *ti, struct id3data *d)
    {
    unsigned char *start, *end;
    unsigned int adv;
    struct tag_lookup *lup;
    static struct tag_lookup lu[] =
        {{ "TLEN", decode_tlen },
         { "CHAP", decode_chap },
         { NULL, NULL }};

    for (start = d->data, end = d->data + d->size; start < end && *start; start += adv)
        {
        if (start + 10 > end || start + (adv = 10 + get_frame_size(start, ti->version)) > end)
            {
            fprintf(stderr, "decode_id3_frames: defective frame size discovered in tag\n");
            mp3_tag_cleanup(ti);
            return;
            }
        for (lup = lu; lup->id; lup++)
            if (!(memcmp(lup->id, start, 4)))
                lup->fn(ti, start);
        }
    }

static int id3_tag_read(struct mp3taginfo *ti, FILE *fp, int skip)
    {
    long start = ftell(fp);
    long tagsize, ehsize, frames_end;
    int minor, flags;
    struct id3data id;
    
    if (fgetc(fp) == 'I' && fgetc(fp) == 'D' && fgetc(fp) == '3')        /* check for ID3 signature */
        {
        ti->version = fgetc(fp); minor = fgetc(fp); ti->flags = flags = fgetc(fp);
        tagsize = fgetc(fp) & 0x7F;       /* 28 bits of tag size info packed into 4 bytes - big endian */
        tagsize <<= 7;                    /* most significant bit discarded - should be zero */
        tagsize |= fgetc(fp) & 0x7F;
        tagsize <<= 7;
        tagsize |= fgetc(fp) & 0x7F;
        tagsize <<= 7;
        tagsize |= fgetc(fp) & 0x7F;
        
        switch (minor != 0xFF ? ti->version : -1)
            {
            case 4:
                if (flags & 0x40)
                    {
                    ehsize = fgetc(fp) & 0x7F;       /* skip over the extended header */
                    ehsize <<= 7;
                    ehsize |= fgetc(fp) & 0x7F;
                    ehsize <<= 7;
                    ehsize |= fgetc(fp) & 0x7F;
                    ehsize <<= 7;
                    ehsize |= fgetc(fp) & 0x7F;
                    if (ehsize < tagsize)
                        fseek(fp, ehsize - 4, SEEK_CUR);
                    else
                        {
                        fprintf(stderr, "read_id3v2_tag: error, tag size not large enough for extended header\n");
                        fseek(fp, start + 10 + tagsize, SEEK_SET);
                        return TRUE;
                        }
                    }
            case 3:
                frames_end = start + 10 + tagsize;
                if (!skip)
                    break;
            default:
                fseek(fp, tagsize, SEEK_CUR);       /* skip over the tag */
                return TRUE;
            }

        if ((id.data = malloc(id.size = frames_end - ftell(fp))) == NULL || (!fread(id.data, id.size, 1, fp)))
            {
            fprintf(stderr, "read_id3_v2_tag: failed to read tag data\n");
            fseek(fp, start + 10 + tagsize, SEEK_SET);
            return TRUE;
            }

        if (ti->version == 3)
            {
            if (flags & 0x80)
                resynchronise(&id);
            if (flags & 0x40)              /* lose the extended header */
                {
                ehsize = bigendianint(id.data);
                if (ehsize <= id.size)
                    memcpy(id.data, id.data + ehsize, id.size -= ehsize);
                else
                    {
                    fprintf(stderr, "read_id3_tag: error, tag size not large enough for extended header\n");
                    fseek(fp, start + 10 + tagsize, SEEK_SET);
                    return TRUE;
                    }
                }
            }

        decode_id3_frames(ti, &id);
        free(id.data);
        if (flags & 0x10)                 /* skip over the footer if present */
            fseek(fp, 10, SEEK_CUR);
        return TRUE;
        }

    fseek(fp, start, SEEK_SET);       /* not ID3 so restore the file pointer */
    return FALSE;
    }

/********************************************************************************/

static int be32bitread(FILE *fp)
    {
    int rv;
    
    rv  = fgetc(fp);
    rv <<= 8;
    rv |= fgetc(fp);
    rv <<= 8;
    rv |= fgetc(fp);
    rv <<= 8;
    rv |= fgetc(fp);
    return rv;
    }

static void xing_tag_read(struct mp3taginfo *ti, FILE *fp)
    {
    unsigned char a, b, c;
    int mpeg1_f, mpeg_ix, mono_f, br_ix, sr_ix;
    int xing_offset, initial_offset, save_point = 0;
    int i, samples_per_frame, frame_length, padding;
    int bit_rate, sample_rate;
    int flags, b1, b2, b3;
    char xing_intro[4];
    char lame_intro[4];
    static int side_info_table[2][2] = { { 17, 9 } , { 32, 17 } };
    static int bitrate_table[2][15] = {
        { 0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160 },
        { 0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320 } };
    static int samplerate_table[4][4] = {
        { 11025, 12000,  8000, 0 },
        { 0,         0,     0, 0 },
        { 22050, 24000, 16000, 0 },
        { 44100, 48000, 32000, 0 } };
    
    initial_offset = ftell(fp);

    for (i = 0; i < 1024; i++)
        {
        while ((a = fgetc(fp)) != 0xFF)
            {
            if (feof(fp) || ferror(fp))
                goto no_tag;
            }

        if (((b = fgetc(fp)) & 0xE0) == 0xE0)
            {
            c = fgetc(fp);
            fgetc(fp);
            if ((br_ix = (c >> 4)) == 0xF || (b & 0x18) == 0x08 || (b & 0x6) != 0x2)
                goto no_tag;
            if ((mpeg_ix =  (b & 0x18) >> 3) == 1)
                goto no_tag;
            mpeg1_f = mpeg_ix == 0x3;
            br_ix   =   c >> 4;
            sr_ix   =  (c >> 2) & 0x3;
            padding =  (c & 0x2)           ? 1 : 0;
            mono_f  = ((c & 0xC0) == 0xC0) ? 1 : 0;
            samples_per_frame = mpeg1_f ? 1152 : 576;
            xing_offset = side_info_table[mpeg1_f][mono_f];
            bit_rate = bitrate_table[mpeg1_f][br_ix];
            sample_rate = samplerate_table[mpeg_ix][sr_ix];
            if (bit_rate == 0 || sample_rate == 0)
                frame_length = 0;
            else
                frame_length = samples_per_frame / 8 * bit_rate * 1000 / sample_rate + padding;
 
            while (xing_offset--)  /* check side info is 100% blank */
                if (fgetc(fp) || feof(fp) || ferror(fp))
                    goto no_tag;
 
            if (!fread(xing_intro, 4, 1, fp))
                goto no_tag;
 
            if (memcmp(xing_intro, "Info", 4) && memcmp(xing_intro, "Xing", 4))
                goto no_tag;
 
            fgetc(fp); fgetc(fp); fgetc(fp);
            flags = fgetc(fp);

            if (flags & 0x1)
                {
                ti->have_frames = 1;
                ti->frames = be32bitread(fp);
                if (!(ti->tlen) && sample_rate)
                    ti->tlen = ti->frames / sample_rate;
                fprintf(stderr, "frames %d\n", ti->frames);
                }
 
            if (flags & 0x2)
                {
                ti->have_bytes = 1;
                ti->bytes = be32bitread(fp);
                fprintf(stderr, "bytes %d\n", ti->bytes);
                }
 
            if (flags & 0x4)
                {
                ti->have_toc = fread(ti->toc, 100, 1, fp);
                fprintf(stderr, "toc has been read\n");
                }
                
            if (flags & 0x8)
                be32bitread(fp);

            if (!fread(lame_intro, 4, 1, fp))
                goto no_tag;
                
            if (!memcmp(lame_intro, "LAME", 4))
                {
                fprintf(stderr, "lame tag found\n");
                fseek(fp, 17, SEEK_CUR);
                b1 = fgetc(fp);
                b2 = fgetc(fp);
                b3 = fgetc(fp);
                ti->start_frames_drop = ((b1 << 4) | (b2 >> 4)) + 528;
                ti->end_frames_drop = (((b2 & 0xF) << 8) | b3);
                fprintf(stderr, "frames to drop %d and %d\n", ti->start_frames_drop, ti->end_frames_drop);
                fseek(fp, 12, SEEK_CUR);
                }
            else
                fseek(fp, -4, SEEK_CUR);

            if (!frame_length)
                save_point = ftell(fp);
  
            if (!(ti->have_bytes))
                {
                fprintf(stderr, "deriving number of bytes manually\n");
                fseek(fp, 0, SEEK_END);
                ti->bytes = ftell(fp) - initial_offset + frame_length;
                ti->have_bytes = 1;
                }

            if (frame_length)
                fseek(fp, initial_offset + frame_length, SEEK_SET);
            else
                {
                fprintf(stderr, "manually skipping to the next frame\n");
                fseek(fp, initial_offset + save_point, SEEK_SET);
                while (fgetc(fp) == '\0');
                fseek(fp, -1, SEEK_CUR);
                }
            
            ti->first_byte = ftell(fp);
            
            return;
            }
        }

    no_tag:
    fseek(fp, initial_offset, SEEK_SET);
    }

/********************************************************************************/

void mp3_tag_read(struct mp3taginfo *ti, FILE *fp)
    {
    if (id3_tag_read(ti, fp, FALSE))
        while(id3_tag_read(ti, fp, TRUE))
            fprintf(stderr, "Surplus ID3 tag skipped\n");
    xing_tag_read(ti, fp);
    }

void mp3_tag_cleanup(struct mp3taginfo *ti)
    {
    struct chapter *c = ti->first_chapter, *oldc;
    
    while ((oldc = c))
        {
        free(c->artist.text);
        free(c->title.text);
        free(c->album.text);
        c = c->next;
        free(oldc);
        }
    memset(ti, 0, sizeof (struct mp3taginfo));
    }

struct chapter *mp3_tag_chapter_scan(struct mp3taginfo *ti, unsigned time_ms)
    {
    struct chapter *c;

    for (c = ti->first_chapter; c; c = c->next)
        if (time_ms >= c->time_begin && (time_ms < c->time_end || c->next == NULL))
            return c;
    return NULL;
    }

