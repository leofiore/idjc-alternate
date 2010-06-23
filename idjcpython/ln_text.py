#   ln_text.py: localisation support for IDJC
#   Copyright (C) 2010 Stephen Fairchild (s-fairchild@users.sourceforge.net)
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

__all__ = ['ln']

import os, sys

def _get_modulename(cls):
   return cls.__name__ + "_text"

class xx_XX(object):
   def __getattr__(self, name):
      """Setting the LANG environment variable to xx_XX will result in all the item labels handled by this module being set by this method. This feature provides the language translator with a context for the item lables themselves."""
      if name[0] != "_":
         print "*** ln_text.py: warning, missing attribute '%s'" % name
         if self._warning == False:
            print "this and other missing attribute warnings will only appear once"
            self._warning = True
         setattr(self, name, "((%s))" % name)   # prevent duplicate warnings
         return getattr(self, name)
   def _load_text(self, cls):
      """The regular __import__ function will not dump multiple references from a module into a class necessitating the following code."""
      modulename = _get_modulename(cls)
      #print "loading attributes from %s for %s" % (modulename, cls.__name__)
      mod = __import__(modulename)
      for item in dir(mod):
         if item[0] != "_":
            setattr(cls, item, getattr(mod, item))
   def _detect_mismatched_references(self, cls):
      def no_underscore(s):
         return s[0] != "_"
      cls_vars = vars(cls)
      for reference in filter(no_underscore, dir(self)):
         if not reference in cls_vars:
            print "### ln_text.py: warning, attribute %s does not appear in the canonical list %s" % (reference, cls.__name__)
   def __str__(self):
      return "Language translation: " + self.__class__.__name__
   def __init__(self):
      self._warning = False
      for cls in self.__class__.mro():
         if cls is not xx_XX:
            if cls._load == True:
               self._load_text(cls)
            if cls.__base__ is xx_XX:
               self._detect_mismatched_references(cls)
         else:
            break
      if os.getenv("LANG") == "xx_XX":       # convert to a valid locale
         os.environ["LANG"] = "en_GB"

class en_GB(xx_XX):
   _load = True

class en_US(en_GB):
   _load = True

class de_DE(en_GB):
   _load = True
   
def _set():               # choose which translation to use
   lev = os.getenv("LANG")
   try:
      language = lev[0:2].lower()
      country  = lev[3:5].upper()
      if lev[2] != "_":
         raise IndexError
   except (IndexError,TypeError):
      print "Selecting language en_US. Change environment variable LANG to override."
      lev = "en_US"
   else:
      lev = "_".join((language, country))
   
   gns = sys.modules[__name__]      # the global name space
   # make sure lev matches one of the available languages
   if not lev in dir(gns):
      for each in dir(gns):
         if each[:2] == language:
            print "Compromise language match found", each
            lev = each
            break
      else:
         print "Could not find a suitable language match - will use en_US"
         lev = "en_US"

   # find the class whose name matches the lev variable and instantiate it
   return getattr(gns, lev)()

# set the ln (localisation) variable which is what the calling module should import 
ln = _set()

if __name__ == "__main__":
   def _cleanlist(module):
      return [ l for l in dir(module) if l[0] != "_" ]

   def sort(cls, basecls = en_GB):
      header = (
"""# -*- encoding: utf-8 -*-
#   Set your text editor to UTF-8 before modifying this file

#   %s: IDJC language localisation file for %s
%s
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
#   If not, see <http://www.gnu.org/licenses/>\n\n""")

      try:
         trans = __import__(_get_modulename(cls))
      except:
         print "Import failed. Try creating the empty file %s and try again." % (_get_modulename(cls) + ".py")
         sys.exit(5)
      base  = __import__(_get_modulename(basecls))
      translist = _cleanlist(trans)
      
      def matching(item):
         return getattr(trans, item) == getattr(base, item)
      
      def write_items(file, module, attrlist, prepend = ""):
         for attr in attrlist:
            file.write("".join((prepend, attr, " = ")))
            data = getattr(module, attr)
            if type(data) == tuple:
               file.write(str(data))
            if type(data) == str:
               escdata = data.replace('"', '\"')
               if '\n' in data:
                  if prepend:
                     escdata = escdata.replace('\n', '\n#')
                  file.write(escdata.join(('"""', '"""')))
               else:
                  file.write(escdata.join(('"', '"')))
            file.write("\n\n")

      def stretch(text):
         return " ".join(text)

      baselist = _cleanlist(base)
      unmatched = [ r for r in translist if not r in baselist ]
      regular = []
      untranslated = []
      for baseitem in baselist:
         if trans != base and (not baseitem in translist or matching(baseitem)):
            untranslated.append(baseitem)
         else:
            regular.append(baseitem)
      if "translationcopyright" in translist:
         transcopyright = getattr(trans, "translationcopyright")
         if type(transcopyright) == str:
            transcopyright = (transcopyright, )
      else:
         transcopyright = ("Copyright (C) 2008 Stephen Fairchild (s-fairchild@users.sourceforge.net)", )
      copyrights = "#   " + "\n#   ".join(transcopyright)
      filename = _get_modulename(cls) + ".py"
      file = open(filename, "w")
      file.write(header % (filename, cls.__name__, copyrights))
      if unmatched:
         file.write(stretch("# Items with no match in %s\n\n" % (_get_modulename(basecls) + ".py")))
         write_items(file, trans, unmatched)
      if regular:
         if trans != base:
            file.write(stretch("# The following are regular translations\n\n"))
         write_items(file, trans, regular)
      if untranslated:
         file.write(stretch("# Untranslated items -- same as %s\n\n" % basecls.__name__))
         write_items(file, base, untranslated, "#")
      print "Sort of %s complete." % filename
      sys.exit(0)
   print "Use the sort() function to neatly arrange the translatable items.\n"
   print "Example usage:\n"
   print ">>> sort(fr_FR)"
   print "Untranslated items will be in British English for translation into French"
   print "The file fr_FR_text.py file needs to exist beforehand even if empty.\n"
   print ">>> sort(de_DE, fr_FR)"
   print "Untranslated items will be in French for translation into German."
   print "This assumes there is a French translation in the first place.\n"
   print "Choose one or two of:", [ s[1].__name__ for s in locals().items() if type(s[1]) == type and s[1] is not xx_XX and issubclass(s[1], xx_XX) ]
   print "To add a language/country code you'll need to edit ln_text.py"
   print "\nIt is quite safe to run this over files that have already been translated.\nCtrl+D quits."
