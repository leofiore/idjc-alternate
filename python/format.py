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
from .gtkstuff import LEDDict
from .tooltips import set_tip


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
        """Returns a tuple of standard suggestion values."""
        
        if bitrate is None:
            lower, upper = self.bounds(channels)["samplerate_bounds"]
        else:
            lower, upper = self.samplerate_bounds(channels, bitrate)
        
        return tuple(x for x in self._encoder.suggested_samplerates if
                                                        lower <= x <= upper)


    def good_bitrates(self, channels, samplerate=None):
        """Returns a tuple of standard suggestion values."""

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
        d["__unapplied__"] = specifier.ident
    return d



class FormatDropdown(gtk.VBox):
    def __init__(self, prev_object, title, ident, elements, row, tooltip=None):
        """Parameter 'elements' is a tuple of dictionaries.
        
        @title: appears above the widget
        @name: is the official name of the control element
        @elements: is tuple of dictionary objects mandatory keys of which are
            'display_text' and 'value'.
        """
        
        self.prev_object = prev_object
        self._ident = ident
        self._row = row
        gtk.VBox.__init__(self)
        frame = gtk.Frame(" %s " % title)
        frame.set_label_align(0.5, 0.5)
        if tooltip is not None:
            set_tip(frame, tooltip)
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
        dict_ = model.get_value(iter, 0)
        cell.props.text = dict_["display_text"]
        cell.props.sensitive = dict_.get("sensitive", True)


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
    def row(self):
        return self._row


    @property
    def ident(self):
        return self._ident


    def apply(self):
        cbp = self._combo_box.props
        if cbp.model[cbp.active][0].get("sensitive", True):
            self._combo_box.hide()
            self._fixed.show()
            return True
        else:
            return False
        
        
    def unapply(self):
        self._combo_box.show()
        self._fixed.hide()


    @property
    def value(self):
        cbp = self._combo_box.props
        return cbp.model[cbp.active][0]["value"]


    @value.setter
    def value(self, data):
        if not self.applied:
            cbp = self._combo_box.props
            for i, each in enumerate(cbp.model):
                if each[0]["value"] == data:
                    self._combo_box.set_active(i)
                    break



class FormatSpin(gtk.VBox):
    def __init__(self, prev_object, title, ident, elements, row, unit, next_element_name, suggested_values, tooltip=None):
        """Parameter 'elements' is a tuple of dictionaries.
        
        @title: appears above the widget
        @name: is the official name of the control element
        @elements: the values of the gtk.Adjustment as integers
        @unit: e.g. " Hz"
        @suggested_values: sequence of standard values
        """
        
        self.prev_object = prev_object
        self._ident = ident
        self._row = row
        self._unit = unit
        self._next_element_name = next_element_name
        gtk.VBox.__init__(self)
        frame = gtk.Frame(" %s " % title)
        frame.set_label_align(0.5, 0.5)
        if tooltip is not None:
            set_tip(frame, tooltip)
        self.pack_start(frame, fill=False)
        vbox = gtk.VBox()
        vbox.set_border_width(3)
        frame.add(vbox)
        
        adjustment = gtk.Adjustment(*(float(x) for x in elements))
        self._spin_button = gtk.SpinButton(adjustment)
        if suggested_values is not None:
            self._spin_button.connect("populate_popup", self._on_populate_popup, suggested_values)
            if tooltip is None:
                set_tip(self._spin_button, _('Right click for suggested values.'))
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
    def row(self):
        return self._row


    @property
    def ident(self):
        return self._ident


    def apply(self):
        self._spin_button.hide()
        self._fixed.show()
        return True

        
    def unapply(self):
        self._spin_button.show()
        self._fixed.hide()
        
        
    @property
    def value(self):
        return str(int(self._spin_button.props.value))


    @value.setter
    def value(self, value):
        if not self.applied:
            self._spin_button.props.value = int(value)



class FormatPregain(FormatDropdown):
    """Level adjustment for audio before hitting the codec."""
    
    def __init__(self, prev_object):
        codec = format_collate(prev_object)["codec"]
        
        FormatDropdown.__init__(self, prev_object, _('Pregain'), "pregain", (
            dict(display_text=_('0 dB'), value="1.0"),
            dict(display_text=_('-0.5 dB'), value="0.944"),
            dict(display_text=_('-1.0 dB'), value="0.891", default=(codec in ("aac", "aacpv2"))),
            dict(display_text=_('-1.5 dB'), value="0.841"),
            dict(display_text=_('-2.0 dB'), value="0.794", default=(codec in ("mp2", "mp3"))),
            dict(display_text=_('-2.5 dB'), value="0.750"),
            dict(display_text=_('-3.0 dB'), value="0.708", default=(codec == "speex"))), 1,
            _("A blanket gain reduction to promote audio quality when using long established lossy audio codecs like mp3 with loud audio material.\n\n"
            "ReplayGain makes this feature generally unnecessary and the correct setting in that case is 0 dB."))



