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


__all__ = ["ArgumentParser", "set_config_dir", "get_config_dir"]


import argparse

from ..utils  import Singleton
from ..utils  import mkdir_p
from ..config import package_name
from ..config import package_version


_config_dir = None


def set_config_dir(d):
   # Call this before set_profile_dir if you require working.
   global _config_dir
   
   _config_dir = d
   
   
def get_config_dir():
   # The first call here locks this value in.
   c = ConfigDirConfigure()
   assert c.get_config_dir() == _config_dir, "config directory changed"
   return _config_dir


class ConfigDirConfigure(object):
   __metaclass__ = Singleton
   
   def __init__(self):
      # Make the directory.
      if _config_dir is not None:
         mkdir_p(_config_dir)
      self._config_dir = _config_dir
   

   def get_config_dir(self):
      return self._config_dir   


class ArgumentParser(argparse.ArgumentParser):
   # We only ever want our command line arguments parsed once.
   __metaclass__ = Singleton
   

   def __init__(self, *args):
      desc = "Internet DJ Console -- be a DJ on the internet"
      argparse.ArgumentParser.__init__(self, description=desc)
      
      self.add_argument("-v", "--version", action='version', version=
                                 package_name + " " + package_version)

      self.add_argument("-p", action="store", nargs=1,
      metavar="profile_name", help="the configuration profile to use")

      self.add_argument("-c", nargs="+",
         metavar="name +[comment] +[clone] +[icon]", action="store",
         help="""create the profile 'name' with optionals preceeded by '+'
         -- an existing profile may be cloned hence the 'clone' option
         -- the icon will be used to mark windows belonging to a particular
         profile and can be can be png, jpeg -- idjc will exit afterwards
         if no '-p' or '-d' option is specified""")

      self.add_argument("-d", action="store", nargs=1,
         choices=["true", "false"], help=
         """override the config file setting for showing the profile
         chooser dialog -- normally selecting a profile would
         cause the dialog to be skipped""")
      
      self.add_argument("-j", action="store", nargs=1,
         metavar="jack_server",
         help="""the named JACK sound server to connect with""")
      
      self.add_argument("-V", action="store", choices=range(3), type=int,
         help="""the initial VoIP mode - off, private, public respectively""")
      
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
      
      self.parse_args(*args)


