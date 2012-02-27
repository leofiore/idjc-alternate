"""Preliminary initialisation stuff."""

#   Copyright (C) 2011 Stephen Fairchild (s-fairchild@users.sourceforge.net)
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


__all__ = ["ArgumentParserImplementation", "ProfileManager"]


import os
import sys
import argparse
import shutil
import tempfile
import time
import math
import fcntl
import re
import glob
import uuid
import datetime
import subprocess
from functools import partial
from collections import defaultdict

import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
DBusGMainLoop(set_as_default=True)
import glib

from idjc import FGlobs
from idjc import PGlobs
from ..utils import Singleton
from ..utils import PathStr


import gettext
t = gettext.translation(FGlobs.package_name, FGlobs.localedir, fallback=True)
_ = t.gettext



# The name of the default profile.
default = "default"


# Regular expressions of files to copy when cloning a profile.
config_files = ("config", "controls", "left_session", "main_session",
    "main_session_files_played", "main_session_tracks", "playerdefaults",
    "right_session", "s_data", "ports_.+_.+")


class ArgumentParserError(Exception):
    pass



class ArgumentParser(argparse.ArgumentParser):
    def error(self, text):
        raise ArgumentParserError(text)


    def exit_with_message(self, text):
        """This is just error on the superclass."""

        super(ArgumentParser, self).error(text)



