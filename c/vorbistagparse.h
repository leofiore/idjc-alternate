/*
#   vorbistagparse.h: parse vorbis tags 
#   Copyright (C) 2013 Stephen Fairchild (s-fairchild@users.sourceforge.net)
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

#include <glib.h>

struct vtag;

enum vtag_error = {VE_OK, VE_ALLOCATION, VE_CROPPED, VE_TRAILING,
                    VE_SHORT_COMMENT, VE_MISSING_SEPARATOR,
                    VE_MISSING_VALUE, VE_INVALID_KEY};

enum vtag_lookup_mode = {VLM_FIRST, /* the first tag of given key */
                         VLM_LAST,  /* last tag of a given key */
                         VLM_MERGE  /* combine like key data into one string */
};

/* vtag_parse: parse a vorbis tag data chunk */
struct vtag *vtag_parse(void *data, size_t bytes, int *error);

/* vtag_lookup: look up a tag by its key
 * mode: how to handle multiple keys
 * sep: separator string in VLM_MERGE mode or NULL
 * return value: the tag data requested or NULL -- the caller is
 * responsible for freeing the returned data
 */
char *vtag_lookup(struct vtag *vtag, char *key, enum vtag_lookup_mode mode, char *sep);

/* vtag_encoder: returns the vendor string of the vorbis tag */
char const *vtag_vendor_string(struct vtag *);

/* vtag_cleanup: dispose of data structure returned by vtag_parse */
void vtag_cleanup(struct vtag *);

/* vtag_error_string:
 * return value: human readable form of the error code
 */
char *vtag_error_string(int error);
