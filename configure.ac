#                                               -*- Autoconf -*-
# Process this file with autoconf to produce a configure script.

AC_PREREQ(2.59)
AC_INIT([idjc], [0.8.9], 
                [http://idjc.sourceforge.net])
AC_SUBST(COPYRIGHT_YEAR, [2013])
AC_CONFIG_SRCDIR([config.h.in])
AM_INIT_AUTOMAKE
AM_CONFIG_HEADER([config.h])

# Generate python installation stuff
AM_PATH_PYTHON([2.7])

# idjc backend library stuff
LT_INIT([disable-static,dlopen])

# Checks for programs.
AM_PROG_CC_C_O

# Cause autoconfiguration to look for an external libintl.
AM_GNU_GETTEXT([external])
AM_GNU_GETTEXT_VERSION([0.18.1])

# We need libjack in order to compile.
PKG_CHECK_MODULES(LIBJACK, [jack >= 0.98.0])

# Core dependencies.
PKG_CHECK_MODULES([LIBVORBIS], [vorbis >= 1.0.0])
PKG_CHECK_MODULES([LIBVORBISENC], [vorbisenc >= 1.0.0])
PKG_CHECK_MODULES([LIBSAMPLERATE], [samplerate])
PKG_CHECK_MODULES([LIBSNDFILE], [sndfile])
PKG_CHECK_MODULES([GLIB], [glib-2.0])

AC_ARG_ENABLE([libav],
   AC_HELP_STRING([--disable-libav],[remove capability to decode m4a/wma/avi files]),[makelibav=$enableval],[makelibav="maybe"])

if test $makelibav != "no" ; then
    PKG_CHECK_MODULES([LIBAVCODEC], [libavcodec], [AC_DEFINE(HAVE_AVCODEC, 1, [Set if libavcodec was found])
            AC_SUBST(HAVE_AVCODEC, 1)
            AC_CHECK_LIB([avcodec],[avcodec_decode_audio4], :, AC_MSG_ERROR("configure with --disable-libav or update ffmpeg/libav"))
            ],
            AC_SUBST(HAVE_AVCODEC, 0)

            if test $makelibav = "yes" ; then
               AC_MSG_ERROR([libavcodec not detected but specifically requested in configure options (libav)])
            else
               AC_MSG_WARN([IDJC will be built without wma/mp4/ape support])
            fi)

   PKG_CHECK_MODULES([LIBAVFORMAT], [libavformat], AC_DEFINE(HAVE_AVFORMAT, 1, [Set if libavformat was found])
            AC_SUBST(HAVE_AVFORMAT, 1),
            AC_SUBST(HAVE_AVFORMAT, 0)

            if test $makelibav = "yes" ; then
               AC_MSG_ERROR([libavformat not detected but specifically requested in configure options (libav)])
            else
               AC_MSG_WARN([IDJC will be built without wma/mp4/ape support])
            fi)

   PKG_CHECK_MODULES([LIBAVUTIL], [libavutil], AC_DEFINE(HAVE_AVUTIL, 1, [Set if libavutil was found])
            AC_SUBST(HAVE_AVUTIL, 1),
            AC_SUBST(HAVE_AVUTIL, 0)

            if test $makelibav = "yes" ; then
               AC_MSG_ERROR([libavutil not detected but specifically requested in configure options (libav)])
            else
               AC_MSG_WARN([IDJC will be built without wma/mp4/ape support])
            fi)
else
   AC_SUBST(HAVE_AVCODEC, 0)
   AC_SUBST(HAVE_AVFORMAT, 0)
   AC_SUBST(HAVE_AVUTIL, 0)
fi

AC_ARG_ENABLE([speex],
   AC_HELP_STRING([--disable-speex],[remove the capability to play/stream speex]),
   [makespeex=$enableval],[makespeex="maybe"])

if test $makespeex != "no" ; then
   PKG_CHECK_MODULES([LIBSPEEX], [speex],
            [
            AC_DEFINE(HAVE_SPEEX, 1, [Set if libspeex was found])
            AC_SUBST(HAVE_SPEEX, 1)],
            [AC_SUBST(HAVE_SPEEX, 0),

            if test $makespeex = "yes" ; then
               AC_MSG_ERROR([libspeex not detected but specifically requested in configure options])
            else
               AC_MSG_WARN([IDJC will be built without speex support])
            fi])
else
   AC_SUBST([HAVE_SPEEX],[0])
fi

# Used only to check the correct version is installed
PKG_CHECK_MODULES([PYGTK], [pygtk-2.0 >= 2.6.0])

AC_MSG_CHECKING([for mutagen])
${PYTHON}${PYTHON_VERSION} -c "import mutagen" >/dev/null 2>&1
if test $? -ne 0 ; then
    AC_MSG_RESULT([no])
    AC_MSG_WARN([runtime dependency (mutagen / python-mutagen) is missing])
else
    AC_MSG_RESULT([yes])
fi

AC_ARG_ENABLE([flac],
   AC_HELP_STRING([--disable-flac],[remove the capability to play/stream in FLAC]),
   [makeflac=$enableval],[makeflac="maybe"])

if test $makeflac != "no" ; then
   PKG_CHECK_MODULES([LIBFLAC],[flac >= 1.1.3],
            [AC_DEFINE([HAVE_FLAC],[1],[Set if libflac >= 1.1.3 was found])
            AC_SUBST([HAVE_FLAC],[1])

            AC_CHECK_LIB([FLAC], [FLAC__stream_decoder_init_ogg_stream],
                   [AC_SUBST([HAVE_OGGFLAC],[1])
                   AC_DEFINE([HAVE_OGGFLAC],[1],[Set if libFLAC has oggflac support])],
                   [AC_SUBST([HAVE_OGGFLAC],[0])
                   AC_MSG_WARN([your version of libFLAC lacks oggflac support])])],

            [AC_SUBST([HAVE_FLAC],[0])
            AC_SUBST([HAVE_OGGFLAC],[0])

            if test $makeflac = "yes" ; then
               AC_MSG_ERROR([libFLAC not detected but specifically requested in configure options])
            else
               AC_MSG_WARN([IDJC will be built without flac support])
            fi])
else
   AC_SUBST([HAVE_FLAC],[0])
   AC_SUBST([HAVE_OGGFLAC],[0])
fi

AC_CHECK_HEADERS([mpg123.h])

AC_ARG_ENABLE(mpg123,
   AC_HELP_STRING([--disable-mpg123],[remove capability to play mp3 format]),[makempg123=$enableval],[makempg123="maybe"])

if test $makempg123 != "no" ; then
    PKG_CHECK_MODULES([MPG123], [libmpg123],
    [AC_SUBST([MPG123], [-lmpg123])
    AC_SUBST([DYN_MPG123], [0])],
    [AC_DEFINE([DYN_MPG123], [1], [MPG123 to be linked dynamically])
    AC_SUBST([DYN_MPG123], [1])
    DYNAMIC="1"
    if test $makempg123 = "yes" ; then
        AC_MSG_ERROR([libmpg123 not detected but specifically requested in configure options])
    fi])
else
    AC_DEFINE([DYN_MPG123], [1], [MPG123 to be linked dynamically])
    AC_SUBST([DYN_MPG123], [1])
    DYNAMIC="1"
fi

AC_CHECK_HEADERS([lame/lame.h])

AC_ARG_ENABLE(lame,
   AC_HELP_STRING([--disable-lame],[remove capability to stream/record mp3 format]),[makelame=$enableval],[makelame="maybe"])

if test $makelame != "no" ; then
AC_CHECK_LIB([mp3lame -lm], [lame_init],
        [AC_SUBST([LIBMP3LAME], [-lmp3lame])
        AC_SUBST([DYN_LAME], [0])],
            AC_DEFINE([DYN_LAME], [1], [LAME to be linked dynamically])
            AC_SUBST([DYN_LAME], [1])
            DYNAMIC="1"
            if test $makelame = "yes" ; then
              AC_MSG_ERROR([libmp3lame not detected but specifically requested in configure options])
            fi)
else
   AC_DEFINE([DYN_LAME], [1], [LAME to be linked dynamically])
   AC_SUBST([DYN_LAME], [1])
   DYNAMIC="1"
fi

AC_ARG_ENABLE([twolame],
   AC_HELP_STRING([--disable-twolame],[remove the capability to stream in mp2]),
   [maketwolame=$enableval],[maketwolame="maybe"])

if test $maketwolame != "no" ; then
   PKG_CHECK_MODULES([TWOLAME], [twolame],
            [
            AC_DEFINE(HAVE_TWOLAME, 1, [Set if libtwolame was found])
            AC_SUBST(HAVE_TWOLAME, 1)],
            [AC_SUBST(HAVE_TWOLAME, 0),

            if test $maketwolame = "yes" ; then
               AC_MSG_ERROR([libtwolame not detected but specifically requested in configure options])
            else
               AC_MSG_WARN([IDJC will be built without libtwolame mp2 streaming support])
            fi])
else
   AC_SUBST([HAVE_TWOLAME],[0])
fi

AC_ARG_ENABLE([opus],
   AC_HELP_STRING([--disable-opus],[remove capability to play/stream in opus format]),
   [makeopus=$enableval],[makeopus="maybe"])

if test $makeopus != "no" ; then
   PKG_CHECK_MODULES([OPUS], [opus],
            [
            AC_DEFINE(HAVE_OPUS, 1, [Set if libopus was found])
            AC_SUBST(HAVE_OPUS, 1)],
            [AC_SUBST(HAVE_OPUS, 0),

            if test $makeopus = "yes" ; then
               AC_MSG_ERROR([libopus not detected but specifically requested in configure options])
            else
               AC_MSG_WARN([IDJC will be built without opus playback or streaming support])
            fi])
else
   AC_SUBST([HAVE_OPUS],[0])
fi

AC_CHECK_LIB([pthread], [pthread_create], :, AC_MSG_ERROR("libpthread not detected"))

# Conditionally include libm.  Some standard libraries could have inbuilt math stuff.
AC_CHECK_FUNCS([sqrt pow], :, [AC_CHECK_LIB([m], [sqrt, pow], AC_SUBST(LIBM, "-lm"),
	AC_MSG_ERROR("math library is missing critical function"))])

# Checks for header files.
AC_HEADER_STDC
AC_CHECK_HEADERS([fcntl.h jack/jack.h jack/transport.h pthread.h], :, AC_MSG_ERROR("Critical header file missing"))

# Checks for typedefs, structures, and compiler characteristics.
AC_C_CONST
AC_C_INLINE
AC_TYPE_PID_T
AC_TYPE_SIZE_T

# Checks for library functions.
AC_FUNC_MALLOC
AC_TYPE_SIGNAL
AC_CHECK_FUNCS([memset strchr], :, AC_MSG_ERROR("Critical function missing"))
AC_CHECK_FUNCS([getline strndup canonicalize_file_name], :,
      [AC_DEFINE([USE_BSD_COMPAT],[1],
      [Set if GNU extensions need to be replicated])])

# Use png or xpm for graphics
AC_SUBST(EXT,[png])

PKG_CHECK_MODULES([SHOUTIDJC], [shout-idjc])
AC_CHECK_HEADERS([shoutidjc/shout.h])

if test x$DYNAMIC = "x1" ; then
   AC_CHECK_FUNCS([dlopen], :, AC_CHECK_LIB([dl], [dlopen], AC_SUBST([DYN_LIBS], [-ldl]), AC_MSG_ERROR([Runtime linking functions not found])))
   AC_SUBST([DYN_LDFLAGS], [-rdynamic])
fi

AC_CONFIG_FILES([Makefile
                  po/Makefile.in
                  c/Makefile
                  python/Makefile
                  python/prelims/Makefile
                  artwork/Makefile
                  man/Makefile
                  doc/Makefile
                  python/__init__.py.in
                  idjc.in
                  idjc.desktop.in])

AC_OUTPUT
