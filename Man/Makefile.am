dist_noinst_DATA = idjc.1_ idjcctrl.1_
nodist_man_MANS = idjc.1 idjcctrl.1

idjc.1: idjc.1_
	@sed -e 's|VERSION|${PACKAGE_NAME}-${PACKAGE_VERSION}|' $? >$@

idjcctrl.1: idjcctrl.1_
	@sed -e 's|VERSION|${PACKAGE_NAME}-${PACKAGE_VERSION}|' $? >$@
