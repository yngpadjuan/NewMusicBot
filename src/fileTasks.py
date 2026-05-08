import os
import glob
from pathlib import Path
from datetime import datetime
from random import choice
from subprocess import run as _run, CalledProcessError
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
        chunk_pattern = os.path.join(self.tmpPath, f'tmp_{self.sessionName}_%03d.wav')
        try:
            _run([
                'ffmpeg', '-y', '-i', src,
                '-loglevel', 'error', '-c:a', 'copy',
                '-f', 'segment', '-segment_time', segment_seconds,
                chunk_pattern,
            ], capture_output=True, text=True, check=True)
        except CalledProcessError as e:
            log.error('ffmpeg fileChunk failed: %s', e.stderr)
            raise
        chunk_list = sorted(glob.glob(os.path.join(self.tmpPath, f'tmp_{self.sessionName}_*.wav')))
        return chunk_list

    def masterAudio(self, chunk_name):
        log.info('Mastering chunk ' + chunk_name)
        tmp_out = chunk_name + '.mastered.wav'
        try:
            mg.process(target=chunk_name, reference=self.ref_file, results=[
                mg.pcm24(tmp_out),
            ])
        except Exception as e:
            #log.error(e)
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
        cmd = ['ffmpeg', '-loglevel', 'error', '-i', src]
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
            _run(cmd, capture_output=True, text=True, check=True)
        except CalledProcessError as e:
            log.error('ffmpeg convertToMP3 failed: %s', e.stderr)
            raise

        if not self.wavPath:
            os.remove(src)

    def mergingChunks(self, chunk_list):
        out = os.path.join(self.tmpPath, f'tmp_{self.wavTag}')
        log.info(f'Merging chunk list to {out}')
        tmp_list = os.path.join(self.tmpPath, f'tmp_{self.sessionName}_file_inv.txt')
        with open(tmp_list, 'w') as fh:
            for item in chunk_list:
                fh.write(f"file '{item}'\n")
        try:
            _run([
                'ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', tmp_list,
                '-loglevel', 'error', '-c', 'copy',
                out,
            ], capture_output=True, text=True, check=True)
        except CalledProcessError as e:
            log.error('ffmpeg mergingChunks failed: %s', e.stderr)
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
            _run([
                'ffmpeg', '-y', '-loglevel', 'error',
                '-i', src,
                '-ss', str(start_s), '-t', str(duration_s),
                '-c:a', 'copy', trimmed,
            ], capture_output=True, text=True, check=True)
        except CalledProcessError as e:
            log.error('ffmpeg segmentAudio failed: %s', e.stderr)
            raise
        os.replace(trimmed, src)

    def cleanup(self):
        patterns = [
            f'tmp_{self.sessionName}_*.wav',
            f'tmp_{self.sessionName}.trim.wav',
            f'tmp_{self.sessionName}_file_inv.txt',
            f'{self.wavTag}.tmp',
        ]
        for pattern in patterns:
            for f in glob.glob(os.path.join(self.tmpPath, pattern)):
                try:
                    os.remove(f)
                    log.debug(f'Cleaned up: {f}')
                except OSError as e:
                    log.warning(f'Could not remove {f}: {e}')

    def _read_wordfile(self, path):
        with open(path) as fh:
            words = [line.strip() for line in fh if line.strip()]
        return choice(words)

    def random_name(self):
        verb = self._read_wordfile(WORDLISTS_DIR / 'verbs.txt')
        noun = self._read_wordfile(WORDLISTS_DIR / 'nouns.txt')
        return f'{verb.capitalize()} {noun.capitalize()}'
    

def process_track(filePrepObject):
    try:
        if filePrepObject.start_time and filePrepObject.end_time:
            filePrepObject.segmentAudio()

        chunkList = filePrepObject.fileChunk()
        for chunk in chunkList:
            filePrepObject.masterAudio(chunk)
        filePrepObject.mergingChunks(chunkList)
        filePrepObject.convertToMP3()
    finally:
        filePrepObject.cleanup()

