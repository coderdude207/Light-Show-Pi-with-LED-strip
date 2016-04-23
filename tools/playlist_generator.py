#
# Playlist generator for LightshowPi
# Author: Eric Higdon (mrbassman.10@gmail.com)
#
# How To:
#   cd to the location of the playlist script (i.e. "lightshowpi/tools/generatePlaylist")
#   run "python generatePlaylist.py"
#   Enter the path to the folder of songs which you desire a playlist for then press <enter> (i.e. "/home/pi/lightshowpi/music/sample")
#   Playlist file will be created in the folder 
#       Paths are absolute. Include the whole path to the songs folder. (i.e. "/home/pi/lightshowpi/music/christmas")

#
# Updated: Tom Enos
# added support to pull title from metadata if it exists
# added support for multiply file types
#

import mutagen
import os
import sys

entries = list()
file_types = [".wav",
              ".mp1", ".mp2", ".mp3", ".mp4", ".m4a", ".m4b",
              ".ogg",
              ".flac",
              ".oga",
              ".wma", ".wmv",
              ".aif"]

make_title = lambda s: s.replace("_", " ").replace(ext, "") + "\t"

location = raw_input("Enter the full path to the folder of songs:")

if not os.path.exists(location):
    print "Path does not exists"
    sys.exit(1)

print "Generating Playlist"

os.chdir(location)

for song in os.listdir(os.getcwd()):
    entry = ""
    title = ""
    ext = os.path.splitext(song)[1]
    
    if ext in file_types:
        metadata = mutagen.File(song, easy=True)

        if not metadata is None:
            if "title" in metadata:
                title = metadata["title"][0] + "\t"
            else:
                title = make_title(song)
        else:
            title = make_title(song)
        

        entry = title + os.path.join(os.getcwd(), song)
        entries.append(entry)
        print entry
              
print "Writing Playlist to File"
 
with open(".playlist", "w") as playlist:
    playlist.write("\n".join(str(entry) for entry in entries))
    
print "DONE"
