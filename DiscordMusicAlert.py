from distutils.log import WARN
import os
import logging
import datetime
import discord
from six.moves.configparser import RawConfigParser

config = RawConfigParser()
config.read(f'{os.getcwd()}/settings.conf')

numeric_level = getattr(logging, config.get('NewMusicBot','logLevel').upper(), None)
logging.basicConfig(filename='/var/log/WAVfilePrep/filePrep.log', level=logging.WARN)

TOKEN = config.get('NewMusicBot','TOKEN')
client = discord.Client()


@client.event
async def on_ready():
    channel = client.get_channel(channel_id)
    await channel.send(message)
    await client.close()

@client.event   
async def on_error(event, *args, **kwargs):
    if event == 'on_message':
        n = datetime.datetime.now()
        time = n.strftime("[%Y-%m%d %H:%M%S]")
        msg = (time +'Unhandled message: '+ str(args[0]) +'\n')
        logging.error(msg)

        channel = client.get_channel(958901182351417354)
        await channel.send(msg)
        await client.close()
    
    else:
        n = datetime.datetime.now()
        time = n.strftime("[%Y-%m%d %H:%M%S]")
        msg = (str(time) + str(event))
        
        logging.error(msg)
        channel = client.get_channel(958901182351417354)
        await channel.send(msg)
        await client.close()

message = os.getenv('MESSAGE')
channel_id = int(os.getenv('CHANNEL'))

client.run(TOKEN)