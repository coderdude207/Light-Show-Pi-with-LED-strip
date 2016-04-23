#!/usr/bin/env python
#
# Licensed under the BSD license.  See full license in LICENSE file.
# http://www.lightshowpi.com/
#
# Author: Todd Giles (todd@lightshowpi.com)
# Author: Tom Enos (tomslick.ca@gmail.com)
#

"""Configuration management for the lightshow.

Configuration files are all located in the <homedir>/config directory. This file contains tools to
manage these configuration files.
"""

import ConfigParser
import ast
import datetime
import fcntl
import logging
import os
import os.path
import sys
import warnings
import json
import shlex
from collections import defaultdict

# The home directory and configuration directory for the application.
HOME_DIR = os.getenv("SYNCHRONIZED_LIGHTS_HOME")
if not HOME_DIR:
    print("Need to setup SYNCHRONIZED_LIGHTS_HOME environment variable, "
          "see readme")
    sys.exit()
CONFIG_DIR = HOME_DIR + '/config'
LOG_DIR = HOME_DIR + '/logs'


def _as_list(list_str, delimiter=','):
    """Return a list of items from a delimited string (after stripping whitespace).

    :param list_str: string to turn into a list
    :type list_str: str

    :param delimiter: split the string on this
    :type delimiter: str

    :return: string converted to a list
    :rtype: list
    """
    return [str.strip(item).rstrip() for item in list_str.split(delimiter)]


