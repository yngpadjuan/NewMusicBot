import os
import logging
import matchering as mg
from pathlib import Path
from datetime import datetime
from pydub import AudioSegment
from pydub.utils import make_chunks
from six.moves.configparser import RawConfigParser


config = RawConfigParser()
config.read(f'{os.getcwd()}/settings.conf')

numeric_level = getattr(logging, config.get('NewMusicBot','logLevel').upper(), None)
logging.basicConfig(filename='/var/log/WAVfilePrep/filePrep.log', level=numeric_level)


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

            self.dest_folder = config.get(self.location,'destFolder') + year
            self.backup_folder = config.get(self.location,'backupFolder') + year

            self.mp3Path = f'{self.dest_folder}/mp3/'
            self.wavPath = f'{self.dest_folder}/wav/'

            Path(self.mp3Path).mkdir(parents=True, exist_ok=True)
            Path(self.wavPath).mkdir(parents=True, exist_ok=True)
            Path(self.backup_folder).mkdir(parents=True, exist_ok=True)

    def mgLogger_warning(self,text):
        logging.warning(f'MG WARNING: {text}')

    def fileChunk(self,track_name):
        chunk_list = []
        tmp_file = track_name.replace(f' {self.sessionName}.wav','')
        
        audio = AudioSegment.from_file(f'{self.tmpPath}/{track_name}', "wav") 
        chunk_length_ms = 60000 * self.audio_max_chunk_length_minutes # pydub calculates in millisec
        chunks = make_chunks(audio, chunk_length_ms) #Make chunks
        
        logging.info(" Chunking the large audio file.")
        #Export all of the individual chunks as wav files
        for i, chunk in enumerate(chunks):
            chunk_name = "tmp{chunknum}_{tempname}.wav".format(chunknum=i,tempname=tmp_file)
            logging.info(" Exporting chunk " + chunk_name)
            chunk.export(f'{self.tmpPath}/{chunk_name}', format="wav")
            chunk_list.append(chunk_name)
        
        return chunk_list

    def masterAudio(self,chunk_name):
        logging.info(" Mastering chunk " + chunk_name)
        #Matchering the tracks
        mg.process(target=f'{self.tmpPath}/{chunk_name}', reference=self.ref_file, results=[
            mg.pcm24(f'{self.tmpPath}/{chunk_name}'),
            ],
        )

    def convertToMP3(self,audioFile):
        logging.info(f" Converting {audioFile} to MP3.")
        audio = AudioSegment.from_wav(f'{self.tmpPath}/{audioFile}')
        audio.export(f'{self.tmpPath}/{audioFile}', format='mp3')

    def mergingChunks(self,track_name,chunk_list):
        combined = AudioSegment.empty()
        for chunk_name in chunk_list:
            logging.info(f" Merging chunk {chunk_name}")
            combined += AudioSegment.from_file(f'{self.tmpPath}/{chunk_name}', format='mp3')
        combined.export(f'{self.tmpPath}/{track_name}', format='mp3')

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

