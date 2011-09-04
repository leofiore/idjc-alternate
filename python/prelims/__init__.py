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


__all__ = ["ArgumentParserImplementation", "ProfileManager"]


import os
import sys
import argparse
import shutil
import tempfile
import time
import math
import subprocess
from functools import partial
from collections import defaultdict

import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
DBusGMainLoop(set_as_default=True)
import glib

from idjc import FGlobs
from idjc import PGlobs
from ..utils import Singleton
from ..utils import PathStr


import gettext
t = gettext.translation(FGlobs.package_name, FGlobs.localedir)
_ = t.gettext



# The name of the default profile.
default = "default"


config_files = ("config", "controls", "left_session", "main_session",
   "main_session_files_played", "main_session_tracks", "playerdefaults",
   "right_session", "s_data", "mic1", "mic2", "mic3", "mic4", "mic5",
   "mic6", "mic7", "mic8", "mic9", "mic10", "mic11", "mic12")


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
                     # TC: command line switch info from $ idjc --help
                     help=_("sub-option -h for more info"))
      # TC: a command line option help string.
      sp_run = sp.add_parser("run", help=_("the default command"),
         # TC: do not translate run.
         description=description + " " + _("-- sub-command: run"), epilog=epilog)
      # TC: a command line option help string.
      sp_mp = sp.add_parser("generateprofile", help=_("make a new profile"),
         # TC: do not translate generateprofile.
         description=description + " " + _("-- sub-command: generateprofile"), epilog=epilog)

      sp_run.add_argument("-d", "--dialog", dest="dialog", nargs=1, 
            choices=("true", "false"), 
            help=_("""force the appearance or non-appearance of the
            profile chooser dialog -- when used with the -p option
            the chosen profile is preselected"""))
      # TC: command line help placeholder.
      sp_run.add_argument("-p", "--profile", dest="profile", nargs=1, metavar=_("profile_choice"), 
            help=_("""the profile to use -- overrides the user interface
            preferences "show profile dialog" option"""))
      sp_run.add_argument("-j", "--jackserver", dest="jackserver", nargs=1,
            # TC: command line help placeholder.
            metavar=_("server_name"), help=_("the named jack sound-server to connect with"))
      group = sp_run.add_argument_group(_("user interface settings"))
      group.add_argument("-m", "--mics", dest="mics", nargs="+", metavar="m",
            help=_("the microphones open at startup"))
      group.add_argument("-a", "--aux", dest="aux", nargs="+", metavar="a",
            help=_("the aux ports open at startup"))
      group.add_argument("-V", "--voip", dest="voip", nargs=1, choices=
            ("off", "private", "public"),
            help=_("the voip mode at startup"))
      group.add_argument("-P", "--players", dest="players", nargs="+", metavar="p",
            help="the players to start among values {1,2}")
      group.add_argument("-s", "--servers", dest="servers", nargs="+", metavar="s",
            help=_("attempt connection with the specified servers"))
      group.add_argument("-c", "--crossfader", dest="crossfader", choices=("1", "2"), 
            help=_("position the crossfader for the specified player"))
      # TC: command line help placeholder.
      sp_mp.add_argument("newprofile", metavar=_("profile_name"),
            help=_("""new profile name -- will form part of the dbus
            bus/object/interface name and the JACK client ID --
            restrictions therefore apply"""))
      # TC: command line help placeholder.
      sp_mp.add_argument("-t", "--template", dest="template", metavar=_("template_profile"),
            help=_("an existing profile to use as a template"))
      # TC: command line help placeholder.
      sp_mp.add_argument("-i", "--icon", dest="icon", metavar=_("icon_pathname"),
            help=_("pathname to an icon -- defaults to idjc logo"))
      # TC: Command line help placeholder for the profile's nickname.
      # TC: Actual profile names are very restricted in what characters can be used.
      sp_mp.add_argument("-n", "--nickname", dest="nickname", metavar=_("nickname"),
            help=_("""the alternate profile name to appear in window title bars"""))
      sp_mp.add_argument("-d", "--description", dest="description", metavar=_("description_text"),
            help=_("a description of the profile"))


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

     

