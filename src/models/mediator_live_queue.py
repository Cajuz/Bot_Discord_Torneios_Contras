"""
mediator_live_queue.py — Model da fila exclusiva de mediadores Controller Live.

Schema da collection 'mediator_live_queues':
  _id             ObjectId
  guild_id        int
  mediators       List[int]  — fila de mediadores disponíveis (ordem de entrada)
  status          str        — waiting | busy | closed
  active_match_id str|None   — partida live em andamento atribuída a esta fila
  created_at      datetime
  updated_at      datetime

Diferença da fila padrão (mediator_queue.py):
  — Esta fila é dedicada ao modo Influencer Live.
  — Apenas mediadores com cargo "Controller Live" entram aqui.
  — Não mistura com a fila padrão de mediadores.
"""
from __future__ import annotations
from typing import Dict, Any, List, Optional
from bson import ObjectId
from utils.datetime_utils import utcnow


class MediatorLiveQueue:

    STATUS_WAITING = "waiting"
    STATUS_BUSY    = "busy"
    STATUS_CLOSED  = "closed"

    # Nome do cargo no Discord
    ROLE_NAME = "Controller Live"

    def __init__(self, data: Dict[str, Any]):
        self._id             = data.get("_id") or ObjectId()
        self.guild_id        = data.get("guild_id")
        self.mediators       = [int(m) for m in data.get("mediators", [])]
        self.status          = data.get("status", self.STATUS_WAITING)
        self.active_match_id = data.get("active_match_id")
        self.created_at      = data.get("created_at", utcnow())
        self.updated_at      = data.get("updated_at", utcnow())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "_id":             self._id,
            "guild_id":        self.guild_id,
            "mediators":       self.mediators,
            "status":          self.status,
            "active_match_id": self.active_match_id,
            "created_at":      self.created_at,
            "updated_at":      utcnow(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MediatorLiveQueue":
        raw_id = data.get("_id")
        if isinstance(raw_id, str):
            data = {**data, "_id": ObjectId(raw_id)}
        return cls(data)

    @staticmethod
    def create_document(guild_id: int) -> Dict[str, Any]:
        now = utcnow()
        return {
            "_id":             ObjectId(),
            "guild_id":        guild_id,
            "mediators":       [],
            "status":          MediatorLiveQueue.STATUS_WAITING,
            "active_match_id": None,
            "created_at":      now,
            "updated_at":      now,
        }

    # ── Helpers ──────────────────────────────────────────────────

    def enter_queue(self, mediator_id: int) -> bool:
        """Mediador entra na fila. Retorna False se já estiver."""
        if mediator_id in self.mediators:
            return False
        self.mediators.append(mediator_id)
        return True

    def leave_queue(self, mediator_id: int) -> bool:
        """Mediador sai da fila. Retorna False se não estiver."""
        if mediator_id not in self.mediators:
            return False
        self.mediators.remove(mediator_id)
        return True

    def next_mediator(self) -> Optional[int]:
        """Retorna o próximo mediador disponível sem remover."""
        return self.mediators[0] if self.mediators else None

    def pop_mediator(self) -> Optional[int]:
        """Remove e retorna o primeiro mediador da fila."""
        if not self.mediators:
            return None
        mediator = self.mediators.pop(0)
        if not self.mediators:
            self.status = self.STATUS_WAITING
        return mediator

    def is_available(self) -> bool:
        """True se há pelo menos um mediador na fila e status não é busy."""
        return bool(self.mediators) and self.status != self.STATUS_BUSY

    def set_busy(self, match_id: str):
        """Marca a fila como ocupada com uma partida live."""
        self.status          = self.STATUS_BUSY
        self.active_match_id = match_id

    def set_free(self):
        """Libera a fila após fim de partida."""
        self.status          = self.STATUS_WAITING
        self.active_match_id = None

    def position(self, mediator_id: int) -> Optional[int]:
        """Posição 1-based do mediador na fila."""
        if mediator_id not in self.mediators:
            return None
        return self.mediators.index(mediator_id) + 1

    def size(self) -> int:
        return len(self.mediators)

    def __repr__(self) -> str:
        return (
            f"<MediatorLiveQueue guild={self.guild_id} "
            f"mediators={len(self.mediators)} status={self.status}>"
        )