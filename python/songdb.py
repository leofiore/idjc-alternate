"""Music database connectivity and display."""

#   Copyright (C) 2012 Stephen Fairchild (s-fairchild@users.sourceforge.net)
#             (C) 2012 Brian Millham (bmillham@users.sourceforge.net)
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
import time
import types
import gettext
import threading
from functools import partial, wraps
from collections import deque
from urllib import quote

import glib
import gobject
import pango
import gtk
try:
    import MySQLdb as sql
except ImportError:
    have_songdb = False
else:
    have_songdb = True

from idjc import FGlobs
from .tooltips import set_tip
from .gtkstuff import threadslock, DefaultEntry, NotebookSR


__all__ = ['MediaPane', 'have_songdb']

AMPACHE = "Ampache"
PROKYON_3 = "Prokyon 3"
FUZZY, CLEAN, WHERE, DIRTY = xrange(4)

t = gettext.translation(FGlobs.package_name, FGlobs.localedir, fallback=True)
_ = t.gettext


def thread_only(func):
    """Guard a method from being called from outside the thread context."""
    
    @wraps(func)
    def inner(self, *args, **kwargs):
        assert threading.current_thread() == self
        func(self, *args, **kwargs)
    return inner


class DBAccessor(threading.Thread):
    """A class to hide the intricacies of database access.
    
    When the database connection is dropped due to timeout it will silently 
    remake the connection and continue on with its work.
    """
    
    def __init__(self, hostnameport, user, password, database, notify):
        """The notify function must lock gtk before accessing widgets."""
        
        threading.Thread.__init__(self)
        try:
            hostname, port = hostnameport.rsplit(":", 1)
            port = int(port)
        except ValueError:
            hostname = hostnameport
            port = 3306  # MySQL uses this as the default port.

        self.hostname = hostname
        self.port = port
        self.user = user
        self.password = password
        self.database = database
        self.notify = notify
        self._handle = None  # No connections made until there is a query.
        self._cursor = None
        self.jobs = deque()
        self.semaphore = threading.Semaphore()
        self.keepalive = True
        self.start()

    def request(self, sql_query, handler, failhandler=None):
        """Add a request to the job queue.
        
        The failhandler may "raise exception" to reconnect and try again or
        it may return...
            False, None: to run the handler
            True: to cancel the job
        """
        
        self.jobs.append((sql_query, handler, failhandler))
        self.semaphore.release()

    def close(self):
        """Clean up the worker thread prior to disposal."""
        
        if self.is_alive():
            self.keepalive = False
            self.semaphore.release()
            return

    def run(self):
        """This is the worker thread."""

        notify = partial(glib.idle_add, threadslock(self.notify))
        
        try:
            while self.keepalive:
                self.semaphore.acquire()
                if self.keepalive and self.jobs:
                    query, handler, failhandler = self.jobs.popleft()

                    trycount = 0
                    while trycount < 3:
                        try:
                            try:
                                rows = self._cursor.execute(*query)
                            except sql.Error as e:
                                if failhandler is not None:
                                    if failhandler(e, notify):
                                        break
                                    rows = 0
                                else:
                                    raise e
                        except (sql.Error, AttributeError) as e:
                            if not self.keepalive:
                                return
                            
                            if isinstance(e, sql.OperationalError):
                                # Unhandled errors will be treated like
                                # connection failures.
                                try:
                                    self._cursor.close()
                                except Exception:
                                    pass
                                    
                                try:
                                    self._handle.close()
                                except Exception:
                                    pass
                                
                            if not self.keepalive:
                                return

                            notify(_('Connecting'))
                            trycount += 1
                            try:
                                self._handle = sql.Connection(
                                    host=self.hostname, port=self.port,
                                    user=self.user, passwd=self.password,
                                    db=self.database, connect_timeout=6)
                                self._cursor = self._handle.cursor()
                            except sql.Error as e:
                                notify(_("Connection failed (try %d)") %
                                                                    trycount)
                                print e
                                time.sleep(0.5)
                            else:
                                try:
                                    self._cursor.execute('set names utf8')
                                    self._cursor.execute(
                                                    'set character set utf8')
                                    self._cursor.execute(
                                            'set character_set_connection=utf8')
                                except sql.MySQLError:
                                    notify(_('Connected: utf-8 mode failed'))
                                else:
                                    notify(_('Connected'))
                        else:
                            if not self.keepalive:
                                return
                            handler(self, self.request, self._cursor, notify,
                                                                        rows)
                            break
                    else:
                        notify(_('Job dropped'))
        finally:
            try:
                self._cursor.close()
            except Exception:
                pass
            try:
                self._handle.close()
            except Exception:
                pass
            notify(_('Disconnected'))

    @thread_only
    def purge_job_queue(self, remain=0):
        while len(self.jobs) > remain:
            self.jobs.popleft()
            self.semaphore.acquire()

    @thread_only
    def disconnect(self):
        try:
            self._handle.close()
        except sql.Error:
            glib.idle_add(threadslock(self.notify),
                                            _('Problem dropping connection'))
        else:
            glib.idle_add(threadslock(self.notify), _('Connection dropped'))

    @thread_only
    def replace_cursor(self, cursor):
        """Handler may break off the cursor to pass along its data."""
        
        assert cursor is self._cursor
        self._cursor = self._handle.cursor()


