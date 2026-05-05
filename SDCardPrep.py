import os
import sys
import shutil
import logging
import filecmp
import time
from subprocess import call
from configparser import RawConfigParser

from fileTasks import filePrep
from serverConnect import serverConnect

config = RawConfigParser()
config.read(f'{os.getcwd()}/settings.conf')

ALERT_CHANNEL_ID = config.getint('NewMusicBot', 'alertChannelId')
PUBLISH_CHANNEL_ID = config.getint('NewMusicBot', 'publishChannelId')

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
        discordMessage('Failed to mount music disk! Exiting.',ALERT_CHANNEL_ID)
        sys.exit(1)
    
    if not os.path.exists(audiof.backup_folder):
        discordMessage('Failed to mount backup disk! Exiting.',ALERT_CHANNEL_ID)
        sys.exit(1)
        
    if not os.path.isfile(os.path.join(audiof.mp3Path,audiof.mp3Tag)):
        chunkList = []
        msg = (f'Started the filePrep process on: {audiof.wavTag}')
        discordMessage(msg,ALERT_CHANNEL_ID)

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
                    discordMessage(msg,ALERT_CHANNEL_ID)
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
                discordMessage(msg,ALERT_CHANNEL_ID)
        
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
            discordMessage(msg,ALERT_CHANNEL_ID)              
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
        discordMessage(msg,ALERT_CHANNEL_ID)

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
                discordMessage(msg, ALERT_CHANNEL_ID)
                raise RuntimeError(msg)
            wait = 2 ** attempt
            logging.warning(f'Upload attempt {attempt} failed for {audiof.mp3Tag}. Retrying in {wait}s...')
            time.sleep(wait)

        msg = (f'Oh Snap! New music @everyone!\n {audiof.mp3Tag.replace(".mp3","")}\n was just uploaded.')
        discordMessage(msg,PUBLISH_CHANNEL_ID)


    if not os.path.isfile(os.path.join(audiof.backup_folder,audiof.mp3Tag)):
        #send MP3 files to backup Disk
        try:
            logging.info("Backing up file.")                        
            shutil.copy(os.path.join(audiof.mp3Path,audiof.mp3Tag), audiof.backup_folder)  
        except Exception as e:
            logging.error(e)
            msg = (f'Oops...something went wrong BACKING UP {audiof.mp3Tag}.')
            discordMessage(msg,ALERT_CHANNEL_ID)
            raise
        else:
            try:
                os.remove(file)
            except Exception as e:
                logging.error(e)
                msg = (f'Oops...unable to delete source {file}.')
                discordMessage(msg,ALERT_CHANNEL_ID)
    else:
        logging.info(f"{audiof.mp3Tag} is already backed up.")
                          
    #date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    msg = f'COMPLETED filePrep on {file}'
    logging.info(msg)
    if logging.root.level <= 10:
        discordMessage(msg,ALERT_CHANNEL_ID)  

if __name__ == "__main__":
    main(sys.argv[1:])