class FormatResampleQuality(FormatDropdown):
    """Resample quality."""
    
    def __init__(self, prev_object):
        FormatDropdown.__init__(self, prev_object, _('Resample Quality'), "resample_quality", (
            dict(display_text=_('Highest'), value="highest", chain="FormatPregain"),
            dict(display_text=_('Medium'), value="medium", chain="FormatPregain", default=True),
            dict(display_text=_('Lowest'), value="lowest", chain="FormatPregain")), 1,
            _("All of these settings will provide adequate audio quality. The highest setting will preserve more of the original audio bandwidth at the expense of many CPU cycles."))



class FormatMetadataChoice(FormatDropdown):
    """User can select the metadata encoding format."""
    
    def __init__(self, prev_object):
        FormatDropdown.__init__(self, prev_object, _('Metadata'), "metadata_mode", (
            dict(display_text=_('Suppressed'), value="suppressed", chain="FormatResampleQuality"),
            dict(display_text=_('UTF-8'), value="utf-8", chain="FormatResampleQuality"),
            dict(display_text=_('Latin1 *'), value="latin1", chain="FormatResampleQuality", default=True)), 1,
            _("This affects the stream metadata only. Recordings will use UTF-8 for their metadata."))



class FormatMetadataUTF8(FormatDropdown):
    """User can select whether to have metadata."""
    
    def __init__(self, prev_object):
        FormatDropdown.__init__(self, prev_object, _('Metadata'), "metadata_mode", (
            dict(display_text=_('Suppressed'), value="suppressed", chain="FormatResampleQuality"),
            dict(display_text=_('UTF-8'), value="utf-8", chain="FormatResampleQuality", default=True)), 1,
            _("Choose whether the stream will carry dynamic metadata. In the case of Ogg streams this is important as a great many players can't handle chained Ogg streams which result from the metadata updates."))



class FormatMetadataLatin1(FormatDropdown):
    """User can select whether to have metadata."""
    
    def __init__(self, prev_object):
        FormatDropdown.__init__(self, prev_object, _('Metadata'), "metadata_mode", (
            dict(display_text=_('Suppressed'), value="suppressed", chain="FormatResampleQuality"),
            dict(display_text=_('Latin1'), value="latin1", chain="FormatResampleQuality", default=True)), 1,
            _("Choose whether to send metadata. Recordings will use UTF-8 metadata."))



class FormatCodecMPEGMP2Mode(FormatDropdown):
    """MP2 modes."""
    
    def __init__(self, prev_object):

        bitrate = int(format_collate(prev_object)["bitrate"])
        if bitrate < 80:
            defmode = "mono"
        elif bitrate < 192:
            defmode = "jointstereo"
        else:
            defmode = "stereo"

        FormatDropdown.__init__(self, prev_object, _('Mode'), "mode", (
            dict(display_text=_("Mono"), value="mono", default=(defmode == "mono"), chain="FormatMetadataChoice"),
            dict(display_text=_("Stereo"), value="stereo", default=(defmode == "stereo"), chain="FormatMetadataChoice"),
            dict(display_text=_("Joint Stereo"), value="jointstereo", default=(defmode=="jointstereo"), chain="FormatMetadataChoice")), 0,
            _('Joint Stereo is a good choice on streams with low bitrates.'))



class FormatCodecMPEGMP2ModeStereo(FormatDropdown):
    """MP2 modes. No mono option due to previous bitrate choice."""
    
    def __init__(self, prev_object):
        FormatDropdown.__init__(self, prev_object, _('Mode'), "mode", (
            dict(display_text=_("Mono"), value="mono", sensitive=False, chain="FormatMetadataLatin1"),
            dict(display_text=_("Stereo"), value="stereo", default=True, chain="FormatMetadataLatin1"),
            dict(display_text=_("Joint Stereo"), value="jointstereo", chain="FormatMetadataLatin1")), 0,
            _('Due to the high bitrate selected, this codec will only support stereo.'))



class FormatCodecMPEGMP2ModeSingle(FormatDropdown):
    """MP2 modes. Only mono available due to previous bitrate choice."""
    
    def __init__(self, prev_object):
        FormatDropdown.__init__(self, prev_object, _('Mode'), "mode", (
            dict(display_text=_("Mono"), value="mono", chain="FormatMetadataLatin1"),
            dict(display_text=_("Stereo"), value="stereo", sensitive=False, chain="FormatMetadataLatin1"),
            dict(display_text=_("Joint Stereo"), value="jointstereo", sensitive=False, chain="FormatMetadataLatin1")), 0,
            _('Due to the low bitrate selected, this codec will only support mono.'))



