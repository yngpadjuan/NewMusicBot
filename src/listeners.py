import re
import os
import sys
import queue
import platform
import threading
import subprocess
from pathlib import Path
from datetime import datetime
from discord.ext import commands

from .paths import get_config, get_logger, CONFIG_PATH, TMP_DIR, ALERT_CHANNEL_ID, HOME

log = get_logger(__name__)
config = get_config()

TOKEN = config.get('NewMusicBot', 'token')

_SDCARD_MODULE = [sys.executable, '-m', 'src.SDCardPrep']
_SONG_MODULE = [sys.executable, '-m', 'src.songPrep']
_ALERT_MODULE = str(HOME / 'src' / 'DiscordMusicAlert.py')

bot = commands.Bot(command_prefix='!')
q: queue.Queue = queue.Queue()


def _discord_alert(message):
    try:
        subprocess.run([sys.executable, _ALERT_MODULE, str(ALERT_CHANNEL_ID), message], check=False)
    except Exception as e:
        log.error(e)


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
                    subprocess.run(_SONG_MODULE + [item[1], item[2], item[3], item[4]],
                                   check=True, cwd=str(HOME))
                except subprocess.CalledProcessError as e:
                    msg = f'Error processing {item[1]}: Code {e.returncode}.'
                    log.error(msg)
                    _discord_alert(msg)
        except Exception as e:
            log.error(e)
            _discord_alert(str(e))


# ── Watcher backends ─────────────────────────────────────────────────────────

def _enqueue_wav(filepath):
    """Add a wav file to the processing queue."""
    log.info(f'Found {filepath}')
    q.put(['filePrep', filepath])


def _udev_listener():
    """Linux udev backend — watches for block device events."""
    from pyudev import Context, Monitor, MonitorObserver  # linux-only

    location = config.get('NewMusicBot', 'location')

    def on_device_event(device):
        if (device.action in ('change', 'add') and
                device.get('ID_FS_TYPE') == 'vfat' and
                device.get('ID_FS_UUID')):
            src_folder = None
            sd_subfolder = config.get(location, 'sdfolder')
            candidates = [
                Path(f"/media/{os.getenv('USER', 'pi')}/{device.get('ID_FS_UUID')}") / sd_subfolder.lstrip('/'),
                Path('/media') / os.getenv('USER', 'pi') / 'H4N_SD' / sd_subfolder.lstrip('/'),
            ]
            for candidate in candidates:
                if candidate.exists():
                    src_folder = candidate
                    break

            if src_folder:
                log.info(f'Source folder: {src_folder}')
                for dirpath, _, filenames in os.walk(src_folder):
                    if dirpath == str(src_folder):
                        for fname in filenames:
                            if fname.endswith('.wav'):
                                _enqueue_wav(os.path.join(dirpath, fname))
            else:
                msg = 'Unable to find audio tracks in SD card.'
                log.info(msg)
                _discord_alert(msg)

    ctx = Context()
    monitor = Monitor.from_netlink(ctx)
    monitor.filter_by(subsystem='block')
    observer = MonitorObserver(monitor, callback=on_device_event, name='monitor-observer')
    observer.start()
    _discord_alert('NewMusicBot is ready')
    observer.join()


def _watchdog_listener():
    """Cross-platform polling backend — watches a configured folder for new wav files."""
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
    """Pick the best available watcher backend for the current platform."""
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


# ── Discord bot commands ──────────────────────────────────────────────────────

@bot.command(pass_context=True)
@commands.has_role('songadmin')
async def publish(ctx, song: str, start: str, stop: str, title: str = None):
    year = re.match(r'^\d{4}', song)
    if year:
        song_loc = config.get('NewMusicBot', 'archiveFolder', fallback='') + f'/{year[0]}/wav'
        try:
            start_dt = datetime.strptime(start, '%H:%M:%S')
            start = str(start_dt.second + start_dt.minute * 60 + start_dt.hour * 3600)
        except Exception as e:
            await ctx.send(str(e))
            return

        try:
            stop_dt = datetime.strptime(stop, '%H:%M:%S')
            stop = str(stop_dt.second + stop_dt.minute * 60 + stop_dt.hour * 3600)
        except Exception as e:
            await ctx.send(str(e))
            return

        if int(start) < int(stop):
            file = ''
            for candidate in (Path(song_loc) / song, Path(song_loc) / (song + '.wav')):
                if candidate.exists():
                    file = str(candidate)
                    break
            if not file:
                await ctx.send('Oops... unable to find that file name. Check your spelling.')
                return

            if not title:
                title = 'None'

            await ctx.send(f'Started publishing {song}. Start: {start} Stop: {stop}')
            q.put(['publishSong', file, start, stop, title])
        else:
            await ctx.send('Oops... start time greater than end time.')
    else:
        await ctx.send('Oops... unable to find that file name. Check your spelling.')


@bot.command(pass_context=True)
@commands.has_role('songadmin')
async def set_session_name(ctx, location: str, session: str = None):
    locations = ['basement', 'gigs']
    if session:
        if location.lower() in locations:
            config.set(location.lower(), 'sessionName', session)
            with open(CONFIG_PATH, 'w') as f:
                config.write(f)
            await ctx.send(f"Session Name for {location}: '{session}'.")
        else:
            await ctx.send(f'!set_session_name <location> <session name>. Location must be one of: {locations}')
    else:
        await ctx.send('!set_session_name <location> <session name>')


@bot.command(pass_context=True)
@commands.has_role('songadmin')
async def get_session_name(ctx, location: str):
    await ctx.send(f"Session Name for {location}: {config.get(location, 'sessionName')}")


@bot.command(pass_context=True)
@commands.has_role('songadmin')
async def set_location(ctx, location: str = None):
    locations = ['basement', 'gigs', 'music']
    if location:
        if location.lower() in locations:
            config.set('NewMusicBot', 'location', location)
            with open(CONFIG_PATH, 'w') as f:
                config.write(f)
            await ctx.send(f'Location is now {location}.')
        else:
            await ctx.send(f'!set_location <location> must be one of {locations}')
    else:
        await ctx.send(f'!set_location <{locations}>')


@bot.command(pass_context=True)
@commands.has_role('songadmin')
async def get_location(ctx):
    await ctx.send(f"Location: {config.get('NewMusicBot', 'location')}")


@bot.command(pass_context=True)
@commands.has_role('Final Boss')
async def set_logging_level(ctx, logging_level: str = None):
    levels = ['DEBUG', 'INFO', 'WARN', 'ERROR']
    if logging_level:
        if logging_level.upper() in levels:
            config.set('NewMusicBot', 'logLevel', logging_level.upper())
            with open(CONFIG_PATH, 'w') as config_file:
                config.write(config_file)
            await ctx.send(f'Logging Level has been set to {logging_level.upper()}')
        else:
            await ctx.send(f"!set_logging_level <level> Must be one of {levels}")
    else:
        await ctx.send('!set_logging_level <level>')


@bot.command(pass_context=True)
@commands.has_role('Final Boss')
async def get_logging_level(ctx):
    await ctx.send(f"Logging Level: {config.get('NewMusicBot', 'logLevel')}")


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.errors.CheckFailure):
        await ctx.send('You do not have the correct role for this command.')
    else:
        await ctx.send(str(error))


threading.Thread(target=worker, daemon=True).start()
threading.Thread(target=_start_listener, daemon=True).start()
bot.run(TOKEN)