class DBusUptimeReporter(dbus.service.Object):
   """Supply uptime to other idjc instances."""


   interface_name = PGlobs.dbus_bus_basename + ".profile"
   obj_path  = PGlobs.dbus_objects_basename + "/uptime"
   
   
   def __init__(self):
      self._uptime_cache = defaultdict(float)
      self._interface_cache = {}
      # Defer base class initialisation.
                           
                           
   @dbus.service.method(interface_name, out_signature="d")
   def get_uptime(self):
      """Broadcast uptime from the current profile."""
      
      return self._get_uptime()


   def activate_for_profile(self, bus_name, get_uptime):
      self._get_uptime = get_uptime
      dbus.service.Object.__init__(self, bus_name, self.obj_path)


   def get_uptime_for_profile(self, profile):
      """Ask and return the uptime of an active profile.
      
      Step 1, Issue an async request for new data.
      Step 2, Return immediately with the cached value.
      
      Note: On error the cache is purged.
      """


      def rh(retval):
         self._uptime_cache[profile] = retval
         
      
      def eh(exception):
         try:
            del self._uptime_cache[profile]
         except KeyError:
            pass
         try:
            del self._interface_cache[profile]
         except KeyError:
            pass


      try:
         interface = self._interface_cache[profile]
      except KeyError:
         try:
            p = dbus.SessionBus().get_object(PGlobs.dbus_bus_basename + \
                                             "." + profile, self.obj_path)
            interface = dbus.Interface(p, self.interface_name)
         except dbus.exceptions.DBusException as e:
            eh(e)
            return self._uptime_cache.default_factory()
         
         self._interface_cache[profile] = interface

      interface.get_uptime(reply_handler=rh, error_handler=eh)
      return self._uptime_cache[profile]



# Profile length limited for practical reasons. For more descriptive
# purposes the nickname parameter was created.
MAX_PROFILE_LENGTH = 18



def profile_name_valid(p):
   try:
      dbus.validate_bus_name("com." + p)
      dbus.validate_object_path("/" + p)
   except (TypeError, ValueError):
      return False
   return len(p) <= MAX_PROFILE_LENGTH



class ProfileError(Exception):
   """General purpose exception used within the ProfileManager class.
   
   Takes two strings so that one can be used for command line messages
   and the other for displaying in dialog boxes."""
   
   def __init__(self, str1, str2=None):
      Exception.__init__(self, str1)
      self.gui_text = str2



