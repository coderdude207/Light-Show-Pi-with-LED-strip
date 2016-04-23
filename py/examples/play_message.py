"""simple script to play a message in the lightshow"""

# import the subprocess module so that
# we can play some audio in a seperate process
# which will allow us to manipulate the lights at the same time
# the os module is also required, allowing the audio to be ended
# if a play now event happens in the pre show
import subprocess
import os

# exit_event is passed in from the pre/post show script as is required
# if an exit_event is generated the pre/post show script can terminate the script 
# Do not forget to include it, if you do not sms commands will not be able
# to end the script and you will have to wait for it to finish
def main(exit_event):
    """
    Play a message

    Play a recorded message for the people and go through the lights
    one channel at a time in order, then back down to the first
    """
    # start with all the lights off
    hc.turn_off_lights()

    # Before we start the lights we should start playing the audio
    # we have installed mpg123 to make this easy
    # if you do not have mpg123 installed then use this command to install it
    # sudo apt-get install mpg123
    # now all you have to do is use the below command to play an mp3 file
    message_file = "/home/pi/lightshowpi/py/examples/message.mp3"
    message = subprocess.Popen("mpg123 -q " + message_file,
                               preexec_fn=os.setsid,
                               shell=True,
                               close_fds=True)

    # subprocess.Popen will open mpg123 player and play an audio file for you
    # and give you a few options that will come in real handy
    # you can stop mpg123 before the audio has finished using the instance
    # variable we just created by calling message.terminate()
    # or at any point in the script you can make everything wait for the audio
    # to finish playing with message.wait() that could be usefull if you
    # ran a short seuqence like in the default preshow and your audio as longer
    # then your sequence and you wanted the audio to finish before continuing
    # and if you use message.poll() or message.returncode you could find out
    # if it has finished, then you might start something else or end everything
    # and shutdown your pi.

    # lights are on while audio is playing
    hc.turn_on_lights()

    # working loop
    while True:
        # this is required so that an sms play now command will 
        # end your script and any subprocess you have statred
        if exit_event.is_set():
            os.killpg(message.pid, signal.SIGTERM)
            break

        # if audio playback has finished break out of the loop
        if message.poll() != None:
            break

    # lets make sure we turn off the lights before we go back to the show
    hc.turn_off_lights()
