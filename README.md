# NewMusicBot

A Discord bot that watches for new audio recordings, masters them via [Matchering](https://github.com/sergree/matchering), converts to MP3, uploads to an FTP server, and announces to Discord.

## Requirements

- Python 3.9+
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
cp -r src scripts wordlists settings.conf.example $NEWMUSICBOT_HOME/
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

Keys under `[DEFAULT]` apply globally and are inherited by every location section.
Comments must be on their own lines — inline `#` comments are not supported by the config parser.

### `[DEFAULT]` section

| Key | Required | Description |
|---|---|---|
| `token` | Yes | Discord bot token |
| `logLevel` | No | `DEBUG` / `INFO` / `WARN` / `ERROR` (default: `INFO`) |
| `alertChannelId` | Yes | Discord channel ID for ops/error alerts |
| `publishChannelId` | Yes | Discord channel ID for public song announcements |
| `artist` | No | MP3 ID3 artist tag |
| `album` | No | MP3 ID3 album tag |
| `mountPoint` | Linux fallback / non-Linux | Directory watched for new `.wav` files (watchdog) and SD card mount root (udev) |
| `srcFolder` | Yes for `/publish` | Root directory containing `{year}/wav/` subdirs used to locate archive files |
| `destFolder` | Yes | Default destination for processed MP3s (used by publish flow) |
| `backupFolder` | Yes | Default backup destination |
| `ftpFolder` | Yes | Default FTP destination path |
| `refFile` | Yes | Absolute path to the Matchering reference track |

### Per-location sections (`[basement]`, `[gigs]`, etc.)

Each location section overrides any `[DEFAULT]` keys it defines. `sessionName` and `subFolder` are location-specific and have no default.

| Key | Description |
|---|---|
| `sessionName` | Label used in output filenames and Discord messages |
| `subFolder` | Subfolder path on the SD card (e.g. `/STEREO/FOLDER01`) |
| `destFolder` | Destination folder (year appended automatically for archival flow) |
| `backupFolder` | Backup folder (year appended automatically for archival flow) |
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
| Linux (with `pyudev`) | udev | Detects SD card insertion via kernel events. Iterates config sections to find a matching `subFolder` under `mountPoint`. |
| Linux (without `pyudev`) / macOS / Windows | watchdog | Polls `mountPoint` from `settings.conf` for new `.wav` files. |

## Discord slash commands

All commands require the `songadmin` role unless noted.

| Command | Description |
|---|---|
| `/publish` | Opens a modal to segment, master, and publish a recording from the archive. Times in `HH:MM:SS`. |
| `/set_session_name` | Update the session label for a location. |
| `/set_logging_level` | Change log verbosity (`Final Boss` role required). |

## Backup

```bash
python scripts/backup.py
```

Copies `src/`, `scripts/`, `wordlists/`, and `settings.conf.example` to the paths configured in `backupDest1` / `backupDest2` under `[DEFAULT]`. **`settings.conf` and `server.credentials` are never copied.**

## Smoke test

```bash
export NEWMUSICBOT_HOME=/tmp/nmb-test
mkdir -p $NEWMUSICBOT_HOME
cp settings.conf.example $NEWMUSICBOT_HOME/settings.conf
# fill in token and channel IDs, then:
python scripts/run.py
```

The bot should connect and post a "NewMusicBot is ready" message to the alert channel.