class FormatCodecMPEGMP2V1BitRates(FormatDropdown):
    """MP2 MPEG1 bit rates. Some channel modes are restricted by bitrate."""
    
    def __init__(self, prev_object):
        FormatDropdown.__init__(self, prev_object, _('Bitrate'), "bitrate", (
            dict(display_text="384 kHz", value="384", chain="FormatCodecMPEGMP2ModeStereo"),
            dict(display_text="320 kHz", value="320", chain="FormatCodecMPEGMP2ModeStereo"),
            dict(display_text="256 kHz", value="256", chain="FormatCodecMPEGMP2ModeStereo"),
            dict(display_text="224 kHz", value="224", chain="FormatCodecMPEGMP2ModeStereo"),
            dict(display_text="192 kHz", value="192", chain="FormatCodecMPEGMP2Mode"),
            dict(display_text="160 kHz", value="160", chain="FormatCodecMPEGMP2Mode", default=True),
            dict(display_text="128 kHz", value="128", chain="FormatCodecMPEGMP2Mode"),
            dict(display_text="112 kHz", value="112", chain="FormatCodecMPEGMP2Mode"),
            dict(display_text="96 kHz", value="96", chain="FormatCodecMPEGMP2Mode"),
            dict(display_text="80 kHz", value="80", chain="FormatCodecMPEGMP2ModeSingle"),
            dict(display_text="64 kHz", value="64", chain="FormatCodecMPEGMP2Mode"),
            dict(display_text="56 kHz", value="56", chain="FormatCodecMPEGMP2ModeSingle"),
            dict(display_text="48 kHz", value="48", chain="FormatCodecMPEGMP2ModeSingle"),
            dict(display_text="32 kHz", value="32", chain="FormatCodecMPEGMP2ModeSingle")), 0)



class FormatCodecMPEGMP2V2BitRates(FormatDropdown):
    """MP2 MPEG2 bit rates."""
    
    def __init__(self, prev_object):
        FormatDropdown.__init__(self, prev_object, _('Bitrate'), "bitrate", (
            dict(display_text="160 kHz", value="160", chain="FormatCodecMPEGMP2Mode"),
            dict(display_text="144 kHz", value="144", chain="FormatCodecMPEGMP2Mode"),
            dict(display_text="128 kHz", value="128", chain="FormatCodecMPEGMP2Mode"),
            dict(display_text="112 kHz", value="112", chain="FormatCodecMPEGMP2Mode"),
            dict(display_text="96 kHz", value="96", chain="FormatCodecMPEGMP2Mode"),
            dict(display_text="80 kHz", value="80", chain="FormatCodecMPEGMP2Mode", default=True),
            dict(display_text="64 kHz", value="64", chain="FormatCodecMPEGMP2Mode"),
            dict(display_text="56 kHz", value="56", chain="FormatCodecMPEGMP2Mode"),
            dict(display_text="48 kHz", value="48", chain="FormatCodecMPEGMP2Mode"),
            dict(display_text="40 kHz", value="40", chain="FormatCodecMPEGMP2Mode"),
            dict(display_text="32 kHz", value="32", chain="FormatCodecMPEGMP2Mode"),
            dict(display_text="24 kHz", value="24", chain="FormatCodecMPEGMP2Mode"),
            dict(display_text="16 kHz", value="16", chain="FormatCodecMPEGMP2Mode"),
            dict(display_text="8 kHz", value="8", chain="FormatCodecMPEGMP2Mode")), 0)



class FormatCodecMPEGMP2V1SampleRates(FormatDropdown):
    """MP2 MPEG1 sample rates."""
    
    def __init__(self, prev_object):
        FormatDropdown.__init__(self, prev_object, _('Samplerate'), "samplerate", (
            dict(display_text="48000 Hz", value="48000", chain="FormatCodecMPEGMP2V1BitRates"),
            dict(display_text="44100 Hz", value="44100", chain="FormatCodecMPEGMP2V1BitRates", default=True),
            dict(display_text="32000 Hz", value="32000", chain="FormatCodecMPEGMP2V1BitRates")), 0)



class FormatCodecMPEGMP2V2SampleRates(FormatDropdown):
    """MP2 MPEG2 sample rates."""
    
    def __init__(self, prev_object):
        FormatDropdown.__init__(self, prev_object, _('Samplerate'), "samplerate", (
            dict(display_text="24000 Hz", value="24000", chain="FormatCodecMPEGMP2V2BitRates"),
            dict(display_text="22050 Hz", value="22050", chain="FormatCodecMPEGMP2V2BitRates", default=True),
            dict(display_text="16000 Hz", value="16000", chain="FormatCodecMPEGMP2V2BitRates")), 0)



class FormatCodecMPEGMP2(FormatDropdown):
    """MP2 standard selection."""
    
    def __init__(self, prev_object):
        # TC: Abbreviation of the word, standard.
        FormatDropdown.__init__(self, prev_object, _('Std.'), "standard", (
            # TC: v stands for version.
            dict(display_text=_("V 1"), value="1", chain="FormatCodecMPEGMP2V1SampleRates"),
            # TC: v stands for version.
            dict(display_text=_("V 2"), value="2", chain="FormatCodecMPEGMP2V2SampleRates")), 0,
            _('MPEG2 introduced lower samplerate options and corresponding lower bitrates. Choose 2 if those are required.'))



