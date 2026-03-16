"""
InviteCog — Invite Tracker (F1) e Rate Limit Monitor (F2).
"""
from __future__ import annotations
import discord
from discord.ext import commands
from discord import app_commands
from utils.logger import logger
from utils.datetime_utils import utcnow
from services.invite_tracker_service import invite_tracker_service
from services.rate_limit_monitor_service import rate_limit_monitor
from utils.retry import on_rate_limit

THEME_COLOR = 0xFFD54F


class InviteCog(commands.Cog, name="Convites"):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        invite_tracker_service.bot = bot
        rate_limit_monitor.bot     = bot
        on_rate_limit(rate_limit_monitor.on_rate_limit_event)
        if not rate_limit_monitor.daily_summary.is_running():
            rate_limit_monitor.daily_summary.start()

    @commands.Cog.listener()
    async def on_ready(self):
        for guild in self.bot.guilds:
            await invite_tracker_service.cache_guild_invites(guild)

    @commands.Cog.listener()
    async def on_invite_create(self, invite: discord.Invite):
        if invite.guild:
            cache = invite_tracker_service._cache.setdefault(invite.guild.id, {})
            cache[invite.code] = invite.uses

    @commands.Cog.listener()
    async def on_invite_delete(self, invite: discord.Invite):
        if invite.guild:
            invite_tracker_service._cache.get(invite.guild.id, {}).pop(invite.code, None)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        invite = await invite_tracker_service.find_used_invite(member.guild)
        await invite_tracker_service.register_join(member, invite)
        await invite_tracker_service.post_join_log(member, invite)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        from config.channels_config import ChannelsConfig
        ch_name = getattr(ChannelsConfig, "INVITES_CHANNEL", "convites")
        ch = discord.utils.get(member.guild.text_channels, name=ch_name)
        if not ch:
            return
        embed = discord.Embed(
            description=f"{member.mention} **{member.name}** saiu do servidor.",
            color=0x95A5A6
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"ID: {member.id} • {utcnow().strftime('%d/%m/%Y %H:%M')} UTC")
        await ch.send(embed=embed)

    @app_commands.command(name="convites", description="Veja seus convites ou de outro membro")
    @app_commands.describe(membro="Membro a consultar")
    async def convites(self, interaction: discord.Interaction, membro: discord.Member = None):
        await interaction.response.defer(ephemeral=True)
        target = membro or interaction.user
        stats  = await invite_tracker_service.get_inviter_stats(str(target.id), str(interaction.guild_id))
        embed  = discord.Embed(title=f"Convites — {target.display_name}", color=THEME_COLOR)
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="Total", value=f"`{stats.get('total_invited', 0)}`", inline=True)
        last = stats.get("last_invited_at")
        embed.add_field(
            name="Último convite",
            value=f"<t:{int(last.timestamp())}:R>" if last else "`Nenhum`",
            inline=True
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="top_convites", description="Ranking dos membros que mais convidaram")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def top_convites(self, interaction: discord.Interaction):
        await interaction.response.defer()
        top = await invite_tracker_service.get_top_inviters(str(interaction.guild_id), limit=10)
        embed = discord.Embed(title="Ranking de Convites", color=THEME_COLOR)
        if not top:
            embed.description = "Nenhum dado registrado ainda."
        else:
            medals = ["🥇", "🥈", "🥉"]
            lines  = [
                f"{medals[i] if i < 3 else f'`{i+1}.`'} **{doc['username']}** — `{doc['total_invited']}` convites"
                for i, doc in enumerate(top)
            ]
            embed.description = "\n".join(lines)
        embed.set_footer(text=f"Atualizado em {utcnow().strftime('%d/%m/%Y %H:%M')} UTC")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="ratelimit_stats", description="Estatísticas de rate limit")
    @app_commands.describe(horas="Período em horas (padrão: 24)")
    @app_commands.checks.has_permissions(administrator=True)
    async def ratelimit_stats(self, interaction: discord.Interaction, horas: int = 24):
        await interaction.response.defer(ephemeral=True)
        stats = await rate_limit_monitor.get_stats(hours=horas)
        embed = discord.Embed(
            title=f"Rate Limits — Últimas {horas}h",
            color=THEME_COLOR if stats["total"] < 10 else 0xE74C3C
        )
        embed.add_field(name="Total", value=f"`{stats['total']}`", inline=True)
        if stats["top_endpoints"]:
            lines = [f"`{e['_id']}` — {e['total']}x" for e in stats["top_endpoints"]]
            embed.add_field(name="Top endpoints", value="\n".join(lines), inline=False)
        else:
            embed.add_field(name="Status", value="Nenhum rate limit no período.", inline=False)
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(InviteCog(bot))
