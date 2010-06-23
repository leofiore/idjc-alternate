#   IDJCfree.py: Free functions used by IDJC
#   Copyright (C) 2005-2007 Stephen Fairchild (s-fairchild@users.sourceforge.net)
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

import pygtk
pygtk.require("2.0")
import gtk

import os, encodings.hex_codec

# Convert characters that have special meaning in pango markup language to their safe equivalents
def rich_safe(x):
   x=x.replace("&", "&amp;")
   x=x.replace("<", "&lt;")
   x=x.replace(">", "&gt;")
   x=x.replace('"', "&quot;")
   return x

def make_cachesafe(arglist, filename):          # modifies mplayer arg list
   bad = [ "ogg", "flac" ]                      # these files will not use -cache option
   ext = os.path.splitext(filename)[1][1:]
   if bad.count(ext):
      try:
         index = arglist.index("-cache")
         del arglist[index]                     # -cache and its parameter are removed
         del arglist[index]                     # so mplayer will start quickly
      except:
         pass                                   # cache option can sometimes be missing


# url_unescape: convert %xx escape sequences in strings to characters.
def url_unescape(text_in):
   output = ""
   double = False
   skip = 0
   for index in range(len(text_in)):
      if double == True:
         double = False
         continue
      if skip:
         skip = skip - 1
         continue
      else:
         if text_in[index] == "%":
            try:
               if text_in[index + 1] == "%":
                  double = True
                  ch = "%"
               else:
                  ch = text_in[index+1:index+3].decode("hex")
                  skip = 2
            except IndexError,TypeError:
               pass
         else:
            ch = text_in[index]
         output = output + ch
   return output

class int_object:               # Putting an int in a class allows its use in a dictionary
   def __init__(self, value = 0):
      self.value = value
   def __str__(self):
      return self.value
   def __int__(self):
      return int(self.value)
   def set_meter_value(self, value):
      self.value = value
      return self.value
   def set_value(self, value):
      self.value = value
      return self.value
   def get_value(self):
      return self.value
   def get_text(self):
      return self.value
   def set_text(self, value):
      self.value = value

def threadslock(f):
   def newf(*args, **kwargs):
      gtk.gdk.threads_enter()
      try:
         r = f(*args, **kwargs)
      finally:
         gtk.gdk.threads_leave()
      return r
   return newf

