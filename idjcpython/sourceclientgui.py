#   sourceclientgui.py: new for version 0.7 this provides the graphical
#   user interface for the new improved streaming module
#   Copyright (C) 2007 Stephen Fairchild (s-fairchild@users.sourceforge.net)
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

__all__ = ['SourceClientGui']

import pygtk
pygtk.require('2.0')
import gtk
import gobject

import os, time, fcntl, subprocess, urllib, urllib2, base64
import xml.dom.minidom as mdom
import xml.etree.ElementTree

import idjc_config
from idjc_config import *
from ln_text import ln
from IDJCfree import int_object, threadslock, DefaultEntry
from IDJCservdialog import *
from threading import Thread

try:
   from collections import namedtuple
except:
   from nt import namedtuple

ENCODER_START=1; ENCODER_STOP=0                                 # start_stop_encoder constants

LISTFORMAT = (("check_stats", bool), ("server_type", int), ("host", str), ("port", int), ("mount", str), ("listeners", int), ("login", str), ("password", str))
ListLine = namedtuple("ListLine", " ".join([x[0] for x in LISTFORMAT]))
BLANK_LISTLINE = ListLine(1, 0, "", 8000, "", -1, "", "")

class ModuleFrame(gtk.Frame):
   def __init__(self, frametext = None):
      gtk.Frame.__init__(self, frametext)
      gtk.Frame.set_shadow_type(self, gtk.SHADOW_ETCHED_OUT)
      self.vbox = gtk.VBox()
      self.add(self.vbox)
      self.vbox.show()

class CategoryFrame(gtk.Frame):
   def __init__(self, frametext = None):
      gtk.Frame.__init__(self, frametext)
      gtk.Frame.set_shadow_type(self, gtk.SHADOW_IN)
 
class SubcategoryFrame(gtk.Frame):
   def __init__(self, frametext = None):
      gtk.Frame.__init__(self, frametext)
      gtk.Frame.set_shadow_type(self, gtk.SHADOW_ETCHED_IN)

class ConnectionDialog(gtk.Dialog):
   """Create new data for or edit an item in the connection table.
   
   When an item is selected in the TreeView, will edit, else add.
   """
   server_types = (ln.label_icecast_master, ln.label_shoutcast_master,
                  ln.label_icecast_relay, ln.label_shoutcast_relay)

   def __init__(self, parent_window, tree_selection):
      gtk.Dialog.__init__(self, ln.connection_dialog_title_add, 
         parent_window, gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
         (gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT, gtk.STOCK_OK, gtk.RESPONSE_ACCEPT))
      model, iter = tree_selection.get_selected()
         
      # Configuration from existing server data.
      #
      cap_master = True
      preselect = 0
      data = BLANK_LISTLINE
      try:
         first = ListLine._make(model[0])
      except IndexError:
         pass  # Defaults are fine. Server table currently empty.
      else:
         if iter:
            # In editing mode.
            self.set_title(ln.connection_dialog_title_edit)
            index = model.get_path(iter)[0]
            data = ListLine._make(model[index])
            preselect = data.server_type
            if index and first.server_type < 2:
               # Editing non first line where a master server is configured.
               cap_master = False
         else:
            # In adding additional server mode.
            if first.server_type < 2:
               cap_master = False
               preselect = first.server_type + 2

      # Widgets
      #
      liststore = gtk.ListStore(int, str, int)
      for i, (l, t) in enumerate(zip(self.server_types, (cap_master, cap_master, True, True))):
         liststore.append((i, l, t))
      self.servertype = gtk.ComboBox(liststore)
      icon_renderer = CellRendererXCast()
      text_renderer = gtk.CellRendererText()
      self.servertype.pack_start(icon_renderer, False)
      self.servertype.pack_start(text_renderer, True)
      self.servertype.set_attributes(icon_renderer, servertype=0, sensitive=2)
      self.servertype.set_attributes(text_renderer, text=1, sensitive=2)
      self.servertype.set_model(liststore)
      
      self.hostname = DefaultEntry("localhost")
      adj = gtk.Adjustment(8000.0, 0.0, 65535.0, 1.0, 10.0)
      self.portnumber = gtk.SpinButton(adj, 1.0, 0)
      self.mountpoint = DefaultEntry("/listen")
      self.loginname = DefaultEntry("source")
      self.password = DefaultEntry("changeme")
      self.password.set_visibility(False)
      self.stats = gtk.CheckButton(ln.server_dialog_stats)
      
      # Layout
      #
      self.set_border_width(5)
      hbox = gtk.HBox(spacing = 20)
      hbox.set_border_width(15)
      icon = gtk.image_new_from_stock(gtk.STOCK_NETWORK, gtk.ICON_SIZE_DIALOG)
      hbox.pack_start(icon)
      col = gtk.VBox(homogeneous = True, spacing = 4)
      hbox.pack_start(col)
      sg = gtk.SizeGroup(gtk.SIZE_GROUP_HORIZONTAL)
      for text, widget in zip(
            (ln.servertype, ln.hostname2, ln.portnumber, 
            ln.mountpoint, ln.loginname, ln.password), 
            (self.servertype, self.hostname, self.portnumber, 
            self.mountpoint, self.loginname, self.password)):
         row = gtk.HBox()
         label = gtk.Label(text)
         label.set_alignment(1.0, 0.5)
         row.pack_start(label, False)
         row.pack_start(widget)
         sg.add_widget(label)
         col.pack_start(row)
      col.pack_start(self.stats, False)
      self.get_content_area().pack_start(hbox)
      self.hostname.set_width_chars(30)
      hbox.show_all()

      # Signals
      #
      self.connect("response", self._on_response, tree_selection, model, iter)
      self.servertype.connect("changed", self._on_servertype_changed)

      # Data fill
      #
      self.servertype.set_active(preselect)
      self.hostname.set_text(data.host)
      self.portnumber.set_value(data.port)
      self.mountpoint.set_text(data.mount)
      self.loginname.set_text(data.login)
      self.password.set_text(data.password)
      self.stats.set_active(data.check_stats)
      
   @staticmethod
   def _on_response(self, response_id, tree_selection, model, iter):
      if response_id == gtk.RESPONSE_ACCEPT:
         for entry in (self.hostname, self.mountpoint, self.loginname, self.password):
            entry.set_text(entry.get_text().strip())
         self.hostname.set_text(self.hostname.get_text().split("://")[-1].strip())
         self.mountpoint.set_text("/" + self.mountpoint.get_text().lstrip("/"))

         data = ListLine(check_stats=self.stats.get_active(),
                         server_type=self.servertype.get_active(),
                         host=self.hostname.get_text(),
                         port=int(self.portnumber.get_value()),
                         mount=self.mountpoint.get_text(),
                         listeners=-1,
                         login=self.loginname.get_text(),
                         password=self.password.get_text())

         if self.servertype.get_active() < 2:
            if iter:
               model.remove(iter)
            new_iter = model.insert(0, data)
         else:
            if iter:
               new_iter = model.insert_after(iter, data)
               model.remove(iter)
            else:
               new_iter = model.append(data)
         tree_selection.select_path(model.get_path(new_iter))
         tree_selection.get_tree_view().scroll_to_cell(model.get_path(new_iter))
      self.destroy()
      
   def _on_servertype_changed(self, servertype):
      sens = not (servertype.get_active() & 1)
      self.mountpoint.set_sensitive(sens)
      self.loginname.set_sensitive(sens)

class StatsThread(Thread):
   def __init__(self, d):
      Thread.__init__(self)
      self.is_shoutcast = d["server_type"] % 2
      self.host = d["host"]
      self.port = d["port"]
      self.mount = d["mount"]
      if self.is_shoutcast:
         self.login = "admin"
      else:
         self.login = d["login"]
      self.passwd = d["password"]
      self.listeners = -2         # preset error code for failed/timeout
      self.url = "http://%s:%d%s" % (self.host, self.port, self.mount)
   def run(self):
      class BadXML(ValueError):
         pass
      
      hostport = "%s:%d" % (self.host, self.port)
      if self.is_shoutcast:
         stats_url = "http://%s/admin.cgi?mode=viewxml" % hostport
         realm = "Shoutcast Server"
      else:
         stats_url = "http://%s/admin/listclients?mount=%s" % (hostport, self.mount)
         realm = "Icecast2 Server"
      auth_handler = urllib2.HTTPBasicAuthHandler()
      auth_handler.add_password(realm, hostport, self.login, self.passwd)
      opener = urllib2.build_opener(auth_handler)
      opener.addheaders = [('User-agent', 'Mozilla/5.0')]
      
      try:
         f = opener.open(stats_url)
         xmlfeed = f.read()
      except:
         print "failed to get server stats for", self.url
         return
      f.close()
      try:
         dom = mdom.parseString(xmlfeed)
      except:
         print "failed to parse server stats for", self.url
         return
      
      try:
         if self.is_shoutcast:
            if dom.documentElement.tagName == u'SHOUTCASTSERVER':
               shoutcastserver = dom.documentElement
            else:
               raise BadXML
            currentlisteners = shoutcastserver.getElementsByTagName('CURRENTLISTENERS')
            try:
               self.listeners = int(currentlisteners[0].firstChild.wholeText.strip())
            except:
               raise BadXML
         else:
            if dom.documentElement.tagName == u'icestats':
               icestats = dom.documentElement
            else:
               raise BadXML
            sources = icestats.getElementsByTagName('source')
            for source in sources:
               mount = source.getAttribute('mount')
               if stats_url.endswith(mount):
                  listeners = source.getElementsByTagName('Listeners')
                  try:
                     self.listeners = int(listeners[0].firstChild.wholeText.strip())
                     break
                  except:
                     raise BadXML
            else:
               raise BadXML
      except BadXML:
         print "Unexpected data in server stats XML file"
      dom.unlink()
      print "server", self.url, "has", self.listeners, "listeners"

class ActionTimer(object):
   def run(self):
      if self.n == 0:
         self.first()
      self.n += 1
      if self.n == self.ticks:
         self.n = 0
         self.last()
   def __init__(self, ticks, first, last):
      assert(ticks)
      self.ticks = ticks
      self.n = 0
      self.first = first
      self.last = last

class CellRendererXCast(gtk.CellRendererText):
   icons = ("<span foreground='#0077FF'>&#x25A0;</span>",
            "<span foreground='orange'>&#x25A0;</span>",
            "<span foreground='#0077FF'>&#x25B4;</span>",
            "<span foreground='orange'>&#x25B4;</span>")
            
   ins_icons = ("<span foreground='#CCCCCC'>&#x25A0;</span>",
            "<span foreground='#CCCCCC'>&#x25A0;</span>",
            "<span foreground='#CCCCCC'>&#x25B4;</span>",
            "<span foreground='#CCCCCC'>&#x25B4;</span>")

   __gproperties__ = {
      'servertype' : (gobject.TYPE_INT,
                      'kind of server',
                      'indication by number of the server in use',
                      0, 3, 0, gobject.PARAM_READWRITE),
      'sensitive' : (gobject.TYPE_BOOLEAN,
                     'sensitivity flag',
                     'indication of selectability',
                      1, gobject.PARAM_READWRITE)
      }
   
   def __init__(self):
      gtk.CellRendererText.__init__(self)
      self._servertype = 0
      self._sensitive = 1
      self.props.xalign = 0.5
      self.props.family = "monospace"

   def do_get_property(self, property):
      if property.name == 'servertype':
         return self._servertype
      elif property.name == 'sensitive':
         return self._sensitive
      else:
         raise AttributeError
         
   def do_set_property(self, property, value):
      if property.name == 'servertype':
         self._servertype = value
      elif property.name == 'sensitive':
         self._sensitive = value
      else:
         raise AttributeError

      if self._sensitive:
         self.props.markup = self.icons[self._servertype]
      else:
         self.props.markup = self.ins_icons[self._servertype]


