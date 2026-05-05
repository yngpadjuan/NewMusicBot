import os
import sys
import shutil
import filecmp
import time
from subprocess import run as sp_run

from .fileTasks import filePrep
from .serverConnect import serverConnect
from .paths import get_config, get_logger, ALERT_CHANNEL_ID, PUBLISH_CHANNEL_ID, HOME

log = get_logger(__name__)
_ALERT_MODULE = str(HOME / 'src' / 'DiscordMusicAlert.py')


def discordMessage(message, channel_id):
    try:
        sp_run([sys.executable, _ALERT_MODULE, str(channel_id), message], check=False)
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
                log.info(f'{file} already copied from SD Card. Moving on.')
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

        try:
            shutil.move(os.path.join(audiof.tmpPath, audiof.wavTag), audiof.wavPath)
            shutil.move(os.path.join(audiof.tmpPath, audiof.mp3Tag), audiof.mp3Path)
        except Exception as e:
            log.error(e)

    else:
        log.info(f'{audiof.mp3Tag} already exists. Skipping to file upload to server.')

    log.info(f'Uploading {audiof.mp3Tag} now.')

    s = serverConnect(os.path.join(audiof.mp3Path, audiof.mp3Tag), audiof.ftp_folder)
    if s.fileExists():
        log.info(f'{audiof.mp3Tag} is already uploaded to the site. Skipping upload.')
    else:
        max_retries = 5
        for attempt in range(1, max_retries + 1):
            if s.Upload():
                break
            if attempt == max_retries:
                msg = f'Upload failed after {max_retries} attempts: {audiof.mp3Tag}. Giving up.'
                log.error(msg)
                discordMessage(msg, ALERT_CHANNEL_ID)
                raise RuntimeError(msg)
            wait = 2 ** attempt
            log.warning(f'Upload attempt {attempt} failed for {audiof.mp3Tag}. Retrying in {wait}s...')
            time.sleep(wait)

        discordMessage(
            f'Oh Snap! New music @everyone!\n {audiof.mp3Tag.replace(".mp3", "")}\n was just uploaded.',
            PUBLISH_CHANNEL_ID,
        )

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

    msg = f'COMPLETED filePrep on {file}'
    log.info(msg)


if __name__ == '__main__':
    main(sys.argv[1:])
