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

import pygtk
pygtk.require('2.0')
import gtk, gobject, time
from idjc_config import *
from IDJCfree import threadslock
from ln_text import ln
from urllib import quote

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
            #print "Database parsed in %f seconds" % (time.time() - self.start_time)
            break
         else:
            while 1:
               if d == 0:
                  self.art = row[1]
                  self.artlower = self.art.lower()
                  self.iter1 = append(None, (-1, self.art, 0, 0, 0, "", "")) 
                  d = 1
               if d == 1:
                  if self.artlower == row[1].lower():
                     self.alb = row[2]
                     self.alblower = self.alb.lower()
                     self.iter2 = append(self.iter1, (-2, self.alb, 0, 0, 0, "", "")) 
                     d = 2
                  else:
                     d = 0
               if d == 2:
                  if self.artlower == row[1].lower() and self.alblower == row[2].lower():
                     append(self.iter2, (row[0], row[4], row[3], row[5], row[6], row[7], row[8]))
                     break
                  else:
                     d = 1
            retval = True
      self.d = d
      self.done += 10.0
      if int(self.done) % 100 == 0:
         self.mp.tree_pb.set_fraction(self.done / self.total)
      return retval
   def __init__(self, mp, c, total, start_time):
      self.mp = mp
      self.c = c
      self.total = float(total)
      self.start_time = start_time
      self.done = 0.0
      self.d = 0
      self.art = self.alb = ""

