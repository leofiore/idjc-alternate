# -*- encoding: utf-8 -*-
#   Set your text editor to UTF-8 before modifying this file

#   en_US_text.py: IDJC language localisation file for en_US
#   Copyright (C) 2008 Stephen Fairchild (s-fairchild@users.sourceforge.net)
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
#   If not, see <http://www.gnu.org/licenses/>

#   T h e   f o l l o w i n g   a r e   r e g u l a r   t r a n s l a t i o n s 
 
announce_tip = "Enter the message you want to send here. To include the track currently playing use %s. You can also include colors using Ctrl+K (standard X-Chat/mIRC method) or from the context menu (right click)."

ask_profile_tip = "Causes a profile selection dialog box to appear when IDJC is started which allows you to have an unlimited number of settings for DJing on multiple radio stations."

insert_attribute_or_colour_code = "Insert Attribute or Color Code"

licence_tab = "License"

mixer_crash = "The mixer module crashed during initialization."

no_mp3_stream_available_tip = """Due to concerns over software patents or through oversight, the person or organization who compiled this program neglected to include support for mp3 encoding.
 
In order to stream mp3 with Shoutcast you need to either locate and install an unrestricted IDJC package or failing that, compile your own from source."""

playlist_modes_tip = """This sets the playlist mode which defines player behavior after a track has finished playing.

'Play All' is the most versatile mode since it allows the use of embeddable playlist control elements which are accessible using the right click context menu in the playlist. When no playlist controls are present the tracks are played sequentially until the end of the playlist is reached at which point the player will stop.

'Loop All' causes the tracks to be played in sequence, restarting with the first track once the end of the playlist is reached.

'Random' causes the tracks to be played indefinitely with the tracks selected at random.

'Manual' causes the player to stop at the end of each track.

'Cue Up' is similar to manual except that the next track in the playlist will also be highlighted."""

record_tab_tip = "Each one of these tabs represents a separate stream recorder. The LED indicator colors represent the following: Clear=Stopped Yellow=Paused Red=Recording."

record_tip = """Start recording.

If this button is grayed out it means that the encoder settings are not valid. This can be fixed by using one of the approved sample rates for mp3 or by choosing a sensible samplerate and bitrate combination for Ogg.

Also check that you have write permission on the folder you have selected to record to."""

rg_defaultgain_tip = "Set this to the typical track gain values you would expect for the program material you are currently playing. For pop and rock music (especially modern studio recordings) this should be about a -8 or -9 and classical music much closer to zero."

server_connect_tip = """Connect to or disconnect from the radio server. If the button does not stay in, the connection failed for some reason.
 
If the button is grayed out it means you are using unsupported settings. Shoutcast only supports mp3 and mp3 requires that you use one of the samplerates in the drop down box. Ogg only supports certain sample rate, bitrate, and stereo combinations. Also, the connection list must contain details for a master server."""

stream_normalizer = "Stream Normalizer"

stream_tab_tip = "Each one of these tabs represents a separate radio streamer. The LED indicator colors represent the following: Clear=No connection Yellow=Awaiting authentication. Green=Connected. Flashing=Packet loss due to a bad connection."

update_encoder_settings_tip = """Use this to change the encoder settings while streaming or recording.
 
If this button is grayed out it means that the encoder is not running, or the bitrate/samplerate combination is not supported by the encoder, or you are trying to switch between Ogg and mp3, which is not permitted."""

xchat_colours = "Colors"

#   U n t r a n s l a t e d   i t e m s   - -   s a m e   a s   e n _ G B 
 
#about_tab = "About"

#add_file = "Add Music"

#add_to_jingles = "Add To Jingles"

#add_track_tip = "Add tracks to the playlist."

#advance_tip = "This button either starts the currently highlighted track playing or stops the currently playing one and highlights the next track."

#af_h_sm = "Audio Filter, Headroom, and Stereo Mix"

#af_mild_tip = "A moderate bass cut filter for noisy environments or boomy microphones."

#af_off_tip = "This turns off the bass cut filter and is the normally recommended setting."

#af_sharp_tip = "This bass cut filter is provided for people who have severe mains hum or an infrasound problem due to poor audio components."

#agc_compressor = "Compressor"

#agc_controls = "Processed Audio Controls"

#agc_cutoff = "Cutoff Frequency"

#agc_deessbias = "Bias"

#agc_deesser = "De-esser"

#agc_ducker = "Ducker"

#agc_duckhold = "Hold"

#agc_duckrelease = "Release"

#agc_gain = "Gain"

#agc_hfdetail = "HF Detail"

#agc_hfmulti = "Effect"

#agc_highpass = "High Pass Filter"

#agc_left = "Left"

#agc_level = "Level"

#agc_lfdetail = "LF Detail"

#agc_lfmulti = "Effect"

#agc_limit = "Limit"

#agc_nggain = "Gain"

#agc_ngthresh = "Threshold"

#agc_noisegate = "Noise Gate"

#agc_other_options = "Options"

#agc_phaserotator = "Phase Rotator"

#agc_ratio = "Boost"

#agc_right = "Right"

#all = "All"

#app_exit_tip = "When IDJC exits run the commands to the right."

#app_start_tip = "When IDJC starts run the commands to the right."

#append = "Append"

