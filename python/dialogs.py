"""Server dialogs for IDJC."""

#   Copyright 2006-2012 Stephen Fairchild (s-fairchild@users.sourceforge.net)
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
import time

import gtk
import pango

from idjc import FGlobs
from idjc.prelims import ProfileManager


import gettext
t = gettext.translation(FGlobs.package_name, FGlobs.localedir, fallback=True)
_ = t.gettext



pm = ProfileManager()



class dialog_group:
    """A mutually exclusive list of dialogs
    
    Only one can be on screen at a time.
    The dialogs below can call the hide method to remove any other dialogs.
    """

    def __init__(self):
        self.dialist = []
    def add(self, newdialog):
        self.dialist.append(newdialog)
    def hide(self, apartfrom = None):
        for each in self.dialist:
            if each is not apartfrom:
                each.hide()

class disconnection_notification_dialog(gtk.Dialog):
    """Used to show a dialog related to the failure of the server connection."""


    def window_attn(self, widget, event):
        if event.new_window_state | gtk.gdk.WINDOW_STATE_ICONIFIED:
            widget.set_urgency_hint(True)
        else:
            widget.set_urgency_hint(False)
    
    def respond(self, dialog, response):
        if response in (gtk.RESPONSE_CLOSE, gtk.RESPONSE_DELETE_EVENT):
            dialog.hide()
    
    def present(self):
        self.dial_group.hide(self)
        gtk.Dialog.present(self)

    def __init__(self, dial_group = None, window_group = None,
                                            window_title = None, text = None):
        if window_title is None:
            window_title = pm.title_extra.strip()
        else:
            window_title += pm.title_extra
        
        gtk.Dialog.__init__(self, window_title, None,
                                        gtk.DIALOG_DESTROY_WITH_PARENT,
                                        (gtk.STOCK_CLOSE, gtk.RESPONSE_CLOSE))
        if window_group is not None:
            window_group.add_window(self)
        self.set_resizable(False)
        self.set_border_width(6)
        self.get_child().set_spacing(12)
        self.connect("close", self.respond)
        self.connect("response", self.respond)
        self.connect("window-state-event", self.window_attn)
        
        hbox = gtk.HBox(False, 20)
        hbox.set_spacing(12)
        self.get_content_area().pack_start(hbox, True, True, 0)
        hbox.show()
        image = gtk.Image()
        image.set_alignment(0.5, 0)
        image.set_from_stock(gtk.STOCK_DISCONNECT, gtk.ICON_SIZE_DIALOG)
        hbox.pack_start(image, False)
        image.show()
        vbox = gtk.VBox()
        hbox.pack_start(vbox, True, True, 0)
        vbox.show()
        
        if text is not None:
            for each in text.splitlines():
                label = gtk.Label(each)
                label.set_use_markup(True)
                label.set_alignment(0.0, 0.5)
                vbox.pack_start(label, False)
                label.show()

        if dial_group is not None:
            dial_group.add(self)
        self.dial_group = dial_group
        # Dialog is not shown upon creation, but rather is (re)shown when needed.



class autodisconnection_notification_dialog(gtk.Dialog):
    """Used to show when autodisconnection is imminent."""


    def window_attn(self, widget, event):
        if event.new_window_state | gtk.gdk.WINDOW_STATE_ICONIFIED:
            widget.set_urgency_hint(True)
        else:
            widget.set_urgency_hint(False)
    
    def respond(self, dialog, response, actionok = None, actioncancel = None):
        if response == gtk.RESPONSE_OK or response == gtk.RESPONSE_DELETE_EVENT:
            if actionok is not None:
                actionok()
        if response == gtk.RESPONSE_CANCEL:
            if actioncancel is not None:
                actioncancel()
        dialog.hide()

    def present(self):
        self.dial_group.hide(self)
        gtk.Dialog.present(self)

    def __init__(self, dial_group = None, window_group = None,
                                    window_title = "", additional_text = None,
                                    actionok = None, actioncancel = None):

        gtk.Dialog.__init__(self, window_title, None,
                        gtk.DIALOG_DESTROY_WITH_PARENT, (gtk.STOCK_CANCEL,
                        gtk.RESPONSE_CANCEL, gtk.STOCK_OK, gtk.RESPONSE_OK))
        if window_group is not None:
            window_group.add_window(self)
        self.set_resizable(False)
        self.connect("close", self.respond, actionok, actioncancel)
        self.connect("response", self.respond, actionok, actioncancel)
        self.connect("window-state-event", self.window_attn)
        self.set_default_response(gtk.RESPONSE_OK)
        
        hbox = gtk.HBox(False, 20)
        hbox.set_border_width(20)
        self.vbox.pack_start(hbox, True, True, 0)
        hbox.show()
        image = gtk.Image()
        image.set_from_stock(gtk.STOCK_DIALOG_WARNING, gtk.ICON_SIZE_DIALOG)
        hbox.pack_start(image, True, True, 0)
        image.show()
        vbox = gtk.VBox()
        vbox.set_spacing(8)
        hbox.pack_start(vbox, True, True, 0)
        vbox.show()
        
        if additional_text is not None:
            if type(additional_text) is str:
                additional_text = additional_text.splitlines()
            for each in additional_text:
                label = gtk.Label()
                attrlist = pango.AttrList()
                attrlist.insert(pango.AttrSize(12500, 0, len(each)))
                label.set_attributes(attrlist)
                label.set_text(each)
                vbox.add(label)
                label.show()
        if dial_group is not None:
            dial_group.add(self)
        self.dial_group = dial_group



