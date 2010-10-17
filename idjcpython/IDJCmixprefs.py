#   IDJCmixprefs.py: Preferences window code for IDJC
#   Copyright (C) 2005-2007 Stephen Fairchild (s-fairchild@users.sourceforge.net)
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

import pygtk
pygtk.require('2.0')
import gtk, os, licence_window, p3db, shutil
import idjc_config
from idjc_config import *
from ln_text import ln
from IDJCfree import int_object
import IDJCcontrols

class XChatInstaller(gtk.Button):
   def check_plugin(self):
      if os.path.exists(os.path.join(self.home, ".xchat2")):
         self.set_sensitive(False)
         self.set_label(ln.xchat_install_done)
         return True
      return False
         
   def cb_install(self, widget):
      plugin = "idjc-announce.py"
      source = os.path.join(plugindir, plugin)
      dest = os.path.join(self.home, plugin)
      shutil.copy(source, dest)
      if not self.check_plugin():
         self.set_label(ln.xchat_install_failed)

   def __init__(self):
      gtk.Button.__init__(self, ln.xchat_install)      
      self.connect("clicked", self.cb_install)
      self.set_border_width(3)
      self.home = os.environ["HOME"]
      self.check_plugin()

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

class ReconnectionDialogConfig(gtk.Frame):
   """Prefereneces for reconnection"""
   def lj(self, widget, indent = 0):
      hbox = gtk.HBox()
      hbox.pack_start(widget, False, False, indent)
      hbox.show_all()
      return hbox
   def __init__(self):
      gtk.Frame.__init__(self, " " + ln.rdc_title + " ")
      vbox = gtk.VBox()
      vbox.set_border_width(8)
      vbox.set_spacing(3)
      self.add(vbox)
      vbox.show()
      
      label = gtk.Label(ln.rdc_autoreconnecthas)
      vbox.add(self.lj(label))
      
      self.limited_delays = gtk.RadioButton(None, ln.rdc_delaysof)
      self.csl = CSLEntry()
      self.csl.set_text("10,10,60")
      l1 = gtk.Label(ln.rdc_seconds)
      line = gtk.HBox()
      line.pack_start(self.limited_delays, False, False, 0)
      line.pack_start(self.csl, True, True, 0)
      line.pack_start(l1, False, False, 0)
      vbox.add(self.lj(line, 20))
      self.unlimited_retries = gtk.RadioButton(self.limited_delays, ln.rdc_unlimited)
      vbox.add(self.lj(self.unlimited_retries, 20))
      self.visible = gtk.CheckButton(ln.rdc_visible)
      self.visible.set_active(True)
      vbox.add(self.lj(self.visible))
      sep = gtk.HSeparator()
      vbox.add(sep)
      sep.show()
      l2 = gtk.Label(ln.rdc_whenstreambufferfull)
      vbox.add(self.lj(l2))
      self.discard_data = gtk.RadioButton(None, ln.rdc_discard_data)
      self.attempt_reconnection = gtk.RadioButton(self.discard_data, ln.rdc_attempt_reconnection)
      vbox.add(self.lj(self.discard_data, 20))
      vbox.add(self.lj(self.attempt_reconnection, 20))
   
