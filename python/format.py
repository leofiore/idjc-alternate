#   format.py: format selection user interface widgets
#   Copyright (C) 2012 Stephen Fairchild (s-fairchild@users.sourceforge.net)
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


import json
import gettext
import ctypes
from abc import ABCMeta, abstractmethod, abstractproperty

import gtk
import gobject

from idjc import FGlobs


_ = gettext.translation(FGlobs.package_name, FGlobs.localedir,
                                                        fallback=True).gettext


class TestEncoder(object):
    __metaclass__ = ABCMeta


    @abstractproperty
    def default_bitrate_stereo(self):
        """A guaranteed good bitrate when encoding 2 channels."""

        return int()
        

    @abstractproperty
    def default_bitrate_mono(self):
        """A guaranteed good bitrate when encoding 1 channel.
        
        Ideally the same value as for stereo if possible."""

        return int()

        
    @abstractproperty
    def default_samplerate(self):
        """Typically 44100Hz unless the encoder won't support this."""
        
        return int()


    @abstractproperty
    def suggested_samplerates(self):
        """Useful samplerates for user interface dropdown selection.
        
        These values are for EncoderRange to verify.
        """
        
        return tuple()


    @abstractproperty
    def suggested_bitrates(self):
        """Useful bitrates for user interface dropdown selection.
        
        These values are for EncoderRange to verify.
        """
        
        return tuple()


    @abstractmethod
    def test(self, channels, samplerate, bitrate):
        return bool()



class VorbisTestEncoder(TestEncoder):
    class _VORBIS_INFO(ctypes.Structure):
        _fields_ = [("version", ctypes.c_int), 
                    ("channels", ctypes.c_int),
                    ("rate", ctypes.c_long),
                    ("bitrate_upper", ctypes.c_long),
                    ("bitrate_nominal", ctypes.c_long),
                    ("bitrate_lower", ctypes.c_long),
                    ("bitrate_window", ctypes.c_long),
                    ("codec_setup", ctypes.c_void_p)]


    _lv = ctypes.CDLL("libvorbis.so.0")
    _lve = ctypes.CDLL("libvorbisenc.so.2")


    def __init__(self):
        self._vi = self._VORBIS_INFO()


    @property
    def default_bitrate_stereo(self):
        return 128000


    @property
    def default_bitrate_mono(self):
        return 128000


    @property
    def default_samplerate(self):
        return 44100


    @property
    def suggested_samplerates(self):
        return (48000, 44100, 32000, 22050, 11025)


    @property
    def suggested_bitrates(self):
        return (192000, 160000, 128000, 112000, 96000, 80000, 64000, 48000, 45000, 32000)


    def test(self, channels, samplerate, bitrate):
        """Test run these encoder settings with a vorbis encoder.
        
        A return value of True indicates that encoding would work for the
        provided settings.
        """

        vi = self._vi

        self._lv.vorbis_info_init(ctypes.byref(vi))
        error_code = self._lve.vorbis_encode_init(ctypes.byref(vi),
                ctypes.c_long(channels), ctypes.c_long(samplerate),
                ctypes.c_long(-1), ctypes.c_long(bitrate), ctypes.c_long(-1))
        self._lv.vorbis_info_clear(ctypes.byref(vi))

        return error_code == 0