class ReconnectionDialog(gtk.Dialog):
    """Displayed when a reconnection is scheduled.
    
    User may expedite or cancel the reconnection operation using this widget.
    """
    
    td = (0.0,)
    # TC: The contents of <> and {} must not be changed.
    lines = _('<span weight="bold" size="12000">The connection to the server '
        'in tab {servertab} has failed.</span>\nA reconnection attempt will'
        ' be made in {countdown} seconds.\nThis is attempt number {attempt}'
        ' of {maxtries}.').splitlines()
    
    def update_countdown_text(self):
        remaining = self.remaining
        self.remaining = int(self.event_time - time.time())
        if self.remaining != remaining:
            self.label2.set_text(self.lines[1].format(countdown=self.remaining))
            if self.remaining == 0:
                self.hide()
                while gtk.events_pending():
                    gtk.main_iteration()
                self.tab.server_connect.set_active(True)
                if self.tab.server_connect.get_active() == False:
                    self.activate()
    
    def run(self):
        if self.active:
            self.update_countdown_text()
    
    def activate(self):
        if not self.tab.troubleshooting.automatic_reconnection.get_active():
            self.deactivate()
            self.tab.scg.disconnected_dialog.present()
            return
        
        if self.active == False:
            self.trycount = 0
            self.td = []
            for each in \
                    self.config.reconnection_times.child.get_text().split(","):
                try:
                    x = max(float(each), 5.0)
                except:
                    x = 5.0
                self.td.append(x)
            self.active = True
        else:
            self.trycount += 1
        
        repeat = self.config.reconnection_repeat.get_active()

        if not repeat and self.trycount >= len(self.td):
            self.deactivate()
            self.tab.scg.disconnected_dialog.present()
            return

        self.remaining = self.td[self.trycount % len(self.td)]

        self.event_time = time.time() + self.remaining
        self.update_countdown_text()
        if repeat:
            self.label3.set_text(_('This is attempt number %d. There is no '
                                        'retry limit.') % (self.trycount + 1))
        else:
            self.label3.set_text(self.lines[2].format(
                        attempt = self.trycount + 1, maxtries = len(self.td)))
        if self.config.reconnection_quiet.get_active():
            self.realize()
        else:
            self.present()
    
    def deactivate(self):
        if self.active:
            self.hide()
            self.active = False

    def cb_response(self, dialog, response):
        if response == gtk.RESPONSE_CANCEL:
            self.deactivate()
        if response == gtk.RESPONSE_OK:
            self.event_time = time.time() + 0.25

    def cb_delete(self, widget, event):
        self.deactivate()
        return True

    def __init__(self, tab):
        self.tab = tab
        gtk.Dialog.__init__(self, pm.title_extra.strip(), None,
                    gtk.DIALOG_DESTROY_WITH_PARENT, (gtk.STOCK_CANCEL,
                    gtk.RESPONSE_CANCEL, _('_Retry Now'), gtk.RESPONSE_OK))
        self.set_modal(False)
        self.set_resizable(False)
        self.set_border_width(6)
        self.vbox.set_spacing(12)
        
        hbox = gtk.HBox()
        hbox.set_spacing(12)
        self.get_content_area().pack_start(hbox, False)
        hbox.show()
        i = gtk.image_new_from_stock(gtk.STOCK_DISCONNECT, gtk.ICON_SIZE_DIALOG)
        i.set_alignment(0.5, 0)
        hbox.pack_start(i, False)
        i.show()

        vbox = gtk.VBox()
        vbox.set_spacing(3)
        hbox.pack_start(vbox, False)
        self.label1 = gtk.Label(self.lines[0].format(
                                        servertab = tab.numeric_id + 1) + "\n")
        self.label1.set_use_markup(True)
        self.label2 = gtk.Label(self.lines[1].format(countdown = 0))
        self.label3 = gtk.Label(self.lines[2].format(attempt = 1, maxtries = 1))
        for l in (self.label1, self.label2, self.label3):
            l.set_alignment(0.0, 0.5)
            vbox.pack_start(l, False)
            l.show()
            
        vbox.show()
            
        self.config = tab.troubleshooting
        self.active = False

        self.connect("delete-event", self.cb_delete)
        self.connect("response", self.cb_response)