class Settings(gtk.Table):
    def __init__(self, name):
        self._name = name
        gtk.Table.__init__(self, 5, 4)
        self.set_border_width(10)
        self.set_row_spacings(1)
        for col, spc in zip(xrange(3), (3, 10, 3)):
            self.set_col_spacing(col, spc)

        self._controls = []
        self.textdict = {}

        # Attachment for labels.
        l_attach = partial(self.attach, xoptions=gtk.SHRINK | gtk.FILL)
        
        # Top row.
        hostportlabel, self.hostnameport = self._factory(
            _('Hostname[:Port]'), 'localhost', "hostnameport")
        l_attach(hostportlabel, 0, 1, 0, 1)
        self.attach(self.hostnameport, 1, 4, 0, 1)
        
        # Second row.
        hbox = gtk.HBox()
        hbox.set_spacing(3)
        fpmlabel, self.addchars = self._factory(_('File Path Modify'), None,
                                                                    "addchars")
        adj = gtk.Adjustment(0.0, 0.0, 999.0, 1.0, 1.0)
        self.delchars = gtk.SpinButton(adj, 0.0, 0)
        self._controls.append(self.delchars)
        self.valuesdict = {"songdb_delchars_" + name: self.delchars}
        set_tip(self.delchars, _('The number of characters to strip from '
                                'the left hand side of media file paths.'))
        set_tip(self.addchars, 
                    _('The characters to prefix to the media file paths.'))
        l_attach(fpmlabel, 0, 1, 1, 2)
        minus = gtk.Label('-')
        hbox.pack_start(minus, False)
        hbox.pack_start(self.delchars, False)
        plus = gtk.Label('+')
        hbox.pack_start(plus, False)
        hbox.pack_start(self.addchars)
        self.attach(hbox, 1, 4, 1, 2)
        
        # Third row.
        userlabel, self.user = self._factory(_('User Name'), "admin", "user")
        l_attach(userlabel, 0, 1, 3, 4)
        self.attach(self.user, 1, 2, 3, 4)
        dblabel, self.database = self._factory(_('Database'), "ampache",
                                                                    "database")
        l_attach(dblabel, 2, 3, 3, 4)
        self.attach(self.database, 3, 4, 3, 4)
        
        # Fourth row.
        passlabel, self.password = self._factory(_('Password'), "", "password")
        self.password.set_visibility(False)
        l_attach(passlabel, 0, 1, 4, 5)
        self.attach(self.password, 1, 2, 4, 5)

    def get_conn_data(self):
        """Collate parameters for DBAccessor contructors."""
        
        conn_data = {}
        for key in "hostnameport user password database".split():
            conn_data[key] = getattr(self, key).get_text().strip()
        
        return conn_data

    def get_transformation_data(self):
        """Make a file path transformation function."""

        from_ = self.delchars.get_value_as_int() + 1
        prepend_str = self.addchars.get_text().strip()

        return from_, prepend_str

    def set_sensitive(self, sens):
        """Just specific contents of the table are made insensitive."""

        for each in self._controls:
            each.set_sensitive(sens)

    def _factory(self, labeltext, entrytext, control_name):
        """Widget factory method."""

        label = gtk.Label(labeltext)
        label.set_alignment(1.0, 0.5)

        if entrytext:
            entry = DefaultEntry(entrytext, True)
        else:
            entry = gtk.Entry()

        entry.set_size_request(10, -1)
        self._controls.append(entry)
        self.textdict["songdb_%s_%s" % (control_name, self._name)] = entry
        
        return label, entry


class PrefsControls(gtk.Frame):
    """Database controls as visible in the preferences window."""
    
    def __init__(self):
        gtk.Frame.__init__(self)
        self.set_border_width(3)
        label = gtk.Label(" %s " % 
                            _('Prokyon3 or Ampache (song title) Database'))
        set_tip(label, _('You can make certain media databases accessible in '
                            'IDJC for easy drag and drop into the playlists.'))
        self.set_label_widget(label)
        vbox = gtk.VBox()
        vbox.set_border_width(6)
        vbox.set_spacing(2)
        self.add(vbox)
        
        self._notebook = NotebookSR()
        if have_songdb:
            vbox.pack_start(self._notebook, False)

        self._settings = []
        for i in range(1, 5):
            settings = Settings(str(i))
            self._settings.append(settings)
            label = gtk.Label(str(i))
            self._notebook.append_page(settings, label)

        self.dbtoggle = gtk.ToggleButton(_('Music Database'))
        self.dbtoggle.connect("toggled", self._cb_dbtoggle)

        hbox = gtk.HBox()
        hbox.set_spacing(2)
        
        self._disconnect = gtk.Button()
        self._disconnect.set_sensitive(False)
        image = gtk.image_new_from_stock(gtk.STOCK_DISCONNECT, gtk.ICON_SIZE_MENU)
        self._disconnect.add(image)
        self._disconnect.connect("clicked", lambda w: self.dbtoggle.set_active(False))
        hbox.pack_start(self._disconnect, False)
        
        self._connect = gtk.Button()
        image = gtk.image_new_from_stock(gtk.STOCK_CONNECT, gtk.ICON_SIZE_MENU)
        self._connect.add(image)
        self._connect.connect("clicked", lambda w: self.dbtoggle.set_active(True))
        hbox.pack_start(self._connect, False)
        
        self._statusbar = gtk.Statusbar()
        self._statusbar.set_has_resize_grip(False)
        cid = self._statusbar.get_context_id("all output")
        self._statusbar.push(cid, _('Disconnected'))
        hbox.pack_start(self._statusbar)

        if have_songdb:
            vbox.pack_start(hbox, False)
        else:
            vbox.set_sensitive(False)
            label = gtk.Label(_('Module mysql-python (MySQLdb) required'))
            vbox.add(label)

        self.show_all()
        
        # Save and Restore.
        self.activedict = {"songdb_active": self.dbtoggle,
                            "songdb_page": self._notebook}
        self.textdict = {}
        self.valuesdict = {}
        for each in self._settings:
            self.textdict.update(each.textdict)
            self.valuesdict.update(each.valuesdict)

    def disconnect(self):
        self.dbtoggle.set_active(False)    
        
    def bind(self, callback):
        """Connect with the activate method of the view pane."""
        
        self.dbtoggle.connect("toggled", self._cb_bind, callback)

    def _cb_bind(self, widget, callback):
        """This runs when the database is toggled on and off."""
        
        if widget.get_active():
            settings = self._notebook.get_nth_page(
                                            self._notebook.get_current_page())
            conn_data = settings.get_conn_data()
            conn_data["notify"] = self._notify
            trans_data = settings.get_transformation_data()
        else:
            conn_data = trans_data = None

        callback(conn_data, trans_data)

    def _cb_dbtoggle(self, widget):
        """Parameter widgets to be made insensitive when db is active."""
    
        if widget.get_active():
            self._connect.set_sensitive(False)
            self._disconnect.set_sensitive(True)
            settings = self._notebook.get_nth_page(
                                            self._notebook.get_current_page())
            for settings_page in self._settings:
                if settings_page is settings:
                    settings_page.set_sensitive(False)
                else:
                    settings_page.hide()
        else:
            self._connect.set_sensitive(True)
            self._disconnect.set_sensitive(False)
            for settings_page in self._settings:
                settings_page.set_sensitive(True)
                settings_page.show()

    def _notify(self, message):
        """Display status messages beneath the prefs settings."""
        
        print "Song title database:", message
        cid = self._statusbar.get_context_id("all output")
        self._statusbar.pop(cid)
        self._statusbar.push(cid, message)
        # To ensure readability of long messages also set the tooltip.
        self._statusbar.set_tooltip_text(message)


