#!/usr/bin/env python
#
# Licensed under the BSD license.  See full license in LICENSE file.
# http://www.lightshowpi.com/
#
# Author: Todd Giles (todd@lightshowpi.com)
"""Trivial wrapper around alsaaduio.cards() for getting a list of your audio cards.

Helpful in determining the list of USB audio cards in advanced audio-in setups.
https://bitbucket.org/togiles/lightshowpi/wiki/Audio-In%20Mode

Sample usage:
python audio_in_cards.py
"""

import alsaaudio as aa

if __name__ == "__main__":
    print aa.cards()
