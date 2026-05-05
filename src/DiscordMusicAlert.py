import sys
import datetime
import discord
from .paths import get_config, get_logger, LOG_DIR

log = get_logger(__name__)

config = get_config()
TOKEN = config.get('NewMusicBot', 'token')
ALERT_CHANNEL_ID = config.getint('NewMusicBot', 'alertChannelId')

channel_id = int(sys.argv[1])
message = sys.argv[2]

client = discord.Client()

@client.event
async def on_ready():
    channel = client.get_channel(channel_id)
    await channel.send(message)
    await client.close()

@client.event
async def on_error(event, *args, **kwargs):
    err_log = LOG_DIR / 'discorderr.log'
    with open(err_log, 'a') as f:
        ts = datetime.datetime.now().strftime('[%Y-%m-%d %H:%M:%S]')
        if event == 'on_message':
            msg = f'{ts} Unhandled message: {args[0]}\n'
            f.write(msg)
        else:
            msg = f'{ts} {event}\n'
            f.write(msg)

    channel = client.get_channel(ALERT_CHANNEL_ID)
    await channel.send(msg)
    await client.close()

client.run(TOKEN)
