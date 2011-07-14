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


import re
import json
from functools import wraps

import gtk
import pango

try:
   import irclib
except ImportError:
   irclib = None

from idjc.prelims import ProfileManager
from .gtkstuff import DefaultEntry
from .freefunctions import string_multireplace
from .ln_text import ln


pm = ProfileManager()



XChat_colour = {
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



class IRCEntry(gtk.Entry):
   """Specialised IRC text entry widget.
   
   Features pop-up menu and direct control character insertion.
   """
   
   
   _control_keytable = {107:u"\u0003", 98:u"\u0002", 117:u"\u001F", 111:u"\u000F"}

   def __init__(self, *args, **kwds):
      gtk.Entry.__init__(self, *args, **kwds)
      self.connect("key-press-event", self._on_key_press_event)
      self.connect("populate-popup", self._popup_menu_populate)


   def _on_key_press_event(self, entry, event, data=None):
      """Handle direct insertion of control characters."""


      if entry.im_context_filter_keypress(event):
         return True
         
      # Check for CTRL key modifier.
      if event.state & gtk.gdk.CONTROL_MASK:
         # Remove the effect of CAPS lock - works for letter keys only.
         keyval = event.keyval + (32 if event.state & gtk.gdk.LOCK_MASK else 0)
         try:
            replacement = self._control_keytable[keyval]
         except KeyError:
            pass
         else:
            entry.reset_im_context()
            cursor = entry.get_position()
            entry.insert_text(replacement, cursor)
            entry.set_position(cursor + 1)
            return True


   def _popup_menu_populate(self, entry, menu):
      menuitem = gtk.MenuItem(ln.insert_attribute_or_colour_code)
      menu.append(menuitem)
      submenu = gtk.Menu()
      menuitem.set_submenu(submenu)
      menuitem.show()
      
      def sub(pairs):
         for menutext, code in pairs:
            mi = gtk.MenuItem()
            l = gtk.Label()
            l.set_alignment(0.0, 0.5)
            l.set_markup(menutext)
            mi.add(l)
            l.show()
            mi.connect("activate", self._on_menu_item_activate, entry, code)
            submenu.append(mi)
            mi.show()

      sub(zip((ln.artist, ln.title, ln.album, ln.songname, ln.dj_name_popup,
                                 ln.description_popup, ln.listen_url_popup),
                                 (u"%r", u"%t", u"%l", u"%s", u"%n", u"%d", u"%u")))

      s = gtk.SeparatorMenuItem()
      submenu.append(s)
      s.show()
      
      sub(zip((ln.irc_bold, ln.irc_underline, ln.irc_normal), (u"\u0002", u"\u001F", u"\u000F")))
      
      for each in ("0-7", "8-15"):
         mi = gtk.MenuItem(" ".join(("Colours", each)))
         submenu.append(mi)
         cmenu = gtk.Menu()
         mi.set_submenu(cmenu)
         cmenu.show()
         lower, upper = [int(x) for x in each.split("-")]
         for i in xrange(lower, upper + 1):
            try:
               rgba = XChat_colour[i]
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
      entry.set_position(cursor + len(code))


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



class IRCView(gtk.TextView):
   """Viewer for IRC text."""
   

   matches = tuple((a, re.compile(b)) for a, b in (
      ("fgbg", "\x03[0-9]{1,2},[0-9]{1,2}"),
      ("fg",   "\x03[0-9]{1,2}(?!=,)"),
      ("bold", "\x02"),
      ("ul",   "\x1F"),
      ("norm", "\x0F"),
      ("text", "[^\x00-\x1F]*"),
      ))


   readable_equiv = (("%r", ln.artist_ircview), ("%t", ln.title_ircview),
      ("%l", ln.album_ircview), ("%s", ln.songname_ircview),
      ("%n", ln.dj_name_ircview), ("%d", ln.description_ircview),
      ("%u", ln.listen_url_ircview))


   def __init__(self):
      gtk.TextView.__init__(self)
      self.set_size_request(500, -1)
      self.set_wrap_mode(gtk.WRAP_CHAR)
      self.set_editable(False)
      self.set_cursor_visible(False)


   def set_text(self, text):
      text = string_multireplace(text, self.readable_equiv)
      
      b = self.get_buffer()
      b.remove_all_tags(b.get_start_iter(), b.get_end_iter())
      b.delete(b.get_start_iter(), b.get_end_iter())

      fg = bg = None
      bold = ul = False
      start = 0
      
      while start < len(text):
         for name, match in self.matches:
            rslt = match.match(text, start)
            if rslt is not None and rslt.group():
               if name == "bold":
                  bold = not bold

               elif name == "ul":
                  ul = not ul

               elif name == "fg":
                  try:
                     fg = rslt.group()[1:]
                  except IndexError:
                     fg = None

               elif name == "fgbg":
                  try:
                     fg, bg = rslt.group()[1:].split(",")
                  except IndexError:
                     fg = bg = None

               elif name == "norm":
                  bold = ul = False
                  fg = bg = None

               elif name == "text":
                  tag = b.create_tag()
                  p = tag.props
                  p.family = "monospace"
                  try:
                     p.foreground = self._colour_string(fg)
                     p.background = self._colour_string(bg)
                  except (TypeError, KeyError):
                     pass

                  if ul:
                     p.underline = pango.UNDERLINE_SINGLE
                  if bold:
                     p.weight = pango.WEIGHT_BOLD
                     
                  b.insert_with_tags(b.get_end_iter(), rslt.group(), tag)
               start = rslt.end()
               break               
         else:
            start += 1


   @staticmethod
   def _colour_string(code):
      return "#%000000X" % (XChat_colour[int(code)] >> 8)



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
      self.delete = gtk.Button(stock=gtk.STOCK_DELETE)
      bb.add(self.delete)



server_port_adj = gtk.Adjustment(6767.0, 0.0, 65535.0, 1.0, 10.0)



class ServerDialog(gtk.Dialog):
   """Data entry dialog for adding a new irc server."""
   
   
   def __init__(self, title="IRC server"):
      gtk.Dialog.__init__(self, title + " - IDJC" + pm.title_extra)

      self.network = gtk.Entry()
      self.network.set_width_chars(25)
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
      image.set_alignment(0.5, 0)
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
      ServerDialog.__init__(self)
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
   icon = gtk.STOCK_NEW

   def __init__(self, title=None):
      if title is None:
         title = self.title
      
      gtk.Dialog.__init__(self, title + " - IDJC" + pm.title_extra)

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
      
      sw = gtk.ScrolledWindow()
      sw.set_policy(gtk.POLICY_NEVER, gtk.POLICY_ALWAYS)
      irc_view = IRCView()
      sw.add(irc_view)
      vbox = gtk.VBox()
      vbox.set_spacing(5)
      vbox.pack_start(hbox1, False)
      vbox.pack_start(hbox2, False)
      vbox.pack_start(sw)
      
      self.hbox = gtk.HBox()
      self.hbox.set_border_width(16)
      self.hbox.set_spacing(5)
      self.image = gtk.image_new_from_stock(self.icon, gtk.ICON_SIZE_DIALOG)
      self.image.set_alignment(0.5, 0)
      self.hbox.pack_start(self.image, False, padding=20)
      self.hbox.pack_start(vbox)
      
      self.message.connect("changed", lambda w: irc_view.set_text(w.get_text()))
      
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
   icon = gtk.STOCK_EDIT

   def __init__(self, title, orig_data):
      MessageDialog.__init__(self, title)
      EditDialogMixin.__init__(self, orig_data)
      
      
   def from_tuple(self, orig_data):
      self.channels.set_text(orig_data[0])
      self.message.set_text(orig_data[1])



class AnnounceMessageDialog(MessageDialog):
   title = "IRC track announce"

   def __init__(self):
      MessageDialog.__init__(self)
      
      self.delay = gtk.SpinButton(message_delay_adj)
      self._pack((("Delay", self.delay), ))
      
      
   def as_tuple(self):
      return (self.delay.get_value(), ) + MessageDialog.as_tuple(self)



class EditAnnounceMessageDialog(AnnounceMessageDialog, EditDialogMixin):
   icon = gtk.STOCK_EDIT
   
   def __init__(self, orig_data):
      AnnounceMessageDialog.__init__(self)
      EditDialogMixin.__init__(self, orig_data)
      
      
   def from_tuple(self, orig_data):
      return (self.delay.set_value(orig_data[0]),
              self.channels.set_text(orig_data[1]),
              self.message.set_text(orig_data[2]))

   

class TimerMessageDialog(MessageDialog):
   title = "IRC timed message"

   def __init__(self):
      MessageDialog.__init__(self)
      
      self.offset = gtk.SpinButton(message_offset_adj)
      self.interval = gtk.SpinButton(message_interval_adj)
      self._pack((("Offset", self.offset), ("Interval", self.interval)))
      
   def as_tuple(self):
      return (self.offset.get_value(), self.interval.get_value()
                                    ) + MessageDialog.as_tuple(self)



class EditTimerMessageDialog(TimerMessageDialog, EditDialogMixin):
   icon = gtk.STOCK_EDIT
   
   def __init__(self, orig_data):
      TimerMessageDialog.__init__(self)
      EditDialogMixin.__init__(self, orig_data)
      
      
   def from_tuple(self, orig_data):
      return (self.offset.set_value(orig_data[0]),
              self.interval.set_value(orig_data[1]),
              self.channels.set_text(orig_data[2]),
              self.message.set_text(orig_data[3]))



def iteminfo(f):
   """IRCPane function decorator for new/edit callbacks."""

   
   @wraps(f)
   def inner(self, widget):
      model, _iter = self._treeview.get_selection().get_selected()
         
      if _iter is not None:
         def dialog(d, cb, *args, **kwds):
            cancel = gtk.Button(gtk.STOCK_CANCEL)
            d.ok = gtk.Button(gtk.STOCK_OK)
            bb = d.get_action_area()
            for each in (cancel, d.ok):
               each.set_use_stock(True)
               each.connect_after("clicked", lambda w: d.destroy())
               bb.add(each)

            d.set_modal(True)
            d.set_transient_for(self.get_toplevel())
            d.ok.connect("clicked", lambda w: cb(d, model, _iter, *args, **kwds))
            
            if hasattr(d, "delete"):
               def delete(w):
                  iter_parent = model.iter_parent(_iter)
                  self._treeview.get_selection().select_iter(iter_parent)
                  model.remove(_iter)
                  
               d.delete.connect("clicked", delete)
               d.delete.connect_after("clicked", lambda w: d.destroy())
            
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
   
   
   
class IRCTreeView(gtk.TreeView):
   def __init__(self, model=None):
      gtk.TreeView.__init__(self, model)
      self.set_headers_visible(False)
      self.set_enable_tree_lines(True)
      self.connect("query-tooltip", self._on_query_tooltip)
      self.set_has_tooltip(True)
      self.tooltip_coords = (0, 0)
      
   
   def _on_query_tooltip(self, tv, x, y, kb_mode, tooltip):
      if (x, y) != self.tooltip_coords:
         self.tooltip_coords = (x, y)
      elif None not in (x, y):
         path = tv.get_path_at_pos(*tv.convert_widget_to_bin_window_coords(x, y))
         if path is not None:
            model = tv.get_model()
            iter = model.get_iter(path[0])
            mode = model.get_value(iter, 0)
            if mode in (3, 5, 7, 9):
               message = model.get_value(iter, 5)
               irc_view = IRCView()
               irc_view.set_text(message)
               tooltip.set_custom(irc_view)
               return True



class IRCPane(gtk.VBox):
   def __init__(self):
      gtk.VBox.__init__(self)
      self.set_border_width(8)
      self.set_spacing(3)
      self._data_format = (int,) * 4 + (str,) * 10
      self._treestore = gtk.TreeStore(*self._data_format)
      self._treestore.append(None, (0, 1, 0, 0) + ("", ) * 10)
      self._treeview = IRCTreeView(self._treestore)
      
      col = gtk.TreeViewColumn()
      toggle = gtk.CellRendererToggle()
      toggle.props.sensitive = False
      col.pack_start(toggle, False)
      col.add_attribute(toggle, "active", 1)
      
      crt = gtk.CellRendererText()
      crt.props.ellipsize = pango.ELLIPSIZE_END
      col.pack_start(crt, True)
      col.set_cell_data_func(crt, self._cell_data_func)
      
      self._treeview.append_column(col)
      
      sw = gtk.ScrolledWindow()
      sw.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
      sw.add(self._treeview)
      
      bb = gtk.HButtonBox()
      bb.set_spacing(6)
      bb.set_layout(gtk.BUTTONBOX_END)
      edit = gtk.Button(gtk.STOCK_EDIT)
      new = gtk.Button(gtk.STOCK_NEW)
      for b, c in zip((edit, new), ("edit", "new")):
         b.set_use_stock(True)
         b.connect("clicked", getattr(self, "_on_" + c))
         bb.add(b)

      toggle_button = gtk.Button("_Toggle")
      toggle_button.connect("clicked", self._on_toggle)
      bb.add(toggle_button)
      bb.set_child_secondary(toggle_button, True)

      selection = self._treeview.get_selection()
      selection.connect("changed", self._on_selection_changed, edit, new)
      selection.select_path(0)

      if irclib is not None:
         self.pack_start(sw)
         self.pack_start(bb, False)
      else:
         self.set_sensitive(False)
         label = gtk.Label("This feature requires the installation of python-irclib.")
         self.add(label)

      self.show_all()


   def _m_signature(self):
      """The client data storage signature. 
      
      Used to crosscheck with that of the saved data to test for usability.
      """

      return [x.__name__ for x in self._data_format]


   def marshall(self):
      store = [self._m_signature()]
      self._treestore.foreach(self._m_read, store)
      return json.dumps(store)


   def _m_read(self, model, path, iter, store):
      line = tuple(model[path])
      store.append((path, line))


   def unmarshall(self, data):
      store = json.loads(data)
      if store.pop(0) != self._m_signature():
         print "mismatch"
         return
         
      selection = self._treeview.get_selection()
      selection.handler_block_by_func(self._on_selection_changed)
      self._treestore.clear()
      for path, row in store:
         pos = path.pop()
         pi = self._treestore.get_iter(tuple(path)) if path else None
         self._treestore.insert(pi, pos, row)
      self._treeview.expand_all()
      selection.handler_unblock_by_func(self._on_selection_changed)
      selection.select_path(0)


   def _on_selection_changed(self, selection, edit, new):
      model, iter = selection.get_selected()
      mode = model.get_value(iter, 0)
      
      edit.set_sensitive(mode % 2)
      new.set_sensitive(not mode % 2)
      

   def _on_toggle(self, widget):
      model, iter = self._treeview.get_selection().get_selected()
      model.set_value(iter, 1, not model.get_value(iter, 1))


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


   @iteminfo
   def _on_new(self, mode, model, iter, dialog):
      if mode == 0:
         dialog(ServerDialog(), self._add_server)
      elif mode == 2:
         dialog(AnnounceMessageDialog(), self._add_announce)
      elif mode == 4:
         dialog(TimerMessageDialog(), self._add_timer)
      elif mode in (6, 8):
         title = "IRC stream up message" if mode == 6 \
            else "IRC stream down message"
         dialog(MessageDialog(title), self._add_message, mode)
    
   
   @iteminfo
   def _on_edit(self, mode, model, iter, dialog):
      if mode == 1:
         dialog(EditServerDialog(tuple(model[model.get_path(iter)])[2:13]),
                                                self._standard_edit, 2)
      if mode == 3:
         dialog(EditAnnounceMessageDialog(
                              tuple(model[model.get_path(iter)])[3:6]),
                                                self._standard_edit, 3)
      if mode == 5:
         dialog(EditTimerMessageDialog(
                              tuple(model[model.get_path(iter)])[2:6]),
                                                self._standard_edit, 2)
      if mode in (7, 9):
         title = "IRC stream up message" if mode == 7 \
            else "IRC stream down message"
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
