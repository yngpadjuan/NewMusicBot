import os
import six
import ftplib
import logging
import threading
from six.moves.configparser import RawConfigParser


config = RawConfigParser()
config.read(f'{os.getcwd()}/settings.conf')

numeric_level = getattr(logging, config.get('NewMusicBot','logLevel').upper(), None)
logging.basicConfig(format='%(asctime)s %(levelname)-8s %(message)s',
                    filename='/var/log/WAVfilePrep/filePrep.log', level=numeric_level,
                    datefmt='%Y-%m-%d %H:%M:%S')


class serverConnect:
    def __init__(self, file, dest_folder):
        self.server_ip = ''
        self.api_key = ''
        self.username = ''
        self.ssl_verify = False

        self.file = file
        self.dest_folder = dest_folder
        self.f_blocksize = 8192
        self.total_size = os.path.getsize(file)
        self.size_written = 0
        self._size_lock = threading.Lock()

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
        
        def handle(block):
            with self._size_lock:
                self.size_written = self.size_written + self.f_blocksize if self.size_written + self.f_blocksize < self.total_size else self.total_size
        
        def background():
            try:
                ftp.login(f'{self.username}',f'{self.api_key}')
                ftp.cwd(self.dest_folder)
            except Exception as e:
                logging.error(e)

            p,f = os.path.split(self.file)
            
            if self.size_written:
                self.size_written = ftp.size(f)
                logging.info("Upload restarting...")
            else:
                logging.info("Uploading...")

            try:
                with open(self.file,'rb') as fileh:
                    fileh.seek(self.size_written)                    
                    response = ftp.storbinary("STOR "+f, fileh, callback=handle,
                                               blocksize=self.f_blocksize, rest=self.size_written)        
                logging.info(response)
            except Exception as e:
                logging.error(e)            
            else:
                quit = ftp.quit()
                logging.info(quit)
            finally:
                ftp.close()
        
        try:
            ftp = ftplib.FTP(f'{self.server_ip}')
        except Exception as e:
            logging.error(f'Unable to connect to server. {e}')
            return False

        percent_complete = 0
        t = threading.Thread(target=background)
        t.start()
        while t.is_alive():
            t.join(120)
            
            with self._size_lock:
                size_snapshot = self.size_written
            if size_snapshot:
                percent_complete = size_snapshot / self.total_size
                logging.info(("{:.1%} percent complete").format(percent_complete))

                if percent_complete == 1:
                    ftp.close()
                    return True

        if percent_complete == 1:
            return True

        return False
           
           
    def fileExists(self):
        ftp = ftplib.FTP(f'{self.server_ip}')
        p,f = os.path.split(self.file)
        ftp.login(f'{self.username}',f'{self.api_key}')
        ftp.cwd(self.dest_folder)

        filelist = []
        ftp.retrlines('LIST',filelist.append)

        for file in filelist:
            logging.debug(f)
            if f in file:
                if os.path.getsize(self.file) == ftp.size(f):
                    return True
        
        return False

    def deleteFile(self):
        ftp = ftplib.FTP(f'{self.server_ip}')
        ftp.login(f'{self.username}',f'{self.api_key}')
        ftp.cwd(self.dest_folder)

        p,f = os.path.split(self.file)

        ftp.delete(f)