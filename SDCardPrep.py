import os
import sys
import shutil
import logging
import filecmp
import psutil
#from time import sleep
import time
from subprocess import call, check_call, CalledProcessError
#from datetime import datetime
from six.moves.configparser import RawConfigParser

from fileTasks import filePrep
from serverConnect import serverConnect

config = RawConfigParser()
config.read(f'{os.getcwd()}/settings.conf')

numeric_level = getattr(logging, config.get('NewMusicBot','logLevel').upper(), None)
logging.basicConfig(format='%(asctime)s %(levelname)-8s %(message)s',
                    filename='/var/log/WAVfilePrep/filePrep.log', level=numeric_level,
                    datefmt='%Y-%m-%d %H:%M:%S')


def discordMessage(message, channel_id):
    try:
        call(['python3', '/home/pi/Music/BoxMusic/DiscordMusicAlert.py', str(channel_id), message])
    except Exception as e:
        logging.error(e)


def main(argv):
    file = argv[0]
    audiof = filePrep(file)

    if not os.path.exists(audiof.dest_folder):
        discordMessage('Failed to mount music disk! Exiting.',958901182351417354)
        sys.exit(1)
    
    if not os.path.exists(audiof.backup_folder):
        discordMessage('Failed to mount backup disk! Exiting.',958901182351417354)
        sys.exit(1)
        
    if not os.path.isfile(os.path.join(audiof.mp3Path,audiof.mp3Tag)):
        chunkList = []
        msg = (f'Started the filePrep process on: {audiof.wavTag}')
        discordMessage(msg,958901182351417354)

        if os.path.isfile(os.path.join(audiof.tmpPath,audiof.wavTag)):
            logging.info(f"{os.path.join(audiof.tmpPath,audiof.wavTag)} exists. Checking fidelity.")           
            if not filecmp.cmp(file, os.path.join(audiof.tmpPath,audiof.wavTag)):
                try:
                    logging.info(f"Copying {file} to {audiof.tmpPath}")
                    shutil.copy(file, os.path.join(audiof.tmpPath,audiof.wavTag))
                    logging.info(f"Copied Successfully!")
                except Exception as e:
                    logging.error(e)
                    msg = (f'Something went wrong COPYING {e}.')
                    discordMessage(msg,958901182351417354)
            else:
                logging.info(f"{file} already copied from SD Card. Moving on.")
        else:
            try:
                logging.info(f"Copying {file} to {audiof.tmpPath}")
                shutil.copy(file, os.path.join(audiof.tmpPath,audiof.wavTag))
                logging.info(f"Copied Successfully!")
            except Exception as e:
                logging.error(e)
                msg = (f'Something went wrong COPYING {e}.')
                discordMessage(msg,958901182351417354)
        
        #master the file
        try:
            chunkList = audiof.fileChunk()                
            for chunk in chunkList:
                audiof.masterAudio(chunk)
                #audiof.convertToMP3(chunk)
            audiof.mergingChunks(chunkList)
            audiof.convertToMP3()
        except Exception as e:
            logging.error(e)
            msg = (f'Oops...something went wrong MASTERING {audiof.wavTag}.')
            discordMessage(msg,958901182351417354)              
            raise

        #move the files to the music disk        
        try:
            shutil.move(os.path.join(audiof.tmpPath,audiof.wavTag), audiof.wavPath)
            shutil.move(os.path.join(audiof.tmpPath,audiof.mp3Tag), audiof.mp3Path)
        except Exception as e:
            logging.error(e)

    else:
        logging.info(f"{audiof.mp3Tag} already exists. Skipping to file upload to server.")
    
    if logging.root.level <= 10:
        msg = (f'Uploading {audiof.mp3Tag} now.')
        discordMessage(msg,958901182351417354)

    #upload file to website
    s = serverConnect(os.path.join(audiof.mp3Path,audiof.mp3Tag),audiof.ftp_folder)
    if s.fileExists():
        logging.info(f"{audiof.mp3Tag} is already uploaded to the site. Skipping upload.")
    else:
        max_retries = 5
        for attempt in range(1, max_retries + 1):
            if s.Upload():
                break
            if attempt == max_retries:
                msg = f'Upload failed after {max_retries} attempts: {audiof.mp3Tag}. Giving up.'
                logging.error(msg)
                discordMessage(msg, 958901182351417354)
                raise RuntimeError(msg)
            wait = 2 ** attempt
            logging.warning(f'Upload attempt {attempt} failed for {audiof.mp3Tag}. Retrying in {wait}s...')
            time.sleep(wait)

        msg = (f'Oh Snap! New music @everyone!\n {audiof.mp3Tag.replace(".mp3","")}\n was just uploaded.')
        discordMessage(msg,565726777138479104)


    if not os.path.isfile(os.path.join(audiof.backup_folder,audiof.mp3Tag)):
        #send MP3 files to backup Disk
        try:
            logging.info("Backing up file.")                        
            shutil.copy(os.path.join(audiof.mp3Path,audiof.mp3Tag), audiof.backup_folder)  
        except Exception as e:
            logging.error(e)
            msg = (f'Oops...something went wrong BACKING UP {audiof.mp3Tag}.')
            discordMessage(msg,958901182351417354)
            raise
        else:
            try:
                os.remove(file)
            except Exception as e:
                logging.error(e)
                msg = (f'Oops...unable to delete source {file}.')
                discordMessage(msg,958901182351417354)
    else:
        logging.info(f"{audiof.mp3Tag} is already backed up.")
                          
    #date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    msg = f'COMPLETED filePrep on {file}'
    logging.info(msg)
    if logging.root.level <= 10:
        discordMessage(msg,958901182351417354)  

if __name__ == "__main__":
    main(sys.argv[1:])