class ConnectionPane(gtk.VBox):
   def get_master_server_type(self):
      try:
         s_type = ListLine(*self.liststore[0]).server_type
      except IndexError:
         return 0
      return 0 if s_type >= 2 else s_type + 1

   def set_button(self, tab):
      if self.get_master_server_type():
         config = ListLine(*self.liststore[0])
         text = "{0.host}:{0.port}{0.mount}".format(config)
         tab.server_connect_label.set_text(text)
      else:
         tab.server_connect_label.set_text(ln.connect_disconnect_nonconfig)
   
   def individual_listeners_toggle_cb(self, cell, path):
      self.liststore[path][0] = not self.liststore[path][0]

   def listeners_renderer_cb(self, column, cell, model, iter):
      listeners = model.get_value(iter, 5)
      if listeners == -1:
         cell.set_property("text", "")
         cell.set_property("xalign", 0.5)
      elif listeners == -2:
         cell.set_property("text", u"\u2049")
         cell.set_property("xalign", 0.5)
      else:
         cell.set_property("text", listeners)
         cell.set_property("xalign", 1.0)

   def master_is_set(self):
      return bool(self.get_master_server_type())

   def streaming_set(self, val):
      self._streaming_set = val

   def streaming_is_set(self):
      return self._streaming_set

   def row_to_dict(self, rownum):
      """ obtain a dictionary of server data for a specified row """
            
      return ListLine._make(self.liststore[rownum])._asdict()
   
   def dict_to_row(self, _dict):
      """ append a row of server data from a dictionary """
      
      _dict["listeners"] = -1
      row = ListLine(**_dict)
      t = row.server_type
      if t < 2:                           # check if first line contains master server info
         self.liststore.insert(0, row)
      else:
         self.liststore.append(row)
      return

   def saver(self):
      server = []
      template = ("<%s dtype=\"int\">%d</%s>", "<%s dtype=\"str\">%s</%s>")
      for i in range(len(self.liststore)):
         s = self.row_to_dict(i)
         del s["listeners"]
         s["password"] = base64.encodestring(s["password"])
         d = []
         for key, value in s.iteritems():
            if type(value) == str:
               t = template[1]
               value = urllib.quote(value)
            else:
               t = template[0]
            d.append(t % (key, value, key))
         server.append("".join(("<server>", "".join(d), "</server>")))
      return "<connections>%s</connections>" % "".join(server)
   
   def loader(self, xmldata):
      def get_child_text(nodelist):
         t = []
         for node in nodelist:
            if node.nodeType == node.TEXT_NODE:
               t.append(node.data)
         return "".join(t)
      if not xmldata:
         return
      try:
         try:
            dom = mdom.parseString(xmldata)
         except:
            print "ConnectionPane.loader: failed to parse xml data...\n", xmldata
            raise
         assert(dom.documentElement.tagName == "connections")
         for server in dom.getElementsByTagName("server"):
            d = {}
            for node in server.childNodes:
               key = str(node.tagName)
               dtype = node.getAttribute("dtype")
               raw = get_child_text(node.childNodes)
               if dtype == "str":
                  value = urllib.unquote(raw)
               elif dtype == "int":
                  value = int(raw)
               else:
                  raise ValueError("ConnectionPane.loader: dtype (%s) is unhandled" % dtype)
               d[key] = value
            try:
               d["password"] = base64.decodestring(d["password"])
            except KeyError:
               pass
            self.dict_to_row(d)
      except Exception, e:
         print e
      self.treeview.get_selection().select_path(0)
         
   def stats_commence(self):
      self.stats_rows = []
      getstats = self.stats_always.get_active() or (self.stats_ifconnected.get_active() and self.streaming_is_set())
      for i, row in enumerate(self.liststore):
         if row[0] and getstats:
            d = self.row_to_dict(i)
            if d["server_type"] == 1:
               ap = self.tab.admin_password_entry.get_text().strip()
               if ap:
                  d["password"] = ap
            stats_thread = StatsThread(d)
            stats_thread.start()
            ref = gtk.TreeRowReference(self.liststore, i)
            self.stats_rows.append((ref, stats_thread))
         else:
            row[5] = -1       # sets listeners text to 'unknown'

   def stats_collate(self):
      count = 0
      for ref, thread in self.stats_rows:
         if ref.valid() == False:
            print "stats_collate:", thread.url, "invalidated by its removal from the stats list"
            continue
         row = ref.get_model()[ref.get_path()[0]]
         row[5] = thread.listeners
         if thread.listeners > 0:
            count += thread.listeners
      self.listeners_display.set_text(str(count))
      self.listeners = count

   def on_dialog_destroy(self, dialog, tree_selection, old_iter):
      model, iter = tree_selection.get_selected()
      if iter is None and old_iter is not None:
         tree_selection.select_iter(old_iter)

   def on_new_clicked(self, button, tree_selection):
      old_iter = tree_selection.get_selected()[1]
      tree_selection.unselect_all()
      self.connection_dialog = ConnectionDialog(self.tab.scg.window, tree_selection)
      self.connection_dialog.connect("destroy", self.on_dialog_destroy, tree_selection, old_iter)
      self.connection_dialog.show()
      
   def on_edit_clicked(self, button, tree_selection):
      model, iter = tree_selection.get_selected()
      if iter:
         self.connection_dialog = ConnectionDialog(self.tab.scg.window, tree_selection)
         self.connection_dialog.show()
      else:
         print "nothing selected for edit"
   
   def on_remove_clicked(self, button, tree_selection):
      model, iter = tree_selection.get_selected()
      if iter:
         if model.remove(iter):
            tree_selection.select_iter(iter)
      else:
         print "nothing selected for removal"

   def on_keypress(self, widget, event):
      if gtk.gdk.keyval_name(event.keyval) == "Delete":
         self.remove.clicked()

   def on_selection_changed(self, tree_selection):
      sens = tree_selection.get_selected()[1] is not None
      for button in self.require_selection:
         button.set_sensitive(sens)

   def __init__(self, set_tip, tab):
      self.tab = tab
      gtk.VBox.__init__(self)
      self.streaming_set(False)
      vbox = gtk.VBox()
      vbox.set_border_width(6)
      vbox.set_spacing(6)
      self.add(vbox)
      vbox.show()
      scrolled = gtk.ScrolledWindow()
      scrolled.set_shadow_type(gtk.SHADOW_ETCHED_IN)
      scrolled.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_ALWAYS)
      vbox.pack_start(scrolled, True)
      scrolled.show()
      self.liststore = gtk.ListStore(*[x[1] for x in LISTFORMAT])
      self.liststore.connect("row-deleted", lambda x, y: self.set_button(tab))
      self.liststore.connect("row-inserted", lambda x, y, z: self.set_button(tab))
      self.set_button(tab)
      self.treeview = gtk.TreeView(self.liststore)
      set_tip(self.treeview, ln.connections_table_tip)
      self.treeview.set_enable_search(False)
      self.treeview.connect("key-press-event", self.on_keypress)

      rend_type = CellRendererXCast()
      rend_type.set_property("xalign", 0.5) 
      col_type = gtk.TreeViewColumn("", rend_type, servertype = 1)
      col_type.set_sizing = gtk.TREE_VIEW_COLUMN_AUTOSIZE
      col_type.set_alignment(0.5)
      self.treeview.append_column(col_type)
      text_cell_rend = gtk.CellRendererText()
      text_cell_rend.set_property("ellipsize", pango.ELLIPSIZE_END)
      col_host = gtk.TreeViewColumn(ln.conn_col_host, text_cell_rend, text=2)
      col_host.set_sizing = gtk.TREE_VIEW_COLUMN_FIXED
      col_host.set_expand(True)
      self.treeview.append_column(col_host)
      rend_port = gtk.CellRendererText()
      rend_port.set_property("xalign", 1.0)
      col_port = gtk.TreeViewColumn(ln.conn_col_port, rend_port, text = 3)
      col_port.set_sizing = gtk.TREE_VIEW_COLUMN_AUTOSIZE
      col_port.set_alignment(0.5)
      self.treeview.append_column(col_port)
      col_mount = gtk.TreeViewColumn(ln.conn_col_mount, text_cell_rend, text=4)
      col_mount.set_sizing = gtk.TREE_VIEW_COLUMN_AUTOSIZE
      self.treeview.append_column(col_mount)
      
      rend_enabled = gtk.CellRendererToggle()
      rend_enabled.connect("toggled", self.individual_listeners_toggle_cb)
      rend_listeners = gtk.CellRendererText()
      col_listeners = gtk.TreeViewColumn(ln.conn_col_listeners)
      col_listeners.set_sizing = gtk.TREE_VIEW_COLUMN_AUTOSIZE
      col_listeners.pack_start(rend_enabled, False)
      col_listeners.pack_start(rend_listeners)
      col_listeners.add_attribute(rend_enabled, "active", 0)
      col_listeners.set_cell_data_func(rend_listeners, self.listeners_renderer_cb)
      self.treeview.append_column(col_listeners)
      scrolled.add(self.treeview)
      self.treeview.show()

      hbox = gtk.HBox()
      
      self.listener_count_button = gtk.Button()
      ihbox = gtk.HBox()
      set_tip(ihbox, ln.listeners_total_tip)
      pixbuf = gtk.gdk.pixbuf_new_from_file_at_size(pkgdatadir + "listenerphones" + gfext, 20, 16)
      image = gtk.image_new_from_pixbuf(pixbuf)
      ihbox.pack_start(image, False, False, 0)
      image.show()
      frame = gtk.Frame()
      frame.set_border_width(0)
      ihbox.pack_start(frame, True, True, 0)
      frame.show()
      ihbox.show()
      self.listeners_display = gtk.Label("0")
      self.listeners_display.set_alignment(1.0, 0.5)
      self.listeners_display.set_width_chars(6)
      self.listeners_display.set_padding(3, 0)
      frame.add(self.listeners_display)
      self.listeners_display.show()
      self.listener_count_button.add(ihbox)
      hbox.pack_start(self.listener_count_button, False)
      
      lcmenu = gtk.Menu()
      self.listener_count_button.connect("button-press-event",
         lambda w, e: lcmenu.popup(None, None, None, e.button, e.time))
      lc_stats = gtk.MenuItem("Update")
      lcmenu.append(lc_stats)
      lcsubmenu = gtk.Menu()
      lc_stats.set_submenu(lcsubmenu)
      self.stats_never = gtk.RadioMenuItem(None, ln.get_stats_never)
      self.stats_never.connect("toggled", lambda w: ihbox.set_sensitive(not w.get_active()))
      self.stats_always  = gtk.RadioMenuItem(self.stats_never, ln.get_stats_always)
      self.stats_ifconnected = gtk.RadioMenuItem(self.stats_never, ln.get_stats_ifconnected)
      self.stats_ifconnected.set_active(True)
      lcsubmenu.append(self.stats_never)
      lcsubmenu.append(self.stats_always)
      lcsubmenu.append(self.stats_ifconnected)
      lcmenu.show_all()
      
      bbox = gtk.HButtonBox()
      bbox.set_spacing(8)
      bbox.set_layout(gtk.BUTTONBOX_END)
      new = gtk.Button("New")
      self.remove = gtk.Button("Remove")
      edit = gtk.Button("Edit")
      bbox.add(new)
      bbox.add(self.remove)
      bbox.add(edit)
      self.require_selection = (edit, self.remove)
      selection = self.treeview.get_selection()
      selection.connect("changed", self.on_selection_changed)
      selection.emit("changed")
      new.connect("clicked", self.on_new_clicked, selection)
      edit.connect("clicked", self.on_edit_clicked, selection)
      self.remove.connect("clicked", self.on_remove_clicked, selection)
      self.require_selection = (self.remove, edit)
      hbox.pack_start(bbox)
      vbox.pack_start(hbox, False)
      hbox.show_all()
      
      """
      sep = gtk.HSeparator()
      vbox.pack_start(sep, False, False, 0)
      sep.show()
      hbox = gtk.HBox()
      hbox.set_spacing(6)
      label = gtk.Label(ln.get_stats)
      hbox.pack_start(label, False, False, 0)
      label.show()
      """
      #self.stats_never = gtk.RadioButton(None, ln.get_stats_never)
      """
      hbox.pack_start(self.stats_never, False, False, 0)
      self.stats_never.show()
      """
      #self.stats_always = gtk.RadioButton(self.stats_never, ln.get_stats_always)
      """
      hbox.pack_start(self.stats_always, False, False, 0)
      self.stats_always.show()
      """
      #self.stats_ifconnected = gtk.RadioButton(self.stats_never, ln.get_stats_ifconnected)
      """
      self.stats_ifconnected.set_active(True)
      hbox.pack_start(self.stats_ifconnected, False, False, 0)
      self.stats_ifconnected.show()
      
      vbox.pack_start(hbox, False, False, 0)
      hbox.pack_start(ihbox, True, True, 0)
      hbox.show()
      """
      
      self.timer = ActionTimer(40, self.stats_commence, self.stats_collate)

class TimeEntry(gtk.HBox):              # A 24-hour-time entry widget with a checkbutton
   def time_valid(self):
      return self.seconds_past_midnight >= 0
   def get_seconds_past_midnight(self):
      return self.seconds_past_midnight
   def set_active(self, boolean):
      self.check.set_active(boolean and True or False)
   def get_active(self):
      return self.check.get_active() and self.time_valid
   def __entry_activate(self, widget):
      boolean = widget.get_active()
      self.entry.set_sensitive(boolean)
      if boolean:
         self.entry.grab_focus()
   def __key_validator(self, widget, event):
      if event.keyval < 128:
         if event.string == ":":
            return False
         if event.string < "0" or event.string > "9":
            return True
   def __time_updater(self, widget):
      text = widget.get_text()
      if len(text) == 5 and text[2] == ":":
         try:
            hours = int(text[:2])
            minutes = int(text[3:])
         except:
            self.seconds_past_midnight = -1
         else:
            if hours >= 0 and hours <=23 and minutes >= 0 and minutes <= 59:
               self.seconds_past_midnight = hours * 3600 + minutes * 60
            else:
               self.seconds_past_midnight = -1
      else:
         self.seconds_past_midnight = -1
   def __init__(self, labeltext):
      gtk.HBox.__init__(self)
      self.set_spacing(5)
      self.check = gtk.CheckButton(labeltext)
      self.check.connect("toggled", self.__entry_activate)
      self.pack_start(self.check, False)
      self.check.show()
      self.entry = gtk.Entry(5)
      self.entry.set_sensitive(False)
      self.entry.set_width_chars(5)
      self.entry.set_text("00:00")
      self.entry.connect("key-press-event", self.__key_validator)
      self.entry.connect("changed", self.__time_updater)
      self.pack_start(self.entry, False)
      self.entry.show()
      self.seconds_past_midnight = -1

class AutoAction(gtk.HBox):                     # widget consiting of a check button and several radio buttons
   def activate(self):                          # radio buttons linked to actions to be performed on the activate method
      if self.get_active():                     # all radio buttons exist in the same radio group so only one action is
         for radio, action in self.action_lookup:       # performed
            if radio.get_active():
               action()
   def get_active(self):
      return self.check_button.get_active()
   def set_active(self, boolean):
      self.check_button.set_active(boolean)
   def get_radio_index(self):
      return self.radio_active
   def set_radio_index(self, value):
      try:
         self.action_lookup[value][0].clicked()
      except:
         try:
            self.action_lookup[0][0].clicked()
         except:
            pass
   def __set_sensitive(self, widget):
      boolean = widget.get_active()
      for radio, action in self.action_lookup:
         radio.set_sensitive(boolean)
   def __handle_radioclick(self, widget, which):
      if widget.get_active():
         self.radio_active = which
   def __init__(self, labeltext, names_actions):
      gtk.HBox.__init__(self)
      self.radio_active = 0
      self.check_button = gtk.CheckButton(labeltext)
      self.set_spacing(4)
      self.pack_start(self.check_button, False, False, 0)
      self.check_button.show()
      lastradio = None
      self.action_lookup = []
      for index, (name, action) in enumerate(names_actions):
         radio = gtk.RadioButton(lastradio, name)
         radio.connect("clicked", self.__handle_radioclick, index)
         lastradio = radio
         radio.set_sensitive(False)
         self.check_button.connect("toggled", self.__set_sensitive)
         self.pack_start(radio, False, False, 0)
         radio.show()
         self.action_lookup.append((radio, action))

class FramedSpin(gtk.Frame):
   """A framed spin button that can be disabled"""
   def get_value(self):
      if self.check.get_active():
         return self.spin.get_value()
      else:
         return -1
   def get_cooked_value(self):
      if self.check.get_active():
         return self.spin.get_value() * self.adj_basis.get_value() / 100
      else:
         return -1
   def set_value(self, new_value):
      self.spin.set_value(new_value)
   def cb_toggled(self, widget):
      self.spin.set_sensitive(widget.get_active())
   def __init__(self, text, adj, adj_basis):
      self.adj_basis = adj_basis
      gtk.Frame.__init__(self)
      self.check = gtk.CheckButton(text)
      hbox = gtk.HBox()
      hbox.pack_start(self.check, False, False, 2)
      self.check.show()
      self.set_label_widget(hbox)
      hbox.show()
      vbox = gtk.VBox()
      vbox.set_border_width(2)
      self.spin = gtk.SpinButton(adj)
      vbox.add(self.spin)
      self.spin.show()
      self.spin.set_sensitive(False)
      self.add(vbox)
      vbox.show()
      self.check.connect("toggled", self.cb_toggled)

