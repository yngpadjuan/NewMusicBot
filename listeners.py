import re
import os
import sys
import queue
import logging
import threading
import subprocess
from pathlib import Path
from datetime import datetime
from discord.ext import commands
from six.moves.configparser import RawConfigParser
from pyudev import Context, Monitor, MonitorObserver



config = RawConfigParser()
config.read(f'{os.getcwd()}/settings.conf')

logging.basicConfig(filename='/var/log/WAVfilePrep/filePrep.log', level=logging.WARN)

TOKEN = config.get('NewMusicBot','TOKEN')

bot = commands.Bot(command_prefix="!")
q = queue.Queue()

def worker():
    logging.info("Queue Started.")
    while True:
        file = q.get()
        logging.info(f"{file} retreived from Queue")
        if file[0] == "filePrep":
            try:
                subprocess.run([sys.executable,'/home/pi/Music/BoxMusic/SDCardPrep.py', file[1]],check=True)
            except subprocess.CalledProcessError as e:
                msg = (f"Error processing {file[1]}: Code{e.returncode}. Retrying.")
                logging.error(msg)
                subprocess.call(['sh','/home/pi/Music/BoxMusic/DiscordMusicAlert.sh',f'{msg}','958901182351417354'])
                q.put(file)
        elif file[0] == "publishSong":
            try:
                subprocess.run([sys.executable,'/home/pi/Music/BoxMusic/songPrep.py', file[1], file[2], file[3], file[4]],check=True)
            except subprocess.CalledProcessError as e:
                msg = (f"Error processing {file[1]}: Code{e.returncode}.")
                logging.error(msg)
                subprocess.call(['sh','/home/pi/Music/BoxMusic/DiscordMusicAlert.sh',f'{msg}','958901182351417354'])


def filePrep(device):
    # print('''
    
    # ''')
    # for prop in device.properties:
    #     print(prop, device.get(f'{prop}'))

    if (device.action == 'change' or device.action == 'add') and (device.get('ID_FS_TYPE') == 'vfat' and device.get('ID_FS_UUID')):
        location = config.get('NewMusicBot','location')      
        src_folder = f"/media/pi/{device.get('ID_FS_UUID')}{config.get(location,'sdfolder')}"
        logging.info("SourceFolder is set to:" + src_folder)

        logging.info(f'Source Folder exists: {Path(src_folder).exists()}')
        if Path(src_folder).exists():
            for (dirpath, dirnames, filenames) in os.walk(src_folder):
                if dirpath == src_folder: 
                    logging.info(f'Found {filenames} in {src_folder}')
                    for file in filenames:                                     
                        if file.endswith('.wav'):                        
                            item = ['filePrep', os.path.join(dirpath,file)]
                            logging.debug(f'Adding {item} to queue.')        
                            q.put(item)
        else:
            msg = (f'Unable to find audio tracks in SD card.')
            logging.info(msg)
            if logging.root.level <= 20:
                subprocess.call(['sh','/home/pi/Music/BoxMusic/DiscordMusicAlert.sh',f'{msg}','958901182351417354'])
                
            
def uDevListener():
    context = Context()
    monitor = Monitor.from_netlink(context)
    monitor.filter_by(subsystem='block')

    observer = MonitorObserver(monitor, callback=filePrep, name='monitor-observer')

    observer.start()
    subprocess.call(['sh','/home/pi/Music/BoxMusic/DiscordMusicAlert.sh','NewMusicBot is ready','958901182351417354'])
    observer.join()


@bot.command(pass_context=True)
@commands.has_role('songadmin')
async def publish(ctx, song: str, start: str, stop: str, title:str=None):
    year = re.match("^\d\d\d\d",song)
    if year:
        song_loc = r'/home/pi/Music/BoxMusic/MusicFiles/Windows/BoxMusic/'+ year[0] + r'/wav'
        try:
            start = datetime.strptime(start, '%H:%M:%S')
            start = str(start.second + start.minute *60 + start.hour *3600)
        except Exception as e:
            await ctx.send(e)

        try:
            stop = datetime.strptime(stop, '%H:%M:%S')
            stop = str(stop.second + stop.minute *60 + stop.hour *3600)
        except Exception as e:
            await ctx.send(e)
        
        if int(start) < int(stop):
            file = ''
            if Path(f"{song_loc}/{song}").exists():
                file = f"{song_loc}/{song}"                       
            elif Path(f"{song_loc}/{song}.wav").exists():
                file = f'{song_loc}/{song}.wav'
            else:
                await ctx.send(f"Oops... unable to find that file name. Check your spelling.")

            await ctx.send(f"Started publishing {song}. Start: {start} Stop: {stop}")
            q.put(['publishSong',file, start, stop, title])

        else:
            await ctx.send(f"Oops... start time greater than end time.")
    else:
        await ctx.send(f"Oops... unable to find that file name. Check your spelling.")

@bot.command(pass_context=True)
@commands.has_role('songadmin')
async def set_session_name(ctx, location, session:str=None):
    locations = ['basement','gigs']
    if session:
        if location.lower() in locations:
            config.set(location.lower(),'sessionName',session)
            with open(f'{os.getcwd()}/settings.conf','w') as f:
                config.write(f)
            await ctx.send(f"Session Name for {location}: \'{session}\'.")
        else:
            await ctx.send(f"!set_session_name <location> <session name>. Location must be one of: {locations}") 
    else:
        await ctx.send("!set_session_name <location> <session name>")

@bot.command(pass_context=True)
@commands.has_role('songadmin')
async def get_session_name(ctx, location):
    await ctx.send(f"Session Name for {location}: {config.get(location,'sessionName')}")

@bot.command(pass_context=True)
@commands.has_role('songadmin')
async def set_location(ctx, location:str=None):
    locations = ['basement','gigs','music']
    if location:
        if location.lower() in locations:
            config.set('NewMusicBot','location',location)
            with open(f'{os.getcwd()}/settings.conf','w') as f:
                config.write(f)
            await ctx.send(f"Location is now {location}.")
        else:
            await ctx.send(f"!set_location <location> must be one of {locations}")
    else:
        await ctx.send(f"!set_location <{locations}>")

@bot.command(pass_context=True)
@commands.has_role('songadmin')
async def get_location(ctx):
    await ctx.send(f"Location: {config.get('NewMusicBot','location')}")

@bot.command(pass_context=True)
@commands.has_role('Final Boss')
async def set_logging_level(ctx, logging_level:str=None):
    levels = ['DEBUG','INFO','WARN','ERROR']
    if logging_level:
        if logging_level.upper() in levels:
            config.set('NewMusicBot','logLevel',logging_level.upper())
            with open(f'{os.getcwd()}/settings.conf','w') as config_file:
                config.write(config_file)
            await ctx.send(f"Logging Level has been set to {logging_level.upper()}")
        else:
            await ctx.send("!set_logging_level <level> Must be one of ['DEBUG','INFO','WARN','ERROR']")
    else:
        await ctx.send("!set_logging_level <level>")        

@bot.command(pass_context=True)
@commands.has_role('Final Boss')
async def get_logging_level(ctx):
    await ctx.send(f"Logging Level: {config.get('NewMusicBot','logLevel')}")

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.errors.CheckFailure):
        await ctx.send('You do not have the correct role for this command.')
    else:
        await ctx.send(error)


threading.Thread(target=worker, daemon=True).start()
threading.Thread(target=uDevListener, daemon=True).start()
bot.run(TOKEN)