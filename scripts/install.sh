#!/usr/bin/env bash
# install.sh — install NewMusicBot on Linux or macOS
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEFAULT_HOME="${HOME}/newmusicbot"

echo "=== NewMusicBot Installer ==="
echo ""
read -rp "Install directory [${DEFAULT_HOME}]: " NEWMUSICBOT_HOME
NEWMUSICBOT_HOME="${NEWMUSICBOT_HOME:-$DEFAULT_HOME}"

echo ""
echo "Installing to: ${NEWMUSICBOT_HOME}"
mkdir -p "${NEWMUSICBOT_HOME}/tmp"
mkdir -p "${NEWMUSICBOT_HOME}/logs"

# Copy code
for d in src scripts wordlists; do
    rm -rf "${NEWMUSICBOT_HOME}/${d}"
    cp -r "${REPO_DIR}/${d}" "${NEWMUSICBOT_HOME}/${d}"
done
for f in settings.conf.example requirements.txt .gitignore; do
    [ -f "${REPO_DIR}/${f}" ] && cp "${REPO_DIR}/${f}" "${NEWMUSICBOT_HOME}/${f}"
done
[ -f "${REPO_DIR}/requirements-linux.txt" ] && cp "${REPO_DIR}/requirements-linux.txt" "${NEWMUSICBOT_HOME}/"

echo ""
echo "--- Python dependencies ---"
pip install -r "${NEWMUSICBOT_HOME}/requirements.txt"
if [[ "$(uname -s)" == "Linux" ]] && [ -f "${NEWMUSICBOT_HOME}/requirements-linux.txt" ]; then
    pip install -r "${NEWMUSICBOT_HOME}/requirements-linux.txt"
fi

# Write settings.conf
CONF="${NEWMUSICBOT_HOME}/settings.conf"
if [ ! -f "${CONF}" ]; then
    echo ""
    echo "--- Configure settings.conf ---"
    read -rp "Discord bot token: " BOT_TOKEN
    read -rp "Alert channel ID: " ALERT_CHANNEL
    read -rp "Publish channel ID: " PUBLISH_CHANNEL
    read -rp "Default location (basement/gigs/music) [basement]: " LOCATION
    LOCATION="${LOCATION:-basement}"
    read -rp "Watch folder for wav files (leave blank to use udev on Linux): " WATCH_FOLDER
    read -rp "Artist name for MP3 tags: " ARTIST
    read -rp "Album name for MP3 tags: " ALBUM

    cat > "${CONF}" <<EOF
[NewMusicBot]
token = ${BOT_TOKEN}
logLevel = INFO
alertChannelId = ${ALERT_CHANNEL}
publishChannelId = ${PUBLISH_CHANNEL}
artist = ${ARTIST}
album = ${ALBUM}
mountPoint = ${WATCH_FOLDER}
srcFolder = 
destFolder =
backupFolder =
ftpFolder =
refFile =

[basement]
sessionName = Basement Bar
subFolder = /STEREO/FOLDER01
destFolder =
backupFolder =
ftpFolder =
refFile =

[gigs]
sessionName = Conifock
subFolder = /STEREO/FOLDER02
destFolder =
backupFolder =
ftpFolder =
refFile =

EOF
    chmod 600 "${CONF}"
    echo "Written: ${CONF}"
else
    echo "settings.conf already exists, skipping."
fi

# Write server.credentials
CREDS="${NEWMUSICBOT_HOME}/server.credentials"
if [ ! -f "${CREDS}" ]; then
    echo ""
    echo "--- Configure server.credentials ---"
    read -rp "FTP server IP/hostname: " FTP_IP
    read -rp "FTP username: " FTP_USER
    read -rsp "FTP password / API key: " FTP_KEY
    echo ""

    cat > "${CREDS}" <<EOF
[default]
ip = ${FTP_IP}
user = ${FTP_USER}
key = ${FTP_KEY}
ssl_verify = false
EOF
    chmod 600 "${CREDS}"
    echo "Written: ${CREDS}"
else
    echo "server.credentials already exists, skipping."
fi

# System service
echo ""
echo "--- System service ---"
OS="$(uname -s)"
if [[ "${OS}" == "Linux" ]]; then
    UNIT="/etc/systemd/system/newmusicbot.service"
    PYTHON="$(which python3)"
    sudo tee "${UNIT}" > /dev/null <<EOF
[Unit]
Description=NewMusicBot
After=network-online.target
Wants=network-online.target

[Service]
ExecStart=${PYTHON} ${NEWMUSICBOT_HOME}/scripts/run.py
WorkingDirectory=${NEWMUSICBOT_HOME}
Environment=NEWMUSICBOT_HOME=${NEWMUSICBOT_HOME}
StandardOutput=inherit
StandardError=inherit
Restart=always
User=${USER}

[Install]
WantedBy=multi-user.target
EOF
    sudo systemctl daemon-reload
    sudo systemctl enable newmusicbot
    echo "systemd unit installed and enabled: ${UNIT}"
    echo "Start with: sudo systemctl start newmusicbot"
elif [[ "${OS}" == "Darwin" ]]; then
    PLIST="${HOME}/Library/LaunchAgents/com.newmusicbot.plist"
    PYTHON="$(which python3)"
    cat > "${PLIST}" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>          <string>com.newmusicbot</string>
    <key>ProgramArguments</key>
    <array>
        <string>${PYTHON}</string>
        <string>${NEWMUSICBOT_HOME}/scripts/run.py</string>
    </array>
    <key>WorkingDirectory</key> <string>${NEWMUSICBOT_HOME}</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>NEWMUSICBOT_HOME</key> <string>${NEWMUSICBOT_HOME}</string>
    </dict>
    <key>RunAtLoad</key>       <true/>
    <key>KeepAlive</key>       <true/>
    <key>StandardOutPath</key> <string>${NEWMUSICBOT_HOME}/logs/stdout.log</string>
    <key>StandardErrorPath</key><string>${NEWMUSICBOT_HOME}/logs/stderr.log</string>
</dict>
</plist>
EOF
    launchctl load "${PLIST}"
    echo "launchd plist installed: ${PLIST}"
    echo "Start with: launchctl start com.newmusicbot"
fi

echo ""
echo "=== Installation complete ==="
echo "NEWMUSICBOT_HOME=${NEWMUSICBOT_HOME}"
echo "Edit ${CONF} to fill in any remaining paths, then start the service."