#append_cursor = "Append Cursor"

#ask_profile = "At startup ask which profile to use"

#attenuate_left_tip = "Use this to attenuate the left microphone signal so that it matches the signal level of the right microphone. Use this when the left microphone signal is generally stronger than the right."

#attenuate_right_tip = "Use this to attenuate the right microphone signal so that it matches the signal level of the left microphone. Use this when the right microphone signal is generally stronger than the left."

#attenuation = "Atten."

#audio_meters = "Meters"

#auto = "Auto"

#auto_start_player_tip = "Have one of the players start automatically when a radio server connection is successfully made."

#auto_start_recorder_tip = "Have a recorder start automatically when a radio server connection is successfully made."

#auto_tip = "Use default jack audio routing"

#autoshutdown = ('An automatic server disconnection occurred.', 'Disconnection was caused by a timer.')

#aux_off_tip = "Each time the auxiliary input is turned off run the commands to the right."

#aux_on_tip = "Each time the auxiliary input is turned on run the commands to the right."

#aux_toggle_tip = "Mix auxiliary audio to the output stream. See also Prefs->JACK Ports Aux L and Aux R."

#auxinput_control_menu = "Switch to Aux"

#basic_streamer = "Basic Streamer"

#basic_streamer_tip = "Run in a reduced functionality mode that lowers the burden on the CPU and takes up less screen space."

#bass_cut = "Bass cut:"

#best_quality_resample = "Highest"

#big_box_toggle = "Enlarge the time elapsed/remaining windows"

#bind_to = "Bind To"

#bitrate = "Bitrate"

#bitrate_tip = "The bit-rate in kilobits per second."

#block_size = "Block size"

#centre_pbspeed_tip = "This sets the playback speed back to normal."

#channels = "Channels:"

#common_volume_control_tip = "The volume control shared by both music players."

#comp_attack = "Attack"

#comp_bar = "Comp"

#comp_bar_toggle = "Microphone Compression Level"

#comp_de_ess = "De-ess"

#comp_depth = "Depth"

#comp_duckhold = "Hold"

#comp_ducking = "Ducking"

#comp_gain = "Gain"

#comp_knee = "Knee"

#comp_manual = "Manual"

#comp_ratio = "Ratio"

#comp_relative = "Relative"

#comp_release = "Release"

#compression_meter_tip = "A meter indicating the current amount of attenuation being applied to each microphone input by the compressor."

#connected_to_history = "connected to"

#connection = " Connection "

#connection_lost = "Connection Lost"

#contact_info = " Shoutcast Contact Info "

#control_menu = "Insert control"

#copy = "Copy"

#count_down = "Count Down"

#count_up = "Count Up"

#cross_left_tip = "Move the crossfader fully left."

#cross_middle_tip = "Move the crossfader to the middle of its range of travel."

#cross_pattern_tip = "This changes the response curve of the crossfader."

#cross_right_tip = "Move the crossfader fully right."

#crossfade_control_ltr_element = ">>> Fade across >>>"

#crossfade_control_menu = "Crossfade"

#crossfade_control_rtl_element = "<<< Fade across <<<"

#crossfader = "Crossfader"

#crossfader_tip = "The crossfader."

#crosspass = "Pass"

#cue_up = "Cue Up"

#dbalbum = "Album"

#dbartist = "Artist"

#dbbitrate = "Bitrate"

#dbcollapse = "_Collapse"

#dbduration = "Duration"

#dbexpand = "_Expand"

#dbfilename = "Filename"

#dbfilters = " Filters "

#dbfound = "(%d)"

#dbfuzzysearch = "Fuzzy Search"

#dbpath = "Path"

#dbtitle = "Title"

#dbtrack = "Track"

#dbunknown = "<unknown>"

#dbwhere = "WHERE"

#default_normalizer_tip = "Load the recommended settings."

#delete_mode_tip = "This button toggles delete mode which allows the removal of tracks from the playlist by mouse clicking them."

#description = "Description:"

#description_tip = "A description of your radio station."

#digiprogress_tip = "Left click toggles between showing the amount of time elapsed or remaining on the current track being played."

#discon_warn = ('You will be automatically disconnected from', 'the server one minute from now.')

#disconnected = "IDJC Disconnected"

#disconnected_history = "disconnected from server"

#disconnection = "IDJC Disconnection"

#dither_tip = "This feature possibly improves the sound quality a little when listening on a 24 bit sound card."

#dither_toggle = "Apply triangular shaped dither to FLAC playback"

#dj_alarm_tip = "An alarm tone alerting the DJ that dead-air is just nine seconds away."

#dj_alarm_toggle = "Sound an alarm when the music is due to end"

#dj_audio_level = "DJ Aud Level"

#dj_audio_tip = "This adjusts the sound level of the DJ audio."

#dj_name = "DJ Name:"

#dj_name_tip = "Enter your DJ name or station name here. Typically this information will be displayed by listener clients."

#dnr_compressor = "Dynamic Range Compressor"

#down_arrow_tip = "This moves the highlighted track down the playlist order."

#drc_attack_tip = "The speed at which signal attenuation is applied. Lower equals faster and is a time constant in milliseconds. A very low number would be more responsive but will remove punchiness from the voice. A sensible setting would be 2.25ms provided the 30ms RMS filter is in use."

