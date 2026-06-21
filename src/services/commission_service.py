# src/services/commission_service.py
# Gerencia a configuração de comissão por servidor (guild), persistindo no MongoDB.
# Estrutura do documento (collection: server_commission_config):
# {
#   "guild_id": str,
#   "match": { "fixed_threshold": float, "fixed_fee": float, "pct": float },
#   "live":  { "fixed_threshold": float, "fixed_fee": float, "pct": float }
# }
from __future__ import annotations
from config.database import db
from utils.logger import logger
from utils.datetime_utils import utcnow

_COL = "server_commission_config"

# ── Defaults ─────────────────────────────────────────────────────────────────
DEFAULT_MATCH = {"fixed_threshold": 20.0, "fixed_fee": 2.0, "pct": 0.10}
DEFAULT_LIVE  = {"fixed_threshold": 20.0, "fixed_fee": 2.0, "pct": 0.10}


class CommissionService:

    # ── Leitura ───────────────────────────────────────────────────────────────

    async def get_config(self, guild_id: str) -> dict:
        """Retorna a config completa do servidor; preenche defaults se ausente."""
        doc = await db.get_collection(_COL).find_one({"guild_id": guild_id})
        if not doc:
            return {"guild_id": guild_id, "match": DEFAULT_MATCH.copy(), "live": DEFAULT_LIVE.copy()}
        return {
            "guild_id": guild_id,
            "match": doc.get("match", DEFAULT_MATCH.copy()),
            "live":  doc.get("live",  DEFAULT_LIVE.copy()),
        }

    async def get_match_config(self, guild_id: str) -> dict:
        cfg = await self.get_config(guild_id)
        return cfg["match"]

    async def get_live_config(self, guild_id: str) -> dict:
        cfg = await self.get_config(guild_id)
        return cfg["live"]

    # ── Cálculo ───────────────────────────────────────────────────────────────

    def calculate(self, bet_value: float, scheme: dict) -> float:
        """Retorna a taxa TOTAL (os dois jogadores) para um bet_value dado."""
        threshold = scheme.get("fixed_threshold", 20.0)
        if bet_value <= threshold:
            return scheme.get("fixed_fee", 2.0) * 2
        return round(bet_value * scheme.get("pct", 0.10) * 2, 2)

    def calculate_per_player(self, bet_value: float, scheme: dict) -> float:
        """Retorna a taxa POR JOGADOR."""
        threshold = scheme.get("fixed_threshold", 20.0)
        if bet_value <= threshold:
            return scheme.get("fixed_fee", 2.0)
        return round(bet_value * scheme.get("pct", 0.10), 2)

    # ── Escrita ───────────────────────────────────────────────────────────────

    async def update_match(self, guild_id: str, fixed_threshold: float, fixed_fee: float, pct: float) -> dict:
        new_scheme = {"fixed_threshold": fixed_threshold, "fixed_fee": fixed_fee, "pct": pct}
        await db.get_collection(_COL).update_one(
            {"guild_id": guild_id},
            {"$set": {"match": new_scheme, "updated_at": utcnow()}},
            upsert=True,
        )
        logger.info(f"[CommissionService] match config updated guild={guild_id} scheme={new_scheme}")
        return new_scheme

    async def update_live(self, guild_id: str, fixed_threshold: float, fixed_fee: float, pct: float) -> dict:
        new_scheme = {"fixed_threshold": fixed_threshold, "fixed_fee": fixed_fee, "pct": pct}
        await db.get_collection(_COL).update_one(
            {"guild_id": guild_id},
            {"$set": {"live": new_scheme, "updated_at": utcnow()}},
            upsert=True,
        )
        logger.info(f"[CommissionService] live config updated guild={guild_id} scheme={new_scheme}")
        return new_scheme

    async def reset_match(self, guild_id: str) -> dict:
        return await self.update_match(guild_id, **DEFAULT_MATCH)

    async def reset_live(self, guild_id: str) -> dict:
        return await self.update_live(guild_id, **DEFAULT_LIVE)


commission_service = CommissionService()
