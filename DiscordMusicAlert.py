import os
import sys
import datetime
import discord
from six.moves.configparser import RawConfigParser

config = RawConfigParser()
config.read(f'{os.getcwd()}/settings.conf')

TOKEN = config.get('NewMusicBot','token')
client = discord.Client()

@client.event
async def on_ready():
    channel = client.get_channel(channel_id)
    await channel.send(message)
    await client.close()

@client.event   
async def on_error(event, *args, **kwargs):
    with open('/home/pi/Music/BoxMusic/discorderr.log', 'a') as f:
        if event == 'on_message':
            n = datetime.datetime.now()
            time = n.strftime("[%Y-%m%d %H:%M%S]")
            msg = (time +'Unhandled message: '+ str(args[0]) +'\n')
            f.write(msg)

            channel = client.get_channel(958901182351417354)
            await channel.send(msg)
            await client.close()
        
        else:
            n = datetime.datetime.now()
            time = n.strftime("[%Y-%m%d %H:%M%S]")
            msg = (str(time) + str(event))
            channel = client.get_channel(958901182351417354)
            await channel.send(msg)
            await client.close()

channel_id = int(sys.argv[1])
message = sys.argv[2]

client.run(TOKEN)