class MediaPane(gtk.Frame):
   """ UI for viewing the prokyon 3 database"""
   
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
   
   @staticmethod
   def cell_show_unknown(column, renderer, model, iter, cell):
      if model.get_value(iter, cell) == "":
         renderer.set_property("text", ln.dbunknown)
   
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

   def cb_tree_drag_data_get(self, treeview, context, selection, target_id, etime):
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
               data.append(model.get_value(iter, 6), model.get_value(iter,5))
      selection.set(selection.target, 8, str(data))

   def cb_flat_drag_data_get(self, treeview, context, selection, target_id, etime):
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

   def activate(self, db, label):
      self.set_label(label)
      self.db = db
      self.whereentry.set_text("")
      self.fuzzyentry.set_text("")
      self.show()
      self.tree_update.clicked()
   
   def deactivate(self):
      self.hide()
      try:
         del self.db
      except AttributeError:
         pass

   def cb_tree_update(self, widget):
      c = self.db.cursor()
      try:
         total = c.execute("""SELECT id,artist,album,tracknumber,title,length,bitrate,filename,path FROM tracks ORDER BY artist,album,path,tracknumber,title""")
      except dberror.MySQLError, inst:
         print inst
         c.close()
      else:
         self.treeview.set_model(None)
         self.treestore.clear()
         self.treescroll.hide()
         self.treealt.show()
         self.tree_pb.set_fraction(0.0)
         if self.tree_idle is not None:
            gobject.source_remove(self.tree_idle)
         tree_populate = TreePopulate(self, c, total, time.time())
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
                  c.execute("""SELECT id,artist,album,tracknumber,title,length,bitrate,filename,path FROM tracks WHERE MATCH (artist,album,title,filename) AGAINST (%s)""", (fuzzy, ))
                  break
               except dberror.OperationalError, inst:
                  if "FULLTEXT" in str(inst):
                     print "adding fulltext index to database"
                     c.execute("""ALTER TABLE tracks ADD FULLTEXT(artist,album,title,filename)""")
                  else:
                     raise
         else:
            if where:
               where = "WHERE %s " % where
            c.execute("""SELECT id,artist,album,tracknumber,title,length,bitrate,filename,path FROM tracks %sORDER BY artist,album,path,tracknumber,title""" % where)
      except dberror.MySQLError, inst:
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
            found += 1
            self.flatstore.append([found] + list(row))
         else:
            break
      self.flatcols[0].set_title("(%s)" % found)
      self.flatview.set_model(self.flatstore)
      c.close()

   def getcolwidths(self, cols):
      return ",".join([ str(x.get_width() or x.get_fixed_width()) for x in cols ])
   
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
      
      self.tree_expand = gtk.Button(ln.dbexpand, None, True)
      image = gtk.image_new_from_stock(gtk.STOCK_ADD, gtk.ICON_SIZE_BUTTON)
      self.tree_expand.set_image(image)
      buttonbox.add(self.tree_expand)
      self.tree_expand.show()
      
      self.tree_collapse = gtk.Button(ln.dbcollapse, None, True)
      image = gtk.image_new_from_stock(gtk.STOCK_REMOVE, gtk.ICON_SIZE_BUTTON)
      self.tree_collapse.set_image(image)
      buttonbox.add(self.tree_collapse)
      self.tree_collapse.show()
      
      buttonbox.show()
      
      self.treeview, self.treescroll, self.treealt = makeview(self.notebook, ln.media_tree, buttonbox)
      self.treeview.set_enable_tree_lines(True)
      self.treeview.set_rubber_banding(True)
      treeselection = self.treeview.get_selection()
      treeselection.set_mode(gtk.SELECTION_MULTIPLE)
      treeselection.set_select_function(self.tree_select_func)
      self.tree_expand.connect_object("clicked", gtk.TreeView.expand_all, self.treeview)
      self.tree_collapse.connect_object("clicked", gtk.TreeView.collapse_all, self.treeview)
      # id, ARTIST-ALBUM-TITLE, TRACK, DURATION, BITRATE, filename, path
      self.treestore = gtk.TreeStore(int, str, int, int, int, str, str)
      self.treeview.set_model(self.treestore)
      self.treecols = makecolumns(self.treeview, (
            ("%s - %s - %s" % (ln.dbartist, ln.dbalbum, ln.dbtitle), 1, self.cell_show_unknown, 180),
            (ln.dbtrack, 2, self.cell_ralign, -1),
            (ln.dbduration, 3, self.cond_cell_secs_to_h_m_s, -1),
            (ln.dbbitrate, 4, self.cell_ralign, -1),
            (ln.dbfilename, 5, None, 100),
            (ln.dbpath, 6, None, -1),
            ))
      
      self.treeview.enable_model_drag_source(gtk.gdk.BUTTON1_MASK, self.sourcetargets, gtk.gdk.ACTION_DEFAULT | gtk.gdk.ACTION_COPY)
      self.treeview.connect_after("drag-begin", self.cb_drag_begin)
      self.treeview.connect("drag_data_get", self.cb_tree_drag_data_get)
      
      vbox = gtk.VBox()
      vbox.set_border_width(20)
      vbox.set_spacing(20)
      label = gtk.Label(ln.populating)
      vbox.pack_start(label, False, False, 0)
      self.tree_pb = gtk.ProgressBar()
      vbox.pack_start(self.tree_pb, False, False, 0)
      self.treealt.add(vbox)
      vbox.show_all()
      
      self.tree_idle = None
      
      # flat gui
      filterframe = gtk.Frame(ln.dbfilters)
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
      fuzzylabel = gtk.Label(ln.dbfuzzysearch)
      fuzzyhbox.pack_start(fuzzylabel, False, False, 0)
      fuzzylabel.show()
      self.fuzzyentry = gtk.Entry()
      self.fuzzyentry.connect("changed", self.fuzzysearch_changed)
      fuzzyhbox.pack_start(self.fuzzyentry, True, True, 0)
      self.fuzzyentry.show()
      
      wherehbox = gtk.HBox()
      filtervbox.pack_start(wherehbox, False, False, 0)
      wherehbox.show()
      wherelabel = gtk.Label(ln.dbwhere)
      wherehbox.pack_start(wherelabel, False, False, 0)
      wherelabel.show()
      self.whereentry = gtk.Entry()
      self.whereentry.connect("activate", self.cb_update)
      wherehbox.pack_start(self.whereentry, True, True, 0)
      self.whereentry.show()
      image = gtk.image_new_from_stock(gtk.STOCK_EXECUTE, gtk.ICON_SIZE_BUTTON)
      self.update = gtk.Button()
      self.update.connect("clicked", self.cb_update)
      self.update.set_image(image)
      image.show
      wherehbox.pack_start(self.update, False, False, 0)
      self.update.show()
      
      self.flatview, self.flatscroll, self.flatalt = makeview(self.notebook, ln.media_flat, filterframe)
      self.flatview.set_rules_hint(True)
      self.flatview.set_rubber_banding(True)
      treeselection = self.flatview.get_selection()
      treeselection.set_mode(gtk.SELECTION_MULTIPLE)
      # found, id, ARTIST, ALBUM, TRACKNUM, TITLE, DURATION, BITRATE, path, filename
      self.flatstore = gtk.ListStore(int, int, str, str, int, str, int, int, str, str)
      self.flatview.set_model(self.flatstore)
      self.flatcols = makecolumns(self.flatview, (
            ("(%d)" % 0, 0, self.cell_ralign, -1),
            (ln.dbartist, 2, self.cell_show_unknown, 100),
            (ln.dbalbum, 3, self.cell_show_unknown, 100),
            (ln.dbtrack, 4, self.cell_ralign, -1),
            (ln.dbtitle, 5, self.cell_show_unknown, 100),
            (ln.dbduration, 6, self.cell_secs_to_h_m_s, -1),
            (ln.dbbitrate, 7, self.cell_ralign, -1),
            (ln.dbfilename, 8, None, 100),
            (ln.dbpath, 9, None, -1),
            ))
         
      self.flatview.enable_model_drag_source(gtk.gdk.BUTTON1_MASK, self.sourcetargets, gtk.gdk.ACTION_DEFAULT | gtk.gdk.ACTION_COPY)
      self.flatview.connect_after("drag-begin", self.cb_drag_begin)
      self.flatview.connect("drag_data_get", self.cb_flat_drag_data_get)

