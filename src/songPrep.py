import os
import sys
import shutil
import random
from pathlib import Path
from subprocess import run as sp_run

from .fileTasks import filePrep
from .serverConnect import serverConnect
from .paths import get_config, get_logger, ALERT_CHANNEL_ID, PUBLISH_CHANNEL_ID, HOME, WORDLISTS_DIR

log = get_logger(__name__)
_ALERT_MODULE = 'src.DiscordMusicAlert'


def discordMessage(message, channel_id):
    try:
        sp_run([sys.executable, '-m', _ALERT_MODULE, str(channel_id), message], check=False, cwd=str(HOME))
    except Exception as e:
        log.error(e)


def _read_wordfile(path):
    with open(path) as fh:
        words = [line.strip() for line in fh if line.strip()]
    return random.choice(words)


def random_name():
    verb = _read_wordfile(WORDLISTS_DIR / 'verbs.txt')
    noun = _read_wordfile(WORDLISTS_DIR / 'nouns.txt')
    return f'{verb.capitalize()} {noun.capitalize()}'


def main(argv):
    file = argv[0]
    start = argv[1]
    end = argv[2]
    songName = argv[3]

    config = get_config()
    audiof = filePrep()

    dest_loc = config.get('music', 'destFolder')
    backup_loc = config.get('music', 'backupFolder')
    ftp_dest = config.get('music', 'ftpFolder')

    if not os.path.exists(dest_loc):
        discordMessage('Failed to mount music disk! Exiting.', ALERT_CHANNEL_ID)
        sys.exit(1)

    Path(dest_loc).mkdir(parents=True, exist_ok=True)
    Path(backup_loc).mkdir(parents=True, exist_ok=True)

    if songName == 'None':
        songName = random_name()

    if not Path(f'{dest_loc}/{songName}.mp3').exists():
        chunk_list = []
        try:
            chunk_list = audiof.segmentAudio(songName, file, start, end)
            for chunk in chunk_list:
                audiof.masterAudio(os.path.join(audiof.tmpPath, chunk))
            audiof.mergingChunks(
                [os.path.join(audiof.tmpPath, c) for c in chunk_list],
                out_name=audiof.tmp_master_track,
            )
            audiof.convertToMP3(out_name=f'{songName}.mp3')
            audiof.applyFade(f'{songName}.mp3')
        except Exception as e:
            log.error(e)
            discordMessage(f'Oops...something went wrong MASTERING {songName}.', ALERT_CHANNEL_ID)
            raise
        else:
            shutil.move(f'{audiof.tmpPath}/{songName}.mp3', dest_loc)

        for tmpfile in chunk_list:
            tmp_path = os.path.join(audiof.tmpPath, tmpfile)
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
    else:
        log.info(f'{songName}.mp3 already exists. Skipping to upload.')

    s = serverConnect(f'{os.path.join(dest_loc, songName)}.mp3', ftp_dest)
    if not s.fileExists():
        try:
            s.Upload()
        except Exception as e:
            log.warning(e)
            discordMessage(f'Oops...something went wrong UPLOADING {songName}.', ALERT_CHANNEL_ID)
            s.deleteFile()
            raise
        else:
            discordMessage(
                f'@everyone BoX has released a new song!\nCheck out {songName}!',
                PUBLISH_CHANNEL_ID,
            )
    else:
        discordMessage(f'Oops... {songName} already exists. Not continuing.', ALERT_CHANNEL_ID)

    if not Path(f'{backup_loc}/{songName}.mp3').exists():
        try:
            shutil.copy(f'{dest_loc}/{songName}.mp3', backup_loc)
        except Exception:
            msg = f'Oops...something went wrong BACKING UP {songName} to {backup_loc}.'
            log.error(msg)
            raise
    else:
        log.info(f'{songName}.mp3 backup already exists.')


if __name__ == '__main__':
    main(sys.argv[1:])
