SUBDIRS = ${MAYBE_LIBSHOUT} c python artwork Man doc
DISTDIRS = libshout

nodist_bin_SCRIPTS=idjc idjcctrl
dist_noinst_SCRIPTS=idjc.in.in idjcctrl_.py env-up ffmpeg_avcodec.c
nodist_doc_DATA=AUTHORS.gz NEWS.gz README.gz ChangeLog.gz
docdir=${prefix}/share/doc/${PACKAGE_NAME}-${PACKAGE_VERSION}
dist_noinst_DATA=idjc.desktop.in
nodist_appmenu_DATA=idjc.desktop
appmenudir=${prefix}/share/applications


idjc: idjc.in
	@sed -e 's|$${prefix}|${prefix}|' $? >$@

idjcctrl: idjcctrl_.py
	@sed -e 's|/path/to/python|${PYTHON}|' $? >$@
	@chmod u+x $@

idjc.desktop: idjc.desktop.in
	@sed -e 's|$${prefix}|${prefix}|' $? >$@

AUTHORS.gz: AUTHORS
	@ gzip -c $? >$@
	 
NEWS.gz: NEWS
	@ gzip -c $? >$@
	
README.gz: README
	@ gzip -c $? >$@
	
ChangeLog.gz: ChangeLog
	@ gzip -c $? >$@

clean-local:
	rm -f ChangeLog.gz README.gz NEWS.gz AUTHORS.gz idjc.desktop idjcctrl idjc

# Too lazy to manually claw this out from the source tree.
dtdist:
	make dist
	mv ${PACKAGE_TARNAME}-${PACKAGE_VERSION}.tar.gz ${HOME}/Desktop

# Too security conscious to not use the .netrc file.
sfpublish:
	make dist
	curl --retry 3 --connect-timeout 10 -T ${PACKAGE_TARNAME}-${PACKAGE_VERSION}.tar.gz -n sftp://frs.sourceforge.net/home/frs/project/i/id/idjc/idjc/0.8/

.PHONY: dtdist sfpublish idjc idjc.desktop
