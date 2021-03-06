#   IDJCmixprefs.py: Preferences window code for IDJC
#   Copyright (C) 2005-2011 Stephen Fairchild (s-fairchild@users.sourceforge.net)
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

__all__ = ['mixprefs']


import os
import shutil
import gettext
import itertools

import gtk

from idjc import FGlobs, PGlobs
from . import licence_window
from . import songdb
from . import midicontrols
from .gtkstuff import WindowSizeTracker, DefaultEntry
from .prelims import ProfileManager
from .utils import PathStr
from .tooltips import set_tip, MAIN_TIPS


_ = gettext.translation(FGlobs.package_name, FGlobs.localedir,
                                                        fallback=True).gettext

def N_(text):
    return text


pm = ProfileManager()


class CSLEntry(gtk.Entry):
    def cb_keypress(self, widget, event):
        if event.string:
            if len(event.string) > 1:
                return True
            if not event.string in "0123456789,":
                return True
        return False
    def __init__(self, max = 0):
        gtk.Entry.__init__(self, max)
        self.connect("key-press-event", self.cb_keypress)



class InitialPlayerConfig(gtk.Frame):
    def __init__(self, title, player, prefix):
        self.player = player
        gtk.Frame.__init__(self, " %s " % title)
        vbox = gtk.VBox()
        vbox.set_border_width(3)
        self.add(vbox)
        
        pl_label = gtk.Label(_("Playlist Mode"))
        fade_label = gtk.Label(_("Fade"))
        if hasattr(gtk, "ComboBoxText"):
            self.pl_mode = gtk.ComboBoxText(player.pl_mode.get_model())
            self.fade = gtk.ComboBoxText(player.fade.get_model())
        else:
            self.pl_mode = gtk.combo_box_new_text()
            self.pl_mode.set_model(player.pl_mode.get_model())
            self.fade = gtk.combo_box_new_text()
            self.fade.set_model(player.pl_delay.get_model())
            
        for each in (self.pl_mode, self.fade):
            each.set_active(0)

        self.elapsed = gtk.RadioButton(None, _("Track time elapsed"))
        self.remaining = gtk.RadioButton(self.elapsed, 
                                                    _("Track time remaining"))
        s1 = gtk.HSeparator()
        self.to_stream = gtk.CheckButton(_("Audio to stream"))
        self.to_dj = gtk.CheckButton(_("Audio to DJ"))
        
        for each in (self.to_stream, self.to_dj):
            each.set_active(True)

        for each in (pl_label, self.pl_mode, fade_label, self.fade,
                self.elapsed, self.remaining, s1, self.to_stream, self.to_dj):
            vbox.pack_start(each, False)
        self.show_all()
        
        self.activedict = {
            prefix + "pl_mode": self.pl_mode,
            prefix + "fade": self.fade,
            prefix + "timeremaining": self.remaining,
            prefix + "tostream": self.to_stream,
            prefix + "todj": self.to_dj
        }


    def apply(self):
        p = self.player
        
        p.pl_mode.set_active(self.pl_mode.get_active())
        p.pl_delay.set_active(self.fade.get_active())
        p.stream.set_active(self.to_stream.get_active())
        p.listen.set_active(self.to_dj.get_active())
        if self.remaining.get_active():
            p.digiprogress_click()