class EncoderRange(object):
    """Test out the limits of an encoder's settings."""


    def __init__(self, encoder):
        """An instance of EncoderRange can probe one type of encoder.
        
        @encoder: an instance of TestEncoder
        """
        
        self._encoder = encoder
        self._test = encoder.test
        self._working_bitrate = {1: encoder.default_bitrate_mono,
                                 2: encoder.default_bitrate_stereo}


    def _boundary_search(self, variable_span, test):
        """Encoder working boundary value finder.
        
        @variable_span is a list of two integers that form the search range.
        The algorithm will find the lowest limit value if the first value is
        smaller and the highest limit value if the first value is bigger.
        
        @test is a function that takes one value, the variable under test and
        returns boolean true indicating success.
        """

        span_1 = variable_span
        found = None

        while 1:
            val1 = None
            span_2 = []
            for val2 in span_1:
                if val1 is None:
                    if abs(span_1[0] - span_1[-1]) + 1 == len(span_1):
                        return found
                    val1 = val2
                    continue

                span_2.append(val1)
                mid = abs(val1 - val2) // 2 + min(val1, val2)
                if min(val1, val2) < mid < max(val1, val2):
                    span_2.append(mid)
                    if test(mid):
                        found = mid
                        span_1 = [val1, mid]
                        val1 = None
                        break
                
                val1 = val2
            else:
                span_1 = [span_2[-1], val1] if found is not None \
                                                        else span_2 + [val1]


    def lowest_bitrate(self, channels, samplerate):
        """Calculate the lowest working bitrate."""

        return self._boundary_search([8000, 1000000],
            lambda bitrate: self._test(channels, samplerate, bitrate))


    def highest_bitrate(self, channels, samplerate):
        """Calculate the highest working bitrate."""

        return self._boundary_search([1000000, 8000],
            lambda bitrate: self._test(channels, samplerate, bitrate))


    def lowest_samplerate(self, channels, bitrate):
        """Calculate the lowest working samplerate."""

        return self._boundary_search([4000, 200000],
            lambda samplerate: self._test(channels, samplerate, bitrate))


    def highest_samplerate(self, channels, bitrate):
        """Calculate the highest working samplerate."""

        return self._boundary_search([200000, 4000],
            lambda samplerate: self._test(channels, samplerate, bitrate))


    def bitrate_bounds(self, channels, samplerate):
        """Lowest and highest working bitrate as a 2 tuple."""

        return self.lowest_bitrate(channels, samplerate), \
                                self.highest_bitrate(channels, samplerate)


    def samplerate_bounds(self, channels, bitrate):
        """Lowest and highest working samplerate as a 2 tuple."""
        
        return self.lowest_samplerate(channels, bitrate), \
                                self.highest_samplerate(channels, bitrate)


    def bounds(self, channels):
        """Find the absolute lowest and highest encoder supported settings.
        
        Return value: dictionary containing 2 tuples for samplerate and bitrate
        Inputs:
        @channels: 1 for mono, 2 for stereo.
        """
        
        srb = self.samplerate_bounds(channels, self._working_bitrate[channels])
        oldbrb = brb = oldsrb = None, None
        
        while brb != oldbrb or oldsrb != srb:
            oldbrb = brb
            oldsrb = srb
     
            brb = (self.bitrate_bounds(channels, srb[0])[0],
                                self.bitrate_bounds(channels, srb[1])[1])
            srb = (self.samplerate_bounds(channels, brb[0])[0],
                                self.samplerate_bounds(channels, brb[1])[1])
        
        return {"samplerate_bounds": srb, "bitrate_bounds": brb}


    def good_samplerates(self, channels, bitrate=None):
        if bitrate is None:
            lower, upper = self.bounds(channels)["samplerate_bounds"]
        else:
            lower, upper = self.samplerate_bounds(channels, bitrate)
        
        return tuple(x for x in self._encoder.suggested_samplerates if
                                                        lower <= x <= upper)


    def good_bitrates(self, channels, samplerate=None):
        if samplerate is None:
            lower, upper = self.bounds(channels)["bitrate_bounds"]
        else:
            lower, upper = self.bitrate_bounds(channels, samplerate)

        return tuple(x for x in self._encoder.suggested_bitrates if
                                                        lower <= x <= upper)



def format_collate(specifier):
    """Takes a FormatDropdown or FormatSpin object, obtains the settings."""
    
    d = {}
    if specifier.prev_object is not None:
        d.update(format_collate(specifier.prev_object))
    
    d[specifier.ident] = specifier.value
    if not specifier.applied:
        d["unapplied"] = specifier.ident
    return d



