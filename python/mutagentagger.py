#!/usr/bin/python

#   mutagengui.py: GTK based file tagger.
#   Copyright (C) 2009 Stephen Fairchild (s-fairchild@users.sourceforge.net)
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


__all__ = ['MutagenGUI']

import os
import sys
import string
import re
import pango

import gtk
import mutagen
import mutagen.id3 as id3
from mutagen.mp3 import MP3
from mutagen.apev2 import APEv2, APETextValue
from mutagen.musepack import Musepack
from mutagen.monkeysaudio import MonkeysAudio
from mutagen.asf import ASF, ASFUnicodeAttribute

from idjc import FGlobs
from .freefunctions import *
from .ln_text import ln

def set_tip(*args):
   """Dummy tooltips setter."""
   
   pass


class LeftLabel(gtk.HBox):
   """Use in place of gtk.Label where left justification is needed."""
   
   def __init__(self, text):
      gtk.HBox.__init__(self)
      self.label = gtk.Label(text)
      self.pack_start(self.label, False, False, 0)


class RightLabel(gtk.HBox):
   """Use in place of gtk.Label where right justification is needed."""
   
   def __init__(self, text):
      gtk.HBox.__init__(self)
      self.pack_end(gtk.Label(text), False, False, 0)


class FreeTagFrame(gtk.Frame):
   def __init__(self):
      gtk.Frame.__init__(self)
      sw = gtk.ScrolledWindow()
      sw.set_border_width(5)
      sw.set_policy(gtk.POLICY_NEVER, gtk.POLICY_ALWAYS)
      self.add(sw)
      sw.show()
      self.tb = gtk.TextBuffer()
      tv = gtk.TextView(self.tb)
      tv.set_wrap_mode(gtk.WRAP_CHAR)
      tv.modify_font(pango.FontDescription('sans 12'))
      sw.add(tv)
      tv.show()


class MutagenTagger(gtk.VBox):
   """Base class for ID3Tagger and NativeTagger."""
   
   def __init__(self, pathname):
      gtk.VBox.__init__(self)
      self.pathname = pathname

class WMATagger(MutagenTagger):
   """Handles tagging of WMA files"""
   
   primary_data = ("Title", "Author")
   secondaries = ("WM/AlbumTitle", "WM/AlbumArtist", "WM/Year", "WM/Genre")
   
   def save_tag(self):
      """Updates the tag with the GUI data."""
       
      tag = self.tag
      tb = self.tag_frame.tb
       
      for key in self.text_set:
         try:
            del tag[key]
         except KeyError:
            pass

      for each in self.primary_line:
         val = each[1].get_text().strip()
         if val:
            tag[each[0]] = val
         else:
            try:
               del tag[each[0]]
            except KeyError:
               pass
             
      lines = tb.get_text(tb.get_start_iter(), tb.get_end_iter()).splitlines()
      for line in lines:
         try:
            key, val = line.split("=", 1)
         except ValueError:
            continue
         else:
            key = key.strip()
            val = val.strip()
            if val:
               try:
                  tag[key] += [ASFUnicodeAttribute(val.decode("utf-8"))]
               except (KeyError, AttributeError):
                  try:
                     tag[key] = [ASFUnicodeAttribute(val.decode("utf-8"))]
                  except KeyError:
                     print "Unacceptable key", key
      tag.save()
   
   def load_tag(self):
      """(re)Writes the tag data to the GUI."""
      
      tag = self.tag
      
      for each in self.primary_line:
         try:
            data = tag[each[0]]
         except KeyError:
            pass
         else:
            each[1].set_text("/".join(unicode(y) for y in data))

      additional = []

      for key in self.secondaries:
         values = tag.get(key, [ASFUnicodeAttribute("")])
         for val in values:
            additional.append(key.encode("utf-8") + "=" + unicode(val).encode("utf-8"))

      for key in self.text_set:
         if key not in self.primary_data and key not in self.secondaries:
            values = tag[key]
            for val in values:
               additional.append(key.encode("utf-8") + "=" + unicode(val).encode("utf-8"))
      
      self.tag_frame.tb.set_text("\n".join(additional))
   
   def __init__(self, pathname):
      MutagenTagger.__init__(self, pathname)
      try:
         self.tag = mutagen.asf.ASF(pathname)
         if not isinstance(self.tag, mutagen.asf.ASF):
            raise mutagen.asf.error
      except mutagen.asf.error:
         print "Not a real wma/asf file apparently."
         self.tag = None
         return
         
      hbox = gtk.HBox()
      hbox.set_border_width(5)
      hbox.set_spacing(8)
      self.pack_start(hbox, False, False, 0)
      vbox_text = gtk.VBox()
      hbox.pack_start(vbox_text, False, False, 0)
      vbox_entry = gtk.VBox()
      hbox.pack_start(vbox_entry, True, True, 0)
      
      self.primary_line = []
      for text, entry in ((x, gtk.Entry()) for x in self.primary_data):
         self.primary_line.append((text, entry))
         vbox_text.add(LeftLabel(text))
         vbox_entry.add(entry)
      hbox.show_all()

      self.tag_frame = FreeTagFrame()
      self.tag_frame.set_border_width(5)
      self.add(self.tag_frame)
      self.tag_frame.show()

      self.text_set = []

      for key, val in self.tag.iteritems():
         if key not in self.primary_line and all(isinstance(v, (ASFUnicodeAttribute, unicode)) for v in val):
            self.text_set.append(key)


