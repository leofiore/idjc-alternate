#   midicontrols.py: MIDI and hotkey controls for IDJC
#   Copyright (C) 2010 Andrew Clover (and@doxdesk.com)
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


import sys
import re
import os.path
import time
import collections
import gettext

import gobject
import gtk
import pango

from idjc import FGlobs, PGlobs
from .freefunctions import *
from .gtkstuff import threadslock
from .prelims import ProfileManager
from .tooltips import main_tips


t = gettext.translation(FGlobs.package_name, FGlobs.localedir, fallback=True)
_ = t.gettext

pm = ProfileManager()
set_tip = main_tips.set_tip



control_methods= {
    # TC: Control method. Please keep it as Target:Action. Please keep the targets consistent. Also,  Player != Players
    'c_tips': _('Prefs enable tooltips'),

    # TC: Control method. Please keep it as Target:Action. Please keep the targets consistent. Also,  Player != Players
    'p_pp': _('Player play/pause'),
    # TC: Control method. Please keep it as Target:Action. Please keep the targets consistent. Also,  Player != Players
    'p_stop': _('Player stop'),
    # TC: Control method. Please keep it as Target:Action. Please keep the targets consistent. Also,  Player != Players
    'p_advance': _('Player advance'),
    # TC: Control method. Please keep it as Target:Action. Please keep the targets consistent. Also,  Player != Players
    'p_prev': _('Player play previous'),
    # TC: Control method. Please keep it as Target:Action. Please keep the targets consistent. Also,  Player != Players
    'p_next': _('Player play next'),
    # TC: Control method. Please keep it as Target:Action. Please keep the targets consistent. Also,  Player != Players
    'p_sfire': _('Player play selected from start'),
    # TC: Control method. Please keep it as Target:Action. Please keep the targets consistent. Also,  Player != Players
    'p_sprev': _('Player select previous'),
    # TC: Control method. Please keep it as Target:Action. Please keep the targets consistent. Also,  Player != Players
    'p_snext': _('Player select next'),
    # TC: Control method. Please keep it as Target:Action. Please keep the targets consistent. Also,  Player != Players
    'p_stream': _('Player stream output enable'),
    # TC: Control method. Please keep it as Target:Action. Please keep the targets consistent. Also,  Player != Players
    'p_listen': _('Player DJ output enable'),
    # TC: Control method. Please keep it as Target:Action. Please keep the targets consistent. Also,  Player != Players
    'p_prep': _('Player DJ-only switch'),
    # TC: Control method. Please keep it as Target:Action. Please keep the targets consistent. Also,  Player != Players
    'p_vol': _('Player set volume'),
    # TC: Control method. Please keep it as Target:Action. Please keep the targets consistent. Also,  Player != Players
    'p_gain': _('Player set gain'),
    # TC: Control method. Please keep it as Target:Action. Please keep the targets consistent. Also,  Player != Players
    'p_pan': _('Player set balance'),
    # TC: Control method. Please keep it as Target:Action. Please keep the targets consistent. Also,  Player != Players
    'p_pitch': _('Player set pitchbend'),

    # TC: Control method. Please keep it as Target:Action. Please keep the targets consistent. Also,  Player != Players
    'p_tag': _('Playlist edit tags'),
    # TC: Control method. Please keep it as Target:Action. Please keep the targets consistent. Also,  Player != Players
    'p_istop': _('Playlist insert stop'),
    # TC: Control method. Please keep it as Target:Action. Please keep the targets consistent. Also,  Player != Players
    'p_ianno': _('Playlist insert announce'),
    # TC: Control method. Please keep it as Target:Action. Please keep the targets consistent. Also,  Player != Players
    'p_itrans': _('Playlist insert transfer'),
    # TC: Control method. Please keep it as Target:Action. Please keep the targets consistent. Also,  Player != Players
    'p_ifade': _('Playlist insert crossfade'),
    # TC: Control method. Please keep it as Target:Action. Please keep the targets consistent. Also,  Player != Players
    'p_ipitch': _('Playlist insert pitchunbend'),
    # TC: Control method. Please keep it as Target:Action. Please keep the targets consistent. Also,  Player != Players
    'p_igotop': _('Playlist insert jump to top'),

    # TC: Control method. Please keep it as Target:Action. Please keep the targets consistent. Also,  Player != Players
    'x_fade': _('Players set crossfade'),
    # TC: Control method. Please keep it as Target:Action. Please keep the targets consistent. Also,  Player != Players
    'x_pass': _('Players pass crossfade'),
    # TC: Control method. Please keep it as Target:Action. Please keep the targets consistent. Also,  Player != Players
    'x_focus': _('Players set focus'),
    # TC: Control method. Please keep it as Target:Action. Please keep the targets consistent. Also,  Player != Players
    'x_pitch': _('Players show pitchbend'),

    # TC: Control method. Please keep it as Target:Action. Please keep the targets consistent. Also,  Player != Players
    'm_on': _('Channel output enable'),
    # TC: Control method. Please keep it as Target:Action. Please keep the targets consistent. Also,  Player != Players
    'm_vol': _('Channel set volume'),
    # TC: Control method. Please keep it as Target:Action. Please keep the targets consistent. Also,  Player != Players
    'm_gain': _('Channel set gain'),
    # TC: Control method. Please keep it as Target:Action. Please keep the targets consistent. Also,  Player != Players
    'm_pan': _('Channel set balance'),

    # TC: Control method. Please keep it as Target:Action. Please keep the targets consistent. Also,  Player != Players
    'v_on': _('VoIP output enable'),
    # TC: Control method. Please keep it as Target:Action. Please keep the targets consistent. Also,  Player != Players
    'v_prep': _('VoIP DJ-only switch'),
    # TC: Control method. Please keep it as Target:Action. Please keep the targets consistent. Also,  Player != Players
    'v_vol': _('VoIP set volume'),
    # TC: Control method. Please keep it as Target:Action. Please keep the targets consistent. Also,  Player != Players
    'v_gain': _('VoIP set gain'),
    # TC: Control method. Please keep it as Target:Action. Please keep the targets consistent. Also,  Player != Players
    'v_pan': _('VoIP set balance'),

    # TC: Control method. Please keep it as Target:Action. Please keep the targets consistent. Also,  Player != Players
    'k_fire': _('Jingle play from start'),

    # TC: Control method. Please keep it as Target:Action. Please keep the targets consistent. Also,  Player != Players
    'j_ps': _('Jingles play/stop'),
    # TC: Control method. Please keep it as Target:Action. Please keep the targets consistent. Also,  Player != Players
    'j_playex': _('Jingles play exclusive'),
    # TC: Control method. Please keep it as Target:Action. Please keep the targets consistent. Also,  Player != Players
    'j_sprev': _('Jingles select previous'),
    # TC: Control method. Please keep it as Target:Action. Please keep the targets consistent. Also,  Player != Players
    'j_snext': _('Jingles select next'),
    # TC: Control method. Please keep it as Target:Action. Please keep the targets consistent. Also,  Player != Players
    'j_sfire': _('Jingles play selected from start'),
    # TC: Control method. Please keep it as Target:Action. Please keep the targets consistent. Also,  Player != Players
    'j_vol': _('Jingles set jingles volume'),
    # TC: Control method. Please keep it as Target:Action. Please keep the targets consistent. Also,  Player != Players
    'j_ivol': _('Jingles set interlude volume'),

    # TC: Control method. Please keep it as Target:Action. Please keep the targets consistent. Also,  Player != Players
    's_on': _('Stream set connected'),

    # TC: Control method. Please keep it as Target:Action. Please keep the targets consistent. Also,  Player != Players
    'r_on': _('Recorder set recording'),
}

control_targets= {
    # TC: This text is followed by a number in a spinbutton and represents a specific user interface target.
    'p': _('Player'),
    # TC: This text is followed by a number in a spinbutton and represents a specific user interface target.
    'm': _('Channel'),
    # TC: This text is followed by a number in a spinbutton and represents a specific user interface target.
    'k': _('Jingle'),
    # TC: This text is followed by a number in a spinbutton and represents a specific user interface target.
    's': _('Stream'),
    # TC: This text is followed by a number in a spinbutton and represents a specific user interface target.
    'r': _('Recorder')
}

control_targets_players= (
    # TC: This text represents a specific user interface target.
    _('Left player'),
    # TC: This text represents a specific user interface target.
    _('Right player'),
    # TC: This text represents a specific user interface target.
    _('Focused player'),
    # TC: This text represents a specific user interface target.
    _('Fadered player'),
)



