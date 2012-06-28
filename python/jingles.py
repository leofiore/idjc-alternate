#   jingles.py: Jingles window and players -- part of IDJC.
#   Copyright 2012 Stephen Fairchild (s-fairchild@users.sourceforge.net)
#
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 2 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program in the file entitled COPYING.
#   If not, see <http://www.gnu.org/licenses/>.


import os
import gettext
import json

import gtk
import itertools

from idjc import *
from .playergui import *
from .prelims import *
from .gtkstuff import LEDDict
from .gtkstuff import WindowSizeTracker
from .gtkstuff import DefaultEntry


_ = gettext.translation(FGlobs.package_name, FGlobs.localedir,
                                                        fallback=True).gettext

PM = ProfileManager()

# Pixbufs for LED's of the specified size.
LED = LEDDict(6)



class Effect(gtk.HBox):
    """A trigger button for an audio effect or jingle.
    
    Takes a numeric parameter for identification. Also includes numeric I.D.,
    L.E.D., stop, and config button.
    """

    def __init__(self, num, parent):
        self.num = num
        self.approot = parent
        self.pathname = None
        
        gtk.HBox.__init__(self)
        self.set_border_width(2)
        self.set_spacing(3)
        
        label = gtk.Label("%02d" % (num + 1))
        self.pack_start(label, False)
        
        self.led = gtk.Image()
        self.led.set_from_pixbuf(LED["clear"].copy())
        self.pack_start(self.led, False)
        
        image = gtk.image_new_from_file(FGlobs.pkgdatadir / "stop.png")
        image.set_padding(4, 4)
        self.stop = gtk.Button()
        self.stop.set_image(image)
        self.pack_start(self.stop, False)
        
        self.trigger = gtk.Button()
        self.trigger.set_size_request(80, -1)
        self.pack_start(self.trigger)

        image = gtk.image_new_from_stock(gtk.STOCK_PROPERTIES,
                                                            gtk.ICON_SIZE_MENU)
        self.config = gtk.Button()
        self.config.set_image(image)
        self.pack_start(self.config, False)
        self.config.connect("clicked", self._on_config)

        self.dialog = EffectConfigDialog(self, parent.window)
        self.dialog.connect("response", self._on_dialog_response)
        self.dialog.emit("response", gtk.RESPONSE_NO)
        
        
    def _on_config(self, widget):
        if self.pathname and os.path.isfile(self.pathname):
            self.dialog.select_filename(self.pathname)
        self.dialog.button_entry.set_text(self.trigger.get_label() or "")
        self.dialog.show()
        
        
    def _on_dialog_response(self, dialog, response_id, pathname=None):
        if response_id in (gtk.RESPONSE_ACCEPT, gtk.RESPONSE_NO):
            self.pathname = pathname or dialog.get_filename()
            text = dialog.button_entry.get_text() if self.pathname else ""
            self.trigger.set_label(text.strip())
            
            sens = self.pathname is not None and os.path.isfile(self.pathname)
            self.stop.set_sensitive(sens)
            self.trigger.set_sensitive(sens)
            
            
    def marshall(self):
        return json.dumps([self.trigger.get_label(), self.dialog.get_filename()])


    def unmarshall(self, data):
        label, pathname = json.loads(data)
        self.dialog.button_entry.set_text(label)
        if pathname is None:
            self.dialog.unselect_all()
        else:
            self.dialog.set_filename(pathname)
        self._on_dialog_response(self.dialog, gtk.RESPONSE_ACCEPT, pathname)



class EffectConfigDialog(gtk.FileChooserDialog):
    """Configuration dialog for an Effect."""

    file_filter = gtk.FileFilter()
    file_filter.set_name(_('Supported media'))
    for each in supported.media:
        if each not in (".cue", ".txt"):
            file_filter.add_pattern("*" + each)
            file_filter.add_pattern("*" + each.upper())
    
    def __init__(self, effect, window):
        gtk.FileChooserDialog.__init__(self, _('Effect %d Config') % (effect.num + 1),
                            window,
                            buttons=(gtk.STOCK_CLEAR, gtk.RESPONSE_NO,
                            gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT,
                            gtk.STOCK_OK, gtk.RESPONSE_ACCEPT))
        self.set_modal(True)

        ca = self.get_content_area()
        ca.set_spacing(5)
        vbox = gtk.VBox()
        ca.pack_start(vbox, False)
        vbox.set_border_width(5)
        
        hbox = gtk.HBox()
        hbox.set_spacing(3)
        label = gtk.Label(_('Button text'))
        self.button_entry = DefaultEntry(_('No Name'))
        hbox.pack_start(label, False)
        hbox.pack_start(self.button_entry)

        vbox.pack_start(hbox, False)
        
        ca.show_all()
        self.connect("delete-event", lambda w, e: w.hide() or True)
        self.connect("response", self._cb_response)
        self.add_filter(self.file_filter)

    def _cb_response(self, dialog, response_id):
        dialog.hide()
        if response_id == gtk.RESPONSE_NO:
            dialog.unselect_all()
            dialog.set_current_folder(os.path.expanduser("~"))
            self.button_entry.set_text("")



