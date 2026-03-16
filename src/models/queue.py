from datetime import datetime
from utils.datetime_utils import utcnow
from typing import List, Optional
from bson import ObjectId


class MatchQueue:
    """Modelo para fila de partidas"""

    STATUS_WAITING    = "waiting"
    STATUS_CONFIRMING = "confirming"
    STATUS_MATCHED    = "matched"    # fila virou partida com sucesso
    STATUS_EXPIRED    = "expired"

    def __init__(
        self,
        channel_name: str,
        bet_value: float,
        gel_type: str,
        max_players: int,
        players: List[int] = None,
        status: str = "waiting",
        created_at: datetime = None,
        expires_at: datetime = None,
        confirmation_message_id: Optional[int] = None,
        confirmations: List[int] = None,
        thread_id: Optional[int] = None,
        guild_id: Optional[int] = None,
        match_id: Optional[str] = None,   # ← referência à partida gerada
        _id: ObjectId = None
    ):
        self._id                     = _id or ObjectId()
        self.channel_name            = channel_name
        self.bet_value               = bet_value
        self.gel_type                = gel_type
        self.max_players             = max_players
        self.players                 = players or []
        self.status                  = status
        self.created_at              = created_at or utcnow()
        self.expires_at              = expires_at
        self.confirmation_message_id = confirmation_message_id
        self.confirmations           = confirmations or []
        self.thread_id               = thread_id
        self.guild_id                = guild_id
        self.match_id                = match_id    # ← novo

    def to_dict(self) -> dict:
        return {
            "_id":                     self._id,
            "channel_name":            self.channel_name,
            "bet_value":               self.bet_value,
            "gel_type":                self.gel_type,
            "max_players":             self.max_players,
            "players":                 self.players,
            "status":                  self.status,
            "created_at":              self.created_at,
            "expires_at":              self.expires_at,
            "confirmation_message_id": self.confirmation_message_id,
            "confirmations":           self.confirmations,
            "thread_id":               self.thread_id,
            "guild_id":                self.guild_id,
            "match_id":                self.match_id,   # ← novo
        }

    @staticmethod
    def from_dict(data: dict) -> "MatchQueue":
        raw_id = data.get("_id")
        if isinstance(raw_id, str):
            raw_id = ObjectId(raw_id)

        return MatchQueue(
            _id=raw_id,
            channel_name=data.get("channel_name"),
            bet_value=data.get("bet_value"),
            gel_type=data.get("gel_type"),
            max_players=data.get("max_players"),
            players=data.get("players", []),
            status=data.get("status", "waiting"),
            created_at=data.get("created_at"),
            expires_at=data.get("expires_at"),
            confirmation_message_id=data.get("confirmation_message_id"),
            confirmations=data.get("confirmations", []),
            thread_id=data.get("thread_id"),
            guild_id=data.get("guild_id"),
            match_id=data.get("match_id"),   # ← novo
        )

    # ── Helpers ─────────────────────────────────────────────────

    def is_full(self) -> bool:
        return len(self.players) >= self.max_players

    def add_player(self, player_id: int) -> bool:
        if player_id not in self.players and not self.is_full():
            self.players.append(player_id)
            return True
        return False

    def remove_player(self, player_id: int) -> bool:
        if player_id in self.players:
            self.players.remove(player_id)
            return True
        return False

    def add_confirmation(self, player_id: int) -> bool:
        if player_id in self.players and player_id not in self.confirmations:
            self.confirmations.append(player_id)
            return True
        return False

    def all_confirmed(self) -> bool:
        return len(self.confirmations) == len(self.players)

    def pending_confirmations(self) -> List[int]:
        """Jogadores que ainda não confirmaram."""
        return [p for p in self.players if p not in self.confirmations]

    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return utcnow() > self.expires_at

    def mark_as_matched(self, match_id: str):
        """Sela a fila como convertida em partida."""
        self.status   = self.STATUS_MATCHED
        self.match_id = match_id

    def __repr__(self) -> str:
        return (
            f"<MatchQueue {self.channel_name} R${self.bet_value} "
            f"{self.gel_type} {len(self.players)}/{self.max_players} "
            f"status={self.status}>"
        )
