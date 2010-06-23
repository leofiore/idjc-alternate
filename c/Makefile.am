libexec_PROGRAMS=idjcmixer idjcsourceclient

idjcsourceclient_SOURCES=sourceclient.c sourceclient.h kvpdict.c kvpdict.h kvpparse.c kvpparse.h encoder.c encoder.h streamer.c streamer.h recorder.c recorder.h audio_feed.c audio_feed.h live_ogg_encoder.c live_ogg_encoder.h watchdog.c watchdog.h  live_mp3_encoder.c live_mp3_encoder.h id3.c id3.h bsdcompat.c bsdcompat.h gnusource.h live_oggflac_encoder.c live_oggflac_encoder.h live_oggspeex_encoder.c live_oggspeex_encoder.h dyn_lame.c dyn_lame.h lame.h
idjcsourceclient_CFLAGS=-Wall -std=gnu99 -O2 ${LIBJACK_CFLAGS} ${LIBVORBIS_CFLAGS} ${LIBVORBISENC_CFLAGS} ${LIBSAMPLERATE_CFLAGS} ${LIBFLAC_CFLAGS} ${LIBSPEEX_CFLAGS} ${LIBSHOUT_CFLAGS}
idjcsourceclient_LDADD=-lpthread ${DYN_LIBS} ${LIBMP3LAME} ${LIBM} ${LIBJACK_LIBS} ${LIBVORBIS_LIBS} ${LIBVORBISENC_LIBS} ${LIBSAMPLERATE_LIBS} ${LIBFLAC_LIBS} ${LIBSPEEX_LIBS} ${LIBSHOUT_LIBS}
idjcsourceclient_LDFLAGS=${DYN_LDFLAGS}

idjcmixer_SOURCES=idjcmixer.c kvpdict.c kvpparse.c kvpdict.h kvpparse.h dbconvert.c dbconvert.h ialloc.c ialloc.h xlplayer.c xlplayer.h compressor.c compressor.h sndfileinfo.c sndfileinfo.h flacdecode.c flacdecode.h mp3dec.c mp3dec.h sndfiledecode.c sndfiledecode.h avcodecdecode.c avcodecdecode.h mp3tagread.c mp3tagread.h oggdec.c oggdec.h ogg_vorbis_dec.c ogg_vorbis_dec.h ogg_flac_dec.c ogg_flac_dec.h ogg_speex_dec.c ogg_speex_dec.h speextag.c speextag.h bsdcompat.c bsdcompat.h gnusource.h agc.c agc.h dyn_mad.c dyn_mad.h mad.h mic.c mic.h peakfilter.c peakfilter.h
idjcmixer_CFLAGS=-Wall -std=gnu99 -O2 ${LIBVORBIS_CFLAGS} ${LIBJACK_CFLAGS} ${LIBSAMPLERATE_CFLAGS} ${LIBFLAC_CFLAGS} ${LIBSNDFILE_CFLAGS} ${LIBMAD_CFLAGS} ${LIBAVCODEC_CFLAGS} ${LIBAVFORMAT_CFLAGS} ${LIBSPEEX_CFLAGS}
idjcmixer_LDADD=-lpthread ${DYN_LIBS} ${LIBM} ${LIBVORBIS_LIBS} ${LIBJACK_LIBS} ${LIBSAMPLERATE_LIBS} ${LIBFLAC_LIBS} ${LIBSNDFILE_LIBS} ${LIBMAD_LIBS} ${LIBAVCODEC_LIBS} ${LIBAVFORMAT_LIBS} ${LIBSPEEX_LIBS}
idjcmixer_LDFLAGS=${DYN_LDFLAGS}
