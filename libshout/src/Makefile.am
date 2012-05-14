## Process this with automake to create Makefile.in

AUTOMAKE_OPTIONS = foreign 1.6

if HAVE_THREAD
  MAYBE_THREAD = thread
  MAYBE_THREAD_LIB = thread/libicethread.la
endif

if HAVE_SPEEX
  MAYBE_SPEEX = speex.c
endif

SUBDIRS = avl net timing httpp $(MAYBE_THREAD)

lib_LTLIBRARIES = libshout.la
libshout_la_LDFLAGS = -version-info 5:0:2

EXTRA_DIST = speex.c
noinst_HEADERS = shout_ogg.h shout_private.h util.h
libshout_la_SOURCES = shout.c util.c ogg.c vorbis.c mpeg.c webm.c $(MAYBE_SPEEX)
AM_CFLAGS = @XIPH_CFLAGS@

libshout_la_LIBADD = net/libicenet.la timing/libicetiming.la avl/libiceavl.la\
		httpp/libicehttpp.la $(MAYBE_THREAD_LIB) $(VORBIS_LIBS) $(SPEEX_LIBS)

INCLUDES = -I$(top_builddir)/include

debug:
	$(MAKE) all CFLAGS="@DEBUG@"

profile:
	$(MAKE) all CFLAGS="@PROFILE@"
