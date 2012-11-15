#   songdb.py: music database connectivity
#   Copyright (C) 2012 Stephen Fairchild (s-fairchild@users.sourceforge.net)
#             (C) 2012 Brian Millham (bmillham@users.sourceforge.net)
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


import time
import gettext
import threading
from functools import partial

import gobject
import gtk
try:
    import MySQLdb as sql
except ImportError:
    sql = None

from idjc import FGlobs
from .tooltips import set_tip
from .gtkstuff import threadslock, DefaultEntry


__all__ = ['MediaPane']

t = gettext.translation(FGlobs.package_name, FGlobs.localedir, fallback=True)
_ = t.gettext


class DBAccessor(threading.Thread):
    """A class to hide the intricacies of database access.
    
    When the database connection is dropped due to timeout it will silently 
    remake the connection and continue on with its work.
    """
    
    def __init__(self, hostnameport, user, password, database, notify=lambda m: 0):
        """The notify function must lock gtk before accessing widgets."""
        
        threading.Thread.__init__()
        try:
            hostname, port = hostnameport.rsplit(":", 1)
            port = int(port)
        except ValueError:
            hostname = hostnameport
            port = 3306  # MySQL uses this as the default port.

        self.hostname = hostname
        self.port = port
        self.user = user
        self.password = password
        self.database = database
        self.notify = notify
        self.handle = None  # No connections made until there is a query.
        self.cursor = None
        self.jobs = []
        self.semaphore = threading.Semaphore()
        self.lock = threading.Lock()
        self.keepalive = True
        start()

    def request(self, sql_query, handler, failhandler):
        """Add a request to the job queue.
        
        sql_query = str()
        def handler(sql cursor): implemented as a generator function with
                                 the yield acting as a cancellation point
                                 if processing a huge data set you want to
                                 allow cancellation once for each artist
        def failhandler(Exception instance)
        """
        
        self.jobs.append((sql_query, handler, failhandler))
        self.semaphore.release()
        
    def run(self):
        while self.keepalive:
            self.notify(_('Ready'))
            self.semaphore.acquire()
            if self.keepalive and self.jobs:
                query, handler, failhandler = self.jobs.pop(0)

                trycount = 0
                while trycount < 4:
                    try:
                        self.cursor.execute(*query)
                    except sql.OperationalError as e:
                        if self.keepalive:
                            # Unhandled errors will be treated like
                            # connection failures.
                            if self.handle.open and failhandler is not None:
                                failhandler(e)
                                break
                            else:
                                try:
                                    self.cursor.close()
                                except Exception:
                                    pass
                                    
                                try:
                                    self.handle.close()
                                except Exception:
                                    pass

                                raise
                        else:
                            break
                    except (sql.Error, AttributeError):
                        with self.lock:
                            if self.keepalive:
                                self.notify(_('Connecting'))
                                trycount += 1
                                try:
                                    self.handle = sql.connect(host=self.hostname,
                                        port=self.port, user=self.user,
                                        passwd=self.password, db=self.database,
                                        connect_timeout=3)
                                    self.cursor = self.handle.cursor()
                                except sql.Error as e:
                                    self.notify(_("Connection failed (try %d)") % i)
                                    print e
                                    time.sleep(0.5)
                                else:
                                    self.notify(_('Connected'))
                    else:
                        if self.keepalive:
                            self.notify(_('Processing'))
                            for dummy in handler(self.cursor):
                                if not self.keepalive:
                                    break
                        break
                
                else:
                    self.notify(_('Job dropped'))
 
        self.notify(_('Disconnected'))

    def close(self):
        """Clean up the worker thread prior to disposal."""
        
        self.keepalive = False
        self.semaphore.release()
        
        # If the thread is stuck on IO unblock it by closing the connection.
        # We should clean up in any event.
        with self.lock:
            try:
                self.cursor.close()
            except Exception:
                pass
                
            try:
                self.handle.close()
            except Exception:
                pass
            
        self.join()  # Hopefully this will complete quickly.
        self.jobs.clear()