class FormatCodecMPEGMP3Quality(FormatDropdown):
    """MP3 quality."""
    
    def __init__(self, prev_object):
        FormatDropdown.__init__(self, prev_object, _('Quality'), "quality", (
            dict(display_text=_('0 most'), value="0", chain="FormatMetadataChoice"),
            dict(display_text="1", value="1", chain="FormatMetadataChoice"),
            # TC: * means is the recommended setting.
            dict(display_text=_("2 *"), value="2", chain="FormatMetadataChoice", default=True)) + tuple(
            dict(display_text=str(x), value=str(x), chain="FormatMetadataChoice") for x in range(3, 10)), 0,
            _('Higher quality costs more in terms of CPU cycles.'))



class FormatCodecMPEGMP3Mode(FormatDropdown):
    """MP3 modes."""
    
    def __init__(self, prev_object):
        bitrate = int(format_collate(prev_object)["bitrate"])
        if bitrate < 64:
            defmode = "mono"
        elif bitrate < 160:
            defmode = "jointstereo"
        else:
            defmode = "stereo"    

        FormatDropdown.__init__(self, prev_object, _('Mode'), "mode", (
            dict(display_text=_("Mono"), value="mono", default=(defmode == "mono"), chain="FormatCodecMPEGMP3Quality"),
            dict(display_text=_("Stereo"), value="stereo", default=(defmode == "stereo"), chain="FormatCodecMPEGMP3Quality"),
            dict(display_text=_("Joint Stereo"), value="jointstereo", default=(defmode == "jointstereo"), chain="FormatCodecMPEGMP3Quality")), 0,
            _('Joint Stereo is a good choice on streams with low bitrates'))



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
            dict(display_text="32 kHz", value="32", chain="FormatCodecMPEGMP3Mode")), 0)



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
            dict(display_text="64 kHz", value="64", chain="FormatCodecMPEGMP3Mode", default=True),
            dict(display_text="56 kHz", value="56", chain="FormatCodecMPEGMP3Mode"),
            dict(display_text="48 kHz", value="48", chain="FormatCodecMPEGMP3Mode"),
            dict(display_text="40 kHz", value="40", chain="FormatCodecMPEGMP3Mode"),
            dict(display_text="32 kHz", value="32", chain="FormatCodecMPEGMP3Mode"),
            dict(display_text="24 kHz", value="24", chain="FormatCodecMPEGMP3Mode"),
            dict(display_text="16 kHz", value="16", chain="FormatCodecMPEGMP3Mode"),
            dict(display_text="8 kHz", value="8", chain="FormatCodecMPEGMP3Mode")), 0)



class FormatCodecMPEGMP3V1SampleRates(FormatDropdown):
    """MP3 MPEG1 sample rates."""
    
    def __init__(self, prev_object):
        FormatDropdown.__init__(self, prev_object, _('Samplerate'), "samplerate", (
            dict(display_text="48000 Hz", value="48000", chain="FormatCodecMPEGMP3V1BitRates"),
            dict(display_text="44100 Hz", value="44100", chain="FormatCodecMPEGMP3V1BitRates", default=True),
            dict(display_text="32000 Hz", value="32000", chain="FormatCodecMPEGMP3V1BitRates")), 0)



class FormatCodecMPEGMP3V2SampleRates(FormatDropdown):
    """MP3 MPEG2 sample rates."""
    
    def __init__(self, prev_object):
        FormatDropdown.__init__(self, prev_object, _('Samplerate'), "samplerate", (
            dict(display_text="24000 Hz", value="24000", chain="FormatCodecMPEGMP3V2BitRates"),
            dict(display_text="22050 Hz", value="22050", chain="FormatCodecMPEGMP3V2BitRates", default=True),
            dict(display_text="16000 Hz", value="16000", chain="FormatCodecMPEGMP3V2BitRates")), 0)



class FormatCodecMPEGMP3V2_5SampleRates(FormatDropdown):
    """MP3 MPEG2.5 non standard sample rates."""
    
    def __init__(self, prev_object):
        FormatDropdown.__init__(self, prev_object, _('Samplerate'), "samplerate", (
            dict(display_text="12000 Hz", value="12000", chain="FormatCodecMPEGMP3V2BitRates"),
            dict(display_text="11025 Hz", value="11025", chain="FormatCodecMPEGMP3V2BitRates", default=True),
            dict(display_text="8000 Hz", value="8000", chain="FormatCodecMPEGMP3V2BitRates")), 0)



class FormatCodecMPEGMP3(FormatDropdown):
    """MP3 standard selection."""
    
    def __init__(self, prev_object):
        # TC: Abbreviation of the word, standard.
        FormatDropdown.__init__(self, prev_object, _('Std.'), "standard", (
            # TC: v stands for version.
            dict(display_text=_("V 1"), value="1", chain="FormatCodecMPEGMP3V1SampleRates"),
            # TC: v stands for version.
            dict(display_text=_("V 2"), value="2", chain="FormatCodecMPEGMP3V2SampleRates"),
            # TC: v stands for version.
            dict(display_text=_("V 2.5"), value="2.5", chain="FormatCodecMPEGMP3V2_5SampleRates")), 0)



