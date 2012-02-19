#   tooltips.py: a replacement for the old style GTK tooltips API
#   Copyright (C) 2008-2011 Stephen Fairchild (s-fairchild@users.sourceforge.net)
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

import gtk



class TooltipsGroup:
    """A central control point for tooltips.""" 

    def __init__(self):
        self.enabled = False


    def set_tip(self, widget, tip_text):
        widget.set_tooltip_window(None)
        widget.connect("query-tooltip", self.cb_query_tooltip, tip_text)
        widget.set_has_tooltip(True)


    def enable(self):
        self.enabled = True


    def disable(self):
        self.enabled = False


    def cb_query_tooltip(self, widget, x, y, keyboard_mode, tooltip, tip_text):
        label = gtk.Label(tip_text)
        label.set_line_wrap(True)
        tooltip.set_custom(label)
        label.show()
        return self.enabled



# An application wide tooltips group.
MAIN_TIPS = TooltipsGroup()


# Global tip setting function.
def set_tip(widget, tip_text):
    MAIN_TIPS.set_tip(widget, tip_text)
