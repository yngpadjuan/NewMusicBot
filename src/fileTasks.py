import os
import glob
from pathlib import Path
from datetime import datetime
from random import choice
from subprocess import check_call, CalledProcessError
import matchering as mg

from .paths import get_config, get_logger, TMP_DIR, WORDLISTS_DIR

log = get_logger(__name__)


class filePrep():
    # matchering loads entire song into memory; OOM will terminate without warning if this is too big
    audio_max_chunk_length_minutes = 5

    def __init__(self, file, section='DEFAULT', start=None, end=None, songName=None):
        config = get_config()
        self.location = section
        self.sessionName = config.get(self.location, 'sessionName', fallback=None)
        self.ftp_folder = config.get(self.location, 'ftpFolder')
        self.ref_file = config.get(self.location, 'refFile')
        self.tmpPath = str(TMP_DIR)
        self.start_time = start
        self.end_time = end
        self.wavPath = None
        self.mp3Path = None

        if self.sessionName:
            ts = int(os.path.getmtime(file))
            localTime = datetime.utcfromtimestamp(ts)
            date = localTime.strftime('%Y-%m-%d.%H%M%S')
            year = localTime.strftime('%Y')

            self.wavTag = f'{date} {self.sessionName}.wav'
            self.mp3Tag = f'{date} {self.sessionName}.mp3'

            self.dest_folder = config.get(self.location, 'destFolder') + year
            self.backup_folder = config.get(self.location, 'backupFolder') + year

            self.mp3Path = os.path.join(self.dest_folder, 'mp3')
            self.wavPath = os.path.join(self.dest_folder, 'wav')     

            Path(self.mp3Path).mkdir(parents=True, exist_ok=True)
            Path(self.wavPath).mkdir(parents=True, exist_ok=True)
            Path(self.backup_folder).mkdir(parents=True, exist_ok=True)
        else:
            if not songName:
                self.sessionName = self.random_name()
            else:
                self.sessionName = songName
            self.wavTag = f'{self.sessionName}.wav'
            self.mp3Tag = f'{self.sessionName}.mp3'

            self.dest_folder = config.get(self.location, 'destFolder')
            self.mp3Path = config.get(self.location, 'destFolder')
            self.backup_folder = config.get(self.location, 'backupFolder')


    def mgLogger_warning(self, text):
        log.warning(f'MG WARNING: {text}')

    def fileChunk(self):
        log.info('Chunking the large audio file.')
        segment_seconds = str(self.audio_max_chunk_length_minutes * 60)
        src = os.path.join(self.tmpPath, self.wavTag)
        try:
            check_call([
                'ffmpeg', '-y', '-i', src,
                '-v', 'quiet', '-c:a', 'copy',
                '-f', 'segment', '-segment_time', segment_seconds,
                os.path.join(self.tmpPath, 'tmp_%03d.wav'),
            ])
        except CalledProcessError as e:
            log.error(e)
            raise
        chunk_list = sorted(glob.glob(os.path.join(self.tmpPath, 'tmp_*.wav')))
        return chunk_list

    def masterAudio(self, chunk_name):
        log.info('Mastering chunk ' + chunk_name)
        tmp_out = chunk_name + '.mastered.wav'
        try:
            mg.process(target=chunk_name, reference=self.ref_file, results=[
                mg.pcm24(tmp_out),
            ])
        except Exception as e:
            log.error(e)
            if os.path.exists(tmp_out):
                os.remove(tmp_out)
            raise
        os.replace(tmp_out, chunk_name)

    def convertToMP3(self):
        config = get_config()
        artist = config.get('DEFAULT', 'artist', fallback='unknown')
        album = config.get('DEFAULT', 'album', fallback='unknown')

        log.info(f'Converting to MP3: {self.mp3Tag}')
        src = os.path.join(self.tmpPath, self.wavTag)
        dst = os.path.join(self.tmpPath, self.mp3Tag)
        cmd = ['ffmpeg', '-v', 'quiet', '-i', src]
        if self.start_time and self.end_time:
            duration_s = int(self.end_time) - int(self.start_time)
            cmd += ['-af', f'afade=t=in:st=0:d=2,afade=t=out:st={duration_s - 3}:d=3']
        cmd += [
            '-c:a', 'libmp3lame', '-q:a', '0',
            '-metadata', f'artist={artist}',
            '-metadata', f'album={album}',
            '-metadata', 'comment=Song created by NewMusicBot.',
            dst,
        ]

        try:
            check_call(cmd)
        except CalledProcessError as e:
            log.error(e)
            raise

        if not self.wavPath:
            os.remove(src)

    def mergingChunks(self, chunk_list):
        out = os.path.join(self.tmpPath, f'{self.wavTag}.tmp')
        log.info(f'Merging chunk list to {out}')
        tmp_list = os.path.join(self.tmpPath, 'tmp_file_inv.txt')
        with open(tmp_list, 'w') as fh:
            for item in chunk_list:
                fh.write(f"file '{item}'\n")
        try:
            check_call([
                'ffmpeg', '-f', 'concat', '-safe', '0', '-i', tmp_list,
                '-v', 'quiet', '-c', 'copy',
                out,
            ])
        except CalledProcessError as e:
            log.error(e)
            raise

        os.replace(out, os.path.join(self.tmpPath, self.wavTag))
        for item in chunk_list:
            os.remove(item)
        os.remove(tmp_list)

    def segmentAudio(self):
        start_s = int(self.start_time)
        duration_s = int(self.end_time) - start_s
        src = os.path.join(self.tmpPath, self.wavTag)
        trimmed = os.path.join(self.tmpPath, f'tmp_{self.sessionName}.trim.wav')
        try:
            check_call([
                'ffmpeg', '-y', '-v', 'quiet',
                '-i', src,
                '-ss', str(start_s), '-t', str(duration_s),
                '-c:a', 'copy', trimmed,
            ])
        except CalledProcessError as e:
            log.error(e)
            raise
        os.replace(trimmed, src)

    def _read_wordfile(self, path):
        with open(path) as fh:
            words = [line.strip() for line in fh if line.strip()]
        return choice(words)

    def random_name(self):
        verb = self._read_wordfile(WORDLISTS_DIR / 'verbs.txt')
        noun = self._read_wordfile(WORDLISTS_DIR / 'nouns.txt')
        return f'{verb.capitalize()} {noun.capitalize()}'
    

def process_track(filePrepObject):
    
    if filePrepObject.start_time and filePrepObject.end_time:
        filePrepObject.segmentAudio()
    
    chunkList = []
    chunkList = filePrepObject.fileChunk()
    for chunk in chunkList:
        filePrepObject.masterAudio(chunk)
    filePrepObject.mergingChunks(chunkList)

    filePrepObject.convertToMP3()
