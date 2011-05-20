"""Generally useful Python code.

But strictly no third party module dependencies.
"""

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
import threading

from functools import wraps


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



def _PA_rlock(f):
   """Policed Attributes helper for thread locking."""
   
   @wraps(f)
   def _wrapper(cls, *args, **kwds):
      bc = f.func_globals["bc"] = super(type(cls), cls)
      rlock = bc.__getattribute__("_rlock")
      
      try:
         rlock.acquire()
         return f(cls, *args, **kwds)
      finally:
         rlock.release()

   return _wrapper



class PolicedAttributes(type):
   """Polices data access to a namespace class.
   
   Prevents write access to attributes after they have been read.
   Envisioned useful for the implementation of "safe" global variables.
   """

   def __new__(meta, name, bases, _dict):
      @classmethod
      @_PA_rlock
      def peek(cls, attr, cb, *args, **kwds):
         """Allow read + write within a callback.

         Typical use might be to append to an existing string.
         No modification ban is placed or bypassed.
         """
         
         if attr not in bc.__getattribute__("_banned"):
            new = cb(
                  super(PolicedAttributes, cls).__getattribute__(attr),
                  *args, **kwds)
            bc.__setattr__(attr, new)
         else:
            raise NotImplementedError("variable is locked")
      
      _dict["peek"] = peek
      _dict["_banned"] = set()
      _dict["_rlock"] = threading.RLock()
      return super(PolicedAttributes, meta).__new__(meta, name, bases, _dict)


   @_PA_rlock
   def __getattribute__(cls, name):
      bc.__getattribute__("_banned").add(name)
      return bc.__getattribute__(name)

     
   @_PA_rlock
   def __setattr__(cls, name, value):
      if name in bc.__getattribute__("_banned"):
         raise NotImplementedError("value has already been read")
      bc.__setattr__(name, value)

         
   def __call__(cls, *args, **kwds):
      raise NotImplementedError("this class cannot be instantiated")



class FixedAttributes(type):
   """Implements a namespace class of constants."""
   

   def __setattr__(cls, name, value):
      raise NotImplementedError("value cannot be changed")
      
   
   def __call__(cls, *args, **kwds):
      raise NotImplementedError("this class cannot be instantiated")
      


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
