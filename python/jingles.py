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
import uuid

import gtk
import itertools

from idjc import *
from .playergui import *
from .prelims import *
from .gtkstuff import LEDDict
from .gtkstuff import WindowSizeTracker
from .gtkstuff import DefaultEntry
from .tooltips import set_tip
from .utils import LinkUUIDRegistry

_ = gettext.translation(FGlobs.package_name, FGlobs.localedir,
                                                        fallback=True).gettext

PM = ProfileManager()
link_uuid_reg = LinkUUIDRegistry()

# Pixbufs for LED's of the specified size.
LED = LEDDict(9)



class Effect(gtk.HBox):
    """A trigger button for an audio effect or jingle.
    
    Takes a numeric parameter for identification. Also includes numeric I.D.,
    L.E.D., stop, and config button.
    """


    dndtargets = [("IDJC_EFFECT_BUTTON", gtk.TARGET_SAME_APP, 6)]


    def __init__(self, num, others, parent):
        self.num = num
        self.others = others
        self.approot = parent
        self.pathname = None
        self.uuid = str(uuid.uuid4())
        self._repeat_works = False
            
        gtk.HBox.__init__(self)
        self.set_border_width(2)
        self.set_spacing(3)
        
        label = gtk.Label("%02d" % (num + 1))
        self.pack_start(label, False)
        
        self.clear = LED["clear"].copy()
        self.green = LED["green"].copy()
        
        self.led = gtk.Image()
        self.led.set_from_pixbuf(self.clear)
        self.pack_start(self.led, False)
        self.old_ledval = 0
        
        image = gtk.image_new_from_file(FGlobs.pkgdatadir / "stop.png")
        image.set_padding(4, 4)
        self.stop = gtk.Button()
        self.stop.set_image(image)
        self.pack_start(self.stop, False)
        self.stop.connect("clicked", self._on_stop)
        set_tip(self.stop, _('Stop'))
        
        self.trigger = gtk.Button()
        self.trigger.set_size_request(80, -1)
        self.pack_start(self.trigger)
        self.trigger.connect("clicked", self._on_trigger)
        self.trigger.drag_dest_set(gtk.DEST_DEFAULT_ALL,
            self.dndtargets, gtk.gdk.ACTION_DEFAULT | gtk.gdk.ACTION_MOVE)
        self.trigger.connect("drag-data-received", self._drag_data_received)
        set_tip(self.trigger, _('Play'))
        
        self.repeat = gtk.ToggleButton()
        image = gtk.Image()
        pb = gtk.gdk.pixbuf_new_from_file_at_size(FGlobs.pkgdatadir / "repeat.png", 23, 19)
        image.set_from_pixbuf(pb)
        self.repeat.add(image)
        image.show()
        self.pack_start(self.repeat, False)
        set_tip(self.repeat, _('Repeat'))

        image = gtk.image_new_from_stock(gtk.STOCK_PROPERTIES,
                                                            gtk.ICON_SIZE_MENU)
        self.config = gtk.Button()
        self.config.set_image(image)
        self.pack_start(self.config, False)
        self.config.connect("clicked", self._on_config)
        self.config.drag_source_set(gtk.gdk.BUTTON1_MASK,
            self.dndtargets, gtk.gdk.ACTION_DEFAULT | gtk.gdk.ACTION_MOVE)
        self.config.connect("drag-data-get", self._drag_get_data)
        set_tip(self.config, _('Configure'))

        self.dialog = EffectConfigDialog(self, parent.window)
        self.dialog.connect("response", self._on_dialog_response)
        self.dialog.emit("response", gtk.RESPONSE_NO)


    def _drag_get_data(self, widget, context, selection, target_id, etime):
        selection.set(selection.target, 8, str(self.num))
        return True


    def _drag_data_received(self, widget, context, x, y, dragged, info, etime):
        other = self.others[int(dragged.data)]
        if context.action == gtk.gdk.ACTION_MOVE:
            if other == self:
                context.finish(False, False, etime)
            else:
                self.stop.clicked()
                other.stop.clicked()
                context.finish(True, False, etime)
                self._swap(other)
        return True
        
        
    def _swap(self, other):
        new_pathname = other.pathname
        new_text = other.trigger.get_label() or ""
        new_level = other.level

        other._set(self.pathname, self.trigger.get_label() or "", self.level)
        self._set(new_pathname, new_text, new_level)
        
        
    def _set(self, pathname, button_text, level):
        try:
            self.dialog.set_filename(pathname)
        except:
            self.dialog.set_current_folder(os.path.expanduser("~"))

        self.dialog.button_entry.set_text(button_text)
        self.dialog.gain_adj.set_value(level)
        self._on_dialog_response(self.dialog, gtk.RESPONSE_ACCEPT, pathname)

        
    def _on_config(self, widget):
        self.stop.clicked()
        if self.pathname and os.path.isfile(self.pathname):
            self.dialog.select_filename(self.pathname)
        self.dialog.button_entry.set_text(self.trigger.get_label() or "")
        self.dialog.gain_adj.set_value(self.level)
        self.dialog.show()


    def _on_trigger(self, widget):
        self._repeat_works = True
        if self.pathname:
            self.approot.mixer_write(
                            "EFCT=%d\nPLRP=%s\nRGDB=%f\nACTN=playeffect\nend\n" % (
                            self.num, self.pathname, self.level))


    def _on_stop(self, widget):
        self._repeat_works = False
        self.approot.mixer_write("EFCT=%d\nACTN=stopeffect\nend\n" % self.num)


    def _on_dialog_response(self, dialog, response_id, pathname=None):
        if response_id in (gtk.RESPONSE_ACCEPT, gtk.RESPONSE_NO):
            self.pathname = pathname or dialog.get_filename()
            text = dialog.button_entry.get_text() if self.pathname and \
                                        os.path.isfile(self.pathname) else ""
            self.trigger.set_label(text.strip())
            self.level = dialog.gain_adj.get_value()
            
            sens = self.pathname is not None and os.path.isfile(self.pathname)
            if response_id == gtk.RESPONSE_ACCEPT and pathname is not None:
                self.uuid = str(uuid.uuid4())
            
            
    def marshall(self):
        link = link_uuid_reg.get_link_filename(self.uuid)
        if link is not None:
            # Replace orig file abspath with alternate path to a hard link
            # except when link is None as happens when a hard link fails.
            link = PathStr("links") / link
            self.pathname = PM.basedir / link
            if not self.dialog.get_visible():
                self.dialog.set_filename(self.pathname)
        return json.dumps([self.trigger.get_label(), (link or self.pathname), self.level, self.uuid])


    def unmarshall(self, data):
        try:
            label, pathname, level, self.uuid = json.loads(data)
        except ValueError:
            label = ""
            pathname = None
            level = 0.0

        if pathname is not None and not pathname.startswith(os.path.sep):
            pathname = PM.basedir / pathname
        if pathname is None or not os.path.isfile(pathname):
            self.dialog.unselect_all()
            label = ""
        else:
            self.dialog.set_filename(pathname)
        self.dialog.button_entry.set_text(label)
        self.dialog.gain_adj.set_value(level)
        self._on_dialog_response(self.dialog, gtk.RESPONSE_ACCEPT, pathname)
        self.pathname = pathname


    def update_led(self, val):
        if val != self.old_ledval:
            self.led.set_from_pixbuf(self.green if val else self.clear)
            self.old_ledval = val

            if not val and self._repeat_works and self.repeat.get_active():
                self.trigger.clicked()



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
        label = gtk.Label(_('Trigger text'))
        self.button_entry = DefaultEntry(_('No Name'))
        hbox.pack_start(label, False)
        hbox.pack_start(self.button_entry, False)
        
        spc = gtk.HBox()
        hbox.pack_start(spc, False, padding=3)
        
        label = gtk.Label(_('Level adjustment (dB)'))
        self.gain_adj = gtk.Adjustment(0.0, -10.0, 10.0, 0.5)
        gain = gtk.SpinButton(self.gain_adj, 1.0, 1)
        hbox.pack_start(label, False)
        hbox.pack_start(gain, False)

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
            self.gain_adj.set_value(0.0)



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
            vbox = gtk.VBox(True)
            hbox.pack_start(vbox)
            
            for row in range(rows):
                self.widgets.append(widget(count, self.widgets, *args))
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


    def update_leds(self, bits):
        bit = 0
        effect = iter(self.widgets)
        while bit < 24:
            effect.next().update_led((1 << bit) & bits)
            bit += 1
            
            
    def stop(self):
        for each in self.widgets:
            each.stop.clicked()
                
                
    def uuids(self):
        return (x.uuid for x in self.widgets)
        
        
    def pathnames(self):
        return (x.pathname for x in self.widgets)



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
        set_tip(jvol, _('Effects volume.'))

        pb = gtk.gdk.pixbuf_new_from_file(FGlobs.pkgdatadir / "headroom.png")
        jmute_image = gtk.image_new_from_pixbuf(pb)
        jmute = gtk.VScale(self.jmute_adj)
        jmute.set_inverted(True)
        jmute.set_draw_value(False)
        set_tip(jmute, _('Player headroom that is applied when an effect is playing.'))
        
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
        set_tip(ivol, _('Background Tracks volume.'))

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
