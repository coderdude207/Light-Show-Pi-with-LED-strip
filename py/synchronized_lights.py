#!/usr/bin/env python
#
# Licensed under the BSD license.  See full license in LICENSE file.
# http://www.lightshowpi.com/
#
# Author: Todd Giles (todd@lightshowpi.com)
# Author: Chris Usey (chris.usey@gmail.com)
# Author: Ryan Jennings
# Author: Paul Dunn (dunnsept@gmail.com)
# Author: Tom Enos (tomslick.ca@gmail.com)

"""Play any audio file and synchronize lights to the music

When executed, this script will play an audio file, as well as turn on
and off N channels of lights to the music (by default the first 8 GPIO
channels on the Raspberry Pi), based upon music it is playing. Many
types of audio files are supported (see decoder.py below), but it has
only been tested with wav and mp3 at the time of this writing.

The timing of the lights turning on and off is based upon the frequency
response of the music being played.  A short segment of the music is
analyzed via FFT to get the frequency response across each defined
channel in the audio range.  Each light channel is then faded in and
out based upon the amplitude of the frequency response in the 
corresponding audio channel.  Fading is accomplished with a software 
PWM output.  Each channel can also be configured to simply turn on and
off as the frequency response in the corresponding channel crosses a 
threshold.

FFT calculation can be CPU intensive and in some cases can adversely
affect playback of songs (especially if attempting to decode the song
as well, as is the case for an mp3).  For this reason, the FFT 
calculations are cached after the first time a new song is played.
The values are cached in a gzip'd text file in the same location as the
song itself.  Subsequent requests to play the same song will use the
cached information and not recompute the FFT, thus reducing CPU
utilization dramatically and allowing for clear music playback of all
audio file types.

Recent optimizations have improved this dramatically and most users are
no longer reporting adverse playback of songs even on the first 
playback.

Sample usage:
To play an entire list -
sudo python synchronized_lights.py --playlist=/home/pi/music/.playlist

To play a specific song -
sudo python synchronized_lights.py --file=/home/pi/music/jingle_bells.mp3

Third party dependencies:

alsaaudio: for audio input/output 
    http://pyalsaaudio.sourceforge.net/

decoder.py: decoding mp3, ogg, wma, ... 
    https://pypi.python.org/pypi/decoder.py/1.5XB

numpy: for FFT calculation
    http://www.numpy.org/
"""

import ConfigParser
import argparse
import atexit
import audioop
import csv
import fcntl
import logging as log
import os
import random
import subprocess
import sys
import wave
import alsaaudio as aa
import json
import signal
import decoder
import numpy as np
import cPickle
import time
import errno
import stat

from collections import deque
import Platform
import fft
from prepostshow import PrePostShow
import RunningStats


# Make sure SYNCHRONIZED_LIGHTS_HOME environment variable is set
HOME_DIR = os.getenv("SYNCHRONIZED_LIGHTS_HOME")

if not HOME_DIR:
    print("Need to setup SYNCHRONIZED_LIGHTS_HOME environment variable, see readme")
    sys.exit()

LOG_DIR = HOME_DIR + '/logs'

# logging levels
levels = {'DEBUG': log.DEBUG,
          'INFO': log.INFO,
          'WARNING': log.WARNING,
          'ERROR': log.ERROR,
          'CRITICAL': log.CRITICAL}

stream = None
fm_process = None
streaming = None

# Arguments
parser = argparse.ArgumentParser()
parser.add_argument('--log', default='INFO',
                    help='Set the logging level. levels:INFO, DEBUG, WARNING, ERROR, CRITICAL')

filegroup = parser.add_mutually_exclusive_group()
filegroup.add_argument('--playlist', default="playlist_path",
                       help='Playlist to choose song from.')
filegroup.add_argument('--file', help='path to the song to play (required if no '
                                      'playlist is designated)')

parser.add_argument('--readcache', type=int, default=1,
                    help='read light timing from cache if available. Default: true')

log.basicConfig(filename=LOG_DIR + '/music_and_lights.play.dbg',
                format='[%(asctime)s] %(levelname)s {%(pathname)s:%(lineno)d} - %(message)s',
                level=log.INFO)

