"""Example Template"""

import time

lights = hc._GPIO_PINS

# exit_event is passed in from the pre/post show script as is required
# if an exit_event is generated the pre/post show script can terminate the script 
# Do not forget to include it, if you do not sms commands will not be able
# to end the script and you will have to wait for it to finish
def main(exit_event):
    """
    Empyt script template for you to use
    """
    # USE ONE OF THE BELOW LOOPS AS A STARTING POINT
    # JUST UNCOMMENT ONE AND DELETE THE OTHERS

    for count in range(10):

    #count = 0
    #while count < 10:
        #count += 1

    # change number_of_seconds_to_run_for to the number of seconds you what
    # this to run for 60 is 1 minute 3600 is 1 hour

    #end_time = time.time() + number_of_seconds_to_run_for
    #while time.time() < end_time:

    ####<PUT ALL YOU CODE IN THIS BLOCK>
        
        # include this in your loop
        # it is required so that an sms play now command will 
        # end your script and any subprocess you have statred
        if exit_event.is_set():
            break

    # lets make sure we turn off the lights before we go back to the show
    hc.turn_off_lights()
