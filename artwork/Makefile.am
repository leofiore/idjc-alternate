dist_pkgdata_DATA = add3.png advance.png control_c.png control_k.png control_n.png control_p.png greenphone.png interlude2.png jack2.png led_lit_amber_black_border_64x64.png led_lit_green_black_border_64x64.png led_lit_red_black_border_64x64.png led_unlit_clear_border_64x64.png next.png note.png pass.png pause.png pbphone.png play2.png play3.png prev.png rec.png redphone.png stop.png volume2.png logo.png icon.png speedicon.png crossout.png classic_cross.png mk2_cross.png listenerphones.png mic_on.png mic_off.png mic_unshown.png mic4.png pat3.png headroom.png

nodist_pixmaps_DATA = ${PACKAGE_NAME}.png
pixmapsdir = ${prefix}/share/pixmaps

${PACKAGE_NAME}.png: icon.png
	@cp $? $@

clean-local:
	rm -f ${PACKAGE_NAME}.png