class Binding(tuple):
    """Immutable value type representing an input bound to an action.

    An input is a MIDI event or keyboard movement. (Possibly others in future?)
    An action is a method of the Controls object, together with how to apply
    input to it, and, for some methods, a target integer specifying which
    player/channel/etc the method should be aimed at.

    A Binding is represented in string form in the 'controls' prefs file as
    one 'input:action' pair per line. There may be multiple bindings of the
    same input or the same action. An 'input' string looks like one of:

        Cc.nn    - MIDI control, channel 'c', control number 'nn'
        Nc.nn    - MIDI note, channel 'c', note id 'nn'
        Pc       - MIDI pitch wheel, channel 'c'
        Kmm.nnnn - Keypress, modifier-state 'm', keyval 'nnnn'

    All numbers are hex. This format is also used to send MIDI event data from
    the mixer to the idjcgui, with trailing ':vv' to set the value (0-127).

    An action string looks like:

        Mmethod.target.value

    Where method is the name of a method in the Controls object, target is
    the object index to apply it to where needed (eg. 0=left player for 'p_'
    methods), and the mode M is one of:

        D - mirror each input level change. For faders and held buttons.
            value may be 127, or -127 for inverted control (hold to set 0)
        P - call on input level high. For one-shot and toggle buttons.
            value is currently ignored.
        S - on input level high, set to specific value
            value is the value to set, from 0..127
        A - on input level high, alter value. For keyboard-controlled faders.
            value is the delta to add to current value, from -127..127

    Value is a signed decimal number. Example:

        C0.0F:Pp_stop.0.7F

    Binds the action 'Player 1 stop' to MIDI control number 15 on channel 0.
    """
    source= property(lambda self: self[0])
    channel= property(lambda self: self[1])
    control= property(lambda self: self[2])
    mode= property(lambda self: self[3])
    method= property(lambda self: self[4])
    target= property(lambda self: self[5])
    value= property(lambda self: self[6])

    # Possible source and mode values, in the order they should be listed in
    # the UI
    #
    SOURCES=(
        SOURCE_CONTROL,
        SOURCE_NOTE,
        SOURCE_PITCHWHEEL,
        SOURCE_KEYBOARD,
    )= 'cnpk'

    MODES=(
        MODE_DIRECT,
        MODE_PULSE,
        MODE_SET,
        MODE_ALTER
    )= 'dpsa'

    _default= [SOURCE_KEYBOARD, 0, 0x31, MODE_PULSE, 'p_pp', 0, 127]

    def __new__(cls, binding= None,
        source= None, channel= None, control= None,
        mode= None, method= None, target= None, value= None
    ):
        """New binding from copying old one, parsing from string, or new values
        """
        if binding is None:
            binding= list(cls._default)
        elif isinstance(binding, tuple):
            binding= list(binding)

        # Parse from string. Can also parse an input string alone
        #
        elif isinstance(binding, (str, unicode)):
            input_part, _, action_part= binding.partition(':')
            binding= list(cls._default)
            s= input_part[:1]
            if s not in Binding.SOURCES:
                raise ValueError('Unknown binding source %r' % input_part[0])
            binding[0]= s
            ch, _, inp= input_part[1:].partition('.')
            binding[1]= int(ch, 16)
            binding[2]= int(inp, 16)
            m= action_part[:1]
            if m not in Binding.MODES:
                raise ValueError('Unknown mode %r' % m)
            binding[3]= m
            parts= action_part[1:].split('.', 3)
            if len(parts)!=3:
                raise ValueError('Malformed control string %r' % action_part)
            if parts[0] not in Binding.METHODS:
                raise ValueError('Unknown method %r' % parts[0])
            binding[4]= parts[0]
            binding[5]= int(parts[1], 16)
            binding[6]= int(parts[2])
        else:
            raise ValueError('Expected string or Binding, not %r' % binding)

        # Override particular properties
        #
        if source is not None: binding[0]= source
        if channel is not None: binding[1]= channel
        if control is not None: binding[2]= control
        if mode is not None: binding[3]= mode
        if method is not None: binding[4]= method
        if target is not None: binding[5]= target
        if value is not None: binding[6]= value
        return tuple.__new__(cls, binding)

    def __str__(self):
        # Back to string
        #
        return '%s%x.%x:%s%s.%x.%d' % (self.source, self.channel, self.control, self.mode, self.method, self.target, self.value)

    def __repr__(self):
        return 'Binding(%r)' % str(self)

    @property
    def input_str(self):
        """Get user-facing representation of channel and control
        """
        if self.source==Binding.SOURCE_KEYBOARD:
            return '%s%s' % (self.channel_str, self.control_str.title())
        elif self.source==Binding.SOURCE_PITCHWHEEL:
            return self.channel_str
        else:
            return '%s: %s' % (self.channel_str, self.control_str)

    @property
    def channel_str(self):
        """Get user-facing representation of channel value (shifting for keys)
        """
        if self.source==Binding.SOURCE_KEYBOARD:
            return Binding.modifier_to_str(self.channel)
        else:
            return str(self.channel)
        return ''

    @property
    def control_str(self):
        """Get user-facing representation of control value (key, note, ...)
        """
        if self.source==Binding.SOURCE_KEYBOARD:
            return Binding.key_to_str(self.control)
        elif self.source==Binding.SOURCE_NOTE:
            return Binding.note_to_str(self.control)
        elif self.source==Binding.SOURCE_CONTROL:
            return str(self.control)
        return ''

    @property
    def action_str(self):
        """Get user-facing representation of action/mode/value
        """
        return control_methods[self.method]
        
    @property
    def modifier_str(self):
        """Get user-facing representation of interaction type and value
        """
        if self.mode==Binding.MODE_DIRECT:
            if self.value<0:
                return ' (-)'
            elif getattr(Controls, self.method).action_modes[0]!=Binding.MODE_DIRECT:
                return ' (+)'
        elif self.mode==Binding.MODE_SET:
            return ' (%d)' % self.value
        elif self.mode==Binding.MODE_ALTER:
            if self.value>=0:
                return ' (+%d)' % self.value
            else:
                return ' (%d)' % self.value
        elif self.mode==Binding.MODE_PULSE:
            if self.value<0x40:
                return ' (1-)'
        return ''

    @property
    def target_str(self):
        """Get user-facing representation of the target for this method
        """
        group= self.method[0]
        if group=='p':
            return control_targets_players[self.target]
        if group in control_targets:
            return '%s %d' % (control_targets[group], self.target+1)
        return ''

    # Display helpers used by the _str methods and also SpinButtons

    # Keys, with fallback names for unmapped keyvals
    #
    @staticmethod
    def key_to_str(k):
        name= gtk.gdk.keyval_name(k)
        if name is None:
            return '<%04X>' % k
        return name
    @staticmethod
    def str_to_key(s):
        s= s.strip()
        if s.startswith('<') and s.endswith('>') and len(s)==6:
            return int(s[1:-1], 16)

        # Try to find a name for a keyval using different case variants.
        # Unfortunately the case needed by keyval_from_name does not usually
        # match the case produced by keyval_name. Argh.
        #
        # Luckily it's not essential that this is completely right, as it's
        # only needed for bumping the 'key' spinbutton, which will rarely be
        # done.
        #
        if s.lower()=='backspace':
            # TC: The name of the backspace key.
            s= _('BackSpace')
        n= gtk.gdk.keyval_from_name(s)
        if n==0:
            n= gtk.gdk.keyval_from_name(s.lower())
        if n==0:
            n= gtk.gdk.keyval_from_name(s.title())
        if n==0:
            n= gtk.gdk.keyval_from_name(s[:1].upper()+s[1:].lower())
        return n

    # Note names. Convert to/from MIDI note/octave format.
    #
    NOTES= u'C,C#,D,D#,E,F,F#,G,G#,A,A#,B'.replace(u'#', u'\u266F').split(',')
    @staticmethod
    def note_to_str(n):
        return '%s%d' % (Binding.NOTES[n%12], n//12-1)
    @staticmethod
    def str_to_note(s):
        m= re.match(u'^([A-G](?:\u266F?))(-1|\d)$', s.replace(' ', '').replace(u'#', u'\u266F').upper())
        if m is None:
            raise ValueError('Invalid note')
        n= Binding.NOTES.index(m.group(1))
        n+= int(m.group(2))*12+12
        if not 0<=n<128:
            raise ValueError('Octave out of range')
        return n

    # Shifting keys. Convert to/from short textual forms, with symbols rather
    # than the verbose names that accelgroup_name uses.
    #
    # Also convert to/from an ordinal form where the bits are reordered to fit
    # a simple 0..127 range, for easy use in a SpinButton.
    #
    MODIFIERS= (
        (gtk.gdk.SHIFT_MASK, u'\u21D1'),
        (gtk.gdk.CONTROL_MASK, u'^'),
        (gtk.gdk.MOD1_MASK, u'\u2020'), # alt/option
        (gtk.gdk.MOD5_MASK, u'\u2021'), # altgr/option
        (gtk.gdk.META_MASK, u'\u25C6'),
        (gtk.gdk.SUPER_MASK, u'\u2318'), # win/command
        (gtk.gdk.HYPER_MASK, u'\u25CF'),
    )
    MODIFIERS_MASK= sum(m for m, c in MODIFIERS)
    @staticmethod
    def modifier_to_str(m):
        return ''.join(c for mask, c in Binding.MODIFIERS if m&mask!=0)
    @staticmethod
    def str_to_modifier(s):
        return sum(mask for mask, c in Binding.MODIFIERS if c in s)
    @staticmethod
    def modifier_to_ord(m):
        return sum(1<<i for i, (mask, c) in enumerate(Binding.MODIFIERS) if m&mask!=0)
    @staticmethod
    def ord_to_modifier(b):
        return sum(mask for i, (mask, c) in enumerate(Binding.MODIFIERS) if b&(1<<i)!=0)


    METHOD_GROUPS= []
    METHODS= []

# Decorator for control method type annotation. Method names will be stored in
# order in Binding.METHODS; the given modes will be added as a function
# property so the binding editor can read what modes to offer.
#
def action_method(*modes):
    def wrap(fn):
        fn.action_modes= modes
        Binding.METHODS.append(fn.func_name)
        group= fn.func_name[0]
        if group not in Binding.METHOD_GROUPS:
            Binding.METHOD_GROUPS.append(group)
        return fn
    return wrap


# Controls ___________________________________________________________________


class RepeatCache(collections.MutableSet):
    """A smart keyboard repeat cache -- implements time to live.

    Downstrokes are logged along with the time. Additional downstrokes
    refresh the TTL value for the key. This is done through checking the
    cached Binding before the TTL has run out, otherwise the cached
    entry is removed.

    The __contains__ method runs the TTL cache purge.
    """
    
    @property
    def ttl(self):
        """Time To Live.
        
        The duration a keystroke is valid in the absence of repeats.""" 
        return self._ttl
    @ttl.setter
    def ttl(self, ttl):
        assert(isinstance(ttl, (float, int)))
        self._ttl = ttl
    
    def __init__(self, ttl=0.8):
        self.ttl = ttl
        self._cache = {}
    
    def __len__(self):
        return len(self._cache)
        
    def __iter__(self):
        return iter(self._cache)

    def __contains__(self, key):
        if key in self._cache:
            if self._cache[key] < time.time():
                del self._cache[key]
                return False
            else:
                self._cache[key] = time.time() + self._ttl
                return True
        else:
            return False
            
    def add(self, key):
        self._cache[key] = time.time() + self._ttl
            
    def discard(self, key):
        if key in self._cache:
            del self._cache[key]


class Controls(object):
    """Dispatch and implementation of input events to action methods.
    """
    # List of controls set up, empty by default. Mapping of input ID to list
    # of associated control commands, each (control_id, n, mode, v)
    #
    settings= {}

    def __init__(self, owner):
        self.owner= owner
        self.learner= None
        self.editing= None
        self.lookup= {}
        self.highlights= {}
        self.repeat_cache= RepeatCache()

        # Default minimal set of bindings, if not overridden by prefs file
        # This matches the hotkeys previously built into IDJC
        #
        self.bindings= [
            Binding('k0.ffbe:pk_fire.0.127'), # F-key jingles
            Binding('k0.ffbf:pk_fire.1.127'),
            Binding('k0.ffc0:pk_fire.2.127'),
            Binding('k0.ffc1:pk_fire.3.127'),
            Binding('k0.ffc2:pk_fire.4.127'),
            Binding('k0.ffc3:pk_fire.5.127'),
            Binding('k0.ffc4:pk_fire.6.127'),
            Binding('k0.ffc5:pk_fire.7.127'),
            Binding('k0.ffc6:pk_fire.8.127'),
            Binding('k0.ffc7:pk_fire.9.127'),
            Binding('k0.ffc8:pk_fire.a.127'),
            Binding('k0.ffc9:pk_fire.b.127'),
            Binding('k0.ff1b:pj_ps.b.127'), # Esc stop jingles
            Binding('k0.31:sx_fade.b.0'), # 1-2 xfader sides
            Binding('k0.32:sx_fade.b.127'),
            Binding('k0.63:px_pass.0.127'), # C, pass xfader
            Binding('k0.6d:pm_on.0.127'), # M, first channel toggle
            Binding('k0.76:pv_on.0.127'), # V, VoIP toggle
            Binding('k0.70:pv_prep.0.127'), # P, VoIP prefade
            Binding('k0.ff08:pp_stop.2.127'), # backspace, stop focused player
            Binding('k0.2f:pp_advance.3.127'), # slash, advance xfaded player
            Binding('k0.74:pp_tag.2.127'), # playlist editing keys
            Binding('k0.73:pp_istop.2.127'),
            Binding('k0.75:pp_ianno.2.127'),
            Binding('k0.61:pp_itrans.2.127'),
            Binding('k0.66:pp_ifade.2.127'),
            Binding('k0.6e:pp_ipitch.2.127'),
            Binding('k4.72:pr_on.0.127'),
            Binding('k4.73:ps_on.0.127'),
            Binding('k0.69:pc_tips.0.127'), # Tooltips shown
        ]
        self.update_lookup()

    def save_prefs(self):
        """Store bindings list to prefs file
        """
        fp= open(pm.basedir / 'controls', 'w')
        for binding in self.bindings:
            fp.write(str(binding)+'\n')
        fp.close()

    def load_prefs(self):
        """Reload bindings list from prefs file
        """
        cpn = pm.basedir / 'controls'
        if os.path.isfile(cpn):
            fp= open(cpn)
            self.bindings= []
            for line in fp:
                line= line.strip()
                if line!='' and not line.startswith('#'):
                    try:
                        self.bindings.append(Binding(line))
                    except ValueError, e:
                        print >>sys.stderr, 'Warning: controls prefs file contained unreadable binding %r' % line
            fp.close()
            self.update_lookup()

    def update_lookup(self):
        """Bindings list has changed, rebuild input lookup
        """
        self.lookup= {}
        for binding in self.bindings:
            self.lookup.setdefault(str(binding).split(':', 1)[0], []).append(binding)

    def input(self, input, iv):
        """Dispatch incoming input to all bindings associated with it
        """
        # If a BindingEditor is open in learning mode, inform it of the input
        # instead of doing anything with it.
        #
        if self.learner is not None:
            self.learner.learn(input)
            return

        # Handle input value according to the action mode and pass value with
        # is-delta flag to action methods.
        #
        for binding in self.lookup.get(input, []):
            isd= False
            v= iv
            if binding.mode==Binding.MODE_DIRECT:
                if binding.value<0:
                    v= 0x7F-v
            else:
                if binding.mode==Binding.MODE_PULSE:
                    if v>=0x40:
                        if binding in self.repeat_cache:
                            continue
                        else:
                            self.repeat_cache.add(binding)
                    else:
                        self.repeat_cache.discard(binding)

                    if binding.value<=0x40:
                        v= (~v)&0x7F # Act upon release.
                if v<0x40:
                    continue
                if binding.mode in (Binding.MODE_SET, Binding.MODE_ALTER):
                    v= binding.value
                if binding.mode in (Binding.MODE_PULSE, Binding.MODE_ALTER):
                    isd= True
            # Binding is to be highlighted in the user interface.
            self.highlights[binding]= (3, True)
            getattr(self, binding.method)(binding.target, v, isd)

    def input_key(self, event):
        """Convert incoming key events into input signals
        """
        # Ignore modifier keypresses, suppress keyboard repeat,
        # and include only relevant modifier flags.
        #
        if not(0xFFE1<=event.keyval<0xFFEF or 0xFE01<=event.keyval<0xFE35):
            state= event.state&Binding.MODIFIERS_MASK
            v= 0x7F if event.type==gtk.gdk.KEY_PRESS else 0
            self.input('k%x.%x' % (state, event.keyval), v)

    # Utility for p_ control methods
    #
    def _get_player(self, n):
        if n==2:
            if self.owner.player_left.treeview.is_focus():
                n= 0
            elif self.owner.player_right.treeview.is_focus():
                n=1
            else:
                return None
        elif n==3:
            if self.owner.crossfade.get_value()<50:
                n= 0
            else:
                n= 1
        return self.owner.player_left if n==0 else self.owner.player_right

    # Control implementations. The @action_method decorator records all control
    # methods in order, so the order they are defined in this code dictates the
    # order they'll appear in in the UI.

    # Preferences
    #
    @action_method(Binding.MODE_PULSE, Binding.MODE_SET)
    def c_tips(self, n, v, isd):
        control= self.owner.prefs_window.enable_tooltips
        if isd:
            v= 0 if control.get_active() else 127
        control.set_active(v>=64)

    # Player
    #
    @action_method(Binding.MODE_PULSE, Binding.MODE_DIRECT)
    def p_pp(self, n, v, isd):
        player= self._get_player(n)
        if player is None: return
        is_playing= player.is_playing
        if not is_playing:
            player.play.set_active(True)
        if is_playing if isd else (not is_playing or player.is_paused)==(v>=0x40):
            player.pause.set_active(not player.pause.get_active())

    @action_method(Binding.MODE_PULSE)
    def p_stop(self, n, v, isd):
        player= self._get_player(n)
        if player is None: return
        player.stop.clicked()

    @action_method(Binding.MODE_PULSE)
    def p_advance(self, n, v, isd):
        player= self._get_player(n)
        if player is None: return
        player.advance()

    @action_method(Binding.MODE_PULSE)
    def p_prev(self, n, v, isd):
        player= self._get_player(n)
        if player is None: return
        player.prev.clicked()

    @action_method(Binding.MODE_PULSE)
    def p_next(self, n, v, isd):
        player= self._get_player(n)
        if player is None: return
        player.next.clicked()

    @action_method(Binding.MODE_PULSE)
    def p_sprev(self, n, v, isd):
        player= self._get_player(n)
        if player is None: return
        treeview_selectprevious(player.treeview)

    @action_method(Binding.MODE_PULSE)
    def p_snext(self, n, v, isd):
        player= self._get_player(n)
        if player is None: return
        treeview_selectnext(player.treeview)

    @action_method(Binding.MODE_PULSE)
    def p_sfire(self, n, v, isd):
        player= self._get_player(n)
        if player is None: return
        player.cb_doubleclick(player.treeview, None, None, None)

    @action_method(Binding.MODE_PULSE, Binding.MODE_DIRECT, Binding.MODE_SET)
    def p_stream(self, n, v, isd):
        player= self._get_player(n)
        if player is None: return
        active= not player.stream.get_active() if isd else v>=0x40
        player.stream.set_active(active)

    @action_method(Binding.MODE_PULSE, Binding.MODE_DIRECT, Binding.MODE_SET)
    def p_listen(self, n, v, isd):
        player= self._get_player(n)
        if player is None: return
        active= not player.listen.get_active() if isd else v>=0x40
        player.listen.set_active(active)

    @action_method(Binding.MODE_PULSE, Binding.MODE_DIRECT, Binding.MODE_SET)
    def p_prep(self, n, v, isd):
        player= self._get_player(n)
        if player is None: return
        other= self.owner.player_left if player is self.owner.player_right else self.owner.player_right
        prep= player.stream.get_active() if isd else v>=0x40
        player.stream.set_active(not prep)
        other.listen.set_active(not prep)
        if prep:
            player.listen.set_active(True)
            self.owner.listen_dj.set_active(True)
        else:
            # This is questionable. I like to listen to the Stream output not
            # DJ, so reset to Stream mode after pre-ing. This may not suit
            # everyone. Maybe there should be a different action for preview
            # without returning to stream listening. The alternative would be
            # to try to remember which output was being listened to previously,
            # but that would introduce invisible state not present in the
            # normal UI, making the behaviour unpredictable.
            #
            self.owner.listen_stream.set_active(True)

    @action_method(Binding.MODE_DIRECT, Binding.MODE_SET, Binding.MODE_ALTER)
    def p_vol(self, n, v, isd):
        player= self._get_player(n)
        if player is None: return
        deckadj= self.owner.deck2adj if player is self.owner.player_right else self.owner.deckadj
        v= v/127.0*100
        cross= deckadj.get_value()+v if isd else v
        deckadj.set_value(cross)

    #@action_method(Binding.MODE_DIRECT, Binding.MODE_SET, Binding.MODE_ALTER)
    #def p_gain(self, n, v, isd):
    #    player= self._get_player(n)
    #    if player is None: return
    #    pass # XXX

    #@action_method(Binding.MODE_DIRECT, Binding.MODE_SET, Binding.MODE_ALTER)
    #def p_pan(self, n, v, isd):
    #    player= self._get_player(n)
    #    if player is None: return
    #    pass # XXX

    @action_method(Binding.MODE_DIRECT, Binding.MODE_SET, Binding.MODE_ALTER)
    def p_pitch(self, n, v, isd):
        player= self._get_player(n)
        if player is None: return
        v= v/127.0*24-12
        speed= player.pbspeedbar.get_value()+v if isd else v
        player.pbspeedbar.set_value(speed)

    # Playlist methods, to reproduce previous idjcmedia shortcuts
    #
    @action_method(Binding.MODE_PULSE)
    def p_tag(self, n, v, isd): #t
        player= self._get_player(n)
        if player is None: return
        player.menu_model, player.menu_iter= player.treeview.get_selection().get_selected()
        player.menuitem_response(None, 'MetaTag')

    @action_method(Binding.MODE_PULSE)
    def p_istop(self, n, v, isd): #s
        player= self._get_player(n)
        if player is None: return
        player.menu_model, player.menu_iter= player.treeview.get_selection().get_selected()
        player.menuitem_response(None, 'Stop Control')

    @action_method(Binding.MODE_PULSE)
    def p_ianno(self, n, v, isd): #u
        player= self._get_player(n)
        if player is None: return
        player.menu_model, player.menu_iter= player.treeview.get_selection().get_selected()
        player.menuitem_response(None, 'Announcement Control')

    @action_method(Binding.MODE_PULSE)
    def p_itrans(self, n, v, isd): #a
        player= self._get_player(n)
        if player is None: return
        player.menu_model, player.menu_iter= player.treeview.get_selection().get_selected()
        player.menuitem_response(None, 'Transfer Control')

    @action_method(Binding.MODE_PULSE)
    def p_ifade(self, n, v, isd): #f
        player= self._get_player(n)
        if player is None: return
        player.menu_model, player.menu_iter= player.treeview.get_selection().get_selected()
        player.menuitem_response(None, 'Crossfade Control')

    @action_method(Binding.MODE_PULSE)
    def p_ipitch(self, n, v, isd): #n
        player= self._get_player(n)
        if player is None: return
        player.menu_model, player.menu_iter= player.treeview.get_selection().get_selected()
        player.menuitem_response(None, 'Normal Speed Control')

    @action_method(Binding.MODE_PULSE)
    def p_igotop(self, n, v, isd):
        player= self._get_player(n)
        if player is None: return
        player.menu_model, player.menu_iter= player.treeview.get_selection().get_selected()
        player.menuitem_response(None, 'Jump To Top Control')

    # Both players
    #
    @action_method(Binding.MODE_DIRECT, Binding.MODE_SET, Binding.MODE_ALTER)
    def x_fade(self, n, v, isd):
        v= v/127.0*100
        cross= self.owner.crossadj.get_value()+v if isd else v
        self.owner.crossadj.set_value(cross)

    @action_method(Binding.MODE_PULSE)
    def x_pass(self, n, v, isd):
        self.owner.passbutton.clicked()

    @action_method(Binding.MODE_PULSE, Binding.MODE_DIRECT, Binding.MODE_SET)
    def x_pitch(self, n, v, isd):
        checkbox= self.owner.prefs_window.speed_variance
        checkbox.set_active(not checkbox.get_active if isd else v>=0x40)

    @action_method(Binding.MODE_PULSE, Binding.MODE_DIRECT, Binding.MODE_SET)
    def x_focus(self, n, v, isd):
        if isd:
           if self.owner.player_left.treeview.is_focus():
              player = self.owner.player_right
           else:
              player = self.owner.player_left
        else:
           player= self.owner.player_right if v>=0x40 else self.owner.player_left
        player.treeview.grab_focus()

    # Channel
    #
    @action_method(Binding.MODE_PULSE, Binding.MODE_DIRECT, Binding.MODE_SET)
    def m_on(self, n, v, isd):
        opener= self.owner.mic_opener
        try:
           mic= opener.mic2button[opener.mic_list[n].ui_name]
        except:
           print "channel %d is not present" % (n + 1)
        else:
           s= not mic.get_active() if isd else v>=0x40
           mic.set_active(s)

    #@action_method(Binding.MODE_DIRECT, Binding.MODE_SET, Binding.MODE_ALTER)
    #def m_vol(self, n, v, isd):
    #    pass # XXX

    #@action_method(Binding.MODE_DIRECT, Binding.MODE_SET, Binding.MODE_ALTER)
    #def m_gain(self, n, v, isd):
    #    pass # XXX

    @action_method(Binding.MODE_DIRECT, Binding.MODE_SET, Binding.MODE_ALTER)
    def m_pan(self, n, v, isd):
        agc= getattr(self.owner.prefs_window, 'mic_control_%d'%n)
        pan= agc.valuesdict[agc.commandname+'_pan']
        v= v/127.0*100
        v= pan.get_value()+v if isd else v
        pan.set_value(v)

    # VoIP
    #
    @action_method(Binding.MODE_PULSE, Binding.MODE_DIRECT, Binding.MODE_SET)
    def v_on(self, n, v, isd):
        phone= self.owner.greenphone
        s= not phone.get_active() if isd else v>=0x40
        phone.set_active(s)

    @action_method(Binding.MODE_PULSE, Binding.MODE_DIRECT, Binding.MODE_SET)
    def v_prep(self, n, v, isd):
        phone= self.owner.redphone
        s= not phone.get_active() if isd else v>=0x40
        phone.set_active(s)

    #@action_method(Binding.MODE_DIRECT, Binding.MODE_SET, Binding.MODE_ALTER)
    #def v_vol(self, n, v, isd):
    #    pass # XXX

    #@action_method(Binding.MODE_DIRECT, Binding.MODE_SET, Binding.MODE_ALTER)
    #def v_gain(self, n, v, isd):
    #    pass # XXX

    #@action_method(Binding.MODE_DIRECT, Binding.MODE_SET, Binding.MODE_ALTER)
    #def v_pan(self, n, v, isd):
    #    pass # XXX

    # One jingle
    #
    @action_method(Binding.MODE_PULSE)
    def k_fire(self, n, v, isd):
        self.owner.jingles.trigger_index(n)

    # Jingles player in general
    #
    @action_method(Binding.MODE_PULSE)
    def j_ps(self, n, v, isd):
        if self.owner.jingles.play.get_active() or self.owner.jingles.play_ex.get_active():
            self.owner.jingles.stop.clicked()
        else:
            self.owner.jingles.play.set_active(True)

    @action_method(Binding.MODE_PULSE)
    def j_playex(self, n, v, isd):
        self.owner.jingles.play_ex.set_active(True)

    @action_method(Binding.MODE_PULSE)
    def j_sprev(self, n, v, isd):
        treeview_selectprevious(self.owner.jingles.treeview)

    @action_method(Binding.MODE_PULSE)
    def j_snext(self, n, v, isd):
        treeview_selectnext(self.owner.jingles.treeview)

    @action_method(Binding.MODE_PULSE)
    def j_sfire(self, n, v, isd):
        self.owner.jingles.stop.clicked()
        self.owner.jingles.play.set_active(True)

    @action_method(Binding.MODE_DIRECT, Binding.MODE_SET, Binding.MODE_ALTER)
    def j_vol(self, n, v, isd):
        fader= self.owner.jingles.deckvol
        v= 105-v/127.0*105
        vol= fader.get_value()+v if isd else v
        fader.set_value(vol)

    @action_method(Binding.MODE_DIRECT, Binding.MODE_SET, Binding.MODE_ALTER)
    def j_ivol(self, n, v, isd):
        fader= self.owner.jingles.intervol
        v= 100-v/127.0*100
        vol= fader.get_value()+v if isd else v
        fader.set_value(vol)

    # Stream connection
    #
    @action_method(Binding.MODE_PULSE, Binding.MODE_DIRECT, Binding.MODE_SET)
    def s_on(self, n, v, isd):
        connect= self.owner.server_window.streamtabframe.tabs[n].server_connect
        s= not connect.get_active() if isd else v>=0x40
        connect.set_active(s)

    # Recorder
    #
    @action_method(Binding.MODE_PULSE, Binding.MODE_DIRECT, Binding.MODE_SET)
    def r_on(self, n, v, isd):
        buttons= self.owner.server_window.recordtabframe.tabs[n].record_buttons
        s= not buttons.record_button.get_active() if isd else v>=0x40
        if s:
            buttons.record_button.set_active(s)
        else:
            buttons.stop_button.clicked()


# Generic GTK utilities ______________________________________________________

# TreeView move selection up/down with wrapping
#
def treeview_selectprevious(treeview):
    selection= treeview.get_selection()
    model, siter= selection.get_selected()
    iter= model.get_iter_first()
    if iter is not None:
        while True:
            niter= model.iter_next(iter)
            if niter is None or siter is not None and model.get_path(niter)==model.get_path(siter):
                break
            iter= niter
        selection.select_iter(iter)
        treeview.scroll_to_cell(model.get_path(iter), None, False)

def treeview_selectnext(treeview):
    selection= treeview.get_selection()
    model, siter= selection.get_selected()
    iter= model.get_iter_first()
    if iter is not None:
        if siter is not None:
            siter= model.iter_next(siter)
            if siter is not None:
                iter= siter
        selection.select_iter(iter)
        treeview.scroll_to_cell(model.get_path(iter), None, False)

# Simple value+text-based combo box with optional icon
#
class LookupComboBox(gtk.ComboBox):
   def __init__(self, values, texts, icons= None):
      self._values = values
      if icons is not None:
          model = gtk.ListStore(str, bool, gtk.gdk.Pixbuf)
      else:
          model = gtk.ListStore(str, bool)
      for valuei, value in enumerate(values):
         if icons is not None:
            model.append((texts[value], True, icons[value]))
         else:
            model.append((texts[value], True))
      gtk.ComboBox.__init__(self, model)

      if icons is not None:
         cricon= gtk.CellRendererPixbuf()
         self.pack_start(cricon, False)
         self.set_attributes(cricon, pixbuf= 2)
      crtext= gtk.CellRendererText()
      self.pack_start(crtext, False)
      self.set_attributes(crtext, text= 0, sensitive= 1)

   def get_value(self):
      active = self.get_active()
      if active==-1:
         active= 0
      return self._values[active]
   def set_value(self, value):
      self.set_active(self._values.index(value))

# Combo box with simple 1-level grouping and insensitive group headings
#
class GroupedComboBox(gtk.ComboBox):
    def __init__(self, groups, groupnames, values, valuenames, valuegroups):
        self._values= values
        self._lookup= {}
        model= gtk.TreeStore(int, str, bool)
        group_rows= {}
        for group in groups:
            group_rows[group]= model.append(None, [-1, groupnames[group], False])
        for i in range(len(values)):
            iter= model.append(group_rows[valuegroups[i]], [i, valuenames[values[i]], True])
            self._lookup[values[i]]= model.get_path(iter)
        gtk.ComboBox.__init__(self, model)

        cr= gtk.CellRendererText()
        self.pack_start(cr, True)
        self.set_attributes(cr, text= 1, sensitive= 2)
        
    def get_value(self):
        iter= self.get_active_iter()
        if iter is None:
            return self._values[0]
        i= self.get_model().get_value(iter, 0)
        if i==-1:
            return self._values[0]
        return self._values[i]

    def set_value(self, value):
        self.set_active_iter(self.get_model().get_iter(self._lookup[value]))

# Horrible hack to make the text of a SpinButton customisable. If the
# adjustment property is set to a subclass of CustomAdjustment, the display
# text will be customisable through the read_input and write_output method
# of that Adjustment. (With a plain Adjustment, works like normal SpinButton.)
#
# Normally customisation is impossible because the 'input' signal needs an
# output written to its gpointer argument, which is not accessible via PyGTK.
# Try to do the pointer write using ctypes, if available. Otherwise fall back
# to working like a standard ComboBox.
#
try:
    import ctypes
except ImportError:
    ctypes= None

class CustomSpinButton(gtk.SpinButton):
    def __init__(self, adjustment, climb_rate= 0.0, digits= 0):
        gtk.SpinButton.__init__(self, adjustment, climb_rate, digits)
        self._value = adjustment.get_value()
        self._iscustom = ctypes is not None
        if self._iscustom:
            self.connect('input', self._on_input)
            self.connect('output', self._on_output)

    def _on_input(self, _, ptr):
        if not repr(ptr).startswith('<gpointer at 0x'):
            self._iscustom= False
        if not self._iscustom or not isinstance(self.get_adjustment(), CustomAdjustment):
            return False
        try:
            value= self.get_adjustment().read_input(self.get_text())
        except ValueError:
            value= self._value
        addr= int(repr(ptr)[15:-1], 16)
        ctypes.c_double.from_address(addr).value= float(value) # danger!
        return True

    def _on_output(self, _):
        if not self._iscustom or not isinstance(self.get_adjustment(), CustomAdjustment):
            return False
        adj= self.get_adjustment()
        self.set_text(adj.write_output(adj.get_value()))
        return True

    def set_adjustment(self, adjustment):
        v= self.get_adjustment().get_value()
        gtk.SpinButton.set_adjustment(self, adjustment)
        if v!=adjustment.get_value():
            adjustment.set_value(v)
        else:
            adjustment.emit('value-changed')

class CustomAdjustment(gtk.Adjustment):
    def read_input(self, text):
        return float(text)
    def write_output(self, value):
        if int(value)==value:
            value= int(value)
        return str(value)


# Binding editor popup _______________________________________________________

class BindingEditor(gtk.Dialog):
    binding_values= {
        # TC: binding editor, action pane, third row, heading text.
        'd': _('Use value'), 
        # TC: binding editor, action pane, third row, heading text.
        'p': _('Act if'), 
        # TC: binding editor, action pane, third row, heading text.
        's': _('Set to'),
        # TC: binding editor, action pane, third row, heading text.
        'a': _('Adjust by'),
    }

    binding_controls= {
        # TC: binding editor, input pane, fourth row, heading text.
        'c': _('Control'),
        # TC: binding editor, input pane, fourth row, heading text.
        'n': _('Note'),
        # TC: binding editor, input pane, fourth row, heading text.
        'p': _('Control'),
        # TC: binding editor, input pane, fourth row, heading text.
        'k': _('Key'),
    }
   
    control_method_groups= {
        # TC: binding editor, action pane, first row, toplevel menu.
        'c': _('Preferences'),
        # TC: binding editor, action pane, first row, toplevel menu.
        'p': _('Player'),
        # TC: binding editor, action pane, first row, toplevel menu.
        'x': _('Both players'),
        # TC: binding editor, action pane, first row, toplevel menu.
        'm': _('Channel'),
        # TC: binding editor, action pane, first row, toplevel menu.
        'v': _('VoIP channel'),
        # TC: binding editor, action pane, first row, toplevel menu.
        'k': _('Single jingle'),
        # TC: binding editor, action pane, first row, toplevel menu.
        'j': _('Jingle player'),
        # TC: binding editor, action pane, first row, toplevel menu.
        's': _('Stream'),
        # TC: binding editor, action pane, first row, toplevel menu.
        'r': _('Stream recorder'),
    }   
   
    control_modes= {
        # TC: binding editor, action pane, second row, dropdown text.
        'd': _('Direct fader/held button'),
        # TC: binding editor, action pane, second row, dropdown text.
        'p': _('One-shot/toggle button'),
        # TC: binding editor, action pane, second row, dropdown text.
        's': _('Set value'),
        # TC: binding editor, action pane, second row, dropdown text.
        'a': _('Alter value')
    }  

    control_sources= {
        # TC: binding editor, input pane, second row, dropdown text.
        'c': _('MIDI control'),
        # TC: binding editor, input pane, second row, dropdown text.
        'n': _('MIDI note'),
        # TC: binding editor, input pane, second row, dropdown text.
        'p': _('MIDI pitch-wheel'),
        # TC: binding editor, input pane, second row, dropdown text.
        'k': _('Keyboard press'),
        # TC: binding editor, input pane, second row, dropdown text. Not implemented. 
        'x': _('XChat command')
    }
   
   
    def __init__(self, owner):
        self.owner= owner
        gtk.Dialog.__init__(self,
            # TC: Dialog window title text.
            # TC: User is expected to edit a control binding.
            _('Edit control binding'), owner.owner.owner.prefs_window.window,
            gtk.DIALOG_DESTROY_WITH_PARENT | gtk.DIALOG_NO_SEPARATOR | gtk.DIALOG_MODAL,
            (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, gtk.STOCK_OK, gtk.RESPONSE_OK)
        )
        gtk.Dialog.set_resizable(self, False)
        owner.owner.owner.window_group.add_window(self)
        self.connect('delete_event', self.on_delete)
        self.connect('close', self.on_close)
        self.connect("key-press-event", self.on_key)

        # Input editing
        #
        # TC: After clicking this button the binding editor will be listening for an input
        # TC: this could be a key press or a settings change from a midi control surface.
        self.learn_button= gtk.ToggleButton(_('Listen for input...'))
        self.learn_button.connect('toggled', self.on_learn_toggled)
        self.learn_timer= None

        self.source_field= LookupComboBox(Binding.SOURCES, self.control_sources, self.owner.source_icons)
        self.source_field.connect('changed', self.on_source_changed)
        # TC: Refers to the class of control input, the keyboard or some type of midi event.
        self.source_label= gtk.Label(_('Source'))

        # TC: The midi channel.
        self.channel_label= gtk.Label(_('Channel'))
        self.channel_field= ModifierSpinButton(ChannelAdjustment())

        self.control_label= gtk.Label(self.binding_controls['c'])
        self.control_field= CustomSpinButton(gtk.Adjustment(0, 0, 127, 1))

        # Control editing
        #
        self.method_field= GroupedComboBox(
            Binding.METHOD_GROUPS, self.control_method_groups,
            Binding.METHODS, control_methods,
            [m[0] for m in Binding.METHODS]
        )
        self.method_field.connect('changed', self.on_method_changed)

        # TC: Heading for interaction type e.g. one-shot, set value, alter value.
        # TC: Basically, the information from the controls can be used in different ways.
        self.mode_label= gtk.Label(_('Interaction'))
        self.mode_field= LookupComboBox(Binding.MODES, self.control_modes)
        self.mode_field.connect('changed', self.on_mode_changed)

        # TC: The effect of the control can be directed upon a specific target.
        # TC: e.g. On target [Left player]
        self.target_label= gtk.Label(_('On target'))
        self.target_field= CustomSpinButton(TargetAdjustment('p'))

        self.value_label= gtk.Label(self.binding_values[Binding.MODE_SET])
        self.value_field_scale= ValueSnapHScale(0, -127, 127)
        dummy= ValueSnapHScale(0, -127, 127)
        # TC: Checkbutton text.
        # TC: Use reverse scale and invert the meaning of button presses.
        self.value_field_invert= gtk.CheckButton(_('Reversed'))
        self.value_field_pulse_noinvert= gtk.RadioButton(None, _('Pressed'))
        self.value_field_pulse_inverted=gtk.RadioButton(self.value_field_pulse_noinvert, _('Released'))

        # Layout
        #
        for label in self.source_label, self.channel_label, self.control_label, self.mode_label, self.target_label, self.value_label:
            label.set_width_chars(10)
            label.set_alignment(0, 0.5)

        sg= gtk.SizeGroup(gtk.SIZE_GROUP_VERTICAL)

        row0, row1, row2, row3= gtk.HBox(spacing= 4), gtk.HBox(spacing= 4), gtk.HBox(spacing= 4), gtk.HBox(spacing= 4)
        row0.pack_start(self.learn_button)
        row1.pack_start(self.source_label, False, False)
        row1.pack_start(self.source_field)
        row2.pack_start(self.channel_label, False, False)
        row2.pack_start(self.channel_field)
        row3.pack_start(self.control_label, False, False)
        row3.pack_start(self.control_field)
        sg.add_widget(row2)

        input_pane= gtk.VBox(homogeneous= True, spacing= 2)
        input_pane.set_border_width(8)
        input_pane.pack_start(row0, False, False)
        input_pane.pack_start(row1, False, False)
        input_pane.pack_start(row2, False, False)
        input_pane.pack_start(row3, False, False)
        input_pane.show_all()
        # TC: Frame heading. Contents pertain to a specific input source and type.
        input_frame= gtk.Frame(" %s " % _('Input'))
        input_frame.set_border_width(4)
        input_frame.add(input_pane)
        input_pane.show()
        set_tip(input_pane, _("The first half of a binding is the input which comes in the form of the press of a keyboard key or an event from a midi device.\n\nInput selection can be done manually or with the help of the '%s' option." % _("Listen for input...")))

        self.value_field_pulsebox= gtk.HBox()
        self.value_field_pulsebox.pack_start(self.value_field_pulse_noinvert)
        self.value_field_pulsebox.pack_start(self.value_field_pulse_inverted)
        self.value_field_pulsebox.foreach(gtk.Widget.show)

        sg.add_widget(self.value_field_scale)
        sg.add_widget(self.value_field_invert)
        sg.add_widget(self.value_field_pulsebox)
        sg.add_widget(dummy)
        dummy.show()

        row0, row1, row2, row3= gtk.HBox(spacing= 4), gtk.HBox(spacing= 4), gtk.HBox(spacing= 4), gtk.HBox(spacing= 4)
        row0.pack_start(self.method_field)
        row1.pack_start(self.mode_label, False, False)
        row1.pack_start(self.mode_field)
        row2.pack_start(self.value_label, False, False)
        row2.pack_start(self.value_field_scale)
        row2.pack_start(self.value_field_invert)
        row2.pack_start(self.value_field_pulsebox)
        row3.pack_start(self.target_label, False, False)
        row3.pack_start(self.target_field)

        action_pane= gtk.VBox(homogeneous= True, spacing= 2)
        action_pane.set_border_width(8)
        action_pane.pack_start(row0, False, False)
        action_pane.pack_start(row1, False, False)
        action_pane.pack_start(row2, False, False)
        action_pane.pack_start(row3, False, False)
        action_pane.show_all()
        # TC: Frame heading. Contents pertain to what action occurs for a specific input.
        action_frame= gtk.Frame(" %s " % _('Action'))
        action_frame.set_border_width(4)
        action_frame.add(action_pane)
        action_pane.show()
        # TC: %s is the translation of 'Action'.
        set_tip(action_pane, _("The '%s' pane determines how the input is handled, and to what effect." % _("Action")))

        hbox= gtk.HBox(True, spacing= 4)
        hbox.pack_start(input_frame)
        hbox.pack_start(action_frame)
        hbox.show_all()
        self.get_content_area().pack_start(hbox)
        hbox.show()

    def set_binding(self, binding):
        self.learn_button.set_active(False)
        self.source_field.set_value(binding.source)
        self.channel_field.set_value(binding.channel)
        self.control_field.set_value(binding.control)
        self.method_field.set_value(binding.method)
        self.mode_field.set_value(binding.mode)
        self.target_field.set_value(binding.target)
        self.value_field_scale.set_value(binding.value)
        self.value_field_invert.set_active(binding.value < 64)
        self.value_field_pulse_noinvert.set_active(binding.value>=64)
        self.value_field_pulse_inverted.set_active(binding.value<64)

    def get_binding(self):
        mode= self.mode_field.get_value()
        if mode==Binding.MODE_DIRECT:
            value= -127 if self.value_field_invert.get_active() else 127
        elif mode==Binding.MODE_PULSE:
            value= 127 if self.value_field_pulse_noinvert.get_active() else 0
        else:
            value= int(self.value_field_scale.get_value())
        return Binding(
            source= self.source_field.get_value(),
            channel= int(self.channel_field.get_value()),
            control= int(self.control_field.get_value()),
            mode= mode,
            method= self.method_field.get_value(),
            target= int(self.target_field.get_value()),
            value= value
        )

    def on_delete(self, *args):
        self.on_close()
        return True
    def on_close(self, *args):
        self.learn_button.set_active(False)

    def on_key(self, _, event):
        if self.learn_button.get_active():
            self.owner.owner.input_key(event)
            return True
        return False

    # Learn mode, take inputs and set the input fields from them
    #
    def on_learn_toggled(self, *args):
        if self.learn_button.get_active():
            # TC: The binding editor will capture then next keyboard or midi event
            # TC: for use in making the settings in the 'Input' pane.
            self.learn_button.set_label(_('Listening for input'))
            self.owner.owner.learner= self
        else:
            # TC: Button text. If pressed triggers 'Listening for input' mode.
            self.learn_button.set_label(_('Listen for input...'))
            self.owner.owner.learner= None

    def learn(self, input):
        binding= Binding(input+':dp_pp.0.0')
        self.source_field.set_value(binding.source)
        self.channel_field.set_value(binding.channel)
        self.control_field.set_value(binding.control)
        self.learn_button.set_active(False)

    # Update dependent controls
    #
    def on_source_changed(self, *args):
        s= self.source_field.get_value()

        if s==Binding.SOURCE_KEYBOARD:
            # TC: Refers to key modifiers including Ctrl, Alt, Shift, ....
            self.channel_label.set_text(_('Shifting'))
            self.channel_field.set_adjustment(ModifierAdjustment())
        else:
            # TC: Specifically, the numerical midi channel.
            self.channel_label.set_text(_('Channel'))
            self.channel_field.set_adjustment(ChannelAdjustment())

        self.control_label.set_text(self.binding_controls[s])
        if s==Binding.SOURCE_KEYBOARD:
            self.control_field.set_adjustment(KeyAdjustment())
        elif s==Binding.SOURCE_NOTE:
            self.control_field.set_adjustment(NoteAdjustment())
        else:
            self.control_field.set_adjustment(gtk.Adjustment(0, 0, 127, 1))
        self.control_label.set_sensitive(s!=Binding.SOURCE_PITCHWHEEL)
        self.control_field.set_sensitive(s!=Binding.SOURCE_PITCHWHEEL)

    def on_method_changed(self, *args):
        method= self.method_field.get_value()
        modes= getattr(Controls, method).action_modes
        model= self.mode_field.get_model()
        iter= model.get_iter_first()
        i= 0
        while iter is not None:
            model.set_value(iter, 1, Binding.MODES[i] in modes)
            iter= model.iter_next(iter)
            i+= 1
        self.mode_field.set_value(modes[0])

        group= method[:1]
        if group=='p':
            self.target_field.set_adjustment(PlayerAdjustment())
        elif group in 'mksr':
            self.target_field.set_adjustment(TargetAdjustment(group))
        else:
            self.target_field.set_adjustment(SingularAdjustment())
        self.target_field.update()
        
        # Snap state may need altering.
        self.snap_needed = 'p' in modes and 'a' not in modes
        if bool(self.value_field_scale.snap) != self.snap_needed:
            self.mode_field.emit("changed")

    def on_mode_changed(self, *args):
        mode= self.mode_field.get_value()
        self.value_label.set_text(self.binding_values[mode])

        self.value_field_pulsebox.hide()
        self.value_field_scale.hide()
        self.value_field_invert.hide()
        
        if mode==Binding.MODE_DIRECT:
            self.value_field_invert.set_active(False)
            self.value_field_invert.show()
        elif mode==Binding.MODE_PULSE:
            self.value_field_pulsebox.show()
        else:
           # Find the adjustment limits.
           if mode==Binding.MODE_SET:
               min, max = 0, 127
           else:
               min, max = -127, 127
           val= min + (max - min + 1) // 2
           snap= val if self.snap_needed else None
           self.value_field_scale.set_range(val, min, max, snap)
           self.value_field_scale.show()

# A Compound HScale widget that supports snapping.
#
class ValueSnapHScale(gtk.HBox):
    can_mark= all(hasattr(gtk.Scale, x) for x in ('add_mark', 'clear_marks'))
    
    def __init__(self, *args, **kwds):
        gtk.HBox.__init__(self)
        self.set_spacing(2)
        self.label= gtk.Label() 
        self.label.set_width_chars(4)
        self.label.set_alignment(1.0, 0.5)
        self.pack_start(self.label, False)
        self.hscale= gtk.HScale()
        self.hscale.connect('change-value', self.on_change_value)
        self.hscale.connect('value-changed', self.on_value_changed)
        # We draw our own value so we can control the alignment.
        self.hscale.set_draw_value(False)
        self.pack_start(self.hscale)
        self.foreach(gtk.Widget.show)
        if args:
            self.set_range(*args, **kwds)
        else:
            self.label.set_text("0")
            self.snap= None

    def set_range(self, val, lower, upper, snap=None):
        # Here snap also doubles as the boundary value.
        self.snap= snap
        if snap is not None:
            policy= gtk.UPDATE_DISCONTINUOUS
            adj= gtk.Adjustment(val, lower, upper + snap - 1, snap * 2, snap * 2, snap-1)
            adj.connect('notify::value', self.on_value_do_snap, lower, upper)
        else:
            policy= gtk.UPDATE_CONTINUOUS
            adj= gtk.Adjustment(val, lower, upper, 1, 6)
        if self.can_mark:
            self.hscale.clear_marks()
            if not self.snap:
                mark= lower + (upper - lower + 1) // 2
                self.hscale.add_mark(mark, gtk.POS_BOTTOM, None)
        self.hscale.set_adjustment(adj)
        self.hscale.set_update_policy(policy)
        adj.props.value= val
        self.hscale.emit('value-changed')

    def on_change_value(self, range, scroll, _val):
        if self.snap:
            props= range.get_adjustment().props
            value= props.upper - props.page_size if range.get_value() >= self.snap else props.lower
            self.label.set_text(str(int(value)))

    def on_value_changed(self, range):
        self.label.set_text(str(int(range.get_value())))

    def on_value_do_snap(self, adj, _val, lower, upper):
        val= upper if adj.props.value >= self.snap else lower
        if adj.props.value != val:
            adj.props.value= val
        if val==lower:
            self.snap= lower + (upper - lower) // 4
        else:
            self.snap= lower + (upper - lower) * 3 // 4

    def __getattr__(self, name):
        return getattr(self.hscale, name)

# Extended adjustments for custom SpinButtons
#
class ChannelAdjustment(CustomAdjustment):
    def __init__(self, value= 0):
        CustomAdjustment.__init__(self, value, 0, 15, 1)
    def read_input(self, text):
        return int(text)-1
    def write_output(self, value):
        return str(int(value+1))
class ModifierAdjustment(CustomAdjustment):
    def __init__(self, value= 0):
        CustomAdjustment.__init__(self, value, 0, 127, 1)
    def read_input(self, text):
        return Binding.modifier_to_ord(Binding.str_to_modifier(text))
    def write_output(self, value):
        return Binding.modifier_to_str(Binding.ord_to_modifier(int(value)))

class NoteAdjustment(CustomAdjustment):
    def __init__(self, value= 0):
        CustomAdjustment.__init__(self, value, 0, 127, 1)
    def read_input(self, text):
        return Binding.str_to_note(text)
    def write_output(self, value):
        return Binding.note_to_str(int(value))
class KeyAdjustment(CustomAdjustment):
    def __init__(self, value= 0):
        CustomAdjustment.__init__(self, value, 0, 0xFFFF, 1)
    def read_input(self, text):
        return Binding.str_to_key(text)
    def write_output(self, value):
        return Binding.key_to_str(int(value))

class PlayerAdjustment(CustomAdjustment):
    def __init__(self, value= 0):
        CustomAdjustment.__init__(self, value, 0, 3, 1)
    def read_input(self, text):
        return control_targets_players.index(text)
    def write_output(self, value):
        return control_targets_players[max(min(int(value), 3), 0)]
class TargetAdjustment(CustomAdjustment):
    def __init__(self, group, value= 0):
        CustomAdjustment.__init__(self, value, 0, {'p': 3, 'm': 11, 'k': 99, 's': 8, 'r': 3}[group], 1)
        self._group= group
    def read_input(self, text):
        return int(text.rsplit(' ', 1)[-1])-1
    def write_output(self, value):
        return '%s %d' % (control_targets[self._group], value+1)
class SingularAdjustment(CustomAdjustment):
    def __init__(self, value= 0):
        CustomAdjustment.__init__(self)
    def read_input(self, text):
        return 0.0
    def write_output(self, value):
        # TC: Spinbutton text when there is only one user interface control that can be referenced.
        return _('Singular control')
        
# SpinButton that can translate its underlying adjustment values to GTK shift
# key modifier flags, when a ModifierAdjustment is used.
#
class ModifierSpinButton(CustomSpinButton):
    def get_value(self):
        value= CustomSpinButton.get_value(self)
        if isinstance(self.get_adjustment(), ModifierAdjustment):
            value= Binding.ord_to_modifier(int(value))
        return value
    def set_value(self, value):
        if isinstance(self.get_adjustment(), ModifierAdjustment):
            value= Binding.modifier_to_ord(int(value))
        CustomSpinButton.set_value(self, value)


# Main UI binding list tab ___________________________________________________

class ControlsUI(gtk.VBox):
    """Controls main config interface, displayed in a tab by IDJCmixprefs
    """
    tooltip_coords = (0, 0)
    
    def __init__(self, owner):
        gtk.VBox.__init__(self, spacing= 4)
        self.owner= owner

        self.source_icons= {}
        for ct in Binding.SOURCES:
            self.source_icons[ct]= gtk.gdk.pixbuf_new_from_file(
                        FGlobs.pkgdatadir / ('control_' + ct + ".png"))
        self.editor= BindingEditor(self)
        self.editor.connect('response', self.on_editor_response)
        self.editing= None

        # Control list
        #
        # TC: Tree column heading for Inputs e.g. Backspace, F1, S.
        column_input= gtk.TreeViewColumn(_('Input'))
        column_input.set_expand(True)
        cricon= gtk.CellRendererPixbuf()
        crtext= gtk.CellRendererText()
        crtext.props.ellipsize= pango.ELLIPSIZE_END
        column_input.pack_start(cricon, False)
        column_input.pack_start(crtext, True)
        column_input.set_attributes(cricon, pixbuf= 3, cell_background= 8)
        column_input.set_attributes(crtext, text= 4)
        column_input.set_sort_column_id(0)
        craction= gtk.CellRendererText()
        crmodifier= gtk.CellRendererText()
        crmodifier.props.xalign= 1.0
        # TC: Tree column heading for actions e.g. Player stop.
        column_action= gtk.TreeViewColumn(_('Action'))
        column_action.pack_start(craction, True)
        column_action.pack_start(crmodifier, False)
        column_action.set_attributes(craction, text= 5)
        column_action.set_attributes(crmodifier, text= 6)
        column_action.set_sort_column_id(1)
        column_action.set_sizing(gtk.TREE_VIEW_COLUMN_AUTOSIZE)
        # TC: Tree column heading for targets e.g. Channel 1, Stream 2
        column_target= gtk.TreeViewColumn(_('Target'), gtk.CellRendererText(), text= 7)
        column_target.set_sort_column_id(2)

        model= BindingListModel(self)
        model_sort= gtk.TreeModelSort(model)
        model_sort.set_sort_column_id(2, gtk.SORT_ASCENDING)
        self.tree= gtk.TreeView(model_sort)
        self.tree.connect('realize', model.on_realize, column_input, model_sort)
        self.tree.connect('cursor-changed', self.on_cursor_changed)
        self.tree.connect('key-press-event', self.on_tree_key)
        self.tree.connect('query-tooltip', self.on_tooltip_query)
        model.connect('row-deleted', self.on_cursor_changed)
        self.tree.append_column(column_input)
        self.tree.append_column(column_action)
        self.tree.append_column(column_target)
        self.tree.set_headers_visible(True)
        self.tree.set_rules_hint(True)
        self.tree.set_enable_search(False)
        self.tree.set_has_tooltip(True)

        # New/Edit/Remove buttons
        #
        # TC: User to create a new input binding.
        self.new_button= gtk.Button(_('New'))
        # TC: User to remove an input binding.
        self.remove_button= gtk.Button(_('Remove'))
        # TC: User to modify an existing input binding.
        self.edit_button= gtk.Button(_('Edit'))
        self.new_button.connect('clicked', self.on_new)
        self.remove_button.connect('clicked', self.on_remove)
        self.edit_button.connect('clicked', self.on_edit)
        self.tree.connect('row-activated', self.on_edit)

        # Layout
        #
        buttons= gtk.HButtonBox()
        buttons.set_spacing(8)
        buttons.set_layout(gtk.BUTTONBOX_END)
        buttons.pack_start(self.new_button, False, False)
        buttons.pack_start(self.remove_button, False, False)
        buttons.pack_start(self.edit_button, False, False)
        buttons.show_all()
        self.on_cursor_changed()

        self.set_border_width(4)
        scroll= gtk.ScrolledWindow()
        scroll.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        scroll.add(self.tree)
        self.pack_start(scroll, True, True)
        self.pack_start(buttons, False, False)
        self.show_all()

    # Dynamic tooltip generation
    #
    def on_tooltip_query(self, tv, x, y, kb_mode, tooltip):
        if (x, y) != self.tooltip_coords:
            self.tooltip_coords = (x, y)
        elif None not in (x, y) and self.owner.owner.prefs_window.enable_tooltips.get_active():
            path = tv.get_path_at_pos(*tv.convert_widget_to_bin_window_coords(x, y))
            if path is not None:
                row = tv.get_model()[path[0]]
                hbox = gtk.HBox()
                hbox.set_spacing(3)
                hbox.pack_start(gtk.image_new_from_pixbuf(row[3].copy()), False)
                hbox.pack_start(gtk.Label(row[4]), False)
                hbox.pack_start(gtk.Label("  " + row[5] + row[6]), False)
                if row[7]:
                    hbox.pack_start(gtk.Label("  " + row[7]), False)
                hbox.show_all()
                tooltip.set_custom(hbox)
                return True

    # Tree interaction
    #
    def on_cursor_changed(self, *args):
        isselected= self.tree.get_selection().count_selected_rows()!=0
        self.edit_button.set_sensitive(isselected)
        self.remove_button.set_sensitive(isselected)

    def on_tree_key(self, tree, event, *args):
        if event.keyval==0xFFFF: # GDK_Delete
            self.on_remove()

    # Button presses
    #
    def on_remove(self, *args):
        model_sort, iter_sort= self.tree.get_selection().get_selected()
        model= model_sort.get_model()
        if iter_sort is None:
            return
        iter= model_sort.convert_iter_to_child_iter(None, iter_sort)
        binding= self.owner.bindings[model.get_path(iter)[0]]

        if binding is self.editing:
            self.editor.learnbutton.set_active(False)
            self.editor.hide()
            self.editing= None
        niter= model.iter_next(iter)
        if niter is None:
            treeview_selectprevious(self.tree)
        else:
            treeview_selectnext(self.tree)
        model.remove(iter)
        self.on_cursor_changed()

    def on_new(self, *args):
        model_sort, iter_sort= self.tree.get_selection().get_selected()
        model= model_sort.get_model()
        if iter_sort is not None:
            iter= model_sort.convert_iter_to_child_iter(None, iter_sort)
            binding= self.owner.bindings[model.get_path(iter)[0]]
        else:
            binding= Binding()

        self.editing= None
        self.editor.set_binding(binding)
        self.editor.show()

    def on_edit(self, *args):
        model_sort, iter_sort= self.tree.get_selection().get_selected()
        if iter_sort is None:
            return
        model= model_sort.get_model()
        iter= model_sort.convert_iter_to_child_iter(None, iter_sort)

        self.editing= iter
        self.editor.set_binding(self.owner.bindings[model.get_path(iter)[0]])
        self.editor.show()

    def on_editor_response(self, _, response):
        if response==gtk.RESPONSE_OK:
            model= self.tree.get_model().get_model()
            binding= self.editor.get_binding()
            if self.editing==None:
                path= model.append(binding)
            else:
                path= model.replace(self.editing, binding)
            path_sort= self.tree.get_model().convert_child_path_to_path(path)
            self.tree.get_selection().select_path(path_sort)
            self.tree.scroll_to_cell(path_sort, None, False)
            self.on_cursor_changed()
        self.editor.hide()


class BindingListModel(gtk.GenericTreeModel):
    """TreeModel mapping the list of Bindings in Controls to a TreeView
    """
    def __init__(self, owner):
        gtk.GenericTreeModel.__init__(self)
        self.owner= owner
        self.bindings= owner.owner.bindings
        self.highlights= owner.owner.highlights
        
    def on_realize(self, tree, column0, model_sort):
        source= gobject.timeout_add(100, self.cb_highlights, tree, column0, model_sort)
        tree.connect_object('destroy', gobject.source_remove, source)
        
    @threadslock
    def cb_highlights(self, tree, column0, model_sort):
        d= self.highlights
        if d:
            for rowref, (count, is_new) in d.items():
                # Highlights counter is reduced.
                if count < 1:
                    del d[rowref]
                else:
                    d[rowref]= (count - 1, False)
                # TreeView area invalidation to trigger a redraw.
                if is_new or rowref not in d:
                    try:
                        path= self.on_get_path(rowref)
                    except ValueError:
                        # User craftily deleted the entry during highlighting.
                        pass
                    else:
                        path= model_sort.convert_child_path_to_path(path)
                        area= tree.get_background_area(path, column0)
                        tree.get_bin_window().invalidate_rect(area, False)
        return True

    def on_get_flags(self):
        return gtk.TREE_MODEL_LIST_ONLY|gtk.TREE_MODEL_ITERS_PERSIST
    def on_get_n_columns(self):
        return len(BindingListModel.column_types)
    def on_get_column_type(self, index):
        return BindingListModel.column_types[index]
    def has_default_sort_func(self):
        return False

    # Pure-list iteration
    #
    def on_get_iter(self, path):
        return self.bindings[path[0]] if self.bindings else None
    def on_get_path(self, rowref):
        return (self.bindings.index(rowref),)
    def on_iter_next(self, rowref):
        i= self.bindings.index(rowref)+1
        if i>=len(self.bindings):
            return None
        return self.bindings[i]
    def on_iter_children(self, rowref):
        if rowref is None and len(self.bindings)>=1:
            return self.bindings[0]
        return None
    def on_iter_has_child(self, rowref):
        return False
    def on_iter_n_children(self, rowref):
        if rowref is None:
            return len(self.bindings)
        return 0
    def on_iter_nth_child(self, rowref, i):
        if rowref is None and i<len(self.bindings):
            return self.bindings[i]
        return None
    def on_iter_parent(self, child):
        return None

    # Make column data from binding objects
    #
    column_types= [str, str, str, gtk.gdk.Pixbuf, str, str, str, str, str]
    def on_get_value(self, binding, i):
        if i<3: # invisible sort columns
            inputix= '%02x.%02x.%04x' % (Binding.SOURCES.index(binding.source), binding.channel, binding.control)
            methodix= '%02x' % Binding.METHODS.index(binding.method)
            targetix= '%02x.%02x' % (Binding.METHOD_GROUPS.index(binding.method[0]), binding.target)
            return ':'.join(((inputix, methodix, targetix), (methodix, targetix, inputix), (targetix, methodix, inputix))[i])
        elif i==3: # icon column
            return self.owner.source_icons[binding.source]
        elif i==4: # input channel/control column
            return binding.input_str
        elif i==5: # method column
            return binding.action_str
        elif i==6: # mode/value column
            return binding.modifier_str
        elif i==7: # target column
            return binding.target_str
        elif i==8: # background color column
            return "red" if binding in self.highlights else None

    # Alteration
    #
    def remove(self, iter):
        path= self.get_path(iter)
        del self.bindings[path[0]]
        self.row_deleted(path)
        self.owner.owner.update_lookup()
    def append(self, binding):
        path= (len(self.bindings),)
        self.bindings.append(binding)
        iter= self.get_iter(path)
        self.row_inserted(path, iter)
        self.owner.owner.update_lookup()
        return path
    def replace(self, iter, binding):
        path= self.get_path(iter)
        del self.bindings[path[0]]
        self.row_deleted(path)
        self.bindings.insert(path[0], binding)
        iter= self.get_iter(path)
        self.row_inserted(path, iter)
        self.owner.owner.update_lookup()
        return path

