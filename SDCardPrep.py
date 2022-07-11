import os
import sys
import shutil
import logging
from subprocess import call
from datetime import datetime
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


def main(argv):
    file = argv[0]
    audiof = filePrep(file)
    
    if not os.path.isfile(os.path.join(audiof.mp3Path,audiof.mp3Tag)):
        chunkList = []
        msg = (f'Started the filePrep process on: {audiof.wavTag}')
        discordMessage(msg,958901182351417354)
            
        logging.info(f"Copying {file} to {audiof.tmpPath}")
        shutil.copy(file, os.path.join(audiof.tmpPath,audiof.wavTag))
        
        #master the file
        try:
            chunkList = audiof.fileChunk(audiof.wavTag)                
            for chunk in chunkList:
                audiof.masterAudio(chunk)
                audiof.convertToMP3(chunk)
            audiof.mergingChunks(audiof.mp3Tag, chunkList)
        except Exception as e:
            logging.error(e)
            msg = (f'Oops...something went wrong MASTERING {audiof.wavTag}.')
            discordMessage(msg,958901182351417354)              
            sys.exit()
        else:
            shutil.move(os.path.join(audiof.tmpPath,audiof.wavTag), audiof.wavPath)
            shutil.move(os.path.join(audiof.tmpPath,audiof.mp3Tag), audiof.mp3Path)
            if logging.root.level <= 10:
                msg = (f'Uploading {audiof.mp3Tag} now.')
                discordMessage(msg,958901182351417354)
        
        for tmpfile in chunkList:
            os.remove(os.path.join(audiof.tmpPath,tmpfile))

    else:
        logging.info(f"{audiof.mp3Tag} already exists. Skipping to file upload to server.")


    #upload file to website
    s = serverConnect(os.path.join(audiof.mp3Path,audiof.mp3Tag),audiof.ftp_folder)
    if not s.fileExists():
        try: 
            s.Upload()
        except Exception as e:
            logging.warning(e)
            msg = (f'Oops...something went wrong UPLOADING {audiof.mp3Tag}.')
            discordMessage(msg,958901182351417354)
        else:
            msg = (f'Oh Snap! @everyone New music!\n {audiof.mp3Tag.replace(".mp3","")}\n was just uploaded.')
            discordMessage(msg,565726777138479104)
    else:
        logging.info(f"{audiof.mp3Tag} is already uploaded to the site. Skipping upload.")


    if not os.path.isfile(os.path.join(audiof.backup_folder,audiof.mp3Tag)):
        #send MP3 files to backup Disk
        try:
            logging.info("Backing up file.")                        
            shutil.copy(os.path.join(audiof.mp3Path,audiof.mp3Tag), audiof.backup_folder)  
        except Exception as e:
            logging.error(e)
            msg = (f'Oops...something went wrong COPYING {audiof.mp3Tag}.')
            discordMessage(msg,958901182351417354)
        else:
            try:
                os.remove(file)
            except Exception as e:
                logging.error(e)
                msg = (f'Oops...unable to delete source {file}.')
                discordMessage(msg,958901182351417354)
    else:
        logging.info(f"{audiof.mp3Tag} is already backed up.")
                          
    date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    msg = f'Completed filePrep on {file}: {date}'
    logging.info(msg)
    if logging.root.level <= 10:
        discordMessage(msg,958901182351417354)  

if __name__ == "__main__":
    main(sys.argv[1:])