class AGCControl(gtk.Frame):
    mic_modes = (
        # TC: Microphone mode combobox text.
        N_('Deactivated'),
        # TC: Microphone mode combobox text.
        N_('Basic input'),
        # TC: Microphone mode combobox text.
        N_('Processed input'), 
        # TC: Microphone mode combobox text.
        N_('Partnered with channel %s'))

    
    def sendnewstats(self, widget, wname):
        if wname != NotImplemented:
            if isinstance(widget, (gtk.SpinButton, gtk.Scale)):
                value = widget.get_value()
            if isinstance(widget, (gtk.ToggleButton, gtk.ComboBox)):
                value = int(widget.get_active())
            stringtosend = "INDX=%d\nAGCP=%s=%s\nACTN=%s\nend\n" % (
                                self.index, wname, str(value), "mic_control")
            self.approot.mixer_write(stringtosend)

    def set_partner(self, partner):
        self.partner = partner
        self.mode.set_cell_data_func(self.mode_cell,
                                        self.mode_cell_data_func, partner.mode)

    def mode_cell_data_func(self, celllayout, cell, model, iter, opposite):
        index = model.get_path(iter)[0]
        oindex = opposite.get_active()
        cell.props.sensitive = not (((index == 0 or index == 3) and oindex == 3)
                                                or (index == 3 and oindex == 0))
        trans = _(model.get_value(iter, 0))
        if index == 3:
            cell.props.text = trans % self.partner.ui_name
        else:
            cell.props.text = trans

    def numline(self, label_text, wname, initial=0, mini=0, maxi=0, step=0,
                                                            digits=0, adj=None):
        hbox = gtk.HBox()
        label = gtk.Label(label_text)
        if not adj:
            adj = gtk.Adjustment(initial, mini, maxi, step)
        sb = gtk.SpinButton(adj, 0, digits)
        sb.connect("value-changed", self.sendnewstats, wname)
        sb.emit("value-changed")
        hbox.pack_start(label, False, False, 0)
        hbox.pack_end(sb, False, False, 0)
        hbox.show_all()
        self.valuesdict[self.commandname + "_" + wname] = sb
        self.fixups.append(lambda: sb.emit("value-changed"))
        return hbox

    def frame(self, label, container):
        frame = gtk.Frame(label)
        container.pack_start(frame, False, False, 0)
        frame.show()
        ivbox = gtk.VBox()
        ivbox.set_border_width(3)
        frame.add(ivbox)
        ivbox.show()
        return ivbox

    def widget_frame(self, widget, container, tip, modes):
        frame = gtk.Frame()
        frame.modes = modes
        set_tip(frame, tip)
        frame.set_label_widget(widget)
        container.pack_start(frame, False, False, 0)
        frame.show()
        ivbox = gtk.VBox()
        ivbox.set_border_width(3)
        frame.add(ivbox)
        ivbox.show()
        return ivbox

    def toggle_frame(self, label_text, wname, container):
        frame = gtk.Frame()
        cb = gtk.CheckButton(label_text)
        cb.connect("toggled", self.sendnewstats, wname)
        cb.emit("toggled")
        cbb = gtk.HBox()
        cbb.pack_start(cb, True, False, 2)
        cb.show()
        frame.set_label_widget(cbb)
        cbb.show()
        container.pack_start(frame, False, False, 0)
        frame.show()
        ivbox = gtk.VBox()
        ivbox.set_border_width(3)
        frame.add(ivbox)
        ivbox.show()
        self.activedict[self.commandname + "_" + wname] = cb
        self.fixups.append(lambda: cb.emit("toggled"))
        return ivbox
    
    def check(self, label_text, wname, save=True):
        cb = gtk.CheckButton(label_text)
        cb.connect("toggled", self.sendnewstats, wname)
        cb.emit("toggled")
        cb.show()
        if save:
            self.activedict[self.commandname + "_" + wname] = cb
        self.fixups.append(lambda: cb.emit("toggled"))
        return cb
        
    def cb_open(self, widget):
        active = widget.get_active()
        self.meter.set_led(active)

    def cb_mode(self, combobox):
        mode = combobox.get_active()

        # Show pertinent features for each mode.
        def showhide(widget):
            try:
                modes = widget.modes
            except:
                pass
            else:
                if mode in modes:
                    widget.show()
                else:
                    widget.hide()
        self.vbox.foreach(showhide)
        
        # Meter sensitivity. Deactivated => insensitive.
        sens = mode != 0
        self.meter.set_sensitive(sens)
        if not sens:
             self.open.set_active(False)
        if mode == 3:
            self.partner.openaction.connect_proxy(self.open)
        else:
            self.openaction.connect_proxy(self.open)
            self.open.set_sensitive(self.no_front_panel_opener.get_active())
            
    def __init__(self, approot, ui_name, commandname, index):
        self.approot = approot
        self.ui_name = ui_name
        self.meter = approot.mic_meters[int(ui_name) - 1]
        self.meter.agc = self
        self.commandname = commandname
        self.index = index
        self.valuesdict = {}
        self.activedict = {}
        self.textdict = {}
        self.fixups = []
        gtk.Frame.__init__(self)
        hbox = gtk.HBox()
        hbox.set_spacing(3)

        label = gtk.Label('<span weight="600">' + ui_name + "</span>")
        label.set_use_markup(True)
        hbox.pack_start(label, False)
        label.show()
 
        self.alt_name = gtk.Entry()
        set_tip(self.alt_name, _('A label so you may describe briefly the '
                                                'role of this audio channel.'))
        self.textdict[self.commandname + "_alt_name"] = self.alt_name
        hbox.pack_start(self.alt_name, True, True)
        self.alt_name.show()
        hbox.show()
        
        self.set_label_widget(hbox)
        hbox.show()
        self.set_label_align(0.5, 0.5)
        self.set_border_width(3)
        self.vbox = gtk.VBox()
        self.vbox.set_spacing(2)
        self.vbox.set_border_width(3)
        self.add(self.vbox)
        self.vbox.show()

        mode_liststore = gtk.ListStore(str)
        self.mode = gtk.ComboBox(mode_liststore)
        self.mode_cell = gtk.CellRendererText()
        self.mode.pack_start(self.mode_cell)
        self.mode.set_attributes(self.mode_cell, text=0)
        self.fixups.append(lambda: self.mode.emit("changed"))
        
        self.vbox.pack_start(self.mode, False, False)
        
        for each in self.mic_modes:
            mode_liststore.append((each, ))
        self.mode.connect("changed", self.sendnewstats, "mode")
        self.mode.connect("changed", self.cb_mode)
        self.activedict[self.commandname + "_mode"] = self.mode
        self.mode.show()
        set_tip(self.mode, _('The signal processing mode.'))

        hbox = gtk.HBox()
        # TC: A frame heading. The channel opener is selected within. 
        label = gtk.Label(_('Channel Opener'))
        hbox.pack_start(label, False, False, 3)
        label.show()
        ivbox = self.widget_frame(hbox, self.vbox, _('This controls the '
            'allocation of front panel open/unmute buttons. Having one button '
            'control multiple microphones can save time.'), (1, 2))
        hbox.show()
                
        hbox = gtk.HBox()
        # TC: Spinbutton label text.
        self.group = gtk.RadioButton(None, _('Main Panel Button'))
        self.activedict[self.commandname + "_group"] = self.group
        hbox.pack_start(self.group, False, False, 0)
        self.group.show()
        ivbox.pack_start(hbox, False, False)
        hbox.show()
        
        self.groups_adj = gtk.Adjustment(1.0, 1.0, PGlobs.num_micpairs * 2, 1.0)
        self.valuesdict[self.commandname + "_groupnum"] = self.groups_adj
        groups_spin = gtk.SpinButton(self.groups_adj, 0.0, 0)
        hbox.pack_end(groups_spin, False)
        groups_spin.show()

        hbox = gtk.HBox()
        hbox.set_spacing(6)
        ivbox.pack_start(hbox, False)
        hbox.show()
        self.no_front_panel_opener = gtk.RadioButton(self.group, _("This:"))
        self.activedict[self.commandname + "_using_local_opener"] = \
                                                    self.no_front_panel_opener
        self.no_front_panel_opener.connect("toggled",
                            lambda w: self.open.set_sensitive(w.get_active()))
        hbox.pack_start(self.no_front_panel_opener, False)
        self.no_front_panel_opener.show()

        self.openaction = gtk.ToggleAction(None, _('Closed'), None, None)
        self.openaction.connect("toggled", lambda w: w.set_label(_('Open')
                                            if w.get_active() else _('Closed')))

        self.open = gtk.ToggleButton()
        self.open.connect("toggled", self.cb_open)
        self.open.connect("toggled", self.sendnewstats, "open")
        hbox.pack_start(self.open)
        self.open.show()
        self.openaction.connect_proxy(self.open)
        self.open.emit("toggled")
        self.open.set_sensitive(False)
        self.fixups.append(lambda: self.open.emit("toggled"))

        sizegroup = gtk.SizeGroup(gtk.SIZE_GROUP_HORIZONTAL)
        panframe = gtk.Frame()
        panframe.modes = (1, 2, 3)
        set_tip(panframe, _('Stereo panning is the selection of where an audio '
        'source sits from left to right within the stereo mix.\n\nThis control '
        'maintains constant audio power throughout its range of travel, giving '
        '-3dB attenuation in both audio channels at the half way point.\n\n'
        'If you require 0dB straight down the middle then this feature should '
        'be turned off.'))
        
        hbox = gtk.HBox()
        self.pan_active = gtk.CheckButton(_('Stereo Panning'))
        self.activedict[self.commandname + "_pan_active"] = self.pan_active
        hbox.pack_start(self.pan_active, False, False, 0)
        self.pan_active.show()
        self.pan_active.connect("toggled", self.sendnewstats, "pan_active")
        panframe.set_label_widget(hbox)
        hbox.show()
        self.fixups.append(lambda: self.pan_active.emit("toggled"))
        
        panvbox = gtk.VBox()
        panvbox.set_border_width(1)
        panframe.add(panvbox)
        panhbox = gtk.HBox()
        panvbox.pack_start(panhbox, False, False)
        panhbox.set_spacing(3)
        panhbox.set_border_width(3)
        l = gtk.Label(_('L'))
        sizegroup.add_widget(l)
        panhbox.pack_start(l, False, False)
        panadj = gtk.Adjustment(50.0, 0.0, 100.0, 1, 10)
        self.pan = gtk.HScale(panadj)
        self.pan.set_draw_value(False)
        self.pan.connect("value-changed", self.sendnewstats, "pan")
        self.pan.emit("value-changed")
        self.fixups.append(lambda: self.pan.emit("value-changed"))
        self.valuesdict[self.commandname + "_pan"] = self.pan
        panhbox.pack_start(self.pan)
        r = gtk.Label(_('R'))
        sizegroup.add_widget(r)
        panhbox.pack_start(r, False, False)
        self.pan.add_mark(50.0, gtk.POS_BOTTOM, None)
        self.pan.add_mark(25.0, gtk.POS_BOTTOM, None)
        self.pan.add_mark(75.0, gtk.POS_BOTTOM, None)
        self.vbox.pack_start(panframe, False, False)
        panframe.show_all()

        # TC: A set of controls that perform audio signal matching.
        pairedframe = gtk.Frame(" %s " % _('Signal Matching'))
        set_tip(pairedframe, _('These controls are provided to obtain a decent '
                                        'match between the two microphones.'))
        pairedframe.modes = (3, )
        self.vbox.pack_start(pairedframe, False)
        pairedvbox = gtk.VBox()
        pairedvbox.set_border_width(3)
        pairedframe.add(pairedvbox)
        pairedvbox.show()
        pairedmicgainadj = gtk.Adjustment(0.0, -20.0, +20.0, 0.1, 2)
        pairedmicgain = self.numline(_('Relative Gain (dB)'), "pairedgain",
                                                digits=1, adj=pairedmicgainadj)
        pairedvbox.pack_start(pairedmicgain, False)
        pairedmicgain.show()
        # TC: Mic audio phase inversion control.
        pairedinvert = self.check(_('Invert Signal'), "pairedinvert")
        pairedvbox.pack_start(pairedinvert, False)
        pairedinvert.show()

        micgainadj = gtk.Adjustment(0.0, -20.0, +30.0, 0.1, 2)
        invertaction = gtk.ToggleAction("invert", _('Invert Signal'), 
                    _('Useful for when microphones are cancelling one another '
                                        'out, producing a hollow sound.'), None)
        # TC: Control whether to mix microphone audio to the DJ mix.
        indjmixaction = gtk.ToggleAction("indjmix", _("In The DJ's Mix"), 
                        _('Make the microphone audio audible in the DJ mix. '
                        'This may not always be desirable.'), None)

        self.simple_box = gtk.VBox()
        self.simple_box.set_spacing(2)
        self.vbox.pack_start(self.simple_box, False, False)
        self.simple_box.modes = (1, )

        ivbox = self.frame(" " + _('Basic Controls') + " ", self.simple_box)
        micgain = self.numline(_('Boost/Cut (dB)'), "gain",
                                                    digits=1, adj=micgainadj)
        ivbox.pack_start(micgain, False, False)
        
        invert_simple = self.check("", "invert")
        invertaction.connect_proxy(invert_simple)
        ivbox.pack_start(invert_simple, False, False)
        set_tip(invert_simple, _('Useful for when microphones are cancelling '
                                'one another out, producing a hollow sound.'))
        
        indjmix = self.check("", "indjmix")
        indjmixaction.connect_proxy(indjmix)
        ivbox.pack_start(indjmix, False, False)
        set_tip(indjmix, _('Make the microphone audio audible in the DJ mix. '
                                        'This may not always be desirable.'))

        self.processed_box = gtk.VBox()
        self.processed_box.modes = (2, )
        self.processed_box.set_spacing(2)
        self.vbox.pack_start(self.processed_box, False, False)

        ivbox = self.frame(" %s " % _('High Pass Filter'), self.processed_box)
        hpcutoff = self.numline(_('Cutoff Frequency'), "hpcutoff",
                                                    100.0, 30.0, 120.0, 1.0, 1)
        ivbox.pack_start(hpcutoff, False, False, 0)
        # TC: User can set the number of filter stages.
        hpstages = self.numline(_('Stages'), "hpstages", 4.0, 1.0, 4.0, 1.0, 0)
        ivbox.pack_start(hpstages, False, False, 0)
        set_tip(ivbox, 
            _('Frequency in Hertz above which audio can pass to later stages. '
            'Use this feature to restrict low frequency sounds such as mains '
            'hum. Setting too high a level will make your voice sound thin.'))
        
        # TC: this is the treble control. HF = high frequency.
        ivbox = self.frame(" " + _('HF Detail') + " ", self.processed_box)
        hfmulti = self.numline(_('Effect'), "hfmulti", 0.0, 0.0, 9.0, 0.1, 1)
        ivbox.pack_start(hfmulti, False, False, 0)
        hfcutoff = self.numline(_('Cutoff Frequency'), "hfcutoff",
                                                2000.0, 900.0, 4000.0, 10.0, 0)
        ivbox.pack_start(hfcutoff, False, False, 0)
        set_tip(ivbox, 
            _('You can use this to boost the amount of treble in the audio.'))
         
        # TC: this is the bass control. LF = low frequency.
        ivbox = self.frame(" " + _('LF Detail') + " ", self.processed_box)
        lfmulti = self.numline(_('Effect'), "lfmulti", 0.0, 0.0, 9.0, 0.1, 1)
        ivbox.pack_start(lfmulti, False, False, 0)
        lfcutoff = self.numline(_('Cutoff Frequency'), "lfcutoff",
                                                    150.0, 50.0, 400.0, 1.0, 0)
        ivbox.pack_start(lfcutoff, False, False, 0)
        set_tip(ivbox,
            _('You can use this to boost the amount of bass in the audio.'))
        
        # TC: lookahead brick wall limiter.
        ivbox = self.frame(" " + _('Limiter') + " ", self.processed_box)
        micgain = self.numline(_('Boost/Cut (dB)'), "gain",
                                                    digits=1, adj=micgainadj)
        ivbox.pack_start(micgain, False, False, 0)
        # TC: this is the peak signal limit.
        limit = self.numline(_('Upper Limit'), "limit", -3.0, -9.0, 0.0, 0.5, 1)
        ivbox.pack_start(limit, False, False, 0)
        set_tip(ivbox, _('A look-ahead brick-wall limiter. Audio signals are '
                                                'capped at the upper limit.'))
        
        ivbox = self.frame(" " + _('Noise Gate') + " ", self.processed_box)
        # TC: noise gate triggers at this level.
        ng_thresh = self.numline(_('Threshold'), "ngthresh",
                                                    -30.0, -62.0, -20.0, 1.0, 0)
        ivbox.pack_start(ng_thresh, False, False, 0)
        # TC: negative gain when the noise gate is active.
        ng_gain = self.numline(_('Gain'), "nggain", -6.0, -12.0, 0.0, 1.0, 0)
        ivbox.pack_start(ng_gain, False, False, 0)
        set_tip(ivbox, _("Reduce the unwanted quietest sounds and background "
                "noise which you don't want your listeners to hear with this."))
        
        ivbox = self.frame(" " + _('De-esser') + " ", self.processed_box)
        # TC: Bias has a numeric setting.
        ds_bias = self.numline(_('Bias'), "deessbias", 0.35, 0.1, 10.0, 0.05, 2)
        ivbox.pack_start(ds_bias, False, False, 0)
        # TC: The de-esser attenuation in ess-detected state.
        ds_gain = self.numline(_('Gain'), "deessgain", -4.5, -10.0, 0.0, 0.5, 1)
        ivbox.pack_start(ds_gain, False, False, 0)
        set_tip(ivbox, _('Reduce the S, T, and P sounds which microphones tend '
        'to exaggerate. Ideally the Bias control will be set low so that the '
        'de-esser is off when there is silence but is set high enough that '
        'mouse clicks are detected and suppressed.'))
        
        ivbox = self.toggle_frame(_('Ducker'), "duckenable", self.processed_box)
        duckrelease = self.numline(_('Release'), "duckrelease",
                                                400.0, 100.0, 999.0, 10.0, 0)
        ivbox.pack_start(duckrelease, False, False, 0)
        duckhold = self.numline(_('Hold'), "duckhold",
                                                350.0, 0.0, 999.0, 10.0, 0)
        ivbox.pack_start(duckhold, False, False, 0)
        set_tip(ivbox, _('The ducker automatically reduces the level of player '
                'audio when the DJ speaks. These settings allow you to adjust'
                ' the timings of that audio reduction.'))
         
        ivbox = self.frame(" " + _('Other options') + " ", self.processed_box)

        invert_complex = self.check("", NotImplemented, save=False)
        invertaction.connect_proxy(invert_complex)
        ivbox.pack_start(invert_complex, False, False)
        set_tip(invert_complex, _('Useful for when microphones are cancelling '
                                'one another out, producing a hollow sound.'))
        phaserotate = self.check(_('Phase Rotator'), "phaserotate")
        ivbox.pack_start(phaserotate, False, False, 0)
        set_tip(phaserotate, 
        _('This feature processes the microphone audio so that it sounds more '
        'even. The effect is particularly noticable on male voices.'))
        indjmix = self.check("", NotImplemented, save=False)
        indjmixaction.connect_proxy(indjmix)
        ivbox.pack_start(indjmix, False, False)
        set_tip(indjmix, _('Make the microphone audio audible in the DJ mix. '
                                        'This may not always be desirable.'))

        self.mode.set_active(0)
        indjmix.set_active(True)
        self.partner = None



