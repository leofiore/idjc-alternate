SOURCES = idjc.1_ idjc-run.1_
TARGETS = idjc.1 idjc-run.1

dist_noinst_DATA = $(SOURCES) reporting_bugs.part
nodist_man_MANS = $(TARGETS)


SUFFIXES = .1_ .1

.1_.1:
	@sed -e 's|VERSION|${PACKAGE_NAME}-${PACKAGE_VERSION}|' -e '/.SH REPORTING BUGS/r ./reporting_bugs.part' $< >$@
	
clean-local:
	rm -f $(TARGETS)
