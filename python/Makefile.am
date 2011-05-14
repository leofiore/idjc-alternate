pkgpython_PYTHON=__init__.py maingui.py midicontrols.py freefunctions.py jingles.py playergui.py preferences.py mutagentagger.py sourceclientgui.py dialogs.py popupwindow.py tooltips.py licence_window.py p3db.py ln_text.py en_GB_text.py en_US_text.py de_DE_text.py nt.py idjc-announce.py

dist_noinst_PYTHON=config.py.in.in

all: config.py

config.py: config.py.in
	sed -e 's|$${pkgdatadir}|${pkgdatadir}|' -e 's|$${plugindir}|${plugindir}|' -e 's|$${exec_prefix}|${exec_prefix}|' $? >$@

.PHONY: idjc_config.py

