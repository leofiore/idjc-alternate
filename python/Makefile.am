SUBDIRS = prelims

pkgpython_PYTHON=utils.py maingui.py midicontrols.py freefunctions.py jingles.py playergui.py preferences.py mutagentagger.py sourceclientgui.py dialogs.py popupwindow.py tooltips.py licence_window.py p3db.py ln_text.py en_GB_text.py en_US_text.py de_DE_text.py gtkstuff.py

nodist_pkgpython_PYTHON=__init__.py

dist_noinst_PYTHON=__init__.py.in.in

all: __init__.py

__init__.py: __init__.py.in
	sed -e 's|$${pkgdatadir}|${pkgdatadir}|' -e 's|$${exec_prefix}|${exec_prefix}|' $? >$@

.PHONY: __init__.py $pkgpython_PYTHON

