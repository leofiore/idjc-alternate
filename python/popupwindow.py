#   popupwindow.py: for when standard gtk tooltips just don't cut it
#   Copyright (C) 2007, 2011 Stephen Fairchild (s-fairchild@users.sourceforge.net)
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

__all__ = ['PopupWindow']


import gobject
import gtk
from .gtkstuff import threadslock


class PopupWindow:
    def message(self, text):
        if self.messages:
            print "PopupWindow:", text
        
    def set_messages(self, boolean):                            # show status messages on the console when true
        self.messages = boolean and True or False
        
    def get_messages(self):
        return self.messages
    
    class new_popup_window(gtk.Window):
        def __init__(self):
            gtk.Window.__init__(self, gtk.WINDOW_POPUP)
            gtk.Window.set_decorated(self, False)
    
    @threadslock
    def timeout_callback(self):
        class bugout:
            def __init__(self, parent, text):
                if parent.popup_window is not None:
                    parent.popup_window.destroy()
                    parent.popup_window = None
                parent.message(text)
        try:
            self.timer_count += 1
            self.total_timer_count += 1
            if self.timer_count == self.popuptime:
                if not self.timeout or self.total_timer_count < self.popuptime + self.timeout:
                    self.popup_window = self.new_popup_window()
                    if self.winpopulate_callback(self.popup_window, self.widget, self.x, self.y) != -1:
                        self.popup_window.realize()
                        # calculate the popup window positioning
                        w_popup = self.popup_window.get_size()[0]     # width of popup window
                        w_root = self.popup_window.get_screen().get_root_window().get_geometry()[2] # width of root window
                        offset = w_root - int(self.x_root) - w_popup - 4
                        if offset > 0:                   # right justify only when needed
                            offset = 0
                        x_pos = int(self.x_root) + 4 + offset
                        if x_pos < 0:                     # cancel right justification for popups that won't fit in the root window
                            x_pos = 0                       # and display against the left edge of the root window
                        self.popup_window.move(x_pos, int(self.y_root) + 4)
                        self.popup_window.show()
                        self.message("popup window created")
                    else:
                        raise bugout(self, "window populate callback returned -1 -- window cancelled")
                else:
                    raise bugout(self, "timeout exceeded")
            if self.timer_count > self.popdowntime:
                raise bugout(self, "popdown time reached")
        except bugout:
            return False
        else:
            return True
    
    def handle_mouse(self, widget, event, data):
        self.timer_count = 0
        self.x_root = event.x_root        # store absolute mouse x and y coordiates
        self.y_root = event.y_root
        self.x = event.x                        # can be used in the callback to obtain context information
        self.y = event.y
        if self.popup_window is not None: # any event triggers destruction of popup windows currently open
            self.popup_window.destroy()
            gobject.source_remove(self.timeout)
            self.popup_window = None
            self.message("popup window destroyed due to the sensing of an event, timer removed")
            if data == "leave": return False
        if data == "enter" and self.inside_widget == False:
            self.timeout = gobject.timeout_add(100, self.timeout_callback)
            self.inside_widget = True
            self.total_timer_count = 0
            self.message("timer started")
        if data == "leave":
            gobject.source_remove(self.timeout)
            self.inside_widget = False
            self.message("timer removed")
        if data == "button" or data == "scroll" or self.inhibit_callback() and self.inside_widget:
            gobject.source_remove(self.timeout)
            self.message("timer removed")
    
    def dummy(self): return False
    
    def __init__(self, widget, popuptime, popdowntime, timeout, winpopulate_callback, inhibit_callback = None):
        self.widget = widget
        self.popuptime = popuptime
        self.popdowntime = popdowntime
        self.timeout = timeout
        self.winpopulate_callback = winpopulate_callback
        self.inhibit_callback = inhibit_callback or self.dummy
        self.popup_window = None
        self.inside_widget = False
        self.messages = False
        self.widget.connect("motion_notify_event", self.handle_mouse, "move")
        self.widget.connect("enter_notify_event", self.handle_mouse, "enter")
        self.widget.connect("leave_notify_event", self.handle_mouse, "leave")
        self.widget.connect("button_press_event", self.handle_mouse, "button")
        self.widget.connect("button_release_event", self.handle_mouse, "button")
        self.widget.connect("scroll_event", self.handle_mouse, "scroll")
