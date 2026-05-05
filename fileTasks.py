import os
#import sys
import glob
import logging
import matchering as mg
from pathlib import Path
from datetime import datetime
from subprocess import check_call, CalledProcessError
from pydub import AudioSegment
from pydub.utils import make_chunks
from six.moves.configparser import RawConfigParser


config = RawConfigParser()
config.read(f'{os.getcwd()}/settings.conf')

numeric_level = getattr(logging, config.get('NewMusicBot','logLevel').upper(), None)
logging.basicConfig(format='%(asctime)s %(levelname)-8s %(message)s',
                    filename='/var/log/WAVfilePrep/filePrep.log', level=numeric_level,
                    datefmt='%Y-%m-%d %H:%M:%S')


class filePrep():
    audio_max_chunk_length_minutes = 5    #ffmpeg is a C++ library; OOM will terminate without warning if this is too big

    location = config.get('NewMusicBot','location')

    src_folder = config.get(location,'srcFolder')
    sessionName = config.get(location,'sessionName')

    ftp_folder = config.get(location,'ftpFolder')
    ref_file = config.get(location,'refFile')

    tmpPath = r'/home/pi/Music/BoxMusic/tmp'

    def __init__(self,file=None):
        if file:
            unixTime = os.path.getmtime(f'{file}')
            ts = int(unixTime)
            localTime = datetime.utcfromtimestamp(ts)
            date = localTime.strftime('%Y-%m-%d.%H%M%S')
            year = localTime.strftime('%Y')

            self.wavTag = (f'{date} {self.sessionName}.wav')
            self.mp3Tag = (f'{date} {self.sessionName}.mp3')
            self.tmp_master_track = 'tmp_master_track.wav'

            self.dest_folder = config.get(self.location,'destFolder') + year
            self.backup_folder = config.get(self.location,'backupFolder') + year

            self.mp3Path = f'{self.dest_folder}/mp3/'
            self.wavPath = f'{self.dest_folder}/wav/'

            #if os.path.exists(self.dest_folder):
            Path(self.mp3Path).mkdir(parents=True, exist_ok=True)
            Path(self.wavPath).mkdir(parents=True, exist_ok=True)
            Path(self.backup_folder).mkdir(parents=True, exist_ok=True)


    def mgLogger_warning(self,text):
        logging.warning(f'MG WARNING: {text}')

    def fileChunk(self):
        logging.info(" Chunking the large audio file.")
        chunk_list = []
        tmp_file_naming = 'tmp_*.wav'
        #tmp_file = track_name.replace(f' {self.sessionName}.wav','')

        try:
            check_call(['ffmpeg','-y','-i', os.path.join(self.tmpPath,self.wavTag),'-v','quiet', 
                        '-c:a', 'copy', '-f', 'segment', '-segment_time', '300', os.path.join(self.tmpPath,'tmp_%03d.wav')])
        except CalledProcessError as e:
            logging.error(e)
            raise
        else:
            search_pattern = os.path.join(self.tmpPath, tmp_file_naming)
            chunk_list = glob.glob(search_pattern)
            #chunk_list = [os.path.basename(x) for x in chunk_list]

            chunk_list.sort()
            return chunk_list


    def masterAudio(self, chunk_name):
        logging.info(" Mastering chunk " + chunk_name)
        tmp_out = chunk_name + '.mastered.wav'
        try:
            mg.process(target=chunk_name, reference=self.ref_file, results=[
                mg.pcm24(tmp_out),
            ])
        except Exception as e:
            logging.error(e)
            if os.path.exists(tmp_out):
                os.remove(tmp_out)
            raise
        os.replace(tmp_out, chunk_name)

    def convertToMP3(self):
        logging.info(f" Converting {self.wavTag} to MP3.")
        try:
            check_call(['ffmpeg', '-v','quiet','-i', os.path.join(self.tmpPath,self.tmp_master_track), '-c:a', 
                        'libmp3lame', '-q:a', '0', os.path.join(self.tmpPath,self.mp3Tag)])
        except CalledProcessError as e:
            logging.error(e)
            raise
        else:
            os.remove(os.path.join(self.tmpPath,self.tmp_master_track))


    def mergingChunks(self,chunk_list):
        logging.info(f" Merging chunk list to {self.wavTag}")
        tmp_list = os.path.join(self.tmpPath,"tmp_file_inv.txt")

        with open(tmp_list, 'w') as file:
            for item in chunk_list:
                file.write(f"file '{item}'\n")

        try:
            check_call(['ffmpeg', '-f', 'concat', '-safe', '0', '-i', tmp_list, 
                        '-v','quiet', '-c', 'copy', os.path.join(self.tmpPath,self.tmp_master_track)])
        except CalledProcessError as e:
            logging.error(e)
            raise
        else:
            os.remove(os.path.join(self.tmpPath,"tmp_file_inv.txt"))
            for item in chunk_list:
                os.remove(item)


    def applyFade(self,track_name):
        combined = AudioSegment.empty()
        combined += AudioSegment.from_file(f'{self.tmpPath}/{track_name}', format='mp3')

        logging.info(f' Applying audio fade: {track_name}')
        combined = combined.fade_in(2000).fade_out(3000)
        combined.export(f'{self.tmpPath}/{track_name}.mp3', format='mp3', tags={'artist':'BoX','album':'WiP','comments':'Song created by NewMusicBot.'})

    def segmentAudio(self, song_name, file, start, end):
        start = int(start)*1000
        end = int(end)*1000

        chunk_size = 60000 * self.audio_max_chunk_length_minutes
        chunk_list = []

        audio = AudioSegment.from_file(file)[start:end]
        chunks = make_chunks(audio, chunk_size)

        for i, chunk in enumerate(chunks):
            chunk_name = "tmp{chunknum}_{tempname}.wav".format(chunknum=i,tempname=song_name)
            chunk.export(f'{self.tmpPath}/{chunk_name}', format="wav")
            chunk_list.append(chunk_name)

        return chunk_list

