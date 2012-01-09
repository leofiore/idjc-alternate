#   IDJCjingles.py: The jingles player GUI code for IDJC
#   Copyright (C) 2005, 2011 Stephen Fairchild (s-fairchild@users.sourceforge.net)
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



__all__ = ['Jingles']



import os
import gettext

import gobject
import gtk
import pango

from idjc import *
from .freefunctions import *
from .gtkstuff import WindowSizeTracker
from .prelims import *
from .tooltips import main_tips


t = gettext.translation(FGlobs.package_name, FGlobs.localedir, fallback=True)
_ = t.gettext

pm = ProfileManager()
set_tip = main_tips.set_tip



class Jingles(object):
   NORMAL = 70  # Target level for hightest main player fader.

   def cleanup(self):
      self.stop.clicked()
      self.interlude.set_active(False)
   
   def cb_doubleclick(self, treeview, path, column, user_data):
      if self.entry.flags() & gtk.SENSITIVE:
         new_text = str(self.liststore[path[0]][0])
         existing_text = self.entry.get_text()
         if existing_text != "":
            self.entry.set_text(existing_text + "," + new_text)
         else:
            self.entry.set_text(new_text)        
         
   def callback(self, widget, data):
      if data == "entrybox":
         self.play.set_active(True)
         
      if data == "Refresh":
         self.load_jingles()
         self.entry.set_text("")
         iter = self.liststore.get_iter_first()
         if iter != None:
            self.treeview.get_selection().select_iter(iter)
      
      if data == "Play":
         if self.ex_is_playing and widget.get_active() == True:
            widget.set_active(False)
         elif self.is_playing and widget.get_active() == False:
            if self.stopping == False:
               widget.set_active(True)
            else:
               self.stop_player()
               self.stopping = self.is_playing = False
         elif self.is_playing == False and widget.get_active() == True:
            self.is_playing = self.start_player(False)
            if self.is_playing == False:
               widget.set_active(False)
 
      if data == "PlayEx":
         if self.is_playing and widget.get_active() == True:
            widget.set_active(False)
         elif self.ex_is_playing and widget.get_active() == False:
            if self.stopping == False:
               widget.set_active(True)
            else:
               self.stop_player()
               self.stopping = self.ex_is_playing = False
         elif self.ex_is_playing == False and widget.get_active() == True:
            self.ex_is_playing = self.start_player(True)
            if self.ex_is_playing == False:
               widget.set_active(False)

      if data == "Stop":
         if self.play.get_active():
            self.stopping = True
            self.play.set_active(False)
         if self.play_ex.get_active():
            self.stopping = True
            self.play_ex.set_active(False)
         self.entry.set_text("")

   def get_playlist_from_entry(self):
      arglist = []
      numericlist = self.entry.get_text().split(",")
      for each in numericlist:
         if each.count("-") == 0:
            try:
               arglist.append(pm.jinglesdir / self.liststore[int(each)-1][1])
            except:
               pass
         elif each.count("-") == 1:
            fromto = each.split("-")
            try:
               start = int(fromto[0]) -1
            except:
               start = 0
            try:
               end = int(fromto[1]) -1
            except:
                  end = 1000000
            while start <= end:
               try:
                  arglist.append(pm.jinglesdir / self.liststore[start][1])
               except:
                  break;
               start = start + 1
      if arglist == []:
         return None
      return arglist
         
   def pack_playlistlist(self, playlist):
      output = str(len(playlist)) + '#'
      for each in playlist:
         output += "d" + str(len(each)) + ":" + each
      return output 
 
   def start_player(self, which):
      self.nomute = not self.parent.mic_opener.any_mic_selected and self.parent.mixermode == self.parent.PRIVATE_PHONE
      if self.entry.get_text() == "":
         selection = self.treeview.get_selection()
         model, iter = selection.get_selected()
         if iter != None:
            self.entry.set_text(str(model.get_value(iter, 0)))
         else:
            self.stop.clicked()
      playlist = self.get_playlist_from_entry()
      if playlist is not None:
         self.playing = True
         if self.nomute == False:
            self.volume1 = self.parent.deckadj.get_value()
            self.volume2 = self.parent.deck2adj.get_value()
            self.interludevolume = self.interadj.get_value()
            self.lvl = self.m1.get_value() if which == 0 else self.m2.get_value()
            #for each in (self.interadj, self.parent.deckadj, self.parent.deck2adj):
            #   each.set_value(lvl)
            self.interadj.set_value(min(self.lvl, self.interludevolume))
               
            # Normalise main player volume to lvl on the highest of the two player volume levels
            # have the lower of the two levels track the higher value.
            # Where the highest volume level is below the normal level do nothing to the level.
            # When the jingles player is done the volume levels are restored.
            
            if self.parent.prefs_window.dual_volume.get_active():
               highest = max((self.volume1, self.volume2))
            else:
               highest = self.volume2 = self.volume1
              
            delta = min((self.lvl - highest, 0)) 
            self.parent.deckadj.set_value(self.volume1 + delta)
            self.parent.deck2adj.set_value(self.volume2 + delta)

         self.parent.deckadj.value_changed()
         string_to_send = "VOL2=%d\nLOOP=0\nPLPL=%s\nACTN=playmanyjingles\nend\n" % (self.play_ex.get_active(), self.pack_playlistlist(playlist))
         self.parent.mixer_write(string_to_send, True)
         
         while 1:
            line = self.parent.mixer_read()
            if line.startswith("context_id="):
               self.player_cid = int(line[11:-1])
               break
            if line == "":
               self.player_cid = -1
               break
         if self.player_cid == -1:
            self.playing = False
            print "player startup was unsuccessful for files", playlist
            return False
         print "player context id is %d\n" % self.player_cid
         self.entry.set_sensitive(False)
         return True
      else:
         self.playing = False
         return False
   
   def stop_player(self, flush = True):
      if self.playing:
         self.playing = False
         self.entry.set_sensitive(True)
         print "Stop player"
         if flush == True:
            print "stop with flush"
            self.parent.mixer_write("ACTN=stopjingles\nend\n", True)
         else:
            print "stop without flush"
            self.stop.clicked() # this will take care of resetting the play button without triggering a flush
         if self.nomute == False:
            # Don't move the level if user moved it upwards.
            v1 = self.parent.deckadj.get_value()
            v2 = self.parent.deck2adj.get_value()
            if max((v1, v2)) <= self.lvl:
               self.parent.deckadj.set_value(self.volume1)
               self.parent.deck2adj.set_value(self.volume2)
            self.interludevolume = max(self.interludevolume, self.interadj.get_value())
            self.interadj.set_value(self.interludevolume)
         else:
            self.parent.send_new_mixer_stats()
         
   def delete_event(self, widget, event, data=None):
      self.window.hide()        # We don't really destroy the window
      return True
   
   def load_jingles(self):
      if not os.path.isdir(pm.jinglesdir):
         os.mkdir(pm.jinglesdir)
      files = os.listdir(pm.jinglesdir)
      count = 0
      self.liststore.clear()
      for each in files:        # files will be added with alpha numeric sorting
         if each == self.interlude_song:
            self.liststore.append([ count, each, "<b>" + rich_safe(each) + "</b>" ])
         else:
            self.liststore.append([ count, each, rich_safe(each) ])
         count = count + 1
      i = 0
      while i < count:          # reorders the item numbers on the left column
         self.liststore[i][0] = i+1
         i = i + 1
      
   def alphanumeric_sort(self, model, iter1, iter2):
      data1 = model.get_value(iter1, 1)
      data2 = model.get_value(iter2, 1)
      if data1 == data2:
         return 0
      if data1 > data2:
         return 1
      return -1
   
   def cb_deckvol(self, widget):
      self.parent.send_new_mixer_stats()
      
   def cb_intervol(self, widget):
      self.parent.send_new_mixer_stats()
      
   def start_interlude_player(self, pathname):
      self.interlude_player_track = pathname
      string_to_send = "LOOP=1\nPLPL=%s\nACTN=playmanyinterlude\nend\n" % self.pack_playlistlist([pathname,])
      print "string to send is:-"
      self.parent.mixer_write(string_to_send, True)
      while 1:
         line = self.parent.mixer_read()
         if line.startswith("context_id="):
            self.interlude_cid = int(line[11:-1])
            break
         if line == "":
            self.interlude_cid = -1
            break
      if self.interlude_cid == -1:
         self.interlude_playing = False
         print "interlude player startup was unsuccessful for", pathname
         self.interlude.set_active(False)
      else:
         self.interlude_playing = True
      
   def stop_interlude_player(self):
      self.interlude_player_track = ""
      if self.interlude_playing == True:
         self.interlude_playing = False
         self.parent.mixer_write("ACTN=stopinterlude\nend\n", True)
      
   def cb_interlude(self, widget, treeview):
      if widget.get_active():
         if self.interlude_playing:
            return
         treeselection = treeview.get_selection()
         model, iter = treeselection.get_selected()
         if iter == None:
            widget.set_active(False)
            print "Can't start interlude player.  No file is selected."
            return
         path = pm.jinglesdir / model.get_value(iter, 1)
         if os.path.isfile(path) == False:
            widget.set_active(False)
            print "Can't start the interlude player, the file", path, "is missing."
            return
         self.start_interlude_player(path)
         if self.interlude_playing:
            model.set_value(iter, 2, '<b>' + model.get_value(iter, 2) + '</b>')
            self.interlude_song = model.get_value(iter, 1)
            print "Starting the interlude player"
         else:
            print "Failed to start the interlude player"
      else:
         if self.interlude_playing:
            intertrack = os.path.split(self.interlude_player_track)[1]
            for each in self.liststore:
               item = str(each[2])
               if item[0]=="<":
                  each[2] = item[3:-4]
                  self.interlude_song = ""
                  break
               elif item == intertrack:
                  self.interlude.set_active(True)
                  each[2] = "<b>" + intertrack + "</b>"
                  self.interlude_song = intertrack
                  return
            else:
               print "The interlude file is missing from the list."
            print "Shutting down the interlude player"
            self.stop_interlude_player()
            
   def trigger_index(self, index):
      if index == -1:
         if self.playing:
            self.stop.clicked()
            self.entry.set_text("1")
            self.play.set_active(True)
            self.stop.clicked()
         return
      if index < len(self.liststore):
         self.trigger_index(-1)
         self.entry.set_text(str(index + 1))
         self.play.set_active(True)

   def __init__(self, parent):
      self.parent = parent
      self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
      self.parent.window_group.add_window(self.window)
      # TC: Window title.
      self.window.set_title(_('IDJC Jingles') + pm.title_extra)
      self.window.set_destroy_with_parent(True)
      self.window.set_border_width(8)
      self.window.connect("delete_event", self.delete_event)
      self.window.add_events(gtk.gdk.KEY_PRESS_MASK)
      self.window.connect("key-press-event", parent.cb_key_capture)
      self.window.connect("key-release-event", parent.cb_key_capture)
      self.wst = WindowSizeTracker(self.window)
      
      attrlist = pango.AttrList()
      attrlist.insert(pango.AttrSize(8000, 0, 100))

      hbox = gtk.HBox()
      hbox.set_spacing(8)

      # A vertical box for our volume and muting controls
      self.vboxvol = gtk.VBox()
      self.vboxvol.set_spacing(4)
      self.vboxvol.set_border_width(0)
      hbox.pack_end(self.vboxvol, False)
      self.vboxvol.show()

      bhbox = gtk.HBox()
      bhbox.set_spacing(2)
      pixbuf = gtk.gdk.pixbuf_new_from_file_at_size(
                        FGlobs.pkgdatadir / "play2.png", 14, 14)
      image = gtk.Image()
      image.set_from_pixbuf(pixbuf)
      self.play = gtk.ToggleButton()
      self.play.set_size_request(40, -1)
      self.play.add(image)
      image.show()
      self.play.connect("toggled", self.callback, "Play")
      bhbox.pack_start(self.play)
      self.play.show()
      set_tip(self.play, _('Play the jingles sequence specified above or if none is specified play the jingle highlighted in the catalogue. The volume level of the main media players will be reduced somewhat during playback.'))

      image = gtk.image_new_from_file(FGlobs.pkgdatadir / "stop.png")
      self.stop = gtk.Button()
      self.stop.set_size_request(40, -1)
      self.stop.add(image)
      image.show()
      self.stop.connect("clicked", self.callback, "Stop")
      bhbox.pack_start(self.stop)
      self.stop.show()
      set_tip(self.stop, _('Stop all jingles playback.'))
      
      pixbuf = gtk.gdk.pixbuf_new_from_file_at_size(
                        FGlobs.pkgdatadir / "play2.png", 14, 14)
      image = gtk.Image()
      image.set_from_pixbuf(pixbuf)
      self.play_ex = gtk.ToggleButton()
      self.play_ex.set_size_request(40, -1)
      self.play_ex.add(image)
      image.show()
      self.play_ex.connect("toggled", self.callback, "PlayEx")
      bhbox.pack_start(self.play_ex)
      self.play_ex.show()
      set_tip(self.play_ex, _('This button works the same as the button to the left does except that the sound level of all the other media players is fully reduced.'))
      self.vboxvol.pack_start(bhbox, False)
      bhbox.show()
     
      label = gtk.Label(_('Sound Level'))
      self.vboxvol.pack_start(label, False)
      label.show()
      
      bhbox = gtk.HBox()
      
      self.l1_adj = gtk.Adjustment(100.0, 0.0, 100.0, 1.0, 6.0, 0.0)
      self.l2_adj = gtk.Adjustment(100.0, 0.0, 100.0, 1.0, 6.0, 0.0)
      self.l1 = gtk.VScale(self.l1_adj)
      self.l2 = gtk.VScale(self.l2_adj)
      
      for l in (self.l1, self.l2):
         l.set_inverted(True)
         l.set_draw_value(False)
         l.connect("value-changed", self.cb_deckvol)
         bhbox.pack_start(l)
         l.show()
      
      self.vboxvol.pack_start(bhbox)
      bhbox.show()
                
      label = gtk.Label(_('Player Muting'))
      self.vboxvol.pack_start(label, False)
      label.show()

      bhbox = gtk.HBox()          

      self.m1_adj = gtk.Adjustment(70.0, 0.0, 100.0, 1.0, 6.0, 0.0)
      self.m2_adj = gtk.Adjustment(0.0, 0.0, 100.0, 1.0, 6.0, 0.0)
      self.m1 = gtk.VScale(self.m1_adj)
      self.m2 = gtk.VScale(self.m2_adj)
      
      for l in (self.m1, self.m2):
         l.set_inverted(True)
         l.set_draw_value(False)
         bhbox.pack_start(l)
         l.show()
                
      self.vboxvol.pack_start(bhbox)
      bhbox.show()
                
           # A vertical box for our second volume control
      self.vboxinter = gtk.VBox()
      self.vboxinter.set_border_width(0)
      hbox.pack_end(self.vboxinter, False, False, 0)
           
      # A pictoral volume label

      pixbuf = gtk.gdk.pixbuf_new_from_file_at_size(
                           FGlobs.pkgdatadir / "interlude2.png", 24, -1)
      image = gtk.image_new_from_pixbuf(pixbuf)
      self.interlude = gtk.ToggleButton()
      self.interlude.add(image)
      image.show()
      self.interlude.show()
      # TC: {0}, {1} = Monitor Mix, Stream.
      # TC: Or whatever they become translated to.
      set_tip(self.interlude, _("When you click this button the jingle or track selected in the catalogue will be looped continuously and will be audible during moments when the main media players are not active. The '{0}' feature needs to be set to '{1}' if you want to be able to hear it.".format(_("Monitor Mix"), _("Stream"))))
      self.vboxinter.pack_start(self.interlude, False)
      
      self.interadj = gtk.Adjustment(65.0, 0.0, 100.0, 1.0, 6.0, 0.0)
      self.interadj.connect("value_changed", self.cb_intervol)
      self.intervol = gtk.VScale(self.interadj)
      self.intervol.set_inverted(True)
      self.intervol.set_update_policy(gtk.UPDATE_CONTINUOUS)
      self.intervol.set_digits(1)
      self.intervol.set_value_pos(gtk.POS_TOP)
      self.intervol.set_draw_value(False)
      self.vboxinter.pack_start(self.intervol, True, True, 0)
      self.intervol.show()
      self.vboxinter.show()
      # TC: For context {0} and {1} refer to Monitor Mix and Stream.
      # TC: They are extracted to force consistency. 
      set_tip(self.intervol, _("This adjusts the volume level of the music that plays whenever the other media players are not active. It is only audible to the DJ when '{0}' in the main application window is set to '{1}'.").format(_("Monitor Mix"), _("Stream")))
                
      vbox = gtk.VBox()
      vbox.set_spacing(6)
      vbox.set_border_width(0)
      self.window.add(hbox)
      hbox.pack_start(vbox, True, True, 0)
      vbox.show()
      hbox.show()
      
      # Make a scrolled window with a 2 column list
      scrolllist = gtk.ScrolledWindow()
      scrolllist.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_ALWAYS)
      scrolllist.set_border_width(0)
      scrolllist.set_shadow_type(gtk.SHADOW_IN)
      scrolllist.set_size_request(270, 240)   
      
      self.liststore = gtk.ListStore(int, str, str)
      self.treeview = gtk.TreeView(self.liststore)
      self.treeview.set_headers_visible(False)  
      self.treeview.connect("row_activated", self.cb_doubleclick, "Double click") 
      
      self.digicellrender = gtk.CellRendererText()
      self.digitvcolumn = gtk.TreeViewColumn("Numbers", self.digicellrender)
      self.digitvcolumn.add_attribute(self.digicellrender, 'text', 0)
      self.treeview.append_column(self.digitvcolumn)
      
      self.filecellrender = gtk.CellRendererText()
      self.filetvcolumn = gtk.TreeViewColumn("Filenames", self.filecellrender)
      self.filetvcolumn.add_attribute(self.filecellrender, 'markup', 2)
      
      self.treeview.append_column(self.filetvcolumn)
      
      self.liststore.set_sort_func(0, self.alphanumeric_sort)
      self.liststore.set_sort_column_id(0, gtk.SORT_ASCENDING)      
      
      scrolllist.add(self.treeview)
      self.treeview.show()
      vbox.pack_start(scrolllist, True, True, 1)
      scrolllist.show()
      # TC: {0}, {1} = Add To Jingles, Item.
      # TC: Or whatever they get translated to.
      set_tip(scrolllist, _('The jingles catalogue.\n\nFrom a main media player tracks can be exported here by right clicking on the playlist entry and selecting {0} from the {1} submenu.\n\nThe jingles catalogue can also be managed by modifying the contents of the \'{2}\' directory directly.'.format(_("Add To Jingles"), _("Item"), pm.jinglesdir)))
      
      hbox = gtk.HBox()
      hbox.set_spacing(4)
      hbox.set_border_width(0)
      
      # TC: Refers to a list of track numbers to play.
      lvbox = gtk.VBox()
      lvbox.set_spacing(1)
      label = gtk.Label(_('Sequence'))
      label.set_attributes(attrlist)
      lvbox.pack_start(label, False)
      label.show()
      
      self.entry = gtk.Entry(45)
      self.entry.connect("activate", self.callback, "entrybox")
      self.entry.set_width_chars(10)
      lvbox.pack_start(self.entry)
      self.entry.show()
      set_tip(self.entry, _('Select multiple jingles to play in sequence by entering the corresponding index number as part of a comma separated list, or double click entries in the catalogue to append them.'))
      hbox.pack_start(lvbox)
      lvbox.show()

      self.refresh = gtk.Button()
      image = gtk.image_new_from_stock(gtk.STOCK_REFRESH, gtk.ICON_SIZE_BUTTON)
      self.refresh.set_image(image)
      image.show()
      self.refresh.connect("clicked", self.callback, "Refresh")
      hbox.pack_start(self.refresh, False)
      self.refresh.show()
      set_tip(self.refresh, _("Cause the jingles catalogue to be refreshed. This is for when items have been added or removed from the jingles directory located at '%s'." % pm.jinglesdir))
      
      vbox.pack_start(hbox, False, False, 0)
      hbox.show()
      
      self.interlude.connect("toggled", self.cb_interlude, self.treeview)
      
      vbox.show()

      self.stopping = False
      self.player_pid = 0
      self.flush = False
      self.interludeflush = False
      self.is_playing = False
      self.ex_is_playing = False
      self.playing = False
      self.interlude_pid = 0
      self.interlude_song= ""
      self.interlude_playing = False
      self.load_jingles()
      self.interlude_player_track = ""
