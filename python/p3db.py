#   p3db.py: prokyon3 database connectivity
#   Copyright (C) 2008 Stephen Fairchild (s-fairchild@users.sourceforge.net)
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

__all__ = ['MediaPane', 'Prefs']

import time
from urllib import quote

import gobject
import gtk

from idjc import FGlobs
from .tooltips import set_tip
from .gtkstuff import threadslock, DefaultEntry, LEDDict


import gettext
t = gettext.translation(FGlobs.package_name, FGlobs.localedir, fallback=True)
_ = t.gettext


try:
    import MySQLdb as sql
    import _mysql_exceptions as dberror
except:
    sql = None

def makeview(notebook, label_text, additional = None):
    vbox = gtk.VBox()
    vbox.set_spacing(2)
    scrollwindow = gtk.ScrolledWindow()
    alternate = gtk.VBox()
    vbox.pack_start(scrollwindow, True, True, 0)
    vbox.pack_start(alternate, True, True, 0)
    if additional is not None:
        vbox.pack_start(additional, False, False, 0)
    vbox.show()
    scrollwindow.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_ALWAYS)
    label = gtk.Label(label_text)
    notebook.append_page(vbox, label)
    label.show()
    scrollwindow.show()
    treeview = gtk.TreeView()
    scrollwindow.add(treeview)
    treeview.show()
    return treeview, scrollwindow, alternate

def makecolumns(view, name_ix_rf_mw):
    l = []
    for name, ix, rf, mw in name_ix_rf_mw:
        renderer = gtk.CellRendererText()
        column = gtk.TreeViewColumn(name, renderer)
        column.add_attribute(renderer, 'text', ix)
        if mw != -1:
            column.set_resizable(True)
            column.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
            column.set_min_width(mw)
            column.set_fixed_width(mw + 50)
        view.append_column(column)
        l.append(column)
        if rf is not None:
            column.set_cell_data_func(renderer, rf, ix)
    return l

class DNDAccumulator(list):
    """ Helper class for assembling a string of file URLs """
    def append(self, pathname, filename):
        list.append(self, "file://%s/%s\n" % (quote(pathname), quote(filename)))
    def __str__(self):
        return "".join(self)
    def __init__(self):
        list.__init__(self)

class TreePopulate(object):
    """ runs as an idle process building the tree view of the p3 database """
    @threadslock
    def run(self):
        i = 10
        append = self.mp.treestore.append
        d = self.d
        while i > 0:
            i -= 1
            row = self.c.fetchone()
            if row is None:
                self.mp.treeview.set_model(self.mp.treestore)
                self.mp.treealt.hide()
                self.mp.treescroll.show()
                self.mp.tree_idle = None
                retval = False
                break
            else:
                while 1:
                    if d == 0:
                        self.art = row[1]
                        self.artlower = self.art.lower()
                        self.iter1 = append(
                                        None, (-1, self.art, 0, 0, 0, "", "", 0)) 
                        d = 1
                    if d == 1:
                        if self.artlower == row[1].lower():
                            self.alb = row[2]
                            self.alblower = self.alb.lower()
                            self.iter2 = append(
                                    self.iter1, (-2, self.alb, 0, 0, 0, "", "", 0)) 
                            d = 2
                        else:
                            d = 0
                    if d == 2:
                        if self.artlower == row[1].lower() and self.alblower \
                                                            == row[2].lower():
                            if self.dbtype == "Ampache":
                                # Split the full path into path and file.
                                row = list(row)
                                fn = row[7].rsplit("/",1)
                                row[7] = fn[1]
                                row[8] = fn[0]
                            path = self.proktransform[1] + row[8][self.proktransform[0]:] 
                            append(self.iter2, (row[0], row[4], row[3],
                                                row[5], row[6], row[7], path, row[9]))
                            break
                        else:
                            d = 1
                retval = True
        self.d = d
        self.done += 10.0
        if int(self.done) % 100 == 0:
            self.mp.tree_pb.set_fraction(self.done / self.total)
        return retval
    def __init__(self, mp, c, dbtype, proktransform, total, start_time):
        self.mp = mp
        self.c = c
        self.dbtype = dbtype
        self.proktransform = proktransform
        self.total = float(total)
        self.start_time = start_time
        self.done = 0.0
        self.d = 0
        self.art = self.alb = ""