class mixprefs:
    def send_new_resampler_stats(self):
        self.parent.mixer_write("RSQT=%d\nACTN=resamplequality\nend\n"
                                                        % self.resample_quality)


    def cb_resample_quality(self, widget, data):
        if widget.get_active():
            self.resample_quality = data
            self.send_new_resampler_stats()

        
    def cb_dither(self, widget, data = None):
        if widget.get_active():
            string_to_send = "ACTN=dither\nend\n"
        else:
            string_to_send = "ACTN=dontdither\nend\n"
        self.parent.mixer_write(string_to_send)


    def cb_vol_changed(self, widget):
        self.parent.send_new_mixer_stats()


    def cb_restore_session(self, widget, data=None):
        state = not widget.get_active()
        for each in (self.lpconfig, self.rpconfig, self.misc_session_frame):
            each.set_sensitive(state)


    def delete_event(self, widget, event, data=None):
        self.window.hide()
        return True


    def save_resource_template(self):
        try:
            with open(pm.basedir / "config", "w") as f:
                f.write("[resource_count]\n")
                for name, widget in self.rrvaluesdict.iteritems():
                    f.write(name + "=" + str(int(widget.get_value())) + "\n")
                f.write("num_effects=%d\n" % (24 if self.more_effects.get_active() else 12))
        except IOError:
            print "Error while writing out player defaults"


    def save_player_prefs(self, where=None):
        try:
            with open((where or pm.basedir) / "playerdefaults", "w") as f:
                for name, widget in self.activedict.iteritems():
                    f.write(name + "=" + str(int(widget.get_active())) + "\n")
                for name, widget in self.valuesdict.iteritems():
                    f.write(name + "=" + str(widget.get_value()) + "\n")
                for name, widget in self.textdict.iteritems():
                    if widget.get_text() is not None:
                        f.write(name + "=" + widget.get_text() + "\n")
                    else:
                        f.write(name + "=\n")
        except IOError:
            print "Error while writing out player defaults"

            
    def load_player_prefs(self):
        songdb_active = False
        try:
            file = open(pm.basedir / "playerdefaults")
            
            while 1:
                line = file.readline()
                if line == "":
                    break
                if line.count("=") != 1:
                    continue
                line = line.split("=")
                key = line[0].strip()
                value = line[1][:-1].strip()
                if self.activedict.has_key(key):
                    if value == "True":
                        value = True
                    elif value == "False":
                        value = False
                    else:
                        value = int(value)
                    if key == "songdb_active":
                        songdb_active = value
                    else:
                        self.activedict[key].set_active(value)
                elif self.valuesdict.has_key(key):
                    self.valuesdict[key].set_value(float(value))
                elif self.textdict.has_key(key):
                    self.textdict[key].set_text(value)
            file.close()
        except IOError:
            print "Failed to read playerdefaults file"
        if songdb_active:
            self.activedict["songdb_active"].set_active(songdb_active)
        self.parent.send_new_mixer_stats()
            
    def apply_player_prefs(self):
        for each in (self.lpconfig, self.rpconfig):
            each.apply()
            
        if self.startmini.get_active():
            self.mini.clicked()
                    
        if self.tracks_played.get_active():
            self.parent.history_expander.set_expanded(True)
            self.parent.history_vbox.show()
        if self.stream_mon.get_active():
            self.parent.listen_stream.set_active(True)

    def callback(self, widget, data):
        parent = self.parent
        if data == "basic streamer":
            if parent.feature_set.get_active():
                parent.feature_set.set_active(False)
        if data == "fully featured":
            if not parent.feature_set.get_active():
                parent.feature_set.set_active(True)
        if data == "enhanced-crossfader":
            if widget.get_active():
                parent.listen.show()
                parent.passleft.show()
                parent.passright.show()
                parent.passspeed.show()
                parent.passbutton.show()
            else:
                parent.listen.hide()
                parent.passleft.hide()
                parent.passright.hide()
                parent.passspeed.hide()
                parent.passbutton.hide()
                parent.listen.set_active(False)
        if data == "bigger box":
            if widget.get_active():
                self.parent.player_left.digiprogress.set_width_chars(7)
                self.parent.player_right.digiprogress.set_width_chars(7)
            else:
                self.parent.player_left.digiprogress.set_width_chars(6)
                self.parent.player_right.digiprogress.set_width_chars(6)
        if data == "tooltips":
            if widget.get_active():
                MAIN_TIPS.enable()
            else:
                MAIN_TIPS.disable()

    def cb_mic_boost(self, widget):
        self.parent.send_new_mixer_stats()
                          
    def cb_pbspeed(self, widget):
        if widget.get_active():
            self.parent.player_left.pbspeedbar.set_value(64.0)
            self.parent.player_right.pbspeedbar.set_value(64.0)
            self.parent.player_left.pbspeedbox.show()
            self.parent.player_right.pbspeedbox.show()
            self.parent.jingles.interlude.pbspeedbar.set_value(64.0)
            self.parent.jingles.interlude.pbspeedbox.show()
        else:
            self.parent.player_left.pbspeedbox.hide()
            self.parent.player_right.pbspeedbox.hide()
            self.parent.jingles.interlude.pbspeedbox.hide()
        self.parent.send_new_mixer_stats()

    def cb_dual_volume(self, widget):
        if widget.get_active():
            self.parent.deck2adj.set_value(self.parent.deckadj.get_value())
            self.parent.deck2vol.show()
            set_tip(self.parent.deckvol,
                            _('The volume control for the left music player.'))
        else:
            if self.parent.player_left.is_playing ^ \
                                            self.parent.player_right.is_playing:
                if self.parent.player_left.is_playing:
                    self.parent.deck2adj.set_value(
                                            self.parent.deckadj.get_value())
                else:
                    self.parent.deckadj.set_value(
                                            self.parent.deck2adj.get_value())
            else:
                halfdelta = (self.parent.deck2adj.get_value() - \
                                            self.parent.deckadj.get_value()) / 2
                self.parent.deck2adj.props.value -= halfdelta
                self.parent.deckadj.props.value += halfdelta
            
            self.parent.deck2vol.hide()
            set_tip(self.parent.deckvol,
                        _('The volume control shared by both music players.'))

    def cb_rg_indicate(self, widget):
        show = widget.get_active()
        for each in (self.parent.player_left, self.parent.player_right,
                                                self.parent.jingles.interlude):
            each.show_replaygain_markers(show)

    def cb_realize(self, window):
        self.wst.apply()
            
    def show_about(self):
        self.notebook.set_current_page(self.notebook.page_num(self.aboutframe))
        self.window.present()

    def fixup_mic_controls(self):
        """Send mic preferences to the backend.
        
        This needs to be called whenever the backend is restarted.
        """
        for mic in self.mic_controls:
            for fixup in mic.fixups:
                fixup()

    def __init__(self, parent):
        self.parent = parent
        self.parent.prefs_window = self
        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.window.set_size_request(-1, 480)
        self.window.connect("realize", self.cb_realize)
        self.parent.window_group.add_window(self.window)
        # TC: preferences window title.
        self.window.set_title(_('IDJC Preferences') + pm.title_extra)
        self.window.set_border_width(10)
        self.window.set_resizable(True)
        self.window.connect("delete_event",self.delete_event)
        self.window.set_destroy_with_parent(True)
        self.notebook = gtk.Notebook()
        self.window.add(self.notebook)
        self.wst = WindowSizeTracker(self.window)

        # General tab
        
        generalwindow = gtk.ScrolledWindow()
        generalwindow.set_border_width(8)
        generalwindow.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        outervbox = gtk.VBox()
        outervbox.set_spacing(5)
        generalwindow.add_with_viewport(outervbox)
        generalwindow.show()
        outervbox.set_border_width(3)

        aud_rs_hbox = gtk.HBox()
        
        # User can use this to set the audio level in the headphones
        
        # TC: The DJ's sound level controller.
        frame = gtk.Frame(" %s " % _('DJ Audio Level'))
        frame.set_label_align(0.5, 0.5)
        frame.set_border_width(3)
        hbox = gtk.HBox()
        hbox.set_border_width(5)
        frame.add(hbox)
        hbox.show()
        self.dj_aud_adj = gtk.Adjustment(0.0, -60.0, 0.0, 0.5, 1.0)
        dj_aud = gtk.SpinButton(self.dj_aud_adj, 1, 1)
        dj_aud.connect("value-changed", self.cb_vol_changed)
        hbox.pack_start(dj_aud, True, False, 0)
        dj_aud.show()
        set_tip(dj_aud, _('This adjusts the sound level of the DJ audio.'))
        aud_rs_hbox.pack_start(frame, False, False, 0)
        frame.show()

        # TC: The alarm sound level.
        frame = gtk.Frame(" %s " % _('Alarm Level'))
        frame.set_label_align(0.5, 0.5)
        frame.set_border_width(3)
        hbox = gtk.HBox()
        hbox.set_border_width(5)
        frame.add(hbox)
        hbox.show()
        self.alarm_aud_adj = gtk.Adjustment(0.0, -60.0, 0.0, 0.5, 1.0)
        alarm_aud = gtk.SpinButton(self.alarm_aud_adj, 1, 1)
        alarm_aud.connect("value-changed", self.cb_vol_changed)
        hbox.pack_start(alarm_aud, True, False, 0)
        alarm_aud.show()
        set_tip(alarm_aud, _('This adjusts the sound level of the DJ alarm. '
        'Typically this should be set close to the dj audio level when using the \'%s\''
        ' feature, otherwise a bit louder.' % _('Music Loudness Compensation')))
        aud_rs_hbox.pack_start(frame, False, False, 0)
        frame.show()

        # User can use this to set the resampled sound quality
        
        frame = gtk.Frame(" %s " % _('Player Resample Quality'))
        frame.set_label_align(0.5, 0.5)
        frame.set_border_width(3)
        hbox = gtk.HBox()
        hbox.set_border_width(5)
        set_tip(hbox,
        _('This adjusts the quality of the audio resampling method '
        'used whenever the sample rate of the music file currently playing does'
        ' not match the sample rate of the JACK sound server. Best mode '
        'offers the best sound quality but also uses the most CPU (not '
        'recommended for systems built before 2006). All these modes provide '
        'adequate sound quality.'))
        frame.add(hbox)
        hbox.show()
        self.best_quality_resample = gtk.RadioButton(None, _('Best'))
        self.best_quality_resample.connect(
                                        "toggled", self.cb_resample_quality, 0)
        rsbox = gtk.HBox()
        rsbox.pack_start(self.best_quality_resample, True, False, 0)
        rsbox.show()
        hbox.add(rsbox)
        self.best_quality_resample.show()
        self.good_quality_resample = gtk.RadioButton(
                                        self.best_quality_resample, _('Medium'))
        self.good_quality_resample.connect(
                                        "toggled", self.cb_resample_quality, 1) 
        rsbox = gtk.HBox()
        rsbox.pack_start(self.good_quality_resample, True, False, 0)
        rsbox.show()
        hbox.add(rsbox)
        self.good_quality_resample.show()
        self.fast_resample = gtk.RadioButton(
                                        self.good_quality_resample, _('Fast'))
        self.fast_resample.connect("toggled", self.cb_resample_quality, 2) 
        rsbox = gtk.HBox()
        rsbox.pack_start(self.fast_resample, True, False, 0)
        rsbox.show()
        hbox.add(rsbox)
        self.fast_resample.show()

        aud_rs_hbox.pack_start(frame, True, True, 0)
        frame.show()
        
        outervbox.pack_start(aud_rs_hbox, False, False, 0)
        aud_rs_hbox.show()
        
        # TC: the set of features - section heading.
        featuresframe = gtk.Frame(" %s " % _('Feature Set'))
        featuresframe.set_border_width(3)
        featuresvbox = gtk.VBox()
        hbox = gtk.HBox()
        hbox.set_border_width(2)
        featuresvbox.pack_start(hbox, False)
        featuresframe.add(featuresvbox)
        featuresvbox.show()
        outervbox.pack_start(featuresframe, False, False, 0)
        featuresframe.show()
        vbox = gtk.VBox()
        # TC: Start in the full featured user interface mode.
        self.startfull = gtk.RadioButton(None, _('Start Full'))
        self.startfull.set_border_width(2)
        vbox.pack_start(self.startfull, False, False, 0)
        self.startfull.show()
        set_tip(self.startfull,
                    _('Indicates which mode IDJC will be in when launched.'))
        
        # TC: Start in a reduced user interface mode.
        self.startmini = gtk.RadioButton(self.startfull, _('Start Mini'))
        self.startmini.set_border_width(2)
        vbox.pack_start(self.startmini, False, False, 0)
        self.startmini.show()
        set_tip(self.startmini,
                    _('Indicates which mode IDJC will be in when launched.'))
        
        vbox.show()
        hbox2 = gtk.HBox()
        hbox2.set_border_width(10)
        hbox2.set_spacing(20)
        hbox.pack_start(hbox2, True, False, 0)
        
        self.maxi = gtk.Button(" %s " % _('Fully Featured'))
        self.maxi.connect("clicked", self.callback, "fully featured")
        hbox2.pack_start(self.maxi, False, False, 0)
        self.maxi.show()
        set_tip(self.maxi,
                _('Run in full functionality mode which uses more CPU power.'))
        
        self.mini = gtk.Button(" %s " % _('Basic Streamer'))
        self.mini.connect("clicked", self.callback, "basic streamer")
        hbox2.pack_start(self.mini, False, False, 0)
        self.mini.show()
        set_tip(self.mini, _('Run in a reduced functionality mode that lowers '
                    'the burden on the CPU and takes up less screen space.'))
        
        hbox2.show()    
        hbox.pack_start(vbox, False, False, 9)    
        hbox.show()
        
        requires_restart = gtk.Frame(" %s " % 
                            _('These settings take effect after restarting'))
        requires_restart.set_border_width(7)
        featuresvbox.pack_start(requires_restart, False)
        requires_restart.show()
        
        rrvbox = gtk.VBox()
        rrvbox.set_border_width(9)
        rrvbox.set_spacing(4)
        requires_restart.add(rrvbox)
        rrvbox.show()

        def hjoin(*widgets):
            hbox = gtk.HBox()
            hbox.set_spacing(3)
            for w in widgets:
                hbox.pack_start(w, False)
                w.show()
            hbox.show()
            return hbox

        self.more_effects = gtk.RadioButton(None, 
                                        _('Reserve 24 sound effects slots'))
        fewer_effects = gtk.RadioButton(self.more_effects, _("Only 12"))
        if PGlobs.num_effects == 24:
            self.more_effects.clicked()
        else:
            fewer_effects.clicked()
       
        rrvbox.pack_start(hjoin(self.more_effects, fewer_effects))

        self.mic_qty_adj = gtk.Adjustment(
                                        PGlobs.num_micpairs * 2, 2.0, 12.0, 2.0)
        spin = gtk.SpinButton(self.mic_qty_adj)
        rrvbox.pack_start(hjoin(spin, gtk.Label(
                                        _('Audio input channels'))))
    
        self.stream_qty_adj = gtk.Adjustment(
                                            PGlobs.num_streamers, 1.0, 9.0, 1.0)
        spin = gtk.SpinButton(self.stream_qty_adj)
        rrvbox.pack_start(hjoin(spin, gtk.Label(_('Simultaneous stream(s)'))))

        self.recorder_qty_adj = gtk.Adjustment(
                                            PGlobs.num_recorders, 0.0, 4.0, 1.0)
        spin = gtk.SpinButton(self.recorder_qty_adj)
        rrvbox.pack_start(hjoin(spin, gtk.Label(
                                            _('Simultaneous recording(s)'))))
        
        self.rrvaluesdict = {"num_micpairs": self.mic_qty_adj,
                                    "num_streamers": self.stream_qty_adj,
                                    "num_recorders": self.recorder_qty_adj}
        
        # Meters on/off
        
        def showhide(toggle, target):
            if toggle.get_active():
                target.show()
            else:
                target.hide()
        frame = gtk.Frame(" %s " % _('View'))
        frame.set_border_width(3)
        hbox = gtk.HBox(3, True)
        hbox.set_border_width(10)
        frame.add(hbox)
        hbox.show()

        vbox = gtk.VBox()
        hbox.pack_start(vbox)
        vbox.show()
        self.show_stream_meters = gtk.CheckButton()
        self.show_stream_meters.set_active(True)
        self.show_stream_meters.connect(
                                    "toggled", showhide, parent.streammeterbox)
        vbox.pack_start(self.show_stream_meters, False)
        self.show_stream_meters.show()

        self.show_background_tracks_player = gtk.CheckButton()
        self.show_background_tracks_player.set_active(True)
        self.show_background_tracks_player.connect(
                            "toggled", showhide, parent.jingles.interlude_frame)
        vbox.pack_start(self.show_background_tracks_player, False)
        self.show_background_tracks_player.show()
        
        self.show_button_bar = gtk.CheckButton()
        self.show_button_bar.set_active(True)
        self.show_button_bar.connect("toggled", showhide, parent.hbox10)
        self.show_button_bar.connect("toggled", showhide, parent.hbox10spc)
        vbox.pack_start(self.show_button_bar, False)
        self.show_button_bar.show()

        vbox = gtk.VBox()
        hbox.pack_start(vbox)
        vbox.show()
        self.show_microphones = gtk.CheckButton()
        self.show_microphones.set_active(True)
        self.show_microphones.connect("toggled", showhide, parent.micmeterbox)
        vbox.pack_start(self.show_microphones, False)
        self.show_microphones.show()                
        
        self.no_mic_void_space = gtk.CheckButton(
                                            _('Fill channel meter void space'))
        self.no_mic_void_space.set_active(True)
        for meter in parent.mic_meters:
            self.no_mic_void_space.connect("toggled", meter.always_show)
        vbox.pack_start(self.no_mic_void_space, False)
        self.no_mic_void_space.show()
        
        outervbox.pack_start(frame, False, False, 0)
        frame.show()
        
        # ReplayGain controls
        
        frame = gtk.Frame(" %s " % _('Player Loudness Normalisation'))
        frame.set_border_width(3)
        outervbox.pack_start(frame, False, False, 0)
        vbox = gtk.VBox()
        frame.add(vbox)
        frame.show()
        vbox.set_border_width(10)
        vbox.set_spacing(1)
        vbox.show()
        
        self.rg_indicate = gtk.CheckButton(
                            _('Indicate which tracks have loudness metadata'))
        set_tip(self.rg_indicate, _('Shows a marker in the playlists next to'
                    ' each track. Either a green circle or a red triangle.'))
        self.rg_indicate.connect("toggled", self.cb_rg_indicate)
        vbox.pack_start(self.rg_indicate, False, False, 0)
        self.rg_indicate.show()
        
        
        
        self.rg_adjust = gtk.CheckButton(_('Adjust playback volume in dB'))
        set_tip(self.rg_adjust, _('Effective only on newly started tracks.'))
        vbox.pack_start(self.rg_adjust, False, False, 0)
        self.rg_adjust.show()
        
        table = gtk.Table(2, 6)
        table.set_col_spacings(3)
        label = gtk.Label(_('R128'))
        label.set_alignment(1.0, 0.5)
        r128_boostadj = gtk.Adjustment(4.0, -5.0, 25.5, 0.5)
        self.r128_boost = gtk.SpinButton(r128_boostadj, 0.0, 1)
        set_tip(self.r128_boost, _('It may not be desirable to use the '
                    'default level since it is rather quiet. This should be'
                    ' set 4 or 5 dB higher than the ReplayGain setting.'))
        table.attach(label, 0, 1, 0, 1)
        table.attach(self.r128_boost, 1, 2, 0, 1)
        label = gtk.Label(_('ReplayGain'))
        label.set_alignment(1.0, 0.5)
        rg_boostadj = gtk.Adjustment(0.0, -10.0, 20.5, 0.5)
        self.rg_boost = gtk.SpinButton(rg_boostadj, 0.0, 1)
        set_tip(self.rg_boost, _('It may not be desirable to use the default'
                        ' level since it is rather quiet. This should be set'
                        ' 4 or 5 dB lower than the R128 setting.'))
        table.attach(label, 2, 3, 0, 1)
        table.attach(self.rg_boost, 3, 4, 0, 1)
        label = gtk.Label(_('Untagged'))
        label.set_alignment(1.0, 0.5)
        rg_defaultgainadj = gtk.Adjustment(-8.0, -30.0, 10.0, 0.5)
        self.rg_defaultgain = gtk.SpinButton(rg_defaultgainadj, 0.0, 1)
        set_tip(self.rg_defaultgain, _('Set this so that any unmarked tracks'
        ' are playing at a roughly similar loudness level as the marked ones.'))
        table.attach(label, 4, 5, 0, 1)
        table.attach(self.rg_defaultgain, 5, 6, 0, 1)

        label = gtk.Label(_('All'))
        label.set_alignment(1.0, 0.5)
        all_boostadj = gtk.Adjustment(0.0, -10.0, 10.0, 0.5)
        self.all_boost = gtk.SpinButton(all_boostadj, 0.0, 1)
        set_tip(self.all_boost, _('A master level control for the media players.'))
        table.attach(label, 0, 1, 1, 2)
        table.attach(self.all_boost, 1, 2, 1, 2)
        
        vbox.pack_start(table, False)
        table.set_col_spacing(1, 7)
        table.set_col_spacing(3, 7)
        table.show_all()

        # Recorder filename format may be desirable to change for FAT32 compatibility

        frame = gtk.Frame(" %s " % _('Recorder Filename (excluding the file extension)'))
        set_tip(frame, _("The specifiers are $r for the number of the "
        "recorder with the rest being documented in the strftime man page.\n"
        "Users may wish to alter this to make filenames that are compatible with particular filesystems."))
        frame.set_border_width(3)
        align = gtk.Alignment()
        align.props.xscale = 1.0
        self.recorder_filename = DefaultEntry("idjc.[%Y-%m-%d][%H:%M:%S].$r")
        align.add(self.recorder_filename)
        self.recorder_filename.show()
        align.set_border_width(3)
        frame.add(align)
        align.show()
        outervbox.pack_start(frame, True)
        frame.show()

        # Miscellaneous Features
        
        frame = gtk.Frame(" " + _('Miscellaneous Features') + " ")
        frame.set_border_width(3)
        vbox = gtk.VBox()
        frame.add(vbox)
        frame.show()
        vbox.set_border_width(10)
        vbox.set_spacing(1)

        self.silence_killer = gtk.CheckButton(
                            _('Trim quiet song endings and trailing silence'))
        self.silence_killer.set_active(True)
        vbox.pack_start(self.silence_killer, False, False, 0)
        self.silence_killer.show()
        
        self.bonus_killer = gtk.CheckButton(
                            _('End tracks containing long passages of silence'))
        self.bonus_killer.set_active(True)
        vbox.pack_start(self.bonus_killer, False, False, 0)
        self.bonus_killer.show()
        
        self.speed_variance = gtk.CheckButton(
                            _('Enable the main-player speed/pitch controls'))
        vbox.pack_start(self.speed_variance, False, False, 0)
        self.speed_variance.connect("toggled", self.cb_pbspeed)
        self.speed_variance.show()
        set_tip(self.speed_variance, _('This option causes some extra widgets '
        'to appear below the playlists which allow the playback speed to be '
        'adjusted from 25% to 400% and a normal speed button.'))

        self.dual_volume = gtk.CheckButton(
                                _('Separate left/right player volume faders'))
        vbox.pack_start(self.dual_volume, False, False, 0)
        self.dual_volume.connect("toggled", self.cb_dual_volume)
        self.dual_volume.show()
        set_tip(self.dual_volume, _('Select this option to use an independent '
                        'volume fader for the left and right music players.'))

        self.bigger_box_toggle = gtk.CheckButton(
                            _('Enlarge the time elapsed/remaining windows'))
        vbox.pack_start(self.bigger_box_toggle, False, False, 0)
        self.bigger_box_toggle.connect("toggled", self.callback, "bigger box")
        self.bigger_box_toggle.show()
        set_tip(self.bigger_box_toggle, _("The time elapsed/remaining windows "
        "sometimes don't appear big enough for the text that appears in them "
        "due to unusual DPI settings or the use of a different rendering "
        "engine. This option serves to fix that."))
        
        self.djalarm = gtk.CheckButton(
                            _('Sound an alarm when the music is due to end'))
        vbox.pack_start(self.djalarm, False, False, 0)
        self.djalarm.show()
        set_tip(self.djalarm, _('An alarm tone alerting the DJ that dead-air is'
        ' just nine seconds away. This also works when monitoring stream audio '
        'but the alarm tone is not sent to the stream.\n\n'
        'JACK freewheel mode will also be automatically disengaged.'))
        
        freewheel_show = self.parent.freewheel_button.enabler
        vbox.pack_start(freewheel_show, False, False, 0)
        freewheel_show.show()
        
        self.dither = gtk.CheckButton(
                                    _('Apply dither to 16 bit PCM playback'))
        vbox.pack_start(self.dither, False, False, 0)
        self.dither.connect("toggled", self.cb_dither)
        self.dither.show()
        set_tip(self.dither, _('This feature maybe improves the sound quality '
                            'a little when listening on a 24 bit sound card.'))

        self.enable_tooltips = gtk.CheckButton(_('Enable tooltips'))
        self.enable_tooltips.connect("toggled", self.callback, "tooltips")
        vbox.pack_start(self.enable_tooltips, False, False, 0)
        self.enable_tooltips.show()
        set_tip(self.enable_tooltips, _('This, what you are currently reading,'
                        ' is a tooltip. This feature turns them on or off.'))
        
        vbox.show()

        outervbox.pack_start(frame, False)
       
        # Song database preferences and connect button.
        self.songdbprefs = self.parent.topleftpane.prefs_controls
        self.parent.menu.songdbmenu_a.connect_proxy(self.songdbprefs.dbtoggle)
        outervbox.pack_start(self.songdbprefs, False)
        
        # Widget for user interface label renaming.
        label_subst = self.parent.label_subst
        outervbox.pack_start(label_subst, False)
        label_subst.set_border_width(3)
        label_subst.show_all()
        
        # Session to be saved, or initial settings preferences.
        frame = gtk.Frame(" %s " % _('Player Settings At Startup'))
        frame.set_label_align(0.5, 0.5)
        frame.set_border_width(3)
        vbox = gtk.VBox()
        frame.add(vbox)
        vbox.show()
        
        restoresessionhbox = gtk.HBox()
        restoresessionhbox.set_border_width(8)
        restoresessionhbox.show()
        self.restore_session_option = gtk.CheckButton(
                                            _('Restore the previous session'))
        vbox.pack_start(restoresessionhbox, False, False, 0)
        restoresessionhbox.pack_start(self.restore_session_option, False)
        self.restore_session_option.show()
        set_tip(self.restore_session_option,
        _('When starting IDJC most of the main window settings will be as they '
        'were left. As an alternative you may specify below how you want the '
        'various settings to be when IDJC starts.'))
        
        hbox = gtk.HBox(True)
        vbox.add(hbox)
        hbox.set_border_width(6)
        hbox.set_spacing(3)
        
        self.lpconfig = InitialPlayerConfig(
                                        _("Player 1"), parent.player_left, "l")
        self.rpconfig = InitialPlayerConfig(
                                        _("Player 2"), parent.player_right, "r")
        for each in self.lpconfig, self.rpconfig:
            hbox.pack_start(each, True, True)
        
        hbox.show()
        
        self.misc_session_frame = gtk.Frame()
        self.misc_session_frame.set_border_width(4)
        misc_startup = gtk.HBox(True, 20)
        self.misc_session_frame.add(misc_startup)
        misc_startup.show()
        hbox2 = gtk.HBox()
        hbox2.pack_start(self.misc_session_frame, True, True, 7)
        hbox2.show()
        
        vbox.pack_start(hbox2, False, False, 2)
        self.misc_session_frame.show()
        misc_startupl = gtk.VBox()
        misc_startup.pack_start(misc_startupl, True, True, 5)
        misc_startupl.show()
        misc_startupr = gtk.VBox()
        misc_startup.pack_start(misc_startupr, True, True, 5)
        misc_startupr.show()
        
        self.tracks_played = gtk.CheckButton(_('Tracks Played'))
        misc_startupl.add(self.tracks_played)
        self.tracks_played.show()
        # TC: DJ hears the stream mix.
        self.stream_mon = gtk.CheckButton(_('Monitor Stream Mix'))
        misc_startupr.add(self.stream_mon)
        self.stream_mon.show()
        
        self.restore_session_option.connect("toggled", self.cb_restore_session)
        self.restore_session_option.set_active(True)
      
        outervbox.pack_start(frame, False)
        frame.show() 
                
        # TC: A heading label for miscellaneous settings.
        features_label = gtk.Label(_('General'))
        self.notebook.append_page(generalwindow, features_label)
        features_label.show()
        outervbox.show()

        # Channels tab

        scrolled_window = gtk.ScrolledWindow()
        scrolled_window.set_border_width(0)
        scrolled_window.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        panevbox = gtk.VBox()
        scrolled_window.add_with_viewport(panevbox)
        scrolled_window.show()
        panevbox.set_border_width(3)
        panevbox.set_spacing(3)
        panevbox.get_parent().set_shadow_type(gtk.SHADOW_NONE)
        panevbox.show()

        # Opener buttons for channels

        opener_settings = parent.mic_opener.opener_settings
        panevbox.pack_start(opener_settings, False, padding=3)

        # Individual channel settings

        self.mic_controls = mic_controls = []
        vbox = gtk.VBox()
        for i in range(PGlobs.num_micpairs):
            uhbox = gtk.HBox(True)
            vbox.pack_start(uhbox, False, False, 0)
            uhbox.show()
            lhbox = gtk.HBox()
            vbox.pack_start(lhbox, False, False, 0)
            lhbox.show()
            for j in range(2):
                n = i * 2 + j
                micname = "mic_control_%d" % n
                c = AGCControl(self.parent, str(n + 1), micname, n)
                setattr(self, micname, c)
                uhbox.add(c)
                c.show()
                parent.mic_opener.add_mic(c)
                mic_controls.append(c)
            mic_controls[-2].set_partner(mic_controls[-1])
            mic_controls[-1].set_partner(mic_controls[-2])  
        parent.mic_opener.finalise()

        panevbox.pack_start(vbox, False, False, 0)
        vbox.show()
                
        label = gtk.Label(_('Channels'))
        self.notebook.append_page(scrolled_window, label)
        label.show()

        # Controls tab
        tab= midicontrols.ControlsUI(self.parent.controls)
        # TC: Keyboard and MIDI bindings configuration.
        label= gtk.Label(_('Bindings'))
        self.notebook.append_page(tab, label)
        tab.show()
        label.show()

        # about tab
        
        self.aboutframe = gtk.Frame()
        frame.set_border_width(9)
        vbox = gtk.VBox()
        self.aboutframe.add(vbox)
        label = gtk.Label()
        label.set_markup('<span font_desc="sans italic 20">' + 
                                                self.parent.appname + '</span>')
        vbox.pack_start(label, False, False, 13)
        label.show()
        label = gtk.Label()
        label.set_markup('<span font_desc="sans 13">Version ' +
                                                self.parent.version + '</span>')
        vbox.pack_start(label, False, False, 0)
        label.show()
        
        pixbuf = gtk.gdk.pixbuf_new_from_file(FGlobs.pkgdatadir / "logo.png")
        image = gtk.Image()
        image.set_from_pixbuf(pixbuf)
        vbox.pack_start(image, False, False, 8)
        image.show()
        
        label = gtk.Label()
        label.set_markup(u'<span font_desc="sans 13">' +
                                            self.parent.copyright + u'</span>')
        vbox.pack_start(label, False, False, 12)
        label.show()
        
        label = gtk.Label()
        label.set_markup(
        '<span font_desc="sans 10">' +
         _('Released under the GNU General Public License V2.0') + '</span>')
        vbox.pack_start(label, False, False, 1)
        label.show()
        
        nb = gtk.Notebook()
        nb.set_border_width(10)
        vbox.pack_start(nb, True, True, 0)
        nb.show()
        
        lw = licence_window.LicenceWindow()
        lw.set_border_width(1)
        lw.set_shadow_type(gtk.SHADOW_ETCHED_IN)
        label = gtk.Label(_('Licence'))
        nb.append_page(lw, label)
        lw.show()
        label.show()
        
        def contribs_page(title, content):
            sw = gtk.ScrolledWindow()
            sw.set_border_width(1)
            sw.set_shadow_type(gtk.SHADOW_NONE)
            sw.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
            label = gtk.Label(title)
            nb.append_page(sw, label)
            sw.show()
            lw.show()
            ivbox = gtk.VBox()
            sw.add_with_viewport(ivbox)
            ivbox.show()
            for each in content:
                label = gtk.Label(each)
                label.set_use_markup(True)
                ivbox.add(label)
                label.show()
        
        contribs_page(_('Contributors'),
            ("Stephen Fairchild (s-fairchild@users.sourceforge.net)",
            "And Clover (and@doxdesk.com)",
            "Dario Abatianni (eisfuchs@users.sourceforge.net)",
            "Stefan Fendt (stefan@sfendt.de)",
            "Brian Millham (bmillham@users.sourceforge.net)"))

        contribs_page(_('Translators'),
            ("<b>it</b>  Raffaele Morelli (raffaele.morelli@gmail.com)",))

        vbox.show()

        aboutlabel = gtk.Label(_('About'))
        self.notebook.append_page(self.aboutframe, aboutlabel)
        aboutlabel.show()
        self.aboutframe.show()
        
        self.notebook.show()

        # These on by default
        self.djalarm.set_active(True)
        self.dither.set_active(True)
        self.fast_resample.set_active(True)
        self.enable_tooltips.set_active(True)

        # Default mic/aux configuration
        mic_controls[0].mode.set_active(2)
        mic_controls[0].alt_name.set_text("DJ")
        t = parent.mic_opener.ix2button[1].opener_tab
        t.button_text.set_text("DJ")
        t.icb.set_filename(FGlobs.pkgdatadir / "mic4.png")
        t.headroom.set_value(3)
        t.has_reminder_flash.set_active(True)
        t.is_microphone.set_active(True)
        t.freewheel_cancel.set_active(True)
        for cb, state in zip(t.open_triggers.itervalues(), (1, 1, 0, 1)):
            cb.set_active(state)
        if len(mic_controls) >= 4:
            mic_controls[2].mode.set_active(1)
            mic_controls[2].alt_name.set_text("Aux L")
            mic_controls[2].groups_adj.set_value(2)
            mic_controls[2].pan_active.set_active(True)
            mic_controls[2].pan.set_value(0)
            mic_controls[3].mode.set_active(3)
            mic_controls[3].alt_name.set_text("Aux R")
            mic_controls[3].pan_active.set_active(True)
            mic_controls[3].pan.set_value(100)
            t = parent.mic_opener.ix2button[2].opener_tab
            t.button_text.set_text("Aux")
            t.icb.set_filename(FGlobs.pkgdatadir / "jack2.png")
            t.open_triggers.values()[2].set_active(True)

        self.parent.menu.strmetersmenu_a.connect_proxy(self.show_stream_meters)
        self.parent.menu.chmetersmenu_a.connect_proxy(self.show_microphones)
        self.parent.menu.backgroundtracksmenu_a.connect_proxy(self.show_background_tracks_player)
        self.parent.menu.buttonbarmenu_a.connect_proxy(self.show_button_bar)

        self.show_stream_meters.set_active(True)
        self.show_microphones.set_active(True)
        self.show_button_bar.set_active(True)

        self.activedict = {  # Widgets to save that have the get_active method.
            "startmini"   : self.startmini,
            "dsp_toggle"  : self.parent.dsp_button,
            "djalarm"     : self.djalarm,
            "trxpld"      : self.tracks_played,
            "strmon"      : self.stream_mon,
            "bigdigibox"  : self.bigger_box_toggle, 
            "dither"      : self.dither,
            "recallsession" : self.restore_session_option,
            "best_rs"       : self.best_quality_resample,
            "good_rs"       : self.good_quality_resample,
            "fast_rs"       : self.fast_resample,
            "speed_var"     : self.speed_variance,
            "dual_volume"   : self.dual_volume,
            "showtips"      : self.enable_tooltips,
            "silencekiller" : self.silence_killer,
            "bonuskiller"   : self.bonus_killer,
            "rg_indicate"   : self.rg_indicate,
            "rg_adjust"     : self.rg_adjust,
            "str_meters"    : self.show_stream_meters,
            "mic_meters"    : self.show_microphones,
            "mic_meters_no_void" : self.no_mic_void_space,
            "players_visible"    : self.parent.menu.playersmenu_i
            }
            
        for each in itertools.chain(mic_controls, 
                            (self.parent.freewheel_button, self.songdbprefs,
                            self.lpconfig, self.rpconfig, opener_settings,
                            label_subst)):
            self.activedict.update(each.activedict)

        self.valuesdict = {  # These widgets all have the get_value method.
            "effects1_vol"    : self.parent.jingles.jvol_adj[0],
            "effects1_muting" : self.parent.jingles.jmute_adj[0],
            "effects2_vol"    : self.parent.jingles.jvol_adj[1],
            "effects2_muting" : self.parent.jingles.jmute_adj[1],
            "voiplevel"     : self.parent.voipgainadj,
            "voipmixback"   : self.parent.mixbackadj,
            "interlude_vol" : self.parent.jingles.ivol_adj,
            "passspeed"     : self.parent.passspeed_adj,
            "djvolume"      : self.dj_aud_adj,
            "alarmvolume"   : self.alarm_aud_adj,
            "rg_default"    : self.rg_defaultgain,
            "rg_boost"      : self.rg_boost,
            "r128_boost"    : self.r128_boost,
            "all_boost"    : self.all_boost
            }

        for each in itertools.chain(mic_controls, (opener_settings,
                                                            self.songdbprefs)):
            self.valuesdict.update(each.valuesdict)

        self.textdict = {  # These widgets all have the get_text method.
            "ltfilerqdir"   : self.parent.player_left.file_requester_start_dir,
            "rtfilerqdir"   : self.parent.player_right.file_requester_start_dir,
            "main_full_wst" : self.parent.full_wst,
            "main_min_wst"  : self.parent.min_wst,
            "prefs_wst"     : self.wst,
            "rec_filename"  : self.recorder_filename
            }

        for each in itertools.chain(mic_controls, (opener_settings,
                                            label_subst, self.songdbprefs)):
            self.textdict.update(each.textdict)

        self.rangewidgets = (self.parent.deckadj,)