class FormatDropdown(gtk.VBox):
    def __init__(self, prev_object, title, ident, elements):
        """Parameter 'elements' is a tuple of dictionaries.
        
        @title: appears above the widget
        @name: is the official name of the control element
        @elements: is tuple of dictionary objects mandatory keys of which are
            'display_text' and 'value'.
        """
        
        self.prev_object = prev_object
        self._ident = ident
        gtk.VBox.__init__(self)
        frame = gtk.Frame(" %s " % title)
        frame.set_label_align(0.5, 0.5)
        self.pack_start(frame, fill=False)
        size_group = gtk.SizeGroup(gtk.SIZE_GROUP_VERTICAL)
        vbox = gtk.VBox()
        vbox.set_border_width(3)
        frame.add(vbox)
        
        model = gtk.ListStore(gobject.TYPE_PYOBJECT)
        default = 0
        for index, each in enumerate(elements):
            if "default" in each and each["default"]:
                default = index
            model.append(((each),))
        cell_text = gtk.CellRendererText()
        self._combo_box = gtk.ComboBox(model)
        size_group.add_widget(self._combo_box)
        self._combo_box.pack_start(cell_text)
        self._combo_box.set_cell_data_func(cell_text, self._cell_data_func)
        vbox.pack_start(self._combo_box, False)
        self._fixed = gtk.Label()
        size_group.add_widget(self._fixed)
        vbox.pack_start(self._fixed, False)
        self._fixed.set_no_show_all(True)

        self._combo_box.connect("changed", self._on_changed)
        self._combo_box.set_active(default)
        
        self.show_all()


    def _cell_data_func(self, cell_layout, cell, model, iter):
        cell.props.text = model.get_value(iter, 0)["display_text"]


    def _on_changed(self, combo_box):
        text = combo_box.props.model[combo_box.props.active][0]["display_text"]
        self._fixed.set_text(text)


    @property
    def next_element_name(self):
        cbp = self._combo_box.props
        try:
            return cbp.model[cbp.active][0]["chain"]
        except KeyError:
            return None


    @property
    def applied(self):
        return self._fixed.props.visible


    @property
    def ident(self):
        return self._ident


    def apply(self):
        self._combo_box.hide()
        self._fixed.show()
        
        
    def unapply(self):
        self._combo_box.show()
        self._fixed.hide()


    @property
    def value(self):
        cbp = self._combo_box.props
        return cbp.model[cbp.active][0]["value"]


    @value.setter
    def value(self, data):
        print data
        
        if not self.applied:
            cbp = self._combo_box.props
            for i, each in enumerate(cbp.model):
                if each[0]["value"] == data:
                    self._combo_box.set_active(i)
                    break



class FormatSpin(gtk.VBox):
    def __init__(self, prev_object, title, ident, elements, unit, next_element_name, suggested_values):
        """Parameter 'elements' is a tuple of dictionaries.
        
        @title: appears above the widget
        @name: is the official name of the control element
        @elements: the values of the gtk.Adjustment as integers
        @unit: e.g. " Hz"
        @suggested_values: sequence of standard values
        """
        
        self.prev_object = prev_object
        self._ident = ident
        self._unit = unit
        self._next_element_name = next_element_name
        gtk.VBox.__init__(self)
        frame = gtk.Frame(" %s " % title)
        frame.set_label_align(0.5, 0.5)
        self.pack_start(frame, fill=False)
        vbox = gtk.VBox()
        vbox.set_border_width(3)
        frame.add(vbox)
        
        adjustment = gtk.Adjustment(*(float(x) for x in elements))
        self._spin_button = gtk.SpinButton(adjustment)
        if suggested_values is not None:
            self._spin_button.connect("populate_popup", self._on_populate_popup, suggested_values)
        vbox.pack_start(self._spin_button, False)
        self._fixed = gtk.Label()
        self._fixed.set_alignment(0.5, 0.5)
        vbox.pack_start(self._fixed)
        self._fixed.set_no_show_all(True)

        self._spin_button.connect("value-changed", self._on_changed)
        self._spin_button.emit("value-changed")
        
        self.show_all()
        size_group = gtk.SizeGroup(gtk.SIZE_GROUP_VERTICAL)
        size_group.add_widget(prev_object.get_children()[0])
        size_group.add_widget(frame)


    def _on_changed(self, spin_button):
        self._fixed.set_text(str(int(spin_button.props.value)) + self._unit)


    def _on_populate_popup(self, spin, menu, values):
        mi = gtk.MenuItem(_('Suggested Values'))
        menu.append(mi)
        mi.show()
        submenu = gtk.Menu()
        mi.set_submenu(submenu)
        submenu.show()
        for each in values:
            mi = gtk.MenuItem(str(each))
            mi.connect("activate", self._on_popup_activate, spin, each)
            submenu.append(mi)
            mi.show()


    def _on_popup_activate(self, menuitem, spin, value):
        spin.set_value(value)


    @property
    def next_element_name(self):
        return self._next_element_name


    @property
    def applied(self):
        return self._fixed.props.visible


    @property
    def ident(self):
        return self._ident


    def apply(self):
        self._spin_button.hide()
        self._fixed.show()
        
        
    def unapply(self):
        self._spin_button.show()
        self._fixed.hide()
        
        
    @property
    def value(self):
        return str(int(self._spin_button.props.value))



