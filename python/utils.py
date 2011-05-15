"""Generally useful Python code."""

#   utils.py: Free functions used by IDJC
#   Copyright (C) 2011 Stephen Fairchild (s-fairchild@users.sourceforge.net)
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


import os


class Singleton(type):
   """Enforce the singleton pattern upon the user class."""
   
   def __call__(cls, *args, **kwds):
      try:
         # Return an existing instance.
         return cls._instance
      except AttributeError:
         # No existing instance so instantiate just this once.
         cls._instance = super(Singleton, cls).__call__(*args, **kwds)
         return cls._instance


def mkdir_p(path):
   """Equivalent to the shell command: mkdir -p path."""
    
   def inner(path):
      if path == os.path.sep:
          return

      head, tail = os.path.split(path)
      inner(head)

      try:
          os.mkdir(head)
      except OSError, e:
          if e.errno != 17:
              raise

   if not os.path.isdir(path):
      inner(path.rstrip(os.path.sep))  # Make the parents.
      os.mkdir(path)
