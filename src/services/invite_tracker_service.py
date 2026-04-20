from __future__ import annotations
import discord
from discord.ext import commands
from typing import Optional
from utils.logger import logger
from utils.datetime_utils import utcnow

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
        from config.database import db

        invite_code = invite.code if invite else None
        influencer_id = None
        if invite_code:
            inf_doc = await db.get_collection("influencers").find_one({"invite_code": invite_code, "is_active": True})
            if inf_doc:
                influencer_id = inf_doc.get("discord_id")

        doc = {
            "member_id": str(member.id),
            "member_name": member.name,
            "guild_id": str(member.guild.id),
            "invite_code": invite_code,
            "inviter_id": str(invite.inviter.id) if invite and invite.inviter else None,
            "inviter_name": invite.inviter.name if invite and invite.inviter else None,
            "invite_uses": invite.uses if invite else None,
            "influencer_id": influencer_id,
            "joined_at": utcnow(),
            "updated_at": utcnow(),
        }
        await db.get_collection(INVITE_JOINS_COLLECTION).insert_one(doc)

        if influencer_id:
            await db.get_collection("users").update_one(
                {"discord_id": str(member.id)},
                {"$set": {"influencer_id": influencer_id, "referred_by": invite_code, "updated_at": utcnow()}}
            )

    def _build_influencer_join_embed(self, member: discord.Member, invite: Optional[discord.Invite], influencer: Optional[dict], onboarding_status: str, matches_count: int) -> discord.Embed:
        embed = discord.Embed(title="Convite de Influencer", color=0xFFD54F)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="Convidado", value=member.mention, inline=True)
        embed.add_field(name="Influencer", value=(f"<@{influencer['discord_id']}>" if influencer else "Não identificado"), inline=True)
        embed.add_field(name="Invite", value=(f"`{invite.code}`" if invite else "`Não identificado`"), inline=True)
        embed.add_field(name="Onboarding", value=f"`{onboarding_status}`", inline=True)
        embed.add_field(name="Partidas até agora", value=f"`{matches_count}`", inline=True)
        if invite and invite.inviter:
            embed.add_field(name="Criado por", value=invite.inviter.mention, inline=True)
        embed.set_footer(text=f"ID: {member.id} • Atualizado em {utcnow().strftime('%d/%m/%Y %H:%M')} UTC")
        return embed

    async def post_join_log(self, member: discord.Member, invite: Optional[discord.Invite]):
        from services.channel_service import INVITE_CHANNEL_NAME
        from services.influencer_service import influencer_service
        from config.database import db

        channel = discord.utils.get(member.guild.text_channels, name=INVITE_CHANNEL_NAME)
        if not channel:
            return

        inf_doc = None
        if invite:
            inf_doc = await db.get_collection("influencers").find_one({"invite_code": invite.code, "is_active": True})

        if inf_doc:
            card_data = await influencer_service.get_invite_card_data(str(member.id), str(member.guild.id))
            embed = self._build_influencer_join_embed(
                member,
                invite,
                inf_doc,
                card_data.get("onboarding_status", "pendente") if card_data else "pendente",
                card_data.get("matches_count", 0) if card_data else 0,
            )
            sent = await channel.send(embed=embed)
            await influencer_service.update_join_card_message(str(member.id), sent.id, channel.id)
            return

        embed = discord.Embed(title="Novo Membro", color=0xFFD54F)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="Membro", value=member.mention, inline=True)
        embed.add_field(name="Invite", value=(f"`{invite.code}`" if invite else "`Não identificado`"), inline=True)
        embed.set_footer(text=f"ID: {member.id} • {utcnow().strftime('%d/%m/%Y %H:%M')} UTC")
        await channel.send(embed=embed)

    async def update_invite_card(self, guild: discord.Guild, member_id: str):
        from services.influencer_service import influencer_service

        card_data = await influencer_service.get_invite_card_data(member_id, str(guild.id))
        if not card_data or not card_data.get("influencer"):
            return False

        join_doc = card_data["join_doc"]
        channel = guild.get_channel(int(join_doc.get("log_channel_id", 0)))
        if not channel:
            return False

        try:
            message = await channel.fetch_message(int(join_doc.get("log_message_id", 0)))
        except Exception:
            return False

        member = guild.get_member(int(member_id)) or await guild.fetch_member(int(member_id))
        embed = self._build_influencer_join_embed(
            member,
            None,
            card_data.get("influencer"),
            card_data.get("onboarding_status", "pendente"),
            card_data.get("matches_count", 0),
        )
        await message.edit(embed=embed)
        return True


invite_tracker_service = InviteTrackerService()