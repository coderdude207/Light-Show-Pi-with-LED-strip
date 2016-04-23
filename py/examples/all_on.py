"""Simple script to turn on all the lights"""

import time

# exit_event is passed in from the pre/post show script as is required
# if an exit_event is generated the pre/post show script can terminate the script 
# Do not forget to include it, if you do not sms commands will not be able
# to end the script and you will have to wait for it to finish
def main(exit_event):
    """Turn all the lights on for 2 minutes"""

    return_value = 0
    # turn on all the lights
    hc.turn_on_lights()

    # run for 2 minutes
    end = time.time() + 120

    # working loop will run as long as time.time() is less then "end"
    while time.time() < end:
        # this is required so that an sms play now command will 
        # end your script and any subprocess you have statred
        if exit_event.is_set():
            break

    # lets make sure we turn off the lights before we go back to the show
    hc.turn_off_lights()
