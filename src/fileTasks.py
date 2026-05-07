import os
import glob
from pathlib import Path
from datetime import datetime
from subprocess import check_call, CalledProcessError
from pydub import AudioSegment
import matchering as mg

from .paths import get_config, get_logger, TMP_DIR

log = get_logger(__name__)


class filePrep():
    # ffmpeg is a C++ library; OOM will terminate without warning if this is too big
    audio_max_chunk_length_minutes = 5

    def __init__(self, file=None):
        config = get_config()
        self.location = config.get('NewMusicBot', 'location')
        self.src_folder = config.get(self.location, 'srcFolder')
        self.sessionName = config.get(self.location, 'sessionName')
        self.ftp_folder = config.get(self.location, 'ftpFolder')
        self.ref_file = config.get(self.location, 'refFile')
        self.tmpPath = str(TMP_DIR)
        self.tmp_master_track = 'tmp_master_track.wav'

        if file:
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

    def mgLogger_warning(self, text):
        log.warning(f'MG WARNING: {text}')

    def fileChunk(self):
        log.info('Chunking the large audio file.')
        segment_seconds = str(self.audio_max_chunk_length_minutes * 60)
        try:
            check_call([
                'ffmpeg', '-y', '-i', os.path.join(self.tmpPath, self.wavTag),
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

    def convertToMP3(self, out_name=None):
        mp3_name = out_name or self.mp3Tag
        log.info(f'Converting to MP3: {mp3_name}')
        src = os.path.join(self.tmpPath, self.tmp_master_track)
        dst = os.path.join(self.tmpPath, mp3_name)
        try:
            check_call([
                'ffmpeg', '-v', 'quiet', '-i', src,
                '-c:a', 'libmp3lame', '-q:a', '0', dst,
            ])
        except CalledProcessError as e:
            log.error(e)
            raise
        os.remove(src)

    def mergingChunks(self, chunk_list, out_name=None):
        out = out_name or self.tmp_master_track
        log.info(f'Merging chunk list to {out}')
        tmp_list = os.path.join(self.tmpPath, 'tmp_file_inv.txt')
        with open(tmp_list, 'w') as fh:
            for item in chunk_list:
                fh.write(f"file '{item}'\n")
        try:
            check_call([
                'ffmpeg', '-f', 'concat', '-safe', '0', '-i', tmp_list,
                '-v', 'quiet', '-c', 'copy',
                os.path.join(self.tmpPath, out),
            ])
        except CalledProcessError as e:
            log.error(e)
            raise
        os.remove(tmp_list)
        for item in chunk_list:
            os.remove(item)

    def applyFade(self, track_name):
        config = get_config()
        artist = config.get('NewMusicBot', 'artist', fallback='NewMusicBot')
        album = config.get('NewMusicBot', 'album', fallback='WiP')
        path = os.path.join(self.tmpPath, track_name)
        log.info(f'Applying audio fade: {track_name}')
        combined = AudioSegment.from_file(path, format='mp3')
        combined = combined.fade_in(2000).fade_out(3000)
        combined.export(
            path, format='mp3',
            tags={'artist': artist, 'album': album, 'comments': 'Song created by NewMusicBot.'},
        )

    def segmentAudio(self, song_name, file, start, end):
        start_s = int(start)
        duration_s = int(end) - start_s
        segment_s = self.audio_max_chunk_length_minutes * 60
        trimmed = os.path.join(self.tmpPath, f'tmp_trim_{song_name}.wav')
        try:
            check_call([
                'ffmpeg', '-y', '-v', 'quiet',
                '-i', file,
                '-ss', str(start_s), '-t', str(duration_s),
                '-c:a', 'copy', trimmed,
            ])
            check_call([
                'ffmpeg', '-y', '-v', 'quiet',
                '-i', trimmed,
                '-c:a', 'copy',
                '-f', 'segment', '-segment_time', str(segment_s),
                os.path.join(self.tmpPath, f'tmp_%03d_{song_name}.wav'),
            ])
        except CalledProcessError as e:
            log.error(e)
            raise
        finally:
            if os.path.exists(trimmed):
                os.remove(trimmed)
        chunk_list = sorted(glob.glob(os.path.join(self.tmpPath, f'tmp_*_{song_name}.wav')))
        return [os.path.basename(c) for c in chunk_list]
