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
import pango

try:
   import irclib
except ImportError:
   irclib = None

from idjc.prelims import ProfileManager
from .gtkstuff import DefaultEntry
from .ln_text import ln


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



class WYSIWYGView(gtk.ScrolledWindow):
   def __init__(self):
      gtk.ScrolledWindow.__init__(self)
      self.set_policy(gtk.POLICY_NEVER, gtk.POLICY_ALWAYS)
      self._textview = gtk.TextView()
      self._textview.set_size_request(500, -1)
      self.add(self._textview)
      


class EditDialogMixin(object):
   """Mix-in class to convert initial-data-entry dialogs to edit dialogs."""
   
   
   def __init__(self, orig_data):
      bb = self.get_action_area()
      self.refresh = gtk.Button(gtk.STOCK_REFRESH)
      self.refresh.set_use_stock(True)
      self.refresh.connect("clicked", lambda w: self.from_tuple(orig_data))
      bb.add(self.refresh)
      bb.set_child_secondary(self.refresh, True)
      self.refresh.clicked()



server_port_adj = gtk.Adjustment(6767.0, 0.0, 65535.0, 1.0, 10.0)



class ServerDialog(gtk.Dialog):
   """Data entry dialog for adding a new irc server."""
   
   
   def __init__(self, title="Add IRC server" + pm.title_extra):
      gtk.Dialog.__init__(self, title)

      self.network = gtk.Entry()
      self.hostname = gtk.Entry()
      self.port = gtk.SpinButton(server_port_adj)
      self.ssl = gtk.CheckButton("SSL")
      self.username = DefaultEntry("Nobody")
      self.password = gtk.Entry()
      self.password.set_visibility(False)
      self.nick1 = gtk.Entry()
      self.nick2 = gtk.Entry()
      self.nick3 = gtk.Entry()
      self.realname = gtk.Entry()
      self.nickserv = gtk.Entry()
      self.nickserv.set_visibility(False)
     
      hbox = gtk.HBox()
      hbox.set_border_width(16)
      hbox.set_spacing(5)
      
      image = gtk.image_new_from_stock(gtk.STOCK_NETWORK, gtk.ICON_SIZE_DIALOG)
      table = gtk.Table(9, 2)
      table.set_col_spacings(6)
      table.set_row_spacings(3)
      table.set_row_spacing(5, 20)
      rvbox = gtk.VBox(True)
      hbox.pack_start(image, False, padding=20)
      hbox.pack_start(table, True)
      
      for i, (text, widget) in enumerate(zip(("Network", "Hostname", "Port", "",
                              "User name", "Password", "Nickname", "Second choice",
                              "Third choice", "Real name", "Nickserv p/w"),
            (self.network, self.hostname, self.port, self.ssl,
             self.username, self.password, self.nick1, self.nick2,
             self.nick3, self.realname, self.nickserv))):
         l = gtk.Label(text)
         l.set_alignment(1.0, 0.5)
         
         table.attach(l, 0, 1, i, i + 1, gtk.SHRINK | gtk.FILL)
         table.attach(widget, 1, 2, i, i + 1)
         
      self.get_content_area().add(hbox)
      
      
   def as_tuple(self):
      return (self.port.get_value(), self.ssl.get_active(),
         self.network.get_text().strip(), self.hostname.get_text().strip(),
         self.username.get_text().strip(), self.password.get_text().strip(),
         self.nick1.get_text().strip(), self.nick2.get_text().strip(),
         self.nick3.get_text().strip(), self.realname.get_text().strip(),
         self.nickserv.get_text().strip())



class EditServerDialog(ServerDialog, EditDialogMixin):
   def __init__(self, orig_data):
      ServerDialog.__init__(self, "Edit existing IRC server")
      EditDialogMixin.__init__(self, orig_data)
      
       
   def from_tuple(self, orig_data):
      n = iter(orig_data).next
      self.port.set_value(n())
      self.ssl.set_active(n())
      self.network.set_text(n())
      self.hostname.set_text(n())
      self.username.set_text(n())
      self.password.set_text(n())
      self.nick1.set_text(n())
      self.nick2.set_text(n())
      self.nick3.set_text(n())
      self.realname.set_text(n())
      self.nickserv.set_text(n())



