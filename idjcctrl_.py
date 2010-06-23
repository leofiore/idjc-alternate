#! /path/to/python

#   idjcctrl(_): Issue commands to IDJC with this script
#   Copyright (C) 2007 Stephen Fairchild
#
#   This program is free software; you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation; either version 2 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program; if not, write to the Free Software
#   Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301  USA

import os, sys, fcntl

home = os.environ["HOME"]
idjc = home + "/.idjc/"
commandfile = idjc + "command"
argv = sys.argv[1:]

allowed_commands = ( "--play",
                     "--enqueue",
                     "--connect",
                     "--disconnect",
                     "--request_left",
                     "--request_right",
                     "--testmonitor_on",
                     "--testmonitor_off",
                     "--record_start",
                     "--record_stop",
                     "--update" )

def usage():
   print "commands are:", allowed_commands
   print "usage: idjcctrl [--play] [--enqueue] file1.mp3 file2.m3u"
   print "or     idjcctrl [--connect] [--record_start] 1 2"
   sys.exit(5)

def write_out_file(command, listoffiles):
   try:
      file = open(commandfile, "r+")
   except:
      print "idjcctrl: unable to open the command file for writing (is idjc running?)"
      sys.exit(5)
   else:
      fcntl.flock(file.fileno(), fcntl.LOCK_EX)
      try:
         file.seek(0, 2)
         file.write("[%s %d]\n" % (command, len(listoffiles)))
         for each in listoffiles:
            file.write(each + "\n")
      except IOError:
         print "idjcctrl: failure to write to the command file"
         sys.exit(5)
      fcntl.flock(file.fileno(), fcntl.LOCK_UN)
      file.close()

if len(argv) > 0 and argv[0] in allowed_commands:
   write_out_file(argv[0], argv[1:])
else:
   usage()
