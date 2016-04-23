#
# Licensed under the BSD license.  See full license in LICENSE file.
# http://www.lightshowpi.com/
#
# Author: Todd Giles (todd@lightshowpi.com)
# Author: Tom Enos (tomslick.ca@gmail.com)

"""FFT methods for computing / analyzing frequency response of audio.

This is simply a wrapper around rpi-audio-level by Colin Guyon.
https://github.com/colin-guyon/rpi-audio-levels

Initial FFT code inspired from the code posted here:
http://www.raspberrypi.org/phpBB3/viewtopic.php?t=35838&p=454041

Optimizations from work by Scott Driscoll:
http://www.instructables.com/id/Raspberry-Pi-Spectrum-Analyzer-with-RGB-LED-Strip-/

Third party dependencies:

numpy: for array support - http://www.numpy.org/
rpi-audio-levels - https://bitbucket.org/tom_slick/rpi-audio-levels (modified for lightshowpi)
"""

import ConfigParser
import logging
import os.path
from numpy import *
import math

from rpi_audio_levels import AudioLevels


class FFT(object):
    def __init__(self,
                 chunk_size,
                 sample_rate,
                 num_bins,
                 min_frequency,
                 max_frequency,
                 custom_channel_mapping,
                 custom_channel_frequencies,
                 input_channels=2):
        """
        :param chunk_size: chunk size of audio data
        :type chunk_size: int

        :param sample_rate: audio file sample rate
        :type sample_rate: int

        :param num_bins: length of gpio to process
        :type num_bins: int

        :param input_channels: number of audio input channels to process for (default=2)
        :type input_channels: int

        :param min_frequency: lowest frequency for which a channel will be activated
        :type min_frequency: float

        :param max_frequency: max frequency for which a channel will be activated.
        :type max_frequency: float

        :param custom_channel_mapping: custom map of channels to different frequencies
        :type custom_channel_mapping: list | int

        :param custom_channel_frequencies: custom list of frequencies that should be
                                        utilized for each channel
        :type custom_channel_frequencies: list | int

        """

        self.chunk_size = chunk_size
        self.sample_rate = sample_rate
        self.num_bins = num_bins
        self.input_channels = input_channels
        self.window = hanning(0)
        self.min_frequency = min_frequency
        self.max_frequency = max_frequency
        self.custom_channel_mapping = custom_channel_mapping
        self.custom_channel_frequencies = custom_channel_frequencies
        self.frequency_limits = self.calculate_channel_frequency()
        self.config = ConfigParser.RawConfigParser(allow_no_value=True)
        self.config_filename = ""
        self.audio_levels = AudioLevels(math.log(chunk_size / 2, 2), num_bins)

        fl = array(self.frequency_limits)
        self.piff = ((fl * self.chunk_size) / self.sample_rate).astype(int)

        for a in range(len(self.piff)):
            if self.piff[a][0] == self.piff[a][1]:
                self.piff[a][1] += 1
        self.piff = self.piff.tolist()
        
    def calculate_levels(self, data):
        """Calculate frequency response for each channel defined in frequency_limits

        :param data: decoder.frames(), audio data for fft calculations
        :type data: decoder.frames

        :return:
        :rtype: numpy.array
        """
        # create a numpy array, taking just the left channel if stereo
        data_stereo = frombuffer(data, dtype="int16")

        if self.input_channels == 2:
            # data has 2 bytes per channel
            # pull out the even values, just using left channel
            data = array(data_stereo[::2])
        elif self.input_channels == 1:
            data = data_stereo

        # if you take an FFT of a chunk of audio, the edges will look like
        # super high frequency cutoffs. Applying a window tapers the edges
        # of each end of the chunk down to zero.
        if len(data) != len(self.window):
            self.window = hanning(len(data)).astype(float32)

        data = data * self.window

        # if all zeros in data then there is no need to do the fft 
        if all(data == 0.0):
            return zeros(self.num_bins, dtype="float32")

        # Apply FFT - real data
        # Calculate the power spectrum
        cache_matrix = array(self.audio_levels.compute(data, self.piff)[0])
        cache_matrix[isinf(cache_matrix)] = 0.0

        return cache_matrix

    def calculate_channel_frequency(self):
        """Calculate frequency values

        Calculate frequency values for each channel,
        taking into account custom settings.

        :return: frequency values for each channel
        :rtype: list
        """

        # How many channels do we need to calculate the frequency for
        if self.custom_channel_mapping != 0 and len(self.custom_channel_mapping) == self.num_bins:
            logging.debug("Custom Channel Mapping is being used: %s",
                          str(self.custom_channel_mapping))
            channel_length = max(self.custom_channel_mapping)
        else:
            logging.debug("Normal Channel Mapping is being used.")
            channel_length = self.num_bins

        logging.debug("Calculating frequencies for %d channels.", channel_length)
        octaves = (log(self.max_frequency / self.min_frequency)) / log(2)
        logging.debug("octaves in selected frequency range ... %s", octaves)
        octaves_per_channel = octaves / channel_length
        frequency_limits = []
        frequency_store = []

        frequency_limits.append(self.min_frequency)

        if self.custom_channel_frequencies != 0 and (
                len(self.custom_channel_frequencies) >= channel_length + 1):
            logging.debug("Custom channel frequencies are being used")
            frequency_limits = self.custom_channel_frequencies
        else:
            logging.debug("Custom channel frequencies are not being used")
            for pin in range(1, self.num_bins + 1):
                frequency_limits.append(frequency_limits[-1]
                                        * 10 ** (3 / (10 * (1 / octaves_per_channel))))
        for pin in range(0, channel_length):
            frequency_store.append((frequency_limits[pin], frequency_limits[pin + 1]))
            logging.debug("channel %d is %6.2f to %6.2f ", pin, frequency_limits[pin],
                          frequency_limits[pin + 1])

        # we have the frequencies now lets map them if custom mapping is defined
        if self.custom_channel_mapping != 0 and len(self.custom_channel_mapping) == self.num_bins:
            frequency_map = []

            for pin in range(0, self.num_bins):
                mapped_channel = self.custom_channel_mapping[pin] - 1
                mapped_frequency_set = frequency_store[mapped_channel]
                mapped_frequency_set_low = mapped_frequency_set[0]
                mapped_frequency_set_high = mapped_frequency_set[1]
                logging.debug("mapped channel: " + str(mapped_channel) + " will hold LOW: "
                              + str(mapped_frequency_set_low) + " HIGH: "
                              + str(mapped_frequency_set_high))
                frequency_map.append(mapped_frequency_set)

            return frequency_map
        else:
            return frequency_store

    def compare_config(self, cache_filename):
        """
        Compare the current configuration used to generate fft to a saved
        copy of the data that was used to generate the fft data for an
        existing cache file
        
        :param cache_filename: path and name of cache file
        :type cache_filename: str
        """
        self.config_filename = cache_filename.replace(".sync", ".cfg")

        if not os.path.isfile(self.config_filename):
            logging.warn("No cached config data found")
            return False
        else:
            has_config = True
            with open(self.config_filename) as f:
                self.config.readfp(f)

        fft_cache = dict()
        fft_current = dict()

        try:
            fft_cache["chunk_size"] = self.config.getint("fft", "chunk_size")
            fft_cache["sample_rate"] = self.config.getint("fft", "sample_rate")
            fft_cache["num_bins"] = self.config.getint("fft", "num_bins")
            fft_cache["min_frequency"] = self.config.getfloat("fft", "min_frequency")
            fft_cache["max_frequency"] = self.config.getfloat("fft", "max_frequency")

            temp = [int(channel) for channel in
                    self.config.get("fft", "custom_channel_mapping").split(',')]
            if len(temp) == 1:
                fft_cache["custom_channel_mapping"] = temp[0]
            else:
                fft_cache["custom_channel_mapping"] = temp

            temp = [int(channel) for channel in
                    self.config.get("fft", "custom_channel_frequencies").split(',')]
            if len(temp) == 1:
                fft_cache["custom_channel_frequencies"] = temp[0]
            else:
                fft_cache["custom_channel_frequencies"] = temp

            fft_cache["input_channels"] = self.config.getint("fft", "input_channels")
        except ConfigParser.Error:
            has_config = False

        fft_current["chunk_size"] = self.chunk_size
        fft_current["sample_rate"] = self.sample_rate
        fft_current["num_bins"] = self.num_bins
        fft_current["min_frequency"] = self.min_frequency
        fft_current["max_frequency"] = self.max_frequency
        fft_current["custom_channel_mapping"] = self.custom_channel_mapping
        fft_current["custom_channel_frequencies"] = self.custom_channel_frequencies
        fft_current["input_channels"] = self.input_channels

        if fft_cache != fft_current:
            has_config = False
            logging.warn("Cached config data does not match")

        if has_config:
            self.audio_levels = None
            
        return has_config

    def save_config(self):
        """Save the current configuration used to generate the fft data"""
        if self.config.has_section("fft"):
            self.config.remove_section("fft")

        self.config.add_section("fft")
        self.config.set('fft', '# DO NOT EDIT THIS SECTION')
        self.config.set('fft', '# EDITING THIS SECTION WILL CAUSE YOUR SYNC FILE TO BE INVALID')

        self.config.set('fft', 'chunk_size', str(self.chunk_size))
        self.config.set('fft', 'sample_rate', str(self.sample_rate))
        self.config.set('fft', 'num_bins', str(self.num_bins))
        self.config.set('fft', 'min_frequency', str(self.min_frequency))
        self.config.set('fft', 'max_frequency', str(self.max_frequency))

        if isinstance(self.custom_channel_mapping, list):
            self.config.set('fft', 'custom_channel_mapping', str(self.custom_channel_mapping)[1:-1])
        else:
            self.config.set('fft', 'custom_channel_mapping', str(self.custom_channel_mapping))

        if isinstance(self.custom_channel_frequencies, list):
            self.config.set('fft', 'custom_channel_frequencies',
                            str(self.custom_channel_frequencies)[1:-1])
        else:
            self.config.set('fft', 'custom_channel_frequencies',
                            str(self.custom_channel_frequencies))

        self.config.set('fft', 'input_channels', str(self.input_channels))

        with open(self.config_filename, "w") as f:
            self.config.write(f)
