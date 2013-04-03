#   sourceclientgui.py: new for version 0.7 this provides the graphical
#   user interface for the new improved streaming module
#   Copyright (C) 2007-2012 Stephen Fairchild (s-fairchild@users.sourceforge.net)
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


import os
import time
import fcntl
import subprocess
import urllib
import urllib2
import base64
import gettext
import traceback
import datetime
import xml.dom.minidom as mdom
import xml.etree.ElementTree
import ctypes
from collections import namedtuple
from threading import Thread

import dbus
import pango
import gtk
import gobject

from idjc import FGlobs, PGlobs
from .utils import string_multireplace
from .gtkstuff import DefaultEntry, threadslock, HistoryEntry
from .gtkstuff import WindowSizeTracker, FolderChooserButton
from .dialogs import *
from .irc import IRCPane
from .format import FormatControl, FormatCodecMPEG
from .tooltips import set_tip
from .prelims import ProfileManager


_ = gettext.translation(FGlobs.package_name, FGlobs.localedir,
                                                        fallback=True).gettext


pm = ProfileManager()


ENCODER_START = 1; ENCODER_STOP = 0

LISTFORMAT = (("check_stats", bool), ("server_type", int), ("host", str),
                            ("port", int), ("mount", str), ("listeners", int),
                            ("login", str), ("password", str))
                            
ListLine = namedtuple("ListLine", " ".join([x[0] for x in LISTFORMAT]))

BLANK_LISTLINE = ListLine(1, 0, "", 8000, "", -1, "", "")

lame_enabled = False

class SmallLabel(gtk.Label):
    """A gtk.Label with small text size."""

    def __init__(self, text=None):
        gtk.Label.__init__(self, text)
        attrlist = pango.AttrList()
        attrlist.insert(pango.AttrSize(8000, 0, 1000000))
        self.set_attributes(attrlist)


class HistoryEntryWithMenu(HistoryEntry):
    def __init__(self):
        HistoryEntry.__init__(self, initial_text=("", "%s", "%r - %t"))
        self.child.connect("populate-popup", self._on_populate_popup)
        
    def _on_populate_popup(self, entry, menu):
        attr_menu_item = gtk.MenuItem(_('Insert Attribute'))
        submenu = gtk.Menu()
        attr_menu_item.set_submenu(submenu)
        for label, subst in zip((_('Artist'), _('Title'), _('Album'),
                                _('Song name')), (u"%r", u"%t", u"%l", u"%s")):
            mi = gtk.MenuItem(label)
            mi.connect("activate", self._on_menu_activate, entry, subst)
            submenu.append(mi)
        
        menu.append(attr_menu_item)
        attr_menu_item.show_all()

    def _on_menu_activate(self, mi, entry, subst):
        p = entry.get_position()
        entry.insert_text(subst, p)
        entry.set_position(p + len(subst))


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
    server_types = (_('Icecast 2 Master'), _('Shoutcast Master'),
                        _('Icecast 2 Stats/Relay'), _('Shoutcast Stats/Relay'))

    def __init__(self, parent_window, tree_selection):
        gtk.Dialog.__init__(self, _('Enter new server connection details'), 
                                        parent_window, gtk.DIALOG_MODAL |
                                        gtk.DIALOG_DESTROY_WITH_PARENT,
                                        (gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT,
                                        gtk.STOCK_OK, gtk.RESPONSE_ACCEPT))
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
                self.set_title(_('Edit existing server connection details') +
                                                                pm.title_extra)
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
        for i, (l, t) in enumerate(zip(self.server_types, (
                                        cap_master, cap_master, True, True))):
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
        self.stats = gtk.CheckButton(
                        _('This server is to be scanned for audience figures'))
        
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
                (_('Server type'), _('Hostname'), _('Port number'), 
                _('Mount point'), _('Login name'), _('Password')), 
                (self.servertype, self.hostname, self.portnumber, 
                self.mountpoint, self.loginname, self.password)):
            row = gtk.HBox()
            row.set_spacing(3)
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
            for entry in (self.hostname, self.mountpoint, self.loginname,
                                                                self.password):
                entry.set_text(entry.get_text().strip())
            self.hostname.set_text(self.hostname.get_text().split("://")[
                                                                    -1].strip())
            self.mountpoint.set_text("/" + self.mountpoint.get_text().lstrip(
                                                                        "/"))

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
            tree_selection.get_tree_view().scroll_to_cell(
                                                    model.get_path(new_iter))
            tree_selection.get_tree_view().get_model().row_changed(
                                            model.get_path(new_iter), new_iter)
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
            stats_url = "http://%s/admin/listclients?mount=%s" % (
                                                        hostport, self.mount)
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
                currentlisteners = shoutcastserver.getElementsByTagName(
                                                            'CURRENTLISTENERS')
                try:
                    self.listeners = int(currentlisteners[
                                                0].firstChild.wholeText.strip())
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
                            self.listeners = int(
                                    listeners[0].firstChild.wholeText.strip())
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
        st = self.get_master_server_type()
        if st:
            config = ListLine(*self.liststore[0])
            p = tab.format_control.props
            sens = (p.cap_icecast, p.cap_shoutcast)[st - 1]
            if sens:
                text = "{0.host}:{0.port}{0.mount}".format(config)
            else:
                text = _("Encoder Format Not Set/Compatible")
        else:
            # TC: Connection button text when no details have been entered.
            text = _('No Master Server Configured')
            sens = False

        tab.server_connect_label.set_text(text)
        tab.server_connect.set_sensitive(sens)
    
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
        self.treeview.get_selection().emit("changed")

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
        if t < 2: # Check if first line contains master server info.
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
                print "ConnectionPane.loader: failed to parse xml data...\n", \
                                                                        xmldata
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
                        raise ValueError(
                            "ConnectionPane.loader: dtype (%s) is unhandled" % \
                                                                        dtype)
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
        getstats = self.stats_always.get_active() or (
                self.stats_ifconnected.get_active() and self.streaming_is_set())
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
                row[5] = -1      # sets listeners text to 'unknown'

    def stats_collate(self):
        count = 0
        for ref, thread in self.stats_rows:
            if ref.valid() == False:
                print "stats_collate:", thread.url, \
                            "invalidated by its removal from the stats list"
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
        self.connection_dialog = ConnectionDialog(self.tab.scg.window,
                                                                tree_selection)
        self.connection_dialog.connect("destroy", self.on_dialog_destroy,
                                                    tree_selection, old_iter)
        self.connection_dialog.show()
        
    def on_edit_clicked(self, button, tree_selection):
        model, iter = tree_selection.get_selected()
        if iter:
            self.connection_dialog = ConnectionDialog(self.tab.scg.window,
                                                                tree_selection)
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
            if self.remove.get_sensitive():
                self.remove.clicked()

    def on_selection_changed(self, tree_selection):
        sens = tree_selection.get_selected()[1] is not None
        if self._streaming_set and tree_selection.path_is_selected((0,)):
            sens = False
        for button in self.require_selection:
            button.set_sensitive(sens)

    def __init__(self, set_tip, tab):
        self.tab = tab
        gtk.VBox.__init__(self)
        self._streaming_set = False
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
        self.liststore.connect("row-changed", 
                                        lambda x, y, z: self.set_button(tab))
        self.set_button(tab)
        self.treeview = gtk.TreeView(self.liststore)
        set_tip(self.treeview, _('A table of servers with which to connect. '
        'Only one master server can be added for the purpose of streaming. All'
        ' other servers will appear below the master server in the list for the'
        ' purpose of stats collection which can be toggled on a per server '
        'basis.'))
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
        col_host = gtk.TreeViewColumn(_('Hostname/IP address'), text_cell_rend,
                                                                        text=2)
        col_host.set_sizing = gtk.TREE_VIEW_COLUMN_FIXED
        col_host.set_expand(True)
        self.treeview.append_column(col_host)
        rend_port = gtk.CellRendererText()
        rend_port.set_property("xalign", 1.0)
        # TC: TCP port number.
        col_port = gtk.TreeViewColumn(_('Port'), rend_port, text = 3)
        col_port.set_sizing = gtk.TREE_VIEW_COLUMN_AUTOSIZE
        col_port.set_alignment(0.5)
        self.treeview.append_column(col_port)
        # TC: Mount point is a technical term in relation to icecast servers.
        col_mount = gtk.TreeViewColumn(_('Mount point       '), text_cell_rend,
                                                                        text=4)
        col_mount.set_sizing = gtk.TREE_VIEW_COLUMN_AUTOSIZE
        self.treeview.append_column(col_mount)
        
        rend_enabled = gtk.CellRendererToggle()
        rend_enabled.connect("toggled", self.individual_listeners_toggle_cb)
        rend_listeners = gtk.CellRendererText()
        # TC: This is the listener count heading.
        col_listeners = gtk.TreeViewColumn(_('Listeners'))
        col_listeners.set_sizing = gtk.TREE_VIEW_COLUMN_AUTOSIZE
        col_listeners.pack_start(rend_enabled, False)
        col_listeners.pack_start(rend_listeners)
        col_listeners.add_attribute(rend_enabled, "active", 0)
        col_listeners.set_cell_data_func(rend_listeners,
                                                    self.listeners_renderer_cb)
        self.treeview.append_column(col_listeners)
        scrolled.add(self.treeview)
        self.treeview.show()

        hbox = gtk.HBox()
        
        self.listener_count_button = gtk.Button()
        ihbox = gtk.HBox()
        set_tip(ihbox, _('The sum total of listeners in this server tab.'))
        pixbuf = gtk.gdk.pixbuf_new_from_file_at_size(
                            FGlobs.pkgdatadir / "listenerphones.png", 20, 16)
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
        self.stats_never = gtk.RadioMenuItem(None, _('Never'))
        self.stats_never.connect("toggled",
                            lambda w: ihbox.set_sensitive(not w.get_active()))
        self.stats_always  = gtk.RadioMenuItem(self.stats_never, _('Always'))
        self.stats_ifconnected = gtk.RadioMenuItem(
                                            self.stats_never, _('If connected'))
        self.stats_ifconnected.set_active(True)
        lcsubmenu.append(self.stats_never)
        lcsubmenu.append(self.stats_always)
        lcsubmenu.append(self.stats_ifconnected)
        lcmenu.show_all()
        
        bbox = gtk.HButtonBox()
        bbox.set_spacing(6)
        bbox.set_layout(gtk.BUTTONBOX_END)
        new = gtk.Button(stock=gtk.STOCK_NEW)
        self.remove = gtk.Button(stock=gtk.STOCK_DELETE)
        edit = gtk.Button(stock=gtk.STOCK_EDIT)
        bbox.add(edit)
        bbox.add(self.remove)
        bbox.add(new)
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
        self.timer = ActionTimer(40, self.stats_commence, self.stats_collate)


