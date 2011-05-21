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

import glib

from idjc import FGlobs
from idjc import PGlobs
from ..utils import Singleton
from ..utils import mkdir_p



class ArgumentParser(object):
   """To parse the command line arguments, if any."""

   __metaclass__ = Singleton

   
   class APError(Exception):
      pass



   class Namespace(argparse.Namespace):
      """Argument parser namespaces can contain conjoined attributes.
      
      e.g. "i, __icon" which will be split apart here. This makes two
      identical variables i and __icon and keeps 'icon'.
      """


      def __init__(self, ns):
         for key, val in ns.__dict__.iteritems():
             keys = key.split(", ")
             setattr(self, keys[-1].lstrip("_"), val)

      

   def __init__(self, args=None, description=None, epilog=None):
      if args is None:
         args = sys.argv[1:]

      self._args = list(args)

      if description is None:
         description = PGlobs.app_longform

     
      class AP(argparse.ArgumentParser):
         APError = self.APError
         
         def error(self, text):
            raise self.APError(text)
            
         def bc_error(self, text):
            super(AP, self).error(text)


      ap = self._ap = AP(description=description, epilog=epilog)
      ap.add_argument("-v", "--version", action='version', version=
                     FGlobs.package_name + " " + FGlobs.package_version)
      sp = self._sp = ap.add_subparsers(
                     help="sub-option -h for more info")
      sp_run = sp.add_parser("run", help="the default command",
         description=description + " -- sub-command: run", epilog=epilog)
      sp_mp = sp.add_parser("generateprofile", help="make a new profile",
         description=description + " -- sub-command: generateprofile", epilog=epilog)

      sp_run.add_argument("-d, --dialog", nargs=1, 
            choices=("true", "false"), 
            help="""force the appearance or non-appearance of the
            profile chooser dialog -- when used with the -p option
            the chosen profile is preselected""")
      sp_run.add_argument("-p, --profile", nargs=1, metavar="P", 
            help="""the profile to use -- overrides the user interface
            preferences "show profile dialog" option""")
      sp_run.add_argument("-j, --jackserver", nargs=1, metavar="server_name",
            help="the named jack server to connect with")
      group = sp_run.add_argument_group("user interface settings")
      group.add_argument("-m, --mics", nargs="+", metavar="m",
            help="microphones open at startup")
      group.add_argument("-a, --aux", nargs="+", metavar="a",
            help="aux ports open at startup")
      group.add_argument("-V, --voip", nargs=1, choices=
            ("off", "private", "public"),
            help="the voip mode at startup")
      group.add_argument("-p, --players", nargs="+", metavar="p",
            help="the players to start among values {1,2}")
      group.add_argument("-s, --servers", nargs="+", metavar="s",
            help="attempt connection with the specified servers")
      group.add_argument("-r, --recorders", nargs="+", metavar="r",
            help="the recorders to start")
      group.add_argument("-f, --crossfader", choices=("1", "2"), 
            help="position the crossfader for the specified player")
      sp_mp.add_argument("newprofile", metavar="p", help="new profile name")
      sp_mp.add_argument("-t, --template", metavar="t",
            help="an existing profile to use as a template")
      sp_mp.add_argument("-i, --icon", metavar="i",
            help="defaults to idjc logo")
      sp_mp.add_argument("-d, --description", metavar="d",
            help="description of the profile")


   def parse_args(self):
      try:
         return self.Namespace(self._ap.parse_args(self._args))
      except self.APError as e:
         try:
            for cmd in self._sp.iterkeys():
               if cmd in self._args:
                  raise
            return self.Namespace(self._ap.parse_args(self._args + ["run"]))
         except self.APError:
            self._ap.bc_error(str(e))



class ProfileSelector(object):
   """The profile gives each application instance a unique identity.
   
   This identity extends to the config file directory if present, 
   to the JACK application ID, to the DBus bus name.
   """
   
   __metaclass__ = Singleton
   

   class ProfileError(Exception):
      pass

   
   def __init__(self, allow_gui=True, gui_title="Profile Selector"):
      ap = ArgumentParser()
      args = ap.parse_args()

      try:
         if PGlobs.config_dir is not None:
            if not os.path.isdir(os.path.join(PGlobs.config_dir, "default")):
               self.generate_profile("default", description="The default profile")

            if "newprofile" in args:
               try:
                  self.generate_profile(**vars(args))
               except self.ProfileError as e:
                  ap._ap.bc_error("profile creation failed: " + str(e))
               else:
                  ap._ap.exit(0)
      
      except self.ProfileError as p:
         ap.error("problem generating profile: " + str(p))

      
   def generate_profile(self, newprofile, description, icon, template):
      if PGlobs.config_dir is not None:
         try:
            tmp = tempfile.mkdtemp()
         except OSError:
            raise self.ProfileError("temporary directory creation failed")
            
         try:
            if template is not None:
               tdir = os.path.join(PGlobs.config_dir, template)
               if os.path.isdir(tdir):
                  for x in ("icon", "description", "config"):
                     try:
                        shutil.copyfile(os.path.join(tdir, x),
                                        os.path.join(tmp, x))
                     except IOError:
                        pass
               else:
                  raise self.ProfileError("template profile does not exist")
                  
            if description is not None:
               try:
                  with open(os.path.join(tmp, "description"), "w") as f:
                     f.write(description)
               except IOError:
                  raise self.ProfileError("could not write description")
                  
            if icon is not None:
               try:
                  shutil.copyfile(icon, os.path.join(tmp, "icon"))
               except IOError:
                  raise self.ProfileError("could not transfer icon")
            
            try:
               dest = os.path.join(PGlobs.config_dir, newprofile)
               shutil.copytree(tmp, dest)
            except IOError as e:
               if e.errno == 17 and os.path.isdir(dest):
                  msg = "profile directory exists"
               else:
                  msg = "could not create profile directory"
               raise self.ProfileError(msg)
         finally:
            # Failure to clean up is not a failure worth declaring.
            try:
               shutil.rmtree(tmp)
            except Exception:
               pass
