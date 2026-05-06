import os
import sys
import queue
import platform
import threading
import subprocess
from pathlib import Path

import discord
from discord.ext import commands

from .paths import get_config, get_logger, TMP_DIR, ALERT_CHANNEL_ID, HOME
from .ui import register_commands

log = get_logger(__name__)
config = get_config()

TOKEN = config.get('NewMusicBot', 'token')

_SDCARD_MODULE = [sys.executable, '-m', 'src.SDCardPrep']
_SONG_MODULE   = [sys.executable, '-m', 'src.songPrep']
_ALERT_MODULE  = 'src.DiscordMusicAlert'

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)
q: queue.Queue = queue.Queue()


# ── Internal alert helper ─────────────────────────────────────────────────────

def _discord_alert(message: str):
    try:
        subprocess.run(
            [sys.executable, '-m', _ALERT_MODULE, str(ALERT_CHANNEL_ID), message],
            check=False, cwd=str(HOME),
        )
    except Exception as e:
        log.error(e)


# ── Queue worker ──────────────────────────────────────────────────────────────

def worker():
    log.info('Queue started.')
    while True:
        item = q.get()
        log.info(f'{item} retrieved from queue')
        try:
            if item[0] == 'filePrep':
                try:
                    subprocess.run(_SDCARD_MODULE + [item[1]], check=True, cwd=str(HOME))
                except subprocess.CalledProcessError as e:
                    msg = f'Error processing {item[1]}: Code {e.returncode}.'
                    log.error(msg)
                    _discord_alert(msg)
                    for fname in os.listdir(TMP_DIR):
                        try:
                            os.remove(TMP_DIR / fname)
                        except Exception:
                            pass

            elif item[0] == 'publishSong':
                try:
                    subprocess.run(
                        _SONG_MODULE + [item[1], item[2], item[3], item[4]],
                        check=True, cwd=str(HOME),
                    )
                except subprocess.CalledProcessError as e:
                    msg = f'Error processing {item[1]}: Code {e.returncode}.'
                    log.error(msg)
                    _discord_alert(msg)
        except Exception as e:
            log.error(e)
            _discord_alert(str(e))


# ── Watcher backends ──────────────────────────────────────────────────────────

def _enqueue_wav(filepath: str):
    log.info(f'Found {filepath}')
    q.put(['filePrep', filepath])


def _udev_listener():
    from pyudev import Context, Monitor, MonitorObserver

    location = config.get('NewMusicBot', 'location')

    def on_device_event(device):
        if (device.action in ('change', 'add') and
                device.get('ID_FS_TYPE') == 'vfat' and
                device.get('ID_FS_UUID')):
            sd_subfolder = config.get(location, 'sdfolder')
            candidates = [
                Path(f"/media/{os.getenv('USER', 'pi')}/{device.get('ID_FS_UUID')}") / sd_subfolder.lstrip('/'),
                Path('/media') / os.getenv('USER', 'pi') / 'H4N_SD' / sd_subfolder.lstrip('/'),
            ]
            for c in candidates:
                log.debug(f'Checking candidate: {c} (exists={c.exists()})')
            src_folder = next((c for c in candidates if c.exists()), None)
            if src_folder:
                log.info(f'Source folder: {src_folder}')
                wav_found = False
                for dirpath, _, filenames in os.walk(src_folder):
                    if dirpath == str(src_folder):
                        for fname in filenames:
                            if fname.endswith('.wav'):
                                wav_found = True
                                _enqueue_wav(os.path.join(dirpath, fname))
                if not wav_found:
                    msg = 'Unable to find audio tracks in SD card.'
                    log.info(msg)
                    _discord_alert(msg)
            else:
                log.warning(f'No candidate path found. UUID={device.get("ID_FS_UUID")} USER={os.getenv("USER")}')

    ctx = Context()
    monitor = Monitor.from_netlink(ctx)
    monitor.filter_by(subsystem='block')
    observer = MonitorObserver(monitor, callback=on_device_event, name='monitor-observer')
    observer.start()
    _discord_alert('NewMusicBot is ready')
    observer.join()


def _watchdog_listener():
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileCreatedEvent

    watch_folder = config.get('NewMusicBot', 'watchFolder', fallback='')
    if not watch_folder:
        log.error('watchFolder not set in settings.conf; watchdog listener cannot start.')
        return

    watch_path = Path(watch_folder)
    watch_path.mkdir(parents=True, exist_ok=True)

    class _Handler(FileSystemEventHandler):
        def on_created(self, event):
            if isinstance(event, FileCreatedEvent) and event.src_path.endswith('.wav'):
                _enqueue_wav(event.src_path)

    observer = Observer()
    observer.schedule(_Handler(), str(watch_path), recursive=False)
    observer.start()
    log.info(f'Watching {watch_path} for new wav files.')
    _discord_alert('NewMusicBot is ready')
    try:
        observer.join()
    finally:
        observer.stop()


def _start_listener():
    if platform.system() == 'Linux':
        try:
            import pyudev  # noqa: F401
            log.info('Using udev listener.')
            _udev_listener()
            return
        except ImportError:
            log.warning('pyudev not available on Linux; falling back to watchdog.')
    try:
        import watchdog  # noqa: F401
        log.info('Using watchdog listener.')
        _watchdog_listener()
    except ImportError:
        log.error('Neither pyudev nor watchdog is installed. No file watcher started.')


# ── Bot lifecycle ─────────────────────────────────────────────────────────────

register_commands(bot, q)


@bot.event
async def on_ready():
    await bot.tree.sync()
    log.info(f'Logged in as {bot.user} — slash commands synced.')


threading.Thread(target=worker, daemon=True).start()
threading.Thread(target=_start_listener, daemon=True).start()
bot.run(TOKEN)