class ID3Tagger(MutagenTagger):
   """ID3 tagging with Mutagen."""
   
   primary_data = (("TIT2", ln.id3title), ("TPE1", ln.id3artist),
                   ("TALB", ln.id3album), ("TRCK", ln.id3track),
                   ("TCON", ln.id3genre), ("TDRC", ln.id3recorddate))
   
   def save_tag(self):
      """Updates the tag with the GUI data."""
      
      tag = self.tag
      
      # Remove all text tags.
      for fid in tag.iterkeys():
         if fid[0] == "T":
            del tag[fid]
   
      # Add the primary tags.
      for fid, entry in self.primary_line:
         text = entry.get_text().strip()
         if text:
            frame = getattr(id3, fid)
            tag[fid] = frame(3, [text])
 
      # Add the freeform text tags.
      tb = self.tag_frame.tb
      lines = tb.get_text(tb.get_start_iter(), tb.get_end_iter()).splitlines()
          
      for line in lines:
         try:
            fid, val = line.split(":", 1)
         
         except ValueError:
            continue
         
         fid = fid.strip()
         val = val.strip().decode("utf-8")
         
         try:
            frame = id3.Frames[fid]
         except NameError:
            continue
 
         if not issubclass(frame, id3.TextFrame):
            continue
 
         if frame is id3.TXXX:
            try:
               key, val = val.split(u"=", 1)
            
            except ValueError:
               continue
            
            f = frame(3, key.strip(), [val.strip()])
            tag[f.HashKey] = f
            
         else:
            try:
               val_list = tag[fid].text
            except KeyError:
               tag[fid] = frame(3, [val])
            else:
               val_list.append(val)

      tag.save()
            
   def load_tag(self):
      """(re)Writes the tag data to the GUI."""
      
      additional = []
      done = []
      
      for fid, entry in self.primary_line:
         try:
            frame = self.tag[fid]
            if fid[0] == "T":
               try:
                  entry.set_text(frame.text[0])
               except TypeError:
                  # Handle occurrence of ID3Timestamp.
                  entry.set_text(str(frame.text[0]))
               for each in frame.text[1:]:
                  additional.append(fid + ":" + each.encode("utf-8"))
         except KeyError:
            entry.set_text("")
         
         done.append(fid)
            
      for fid, frame in self.tag.iteritems():
         if fid[0] == "T" and fid not in done:
            sep = "=" if fid.startswith("TXXX:") else ":"
            for text in frame.text:
               additional.append(fid + sep + text.encode("utf-8"))
            
      self.tag_frame.tb.set_text("\n".join(additional))
      
   def __init__(self, pathname, force=False):
      MutagenTagger.__init__(self, pathname)
      if force:
         try:
            self.tag = mutagen.File(pathname)
            if not isinstance(self.tag, MP3):
               raise mutagen.mp3.error
         except mutagen.mp3.error:
            print "Not a real mp3 file apparently."
            self.tag = None
            return
         try:
            self.tag.add_tags()
            print "Added ID3 tags to", pathname
         except mutagen.id3.error:
            print "Existing ID3 tags found."
      else:
         try:
            # Obtain ID3 tags from a non mp3 file.
            self.tag = mutagen.id3.ID3(pathname)
         except mutagen.id3.error:
            self.tag = None
            return
         
      hbox = gtk.HBox()
      hbox.set_border_width(5)
      hbox.set_spacing(8)
      self.pack_start(hbox, False, False, 0)
      vbox_frame = gtk.VBox()
      hbox.pack_start(vbox_frame, False, False, 0)
      vbox_text = gtk.VBox()
      hbox.pack_start(vbox_text, False, False, 0)
      vbox_entry = gtk.VBox()
      hbox.pack_start(vbox_entry, True, True, 0)
      
      self.primary_line = []
      for frame, text, entry in ((x, y, gtk.Entry()) for x, y in self.primary_data):
         self.primary_line.append((frame, entry))
         vbox_frame.add(LeftLabel(frame))
         vbox_text.add(RightLabel(text))
         vbox_entry.add(entry)
      hbox.show_all()
      
      self.tag_frame = FreeTagFrame()
      set_tip(self.tag_frame, ln.id3freeform)
      self.tag_frame.set_border_width(5)
      self.tag_frame.set_label(ln.id3textframes)
      self.add(self.tag_frame)
      self.tag_frame.show()