level = levels.get(parser.parse_args().log.upper())
log.getLogger().setLevel(level)

# import hardware_controller as hc
import hardware_controller as hc

# get copy of configuration manager
cm = hc.cm

parser.set_defaults(playlist=cm.lightshow.playlist_path)
args = parser.parse_args()

decay_factor = cm.lightshow.decay_factor
decay = np.zeros(cm.hardware.gpio_len, dtype='float32')

network = hc.network
server = network.networking == 'server'
client = network.networking == "client"

if cm.lightshow.use_fifo:
    if os.path.exists(cm.lightshow.fifo):
        os.remove(cm.lightshow.fifo)
    os.mkfifo(cm.lightshow.fifo, 0777)

CHUNK_SIZE = 2048  # Use a multiple of 8 (move this to config)


def end_early():
    """atexit function"""
    if server:
        network.set_playing()
        network.broadcast([0. for _ in range(hc.GPIOLEN)])
        time.sleep(1)
        network.unset_playing()

    hc.clean_up()

    if cm.audio_processing.fm:
        fm_process.kill()

    if network.network_stream:
        network.close_connection()

    if cm.lightshow.mode == 'stream-in':
        try:
            streaming.stdin.write("q")
        except:
            pass
        os.kill(streaming.pid, signal.SIGINT)
        os.unlink(cm.lightshow.fifo)


atexit.register(end_early)

# Remove traceback on Ctrl-C
signal.signal(signal.SIGINT, lambda x, y: sys.exit(0))


def update_lights(matrix, mean, std):
    """Update the state of all the lights

    Update the state of all the lights based upon the current
    frequency response matrix

    :param matrix: row of data from cache matrix
    :type matrix: list

    :param mean: standard mean of fft values
    :type mean: list

    :param std: standard deviation of fft values
    :type std: list
    """
    global decay

    brightness = matrix - mean + (std * cm.lightshow.SD_low)
    brightness = (brightness / (std * (cm.lightshow.SD_low + cm.lightshow.SD_high))) * (1.0 - (cm.lightshow.attenuate_pct / 100.0))

    # insure that the brightness levels are in the correct range
    brightness = np.clip(brightness, 0.0, 1.0)
    brightness = np.round(brightness, decimals=3)

    # calculate light decay rate if used
    if decay_factor > 0:
        decay = np.where(decay <= brightness, brightness, decay)
        brightness = np.where(decay - decay_factor > 0, decay - decay_factor, brightness)
        decay = np.where(decay - decay_factor > 0, decay - decay_factor, decay)

    # broadcast to clients if in server mode
    if server:
        network.broadcast(brightness)

    for blevel, pin in zip(brightness, range(hc.GPIOLEN)):
        hc.set_light(pin, True, blevel)


def set_audio_device(sample_rate, num_channels):
    global fm_process
    pi_version = Platform.pi_version()

    if cm.audio_processing.fm:
        srate = str(int(sample_rate / (1 if num_channels > 1 else 2)))

        fm_command = ["sudo",
                      cm.home_dir + "/bin/pifm",
                      "-",
                      cm.audio_processing.frequency,
                      srate,
                      "stereo" if num_channels > 1 else "mono"]

        if pi_version == 2:
            fm_command = ["sudo",
                          cm.home_dir + "/bin/pi_fm_rds",
                          "-audio", "-", "-freq",
                          cm.audio_processing.frequency,
                          "-srate",
                          srate,
                          "-nochan",
                          "2" if num_channels > 1 else "1"]

        log.info("Sending output as fm transmission")
        
        
        with open(os.devnull, "w") as dev_null:
            fm_process = subprocess.Popen(fm_command, stdin=subprocess.PIPE, stdout=dev_null)

        return lambda raw_data: fm_process.stdin.write(raw_data)
    elif cm.lightshow.audio_out_card is not '':
        if cm.lightshow.mode == 'stream-in':
            num_channels = 2

        output_device = aa.PCM(aa.PCM_PLAYBACK, aa.PCM_NORMAL, cm.lightshow.audio_out_card)
        output_device.setchannels(num_channels)
        output_device.setrate(sample_rate)
        output_device.setformat(aa.PCM_FORMAT_S16_LE)
        output_device.setperiodsize(CHUNK_SIZE)

        return lambda raw_data: output_device.write(raw_data)

    else:
        return lambda raw_data: None


