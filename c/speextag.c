/*
#   speextag.c: reads/writes speex metadata tags
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
#ifdef HAVE_SPEEX

#include "gnusource.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <unistd.h>
#include <ogg/ogg.h>
#include "speextag.h"
#include "bsdcompat.h"
#include "main.h"

#define TRUE  1
#define FALSE 0

#define readint(buf, base) (((buf[base+3]<<24)&0xff000000)| \
                                    ((buf[base+2]<<16)&0xff0000)| \
                                    ((buf[base+1]<<8)&0xff00)| \
                                     (buf[base]&0xff))

#define writeint(buf, base, val)  buf[base+3] = ((val) >> 24) & 0xff; \
                                             buf[base+2] = ((val) >> 16) & 0xff; \
                                             buf[base+1] = ((val) >> 8 ) & 0xff; \
                                             buf[base]   = (val) & 0xff

#define INIT_PATHLENGTH 256

enum packet_t { INITIAL_PACKET, TAG_PACKET, SUBSEQUENT_PACKETS };

/* nlcount: return a count of the number of new lines in a string */
static int nlcount(char *s)
    {
    int n;

    for (n = 0; *s; s++)
        if (*s == '\n')
            n++;

    return n;
    }

static int build_tag_packet(ogg_packet *op, char *createdby, char *taglist)
    {
    size_t cb_len, tl_len;
    int    newlines;
    char  *s, *t = taglist, *e;
    int    o = 0;

    cb_len = strlen(createdby);
    tl_len = strlen(taglist);
    newlines = nlcount(taglist);

    op->bytes = cb_len + 3 * newlines + tl_len + 8;
    if (!(s = (char *)(op->packet = malloc(op->bytes))))
        {
        fprintf(stderr, "build_tag_packet: malloc failure\n");
        return FALSE;
        }

    writeint(s, o, cb_len);
    o += 4;
    memcpy(s + o, createdby, cb_len);
    o += cb_len;

    writeint(s, o, newlines);
    o += 4;

    while (newlines--)
        {
        e = strchr(t, '\n');
        writeint(s, o, (int)(e - t));
        o += 4;
        memcpy(s + o, t, e - t);
        o += e - t;
        t = e + 1;
        }

    if (o != op->bytes)
        {
        fprintf(stderr, "build_tag_packet: warning, offset is %d and available buffer is size %d\n", o, (int)op->bytes);
        }

    return TRUE;
    }

/* get_id3_size: returns the size of the id3v2 tag if present */
static int get_id3_size(FILE *fp)
    {
    int id3size = 0;

    if (fgetc(fp) == 'I' && fgetc(fp) == 'D' && fgetc(fp) == '3' && fgetc(fp) != '\xFF' && fgetc(fp) != '\xFF')
        {
        fprintf(stderr, "ID3 tag detected\n");
        fgetc(fp);
        id3size =  fgetc(fp);
        id3size <<= 7;
        id3size |= fgetc(fp);
        id3size <<= 7;
        id3size |= fgetc(fp);
        id3size <<= 7;
        id3size |= fgetc(fp);
        id3size += 10;
        }

    rewind(fp);
    return id3size;
    }