class MP4Tagger(MutagenTagger):
   """MP4 tagging with Mutagen."""
   
   primary_data = (("\xa9nam", ln.mp4title), ("\xa9ART", ln.mp4artist),
                   ("\xa9alb", ln.mp4album), ("trkn", ln.mp4track),
                   ("\xa9gen", ln.mp4genre), ("\xa9day", ln.mp4year))
   
   def save_tag(self):
      """Updates the tag with the GUI data."""
      
      tag = self.tag
      for fid, entry in self.primary_line:
         text = entry.get_text().strip()
         if fid == "trkn":
            mo1 = re.search("\d+", text)
            try:
               track = int(text[mo1.start():mo1.end()])
            except AttributeError:
               new_val = None
            else:
               text = text[mo1.end():]
               mo2 = re.search("\d+", text)
               try:
                  total = int(text[mo2.start():mo2.end()])
               except AttributeError:
                  new_val = [(track, 0)]
               else:
                  new_val = [(track, total)]
         else:
            new_val = [text] if text else None

         if new_val is not None:
            tag[fid] = new_val
         else:
            try:
               del tag[fid]
            except KeyError:
               pass

      tag.save()
            
   def load_tag(self):
      """(re)Writes the tag data to the GUI."""
      
      additional = []
      
      for fid, entry in self.primary_line:
         try:
            frame = self.tag[fid][0]
         except KeyError:
            entry.set_text("")
         else:
            if fid == "trkn":
               if frame[1]:
                  entry.set_text("%d/%d" % frame)
               else:
                  entry.set_text(str(frame[0]))
            else:
               entry.set_text(frame)
          
   def __init__(self, pathname):
      MutagenTagger.__init__(self, pathname)
      try:
         self.tag = mutagen.mp4.MP4(pathname)
         if not isinstance(self.tag, mutagen.mp4.MP4):
            raise mutagen.mp4.error
      except mutagen.mp4.error:
         print "Not a real mp4 file apparently."
         self.tag = None
         return
         
      hbox = gtk.HBox()
      hbox.set_border_width(5)
      hbox.set_spacing(8)
      self.pack_start(hbox, False, False, 0)
      vbox_text = gtk.VBox()
      hbox.pack_start(vbox_text, False, False, 0)
      vbox_entry = gtk.VBox()
      hbox.pack_start(vbox_entry, True, True, 0)
      
      self.primary_line = []
      for frame, text, entry in ((x, y, gtk.Entry()) for x, y in self.primary_data):
         self.primary_line.append((frame, entry))
         vbox_text.add(LeftLabel(text))
         vbox_entry.add(entry)
      hbox.show_all()


