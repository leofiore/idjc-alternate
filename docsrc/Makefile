HTML = index.html tour.html tour_main.html tour_jingles.html tour_output.html tour_preferences.html install.html install_build.html install_first_run.html
TEMPLATES = template_head.html__ template_tail.html__
IMAGES = main-window.png jingles-window.png output-window.png prefs-general.png prefs-microphones.png prefs-jack-ports.png prefs-bindings.png

STATIC = favicon.png style.css site-logo.png

.SUFFIXES:
.SUFFIXES: .html_ .html .jpg_ .jpg .png_ .png

.html_.html :
	cat template_head.html__ $< template_tail.html__ > $@

.png_.png :
	basename $@ .png | xargs -I @r@ cp $< @r@.hq.png
	convert $< -quality 1 -resize 80% $@

all : $(HTML) $(IMAGES)

$(HTML) : $(TEMPLATES)

doc:
	mkdir -p ../doc/
	rm -f ../doc/*
	cp $(HTML) $(IMAGES) $(STATIC) ../doc/
	echo "EXTRA_DIST=$(HTML) $(IMAGES) $(STATIC)" > ../doc/Makefile.am

site:
	mkdir -p site/
	rm -f site/*
	cp $(HTML) $(IMAGES) $(STATIC) *.hq.png site/
	find site -type f -exec curl --retry 3 --connect-timeout 10 -n -T "{}" sftp://web.sourceforge.net/home/groups/i/id/idjc/htdocs/ \;

clean:
	rm -f $(HTML) $(IMAGES) *.hq.png
	
docclean:
	rm -f ../doc/*

siteclean:
	rm -f site/*

.PHONY: doc site clean docclean siteclean

