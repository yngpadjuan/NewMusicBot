import os
import sys
import shutil
import random
import logging
from pathlib import Path
from subprocess import call
from six.moves.configparser import RawConfigParser

from fileTasks import filePrep
from serverConnect import serverConnect

config = RawConfigParser()
config.read(f'{os.getcwd()}/settings.conf')

numeric_level = getattr(logging, config.get('NewMusicBot','logLevel').upper(), None)
logging.basicConfig(filename='/var/log/WAVfilePrep/filePrep.log', level=numeric_level)


def discordMessage(message,channel_id):
    try:
        os.environ['MESSAGE'] = message
        os.environ['CHANNEL'] = str(channel_id)
        call(['python3','/home/pi/Music/BoxMusic/DiscordMusicAlert.py'])
    except Exception as e:
        logging.error(e)

def read_wordfile(wordfile):
    words = []

    wlf = os.path.expanduser(wordfile)
    wlf = open(wordfile)

    for word in wlf:
        thisword = word.strip()
        words.append(thisword)

    wlf.close()    
    word = random.choice(words)

    return word

def random_name():
    vf = r'/home/pi/Music/BoxMusic/wordlists/verbs.txt'
    nf = r'/home/pi/Music/BoxMusic/wordlists/nouns.txt'

    verb = read_wordfile(vf)
    noun = read_wordfile(nf)

    name = f'{verb.capitalize()} {noun.capitalize()}'
    return name


def main(argv):
    file = argv[0]
    start = argv[1]
    end = argv[2]
    if argv[3]:
        songName = argv[3]

    audiof = filePrep()

    dest_loc = config.get('music','destFolder')
    backup_loc = config.get('music','backupFolder')
    ftp_dest = config.get('music','ftpfolder')

    Path(dest_loc).mkdir(parents=True, exist_ok=True)
    Path(backup_loc).mkdir(parents=True, exist_ok=True)

    if not songName:
        songName = random_name()
    
    if not Path(f"{dest_loc}/{songName}.mp3").exists():
        chunk_list = []
        try:
            chunk_list = audiof.segmentAudio(songName,file,start,end)
            for chunk in chunk_list:
                audiof.masterAudio(chunk)
                audiof.convertToMP3(chunk)
            audiof.mergingChunks(songName,chunk_list)
            audiof.applyFade(songName)
        except Exception as e:
            logging.error(e)
            msg = (f'Oops...something went wrong MASTERING {songName}.')
            discordMessage(msg,958901182351417354)
        else:
            shutil.move(f"{audiof.tmpPath}/{songName}.mp3", dest_loc)

        #clean up tmp files
        for tmpfile in chunk_list:
                os.remove(os.path.join(audiof.tmpPath,tmpfile))
    else:
        logging.info(f"{songName}.mp3 already exists. Skipping to upload.")

    s = serverConnect(f'{os.path.join(dest_loc,songName)}.mp3',ftp_dest)
    if not s.fileExists():
        try: 
            s.Upload()
        except Exception as e:
            logging.warning(e)
            msg = (f'Oops...something went wrong UPLOADING {songName}.')
            discordMessage(msg,958901182351417354)
        else:
            msg = (f'Oh Snap! @everyone New music!\n {songName.replace(".mp3","")}\n was just uploaded.')
            discordMessage(msg,565726777138479104)
    else:
        msg = (f'Oops... {songName} already exists. Not continuing.')
        discordMessage(msg,958901182351417354)

    if not Path(f"{backup_loc}/{songName}.mp3").exists():
        try:
            shutil.copy(f'{dest_loc}/{songName}.mp3',backup_loc)
        except Exception as e:
            msg = (f'Oops...something went wrong COPYING {songName} to {backup_loc}.')
            raise msg
    else:
        logging.info(f"{songName}.mp3 backup already exists.")


if __name__ == "__main__":
    main(sys.argv[1:])