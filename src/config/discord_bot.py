import discord
from discord.ext import commands, tasks
import os
from utils.logger import logger, log_success
from services.mediador_dashboard_service import mediator_dashboard_service
import asyncio

# ==========================================
# 1. DEFINIÇÃO DO LOOP DE 1 HORA
# ==========================================
@tasks.loop(hours=1)
async def dashboard_auto_loop(bot):
    """Loop que atualiza o dashboard a cada 1 hora"""
    try:
        logger.info("🔄 Iniciando atualização automática do dashboard...")
        await mediator_dashboard_service.update_dashboard(bot)
        log_success("✅ Dashboard automatizado atualizado com sucesso.")
    except Exception as e:
        logger.error(f"❌ Erro no loop do dashboard: {e}")

# ==========================================
# 2. CRIAÇÃO DA INSTÂNCIA DO BOT
# ==========================================
def create_discord_bot() -> commands.Bot:
    """Configura e retorna o bot"""
    
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True
    intents.guilds = True
    
    bot = commands.Bot(
        command_prefix='!',
        intents=intents,
        help_command=None
    )

    # Função obrigatória para iniciar tarefas de fundo (Loops)
    #async def setup_hook():
        #try:
            # IMPORTANTE: Se seus comandos estão no main, 
            # NÃO use load_extension aqui para não duplicar o comando 'dashboard'
            
            #if not dashboard_auto_loop.is_running():
                #dashboard_auto_loop.start(bot)
                #log_success("✅ Loop de 1 hora iniciado!")
       #except Exception as e:
            #logger.error(f"❌ Erro ao iniciar loop no setup_hook: {e}")

    # Conecta o setup_hook ao bot
    #bot.setup_hook = setup_hook

    @bot.event
    async def on_ready():
        log_success(f'🚀 Discord Bot logado como {bot.user.name}')
        await bot.change_presence(
            activity=discord.Game(name="Gerenciando partidas de X1!")
        )
        
        # Postagem imediata ao ligar o bot
        try:
            mediator_dashboard_service.channel_id_dashboard = 1473728494503596084
            await mediator_dashboard_service.update_dashboard(bot)
        except Exception as e:
            logger.error(f"❌ Erro na postagem inicial: {e}")

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