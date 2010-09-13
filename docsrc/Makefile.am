dist_doc_DATA=idjc.css
nodist_doc_DATA=index.html tour.html
dist_noinst_DATA=template_head.html__ template_tail.html__ index.html_ tour.html_
docdir=${prefix}/share/doc/${PACKAGE_NAME}-${PACKAGE_VERSION}/htmldoc

.html_.html:
	cat template_head.html__ $? template_tail.html__ > $@