class SimpleFramedSpin(gtk.Frame):
   """A framed spin button"""
   def get_value(self):
      if self.check.get_active():
         return self.spin.get_value()
      else:
         return -1
   def set_value(self, new_value):
      self.spin.set_value(new_value)
   def __init__(self, text, adj):
      gtk.Frame.__init__(self)
      label = gtk.Label(text)
      hbox = gtk.HBox()
      hbox.pack_start(label, False, False, 3)
      label.show()
      self.set_label_widget(hbox)
      hbox.show()
      vbox = gtk.VBox()
      vbox.set_border_width(2)
      self.spin = gtk.SpinButton(adj)
      vbox.add(self.spin)
      self.spin.show()
      self.add(vbox)
      vbox.show()

class Tab(gtk.VBox):
   def show_indicator(self, colour):
      thematch = self.indicator_lookup[colour]
      thematch.show()
      for colour, indicator in self.indicator_lookup.iteritems():
         if indicator is not thematch:
            indicator.hide()
   def send(self, stringtosend):
      self.source_client_gui.send("tab_id=%d\n%s" % (self.numeric_id, stringtosend))
   def receive(self):
      return self.source_client_gui.receive()
   def __init__(self, scg, numeric_id, indicator_lookup):
      self.indicator_lookup = indicator_lookup
      self.numeric_id = numeric_id
      self.source_client_gui = scg
      gtk.VBox.__init__(self)
      gtk.VBox.set_border_width(self, 8)
      gtk.VBox.show(self)

