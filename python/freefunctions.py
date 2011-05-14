#   IDJCfree.py: Free functions used by IDJC
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

import pygtk
pygtk.require("2.0")
import gtk

import os, encodings.hex_codec
from idjc_config import *
import pangocairo, pango

# Convert characters that have special meaning in pango markup language to their safe equivalents
def rich_safe(x):
   x=x.replace("&", "&amp;")
   x=x.replace("<", "&lt;")
   x=x.replace(">", "&gt;")
   x=x.replace('"', "&quot;")
   return x

def make_cachesafe(arglist, filename):          # modifies mplayer arg list
   bad = [ "ogg", "flac" ]                      # these files will not use -cache option
   ext = os.path.splitext(filename)[1][1:]
   if bad.count(ext):
      try:
         index = arglist.index("-cache")
         del arglist[index]                     # -cache and its parameter are removed
         del arglist[index]                     # so mplayer will start quickly
      except:
         pass                                   # cache option can sometimes be missing


# url_unescape: convert %xx escape sequences in strings to characters.
def url_unescape(text_in):
   output = ""
   double = False
   skip = 0
   for index in range(len(text_in)):
      if double == True:
         double = False
         continue
      if skip:
         skip = skip - 1
         continue
      else:
         if text_in[index] == "%":
            try:
               if text_in[index + 1] == "%":
                  double = True
                  ch = "%"
               else:
                  ch = text_in[index+1:index+3].decode("hex")
                  skip = 2
            except IndexError,TypeError:
               pass
         else:
            ch = text_in[index]
         output = output + ch
   return output

class int_object:               # Putting an int in a class allows its use in a dictionary
   def __init__(self, value = 0):
      self.value = value
   def __str__(self):
      return self.value
   def __int__(self):
      return int(self.value)
   def set_meter_value(self, value):
      self.value = value
      return self.value
   def set_value(self, value):
      self.value = value
      return self.value
   def get_value(self):
      return self.value
   def get_text(self):
      return self.value
   def set_text(self, value):
      self.value = value

def threadslock(f):
   def newf(*args, **kwargs):
      gtk.gdk.threads_enter()
      try:
         r = f(*args, **kwargs)
      finally:
         gtk.gdk.threads_leave()
      return r
   return newf

class DefaultEntry(gtk.Entry):
   def __init__(self, default_text, sensitive_override=False):
      gtk.Entry.__init__(self)
      self.connect("focus-in-event", self.on_focus_in)
      self.connect("focus-out-event", self.on_focus_out)
      self.props.primary_icon_activatable = True
      self.connect("icon-press", self.on_icon_press)
      self.connect("realize", self.on_realize)
      self.default_text = default_text
      self.sensitive_override = sensitive_override

   def on_realize(self, entry):
      layout = self.get_layout().copy()
      layout.set_markup("<span foreground='dark gray'>%s</span>" % self.default_text)
      extents = layout.get_pixel_extents()[1]
      drawable = gtk.gdk.Pixmap(self.get_parent_window(), extents[2], extents[3])
      gc = gtk.gdk.GC(drawable)
      gc2 = entry.props.style.base_gc[0]
      drawable.draw_rectangle(gc2, True, *extents)
      drawable.draw_layout(gc, 0, 0, layout)
      pixbuf = gtk.gdk.Pixbuf(gtk.gdk.COLORSPACE_RGB, True, 8, extents[2], extents[3])
      pixbuf.get_from_drawable(drawable, drawable.get_colormap(), 0, 0, *extents)
      self.empty_pixbuf = pixbuf
      if not gtk.Entry.get_text(self):
         self.props.primary_icon_pixbuf = pixbuf

   def on_icon_press(self, entry, icon_pos, event):
      self.grab_focus()
      
   def on_focus_in(self, entry, event):
      self.props.primary_icon_pixbuf = None
      
   def on_focus_out(self, entry, event):
      text = gtk.Entry.get_text(self).strip()
      if not text:
         self.props.primary_icon_pixbuf = self.empty_pixbuf
      
   def get_text(self):
      if (self.flags() & gtk.SENSITIVE) or self.sensitive_override:
         return gtk.Entry.get_text(self).strip() or self.default_text
      else:
         return ""
      
   def set_text(self, newtext):
      newtext = newtext.strip()
      gtk.Entry.set_text(self, newtext)
      if newtext:
         self.props.primary_icon_pixbuf = None
      else:
         try:
            self.props.primary_icon_pixbuf = self.empty_pixbuf
         except AttributeError:
            pass

# string_multireplace: replace multiple items in a string without side effects
def string_multireplace(part, table):
   if not table:
      return part
      
   parts = part.split(table[0][0])
   t_next = table[1:]
   for i, each in enumerate(parts):
      parts[i] = string_multireplace(each, t_next)
      
   return table[0][1].join(parts)
