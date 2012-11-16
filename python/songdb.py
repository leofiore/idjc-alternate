#   songdb.py: music database connectivity
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


import time
import gettext
import threading
from functools import partial, wraps

import glib
import gtk
try:
    import MySQLdb as sql
except ImportError:
    sql = None

from idjc import FGlobs
from .tooltips import set_tip
from .gtkstuff import threadslock, DefaultEntry


__all__ = ['MediaPane']

t = gettext.translation(FGlobs.package_name, FGlobs.localedir, fallback=True)
_ = t.gettext


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
        self.handle = None  # No connections made until there is a query.
        self.cursor = None
        self.jobs = []
        self.semaphore = threading.Semaphore()
        self.lock = threading.Lock()
        self.keepalive = True
        self.start()

    def request(self, sql_query, handler, failhandler):
        """Add a request to the job queue.
        
        sql_query is a one or 2 tuple e.g.
                ("DESCRIBE SONGS",)
                ("DESCRIBE %s", ("SONGS",))
        
        def handler(sql_cursor, notify)
            def notify("status message")

        def failhandler(exception, notify)
        """
        
        self.jobs.append((sql_query, handler, failhandler))
        self.semaphore.release()
        
    def run(self):
        notify = partial(glib.idle_add, threadslock(self.notify))
        
        while self.keepalive:
            self.semaphore.acquire()
            if self.keepalive and self.jobs:
                query, handler, failhandler = self.jobs.pop(0)

                trycount = 0
                while trycount < 4:
                    try:
                        self.cursor.execute(*query)
                    except sql.OperationalError as e:
                        if self.keepalive:
                            # Unhandled errors will be treated like
                            # connection failures.
                            if self.handle.open and failhandler is not None:
                                failhandler(e, notify)
                                break
                            else:
                                try:
                                    self.cursor.close()
                                except Exception:
                                    pass
                                    
                                try:
                                    self.handle.close()
                                except Exception:
                                    pass

                                raise
                        else:
                            break
                    except (sql.Error, AttributeError):
                        with self.lock:
                            if self.keepalive:
                                notify(_('Connecting'))
                                trycount += 1
                                try:
                                    self.handle = sql.connect(
                                        host=self.hostname,
                                        port=self.port, user=self.user,
                                        passwd=self.password, db=self.database,
                                        connect_timeout=3)
                                    self.cursor = self.handle.cursor()
                                except sql.Error as e:
                                    notify(_("Connection failed (try %d)") % i)
                                    print e
                                    time.sleep(0.5)
                                else:
                                    notify(_('Connected'))
                    else:
                        if self.keepalive:
                            for dummy in handler(self.cursor, notify):
                                if not self.keepalive:
                                    break
                        break
                
                else:
                    notify(_('Job dropped'))

        notify(_('Disconnected'))

    def close(self):
        """Clean up the worker thread prior to disposal."""
        
        self.keepalive = False
        self.semaphore.release()

        # If the thread is stuck on IO unblock it by closing the connection.
        # We should clean up in any event.
        with self.lock:
            try:
                self.cursor.close()
            except Exception:
                pass
                
            try:
                self.handle.close()
            except Exception:
                pass

        self.join()  # Hopefully this will complete quickly.
        del self.jobs[:]


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
        
        # List of widgets that should be made insensitive when db is active. 
        self._parameters = []  
        if not sql:
            # Feature is disabled.
            vbox = gtk.VBox()
            vbox.set_sensitive(False)
            vbox.set_border_width(3)
            label = gtk.Label(_('Python module MySQLdb required'))
            vbox.add(label)
            self.add(vbox)
            self.data_panel = gtk.VBox()  # Empty placeholder widget.
        else:
            # Control widgets.
            table = gtk.Table(5, 4)
            table.set_border_width(10)
            table.set_row_spacings(1)
            for col, spc in zip(xrange(3), (3, 10, 3)):
                table.set_col_spacing(col, spc)

            # Attachment for labels.
            l_attach = partial(table.attach, xoptions=gtk.SHRINK | gtk.FILL)
            
            # Top row.
            hostportlabel, self._hostnameport = self._factory(
                                            _('Hostname[:Port]'), 'localhost')
            l_attach(hostportlabel, 0, 1, 0, 1)
            table.attach(self._hostnameport, 1, 4, 0, 1)
            
            # Second row.
            hbox = gtk.HBox()
            hbox.set_spacing(3)
            fpmlabel, self._addchars = self._factory(
                                                _('File Path Modify'), None)
            adj = gtk.Adjustment(0.0, 0.0, 999.0, 1.0, 1.0)
            self._delchars = gtk.SpinButton(adj, 0.0, 0)
            self._parameters.append(self._delchars)
            set_tip(self._delchars, _('The number of characters to strip from '
                                    'the left hand side of media file paths.'))
            set_tip(self._addchars, 
                        _('The characters to prefix to the media file paths.'))
            l_attach(fpmlabel, 0, 1, 1, 2)
            minus = gtk.Label('-')
            hbox.pack_start(minus, False)
            hbox.pack_start(self._delchars, False)
            plus = gtk.Label('+')
            hbox.pack_start(plus, False)
            hbox.pack_start(self._addchars)
            table.attach(hbox, 1, 4, 1, 2)
            
            # Third row.
            userlabel, self._user = self._factory(_('User Name'), "admin")
            l_attach(userlabel, 0, 1, 3, 4)
            table.attach(self._user, 1, 2, 3, 4)
            dblabel, self._database = self._factory(_('Database'), "ampache")
            l_attach(dblabel, 2, 3, 3, 4)
            table.attach(self._database, 3, 4, 3, 4)
            
            # Fourth row.
            passlabel, self._password = self._factory(_('Password'), 'password')
            self._password.set_visibility(False)
            l_attach(passlabel, 0, 1, 4, 5)
            table.attach(self._password, 1, 2, 4, 5)
            self.dbtoggle = gtk.ToggleButton(_('Music Database'))
            self.dbtoggle.set_size_request(10, -1)
            self.dbtoggle.connect("toggled", self._cb_dbtoggle)
            table.attach(self.dbtoggle, 2, 4, 4, 5)
            
            # Notification row.
            self._statusbar = gtk.Statusbar()
            self._statusbar.set_has_resize_grip(False)
            self._notify(_('Disconnected'))
            table.attach(self._statusbar, 0, 4, 5, 6)
            
            self.add(table)
            self.data_panel = gtk.VBox()  # Bring in widget at some point.
            
        self.data_panel.set_no_show_all(False)
        self.show_all()
        
        # Save and Restore settings.
        self.activedict = {"songdb_toggle": self.dbtoggle}
        self.valuesdict = {"songdb_delchars": self._delchars}
        self.textdict = {"songdb_hostnameport": self._hostnameport,
            "songdb_user": self._user, "songdb_password": self._password,
            "songdb_dbname": self._database, "songdb_addchars": self._addchars}
        
    def bind(self, callback):
        """Connect with the activate method of the view pane."""
        
        self.dbtoggle.connect("toggled", self._cb_bind, callback)

    def _cb_bind(self, widget, callback):
        """This runs when the database is toggled on and off."""
        
        if widget.get_active():
            # Collate parameters for DBAccessor contructors.
            conn_data = {"notify": self._notify}
            for key in "hostnameport user password database".split():
                conn_data[key] = getattr(self, "_" + key).get_text().strip()
            
            # Make a file path transformation function.
            del_qty = self._delchars.get_value()
            prepend_str = self._addchars.get_text().strip()

            if del_qty or prepend_str:
                def transform(input_str):
                    return prepend_str + input_str[del_qty:]
            else:
                transform = lambda s: s  # Do nothing.
        else:
            conn_data = transform = None

        callback(conn_data, transform)

    def _cb_dbtoggle(self, widget):
        """Parameter widgets to be made insensitive when db is active."""
    
        sens = not widget.get_active()
    
        for each in self._parameters:
            each.set_sensitive(sens)

    def _notify(self, message):
        """Display status messages beneath the prefs settings."""
        
        self._statusbar.push(1, message)
        # To ensure readability of long messages also set the tooltip.
        self._statusbar.set_tooltip_text(message)

    def _factory(self, labeltext, entrytext=None):
        """Widget factory method."""
        
        label = gtk.Label(labeltext)
        label.set_alignment(1.0, 0.5)
        
        if entrytext:
            entry = DefaultEntry(entrytext, True)
        else:
            entry = gtk.Entry()
            
        entry.set_size_request(10, -1)
        self._parameters.append(entry)
        return label, entry


