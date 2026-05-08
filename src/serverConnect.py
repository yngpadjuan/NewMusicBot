import os
import ftplib
import threading
from .paths import get_logger
from .credentials import load as load_credentials

log = get_logger(__name__)


class serverConnect:
    _ftp_timeout = 30

    def __init__(self, file, dest_folder):
        creds = load_credentials()
        self.server_ip = creds['server_ip']
        self.username = creds['username']
        self.api_key = creds['api_key']

        self.file = file
        self.dest_folder = dest_folder
        self.f_blocksize = 8192
        self.total_size = os.path.getsize(file)
        self.size_written = 0
        self._size_lock = threading.Lock()

    def Upload(self):

        def handle(block):
            with self._size_lock:
                self.size_written = (
                    self.size_written + self.f_blocksize
                    if self.size_written + self.f_blocksize < self.total_size
                    else self.total_size
                )

        def background():
            try:
                with ftplib.FTP(self.server_ip, timeout=self._ftp_timeout) as ftp:
                    try:
                        ftp.login(self.username, self.api_key)
                        ftp.cwd(self.dest_folder)
                    except Exception as e:
                        log.exception('FTP login/cwd failed: %s', e)
                        return

                    _, f = os.path.split(self.file)

                    with self._size_lock:
                        resume_from = self.size_written
                    if resume_from:
                        with self._size_lock:
                            self.size_written = ftp.size(f)
                        log.info('Upload restarting...')
                    else:
                        log.info('Uploading...')

                    try:
                        with open(self.file, 'rb') as fileh:
                            fileh.seek(resume_from)
                            response = ftp.storbinary(
                                'STOR ' + f, fileh,
                                callback=handle,
                                blocksize=self.f_blocksize,
                                rest=resume_from,
                            )
                        log.info(response)
                    except Exception as e:
                        log.exception('FTP storbinary failed: %s', e)
            except Exception as e:
                log.exception('Unable to connect to server: %s', e)

        percent_complete = 0
        t = threading.Thread(target=background)
        t.start()
        while t.is_alive():
            t.join(120)
            with self._size_lock:
                size_snapshot = self.size_written
            if size_snapshot:
                percent_complete = size_snapshot / self.total_size
                log.info('{:.1%} percent complete'.format(percent_complete))
                if percent_complete == 1:
                    return True

        if percent_complete == 1:
            return True
        return False

    def fileExists(self):
        _, f = os.path.split(self.file)
        try:
            with ftplib.FTP(self.server_ip, timeout=self._ftp_timeout) as ftp:
                ftp.login(self.username, self.api_key)
                ftp.cwd(self.dest_folder)
                return ftp.size(f) == os.path.getsize(self.file)
        except ftplib.error_perm:
            return False
        except Exception as e:
            log.exception('fileExists check failed: %s', e)
            return False

    def deleteFile(self):
        _, f = os.path.split(self.file)
        with ftplib.FTP(self.server_ip, timeout=self._ftp_timeout) as ftp:
            ftp.login(self.username, self.api_key)
            ftp.cwd(self.dest_folder)
            ftp.delete(f)
