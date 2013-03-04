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


class EffectBank(gtk.Frame):
    """A vertical stack of effects with level controls."""

    def __init__(self, qty, base, filename, parent, all_effects, vol_adj, mute_adj):
        gtk.Frame.__init__(self)
        self.base = base
        self.session_filename = filename
        
        hbox = gtk.HBox()
        hbox.set_spacing(1)
        self.add(hbox)
        vbox = gtk.VBox()
        hbox.pack_start(vbox)
        
        self.effects = []
        self.all_effects = all_effects
        
        count = 0
        
        for row in range(qty):
            effect = Effect(base + row, self.all_effects, parent)
            self.effects.append(effect)
            self.all_effects.append(effect)
            vbox.pack_start(effect)
            count += 1

        level_vbox = gtk.VBox()
        hbox.pack_start(level_vbox, False, padding=3)
        
        vol_image = gtk.image_new_from_file(FGlobs.pkgdatadir / "volume2.png")
        vol = gtk.VScale(vol_adj)
        vol.set_inverted(True)
        vol.set_draw_value(False)
        set_tip(vol, _('Effects volume.'))

        pb = gtk.gdk.pixbuf_new_from_file(FGlobs.pkgdatadir / "headroom.png")
        mute_image = gtk.image_new_from_pixbuf(pb)
        mute = gtk.VScale(mute_adj)
        mute.set_inverted(True)
        mute.set_draw_value(False)
        set_tip(mute, _('Player headroom that is applied when an effect is playing.'))
        
        spc = gtk.VBox()
        
        for widget, expand in zip((vol_image, vol, spc, mute_image, mute), 
                                    (False, True, False, False, True)):
            level_vbox.pack_start(widget, expand, padding=2)

    def marshall(self):
        return json.dumps([x.marshall() for x in self.effects])

    def unmarshall(self, data):
        for per_widget_data, widget in zip(json.loads(data), self.effects):
            widget.unmarshall(per_widget_data)
   
    def restore_session(self):
        try:
            with open(PM.basedir / self.session_filename, "r") as f:
                self.unmarshall(f.read())
        except IOError:
            print "failed to read effects session file"

    def save_session(self, where):
        try:
            with open((where or PM.basedir) / self.session_filename, "w") as f:
                f.write(self.marshall())
        except IOError:
            print "failed to write effects session file"

    def update_leds(self, bits):
        for bit, each in enumerate(self.effects):
            each.update_led((1 << bit + self.base) & bits)

    def stop(self):
        for each in self.effects:
            each.stop.clicked()

    def uuids(self):
        return (x.uuid for x in self.widgets)

    def pathnames(self):
        return (x.pathname for x in self.widgets)


class LabelSubst(gtk.Frame):
    def __init__(self, heading):
        gtk.Frame.__init__(self, " %s " % heading)
        self.vbox = gtk.VBox()
        self.vbox.set_border_width(2)
        self.vbox.set_spacing(2)
        self.add(self.vbox)
        self.textdict = {}
        self.activedict = {}

    def add_widget(self, widget, ui_name, default_text):
        frame = gtk.Frame(" %s " % default_text)
        frame.set_label_align(0.5, 0.5)
        frame.set_border_width(3)
        self.vbox.pack_start(frame)
        hbox = gtk.HBox()
        hbox.set_spacing(3)
        frame.add(hbox)
        hbox.set_border_width(2)
        use_supplied = gtk.RadioButton(None, _("Alternative"))
        use_default = gtk.RadioButton(use_supplied, _('Default'))
        self.activedict[ui_name + "_use_supplied"] = use_supplied
        hbox.pack_start(use_default, False)
        hbox.pack_start(use_supplied, False)
        entry = gtk.Entry()
        self.textdict[ui_name + "_text"] = entry
        hbox.pack_start(entry)
        
        if isinstance(widget, gtk.Frame):
            def set_text(new_text):
                new_text = new_text.strip()
                if new_text:
                    new_text = " %s " % new_text
                widget.set_label(new_text or None)
            widget.set_text = set_text

        entry.connect("changed", self.cb_entry_changed, widget, use_supplied)
        args = default_text, entry, widget
        use_default.connect("toggled", self.cb_radio_default, *args)
        use_supplied.connect_object("toggled", self.cb_radio_default,
                                                            use_default, *args)
        use_default.set_active(True)
        
    def cb_entry_changed(self, entry, widget, use_supplied):
        if use_supplied.get_active():
            widget.set_text(entry.get_text())
        elif entry.has_focus():
            use_supplied.set_active(True)
        
    def cb_radio_default(self, use_default, default_text, entry, widget):
        if use_default.get_active():
            widget.set_text(default_text)
        else:
            widget.set_text(entry.get_text())
            entry.grab_focus()