#drc_deess_tip = "This reduces the impact of S T and P sounds by providing a second audio signal path to the compressor which performs a kind of audio processing to isolate those sounds. The higher the De-ess figure the more dominant this second audio path becomes. Making a test recording is the best way to find the ideal level however values above 10 are probably not sensible but are included for illustrating the full effect."

#drc_depth_tip = "When the setting is anything other than zero, this feature provides what is known as soft knee compression so that the compression ratio ramps up gradually with an increasing audio level rather than suddenly being applied at the 'Knee' point. This makes for a more natural sound and is recommended for compressing the human voice. A sensible value would be 27. Using 0 results in what is known in compressor jargon as hard knee compression. It is recommended to set this value before calibrating 'Knee' since there is interaction between the two settings."

#drc_ducking_hold_tip = "This is the time delay in milliseconds before ducking attenuation starts to be released. A sensible figure would be 680ms but the ideal figure depends to some extent on your speaking style."

#drc_ducking_ratio_tip = "Ducking is a feature that reduces the sound level of the music players when the DJ is talking with the microphone on. This allows the DJ to talk over the music with ease and works by taking the amount of signal attenuation applied by the compressor and multiplying it by the ducking factor (note: this widget controls the ducking factor) to calculate a level of attenuation to apply to the music players. A sensible level would be 1.6 but it largely depends on how much compression you are using."

#drc_filter_3 = "This input filter computes the average (RMS) signal strength over a period of 3 milliseconds."

#drc_filter_30 = "This input filter computes the average (RMS) signal strength over a period of 30 milliseconds which gives a response generally considered more suitable for regulating human voice."

#drc_gain = "The amount of signal boost in dB to apply to the audio signal after compression. Related: Relative and Manual below."

#drc_gain_manual_tip = "The gain figure above will be applied in an absolute fashion taking no account of compressor settings"

#drc_gain_relative_tip = "The gain figure above will be in addition to a computed sensible gain-level-boost based on how the compressor is configured."

#drc_knee_tip = "The audio signal level in dB above which the full amount of compression specified in 'Ratio' is applied. A sensible level for this should be determined by trial and error with an aim to have the peak microphone level close to 0dB."

#drc_ratio_tip = "Adjusts the compression ratio applied to the microphone input. The bigger the number the more compressed the sound. A sensible value for this would be 3 or 3.5. To deactivate this feature choose 0. Consult the web for more information on the subject of 'dynamic range compression'."

#drc_release_tip = "Release is the opposite of attack and relates to how quickly the compressor releases signal attenuation when the microphone signal level drops. The higher this figure the longer it takes. A sensible setting would be 180ms. Too high a figure will result in an audio artifact known as compressor pump where the sound level changes in a notably rhythmic fashion."

#duplicate = "Duplicate"

#elapsed_recording = "Elapsed:"

#empty = "Empty"

#enable = "Enable"

#enable_message_timer_tip = "This widget enables the IRC message timer which broadcasts a message periodically to the specified channels."

#enable_stream_normalizer_tip = "This feature is provided to make the various pieces of music that are played of a more uniform loudness level which is standard practice by 'real' radio stations. The default settings are likely to be sufficient however you may adjust them and you can compare the effect by clicking the 'Monitor Mix' 'Stream' button in the main application window which will allow you to compare the processed with the non-processed audio."

#enable_tooltips = "Enable tooltips"

#enable_tooltips_tip = "This, what you are currently reading, is a tooltip. This feature turns them on or off."

#enable_track_announcer_tip = "This widget enables the track announcer which is a facility for announcing new tracks on IRC (internet relay chat) using the X-Chat IRC client. For full instructions on how to use this feature refer to the IDJC documentation in the doc folder or to the IDJC homepage."

#encoding = " Encoding "

#encoding_quality = "Quality (0=best)"

#enlarge_time_elapsed_tip = "The time elapsed/remaining windows sometimes don't appear big enough for the text that appears in them due to unusual DPI settings or the use of a different rendering engine. This option serves to fix that."

#event_tab = "Event"

#exchange = "Exchange"

#fadeout_toggle = "Fadeout"

#fall = "Fall"

#fast_resample = "Fast"

#fastest_resample = "Fastest"

#feature_disabled = "Feature Disabled"

#feature_set = "Feature Set"

#filter_fast = "3ms RMS"

#filter_slow = "30ms RMS"

#finish = "Finish"

#flac16_tip = "The ideal bit width for streaming assuming you have the bandwidth to spare."

#flac20_tip = "Ideal for very high quality streaming or recording although not as compatible as 16 bit."

#flac24_tip = "The highest quality audio format available within IDJC. Recommended for pre-recording."

#flac_bitrates = ('16 Bit', '20 Bit', '24 Bit')

#flac_streamtab_tip = "This chooses the OggFLAC format for streaming and recording."

#flacmetadata = "Metadata"

#flacmetadata_tip = "You can prevent the sending of metadata by turning this feature off. This will prevent certain players from dropping the stream or inserting an audible gap every time the song title changes."

#format = " Format "

#format_info_bar_tip = "Information about how the encoder is currently configured is displayed here."

#formats = " Supported Media Formats "

#from_here = "From Here"

