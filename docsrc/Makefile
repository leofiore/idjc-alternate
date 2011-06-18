# HTML that will be wrapped by $(TEMPLATES)
HTML = index.html tour.html tour_main.html tour_jingles.html tour_output.html tour_preferences.html install.html install_standard.html install_build.html install_first_run.html tutorials.html tutorials_icecast.html tutorials_shoutcast.html tutorials_voip.html contact.html
# Wrappers for $(HTML)
TEMPLATES = template_head.html__ template_tail.html__
# Images that will to be compressed.
IMAGES = main-window.png jingles-window.png output-window.png prefs-general.png prefs-microphones.png prefs-jack-ports.png prefs-bindings.png prefs-xchat.png
# HTML and related style info that will not be wrapped.
STYLESHEETS = style.css style_ie.css
# Images that will not be compressed.
QUALIMAGES = favicon.png site-logo.png
# Stuff to transfer direct - as raw.
STATIC = $(STYLESHEETS) $(QUALIMAGES)

.SUFFIXES:
.SUFFIXES: .html_ .html .jpg_ .jpg .png_ .png

.html_.html :
	cat template_head.html__ $< template_tail.html__ > $@

.png_.png :
	basename $@ .png | xargs -I @r@ cp $< @r@.hq.png
	convert $< -quality 1 -resize 80% $@

all : $(HTML) $(IMAGES)

$(HTML) : $(TEMPLATES)

# Build the doc directory.
doc:
	mkdir -p ../doc/
	rm -f ../doc/*
	cp $(HTML) $(IMAGES) $(STATIC) ../doc/
	echo "EXTRA_DIST=$(HTML) $(IMAGES) $(STATIC)" > ../doc/Makefile.am

DIRPREP = mkdir -p site/ ; rm -f site/*
UPLOAD = find site -type f -exec curl --retry 3 --connect-timeout 10 -n -T "{}" sftp://web.sourceforge.net/~/htdocs/ \;

# Upload everything to the website.
site:
	$(DIRPREP)
	cp $(HTML) $(IMAGES) $(STATIC) *.hq.png site/
	$(UPLOAD)

# Convenience uploader for all except images.
sitemarkup:
	$(DIRPREP)
	cp $(HTML) $(STATIC) site/
	$(UPLOAD)

# Convenience uploader for stylesheet information only.
sitecss:
	$(DIRPREP)
	cp $(STYLESHEETS) site/
	$(UPLOAD)

clean:
	rm -f $(HTML) $(IMAGES) *.hq.png

docclean:
	rm -f ../doc/*

siteclean:
	rm -f site/*

.PHONY: all doc site sitemarkup sitecss clean docclean siteclean
