"""
InviteTrackerService
Rastreia convites do servidor: quem entrou, por qual link, quem convidou.
Vincula automaticamente ao influencer quando o invite pertence a um.
"""
from __future__ import annotations
import discord
from discord.ext import commands
from typing import Optional
from utils.logger import logger
from utils.datetime_utils import utcnow

# Collection unificada — usada por invite_tracker E influencer_service
INVITE_JOINS_COLLECTION = "invite_joins"


class InviteTrackerService:

    def __init__(self):
        self.bot: commands.Bot | None = None
        self._cache: dict[int, dict[str, int]] = {}

    async def cache_guild_invites(self, guild: discord.Guild):
        try:
            invites = await guild.invites()
            self._cache[guild.id] = {inv.code: inv.uses for inv in invites}
            logger.info(f"[InviteTracker] {len(invites)} invites cacheados em {guild.name}")
        except discord.Forbidden:
            logger.warning(f"[InviteTracker] Sem permissão para listar invites em {guild.name}")
        except Exception as e:
            logger.error(f"[InviteTracker] Erro ao cachear invites: {e}")

    async def find_used_invite(self, guild: discord.Guild) -> Optional[discord.Invite]:
        try:
            current_invites = await guild.invites()
            cached = self._cache.get(guild.id, {})
            used = None
            for inv in current_invites:
                if inv.uses > cached.get(inv.code, 0):
                    used = inv
                    break
            self._cache[guild.id] = {inv.code: inv.uses for inv in current_invites}
            return used
        except discord.Forbidden:
            logger.warning(f"[InviteTracker] Sem permissão para listar invites em {guild.name}")
            return None
        except Exception as e:
            logger.error(f"[InviteTracker] Erro ao detectar invite: {e}")
            return None

    async def register_join(self, member: discord.Member, invite: Optional[discord.Invite]):
        """Salva evento de entrada. Vincula ao influencer se o invite pertencer a um."""
        from config.database import db

        invite_code = invite.code if invite else None

        # Verifica se o invite pertence a um influencer
        influencer_id = None
        if invite_code:
            inf_doc = await db.get_collection("influencers").find_one(
                {"invite_code": invite_code, "is_active": True}
            )
            if inf_doc:
                influencer_id = inf_doc.get("discord_id")

        doc = {
            "member_id":     str(member.id),
            "member_name":   member.name,
            "guild_id":      str(member.guild.id),
            "invite_code":   invite_code,
            "inviter_id":    str(invite.inviter.id) if invite and invite.inviter else None,
            "inviter_name":  invite.inviter.name    if invite and invite.inviter else None,
            "invite_uses":   invite.uses            if invite else None,
            "influencer_id": influencer_id,
            "joined_at":     utcnow(),
        }

        # Salva na collection unificada
        await db.get_collection(INVITE_JOINS_COLLECTION).insert_one(doc)

        # Atualiza stats do inviter
        if invite and invite.inviter:
            await db.get_collection("invite_stats").update_one(
                {"discord_id": str(invite.inviter.id), "guild_id": str(member.guild.id)},
                {
                    "$inc": {"total_invited": 1},
                    "$set": {
                        "username":        invite.inviter.name,
                        "last_invited_at": utcnow(),
                    },
                    "$setOnInsert": {"created_at": utcnow()},
                },
                upsert=True
            )

        # Preenche influencer_id e referred_by no documento do user
        if influencer_id:
            await db.get_collection("users").update_one(
                {"discord_id": str(member.id)},
                {"$set": {
                    "influencer_id": influencer_id,
                    "referred_by":   invite_code,
                    "updated_at":    utcnow(),
                }}
            )
            logger.info(f"[InviteTracker] {member.name} vinculado ao influencer {influencer_id}")

    async def post_join_log(self, member: discord.Member, invite: Optional[discord.Invite]):
        from services.channel_service import INVITE_CHANNEL_NAME
        channel = discord.utils.get(member.guild.text_channels, name=INVITE_CHANNEL_NAME)
        if not channel:
            return

        embed = discord.Embed(title="Novo Membro", color=0xFFD54F)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="Membro",   value=member.mention, inline=True)
        embed.add_field(
            name="Conta em",
            value=f"<t:{int(member.created_at.timestamp())}:D>",
            inline=True
        )

        if invite:
            from config.database import db
            inf_doc = await db.get_collection("influencers").find_one(
                {"invite_code": invite.code, "is_active": True}
            )
            inviter_mention = invite.inviter.mention if invite.inviter else "`Desconhecido`"
            embed.add_field(name="Invite",        value=f"`{invite.code}`", inline=True)
            embed.add_field(name="Convidado por", value=inviter_mention,    inline=True)
            embed.add_field(name="Usos do link",  value=f"`{invite.uses}`", inline=True)
            if inf_doc:
                embed.add_field(
                    name="Influencer",
                    value=f"<@{inf_doc['discord_id']}>",
                    inline=True
                )
        else:
            embed.add_field(name="Invite", value="`Não identificado`", inline=True)

        embed.set_footer(text=f"ID: {member.id} • {utcnow().strftime('%d/%m/%Y %H:%M')} UTC")
        await channel.send(embed=embed)

    async def get_inviter_stats(self, discord_id: str, guild_id: str) -> dict:
        from config.database import db
        doc = await db.get_collection("invite_stats").find_one(
            {"discord_id": discord_id, "guild_id": guild_id}
        )
        return doc or {"total_invited": 0}

    async def get_top_inviters(self, guild_id: str, limit: int = 10) -> list[dict]:
        from config.database import db
        return await db.get_collection("invite_stats").find(
            {"guild_id": guild_id}
        ).sort("total_invited", -1).limit(limit).to_list(limit)


invite_tracker_service = InviteTrackerService()