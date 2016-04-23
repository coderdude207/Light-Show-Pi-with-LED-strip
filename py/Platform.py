# Copyright (c) 2014 Adafruit Industries
# Author: Tony DiCola

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import platform
import re

# Platform identification constants.
UNKNOWN = 0
RASPBERRY_PI = 1
BEAGLEBONE_BLACK = 2
MINNOWBOARD = 3


def platform_detect():
    """Detect if running on the Raspberry Pi or Beaglebone Black and return the
    platform type.  Will return RASPBERRY_PI, BEAGLEBONE_BLACK, or UNKNOWN."""
    # Handle Raspberry Pi
    pi = pi_version()
    if pi is not None:
        return RASPBERRY_PI

    # Handle Beaglebone Black
    # TODO: Check the Beaglebone Black /proc/cpuinfo value instead of reading
    # the platform.
    plat = platform.platform()
    if plat.lower().find('armv7l-with-debian') > -1:
        return BEAGLEBONE_BLACK
    elif plat.lower().find('armv7l-with-ubuntu') > -1:
        return BEAGLEBONE_BLACK
    elif plat.lower().find('armv7l-with-glibc2.4') > -1:
        return BEAGLEBONE_BLACK

    # Handle Minnowboard
    # Assumption is that mraa is installed
    try:
        import mraa

        if mraa.getPlatformName() == 'MinnowBoard MAX':
            return MINNOWBOARD
    except ImportError:
        pass

    # Couldn't figure out the platform, just return unknown.
    return UNKNOWN


def pi_revision():
    """Detect the revision number of a Raspberry Pi, useful for changing
    functionality like default I2C bus based on revision."""
    # Revision list available at: http://elinux.org/RPi_HardwareHistory#Board_Revision_History
    with open('/proc/cpuinfo', 'r') as infile:
        for line in infile:
            # Match a line of the form "Revision : 0002" while ignoring extra
            # info in front of the revsion (like 1000 when the Pi was over-volted).
            match = re.match('Revision\s+:\s+.*(\w{4})$', line, flags=re.IGNORECASE)
            if match and match.group(1) in ['0000', '0002', '0003']:
                # Return revision 1 if revision ends with 0000, 0002 or 0003.
                return 1
            elif match:
                # Assume revision 2 if revision ends with any other 4 chars.
                return 2
        # Couldn't find the revision, throw an exception.
        raise RuntimeError('Could not determine Raspberry Pi revision.')


def pi_version():
    """Detect the version of the Raspberry Pi.  Returns either 1, 2 or
    None depending on if it's a Raspberry Pi 1 (model A, B, A+, B+),
    Raspberry Pi 2 (model B+), or not a Raspberry Pi.
    """
    # Check /proc/cpuinfo for the Hardware field value.
    # 2708 is pi 1
    # 2709 is pi 2
    # Anything else is not a pi.
    with open('/proc/cpuinfo', 'r') as infile:
        cpuinfo = infile.read()
    # Match a line like 'Hardware   : BCM2709'
    match = re.search('^Hardware\s+:\s+(\w+)$', cpuinfo,
                      flags=re.MULTILINE | re.IGNORECASE)
    if not match:
        # Couldn't find the hardware, assume it isn't a pi.
        return None
    if match.group(1) == 'BCM2708':
        # Pi 1
        return 1
    elif match.group(1) == 'BCM2709':
        # Pi 2
        return 2
    else:
        # Something else, not a pi.
        return None


header40 = """A+, B+ and Pi2 B, and Zero models
                         +=========+
         POWER  3.3VDC   | 1 . . 2 |  5.0VDC   POWER
      I2C SDA1  GPIO  8  | 3 . . 4 |  5.0VDC   POWER
      I2C SCL1  GPIO  9  | 5 . . 6 |  GROUND
      CPCLK0    GPIO  7  | 7 . . 8 |  GPIO 15  TxD UART
                GROUND   | 9 . . 10|  GPIO 16  RxD UART
                GPIO  0  |11 . . 12|  GPIO  1  PCM_CLK/PWM0
                GPIO  2  |13 . . 14|  GROUND
                GPIO  3  |15 . . 16|  GPIO  4
         POWER  3.3VDC   |17 . . 18|  GPIO  5
      SPI MOSI  GPIO 12  |19 .   20|  GROUND
      SPI MISO  GPIO 13  |21 . . 22|  GPIO  6
      SPI SCLK  GPIO 14  |23 . . 24|  GPIO 10  CE0 SPI
                GROUND   |25 . . 26|  GPIO 11  CE1 SPI
 I2C ID EEPROM  SDA0     |27 . . 28|  SCL0     I2C ID EEPROM
        GPCLK1  GPIO 21  |29 . . 30|  GROUND
        CPCLK2  GPIO 22  |31 . . 32|  GPIO 26  PWM0
          PWM1  GPIO 23  |33 . . 34|  GROUND
   PCM_FS/PWM1  GPIO 24  |35 . . 36|  GPIO 27
                GPIO 25  |37 . . 38|  GPIO 28  PCM_DIN
                GROUND   |39 . . 40|  GPIO 29  PCM_DOUT
                         +=========+"""

header26 = """A and B models
                         +=========+
         POWER  3.3VDC   | 1 . . 2 |  5.0VDC   POWER
      I2C SDA0  GPIO  8  | 3 . . 4 |  DNC  
      I2C SCL0  GPIO  9  | 5 . . 6 |  GROUND
                GPIO  7  | 7 . . 8 |  GPIO 15  TxD UART
                DNC      | 9 . . 10|  GPIO 16  RxD UART
                GPIO  0  |11 . . 12|  GPIO  1  PCM_CLK/PWM0
                GPIO  2  |13 . . 14|  DNC
                GPIO  3  |15 . . 16|  GPIO  4
                DNC      |17 . . 18|  GPIO  5
      SPI MOSI  GPIO 12  |19 .   20|  DNC
      SPI MISO  GPIO 13  |21 . . 22|  GPIO  6
      SPI SCLK  GPIO 14  |23 . . 24|  GPIO 10  CE0 SPI
                DNC      |25 . . 26|  GPIO 11  CE1 SPI
                         +=========+"""


def get_model():
    with open('/proc/cmdline', 'r') as f:
        line = f.readline()
        m = re.search('bcm2708.boardrev=(0x[0123456789abcdef]*) ', line)
        model = m.group(1)[-2:].lower()
    
    if model in ["07", "08", "09"]:
        return "Model A", header26
    
    elif model in ["02", "03", "04", "05", "06", "0d", "0e", "0f"]:
        return "Model B", header26
    
    elif model in ["12", "15"]:
        return "Model A+", header40
    
    elif model in ["10", "13"]:
        return "Model B+", header40
    
    elif model in ["11"]:
        return "Compute Module", "Custom"
    
    elif model in ["41"]:
        return "Pi 2 Model B", header40
    
    elif model in ["92"]:
        return "Pi Zero", header40
    
    raise RuntimeError('Could not determine Raspberry Pi model.')    
