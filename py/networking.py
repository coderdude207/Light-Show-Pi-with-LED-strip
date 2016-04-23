#!/usr/bin/env python
#
# Licensed under the BSD license.  See full license in LICENSE file.
# http://www.lightshowpi.com/
#
# Author: Paul Dunn (dunnsept@gmail.com)
# Author: Tom Enos (tomslick.ca@gmail.com)

"""Control the raspberry pi network.

The network controller handles all interaction with the raspberry pi
to send or receive data to/from lightshowpi network enabled raspberry pi(s).
"""

import cPickle
import logging as log
import socket
import numpy as np
import sys


class Networking(object):
    """Control the raspberry pi network.

    The network controller handles all interaction with the raspberry pi
    to send or receive data to/from lightshowpi network enabled raspberry pi(s).
    """

    def __init__(self, cm):
        self.cm = cm

        self.networking = cm.network.networking
        self.port = cm.network.port
        self.network_buffer = cm.network.buffer
        self.channels = cm.network.channels
        self.playing = False

        self.network_stream = None
        self.setup()

    def setup(self):
        """Setup as either server or client"""
        if self.networking == "server":
            self.setup_server()
        elif self.networking == "client":
            self.setup_client()

    def setup_server(self):
        """Setup network broadcast stream if this RPi is to be serving data"""

        print "streaming on port: " + str(self.port)
        try:
            self.network_stream = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.network_stream.bind(('', 0))
            self.network_stream.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            log.info("streaming on port: " + str(self.port))
        except socket.error, msg:
            log.error('Failed create socket or bind. Error code: ' +
                      str(msg[0]) + ' : ' + msg[1])
            print "error creating and binding socket for broadcast"
            sys.exit(1)

    def setup_client(self):
        """Setup network receive stream if this RPi is to be a client"""
        log.info("Network client mode starting")
        print "Network client mode starting..."
        try:
            self.network_stream = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.network_stream.bind(('', self.port))

            print "listening on port: " + str(self.port)

            log.info("client channels mapped as\n" + str(self.channels))
            log.info("listening on port: " + str(self.port))
        except socket.error, msg:
            log.error('Failed create socket or bind. Error code: ' +
                      str(msg[0]) + ' : ' + msg[1])
            self.network_stream.close()
            sys.exit(1)

    def close_connection(self):
        """Close the network stream"""
        if self.network_stream:
            self.network_stream.close()
            self.network_stream = None

    def receive(self):
        """Receive the data sent from the server and decode it

        :return: data
        :rtype tuple: np.array | tuple
        """
        try:
            data, address = self.network_stream.recvfrom(self.network_buffer)
            data = cPickle.loads(data)
        except (IndexError, cPickle.PickleError):
            data = tuple(np.array([0 for _ in range(cm.hardware.gpio_len)]))

        return data

    def broadcast(self, *args):
        """Broadcast data over the network

        args will be pickled before being sent

        :param args: (list of lists) to broadcast clients channel data

                        (tuple) pin, brightness pair

        :type args: list | tuple
        """
        if self.networking == "server":
            try:
                data = cPickle.dumps(args)
                self.network_stream.sendto(data, ('<broadcast>', self.port))
            except socket.error, msg:
                if msg[0] != 9:
                    log.error(str(msg[0]) + ' ' + msg[1])
                    print str(msg[0]) + ' ' + msg[1]

    def set_playing(self):
        """Set a flag for playing,

        Setting this flag allows for synchronized_lights.py to broadcast
        the matrix, std, and mean.

        If this flag is set to False the turn_off_light/set_light methods
        will broadcast the pin number and brightness.  Useful if you want
        to broadcast the pre/post show data to your clients without codding
        the pre/post shows config or scripts to broadcast. Allowing then to
        remain unchanged
        """
        self.playing = True

    def unset_playing(self):
        """Unset the playing flag."""
        self.playing = False
