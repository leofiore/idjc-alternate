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
from functools import partial

import dbus
import dbus.service
import glib

from idjc import FGlobs
from idjc import PGlobs
from ..utils import Singleton


# The name of the default profile.
default = "default"


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
      sp_mp.add_argument("newprofile", metavar="profile_name",
            help="""new profile name -- will form part of the dbus
            bus/object/interface name and the jack client ID --
            restrictions therefore apply""")
      sp_mp.add_argument("-t", "--template", dest="template", metavar="template_profile",
            help="an existing profile to use as a template")
      sp_mp.add_argument("-i", "--icon", dest="icon", metavar="icon_pathname",
            help="pathname to an icon -- defaults to idjc logo")
      sp_mp.add_argument("-n", "--nickname", dest="nickname", metavar="nickname",
            help="""the alternate name to appear in window title bars""")
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

     

# Profile length limited for practical reasons. For more descriptive
# purposes the nickname parameter was created.
MAX_PROFILE_LENGTH = 12



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
   

   _profile = _dbus_bus_name = _profile_dialog = None

   _optionals = ("icon", "nickname", "description")




   def __init__(self):
      ap = ArgumentParserImplementation()
      args = ap.parse_args()

      if PGlobs.profile_dir is not None:
         try:
            if not os.path.isdir(os.path.join(PGlobs.profile_dir, default)):
               self._generate_default_profile()

            if "newprofile" in args:
               self._generate_profile(**vars(args))
               ap.exit(0)
         except ProfileError as e:
            ap.error("failed to create profile: " + str(e))

         profile = default
         dialog_selects = not os.path.exists(PGlobs.profile_dialog_refusal_pathname)
         if args.profile is not None:
            profile = args.profile[0]
            dialog_selects = False
            if not profile_name_valid(profile):
               ap.error("specified profile name is not valid")

         if args.dialog is not None:
            dialog_selects = args.dialog[0] == "true"
         
         self._profile_dialog = self._get_profile_dialog()
         self._profile_dialog.connect("delete", self._cb_delete_profile)
         self._profile_dialog.connect("choose", self._choose_profile)
         def new_profile(dialog, profile, template, icon, nickname, description):
            try:
               self._generate_profile(profile, template, icon=icon,
                           nickname=nickname, description=description)
               dialog.destroy_new_profile_dialog()
            except ProfileError as e:
               dialog.display_error("Error while creating new profile",
               e.gui_text, transient_parent=dialog.get_new_profile_dialog())

         self._profile_dialog.connect("new", new_profile)
         self._profile_dialog.connect("clone", new_profile)
         if dialog_selects:
            self._profile_dialog.run()
            self._profile_dialog.hide()
         else:
            self._choose_profile(self._profile_dialog, profile, verbose=True)
         if self._profile is None:
            ap.error("no profile set")


   @property
   def profile(self):
      return self._profile


   @property
   def nickname(self):
      return self._nickname


   @property
   def dbus_bus_name(self):
      return self._dbus_bus_name

      
   def show_profile_dialog(self):
      self._profile_dialog.show_all()
      
      
   def _cb_delete_profile(self, dialog, profile):
      if profile is not dialog.profile:
         try:
            busname = self._grab_bus_name_for_profile(profile)
            shutil.rmtree(os.path.join(PGlobs.profile_dir, profile))
         except dbus.DBusException:
            pass
         if profile == default:
            self._generate_default_profile()
      
   
   def _choose_profile(self, dialog, profile, verbose=False):
      if dialog._profile is None:
         try:
            busname = self._grab_bus_name_for_profile(profile)
         except dbus.DBusException:
            if verbose:
               print "profile '%s' is in use" % profile
         else:
            nickname = self._grab_nickname_for_profile(profile)
            nickname = nickname or profile
            dialog.set_profile(profile, nickname)
            self._profile = profile
            self._nickname = nickname
            self._dbus_bus_name = busname


   def _generate_profile(self, newprofile, template=None, **kwds):
      if PGlobs.profile_dir is not None:
         if len(newprofile) > MAX_PROFILE_LENGTH:
            raise ProfileError("the profile length is too long " 
                           "(max %d characters)" % MAX_PROFILE_LENGTH,
               "The profile length is too long (max %d characters)."
                                                 % MAX_PROFILE_LENGTH)

         if not profile_name_valid(newprofile):
            raise ProfileError("the new profile name is not valid",
                                 "The new profile name is not valid.")
           
         try:
            busname = self._grab_bus_name_for_profile(newprofile)
         except dbus.DBusException:
            raise ProfileError("the profile is currently running",
                                 "The profile is currently running.")

         try:
            tmp = tempfile.mkdtemp()
         except EnvironmentError:
            raise ProfileError("temporary directory creation failed",
                                 "Temporary directory creation failed.")
            
         try:
            if template is not None:
               if not profile_name_valid(template):
                  raise ProfileError(
                        "specified template not valid (%s)" % template,
                        "Specified template not valid (%s)" % template)
               
               tdir = os.path.join(PGlobs.profile_dir, template)
               if os.path.isdir(tdir):
                  for x in self._optionals + ("config", ):
                     try:
                        shutil.copyfile(os.path.join(tdir, x),
                                        os.path.join(tmp, x))
                     except EnvironmentError:
                        pass
               else:
                  raise ProfileError(
                     "template profile '%s' does not exist" % template,
                     "Template profile '%s' does not exist." % template)
                  
            for fname in self._optionals:
               if kwds.get(fname):
                  try:
                     with open(os.path.join(tmp, fname), "w") as f:
                        f.write(kwds[fname])
                  except EnvironmentError:
                     raise ProfileError("could not write " + fname,
                                        "Could not write %s" % fname)
            

            dest = os.path.join(PGlobs.profile_dir, newprofile)
            try:
               shutil.copytree(tmp, dest)
            except EnvironmentError as e:
               if e.errno == 17 and os.path.isdir(dest):
                  msg1 = "the profile directory '%s' exists" % dest
                  msg2 = "The profile directory '%s' exists." % dest
               else:
                  msg1 = "non directory path exists: '%s'" % dest
                  msg2 = "Non directory path exists: '%s'." % dest
               raise ProfileError(msg1, msg2)
         finally:
            # Failure to clean up is not a critical error.
            try:
               shutil.rmtree(tmp)
            except EnvironmentError:
               pass


   def _generate_default_profile(self):
      self._generate_profile(default, description="The default profile")


   def _profile_data(self):
      d = PGlobs.profile_dir
      try:
         profdirs = os.walk(d).next()[1]
      except EnvironmentError:
         return
      for profname in profdirs:
         if profile_name_valid(profname):
            files = os.walk(os.path.join(d, profname)).next()[2]
            rslt = {"profile": profname}
            for each in self._optionals:
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


   @staticmethod
   def _grab_nickname_for_profile(profile):
      d = PGlobs.profile_dir
      try:
         with open(os.path.join(d, profile, "nickname")) as f:
            return f.read()
      except EnvironmentError:
         return None


   def _get_profile_dialog(self):
      from .profiledialog import ProfileDialog
      
      return ProfileDialog(default=default, data_function=self._profile_data)
