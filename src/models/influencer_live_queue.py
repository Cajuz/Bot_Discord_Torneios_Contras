"""
influencer_live_queue.py — Model da fila de desafiantes da sala live.

Schema da collection 'influencer_live_queues':
  _id             ObjectId
  room_id         ObjectId  — referência à InfluencerLiveRoom
  guild_id        int
  influencer_id   int       — dono da sala (para queries diretas)
  players         List[int] — fila de desafiantes (ordem de entrada)
  status          str       — waiting | matched | closed
  current_match_id str|None — partida em andamento na sala
  created_at      datetime
  updated_at      datetime
"""
from __future__ import annotations
from typing import Dict, Any, List, Optional
from bson import ObjectId
from utils.datetime_utils import utcnow


class InfluencerLiveQueue:

    STATUS_WAITING = "waiting"
    STATUS_MATCHED = "matched"
    STATUS_CLOSED  = "closed"

    def __init__(self, data: Dict[str, Any]):
        self._id              = data.get("_id") or ObjectId()
        self.room_id          = data.get("room_id")
        self.guild_id         = data.get("guild_id")
        self.influencer_id    = data.get("influencer_id")
        self.players          = [int(p) for p in data.get("players", [])]
        self.status           = data.get("status", self.STATUS_WAITING)
        self.current_match_id = data.get("current_match_id")
        self.created_at       = data.get("created_at", utcnow())
        self.updated_at       = data.get("updated_at", utcnow())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "_id":              self._id,
            "room_id":          self.room_id,
            "guild_id":         self.guild_id,
            "influencer_id":    self.influencer_id,
            "players":          self.players,
            "status":           self.status,
            "current_match_id": self.current_match_id,
            "created_at":       self.created_at,
            "updated_at":       utcnow(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "InfluencerLiveQueue":
        raw_id = data.get("_id")
        if isinstance(raw_id, str):
            data = {**data, "_id": ObjectId(raw_id)}
        return cls(data)

    @staticmethod
    def create_document(
        room_id: ObjectId,
        guild_id: int,
        influencer_id: int,
    ) -> Dict[str, Any]:
        now = utcnow()
        return {
            "_id":              ObjectId(),
            "room_id":          room_id,
            "guild_id":         guild_id,
            "influencer_id":    influencer_id,
            "players":          [],
            "status":           InfluencerLiveQueue.STATUS_WAITING,
            "current_match_id": None,
            "created_at":       now,
            "updated_at":       now,
        }

    # ── Helpers ──────────────────────────────────────────────────

    def enqueue(self, player_id: int) -> bool:
        """Adiciona jogador à fila. Retorna False se já estiver na fila."""
        if player_id in self.players:
            return False
        self.players.append(player_id)
        return True

    def dequeue(self, player_id: int) -> bool:
        """Remove jogador da fila. Retorna False se não estiver."""
        if player_id not in self.players:
            return False
        self.players.remove(player_id)
        return True

    def next_challenger(self) -> Optional[int]:
        """Retorna o próximo da fila sem remover."""
        return self.players[0] if self.players else None

    def pop_challenger(self) -> Optional[int]:
        """Remove e retorna o primeiro da fila."""
        return self.players.pop(0) if self.players else None

    def position(self, player_id: int) -> Optional[int]:
        """Posição 1-based do jogador na fila. None se não estiver."""
        if player_id not in self.players:
            return None
        return self.players.index(player_id) + 1

    def is_empty(self) -> bool:
        return len(self.players) == 0

    def size(self) -> int:
        return len(self.players)

    def __repr__(self) -> str:
        return (
            f"<InfluencerLiveQueue room={self.room_id} "
            f"players={len(self.players)} status={self.status}>"
        )