#   jingles.py: Jingles window and players -- part of IDJC.
#   Copyright 2012 Stephen Fairchild (s-fairchild@users.sourceforge.net)
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


import gettext

import gtk
import itertools

from idjc import *
from .playergui import *
from .prelims import *
from .gtkstuff import LEDDict
from .gtkstuff import WindowSizeTracker


_ = gettext.translation(FGlobs.package_name, FGlobs.localedir,
                                                        fallback=True).gettext

PM = ProfileManager()

# Pixbufs for LED's of the specified size.
LED = LEDDict(6)



class JingleUnit(gtk.HBox):
    """A trigger button for a Jingle or Sequence with additional widgets.
    
    Takes a numeric parameter for identification.
    """


    # All JingleUnit widgets' labels to be of uniform size.
    sizegroup = gtk.SizeGroup(gtk.SIZE_GROUP_HORIZONTAL)


    def __init__(self, num):
        gtk.HBox.__init__(self)
        self.set_border_width(2)
        self.set_spacing(3)
        
        label = gtk.Label("%02d" % (num + 1))
        self.pack_start(label, False)
        self.sizegroup.add_widget(label)
        
        self.led = gtk.Image()
        self.led.set_from_pixbuf(LED["clear"].copy())
        self.pack_start(self.led, False)
        
        image = gtk.image_new_from_file(FGlobs.pkgdatadir / "stop.png")
        self.stop = gtk.Button()
        self.stop.set_sensitive(False)
        self.stop.set_image(image)
        self.pack_start(self.stop)
        
        self.trigger = gtk.Button()
        self.trigger.set_size_request(80, -1)
        self.trigger.set_sensitive(False)
        self.pack_start(self.trigger)

        image = gtk.image_new_from_stock(gtk.STOCK_PROPERTIES,
                                                            gtk.ICON_SIZE_MENU)
        self.config = gtk.Button()
        self.config.set_image(image)
        self.pack_start(self.config, False)



class Effect(JingleUnit):
    """A trigger button for an effect."""


    def __init__(self, num):
        JingleUnit.__init__(self, num)



class Sequence(JingleUnit):
    """A trigger button for chained effects."""


    def __init__(self, num):
        JingleUnit.__init__(self, num)



class JingleCluster(gtk.Frame):
    """A frame containing columns of widget."""


    def __init__(self, label, qty, cols, widget, *args):
        gtk.Frame.__init__(self, label)
        self.widgets = []
        hbox = gtk.HBox()
        self.add(hbox)
        count = 0
        
        rows = (qty + cols - 1) // cols
        for col in range(cols):
            vbox = gtk.VBox()
            hbox.pack_start(vbox)
            
            for row in range(rows):
                self.widgets.append(widget(count, *args))
                vbox.pack_start(self.widgets[-1])
                count += 1



class ExtraPlayers(gtk.HBox):
    """For effects, sequences of same, and background tracks."""
    
    
    def __init__(self, parent):
        self.approot = parent

        gtk.HBox.__init__(self)
        self.set_border_width(6)
        self.set_spacing(12)
        self.viewlevels = (5,)

        esbox = gtk.VBox()
        self.pack_start(esbox)
        estable = gtk.Table(columns=3, homogeneous=True)
        estable.set_col_spacing(1, 8)
        esbox.pack_start(estable)

        self.effects = JingleCluster(" %s " % _('Effects'), 24, 2, Effect)
        estable.attach(self.effects, 0, 2, 0, 1)
        
        self.sequences = JingleCluster(" %s " % _('Sequences'), 12, 1, Sequence)
        estable.attach(self.sequences, 2, 3, 0, 1)
        
        self.jvol_adj = gtk.Adjustment(100.0, 0.0, 100.0, 1.0, 10.0)
        self.jmute_adj = gtk.Adjustment(80.0, 0.0, 100.0, 1.0, 10.0)
        self.ivol_adj = gtk.Adjustment(50.0, 0.0, 100.0, 1.0, 10.0)

        for each in (self.jvol_adj, self.jmute_adj, self.ivol_adj):
            each.connect("value-changed",
                                lambda w: parent.send_new_mixer_stats())
        
        volpb = gtk.gdk.pixbuf_new_from_file(FGlobs.pkgdatadir / "volume2.png")

        jlevel_vbox = gtk.VBox()
        self.pack_start(jlevel_vbox, False)
        
        jvol_image = gtk.image_new_from_pixbuf(volpb.copy())
        jvol = gtk.VScale(self.jvol_adj)
        jvol.set_draw_value(False)

        jmute_image = gtk.image_new_from_file(FGlobs.pkgdatadir / "volume2.png")
        jmute = gtk.VScale(self.jmute_adj)
        jmute.set_draw_value(False)
        
        for widget, expand in zip((jvol_image, jvol, jmute_image, jmute), 
                                                itertools.cycle((False, True))):
            jlevel_vbox.pack_start(widget, expand)

        self.pack_start(gtk.VSeparator(), False)
        
        ilevel_vbox = gtk.VBox()
        self.pack_start(ilevel_vbox, False)
        
        ivol_image = gtk.image_new_from_pixbuf(volpb.copy())
        ilevel_vbox.pack_start(ivol_image, False)
        ivol = gtk.VScale(self.ivol_adj)
        ivol.set_draw_value(False)
        ilevel_vbox.pack_start(ivol)

        interlude_frame = gtk.Frame(" %s " % _('Background Tracks'))
        self.pack_start(interlude_frame)
        interlude_box = gtk.VBox()
        interlude_box.set_border_width(8)
        interlude_frame.add(interlude_box)
        self.interlude = IDJC_Media_Player(interlude_box, "interlude", parent)
        interlude_box.set_no_show_all(True)

        self.show_all()
        interlude_box.show()


    def clear_indicators(self):
        """Set all LED indicators to off."""
        
        pass


    def cleanup(self):
        pass


    @property
    def playing(self):
        return False
        
    
    @property
    def flush(self):
        return 0
        

    @flush.setter
    def flush(self, value):
        pass


    @property
    def interludeflush(self):
        return 0


    @interludeflush.setter
    def interludeflush(self, value):
        pass
