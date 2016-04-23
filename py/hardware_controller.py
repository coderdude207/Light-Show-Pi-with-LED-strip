#!/usr/bin/env python
#
# Licensed under the BSD license.  See full license in LICENSE file.
# http://www.lightshowpi.com/
#
# Author: Ryan Jennings
# Author: Chris Usey
# Author: Todd Giles (todd@lightshowpi.com)
# Author: Tom Enos (tomslick.ca@gmail.com)

"""Control the raspberry pi hardware.

The hardware controller handles all interaction with the raspberry pi
hardware to turn the lights on and off.

Third party dependencies:

wiringpi2: python wrapper around wiring pi
    https://github.com/WiringPi/WiringPi2-Python
"""

import argparse
import logging
import math
import time
import sys
import Platform
import random
import atexit
import signal
import threading
import os

import configuration_manager
from collections import defaultdict
import networking


state = None


def end_early():
    """atexit function"""
    if state == "random_pattern":
        exit_event.set()
        time.sleep(3)
        turn_off_lights()


atexit.register(end_early)

# Remove traceback on Ctrl-C
signal.signal(signal.SIGINT, lambda x, y: sys.exit(0))

cm = configuration_manager.Configuration()

is_a_raspberryPI = Platform.platform_detect() == 1

if is_a_raspberryPI:
    import wiringpi2 as wiringpi
else:
    # if this is not a RPi you can't run wiringpi so lets load
    # something in its place
    import wiring_pi as wiringpi

    logging.debug("Not running on a raspberryPI")

_PWM_MAX = cm.hardware.pwm_range
_ACTIVE_LOW_MODE = cm.hardware.active_low_mode

always_on_channels = cm.lightshow.always_on_channels
always_off_channels = cm.lightshow.always_off_channels
inverted_channels = cm.lightshow.invert_channels

# Initialize GPIO
_GPIOASINPUT = 0
_GPIOASOUTPUT = 1
GPIOLEN = cm.hardware.gpio_len

is_pin_pwm = list()
for mode in range(len(cm.hardware.pin_modes)):
    if cm.hardware.pin_modes[mode] == "pwm":
        is_pin_pwm.append(True)
    else:
        is_pin_pwm.append(False)

# Check ActiveLowMode Configuration Setting
if _ACTIVE_LOW_MODE:
    # Enabled
    _GPIOACTIVE = 0
    _PWM_ON = 0
    _GPIOINACTIVE = 1
    _PWM_OFF = _PWM_MAX
else:
    # Disabled
    _GPIOACTIVE = 1
    _PWM_ON = _PWM_MAX
    _GPIOINACTIVE = 0
    _PWM_OFF = 0

# left in for compatibility with external scripts
_GPIO_PINS = cm.hardware.gpio_pins


# Functions
def enable_device():
    """enable the specified device """
    try:
        devices = cm.hardware.devices

        for key in devices.keys():
            device = key
            device_slaves = devices[key]

            # mcp23017
            if device.lower() == "mcp23017":
                for slave in device_slaves:
                    params = slave
                    wiringpi.mcp23017Setup(int(params['pinBase']),
                                           int(params['i2cAddress'],
                                               16))

            # mcp23s17
            elif device.lower() == "mcp23s17":
                for slave in device_slaves:
                    params = slave
                    wiringpi.mcp23s17Setup(int(params['pinBase']),
                                           int(params['spiPort'],
                                               16),
                                           int(params['devId']))

            # TODO: Devices below need testing, these should work but
            # could not verify due to lack of hardware

            # mcp23016
            elif device.lower() == "mcp23016":
                for slave in device_slaves:
                    params = slave
                    wiringpi.mcp23016Setup(int(params['pinBase']),
                                           int(params['i2cAddress'],
                                               16))

            # mcp23s08 - Needs Testing
            elif device.lower() == "mcp23008":
                for slave in device_slaves:
                    params = slave
                    wiringpi.mcp23008Setup(int(params['pinBase']),
                                           int(params['i2cAddress'],
                                               16))

            # mcp23s08 - Needs Testing
            elif device.lower() == "mcp23s08":
                for slave in device_slaves:
                    params = slave
                    wiringpi.mcp23s08Setup(int(params['pinBase']),
                                           int(params['spiPort'],
                                               16),
                                           int(params['devId']))

            # sr595 - Needs Testing
            elif device.lower() == "sr595":
                for slave in device_slaves:
                    params = slave
                    wiringpi.sr595Setup(int(params['pinBase']),
                                        int(params['numPins']),
                                        int(params['dataPin']),
                                        int(params['clockPin']),
                                        int(params['latchPin']))

            # pcf8574
            elif device.lower() == "pcf8574":
                for slave in device_slaves:
                    params = slave
                    wiringpi.pcf8574Setup(int(params['pinBase']),
                                          int(params['i2cAddress'],
                                              16))

            else:
                logging.error("Device defined is not supported, please check "
                              "your devices settings: " + str(device))
    except Exception as error:
        logging.debug("Error setting up devices, please check your devices "
                      "settings.")
        logging.debug(error)


