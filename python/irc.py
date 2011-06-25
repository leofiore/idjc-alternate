#   irc.py: IRC bots for IDJC
#   Copyright (C) 2011 Stephen Fairchild (s-fairchild@users.sourceforge.net)
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


__all__ = ["IRCPane"]


import gtk

try:
   import irclib
except ImportError:
   irclib = None



class IRCEntry(gtk.Entry):
   """Specialised IRC text entry widget.
   
   Features pop-up menu and direct control character insertion.
   """
   
   
   _control_keytable = {107:u"\u0003", 98:u"\u0002", 117:u"\u001F", 111:u"\u000F"}

   _XChat_colour = {
      0:  0xCCCCCCFF,
      1:  0x000000FF,
      2:  0x3636B2FF,
      3:  0x2A8C2AFF,
      4:  0xC33B3BFF,
      5:  0xC73232FF,
      6:  0x80267FFF,
      7:  0x66361FFF,
      8:  0xD9A641FF,
      9:  0x3DCC3DFF,
      10: 0x1A5555FF,
      11: 0x2F8C74FF,
      12: 0x4545E6FF,
      13: 0xB037B0FF,
      14: 0x4C4C4CFF,
      15: 0x959595FF
   }


   def __init__(self, *args, **kwds):
      gtk.Entry.__init__(self, *args, **kwds)
      self.connect("key-press-event", self._on_key_press_event)
      self.connect("populate-popup", self._popup_menu_populate)


   def _on_key_press_event(self, entry, event, data=None):
      """Handle direct insertion of control characters."""


      # Check for CTRL key modifier.
      if event.state & (~gtk.gdk.LOCK_MASK) == gtk.gdk.CONTROL_MASK:
         # Remove the effect of CAPS lock - works for letter keys only.
         keyval = event.keyval + (32 if event.state & gtk.gdk.LOCK_MASK else 0)
         try:
            replacement = self._control_keytable[keyval]
         except KeyError:
            pass
         else:
            cursor = entry.get_position()
            entry.insert_text(replacement, cursor)
            entry.set_position(cursor + 1)


   def _popup_menu_populate(self, entry, menu):
      menuitem = gtk.MenuItem(ln.insert_attribute_or_colour_code)
      menu.append(menuitem)
      submenu = gtk.Menu()
      menuitem.set_submenu(submenu)
      menuitem.show()
      
      for menutext, code in ((ln.irc_bold, u"\u0002"), (ln.irc_underline, u"\u001F"),
                                                    (ln.irc_normal, u"\u000F")):
         mi = gtk.MenuItem()
         l = gtk.Label()
         l.set_alignment(0.0, 0.5)
         l.set_markup(menutext)
         mi.add(l)
         l.show()
         mi.connect("activate", self._on_menu_item_activate, entry, code)
         submenu.append(mi)
         mi.show()
      
      for each in ("0-7", "8-15"):
         mi = gtk.MenuItem(" ".join(("Colours", each)))
         submenu.append(mi)
         cmenu = gtk.Menu()
         mi.set_submenu(cmenu)
         cmenu.show()
         lower, upper = [int(x) for x in each.split("-")]
         for i in xrange(lower, upper + 1):
            try:
               rgba = self._XChat_colour[i]
            except:
               continue

            cmi = gtk.MenuItem()
            cmi.connect("activate", self._on_menu_insert_colour_code, entry, i)
            hbox = gtk.HBox()
            
            l = gtk.Label()
            l.set_alignment(0, 0.5)
            l.set_markup("<span font_family='monospace'>%02d</span>" % i)
            hbox.pack_start(l)
            l.show()

            pixbuf = gtk.gdk.Pixbuf(gtk.gdk.COLORSPACE_RGB, True, 8, 20, 20)
            pixbuf.fill(rgba)
            image = gtk.image_new_from_pixbuf(pixbuf)
            image.connect_after("expose-event", self._on_colour_box_expose)
            hbox.pack_start(image)
            image.show()

            cmi.add(hbox)
            hbox.show()
            cmenu.append(cmi)
            cmi.show()
         mi.show()


   def _on_menu_item_activate(self, menuitem, entry, code):
      """Perform relevant character code insertion."""
      
      
      cursor = entry.get_position()
      entry.insert_text(code, cursor)
      entry.set_position(cursor + 1)


   def _on_menu_insert_colour_code(self, menuitem, entry, code):
      """One of the colour palette items was chosen."""
      
      
      cursor = entry.get_position()
      if cursor < 3 or entry.get_text()[cursor - 3] !="\x03":
         # Foreground colour.
         entry.insert_text(u"\u0003" + unicode("%02d" % code), cursor)
      else:
         # Background colour.
         entry.insert_text(unicode(",%02d" % code), cursor)
      entry.set_position(cursor + 3)


   def _on_colour_box_expose(self, widget, event, data=None):
      """A colour palette item is hovered over.
      
      This implies also prelight which needs to be cancelled.
      """ 


      widget.set_state(gtk.STATE_NORMAL)



class NewServerDialog(gtk.Dialog):
   def __init__(self, tv):
      gtk.Dialog.__init__(self)
      self.set_modal(True)
      
      


class IRCPane(gtk.VBox):
   def __init__(self):
      gtk.VBox.__init__(self)
      self.set_border_width(4)
      self.set_spacing(3)
      self._treestore = gtk.TreeStore(int, int, int, int, str)
      self._treestore.append(None, (0, 0, 0, 0, ""))
      self._treeview = gtk.TreeView(self._treestore)
      self._treeview.set_headers_visible(False)
      
      col = gtk.TreeViewColumn()
     
      toggle = gtk.CellRendererToggle()
      col.pack_start(toggle, False)
      col.add_attribute(toggle, "active", 1)
      toggle.connect("toggled", self._on_toggle)
      
      str1 = gtk.CellRendererText()
      col.pack_start(str1, False)
      col.set_cell_data_func(str1, self._cdf1)
      
      str2 = gtk.CellRendererText()
      col.pack_start(str2, False)
      col.set_cell_data_func(str2, self._cdf2)
      
      self._treeview.append_column(col)
      
      sw = gtk.ScrolledWindow()
      sw.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
      sw.add(self._treeview)
      self.pack_start(sw)
      bb = gtk.HButtonBox()
      bb.set_spacing(8)
      bb.set_layout(gtk.BUTTONBOX_END)
      new = gtk.Button("New")
      remove = gtk.Button("Remove")
      edit = gtk.Button("Edit")
      for b, c in zip((new, remove, edit), ("new", "remove", "edit")):
         bb.add(b)
         b.connect("clicked", getattr(self, "_on_" + c))
   
      bb.set_child_secondary(new, True)
      bb.set_child_secondary(remove, True)
      self.pack_start(bb, False)
      self.show_all()


   def _on_toggle(self, cell, path):
      self._treestore[path][1] = not self._treestore[path][1]
      

   def _cdf1(self, column, cell, model, iter):
      cell.props.text = ("Server", "", "Announce", "Timer", "On up",
                              "On down", "")[model.get_value(iter, 0)]
      cell.props.visible = cell.props.text != ""
      
      
   def _cdf2(self, column, cell, model, iter):
      cell.text = ""


   def _on_new(self, widget):
      n = NewServerDialog(self._treeview)
      n.set_transient_for(self.get_toplevel())
      n.show_all()
      
      
   def _on_remove(self, widget):
      pass
      
      
   def _on_edit(self, widget):
      pass