#fully_featured = "Fully Featured"

#fully_featured_tip = "Run in full functionality mode which uses more CPU power."

#general_tab = "General"

#genre = "Genre:"

#genre_tip = "The musical genres you are likely to play."

#good_quality_resample = "Good"

#green_phone_tip = "Mix voice over IP audio to the output stream."

#headroom = "Player headroom when the microphone is open (dB)"

#headroom_tip = "The number of dB to reduce the music players' sound level by when the microphone is switched on. A sensible setting would be 3.0 or even higher if you are not going to use ducking."

#high_quality_abbrev = "HQ"

#hostname = "Hostname"

#hostname_tip = """The hostname of the server.
#Example 1: 192.168.1.4
#Example 2: localhost"""

#hysteresis = "Hyster."

#icy_aim = "AIM:"

#icy_aim_tip = "Connection info for AOL instant messenger goes here."

#icy_icq = "ICQ:"

#icy_icq_tip = "ICQ instant messenger connection info goes here."

#icy_irc = "IRC:"

#icy_irc_tip = "Internet Relay Chat connection info goes here."

#id3_tag = "ID3 Tag"

#idjc_launch_failed = "IDJC Launch Failed"

#idjc_shutdown = "IDJC Shutdown"

#initial_player_settings = "Player Settings At Startup"

#interval = "Interval:"

#invert_left = "Invert left mic audio"

#invert_left_tip = "Performs phase inversion on the left microphone signal. Use this to make both microphones be in phase with one another and to affect phase in relation to your voice with respect to the headphones."

#invert_right = "Invert right mic audio"

#invert_right_tip = "Performs phase inversion on the right microphone signal. Use this to make both microphones be in phase with one another and to affect phase in relation to your voice with respect to the headphones."

#irc_channels_tip = "A comma separated list of IRC channels. Some IRC servers require that you also be logged into the channel before you can announce there."

#irc_message_timer = "IRC Message Timer"

#is_recording = "IDJC is currently recording."

#is_streaming = "IDJC is currently streaming."

#item_menu = "Item"

#jack_connection_failed = """The JACK sound server needs to be running in order to run IDJC.
#In order to manually start it try something like:
#
#       $ jackd -d alsa -r 44100 -p 2048
#
#If you would like JACK to start automatically with your user specified parameters try something like this, which will create a file called .jackdrc in your home directory:
#
#       $ echo "/usr/bin/jackd -d alsa -r 44100" > ~/.jackdrc
#
#If you have already done this it is possible another application or non-JACK sound server is using the sound card.
#
#Possible remedies would be to close the other audio app or configure the sound server to go into suspend mode after a brief amount of idle time.
#
#If you are trying to connect to a named jack server, either set the environment variable JACK_DEFAULT_SERVER to that name or launch IDJC with the -j jackservername option. For example:
#
#        $ jackd -n xyzzy -d alsa -r 44100 -p 2048 &
#        $ idjc -p profilename -j xyzzy"""

#jack_entry = """Enter the name of the JACK audio port with which to bind and then click the set button to the right.
#Typing 'jack_lsp -p' in a console will give you a list of valid JACK audio ports. Note that inputs will only bind to output ports and outputs will only bind to input ports."""

#jack_ports_tab = "Jack Ports"

#jingles_button = "Jingles"

#jingles_entry_tip = "Specify a multiple jingles play order by adding the corresponding index number to a comma separated list here. Alternatively just double click the entries in the playlist that you want to add."

#jingles_playlist_tip = "The jingles playlist. To add files here you can do so from one of the main media players by using the right click menu and selecting Add To Jingles from the Item submenu."

#jingles_volume_tip = "This adjusts the volume level of the jingles player."

#jingles_window = "IDJC Jingles"

#jingles_window_open_tip = "Open the jingles player window."

#keep_password_tip = "Choosing this option will cause the server passwords to be saved to the IDJC configuration file so they will be there when you next restart IDJC. If this is a security concern to you it would be wise to keep this feature turned off. Those doing so will have to type in their server passwords each time IDJC is run."

#keeppass = "Remember server passwords (potential security risk)"

#l = "L"

#latency = "Latency:"

#left = "Left:"

#left_mic_stereo_tip = "This controls the stereo balance of the left microphone."

#left_playlist_addition = "Add music to left playlist"

#left_playlist_save = "Save left playlist"

#level = "Level"

#listen = " Listen "

#listen_tip = "Make output from this player audible to the DJ."

#listen_url = "Listen URL:"

#listen_url_tip = "The URL of your radio station. This and the rest of the information below is intended for display on a radio station listings website."

#lmic_toggle_tip = "This button toggles the left microphone input."

#localhost = "Localhost"

#login_tip = "Icecast servers can be configured to have individual per-user source passwords to facilitate efficient password revocation. This requires that every user must have a separate login name which is entered here. The default login name is 'source'."

#loop_all = "Loop All"

#lower_vorbis = "Lower %"

#make_public = "Make Public"

#make_public_tip = "Publish your radio station on a listings website. The website in question will depend on how the server to which you connect is configured."

#manual = "Manual"

#media_flat = "Flat"

#media_tree = "Tree"

#media_viewer_title = " P3 Database View (%s) "

#mediafilter_all = "Supported media"