def set_pins_as_outputs():
    """Set all the configured pins as outputs."""
    for pin in range(GPIOLEN):
        set_pin_as_output(pin)


def set_pin_as_output(pin):
    """Set the specified pin as an output.

    :param pin: index of pin in cm.hardware.gpio_pins
    :type pin: int
    """
    if is_pin_pwm[pin]:
        wiringpi.softPwmCreate(cm.hardware.gpio_pins[pin], 0, _PWM_MAX)
    else:
        wiringpi.pinMode(cm.hardware.gpio_pins[pin], _GPIOASOUTPUT)


def set_pins_as_inputs():
    """Set all the configured pins as inputs."""
    for pin in range(GPIOLEN):
        set_pin_as_input(pin)


def set_pin_as_input(pin):
    """Set the specified pin as an input.

    :param pin: index of pin in cm.hardware.gpio_pins
    :type pin: int
    """
    wiringpi.pinMode(cm.hardware.gpio_pins[pin], _GPIOASINPUT)


def turn_off_lights(use_always_onoff=False):
    """
    Turn off all the lights

    But leave on all lights designated to be always on if specified.

    :param use_always_onoff: boolean, should always on/off be used
    :type use_always_onoff: bool
    """
    for pin in range(GPIOLEN):
        set_light(pin, use_always_onoff, 0)


# turn_off_light and turn_on_light are left in for compatibility 
# with external scripts and will be removed in future versions
def turn_off_light(pin, use_overrides=False):
    """
    Turn off the specified light

    Taking into account various overrides if specified.

    :param pin: index of pin in cm.hardware.gpio_pins
    :type pin: int

    :param use_overrides: should overrides be used
    :type use_overrides: bool
    """
    set_light(pin, use_overrides, 0)


def turn_on_light(pin, use_overrides=False, brightness=1.0):
    """
    Turn off the specified light

    Taking into account various overrides if specified.

    :param pin: index of pin in cm.hardware.gpio_pins
    :type pin: int

    :param use_overrides: should overrides be used
    :type use_overrides: bool
    """
    set_light(pin, use_overrides, brightness)


def turn_on_lights(use_always_onoff=False):
    """
    Turn on all the lights

    But leave off all lights designated to be always off if specified.

    :param use_always_onoff: should always on/off be used
    :type use_always_onoff: bool
    """
    for pin in range(GPIOLEN):
        set_light(pin, use_always_onoff)


def set_light(pin, use_overrides=False, brightness=1.0):
    """Set the brightness of the specified light
    
    Taking into account various overrides if specified.
    The default is full on (1.0)
    To turn a light off pass 0 for brightness
    If brightness is a float between 0 and 1.0 that level 
    will be set.
    
    This function replaces turn_on_light and turn_off_light

    :param pin: index of pin in cm.hardware.gpio_pins
    :type pin: int

    :param use_overrides: should overrides be used
    :type use_overrides: bool

    :param brightness: float, a float representing the brightness of the lights
    :type brightness: float
    """
    if math.isnan(brightness):
        brightness = 0.0

    if _ACTIVE_LOW_MODE:
        brightness = 1.0 - brightness

    if use_overrides:
        if pin + 1 in always_off_channels:
            brightness = 0
        elif pin + 1 in always_on_channels:
            brightness = 1

        if pin + 1 in inverted_channels:
            brightness = 1 - brightness

    if not network.playing and server:
        network.broadcast(cm.hardware.gpio_pins.index(cm.hardware.gpio_pins[pin]), brightness)

    if is_pin_pwm[pin]:
        wiringpi.softPwmWrite(cm.hardware.gpio_pins[pin], int(brightness * _PWM_MAX))
    else:
        wiringpi.digitalWrite(cm.hardware.gpio_pins[pin], int(brightness > 0.5))


