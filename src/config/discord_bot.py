# config/discord_bot.py

import discord
from discord.ext import commands
import os
from utils.logger import logger, log_success


# ==========================================
# 1. SINGLETON DO BOT
# ==========================================

_bot_instance: commands.Bot | None = None


def get_bot() -> commands.Bot | None:
    """Retorna a instância global do bot (usado por serviços internos)."""
    return _bot_instance


def set_bot(bot: commands.Bot):
    """Registra a instância global do bot."""
    global _bot_instance
    _bot_instance = bot


# ==========================================
# 2. CRIAÇÃO DA INSTÂNCIA DO BOT
# ==========================================

def create_discord_bot() -> commands.Bot:
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members          = True
    intents.guilds           = True

    bot = commands.Bot(
        command_prefix='!',
        intents=intents,
        help_command=None
    )

    # Registra singleton imediatamente
    set_bot(bot)

    @bot.event
    async def on_error(event, *args, **kwargs):
        logger.error(f'🚨 Erro no evento {event}', exc_info=True)

    return bot


# ==========================================
# 3. INICIALIZAÇÃO DO TOKEN
# ==========================================

async def start_discord_bot(bot: commands.Bot):
    token = os.getenv('DISCORD_TOKEN')

    if not token:
        raise ValueError("DISCORD_TOKEN não definido no arquivo .env")

    try:
        await bot.start(token)
    except Exception as e:
        logger.error(f"❌ Falha ao iniciar Discord Bot: {e}")
        raise
