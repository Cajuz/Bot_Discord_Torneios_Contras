from __future__ import annotations
import re
from typing import Optional
from urllib.parse import urlparse

from config.database import db
from utils.datetime_utils import utcnow

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
    url = url.strip()
    if not url:
        return True, ""
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


class InfluencerService:
    COLLECTION = "influencers"
    INVITES_COLL = "invite_joins"
    MATCHES_COLL = "matches"
    USERS_COLL = "users"

    async def add_influencer(
        self,
        discord_id: str,
        username: str,
        invite_code: str,
        link: str = "",
        commission_per_member: float = 2.0,
    ) -> tuple[bool, str, dict]:
        if link:
            ok, result = validate_influencer_link(link)
            if not ok:
                return False, result, {}
            link = result

        doc = {
            "discord_id": discord_id,
            "username": username,
            "invite_code": invite_code,
            "invite_url": f"https://discord.gg/{invite_code}",
            "link": link,
            "commission_per_member": commission_per_member,
            "total_earned": 0.0,
            "is_active": True,
            "created_at": utcnow(),
            "updated_at": utcnow(),
        }
        await db.get_collection(self.COLLECTION).update_one(
            {"discord_id": discord_id},
            {"$set": doc},
            upsert=True,
        )
        return True, "Influencer cadastrado com sucesso!", doc

    async def remove_influencer(self, discord_id: str) -> bool:
        result = await db.get_collection(self.COLLECTION).update_one(
            {"discord_id": discord_id},
            {"$set": {"is_active": False, "removed_at": utcnow(), "updated_at": utcnow()}}
        )
        return result.modified_count > 0

    async def get_influencer(self, discord_id: str) -> Optional[dict]:
        return await db.get_collection(self.COLLECTION).find_one({"discord_id": discord_id})

    async def get_influencer_by_invite(self, invite_code: str) -> Optional[dict]:
        return await db.get_collection(self.COLLECTION).find_one({"invite_code": invite_code, "is_active": True})

    async def get_members_brought(self, discord_id: str, guild_id: str) -> list[dict]:
        influencer = await self.get_influencer(discord_id)
        if not influencer:
            return []
        return await db.get_collection(self.INVITES_COLL).find({
            "guild_id": guild_id,
            "invite_code": influencer.get("invite_code"),
        }).to_list(None)

    async def get_member_match_count(self, member_id: str) -> int:
        return await db.get_collection(self.MATCHES_COLL).count_documents({
            "player_ids": member_id,
            "status": "finalizado",
        })

    async def get_member_onboarding_status(self, member_id: str) -> str:
        user_doc = await db.get_collection(self.USERS_COLL).find_one({"discord_id": member_id})
        if not user_doc:
            return "pendente"
        if user_doc.get("has_accepted_rules") or user_doc.get("onboarding_result") == "aceito":
            return "concluído"
        return user_doc.get("onboarding_result") or "pendente"

    async def update_join_card_message(self, member_id: str, message_id: int | None, channel_id: int | None):
        await db.get_collection(self.INVITES_COLL).update_one(
            {"member_id": member_id},
            {"$set": {"log_message_id": message_id, "log_channel_id": channel_id, "updated_at": utcnow()}}
        )

    async def get_invite_card_data(self, member_id: str, guild_id: str) -> Optional[dict]:
        join_doc = await db.get_collection(self.INVITES_COLL).find_one({"member_id": member_id, "guild_id": guild_id})
        if not join_doc:
            return None
        influencer = await self.get_influencer_by_invite(join_doc.get("invite_code")) if join_doc.get("invite_code") else None
        return {
            "join_doc": join_doc,
            "influencer": influencer,
            "matches_count": await self.get_member_match_count(member_id),
            "onboarding_status": await self.get_member_onboarding_status(member_id),
        }

    async def get_stats(self, discord_id: str, guild_id: str) -> dict:
        influencer = await self.get_influencer(discord_id)
        if not influencer:
            return {}
        members = await self.get_members_brought(discord_id, guild_id)
        member_ids = [m["member_id"] for m in members]
        total_matches = 0
        total_wagered = 0.0
        matches_col = db.get_collection(self.MATCHES_COLL)
        for mid in member_ids:
            total_matches += await matches_col.count_documents({"player_ids": mid, "status": "finalizado"})
            agg = await matches_col.aggregate([
                {"$match": {"player_ids": mid, "status": "finalizado"}},
                {"$group": {"_id": None, "total": {"$sum": "$bet_value"}}}
            ]).to_list(1)
            if agg:
                total_wagered += agg[0].get("total", 0.0)
        return {
            "influencer": influencer,
            "total_members_brought": len(member_ids),
            "members": member_ids,
            "total_matches_played": total_matches,
            "total_wagered": total_wagered,
            "commission_due": len(member_ids) * influencer.get("commission_per_member", 2.0),
        }


influencer_service = InfluencerService()