def clean_up():
    """
    Clean up and end the lightshow

    Turn off all lights and set the pins as inputs
    """
    network.unset_playing()
    turn_off_lights()
    set_pins_as_inputs()


def initialize():
    """Set pins as outputs and start all lights in the off state."""
    wiringpi.wiringPiSetup()
    enable_device()
    set_pins_as_outputs()

    turn_off_lights()

# network setup if used
network = networking.Networking(cm)
server = network.networking == "server"


# test functions
def light_on(pins, override=False, brightness=1.0):
    """work around to make custom channel mapping work with hardware tests"""
    if ccm:
        pins = ccm_map[pins]
    else:
        pins = [pins]

    if len(pins) == 0:
        return

    for pin in pins:
        if not is_pin_pwm[pin]:
            brightness = 1

        set_light(pin, use_overrides=override, brightness=brightness)


def light_off(pins, override=False, brightness=0.0):
    """work around to make custom channel mapping work with hardware tests"""
    if ccm:
        pins = ccm_map[pins]
    else:
        pins = [pins]

    if len(pins) == 0:
        return

    for pin in pins:
        set_light(pin, use_overrides=override, brightness=brightness)


def fade(from_test=False):
    """Fade lights in and out in sequence"""
    # Test fading in and out for each light configured in pwm mode
    if not from_test:
        print "Press <CTRL>-C to stop"

    if ccm:
        print "custom channel mapping is being used"
        print "multiple channels may display that the same time"

    while True:
        for light in lights:
            if ccm:
                for p in ccm_map[light]:
                    print "channel %s : gpio pin number %d" % (str(p + 1), cm.hardware.gpio_pins[p])
            else:
                print "channel %s : gpio pin number %d" % (
                    str(light + 1), cm.hardware.gpio_pins[light])

            print

            if is_pin_pwm[light]:
                for _ in range(flashes):
                    for brightness in range(0, _PWM_MAX + 1):
                        # fade in
                        light_on(light, False, float(brightness) / _PWM_MAX)
                        time.sleep(sleep / _PWM_MAX)
                    for brightness in range(_PWM_MAX - 1, -1, -1):
                        # fade out
                        light_on(light, False, float(brightness) / _PWM_MAX)
                        time.sleep(sleep / _PWM_MAX)
            else:
                print "channel %s not set to pwm mode" % light

        if from_test:
            return


def flash(from_test=False):
    """Flash lights in sequence"""
    if not from_test:
        print "Press <CTRL>-C to stop"

    if ccm:
        print "custom channel mapping is being used"
        print "multiple channels may display that the same time"

    while True:
        for light in lights:
            if ccm:
                for p in ccm_map[light]:
                    print "channel %s : gpio pin number %d" % (str(p + 1), cm.hardware.gpio_pins[p])
            else:
                print "channel %s : gpio pin number %d" % (
                    str(light + 1), cm.hardware.gpio_pins[light])

            print

            for _ in range(flashes):
                light_on(light)
                time.sleep(sleep)
                light_off(light)
                time.sleep(sleep)
        if from_test:
            return


def cylon():
    """Cylon

    Lights one channel at a time in order
    Then backs down to the first rapidly
    """
    # pause for 1 second
    time.sleep(1)

    # working loop
    print "Press <CTRL>-C to stop"
    while True:
        # here we just loop over the gpio pins and do something with them
        # except the last one
        for light in range(len(lights) - 1):
            # turn off all the lights
            for l in lights:
                light_off(l)

            # then turn on one
            light_on(light)

            # wait a little bit
            time.sleep(.06)

        # to make the transition back smoother we handle the last pin here
        for l in lights:
            light_off(l)
        light_on(light + 1)

        # this loop walks it back the other way
        for light in range(len(lights) - 1, 0, -1):
            # turn off all the lights
            for l in lights:
                light_off(l)

            # then turn on one
            light_on(light)

            # wait a little bit
            time.sleep(.06)

        # again to make it smoother handle the first pin like the last pin
        for l in lights:
            light_off(l)
        light_on(light - 1)


