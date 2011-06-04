"""The profile management dialog."""

#   Copyright (C) 2011 Stephen Fairchild (s-fairchild@users.sourceforge.net)
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


__all__ = ["ProfileDialog"]


import atexit

# This is and needs to remain the initial gtk import point.
import gobject
import gtk
import pango

from idjc import PGlobs, FGlobs
from ..utils import Singleton

gtk.gdk.threads_init()
gtk.gdk.threads_enter()
atexit.register(gtk.gdk.threads_leave)

from ..gtkstuff import ConfirmationDialog
from ..gtkstuff import ErrorMessageDialog
from ..gtkstuff import CellRendererLED
from ..gtkstuff import threadslock



class IconChooserButton(gtk.Button):
   """Imitate a FileChooserButton but specific to image types.
   
   The image rather than the mime-type icon is shown on the button.
   """
   
   def __init__(self, dialog):
      gtk.Button.__init__(self)
      filefilter = gtk.FileFilter()
      filefilter.set_name("Supported Image Formats")
      filefilter.add_pixbuf_formats()
      dialog.add_filter(filefilter)
      dialog.set_icon_from_file(PGlobs.default_icon)

      hbox = gtk.HBox()
      hbox.set_spacing(4)
      image = gtk.Image()
      hbox.pack_start(image, False, padding=1)
      label = gtk.Label()
      label.set_alignment(0, 0.5)
      label.set_ellipsize(pango.ELLIPSIZE_END)
      hbox.pack_start(label)
      
      vsep = gtk.VSeparator()
      hbox.pack_start(vsep, False)
      rightmost_icon = gtk.image_new_from_stock(gtk.STOCK_OPEN,
                                             gtk.ICON_SIZE_MENU)
      hbox.pack_start(rightmost_icon, False)
      self.add(hbox)
      hbox.show_all()

      self.connect("clicked", self._cb_clicked, dialog)
      self._dialog = dialog
      self._image = image
      self._label = label
      self.set_filename(dialog.get_filename())


   def set_filename(self, f):
      try:
         disp = glib.filename_display_name(f)
         pb = gtk.gdk.pixbuf_new_from_file_at_size(f, 16, 16)
      except (glib.GError, TypeError):
         self._label.set_text("(None)")
         self._image.clear()
         self._filename = None
      else:
         self._label.set_text(disp)
         self._image.set_from_pixbuf(pb)
         self._filename = f
         self._dialog.set_filename(f)
      
      
   def get_filename(self):
      return self._filename


   def _cb_clicked(self, button, dialog):
      response = dialog.run()
      if response == gtk.RESPONSE_OK:
         self.set_filename(dialog.get_filename())
      dialog.hide()


   def __getattr__(self, attr):
      if attr in gtk.FileChooser.__dict__:
         return getattr(self._dialog, attr)
      raise AttributeError("%s has no attribute, %s" % (
                                 self, attr))
      

class IconPreviewFileChooserDialog(gtk.FileChooserDialog):
   def __init__(self, *args, **kwds):
      gtk.FileChooserDialog.__init__(self, *args, **kwds)
      vbox = gtk.VBox()
      frame = gtk.Frame()
      vbox.pack_start(frame, expand=True, fill=False)
      frame.show()
      image = gtk.Image()
      frame.add(image)
      self.set_use_preview_label(False)
      self.set_preview_widget(vbox)
      self.set_preview_widget_active(False)
      self.connect("update-preview", self._cb_update_preview, image)
      vbox.show_all()
      
      
   def _cb_update_preview(self, dialog, image):
      f = self.get_preview_filename()
      try:
         pb = gtk.gdk.pixbuf_new_from_file_at_size(f, 16, 16)
      except (glib.GError, TypeError):
         active = False
      else:
         active = True
         image.set_from_pixbuf(pb)
      self.set_preview_widget_active(active)



