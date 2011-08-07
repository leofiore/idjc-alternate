#   IDJCservdialog.py: Server dialogs for IDJC
#   Copyright (C) 2006 Stephen Fairchild (s-fairchild@users.sourceforge.net)
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


import gettext
t = gettext.translation(FGlobs.package_name, fallback=True)
_ = t.gettext



# A mutually exclusive list of dialogs so that only one can be on screen at a time
# The dialogs below can call the hide method to remove any other dialogs
class dialog_group:
   def __init__(self):
      self.dialist = []
   def add(self, newdialog):
      self.dialist.append(newdialog)
   def hide(self, apartfrom = None):
      for each in self.dialist:
         if each is not apartfrom:
            each.hide()

# Used to show a dialog related to the failure of the server connection
class error_notification_dialog(gtk.Dialog):
   def window_attn(self, widget, event):
      if event.new_window_state | gtk.gdk.WINDOW_STATE_ICONIFIED:
         widget.set_urgency_hint(True)
      else:
         widget.set_urgency_hint(False)
   
   def respond(self, dialog, response):
      if response == gtk.RESPONSE_CLOSE or response == gtk.RESPONSE_DELETE_EVENT:
         dialog.hide()
   
   def present(self):
      self.dial_group.hide(self)
      gtk.Dialog.present(self)

   def __init__(self, dial_group = None, window_group = None, window_title = "", additional_text = None):
      gtk.Dialog.__init__(self, window_title, None, gtk.DIALOG_DESTROY_WITH_PARENT, (gtk.STOCK_CLOSE, gtk.RESPONSE_CLOSE))
      if window_group is not None:
         window_group.add_window(self)
      self.set_resizable(False)
      self.connect("close", self.respond)
      self.connect("response", self.respond)
      self.connect("window-state-event", self.window_attn)
      
      hbox = gtk.HBox(False, 20)
      hbox.set_border_width(20)
      self.vbox.pack_start(hbox, True, True, 0)
      hbox.show()
      image = gtk.Image()
      image.set_from_stock(gtk.STOCK_DIALOG_ERROR, gtk.ICON_SIZE_DIALOG)
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
      # Dialog is not shown upon creation, but rather is (re)shown when needed.


# Used to show when autodisconnection is imminent with the option to cancel
class autodisconnection_notification_dialog(gtk.Dialog):
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

   def __init__(self, dial_group = None, window_group = None, window_title = "", additional_text = None, actionok = None, actioncancel = None):
      gtk.Dialog.__init__(self, window_title, None, gtk.DIALOG_DESTROY_WITH_PARENT, (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, gtk.STOCK_OK, gtk.RESPONSE_OK))
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
      # Dialog is not shown upon creation, but rather is (re)shown when needed.

class ReconnectionDialog(gtk.Dialog):
   td = (0.0, 10.0, 10.0, 60.0)
   
   def update_countdown_text(self):
      remaining = self.remaining
      self.remaining = int(self.event_time - time.time())
      if self.remaining != remaining:
         self.label2.set_text(_('Automatic reconnect in %d seconds.') % self.remaining)
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
      if self.config is None:
         self.config = self.tab.source_client_gui.parent.prefs_window.recon_config
      if self.active == False:
         self.trycount = 1
         if self.config.limited_delays.get_active():
            self.limited_delays = True
            self.td = [0.0]
            for each in self.config.csl.get_text().split(","):
               try:
                  x = float(each)
               except:
                  pass
               else:
                  if x >= 1.0:
                    self.td.append(x)
         else:
            self.limited_delays = False
         self.active = True
      else:
         self.trycount += 1
      
      if self.limited_delays:
         if self.trycount >= len(self.td):
            self.deactivate()
            self.tab.scg.disconnected_dialog.present()
            return
         else:
            self.remaining = self.td[self.trycount]
      else:
         self.remaining = 5.0
      self.event_time = time.time() + self.remaining
      self.update_countdown_text()
      if self.limited_delays:
         # Read as: attempt number x of y total possible attempts.
         text = _('Try {0} of {1}.')
         self.label3.set_text(text.format(self.trycount, len(self.td) - 1))
      else:
         self.label3.set_text(_('Try %d.') % self.trycount)
      if self.config.visible.get_active():
         self.present()
      else:
         self.realize()
   
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
      gtk.Dialog.__init__(self, _('Connection Lost'), None, gtk.DIALOG_DESTROY_WITH_PARENT, (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, _('Try Now'), gtk.RESPONSE_OK))
      self.set_resizable(False)
      
      self.vb = gtk.VBox() # bug workaround
      self.vbox.pack_start(self.vb)
      self.vb.show()
      self.vb.set_border_width(10)
      self.vb.set_spacing(10)
      
      self.connect("delete-event", self.cb_delete)
      self.connect("response", self.cb_response)
      
      self.label1 = gtk.Label(_('The connection to the server in tab %s has failed.') % (tab.numeric_id + 1))
      self.label2 = gtk.Label(_('Automatic reconnect in %d seconds.') % self.td[1])
      text = _('Try {0} of {1}.')
      self.label3 = gtk.Label(text.format(1, len(self.td) - 1))
      for each in (self.label1, self.label2, self.label3):
         attrlist = pango.AttrList()
         attrlist.insert(pango.AttrSize(12500, 0, len(each.get_text())))
         each.set_attributes(attrlist)
         self.vb.add(each)
         each.show()
      
      self.config = None   # unavailable just yet
      self.active = False