def random_pattern():
    """Display a random pattern of lights
    
    This will turn your lights on in a random pattern.  It will read the pin modes
    and use that for the channels you have set.  pwm fade for pwm mode and flash
    for onoff mode.
    
    From the command line you can set lights to work in groups by using the 
    --lights_in_group option (default 1)
    --lights_in_group is the number of lights that you wish to be bound as a group.
    if set to 3, 3 channels will be bound to the first group, and this will continue
    until all channels have been use in order of pin assignment with the last
    group containing the all leftover channels in the case of odd assignment.
   
    and you can adjust the speed of fade with the --pwm_speed option (default .5).  
    
    If you wish to alter the pattern delay the --sleep' (default 0.5 seconds) is
    the minimum between transitions and the maximum is defined as max_pause
    (default 4 time min_pause) in this function.  This value is a random time
    between the min and max values and not a guarantee of exact time between 
    transitions and will change for every transitions.

    --pwm_speed is the time it takes for full on or full off measured in seconds.
    .5 is half a second and 1 is a full second

    A complete command string would look like
    sudo python hardware_controller --state=random_pattern --lights_in_group=2 --sleep=.75 --pwm_speed=1.5
    
    Initial implementation Thanks to Russell Pyburn. 
    """
    # your gpio pins
    pins = cm.hardware.gpio_pins

    min_pause = sleep * 1000

    # min and max time to pause before restarting light group
    max_pause = min_pause * 4.0

    light_group = list()
    step_range = [_ for _ in range(_PWM_MAX)]
    step_range.extend([_ for _ in range(_PWM_MAX, -1, -1)])

    def the_lights(exit_e, lits):
        while True:
            if exit_e.is_set():
                break

            time.sleep(random.randrange(min_pause, max_pause) * .001)

            # activate the lights
            for stp in step_range:
                for pin in lits:
                    light_on(pins.index(pin), True, stp * .01)

                time.sleep(pwm_speed / float(_PWM_MAX))

    # start the threads
    for group in range(0, len(pins), lights_per_group):
        light_group.append(threading.Thread(target=the_lights, args=(
            exit_event, pins[group:group + lights_per_group],)))
        light_group[-1].setDaemon(True)
        light_group[-1].start()

    print "press <ctrl-c> to exit"
    while True:
        time.sleep(.1)


def dance():
    """
    dancing pair

    Start at each end and dance to the other using pwm or onoff
    """
    # the gpio pins in reversed order
    lights2 = lights[::-1]

    # get _PWM_MAX from the hc module
    # this is the max value for the pwm channels
    pwm_max = _PWM_MAX

    # working loop, we will do this sequence 10 times then end
    while True:
        # here we just loop over the gpio pins and turn them on and off
        # with the pwm feature of lightshowpi
        for light in range(int(len(lights) / 2)):
            if is_pin_pwm[light]:
                for brightness in range(0, pwm_max):
                    # fade in
                    light_on(lights[light], 0, brightness=float(brightness) / pwm_max)
                    light_on(lights2[light], brightness=float(brightness) / pwm_max)
                    time.sleep(.1 / pwm_max)

                for brightness in range(pwm_max - 1, -1, -1):
                    # fade out
                    light_on(lights[light], brightness=float(brightness) / pwm_max)
                    light_on(lights2[light], brightness=float(brightness) / pwm_max)
                    time.sleep(.1 / pwm_max)
            else:
                light_on(lights[light], 1)
                light_on(lights2[light], 1)
                time.sleep(.5)
                light_off(lights[light], 0)
                light_off(lights2[light], 0)

        for light in range(int(len(lights) / 2) - 1, -1, -1):
            if is_pin_pwm[light]:
                for brightness in range(0, pwm_max):
                    # fade in
                    light_on(lights[light], brightness=float(brightness) / pwm_max)
                    light_on(lights2[light], brightness=float(brightness) / pwm_max)
                    time.sleep(.1 / pwm_max)

                for brightness in range(pwm_max - 1, -1, -1):
                    # fade out
                    light_on(lights[light], brightness=float(brightness) / pwm_max)
                    light_on(lights2[light], brightness=float(brightness) / pwm_max)
                    time.sleep(.1 / pwm_max)
            else:
                light_on(lights[light], 1)
                light_on(lights2[light], 1)
                time.sleep(.5)
                light_off(lights[light], 0)
                light_off(lights2[light], 0)


def step():
    """Test fading in and out for each light configured in pwm mode"""
    print "Press <CTRL>-C to stop"
    while True:
        for light in lights:
            print "channel %s " % light
            for brightness in range(0, _PWM_MAX):
                # fade in
                light_on(light, False, float(brightness) / _PWM_MAX)
                time.sleep(sleep / _PWM_MAX)

        for light in reversed(lights):
            print "channel %s " % light
            for brightness in range(_PWM_MAX - 1, -1, -1):
                # fade out
                if is_pin_pwm[light]:
                    light_on(light, False, float(brightness) / _PWM_MAX)
                else:
                    light_off(light, False, 0)
                time.sleep(sleep / _PWM_MAX)


