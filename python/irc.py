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


from functools import wraps

import gtk

try:
   import irclib
except ImportError:
   irclib = None

from idjc.prelims import ProfileManager


pm = ProfileManager()



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



def grabselected(f):
   """Function decorator to obtain selected item info from a TreeView."""
   
   @wraps(f)
   def inner(self, widget=None):
      del widget
      model, iter = self._treeview.get_selection().get_selected()
      if iter is not None:
         return f(self, model, iter, model.get_value(iter, 0))
      else:
         return None
   return inner



class ServerDialog(gtk.Dialog):
   def __init__(self):
      gtk.Dialog.__init__(self)
      self.set_modal(True)
      self.set_title("Add IRC server" + pm.title_extra)
      
      self.ok = gtk.Button(gtk.STOCK_OK)
      cancel = gtk.Button(gtk.STOCK_CANCEL)
      bb = self.get_action_area()
      for each in (self.ok, cancel):
         each.set_use_stock(True)
         each.connect_after("clicked", lambda w: self.destroy())
         bb.add(each)

      adj = gtk.Adjustment(6767.0, 0.0, 65535.0, 1.0, 10.0)

      self.network = gtk.Entry()
      self.hostname = gtk.Entry()
      self.port = gtk.SpinButton(adj)
      self.ssl = gtk.CheckButton("SSL")
      self.password = gtk.Entry()
      self.password.set_visibility(False)
      
      hbox = gtk.HBox()
      hbox.set_border_width(16)
      hbox.set_spacing(5)
      
      image = gtk.image_new_from_stock(gtk.STOCK_NETWORK, gtk.ICON_SIZE_DIALOG)
      lvbox = gtk.VBox(True)
      rvbox = gtk.VBox(True)
      hbox.pack_start(image, False, padding=20)
      hbox.pack_start(lvbox, False)
      hbox.pack_start(rvbox, False)
      
      for each in (lvbox, rvbox):
         each.set_spacing(4)
      
      for text, widget in zip(("Network", "Hostname", "Port", "", "Password"),
            (self.network, self.hostname, self.port, self.ssl, self.password)):
         l = gtk.Label(text)
         l.set_alignment(1.0, 0.5)
         lvbox.pack_start(l, False)
         rvbox.pack_start(widget, False)
         
      self.get_content_area().add(hbox)
      


class EditServerDialog(ServerDialog):
   def __init__(self):
      ServerDialog.__init__(self)
      self.set_title("Edit IRC server" + pm.title_extra)
      bb = self.get_action_area()
      self.refresh = gtk.Button(gtk.STOCK_REFRESH)
      self.refresh.set_use_stock(True)
      bb.add(self.refresh)
      bb.set_child_secondary(self.refresh, True)

       
         
class IRCPane(gtk.VBox):
   def __init__(self):
      gtk.VBox.__init__(self)
      self.set_border_width(4)
      self.set_spacing(3)
      self._treestore = gtk.TreeStore(int, int, int, int, str, str, str)
      self._treestore.append(None, (0, 0, 0, 0, "", "", ""))
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
      mode = model.get_value(iter, 0)
      text = ""
      
      if mode == 1:
         hostname = model.get_value(iter, 5)
         port = model.get_value(iter, 2)
         ssl = model.get_value(iter, 3)
         network = model.get_value(iter, 4)
         password = model.get_value(iter, 6)
         
         text = "%s:%d" % (hostname, port)
         if network:
            text += "(%s)" % network

         opt = []
         if ssl:
            opt.append("SSL")
         if password:
            opt.append("PASSWORD")
         if opt:
            text += " " + ", ".join(opt)

      cell.props.text = text


   @grabselected
   def _on_new(self, model, iter, mode):
      if mode == 0:
         d = ServerDialog()
         d.set_transient_for(self.get_toplevel())
         d.show_all()
         d.ok.connect("clicked", self._cb_add_server, d, model, iter)
      elif mode == 2:
         d = AnnounceDialog(self._treeview, model, iter)
         d.set_transient_for(self.get_toplevel())
         d.show_all()
         d.ok.connect("clicked", self._add_server, d, model, iter)
      
    
   @grabselected
   def _on_remove(self, model, iter, mode):
      pass
      
   
   @grabselected
   def _on_edit(self, model, iter, mode):
      if mode == 1:
         d = EditServerDialog()
         d.set_transient_for(self.get_toplevel())
         d.show_all()
         d.ok.connect("clicked", self._cb_edit_server, d, model, iter)
         d.refresh.connect("clicked", self._cb_refresh_edit_server, d, model, iter)
         d.refresh.clicked()


   def _cb_add_server(self, ok, d, model, parent_iter):
      model.append(parent_iter, (1, 1, d.port.get_value(), d.ssl.get_active(),
               d.network.get_text().strip(), d.hostname.get_text().strip(),
               d.password.get_text().strip()))
               
               
   def _cb_edit_server(self, ok, d, model, iter):
      for i, each in enumerate((d.port.get_value(), d.ssl.get_active(),
            d.network.get_text().strip(), d.hostname.get_text().strip(),
                              d.password.get_text().strip()), start=2):
         model.set_value(iter, i, each)


   def _cb_refresh_edit_server(self, refresh, d, model, iter):
      d.port.set_value(model.get_value(iter, 2))
      d.ssl.set_active(model.get_value(iter, 3))
      d.network.set_text(model.get_value(iter, 4))
      d.hostname.set_text(model.get_value(iter, 5))
      d.password.set_text(model.get_value(iter, 6))
