"""Operações de partidas no banco"""
from datetime import datetime
from typing import List, Optional
from src.database.connection import Database
from src.database.models import MatchSchema, MatchStatus, MatchType

class MatchRepository:
    COLLECTION = "matches"

    @classmethod
    async def create(
        cls,
        match_type: MatchType,
        players: List[int],
        thread_id: int,
        **kwargs
    ):
        """Cria nova partida"""
        collection = Database.get_collection(cls.COLLECTION)
        
        match_data = MatchSchema.create(
            match_type=match_type,
            players=players,
            thread_id=thread_id,
            **kwargs
        )
        
        result = await collection.insert_one(match_data)
        match_data["_id"] = result.inserted_id
        
        return match_data

    @classmethod
    async def find_by_thread_id(cls, thread_id: int):
        """Busca partida por ID da thread"""
        collection = Database.get_collection(cls.COLLECTION)
        return await collection.find_one({"thread_id": thread_id})

    @classmethod
    async def update_status(cls, thread_id: int, status: MatchStatus):
        """Atualiza status da partida"""
        collection = Database.get_collection(cls.COLLECTION)
        
        await collection.update_one(
            {"thread_id": thread_id},
            {
                "$set": {
                    "status": status.value,
                    "updated_at": datetime.utcnow()
                }
            }
        )

    @classmethod
    async def finish_match(cls, thread_id: int, winner_id: int):
        """Finaliza partida com vencedor"""
        collection = Database.get_collection(cls.COLLECTION)
        
        await collection.update_one(
            {"thread_id": thread_id},
            {
                "$set": {
                    "status": MatchStatus.COMPLETED.value,
                    "winner_id": winner_id,
                    "finished_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }
            }
        )

    @classmethod
    async def get_active_matches(cls) -> List[dict]:
        """Retorna partidas ativas"""
        collection = Database.get_collection(cls.COLLECTION)
        
        cursor = collection.find({
            "status": MatchStatus.IN_PROGRESS.value
        })
        
        return await cursor.to_list(length=100)

    @classmethod
    async def get_user_matches(cls, discord_id: int, limit: int = 10):
        """Retorna últimas partidas do usuário"""
        collection = Database.get_collection(cls.COLLECTION)
        
        cursor = collection.find({
            "players": discord_id
        }).sort("created_at", -1).limit(limit)
        
        return await cursor.to_list(length=limit)

    @classmethod
    async def count_by_type(cls, match_type: MatchType) -> int:
        """Conta partidas por tipo"""
        collection = Database.get_collection(cls.COLLECTION)
        return await collection.count_documents({"match_type": match_type.value})