def audio_in():
    """Control the lightshow from audio coming in from a real time audio"""
    global streaming
    stream_reader = None
    streaming = None

    sample_rate = cm.lightshow.input_sample_rate
    num_channels = cm.lightshow.input_channels

    if cm.lightshow.mode == 'audio-in':
        # Open the input stream from default input device
        streaming = aa.PCM(aa.PCM_CAPTURE, aa.PCM_NORMAL, cm.lightshow.audio_in_card)
        streaming.setchannels(num_channels)
        streaming.setformat(aa.PCM_FORMAT_S16_LE)  # Expose in config if needed
        streaming.setrate(sample_rate)
        streaming.setperiodsize(CHUNK_SIZE)

        stream_reader = lambda: streaming.read()[-1]

    elif cm.lightshow.mode == 'stream-in':

        if cm.lightshow.use_fifo:
            streaming = subprocess.Popen(cm.lightshow.stream_command_string,
                                         stdin=subprocess.PIPE,
                                         stdout=subprocess.PIPE,
                                         preexec_fn=os.setsid)
            io = os.open(cm.lightshow.fifo, os.O_RDONLY | os.O_NONBLOCK)
            stream_reader = lambda: os.read(io, CHUNK_SIZE)
        else:
            # Open the input stream from command string
            streaming = subprocess.Popen(cm.lightshow.stream_command_string,
                                         stdin=subprocess.PIPE,
                                         stdout=subprocess.PIPE,
                                         stderr=subprocess.PIPE)
            stream_reader = lambda: streaming.stdout.read(CHUNK_SIZE)

    log.debug("Running in %s mode - will run until Ctrl+C is pressed" % cm.lightshow.mode)
    print "Running in %s mode, use Ctrl+C to stop" % cm.lightshow.mode

    # setup light_delay.
    chunks_per_sec = ((16 * num_channels * sample_rate) / 8) / CHUNK_SIZE
    light_delay = int(cm.audio_processing.light_delay * chunks_per_sec)
    matrix_buffer = deque([], 1000)

    output = set_audio_device(sample_rate, num_channels)

    # Start with these as our initial guesses - will calculate a rolling mean / std 
    # as we get input data.
    mean = np.array([12.0 for _ in range(hc.GPIOLEN)], dtype='float32')
    std = np.array([1.5 for _ in range(hc.GPIOLEN)], dtype='float32')
    count = 2

    running_stats = RunningStats.Stats(hc.GPIOLEN)

    # preload running_stats to avoid errors, and give us a show that looks
    # good right from the start
    running_stats.preload(mean, std, count)

    hc.initialize()
    fft_calc = fft.FFT(CHUNK_SIZE,
                       sample_rate,
                       hc.GPIOLEN,
                       cm.audio_processing.min_frequency,
                       cm.audio_processing.max_frequency,
                       cm.audio_processing.custom_channel_mapping,
                       cm.audio_processing.custom_channel_frequencies,
                       1)

    if server:
        network.network.set_playing()

    # Listen on the audio input device until CTRL-C is pressed
    while True:
        try:
            data = stream_reader()

        except OSError as err:
            if err.errno == errno.EAGAIN or err.errno == errno.EWOULDBLOCK:
                continue
        try:
            output(data)
        except aa.ALSAAudioError:
            continue

        if len(data):
            # if the maximum of the absolute value of all samples in
            # data is below a threshold we will disregard it
            audio_max = audioop.max(data, 2)
            if audio_max < 250:
                # we will fill the matrix with zeros and turn the lights off
                matrix = np.zeros(hc.GPIOLEN, dtype="float32")
                log.debug("below threshold: '" + str(audio_max) + "', turning the lights off")
            else:
                matrix = fft_calc.calculate_levels(data)
                running_stats.push(matrix)
                mean = running_stats.mean()
                std = running_stats.std()

            matrix_buffer.appendleft(matrix)

            if len(matrix_buffer) > light_delay:
                matrix = matrix_buffer[light_delay]
                update_lights(matrix, mean, std)


