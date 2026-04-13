# stats_service.py — Agrega estatísticas completas de um membro.
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
from config.database import db
from utils.datetime_utils import utcnow
from utils.logger import logger


@dataclass
class MemberStats:
    discord_id: str
    # Partidas
    total_partidas: int = 0
    partidas_ganhas: int = 0
    partidas_perdidas: int = 0
    partidas_canceladas: int = 0
    valor_apostado_total: float = 0.0
    valor_ganho_total: float = 0.0
    # Blacklist
    na_blacklist: bool = False
    blacklist_motivo: Optional[str] = None
    blacklist_data: Optional[str] = None
    blacklist_adicionado_por: Optional[str] = None
    # Contrato / mediador
    e_mediador: bool = False
    contrato_status: Optional[str] = None
    contrato_vence: Optional[str] = None
    pix_cadastrado: bool = False
    # Suporte
    tickets_abertos: int = 0
    tickets_fechados: int = 0
    # Spam/bloqueio
    spam_bloqueado: bool = False
    spam_motivo: Optional[str] = None
    # Meta
    win_rate: float = 0.0
    tags: list[str] = field(default_factory=list)


class StatsService:

    async def get(self, discord_id: str) -> MemberStats:
        """Retorna MemberStats completo para um discord_id."""
        stats = MemberStats(discord_id=discord_id)
        try:
            await self._fill_matches(stats)
            await self._fill_blacklist(stats)
            await self._fill_contract(stats)
            await self._fill_pix(stats)
            await self._fill_tickets(stats)
            await self._fill_user(stats)
            self._compute_derived(stats)
        except Exception as e:
            logger.error(f"[StatsService] get({discord_id}): {e}", exc_info=True)
        return stats

    # ──────────────────────────────────────────────
    # internos
    # ──────────────────────────────────────────────

    async def _fill_matches(self, s: MemberStats):
        col = db.get_collection("matches")
        pipeline = [
            {"$match": {
                "$or": [
                    {"team_blue": s.discord_id},
                    {"team_red": s.discord_id},
                    {"players": s.discord_id},
                ]
            }},
            {"$group": {
                "_id": None,
                "total":     {"$sum": 1},
                "ganhou":    {"$sum": {"$cond": [{"$eq": ["$winner_id", s.discord_id]}, 1, 0]}},
                "cancelado": {"$sum": {"$cond": [{"$eq": ["$status", "cancelled"]}, 1, 0]}},
                "apostado":  {"$sum": {"$ifNull": ["$bet_value", 0]}},
                "ganho":     {"$sum": {"$cond": [{"$eq": ["$winner_id", s.discord_id]},
                                                  {"$ifNull": ["$prize_value", 0]}, 0]}},
            }},
        ]
        async for doc in col.aggregate(pipeline):
            s.total_partidas      = doc.get("total", 0)
            s.partidas_ganhas     = doc.get("ganhou", 0)
            s.partidas_canceladas = doc.get("cancelado", 0)
            s.partidas_perdidas   = max(0, s.total_partidas - s.partidas_ganhas - s.partidas_canceladas)
            s.valor_apostado_total = doc.get("apostado", 0.0)
            s.valor_ganho_total    = doc.get("ganho", 0.0)

    async def _fill_blacklist(self, s: MemberStats):
        col = db.get_collection("blacklist")
        doc = await col.find_one({"discord_id": s.discord_id})
        if not doc:
            # fallback legado
            col2 = db.get_collection("exposed")
            doc  = await col2.find_one({"discord_id": s.discord_id})
        if doc:
            s.na_blacklist             = True
            s.blacklist_motivo         = doc.get("motivo") or doc.get("reason", "Não informado")
            s.blacklist_adicionado_por = doc.get("adicionado_por") or doc.get("added_by")
            data = doc.get("criado_em") or doc.get("created_at")
            if data:
                try:
                    s.blacklist_data = data.strftime("%d/%m/%Y") if hasattr(data, "strftime") else str(data)[:10]
                except Exception:
                    s.blacklist_data = str(data)[:10]

    async def _fill_contract(self, s: MemberStats):
        col = db.get_collection("mediator_contracts")
        doc = await col.find_one({"discord_id": s.discord_id}, sort=[("created_at", -1)])
        if doc:
            s.e_mediador      = True
            s.contrato_status = doc.get("status", "desconhecido")
            vence = doc.get("expires_at") or doc.get("vencimento")
            if vence:
                try:
                    s.contrato_vence = vence.strftime("%d/%m/%Y") if hasattr(vence, "strftime") else str(vence)[:10]
                except Exception:
                    s.contrato_vence = str(vence)[:10]

    async def _fill_pix(self, s: MemberStats):
        col = db.get_collection("mediator_pix")
        doc = await col.find_one({"discord_id": s.discord_id})
        s.pix_cadastrado = bool(doc and doc.get("pix_key"))

    async def _fill_tickets(self, s: MemberStats):
        col = db.get_collection("support_tickets")
        s.tickets_abertos  = await col.count_documents({"discord_id": s.discord_id, "status": "open"})
        s.tickets_fechados = await col.count_documents({"discord_id": s.discord_id, "status": "closed"})

    async def _fill_user(self, s: MemberStats):
        col = db.get_collection("users")
        doc = await col.find_one({"discord_id": s.discord_id})
        if doc:
            s.spam_bloqueado = doc.get("spam_blocked", False)
            s.spam_motivo    = doc.get("spam_block_reason")

    def _compute_derived(self, s: MemberStats):
        jogadas = s.partidas_ganhas + s.partidas_perdidas
        s.win_rate = round(s.partidas_ganhas / jogadas * 100, 1) if jogadas else 0.0
        if s.na_blacklist:
            s.tags.append("🚫 Blacklist")
        if s.spam_bloqueado:
            s.tags.append("🔇 Bloqueado")
        if s.e_mediador:
            s.tags.append("🎖️ Mediador")
        if s.pix_cadastrado:
            s.tags.append("💳 PIX ok")
        elif s.e_mediador:
            s.tags.append("⚠️ Sem PIX")


stats_service = StatsService()