class ProfileEntry(gtk.Entry):
   _allowed = (65056, 65361, 65363, 65365, 65288, 65289, 65535)
   
   def __init__(self):
      gtk.Entry.__init__(self)
      self.set_max_length(MAX_PROFILE_LENGTH)
      self.connect("key-press-event", self._cb_kp)
      self.connect("button-press-event", self._cb_button)
   
   
   def _cb_kp(self, widget, event):
      if not event.keyval in self._allowed and not \
                           profile_name_valid(event.string):
         return True
         
         
   def _cb_button(self, widget, event):
      if event.button != 1:
         return True



class NewProfileDialog(gtk.Dialog):
   _icon_dialog = IconPreviewFileChooserDialog("Choose An Icon",
                  buttons = (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                             gtk.STOCK_OK, gtk.RESPONSE_OK))
   
   
   def __init__(self, row, filter_function=None):
      gtk.Dialog.__init__(self)
      self.set_modal(True)
      self.set_destroy_with_parent(True)
      self.set_size_request(330, -1)
      
      if row is not None:
         self.set_title("New profile based upon %s" % row[1])
      else:
         self.set_title("New profile details")

      vbox = gtk.VBox()
      vbox.set_border_width(5)
      vbox.set_spacing(5)

      labels = (gtk.Label(x) for x in ("Profile name:",
                        "Icon:", "Nickname:", "Description:"))
      names = ("profile_entry", "icon_button", "nickname_entry",
                                          "description_entry")
      widgets = (ProfileEntry(), IconChooserButton(self._icon_dialog),
                 gtk.Entry(), gtk.Entry())
      for label, name, widget in zip(labels, names, widgets):
         item_vbox = gtk.VBox()
         item_vbox.add(label)
         label.set_alignment(0, 0.5)
         item_vbox.add(widget)
         setattr(self, name, widget)
         vbox.add(item_vbox)
                                          
      self._icon_dialog.set_transient_for(self)

      if row is not None:
         self.icon_button.set_filename(row[4])
         self.nickname_entry.set_text(row[5])
         self.description_entry.set_text(row[2])
      else:
         self.icon_button.set_filename(None)
         
      self.get_content_area().add(vbox)
         
      box = gtk.HButtonBox()
      cancel = gtk.Button(stock=gtk.STOCK_CANCEL)
      cancel.connect("clicked", lambda w: self.destroy())
      box.add(cancel)
      self.ok = gtk.Button(stock=gtk.STOCK_OK)
      box.add(self.ok)
      self.get_action_area().add(box)



class ProfileSingleton(Singleton, type(gtk.Dialog)):
   def __call__(cls, *args, **kwds):
      return super(ProfileSingleton, cls).__call__(*args, **kwds)
   
   

