"""light one light at a time"""
import time

# exit_event is passed in from the pre/post show script as is required
# if an exit_event is generated the pre/post show script can terminate the script 
# Do not forget to include it, if you do not sms commands will not be able
# to end the script and you will have to wait for it to finish
def main(exit_event):
    """
    Test pattern 1

    Lights one channel at a time in order
    """
    # this is a list of all the channels you have access to
    lights = hc._GPIO_PINS

    # start with all the lights off
    hc.turn_on_lights()

    # pause for 1 second
    time.sleep(2)

    # working loop
    for _ in range(50):
        # here we just loop over the gpio pins
        for light in range(len(lights)):
            # turn off all the lights
            hc.turn_off_lights()

            # then turn on one
            hc.turn_on_light(light)

            # wait a little bit before the for loop
            # starts again and turns on the next light
            time.sleep(.4)

        # this is required so that an sms play now command will 
        # end your script and any subprocess you have statred
        if exit_event.is_set():
            break

    # lets make sure we turn off the lights before we go back to the show
    hc.turn_off_lights()
