import os
import queue
import platform
import threading
import time
from pathlib import Path

import discord
from discord.ext import commands

from .paths import get_config, get_logger, ALERT_CHANNEL_ID
from .ui import register_commands
from .songPrep import main as song_prep_main
from .DiscordMusicAlert import send as _discord_send

log = get_logger(__name__)
config = get_config()

TOKEN = config.get('DEFAULT', 'token')

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)
q: queue.Queue = queue.Queue()


# ── Internal alert helper ─────────────────────────────────────────────────────

def _discord_alert(message: str):
    try:
        _discord_send(ALERT_CHANNEL_ID, message)
    except Exception as e:
        log.error(e)


# ── Queue worker ──────────────────────────────────────────────────────────────

def worker():
    log.info('Queue started.')
    while True:
        file, section, start, end, songName = q.get()
        log.info(f'{file} retrieved from queue')
        try:
            try:
                song_prep_main(file=file, section=section, start=start, end=end, songName=songName)
            except Exception as e:
                msg = f'Error processing {file}: {e}.'
                log.error(msg)
                _discord_alert(msg)
        except Exception as e:
            log.error(e)
            _discord_alert(str(e))


# ── Watcher backends ──────────────────────────────────────────────────────────

def _udev_listener():
    from pyudev import Context, Monitor, MonitorObserver

    def on_device_event(device):
        if (device.action in ('change', 'add') and
                device.get('ID_FS_TYPE') == 'vfat' and
                device.get('ID_FS_UUID')):
            #TODO: This is pretty hacky; we should probably store the UUIDs of known devices in the config and match against that instead of blindly checking all candidates for every event.
            for sections in config.sections():
                if config.get(sections, 'subFolder', fallback=None):
                    sd_subfolder = config.get(sections, 'subFolder', fallback='')
                    candidates = [
                        Path(f"{config.get('DEFAULT', 'mountPoint', fallback='')}/{device.get('ID_FS_UUID')}{sd_subfolder}"),
                        Path(f"{config.get('DEFAULT', 'mountPoint', fallback='')}/H4N_SD{sd_subfolder}")
                    ]
                    for c in candidates:
                        log.debug(f'Checking candidate: {c} (exists={c.exists()})')

                    src_folder = next((c for c in candidates if c.exists()), None)
                    if src_folder:
                        log.info(f'Source folder: {src_folder}')
                        for dirpath, _, filenames in os.walk(src_folder):
                            if dirpath == str(src_folder):
                                for fname in filenames:
                                    if fname.endswith('.wav'):
                                        q.put([os.path.join(dirpath, fname), sections, None, None, None])
                    else:
                        log.warning(f'No candidate path found. UUID={device.get("ID_FS_UUID")} USER={os.getenv("USER")}')

    ctx = Context()
    monitor = Monitor.from_netlink(ctx)
    monitor.filter_by(subsystem='block')
    observer = MonitorObserver(monitor, callback=on_device_event, name='monitor-observer')
    observer.start()
    observer.join()


def _wait_for_write_complete(path: str, stable_checks: int = 3, interval: float = 1.0) -> bool:
    """Poll until file size is stable for `stable_checks` consecutive reads, or file disappears."""
    last_size = -1
    streak = 0
    while streak < stable_checks:
        try:
            size = os.path.getsize(path)
        except OSError:
            return False
        if size == last_size:
            streak += 1
        else:
            streak = 0
            last_size = size
        if streak < stable_checks:
            time.sleep(interval)
    return True


def _watchdog_folder_listener():
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileCreatedEvent

    use_close_event = platform.system() == 'Linux'
    if use_close_event:
        from watchdog.events import FileClosedEvent

    class _Handler(FileSystemEventHandler):
        def __init__(self, section):
            self.section = section

        def _enqueue(self, path):
            if _wait_for_write_complete(path):
                q.put([path, self.section, None, None, None])
            else:
                log.warning(f'File disappeared before write completed: {path}')

        def on_created(self, event):
            if use_close_event:
                return
            if isinstance(event, FileCreatedEvent) and event.src_path.endswith('.wav'):
                threading.Thread(target=self._enqueue, args=(event.src_path,), daemon=True).start()

        def on_closed(self, event):
            if use_close_event and isinstance(event, FileClosedEvent) and event.src_path.endswith('.wav'):
                q.put([event.src_path, self.section, None, None, None])

    observer = Observer()
    watched_count = 0

    default_loc = config.get('DEFAULT', 'watchdog_location', fallback='').strip()
    if default_loc:
        p = Path(default_loc)
        p.mkdir(parents=True, exist_ok=True)
        observer.schedule(_Handler('DEFAULT'), str(p), recursive=False)
        log.info(f'Watchdog monitoring {p} (DEFAULT)')
        watched_count += 1

    for section in config.sections():
        loc = config.get(section, 'watchdog_location', fallback='').strip()
        if loc:
            p = Path(loc)
            p.mkdir(parents=True, exist_ok=True)
            observer.schedule(_Handler(section), str(p), recursive=False)
            log.info(f'Watchdog monitoring {p} ({section})')
            watched_count += 1

    if watched_count == 0:
        log.info('No watchdog_location configured; watchdog folder listener not started.')
        return

    observer.start()
    try:
        observer.join()
    finally:
        observer.stop()


def _start_listener():
    if platform.system() == 'Linux':
        try:
            import pyudev  # noqa: F401
            log.info('Starting udev listener.')
            threading.Thread(target=_udev_listener, daemon=True).start()
        except ImportError:
            log.warning('pyudev not available on Linux; udev listener skipped.')

    _discord_alert('NewMusicBot is ready')

    try:
        import watchdog  # noqa: F401
        _watchdog_folder_listener()
    except ImportError:
        log.warning('watchdog not installed; watchdog folder listener not started.')


# ── Bot lifecycle ─────────────────────────────────────────────────────────────

register_commands(bot, q)


@bot.event
async def on_ready():
    await bot.tree.sync()
    log.info(f'Logged in as {bot.user} — slash commands synced.')


threading.Thread(target=worker, daemon=True).start()
threading.Thread(target=_start_listener, daemon=True).start()
bot.run(TOKEN)
