An Edited version of lightshowpi for rgb led strip the original version available on [http://lightshowpi.org/](http://lightshowpi.org/)
The edited installation available on 

[http://suffcingbowl7.github.io/](http://suffcingbowl7.github.io/)

All files here are free to use under the BSD License (see the LICENSE file for details).  All we
ask in return is that you send any updates / improvements you may make to them back to us so 
that we can all benefit from your improvements!

Join on the original community on Their [Google+ community page](https://plus.google.com/communities/101789596301454731630) and / or [Facebook page](https://www.facebook.com/lightshowpi) as well to share your experiences using lightshowPi, as well as videos of your shows!

Thanks to Todd Giles for this this awesome thing.
Thanks and enjoy :-)
Himanshu Gore

Installation / Getting Started
==============================

Please visit the [Getting Started Page](http://suffcingbowl7.github.io) for details on getting
started.  Or for those who want to just jump on in, feel free to run the install.sh script and go 
for it :-)

Directory Structure
===================

* bin/* - Various bash scripts / tools to aid in playing songs, controlling volume, etc...
* config/* - Configuration files.
* crontab/synchronized_lights - Add these via 'sudo crontab -e' to start / stop the lightshow automatically
* logs/* - Log files will be output here.
* music/* - Music files go here (includes some samples to get you started).
* py/* - All the python code.
* tools/* - Various tools helpful in configuring / using / etc... LightshowPi

Contributors
============

A huge thanks to all those that have contributed to the Lightshow Pi codebase:

* Todd Giles
* Chris Usey
* Ryan Jennings
* Sean Millar
* Scott Driscoll
* Micah Wedemeyer
* Chase Cromwell
* Bruce Goheen
* Paul Dunn
* Stephen Burning
* Eric Higdon
* Tom Enos

Release Notes
============

2014/11/27 :: Version 1.1
-------------------------------

* piFM support (thanks to Stephen Burning)
* audio-in support (thanks to Paul Dunn)
* command line play-list generator (thanks to Eric Higdon)
* enhancements to preshow configuration, including per-channel control  (thanks to Chris Usey)
* support for expansion cards, including mcp23s17,mcp23017 (thanks to Chris Usey)
* updated to support RPi B+ (thanks to Chris Usey)
* clarification on comments and in-code documentation (thanks to Bruce Goheen, Chase Cromwell, and Micah Wedemeyer)
* other misc bug fixes (see Issues list for more details)

2014/02/16 :: Version 1
-------------------------------

* First "stable" release
