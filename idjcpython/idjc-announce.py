#   idjc-announce.py: X-Chat plug-in for IDJC
#   Copyright (C) 2005-2007 Stephen Fairchild (s-fairchild@users.sourceforge.net)
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

__module_name__ = "idjc-announce"
__module_version__ = "1.2"
__module_description__ = "Announce tracks playing in idjc"

import xchat
import fcntl
import os, time

def listening(word, word_eol, userdata):        # Announce in the current channel
   global idjc                                  # the track now playing in idjc
   try:
      file = open(idjc + "songtitle")
      fcntl.flock(file.fileno(), fcntl.LOCK_EX) # File locking
      song = file.read()
      fcntl.flock(file.fileno(), fcntl.LOCK_UN)
      file.close()
   except IOError:
      print "Unable to read the songtitle file"
   else:
      xchat.command("me is listening to: " + song)
   return xchat.EAT_XCHAT                       # Processing of the command stops here

def execute_command(word, word_eol, userdata):
   if len(word_eol) > userdata:
      send, recv = os.popen2(word)
      send.close()
      output = recv.read()[:-1].splitlines()
      recv.close()
      if not output:
         print "No output. Is", word[0], "installed?"
      else:
         for line in output:
            xchat.command("say " + line)
   else:
      print "Not enough parameters"
   return xchat.EAT_XCHAT

def stop_cb(word, word_eol, userdata):
   global timeout_hook
   if timeout_hook is not None:                 # Check if we are announcing
      xchat.unhook(timeout_hook)                # Stop the timeout callback from running
      timeout_hook = None                       # Make timeout_hook reflect that fact
      print "Stopping IDJC annoucements."
   else:
      print "IDJC announcements are already stopped."
   return xchat.EAT_XCHAT

def start_cb(word, word_eol, userdata):
   global timeout_hook
   if timeout_hook is None:                             # Only start if we are curently stopped
      timeout_hook = xchat.hook_timer(1000, cb_timeout) # Cause cb_timeout to be run once a second
      print "Starting IDJC announcements."      # Prints to the currenly open X-Chat window.
   else:
      print "IDJC announcements are already started."
   return xchat.EAT_XCHAT

def unpack(text):                               # Unpacks the file which is in the format:
   start = 0                                    # d5:hellod3:byed2:ok <- would be 3 items
   item = 0                                     # d indicates that the file is not finished
   reply = list()                               # an x is added to help processing of the file
   text = text + "x"                            # the number between d and the next :
   while text[start] == "d":                    # is the size of the payload in bytes
      end = start                               # hello is 5 bytes for example
      while text[end] != ":":                   # When the x is hit we are done processsing
         end = end + 1                          
      nextstart = int(text[start + 1 : end]) + end + 1
      reply.append(text[ end+1 : nextstart ])
      start = nextstart
   return reply                                 # A list of the contents of the file is returned

def process_message_file_contents(text):
   nickmatch = chanmatch = 0
   text = unpack(text)                          # Turns the file into a list of its contents
   if int(text[3]) + 5 > time.time():           # Ignore old expired messages
      xchannellist = xchat.get_list("channels") # A list of all available X-Chat channels
      uchannellist = text[1].split(",")         # The user supplied list of channels
      for xchatchan in xchannellist:            # Iterate through the X-Chat channels
         if xchatchan.type == 2:                # Determine that the object is a channel (type 2)
            if xchatchan.context.get_info("nick") == text[0].strip():   # Match the nick
               nickmatch += 1
               for uchannel in uchannellist:    # Iterate through the user supplied channel list
                  if uchannel.strip() == xchatchan.channel:     # Match the channel
                     chanmatch += 1
                     # This next line sends the message to the channel using /msg
                     xchatchan.context.command("msg " + xchatchan.channel + " " + text[2])
      if chanmatch == 0:
         if nickmatch == 0:
            print "IDJC announce: no nicks were matched\nto stop announcements use the /stopannounce command"
         else:
            print "IDJC announce: no channels were matched\nto stop announcements use the /stopannounce command"
 
def process_idjc_message_file(pathname):
   try:                         
      file = open(pathname, "r+")               # Read and process the idjc announcements file
   except IOError:                              # Except when it doesn't exist of course.
      return
   fcntl.flock(file.fileno(), fcntl.LOCK_EX)    # File locking
   text = file.read()                           # The annoucements file is read in
   if len(text) > 0 and text[0] != "+":         # Check whether the file is already marked as read
      file.seek(0)                              # before marking the file as read with a +
      file.write("+")                           # at the beginning of the file
   fcntl.flock(file.fileno(), fcntl.LOCK_UN)    # File is unlocked and closed
   file.close()
   if len(text) > 0 and text[0] != "+":         # If the announcement message is not marked read
      process_message_file_contents(text)       # the message is processed
 
def cb_timeout(userdata):                       # This is run once a second by X-Chat
   global idjc                                  # The path to the ~/.idjc/ directory
   
   process_idjc_message_file(idjc + "announce.xchat")
   process_idjc_message_file(idjc + "timer.xchat")
   return 1

timeout_hook = None                             # Handle for callback timer
idjc = os.environ.get("HOME") + "/.idjc/"       # The file path of the ~/.idjc directory
xchat.hook_command("announce", start_cb)        # Adds X-Chat command /announce
xchat.hook_command("stopannounce", stop_cb)     # Adds X-Chat command /stopannounce
xchat.hook_command("listening", listening)      # Shows what the idjc listener is listening to
xchat.hook_command("cowsay", execute_command, 1)# This is really silly
start_cb(None, None, None)                      # Automatically start the annoucements
print "Commands are: /announce /stopannounce /listening"
