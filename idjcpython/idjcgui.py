#   idjcgui.py: Main python code of IDJC
#   Copyright (C) 2005-2010 Stephen Fairchild (s-fairchild@users.sourceforge.net)
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

appname= "Internet DJ Console"
copyright = "Copyright 2005-2010 Stephen Fairchild"
copyright2 = u"\xA9 2005-2010 Stephen Fairchild"        # As above but uses copyright character (c)
license = "Released under the GNU General Public License V2.0"
# version is set in the configure.in files
METER_TEXT_SIZE = 8000

console_help_message="""Usage:  idjc [-vhe] [-p profile] [-j jackserver] [-m microphone] [-a auxiliary] [-t voipmode] [-s serverstart]
            -v    display the version number and exit
            -h    show this help
            -e    allow the launching of extra instances
            -p    select a new or existing application profile
            -j    which JACK server to use
            -m    which microphone inputs to open e.g. 12 for mics 1 and 2
            -a    open the auxiliary input - 1 is the only parameter allowed
            -t    the VOIP mode 0=Off, 1=Green phone, 2=Red phone
            -s    servers to connect to e.g. 13 for servers 1 and 3"""
            

import locale, os, sys, fcntl, subprocess, ConfigParser

def locale_encoding():
   read = subprocess.Popen(["locale", "-a"], stdout=subprocess.PIPE).stdout# I have to do all this because an exception 
   validlocales = read.read()           # refuses to be trapped for some reason
   read.close()                         # therefore I need to prevent it from occurring
   validlocales = validlocales.splitlines()
   lang = os.environ.get("LANG")
   if lang is not None and lang is not "":
      # I wouldn't need to do this if I could use try/except but for some reason I can't trap any locale exceptions hence this code here.
      lang = lang[:5] + lang[5:].replace("-", "").lower().replace("\x00", "").strip()   
      for each in validlocales:
         each = each[:5] + each[5:].replace("-", "").lower().replace("\x00", "").strip()
         if each == lang:               # almost tempted to add a strip on this line too
            break
      else:
         print "The LANG environment variable points to an invalid locale:", lang
         print "Type 'locale -a' at a console for a list of valid settings"
         del os.environ["LANG"]
   os.environ["LANG"] = locale.setlocale(locale.LC_ALL, "")
   try:
      locale.getpreferredencoding()
   except (locale.Error, Exception):
      del os.environ["LANG"] 
      locale.setlocale(locale.LC_ALL, "")
      de = "iso8859-1"
   else:
      de = locale.getpreferredencoding()
   if de == "ANSI_X3.4-1968":
      # Avoid using ASCII encoding.  The terminal is most likely latin1 or utf8
      # The ASCII fallback is there for windows compatibility!
      de = "iso-8859-1"
   fe = os.environ.get("G_FILENAME_ENCODING")
   if fe == None or fe == "":
      if os.environ.get("G_BROKEN_FILENAMES") == "1":
         fe = sys.getfilesystemencoding()
         os.environ["G_FILENAME_ENCODING"]=fe
      else:
         fe = "UTF-8"
   elif fe.lower() == "@locale" or fe.lower() == "locale":
      fe = de
      os.environ["G_FILENAME_ENCODING"]=fe
   return de, fe                # note that fe can contain a comma separated list

display_enc, file_enc = locale_encoding()

try:
   from ln_text import ln
except:
   sys.path.append(os.environ.get("pkgpyexecdir"))
   from ln_text import ln

import pygtk
pygtk.require('2.0')
import gtk, gobject, time, fcntl, signal, stat, cairo, socket, pickle

try:
   pango.Font   # some users will not need to import pango explicitly
except:
   import pango

# import the python modules
import idjc_config
from idjc_config import *
from IDJCmedia import *
from sourceclientgui import *
from IDJCmixprefs import *
from IDJCjingles import *
from IDJCfree import int_object, threadslock
import IDJCcontrols
import tooltips
import p3db

class MicButton(gtk.ToggleButton):
   def __init__(self, labeltext):
      gtk.ToggleButton.__init__(self)
      hbox = gtk.HBox()
      pad = gtk.HBox()
      hbox.pack_start(pad, True, True)
      pad.show()
      hbox.set_spacing(4)
      self.add(hbox)
      label = gtk.Label(labeltext)
      hbox.pack_start(label, False, False)
      label.show()
      self.image = gtk.Image()
      pb = gtk.gdk.pixbuf_new_from_file_at_size(pkgdatadir + "mic4" + gfext, 47, 20)
      self.image.set_from_pixbuf(pb)
      hbox.pack_start(self.image, False, False)
      self.image.show()
      pad = gtk.HBox()
      hbox.pack_start(pad, True, True)
      pad.show()
      hbox.show()
   
class MicOpener(gtk.HBox):
   def notify_others(self):
      approot = self.approot
      # Player headroom for mic-audio toggle.
      sts = "ACTN=anymic\nFLAG=%d\nend\n" % self.any_mic_selected
      approot.mixer_write(sts, True)
      # Aux/Mic mutex implemented here.
      if self.any_mic_selected == False:
         approot.prefs_window.mic_off_event.activate()
      else:
         if approot.prefs_window.mic_aux_mutex.get_active() and approot.aux_select.get_active():
            approot.prefs_window.mic_aux_mutex.set_active(False)
            approot.aux_select.set_active(False)
            approot.prefs_window.mic_aux_mutex.set_active(True)
         if self.any_mic_selected:
            approot.prefs_window.mic_on_event.activate()
      # Mixer mode can change with mic buttons being pressed.
      approot.new_mixermode(approot.mixermode)

   def cb_mictoggle(self, button, mics):
      for mic in mics:
         mic.open.set_active(button.get_active())
      self.any_mic_selected = any(x.get_active() for x in self.mic2button.itervalues())
      self.notify_others()

   def cb_reconfigure(self, widget, trigger=None):
      self.new_button_set()
      self.notify_others()
      
   def mic_names(self, group):
      ui_names = []
      full_names = []
      for m in group:
         ui_names.append(m.ui_name)
         alt = m.alt_name.get_text().strip()
         full_names.append((m.ui_name + " " + alt) if alt else m.ui_name)
         
      return ui_names, full_names
      
   def new_button_set(self):
      # Clear away all child widgets.
      self.foreach(lambda x: x.destroy())
      self.mic2button = {}
      # New buttons arrive.
      free = []
      group_list = [[] for x in xrange(idjc_config.num_micpairs)]
      for m in self.mic_list:
         if m.active.get_active():
            # Mics listed according to their group.
            if not m.group.get_active():
               free.append(m)
            else:
               for i, mic_group in enumerate(m.groups):
                  if mic_group.get_active():
                     group_list[i].append(m)
      
      for g in group_list:
         if g:
            ui_names, full_names = self.mic_names(g)
            mb = MicButton("  ".join(full_names))
            mb.connect("toggled", self.cb_mictoggle, g)
            # One mic on in the group means remaining mics to be on also.
            mb.set_active(any(m.open.get_active() for m in g))
            self.add(mb)
            mb.show()
            self.mic2button.update(dict.fromkeys(ui_names, mb))
         
      for m in free:
         mb = MicButton(self.mic_names((m, ))[1][0])
         # Button state set to match state of back end.
         mb.set_active(m.open.get_active())
         mb.connect("toggled", self.cb_mictoggle, (m,)) # Associate with one mic
         self.mic2button[m.ui_name] = mb                # Reverse mapping
         self.add(mb)
         mb.show()

      if self.all_forced_on:
         self.force_all_on(True)
            
      if not self.mic2button:
         l = gtk.Label(ln.no_microphones)
         l.set_sensitive(False) # It just looks better that way.
         self.add(l)
         l.show()
     
   def force_all_on(self, val):
      self.all_forced_on = val
      for mb in self.mic2button.itervalues():
         if val:
            mb.set_active(True)
         mb.set_sensitive(not val)
         mb.set_inconsistent(val)

   def open_auto(self):
      for m in self.mic_list:
         if m.autoopen.get_active():
            self.mic2button[m.ui_name].set_active(True)

   def oc(self, mic, val):
      """Perform open/close on the matching button for the mic."""
      
      try:
         self.mic2button[mic].set_active(val)
      except:
         pass

   def close_all(self):
      for mb in self.mic2button.itervalues():
         mb.set_active(False)

   def open(self, val):
      self.oc(val, True)
      
   def close(self, val):
      self.oc(val, False)

   def add_mic(self, mic):
      """mic: AGCControl object passed here to register it with this class."""

      self.mic_list.append(mic)
      mic.active.connect("toggled", self.cb_reconfigure)
      mic.group.connect("toggled", self.cb_reconfigure)
      for mic_group in mic.groups:
         mic_group.connect("toggled", self.cb_reconfigure)
      mic.alt_name.connect("changed", self.cb_reconfigure)

   def __init__(self, approot):
      self.approot = approot
      gtk.HBox.__init__(self)
      self.set_spacing(2)
      self.mic_list = []
      self.any_mic_selected = False
      self.all_forced_on = False

class PaddedVBox(gtk.VBox):
   def vbox_pack_start(self, *args, **kwargs):
      self.vbox.pack_start(*args, **kwargs)
   def vbox_add(self, *args, **kwargs):
      self.vbox.add(*args, **kwargs)

   def __init__(self, l, t, r, b, s):
      gtk.VBox.__init__(self)
      d = gtk.VBox()
      self.pack_start(d, False, False, t)
      d.show()
      d = gtk.VBox()
      self.pack_end(d, False, False, b)
      d.show()
      h = gtk.HBox()
      self.pack_start(h, True, True)
      h.show()
      d = gtk.VBox()
      h.pack_start(d, False, False, l)
      d.show()
      d = gtk.VBox()
      h.pack_end(d, False, False, r)
      d.show()
      self.vbox = gtk.VBox()
      self.vbox.set_spacing(6)
      h.pack_start(self.vbox)
      self.vbox.show()      
      self.pack_start = self.vbox_pack_start
      self.add = self.vbox_add

def make_limiter_scale():
   scalebox = gtk.VBox()
   label = gtk.Label("30")
   attrlist = pango.AttrList()
   attrlist.insert(pango.AttrSize(METER_TEXT_SIZE, 0, len(label.get_text())))
   label.set_attributes(attrlist)
   alignment = gtk.Alignment(0, 0)
   alignment.add(label)
   label.show()
   scalebox.add(alignment)
   alignment.show()
   label = gtk.Label("25")
   attrlist = pango.AttrList()
   attrlist.insert(pango.AttrSize(METER_TEXT_SIZE, 0, len(label.get_text())))
   label.set_attributes(attrlist)
   alignment = gtk.Alignment(0, .1)
   alignment.add(label)
   label.show()
   scalebox.add(alignment)
   alignment.show()
   label = gtk.Label("20")
   attrlist = pango.AttrList()
   attrlist.insert(pango.AttrSize(METER_TEXT_SIZE, 0, len(label.get_text())))
   label.set_attributes(attrlist)
   alignment = gtk.Alignment(0, .3)
   alignment.add(label)
   label.show()
   scalebox.add(alignment)
   alignment.show()
   label = gtk.Label("15")
   attrlist = pango.AttrList()
   attrlist.insert(pango.AttrSize(METER_TEXT_SIZE, 0, len(label.get_text())))
   label.set_attributes(attrlist)
   alignment = gtk.Alignment(0, .5)
   alignment.add(label)
   label.show()
   scalebox.add(alignment)
   alignment.show()
   label = gtk.Label("10")
   attrlist = pango.AttrList()
   attrlist.insert(pango.AttrSize(METER_TEXT_SIZE, 0, len(label.get_text())))
   label.set_attributes(attrlist)
   alignment = gtk.Alignment(0, .7)
   alignment.add(label)
   label.show()
   scalebox.add(alignment)
   alignment.show()
   label = gtk.Label(" 5")
   attrlist = pango.AttrList()
   attrlist.insert(pango.AttrSize(METER_TEXT_SIZE, 0, len(label.get_text())))
   label.set_attributes(attrlist)
   alignment = gtk.Alignment(0, .9)
   alignment.add(label)
   label.show()
   scalebox.add(alignment)
   alignment.show()
   label = gtk.Label(" 0")
   attrlist = pango.AttrList()
   attrlist.insert(pango.AttrSize(METER_TEXT_SIZE, 0, len(label.get_text())))
   label.set_attributes(attrlist)
   alignment = gtk.Alignment(0, 1)
   alignment.add(label)
   label.show()
   scalebox.add(alignment)
   alignment.show()
   return scalebox  

def make_meter_scale():         # A logarithmic meter scale for a 'VU' meter
   scalebox = gtk.VBox()
   label = gtk.Label("  0")
   attrlist = pango.AttrList()
   attrlist.insert(pango.AttrSize(METER_TEXT_SIZE, 0, len(label.get_text())))
   label.set_attributes(attrlist)
   alignment = gtk.Alignment(0, 0)
   alignment.add(label)
   label.show()
   scalebox.add(alignment)
   alignment.show()
   label = gtk.Label(" -6")
   attrlist = pango.AttrList()
   attrlist.insert(pango.AttrSize(METER_TEXT_SIZE, 0, len(label.get_text())))
   label.set_attributes(attrlist)
   alignment = gtk.Alignment(0, 0)
   alignment.add(label)
   label.show()
   scalebox.add(alignment)
   alignment.show()
   label = gtk.Label("-12")
   attrlist = pango.AttrList()
   attrlist.insert(pango.AttrSize(METER_TEXT_SIZE, 0, len(label.get_text())))
   label.set_attributes(attrlist)
   alignment = gtk.Alignment(0, 0.25)
   alignment.add(label)
   label.show()
   scalebox.add(alignment)
   alignment.show()
   label = gtk.Label("-18")
   attrlist = pango.AttrList()
   attrlist.insert(pango.AttrSize(METER_TEXT_SIZE, 0, len(label.get_text())))
   label.set_attributes(attrlist)
   alignment = gtk.Alignment(0, 0.5)
   alignment.add(label)
   label.show()
   scalebox.add(alignment)
   alignment.show()
   label = gtk.Label("-24")
   attrlist = pango.AttrList()
   attrlist.insert(pango.AttrSize(METER_TEXT_SIZE, 0, len(label.get_text())))
   label.set_attributes(attrlist)
   alignment = gtk.Alignment(0, 0.75)
   alignment.add(label)
   label.show()
   scalebox.add(alignment)
   alignment.show()
   label = gtk.Label("-30")
   attrlist = pango.AttrList()
   attrlist.insert(pango.AttrSize(METER_TEXT_SIZE, 0, len(label.get_text())))
   label.set_attributes(attrlist)
   alignment = gtk.Alignment(0, 1)
   alignment.add(label)
   label.show()
   scalebox.add(alignment)
   alignment.show()
   label = gtk.Label("-36")
   attrlist = pango.AttrList()
   attrlist.insert(pango.AttrSize(METER_TEXT_SIZE, 0, len(label.get_text())))
   label.set_attributes(attrlist)
   alignment = gtk.Alignment(0, 1)
   alignment.add(label)
   label.show()
   scalebox.add(alignment)
   alignment.show()
   return scalebox
   