class ExtraPlayers(gtk.HBox):
    """For effects, and background tracks."""
    
    def __init__(self, parent):
        self.approot = parent

        self.nb_label = gtk.Label()
        parent.label_subst.add_widget(self.nb_label, "jingles_tabtext", _('Jingles'))
            
        gtk.HBox.__init__(self)
        self.set_border_width(4)
        self.set_spacing(10)
        self.viewlevels = (5,)

        esbox = gtk.VBox()
        self.pack_start(esbox)
        estable = gtk.Table(columns=2, homogeneous=True)
        estable.set_col_spacing(1, 8)
        esbox.pack_start(estable)

        self.jvol_adj = (gtk.Adjustment(127.0, 0.0, 127.0, 1.0, 10.0),
                         gtk.Adjustment(127.0, 0.0, 127.0, 1.0, 10.0))
        self.jmute_adj = (gtk.Adjustment(100.0, 0.0, 127.0, 1.0, 10.0),
                          gtk.Adjustment(100.0, 0.0, 127.0, 1.0, 10.0))
        self.ivol_adj = gtk.Adjustment(64.0, 0.0, 127.0, 1.0, 10.0)
        for each in (self.jvol_adj[0], self.jvol_adj[1], self.ivol_adj,
                                        self.jmute_adj[0], self.jmute_adj[1]):
            each.connect("value-changed",
                                lambda w: parent.send_new_mixer_stats())

        effects_hbox = gtk.HBox(homogeneous=True)
        effects_hbox.set_spacing(6)
        effects = PGlobs.num_effects
        base = 0
        max_rows = 12
        effect_cols = (effects + max_rows - 1) // max_rows
        self.all_effects = []
        self.effect_banks = []
        for col in range(effect_cols):
            bank = EffectBank(min(effects - base, max_rows), base,
            "effects%d_session" % (col + 1), parent, self.all_effects,
            self.jvol_adj[col], self.jmute_adj[col])
            parent.label_subst.add_widget(bank, 
                            "effectbank%d" % col, _('Effects %d') % (col + 1))
            self.effect_banks.append(bank)
            effects_hbox.pack_start(bank)
            base += max_rows
        estable.attach(effects_hbox, 0, 2, 0, 1)

        interlude_frame = gtk.Frame()
        parent.label_subst.add_widget(interlude_frame, "bgplayername",
                                                        _('Background Tracks'))
        self.pack_start(interlude_frame)
        hbox = gtk.HBox()
        hbox.set_spacing(1)
        interlude_frame.add(hbox)
        interlude_box = gtk.VBox()
        hbox.pack_start(interlude_box)
        self.interlude = IDJC_Media_Player(interlude_box, "interlude", parent)
        interlude_box.set_no_show_all(True)

        ilevel_vbox = gtk.VBox()
        hbox.pack_start(ilevel_vbox, False, padding=3)
        volpb = gtk.gdk.pixbuf_new_from_file(FGlobs.pkgdatadir / "volume2.png")
        ivol_image = gtk.image_new_from_pixbuf(volpb)
        ilevel_vbox.pack_start(ivol_image, False, padding=2)
        ivol = gtk.VScale(self.ivol_adj)
        ivol.set_inverted(True)
        ivol.set_draw_value(False)
        ilevel_vbox.pack_start(ivol, padding=2)
        set_tip(ivol, _('Background Tracks volume.'))

        self.show_all()
        interlude_box.show()

    def restore_session(self):
        for each in self.effect_banks:
            each.restore_session()
        self.interlude.restore_session()
        
    def save_session(self, where):
        for each in self.effect_banks:
            each.save_session(where)
        self.interlude.save_session(where)

    def update_effect_leds(self, ep):
        for each in self.effect_banks:
            each.update_leds(ep)

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