class PageCommon(gtk.VBox):
    """Base class for TreePage and FlatPage."""
    
    def __init__(self, notebook, label_text, controls):
        gtk.VBox.__init__(self)
        self.set_spacing(2)
        self.scrolled_window = gtk.ScrolledWindow()
        self.scrolled_window.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_ALWAYS)
        self.pack_start(self.scrolled_window)
        self.tree_view = gtk.TreeView()
        self.tree_view.set_rubber_banding(True)
        self.tree_selection = self.tree_view.get_selection()
        self.tree_selection.set_mode(gtk.SELECTION_MULTIPLE)
        self.scrolled_window.add(self.tree_view)
        self.pack_start(controls, False)
        label = gtk.Label(label_text)
        notebook.append_page(self, label)
        
        self.tree_view.enable_model_drag_source(gtk.gdk.BUTTON1_MASK,
            self._sourcetargets, gtk.gdk.ACTION_DEFAULT | gtk.gdk.ACTION_COPY)
        self.tree_view.connect_after("drag-begin", self._cb_drag_begin)
        self.tree_view.connect("drag_data_get", self._cb_drag_data_get)

    def db_toggle(self, conn_data, transform):
        if conn_data is not None:
            self.transform = transform
            self.db_accessor = DBAccessor(**conn_data)
        else:
            self.cleanup()

    def cleanup(self):
        if self.db_accessor is not None:
            self.db_accessor.close()
            self.db_accessor = None

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

    _sourcetargets = (  # Drag and drop source target specs.
        ('text/plain', 0, 1),
        ('TEXT', 0, 2),
        ('STRING', 0, 3))

    def _cb_drag_begin(self, widget, context):
        """Set icon for drag and drop operation."""

        context.set_icon_stock(gtk.STOCK_CDROM, -5, -5)

    @staticmethod
    def _make_tv_columns(tree_view, parameters):
        """Build a TreeViewColumn list from a table of data."""

        list_ = []
        for label, data_index, data_function, mw in parameters:
            renderer = gtk.CellRendererText()
            column = gtk.TreeViewColumn(label, renderer)
            column.add_attribute(renderer, 'text', data_index)
            if mw != -1:
                column.set_resizable(True)
                column.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
                column.set_min_width(mw)
                column.set_fixed_width(mw + 50)
            tree_view.append_column(column)
            list_.append(column)
            if data_function is not None:
                column.set_cell_data_func(renderer, data_function, data_index)
        return list_

    def _cond_cell_secs_to_h_m_s(self, column, renderer, model, iter, cell):
        if model.get_value(iter, 0) >= 0:
            return self.cell_secs_to_h_m_s(column, renderer, model, iter, cell)
        else:
            renderer.set_property("text", "")
    
    def _cell_k(self, column, renderer, model, iter, cell):
        bitrate = model.get_value(iter, cell)
        if bitrate == 0:
            renderer.set_property("text", "")
        elif self.dbtype == "P3":
            renderer.set_property("text", "%dk" % bitrate)
        elif bitrate > 9999 and self.dbtype == "Ampache":
            renderer.set_property("text", "%dk" % (bitrate // 1000))
        renderer.set_property("xalign", 1.0)
    
    @staticmethod
    def _cell_show_unknown(column, renderer, model, iter, cell):
        if model.get_value(iter, cell) == "":
            # TC: Placeholder for unknown data.
            renderer.set_property("text", _('<unknown>'))
    
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
        else:
            renderer.set_property("text", "")


def drag_data_get_common(func):
    @wraps(func)
    def inner(self, tree_view, context, selection, target_id, etime):
        tree_selection = tree_view.get_selection()
        model, paths = tree_selectoin.get_selected_rows()
        data = DNDAccumulator()
        return func(tree_view, model, paths, data, selection)
        
    return inner


class TreePage(PageCommon):
    """Tree UI with Artist, Album, Title heirarchy."""

    def __init__(self, notebook):
        # Base class overwrites these values.
        self.scrolled_window = self.tree_view = self.tree_selection = None
        self.transfrom = self.db_accessor = None
        
        self.controls = gtk.HButtonBox()
        self.controls.set_layout(gtk.BUTTONBOX_SPREAD)
        tree_rebuild = gtk.Button(gtk.STOCK_REFRESH)
        tree_rebuild.connect("clicked", self._cb_tree_rebuild)
        tree_rebuild.set_use_stock(True)
        tree_expand = gtk.Button(_('_Expand'), None, True)
        image = gtk.image_new_from_stock(gtk.STOCK_ADD, gtk.ICON_SIZE_BUTTON)
        tree_expand.set_image(image)
        tree_collapse = gtk.Button(_('_Collapse'), None, True)
        image = gtk.image_new_from_stock(gtk.STOCK_REMOVE, gtk.ICON_SIZE_BUTTON)
        tree_collapse.set_image(image)
        for each in (tree_rebuild, tree_expand, tree_collapse):
            self.controls.add(each)
            
        PageCommon.__init__(self, notebook, _("Tree"), self.controls)
        
        self.tree_view.set_enable_tree_lines(True)
        self.tree_selection.set_select_function(self._tree_select_func)

        tree_expand.connect_object("clicked", gtk.TreeView.expand_all,
                                                                self.tree_view)
        tree_collapse.connect_object("clicked", gtk.TreeView.collapse_all,
                                                                self.tree_view)

        # id, ARTIST-ALBUM-TITLE, TRACK, DURATION, BITRATE, filename, path, disk
        self.tree_store = gtk.TreeStore(int, str, int, int, int, str, str, int)
        self.tree_view.set_model(self.tree_store)
        self.tree_cols = self._make_tv_columns(self.tree_view, (
                ("%s - %s - %s" % (_('Artist'), _('Album'), _('Title')), 1,
                                                self._cell_show_unknown, 180),
                # TC: The disk number of the album track.
                (_('Disk'), 7, self._cell_ralign, -1),
                # TC: The album track number.
                (_('Track'), 2, self._cell_ralign, -1),
                # TC: Track playback time.
                (_('Duration'), 3, self._cond_cell_secs_to_h_m_s, -1),
                (_('Bitrate'), 4, self._cell_k, -1),
                (_('Filename'), 5, None, 100),
                # TC: Directory path to a file.
                (_('Path'), 6, None, -1),
                ))
                
        self.loading_vbox = gtk.VBox()
        self.loading_vbox.set_border_width(20)
        self.loading_vbox.set_spacing(20)
        # TC: The database tree view is being built (populated).
        label = gtk.Label(_('Populating'))
        self.loading_vbox.pack_start(label, False)
        self.progress_bar = gtk.ProgressBar()
        self.loading_vbox.pack_start(self.progress_bar, False)
        
        self.show_all()

    def set_loading_view(self, loading):
        if loading:
            self.controls.hide()
            self.scrolled_window.hide()
            self.loading_vbox.show()
        else:
            self.loading_vbox.hide()
            self.scrolled_window.show()
            self.controls.show()

    def _cb_tree_rebuild(self, widget):
        """(Re)load the tree with info from the database."""

        pass

    def _tree_select_func(self, info):
        return len(info) - 1

    @drag_data_get_common
    def _cb_drag_data_get(tree_view, model, paths, data, selection):
        if len(paths) == 1 and len(paths[0]) == 2:
            d2 = 0
            while 1:
                try:
                    iter = model.get_iter(paths[0] + (d2, ))
                except ValueError:
                    break
                data.append(model.get_value(iter, 6), model.get_value(iter, 5))
                d2 += 1
        else:
            for each in paths:
                if len(each) == 3:
                    iter = model.get_iter(each)
                    data.append(model.get_value(iter, 6),
                                                        model.get_value(iter,5))
        selection.set(selection.target, 8, str(data))


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
        where_hbox.pack_start(self.update_button)
        
        PageCommon.__init__(self, notebook, _("Flat"), self.controls)
 
        # Row data specification:
        # index, id, ARTIST, ALBUM, TRACKNUM, TITLE, DURATION, BITRATE,
        # path, filename, disk
        self.list_store = gtk.ListStore(
                        int, int, str, str, int, str, int, int, str, str, int)
        self.tree_view.set_model(self.list_store)
        self.tree_cols = self._make_tv_columns(self.tree_view, (
                ("(%d)" % 0, 0, self._cell_ralign, -1),
                (_('Artist'), 2, self._cell_show_unknown, 100),
                (_('Album'), 3, self._cell_show_unknown, 100),
                (_('Disk'), 10, self._cell_ralign, -1),
                (_('Track'), 4, self._cell_ralign, -1),
                (_('Title'), 5, self._cell_show_unknown, 100),
                (_('Duration'), 6, self._cell_secs_to_h_m_s, -1),
                (_('Bitrate'), 7, self._cell_k, -1),
                (_('Filename'), 8, None, 100),
                (_('Path'), 9, None, -1),
                ))

        self.tree_view.set_rules_hint(True)

    def repair_focusability(self):
        self.fuzzy_entry.set_flags(gtk.CAN_FOCUS)
        self.where_entry.set_flags(gtk.CAN_FOCUS)

    def _cb_update(self, widget):
        print "update button was pressed"

    @drag_data_get_common
    def _cb_drag_data_get(self, tree_view, model, paths, data, selection):
        for each in paths:
            iter = model.get_iter(each)
            data.append(model.get_value(iter, 9), model.get_value(iter, 8))
        selection.set(selection.target, 8, str(data))

    def _cb_fuzzysearch_changed(self, widget):
        if widget.get_text().strip():
            self.where_entry.set_sensitive(False)
        else:
            self.where_entry.set_sensitive(True)
        self.update_button.clicked()


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
        self.prefs_controls.bind(self._dbtoggle)

        main_vbox.show_all()

    def cleanup(self):
        for each in (self._tree_page, self._flat_page):
            each.cleanup()

    def repair_focusability(self):
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

    def _dbtoggle(self, *args):
        self.set_visible(any(args))
        self._tree_page.db_toggle(*args)
        self._flat_page.db_toggle(*args)
