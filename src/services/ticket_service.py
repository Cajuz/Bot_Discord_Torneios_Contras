from __future__ import annotations
from datetime import datetime
from typing import Optional, List
import discord

from config.database import db
from models.ticket import Ticket
from utils.logger import logger

CHAMADOS_CHANNEL_NAME = "chamados-suporte"
SUPORTE_CHANNEL_NAME  = "suporte"
SUPORTE_ROLE_NAME     = "Suporte"


class TicketService:

    # ─────────────────────────────────────────────
    # Numeração sequencial
    # ─────────────────────────────────────────────

    

    async def get_ticket_by_card_message_id(self, message_id: int) -> Optional[Ticket]:
        doc = await db.get_collection("tickets").find_one(
            {"card_message_id": message_id}
        )
        return Ticket.from_dict(doc) if doc else None


    async def _next_ticket_id(self) -> str:
        col    = db.get_collection("tickets")
        ultimo = await col.find_one(
            {},
            sort=[("ticket_id", -1)]
        )
        if not ultimo:
            return "TKT-00000000"

        last_num = int(ultimo["ticket_id"].replace("TKT-", ""))
        return f"TKT-{(last_num + 1):08d}"

    # ─────────────────────────────────────────────
    # Criar ticket
    # ─────────────────────────────────────────────

    async def create_ticket(
        self,
        discord_id: str,
        username: str,
        guild_id: int,
        categoria: str,
        descricao: str,
    ) -> tuple[bool, str, Optional[Ticket]]:
        """
        Retorna (success, mensagem_erro, ticket).
        Falha se já houver ticket aberto ou pendente.
        """
        col = db.get_collection("tickets")

        # Checa ticket ativo
        ativo = await col.find_one({
            "discord_id": str(discord_id),
            "guild_id":   guild_id,
            "status":     {"$in": [Ticket.STATUS_ABERTO, Ticket.STATUS_PENDENTE]}
        })
        if ativo:
            t = Ticket.from_dict(ativo)
            return (
                False,
                f"Você já possui um chamado ativo (`{t.ticket_id}` — {t.categoria}).\n"
                f"Feche-o antes de abrir um novo com `!fechar_chamado {t.ticket_id}`.",
                None
            )

        ticket_id = await self._next_ticket_id()
        doc       = Ticket.create_document(
            discord_id=str(discord_id),
            username=username,
            guild_id=guild_id,
            ticket_id=ticket_id,
            categoria=categoria,
            descricao=descricao,
        )
        await col.insert_one(doc)
        return True, "", Ticket.from_dict(doc)

    # ─────────────────────────────────────────────
    # Assumir ticket
    # ─────────────────────────────────────────────

    async def assume_ticket(
        self,
        ticket_id: str,
        atendente_id: str,
        guild_id: int,
    ) -> tuple[bool, str, Optional[Ticket]]:
        col    = db.get_collection("tickets")
        doc    = await col.find_one({"ticket_id": ticket_id, "guild_id": guild_id})
        if not doc:
            return False, "Chamado não encontrado.", None

        ticket = Ticket.from_dict(doc)
        if ticket.status != Ticket.STATUS_ABERTO:
            return False, f"Chamado já está `{ticket.status}` — não pode ser assumido.", None

        now = datetime.utcnow()
        await col.update_one(
            {"ticket_id": ticket_id},
            {"$set": {
                "status":       Ticket.STATUS_PENDENTE,
                "atendente_id": str(atendente_id),
                "updated_at":   now,
            }}
        )
        ticket.status       = Ticket.STATUS_PENDENTE
        ticket.atendente_id = str(atendente_id)
        ticket.updated_at   = now
        return True, "", ticket

    # ─────────────────────────────────────────────
    # Fechar ticket (membro)
    # ─────────────────────────────────────────────

    async def close_ticket(
        self,
        ticket_id: str,
        discord_id: str,
        guild_id: int,
    ) -> tuple[bool, str, Optional[Ticket]]:
        col = db.get_collection("tickets")
        doc = await col.find_one({"ticket_id": ticket_id, "guild_id": guild_id})
        if not doc:
            return False, "Chamado não encontrado.", None

        ticket = Ticket.from_dict(doc)
        if ticket.discord_id != str(discord_id):
            return False, "Você não é o dono deste chamado.", None

        if ticket.is_closed():
            return False, f"Chamado já está `{ticket.status}`.", None

        now = datetime.utcnow()
        await col.update_one(
            {"ticket_id": ticket_id},
            {"$set": {
                "status":     Ticket.STATUS_FECHADO,
                "closed_at":  now,
                "updated_at": now,
            }}
        )
        ticket.status    = Ticket.STATUS_FECHADO
        ticket.closed_at = now
        ticket.updated_at = now
        return True, "", ticket

    # ─────────────────────────────────────────────
    # Concluir ticket (suporte/ADM)
    # ─────────────────────────────────────────────

    async def resolve_ticket(
        self,
        ticket_id: str,
        atendente_id: str,
        guild_id: int,
        is_admin: bool = False,
    ) -> tuple[bool, str, Optional[Ticket]]:
        col = db.get_collection("tickets")
        doc = await col.find_one({"ticket_id": ticket_id, "guild_id": guild_id})
        if not doc:
            return False, "Chamado não encontrado.", None

        ticket = Ticket.from_dict(doc)

        if ticket.status != Ticket.STATUS_PENDENTE:
            return False, f"Chamado precisa estar `pendente` para ser concluído. Status atual: `{ticket.status}`.", None

        if not is_admin and ticket.atendente_id != str(atendente_id):
            return False, "Apenas o atendente responsável pode concluir este chamado.", None

        now = datetime.utcnow()
        await col.update_one(
            {"ticket_id": ticket_id},
            {"$set": {
                "status":      Ticket.STATUS_RESOLVIDO,
                "resolved_at": now,
                "updated_at":  now,
            }}
        )
        ticket.status      = Ticket.STATUS_RESOLVIDO
        ticket.resolved_at = now
        ticket.updated_at  = now
        return True, "", ticket

    # ─────────────────────────────────────────────
    # Salvar card_message_id
    # ─────────────────────────────────────────────

    async def save_card_message_id(self, ticket_id: str, message_id: int):
        await db.get_collection("tickets").update_one(
            {"ticket_id": ticket_id},
            {"$set": {"card_message_id": message_id, "updated_at": datetime.utcnow()}}
        )

    # ─────────────────────────────────────────────
    # Buscar tickets (histórico do membro)
    # ─────────────────────────────────────────────

    async def get_user_tickets(self, discord_id: str, guild_id: int) -> List[Ticket]:
        col  = db.get_collection("tickets")
        docs = await col.find(
            {"discord_id": str(discord_id), "guild_id": guild_id}
        ).sort("created_at", -1).to_list(length=20)
        return [Ticket.from_dict(d) for d in docs]

    async def get_ticket(self, ticket_id: str, guild_id: int) -> Optional[Ticket]:
        doc = await db.get_collection("tickets").find_one(
            {"ticket_id": ticket_id, "guild_id": guild_id}
        )
        return Ticket.from_dict(doc) if doc else None


ticket_service = TicketService()