class EffectCluster(gtk.Frame):
    """A frame containing columns of widget."""

    session_pathname = "effects_session"

    def __init__(self, label, qty, cols, widget, *args):
        gtk.Frame.__init__(self, label)
        self.widgets = []
        hbox = gtk.HBox()
        self.add(hbox)
        count = 0
        
        rows = (qty + cols - 1) // cols
        for col in range(cols):
            vbox = gtk.VBox()
            hbox.pack_start(vbox)
            
            for row in range(rows):
                self.widgets.append(widget(count, *args))
                vbox.pack_start(self.widgets[-1])
                count += 1


    def marshall(self):
        return json.dumps([x.marshall() for x in self.widgets])


    def unmarshall(self, data):
        for per_widget_data, widget in zip(json.loads(data), self.widgets):
            widget.unmarshall(per_widget_data)
   
   
    def restore_session(self):
        try:
            with open(PM.basedir / self.session_pathname, "r") as f:
                self.unmarshall(f.read())
        except IOError:
            print "failed to read effects session file"


    def save_session(self, where):
        try:
            with open((where or PM.basedir) / self.session_pathname, "w") as f:
                f.write(self.marshall())
        except IOError:
            print "failed to write effects session file"



class ExtraPlayers(gtk.HBox):
    """For effects, sequences of same, and background tracks."""
    
    
    def __init__(self, parent):
        self.approot = parent

        gtk.HBox.__init__(self)
        self.set_border_width(6)
        self.set_spacing(15)
        self.viewlevels = (5,)

        esbox = gtk.VBox()
        self.pack_start(esbox)
        estable = gtk.Table(columns=2, homogeneous=True)
        estable.set_col_spacing(1, 8)
        esbox.pack_start(estable)

        self.effects = EffectCluster(" %s " % _('Effects'), 24, 2, Effect,
                                                                        parent)
        estable.attach(self.effects, 0, 2, 0, 1)
        
        self.jvol_adj = gtk.Adjustment(127.0, 0.0, 127.0, 1.0, 10.0)
        self.jmute_adj = gtk.Adjustment(100.0, 0.0, 127.0, 1.0, 10.0)
        self.ivol_adj = gtk.Adjustment(64.0, 0.0, 127.0, 1.0, 10.0)

        for each in (self.jvol_adj, self.jmute_adj, self.ivol_adj):
            each.connect("value-changed",
                                lambda w: parent.send_new_mixer_stats())
        
        volpb = gtk.gdk.pixbuf_new_from_file(FGlobs.pkgdatadir / "volume2.png")

        jlevel_vbox = gtk.VBox()
        self.pack_start(jlevel_vbox, False)
        
        jvol_image = gtk.image_new_from_pixbuf(volpb.copy())
        jvol = gtk.VScale(self.jvol_adj)
        jvol.set_inverted(True)
        jvol.set_draw_value(False)

        jmute_image = gtk.image_new_from_file(FGlobs.pkgdatadir / "volume2.png")
        jmute = gtk.VScale(self.jmute_adj)
        jmute.set_inverted(True)
        jmute.set_draw_value(False)
        
        for widget, expand in zip((jvol_image, jvol, jmute_image, jmute), 
                                                itertools.cycle((False, True))):
            jlevel_vbox.pack_start(widget, expand, padding=2)
       
        ilevel_vbox = gtk.VBox()
        self.pack_start(ilevel_vbox, False)
        
        ivol_image = gtk.image_new_from_pixbuf(volpb.copy())
        ilevel_vbox.pack_start(ivol_image, False, padding=2)
        ivol = gtk.VScale(self.ivol_adj)
        ivol.set_inverted(True)
        ivol.set_draw_value(False)
        ilevel_vbox.pack_start(ivol, padding=2)

        interlude_frame = gtk.Frame(" %s " % _('Background Tracks'))
        self.pack_start(interlude_frame)
        interlude_box = gtk.VBox()
        interlude_box.set_border_width(8)
        interlude_frame.add(interlude_box)
        self.interlude = IDJC_Media_Player(interlude_box, "interlude", parent)
        interlude_box.set_no_show_all(True)

        self.show_all()
        interlude_box.show()


    def clear_indicators(self):
        """Set all LED indicators to off."""
        
        pass


    def cleanup(self):
        pass


    @property
    def playing(self):
        return False
        
    
    @property
    def flush(self):
        return 0
        

    @flush.setter
    def flush(self, value):
        pass


    @property
    def interludeflush(self):
        return 0


    @interludeflush.setter
    def interludeflush(self, value):
        pass