def make_meter_unit(text, l_meter, r_meter):
   mic_peak_box = gtk.VBox()
   mic_peak_box.set_border_width(0)
   frame = gtk.Frame()
   frame.set_border_width(4)
   hbox = gtk.HBox()
   hbox.set_border_width(1)
   frame.add(hbox)
   label = gtk.Label(text)
   attrlist = pango.AttrList()
   attrlist.insert(pango.AttrSize(METER_TEXT_SIZE, 0, len(text)))
   label.set_attributes(attrlist)
   labelbox = gtk.HBox()
   labelbox.add(label)
   label.show()
   mic_peak_box.pack_start(labelbox, False, False, 0)
   labelbox.show()
   mic_peak_box.add(frame)
   frame.show()
   hbox.show()
   l_meter.set_size_request(16, -1)
   hbox.add(l_meter)
   scalebox = make_meter_scale()
   hbox.add(scalebox)
   scalebox.show()
   r_meter.set_size_request(16, -1)
   hbox.add(r_meter)
   l_meter.show()
   r_meter.show()
   return mic_peak_box
 
def make_stream_meter_unit(text, meters, tooltips):
   outer_vbox = gtk.VBox()
   outer_vbox.set_border_width(0)
   frame = gtk.Frame()
   frame.set_border_width(4)
   inner_vbox = gtk.VBox()
   frame.add(inner_vbox)
   label = gtk.Label(text)
   attrlist = pango.AttrList()
   attrlist.insert(pango.AttrSize(METER_TEXT_SIZE, 0, len(text)))
   label.set_attributes(attrlist)
   labelbox = gtk.HBox()
   labelbox.add(label)
   label.show()
   outer_vbox.pack_start(labelbox, False, False, 0)
   labelbox.show()
   outer_vbox.pack_start(frame, False, False, 0)
   frame.show()
   inner_vbox.show()
   for num, meter in enumerate(meters):
      hbox = gtk.HBox()
      hbox.set_border_width(1)
      hbox.set_spacing(1)
      inner_vbox.add(hbox)
      hbox.show()
      label = gtk.Label(str(num + 1))
      hbox.pack_start(label, False, False, 0)
      label.show()
      vbox = gtk.VBox()
      vbox.pack_start(meter, True, True, 2)
      meter.show()
      hbox.pack_start(vbox, True, True, 0)
      vbox.show()
   tooltips.set_tip(frame, ln.streams_tip)
   
   frame = gtk.Frame()              # for the listener count
   frame.set_label_align(0.5, 0.5)
   pixbuf = gtk.gdk.pixbuf_new_from_file_at_size(pkgdatadir + "listenerphones" + gfext, 20, 16)
   image = gtk.image_new_from_pixbuf(pixbuf)
   frame.set_label_widget(image)
   image.show()
   
   frame.set_border_width(4)
   inner_vbox = gtk.VBox()
   frame.add(inner_vbox)
   inner_vbox.show()
   connections = gtk.Label("0")
   inner_vbox.add(connections)
   connections.show()
   outer_vbox.pack_start(frame, False, False, 0)
   frame.show()
   tooltips.set_tip(frame, ln.listener_indicator_tip)
   
   return outer_vbox, connections
 
class nice_mic_togglebutton(gtk.ToggleButton):
   def __init__(self, label = None, use_underline = True):
      try:
         gtk.ToggleButton.__init__(self, label, use_underline)
      except RuntimeError:
         gtk.ToggleButton.__init__(self, label)
   def __str__(self):
      return gtk.ToggleButton.__str__(self) + " wrapped by a prelight remover class"
   def set_sensitive(self, bool):
      if bool is False:
         gtk.ToggleButton.set_sensitive(self, False)
         gtk.ToggleButton.set_active(self, True)
         gtk.ToggleButton.set_inconsistent(self, True)
         gtk.ToggleButton.set_inconsistent(self, False)
      else:
         gtk.ToggleButton.set_sensitive(self, True)

class StreamMeter(gtk.Frame):
   def realize(self, widget):
      self.gc = gtk.gdk.GC(self.window)
      self.gc.copy(self.da.get_style().fg_gc[gtk.STATE_NORMAL])
      self.green = gtk.gdk.color_parse("#30D030")
      self.red   = gtk.gdk.color_parse("#D05044")
      self.grey  = gtk.gdk.color_parse("darkgray")
   def expose(self, widget, event):
      if self.flash or not self.active:
         self.gc.set_rgb_fg_color(self.grey)
         self.da.window.draw_rectangle(self.gc, True, 0, 0, self.rect.width, self.rect.height)
      else:
         valuep = int(float(self.value - self.base) / float(self.top - self.base) * self.rect.width)
         self.gc.set_rgb_fg_color(self.red)
         self.da.window.draw_rectangle(self.gc, True, 0, 0, valuep, self.rect.height)
         self.gc.set_rgb_fg_color(self.green)
         self.da.window.draw_rectangle(self.gc, True, valuep, 0, self.rect.width - valuep, self.rect.height)
   def cb_configure(self, widget, event):
      self.rect.width = event.width
      self.rect.height = event.height
   def set_value(self, value):
      if value < self.base:
         self.value = self.base
      elif self.value > self.top:
         self.value = self.top
      else:
         self.value = value
      if value != self.oldvalue:
         self.invalidate()
   def set_active(self, active):
      if active != self.active:
         self.active = active
         self.invalidate()
   def set_flash(self, flash):
      if flash != self.flash:
         self.flash = flash
         self.invalidate()
   def invalidate(self):
      if self.da.flags() & gtk.REALIZED:
         self.da.window.invalidate_rect(self.rect, False)
   def __init__(self, base, top):
      self.base = base
      self.top = top
      gtk.Frame.__init__(self)
      self.set_shadow_type(gtk.SHADOW_IN)
      self.da = gtk.DrawingArea()
      self.add(self.da)
      self.da.connect("configure_event", self.cb_configure)
      self.da.connect("realize", self.realize)
      self.da.connect("expose_event", self.expose)
      self.da.show()
      self.rect = gtk.gdk.Rectangle()
      self.value = self.oldvalue = self.base
      self.active = False
      self.flash = False

class BasicMeter(gtk.Frame):
   def realize(self, widget):
      self.gc = gtk.gdk.GC(self.window)
      self.gc.copy(self.da.get_style().fg_gc[gtk.STATE_NORMAL])
      self.lowc = gtk.gdk.color_parse("#30D030")
      self.midc = gtk.gdk.color_parse("#CCCF44")
      self.highc = gtk.gdk.color_parse("#D05044")
      self.backc = gtk.gdk.color_parse("darkgray")
      self.linec = gtk.gdk.color_parse("#505050")
   def expose(self, widget, event):
      self.oldvalue = self.top
      self.set_value(self.value)
      if self.value != self.base:
         self.oldvalue = self.base
         self.set_value(self.value)
   def cb_configure(self, widget, event):
      self.width = event.width
      self.height = event.height
      # calculate colour threshold pixels
      self.lutp = int(self.height * float(self.lut - self.base) / float(self.top - self.base))
      self.mutp = int(self.height * float(self.mut - self.base) / float(self.top - self.base))
   def set_value(self, value):
      if value > self.top:
         value = self.top
      if value < self.base:
         value = self.base
      self.value = value
      if self.da.flags() & gtk.REALIZED:
         valuep = int(self.height * float(self.value - self.base) / float(self.top - self.base))
         if value < self.oldvalue:
            self.gc.set_rgb_fg_color(self.backc)
            self.da.window.draw_rectangle(self.gc, True, 0, 0, self.width, self.height - valuep)
         if value > self.oldvalue:
            if valuep > self.mutp:
               self.gc.set_rgb_fg_color(self.highc)
               self.da.window.draw_rectangle(self.gc, True, 0, self.height - valuep, self.width, valuep - self.mutp)
               valuep = self.mutp
            if valuep > self.lutp:
               self.gc.set_rgb_fg_color(self.midc)
               self.da.window.draw_rectangle(self.gc, True, 0, self.height - valuep, self.width, valuep - self.lutp)
               valuep = self.lutp
            if valuep > 0:
               self.gc.set_rgb_fg_color(self.lowc)
               self.da.window.draw_rectangle(self.gc, True, 0, self.height - valuep, self.width, valuep)
         if self.line is not None:
            valuel = int(self.height * float(self.line - self.base) / float(self.top - self.base))
            self.gc.set_rgb_fg_color(self.linec)
            self.da.window.draw_lines(self.gc, ((0, self.height - valuel), (self.width, self.height - valuel))) 
         self.oldvalue = value
   def set_line(self, lineval):
      if lineval is not None and (lineval >= self.top or lineval <= self.base):
         lineval = None
      self.line = lineval
      self.expose(None, None)
   def get_value(self):
      return self.value
   def __init__(self, base, top, lut, mut):
      """widget will draw in up to three colours mut = mid upper threshold, lut = low upper threshold"""
      assert top > base, "top must be greater than base"
      assert lut >= base, "lut must be greater than or equal to base" 
      assert lut <= top, "lut must not exceed top"
      assert mut >= lut, "mut must be greater than or equal to lut"
      assert mut <= top, "mut must not exceed top"
      gtk.Frame.__init__(self)
      self.set_shadow_type(gtk.SHADOW_IN)
      self.da = gtk.DrawingArea()
      self.add(self.da)
      self.da.connect("configure_event", self.cb_configure)
      self.da.connect("realize", self.realize)
      self.da.connect("expose_event", self.expose)
      self.da.show()
      self.base = base
      self.top = top
      self.lut = lut
      self.mut = mut
      self.value = base
      self.oldvalue = self.top
      self.line = None

class StackedMeter(gtk.Frame):
   def realize(self, widget):
      self.gc = gtk.gdk.GC(self.window)
      self.gc.copy(self.da.get_style().fg_gc[gtk.STATE_NORMAL])
      self.ngc = gtk.gdk.color_parse("#30D030")
      self.dsc = gtk.gdk.color_parse("#CCCF44")
      self.compc = gtk.gdk.color_parse("#D05044")
      self.backc = gtk.gdk.color_parse("darkgray")
   def expose(self, widget, event):
      self.set_meter_value(self.c, self.d, self.n, True)
   def cb_configure(self, widget, event):
      self.width = event.width
      self.height = event.height
      self.uh = self.height / float(self.top - self.base)
   def set_meter_value(self, c, d, n, force=False):
      if not force and (self.c == c and self.d == d and self.n == n):
         return      # values not changed from last time so no need to redraw
      if c < self.base:
         c = self.base
      if d < self.base:
         d = self.base
      if n < self.base:
         n = self.base
      if c > self.top:
         c = self.top
      if d > self.top:
         d = self.top
      if n > self.top:
         n = self.top
      self.c = c
      self.d = d
      self.n = n
      if self.da.flags() & gtk.REALIZED:
         nh = int(self.uh * n)
         dh = int(self.uh * d)
         ch = int(self.uh * c)
         if ch + dh + nh > self.height:
            ch = self.height - dh - nh
         if nh:
            self.gc.set_rgb_fg_color(self.ngc)
            self.da.window.draw_rectangle(self.gc, True, 0, 0, self.width, nh)
         if dh:
            self.gc.set_rgb_fg_color(self.dsc) 
            self.da.window.draw_rectangle(self.gc, True, 0, nh, self.width, dh)
         if ch:
            self.gc.set_rgb_fg_color(self.compc)
            self.da.window.draw_rectangle(self.gc, True, 0, nh + dh, self.width, ch)

         self.gc.set_rgb_fg_color(self.backc)
         self.da.window.draw_rectangle(self.gc, True, 0, nh + dh + ch, self.width, self.height - (nh + dh + ch))


   def __init__(self, base, top):
      self.base = base
      self.top = top
      assert top > base, "top must be greater than base"
      gtk.Frame.__init__(self)
      self.set_shadow_type(gtk.SHADOW_IN)
      self.da = gtk.DrawingArea()
      self.add(self.da)
      self.da.connect("configure_event", self.cb_configure)
      self.da.connect("realize", self.realize)
      self.da.connect("expose_event", self.expose)
      self.da.show()
      self.c = self.d = self.n = base - 1

class vumeter(BasicMeter):      # this meter is fed rms values at 50ms intervals
   def set_meter_value(self, newvalue):
      if newvalue > self.scale:
         newvalue = self.scale
         
      self.gen6 = self.gen5
      self.gen5 = self.gen4
      self.gen4 = self.gen3
      self.gen3 = self.gen2
      self.gen2 = self.gen1
      self.gen1 = newvalue
      # take a mean average of rms values for 300ms weighted towards recent sounds
      newvalue = (5 * self.gen1 + 6 * self.gen2 + 4 * self.gen3 + 3 * self.gen4 + 2 * self.gen5 + self.gen6 ) / 21
      BasicMeter.set_value(self, -newvalue)
   def __init__(self):
      BasicMeter.__init__(self, -36, 0, -12, -7)
      self.gen1 = self.gen2 = self.gen3 = self.gen4 = self.gen5 = self.scale = 36

class peakholdmeter(BasicMeter):
   def set_meter_value(self, newval):
      oldval = self.get_value()
      if newval > oldval:
         self.peakage = 0
         oldval = newval
      else:
         self.peakage += 1
         if self.peakage > self.peakholditers:
                 newval = oldval - (self.peakage - self.peakholditers) ** 1.1
         else:
            newval = oldval
      BasicMeter.set_value(self, newval)
   def __init__(self):
      BasicMeter.__init__(self, -36, 0, -12, -2)
      self.peakage = 0
      self.oldval = 0
      self.peakholditers = 4    # number of calls before the meter starts to decay

class MicMeter(gtk.VBox):
   def set_meter_value(self, newvals):
      gain, red, yellow, green = (int(x) for x in newvals.split(","))
      self.peak.set_meter_value(gain)
      self.attenuation.set_meter_value(red, yellow, green)

   def set_led(self, value):
      self.led.set_from_pixbuf(self.led_onpb if value else self.led_offpb)

   def always_show(self, widget):
      self.show_while_inactive = widget.get_active()
      if self.show_while_inactive:
         self.show()
      elif not (self.flags() & gtk.SENSITIVE):
         self.hide()

   def set_sensitive(self, value):
      gtk.VBox.set_sensitive(self, value)
      if self.show_while_inactive == False and value == False:
         self.hide()
      else:
         self.show()

   def __init__(self, labelbasetext, index):
      gtk.VBox.__init__(self)
      self.set_border_width(0)
      lhbox = gtk.HBox()
      pad = gtk.VBox()
      lhbox.add(pad)
      pad.show()
      lhbox.set_spacing(2)
      self.led_onpb = gtk.gdk.pixbuf_new_from_file_at_size(pkgdatadir + "led_lit_green_black_border_64x64" + gfext, 7, 7)
      self.led_offpb = gtk.gdk.pixbuf_new_from_file_at_size(pkgdatadir + "led_unlit_clear_border_64x64" + gfext, 7, 7)
      self.led = gtk.Image()
      lhbox.pack_start(self.led, False, False)
      self.set_led(False)
      self.led.show()
      labeltext = labelbasetext + str(index)
      label = gtk.Label(labeltext)
      attrlist = pango.AttrList()
      attrlist.insert(pango.AttrSize(METER_TEXT_SIZE, 0, len(labeltext)))
      label.set_attributes(attrlist)     
      lhbox.pack_start(label, False, False)
      label.show()
      pad = gtk.VBox()
      lhbox.add(pad)
      pad.show()
      self.pack_start(lhbox, False, False)
      lhbox.show()
      frame = gtk.Frame()
      frame.set_border_width(4)
      self.pack_start(frame, True, True)
      frame.show()
      hbox = gtk.HBox()
      hbox.set_border_width(1)
      frame.add(hbox)
      hbox.show()
      
      self.peak = peakholdmeter()
      self.peak.set_size_request(16, -1)
      hbox.pack_start(self.peak, False, False)
      self.peak.show()

      scale = make_meter_scale()
      hbox.pack_start(scale, False, False)
      scale.show()

      self.attenuation = StackedMeter(0, 36)
      self.attenuation.set_size_request(16, -1)
      hbox.pack_start(self.attenuation, False, False)
      self.attenuation.show()
      self.show_while_inactive = True