class MediaPane(gtk.Frame):
    """UI for viewing the prokyon 3 database"""
    
    sourcetargets = (
        #('MY_TREE_MODEL_ROW', gtk.TARGET_SAME_WIDGET, 0),
        ('text/plain', 0, 1),
        ('TEXT', 0, 2),
        ('STRING', 0, 3))

    def cond_cell_secs_to_h_m_s(self, column, renderer, model, iter, cell):
        if model.get_value(iter, 0) >= 0:
            return self.cell_secs_to_h_m_s(column, renderer, model, iter, cell)
        else:
            renderer.set_property("text", "")
    
    def cell_k(self, column, renderer, model, iter, cell):
        bitrate = model.get_value(iter, cell)
        if bitrate == 0:
            renderer.set_property("text", "")
        elif self.dbtype == "P3":
            renderer.set_property("text", "%dk" % bitrate)
        elif bitrate > 9999 and self.dbtype == "Ampache":
            renderer.set_property("text", "%dk" % (bitrate // 1000))
        renderer.set_property("xalign", 1.0)
    
    @staticmethod
    def cell_show_unknown(column, renderer, model, iter, cell):
        if model.get_value(iter, cell) == "":
            # TC: Placeholder for unknown data.
            renderer.set_property("text", _('<unknown>'))
    
    @staticmethod
    def cell_secs_to_h_m_s(column, renderer, model, iter, cell):
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
    def cell_ralign(column, renderer, model, iter, cell):
        val = model.get_value(iter, cell)
        if val:
            renderer.set_property("xalign", 1.0)
        else:
            renderer.set_property("text", "")

    def tree_select_func(self, info):
        return len(info) - 1

    def cb_drag_begin(self, widget, context):
        context.set_icon_stock(gtk.STOCK_CDROM, -5, -5)

    def cb_tree_drag_data_get(self, treeview, context, selection, target_id,
                                                                        etime):
        treeselection = treeview.get_selection()
        model, paths = treeselection.get_selected_rows()
        data = DNDAccumulator()
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

    def cb_flat_drag_data_get(self, treeview, context, selection, target_id,
                                                                        etime):
        treeselection = treeview.get_selection()
        model, paths = treeselection.get_selected_rows()
        data = DNDAccumulator()
        for each in paths:
            iter = model.get_iter(each)
            data.append(model.get_value(iter, 9), model.get_value(iter, 8))
        selection.set(selection.target, 8, str(data))

    def fuzzysearch_changed(self, widget):
        if widget.get_text().strip():
            self.whereentry.set_sensitive(False)
        else:
            self.whereentry.set_sensitive(True)
        self.update.clicked()

    def activate(self, db, dbtype, proktransform, label):
        self.set_label(label)
        self.db = db
        self.dbtype = dbtype
        self.proktransform = proktransform
        self.whereentry.set_text("")
        self.fuzzyentry.set_text("")
        # Show the 'Disk' column whenever the database supports it.
        for each in (self.treecols[1], self.flatcols[3]):
            each.set_visible(dbtype in ("Ampache",))
        self.show()
        self.tree_update.clicked()
    
    def deactivate(self):
        self.treestore.clear()
        self.flatstore.clear()
        self.hide()
        try:
            del self.db
            del self.dbtype
        except AttributeError:
            pass

    def cb_tree_update(self, widget):
        print "Start reading the %s database" % self.dbtype
        c = self.db.cursor()
        print "Setting UTF8 mode"
        try:
            # Set UTF8 mode for the database
            c.execute('set names utf8')
            c.execute('set character set utf8')
            c.execute('set character_set_connection=utf8')
        except dberror.MySQLError, inst:
            print "Failed to set UTF8: " + inst
            # Don't treat as fatal error, just warn
        print "Reading tracks"
        try:
            if self.dbtype == "P3":
                total = c.execute("SELECT id,artist,album,tracknumber,title,"
                    "length,bitrate,filename,path,0 as disk FROM tracks ORDER BY"
                    " artist,album,path,tracknumber,title")
            elif self.dbtype == "Ampache":
                total = c.execute("""SELECT song.id as id, 
                    concat_ws(" ", artist.prefix, artist.name) as artist, 
                    concat_ws(" ", album.prefix, album.name) as album,
                    track as tracknumber, title, time as length, 
                    bitrate, file, "" as padding, album.disk as disk
                    from song
                    left join artist on song.artist = artist.id 
                    left join album on song.album = album.id 
                    ORDER BY artist.name,album.disk,album.name,tracknumber,title""")
        except dberror.MySQLError, inst:
            print inst
            c.close()
        else:
            print "Start populating tree"
            self.treeview.set_model(None)
            self.treestore.clear()
            self.treescroll.hide()
            self.treealt.show()
            self.tree_pb.set_fraction(0.0)
            if self.tree_idle is not None:
                gobject.source_remove(self.tree_idle)
            tree_populate = TreePopulate(self, c, self.dbtype, self.proktransform, total, time.time())
            self.tree_idle = gobject.idle_add(tree_populate.run)
        
    def cb_update(self, widget):
        """ Database lookup performed here """
        fuzzy = self.fuzzyentry.get_text().strip()
        where = self.whereentry.get_text().strip()
        
        if not (fuzzy or where):
            where = "bitrate = -1"
            
        c = self.db.cursor()
        try:
            if fuzzy:
                while 1:
                    try:
                        if self.dbtype == "P3":
                            c.execute("""SELECT id,artist,album,
                                      tracknumber,title,length,bitrate,
                                      filename,path,0 as disk FROM tracks WHERE 
                                      MATCH (artist,album,title,filename) AGAINST (%s)""",
                                      (fuzzy, ))
                        if self.dbtype == "Ampache":
                            c.execute("""SELECT song.id as id,
                                concat_ws(" ",artist.prefix,artist.name),
                                concat_ws(" ",album.prefix,album.name),
                                track as tracknumber, title, time as length,
                                bitrate, file, "" as padding, album.disk as disk FROM song
                                LEFT JOIN artist ON artist.id = song.artist
                                LEFT JOIN album ON album.id = song.album
                                WHERE
                                 (MATCH(album.name) against(%s)
                                  OR MATCH(artist.name) against(%s)
                                  OR MATCH(title) against(%s)
                                 )
                            """,(fuzzy,fuzzy,fuzzy))
                        break
                    except dberror.OperationalError, inst:
                        if "FULLTEXT" in str(inst):
                            print "adding fulltext index to database"
                            if self.dbtype == "P3":
                                c.execute("ALTER TABLE tracks ADD FULLTEXT"
                                          "(artist,album,title,filename)")
                            if self.dbtype == "Ampache":
                                c.execute("ALTER TABLE album ADD FULLTEXT(name)")
                                c.execute("ALTER TABLE artist ADD FULLTEXT(name)")
                                c.execute("ALTER TABLE song ADD FULLTEXT(title)")
                        else:
                            raise
            else:
                if ";" in where:
                    raise ValueError("Semicolon character is banned from WHERE box.")
                if self.dbtype == "P3":
                    query = """SELECT id,artist,album,
                            tracknumber,title,length,
                            bitrate,filename, path, 0 as disk FROM tracks WHERE (%s) ORDER BY 
                            artist,album,path,tracknumber,title""" % where
                if self.dbtype == "Ampache":
                    query = """SELECT song.id as id,
                            concat_ws(" ", artist.prefix, artist.name) as artist,
                            concat_ws(" ", album.prefix, album.name) as albumname,
                            track as tracknumber, title,
                            time as length, bitrate, file, "" as padding,
                            album.disk as disk FROM song
                            LEFT JOIN album on album.id = song.album
                            LEFT JOIN artist on artist.id = song.artist
                            WHERE (%s) ORDER BY artist.name, album.name, file, album.disk, track, title
                            """ % where
                c.execute(query)
        except (dberror.MySQLError, ValueError), inst:
            print inst
            c.close()
            self.flatstore.clear()
            return

        self.flatview.set_model(None)
        self.flatstore.clear()
        found = 0
        while 1:
            row = c.fetchone()
            if row is not None:
                row = list(row)
                if self.dbtype == "Ampache":
                    # Split the file into path and filename
                    fn = row[7].rsplit("/",1)
                    row[7] = fn[1]
                    row[8] = fn[0]
                found += 1
                
                row[8] = self.proktransform[1] + row[8][self.proktransform[0]:]                 
                self.flatstore.append([found] + row)
            else:
                break
        self.flatcols[0].set_title("(%s)" % found)
        self.flatview.set_model(self.flatstore)
        c.close()

    def getcolwidths(self, cols):
        return ",".join([ str(x.get_width() or x.get_fixed_width())
                                                            for x in cols ])
    
    def setcolwidths(self, cols, data):
        c = cols.__iter__()
        for w in data.split(","):
            if w != "0":
                c.next().set_fixed_width(int(w))
            else:
                c.next()

    def __init__(self):
        gtk.Frame.__init__(self)
        self.set_shadow_type(gtk.SHADOW_IN)
        self.set_border_width(6)
        self.set_label_align(0.5, 0.5)

        vbox = gtk.VBox()
        self.add(vbox)
        vbox.show()
        
        self.notebook = gtk.Notebook()
        vbox.pack_start(self.notebook, True, True, 0)
        self.notebook.show()
        
        # tree gui
        buttonbox = gtk.HButtonBox()
        buttonbox.set_layout(gtk.BUTTONBOX_SPREAD)
        
        self.tree_update = gtk.Button(gtk.STOCK_REFRESH)
        self.tree_update.connect("clicked", self.cb_tree_update)
        self.tree_update.set_use_stock(True)
        buttonbox.add(self.tree_update)
        self.tree_update.show()
        
        self.tree_expand = gtk.Button(_('_Expand'), None, True)
        image = gtk.image_new_from_stock(gtk.STOCK_ADD, gtk.ICON_SIZE_BUTTON)
        self.tree_expand.set_image(image)
        buttonbox.add(self.tree_expand)
        self.tree_expand.show()
        
        self.tree_collapse = gtk.Button(_('_Collapse'), None, True)
        image = gtk.image_new_from_stock(gtk.STOCK_REMOVE, gtk.ICON_SIZE_BUTTON)
        self.tree_collapse.set_image(image)
        buttonbox.add(self.tree_collapse)
        self.tree_collapse.show()
        
        buttonbox.show()

        # TC: Refers to the tree view of the tracks database.
        self.treeview, self.treescroll, self.treealt = makeview(
                                        self.notebook, _('Tree'), buttonbox)
        self.treeview.set_enable_tree_lines(True)
        self.treeview.set_rubber_banding(True)
        treeselection = self.treeview.get_selection()
        treeselection.set_mode(gtk.SELECTION_MULTIPLE)
        treeselection.set_select_function(self.tree_select_func)
        self.tree_expand.connect_object("clicked", gtk.TreeView.expand_all,
                                                                self.treeview)
        self.tree_collapse.connect_object("clicked", gtk.TreeView.collapse_all,
                                                                self.treeview)
        # id, ARTIST-ALBUM-TITLE, TRACK, DURATION, BITRATE, filename, path, disk
        self.treestore = gtk.TreeStore(int, str, int, int, int, str, str, int)
        self.treeview.set_model(self.treestore)
        self.treecols = makecolumns(self.treeview, (
                ("%s - %s - %s" % (_('Artist'), _('Album'), _('Title')), 1,
                                                self.cell_show_unknown, 180),
                # TC: The disk number of the album track.
                (_('Disk'), 7, self.cell_ralign, -1),
                # TC: The album track number.
                (_('Track'), 2, self.cell_ralign, -1),
                # TC: Track playback time.
                (_('Duration'), 3, self.cond_cell_secs_to_h_m_s, -1),
                (_('Bitrate'), 4, self.cell_k, -1),
                (_('Filename'), 5, None, 100),
                # TC: Directory path to a file.
                (_('Path'), 6, None, -1),
                ))
        
        self.treeview.enable_model_drag_source(gtk.gdk.BUTTON1_MASK,
            self.sourcetargets, gtk.gdk.ACTION_DEFAULT | gtk.gdk.ACTION_COPY)
        self.treeview.connect_after("drag-begin", self.cb_drag_begin)
        self.treeview.connect("drag_data_get", self.cb_tree_drag_data_get)
        
        vbox = gtk.VBox()
        vbox.set_border_width(20)
        vbox.set_spacing(20)
        # TC: The database tree view is being built (populated).
        label = gtk.Label(_('Populating'))
        vbox.pack_start(label, False, False, 0)
        self.tree_pb = gtk.ProgressBar()
        vbox.pack_start(self.tree_pb, False, False, 0)
        self.treealt.add(vbox)
        vbox.show_all()
        
        self.tree_idle = None
        
        # flat gui
        # TC: User specified search filter entry box title text.
        filterframe = gtk.Frame(" %s " % _('Filters'))
        filterframe.set_shadow_type(gtk.SHADOW_OUT)
        filterframe.set_border_width(1)
        filterframe.set_label_align(0.5, 0.5)
        filterframe.show()
        filtervbox = gtk.VBox()
        filtervbox.set_border_width(3)
        filtervbox.set_spacing(1)
        filterframe.add(filtervbox)
        filtervbox.show()
        
        fuzzyhbox = gtk.HBox()
        filtervbox.pack_start(fuzzyhbox, False, False, 0)
        fuzzyhbox.show()
        # TC: A type of search on any data field matching paritial strings.
        fuzzylabel = gtk.Label(_('Fuzzy Search'))
        fuzzyhbox.pack_start(fuzzylabel, False, False, 0)
        fuzzylabel.show()
        self.fuzzyentry = gtk.Entry()
        self.fuzzyentry.connect("changed", self.fuzzysearch_changed)
        fuzzyhbox.pack_start(self.fuzzyentry, True, True, 0)
        self.fuzzyentry.show()
        
        wherehbox = gtk.HBox()
        filtervbox.pack_start(wherehbox, False, False, 0)
        wherehbox.show()
        # TC: WHERE is an SQL keyword.
        wherelabel = gtk.Label(_('WHERE'))
        wherehbox.pack_start(wherelabel, False, False, 0)
        wherelabel.show()
        self.whereentry = gtk.Entry()
        self.whereentry.connect("activate", self.cb_update)
        wherehbox.pack_start(self.whereentry, True, True, 0)
        self.whereentry.show()
        image = gtk.image_new_from_stock(gtk.STOCK_EXECUTE,
                                                        gtk.ICON_SIZE_BUTTON)
        self.update = gtk.Button()
        self.update.connect("clicked", self.cb_update)
        self.update.set_image(image)
        image.show
        wherehbox.pack_start(self.update, False, False, 0)
        self.update.show()
        
        self.flatview, self.flatscroll, self.flatalt = makeview(
                                        self.notebook, _('Flat'), filterframe)
        self.flatview.set_rules_hint(True)
        self.flatview.set_rubber_banding(True)
        treeselection = self.flatview.get_selection()
        treeselection.set_mode(gtk.SELECTION_MULTIPLE)
        #                           found, id, ARTIST, ALBUM, TRACKNUM, TITLE,
        #                           DURATION, BITRATE, path, filename, disk
        self.flatstore = gtk.ListStore(
                            int, int, str, str, int, str, int, int, str, str, int)
        self.flatview.set_model(self.flatstore)
        self.flatcols = makecolumns(self.flatview, (
                ("(%d)" % 0, 0, self.cell_ralign, -1),
                (_('Artist'), 2, self.cell_show_unknown, 100),
                (_('Album'), 3, self.cell_show_unknown, 100),
                (_('Disk'), 10, self.cell_ralign, -1),
                (_('Track'), 4, self.cell_ralign, -1),
                (_('Title'), 5, self.cell_show_unknown, 100),
                (_('Duration'), 6, self.cell_secs_to_h_m_s, -1),
                (_('Bitrate'), 7, self.cell_k, -1),
                (_('Filename'), 8, None, 100),
                (_('Path'), 9, None, -1),
                ))

        self.flatview.enable_model_drag_source(gtk.gdk.BUTTON1_MASK,
            self.sourcetargets, gtk.gdk.ACTION_DEFAULT | gtk.gdk.ACTION_COPY)
        self.flatview.connect_after("drag-begin", self.cb_drag_begin)
        self.flatview.connect("drag_data_get", self.cb_flat_drag_data_get)

class Prefs(gtk.Frame):
    """ Controls and settings for Prokyon3 database connectivity """

    def set_ui_state(self, state):
        sens = not state
        self.prokhostname.set_sensitive(sens)
        self.pathdelchars.set_sensitive(sens)
        self.pathaddchars.set_sensitive(sens)
        self.prokuser.set_sensitive(sens)
        self.prokdatabase.set_sensitive(sens)
        self.prokpassword.set_sensitive(sens)
        self.prok_led_image.set_from_pixbuf(self.led["green" 
                                                        if state else "clear"])
        if state:
            # TC: P3 refers to Prokyon3, a music cataloging program.
            self.main.topleftpane.activate(self.db, self.dbtype, self.proktransform, " %s " % 
                    (_('%s Database View (%s)') % (self.dbtype, self.prokdatabase.get_text())))
        else:
            self.main.topleftpane.deactivate()
            
    def cb_proktoggle(self, widget):
        def dbtest(c, command, checkitems):
            c.execute(command)
            q = c.fetchall()
            refcount = 0
            for qitem in q:
                if qitem[0] in checkitems:
                    refcount += 1
            if refcount != len(checkitems):
                raise dberror.ProgrammingError, "database format not supported"
                " due to missing reference to one or more of:\n    "
                "%s,\n   for command: %s" % (str(checkitems), command)

        if sql is not None:
            if widget.get_active():
                self.proktransform = (self.pathdelchars.get_value_as_int(), self.pathaddchars.get_text())
                try:
                    host, port = self.prokhostname.get_text().strip().rsplit(":", 1)
                    port = int(port)
                except ValueError:
                    host = self.prokhostname.get_text().strip()
                    port = 3306  # Default MySQL port.

                try:
                    self.db = sql.connect(host=host, port=port,
                            user=self.prokuser.get_text(),
                            passwd=self.prokpassword.get_text(),
                            db=self.prokdatabase.get_text(), connect_timeout=3)

                    c = self.db.cursor()
                    # check this database looks familiar enough to use
                    print "Checking for prokyon format"
                    dbtest(c, "SHOW tables", ("tracks", ))
                    dbtest(c, "DESCRIBE tracks", ("artist", "title", "album",
                              "tracknumber", "bitrate", "path", "filename"))
                    self.dbtype = "P3"
                    c.close()
                except dberror.MySQLError, inst:
                    print "prokyon: ", inst
                    self.dbtype = None
                    try:
                        c.close()
                    except Exception:
                        pass
                else:
                    self.set_ui_state(True)
                    self.dbtype = "P3"
                    print "connected to %s type database" % self.dbtype

                if self.dbtype is None: #Check for ampache database
                    try:
                        self.db = sql.connect(host=host, port=port,
                            user=self.prokuser.get_text(),
                            passwd=self.prokpassword.get_text(),
                            db=self.prokdatabase.get_text(), connect_timeout=3)
                        c = self.db.cursor()
                        print "Checking for ampache format"
                        dbtest(c, "SHOW tables", ("album", "artist", "song"))
                        dbtest(c, "DESCRIBE album", ("name", "prefix"))
                        dbtest(c, "DESCRIBE artist", ("name", "prefix"))
                        dbtest(c, "DESCRIBE song", ("artist", "title", "album",
                                                    "track", "bitrate", "file"))
                        self.dbtype = "Ampache"
                        c.close()
                    except dberror.MySQLError, inst:
                        print "ampache: ", inst
                        self.dbtype = None
                        try:
                            c.close()
                        except Exception:
                            pass
                    else:
                        self.set_ui_state(True)
                        self.dbtype = "Ampache"
                        print "connected to %s type database" % self.dbtype
                if self.dbtype == None:
                    widget.set_active(False)
            else:
                try:
                    self.db.close()
                    self.dbtype = None
                except (AttributeError, NameError, dberror.MySQLError):
                    pass
                else:
                    self.set_ui_state(False)
                    print "database connection removed"


    def __init__(self, parent):
        gtk.Frame.__init__(self)
        self.main = parent
        label = gtk.Label(_('Prokyon3 or Ampache (song title) Database'))
        set_tip(label, _('You can make certain media databases accessible in IDJC for easy drag and drop into the playlists.'))
        self.prok_led_image = gtk.Image()
        hbox = gtk.HBox()
        hbox.pack_start(label, False, False, 4)
        if sql:
            hbox.pack_start(self.prok_led_image, False, False, 4)
        hbox.show_all()
        self.led = LEDDict()
        self.prok_led_image.set_from_pixbuf(self.led["clear"])
        self.set_label_widget(hbox)
        self.set_border_width(3)
        table = gtk.Table(4, 4)
        table.set_border_width(10)
        if sql:
            self.add(table)
        else:
            vbox = gtk.VBox()
            vbox.set_border_width(3)
            # TC: shown when the dependency is missing.
            label = gtk.Label(_('Python module MySQLdb required'))
            vbox.add(label)
            label.show()
            self.add(vbox)
            vbox.show()
        table.show()
        table.set_row_spacing(0, 1)
        table.set_row_spacing(1, 1)
        table.set_row_spacing(2, 1)
        table.set_row_spacing(3, 1)
        table.set_col_spacing(0, 3)
        table.set_col_spacing(1, 10)
        table.set_col_spacing(2, 3)
        hostlabel = gtk.Label(_('Hostname[:Port]'))
        hostlabel.set_alignment(1.0, 0.5)
        table.attach(hostlabel, 0, 1, 0, 1, gtk.SHRINK | gtk.FILL)
        hostlabel.show()
        self.prokhostname = DefaultEntry("localhost", True)
        table.attach(self.prokhostname, 1, 4, 0, 1)
        self.prokhostname.show()
        
        prefixlabel = gtk.Label(_('File Path Modify'))
        prefixlabel.set_alignment(1.0, 0.5)
        table.attach(prefixlabel, 0, 1, 1, 2, gtk.SHRINK | gtk.FILL)
        prefixlabel.show()
        
        hbox = gtk.HBox()
        hbox.set_spacing(3)
        label = gtk.Label(_('-'))
        hbox.pack_start(label, False)
        label.show()
        adj = gtk.Adjustment(0.0, 0.0, 999.0, 1.0, 1.0)
        self.pathdelchars = gtk.SpinButton(adj, 0.0, 0)
        set_tip(self.pathdelchars, _('The number of characters to strip from the left hand side of media file paths.'))
        hbox.pack_start(self.pathdelchars, False)
        self.pathdelchars.show()
        label = gtk.Label('+')
        hbox.pack_start(label, False)
        label.show()
        self.pathaddchars = gtk.Entry()
        set_tip(self.pathaddchars, _('The characters to prefix to the media file paths.'))
        hbox.pack_start(self.pathaddchars)
        self.pathaddchars.show()
        table.attach(hbox, 1, 4, 1, 2)
        hbox.show()
        
        userlabel = gtk.Label(_('User Name'))
        userlabel.set_alignment(1.0, 0.5)
        table.attach(userlabel, 0, 1, 3, 4, gtk.SHRINK | gtk.FILL)
        userlabel.show()
        self.prokuser = DefaultEntry("prokyon", True)
        self.prokuser.set_size_request(30, -1)
        table.attach(self.prokuser, 1, 2, 3, 4)
        self.prokuser.show()
        databaselabel = gtk.Label(_('Database'))
        databaselabel.set_alignment(1.0, 0.5)
        table.attach(databaselabel, 2, 3, 3, 4, gtk.SHRINK | gtk.FILL)
        databaselabel.show()
        self.prokdatabase = DefaultEntry("prokyon", True)
        self.prokdatabase.set_size_request(30, -1)
        table.attach(self.prokdatabase, 3, 4, 3, 4)
        self.prokdatabase.show()
        passwordlabel = gtk.Label(_('Password'))
        passwordlabel.set_alignment(1.0, 0.5)
        table.attach(passwordlabel, 0, 1, 4, 5, gtk.SHRINK | gtk.FILL)
        passwordlabel.show()
        self.prokpassword = DefaultEntry("prokyon", True)
        self.prokpassword.set_size_request(30, -1)
        self.prokpassword.set_visibility(False)
        table.attach(self.prokpassword, 1, 2, 4, 5)
        self.prokpassword.show()
        # TC: Button text, cause connection to the selected database.
        self.proktoggle = gtk.ToggleButton(_('Database Connect'))
        self.proktoggle.set_size_request(10, -1)
        self.proktoggle.connect("toggled", self.cb_proktoggle)
        table.attach(self.proktoggle, 2, 4, 4, 5)
        self.proktoggle.show()
        self.db = None
        self.dbtype = None
    
