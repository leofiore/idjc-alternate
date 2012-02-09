SOURCES = idjc.1_ idjc-profile.1_ idjc-ctrl.1_ idjc-run.1_
TARGETS = idjc.1 idjc-profile.1 idjc-ctrl.1 idjc-run.1

dist_noinst_DATA = $(SOURCES)
nodist_man_MANS = $(TARGETS)

SUFFIXES = .1_ .1

.1_.1:
	@sed -e 's|VERSION|${PACKAGE_NAME}-${PACKAGE_VERSION}|' $< >$@
	
clean-local:
	rm -f $(TARGETS)