# A dialog window for electing to create a new profile
class profile_import_dialog(gtk.Dialog):
   def __init__(self, title_text, additional_text, profiledir, newprofile):
      gtk.Dialog.__init__(self, title_text, None, False, (gtk.STOCK_YES, gtk.RESPONSE_YES, gtk.STOCK_NO, gtk.RESPONSE_NO, ))
      gtk.Dialog.set_icon_from_file(self, pkgdatadir + "icon" + gfext)
      gtk.Dialog.set_resizable(self, False)
      hbox = gtk.HBox(False, 20)
      hbox.set_border_width(20)
      self.vbox.pack_start(hbox, True, True, 0)
      hbox.show()
      image = gtk.Image()
      image.set_from_stock(gtk.STOCK_DIALOG_QUESTION, gtk.ICON_SIZE_DIALOG)
      hbox.pack_start(image, True, True, 0)
      image.show()
      vbox = gtk.VBox()
      vbox.set_spacing(8)
      hbox.pack_start(vbox, True, True, 0)
      vbox.show()
      if additional_text is not None:
         if type(additional_text) is str:
            additional_text = additional_text.splitlines()
         for each in additional_text:
            label = gtk.Label()
            attrlist = pango.AttrList()
            attrlist.insert(pango.AttrSize(12500, 0, len(each)))
            label.set_attributes(attrlist)
            label.set_text(each)
            vbox.add(label)
            label.show()
      self.combobox = gtk.combo_box_new_text()
      self.combobox.append_text("default")
      root, dirs, files = os.walk(profiledir).next()
      for each in dirs:
         if each != "default" and each != newprofile:
            self.combobox.append_text(each)
      self.combobox.set_active(0)
      vbox.add(self.combobox)
      self.combobox.show()

# A dialog window for electing to create a new profile
class select_profile_dialog(gtk.Dialog):
   def profile_enter(self, widget):
      if widget.get_text() != "":
         self.enterbutton.clicked()
      
   def profile_changed(self, widget):
      self.enterbutton.set_sensitive(len(widget.get_text()) != 0)
   
   def cb_keypress(self, widget, event):
      # filter out undesired keys
      if event.keyval == 65361: return False
      if event.keyval == 65363: return False
      if event.keyval == 65535: return False
      if event.keyval == 65288: return False
      if event.keyval == 65293: return False
      if event.string.isalnum(): return False
      if event.string == "_": return False
      return True
   
   def comboselection(self, widget):
      if widget.get_active() == 0:
         self.new_profile_box.show()
         self.new_profile_box.grab_focus()
         self.profile_changed(self.new_profile_box)
      else:
         self.new_profile_box.hide()
         self.enterbutton.set_sensitive(True)

   def __init__(self, title_text, additional_text, profiledir, newprofile):
      gtk.Dialog.__init__(self, title_text, None, False, None)
      self.no_more_ask = gtk.CheckButton(ln.no_more_ask)
      self.action_area.pack_start(self.no_more_ask, False, False, 0)
      self.no_more_ask.show()
      self.enterbutton = gtk.Dialog.add_button(self, gtk.STOCK_OK, gtk.RESPONSE_OK)
      gtk.Dialog.add_button(self, gtk.STOCK_QUIT, gtk.RESPONSE_CANCEL)
      gtk.Dialog.set_icon_from_file(self, pkgdatadir + "icon" + gfext)
      gtk.Dialog.set_resizable(self, False)
      hbox = gtk.HBox(False, 20)
      hbox.set_border_width(20)
      self.vbox.pack_start(hbox, True, True, 0)
      hbox.show()
      image = gtk.Image()
      image.set_from_stock(gtk.STOCK_DIALOG_QUESTION, gtk.ICON_SIZE_DIALOG)
      hbox.pack_start(image, True, True, 0)
      image.show()
      vbox = gtk.VBox()
      vbox.set_spacing(8)
      hbox.pack_start(vbox, True, True, 0)
      vbox.show()
      if additional_text is not None:
         if type(additional_text) is str:
            additional_text = additional_text.splitlines()
         for each in additional_text:
            label = gtk.Label()
            attrlist = pango.AttrList()
            attrlist.insert(pango.AttrSize(12500, 0, len(each)))
            label.set_attributes(attrlist)
            label.set_text(each)
            vbox.add(label)
            label.show()
      self.combobox = gtk.combo_box_new_text()
      self.combobox.append_text(ln.select_profile_new)
      self.combobox.append_text("default")
      for root, dirs, files in os.walk(profiledir):
         for each in dirs:
            if each != "default":
               self.combobox.append_text(each)
         break
      self.combobox.connect("changed", self.comboselection)
      vbox.add(self.combobox)
      self.combobox.show()
      self.new_profile_box = gtk.Entry()
      self.new_profile_box.set_max_length(24)
      self.new_profile_box.connect("key_press_event", self.cb_keypress)
      self.new_profile_box.connect("activate", self.profile_enter)
      self.new_profile_box.connect("changed", self.profile_changed)
      if newprofile:
         self.combobox.set_active(0)
         self.new_profile_box.set_text(newprofile)
      else:
         self.combobox.set_active(1)
      vbox.add(self.new_profile_box)
 
# A dialog window for electing to create a new profile
class new_profile_dialog(gtk.Dialog):
   def __init__(self, title_text, additional_text):
      gtk.Dialog.__init__(self, title_text, None, False, (gtk.STOCK_YES, gtk.RESPONSE_YES, gtk.STOCK_NO, gtk.RESPONSE_NO, gtk.STOCK_QUIT, gtk.RESPONSE_CANCEL))
      gtk.Dialog.set_icon_from_file(self, pkgdatadir + "icon" + gfext)
      gtk.Dialog.set_resizable(self, False)
      hbox = gtk.HBox(False, 20)
      hbox.set_border_width(20)
      self.vbox.pack_start(hbox, True, True, 0)
      hbox.show()
      image = gtk.Image()
      image.set_from_stock(gtk.STOCK_DIALOG_QUESTION, gtk.ICON_SIZE_DIALOG)
      hbox.pack_start(image, True, True, 0)
      image.show()
      vbox = gtk.VBox()
      vbox.set_spacing(8)
      hbox.pack_start(vbox, True, True, 0)
      vbox.show()
      if additional_text is not None:
         if type(additional_text) is str:
            additional_text = additional_text.splitlines()
         for each in additional_text:
            label = gtk.Label()
            attrlist = pango.AttrList()
            attrlist.insert(pango.AttrSize(12500, 0, len(each)))
            label.set_attributes(attrlist)
            label.set_text(each)
            vbox.add(label)
            label.show()
  
# A dialog window to appear when shutdown is selected while still streaming.
class idjc_shutdown_dialog:
   def window_attn(self, widget, event):
      if event.new_window_state | gtk.gdk.WINDOW_STATE_ICONIFIED:
         widget.set_urgency_hint(True)
      else:
         widget.set_urgency_hint(False)
   
   def respond(self, dialog, response, actionyes, actionno):
      if response == gtk.RESPONSE_OK:
         print "Dialog quit"
         if actionyes is not None:
            actionyes()
      if response == gtk.RESPONSE_DELETE_EVENT or response == gtk.RESPONSE_CANCEL:
         print "Dialog keep running"
         if actionno is not None:
            actionno()
      dialog.destroy()

   def __init__(self, window_group = None, actionyes = None, actionno = None, additional_text = None):
      dialog = gtk.Dialog(ln.idjc_shutdown, None, gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT, (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, gtk.STOCK_QUIT, gtk.RESPONSE_OK))
      if window_group is not None:
         window_group.add_window(dialog)
      dialog.set_icon_from_file(pkgdatadir + "icon" + gfext)
      dialog.set_resizable(False)
      dialog.connect("close", self.respond, actionyes, actionno)
      dialog.connect("response", self.respond, actionyes, actionno)
      dialog.connect("window-state-event", self.window_attn)
      
      hbox = gtk.HBox(False, 20)
      hbox.set_border_width(20)
      dialog.vbox.pack_start(hbox, True, True, 0)
      hbox.show()
      image = gtk.Image()
      image.set_from_stock(gtk.STOCK_DIALOG_QUESTION, gtk.ICON_SIZE_DIALOG)
      hbox.pack_start(image, True, True, 0)
      image.show()
      vbox = gtk.VBox()
      vbox.set_spacing(8)
      hbox.pack_start(vbox, True, True, 0)
      vbox.show()
      
      if additional_text is not None:
         if type(additional_text) is str:
            additional_text = additional_text.splitlines()
         for each in additional_text:
            label = gtk.Label()
            attrlist = pango.AttrList()
            attrlist.insert(pango.AttrSize(12500, 0, len(each)))
            label.set_attributes(attrlist)
            label.set_text(each)
            vbox.add(label)
            label.show()
      dialog.show()