class ProfileDialog(gtk.Dialog):
   __metaclass__ = ProfileSingleton
   
   
   __gproperties__ = {  "selection-active" : (gobject.TYPE_BOOLEAN, 
                        "selection active", 
                        "selected profile is active",
                        0, gobject.PARAM_READABLE),}

   _signal_names = "delete", "choose"
   _new_profile_dialog_signal_names = "new", "clone"

   __gsignals__ = { "selection-active-changed" : (
                        gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE,
                        (gobject.TYPE_BOOLEAN,)) }
   __gsignals__.update(dict(
         (x, (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE,
         (gobject.TYPE_STRING,))) for x in (_signal_names)))
   __gsignals__.update(dict(
         (x, (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE,
         (gobject.TYPE_STRING,) * 5)) for x in (_new_profile_dialog_signal_names)))


   def __init__(self, default, data_function=None):
      self._default = default
      self._profile = self._highlighted = None
      self._selection_active = False
      self._olddata = ()

      gtk.Dialog.__init__(self, "Profile Manager")
      self.set_icon_from_file(PGlobs.default_icon)
      self.set_size_request(500, 300)
      w = gtk.ScrolledWindow()
      w.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
      self.get_content_area().add(w)
      self.store = gtk.ListStore(gtk.gdk.Pixbuf, str, str, int, str, str)
      self.sorted = gtk.TreeModelSort(self.store)
      self.sorted.set_sort_func(1, self._sort_func)
      self.sorted.set_sort_column_id(1, gtk.SORT_ASCENDING)
      self.treeview = gtk.TreeView(self.sorted)
      self.treeview.set_headers_visible(True)
      self.treeview.set_rules_hint(True)
      w.add(self.treeview)
      pbrend = gtk.CellRendererPixbuf()
      strrend = gtk.CellRendererText()
      ledrend = CellRendererLED()
      c1 = gtk.TreeViewColumn("Profile")
      c1.pack_start(pbrend, expand=False)
      c1.pack_start(strrend)
      c1.add_attribute(pbrend, "pixbuf", 0)
      c1.add_attribute(strrend, "text", 1)
      c1.set_spacing(3)
      self.treeview.append_column(c1)
      c2 = gtk.TreeViewColumn("Nickname")
      c2.pack_start(strrend)
      c2.add_attribute(strrend, "text", 5)
      self.treeview.append_column(c2)
      c3 = gtk.TreeViewColumn("Description")
      c3.pack_start(strrend)
      c3.add_attribute(strrend, "text", 2)
      c3.set_expand(True)
      self.treeview.append_column(c3)
      c4 = gtk.TreeViewColumn()
      c4.pack_start(ledrend)
      c4.add_attribute(ledrend, "active", 3)
      self.treeview.append_column(c4)
      self.selection = self.treeview.get_selection()
      self.selection.connect("changed", self._cb_selection)
      box = gtk.HButtonBox()
      box.set_layout(gtk.BUTTONBOX_START)
      self.get_action_area().add(box)
      self.new = gtk.Button(stock=gtk.STOCK_NEW)
      box.pack_start(self.new)
      self.clone = gtk.Button(stock=gtk.STOCK_COPY)
      box.pack_start(self.clone)
      self.delete = gtk.Button(stock=gtk.STOCK_DELETE)
      box.pack_start(self.delete)
      self.cancel = gtk.Button(stock=gtk.STOCK_QUIT)
      self.cancel.connect("clicked", self._cb_cancel)
      box.pack_start(self.cancel)
      box.set_child_secondary(self.cancel, True)
      self.choose = gtk.Button(stock=gtk.STOCK_OPEN)
      box.pack_start(self.choose)
      box.set_child_secondary(self.choose, True)
      self.set_data_function(data_function)
      self.connect("notify::visible", self._cb_visible)
      for each in self._signal_names:
         getattr(self, each).connect("clicked", self._cb_click, each)
      for each in self._new_profile_dialog_signal_names:
         getattr(self, each).connect("clicked", self._cb_new_profile_dialog, each)
    
   
   def display_error(self, title, message, transient_parent=None):
      error_dialog = ErrorMessageDialog(title, message)
      error_dialog.set_transient_for(transient_parent or self)
      error_dialog.set_icon_from_file(PGlobs.default_icon)
      error_dialog.show_all()

   
   def destroy_new_profile_dialog(self):
      self._new_profile_dialog.destroy()
      del self._new_profile_dialog


   def get_new_profile_dialog(self):
      return self._new_profile_dialog
   
   
   def do_get_property(self, prop):
      if prop.name == "selection-active":
         return self._selection_active
      else:
         raise AttributeError("unknown property: %s" % prop.name)
   

   def do_selection_active_changed(self, state):
      state = not state
      self.choose.set_sensitive(state and self._profile is None)
      self.delete.set_sensitive(state)
      self.clone.set_sensitive(state)

   
   def _cb_click(self, widget, signal):
      if self._highlighted is not None:
         def commands():
            self.emit(signal, self._highlighted)
            self._update_data()

         if signal == "delete":
            message = "Delete profile: %s?" % self._highlighted
            if self._highlighted == self._default:
               message += "\n\nThis profile is protected and will" \
               " be recreated with initial settings."
            conf = ConfirmationDialog("Confirmation", message)
            conf.set_transient_for(self)
            conf.ok.connect("clicked", lambda w: commands())
            conf.show_all()
         else:
            commands()

   
   def _cb_new_profile_dialog(self, widget, action):
      if action == "clone":
         if self._highlighted is None:
            return
         row = self._get_row_for_profile(self._highlighted)
         template = row[1]
      else:
         row = None
         template = None
         
      np_dialog = self._new_profile_dialog = NewProfileDialog(row)
      
      def sub_ok(widget):
         profile = np_dialog.profile_entry.get_text()
         icon = np_dialog.icon_button.get_filename()
         description = np_dialog.description_entry.get_text().strip()
         nickname = np_dialog.nickname_entry.get_text().strip()
         self.emit(action, profile, template, icon, nickname, description)
         self._update_data()
         
      np_dialog.set_transient_for(self)
      np_dialog.ok.connect("clicked", sub_ok)
      np_dialog.show_all()


   def _cb_cancel(self, widget):
      if self._profile is None:
         self.response(0)
      else:
         self.hide()


   def _cb_delete_event(self, widget, event):
      self.hide()
      return True

   
   def _cb_visible(self, *args):
      if self.props.visible:
         gobject.timeout_add(200, self._protected_update_data)
      
      
   def _cb_selection(self, ts):
      model, iter = ts.get_selected()
      if iter is not None:
         self._highlighted = model.get_value(iter, 1)
         active = model.get_value(iter, 3)
      else:
         self._highlighted = None
         active = True
      if active != self._selection_active:
         self._selection_active = active
         self.emit("selection-active-changed", active)
            
      
   def _highlight_profile(self, target):
      i = self._get_index_for_profile(target)
      if i is not None:
         self.selection.select_path(i)
         self.selection.get_tree_view().scroll_to_cell(i)


   def _get_index_for_profile(self, target):
      for i, data in enumerate(self.sorted):
         if data[1] == target:
            return i
      return None


   def _get_row_for_profile(self, target):
      return list(self.sorted[self._get_index_for_profile(target)])


   def _sort_func(self, model, *iters):
      vals = tuple(model.get_value(x, 1) for x in iters)
      
      try:
         return vals.index(self._default)
      except ValueError:
         return cmp(*vals)
      

   def set_data_function(self, f):
      self._data_function = f
      self._update_data()
      if f is not None:
         self._highlight_profile(self._default)
         
         
   def _update_data(self):
      if self._data_function is not None:
         data = tuple(self._data_function())
         if self._olddata != data:
            self._olddata = data

            h = self._highlighted
            self.store.clear()
            for d in data:
               if d["icon"] is not None:
                  i = d["icon"]
               else:
                  if d["profile"] == self._default:
                     i = PGlobs.default_icon
                  else:
                     i = None
               if i is not None:
                  try:
                     pb = gtk.gdk.pixbuf_new_from_file_at_size(i, 16, 16)
                  except glib.GError:
                     pb = i = None
               else:
                  pb = None
               desc = d["description"] or ""
               active = d["active"]
               nick = d["nickname"] or ""
               self.store.append((pb, d["profile"], desc, active, i or "", nick))
            self._highlight_profile(h)
      return self.props.visible
      
      
   _protected_update_data = threadslock(_update_data)
      
      
   @property
   def profile(self):
      return self._profile
      
      
   def set_profile(self, newprofile, newnickname):
      assert self._profile is None
      self._profile = newprofile
      self.set_title(self.get_title() + "  (%s)" % newnickname)
      self.cancel.set_label(gtk.STOCK_CLOSE)
      self.connect("delete-event", self._cb_delete_event)
      self.response(0)
      
      
   def run(self):
      if self._profile is None:
         self.show_all()
         gtk.Dialog.run(self)
      else:
         self.show()
