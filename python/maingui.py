#   maingui.py: Main python code of IDJC
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

         
import os
import sys
import fcntl
import subprocess
import ConfigParser
import operator
import socket
import pickle
import stat
import signal
import time
import gettext
import itertools
import collections
import json

import glib
import gobject
import gtk
import cairo
import pango

from idjc import FGlobs, PGlobs
from .playergui import *
from .sourceclientgui import *
from .preferences import *
from .jingles import *
from .freefunctions import slot_object
from .freefunctions import rich_safe
from .gtkstuff import threadslock, WindowSizeTracker
from .gtkstuff import IconChooserButton, IconPreviewFileChooserDialog
from . import midicontrols
from .tooltips import main_tips
from . import p3db
from .prelims import *


t = gettext.translation(FGlobs.package_name, FGlobs.localedir, fallback=True)
_ = t.gettext

args = ArgumentParserImplementation().parse_args()
pm = ProfileManager()
set_tip = main_tips.set_tip


METER_TEXT_SIZE = 8000


class MenuMixin(object):
   def build(self, menu, autowipe=False, use_underline=True):
      def mkitems(x, how=gtk.MenuItem):
         for name, text in x:
            mi = how(text)
            mi.set_use_underline(use_underline)
            menu.append(mi)
            mi.show()
            setattr(self, name + "menu_i", mi)
            if autowipe:
               mi.connect("activate", self.cb_autowipe)

            if issubclass(how, gtk.CheckMenuItem) and use_underline == True:
               a = gtk.ToggleAction(None, text, None, None)
               a.connect_proxy(mi)
               setattr(self, name + "menu_a", a)

      return mkitems
      
   def submenu(self, mi, name):
      m = gtk.Menu()
      mi.set_submenu(m)
      m.show()
      setattr(self, name + "menu", m)
      return m

   def sep(self, menu):
      s = gtk.SeparatorMenuItem()
      menu.append(s)
      s.show()
      
   def cb_autowipe(self, mi):
      mi.get_submenu().foreach(lambda w: w.destroy())


class MainMenu(gtk.MenuBar, MenuMixin):
   def __init__(self):
      gtk.MenuBar.__init__(self)

      self.build(self)((("file", _('File')), ("view", _('View')), ("jack", _('JACK Ports')), ("help", _('Help'))))
      self.submenu(self.filemenu_i, "file")
      self.build(self.filemenu, autowipe=True)((("streams", _('Streams')), ("recorders", _('Recorders'))))

      self.sep(self.filemenu)
      self.build(self.filemenu)((("quit", gtk.STOCK_QUIT),), gtk.ImageMenuItem)

      for each in ("streams", "recorders"):
         m = self.submenu(getattr(self, each + "menu_i"), each)
         
      self.submenu(self.viewmenu_i, "view")
      mkitems = self.build(self.viewmenu)
      mkitems(zip("output prefs jingles profiles".split(" "),
            (_('Output'), _('Preferences'), _('Jingles'), _('Profiles'))))
      self.sep(self.viewmenu)
      mkitems(zip("songdb chmeters strmeters".split(" "),
            (_('Music Database'), _('Channel Meters'), _('Output Meters'))), gtk.CheckMenuItem)

      self.submenu(self.jackmenu_i, "jack")

      self.submenu(self.helpmenu_i, "help")
      self.build(self.helpmenu)((("about", gtk.STOCK_ABOUT),), gtk.ImageMenuItem)

      """
      self.submenu(self.outputmenu_i, "output")

      for each in zip(("str_in_",) * 2, lr):
         self.jack.add_port(self.outputmenu, "".join(each))
      """


class JackMenu(MenuMixin):
   def __init__(self, menu, write, read):
      self.menu = menu
      self.write = write
      self.read = read
      self.ports = []
      self.pathname = pm.session_pathname
      self.session_type = pm.session_type

      self.build(menu.jackmenu)(zip("channels voip dsp mix midi output".split(), (_('Channels'), _('VoIP'), _('DSP'), _('Mix'), _('MIDI'), _('Output'))))
      self.submenu(self.channelsmenu_i, "channels")
      self.submenu(self.voipmenu_i, "voip")
      self.submenu(self.dspmenu_i, "dsp")
      self.submenu(self.mixmenu_i, "mix")
      self.submenu(self.midimenu_i, "midi")
      self.submenu(self.outputmenu_i, "output")
      
      out2_in2 = itertools.cycle(("_out_",)*2 + ("_in_",)*2)
      lr = itertools.cycle("lr")
      dj2_str2 = itertools.cycle(("dj",)*2 + ("str",)*2)
   
      for each in zip(("voip",) * 4, out2_in2, lr):
         self.add_port(self.voipmenu, "".join(each))

      for each in zip(("dsp",) * 4, out2_in2, lr):
         self.add_port(self.dspmenu, "".join(each))
         
      for each in zip(dj2_str2, ("_out_",)*4, lr):
         self.add_port(self.mixmenu, "".join(each))
         
      self.add_port(self.midimenu, "midi_control")
      
      for i in range(1, PGlobs.num_micpairs * 2 + 1):
         self.add_port(self.channelsmenu, "ch_in_" + str(i))

      for each in zip(("str_in_",) * 2, lr):
         self.add_port(self.outputmenu, "".join(each), "sc")

   def add_port(self, menu, port, prefix="mx"):
      pport = os.environ["%s_client_id" % prefix] + ":" + port
      self.ports.append(pport)
      self.build(menu, autowipe=True, use_underline=False)(((port, pport),))
      mi = getattr(self, port + "menu_i")
      sub = self.submenu(mi, port)
      mi.connect("activate", self.cb_port_connections, pport, sub)
      
   def cb_port_connections(self, mi, port, menu):
      reply = ""
      
      if "_in_" in port:
         filter_ = "outputs"
      elif "_out_" in port:
         filter_ = "inputs"
      elif "midi" in port:
         filter_ = "midioutputs"
      else:
         print "JackMenu.port_connections: unknown port type"
         return
         
      self.write("portread", "JFIL=%s\nJPRT=%s\nend\n" % (filter_, port))
      while not reply.startswith("jackports="):
         reply = self.read()
      reply = reply[10:].rstrip().split()
      if not reply:
         self.build(menu)((("noports", _('No compatible ports available.')),))
         self.noportsmenu_i.set_sensitive(False)
      else:
         for destport in reply:
            self.build(menu, use_underline=False)((("targetport", destport.lstrip("@")),), how=gtk.CheckMenuItem)
            mi = getattr(self, "targetportmenu_i")
            if destport.startswith("@"):
               mi.set_active(True)
            mi.connect("activate", self.cb_activate, port, destport.lstrip("@"))

   def cb_activate(self, mi, local, dest):
      cmd = "connect" if mi.get_active() else "disconnect"
      self.write(cmd, "JPRT=%s\nJPT2=%s\nend\n" % (local, dest))
      self.save()

   def get_playback_port_qty(self):
      self.write("portread", "JFIL=\nJPRT=\nend\n")
      reply = ""
      while not reply.startswith("jackports="):
         reply = self.read()
         
      pbports = len([x for x in reply[10:].strip().split() if x.startswith("system:playback_")])
      return pbports
      
   def standard_save(self):
      if self.session_type == "L0":
         self._save()

   def session_save(self, where=None):
      self._save(where)
      try:
         subprocess.call(["notify-send", "%s:%s %s Session Saved" % (PGlobs.app_shortform, pm.profile, self.session_type)])
      except OSError:
         pass

   def _save(self, where=None):
      total = []
      for port in self.ports:
         element = [port]
         self.write("portread", "JFIL=\nJPRT=%s\nend\n" % port)
         reply = ""
         while not reply.startswith("jackports="):
            reply = self.read()
         
         element.append([x.lstrip("@") for x in reply[10:].rstrip().split() if x.startswith("@")])
         total.append(element)
      
      try:
         with open(where or self.pathname, "w") as f:
            json.dump(total, f)
      except Exception as e:
         print "problem writing", self.pathname
      else:
         print "jack connections saved"
         
   def load(self, where=None, restrict="", startup=False):
      try:
         with open(where or self.pathname) as f:
            cons = json.load(f)
      except Exception:
         print "problem reading", self.pathname
         if args.no_default_jack_connections:
            cons = []
         else:
            cons = """[
               ["{mx}:ch_in_1", ["system:capture_1"]],
               ["{mx}:ch_in_2", ["system:capture_2"]],
               ["{mx}:dj_out_l", ["system:playback_1"]],
               ["{mx}:dj_out_r", ["system:playback_2"]],
               ["{sc}:str_in_l", ["{mx}:str_out_l"]],
               ["{sc}:str_in_r", ["{mx}:str_out_r"]], """

            if self.get_playback_port_qty() < 8:
               cons += """
                  ["{mx}:str_out_l", ["system:playback_3", "{sc}:str_in_l"]],
                  ["{mx}:str_out_r", ["system:playback_4", "{sc}:str_in_r"]]] """
            else:
               cons += """
                  ["{mx}:str_out_l", ["system:playback_5", "{sc}:str_in_l"]],
                  ["{mx}:str_out_r", ["system:playback_6", "{sc}:str_in_r"]]] """

            cons = eval(cons.format(mx=os.environ["mx_client_id"], sc=os.environ["sc_client_id"]))

      if not startup or not args.no_jack_connections:
         for port, targets in cons:
            for target in targets:
               if target.startswith(restrict):
                  self.write("connect", "JPRT=%s\nJPT2=%s\nend\n" % (port, target))


 