class MainWindow:
   def send_new_mixer_stats(self):
      def xtp(in_str):                  # xchat text package maker
         return "".join(("d", str(len(in_str)), ":", in_str))

      deckadj = deck2adj = self.deckadj.get_value() * -1.0 + 100.0
      if self.prefs_window.dual_volume.get_active():
          deck2adj = self.deck2adj.get_value() * -1.0 + 100.0

      string_to_send = ":%03d:%03d:%03d:%03d:%03d:%03d:%d:%d%d%d%d%d:%d%d:%d:%d%d%d%d:%d:%d:%d:%d:%d:%f:%f:%d:%f:%d:%d:%d:" % (
                                                deckadj,
                                                deck2adj,
                                                self.crossadj.get_value(),
                                                self.jingles.deckadj.get_value() * -1.0 + 100.0,
                                                self.jingles.interadj.get_value() * -1.0 + 100.0,
                                                self.mixbackadj.get_value() * -1.0 + 100.0,
                                                self.jingles.playing,
                                                self.player_left.stream.get_active(),
                                                self.player_left.listen.get_active(),
                                                self.player_right.stream.get_active(),
                                                self.player_right.listen.get_active(),
                                                self.listen_stream.get_active(),
                                                self.player_left.pause.get_active(),
                                                self.player_right.pause.get_active(),
                                                self.aux_select.get_active(),
                                                self.player_left.flush,
                                                self.player_right.flush,
                                                self.jingles.flush,
                                                self.jingles.interludeflush,
                                                self.simplemixer,
                                                self.alarm,
                                                self.mixermode,
                                                True,
                                                self.player_left.play.get_active() or
                                                self.player_right.play.get_active(),
                                                1.0 / self.player_left.pbspeedfactor,
                                                1.0 / self.player_right.pbspeedfactor,
                                                self.prefs_window.speed_variance.get_active(),
                                                self.prefs_window.dj_aud_adj.get_value(),
                                                self.crosspattern.get_active(),
                                                self.prefs_window.use_dsp.get_active(), 
                                                self.prefs_window.twodblimit.get_active(),
                                                )
      self.mixer_write("MIXR=%s\nACTN=mixstats\nend\n" % string_to_send, True)

      self.alarm = False
      iteration = 0
      while self.player_left.flush or self.player_right.flush or self.jingles.flush or self.jingles.interludeflush:
         time.sleep(0.05)
         self.vu_update(False)
         self.jingles.interludeflush = self.jingles.interludeflush & self.interlude_playing.value
         self.jingles.flush = self.jingles.flush & self.jingles_playing.value
         self.player_left.flush = self.player_left.flush & self.player_left.mixer_playing.value
         self.player_right.flush = self.player_right.flush & self.player_right.mixer_playing.value

      # decide which metadata source to use (0 = left, 1 = right)
      if self.metadata_src == self.METADATA_LEFT_DECK:
         meta = 0
      elif self.metadata_src == self.METADATA_RIGHT_DECK:
         meta = 1
      elif self.metadata_src == self.METADATA_LAST_PLAYED:
         if self.last_player == "left":
            meta = 0
         else:
            meta = 1
      elif self.metadata_src == self.METADATA_CROSSFADER:
         if self.crossadj.get_value() < 50:
            meta = 0
         else:
            meta = 1
      elif self.metadata_src == self.METADATA_NONE:
         meta = -1

      # get metadata from left (meta == 0) or right (meta == 1) player
      if meta == 0:
         self.songname = self.player_left.songname
         self.artist = self.player_left.artist
         self.title = self.player_left.title
      elif meta == 1:
         self.songname = self.player_right.songname
         self.artist = self.player_right.artist
         self.title = self.player_right.title
      elif meta == -1:
         self.songname = ""
         self.artist = ""
         self.title = ""

      # update metadata on stream if it has changed
      if self.metadata != self.songname:
         self.metadata = self.songname                  # now we need to send the new metadata
         print "song title: %s\n" % self.metadata.encode(self.denc, "replace")
         if self.metadata != u"":
            self.window.set_title("%s :: IDJC%s" % (self.metadata, self.profile_title))
            tm = time.localtime()
            ts = "%02d:%02d :: " % (tm[3], tm[4])       # hours and minutes
            self.history_buffer.place_cursor(self.history_buffer.get_end_iter())
            self.history_buffer.insert_at_cursor(ts + self.metadata + "\n")
            adjustment = self.history_window.get_vadjustment()
            adjustment.set_value(adjustment.upper)
            try:
               file = open(self.idjc + "history.log", "a")
            except IOError:
               print "unable to open history.log for writing"
            else:
               try:
                  file.write(time.strftime("%x %X :: ") + self.metadata.encode("utf-8") + "\n")
               except IOError:
                  print "unable to append to file \"history.log\""
               file.close()

            try: # The song the DJ is listening to for the xchat /listening trigger
               file = open(self.idjcroot + "songtitle", "w")
               file.write(self.metadata)                # <--- This is wrong
               file.close()
            except IOError:
               print "Failed to write the song title to disk"
               
            # Write out the x-chat track announcement to a file
            # note how the announcement is done on a time delay
            
            if self.prefs_window.announce_enable.get_active() and self.server_window.is_streaming:
               message_text = self.prefs_window.announcemessageentry.get_text().replace(u"%s", self.metadata)
               xchat_text_packet = "".join((
                        xtp(self.prefs_window.nickentry.get_text().encode("utf-8")),
                        xtp(self.prefs_window.channelsentry.get_text().encode("utf-8")),
                        xtp(message_text.encode("utf-8")),
                        xtp(str(int(time.time() + self.prefs_window.announcedelayadj.get_value())))))
               gobject.timeout_add(int(self.prefs_window.announcedelayadj.get_value() * 1000 - 500), self.xchat_announce_the_track, xchat_text_packet)
            self.server_window.new_metadata(self.artist, self.title, self.metadata)
         else:
            self.window.set_title(self.appname + self.profile_title)

   def xchat_announce_the_track(self, message):
      try:
         file = open(self.idjcroot + "announce.xchat", "w")
         fcntl.flock(file.fileno(), fcntl.LOCK_EX)
         file.write(message)
         fcntl.flock(file.fileno(), fcntl.LOCK_UN)
         file.close()
      except IOError:
         print "Problem writing the announcement file to disk"
      return False  

   def songname_decode(self, data):
      data = data[13:]
      i = 1
      while 1:
         if data[i - 1] != "d":
            print "songname_decode: WARNING, read past end boundary"
            yield None
            continue
         colon_index = data.index(":", i)
         text_length = int(data[i : colon_index])
         text = data[colon_index + 1 : colon_index + 1 + text_length]
         yield text
         i = colon_index + text_length + 2

   def update_songname(self, player, data, infotype):
      gen = self.songname_decode(data)
      artist = gen.next()
      title = gen.next()
      artist_title = gen.next()
      player_context = int(gen.next())
      time_lag = int(gen.next())
      
      if infotype == 1:
         song = artist.decode("utf-8", "replace") + u" - " + title.decode("utf-8", "replace")
      if infotype == 2:
         song = artist_title.decode("utf-8", "replace")
         artist = ""
         title = artist_title
      if infotype == 3:
         song = artist.decode("iso8859-1", "replace") + u" - " + title.decode("iso8859-1", "replace")
         artist = artist.decode("iso8859-1", "replace").encode("utf-8", "replace")
         title = title.decode("iso8859-1", "replace").encode("utf-8", "replace")
      if infotype == 4:
         song = artist_title.decode("iso8859-1", "replace")
         artist = ""
         title = song.encode("utf-8", "replace")
      if infotype == 7:
         model = player.model_playing
         iter = player.iter_playing
         
         song = model.get_value(iter, 3)
         artist = model.get_value(iter, 6)
         title = model.get_value(iter, 5)
      if infotype > 4 and infotype < 7: # unicode chapter tags unsupported
         return
      if not player_context & 1:
         time_lag = 0
      else:
         time_lag = int(time_lag / player.pbspeedfactor)
      gobject.timeout_add(time_lag, self.new_songname_timeout, (song, artist, title, player, player_context))

   @threadslock
   def new_songname_timeout(self, (song, artist, title, player, player_context)):
      if player.player_cid == (player_context | 1):
         player.songname = song
         player.artist = artist
         player.title = title
         self.send_new_mixer_stats()
      else:
         print "context mismatch, player context id =", player.player_cid, "metadata update carries context id =", player_context
      return False

   def ui_detail_leveller(self, level):
      def inner(widget):
         try:
            widget.forall(inner)
         except AttributeError:
            pass
         try:
            l = widget.viewlevels
         except AttributeError:
            pass
         else:
            if level in l:
               widget.show()
            else:
               widget.hide()
      return inner

   def callback(self, widget, data):
      print "%s was pressed" % data
      if data == "Show about":
         self.prefs_window.notebook.set_current_page(6)
         self.prefs_window.window.present()
      if data == "Features":
         if widget.get_active():
            self.simplemixer = False
            self.window.forall(self.ui_detail_leveller(5))
            self.window.resize(self.fullwinx, self.fullwiny)
            self.send_new_mixer_stats()
            for each in (self.player_left, self.player_right):
               each.pl_mode.emit("changed")
         else:
            self.simplemixer = True
            self.player_right.stop.clicked()
            self.jingles.window.hide()
            self.crossadj.set_value(0)
            self.crossadj.value_changed()
            self.window.forall(self.ui_detail_leveller(0))
            self.window.resize(self.minwinx, self.minwiny)
            for each in (self.player_left, self.player_right):
               each.pl_delay.set_sensitive(False)
      
      if data == "Advance":
         if self.crossfade.get_value() < 50:
            self.player_left.advance()
         else:
            self.player_right.advance()
      if data == "Server":
         self.server_window.window.present()
         #self.server_window.password_entry.grab_focus()
      if data == "Prefs":
         self.prefs_window.window.present()
      if data == "Jingles":
         self.jingles.window.present()
         self.jingles.entry.grab_focus()
      if data.startswith("cfm"):
         if self.crosspass:
            gobject.source_remove(self.crosspass)
            self.crosspass = 0
         self.crossfade.set_value(data == "cfmright" and 100 or data == "cfmmidl" and 48 or data == "cfmmidr" and 52 or data == "cfmleft" and 0) 
      if data == "pass-crossfader":
         if self.crosspass:
            self.crossdirection = not self.crossdirection
         else:
            self.crossdirection = (self.crossadj.get_value() <= 50)
            self.crosspass = gobject.timeout_add(int(self.passspeed_adj.get_value() * 10), self.cb_crosspass)
      if data == "Clear History":
         self.history_buffer.set_text("")

   def expandercallback(self, expander, param_spec, user_data=None): 
      if expander.get_expanded():
         self.history_vbox.show()
      else:
         self.history_vbox.hide()
      if self.player_left.is_playing:
         self.player_left.reselect_cursor_please = True
      if self.player_right.is_playing:
         self.player_right.reselect_cursor_please = True

   @threadslock
   def cb_crosspass(self):
      x = self.crossadj.get_value()
      if x == 100 * self.crossdirection:
         self.crosspass = 0
         return False
      if self.crossdirection:
         self.crossfade.set_value(x+1)
      else:
         self.crossfade.set_value(x-1)
      return True

   # handles selection of metadata source
   def cb_metadata_source(self, widget):
      print "Metadata source was changed. Before: %d" % self.metadata_src
      self.metadata_src = widget.get_active()
      print "Metadata source was changed. Now: %d" % self.metadata_src
      # update mixer status and metadata
      self.send_new_mixer_stats()
      return True;

   def cb_toggle(self, widget, data):
      print "%s was toggled %s" % (data, ("OFF","ON")[widget.get_active()])
      if data == "Aux Open":
         if widget.get_active() == False:
            self.prefs_window.aux_off_event.activate()
         else:
            if self.prefs_window.mic_aux_mutex.get_active() and (self.mic_opener.any_mic_selected or self.mixermode != self.NO_PHONE):
               self.prefs_window.mic_aux_mutex.set_active(False)        # prevent infinite loop
               self.greenphone.set_active(False)
               self.redphone.set_active(False)
               self.mic_opener.close_all()
               self.prefs_window.mic_aux_mutex.set_active(True)
            self.prefs_window.aux_on_event.activate()
         self.send_new_mixer_stats()
      if data == "stream-mon":
         self.send_new_mixer_stats()
      if data == "Greenphone":
         mode = self.mixermode
         if widget.get_active() == True:
            if self.prefs_window.mic_aux_mutex.get_active() and self.aux_select.get_active():
               self.prefs_window.mic_aux_mutex.set_active(False)
               self.aux_select.set_active(False)
               self.prefs_window.mic_aux_mutex.set_active(True)
            if self.mixermode == self.PRIVATE_PHONE:
               self.mixermode = self.PUBLIC_PHONE
               self.redphone.set_active(False)
            self.mixermode = self.PUBLIC_PHONE
         else:
            if self.mixermode == self.PUBLIC_PHONE:
               self.mixermode = self.NO_PHONE
         if self.mixermode != mode:
            self.new_mixermode(self.mixermode)
      if data == "Redphone":
         mode = self.mixermode
         if widget.get_active() == True:
            if self.prefs_window.mic_aux_mutex.get_active() and self.aux_select.get_active():
               self.prefs_window.mic_aux_mutex.set_active(False)
               self.aux_select.set_active(False)
               self.prefs_window.mic_aux_mutex.set_active(True)
            if self.mixermode == self.PUBLIC_PHONE:
               self.mixermode = self.PRIVATE_PHONE
               self.greenphone.set_active(False)
            self.mixermode = self.PRIVATE_PHONE
         else:
            if self.mixermode == self.PRIVATE_PHONE:
               self.mixermode = self.NO_PHONE
         if self.mixermode != mode:
            self.new_mixermode(self.mixermode)
            
   def new_mixermode(self, mode):
      mic = self.mic_opener.any_mic_selected
      sens = (mode == self.NO_PHONE or mode == self.PUBLIC_PHONE or mic == True)
      self.player_left.listen.set_sensitive(sens)
      self.player_right.listen.set_sensitive(sens)
      self.mic_opener.force_all_on(mode == self.PUBLIC_PHONE)
      if mode == self.PRIVATE_PHONE:
         self.spacerbox.show()
         self.pbphoneimage.show()
         self.mixback.show()
      else:
         self.spacerbox.hide()
         self.pbphoneimage.hide()
         self.mixback.hide()
      self.send_new_mixer_stats()

   def cb_crossfade(self, fader):
      # expire song title data on players that are not on due the crossfader position
      if self.crossadj.get_value() < 50:
         if self.player_right.is_playing == False:
            self.player_right.songname = u""
      else:
         if self.player_left.is_playing == False:
            self.player_left.songname = u""
      # update the mixer of the new crossfader setting and also the metadata if need be
      self.send_new_mixer_stats()
   
   def cb_crosspattern(self, widget):
      print "crossfader pattern changed"
      self.send_new_mixer_stats()
   
   def cb_deckvol(self, gain):
      #print "Hello there, the volume control was moved, value = %d" % gain.value
      self.send_new_mixer_stats()

   def cb_menu_select(self, widget, data):
      print ("%s was chosen from the menu" % data)   

   def save_session(self):
      try:
         fh = open(self.session_filename, "w")
         fh.write("deckvol=" + str(self.deckadj.get_value()) + "\n")
         fh.write("deck2vol=" + str(self.deck2adj.get_value()) + "\n")
         fh.write("crossfade=" + str(self.crossadj.get_value()) + "\n")
         fh.write("jingles_deckvol=" + str(self.jingles.deckadj.get_value()) + "\n")
         fh.write("jingles_intervol=" + str(self.jingles.interadj.get_value()) + "\n")
         fh.write("stream_mon="+ str(int(self.listen_stream.get_active())) + "\n")
         fh.write("tracks_played=" + str(int(self.history_expander.get_expanded())) + "\n")
         fh.write("pass_speed=" + str(self.passspeed_adj.get_value()) + "\n")
         fh.write("prefs=" + str(int((self.prefs_window.window.flags() & gtk.VISIBLE) != 0)) + "\n")
         fh.write("server=" + str(int((self.server_window.window.flags() & gtk.VISIBLE) != 0)) + "\n")
         fh.write("jingles=" + str(int((self.jingles.window.flags() & gtk.VISIBLE) != 0)) + "\n")
         fh.write("prefspage=" + str(self.prefs_window.notebook.get_current_page()) + "\n")
         fh.write("metadata_src=" + str(self.metadata_source.get_active()) + "\n")
         fh.write("crosstype=" + str(self.crosspattern.get_active()) + "\n")
         fh.write("hpane=" + str(self.paned.get_position()) + "\n")
         fh.write("vpane=" + str(self.leftpane.get_position()) + "\n")
         fh.write("treecols=" + self.topleftpane.getcolwidths(self.topleftpane.treecols) + "\n")
         fh.write("flatcols=" + self.topleftpane.getcolwidths(self.topleftpane.flatcols) + "\n")
         fh.write("dbpage=" + str(self.topleftpane.notebook.get_current_page()) + "\n")
         fh.write("interlude=" + self.jingles.saved_interlude + "\n")
         fh.close()
         
         # Save a list of files played and timestamps.
         fh = open(self.session_filename + "_files_played", "w")
         cutoff = time.time() - 2592000 # 2592000 = 30 days.
         recent = {}
         for key, value in self.files_played.iteritems():
            if value > cutoff:
               recent[key] = value
         pickle.Pickler(fh).dump(recent)
         fh.close()
         
      except:
         print "Error writing out main session data"
         raise
      try:
         fh = open(self.session_filename + "_tracks", "w")
         start, end = self.history_buffer.get_bounds()
         text = self.history_buffer.get_text(start, end)
         fh.write(text)
         fh.close()
      except:
         print "Error writing out tracks played data"

   def restore_session(self):
      try:
         fh = open(self.session_filename, "r")
      except:
         return
      while 1:
         try:
            line = fh.readline()
            if line == "":
               break
         except:
               break
         k, _, v = line[:-1].partition('=')
         if k=="deckvol":
            self.deckadj.set_value(float(v))
         elif k=="deck2vol":
            self.deck2adj.set_value(float(v))
         elif k=="crossfade":
            self.crossadj.set_value(float(v))
         elif k=="jingles_deckvol":
            self.jingles.deckadj.set_value(float(v))
         elif k=="jingles_intervol":
            self.jingles.interadj.set_value(float(v))
         elif k=="stream_mon":
            self.listen_stream.set_active(int(v))
         elif k=="tracks_played":
            if int(line[14:-1]):
               self.history_expander.emit("activate")
         elif k=="pass_speed":
            self.passspeed_adj.set_value(float(v))
         elif k=="prefs":
            if v=="1":
               self.prefs_window.window.show()
         elif k=="server":
            if v=="1":
               self.server_window.window.show()
         elif k=="jingles":
            if v=="1":
               self.jingles.window.show()
         elif k=="prefspage":
            self.prefs_window.notebook.set_current_page(int(v))
         elif k=="metadata_src":
            self.metadata_source.set_active(int(v))
         elif k=="crosstype":
            self.crosspattern.set_active(int(v))
         elif k=="hpane":
            self.paned.set_position(int(v))
         elif k=="vpane":
            self.leftpane.set_position(int(v))
         elif k=="treecols":
            self.topleftpane.setcolwidths(self.topleftpane.treecols, v)
         elif k=="flatcols":
            self.topleftpane.setcolwidths(self.topleftpane.flatcols, v)
         elif k=="dbpage":
            self.topleftpane.notebook.set_current_page(int(v))
         elif k=="interlude":
            if v!="":
                self.jingles.start_interlude_player(v)
                self.jingles.interlude.emit("toggled")

      try:
         fh = open(self.session_filename + "_files_played", "r")
      except:
         pass
      else:
         self.files_played = pickle.Unpickler(fh).load()
         fh.close()

      stat = os.stat(self.session_filename + "_tracks")
      if stat.st_ctime + 21600 > time.time():
         try:
            fh = open(self.session_filename + "_tracks", "r")
         except:
            return
         text = fh.read()
         fh.close()
         self.history_buffer.set_text(text)
      else:
         print "Track history text is more than six hours old.  Disregarding.\n"

   def destroy_hard(self, widget=None, data=None):
      if self.session_loaded:
         self.save_session()
         self.prefs_window.save_player_prefs()
         self.controls.save_prefs()
         self.server_window.save_session_settings()
      try:
         gtk.main_quit()
         os.unlink(self.idjc + "command")
         self.lock.close()
         os.unlink(self.idjc + "lock")
      except:
         pass
      gtk.gdk.threads_leave()
      time.sleep(0.3)
      sys.exit(0)

   def destroy(self, widget=None, data=None):
      signal.signal(signal.SIGINT, self.destroy_hard)
      if self.crosspass:
         gobject.source_remove(self.crosspass)
      self.server_window.cleanup()
      self.mic_opener.close_all()
      self.aux_select.set_active(False)
      self.player_left.cleanup()
      self.player_right.cleanup()
      self.jingles.cleanup()
      self.player_left.flush = True
      self.player_right.flush = True
      self.send_new_mixer_stats()
      gobject.source_remove(self.statstimeout)
      gobject.source_remove(self.vutimeout)
      self.server_window.source_client_close()
      self.mixer_ctrl.close()
      self.save_session()
      self.prefs_window.save_player_prefs()
      self.controls.save_prefs()
      self.server_window.save_session_settings()
      self.prefs_window.appexit_event.activate()        # run user specified command for application exit
      if os.path.isfile(self.idjc + "command"):
         os.unlink(self.idjc + "command")
      self.lock.close()
      os.unlink(self.idjc + "lock")
      if gtk.main_level():
         gtk.main_quit()
      time.sleep(0.3)   # Allow time for all subthreads/programs time to exit 
      try:
         os.unlink(self.idjc + "command")       # intentionally did this twice
      except:
         pass
      gtk.gdk.threads_leave()
      sys.exit(0)

   def delete_event(self, widget, event, data=None):
      if self.server_window.is_streaming:
         idjc_shutdown_dialog(self.window_group, self.destroy, None, (ln.is_streaming, ln.question_quit))
         return True
      elif self.server_window.is_recording:
         idjc_shutdown_dialog(self.window_group, self.destroy, None, (ln.is_recording, ln.question_quit))
         return True
      self.destroy()
      return False

   # all mixer write operations should go through here so that broken pipes can be handled properly
   def mixer_write(self, message, flush = False, nowrite = False):
      try:
         if nowrite:
            raise IOError
         self.mixer_ctrl.write(message)
         if flush:
            self.mixer_ctrl.flush()
      except (IOError, ValueError):
         print "*** Mixer has likely crashed ***"
         
         try:
            sp_mx = subprocess.Popen([libexecdir + "idjcmixer"], bufsize = 4096, stdin = subprocess.PIPE, stdout = subprocess.PIPE, close_fds = True)
         except Exception, inst:
            print inst
            print "unable to open a pipe to the mixer module"
            self.destroy_hard()
         else:
            (self.mixer_ctrl, self.mixer_rply) = (sp_mx.stdin, sp_mx.stdout)
            
         rply = self.mixer_read()
         while rply[:17] != "IDJC: Sample rate":
            if rply == "":
               if self.last_chance == True:
                  print "mixer crashed a third time -- exiting"
                  self.destroy_hard()
               self.last_chance = True
               print "mixer has crashed a second time"
               self.mixer_write(message, flush, True)
               return
            rply = self.mixer_read()
            if rply[:6] == "JACK: ":
               print rply
               self.destroy_hard()
         self.samplerate = rply[18:].strip()
         print "Sample rate is %s" % self.samplerate
         if self.samplerate != "44100" and self.samplerate !="48000":
            print "Sample rate not supported or garbled reply from mixer"
            self.destroy_hard()
         self.mixer_write("ACTN=nothing\nend\nACTN=sync\nend\n", True)
         print "attempting to sync"
         while 1:
            rply = self.mixer_read()
            if rply == "IDJC: sync reply\n":
               break;
            if rply == "":
               print "mixer has crashed a second time"
               self.destroy_hard()
            print "attempting to sync"
         print "got sync"
         
         self.send_new_mixer_stats()                    # restore previous settings to the mixer
         self.prefs_window.send_new_normalizer_stats()
         self.prefs_window.bind_jack_ports()
         self.mixer_write("ACTN=serverbind\n", True)    # tell mixer to bind audio with the sourceclient module
         self.player_left.next.clicked()
         self.player_right.next.clicked()
         self.jingles.stop.clicked()
         if self.jingles.interlude_player_track != "":
            self.jingles.start_interlude_player(self.jingles.interlude_player_track)
         if self.last_chance == False:
            self.mixer_write(message, flush)            # resume what we were doing
      else:
         self.last_chance = False

   def mixer_read(self, iters = 0):
      if iters == 5:
         self.destroy_hard()
      try:
         line = self.mixer_rply.readline()
      except IOError:
         print "mixer_read: IOError detected"           # this can occur as a result of SIGUSR2 from the launcher
         line = self.mixer_read(iters + 1)
      if line == "Segmentation Fault\n":
         line = ""
         print "Mixer reports a segmentation fault"
         self.mixer_rply.close()
         self.mixer_ctrl.close()
      return line

   def process_play_command(self, filelist):
      if self.crossadj.value < 50:
         player = self.player_left
      else:
         player = self.player_right
      player.stop.clicked()
      player.liststore.clear()
      self.process_enqueue_command(filelist)
      player.play.clicked()

   def process_enqueue_command(self, filelist):
      if self.crossadj.value < 50:
         player = self.player_left
      else:
         player = self.player_right
      for each in filelist:
         if each.endswith(".m3u"):
            filelist2 = self.process_m3u_file(each)
            for item in filelist2:
               self.append_item_to_playlist(player, item)
         if each.endswith(".pls"):
            filelist2 = self.process_pls_file(each)
            for item in filelist2:
               self.append_item_to_playlist(player, item)
         else:
            self.append_item_to_playlist(player, each)

   def process_connect_command(self, tablist):
      for each in tablist:
         try:
            value = int(each) -1
         except ValueError:
            pass
         else:
            try:
               self.server_window.streamtabframe.tabs[value].server_connect.set_active(True)
            except IndexError:
               print "idjcctrl tried to start/stop a non existent stream"

   def process_disconnect_command(self, tablist):
      for each in tablist:
         try:
            value = int(each) -1
         except ValueError:
            pass
         else:
            self.server_window.streamtabframe.tabs[value].server_connect.set_active(False)
   
   def process_record_start_command(self, tablist):
      for each in tablist:
         try:
            value = int(each) -1
         except ValueError:
            pass
         else:
            try:
               self.server_window.recordtabframe.tabs[value].record_buttons.record_button.set_active(True)
            except IndexError:
               print "idjcctrl tried to start/stop a non existent stream"

   def process_record_stop_command(self, tablist):
      for each in tablist:
         try:
            value = int(each) -1
         except ValueError:
            pass
         else:
            self.server_window.recordtabframe.tabs[value].record_buttons.stop_button.clicked()
   
   def process_testmonitor_on_command(self, tablist):
      for each in tablist:
         try:
            value = int(each) -1
         except ValueError:
            pass
         else:
            self.server_window.streamtabframe.tabs[value].test_monitor.set_active(True)
   
   def process_testmonitor_off_command(self, tablist):
      for each in tablist:
         try:
            value = int(each) -1
         except ValueError:
            pass
         else:
            self.server_window.streamtabframe.tabs[value].test_monitor.set_active(False)
   
   def process_update_command(self, tablist):
      for each in tablist:
         try:
            value = int(each) -1
         except ValueError:
            pass
         else:
            self.server_window.streamtabframe.tabs[value].update_button.clicked()
   
   def process_m3u_file(self, filename):
      contents = []
      try:
         file = open(filename, "r")
      except IOError:
         print "unable to open file", filename
      else:
         while 1:
            line = file.readline()
            if not line:
               break
            if line[0] != "#":
               contents.append(line[:-1])
      return contents
   
   def process_pls_file(self, filename):
      contents = []
      try:
         file = open(filename, "r")
      except IOError:
         print "unable to open file", filename
      else:
         while 1:
            line = file.readline()
            if not line:
               break
            if line.startswith("File"):
               line = line.split("=")
               contents.append(line[1][:-1])
      return contents
   
   def append_item_to_playlist(self, player, file):
      entryline = player.get_media_metadata(file)
      if entryline[0] != "Not a valid file":
         player.liststore.append(entryline)
      else:
         print "file not valid:", file

   def process_command_file(self):
      try:
         file = open(self.idjc + "command", "r+")
      except IOError:
         print "Problem reading command file from disk"
      else:
         fcntl.flock(file.fileno(), fcntl.LOCK_EX)
         class stop(Exception): pass
         try:
            while 1:
               line = file.readline()
               if not line:             # check if we are finished
                  break
               if line[0] != "[":       # 1st line must be of the form
                  raise stop            # [--command x] where x is the number of lines that follow
               if line[-2:] != "]\n":
                  raise stop
               line = line[1:-2].split(" ")
               if not line[0].startswith("--"):
                  raise stop
               else:
                  command = line[0][2:]
               try:
                  numberoffiles = int(line[1])
               except:
                  raise stop
               command_data = []
               for item in range(numberoffiles):
                  filename = file.readline()
                  if filename == "":    # check the correct number of files are present
                     raise stop
                  command_data.append(filename[:-1])
               if command == "enqueue":
                  self.process_enqueue_command(command_data)
               elif command == "play":
                  self.process_play_command(command_data)
               elif command == "connect":
                  self.process_connect_command(command_data)
               elif command == "disconnect":
                  self.process_disconnect_command(command_data)
               elif command == "record_start":
                  self.process_record_start_command(command_data)
               elif command == "record_stop":
                  self.process_record_stop_command(command_data)
               elif command == "testmonitor_on":
                  self.process_testmonitor_on_command(command_data)
               elif command == "testmonitor_off":
                  self.process_testmonitor_off_command(command_data)
               elif command == "update":
                  self.process_update_command(command_data)
               else:
                  print "unknown command", command
         except stop:
            print "corruption detected in command file\n"
         file.truncate(0)
         fcntl.flock(file.fileno(), fcntl.LOCK_UN)
         file.close()

   def vu_update(self, locking = True):
      if locking:
         gtk.gdk.threads_enter()
      try:
         if self.second_instance:
            self.window.present()
            self.second_instance = False

         if os.stat(self.idjc + "command").st_size:
            self.process_command_file()

         try:
            self.mixer_write("ACTN=requestlevels\nend\n", True)
         except ValueError, IOError:
            if locking:
               gtk.gdk.threads_leave()
            return True

         midis= ''
         while 1:
            line = self.mixer_read().rstrip()
            if line == "":
               if locking:
                  gtk.gdk.threads_leave()
               return True
            if line == "end":
               break
            if not line.count("="):
               print line
               continue
            key, value = line.split("=")

            if key == "midi":
               midis= value
               continue
            try:
               value = int(value)
            except ValueError:
               pass
            try:
               self.vumap[key].set_meter_value(value)
            except KeyError:
               pass
               #print "key value", key, "missing from vumap"
         if self.jingles.playing == True and int(self.jingles_playing) == 0:
            self.jingles.stop_player(False)
         
         if self.metadata_left_ctrl.get_value():        # handle dynamic metadata
            while 1:
               line = self.mixer_read()
               if line.startswith("new_metadata="):
                  self.update_songname(self.player_left, line, self.metadata_left_ctrl.get_value())
                  break
         if self.metadata_right_ctrl.get_value():
            while 1:
               line = self.mixer_read()
               if line.startswith("new_metadata="):
                  self.update_songname(self.player_right, line, self.metadata_right_ctrl.get_value())
                  break
         #self.left_compressor_gain.set_meter_value(int(self.left_compression_level), int(self.left_deess_level), int(self.left_noisegate_level))
         #self.right_compressor_gain.set_meter_value(int(self.right_compression_level), int(self.right_deess_level), int(self.right_noisegate_level))

         # Carry out MIDI-triggered actions *after* reading them from the
         # response to requestlevels. This is so that any trailing lines after the
         # actions don't interfere with mixer_write/read cycles caused by the
         # control commands themselves.
         #
         if midis!='':
            for midi in midis.split(','):
               input, _, value = midi.partition(':')
               self.controls.input(input, int(value, 16))

      except:
         if locking:    # ensure unlocking occurs whenever there is an exception
            gtk.gdk.threads_leave()
         raise
      if locking:
         gtk.gdk.threads_leave()
      return True

   @threadslock 
   def stats_update(self):
      if not self.player_left.player_is_playing:
         self.player_left.update_time_stats()
      else:
         self.player_left.check_mixer_signal()
      if not self.player_right.player_is_playing:
         self.player_right.update_time_stats()
      else:
         self.player_right.check_mixer_signal()
      return True

   def cb_history_populate(self, textview, menu):
      menusep = gtk.SeparatorMenuItem()
      menu.append(menusep)
      menusep.show()
      menuitem = gtk.MenuItem(ln.track_history_clear)
      menuitem.connect_object("activate", gtk.Button.clicked, self.history_clear)
      menu.append(menuitem)
      menuitem.show()

   def cb_key_capture(self, widget, event):
      self.controls.input_key(event)
      return False

   def configure_event(self, widget, event):
      if self.player_left.is_playing:
         self.player_left.reselect_cursor_please = True
      if self.player_right.is_playing:
         self.player_right.reselect_cursor_please = True
      if not self.simplemixer:
         self.fullwinx.set_value(event.width)
         self.fullwiny.set_value(event.height)
      else:
         self.minwinx.set_value(event.width)
         self.minwiny.set_value(event.height)
         
   def menu_activate(self, widget, event):
      if event.type == gtk.gdk.BUTTON_PRESS and event.button == 3:
         widget.popup(None, None, None, event.button, event.time)
         return True
      return False
   
   def close_window(self, widget, menu):
      menu.get_attach_widget().hide()
   
   def close_menu_attach(self, widget, event, data):
      def detach(self, widget):
         pass
      if event.button == 3:
         if self.close_menu.get_attach_widget() is not None:
            self.close_menu.detach()
         self.close_menu.attach_to_widget(data, detach)
         self.close_menu.popup(None, None, None, event.button, event.time)
   
   # when a second instance of idjc is launched the program launcher will signal the running instance with SIGUSR2
   def second_instance_handler(self, arg1, arg2):
      print "the launch of a second instance of idjc was detected"
      self.second_instance = True       # idjc will handle this event in good time


   def init_profile(self):
      def profile_test(profile):
         for each in profile:
            if each.isalnum() or each == "_":
               continue
            else:
               return False
         return True
      
      def profile_exists(profile):
         return os.path.exists(self.home + "/.idjc/profiles/" + profile)
      
      # decide if we need to run the profile chooser dialog
      self.profile = os.environ["APP_PROFILE"]
      specify_text = ""
      ask_profile = not os.path.isfile(self.idjcroot + "do-not-ask-profile")
      self.ask_profile_next_time = ask_profile
      if self.profile == "(unspecified)":
         self.profile = "default"
      else:
         if profile_test(self.profile) == False:
            print "The profile specified must contain only alphanumeric characters or underscores"
            raise self.initcleanexit
         if self.profile == "ask":
            ask_profile = True
         elif not profile_exists(self.profile):
            ask_profile = True
            specify_text = self.profile
         else:
            ask_profile = False

      # running the profile chooser
      if ask_profile:
         spd = select_profile_dialog(ln.select_profile_title, ln.select_profile_body, self.idjcroot + "profiles", specify_text)
         response = spd.run()
         if response == gtk.RESPONSE_OK:
            if spd.combobox.get_active() != 0:
               self.profile = spd.combobox.get_active_text()
            else:
               self.profile = spd.new_profile_box.get_text()
            if spd.no_more_ask.get_active():
               if not os.path.isfile(self.idjcroot + "do-not-ask-profile"):
                  dnap = "do-not-ask-profile"
                  try:
                     os.mknod(self.idjcroot + dnap)
                  except OSError:
                     # mknod has been reported to fail on mac
                     os.system("touch %s%s" % (self.idjcroot, dnap))
                  self.ask_profile_next_time = False
            spd.destroy()
         else:
            if response == gtk.RESPONSE_CANCEL:
               spd.destroy()
            raise self.initcleanexit

      # creating a new profile to order
      if not profile_exists(self.profile):
         npd = new_profile_dialog(ln.new_profile_title, ln.new_profile_body % self.profile)
         response = npd.run()
         if response != gtk.RESPONSE_DELETE_EVENT:
            npd.destroy()
         if response == gtk.RESPONSE_CANCEL:
            print "user chose to quit"
            raise self.initcleanexit
         if response == gtk.RESPONSE_NO or response == gtk.RESPONSE_DELETE_EVENT:
            print "user chose no -- we will continue with the default profile"
            self.profile = "default"
            self.idjc = self.home + "/.idjc/"
         if response == gtk.RESPONSE_YES:
            print "user chose to create a new profile"
            self.idjc = self.home + "/.idjc/profiles/" + self.profile + "/"
            os.mkdir(self.idjc[:-1])
            os.mkdir(self.idjc + "jingles")
            pid = profile_import_dialog(ln.new_profile_title + ": " + self.profile, ln.profile_import_body, self.idjcroot + "profiles", self.profile)
            response = pid.run()
            if response != gtk.RESPONSE_DELETE_EVENT:
               if response == gtk.RESPONSE_YES:
                  importprofile = pid.combobox.get_active_text()
                  print "copying settings from %s profile" % importprofile
                  os.system("cp %s %s" % (self.home + "/.idjc/profiles/" + importprofile + "/*", self.idjc))
                  # make hard links of jingles files to save space
                  os.system("cp -l %s %s" % (self.home + "/.idjc/profiles/" + importprofile + "/jingles/*", self.idjc + "jingles/"))
               if response == gtk.RESPONSE_NO:
                  print "no profile imported"
               pid.destroy()
      else:
         self.idjc = self.home + "/.idjc/profiles/" + self.profile + "/"
 
      while gtk.events_pending(): # clean up dialog boxes
         gtk.main_iteration()
 
      if os.path.isfile(self.idjc + "lock"):
         if os.system("fuser " + self.idjc + "lock") == 0:
            message_dialog = gtk.MessageDialog(None, 0, gtk.MESSAGE_INFO, gtk.BUTTONS_CLOSE, ln.profile_already_in_use)
            message_dialog.set_icon_from_file(pkgdatadir + "icon" + gfext)
            message_dialog.set_title(ln.idjc_launch_failed)
            message_dialog.run()
            message_dialog.destroy()
            raise self.initfailed("Instance of idjc already running in this profile.")
 
      try:
         self.lock = open(self.idjc + "lock", "w")
      except:
         raise self.initfailed("Failed to create lock file" + self.idjc + "lock")

   def cb_panehide(self, widget):
      """ hide widget when all it's children are hidden or non existent """
      c1 = widget.get_child1()
      c2 = widget.get_child2()
      if (not c1 or not c1.flags() & gtk.VISIBLE) and (not c2 or not c2.flags() & gtk.VISIBLE):
         widget.hide()

   def strip_focusability(self, widget):
      try:
         widget.forall(self.strip_focusability)
      except AttributeError:
         pass
      widget.unset_flags(gtk.CAN_FOCUS)

   class initfailed:
      def __init__(self, errormessage = "something bad happened and IDJC could not continue"):
         print errormessage
         
   class initcleanexit:
      pass

   def __init__(self):
      self.appname = appname
      self.version = version
      self.copyright = copyright2
      self.license = license
      
      self.second_instance = False
      signal.signal(signal.SIGUSR2, self.second_instance_handler)
      signal.signal(signal.SIGINT, self.destroy_hard)
      
      socket.setdefaulttimeout(15)
      
      home = os.environ.get("HOME")
      if home == "":
         raise self.initfailed("Error, HOME environment variable is not set")
      # Build the application data directory tree for idjc
      self.home = home
      self.idjcroot = home + "/.idjc/"
      if not os.path.isdir(home + "/.idjc"):
         os.mkdir(home + "/.idjc")
      if not os.path.isdir(home + "/.idjc/jingles"):
         os.mkdir(home + "/.idjc/jingles")
      if not os.path.isdir(home + "/.idjc/profiles"):
         os.mkdir(home + "/.idjc/profiles")
      if not os.path.exists(home + "/.idjc/profiles/default"):
         os.symlink(home + "/.idjc/", home + "/.idjc/profiles/default")
 
      jackname = os.environ["JACK_SERVER"]
      if jackname == "default":
         try:
            jackname = os.environ["JACK_DEFAULT_SERVER"]
         except:
            pass
      os.environ["IDJC_JACK_SERVER"] = jackname
         
      self.denc = display_enc
      self.fenc = file_enc
      
      print "%s Version %s\n%s\n%s\n" % (appname, self.version, copyright, license)
      
      if os.environ["VERSION_ONLY"] == "1":
         raise self.initcleanexit
      if os.environ["SHOW_HELP"] == "1":
         print console_help_message
         raise self.initcleanexit
      
      self.init_profile()            # decide which profile to use
      print ln

      config = ConfigParser.RawConfigParser()
      config.read(self.idjc + 'limits')
      try:
         idjc_config.num_micpairs = config.getint('resource_count', 'n_mics') // 2
      except ConfigParser.Error:
         idjc_config.num_micpairs = 4
      try:
         idjc_config.num_streamers = idjc_config.num_encoders = config.getint('resource_count', 'n_streamers')
      except ConfigParser.Error:
         idjc_config.num_streamers = idjc_config.num_encoders = 6
      try:
         idjc_config.num_recorders = config.getint('resource_count', 'n_recorders')
      except ConfigParser.Error:
         idjc_config.num_recorders = 2

      # Name the mixer and sourceclient jack client IDs.
      tail = "-" + self.profile if os.environ["EXTRA"] == "1" else ""
      os.environ["mx_client_id"] = mx_id = "idjc-mx" + tail
      os.environ["sc_client_id"] = sc_id = "idjc-sc" + tail
      print "jack client IDs:", mx_id, sc_id
      os.environ["mx_mic_qty"] = str(idjc_config.num_micpairs * 2)

      self.session_loaded = False
 
      try:
         sp_mx = subprocess.Popen([libexecdir + "idjcmixer"], bufsize = 4096, stdin = subprocess.PIPE, stdout = subprocess.PIPE, close_fds = True)
      except Exception, inst:
         print inst
         raise self.initfailed("unable to open a pipe to the mixer module")
      else:
         (self.mixer_ctrl, self.mixer_rply) = (sp_mx.stdin, sp_mx.stdout)
  
      # check for a reply from the mixer.
      self.last_chance = False
      rply = jackrply = self.mixer_read()
      while rply[:6] != "IDJC: ":
         if rply == "":
            print "mixer crashed"
            message_dialog = gtk.MessageDialog(None, 0, gtk.MESSAGE_INFO, gtk.BUTTONS_CLOSE, ln.mixer_crash)
            message_dialog.set_icon_from_file(pkgdatadir + "icon" + gfext)
            message_dialog.set_title(ln.idjc_launch_failed)
            message_dialog.run()
            message_dialog.destroy()
            raise self.initfailed()
         rply = self.mixer_read()
         if rply[:6] == "JACK: ":
            jackrply = rply
      if rply[:17] == "IDJC: Sample rate":
         self.samplerate = rply[18:].strip()
         self.mixer_write("ACTN=sync\nend\n", True)
         self.mixer_read()
      else:
         message_dialog = gtk.MessageDialog(None, 0, gtk.MESSAGE_INFO, gtk.BUTTONS_CLOSE, ln.jack_connection_failed)
         message_dialog.set_icon_from_file(pkgdatadir + "icon" + gfext)
         message_dialog.set_title(ln.idjc_launch_failed)
         message_dialog.run()
         message_dialog.destroy()
         raise self.initfailed()
  
      self.mixer_write("ACTN=mp3status\nend\n", True)
      rply = self.mixer_read()
      if rply == "IDJC: mp3=1\n":
         supported.media.append(".mp3")
  
      # create the GUI elements
      self.window_group = gtk.WindowGroup()
      self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
      self.window_group.add_window(self.window)
      if self.profile == "default":
         self.profile_title = ""
      else:
         self.profile_title = "  (%s)" % self.profile
      self.window.set_title(self.appname + self.profile_title)
      self.window.set_border_width(8)
      self.window.connect("delete_event",self.delete_event)
      self.window.set_icon_from_file(pkgdatadir + "icon" + gfext)
      self.tooltips = tooltips.Tooltips()

      self.hbox10 = gtk.HBox(False)
      self.hbox10.set_border_width(2)
      self.hbox10.set_spacing(7)
      self.paned = gtk.HPaned()
      self.leftpane = gtk.VPaned()
      self.paned.pack1(self.leftpane)
      self.topleftpane = p3db.MediaPane()
      self.leftpane.pack1(self.topleftpane)
      self.topleftpane.connect_object("show", gtk.VPaned.show, self.leftpane)
      self.topleftpane.connect_object("hide", self.cb_panehide, self.leftpane)
      
      # Expand features by adding something useful here
      # a dummy widget is needed to prevent a segfault when F8 is pressed
      self.bottomleftpane = gtk.Button("Bottom")
      #self.bottomleftpane.connect_object("show", gtk.VPaned.show, self.leftpane)
      #self.bottomleftpane.connect_object("hide", self.cb_panehide, self.leftpane)
      self.leftpane.pack2(self.bottomleftpane)
      #self.bottomleftpane.show()
      
      self.rightpane = gtk.HBox(False, 0)
      self.paned.pack2(self.rightpane, True, False)
      self.vbox8 = gtk.VBox(False, 0)
      self.rightpane.pack_start(self.vbox8, True, True ,0)
      self.window.add(self.paned)
      self.rightpane.show()
      self.paned.show()
      
      # add box 6 to box 8
      self.vbox6 = gtk.VBox(False, 0)
      self.vbox8.pack_start(self.vbox6, True, True, 0)
      # add box 7 to box 8
      self.hbox7 = gtk.HBox(True)
      self.hbox7.set_spacing(5)
      self.hbox7.set_border_width(3)
      
      self.frame2 = gtk.Frame()
      self.frame2.set_border_width(6)
      self.frame2.set_shadow_type(gtk.SHADOW_IN)
      self.frame2.add(self.hbox10)
      self.hbox10.show()
      self.frame2.show()
  
      self.vbox8.pack_start(self.frame2, False, False, 0)
      
      # show box 8 now that it's finished
      self.vbox8.show()            
      
      # do box 7 before the others since it is nice and simple
      # add a playlist button to open the playlist window
      wbsg = gtk.SizeGroup(gtk.SIZE_GROUP_HORIZONTAL)
      
      self.prefs_button = gtk.Button(ln.prefs_button)
      wbsg.add_widget(self.prefs_button)
      self.prefs_button.connect("clicked", self.callback, "Prefs")
      self.hbox10.pack_start(self.prefs_button, True, True, 0)
      self.prefs_button.show()
      self.tooltips.set_tip(self.prefs_button, ln.prefs_window_open_tip)
      
      # add a server button to open the output window
      self.server_button = gtk.Button(ln.output_button)
      wbsg.add_widget(self.server_button)
      self.server_button.connect("clicked", self.callback, "Server")
      self.hbox10.pack_start(self.server_button, True, True, 0)
      self.server_button.show()
      self.tooltips.set_tip(self.server_button, ln.output_window_open_tip)
      
      # add a jingles button to open the jingles window
      self.jingles_button = gtk.Button(ln.jingles_button)
      self.jingles_button.viewlevels = (5,)
      wbsg.add_widget(self.jingles_button)
      self.jingles_button.connect("clicked", self.callback, "Jingles")
      self.hbox10.pack_start(self.jingles_button, True, True, 0)
      self.jingles_button.show()
      self.tooltips.set_tip(self.jingles_button, ln.jingles_window_open_tip)
      
      sep = gtk.VSeparator()
      self.hbox10.pack_start(sep, False, False, 5)
      sep.show()
      
      
      phonebox = gtk.HBox()
      phonebox.viewlevels = (5,)       
      phonebox.set_spacing(2)
      
      pixbuf4 = gtk.gdk.pixbuf_new_from_file(pkgdatadir + "greenphone" + gfext)
      pixbuf4 = pixbuf4.scale_simple(25, 20, gtk.gdk.INTERP_BILINEAR)
      image = gtk.Image()
      image.set_from_pixbuf(pixbuf4)
      image.show()
      self.greenphone = gtk.ToggleButton()
      self.greenphone.add(image)
      self.greenphone.connect("toggled", self.cb_toggle, "Greenphone")
      phonebox.pack_start(self.greenphone)
      self.greenphone.show()
      self.tooltips.set_tip(self.greenphone, ln.green_phone_tip)

      pixbuf5 = gtk.gdk.pixbuf_new_from_file(pkgdatadir + "redphone" + gfext)
      pixbuf5 = pixbuf5.scale_simple(25, 20, gtk.gdk.INTERP_BILINEAR)
      image = gtk.Image()
      image.set_from_pixbuf(pixbuf5)
      image.show()
      self.redphone = gtk.ToggleButton()
      self.redphone.add(image)
      self.redphone.connect("toggled", self.cb_toggle, "Redphone")
      phonebox.pack_start(self.redphone)
      self.redphone.show()
      self.tooltips.set_tip(self.redphone, ln.red_phone_tip)
 
      self.hbox10.pack_start(phonebox)
      phonebox.show()
 
      pixbuf3 = gtk.gdk.pixbuf_new_from_file(pkgdatadir + "jack2" + gfext)
      pixbuf3 = pixbuf3.scale_simple(32, 20, gtk.gdk.INTERP_BILINEAR)
      image = gtk.Image()
      image.set_from_pixbuf(pixbuf3)
      image.show()
      self.aux_select = gtk.ToggleButton()
      self.aux_select.viewlevels = (5,)       
      self.aux_select.add(image)
      self.aux_select.connect("toggled", self.cb_toggle, "Aux Open")
      self.hbox10.pack_start(self.aux_select)
      self.aux_select.show()
      self.tooltips.set_tip(self.aux_select, ln.aux_toggle_tip)
      
      # microphone open/unmute dynamic widget cluster thingy
      self.mic_opener = MicOpener(self)
      self.mic_opener.viewlevels = (5,)
      self.hbox10.pack_start(self.mic_opener, True, True)
      self.mic_opener.show()
      
      # playlist advance button
      pixbuf = gtk.gdk.pixbuf_new_from_file(pkgdatadir + "advance" + gfext)
      pixbuf = pixbuf.scale_simple(32, 14, gtk.gdk.INTERP_BILINEAR)
      image = gtk.Image()
      image.set_from_pixbuf(pixbuf)
      self.advance = gtk.Button()
      self.advance.add(image)
      image.show()
      self.advance.connect("clicked", self.callback, "Advance")
      self.hbox10.pack_end(self.advance)
      self.advance.show()
      self.tooltips.set_tip(self.advance, ln.advance_tip)
      
      # we are done messing with hbox7 so lets show it
      self.hbox7.show()
      # ditto
      self.hbox10.show()
      
      # Now to the interesting stuff.

      self.hbox4 = gtk.HBox(False, 0)
      self.vbox6.pack_start(self.hbox4, True, True, 0)
      
      # Boxes 3L and 3R contain our media players
      self.vbox3L = gtk.VBox(False, 0)
      self.vbox3L.set_border_width(2)
      self.hbox4.pack_start(self.vbox3L, True, True, 0)

      # A vertical box for our main volume controls
      self.vboxvol = gtk.VBox(False, 0)
      self.vboxvol.set_border_width(2)
      self.volframe = gtk.Frame()
      self.volframe.viewlevels = (5,)
      self.volframe.set_border_width(5)
      self.volframe.set_shadow_type(gtk.SHADOW_ETCHED_IN)
      self.volframe.add(self.vboxvol)
      self.volframe.show()
      self.hbox4.pack_start(self.volframe, False, True, 4)
           
      # A pictoral volume label above horizontally-stacked volume control(s)
      image = gtk.Image()
      image.set_from_file(pkgdatadir + "volume2" + gfext)
      self.vboxvol.pack_start(image, False, False, 0)
      image.show()
      hboxvol = gtk.HBox(True, 0)
      self.vboxvol.pack_start(hboxvol, True, True, 0)
      hboxvol.show()
      
      # Primary volume control
      self.deckadj = gtk.Adjustment(100.0, 0.0, 100.0, 1.0, 6.0)
      self.deckadj.connect("value_changed", self.cb_deckvol)
      self.deckvol = gtk.VScale(self.deckadj)
      self.deckvol.set_update_policy(gtk.UPDATE_CONTINUOUS)
      self.deckvol.set_draw_value(False)
      self.deckvol.set_inverted(True)
      hboxvol.pack_start(self.deckvol, False, False, 6)
      self.deckvol.show()
      self.tooltips.set_tip(self.deckvol, ln.common_volume_control_tip)

      # Secondary volume controller, visible when using separate player volumes
      self.deck2adj = gtk.Adjustment(100.0, 0.0, 100.0, 1.0, 6.0)
      self.deck2adj.connect("value_changed", self.cb_deckvol)
      self.deck2vol = gtk.VScale(self.deck2adj)
      self.deck2vol.set_update_policy(gtk.UPDATE_CONTINUOUS)
      self.deck2vol.set_draw_value(False)
      self.deck2vol.set_inverted(True)
      hboxvol.pack_start(self.deck2vol, False, False, 0)
      self.tooltips.set_tip(self.deck2vol, ln.right_volume_control_tip)

      self.spacerbox = gtk.VBox()
      self.spacerbox.set_size_request(1, 5)
      self.vboxvol.pack_start(self.spacerbox, False, False, 0)
       
      pixbuf = gtk.gdk.pixbuf_new_from_file(pkgdatadir + "pbphone" + gfext)
      pixbuf = pixbuf.scale_simple(20, 17, gtk.gdk.INTERP_HYPER)
      self.pbphoneimage = gtk.Image()
      self.pbphoneimage.set_from_pixbuf(pixbuf)
      self.vboxvol.pack_start(self.pbphoneimage, False, False, 0)
      
      self.mixbackadj = gtk.Adjustment(50.0, 0.0, 100.0, 1.0, 6.0)
      self.mixbackadj.connect("value_changed", self.cb_deckvol)
      self.mixback = gtk.VScale(self.mixbackadj)
      self.mixback.set_update_policy(gtk.UPDATE_CONTINUOUS)
      self.mixback.set_draw_value(False)
      self.mixback.set_inverted(True)
      self.vboxvol.pack_start(self.mixback, True, True, 0)
      self.tooltips.set_tip(self.mixback, ln.voip_mixback_volume_control_tip)
      
      self.vboxvol.show()
      
      # A box for the second deck.
      self.vbox3R = gtk.VBox(False, 0)
      self.vbox3R.viewlevels = (5,)
      self.vbox3R.set_border_width(2)
      self.hbox4.pack_start(self.vbox3R, True, True, 0)
      
      # hbox4 is full now so let's show it.
      self.hbox4.show()
      
      # The contents of the two player panes 3L and 3R are next up
      # The two identical players have been moved into one class
      
      self.player_left = IDJC_Media_Player(self.vbox3L, "left", self)
      self.vbox3L.show()
      
      self.player_right = IDJC_Media_Player(self.vbox3R, "right", self)
      self.vbox3R.show()
      
      # A track history window to help with announcements

      history_expander_hbox = gtk.HBox()
      self.history_expander = gtk.expander_new_with_mnemonic(ln.tracks_played)
      history_expander_hbox.pack_start(self.history_expander, True, True, 6)
      self.history_expander.connect("notify::expanded", self.expandercallback)
      self.history_expander.show()
      self.vbox6.pack_start(history_expander_hbox, False, False, 0)
      history_expander_hbox.show()
      
      self.history_vbox = gtk.VBox()
      history_hbox = gtk.HBox()
      self.history_vbox.pack_start(history_hbox, True, True, 0)
      self.vbox6.pack_start(self.history_vbox, True, True, 0)
      #self.history_vbox.show()
      history_hbox.show()
      history_frame = gtk.Frame()
      history_hbox.pack_start(history_frame, True, True, 6)
      history_frame.show()
      history_frame.set_border_width(0)
      self.history_window = gtk.ScrolledWindow()
      history_frame.add(self.history_window)
      self.history_window.set_border_width(4)
      self.history_window.show()
      self.history_window.set_size_request(-1, 81)
      self.history_window.set_shadow_type(gtk.SHADOW_IN)
      self.history_window.set_policy(gtk.POLICY_NEVER, gtk.POLICY_ALWAYS)
      
      history_clear_box = gtk.HBox()
      self.history_clear = gtk.Button(" " + ln.track_history_clear + " ")
      self.history_clear.connect("clicked", self.callback, "Clear History") 
      history_clear_box.pack_start(self.history_clear, True, False, 0)
      self.history_clear.show()
      self.history_vbox.pack_start(history_clear_box, False, False, 1)
      #history_clear_box.show()
      
      spacer = gtk.VBox()
      self.history_vbox.pack_start(spacer, False, False, 1)
      spacer.show()
      
      self.history_textview = gtk.TextView()
      self.history_textview.connect("populate-popup", self.cb_history_populate)
      self.history_window.add(self.history_textview)
      self.history_textview.show()
      self.history_textview.set_cursor_visible(False)
      self.history_textview.set_editable(False)
      self.history_textview.set_wrap_mode(gtk.WRAP_CHAR)
      self.history_buffer = self.history_textview.get_buffer()
      
      self.abox = gtk.HBox()
      self.abox.viewlevels = (5,)
      self.abox.set_border_width(2)
      self.vbox6.pack_start(self.abox, False, False, 0)
      self.abox.show()
      
      # The crossfader.  No DJ should be without one. ;)
      self.outercrossbox = gtk.HBox()
      self.outercrossbox.viewlevels = (5,)
      crossframe = gtk.Frame()
      self.outercrossbox.pack_start(crossframe, True, True, 6)
      self.outercrossbox.show()
      crossframe.set_border_width(0)
      self.crossbox = gtk.HBox()
      crossframe.add(self.crossbox)
      crossframe.show()
      self.crossbox.set_border_width(2)
      self.crossbox.set_spacing(3)
      
      cross_sizegroup = gtk.SizeGroup(gtk.SIZE_GROUP_HORIZONTAL)
      cross_sizegroup2 = gtk.SizeGroup(gtk.SIZE_GROUP_HORIZONTAL)
      sg3 = gtk.SizeGroup(gtk.SIZE_GROUP_VERTICAL)
            
      smvbox = gtk.VBox()
      label = gtk.Label(ln.monitor)
      attrlist = pango.AttrList()
      attrlist.insert(pango.AttrSize(8000, 0, len(ln.monitor)))
      label.set_attributes(attrlist)
      smvbox.add(label)
      label.show()
      
      frame = gtk.Frame()
      frame.set_shadow_type(gtk.SHADOW_NONE)
      smhbox = gtk.HBox()
      self.listen_dj = gtk.RadioButton(None, ln.monitor_dj)
      smhbox.add(self.listen_dj)
      self.listen_dj.show()
      self.listen_stream = gtk.RadioButton(self.listen_dj, ln.monitor_stream)
      smhbox.add(self.listen_stream)
      self.listen_stream.show()
      frame.add(smhbox)
      smhbox.show()
      smvbox.add(frame)
      frame.show()
      sg3.add_widget(frame)
      
      self.listen_stream.connect("toggled", self.cb_toggle, "stream-mon")
      self.tooltips.set_tip(smvbox, ln.stream_mon_tip)
      
      cross_sizegroup.add_widget(smhbox)
      self.crossbox.pack_start(smvbox, False, False, 0)
      smvbox.show()

      # metadata source selector combo box
      mvbox = gtk.VBox()
      label = gtk.Label(ln.metadata_source_label)
      attrlist = pango.AttrList()
      attrlist.insert(pango.AttrSize(8000, 0, len(ln.metadata_source_label)))
      label.set_attributes(attrlist)
      mvbox.add(label)
      label.show()
      self.metadata_source = gtk.combo_box_new_text()
      self.metadata_source.append_text(ln.metadata_source_left_deck)
      self.metadata_source.append_text(ln.metadata_source_right_deck)
      self.metadata_source.append_text(ln.metadata_source_last_played)
      self.metadata_source.append_text(ln.metadata_source_crossfader)
      self.metadata_source.append_text(ln.metadata_source_none)
      self.metadata_source.set_active(3)
      cross_sizegroup.add_widget(self.metadata_source)
      self.metadata_source.connect("changed", self.cb_metadata_source)
      self.tooltips.set_tip(self.metadata_source, ln.metadata_source_tip)
      mvbox.add(self.metadata_source)
      self.metadata_source.show()
      self.crossbox.pack_start(mvbox, False, False, 0)
      mvbox.show()
      cross_sizegroup2.add_widget(self.metadata_source)
      sg3.add_widget(self.metadata_source)
      
      plvbox = gtk.VBox()
      label = gtk.Label(ln.l)
      attrlist = pango.AttrList()
      attrlist.insert(pango.AttrSize(8000, 0, len(ln.l)))
      label.set_attributes(attrlist)
      plvbox.add(label)
      label.show()
      self.passleft = make_arrow_button(self, gtk.ARROW_LEFT, gtk.SHADOW_NONE, "cfmleft")
      plvbox.add(self.passleft)
      self.passleft.show()
      self.crossbox.pack_start(plvbox, False, False, 0)
      plvbox.show()
      self.tooltips.set_tip(plvbox, ln.cross_left_tip)
      sg3.add_widget(self.passleft)
      
      self.crossadj = gtk.Adjustment(0.0, 0.0, 100.0, 1.0, 3.0, 0.0)
      self.crossadj.connect("value_changed", self.cb_crossfade)      
      cvbox = gtk.VBox()
      label = gtk.Label(ln.crossfader)
      attrlist = pango.AttrList()
      attrlist.insert(pango.AttrSize(8000, 0, len(ln.crossfader)))
      label.set_attributes(attrlist)
      cvbox.add(label)
      label.show()
      self.crossfade = gtk.HScale(self.crossadj)
      self.crossfade.set_update_policy(gtk.UPDATE_CONTINUOUS)
      self.crossfade.set_draw_value(False)
      cvbox.add(self.crossfade)
      self.crossfade.show()
      self.crossbox.pack_start(cvbox, True, True, 0)
      cvbox.show()
      self.vbox6.pack_start(self.outercrossbox, False, False, 2)
      self.tooltips.set_tip(cvbox, ln.crossfader_tip)

      prvbox = gtk.VBox()
      label = gtk.Label(ln.r)
      attrlist = pango.AttrList()
      attrlist.insert(pango.AttrSize(8000, 0, len(ln.r)))
      label.set_attributes(attrlist)
      prvbox.add(label)
      label.show()
      self.passright = make_arrow_button(self, gtk.ARROW_RIGHT, gtk.SHADOW_NONE, "cfmright")
      prvbox.add(self.passright)
      self.passright.show()
      self.crossbox.pack_start(prvbox, False, False, 0)
      prvbox.show()
      self.tooltips.set_tip(prvbox, ln.cross_right_tip)
      sg3.add_widget(self.passright)
      
      patternbox = gtk.HBox()
      patternbox.set_spacing(2)
      sg4 = gtk.SizeGroup(gtk.SIZE_GROUP_VERTICAL)
      
      passbox = gtk.VBox()
      label = gtk.Label(ln.middle)
      attrlist = pango.AttrList()
      attrlist.insert(pango.AttrSize(8000, 0, len(ln.middle)))
      label.set_attributes(attrlist)
      label.show()
      passbox.add(label)
      passhbox = gtk.HBox()
      passhbox.set_spacing(2)
      passbox.add(passhbox)
      passhbox.show()
      patternbox.pack_start(passbox, False, False, 0)
      passbox.show()
      
      self.passmidleft = make_arrow_button(self, gtk.ARROW_UP, gtk.SHADOW_NONE, "cfmmidl")
      sg4.add_widget(self.passmidleft)
      passhbox.pack_start(self.passmidleft, False, False, 0)
      self.passmidleft.show()
      self.tooltips.set_tip(self.passmidleft, ln.cross_middle_tip)
      
      self.passmidright = make_arrow_button(self, gtk.ARROW_UP, gtk.SHADOW_NONE, "cfmmidr")
      passhbox.pack_start(self.passmidright, False, False, 0)
      self.passmidright.show()
      self.tooltips.set_tip(self.passmidright, ln.cross_middle_tip)
      sg4.add_widget(self.passmidright)
      
      pvbox = gtk.VBox()
      label = gtk.Label(ln.response)
      attrlist = pango.AttrList()
      attrlist.insert(pango.AttrSize(8000, 0, len(ln.response)))
      label.set_attributes(attrlist)
      pvbox.add(label)
      label.show()
      liststore = gtk.ListStore(gtk.gdk.Pixbuf)
      self.crosspattern = gtk.ComboBox(liststore)
      cell = gtk.CellRendererPixbuf()
      self.crosspattern.pack_start(cell, True)
      self.crosspattern.add_attribute(cell, 'pixbuf', 0)
      liststore.append((gtk.gdk.pixbuf_new_from_file(pkgdatadir + "classic_cross" + gfext), ))
      liststore.append((gtk.gdk.pixbuf_new_from_file(pkgdatadir + "mk2_cross" + gfext), ))
      pvbox.pack_start(self.crosspattern, True, True, 0)
      self.crosspattern.show()
      self.crossbox.pack_start(patternbox, False, False, 0)
      patternbox.show()
      cross_sizegroup2.add_widget(patternbox)
      self.crosspattern.set_active(0)
      self.crosspattern.connect("changed", self.cb_crosspattern)
      self.tooltips.set_tip(self.crosspattern, ln.cross_pattern_tip)
      patternbox.pack_start(pvbox, True, True, 0)
      pvbox.show()
      
      
      sg4.add_widget(self.crosspattern)
      
      passbox = gtk.HBox()
      passbox.set_spacing(2)
      
      tvbox = gtk.VBox()
      label = gtk.Label(ln.time)
      attrlist = pango.AttrList()
      attrlist.insert(pango.AttrSize(8000, 0, len(ln.time)))
      label.set_attributes(attrlist)
      tvbox.add(label)
      label.show()
      self.passspeed_adj = gtk.Adjustment(1.0, 0.25, 20.0, 0.25, 0.25)
      psvbox = gtk.VBox()
      hs = gtk.HSeparator()
      psvbox.pack_start(hs, False)
      hs.show()
      self.passspeed = gtk.SpinButton(self.passspeed_adj, 0, 2)
      psvbox.pack_start(self.passspeed, True, False)
      self.passspeed.show()
      hs = gtk.HSeparator()
      psvbox.pack_start(hs, False)
      hs.show()
      tvbox.pack_start(psvbox, False, False, 0)
      psvbox.show()
      self.tooltips.set_tip(tvbox, ln.pass_speed_tip)
      passbox.pack_start(tvbox, False, False, 0)
      tvbox.show()
      sg4.add_widget(psvbox)
      
      pvbox = gtk.VBox()
      label = gtk.Label(ln.crosspass)
      attrlist = pango.AttrList()
      attrlist.insert(pango.AttrSize(8000, 0, len(ln.crosspass)))
      label.set_attributes(attrlist)
      pvbox.add(label)
      label.show()
      image = gtk.Image()
      image.set_from_file(pkgdatadir + "pass" + gfext)
      image.show()
      self.passbutton = gtk.Button()
      self.passbutton.set_size_request(53, -1)
      self.passbutton.add(image)
      self.passbutton.connect("clicked", self.callback, "pass-crossfader")
      pvbox.add(self.passbutton)
      self.passbutton.show()
      self.tooltips.set_tip(pvbox, ln.pass_button_tip)
      passbox.pack_start(pvbox, True, True, 0)
      pvbox.show()
      sg4.add_widget(self.passbutton)
     
      self.crossbox.pack_start(passbox, False, False, 0)
      cross_sizegroup.add_widget(passbox)
      passbox.show()
      self.crossbox.show()
      
      abox = gtk.HBox()
      abox.set_border_width(1)
      self.vbox6.pack_start(abox, False, False, 0)
      abox.show()
      
      # We are done with vbox6 so lets show it
      self.vbox6.show()
      
      # The various meters
      self.metereventbox = gtk.EventBox()
      self.metereventbox.viewlevels = (5,)
      self.meterbox = gtk.HBox()
      self.metereventbox.add(self.meterbox)
      self.rightpane.pack_start(self.metereventbox, False, False, 0)
      self.meterbox.show()
      self.metereventbox.show()

      # Box contains stream peak, vu and connection status, listener stats.
      self.streammeterbox = PaddedVBox(4, 2, 0, 1, 6)
      self.meterbox.pack_start(self.streammeterbox, False, False, 0)
      self.streammeterbox.show()

      # Table that contains 1, 2, or 4 microphone meters.
      self.micmeterbox = PaddedVBox(4, 2, 0, 1, 6)
      self.meterbox.pack_start(self.micmeterbox, False, False, 0)
      self.micmeterbox.show()
      
      self.str_l_peak = peakholdmeter()
      self.str_r_peak = peakholdmeter() 
      self.stream_peak_box = make_meter_unit(ln.str_peak, self.str_l_peak, self.str_r_peak)
      self.streammeterbox.pack_start(self.stream_peak_box)
      self.stream_peak_box.show()
      self.tooltips.set_tip(self.stream_peak_box, ln.stream_peak_meter_tip)

      sg = gtk.SizeGroup(gtk.SIZE_GROUP_HORIZONTAL)
      self.stream_indicator = []
      for i in range(idjc_config.num_streamers):
         self.stream_indicator.append(StreamMeter(1, 100))
      self.stream_indicator_box, self.listener_indicator = make_stream_meter_unit(ln.streams, self.stream_indicator, self.tooltips)
      self.streammeterbox.pack_start(self.stream_indicator_box, False, False, 0)
      self.stream_indicator_box.show()
      sg.add_widget(self.stream_indicator_box)

      self.str_l_rms_vu = vumeter()
      self.str_r_rms_vu = vumeter()
      stream_vu_box = make_meter_unit(ln.str_vu, self.str_l_rms_vu, self.str_r_rms_vu)
      self.streammeterbox.pack_start(stream_vu_box)
      stream_vu_box.show()
      self.tooltips.set_tip(stream_vu_box, ln.stream_vu_meter_tip)
       
      self.mic_meters = [MicMeter("Mic ", i) for i in range(1, idjc_config.num_micpairs * 2 + 1)]
      if len(self.mic_meters) <= 4:
         for meter in self.mic_meters:
            self.micmeterbox.pack_start(meter)
            meter.show()
      else:
         table = gtk.Table(idjc_config.num_micpairs, 2)
         table.set_row_spacings(4)
         table.set_col_spacings(4)
         self.micmeterbox.pack_start(table)
         table.show()
         for i, meter in enumerate(self.mic_meters):
            row, col = divmod(i, 2)
            table.attach(meter, col, col + 1, row, row + 1)
            meter.show()
      
      self.tooltips.set_tip(self.micmeterbox, ln.mic_meter_tip)

      # Main window context menu
      self.app_menu = gtk.Menu()
      self.app_menu.show()
      self.window.connect_object("event", self.menu_activate, self.app_menu)
      
      aboutimg = gtk.Image()
      aboutimg.set_from_stock(gtk.STOCK_ABOUT, gtk.ICON_SIZE_MENU)
      aboutimg.show()
      aboutlabel = gtk.Label("About")
      aboutlabel.show()
      aboutbox = gtk.HBox()
      aboutbox.show()
      aboutbox.pack_start(aboutimg, False, False, 0)
      aboutbox.pack_start(aboutlabel, False, False, 0)
      menu_about = gtk.MenuItem(None, False)
      menu_about.connect("activate", self.callback, "Show about")
      menu_about.show()
      menu_about.add(aboutbox)
      self.app_menu.append(menu_about)
      
      sep = gtk.SeparatorMenuItem()
      sep.show()
      self.app_menu.append(sep)
      
      viewimg = gtk.Image()
      viewimg.show()
      viewlabel = gtk.Label("View")
      viewlabel.show()
      viewbox = gtk.HBox()
      viewbox.show()
      viewbox.pack_start(viewimg, False, False, 8)
      viewbox.pack_start(viewlabel, False, False, 0)
      menu_view = gtk.MenuItem(None, False)
      menu_view.show()
      menu_view.add(viewbox)
      self.app_menu.append(menu_view)
     
      sep = gtk.SeparatorMenuItem()
      sep.show()
      self.app_menu.append(sep)
      
      quitimg = gtk.Image()
      quitimg.set_from_stock(gtk.STOCK_QUIT, gtk.ICON_SIZE_MENU)
      quitimg.show()
      quitlabel = gtk.Label("Quit")
      quitlabel.show()
      quitbox = gtk.HBox()
      quitbox.show()
      quitbox.pack_start(quitimg, False, False, 0)
      quitbox.pack_start(quitlabel, False, False, 0)
      menu_quit = gtk.MenuItem(None, False)
      menu_quit.connect_object("activate", self.delete_event, self.window, None)
      menu_quit.show()
      menu_quit.add(quitbox)
      self.app_menu.append(menu_quit)

      # The view submenu of app_menu
      view_menu = gtk.Menu()
      view_menu.show()
      menu_view.set_submenu(view_menu)
      
      menu_str_meters = gtk.CheckMenuItem()
      menu_str_meters.show()
      view_menu.append(menu_str_meters)
      self.str_meters_action = gtk.ToggleAction(None, ln.show_stream_meters, None, None)
      self.str_meters_action.connect_proxy(menu_str_meters)

      menu_mic_meters = gtk.CheckMenuItem()
      menu_mic_meters.show()
      view_menu.append(menu_mic_meters)
      self.mic_meters_action = gtk.ToggleAction(None, ln.show_microphone_meters, None, None)
      self.mic_meters_action.connect_proxy(menu_mic_meters)
      
      sep = gtk.SeparatorMenuItem()
      sep.show()
      view_menu.append(sep)
      
      self.menu_feature_set = gtk.CheckMenuItem(ln.fully_featured)
      self.menu_feature_set.set_active(True)
      self.menu_feature_set.connect("activate", self.callback, "Features")
      self.menu_feature_set.show()
      view_menu.append(self.menu_feature_set)
      
      sep = gtk.SeparatorMenuItem()
      sep.show()
      view_menu.append(sep)
      
      menu_prefs = gtk.MenuItem(ln.prefs_button)
      menu_prefs.connect("activate", self.callback, "Prefs")
      menu_prefs.show()
      view_menu.append(menu_prefs)
      
      menu_server = gtk.MenuItem(ln.output_button)
      menu_server.connect("activate", self.callback, "Server")
      menu_server.show()
      view_menu.append(menu_server)
      
      menu_jingles = gtk.MenuItem(ln.jingles_button)
      menu_jingles.connect("activate", self.callback, "Jingles")
      menu_jingles.show()
      view_menu.append(menu_jingles)

      # menu for closing prefs, server, jingles

      self.close_menu = gtk.Menu()
      close_menu_item = gtk.MenuItem(ln.window_close)
      self.close_menu.add(close_menu_item)
      self.close_menu.show()
      close_menu_item.show()
      close_menu_item.connect("activate", self.close_window, self.close_menu)

      # Create the jingles player
      self.jingles = jingles(self)

      # Variable initialisation
      self.songname = u""
      self.newmetadata = False
      self.showing_left_file_requester = False
      self.showing_right_file_requester = False
      self.metadata = ""
      self.simplemixer = False
      self.crosspass = 0

      # initialize metadata source setting
      self.last_player = ""
      self.METADATA_LEFT_DECK = 0
      self.METADATA_RIGHT_DECK = 1
      self.METADATA_LAST_PLAYED = 2
      self.METADATA_CROSSFADER = 3
      self.METADATA_NONE = 4
      self.metadata_src = self.METADATA_CROSSFADER

      self.alarm = False
      self.NO_PHONE = 0
      self.PUBLIC_PHONE = 1
      self.PRIVATE_PHONE = 2
      self.mixermode = self.NO_PHONE
      self.jingles_playing = int_object(0)
      self.interlude_playing = int_object(0)
      self.player_left.playtime_elapsed = int_object(0)
      self.player_right.playtime_elapsed = int_object(0)
      self.player_left.mixer_playing = int_object(0)
      self.player_right.mixer_playing = int_object(0)
      self.player_left.mixer_signal_f = int_object(0)
      self.player_right.mixer_signal_f = int_object(0)
      self.player_left.mixer_cid = int_object(0)
      self.player_right.mixer_cid = int_object(0)
      self.left_compression_level = int_object(0)
      self.right_compression_level = int_object(0)
      self.left_deess_level = int_object(0)
      self.right_deess_level = int_object(0)
      self.left_noisegate_level = int_object(0)
      self.right_noisegate_level = int_object(0)
      self.jingles.mixer_jingles_cid = int_object(0)
      self.jingles.mixer_interlude_cid = int_object(0)
      self.player_left.runout = int_object(0)
      self.player_right.runout = int_object(0)
      self.metadata_left_ctrl = int_object(0)
      self.metadata_right_ctrl = int_object(0)
      self.fullwinx = int_object(1)
      self.fullwiny = int_object(1)
      self.minwinx = int_object(1)
      self.minwiny = int_object(1)
      self.in_vu_timeout = False
      self.vucounter = 0
      self.session_filename = self.idjc + "main_session"
      self.files_played = {}
      self.files_played_offline = {}
      
      # create or empty out the command file which should not exist when idjc is not running
      # This interface should be replaced with D-Bus
      try:
         file = open(self.idjc + "command", "w")
      except IOError:
         print "unable to initialise the command file"
         raise self.initfailed
      else:
         fcntl.flock(file.fileno(), fcntl.LOCK_EX)
         file.truncate(0)
         fcntl.flock(file.fileno(), fcntl.LOCK_UN)
         file.close()

      # Variable map for stuff read from the mixer
      self.vumap = {
         "str_l_peak"   : self.str_l_peak,
         "str_r_peak"   : self.str_r_peak,
         "str_l_rms"    : self.str_l_rms_vu,
         "str_r_rms"    : self.str_r_rms_vu,
         "jingles_playing"          : self.jingles_playing,
         "left_elapsed"             : self.player_left.playtime_elapsed,
         "right_elapsed"            : self.player_right.playtime_elapsed,
         "left_playing"             : self.player_left.mixer_playing,
         "right_playing"            : self.player_right.mixer_playing,
         "interlude_playing"        : self.interlude_playing,
         "left_signal"              : self.player_left.mixer_signal_f,
         "right_signal"             : self.player_right.mixer_signal_f,
         "left_cid"                 : self.player_left.mixer_cid,
         "right_cid"                : self.player_right.mixer_cid,
         "jingles_cid"              : self.jingles.mixer_jingles_cid,
         "interlude_cid"            : self.jingles.mixer_interlude_cid,
         "left_audio_runout"        : self.player_left.runout,
         "right_audio_runout"       : self.player_right.runout,
         "left_additional_metadata" : self.metadata_left_ctrl,
         "right_additional_metadata": self.metadata_right_ctrl
         }
         
      for i, mic in enumerate(self.mic_meters):
         self.vumap.update({"mic_%d_levels" % (i + 1): mic})

      self.controls= IDJCcontrols.Controls(self)
      self.controls.load_prefs()

      self.window.realize()     # prevent ubuntu crash when activating vu meters
      media_sg = gtk.SizeGroup(gtk.SIZE_GROUP_HORIZONTAL)
      media_sg.add_widget(self.vbox3L)
      media_sg.add_widget(self.vbox3R)
      
      self.server_window = SourceClientGui(self)
      self.prefs_window = mixprefs(self)
      self.prefs_window.load_player_prefs()
      self.prefs_window.apply_player_prefs()
      self.prefs_window.ask_profile.set_active(self.ask_profile_next_time)
      self.vutimeout = gobject.timeout_add(50, self.vu_update)
      self.statstimeout = gobject.timeout_add(100, self.stats_update)
      
      signal.signal(signal.SIGINT, self.destroy)
      if not self.simplemixer:
         self.window.resize(self.fullwinx, self.fullwiny)
      else:
         self.window.resize(self.minwinx, self.minwiny)
      self.window.connect("configure_event", self.configure_event)
      self.jingles.window.resize(self.jingles.jingleswinx, self.jingles.jingleswiny)

      if self.prefs_window.restore_session_option.get_active():
         print "Restoring previous session"
         self.player_left.restore_session()
         self.player_right.restore_session()
         self.restore_session()
      self.session_loaded = True
       
      self.prefs_button.connect("button-press-event", self.close_menu_attach, self.prefs_window.window)
      self.server_button.connect("button-press-event", self.close_menu_attach, self.server_window.window)
      self.jingles_button.connect("button-press-event", self.close_menu_attach, self.jingles.window)
       
      self.window.set_focus_chain((self.player_left.scrolllist, self.player_right.scrolllist))
       
      self.prefs_window.appstart_event.activate()       # run user specified commands for application start
      self.server_window.update_metadata()              # metadata formatting -> backend
      
      self.window.forall(self.strip_focusability)
      self.topleftpane.fuzzyentry.set_flags(gtk.CAN_FOCUS)
      self.topleftpane.whereentry.set_flags(gtk.CAN_FOCUS)
      self.player_left.treeview.set_flags(gtk.CAN_FOCUS)
      self.player_right.treeview.set_flags(gtk.CAN_FOCUS)
      self.player_left.treeview.grab_focus()
     
      self.window.add_events(gtk.gdk.KEY_PRESS_MASK)
      self.window.connect("key-press-event", self.cb_key_capture)
      self.window.connect("key-release-event", self.cb_key_capture)
     
      self.window.show()
      
      self.player_left.treeview.emit("cursor-changed")
      self.player_right.treeview.emit("cursor-changed")

      mic = os.environ["MICROPHONE"]
      for each in mic:
         self.mic_opener.open(each)

      aux = os.environ["AUXILIARY"]
      if "1" in aux:
         self.aux_select.set_active(True)

      voip = os.environ["VOIPMODE"]
      if voip == "1":
         self.greenphone.set_active(True)
      elif voip == "2":
         self.redphone.set_active(True)

      serv = os.environ["SERVERSTART"]
      servtabs = self.server_window.streamtabframe.tabs
      for n in range(len(servtabs)):
         if chr(n + ord("1")) in serv:
            servtabs[n].server_connect.set_active(True)

   def main(self):
      gtk.main()