class FormatCodecSpeexComplexity(FormatDropdown):
    """Speex cpu usage selection."""
    
    def __init__(self, prev_object):
        FormatDropdown.__init__(self, prev_object, _('Complexity'), "complexity", 
            tuple(dict(display_text=str(x), value=str(x), chain="FormatMetadataUTF8", default=(x==5))
                                                            for x in range(9, -1, -1)), 0,
            _('A quality setting that affects how heavily the CPU is used.'))



class FormatCodecSpeexQuality(FormatDropdown):
    """Speex quality selection."""
    
    def __init__(self, prev_object):
        FormatDropdown.__init__(self, prev_object, _('Quality'), "quality", 
            tuple(dict(display_text=str(x), value=str(x), default=(x==8), chain="FormatCodecSpeexComplexity")
                                                            for x in range(9, -1, -1)), 0,
            _('The higher this setting, the higher the bitrate.'))



class FormatCodecSpeexBandwidth(FormatDropdown):
    """Speex bandwidth selection."""
    
    def __init__(self, prev_object):
        FormatDropdown.__init__(self, prev_object, _('Bandwidth'), "samplerate", (
            dict(display_text=_("Ultrawide"), value="32000", chain="FormatCodecSpeexQuality"),
            dict(display_text=_("Wide"), value="16000", chain="FormatCodecSpeexQuality"),
            dict(display_text=_("Narrow"), value="8000", chain="FormatCodecSpeexQuality")), 0,
            _('Essentially a samplerate setting.'))



class FormatCodecSpeexMode(FormatDropdown):
    """Speex mode selection."""
    
    def __init__(self, prev_object):
        FormatDropdown.__init__(self, prev_object, _('Mode'), "mode", (
            dict(display_text=_("Mono"), value="mono", chain="FormatCodecSpeexBandwidth"),
            dict(display_text=_("Stereo"), value="stereo", chain="FormatCodecSpeexBandwidth")), 0)



class FormatCodecFLACBits(FormatDropdown):
    """FLAC bit width selection."""
    
    def __init__(self, prev_object):
        FormatDropdown.__init__(self, prev_object, _('Width'), "bitwidth", (
            dict(display_text=_("24 bit"), value="24", chain="FormatMetadataUTF8"),
            dict(display_text=_("20 bit"), value="20", chain="FormatMetadataUTF8"),
            dict(display_text=_("16 bit"), value="16", chain="FormatMetadataUTF8")), 0,
            _('24 bit records with the highest level of detail. If file size is a concern maybe FLAC is not the right codec.'))



class FormatCodecVorbisVariability(FormatDropdown):
    """Vorbis bit rate variability."""
    
    
    def __init__(self, prev_object):
        FormatDropdown.__init__(self, prev_object, _('Variability'), "variability", (
            dict(display_text=_("Constant"), value="0", chain="FormatMetadataUTF8"),
            dict(display_text=_(u"\u00B110%"), value="10", chain="FormatMetadataUTF8"),
            dict(display_text=_(u"\u00B120%"), value="20", chain="FormatMetadataUTF8"),
            dict(display_text=_(u"\u00B130%"), value="30", chain="FormatMetadataUTF8"),
            dict(display_text=_(u"\u00B140%"), value="40", chain="FormatMetadataUTF8"),
            dict(display_text=_(u"\u00B150%"), value="50", chain="FormatMetadataUTF8")), 0,
            _('This control is for enabling variable bitrate on Vorbis streams.'))



class FormatCodecVorbisBitRate(FormatSpin):
    """Vorbis bit rate selection."""
    
    
    def __init__(self, prev_object):
        dict_ = format_collate(prev_object)
        channels = 1 if dict_["mode"] == "mono" else 2
        er = EncoderRange(VorbisTestEncoder())
        sr = int(dict_["samplerate"])
        bounds = er.bitrate_bounds(channels, sr)
        FormatSpin.__init__(self, prev_object, _('Bitrate'), "bitrate",
            (128000,) + bounds + (1, 10), 0, " Hz", "FormatCodecVorbisVariability",
            er.good_bitrates(channels, sr))



class FormatCodecVorbisSampleRate(FormatSpin):
    """Vorbis sample rate selection."""
    
    
    def __init__(self, prev_object):
        channels = 1 if format_collate(prev_object)["mode"] == "mono" else 2
        er = EncoderRange(VorbisTestEncoder())
        bounds = er.bounds(channels)["samplerate_bounds"]
        FormatSpin.__init__(self, prev_object, _('Samplerate'), "samplerate",
            (44100,) + bounds + (1, 10), 0, " Hz", "FormatCodecVorbisBitRate",
            er.good_samplerates(channels))



class FormatCodecFLACSampleRate(FormatSpin):
    """FLAC sample rate selection."""
    
    
    def __init__(self, prev_object):
        FormatSpin.__init__(self, prev_object, _('Samplerate'), "samplerate",
            (44100, 1, 655350, 1, 10), 0, " Hz", "FormatCodecFLACBits",
            (96000, 88200, 48000, 44100))



class FormatCodecFLACMode(FormatDropdown):
    """Speex mode selection."""
    
    def __init__(self, prev_object):
        FormatDropdown.__init__(self, prev_object, _('Mode'), "mode", (
            dict(display_text=_("Mono"), value="mono", chain="FormatCodecFLACSampleRate"),
            dict(display_text=_("Stereo"), value="stereo", default=True, chain="FormatCodecFLACSampleRate")), 0)