class FormatCodecMPEGMP3Quality(FormatDropdown):
    """MP3 quality."""
    
    def __init__(self, prev_object):
        FormatDropdown.__init__(self, prev_object, _('Qual.'), "quality", (
            dict(display_text=_('0 most'), value="0"),
            dict(display_text="1", value="1"),
            # TC: * means is the recommended setting.
            dict(display_text=_("2 *"), value="2", default=True)) + tuple(
            dict(display_text=str(x), value=str(x)) for x in range(3, 10)))



class FormatCodecMPEGMP3Mode(FormatDropdown):
    """MP3 modes."""
    
    def __init__(self, prev_object):
        FormatDropdown.__init__(self, prev_object, _('Mode'), "mode", (
            dict(display_text=_("Mono"), value="mono", chain="FormatCodecMPEGMP3Quality"),
            dict(display_text=_("Stereo"), value="stereo", chain="FormatCodecMPEGMP3Quality"),
            dict(display_text=_("Joint Stereo"), value="jointstereo", default=True, chain="FormatCodecMPEGMP3Quality")))



class FormatCodecMPEGMP3V1BitRates(FormatDropdown):
    """MP3 MPEG1 bit rates."""
    
    def __init__(self, prev_object):
        FormatDropdown.__init__(self, prev_object, _('Bitrate'), "bitrate", (
            dict(display_text="320 kHz", value="320", chain="FormatCodecMPEGMP3Mode"),
            dict(display_text="256 kHz", value="256", chain="FormatCodecMPEGMP3Mode"),
            dict(display_text="224 kHz", value="224", chain="FormatCodecMPEGMP3Mode"),
            dict(display_text="192 kHz", value="192", chain="FormatCodecMPEGMP3Mode"),
            dict(display_text="160 kHz", value="160", chain="FormatCodecMPEGMP3Mode"),
            dict(display_text="128 kHz", value="128", chain="FormatCodecMPEGMP3Mode", default=True),
            dict(display_text="112 kHz", value="112", chain="FormatCodecMPEGMP3Mode"),
            dict(display_text="96 kHz", value="96", chain="FormatCodecMPEGMP3Mode"),
            dict(display_text="80 kHz", value="80", chain="FormatCodecMPEGMP3Mode"),
            dict(display_text="64 kHz", value="64", chain="FormatCodecMPEGMP3Mode"),
            dict(display_text="56 kHz", value="56", chain="FormatCodecMPEGMP3Mode"),
            dict(display_text="48 kHz", value="48", chain="FormatCodecMPEGMP3Mode"),
            dict(display_text="40 kHz", value="40", chain="FormatCodecMPEGMP3Mode"),
            dict(display_text="32 kHz", value="32", chain="FormatCodecMPEGMP3Mode")))



class FormatCodecMPEGMP3V2BitRates(FormatDropdown):
    """MP3 MPEG2 and 2.5 bit rates."""
    
    def __init__(self, prev_object):
        FormatDropdown.__init__(self, prev_object, _('Bitrate'), "bitrate", (
            dict(display_text="160 kHz", value="160", chain="FormatCodecMPEGMP3Mode"),
            dict(display_text="144 kHz", value="144", chain="FormatCodecMPEGMP3Mode"),
            dict(display_text="128 kHz", value="128", chain="FormatCodecMPEGMP3Mode"),
            dict(display_text="112 kHz", value="112", chain="FormatCodecMPEGMP3Mode"),
            dict(display_text="96 kHz", value="96", chain="FormatCodecMPEGMP3Mode"),
            dict(display_text="80 kHz", value="80", chain="FormatCodecMPEGMP3Mode"),
            dict(display_text="64 kHz", value="64", chain="FormatCodecMPEGMP3Mode"),
            dict(display_text="56 kHz", value="56", chain="FormatCodecMPEGMP3Mode"),
            dict(display_text="48 kHz", value="48", chain="FormatCodecMPEGMP3Mode"),
            dict(display_text="40 kHz", value="40", chain="FormatCodecMPEGMP3Mode"),
            dict(display_text="32 kHz", value="32", chain="FormatCodecMPEGMP3Mode"),
            dict(display_text="24 kHz", value="24", chain="FormatCodecMPEGMP3Mode"),
            dict(display_text="16 kHz", value="16", chain="FormatCodecMPEGMP3Mode"),
            dict(display_text="8 kHz", value="8", chain="FormatCodecMPEGMP3Mode")))



