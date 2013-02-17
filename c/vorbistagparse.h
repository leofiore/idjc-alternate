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
struct vtag_block_private;

struct vtag_block {
    char *data;
    size_t length;
    struct vtag_block_private *private;
};

enum vtag_error {VE_OK, VE_ALLOCATION, VE_CROPPED, VE_TRAILING,
                    VE_SHORT_COMMENT, VE_MISSING_SEPARATOR,
                    VE_MISSING_VALUE, VE_INVALID_KEY};

enum vtag_lookup_mode {VLM_FIRST, /* the first tag of given key */
                        VLM_LAST,  /* last tag of a given key */
                        VLM_MERGE  /* combine like key data into one string */
};

/* vtag_new: a new empty vorbis tag
 * vendor_string: the vendor string of course
 * error: optional, can point to NULL
 */
struct vtag *vtag_new(const char *vendor_string, int *error);

/* vtag_parse: parse a vorbis tag data chunk
 * the data chunk must be framed exactly to not be rejected
 * all tags within must be of key=value form and keys
 * must only contain legal characters
 * error: optional, can point to NULL
 */
struct vtag *vtag_parse(void *data, size_t bytes, int *error);

/* vtag_comment_count:
 * return value: the number of comments attached to a given key, key
 */
int vtag_comment_count(struct vtag *s, char const *key);

/* vtag_lookup: look up a tag by its key
 * key: this is case independent
 * mode: how to handle multiple keys
 * sep: separator string in VLM_MERGE mode or NULL
 * return value: the tag data requested or NULL -- the caller is
 * responsible for freeing the returned data
 */
char *vtag_lookup(struct vtag *s, char const *key, enum vtag_lookup_mode mode, char *sep);

/* vtag_append: append a new key=value comment
 * key: must consist of the printable ASCII characters 0x20 to 0x7D inclusive
 * value: a string that must not have zero length
 */
int vtag_append(struct vtag *s, char const *key, char const *value);

/* vtag_block_init: initialise output data structure for vtag_serialize
 * return value: 0 if failure, otherwise success */
int vtag_block_init(struct vtag_block *block);

/* vtag_block_cleanup: frees memory */
void vtag_block_cleanup(struct vtag_block *block);

/* vtag_serialize: constructs a new vorbis comment block
 * 
 * block: the output data structure initialised with vtag_block_init
 * prefix: optional prefix string for the data block e.g. OpusTags or NULL
 * return value: VE_OK or VE_ALLOCATION
 */
int vtag_serialize(struct vtag *s, struct vtag_block *block, char const *prefix);

/* vtag_encoder: returns the vendor string of the vorbis tag */
char const *vtag_vendor_string(struct vtag *);

/* vtag_cleanup: dispose of data structure returned by vtag_parse */
void vtag_cleanup(struct vtag *);

/* vtag_strerror:
 * return value: human readable form of the error code
 */
char const *vtag_strerror(int error);