#message = "Message:"

#message_timer_interval = "The time period in minutes between messages. The minimum 1 minute is intended for testing purposes."

#meta_tag = "Meta Tag"

#metadata = "Metadata: "

#metadata_checkbox_tip = "Choose the streams upon which you wish to reformat the metadata."

#metadata_entry_tip = "You can enter text to accompany the stream here, as well as incorporating the title of the currently playing track by including %s at the appropriate point."

#metadata_source_crossfader = "Crossfader"

#metadata_source_label = "Metadata Source"

#metadata_source_last_played = "Last Played"

#metadata_source_left_deck = "Left Deck"

#metadata_source_none = "None"

#metadata_source_right_deck = "Right Deck"

#metadata_source_tip = "Select which Deck is responsible for the metadata on the stream."

#metadata_update_tip = "Update the metadata."

#mic_agc = "Use AGC for mic audio processing (experimental)"

#mic_aux_mutex = "Make Mic and Aux buttons mutually exclusive"

#mic_aux_mutex_tip = "This feature ensures that the microphone and auxiliary inputs can not both be on at the same time. This allows the DJ to be able to switch between the two with only one mouse click. It may be of use to those who mix a lot of external audio, or who wish to use the auxiliary input as a secondary microphone source with different audio processing."

#mic_compression_level_tip = "Controls whether to display a meter indicating the amount of compression currently being applied to both microphone signals."

#mic_in_phones = "Hearing your voice in your headphones (somewhat delayed) can be distracting which is why some users might want to turn this feature off."

#mic_off_tip = "Each time the microphone is turned off run the commands to the right."

#mic_on_tip = "Each time the microphone is turned on run the commands to the right."

#mic_peak = "Mic Peak"

#mic_peak_meter_tip = "A peak hold meter indicating the strength of the audio from each individual microphone."

#mic_peak_toggle = "Mic Peak"

#mic_peak_toggle_tip = "Controls whether to display a peak-hold signal level meter in the main application window indicating the signal strength of the individual microphone audio levels."

#mic_to_dj = "Send microphone audio (mono) to the DJ's headphones"

#mic_toggle_tip = "This button toggles the microphone input for both the left and the right microphones. To select microphones individually, right click on this button."

#mic_vu = "Mic VU"

#mic_vu_meter_tip = "A VU meter for the microphone audio."

#microphone_tab = "Microphone"

#middle = "Middle"

#mild = "Mild"

#misc_features = "Miscellaneous Features"

#missing_lame = "MP3 Not available"

#monitor = "Monitor Mix"

#monitor_dj = "DJ"

#monitor_stream = "Stream"

#mono = "Mono"

#mount_point_tip = "The mount point, which is not required when dealing with Shoutcast servers. A typical mount point might be /listen or /listen.ogg. It is recommended that Ogg streams have a mount point ending in .ogg for the sake of listener client compatibility."

#mp3_compat_tip = "The type of mpeg header used in the mp3 stream or either s-rate or freeformat. Freeformat indicates that the bitrate is not specified in the header since it is non-standard, rather the listener client has to figure out what the bitrate is by itself and not all of them are capable of doing that. In short you'll be streaming something many listeners may not be able to listen to. S-rate indicates the sample rate you have selected is not compatible with mp3 and you'll need to change it if you want to stream."

#mp3_quality_tip = "This trades off sound quality against CPU efficiency. The more streams you want to run concurrently the more you might want to consider using a lower quality setting."

#mp3_stereo_type_tip = "Mono is self explanatory. Joint Stereo is recommended below 160kb/s where regular Stereo might result in metallic sounding distortion. At higher bitrates regular stereo sounds better due to superior channel separation."

#mp3_streamtab_tip = "Clicking this tab selects the mp3 file format for streaming and contains settings for configuring the mp3 encoder."

#mp3_utf8 = "Use utf-8 encoding when streaming mp3 metadata"

#mp3_utf8_tip = "It is standard practice when streaming metadata in mp3 streams to use iso-8859-1 character encoding. This is unfortunate since with utf-8 practically anything can be encoded. In deciding whether to use this feature you have to consider the proportion of listener clients that will be capable of correctly decoding text encoded with utf-8."

#new_profile_body = """Profile '%s' does
#not currently exist.
#Would you like to create it?"""

#new_profile_title = "IDJC - New Profile"

#next_track_tip = "Next track."

#ng_atten_tip = "This controls the amount of attenuation applied by the noise gate. The higher this figure the more it will noticably chop audio at the start of spoken sentences. A suitable setting would be -3."

#ng_delay = "Delay"

#ng_delay_tip = "This is the number of milliseconds to wait before closing the noise gate. It's purpose is to make the noise gate ignore very brief pauses in speech. A sensible figure would be 18ms."

#ng_fall_tip = "This controls the speed at which the gate attenuation can increase. The value is a time constant expressed in milliseconds. A sensible value would be 12ms."

#ng_hyster_tip = "This setting applies hysteresis to the noise gate so that it does not continuously switch itself on and off. A sensible setting would be 6 but it depends on how variable the noise floor is."

#ng_rise_tip = "This is the rise speed as a time constant and relates to how quickly the noise gate opens, allowing the full sound level of speech to pass through. A sensible value would be 1.2ms."

