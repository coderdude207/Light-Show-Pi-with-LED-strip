"""Simple script to walk the lights up and down"""

import time

# exit_event is passed in from the pre/post show script as is required
# if an exit_event is generated the pre/post show script can terminate the script 
# Do not forget to include it, if you do not sms commands will not be able
# to end the script and you will have to wait for it to finish
def main(exit_event):
    """
    ladder

    Lights one channel at a time in order
    Then backs down to the first
    Then repeat everything 20 times
    """
    # this is a list of all the channels you have access to
    lights = hc._GPIO_PINS
    # start with all the lights off
    hc.turn_off_lights()

    # pause for 1 second
    time.sleep(1)

    # working loop
    for _ in range(20):
        # here we just loop over the gpio pins and do something with them
        # except the last one
        for light in range(len(lights)-1):
            # turn off all the lights
            hc.turn_off_lights()

            # then turn on one
            hc.turn_on_light(light)

            # wait a little bit
            time.sleep(.04)

        # to make the transition back smoother we handle the last pin here
        hc.turn_off_lights()
        hc.turn_on_light(light + 1)

        # this loop walks it back the other way
        for light in range(len(lights)-1, 0, -1):
            # turn off all the lights
            hc.turn_off_lights()

            # then turn on one
            hc.turn_on_light(light)

            # wait a little bit
            time.sleep(.04)

        # again to make it smoother handle the first pin like the last pin
        hc.turn_off_lights()
        hc.turn_on_light(light - 1)

        # this is required so that an sms play now command will 
        # end your script and any subprocess you have statred
        if exit_event.is_set():
            break

    # lets make sure we turn off the lights before we go back to the show
    hc.turn_off_lights()