class AGCControl(gtk.Frame):
   def sendnewstats(self, widget, wname):
      if isinstance(widget, (gtk.SpinButton, gtk.Scale)):
         value = widget.get_value()
      if isinstance(widget, (gtk.CheckButton, gtk.ComboBox)):
         value = (0, 1)[widget.get_active()]
      stringtosend = "INDX=%d\nAGCP=%s=%s\nACTN=%s\nend\n" % (self.index, wname, str(value), "mic_control")
      self.approot.mixer_write(stringtosend, True)

   def set_partner(self, partner):
      self.partner = partner

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

   def widget_frame(self, widget, container, tip):
      frame = gtk.Frame()
      self.approot.tooltips.set_tip(frame, tip)
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

   def cb_active(self, widget):
      sens = widget.get_active()
      for each in (self.vbox, self.meter):
          each.set_sensitive(sens)
      if not sens:
          self.open.set_active(False)
          
   def cb_open(self, widget):
      active = widget.get_active()
      self.meter.set_led(active)
      self.status_led.set_from_pixbuf(self.status_on_pb if active else self.status_off_pb)

   def cb_pan_middle(self, button):
      self.pan.set_value(50)

   def cb_complexity(self, combobox):
      if combobox.get_active():
         self.processed_box.show()
         self.simple_box.hide()
      else:
         self.processed_box.hide()
         self.simple_box.show()
         
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
      set_tip = approot.tooltips.set_tip
      hbox = gtk.HBox()
      self.active = gtk.CheckButton(ui_name)
      set_tip(self.active, ln.agc_active_tip)
      self.active.connect("toggled", self.cb_active)
      self.active.connect("toggled", self.sendnewstats, "active")
      self.booleandict[self.commandname + "_active"] = self.active
      hbox.pack_start(self.active, False, False)
      self.active.show()
 
      self.alt_name = gtk.Entry()
      set_tip(self.alt_name, ln.alt_mic_name)
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

      self.complexity = gtk.combo_box_new_text()
      self.vbox.pack_start(self.complexity, False, False)
      self.complexity.append_text(ln.mic_simple)
      self.complexity.append_text(ln.mic_processed)
      self.complexity.connect("changed", self.sendnewstats, "complexity")
      self.complexity.emit("changed")
      self.complexity.connect("changed", self.cb_complexity)
      self.booleandict[self.commandname + "_complexity"] = self.complexity
      self.complexity.show()
      set_tip(self.complexity, ln.mic_complexity_tip)

      hbox = gtk.HBox()
      label = gtk.Label(ln.open_mic)
      hbox.pack_start(label, False, False, 3)
      label.show()
      self.status_led = gtk.Image()
      hbox.pack_start(self.status_led, False, False, 3)
      self.status_led.show()
      ivbox = self.widget_frame(hbox, self.vbox, ln.open_unmute_tip)
      hbox.show()
      self.status_off_pb = gtk.gdk.pixbuf_new_from_file_at_size(pkgdatadir + "led_unlit_clear_border_64x64" + gfext, 12, 12)
      self.status_on_pb = gtk.gdk.pixbuf_new_from_file_at_size(pkgdatadir + "led_lit_green_black_border_64x64" + gfext, 12, 12)
      self.status_led.set_from_pixbuf(self.status_off_pb)
            
      hbox = gtk.HBox()
      self.group = gtk.CheckButton(ln.group)
      self.booleandict[self.commandname + "_group"] = self.group
      hbox.pack_start(self.group, False, False, 0)
      self.group.show()
      ivbox.pack_start(hbox, False, False)
      hbox.show()
      
      self.groups_adj = gtk.Adjustment(1.0, 1.0, idjc_config.num_micpairs, 1.0)
      self.valuesdict[self.commandname + "_groupnum"] = self.groups_adj
      groups_spin = gtk.SpinButton(self.groups_adj, 0.0, 0)
      hbox.pack_end(groups_spin, False)
      groups_spin.show()

      self.autoopen = gtk.CheckButton(ln.autoopen)
      ivbox.pack_start(self.autoopen, False, False)
      self.autoopen.show()
      set_tip(self.autoopen, ln.autoopen_tip)
      self.booleandict[self.commandname + "_autoopen"] = self.autoopen

      sizegroup = gtk.SizeGroup(gtk.SIZE_GROUP_HORIZONTAL)
      panframe = gtk.Frame()
      set_tip(panframe, ln.pan_tip)
      
      hbox = gtk.HBox()
      self.pan_active = gtk.CheckButton(ln.pan)
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
      l = gtk.Label(ln.l)
      sizegroup.add_widget(l)
      panhbox.pack_start(l, False, False)
      panadj = gtk.Adjustment(50.0, 0.0, 100.0, 1, 10)
      self.pan = gtk.HScale(panadj)
      self.pan.set_draw_value(False)
      self.pan.connect("value-changed", self.sendnewstats, "pan")
      self.pan.emit("value-changed")
      self.valuesdict[self.commandname + "_pan"] = self.pan
      panhbox.pack_start(self.pan)
      r = gtk.Label(ln.r)
      sizegroup.add_widget(r)
      panhbox.pack_start(r, False, False)
      pancenterbox = gtk.HBox()
      pancenter = gtk.Button()
      pancenter.connect("clicked", self.cb_pan_middle)
      pancenterbox.pack_start(pancenter, True, False)
      panvbox.pack_start(pancenterbox, False, False)
      self.vbox.pack_start(panframe, False, False)
      panframe.show_all()

      micgainadj = gtk.Adjustment(5.0, -20.0, +30.0, 0.1, 2)
      openaction = gtk.ToggleAction("open", ln.open_mic, ln.open_mic_tip, None)
      invertaction = gtk.ToggleAction("invert", ln.invert_mic, ln.invert_mic_tip, None)
      indjmixaction = gtk.ToggleAction("indjmix", ln.in_dj_mix, ln.in_dj_mix_tip, None)

      self.simple_box = gtk.VBox()
      self.simple_box.set_spacing(2)
      self.vbox.pack_start(self.simple_box, False, False)

      ivbox = self.frame(" " + ln.basic_controls + " ", self.simple_box)
      micgain = self.numline(ln.agc_boost, "gain", digits=1, adj=micgainadj)
      ivbox.pack_start(micgain, False, False)
      
      self.open = self.check("", "open", save=False)
      openaction.connect_proxy(self.open)
      self.open.connect("toggled", self.cb_open)
      #ivbox.pack_start(self.open, False, False)
      #set_tip(self.open, ln.open_mic_tip)
      
      invert_simple = self.check("", "invert")
      invertaction.connect_proxy(invert_simple)
      ivbox.pack_start(invert_simple, False, False)
      set_tip(invert_simple, ln.invert_mic_tip)
      
      indjmix = self.check("", "indjmix")
      indjmixaction.connect_proxy(indjmix)
      ivbox.pack_start(indjmix, False, False)
      set_tip(indjmix, ln.in_dj_mix_tip)

      self.processed_box = gtk.VBox()
      self.processed_box.set_spacing(2)
      self.vbox.pack_start(self.processed_box, False, False)

      ivbox = self.frame(" " + ln.agc_highpass + " ", self.processed_box)
      hpcutoff = self.numline(ln.agc_cutoff, "hpcutoff", 100.0, 30.0, 120.0, 1.0, 1)
      ivbox.pack_start(hpcutoff, False, False, 0)
      hpstages = self.numline(ln.agc_cutoff_stages, "hpstages", 4.0, 1.0, 4.0, 1.0, 0)
      ivbox.pack_start(hpstages, False, False, 0)
      set_tip(ivbox, ln.agc_hpcutoff_tip)
      
      ivbox = self.frame(" " + ln.agc_hfdetail + " ", self.processed_box)
      hfmulti = self.numline(ln.agc_hfmulti, "hfmulti", 0.0, 0.0, 9.0, 0.1, 1)
      ivbox.pack_start(hfmulti, False, False, 0)
      hfcutoff = self.numline(ln.agc_cutoff, "hfcutoff", 2000.0, 900.0, 4000.0, 10.0, 0)
      ivbox.pack_start(hfcutoff, False, False, 0)
      set_tip(ivbox, ln.agc_hfdetail_tip)
       
      ivbox = self.frame(" " + ln.agc_lfdetail + " ", self.processed_box)
      lfmulti = self.numline(ln.agc_lfmulti, "lfmulti", 0.0, 0.0, 9.0, 0.1, 1)
      ivbox.pack_start(lfmulti, False, False, 0)
      lfcutoff = self.numline(ln.agc_cutoff, "lfcutoff", 150.0, 50.0, 400.0, 1.0, 0)
      ivbox.pack_start(lfcutoff, False, False, 0)
      set_tip(ivbox, ln.agc_lfdetail_tip)
      
      ivbox = self.frame(" " + ln.agc_compressor + " ", self.processed_box)
      micgain = self.numline(ln.agc_boost, "gain", digits=1, adj=micgainadj)
      ivbox.pack_start(micgain, False, False, 0)
      limit = self.numline(ln.agc_limit, "limit", -3.0, -9.0, 0.0, 0.5, 1)
      ivbox.pack_start(limit, False, False, 0)
      set_tip(ivbox, ln.agc_compressor_tip)
      
      ivbox = self.frame(" " + ln.agc_noisegate + " ", self.processed_box)
      ng_thresh = self.numline(ln.agc_ngthresh, "ngthresh", -30.0, -62.0, -20.0, 1.0, 0)
      ivbox.pack_start(ng_thresh, False, False, 0)
      ng_gain = self.numline(ln.agc_gain, "nggain", -6.0, -12.0, 0.0, 1.0, 0)
      ivbox.pack_start(ng_gain, False, False, 0)
      set_tip(ivbox, ln.agc_noisegate_tip)
      
      ivbox = self.frame(" " + ln.agc_deesser + " ", self.processed_box)
      ds_bias = self.numline(ln.agc_deessbias, "deessbias", 0.35, 0.1, 10.0, 0.05, 2)
      ivbox.pack_start(ds_bias, False, False, 0)
      ds_gain = self.numline(ln.agc_gain, "deessgain", -4.5, -10.0, 0.0, 0.5, 1)
      ivbox.pack_start(ds_gain, False, False, 0)
      set_tip(ivbox, ln.agc_deesser_tip)
      
      ivbox = self.toggle_frame(ln.agc_ducker, "duckenable", self.processed_box)
      duckrelease = self.numline(ln.agc_duckrelease, "duckrelease", 400.0, 100.0, 999.0, 10.0, 0)
      ivbox.pack_start(duckrelease, False, False, 0)
      duckhold = self.numline(ln.agc_duckhold, "duckhold", 350.0, 0.0, 999.0, 10.0, 0)
      ivbox.pack_start(duckhold, False, False, 0)
      set_tip(ivbox, ln.agc_ducker_tip)
       
      ivbox = self.frame(" " + ln.agc_other_options + " ", self.processed_box)

      open_complex = self.check("", "open2", save=False)
      openaction.connect_proxy(open_complex)
      #ivbox.pack_start(open_complex, False, False)
      #set_tip(open_complex, ln.open_mic_tip)
      invert_complex = self.check("", "invert2")
      invertaction.connect_proxy(invert_complex)
      ivbox.pack_start(invert_complex, False, False)
      set_tip(invert_complex, ln.invert_mic_tip)
      phaserotate = self.check(ln.agc_phaserotator, "phaserotate")
      ivbox.pack_start(phaserotate, False, False, 0)
      set_tip(phaserotate, ln.agc_phaserotator_tip)
      indjmix = self.check("", "indjmix2")
      indjmixaction.connect_proxy(indjmix)
      ivbox.pack_start(indjmix, False, False)
      set_tip(indjmix, ln.in_dj_mix_tip)

      self.complexity.set_active(1)
      indjmix.set_active(True)
      self.partner = None
      self.active.emit("toggled")

mIRC_colours = (                # Actually these are the XChat2 colours.
   (0xCCCCCCFF, "00"),          # XChat2 calls them mIRC colours, but I doubt they match.
   (0x000000FF, "01"),
   (0x3636B2FF, "02"),
   (0x2A8C2AFF, "03"),
   (0xC33B3BFF, "04"),
   (0xC73232FF, "05"),
   (0x80267FFF, "06"),
   (0x66361FFF, "07"),
   (0xD9A641FF, "08"),
   (0x3DCC3DFF, "09"),
   (0x1A5555FF, "10"),
   (0x2F8C74FF, "11"),
   (0x4545E6FF, "12"),
   (0xB037B0FF, "13"),
   (0x4C4C4CFF, "14"),
   (0x959595FF, "15"),
   (0x00000000, "99"))          # used to restore default colours

def cb_colour_box_expose(widget, event, data=None):
   widget.set_state(gtk.STATE_NORMAL)   # Prevent pre-light from messing up the colour

def make_colour_box(rgba, label_text, width, height):
   pixbuf = gtk.gdk.Pixbuf(gtk.gdk.COLORSPACE_RGB, True, 8, width, height)
   pixbuf.fill(rgba)
   image = gtk.Image()
   image.connect_after("expose-event", cb_colour_box_expose)
   image.set_from_pixbuf(pixbuf)
   image.show()
   label = gtk.Label(label_text)
   label.show()
   hbox = gtk.HBox()
   hbox.set_spacing(15)
   hbox.pack_start(label, False, False, 0)
   hbox.pack_end(image, False, False, 0)
   hbox.show()
   return hbox

def make_colour_box_menu(entry, callback):
   menu = gtk.Menu()
   for each in mIRC_colours:
      menuitem = gtk.MenuItem()
      menuitem.connect("activate", callback, entry, each[1])
      colourbox = make_colour_box(each[0], each[1], 45, 28)
      menuitem.add(colourbox)
      menu.add(menuitem)
      menuitem.show()
   menu.show()
   return menu