#ng_thresh_tip = "The noise gate is provided to apply a little audio expansion to soften the initial punchiness that the compressor lends to the audio when silence is broken while at the same time improving the signal to noise ratio. The 'Threshold' setting should be set about 10dB above the noise floor so that the noise gate is active when you are not talking."

#nick = "Nick:"

#nick_entry_tip = "The nick specified here must match at least one of the nicks you are logged into IRC as"

#no_more_ask = "Don't ask again"

#no_mp3_stream_available = ('MP3 streaming is unavailable,', 'and as a consequence', 'Shoutcast is also disabled.', '', 'Icecast Ogg streaming only.')

#no_resample = "Use JACK sample rate"

#noise_gate = "Noise Gate"

#nonstd_mp3_rate_tip = "Freedom to choose a non standard bitrate. Note however that the use of a non-standard bit rate will result in a 'free-format' stream that cannot be handled by a great many media players."

#normal_speed_control_menu = "Normal Speed"

#normal_speed_element = ">> Normal Speed <<"

#normboost = "Boost"

#normceiling = "Threshold"

#normdefaults = "Defaults"

#normfall = "Fall"

#normrise = "Rise"

#off = "Off"

#ogg_streamtab_tip = "Clicking this tab selects the Ogg family of file formats."

#open_aux_element = "Switch to Aux input"

#other_mic_options = "Other Options"

#pass_button_tip = "This button causes the crossfader to move to the opposite side at a speed determined by the speed selector to the left."

#pass_speed_tip = "The time in seconds that the crossfader will take to automatically pass across when the button to the right is clicked."

#password_tip = "The server password goes here."

#pause_rec_tip = "Pause recording."

#pause_tip = "Pause."

#play_all = "Play All"

#play_jingles_tip = "Play the jingles sequence specified above or if none is specified play the jingle highlighted in the playlist. The volume level of the main media players will be reduced somewhat for the duration."

#play_progress_tip = "This slider acts as both a play progress indicator and as a means for seeking within the currently playing track."

#play_tip = "Play."

#playback_speed_tip = "This adjusts the playback speed anywhere from 25% to 400%."

#player_1 = "Player 1"

#player_2 = "Player 2"

#player_resample_mode = "Player resample quality"

#player_resample_quality = "This adjusts the quality of the audio resampling method used whenever the sample rate of the music file currently playing does not match the sample rate of the JACK sound server. Highest mode offers the best sound quality but also uses the most CPU (not recommended for systems built before 2006). Fastest mode while it uses by far the least amount of CPU should be avoided if at all possible."

#player_speed_tip = "This option causes some extra widgets to appear below the playlists which allow the playback speed to be adjusted from 25% to 400% and a normal speed button."

#playex_jingles_tip = "This button works the same as the button to the left does except that the sound level of all the other media players is fully reduced."

#playlist = "Playlist"

#playlist1 = "Playlist 1"

#playlist2 = "Playlist 2"

#playlist_menu = "Playlist"

#playlistfilter_all = "All file types"

#playlistfilter_supported = "Playlist types (*.m3u, *.xspf, *.pls)"

#playlisttype_expander = "Select File Type "

#playlisttype_extension = (('By Extension', ''), ('M3U playlist', 'm3u'), ('XSPF playlist', 'xspf'), ('PLS playlist', 'pls'))

#playlisttype_header1 = "File Type"

#playlisttype_header2 = "Extension"

#popupwindowplayduration = "Total play duration %s"

#popupwindowplaying = "Playing track %d of %d"

#popupwindowtracktotal = "Total number of tracks %d"

#port = "Port"

#port_tip = "The network port number which the server is using. Frequently it is 8000."

#prefs_button = "Prefs"

#prefs_window = "IDJC Preferences"

#prefs_window_open_tip = "Open the preferences window."

#prepend = "Prepend"

#prepend_cursor = "Prepend Cursor"

#previous_tip = "Previous track."

#profile_already_in_use = """IDJC could not be started because the profile is currently in use by another instance of IDJC.
#
#If you wish to run more than one instance of IDJC concurrently then in addition to using a different profile you also need to be running an additional JACK sound server.
#
#For further information refer to the -p and -j command line options in the IDJC man page and also to the -n option for starting jackd."""

#profile_import_body = """You can choose to import settings from
#one of the existing profiles
#listed in the drop down box below."""

#prokyon3_connect = "Database Connect"

#prokyon3_database = "Database:"

#prokyon3_frame_text = "Prokyon3 Database"

#prokyon3_nosql = "Python module MySQLdb required"

#prokyon3_password = "Password:"

#prokyon3_user = "User:"

#question_quit = "Do you really want to quit?"

#r = "R"

#random = "Random"

#rec_directory_tip = "Choose which directory you want to save to. All file names will be in a timestamp format and have either an ogg or mp3 file extension. Important: you need to select a directory to which you have adequate write permission."

#rec_source_tip = "Chooses which stream to record. If the stream isn't running the encoder will be started for you. Remember to make sure the encoder settings are to your liking before you start recording."

#reconnected = "IDJC Reconnected"

#reconnected_additional = ('Automatically reconnected to the server', 'after the server module crashed')

#reconnection_text_1 = "The connection to the server in tab %s has failed."

