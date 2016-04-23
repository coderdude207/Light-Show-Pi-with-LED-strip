#!/usr/bin/env python
#
# Licensed under the BSD license.  See full license in LICENSE file.
# http://www.lightshowpi.com/
#
# Author: Todd Giles (todd@lightshowpi.com)
# Author: Chris Usey (chris.usey@gmail.com)
# Author: Tom Enos (tomslick.ca@gmail.com)

"""Preshow and Postshow functionality for the lightshows.

Your lightshow can be configured to have a "preshow" before each
individual song is played or a "postshow" after each individual
song is played.  See the default configuration file for more
details on configuring your pre or post show.

Sample usage (to test your preshow or postshow configuration):

sudo python prepostshow.py "preshow"
or
sudo python prepostshow.py "postshow"
"""

import __builtin__
import logging
import os
import subprocess
import signal
import sys
import time
import threading


class PrePostShow(object):
    """The PreshowPostshow class handles all pre-show and post-show logic

    Typical usage to simply play the default configured preshow_configuration:
    or postshow_configuration:

    PrePostShow("preshow").execute()
    PrePostShow("postshow").execute()
    """
    done = 0
    play_now_interrupt = 1

    def __init__(self, show="preshow", hardware=None):
        """

        :param show: which show should be preformed
        :type show: str

        :param hardware: an instance of hardware_controller.py
        :type hardware: object
        """
        if hardware:
            self.hc = hardware
        else:
            self.hc = __import__('hardware_controller')
            self.hc.initialize()

        self.config = self.hc.cm.lightshow.get(show)
        self.show = show
        self.audio = None

    def check_state(self):
        """Check State file

        Check the state file to see if play now requested
        """
        # refresh state
        self.hc.cm.load_state()
        if int(self.hc.cm.get_state('play_now', "0")):
            # play now requested!
            return True
        return False

    def execute(self):
        """Execute the pre/post show as defined by the current config

        Returns the exit status of the show, either done if the
        show played to completion, or play_now_interrupt if the
        show was interrupted by a play now command.
        """
        # Is there a show to launch?
        if self.config is None:
            return PrePostShow.done

        # Is the config a script or a transition based show
        # launch the script if it is
        if not isinstance(self.config, dict) and os.path.exists(self.config):
            logging.debug("Launching external script " + self.config + " as " + self.show)
            return self.start_script()

        # start the audio if there is any
        self.start_audio()

        if 'transitions' in self.config:
            try:
                # display transition based show
                for transition in self.config['transitions']:
                    start = time.time()

                    if transition['type'].lower() == 'on':
                        self.hc.turn_on_lights(True)
                    else:
                        self.hc.turn_off_lights(True)

                    logging.debug('Transition to ' + transition['type'] + ' for '
                                  + str(transition['duration']) + ' seconds')

                    if 'channel_control' in transition:
                        channel_control = transition['channel_control']

                        for key in channel_control.keys():
                            mode = key
                            channels = channel_control[key]

                            for channel in channels:
                                if mode == 'on':
                                    self.hc.set_light(int(channel) - 1, True, 1)
                                elif mode == 'off':
                                    self.hc.set_light(int(channel) - 1, True, 0)
                                else:
                                    logging.error("Unrecognized channel_control mode "
                                                  "defined in preshow_configuration "
                                                  + str(mode))

                    # hold transition for specified time
                    while transition['duration'] > (time.time() - start):
                        # check for play now
                        if self.check_state():
                            # kill the audio playback if playing
                            if self.audio:
                                os.killpg(self.audio.pid, signal.SIGTERM)
                                self.audio = None
                            return PrePostShow.play_now_interrupt

                        time.sleep(0.1)
            except KeyboardInterrupt:
                pass

        # hold show until audio has finished if we have audio
        # or audio is not finished
        return_value = self.hold_for_audio()

        return return_value

    def start_audio(self):
        """Start audio playback if there is any"""
        if "audio_file" in self.config and self.config['audio_file'] is not None:
            audio_file = self.config['audio_file']
            self.audio = subprocess.Popen(["mpg123", "-q", audio_file])
            logging.debug("Starting " + self.show + " audio file " + self.config['audio_file'])

    def hold_for_audio(self):
        """hold show until audio has finished"""
        if self.audio:
            while self.audio.poll() is None:
                # check for play now
                if self.check_state():
                    # kill the audio playback if playing
                    os.killpg(self.audio.pid, signal.SIGTERM)
                    self.audio = None

                    return PrePostShow.play_now_interrupt

                time.sleep(0.1)

        return PrePostShow.done

    def start_script(self):
        """Start a separate script to control the lights"""
        return_value = PrePostShow.done
        self.hc.turn_off_lights()

        # make a copy of the path
        path = list(sys.path)

        # insert script location into path
        sys.path.insert(0, os.path.split(self.config)[0])
        __builtin__.hc = self.hc

        # import custom script
        script = __import__(os.path.basename(os.path.splitext(self.config)[0]))

        # run the scripts main method
        exit_event = threading.Event()
        script_thread = threading.Thread(target=script.main, args=(exit_event,))
        script_thread.setDaemon(True)
        script_thread.start()

        while script_thread.is_alive():
            if self.check_state():
                # Skip out on the rest of the show if play now requested!
                exit_event.set()
                return_value = PrePostShow.play_now_interrupt
                break

            # Check once every ~ .1 seconds to break out
            time.sleep(0.1)

        # restore path
        sys.path[:] = path

        return return_value


if __name__ == "__main__":
    show_to_call = 'preshow'

    if len(sys.argv) > 1:
        show_to_call = sys.argv[1]

    PrePostShow(show_to_call).execute()