def test():
    model, header = Platform.get_model()

    print "We are going to do some basic tests to make sure"
    print "your hardware is working as expected."
    print "Raspberry Pi %s" % model
    print "You have %s channels defined" % str(cm.hardware.gpio_len)
    print "They are using gpio pins %s" % ", ".join(map(str, cm.hardware.gpio_pins))
    print "You have configured your relays as active %s" % (
        "low" if cm.hardware.active_low_mode else "high")
    print "pin_modes are %s " % ", ".join(cm.hardware.pin_modes)
    print "custom_channel_mapping %s being used" % ("is" if ccm else "is not")

    if ccm:
        print "[%s]" % ", ".join(map(str, cm.audio_processing.custom_channel_mapping))

    print "\nFirst we are going to flash each light in order to see if they are all working"

    raw_input("Press Enter to continue....")

    flash(True)

    print "If everything went correctly you should have seen each of your channels"
    print "flash one at a time in order of assignment."

    while True:
        answer = raw_input("Did you see all channels flash in order? (yes/no) ").lower()
        yes = ['yes', 'y', 'yep', 'ja', 'si', 'oui']
        no = ['no', 'n', 'nope', 'nein', 'non']

        if answer in yes or answer in no:
            if answer in yes:
                print "Great, your basic config is ready for you to start with\n\n"

                return

            if answer in no:
                print "Lets make sure you're using the correct gpio pins"
                print "Here is what the %s header looks like\n" % model
                print header
                print
                print "Make sure you are using the correct pins as listed above"

                if ccm:
                    print "Disable custom channel mapping to help with debugging your config"

                print "After you have made these corrections please rerun this test\n\n"

                return

        print "Please answer yes or no"


def main():
    """main"""
    initialize()
    network.unset_playing()

    if args.test:
        test()
        return

    if state == "cleanup":
        clean_up()

    elif state == "off":
        for light in lights:
            light_off(light)

    elif state == "on":
        for light in lights:
            light_on(light)

    elif state == "fade":
        fade()

    elif state == "flash":
        flash()

    elif state == "random_pattern":
        random_pattern()

    elif state == "cylon":
        cylon()

    elif state == "dance":
        dance()

    elif state == "step":
        step()

    else:
        parser.print_help()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--state', choices=["off",
                                            "on",
                                            "flash",
                                            "fade",
                                            "random_pattern",
                                            "cylon",
                                            "dance",
                                            "step",
                                            "cleanup"],
                        help='turn off, on, flash, or cleanup')
    parser.add_argument('--test', action="store_true",
                        help='Run a basic hardware test')

    parser.add_argument('--light', default='-1',
                        help='the lights to act on (comma delimited list), -1 for all lights')
    parser.add_argument('--sleep', default=0.5,
                        help='how long to sleep between flashing or fading a light')
    parser.add_argument('--flashes', default=2,
                        help='the number of times to flash or fade each light')
    parser.add_argument('--lights_in_group', default=1,
                        help='number of light in a group')
    parser.add_argument('--pwm_speed', default=0.5,
                        help='time in seconds to full on or off')

    args = parser.parse_args()
    state = args.state
    sleep = float(args.sleep)

    flashes = int(args.flashes)
    lights_per_group = int(args.lights_in_group)
    pwm_speed = float(args.pwm_speed)

    ccm = False
    lights = [int(lit) for lit in args.light.split(',')]

    if -1 in lights:
        lights = range(0, cm.hardware.gpio_len)

        if cm.audio_processing.custom_channel_mapping != 0 and len(
                cm.audio_processing.custom_channel_mapping) == cm.hardware.gpio_len:
            ccm = True
            cc = [i - 1 for i in cm.audio_processing.custom_channel_mapping]
            ccm_map = dict()

            for lit in lights:
                ccm_map[lit] = [idx for idx, pin_num in enumerate(cc) if pin_num == lit]

            if len(lights) == cm.hardware.gpio_len:
                lights = range(max(cm.audio_processing.custom_channel_mapping))

    if state == "random_pattern":
        exit_event = threading.Event()

    main()
