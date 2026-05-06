import os
import sys
import shutil
import filecmp
from subprocess import run as sp_run
from datetime import datetime

from .fileTasks import filePrep
from .serverConnect import serverConnect
from .paths import get_logger, ALERT_CHANNEL_ID, PUBLISH_CHANNEL_ID, HOME

log = get_logger(__name__)
_ALERT_MODULE = 'src.DiscordMusicAlert'


def discordMessage(message, channel_id):
    try:
        sp_run([sys.executable, '-m', _ALERT_MODULE, str(channel_id), message], check=False, cwd=str(HOME))
    except Exception as e:
        log.error(e)


def main(argv):
    file = argv[0]
    audiof = filePrep(file)

    if not os.path.exists(audiof.dest_folder):
        discordMessage('Failed to mount music disk! Exiting.', ALERT_CHANNEL_ID)
        sys.exit(1)
    if not os.path.exists(audiof.backup_folder):
        discordMessage('Failed to mount backup disk! Exiting.', ALERT_CHANNEL_ID)
        sys.exit(1)

    if not os.path.isfile(os.path.join(audiof.mp3Path, audiof.mp3Tag)):
        chunkList = []
        discordMessage(f'Started the filePrep process on: {audiof.wavTag}', ALERT_CHANNEL_ID)

        tmp_copy = os.path.join(audiof.tmpPath, audiof.wavTag)
        if os.path.isfile(tmp_copy):
            log.info(f'{tmp_copy} exists. Checking fidelity.')
            if not filecmp.cmp(file, tmp_copy):
                try:
                    log.info(f'Copying {file} to {audiof.tmpPath}')
                    shutil.copy(file, tmp_copy)
                    log.info('Copied successfully.')
                except Exception as e:
                    log.error(e)
                    discordMessage(f'Something went wrong COPYING {e}.', ALERT_CHANNEL_ID)
            else:
                log.info(f'{file} already copied. Moving on.')
        else:
            try:
                log.info(f'Copying {file} to {audiof.tmpPath}')
                shutil.copy(file, tmp_copy)
                log.info('Copied successfully.')
            except Exception as e:
                log.error(e)
                discordMessage(f'Something went wrong COPYING {e}.', ALERT_CHANNEL_ID)

        try:
            chunkList = audiof.fileChunk()
            for chunk in chunkList:
                audiof.masterAudio(chunk)
            audiof.mergingChunks(chunkList)
            audiof.convertToMP3()
        except Exception as e:
            log.error(e)
            discordMessage(f'Oops...something went wrong MASTERING {audiof.wavTag}.', ALERT_CHANNEL_ID)
            raise
        else:
            shutil.move(os.path.join(audiof.tmpPath, audiof.wavTag), audiof.wavPath)
            shutil.move(os.path.join(audiof.tmpPath, audiof.mp3Tag), audiof.mp3Path)
            log.info(f'Uploading {audiof.mp3Tag} now.')

    else:
        log.info(f'{audiof.mp3Tag} already exists. Skipping to file upload to server.')

    s = serverConnect(os.path.join(audiof.mp3Path, audiof.mp3Tag), audiof.ftp_folder)
    if not s.fileExists():
        try:
            s.Upload()
        except Exception as e:
            log.warning(e)
            discordMessage(f'Oops...something went wrong UPLOADING {audiof.mp3Tag}.', ALERT_CHANNEL_ID)
            s.deleteFile()
            raise
        else:
            discordMessage(
                f'Oh Snap! @everyone New music!\n {audiof.mp3Tag.replace(".mp3", "")}\n was just uploaded.',
                PUBLISH_CHANNEL_ID,
            )
    else:
        log.info(f'{audiof.mp3Tag} is already uploaded to the site. Skipping upload.')

    if not os.path.isfile(os.path.join(audiof.backup_folder, audiof.mp3Tag)):
        try:
            log.info('Backing up file.')
            shutil.copy(os.path.join(audiof.mp3Path, audiof.mp3Tag), audiof.backup_folder)
        except Exception as e:
            log.error(e)
            discordMessage(f'Oops...something went wrong BACKING UP {audiof.mp3Tag}.', ALERT_CHANNEL_ID)
            raise
        else:
            try:
                os.remove(file)
            except Exception as e:
                log.error(e)
                discordMessage(f'Oops...unable to delete source {file}.', ALERT_CHANNEL_ID)
    else:
        log.info(f'{audiof.mp3Tag} is already backed up.')

    date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log.info(f'Completed filePrep on {file}: {date}')


if __name__ == '__main__':
    main(sys.argv[1:])