class PageCommon(gtk.VBox):
    """Base class for TreePage and FlatPage."""
    
    def __init__(self, notebook, label_text, controls):
        gtk.VBox.__init__(self)
        self.set_spacing(2)
        self.scrolled_window = gtk.ScrolledWindow()
        self.scrolled_window.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_ALWAYS)
        self.pack_start(self.scrolled_window)
        self.tree_view = gtk.TreeView()
        self.tree_view.set_enable_search(False)
        self.tree_selection = self.tree_view.get_selection()
        self.scrolled_window.add(self.tree_view)
        self.pack_start(controls, False)
        label = gtk.Label(label_text)
        notebook.append_page(self, label)
        
        self.tree_view.enable_model_drag_source(gtk.gdk.BUTTON1_MASK,
            self._sourcetargets, gtk.gdk.ACTION_DEFAULT | gtk.gdk.ACTION_COPY)
        self.tree_view.connect_after("drag-begin", self._cb_drag_begin)
        self.tree_view.connect("drag-data-get", self._cb_drag_data_get)
        self._update_id = deque()
        self._acc = None

    @property
    def db_type(self):
        return self._db_type

    @property
    def trans_from(self):
        return self._trans_data[0]
       
    @property
    def trans_prepend(self):
        return self._trans_data[1]

    def get_col_widths(self):
        pass

    def get_col_widths(self):
        return ",".join([str(x.get_width() or x.get_fixed_width())
                                                    for x in self.tree_cols])

    def set_col_widths(self, data):
        """Restore column width values."""
         
        c = self.tree_cols.__iter__()
        for w in data.split(","):
            if w != "0":
                c.next().set_fixed_width(int(w))
            else:
                c.next()

    def activate(self, accessor, db_type, trans_data):
        self._db_type = db_type
        self._acc = accessor
        self._trans_data = trans_data
        
    def deactivate(self):
        while self._update_id:
            context, namespace = self._update_id.popleft()
            namespace[0] = True
            glib.source_remove(context)
        
        self._acc = None
        model = self.tree_view.get_model()
        self.tree_view.set_model(None)
        if model is not None:
            model.clear()

    def repair_focusability(self):
        self.tree_view.set_flags(gtk.CAN_FOCUS)

    _sourcetargets = (  # Drag and drop source target specs.
        ('text/plain', 0, 1),
        ('TEXT', 0, 2),
        ('STRING', 0, 3))

    def _cb_drag_begin(self, widget, context):
        """Set icon for drag and drop operation."""

        context.set_icon_stock(gtk.STOCK_CDROM, -5, -5)

    def _cb_drag_data_get(self, tree_view, context, selection, target, etime):
        model, paths = self.tree_selection.get_selected_rows()
        data = ("file://%s" % row for row in self._drag_data(model, paths))
        selection.set(selection.target, 8, "\n".join(data))

    @staticmethod
    def _make_tv_columns(tree_view, parameters):
        """Build a TreeViewColumn list from a table of data."""

        list_ = []
        for label, data_index, data_function, mw, el in parameters:
            renderer = gtk.CellRendererText()
            renderer.props.ellipsize = el
            column = gtk.TreeViewColumn(label, renderer)
            if mw != -1:
                column.set_resizable(True)
                column.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
                column.set_min_width(mw)
                column.set_fixed_width(mw + 50)
            tree_view.append_column(column)
            list_.append(column)
            if data_function is not None:
                column.set_cell_data_func(renderer, data_function, data_index)
            else:
                column.add_attribute(renderer, 'text', data_index)

        return list_

    def _cond_cell_secs_to_h_m_s(self, column, renderer, model, iter, cell):
        if model.get_value(iter, 0) >= 0:
            return self._cell_secs_to_h_m_s(column, renderer, model, iter, cell)
        else:
            renderer.set_property("text", "")
    
    def _cell_k(self, column, renderer, model, iter, cell):
        bitrate = model.get_value(iter, cell)
        if bitrate == 0:
            renderer.set_property("text", "")
        elif self._db_type == "P3":
            renderer.set_property("text", "%dk" % bitrate)
        elif bitrate > 9999 and self._db_type == AMPACHE:
            renderer.set_property("text", "%dk" % (bitrate // 1000))
        renderer.set_property("xalign", 1.0)

    @staticmethod
    def _cell_show_unknown(column, renderer, model, iter, cell):
        text = model.get_value(iter, cell) or _('<unknown>')
        renderer.props.text = text


    def inner(column, renderer, model, iter, cell, which_bit):
        text = model.get_value(iter, cell)

        if text:
            renderer.props.text = which_bit(text)
        else:
            renderer.props.text = ""    
    _cell_path = staticmethod(partial(inner, which_bit=os.path.dirname))
    _cell_filename = staticmethod(partial(inner, which_bit=os.path.basename))
    del inner
    
    @staticmethod
    def _cell_secs_to_h_m_s(column, renderer, model, iter, cell):
        v_in = model.get_value(iter, cell)
        m, s = divmod(v_in, 60)
        h, m = divmod(m, 60)
        d, h = divmod(h, 24)
        if d:
            v_out = "%dd:%02d:%02d" % (d, h, m)
        else:
            if h:
                v_out = "%d:%02d:%02d" % (h, m, s)
            else:
                v_out = "%d:%02d" % (m, s)
        renderer.set_property("xalign", 1.0)
        renderer.set_property("text", v_out)
        
    @staticmethod
    def _cell_ralign(column, renderer, model, iter, cell):
        val = model.get_value(iter, cell)
        if val:
            renderer.set_property("xalign", 1.0)
            renderer.set_property("text", val)
        else:
            renderer.set_property("text", "")

    def _handler(self, acc, request, cursor, notify, rows):
        # Lock against the very start of the update functions.
        gtk.gdk.threads_enter()
        while self._update_id:
            context, namespace = self._update_id.popleft()
            glib.source_remove(context)
            # Idle functions to receive the following and know to clean-up.
            namespace[0] = True
        gtk.gdk.threads_leave()

        try:
            self._old_cursor.close()
        except sql.Error as e:
            print str(e)
        except AttributeError:
            pass

        self._old_cursor = cursor
        acc.replace_cursor(cursor)
        # Scrap intermediate jobs whose output would merely slow down the
        # user interface responsiveness.
        namespace = [False, ()]
        context = glib.idle_add(self._update_1, acc, cursor, rows, namespace)
        self._update_id.append((context, namespace))


class ExpandAllButton(gtk.Button):
    def __init__(self, expanded, tooltip=None):
        expander = gtk.Expander()
        expander.set_expanded(expanded)
        expander.show_all()
        gtk.Button.__init__(self)
        self.add(expander)
        if tooltip is not None:
            set_tip(self, tooltip)


class TreePage(PageCommon):
    """Browsable UI with tree structure."""

    # *depth*, *treecol*, album, album_prefix, year, disk, album_id,
    # tracknumber, title, artist, artist_prefix, pathname, bitrate, length
    # The order chosen negates the need for a custom sort comparison function.
    DATA_SIGNATURE = int, str, str, str, int, int, int, int, str, str, str, str, int, int
    BLANK_ROW = tuple(x() for x in DATA_SIGNATURE[2:])

    def __init__(self, notebook):
        self.controls = gtk.HBox()
        layout_store = gtk.ListStore(str, gtk.TreeStore, gobject.TYPE_PYOBJECT)
        self.layout_combo = gtk.ComboBox(layout_store)
        cell_text = gtk.CellRendererText()
        self.layout_combo.pack_start(cell_text)
        self.layout_combo.add_attribute(cell_text, "text", 0)
        self.controls.pack_start(self.layout_combo, False)
        self.right_controls = gtk.HBox()
        self.right_controls.set_spacing(1)
        self.tree_rebuild = gtk.Button()
        set_tip(self.tree_rebuild, _('Reload the database.'))
        image = gtk.image_new_from_stock(gtk.STOCK_REFRESH, gtk.ICON_SIZE_MENU)
        self.tree_rebuild.add(image)
        self.tree_rebuild.connect("clicked", self._cb_tree_rebuild)
        self.tree_rebuild.set_use_stock(True)
        tree_expand = ExpandAllButton(True, _('Expand entire tree.'))
        tree_collapse = ExpandAllButton(False, _('Collapse tree.'))
        sg = gtk.SizeGroup(gtk.SIZE_GROUP_HORIZONTAL)
        for each in (self.tree_rebuild, tree_expand, tree_collapse):
            self.right_controls.pack_start(each, False)
            sg.add_widget(each)
        self.controls.pack_end(self.right_controls, False)

        PageCommon.__init__(self, notebook, _('Browse'), self.controls)
        
        self.tree_view.set_enable_tree_lines(True)
        tree_expand.connect_object("clicked", gtk.TreeView.expand_all,
                                                                self.tree_view)
        tree_collapse.connect_object("clicked", gtk.TreeView.collapse_all,
                                                                self.tree_view)
        self.tree_cols = self._make_tv_columns(self.tree_view, (
                ("", 1, self._cell_show_unknown, 180, pango.ELLIPSIZE_END),
                # TC: Track artist.
                (_('Artist'), (10, 9), self._data_merge, 100, pango.ELLIPSIZE_END),
                # TC: The disk number of the album track.
                (_('Disk'), 5, self._cell_ralign, -1, pango.ELLIPSIZE_NONE),
                # TC: The album track number.
                (_('Track'), 7, self._cell_ralign, -1, pango.ELLIPSIZE_NONE),
                # TC: Track playback time.
                (_('Duration'), 13, self._cond_cell_secs_to_h_m_s, -1, pango.ELLIPSIZE_NONE),
                (_('Bitrate'), 12, self._cell_k, -1, pango.ELLIPSIZE_NONE),
                (_('Filename'), 11, self._cell_filename, 100, pango.ELLIPSIZE_END),
                # TC: Directory path to a file.
                (_('Path'), 11, self._cell_path, -1, pango.ELLIPSIZE_NONE),
                ))

        self.artist_store = gtk.TreeStore(*self.DATA_SIGNATURE)
        self.album_store = gtk.TreeStore(*self.DATA_SIGNATURE)
        layout_store.append((_('Artist - Album - Title'), self.artist_store, (1, )))
        layout_store.append((_('Album - [Disk] - Title'), self.album_store, (2, )))
        self.layout_combo.set_active(0)
        self.layout_combo.connect("changed", self._cb_layout_combo)

        self.loading_vbox = gtk.VBox()
        self.loading_vbox.set_border_width(20)
        self.loading_vbox.set_spacing(20)
        # TC: The database tree view is being built (populated).
        self.loading_label = gtk.Label()
        self.loading_vbox.pack_start(self.loading_label, False)
        self.progress_bar = gtk.ProgressBar()
        self.loading_vbox.pack_start(self.progress_bar, False)
        self.pack_start(self.loading_vbox)
        self._pulse_id = deque()
        
        self.show_all()

    def set_loading_view(self, loading):
        if loading:
            self.progress_bar.set_fraction(0.0)
            self.loading_label.set_text(_('Fetching'))
            self.controls.hide()
            self.scrolled_window.hide()
            self.loading_vbox.show()
        else:
            self.layout_combo.emit("changed")
            self.loading_vbox.hide()
            self.scrolled_window.show()
            self.controls.show()

    def activate(self, *args, **kwargs):
        PageCommon.activate(self, *args, **kwargs)
        glib.idle_add(threadslock(self.tree_rebuild.clicked))

    def deactivate(self):
        while self._pulse_id:
            glib.source_remove(self._pulse_id.popleft())
        self.progress_bar.set_fraction(0.0)
        
        PageCommon.deactivate(self)

    def _cb_layout_combo(self, widget):
        iter = widget.get_active_iter()
        store, hide = widget.get_model().get(iter, 1, 2)
        self.tree_view.set_model(store)
        for i, col in enumerate(self.tree_cols):
            col.set_visible(i not in hide)

    def _cb_tree_rebuild(self, widget):
        """(Re)load the tree with info from the database."""

        self.set_loading_view(True)
        if self._db_type == PROKYON_3:
            query = """SELECT
                    album,
                    "" as alb_prefix,
                    IFNULL(albums.year, 0) as year,
                    0 as disk,
                    IFNULL(albums.id, 0) as album_id,
                    tracknumber,
                    title,
                    tracks.artist as artist,
                    "" as art_prefix,
                    CONCAT(%s,MID(CONCAT_WS('/',path,filename),%s)) as file,
                    bitrate, length
                    FROM tracks
                    LEFT JOIN albums on tracks.album = albums.name
                    ORDER BY tracks.artist, album, tracknumber, title"""
        elif self._db_type == AMPACHE:
            query = """SELECT
                    album.name as album,
                    album.prefix as alb_prefix,
                    album.year as year,
                    album.disk as disk,
                    song.album as album_id,
                    track as tracknumber,
                    title,
                    artist.name as artist,
                    artist.prefix as art_prefix,
                    CONCAT(%s,MID(file,%s)) as file,
                    bitrate,
                    time as length
                    FROM song
                    LEFT JOIN artist ON song.artist = artist.id
                    LEFT JOIN album ON song.album = album.id
                    ORDER BY artist.name, album, disk, tracknumber, title"""
        else:
            print "unsupported database type:", self._db_type
            return
            
        self._pulse_id.append(glib.timeout_add(1000, self._progress_pulse))
        self._acc.request((query, (self.trans_prepend, self.trans_from)),
                                            self._handler, self._failhandler)

    def _drag_data(self, model, path):
        iter = model.get_iter(path[0])
        for each in self._more_drag_data(model, iter):
            yield each 
                
    def _more_drag_data(self, model, iter):
        depth, pathname = model.get(iter, 0, 11)
        if depth == 0:
            yield pathname
        else:
            iter = model.iter_children(iter)
            while iter is not None:
                for pathname in self._more_drag_data(model, iter):
                    yield pathname
            
                iter = model.iter_next(iter)

    @threadslock
    def _progress_pulse(self):
        self.progress_bar.pulse()
        return True

    def _data_merge(self, column, renderer, model, iter, elements):
        renderer.props.text = self._join(*model.get(iter, *elements))

    @staticmethod
    def _join(prefix, name):
        if prefix and name:
            return prefix + " " + name
        return prefix or name or ""

    ###########################################################################

    def _handler(self, acc, request, cursor, notify, rows):
        PageCommon._handler(self, acc, request, cursor, notify, rows)
        acc.disconnect()

    def _failhandler(self, exception, notify):
        if isinstance(exception, sql.InterfaceError):
            raise exception  # Recover.
        
        print exception
        
        notify(_('Tree fetch failed'))
        glib.idle_add(threadslock(self.loading_label.set_text),
                                                        _('Fetch Failed!'))
        while self._pulse_id:
            glib.source_remove(self._pulse_id.popleft())
        
        return True  # Drop job. Don't run handler.

    ###########################################################################

    @threadslock
    def _update_1(self, acc, cursor, rows, namespace):
        if namespace[0]:
            return False
            
        self.loading_label.set_text(_('Populating'))
        # Turn off progress bar pulser.
        while self._pulse_id:
            glib.source_remove(self._pulse_id.popleft())

        # Clean away old data.
        self.tree_view.set_model(None)
        self.artist_store.clear()
        self.album_store.clear()

        namespace = [False, (0.0, None, None, None, None, None, None)]
        do_max = min(max(30, rows / 100), 200)  # Data size to process.
        total = 2.0 * rows
        context = glib.idle_add(self._update_2, acc, cursor, total, do_max,
                                                            [], namespace)
        self._update_id.append((context, namespace))
        return False

    @threadslock
    def _update_2(self, acc, cursor, total, do_max, store, namespace):
        kill, (done, iter_1, iter_2, artist, album, art_prefix, alb_prefix) = namespace
        if kill:
            return False

        r_append = self.artist_store.append
        l_append = store.append
        BLANK_ROW = self.BLANK_ROW

        rows = cursor.fetchmany(do_max)
        if not rows:
            store.sort()
            namespace = [False, (done, ) + (None, ) * 9]
            context = glib.idle_add(self._update_3, acc, total, do_max,
                                                        store, namespace)
            self._update_id.append((context, namespace))
            return False

        for row in rows:
            if acc.keepalive == False:
                return False

            l_append(row)
            if album == row[0] and artist == row[7] and \
                                alb_prefix == row[1] and art_prefix == row[8]:
                r_append(iter_2, (0, row[6]) + row)
                continue
            else:
                if artist != row[7] or art_prefix != row[8]:
                    artist = row[7]
                    art_prefix = row[8]
                    iter_1 = r_append(None, (-1, self._join(art_prefix, artist)) + BLANK_ROW)
                    album = None
                if album != row[0] or alb_prefix != row[1]:
                    album = row[0]
                    alb_prefix = row[1]
                    year = row[2]
                    if year:
                        albumtext = "%s (%d)" % (self._join(alb_prefix, album), year)
                    else:
                        albumtext = album
                    iter_2 = r_append(iter_1, (-2, albumtext) + BLANK_ROW)
                r_append(iter_2, (0, row[6]) + row)
                
        done += do_max
        self.progress_bar.set_fraction(done / total)
        namespace[1] = done, iter_1, iter_2, artist, album, art_prefix, alb_prefix
        return True

    @threadslock
    def _update_3(self, acc, total, do_max, store, namespace):
        kill, (done, iter_1, iter_2, artist, album, art_prefix, alb_prefix, year, disk, album_id) = namespace
        if kill:
            return False

        append = self.album_store.append
        pop = store.pop
        BLANK_ROW = self.BLANK_ROW
        
        for each in xrange(do_max):
            if acc.keepalive == False:
                return False
                
            try:
                row = pop(0)
            except IndexError:
                self.set_loading_view(False)
                return False

            if album_id == row[4]:
                append(iter_2, (0, row[6]) + row)
                continue
            else:
                if album != row[0] or year != row[2] or alb_prefix != row[1]:
                    album = row[0]
                    alb_prefix = row[1]
                    year = row[2]
                    disk = None
                    if year:
                        albumtext = "%s (%d)" % (self._join(alb_prefix, album), year)
                    else:
                        albumtext = album
                    iter_1 = append(None, (-1, albumtext) + BLANK_ROW)
                if disk != row[3]:
                    disk = row[3]
                    if disk == 0:
                        iter_2 = iter_1
                    else:
                        iter_2 = append(iter_1, (-2, _('Disk %d') % disk)
                                                                + BLANK_ROW)
                append(iter_2, (0, row[6]) + row)

        done += do_max
        self.progress_bar.set_fraction(min(done / total, 1.0))
        namespace[1] = done, iter_1, iter_2, artist, album, art_prefix, alb_prefix, year, disk, album_id
        return True


class FlatPage(PageCommon):
    """Flat list based user interface with a search facility."""
    
    def __init__(self, notebook):
        # Base class overwrites these values.
        self.scrolled_window = self.tree_view = self.tree_selection = None
        self.transfrom = self.db_accessor = None

        # TC: User specified search filter entry box title text.
        self.controls = gtk.Frame(" %s " % _('Filters'))
        self.controls.set_shadow_type(gtk.SHADOW_OUT)
        self.controls.set_border_width(1)
        self.controls.set_label_align(0.5, 0.5)
        filter_vbox = gtk.VBox()
        filter_vbox.set_border_width(3)
        filter_vbox.set_spacing(1)
        self.controls.add(filter_vbox)
        
        fuzzy_hbox = gtk.HBox()
        filter_vbox.pack_start(fuzzy_hbox, False)
        # TC: A type of search on any data field matching paritial strings.
        fuzzy_label = gtk.Label(_('Fuzzy Search'))
        fuzzy_hbox.pack_start(fuzzy_label, False)
        self.fuzzy_entry = gtk.Entry()
        self.fuzzy_entry.connect("changed", self._cb_fuzzysearch_changed)
        fuzzy_hbox.pack_start(self.fuzzy_entry, True, True, 0)
        
        where_hbox = gtk.HBox()
        filter_vbox.pack_start(where_hbox, False)
        # TC: WHERE is an SQL keyword.
        where_label = gtk.Label(_('WHERE'))
        where_hbox.pack_start(where_label, False)
        self.where_entry = gtk.Entry()
        self.where_entry.connect("activate", self._cb_update)
        where_hbox.pack_start(self.where_entry)
        image = gtk.image_new_from_stock(gtk.STOCK_EXECUTE,
                                                        gtk.ICON_SIZE_BUTTON)
        self.update_button = gtk.Button()
        self.update_button.connect("clicked", self._cb_update)
        self.update_button.set_image(image)
        image.show
        where_hbox.pack_start(self.update_button, False)
        
        PageCommon.__init__(self, notebook, _("Search"), self.controls)
 
        # Row data specification:
        # index, ARTIST, ALBUM, TRACKNUM, TITLE, DURATION, BITRATE,
        # pathname, disk
        self.list_store = gtk.ListStore(
                                int, str, str, int, str, int, int, str, int)
        self.tree_cols = self._make_tv_columns(self.tree_view, (
            ("(0)", 0, self._cell_ralign, -1, pango.ELLIPSIZE_NONE),
            (_('Artist'), 1, self._cell_show_unknown, 100, pango.ELLIPSIZE_END),
            (_('Album'), 2, self._cell_show_unknown, 100, pango.ELLIPSIZE_END),
            (_('Disk'), 8, self._cell_ralign, -1, pango.ELLIPSIZE_NONE),
            (_('Track'), 3, self._cell_ralign, -1, pango.ELLIPSIZE_NONE),
            (_('Title'), 4, self._cell_show_unknown, 100, pango.ELLIPSIZE_END),
            (_('Duration'), 5, self._cell_secs_to_h_m_s, -1, pango.ELLIPSIZE_NONE),
            (_('Bitrate'), 6, self._cell_k, -1, pango.ELLIPSIZE_NONE),
            (_('Filename'), 7, self._cell_filename, 100, pango.ELLIPSIZE_END),
            (_('Path'), 7, self._cell_path, -1, pango.ELLIPSIZE_NONE),
            ))

        self.tree_view.set_rules_hint(True)
        self.tree_view.set_rubber_banding(True)
        self.tree_selection.set_mode(gtk.SELECTION_MULTIPLE)

    def deactivate(self):
        self.fuzzy_entry.set_text("")
        self.where_entry.set_text("")
        PageCommon.deactivate(self)

    def repair_focusability(self):
        PageCommon.repair_focusability(self)
        self.fuzzy_entry.set_flags(gtk.CAN_FOCUS)
        self.where_entry.set_flags(gtk.CAN_FOCUS)

    _queries_table = {
        PROKYON_3:
            {FUZZY: (CLEAN, """
                    SELECT artist,album,tracknumber,title,length,bitrate,
                    CONCAT(%s,MID(CONCAT_WS('/',path,filename),%s)) as file,
                    0 as disk
                    FROM tracks
                    WHERE MATCH (artist,album,title,filename) AGAINST (%s)
                    """),
        
            WHERE: (DIRTY, """
                    SELECT artist,album,tracknumber,title,length,bitrate,
                    CONCAT("%s",MID(CONCAT_WS('/',path,filename),%s)) as file,
                    0 as disk
                    FROM tracks WHERE (%s)
                    ORDER BY artist,album,path,tracknumber,title
                    """)},
        
        AMPACHE:
            {FUZZY: (CLEAN, """
                    SELECT
                    concat_ws(" ",artist.prefix,artist.name),
                    concat_ws(" ",album.prefix,album.name),
                    track as tracknumber, title, time as length,bitrate,
                    CONCAT(%s,MID(file,%s)) as file,
                    album.disk as disk FROM song
                    LEFT JOIN artist ON artist.id = song.artist
                    LEFT JOIN album ON album.id = song.album
                    WHERE
                         (MATCH(album.name) against(%s)
                          OR MATCH(artist.name) against(%s)
                          OR MATCH(title) against(%s))
                    """),

            WHERE: (DIRTY, """
                    SELECT
                    concat_ws(" ", artist.prefix, artist.name) as artist,
                    concat_ws(" ", album.prefix, album.name) as albumname,
                    track as tracknumber, title,time as length, bitrate,
                    CONCAT("%s",MID(file,%s)) as file,
                    album.disk as disk FROM song
                    LEFT JOIN album on album.id = song.album
                    LEFT JOIN artist on artist.id = song.artist
                    WHERE (%s) ORDER BY
                    artist.name, album.name, file, album.disk, track, title
                    """)}
    }

    def _cb_update(self, widget):
        try:
            table = self._queries_table[self._db_type]
        except KeyError:
            print "unsupported database type"
            return

        user_text = self.fuzzy_entry.get_text().strip()
        if user_text:
            access_mode, query = table[FUZZY]
        else:
            access_mode, query = table[WHERE]
            user_text = self.where_entry.get_text().strip()
            if not user_text:
                self.where_entry.set_text("")
                while self._update_id:
                    context, namespace = self._update_id.popleft()
                    glib.source_remove(context)
                    namespace[0] = True
                self.list_store.clear()
                return

        qty = query.count("(%s)")
        if access_mode == CLEAN:
            query = (query, (self.trans_prepend, self.trans_from, ) + 
                                                    (user_text, ) * qty)
        elif access_mode == DIRTY:  # Accepting of SQL code in user data.
            query = (query % ((self.trans_prepend, self.trans_from, )
                                                    + (user_text, ) * qty), )
        else:
            print "unknown database access mode", access_mode
            return

        self._acc.request(query, self._handler, self._failhandler)
        return

    @staticmethod
    def _drag_data(model, paths):
        """Generate tuples of (path, filename) for the given paths."""
        
        for path in paths:
            row = model[path]
            yield row[7]

    def _cb_fuzzysearch_changed(self, widget):
        if widget.get_text().strip():
            self.where_entry.set_sensitive(False)
            self.where_entry.set_text("")
        else:
            self.where_entry.set_sensitive(True)
        self.update_button.clicked()
        
    ###########################################################################

    def _handler(self, acc, *args, **kwargs):
        PageCommon._handler(self, acc, *args, **kwargs)
        acc.purge_job_queue(1)

    def _failhandler(self, exception, notify):
        notify(str(exception))
        if exception[0] == 2006:
            raise

        glib.idle_add(self.tree_view.set_model, None)
        glib.idle_add(self.list_store.clear)

    ###########################################################################
    
    @threadslock
    def _update_1(self, acc, cursor, rows, namespace):
        if not namespace[0]:
            self.tree_view.set_model(None)
            self.list_store.clear()
            namespace[1] = (0, )  # found = 0
            context = glib.idle_add(self._update_2, acc, cursor, namespace)
            self._update_id.append((context, namespace))
        return False

    @threadslock
    def _update_2(self, acc, cursor, namespace):
        kill, (found, ) = namespace
        if kill:
            return False
        
        next_row = cursor.fetchone
        append = self.list_store.append

        for i in xrange(100):
            if acc.keepalive == False:
                return False

            try:
                row = next_row()
            except sql.Error:
                return False

            if row:
                found += 1
                append((found, ) + row)
            else:
                if found:
                    self.tree_cols[0].set_title("(%s)" % found)
                    self.tree_view.set_model(self.list_store)
                return False

        namespace[1] = (found, )
        return True


class MediaPane(gtk.Frame):
    """Database song details are displayed in this widget."""

    def __init__(self):
        gtk.Frame.__init__(self)

        self.set_shadow_type(gtk.SHADOW_IN)
        self.set_border_width(6)
        self.set_label_align(0.5, 0.5)
        main_vbox = gtk.VBox()
        self.add(main_vbox)
        self.notebook = gtk.Notebook()
        main_vbox.pack_start(self.notebook)
        
        self._tree_page = TreePage(self.notebook)
        self._flat_page = FlatPage(self.notebook)
        self.prefs_controls = PrefsControls()

        if have_songdb:
            self.prefs_controls.bind(self._dbtoggle)

        main_vbox.show_all()

    def repair_focusability(self):
        self._tree_page.repair_focusability()
        self._flat_page.repair_focusability()

    def get_col_widths(self, keyval):
        """Grab column widths as textual data."""
        
        try:
            target = getattr(self, keyval)
        except AttributeError:
            return ""
        else:
            return target.get_col_widths()
    
    def set_col_widths(self, keyval, data):
        """Column widths are to be restored on application restart."""
        
        if data:
            try:
                target = getattr(self, keyval)
            except AttributeError:
                return
            else:
                target.set_col_widths(data)

    def _dbtoggle(self, conn_data, trans_data):
        if conn_data:
            # Connect and discover the database type.
            self._acc1 = DBAccessor(**conn_data)
            self._acc2 = DBAccessor(**conn_data)
            self._trans_data = trans_data
            self._acc1.request(('SHOW tables',), self._stage_1, self._fail_1)
        else:
            try:
                self._acc1.close()
                self._acc2.close()
            except AttributeError:
                pass
            else:
                self._tree_page.deactivate()
                self._flat_page.deactivate()
            self.hide()

    @staticmethod
    def schema_test(string, data):
        data = frozenset(x[0] for x in data)
        return frozenset(string.split()).issubset(data)
    
    ###########################################################################

    def _safe_disconnect(self):
        glib.idle_add(threadslock(self.prefs_controls.disconnect))

    def _hand_over(self, database_name):
        self._tree_page.activate(self._acc1, database_name, self._trans_data)
        self._flat_page.activate(self._acc2, database_name, self._trans_data)
        glib.idle_add(threadslock(self.show))
            
    def _fail_1(self, exception, notify):
        # Give up.
        self._safe_disconnect()
        return True

    def _fail_2(self, exception, notify):
        try:
            code = exception.args[0]
        except IndexError:
            raise

        if code != 1061:
            notify(_('Failed to create FULLTEXT index'))
            print exception
            raise

        notify(_('Found existing FULLTEXT index'))

    def _stage_1(self, acc, request, cursor, notify, rows):
        """Running under the accessor worker thread!
        
        Step 1 Identifying database type.
        """
        
        data = cursor.fetchall()
        if self.schema_test("tracks", data):
            request(('DESCRIBE tracks',), self._stage_2, self._fail_1)
        elif self.schema_test("album artist song", data):
            request(('DESCRIBE song',), self._stage_4, self._fail_1)
        else:
            notify(_('Unrecognised database'))
            self._safe_disconnect()
            
    def _stage_2(self, acc, request, cursor, notify, rows):
        """Confirm it's a Prokyon 3 database."""
        
        if self.schema_test("artist title album tracknumber bitrate " 
                                        "path filename", cursor.fetchall()):
            notify(_('Found Prokyon 3 schema'))
            # Try to add a FULLTEXT database.
            request(("""ALTER TABLE tracks ADD FULLTEXT artist (artist,title,
                        album,filename)""",), self._stage_2a, self._fail_2)
        else:
            notify(_('Unrecognised database'))
            self._safe_disconnect()

    def _stage_2a(self, acc, request, cursor, notify, rows):
        request(("ALTER TABLE albums ADD INDEX idjc (name)",),
                self._stage_3, self._fail_2)

    def _stage_3(self, acc, request, cursor, notify, rows):
        self._hand_over(PROKYON_3)

    def _stage_4(self, acc, request, cursor, notify, rows):
        """Test for Ampache database."""

        if self.schema_test("artist title album track bitrate file", 
                                                            cursor.fetchall()):
            request(('DESCRIBE artist',), self._stage_5, self._fail_1)
        else:
            notify('Unrecognised database')
            self._safe_disconnect()

    def _stage_5(self, acc, request, cursor, notify, rows):
        if self.schema_test("name prefix", cursor.fetchall()):
            request(('DESCRIBE artist',), self._stage_6, self._fail_1)
        else:
            notify('Unrecognised database')
            self._safe_disconnect()

    def _stage_6(self, acc, request, cursor, notify, rows):
        if self.schema_test("name prefix", cursor.fetchall()):
            notify('Found Ampache schema')
            request(("ALTER TABLE album ADD FULLTEXT idjc (name)",),
                                                self._stage_7, self._fail_2)
        else:
            notify('Unrecognised database')
            self._safe_disconnect()
        
    def _stage_7(self, acc, request, cursor, notify, rows):
        request(("ALTER TABLE artist ADD FULLTEXT idjc (name)",), self._stage_8,
                                                                self._fail_2)
        
    def _stage_8(self, acc, request, cursor, notify, rows):
        request(("ALTER TABLE song ADD FULLTEXT idjc (title)",), self._stage_9,
                                                                self._fail_2)

    def _stage_9(self, acc, request, cursor, notify, rows):
        self._hand_over(AMPACHE)