class NativeTagger(MutagenTagger):
   """Native format tagging with Mutagen. Mostly FLAC and Ogg."""
   
   blacklist = "coverart", "metadata_block_picture"
   
   def save_tag(self):
      """Updates the tag with the GUI data."""
      
      tag = self.tag
      
      for key in tag.iterkeys():
         if key not in self.blacklist:
            del tag[key]
            
      tb = self.tag_frame.tb
      lines = tb.get_text(tb.get_start_iter(), tb.get_end_iter()).splitlines()
      
      for line in lines:
         try:
            key, val = line.split("=", 1)
         except ValueError:
            continue
         else:
            key = key.strip()
            val = val.strip()
            if key not in self.blacklist and val:
               try:
                  tag[key] += [val.decode("utf-8")]
               except (KeyError, AttributeError):
                  try:
                     tag[key] = [val.decode("utf-8")]
                  except KeyError:
                     print "Unacceptable key", key
   
      tag.save() 
   
   def load_tag(self):
      """(re)Writes the tag data to the GUI."""
      
      tag = self.tag
      lines = []
      primaries = "title", "artist", "author", "album",\
                          "tracknumber", "tracktotal", "genre", "date"
      
      for key in primaries:
         try:
            values = tag[key]
         except KeyError:
            lines.append(key + "=")
         else:
            for val in values:
               lines.append(key + "=" + val.encode("utf-8"))

      for key, values in tag.iteritems():
         if key not in primaries and key not in self.blacklist:
            for val in values:
               lines.append(key + "=" + val.encode("utf-8"))
            
      self.tag_frame.tb.set_text("\n".join(lines))
   
   def __init__(self, pathname, ext):
      MutagenTagger.__init__(self, pathname)
      self.tag = mutagen.File(pathname)
      if isinstance(self.tag, (MP3, APEv2)):
         # MP3 and APEv2 have their own specialised tagger.
         self.tag = None
         return
      
      self.tag_frame = FreeTagFrame()
      self.add(self.tag_frame)
      self.tag_frame.show()


class ApeTagger(MutagenTagger):
   """APEv2 tagging with Mutagen."""
   
   opener = {"ape": MonkeysAudio, "mpc": Musepack }
   
   def save_tag(self):
      """Updates the tag with the GUI data."""
      
      tag = self.tag
      
      for key, values in tag.iteritems():
         if isinstance(values, APETextValue):
            del tag[key]
            
      tb = self.tag_frame.tb
      lines = tb.get_text(tb.get_start_iter(), tb.get_end_iter()).splitlines()
      
      for line in lines:
         try:
            key, val = line.split("=", 1)
         except ValueError:
            continue
         else:
            key = key.strip()
            val = val.strip()
            if val:
               try:
                  tag[key].value += "\0" + val.decode("utf-8")
               except (KeyError, AttributeError):
                  try:
                     tag[key] = APETextValue(val.decode("utf-8"), 0)
                  except KeyError:
                     print "Unacceptable key", key
   
      tag.save() 
   
   def load_tag(self):
      """(re)Writes the tag data to the GUI."""
      
      tag = self.tag
      lines = []
      primaries = "TITLE", "ARTIST", "AUTHOR", "ALBUM",\
                          "TRACKNUMBER", "TRACKTOTAL", "GENRE", "DATE"
      
      for key in primaries:
         try:
            values = tag[key]
         except KeyError:
            lines.append(key + "=")
         else:
            for val in values:
               lines.append(key + "=" + val.encode("utf-8"))

      for key, values in tag.iteritems():
         if key not in primaries and isinstance(values, APETextValue):
            for val in values:
               lines.append(key + "=" + val.encode("utf-8"))
            
      self.tag_frame.tb.set_text("\n".join(lines))
   
   def __init__(self, pathname, extension):
      MutagenTagger.__init__(self, pathname)
      
      try:
         self.tag = self.opener[extension](pathname)
      except KeyError:
         try:
            self.tag = APEv2(pathname)
         except:
            print "ape tag not found"
            self.tag = None
            return
         else:
            print "ape tag found on non-native format"
      except:
         print "failed to create tagger for native format"
         self.tag = None
         return
      else:
         try:
            self.tag.add_tags()
         except:
            print "ape tag found on native format"
         else:
            print "no existing ape tags found"
         
      self.tag_frame = FreeTagFrame()
      self.add(self.tag_frame)
      self.tag_frame.show()