#reconnection_text_2 = "Automatic reconnect in %d seconds."

#reconnection_text_3 = "Try %d of %d."

#record = " Record "

#record_artist = "Artist:"

#record_filename = "Filename:"

#record_title = "Title:"

#recording_time_tip = "Recording time elapsed."

#red_phone_tip = "Mix voice over IP audio to the DJ only."

#refresh_jingles_tip = "Cause the playlist to be refreshed. This is for when items have been added or removed from the jingles playlist folder located at '~/.idjc/profiles/[active profile]/jingles'."

#remaining = "Remaining"

#remove = "Remove"

#request_activate = "Activate"

#request_tab = "Request"

#resample_quality = "Quality"

#response = "Response"

#restore_session = "Restore previous session"

#restore_session_tip = "When starting IDJC most of the main window settings will be as they were left. As an alternative you may specify below how you want the various settings to be when IDJC starts."

#right = "Right:"

#right_mic_stereo_tip = "This controls the stereo balance of the right microphone."

#right_playlist_addition = "Add music to right playlist"

#right_playlist_save = "Save right playlist"

#rise = "Rise"

#rmic_toggle_tip = "This button toggles the right microphone input."

#rms = "Filter"

#save = "Save"

#save_folder_dialog_title = "Select A Folder To Save To"

#save_tip = "Save the audio routing so that it persists across application restarts"

#select_profile_body = "Which profile do you wish to use?"

#select_profile_new = "A New Profile"

#select_profile_title = "IDJC - Profile Chooser"

#send_metadata = "Send Metadata"

#sequence = "Sequence:"

#server_button = "Server"

#server_connect = "Server Connect"

#server_host = "Host:"

#server_login = "Login:"

#server_mount = "Mount:"

#server_passwd = "Pass:"

#server_port = "Port:"

#server_type = "Type:"

#server_type_icecast2 = "Icecast 2"

#server_type_shoutcast = "Shoutcast"

#server_type_tip = "IDJC can connect to both Icecast and Shoutcast servers. For this to be successful you need to specify the type of server that you wish to connect to since each type has a different connection protocol."

#server_window = "Radio Server"

#server_window_open_tip = "Open the radio server connection window."

#set = "Set"

#set_tip = "Reroute the audio to/from the specified port"

#settings_warning_tip = "Adjust these settings carefully since they can have subtle but undesireable effects on the sound quality."

#sharp = "Sharp"

#shell_commands_tip = "Enter bash shell commands to run, separated by a semicolon for this particular event."

#song_placemarker = "Song name place marker = %s"

#speed_variance = "Enable the main-player speed/pitch controls"

#speex_complexity = "CPU"

#speex_complexity_tip = "This sets the level of complexity in the encoder. Higher values use more CPU but result in better sounding audio though not as great an improvement as you would get by increasing the quality setting to the left."

#speex_metadata_tip = "Sending metadata may cause listener clients to misbehave when the metadata changes. By keeping this feature turned off you can avoid that."

#speex_mode = "Mode"

#speex_mode_tip = "This is the audio bandwidth selector. Ultra Wide Band has a bandwidth of 16kHz; Wide Band, 8kHz; Narrow Band, 4kHz. The samplerate is twice the value of the selected bandwidth consequently all settings in the samplerate pane to the left will be disregarded apart from the resample quality setting."

#speex_modes = ('Ultra Wide Band', 'Wide Band', 'Narrow Band')

#speex_quality = "Quality"

#speex_quality_tip = "This picks an appropriate bitrate for the selected bandwidth on a quality metric. Q8 is a good choice for artifact-free speech and Q10 would be the ideal choice for music."

#speex_stereo_tip = "Apply intensity stereo to the audio stream. This is a very efficient implementation of stereo but is only really suited to voice."

#speex_streamtab_tip = "This chooses the Speex speech format for streaming and recording."

#standard_tags = "Standard Tags"

#start_full = "Start Full"

#start_mini = "Start Mini"

#start_mini_full = "Indicates which mode IDJC will be in when launched."

#start_player = "Start player"

#start_recorder = "Start recorder"

#start_recording_history = "started recording to file"

#start_streaming_time = "Start:"

#start_timer_tip = "Automatically connect to the server at a specific time in 24 hour format, midnight being 00:00"

#statusbar_tip = """'Block size' indicates the amount of time that it will take to play from the currently selected track to the next stop.
#'Remaining' is the amount of time until the next stop.
#'Finish' Is the computed time when the tracks will have finished playing."""

#std_mp3_rate_tip = "Use one of the standard mp3 bit rates."

#stereo = "Stereo"

#stop_control_element = "Player stop"

#stop_control_menu = "Player stop"

#stop_jingles_tip = "Stop playing jingles."

#stop_rec_tip = "Stop recording."

#stop_recording_element = "Stop recording"

#stop_recording_history = "stopped recording"

#stop_recording_menu = "Stop recording"

#stop_streaming_time = "Stop:"

#stop_timer_tip = "Automatically disconnect from the server at a specific time in 24 hour format."

#stop_tip = "Stop."

#str_mic_vu_toggle_tip = "Controls whether to display VU meters for the stream and individual microphone audio levels."

#str_peak = "Str Peak"

#str_vu = "Str VU"

#stream = " Stream "

