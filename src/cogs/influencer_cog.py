"""
influencer_cog.py — F11: Controle de Influencers.

Comandos:
  /influencer add   — cadastra influencer
  /influencer remove — remove influencer
  /influencer stats  — stats do influencer
  /influencer faturamento — faturamento individual
  /influencer ranking — ranking geral (Admin)
"""
from __future__ import annotations
import discord
from discord.ext import commands
from discord import app_commands
from utils.logger import logger
from utils.datetime_utils import utcnow

THEME_COLOR = 0xFFD54F
INFLUENCER_ROLE = "Influencer"


class InfluencerGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="influencer", description="Gestão de influencers")

    @app_commands.command(name="add", description="Cadastra um influencer")
    @app_commands.describe(
        membro="Membro do Discord",
        invite_code="Código do invite (ex: abc123)",
        comissao="Comissão por membro (R$, padrão 2.00)"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def add(
        self,
        interaction: discord.Interaction,
        membro: discord.Member,
        invite_code: str,
        comissao: float = 2.00,
    ):
        await interaction.response.defer(ephemeral=True)
        from services.influencer_service import influencer_service

        await influencer_service.add_influencer(
            discord_id=str(membro.id),
            username=membro.name,
            invite_code=invite_code,
            commission_per_member=comissao,
        )

        # Atribui cargo Influencer
        role = discord.utils.get(interaction.guild.roles, name=INFLUENCER_ROLE)
        if role and role not in membro.roles:
            try:
                await membro.add_roles(role, reason="Cadastrado como influencer")
            except discord.Forbidden:
                pass

        embed = discord.Embed(title="Influencer Cadastrado", color=THEME_COLOR)
        embed.add_field(name="Membro",   value=membro.mention,       inline=True)
        embed.add_field(name="Invite",   value=f"`{invite_code}`",    inline=True)
        embed.add_field(name="Comissão", value=f"R$ {comissao:.2f} por membro", inline=False)
        embed.set_footer(text=utcnow().strftime("%d/%m/%Y %H:%M UTC"))
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="remove", description="Remove um influencer")
    @app_commands.describe(membro="Membro a remover")
    @app_commands.checks.has_permissions(administrator=True)
    async def remove(self, interaction: discord.Interaction, membro: discord.Member):
        await interaction.response.defer(ephemeral=True)
        from services.influencer_service import influencer_service

        ok = await influencer_service.remove_influencer(str(membro.id))

        # Remove cargo
        role = discord.utils.get(interaction.guild.roles, name=INFLUENCER_ROLE)
        if role and role in membro.roles:
            try:
                await membro.remove_roles(role, reason="Removido como influencer")
            except discord.Forbidden:
                pass

        if ok:
            await interaction.followup.send(f"✅ {membro.mention} removido como influencer.", ephemeral=True)
        else:
            await interaction.followup.send("Influencer não encontrado.", ephemeral=True)

    @app_commands.command(name="stats", description="Estatísticas de um influencer")
    @app_commands.describe(membro="Influencer a consultar (Admin) ou deixe vazio para ver o seu")
    async def stats(self, interaction: discord.Interaction, membro: discord.Member = None):
        await interaction.response.defer(ephemeral=True)
        from services.influencer_service import influencer_service

        target = membro or interaction.user
        # Não-admin só pode ver o próprio
        if membro and membro.id != interaction.user.id:
            if not interaction.user.guild_permissions.administrator:
                await interaction.followup.send("Apenas administradores podem ver stats de outros.", ephemeral=True)
                return

        stats = await influencer_service.get_stats(str(target.id), str(interaction.guild_id))
        if not stats:
            await interaction.followup.send(f"{target.mention} não é um influencer cadastrado.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"Stats — {target.display_name}",
            color=THEME_COLOR
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        inf = stats["influencer"]
        embed.add_field(name="Invite",       value=f"`{inf.get('invite_code','—')}`",         inline=True)
        embed.add_field(name="Membros trazidos", value=f"`{stats['total_members_brought']}`",  inline=True)
        embed.add_field(name="Partidas deles",   value=f"`{stats['total_matches_played']}`",   inline=True)
        embed.add_field(name="Volume apostado",  value=f"R$ {stats['total_wagered']:.2f}",     inline=True)
        embed.add_field(name="Comissão devida",  value=f"R$ {stats['commission_due']:.2f}",    inline=True)
        embed.set_footer(text=utcnow().strftime("%d/%m/%Y %H:%M UTC"))
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="faturamento", description="Relatório de comissão de um influencer")
    @app_commands.describe(membro="Influencer (Admin) ou vazio para ver o seu")
    async def faturamento(self, interaction: discord.Interaction, membro: discord.Member = None):
        await interaction.response.defer(ephemeral=True)
        from services.influencer_service import influencer_service

        target = membro or interaction.user
        if membro and membro.id != interaction.user.id:
            if not interaction.user.guild_permissions.administrator:
                await interaction.followup.send("Apenas administradores podem ver faturamento de outros.", ephemeral=True)
                return

        stats = await influencer_service.get_stats(str(target.id), str(interaction.guild_id))
        if not stats:
            await interaction.followup.send(f"{target.mention} não é um influencer cadastrado.", ephemeral=True)
            return

        inf = stats["influencer"]
        embed = discord.Embed(
            title=f"Faturamento — {target.display_name}",
            color=THEME_COLOR
        )
        embed.add_field(name="Membros trazidos",  value=f"`{stats['total_members_brought']}`",            inline=True)
        embed.add_field(name="Comissão/membro",   value=f"R$ {inf.get('commission_per_member',2):.2f}",   inline=True)
        embed.add_field(name="Total acumulado",   value=f"**R$ {stats['commission_due']:.2f}**",          inline=False)
        embed.add_field(name="Partidas deles",    value=f"`{stats['total_matches_played']}`",             inline=True)
        embed.add_field(name="Volume apostado",   value=f"R$ {stats['total_wagered']:.2f}",               inline=True)
        embed.set_footer(text=f"Cadastrado em {inf.get('created_at','').strftime('%d/%m/%Y') if inf.get('created_at') else '—'}")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="ranking", description="Ranking de todos os influencers")
    @app_commands.checks.has_permissions(administrator=True)
    async def ranking(self, interaction: discord.Interaction):
        await interaction.response.defer()
        from services.influencer_service import influencer_service

        rows = await influencer_service.get_ranking(str(interaction.guild_id), limit=10)
        embed = discord.Embed(title="Ranking de Influencers", color=THEME_COLOR)
        if not rows:
            embed.description = "Nenhum influencer cadastrado."
        else:
            medals = ["🥇", "🥈", "🥉"]
            lines  = [
                f"{medals[i] if i < 3 else f'`{i+1}.`'} **{r['username']}** — "
                f"`{r['total_members']}` membros | R$ {r['commission']:.2f}"
                for i, r in enumerate(rows)
            ]
            embed.description = "\n".join(lines)
        embed.set_footer(text=utcnow().strftime("%d/%m/%Y %H:%M UTC"))
        await interaction.followup.send(embed=embed)


class InfluencerCog(commands.Cog, name="Influencer"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.bot.tree.add_command(InfluencerGroup())


async def setup(bot: commands.Bot):
    await bot.add_cog(InfluencerCog(bot))