class ColouredArea(gtk.DrawingArea):
   def __init__(self, colour=gtk.gdk.Color()):
      gtk.DrawingArea.__init__(self)
      self.colour = colour
      self.rect = gtk.gdk.Rectangle()
      self.connect("realize", self._on_realize)
      self.connect("configure-event", self._on_configure)
      self.connect("expose-event", self._on_expose)


   def set_colour(self, colour):
      self.colour = colour
      self.queue_draw_area(0, 0, self.rect.width, self.rect.height)


   def _on_realize(self, widget):
      self.gc = gtk.gdk.GC(self.window)


   def _on_configure(self, widget, event):
      self.rect.width = event.width
      self.rect.height = event.height
      

   def _on_expose(self, widget, event):
      self.gc.set_rgb_fg_color(self.colour)      
      self.window.draw_rectangle(self.gc, True, 0, 0, self.rect.width, self.rect.height)


class ColourButton(gtk.ColorButton):
   def get_text(self):
      return self.get_color().to_string()
      
   def set_text(self, string):
      self.set_color(gtk.gdk.Color(string))


class IconChooserButtonExtd(IconChooserButton):
   def get_text(self):
      return self.get_filename() or ""
      
   def set_text(self, filename):
      self.set_filename(filename or None)
      

class MicButton(gtk.ToggleButton):
   @property
   def flash(self):
      return self.__flash
   @flash.setter
   def flash(self, value):
      self.__flash = bool(value) and self.has_reminder_flash()
      self.__indicate()
  
   @staticmethod
   def __cb_toggle(self):
      self.__indicate()
      if self.get_active():
         self.set_colour(self.open_colour)
         self.opener_tab.button_was_on = True
      else:
         self.opener_tab.button_was_on = False

   def __indicate(self):
      if self.get_active():
         if self.flash:
            self.set_colour(self.flash_colour)
         else:
            self.set_colour(self.open_colour)
      else:
         self.set_colour(self.closed_colour)
         
         
   def set_colour(self, colour):
      for each in (self.ca1, self.ca2):
         each.set_colour(colour)


   def __init__(self, opener_settings, opener_tab, mic_agc_list):
      gtk.ToggleButton.__init__(self)

      self.opener_tab = opener_tab

      nsa = not opener_settings.button_numbers.get_active()

      self.open_colour = opener_settings.open_colour.get_color()
      self.closed_colour = opener_settings.closed_colour.get_color()
      self.flash_colour = opener_settings.reminder_colour.get_color()
      self.has_reminder_flash = opener_tab.has_reminder_flash.get_active

      attrlist = pango.AttrList()
      attrlist.insert(pango.AttrSize(METER_TEXT_SIZE, 0, 100))
      
      hbox = gtk.HBox()
      hbox.set_spacing(4)

      def make_indicator():
         ca = ColouredArea(self.closed_colour)
         width = opener_settings.indicator_width.get_value_as_int()
         if width:
            ca.set_size_request(width, -1)
            hbox.pack_start(ca, False)

         return ca
         
      self.ca1 = make_indicator()

      lvbox = gtk.VBox()
      hbox.pack_start(lvbox, False)

      self._ident_label = gtk.Label()
      self._ident_label.set_no_show_all(nsa)
      self._ident_label.set_alignment(0.0, 0.0)
      self._ident_label.set_attributes(attrlist)
      lvbox.pack_start(self._ident_label, False)
      
      self._chan_label3 = gtk.Label()
      self._chan_label3.set_no_show_all(nsa)
      self._chan_label3.set_alignment(0.0, 1.0)
      self._chan_label3.set_attributes(attrlist)
      lvbox.pack_end(self._chan_label3, False)

      pad = gtk.HBox()
      hbox.pack_start(pad)

      self._text_label = gtk.Label()
      text = opener_tab.button_text.get_text().strip()
      if text:
         self._text_label.set_text(text)
         hbox.pack_start(self._text_label, False)
     
      self._icon_image = gtk.Image()
      icon = opener_tab.icb.get_filename()
      try:
         pb = gtk.gdk.pixbuf_new_from_file_at_size(icon, 47, 20)
      except (TypeError, glib.GError):
         pass
      else:
         self._icon_image.set_from_pixbuf(pb)
         hbox.pack_start(self._icon_image, False)

      pad = gtk.HBox()
      hbox.pack_start(pad)
      
      rvbox = gtk.VBox()
      hbox.pack_start(rvbox, False)
      
      self._chan_label1 = gtk.Label()
      self._chan_label1.set_no_show_all(nsa)
      self._chan_label1.set_alignment(1.0, 0.0)
      self._chan_label1.set_attributes(attrlist)
      rvbox.pack_start(self._chan_label1, False)

      self._chan_label2 = gtk.Label()
      self._chan_label2.set_no_show_all(nsa)
      self._chan_label2.set_alignment(1.0, 1.0)
      self._chan_label2.set_attributes(attrlist)
      rvbox.pack_end(self._chan_label2, False)

      self.ca2 = make_indicator()

      self.add(hbox)

      to_close = ",".join(str(i) for i, cb in enumerate(opener_tab.closer_hbox.get_children(), start=1) if cb.get_active())
      if to_close:
         to_close = "!" + to_close

      self._ident_label.set_text("(%d)%s" % (opener_tab.ident, to_close))
      
      def labeltext():
         for blk in itertools.izip_longest(*(iter(mic_agc_list),) * 4):
            yield ",".join(x.ui_name for x in blk if x is not None)
      
      for text, label in zip(labeltext(),
               (self._chan_label1, self._chan_label2, self._chan_label3)):
         label.set_text(text)

      self.connect("toggled", self.__cb_toggle)
      self.__flash = False
      self.show_all()
   
   

class OpenerTab(gtk.VBox):
   __gsignals__ = { "changed" : (
                  gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, ())}

   def __init__(self, ident):
      gtk.VBox.__init__(self)
      self.set_border_width(6)
      self.set_spacing(4)
      self.label = gtk.Label()
      self.label.show()
      self.set_ident(ident)
      self.activedict = {}
      sg = gtk.SizeGroup(gtk.SIZE_GROUP_HORIZONTAL)
      lhbox = gtk.HBox()
      lhbox.set_spacing(3)
      label = gtk.Label(_('Text'))
      lhbox.pack_start(label, False)
      self.button_text = gtk.Entry()
      set_tip(self.button_text, _("The opener button's text."))
      self.button_text.connect("changed", lambda w: self.emit("changed"))
      sg.add_widget(self.button_text)
      lhbox.pack_start(self.button_text)
      
      spc = gtk.HBox()
      lhbox.pack_start(spc, False, padding=2)
      
      label = gtk.Label(_('Icon'))
      lhbox.pack_start(label, False)
      
      self.icon_chooser = IconPreviewFileChooserDialog("Choose An Icon",
                  buttons = (gtk.STOCK_CLEAR, gtk.RESPONSE_NONE,
                             gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                             gtk.STOCK_OK, gtk.RESPONSE_OK))
      self.icb = IconChooserButtonExtd(self.icon_chooser)
      set_tip(self.icb, _("The opener button's icon."))
      self.icb.connect("filename-changed", lambda w, r: self.emit("changed"))
      sg.add_widget(self.icb)
      lhbox.pack_start(self.icb, True)

      self.pack_start(lhbox, False)

      hbox = gtk.HBox()
      set_tip(hbox, _('The headroom is the amount by which to reduce player volume when this opener is active. Note that the actual amount will be the largest value of all the currently open buttons.'))
      self.pack_start(hbox, False)
      label = gtk.Label(_('The amount of headroom required (dB)'))
      label.set_alignment(0.0, 0.5)
      hbox.pack_start(label, False)
      self.headroom = gtk.SpinButton(gtk.Adjustment(0.0, 0.0, 32.0, 0.5), digits=1)
      self.headroom.connect("value-changed", lambda w: self.emit("changed"))
      hbox.pack_end(self.headroom, False)
      
      self.has_reminder_flash = gtk.CheckButton(_('This button will flash as a reminder to close'))
      set_tip(self.has_reminder_flash, _("After a number of seconds where a main player is active this button's status indicator will start to flash and will continue to do so until the button is closed or the player stops."))
      self.pack_start(self.has_reminder_flash, False)
      
      self.is_microphone = gtk.CheckButton(_('This button is to be treated as a microphone opener'))
      set_tip(self.is_microphone, _("The button will be grouped with the other microphone opener buttons. It will be affected by signals to close microphone buttons. Channels associated with this button will be mixed differently when using the VoIP modes."))
      self.is_microphone.connect("toggled", lambda w: self.emit("changed"))
      self.pack_start(self.is_microphone, False)
      
      frame = gtk.Frame(" %s " % _('Button Open Triggers'))
      self.pack_start(frame, False, padding=3)
      self.open_triggers = collections.OrderedDict()
      lvbox = gtk.VBox()
      rvbox = gtk.VBox()
      for w, t, col in zip(("advance", "stop_control", "stop_control2", "announcement"),
              (_('Playlist advance button'),
               _("'%s' control") % _('Player Stop'),
               _("'%s' control") % _('Player Stop 2'),
               _('Announcements')),
               itertools.cycle((lvbox, rvbox))):
         cb = gtk.CheckButton(t)
         self.open_triggers[w] = cb
         col.pack_start(cb, False)
         self.activedict["oc_" + w] = cb
      hbox = gtk.HBox(True, 10)
      hbox.set_border_width(6)
      for each in (lvbox, rvbox):
         hbox.pack_start(each, False)
      frame.add(hbox)
      
      frame = gtk.Frame(" %s " % _('When opened close these other buttons'))
      self.pack_start(frame, False, padding=3)
      self.closer_hbox = gtk.HBox()
      self.closer_hbox.set_border_width(3)
      for i in range(1, ident):
         cb = gtk.CheckButton(str(i))
         cb.connect("toggled", lambda w: self.emit("changed"))
         self.closer_hbox.pack_start(cb)
         self.activedict["close_%d_button" % i] = cb
      frame.add(self.closer_hbox)
      
      frame = gtk.Frame(" %s " % _('Shell Command'))
      set_tip(frame, _("Mostly useful issuing 'amixer' commands, in particular for setting capture."))
      self.pack_start(frame, False, padding=3)
      ivbox = gtk.VBox()
      frame.add(ivbox)
      ivbox.set_border_width(6)
      ivbox.set_spacing(3)
      sg = gtk.SizeGroup(gtk.SIZE_GROUP_HORIZONTAL)
      def enbox(l, r):
         hbox = gtk.HBox()
         hbox.set_spacing(3)
         label = gtk.Label(l)
         label.set_alignment(0.0, 0.5)
         hbox.pack_start(label, False)
         hbox.pack_start(r)
         sg.add_widget(r)
         return hbox
         
      self.shell_on_open = gtk.Entry()
      self.shell_on_close = gtk.Entry()
      ivbox.pack_start(enbox(_('On open'), self.shell_on_open), False)
      ivbox.pack_start(enbox(_('On close'), self.shell_on_close), False)
      
      self.activedict.update({
         "reminderflash" : self.has_reminder_flash,
         "isamicrophone" : self.is_microphone,
      })
      
      self.valuesdict = {
         "headroom" : self.headroom
      }

      self.textdict = {
         "iconpathname" : self.icb,
         "buttontext" : self.button_text,
         "shell_onopen" : self.shell_on_open,
         "shell_onclose" : self.shell_on_close,
      }
     
      self.button_was_on = False


   def set_ident(self, ident):
      self.label.set_text(str(ident))
      self.ident = ident


   def add_closer(self, closer_ident):
      cb = gtk.CheckButton(str(closer_ident))
      if closer_ident == self.ident:
         cb.set_sensitive(False)
      else:
         cb.connect("toggled", lambda w: self.emit("changed"))
         self.activedict["close_%d_button" % closer_ident] = cb
      self.closer_hbox.pack_start(cb)
      cb.show()