class FormatCodecMPEGMP3V1SampleRates(FormatDropdown):
    """MP3 MPEG1 sample rates."""
    
    def __init__(self, prev_object):
        FormatDropdown.__init__(self, prev_object, _('Samplerate'), "samplerate", (
            dict(display_text="48000 Hz", value="48000", chain="FormatCodecMPEGMP3V1BitRates"),
            dict(display_text="44100 Hz", value="44100", chain="FormatCodecMPEGMP3V1BitRates", default=True),
            dict(display_text="32000 Hz", value="32000", chain="FormatCodecMPEGMP3V1BitRates")))



class FormatCodecMPEGMP3V2SampleRates(FormatDropdown):
    """MP3 MPEG2 sample rates."""
    
    def __init__(self, prev_object):
        FormatDropdown.__init__(self, prev_object, _('Samplerate'), "samplerate", (
            dict(display_text="24000 Hz", value="24000", chain="FormatCodecMPEGMP3V2BitRates"),
            dict(display_text="22050 Hz", value="22050", chain="FormatCodecMPEGMP3V2BitRates", default=True),
            dict(display_text="16000 Hz", value="16000", chain="FormatCodecMPEGMP3V2BitRates")))



class FormatCodecMPEGMP3V2_5SampleRates(FormatDropdown):
    """MP3 MPEG2.5 non standard sample rates."""
    
    def __init__(self, prev_object):
        FormatDropdown.__init__(self, prev_object, _('Samplerate'), "samplerate", (
            dict(display_text="12000 Hz", value="12000", chain="FormatCodecMPEGMP3V2BitRates"),
            dict(display_text="11025 Hz", value="11025", chain="FormatCodecMPEGMP3V2BitRates", default=True),
            dict(display_text="8000 Hz", value="8000", chain="FormatCodecMPEGMP3V2BitRates")))



class FormatCodecMPEGMP3(FormatDropdown):
    """MP3 standard selection."""
    
    def __init__(self, prev_object):
        # TC: Abbreviation of the word, standard.
        FormatDropdown.__init__(self, prev_object, _('Std.'), "mp3std", (
            # TC: v stands for version.
            dict(display_text=_("V 1"), value="1", chain="FormatCodecMPEGMP3V1SampleRates"),
            # TC: v stands for version.
            dict(display_text=_("V 2"), value="2", chain="FormatCodecMPEGMP3V2SampleRates"),
            # TC: v stands for version.
            dict(display_text=_("V 2.5"), value="2.5", chain="FormatCodecMPEGMP3V2_5SampleRates")))



class FormatCodecSpeexCPU(FormatDropdown):
    """Speex cpu usage selection."""
    
    def __init__(self, prev_object):
        FormatDropdown.__init__(self, prev_object, _('CPU'), "cpu", 
            tuple(dict(display_text=str(x), value=str(x), default=(x==5))
                                                            for x in range(9, -1, -1)))



class FormatCodecSpeexQuality(FormatDropdown):
    """Speex quality selection."""
    
    def __init__(self, prev_object):
        FormatDropdown.__init__(self, prev_object, _('Quality'), "quality", 
            tuple(dict(display_text=str(x), value=str(x), default=(x==8), chain="FormatCodecSpeexCPU")
                                                            for x in range(9, -1, -1)))



