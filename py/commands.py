#!/usr/bin/env python
#
# Licensed under the BSD license.  See full license in LICENSE file.
# http://www.lightshowpi.com/
#
# Author: Todd Giles (todd@lightshowpi.com)
#
# Initial commands implemented by Chris Usey (chris.usey@gmail.com)
"""Command definition file.

Enabled commands must be defined in the configuration file. Each command must also have a
matching function defined in this file with a name in the form 'def cmd_commandname(user, args)'.
For example, the command help would have a matching function definition for 'def cmd_help(user,
args)'. The user argument will include the cell number of the user who made the request (if the
command is received via sms) and the 'args' argument is a string containing all the text in the
command sent (e.g. an sms message) after the command name itself has already been stripped.
So following the 'help' example, if a user with the cell phone number 1 (123) 456-7890 texted
'help me please!!!' then the function cmd_help will be called with arguments user = '+11234567890:',
and args = ' me please!!!'.

The function should return a string that will then be sent back to the user in some fashion (e.g.
in a return text message if via sms). Return an empty string if you'd rather no message be sent in
response to the command.

To install the command, simply instantiate an instance of Command for the command you've created
(see examples below). Note that new commands may be defined in their own files if desired (i.e. no
need to define all commands in this file).
"""

import logging
import math
import re
import subprocess


# The base command class. The class keeps track of all commands instantiated, so to install a new
# command, simply instantiate a new instance of it.


class Command(object):
    """The base command class

    This class keeps track of all commands instantiated, so to install
    a new command, simply instantiate a new instance of that command.
    """
    commands = {}

    def __init__(self, name, func):
        self.name = name.lower()
        if self.name not in _CMD_NAMES:
            raise ValueError(name + ' command not defined in configuration file')
        if self.name in Command.commands:
            logging.warn(name + 'command is defined more than once, using last definition')
        self.func = func
        Command.commands[self.name] = self

    def execute(self, user, args):
        """
        Execute this command for the specified user with given arguments,
        returning a message to be sent to the user after the command has
        finished

        :param user: A specified user
        :type user: str

        :param args: function to execute
        :type args: function

        :return: response to an executed command
        :rtype: str
        """
        return self.func(user, args)


def execute(command, user):
    """
    Attempt to execute a command for the specified user with given
    arguments, returning a message to be sent to the user after
    the command has finished

    :param command: function, function to execute
    :type command: function

    :param user: string, specified user
    :type user: str

    :return: response to an executed command
    :rtype: str

    :raises: :ValueError: if command does not exist
    """
    # Determine the name of the command and arguments from the full
    # command (taking into account aliases).
    name = ''
    args = ''

    for command_name in _CMD_NAMES:
        if bool(re.match(command_name, command, re.I)):
            name = command_name
            args = command[len(command_name):]
        else:
            try:
                for command_alias in cm.sms.get(command_name + '_aliases'):
                    if bool(re.match(command_alias, command, re.I)):
                        name = command_name
                        args = command[len(command_alias):]
                        break
            except KeyError:
                pass  # No aliases defined, that's fine - keep looking

        if name:
            break

    # If no command found, assume we're executing the default command
    if not name:
        name = cm.sms.default_command
        args = command

    # Verify this command is installed
    if name not in Command.commands:
        raise ValueError(name
                         + ' command must be installed by calling Command(\''
                         + name + '\', <handler>)')

    # Verify the user has permission to execute this command
    if not cm.has_permission(user, name):
        return cm.sms.unauthorized_response.format(cmd=name, user=user)

    # Check to see if the command issued should be throttled
    if cm.is_throttle_exceeded(name, user):
        return cm.sms.throttle_limit_reached_response.format(cmd=name, user=user)

    # Execute the command
    return Command.commands[name].execute(user, args.strip())