class Configuration(object):
    """Configuration management for the lightshow.

    Configuration files are all located in the <homedir>/config directory. This file contains tools
    to manage these configuration files.
    """

    def __init__(self, sms=False):
        self.gpio_len = None
        self.playlist = None

        # path and file locations
        self.home_dir = os.getenv("SYNCHRONIZED_LIGHTS_HOME")
        self.config_dir = self.home_dir + "/config/"
        self.log_dir = self.home_dir + "/logs/"
        self.state_file = self.config_dir + "state.cfg"

        # ConfigParsers
        self.config = ConfigParser.RawConfigParser(allow_no_value=True)
        self.state = ConfigParser.RawConfigParser()

        self.state_section = 'do_not_modify'

        self.load_config()

        # Ensure state file has been created
        if not os.path.isfile(self.state_file):
            open(self.state_file, 'w').close()

        self.load_state()

        # synchronized_lights and check_sms both use configuration_manager
        # let them only use the parts they need, saving a little memory and time.
        if not sms:
            self.hardware = None
            self.lightshow = None
            self.audio_processing = None
            self.network = None

            self.set_hardware()
            self.set_lightshow()
            self.set_audio_processing()
            self.set_network()
        else:
            self.sms = None
            self.who_can = dict()
            self.throttlestate = dict()
            self.set_sms()

    def load_config(self):
        """Load config files into ConfigParser instance"""
        self.config.readfp(open(self.config_dir + '/defaults.cfg'))
        self.config.read([self.config_dir + '/overrides.cfg', '/home/pi/.lights.cfg',
                          os.path.expanduser('~/.lights.cfg')])

    # handle the program state / next 3 methods
    def load_state(self):
        """Force the state to be reloaded form disk."""
        with open(self.state_file) as state_fp:
            fcntl.lockf(state_fp, fcntl.LOCK_SH)
            self.state.readfp(state_fp, self.state_file)
            fcntl.lockf(state_fp, fcntl.LOCK_UN)

    def get_state(self, name, default=""):
        """
        Get application state

        Return the value of a specific application state variable, or the specified
        default if not able to load it from the state file

        :param name: option to load from state file
        :type name: str

        :param default: return if not able to load option from state file
        :type default: str

        :return: the current state
        :rtype: str
        """
        try:
            return self.state.get(self.state_section, name)
        except (ConfigParser.NoOptionError, ConfigParser.NoSectionError):
            return default

    def update_state(self, name, value):
        """Update the application state (name / value pair)

        :param name: option name to update
        :type name: str

        :param value: value to update option name to
        :type value: str
        """
        value = str(value)
        logging.info('Updating application state {%s: %s}', name, value)

        if not self.state.has_section(self.state_section):
            self.state.add_section(self.state_section)

        self.state.set(self.state_section, name, value)

        with open(self.state_file, 'wb') as state_fp:
            fcntl.lockf(state_fp, fcntl.LOCK_EX)
            self.state.write(state_fp)
            fcntl.lockf(state_fp, fcntl.LOCK_UN)

    def set_hardware(self):
        """
        Retrieves the hardware configuration parsing it from the Config Parser as necessary.
        """
        hrdwr = dict()
        devices = dict()
        try:
            devices = json.loads(self.config.get('hardware', 'devices'))
        except Exception as error:
            logging.error("devices not defined or not in JSON format." + str(error))
        hrdwr["devices"] = devices

        for device_type, settings in hrdwr["devices"].iteritems():
            for count in range(len(settings)):
                for k, v in settings[count].iteritems():
                    settings[count][k] = v if not isinstance(v, str) else int(v, 16)

        hrdwr["gpio_pins"] = map(int, self.config.get('hardware', 'gpio_pins').split(","))
        self.gpio_len = len(hrdwr["gpio_pins"])

        hrdwr["gpio_len"] = len(hrdwr["gpio_pins"])

        temp = self.config.get('hardware', 'pin_modes').split(",")
        if len(temp) != 1:
            hrdwr["pin_modes"] = temp
        else:
            hrdwr["pin_modes"] = [temp[0] for _ in range(self.gpio_len)]

        hrdwr["pwm_range"] = int(self.config.get('hardware', 'pwm_range'))
        hrdwr["active_low_mode"] = self.config.getboolean('hardware', 'active_low_mode')

        self.hardware = Section(hrdwr)

    def set_network(self):
        """
        Retrieves the network configuration parsing it from the Config Parser as necessary.
        """
        ntwrk = dict()
        ntwrk["networking"] = self.config.get('network', 'networking')
        ntwrk["port"] = self.config.getint('network', 'port')
        ntwrk["buffer"] = self.config.getint('network', 'buffer')

        if len(self.config.get('network', 'channels')) == 0:
            channels = [_ for _ in range(self.gpio_len)]
        else:
            channels = map(int, self.config.get('network', 'channels').split(","))

        temp = defaultdict()
        for channel in range(len(channels)):
            temp[channels[channel]] = channel

        ntwrk["channels"] = temp

        self.network = Section(ntwrk)

    def set_lightshow(self):
        """
        Retrieve the lightshow configuration loading and parsing it from a file as necessary.
        """
        lghtshw = dict()
        ls = 'lightshow'
        lghtshw["mode"] = self.config.get(ls, 'mode')
        lghtshw["use_fifo"] = self.config.getboolean(ls, 'use_fifo')
        lghtshw["fifo"] = "/tmp/audio"
        lghtshw["audio_in_card"] = self.config.get(ls, 'audio_in_card')
        lghtshw["audio_out_card"] = self.config.get(ls, 'audio_out_card')
        
        if lghtshw["use_fifo"]:
            lghtshw["audio_out_card"] = ""
            
        lghtshw["input_channels"] = self.config.getint(ls, 'input_channels')
        lghtshw["input_sample_rate"] = self.config.getint(ls, 'input_sample_rate')

        command_string = self.config.get(ls, 'stream_command_string')
        lghtshw["stream_command_string"] = shlex.split(command_string)

        playlist_path = self.config.get(ls, 'playlist_path')
        playlist_path = playlist_path.replace('$SYNCHRONIZED_LIGHTS_HOME', self.home_dir)
        if playlist_path:
            lghtshw["playlist_path"] = playlist_path
        else:
            lghtshw["playlist_path"] = "/home/pi/music/.playlist"

        lghtshw["randomize_playlist"] = self.config.getboolean(ls, 'randomize_playlist')

        onc = "always_on_channels"
        lghtshw[onc] = map(int, self.config.get(ls, onc).split(","))
        offc = "always_off_channels"
        lghtshw[offc] = map(int, self.config.get(ls, offc).split(","))
        ic = "invert_channels"
        lghtshw[ic] = map(int, self.config.get(ls, ic).split(","))

        # setup up preshow
        preshow = None
        preshow_configuration = self.config.get(ls, 'preshow_configuration')
        preshow_script = self.config.get(ls, 'preshow_script')

        if preshow_configuration and not preshow_script:
            try:
                preshow = json.loads(preshow_configuration)
            except (ValueError, TypeError) as error:
                msg = "Preshow_configuration not defined or not in JSON format."
                logging.error(msg + str(error))
        else:
            if os.path.isfile(preshow_script):
                preshow = preshow_script

        lghtshw['preshow'] = preshow

        # setup postshow
        postshow = None
        postshow_configuration = self.config.get(ls, 'postshow_configuration')
        postshow_script = self.config.get(ls, 'postshow_script')

        if postshow_configuration and not postshow_script:
            try:
                postshow = json.loads(postshow_configuration)
            except (ValueError, TypeError) as error:
                msg = "Postshow_configuration not defined or not in JSON format."
                logging.error(msg + str(error))
        else:
            if os.path.isfile(postshow_script):
                postshow = postshow_script

        lghtshw['postshow'] = postshow
        lghtshw["decay_factor"] = self.config.getfloat(ls, 'decay_factor')
        lghtshw["attenuate_pct"] = self.config.getfloat(ls, 'attenuate_pct')

	# Standard Deviation
	lghtshw["SD_low"] = self.config.getfloat(ls, 'SD_low')
	lghtshw["SD_high"] = self.config.getfloat(ls, 'SD_high')

        self.lightshow = Section(lghtshw)

    def set_audio_processing(self):
        """
        Retrieve the audio processing configuration loading and parsing it from a file as necessary.
        """
        audio_prcssng = dict()
        audio_prcssng["fm"] = self.config.getboolean('audio_processing', 'fm')
        audio_prcssng["frequency"] = self.config.get('audio_processing', 'frequency')
        audio_prcssng["light_delay"] = self.config.getfloat('audio_processing', 'light_delay')
        audio_prcssng["min_frequency"] = \
            self.config.getfloat('audio_processing', 'min_frequency')
        audio_prcssng["max_frequency"] = \
            self.config.getfloat('audio_processing', 'max_frequency')
        temp = self.config.get('audio_processing', 'custom_channel_mapping')
        audio_prcssng["custom_channel_mapping"] = \
            map(int, temp.split(',')) if temp else 0
        temp = self.config.get('audio_processing', 'custom_channel_frequencies')
        audio_prcssng["custom_channel_frequencies"] = \
            map(int, temp.split(',')) if temp else 0

        self.audio_processing = Section(audio_prcssng)

    def set_sms(self):
        """
        Retrieves and validates sms configuration loading and parsing it from a file as necessary.
        """
        shrtmssgsrvc = dict(self.config.items('sms'))
        self.who_can["all"] = set()
        shrtmssgsrvc['commands'] = _as_list(self.config.get('sms', 'commands'))
        shrtmssgsrvc['throttle_time_limit_seconds'] = int(
            self.config.get('sms', 'throttle_time_limit_seconds'))

        shrtmssgsrvc['enable'] = self.config.getboolean('sms', 'enable')
        shrtmssgsrvc['groups'] = _as_list(self.config.get('sms', 'groups'))
        shrtmssgsrvc['blacklist'] = _as_list(self.config.get('sms', 'blacklist'))
        shrtmssgsrvc['unknown_command_response'] = self.config.get('sms',
                                                                   'unknown_command_response')
        shrtmssgsrvc['list_songs_per_sms'] = self.config.getint('sms', 'list_songs_per_sms')
        shrtmssgsrvc['list_songs_per_page'] = self.config.getint('sms', 'list_songs_per_page')

        playlist_path = self.config.get('lightshow', 'playlist_path')
        playlist_path = playlist_path.replace('$SYNCHRONIZED_LIGHTS_HOME', self.home_dir)
        
        if playlist_path:
            shrtmssgsrvc["playlist_path"] = playlist_path
        else:
            shrtmssgsrvc["playlist_path"] = "/home/pi/music/.playlist"

        # Commands
        for cmd in shrtmssgsrvc['commands']:
            try:
                shrtmssgsrvc[cmd + '_aliases'] = _as_list(shrtmssgsrvc[cmd + '_aliases'])
            except KeyError:
                shrtmssgsrvc[cmd + '_aliases'] = []
            self.who_can[cmd] = set()

        # Groups / Permissions
        shrtmssgsrvc['throttled_groups'] = dict()
        for group in shrtmssgsrvc['groups']:
            try:
                shrtmssgsrvc[group + '_users'] = _as_list(shrtmssgsrvc[group + '_users'])
            except KeyError:
                shrtmssgsrvc[group + '_users'] = []

            try:
                shrtmssgsrvc[group + '_commands'] = _as_list(shrtmssgsrvc[group + '_commands'])
            except KeyError:
                shrtmssgsrvc[group + '_commands'] = []

            for cmd in shrtmssgsrvc[group + '_commands']:
                for user in shrtmssgsrvc[group + '_users']:
                    self.who_can[cmd].add(user)

            # Throttle
            try:
                throttled_group_definitions = _as_list(shrtmssgsrvc[group + '_throttle'])
                throttled_group = dict()

                for definition in throttled_group_definitions:
                    definition = definition.split(':')

                    if len(definition) != 2:
                        gtd = "_throttle definitions should be in the form [command]:<limit> - "
                        warnings.warn(group + gtd + ":".join(definition))
                        continue

                    throttle_command = definition[0]
                    throttle_limit = int(definition[1])
                    throttled_group[throttle_command] = throttle_limit

                shrtmssgsrvc['throttled_groups'][group] = throttled_group
            except KeyError:
                warnings.warn(
                    "Throttle definition either does not exist or is configured" +
                    "incorrectly for group: " + group)

        self.sms = Section(shrtmssgsrvc)

    def get_playlist(self):
        """Retrieve the song list

        :return: a list of songs
        :rtype: list
        """
        return self.playlist

    def set_playlist(self, songs):
        """Sets the list of songs

        if loaded elsewhere, as is done by check_sms for example

        :param song_list: a list of songs
        :type song_list: list
        """
        self.playlist = songs

    def has_permission(self, user, cmd):
        """Returns True if a user has permission to execute the given command
        :param user: the user trying to execute the command
        :type user: str

        :param cmd: the command at question
        :type cmd: str

        :return: user has permission
        :rtype: bool
        """
        blacklisted = user in self.sms.blacklist
        return not blacklisted and (user in self.who_can['all']
                                    or 'all' in self.who_can[cmd]
                                    or user in self.who_can[cmd])

    def is_throttle_exceeded(self, cmd, user):
        """Returns True if the throttle has been exceeded and False otherwise

        :param cmd: the command at question
        :type cmd: str

        :param user: the user trying to execute the command
        :type user: str

        :return: has throttle been exceeded
        :rtype: bool
        """
        # Load throttle STATE
        self.load_state()
        self.throttlestate = ast.literal_eval(self.get_state('throttle', '{}'))
        processcommandflag = -1

        # Analyze throttle timing
        currenttimestamp = datetime.datetime.now()
        throttletimelimit = self.sms.throttle_time_limit_seconds

        if "throttle_timestamp_start" in self.throttlestate:
            throttlestarttime = datetime.datetime.strptime(
                self.throttlestate['throttle_timestamp_start'], '%Y-%m-%d %H:%M:%S.%f')
        else:
            throttlestarttime = currenttimestamp

        delta = datetime.timedelta(seconds=int(throttletimelimit))
        throttlestoptime = throttlestarttime + delta

        # Compare times and see if we need to reset the throttle STATE
        if (currenttimestamp == throttlestarttime) or \
                (throttlestoptime < currenttimestamp):
            # There is no time recorded or the time 
            # has expired reset the throttle STATE
            self.throttlestate = dict()
            self.throttlestate['throttle_timestamp_start'] = str(currenttimestamp)
            self.update_state('throttle', self.throttlestate)

        # ANALYZE THE THROTTLE COMMANDS AND LIMITS
        allthrottlelimit = -1
        cmdthrottlelimit = -1

        # Check to see what group belongs to starting with the first 
        # group declared
        throttled_group = None
        for group in self.sms.groups:
            userlist = self.sms.get(group + "_users")

            if user in userlist:
                # The user belongs to this group, check if there are any 
                # throttle definitions
                if group in self.sms.throttled_groups:
                    # The group has throttle commands defined, now check if 
                    # the command is defined
                    throttledcommands = self.sms.throttled_groups[group]

                    # Check if all command exists
                    if "all" in throttledcommands:
                        allthrottlelimit = int(throttledcommands['all'])

                    # Check if the command passed is defined
                    if cmd in throttledcommands:
                        cmdthrottlelimit = int(throttledcommands[cmd])

                    # A throttle definition was found, we no longer need to 
                    # check anymore groups
                    if allthrottlelimit != -1 or cmdthrottlelimit != -1:
                        throttled_group = group
                        break

        # Process the throttle settings that were found for the throttled group
        if not throttled_group:
            # No throttle limits were found for any group
            return False
        else:
            # Throttle limits were found, check them against throttle STATE 
            # limits
            if throttled_group in self.throttlestate:
                groupthrottlestate = self.throttlestate[throttled_group]
            else:
                groupthrottlestate = dict()

            if cmd in groupthrottlestate:
                groupthrottlecmdlimit = int(groupthrottlestate[cmd])
            else:
                groupthrottlecmdlimit = 0

        # Check to see if we need to apply "all"
        if allthrottlelimit != -1:

            if 'all' in groupthrottlestate:
                groupthrottlealllimit = int(groupthrottlestate['all'])
            else:
                groupthrottlealllimit = 0

            # Check if "all" throttle limit has been reached
            if groupthrottlealllimit < allthrottlelimit:
                # Not Reached, bump throttle and record
                groupthrottlealllimit += 1
                groupthrottlestate['all'] = groupthrottlealllimit
                self.throttlestate[throttled_group] = groupthrottlestate
                processcommandflag = False
            else:
                # "all" throttle has been reached we dont want to process 
                # anything else
                return True

        # Check to see if we need to apply "cmd"
        if cmdthrottlelimit != -1:
            if groupthrottlecmdlimit < cmdthrottlelimit:
                # Not reached, bump throttle
                groupthrottlecmdlimit += 1
                groupthrottlestate[cmd] = groupthrottlecmdlimit
                self.throttlestate[throttled_group] = groupthrottlestate
                processcommandflag = False

        # Record the updatedthrottle STATE and return
        self.update_state('throttle', self.throttlestate)

        return processcommandflag