void speex_tag_read(char *pathname)
    {
    FILE *fp;
    char *buffer, *s, *e;
    int   bytes;
    int   first = TRUE;
    int   packet_no = 0;
    int   id3size;
    int   offset = 0;
    int   size;
    int   tags;
    ogg_sync_state    oy;
    ogg_page          og;
    ogg_stream_state  os;
    ogg_packet        op;

    //memset(&og, 0, sizeof (ogg_page));
    //memset(&op, 0, sizeof (ogg_packet));

    if (!(fp = fopen(pathname, "r")))
        {
        fprintf(stderr, "speex_tag_read: could not open media file for tag reading\n");
        goto fail0;
        }

    if ((id3size = get_id3_size(fp)))
        fseek(fp, id3size, SEEK_CUR);

    ogg_sync_init(&oy);

    for (;;)
        {
        while (ogg_sync_pageout(&oy, &og) != 1)
            {
            buffer = ogg_sync_buffer(&oy, 4096);
            bytes = fread(buffer, 1, 4096, fp);
            ogg_sync_wrote(&oy, bytes);
            if (bytes == 0)
                {
                fprintf(stderr, "speex_tag_read: file came to an unexpected end\n");
                if (!first)
                    goto fail3;
                goto fail2;
                }
            }

        fprintf(stderr, "got an ogg page\n");

        if (first && ogg_page_pageno(&og) == 0)
            {
            if (ogg_stream_init(&os, ogg_page_serialno(&og)))
                {
                fprintf(stderr, "speex_tag_read: call to ogg_stream_init failed\n");
                goto fail2;
                }
            fprintf(stderr, "initialised stream\n");
            first = FALSE;
            }

        if (first || ogg_stream_pagein(&os, &og) == -1)
            continue;

        while (ogg_stream_packetout(&os, &op) != 0)
            {
            ++packet_no;
            if (packet_no == 1)
                {
                fprintf(stderr, "packet 1\n");
                if (ogg_page_pageno(&og) != 0)
                    {
                    fprintf(stderr, "speex_tag_read: first packet has incorrect ogg page number\n");
                    goto fail3;
                    }

                if (op.granulepos != 0 || op.bytes < 8 || memcmp("Speex   ", op.packet, 5))
                    {
                    fprintf(stderr, "speex_tag_read: header mismatch - does not appear to be a speex file\n");
                    goto fail3;
                    }
                else
                    fprintf(stderr, "found speex header\n");
                }

            if (packet_no == 2)
                {
                fprintf(stderr, "packet 2\n");
                if (ogg_page_pageno(&og) <= 0)
                    {
                    fprintf(stderr, "speex_tag_read: second packet has incorrect ogg page number\n");
                    goto fail3;
                    }

                if (op.granulepos != 0)
                    {
                    fprintf(stderr, "speex_tag_read: second packet has incorrect granule pos\n");
                    goto fail3;
                    }

                if (op.bytes < 8)
                    {
                    fprintf(stderr, "speex_tag_read: second packet is too small to be a valid metadata packet\n");
                    goto fail3;
                    }

                s = (char *)op.packet;
                e = s + op.bytes;
                offset = 0;

                size = readint(s, offset);
                offset += 4;
                if (s + offset + size + 4 > e)
                    {
                    fprintf(stderr, "speex_tag_read: corrupt tag\n");
                    goto fail3;
                    }
                else
                    {
                    fprintf(g.out, "idjcmixer: speexcreatedread ");
                    if (!(fwrite(s + offset, size, 1, stdout)))
                        goto fail3;
                    fputc('\n', g.out);
                    offset += size;
                    }

                tags = readint(s, offset);
                offset += 4;
                fprintf(stderr, "there are %d tags on this file\n", tags);
                if (s + offset + tags * sizeof (int) > e)
                    {
                    fprintf(stderr, "speex_tag_read: corrupt tag\n");
                    goto fail3;
                    }

                while (tags--)
                    {
                    size = readint(s, offset);
                    offset += 4;
                    if (s + offset + size > e)
                        {
                        fprintf(stderr, "speex_tag_read: corrupt tag\n");
                        goto fail3;
                        }
                    else
                        {
                        fprintf(g.out, "idjcmixer: speextagread ");
                        if (!(fwrite(s + offset, size, 1, stdout)))
                            goto fail3;
                        fputc('\n', g.out);
                        offset += size;
                        }
                    }
                
                if (s + offset != e)
                    {
                    fprintf(stderr, "did not finish at end of packet!\n");
                    goto fail3;
                    }

                fprintf(stderr, "packet appears to be totally correct\n");

                fprintf(g.out, "idjcmixer: speextagread end\n");
                fflush(g.out);
                ogg_stream_clear(&os);
                ogg_sync_clear(&oy);
                return;
                }
            }
        fprintf(stderr, "going around for another packet\n");
        }

    fail3:
        ogg_stream_clear(&os);
    fail2:
        ogg_sync_clear(&oy);
    //fail1:
        fclose(fp);
    fail0:
        fprintf(g.out, "idjcmixer: speexfileinfo Not Valid\n");
        fflush(g.out);
    }