message_delay_adj = gtk.Adjustment(10, 0, 30, 1, 10)
message_offset_adj = gtk.Adjustment(0, 0, 9999, 1, 10)
message_interval_adj = gtk.Adjustment(600, 60, 9999, 1, 10)

         
class MessageDialog(gtk.Dialog):
   def __init__(self, title):
      gtk.Dialog.__init__(self, title + pm.title_extra)

      hbox1 = gtk.HBox()
      hbox1.set_spacing(6)
      l = gtk.Label("Channels/Users")
      self.channels = gtk.Entry()
      hbox1.pack_start(l, False)
      hbox1.pack_start(self.channels, True)
      
      hbox2 = gtk.HBox()
      hbox2.set_spacing(6)
      l = gtk.Label("Message")
      self.message = IRCEntry()
      hbox2.pack_start(l, False)
      hbox2.pack_start(self.message)
      
      self.wysiwyg = WYSIWYGView()
      vbox = gtk.VBox()
      vbox.set_spacing(5)
      vbox.pack_start(hbox1, False)
      vbox.pack_start(hbox2, False)
      vbox.pack_start(self.wysiwyg)
      
      self.hbox = gtk.HBox()
      self.hbox.set_border_width(16)
      self.hbox.set_spacing(5)
      self.image = gtk.image_new_from_stock(gtk.STOCK_NEW, gtk.ICON_SIZE_DND)
      self.hbox.pack_start(self.image, False, padding=20)
      self.hbox.pack_start(vbox)
      
      self.get_content_area().add(self.hbox)
      self.channels.grab_focus()
      
      
   def _from_channels(self):
      text = self.channels.get_text().replace(",", " ").split()
      return ",".join(x for x in text if x)


   def _pack(self, widgets):
      vbox = gtk.VBox()
      for l, w in widgets:
         ivbox = gtk.VBox()
         ivbox.set_spacing(4)
         vbox.pack_start(ivbox, True, False)
         l = gtk.Label(l)
         ivbox.pack_start(l)
         ivbox.pack_start(w)
         
      self.hbox.pack_start(vbox, False, padding=20)


   def as_tuple(self):
      return self._from_channels(), self.message.get_text().strip()



class EditMessageDialog(MessageDialog, EditDialogMixin):
   def __init__(self, title, orig_data):
      MessageDialog.__init__(self, title)
      EditDialogMixin.__init__(self, orig_data)
      self.image.set_from_stock(gtk.STOCK_EDIT, gtk.ICON_SIZE_DND)
      
      
   def from_tuple(self, orig_data):
      self.channels.set_text(orig_data[0])
      self.message.set_text(orig_data[1])



class AnnounceMessageDialog(MessageDialog):
   def __init__(self, title):
      MessageDialog.__init__(self, title)
      
      self.delay = gtk.SpinButton(message_delay_adj)
      self._pack((("Delay", self.delay), ))
      
      
   def as_tuple(self):
      return (self.delay.get_value(), ) + MessageDialog.as_tuple(self)



class EditAnnounceMessageDialog(AnnounceMessageDialog, EditDialogMixin):
   def __init__(self, title, orig_data):
      AnnounceMessageDialog.__init__(self, title)
      EditDialogMixin.__init__(self, orig_data)
      self.image.set_from_stock(gtk.STOCK_EDIT, gtk.ICON_SIZE_DND)
      
      
   def from_tuple(self, orig_data):
      return (self.delay.set_value(orig_data[0]),
              self.channels.set_text(orig_data[1]),
              self.message.set_text(orig_data[2]))

   

class TimerMessageDialog(MessageDialog):
   def __init__(self, title):
      MessageDialog.__init__(self, title)
      
      self.offset = gtk.SpinButton(message_offset_adj)
      self.interval = gtk.SpinButton(message_interval_adj)
      self._pack((("Offset", self.offset), ("Interval", self.interval)))
      
   def as_tuple(self):
      return (self.offset.get_value(), self.interval.get_value()
                                    ) + MessageDialog.as_tuple(self)



