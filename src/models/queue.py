from datetime import datetime
from typing import List, Optional
from bson import ObjectId

class MatchQueue:
    """Modelo para fila de partidas"""
    
    def __init__(
        self,
        channel_name: str,
        bet_value: float,
        gel_type: str,  # "normal" ou "infinito"
        max_players: int,
        players: List[int] = None,
        status: str = "waiting",  # waiting, confirming, expired
        created_at: datetime = None,
        expires_at: datetime = None,
        confirmation_message_id: Optional[int] = None,
        confirmations: List[int] = None,
        _id: ObjectId = None
    ):
        self._id = _id or ObjectId()
        self.channel_name = channel_name
        self.bet_value = bet_value
        self.gel_type = gel_type
        self.max_players = max_players
        self.players = players or []
        self.status = status
        self.created_at = created_at or datetime.utcnow()
        self.expires_at = expires_at
        self.confirmation_message_id = confirmation_message_id
        self.confirmations = confirmations or []
    
    def to_dict(self):
        """Converter para dicionário"""
        return {
            "_id": self._id,
            "channel_name": self.channel_name,
            "bet_value": self.bet_value,
            "gel_type": self.gel_type,
            "max_players": self.max_players,
            "players": self.players,
            "status": self.status,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "confirmation_message_id": self.confirmation_message_id,
            "confirmations": self.confirmations
        }
    
    @staticmethod
    def from_dict(data: dict):
        """Criar instância a partir de dicionário"""
        return MatchQueue(
            _id=data.get("_id"),
            channel_name=data.get("channel_name"),
            bet_value=data.get("bet_value"),
            gel_type=data.get("gel_type"),
            max_players=data.get("max_players"),
            players=data.get("players", []),
            status=data.get("status", "waiting"),
            created_at=data.get("created_at"),
            expires_at=data.get("expires_at"),
            confirmation_message_id=data.get("confirmation_message_id"),
            confirmations=data.get("confirmations", [])
        )
    
    def is_full(self) -> bool:
        """Verificar se a fila está cheia"""
        return len(self.players) >= self.max_players
    
    def add_player(self, player_id: int) -> bool:
        """Adicionar jogador à fila"""
        if player_id not in self.players and not self.is_full():
            self.players.append(player_id)
            return True
        return False
    
    def remove_player(self, player_id: int) -> bool:
        """Remover jogador da fila"""
        if player_id in self.players:
            self.players.remove(player_id)
            return True
        return False
    
    def add_confirmation(self, player_id: int) -> bool:
        """Adicionar confirmação de jogador"""
        if player_id in self.players and player_id not in self.confirmations:
            self.confirmations.append(player_id)
            return True
        return False
    
    def all_confirmed(self) -> bool:
        """Verificar se todos confirmaram"""
        return len(self.confirmations) == len(self.players)