class StreamTab(Tab):
   class ResampleFrame(SubcategoryFrame):
      def cb_eval(self, widget, data = None):
         if data is not None:
            if widget.get_active():
               self.extraction_method = data
            else:
               return
         if self.extraction_method == "no_resample":
            self.resample_rate = self.jack_sample_rate
         elif self.extraction_method == "standard":
            self.resample_rate = int(self.resample_rate_combo_box.get_active_text())
         else:
            self.resample_rate = int(self.resample_rate_spin_adj.get_value())
         self.resample_quality = ("highest", "high", "fast", "fastest")[self.resample_quality_combo_box.get_active()]
         self.mp3_compatible = self.resample_rate in self.mp3_samplerates
         self.parentobject.mp3_dummy_object.clicked()           # update mp3 pane
         self.parentobject.vorbis_dummy_object.clicked()
      def __init__(self, parent, sizegroup):
         self.parentobject = parent
         self.jack_sample_rate = parent.source_client_gui.jack_sample_rate
         self.resample_rate = self.jack_sample_rate
         self.extraction_method = "no_resample"
         self.mp3_compatible = True
         SubcategoryFrame.__init__(self, ln.stream_resample)
         self.resample_no_resample, self.resample_standard, self.resample_custom = self.parentobject.make_radio(3)
         self.resample_no_resample.connect("clicked", self.cb_eval, "no_resample")
         self.resample_standard.connect("clicked", self.cb_eval, "standard")
         self.resample_custom.connect("clicked", self.cb_eval, "custom")
         no_resample_label = gtk.Label(ln.no_resample)
         self.mp3_samplerates = (48000, 44100, 32000, 24000, 22050, 16000, 12000, 11025, 8000)
         self.resample_rate_combo_box = self.parentobject.make_combo_box(map(str, self.mp3_samplerates))
         self.resample_rate_combo_box.set_active(1)
         self.resample_rate_combo_box.connect("changed", self.cb_eval)
         self.resample_rate_spin_adj = gtk.Adjustment(44100, 4000, 190000, 10, 100, 0)
         self.resample_rate_spin_control = gtk.SpinButton(self.resample_rate_spin_adj, 0, 0)
         self.resample_rate_spin_control.connect("value-changed", self.cb_eval)
         resample_quality_label = gtk.Label(ln.resample_quality)
         self.resample_quality_combo_box = self.parentobject.make_combo_box((ln.best_quality_resample,
                        ln.good_quality_resample, ln.fast_resample, ln.fastest_resample))
         self.resample_quality_combo_box.set_active(3)
         self.resample_quality_combo_box.connect("changed", self.cb_eval)
         self.resample_dummy_object = gtk.Button()
         self.resample_dummy_object.connect("clicked", self.cb_eval)
         sample_rate_pane = self.parentobject.item_item_layout(((self.resample_no_resample, no_resample_label),
                              (self.resample_standard, self.resample_rate_combo_box),
                              (self.resample_custom, self.resample_rate_spin_control),
                              (resample_quality_label, self.resample_quality_combo_box)), sizegroup)
         sample_rate_pane.set_border_width(10)
         self.add(sample_rate_pane)
         sample_rate_pane.show()
         tooltips = parent.scg.parent.tooltips
         tooltips.set_tip(self.resample_no_resample.get_parent(), ln.use_jack_srate_tip)
         tooltips.set_tip(self.resample_standard.get_parent(), ln.use_mp3_srate_tip)
         tooltips.set_tip(self.resample_custom.get_parent(), ln.use_custom_srate_tip)
         tooltips.set_tip(self.resample_quality_combo_box.get_parent(), ln.streamer_resample_quality)
   def make_combo_box(self, items):
      combobox = gtk.combo_box_new_text()
      for each in items:
         combobox.append_text(each)
      return combobox
   def make_radio(self, qty):
      listofradiobuttons = []
      for iteration in range(qty):
         listofradiobuttons.append(gtk.RadioButton())
         if iteration > 0:
            listofradiobuttons[iteration].set_group(listofradiobuttons[0])
      return listofradiobuttons
   def make_radio_with_text(self, labels):
      listofradiobuttons = []
      for count, label in enumerate(labels):
         listofradiobuttons.append(gtk.RadioButton(None, label))
         if count > 0:
            listofradiobuttons[count].set_group(listofradiobuttons[0])
      return listofradiobuttons
   def make_notebook_tab(self, notebook, labeltext, tooltip = None):
      label = gtk.Label(labeltext)
      if tooltip is not None:
         self.scg.parent.tooltips.set_tip(label, tooltip)
      vbox = gtk.VBox()
      notebook.append_page(vbox, label)
      label.show()
      vbox.show()
      return vbox
   def item_item_layout(self, item_item_pairs, sizegroup):
      vbox = gtk.VBox()
      vbox.set_spacing(2)
      for left, right in item_item_pairs:
         hbox = gtk.HBox()
         sizegroup.add_widget(hbox)
         hbox.set_spacing(5)
         if left is not None:
            hbox.pack_start(left, False, False, 0)
            left.show()
         if right is not None:
            hbox.pack_start(right, True, True, 0)
            right.show()
         vbox.pack_start(hbox, False, False, 0)
         hbox.show()
      return vbox
   def item_item_layout2(self, item_item_pairs, sizegroup):
      rhs_size = gtk.SizeGroup(gtk.SIZE_GROUP_HORIZONTAL)
      vbox = gtk.VBox()
      vbox.set_spacing(2)
      for left, right in item_item_pairs:
         hbox = gtk.HBox()
         rhs_size.add_widget(left)
         sizegroup.add_widget(hbox)
         hbox.set_spacing(5)
         hbox.pack_start(left, False, False, 0)
         left.show()
         if right is not None:
            rhs_size.add_widget(right)
            hbox.pack_end(right, False, False, 0)
            right.show()
         vbox.pack_start(hbox, False, False, 0)
         hbox.show()
      return vbox
   def item_item_layout3(self, leftitems, rightitems):
      outer = gtk.HBox()
      wedge = gtk.HBox()
      outer.pack_start(wedge, False, False, 2)
      wedge = gtk.HBox()
      outer.pack_end(wedge, False, False, 2)
      lh = gtk.HBox()
      rh = gtk.HBox()
      outer.pack_start(lh, True, False, 0)
      outer.pack_start(rh, True, False, 0)
      lv = gtk.VBox()
      rv = gtk.VBox()
      lh.pack_start(lv, False, False, 0)
      rh.pack_start(rv, False, False, 0)
      lframe = gtk.Frame()
      lframe.set_shadow_type(gtk.SHADOW_OUT)
      rframe = gtk.Frame()
      rframe.set_shadow_type(gtk.SHADOW_OUT)
      lv.pack_start(lframe, True, False, 0)
      rv.pack_start(rframe, True, False, 0)
      lvi = gtk.VBox()
      lvi.set_border_width(5)
      lvi.set_spacing(7)
      rvi = gtk.VBox()
      rvi.set_border_width(5)
      rvi.set_spacing(7)
      lframe.add(lvi)
      rframe.add(rvi)
      for item in leftitems:
         lvi.pack_start(item, True, False, 0)
      for item in rightitems:
         rvi.pack_start(item, True, False, 0)
      return outer
   def label_item_layout(self, label_item_pairs, sizegroup):    # align vertical colums of label : item
      hbox = gtk.HBox()                                         # label is right justified and narrow as possible
      vbox_left = gtk.VBox()                                    # the item widget is free to expand
      vbox_left.set_spacing(1)
      vbox_right = gtk.VBox()
      vbox_right.set_spacing(1)
      hbox.pack_start(vbox_left, False, False, 0)
      hbox.pack_start(vbox_right, True, True, 0)
      hbox.set_spacing(5)
      for text, item in label_item_pairs:
         if text is not None:
            labelbox = gtk.HBox()
            if type(text) == str:
               label = gtk.Label(text)
            else:
               label = text
            sizegroup.add_widget(label)
            labelbox.pack_end(label, False, False)
            label.show()
            vbox_left.pack_start(labelbox, False, False, 0)
            labelbox.show()
         itembox = gtk.HBox()
         sizegroup.add_widget(itembox)
         itembox.add(item)
         item.show()
         vbox_right.pack_start(itembox, False, False, 0)
         itembox.show()
      vbox_left.show()
      vbox_right.show()
      return hbox
   def send(self, string_to_send):
      Tab.send(self, "dev_type=streamer\n" + string_to_send)
   def receive(self):
      return Tab.receive(self)
   def cb_servertype(self, widget):
      sens = bool(widget.get_active())
      for each in (self.mount_entry, self.login_entry):
         each.set_sensitive(sens)
      self.update_sensitives()
   def update_sensitives(self, *params):
      if self.encoder == "off":
         self.update_button.set_sensitive(False)
      mode = self.connection_pane.get_master_server_type() # 0 = none, 1 = icecast2, 2 = shoutcast
      self.recorder_valid_override = False
      
      if self.encoder == "ogg":
         self.server_connect.set_sensitive(mode == 1 or self.server_connect.get_active())
         if self.format_page == 0:
            self.update_button.set_sensitive(False)
         elif self.format_page == 1:
           self.update_button.set_sensitive(self.vorbis_settings_valid)
         elif self.format_page == 2:
            try:
               self.update_button.set_sensitive(self.file_dialog.get_filename().lower().endswith(".ogg"))
            except AttributeError:
               self.update_button.set_sensitive(False)
         else:
            print "update_sensitives: unhandled format page"
      elif self.encoder == "mp3":
         self.server_connect.set_sensitive(mode != 0 or self.server_connect.get_active())
         if self.format_page == 0:
            self.update_button.set_sensitive(self.mp3_compatibility != "s-rate!")
         elif self.format_page == 1:
            self.update_button.set_sensitive(False)
         elif self.format_page == 2:
            try:
               self.update_button.set_sensitive(self.file_dialog.get_filename().lower().endswith(".mp3"))
            except AttributeError:
               self.update_button.set_sensitive(False)
         else:
            print "update_sensitives: unhandled format page"
      elif self.encoder == "off":
         self.test_monitor.set_sensitive(True)
         if self.format_page == 0:
            self.recorder_valid_override = sens = bool(self.mp3_compatibility != "s-rate!" and lameenabled)
            sens = sens and mode
            self.server_connect.set_sensitive(sens)
            self.test_monitor.set_sensitive(sens)
         elif self.format_page == 1:
            if self.subformat_page == 0:
               self.recorder_valid_override = sens = self.vorbis_settings_valid
            elif self.subformat_page == 1:   # OggFLAC
               sr = self.stream_resample_frame.resample_rate
               self.recorder_valid_override = sens = sr <= 65535 or sr % 10 == 0
            elif self.subformat_page == 2:   # Speex
               self.recorder_valid_override = sens = True                   # True always for now
            self.server_connect.set_sensitive(sens and mode == 1)
            self.test_monitor.set_sensitive(sens)
         try:
            record_tabs = self.source_client_gui.recordtabframe.tabs
         except:
            pass        # this will be called inevitably before recordtabframe has been created yet
         else:
            for rectab in record_tabs:
               rectab.source_dest.source_combo.emit("changed")  # update sensitivity on record buttons
      if self.encoder != "off":
         if self.format_page == 0:
            if self.encoder == "ogg" or self.mp3_compatibility == "s-rate!":
               self.update_button.set_sensitive(False)
         if self.format_page == 1 and self.encoder == "mp3":
               self.update_button.set_sensitive(False)
   
   def cb_file_dialog_response(self, widget, response_id):
      self.update_sensitives()
   def cb_format_notebook(self, widget, page, page_num):
      if self.format_page != page_num:
         self.format_page = page_num
         self.update_sensitives()
   def cb_subformat_notebook(self, widget, page, page_num):
      if self.subformat_page != page_num:
         self.subformat_page = page_num
         self.update_sensitives()
   def cb_mp3tab(self, widget, data = None):
      if data == "standard" or data == "custom":
         if widget.get_active():
            self.mp3_bitrate_widget = data
         else:
            return
      self.mp3_stereo_type = ("stereo", "mono", "jstereo")[self.mp3_stereo_combo_box.get_active()]
      self.mp3_encode_quality = self.mp3_encoding_quality_combo_box.get_active_text()
      if self.mp3_bitrate_widget == "standard":
         self.mp3_bitrate = int(self.mp3_bitrate_combo_box.get_active_text())
      elif self.mp3_bitrate_widget == "custom":
         self.mp3_bitrate = int(self.mp3_bitrate_spin_adj.get_value())
      self.mp3_standard_bitrate = self.mp3_bitrate in self.mp3_standard_bitrates
      self.mp3_samplerate = self.stream_resample_frame.resample_rate
      self.mp3_resample_compatible = self.stream_resample_frame.mp3_compatible
      self.mp3_compatibility = "freeformat"
      if not self.mp3_resample_compatible:
         self.mp3_compatibility = "s-rate!"
      else:
         if self.mpeg_std_search(self.mp3_bitrate, self.mp3_samplerate, self.mp3_mpeg2_5_bitrates_samplerates):
            self.mp3_compatibility = "mpeg 2.5"
         if self.mpeg_std_search(self.mp3_bitrate, self.mp3_samplerate, self.mp3_mpeg2_bitrates_samplerates):
            self.mp3_compatibility = "mpeg 2"
         if self.mpeg_std_search(self.mp3_bitrate, self.mp3_samplerate, self.mp3_mpeg1_bitrates_samplerates):
            self.mp3_compatibility = "mpeg 1"
      self.mp3_compatibility_status.push(1, self.mp3_compatibility)
      self.mp3_freeformat = ("0", "1")[self.mp3_compatibility == "freeformat"]
      self.update_sensitives()
   
   def cb_oggtab(self, widget, data = None):
      ogg_bitrate = self.ogg_encoding_nominal_spin_adj.get_value()
      minactive = self.ogg_min_checkbutton.get_active()
      maxactive = self.ogg_max_checkbutton.get_active()
      self.ogg_encoding_relmin_spin_control.set_sensitive(minactive)
      self.ogg_encoding_relmax_spin_control.set_sensitive(maxactive)
      if minactive:
         ogg_min = self.ogg_encoding_relmin_spin_adj.get_value() + ogg_bitrate
         if ogg_min <= 0:
            ogg_min = -1
      else:
         ogg_min = -1
      if maxactive:
         ogg_max = self.ogg_encoding_relmax_spin_adj.get_value() + ogg_bitrate
      else:
         ogg_max = -1
      self.send("sample_rate=%d\nbit_rate=%d\nbit_rate_min=%d\nbit_rate_max=%d\nstereo=%s\ncommand=test_ogg_values\n" % (self.stream_resample_frame.resample_rate, 
                ogg_bitrate, ogg_min, ogg_max,
                ("mono","stereo")[self.ogg_encoding_stereo_checkbutton.get_active()]))
      self.vorbis_settings_valid = self.receive() == "succeeded"
      self.update_sensitives()
      
   def cb_vorbistab(self, widget, data = None):
      vorbis_bitrate = self.vorbis_encoding_nominal_spin_adj.get_value()
      vorbis_min = self.vorbis_encoding_lower_spin_control.get_cooked_value()
      vorbis_max = self.vorbis_encoding_upper_spin_control.get_cooked_value()
      self.send("sample_rate=%d\nbit_rate=%d\nbit_rate_min=%d\nbit_rate_max=%d\nstereo=%s\ncommand=test_ogg_values\n" % (self.stream_resample_frame.resample_rate, 
                vorbis_bitrate, vorbis_min, vorbis_max,
                ("mono","stereo")[self.vorbis_stereo_rb.get_active()]))
      self.vorbis_settings_valid = self.receive() == "succeeded"
      self.update_sensitives()
      
   def mpeg_std_search(self, bitrate, samplerate, brsr):
      return bitrate in brsr[0] and samplerate in brsr[1]
   def server_reconnect(self):
      if self.connection_string:
         self.send("command=server_disconnect\n")
         self.receive()
         time.sleep(0.25)
         self.send(self.connection_string)
         self.receive()
   def cb_server_connect(self, widget):
      if widget.get_active():
         self.start_stop_encoder(ENCODER_START)
         d = self.connection_pane.row_to_dict(0)

         self.connection_string = "\n".join((
               "stream_source=" + str(self.numeric_id),
               "server_type=" + ("Icecast 2", "Shoutcast")[d["server_type"]],
               "host=" + d["host"],
               "port=%d" % d["port"],
               "mount=" + d["mount"],
               "login=" + d["login"],
               "password=" + d["password"],
               "dj_name=" + self.dj_name_entry.get_text().strip(),
               "listen_url=" + self.listen_url_entry.get_text().strip(),
               "description=" + self.description_entry.get_text().strip(),
               "genre=" + self.genre_entry.get_text().strip(),
               "irc=" + self.irc_entry.get_text().strip(),
               "aim=" + self.aim_entry.get_text().strip(),
               "icq=" + self.icq_entry.get_text().strip(),
               "make_public=" + str(bool(self.make_public.get_active())),
               "command=server_connect\n"))
         self.send(self.connection_string)
         self.is_shoutcast = d["server_type"] == 1
         if self.receive() == "failed":
            self.server_connect.set_active(False)
            self.connection_string = None
         else:
            self.connection_pane.streaming_set(True)
      else:
         self.send("command=server_disconnect\n")
         self.receive()
         self.start_stop_encoder(ENCODER_STOP)
         self.connection_string = None
         self.connection_pane.streaming_set(False)
   def cb_test_monitor(self, widget):
      if widget.get_active():
         self.start_stop_encoder(ENCODER_START)
         self.send("command=monitor_start\n")
      else:
         self.send("command=monitor_stop\n")
         self.start_stop_encoder(ENCODER_STOP)
   def cb_update_button(self, widget):
      self.start_encoder("encoder_update")
      if self.server_connect.get_active() and self.is_shoutcast:
         self.server_reconnect()
   def start_stop_encoder(self, command):               # provides for nested starts, stops of the encoder
      if command == ENCODER_START:
         self.encoder_on_count += 1
         if self.encoder_on_count == 1:
            self.start_encoder()
      else:
         self.encoder_on_count -= 1
         if self.encoder_on_count == 0:
            self.stop_encoder()
      self.update_sensitives()
   def start_encoder(self, command = "encoder_start"):
      if self.format_page == 0:
         self.encoder = "mp3"
         self.send("format=mp3\nencode_source=jack\nsample_rate=%d\nresample_quality=%s\nbit_rate=%d\nstereo=%s\nencode_quality=%s\nfreeformat_mp3=%s\ncommand=%s\n" %   (self.stream_resample_frame.resample_rate,
                                         self.stream_resample_frame.resample_quality,
                                         self.mp3_bitrate, 
                                         self.mp3_stereo_type,
                                         self.mp3_encode_quality,
                                         self.mp3_freeformat,
                                         command))
         if self.receive() == "succeeded":
            self.format_info_bar.push(1, "mp3   %dHz   %dkbps   %s" % (self.stream_resample_frame.resample_rate, self.mp3_bitrate, self.mp3_stereo_type))
         else:
            self.format_info_bar.push(1, "")
      elif self.format_page == 1:
         self.encoder = "ogg"
         if self.subformat_page == 0:  # vorbis
            vorbis_bitrate = self.vorbis_encoding_nominal_spin_adj.get_value()
            vorbis_min = self.vorbis_encoding_lower_spin_control.get_cooked_value()
            vorbis_max = self.vorbis_encoding_upper_spin_control.get_cooked_value()
            vorbis_channels = ("mono", "stereo")[self.vorbis_stereo_rb.get_active()]
            self.send("format=ogg\nsubformat=vorbis\nencode_source=jack\nsample_rate=%d\nresample_quality=%s\nbit_rate=%d\nbit_rate_min=%d\nbit_rate_max=%d\nstereo=%s\ncommand=%s\n" % (self.stream_resample_frame.resample_rate, 
                                             self.stream_resample_frame.resample_quality,
                                             vorbis_bitrate, vorbis_min, vorbis_max,
                                             vorbis_channels, command))
            if self.receive() == "succeeded":
               if vorbis_min == vorbis_max == -1:
                  managed = ""
               else:
                  managed = "   managed"
               self.format_info_bar.push(1, "Ogg Vorbis   %dHz   %dkbps   %s%s" % (self.stream_resample_frame.resample_rate, vorbis_bitrate, vorbis_channels, managed))
            else:
               self.format_info_bar.push(1, "")
         elif self.subformat_page == 1: # OggFLAC
            flac_channels = ("mono", "stereo")[self.flacstereo.get_active()]
            flac_bitwidth = ("16", "20", "24")[(self.flac20bit.get_active() and 1) + (self.flac24bit.get_active() and 2)]
            self.send("format=ogg\nsubformat=flac\nencode_source=jack\nsample_rate=%d\nresample_quality=%s\nbit_width=%s\nstereo=%s\nuse_metadata=%d\ncommand=%s\n" % (self.stream_resample_frame.resample_rate, self.stream_resample_frame.resample_quality, flac_bitwidth, flac_channels, self.flacmetadata.get_active(), command))
            if self.receive() == "succeeded":
               self.format_info_bar.push(1, "Ogg FLAC   %s bit   %s" % (flac_bitwidth, flac_channels))
            else:
               self.format_info_bar.push(1, "")
         elif self.subformat_page == 2: # speex
            speex_srate = (32000, 16000, 8000)[self.speex_mode.get_active()]
            speex_channels = ("mono", "stereo")[self.speex_stereo.get_active()]
            self.send("format=ogg\nsubformat=speex\nencode_source=jack\nsample_rate=%d\nresample_quality=%s\nspeex_mode=%d\nstereo=%s\nuse_metadata=%d\nspeex_quality=%s\nspeex_complexity=%s\ncommand=%s\n" % (speex_srate, self.stream_resample_frame.resample_quality, self.speex_mode.get_active(), speex_channels, self.speex_metadata.get_active(), self.speex_quality.get_active_text(), self.speex_complexity.get_active_text(), command))
            metatext = ("-Meta", "+Meta")[self.speex_metadata.get_active()]
            if self.receive() == "succeeded":
               self.format_info_bar.push(1, "Speex   %s   %s   Q%s   C%s   %s" % (self.speex_mode.get_active_text(), speex_channels.capitalize(), self.speex_quality.get_active_text(), self.speex_complexity.get_active_text(), metatext))
            else:
               self.format_info_bar.push(1, "")
      else:
         if self.file_dialog.get_filename().endswith(".mp3"):
            self.encoder = "mp3"
         else:
            self.encoder = "ogg"
         self.send("format=%s\nencode_source=file\nfilename=%s\noffset=%d\ncommand=%s\n" %   (self.encoder, self.file_dialog.get_filename(), self.file_offset_adj.get_value(), command))
         if self.receive() == "succeeded":
            self.format_info_bar.push(1, self.file_dialog.get_filename())
         else:
            self.format_info_bar.push(1, "")
   def stop_encoder(self):
      self.encoder = "off"
      self.send("command=encoder_stop\n")
      if self.receive() == "failed":
         print "stop_encoder: encoder was already stopped"
      self.format_info_bar.push(1, "")
   
   def server_type_cell_data_func(self, celllayout, cell, model, iter):
      text = model.get_value(iter, 0)
      if text == ln.server_type_shoutcast and lameenabled == 0:
         cell.set_property("sensitive", False)
      else:
         cell.set_property("sensitive", True)
   
   def cb_metadata(self, widget):
      table = zip(("%r", "%t", "%l"), ((getattr(self.scg.parent, x) or "<Unknown>") for x in ("artist", "title", "album")))
      parts = self.metadata.get_text().encode("utf-8", "replace").strip().split("%%")
      custom_meta = []

      for part in parts:
         for pattern, replacement in table:
            part = part.replace(pattern, replacement)
         custom_meta.append(part)
      custom_meta = "%".join(custom_meta)

      if self.scg.parent.prefs_window.mp3_utf8.get_active():
         custom_meta_lat1 = custom_meta
      else:
         custom_meta_lat1 = custom_meta.decode("utf-8").encode("iso8859-1", "replace").strip()

      self.scg.send("tab_id=%d\ndev_type=encoder\ncustom_meta=%s\ncustom_meta_lat1=%s\ncommand=new_custom_metadata\n" % (self.numeric_id, custom_meta, custom_meta_lat1))
  
   
   @threadslock
   def deferred_connect(self):
      """Intended to be called from a thread."""
      
      self.server_connect.set_active(True)
  
   def cb_kick_incumbent(self, widget, post_action=lambda : None):
      """Try to remove whoever is using the server so that we can connect."""
      
      mode = self.connection_pane.get_master_server_type()
      if mode == 0:
         return
        
      srv = ListLine(*self.connection_pane.liststore[0])
      auth_handler = urllib2.HTTPBasicAuthHandler()

      if mode == 1:
         url = "http://" + urllib.quote(srv.host) + ":" + str(srv.port) + "/admin/killsource?mount=" + urllib.quote(srv.mount)
         auth_handler.add_password("Icecast2 Server", srv.host + ":" + str(srv.port), srv.login, srv.password)
         def check_reply(reply):
            elem = xml.etree.ElementTree.fromstring(reply)
            rslt = "succeeded" if elem.findtext("return") == "1" else "failed"
            print "kick %s: %s" % (rslt, elem.findtext("message"))
            return rslt == "succeeded"

      elif mode == 2:
         password = self.admin_password_entry.get_text().strip() or srv.password
         url = "http://" + urllib.quote(srv.host) + ":" + str(srv.port) + "/admin.cgi?mode=kicksrc"
         auth_handler.add_password("Shoutcast Server", srv.host + ":" + str(srv.port), "admin", password)
         def check_reply(reply):
            # Could go to lengths to check the XML stats here.
            # Thats one whole extra HTTP request.
            print "kick succeeded"
            return True

      opener = urllib2.build_opener(auth_handler)
      opener.addheaders = [('User-agent', 'Mozilla/5.0')]

      def threaded():
         try:
            reply = opener.open(url).read()
         except urllib2.URLError, e:
            print "kick failed:", e
         else:
            check_reply(reply)
            post_action()
     
      Thread(target=threaded).start()
  
   def __init__(self, scg, numeric_id, indicator_lookup):
      Tab.__init__(self, scg, numeric_id, indicator_lookup)
      self.scg = scg
      self.show_indicator("clear")
      self.tab_type = "streamer"
      set_tip = self.scg.parent.tooltips.set_tip
      self.encoder = "off"                      # can also be set to "mp3" or "ogg" depending on what is encoded
      self.encoder_on_count = 0                 # when this counter hits zero the encoder is turned off
      self.format_page = 0                      # the current format page
      self.subformat_page = 0                   # the Ogg sub-format
      self.set_spacing(10)
           
      self.ic_expander = gtk.Expander(ln.individual_controls)
      self.pack_start(self.ic_expander, False)
      self.ic_expander.show()
            
      self.ic_frame = gtk.Frame()
      ic_vbox = gtk.VBox()                 # box containing connect button and timers
      ic_vbox.set_border_width(10)
      ic_vbox.set_spacing(10)
      self.ic_frame.add(ic_vbox)
      ic_vbox.show()
      
      hbox = gtk.HBox()
      hbox.set_spacing(6)
      self.server_connect = gtk.ToggleButton()
      set_tip(self.server_connect, ln.server_connect_tip)
      self.server_connect.connect("toggled", self.cb_server_connect)
      hbox.pack_start(self.server_connect, True, True, 0)
      self.server_connect_label = gtk.Label()
      self.server_connect_label.set_ellipsize(pango.ELLIPSIZE_MIDDLE)
      self.server_connect.add(self.server_connect_label)
      self.server_connect_label.show()
      self.server_connect.show()
      
      self.kick_incumbent = gtk.Button(ln.kick_incumbent)
      self.kick_incumbent.connect("clicked", self.cb_kick_incumbent)
      set_tip(self.kick_incumbent, ln.kick_incumbent_tip)
      hbox.pack_start(self.kick_incumbent, False)
      self.kick_incumbent.show()
      
      ic_vbox.pack_start(hbox, False)
      hbox.show()
      
      hbox = gtk.HBox()
      hbox.set_spacing(10)
      label = gtk.Label(ln.timer)
      hbox.pack_start(label, False)
      label.show()
      
      self.start_timer = TimeEntry(ln.start_streaming_time)
      set_tip(self.start_timer, ln.start_timer_tip)
      hbox.pack_start(self.start_timer, True)
      self.start_timer.show()
      self.stop_timer = TimeEntry(ln.stop_streaming_time)
      set_tip(self.stop_timer, ln.stop_timer_tip)
      hbox.pack_start(self.stop_timer, True)
      self.stop_timer.show()
      
      self.kick_before_start = gtk.CheckButton(ln.kick_before_start)
      set_tip(self.kick_before_start, ln.kick_before_start_tip)
      hbox.pack_end(self.kick_before_start, False)
      self.kick_before_start.show()
      
      ic_vbox.pack_start(hbox, False, False, 0)
      hbox.show()
      
      hbox = gtk.HBox()                                 # box containing auto action widgets
      hbox.set_spacing(10)
      label = gtk.Label(ln.upon_connection)
      hbox.pack_start(label, False, False, 0)
      label.show()
      self.start_player_action = AutoAction(ln.start_player, (
                ("1", self.source_client_gui.parent.player_left.play.clicked),
                ("2", self.source_client_gui.parent.player_right.play.clicked)))
      hbox.pack_start(self.start_player_action, False, False, 0)
      self.start_player_action.show()
      set_tip(self.start_player_action, ln.auto_start_player_tip)
      if idjc_config.num_recorders:
         vseparator = gtk.VSeparator()
         hbox.pack_start(vseparator, True, False, 0)
         vseparator.show()
      
      self.start_recorder_action = AutoAction(ln.start_recorder, [ (chr(ord("1") + i), t.record_buttons.record_button.activate) for i, t in enumerate(self.source_client_gui.recordtabframe.tabs) ])
      
      hbox.pack_end(self.start_recorder_action, False, False, 0)
      if idjc_config.num_recorders:
         self.start_recorder_action.show()
      set_tip(self.start_recorder_action, ln.auto_start_recorder_tip)
      ic_vbox.pack_start(hbox, False, False, 0)
      hbox.show()

      hbox = gtk.HBox()
      hbox.set_spacing(6)
      label = gtk.Label(ln.metadata)
      hbox.pack_start(label, False)
      label.show()
      self.metadata = gtk.Entry()
      set_tip(self.metadata, ln.metadata_entry_tip)
      hbox.pack_start(self.metadata)
      self.metadata.show()
      self.metadata_update = gtk.Button(ln.update)
      self.metadata_update.connect("clicked", self.cb_metadata)
      set_tip(self.metadata_update, ln.metadata_update_tip)
      hbox.pack_start(self.metadata_update, False)
      self.metadata_update.show()
      
      ic_vbox.pack_start(hbox, False)
      hbox.show()
      
      self.pack_start(self.ic_frame, False)
      
      self.details = gtk.Expander(ln.stream_details)
      set_tip(self.details, ln.stream_details_tip)
      self.pack_start(self.details, False)
      self.details.show()
     
      self.details_nb = gtk.Notebook()
      self.pack_start(self.details_nb, False)
      
      self.connection_pane = ConnectionPane(set_tip, self)
      self.connection_pane.liststore.connect("row-deleted", self.update_sensitives)
      self.connection_pane.liststore.connect("row-inserted", self.update_sensitives)
      label = gtk.Label(ln.connection)
      self.details_nb.append_page(self.connection_pane, label)
      label.show()
      self.connection_pane.show()
       
      vbox = gtk.VBox()          # format box
      vbox.set_border_width(10)
      vbox.set_spacing(14)
      label = gtk.Label(ln.format)
      self.details_nb.append_page(vbox, label)
      label.show()
      vbox.show()
      hbox = gtk.HBox(True)
      hbox.set_spacing(16)
      vbox.pack_start(hbox, False)
      hbox.show()
      sizegroup = gtk.SizeGroup(gtk.SIZE_GROUP_VERTICAL)
      self.stream_resample_frame = self.ResampleFrame(self, sizegroup)  # stream resample frame
      hbox.add(self.stream_resample_frame)
      self.stream_resample_frame.show()
      self.format_notebook = gtk.Notebook()     # [mp3 / ogg / file] chooser
      hbox.add(self.format_notebook)
      self.format_notebook.show()
      
      # mp3 tab
      self.mp3tab = self.make_notebook_tab(self.format_notebook, "MP3", ln.mp3_streamtab_tip)
      self.standard_mp3_bitrate, self.custom_mp3_bitrate = self.make_radio(2)
      set_tip(self.standard_mp3_bitrate, ln.std_mp3_rate_tip)
      set_tip(self.custom_mp3_bitrate, ln.nonstd_mp3_rate_tip)
      self.standard_mp3_bitrate.connect("clicked", self.cb_mp3tab, "standard")
      self.custom_mp3_bitrate.connect("clicked", self.cb_mp3tab, "custom")
      self.mp3_standard_bitrates = (320, 256, 224, 192, 160, 144, 128, 112, 96, 80, 64, 56, 48, 40, 32, 24, 16, 8)
      self.mp3_mpeg1_bitrates_samplerates = ((320, 256, 224, 192, 160, 128, 112, 96, 80, 64, 56, 48, 40, 32), (48000, 44100, 32000))
      self.mp3_mpeg2_bitrates_samplerates = ((160, 144, 128, 112, 96, 80, 64, 56, 48, 40, 32, 24, 16, 8), (24000, 22050, 16000))
      self.mp3_mpeg2_5_bitrates_samplerates = ((160, 144, 128, 112, 96, 80, 64, 56, 48, 40, 32, 24, 16, 8), (12000, 11025, 8000))
      self.mp3_bitrate_combo_box = self.make_combo_box(map(str, self.mp3_standard_bitrates))
      set_tip(self.mp3_bitrate_combo_box, ln.bitrate_tip)
      self.mp3_bitrate_combo_box.set_active(6)
      self.mp3_bitrate_combo_box.connect("changed", self.cb_mp3tab)
      self.mp3_bitrate_spin_adj = gtk.Adjustment(128, 8, 640, 10, 100, 0)
      self.mp3_bitrate_spin_control = gtk.SpinButton(self.mp3_bitrate_spin_adj)
      set_tip(self.mp3_bitrate_spin_control, ln.bitrate_tip)
      self.mp3_bitrate_spin_control.connect("value-changed", self.cb_mp3tab)
      encoding_quality_label = gtk.Label(ln.encoding_quality)
      self.mp3_encoding_quality_combo_box = self.make_combo_box(("0", "1", "2", "3", "4", "5", "6", "7", "8", "9"))
      set_tip(self.mp3_encoding_quality_combo_box, ln.mp3_quality_tip)
      self.mp3_encoding_quality_combo_box.set_active(2)
      self.mp3_encoding_quality_combo_box.connect("changed", self.cb_mp3tab)
      self.mp3_stereo_combo_box = self.make_combo_box(("Stereo", "Mono", "Joint Stereo"))
      set_tip(self.mp3_stereo_combo_box, ln.mp3_stereo_type_tip)
      self.mp3_stereo_combo_box.set_active(2)
      self.mp3_stereo_combo_box.connect("changed", self.cb_mp3tab)
      self.mp3_compatibility_status = gtk.Statusbar()
      set_tip(self.mp3_compatibility_status, ln.mp3_compat_tip)
      self.mp3_compatibility_status.set_has_resize_grip(False)
      self.mp3_dummy_object = gtk.Button()
      self.mp3_dummy_object.connect("clicked", self.cb_mp3tab)
      self.mp3_bitrate = 128
      self.mp3_bitrate_widget = "standard"
      
      if lameenabled:
         mp3_pane = self.item_item_layout(((self.standard_mp3_bitrate, self.mp3_bitrate_combo_box),
                                       (self.custom_mp3_bitrate, self.mp3_bitrate_spin_control),
                                       (encoding_quality_label, self.mp3_encoding_quality_combo_box),
                                       (self.mp3_stereo_combo_box, self.mp3_compatibility_status)), sizegroup)
         mp3_pane.set_border_width(10)
      else:
         mp3_pane = gtk.VBox(True)
         for line in ln.no_mp3_stream_available:
            label = gtk.Label(line)
            mp3_pane.add(label)
            label.show()
         set_tip(mp3_pane, ln.no_mp3_stream_available_tip)
      
      self.mp3tab.add(mp3_pane)
      mp3_pane.show()

      # Ogg tab
      self.oggtab = self.make_notebook_tab(self.format_notebook, "Ogg", ln.ogg_streamtab_tip)
      self.subformat_notebook = gtk.Notebook()
      self.oggtab.add(self.subformat_notebook)
      self.subformat_notebook.show()
      self.oggvorbistab = self.make_notebook_tab(self.subformat_notebook, "Vorbis", ln.vorbis_streamtab_tip)
      self.oggflactab = self.make_notebook_tab(self.subformat_notebook, "FLAC", ln.flac_streamtab_tip)
      self.oggspeextab = self.make_notebook_tab(self.subformat_notebook, "Speex", ln.speex_streamtab_tip)
      
      # Vorbis subtab contents
      self.vorbis_encoding_nominal_spin_adj = gtk.Adjustment(128, 8, 500, 1, 10, 0)
      self.vorbis_encoding_nominal_spin_control = SimpleFramedSpin(ln.bitrate, self.vorbis_encoding_nominal_spin_adj)
      self.vorbis_encoding_nominal_spin_control.spin.connect("value-changed", self.cb_vorbistab)
      
      self.vorbis_stereo_rb, self.vorbis_mono_rb = self.make_radio(2)
      self.vorbis_stereo_rb.connect("toggled", self.cb_vorbistab)
      radiovbox = gtk.VBox()
      radiovbox.set_border_width(5)
      stereohbox = gtk.HBox()
      monohbox = gtk.HBox()
      radiovbox.add(stereohbox)
      radiovbox.add(monohbox)
      stereohbox.pack_start(self.vorbis_stereo_rb, False, False, 0)
      monohbox.pack_start(self.vorbis_mono_rb, False, False, 0)
      label = gtk.Label(ln.stereo)
      stereohbox.pack_start(label)
      label = gtk.Label(ln.mono)
      monohbox.pack_start(label)
      radiovbox.show_all()
      
      upper_spin_adj = gtk.Adjustment(150, 100, 400, 1, 10, 0)
      lower_spin_adj = gtk.Adjustment(50, 0, 100, 1, 10, 0)
      self.vorbis_encoding_upper_spin_control = FramedSpin(ln.upper_vorbis, upper_spin_adj, self.vorbis_encoding_nominal_spin_adj)
      self.vorbis_encoding_lower_spin_control = FramedSpin(ln.lower_vorbis, lower_spin_adj, self.vorbis_encoding_nominal_spin_adj)
      
      sizegroup = gtk.SizeGroup(gtk.SIZE_GROUP_VERTICAL)

      vorbis_pane = self.item_item_layout2(((self.vorbis_encoding_nominal_spin_control, self.vorbis_encoding_upper_spin_control), (radiovbox, self.vorbis_encoding_lower_spin_control)), sizegroup)
      vorbis_pane.set_border_width(3)
      self.oggvorbistab.add(vorbis_pane)
      vorbis_pane.show()

      set_tip(self.vorbis_encoding_nominal_spin_control, ln.vorbis_bitrate_tip)
      set_tip(self.vorbis_encoding_upper_spin_control, ln.vorbis_bitrate_max_tip)
      set_tip(self.vorbis_encoding_lower_spin_control, ln.vorbis_bitrate_min_tip)

      self.vorbis_settings_valid = False
      self.vorbis_dummy_object = gtk.Button()
      self.vorbis_dummy_object.connect("clicked", self.cb_vorbistab)

      # FLAC subtab contents
      self.flacstereo = gtk.CheckButton(ln.stereo)
      self.flacmetadata = gtk.CheckButton(ln.flacmetadata)
      self.flacstereo.set_active(True)
      self.flacmetadata.set_active(True)
      set_tip(self.flacmetadata, ln.flacmetadata_tip)
      
      self.flac16bit, self.flac20bit, self.flac24bit = self.make_radio_with_text(ln.flac_bitrates)
      set_tip(self.flac16bit, ln.flac16_tip)
      set_tip(self.flac20bit, ln.flac20_tip)
      set_tip(self.flac24bit, ln.flac24_tip)
      if oggflacenabled:
         flac_pane = self.item_item_layout3((self.flacstereo, self.flacmetadata),(self.flac16bit, self.flac20bit, self.flac24bit))
      else:
         flac_pane = gtk.Label(ln.feature_disabled)
      self.oggflactab.add(flac_pane)
      flac_pane.show_all()
      
      # Speex subtab contents
      self.speex_mode = gtk.combo_box_new_text()
      for each in ln.speex_modes:
         self.speex_mode.append_text(each)
      self.speex_mode.set_active(0)
      self.speex_stereo = gtk.CheckButton(ln.stereo)
      set_tip(self.speex_stereo, ln.speex_stereo_tip)
      self.speex_metadata = gtk.CheckButton(ln.flacmetadata)
      set_tip(self.speex_metadata, ln.speex_metadata_tip)
      self.speex_quality = gtk.combo_box_new_text()
      for i in range(11):
         self.speex_quality.append_text("%d" % i)
      self.speex_quality.set_active(8)
      self.speex_complexity = gtk.combo_box_new_text()
      for i in range(1, 11):
         self.speex_complexity.append_text("%d" % i)
      self.speex_complexity.set_active(2)
      
      if speexenabled:
         svbox = gtk.VBox()
         svbox.set_border_width(5)
         
         label = gtk.Label(ln.speex_mode)
         shbox0 = gtk.HBox()
         shbox0.set_spacing(5)
         shbox0.pack_start(label, False, False, 0)
         shbox0.pack_start(self.speex_mode, True, True, 0)
         set_tip(shbox0, ln.speex_mode_tip)
         svbox.pack_start(shbox0, True, False, 0)
         shbox1 = gtk.HBox()
         shbox1.pack_start(self.speex_stereo, True, False, 0)
         shbox1.pack_end(self.speex_metadata, True, False, 0)
         svbox.pack_start(shbox1, True, False, 0)
         shbox2 = gtk.HBox()
         shbox3 = gtk.HBox()
         shbox3.set_spacing(5)
         shbox4 = gtk.HBox()
         shbox4.set_spacing(5)
         shbox2.pack_start(shbox3, False, False, 0)
         shbox2.pack_end(shbox4, False, False, 0)
         
         label = gtk.Label(ln.speex_quality)
         shbox3.pack_start(label, False, False, 0)
         shbox3.pack_start(self.speex_quality, False, False, 0)
         set_tip(shbox3, ln.speex_quality_tip)
         
         label = gtk.Label(ln.speex_complexity)
         shbox4.pack_start(label, False, False, 0)
         shbox4.pack_start(self.speex_complexity, False, False, 0)
         set_tip(shbox4, ln.speex_complexity_tip)
         
         svbox.pack_start(shbox2, True, False, 0)
         self.oggspeextab.add(svbox)
         svbox.show_all()
      else:
         label = gtk.Label(ln.feature_disabled)
         self.oggspeextab.add(label)
         label.show()
      
      format_control_bar = gtk.HBox()                           # Button box in Format frame
      format_control_sizegroup = gtk.SizeGroup(gtk.SIZE_GROUP_HORIZONTAL)
      format_control_bar.set_spacing(10)
      vbox.pack_start(format_control_bar, False)
      format_control_bar.show()
      self.test_monitor = gtk.ToggleButton(ln.test_monitor)
      self.test_monitor.connect("toggled", self.cb_test_monitor)
      format_control_sizegroup.add_widget(self.test_monitor)
      format_control_bar.pack_start(self.test_monitor, False, False, 0)
      #self.test_monitor.show()
      self.format_info_bar = gtk.Statusbar()
      self.format_info_bar.set_has_resize_grip(False)
      format_control_bar.pack_start(self.format_info_bar, True, True, 0)
      self.format_info_bar.show()
      set_tip(self.format_info_bar, ln.format_info_bar_tip)
      self.update_button = gtk.Button(ln.update)
      set_tip(self.update_button, ln.update_encoder_settings_tip)
      self.update_button.connect("clicked", self.cb_update_button)
      format_control_sizegroup.add_widget(self.update_button)
      self.update_button.set_sensitive(False)
      format_control_bar.pack_start(self.update_button, False, False, 0)
      self.update_button.show()
      self.format_notebook.connect("switch-page", self.cb_format_notebook)
      self.subformat_notebook.connect("switch-page", self.cb_subformat_notebook)
      self.format_notebook.set_current_page(0)

      vbox = gtk.VBox()
      label = gtk.Label(ln.extra_info)
      self.details_nb.append_page(vbox, label)
      label.show()
      vbox.show()
      self.dj_name_entry = gtk.Entry()
      set_tip(self.dj_name_entry, ln.dj_name_tip)
      self.listen_url_entry = gtk.Entry()
      set_tip(self.listen_url_entry, ln.listen_url_tip)
      self.description_entry = gtk.Entry()
      set_tip(self.description_entry, ln.description_tip)
      genre_entry_box = gtk.HBox()
      genre_entry_box.set_spacing(12)
      self.genre_entry = gtk.Entry()
      set_tip(self.genre_entry, ln.genre_tip)
      genre_entry_box.pack_start(self.genre_entry, True, True, 0)
      self.genre_entry.show()
      self.make_public = gtk.CheckButton(ln.make_public)
      set_tip(self.make_public, ln.make_public_tip)
      genre_entry_box.pack_start(self.make_public, False, False, 0)
      self.make_public.show()
      info_sizegroup = gtk.SizeGroup(gtk.SIZE_GROUP_VERTICAL)
      stream_details_pane = self.label_item_layout(((ln.dj_name, self.dj_name_entry),
                                              (ln.listen_url, self.listen_url_entry),
                                              (ln.description, self.description_entry),
                                              (ln.genre, genre_entry_box)
                                              ), info_sizegroup)
      stream_details_pane.set_border_width(10)
      vbox.add(stream_details_pane)
      stream_details_pane.show()
      

      vbox = gtk.VBox()
      alhbox = gtk.HBox()
      alhbox.set_border_width(10)
      alhbox.set_spacing(5)
      label = gtk.Label(ln.master_login)
      alhbox.pack_start(label, False)
      label.show()
      self.admin_password_entry = gtk.Entry()
      self.admin_password_entry.set_visibility(False)
      set_tip(self.admin_password_entry, ln.master_login_tip)
      alhbox.pack_start(self.admin_password_entry)
      self.admin_password_entry.show()
      vbox.pack_start(alhbox, False)
      alhbox.show()
           
      frame = CategoryFrame(ln.contact_details)
      frame.set_shadow_type(gtk.SHADOW_NONE)
      frame.set_border_width(0)
      self.irc_entry = gtk.Entry()
      set_tip(self.irc_entry, ln.icy_irc_tip)
      self.aim_entry = gtk.Entry()
      set_tip(self.aim_entry, ln.icy_aim_tip)
      self.icq_entry = gtk.Entry()
      set_tip(self.icq_entry, ln.icy_icq_tip)
      contact_sizegroup = gtk.SizeGroup(gtk.SIZE_GROUP_VERTICAL)
      contact_details_pane = self.label_item_layout((
                                              (ln.icy_irc, self.irc_entry),
                                              (ln.icy_aim, self.aim_entry),
                                              (ln.icy_icq, self.icq_entry)
                                              ), contact_sizegroup)
      contact_details_pane.set_border_width(10)
      frame.add(contact_details_pane)
      contact_details_pane.show()
      
      vbox.pack_start(frame, False)
      if enh_libshout:
         frame.show()
      label = gtk.Label(ln.shoutcast_extra)
      self.details_nb.append_page(vbox, label)
      label.show()
      vbox.show()
      
      self.stream_resample_frame.resample_no_resample.emit("clicked")   # bogus signal to update mp3 pane
      self.objects = {  "metadata"    : (self.metadata, "text"),
                        "prekick"     : (self.kick_before_start, "active"),
                        "connections" : (self.connection_pane, ("loader", "saver")),
                        "stats_never" : (self.connection_pane.stats_never, "active"),
                        "stats_always": (self.connection_pane.stats_always, "active"),
                        "rs_use_jack" : (self.stream_resample_frame.resample_no_resample, "active"),
                        "rs_use_std" : (self.stream_resample_frame.resample_standard, "active"),
                        "rs_use_custom_rate" : (self.stream_resample_frame.resample_custom, "active"),
                        "rs_std_rate" : (self.stream_resample_frame.resample_rate_combo_box, "active"),
                        "rs_custom_rate" : (self.stream_resample_frame.resample_rate_spin_adj, "value"),
                        "rs_quality" : (self.stream_resample_frame.resample_quality_combo_box, "active"),
                        "source_type" : (self.format_notebook, "notebookpage"),
                        "ogg_type": (self.subformat_notebook, "notebookpage"),
                        "std_mp3bitrate" : (self.standard_mp3_bitrate, "active"),
                        "custom_mp3_bitrate" : (self.custom_mp3_bitrate, "active"),
                        "mp3_bitrate_combo" : (self.mp3_bitrate_combo_box, "active"),
                        "mp3_bitrate_spin" : (self.mp3_bitrate_spin_adj, "value"),
                        "mp3_quality" : (self.mp3_encoding_quality_combo_box, "active"),
                        "mp3_stereo" : (self.mp3_stereo_combo_box, "active"),
                        "vorbis_bitrate" : (self.vorbis_encoding_nominal_spin_adj, "value"),
                        "vorbis_upper_pc": (self.vorbis_encoding_upper_spin_control.spin, "value"),
                        "vorbis_lower_pc":  (self.vorbis_encoding_lower_spin_control.spin, "value"),
                        "vorbis_upper_enable": (self.vorbis_encoding_upper_spin_control.check, "active"),
                        "vorbis_lower_enable": (self.vorbis_encoding_lower_spin_control.check, "active"),
                        "vorbis_mono": (self.vorbis_mono_rb, "active"),
                        "flac_stereo": (self.flacstereo, "active"),
                        "flac_metadata": (self.flacmetadata, "active"),
                        "flac_20_bit": (self.flac20bit, "active"),
                        "flac_24_bit": (self.flac24bit, "active"),
                        "speex_mode": (self.speex_mode, "active"),
                        "speex_stereo": (self.speex_stereo, "active"), 
                        "speex_metadata": (self.speex_metadata, "active"), 
                        "speex_quality": (self.speex_quality, "active"),
                        "speex_complexity": (self.speex_complexity, "active"),
                        "dj_name" : (self.dj_name_entry, "text"),
                        "listen_url" : (self.listen_url_entry, "text"),
                        "description" : (self.description_entry, "text"),
                        "genre" : (self.genre_entry, "text"),
                        "make_public" : (self.make_public, "active"),
                        "contact_aim" : (self.aim_entry, "text"),
                        "contact_irc" : (self.irc_entry, "text"),
                        "contact_icq" : (self.icq_entry, "text"),
                        "timer_start_active" : (self.start_timer.check, "active"),
                        "timer_start_time" : (self.start_timer.entry, "text"),
                        "timer_stop_active" : (self.stop_timer.check, "active"),
                        "timer_stop_time" : (self.stop_timer.entry, "text"),
                        "sc_admin_pass" : (self.admin_password_entry, "text"),
                        "ic_expander" : (self.ic_expander, "expanded"),
                        "conf_expander" : (self.details, "expanded"),
                        "action_play_active" : (self.start_player_action, "active"),
                        "action_play_which" : (self.start_player_action, "radioindex"),
                        "action_record_active" : (self.start_recorder_action, "active"),
                        "action_record_which" : (self.start_recorder_action, "radioindex") }
      self.reconnection_dialog = ReconnectionDialog(self)

