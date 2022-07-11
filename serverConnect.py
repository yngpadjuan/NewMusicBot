import os
import six
import ftplib
import logging
from time import sleep
from six.moves.configparser import RawConfigParser


config = RawConfigParser()
config.read(f'{os.getcwd()}/settings.conf')

numeric_level = getattr(logging, config.get('NewMusicBot','logLevel').upper(), None)
logging.basicConfig(filename='/var/log/WAVfilePrep/filePrep.log', level=numeric_level)


class serverConnect:
    def __init__(self, file, dest_folder):
        self.server_ip = ''
        self.api_key = ''
        self.username = ''
        self.ssl_verify = False

        self.file = file
        self.dest_folder = dest_folder

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

    def Upload(self):
        f_blocksize = 1024
        ftp = ftplib.FTP(f'{self.server_ip}')
        p,f = os.path.split(self.file)

        fileh = open(self.file,'rb')
        logging.info("Uploading...")
        
        response = '000-Start of Upload'
        while response[:3] != '226':
            try:
                ftp.login(f'{self.username}',f'{self.api_key}')
                #print(ftp.getwelcome())
                ftp.cwd(self.dest_folder)

                response = ftp.storbinary("STOR "+f, fileh, f_blocksize)
                logging.info(response)
            except Exception as response:
                logging.error(response)
                sleep(300)
   
        fileh.close()
        ftp.quit()
    
    def fileExists(self):
        ftp = ftplib.FTP(f'{self.server_ip}')
        p,f = os.path.split(self.file)
        ftp.login(f'{self.username}',f'{self.api_key}')

        filelist = []
        ftp.cwd(self.dest_folder)
        ftp.retrlines('LIST',filelist.append)

        for file in filelist:
            logging.debug(f)
            if f in file:
                return True
        
        return False