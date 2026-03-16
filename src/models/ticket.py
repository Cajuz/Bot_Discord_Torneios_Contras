from __future__ import annotations
from datetime import datetime
from utils.datetime_utils import utcnow
from bson import ObjectId
from typing import Optional


class Ticket:

    STATUS_ABERTO    = "aberto"
    STATUS_PENDENTE  = "pendente"
    STATUS_RESOLVIDO = "resolvido"
    STATUS_FECHADO   = "fechado"

    CATEGORIAS = ["Bug", "Pagamento", "Dúvida", "Outro"]

    STATUS_EMOJI = {
        "aberto":    "🟡",
        "pendente":  "🔵",
        "resolvido": "✅",
        "fechado":   "⛔",
    }

    OPEN_STATUSES   = {STATUS_ABERTO, STATUS_PENDENTE}
    CLOSED_STATUSES = {STATUS_RESOLVIDO, STATUS_FECHADO}

    def __init__(self, data: dict):
        self._id             = data.get("_id", ObjectId())
        self.ticket_id       = data.get("ticket_id", "TKT-00000000")
        self.discord_id      = str(data.get("discord_id", ""))
        self.username        = data.get("username", "")
        self.guild_id        = data.get("guild_id")
        self.categoria       = data.get("categoria", "Outro")
        self.descricao       = data.get("descricao", "")
        self.status          = data.get("status", self.STATUS_ABERTO)
        self.atendente_id    = data.get("atendente_id")
        self.card_message_id = data.get("card_message_id")
        self.opened_at       = data.get("opened_at")
        self.created_at      = data.get("created_at", utcnow())
        self.updated_at      = data.get("updated_at", utcnow())
        self.closed_at       = data.get("closed_at")
        self.resolved_at     = data.get("resolved_at")

    def is_open(self) -> bool:
        return self.status in self.OPEN_STATUSES

    def is_closed(self) -> bool:
        return self.status in self.CLOSED_STATUSES

    def status_label(self) -> str:
        emoji = self.STATUS_EMOJI.get(self.status, "❓")
        return f"{emoji} {self.status.capitalize()}"

    def to_dict(self) -> dict:
        return {
            "_id":            self._id,
            "ticket_id":      self.ticket_id,
            "discord_id":     self.discord_id,
            "username":       self.username,
            "guild_id":       self.guild_id,
            "categoria":      self.categoria,
            "descricao":      self.descricao,
            "status":         self.status,
            "atendente_id":   self.atendente_id,
            "card_message_id": self.card_message_id,
            "opened_at":      self.opened_at,
            "created_at":     self.created_at,
            "updated_at":     self.updated_at,
            "closed_at":      self.closed_at,
            "resolved_at":    self.resolved_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Ticket":
        return cls(data)

    @staticmethod
    def create_document(
        discord_id: str,
        username: str,
        guild_id: int,
        ticket_id: str,
        categoria: str,
        descricao: str,
    ) -> dict:
        now = utcnow()
        return {
            "_id":            ObjectId(),
            "ticket_id":      ticket_id,
            "discord_id":     discord_id,
            "username":       username,
            "guild_id":       guild_id,
            "categoria":      categoria,
            "descricao":      descricao,
            "status":         Ticket.STATUS_ABERTO,
            "atendente_id":   None,
            "card_message_id": None,
            "opened_at":      now,
            "created_at":     now,
            "updated_at":     now,
            "closed_at":      None,
            "resolved_at":    None,
        }