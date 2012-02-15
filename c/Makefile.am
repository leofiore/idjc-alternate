libexec_PROGRAMS = idjcbe

idjcbe_SOURCES = agc.c agc.h audio_feed.c audio_feed.h avcodecdecode.c avcodecdecode.h bsdcompat.c bsdcompat.h			\
			\
				compressor.c compressor.h dbconvert.c dbconvert.h dyn_lame.c dyn_lame.h dyn_mad.c dyn_mad.h encoder.c		\
			\
				encoder.h fade.c fade.h flacdecode.c flacdecode.h gnusource.h ialloc.c ialloc.h id3.c id3.h kvpdict.c		\
			\
				kvpdict.h kvpparse.c kvpparse.h lame.h live_mp3_encoder.c live_mp3_encoder.h live_ogg_encoder.c				\
			\
				live_ogg_encoder.h live_oggflac_encoder.c live_oggflac_encoder.h live_oggspeex_encoder.c						\
			\
				live_oggspeex_encoder.h mad.h main.c main.h mic.c mic.h mixer.c mixer.h mp3dec.c mp3dec.h mp3tagread.c	\
			\
				mp3tagread.h ogg_flac_dec.c ogg_flac_dec.h ogg_speex_dec.c ogg_speex_dec.h ogg_vorbis_dec.c					\
			\
				ogg_vorbis_dec.h oggdec.c oggdec.h peakfilter.c peakfilter.h recorder.c recorder.h sig.c sig.h				\
			\
				sndfiledecode.c sndfiledecode.h sndfileinfo.c sndfileinfo.h sourceclient.c sourceclient.h speextag.c		\
			\
				speextag.h streamer.c streamer.h watchdog.c watchdog.h xlplayer.c xlplayer.h


idjcbe_CFLAGS = ${GLIB_CFLAGS} ${LIBAVCODEC_CFLAGS} ${LIBAVFORMAT_CFLAGS} ${LIBAVUTIL_CFLAGS} ${LIBFLAC_CFLAGS}		\
			\
				${LIBJACK_CFLAGS} ${LIBMAD_CFLAGS} ${LIBSAMPLERATE_CFLAGS} ${LIBSHOUT_CFLAGS} ${LIBSNDFILE_CFLAGS} 		\
			\
				${LIBSPEEX_CFLAGS} ${LIBVORBISENC_CFLAGS} ${LIBVORBIS_CFLAGS} -O2 -Wall -std=gnu99


idjcbe_LDADD = ${DYN_LIBS} ${GLIB_LIBS} ${LIBAVCODEC_LIBS} ${LIBAVFORMAT_LIBS} ${LIBAVUTIL_LIBS} ${LIBFLAC_LIBS} 		\
			\
				${LIBJACK_LIBS} ${LIBMAD_LIBS} ${LIBMP3LAME} ${LIBM} ${LIBSAMPLERATE_LIBS} ${LIBSHOUT_LIBS} 					\
			\
				${LIBSNDFILE_LIBS} ${LIBSPEEX_LIBS} ${LIBVORBISENC_LIBS} ${LIBVORBIS_LIBS} -lpthread


idjcbe_LDFLAGS = ${DYN_LDFLAGS}
