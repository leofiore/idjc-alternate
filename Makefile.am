SUBDIRS = po c python artwork man doc

EXTRA_SCRIPTS=
nodist_bin_SCRIPTS=${PACKAGE_NAME}
dist_noinst_SCRIPTS=idjc.in.in bootstrap
nodist_doc_DATA=AUTHORS.gz NEWS.gz README.gz ChangeLog.gz
docdir=${prefix}/share/doc/${PACKAGE_NAME}-${PACKAGE_VERSION}
dist_noinst_DATA=idjc.desktop.in.in
nodist_appmenu_DATA=${PACKAGE_NAME}.desktop
appmenudir=${prefix}/share/applications

${PACKAGE_NAME}: idjc.in
	@sed -e 's|$${prefix}|${prefix}|g' $? >$@

${PACKAGE_NAME}.desktop: idjc.desktop.in
	@sed -e 's|$${prefix}|${prefix}|g' -e 's|$${exec_prefix}|${exec_prefix}|g' $? >$@

AUTHORS.gz: AUTHORS
	@ gzip -c $? >$@
	 
NEWS.gz: NEWS
	@ gzip -c $? >$@
	
README.gz: README
	@ gzip -c $? >$@
	
ChangeLog.gz: ChangeLog
	@ gzip -c $? >$@

clean-local:
	rm -f ChangeLog.gz README.gz NEWS.gz AUTHORS.gz ${PACKAGE_NAME}.desktop idjcctrl ${PACKAGE_NAME}

dtdist:
	make dist
	mv ${PACKAGE_TARNAME}-${PACKAGE_VERSION}.tar.gz ${HOME}/Desktop

sfpublish:
	make dist
	curl --retry 3 --connect-timeout 10 -T ${PACKAGE_TARNAME}-${PACKAGE_VERSION}.tar.gz -n sftp://frs.sourceforge.net/home/frs/project/i/id/idjc/idjc/0.8/

.PHONY: dtdist sfpublish ${PACKAGE_NAME} ${PACKAGE_NAME}.desktop

ACLOCAL_AMFLAGS = -I m4

EXTRA_DIST = config.rpath m4/ChangeLog
