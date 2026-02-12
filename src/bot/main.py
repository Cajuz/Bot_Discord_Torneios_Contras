# ✅ Imports necessários
import os
import sys
sys.path.insert(0, '/app/src')
import logging
from dotenv import load_dotenv
from database.connection import Database  
import discord
from discord.ext import commands

# ✅ Configurações iniciais
load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("x1-bot")
intents = discord.Intents.default()
intents.message_content = True
intents.members = True


# ✅ Classe local do Bot customizada
class MyBot(commands.Bot):
    async def setup_hook(self):
        """Executado antes do bot conectar ao Discord"""
        await Database.connect()
        await self.tree.sync()
        logger.info("Comandos sincronizados")
    
    async def close(self):
        """Executado ao desligar o bot"""
        await Database.disconnect()
        await super().close()

# ✅ Instancia a classe customizada
bot = MyBot(command_prefix=os.getenv("DISCORD_PREFIX", "!"), intents=intents)

@bot.event
async def on_ready():
    # Testa conexão com banco de dados e discord api
    db_status = Database.db.name if Database.db is not None else "Desconectado"
    logger.info(f"Bot online: {bot.user}")
    logger.info(f"MongoDB conectado: {db_status}")

@bot.command()
async def ping(ctx):
    await ctx.send(f"Pong! {round(bot.latency * 1000)}ms")

def main():
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise RuntimeError("DISCORD_TOKEN vazio no .env")
    bot.run(token)
if __name__ == "__main__":
    main()