class RecordTab(Tab):
   class RecordButtons(CategoryFrame):
      def cb_recbuttons(self, widget, userdata):
         changed_state = False
         if userdata == "rec":
            if widget.get_active():
               if not self.recording:
                  sd = self.parentobject.source_dest
                  if sd.streamtab is not None:
                     sd.streamtab.start_stop_encoder(ENCODER_START)
                     num_id = sd.streamtab.numeric_id
                  else:
                     num_id = -1
                  self.parentobject.send("record_source=%d\nrecord_folder=%s\ncommand=recorder_start\n" % (
                                        num_id,
                                        sd.file_dialog.get_current_folder()))
                  sd.file_dialog.response(gtk.RESPONSE_CLOSE)
                  sd.set_sensitive(False)
                  self.parentobject.time_indicator.set_sensitive(True)
                  self.recording = True
                  if self.parentobject.receive() == "failed":
                     self.stop_button.clicked()
            else:
               if self.stop_pressed:
                  self.stop_pressed = False
                  if self.recording == True:
                     self.recording = False
                     self.parentobject.send("command=recorder_stop\n")
                     self.parentobject.receive()
                  if self.parentobject.source_dest.streamtab is not None:
                     self.parentobject.source_dest.streamtab.start_stop_encoder(ENCODER_STOP)
                  self.parentobject.source_dest.set_sensitive(True)
                  self.parentobject.time_indicator.set_sensitive(False)
                  if self.pause_button.get_active():
                     self.pause_button.set_active(False)
               else:
                  widget.set_active(True)
         elif userdata == "stop":
            if self.recording:
               self.stop_pressed = True
               self.record_button.set_active(False)
            else:
               self.pause_button.set_active(False)
         elif userdata == "pause":
            if self.pause_button.get_active():
               self.parentobject.send("command=recorder_pause\n")
            else:
               self.parentobject.send("command=recorder_unpause\n")
            self.parentobject.receive()
      def path2image(self, pathname):
         pixbuf = gtk.gdk.pixbuf_new_from_file_at_size(pathname, 14, 14)
         image = gtk.Image()
         image.set_from_pixbuf(pixbuf)
         image.show()
         return image
      def __init__(self, parent):
         CategoryFrame.__init__(self)
         self.parentobject = parent
         self.stop_pressed = False
         self.recording = False
         hbox = gtk.HBox()
         hbox.set_border_width(3)
         hbox.set_spacing(6)
         self.stop_button = gtk.Button()
         self.record_button = gtk.ToggleButton()
         self.pause_button = gtk.ToggleButton()
         tooltips = parent.scg.parent.tooltips
         for button, gname, signal, tip_text in (
               (self.stop_button,   "stop",  "clicked", ln.stop_rec_tip),
               (self.record_button, "rec",   "toggled", ln.record_tip),
               (self.pause_button,  "pause", "toggled", ln.pause_rec_tip)):
            button.set_size_request(30, -1)
            button.add(self.path2image("".join((pkgdatadir, gname, gfext))))
            button.connect(signal, self.cb_recbuttons, gname)
            hbox.pack_start(button, False, False, 0)
            button.show()
            tooltips.set_tip(button, tip_text)
         self.add(hbox)
         hbox.show()
   class TimeIndicator(gtk.Entry):
      def set_value(self, seconds):
         if self.oldvalue != seconds:
            self.oldvalue = seconds
            minutes, seconds = divmod(seconds, 60)
            hours, minutes = divmod(minutes, 60)
            days, hours = divmod(hours, 24)
            if days > 10:                       # shut off the recorder after 10 days continuous recording
               self.parentobject.record_buttons.stop_button.clicked()
            elif days >= 1:
               self.set_text("%dd:%02d:%02d" % (days, hours, minutes))
            else:
               self.set_text("%02d:%02d:%02d" % (hours, minutes, seconds))
      def button_press_cancel(self, widget, event):
         return True
      def __init__(self, parent):
         self.parentobject = parent
         gtk.Entry.__init__(self)
         self.set_width_chars(7)
         self.set_sensitive(False)
         self.set_editable(False)
         self.oldvalue = -1
         self.set_value(0)
         self.connect("button-press-event", self.button_press_cancel)
         parent.scg.parent.tooltips.set_tip(self, ln.recording_time_tip)
   class SourceDest(CategoryFrame):
      cansave = False
      def set_sensitive(self, boolean):
         self.source_combo.set_sensitive(boolean)
         self.file_chooser_button.set_sensitive(boolean)
      def cb_source_combo(self, widget):
         if widget.get_active() > 0:
            self.streamtab = self.streamtabs[widget.get_active() - 1]
         else:
            self.streamtab = None
         self.parentobject.record_buttons.record_button.set_sensitive(self.streamtab is None or (self.cansave and ((self.streamtab.server_connect.flags() & gtk.SENSITIVE) or self.streamtab.recorder_valid_override)))
      def populate_stream_selector(self, text, tabs):
         self.streamtabs = tabs
         for index in range(len(tabs)):
            self.source_combo.append_text(" ".join((text, str(index + 1))))
         self.source_combo.connect("changed", self.cb_source_combo)
         self.source_combo.set_active(0)
      def cb_new_folder(self, filechooser):
         self.cansave = os.access(filechooser.get_current_folder(), os.W_OK)
         self.source_combo.emit("changed")
      def __init__(self, parent):
         self.parentobject = parent
         CategoryFrame.__init__(self)
         hbox = gtk.HBox()
         hbox.set_spacing(6)
         self.source_combo = gtk.combo_box_new_text()
         self.source_combo.append_text(" FLAC+CUE")
         hbox.pack_start(self.source_combo, False, False, 0)
         self.source_combo.show()
         arrow = gtk.Arrow(gtk.ARROW_RIGHT, gtk.SHADOW_IN)
         hbox.pack_start(arrow, False, False, 0)
         arrow.show()
         self.file_dialog = gtk.FileChooserDialog("", None, gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER, (gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT, gtk.STOCK_OK, gtk.RESPONSE_ACCEPT))
         self.file_dialog.set_do_overwrite_confirmation(True)
         self.file_chooser_button = gtk.FileChooserButton(self.file_dialog)
         self.file_dialog.set_title(ln.save_folder_dialog_title)
         self.file_dialog.connect("current-folder-changed", self.cb_new_folder)
         self.file_dialog.set_current_folder(os.environ["HOME"])
         hbox.pack_start(self.file_chooser_button, True, True, 0)
         self.file_chooser_button.show()
         self.add(hbox)
         hbox.show()
         parent.scg.parent.tooltips.set_tip(self.source_combo, ln.rec_source_tip)
         parent.scg.parent.tooltips.set_tip(self.file_chooser_button, ln.rec_directory_tip)
   def send(self, string_to_send):
      Tab.send(self, "dev_type=recorder\n" + string_to_send)
   def receive(self):
      return Tab.receive(self)
   def show_indicator(self, colour):
      Tab.show_indicator(self, colour)
      self.scg.parent.recording_panel.indicator[self.numeric_id].set_indicator(colour)
      
      
   def __init__(self, scg, numeric_id, indicator_lookup):
      Tab.__init__(self, scg, numeric_id, indicator_lookup)
      self.scg = scg
      self.show_indicator("clear")
      self.tab_type = "recorder"
      hbox = gtk.HBox()
      hbox.set_spacing(10)
      self.pack_start(hbox, False, False, 0)
      hbox.show()
      self.source_dest = self.SourceDest(self)
      hbox.pack_start(self.source_dest, True, True, 0)
      self.source_dest.show()
      self.time_indicator = self.TimeIndicator(self)
      hbox.pack_start(self.time_indicator, False, False, 0)
      self.time_indicator.show()
      self.record_buttons = self.RecordButtons(self)
      hbox.pack_start(self.record_buttons, False, False, 0)
      self.record_buttons.show()
      self.objects = {  "recording_source": (self.source_dest.source_combo, "active"),
                        "recording_directory": (self.source_dest.file_dialog, "directory") }