class EditTimerMessageDialog(TimerMessageDialog, EditDialogMixin):
   def __init__(self, title, orig_data):
      TimerMessageDialog.__init__(self, title)
      EditDialogMixin.__init__(self, orig_data)
      self.image.set_from_stock(gtk.STOCK_EDIT, gtk.ICON_SIZE_DND)
      
      
   def from_tuple(self, orig_data):
      return (self.offset.set_value(orig_data[0]),
              self.interval.set_value(orig_data[1]),
              self.channels.set_text(orig_data[2]),
              self.message.set_text(orig_data[3]))
   


def modifier(f):
   """IRCPane function decorator for new/remove/edit callbacks."""

   
   @wraps(f)
   def inner(self, widget):
      model, _iter = self._treeview.get_selection().get_selected()
         
      if _iter is not None:
         def dialog(d, cb, *args, **kwds):
            d.ok = gtk.Button(gtk.STOCK_OK)
            cancel = gtk.Button(gtk.STOCK_CANCEL)
            bb = d.get_action_area()
            for each in (d.ok, cancel):
               each.set_use_stock(True)
               each.connect_after("clicked", lambda w: d.destroy())
               bb.add(each)

            d.set_modal(True)
            d.set_transient_for(self.get_toplevel())
            d.ok.connect("clicked", lambda w: cb(d, model, _iter, *args, **kwds))
            d.show_all()

         return f(self, model.get_value(_iter, 0), model, _iter, dialog)
      else:
         return None
   return inner



def highlight(f):
   """IRCPane function decorator to highlight newly added item."""
   
   
   @wraps(f)
   def inner(self, mode, model, iter, *args, **kwds):
      new_iter = f(self, mode, model, iter, *args, **kwds)
      
      path = model.get_path(new_iter)
      self._treeview.expand_to_path(path)
      self._treeview.expand_row(path, True)
      self._treeview.get_selection().select_path(path)
      
      return new_iter
   return inner
   
   

