#!/usr/bin/env python
#
# Licensed under the BSD license.  See full license in LICENSE file.
# http://www.lightshowpi.com/
#
# Author: Tom Enos
#

"""Compute a running mean and standard deviation

Receives an numpy array of fft data from lightshowpi and computes a
running mean and standard deviation for each element in the array

derived from the work of John D. Cook
http://www.johndcook.com/blog/standard_deviation/

Third party dependencies:

numpy: for calculation
    http://www.numpy.org/
"""
import numpy


class Stats(object):
    def __init__(self, length):
        """Constructor
        
        :param length: the length of the matrix
        :type length: int
        """
        self.length = length
        self.empty = numpy.zeros(length, dtype='float32')
        self.clear()
        self.sample_count = 0
        self.old_mean = self.empty
        self.old_std = self.empty
        self.new_mean = self.empty
        self.new_std = self.empty

    def clear(self):
        self.sample_count = 0
        self.old_mean = self.empty
        self.old_std = self.empty
        self.new_mean = self.empty
        self.new_std = self.empty

    def preload(self, mean, std, sample_count=2):
        """Add a starting samples to the running standard deviation and mean
        
        This data does not need to be accurate.  It is only a base starting
        point for our light show.  With out preloading some values the show 
        will start with all lights on and then slowly change to what we want
        to see.  
        
        :param mean: new sample mean starting point
        :type mean: numpy array
        :param std: new sample standard deviation starting point
        :type std: numpy array
        :param sample_count: how many samples to start with (min 2)
        :type sample_count: int
        """
        if len(mean) == self.length and len(
                std) == self.length and sample_count > 1 and self.sample_count == 0:
            # cast all arrays to numpy just to make sure the data type is correct
            self.new_mean = numpy.array(mean, dtype='float32')
            self.new_std = numpy.array(std, dtype='float32')
            self.old_mean = numpy.array(mean, dtype='float32')
            self.old_std = numpy.array(std, dtype='float32')
            self.sample_count = sample_count

    def push(self, data):
        """Add a new sample to the running standard deviation and mean

        data should be numpy array the same length as self.length
        :param data: new sample data, this must be a numpy array 
        :type data: numpy array
        """
        self.sample_count += 1

        if self.sample_count == 1:
            self.old_mean = self.new_mean
            self.new_mean = data
            self.old_std = self.empty
        else:
            self.new_mean = self.old_mean + (data - self.old_mean) / self.sample_count
            self.new_std = self.old_std + (data - self.old_mean) * (data - self.new_mean)

            # set up for next iteration
            self.old_mean = self.new_mean
            self.old_std = self.new_std

    def num_data_values(self):
        """Get the current number of observations in the sample
        
        :return: current samples observed
        :rtype: int
        """
        return self.sample_count

    def mean(self):
        """Get the current mean
        
        :return: current sampled mean
        :rtype: numpy array
        """
        return self.new_mean

    def variance(self):
        """Get the current variance 
        
        :return: current variance
        :rtype: numpy array
        """
        if self.sample_count > 1:
            return self.new_std / (self.sample_count - 1.0)
        else:
            return self.empty

    def std(self):
        """Get the current standard deviation 
        
        :return: current standard deviation
        :rtype: numpy array
        """
        return numpy.sqrt(self.variance())
