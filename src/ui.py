"""Discord UI components and slash command definitions for NewMusicBot."""
import re
from pathlib import Path
from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands

from .paths import get_config, get_logger, CONFIG_PATH

log = get_logger(__name__)
config = get_config()


# ── Embeds ────────────────────────────────────────────────────────────────────

def ok_embed(title: str, description: str = '') -> discord.Embed:
    return discord.Embed(title=title, description=description, color=discord.Color.green())


def err_embed(title: str, description: str = '') -> discord.Embed:
    return discord.Embed(title=title, description=description, color=discord.Color.red())


def info_embed(title: str, description: str = '') -> discord.Embed:
    return discord.Embed(title=title, description=description, color=discord.Color.blurple())


# ── Modals ────────────────────────────────────────────────────────────────────

class PublishModal(discord.ui.Modal, title='Publish Song'):
    filename = discord.ui.TextInput(
        label='Filename',
        placeholder='e.g. 2024-01-15 Basement Bar.wav',
        required=True,
    )
    start_time = discord.ui.TextInput(
        label='Start time',
        placeholder='HH:MM:SS',
        max_length=8,
        required=True,
    )
    stop_time = discord.ui.TextInput(
        label='Stop time',
        placeholder='HH:MM:SS',
        max_length=8,
        required=True,
    )
    song_title = discord.ui.TextInput(
        label='Song title (optional)',
        placeholder='Leave blank for a random name',
        required=False,
    )

    # Injected by register_commands() so the modal can enqueue work.
    _queue = None

    async def on_submit(self, interaction: discord.Interaction):
        song      = self.filename.value.strip()
        start_raw = self.start_time.value.strip()
        stop_raw  = self.stop_time.value.strip()
        title     = self.song_title.value.strip() or None

        try:
            start_dt = datetime.strptime(start_raw, '%H:%M:%S')
            start    = str(start_dt.second + start_dt.minute * 60 + start_dt.hour * 3600)
        except ValueError:
            await interaction.response.send_message(
                embed=err_embed('Invalid start time', f'`{start_raw}` is not in HH:MM:SS format.'),
                ephemeral=True,
            )
            return

        try:
            stop_dt = datetime.strptime(stop_raw, '%H:%M:%S')
            stop    = str(stop_dt.second + stop_dt.minute * 60 + stop_dt.hour * 3600)
        except ValueError:
            await interaction.response.send_message(
                embed=err_embed('Invalid stop time', f'`{stop_raw}` is not in HH:MM:SS format.'),
                ephemeral=True,
            )
            return

        if int(start) >= int(stop):
            await interaction.response.send_message(
                embed=err_embed('Invalid range', 'Start time must be before stop time.'),
                ephemeral=True,
            )
            return

        year_match = re.match(r'^\d{4}', song)
        if not year_match:
            await interaction.response.send_message(
                embed=err_embed('File not found', 'Filename must begin with a 4-digit year.'),
                ephemeral=True,
            )
            return

        song_loc = config.get('DEFAULT', 'srcFolder', fallback='') + f'/{year_match[0]}/wav'
        file = ''
        for candidate in (Path(song_loc) / song, Path(song_loc) / (song + '.wav')):
            if candidate.exists():
                file = str(candidate)
                break

        if not file:
            await interaction.response.send_message(
                embed=err_embed('File not found', f'Could not locate `{song}` in `{song_loc}`.'),
                ephemeral=True,
            )
            return

        self._queue.put([file, 'DEFAULT', start, stop, title])
        await interaction.response.send_message(embed=ok_embed(
            '✅ Queued for publishing',
            f'**File:** `{song}`\n**Start:** {start_raw}  **Stop:** {stop_raw}\n**Title:** {title}',
        ))

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        log.error(error)
        await interaction.response.send_message(
            embed=err_embed('Unexpected error', str(error)), ephemeral=True,
        )


class SessionNameModal(discord.ui.Modal, title='Set Session Name'):
    session = discord.ui.TextInput(label='Session name', required=True)

    def __init__(self, location: str):
        super().__init__()
        self.location = location
        self.session.placeholder = config.get(location, 'sessionName', fallback='')

    async def on_submit(self, interaction: discord.Interaction):
        name = self.session.value.strip()
        config.set(self.location, 'sessionName', name)
        with open(CONFIG_PATH, 'w') as f:
            config.write(f)
        await interaction.response.send_message(
            embed=ok_embed('Session name updated', f'**{self.location}** → `{name}`'),
        )


# ── Select views ──────────────────────────────────────────────────────────────

class LogLevelSelect(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        current = config.get('DEFAULT', 'logLevel', fallback='INFO').upper()
        options = [
            discord.SelectOption(label=lvl, default=(current == lvl))
            for lvl in ('DEBUG', 'INFO', 'WARN', 'ERROR')
        ]
        self.select = discord.ui.Select(placeholder='Choose a log level…', options=options)
        self.select.callback = self._on_select
        self.add_item(self.select)

    async def _on_select(self, interaction: discord.Interaction):
        level = self.select.values[0]
        config.set('DEFAULT', 'logLevel', level)
        with open(CONFIG_PATH, 'w') as config_file:
            config.write(config_file)
        await interaction.response.edit_message(
            embed=ok_embed('Log level updated', f'Log level is now **{level}**.'),
            view=None,
        )


# ── Slash command registration ────────────────────────────────────────────────

def register_commands(bot: commands.Bot, q) -> None:
    """Attach all slash commands to *bot*, passing the work queue *q* where needed."""

    # Give PublishModal access to the queue without making it a global.
    PublishModal._queue = q
    locations = {}
    for location in config.sections():
        session_name = config.get(location, 'sessionName', fallback='<unset>')
        locations[location] = session_name
    location_choices = [app_commands.Choice(name=f"{loc} ({sesh})", value=loc) for loc, sesh in locations.items()]

    @bot.tree.command(name='publish', description='Segment, master, and publish a recording')
    @app_commands.checks.has_role('songadmin')
    async def slash_publish(interaction: discord.Interaction):
        await interaction.response.send_modal(PublishModal())


    @bot.tree.command(name='set_session_name', description='Update the session label for a location')
    @app_commands.checks.has_role('songadmin')
    @app_commands.describe(location='Location to update (basement or gigs)')
    @app_commands.choices(location=location_choices)
    async def slash_set_session_name(interaction: discord.Interaction, location: str):
        await interaction.response.send_modal(SessionNameModal(location))



    @bot.tree.command(name='set_logging_level', description='Change the bot log verbosity')
    @app_commands.checks.has_role('Final Boss')
    async def slash_set_logging_level(interaction: discord.Interaction):
        current = config.get('DEFAULT', 'logLevel', fallback='INFO').upper()
        await interaction.response.send_message(
            embed=info_embed('Set Log Level', f'Current level: **{current}**'),
            view=LogLevelSelect(),
            ephemeral=True,
        )


    @bot.tree.error
    async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingRole):
            await interaction.response.send_message(
                embed=err_embed('Permission denied', 'You do not have the required role.'),
                ephemeral=True,
            )
        else:
            log.error(error)
            await interaction.response.send_message(
                embed=err_embed('Error', str(error)), ephemeral=True,
            )