class OpenerSettings(gtk.Frame):
   __gsignals__ = { "changed" : (
                  gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, (gobject.TYPE_PYOBJECT,))}

   def __init__(self):
      gtk.Frame.__init__(self, " %s " % _('Main Panel Opener Buttons'))
      self.set_border_width(3)
      
      def changed(*args):
         self.emit("changed", None)
      
      vbox = gtk.VBox()
      self.add(vbox)
      vbox.set_border_width(7)
      vbox.set_spacing(3)

      self.button_numbers = gtk.CheckButton(_('Indicate button numbers and associated channel numbers'))
      set_tip(self.button_numbers, _("A useful feature to have switched on while allocating channel openers."))
      self.button_numbers.connect("toggled", changed)
      vbox.pack_start(self.button_numbers, False)
      
      frame = gtk.Frame(" %s " % _('Status Indicator Appearance'))
      set_tip(frame, _('Each opener button has two vertical bars at the side to make the button state more apparent. These settings control their appearance.'))
      vbox.pack_start(frame, False, padding=6)
      hbox = gtk.HBox()
      hbox.set_border_width(3)
      hbox.set_spacing(3)
      frame.add(hbox)
      
      hbox.pack_start(gtk.Label(_('Width')), False)
      self.indicator_width = gtk.SpinButton(gtk.Adjustment(4.0, 0.0, 10.0, 1.0), digits=0)
      self.indicator_width.connect("value-changed", changed)
      hbox.pack_start(self.indicator_width, False)
      hbox.pack_start(gtk.HBox())
      
      hbox.pack_start(gtk.Label(_('Opened')), False)
      self.open_colour = ColourButton(gtk.gdk.Color(0.95, 0.2, 0.2))
      hbox.pack_start(self.open_colour, False)
      hbox.pack_start(gtk.HBox())
      hbox.pack_start(gtk.Label(_('Closed')), False)
      col = gtk.gdk.Color("gray")
      self.closed_colour = ColourButton(col)
      hbox.pack_start(self.closed_colour, False)
      hbox.pack_start(gtk.HBox())
      hbox.pack_start(gtk.Label(_('Remind')), False)
      self.reminder_colour = ColourButton(col)
      hbox.pack_start(self.reminder_colour, False)
     
      for each in (self.open_colour, self.closed_colour, self.reminder_colour):
         each.connect("color-set", changed)
     
      self.notebook = gtk.Notebook()
      vbox.pack_start(self.notebook, False, padding=3)
      self.show_all()
   
      self.activedict = {
         "btnnumbers" : self.button_numbers,
      }

      self.textdict = {
         "btncolour_opened" : self.open_colour,
         "btncolour_closed" : self.closed_colour,
         "btncolour_remind" : self.reminder_colour,
      }
   
      self.valuesdict = {
         "btnreminderwidth": self.indicator_width,
      }
      

   def add_channel(self):
      tab = OpenerTab(len(self.notebook) + 1)
      self.notebook.append_page(tab, tab.label)
      def add_closer(each_tab):
         each_tab.add_closer(tab.ident)
      self.notebook.foreach(add_closer)
      tab.show_all()
      tab.connect("changed", lambda w: self.emit("changed", tab))
      
      
   def finalise(self):
      for tab in self.notebook.get_children():
         for attrname in ("activedict", "valuesdict", "textdict"):
            dest = getattr(self, attrname)
            src = getattr(tab, attrname)
            for key, val in src.iteritems():
               dest[key + "_%d" % tab.ident] = val

   
