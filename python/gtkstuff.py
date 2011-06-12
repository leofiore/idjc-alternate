"""Generally useful gtk based widgets."""

#   Copyright (C) 2011 Stephen Fairchild (s-fairchild@users.sourceforge.net)
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

import gobject
import gtk

from idjc import FGlobs, PGlobs


class LEDDict(dict):
   """Dictionary of pixbufs of LEDs."""
   
   
   def __init__(self, size=10):
      names = "clear", "red", "green", "yellow"
      filenames = ("led_unlit_clear_border_64x64.png",
                   "led_lit_red_black_border_64x64.png",
                   "led_lit_green_black_border_64x64.png",
                   "led_lit_amber_black_border_64x64.png")
      for name, filename in zip(names, filenames):
         self[name] = gtk.gdk.pixbuf_new_from_file_at_size(
            FGlobs.pkgdatadir / filename, size, size)



class CellRendererLED(gtk.CellRendererPixbuf):
   """A cell renderer that displays LEDs."""
   
   
   __gproperties__ = {
         "active" : (gobject.TYPE_INT, "active", "active",
                     0, 1, 0, gobject.PARAM_WRITABLE),
         "color" :  (gobject.TYPE_STRING, "color", "color",
                     "clear", gobject.PARAM_WRITABLE)
   }

                     
   def __init__(self, size=10, actives=("clear", "green")):
      gtk.CellRendererPixbuf.__init__(self)
      self._led = LEDDict(size)
      self._index = [self._led[key] for key in actives] 

        
   def do_set_property(self, prop, value):
      if prop.name == "active":
         item = self._index[value]
      elif prop.name == "color":
         item = self._led[value]
      else:
         raise AttributeError("unknown property %s" % prop.name)
         
      gtk.CellRendererPixbuf.set_property(self, "pixbuf", item)



class CellRendererTime(gtk.CellRendererText):
   """Displays time in days, hours, minutes."""
   
   
   __gproperties__ = {
         "time" : (gobject.TYPE_INT, "time", "time",
                   0, 1000000000, 0, gobject.PARAM_WRITABLE)
   }
   
   
   def do_set_property(self, prop, value):
      if prop.name == "time":
         m, s = divmod(value, 60)
         h, m = divmod(m, 60)
         d, h = divmod(h, 24)
         if d:
            text = "%dd.%02d:%02d" % (d, h, m)
         else:
            text = "%02d:%02d:%02d" % (h, m, s)
      else:
         raise AttributeError("unknown property %s" % prop.name)
         
      gtk.CellRendererText.set_property(self, "text", text)



class StandardDialog(gtk.Dialog):
   def __init__(self, title, message, stock_item, label_width, modal):
      gtk.Dialog.__init__(self)
      self.set_modal(modal)
      self.set_destroy_with_parent(True)
      self.set_title(title)
      self.set_icon_from_file(PGlobs.default_icon)
      
      hbox = gtk.HBox()
      hbox.set_border_width(10)
      image = gtk.image_new_from_stock(stock_item,
                                          gtk.ICON_SIZE_DIALOG)
      hbox.pack_start(image, False, padding=30)
      vbox = gtk.VBox()
      hbox.pack_start(vbox)
      for each in message.split("\n"):
         label = gtk.Label(each)
         label.set_alignment(0, 0.5)
         label.set_size_request(label_width, -1)
         label.set_line_wrap(True)
         vbox.pack_start(label)
      self.get_content_area().add(hbox)



class ConfirmationDialog(StandardDialog):
   """This needs to be pulled out since it's generic."""
   
   def __init__(self, title, message, label_width=300, modal=True):
      StandardDialog.__init__(self, title, message,
                     gtk.STOCK_DIALOG_QUESTION, label_width, modal)
      box = gtk.HButtonBox()
      cancel = gtk.Button(stock=gtk.STOCK_CANCEL)
      cancel.connect("clicked", lambda w: self.destroy())
      box.pack_start(cancel)
      self.ok = gtk.Button(stock=gtk.STOCK_OK)
      self.ok.connect_after("clicked", lambda w: self.destroy())
      box.pack_start(self.ok)
      self.get_action_area().add(box)



class ErrorMessageDialog(StandardDialog):
   """This needs to be pulled out since it's generic."""
   
   def __init__(self, title, message, label_width=300, modal=True):
      StandardDialog.__init__(self, title, message,
                     gtk.STOCK_DIALOG_ERROR, label_width, modal)
      b = gtk.Button(stock=gtk.STOCK_CLOSE)
      b.connect("clicked", lambda w: self.destroy())
      self.get_action_area().add(b)



def threadslock(f):
   """Function decorator for thread locking timeout callbacks."""
   
   
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
