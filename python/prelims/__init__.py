"""Preliminary initialisation stuff.

Intended to be called from outside in order to configure capabilities.
"""

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


import argparse

from ..utils  import Singleton
from ..utils  import PolicedAttributes
from ..utils  import mkdir_p
from ..config import package_name
from ..config import package_version


      
class Globs(object):
   __metaclass__ = PolicedAttributes
   
   # You probably don't want these settings. They were deliberately
   # chosen to require overriding so the code could self document
   # and also be reused.
   config_dir = None
   dbus_bus_basename = "com.example"
   dbus_objects_basename = "/com/example"
   app_shortform = "unnamed application"
   app_longform = "unnamed application"
   default_icon = None
   dbus_busname = None
   argument_parser = None


class ArgumentParser(argparse.ArgumentParser):
   """To parse the command line arguments, if any."""

   __metaclass__ = Singleton
   

   def __init__(self, args=None, description=None):
      if description is None:
         description = Globs.app_longform

      argparse.ArgumentParser.__init__(self, description=description)
   
      self.add_argument("-v", "--version", action='version', version=
                                 package_name + " " + package_version)

      self.add_argument("-p", action="store", nargs=1,
         metavar="profile_name", help="""the configuration profile to use 
         -- """ + ("""if the profile dialog is suppressed 'default' will
         be assumed"""
         if Globs.config_dir is not None else """if no '-p' option is
         specified the process ID will be used"""))

      if Globs.config_dir is not None:
         self.add_argument("-c", nargs="+",
            metavar="name +[comment] +[clone] +[icon]", action="store",
            help="""create the profile 'name' with optionals preceeded by '+'
            -- an existing profile may be cloned hence the 'clone' option
            -- the icon will be used to mark windows belonging to a particular
            profile and can be can be png, jpeg -- idjc will exit afterwards
            if no '-p' or '-d' option is specified""")

      if Globs.config_dir is not None:
         self.add_argument("-d", action="store", nargs=1,
            choices=["true", "false"], help=
            """override the config file setting for showing the profile
            chooser dialog -- normally selecting a profile would
            cause the dialog to be skipped""")
      
      self.add_argument("-j", action="store", nargs=1,
         metavar="jack_server",
         help="""the named JACK sound server to connect with""")
      
      self.add_argument("-V", action="store", choices=(
         "off", "private", "public"),
         help="""the initial VoIP mode""")
      
      self.add_argument("-m", action="store", nargs="+", choices=range(1, 13),
         type=int, help="""the microphones to be switched on --
         note that additional microphones will be switched on if they
         share a microphone group""")
      
      self.add_argument("-a", action="store", nargs=1, choices=[1],
         type=int, help="""the aux ports to be switched on""")
      
      self.add_argument("-P", action="store", nargs=1, choices=[1, 2],
         type=int, help="""the media players to be started""")
      
      self.add_argument("-C", action="store", nargs=1, choices=[1, 2],
         type=int, help="""the crossfader position""")
      
      self._args = args


   def parse_args(self):
      return super(ArgumentParser, self).parse_args(self._args)



class ProfileSelector(object):
   """The profile gives each application instance a unique identity.
   
   This identity extends to the config file directory if present, 
   to the JACK application ID, to the DBus bus name.
   
   In addition to a name an icon can be associated.
   """
   
   __metaclass__ = Singleton
   
   
   def __init__(self, allow_gui=True, gui_title="Profile Selector"):
      ap = Globs.argument_parser = ArgumentParser()
      args = ap.parse_args()

      # Make profiles that are requested.
      if Globs.config_dir is not None:
         mkdir_p(Globs.config_dir)

         if args.c is not None:
            create_list = []
            for a in args.c:
               if a.startswith("+"):
                  create_list[-1].append(a[1:] if len(a) > 1 else None)
               else:
                  create_list.append([])
                  create_list[-1].append(a)

            for l in create_list:
               while len(l) < 4:
                  l.append(None)
            
            print create_list
      
      print args
      ap.error("trying this out for size")

