#   IDJCmedia.py: GUI code for main media players in IDJC
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

__all__ = [ 'IDJC_Media_Player', 'make_arrow_button', 'supported' ]

import os
import sys
import time
import urllib
import subprocess
import random
import signal
import re
import xml.dom.minidom as mdom
from stat import *
from collections import deque
from functools import partial

import pygtk
pygtk.require('2.0')
import gtk
import gobject
import pango
import mutagen
from mutagen.mp3 import MP3
from mutagen.flac import FLAC
from mutagen.mp4 import MP4
from mutagen.easyid3 import EasyID3
from mutagen.apev2 import APEv2
from mutagen.asf import ASF
   
import popupwindow
from mutagentagger import*
from IDJCfree import *
from idjc_config import *
from ln_text import ln

try:
   from collections import namedtuple, defaultdict
except:
   from nt import namedtuple

# Named tuple for a playlist row.
class PlayerRow(namedtuple("PlayerRow", "rsmeta filename length meta encoding title artist replaygain cuesheet")):
   def __nonzero__(self):
      return self.rsmeta != "<s>valid</s>"

# Playlist value indicating a file isn't valid.
NOTVALID = PlayerRow("<s>valid</s>", "", 0, "", "latin1", "", "", 0.0, None)

# Replay Gain value to indicate default.
RGDEF = 100.0

# Pathname is an absolute file path or 'missing' or 'pregap'.
CueSheetTrack = namedtuple("CueSheetTrack", "pathname play tracknum index performer title offset duration replaygain")

class CueSheetListStore(gtk.ListStore):
   _columns = (str, int, int, int, str, str, int, int, float)
   assert len(_columns) == len(CueSheetTrack._fields)
   def __nonzero__(self):
      return len(self) != 0
      
   def __getitem__(self, i):
      return CueSheetTrack(*gtk.ListStore.__getitem__(self, i))
      
   def __iter__(self):
      i = 0
      while 1:
         try:
            val = self[i]
         except IndexError:
            break
         yield val
         i += 1
      
   def __init__(self):
      gtk.ListStore.__init__(self, *self._columns)

class NumberedLabel(gtk.Label):
   attrs = pango.AttrList()
   attrs.insert(pango.AttrFamily("Monospace" , 0, 3))
   #attrs.insert(pango.AttrWeight(pango.WEIGHT_BOLD, 0, 3))
   
   def set_value(self, value):
      self.set_text("--" if value is None else "%02d" % value)
      
   def get_value(self):
      text = self.get_text()
      return None if text == "--" else int(self.text)
     
   def __init__(self, value=None):
      gtk.Label.__init__(self)
      self.set_attributes(self.attrs)
      self.set_value(value)