class FormatCodecSpeexBandwidth(FormatDropdown):
    """Speex bandwidth selection."""
    
    def __init__(self, prev_object):
        FormatDropdown.__init__(self, prev_object, _('Bandwidth'), "spxbw", (
            dict(display_text=_("Ultrawide"), value="ultrawide", chain="FormatCodecSpeexQuality"),
            dict(display_text=_("Wide"), value="wide", chain="FormatCodecSpeexQuality"),
            dict(display_text=_("Narrow"), value="narrow", chain="FormatCodecSpeexQuality")))



class FormatCodecSpeexMode(FormatDropdown):
    """Speex mode selection."""
    
    def __init__(self, prev_object):
        FormatDropdown.__init__(self, prev_object, _('Mode'), "mode", (
            dict(display_text=_("Mono"), value="mono", chain="FormatCodecSpeexBandwidth"),
            dict(display_text=_("Stereo"), value="stereo", chain="FormatCodecSpeexBandwidth")))



class FormatCodecFLACBits(FormatDropdown):
    """FLAC bit width selection."""
    
    def __init__(self, prev_object):
        FormatDropdown.__init__(self, prev_object, _('Width'), "bitwidth", (
            dict(display_text=_("24 bit"), value="24"),
            dict(display_text=_("20 bit"), value="20"),
            dict(display_text=_("16 bit"), value="16")))



class FormatCodecVorbisVariability(FormatDropdown):
    """Vorbis bit rate variability."""
    
    
    def __init__(self, prev_object):
        FormatDropdown.__init__(self, prev_object, _('Variability'), "variability", (
            dict(display_text=_("Constant"), value="0"),
            dict(display_text=_(u"\u00B110%"), value="10"),
            dict(display_text=_(u"\u00B120%"), value="20"),
            dict(display_text=_(u"\u00B130%"), value="30"),
            dict(display_text=_(u"\u00B140%"), value="40"),
            dict(display_text=_(u"\u00B150%"), value="50")))



class FormatCodecVorbisBitRate(FormatSpin):
    """Vorbis bit rate selection."""
    
    
    def __init__(self, prev_object):
        dict_ = format_collate(prev_object)
        channels = 1 if dict_["mode"] == "mono" else 2
        er = EncoderRange(VorbisTestEncoder())
        sr = int(dict_["samplerate"])
        bounds = er.bitrate_bounds(channels, sr)
        FormatSpin.__init__(self, prev_object, _('Bitrate'), "bitrate",
            (128000,) + bounds + (1, 10), " Hz", "FormatCodecVorbisVariability",
            er.good_bitrates(channels, sr))



class FormatCodecVorbisSampleRate(FormatSpin):
    """Vorbis sample rate selection."""
    
    
    def __init__(self, prev_object):
        channels = 1 if format_collate(prev_object)["mode"] == "mono" else 2
        er = EncoderRange(VorbisTestEncoder())
        bounds = er.bounds(channels)["samplerate_bounds"]
        FormatSpin.__init__(self, prev_object, _('Samplerate'), "samplerate",
            (44100,) + bounds + (1, 10), " Hz", "FormatCodecVorbisBitRate",
            er.good_samplerates(channels))



class FormatCodecFLACSampleRate(FormatSpin):
    """FLAC sample rate selection."""
    
    
    def __init__(self, prev_object):
        FormatSpin.__init__(self, prev_object, _('Samplerate'), "samplerate",
            (44100, 1, 655350, 1, 10), " Hz", "FormatCodecFLACBits",
            (96000, 88200, 48000, 44100))



class FormatCodecFLACMode(FormatDropdown):
    """Speex mode selection."""
    
    def __init__(self, prev_object):
        FormatDropdown.__init__(self, prev_object, _('Mode'), "mode", (
            dict(display_text=_("Mono"), value="mono", chain="FormatCodecFLACSampleRate"),
            dict(display_text=_("Stereo"), value="stereo", default=True, chain="FormatCodecFLACSampleRate")))



class FormatCodecVorbisMode(FormatDropdown):
    """Vorbis mode selection."""
    
    def __init__(self, prev_object):
        FormatDropdown.__init__(self, prev_object, _('Mode'), "mode", (
            dict(display_text=_("Mono"), value="mono", chain="FormatCodecVorbisSampleRate"),
            dict(display_text=_("Stereo"), value="stereo", default=True, chain="FormatCodecVorbisSampleRate")))



