"""
Arquivo de inicialização do projeto
Execute: python -m src.bot.main
"""

import asyncio
import os
from dotenv import load_dotenv

# Carrega variáveis de ambiente
load_dotenv()

# Import após carregar variáveis
from src.bot.main import bot
from src.database.mongodb import connect_db, close_db

async def main():
    """Inicializa o bot"""
    print("=" * 50)
    print("🤖 X1 FREE FIRE DISCORD BOT")
    print("=" * 50)
    
    # Conecta ao MongoDB
    try:
        await connect_db()
        print("✓ Banco de dados conectado")
    except Exception as e:
        print(f"✗ Erro ao conectar ao MongoDB: {e}")
        return
    
    # Inicia o bot
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        print("✗ DISCORD_TOKEN não configurado em .env")
        return
    
    try:
        await bot.start(token)
    except Exception as e:
        print(f"✗ Erro ao iniciar bot: {e}")
    finally:
        await close_db()

if __name__ == "__main__":
    asyncio.run(main())