class MutagenGUI:
   ext2name = { "mp3": "ID3", "mp4": "MP4", "m4a": "MP4", "spx": "Speex",
               "flac": "FLAC", "ogg": "Ogg Vorbis", "oga": "XIPH Ogg audio",
               "m4b": "MP4", "m4p": "MP4", "wma": "Windows Media Audio" }
   
   def destroy_and_quit(self, widget, data = None):
      gtk.main_quit()
      sys.exit(0)
   
   def update_playlists(self, pathname, idjcroot):
      newplaylistdata = idjcroot.player_left.get_media_metadata(pathname)
      idjcroot.player_left.update_playlist(newplaylistdata)
      idjcroot.player_right.update_playlist(newplaylistdata)
   
   @staticmethod
   def is_supported(pathname):
      supported = [ "mp3", "ogg", "oga" ]
      if avcodec and avformat:
         supported += ["mp4", "m4a", "m4b", "m4p", "ape", "mpc", "wma"]
      if flacenabled:
         supported.append("flac")
      if speexenabled:
         supported.append("spx")
      extension = os.path.splitext(pathname)[1][1:].lower()
      if supported.count(extension) != 1:
         if extension:
            print "File type", extension, "is not supported for tagging"
         return False
      else:
         return extension
   
   def __init__(self, pathname, encoding, idjcroot = None):
      if not pathname:
         print "Tagger not supplied any pathname."
         return
      
      extension = self.is_supported(pathname)
      if extension == False:
         print "Tagger file extension", extension, "not supported."
         return
      
      global set_tip
      if idjcroot:
         set_tip = idjcroot.tooltips.set_tip
      
      self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
      if idjcroot is not None:
         idjcroot.window_group.add_window(self.window)
      self.window.set_size_request(550, 450)
      self.window.set_title(ln.tagger_window_title)
      self.window.set_destroy_with_parent(True)
      self.window.set_border_width(9)
      self.window.set_resizable(True)
      self.window.set_icon_from_file(pkgdatadir + "icon" + gfext)
      if idjcroot == None:
         self.window.connect("destroy", self.destroy_and_quit)
      vbox = gtk.VBox()
      self.window.add(vbox)
      vbox.show()
      label = gtk.Label()
      if idjcroot:
         label.set_markup(u"<b>" + ln.tagger_filename + u" " + rich_safe(unicode(os.path.split(pathname)[1], encoding).encode("utf-8", "replace")) + u"</b>")
      else:
         label.set_markup(u"<b>" + ln.tagger_filename + u" " + rich_safe(unicode(os.path.split(pathname)[1], "latin1").encode("utf-8", "replace")) + u"</b>")
      vbox.pack_start(label, False, False, 6)
      label.show()
      
      hbox = gtk.HBox()
      hbox.set_border_width(2)
      apply_button = gtk.Button(None, gtk.STOCK_APPLY)
      if idjcroot is not None:
         apply_button.connect_object_after("clicked", self.update_playlists, pathname, idjcroot)
      hbox.pack_end(apply_button, False, False, 0)
      apply_button.show()
      close_button = gtk.Button(None, gtk.STOCK_CLOSE)
      close_button.connect_object("clicked", gtk.Window.destroy, self.window)
      hbox.pack_end(close_button, False, False, 10)
      close_button.show()
      reload_button = gtk.Button(None, gtk.STOCK_REVERT_TO_SAVED)
      hbox.pack_start(reload_button, False, False, 10)
      reload_button.show()
      vbox.pack_end(hbox, False, False, 0)
      hbox.show()
      hbox = gtk.HBox()
      vbox.pack_end(hbox, False, False, 2)
      hbox.show()
      
      notebook = gtk.Notebook()
      notebook.set_border_width(2)
      vbox.pack_start(notebook, True, True, 0)
      notebook.show()
      
      self.ape = ApeTagger(pathname, extension)
      
      if extension == "mp3":
         self.id3 = ID3Tagger(pathname, True)
         self.native = None
      else:
         self.id3 = ID3Tagger(pathname, False)
         if extension in ("mp4", "m4a", "m4b", "m4p"):
            self.native = MP4Tagger(pathname)
         elif extension == "wma":
            self.native = WMATagger(pathname)
         elif extension in ("ape", "mpc"):
            # APE tags are native to this format.
            self.native = None
         else:
            self.native = NativeTagger(pathname, ext=extension)
      
      if self.id3 is not None and self.id3.tag is not None:
         reload_button.connect("clicked", lambda x: self.id3.load_tag())
         apply_button.connect("clicked", lambda x: self.id3.save_tag())
         label = gtk.Label("ID3")
         notebook.append_page(self.id3, label)
         self.id3.show()
      
      if self.ape is not None and self.ape.tag is not None:
         reload_button.connect("clicked", lambda x: self.ape.load_tag())
         apply_button.connect("clicked", lambda x: self.ape.save_tag())
         label = gtk.Label("APE v2")
         notebook.append_page(self.ape, label)
         self.ape.show()   
      
      if self.native is not None and self.native.tag is not None:
         reload_button.connect("clicked", lambda x: self.native.load_tag())
         apply_button.connect("clicked", lambda x: self.native.save_tag())
         label = gtk.Label(ln.native + " (" + self.ext2name[extension] + ")")
         notebook.append_page(self.native, label)
         self.native.show()
      
      reload_button.clicked()

      apply_button.connect_object_after("clicked", gtk.Window.destroy, self.window)
      self.window.show()