def load_custom_config(config_filename):
    """
    Load custom configuration settings for file config_filename

    :param config_filename: string containing path / filename of config
    :type config_filename: str
    """

    """
    example usage
    your song
    carol-of-the-bells.mp3

    First run your playlist (or single files) to create your sync files.  This will
    create a file in the same directory as your music file.
    .carol-of-the-bells.mp3.cfg

    DO NOT EDIT THE existing section [fft], it will cause your sync files to be ignored.

    If you want to use an override you need to add the appropriate section
    The add the options you wish to use, but do not add an option you do not
    want to use, as this will set that option to None and could crash your lightshow.
    Look at defaults.cfg for exact usages of each option

    [custom_lightshow]
    always_on_channels =
    always_off_channels =
    invert_channels =
    preshow_configuration =
    preshow_script =
    postshow_configuration =
    postshow_script =
    SD_low =
    SD_high =

    [custom_audio_processing]
    min_frequency =
    max_frequency =
    custom_channel_mapping =
    custom_channel_frequencies =

    Note: DO NOT EDIT THE existing section [fft]

    Note: If you use any of the options in "custom_audio_processing" your sync files will be
          automatically regenerated after every change.  This is normal as your sync file needs
          to match these new settings.  After they have been regenerated you will see that they
          now match the settings [fft], and you will not have to regenerate then again.  Unless
          you make more changes again.

    Note: Changes made in "custom_lightshow" do not affect the sync files, so you will not need
          to regenerate them after making changes.
    """
    if os.path.isfile(config_filename):
        config = ConfigParser.RawConfigParser(allow_no_value=True)
        with open(config_filename) as f:
            config.readfp(f)

            if config.has_section('custom_lightshow'):
                lsc = "custom_lightshow"

                always_on = "always_on_channels"
                if config.has_option(lsc, always_on):
                    hc.always_on_channels = map(int, config.get(lsc, always_on).split(","))

                always_off = "always_off_channels"
                if config.has_option(lsc, always_off):
                    hc.always_off_channels = map(int, config.get(lsc, always_off).split(","))

                inverted = "invert_channels"
                if config.has_option(lsc, inverted):
                    hc.inverted_channels = map(int, config.get(lsc, inverted).split(","))

		if config.has_option(lsc, "SD_low"):
		   cm.lightshow.SD_low = config.getfloat(lsc, "SD_low")

		if config.has_option(lsc, "SD_high"):
		   cm.lightshow.SD_high = config.getfloat(lsc, "SD_high")

                # setup up custom preshow
                has_preshow_configuration = config.has_option(lsc, 'preshow_configuration')
                has_preshow_script = config.has_option(lsc, 'preshow_script')

                if has_preshow_configuration or has_preshow_script:
                    preshow = None
                    try:
                        preshow_configuration = config.get(lsc, 'preshow_configuration')
                    except ConfigParser.NoOptionError:
                        preshow_configuration = None
                    try:
                        preshow_script = config.get(lsc, 'preshow_script')
                    except ConfigParser.NoOptionError:
                        preshow_script = None

                    if preshow_configuration and not preshow_script:
                        try:
                            preshow = json.loads(preshow_configuration)
                        except (ValueError, TypeError) as error:
                            msg = "Preshow_configuration not defined or not in JSON format."
                            log.error(msg + str(error))
                    else:
                        if os.path.isfile(preshow_script):
                            preshow = preshow_script

                    cm.lightshow.preshow = preshow

                # setup postshow
                has_postshow_configuration = config.has_option(lsc, 'postshow_configuration')
                has_postshow_script = config.has_option(lsc, 'postshow_script')

                if has_postshow_configuration or has_postshow_script:
                    postshow = None
                    postshow_configuration = config.get(lsc, 'postshow_configuration')
                    postshow_script = config.get(lsc, 'postshow_script')

                    if postshow_configuration and not postshow_script:
                        try:
                            postshow = json.loads(postshow_configuration)
                        except (ValueError, TypeError) as error:
                            msg = "Postshow_configuration not defined or not in JSON format."
                            log.error(msg + str(error))
                    else:
                        if os.path.isfile(postshow_script):
                            postshow = postshow_script

                    cm.lightshow.postshow = postshow

            if config.has_section('custom_audio_processing'):
                if config.has_option('custom_audio_processing', 'min_frequency'):
                    cm.audio_processing.min_frequency = config.getfloat('custom_audio_processing',
                                                                        'min_frequency')

                if config.has_option('custom_audio_processing', 'max_frequency'):
                    cm.audio_processing.max_frequency = config.getfloat('custom_audio_processing',
                                                                        'max_frequency')

                if config.has_option('custom_audio_processing', 'custom_channel_mapping'):
                    temp = config.get('custom_audio_processing', 'custom_channel_mapping')
                    cm.audio_processing.custom_channel_mapping = map(int,
                                                                     temp.split(',')) if temp else 0

                if config.has_option('custom_audio_processing', 'custom_channel_frequencies'):
                    temp = config.get('custom_audio_processing', 'custom_channel_frequencies')
                    cm.audio_processing.custom_channel_frequencies = map(int,
                                                                         temp.split(
                                                                             ',')) if temp else 0


