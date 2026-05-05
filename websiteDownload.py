from six.moves.configparser import RawConfigParser
import ftplib
import os
import six
from pathlib import Path

local_destination = '/home/pi/Music/BoxMusic/MusicFiles/website'

config = RawConfigParser()
config.read(f'{os.getcwd()}/settings.conf')

class connect():
    def __init__(self):
        self.server_ip = ''
        self.api_key = ''
        self.username = ''
        self.ssl_verify = False

        default_profile = {
            "server_ip": None,
            "api_key": None,
            "username": None,
            "ssl_verify": False
        }

        credential_search_path = [
            os.path.join(os.path.sep, "etc","BoxMusic","server.credentials"),
            os.path.join(os.path.expanduser("~"), "BoxMusic", "server.credentials"),
            os.path.join(".", "BoxMusic","server.credentials"),
        ]

        credentials = RawConfigParser(defaults=default_profile)
        credentials.read(credential_search_path)

        for k, v in six.iteritems(default_profile):
            self.server_ip = credentials.get("default","ip")
            self.username = credentials.get("default","user")
            self.api_key = credentials.get("default","key")
            self.ssl_verify = credentials.get("default","ssl_verify")

    def listFiles(self, folder='/'):
        ftp = ftplib.FTP(f'{self.server_ip}')
        ftp.login(f'{self.username}',f'{self.api_key}')

        filelist = []
        try:
            ftp.cwd(folder)
        except Exception as e:
            if 'Not a directory' in str(e):
                print('')
            else:
                raise
        else:
            ftp.retrlines('NLST',filelist.append)
        
        return filelist
    
    def download(self, folder, files):
        ftp = ftplib.FTP(f'{self.server_ip}')
        ftp.login(f'{self.username}',f'{self.api_key}')

        for file in files:
            local_dest = os.path.join(local_destination, folder)
            Path(local_dest).mkdir(parents=True, exist_ok=True)

            local_filename = os.path.join(local_dest, filename)
            remote_file = os.path.join(folder, file)

            # Open a local file for writing (binary mode)...
            # The 'with' statement ensures that the file will be closed 
            with open(local_filename, 'wb') as f:
                # Define the callback as a closure so it can access the opened 
                # file in local scope
                def callback(data):
                    f.write(data)
                print(f'Downloading...{remote_file}')
                ftp.retrbinary('RETR %s' % remote_file, callback)        
     

exclusions = ['.','..','.ftpquota']

server = connect()
home_folder = server.listFiles('/story')
for folder in home_folder:
    if folder not in exclusions:
        server.download('/story', folder)
        contents = server.listFiles('/story'+folder)
        print(folder, contents)
        for content in contents:
            if content not in exclusions:
                server.download('/story/'+folder, content)
                c = server.listFiles(folder + '/' + content)
                print(folder + '/' + content, c)
                for con in c:
                    if con not in exclusions:
                        server.download('/story/'+folder, con)

        
        