class MicOpener(gtk.HBox):
   @property
   def any_mic_selected(self):
      return self._any_mic_selected
   
   def notify_others(self):
      r = self.approot
      # Player headroom for mic-audio toggle.
      r.mixer_write("ACTN=anymic\nFLAG=%d\nend\n" % self.any_mic_selected, True)
      r.mixer_write("HEAD=%f\nACTN=headroom\nend\n" % self._headroom, True)
      r.new_mixermode(r.mixermode)

   def cb_mictoggle(self, button, mics):
      self._flashing_timer = 0

      if button.get_active():
         cmd = button.opener_tab.shell_on_open.get_text().strip()
         closers = button.opener_tab.closer_hbox.get_children()
         for i, closer in enumerate(closers, start=1):
            if closer.get_active():
               try:
                  self.ix2button[i].set_active(False)
               except KeyError:
                  pass
      else:
         cmd = button.opener_tab.shell_on_close.get_text().strip()

      if cmd and not button.block_shell_command:
         print "button %d shell command: %s" % (button.opener_tab.ident, cmd)
         subprocess.Popen(cmd, shell=True, close_fds=True)

      for mic in mics:
         mic.open.set_active(button.get_active())

      self._any_mic_selected = any(mb.get_active() for mb in self.buttons if mb.opener_tab.is_microphone.get_active())

      try: 
         self._headroom = max(mb.opener_tab.headroom.get_value() for mb in self.buttons if mb.get_active())
      except ValueError:
         self._headroom = 0.0

      self.notify_others()

   def cb_reconfigure(self, widget, trigger=None):
      self.new_button_set()
      
   def new_button_set(self):
      # Clear away old button widgets.
      self.foreach(lambda x: x.destroy())
      self.mic2button = {}
      self.buttons = []
      self.ix2button = {}
      joiner = ' <span foreground="red">&#64262;</span> '

      mic_group_list = [[] for x in xrange(PGlobs.num_micpairs * 2)]
      aux_group_list = [[] for x in xrange(PGlobs.num_micpairs * 2)]
      ot = self.opener_settings.notebook.get_children()
      mic_qty = aux_qty = 0
      
      # Categorisation of channels into button groups.
      for m in self.mic_list:
         mode = m.mode.get_active()
         if mode:
            pm = m.partner if mode == 3 else m
            if pm.group.get_active():
               oti = int(pm.groups_adj.value) - 1
               if ot[oti].is_microphone.get_active():
                  t = mic_group_list[oti]
                  if not t:
                     mic_qty += 1
               else:
                  t = aux_group_list[oti]
                  if not t:
                     aux_qty += 1
               t.append(m)

      # Opener buttons built here.
      def build(group_list, closer):
         image = gtk.image_new_from_stock(gtk.STOCK_CLOSE, gtk.ICON_SIZE_BUTTON)
         closer_button = gtk.Button()
         closer_button.set_image(image)
         closer_button.show_all()

         if closer == "left":
            self.pack_start(closer_button, False)

         for i, g in enumerate(group_list):
            if g:
               mic_list = []
               mb = MicButton(self.opener_settings, ot[i], g)
               self.ix2button[mb.opener_tab.ident] = mb
               self.buttons.append(mb)
               active = False
               for m in g:
                  mic_list.append(m)
                  if m.open.get_active():
                     active = True
                  self.mic2button[m.ui_name] = mb
               mb.connect("toggled", self.cb_mictoggle, mic_list)
               self.add(mb)
               mb.show()
               mb.block_shell_command = mb.opener_tab.button_was_on
               mb.set_active(active)  # Open all if any opener members are currently open.
               mb.block_shell_command = False
               
               closer_button.connect("clicked", lambda w, btn: btn.set_active(False), mb)

         if closer == "right":
            self.pack_start(closer_button, False)
            
      if aux_qty:
         build(aux_group_list, closer=("right" if aux_qty > 1 else None))
         if mic_qty:
            spc = gtk.HBox()
            spc.set_size_request(3, -1)
            self.pack_start(spc, False)
            spc.show()
            
      if mic_qty:
         build(mic_group_list, closer=("left" if mic_qty > 1 else None))
         

      if self._forced_on_mode:
         self.force_all_on(True)
            
      if not self.mic2button:
         # TC: A textual placeholder for microphone opener buttons.
         # TC: If the user is reading this text then all microphones have been deactivated.
         l = gtk.Label(_('No Channel Opener Buttons'))
         l.set_sensitive(False)
         self.add(l)
         l.show()
         
      # Categorisation of channels according to type a or m (aux or mic)
      channel_modes = ['a' for i in range(PGlobs.num_micpairs * 2)]
      for button in mic_group_list:
         for channel in button:
            channel_modes[channel.index] = 'm'

      self.approot.mixer_write("CMOD=%s\nACTN=new_channel_mode_string\nend\n" % "".join(channel_modes), True)    
      self.notify_others()

     
   @threadslock
   def cb_flash_timeout(self):

      if self._flash_test() and not self._forced_on_mode:
         self._flashing_timer += 1
      else:
         self._flashing_timer = 0

      flash_value = bool((self._flashing_timer % 2) if self._flashing_timer > 7 else 0)

      for mb in self.buttons:
         mb.flash = flash_value

      return True
     
   def force_all_on(self, val):
      """Switch on all front panel mic buttons and make them insensitive."""
      
      self._forced_on_mode = val
      for mb in self.buttons:
         if mb.opener_tab.is_microphone.get_active():
            if val:
               mb.set_active(True)
            mb.set_sensitive(not val)
            mb.set_inconsistent(val)

   def open_auto(self, type_):
      for b in self.buttons:
         try:
            cb = b.opener_tab.open_triggers[type_]
         except KeyError:
            print "unknown auto open type:", type_
         else:
            if cb.get_active():
               b.set_active(True)

   def oc(self, mic, val):
      """Perform open/close."""
      
      try:
         self.mic2button[mic].set_active(val)
      except:
         for m in self.mic_list:
            if mic == m.ui_name:
               mode = m.mode.get_active()
               if mode in (1, 2):
                  m.open.set_active(val)
               elif mode == 3:
                  m.partner.open.set_active(val)
               break
   
   def get_opener_button(self, ix):
      try:
         m = self.mic_list[ix]
         return self.mic2button[m.ui_name]
      except KeyError:
         mode = m.mode.get_active()
         if mode in (1, 2):
            return m.open
         elif mode == 3:
            return m.partner.open
         print "channel %d is not active" % (ix + 1)
      except IndexError:
         print "channel %d does not exist" % (ix + 1)
      return None

   def close_all(self):
      for mb in self.buttons:
         mb.set_active(False)

   def open(self, val):
      self.oc(val, True)
      
   def close(self, val):
      self.oc(val, False)

   def add_mic(self, mic):
      """mic: AGCControl object passed here to register it with this class."""

      self.opener_settings.add_channel()
      self.mic_list.append(mic)
      for attr, signal in zip (("mode", "group", "no_front_panel_opener", "groups_adj"),
                               ("changed", "toggled", "toggled", "notify::value")):
         getattr(mic, attr).connect(signal, self.cb_reconfigure)
         
   def finalise(self):
      self.opener_settings.finalise()

   def __init__(self, approot, flash_test):
      self.approot = approot
      self._flash_test = flash_test
      gtk.HBox.__init__(self)
      self.set_spacing(2)
      self.mic_list = []
      self.buttons = []
      self.mic2button = {}
      self._any_mic_selected = False
      self._forced_on_mode = False
      self._flashing_mode = False
      self._flashing_timer = 0
      self._headroom = 0.0
      timeout = glib.timeout_add(700, self.cb_flash_timeout)
      self.connect("destroy", lambda w: glib.source_remove(timeout))
      self.opener_settings = OpenerSettings()
      self.opener_settings.connect("changed", self.cb_reconfigure)
      

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
 
def make_stream_meter_unit(text, meters):
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
   set_tip(frame, _('This indicates the state of the various streams. Flashing means stream packets are being discarded because of network congestion. Partial red means the send buffer is partially full indicating difficulty communicating with the server. Green means everything is okay.'))
   
   frame = gtk.Frame()              # for the listener count
   frame.set_label_align(0.5, 0.5)
   pixbuf = gtk.gdk.pixbuf_new_from_file_at_size(FGlobs.pkgdatadir / "listenerphones.png", 20, 16)
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
   set_tip(frame, _('The combined total number of listeners in all server tabs.'))
   
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
         
   def _cb_tooltip(self, widget, x, y, keyboard_mode, tooltip):
      if self.agc:
         text = self.agc.alt_name.get_text().strip()
         if not text:
            return False
         label = gtk.Label(text)
         tooltip.set_custom(label)
         label.show()
         return True
      else:
         return False

   def __init__(self, labelbasetext, index):
      gtk.VBox.__init__(self)
      self.set_border_width(0)
      lhbox = gtk.HBox()
      pad = gtk.VBox()
      lhbox.add(pad)
      pad.show()
      lhbox.set_spacing(2)
      self.led_onpb = gtk.gdk.pixbuf_new_from_file_at_size(
         FGlobs.pkgdatadir / "led_lit_green_black_border_64x64.png", 7, 7)
      self.led_offpb = gtk.gdk.pixbuf_new_from_file_at_size(
         FGlobs.pkgdatadir / "led_unlit_clear_border_64x64.png", 7, 7)
      self.led = gtk.Image()
      lhbox.pack_start(self.led, False, False)
      self.set_led(False)
      self.led.show()
      labeltext = labelbasetext + " " + str(index)
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
      self.agc = None
      self.set_tooltip_window(None)
      self.connect("query-tooltip", self._cb_tooltip)
      self.set_has_tooltip(True)


class RecIndicator(gtk.HBox):
   colour = "clear", "red", "amber"
   def set_indicator(self, colour):
      self.image.set_from_pixbuf(self.led[self.colour.index(colour)])
   def __init__(self, label_text):
      gtk.HBox.__init__(self)
      label = gtk.Label(label_text)
      self.pack_start(label)
      label.show()
      attrlist = pango.AttrList()
      attrlist.insert(pango.AttrSize(METER_TEXT_SIZE, 0, 1))
      label.set_attributes(attrlist)   
      self.image = gtk.Image()
      self.pack_start(self.image, False)
      self.image.show()
      
      self.led = [gtk.gdk.pixbuf_new_from_file_at_size(FGlobs.pkgdatadir / (which + ".png"), 9, 9) for which in (
               "led_unlit_clear_border_64x64", "led_lit_red_black_border_64x64",
               "led_lit_amber_black_border_64x64")]
      self.set_indicator("clear") 


class RecordingPanel(gtk.VBox):
   def __init__(self, howmany):
      gtk.VBox.__init__(self)
      
      # TC: Record as in, to make a recording.
      label = gtk.Label(" %s " % _('Record'))
      attrlist = pango.AttrList()
      attrlist.insert(pango.AttrSize(METER_TEXT_SIZE, 0, len(label.get_text())))
      label.set_attributes(attrlist)
      self.pack_start(label)
      label.show()
      frame = gtk.Frame()
      frame.set_border_width(4)
      self.pack_start(frame)
      frame.show()
      hbox = gtk.HBox()
      hbox.set_spacing(1)
      hbox.set_border_width(3)
      frame.add(hbox)
      hbox.show()
      box = [gtk.VBox(), gtk.VBox()]
      for each in box:
         each.set_spacing(4)
         hbox.pack_start(each)
         each.show()
      self.indicator = []
      for i in range(howmany):
         ind = RecIndicator(str(i+1))
         self.indicator.append(ind)
         box[i%2].pack_start(ind, False)
         ind.show()

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
      dialog = gtk.Dialog(pm.title_extra.strip(), None, gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT, (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, gtk.STOCK_QUIT, gtk.RESPONSE_OK))
      if window_group is not None:
         window_group.add_window(dialog)
      dialog.set_resizable(False)
      dialog.connect("close", self.respond, actionyes, actionno)
      dialog.connect("response", self.respond, actionyes, actionno)
      dialog.connect("window-state-event", self.window_attn)
      dialog.set_border_width(6)
      dialog.vbox.set_spacing(12)
      
      hbox = gtk.HBox(False, 20)
      hbox.set_spacing(12)
      dialog.get_content_area().add(hbox)
      image = gtk.image_new_from_stock(gtk.STOCK_DIALOG_WARNING, gtk.ICON_SIZE_DIALOG)
      image.set_alignment(0.5, 0)
      hbox.pack_start(image, False)

      vbox = gtk.VBox()
      hbox.pack_start(vbox, True, True, 0)
      vbox.show()
      
      if additional_text is not None:
         if type(additional_text) is str:
            additional_text = additional_text.splitlines()
         for each in additional_text:
            label = gtk.Label()
            label.set_alignment(0.0, 0.5)
            label.set_markup(each)
            vbox.pack_start(label, False)
      dialog.show_all()


