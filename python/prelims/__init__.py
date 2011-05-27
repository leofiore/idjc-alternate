"""Preliminary initialisation stuff."""

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


__all__ = ["ArgumentParser", "ProfileSelector"]


import os
import sys
import argparse
import shutil
import tempfile
from functools import partial

import dbus
import dbus.service
import glib

from idjc import FGlobs
from idjc import PGlobs
from ..utils import Singleton



class ArgumentParserError(Exception):
   pass



class ArgumentParser(argparse.ArgumentParser):
   def error(self, text):
      raise ArgumentParserError(text)

      
   def exit_with_message(self, text):
      """This is just error on the superclass."""
      
      super(ArgumentParser, self).error(text)



class ArgumentParserImplementation(object):
   """To parse the command line arguments, if any."""

   __metaclass__ = Singleton


   def __init__(self, args=None, description=None, epilog=None):
      if args is None:
         args = sys.argv[1:]

      self._args = list(args)

      if description is None:
         description = PGlobs.app_longform

      ap = self._ap = ArgumentParser(description=description, epilog=epilog)
      ap.add_argument("-v", "--version", action='version', version=
                     FGlobs.package_name + " " + FGlobs.package_version)
      sp = self._sp = ap.add_subparsers(
                     help="sub-option -h for more info")
      sp_run = sp.add_parser("run", help="the default command",
         description=description + " -- sub-command: run", epilog=epilog)
      sp_mp = sp.add_parser("generateprofile", help="make a new profile",
         description=description + " -- sub-command: generateprofile", epilog=epilog)

      sp_run.add_argument("-d", "--dialog", dest="dialog", nargs=1, 
            choices=("true", "false"), 
            help="""force the appearance or non-appearance of the
            profile chooser dialog -- when used with the -p option
            the chosen profile is preselected""")
      sp_run.add_argument("-p", "--profile", dest="profile", nargs=1, metavar="profile_choice", 
            help="""the profile to use -- overrides the user interface
            preferences "show profile dialog" option""")
      sp_run.add_argument("-j", "--jackserver", dest="jackserver", nargs=1,
            metavar="server_name", help="the named jack sound-server to connect with")
      group = sp_run.add_argument_group("user interface settings")
      group.add_argument("-m", "--mics", dest="mics", nargs="+", metavar="m",
            help="microphones open at startup")
      group.add_argument("-a", "--aux", dest="aux", nargs="+", metavar="a",
            help="aux ports open at startup")
      group.add_argument("-V", "--voip", dest="voip", nargs=1, choices=
            ("off", "private", "public"),
            help="the voip mode at startup")
      group.add_argument("-P", "--players", dest="players", nargs="+", metavar="p",
            help="the players to start among values {1,2}")
      group.add_argument("-s", "--servers", dest="servers", nargs="+", metavar="s",
            help="attempt connection with the specified servers")
      group.add_argument("-r", "--recorders", dest="recorders", nargs="+", metavar="r",
            help="the recorders to start")
      group.add_argument("-c", "--crossfader", dest="crossfader", choices=("1", "2"), 
            help="position the crossfader for the specified player")
      sp_mp.add_argument("newprofile", metavar="profile_name", help="new profile name")
      sp_mp.add_argument("-t", "--template", dest="template", metavar="template_profile",
            help="an existing profile to use as a template")
      sp_mp.add_argument("-i", "--icon", dest="icon", metavar="icon_pathname",
            help="pathname to an icon -- defaults to idjc logo")
      sp_mp.add_argument("-d", "--description", dest="description", metavar="description_text",
            help="description of the profile")


   def parse_args(self):
      try:
         return self._ap.parse_args(self._args)
      except ArgumentParserError as e:
         try:
            for cmd in self._sp.choices.iterkeys():
               if cmd in self._args:
                  raise
            return self._ap.parse_args(self._args + ["run"])
         except ArgumentParserError:
            self._ap.exit_with_message(str(e))


   def error(self, text):
      self._ap.exit_with_message(text)
      
      
   def exit(self, status=0, message=None):
      self._ap.exit(status, message)
     