class PrefsControls(gtk.Frame):
    """Database controls as visible in the preferences window."""
    
    def __init__(self):
        gtk.Frame.__init__(self)
        self.set_border_width(3)
        label = gtk.Label(" %s " % _('Prokyon3 or Ampache (song title) Database'))
        set_tip(label, _('You can make certain media databases accessible in IDJC for easy drag and drop into the playlists.'))
        self.set_label_widget(label)
        
        self._parameters = []  # List of widgets that should be made insensitive when db is active. 
        if not sql:
            # Feature is disabled.
            vbox = gtk.VBox()
            vbox.set_sensitive(False)
            vbox.set_border_width(3)
            label = gtk.Label(_('Python module MySQLdb required'))
            vbox.add(label)
            self.add(vbox)
            self.data_panel = gtk.VBox()  # Empty placeholder widget.
        else:
            # Control widgets.
            table = gtk.Table(5, 4)
            table.set_border_width(10)
            table.set_row_spacings(1)
            for col, spc in zip(xrange(3), (3, 10, 3)):
                table.set_col_spacing(col, spc)

            # Attachment for labels.
            l_attach = partial(table.attach, xoptions=gtk.SHRINK | gtk.FILL)
            
            # Top row.
            hostportlabel, self._hostport = self._factory(_('Hostname[:Port]'), 'localhost')
            l_attach(hostportlabel, 0, 1, 0, 1)
            table.attach(self._hostport, 1, 4, 0, 1)
            
            # Second row.
            hbox = gtk.HBox()
            hbox.set_spacing(3)
            fpmlabel, self._addchars = self._factory(_('File Path Modify'), None)
            adj = gtk.Adjustment(0.0, 0.0, 999.0, 1.0, 1.0)
            self._delchars = gtk.SpinButton(adj, 0.0, 0)
            self._parameters.append(self._delchars)
            set_tip(self._delchars, _('The number of characters to strip from the left hand side of media file paths.'))
            set_tip(self._addchars, _('The characters to prefix to the media file paths.'))
            l_attach(fpmlabel, 0, 1, 1, 2)
            minus = gtk.Label('-')
            hbox.pack_start(minus, False)
            hbox.pack_start(self._delchars, False)
            plus = gtk.Label('+')
            hbox.pack_start(plus, False)
            hbox.pack_start(self._addchars)
            table.attach(hbox, 1, 4, 1, 2)
            
            # Third row.
            userlabel, self._user = self._factory(_('User Name'), "admin")
            l_attach(userlabel, 0, 1, 3, 4)
            table.attach(self._user, 1, 2, 3, 4)
            dblabel, self._database = self._factory(_('Database'), "ampache")
            l_attach(dblabel, 2, 3, 3, 4)
            table.attach(self._database, 3, 4, 3, 4)
            
            # Fourth row.
            passlabel, self._password = self._factory(_('Password'), 'password')
            self._password.set_visibility(False)
            l_attach(passlabel, 0, 1, 4, 5)
            table.attach(self._password, 1, 2, 4, 5)
            self.dbtoggle = gtk.ToggleButton(_('Music Database'))
            self.dbtoggle.set_size_request(10, -1)
            self.dbtoggle.connect("toggled", self._cb_dbtoggle)
            table.attach(self.dbtoggle, 2, 4, 4, 5)
            
            # Notification row.
            self._statusbar = gtk.Statusbar()
            self._statusbar.set_has_resize_grip(False)
            gtk.gdk.threads_leave()
            self.notify(_('Disconnected'))
            gtk.gdk.threads_enter()
            table.attach(self._statusbar, 0, 4, 5, 6)
            
            self.add(table)
            self.data_panel = gtk.VBox()  # Bring in widget at some point.
            
        self.data_panel.set_no_show_all(False)
        self.show_all()

    @property
    def hostport(self):
        return self._hostport.get_text().strip()
        
    @property
    def user(self):
        return self._user.get_text().strip()
        
    @property
    def password(self):
        return self._password.get_text().strip()
        
    @property
    def database(self):
        return self._database.get_text().strip()
        
    @property
    def delchars(self):
        return self._delchars.get_value()
        
    @property
    def addchars(self):
        return self._addchars.get_text().strip()

    @threadslock
    def notify(self, message):
        """Intended for use by DBAccessor worker thread for status messages."""
        
        self._statusbar.push(1, message)
        self._statusbar.set_tooltip_text(message)  # To show long messages.

    def _cb_dbtoggle(self, widget):
        """Parameter widgets to be made insensitive when db is active."""
    
        sens = not widget.get_active()
    
        for each in self._parameters:
            each.set_sensitive(sens)

    def _factory(self, labeltext, entrytext=None):
        """Widget factory method."""
        
        label = gtk.Label(labeltext)
        label.set_alignment(1.0, 0.5)
        
        if entrytext:
            entry = DefaultEntry(entrytext, True)
        else:
            entry = gtk.Entry()
            
        entry.set_size_request(10, -1)
        self._parameters.append(entry)
        return label, entry
