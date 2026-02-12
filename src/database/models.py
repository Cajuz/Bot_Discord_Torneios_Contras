"""Schemas/modelos de dados"""
from datetime import datetime
from typing import Optional, List
from enum import Enum

class MatchStatus(str, Enum):
    WAITING = "waiting"        # Aguardando jogadores
    IN_PROGRESS = "in_progress" # Em andamento
    COMPLETED = "completed"     # Finalizada
    CANCELLED = "cancelled"     # Cancelada

class MatchType(str, Enum):
    X1_1REAL = "x1_1real"
    X1_2REAIS = "x1_2reais"
    X1_3REAIS = "x1_3reais"

# Schema de Usuário
class UserSchema:
    @staticmethod
    def create(discord_id: int, username: str, **kwargs):
        return {
            "discord_id": discord_id,
            "username": username,
            "total_matches": kwargs.get("total_matches", 0),
            "wins": kwargs.get("wins", 0),
            "losses": kwargs.get("losses", 0),
            "total_earned": kwargs.get("total_earned", 0.0),
            "total_spent": kwargs.get("total_spent", 0.0),
            "is_mediator": kwargs.get("is_mediator", False),
            "is_admin": kwargs.get("is_admin", False),
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }

# Schema de Partida
class MatchSchema:
    @staticmethod
    def create(
        match_type: MatchType,
        players: List[int],  # lista de discord_ids
        thread_id: int,
        **kwargs
    ):
        return {
            "match_type": match_type.value,
            "thread_id": thread_id,
            "players": players,  # [discord_id1, discord_id2, ...]
            "mediator_id": kwargs.get("mediator_id"),
            "status": MatchStatus.IN_PROGRESS.value,
            "winner_id": kwargs.get("winner_id"),
            "bet_amount": kwargs.get("bet_amount", 0.0),
            "started_at": datetime.utcnow(),
            "finished_at": kwargs.get("finished_at"),
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }

# Schema de Fila
class QueueSchema:
    @staticmethod
    def create(discord_id: int, match_type: MatchType, **kwargs):
        return {
            "discord_id": discord_id,
            "match_type": match_type.value,
            "position": kwargs.get("position", 0),
            "joined_at": datetime.utcnow()
        }