void speex_tag_write(char *suppliedpathname, char *createdby, char *taglist)
    {
    char *pathname;
    char *tmpname;
    char *buffer;
    FILE *fpr, *fpw;
    int   id3size;
    char *copybuf;
    int   first = TRUE;
    size_t bytes;
    enum  packet_t packet_type = INITIAL_PACKET;
    ogg_sync_state    oy;
    ogg_page          ogr;
    ogg_page          ogw;
    ogg_stream_state  osr;
    ogg_stream_state  osw;
    ogg_packet        op;

    void flush_and_write()
        {
        while (ogg_stream_flush(&osw, &ogw))
            {
            if (fwrite(ogw.header, ogw.header_len, 1, fpw) == 0 ||
                 fwrite(ogw.body, ogw.body_len, 1, fpw) == 0)
                break;
            }
        }

    if (!(pathname = canonicalize_file_name(suppliedpathname)))
        {
        fprintf(stderr, "speex_tag_write: supplied pathname did not resolve\n");
        goto failA;
        }

    fprintf(stderr, "%s\n%s\n", suppliedpathname, pathname);

    if (!(tmpname = malloc(strlen(pathname) + 5)))
        {
        fprintf(stderr, "speex_tag_write: malloc failure\n");
        goto failB;
        }

    sprintf(tmpname, "%s%s", pathname, ".TMP");

    fpr = fopen(pathname, "r");
    fpw = fopen(tmpname, "w");
    if (!fpr || !fpw)
        {
        fprintf(stderr, "speex_tag_write: file io error\n");
        goto fail0;
        }

    if (!(copybuf = malloc(id3size = get_id3_size(fpr))))
        {
        fprintf(stderr, "speex_tag_write: malloc failure\n");
        goto fail0;
        }

    if (id3size)
        {
        if (!fread(copybuf, id3size, 1, fpr))
            {
            fprintf(stderr, "speex_tag_write: file io error\n");
            goto fail1;
            }
    
        if (!fwrite(copybuf, id3size, 1, fpw))
            {
            fprintf(stderr, "speex_tag_write: file io error\n");
            goto fail1;
            }
        }

    ogg_sync_init(&oy);

    for (;;)
        {
        while (ogg_sync_pageout(&oy, &ogr) != 1)
            {
            buffer = ogg_sync_buffer(&oy, 4);
            bytes = fread(buffer, 1, 1, fpr);
            ogg_sync_wrote(&oy, bytes);
            if (bytes == 0)
                {
                fprintf(stderr, "speex_tag_read: file came to an unexpected end\n");
                if (!first)
                    goto fail4;
                goto fail2;
                }
            }

        fprintf(stderr, "got an ogg page\n");

        if (first)
            {
            if (ogg_page_bos(&ogr))
                {
                if (ogg_stream_init(&osr, ogg_page_serialno(&ogr)))
                    {
                    fprintf(stderr, "speex_tag_write: call to ogg_stream_init failed\n");
                    goto fail2;
                    }
    
                if (ogg_stream_init(&osw, ogg_page_serialno(&ogr)))
                    {
                    fprintf(stderr, "speex_tag_write: call to ogg_stream_init failed\n");
                    goto fail3;
                    }
    
                fprintf(stderr, "initialised stream\n");
                first = FALSE;
                }
            else
                {
                fprintf(stderr, "speex_tag_write: unexpected non bos packet\n");
                goto fail2;
                }
            }

        if (ogg_stream_pagein(&osr, &ogr) == -1)
            {
            fprintf(stderr, "speex_tag_write: got bad ogg page\n");
            goto fail4;
            }

        while (ogg_stream_packetout(&osr, &op) != 0)
            {
            switch (packet_type)
                {
                case INITIAL_PACKET:
                    //fprintf(stderr, "header packet\n");
                    if (ogg_page_pageno(&ogr) != 0)
                        {
                        fprintf(stderr, "speex_tag_read: first packet has incorrect ogg page number\n");
                        goto fail4;
                        }

                    ogg_stream_packetin(&osw, &op);
                    flush_and_write();
                    packet_type = TAG_PACKET;
                    break;
                case TAG_PACKET:
                    //fprintf(stderr, "metadata packet\n");
                    if (!build_tag_packet(&op, createdby, taglist))
                        {
                        fprintf(stderr, "speex_tag_read: failed to build tagging metadata packet\n");
                        goto fail4;
                        }

                    ogg_stream_packetin(&osw, &op);
                    flush_and_write();
                    ogg_packet_clear(&op);
                    packet_type = SUBSEQUENT_PACKETS;
                    break;
                case SUBSEQUENT_PACKETS:
                    //fprintf(stderr, "subsequent packet\n");
                    ogg_stream_packetin(&osw, &op);
                    if (op.granulepos != -1)
                        flush_and_write();
                    break;
                }
            }

        if (op.e_o_s)
            {
            fprintf(stderr, "last packet processed\n");
            ogg_stream_clear(&osw);
            ogg_stream_clear(&osr);
            ogg_sync_clear(&oy);

            /* copy all remaining bytes in the file, e.g. an id3 version 1 tag */
            if (!(copybuf = realloc(copybuf, 4096)))
                {
                fprintf(stderr, "speex_tag_read: malloc failure\n");
                goto fail4;
                }

            do
                {
                bytes = fread(copybuf, 1, 4096, fpr);
                if (fwrite(copybuf, 1, bytes, fpw) != bytes)
                    break;
                } while (bytes == 4096);

            free(copybuf);
            fclose(fpw);
            fclose(fpr);
            rename(tmpname, pathname);
            free(tmpname);
            free(pathname);
            return;
            }
        }

    fail4:
        ogg_stream_clear(&osw);
    fail3:
        ogg_stream_clear(&osr);
    fail2:
        ogg_sync_clear(&oy);
    fail1:
        if (copybuf)
            free(copybuf);
    fail0:
        if (fpr)
            fclose(fpr);
        if (fpw)
            fclose(fpw);
        free(tmpname);
    failB:
        free(pathname);
    failA:
        fprintf(stderr, "speex_tag_write failed\n");
    }

#endif /* HAVE_SPEEX */
