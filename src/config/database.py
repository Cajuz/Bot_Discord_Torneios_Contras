import os
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import ConnectionFailure
from utils.logger import logger, log_success

class Database:
    """Classe para gerenciar conexão com MongoDB usando Motor (async)"""
    
    def __init__(self):
        self.client = None
        self.db = None
        self.uri = os.getenv('MONGODB_URI', 'mongodb://localhost:27017')
        self.db_name = os.getenv('MONGODB_DB_NAME', 'x1_bot')
    
    async def connect(self):
        """Conectar ao MongoDB"""
        try:
            self.client = AsyncIOMotorClient(self.uri)
            self.db = self.client[self.db_name]
            
            # Testar conexão
            await self.client.admin.command('ping')
            
            log_success(f"MongoDB conectado com sucesso - Database: {self.db_name}")
            
            # Criar índices
            await self._create_indexes()
            
            return True
            
        except ConnectionFailure as e:
            logger.error(f"Erro ao conectar ao MongoDB: {e}")
            raise
        except Exception as e:
            logger.error(f"Erro inesperado ao conectar ao MongoDB: {e}")
            raise
    
    async def _create_indexes(self):
        """Criar índices necessários nas collections"""
        try:

            # Índices para match_queues
            await self.db.match_queues.create_index([("channel_name", 1), ("bet_value", 1), ("gel_type", 1)])
            await self.db.match_queues.create_index("status")
            await self.db.match_queues.create_index("expires_at")

            # Índices para mediators
            await self.db.mediators.create_index("discord_id", unique=True)
            await self.db.mediators.create_index("position")
            await self.db.mediators.create_index("is_active")
            
            # Índices para matches
            await self.db.matches.create_index("status")
            await self.db.matches.create_index("created_at")
            await self.db.matches.create_index("mediator_id")
            await self.db.matches.create_index([("status", 1), ("created_at", -1)])
            
            # Índices para users
            await self.db.users.create_index("discord_id", unique=True)
            await self.db.users.create_index("is_active")
            
            logger.info("Índices do MongoDB criados com sucesso")
            
        except Exception as e:
            logger.warning(f"Erro ao criar índices (podem já existir): {e}")
    
    async def close(self):
        """Fechar conexão com MongoDB"""
        if self.client is not None:  # ✅ CORRETO - comparar com None
            self.client.close()
            logger.info("Conexão MongoDB fechada")
    
    def get_collection(self, collection_name: str):
        """
        Obter uma collection do MongoDB
        
        Args:
            collection_name: Nome da collection
            
        Returns:
            Collection do MongoDB
        """
        if self.db is None:  # ✅ CORRETO - comparar com None
            raise Exception("Database não está conectado. Execute connect() primeiro.")
        
        return self.db[collection_name]
    
    def get_database(self):
        """
        Obter instância do database
        
        Returns:
            Database do MongoDB
        """
        if self.db is None:  # ✅ CORRETO - comparar com None
            raise Exception("Database não está conectado. Execute connect() primeiro.")
        
        return self.db


# Instância global do database
db = Database()