class TabFrame(ModuleFrame):
   def __init__(self, scg, frametext, q_tabs, tabtype, path, indicatorlist, file_extension, tab_tip_text):
      ModuleFrame.__init__(self, frametext)
      self.notebook = gtk.Notebook()
      self.notebook.set_border_width(8)
      self.vbox.add(self.notebook)
      self.notebook.show()
      self.tabs = []
      self.indicator_image_qty = len(indicatorlist)
      for index in range(q_tabs):
         labelbox = gtk.HBox()
         labelbox.set_spacing(3)
         numlabel = gtk.Label(str(index + 1))
         labelbox.add(numlabel)
         numlabel.show()
         indicator_lookup = {}
         for colour, indicator in indicatorlist:
            image = gtk.Image()
            pixbuf = gtk.gdk.pixbuf_new_from_file_at_size("".join((path, indicator, file_extension)), 16, 16)
            image.set_from_pixbuf(pixbuf)
            labelbox.add(image)
            indicator_lookup[colour] = image
         self.tabs.append(tabtype(scg, index, indicator_lookup))
         self.notebook.append_page(self.tabs[-1], labelbox)
         labelbox.show()
         scg.parent.tooltips.set_tip(labelbox, tab_tip_text)

class StreamTabFrame(TabFrame):
   def forall(self, widget, f, *args):
      for cb, tab in zip(self.togglelist, self.tabs):
         if cb.get_active():
            f(tab, *args)

   def cb_metadata_group(self, tab):
      tab.metadata.set_text(self.metadata_group.get_text())
      tab.metadata_update.clicked()
            
   def cb_connect_toggle(self, tab, val):
      if tab.server_connect.flags() & gtk.SENSITIVE:
         tab.server_connect.set_active(val)

   def cb_kick_group(self, tab):
      tab.kick_incumbent.clicked()
            
   def cb_group_safety(self, widget):
      sens = widget.get_active()
      for each in (self.disconnect_group, self.kick_group):
         each.set_sensitive(sens)
         
   def __init__(self, scg, frametext, q_tabs, tabtype, path, indicatorlist, file_extension, tab_tip_text):
      TabFrame.__init__(self, scg, frametext, q_tabs, tabtype, path, indicatorlist, file_extension, tab_tip_text)

      outerframe = gtk.Frame()
      scg.parent.tooltips.set_tip(outerframe, ln.group_action_tip)
      outerframe.set_border_width(8)
      outerframe.set_shadow_type(gtk.SHADOW_OUT)
      gvbox = gtk.VBox()
      gvbox.set_border_width(8)
      gvbox.set_spacing(8)
      outerframe.add(gvbox)
      gvbox.show()
      hbox = gtk.HBox()
      hbox.set_spacing(5)
      gvbox.pack_start(hbox, False)
      hbox.show()
      self.connect_group = gtk.Button("Connect")
      self.connect_group.connect("clicked", self.forall, self.cb_connect_toggle, True)
      hbox.add(self.connect_group)
      self.connect_group.show()
      frame = gtk.Frame()
      hbox.add(frame)
      frame.show()
      ihbox = gtk.HBox()
      ihbox.set_border_width(3)
      ihbox.set_spacing(6)
      frame.add(ihbox)
      ihbox.show()
      self.group_safety = gtk.CheckButton()
      self.group_safety.connect("toggled", self.cb_group_safety)
      ihbox.pack_start(self.group_safety, False)
      self.group_safety.show()
      self.disconnect_group = gtk.Button("Disconnect")
      self.disconnect_group.connect("clicked", self.forall, self.cb_connect_toggle, False)
      self.disconnect_group.connect("clicked", lambda x: self.group_safety.set_active(False))
      self.disconnect_group.set_sensitive(False)
      ihbox.add(self.disconnect_group)
      self.disconnect_group.show()
      self.kick_group = gtk.Button("Kick Incumbents")
      self.kick_group.connect("clicked", self.forall, self.cb_kick_group)
      self.kick_group.connect("clicked", lambda x: self.group_safety.set_active(False))
      self.kick_group.set_sensitive(False)
      ihbox.add(self.kick_group)
      self.kick_group.show()
      hbox = gtk.HBox()
      hbox.set_spacing(6)
      label = gtk.Label(ln.metadata)
      hbox.pack_start(label, False)
      label.show()
      self.metadata_group = gtk.Entry()
      self.metadata_group.set_text("%s")
      hbox.pack_start(self.metadata_group)
      self.metadata_group.show()
      self.metadata_group_update = gtk.Button(ln.update)
      self.metadata_group_update.connect("clicked", self.forall, self.cb_metadata_group)
      hbox.pack_start(self.metadata_group_update, False)
      self.metadata_group_update.show()
      gvbox.pack_start(hbox, False)
      hbox.show()
      self.vbox.pack_start(outerframe, False)   
      outerframe.show()  
      self.vbox.reorder_child(outerframe, 0)
      self.objects = { "group_metadata": (self.metadata_group, "text") }
      self.togglelist = [gtk.CheckButton(str(x + 1)) for x in range(q_tabs)]
      hbox = gtk.HBox()
      label = gtk.Label(ln.group_action)
      hbox.pack_start(label, False)
      label.show()
      for i, cb in enumerate(self.togglelist):
         hbox.pack_start(cb, False)
         cb.show()
         self.objects["group_toggle_" + str(i + 1)] = (cb, "active")
      spc = gtk.HBox()
      hbox.pack_end(spc, False, False, 2)
      spc.show()
      outerframe.set_label_widget(hbox)
      
      hbox.show()
      

