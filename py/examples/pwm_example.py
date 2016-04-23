"""Example to show the use of the pwm functions in lightshowpi"""

import time

# exit_event is passed in from the pre/post show script as is required
# if an exit_event is generated the pre/post show script can terminate the script 
# Do not forget to include it, if you do not sms commands will not be able
# to end the script and you will have to wait for it to finish
def main(exit_event):
    """
    PWM example

    Start at each end and walk to the other using pwm
    """
    # this is a list of all the channels you have access to
    lights = [pin for pin in range(len(hc._GPIO_PINS))]
    
    # the gpio pins in reversed order
    lights2 = lights[::-1]
    
    # get _PWM_MAX from the hc module
    # this is the max value for the pwm channels
    pwm_max = hc._PWM_MAX
    
    # start with all the lights off
    hc.turn_on_lights()
    time.sleep(1)
    hc.turn_off_lights()
    # pause for 1 second
    time.sleep(1)

    # working loop, we will do this sequence 10 times then end
    for _ in range(10):
        # here we just loop over the gpio pins and turn them on and off
        # with the pwm feature of lightshowpi
        for light in range(int(len(lights) / 2)):
            if hc.is_pin_pwm[lights[light]] and hc.is_pin_pwm[lights2[light]]:
                for brightness in range(0, pwm_max):
                    # fade in
                    hc.turn_on_light(lights[light], 0, brightness=float(brightness)/pwm_max)
                    hc.turn_on_light(lights2[light], brightness=float(brightness)/pwm_max)
                    time.sleep(.1 / pwm_max)

                for brightness in range(pwm_max - 1, -1, -1):
                    # fade out
                    hc.turn_on_light(lights[light], brightness=float(brightness)/pwm_max)
                    hc.turn_on_light(lights2[light], brightness=float(brightness)/pwm_max)
                    time.sleep(.1 / pwm_max)

        for light in range(int(len(lights) / 2)-1, -1, -1):
            if hc.is_pin_pwm[lights[light]] and hc.is_pin_pwm[lights2[light]]:
                for brightness in range(0, pwm_max):
                    # fade in
                    hc.turn_on_light(lights[light], brightness=float(brightness)/pwm_max)
                    hc.turn_on_light(lights2[light], brightness=float(brightness)/pwm_max)
                    time.sleep(.1 / pwm_max)

                for brightness in range(pwm_max - 1, -1, -1):
                    # fade out
                    hc.turn_on_light(lights[light], brightness=float(brightness)/pwm_max)
                    hc.turn_on_light(lights2[light], brightness=float(brightness)/pwm_max)
                    time.sleep(.1 / pwm_max)

        # this is required so that an sms play now command will 
        # end your script and any subprocess you have statred
        if exit_event.is_set():
            break
    # lets make sure we turn off the lights before we go back to the show
    hc.turn_off_lights()
