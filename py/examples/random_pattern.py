"""Randomly turn off about 40% of the lights"""

import time
import random

# exit_event is passed in from the pre/post show script as is required
# if an exit_event is generated the pre/post show script can terminate the script 
# Do not forget to include it, if you do not sms commands will not be able
# to end the script and you will have to wait for it to finish
def main(exit_event):
    """
    Random flashing lights
    """
    # required to cleanup all processes

    # this is a list of all the channels you have access to
    # I'm also tracking the time here so that I know when I turned a light off
    # So I'm putting everything in a dict
    gpio_pins = hc._GPIO_PINS
    lights = dict.fromkeys(range(0, len(gpio_pins)), [True, time.time()])

    # get a number that is about 40% the length of your gpio's
    # this will be use to make sure that no more then 40% of
    # the light will be off at any one time
    max_off = int(round(len(lights) * .4))

    # start with all the lights on
    hc.turn_on_lights()

    # lets run for 2 minutes
    end = time.time() + 120

    # working loop will run as long as time.time() is less then "end"
    while time.time() < end:
        # here we just loop over the gpio pins
        for light in lights:
            # this is where we check to see if we have any light
            # that are turned off
            # if they are off we will check the time to see if we
            # want to turn them back on yet, if we do then turn it on
            if not lights[light][0]:
                if lights[light][1] < time.time():
                    lights[light][0] = True
                    hc.turn_on_light(light)

        # count the number of lights that are off
        off = [k for (k, v) in lights.iteritems() if v.count(1) == False]

        # if less then out max count of light that we chose
        # we can turn one off
        if len(off) < max_off:
            # pick a light at random to turn off
            choice = random.randrange(0, len(gpio_pins))
            # if it's on then lets turn it off
            if lights[choice][0]:
                # pick a duration for that light to be off
                # default times are between 1/2 and secong and 1.8 seconds
                duration = random.uniform(0.5, 1.8)

                # store this informatin in our dict
                lights[choice] = [False, time.time() + duration]
                # and turn that light off then continue with the main loop
                # and do it all over again
                hc.turn_off_light(choice)

        # this is required so that an sms play now command will 
        # end your script and any subprocess you have statred
        if exit_event.is_set():
            break

    # lets make sure we turn off the lights before we go back to the show
    hc.turn_off_lights()