#stream_disconnect_element = "Stop streaming"

#stream_disconnect_menu = "Stop streaming"

#stream_file_chooser_title = "Select A File To Stream"

#stream_info = " Stream Info "

#stream_mic_vu = "Stream + Mic VU"

#stream_mon_tip = "In IDJC there are are two audio paths and this 'Monitor Mix' control toggles between them. When 'Stream' is active you can hear what the listeners are hearing including the effects of the crossfader. 'Monitor Mix' needs to be set to 'DJ' in order to make proper use of the VOIP features."

#stream_monitor = "Monitor Stream Mix"

#stream_peak_meter_tip = "A peak hold meter indicating the signal strength of the stream audio."

#stream_peak_toggle = "Stream Peak"

#stream_peak_toggle_tip = "Controls whether to display a peak-hold signal level meter in the main application window indicating the signal strength of the outgoing stream."

#stream_resample = " Sample rate "

#stream_status_bar_toggle = "Stream Status"

#stream_status_tip = "Controls whether to display a stream status meter in the main window."

#stream_tip = "Make output from this player available for streaming."

#stream_vu_meter_tip = "A VU meter for the stream audio."

#streamer_resample_quality = "This selects the audio resampling method to be used, efficiency versus quality. Highest mode offers the best sound quality but also uses the most CPU (not recommended for systems built before 2006). Fastest mode while it uses by far the least amount of CPU should be avoided if at all possible."

#streams = "Streams"

#streams_tip = "This indicates the state of the various streams. Flashing means stream packets are being discarded because of network congestion. Partial red means the send buffer is partially full indicating difficulty communicating with the server. Green means everything is okay."

#tag_album = "Album:"

#tag_artist = "Artist:"

#tag_comment = "Comment:"

#tag_genre = "Genre:"

#tag_title = "Title:"

#tag_track = "Track:"

#tag_year = "Year:"

#tagger_filename = "Filename:"

#tagger_window_title = "IDJC Tagger"

#test_monitor = " Test / Monitor "

#this = "This"

#threshold = "Thresh."

#time = "Time"

#timed_out = ('Automatically disconnected from the server,', 'after the connection timed out.')

#to_here = "To Here"

#to_install_lame = ('LAME needs to be installed', 'in order to stream or record', 'in mp3 format.')

#track_announcer = "Track Announcer"

#track_announcer_latency_tip = "A delay to the displaying of the change of track information in IRC. The idea is to match this number to the average audio latency in seconds that the listeners will be experiencing. Ten to fifteen seconds typically."

#track_history_clear = "Remove Contents"

#tracks_played = "Tracks Played"

#transfer = "Transfer"

#transfer_control_ltr_element = ">>> Transfer across >>>"

#transfer_control_menu = "Transfer"

#transfer_control_rtl_element = "<<< Transfer across <<<"

#translationcopyright = "Copyright (C) 2008 Stephen Fairchild (s-fairchild@users.sourceforge.net)"

#try_now = "Try Now"

#twodblimit = "Restrict the stream audio level to -2dB"

#twodblimit_tip = "This option may improve the audio quality at the expense of a little playback volume."

#unexpected = "A connection to a radio server failed."

#unp_controls = "Unprocessed Audio Controls"

#up_arrow_tip = "This moves the highlighted track up the playlist order."

#update = "Update"

#upon_connection = "Upon connection:"

#upper_vorbis = "Upper %"

#use = "Use"

#use_custom_srate_tip = "Complete sample rate freedom. Note that only sample rates that appear in the drop down box can be used with an mp3 stream."

#use_dsp_text = "Route audio through DSP interface"

#use_jack_srate_tip = "No additional resampling will occur. The stream sample rate will be that of the JACK sound server."

#use_mp3_srate_tip = "Use one of the standard mp3 sample rates for the stream."

#using_jack_server = "Using named JACK server: "

#voip_mixback_volume_control_tip = "The stream volume level to send to the voice over IP connection."

#vorbis_bitrate_max_tip = "The upper bitrate limit relative to the nominal bitrate. This is an advisory limit and it may be exceeded. Normally it is safe to leave the upper limit uncapped since the bitrate will be averaged and the listeners have buffers that extend for many seconds. The checkbox enables/disables this feature."

#vorbis_bitrate_min_tip = "The minimum bitrate in relative percentage terms. For streaming it is recommended that you set a minimum bitrate to ensure correct listener client behaviour however setting any upper or lower limit will result in a significantly higher CPU usage by a factor of at least three, and slightly degraded sound quality. The checkbox enables/disables this feature."

#vorbis_bitrate_tip = "The nominal Ogg/Vorbis bitrate in kilobits per second."

#vorbis_streamtab_tip = "This chooses the Ogg/vorbis format for streaming and recording."

#vorbis_tag = "Vorbis Tag"

#wet_voice_player_tip = "When you click this button the jingle or track selected in the playlist will be looped continuously and will be audible during moments when the main media players are not active. The 'Monitor Mix' feature needs to be set to 'Stream' if you want to be able to hear it."

#wet_voice_volume_tip = "This adjusts the volume level of the music that plays whenever the other media players are not active. It is only audible to the DJ when 'Monitor Mix' in the main application window is set to 'Stream'."

#window_close = "Close"

