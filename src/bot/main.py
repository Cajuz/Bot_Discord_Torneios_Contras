import os
import logging
from dotenv import load_dotenv

import discord
from discord.ext import commands

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("x1-bot")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix=os.getenv("DISCORD_PREFIX", "!"), intents=intents)

@bot.event
async def on_ready():
    logger.info("Bot online: %s", bot.user)

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
