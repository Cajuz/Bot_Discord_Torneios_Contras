import discord
from discord.ext import commands
import os
from utils.logger import logger, log_success
from services.mediador_dashbord_service import mediator_dashboard_service
import asyncio
import matplotlib.pyplot as plt
import io

def create_discord_bot() ->commands.Bot:
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
    async def setup_hook():
        try:
            # Carrega o comando uma única vez
            await bot.load_extension("models.dashbord") 
            log_success("Extensão dashboard carregada!")
            bot.loop.create_task(auto_dashboard(bot)) 

        except Exception as e:
            logger.error(f"Erro ao carregar extensão: {e}")

    bot.setup_hook = setup_hook

    @bot.event
    async def on_ready():
        log_success(f'Discord Bot logado como {bot.user.name} (ID: {bot.user.id})')
        await bot.change_presence(
            activity=discord.Game(name="Gerenciando partidas de X1!")
        )
        try:
            mediator_dashboard_service.channel_id_dashboard = 1473728494503596084


        # posta imediatamente
            await mediator_dashboard_service.update_dashboard(bot)
        except Exception as e:
            logger.error(f"Erro ao postar dashboard: {e}")
            await bot.get_channel(mediator_dashboard_service.channel_id_dashboard).send(f"❌ Erro ao postar dashboard: {e}")

    # inicia atualização automática
    
    @bot.event
    async def on_error(event, *args, **kwargs):
        logger.error(f'Erro no evento {event}', exc_info=True)
    
    return bot

async def auto_dashboard(bot):
    await bot.wait_until_ready() 
    while True:

        try:

            await mediator_dashboard_service.update_dashboard(bot)
            logger.info("Dashboard atualizado automaticamente.")
        except Exception as e:

            logger.error(f"Erro dashboard: {e}")

        await asyncio.sleep(3600)


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





