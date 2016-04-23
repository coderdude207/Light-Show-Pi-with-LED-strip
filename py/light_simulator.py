# !/usr/bin/env python
#
# Licensed under the BSD license.  See full license in LICENSE file.
# http://www.lightshowpi.com/
#
# Author: Tom Enos
"""Simple Gui to see what the lightshow is doing

The is a development tool made so that you do not need to keep setting up your
RPI with a breadboard and leds.  It allows you to edit and run the code right
on you linux desktop.

Setup:
      You will need to install the dependencies for lightshowpi on you computer
      look at the install scripts to see what is needed.
      
Usage:
      Open 2 terminals, in both export your SYNCHRONIZED_LIGHTS_HOME variable
      or you can export it globaly and not do this all the time.  But if your
      working with different versions in different directories you might not want
      to do that.  Next edit (or create)overrides.cfg and under [network] set 
      networking = server In one of the terminals start this sim.  You will not
      see anything yet.  In the second terminal start synchronized_lights.py as
      a regular user without sudo (you don't need access to the gpio pins) so
      you don't need to run as root
      
      When the show starts a Tkinter window will open up and you can see what
      lightshowpi is doing.  Just leave the Tkinter window running.  Every time
      you run synchronized_lights it will respond.
      
Note:
      Also note if you do globally set SYNCHRONIZED_LIGHTS_HOME the scripts in
      the bin folder should also work with this as well as the sms code if you 
      set everything up correctly.

      Audio-in might be a problem on some distros.  For example the audioop module
      is not part of my version of openSuse.  But it is in Debian and Ubuntu so
      it will work with them.
"""

from math import ceil
import Tkinter
import numpy as np
import hardware_controller as hc
from Tkinter import Canvas
import math

CM = hc.cm
CM.network.networking = "client"
hc.network = hc.networking.Networking(CM)
hc.server = hc.network.networking == "server"
network = hc.network


class Gui(Canvas):
    """Simple Gui to see what the lightshow is doing"""

    def __init__(self, parent):
        Canvas.__init__(self, parent)
        self.gpio_pins = CM.hardware.gpio_pins
        self.gpiolen = CM.hardware.gpio_len
        self.pwm_max = CM.hardware.pwm_range
        self.gpioactive = hc._GPIOACTIVE
        self.is_pin_pwm = hc.is_pin_pwm
        self.gpio = list()
        self.state = list()
        self.channels = [_ for _ in range(self.gpiolen)]
        self.channel_keys = CM.network.channels.keys()
        self.network = hc.network
        self.red = "#FF0000"
        self.green = "#00FF00"
        self.blue = "#0000FF"
        self.white = "#FFFFFF"
        self.black = "#000000"
        self.parent = parent
        self.init_ui()
        self.tkinter_function()

    def init_ui(self):
        """initialize the ui"""
        # on screen position of the tkinter window
        # 0,0 top left corner
        screen_x = 0
        screen_y = 0

        # radius of lights
        rad = 10

        # column and row of the first light inside the tkinter window
        column = rad * 2
        row = rad * 2

        # lights are evenly spaced by half the radius
        spacing = (rad * 2) + (rad / 2)

        # How many lights in a row
        max_row_length = 16

        row_length = self.gpiolen

        if self.gpiolen > max_row_length:
            row_length = max_row_length

        # calculate number of rows
        rows = int(ceil(self.gpiolen / row_length))

        # size of the window
        width = (row_length * spacing) + int((rad * 1.75))
        height = (rows * spacing) + int(rad * 1.75)

        self.parent.geometry('{0:d}x{1:d}+{2:d}+{3:d}'.format(width,
                                                              height,
                                                              screen_x,
                                                              screen_y))
        self.parent.title("Lights")
        self.parent.protocol("WM_DELETE_WINDOW", self.quit)
        column_worker, row_worker = column, row

        row_counter = 0

        for _ in range(self.gpiolen):
            top_left = column_worker - rad
            bottom_left = row_worker - rad
            top_right = column_worker + rad
            bottom_right = row_worker + rad

            self.gpio.append(self.create_oval(top_left,
                                              bottom_left,
                                              top_right,
                                              bottom_right,
                                              fill="#FFFFFF"))

            column_worker += spacing
            row_counter += 1

            if row_counter == row_length:
                column_worker = column
                row_worker += spacing
                row_counter = 0

        self.pack(fill=Tkinter.BOTH, expand=1)

    def start_display(self):
        """
        start the display
        """
        self.tkinter_function()
        self.parent.mainloop()

    def quit(self):
        """
        close the window
        """
        if 'normal' == self.parent.state():
            self.parent.destroy()

    def tkinter_function(self):
        """this is where the window is updated"""
        blevels = None
        data = self.network.receive()
        done = False

        if isinstance(data[0], int):
            pin = data[0]
            if pin in self.channel_keys:
                self.set_light(self.channels[pin], True, float(data[1]))
            done = True

        elif isinstance(data[0], np.ndarray):
            blevels = data[0]

        else:
            done = True

        if not done:
            for pin in self.channel_keys:
                self.set_light(self.channels[pin], True, blevels[pin])

        self.parent.after(1, self.tkinter_function)

    def set_light(self, pin, use_overrides=False, brightness=1.0):
        """Set the brightness of the specified light

        Taking into account various overrides if specified.
        The default is full on (1.0)
        To turn a light off pass 0 for brightness
        If brightness is a float between 0 and 1.0 that level
        will be set.

        This function replaces turn_on_light and turn_off_light

        :param pin: index of pin in CM.hardware.gpio_pins
        :type pin: int

        :param use_overrides: should overrides be used
        :type use_overrides: bool

        :param brightness: float, a float representing the brightness of the lights
        :type brightness: float
        """
        if math.isnan(brightness):
            brightness = 0.0

        if hc._ACTIVE_LOW_MODE:
            brightness = 1.0 - brightness

        if use_overrides:
            if pin + 1 in hc.always_off_channels:
                brightness = 0
            elif pin + 1 in hc.always_on_channels:
                brightness = 1

            if pin + 1 in hc.inverted_channels:
                brightness = 1 - brightness

        if hc.is_pin_pwm[pin]:
            brightness = int(brightness * self.pwm_max)
            if self.gpioactive:
                brightness = 100 - brightness
            level = '#{0:02X}{1:02X}{2:02X}'.format(255,
                                                    int(ceil(brightness * 2.55)),
                                                    int(ceil(brightness * 2.55)))
            try:
                item = self.gpio[pin]
                print item, level, brightness, int(ceil(brightness * 2.55))
                self.itemconfig(item, fill=level)
                self.parent.update()
            except:
                pass
        else:
            item = self.gpio[pin]
            onoff = int(brightness > .5)
            if self.gpioactive:
                onoff = 1 - onoff
            color = (self.blue, self.white)[onoff]
            try:
                self.itemconfig(item, fill=color)
                self.parent.update()
            except:
                pass


def main():
    """main function, start the process"""
    parent = Tkinter.Tk()
    parent.geometry("250x150+300+300")
    Gui(parent)
    parent.mainloop()


if __name__ == "__main__":
    main()
