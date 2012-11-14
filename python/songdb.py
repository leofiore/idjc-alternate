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

import gobject
import gtk
try:
    import MySQLdb as sql
    import _mysql_exceptions as dberror
except ImportError:
    sql = None

from idjc import FGlobs
from .tooltips import set_tip
from .gtkstuff import threadslock, DefaultEntry, LEDDict


__all__ = ['MediaPane']

t = gettext.translation(FGlobs.package_name, FGlobs.localedir, fallback=True)
_ = t.gettext


class DBAccessor(threading.Thread):
    """A class to hide the intricacies of database access.
    
    When the database connection is dropped due to timeout it will silently 
    remake the connection and continue on with its work.
    """
    
    def __init__(self, hostnameport, user, password, database, notify=lambda m:):
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

    def request(self, sql_query, data_handler):
        self.jobs.append((sql_query, data_handler))
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
                    except dberror.OperationalError as e:
                        if self.keepalive:
                            print e
                            if failhandler is not None:
                                failhandler()
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
                    except Exception:
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
                                except dberror.OperationalError as e:
                                    self.notify(_("Connection failed (try %d)") % i)
                                    print e
                                    time.sleep(0.5)
                                else:
                                    self.notify(_('Connected'))
                    else:
                        break
 
                self.notify(_('Processing'))
                while self.keepalive and handler(self.cursor):
                    pass
                    
        self.notify(_('Disconnected'))

    def close(self):
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