class TimeEntry(gtk.HBox):
    """A 24-hour-time entry widget with a checkbutton."""
    
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
        self.set_spacing(3)
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


class AutoAction(gtk.HBox):
    def activate(self):
        if self.get_active():
            for radio, action in self.action_lookup:
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
        return self.spin.get_value()

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
    """Base class for the widget in which each streamer and recorder appears."""
    
    def show_indicator(self, colour):
        thematch = self.indicator_lookup[colour]
        thematch.show()
        for colour, indicator in self.indicator_lookup.iteritems():
            if indicator is not thematch:
                indicator.hide()

    def send(self, stringtosend):
        self.source_client_gui.send("tab_id=%d\n%s" % (
                                                self.numeric_id, stringtosend))

    def receive(self):
        return self.source_client_gui.receive()

    def __init__(self, scg, numeric_id, indicator_lookup):
        self.indicator_lookup = indicator_lookup
        self.numeric_id = numeric_id
        self.source_client_gui = scg
        gtk.VBox.__init__(self)
        gtk.VBox.set_border_width(self, 8)
        gtk.VBox.show(self)


class Troubleshooting(gtk.VBox):
    """Server connection management control widget."""

    def __init__(self):
        gtk.VBox.__init__(self)
        self.set_border_width(6)
        self.set_spacing(8)
        
        hbox = gtk.HBox()
        hbox.set_spacing(4)
        self.custom_user_agent = gtk.CheckButton(_("Custom user agent string"))
        self.custom_user_agent.connect("toggled", self._on_custom_user_agent)
        hbox.pack_start(self.custom_user_agent, False)
        self.user_agent_entry = HistoryEntry()
        self.user_agent_entry.set_sensitive(False)
        hbox.pack_start(self.user_agent_entry)
        self.pack_start(hbox, False)
        set_tip(hbox, _("Set this on the occasion that the server or its "
            "firewall specifically refuses to allow libshout based clients."))
        
        frame = gtk.Frame()
        self.automatic_reconnection = gtk.CheckButton(
                        _("If the connection breaks reconnect to the server"))
        self.automatic_reconnection.set_active(True)
        frame.set_label_widget(self.automatic_reconnection)
        self.pack_start(frame, False)
        
        reconbox = gtk.HBox()
        reconbox.set_border_width(6)
        reconbox.set_spacing(4)
        frame.add(reconbox)
        # TC: Label for a comma separated list of delay times.
        reconlabel = gtk.Label(_("Delay times"))
        reconbox.pack_start(reconlabel, False)
        self.reconnection_times = HistoryEntry(initial_text=("10,10,60", "5"),
                                                            store_blank=False)
        set_tip(self.reconnection_times, _("A comma separated list of delays"
            " in seconds between reconnection attempts. Note that bad values"
            " or values less than 5 will be interpreted as 5."))
        reconbox.pack_start(self.reconnection_times, True)
        self.reconnection_repeat = gtk.CheckButton(_("Repeat"))
        set_tip(self.reconnection_repeat, 
                            _("Repeat the sequence of delays indefinitely."))
        reconbox.pack_start(self.reconnection_repeat, False)
        # TC: User specifies no dialog box to be shown.
        self.reconnection_quiet = gtk.CheckButton(_("Quiet"))
        set_tip(self.reconnection_quiet,
                _("Keep the reconnection dialogue box hidden at all times."))
        reconbox.pack_start(self.reconnection_quiet, False)
        self.automatic_reconnection.connect("toggled",
                                    self._on_automatic_reconnection, reconbox)
        
        frame = gtk.Frame(" %s " % _("The contingency plan upon the stream "
                                                "buffer becoming full is..."))
        sbfbox = gtk.VBox()
        sbfbox.set_border_width(6)
        sbfbox.set_spacing(1)
        frame.add(sbfbox)
        self.pack_start(frame, False)
        
        self.sbf_discard_audio = gtk.RadioButton(None,
                                _("Discard audio data for as long as needed."))
        self.sbf_reconnect = gtk.RadioButton(self.sbf_discard_audio,
                    _("Assume the connection is beyond saving and reconnect."))
        for each in (self.sbf_discard_audio, self.sbf_reconnect):
            sbfbox.pack_start(each, True, False)
        
        self.show_all()
        
        self.objects = {"custom_user_agent": (self.custom_user_agent, "active"),
            "user_agent_entry": (self.user_agent_entry, "history"),
            "automatic_reconnection": (self.automatic_reconnection, "active"),
            "reconnection_times": (self.reconnection_times, "history"),
            "reconnection_repeat": (self.reconnection_repeat, "active"),
            "reconnection_quiet": (self.reconnection_quiet, "active"),
            "sbf_reconnect": (self.sbf_reconnect, "active"),
        }
        
    def _on_custom_user_agent(self, widget):
        self.user_agent_entry.set_sensitive(widget.get_active())
        
    def _on_automatic_reconnection(self, widget, reconbox):
        reconbox.set_sensitive(widget.get_active())