class SourceClientGui:
   server_errmsg = "idjc: idjcsourceclient appears to have crashed -- possible segfault"
   unexpected_reply = "unexpected reply from idjcsourceclient"

   @threadslock
   def monitor(self):
      self.led_alternate = not self.led_alternate
      streaming = recording = False
      # update the recorder LED indicators 
      for rectab in self.recordtabframe.tabs:
         self.send("dev_type=recorder\ntab_id=%d\ncommand=get_report\n" % rectab.numeric_id)
         while 1:
            reply = self.receive()
            if reply == "succeeded" or reply == "failed":
               break
            if reply.startswith("recorder%dreport=" % rectab.numeric_id):
               recorder_state, recorded_seconds = reply.split("=")[1].split(":")
               rectab.show_indicator(("clear", "red", "amber", "clear")[int(recorder_state)])
               rectab.time_indicator.set_value(int(recorded_seconds))
               if recorder_state != "0":
                  recording = True
      update_listeners = False
      l_count = 0
      for streamtab in self.streamtabframe.tabs:
         cp = streamtab.connection_pane
         cp.timer.run()   # obtain connection stats
         if cp.timer.n == 0:
            update_listeners = True
            l_count += cp.listeners
         
         self.send("dev_type=streamer\ntab_id=%d\ncommand=get_report\n" % streamtab.numeric_id)
         reply = self.receive()
         if reply != "failed":
            self.receive()
            if reply.startswith("streamer%dreport=" % streamtab.numeric_id):
               streamer_state, stream_sendbuffer_pc, brand_new = reply.split("=")[1].split(":")
               streamtab.show_indicator(("clear", "amber", "green", "clear")[int(streamer_state)])
               mi = self.parent.stream_indicator[streamtab.numeric_id]
               if (streamer_state == "2"):
                  mi.set_active(True)
                  mi.set_value(int(stream_sendbuffer_pc))
                  if int(stream_sendbuffer_pc) >= 100 and self.led_alternate:
                     if self.parent.prefs_window.recon_config.discard_data.get_active():
                        streamtab.show_indicator("amber")
                        mi.set_flash(True)
                     else:
                        streamtab.server_connect.set_active(False)
                        streamtab.server_connect.set_active(True)
                        print "remade the connection because stream buffer was full"
                  else:
                     mi.set_flash(False)
               else:
                  mi.set_active(False)
                  mi.set_flash(False)
               if brand_new == "1":
                  # connection has just been made, do user requested actions at this time
                  streamtab.start_recorder_action.activate()
                  streamtab.start_player_action.activate()
                  streamtab.reconnection_dialog.deactivate()
               if streamer_state != "0":
                  streaming = True
               elif streamtab.server_connect.get_active():
                  streamtab.server_connect.set_active(False)
                  streamtab.reconnection_dialog.activate()
            else:
               print "sourceclientgui.monitor: bad reply for streamer data:", reply
         else:
            print "sourceclientgui.monitor: failed to get a report from the streamer"
         # the connection start/stop timers are processed here
         if streamtab.start_timer.get_active():
            diff = time.localtime(time.time() - streamtab.start_timer.get_seconds_past_midnight())
            # check hours, minutes, seconds for midnightness
            if not (diff[3] or diff[4] or diff[5]):
               streamtab.start_timer.check.set_active(False)
               if streamtab.kick_before_start.get_active():
                  streamtab.cb_kick_incumbent(None, streamtab.deferred_connect)
               else:
                  streamtab.server_connect.set_active(True)
         if streamtab.stop_timer.get_active():
            diff = time.localtime(int(time.time()) - streamtab.stop_timer.get_seconds_past_midnight())
            if not (diff[3] or diff[4] or diff[5]):
               streamtab.server_connect.set_active(False)
               streamtab.stop_timer.check.set_active(False)
               self.autoshutdown_dialog.present()
         self.is_streaming = streaming
         self.is_recording = recording
         streamtab.reconnection_dialog.run()
      if streaming and self.parent.prefs_window.timer_enable.get_active() and (self.last_message_time + (self.parent.prefs_window.intervaladj.get_value() * 60) < time.time()):
         pw = self.parent.prefs_window
         self.last_message_time = time.time()
         try:
            with open(self.parent.idjcroot + "timer.xchat", "w") as file:
               try:
                  fcntl.flock(file.fileno(), fcntl.LOCK_EX)
                  file.write("d" + str(len(self.parent.prefs_window.timernickentry.get_text().encode("utf-8"))) + ":" + self.parent.prefs_window.timernickentry.get_text().encode("utf-8"))
                  file.write("d" + str(len(self.parent.prefs_window.timerchannelsentry.get_text().encode("utf-8"))) + ":" + self.parent.prefs_window.timerchannelsentry.get_text().encode("utf-8"))
                  cookedmessage = self.parent.prefs_window.timermessageentry.get_text().replace(u"%s", self.parent.metadata).encode("utf-8")
                  file.write("d" + str(len(cookedmessage)) + ":" + cookedmessage)
                  timestr = str(int(time.time()))
                  file.write("d" + str(len(timestr)) + ":" + timestr)
               finally:
                  fcntl.flock(file.fileno(), fcntl.LOCK_UN)
         except IOError:
            print "Problem writing the timer file to disk"

      if update_listeners:
         self.parent.listener_indicator.set_text(str(l_count))
      return True
   def stop_streaming_all(self):
      for streamtab in self.streamtabframe.tabs:
         streamtab.server_connect.set_active(False)
   def stop_recording_all(self):
      for rectab in self.recordtabframe.tabs:
         rectab.record_buttons.stop_button.clicked()
   def stop_test_monitor_all(self):
      for streamtab in self.streamtabframe.tabs:
         streamtab.test_monitor.set_active(False)
   def cleanup(self):
      self.stop_recording_all()
      self.stop_streaming_all()
      self.stop_test_monitor_all()
      gobject.source_remove(self.monitor_source_id)
   def app_exit(self):
      if self.parent.session_loaded:
         self.parent.destroy()
      else:
         self.parent.destroy_hard()
   
   def receive(self):
      if not self.comms_reply_pending:
         print "sourceclientgui.receive: nothing to receive"
         return "failed"
      while 1:
         try:
            reply = self.comms_rply.readline()
         except:
            return "failed"
         if reply.startswith("idjcsc: "):
            reply = reply[8:-1]
            if reply == "succeeded" or reply == "failed":
               self.comms_reply_pending = False
            return reply
         else:
            print self.unexpected_reply, reply
         if reply == "" or reply == "Segmentation Fault\n":
            self.comms_reply_pending = False
            return "failed"
   def send(self, string_to_send):
      while self.comms_reply_pending:   # dump unused replies from previous send
         self.receive()
      if not "tab_id=" in string_to_send:
         string_to_send = "tab_id=-1\n" + string_to_send
      try:
         self.comms_cmd.write(string_to_send + "end\n")
         self.comms_cmd.flush()
         self.comms_reply_pending = True
      except (ValueError, IOError):
         print "sourceclientgui.send: send failed - idjcsourceclient crashed"
         self.source_client_crash_count += 1
         self.source_client_close()
         print self.server_errmsg
         time.sleep(0.5)
         if self.source_client_crash_count == 3:
            print "idjcsourceclient is crashing repeatedly - exiting\n"
            self.app_exit()
         self.source_client_open()
         self.comms_reply_pending = False
      else:
         if self.source_client_crash_count:
            if time.time() > self.uptime + 15.0:
               self.source_client_crash_count -= 1
               self.uptime = time.time()
         
   def new_metadata(self, artist, title, album):
      if artist:
         artist_title = artist + " - " + title
      else:
         artist_title = title
      if not self.parent.prefs_window.mp3_utf8.get_active():
         artist_title_lat1 = artist_title.decode("utf-8", "replace").encode("iso8859-1", "replace")

      self.send("artist=%s\ntitle=%s\nalbum=%s\nartist_title_lat1=%s\ncommand=new_song_metadata\n" % (artist.strip(), title.strip(), album.strip(), artist_title_lat1.strip()))
      if self.receive() == "succeeded":
         print "updated song metadata successfully"

      for tab in self.streamtabframe.tabs:         # Update the custom metadata on all stream tabs.
         tab.metadata_update.clicked()
      
   def source_client_open(self):
      try:
         sp_sc = subprocess.Popen([libexecdir + "idjcsourceclient"], bufsize = 4096, stdin = subprocess.PIPE, stdout = subprocess.PIPE, close_fds = True)
      except Exception, inst:
         print inst
         print "unable to open a pipe to the sourceclient module"
         self.app_exit()
      (self.comms_cmd, self.comms_rply) = (sp_sc.stdin, sp_sc.stdout)
      self.comms_reply_pending = True
      reply = self.receive()
      if reply != "succeeded":
         print self.server_errmsg
         self.app_exit()
      self.send("encoders=%d\nstreamers=%d\nrecorders=%d\ncommand=threads_init\n" % (idjc_config.num_encoders, idjc_config.num_streamers, idjc_config.num_recorders))
      if self.receive() != "succeeded":
         print self.unexpected_reply
         print "failed to initialise threads\n"
         self.app_exit()
      self.send("command=jack_samplerate_request\n")
      reply = self.receive()
      if reply != "failed" and self.receive() == "succeeded":
         sample_rate_string = reply
      else:
         print self.unexpected_reply
         print "failed to obtain the sample rate"
         self.app_exit()
      if not sample_rate_string.startswith("sample_rate="):
         print self.unexpected_reply
         print "sample rate reply contains the following:", sample_rate_string
         self.app_exit()
      self.send("command=encoder_lame_availability\n")
      reply = self.receive()
      if reply != "failed" and self.receive() == "succeeded" and reply.startswith("lame_available="):
         global lameenabled
         if reply[15] == "1":
            lameenabled = 1
         else:
            lameenabled = 0
      else:
         print self.unexpected_reply
         self.app_exit()
      print "threads initialised"
      self.jack_sample_rate = int(sample_rate_string[12:])
      print "jack sample rate is", self.jack_sample_rate
      try:
         for streamtab in self.streamtabframe.tabs:
            streamtab.stream_resample_frame.jack_sample_rate = self.jack_sample_rate
            streamtab.stream_resample_frame.resample_dummy_object.clicked()
            # update the stream tabs with the current jack sample rate
      except (NameError, AttributeError):
         # If this is the initial call the stream tabs will not exist yet.
         pass
      self.uptime = time.time()

   def source_client_close(self):
      try:
         self.comms_cmd
      except:
         pass
      else:
         self.comms_cmd.close()
   def cb_delete_event(self, widget, event, data = None):
      self.window.hide()
      return True
   def save_session_settings(self):
      try:                              # check the following are initilised before proceeding
         tabframes = (self, self.streamtabframe, self.recordtabframe)
      except AttributeError:
         return                         # cancelled save
      try:
         file = open(self.parent.idjc + "s_data", "w")
      except:
         print "error attempting to write file: serverdata"
      else:
         for tabframe in tabframes:
            for tab in tabframe.tabs:
               file.write("".join(("[", tab.tab_type, " ", str(tab.numeric_id), "]\n")))
               for lvalue, (widget, method) in tab.objects.iteritems():
                  if type(method) == tuple:
                     rvalue = widget.__getattribute__(method[1])()
                  elif method == "active":
                     rvalue = str(int(widget.get_active()))
                  elif method == "text":
                     rvalue = widget.get_text()
                  elif method == "value":
                     rvalue = str(widget.get_value())
                  elif method == "expanded":
                     rvalue = str(int(widget.get_expanded()))
                  elif method == "notebookpage":
                     rvalue = str(widget.get_current_page())
                  elif method == "password":
                     rvalue = widget.get_text()
                  elif method == "radioindex":
                     rvalue = str(widget.get_radio_index())
                  elif method == "directory":
                     rvalue = widget.get_filename() or ""
                  elif method == "filename":
                     rvalue = widget.get_filename() or ""
                  else:
                     print "unsupported", lvalue, widget, method
                     continue
                  if method != "password" or self.parent.prefs_window.keeppass.get_active():
                     file.write("".join((lvalue, "=", rvalue, "\n")))
               file.write("\n")
         file.close()
   def load_previous_session(self):
      try:
         file = open(self.parent.idjc + "s_data", "r")
      except:
         print "failed to open serverdata file"
      else:
         tabframe = None
         while 1:
            line = file.readline()
            if line == "":
               break
            else:
               line = line[:-1]         # strip off the newline character
               if line == "":
                  continue
            if line.startswith("[") and line.endswith("]"):
               try:
                  name, numeric_id = line[1:-1].split(" ")
               except:
                  print "malformed line:", line, "in serverdata file"
                  tabframe = None
               else:
                  if name == "server_window":
                     tabframe = self
                  elif name == "streamer":
                     tabframe = self.streamtabframe
                  elif name == "recorder":
                     tabframe = self.recordtabframe
                  else:
                     print "unsupported element:", line, "in serverdata file"
                     tabframe = None
                  if tabframe is not None:
                     try:
                        tab = tabframe.tabs[int(numeric_id)]
                     except:
                        print "unsupported tab number:", line, "in serverdata file"
                        tabframe = None
            else:
               if tabframe is not None:
                  try:
                     lvalue, rvalue = line.split("=", 1)
                  except:
                     print "not a valid key, value pair:", line, "in serverdata file"
                  else:
                     if not lvalue:
                        print "key value is missing:", line, "in serverdata file"        
                     else:
                        try:
                           (widget, method) = tab.objects[lvalue]
                        except KeyError:
                           print "key value not recognised:", line, "in serverdata file"
                        else:
                           try:
                              int_rvalue = int(rvalue)
                           except:
                              int_rvalue = None
                           try:
                              float_rvalue = float(rvalue)
                           except:
                              float_rvalue = None
                           if type(method) == tuple:
                              widget.__getattribute__(method[0])(rvalue)
                           elif method == "active":
                              if int_rvalue is not None:
                                 widget.set_active(int_rvalue)
                           elif method == "expanded":
                              if int_rvalue is not None:
                                 widget.set_expanded(int_rvalue)
                           elif method == "value":
                              if float_rvalue is not None:
                                 widget.set_value(float_rvalue)
                           elif method == "notebookpage":
                              if int_rvalue is not None:
                                 widget.set_current_page(int_rvalue)
                           elif method == "radioindex":
                              if int_rvalue is not None:
                                 widget.set_radio_index(int_rvalue)
                           elif method == "text":
                              widget.set_text(rvalue)
                           elif method == "password":
                              widget.set_text(rvalue)
                           elif method == "directory":
                              if rvalue:
                                 widget.set_current_folder(rvalue)
                           elif method == "filename":
                              if rvalue:
                                 rvalue = widget.set_filename(rvalue)
                           else:
                              print "method", method, "is unsupported at this time hence widget pertaining to", lvalue, "will not be set"
   def cb_configure_event(self, widget, event):
      self.win_x.set_value(event.width)
      self.win_y.set_value(event.height)
   def cb_after_realize(self, widget):
      widget.resize(int(self.win_x), 1)
      self.streamtabframe.connect_group.grab_focus()
      
   def cb_stream_details_expand(self, expander, param_spec, next_expander, sw):
      if expander.get_expanded():
         sw.show()
      else:
         sw.hide()
      
      if expander.get_expanded() == next_expander.get_expanded():
         if not expander.get_expanded():
            self.window.resize((int(self.win_x)), 1)
         else:
            pass
            #self.window.resize((int(self.win_x)), 1000)
      else:
         next_expander.set_expanded(expander.get_expanded())

   def cb_stream_controls_expand(self, expander, param_spec, next_expander, frame, details_shown):
      if expander.get_expanded():
         frame.show()
      else:
         frame.hide()
      
      if expander.get_expanded() == next_expander.get_expanded():
         self.window.resize((int(self.win_x)), 1)
      else:
         next_expander.set_expanded(expander.get_expanded())
      
   def update_metadata(self, text=None, filter=None):
      for tab in self.streamtabframe.tabs:
         if filter is None or str(tab.numeric_id) in filter:
            if text is not None:
               tab.metadata.set_text(text)
            tab.metadata_update.clicked()

   def __init__(self, parent):
      self.parent = parent
      parent.server_window = self
      self.win_x = int_object(100)
      self.win_y = int_object(100)
      self.source_client_crash_count = 0
      self.source_client_open()
      self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
      self.parent.window_group.add_window(self.window)
      self.window.set_title(ln.output_window_title + parent.profile_title)
      self.window.set_destroy_with_parent(True)
      self.window.set_border_width(11)
      self.window.set_resizable(True)
      self.window.set_icon_from_file(pkgdatadir + "icon" + gfext)
      self.window.connect("configure_event", self.cb_configure_event)
      self.window.connect_after("realize", self.cb_after_realize)
      self.window.connect("delete_event", self.cb_delete_event)
      vbox = gtk.VBox()
      vbox.set_spacing(10)
      self.window.add(vbox)
      
      self.recordtabframe = TabFrame(self, ln.record, idjc_config.num_recorders, RecordTab, pkgdatadir, (
                                                                ("clear", "led_unlit_clear_border_64x64"),
                                                                ("amber", "led_lit_amber_black_border_64x64"),
                                                                ("red", "led_lit_red_black_border_64x64")),
                                                                gfext,
                                                                ln.record_tab_tip)
      self.streamtabframe = StreamTabFrame(self, ln.stream, idjc_config.num_streamers, StreamTab, pkgdatadir, (
                                                                ("clear", "led_unlit_clear_border_64x64"),
                                                                ("amber", "led_lit_amber_black_border_64x64"),
                                                                ("green", "led_lit_green_black_border_64x64")),
                                                                gfext,
                                                                ln.stream_tab_tip)
         
      tab = self.streamtabframe.tabs[-1]
      for next_tab in self.streamtabframe.tabs:
         tab.details.connect("notify::expanded", self.cb_stream_details_expand, next_tab.details, tab.details_nb)
         tab.ic_expander.connect("notify::expanded", self.cb_stream_controls_expand, next_tab.ic_expander, tab.ic_frame, self.streamtabframe.tabs[0].details.get_expanded)
         tab = next_tab
                                                                
      self.streamtabframe.set_sensitive(True)
      vbox.pack_start(self.streamtabframe, True, True, 0)
      self.streamtabframe.show()
      for rectab in self.recordtabframe.tabs:
         rectab.source_dest.populate_stream_selector(ln.stream, self.streamtabframe.tabs)
      vbox.pack_start(self.recordtabframe, False, False, 0)
      if idjc_config.num_recorders:
         self.recordtabframe.show()
      vbox.show()
      self.tabs = (self, )                      #
      self.numeric_id = 0                       # pretend to be a tabframe and its tab for save/load purposes
      self.tab_type = "server_window"           #
      self.objects = {  "width" : (self.win_x, "value"),
                        "height": (self.win_y, "value"),
                        "streamer_page": (self.streamtabframe.notebook, "notebookpage"),
                        "recorder_page": (self.recordtabframe.notebook, "notebookpage"),
                        "controls_shown": (self.streamtabframe.tabs[0].ic_expander, "expanded") }
      self.objects.update(self.streamtabframe.objects)
      self.load_previous_session()
      self.is_streaming = False
      self.is_recording = False
      self.led_alternate = False
      self.last_message_time = 0
      self.connection_string = None
      self.is_shoutcast = False

      self.dialog_group = dialog_group()
      self.disconnected_dialog = error_notification_dialog(self.dialog_group, self.parent.window_group, ln.disconnected, ln.unexpected)

      self.autoshutdown_dialog = error_notification_dialog(self.dialog_group, self.parent.window_group, ln.disconnected, ln.autoshutdown)
      
      self.monitor_source_id = gobject.timeout_add(250, self.monitor)
      self.window.realize()   # prevent rendering bug and problems with sizegroups on certain widgets