def setup_audio(song_filename):
    """Setup audio file

    and setup setup the output device.output is a lambda that will send data to
    fm process or to the specified ALSA sound card

    :param song_filename: path / filename to music file
    :type song_filename: str
    :return: output, fm_process, fft_calc, music_file
    :rtype tuple: lambda, subprocess, fft.FFT, decoder
    """
    # Set up audio
    force_header = False

    if any([ax for ax in [".mp4", ".m4a", ".m4b"] if ax in song_filename]):
        force_header = True

    music_file = decoder.open(song_filename, force_header)

    sample_rate = music_file.getframerate()
    num_channels = music_file.getnchannels()

    fft_calc = fft.FFT(CHUNK_SIZE,
                       sample_rate,
                       hc.GPIOLEN,
                       cm.audio_processing.min_frequency,
                       cm.audio_processing.max_frequency,
                       cm.audio_processing.custom_channel_mapping,
                       cm.audio_processing.custom_channel_frequencies)

    # setup output device
    output = set_audio_device(sample_rate, num_channels)

    chunks_per_sec = ((16 * num_channels * sample_rate) / 8) / CHUNK_SIZE
    light_delay = int(cm.audio_processing.light_delay * chunks_per_sec)

    # Output a bit about what we're about to play to the logs
    nframes = str(music_file.getnframes() / sample_rate)
    log.info("Playing: " + song_filename + " (" + nframes + " sec)")

    return output, fft_calc, music_file, light_delay


def setup_cache(cache_filename, fft_calc):
    """Setup the cache_matrix, std and mean

    loading them from a file if it exists, otherwise create empty arrays to be filled

    :param cache_filename: path / filename to cache file
    :type cache_filename: str

    :param fft_calc: instance of FFT class
    :type fft_calc: fft.FFT

    :return:  tuple of cache_found, cache_matrix, std, mean
    :type tuple: (bool, numpy.array, numpy.array, numpy.array)

    :raise IOError:
    """
    # create empty array for the cache_matrix
    cache_matrix = np.empty(shape=[0, hc.GPIOLEN])
    cache_found = False

    # The values 12 and 1.5 are good estimates for first time playing back
    # (i.e. before we have the actual mean and standard deviations
    # calculated for each channel).
    mean = np.array([12.0 for _ in range(hc.GPIOLEN)], dtype='float32')
    std = np.array([1.5 for _ in range(hc.GPIOLEN)], dtype='float32')

    if args.readcache:
        # Read in cached fft
        try:
            # load cache from file using numpy loadtxt
            cache_matrix = np.loadtxt(cache_filename)

            # compare configuration of cache file to current configuration
            cache_found = fft_calc.compare_config(cache_filename)
            if not cache_found:
                # create empty array for the cache_matrix
                cache_matrix = np.empty(shape=[0, hc.GPIOLEN])
                raise IOError()

            # get std from matrix / located at index 0
            std = np.array(cache_matrix[0])

            # get mean from matrix / located at index 1
            mean = np.array(cache_matrix[1])

            # delete mean and std from the array
            cache_matrix = np.delete(cache_matrix, 0, axis=0)
            cache_matrix = np.delete(cache_matrix, 0, axis=0)

            log.debug("std: " + str(std) + ", mean: " + str(mean))
        except IOError:
            cache_found = fft_calc.compare_config(cache_filename)
            msg = "Cached sync data song_filename not found: '"
            log.warn(msg + cache_filename + "'.  One will be generated.")

    return cache_found, cache_matrix, std, mean


