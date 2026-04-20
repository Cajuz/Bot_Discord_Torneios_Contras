"""
mediator.py — Modelo de Mediador.
Alinhado com o schema do mediator_queue.py.

Schema da collection 'mediators':
  user_id          int   — ID Discord (chave principal)
  username         str
  guild_id         int
  is_active        bool
  in_queue         bool
  queue_type       str   — standard | live  (tipo de fila ativa)
  matches_mediated int
  expiration_date  datetime | None  — adicionado pelo renewal_cog
  last_renewal_at  datetime | None
  expiry_notified  bool
  last_match_at    datetime | None
  created_at       datetime
  updated_at       datetime
"""
from __future__ import annotations
from datetime import datetime
from typing import Dict, Any, Optional
from utils.datetime_utils import utcnow


class Mediator:

    # ── Queue Types ───────────────────────────────────────────
    # Identifica em qual fila o mediador está atuando no momento
    QUEUE_TYPE_STANDARD = 'standard'  # fila padrão (comportamento atual)
    QUEUE_TYPE_LIVE     = 'live'      # fila Controller Live (modo contra)

    QUEUE_TYPES = [QUEUE_TYPE_STANDARD, QUEUE_TYPE_LIVE]

    def __init__(self, data: Dict[str, Any]):
        self.user_id          = data.get("user_id")
        self.username         = data.get("username", "")
        self.guild_id         = data.get("guild_id", 0)
        self.is_active        = data.get("is_active", True)
        self.in_queue         = data.get("in_queue", False)
        self.queue_type       = data.get("queue_type", self.QUEUE_TYPE_STANDARD)
        self.matches_mediated = data.get("matches_mediated", 0)
        self.expiration_date  = data.get("expiration_date")
        self.last_renewal_at  = data.get("last_renewal_at")
        self.expiry_notified  = data.get("expiry_notified", False)
        self.last_match_at    = data.get("last_match_at")
        self.created_at       = data.get("created_at", utcnow())
        self.updated_at       = data.get("updated_at", utcnow())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id":          self.user_id,
            "username":         self.username,
            "guild_id":         self.guild_id,
            "is_active":        self.is_active,
            "in_queue":         self.in_queue,
            "queue_type":       self.queue_type,
            "matches_mediated": self.matches_mediated,
            "expiration_date":  self.expiration_date,
            "last_renewal_at":  self.last_renewal_at,
            "expiry_notified":  self.expiry_notified,
            "last_match_at":    self.last_match_at,
            "created_at":       self.created_at,
            "updated_at":       utcnow(),
        }

    @staticmethod
    def create_document(
        user_id: int,
        username: str,
        guild_id: int = 0,
    ) -> Dict[str, Any]:
        now = utcnow()
        return {
            "user_id":          user_id,
            "username":         username,
            "guild_id":         guild_id,
            "is_active":        True,
            "in_queue":         False,
            "queue_type":       Mediator.QUEUE_TYPE_STANDARD,
            "matches_mediated": 0,
            "expiration_date":  None,
            "last_renewal_at":  None,
            "expiry_notified":  False,
            "last_match_at":    None,
            "created_at":       now,
            "updated_at":       now,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Mediator":
        return cls(data)

    # ── Helpers ──────────────────────────────────────────────────

    def is_license_valid(self) -> bool:
        """Retorna True se a licença está ativa e não vencida."""
        if not self.expiration_date:
            return True  # sem data = sem restrição
        return self.expiration_date > utcnow()

    def days_until_expiry(self) -> Optional[int]:
        """Dias restantes da licença. Negativo = já venceu."""
        if not self.expiration_date:
            return None
        return (self.expiration_date - utcnow()).days

    def is_live_mediator(self) -> bool:
        """True se o mediador está operando na fila Controller Live."""
        return self.queue_type == self.QUEUE_TYPE_LIVE

    def enter_live_queue(self):
        """Coloca o mediador na fila live."""
        self.in_queue   = True
        self.queue_type = self.QUEUE_TYPE_LIVE

    def enter_standard_queue(self):
        """Coloca o mediador na fila padrão."""
        self.in_queue   = True
        self.queue_type = self.QUEUE_TYPE_STANDARD

    def leave_queue(self):
        """Remove o mediador de qualquer fila."""
        self.in_queue   = False
        self.queue_type = self.QUEUE_TYPE_STANDARD

    def __repr__(self) -> str:
        return (
            f"<Mediator user_id={self.user_id} "
            f"username={self.username} "
            f"in_queue={self.in_queue} "
            f"queue_type={self.queue_type} "
            f"active={self.is_active}>"
        )