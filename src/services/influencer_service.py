"""
Funcionalidades:
  • Cadastrar / remover influencer vinculando invite
  • Rastrear membros trazidos por cada influencer
  • Calcular comissão (Opção A — valor fixo por membro)
"""
from __future__ import annotations
from typing import Optional

from config.database import db
from utils.datetime_utils import utcnow
from utils.logger import logger


class InfluencerService:

    COLLECTION   = "influencers"
    INVITES_COLL = "invite_joins"   # collection unificada com invite_tracker_service
    MATCHES_COLL = "matches"

    async def add_influencer(
        self,
        discord_id: str,
        username: str,
        invite_code: str,
        commission_per_member: float = 2.0,
    ) -> dict:
        doc = {
            "discord_id":            discord_id,
            "username":              username,
            "invite_code":           invite_code,
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
        return doc

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
        all_inf = await self.get_all_active()
        rows    = []
        for inf in all_inf:
            members    = await self.get_members_brought(inf["discord_id"], guild_id)
            commission = len(members) * inf.get("commission_per_member", 2.0)
            rows.append({
                "discord_id":    inf["discord_id"],
                "username":      inf.get("username", "?"),
                "total_members": len(members),
                "commission":    commission,
            })
        rows.sort(key=lambda x: x["total_members"], reverse=True)
        return rows[:limit]


influencer_service = InfluencerService()