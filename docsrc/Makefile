HTML = index.html tour.html
TEMPLATES = template_head.html__ template_tail.html__
IMAGES = site-logo.png site-logo.jpg

LITERALS = favicon.png idjc.css

.SUFFIXES:
.SUFFIXES: .html_ .html .jpg_ .jpg .png_ .png

.html_.html :
	cat template_head.html__ $< template_tail.html__ > $@
	cp $@ hiqual/$@
	sed -e s/.png/.jpg/ <$@ >loqual/$@

.png_.png :
	cp $< $@
	cp $< hiqual/$@

.jpg_.jpg :
	cp $< $@
	cp $< hiqual/$@
	convert $< -quality 3 -resize 80% loqual/$@

.png_.jpg :
	convert $< -quality 3 -resize 80% $@
	cp $@ loqual/$@

all : $(HTML) $(IMAGES) literals

$(HTML) : $(TEMPLATES)

literals: $(LITERALS)
	mkdir -p hiqual loqual
	cp $? hiqual/
	cp $? loqual/

doc:
	rm -f ../doc/*
	cp loqual/* ../doc/

clean:
	rm -f $(HTML) $(IMAGES) hiqual/* loqual/*

.PHONY: clean literals