class ProfileManager(object):
   """The profile gives each application instance a unique identity.
   
   This identity extends to the config file directory if present, 
   to the JACK application ID, to the DBus bus name.
   """
   
   __metaclass__ = Singleton
   

   _profile = _dbus_bus_name = _profile_dialog = _init_time = None

   _optionals = ("icon", "nickname", "description")



   def __init__(self):
      ap = ArgumentParserImplementation()
      args = ap.parse_args()

      if PGlobs.profile_dir is not None:
         try:
            if not os.path.isdir(PGlobs.profile_dir / default):
               self._generate_default_profile()

            if "newprofile" in args:
               self._generate_profile(**vars(args))
               ap.exit(0)
         except ProfileError as e:
            ap.error(_("failed to create profile: %s") % str(e))

         profile = default
         dialog_selects = not os.path.exists(PGlobs.profile_dialog_refusal_pathname)
         if args.profile is not None:
            profile = args.profile[0]
            dialog_selects = False
            if not profile_name_valid(profile):
               ap.error(_("the specified profile name is not valid"))

         if args.dialog is not None:
            dialog_selects = args.dialog[0] == "true"
         
         self._uprep = DBusUptimeReporter()
         self._profile_dialog = self._get_profile_dialog()
         self._profile_dialog.connect("delete", self._cb_delete_profile)
         self._profile_dialog.connect("choose", self._choose_profile)

         def new_profile(dialog, profile, template, icon, nickname, description):
            try:
               self._generate_profile(profile, template, icon=icon,
                           nickname=nickname, description=description)
               dialog.destroy_new_profile_dialog()
            except ProfileError as e:
               dialog.display_error(_("<span weight='bold' size='12000'>Error while creating new profile.</span>\n\n%s") % e.gui_text,
               transient_parent=dialog.get_new_profile_dialog(), markup=True)

         self._profile_dialog.connect("new", new_profile)
         self._profile_dialog.connect("clone", new_profile)
         self._profile_dialog.connect("edit", self._cb_edit_profile)
         if dialog_selects:
            self._profile_dialog.run()
            self._profile_dialog.hide()
         else:
            self._choose_profile(self._profile_dialog, profile, verbose=True)
         if self._profile is None:
            ap.error(_("no profile is set"))


   @property
   def profile(self):
      return self._profile


   @property
   def iconpathname(self):
      return self._iconpathname


   @property
   def dbus_bus_name(self):
      return self._dbus_bus_name

      
   @property
   def basedir(self):
      """The base directory of this profile."""
      
      return PGlobs.profile_dir / self.profile
      
      
   @property
   def jinglesdir(self):
      """The directory for jingles storage."""
      
      return self.basedir / "jingles"
      
      
   @property
   def title_extra(self):
      """Window title text indicating which profile is in use."""
      
      n = self._nickname
      if n:
         return "  (%s:%s)" % ((self.profile, n))
      else:
         if self.profile == default:
            return ""
         return "  (%s)" % self.profile


   def get_uptime(self):
      if self._init_time is not None:
         return time.time() - self._init_time
      else:
         return 0.0


   def show_profile_dialog(self):
      self._profile_dialog.show_all()
      
      
   def _cb_edit_profile(self, dialog, newprofile, oldprofile, *opts):
      busses = []
      
      try:
         try:
            busses.append(self._grab_bus_name_for_profile(oldprofile))
            if newprofile != oldprofile:
               busses.append(self._grab_bus_name_for_profile(newprofile))
         except dbus.DBusException:
            raise ProfileError(None, _("Profile %s is active.") % 
                                    (oldprofile, newprofile)[len(busses)])

         if newprofile != oldprofile:
            try:
               shutil.copytree(PGlobs.profile_dir / oldprofile,
                                       PGlobs.profile_dir / newprofile)
            except EnvironmentError as e:
               if e.errno == 17:
                  raise ProfileError(None, 
                  _("Cannot rename profile {0} to {1}, {1} currently exists.").format(
                                                oldprofile, newprofile))
               else:
                  raise ProfileError(None, 
                     _("Error during attempt to rename {0} to {1}.").format(
                                                oldprofile, newprofile))

            shutil.rmtree(PGlobs.profile_dir / oldprofile)

         for name, data in zip(self._optionals, opts):
            with open(PGlobs.profile_dir / newprofile / name, "w") as f:
               f.write(data or "")

      except ProfileError, e:
         text = _("<span weight='bold' size='12000'>Error while editing profile: {0}.</span>\n\n{1}").format(oldprofile, e.gui_text)
         dialog.display_error(text, markup=True,
                        transient_parent=dialog.get_new_profile_dialog())
      else:
         dialog.destroy_new_profile_dialog()
      
      
   def _cb_delete_profile(self, dialog, profile):
      if profile is not dialog.profile:
         try:
            busname = self._grab_bus_name_for_profile(profile)
            shutil.rmtree(PGlobs.profile_dir / profile)
         except dbus.DBusException:
            pass
         if profile == default:
            self._generate_default_profile()


   def _choose_profile(self, dialog, profile, verbose=False):
      if dialog.profile is None:
         try:
            self._dbus_bus_name = self._grab_bus_name_for_profile(profile)
         except dbus.DBusException:
            if verbose:
               print _("the profile '%s' is in use") % profile
         else:
            self._init_time = time.time()
            self._profile = profile
            self._nickname = self._grab_profile_filetext(
                               profile, "nickname") or ""
            self._iconpathname = self._grab_profile_filetext(
                               profile, "icon") or PGlobs.default_icon
            dialog.set_profile(profile, self.title_extra, self._iconpathname)
            self._uprep.activate_for_profile(self._dbus_bus_name, self.get_uptime)
      else:
         print "%s run -p %s" % (FGlobs.bindir / FGlobs.package_name, profile)
         subprocess.Popen([FGlobs.bindir / FGlobs.package_name, "run", "-p", profile], close_fds=True)


   def _generate_profile(self, newprofile, template=None, **kwds):
      if PGlobs.profile_dir is not None:
         if len(newprofile) > MAX_PROFILE_LENGTH:
            raise ProfileError(_("the profile length is too long (max %d characters)") % MAX_PROFILE_LENGTH,
               _("The profile length is too long (max %d characters).") % MAX_PROFILE_LENGTH)

         if not profile_name_valid(newprofile):
            raise ProfileError(_("the new profile name is not valid"),
                                 _("The new profile name is not valid."))
           
         try:
            busname = self._grab_bus_name_for_profile(newprofile)
         except dbus.DBusException:
            raise ProfileError(_("the chosen profile is currently running"),
                                 _("The chosen profile is currently running."))

         try:
            tmp = PathStr(tempfile.mkdtemp())
         except EnvironmentError:
            raise ProfileError(_("temporary directory creation failed"),
                                 _("Temporary directory creation failed."))
            
         try:
            if template is not None:
               if not profile_name_valid(template):
                  raise ProfileError(
                        _("the specified template '%s' is not valid") % template,
                        _("The specified template '%s' is not valid.") % template)
               
               tdir = PGlobs.profile_dir / template
               if os.path.isdir(tdir):
                  for x in self._optionals + config_files:
                     try:
                        shutil.copyfile(tdir / x, tmp / x)
                     except EnvironmentError:
                        pass
                  shutil.copytree(tdir / "jingles", tmp / "jingles")
               else:
                  raise ProfileError(
                     _("the template profile '%s' does not exist") % template,
                     _("The template profile '%s' does not exist.") % template)
                  
            for fname in self._optionals:
               if kwds.get(fname):
                  try:
                     with open(tmp / fname, "w") as f:
                        f.write(kwds[fname])
                  except EnvironmentError:
                     raise ProfileError(_("could not write file %s") + fname,
                                        _("Could not write file %s.") % fname)
            

            dest = PGlobs.profile_dir / newprofile
            try:
               shutil.copytree(tmp, dest)
            except EnvironmentError as e:
               if e.errno == 17 and os.path.isdir(dest):
                  msg1 = _("the profile directory '%s' already exists") % dest
                  msg2 = _("The profile directory '%s' already exists.") % dest
               else:
                  msg1 = _("a non directory path exists at: '%s'") % dest
                  msg2 = _("A Non directory path exists at: '%s'.") % dest
               raise ProfileError(msg1, msg2)
         finally:
            # Failure to clean up is not a critical error.
            try:
               shutil.rmtree(tmp)
            except EnvironmentError:
               pass


   def _generate_default_profile(self):
      self._generate_profile(default, description=_("The default profile"))


   def _profile_data(self):
      d = PGlobs.profile_dir
      try:
         profdirs = os.walk(d).next()[1]
      except EnvironmentError:
         return
      for profname in profdirs:
         if profile_name_valid(profname):
            files = os.walk(d / profname).next()[2]
            rslt = {"profile": profname}
            for each in self._optionals:
               try:
                  with open(d / profname / each) as f:
                     rslt[each] = f.read()
               except EnvironmentError:
                  rslt[each] = None
               
            rslt["active"] = self._profile_has_owner(profname)
            rslt["uptime"] = math.floor(self._uprep.get_uptime_for_profile(profname))
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


   @staticmethod
   def _grab_profile_filetext(profile, filename):
      try:
         with open(PGlobs.profile_dir / profile / filename) as f:
            return f.readline().strip()
      except EnvironmentError:
         return None


   def _get_profile_dialog(self):
      from .profiledialog import ProfileDialog
      
      return ProfileDialog(default=default, data_function=self._profile_data)
