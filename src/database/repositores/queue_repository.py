"""Operações de fila no banco (opcional, se quiser persistir)"""
from src.database.connection import Database
from src.database.models import QueueSchema, MatchType

class QueueRepository:
    COLLECTION = "queues"

    @classmethod
    async def add_to_queue(cls, discord_id: int, match_type: MatchType):
        """Adiciona usuário à fila"""
        collection = Database.get_collection(cls.COLLECTION)
        
        # Conta posição na fila
        position = await collection.count_documents({"match_type": match_type.value})
        
        queue_data = QueueSchema.create(discord_id, match_type, position=position + 1)
        
        await collection.insert_one(queue_data)

    @classmethod
    async def remove_from_queue(cls, discord_id: int, match_type: MatchType):
        """Remove usuário da fila"""
        collection = Database.get_collection(cls.COLLECTION)
        
        await collection.delete_one({
            "discord_id": discord_id,
            "match_type": match_type.value
        })

    @classmethod
    async def get_queue(cls, match_type: MatchType):
        """Retorna fila ordenada"""
        collection = Database.get_collection(cls.COLLECTION)
        
        cursor = collection.find({
            "match_type": match_type.value
        }).sort("joined_at", 1)
        
        return await cursor.to_list(length=100)

    @classmethod
    async def clear_queue(cls, match_type: MatchType):
        """Limpa fila"""
        collection = Database.get_collection(cls.COLLECTION)
        await collection.delete_many({"match_type": match_type.value})
