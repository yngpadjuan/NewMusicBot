import os
from configparser import RawConfigParser
from .paths import CREDENTIALS_PATH


def load() -> dict:
    """Return FTP credentials from server.credentials.

    Search order:
    1. $NEWMUSICBOT_HOME/server.credentials  (managed by install.sh)
    2. ~/.config/newmusicbot/server.credentials  (user override)
    """
    search_path = [
        str(CREDENTIALS_PATH),
        os.path.join(os.path.expanduser('~'), '.config', 'newmusicbot', 'server.credentials'),
    ]

    defaults = {
        'server_ip': None,
        'api_key': None,
        'username': None,
        'ssl_verify': 'false',
    }

    cfg = RawConfigParser(defaults=defaults)
    cfg.read(search_path)

    return {
        'server_ip': cfg.get('default', 'ip'),
        'username': cfg.get('default', 'user'),
        'api_key': cfg.get('default', 'key'),
        'ssl_verify': cfg.getboolean('default', 'ssl_verify', fallback=False),
    }