class Prefs(gtk.Frame):
   """ Controls and settings for Prokyon3 database connectivity """
   
   def set_ui_state(self, state):
      sens = not state
      self.prokuser.set_sensitive(sens)
      self.prokdatabase.set_sensitive(sens)
      self.prokpassword.set_sensitive(sens)
      self.prok_led_image.set_from_pixbuf((self.prok_ledclear, self.prok_ledgreen)[state])
      if state:
         self.main.topleftpane.activate(self.db, ln.media_viewer_title % self.prokdatabase.get_text())
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
            raise dberror.ProgrammingError, "database format not supported due to missing reference to one or more of:\n   %s,\n   for command: %s" % (str(checkitems), command)

      if sql is not None:
         if widget.get_active():
            try:
               self.db = sql.connect(user=self.prokuser.get_text(), passwd=self.prokpassword.get_text(), db=self.prokdatabase.get_text())
               c = self.db.cursor()
               # check this database looks familiar enough to use
               dbtest(c, "SHOW tables", ("tracks", ))
               dbtest(c, "DESCRIBE tracks", ("artist", "title", "album", "tracknumber", "bitrate", "path", "filename"))
               c.close()
            except dberror.MySQLError, inst:
               print inst
               try:
                  c.close()
               except:
                  pass
               widget.set_active(False)
            else:
               self.set_ui_state(True)
               print "connected to database"
         else:
            try:
               self.db.close()
            except (AttributeError, NameError, dberror.MySQLError):
               pass
            else:
               self.set_ui_state(False)
               print "database connection removed"

   @staticmethod
   def rjustlabel(text):
      box = gtk.HBox()
      label = gtk.Label(text)
      box.pack_end(label, False, False, 0)
      label.show()
      return box

   class ProkEntry(gtk.Entry):
      def __init__(self, maxlength=0):
         gtk.Entry.__init__(self, maxlength)
         self.set_size_request(30, -1)
         self.set_text("prokyon")

   def __init__(self, parent):
      gtk.Frame.__init__(self)
      self.main = parent
      label = gtk.Label(ln.prokyon3_frame_text)
      self.prok_led_image = gtk.Image()
      hbox = gtk.HBox()
      hbox.pack_start(label, False, False, 4)
      if sql:
         hbox.pack_start(self.prok_led_image, False, False, 4)
      hbox.show_all()
      self.prok_ledgreen = gtk.gdk.pixbuf_new_from_file_at_size(pkgdatadir + "led_lit_green_black_border_64x64" + gfext, 10, 10)
      self.prok_ledclear = gtk.gdk.pixbuf_new_from_file_at_size(pkgdatadir + "led_unlit_clear_border_64x64" + gfext, 10, 10)
      self.prok_led_image.set_from_pixbuf(self.prok_ledclear)
      self.set_label_widget(hbox)
      self.set_border_width(3)
      table = gtk.Table(2, 4)
      table.set_border_width(10)
      if sql:
         self.add(table)
      else:
         vbox = gtk.VBox()
         vbox.set_border_width(3)
         label = gtk.Label(ln.prokyon3_nosql)
         vbox.add(label)
         label.show()
         self.add(vbox)
         vbox.show()
      table.show()
      table.set_row_spacing(0, 1)
      table.set_col_spacing(0, 2)
      table.set_col_spacing(1, 10)
      table.set_col_spacing(2, 2)
      userlabel = self.rjustlabel(ln.prokyon3_user)
      table.attach(userlabel, 0, 1, 0, 1, gtk.SHRINK | gtk.FILL)
      userlabel.show()
      self.prokuser = self.ProkEntry()
      table.attach(self.prokuser, 1, 2, 0, 1)
      self.prokuser.show()
      databaselabel = self.rjustlabel(ln.prokyon3_database)
      table.attach(databaselabel, 2, 3, 0, 1, gtk.SHRINK | gtk.FILL)
      databaselabel.show()
      self.prokdatabase = self.ProkEntry()
      table.attach(self.prokdatabase, 3, 4, 0, 1)
      self.prokdatabase.show()
      passwordlabel = self.rjustlabel(ln.prokyon3_password)
      table.attach(passwordlabel, 0, 1, 1, 2, gtk.SHRINK | gtk.FILL)
      passwordlabel.show()
      self.prokpassword = self.ProkEntry()
      self.prokpassword.set_visibility(False)
      table.attach(self.prokpassword, 1, 2, 1, 2)
      self.prokpassword.show()
      self.proktoggle = gtk.ToggleButton(ln.prokyon3_connect)
      self.proktoggle.set_size_request(10, -1)
      self.proktoggle.connect("toggled", self.cb_proktoggle)
      table.attach(self.proktoggle, 2, 4, 1, 2)
      self.proktoggle.show()