class MainWindow:
   def send_new_mixer_stats(self):

      deckadj = deck2adj = self.deckadj.get_value() * -1.0 + 100.0
      if self.prefs_window.dual_volume.get_active():
          deck2adj = self.deck2adj.get_value() * -1.0 + 100.0

      string_to_send = ":%03d:%03d:%03d:%03d:%03d:%03d:%03d:%d:%d%d%d%d%d:%d%d:%d%d%d%d:%d:%d:%d:%d:%d:%f:%f:%d:%f:%d:%d:%d:" % (
                                                deckadj,
                                                deck2adj,
                                                self.crossadj.get_value(),
                                                self.jingles.l1_adj.get_value() * -1.0 + 100.0,
                                                self.jingles.l2_adj.get_value() * -1.0 + 100.0,
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
                                                self.dsp_button.get_active(), 
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
         self.album = self.player_left.album
      elif meta == 1:
         self.songname = self.player_right.songname
         self.artist = self.player_right.artist
         self.title = self.player_right.title
         self.album = self.player_right.album
      elif meta == -1:
         self.songname = ""
         self.artist = ""
         self.title = ""
         self.album = ""

      self.new_metadata = (self.songname, self.artist, self.title, self.album)
      
      # update metadata on stream if it has changed
      if self.new_metadata != self.old_metadata:
         self.old_metadata = self.new_metadata             # now we need to send the new metadata
         print "song title: %s\n" % self.songname
         if self.songname != u"":
            self.window.set_title("%s :: IDJC%s" % (self.songname, pm.title_extra))
            tm = time.localtime()
            ts = "%02d:%02d :: " % (tm[3], tm[4])       # hours and minutes
            tstext = self.songname.encode("utf-8") + " - %s" % self.album
            self.history_buffer.place_cursor(self.history_buffer.get_end_iter())
            self.history_buffer.insert_at_cursor(ts + tstext + "\n")
            adjustment = self.history_window.get_vadjustment()
            adjustment.set_value(adjustment.upper)
            try:
               file = open(PGlobs.profile_dir / pm.profile / "history.log", "a")
            except IOError:
               print "unable to open history.log for writing"
            else:
               try:
                  file.write(time.strftime("%x %X :: ") + tstext + "\n")
               except IOError:
                  print "unable to append to file \"history.log\""
               file.close()

            self.server_window.new_metadata(self.artist, self.title, self.album, self.songname)
         else:
            self.window.set_title(self.appname + pm.title_extra)

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
      album = gen.next()
      player_context = int(gen.next())
      time_lag = int(gen.next())
  
      if infotype == 1:
         if not artist and " - " in title:
            artist, title = title.split(" - ")
         song = artist.decode("utf-8", "replace") + u" - " + title.decode("utf-8", "replace")
      if infotype == 2:
         song = artist_title.decode("utf-8", "replace")
         if not artist and " - " in title:
            artist, title = title.split(" - ")
      if infotype == 3:
         if not artist and " - " in title:
            artist, title = title.split(" - ")
         song = artist.decode("iso8859-1", "replace") + u" - " + title.decode("iso8859-1", "replace")
         artist = artist.decode("iso8859-1", "replace").encode("utf-8", "replace")
         title = title.decode("iso8859-1", "replace").encode("utf-8", "replace")
         album = album.decode("iso8859-1", "replace").encode("utf-8", "replace")
      if infotype == 4:
         song = title.decode("iso8859-1", "replace")
         if not artist and " - " in title:
            artist, title = title.split(" - ")
         artist = artist.decode("iso8859-1", "replace").encode("utf-8", "replace")
         title = title.decode("iso8859-1", "replace").encode("utf-8", "replace")
         album = album.decode("iso8859-1", "replace").encode("utf-8", "replace")
      if infotype == 7:
         model = player.model_playing
         iter = player.iter_playing
         
         song = model.get_value(iter, 3)
         artist = model.get_value(iter, 6)
         title = model.get_value(iter, 5)
         album = model.get_value(iter, 9)
      if infotype > 4 and infotype < 7: # unicode chapter tags unsupported
         return
      if not player_context & 1:
         time_lag = 0
      else:
         time_lag = int(time_lag / player.pbspeedfactor)
      gobject.timeout_add(time_lag, self.new_songname_timeout, (song, artist, title, album, player, player_context))

   @threadslock
   def new_songname_timeout(self, (song, artist, title, album, player, player_context)):
      if player.player_cid == (player_context | 1):
         player.songname = song
         player.artist = artist
         player.title = title
         player.album = album
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
         self.prefs_window.notebook.set_current_page(4)
         self.prefs_window.window.present()
      if data == "Features":
         if widget.get_active():
            self.simplemixer = False
            self.min_wst.set_tracking(False)
            self.window.forall(self.ui_detail_leveller(5))
            self.send_new_mixer_stats()
            for each in (self.player_left, self.player_right):
               each.pl_mode.emit("changed")
            self.full_wst.apply()
            self.full_wst.set_tracking(True)
         else:
            self.simplemixer = True
            self.full_wst.set_tracking(False)
            self.player_right.stop.clicked()
            self.jingles.window.hide()
            self.crossadj.set_value(0)
            self.crossadj.value_changed()
            self.window.forall(self.ui_detail_leveller(0))
            for each in (self.player_left, self.player_right):
               each.pl_delay.set_sensitive(False)
            self.min_wst.apply()
            self.min_wst.set_tracking(True)
      if data == "Advance":
         if self.crossfade.get_value() < 50:
            self.player_left.advance()
         else:
            self.player_right.advance()
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
      if data == "stream-mon":
         self.send_new_mixer_stats()
      if data == "Greenphone":
         mode = self.mixermode
         if widget.get_active() == True:
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

   def save_session(self):
      print "saving profile settings"

      try:
         fh = open(self.session_filename, "w")
         fh.write("deckvol=" + str(self.deckadj.get_value()) + "\n")
         fh.write("deck2vol=" + str(self.deck2adj.get_value()) + "\n")
         fh.write("crossfade=" + str(self.crossadj.get_value()) + "\n")
         fh.write("jingles_deckvol1=" + str(self.jingles.l1_adj.get_value()) + "\n")
         fh.write("jingles_deckvol2=" + str(self.jingles.l2_adj.get_value()) + "\n")
         fh.write("jingles_muting1=" + str(self.jingles.m1_adj.get_value()) + "\n")
         fh.write("jingles_muting2=" + str(self.jingles.m2_adj.get_value()) + "\n")
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
         fh.write("interlude=" + self.jingles.interlude_player_track + "\n")
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
         
      except Exception as e:
         print "Error writing out main session data", e

      try:
         fh = open(self.session_filename + "_tracks", "w")
         start, end = self.history_buffer.get_bounds()
         text = self.history_buffer.get_text(start, end)
         fh.write(text)
         fh.close()
      except Exception as e:
         print "Error writing out tracks played data", e
         
      self.prefs_window.save_player_prefs()
      self.controls.save_prefs()
      self.server_window.save_session_settings()
      self.jack.standard_save()
      
      return True  # This is also a timeout routine

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
         elif k=="jingles_deckvol1":
            self.jingles.l1_adj.set_value(float(v))
         elif k=="jingles_deckvol2":
            self.jingles.l2_adj.set_value(float(v))
         elif k=="jingles_muting1":
            self.jingles.m1_adj.set_value(float(v))
         elif k=="jingles_muting2":
            self.jingles.m2_adj.set_value(float(v))
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
      try:
         gtk.main_quit()
      except:
         pass
      gtk.gdk.threads_leave()
      time.sleep(0.3)
      sys.exit(0)

   def destroy(self, widget=None, data=None):
      self.save_session()
      if self.crosspass:
         gobject.source_remove(self.crosspass)
      self.server_window.cleanup()
      self.mic_opener.close_all()
      self.player_left.cleanup()
      self.player_right.cleanup()
      self.jingles.cleanup()
      self.player_left.flush = True
      self.player_right.flush = True
      self.send_new_mixer_stats()
      gobject.source_remove(self.statstimeout)
      gobject.source_remove(self.vutimeout)
      gobject.source_remove(self.savetimeout)
      self.server_window.source_client_close()
      self.mixer_ctrl.close()
      if gtk.main_level():
         gtk.main_quit()
      time.sleep(0.3)   # Allow time for all subthreads/programs time to exit 
      gtk.gdk.threads_leave()
      sys.exit(0)

   def delete_event(self, widget, event, data=None):
      qm = ["<span size='12000' weight='bold'>%s</span>" % _("Confirmation to quit IDJC is required."), ""]
      
      if self.server_window.is_streaming and self.server_window.is_recording:
         qm.append(_("All active recordings and radio streams will terminate."))
      elif self.server_window.is_streaming:
         qm.append(_("All of the active radio streams will terminate."))
      elif self.server_window.is_recording:
         qm.append(_("All active recordings will cease."))
      else:
         self.destroy()
         return False
      
      idjc_shutdown_dialog(self.window_group, self.destroy, None, qm)
      return True

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
            sp_mx = subprocess.Popen([FGlobs.libexecdir / "idjcmixer"], bufsize = 4096, stdin = subprocess.PIPE, stdout = subprocess.PIPE, close_fds = True)
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
         self.player_left.next.clicked()
         self.player_right.next.clicked()
         self.jingles.stop.clicked()
         if self.jingles.interlude_player_track != "":
            self.jingles.start_interlude_player(self.jingles.interlude_player_track)
         if self.last_chance == False:
            self.mixer_write(message, flush)            # resume what we were doing
         self.jack.load(restrict=os.environ["mx_client_id"] + ":")
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

   def vu_update(self, locking = True):
      if locking:
         gtk.gdk.threads_enter()
      try:
         try:
            self.mixer_write("ACTN=requestlevels\nend\n", True)
         except ValueError, IOError:
            if locking:
               gtk.gdk.threads_leave()
            return True

         session_cmd = midis = ''
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
               
            if key == "session_command":
               session_cmd = value
               continue
               
            if key.startswith("silence_"):
               try:
                  value = float(value)
               except ValueError:
                  pass
            else:
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

         # Carry out certain triggered actions *after* exhausting the reply queue
         # specifically any which could result in a newly issued mixer command.
         #
         if midis:
            for midi in midis.split(','):
               input, _, value = midi.partition(':')
               self.controls.input(input, int(value, 16))
               
         if session_cmd:
            if session_cmd == "save_L1" and pm.session_type == "L1":
               self.jack.session_save()

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
      menuitem = gtk.MenuItem(_('Remove Contents'))
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

   # when a second instance of idjc is launched the program launcher will signal the running instance with SIGUSR2
   def second_instance_handler(self, arg1, arg2):
      print "the launch of a second instance of idjc was detected"
      self.second_instance = True       # idjc will handle this event in good time

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

   def flash_test(self):
      """True if the mic button needs to be flashing now or soon.""" 
      
      return self.player_left.is_playing or self.player_right.is_playing

   def __init__(self):
      self.appname = PGlobs.app_longform
      self.version = FGlobs.package_version
      self.copyright = PGlobs.copyright
      self.license = PGlobs.license
      self.profile = pm.profile
      
      signal.signal(signal.SIGINT, self.destroy_hard)
      signal.signal(signal.SIGUSR1, signal.SIG_IGN)
      signal.signal(signal.SIGUSR2, signal.SIG_IGN)
      
      socket.setdefaulttimeout(15)
      
      # Resources to reserve.
      config = ConfigParser.RawConfigParser()
      config.read(PGlobs.profile_dir / pm.profile / 'config')
      try:
         PGlobs.num_micpairs = config.getint('resource_count', 'num_micpairs') // 2
      except ConfigParser.Error:
         pass
      try:
         count = config.getint('resource_count', 'num_streamers')
      except ConfigParser.Error:
         pass
      else:
         PGlobs.num_streamers = count
         PGlobs.num_encoders = count
      try:
         PGlobs.num_recorders = config.getint('resource_count', 'num_recorders')
      except ConfigParser.Error:
         pass
      
      if args.jackserver is not None:
         os.environ["jack_parameter"] = args.jackserver[0]
      else:
         os.environ["jack_parameter"] = "default"
            
      os.environ["mx_client_id"] = mx_id = "idjc-mx_" + pm.profile
      os.environ["sc_client_id"] = sc_id = "idjc-sc_" + pm.profile

      print "jack client IDs:", mx_id, sc_id
      os.environ["mx_mic_qty"] = str(PGlobs.num_micpairs * 2)

      self.session_loaded = False

      try:
         sp_mx = subprocess.Popen([FGlobs.libexecdir / "idjcmixer"], bufsize = 4096, stdin = subprocess.PIPE, stdout = subprocess.PIPE, close_fds = True)
      except Exception, e:
         print e
         raise self.initfailed("unable to open a pipe to the mixer module")
      else:
         (self.mixer_ctrl, self.mixer_rply) = (sp_mx.stdin, sp_mx.stdout)
  
      # check for a reply from the mixer.
      self.last_chance = False
      rply = jackrply = self.mixer_read()
      while rply[:6] != "IDJC: ":
         if rply == "":
            print "mixer crashed"
            message_dialog = gtk.MessageDialog(None, 0, gtk.MESSAGE_INFO, gtk.BUTTONS_CLOSE, _('The mixer module crashed during initialisation.'))
            message_dialog.set_title(_('IDJC Launch Failed') + pm.title_extra)
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
         message_dialog = gtk.MessageDialog(None, 0, gtk.MESSAGE_INFO, gtk.BUTTONS_CLOSE, _('The JACK sound server needs to be running in order to run IDJC.\nIn order to manually start it try something like:\n\n        $ jackd -d alsa -r 44100 -p 2048\n\nIf you would like JACK to start automatically with your user specified parameters try something like this, which will create a file called .jackdrc in your home directory:\n\n        $ echo "/usr/bin/jackd -d alsa -r 44100" > ~/.jackdrc\n\nIf you have already done this it is possible another application or non-JACK sound server is using the sound card.\n\nPossible remedies would be to close the other audio app or configure the sound server to go into suspend mode after a brief amount of idle time.\n\nIf you are trying to connect to a named jack server, either set the environment variable JACK_DEFAULT_SERVER to that name or launch IDJC with the -j jackservername option. For example:\n\n         $ jackd -n xyzzy -d alsa -r 44100 -p 2048 &\n         $ idjc -p profilename -j xyzzy\n\nIf you are trying to open multiple instances of IDJC use the -e command line switch.'))
         message_dialog.set_title(_('IDJC Launch Failed') + pm.title_extra)
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
      self.window.set_gravity(gtk.gdk.GRAVITY_STATIC)
      self.window_group.add_window(self.window)
      self.window.set_title(self.appname + pm.title_extra)
      self.window.set_border_width(8)
      self.window.connect("delete_event",self.delete_event)
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
      self.menu = MainMenu()
      self.menu.set_border_width(6)
      self.vbox8.pack_start(self.menu, False)
      self.menu.show()
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

      self.dsp_button = gtk.ToggleButton()
      label = gtk.Label()
      label.set_markup("<span weight='bold' size='9000' foreground='#333'>%s</span>" % _('DSP'))
      self.dsp_button.add(label)
      label.show()
      self.dsp_button.connect("toggled", lambda w: self.send_new_mixer_stats())
      self.hbox10.pack_start(self.dsp_button, False)
      self.dsp_button.show()
            
      phonebox = gtk.HBox()
      phonebox.viewlevels = (5,)       
      phonebox.set_spacing(2)
      
      pixbuf4 = gtk.gdk.pixbuf_new_from_file(FGlobs.pkgdatadir / "greenphone.png")
      pixbuf4 = pixbuf4.scale_simple(25, 20, gtk.gdk.INTERP_BILINEAR)
      image = gtk.Image()
      image.set_from_pixbuf(pixbuf4)
      image.show()
      self.greenphone = gtk.ToggleButton()
      self.greenphone.add(image)
      self.greenphone.connect("toggled", self.cb_toggle, "Greenphone")
      phonebox.pack_start(self.greenphone)
      self.greenphone.show()
      set_tip(self.greenphone, _('Mix voice over IP audio to the output stream.'))

      pixbuf5 = gtk.gdk.pixbuf_new_from_file(FGlobs.pkgdatadir / "redphone.png")
      pixbuf5 = pixbuf5.scale_simple(25, 20, gtk.gdk.INTERP_BILINEAR)
      image = gtk.Image()
      image.set_from_pixbuf(pixbuf5)
      image.show()
      self.redphone = gtk.ToggleButton()
      self.redphone.add(image)
      self.redphone.connect("toggled", self.cb_toggle, "Redphone")
      phonebox.pack_start(self.redphone)
      self.redphone.show()
      set_tip(self.redphone, _('Mix voice over IP audio to the DJ only.'))
 
      self.hbox10.pack_start(phonebox, False)
      phonebox.show()
 
      pixbuf3 = gtk.gdk.pixbuf_new_from_file(FGlobs.pkgdatadir / "jack2.png")
      pixbuf3 = pixbuf3.scale_simple(32, 20, gtk.gdk.INTERP_BILINEAR)
      image = gtk.Image()
      image.set_from_pixbuf(pixbuf3)
      image.show()
      
      # microphone open/unmute dynamic widget cluster thingy
      self.mic_opener = MicOpener(self, self.flash_test)
      self.mic_opener.viewlevels = (5,)
      self.hbox10.pack_start(self.mic_opener)
      self.mic_opener.show()
      
      # playlist advance button
      pixbuf = gtk.gdk.pixbuf_new_from_file(FGlobs.pkgdatadir / "advance.png")
      pixbuf = pixbuf.scale_simple(32, 14, gtk.gdk.INTERP_BILINEAR)
      image = gtk.Image()
      image.set_from_pixbuf(pixbuf)
      self.advance = gtk.Button()
      self.advance.add(image)
      image.show()
      self.advance.connect("clicked", self.callback, "Advance")
      self.hbox10.pack_end(self.advance, False)
      self.advance.show()
      set_tip(self.advance, _('This button steps through the active playlist, pausing between tracks. The active playlist is defined by the placement of the crossfader.'))
      
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
      image.set_from_file(FGlobs.pkgdatadir / "volume2.png")
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
      set_tip(self.deckvol, _('The volume control shared by both music players.'))

      # Secondary volume controller, visible when using separate player volumes
      self.deck2adj = gtk.Adjustment(100.0, 0.0, 100.0, 1.0, 6.0)
      self.deck2adj.connect("value_changed", self.cb_deckvol)
      self.deck2vol = gtk.VScale(self.deck2adj)
      self.deck2vol.set_update_policy(gtk.UPDATE_CONTINUOUS)
      self.deck2vol.set_draw_value(False)
      self.deck2vol.set_inverted(True)
      hboxvol.pack_start(self.deck2vol, False, False, 0)
      set_tip(self.deck2vol, _('The volume control for the right music player.'))

      self.spacerbox = gtk.VBox()
      self.spacerbox.set_size_request(1, 5)
      self.vboxvol.pack_start(self.spacerbox, False, False, 0)
       
      pixbuf = gtk.gdk.pixbuf_new_from_file(FGlobs.pkgdatadir / "pbphone.png")
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
      set_tip(self.mixback, _('The stream volume level to send to the voice over IP connection.'))
      
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
      # Expander widget text for showing a list of tracks that were recently played.
      self.history_expander = gtk.expander_new_with_mnemonic(_('Tracks Played'))
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
      # TC: Popup menu item, wipes away the tracks played history text.
      self.history_clear = gtk.Button(" " + _('Remove Contents') + " ")
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
      label = gtk.Label(_('Monitor Mix'))
      attrlist = pango.AttrList()
      attrlist.insert(pango.AttrSize(8000, 0, len(_('Monitor Mix'))))
      label.set_attributes(attrlist)
      smvbox.add(label)
      label.show()
      
      frame = gtk.Frame()
      frame.set_shadow_type(gtk.SHADOW_NONE)
      smhbox = gtk.HBox()
      # TC: IDJC creates two audio mixes with DJ being the name of one of them.
      # TC: The DJ mix is strictly for the DJ and allows for off air VoIP chat and pre-listening.
      self.listen_dj = gtk.RadioButton(None, _('DJ'))
      smhbox.add(self.listen_dj)
      self.listen_dj.show()
      # TC: IDJC creates two audio mixes with Stream being the name of one of them.
      # TC: The Stream mix is the one the listeners hear.
      self.listen_stream = gtk.RadioButton(self.listen_dj, _('Stream'))
      smhbox.add(self.listen_stream)
      self.listen_stream.show()
      frame.add(smhbox)
      smhbox.show()
      smvbox.add(frame)
      frame.show()
      sg3.add_widget(frame)
      
      self.listen_stream.connect("toggled", self.cb_toggle, "stream-mon")
      # TC: Context {0}, {1}, {2} = Monitor Mix, Stream, DJ
      # TC: Or whatever they become translated to.
      set_tip(smvbox, _("In IDJC there are are two audio paths and this '{0}' control toggles between them. When '{1}' is active you can hear what the listeners are hearing including the effects of the crossfader. '{0}' needs to be set to '{2}' in order to make proper use of the VoIP features.").format(_("Monitor Mix"), _("Stream"), _("DJ")))
      
      cross_sizegroup.add_widget(smhbox)
      self.crossbox.pack_start(smvbox, False, False, 0)
      smvbox.show()

      # metadata source selector combo box
      mvbox = gtk.VBox()
      # TC: Dropdown box title text. Track metadata is derived from the source selected by a drop down box.
      label = gtk.Label(_('Metadata Source'))
      attrlist = pango.AttrList()
      attrlist.insert(pango.AttrSize(8000, 0, len(_('Metadata Source'))))
      label.set_attributes(attrlist)
      mvbox.add(label)
      label.show()
      self.metadata_source = gtk.combo_box_new_text()
      # TC: The chosen source of track metadata.
      self.metadata_source.append_text(_('Left Player'))
      # TC: The chosen source of track metadata.
      self.metadata_source.append_text(_('Right Player'))
      # TC: The chosen source of track metadata.
      self.metadata_source.append_text(_('Last Played'))
      # TC: The chosen source of track metadata.
      self.metadata_source.append_text(_('Crossfader'))
      # TC: The chosen source of track metadata. In this case no metadata.
      self.metadata_source.append_text(_('None'))
      self.metadata_source.set_active(3)
      cross_sizegroup.add_widget(self.metadata_source)
      self.metadata_source.connect("changed", self.cb_metadata_source)
      set_tip(self.metadata_source, _('Select which Deck is responsible for the metadata on the stream.'))
      mvbox.add(self.metadata_source)
      self.metadata_source.show()
      self.crossbox.pack_start(mvbox, False, False, 0)
      mvbox.show()
      cross_sizegroup2.add_widget(self.metadata_source)
      sg3.add_widget(self.metadata_source)
      
      plvbox = gtk.VBox()
      # TC: Abbreviation of left.
      label = gtk.Label(_('L'))
      attrlist = pango.AttrList()
      attrlist.insert(pango.AttrSize(8000, 0, len(_('L'))))
      label.set_attributes(attrlist)
      plvbox.add(label)
      label.show()
      self.passleft = make_arrow_button(self, gtk.ARROW_LEFT, gtk.SHADOW_NONE, "cfmleft")
      plvbox.add(self.passleft)
      self.passleft.show()
      self.crossbox.pack_start(plvbox, False, False, 0)
      plvbox.show()
      set_tip(plvbox, _('Move the crossfader fully left.'))
      sg3.add_widget(self.passleft)
      
      self.crossadj = gtk.Adjustment(0.0, 0.0, 100.0, 1.0, 3.0, 0.0)
      self.crossadj.connect("value_changed", self.cb_crossfade)      
      cvbox = gtk.VBox()
      label = gtk.Label(_('Crossfader'))
      attrlist = pango.AttrList()
      attrlist.insert(pango.AttrSize(8000, 0, len(_('Crossfader'))))
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
      set_tip(cvbox, _('The crossfader.'))

      prvbox = gtk.VBox()
      # TC: Abbreviation of right.
      label = gtk.Label(_('R'))
      attrlist = pango.AttrList()
      attrlist.insert(pango.AttrSize(8000, 0, len(_('R'))))
      label.set_attributes(attrlist)
      prvbox.add(label)
      label.show()
      self.passright = make_arrow_button(self, gtk.ARROW_RIGHT, gtk.SHADOW_NONE, "cfmright")
      prvbox.add(self.passright)
      self.passright.show()
      self.crossbox.pack_start(prvbox, False, False, 0)
      prvbox.show()
      set_tip(prvbox, _('Move the crossfader fully right.'))
      sg3.add_widget(self.passright)
      
      patternbox = gtk.HBox()
      patternbox.set_spacing(2)
      sg4 = gtk.SizeGroup(gtk.SIZE_GROUP_VERTICAL)
      
      passbox = gtk.VBox()
      # TC: Describes a mid point.
      label = gtk.Label(_('Middle'))
      attrlist = pango.AttrList()
      attrlist.insert(pango.AttrSize(8000, 0, len(_('Middle'))))
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
      set_tip(self.passmidleft, _('Move the crossfader to the middle of its range of travel.'))
      
      self.passmidright = make_arrow_button(self, gtk.ARROW_UP, gtk.SHADOW_NONE, "cfmmidr")
      passhbox.pack_start(self.passmidright, False, False, 0)
      self.passmidright.show()
      set_tip(self.passmidright, _('Move the crossfader to the middle of its range of travel.'))
      sg4.add_widget(self.passmidright)
      
      pvbox = gtk.VBox()
      # TC: The attenuation response curve of the crossfader. User selectable.
      label = gtk.Label(_('Response'))
      attrlist = pango.AttrList()
      attrlist.insert(pango.AttrSize(8000, 0, len(_('Response'))))
      label.set_attributes(attrlist)
      pvbox.add(label)
      label.show()
      liststore = gtk.ListStore(gtk.gdk.Pixbuf)
      self.crosspattern = gtk.ComboBox(liststore)
      cell = gtk.CellRendererPixbuf()
      self.crosspattern.pack_start(cell, True)
      self.crosspattern.add_attribute(cell, 'pixbuf', 0)
      liststore.append((gtk.gdk.pixbuf_new_from_file(FGlobs.pkgdatadir / "classic_cross.png"), ))
      liststore.append((gtk.gdk.pixbuf_new_from_file(FGlobs.pkgdatadir / "mk2_cross.png"), ))
      liststore.append((gtk.gdk.pixbuf_new_from_file(FGlobs.pkgdatadir / "pat3.png"), ))
      pvbox.pack_start(self.crosspattern, True, True, 0)
      self.crosspattern.show()
      self.crossbox.pack_start(patternbox, False, False, 0)
      patternbox.show()
      cross_sizegroup2.add_widget(patternbox)
      self.crosspattern.set_active(0)
      self.crosspattern.connect("changed", self.cb_crosspattern)
      set_tip(self.crosspattern, _('This selects the response curve of the crossfader.\n\nThe mid-point attenuations are -3dB, 0dB, and -22dB respectively.'))
      patternbox.pack_start(pvbox, True, True, 0)
      pvbox.show()
      
      
      sg4.add_widget(self.crosspattern)
      
      passbox = gtk.HBox()
      passbox.set_spacing(2)
      
      tvbox = gtk.VBox()
      # TC: The time taken for a full sweep of the crossfader when the user hits the crossfader pass button.
      label = gtk.Label(_('Time'))
      attrlist = pango.AttrList()
      attrlist.insert(pango.AttrSize(8000, 0, len(_('Time'))))
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
      set_tip(tvbox, _('The time in seconds that the crossfader will take to automatically pass across when the button to the right is clicked.'))
      passbox.pack_start(tvbox, False, False, 0)
      tvbox.show()
      sg4.add_widget(psvbox)
      
      pvbox = gtk.VBox()
      # TC: The crossfader pass-across button text. The actual button appears as [<-->] with this text above it.
      label = gtk.Label(_('Pass'))
      attrlist = pango.AttrList()
      attrlist.insert(pango.AttrSize(8000, 0, len(_('Pass'))))
      label.set_attributes(attrlist)
      pvbox.add(label)
      label.show()
      image = gtk.Image()
      image.set_from_file(FGlobs.pkgdatadir / "pass.png")
      image.show()
      self.passbutton = gtk.Button()
      self.passbutton.set_size_request(53, -1)
      self.passbutton.add(image)
      self.passbutton.connect("clicked", self.callback, "pass-crossfader")
      pvbox.add(self.passbutton)
      self.passbutton.show()
      set_tip(pvbox, _('This button causes the crossfader to move to the opposite side at a speed determined by the speed selector to the left.'))
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
      # TC: This text appears above the stream mix peak level meter.
      self.stream_peak_box = make_meter_unit(_('Peak'), self.str_l_peak, self.str_r_peak)
      self.streammeterbox.pack_start(self.stream_peak_box)
      self.stream_peak_box.show()
      set_tip(self.stream_peak_box, _('A peak hold meter indicating the signal strength of the stream audio.'))

      sg = gtk.SizeGroup(gtk.SIZE_GROUP_HORIZONTAL)
      self.stream_indicator = []
      for i in range(PGlobs.num_streamers):
         self.stream_indicator.append(StreamMeter(1, 100))
      self.stream_indicator_box, self.listener_indicator = make_stream_meter_unit(_('Streams'), self.stream_indicator)
      self.streammeterbox.pack_start(self.stream_indicator_box, False, False, 0)
      self.stream_indicator_box.show()
      sg.add_widget(self.stream_indicator_box)

      if PGlobs.num_recorders:
         self.recording_panel = RecordingPanel(PGlobs.num_recorders)
         self.streammeterbox.pack_start(self.recording_panel, False)
         self.recording_panel.show()

      self.str_l_rms_vu = vumeter()
      self.str_r_rms_vu = vumeter()
      # TC: This text appears above the stream mix VU meter.
      stream_vu_box = make_meter_unit(_('VU'), self.str_l_rms_vu, self.str_r_rms_vu)
      self.streammeterbox.pack_start(stream_vu_box)
      stream_vu_box.show()
      set_tip(stream_vu_box, _('A VU meter for the stream audio.'))
       
      # TC: Appears above the mic meters as a label followed by a number.
      self.mic_meters = [MicMeter(_("Ch"), i) for i in range(1, PGlobs.num_micpairs * 2 + 1)]
      if len(self.mic_meters) <= 4:
         for meter in self.mic_meters:
            self.micmeterbox.pack_start(meter)
            meter.show()
      else:
         chvbox = gtk.VBox()
         chvbox.set_spacing(4)
         self.micmeterbox.pack_start(chvbox)
         chvbox.show()
         def showhide(widget, state, box, l, r):
            if l.flags() & gtk.SENSITIVE or r.flags() & gtk.SENSITIVE:
               box.show()
            else:
               box.hide()
         for l, r in zip(*((iter(self.mic_meters),) * 2)):
            chhbox = gtk.HBox()
            chhbox.set_spacing(4)
            chhbox.pack_start(l, False)
            chhbox.pack_end(r, False)
            chvbox.pack_start(chhbox)
            chhbox.show()
            for each in l, r:
               each.connect("state-changed", showhide, chhbox, l, r)
               each.show()
      
      set_tip(self.micmeterbox, _('A peak hold meter indicating the microphone signal strength and a meter indicating attenuation levels in the microphone signal processing system. Green indicates attenuation from the noise gate, yellow from the de-esser, red from the limiter.'))
      
      # Create the jingles player
      self.jingles = Jingles(self)

      # Variable initialisation
      self.songname = u""
      self.newmetadata = False
      self.showing_left_file_requester = False
      self.showing_right_file_requester = False
      self.old_metadata = ("",) * 4
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
      self.jingles_playing = slot_object(0)
      self.interlude_playing = slot_object(0)
      self.player_left.playtime_elapsed = slot_object(0)
      self.player_right.playtime_elapsed = slot_object(0)
      self.player_left.mixer_playing = slot_object(0)
      self.player_right.mixer_playing = slot_object(0)
      self.player_left.mixer_signal_f = slot_object(0)
      self.player_right.mixer_signal_f = slot_object(0)
      self.player_left.mixer_cid = slot_object(0)
      self.player_right.mixer_cid = slot_object(0)
      self.left_compression_level = slot_object(0)
      self.right_compression_level = slot_object(0)
      self.left_deess_level = slot_object(0)
      self.right_deess_level = slot_object(0)
      self.left_noisegate_level = slot_object(0)
      self.right_noisegate_level = slot_object(0)
      self.jingles.mixer_jingles_cid = slot_object(0)
      self.jingles.mixer_interlude_cid = slot_object(0)
      self.player_left.runout = slot_object(0)
      self.player_right.runout = slot_object(0)
      self.metadata_left_ctrl = slot_object(0)
      self.metadata_right_ctrl = slot_object(0)
      self.player_left.silence = slot_object(0.0)
      self.player_right.silence = slot_object(0.0)
      
      self.feature_set = gtk.ToggleButton()
      self.feature_set.set_active(True)
      self.feature_set.connect("toggled", self.callback, "Features")

      self.full_wst = WindowSizeTracker(self.window, True)
      self.min_wst = WindowSizeTracker(self.window, False)

      self.in_vu_timeout = False
      self.vucounter = 0
      self.session_filename = pm.basedir / "main_session"
      self.files_played = {}
      self.files_played_offline = {}
      
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
         "right_additional_metadata": self.metadata_right_ctrl,
         "silence_l"                : self.player_left.silence,
         "silence_r"                : self.player_right.silence,
         }
         
      for i, mic in enumerate(self.mic_meters):
         self.vumap.update({"mic_%d_levels" % (i + 1): mic})

      self.controls= midicontrols.Controls(self)
      self.controls.load_prefs()

      self.window.realize()     # prevent ubuntu crash when activating vu meters
      media_sg = gtk.SizeGroup(gtk.SIZE_GROUP_HORIZONTAL)
      media_sg.add_widget(self.vbox3L)
      media_sg.add_widget(self.vbox3R)
      
      self.server_window = SourceClientGui(self)
      self.prefs_window = mixprefs(self)
      self.prefs_window.load_player_prefs()
      self.prefs_window.apply_player_prefs()

      self.menu.quitmenu_i.connect_object("activate", self.delete_event, self.window, None)
      self.menu.outputmenu_i.connect("activate", lambda w: self.server_window.window.present())
      self.menu.prefsmenu_i.connect("activate", lambda w: self.prefs_window.window.present())
      self.menu.jinglesmenu_i.connect("activate", lambda w: self.jingles.window.present())
      self.menu.profilesmenu_i.connect("activate", lambda w: pm.profile_dialog.present())
      self.menu.aboutmenu_i.connect("activate", lambda w: self.prefs_window.show_about())

      self.jack = JackMenu(self.menu, lambda s, r: self.mixer_write("ACTN=jack%s\n%s" % (s, r), True), lambda: self.mixer_read())
      self.jack.load(startup=True)

      self.vutimeout = gobject.timeout_add(50, self.vu_update)
      self.statstimeout = gobject.timeout_add(100, self.stats_update)
      self.savetimeout = gobject.timeout_add_seconds(60, threadslock(self.save_session));
      
      for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
         signal.signal(sig, lambda s, f: glib.idle_add(threadslock(self.destroy)))
      
      (self.full_wst, self.min_wst)[bool(self.simplemixer)].apply()
      self.window.connect("configure_event", self.configure_event)
      self.jingles.wst.apply()

      if self.prefs_window.restore_session_option.get_active():
         print "Restoring previous session"
         self.player_left.restore_session()
         self.player_right.restore_session()
         self.restore_session()
      self.session_loaded = True
       
      self.window.set_focus_chain((self.player_left.scrolllist, self.player_right.scrolllist))
       
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
      gobject.idle_add(lambda: self.prefs_window.window.realize() and False)
      
      self.player_left.treeview.emit("cursor-changed")
      self.player_right.treeview.emit("cursor-changed")

      if args.channels is not None:
         for each in args.channels:
            self.mic_opener.open(each)

      if args.voip is not None:
         if args.voip == ["public"]:
            self.greenphone.set_active(True)
         elif args.voip == ["private"]:
            self.redphone.set_active(True)

      if args.servers is not None:
         servtabs = self.server_window.streamtabframe.tabs
         for n in range(len(servtabs)):
            if chr(n + ord("1")) in args.servers:
               servtabs[n].server_connect.set_active(True)
   
      if args.crossfader is not None:
         if args.crossfader == "1":
            self.passleft.clicked()
         elif args.crossfader == "2":
            self.passright.clicked()

      if args.players is not None:
         if "1" in args.players:
            self.player_left.play.clicked()
         if "2" in args.players:
            self.player_right.play.clicked()
               
   def main(self):
      gtk.main()


def main():
   try:
      run_instance = MainWindow()
   except (MainWindow.initfailed, MainWindow.initcleanexit, KeyboardInterrupt):
      return 5
   else:
      try:
         run_instance.main()
      except KeyboardInterrupt:
         return 5
   return 0