class FormatCodecVorbisMode(FormatDropdown):
    """Vorbis mode selection."""
    
    def __init__(self, prev_object):
        FormatDropdown.__init__(self, prev_object, _('Mode'), "mode", (
            dict(display_text=_("Mono"), value="mono", chain="FormatCodecVorbisSampleRate"),
            dict(display_text=_("Stereo"), value="stereo", default=True, chain="FormatCodecVorbisSampleRate")), 0)



class FormatCodecXiphOgg(FormatDropdown):
    """Ogg codec selection."""
    
    def __init__(self, prev_object):
        FormatDropdown.__init__(self, prev_object, _('Codec'), "codec", (
            dict(display_text=_('Vorbis'), value="vorbis", chain="FormatCodecVorbisMode"),
            dict(display_text=_('FLAC'), value="flac", chain="FormatCodecFLACMode", sensitive=FGlobs.oggflacenabled),
            dict(display_text=_('Speex'), value="speex", chain="FormatCodecSpeexMode", sensitive=FGlobs.speexenabled)), 0,
            _('Codecs of the Ogg container.'))




class FormatCodecMPEGAACMode(FormatDropdown):
    """AAC mode selection."""
    
    def __init__(self, prev_object):
        FormatDropdown.__init__(self, prev_object, _('Mode'), "mode", (
            dict(display_text=_("Mono"), value="mono", chain="FormatMetadataUTF8"),
            dict(display_text=_("Stereo"), value="stereo", default=True, chain="FormatMetadataUTF8")), 0)



class FormatCodecMPEGAACModeStereo(FormatDropdown):
    """AAC+ v2 mode selection which is always stereo."""
    
    def __init__(self, prev_object):
        FormatDropdown.__init__(self, prev_object, _('Mode'), "mode", (
            dict(display_text=_("Mono"), value="mono", sensitive=False),
            dict(display_text=_("Stereo"), value="stereo", default=True, chain="FormatMetadataUTF8")), 0)



class FormatCodecMPEGAACBitrate(FormatSpin):
    """AAC bit rate selection."""
    
    def __init__(self, prev_object):
        FormatSpin.__init__(self, prev_object, _('Bitrate'), "bitrate",
            (128000, 32000, 320000, 1, 10), 0, " Hz", "FormatCodecMPEGAACMode",
            (192000, 160000, 128000, 112000, 96000, 80000, 64000, 48000, 45000, 32000))



class FormatCodecMPEGAACPlusV2Bitrate(FormatSpin):
    """AAC bit rate selection."""
    
    def __init__(self, prev_object):
        FormatSpin.__init__(self, prev_object, _('Bitrate'), "bitrate",
            (64000, 16000, 72000, 1, 10), 0, " Hz", "FormatCodecMPEGAACModeStereo",
            (72000, 64000, 48000, 45000, 32000, 24000, 16000))



class FormatCodecMPEGAACSamplerate(FormatDropdown):
    """Sample rates as allowed when using the ADTS header."""
    
    def __init__(self, prev_object):
        FormatDropdown.__init__(self, prev_object, _('Samplerate'), "samplerate", (
            dict(display_text=_('96000 Hz'), value="96000", chain="FormatCodecMPEGAACBitrate"),
            dict(display_text=_('88200 Hz'), value="88200", chain="FormatCodecMPEGAACBitrate"),
            dict(display_text=_('64000 Hz'), value="64000", chain="FormatCodecMPEGAACBitrate"),
            dict(display_text=_('48000 Hz'), value="48000", chain="FormatCodecMPEGAACBitrate"),
            dict(display_text=_('44100 Hz'), value="44100", chain="FormatCodecMPEGAACBitrate", default=True),
            dict(display_text=_('32000 Hz'), value="32000", chain="FormatCodecMPEGAACBitrate"),
            dict(display_text=_('24000 Hz'), value="24000", chain="FormatCodecMPEGAACBitrate"),
            dict(display_text=_('22050 Hz'), value="22050", chain="FormatCodecMPEGAACBitrate"),
            dict(display_text=_('16000 Hz'), value="16000", chain="FormatCodecMPEGAACBitrate"),
            dict(display_text=_('12000 Hz'), value="12000", chain="FormatCodecMPEGAACBitrate"),
            dict(display_text=_('11025 Hz'), value="11025", chain="FormatCodecMPEGAACBitrate"),
            dict(display_text=_('8000 Hz'), value="8000", chain="FormatCodecMPEGAACBitrate"),
            dict(display_text=_('7350 Hz'), value="7350", chain="FormatCodecMPEGAACBitrate")), 0)



class FormatCodecMPEGAACPlusV2Samplerate(FormatDropdown):
    """Sample rates as allowed when using the ADTS header."""
    
    def __init__(self, prev_object):
        FormatDropdown.__init__(self, prev_object, _('Samplerate'), "samplerate", (
            dict(display_text=_('48000 Hz'), value="48000", chain="FormatCodecMPEGAACPlusV2Bitrate"),
            dict(display_text=_('44100 Hz'), value="44100", chain="FormatCodecMPEGAACPlusV2Bitrate", default=True)), 0)



