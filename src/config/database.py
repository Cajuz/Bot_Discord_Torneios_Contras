import os
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import ConnectionFailure
from utils.logger import logger, log_success


class Database:

    def __init__(self):
        self.client  = None
        self.db      = None
        self.uri     = (
            os.getenv('MONGODB_URI')
            or os.getenv('MONGO_URI')
            or 'mongodb://localhost:27017'
        )
        self.db_name = (
            os.getenv('MONGODB_DB_NAME')
            or os.getenv('MONGO_DB_NAME')
            or 'x1_bot'
        )

    async def connect(self):
        try:
            self.client = AsyncIOMotorClient(
                self.uri,
                serverSelectionTimeoutMS=10000,
                connectTimeoutMS=10000,
                socketTimeoutMS=20000,
            )
            self.db     = self.client[self.db_name]
            await self.client.admin.command('ping')
            log_success(f"MongoDB conectado — Database: {self.db_name}")
            await self._create_indexes()
            return True
        except ConnectionFailure as e:
            logger.error(f"Erro ao conectar ao MongoDB: {e}")
            raise
        except Exception as e:
            logger.error(f"Erro inesperado ao conectar ao MongoDB: {e}")
            raise

    async def _create_indexes(self):
        try:
            await self.db.match_queues.create_index(
                [("channel_name", 1), ("bet_value", 1), ("gel_type", 1)]
            )
            await self.db.match_queues.create_index("status")
            await self.db.match_queues.create_index("expires_at")

            await self.db.mediators.create_index("discord_id", unique=True)
            await self.db.mediators.create_index("position")
            await self.db.mediators.create_index("is_active")

            await self.db.matches.create_index("status")
            await self.db.matches.create_index("created_at")
            await self.db.matches.create_index("mediator_id")
            await self.db.matches.create_index([("status", 1), ("created_at", -1)])

            await self.db.users.create_index("discord_id", unique=True)
            await self.db.users.create_index("is_active")

            await self.db.thread_pool.create_index("channel_id")

            await self.db.active_threads.create_index("expires_at")
            await self.db.active_threads.create_index("thread_id", unique=True)

            await self.db.match_history_messages.create_index(
                "expires_at", expireAfterSeconds=0
            )

            logger.info("Índices do MongoDB criados com sucesso")

        except Exception as e:
            logger.warning(f"Erro ao criar índices (podem já existir): {e}")

    async def close(self):
        if self.client is not None:
            self.client.close()
            logger.info("Conexão MongoDB fechada")

    def get_collection(self, collection_name: str):
        if self.db is None:
            raise Exception("Database não conectado. Execute connect() primeiro.")
        return self.db[collection_name]

    def get_database(self):
        if self.db is None:
            raise Exception("Database não conectado. Execute connect() primeiro.")
        return self.db


db = Database()