class FormatCodecXiphOgg(FormatDropdown):
    """Ogg codec selection."""
    
    def __init__(self, prev_object):
        FormatDropdown.__init__(self, prev_object, _('Codec'), "codec", (
            dict(display_text=_('Vorbis'), value="vorbis", chain="FormatCodecVorbisMode"),
            dict(display_text=_('FLAC'), value="flac", chain="FormatCodecFLACMode"),
            dict(display_text=_('Speex'), value="speex", chain="FormatCodecSpeexMode")))



class FormatCodecMPEG(FormatDropdown):
    """MPEG codec selection."""

    def __init__(self, prev_object):
        FormatDropdown.__init__(self, prev_object, _('Codec'), "codec", (
            dict(display_text=_('MP2'), value="mp2"),
            dict(display_text=_('MP3'), value="mp3", chain="FormatCodecMPEGMP3", default=True),
            dict(display_text=_('AAC'), value="aac"),
            dict(display_text=_('AAC+'), value="aacp"),
            dict(display_text=_('AAC+ v2'), value="aacpv2")))



class FormatFamily(FormatDropdown):
    """Gives choice of codec family/container format e.g. Xiph/Ogg or MPEG.
    
    The format is modified by means of a dropdown box.
    """

    def __init__(self, prev_object):
        # TC: Codec family e.g. Xiph/Ogg, MPEG etc.
        FormatDropdown.__init__(self, prev_object, _('Family'), "family", (
            # TC: Xiph.org Ogg container format.
            dict(display_text=_('Xiph/Ogg'), value="ogg", chain="FormatCodecXiphOgg", shoutcast=False),
            dict(display_text=_('MPEG'), value="mpeg", chain="FormatCodecMPEG", default=True)))



class FormatBox(gtk.VBox):
    def __init__(self):
        gtk.VBox.__init__(self)
        self.set_border_width(6)
        self.set_spacing(4)
        elem_box = gtk.HBox()
        self.pack_start(elem_box)
        button_box = gtk.HButtonBox()
        button_box.set_layout(gtk.BUTTONBOX_EDGE)
        image = gtk.image_new_from_stock(gtk.STOCK_GO_BACK, gtk.ICON_SIZE_MENU)
        back_button = gtk.Button()
        back_button.set_sensitive(False)
        back_button.add(image)
        button_box.add(back_button)
        image = gtk.image_new_from_stock(gtk.STOCK_APPLY, gtk.ICON_SIZE_MENU)
        apply_button = self.apply_button = gtk.Button()
        apply_button.add(image)
        button_box.add(apply_button)
        self.pack_start(button_box, False)
        self.show_all()

        self._current = self._first = FormatFamily(prev_object=None)
        elem_box.pack_start(self._first, False)
        
        apply_button.connect("clicked", self._on_apply, back_button, elem_box)
        back_button.connect("clicked", self._on_back, apply_button)
        
        self.__ref = (back_button, elem_box)


    def _on_apply(self, apply_button, back_button, elem_box):
        self._current.apply()
        next_element_name = self._current.next_element_name
        if next_element_name is None:
            apply_button.set_sensitive(False)
        else:
            self._current = globals()[next_element_name](self._current)
            elem_box.pack_start(self._current, False)
        back_button.set_sensitive(True)
        
        
    def _on_back(self, back_button, apply_button):
        apply_button.set_sensitive(True)
        if self._current.applied:
            self._current.unapply()
        else:
            current = self._current
            self._current = current.prev_object
            current.destroy()
            self._current.unapply()
        back_button.set_sensitive(self._current.prev_object is not None)
        
        
    def marshall(self):
        data = json.dumps(format_collate(self._current))
        print data
        return data


    def unmarshall(self, data):
        dict_ = json.loads(data)
        unapplied = dict_.get("unapplied", None)
        
        while 1:
            try:
                self._current.value = dict_[self._current.ident]
            except KeyError:
                print "key error", self._current_ident
                break
            else:
                if self._current.applied or self._current.ident == unapplied:
                    break
                oldcurr = self._current
                self.apply_button.clicked()
                if oldcurr.next_element_name is None:
                    break