def save_cache(cache_matrix, cache_filename, fft_calc):
    """
    Save matrix, std, and mean to cache_filename for use during future playback

    :param cache_matrix: numpy array containing the matrix
    :type cache_matrix: numpy.array

    :param cache_filename: name of the cache file to look for
    :type cache_filename: str

    :param fft_calc: instance of fft.FFT
    :type fft_calc: fft.FFT
    """
    # Compute the standard deviation and mean values for the cache
    mean = np.empty(hc.GPIOLEN, dtype='float32')
    std = np.empty(hc.GPIOLEN, dtype='float32')

    for i in range(0, hc.GPIOLEN):
        std[i] = np.std([item for item in cache_matrix[:, i] if item > 0])
        mean[i] = np.mean([item for item in cache_matrix[:, i] if item > 0])

    # Add mean and std to the top of the cache
    cache_matrix = np.vstack([mean, cache_matrix])
    cache_matrix = np.vstack([std, cache_matrix])

    # Save the cache using numpy savetxt
    np.savetxt(cache_filename, cache_matrix)

    # Save fft config
    fft_calc.save_config()

    cm_len = str(len(cache_matrix))
    log.info("Cached sync data written to '." + cache_filename + "' [" + cm_len + " rows]")
    log.info("Cached config data written to '." + fft_calc.config_filename)


def get_song():
    """
    Determine the next file to play

    :return: tuple containing 3 strings: song_filename, config_filename, cache_filename
    :rtype: tuple
    """
    play_now = int(cm.get_state('play_now', "0"))
    song_to_play = int(cm.get_state('song_to_play', "0"))
    song_filename = args.file

    if args.playlist is not None and args.file is None:
        most_votes = [None, None, []]

        with open(args.playlist, 'rb') as playlist_fp:
            fcntl.lockf(playlist_fp, fcntl.LOCK_SH)
            playlist = csv.reader(playlist_fp, delimiter='\t')
            songs = []

            for song in playlist:
                if len(song) < 2 or len(song) > 4:
                    log.error('Invalid playlist.  Each line should be in the form: '
                              '<song name><tab><path to song>')
                    log.warning('Removing invalid entry')
                    print "Error found in playlist"
                    print "Deleting entry:", song
                    continue
                elif len(song) == 2:
                    song.append(set())
                else:
                    song[2] = set(song[2].split(','))
                    if len(song) == 3 and len(song[2]) >= len(most_votes[2]):
                        most_votes = song
                songs.append(song)

            fcntl.lockf(playlist_fp, fcntl.LOCK_UN)

        if most_votes[0] is not None:
            log.info("Most Votes: " + str(most_votes))
            current_song = most_votes

            # Update playlist with latest votes
            with open(args.playlist, 'wb') as playlist_fp:
                fcntl.lockf(playlist_fp, fcntl.LOCK_EX)
                writer = csv.writer(playlist_fp, delimiter='\t')

                for song in songs:
                    if current_song == song and len(song) == 3:
                        song.append("playing!")

                    if len(song[2]) > 0:
                        song[2] = ",".join(song[2])
                    else:
                        del song[2]

                writer.writerows(songs)
                fcntl.lockf(playlist_fp, fcntl.LOCK_UN)
        else:
            # Get a "play now" requested song
            if 0 < play_now <= len(songs):
                current_song = songs[play_now - 1]
            # Get random song
            elif cm.lightshow.randomize_playlist:
                current_song = songs[random.randrange(0, len(songs))]
            # Play next song in the lineup
            else:
                if not (song_to_play <= len(songs) - 1):
                    song_to_play = 0

                current_song = songs[song_to_play]

                if (song_to_play + 1) <= len(songs) - 1:
                    next_song = (song_to_play + 1)
                else:
                    next_song = 0

                cm.update_state('song_to_play', str(next_song))

        # Get filename to play and store the current song playing in state cfg
        song_filename = current_song[1]
        cm.update_state('current_song', str(songs.index(current_song)))

    song_filename = song_filename.replace("$SYNCHRONIZED_LIGHTS_HOME", cm.home_dir)

    filename = os.path.abspath(song_filename)
    config_filename = os.path.dirname(filename) + "/." + os.path.basename(song_filename) + ".cfg"
    cache_filename = os.path.dirname(filename) + "/." + os.path.basename(song_filename) + ".sync"

    return song_filename, config_filename, cache_filename


