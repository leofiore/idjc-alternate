"""Generally useful Python code.

But strictly no third party module dependencies.
"""

#   Copyright (C) 2011 Stephen Fairchild (s-fairchild@users.sourceforge.net)
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


__all__ = ["Singleton", "PolicedAttributes", "FixedAttributes",
                "PathStr", "SlotObject", "string_multireplace"]


import os
import threading
from functools import wraps


# pylint: disable=C0203
#
# The mcs parameter goes to the __new__ method, not any other.


class Singleton(type):
    """Enforce the singleton pattern upon the user class."""


    def __init__(cls, name, bases, dict_):
        super(Singleton, cls).__init__(name, bases, dict_)
        cls._instance = None


    def __call__(cls, *args, **kwds):
        if cls._instance is not None:
            # Return an existing instance.
            return cls._instance

        else:
            # No existing instance so instantiate just this once.
            cls._instance = super(Singleton, cls).__call__(*args, **kwds)
            return cls._instance



def _pa_rlock(func):
    """Policed Attributes helper for thread locking."""

    @wraps(func)
    def _wrapper(cls, *args, **kwds):
        """Wrapper with locking feature. Performs rlock."""
        
        rlock = type.__getattribute__(cls, "_rlock")

        try:
            rlock.acquire()
            return func(cls, *args, **kwds)

        finally:
            rlock.release()

    return _wrapper



class FixedAttributes(type):
    """Implements a namespace class of constants."""


    def __setattr__(cls, name, value):
        raise AttributeError("attribute is locked")


    def __call__(cls, *args, **kwds):
        raise TypeError("%s object is not callable" % cls.__name__)



class PolicedAttributes(FixedAttributes):
    """Polices data access to a namespace class.

    Prevents write access to attributes after they have been read.
    Envisioned useful for the implementation of "safe" global variables.
    """

    def __new__(mcs, name, bases, dict_):
        @classmethod
        @_pa_rlock
        def peek(cls, attr, callback, *args, **kwds):
            """Allow read + write within a callback.

            Typical use might be to append to an existing string.
            No modification ban is placed or bypassed.
            """

            if attr not in type.__getattribute__(cls, "_banned"):
                new = callback(
                        super(PolicedAttributes, cls).__getattribute__(attr),
                        *args, **kwds)
                type.__setattr__(attr, new)

            else:
                raise AttributeError("attribute is locked")

        dict_["peek"] = peek
        dict_["_banned"] = set()
        dict_["_rlock"] = threading.RLock()
        return super(PolicedAttributes, mcs).__new__(mcs, name, bases, dict_)


    @_pa_rlock
    def __getattribute__(cls, name):
        type.__getattribute__(cls, "_banned").add(name)
        return type.__getattribute__(cls, name)


    @_pa_rlock
    def __setattr__(cls, name, value):
        if name in type.__getattribute__(cls, "_banned"):
            FixedAttributes.__setattr__(cls, name, value)

        type.__setattr__(cls, name, value)



class PathStrMeta(type):
    """PathStr() returns None if called with None."""
    
    def __call__(cls, arg):
        if arg is None:
            return None
        else:
            return cls.__new__(cls, arg)



class PathStr(str):
    """A data type to perform path joins using the / operator.

    In this case the higher precedence of / is unfortunate.
    """

    # pylint: disable=R0904


    __metaclass__ = PathStrMeta


    def __div__(self, other):
        return PathStr(os.path.join(str(self), other))


    def __add__(self, other):
        return PathStr(str.__add__(self, other))


    def __repr__(self):
        return "PathStr('%s')" % self



class SlotObject(object):
    """A mutable object containing an immutable object."""


    # pylint: disable=R0903


    __slots__ = ['value']


    def __init__(self, value):
        self.value = value


    def __str__(self):
        return str(self.value)


    def __int__(self):
        return int(self.value)


    def __float__(self):
        return float(self.value)


    def __repr__(self):
        return "SlotObject(%s)" % repr(self.value)


    def __getattr__(self, what):
        """Universal getter for get_ prefix."""
        
        def assign(value):
            """Returned by set_ prefix call. A setter function."""
            
            self.value = value

        if what.startswith("get_"):
            return lambda : self.value

        elif what.startswith("set_"):
            return assign

        else:
            object.__getattribute__(self, what)



def string_multireplace(part, table):
    """Replace multiple items in a string.

    Table is a sequence of 2 tuples of from, to strings.
    """

    if not table:
        return part

    parts = part.split(table[0][0])
    t_next = table[1:]

    for i, each in enumerate(parts):
        parts[i] = string_multireplace(each, t_next)

    return table[0][1].join(parts)