class Section(object):
    def __init__(self, config):
        self.config = config
        self.set_values(self.config)

    def set_config(self, config):
        self.config = config
        self.set_values(self.config)

    def get_config(self):
        return self.config

    def set_value(self, key, value):
        setattr(self, key, value)

    def set_values(self, dict_of_items):
        """Create class instance variables from key, value pairs

        :param dict_of_items: a dict containing key, value pairs to set
        :type dict_of_items: dict
        """
        for key, value in dict_of_items.iteritems():
            setattr(self, key, value)

    def get(self, item):
        """Get class instance variables from string

        :param item:
        :type item: str

        :return: object of item type
        :rtype: object
        """
        return getattr(self, item)


if __name__ == "__main__":
    # prints the current configuration
    cm = Configuration()
    sms_cm = Configuration(True)
    print "Home directory set:", HOME_DIR
    print "Config directory set:", CONFIG_DIR
    print "Logs directory set:", LOG_DIR

    print "\nHardware Configuration"
    for hkey, hvalue in cm.hardware.config.iteritems():
        print hkey, "=", hvalue

    print "\nLightshow Configuration"
    for lkey, lvalue in cm.lightshow.config.iteritems():
        print lkey, "=", lvalue

    print "\nAudio Processing Configuration"
    for akey, avalue in cm.audio_processing.config.iteritems():
        print akey, "=", avalue

    print "\nSMS Configuration"
    for skey, svalue in sms_cm.sms.config.iteritems():
        print skey, "=", svalue

    for wckey, wcvalue in sms_cm.who_can.iteritems():
        print wckey, "=", wcvalue
