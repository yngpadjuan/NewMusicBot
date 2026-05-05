import os
import logging
import logging.handlers
from pathlib import Path
from configparser import RawConfigParser

# NEWMUSICBOT_HOME is the single install root. Falls back to the parent of this
# file's directory so the repo itself is usable without setting the env var.
HOME = Path(os.environ.get('NEWMUSICBOT_HOME', Path(__file__).parent.parent)).resolve()

CONFIG_PATH = HOME / 'settings.conf'
TMP_DIR = HOME / 'tmp'
LOG_DIR = HOME / 'logs'
WORDLISTS_DIR = HOME / 'wordlists'
CREDENTIALS_PATH = HOME / 'server.credentials'

# Ensure runtime directories exist
TMP_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

_config: RawConfigParser | None = None


def get_config() -> RawConfigParser:
    global _config
    if _config is None:
        _config = RawConfigParser()
        _config.read(CONFIG_PATH)
    return _config


def get_logger(name: str) -> logging.Logger:
    config = get_config()
    level_name = config.get('NewMusicBot', 'logLevel', fallback='INFO').upper()
    level = getattr(logging, level_name, logging.INFO)

    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.handlers.RotatingFileHandler(
            LOG_DIR / 'newmusicbot.log',
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
        )
        handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)-8s %(name)s %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
        ))
        logger.addHandler(handler)
        logger.setLevel(level)
    return logger


def _get_channel_id(key: str) -> int:
    try:
        return get_config().getint('NewMusicBot', key)
    except Exception:
        return 0


ALERT_CHANNEL_ID: int = _get_channel_id('alertChannelId')
PUBLISH_CHANNEL_ID: int = _get_channel_id('publishChannelId')