def cmd_help(*args):
    """
    Returns a list of available commands for the requesting user.

    :param args: [specified user, arguments for command]
    :type args: list

    :return: list of available commands that the current user has permission to execute
    :rtype: str
    """
    user = args[0]
    help_msg = "Commands:\n"

    for cmd in _CMD_NAMES:
        if cm.has_permission(user, cmd):
            cmd_description = cm.sms.get(cmd + '_description')

            if cmd_description:
                help_msg += cmd_description + "\n"

    return help_msg


def cmd_list(*args):
    """Lists all the songs from the current playlist.

    :param args: [specified user, arguments for command]
    :type args: list

    :return: list of songs
    :rtype: list
    """

    per_sms = cm.sms.list_songs_per_sms
    per_page = cm.sms.list_songs_per_page
    pages = int(math.ceil(float(len(cm.playlist)) / per_sms))
    page = 1

    if len(args) > 1 and args[1].isdigit():
        page = int(args[1])
    if page < 1 or page > pages:
        return 'page # must be between 1 and ' + str(pages)

    response = ['Vote by texting the song #:\n']
    if page == 1:
        response[0] += '(Showing 1-' + str(per_page) + ' of ' + str(len(cm.playlist)) + ')\n'

    i_sms = 0
    i_song = per_page * (page-1)
    for song in cm.playlist[per_page * (page - 1):per_page * page]:
        if i_sms > len(response) - 1:
            response.append('')
        response[i_sms] += str(1 + i_song) + ': ' + song[0] + '\n'
        i_song += 1
        if i_song % per_sms == 0:
            i_sms += 1

    if page < pages:
        response[len(response) - 1] += '(Text "list ' + str(1 + page) + '" for more songs)'
    return response


def cmd_play(*args):
    """Interrupts whatever is going on, and plays the requested song.

    :param args: [specified user, arguments for command]
    :type args: list

    :return: play song response
    :rtype: str
    """
    args = args[1]

    if len(args) == 0 or not args.isdigit():
        cm.update_state('play_now', -1)

        return 'Skipping straight ahead to the next show!'
    else:
        song = int(args)

        if song < 1 or song > len(cm.playlist):
            return 'Sorry, the song you requested ' + args + ' is out of range :('
        else:
            cm.update_state('play_now', song)

            return '"' + cm.playlist[song - 1][0] + '" coming right up!'


def cmd_volume(*args):
    """Changes the system volume.

    :param args: [specified user, arguments for command]
    :type args: list

    :return: volume request result
    :rtype: str
    """
    # Sanitize the input before passing to volume script
    args = args[1]

    if '-' in args:
        sanitized_cmd = '-'
    elif '+' in args:
        sanitized_cmd = '+'
    elif args.isdigit():
        vol = int(args)

        if vol < 0 or vol > 100:
            return 'volume must be between 0 and 100'
        sanitized_cmd = str(vol)
    else:
        return cm.sms.volume_description

    # Execute the sanitized command and handle result
    volscript = cm.home_dir + '/bin/vol'
    output, error = subprocess.Popen(volscript + ' ' + sanitized_cmd,
                                     shell=True, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE).communicate()
    if error:
        logging.warn('volume request failed: ' + str(error))

        return 'volume request failed'
    else:
        return 'volume = ' + str(output)


def cmd_vote(*args):
    """Casts a vote for the next song to be played

    :param args: [specified user, arguments for command]
    :type args: list

    :return: unknown command response
    :rtype: str
    """
    user = args[0]
    args = args[1]

    if args.isdigit():
        song_num = int(args)

        if user != 'Me' and 0 < song_num <= len(cm.playlist):
            song = cm.playlist[song_num - 1]
            song[2].add(user)
            logging.info('Song requested: ' + str(song))

            return 'Thank you for requesting "' + song[0] \
                   + '", we\'ll notify you when it starts!'
    else:
        return cm.sms.unknown_command_response


def start(config):
    global cm, _CMD_NAMES
    cm = config
    _CMD_NAMES = cm.sms.commands
        
    Command('help', cmd_help)
    Command('list', cmd_list)
    Command('play', cmd_play)
    Command('volume', cmd_volume)
    Command('vote', cmd_vote)


if __name__ == "__main__":
    pass
