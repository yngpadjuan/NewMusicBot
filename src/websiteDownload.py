import os
import ftplib
from pathlib import Path

from .paths import get_config, get_logger
from .credentials import load as load_credentials

log = get_logger(__name__)

config = get_config()
local_destination = config.get('NewMusicBot', 'localDestination', fallback='')


class connect():
    def __init__(self):
        creds = load_credentials()
        self.server_ip = creds['server_ip']
        self.username = creds['username']
        self.api_key = creds['api_key']

    def listFiles(self, folder='/'):
        filelist = []
        with ftplib.FTP(self.server_ip) as ftp:
            ftp.login(self.username, self.api_key)
            try:
                ftp.cwd(folder)
            except Exception as e:
                if 'Not a directory' in str(e):
                    return filelist
                raise
            ftp.retrlines('NLST', filelist.append)
        return filelist

    def download(self, folder, file):
        local_dest = os.path.join(local_destination, folder)
        Path(local_dest).mkdir(parents=True, exist_ok=True)
        local_filename = os.path.join(local_dest, file)
        remote_file = os.path.join(folder, file)
        with ftplib.FTP(self.server_ip) as ftp:
            ftp.login(self.username, self.api_key)
            with open(local_filename, 'wb') as f:
                log.info(f'Downloading...{remote_file}')
                ftp.retrbinary('RETR %s' % remote_file, f.write)


exclusions = ['.', '..', '.ftpquota']

server = connect()
home_folder = server.listFiles('/story')
for folder in home_folder:
    if folder not in exclusions:
        server.download('/story', folder)
        contents = server.listFiles('/story' + folder)
        log.info(f'{folder}: {contents}')
        for content in contents:
            if content not in exclusions:
                server.download('/story/' + folder, content)
                c = server.listFiles(folder + '/' + content)
                log.info(f'{folder}/{content}: {c}')
                for con in c:
                    if con not in exclusions:
                        server.download('/story/' + folder, con)
