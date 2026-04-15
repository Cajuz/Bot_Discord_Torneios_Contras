"""
Funcionalidades:
  • Cadastrar / remover influencer vinculando invite
  • Rastrear membros trazidos por cada influencer
  • Calcular comissão (Opção A — valor fixo por membro)
  • Validar links de redes sociais
  • Ranking via aggregation pipeline (sem N+1 queries)
"""
from __future__ import annotations
import re
from typing import Optional
from urllib.parse import urlparse

from config.database import db
from utils.datetime_utils import utcnow
from utils.logger import logger


# ─────────────────────────────────────────────
# Validação de links
# ─────────────────────────────────────────────

URL_PATTERN = re.compile(
    r"^https?://"
    r"(?:[a-zA-Z0-9\-]+\.)+[a-zA-Z]{2,}"
    r"(?:/[^\s]*)?$"
)

ALLOWED_PLATFORMS = {
    "youtube.com", "youtu.be",
    "instagram.com", "tiktok.com",
    "twitch.tv", "twitter.com", "x.com",
    "kick.com", "facebook.com",
}


def validate_influencer_link(url: str) -> tuple[bool, str]:
    """
    Valida URL de influencer.
    Retorna (True, url_normalizada) ou (False, mensagem_de_erro).
    """
    url = url.strip()

    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    if not URL_PATTERN.match(url):
        return False, "URL inválida. Use um link completo (ex: https://instagram.com/seu_perfil)"

    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        if domain not in ALLOWED_PLATFORMS:
            platforms = ", ".join(sorted(ALLOWED_PLATFORMS))
            return False, f"Plataforma não suportada. Permitidas: {platforms}"
    except Exception:
        return False, "Erro ao validar URL."

    return True, url


# ─────────────────────────────────────────────
# Service
# ─────────────────────────────────────────────

class InfluencerService:

    COLLECTION   = "influencers"
    INVITES_COLL = "invite_joins"
    MATCHES_COLL = "matches"

    async def add_influencer(
        self,
        discord_id: str,
        username: str,
        invite_code: str,
        link: str = "",
        commission_per_member: float = 2.0,
    ) -> tuple[bool, str, dict]:
        """
        Cadastra influencer com validação de link.
        Retorna (sucesso, mensagem, documento).
        """
        if link:
            ok, result = validate_influencer_link(link)
            if not ok:
                return False, result, {}
            link = result

        doc = {
            "discord_id":            discord_id,
            "username":              username,
            "invite_code":           invite_code,
            "link":                  link,
            "commission_per_member": commission_per_member,
            "total_earned":          0.0,
            "is_active":             True,
            "created_at":            utcnow(),
        }
        await db.get_collection(self.COLLECTION).update_one(
            {"discord_id": discord_id},
            {"$set": doc},
            upsert=True,
        )
        return True, "Influencer cadastrado com sucesso!", doc

    async def update_link(self, discord_id: str, new_link: str) -> tuple[bool, str]:
        """Atualiza link de um influencer com validação."""
        ok, result = validate_influencer_link(new_link)
        if not ok:
            return False, result
        await db.get_collection(self.COLLECTION).update_one(
            {"discord_id": discord_id},
            {"$set": {"link": result, "updated_at": utcnow()}}
        )
        return True, f"Link atualizado: {result}"

    async def remove_influencer(self, discord_id: str) -> bool:
        result = await db.get_collection(self.COLLECTION).update_one(
            {"discord_id": discord_id},
            {"$set": {"is_active": False, "removed_at": utcnow()}}
        )
        return result.modified_count > 0

    async def get_influencer(self, discord_id: str) -> Optional[dict]:
        return await db.get_collection(self.COLLECTION).find_one({"discord_id": discord_id})

    async def get_all_active(self) -> list[dict]:
        return await db.get_collection(self.COLLECTION).find({"is_active": True}).to_list(None)

    async def get_members_brought(self, discord_id: str, guild_id: str) -> list[dict]:
        """Retorna membros trazidos por este influencer via invite_joins."""
        influencer = await self.get_influencer(discord_id)
        if not influencer:
            return []
        invite_code = influencer.get("invite_code")
        return await db.get_collection(self.INVITES_COLL).find({
            "guild_id":    guild_id,
            "invite_code": invite_code,
        }).to_list(None)

    async def get_stats(self, discord_id: str, guild_id: str) -> dict:
        influencer = await self.get_influencer(discord_id)
        if not influencer:
            return {}

        members    = await self.get_members_brought(discord_id, guild_id)
        member_ids = [m["member_id"] for m in members]

        matches_col   = db.get_collection(self.MATCHES_COLL)
        total_matches = 0
        total_wagered = 0.0
        for mid in member_ids:
            total_matches += await matches_col.count_documents({
                "player_ids": mid,
                "status":     "finalizado"
            })
            agg = await matches_col.aggregate([
                {"$match": {"player_ids": mid, "status": "finalizado"}},
                {"$group": {"_id": None, "total": {"$sum": "$bet_value"}}}
            ]).to_list(1)
            if agg:
                total_wagered += agg[0].get("total", 0.0)

        commission = len(member_ids) * influencer.get("commission_per_member", 2.0)

        return {
            "influencer":            influencer,
            "total_members_brought": len(member_ids),
            "members":               member_ids,
            "total_matches_played":  total_matches,
            "total_wagered":         total_wagered,
            "commission_due":        commission,
        }

    async def get_ranking(self, guild_id: str, limit: int = 10) -> list[dict]:
        """
        Usa aggregation pipeline para evitar N+1 queries.
        """
        pipeline = [
            {"$match": {"is_active": True}},
            {"$lookup": {
                "from":       self.INVITES_COLL,
                "localField": "invite_code",
                "foreignField": "invite_code",
                "as":         "members",
                "pipeline":   [{"$match": {"guild_id": guild_id}}]
            }},
            {"$addFields": {"total_members": {"$size": "$members"}}},
            {"$sort":   {"total_members": -1}},
            {"$limit":  limit},
            {"$project": {
                "discord_id": 1, "username": 1, "link": 1,
                "commission_per_member": 1, "total_members": 1,
                "commission": {
                    "$multiply": ["$total_members", "$commission_per_member"]
                }
            }}
        ]
        return await db.get_collection(self.COLLECTION).aggregate(pipeline).to_list(limit)


influencer_service = InfluencerService()
