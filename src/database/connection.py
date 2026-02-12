"""Gerenciamento de conexão com MongoDB"""
import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
import logging

load_dotenv()
logger = logging.getLogger("x1-bot")

class Database:
    client: AsyncIOMotorClient = None
    db = None

    @classmethod
    async def connect(cls):
        """Conecta ao MongoDB"""
        mongo_uri = os.getenv("MONGO_URI")
        db_name = os.getenv("MONGO_DB_NAME", "x1_bot_user")

        if not mongo_uri:
            raise RuntimeError("MONGO_URI não definido no .env")

        try:
            cls.client = AsyncIOMotorClient(
                mongo_uri,
                serverSelectionTimeoutMS=5000
            )
            
            # Testa conexão
            await cls.client.admin.command("ping")
            cls.db = cls.client[db_name]
            
            logger.info(f"✅ Conectado ao MongoDB: {db_name}")
            
        except Exception as e:
            logger.error(f"❌ Erro ao conectar MongoDB: {e}")
            raise

    @classmethod
    async def disconnect(cls):
        """Desconecta do MongoDB"""
        if cls.client:
            cls.client.close()
            logger.info("MongoDB desconectado")

    @classmethod
    def get_collection(cls, name: str):
        """Retorna uma coleção do banco"""
        if not cls.db:
            raise RuntimeError("Database não conectado. Use await Database.connect()")
        return cls.db[name]

# Atalho para usar no código
async def get_db():
    if not Database.db:
        await Database.connect()
    return Database.db