class FormatCodecMPEG(FormatDropdown):
    """MPEG codec selection."""

    def __init__(self, prev_object):
        have_mp3 = FGlobs.have_libmp3lame
        have_aac = FGlobs.avcodec and FGlobs.avformat
        extra = []

        if not have_mp3:
            extra.append(_('Enable the MP3 option by installing libmp3lame.'))

        if not have_aac:
            extra.append(_('The AAC options require IDJC be built against libavcodec and libavformat.'))

        spc = "\n\n\n" if extra else ""
        tooltip = _('Codecs of the MPEG family.') + spc + "\n\n".join(extra)
        
        FormatDropdown.__init__(self, prev_object, _('Codec'), "codec", (
            dict(display_text=_('MP2'), value="mp2", chain="FormatCodecMPEGMP2"),
            dict(display_text=_('MP3'), value="mp3", chain="FormatCodecMPEGMP3", sensitive=have_mp3, default=have_mp3),
            dict(display_text=_('AAC'), value="aac", chain="FormatCodecMPEGAACSamplerate", sensitive=have_aac and FormatCodecMPEG.aac_enabled),
            dict(display_text=_('AAC+ v2'), value="aacpv2", chain="FormatCodecMPEGAACPlusV2Samplerate", sensitive=have_aac and FormatCodecMPEG.aacpv2_enabled)), 0,
            tooltip)



class FormatFamily(FormatDropdown):
    """Gives choice of codec family/container format e.g. Xiph/Ogg or MPEG.
    
    The format is modified by means of a dropdown box.
    """

    def __init__(self, prev_object):
        # TC: Codec family e.g. Xiph/Ogg, MPEG etc.
        FormatDropdown.__init__(self, prev_object, _('Family'), "family", (
            # TC: Xiph.org Ogg container format.
            dict(display_text=_('Xiph/Ogg'), value="ogg", chain="FormatCodecXiphOgg", shoutcast=False),
            dict(display_text=_('MPEG'), value="mpeg", chain="FormatCodecMPEG", default=True)), 0,
            _('Codecs have been grouped by standards body and or container format.'))