class IRCPane(gtk.VBox):
   def __init__(self):
      gtk.VBox.__init__(self)
      self.set_border_width(4)
      self.set_spacing(3)
      self._treestore = gtk.TreeStore(int, int, int, int, str, str, str,
                                      str, str, str, str, str, str, str)
      self._treestore.append(None, (0, 1, 0, 0) + ("", ) * 10)
      self._treeview = gtk.TreeView(self._treestore)
      self._treeview.set_headers_visible(False)
      self._treeview.set_enable_tree_lines(True)
      self._treeview.get_selection().select_path(0)
      
      col = gtk.TreeViewColumn()
     
      toggle = gtk.CellRendererToggle()
      toggle.props.mode = gtk.CELL_RENDERER_MODE_INERT
      toggle.props.sensitive = False
      col.pack_start(toggle, False)
      col.add_attribute(toggle, "active", 1)
      toggle.connect("toggled", self._on_cell_toggle)
      
      crt = gtk.CellRendererText()
      crt.props.ellipsize = pango.ELLIPSIZE_END
      col.pack_start(crt, True)
      col.set_cell_data_func(crt, self._cell_data_func)
      
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

      cell_toggle_mode = gtk.ToggleButton("+Toggle")
      cell_toggle_mode.connect("toggled", self._on_cell_toggle_mode, toggle)
      bb.add(cell_toggle_mode)
      bb.set_child_secondary(cell_toggle_mode, True)

      self.pack_start(bb, False)
      self.show_all()


   def _on_cell_toggle_mode(self, mode, cell):
      if mode.get_active():
         cell.props.mode = gtk.CELL_RENDERER_MODE_ACTIVATABLE
         cell.props.sensitive = True
      else:
         cell.props.mode = gtk.CELL_RENDERER_MODE_INERT
         cell.props.sensitive = False

      tr = self._treeview.get_visible_rect()
      x, y = self._treeview.convert_tree_to_bin_window_coords(tr.x, tr.y)
      br = gtk.gdk.Rectangle(x, y, tr.width, tr.height)
      self._treeview.get_bin_window().invalidate_rect(br, True)


   def _on_cell_toggle(self, cell, path):
      self._treestore[path][1] = not self._treestore[path][1]
      

   def _cell_data_func(self, column, cell, model, iter):
      mode = model.get_value(iter, 0)
      text = ""
      
      if mode % 2:
         if mode == 1:
            port = model.get_value(iter, 2)
            ssl = model.get_value(iter, 3)
            network = model.get_value(iter, 4)
            hostname = model.get_value(iter, 5)
            password = model.get_value(iter, 7)
            nickserv = model.get_value(iter, 12)
            nick = model.get_value(iter, 13)
            
            if nick:
               text = nick + "@"
            text += "%s:%d" % (hostname, port)
            if network:
               text += "(%s)" % network

            opt = []
            if ssl:
               opt.append("SSL")
            if password:
               opt.append("PASSWORD")
            if nickserv:
               opt.append("NICKSERV")
            if opt:
               text += " " + ", ".join(opt)
         else:
            channels = model.get_value(iter, 4)
            message = model.get_value(iter, 5)
            
            if mode == 3:
               delay = model.get_value(iter, 3)
               text = "+%d;%s; %s" % (delay, channels, message)
            elif mode == 5:
               offset = model.get_value(iter, 2)
               interval = model.get_value(iter, 3)
               text = "%d/%d;%s; %s" % (offset, interval, channels, message)
            else:
               text = channels + "; " + message
      else:
         text = ("Server", "Announce", "Timer", "On up", "On down")[mode / 2]

      cell.props.text = text


   @modifier
   def _on_new(self, mode, model, iter, dialog):
      if mode == 0:
         dialog(ServerDialog(), self._add_server)
      elif mode == 2:
         dialog(AnnounceMessageDialog("Add an IRC track announce message"),
                                                      self._add_announce)
      elif mode == 4:
         dialog(TimerMessageDialog("Add an IRC timed interval message"),
                                                      self._add_timer)
      elif mode in (6, 8):
         title = "Add an IRC radio stream up message" if mode == 6 \
            else "And an IRC radio stream down message"
         dialog(MessageDialog(title), self._add_message, mode)
      
    
   @modifier
   def _on_remove(self, mode, model, _iter, dialog):
      pass
      
   
   @modifier
   def _on_edit(self, mode, model, iter, dialog):
      if mode == 1:
         dialog(EditServerDialog(tuple(model[model.get_path(iter)])[2:13]),
                                                self._standard_edit, 2)
      if mode == 3:
         dialog(EditAnnounceMessageDialog("Edit IRC track announce message",
                              tuple(model[model.get_path(iter)])[3:6]),
                                                self._standard_edit, 3)
      if mode == 5:
         dialog(EditTimerMessageDialog("Edit IRC timed interval message",
                              tuple(model[model.get_path(iter)])[2:6]),
                                                self._standard_edit, 2)
      if mode in (7, 9):
         title = "Edit IRC radio stream up message" if mode == 7 \
            else "Edit IRC radio stream down message"
         dialog(EditMessageDialog(title, tuple(
            model[model.get_path(iter)])[4:6]), self._standard_edit, 4)
                                                

   def _standard_edit(self, d, model, iter, start):
      for i, each in enumerate(d.as_tuple(), start=start):
         model.set_value(iter, i, each)


   @highlight
   def _add_server(self, d, model, parent_iter):
      iter = model.append(parent_iter, (1, 1) + d.as_tuple() + ("", ))

      # Add the subelements.
      for i in xrange(2, 10, 2):
         model.append(iter, (i, 1, 0, 0) + ("", ) * 10)
         
      return iter

               
   @highlight
   def _add_announce(self, d, model, parent_iter):
      return model.append(parent_iter, (3, 1, 0) + d.as_tuple() + ("", ) * 8)


   @highlight
   def _add_timer(self, d, model, parent_iter):
      return model.append(parent_iter, (5, 1) + d.as_tuple() + ("", ) * 8)
      
   
   @highlight
   def _add_message(self, d, model, parent_iter, mode):
      return model.append(parent_iter, (mode + 1, 1, 0, 0) + d.as_tuple() + ("", ) * 8)
