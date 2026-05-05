import sys
import discord
from .paths import get_config, get_logger

log = get_logger(__name__)

config = get_config()
TOKEN = config.get('NewMusicBot', 'token')
ALERT_CHANNEL_ID = config.getint('NewMusicBot', 'alertChannelId')

channel_id = int(sys.argv[1])
message = sys.argv[2]

client = discord.Client(intents=discord.Intents.default())

@client.event
async def on_ready():
    channel = client.get_channel(channel_id)
    await channel.send(message)
    await client.close()

@client.event
async def on_error(event, *args, **kwargs):
    if event == 'on_message':
        msg = f'Unhandled message: {args[0]}'
    else:
        msg = event
    log.error(msg)
    channel = client.get_channel(ALERT_CHANNEL_ID)
    await channel.send(msg)
    await client.close()

client.run(TOKEN)