class StreamTab(Tab):
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
            set_tip(label, tooltip)
        vbox = gtk.VBox()
        notebook.append_page(vbox, label)
        label.show()
        vbox.show()
        return vbox

    def item_item_layout(self, item_item_pairs, sizegroup):
        """Widget packing method."""
        
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
        """Widget packing method."""
        
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

    def label_item_layout(self, label_item_pairs, sizegroup):
        """Widget packing method."""

        hbox = gtk.HBox()
        vbox_left = gtk.VBox()
        vbox_left.set_spacing(1)
        vbox_right = gtk.VBox()
        vbox_right.set_spacing(1)
        hbox.pack_start(vbox_left, False, False, 0)
        hbox.pack_start(vbox_right, True, True, 0)
        hbox.set_spacing(3)
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

            # Determine the value to user for the user agent.
            if self.troubleshooting.custom_user_agent.get_active():
                entry = self.troubleshooting.user_agent_entry
                user_agent = entry.get_text().strip()
                del entry
            else:
                user_agent = ""
            
            self.troubleshooting.user_agent_entry.get_text().strip()

            self.connection_string = "\n".join((
                    "stream_source=" + str(self.numeric_id),
                    "server_type=" + (
                    "Icecast 2", "Shoutcast")[d["server_type"]],
                    "host=" + d["host"],
                    "port=%d" % d["port"],
                    "mount=" + d["mount"],
                    "login=" + d["login"],
                    "password=" + d["password"],
                    "useragent=" + user_agent,
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

    def start_stop_encoder(self, command):
        """Reference counting starter and stopper for the encoder."""
                
        if command == ENCODER_START:
            self.format_control.start_encoder_rc()
        elif command == ENCODER_STOP:
            self.format_control.stop_encoder_rc()
    
    def server_type_cell_data_func(self, celllayout, cell, model, iter):
        text = model.get_value(iter, 0)
        if text == _('Shoutcast') and lame_enabled == 0:
            cell.set_property("sensitive", False)
        else:
            cell.set_property("sensitive", True)

    
    def cb_metadata(self, widget):
        if self.format_control.finalised:
            fallback = self.metadata_fallback.get_text()
            songname = self.scg.parent.songname.encode("utf-8") or fallback
            table = [("%%", "%")] + zip(("%r", "%t", "%l"), ((
                            getattr(self.scg.parent, x) or fallback) for x in (
                            "artist", "title", "album")))
            table.append(("%s", songname))
            raw_cm = self.metadata.get_text().encode("utf-8", "replace").strip()
            cm = string_multireplace(raw_cm, table)
            
            fdata = self.format_control.get_settings()
            encoding = "utf-8"
            if fdata["family"] == "mpeg" and fdata["codec"] in ("mp2", "mp3", "aac", "aacpv2"):
                if fdata["metadata_mode"] == "utf-8":
                    disp = songname
                else:
                    encoding = "latin1"
                    disp = songname.decode("utf-8").encode(encoding, "replace").decode(encoding)
                if not cm:
                    cm = songname
            elif fdata["family"] == "ogg":
                disp = "[{0[%r]}], [{0[%t]}], [{0[%l]}]".format(dict(table))
            else:
                disp = "no metadata string defined for this stream format: %s %s" % (fdata["family"], fdata["codec"])
            
            if cm:
                cm = cm.decode("utf-8").encode(encoding, "replace")
                disp = cm.decode(encoding)
                
            if fdata["metadata_mode"] == "suppressed":
                disp = _('[Metadata suppressed]')

            self.metadata_display.push(0, disp)
            self.metadata_update.set_relief(gtk.RELIEF_HALF)
            self.scg.send("tab_id=%d\ndev_type=encoder\ncustom_meta=%s\n"
                    "command=new_custom_metadata\n" % (
                    self.numeric_id, cm))
            self.scg.receive()

    def cb_new_metadata_format(self, widget):
        self.metadata_update.set_relief(gtk.RELIEF_NORMAL)  
    
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
            url = "http://" + urllib.quote(srv.host) + ":" + str(srv.port) + \
                            "/admin/killsource?mount=" + urllib.quote(srv.mount)
            auth_handler.add_password("Icecast2 Server", srv.host + ":" + \
                                        str(srv.port), srv.login, srv.password)
            def check_reply(reply):
                try:
                    elem = xml.etree.ElementTree.fromstring(reply)
                except xml.etree.ElementTree.ParseError:
                    return False
                else:
                    rslt = "succeeded" if elem.findtext("return") == "1" else \
                                                                        "failed"
                    print "kick %s: %s" % (rslt, elem.findtext("message"))
                    return rslt == "succeeded"

        elif mode == 2:
            password = self.admin_password_entry.get_text().strip() or \
                                                                srv.password
            url = "http://" + urllib.quote(srv.host) + ":" + str(srv.port) + \
                                                    "/admin.cgi?mode=kicksrc"
            auth_handler.add_password("Shoutcast Server", srv.host + ":" + \
                                            str(srv.port), "admin", password)
            def check_reply(reply):
                # Could go to lengths to check the XML stats here.
                # Thats one whole extra HTTP request.
                print "kick succeeded"
                return True

        opener = urllib2.build_opener(auth_handler)
        opener.addheaders = [('User-agent', 'Mozilla/5.0')]

        def threaded():
            try:
                print url
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
        self.set_spacing(10)
              
        self.ic_expander = gtk.Expander(_('Individual Controls'))
        self.pack_start(self.ic_expander, False)
        self.ic_expander.show()
                
        self.ic_frame = gtk.Frame()
        ic_vbox = gtk.VBox()
        ic_vbox.set_border_width(10)
        ic_vbox.set_spacing(10)
        self.ic_frame.add(ic_vbox)
        ic_vbox.show()
        
        hbox = gtk.HBox()
        hbox.set_spacing(6)
        self.server_connect = gtk.ToggleButton()
        set_tip(self.server_connect, _('Connect to or disconnect from the radio'
            ' server. If the button does not stay in, the connection failed '
            'for some reason.\n\nIf the button is greyed out it means your '
            'settings within the \'Connections\' and \'Format\' sections are '
            'either incompatible with one another or are incomplete.\n\n'
            'In order to stream a master server needs to be specified in the '
            'configuration section below and must be capable of handling the '
            'chosen streaming format.'))
        self.server_connect.connect("toggled", self.cb_server_connect)
        hbox.pack_start(self.server_connect, True, True, 0)
        self.server_connect_label = gtk.Label()
        self.server_connect_label.set_ellipsize(pango.ELLIPSIZE_MIDDLE)
        self.server_connect.add(self.server_connect_label)
        self.server_connect_label.show()
        self.server_connect.show()
        
        # TC: Kick whoever is on the server.
        self.kick_incumbent = gtk.Button(_('Kick Source'))
        self.kick_incumbent.connect("clicked", self.cb_kick_incumbent)
        set_tip(self.kick_incumbent, _('This will disconnect whoever is '
                'currently using the server, freeing it up for personal use.'))
        hbox.pack_start(self.kick_incumbent, False)
        self.kick_incumbent.show()
        
        ic_vbox.pack_start(hbox, False)
        hbox.show()
        
        hbox = gtk.HBox()
        hbox.set_spacing(6)
        label = gtk.Label(_('Connection timer:'))
        hbox.pack_start(label, False)
        label.show()
        
        self.start_timer = TimeEntry(_('Begin'))
        set_tip(self.start_timer, _('Automatically connect to the server at '
                    'a specific time in 24 hour format, midnight being 00:00'))
        hbox.pack_start(self.start_timer, False)
        self.start_timer.show()
        
        self.kick_before_start = gtk.CheckButton(_('With kick'))
        self.kick_before_start.set_sensitive(False)
        set_tip(self.kick_before_start, _('Disconnect whoever is using the '
                                            'server just before start time.'))
        hbox.pack_start(self.kick_before_start, False)
        self.kick_before_start.show()

        self.start_timer.check.connect("toggled", lambda w: 
                        self.kick_before_start.set_sensitive(w.props.active))

        
        self.stop_timer = TimeEntry(_('End'))
        set_tip(self.stop_timer, _('Automatically disconnect from the server '
                                    'at a specific time in 24 hour format.'))
        hbox.pack_end(self.stop_timer, False)
        self.stop_timer.show()
        
        
        ic_vbox.pack_start(hbox, False, False, 0)
        hbox.show()
        
        hbox = gtk.HBox() 
        hbox.set_spacing(10)
        label = gtk.Label(_('At connect:'))
        hbox.pack_start(label, False, False, 0)
        label.show()
        # TC: [x] Start player (*) 1 ( ) 2
        self.start_player_action = AutoAction(_('Start player'), (
                ("1", self.source_client_gui.parent.player_left.play.clicked),
                ("2", self.source_client_gui.parent.player_right.play.clicked)))
        hbox.pack_start(self.start_player_action, False, False, 0)
        self.start_player_action.show()
        set_tip(self.start_player_action, _('Have one of the players start '
        'automatically when a radio server connection is successfully made.'))
        if PGlobs.num_recorders:
            vseparator = gtk.VSeparator()
            hbox.pack_start(vseparator, True, False, 0)
            vseparator.show()
        
        # TC: [x] Start recorder (*) 1 ( ) 2
        self.start_recorder_action = AutoAction(_('Start recorder'), [
            (chr(ord("1") + i), t.record_buttons.record_button.activate)
            for i, t in enumerate(self.source_client_gui.recordtabframe.tabs)])
        
        hbox.pack_end(self.start_recorder_action, False, False, 0)
        if PGlobs.num_recorders:
            self.start_recorder_action.show()
        set_tip(self.start_recorder_action, _('Have a recorder start '
        'automatically when a radio server connection is successfully made.'))
        ic_vbox.pack_start(hbox, False, False, 0)
        hbox.show()

        frame = gtk.Frame(" %s " % _('Metadata'))
        table = gtk.Table(3, 3)
        table.set_border_width(6)
        table.set_row_spacings(1)
        table.set_col_spacings(4)
        frame.add(table)
        table.show()
        ic_vbox.pack_start(frame, False)
        frame.show()
        
        format_label = SmallLabel(_('Format String'))
        # TC: Label for the metadata fallback value.
        fallback_label = SmallLabel(_('Fallback'))
        self.metadata = HistoryEntryWithMenu()
        self.metadata.child.connect("changed", self.cb_new_metadata_format)
        self.metadata_fallback = gtk.Entry()
        self.metadata_fallback.set_width_chars(10)
        self.metadata_fallback.set_text("<Unknown>")
        self.metadata_update = gtk.Button()
        image = gtk.image_new_from_stock(gtk.STOCK_EXECUTE, gtk.ICON_SIZE_MENU)
        self.metadata_update.set_image(image)
        image.show()
        self.metadata_update.connect("clicked", self.cb_metadata)
        self.metadata_display = gtk.Statusbar()
        self.metadata_display.set_has_resize_grip(False)

        set_tip(self.metadata, _('You can enter text to accompany the stream '
            'here and can specify placemarkers %r %t %l %s for the artist, '
            'title, album, and songname respectively, or leave this text '
            'field blank to use the default metadata.\n\nSongname (%s) is '
            'derived from the filename in the absence of sufficient metadata,'
            ' while the other placemarkers will use the fallback text to the'
            ' right.\n\nWhen blank, Ogg streams will use the standard Vorbis'
            ' tags and mp3 will use %s.'))
        set_tip(self.metadata_fallback, _('The fallback text to use when %r %t'
            ' %l metadata is unavailable. See the format string to the left.'))
        set_tip(self.metadata_update, _('Metadata normally updates only on song'
            ' title changes but you can force an immediate update here.'))
        
        x = gtk.EXPAND
        f = gtk.FILL
        s = gtk.SHRINK
        arrangement = (((format_label, x|f), (fallback_label, s|f)),
                ((self.metadata, x|f),
                (self.metadata_fallback, s), (self.metadata_update, s)))
        
        for r, row in enumerate(arrangement):
            for c, (child, xopt) in enumerate(row):
                table.attach(child, c, c + 1, r, r + 1, xopt, s|f)
                child.show()
        table.attach(self.metadata_display, 0, 3, 2, 3, x|f, s|f)
        self.metadata_display.show()

        self.pack_start(self.ic_frame, False)
        
        self.details = gtk.Expander(_('Configuration'))
        set_tip(self.details, _('The controls for configuring a stream.'))
        self.pack_start(self.details, False)
        self.details.show()
      
        self.details_nb = gtk.Notebook()
        self.pack_start(self.details_nb, False)
        
        self.connection_pane = ConnectionPane(set_tip, self)
        label = gtk.Label(_('Connection'))
        self.details_nb.append_page(self.connection_pane, label)
        label.show()
        self.connection_pane.show()
         
        label = gtk.Label(_('Format'))  # Format box
        self.format_control = FormatControl(self.send, self.receive)
        self.details_nb.append_page(self.format_control, label)
        self.format_control.connect("notify::cap-icecast", lambda a, b: self.connection_pane.set_button(self))
        self.format_control.connect("notify::cap-shoutcast", lambda a, b: self.connection_pane.set_button(self))
        label.show()
        
        vbox = gtk.VBox()
        # TC: Tab heading. User can enter information about the stream here.
        label = gtk.Label(_('Stream Info'))
        self.details_nb.append_page(vbox, label)
        label.show()
        vbox.show()
        self.dj_name_entry = DefaultEntry("eyedeejaycee")
        set_tip(self.dj_name_entry, _('Enter your DJ name or station name here.'
        ' Typically this information will be displayed by listener clients.'))
        self.listen_url_entry = DefaultEntry("http://www.example.com")
        set_tip(self.listen_url_entry, _('The URL of your radio station. This'
            ' and the rest of the information below is intended for display'
            ' on a radio station listings website.'))
        self.description_entry = gtk.Entry()
        set_tip(self.description_entry,
                                    _('A description of your radio station.'))
        genre_entry_box = gtk.HBox()
        genre_entry_box.set_spacing(12)
        self.genre_entry = DefaultEntry("Misc")
        set_tip(self.genre_entry,
                                _('The musical genres you are likely to play.'))
        genre_entry_box.pack_start(self.genre_entry, True, True, 0)
        self.genre_entry.show()
        self.make_public = gtk.CheckButton(_('Make Public'))
        set_tip(self.make_public, _('Publish your radio station on a listings'
            ' website. The website in question will depend on how the server'
            ' to which you connect is configured.'))
        genre_entry_box.pack_start(self.make_public, False, False, 0)
        self.make_public.show()
        info_sizegroup = gtk.SizeGroup(gtk.SIZE_GROUP_VERTICAL)
        stream_details_pane = self.label_item_layout((
            # TC: The DJ or Stream name.
            (_('DJ name'), self.dj_name_entry),
            (_('Listen URL'), self.listen_url_entry),
            # TC: Station description.
            (_('Description'), self.description_entry),
            (_('Genre(s)'), genre_entry_box)
            ), info_sizegroup)
        stream_details_pane.set_border_width(10)
        vbox.add(stream_details_pane)
        stream_details_pane.show()

        vbox = gtk.VBox()
        alhbox = gtk.HBox()
        alhbox.set_border_width(10)
        alhbox.set_spacing(3)
        label = gtk.Label(_('Master server admin password'))
        alhbox.pack_start(label, False)
        label.show()
        self.admin_password_entry = gtk.Entry()
        self.admin_password_entry.set_visibility(False)
        set_tip(self.admin_password_entry, _("This is for kick and stats on "
            "Shoutcast master servers that have an administrator password. For"
            " those that don't leave this blank (the source password is"
            " sufficient for those)."))
        alhbox.pack_start(self.admin_password_entry)
        self.admin_password_entry.show()
        vbox.pack_start(alhbox, False)
        alhbox.show()
              
        frame = CategoryFrame(" %s " % _('Contact Details'))
        frame.set_shadow_type(gtk.SHADOW_NONE)
        frame.set_border_width(0)
        self.irc_entry = gtk.Entry()
        set_tip(self.irc_entry,
                    _('Internet Relay Chat connection info goes here.'))
        self.aim_entry = gtk.Entry()
        set_tip(self.aim_entry,
                    _('Connection info for AOL instant messenger goes here.'))
        self.icq_entry = gtk.Entry()
        set_tip(self.icq_entry,
                    _('ICQ instant messenger connection info goes here.'))
        contact_sizegroup = gtk.SizeGroup(gtk.SIZE_GROUP_VERTICAL)
        contact_details_pane = self.label_item_layout((
                                                 (_('IRC'), self.irc_entry),
                                                 (_('AIM'), self.aim_entry),
                                                 (_('ICQ'), self.icq_entry)
                                                 ), contact_sizegroup)
        contact_details_pane.set_border_width(10)
        frame.add(contact_details_pane)
        contact_details_pane.show()
        
        vbox.pack_start(frame, False)
        frame.show_all()

        label = gtk.Label(_('Extra Shoutcast'))
        self.details_nb.append_page(vbox, label)
        label.show()
        vbox.show()
        
        label = gtk.Label(_("Troubleshooting"))
        self.troubleshooting = Troubleshooting()
        self.details_nb.append_page(self.troubleshooting, label)
        label.show()
        
        label = gtk.Label("IRC")
        self.ircpane = IRCPane()
        self.details_nb.append_page(self.ircpane, label)
        label.show()

        self.details_nb.set_current_page(0)
        
        self.objects = {
            "metadata"    : (self.metadata, "history"),
            "metadata_fb" : (self.metadata_fallback, "text"),
            "prekick"     : (self.kick_before_start, "active"),
            "connections" : (self.connection_pane, ("loader", "saver")),
            "stats_never" : (self.connection_pane.stats_never, "active"),
            "stats_always": (self.connection_pane.stats_always, "active"),
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
            "action_record_which" : (self.start_recorder_action, "radioindex"),
            "irc_data" : (self.ircpane, "marshall"),
            "format_data" : (self.format_control, "marshall"),
            "details_nb" : (self.details_nb, "current_page"),
        }
                                
        self.objects.update(self.troubleshooting.objects)
                                
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
   
                        filename = datetime.datetime.today().strftime(self.parentobject.scg.parent.prefs_window.recorder_filename.get_text().strip())
                        table = (("$$", "$"), ("$r", "%02d" % (self.parentobject.numeric_id + 1)))
                        filename = string_multireplace(filename, table)
                        self.parentobject.send("record_source=%d\n"
                            "record_filename=%s\n"
                            "record_folder=%s\ncommand=recorder_start\n" % (
                            num_id, filename,
                            sd.file_chooser_button.get_current_folder()))
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
                            control = self.parentobject.source_dest.streamtab
                            control.start_stop_encoder(ENCODER_STOP)
                            del control
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
            for button, gname, signal, tip_text in (
                    (self.stop_button,  "stop",  "clicked",
                    _('Stop recording.')),
                    (self.record_button, "rec", "toggled",
                    _('Start recording.\n\nIf this button is greyed out it '
                    'could mean either the encoder settings are not valid or '
                    'write permission is not granted on the selected folder.'
                    )),
                    (self.pause_button,  "pause", "toggled",
                                                        _('Pause recording.'))):
                button.set_size_request(30, -1)
                button.add(self.path2image(FGlobs.pkgdatadir / (
                                                            gname + ".png")))
                button.connect(signal, self.cb_recbuttons, gname)
                hbox.pack_start(button, False, False, 0)
                button.show()
                set_tip(button, tip_text)
            self.add(hbox)
            hbox.show()

    class TimeIndicator(gtk.Entry):
        def set_value(self, seconds):
            if self.oldvalue != seconds:
                self.oldvalue = seconds
                minutes, seconds = divmod(seconds, 60)
                hours, minutes = divmod(minutes, 60)
                days, hours = divmod(hours, 24)
                if days > 10:  # Shut off the recorder after 10 days recording.
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
            set_tip(self, _('Recording time elapsed.'))

    class SourceDest(CategoryFrame):
        cansave = False

        def set_sensitive(self, boolean):
            self.source_combo.set_sensitive(boolean)
            self.file_chooser_button.set_sensitive(boolean)

        def cb_source_combo(self, widget):
            sens = self.parentobject.record_buttons.record_button.set_sensitive
            
            if widget.get_active() > 0:
                self.streamtab = self.streamtabs[widget.get_active() - 1]
                sens(self.cansave and self.streamtab.format_control.props.cap_recordable)
            else:
                self.streamtab = None
                sens(self.cansave and self.source_store[self.source_combo.get_active()][1])

        def populate_stream_selector(self, text, tabs):
            self.streamtabs = tabs
            for index in range(len(tabs)):
                self.source_store.append((" ".join((text, str(index + 1))), 1))
            self.source_combo.connect("changed", self.cb_source_combo)
            self.source_combo.set_active(0)
            for tab in tabs:
                tab.format_control.connect("notify::cap-recordable",
                                lambda w, v: self.source_combo.emit("changed"))

        def cb_new_folder(self, folder_chooser_button, path):
            self.cansave = os.access(path, os.W_OK)
            self.source_combo.emit("changed")

        def __init__(self, parent):
            self.parentobject = parent
            CategoryFrame.__init__(self)
            hbox = gtk.HBox()
            hbox.set_spacing(6)
            
            self.source_store = gtk.ListStore(str, int)
            self.source_combo = gtk.ComboBox(self.source_store)
            rend = gtk.CellRendererText()
            self.source_combo.pack_start(rend)
            self.source_combo.set_attributes(rend, text=0, sensitive=1)
            self.source_store.append((" FLAC+CUE", FGlobs.flacenabled))
            hbox.pack_start(self.source_combo, False, False, 0)
            self.source_combo.show()
            arrow = gtk.Arrow(gtk.ARROW_RIGHT, gtk.SHADOW_IN)
            hbox.pack_start(arrow, False, False, 0)
            arrow.show()
            file_dialog = gtk.FileChooserDialog("", None,
                    gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER, (gtk.STOCK_CANCEL,
                    gtk.RESPONSE_REJECT, gtk.STOCK_OK, gtk.RESPONSE_ACCEPT))
            # TC: Dialog title bar text.
            file_dialog.set_title(_('Select the folder to record to'
                                                            ) + pm.title_extra)
            file_dialog.set_do_overwrite_confirmation(True)
            self.file_chooser_button = FolderChooserButton(file_dialog)
            self.file_chooser_button.connect("current-folder-changed",
                                                            self.cb_new_folder)
            self.file_chooser_button.set_current_folder(os.environ["HOME"])
            hbox.pack_start(self.file_chooser_button, True, True, 0)
            self.file_chooser_button.show()
            self.add(hbox)
            hbox.show()
            set_tip(self.source_combo, _("Choose which stream to record or the"
                " 24 bit FLAC option. If the stream isn't already running the"
                " encoder will be started automatically using whatever settings"
                " are currently configured."))
            set_tip(self.file_chooser_button, _('Choose which directory you '
            'want to save to. All file names will be in a timestamp format '
            'and have either an oga, mp3, or flac file extension. Important:'
            ' you need to select a directory to which you have adequate '
            'write permission.'))

    def send(self, string_to_send):
        Tab.send(self, "dev_type=recorder\n" + string_to_send)

    def receive(self):
        return Tab.receive(self)

    def show_indicator(self, colour):
        Tab.show_indicator(self, colour)
        self.scg.parent.recording_panel.indicator[self.numeric_id
                                                        ].set_indicator(colour)
        
    def __init__(self, scg, numeric_id, indicator_lookup):
        Tab.__init__(self, scg, numeric_id, indicator_lookup)
        self.scg = scg
        self.numeric_id = numeric_id
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
        self.objects = {
            "recording_source": (self.source_dest.source_combo, "active"),
            "recording_directory": (self.source_dest.file_chooser_button, "directory")
        }


class TabFrame(ModuleFrame):
    def __init__(self, scg, frametext, q_tabs, tabtype, indicatorlist,
                                                                tab_tip_text):
        ModuleFrame.__init__(self, " %s " % frametext)
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
                pixbuf = gtk.gdk.pixbuf_new_from_file_at_size(
                            FGlobs.pkgdatadir / (indicator + ".png"), 16, 16)
                image.set_from_pixbuf(pixbuf)
                labelbox.add(image)
                indicator_lookup[colour] = image
            self.tabs.append(tabtype(scg, index, indicator_lookup))
            self.notebook.append_page(self.tabs[-1], labelbox)
            labelbox.show()
            set_tip(labelbox, tab_tip_text)


class StreamTabFrame(TabFrame):
    def forall(self, widget, f, *args):
        for cb, tab in zip(self.togglelist, self.tabs):
            if cb.get_active():
                f(tab, *args)

    def cb_metadata_group_set(self, tab):
        tab.metadata.set_text(self.metadata_group.get_text())
                
    def cb_metadata_group_update(self, tab):
        self.cb_metadata_group_set(tab)
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
            
    def __init__(self, scg, frametext, q_tabs, tabtype, indicatorlist,
                                                                tab_tip_text):
        TabFrame.__init__(self, scg, frametext, q_tabs, tabtype,
                                                    indicatorlist, tab_tip_text)

        outerframe = gtk.Frame()
        set_tip(outerframe,
                        _('Perform operations on multiple servers in unison.'))
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
        self.connect_group = gtk.Button(_("Connect"))
        self.connect_group.connect("clicked", self.forall,
                                                self.cb_connect_toggle, True)
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
        self.disconnect_group = gtk.Button(_("Disconnect"))
        self.disconnect_group.connect("clicked", self.forall,
                                                self.cb_connect_toggle, False)
        self.disconnect_group.connect("clicked", 
                                lambda x: self.group_safety.set_active(False))
        self.disconnect_group.set_sensitive(False)
        ihbox.add(self.disconnect_group)
        self.disconnect_group.show()
        self.kick_group = gtk.Button(_("Kick Sources"))
        self.kick_group.connect("clicked", self.forall, self.cb_kick_group)
        self.kick_group.connect("clicked",
                                lambda x: self.group_safety.set_active(False))
        self.kick_group.set_sensitive(False)
        ihbox.add(self.kick_group)
        self.kick_group.show()
        hbox = gtk.HBox()
        hbox.set_spacing(6)
        label = gtk.Label("%s " % _('Metadata:'))
        hbox.pack_start(label, False)
        label.show()
        self.metadata_group = HistoryEntryWithMenu()
        hbox.pack_start(self.metadata_group)
        self.metadata_group.show()
        self.metadata_group_set = gtk.Button()
        image = gtk.image_new_from_stock(gtk.STOCK_ADD, gtk.ICON_SIZE_MENU)
        self.metadata_group_set.set_image(image)
        image.show()
        self.metadata_group_set.connect("clicked", self.forall,
                                                    self.cb_metadata_group_set)
        hbox.pack_start(self.metadata_group_set, False)
        self.metadata_group_set.show()
        self.metadata_group_update = gtk.Button()
        image = gtk.image_new_from_stock(gtk.STOCK_EXECUTE, gtk.ICON_SIZE_MENU)
        self.metadata_group_update.set_image(image)
        image.show()
        self.metadata_group_update.connect("clicked", self.forall,
                                                self.cb_metadata_group_update)
        hbox.pack_start(self.metadata_group_update, False)
        self.metadata_group_update.show()
        gvbox.pack_start(hbox, False)
        hbox.show()
        self.vbox.pack_start(outerframe, False) 
        outerframe.show()  
        self.vbox.reorder_child(outerframe, 0)
        self.objects = { "group_metadata": (self.metadata_group, "history") }
        self.togglelist = [gtk.CheckButton(str(x + 1)) for x in range(q_tabs)]
        hbox = gtk.HBox()
        label = gtk.Label(" %s " % _('Group Controls'))
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
        

class SourceClientGui(dbus.service.Object):
    unexpected_reply = "unexpected reply from idjcsourceclient"

    @dbus.service.method(dbus_interface=PGlobs.dbus_bus_basename)
    def new_plugin_started(self):
        print "streamstate_cache purge"
        self._streamstate_cache = {}

    def monitor(self):
        self.led_alternate = not self.led_alternate
        streaming = recording = False
        # update the recorder LED indicators 
        for rectab in self.recordtabframe.tabs:
            self.send("dev_type=recorder\ntab_id=%d\ncommand=get_report\n" %
                                                            rectab.numeric_id)
            while 1:
                reply = self.receive()
                if reply == "succeeded" or reply == "failed":
                    break
                if reply.startswith("recorder%dreport=" % rectab.numeric_id):
                    recorder_state, recorded_seconds = reply.split("=")[
                                                                1].split(":")
                    rectab.show_indicator(("clear", "red", "amber", "clear")[
                                                        int(recorder_state)])
                    rectab.time_indicator.set_value(int(recorded_seconds))
                    if recorder_state != "0":
                        recording = True
        update_listeners = False
        l_count = 0
        for streamtab in self.streamtabframe.tabs:
            cp = streamtab.connection_pane
            cp.timer.run()  # obtain connection stats
            if cp.timer.n == 0:
                update_listeners = True
                l_count += cp.listeners
            
            self.send("dev_type=streamer\ntab_id=%d\ncommand=get_report\n" % \
                                                        streamtab.numeric_id)
            reply = self.receive()
            if reply != "failed":
                self.receive()
                if reply.startswith("streamer%dreport=" % streamtab.numeric_id):
                    streamer_state, stream_sendbuffer_pc, brand_new = \
                                                    reply.split("=")[1].split(":")
                    state = int(streamer_state)
                    self._handle_streamstate(streamtab.numeric_id,
                                            int(state > 1), streamtab)
                    streamtab.show_indicator(
                                    ("clear", "amber", "green", "clear")[state])
                    streamtab.ircpane.connections_controller.set_stream_active(
                                                                    state > 1)
                    mi = self.parent.stream_indicator[streamtab.numeric_id]
                    if (streamer_state == "2"):
                        mi.set_active(True)
                        mi.set_value(int(stream_sendbuffer_pc))
                        if int(stream_sendbuffer_pc
                                                ) >= 100 and self.led_alternate:
                            tshoot = streamtab.troubleshooting
                            if tshoot.sbf_discard_audio.get_active():
                                streamtab.show_indicator("amber")
                                mi.set_flash(True)
                            else:
                                streamtab.server_connect.set_active(False)
                                streamtab.server_connect.set_active(True)
                                print "remade the connection because stream " \
                                                            "buffer was full"
                            del tshoot
                        else:
                            mi.set_flash(False)
                    else:
                        mi.set_active(False)
                        mi.set_flash(False)
                    if brand_new == "1":
                        # Streamer connected triggers.
                        streamtab.start_recorder_action.activate()
                        streamtab.start_player_action.activate()
                        streamtab.reconnection_dialog.deactivate()
                    if streamer_state != "0":
                        streaming = True
                    elif streamtab.server_connect.get_active():
                        streamtab.server_connect.set_active(False)
                        streamtab.reconnection_dialog.activate()
                else:
                    print "sourceclientgui.monitor: bad reply for" \
                                                    " streamer data:", reply
            else:
                print "sourceclientgui.monitor:" \
                                    " failed to get a report from the streamer"
            # the connection start/stop timers are processed here
            if streamtab.start_timer.get_active():
                diff = time.localtime(time.time() - \
                            streamtab.start_timer.get_seconds_past_midnight())
                # check hours, minutes, seconds for midnightness
                if not (diff[3] or diff[4] or diff[5]):
                    streamtab.start_timer.check.set_active(False)
                    if streamtab.kick_before_start.get_active():
                        streamtab.cb_kick_incumbent(None,
                                                    streamtab.deferred_connect)
                    else:
                        streamtab.server_connect.set_active(True)
            if streamtab.stop_timer.get_active():
                diff = time.localtime(int(time.time()) - \
                            streamtab.stop_timer.get_seconds_past_midnight())
                if not (diff[3] or diff[4] or diff[5]):
                    streamtab.server_connect.set_active(False)
                    streamtab.stop_timer.check.set_active(False)
                    self.autoshutdown_dialog.present()
            self.is_streaming = streaming
            self.is_recording = recording
            streamtab.reconnection_dialog.run()
        if update_listeners:
            self.parent.listener_indicator.set_text(str(l_count))
        return True

    def _handle_streamstate(self, numeric_id, connected, streamtab):
        cache = self._streamstate_cache
        
        if cache is not None and (numeric_id not in cache or cache[numeric_id] != connected):
            cache[numeric_id] = connected
            self.streamstate_changed(numeric_id, connected,
                                    streamtab.server_connect_label.get_text())

    @dbus.service.signal(dbus_interface=PGlobs.dbus_bus_basename, signature="uus")
    def streamstate_changed(self, numeric_id, state, where):
        pass
        
    def stop_streaming_all(self):
        for streamtab in self.streamtabframe.tabs:
            streamtab.server_connect.set_active(False)
    def stop_irc_all(self):
        for streamtab in self.streamtabframe.tabs:
            streamtab.ircpane.connections_controller.cleanup()
    def stop_recording_all(self):
        for rectab in self.recordtabframe.tabs:
            rectab.record_buttons.stop_button.clicked()
    def cleanup(self):
        self.stop_recording_all()
        self.stop_streaming_all()
        self.stop_irc_all()
        gobject.source_remove(self.monitor_source_id)
        self.monitor()
    def app_exit(self):
        if self.parent.session_loaded:
            self.parent.destroy()
        else:
            self.parent.destroy_hard()
    
    def receive(self):
        if not self.comms_reply_pending:
            raise RuntimeError("sc receive: nothing to receive")
        while 1:
            try:
                reply = self.parent.mixer_read()
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
        if self.comms_reply_pending:  # Dump unused replies from previous send.
            raise RuntimeError("uncollected reply from previous command: " \
                                        "\n%s+++" % self.comms_reply_pending)
        if not "tab_id=" in string_to_send:
            string_to_send = "tab_id=-1\n" + string_to_send
        self.parent.mixer_write(string_to_send + "end\n", "sc")
        self.comms_reply_pending = string_to_send
                
    def restart_streams_and_recorders(self):
        whichstreams = []
        whichrecorders = []
        
        s = self.streamtabframe.tabs
        for each in s:
            whichstreams.append(each.server_connect.get_active())
            each.server_connect.set_active(False)
        
        r = self.recordtabframe.tabs
        for each in r:
            whichrecorders.append(
                                each.record_buttons.record_button.get_active())
            each.record_buttons.stop_button.clicked()

        for each in s:
            each.server_connect.set_active(whichstreams.pop(0))

        for each in r:
            each.record_buttons.record_button.set_active(whichrecorders.pop(0))
                
    def new_metadata(self, artist, title, album, songname):
        self.send("artist=%s\ntitle=%s\nalbum=%s\n"
                                    "command=new_song_metadata\n" % (
                                    artist.strip(), title.strip(),
                                    album.strip()))
        if self.receive() == "succeeded":
            print "updated song metadata successfully"

        common = {"artist": artist, "title": title, "album": album,
                                                        "songname": songname}
        # Update the custom metadata on all stream tabs.
        for tab in self.streamtabframe.tabs:  
            tab.metadata_update.clicked()
            ircmetadata = {"djname": tab.dj_name_entry.get_text(),
                                "description": tab.description_entry.get_text(),
                                "url": tab.listen_url_entry.get_text()
            }
            ircmetadata.update(common)

            tab.ircpane.connections_controller.new_metadata(ircmetadata)
        
    def source_client_open(self):
        global lame_enabled

        self.comms_reply_pending = False
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
            print "sample rate reply contains the following:", \
                                                            sample_rate_string
            self.app_exit()
        self.send("command=encoder_lame_availability\n")
        reply = self.receive()
        if reply != "failed" and self.receive() == "succeeded" and \
                                            reply.startswith("lame_available="):
            if reply[15] == "1":
                lame_enabled = 1
            else:
                lame_enabled = 0
        else:
            print self.unexpected_reply
            self.app_exit()
        print "threads initialised"
        self.jack_sample_rate = int(sample_rate_string[12:])
        print "jack sample rate is", self.jack_sample_rate
        try:
            for streamtab in self.streamtabframe.tabs:
                streamtab.stream_resample_frame.jack_sample_rate = \
                                                        self.jack_sample_rate
                streamtab.stream_resample_frame.resample_dummy_object.clicked()
                # update the stream tabs with the current jack sample rate
        except (NameError, AttributeError):
            # If this is the initial call the stream tabs will not exist yet.
            pass
        if FGlobs.avcodec:
            self.send("command=encoder_aac_availability\n")
            reply = self.receive()
            assert reply != "failed" and self.receive() == "succeeded" and \
                                        reply.startswith("aac_functionality=")
            FormatCodecMPEG.aac_enabled = int(reply[-3])
            FormatCodecMPEG.aacpv2_enabled = int(reply[-1])
        else:
            FormatCodecMPEG.aac_enabled = 0
            FormatCodecMPEG.aacpv2_enabled = 0
            
        self.uptime = time.time()

    def cb_delete_event(self, widget, event, data = None):
        self.window.hide()
        return True

    def save_session_settings(self, where):
        try:               
            # Check the following are initilised before proceeding.
            tabframes = (self, self.streamtabframe, self.recordtabframe)
        except AttributeError:
            return  # Cancelled save.

        try:
            with open((where or pm.basedir) / "s_data", "w") as f:
                for tabframe in tabframes:
                    for tab in tabframe.tabs:
                        f.write("".join(("[", tab.tab_type, " ", 
                                                str(tab.numeric_id), "]\n")))
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
                            elif method == "history":
                                rvalue = widget.get_history()
                            elif method == "radioindex":
                                rvalue = str(widget.get_radio_index())
                            elif method == "current_page":
                                rvalue = str(widget.get_current_page())
                            elif method == "directory":
                                rvalue = widget.get_current_folder() or ""
                            elif method == "filename":
                                rvalue = widget.get_filename() or ""
                            elif method == "marshall":
                                rvalue = widget.marshall()
                            else:
                                print "unsupported", lvalue, widget, method
                                continue
                            if method != "password" or \
                                self.parent.prefs_window.keeppass.get_active():
                                f.write("".join((lvalue, "=", rvalue, "\n")))
                        f.write("\n")
        except Exception as e:
            print "error attempting to write file: serverdata", e

    def load_previous_session(self):
        try:
            with open(pm.basedir / "s_data") as f:
                tabframe = None
                while 1:
                    line = f.readline()
                    if line == "":
                        break
                    else:
                        line = line[:-1]            # strip off the newline character
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
                                        elif method == "current_page":
                                            widget.set_current_page(int_rvalue)
                                        elif method == "text":
                                            widget.set_text(rvalue)
                                        elif method == "password":
                                            widget.set_text(rvalue)
                                        elif method == "history":
                                            widget.set_history(rvalue)
                                        elif method == "directory":
                                            if rvalue:
                                                widget.set_current_folder(rvalue)
                                        elif method == "filename":
                                            if rvalue:
                                                rvalue = widget.set_filename(rvalue)
                                        elif method == "marshall":
                                            widget.unmarshall(rvalue)
                                        else:
                                            print "method", method, "is unsupported at this time hence widget pertaining to", lvalue, "will not be set"
        except Exception as e:
            if isinstance(e, IOError):
                print e
            else:
                traceback.print_exc()

    def cb_after_realize(self, widget):
        self.wst.apply()
        #widget.resize(int(self.win_x), 1)
        self.streamtabframe.connect_group.grab_focus()
        
    def cb_stream_details_expand(self, expander, param_spec, next_expander, sw):
        if expander.get_expanded():
            sw.show()
        else:
            sw.hide()
        
        if expander.get_expanded() == next_expander.get_expanded():
            if not expander.get_expanded():
                self.window.resize((self.wst.get_x()), 1)
            else:
                pass
        else:
            next_expander.set_expanded(expander.get_expanded())

    def cb_stream_controls_expand(self, expander, param_spec, next_expander,
                                                        frame, details_shown):
        if expander.get_expanded():
            frame.show()
        else:
            frame.hide()
        
        if expander.get_expanded() == next_expander.get_expanded():
            self.window.resize((self.wst.get_x()), 1)
        else:
            next_expander.set_expanded(expander.get_expanded())
        
    def update_metadata(self, text=None, filter=None):
        for tab in self.streamtabframe.tabs:
            if filter is None or str(tab.numeric_id) in filter:
                if text is not None:
                    tab.metadata.set_text(text)
                tab.metadata_update.clicked()

    def cb_populate_recorder_menu(self, mi, tabs):
        menu = mi.get_submenu()
        
        def none(text):
            mi = gtk.MenuItem(text)
            mi.set_sensitive(False)
            menu.append(mi)
            mi.show()
        
        if not tabs:
            none(_('Recording Facility Unavailable'))
        elif not any(tab.record_buttons.record_button.get_sensitive() \
                                                            for tab in tabs):
            none(_('No Recorders Are Correctly Configured'))
        else:
            for tab in tabs:
                rec = tab.record_buttons.record_button
                stop = tab.record_buttons.stop_button
                sens = rec.get_sensitive()
                src = tab.source_dest.source_combo.get_active_text().strip()
                dest = tab.source_dest.file_chooser_button.get_current_folder()
                mi = gtk.CheckMenuItem()
                label = gtk.Label()
                label.set_alignment(0.0, 0.5)
                label.set_markup(
                    # TC: Recorder menu format string.
                    (_("{numericid} [{source}] > [{directory}]").format(
                    numericid=tab.numeric_id + 1, source=src, directory=dest)
                    if sens else " " + _('Misconfigured')))
                mi.add(label)
                label.show()
                mi.set_active(rec.get_active())
                mi.set_sensitive(sens)
                menu.append(mi)
                mi.show()
                mi.connect("activate", 
                                lambda w, r, s: r.set_active(r.get_sensitive()) 
                                if w.get_active() else s.clicked(), rec, stop)

    def cb_populate_streams_menu(self, mi, tabs):
        menu = mi.get_submenu()
        
        def none(text):
            mi = gtk.MenuItem(text)
            mi.set_sensitive(False)
            menu.append(mi)
            mi.show()
        
        if not tabs:
            none(_('Streaming Facility Unavailable'))
        elif not any(tab.server_connect.get_sensitive() for tab in tabs):
            none(_('No Streams Are Currently Configured'))
        else:
            sens = any(x.get_active() for x in self.streamtabframe.togglelist)
            mi = gtk.MenuItem(_('Group Connect'))
            mi.set_sensitive(sens)
            menu.append(mi)
            mi.show()
            mi.connect("activate",
                    lambda w: self.streamtabframe.connect_group.clicked())
            mi = gtk.MenuItem(_('Group Disconnect'))
            mi.set_sensitive(sens)
            menu.append(mi)
            mi.show()
            mi.connect("activate",
                    lambda w: self.streamtabframe.disconnect_group.clicked())
            spc = gtk.SeparatorMenuItem()
            menu.append(spc)
            spc.show()
            
            
            for tab in tabs:
                sc = tab.server_connect
                if sc.get_sensitive():
                    mi = gtk.CheckMenuItem(str(tab.numeric_id + 1) + " %s" % 
                                            sc.get_children()[0].get_label())
                    mi.set_active(sc.get_active())
                    menu.append(mi)
                    mi.show()
                    mi.connect("activate", 
                                lambda w, b: b.set_active(w.get_active()), sc)

    def __init__(self, parent):
        self.parent = parent
        parent.server_window = self
        self.source_client_crash_count = 0
        self.source_client_open()

        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.parent.window_group.add_window(self.window)
        # TC: Window title bar text.
        self.window.set_title(_('IDJC Output') + pm.title_extra)
        self.window.set_destroy_with_parent(True)
        self.window.set_border_width(11)
        self.window.set_resizable(True)
        self.window.connect_after("realize", self.cb_after_realize)
        self.window.connect("delete_event", self.cb_delete_event)
        self.wst = WindowSizeTracker(self.window)
        vbox = gtk.VBox()
        vbox.set_spacing(10)
        self.window.add(vbox)
        
        self.recordtabframe = TabFrame(self, _('Record'), PGlobs.num_recorders,
            RecordTab, (
            ("clear", "led_unlit_clear_border_64x64"),
            ("amber", "led_lit_amber_black_border_64x64"),
            ("red", "led_lit_red_black_border_64x64")),
            _('Each one of these tabs represents a separate stream recorder.'
            ' The LED indicator colours represent the following: Clear=Stopped'
            ' Yellow=Paused Red=Recording.'))
        self.streamtabframe = StreamTabFrame(self, _('Stream'),
            PGlobs.num_streamers, StreamTab, (
            ("clear", "led_unlit_clear_border_64x64"),
            ("amber", "led_lit_amber_black_border_64x64"),
            ("green", "led_lit_green_black_border_64x64")),
            _('Each one of these tabs represents a separate radio streamer. '
            'The LED indicator colours represent the following: Clear=No '
            'connection Yellow=Awaiting authentication. Green=Connected. '
            'Flashing=Packet loss due to a bad connection.'))
            
        tab = self.streamtabframe.tabs[-1]
        for next_tab in self.streamtabframe.tabs:
            tab.details.connect("notify::expanded",
                self.cb_stream_details_expand, next_tab.details, tab.details_nb)
            tab.ic_expander.connect("notify::expanded",
                self.cb_stream_controls_expand, next_tab.ic_expander,
                tab.ic_frame, self.streamtabframe.tabs[0].details.get_expanded)
            tab = next_tab

        self.streamtabframe.set_sensitive(True)
        vbox.pack_start(self.streamtabframe, True, True, 0)
        self.streamtabframe.show()
        for rectab in self.recordtabframe.tabs:
            rectab.source_dest.populate_stream_selector(_(' Stream '),
                                                    self.streamtabframe.tabs)
              
        self.parent.menu.recordersmenu_i.connect("activate",
                    self.cb_populate_recorder_menu, self.recordtabframe.tabs)
        self.parent.menu.streamsmenu_i.connect("activate",
                    self.cb_populate_streams_menu, self.streamtabframe.tabs)
        

        vbox.pack_start(self.recordtabframe, False, False, 0)
        if PGlobs.num_recorders:
            self.recordtabframe.show()
        vbox.show()
        self.tabs = (self, )
        self.numeric_id = 0
        self.tab_type = "server_window"
        self.objects = {"wst" : (self.wst, "text"),
            "streamer_page": (self.streamtabframe.notebook, "notebookpage"),
            "recorder_page": (self.recordtabframe.notebook, "notebookpage"),
            "controls_shown": (self.streamtabframe.tabs[0].ic_expander,
                                                                "expanded")}
        self.objects.update(self.streamtabframe.objects)
        self.load_previous_session()
        self.is_streaming = False
        self.is_recording = False
        self.led_alternate = False
        self.last_message_time = 0
        self.connection_string = None
        self.is_shoutcast = False
        self._streamstate_cache = None

        self.dialog_group = dialog_group()
        self.disconnected_dialog = disconnection_notification_dialog(
            self.dialog_group, self.parent.window_group, "",
            _('<span weight="bold" size="12000">A connection to a radio server'
            ' has failed.</span>\n\nReconnection will not be attempted.'))

        self.autoshutdown_dialog = disconnection_notification_dialog(
            self.dialog_group, self.parent.window_group, "",
            _('<span weight="bold" size="12000">A scheduled stream'
            ' disconnection has occurred.</span>'))
        
        self.monitor_source_id = gobject.timeout_add(250, threadslock(self.monitor))
        self.window.realize()   # Prevent a rendering bug.
        
        dbus.service.Object.__init__(self,
                    pm.dbus_bus_name, PGlobs.dbus_objects_basename + "/output")