class ArgumentParserImplementation(object):
    """To parse the command line arguments, if any."""

    __metaclass__ = Singleton


    def __init__(self, args=None, description=None, epilog=None):
        if args is None:
            args = sys.argv[1:]

        self._args = list(args)

        if description is None:
            description = PGlobs.app_longform

        ap = self._ap = ArgumentParser(description=description, epilog=epilog,
                                                                add_help=False)
        ap.add_argument("-h", "--help", action="help", help=_('show this help '
        'message and exit -- additional help is available on each of the '
        'sub-commands for example: "%(prog)s run --help" shows the help '
        'for the run command'))
        ap.add_argument("-v", "--version", action='version',
                version=FGlobs.package_name + " " + FGlobs.package_version,
                # TC: a command line option help string.
                help=_("show the version number and exit"))
        sp = self._sp = ap.add_subparsers()
        # TC: a command line option help string.

        sp_run = sp.add_parser("run", add_help=False, help=_("run the main "
        "idjc application -- this is the default when no command line options"
        " are specified"),
            # TC: do not translate run.
            description=description + " " + _("-- sub-command: run -- launch "
            "the idjc application"), epilog=epilog)

        # TC: a command line option help string.
        sp_new = sp.add_parser("new", add_help=False,
                                                help=_("make a new profile"),
            # TC: do not translate the word new.
            description=description + " " + _("-- sub-command: new -- "
            "make a new profile"), epilog=epilog)

        # TC: a command line option help string.
        sp_rm = sp.add_parser("rm", add_help=False, help=_("remove profile(s)"),
            # TC: do not translate the word rm.
            description=description + " " + _("-- sub-command: rm -- remove "
            "profile(s)"), epilog=epilog)

        # TC: a command line option help string.
        sp_auto = sp.add_parser("auto", add_help=False, help=_("select which "
        "profile is to automatically launch"),
            # TC: do not translate the word auto.
            description=description + " " + _("-- sub-command: auto -- mark a"
            " profile for auto-launch"), epilog=epilog)

        # TC: a command line option help string.
        sp_noauto = sp.add_parser("noauto", add_help=False,
                                                help=_("remove auto-launch"),
            description=description + " " + _("-- sub-command: noauto -- "
            "remove auto-launch"), epilog=epilog)

        # TC: a command line option help string.
        sp_ls = sp.add_parser("ls", add_help=False,
                                            help=_("list available profiles"),
            # TC: do not translate the word ls.
            description=description + " " + _("-- sub-command: ls -- list "
                                        "available profiles"), epilog=epilog)

        sp_run.add_argument("-h", "--help", action="help",
                                    help=_('show this help message and exit'))
        sp_run.add_argument("-d", "--dialog", dest="dialog", nargs=1,
                choices=("true", "false"),
                help=_("""force the appearance or non-appearance of the
                profile chooser dialog -- when used with the -p option
                the chosen profile is preselected"""))
        # TC: command line help placeholder.
        sp_run.add_argument("-p", "--profile", dest="profile", nargs=1,
                                                    metavar=_("profile_choice"),
                help=_("""the profile to use -- overrides the user interface
                preferences "show profile dialog" option"""))
        sp_run.add_argument("-j", "--jackserver", dest="jackserver", nargs=1,
                # TC: command line help placeholder.
                metavar=_("server_name"), help=_("the named jack sound-server "
                                                            "to connect with"))
        sp_run.add_argument("-S", "--session", dest="session", nargs=1,
                # TC: command line help placeholder.
                metavar=_("session_details"),
                help=_("e.g. 'L1:name' for a named Ladish [L1] session called "
                "'name' -- refer to the idjc man page for more details"))

        sp_run.add_argument("--no-jack-connections", dest="no_jack_connections",
                action="store_true",
                help=_('At start-up do not make any JACK connections. This '
                'option delegates all control over restored connections to '
                'the session handler.'))
        sp_run.add_argument("-C", "--no-default-jack-connections",
                        dest="no_default_jack_connections", action="store_true",
                help=_('No JACK ports will be connected except those listed in'
                ' the session file.'))

        group = sp_run.add_argument_group(_("user interface settings"))
        group.add_argument("-c", "--channels", dest="channels", nargs="+",
                metavar="c",
                help=_("the audio channels to have open at startup"))
        group.add_argument("-V", "--voip", dest="voip", nargs=1, choices=
                ("off", "private", "public"),
                help=_("the voip mode at startup"))
        group.add_argument("-P", "--players", dest="players", nargs="+",
                metavar="p",
                help="the players to start among values {1,2}")
        group.add_argument("-s", "--servers", dest="servers", nargs="+",
                metavar="s",
                help=_("attempt connection with the specified servers"))
        group.add_argument("-x", "--crossfader", dest="crossfader",
                choices=("1", "2"),
                help=_("position the crossfader for the specified player"))

        sp_new.add_argument("-h", "--help", action="help",
                                    help=_('show this help message and exit'))
        # TC: command line help placeholder.
        sp_new.add_argument("newprofile", metavar=_("profile_name"),
                help=_("""new profile name -- will form part of the dbus
                bus/object/interface name and the JACK client ID --
                restrictions therefore apply"""))
        # TC: command line help placeholder.
        sp_new.add_argument("-t", "--template", dest="template",
                                                metavar=_("template_profile"),
                help=_("an existing profile to use as a template"))
        # TC: command line help placeholder.
        sp_new.add_argument("-i", "--icon", dest="icon",
                metavar=_("icon_pathname"),
                help=_("pathname to an icon -- defaults to idjc logo"))
        # TC: Command line help placeholder for the profile's nickname.
        # TC: Profile names are very restricted in what characters can be used.
        sp_new.add_argument("-n", "--nickname", dest="nickname",
                metavar=_("nickname"),
                help=_("the alternate profile name to appear in window title"
                " bars"))
        sp_new.add_argument("-d", "--description", dest="description",
                metavar=_("description_text"),
                help=_("a description of the profile"))

        sp_rm.add_argument("-h", "--help", action="help",
                help=_('show this help message and exit'))
        sp_rm.add_argument("rmprofile", metavar=_("profile_name"), nargs="+",
                help=_('the profile(s) to remove'))

        sp_auto.add_argument("-h", "--help", action="help",
                help=_('show this help message and exit'))
        sp_auto.add_argument("autoprofile", metavar="profile_name",
                help=_('the profile to make automatic'))

        sp_noauto.add_argument("-h", "--help", action="help",
                help=_('show this help message and exit'))
        sp_noauto.add_argument("--dummyarg", dest="noauto",
                help=argparse.SUPPRESS)

        sp_ls.add_argument("-h", "--help", action="help",
                help=_('show this help message and exit'))
        sp_ls.add_argument("--dummyarg", dest="ls", help=argparse.SUPPRESS)


    def parse_args(self):
        try:
            return self._ap.parse_args(self._args)
        except ArgumentParserError as e:
            try:
                for cmd in self._sp.choices.iterkeys():
                    if cmd in self._args:
                        raise
                return self._ap.parse_args(self._args + ["run"])
            except ArgumentParserError:
                self._ap.exit_with_message(str(e))


    def error(self, text):
        self._ap.exit_with_message(text)


    def exit(self, status=0, message=None):
        self._ap.exit(status, message)



