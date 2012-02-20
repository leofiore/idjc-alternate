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


class Singleton(type):
    """Enforce the singleton pattern upon the user class."""


    def __call__(cls, *args, **kwds):
        try:
            # Return an existing instance.
            return cls._instance

        except AttributeError:
            # No existing instance so instantiate just this once.
            cls._instance = super(Singleton, cls).__call__(*args, **kwds)
            return cls._instance



def _PA_rlock(func):
    """Policed Attributes helper for thread locking."""

    @wraps(func)
    def _wrapper(cls, *args, **kwds):
        rlock = type.__getattribute__(cls, "_rlock")

        try:
            rlock.acquire()
            return func(cls, *args, **kwds)

        finally:
            rlock.release()

    return _wrapper



class PolicedAttributes(type):
    """Polices data access to a namespace class.

    Prevents write access to attributes after they have been read.
    Envisioned useful for the implementation of "safe" global variables.
    """

    def __new__(meta, name, bases, _dict):
        @classmethod
        @_PA_rlock
        def peek(cls, attr, callback, *args, **kwds):
            """Allow read + write within a callback.

            Typical use might be to append to an existing string.
            No modification ban is placed or bypassed.
            """

            if attr not in super(type(cls), cls).__getattribute__("_banned"):
                new = callback(
                        super(PolicedAttributes, cls).__getattribute__(attr),
                        *args, **kwds)
                base.__setattr__(attr, new)

            else:
                raise NotImplementedError("variable is locked")

        _dict["peek"] = peek
        _dict["_banned"] = set()
        _dict["_rlock"] = threading.RLock()
        return super(PolicedAttributes, meta).__new__(meta, name, bases, _dict)


    @_PA_rlock
    def __getattribute__(cls, name):
        type.__getattribute__(cls, "_banned").add(name)
        return type.__getattribute__(cls, name)


    @_PA_rlock
    def __setattr__(cls, name, value):
        if name in type.__getattribute__(cls, "_banned"):
            raise NotImplementedError("value has already been read")

        type.__setattr__(cls, name, value)


    def __call__(cls, *args, **kwds):
        raise NotImplementedError("this class cannot be instantiated")



class FixedAttributes(type):
    """Implements a namespace class of constants."""


    def __setattr__(cls, name, value):
        raise NotImplementedError("value cannot be changed")


    def __call__(cls, *args, **kwds):
        raise NotImplementedError("this class cannot be instantiated")



class PathStr(str):
    """A data type to perform path joins using the / operator.

    In this case the higher precedence of / is unfortunate.
    """

    def __div__(self, other):
        return PathStr(os.path.join(str(self), other))


    def __add__(self, other):
        return PathStr(str.__add__(self, other))


    def __repr__(self):
        return "PathStr('%s')" % self



class slot_object(object):
    """A mutable object containing an immutable object."""


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
        return "slot_object(%s)" % repr(self.value)


    def __getattr__(self, what):
        def assign(value):
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