def environment_variables_okay():
   # Shows a dialog box when one or more of the helper programs is missing
   environvars = (
      ("jackd from the jack-audio-connection-kit package\n", ("jackd", "missing")),)
   error_message = "The following programs were found to be missing...\n\n"
   for each in environvars:
      if os.environ.get(each[1][0], "") == "":
         if each[1][1] == "missing":
            error_message = error_message + each[0]     # append the appropriate error message
         os.environ[each[1][0]] = each[1][1]
   if error_message[-2:] != "\n\n":
      error_message = error_message + "\n\t\tDo you want to continue?"
      message_dialog = gtk.MessageDialog(None, 0, gtk.MESSAGE_INFO, gtk.BUTTONS_YES_NO, error_message)
      message_dialog.set_icon_from_file(pkgdatadir + "icon" + gfext)
      message_dialog.set_default_response(gtk.RESPONSE_YES)
      if message_dialog.run() == gtk.RESPONSE_NO:
         message_dialog.destroy()
         return False
      else:
         message_dialog.destroy()
   return True

@threadslock
def main():
   if environment_variables_okay() == True:
      try:
         run_instance = MainWindow()
      except (MainWindow.initfailed,
              MainWindow.initcleanexit,
              KeyboardInterrupt):
         return 5
      else:
         try:
            run_instance.main()
         except KeyboardInterrupt:
            return 5
         else:
            return 0
   return 5

if __name__ == "__main__":
   gtk.gdk.threads_init()
   sys.exit(main())
