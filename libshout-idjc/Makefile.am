## Process this file with automake to produce Makefile.in

AUTOMAKE_OPTIONS = 1.6 foreign
ACLOCAL_AMFLAGS = -I m4

SUBDIRS = include src

EXTRA_DIST = m4/acx_pthread.m4 \
	m4/ogg.m4 m4/vorbis.m4 m4/xiph_compiler.m4 m4/xiph_net.m4 \
	m4/xiph_types.m4

docdir = $(datadir)/doc/$(PACKAGE)
doc_DATA = COPYING NEWS README

m4datadir = $(datadir)/aclocal

if HAVE_PKGCONFIG
  pkgconfigdir = $(libdir)/pkgconfig
  pkgconfig_DATA = shout-idjc.pc
endif

debug:
	$(MAKE) all CFLAGS="@DEBUG@"

profile:
	$(MAKE) all CFLAGS="@PROFILE@"