class ProfileSelector(object):
   """The profile gives each application instance a unique identity.
   
   This identity extends to the config file directory if present, 
   to the JACK application ID, to the DBus bus name.
   """
   
   __metaclass__ = Singleton
   

   _profile = _dbus_bus_name = _profile_dialog = None
   

   class ProfileError(Exception):
      pass


   def __init__(self):
      ap = ArgumentParserImplementation()
      args = ap.parse_args()

      if PGlobs.profile_dir is not None:
         try:
            if not os.path.isdir(os.path.join(PGlobs.profile_dir, "default")):
               self._generate_profile("default", description="The default profile")

            if "newprofile" in args:
               self._generate_profile(**vars(args))
               ap.exit(0)
         except self.ProfileError as e:
            ap.error("failed to create profile: " + str(e))

         self._obtain_profile(ap, args)
         if self.profile is None:
            ap.error("no profile set")

         assert all((self.dbus_bus_name, self.profile_dialog))


   @property
   def profile(self):
      return self._profile


   @property
   def profile_dialog(self):
      return self._profile_dialog
      
      
   @property
   def dbus_bus_name(self):
      return self._dbus_bus_name


   def _obtain_profile(self, ap, args):
      profile = "default"
      dialog_selects = not os.path.exists(PGlobs.profile_dialog_refusal_pathname)
      if args.profile is not None:
         profile = args.profile[0]
         dialog_selects = False
         if not self._profile_name_valid(profile):
            ap.error("specified profile name is not valid")

      if args.dialog is not None:
         dialog_selects = args.dialog[0] == "true"
      
      self._profile_dialog = self._get_profile_dialog(dialog_selects, profile)
      self._profile_dialog.connect("delete", self._cb_delete_profile)
      self._profile_dialog.connect("choose", self._choose_profile)
      if dialog_selects:
         self._profile_dialog.run()
         self._profile_dialog.hide()
      else:
         self._choose_profile(self._profile_dialog, profile, verbose=True)
      
      
   def _cb_delete_profile(self, dialog, profile):
      if profile is not dialog.profile:
         try:
            busname = self._grab_bus_name_for_profile(profile)
            shutil.rmtree(os.path.join(PGlobs.profile_dir, profile))
         except dbus.DBusException:
            pass
      
   
   def _choose_profile(self, dialog, profile, verbose=False):
      if dialog._profile is None:
         try:
            busname = self._grab_bus_name_for_profile(profile)
         except dbus.DBusException:
            if verbose:
               print "profile '%s' is in use" % profile
         else:
            dialog.set_profile(profile)
            self._dbus_bus_name = busname
            self._profile = profile


   def _generate_profile(self, newprofile, template=None, **kwds):
      if PGlobs.profile_dir is not None:
         if not self._profile_name_valid(newprofile):
            raise self.ProfileError("new profile is not valid")
           
         if self._profile_has_owner(newprofile):
            raise self.ProfileError("profile is currently running")
            
         try:
            tmp = tempfile.mkdtemp()
         except EnvironmentError:
            raise self.ProfileError("temporary directory creation failed")
            
         try:
            if template is not None:
               if not self._profile_name_valid(template):
                  raise self.ProfileError("specified template not valid (%s)" % template)
               
               tdir = os.path.join(PGlobs.profile_dir, template)
               if os.path.isdir(tdir):
                  for x in ("icon", "description", "config"):
                     try:
                        shutil.copyfile(os.path.join(tdir, x),
                                        os.path.join(tmp, x))
                     except EnvironmentError:
                        pass
               else:
                  raise self.ProfileError("template profile (%s) does not exist" % template)
                  
            for fname in ("icon", "description"):
               if kwds.get(fname):
                  try:
                     with open(os.path.join(tmp, fname), "w") as f:
                        f.write(kwds[fname])
                  except EnvironmentError:
                     raise self.ProfileError("could not write " + fname)
            
            try:
               dest = os.path.join(PGlobs.profile_dir, newprofile)
               shutil.copytree(tmp, dest)
            except EnvironmentError as e:
               if e.errno == 17 and os.path.isdir(dest):
                  msg = "profile directory exists"
               else:
                  msg = "could not create profile directory: path exists"
               raise self.ProfileError(msg)
         finally:
            # Failure to clean up is not a critical error.
            try:
               shutil.rmtree(tmp)
            except EnvironmentError:
               pass


   @staticmethod
   def _profile_name_valid(p):
      try:
         dbus.validate_bus_name("com." + p)
         dbus.validate_object_path("/" + p)
      except (TypeError, ValueError):
         return False
      return True


   def _profile_data(self, want=("icon", "description")):
      d = PGlobs.profile_dir
      try:
         profdirs = os.walk(d).next()[1]
      except EnvironmentError:
         return
      for profname in profdirs:
         if self._profile_name_valid(profname):
            files = os.walk(os.path.join(d, profname)).next()[2]
            rslt = {"profile": profname}
            for each in want:
               try:
                  with open(os.path.join(d, profname, each)) as f:
                     rslt[each] = f.read()
               except EnvironmentError:
                  rslt[each] = None
               
            rslt["active"] = self._profile_has_owner(profname)
            yield rslt


   def closure(cmd, name):
      busbase = PGlobs.dbus_bus_basename
      def inner(profname):
         return cmd(".".join((busbase, profname)))
      inner.__name__ = name
      return staticmethod(inner)

   _profile_has_owner = closure(dbus.SessionBus().name_has_owner,
                     "_profile_has_owner")
      
   _grab_bus_name_for_profile = closure(partial(dbus.service.BusName, do_not_queue=True),
                     "_grab_bus_name_for_profile")
                     
   del closure


   def _get_profile_dialog(self, can_select, highlight="default"):
      import gobject
      import gtk


      class CellRendererGreenLED(gtk.CellRendererPixbuf):
         __gproperties__ = {
               "active" : (gobject.TYPE_INT,
                           "active", "active",
                           0, 1, 0, gobject.PARAM_READWRITE),}

                           
         def __init__(self):
            gtk.CellRendererPixbuf.__init__(self)
            self._led = [gtk.gdk.pixbuf_new_from_file_at_size(
                         os.path.join(FGlobs.pkgdatadir, x + ".png"), 10, 10)
                         for x in ("led_unlit_clear_border_64x64",
                                   "led_lit_green_black_border_64x64")]
            self._active = 0

                     
         def do_get_property(self, prop):
            if prop.name == "active":
               return self._active
            else:
               raise AttributeError("unknown property %s" % prop.name)

               
         def do_set_property(self, prop, value):
            if prop.name == "active":
               self._active = value
               gtk.CellRendererPixbuf.set_property(self, "pixbuf", 
                                                      self._led[value])
            else:
               raise AttributeError("unknown property %s" % prop.name)
      
      
      class Dialog(gtk.Dialog):
         __gproperties__ = {  "selection-active" : (gobject.TYPE_BOOLEAN, 
                              "selection active", 
                              "selected profile is active",
                              0, gobject.PARAM_READABLE),}

         signal_names = "clone", "delete", "choose"

         __gsignals__ = { "selection-active-changed" : (
                              gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE,
                              (gobject.TYPE_BOOLEAN,)) }
         __gsignals__.update(dict(
                  (x, (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE,
                  (gobject.TYPE_STRING,))) for x in signal_names))


         def __init__(self, data_function=None):
            self._profile = self._highlighted = None
            self._selection_active = False
            self._olddata = ()

            gtk.Dialog.__init__(self, "Profile Manager")
            self.set_icon_from_file(PGlobs.default_icon)
            self.set_size_request(400, 200)
            w = gtk.ScrolledWindow()
            w.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
            self.get_content_area().add(w)
            self.store = gtk.ListStore(gtk.gdk.Pixbuf, str, str, int)
            self.sorted = gtk.TreeModelSort(self.store)
            self.sorted.set_sort_func(1, self._sort_func)
            self.sorted.set_sort_column_id(1, gtk.SORT_ASCENDING)
            self.treeview = gtk.TreeView(self.sorted)
            self.treeview.set_headers_visible(True)
            w.add(self.treeview)
            pbrend = gtk.CellRendererPixbuf()
            strrend = gtk.CellRendererText()
            ledrend = CellRendererGreenLED()
            c1 = gtk.TreeViewColumn("Profile")
            c1.pack_start(pbrend, expand=False)
            c1.pack_start(strrend)
            c1.add_attribute(pbrend, "pixbuf", 0)
            c1.add_attribute(strrend, "text", 1)
            self.treeview.append_column(c1)
            c2 = gtk.TreeViewColumn("Description")
            c2.pack_start(strrend)
            c2.add_attribute(strrend, "text", 2)
            c2.set_expand(True)
            self.treeview.append_column(c2)
            c3 = gtk.TreeViewColumn()
            c3.pack_start(ledrend)
            c3.add_attribute(ledrend, "active", 3)
            self.treeview.append_column(c3)
            self.selection = self.treeview.get_selection()
            self.selection.connect("changed", self._cb_selection)
            box = gtk.HButtonBox()
            self.get_action_area().add(box)
            self.new = gtk.Button("New")
            box.pack_start(self.new)
            self.clone = gtk.Button("Clone")
            box.pack_start(self.clone)
            self.delete = gtk.Button("Delete")
            box.pack_start(self.delete)
            self.choose = gtk.Button("Choose")
            box.pack_start(self.choose)
            self.set_data_function(data_function)
            self.connect("notify::visible", self._cb_visible)
            for each in self.signal_names:
               getattr(self, each).connect("clicked", self._cb_click, each)
          
         
         def do_get_property(self, prop):
            if prop.name == "selection-active":
               return self._selection_active
            else:
               raise AttributeError("unknown property: %s" % prop.name)
         

         def do_selection_active_changed(self, state):
            state = not state
            self.choose.set_sensitive(state and self._profile is None)
            self.delete.set_sensitive(state)

         
         def _cb_click(self, widget, signal):
            if self._highlighted is not None:
               self.emit(signal, self._highlighted)
               self._update_data()
         
         
         def _cb_visible(self, *args):
            if self.props.visible:
               gobject.timeout_add(200, self._update_data)
            
            
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
            for i, data in enumerate(self.sorted):
               if data[1] == target:
                  self.selection.select_path(i)
                  self.selection.get_tree_view().scroll_to_cell(i)


         def _sort_func(self, model, *iters):
            vals = tuple(model.get_value(x, 1) for x in iters)
            
            try:
               return vals.index("default")
            except ValueError:
               return cmp(*vals)
            

         def set_data_function(self, f):
            self._data_function = f
            self._update_data()
            if f is not None:
               self._highlight_profile(highlight)
               
               
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
                        if d["profile"] == "default":
                           i = PGlobs.default_icon
                        else:
                           i = None
                     if i is not None:
                        pb = gtk.gdk.pixbuf_new_from_file_at_size(i, 16, 16)                     
                     else:
                        pb = None
                     desc = d["description"] or ""
                     active = d["active"]
                     self.store.append((pb, d["profile"], desc, active))
                  self._highlight_profile(h)
            return self.props.visible
            
            
         @property
         def profile(self):
            return self._profile
            
            
         def set_profile(self, newprofile):
            assert self._profile is None
            self._profile = newprofile
            self.set_title(self.get_title() + "  (%s)" % newprofile)
            self.choose.set_label("Chosen")
            self.response(0)
            
            
         def run(self):
            self.show_all()
            gtk.Dialog.run(self)


      d = Dialog(data_function=self._profile_data)
      return d
