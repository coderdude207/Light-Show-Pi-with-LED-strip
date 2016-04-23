 
This is a little guide to help you write your own little python scripts to
control a custom pre or post show

It will require you to learn a little bit of python
https://www.python.org/

But don't worry is not all that hard and with just a few commands you can 
make your lights do all kinds of things.

Lets start with a basic template that you will need to follow

[code]

import time

def main(exit_event):

    lights = hc._GPIO_PINS
    
    <a loop>
    
        <your code here>
            
        if exit_event.is_set():
            break

[/code]

First import your modules.
NOTE: You do not need to import the hardware_controller module,
      it has been made avaliable as a global variable in the prepostshow script
      that calls this.
      Also note that because of this your script will not run by it self.
      you will need to run it through prepostshow.

The time module is not strictly needed but it comes in handy

You need to place most of your code in the main() function inside a loop of some kind.

For the pre or post show to call your main function you need to include one parameter
in the function definition.  exit_event to make your definition look like the below example

def main(exit_event):

exit_event is used to end your script if a play now request comes in.
It must be included or your script will not work, but you do not have to use it
if you don't want to.  It just means that the script will have to finish before
it exits.

Then I think it's a good idea to assign the list of gpio pins to an easy to remember
variable name, but _GPIO_PINS in hardware_controller is the same list,
you can decide which way you want to use them.
You can also setup other things at this point if you need or want to.
Setup other variables (like storing a start time from the time module)
Start playing some audio.
What ever you might need.

The loop is where almost everything will happen
while <exit condition>:
or
for count in range(<number>):

A for loop will execute the body of the loop a set number of times

>>> for count in range(10):
...     print count
... 
0
1
2
3
4
5
6
7
8
9

The above for loop will run through 10 times and print the value of count each time
From 0 to 9, python starts counting at 0

A while loop will execute the body of the loop until the <exit condition> is met

>>> count = 0
>>> while count < 10:
...     print count
...     count = count + 1
... 
0
1
2
3
4
5
6
7
8
9

The above while loop will run through as long as count is less then 10
This time we started with count = 0 and told it to stop when count was greater then 9
if you print the value of count you will see that it equals 10
>>> print count
10

In your loop you added 1 to count every time through after you printed the result
After 9 was printed you added 1 to count making it 10, but the next time through
the loop count as not less then 10 (it was 10) so the loop exited 

Either is fine, just remember to test your <exit condition> if you use a while loop
a bad <exit condition> will cause the loop not to run or trap you in an infinite loop

This is used by the pre/post shows to exit your script if a play now request happens
include this in the working loop, either at the top or bottom, it dosen't matter,
as long as it is in there.

if exit_event.is_set():
    break
            
After your loop finishes it you will want to turn off all the lights.

hc.turn_off_lights()

These are the functions that you can use from the hardware_controller module

turn_on_light(light)
    this will turn on one light, you need to pass in the the gpio pin number
    if your gpio pins are set to onoff instead of pwm and you have allways_on
    allways_off channels set in your config files you can add an argument to 
    enforce these settings
    hc.turn_on_light(pin#, useoverrides=0)

turn_off_light(light)
    the oppisite of turn_on_light()
    hc.turn_off_light(pin#, useoverrides=0)

turn_on_lights()
    this will turn on all the light  if your gpio pins are set to onoff instead 
    of pwm and you have allways_on allways_off channels set in your config files
    you can add an argument to enforce these settings
    turn_on_lights(usealwaysonoff=0)

turn_off_lights()
    the oppisite of turn_off_lights()
    turn_off_lights(usealwaysonoff=0)
    
is_pin_pwm[pin]
    check if a pin is in pwm mode.
    NOTE: this is not a function, it is a list make sure you use [] and not ()

There are a few other functions in hardware_controller but there is no need for
them to be used here.  

You can use any combination of the above to create anything you wish

Included are several basic examples to get you started
Please look at the examples as they will show you better how to use the above 
functions, and show you some other things that you might want to do.
Two examples of note are play_message.py and PWM_example, the first has an example
that allows you to play an audio file while you are manipulating the lights
the latter is an examples of using the software PWM feature offered in lightshowpi.

Happy coding