class CellRendererDuration(gtk.CellRendererText):
   """Render a value in frames as a time mm:ss:hs right justified."""
   
   __gproperties__ = { "duration" : (gobject.TYPE_UINT64, "duration",
      "playback time expressed in CD audio frames",
      0, long(3e9), 0, gobject.PARAM_WRITABLE) }
   
   def __init__(self):
      gtk.CellRendererText.__init__(self)
      self.set_property("xalign", 1.0)

   def do_set_property(self, property, value):
      if property.name == "duration":
         s, f = divmod(value, 75)
         m, s = divmod(s, 60)
         self.props.text = "%d:%02d.%02d" % (m, s, f // 0.75)

class CuesheetPlaylist(gtk.Frame):
   def description_col_func(self, column, cell, model, iter):
      line = model[model.get_path(iter)[0]]
      desc = " - ".join(x for x in (line.performer, line.title) if x)
      desc = desc or os.path.splitext(os.path.split(line.pathname)[1])[0]
      cell.props.text = desc

   def play_clicked(self, cellrenderer, path):
      model = self.treeview.get_model()
      iter = model.get_iter(path)
      col = CueSheetTrack._fields.index("play")
      val = model.get_value(iter, col)
      model.set_value(iter, col, not val)

   def __init__(self):
      gtk.Frame.__init__(self, ln.cuesheet_playlist)
      self.set_border_width(3)
      
      vbox = gtk.VBox()
      vbox.set_border_width(4)
      vbox.set_spacing(2)
      self.add(vbox)
      vbox.show()
      hbox = gtk.HBox()
      hbox.set_spacing(6)
      vbox.pack_start(hbox, False)
      
      def nextprev_unit(label_text):
         def icon_button(stock_item):
            button = gtk.Button()
            image = gtk.image_new_from_stock(stock_item, gtk.ICON_SIZE_MENU)
            button.set_image(image)
            image.show()
            return button
         
         box = gtk.HBox()
         box.set_spacing(6)
         prev = icon_button(gtk.STOCK_MEDIA_PREVIOUS)
         box.pack_start(prev)
         prev.show()
         
         lhbox = gtk.HBox()
         box.pack_start(lhbox, False)
         lhbox.show()
         
         label = gtk.Label(label_text + " ")
         lhbox.pack_start(label, False)
         label.show()
         numbered = NumberedLabel()
         lhbox.pack_start(numbered, False)
         numbered.show()
         
         next = icon_button(gtk.STOCK_MEDIA_NEXT)
         box.pack_start(next)
         next.show()
         box.show()
         return box, prev, next
         
      box_t, self.prev_track, self.next_track = nextprev_unit(ln.cue_track)
      box_i, self.prev_index, self.next_index = nextprev_unit(ln.cue_index)
      hbox.pack_start(box_t, fill=False)
      hbox.pack_start(box_i, fill=False)
      hbox.show()
      
      scrolled = gtk.ScrolledWindow()
      scrolled.set_size_request(-1, 117)
      scrolled.set_policy(gtk.POLICY_NEVER, gtk.POLICY_ALWAYS)
      scrolled.set_shadow_type(gtk.SHADOW_ETCHED_IN)
      vbox.pack_start(scrolled)
      scrolled.show()
      self.treeview = gtk.TreeView()
      #self.treeview.set_headers_visible(True)
      scrolled.add(self.treeview)
      self.treeview.show()
      #self.treeview.set_fixed_height_mode(True)
      
      renderer_toggle = gtk.CellRendererToggle()
      renderer_toggle.connect("toggled", self.play_clicked)
      renderer_text_desc = gtk.CellRendererText()
      renderer_text_desc.set_property("ellipsize", pango.ELLIPSIZE_END)
      renderer_text_rjust = gtk.CellRendererText()
      renderer_text_rjust.set_property("xalign", 0.9)
      renderer_duration = CellRendererDuration()
      
      play = gtk.TreeViewColumn(ln.cue_play, renderer_toggle, active=1)
      self.treeview.append_column(play)
      track = gtk.TreeViewColumn(ln.cue_track_abbrev, renderer_text_rjust, text=2)
      self.treeview.append_column(track)
      index = gtk.TreeViewColumn(ln.cue_index_abbrev, renderer_text_rjust, text=3)
      self.treeview.append_column(index)
      description = gtk.TreeViewColumn(ln.cue_description, renderer_text_desc)
      description.set_expand(True)
      description.set_cell_data_func(renderer_text_desc, self.description_col_func)
      self.treeview.append_column(description)
      duration = gtk.TreeViewColumn(ln.cue_duration, renderer_duration)
      duration.add_attribute(renderer_duration, "duration", 7)
      self.treeview.append_column(duration)


class ButtonFrame(gtk.Frame):
   def __init__(self, title):
      gtk.Frame.__init__(self)
      attrlist = pango.AttrList()
      attrlist.insert(pango.AttrSize(8000, 0, len(title)))
      label = gtk.Label(title)
      label.set_attributes(attrlist)
      self.set_label_widget(label)
      label.show()
      self.hbox = gtk.HBox()
      self.add(self.hbox)
      self.hbox.show()
      self.set_shadow_type(gtk.SHADOW_NONE)
      self.set_label_align(0.5, 0.5)

class ExternalPL(gtk.Frame):
   def get_next(self):
      next = self._get_next()
      if next is None:
         return self._get_next()
      return next
   
   def _get_next(self):
      if self.active.get_active():
         try:
            line = self.gen.next()
         except StopIteration:
            self.gen = self.player.get_elements_from([self.pathname])
            line = None
         return line
      return None
   
   def cb_active(self, widget):
      if widget.get_active():
         self.pathname = (self.filechooser, self.directorychooser)[self.radio_directory.get_active()].get_filename()
         if self.pathname is not None:
            self.gen = self.player.get_elements_from([self.pathname])
            try:
               line = self.gen.next()
            except StopIteration:
               widget.set_active(False)
            else:
               self.player.stop.clicked()
               self.player.liststore.clear()
               self.player.liststore.append(line)
               self.player.treeview.get_selection().select_path(0)
               self.vbox.set_sensitive(False)
         else:
            widget.set_active(False)
      else:
         self.vbox.set_sensitive(True)
   
   def cb_newselection(self, widget, radio):
      radio.set_active(True)
   
   def make_line(self, radio, dialog):
      button = gtk.FileChooserButton(dialog)
      dialog.set_current_folder(self.player.parent.home)
      hbox = gtk.HBox()
      hbox.pack_start(radio, False, False, 0)
      hbox.pack_start(button, True, True, 0)
      radio.show()
      button.show()
      return hbox
   
   def __init__(self, player):
      self.player = player
      tooltips = player.parent.tooltips
      gtk.Frame.__init__(self, " " + ln.epc_title + " ")
      self.set_border_width(4)
      hbox = gtk.HBox()
      self.add(hbox)
      hbox.set_border_width(8)
      hbox.set_spacing(10)
      hbox.show()
      self.vbox = gtk.VBox()
      hbox.pack_start(self.vbox, True, True, 0)
      self.vbox.show()
      self.active = gtk.ToggleButton(ln.epc_active)
      self.active.connect("toggled", self.cb_active)
      hbox.pack_end(self.active, False, False, 0)
      self.active.show()

      filefilter = gtk.FileFilter()
      filefilter.add_pattern("*.m3u")
      filefilter.add_pattern("*.pls")
      filefilter.add_pattern("*.xspf")

      self.filechooser = gtk.FileChooserDialog(title = ln.epc_choosefile, buttons = (gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT, gtk.STOCK_OPEN, gtk.RESPONSE_ACCEPT))
      self.filechooser.set_filter(filefilter)
      self.directorychooser = gtk.FileChooserDialog(title = ln.epc_choosedirectory, action = gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER, buttons = (gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT, gtk.STOCK_OPEN, gtk.RESPONSE_ACCEPT))
      
      self.radio_file = gtk.RadioButton()
      self.radio_directory = gtk.RadioButton(self.radio_file)
      
      self.filechooser.connect("selection-changed", self.cb_newselection, self.radio_file)
      self.directorychooser.connect("selection-changed", self.cb_newselection, self.radio_directory)
      
      fbox = self.make_line(self.radio_file, self.filechooser)
      tooltips.set_tip(fbox, ln.external_playlist)
      dbox = self.make_line(self.radio_directory, self.directorychooser)
      tooltips.set_tip(dbox, ln.external_directory)
      
      self.vbox.pack_start(fbox, True, True, 0)
      self.vbox.pack_start(dbox, True, True, 0)
      
      fbox.show()
      dbox.show()

class AnnouncementDialog(gtk.Dialog):
   def write_changes(self, widget):
      m = "%02d" % int(self.minutes.get_value())
      s = "%02d" % int(self.seconds.get_value())
      self.model.set_value(self.iter, 3, "00" + m + s)
      b = self.tv.get_buffer()
      text = b.get_text(b.get_start_iter(), b.get_end_iter())
      self.model.set_value(self.iter, 4, urllib.quote(text))
      self.player.reselect_please = True
   def restore_mic_playnext(self, widget):
      self.player.parent.mic_opener.close_all()
      if self.model.iter_next(self.iter) is not None:
         self.player.play.clicked()
   def delete_announcement(self, widget, event=None):
      self.model.remove(self.iter)
      self.player.reselect_please = True
      gtk.Dialog.destroy(self)
   def timeout_remove(self, widget):
      gobject.source_remove(self.timeout)
   def timer_update(self, lock = True):
      if lock:
         gtk.gdk.threads_enter()
      inttime = int(self.cdt - time.time())
      if inttime != self.oldinttime:
         if inttime > 0:
            stime = "%2d:%02d" % divmod(inttime, 60)
            self.countdownlabel.set_text(stime)
            if inttime == 5:
               self.attrlist.change(self.fontcolour_red)
            if lock:
               gtk.gdk.threads_leave()
            return True
         else:
            self.countdownlabel.set_text("--:--")
            self.attrlist.change(self.fontcolour_black)
            if lock:
               gtk.gdk.threads_leave()
            return False
      if lock:
         gtk.gdk.threads_leave()
      return True
   def cb_keypress(self, widget, event):
      self.player.parent.cb_key_capture(widget, event)
      if event.keyval == 65307:
         return True
      if event.keyval == 65288 and self.mode == "active":
         self.cancel_button.clicked()
   def __init__(self, player, model, iter, mode):
      self.player = player
      self.model = model
      self.iter = iter
      self.mode = mode
      if mode == "initial":
         model.set_value(iter, 3, "110000")
         gtk.Dialog.__init__(self, ln.announcement_initial, player.parent.window, gtk.DIALOG_MODAL)
      elif mode == "delete_modify":
         gtk.Dialog.__init__(self, ln.announcement_delete, player.parent.window, gtk.DIALOG_MODAL)
      elif mode == "active":
         gtk.Dialog.__init__(self, ln.announcement_use, player.parent.window, gtk.DIALOG_MODAL)
      self.connect("key-press-event", self.cb_keypress)
      ivbox = gtk.VBox()
      ivbox.set_border_width(10)
      ivbox.set_spacing(8)
      self.vbox.add(ivbox)
      ivbox.show()
      sw = gtk.ScrolledWindow()
      sw.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
      sw.set_shadow_type(gtk.SHADOW_IN)
      sw.set_size_request(500, 200)
      ivbox.pack_start(sw, True, True, 0)
      sw.show()
      self.tv = gtk.TextView()
      if mode == "active":
         self.tv.unset_flags(gtk.CAN_FOCUS)
      sw.add(self.tv)
      self.tv.show()
      ihbox = gtk.HBox()
      ivbox.pack_start(ihbox, False, False, 0)
      ihbox.show()
      
      chbox = gtk.HBox()
      
      if mode == "initial" or mode == "delete_modify":
         countdown_label = gtk.Label(ln.announcement_countdown_label)
         chbox.pack_start(countdown_label, False, False, 0)
         countdown_label.show()
         minutes_adj = gtk.Adjustment(0.0, 0.0, 59.0, 1.0)
         seconds_adj = gtk.Adjustment(0.0, 0.0, 59.0, 1.0)
         self.minutes = gtk.SpinButton(minutes_adj)
         self.seconds = gtk.SpinButton(seconds_adj)
         sep = gtk.Label(":")
         chbox.pack_start(self.minutes, False, False, 0)
         self.minutes.show()
         chbox.pack_start(sep, False, False, 0)
         sep.show()
         chbox.pack_start(self.seconds, False, False, 0)
         self.seconds.show()
         
      if mode == "active":
         cdtime = model.get_value(iter, 3)[2:6]
         if cdtime != "0000":
            cd = int(cdtime[:2]) * 60 + int(cdtime[2:])
            self.cdt = time.time() + cd + 1
            self.countdownlabel = gtk.Label()
            self.attrlist = pango.AttrList()
            fontdesc = pango.FontDescription("monospace bold condensed 15")
            self.attrlist.insert(pango.AttrFontDesc(fontdesc, 0, 5))
            self.fontcolour_black = pango.AttrForeground(0, 0, 0, 0, 5)
            self.fontcolour_red = pango.AttrForeground(65535, 0, 0, 0, 5)
            self.attrlist.insert(self.fontcolour_black)
            self.countdownlabel.set_attributes(self.attrlist)
            self.oldinttime = -2
            self.timer_update(False)
            self.timeout = gobject.timeout_add(100, self.timer_update)
            self.connect("destroy", self.timeout_remove)
            chbox.pack_start(self.countdownlabel, True, False, 0)
            self.countdownlabel.show()
         
      ihbox.pack_start(chbox, True, False, 0)
      chbox.show()
      
      if mode == "delete_modify" or mode == "active":
         lr = model.get_value(iter, 3)
         text = model.get_value(iter, 4)
         self.tv.get_buffer().set_text(urllib.unquote(text))
      if mode == "delete_modify":
         self.minutes.set_value((int(lr[2:4])))
         self.seconds.set_value((int(lr[4:6])))
      if mode == "active":
         self.player.parent.mic_opener.open_auto()
         
      thbox = gtk.HBox()
      ivbox.pack_start(thbox, False, False, 0)
      thbox.show()
      label = gtk.Label(ln.announcement_next_track)
      thbox.pack_start(label, False, False, 0)
      label.show()
      entry = gtk.Entry()
      entry.set_editable(False)
      entry.unset_flags(gtk.CAN_FOCUS)
      ni = model.iter_next(iter)
      if ni and model.get_value(ni, 0)[0] != ">" : 
         entry.set_text(model.get_value(ni, 3))
      thbox.pack_start(entry, True, True, 0)
      entry.show()
      
      self.ok_button = gtk.Button(gtk.STOCK_OK)
      if mode == "initial" or mode == "delete_modify":
         self.ok_button.connect("clicked", self.write_changes)
      if mode == "active":
         self.ok_button.connect("clicked", self.restore_mic_playnext)
      self.ok_button.connect_object("clicked", gtk.Dialog.destroy, self)
      self.ok_button.set_use_stock(True)
      self.action_area.add(self.ok_button)
      self.ok_button.show()
      if mode == "delete_modify":
         self.delete_button = gtk.Button(gtk.STOCK_DELETE)
         self.delete_button.connect("clicked", self.delete_announcement)
         self.delete_button.set_use_stock(True)
         self.action_area.add(self.delete_button)
         self.delete_button.show()
      self.cancel_button = gtk.Button(gtk.STOCK_CANCEL)
      if mode == "initial":
         self.connect("delete-event", self.delete_announcement)
         self.cancel_button.connect("clicked", self.delete_announcement)
      else:
         self.cancel_button.connect_object("clicked", gtk.Dialog.destroy, self)
      self.cancel_button.set_use_stock(True)
      self.action_area.add(self.cancel_button)
      self.cancel_button.show()
      if mode == "active":
         self.ok_button.grab_focus()
      
class Supported(object):
   def _check(self, pathname, which):
      ext = os.path.splitext(pathname)[1].lower()
      return ext in which and ext or False
   def playlists_as_text(self):
      return "(*" + ", *".join(self.playlists) + ")"
   def media_as_text(self):
      return "(*" + ", *".join(self.media) + ")"
   def check_media(self, pathname):
      return self._check(pathname, self.media)
   def check_playlists(self, pathname):
      return self._check(pathname, self.playlists)
   def __init__(self):
      self.media = [ ".ogg", ".oga", ".wav", ".aiff", ".au", ".txt", ".cue" ]
      self.playlists = [ ".m3u", ".xspf", ".pls" ]
      
      if avcodec and avformat:
         self.media.append(".avi")
         self.media.append(".wma")
         self.media.append(".ape")
         self.media.append(".mpc")
         self.media.append(".mp4")
         self.media.append(".m4a")
         self.media.append(".m4b")
         self.media.append(".m4p")
      if flacenabled:
         self.media.append(".flac")
      if speexenabled:
         self.media.append(".spx")

supported = Supported()

# Arrow button creation helper function
def make_arrow_button(self, arrow_type, shadow_type, data):
   button = gtk.Button();
   arrow = gtk.Arrow(arrow_type, shadow_type);
   button.add(arrow)
   button.connect("clicked", self.callback, data)
   button.show()
   arrow.show()
   return button

def get_number_for(token, string):
   try:
      end = string.rindex(token)
      start = end - 1
      while start >= 0 and (string[start].isdigit() or string[start] == "."):
         start = start - 1
      return int(float(string[start+1:end]))
   except ValueError:
      return 0
   
class nice_listen_togglebutton(gtk.ToggleButton):
   def __init__(self, label = None, use_underline = True):
      try:
         gtk.ToggleButton.__init__(self, label, use_underline)
      except RuntimeError:
         gtk.ToggleButton.__init__(self, label)
   def __str__(self):
      return gtk.ToggleButton.__str__(self) + " auto inconsistent when insensitive"
   def set_sensitive(self, bool):
      if bool is False:
         gtk.ToggleButton.set_sensitive(self, False)
         gtk.ToggleButton.set_inconsistent(self, True)
      else:
         gtk.ToggleButton.set_sensitive(self, True)
         gtk.ToggleButton.set_inconsistent(self, False)
        

class CueSheet(object):
   """A class for parsing cue sheets."""

   _operands = (("PERFORMER", "SONGWRITER", "TITLE", "PREGAP", "POSTGAP"),
                ("FILE", "TRACK", "INDEX"))
   _operands = dict((k, v + 1) for v, o in enumerate(_operands) for k in o)

   # Try to split a string into three parts with a large quoted section
   # and parts fore and aft.
   _quoted = re.compile(r'(.*?)[ \t]"(.*)"[ \t](.*)').match

   def _time_handler(self, time_str):
      """Returns the number of frames of audio (75ths of seconds)

      Minutes can exceed 99 going beyond the cue sheet standard.

      """
      try:
         mm, ss, ff = [int(x) for x in time_str.split(":")]
      except ValueError:
         raise ValueError("time must be in (m*)mm:ss:ff format %s" % self.line)

      if ff < 0 or ff > 74 or ss < 0 or ss > 59 or mm < 0:
         raise ValueError("a time value is out of range %s" % self.line)

      return ff + 75 * ss + 75 * 60 * mm

   def _int_handler(self, int_str):
      """Attempt to convert to an integer."""

      try:
         ret = int(int_str)
      except:
         raise ValueError("expected integer value for %s %s", (int_str, self.line))
      return ret

   @classmethod
   def _tokenize(cls, iterable):
      """Scanner/tokenizer for cue sheets.
      
      This routine will iteratively take one line at a time and return
      the line number, command, and any operands related to the command.
      
      Quoted text will have spaces and tabs intact and counts as one,
      otherwise all consecutive non-whitespace is a token. The first
      token is the command, the rest are it's operands.
      
      """
      for i, line in enumerate(iterable):
         line = line.strip() + " "
         match = cls._quoted(line)
         if match:
            left, quoted, right = match.groups()
            left = left.replace("\t", " ").split()
            right = right.replace("\t", " ").split()
         else:
            left = line.replace("\t", " ").split()
            right = [""]
            quoted = ""
               
         tokens = filter(lambda x: x, left + [quoted] + right)
         yield i + 1, tokens[0].upper(), tokens[1:]

   def _parse_PERFORMER(self):
      self.segment[self.tracknum][self.command].append(self.operand[0])
      
   _parse_SONGWRITER = _parse_TITLE = _parse_PERFORMER

   def _parse_FILE(self):
      if not self.operand[1] in ("WAVE", "MP3", "AIFF"):
         raise ValueError("unsupported file type %s" % self.line)
         
      self.filename = self.operand[0]
      self.prevframes = 0
      
   def _parse_TRACK(self):
      if self.filename is None:
         raise ValueError("no filename yet specified %s" % self.line)

      if self.tracknum and self.index < 1:
         raise ValueError("track %02d lacks a 01 index" % self.tracknum)

      if self.operand[1] != "AUDIO":
         raise ValueError("only AUDIO track datatype supported %s" % self.line)

      num = self._int_handler(self.operand[0])
      self.tracknum += 1
      self.index = -1
      if num != self.tracknum:
         raise ValueError("unexpected track number %s" % self.line)
                  
   def _parse_PREGAP(self):
      if self.tracknum == 0 or self.index != -1 or "PREGAP" in self.segment[self.tracknum]:
         raise ValueError("unexpected PREGAP command %s" % self.line)
         
      self.segment[self.tracknum]["PREGAP"] = self._time_handler(self.operand[0])

   def _parse_INDEX(self):
      if self.tracknum == 0:
         raise ValueError("no track yet specified %s" % self.line)
      
      if "POSTGAP" in self.segment[self.tracknum]:
         raise ValueError("INDEX command following POSTGAP %s" % self.line)
      
      num = self._int_handler(self.operand[0])
      frames = self._time_handler(self.operand[1])
      
      if self.tracknum == 1 and self.index == -1 and frames != 0:
         raise ValueError("first index must be zero for a file %s" % self.line)

      if self.index == -1 and num == 1:
         self.index += 1
      self.index += 1
      if num != self.index:
         raise ValueError("unexpected index number %s" % self.line)
         
      if frames < self.prevframes:
         raise ValueError("index time before the previous index %s" % self.line)
         
      if self.prevframes and frames == self.prevframes:
         raise ValueError("index time no different than previously %s" % self.line)
         
      self.segment[self.tracknum][self.index] = (self.filename, frames)
      
      self.prevframes = frames
                  
   def _parse_POSTGAP(self):
      if self.tracknum == 0 or self.index < 1 or "POSTGAP" in self.segment[self.tracknum]:
         raise ValueError("unexpected POSTGAP command %s" % self.line)
         
      self.segment[self.tracknum]["POSTGAP"] = self._time_handler(operand[0])

   def parse(self, iterable):
      """Return a parsed cuesheet object."""
      
      self.filename = None
      self.tracknum = 0
      self.segment = defaultdict(partial(defaultdict, list))

      for self.i, self.command, self.operand in self._tokenize(iterable):
         if self.command not in self._operands:
            continue

         self.line = "on line %d" % self.i

         if len(self.operand) != self._operands[self.command]:
            raise ValueError("wrong number of operands got %d required %d %s" %
                  (len(self.operand), self._operands[self.command], self.line))
         else:
            getattr(self, "_parse_" + self.command)()

      if self.tracknum == 0:
         raise ValueError("no tracks")
         
      if self.index < 1:
         raise ValueError("track %02d lacks a 01 index" % tracknum)
       
      for each in self.segment.itervalues():
          del each.default_factory
      del self.segment.default_factory
                 
      return self.segment

       
class IDJC_Media_Player:
   def make_cuesheet_playlist_entry(self, cue_pathname):
      cuesheet_liststore = CueSheetListStore()
      try:
         with open(cue_pathname) as f:
            segment_data = CueSheet().parse(f)
      except (IOError, ValueError), e:
         print "failed reading cue sheet", cue_pathname
         print e
         return NOTVALID
      
      basepath = os.path.split(cue_pathname)[0]
      oldfilename = None
      totalframes = trackframes = cumulativeframes = 0
      global_cue_performer = global_cue_title = ""

      for key, val in sorted(segment_data.iteritems()):
         track = key
         cue_performer = ", ".join(val.get("PERFORMER", []))
         cue_title = ", ".join(val.get("TITLE", []))
         if key == 0:
            global_cue_performer = cue_performer
            global_cue_title = cue_title
         else:
            for key2, val2 in sorted(val.iteritems()):
               if isinstance(key2, int):
                  index = key2
                  filename, frames = val2
                  if filename != oldfilename:
                     oldfilename = filename
                     pathname = os.path.join(basepath, filename)
                     track_data = self.get_media_metadata(pathname)
                     if track_data:
                        trackframes = 75 * track_data.length
                        totalframes += trackframes
                        replaygain = track_data.replaygain
                     else:
                        pathname = ""
                        trackframes = 0
                        replaygain = RGDEF

                  if not cue_performer:
                     cue_performer = track_data.artist or global_cue_performer
                  if not cue_title:
                     cue_title = track_data.title or global_cue_title

                  try:
                     nextoffset = val[index + 1][1]
                  except LookupError:
                     try:
                        nextoffset = segment_data[track + 1][0][1]
                     except LookupError:
                        try:
                           nextoffset = segment_data[track + 1][1][1]
                        except LookupError:
                           nextoffset = trackframes
                  
                  if nextoffset == 0:
                     nextoffset = trackframes
                  duration = nextoffset - frames
                  if not trackframes:
                     duration = frames = 0

                  element = CueSheetTrack(pathname, bool(pathname), track, index,
                                       cue_performer, cue_title, frames, duration, replaygain)
                  cuesheet_liststore.append(element)

      if global_cue_performer and global_cue_title:
         metadata = global_cue_performer + " - " + global_cue_title
      else:
         metadata = global_cue_performer or global_cue_title
      metadata = metadata or ln.unknown
         
      element = PlayerRow('<span foreground="dark green">(Cue Sheet)</span>' + rich_safe(metadata),
            cue_pathname, totalframes // 75 + 1, metadata, "utf-8",
            global_cue_title, global_cue_performer, RGDEF, cuesheet_liststore)
         
      return element
   
   def get_media_metadata(self, filename):
      artist = u""
      title = u""
      length = 0
      artist_retval = u""
      title_retval = u""
      
      # Strip away any file:// prefix
      if filename.count("file://", 0, 7):
         filename = filename[7:]
      elif filename.count("file:", 0, 5):
         filename = filename[5:]
         
      filext = supported.check_media(filename)
      if filext == False or os.path.isfile(filename) == False:
         return NOTVALID._replace(filename=filename)
 
      if filext in (".cue", ".txt"):
         return self.make_cuesheet_playlist_entry(filename)
      else:
         cuesheet = None
 
      # Use this name for metadata when we can't get anything from tags.
      # The name will also appear grey to indicate a tagless state.
      meta_name = os.path.basename(filename)
      enclist = self.parent.fenc.split(",")
      for each in enclist:
         each = each.strip()
         if each == "@locale":
            each = self.parent.denc
         try:
            meta_name = unicode(os.path.splitext(meta_name)[0], each).lstrip("0123456789 -")
         except:
            pass
         else:
            encoding = each
            rsmeta_name = '<span foreground="dark red">(%s)</span> %s' % (ln.notag, rich_safe(meta_name))
            title_retval = meta_name
            break
      else:
         encoding = "latin1"            # Have to default to something.
         meta_name = u'Unknown'
         rsmeta_name = u'<span foreground="gray">Unknown encoding</span>'
         title_retval = u"Unknown"
         
      # Obtain as much metadata from ubiquitous tags as possible.
      # Files can have ape and id3 tags. ID3 has priority in this case.
      try:
         audio = APEv2(filename)
      except:
         rg = RGDEF
         artist = title = ""
      else:
         try: 
            rg = float(audio["REPLAYGAIN_TRACK_GAIN"][0].rstrip(" dB"))
         except:
            rg = RGDEF
         artist = audio.get("ARTIST", [u""])
         title = audio.get("TITLE", [u""])
      # ID3 is tried second so it can supercede APE tag data.
      try:
         audio = EasyID3(filename)
      except:
         pass
      else:
         try:
            rg = float(audio["replaygain_track_gain"][0].rstrip(" dB"))
         except:
            pass
         try:
            artist = audio["artist"]
         except:
            pass
         try:
            title = audio["title"]
         except:
            pass
         
      # Trying for metadata from native tagging formats.
      if avcodec and avformat and filext == ".avi":
         self.parent.mixer_write("AVFP=%s\nACTN=avformatinforequest\nend\n" % filename, True)
         while 1:
            line = self.parent.mixer_read()
            if line.startswith("avformatinfo: artist="):
               artist = line[21:].strip()
            if line.startswith("avformatinfo: title="):
               title = line[20:].strip()
            if line.startswith("avformatinfo: duration="):
               length = int(line[23:-1])
            if line == "avformatinfo: end\n":
               break
      
      elif (filext == ".wav" or filext == ".aiff" or filext == ".au"):
         self.parent.mixer_write("SNDP=%s\nACTN=sndfileinforequest\nend\n" % filename, True)
         while 1:
            line = self.parent.mixer_read()
            if line == "idjcmixer: sndfileinfo Not Valid\n" or line == "":
               return NOTVALID._replace(filename=filename)
            if line.startswith("idjcmixer: sndfileinfo length="):
               length = int(line[30:-1])
            if line.startswith("idjcmixer: sndfileinfo artist="):
               artist = line[30:-1]
            if line.startswith("idjcmixer: sndfileinfo title="):
               title = line[29:-1]
            if line == "idjcmixer: sndfileinfo end\n":
               break
         if length == None:
            return NOTVALID._replace(filename=filename)
     
      # This handles chained ogg files as generated by IDJC.
      elif filext == ".ogg" or filext == ".oga" or filext == ".spx":
         self.parent.mixer_write("OGGP=%s\nACTN=ogginforequest\nend\n" % filename, True)
         while 1:
            line = self.parent.mixer_read()
            if line == "OIR:NOT VALID\n" or line == "":
               return NOTVALID._replace(filename=filename)
            if line.startswith("OIR:ARTIST="):
               artist = line[11:].strip()
            if line.startswith("OIR:TITLE="):
               title = line[10:].strip()
            if line.startswith("OIR:LENGTH="):
               length = int(float(line[11:].strip()))
            if line.startswith("OIR:REPLAYGAIN_TRACK_GAIN="):
               try:
                  rg = float(line[26:].rstrip(" dB\n"))
               except:
                  rg = RGDEF
            if line == "OIR:end\n":
               break
      else:
         # Mutagen used for all remaining formats.
         try:
            audio = mutagen.File(filename)
         except:
            return NOTVALID._replace(filename=filename)
         else:
            length = int(audio.info.length)
            if isinstance(audio, MP4):
               try:
                  artist = audio["\xa9ART"][0]
               except:
                  pass
               try:
                  title = audio["\xa9nam"][0]
               except:
                  pass
            elif isinstance(audio, MP3):
               # The LAME tag is the last port of call for Replay Gain info
               # due to it frequently being based on the source audio.
               if rg == RGDEF:
                  try:
                     rg = audio.info.track_gain
                  except:
                     pass
                  else:
                      if rg is None:
                         rg = RGDEF
            else:
               x = list(audio.get("Artist", []))
               x += list(audio.get("Author", []))
               if x:
                  artist = "/".join((unicode(y) for y in x))
               
               try:
                  x = list(audio["Title"])
               except:
                  pass
               else:
                  title = "/".join((unicode(y) for y in x))
               
               try:
                  rg = float(unicode(audio["replaygain_track_gain"][-1]).rstrip(" dB"))
               except:
                  pass 
      
      if isinstance(artist, list):
         artist = u"/".join(artist)
         
      if isinstance(title, list):
         title = u"/".join(title)
      
      if isinstance(artist, str):
         try:
            artist = artist.decode("utf-8", "strict")
         except:
            artist = artist.decode("latin1", "replace")
            
      if isinstance(title, str):
         try:
            title = title.decode("utf-8", "strict")
         except:
            title = title.decode("latin1", "replace")
            
      assert(isinstance(artist, unicode))
      assert(isinstance(title, unicode))
      
      if length == 0:
         length = 1
      
      if artist and title:
         meta_name = artist + u" - " + title
         return PlayerRow(rich_safe(meta_name), filename, length, meta_name, encoding, title, artist, rg, cuesheet)
      else:
         return PlayerRow(rsmeta_name, filename, length, meta_name, encoding, title_retval, artist_retval, rg, cuesheet)

   # Update playlist entries for a given filename e.g. when tag has been edited
   def update_playlist(self, newdata):
      update = False
      for item in self.liststore:
         if item[1] == newdata[1]:
            if item[0].startswith("<b>"):
               item[0] = u"<b>" + newdata[0] + u"</b>"
               update = True
            else:
               item[0] = newdata[0]
            for i in range(2, len(item)):
               item[i] = newdata[i]
      if update:
         self.songname = item[3]        # update metadata on server
         self.title = item[5].encode("utf-8")
         self.artist = item[6].encode("utf-8")
         self.player_restart()
         self.parent.send_new_mixer_stats()
      
   # Shut down our media players when we exit.
   def cleanup(self):
      self.exiting = True               # I added this because, well the reason totally sucks TBH
      if self.player_is_playing:
         self.stop.clicked()
      self.save_session()

   def save_session(self):
      fh = open(self.session_filename, "w")
      extlist = self.external_pl.filechooser.get_filename()
      if extlist is not None:
         fh.write("extlist=" + extlist + "\n")
      extdir = self.external_pl.directorychooser.get_filename()
      if extdir is not None:
         fh.write("extdir=" + extdir + "\n")
      fh.write("digiprogress_type=" + str(int(self.digiprogress_type)) + "\n")
      fh.write("stream_button=" + str(int(self.stream.get_active())) + "\n")
      fh.write("listen_button=" + str(int(self.listen.get_active())) + "\n")
      fh.write("playlist_mode=" + str(self.pl_mode.get_active()) + "\n")
      fh.write("plsave_filetype=" + str(self.plsave_filetype) + "\n")
      fh.write("plsave_open=" + str(int(self.plsave_open)) + "\n")
      fh.write("fade_mode=" + str(self.pl_delay.get_active()) + "\n")
      if self.plsave_folder is not None:
         fh.write("plsave_folder=" + self.plsave_folder + "\n")
      
      for entry in self.liststore:
         fh.write("pe=")
         entry = list(entry)
         if entry[0].startswith("<b>"):   # clean off any accidental bold tags
            entry[0] = entry[0][3:-4]
         for item in entry:
            if isinstance(item, int):
               item = str(item)
               fh.write("i")
            elif isinstance(item, float):
               item = str(item)
               fh.write("f")
            elif isinstance(item, str):
               fh.write("s")
            elif isinstance(item, CueSheetListStore):
               fh.write("c")
               if item:
                  item = "(%s, )" % ", ".join(repr(x) for x in item)
               else:
                  item = "()"
            elif item is None:
               fh.write("n")
               item = "None"
            fh.write(str(len(item)) + ":" + item)
         fh.write("\n")
      model, iter = self.treeview.get_selection().get_selected()
      if iter is not None:
         fh.write("select=" + str(model.get_path(iter)[0]) + "\n")
      fh.close()

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
         try:
            if line.startswith("extlist="):
               self.external_pl.filechooser.set_filename(line[8:-1])
            if line.startswith("extdir="):
               self.external_pl.directorychooser.set_current_folder(line[7:-1])
            if line.startswith("digiprogress_type="):
               if int(line[18]) != self.digiprogress_type:
                  self.digiprogress_click()
            if line.startswith("stream_button="):
               self.stream.set_active(int(line[14]))
            if line.startswith("listen_button="):
               self.listen.set_active(int(line[14]))
            if line.startswith("playlist_mode="):
               self.pl_mode.set_active(int(line[14]))
            if line.startswith("plsave_filetype="):
               self.plsave_filetype=int(line[16])
            if line.startswith("plsave_open="):
               self.plsave_open=bool(int(line[12]))
            if line.startswith("plsave_folder="):
               self.plsave_folder=line[14:-1]
            if line.startswith("fade_mode="):
               self.pl_delay.set_active(int(line[10]))
            if line.startswith("pe="):
               playlist_entry = self.pl_unpack(line[3:])
               if not playlist_entry or self.playlist_todo:
                  self.playlist_todo.append(playlist_entry.filename)
               else:
                  self.liststore.append(playlist_entry)
            if line.startswith("select="):
               path = line[7:-1]
               try:
                  self.treeview.get_selection().select_path(path)
                  self.treeview.scroll_to_cell(path, None, False) 
               except:
                  pass
         except ValueError:
            pass
      if self.playlist_todo:
         print self.playername + " player: the stored playlist data is not compatible with this version\nfiles placed in a queue for rescanning"
         gobject.idle_add(self.cb_playlist_todo)
         
   @threadslock
   def cb_playlist_todo(self):
      if self.no_more_files:
         return False
      try:
         pathname = self.playlist_todo.popleft()
      except:
         return False
      line = self.get_media_metadata(pathname)
      if line:
         self.liststore.append(line)
      else:
         print "file missing or type unsupported %s" % pathname
      return True

   def pl_unpack(self, text):           # converts a string encoded list to a python list
      start = 0 
      item = 0  
      reply = []
      while text[start] != "\n":
         end = start
         while text[end] != ":":
            end = end + 1                               
         nextstart = int(text[start + 1 : end]) + end + 1
         
         value = text[end + 1 : nextstart]
         try:
            t = text[start]
            if t == "i":
               value = int(value)
            elif t == "f":
               value = float(value)
            elif t == "s":
               pass
            elif t == "c":
               csts = eval(value, {"__builtins__":None},{"CueSheetTrack":CueSheetTrack})
               value = CueSheetListStore()
               for cst in csts:
                  value.append(cst)
            elif t == "n":
               value = None
         except Exception, e:
            print "pl_unpack: playlist line not valid", e
            try:
               return NOTVALID._replace(filename=reply[1])
            except IndexError:
               return NOTVALID
            return nv
         reply.append(value)
         start = nextstart
      try:
         return PlayerRow._make(reply)
      except:
         return NOTVALID._replace(filename=reply[1])
             
   def handle_stop_button(self, widget):
      self.restart_cancel = True
      if self.is_playing == True:
         self.is_playing = False
         if self.timeout_source_id:
            gobject.source_remove(self.timeout_source_id)
         # This will make our play button code branch to its shutdown code.
         self.is_stopping = True
         # This will emit a signal which will trigger the play button handler code.
         self.play.set_active(False)
         # Must do pause as well if it is pressed.
         if self.pause.get_active() == True:
            self.pause.set_active(False)
         self.parent.send_new_mixer_stats()
         
   def handle_pause_button(self, widget, selected):
      if self.is_playing == True:
         if self.is_paused == False:
            # Player pause code goes here
            print "Player paused"
            self.is_paused = True
            self.parent.send_new_mixer_stats()
         else:
            # Player unpause code goes here
            print "Player unpaused"
            self.is_paused = False
            self.parent.send_new_mixer_stats()
      else:
         # Prevent the pause button going into its on state when not playing.
         if selected:
            # We must unselect it.
            widget.set_active(False)
         else:
            self.is_paused = False
   
   def handle_play_button(self, widget, selected):
      if selected == False:
         # Prevent the button from being toggled off by clicking on a selected play button.
         # This emits a toggled signal so we will handle this eventuality too.
         # Note that when flag is_stopping is set we don't want to reactivate this button.
         if self.is_stopping == False:
            widget.set_active(True)
         else:
            self.is_stopping = False
            if self.player_is_playing == True:
               self.player_shutdown()
      else:
         if self.is_playing == True:
            if self.new_title == True:
               self.new_title = False
               self.player_shutdown()
               self.parent.send_new_mixer_stats()
               self.player_is_playing = self.player_startup()
               if self.player_is_playing == False:
                  self.player_is_playing = True
               if self.is_paused:
                  self.pause.set_active(False)
            else:    
               print "Someone probably clicked Play when we were already playing"
         else:
            self.is_playing = True
            self.new_title = False
            if self.player_startup():
               self.player_is_playing = True
               print "Player has started"
            else:
               self.stop.clicked()
   
   def player_startup(self):
      # remember which player started last so we can decide on metadata
      print "player_startup %s" % self.playername
      self.parent.last_player = self.playername

      if self.player_is_playing == True:
         # Use the current song if one is playing.
         model = self.model_playing
         iter = self.iter_playing
      else:
         # Get our next playlist item.
         treeselection = self.treeview.get_selection()
         (model, iter) = treeselection.get_selected()
      if iter == None:
         print "Nothing selected in the playlist - trying the first entry."
         try:
            iter = model.get_iter(0)
         except:
            print "Playlist is empty"
            return False
         print "We start at the beginning"
         treeselection.select_iter(iter)
         
      self.treeview.scroll_to_cell(model.get_path(iter)[0], None, False)

      self.music_filename = model.get_value(iter, 1)
      if self.music_filename != "":
         # Songname is used for metadata for mp3         
         self.songname = unicode(model.get_value(iter, 3))
         # These two are used for ogg metadata
         self.title = unicode(model.get_value(iter, 5)).encode("utf-8", "replace")
         self.artist = unicode(model.get_value(iter, 6)).encode("utf-8", "replace")
         self.parent.send_new_mixer_stats()      
      # rt is the run time in seconds of our song
      rt = model.get_value(iter, 2)
      if rt < 0:
         rt = 0         # playlist controls have negative numbers
      # Calculate our seek time scaling from old slider settings.
      # Used for when seek is moved before play is pressed.
      if os.path.isfile(self.music_filename):
         try:
            self.start_time = int(self.progressadj.get_value() / self.max_seek * float(rt))
         except ZeroDivisionError:
            self.start_time = 0
      else:
         self.start_time = rt   # Seek to the end when file is missing.
      print "Seek time is %d seconds" % self.start_time
        
      if self.parent.prefs_window.rg_adjust.get_active():
         self.gain = model.get_value(iter, 7)
         if self.gain == RGDEF:
            self.gain = self.parent.prefs_window.rg_defaultgain.get_value()
         self.gain += self.parent.prefs_window.rg_boost.get_value()
         print "final gain value of %f dB" % self.gain      
      else:
         self.gain = 0.0
         print "not using replay gain"
           
      # Now we recalibrate the progress bar to the current song length
      self.digiprogress_f = True
      self.progressadj.set_all(float (self.start_time) , 0.0, rt, rt/1000.0, rt/100.0, 0.0)
      self.progressadj.emit("changed")
      # Set the stop figure used by the progress bar's timeout function
      self.progress_stop_figure = model.get_value(iter, 2)
      self.progress_current_figure = self.start_time
      
      self.player_is_playing = True
      
      # Bold highlight the file we are playing
      text = model.get_value(iter, 0)
      if not text.startswith("<b>"):
         text = "<b>" + text + "</b>"
         model.set_value(iter, 0, text)
      self.iter_playing = iter
      self.model_playing = model
      self.max_seek = rt
      self.silence_count = 0
      
      if self.music_filename != "":
         self.parent.mixer_write("PLRP=%s\nSEEK=%d\nSIZE=%d\nRGDB=%f\nACTN=playnoflush%s\nend\n" % (
                                 self.music_filename, self.start_time, self.max_seek, self.gain, self.playername), True)
         while 1:
            line = self.parent.mixer_read()
            if line.startswith("context_id="):
               self.player_cid = int(line[11:-1])
               break
            if line == "":
               self.player_cid = -1
               break
      else:
         print "skipping play for empty filename"
         self.player_cid = -1
      if self.player_cid == -1:
         print "player startup was unsuccessful for file", self.music_filename
         # we will treat this as successful and not return false so that end of track processing will take care of it
         self.timeout_source_id = gobject.timeout_add(0, self.cb_play_progress_timeout, self.player_cid)
      else:
         print "player context id is %d\n" % self.player_cid
         if self.player_cid & 1:
            self.timeout_source_id = gobject.timeout_add(200, self.cb_play_progress_timeout, self.player_cid)
         else:
            self.invoke_end_of_track_policy()
      return True

   def player_shutdown(self):
      print "player shutdown code was called"
      
      if self.iter_playing:
         # Unhighlight this track
         text = self.model_playing.get_value(self.iter_playing, 0)
         if text[:3] == "<b>":
            text = text[3:-4]
            self.model_playing.set_value(self.iter_playing, 0, text)
         self.file_iter_playing = 0
      
      self.player_is_playing = False
      if self.timeout_source_id:
         gobject.source_remove(self.timeout_source_id)
         
      self.progress_current_figure = 0
      self.playtime_elapsed.set_value(0)
      self.progressadj.set_value(0.0)
      self.progressadj.value_changed()
      
      if self.gapless == False:
         self.parent.mixer_write("ACTN=stop%s\nend\n" % self.playername, True)
      
      self.digiprogress_f = False
      self.other_player_initiated = False
      self.crossfader_initiated = False
   
   def set_fade_mode(self, mode):
      if self.parent.simplemixer:
         mode = 0
      self.parent.mixer_write("FADE=%d\nACTN=fademode_%s\nend\n" % (mode, self.playername), True)
   
   def player_restart(self):
      # remember which player started last so we can decide on metadata
      print "player_restart %s" % self.playername
      self.parent.last_player = self.playername

      gobject.source_remove(self.timeout_source_id)
      self.start_time = int (self.progressadj.get_value())
      self.silence_count = 0
      self.parent.mixer_write("PLRP=%s\nSEEK=%d\nACTN=play%s\nend\n" % (
                                self.music_filename, self.start_time, self.playername), True)
      while 1:
         line = self.parent.mixer_read()
         if line.startswith("context_id="):
            self.player_cid = int(line[11:-1])
            break
         if line == "":
            self.player_cid = -1
            break
      if self.player_cid == -1:
         print "player startup was unsuccessful for file", self.music_filename
         return False
      
      print "player context id is %d\n" % self.player_cid
      
      # Restart a callback to update the progressbar.
      self.timeout_source_id = gobject.timeout_add(100, self.cb_play_progress_timeout, self.player_cid)
      return True

   def next_real_track(self, i):
      if i == None:
         return None
      
      m = self.model_playing
      while 1:
         i = m.iter_next(i)
         if i is None:
            return None
         if m.get_value(i, 0)[0] != ">":
            return i

   def first_real_track(self):
      m = self.model_playing
      i = m.get_iter_first()
      
      while 1:
         if i == None:
            return None
         if m.get_value(i, 0)[0] != ">":
            return i
         i = m.get_iter_next(i)

   def invoke_end_of_track_policy(self):
      # This is where we implement the playlist modes.
      mode_text = self.pl_mode.get_active_text()
      if self.is_playing == False:
         print "Assertion failed in: invoke_end_of_track_policy"
         return
      
      if mode_text == ln.manual:
         # For Manual mode just stop the player at the end of the track.
         print "Stopping in accordance with manual mode"
         self.stop.clicked()
      elif mode_text == ln.play_all:
         if self.music_filename == "":
            self.handle_playlist_control()
         else:
            self.next.clicked()
            treeselection = self.treeview.get_selection()
            if self.is_playing == False:
               treeselection.select_path(0) # park on the first menu item
      elif mode_text == ln.loop_all or mode_text == ln.cue_up:
         iter = self.next_real_track(self.iter_playing)
         if iter is None:
            iter = self.first_real_track()
         self.stop.clicked()
         if iter is not None:
            treeselection = self.treeview.get_selection()
            treeselection.select_iter(iter)
            if mode_text == ln.loop_all:
               self.play.clicked()
         else:
            treeselection.select_path(0)
      elif mode_text == ln.random:
         # Not truly random. Effort is made to break the appearance of
         # having a set play order to a long term listener without
         # re-playing the same track too soon.
         
         self.stop.clicked()

         poolsize = len(self.liststore) // 10
         if poolsize > 50:
            poolsize = 50
         elif poolsize < 10:
            poolsize = 10
            if poolsize > len(self.liststore):
               poolsize = len(self.liststore)

         if self.parent.server_window.is_streaming or self.parent.server_window.is_recording:
            fp = self.parent.files_played
         else:
            fp = self.parent.files_played_offline
         timestamped_pathnames = []
         while not timestamped_pathnames:
            random_pathnames = [PlayerRow(*x).filename for x in random.sample(self.liststore, poolsize)]
            timestamped_pathnames = [(fp.get(pn, 0), pn) for pn in random_pathnames if pn]
            timestamped_pathnames.sort()
            least_recent_ts = timestamped_pathnames[0][0]
            timestamped_pathnames = [x for x in timestamped_pathnames if x[0] == least_recent_ts]
            least_recent = random.choice(timestamped_pathnames)[1]
         
         for path, entry in enumerate(self.liststore):
            entry_filename = PlayerRow(*entry).filename
            if least_recent == entry_filename:
               break
            
         treeselection = self.treeview.get_selection()        
         treeselection.select_path(path)
         self.play.clicked()
      elif mode_text == ln.external:
         path = self.model_playing.get_path(self.iter_playing)[0]
         self.stop.clicked()
         next_track = self.external_pl.get_next()
         if next_track is None:
            print "Cannot obtain anything from external directory/playlist - stopping"
         else:
            self.model_playing.insert_after(self.iter_playing, next_track)
            self.model_playing.remove(self.iter_playing)
            treeselection = self.treeview.get_selection()
            treeselection.select_path(path)
            self.play.clicked()
      elif mode_text == ln.alternate:
         iter = self.next_real_track(self.iter_playing)
         if iter is None:
            iter = self.first_real_track()
         self.stop.clicked()
         treeselection = self.treeview.get_selection()
         if iter is not None:
            treeselection.select_iter(iter)
         else:
            treeselection.select_path(0)
         if self.playername == "left":
            self.parent.passright.clicked()
            self.parent.player_right.play.clicked()
         else:
            self.parent.passleft.clicked()
            self.parent.player_left.play.clicked()
      else:
         print 'The mode "%s" is not currently supported - stopping' % mode_text
         self.stop.clicked()

   def handle_playlist_control(self):
      treeselection = self.treeview.get_selection()
      model = self.model_playing
      iter = self.iter_playing
      control = model.get_value(iter, 0)
      print "control is", control
      
      if control == "<b>>openaux</b>":
         self.parent.aux_select.set_active(True)
         self.stop.clicked()
         if model.iter_next(iter):
            treeselection.select_iter(model.iter_next(iter))
         else:
            treeselection.select_iter(model.get_iter_first())
      if control == "<b>>normalspeed</b>":
         self.pbspeedzerobutton.clicked()
         self.next.clicked()
         if self.is_playing == False:
            treeselection.select_path(0)
      if control == "<b>>stopplayer</b>":
         print "player", self.playername, "stopping due to playlist control"
         if (self.playername == "left" and self.parent.crossfade.get_value() < 50) or (self.playername == "right" and self.parent.crossfade.get_value() >= 50):
            self.parent.mic_opener.open_auto()
         self.stop.clicked()
         if model.iter_next(iter):
            treeselection.select_iter(model.iter_next(iter))
         else:
            treeselection.select_iter(model.get_iter_first())
      if control == "<b>>jumptotop</b>":
         self.stop.clicked()
         treeselection.select_path(0)
         self.play.clicked()
      if control == "<b>>announcement</b>":
         dia = AnnouncementDialog(self, model, iter, "active")
         dia.present()
         self.stop.clicked()
         if model.iter_next(iter):
            treeselection.select_iter(model.iter_next(iter))
         else:
            treeselection.select_iter(model.get_iter_first())
      if control == "<b>>crossfade</b>":
         print "player", self.playername, "stopping, crossfade complete"
         self.stop.clicked()
         if model.iter_next(iter):
            treeselection.select_iter(model.iter_next(iter))
         else:
            treeselection.select_path(0)
      if control == "<b>>stopstreaming</b>":
         self.next.clicked()
         self.parent.server_window.stop_streaming_all()
         if self.is_playing == False:
            treeselection.select_path(0)
      if control == "<b>>stoprecording</b>":
         self.next.clicked()
         self.parent.server_window.stop_recording_all()
         if self.is_playing == False:
            treeselection.select_path(0)
      if control == "<b>>transfer</b>":
         if self.playername == "left":
            otherplayer = self.parent.player_right
            self.parent.passright.clicked()
         else:
            otherplayer = self.parent.player_left
            self.parent.passleft.clicked()
         print "transferring to player", otherplayer.playername
         otherplayer.play.clicked()
         self.stop.clicked()
         if model.iter_next(iter):
            treeselection.select_iter(model.iter_next(iter))
         else:
            treeselection.select_path(0)
      if control.startswith("<b>>fade"):
         if control.endswith("e5</b>"):
            self.set_fade_mode(1)
         elif control.endswith("e10</b>"):
            self.set_fade_mode(2)
         self.next.clicked()
         self.set_fade_mode(0)
         if self.is_playing == False:
            treeselection.select_path(0)
      
   def get_pl_block_size(self, iter):
      size = 0
      speedfactor = self.pbspeedfactor
      while iter is not None:
         length = self.liststore.get_value(iter, 2)
         if length == -11:
            text = self.liststore.get_value(iter, 0)
            if text.startswith("<b>"):
               text = text[3:-4]
            if text in (">stopplayer", ">openaux", ">transfer", ">crossfade", ">announcement", ">jumptotop"):
               break
            if text == ">normalspeed":
               speedfactor = 1.0
         if length >= 0:
            size += int(length / speedfactor)
         iter = self.liststore.iter_next(iter)
      return size

   def update_time_stats(self):
      if self.pl_mode.get_active() != 0:                # optimisation -- this function uses a lot of cpu
         return
      if self.player_is_playing:
         tr = int((self.max_seek - self.progressadj.value) / self.pbspeedfactor)
         model = self.model_playing
         iter = model.iter_next(self.iter_playing)
         tr += self.get_pl_block_size(iter)
      else:
         tr = 0
      selection = self.treeview.get_selection()
      model, iter = selection.get_selected()
      if iter is None:
         if self.is_playing:
            bs = 0
         else:
            iter = model.get_iter_first()
            bs = self.get_pl_block_size(iter)
      else:
         try:
            if model.get_value(iter, 0)[0:3] == "<b>":
               bs = 0
            else:
               bs = self.get_pl_block_size(iter)
         except:
            print "Playlist data is fucked up"
            bs = 0
      bsm, bss = divmod(bs, 60)
      if self.is_playing:
         trm, trs = divmod(tr, 60)
         tm_end = time.localtime(int(time.time()) + tr)
         tm_end_h = tm_end[3]
         tm_end_m = tm_end[4]
         tm_end_s = tm_end[5]
         if bs == 0:
            self.statusbar_update("%s -%2d:%02d | %s %02d:%02d:%02d" % (ln.remaining, trm, trs, ln.finish, tm_end_h, tm_end_m, tm_end_s))
         else:
            self.statusbar_update("%s -%2d:%02d | %s %02d:%02d:%02d | %s %2d:%02d" % (ln.remaining, trm, trs, ln.finish, tm_end_h, tm_end_m, tm_end_s, ln.block_size, bsm, bss))
      else:
         if bs == 0:
            self.statusbar_update("")
         else:
            bft = time.localtime(time.time() + bs)
            bf_h = bft[3]
            bf_m = bft[4]
            bf_s = bft[5]
            self.statusbar_update("%s %2d:%02d | %s %02d:%02d:%02d" % (ln.block_size, bsm, bss, ln.finish, bf_h, bf_m, bf_s))
            
   def statusbar_update(self, newtext):         # optimisation -- only update the status bars when the text changes
      if newtext != self.oldstatusbartext:
         if self.pbspeedfactor < 0.999 or self.pbspeedfactor > 1.001:
            newtext = ("%03.1f%% | " % (self.pbspeedfactor * 100)) + newtext
         self.pl_statusbar.push(1, newtext)
         self.oldstatusbartext = newtext

   def check_mixer_signal(self):
      if self.progress_press == False and self.progressadj.upper - self.progress_current_figure < 5.0 and self.progressadj.upper > 10.0:
         if self.mixer_signal_f.value == 0 and int(self.mixer_cid) == self.player_cid + 1 and self.parent.prefs_window.silence_killer.get_active() and self.eos_inspect() == False:
            print "termination by check mixer signal"
            self.invoke_end_of_track_policy()

   @threadslock
   def cb_play_progress_timeout(self, cid):
      if cid % 2 == 0:
         # player started at end of track
         self.invoke_end_of_track_policy()
         return False

      if self.reselect_cursor_please:
         treeselection = self.treeview.get_selection()
         (model, iter) = treeselection.get_selected()
         if iter is not None:
            self.treeview.scroll_to_cell(model.get_path(iter)[0], None, False)
         else:
            self.reselect_please = True
         self.reselect_cursor_please = False
      if self.reselect_please:
         print "Set cursor on track playing"
         # This code reselects the playing track after a drag operation.
         treeselection = self.treeview.get_selection()
         try:
            treeselection.select_iter(self.iter_playing)
         except:
            print "Iter was cancelled probably due to song dragging"
         self.reselect_please = False
      if self.progress_press == False:
         if self.runout.value and self.is_paused == False and self.mixer_cid.value > self.player_cid:
            self.gapless = True
            print "termination due to end of track"
            self.invoke_end_of_track_policy()
            self.gapless = False
            return False
         if self.mixer_signal_f.value == False:
            self.silence_count += 1
            if self.silence_count >= 120 and self.playtime_elapsed.value > 15 and self.parent.prefs_window.bonus_killer.get_active():
               print "termination due to excessive silence"
               self.invoke_end_of_track_policy()
               return False
         else:
            self.silence_count = 0

         if self.progress_current_figure != self.playtime_elapsed.value:
            # Code runs once a second.
            
            # Check whether a track is hitting a stream or being recorded.
            if self.stream.get_active() and (self.parent.server_window.is_streaming or
               self.parent.server_window.is_recording) and (
               (self.playername == "left" and self.parent.crossadj.value < 90)
               or
               (self.playername == "right" and self.parent.crossadj.value > 10)):
                  # Log the time the file was last played.
               self.parent.files_played[self.music_filename] = time.time()
            else:
               self.parent.files_played_offline[self.music_filename] = time.time()

         self.progress_current_figure = self.playtime_elapsed.value
         self.progressadj.set_value(self.playtime_elapsed.value)
         if self.max_seek == 0:
            self.progressadj.emit("value_changed")
         self.update_time_stats()
      else:
         # we stop monitoring the play progress during the progress bar drag operation
         # by cancelling this timeout
         return False
      # Calclulate when to sound the DJ alarm (end of music notification)
      # Bugs: does not deep scan the playlist controls for >stopplayer so the alarm will not sound if
      # preceeded by another playlist control
      if self.progress_current_figure == self.progress_stop_figure -10 and self.progressadj.upper > 11 and self.parent.prefs_window.djalarm.get_active():
         if ((self.playername == "left" and self.parent.crossadj.get_value() < 50) or (self.playername == "right" and self.parent.crossadj.get_value() >= 50)) and (self.pl_mode.get_active() == 3 or self.pl_mode.get_active() == 4 or (self.pl_mode.get_active() == 0 and (self.model_playing.iter_next(self.iter_playing) is None or (self.pl_mode.get_active() == 0 and self.stop_inspect())))):
            if self.alarm_cid != cid:
               gobject.timeout_add(1000, self.deferred_alarm)
               self.alarm_cid = cid
      # Initial autocrossfade -- start the other player.
      if self.model_playing.iter_next(self.iter_playing) is not None and self.model_playing.get_value(self.model_playing.iter_next(self.iter_playing), 0) == ">crossfade" and self.pl_mode.get_active() == 0 and int(self.progress_current_figure) >= int(self.progress_stop_figure) -15:
         if self.other_player_initiated == False:
            if self.playername == "left":
               self.parent.player_right.play.clicked()
            else:
               self.parent.player_left.play.clicked()
            self.other_player_initiated = True
      # Now we do the crossfade
      if self.model_playing.iter_next(self.iter_playing) is not None and self.model_playing.get_value(self.model_playing.iter_next(self.iter_playing), 0) == ">crossfade" and self.pl_mode.get_active() == 0 and int(self.progress_current_figure) >= int(self.progress_stop_figure) -9:
         if self.crossfader_initiated == False:
            self.parent.passbutton.clicked()
            self.crossfader_initiated = True
            desired_direction = (self.playername == "left")
            if desired_direction != self.parent.crossdirection:
               self.parent.passbutton.clicked()
      
      rem = self.progress_stop_figure - self.progress_current_figure
      if (rem == 5 or rem == 10) and not self.crossfader_initiated and not self.parent.simplemixer:
         mode = self.pl_mode.get_active()
         next = self.model_playing.iter_next(self.iter_playing)
         if next is not None:
            nextval = self.model_playing.get_value(next, 0)
         else:
            nextval = ""
         if mode == 0 and nextval.startswith(">"):
            if rem == 5 and nextval == ">fade5":
               fade = 1
            elif rem == 10 and nextval == ">fade10":
               fade = 2
            else:
               fade = 0
            if (fade):
               self.set_fade_mode(fade)
               self.stop.clicked()
               treeselection = self.treeview.get_selection()
               next = self.model_playing.iter_next(next)
               if next is not None:
                  path = self.model_playing.get_path(next)
                  treeselection.select_path(path)
                  self.play.clicked()
               else:
                  treeselection.select_path(0)
               self.set_fade_mode(0)
         else:
            fade = self.pl_delay.get_active()
            if (fade == 1 and rem == 10) or (fade == 2 and rem == 5) or self.pl_mode.get_active() in (3, 4, 6) or (mode == 0 and self.islastinplaylist()):
               fade = 0
            if fade:
               self.set_fade_mode(fade)
               self.invoke_end_of_track_policy()
               self.set_fade_mode(0)
      
      return True

   @threadslock
   def deferred_alarm(self):
      self.parent.alarm = True
      self.parent.send_new_mixer_stats()
      return False

   def stop_inspect(self):
      stoppers = (">stopplayer", ">announcement")
      horizon = (">transfer", ">crossfade", ">openaux", ">jumptotop")
      i = self.iter_playing
      m = self.model_playing
      while 1:
         i = m.iter_next(i)
         if i is None:
            return True
         v = m.get_value(i, 0)
         if v and v[0] != ">":
            return False
         if v in stoppers:
            return True
         if v in horizon:
            return False

   def eos_inspect(self):
      # Returns true when playlist ended or stream disconnect is imminent.
      if self.pl_mode.get_active():
         return False
      if self.islastinplaylist():
         return True
      stoppers = (">stopstreaming", )
      horizon = (">transfer", ">crossfade", ">openaux")
      i = self.iter_playing
      m = self.model_playing
      while 1:
         i = m.iter_next(i)
         if i is None:
            return True
         v = m.get_value(i, 0)
         if v and v[0] != ">":
            return False
         if v in stoppers:
            return True
         if v in horizon:
            return False

   def islastinplaylist(self):
      iter = self.model_playing.iter_next(self.iter_playing)
      if iter is None:
         return True
      else:
         return False
          
   def arrow_up(self):
      treeselection = self.treeview.get_selection()
      (model, iter) = treeselection.get_selected()
      if iter == None:
         print "Nothing is selected"
      else:
         path = model.get_path(iter)
         if path[0]:
            other_iter = model.get_iter(path[0]-1)
            self.liststore.swap(iter, other_iter)
            self.treeview.scroll_to_cell(path[0]-1, None, False)
            
   def arrow_down(self):
      treeselection = self.treeview.get_selection()
      (model, iter) = treeselection.get_selected()
      if iter == None:
         print "Nothing is selected"
      else:
         path = model.get_path(iter)
         try:
            other_iter = model.get_iter(path[0]+1)
            self.liststore.swap(iter, other_iter)
            self.treeview.scroll_to_cell(path[0]+1, None, False)
         except ValueError:
            pass
          
   def advance(self):
      #self.set_fade_mode(self.pl_delay.get_active())
      if self.is_playing:
         self.parent.mic_opener.open_auto()
         path = self.model_playing.get_path(self.iter_playing)[0]+1
         self.stop.clicked()
         treeselection = self.treeview.get_selection()
         treeselection.select_path(path)
         self.treeview.scroll_to_cell(path, None, False)
      else:
         self.parent.mic_opener.close_all()
         self.play.clicked()
      #self.set_fade_mode(0)
          
   def callback(self, widget, data):
      if data == "pbspeedzero":
         self.pbspeedbar.set_value(0.0)

      if data == "Arrow Up":
         self.arrow_up()
      
      if data == "Arrow Dn":
         self.arrow_down()
               
      if data == "Stop":
         self.handle_stop_button(widget)
         
      if data == "Next":
         if self.is_playing:
            path = self.model_playing.get_path(self.iter_playing)[0]+1
            if self.is_paused:
               self.stop.clicked()
            try:
               self.model_playing.get_iter(path)
            except:
               self.stop.clicked()
               return
            treeselection = self.treeview.get_selection()           
            treeselection.select_path(path)
            self.new_title = True
            self.play.clicked()        
               
      if data == "Prev":
         if self.is_playing:
            treeselection = self.treeview.get_selection()
            path = self.model_playing.get_path(self.iter_playing)
            if self.is_paused:
               self.stop.clicked()
            treeselection.select_path(path[0]-1)
            self.new_title = True
            self.play.clicked()
               
      # This is for adding files to the playlist using the file requester.
      if data == "Add Files":
         if self.showing_file_requester == False:
            if self.playername == "left":
               filerqtext = ln.left_playlist_addition
            else:
               filerqtext = ln.right_playlist_addition
            self.filerq = gtk.FileChooserDialog(filerqtext, None, gtk.FILE_CHOOSER_ACTION_OPEN, (gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT, gtk.STOCK_OK, gtk.RESPONSE_ACCEPT))
            self.filerq.set_select_multiple(True)
            self.filerq.set_icon_from_file(pkgdatadir + "icon" + gfext)
            self.filerq.set_current_folder(str(self.file_requester_start_dir))
            self.filerq.add_filter(self.plfilefilter_all)
            self.filerq.add_filter(self.plfilefilter_playlists)
            self.filerq.add_filter(self.plfilefilter_media)
            self.filerq.set_filter(self.plsave_filtertype)
            frame = gtk.Frame(ln.formats)
            box = gtk.HBox()
            box.set_border_width(3)
            frame.add(box)
            entry = gtk.Entry()
            entry.unset_flags(gtk.CAN_FOCUS)
            entry.set_has_frame(False)
            text = "*" + ", *".join(supported.media)
            entry.set_text(text)
            entry.show()
            box.add(entry)
            box.show()
            self.filerq.set_extra_widget(frame)
            self.filerq.connect("response", self.file_response)
            self.filerq.connect("destroy", self.file_destroy)
            self.filerq.show()
            self.showing_file_requester = True
         else:
            self.filerq.present()

   def file_response(self, dialog, response_id):
      chosenfiles = self.filerq.get_filenames()
      if chosenfiles:
         self.file_requester_start_dir.set_text(os.path.split(chosenfiles[0])[0])
         self.plsave_filtertype = self.filerq.get_filter()
      self.filerq.destroy()
      if response_id != gtk.RESPONSE_ACCEPT:
         return
      gen = self.get_elements_from(chosenfiles)
      for each in gen:
         if self.no_more_files:
            self.no_more_files = False
            break
         self.liststore.append(each)
         while gtk.events_pending():
            gtk.main_iteration()
    
   def file_destroy(self, widget):
      self.showing_file_requester = False
     
   def plfile_new_savetype(self, widget):
      self.plsave_filetype = self.pltreeview.get_selection().get_selected_rows()[1][0][0]
      self.expander.set_label(ln.playlisttype_expander + "(" +  ln.playlisttype_extension[self.plsave_filetype][0] + ")")

   def plfile_response(self, dialog, response_id):
      self.plsave_filtertype = dialog.get_filter()
      self.plsave_open = self.expander.get_expanded()
      self.plsave_folder = dialog.get_current_folder()
      
      if response_id == gtk.RESPONSE_ACCEPT:
         chosenfile = self.plfilerq.get_filename()
      self.plfilerq.destroy()
      if response_id != gtk.RESPONSE_ACCEPT:
         return
      
      main, ext = os.path.splitext(chosenfile)
      ext = ext.lower()
      if self.plsave_filetype == 0:
         if not ext in supported.playlists:
            main += ext
            ext = ".m3u"      # default to m3u playlist format
      else:
         t = self.plsave_filetype - 1
         useext = supported.playlists[t]
         others = list(supported.playlists)
         del others[t]
         if ext != useext:
            if not ext in others:
               main += ext
            ext = useext
      chosenfile = main + ext

      validlist = [ x for x in self.liststore if x[0][0] != ">" and x[2] >= 0 ]

      print "Chosenfile is", chosenfile
      try:
         pl = open(chosenfile, "w")
      except IOError:
         print "Can't open file for writing.  Permissions problem?"
      else:
         if (ext == ".m3u"):
            try:
               pl.write("#EXTM3U\r\n")
               for each in validlist:
                  pl.write("#EXTINF:%d,%s\r\n" % (each[2], each[3].decode("UTF-8").encode("ISO8859-1", "replace")))
                  pl.write(each[1] + "\r\n")
            except IndexError:
               pl.close()
            except IOError:
               pl.close()
               print "That was odd\n"
         
         if ext == ".pls":
            pl.write("[playlist]\r\nNumberOfEntries=%d\r\n\r\n" % len(validlist))
            for i in range(1, len(validlist) + 1):
               each = validlist[i - 1]
               pl.write("File%d=%s\r\n" % (i, each[1]))
               pl.write("Title%d=%s\r\n" % (i, each[3]))
               pl.write("Length%d=%d\r\n\r\n" % (i, each[2]))
            pl.write("Version=2\r\n")
            
         if ext == ".xspf":
            doc = mdom.getDOMImplementation().createDocument('http://xspf.org/ns/0/', 'playlist', None)
            
            playlist = doc.documentElement
            playlist.setAttribute('version', '1')
            playlist.setAttribute('xmlns', 'http://xspf.org/ns/0/')
            playlist.setAttribute('xmlns:idjc', 'http://idjc.sourceforge.net/ns/')
            
            trackList = doc.createElement('trackList')
            playlist.appendChild(trackList)
            
            for each in self.liststore:
               row = PlayerRow(*each)
               
               track = doc.createElement('track')
               trackList.appendChild(track)

               if row.rsmeta.startswith(">"):
                  extension = doc.createElement('extension')
                  track.appendChild(extension)
                  extension.setAttribute('application', 'http://idjc.sourceforge.net/ns/')
                  
                  pld = doc.createElementNS('http://idjc.sourceforge.net/ns/', 'idjc:pld')
                  extension.appendChild(pld)
                  pld.setAttribute('rsmeta', row.rsmeta)
                  pld.setAttribute('length', str(row.length))
               else:
                  location = doc.createElement('location')
                  track.appendChild(location)
                  locationText = doc.createTextNode("file://" + urllib.quote(each[1]))
                  location.appendChild(locationText)
                  
                  if each[6]:
                     creator = doc.createElement('creator')
                     track.appendChild(creator)
                     creatorText = doc.createTextNode(each[6])
                     creator.appendChild(creatorText)
                     
                  if each[5]:
                     title = doc.createElement('title')
                     track.appendChild(title)
                     titleText = doc.createTextNode(each[5])
                     title.appendChild(titleText)
                     
                  duration = doc.createElement('duration')
                  track.appendChild(duration)
                  durationText = doc.createTextNode(str(each[2] * 1000))
                  duration.appendChild(durationText)
            
            xmltext = doc.toxml("UTF-8").replace("><", ">\n<").splitlines()
            spc = ""
            for i in range(len(xmltext)):
               if xmltext[i][1] == "/":
                  spc = spc[2:]
               if len(xmltext[i]) < 3 or xmltext[i].startswith("<?") or xmltext[i][-2] == "/" or xmltext[i].count("<") == 2:
                  xmltext[i] = spc + xmltext[i]
               else:
                  xmltext[i] = spc + xmltext[i]
                  if xmltext[i][len(spc) + 1] != "/":
                     spc = spc + "  "
            pl.write("\r\n".join(xmltext))
            pl.write("\r\n")
            doc.unlink()
            pl.close()

   def plfile_destroy(self, widget):
      self.showing_pl_save_requester = False
 
   def cb_toggle(self, widget, data):
      print "Toggle %s recieved for signal: %s" % (("OFF","ON")[widget.get_active()], data)
   
      if data == "Play":
         self.handle_play_button(widget, widget.get_active())
      if data == "Pause":
         self.handle_pause_button(widget, widget.get_active())
      if data == "Stream":
         self.parent.send_new_mixer_stats();
      if data == "Listen":
         self.parent.send_new_mixer_stats();
   
   def cb_progress(self, progress):
      if self.digiprogress_f:
         if self.max_seek > 0:
            if self.digiprogress_type == 0 or self.player_is_playing == False:
               count = int(progress.value)
            else:
               count = self.max_seek - int(progress.value)
         else:
            count = self.progress_current_figure
         hours = int(count / 3600)
         count = count - (hours * 3600)
         minutes = count / 60
         seconds = count - (minutes * 60)
         if self.digiprogress_type == 0:
            self.digiprogress.set_text("%d:%02d:%02d" % (hours, minutes, seconds))
         else:
            if self.max_seek != 0:
               self.digiprogress.set_text(" -%02d:%02d " % (minutes, seconds))
            else:
               self.digiprogress.set_text(" -00:00 ")
      if self.handle_motion_as_drop:
         self.handle_motion_as_drop = False
         if self.player_restart() == False:
            self.next.clicked()
         else:
            if self.pause.get_active():
               self.pause.set_active(False)

   def cb_pbspeed(self, widget, data=None):
      self.pbspeedfactor = pow(10.0, widget.get_value() * 0.05)
      self.parent.send_new_mixer_stats()

   def digiprogress_click(self):    
      self.digiprogress_type = not self.digiprogress_type
      if not self.digiprogress_f:
         if self.digiprogress_type == 0:
            self.digiprogress.set_text("0:00:00")
         else:
            self.digiprogress.set_text(" -00:00 ")
      else:
         self.cb_progress(self.progressadj)

   def cb_event(self, widget, event, callback_data):
      # Handle click to the play progress indicator
      if callback_data == "DigitalProgressPress":
         if event.button == 1:
            self.digiprogress_click()
         if event.button == 3:
            self.parent.app_menu.popup(None, None, None, event.button, event.time)
         return True                            # Prevent any focus therefore any cursor appearing
      if event.button == 1:
         # Handle click to the play progress bar
         if callback_data == "ProgressPress":
            self.progress_press = True
            if self.timeout_source_id:
               gobject.source_remove(self.timeout_source_id)
         elif callback_data == "ProgressRelease":
            self.progress_press = False
            if self.player_is_playing:
               self.progress_current_figure = self.progressadj.get_value()
               self.handle_motion_as_drop = True
               gobject.idle_add(self.player_progress_value_changed_emitter)
      return False
      
   # This is really a very convoluted workaround to achieve the effect of a connect_after
   # method on a button_release_event on the player progress bar to run player_restart
   # I tried using connect_after but no such luck hence this retarded idle function.
   @threadslock
   def player_progress_value_changed_emitter(self):
      self.progressadj.emit("value_changed")
      return False

   def cb_menu_select(self, widget, data):
      print "The %s was chosen from the %s menu" % (data, self.playername)   

   def delete_event(self, widget, event, data=None):
      return False

   def get_elements_from(self, pathnames):
      self.no_more_files = False
      l = len(pathnames)
      if l == 1:
         ext = os.path.splitext(pathnames[0])[1]
         if ext == ".m3u":
            return self.get_elements_from_m3u(pathnames[0])
         elif ext == ".pls":
            return self.get_elements_from_pls(pathnames[0])
         elif ext == ".xspf":
            return self.get_elements_from_xspf(pathnames[0])
         elif os.path.isdir(pathnames[0]):
            return self.get_elements_from_directory(pathnames[0], set(), 2)
      return self.get_elements_from_chosen(pathnames)

   def get_elements_from_chosen(self, chosenfiles):
      for each in chosenfiles:
         meta = self.get_media_metadata(each)
         if meta:
            yield meta
   
   def get_elements_from_directory_orig(self, chosendir):
      files = os.listdir(chosendir)
      files.sort()
      for each in files:
         path = "/".join((chosendir, each))
         meta = self.get_media_metadata(path)
         if meta:
            yield meta

   def get_elements_from_directory(self, chosendir, visited, depth):
      depth -= 1
      chosendir = os.path.realpath(chosendir)
      if chosendir in visited or not os.path.isdir(chosendir):
         return
      else:
         visited.add(chosendir)

      directories = set()

      print chosendir
      files = os.listdir(chosendir)
      files.sort()
      for filename in files:
         pathname = "/".join((chosendir, filename))
         if os.path.isdir(pathname):
            #if os.path.realpath(pathname) == pathname:
            if not filename.startswith("."):
               directories.add(filename)
         else:
            meta = self.get_media_metadata(pathname)
            if meta:
               yield meta
               
      if depth:
         for subdir in directories:
            print "examining", "/".join((chosendir, subdir))
            gen = self.get_elements_from_directory("/".join((chosendir, subdir)), visited, depth)
            for meta in gen:
               yield meta
 
   def get_elements_from_m3u(self, filename):
      try:
         file = open(filename, "r")
         data = file.read().strip()
         file.close()
      except IOError:
         print "Problem reading file", filename
         return
      basepath = os.path.split(filename)[0] + "/"
      data = data.splitlines()
      for line, each in enumerate(data):
         if each[0] == "#":
            continue
         if each[0] != "/":
            each = basepath + each
         # handle special case of a single element referring to a directory
         if line == 0 and len(data) == 1 and os.path.isdir(each):
            gen = self.get_elements_from_directory(each)
            for meta in gen:
               yield meta
            return
         meta = self.get_media_metadata(each)
         if meta:
            yield meta
         line += 1
         
   def get_elements_from_pls(self, filename):
      import ConfigParser
      cfg = ConfigParser.RawConfigParser()
      try:
         cfg.readfp(open(filename))
      except IOError:
         print "Problem reading file"
         return
      if cfg.sections() != ['playlist']:
         print "wrong number of sections in pls file"
         return
      if cfg.getint('playlist', 'Version') != 2:
         print "can handle version 2 pls playlists only"
         return
      try:
         n = cfg.getint('playlist', 'NumberOfEntries')
      except ConfigParser.NoOptionError:
         print "NumberOfEntries is missing from playlist"
         return
      except ValueError:
         print "NumberOfEntries is not an int"
      for i in range(1, n + 1):
         try:
            path = cfg.get('playlist', 'File%d' % i)
         except:
            print "Problem getting file path from playlist"
         else:
            if os.path.isfile(path):
               meta = self.get_media_metadata(path)
               if meta:
                  yield meta
         
   def get_elements_from_xspf(self, filename):
      class BadXspf(ValueError):
         pass
      class GotLocation(Exception):
         pass
      
      try:
         baseurl = []
         
         try:
            dom = mdom.parse(filename)
         except:
            raise BadXspf
 
         if dom.hasChildNodes() and len(dom.childNodes) == 1 and dom.documentElement.nodeName == u'playlist':
            playlist = dom.documentElement
         else:
            raise BadXspf

         if playlist.namespaceURI != u"http://xspf.org/ns/0/":
            raise BadXspf
            
         try:
            v = int(playlist.getAttribute('version'))
         except:
            raise BadXspf
         if v < 0 or v > 1:
            print "only xspf playlist versions 0 and 1 supported"
            raise BadXspf
         del v
         
         # obtain base URLs for relative URLs encountered in trackList
         # only one location tag is allowed
         locations = [ x for x in playlist.childNodes if x.nodeName == u"location" ]
         if len(locations) == 1:
            url = locations[0].childNodes[0].wholeText
            if url.startswith(u"file:///"):
               baseurl.append(url)
         elif locations:
            raise BadXspf
         # lesser priority given to the path of the playlist in the filesystem
         baseurl.append(u"file://" + urllib.quote(os.path.split(os.path.realpath(filename))[0].decode("ASCII") + u"/"))
         # as before but without realpath
         baseurl.append(u"file://" + urllib.quote(os.path.split(filename)[0].decode("ASCII") + u"/"))
         if baseurl[-1] == baseurl[-2]:
            del baseurl[-1]
         
         trackLists = playlist.getElementsByTagName('trackList')
         if len(trackLists) != 1:
            raise BadXspf
         trackList = trackLists[0]
         if trackList.parentNode != playlist:
            raise BadXspf
            
         tracks = trackList.getElementsByTagName('track')
         for track in tracks:
            if track.parentNode != trackList:
               raise BadXspf
            locations = track.getElementsByTagName('location')
            try:
               for location in locations:
                  for base in baseurl:
                     url = urllib.unquote(urllib.basejoin(base, location.firstChild.wholeText).encode("ASCII"))
                     meta = self.get_media_metadata(url)
                     if meta:
                        yield meta
                        raise GotLocation
               # Support namespaced pld tag for literal playlist data.
               # This is only used for non playable data such as playlist controls.
               extensions = track.getElementsByTagName('extension')
               for extension in extensions:
                  if extension.getAttribute("application") == "http://idjc.sourceforge.net/ns/":
                     customtags = extension.getElementsByTagNameNS("http://idjc.sourceforge.net/ns/", "pld")
                     for tag in customtags:
                        try:
                           literal_entry = NOTVALID._replace(**dict((k, type(getattr(NOTVALID, k))(tag.attributes.get(k).nodeValue)) for k in tag.attributes.keys()))
                        except Exception, e:
                           print e
                           pass
                        else:
                           yield literal_entry
                           raise GotLocation
            except GotLocation:
               pass
         return
      except BadXspf:
         print "could not parse playlist", filename
         return
    
   def drag_data_delete(self, treeview, context):
      if context.action == gtk.gdk.ACTION_MOVE:
         treeselection = treeview.get_selection()
         model, iter = treeselection.get_selected()
         data = model.get_value(iter, 0)
         if data[:3] == "<b>":
            self.iter_playing = 0
            self.stop.clicked()

   def drag_data_get_data(self, treeview, context, selection, target_id, etime):
      treeselection = treeview.get_selection()
      model, iter = treeselection.get_selected()
      if model.get_value(iter, 1) != "":
         data = "file://" + model.get_value(iter, 1)
      else:
         data = "idjcplayercontrol://" + model.get_value(iter, 0) + "+" + str(model.get_value(iter, 2)) + "+" + model.get_value(iter, 3) + "+" + model.get_value(iter, 4)
      print "data for drag_get =", data
      selection.set(selection.target, 8, data)
      self.reselect_please = True
      return True

   def drag_data_received_data(self, treeview, context, x, y, dragged, info, etime):
      if info != 0:
         text = str(dragged.data)
         if text.count("\x00"): # where did these come from??
            try:
               # Strip out any Null characters which may be due to the dragged
               # text being composed of unicode and convert back to the 
               # filesystem encoding.
               # If fenc is wrong dnd will likely fail on filenames with non ASCII.
               # The names must ultimately match what is written on your hard drive.
               # This can be a problem when you have multiple encodings registered.
               text = unicode(text)
               fe = self.parent.fenc.split(",")
               for each in fe:
                  if each == "@locale" or each == "locale":
                     each = self.parent.de
                  try:
                     result = text.encode(each, "strict")
                  except:
                     continue           # failed to encode text with the encoding in each
                  else:
                     text = result      # encoding succeeded even if it is wrong
                     break
               else:
                  print "Unable to encode drag and drop filenames with the supplied list:", self.parent.fenc
            except:
               pass             # Not unicode aparrently or we wouldn't be here.
            # Finally a blanket removal of any NULLs because they really need to go
            text = text.replace("\x00", "") 
         if text[:20] == "idjcplayercontrol://":
            ct = text[20:].split("+")
            newrow = [ ct[0], "", int(ct[1]), ct[2], ct[3], "", "" ]
            drop_info = treeview.get_dest_row_at_pos(x, y)
            model = treeview.get_model()
            if drop_info == None:
               model.append(newrow)
            else:
               path, position = drop_info
               dest_iter = model.get_iter(path)
               if(position == gtk.TREE_VIEW_DROP_BEFORE or position == gtk.TREE_VIEW_DROP_INTO_OR_BEFORE):
                  model.insert_before(dest_iter, newrow)
               else:
                  model.insert_after(dest_iter, newrow)
            if context.action == gtk.gdk.ACTION_MOVE:
               context.finish(True, True, etime)
         else:
            if context.action == gtk.gdk.ACTION_MOVE:
               context.finish(True, True, etime)
            gobject.idle_add(self.drag_data_received_data_idle, treeview, x, y, text)
      else:
         treeselection = treeview.get_selection()
         model, iter = treeselection.get_selected()
         drop_info = treeview.get_dest_row_at_pos(x, y)
         if drop_info == None:
            self.liststore.move_before(iter, None)
         else:
            path, position = drop_info
            dest_iter = model.get_iter(path)
            if(position == gtk.TREE_VIEW_DROP_BEFORE or position == gtk.TREE_VIEW_DROP_INTO_OR_BEFORE):
               self.liststore.move_before(iter, dest_iter)
            else:
               self.liststore.move_after(iter, dest_iter)
         if context.action == gtk.gdk.ACTION_MOVE:
            context.finish(False, False, etime)
      return True
   
   def drag_data_received_data_idle(self, treeview, x, y, dragged):
      gtk.gdk.threads_enter()
      model = treeview.get_model()
      gtk.gdk.threads_leave()
        
      pathnames = [ urllib.unquote(t[7:]) for t in dragged.strip().splitlines() if t.startswith("file://") ]
      gen = self.get_elements_from(pathnames)
      
      first = True
      for media_data in gen:
         if self.no_more_files:
            self.no_more_files = False
            break
         if first:
            gtk.gdk.threads_enter()
            drop_info = treeview.get_dest_row_at_pos(x, y)
            gtk.gdk.threads_leave()
            if drop_info:
               path, position = drop_info
               gtk.gdk.threads_enter()
               iter = model.get_iter(path)
               gtk.gdk.threads_leave()
               if(position == gtk.TREE_VIEW_DROP_BEFORE or position == gtk.TREE_VIEW_DROP_INTO_OR_BEFORE):
                  gtk.gdk.threads_enter()
                  iter = model.insert_before(iter, media_data)
                  gtk.gdk.threads_leave()
               else:
                  gtk.gdk.threads_enter()
                  iter = model.insert_after(iter, media_data)
                  gtk.gdk.threads_leave()
            else:
               gtk.gdk.threads_enter()
               iter = model.append(media_data)
               gtk.gdk.threads_leave()
            first = False
         else:
            gtk.gdk.threads_enter()
            iter = model.insert_after(iter, media_data)
            gtk.gdk.threads_leave()
         gtk.gdk.threads_enter()
         while gtk.events_pending():
            gtk.gdk.threads_leave()
            gtk.gdk.threads_enter()
            gtk.main_iteration()
            gtk.gdk.threads_leave()
            gtk.gdk.threads_enter()
         gtk.gdk.threads_leave()
      self.reselect_please = True
      return False
   
   sourcetargets = [
      ('MY_TREE_MODEL_ROW', gtk.TARGET_SAME_WIDGET, 0),
      ('text/plain', 0, 1),
      ('TEXT', 0, 2),
      ('STRING', 0, 3),
      ]
      
   droptargets = [
      ('MY_TREE_MODEL_ROW', gtk.TARGET_SAME_WIDGET, 0),
      ('text/plain', 0, 1),
      ('TEXT', 0, 2),
      ('STRING', 0, 3),
      ('text/uri-list', 0, 4)                   # Need drop target for prokyon3
      ] 
      
   def cb_doubleclick(self, treeview, path, tvcolumn, user_data):
      # Our play button handler will manage to get the song title.
      # All we need to do is set a flag and issue a play button started signal.
      if self.is_playing:
         # The new_title flag allows a new song to be played when the player is going.
         self.new_title = True
         self.play.clicked()
      else:
         self.play.clicked()
                           
   def cb_selection_changed(self, treeselection):
      (model, iter) = treeselection.get_selected()
      if iter:
         row = PlayerRow._make(self.liststore[model.get_path(iter)[0]])
         if row.cuesheet:
            self.cuesheet_playlist.treeview.set_model(row.cuesheet)
            self.cuesheet_playlist.show()
         else:
            self.cuesheet_playlist.hide()
            self.cuesheet_playlist.treeview.set_model(None)
         self.update_time_stats()
         
   def cb_playlist_changed(self, treemodel, path, iter = None):
      self.playlist_changed = True      # used by the request system
         
   def menu_activate(self, widget, event):
      if event.type == gtk.gdk.BUTTON_PRESS and event.button == 3:
         self.menu_model = self.treeview.get_model()
         row_info = self.treeview.get_dest_row_at_pos(int(event.x + 0.5), int(event.y + 0.5))
         if row_info:
            sens = True
            path, position = row_info
            selection = self.treeview.get_selection()
            selection.select_path(path)
            self.menu_iter = self.menu_model.get_iter(path)     # store the context of the menu action
            pathname = self.menu_model.get_value(self.menu_iter, 1)
            self.item_tag.set_sensitive(MutagenGUI.is_supported(pathname) != False)
         else:
            pathname = ""
            self.menu_iter = None
            sens = False
         self.item_duplicate.set_sensitive(sens)
         self.remove_this.set_sensitive(sens)
         self.remove_from_here.set_sensitive(sens)
         self.remove_to_here.set_sensitive(sens)
         self.item_tojingles.set_sensitive(pathname != "")
         model = self.treeview.get_model()
         if model.get_iter_first() == None:
            sens2 = False
         else:
            sens2 = True
         self.pl_menu_item.set_sensitive(sens2)
         self.playlist_save.set_sensitive(sens2)
         self.playlist_copy.set_sensitive(sens2)
         self.playlist_transfer.set_sensitive(sens2)
         self.playlist_empty.set_sensitive(sens2)
         if self.pl_mode.get_active() != 0:
            self.pl_menu_control.set_sensitive(False)
         else:
            self.pl_menu_control.set_sensitive(True)
         
         if self.playername == "left":  # determine if anything is selected in the other playlist
            tv = self.parent.player_right.treeview.get_selection()
         else:
            tv = self.parent.player_left.treeview.get_selection()
         model, iter = tv.get_selected()
         if iter:
            sens3 = True
         else:
            sens3 = False
         self.copy_append_cursor.set_sensitive(sens3)
         self.copy_prepend_cursor.set_sensitive(sens3)
         self.transfer_append_cursor.set_sensitive(sens3)
         self.transfer_prepend_cursor.set_sensitive(sens3)   
            
         widget.popup(None, None, None, event.button, event.time)
         return True
      return False
      
   def cb_plexpander(self, widget, param_spec):
      if widget.get_expanded():
         self.plframe.show()
      else:
         self.plframe.hide()
      
   def menuitem_response(self, widget, text):
      print "The %s menu option was chosen" % text
      model = self.menu_model
      iter = self.menu_iter
      
      if text == "Announcement Control" and iter is not None and model.get_value(iter, 0) == ">announcement":
         # modify existing announcement dialog
         dia = AnnouncementDialog(self, model, iter, "delete_modify")
         dia.show()
         return
      
      dict = {
             "Stop Control"              : ">stopplayer",
             "Transfer Control"          : ">transfer",
             "Crossfade Control"         : ">crossfade",
             "Stream Disconnect Control" : ">stopstreaming",
             "Stop Recording Control"    : ">stoprecording",
             "Normal Speed Control"      : ">normalspeed",
             "Switch To Aux Control"     : ">openaux",
             "Announcement Control"      : ">announcement",
             "Fade 10"                   : ">fade10",
             "Fade 5"                    : ">fade5",
             "Fade none"                 : ">fadenone",
             "Jump To Top Control"       : ">jumptotop",
      }
      if dict.has_key(text):
         if iter is not None:
            iter = model.insert_after(iter)
         else:
            iter = model.append()
         model.set_value(iter, 0, dict[text])
         model.set_value(iter, 1, "")
         model.set_value(iter, 2, -11)
         model.set_value(iter, 3, "")
         model.set_value(iter, 4, "")
         model.set_value(iter, 5, "")
         model.set_value(iter, 6, "")
         self.treeview.get_selection().select_iter(iter)
         
         if text == "Announcement Control":
            # brand new announcement dialog
            dia = AnnouncementDialog(self, model, iter, "initial")
            dia.show()
         return
      
      if text == "MetaTag":
         try:
            pathname = model.get_value(iter, 1)
         except TypeError:
            pass
         else:
            MutagenGUI(pathname, model.get_value(iter, 4) , self.parent)
      
      if text == "Add File":
         self.add.clicked()
      
      if text == "Playlist Save":
         if self.showing_pl_save_requester == False:
            if self.playername == "left":
               filerqtext = ln.left_playlist_save
            else:
               filerqtext = ln.right_playlist_save
            vbox = gtk.VBox()
            self.expander = gtk.Expander()
            self.expander.connect("notify::expanded", self.cb_plexpander)
            vbox.add(self.expander)
            self.expander.show()
            
            self.plframe = gtk.Frame()
            self.plliststore = gtk.ListStore(str, str)
            for row in ln.playlisttype_extension:
               self.plliststore.append(row)
            self.pltreeview = gtk.TreeView(self.plliststore)
            self.plframe.add(self.pltreeview)
            
            self.pltreeview.show()
            self.pltreeview.set_rules_hint(True)
            cellrenderer1 = gtk.CellRendererText()
            self.pltreeviewcol1 = gtk.TreeViewColumn(ln.playlisttype_header1, cellrenderer1, text = 0)
            self.pltreeviewcol1.set_expand(True)
            cellrenderer2 = gtk.CellRendererText()
            self.pltreeviewcol2 = gtk.TreeViewColumn(ln.playlisttype_header2, cellrenderer2, text = 1)
            self.pltreeview.append_column(self.pltreeviewcol1)
            self.pltreeview.append_column(self.pltreeviewcol2)
            self.pltreeview.connect("cursor-changed", self.plfile_new_savetype)
            self.pltreeview.set_cursor(self.plsave_filetype)
            
            if (self.plsave_open):
               self.expander.set_expanded(True)
            vbox.add(self.plframe)
               
            self.plfilerq = gtk.FileChooserDialog(filerqtext, None, gtk.FILE_CHOOSER_ACTION_SAVE, (gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT, gtk.STOCK_OK, gtk.RESPONSE_ACCEPT))
            self.plfilerq.set_icon_from_file(pkgdatadir + "icon" + gfext)
            self.plfilerq.set_current_folder(self.home)
            self.plfilerq.add_filter(self.plfilefilter_all)
            self.plfilerq.add_filter(self.plfilefilter_playlists)
            self.plfilerq.set_filter(self.plsave_filtertype)
            self.plfilerq.set_extra_widget(vbox)
            if self.plsave_folder is not None:
               self.plfilerq.set_current_folder(self.plsave_folder)
            if self.plsave_filetype == 0:
               self.plfilerq.set_current_name("idjcplaylist.m3u")
            else:
               self.plfilerq.set_current_name("idjcplaylist")
            self.plfilerq.connect("response", self.plfile_response)
            self.plfilerq.connect("destroy", self.plfile_destroy)
            self.plfilerq.show()
            self.showing_pl_save_requester = True
         else:
            self.plfilerq.present()
       
      if text == "Remove All":
         if self.is_playing:
            self.stop.clicked()
         self.no_more_files = True
         self.liststore.clear()
      
      if text == "Remove This" and iter != None:
         name = model.get_value(iter, 0)
         if name[:3] == "<b>":
            self.stop.clicked()
         self.liststore.remove(iter)
         
      if text == "Remove From Here" and iter != None:    
         path = model.get_path(iter)
         try:
            while 1:
               iter = model.get_iter(path)
               if model.get_value(iter, 0)[:3] == "<b>":
                  self.stop.clicked()
               self.no_more_files = True
               self.liststore.remove(iter)
         except:
            print "Nothing more to delete"
         
      if text == "Remove To Here" and iter != None:
         self.no_more_files = True
         path = model.get_path(iter)[0] -1
         while path >= 0:
            iter = model.get_iter(path)
            if model.get_value(iter, 0)[:3] == "<b>":
               self.stop.clicked()
            self.liststore.remove(iter)
            path = path -1

      if text == "Duplicate" and iter != None:
         row = list(model[model.get_path(iter)])
         if row[0][:3] == "<b>":                # strip off any bold tags
            row[0] = row[0][3:-4]
         model.insert_after(iter, row)
      
      if text == "Playlist Exchange":
         self.no_more_files = True
         if self.playername == "left":
            opposite = self.parent.player_right
         else:
            opposite = self.parent.player_left
         self.stop.clicked()
         opposite.stop.clicked()
         i = 0
         try:
            while 1:
               self.templist.append(self.liststore[i])
               i = i + 1
         except IndexError:
            pass
         self.liststore.clear()
         i = 0
         try:
            while 1:
               self.liststore.append(opposite.liststore[i])
               i = i + 1
         except IndexError:
            pass
         opposite.liststore.clear()
         i = 0
         try:
            while 1:
               opposite.liststore.append(self.templist[i])
               i = i + 1
         except IndexError:
            pass
         self.templist.clear()
         
      if text == "Copy Append":
         self.copy_playlist("end")
         
      if text == "Transfer Append":
         self.copy_playlist("end")
         self.stop.clicked()
         self.liststore.clear()
                 
      if text == "Copy Prepend":
         self.copy_playlist("start")
         
      if text == "Transfer Prepend":
         self.copy_playlist("start")
         self.stop.clicked()
         self.liststore.clear()
         
      if text == "Copy Append Cursor":
         self.copy_playlist("after")
         
      if text == "Transfer Append Cursor":
         self.copy_playlist("after")
         self.stop.clicked()
         self.liststore.clear()
         
      if text == "Copy Prepend Cursor":
         self.copy_playlist("before")
         
      if text == "Transfer Prepend Cursor":
         self.copy_playlist("before")
         self.stop.clicked()
         self.liststore.clear()
        
      if text == "ToJingles":
         source = model.get_value(iter, 1)
         dest = self.parent.idjc + "jingles/" + os.path.split(source)[1]
         try:
            source = open(source, "r")
            dest = open(dest, "w")
            while True:
               data = source.read(4096)
               dest.write(data)
               if len(data) < 4096:
                  break;
         except IOError:
            print "IOError occurred"
         source.close
         dest.close
         self.parent.jingles.refresh.clicked()
               
      if self.player_is_playing:        # put the cursor on the file playing after a brief pause.
         self.reselect_please = True

   def stripbold(self, playlist_item):
      copy = list(playlist_item)
      if copy[0][:3] == "<b>":
         copy[0] = copy[0][3:-4]
      return copy
                 
   def copy_playlist(self, dest):
      if self.playername == "left":
         other = self.parent.player_right
      else:
         other = self.parent.player_left
      i = 0
      try:
         if dest == "start":
            while 1:
               other.liststore.insert(i, self.stripbold(self.liststore[i]))
               i = i + 1
         if dest == "end":
            while 1:
               other.liststore.append(self.stripbold(self.liststore[i]))
               i = i + 1
         
         (model, iter) = other.treeview.get_selection().get_selected()         
         
         if dest == "after":
            while 1:
               iter = other.liststore.insert_after(iter, self.stripbold(self.liststore[i]))
               i = i + 1
         if dest == "before":
            while 1:
               other.liststore.insert_before(iter, self.stripbold(self.liststore[i]))
               i = i + 1
      except IndexError:
         pass
            
   def cb_keypress(self, widget, event):
      # Handle shifted arrow keys for rearranging stuff in the playlist.
      if event.state & gtk.gdk.SHIFT_MASK:
         if event.keyval == 65362:
            self.arrow_up()
            return True
         if event.keyval == 65364:
            self.arrow_down()
            return True
         if event.keyval == 65361 and self.playername == "right":
            treeselection = widget.get_selection()
            s_model, s_iter = treeselection.get_selected()
            if s_iter is not None:
               name = s_model.get_value(s_iter, 0)
               if name[:3] == "<b>":
                  self.stop.clicked()
               otherselection = self.parent.player_left.treeview.get_selection()
               d_model, d_iter = otherselection.get_selected()
               row = list(s_model[s_model.get_path(s_iter)])
               path = s_model.get_path(s_iter)
               s_model.remove(s_iter)
               treeselection.select_path(path)
               if d_iter is None:
                  d_iter = d_model.append(row)
               else:
                  d_iter = d_model.insert_after(d_iter, row)
               otherselection.select_iter(d_iter)
               self.parent.player_left.treeview.set_cursor(d_model.get_path(d_iter))
               self.parent.player_left.treeview.scroll_to_cell(d_model.get_path(d_iter), None, False)
            return True
         if event.keyval == 65363 and self.playername == "left":
            treeselection = widget.get_selection()
            s_model, s_iter = treeselection.get_selected()
            if s_iter is not None:
               name = s_model.get_value(s_iter, 0)
               if name[:3] == "<b>":
                  self.stop.clicked()
               otherselection = self.parent.player_right.treeview.get_selection()
               d_model, d_iter = otherselection.get_selected()
               row = list(s_model[s_model.get_path(s_iter)])
               path = s_model.get_path(s_iter)
               s_model.remove(s_iter)
               treeselection.select_path(path)
               if d_iter is None:
                  d_iter = d_model.append(row)
               else:
                  d_iter = d_model.insert_after(d_iter, row)
               otherselection.select_iter(d_iter)
               self.parent.player_right.treeview.set_cursor(d_model.get_path(d_iter))
               self.parent.player_right.treeview.scroll_to_cell(d_model.get_path(d_iter), None, False)
            return True
      if event.keyval == 65361 and self.playername == "right":
         treeselection = self.parent.player_left.treeview.get_selection()
         model, iter = treeselection.get_selected()
         if iter is not None:
            self.parent.player_left.treeview.set_cursor(model.get_path(iter))
         else:
            treeselection.select_path(0)
         self.parent.player_left.treeview.grab_focus()
         return True
      if event.keyval == 65363 and self.playername == "left":
         treeselection = self.parent.player_right.treeview.get_selection()
         model, iter = treeselection.get_selected()
         if iter is not None:
            self.parent.player_right.treeview.set_cursor(model.get_path(iter))
         else:
            treeselection.select_path(0)
         self.parent.player_right.treeview.grab_focus()
         return True
      if event.keyval == 65535 or event.keyval == 65439:         # The Main and NK Delete keys
         treeselection = widget.get_selection()         # Delete to cause playlist entry removal
         model, iter = treeselection.get_selected()
         if iter is not None:
            path = model.get_path(iter)
            if path[0] > 0:
               prev = model.get_iter(path[0]-1)
            else:
               prev = None
            try:
               next = model.get_iter(path[0]+1)
            except:
               next = None
            name = model.get_value(iter, 0)
            if name[:3] == "<b>":
               self.stop.clicked()
            self.liststore.remove(iter)
            if next is not None:
               treeselection.select_iter(next)
               widget.set_cursor(model.get_path(next))
               self.treeview.scroll_to_cell(model.get_path(next), None, False)
            elif prev is not None:
               treeselection.select_iter(prev)
               widget.set_cursor(model.get_path(prev))
               self.treeview.scroll_to_cell(model.get_path(prev), None, False)
         else:
            print "Playlist is empty!"
         return True
      # Allow certain key presses to work but not allow a text entry box to appear.
      if event.string =="\r":
         self.stop.clicked()
         self.play.clicked()
         return True
      if event.string == "":
         return False
      return True
            
   def rgrowconfig(self, tv_column, cell_renderer, model, iter):
      if self.exiting:
         return
      self.rowconfig(tv_column, cell_renderer, model, iter)
      if model.get_value(iter, 0)[0] == ">":
         cell_renderer.set_property("text", " ")
      else:
         if model.get_value(iter, 7) == RGDEF:
            # Red triangle.
            cell_renderer.set_property("markup", '<span foreground="dark red">&#x25b5;</span>')
         else:
            # Small green bullet point.
            cell_renderer.set_property("markup", '<span foreground="dark green">&#x2022;</span>')
        
   def playtimerowconfig(self, tv_column, cell_renderer, model, iter):
      if self.exiting:
         return
      playtime = model.get_value(iter, 2)
      self.rowconfig(tv_column, cell_renderer, model, iter)
      cell_renderer.set_property("xalign", 1.0)
      if playtime == -11:
         if model.get_value(iter, 0) == ">announcement":
            length = model.get_value(iter, 3)[2:6]
            if not length:
               length = "0000"
            if length == "0000":
               cell_renderer.set_property("text", "")
            else:
               if length[0] == "0":
                  length = " " + length[1] + ":" + length[2:]
               else:
                  length = length[:2] + ":" + length[2:]
               cell_renderer.set_property("text", length)
         else:
            cell_renderer.set_property("text", "")
      elif playtime == 0:
         cell_renderer.set_property("text", "? : ??")
      else:   
         secs = playtime % 60
         playtime -= secs
         mins = playtime / 60
         text = "%d:%02d" % (mins, secs)
         cell_renderer.set_property("text", text)

   def rowconfig(self, tv_column, cell_renderer, model, iter):
      if self.exiting:
         return
      celltext = model.get_value(iter, 0)
      if celltext[:4] == "<b>>":
         celltext = celltext[3:-4]
      if celltext[0] == ">" and self.pl_mode.get_active() == 0:
         cell_renderer.set_property("xalign", 0.45)
         cell_renderer.set_property("ypad", 0)
         cell_renderer.set_property("scale", 0.75)
         cell_renderer.set_property("cell-background-set", True)
         cell_renderer.set_property("background-set", True)
         cell_renderer.set_property("foreground-set", True)
         
         if celltext == ">fade10":
            cell_renderer.set_property("cell-background", "dark red")
            cell_renderer.set_property("background", "gray")
            cell_renderer.set_property("foreground", "dark red")
            cell_renderer.set_property("text", ln.fade_10_menu)
         if celltext == ">fade5":
            cell_renderer.set_property("cell-background", "dark red")
            cell_renderer.set_property("background", "gray")
            cell_renderer.set_property("foreground", "dark red")
            cell_renderer.set_property("text", ln.fade_5_menu)
         if celltext == ">fadenone":
            cell_renderer.set_property("cell-background", "dark red")
            cell_renderer.set_property("background", "gray")
            cell_renderer.set_property("foreground", "dark red")
            cell_renderer.set_property("text", ln.fade_none_menu)
         if celltext == ">announcement":
            cell_renderer.set_property("cell-background", "dark blue")
            cell_renderer.set_property("background", "gray")
            cell_renderer.set_property("foreground", "dark blue")
            cell_renderer.set_property("text", ln.announcement_element)
         if celltext == ">openaux":
            cell_renderer.set_property("cell-background", "light green")
            cell_renderer.set_property("background", "gray")
            cell_renderer.set_property("foreground", "light green")
            cell_renderer.set_property("text", ln.open_aux_element)
         if celltext == ">normalspeed":
            cell_renderer.set_property("cell-background", "dark green")
            cell_renderer.set_property("background", "gray")
            cell_renderer.set_property("foreground", "dark green")
            cell_renderer.set_property("text", ln.normal_speed_element)
         if celltext == ">stopplayer":
            cell_renderer.set_property("cell-background", "red")
            cell_renderer.set_property("background", "gray")
            cell_renderer.set_property("foreground", "red")
            cell_renderer.set_property("text", ln.stop_control_element)
         if celltext == ">jumptotop":
            cell_renderer.set_property("cell-background", "dark magenta")
            cell_renderer.set_property("background", "gray")
            cell_renderer.set_property("foreground", "dark magenta")
            cell_renderer.set_property("text", ln.jump_to_top_control_element)
         if celltext == ">stopstreaming":
            cell_renderer.set_property("cell-background", "black")
            cell_renderer.set_property("background", "gray")
            cell_renderer.set_property("foreground", "black")
            cell_renderer.set_property("text", ln.stream_disconnect_element)
         if celltext == ">stoprecording":
            cell_renderer.set_property("cell-background", "black")
            cell_renderer.set_property("background", "gray")
            cell_renderer.set_property("foreground", "black")
            cell_renderer.set_property("text", ln.stop_recording_element)
         if celltext == ">transfer":
            cell_renderer.set_property("cell-background", "magenta")
            cell_renderer.set_property("background", "gray")
            cell_renderer.set_property("foreground", "magenta")
            if self.playername == "left":
               cell_renderer.set_property("text", ln.transfer_control_ltr_element)
            else:
               cell_renderer.set_property("text", ln.transfer_control_rtl_element)
         if celltext == ">crossfade":
            cell_renderer.set_property("cell-background", "blue")
            cell_renderer.set_property("background", "gray")
            cell_renderer.set_property("foreground", "blue")
            if self.playername == "left":
               cell_renderer.set_property("text", ln.crossfade_control_ltr_element)
            else:
               cell_renderer.set_property("text", ln.crossfade_control_rtl_element)
      else:
         if celltext[0] == ">":
            cell_renderer.set_property("visible", False)
         else:
            cell_renderer.set_property("visible", True)
         cell_renderer.set_property("foreground-set", False)
         cell_renderer.set_property("cell-background-set", False)
         cell_renderer.set_property("background-set", False)
         cell_renderer.set_property("scale", 1.0)
         cell_renderer.set_property("xalign", 0.0)
         cell_renderer.set_property("ypad", 2)
            
   def cb_playlist_delay(self, widget):
      print "inter track fade was changed"
            
   def cb_playlist_mode(self, widget):
      self.pl_delay.set_sensitive(self.pl_mode.get_active() in (0, 1, 2, 5))
      if widget.get_active() == 0:
         self.pl_statusbar.show()
      else:
         self.pl_statusbar.hide()
      if widget.get_active() == 5:
         self.external_pl.show()
      else:
         self.external_pl.hide()
      
   def popupwindow_populate(self, window, parentwidget, parent_x, parent_y):
      frame = gtk.Frame()
      frame.set_shadow_type(gtk.SHADOW_OUT)
      window.add(frame)
      frame.show()
      hbox = gtk.HBox()
      hbox.set_border_width(10)
      hbox.set_spacing(5)
      frame.add(hbox)
      image = gtk.Image()
      image.set_from_file(pkgdatadir + "icon" + gfext)
      hbox.add(image)
      image.show()
      separator = gtk.VSeparator()
      hbox.add(separator)
      separator.show()
      vbox = gtk.VBox()
      vbox.set_spacing(3)
      hbox.add(vbox)
      vbox.show()
      hbox.show()
      
      trackscount = 0
      tracknum = 0
      tracktitle = self.songname
      duration = 0
      for each in self.liststore:
         if each[2] > 0:
            trackscount += 1
            duration += each[2]
         if each[0][:3] == "<b>":
            tracknum = trackscount
         if each[0] == ">announcement":
            duration += int(each[3][2:4]) * 60 + int(each[3][4:6])
      if trackscount:
         duration, seconds = divmod(duration, 60)
         hours, minutes = divmod(duration, 60)
         hms = hours and "%d:%02d:%02d" % (hours, minutes, seconds) or "%d:%02d" % (minutes, seconds)
         if tracknum:
            try:
               label1 = gtk.Label(ln.popupwindowplaying % (tracknum, trackscount))
            except:
               label1 = gtk.Label(ln.popupwindowplaying)
            vbox.add(label1)
            label1.show()
            label2 = gtk.Label(tracktitle)
            vbox.add(label2)
            label2.show()
            blank = gtk.Label("")
            vbox.add(blank)
            blank.show()
         else:
            try:
               label3 = gtk.Label(ln.popupwindowtracktotal % trackscount)
            except:
               label3 = gtk.Label(ln.popupwindowtracktotal)
            vbox.add(label3)
            label3.show()
         try:
            label4 = gtk.Label(ln.popupwindowplayduration % hms)
         except:
            label4 = gtk.Label(ln.popupwindowplayduration)
         vbox.add(label4)
         label4.show()
      else:
         return -1
      
   def popupwindow_inhibit(self):
      return self.pl_menu.flags() & gtk.MAPPED          # we don't want a popup window when there is a popup menu around
      
   def __init__(self, pbox, name, parent):
      self.parent = parent
      self.exiting = False                              # used to stop the running of problem code - don't ask
      # A box for the Stop/Start/Pause widgets
      self.hbox1 = gtk.HBox(True, 0)
      self.hbox1.set_border_width(2)
      self.hbox1.set_spacing(3)
      frame = gtk.Frame()
      frame.set_border_width(3)
      frame.set_shadow_type(gtk.SHADOW_IN)
      frame.add(self.hbox1)
      frame.show()
      pbox.pack_start(frame, False, False, 0)

      # A box for the progress bar, which may at a later date contain other stuff
      # Like an elapsed timer for instance.
      self.progressbox = gtk.HBox(False, 0)
      self.progressbox.set_border_width(3)
      self.progressbox.set_spacing(4)
      pbox.pack_start(self.progressbox, False, False, 0)
           
      # The numerical play progress box
      self.digiprogress = gtk.Entry()
      self.digiprogress.set_text("0:00:00")
      self.digiprogress.set_width_chars(6)
      self.digiprogress.set_editable(False)
      self.digiprogress.connect("button_press_event", self.cb_event, "DigitalProgressPress")
      self.progressbox.pack_start(self.digiprogress, False, False, 1)
      self.digiprogress.show()
      parent.tooltips.set_tip(self.digiprogress, ln.digiprogress_tip)
      
      # The play progress bar and "needle shifter"
      self.progressadj = gtk.Adjustment(0.0, 0.0, 100.0, 0.1, 1.0, 0.0)
      self.progressadj.connect("value_changed", self.cb_progress)
      self.progressbar = gtk.HScale(self.progressadj)
      self.progressbar.set_update_policy(gtk.UPDATE_CONTINUOUS)
      self.progressbar.set_digits(1)
      self.progressbar.set_value_pos(gtk.POS_TOP)
      self.progressbar.set_draw_value(False)
      self.progressbar.connect("button_press_event", self.cb_event, "ProgressPress")
      self.progressbar.connect("button_release_event", self.cb_event, "ProgressRelease")
      self.progressbox.pack_start(self.progressbar, True, True, 0)
      self.progressbar.show()
      parent.tooltips.set_tip(self.progressbar, ln.play_progress_tip)
      
      # Finished filling the progress box so lets show it.
      self.progressbox.show()
      
      # A frame for our playlist
      if name == "left":
         plframe = gtk.Frame(" " + ln.playlist + " 1 ")
      else:
         plframe = gtk.Frame(" " + ln.playlist + " 2 ")  
      plframe.set_border_width(4)
      plframe.set_shadow_type(gtk.SHADOW_ETCHED_IN)
      plframe.show()
      plvbox = gtk.VBox()
      plframe.add(plvbox)
      plvbox.show()
      # The scrollable window box that will contain our playlist.
      self.scrolllist = gtk.ScrolledWindow()
      self.scrolllist.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_ALWAYS)
      self.scrolllist.set_size_request(-1, 117)
      self.scrolllist.set_border_width(4)
      self.scrolllist.set_shadow_type(gtk.SHADOW_IN)
      # A liststore object for our playlist
      # The first one gets rendered and is derived from id3 tags or just is the filename
      # when the id3 tag is not sufficient.
      # The second one always is the filename and is passed to the player.
      self.liststore = gtk.ListStore(str, str, int, str, str, str, str, float, CueSheetListStore)
      self.templist = gtk.ListStore(str, str, int, str, str, str, str, float, CueSheetListStore)
      self.treeview = gtk.TreeView(self.liststore)
      self.rgcellrender = gtk.CellRendererText()
      self.playtimecellrender = gtk.CellRendererText()
      self.cellrender = gtk.CellRendererText()
      self.cellrender.set_property("ellipsize", pango.ELLIPSIZE_END)
      self.rgtvcolumn = gtk.TreeViewColumn("", self.rgcellrender)
      self.playtimetvcolumn = gtk.TreeViewColumn("Time", self.playtimecellrender)
      self.tvcolumn = gtk.TreeViewColumn("Playlist", self.cellrender, markup=0)
      self.rgtvcolumn.set_cell_data_func(self.rgcellrender, self.rgrowconfig)
      self.playtimetvcolumn.set_cell_data_func(self.playtimecellrender, self.playtimerowconfig)
      self.tvcolumn.set_cell_data_func(self.cellrender, self.rowconfig)
      self.playtimetvcolumn.set_sizing(gtk.TREE_VIEW_COLUMN_AUTOSIZE)
      self.tvcolumn.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
      self.tvcolumn.set_expand(True)
      self.treeview.append_column(self.tvcolumn)
      self.treeview.append_column(self.playtimetvcolumn)
      self.treeview.set_search_column(0)
      self.treeview.set_headers_visible(False)
      self.treeview.set_enable_search(False)
      self.treeview.enable_model_drag_source( gtk.gdk.BUTTON1_MASK,
                                                self.sourcetargets,
                                                gtk.gdk.ACTION_DEFAULT |
                                                gtk.gdk.ACTION_MOVE)
      self.treeview.enable_model_drag_dest( self.droptargets,
                                                gtk.gdk.ACTION_DEFAULT)
        
      self.treeview.connect("drag_data_get", self.drag_data_get_data)
      self.treeview.connect("drag_data_received", self.drag_data_received_data)
      self.treeview.connect("drag_data_delete", self.drag_data_delete)
      
      self.treeview.connect("row_activated", self.cb_doubleclick, "Double click")
      self.treeview.get_selection().connect("changed", self.cb_selection_changed)
      
      self.treeview.connect("key_press_event", self.cb_keypress)
      
      self.liststore.connect("row-inserted", self.cb_playlist_changed)
      self.liststore.connect("row-deleted", self.cb_playlist_changed)
      
      self.scrolllist.add(self.treeview)
      self.treeview.show()
      
      plvbox.pack_start(self.scrolllist, True, True, 0)
      self.scrolllist.show()
      
      # Cue sheet playlist controls.
      
      self.cuesheet_playlist = CuesheetPlaylist()
      plvbox.pack_start(self.cuesheet_playlist)
      
      # External playlist control unit
      self.external_pl = ExternalPL(self)
      plvbox.pack_start(self.external_pl, False, False, 0)
      
      # File filters for file dialogs
      self.plfilefilter_all = gtk.FileFilter()
      self.plfilefilter_all.set_name(ln.playlistfilter_all)
      self.plfilefilter_all.add_pattern("*")
      self.plfilefilter_playlists = gtk.FileFilter()
      self.plfilefilter_playlists.set_name(ln.playlistfilter_supported)
      self.plfilefilter_playlists.add_mime_type("audio/x-mpegurl")
      self.plfilefilter_playlists.add_mime_type("application/xspf+xml")
      self.plfilefilter_playlists.add_mime_type("audio/x-scpls")
      self.plfilefilter_media = gtk.FileFilter()
      self.plfilefilter_media.set_name(ln.mediafilter_all)
      for each in supported.media:
         self.plfilefilter_media.add_pattern("*" + each)
         self.plfilefilter_media.add_pattern("*" + each.upper())
      
      # An information display for playlist stats
      self.pl_statusbar = gtk.Statusbar()
      self.pl_statusbar.set_has_resize_grip(False)
      plvbox.pack_start(self.pl_statusbar, False, False, 0)
      self.pl_statusbar.show()
      parent.tooltips.set_tip(self.pl_statusbar, ln.statusbar_tip)

      pbox.pack_start(plframe, True, True, 0) 
      
      # A box for the playback speed controls
      self.pbspeedbox = gtk.HBox(False, 0)
      self.pbspeedbox.set_border_width(3)
      self.pbspeedbox.set_spacing(3)
      pbox.pack_start(self.pbspeedbox, False, False, 0)
      
      # The playback speed control
      self.pbspeedadj = gtk.Adjustment(0.0, -12.0, 12.0, 0.0125, 0.0, 0.0)
      self.pbspeedadj.connect("value_changed", self.cb_pbspeed)
      self.pbspeedbar = gtk.HScale(self.pbspeedadj)
      self.pbspeedbar.set_update_policy(gtk.UPDATE_CONTINUOUS)
      self.pbspeedbar.set_digits(1)
      self.pbspeedbar.set_value_pos(gtk.POS_TOP)
      self.pbspeedbar.set_draw_value(False)
      self.pbspeedbox.pack_start(self.pbspeedbar, True, True, 0)
      self.pbspeedbar.show()
      parent.tooltips.set_tip(self.pbspeedbar, ln.playback_speed_tip)
      
      self.pbspeedzerobutton = gtk.Button()
      self.pbspeedzerobutton.connect("clicked", self.callback, "pbspeedzero")
      pixbuf = gtk.gdk.pixbuf_new_from_file(pkgdatadir+ "speedicon" + gfext)
      pixbuf = pixbuf.scale_simple(55, 14, gtk.gdk.INTERP_BILINEAR)
      image = gtk.Image()
      image.set_from_pixbuf(pixbuf)
      image.show()
      self.pbspeedzerobutton.add(image)
      self.pbspeedbox.pack_start(self.pbspeedzerobutton, False, False, 1)
      self.pbspeedzerobutton.show()
      parent.tooltips.set_tip(self.pbspeedzerobutton, ln.centre_pbspeed_tip)
      
      # The box for the mute widgets.
      self.hbox2 = gtk.HBox(False, 0)
      self.hbox2.set_border_width(4)
      self.hbox2.set_spacing(4)
      frame = gtk.Frame()
      frame.set_border_width(4)
      frame.add(self.hbox2)
      pbox.pack_start(frame, False, False, 0)
      frame.show()

      # A set of buttons for hbox1 namely Prev/Play/Pause/Stop/Next/Playlist : XMMS order
      image = gtk.Image()
      image.set_from_file(pkgdatadir + "prev" + gfext)
      image.show()
      self.prev = gtk.Button()
      self.prev.add(image)
      self.prev.connect("clicked", self.callback, "Prev")
      self.hbox1.add(self.prev)
      self.prev.show()
      parent.tooltips.set_tip(self.prev, ln.previous_tip)
      
      pixbuf = gtk.gdk.pixbuf_new_from_file(pkgdatadir + "play2" + gfext)
      pixbuf = pixbuf.scale_simple(14, 14, gtk.gdk.INTERP_BILINEAR)
      image=gtk.Image()
      image.set_from_pixbuf(pixbuf)
      image.show()
      self.play = gtk.ToggleButton()
      self.play.add(image)
      self.play.connect("toggled", self.cb_toggle, "Play")
      self.hbox1.add(self.play)
      self.play.show()
      parent.tooltips.set_tip(self.play, ln.play_tip)
      
      image=gtk.Image()
      image.set_from_file(pkgdatadir + "pause" + gfext)
      image.show()
      self.pause = gtk.ToggleButton()
      self.pause.add(image)
      self.pause.connect("toggled", self.cb_toggle, "Pause")
      self.hbox1.add(self.pause)
      self.pause.show()
      parent.tooltips.set_tip(self.pause, ln.pause_tip)
      
      image=gtk.Image()
      image.set_from_file(pkgdatadir + "stop" + gfext)
      image.show()
      self.stop = gtk.Button()
      self.stop.add(image)
      self.stop.connect("clicked", self.callback, "Stop")
      self.hbox1.add(self.stop)
      self.stop.show()
      parent.tooltips.set_tip(self.stop, ln.stop_tip)
            
      image=gtk.Image()
      image.set_from_file(pkgdatadir + "next" + gfext)
      image.show()
      self.next = gtk.Button()
      self.next.add(image)
      self.next.connect("clicked", self.callback, "Next")
      self.hbox1.add(self.next)
      self.next.show()
      parent.tooltips.set_tip(self.next, ln.next_track_tip)

      pixbuf = gtk.gdk.pixbuf_new_from_file(pkgdatadir + "add3" + gfext)
      pixbuf = pixbuf.scale_simple(14, 14, gtk.gdk.INTERP_HYPER)
      image = gtk.Image()
      image.set_from_pixbuf(pixbuf)
      image.show()
      self.add = gtk.Button()
      self.add.add(image)
      self.add.connect("clicked", self.callback, "Add Files")
      self.hbox1.add(self.add)
      self.add.show()
      parent.tooltips.set_tip(self.add, ln.add_track_tip)
      
      # hbox1 is done so it is time to show it
      self.hbox1.show()

      # The playlist mode dropdown menu.
      
      frame = ButtonFrame(ln.playlistmode)
      self.hbox2.pack_start(frame, True, True, 0)
      frame.show()
      
      self.pl_mode = gtk.combo_box_new_text()
      self.pl_mode.append_text(ln.play_all)
      self.pl_mode.append_text(ln.loop_all)
      self.pl_mode.append_text(ln.random)
      self.pl_mode.append_text(ln.manual)
      self.pl_mode.append_text(ln.cue_up)
      self.pl_mode.append_text(ln.external)
      self.pl_mode.append_text(ln.alternate)
      self.pl_mode.set_active(0)
      self.pl_mode.connect("changed", self.cb_playlist_mode)
      parent.tooltips.set_tip(self.pl_mode, ln.playlist_modes_tip)
      
      frame.hbox.pack_start(self.pl_mode, True, True, 0)
      self.pl_mode.show()
      
      frame = ButtonFrame(ln.trackfade)
      self.hbox2.pack_start(frame, True, True, 0)
      frame.show()
      
      self.pl_delay = gtk.combo_box_new_text()
      self.pl_delay.append_text(ln.pldelay_none)
      self.pl_delay.append_text("5")
      self.pl_delay.append_text("10")
      self.pl_delay.set_active(0)
      self.pl_delay.connect("changed", self.cb_playlist_delay)
      parent.tooltips.set_tip(self.pl_delay, ln.pldelay_tip)
      
      frame.hbox.pack_start(self.pl_delay, True, True, 0)
      self.pl_delay.show()
      
      # Mute buttons
      
      frame = ButtonFrame(ln.audiofeed)
      self.hbox2.pack_start(frame, True, True, 0)
      frame.show()
      
      self.stream = gtk.ToggleButton(ln.stream)
      self.stream.set_active(True)
      self.stream.connect("toggled", self.cb_toggle, "Stream")
      frame.hbox.pack_start(self.stream, True, True, 0)
      self.stream.show()
      parent.tooltips.set_tip(self.stream, ln.stream_tip)
            
      self.listen = nice_listen_togglebutton(ln.djlisten)
      self.listen.set_active(True)
      self.listen.connect("toggled", self.cb_toggle, "Listen")
      frame.hbox.pack_start(self.listen, True, True, 0)
      self.listen.show()
      parent.tooltips.set_tip(self.listen, ln.listen_tip)
      
      #sizegroup = gtk.SizeGroup(gtk.SIZE_GROUP_HORIZONTAL)
      #sizegroup.add_widget(self.stream)
      #sizegroup.add_widget(self.listen)
      
      # hbox2 is now filled so lets show it
      self.hbox2.show()
      
      # Popup menu code here
      
      # Main popup menu
      self.pl_menu = gtk.Menu()

      self.pl_menu_control = gtk.MenuItem(ln.control_menu)
      self.pl_menu.append(self.pl_menu_control)
      self.pl_menu_control.show()

      separator = gtk.SeparatorMenuItem()
      self.pl_menu.append(separator)
      separator.show()
      
      self.pl_menu_item = gtk.MenuItem(ln.item_menu)
      self.pl_menu.append(self.pl_menu_item)
      self.pl_menu_item.show()
      
      self.pl_menu_playlist = gtk.MenuItem(ln.playlist_menu)
      self.pl_menu.append(self.pl_menu_playlist)
      self.pl_menu_playlist.show()
      
      self.pl_menu.show()
      
      # Control element submenu of main popup menu
      
      self.control_menu = gtk.Menu()
      
      self.control_normal_speed_control = gtk.MenuItem(ln.normal_speed_control_menu)
      self.control_normal_speed_control.connect("activate", self.menuitem_response, "Normal Speed Control")
      self.control_menu.append(self.control_normal_speed_control)
      self.control_normal_speed_control.show()
      
      self.control_menu_stop_control = gtk.MenuItem(ln.stop_control_menu)
      self.control_menu_stop_control.connect("activate", self.menuitem_response, "Stop Control")
      self.control_menu.append(self.control_menu_stop_control)
      self.control_menu_stop_control.show()

      self.control_menu_jumptop_control = gtk.MenuItem(ln.jump_to_top_control_menu)
      self.control_menu_jumptop_control.connect("activate", self.menuitem_response, "Jump To Top Control")
      self.control_menu.append(self.control_menu_jumptop_control)
      self.control_menu_jumptop_control.show()
      
      self.control_menu_transfer_control = gtk.MenuItem(ln.transfer_control_menu)
      self.control_menu_transfer_control.connect("activate", self.menuitem_response, "Transfer Control")
      self.control_menu.append(self.control_menu_transfer_control)
      self.control_menu_transfer_control.show()
      
      self.control_menu_crossfade_control = gtk.MenuItem(ln.crossfade_control_menu)
      self.control_menu_crossfade_control.connect("activate", self.menuitem_response, "Crossfade Control")
      self.control_menu.append(self.control_menu_crossfade_control)
      self.control_menu_crossfade_control.show()
      
      self.control_menu_auxinput_control = gtk.MenuItem(ln.auxinput_control_menu)
      self.control_menu_auxinput_control.connect("activate", self.menuitem_response, "Switch To Aux Control")
      self.control_menu.append(self.control_menu_auxinput_control)
      self.control_menu_auxinput_control.show()
      
      self.control_menu_announcement_control = gtk.MenuItem(ln.announcement_control_menu)
      self.control_menu_announcement_control.connect("activate", self.menuitem_response, "Announcement Control")
      self.control_menu.append(self.control_menu_announcement_control)
      self.control_menu_announcement_control.show()
      
      separator = gtk.SeparatorMenuItem()
      self.control_menu.append(separator)
      separator.show()
      
      self.control_menu_fade_10_control = gtk.MenuItem(ln.fade_10_menu)
      self.control_menu_fade_10_control.connect("activate", self.menuitem_response, "Fade 10")
      self.control_menu.append(self.control_menu_fade_10_control)
      self.control_menu_fade_10_control.show()
      
      self.control_menu_fade_5_control = gtk.MenuItem(ln.fade_5_menu)
      self.control_menu_fade_5_control.connect("activate", self.menuitem_response, "Fade 5")
      self.control_menu.append(self.control_menu_fade_5_control)
      self.control_menu_fade_5_control.show()
      
      self.control_menu_fade_none_control = gtk.MenuItem(ln.fade_none_menu)
      self.control_menu_fade_none_control.connect("activate", self.menuitem_response, "Fade none")
      self.control_menu.append(self.control_menu_fade_none_control)
      self.control_menu_fade_none_control.show()
      
      separator = gtk.SeparatorMenuItem()
      self.control_menu.append(separator)
      separator.show()
      
      self.control_menu_stream_disconnect_control = gtk.MenuItem(ln.stream_disconnect_menu)
      self.control_menu_stream_disconnect_control.connect("activate", self.menuitem_response, "Stream Disconnect Control")
      self.control_menu.append(self.control_menu_stream_disconnect_control)
      self.control_menu_stream_disconnect_control.show()
      
      self.control_menu_stop_recording_control = gtk.MenuItem(ln.stop_recording_menu)
      self.control_menu_stop_recording_control.connect("activate", self.menuitem_response, "Stop Recording Control")
      self.control_menu.append(self.control_menu_stop_recording_control)
      self.control_menu_stop_recording_control.show()
      
      self.pl_menu_control.set_submenu(self.control_menu)
      self.control_menu.show()
      
      # Item submenu of main popup menu
      self.item_menu = gtk.Menu()
      
      self.item_tag = gtk.MenuItem(ln.meta_tag)
      self.item_tag.connect("activate", self.menuitem_response, "MetaTag")
      self.item_menu.append(self.item_tag)
      self.item_tag.show()
      
      self.item_duplicate = gtk.MenuItem(ln.duplicate)
      self.item_duplicate.connect("activate", self.menuitem_response, "Duplicate")
      self.item_menu.append(self.item_duplicate)
      self.item_duplicate.show()
      
      self.item_remove = gtk.MenuItem(ln.remove)
      self.item_menu.append(self.item_remove)
      self.item_remove.show()
      
      self.item_tojingles = gtk.MenuItem(ln.add_to_jingles)
      self.item_tojingles.connect("activate", self.menuitem_response, "ToJingles")
      self.item_menu.append(self.item_tojingles)
      self.item_tojingles.show()
      
      self.pl_menu_item.set_submenu(self.item_menu)
      self.item_menu.show()
      
      # Remove submenu of Item submenu
      self.remove_menu = gtk.Menu()

      self.remove_this = gtk.MenuItem(ln.this)
      self.remove_this.connect("activate", self.menuitem_response, "Remove This")
      self.remove_menu.append(self.remove_this)
      self.remove_this.show()
      
      self.remove_all = gtk.MenuItem(ln.all)
      self.remove_all.connect("activate", self.menuitem_response, "Remove All")
      self.remove_menu.append(self.remove_all)
      self.remove_all.show()
      
      self.remove_from_here = gtk.MenuItem(ln.from_here)
      self.remove_from_here.connect("activate", self.menuitem_response, "Remove From Here")
      self.remove_menu.append(self.remove_from_here)
      self.remove_from_here.show()
      
      self.remove_to_here = gtk.MenuItem(ln.to_here)
      self.remove_to_here.connect("activate", self.menuitem_response, "Remove To Here")
      self.remove_menu.append(self.remove_to_here)
      self.remove_to_here.show()
      
      self.item_remove.set_submenu(self.remove_menu)
      self.remove_menu.show()
      
      # Playlist submenu of main popup menu.
      self.playlist_menu = gtk.Menu()
      
      self.playlist_add_file = gtk.MenuItem(ln.add_file)
      self.playlist_add_file.connect("activate", self.menuitem_response, "Add File")
      self.playlist_menu.append(self.playlist_add_file)
      self.playlist_add_file.show()
      
      self.playlist_save = gtk.MenuItem(ln.save)
      self.playlist_save.connect("activate", self.menuitem_response, "Playlist Save")
      self.playlist_menu.append(self.playlist_save)
      self.playlist_save.show()
      
      separator = gtk.SeparatorMenuItem()
      self.playlist_menu.append(separator)
      separator.show()
      
      self.playlist_copy = gtk.MenuItem(ln.copy)
      self.playlist_menu.append(self.playlist_copy)
      self.playlist_copy.show()
      
      self.playlist_transfer = gtk.MenuItem(ln.transfer)
      self.playlist_menu.append(self.playlist_transfer)
      self.playlist_transfer.show()
      
      self.playlist_exchange = gtk.MenuItem(ln.exchange)
      self.playlist_exchange.connect("activate", self.menuitem_response, "Playlist Exchange")
      self.playlist_menu.append(self.playlist_exchange)
      self.playlist_exchange.show()
      
      self.playlist_empty = gtk.MenuItem(ln.empty)
      self.playlist_empty.connect("activate", self.menuitem_response, "Remove All")
      self.playlist_menu.append(self.playlist_empty)
      self.playlist_empty.show()
      
      self.pl_menu_playlist.set_submenu(self.playlist_menu)
      self.playlist_menu.show()
      
      # Position Submenu of Playlist-Copy menu item
      
      self.copy_menu = gtk.Menu()
      
      self.copy_append = gtk.MenuItem(ln.append)
      self.copy_append.connect("activate", self.menuitem_response, "Copy Append")
      self.copy_menu.append(self.copy_append)
      self.copy_append.show()
      
      self.copy_prepend = gtk.MenuItem(ln.prepend)
      self.copy_prepend.connect("activate", self.menuitem_response, "Copy Prepend")
      self.copy_menu.append(self.copy_prepend)
      self.copy_prepend.show()
      
      separator = gtk.SeparatorMenuItem()
      self.copy_menu.append(separator)
      separator.show()
      
      self.copy_append_cursor = gtk.MenuItem(ln.append_cursor)
      self.copy_append_cursor.connect("activate", self.menuitem_response, "Copy Append Cursor")
      self.copy_menu.append(self.copy_append_cursor)
      self.copy_append_cursor.show()
      
      self.copy_prepend_cursor = gtk.MenuItem(ln.prepend_cursor)
      self.copy_prepend_cursor.connect("activate", self.menuitem_response, "Copy Prepend Cursor")
      self.copy_menu.append(self.copy_prepend_cursor)
      self.copy_prepend_cursor.show()

      self.playlist_copy.set_submenu(self.copy_menu)
      self.copy_menu.show()
      
      # Position Submenu of Playlist-Transfer menu item
      
      self.transfer_menu = gtk.Menu()
      
      self.transfer_append = gtk.MenuItem(ln.append)
      self.transfer_append.connect("activate", self.menuitem_response, "Transfer Append")
      self.transfer_menu.append(self.transfer_append)
      self.transfer_append.show()
      
      self.transfer_prepend = gtk.MenuItem(ln.prepend)
      self.transfer_prepend.connect("activate", self.menuitem_response, "Transfer Prepend")
      self.transfer_menu.append(self.transfer_prepend)
      self.transfer_prepend.show()
      
      separator = gtk.SeparatorMenuItem()
      self.transfer_menu.append(separator)
      separator.show()
      
      self.transfer_append_cursor = gtk.MenuItem(ln.append_cursor)
      self.transfer_append_cursor.connect("activate", self.menuitem_response, "Transfer Append Cursor")
      self.transfer_menu.append(self.transfer_append_cursor)
      self.transfer_append_cursor.show()
      
      self.transfer_prepend_cursor = gtk.MenuItem(ln.prepend_cursor)
      self.transfer_prepend_cursor.connect("activate", self.menuitem_response, "Transfer Prepend Cursor")
      self.transfer_menu.append(self.transfer_prepend_cursor)
      self.transfer_prepend_cursor.show()

      self.playlist_transfer.set_submenu(self.transfer_menu)
      self.transfer_menu.show()      
 
 
      self.treeview.connect_object("event", self.menu_activate, self.pl_menu)
      popupwindow.PopupWindow(self.treeview, 12, 120, 10, self.popupwindow_populate, self.popupwindow_inhibit)

      # Initialisations
      self.playername = name 
      self.showing_file_requester = False
      self.showing_pl_save_requester = False

      # Get the users home directory and test that the environment variable is okay.
      # Actually this is more than bullet proof because when HOME is wrong I cant even run it.
      self.home = os.getenv("HOME")
      if os.path.exists(self.home):
         if os.path.isdir(self.home) == False:
            self.home = os.path.basename(self.home)
         else:
            # Make sure there is a trailing slash or the filerequester will mess up a bit.
            if self.home[-1:] != '/':
               self.home = self.home + '/'
               
      self.file_requester_start_dir = int_object(self.home)
      self.plsave_filetype = 0
      self.plsave_open = False
      self.plsave_filtertype = self.plfilefilter_all
      self.plsave_folder = None
      
      # This is used for mouse-click debounce when deleting files in the playlist.
      self.last_time = time.time()
      
      # This flag symbolises if we are playing music or not.
      self.is_playing = False
      self.is_paused = False
      self.is_stopping = False
      self.player_is_playing = False
      self.new_title = False
      self.timeout_source_id = 0
      self.progress_press = False
      random.seed()
      # The maximum value from the progress bar at startup
      self.max_seek = 100.0
      self.reselect_please = False
      self.reselect_cursor_please = False
      self.songname = u""
      self.flush = False
      self.title = ""
      self.artist = ""
      self.gapless = False
      self.seek_file_valid = False
      self.digiprogress_type = 0
      self.digiprogress_f = 0
      self.handle_motion_as_drop = False
      self.other_player_initiated = False
      self.crossfader_initiated = False
      self.music_filename = ""
      self.session_filename = self.parent.idjc + self.playername + "_session"
      self.oldstatusbartext = ""
      self.pbspeedfactor = 1.0
      self.playlist_changed = True
      self.alarm_cid = 0
      self.playlist_todo = deque()
      self.no_more_files = False

