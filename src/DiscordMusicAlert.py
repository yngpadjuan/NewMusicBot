import sys
import discord
from .paths import get_config, get_logger

log = get_logger(__name__)


def send(channel_id: int, message: str):
    config = get_config()
    token = config.get('DEFAULT', 'token')
    alert_channel_id = config.getint('DEFAULT', 'alertChannelId')

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
        channel = client.get_channel(alert_channel_id)
        await channel.send(msg)
        await client.close()

    client.run(token)


if __name__ == '__main__':
    send(int(sys.argv[1]), sys.argv[2])
