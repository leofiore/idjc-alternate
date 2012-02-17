SUBDIRS = prelims

pkgpython_PYTHON = dialogs.py gtkstuff.py irc.py jingles.py licence_window.py maingui.py	 \
					\
						midicontrols.py mutagentagger.py p3db.py playergui.py popupwindow.py \
					\
						preferences.py sourceclientgui.py tooltips.py utils.py

nodist_pkgpython_PYTHON=__init__.py

dist_noinst_PYTHON=__init__.py.in.in

__init__.py: __init__.py.in
	@sed -e 's|$${pkgdatadir}|${pkgdatadir}|' \
		 -e 's|$${exec_prefix}|${exec_prefix}|' \
	     -e 's|$${prefix}|${prefix}|' $? >$@

clean-local:
	rm -f __init__.py

.PHONY: __init__.py $pkgpython_PYTHON
