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

import gtk

from idjc import FGlobs, PGlobs
from . import licence_window
from . import p3db
from . import midicontrols
from .freefunctions import int_object
from .gtkstuff import WindowSizeTracker
from .prelims import ProfileManager
from .utils import PathStr
from .tooltips import main_tips
from .tooltips import main_tips


t = gettext.translation(FGlobs.package_name, FGlobs.localedir, fallback=True)
_ = t.gettext
def N_(text):
   return text


pm = ProfileManager()
set_tip = main_tips.set_tip


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
      try:
         self.pl_mode = gtk.ComboBoxText(player.pl_mode.get_model())
         self.fade = gtk.ComboBoxText(player.fade.get_model())
      except AttributeError:
         self.pl_mode = gtk.combo_box_new_text()
         self.pl_mode.set_model(player.pl_mode.get_model())
         self.fade = gtk.combo_box_new_text()
         self.fade.set_model(player.pl_delay.get_model())
         
      for each in (self.pl_mode, self.fade):
         each.set_active(0)

      self.elapsed = gtk.RadioButton(None, _("Track time elapsed"))
      self.remaining = gtk.RadioButton(self.elapsed, _("Track time remaining"))
      s1 = gtk.HSeparator()
      self.to_stream = gtk.CheckButton(_("Audio to stream"))
      self.to_dj = gtk.CheckButton(_("Audio to DJ"))
      
      for each in (self.to_stream, self.to_dj):
         each.set_active(True)

      for each in (pl_label, self.pl_mode, fade_label, self.fade, self.elapsed, self.remaining, s1, self.to_stream, self.to_dj):
         vbox.pack_start(each, False)
      self.show_all()
      
      self.active_dict = {
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
   can_mark = all(hasattr(gtk.Scale, x) for x in ('add_mark', 'clear_marks'))

   mic_modes = (
      # TC: Microphone mode combobox text.
      N_('Deactivated'),
      # TC: Microphone mode combobox text.
      N_('Line input'),
      # TC: Microphone mode combobox text.
      N_('Mic input (processed)'), 
      # TC: Microphone mode combobox text.
      N_('Partnered with channel %s'))

   
   def sendnewstats(self, widget, wname):
      if wname != NotImplemented:
         if isinstance(widget, (gtk.SpinButton, gtk.Scale)):
            value = widget.get_value()
         if isinstance(widget, (gtk.CheckButton, gtk.ComboBox)):
            value = int(widget.get_active())
         stringtosend = "INDX=%d\nAGCP=%s=%s\nACTN=%s\nend\n" % (self.index, wname, str(value), "mic_control")
         self.approot.mixer_write(stringtosend, True)

   def set_partner(self, partner):
      self.partner = partner
      self.mode.set_cell_data_func(self.mode_cell, self.mode_cell_data_func, partner.mode)

   def mode_cell_data_func(self, celllayout, cell, model, iter, opposite):
      index = model.get_path(iter)[0]
      oindex = opposite.get_active()
      cell.props.sensitive = not (((index == 0 or index == 3) and oindex == 3) or (index == 3 and oindex == 0))
      trans = t.gettext(model.get_value(iter, 0))
      if index == 3:
         cell.props.text = trans % self.partner.ui_name
      else:
         cell.props.text = trans

   def numline(self, label_text, wname, initial=0, mini=0, maxi=0, step=0, digits=0, adj=None):
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
      self.booleandict[self.commandname + "_" + wname] = cb
      return ivbox
   
   def check(self, label_text, wname, save=True):
      cb = gtk.CheckButton(label_text)
      cb.connect("toggled", self.sendnewstats, wname)
      cb.emit("toggled")
      cb.show()
      if save:
         self.booleandict[self.commandname + "_" + wname] = cb
      return cb
      
   def cb_open(self, widget):
      active = widget.get_active()
      self.meter.set_led(active)
      self.status_led.set_from_pixbuf(self.status_on_pb if active else self.status_off_pb)

   def cb_pan_middle(self, button):
      self.pan.set_value(50)

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
         
   def __init__(self, approot, ui_name, commandname, index):
      self.approot = approot
      self.ui_name = ui_name
      self.meter = approot.mic_meters[int(ui_name) - 1]
      self.commandname = commandname
      self.index = index
      self.valuesdict = {}
      self.booleandict = {}
      self.textdict = {}
      gtk.Frame.__init__(self)
      hbox = gtk.HBox()
      hbox.set_spacing(3)

      label = gtk.Label('<span weight="600">' + ui_name + "</span>")
      label.set_use_markup(True)
      hbox.pack_start(label, False)
      label.show()
 
      self.alt_name = gtk.Entry()
      set_tip(self.alt_name, _('Alternate opener button text goes here e.g. DJ, Guest. When not specified the microphone number is shown instead.'))
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
      
      self.vbox.pack_start(self.mode, False, False)
      
      for each in self.mic_modes:
         mode_liststore.append((each, ))
      self.mode.connect("changed", self.sendnewstats, "mode")
      self.mode.connect("changed", self.cb_mode)
      self.booleandict[self.commandname + "_mode"] = self.mode
      self.mode.show()
      set_tip(self.mode, _('The signal processing mode.'))

      hbox = gtk.HBox()
      # TC: Indicator of the microphones open or unmuted status. Has alongside an LED indicator.
      label = gtk.Label(_('Open/Unmute'))
      hbox.pack_start(label, False, False, 3)
      label.show()
      self.status_led = gtk.Image()
      hbox.pack_start(self.status_led, False, False, 3)
      self.status_led.show()
      ivbox = self.widget_frame(hbox, self.vbox, _('This controls the allocation of front panel open/unmute buttons. Having one button control multiple microphones can save time.'), (1, 2))
      hbox.show()
      self.status_off_pb = gtk.gdk.pixbuf_new_from_file_at_size(FGlobs.pkgdatadir / "led_unlit_clear_border_64x64.png", 12, 12)
      self.status_on_pb = gtk.gdk.pixbuf_new_from_file_at_size(FGlobs.pkgdatadir / "led_lit_green_black_border_64x64.png", 12, 12)
      self.status_led.set_from_pixbuf(self.status_off_pb)
            
      hbox = gtk.HBox()
      # TC: Mic opener buttons can be grouped together. This checkbutton sits alongside a button group numerical selector.
      self.group = gtk.CheckButton(_('Button group'))
      self.booleandict[self.commandname + "_group"] = self.group
      hbox.pack_start(self.group, False, False, 0)
      self.group.show()
      ivbox.pack_start(hbox, False, False)
      hbox.show()
      
      self.groups_adj = gtk.Adjustment(1.0, 1.0, PGlobs.num_micpairs, 1.0)
      self.valuesdict[self.commandname + "_groupnum"] = self.groups_adj
      groups_spin = gtk.SpinButton(self.groups_adj, 0.0, 0)
      hbox.pack_end(groups_spin, False)
      groups_spin.show()

      # TC: Checkbutton that selects this microphone to open automatically in certain circumstances.
      self.autoopen = gtk.CheckButton(_('Automatic Open'))
      ivbox.pack_start(self.autoopen, False, False)
      self.autoopen.show()
      set_tip(self.autoopen, _('This mic is to be opened automatically when a Player Stop or Announcement playlist control is encountered in the active player. This mic is also to be opened by the playlist advance button.'))
      self.booleandict[self.commandname + "_autoopen"] = self.autoopen

      sizegroup = gtk.SizeGroup(gtk.SIZE_GROUP_HORIZONTAL)
      panframe = gtk.Frame()
      panframe.modes = (1, 2, 3)
      set_tip(panframe, _('Stereo panning is the selection of where an audio source sits from left to right within the stereo mix.\n\nThis control maintains constant audio power throughout its range of travel, giving -3dB attenuation in both audio channels at the half way point.\n\nIf you require 0dB straight down the middle then this feature should be turned off.'))
      
      hbox = gtk.HBox()
      self.pan_active = gtk.CheckButton(_('Stereo Panning'))
      self.booleandict[self.commandname + "_pan_active"] = self.pan_active
      hbox.pack_start(self.pan_active, False, False, 0)
      self.pan_active.show()
      self.pan_active.connect("toggled", self.sendnewstats, "pan_active")
      panframe.set_label_widget(hbox)
      hbox.show()
      
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
      self.valuesdict[self.commandname + "_pan"] = self.pan
      panhbox.pack_start(self.pan)
      r = gtk.Label(_('R'))
      sizegroup.add_widget(r)
      panhbox.pack_start(r, False, False)
      pancenterbox = gtk.HBox()
      pancenter = gtk.Button()
      pancenter.connect("clicked", self.cb_pan_middle)
      if self.can_mark:
         self.pan.add_mark(50.0, gtk.POS_BOTTOM, None)
         self.pan.add_mark(25.0, gtk.POS_BOTTOM, None)
         self.pan.add_mark(75.0, gtk.POS_BOTTOM, None)
      else:
         pancenterbox.pack_start(pancenter, True, False)
      panvbox.pack_start(pancenterbox, False, False)
      self.vbox.pack_start(panframe, False, False)
      panframe.show_all()

      # TC: A set of controls that the user canl use to match partnered microphone audio with the master.
      pairedframe = gtk.Frame(" %s " % _('Signal Matching'))
      set_tip(pairedframe, _('These controls are provided to obtain a decent match between the two microphones.'))
      pairedframe.modes = (3, )
      self.vbox.pack_start(pairedframe, False)
      pairedvbox = gtk.VBox()
      pairedvbox.set_border_width(3)
      pairedframe.add(pairedvbox)
      pairedvbox.show()
      pairedmicgainadj = gtk.Adjustment(0.0, -20.0, +20.0, 0.1, 2)
      pairedmicgain = self.numline(_('Relative Gain (dB)'), "pairedgain", digits=1, adj=pairedmicgainadj)
      pairedvbox.pack_start(pairedmicgain, False)
      pairedmicgain.show()
      # TC: Mic audio phase inversion control.
      pairedinvert = self.check(_('Invert Signal'), "pairedinvert")
      pairedvbox.pack_start(pairedinvert, False)
      pairedinvert.show()

      micgainadj = gtk.Adjustment(5.0, -20.0, +30.0, 0.1, 2)
      openaction = gtk.ToggleAction("open", _('Open/Unmute'), _('Allow microphone audio into the mix.'), None)
      invertaction = gtk.ToggleAction("invert", _('Invert Signal'), _('Useful for when microphones are cancelling one another out, producing a hollow sound.'), None)
      # TC: Control whether to mix microphone audio to the DJ mix.
      indjmixaction = gtk.ToggleAction("indjmix", _("In The DJ's Mix"), _('Make the microphone audio audible in the DJ mix. This may not always be desirable.'), None)

      self.simple_box = gtk.VBox()
      self.simple_box.set_spacing(2)
      self.vbox.pack_start(self.simple_box, False, False)
      self.simple_box.modes = (1, )

      ivbox = self.frame(" " + _('Basic Controls') + " ", self.simple_box)
      micgain = self.numline(_('Boost/Cut (dB)'), "gain", digits=1, adj=micgainadj)
      ivbox.pack_start(micgain, False, False)
      
      self.open = self.check("", "open", save=False)
      openaction.connect_proxy(self.open)
      self.open.connect("toggled", self.cb_open)
      
      invert_simple = self.check("", "invert")
      invertaction.connect_proxy(invert_simple)
      ivbox.pack_start(invert_simple, False, False)
      set_tip(invert_simple, _('Useful for when microphones are cancelling one another out, producing a hollow sound.'))
      
      indjmix = self.check("", "indjmix")
      indjmixaction.connect_proxy(indjmix)
      ivbox.pack_start(indjmix, False, False)
      set_tip(indjmix, _('Make the microphone audio audible in the DJ mix. This may not always be desirable.'))

      self.processed_box = gtk.VBox()
      self.processed_box.modes = (2, )
      self.processed_box.set_spacing(2)
      self.vbox.pack_start(self.processed_box, False, False)

      ivbox = self.frame(" " + _('High Pass Filter') + " ", self.processed_box)
      hpcutoff = self.numline(_('Cutoff Frequency'), "hpcutoff", 100.0, 30.0, 120.0, 1.0, 1)
      ivbox.pack_start(hpcutoff, False, False, 0)
      # TC: User can set the number of filter stages.
      hpstages = self.numline(_('Stages'), "hpstages", 4.0, 1.0, 4.0, 1.0, 0)
      ivbox.pack_start(hpstages, False, False, 0)
      set_tip(ivbox, _('Frequency in Hertz above which audio can pass to later stages. Use this feature to restrict low frequency sounds such as mains hum. Setting too high a level will make your voice sound thin.'))
      
      # TC: this is the treble control. HF = high frequency.
      ivbox = self.frame(" " + _('HF Detail') + " ", self.processed_box)
      hfmulti = self.numline(_('Effect'), "hfmulti", 0.0, 0.0, 9.0, 0.1, 1)
      ivbox.pack_start(hfmulti, False, False, 0)
      hfcutoff = self.numline(_('Cutoff Frequency'), "hfcutoff", 2000.0, 900.0, 4000.0, 10.0, 0)
      ivbox.pack_start(hfcutoff, False, False, 0)
      set_tip(ivbox, _('You can use this to boost the amount of treble in the audio.'))
       
      # TC: this is the bass control. LF = low frequency.
      ivbox = self.frame(" " + _('LF Detail') + " ", self.processed_box)
      lfmulti = self.numline(_('Effect'), "lfmulti", 0.0, 0.0, 9.0, 0.1, 1)
      ivbox.pack_start(lfmulti, False, False, 0)
      lfcutoff = self.numline(_('Cutoff Frequency'), "lfcutoff", 150.0, 50.0, 400.0, 1.0, 0)
      ivbox.pack_start(lfcutoff, False, False, 0)
      set_tip(ivbox, _('You can use this to boost the amount of bass in the audio.'))
      
      # TC: dynamic range compressor.
      ivbox = self.frame(" " + _('Compressor') + " ", self.processed_box)
      micgain = self.numline(_('Boost/Cut (dB)'), "gain", digits=1, adj=micgainadj)
      ivbox.pack_start(micgain, False, False, 0)
      # TC: this is the peak signal limit.
      limit = self.numline(_('Limit'), "limit", -3.0, -9.0, 0.0, 0.5, 1)
      ivbox.pack_start(limit, False, False, 0)
      set_tip(ivbox, _('A lookahead brick wall limiter. Use the Ratio control to boost the quieter sounds. The Limit control is used to set the absolute maximum audio level.'))
      
      ivbox = self.frame(" " + _('Noise Gate') + " ", self.processed_box)
      # TC: noise gate triggers at this level.
      ng_thresh = self.numline(_('Threshold'), "ngthresh", -30.0, -62.0, -20.0, 1.0, 0)
      ivbox.pack_start(ng_thresh, False, False, 0)
      # TC: negative gain when the noise gate is active.
      ng_gain = self.numline(_('Gain'), "nggain", -6.0, -12.0, 0.0, 1.0, 0)
      ivbox.pack_start(ng_gain, False, False, 0)
      set_tip(ivbox, _("Reduce the unwanted quietest sounds and background noise which you don't want your listeners to hear with this."))
      
      ivbox = self.frame(" " + _('De-esser') + " ", self.processed_box)
      # TC: the de-esser uses two filters to determine ess or not ess. Bias sets the balance between the two.
      ds_bias = self.numline(_('Bias'), "deessbias", 0.35, 0.1, 10.0, 0.05, 2)
      ivbox.pack_start(ds_bias, False, False, 0)
      # TC: the de-esser negative gain when the de-esser is active.
      ds_gain = self.numline(_('Gain'), "deessgain", -4.5, -10.0, 0.0, 0.5, 1)
      ivbox.pack_start(ds_gain, False, False, 0)
      set_tip(ivbox, _('Reduce the S, T, and P sounds which microphones tend to exagerate. Ideally the Bias control will be set so that the de-esser is off when there is silence but is set high enough that mouse clicks are detected and suppressed.'))
      
      ivbox = self.toggle_frame(_('Ducker'), "duckenable", self.processed_box)
      duckrelease = self.numline(_('Release'), "duckrelease", 400.0, 100.0, 999.0, 10.0, 0)
      ivbox.pack_start(duckrelease, False, False, 0)
      duckhold = self.numline(_('Hold'), "duckhold", 350.0, 0.0, 999.0, 10.0, 0)
      ivbox.pack_start(duckhold, False, False, 0)
      set_tip(ivbox, _('The ducker automatically reduces the level of player audio when the DJ speaks. These settings allow you to adjust the timings of that audio reduction.'))
       
      ivbox = self.frame(" " + _('Other options') + " ", self.processed_box)

      open_complex = self.check("", NotImplemented, save=False)
      openaction.connect_proxy(open_complex)
      #ivbox.pack_start(open_complex, False, False)
      #set_tip(open_complex, _('Allow microphone audio into the mix.'))
      invert_complex = self.check("", NotImplemented, save=False)
      invertaction.connect_proxy(invert_complex)
      ivbox.pack_start(invert_complex, False, False)
      set_tip(invert_complex, _('Useful for when microphones are cancelling one another out, producing a hollow sound.'))
      phaserotate = self.check(_('Phase Rotator'), "phaserotate")
      ivbox.pack_start(phaserotate, False, False, 0)
      set_tip(phaserotate, _('This feature processes the microphone audio so that it sounds more even. The effect is particularly noticable on male voices.'))
      indjmix = self.check("", NotImplemented, save=False)
      indjmixaction.connect_proxy(indjmix)
      ivbox.pack_start(indjmix, False, False)
      set_tip(indjmix, _('Make the microphone audio audible in the DJ mix. This may not always be desirable.'))

      self.mode.set_active(0)
      indjmix.set_active(True)
      self.partner = None



def make_entry_line(parent, item, code, hastoggle, index=None):
   box = gtk.HBox(False, 0)
   box.set_border_width(4)
   box.set_spacing(5)

   entry = gtk.Entry(128)
   entry.set_size_request(185, -1)

   # TC: save the current setting for the next time this session profile is run.
   savebutton = gtk.Button(_('Save'))
   savebutton.connect("clicked", parent.save_click, (code, entry, index))
   box.pack_end(savebutton, False, False, 0)
   savebutton.show()

   # TC: use a user specified setting.
   setbutton = gtk.Button(_('Set'))
   setbutton.connect("clicked", parent.update_click, (code, entry, index))
   box.pack_end(setbutton, False, False, 0)
   setbutton.show()

   if hastoggle:
      entry.set_sensitive(False)
   box.pack_end(entry, False, False, 0)
   entry.show()

   # TC: use the auto detected default setting.
   checkbox = gtk.CheckButton(_('Auto'))
   box.pack_end(checkbox, False, False, 0)
   if hastoggle:
      checkbox.set_active(True)
      checkbox.connect("toggled", parent.auto_click, entry)
      checkbox.show()
      
   label = gtk.Label(item)
   box.pack_start(label, False, False, 0)
   label.show()
      
   box.show()
   
   set_tip(checkbox, _('Use default JACK audio routing'))
   set_tip(setbutton, _('Reroute the audio to/from the specified port'))
   set_tip(savebutton, _('Save the audio routing so that it persists across application restarts'))
   set_tip(entry, _("Enter the name of the JACK audio port with which to bind and then click the set button to the right.\nTyping 'jack_lsp -p' in a console will give you a list of valid JACK audio ports. Note that inputs will only bind to output ports and outputs will only bind to input ports."))
   
   return box, checkbox, entry, setbutton



class mixprefs:
   class event_command_container(gtk.Frame):
      def add(self, widget):
         self.vbox.add(widget)
      def __init__(self):
         gtk.Frame.__init__(self)
         gtk.Frame.set_border_width(self, 4)
         gtk.Frame.set_shadow_type(self, gtk.SHADOW_ETCHED_OUT)
         self.vbox = gtk.VBox()
         self.vbox.set_spacing(2)
         gtk.Frame.add(self, self.vbox)
         self.vbox.set_border_width(4)
         self.vbox.show()
   
   class event_command(gtk.HBox):
      def activate(self):
         if self.checkbutton.get_active():
            os.system(self.entry.get_text())
      def get_text(self):
         return self.entry.get_text()
      def get_active(self):
         return self.checkbutton.get_active()
      def set_text(self, text):
         return self.entry.set_text(text)
      def set_active(self, bool):
         return self.checkbutton.set_active(bool)
      def cb_checkbutton(self, widget, data = None):
         self.entry.set_sensitive(widget.get_active())
      def __init__(self, imagefile, width, height, text, default_state, crossout, checkbutton_tip = None, entry_tip = None):
         gtk.HBox.__init__(self)
         gtk.HBox.set_spacing(self, 6)
         self.checkbutton = gtk.CheckButton()
         self.checkbutton.set_active(default_state)
         image = gtk.Image()
         if crossout:
            pixbuf = gtk.gdk.pixbuf_new_from_file_at_size(FGlobs.pkgdatadir / "crossout.png", width , height)
         else:
            pixbuf = gtk.gdk.pixbuf_new_from_file_at_size(FGlobs.pkgdatadir / (imagefile + ".png"), width, height)
         image.set_from_pixbuf(pixbuf)
         self.checkbutton.add(image)
         image.show()
         gtk.HBox.pack_start(self, self.checkbutton, False, False, 0)
         self.checkbutton.connect("toggled", self.cb_checkbutton)
         self.checkbutton.show()
         self.entry = gtk.Entry()
         self.entry.set_text(text)
         gtk.HBox.pack_start(self, self.entry, True, True, 0)
         self.entry.set_sensitive(default_state)
         self.entry.show()

         if checkbutton_tip is not None:
            set_tip(self.checkbutton, checkbutton_tip)
         if entry_tip is not None:
            set_tip(self.entry, entry_tip)

   
   def send_new_normalizer_stats(self):
      r = float(self.parent.samplerate)
      string_to_send = ":%0.1f:%0.1f:%d:%d:%d:" % (
                                        self.normboost_adj.get_value(),
                                        self.normceiling_adj.get_value(),
                                        self.normrise_adj.get_value() * r,
                                        self.normfall_adj.get_value() * r, 
                                        self.normalize.get_active())
      self.parent.mixer_write("NORM=%s\nACTN=normalizerstats\nend\n" % string_to_send, True)
      
   def send_new_resampler_stats(self):
      self.parent.mixer_write("RSQT=%d\nACTN=resamplequality\nend\n" % self.resample_quality, True)
      
   def normalizer_defaults(self, value = None):
      self.normboost_adj.set_value(12.0)
      self.normboost_adj.value_changed()
      self.normceiling_adj.set_value(-12.0)
      self.normceiling_adj.value_changed()
      self.normrise_adj.set_value(2.7)
      self.normrise_adj.value_changed()
      self.normfall_adj.set_value(2.0)
      self.normfall_adj.value_changed()

   def cb_normalizer(self, widget, data = None):
      self.normalizer_hbox.set_sensitive(self.normalize.get_active())
      self.send_new_normalizer_stats()
      
   def cb_resample_quality(self, widget, data):
      if widget.get_active():
         self.resample_quality = data
         self.send_new_resampler_stats()
      
   def cb_dither(self, widget, data = None):
      if widget.get_active():
         string_to_send = "ACTN=dither\nend\n"
      else:
         string_to_send = "ACTN=dontdither\nend\n"
      self.parent.mixer_write(string_to_send, True)

   def cb_dj_aud(self, widget):
      self.parent.send_new_mixer_stats()
      
   def cb_use_dsp(self, widget):
      self.parent.send_new_mixer_stats()
      
   def cb_restore_session(self, widget, data=None):
      state = not widget.get_active()
      for each in (self.lpconfig, self.rpconfig, self.misc_session_frame):
         each.set_sensitive(state)
   
   jack_ports= ("audl", "audr", "strl", "strr", "auxl", "auxr", "midi", "dol", "dor", "dil", "dir")

   def load_jack_port_settings(self):
      for port in self.jack_ports:
         try:
            with open(pm.basedir / port) as f:
               getattr(self, port+"entry").set_text(f.readline()[:-1])
               getattr(self, port+"check").set_active(f.readline() == "1\n")
         except:
            pass
            
      for i, mic in enumerate(self.mic_jack_data):
         try:
            with open(pm.basedir / ("mic" + str(i + 1))) as f:
               mic[1].set_text(f.readline()[:-1])
               mic[0].set_active(f.readline() == "1\n")
         except:
            pass
   
   def auto_click(self, widget, data):
      data.set_sensitive(not widget.get_active())
   
   def save_click(self, widget, data):
      filename = data[0].lower()
      if data[2] is not None:
         filename += str(data[2] + 1)
      try:
         with open(pm.basedir / filename, "w") as f:
            if data[1].flags() & gtk.SENSITIVE:
               f.write(data[1].get_text() + "\n" + "0\n")
            else:
               f.write(data[1].get_text() + "\n" + "1\n")
      except:
         pass
   
   def update_click(self, widget, (code, entry, index)):
      if entry.flags() & gtk.SENSITIVE:
         entrytext = entry.get_text()
      else:
         entrytext = "default"
      if index is None:
         buffer = "ACTN=remake%s\n%s=%s\nend\n" % (code.lower(), code, entrytext)
      else:
         buffer = "ACTN=remake%s\n%s=%s\nINDX=%d\nend\n" % (code.lower(), code, entrytext, index)
      self.parent.mixer_write(buffer, True)
      
   def delete_event(self, widget, event, data=None):
      self.window.hide()
      return True

   def save_player_prefs(self):
      try:
         with open(pm.basedir / "playerdefaults", "w") as f:
            for name, widget in self.playersettingsdict.iteritems():
               f.write(name + "=" + str(int(widget.get_active())) + "\n")
            for name, widget in self.valuesdict.iteritems():
               f.write(name + "=" + str(widget.get_value()) + "\n")
            for name, widget in self.textdict.iteritems():
               f.write(name + "=" + widget.get_text() + "\n")
      except IOError:
         print "Error while writing out player defaults"
      try:
         with open(pm.basedir / "config", "w") as f:
            f.write("[resource_count]\n")
            for name, widget in self.rrvaluesdict.iteritems():
               f.write(name + "=" + str(int(widget.get_value())) + "\n")
      except IOError:
         print "Error while writing out player defaults"
         
   def load_player_prefs(self):
      proktogglevalue = False
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
            if self.playersettingsdict.has_key(key):
               if value == "True":
                  value = True
               elif value == "False":
                  value = False
               else:
                  value = int(value)
               if key == "proktoggle":
                  proktogglevalue = value
               else:
                  self.playersettingsdict[key].set_active(value)
            elif self.valuesdict.has_key(key):
               self.valuesdict[key].set_value(float(value))
            elif self.textdict.has_key(key):
               self.textdict[key].set_text(value)
         file.close()
      except IOError:
         print "Failed to read playerdefaults file"
      if proktogglevalue:
         self.playersettingsdict["proktoggle"].set_active(True)
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
         if parent.menu_feature_set.get_active():
            parent.menu_feature_set.set_active(False)
      if data == "fully featured":
         if parent.menu_feature_set.get_active() == False:
            parent.menu_feature_set.set_active(True)
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
            main_tips.enable()
         else:
            main_tips.disable()
            
   def meter_callback(self, widget, data):
      if data[0] == "meter":
         if widget.get_active():
            data[1].show()
         else:
            data[1].hide()
      if self.mic_peak_toggle.get_active() or self.stream_peak_toggle.get_active() or self.vu_toggle.get_active() or self.limiter_toggle.get_active() or self.stream_status_toggle.get_active():
         if self.parent.simplemixer == False:
            self.parent.meterbox.show()
      else:
         self.parent.meterbox.hide()
    
   def cb_mic_boost(self, widget):
      self.parent.send_new_mixer_stats()
                    
   def cb_pbspeed(self, widget):
      if widget.get_active():
         self.parent.player_left.pbspeedbar.set_value(0)
         self.parent.player_right.pbspeedbar.set_value(0)
         self.parent.player_left.pbspeedbox.show()
         self.parent.player_right.pbspeedbox.show()
      else:
         self.parent.player_left.pbspeedbox.hide()
         self.parent.player_right.pbspeedbox.hide()
      self.parent.send_new_mixer_stats()

   def cb_dual_volume(self, widget):
      if widget.get_active():
         self.parent.deck2adj.set_value(self.parent.deckadj.get_value())
         self.parent.deck2vol.show()
         set_tip(self.parent.deckvol, _('The volume control for the left music player.'))
      else:
         if self.parent.player_left.is_playing ^ self.parent.player_right.is_playing:
            if self.parent.player_left.is_playing:
               self.parent.deck2adj.set_value(self.parent.deckadj.get_value())
            else:
               self.parent.deckadj.set_value(self.parent.deck2adj.get_value())
         else:
            halfdelta = (self.parent.deck2adj.get_value() - self.parent.deckadj.get_value()) / 2
            self.parent.deck2adj.props.value -= halfdelta
            self.parent.deckadj.props.value += halfdelta
         
         self.parent.deck2vol.hide()
         set_tip(self.parent.deckvol, _('The volume control shared by both music players.'))

   def cb_twodblimit(self, widget):
      if widget.get_active():
         level = -2.0
      else:
         level = None
      self.parent.str_l_peak.set_line(level)
      self.parent.str_r_peak.set_line(level)
      self.parent.str_l_rms_vu.set_line(level)
      self.parent.str_r_rms_vu.set_line(level)
      self.parent.send_new_mixer_stats()
      
   def bind_jack_ports(self):
      for port in self.jack_ports:
         getattr(self, port+"update").clicked()
      for mic_entry_line in self.mic_jack_data:
         mic_entry_line[2].clicked()

   def cb_headroom(self, widget):
      self.parent.mixer_write("HEAD=%f\nACTN=headroom\nend\n" % widget.get_value(), True)

   def cb_rg_indicate(self, widget):
      left = self.parent.player_left
      right = self.parent.player_right
      
      if widget.get_active():
         left.treeview.insert_column(left.rgtvcolumn, 0)
         right.treeview.insert_column(right.rgtvcolumn, 0)
      else:         
         left.treeview.remove_column(left.rgtvcolumn)
         right.treeview.remove_column(right.rgtvcolumn)
               
   def cb_realize(self, window):
      self.wst.apply()
         
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
      set_tip(self.startfull, _('Indicates which mode IDJC will be in when launched.'))
      
      # TC: Start in a reduced user interface mode.
      self.startmini = gtk.RadioButton(self.startfull, _('Start Mini'))
      self.startmini.set_border_width(2)
      vbox.pack_start(self.startmini, False, False, 0)
      self.startmini.show()
      set_tip(self.startmini, _('Indicates which mode IDJC will be in when launched.'))
      
      vbox.show()
      hbox2 = gtk.HBox()
      hbox2.set_border_width(10)
      hbox2.set_spacing(20)
      hbox.pack_start(hbox2, True, False, 0)
      
      self.maxi = gtk.Button(" %s " % _('Fully Featured'))
      self.maxi.connect("clicked", self.callback, "fully featured")
      hbox2.pack_start(self.maxi, False, False, 0)
      self.maxi.show()
      set_tip(self.maxi, _('Run in full functionality mode which uses more CPU power.'))
      
      self.mini = gtk.Button(" %s " % _('Basic Streamer'))
      self.mini.connect("clicked", self.callback, "basic streamer")
      hbox2.pack_start(self.mini, False, False, 0)
      self.mini.show()
      set_tip(self.mini, _('Run in a reduced functionality mode that lowers the burden on the CPU and takes up less screen space.'))
      
      hbox2.show()   
      hbox.pack_start(vbox, False, False, 9)     
      hbox.show()
      
      requires_restart = gtk.Frame(" %s " % _('These settings take effect after restarting'))
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

      self.mic_qty_adj = gtk.Adjustment(PGlobs.num_micpairs * 2, 2.0, 12.0, 2.0)
      spin = gtk.SpinButton(self.mic_qty_adj)
      rrvbox.pack_start(hjoin(spin, gtk.Label(_('Microphone audio channels*'))))
   
      self.stream_qty_adj = gtk.Adjustment(PGlobs.num_streamers, 1.0, 9.0, 1.0)
      spin = gtk.SpinButton(self.stream_qty_adj)
      rrvbox.pack_start(hjoin(spin, gtk.Label(_('Simultaneous stream(s)'))))

      self.recorder_qty_adj = gtk.Adjustment(PGlobs.num_recorders, 0.0, 4.0, 1.0)
      spin = gtk.SpinButton(self.recorder_qty_adj)
      rrvbox.pack_start(hjoin(spin, gtk.Label(_('Simultaneous recording(s)'))))
      
      # TC: star marked items are relevant only in 'fully featured' mode.
      key_label = gtk.Label(_("* In 'Fully Featured' mode."))
      rrvbox.pack_start(key_label)
      key_label.show()

      self.rrvaluesdict = {"num_micpairs": self.mic_qty_adj,
                           "num_streamers": self.stream_qty_adj,
                           "num_recorders": self.recorder_qty_adj}
      
      # Meters on/off
      
      def showhide(toggle, target):
         if toggle.get_active():
            target.show()
         else:
            target.hide()
      frame = gtk.Frame(" %s " % _('Meters'))
      frame.set_border_width(3)
      vbox = gtk.VBox()
      vbox.set_border_width(10)
      frame.add(vbox)
      vbox.show()
      self.show_stream_meters = gtk.CheckButton(_('Stream Audio Levels And Connections'))
      self.show_stream_meters.set_active(True)
      self.show_stream_meters.connect("toggled", showhide, parent.streammeterbox)
      parent.str_meters_action.connect_proxy(self.show_stream_meters)
      vbox.pack_start(self.show_stream_meters, False, False)
      self.show_stream_meters.show()
      
      hbox = gtk.HBox()
      vbox.pack_start(hbox, False, False)
      hbox.show()
      self.show_microphones = gtk.CheckButton(_('Microphone Meters'))
      self.show_microphones.set_active(True)
      self.show_microphones.connect("toggled", showhide, parent.micmeterbox)
      parent.mic_meters_action.connect_proxy(self.show_microphones)
      hbox.pack_start(self.show_microphones, False, False)
      self.show_microphones.show()            
      
      self.show_all_microphones = gtk.RadioButton(None, _('All'))
      for meter in parent.mic_meters:
         self.show_all_microphones.connect("toggled", meter.always_show)
      hbox.pack_start(self.show_all_microphones, False, False)
      self.show_all_microphones.show()
      
      self.show_active_microphones = gtk.RadioButton(self.show_all_microphones, _('Only Those Active'))
      hbox.pack_start(self.show_active_microphones, False, False)
      self.show_active_microphones.show()
      
      outervbox.pack_start(frame, False, False, 0)
      frame.show()
      
      # Replay Gain controls
      
      frame = gtk.Frame(" %s " % _('Replay Gain'))
      frame.set_border_width(3)
      outervbox.pack_start(frame, False, False, 0)
      vbox = gtk.VBox()
      frame.add(vbox)
      frame.show()
      vbox.set_border_width(10)
      vbox.set_spacing(1)
      vbox.show()
      
      self.rg_indicate = gtk.CheckButton(_('Indicate which tracks have Replay Gain values'))
      set_tip(self.rg_indicate, _('Show a marker in the playlists next to each track.'))
      self.rg_indicate.connect("toggled", self.cb_rg_indicate)
      vbox.pack_start(self.rg_indicate, False, False, 0)
      self.rg_indicate.show()
      
      self.rg_adjust = gtk.CheckButton(_('Adjust playback volume'))
      set_tip(self.rg_adjust, _('Effective only on newly started tracks.'))
      vbox.pack_start(self.rg_adjust, False, False, 0)
      self.rg_adjust.show()
      
      hbox = gtk.HBox()
      hbox.set_spacing(3)
      spacer = gtk.HBox()
      hbox.pack_start(spacer, False, False, 16)
      spacer.show()
      label = gtk.Label(_('Unmarked tracks assumed gain value'))
      hbox.pack_start(label, False, False, 0)
      label.show()
      rg_defaultgainadj = gtk.Adjustment(-8.0, -20.0, 10.0, 0.1)
      self.rg_defaultgain = gtk.SpinButton(rg_defaultgainadj, 0.0, 1)
      set_tip(hbox, _('Set this to the typical track gain values you would expect for the programme material you are currently playing. For pop and rock music (especially modern studio recordings) this should be about a -8 or -9 and classical music around zero.'))
      hbox.pack_start(self.rg_defaultgain, False, False, 0)
      self.rg_defaultgain.show()
      vbox.pack_start(hbox, False, False, 0)
      hbox.show()

      hbox = gtk.HBox()
      hbox.set_spacing(3)
      spacer = gtk.HBox()
      hbox.pack_start(spacer, False, False, 16)
      spacer.show()
      label = gtk.Label(_('Further gain adjustment'))
      hbox.pack_start(label, False, False, 0)
      label.show()
      rg_boostadj = gtk.Adjustment(6.0, -5.0, 15.5, 0.5)
      self.rg_boost = gtk.SpinButton(rg_boostadj, 0.0, 1)
      set_tip(hbox, _('For material that is generally loud it is recommended to set this between 4 and 8 dB however going too high will result in a loss of dynamic range. The Str Peak meter is a useful guide for getting this right.'))
      hbox.pack_start(self.rg_boost, False, False, 0)
      self.rg_boost.show()
      vbox.pack_start(hbox, False, False, 0)
      hbox.show()

      # Miscellaneous Features
      
      frame = gtk.Frame(" " + _('Miscellaneous Features') + " ")
      frame.set_border_width(3)
      vbox = gtk.VBox()
      frame.add(vbox)
      frame.show()
      vbox.set_border_width(10)
      vbox.set_spacing(1)
      
      self.silence_killer = gtk.CheckButton(_('Trim quiet endings'))
      self.silence_killer.set_active(True)
      vbox.pack_start(self.silence_killer, False, False, 0)
      self.silence_killer.show()
      
      self.bonus_killer = gtk.CheckButton(_('End tracks containing long passages of silence'))
      self.bonus_killer.set_active(True)
      vbox.pack_start(self.bonus_killer, False, False, 0)
      self.bonus_killer.show()
      
      self.twodblimit = gtk.CheckButton(_('Restrict the stream audio ceiling to -2dB'))
      vbox.pack_start(self.twodblimit, False, False, 0)
      self.twodblimit.connect("toggled", self.cb_twodblimit)
      self.twodblimit.show()
      set_tip(self.twodblimit, _('This option may improve the audio quality at the expense of a little playback volume. Limiting audio to -2dB at the encoder input will generally prevent decoded audio from breaching 0dB.'))
      
      self.speed_variance = gtk.CheckButton(_('Enable the main-player speed/pitch controls'))
      vbox.pack_start(self.speed_variance, False, False, 0)
      self.speed_variance.connect("toggled", self.cb_pbspeed)
      self.speed_variance.show()
      set_tip(self.speed_variance, _('This option causes some extra widgets to appear below the playlists which allow the playback speed to be adjusted from 25% to 400% and a normal speed button.'))

      self.dual_volume = gtk.CheckButton(_('Separate left/right player volume faders'))
      vbox.pack_start(self.dual_volume, False, False, 0)
      self.dual_volume.connect("toggled", self.cb_dual_volume)
      self.dual_volume.show()
      set_tip(self.dual_volume, _('Select this option to use an independent volume fader for the left and right music players.'))

      self.flash_mic = gtk.CheckButton(_('Open mic button icon to flash during playback'))
      vbox.pack_start(self.flash_mic, False)
      self.flash_mic.show()
      set_tip(self.flash_mic, _('A reminder to turn the microphone off when a main player is active and any particular mic button is still engaged.'))
      
      self.bigger_box_toggle = gtk.CheckButton(_('Enlarge the time elapsed/remaining windows'))
      vbox.pack_start(self.bigger_box_toggle, False, False, 0)
      self.bigger_box_toggle.connect("toggled", self.callback, "bigger box")
      self.bigger_box_toggle.show()
      set_tip(self.bigger_box_toggle, _("The time elapsed/remaining windows sometimes don't appear big enough for the text that appears in them due to unusual DPI settings or the use of a different rendering engine. This option serves to fix that."))
      
      self.djalarm = gtk.CheckButton(_('Sound an alarm when the music is due to end'))
      vbox.pack_start(self.djalarm, False, False, 0)
      self.djalarm.show()
      set_tip(self.djalarm, _('An alarm tone alerting the DJ that dead-air is just nine seconds away. This also works when monitoring stream audio but the alarm tone is not sent to the stream.'))
      
      self.dither = gtk.CheckButton(_('Apply dither to MP3 and FLAC playback'))
      vbox.pack_start(self.dither, False, False, 0)
      self.dither.connect("toggled", self.cb_dither)
      self.dither.show()
      set_tip(self.dither, _('This feature maybe improves the sound quality a little when listening on a 24 bit sound card.'))

      self.mp3_utf8 = gtk.CheckButton(_('Use utf-8 encoding when streaming mp3 metadata'))
      self.mp3_utf8.set_active(True)
      vbox.pack_start(self.mp3_utf8, False, False, 0)
      self.mp3_utf8.show()
      set_tip(self.mp3_utf8, _('It is standard to stream mp3 metadata with iso-8859-1 character encoding on shoutcast. This option should therefore not be used.'))
      
      self.mic_aux_mutex = gtk.CheckButton(_('Make Mic and Aux buttons mutually exclusive'))
      vbox.pack_start(self.mic_aux_mutex, False, False, 0)
      self.mic_aux_mutex.show()
      set_tip(self.mic_aux_mutex, _('This feature ensures that the microphone and auxiliary inputs can not both be on at the same time. This allows the DJ to be able to switch between the two with only one mouse click. It may be of use to those who mix a lot of external audio, or who wish to use the auxiliary input as a secondary microphone source with different audio processing.'))
      
      self.enable_tooltips = gtk.CheckButton(_('Enable tooltips'))
      self.enable_tooltips.connect("toggled", self.callback, "tooltips")
      vbox.pack_start(self.enable_tooltips, False, False, 0)
      self.enable_tooltips.show()
      set_tip(self.enable_tooltips, _('This, what you are currently reading, is a tooltip. This feature turns them on or off.'))
      
      vbox.show()

      outervbox.pack_start(frame, False, False, 0)
      
      # Stream normalizer config
      
      frametitlebox = gtk.HBox()
      self.normalize = gtk.CheckButton(_('Stream Normaliser'))
      self.normalize.connect("toggled", self.cb_normalizer)
      frametitlebox.pack_start(self.normalize, True, False, 2)
      set_tip(self.normalize, _("This feature is provided to make the various pieces of music that are played of a more uniform loudness level. The default settings are likely to be sufficient however you may adjust them and you can compare the effect by clicking the 'Monitor Mix' 'Stream' button in the main application window which will allow you to compare the processed with the non-processed audio."))
      self.normalize.show()
      frametitlebox.show()

      frame = gtk.Frame()
      frame.set_label_widget(frametitlebox)
      frame.set_border_width(3)
      self.normalizer_hbox = gtk.HBox()
      self.normalizer_hbox.set_sensitive(False)
      self.normalizer_hbox.set_border_width(5)
      frame.add(self.normalizer_hbox)
      self.normalizer_hbox.show()
      mvbox = gtk.VBox()
      self.normalizer_hbox.pack_start(mvbox, True, False, 0)
      mvbox.show()
      lvbox = gtk.VBox()
      lvbox.set_spacing(2)
      self.normalizer_hbox.pack_start(lvbox, True, False, 0)
      lvbox.show()
      rvbox = gtk.VBox()
      rvbox.set_spacing(2)
      self.normalizer_hbox.pack_start(rvbox, True, False, 0)
      rvbox.show()
      outervbox.pack_start(frame, False, False, 0)
      frame.show()
      
      sizegroup = gtk.SizeGroup(gtk.SIZE_GROUP_HORIZONTAL)
      
      boostbox = gtk.HBox()
      boostbox.set_spacing(3)
      self.normboost_adj = gtk.Adjustment(12.0, 0.0, 25.0, 0.1, 0.2)
      normboost = gtk.SpinButton(self.normboost_adj, 1, 1)
      normboost.connect("value-changed", self.cb_normalizer)
      sizegroup.add_widget(normboost)
      boostbox.pack_start(normboost, False, False, 0)
      normboost.show()
      label = gtk.Label(_('Boost'))
      boostbox.pack_start(label, False, False, 0)
      label.show()
      lvbox.add(boostbox)
      boostbox.show()
      set_tip(normboost, _('Adjust these settings carefully since they can have subtle but undesireable effects on the sound quality.'))
      
      ceilingbox = gtk.HBox()
      ceilingbox.set_spacing(3)
      self.normceiling_adj = gtk.Adjustment(-12.0, -25.0, 0.0, 0.1, 0.2)
      normceiling = gtk.SpinButton(self.normceiling_adj, 1, 1)
      normceiling.connect("value-changed", self.cb_normalizer)
      sizegroup.add_widget(normceiling)
      ceilingbox.pack_start(normceiling, False, False, 0)
      normceiling.show()
      label = gtk.Label(_('Threshold'))
      ceilingbox.pack_start(label, False, False, 0)
      label.show()
      lvbox.add(ceilingbox)
      ceilingbox.show()
      set_tip(normceiling, _('Adjust these settings carefully since they can have subtle but undesireable effects on the sound quality.'))
      
      defaultsbox = gtk.HBox()
      self.normdefaults = gtk.Button(_('Defaults'))
      self.normdefaults.connect("clicked", self.normalizer_defaults)
      defaultsbox.pack_start(self.normdefaults, True, True, 0)
      self.normdefaults.show()
      mvbox.pack_start(defaultsbox, True, False, 0)
      defaultsbox.show()
      set_tip(self.normdefaults, _('Load the recommended settings.'))
      
      sizegroup = gtk.SizeGroup(gtk.SIZE_GROUP_HORIZONTAL)
      
      risebox = gtk.HBox()
      risebox.set_spacing(3)
      self.normrise_adj = gtk.Adjustment(2.7, 0.1, 5.0, 0.1, 1.0)
      normrise = gtk.SpinButton(self.normrise_adj, 1, 1)
      normrise.connect("value-changed", self.cb_normalizer)
      sizegroup.add_widget(normrise)
      risebox.pack_start(normrise, False, False, 0)
      normrise.show()
      label = gtk.Label(_('Rise'))
      risebox.pack_start(label, False, False, 0)
      label.show()
      rvbox.add(risebox)
      risebox.show()
      set_tip(normrise, _('Adjust these settings carefully since they can have subtle but undesireable effects on the sound quality.'))
      
      fallbox = gtk.HBox()
      fallbox.set_spacing(3)
      self.normfall_adj = gtk.Adjustment(2.0, 0.1, 5.0, 0.1, 1.0)
      normfall = gtk.SpinButton(self.normfall_adj, 1, 1)
      normfall.connect("value-changed", self.cb_normalizer)
      sizegroup.add_widget(normfall)
      fallbox.pack_start(normfall, False, False, 0)
      normfall.show()
      label = gtk.Label(_('Fall'))
      fallbox.pack_start(label, False, False, 0)
      label.show()
      rvbox.add(fallbox)
      fallbox.show()
      set_tip(normfall, _('Adjust these settings carefully since they can have subtle but undesireable effects on the sound quality.'))
      
      aud_rs_hbox = gtk.HBox()
      
      # User can use this to set the audio level in the headphones
      
      # TC: The DJ's sound level controller.
      frame = gtk.Frame(" " + _('DJ Audio Level') + " ")
      frame.set_label_align(0.5, 0.5)
      frame.set_border_width(3)
      hbox = gtk.HBox()
      hbox.set_border_width(5)
      frame.add(hbox)
      hbox.show()
      
      self.dj_aud_adj = gtk.Adjustment(0.0, -60.0, 0.0, 0.5, 1.0)
      dj_aud = gtk.SpinButton(self.dj_aud_adj, 1, 1)
      dj_aud.connect("value-changed", self.cb_dj_aud)
      hbox.pack_start(dj_aud, True, False, 0)
      dj_aud.show()
      set_tip(dj_aud, _('This adjusts the sound level of the DJ audio.'))
      
      aud_rs_hbox.pack_start(frame, False, False, 0)
      frame.show()
      
      # User can use this to set the resampled sound quality
      
      frame = gtk.Frame(" %s " % _('Player Resample Quality'))
      frame.set_label_align(0.5, 0.5)
      frame.set_border_width(3)
      hbox = gtk.HBox()
      hbox.set_border_width(5)
      frame.add(hbox)
      hbox.show()
      self.best_quality_resample = gtk.RadioButton(None, _('Highest'))
      self.best_quality_resample.connect("toggled", self.cb_resample_quality, 0)
      rsbox = gtk.HBox()
      rsbox.pack_start(self.best_quality_resample, True, False, 0)
      rsbox.show()
      hbox.add(rsbox)
      self.best_quality_resample.show()
      self.good_quality_resample = gtk.RadioButton(self.best_quality_resample, _('Good'))
      self.good_quality_resample.connect("toggled", self.cb_resample_quality, 1) 
      rsbox = gtk.HBox()
      rsbox.pack_start(self.good_quality_resample, True, False, 0)
      rsbox.show()
      hbox.add(rsbox)
      self.good_quality_resample.show()
      self.fast_resample = gtk.RadioButton(self.good_quality_resample, _('Fast'))
      self.fast_resample.connect("toggled", self.cb_resample_quality, 2) 
      rsbox = gtk.HBox()
      rsbox.pack_start(self.fast_resample, True, False, 0)
      rsbox.show()
      hbox.add(rsbox)
      self.fast_resample.show()
      self.fastest_resample = gtk.RadioButton(self.fast_resample, _('Fastest'))
      self.fastest_resample.connect("toggled", self.cb_resample_quality, 4) 
      rsbox = gtk.HBox()
      rsbox.pack_start(self.fastest_resample, True, False, 0)
      rsbox.show()
      hbox.add(rsbox)
      self.fastest_resample.show()
      aud_rs_hbox.pack_start(frame, True, True, 0)
      frame.show()
      set_tip(self.best_quality_resample, _('This adjusts the quality of the audio resampling method used whenever the sample rate of the music file currently playing does not match the sample rate of the JACK sound server. Highest mode offers the best sound quality but also uses the most CPU (not recommended for systems built before 2006). Fastest mode while it uses by far the least amount of CPU should be avoided if at all possible.'))
      set_tip(self.good_quality_resample, _('This adjusts the quality of the audio resampling method used whenever the sample rate of the music file currently playing does not match the sample rate of the JACK sound server. Highest mode offers the best sound quality but also uses the most CPU (not recommended for systems built before 2006). Fastest mode while it uses by far the least amount of CPU should be avoided if at all possible.'))
      set_tip(self.fast_resample, _('This adjusts the quality of the audio resampling method used whenever the sample rate of the music file currently playing does not match the sample rate of the JACK sound server. Highest mode offers the best sound quality but also uses the most CPU (not recommended for systems built before 2006). Fastest mode while it uses by far the least amount of CPU should be avoided if at all possible.'))
      set_tip(self.fastest_resample, _('This adjusts the quality of the audio resampling method used whenever the sample rate of the music file currently playing does not match the sample rate of the JACK sound server. Highest mode offers the best sound quality but also uses the most CPU (not recommended for systems built before 2006). Fastest mode while it uses by far the least amount of CPU should be avoided if at all possible.'))
      
      outervbox.pack_start(aud_rs_hbox, False, False, 0)
      aud_rs_hbox.show()
      
      # Prokyon 3 database connection
      self.p3prefs = p3db.Prefs(self.parent)
      outervbox.pack_start(self.p3prefs, False, False, 0)
      self.p3prefs.show()
      
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
      self.restore_session_option = gtk.CheckButton(_('Restore the previous session'))
      vbox.pack_start(restoresessionhbox, False, False, 0)
      restoresessionhbox.pack_start(self.restore_session_option, False, False, 0)
      self.restore_session_option.show()
      set_tip(self.restore_session_option, _('When starting IDJC most of the main window settings will be as they were left. As an alternative you may specify below how you want the various settings to be when IDJC starts.'))
      
      hbox = gtk.HBox(True)
      vbox.add(hbox)
      hbox.set_border_width(6)
      hbox.set_spacing(3)
      
      self.lpconfig = InitialPlayerConfig(_("Player 1"), parent.player_left, "l")
      self.rpconfig = InitialPlayerConfig(_("Player 2"), parent.player_right, "r")
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
     
      outervbox.pack_start(frame, False, False, 0)
      frame.show() 
            
      # TC: Tab heading for controls that don't merit their own preferences tab.
      features_label = gtk.Label(_('General'))
      self.notebook.append_page(generalwindow, features_label)
      features_label.show()
      outervbox.show()
         
      # Microphones tab
      
      scrolled_window = gtk.ScrolledWindow()
      scrolled_window.set_border_width(0)
      scrolled_window.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
      panevbox = gtk.VBox()
      scrolled_window.add_with_viewport(panevbox)
      scrolled_window.show()
      panevbox.set_border_width(3)
      panevbox.get_parent().set_shadow_type(gtk.SHADOW_NONE)
      panevbox.show()
     
      # Opener buttons controls
      
      panevbox.pack_start(parent.channel_opener_box.settings, False)
    
      # New AGC controls
      
      mic_controls = []
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
            uhbox.add(c)
            c.show()
            parent.mic_opener.add_mic(c)
            parent.channel_opener_box.register_channel(c)
            mic_controls.append(c)
         mic_controls[-2].set_partner(mic_controls[-1])
         mic_controls[-1].set_partner(mic_controls[-2])   
      parent.mic_opener.new_button_set()
      parent.channel_opener_box.finalise()

      panevbox.pack_start(vbox, False, False, 0)
      vbox.show()
      
      frame = gtk.Frame(" %s " % _('General Mic Options'))
      frame.set_label_align(0.5, 0.5)
      frame.set_border_width(3)
      vbox = gtk.VBox()
      vbox.set_border_width(3)
      frame.add(vbox)
      vbox.show()
      panevbox.pack_start(frame, False, False, 0)
      frame.show()
      hbox = gtk.HBox()
      label = gtk.Label(_('Player headroom when a microphone is open (dB)'))
      hbox.pack_start(label, False, False, 0)
      label.show()
      headroom_adj = gtk.Adjustment(0.0, 0.0, 32.0, 0.5)
      self.headroom = gtk.SpinButton(headroom_adj, digits=1)
      self.headroom.connect("value-changed", self.cb_headroom)
      hbox.pack_end(self.headroom, False, False, 0)
      self.headroom.show()
      vbox.add(hbox)
      hbox.show()
      
      compressor_label = gtk.Label(_('Channels'))
      self.notebook.append_page(scrolled_window, compressor_label)
      compressor_label.show()
       
      # Jack settings tab      
                 
      scrolled = gtk.ScrolledWindow()
      scrolled.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
      jack_vbox = gtk.VBox()
      scrolled.add_with_viewport(jack_vbox)
      scrolled.child.set_shadow_type(gtk.SHADOW_NONE)
      jack_vbox.set_spacing(3)
      #jack_vbox.set_border_width(4)
      jack_vbox.show()
      
      jackname = os.environ["jack_server_name"]
      if jackname != "default":
         label = gtk.Label(_('Using named JACK server: %s') % jackname)
         jack_vbox.add(label)
         label.show()
      
      frame = gtk.Frame()
      frame.set_border_width(5)
      vbox = gtk.VBox(False, 0)
      frame.add(vbox)
      frame.show()
      
      self.mic_jack_data = []
      for i in range(1, PGlobs.num_micpairs * 2 + 1):
         n = str(i)
         box, check, entry, update = make_entry_line(self, "ch_in_" + n + ": ", "MIC", True, i - 1)
         vbox.add(box)
         self.mic_jack_data.append((check, entry, update))
         if i < 5:
            entry.set_text("system:capture_%d" % i)
      jack_vbox.pack_start(frame, False)
      vbox.show()
      
      frame = gtk.Frame()
      frame.set_border_width(5)
      vbox = gtk.VBox(False, 0)
      frame.add(vbox)
      frame.show()
      box, self.auxlcheck, self.auxlentry, self.auxlupdate = make_entry_line(self, "aux_in_l: ", "AUXL", False)
      vbox.add(box)
      box, self.auxrcheck, self.auxrentry, self.auxrupdate = make_entry_line(self, "aux_in_r: ", "AUXR", False)
      vbox.add(box)
      box, self.midicheck, self.midientry, self.midiupdate = make_entry_line(self, "midi_control: ", "MIDI", False)
      vbox.add(box)
      jack_vbox.pack_start(frame, False)
      vbox.show()
     
      frame = gtk.Frame()
      frame.set_border_width(5)
      vbox = gtk.VBox(False, 0)
      frame.add(vbox)
      frame.show()
      box, self.audlcheck, self.audlentry, self.audlupdate = make_entry_line(self, "dj_out_l: ", "AUDL", True)
      vbox.add(box)
      box, self.audrcheck, self.audrentry, self.audrupdate = make_entry_line(self, "dj_out_r: ", "AUDR", True)
      vbox.add(box)
      jack_vbox.pack_start(frame, False)
      vbox.show()
      self.audlentry.set_text("system:playback_1")
      self.audrentry.set_text("system:playback_2")
      
      frame = gtk.Frame()
      frame.set_border_width(5)
      vbox = gtk.VBox(False, 0)
      frame.add(vbox)
      frame.show()
      box, self.strlcheck, self.strlentry, self.strlupdate = make_entry_line(self, "str_out_l: ", "STRL", True)
      vbox.add(box)
      box, self.strrcheck, self.strrentry, self.strrupdate = make_entry_line(self, "str_out_r: ", "STRR", True)
      vbox.add(box)
      jack_vbox.pack_start(frame, False)
      vbox.show()
      self.strlentry.set_text("system:playback_5")
      self.strrentry.set_text("system:playback_6")
      
      frame = gtk.Frame()
      frame.set_border_width(5)
      self.use_dsp = gtk.CheckButton(_('Route audio through the DSP interface'))
      self.use_dsp.connect("toggled", self.cb_use_dsp)
      frame.set_label_widget(self.use_dsp)
      self.use_dsp.show()
      vbox = gtk.VBox(False, 0)
      frame.add(vbox)
      frame.show()
      box, self.dolcheck, self.dolentry, self.dolupdate = make_entry_line(self, "dsp_out_l: ", "DOL", False)
      vbox.add(box)
      self.dolentry.set_text("jamin:in_L")
      box, self.dorcheck, self.dorentry, self.dorupdate = make_entry_line(self, "dsp_out_r: ", "DOR", False)
      vbox.add(box)
      self.dorentry.set_text("jamin:in_R")
      box, self.dilcheck, self.dilentry, self.dilupdate = make_entry_line(self, "dsp_in_l: ", "DIL", False)
      vbox.add(box)
      self.dilentry.set_text("jamin:out_L")
      box, self.dircheck, self.direntry, self.dirupdate = make_entry_line(self, "dsp_in_r: ", "DIR", False)
      self.direntry.set_text("jamin:out_R")
      vbox.add(box)
      jack_vbox.pack_start(frame, False)
      vbox.show()
      
      jacklabel = gtk.Label(_('JACK Ports'))
      self.notebook.append_page(scrolled, jacklabel)
      jacklabel.show()
      scrolled.show()

      # Controls tab
      tab= midicontrols.ControlsUI(self.parent.controls)
      # TC: Keyboard and MIDI bindings configuration.
      label= gtk.Label(_('Bindings'))
      self.notebook.append_page(tab, label)
      tab.show()
      label.show()

      # Event tab
      
      vbox = gtk.VBox()
      vbox.set_border_width(4)
      vbox.set_spacing(2)
      
      app_event_container = self.event_command_container()
      self.appstart_event = self.event_command("icon", 20, 20, "", False, False, _('When IDJC starts run the commands to the right.'), _('Enter bash shell commands to run, separated by a semicolon for this particular event.'))
      app_event_container.add(self.appstart_event)
      self.appstart_event.show()
      self.appexit_event = self.event_command("icon", 20, 20, "", False, True, _('When IDJC exits run the commands to the right.'), _('Enter bash shell commands to run, separated by a semicolon for this particular event.'))
      app_event_container.add(self.appexit_event)
      self.appexit_event.show()
      vbox.pack_start(app_event_container, False, False, 0)
      app_event_container.show()
      
      mic_event_container = self.event_command_container()
      self.mic_on_event = self.event_command("mic4", 20, 20, "", False, False, _('Each time the microphone is turned on run the commands to the right.'), _('Enter bash shell commands to run, separated by a semicolon for this particular event.'))
      mic_event_container.add(self.mic_on_event)
      self.mic_on_event.show()
      self.mic_off_event = self.event_command("mic4", 20, 20, "", False, True, _('Each time the microphone is turned off run the commands to the right.'), _('Enter bash shell commands to run, separated by a semicolon for this particular event.'))
      mic_event_container.add(self.mic_off_event)
      self.mic_off_event.show()
      vbox.pack_start(mic_event_container, False, False, 0)
      mic_event_container.show()
      
      aux_event_container = self.event_command_container()
      self.aux_on_event = self.event_command("jack2", 20, 20, "", False, False, _('Each time the auxiliary input is turned on run the commands to the right.'), _('Enter bash shell commands to run, separated by a semicolon for this particular event.'))
      aux_event_container.add(self.aux_on_event)
      self.aux_on_event.show()
      self.aux_off_event = self.event_command("jack2", 20, 20, "", False, True, _('Each time the auxiliary input is turned off run the commands to the right.'), _('Enter bash shell commands to run, separated by a semicolon for this particular event.'))
      aux_event_container.add(self.aux_off_event)
      self.aux_off_event.show()
      vbox.pack_start(aux_event_container, False, False, 0)
      aux_event_container.show()
      
      eventlabel = gtk.Label(_('Event'))
      self.notebook.append_page(vbox, eventlabel)
      eventlabel.show()
      vbox.show()
      
      # about tab
      
      frame = gtk.Frame()
      frame.set_border_width(9)
      vbox = gtk.VBox()
      frame.add(vbox)
      label = gtk.Label()
      label.set_markup('<span font_desc="sans italic 20">' + self.parent.appname + '</span>')
      vbox.pack_start(label, False, False, 13)
      label.show()
      label = gtk.Label()
      label.set_markup('<span font_desc="sans 13">Version ' + self.parent.version + '</span>')
      vbox.pack_start(label, False, False, 0)
      label.show()
      
      pixbuf = gtk.gdk.pixbuf_new_from_file(FGlobs.pkgdatadir / "logo.png")
      image = gtk.Image()
      image.set_from_pixbuf(pixbuf)
      vbox.pack_start(image, False, False, 8)
      image.show()
      
      label = gtk.Label()
      label.set_markup(u'<span font_desc="sans 13">' + self.parent.copyright + u'</span>')
      vbox.pack_start(label, False, False, 12)
      label.show()
      
      label = gtk.Label()
      # TC: 'General Public License' is a proper name and must not be translated. It can however be abbreviated as 'GPL'.
      label.set_markup('<span font_desc="sans 10" underline="low" foreground="blue">' + _('Released under the GNU General Public License V2.0') + '</span>')
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
      
      contributors = ("Stephen Fairchild (s-fairchild@users.sourceforge.net)", "And Clover (and@doxdesk.com)", "Dario Abatianni (eisfuchs@users.sourceforge.net)", "Stefan Fendt (stefan@sfendt.de)", "Jannis Achstetter (jannis_achstetter@web.de)", "Sven Krohlas (sven@asbest-online.de)")
      
      sw = gtk.ScrolledWindow()
      sw.set_border_width(1)
      sw.set_shadow_type(gtk.SHADOW_NONE)
      sw.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
      label = gtk.Label(_('Contributors'))
      nb.append_page(sw, label)
      sw.show()
      lw.show()
      ivbox = gtk.VBox()
      sw.add_with_viewport(ivbox)
      ivbox.show()
      for each in contributors:
         label = gtk.Label(each)
         ivbox.add(label)
         label.show()
      
      vbox.show()

      aboutlabel = gtk.Label(_('About'))
      self.notebook.append_page(frame, aboutlabel)
      aboutlabel.show()
      frame.show()
      
      self.notebook.show()

      # These on by default
      self.flash_mic.set_active(True)
      self.djalarm.set_active(True)
      self.dither.set_active(True)
      self.fastest_resample.set_active(True)
      self.enable_tooltips.set_active(True)
      mic0 = mic_controls[0]
      mic0.mode.set_active(1)
      mic0.alt_name.set_text("DJ")
      mic0.autoopen.set_active(True)
      self.show_stream_meters.set_active(True)
      self.show_microphones.set_active(True)
      self.headroom.set_value(3.0)
      
      self.load_jack_port_settings()
      self.bind_jack_ports()
      
      self.playersettingsdict = {       # Settings of these will be saved in the config file 
         "startmini"     : self.startmini,
         "djalarm"       : self.djalarm,
         "trxpld"        : self.tracks_played,
         "strmon"        : self.stream_mon,
         "bigdigibox"    : self.bigger_box_toggle, 
         "normalize"     : self.normalize,
         "dither"        : self.dither,
         "recallsession" : self.restore_session_option,
         "proktoggle"    : self.p3prefs.proktoggle,
         "ee_appstart"   : self.appstart_event,
         "ee_appexit"    : self.appexit_event,
         "ee_micon"      : self.mic_on_event,
         "ee_micoff"     : self.mic_off_event,
         "ee_auxon"      : self.aux_on_event,
         "ee_auxoff"     : self.aux_off_event,
         "best_rs"       : self.best_quality_resample,
         "good_rs"       : self.good_quality_resample,
         "fast_rs"       : self.fast_resample,
         "fastest_rs"    : self.fastest_resample,
         "micauxmutex"   : self.mic_aux_mutex,
         "speed_var"     : self.speed_variance,
         "dual_volume"   : self.dual_volume,
         "twodblimit"    : self.twodblimit,
         "showtips"      : self.enable_tooltips,
         "mp3utf8"       : self.mp3_utf8,
         "silencekiller" : self.silence_killer,
         "bonuskiller"   : self.bonus_killer,
         "rg_indicate"   : self.rg_indicate,
         "rg_adjust"     : self.rg_adjust,
         "str_meters"    : self.show_stream_meters,
         "mic_meters"    : self.show_microphones,
         "mic_meters_active" : self.show_active_microphones,
         "flash_mic"     : self.flash_mic,
         }
         
      for mic_control in mic_controls:
         self.playersettingsdict.update(mic_control.booleandict)

      for each in (self.lpconfig, self.rpconfig):
         self.playersettingsdict.update(each.active_dict)


      self.valuesdict = {
         "interval_vol"  : self.parent.jingles.interadj,
         "passspeed"     : self.parent.passspeed_adj,
         "normboost"     : self.normboost_adj,
         "normceiling"   : self.normceiling_adj,
         "normrisetc"    : self.normrise_adj,
         "normfalltc"    : self.normfall_adj, 
         "djvolume"      : self.dj_aud_adj,
         "headroom"      : self.headroom,
         "rg_default"    : self.rg_defaultgain,
         "rg_boost"      : self.rg_boost,
         }

      for mic_control in mic_controls:
         self.valuesdict.update(mic_control.valuesdict)

      self.textdict = {                   # These are all text
         "prokuser"      : self.p3prefs.prokuser,
         "prokdatabase"  : self.p3prefs.prokdatabase,
         "prokpassword"  : self.p3prefs.prokpassword,
         "prokhostname"  : self.p3prefs.prokhostname,
         "ltfilerqdir"   : self.parent.player_left.file_requester_start_dir,
         "rtfilerqdir"   : self.parent.player_right.file_requester_start_dir,
         "et_appstart"   : self.appstart_event,
         "et_appexit"    : self.appexit_event,
         "et_micon"      : self.mic_on_event,
         "et_micoff"     : self.mic_off_event,
         "et_auxon"      : self.aux_on_event,
         "et_auxoff"     : self.aux_off_event,
         "main_full_wst" : self.parent.full_wst,
         "main_min_wst"  : self.parent.min_wst,
         "jingles_wst"   : self.parent.jingles.wst,
         "prefs_wst"     : self.wst,
         }

      for mic_control in mic_controls:
         self.textdict.update(mic_control.textdict)

      self.rangewidgets = (self.parent.deckadj,)
