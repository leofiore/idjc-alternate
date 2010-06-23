#   tooltips.py: a tooltips widget that works? see comments below
#   Copyright (C) 2008 Stephen Fairchild (s-fairchild@users.sourceforge.net)
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
pygtk.require('2.0')
import gtk
from idjc_config import tipsenabled

# PyGTK 2.12 is currently an unstable release. This module uses new functionality
# which at present does not allow for the complete blocking of tooltips due to
# an apparrent deficiency in the underlying GTK code. 
# Tooltips can be completely blocked by setting tipsenabled = 0 in idjc_config.py

# According to the API cb_query_tooltip is to return False to block tooltips
# and True to allow them however the reverse functionality is present.
# I have decided to program to the API in the hope this problem will resolve itself

# gtk.Tooltips functionality has been duplicated here due to a bug in 2.12
# where old style tooltips can not be disabled.

if tipsenabled == False:
   class Tooltips:                  # a dummy tooltips class
      def enable(self):
         pass
      def disable(self):
         pass
      def set_tip(self, widget, tip_text, tip_private = None):
         pass
      def __init__(self):
         self.dummy = True
else:
   try:
      gtk.Widget.set_tooltip_text   # determine the presence of new tooltip API
   except AttributeError:
      class Tooltips(gtk.Tooltips): # fall back to using the old tooltips API
         def __init__(self):
            gtk.Tooltips.__init__(self)
            self.dummy = False
   else:
      class Tooltips:               # use the new tooltip API where possible
         def cb_query_tooltip(self, widget, x, y, keyboard_mode, tooltip):
            #print "returning", not self.enabled
            return not self.enabled # see also bug 519517
         def enable(self):
            self.enabled = True
         def disable(self):
            self.enabled = False
         def set_tip(self, widget, tip_text, tip_private = None):
            widget.set_tooltip_text(tip_text)
            widget.connect("query-tooltip", self.cb_query_tooltip)
         def __init__(self):
            self.enabled = False
            self.dummy = False
