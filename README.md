# NewMusicBot

A Discord bot that watches for new audio recordings, masters them via [Matchering](https://github.com/sergree/matchering), converts to MP3, uploads to an FTP server, and announces to Discord.

## Requirements

- Python 3.10+
- [ffmpeg](https://ffmpeg.org/) in `PATH`
- A Discord bot token with message and guild permissions

## Quick install (Linux / macOS)

```bash
git clone <repo-url>
cd NewMusicBot
bash scripts/install.sh
```

The installer will:
1. Prompt for an install directory (default: `~/newmusicbot/`)
2. Install Python dependencies
3. Write `settings.conf` and `server.credentials` (both `chmod 600`)
4. On **Linux**: install and enable a systemd unit
5. On **macOS**: install and load a launchd plist

## Manual install

```bash
export NEWMUSICBOT_HOME=/path/to/install
mkdir -p $NEWMUSICBOT_HOME/{tmp,logs}
cp -r src scripts wordlists serviceFiles settings.conf.example $NEWMUSICBOT_HOME/
cp settings.conf.example $NEWMUSICBOT_HOME/settings.conf  # then edit it
pip install -r requirements.txt
# Linux only:
pip install -r requirements-linux.txt
python $NEWMUSICBOT_HOME/scripts/run.py
```

## Environment variables

| Variable | Description |
|---|---|
| `NEWMUSICBOT_HOME` | Root install directory. All paths are resolved relative to this. Falls back to the repo root if unset. |

## `settings.conf` reference

All keys live under `[NewMusicBot]` unless noted.

| Key | Required | Description |
|---|---|---|
| `token` | Yes | Discord bot token |
| `logLevel` | No | `DEBUG` / `INFO` / `WARN` / `ERROR` (default: `INFO`) |
| `location` | Yes | Active location section: `basement`, `gigs`, or `music` |
| `alertChannelId` | Yes | Discord channel ID for ops/error alerts |
| `publishChannelId` | Yes | Discord channel ID for public song announcements |
| `watchFolder` | Linux fallback / non-Linux | Directory to watch for new `.wav` files via watchdog |
| `artist` | No | MP3 ID3 artist tag |
| `album` | No | MP3 ID3 album tag |
| `archiveFolder` | Yes for `!publish` | Root directory containing `{year}/wav/` subdirs |
| `localDestination` | Yes for websiteDownload | Local path for FTP downloads |
| `backupDest1` | No | First backup destination for `scripts/backup.py` |
| `backupDest2` | No | Second backup destination for `scripts/backup.py` |

Per-location sections (`[basement]`, `[gigs]`, `[music]`):

| Key | Description |
|---|---|
| `sessionName` | Label used in output filenames and Discord messages |
| `sdfolder` | Subfolder path on the SD card (e.g. `/STEREO/FOLDER01`) |
| `srcFolder` | Source folder on the local machine |
| `destFolder` | Destination folder on the local machine (year appended automatically) |
| `backupFolder` | Backup folder on the local machine (year appended automatically) |
| `ftpFolder` | Destination path on the FTP server |
| `refFile` | Absolute path to the Matchering reference track |

## `server.credentials` reference

Placed at `$NEWMUSICBOT_HOME/server.credentials` or `~/.config/newmusicbot/server.credentials`.

```ini
[default]
ip = ftp.example.com
user = ftpuser
key = ftppassword
ssl_verify = false
```

## File watcher backends

| Platform | Backend | How it works |
|---|---|---|
| Linux (with `pyudev`) | udev | Detects SD card insertion via kernel events. Mount point resolved from `ID_FS_UUID` or the `H4N_SD` volume label. |
| Linux (without `pyudev`) / macOS / Windows | watchdog | Polls `watchFolder` from `settings.conf` for new `.wav` files. |

## Discord bot commands

All commands require the `songadmin` role unless noted.

| Command | Description |
|---|---|
| `!publish <file> <start> <stop> [title]` | Segment, master, and publish a recording. Times in `HH:MM:SS`. |
| `!set_location <basement\|gigs\|music>` | Switch the active location. |
| `!get_location` | Show the current location. |
| `!set_session_name <location> <name>` | Update the session label for a location. |
| `!get_session_name <location>` | Show the session label. |
| `!set_logging_level <level>` | Change log verbosity (`Final Boss` role required). |
| `!get_logging_level` | Show current log level (`Final Boss` role required). |

## Backup

```bash
python scripts/backup.py
```

Copies `src/`, `scripts/`, `wordlists/`, `serviceFiles/`, and `settings.conf.example` to the paths in `backupDest1` / `backupDest2`. **`settings.conf` and `server.credentials` are never copied.**

## Smoke test

```bash
export NEWMUSICBOT_HOME=/tmp/nmb-test
mkdir -p $NEWMUSICBOT_HOME
cp settings.conf.example $NEWMUSICBOT_HOME/settings.conf
# fill in token and channel IDs, then:
python scripts/run.py
```

The bot should connect and post a "NewMusicBot is ready" message to the alert channel.
