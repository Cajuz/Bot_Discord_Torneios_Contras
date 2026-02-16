import discord
from discord.ext import commands
import os
from utils.logger import logger, log_success

def create_discord_bot() -> commands.Bot:
    """Criar instância do bot Discord"""
    
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True
    intents.guilds = True
    
    bot = commands.Bot(
        command_prefix='!',
        intents=intents,
        help_command=None
    )
    
    @bot.event
    async def on_ready():
        log_success(f'Discord Bot logado como {bot.user.name} (ID: {bot.user.id})')
        await bot.change_presence(
            activity=discord.Game(name="Gerenciando partidas de X1!")
        )
    
    @bot.event
    async def on_error(event, *args, **kwargs):
        logger.error(f'Erro no evento {event}', exc_info=True)
    
    return bot

async def start_discord_bot(bot: commands.Bot):
    """Iniciar o bot Discord"""
    token = os.getenv('DISCORD_TOKEN')
    
    if not token:
        raise ValueError("DISCORD_TOKEN não definido no arquivo .env")
    
    try:
        await bot.start(token)
    except Exception as e:
        logger.error(f"Falha ao iniciar Discord Bot: {e}")
        raise
