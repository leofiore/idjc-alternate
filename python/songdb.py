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
    
    def __init__(self, hostnameport, user, password, database):
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
        self.handle = None  # No connections made until there is a query.
        self.cursor = None
        self.jobs = []
        self.semaphore = threading.Semaphore()
        start()

    def request(self, sql_query, data_handler):
        self.jobs.append((sql_query, data_handler))
        self.semaphore.release()
        
    def run(self):
        while 1:
            self.semaphore.acquire()
            if self.jobs:
                query, handler = self.jobs.pop(0)
            
                try:
                    self.cursor.execute(*query)
                except dberror.OperationalError as e:
                    print "Query failed.", e
                    self.cursor.close()
                    self.handle.close()
                    raise
                except Exception:
                    for i in range(1, 4):
                        try:
                            self.handle = sql.connect(host=self.hostname,
                                port=self.port, user=self.user,
                                passwd=self.password, db=self.database,
                                connect_timeout=3)
                            self.cursor = self.handle.cursor()
                            self.cursor.execute(*query)
                        except dberror.OperationalError as e:
                            print "Database connection failed (try %d)." % i, e
                            time.sleep(1)
                        else:
                            break
                    else:
                        print "Database connection failed. Job dropped."        
                        continue

                handler(self.cursor)