class DBusUptimeReporter(dbus.service.Object):
    """Supply uptime to other idjc instances."""


    interface_name = PGlobs.dbus_bus_basename + ".profile"
    obj_path  = PGlobs.dbus_objects_basename + "/uptime"


    def __init__(self):
        self._uptime_cache = defaultdict(float)
        self._interface_cache = {}
        # Defer base class initialisation.


    @dbus.service.method(interface_name, out_signature="d")
    def get_uptime(self):
        """Broadcast uptime from the current profile."""

        return self._get_uptime()


    def activate_for_profile(self, bus_name, get_uptime):
        self._get_uptime = get_uptime
        dbus.service.Object.__init__(self, bus_name, self.obj_path)


    def get_uptime_for_profile(self, profile):
        """Ask and return the uptime of an active profile.

        Step 1, Issue an async request for new data.
        Step 2, Return immediately with the cached value.

        Note: On error the cache is purged.

        Supports synchronous mode in the absence of an event loop.
        """


        def rh(retval):
            self._uptime_cache[profile] = retval


        def eh(exception):
            try:
                del self._uptime_cache[profile]
            except KeyError:
                pass
            try:
                del self._interface_cache[profile]
            except KeyError:
                pass


        try:
            interface = self._interface_cache[profile]
        except KeyError:
            try:
                p = dbus.SessionBus().get_object(PGlobs.dbus_bus_basename + \
                                                "." + profile, self.obj_path)
                interface = dbus.Interface(p, self.interface_name)
            except dbus.exceptions.DBusException as e:
                eh(e)
                return self._uptime_cache.default_factory()

            self._interface_cache[profile] = interface

        if glib.main_depth():
            # asynchronous: more CPU efficient but requires event loop
            interface.get_uptime(reply_handler=rh, error_handler=eh)
            return self._uptime_cache[profile]
        else:
            # synchronous
            return interface.get_uptime()



# Profile length limited for practical reasons. For more descriptive
# purposes the nickname parameter was created.
MAX_PROFILE_LENGTH = 18



def profile_name_valid(p):
    try:
        dbus.validate_bus_name("com." + p)
        dbus.validate_object_path("/" + p)
    except (TypeError, ValueError):
        return False
    return len(p) <= MAX_PROFILE_LENGTH



class ProfileError(Exception):
    """General purpose exception used within the ProfileManager class.

    Takes two strings so that one can be used for command line messages
    and the other for displaying in dialog boxes."""

    def __init__(self, str1, str2=None):
        Exception.__init__(self, str1)
        self.gui_text = str2



def profileclosure(cmd, name):
    """A factory function of sorts."""


    busbase = PGlobs.dbus_bus_basename
    def inner(profname):
        return cmd(".".join((busbase, profname)))
    inner.__name__ = name
    return staticmethod(inner)