def play_song():
    """Play the next song from the play list (or --file argument)."""

    # get the next song to play
    song_filename, config_filename, cache_filename = get_song()

    # load custom configuration from file
    load_custom_config(config_filename)

    # Initialize Lights
    network.set_playing()
    hc.initialize()

    # Handle the pre/post show
    play_now = int(cm.get_state('play_now', "0"))

    network.unset_playing()

    if not play_now:
        result = PrePostShow('preshow', hc).execute()

        if result == PrePostShow.play_now_interrupt:
            play_now = int(cm.get_state('play_now', "0"))

    network.set_playing()

    # Ensure play_now is reset before beginning playback
    if play_now:
        cm.update_state('play_now', "0")
        play_now = 0

    # setup audio file and output device
    output, fft_calc, music_file, light_delay = setup_audio(song_filename)

    # setup our cache_matrix, std, mean
    cache_found, cache_matrix, std, mean = setup_cache(cache_filename, fft_calc)

    matrix_buffer = deque([], 1000)

    # Process audio song_filename
    row = 0
    data = music_file.readframes(CHUNK_SIZE)

    while data != '' and not play_now:
        # output data to sound device
        output(data)

        # Control lights with cached timing values if they exist
        matrix = None
        if cache_found and args.readcache:
            if row < len(cache_matrix):
                matrix = cache_matrix[row]
            else:
                log.warning("Ran out of cached FFT values, will update the cache.")
                cache_found = False

        if matrix is None:
            # No cache - Compute FFT in this chunk, and cache results
            matrix = fft_calc.calculate_levels(data)

            # Add the matrix to the end of the cache 
            cache_matrix = np.vstack([cache_matrix, matrix])

        matrix_buffer.appendleft(matrix)

        if len(matrix_buffer) > light_delay:
            matrix = matrix_buffer[light_delay]
            update_lights(matrix, mean, std)

        # Read next chunk of data from music song_filename
        data = music_file.readframes(CHUNK_SIZE)
        row += 1

        # Load new application state in case we've been interrupted
        cm.load_state()
        play_now = int(cm.get_state('play_now', "0"))

    if not cache_found and not play_now:
        save_cache(cache_matrix, cache_filename, fft_calc)

    # Cleanup the pifm process
    if cm.audio_processing.fm:
        fm_process.kill()

    # check for postshow
    network.unset_playing()

    if not play_now:
        PrePostShow('postshow', hc).execute()

    # We're done, turn it all off and clean up things ;)
    hc.clean_up()


def network_client():
    """Network client support

    If in client mode, ignore everything else and just
    read data from the network and blink the lights
    """
    log.info("Network client mode starting")
    print "Network client mode starting..."
    print "press CTRL<C> to end"

    hc.initialize()

    print

    try:
        channels = network.channels
        channel_keys = channels.keys()

        while True:
            data = network.receive()

            if isinstance(data[0], int):
                pin = data[0]
                if pin in channel_keys:
                    hc.set_light(channels[pin], True, float(data[1]))
                continue

            elif isinstance(data[0], np.ndarray):
                blevels = data[0]

            else:
                continue

            for pin in channel_keys:
                hc.set_light(channels[pin], True, blevels[pin])

    except KeyboardInterrupt:
        log.info("CTRL<C> pressed, stopping")
        print "stopping"

        network.close_connection()
        hc.clean_up()


if __name__ == "__main__":
    # Make sure one of --playlist or --file was specified
    if args.file is None and args.playlist is None:
        print "One of --playlist or --file must be specified"
        sys.exit()

    if "-in" in cm.lightshow.mode:
        audio_in()
    elif client:
        network_client()
    else:
        play_song()