class FormatControl(gtk.VBox):
    __gproperties__ = {
        'cap-icecast': (gobject.TYPE_BOOLEAN, 'icecast capable',
                        'if true this format can stream to icecast',
                        0, gobject.PARAM_READABLE),
                        
        'cap-shoutcast': (gobject.TYPE_BOOLEAN, 'shoutcast capable',
                        'if true this format can stream to shoutcast',
                        0, gobject.PARAM_READABLE),
                        
        'cap-recordable': (gobject.TYPE_BOOLEAN, 'can be recorded',
                        'if true this format is compatible with the recording facility',
                        0, gobject.PARAM_READABLE)
    }
    
    
    def __init__(self, send, receive):
        gtk.VBox.__init__(self)
        self.set_border_width(6)
        self.set_spacing(4)
        elem_box = [gtk.HBox()]
        self.pack_start(elem_box[0])
        
        self.caps_frame = gtk.Frame(" %s " % _('Capabilities'))
        self.caps_frame.set_sensitive(False)
        caps_box = gtk.HBox()
        caps_box.set_border_width(6)
        self.caps_frame.add(caps_box)
        self.pack_start(self.caps_frame, fill=False)
        
        led = LEDDict(8)
        self.green = led["green"]
        self.clear = led["clear"]
        
        for name, label_text in zip("icecast shoutcast recordable".split(),
                            (_('Icecast'), _('Shoutcast'), _('Recordable'))):
            hbox = gtk.HBox()
            hbox.set_spacing(3)
            label = gtk.Label(label_text)
            hbox.pack_start(label, False)
            
            image = gtk.Image()
            image.set_from_pixbuf(self.clear)
            hbox.pack_start(image, False)
            
            caps_box.pack_start(hbox, fill=False)
            setattr(self, "_" + name + "_indicator", image)

        elem_box.append(gtk.HBox())
        self.pack_start(elem_box[-1])
        
        button_frame = gtk.Alignment(xalign=1.0, yscale=0.85)
        button_frame.props.top_padding = 6
        button_box = gtk.HBox()
        button_box.set_spacing(3)
        button_frame.add(button_box)
        image = gtk.image_new_from_stock(gtk.STOCK_GO_BACK, gtk.ICON_SIZE_MENU)
        back_button = self._back_button = gtk.Button()
        back_button.set_sensitive(False)
        back_button.add(image)
        button_box.add(back_button)
        image = gtk.image_new_from_stock(gtk.STOCK_GO_FORWARD, gtk.ICON_SIZE_MENU)
        apply_button = self.apply_button = gtk.Button()
        apply_button.add(image)
        button_box.add(apply_button)

        #test_button = gtk.ToggleButton("Test")
        #button_box.add(test_button)
        #test_button.connect("toggled", self._on_test)
        
        elem_box[-1].pack_end(button_frame, True)
        self.show_all()

        self._current = self._first = FormatFamily(prev_object=None)
        elem_box[self._first.row].pack_start(self._first, False)
        
        apply_button.connect("clicked", self._on_apply, back_button, elem_box)
        back_button.connect("clicked", self._on_back, apply_button)
        
        sizegroup = gtk.SizeGroup(gtk.SIZE_GROUP_VERTICAL)
        for each in elem_box:
            sizegroup.add_widget(each)
        
        self._send = send
        self._receive = receive
        self._reference_counter = 0
        self._cap_icecast = self._cap_shoutcast = self._cap_recordable = False

        # GTK closures seem to be weak references.
        self.__refs = (elem_box,)


    def _on_apply(self, apply_button, back_button, elem_box):
        if self._current.apply():
            next_element_name = self._current.next_element_name
            if next_element_name is None:
                apply_button.set_sensitive(False)
                self._update_capabilities()
            else:
                self._current = globals()[next_element_name](self._current)
                elem_box[self._current.row].pack_start(self._current, False)
            back_button.set_sensitive(True)
        
        
    def _on_back(self, back_button, apply_button):
        apply_button.set_sensitive(True)
        if self._current.applied:
            self._current.unapply()
            self._update_capabilities()
        else:
            current = self._current
            self._current = current.prev_object
            current.destroy()
            self._current.unapply()
        back_button.set_sensitive(self._current.prev_object is not None)


    def _on_test(self, widget):
        if widget.get_active():
            self.start_encoder_rc()
        else:
            self.stop_encoder_rc()
            

    _cap_table = {
            "ogg":
            {
                "vorbis":
                    {"shoutcast": False, "icecast": True, "recordable": True},
                "flac":
                    {"shoutcast": False, "icecast": True, "recordable": True},
                "speex":
                    {"shoutcast": False, "icecast": True, "recordable": True}
            },
            "mpeg":
            {
                "mp2":
                    {"shoutcast": True, "icecast": True, "recordable": True},
                "mp3":
                    {"shoutcast": True, "icecast": True, "recordable": True},
                "aac":
                    {"shoutcast": True, "icecast": True, "recordable": True},
                "aacpv2":
                    {"shoutcast": True, "icecast": True, "recordable": True}
            }
    }


    def _update_capabilities(self):
        settings = format_collate(self._current)
        dict_ = self._cap_table[settings["family"]][settings["codec"]]
            
        for each in "shoutcast icecast recordable".split():
            can = dict_[each] and self._current.applied
            indicator = getattr(self, "_" + each + "_indicator")
            indicator.set_from_pixbuf(self.green if can else self.clear)
            name = "_cap_" + each
            if getattr(self, name) != can:
                setattr(self, name, can)
                self.notify("cap-" + each)
            
        self.caps_frame.set_sensitive(self._current.applied)


    def do_get_property(self, property):
        if property.name not in (
                            "cap-icecast", "cap-shoutcast", "cap-recordable"):
            raise AttributeError('unknown property %s' % property.name)
        return getattr(self, "_" + property.name.replace("-", "_"))


    def marshall(self):
        return json.dumps(format_collate(self._current))


    def unmarshall(self, data):
        dict_ = json.loads(data)
        unapplied = dict_.get("__unapplied__", None)
        oldcurr = None
        
        while 1:
            try:
                self._current.value = dict_[self._current.ident]
            except KeyError:
                print "key error", self._current.ident
                break
            else:
                if self._current.applied or self._current.ident == unapplied or oldcurr == self._current:
                    break
                oldcurr = self._current
                self.apply_button.clicked()
                if oldcurr.next_element_name is None:
                    break


    def get_settings(self):
        return format_collate(self._current)


    def start_encoder_rc(self):
        """Start the encoder (with reference counter)."""
        
        if self._reference_counter:
            self._reference_counter += 1
        else:
            self._reference_counter = int(self._start_encoder())
        return self._reference_counter > 0

     
    def stop_encoder_rc(self):
        """Stop the encoder (with reference counter)."""

        if self._reference_counter:
            if self._reference_counter == 1:
                self._stop_encoder()
            self._reference_counter -= 1


    @property
    def running(self):
        """True if the encoder is currently running."""

        return self._reference_counter > 0
        
        
    @property
    def finalised(self):
        """Return whether the encoder settings list is complete."""

        return self._current.applied


    def _start_encoder(self):
        if self._current.applied:
            kvps = [] 
            for pairs in format_collate(self._current).iteritems():
                kvps.append("=".join(pairs))
            kvps.append("encode_source=jack\ncommand=encoder_start\n")
            kvps = "\n".join(kvps)

            self._send(kvps)
            
            ret = self._receive() != "failed"
            if ret:
                self._back_button.set_sensitive(False)
            return ret
        else:
            print "encoder settings are not finalised"
            return False


    def _stop_encoder(self):
        self._back_button.set_sensitive(True)
        self._send("command=encoder_stop\n")
        return self._receive() != "failed"
        