class ProfileManager(object):
    """The profile gives each application instance a unique identity.

    This identity extends to the config file directory if present,
    to the JACK application ID, to the DBus bus name.
    """

    __metaclass__ = Singleton


    _profile = _dbus_bus_name = _profile_dialog = _init_time = None
    _iconpathname = PGlobs.default_icon

    _textoptionals = ("nickname", "description")
    _optionals = ("icon",) + _textoptionals


    def __init__(self):
        ap = ArgumentParserImplementation()
        args = ap.parse_args()

        try:
            if not os.path.isdir(PGlobs.profile_dir / default):
                self._generate_default_profile()

            if "newprofile" in args:
                self._generate_profile(**vars(args))
                ap.exit(0)
        except ProfileError as e:
            ap.error(_("failed to create profile: %s") % str(e))

        try:
            if "rmprofile" in args:
                self._delete_profile(None, args.rmprofile)
                ap.exit(0)
        except ProfileError as e:
            ap.error(_("failed to delete profile: %s") % str(e))

        try:
            if "autoprofile" in args:
                self._auto(None, args.autoprofile)
                ap.exit(0)
        except ProfileError as e:
            ap.error(_("auto failed: %s") % str(e))

        try:
            if "noauto" in args:
                self._noauto()
                ap.exit(0)
        except EnvironmentError as e:
            ap.error(_("noauto failed: %s") % e)

        self._uprep = DBusUptimeReporter()

        try:
            if "ls" in args:
                self._ls()
                ap.exit(0)
        except EnvironmentError as e:
            ap.error(_("ls failed: %s") % e)

        self._session_type, self._session_dir, self._session_name = \
                                                self._parse_session(ap, args)

        if self._session_dir is None:
            # Not in session mode so do the profile init stuff.

            profile = self.autoloadprofilename
            if profile is None:
                profile = default
                dialog_selects = True
            else:
                dialog_selects = False

            if args.profile is not None:
                profile = args.profile[0]
                dialog_selects = False
                if not profile_name_valid(profile):
                    ap.error(_("the specified profile name is not valid"))

            if args.dialog is not None:
                dialog_selects = args.dialog[0] == "true"

            if not dialog_selects and profile:
                if not profile_name_valid(profile):
                    ap.error(_('profile name is bad'))

                if profile not in os.walk(PGlobs.profile_dir).next()[1]:
                    ap.error(_('profile %s does not exist') % profile)

                if self._profile_has_owner(profile):
                    ap.error(_('profile %s is already running') % profile)

            self._profile_dialog = self._get_profile_dialog()
            self._profile_dialog.connect("delete", self._delete_profile)
            self._profile_dialog.connect("choose", self._choose_profile)

            def new_profile(dialog, profile, template, icon, nickname,
                                                                description):
                try:
                    self._generate_profile(profile, template, icon=icon,
                                    nickname=nickname, description=description)
                    dialog.destroy_new_profile_dialog()
                except ProfileError as e:
                    dialog.display_error(_("<span weight='bold' size='12000'>"
                        "Error while creating new profile.</span>\n\n%s") %
                        e.gui_text,
                        transient_parent=dialog.get_new_profile_dialog(),
                        markup=True)

            self._profile_dialog.connect("new", new_profile)
            self._profile_dialog.connect("clone", new_profile)
            self._profile_dialog.connect("edit", self._cb_edit_profile)
            self._profile_dialog.connect("auto", self._auto)
            self._profile_dialog.highlight_profile(profile, scroll=True)
            if dialog_selects:
                self._profile_dialog.run()
                self._profile_dialog.hide()
            else:
                self._choose_profile(self._profile_dialog, profile,
                                                                verbose=True)
            if self._profile is None:
                ap.error(_("no profile is set"))


    @property
    def profile(self):
        return self._profile


    @property
    def iconpathname(self):
        return self._iconpathname


    @property
    def dbus_bus_name(self):
        return self._dbus_bus_name


    @property
    def basedir(self):
        """The root save directory."""

        if self._session_dir is not None:
            return self._session_dir
        else:
            return PGlobs.profile_dir / self.profile


    @property
    def jinglesdir(self):
        """The directory for jingles storage."""

        return self.basedir / "jingles"


    @property
    def session_type(self):
        """Session mode: L0 for none, L1 for Ladish L1 mode."""

        return self._session_type


    @property
    def session_name(self):
        """The name of the session."""
        
        return self._session_name


    @property
    def ports_pathname(self):
        """Where to save jack session to and load it from."""

        return self.basedir / ("ports-%s-%s" % (
                                        self.session_type, self.session_name))


    @property
    def title_extra(self):
        """Window title text indicating which profile is in use."""

        if self.profile is not None:
            n = self._nickname
            if n:
                return "  (%s:%s)" % ((self.profile, n))
            else:
                if self.profile == default:
                    return ""
                return "  (%s)" % self.profile
        else:
            # TC: text appears in the title bar when in session mode.
            return "  (%s)" % _('session={type}:{name}').format(
                                type=self.session_type, name=self.session_name)


    @property
    def autoloadprofilename(self):
        """Which profile would automatically load if given the chance?"""

        al_profile = self._autoloadprofilename()
        if al_profile is None:
            return None

        try:
            profiledirs = os.walk(PGlobs.profile_dir).next()[1]
        except (EnvironmentError, StopIteration):
            return None

        return al_profile if al_profile in profiledirs else None


    @property
    def profile_dialog(self):
        return self._profile_dialog


    def get_uptime(self):
        if self._init_time is not None:
            return time.time() - self._init_time
        else:
            return 0.0


    @staticmethod
    def _parse_session(ap, args):
        """User supplied session details are parsed and checked for validity."""

        if args.session is None:
            # The None parameter below indicates profile mode is on and the
            # profile will determine the save directory, otherwise we return
            # the save directory instead.

            # L0 relates to Ladish [L0] mode which is an unmanaged session.
            # The final return value is the save location of the JACK port
            # connections file.
            # Since it's not a pathname it goes in the standard save directory.
            return "L0", None, "default"

        if ":" in args.session[0]:
            session_type, rest = args.session[0].split(":", 1)
            if ":" in rest:
                session_name, session_dir = rest.split(":", 1)
            else:
                session_name = rest
                session_dir = None
        else:
            session_type = args.session[0]
            session_name = "default"
            session_dir = None

        # Check validity of session_type and normalize it.
        supported_sessions = {"l0": "L0", "l1": "L1", "jack": "JACK"}
        try:
            session_type = supported_sessions[session_type.lower()]
        except KeyError:
            ap.error(_("unknown session type: %s: must be one of %s") %
                            (session_type, str(supported_sessions.values())))

        # The backend when started needs to know what session type we are using.
        os.environ["session_type"] = session_type

        if re.match("^[a-zA-Z0-9_]+$", session_name) is None:
            ap.error("session name must match [a-zA-Z0-9_]+")

        if session_dir is not None:
            session_dir = os.path.realpath(os.path.expanduser(session_dir))
            
            if not os.path.isdir(session_dir):
                ap.error(_('save directory does not exist: %s') % session_dir)
            
            # Make subdir for the actual save path based on the mode and name.
            session_dir = os.path.join(session_dir, "idjc-%s-%s" % (
                                                session_type, session_name))

            # Copy settings from a specified profile.
            if args.profile is not None:
                # Checks for profile validity.
                if not profile_name_valid(args.profile[0]):
                    ap.error(
                    _('specified profile is not valid %s') % args.profile[0])

                if not os.path.isdir(PGlobs.profile_dir / args.profile[0]):
                    ap.error(_('specified profile does not exist: %s') % \
                                                                args.profile[0])

                # Perform copy of profile data.
                try:
                    shutil.copytree(PGlobs.profile_dir / args.profile[0],
                                                                    session_dir)
                except EnvironmentError as e:
                    if e.errno != 17:
                        ap.error(
                        "failed to copy data from the profile directory: %s" % \
                                                                            e)

                # Delete files relating to JACK ports.
                try:
                    for each in glob.iglob(
                                        os.path.join(session_dir, "ports_*")):
                        os.unlink(each)
                except EnvironmentError as e:
                    print str(e)

            else:
                # Just make the empty session directory.
                try:
                    os.makedirs(session_dir)
                except EnvironmentError as e:
                    if e.errno != 17:
                        ap.error(
                        _('problem with specified session directory: %s') % e)

        if session_type == "JACK":
            try:
                uuid.UUID(args.jackserver[0])
            except TypeError:
                ap.error(
                _("session mode is JACK but no UUID specified to -j option"))

        return session_type, PathStr(session_dir), session_name


    def _autoloadprofilename(self):
        """Just the file contents without checking."""

        try:
            with open(PGlobs.autoload_profile_pathname) as f:
                fcntl.flock(f, fcntl.LOCK_EX)
                al_profile = f.readline().strip()
        except IOError:
            return None
        return al_profile


    def _auto(self, dialog, profile):
        if dialog is None and profile != default and not \
                                    os.path.isdir(PGlobs.profile_dir / profile):
            raise ProfileError(_('profile %s does not exist') % profile, None)

        try:
            with open(PGlobs.autoload_profile_pathname, "r+") as f:
                fcntl.flock(f, fcntl.LOCK_EX)
                al_profile = f.readline().strip()
                f.seek(0)
                if profile != al_profile or dialog is None:
                    f.write(profile)
                f.truncate()
        except IOError as e:
            if dialog is None:
                raise ProfileError(str(e), None)


    def _noauto(self):
        try:
            with open(PGlobs.autoload_profile_pathname, "r+") as f:
                fcntl.flock(f, fcntl.LOCK_EX)
                f.truncate()
        except IOError:
            pass


    def _cb_edit_profile(self, dialog, newprofile, oldprofile, *opts):
        busses = []

        try:
            try:
                busses.append(self._grab_bus_name_for_profile(oldprofile))
                if newprofile != oldprofile:
                    busses.append(self._grab_bus_name_for_profile(newprofile))
            except dbus.DBusException:
                raise ProfileError(None, _("Profile %s is active.") %
                                        (oldprofile, newprofile)[len(busses)])

            if newprofile != oldprofile:
                try:
                    shutil.copytree(PGlobs.profile_dir / oldprofile,
                                                PGlobs.profile_dir / newprofile)
                except EnvironmentError as e:
                    if e.errno == 17:
                        raise ProfileError(None,
                        _("Cannot rename profile {0} to {1}, {1} currently "
                                    "exists.").format(oldprofile, newprofile))
                    else:
                        raise ProfileError(None,
                            _("Error during attempt to rename {0} to {1}."
                                            ).format(oldprofile, newprofile))

                shutil.rmtree(PGlobs.profile_dir / oldprofile)

            for name, data in zip(self._optionals, opts):
                with open(PGlobs.profile_dir / newprofile / name, "w") as f:
                    f.write(data or "")

        except ProfileError, e:
            text = _("<span weight='bold' size='12000'>Error while editing "
                "profile: {0}.</span>\n\n{1}").format(oldprofile, e.gui_text)
            dialog.display_error(text, markup=True,
                            transient_parent=dialog.get_new_profile_dialog())
        else:
            dialog.destroy_new_profile_dialog()


    def _delete_profile(self, dialog, profiles):
        if isinstance(profiles, str):
            profiles = [profiles]
        if dialog is None or profiles[0] is not dialog.profile:
            busnames = []
            # Lock all specified profiles before deleting any.
            for profile in profiles:
                try:
                    busnames.append(self._grab_bus_name_for_profile(profile))
                except (dbus.DBusException, ValueError) as e:
                    if dialog is None:
                        raise ProfileError(_("could not get a lock on profile"
                                    " {0}: {1}").format(profile, str(e)), None)

            # Check all directories exist beforehand.
            if not any(os.path.isdir(PGlobs.profile_dir / x) for x in profiles):
                raise ProfileError(_('profile does not exist'))

            for profile in profiles:
                try:
                    shutil.rmtree(PGlobs.profile_dir / profile)
                except OSError as e:
                    if dialog is None:
                        raise ProfileError(e, None)

            del busnames

            if profile == default:
                self._generate_default_profile()


    def _choose_profile(self, dialog, profile, verbose=False):
        if dialog.profile is None:
            try:
                self._dbus_bus_name = self._grab_bus_name_for_profile(profile)
            except dbus.DBusException:
                if verbose:
                    print _("the profile '%s' is in use") % profile
            else:
                self._init_time = time.time()
                self._profile = profile
                self._nickname = self._grab_profile_filetext(
                                         profile, "nickname") or ""
                self._iconpathname = self._grab_profile_filetext(
                                         profile, "icon") or PGlobs.default_icon
                dialog.set_profile(
                                profile, self.title_extra, self._iconpathname)
                self._uprep.activate_for_profile(
                                self._dbus_bus_name, self.get_uptime)
        else:
            print "%s run -p %s" % (FGlobs.bindir /
                                                FGlobs.package_name, profile)
            subprocess.Popen([FGlobs.bindir / FGlobs.package_name,
                "run", "-p", profile], close_fds=True)


    def _generate_profile(self, newprofile, template=None, **kwds):
        if PGlobs.profile_dir is not None:
            if len(newprofile) > MAX_PROFILE_LENGTH:
                raise ProfileError(_("the profile length is too long "
                        "(max %d characters)") % MAX_PROFILE_LENGTH,
                        _("The profile length is too long (max %d characters).")
                        % MAX_PROFILE_LENGTH)

            if not profile_name_valid(newprofile):
                raise ProfileError(_("the new profile name is not valid"),
                        _("The new profile name is not valid."))

            try:
                busname = self._grab_bus_name_for_profile(newprofile)
            except dbus.DBusException:
                raise ProfileError(_("the chosen profile is currently running"),
                        _("The chosen profile is currently running."))

            try:
                tmp = PathStr(tempfile.mkdtemp())
            except EnvironmentError:
                raise ProfileError(_("temporary directory creation failed"),
                        _("Temporary directory creation failed."))

            try:
                if template is not None:
                    if not profile_name_valid(template):
                        raise ProfileError(
                            _("the specified template '%s' is not valid") %
                                                                    template,
                            _("The specified template '%s' is not valid.") %
                                                                    template)

                    tdir = PGlobs.profile_dir / template
                    if os.path.isdir(tdir):
                        for top, dirs, files in os.walk(tdir):
                            for filename in files:
                                for expr in self._optionals + config_files:
                                    if re.match(expr + "$", filename):
                                        try:
                                            shutil.copyfile(tdir / filename,
                                                                tmp / filename)
                                        except EnvironmentError as e:
                                            print e

                        shutil.copytree(tdir / "jingles", tmp / "jingles")
                    else:
                        raise ProfileError(
                            _("the template profile '%s' does not exist") %
                                                                    template,
                            _("The template profile '%s' does not exist.") %
                                                                    template)

                for fname in self._optionals:
                    if kwds.get(fname):
                        try:
                            with open(tmp / fname, "w") as f:
                                f.write(kwds[fname])
                        except EnvironmentError:
                            raise ProfileError(
                                        _("could not write file %s") + fname,
                                        _("Could not write file %s.") % fname)


                dest = PGlobs.profile_dir / newprofile
                try:
                    shutil.copytree(tmp, dest)
                except EnvironmentError as e:
                    if e.errno == 17 and os.path.isdir(dest):
                        msg1 = _("the profile directory '%s' already" \
                                                            " exists") % dest
                        msg2 = _("The profile directory '%s' already" \
                                                            " exists.") % dest
                    else:
                        msg1 = _("a non directory path exists at: '%s'") % dest
                        msg2 = _("A Non directory path exists at: '%s'.") % dest
                    raise ProfileError(msg1, msg2)
            finally:
                # Failure to clean up is not a critical error.
                try:
                    shutil.rmtree(tmp)
                except EnvironmentError:
                    pass


    def _generate_default_profile(self):
        self._generate_profile(default, description=_("The default profile"))


    def _profile_data(self):
        a = self._autoloadprofilename()
        d = PGlobs.profile_dir
        try:
            profdirs = os.walk(d).next()[1]
        except (EnvironmentError, StopIteration):
            return
        for profname in profdirs:
            if profile_name_valid(profname):
                files = os.walk(d / profname).next()[2]
                rslt = {"profile": profname}
                for each in self._optionals:
                    try:
                        with open(d / profname / each) as f:
                            rslt[each] = f.read()
                    except EnvironmentError:
                        rslt[each] = None

                rslt["active"] = self._profile_has_owner(profname)
                rslt["uptime"] = math.floor(self._uprep.get_uptime_for_profile(
                                                                    profname))
                rslt["auto"] = (1 if a == profname else 0)
                yield rslt


    def _ls(self):
        table = []
        for pd in self._profile_data():
            row = []
            row.append(pd["profile"])
            row.append("*" if pd["auto"] else " ")
            row.append(str(datetime.timedelta(seconds=pd["uptime"])))
            for each in self._textoptionals:
                row.append(self._grab_profile_filetext(pd["profile"], each) or
                                                                        "\b")
            table.append(row)

        for row in sorted(table):
            print "{1} {0:{5}} {2:>16} {3} {4}".format(*(tuple(row) +
                                                        (MAX_PROFILE_LENGTH,)))


    _profile_has_owner = profileclosure(dbus.SessionBus().name_has_owner,
                            "_profile_has_owner")

    _grab_bus_name_for_profile = profileclosure(partial(
        dbus.service.BusName, do_not_queue=True), "_grab_bus_name_for_profile")


    @staticmethod
    def _grab_profile_filetext(profile, filename):
        try:
            with open(PGlobs.profile_dir / profile / filename) as f:
                return f.readline().strip()
        except EnvironmentError:
            return None


    def _get_profile_dialog(self):
        from .profiledialog import ProfileDialog

        return ProfileDialog(default=default, data_function=self._profile_data)
