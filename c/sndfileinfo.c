/*
#   sndfileinfo.c: Provide information on wav files
#   Copyright (C) 2006 Stephen Fairchild (s-fairchild@users.sourceforge.net)
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
#include <sndfile.h>
#include "sndfileinfo.h"
#include "main.h"

int sndfileinfo(char *pathname)
    {
    SF_INFO sfinfo;
    SNDFILE *handle;
    const char *artist, *title, *album;

    if (!(handle = sf_open(pathname, SFM_READ, &sfinfo)))
        {
        fprintf(stderr, "sndfileinfo failed to open file %s\n", pathname);
        return 0;
        }
    artist = sf_get_string(handle, SF_STR_ARTIST);
    title = sf_get_string(handle, SF_STR_TITLE);
    album = sf_get_string(handle, SF_STR_ALBUM);
 
    fprintf(g.out, "idjcmixer: sndfileinfo length=%f\n", (float)sfinfo.frames / sfinfo.samplerate);
    if (artist && title)
        {
        fprintf(g.out, "idjcmixer: sndfileinfo artist=%s\n", artist);
        fprintf(g.out, "idjcmixer: sndfileinfo title=%s\n", title);
        if (album)
            fprintf(g.out, "idjcmixer: sndfileinfo album=%s\n", album);
        }
    fprintf(g.out, "idjcmixer: sndfileinfo end\n");
    sf_close(handle);
    fflush(g.out);
    return 1;
    }