def make_entry_line(parent, item, code, hastoggle, index=None):
   box = gtk.HBox(False, 0)
   box.set_border_width(4)
   box.set_spacing(5)

   entry = gtk.Entry(128)
   entry.set_size_request(185, -1)

   savebutton = gtk.Button(ln.save)
   savebutton.connect("clicked", parent.save_click, (code, entry, index))
   box.pack_end(savebutton, False, False, 0)
   savebutton.show()

   setbutton = gtk.Button(ln.set)
   setbutton.connect("clicked", parent.update_click, (code, entry, index))
   box.pack_end(setbutton, False, False, 0)
   setbutton.show()

   if hastoggle:
      entry.set_sensitive(False)
   box.pack_end(entry, False, False, 0)
   entry.show()

   checkbox = gtk.CheckButton(ln.auto)
   box.pack_end(checkbox, False, False, 0)
   if hastoggle:
      checkbox.set_active(True)
      checkbox.connect("toggled", parent.auto_click, entry)
      checkbox.show()
      
   label = gtk.Label(item)
   box.pack_start(label, False, False, 0)
   label.show()
      
   box.show()
   
   parent.parent.tooltips.set_tip(checkbox, ln.auto_tip)
   parent.parent.tooltips.set_tip(setbutton, ln.set_tip)
   parent.parent.tooltips.set_tip(savebutton, ln.save_tip)
   parent.parent.tooltips.set_tip(entry, ln.jack_entry)
   
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
      def __init__(self, imagefile, width, height, text, default_state, crossout, tips = None, checkbutton_tip = None, entry_tip = None):
         gtk.HBox.__init__(self)
         gtk.HBox.set_spacing(self, 6)
         self.checkbutton = gtk.CheckButton()
         self.checkbutton.set_active(default_state)
         image = gtk.Image()
         if crossout:
            pixbuf = gtk.gdk.pixbuf_new_from_file_at_size(pkgdatadir + "crossout" + gfext, width , height)
         else:
            pixbuf = gtk.gdk.pixbuf_new_from_file_at_size(pkgdatadir + imagefile + gfext, width, height)
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
         if tips is not None:
            if checkbutton_tip is not None:
               tips.set_tip(self.checkbutton, checkbutton_tip)
            if entry_tip is not None:
               tips.set_tip(self.entry, entry_tip)
   
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
      self.left_player_frame.set_sensitive(state)
      self.right_player_frame.set_sensitive(state)
      self.misc_session_frame.set_sensitive(state)
   
   jack_ports= ("audl", "audr", "strl", "strr", "auxl", "auxr", "midi", "dol", "dor", "dil", "dir")

   def load_jack_port_settings(self):
      for port in self.jack_ports:
         if os.path.isfile(self.parent.idjc + port):
            file = open(self.parent.idjc + port, "r")
            getattr(self, port+"entry").set_text(file.readline()[:-1])
            getattr(self, port+"check").set_active(file.readline() == "1\n")
            file.close()
            
      for i, mic in enumerate(self.mic_jack_data):
         pathname = self.parent.idjc + "mic" + str(i + 1)
         if os.path.isfile(pathname):
            file = open(pathname, "r")
            mic[1].set_text(file.readline()[:-1])
            mic[0].set_active(file.readline() == "1\n")
   
   def auto_click(self, widget, data):
      data.set_sensitive(not widget.get_active())
   
   def save_click(self, widget, data):
      filename = self.parent.idjc + data[0].lower()
      if data[2] is not None:
         filename += str(data[2] + 1)
      file = open(filename, "w")
      if data[1].flags() & gtk.SENSITIVE:
         file.write(data[1].get_text() + "\n" + "0\n")
      else:
         file.write(data[1].get_text() + "\n" + "1\n")
      file.close()
   
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
         file = open(self.parent.idjc + "playerdefaults", "w")
         for name, widget in self.playersettingsdict.iteritems():
            file.write(name + ("=False\n","=True\n")[widget.get_active()])
         for name, widget in self.valuesdict.iteritems():
            file.write(name + "=" + str(widget.get_value()) + "\n")
         for name, widget in self.textdict.iteritems():
            file.write(name + "=" + widget.get_text() + "\n")
         file.close()
      except IOError:
         print "Error while writing out player defaults"
      try:
         file = open(self.parent.idjc + "config", "w")
         file.write("[resource_count]\n")
         for name, widget in self.rrvaluesdict.iteritems():
            file.write(name + "=" + str(int(widget.get_value())) + "\n")
         file.close()
      except IOError:
         print "Error while writing out player defaults"
      if self.ask_profile.get_active():
         if os.path.isfile(self.parent.idjcroot + "do-not-ask-profile"):
            try:
               os.unlink(self.parent.idjcroot + "do-not-ask-profile")
            except:
               print "error removing file 'do-not-ask-profile'"
      else:
         try:
            if not os.path.isfile(self.parent.idjcroot + "do-not-ask-profile"):
               os.mknod(self.parent.idjcroot + "do-not-ask-profile")
         except:
            print "error creating file 'do-not-ask-profile'"
         
   def load_player_prefs(self):
      proktogglevalue = False
      try:
         file = open(self.parent.idjc + "playerdefaults", "r")
         
         while 1:
            line = file.readline()
            if line == "":
               break
            if line.count("=") != 1:
               continue
            line = line.split("=")
            key = line[0].strip()
            value = line[1][:-1].strip()
            if value == "True":
               value = True
            elif value == "False":
               value = False
            if self.playersettingsdict.has_key(key):
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
      left = self.parent.player_left
      right = self.parent.player_right
      
      if self.lplayall.get_active():
         left.pl_mode.set_active(0)
      if self.lloopall.get_active():
         left.pl_mode.set_active(1)
      if self.lrandom.get_active():
         left.pl_mode.set_active(2)
      if self.lmanual.get_active():
         left.pl_mode.set_active(3)
      if self.lcueup.get_active():
         left.pl_mode.set_active(4)
                 
      if self.rplayall.get_active():
         right.pl_mode.set_active(0)
      if self.rloopall.get_active():
         right.pl_mode.set_active(1)
      if self.rrandom.get_active():
         right.pl_mode.set_active(2)
      if self.rmanual.get_active():
         right.pl_mode.set_active(3)
      if self.rcueup.get_active():
         right.pl_mode.set_active(4)

      left.stream.set_active(self.lstream.get_active())
      right.stream.set_active(self.rstream.get_active())
      
      left.listen.set_active(self.llisten.get_active())
      right.listen.set_active(self.rlisten.get_active())
      
      if self.lcountdown.get_active():
         left.digiprogress_click()
      if self.rcountdown.get_active():
         right.digiprogress_click()
         
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
            parent.tooltips.enable()
         else:
            parent.tooltips.disable()
            
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
                    
   def cb_colourbox(self, menuitem, entry, colour):
      cursor = entry.get_position()
      if cursor < 3 or entry.get_text()[cursor - 3] !="\x03":
         entry.insert_text("\x03" + colour, cursor)     # Foreground colour
      else:
         entry.insert_text("," + colour, cursor)        # Background
      entry.set_position(cursor + 3)

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
         self.parent.tooltips.set_tip(self.parent.deckvol, ln.left_volume_control_tip)
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
         self.parent.tooltips.set_tip(self.parent.deckvol, ln.common_volume_control_tip)

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

   def colourmenupopulate(self, entry, menu):
      menusep = gtk.SeparatorMenuItem()
      menu.append(menusep)
      menusep.show()
      menuitem = gtk.MenuItem(ln.mirc_colour_menu)
      menu.append(menuitem)
      submenu = make_colour_box_menu(entry, self.cb_colourbox)
      menuitem.set_submenu(submenu)
      menuitem.show()
      
   def cb_handle_colour_char(self, entry, event, data=None):
      if event.state & gtk.gdk.LOCK_MASK:
         target = 75
      else:
         target = 107
      if event.state & (~gtk.gdk.LOCK_MASK) == gtk.gdk.CONTROL_MASK and event.keyval == target:
         cursor = entry.get_position()
         entry.insert_text("\x03", cursor)
         entry.set_position(cursor + 1)

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
      
   def cb_configure_event(self, window, event):
         self.winx.set_value(event.width)
         self.winy.set_value(event.height)
         
   def cb_realize(self, window):
      window.resize(self.winx, self.winy)
         
   def __init__(self, parent):
      self.parent = parent
      self.parent.prefs_window = self
      self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
      self.window.set_size_request(-1, 480)
      self.winx = int_object(1)
      self.winy = int_object(1)      
      self.window.connect("configure-event", self.cb_configure_event)
      self.window.connect("realize", self.cb_realize)
      self.parent.window_group.add_window(self.window)
      self.window.set_title(ln.prefs_window + parent.profile_title)
      self.window.set_border_width(10)
      self.window.set_resizable(True)
      self.window.connect("delete_event",self.delete_event)
      self.window.set_destroy_with_parent(True)
      self.window.set_icon_from_file(pkgdatadir + "icon" + gfext)
      self.notebook = gtk.Notebook()
      self.window.add(self.notebook)

      # General tab
      
      generalwindow = gtk.ScrolledWindow()
      generalwindow.set_border_width(8)
      generalwindow.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
      outervbox = gtk.VBox()
      outervbox.set_spacing(5)
      generalwindow.add_with_viewport(outervbox)
      generalwindow.show()
      outervbox.set_border_width(3)
      
      featuresframe = gtk.Frame(" " + ln.feature_set + " ")
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
      self.startfull = gtk.RadioButton(None, ln.start_full)
      self.startfull.set_border_width(2)
      vbox.pack_start(self.startfull, False, False, 0)
      self.startfull.show()
      parent.tooltips.set_tip(self.startfull, ln.start_mini_full)
      
      self.startmini = gtk.RadioButton(self.startfull, ln.start_mini)
      self.startmini.set_border_width(2)
      vbox.pack_start(self.startmini, False, False, 0)
      self.startmini.show()
      parent.tooltips.set_tip(self.startmini, ln.start_mini_full)
      
      vbox.show()
      hbox2 = gtk.HBox()
      hbox2.set_border_width(10)
      hbox2.set_spacing(20)
      hbox.pack_start(hbox2, True, False, 0)
      
      self.maxi = gtk.Button(" " + ln.fully_featured + " ")
      self.maxi.connect("clicked", self.callback, "fully featured")
      hbox2.pack_start(self.maxi, False, False, 0)
      self.maxi.show()
      parent.tooltips.set_tip(self.maxi, ln.fully_featured_tip)
      
      self.mini = gtk.Button(" " + ln.basic_streamer + " ")
      self.mini.connect("clicked", self.callback, "basic streamer")
      hbox2.pack_start(self.mini, False, False, 0)
      self.mini.show()
      parent.tooltips.set_tip(self.mini, ln.basic_streamer_tip)
      
      hbox2.show()   
      hbox.pack_start(vbox, False, False, 9)     
      hbox.show()
      
      requires_restart = gtk.Frame(ln.requires_restart)
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

      self.mic_qty_adj = gtk.Adjustment(idjc_config.num_micpairs * 2, 2.0, 12.0, 2.0)
      spin = gtk.SpinButton(self.mic_qty_adj)
      rrvbox.pack_start(hjoin(spin, gtk.Label(ln.n_microphones)))
   
      self.stream_qty_adj = gtk.Adjustment(idjc_config.num_streamers, 1.0, 9.0, 1.0)
      spin = gtk.SpinButton(self.stream_qty_adj)
      rrvbox.pack_start(hjoin(spin, gtk.Label(ln.n_streamers)))

      self.recorder_qty_adj = gtk.Adjustment(idjc_config.num_recorders, 0.0, 4.0, 1.0)
      spin = gtk.SpinButton(self.recorder_qty_adj)
      rrvbox.pack_start(hjoin(spin, gtk.Label(ln.n_recorders)))
      
      key_label = gtk.Label(ln.n_feature_set_asterisk)
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
      frame = gtk.Frame(" " + ln.audio_meters + " ")
      frame.set_border_width(3)
      vbox = gtk.VBox()
      vbox.set_border_width(10)
      frame.add(vbox)
      vbox.show()
      self.show_stream_meters = gtk.CheckButton(ln.show_stream_meters)
      self.show_stream_meters.set_active(True)
      self.show_stream_meters.connect("toggled", showhide, parent.streammeterbox)
      parent.str_meters_action.connect_proxy(self.show_stream_meters)
      vbox.pack_start(self.show_stream_meters, False, False)
      self.show_stream_meters.show()
      
      hbox = gtk.HBox()
      vbox.pack_start(hbox, False, False)
      hbox.show()
      self.show_microphones = gtk.CheckButton(ln.show_microphone_meters)
      self.show_microphones.set_active(True)
      self.show_microphones.connect("toggled", showhide, parent.micmeterbox)
      parent.mic_meters_action.connect_proxy(self.show_microphones)
      hbox.pack_start(self.show_microphones, False, False)
      self.show_microphones.show()            
      
      self.show_all_microphones = gtk.RadioButton(None, ln.all)
      for meter in parent.mic_meters:
         self.show_all_microphones.connect("toggled", meter.always_show)
      hbox.pack_start(self.show_all_microphones, False, False)
      self.show_all_microphones.show()
      
      self.show_active_microphones = gtk.RadioButton(self.show_all_microphones, ln.those_active)
      hbox.pack_start(self.show_active_microphones, False, False)
      self.show_active_microphones.show()
      
      outervbox.pack_start(frame, False, False, 0)
      frame.show()
      
      # Replay Gain controls
      
      frame = gtk.Frame(" " + ln.rg_title + " ")
      frame.set_border_width(3)
      outervbox.pack_start(frame, False, False, 0)
      vbox = gtk.VBox()
      frame.add(vbox)
      frame.show()
      vbox.set_border_width(10)
      vbox.set_spacing(1)
      vbox.show()
      
      self.rg_indicate = gtk.CheckButton(ln.rg_indicate)
      parent.tooltips.set_tip(self.rg_indicate, ln.rg_indicate_tip)
      self.rg_indicate.connect("toggled", self.cb_rg_indicate)
      vbox.pack_start(self.rg_indicate, False, False, 0)
      self.rg_indicate.show()
      
      self.rg_adjust = gtk.CheckButton(ln.rg_adjust)
      parent.tooltips.set_tip(self.rg_adjust, ln.rg_adjust_tip)
      vbox.pack_start(self.rg_adjust, False, False, 0)
      self.rg_adjust.show()
      
      hbox = gtk.HBox()
      hbox.set_spacing(3)
      spacer = gtk.HBox()
      hbox.pack_start(spacer, False, False, 16)
      spacer.show()
      label = gtk.Label(ln.rg_defaultgain)
      hbox.pack_start(label, False, False, 0)
      label.show()
      rg_defaultgainadj = gtk.Adjustment(-8.0, -20.0, 10.0, 0.1)
      self.rg_defaultgain = gtk.SpinButton(rg_defaultgainadj, 0.0, 1)
      parent.tooltips.set_tip(hbox, ln.rg_defaultgain_tip)
      hbox.pack_start(self.rg_defaultgain, False, False, 0)
      self.rg_defaultgain.show()
      vbox.pack_start(hbox, False, False, 0)
      hbox.show()

      hbox = gtk.HBox()
      hbox.set_spacing(3)
      spacer = gtk.HBox()
      hbox.pack_start(spacer, False, False, 16)
      spacer.show()
      label = gtk.Label(ln.rg_boost)
      hbox.pack_start(label, False, False, 0)
      label.show()
      rg_boostadj = gtk.Adjustment(6.0, -5.0, 15.5, 0.5)
      self.rg_boost = gtk.SpinButton(rg_boostadj, 0.0, 1)
      parent.tooltips.set_tip(hbox, ln.rg_boost_tip)
      hbox.pack_start(self.rg_boost, False, False, 0)
      self.rg_boost.show()
      vbox.pack_start(hbox, False, False, 0)
      hbox.show()

      # Miscellaneous Features
      
      frame = gtk.Frame(" " + ln.misc_features + " ")
      frame.set_border_width(3)
      vbox = gtk.VBox()
      frame.add(vbox)
      frame.show()
      vbox.set_border_width(10)
      vbox.set_spacing(1)
      
      self.silence_killer = gtk.CheckButton(ln.silence_killer)
      self.silence_killer.set_active(True)
      vbox.pack_start(self.silence_killer, False, False, 0)
      self.silence_killer.show()
      
      self.bonus_killer = gtk.CheckButton(ln.bonus_killer)
      self.bonus_killer.set_active(True)
      vbox.pack_start(self.bonus_killer, False, False, 0)
      self.bonus_killer.show()
      
      self.twodblimit = gtk.CheckButton(ln.twodblimit)
      vbox.pack_start(self.twodblimit, False, False, 0)
      self.twodblimit.connect("toggled", self.cb_twodblimit)
      self.twodblimit.show()
      parent.tooltips.set_tip(self.twodblimit, ln.twodblimit_tip)
      
      self.speed_variance = gtk.CheckButton(ln.speed_variance)
      vbox.pack_start(self.speed_variance, False, False, 0)
      self.speed_variance.connect("toggled", self.cb_pbspeed)
      self.speed_variance.show()
      parent.tooltips.set_tip(self.speed_variance, ln.player_speed_tip)

      self.dual_volume = gtk.CheckButton(ln.dual_volume)
      vbox.pack_start(self.dual_volume, False, False, 0)
      self.dual_volume.connect("toggled", self.cb_dual_volume)
      self.dual_volume.show()
      parent.tooltips.set_tip(self.dual_volume, ln.dual_volume_tip)

      self.ask_profile = gtk.CheckButton(ln.ask_profile)
      vbox.pack_start(self.ask_profile, False, False, 0)
      self.ask_profile.show()
      parent.tooltips.set_tip(self.ask_profile, ln.ask_profile_tip)
      
      self.bigger_box_toggle = gtk.CheckButton(ln.big_box_toggle)
      vbox.pack_start(self.bigger_box_toggle, False, False, 0)
      self.bigger_box_toggle.connect("toggled", self.callback, "bigger box")
      self.bigger_box_toggle.show()
      parent.tooltips.set_tip(self.bigger_box_toggle, ln.enlarge_time_elapsed_tip)
      
      self.djalarm = gtk.CheckButton(ln.dj_alarm_toggle)
      vbox.pack_start(self.djalarm, False, False, 0)
      self.djalarm.show()
      parent.tooltips.set_tip(self.djalarm, ln.dj_alarm_tip)
      
      self.dither = gtk.CheckButton(ln.dither_toggle)
      vbox.pack_start(self.dither, False, False, 0)
      self.dither.connect("toggled", self.cb_dither)
      self.dither.show()
      parent.tooltips.set_tip(self.dither, ln.dither_tip)

      self.mp3_utf8 = gtk.CheckButton(ln.mp3_utf8)
      self.mp3_utf8.set_active(True)
      vbox.pack_start(self.mp3_utf8, False, False, 0)
      self.mp3_utf8.show()
      parent.tooltips.set_tip(self.mp3_utf8, ln.mp3_utf8_tip)
      
      self.mic_aux_mutex = gtk.CheckButton(ln.mic_aux_mutex)
      vbox.pack_start(self.mic_aux_mutex, False, False, 0)
      self.mic_aux_mutex.show()
      parent.tooltips.set_tip(self.mic_aux_mutex, ln.mic_aux_mutex_tip)
      
      self.enable_tooltips = gtk.CheckButton(ln.enable_tooltips)
      self.enable_tooltips.connect("toggled", self.callback, "tooltips")
      vbox.pack_start(self.enable_tooltips, False, False, 0)
      self.enable_tooltips.show()
      parent.tooltips.set_tip(self.enable_tooltips, ln.enable_tooltips_tip)
      
      vbox.show()

      outervbox.pack_start(frame, False, False, 0)
      
      # Reconnection dialog config
      
      self.recon_config = ReconnectionDialogConfig()
      self.recon_config.set_border_width(3)
      parent.tooltips.set_tip(self.recon_config, ln.recon_tip)
      outervbox.pack_start(self.recon_config, False, False, 0)
      self.recon_config.show()
      
      # Stream normalizer config
      
      frametitlebox = gtk.HBox()
      self.normalize = gtk.CheckButton(ln.stream_normalizer)
      self.normalize.connect("toggled", self.cb_normalizer)
      frametitlebox.pack_start(self.normalize, True, False, 2)
      parent.tooltips.set_tip(self.normalize, ln.enable_stream_normalizer_tip)
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
      label = gtk.Label(ln.normboost)
      boostbox.pack_start(label, False, False, 0)
      label.show()
      lvbox.add(boostbox)
      boostbox.show()
      parent.tooltips.set_tip(normboost, ln.settings_warning_tip)
      
      ceilingbox = gtk.HBox()
      ceilingbox.set_spacing(3)
      self.normceiling_adj = gtk.Adjustment(-12.0, -25.0, 0.0, 0.1, 0.2)
      normceiling = gtk.SpinButton(self.normceiling_adj, 1, 1)
      normceiling.connect("value-changed", self.cb_normalizer)
      sizegroup.add_widget(normceiling)
      ceilingbox.pack_start(normceiling, False, False, 0)
      normceiling.show()
      label = gtk.Label(ln.normceiling)
      ceilingbox.pack_start(label, False, False, 0)
      label.show()
      lvbox.add(ceilingbox)
      ceilingbox.show()
      parent.tooltips.set_tip(normceiling, ln.settings_warning_tip)
      
      defaultsbox = gtk.HBox()
      self.normdefaults = gtk.Button(ln.normdefaults)
      self.normdefaults.connect("clicked", self.normalizer_defaults)
      defaultsbox.pack_start(self.normdefaults, True, True, 0)
      self.normdefaults.show()
      mvbox.pack_start(defaultsbox, True, False, 0)
      defaultsbox.show()
      parent.tooltips.set_tip(self.normdefaults, ln.default_normalizer_tip)
      
      sizegroup = gtk.SizeGroup(gtk.SIZE_GROUP_HORIZONTAL)
      
      risebox = gtk.HBox()
      risebox.set_spacing(3)
      self.normrise_adj = gtk.Adjustment(2.7, 0.1, 5.0, 0.1, 1.0)
      normrise = gtk.SpinButton(self.normrise_adj, 1, 1)
      normrise.connect("value-changed", self.cb_normalizer)
      sizegroup.add_widget(normrise)
      risebox.pack_start(normrise, False, False, 0)
      normrise.show()
      label = gtk.Label(ln.normrise)
      risebox.pack_start(label, False, False, 0)
      label.show()
      rvbox.add(risebox)
      risebox.show()
      parent.tooltips.set_tip(normrise, ln.settings_warning_tip)
      
      fallbox = gtk.HBox()
      fallbox.set_spacing(3)
      self.normfall_adj = gtk.Adjustment(2.0, 0.1, 5.0, 0.1, 1.0)
      normfall = gtk.SpinButton(self.normfall_adj, 1, 1)
      normfall.connect("value-changed", self.cb_normalizer)
      sizegroup.add_widget(normfall)
      fallbox.pack_start(normfall, False, False, 0)
      normfall.show()
      label = gtk.Label(ln.normfall)
      fallbox.pack_start(label, False, False, 0)
      label.show()
      rvbox.add(fallbox)
      fallbox.show()
      parent.tooltips.set_tip(normfall, ln.settings_warning_tip)
      
      aud_rs_hbox = gtk.HBox()
      
      # User can use this to set the audio level in the headphones
      
      frame = gtk.Frame(" " + ln.dj_audio_level + " ")
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
      parent.tooltips.set_tip(dj_aud, ln.dj_audio_tip)
      
      aud_rs_hbox.pack_start(frame, False, False, 0)
      frame.show()
      
      # User can use this to set the resampled sound quality
      
      frame = gtk.Frame(" " + ln.player_resample_mode + " ")
      frame.set_label_align(0.5, 0.5)
      frame.set_border_width(3)
      hbox = gtk.HBox()
      hbox.set_border_width(5)
      frame.add(hbox)
      hbox.show()
      self.best_quality_resample = gtk.RadioButton(None, ln.best_quality_resample)
      self.best_quality_resample.connect("toggled", self.cb_resample_quality, 0)
      rsbox = gtk.HBox()
      rsbox.pack_start(self.best_quality_resample, True, False, 0)
      rsbox.show()
      hbox.add(rsbox)
      self.best_quality_resample.show()
      self.good_quality_resample = gtk.RadioButton(self.best_quality_resample, ln.good_quality_resample)
      self.good_quality_resample.connect("toggled", self.cb_resample_quality, 1) 
      rsbox = gtk.HBox()
      rsbox.pack_start(self.good_quality_resample, True, False, 0)
      rsbox.show()
      hbox.add(rsbox)
      self.good_quality_resample.show()
      self.fast_resample = gtk.RadioButton(self.good_quality_resample, ln.fast_resample)
      self.fast_resample.connect("toggled", self.cb_resample_quality, 2) 
      rsbox = gtk.HBox()
      rsbox.pack_start(self.fast_resample, True, False, 0)
      rsbox.show()
      hbox.add(rsbox)
      self.fast_resample.show()
      self.fastest_resample = gtk.RadioButton(self.fast_resample, ln.fastest_resample)
      self.fastest_resample.connect("toggled", self.cb_resample_quality, 4) 
      rsbox = gtk.HBox()
      rsbox.pack_start(self.fastest_resample, True, False, 0)
      rsbox.show()
      hbox.add(rsbox)
      self.fastest_resample.show()
      aud_rs_hbox.pack_start(frame, True, True, 0)
      frame.show()
      parent.tooltips.set_tip(self.best_quality_resample, ln.player_resample_quality)
      parent.tooltips.set_tip(self.good_quality_resample, ln.player_resample_quality)
      parent.tooltips.set_tip(self.fast_resample, ln.player_resample_quality)
      parent.tooltips.set_tip(self.fastest_resample, ln.player_resample_quality)
      
      outervbox.pack_start(aud_rs_hbox, False, False, 0)
      aud_rs_hbox.show()
      
      # Prokyon 3 database connection
      self.p3prefs = p3db.Prefs(self.parent)
      outervbox.pack_start(self.p3prefs, False, False, 0)
      self.p3prefs.show()
      
      # Session to be saved, or initial settings preferences.
      frame = gtk.Frame(" " + ln.initial_player_settings + " ")
      frame.set_label_align(0.5, 0.5)
      frame.set_border_width(3)
      vbox = gtk.VBox()
      frame.add(vbox)
      vbox.show()
      
      restoresessionhbox = gtk.HBox()
      restoresessionhbox.set_border_width(8)
      restoresessionhbox.show()
      self.restore_session_option = gtk.CheckButton(ln.restore_session)
      vbox.pack_start(restoresessionhbox, False, False, 0)
      restoresessionhbox.pack_start(self.restore_session_option, False, False, 0)
      self.restore_session_option.show()
      parent.tooltips.set_tip(self.restore_session_option, ln.restore_session_tip)
      
      hbox = gtk.HBox()
      vbox.add(hbox)
      hbox.set_border_width(3)
      
      self.left_player_frame = gtk.Frame(" " + ln.player_1 + " ")
      self.left_player_frame.set_border_width(2)
      hbox.pack_start(self.left_player_frame, True, True, 6)
      self.left_player_frame.show()
      
      self.right_player_frame = gtk.Frame(" " + ln.player_2 + " ")
      self.right_player_frame.set_border_width(2)
      hbox.pack_start(self.right_player_frame, True, True, 6)
      self.right_player_frame.show()

      hbox.show()
      
      lvbox = gtk.VBox()
      lvbox.set_border_width(4)
      self.left_player_frame.add(lvbox)
      self.lplayall = gtk.RadioButton(None, ln.play_all)
      self.lplayall.set_border_width(1)
      lvbox.add(self.lplayall)
      self.lplayall.show()
      self.lloopall = gtk.RadioButton(self.lplayall, ln.loop_all)
      self.lloopall.set_border_width(1)
      lvbox.add(self.lloopall)
      self.lloopall.show()
      self.lrandom = gtk.RadioButton(self.lloopall, ln.random)
      self.lrandom.set_border_width(1)
      lvbox.add(self.lrandom)
      self.lrandom.show()
      self.lmanual = gtk.RadioButton(self.lrandom, ln.manual)
      self.lmanual.set_border_width(1)
      lvbox.add(self.lmanual)
      self.lmanual.show()
      self.lcueup = gtk.RadioButton(self.lmanual, ln.cue_up)
      self.lcueup.set_border_width(1)
      lvbox.add(self.lcueup)
      self.lcueup.show()
      separator = gtk.HSeparator()
      lvbox.pack_start(separator, False, False, 1)
      separator.show()
      self.lcountup = gtk.RadioButton(None, ln.count_up)
      self.lcountup.set_border_width(1)
      lvbox.add(self.lcountup)
      self.lcountup.show()
      self.lcountdown = gtk.RadioButton(self.lcountup, ln.count_down)
      self.lcountdown.set_border_width(1)
      lvbox.add(self.lcountdown)
      self.lcountdown.show()
      separator = gtk.HSeparator()
      lvbox.pack_start(separator, False, False, 1)
      separator.show()
      self.lstream = gtk.CheckButton(ln.stream)
      self.lstream.set_border_width(1)
      self.lstream.set_active(True)
      lvbox.add(self.lstream)
      self.lstream.show()
      self.llisten = gtk.CheckButton(ln.djlisten)
      self.llisten.set_border_width(1)
      self.llisten.set_active(True)
      lvbox.add(self.llisten)
      self.llisten.show()
      
      lvbox.show()
      
      rvbox = gtk.VBox()
      rvbox.set_border_width(4)
      self.right_player_frame.add(rvbox)
      self.rplayall = gtk.RadioButton(None, ln.play_all)
      self.rplayall.set_border_width(1)
      rvbox.add(self.rplayall)
      self.rplayall.show()
      self.rloopall = gtk.RadioButton(self.rplayall, ln.loop_all)
      self.rloopall.set_border_width(1)
      rvbox.add(self.rloopall)
      self.rloopall.show()
      self.rrandom = gtk.RadioButton(self.rloopall, ln.random)
      self.rrandom.set_border_width(1)
      rvbox.add(self.rrandom)
      self.rrandom.show()
      self.rmanual = gtk.RadioButton(self.rrandom, ln.manual)
      self.rmanual.set_border_width(1)
      rvbox.add(self.rmanual)
      self.rmanual.show()
      self.rcueup = gtk.RadioButton(self.rmanual, ln.cue_up)
      self.rcueup.set_border_width(1)
      rvbox.add(self.rcueup)
      self.rcueup.show()
      separator = gtk.HSeparator()
      rvbox.pack_start(separator, False, False, 1)
      separator.show()
      self.rcountup = gtk.RadioButton(None, ln.count_up)
      self.rcountup.set_border_width(1)
      rvbox.add(self.rcountup)
      self.rcountup.show()
      self.rcountdown = gtk.RadioButton(self.rcountup, ln.count_down)
      self.rcountdown.set_border_width(1)
      rvbox.add(self.rcountdown)
      self.rcountdown.show()
      separator = gtk.HSeparator()
      rvbox.pack_start(separator, False, False, 1)
      separator.show()
      self.rstream = gtk.CheckButton(ln.stream)
      self.rstream.set_border_width(1)
      self.rstream.set_active(True)
      rvbox.add(self.rstream)
      self.rstream.show()
      self.rlisten = gtk.CheckButton(ln.djlisten)
      self.rlisten.set_border_width(1)
      self.rlisten.set_active(True)
      rvbox.add(self.rlisten)
      self.rlisten.show()
      rvbox.show()
      
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
      
      self.tracks_played = gtk.CheckButton(ln.tracks_played)
      misc_startupl.add(self.tracks_played)
      self.tracks_played.show()
      self.stream_mon = gtk.CheckButton(ln.stream_monitor)
      misc_startupr.add(self.stream_mon)
      self.stream_mon.show()
      
      self.restore_session_option.connect("toggled", self.cb_restore_session)
      self.restore_session_option.set_active(True)
     
      outervbox.pack_start(frame, False, False, 0)
      frame.show() 
            
      features_label = gtk.Label(ln.general_tab)
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
     
      # New AGC controls
      
      mic_controls = []
      vbox = gtk.VBox()
      for i in range(idjc_config.num_micpairs):
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
            mic_controls.append(c)
         mic_controls[-2].set_partner(mic_controls[-1])
         mic_controls[-1].set_partner(mic_controls[-2])   
      parent.mic_opener.new_button_set()

      panevbox.pack_start(vbox, False, False, 0)
      vbox.show()
      
      frame = gtk.Frame(" " + ln.other_mic_options + " ")
      frame.set_label_align(0.5, 0.5)
      frame.set_border_width(3)
      vbox = gtk.VBox()
      vbox.set_border_width(3)
      frame.add(vbox)
      vbox.show()
      panevbox.pack_start(frame, False, False, 0)
      frame.show()
      hbox = gtk.HBox()
      label = gtk.Label(ln.headroom)
      hbox.pack_start(label, False, False, 0)
      label.show()
      headroom_adj = gtk.Adjustment(0.0, 0.0, 12.0, 0.5)
      self.headroom = gtk.SpinButton(headroom_adj, digits=1)
      self.headroom.connect("value-changed", self.cb_headroom)
      hbox.pack_end(self.headroom, False, False, 0)
      self.headroom.show()
      vbox.add(hbox)
      hbox.show()
      
      compressor_label = gtk.Label(ln.microphone_tab)
      self.notebook.append_page(scrolled_window, compressor_label)
      compressor_label.show()
       
      # X-Chat IRC announcements tag.
      
      vbox = gtk.VBox()
      vbox.set_border_width(6)
      sizegroup = gtk.SizeGroup(gtk.SIZE_GROUP_VERTICAL)
      
      trackannouncerframe = gtk.Frame(" " + ln.track_announcer + " ")
      trackannouncerframe.set_border_width(3)
      vbox.pack_start(trackannouncerframe, False, False, 0)
      announcervbox = gtk.VBox()
      announcervbox.set_border_width(5)
      trackannouncerframe.add(announcervbox)
      announcervbox.show()
      
      hbox = gtk.HBox()
      announcervbox.add(hbox)
      hbox.show()
      leftpaddingbox = gtk.VBox()
      leftpaddingbox.set_size_request(6, -1)
      hbox.pack_start(leftpaddingbox, False, False, 0)
      leftpaddingbox.show()
      leftvbox = gtk.VBox()
      hbox.pack_start(leftvbox, False, False, 0)
      leftvbox.show()
      rightvbox = gtk.VBox()
      hbox.pack_start(rightvbox, True, True, 0)
      rightvbox.show()
      paddingbox = gtk.VBox()
      paddingbox.set_size_request(6, -1)
      hbox.pack_start(paddingbox, False, False, 0)
      paddingbox.show()
      
      enablebox = gtk.HBox()
      self.announce_enable = gtk.CheckButton(" " + ln.enable)
      sizegroup.add_widget(self.announce_enable)
      enablebox.pack_end(self.announce_enable, False, False, 0)
      self.announce_enable.show()
      enablebox.show()
      leftvbox.add(enablebox)
      enablebox.show()
      parent.tooltips.set_tip(self.announce_enable, ln.enable_track_announcer_tip)

      nickbox = gtk.HBox()
      self.nickentry = gtk.Entry()
      sizegroup.add_widget(self.nickentry)
      self.nickentry.set_width_chars(14)
      self.nickentry.set_max_length(30)
      nickbox.pack_end(self.nickentry, False, False, 0)
      self.nickentry.show()
      nicklabel = gtk.Label(ln.nick + " ")
      nickbox.pack_end(nicklabel, False, False, 0)
      nicklabel.show()
      parent.tooltips.set_tip(self.nickentry, ln.nick_entry_tip)
      
      delaybox = gtk.HBox()
      nickbox.pack_end(delaybox, False, False, 14)
      delaybox.show()
      delaylabel = gtk.Label(ln.latency + " ")
      delaybox.pack_start(delaylabel, False, False, 0)
      delaylabel.show()
      self.announcedelayadj = gtk.Adjustment(10.0, 1.0, 60.0, 1.0, 1.0)
      delay = gtk.SpinButton(self.announcedelayadj, 4, 0)
      delaybox.pack_start(delay, False, False, 0)
      delay.show()
      parent.tooltips.set_tip(delay, ln.track_announcer_latency_tip)
      
      rightvbox.pack_start(nickbox, False, False, 1)
      nickbox.show()
      
      channelslabel = gtk.Label(ln.channels + " ")
      sizegroup.add_widget(channelslabel)
      channelslabelbox = gtk.HBox()
      channelslabelbox.pack_end(channelslabel, False, False, 0)
      channelslabel.show()
      leftvbox.add(channelslabelbox)
      channelslabelbox.show()
      
      self.channelsentry = gtk.Entry()
      sizegroup.add_widget(self.channelsentry)
      channelsbox = gtk.HBox()
      channelsbox.pack_start(self.channelsentry, True, True, 0)
      self.channelsentry.show()
      rightvbox.pack_start(channelsbox, False, False, 1)
      channelsbox.show()
      parent.tooltips.set_tip(self.channelsentry, ln.irc_channels_tip)
      
      announcemessagelabel = gtk.Label(ln.message + " ")
      sizegroup.add_widget(announcemessagelabel)
      announcemessagelabelbox = gtk.HBox()
      announcemessagelabelbox.pack_end(announcemessagelabel, False, False, 0)
      announcemessagelabel.show()
      leftvbox.add(announcemessagelabelbox)
      announcemessagelabelbox.show()
      
      self.announcemessageentry = gtk.Entry()
      sizegroup.add_widget(self.announcemessageentry)
      announcemessagebox = gtk.HBox()
      announcemessagebox.pack_start(self.announcemessageentry, True, True, 0)
      self.announcemessageentry.show()
      rightvbox.pack_start(announcemessagebox, False, False, 1)
      self.announcemessageentry.connect("populate-popup", self.colourmenupopulate)
      self.announcemessageentry.connect("key-press-event", self.cb_handle_colour_char)
      announcemessagebox.show()
      parent.tooltips.set_tip(self.announcemessageentry, ln.announce_tip)
      
      trackannouncerframe.show()
      
      timerframe = gtk.Frame(" " + ln.irc_message_timer + " ")
      timerframe.set_border_width(3)
      vbox.pack_start(timerframe, False, False, 2)
      timerframe.show()
      timervbox = gtk.VBox()
      timervbox.set_border_width(5)
      timerframe.add(timervbox)
      timervbox.show()
      
      hbox = gtk.HBox()
      timervbox.add(hbox)
      hbox.show()
      leftpaddingbox = gtk.VBox()
      leftpaddingbox.set_size_request(6,-1)
      hbox.pack_start(leftpaddingbox, False, False, 0)
      leftpaddingbox.show()
      leftvbox = gtk.VBox()
      hbox.pack_start(leftvbox, False, False, 0)
      leftvbox.show()
      rightvbox = gtk.VBox()
      hbox.pack_start(rightvbox, True, True, 0)
      rightvbox.show()
      paddingbox = gtk.VBox()
      paddingbox.set_size_request(6, -1)
      hbox.pack_start(paddingbox, False, False, 0)
      paddingbox.show()
      
      enablebox = gtk.HBox()
      self.timer_enable = gtk.CheckButton(" " + ln.enable)
      sizegroup.add_widget(self.timer_enable)
      enablebox.pack_end(self.timer_enable, False, False, 0)
      self.timer_enable.show()
      enablebox.show()
      leftvbox.add(enablebox)
      enablebox.show()
      parent.tooltips.set_tip(self.timer_enable, ln.enable_message_timer_tip)

      nickbox = gtk.HBox()
      self.timernickentry = gtk.Entry()
      sizegroup.add_widget(self.timernickentry)
      self.timernickentry.set_width_chars(14)
      self.timernickentry.set_max_length(30)
      nickbox.pack_end(self.timernickentry, False, False, 0)
      self.timernickentry.show()
      nicklabel = gtk.Label(ln.nick + " ")
      nickbox.pack_end(nicklabel, False, False, 0)
      nicklabel.show()
      intervalbox = gtk.HBox()
      nickbox.pack_end(intervalbox, False, False, 14)
      parent.tooltips.set_tip(self.timernickentry, ln.nick_entry_tip)
      
      intervalbox.show()
      intervallabel = gtk.Label(ln.interval + " ")
      intervalbox.pack_start(intervallabel, False, False, 0)
      intervallabel.show()
      self.intervaladj = gtk.Adjustment(20.0, 1.0, 60.0, 1.0, 1.0)
      interval = gtk.SpinButton(self.intervaladj, 4, 0)
      intervalbox.pack_start(interval, False, False, 0)
      interval.show()
      rightvbox.pack_start(nickbox, True, True, 1)
      nickbox.show()
      parent.tooltips.set_tip(interval, ln.message_timer_interval)
      
      channelslabel = gtk.Label(ln.channels + " ")
      sizegroup.add_widget(channelslabel)
      channelslabelbox = gtk.HBox()
      channelslabelbox.pack_end(channelslabel, False, False, 0)
      channelslabel.show()
      leftvbox.add(channelslabelbox)
      channelslabelbox.show()
      
      self.timerchannelsentry = gtk.Entry()
      sizegroup.add_widget(self.timerchannelsentry)
      channelsbox = gtk.HBox()
      channelsbox.pack_start(self.timerchannelsentry, True, True, 0)
      self.timerchannelsentry.show()
      rightvbox.pack_start(channelsbox, True, True, 1)
      channelsbox.show()
      parent.tooltips.set_tip(self.timerchannelsentry, ln.irc_channels_tip)
      
      timemessagelabel = gtk.Label(ln.message + " ")
      sizegroup.add_widget(timemessagelabel)
      timemessagelabelbox = gtk.HBox()
      timemessagelabelbox.pack_end(timemessagelabel, False, False, 0)
      timemessagelabel.show()
      leftvbox.add(timemessagelabelbox)
      timemessagelabelbox.show()
      
      self.timermessageentry = gtk.Entry()
      sizegroup.add_widget(self.timermessageentry)
      timemessagebox = gtk.HBox()
      timemessagebox.pack_start(self.timermessageentry, True, True, 0)
      self.timermessageentry.show()
      rightvbox.pack_start(timemessagebox, True, True, 1)
      self.timermessageentry.connect("populate-popup", self.colourmenupopulate)
      self.timermessageentry.connect("key-press-event", self.cb_handle_colour_char)
      timemessagebox.show()
      parent.tooltips.set_tip(self.timermessageentry, ln.announce_tip)
      
      timerframe.show()
      
      label = gtk.Label(ln.song_placemarker)
      hbox = gtk.HBox()
      hbox.add(label)
      vbox.pack_start(hbox, False, False, 2)
      hbox.show()
      label.show()
      
      xchat_installer = XChatInstaller() 
      parent.tooltips.set_tip(xchat_installer, ln.xchat_install_tip)

      vbox.pack_end(xchat_installer, False)
      xchat_installer.show()
      
      irc_label = gtk.Label("XChat")
      self.notebook.append_page(vbox, irc_label)
      irc_label.show()
      vbox.show()
       
      # Jack settings Tab      
                 
      scrolled = gtk.ScrolledWindow()
      scrolled.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
      jack_vbox = gtk.VBox()
      scrolled.add_with_viewport(jack_vbox)
      scrolled.child.set_shadow_type(gtk.SHADOW_NONE)
      jack_vbox.set_spacing(3)
      #jack_vbox.set_border_width(4)
      jack_vbox.show()
      
      jackname = os.environ["IDJC_JACK_SERVER"]
      if jackname != "default":
         label = gtk.Label(ln.using_jack_server + jackname)
         jack_vbox.add(label)
         label.show()
      
      frame = gtk.Frame()
      frame.set_border_width(5)
      vbox = gtk.VBox(False, 0)
      frame.add(vbox)
      frame.show()
      
      self.mic_jack_data = []
      for i in range(1, idjc_config.num_micpairs * 2 + 1):
         n = str(i)
         box, check, entry, update = make_entry_line(self, "mic_in_" + n + ": ", "MIC", True, i - 1)
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
      self.use_dsp = gtk.CheckButton(ln.use_dsp_text)
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
      
      jacklabel = gtk.Label(ln.jack_ports_tab)
      self.notebook.append_page(scrolled, jacklabel)
      jacklabel.show()
      scrolled.show()

      # Controls tab
      tab= IDJCcontrols.ControlsUI(self.parent.controls)
      label= gtk.Label(ln.ctrltab_label)
      self.notebook.append_page(tab, label)
      tab.show()
      label.show()

      # Event tab
      
      vbox = gtk.VBox()
      vbox.set_border_width(4)
      vbox.set_spacing(2)
      
      app_event_container = self.event_command_container()
      self.appstart_event = self.event_command("icon", 20, 20, "", False, False, parent.tooltips, ln.app_start_tip, ln.shell_commands_tip)
      app_event_container.add(self.appstart_event)
      self.appstart_event.show()
      self.appexit_event = self.event_command("icon", 20, 20, "", False, True, parent.tooltips, ln.app_exit_tip, ln.shell_commands_tip)
      app_event_container.add(self.appexit_event)
      self.appexit_event.show()
      vbox.pack_start(app_event_container, False, False, 0)
      app_event_container.show()
      
      mic_event_container = self.event_command_container()
      self.mic_on_event = self.event_command("mic4", 20, 20, "", False, False, parent.tooltips, ln.mic_on_tip, ln.shell_commands_tip)
      mic_event_container.add(self.mic_on_event)
      self.mic_on_event.show()
      self.mic_off_event = self.event_command("mic4", 20, 20, "", False, True, parent.tooltips, ln.mic_off_tip, ln.shell_commands_tip)
      mic_event_container.add(self.mic_off_event)
      self.mic_off_event.show()
      vbox.pack_start(mic_event_container, False, False, 0)
      mic_event_container.show()
      
      aux_event_container = self.event_command_container()
      self.aux_on_event = self.event_command("jack2", 20, 20, "", False, False, parent.tooltips, ln.aux_on_tip, ln.shell_commands_tip)
      aux_event_container.add(self.aux_on_event)
      self.aux_on_event.show()
      self.aux_off_event = self.event_command("jack2", 20, 20, "", False, True, parent.tooltips, ln.aux_off_tip, ln.shell_commands_tip)
      aux_event_container.add(self.aux_off_event)
      self.aux_off_event.show()
      vbox.pack_start(aux_event_container, False, False, 0)
      aux_event_container.show()
      
      eventlabel = gtk.Label(ln.event_tab)
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
      
      pixbuf = gtk.gdk.pixbuf_new_from_file(pkgdatadir + "logo" + gfext)
      image = gtk.Image()
      image.set_from_pixbuf(pixbuf)
      vbox.pack_start(image, False, False, 8)
      image.show()
      
      label = gtk.Label()
      label.set_markup(u'<span font_desc="sans 13">' + self.parent.copyright + u'</span>')
      vbox.pack_start(label, False, False, 12)
      label.show()
      
      label = gtk.Label()
      label.set_markup(u'<span font_desc="sans 10" underline="low" foreground="blue">' + ln.licence + '</span>')
      vbox.pack_start(label, False, False, 1)
      label.show()
      
      nb = gtk.Notebook()
      nb.set_border_width(10)
      vbox.pack_start(nb, True, True, 0)
      nb.show()
      
      lw = licence_window.LicenceWindow()
      lw.set_border_width(1)
      lw.set_shadow_type(gtk.SHADOW_ETCHED_IN)
      label = gtk.Label(ln.licence_tab)
      nb.append_page(lw, label)
      lw.show()
      label.show()
      
      contributors = ("Stephen Fairchild (s-fairchild@users.sourceforge.net)", "And Clover (and@doxdesk.com)", "Dario Abatianni (eisfuchs@users.sourceforge.net)", "Stefan Fendt (stefan@sfendt.de)", "Jannis Achstetter (jannis_achstetter@web.de)", "Sven Krohlas (sven@asbest-online.de)")
      
      sw = gtk.ScrolledWindow()
      sw.set_border_width(1)
      sw.set_shadow_type(gtk.SHADOW_NONE)
      sw.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
      label = gtk.Label(ln.contrib_label)
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

      aboutlabel = gtk.Label(ln.about_tab)
      self.notebook.append_page(frame, aboutlabel)
      aboutlabel.show()
      frame.show()
      
      self.notebook.show()

      # These on by default
      self.djalarm.set_active(True)
      self.dither.set_active(True)
      self.fastest_resample.set_active(True)
      self.enable_tooltips.set_active(True)
      mic0 = mic_controls[0]
      mic0.active.set_active(True)
      mic0.alt_name.set_text("DJ")
      mic0.autoopen.set_active(True)
      self.show_stream_meters.set_active(True)
      self.show_microphones.set_active(True)
      self.headroom.set_value(3.0)
      
      self.load_jack_port_settings()
      self.bind_jack_ports()
      
      self.playersettingsdict = {       # Settings of these will be saved in the config file 
         "lplayall"      : self.lplayall,       # These are all True/False values
         "lloopall"      : self.lloopall,
         "lrandom"       : self.lrandom,
         "lmanual"       : self.lmanual,
         "lcueup"        : self.lcueup,
         "lcountup"      : self.lcountup,
         "lcountdown"    : self.lcountdown,
         "lstream"       : self.lstream,
         "llisten"       : self.llisten,
         "rplayall"      : self.rplayall,
         "rloopall"      : self.rloopall,
         "rrandom"       : self.rrandom,
         "rmanual"       : self.rmanual,
         "rcueup"        : self.rcueup,
         "rcountdown"    : self.rcountdown,
         "rstream"       : self.rstream,
         "rlisten"       : self.rlisten,
         "startmini"     : self.startmini,
         "announce_en"   : self.announce_enable,
         "timer_en"      : self.timer_enable,
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
         "mp3utf8"           : self.mp3_utf8,
         "silencekiller" : self.silence_killer,
         "bonuskiller"   : self.bonus_killer,
         "unlimretries"  : self.recon_config.unlimited_retries,
         "recondialog"   : self.recon_config.visible,
         "sbfullrecon"   : self.recon_config.attempt_reconnection,
         "rg_indicate"   : self.rg_indicate,
         "rg_adjust"     : self.rg_adjust,
         "str_meters"    : self.show_stream_meters,
         "mic_meters"    : self.show_microphones,
         "mic_meters_active" : self.show_active_microphones,
         }
         
      for mic_control in mic_controls:
         self.playersettingsdict.update(mic_control.booleandict)
         
      self.valuesdict = {
         "interval"          : self.intervaladj,
         "latency"           : self.announcedelayadj,
         "interval_vol"  : self.parent.jingles.interadj,
         "fullwinx"      : self.parent.fullwinx,
         "fullwiny"      : self.parent.fullwiny,
         "minwinx"       : self.parent.minwinx,
         "minwiny"       : self.parent.minwiny,
         "jingleswinx"   : self.parent.jingles.jingleswinx,
         "jingleswiny"   : self.parent.jingles.jingleswiny,
         "prefswinx"     : self.winx,
         "prefswiny"     : self.winy,
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
         "announcenick"  : self.nickentry,
         "announcechan"  : self.channelsentry, 
         "announcemess"  : self.announcemessageentry,
         "timernick"     : self.timernickentry,
         "timerchan"     : self.timerchannelsentry,
         "timermess"     : self.timermessageentry,
         "ltfilerqdir"   : self.parent.player_left.file_requester_start_dir,
         "rtfilerqdir"   : self.parent.player_right.file_requester_start_dir,
         "et_appstart"   : self.appstart_event,
         "et_appexit"    : self.appexit_event,
         "et_micon"      : self.mic_on_event,
         "et_micoff"     : self.mic_off_event,
         "et_auxon"      : self.aux_on_event,
         "et_auxoff"     : self.aux_off_event,
         "con_delays"    : self.recon_config.csl,
         }

      for mic_control in mic_controls:
         self.textdict.update(mic_control.textdict)

      self.rangewidgets = (self.parent.deckadj,)
