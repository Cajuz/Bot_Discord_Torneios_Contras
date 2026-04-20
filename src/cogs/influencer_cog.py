from __future__ import annotations
import discord
from discord.ext import commands
from discord import app_commands
from utils.datetime_utils import utcnow

THEME_COLOR = 0xFFD54F
INFLUENCER_ROLE = "Influencer"


class InfluencerGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="influencer", description="Gestão de influencers")

    @app_commands.command(name="add", description="Cadastra um influencer e gera link de convite do Discord")
    @app_commands.describe(
        membro="Membro do Discord",
        canal_convite="Canal usado para gerar o link de convite",
        comissao="Comissão por membro (R$, padrão 2.00)",
        link="Link da rede social do influencer (opcional)",
        max_usos="Máximo de usos do convite (0 = ilimitado)"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def add(
        self,
        interaction: discord.Interaction,
        membro: discord.Member,
        canal_convite: discord.TextChannel,
        comissao: float = 2.00,
        link: str = "",
        max_usos: int = 0,
    ):
        await interaction.response.defer(ephemeral=True)
        from services.influencer_service import influencer_service

        try:
            invite = await canal_convite.create_invite(
                max_age=0,
                max_uses=max(0, max_usos),
                unique=True,
                reason=f"Invite criado para influencer {membro}"
            )
        except discord.Forbidden:
            await interaction.followup.send(
                "Não tenho permissão para criar convite nesse canal.",
                ephemeral=True,
            )
            return
        except discord.HTTPException as e:
            await interaction.followup.send(
                f"Erro ao criar convite: {e}",
                ephemeral=True,
            )
            return

        ok, msg, saved = await influencer_service.add_influencer(
            discord_id=str(membro.id),
            username=membro.name,
            invite_code=invite.code,
            link=link,
            commission_per_member=comissao,
        )

        if not ok:
            try:
                await invite.delete(reason="Rollback: falha ao cadastrar influencer")
            except Exception:
                pass
            await interaction.followup.send(msg, ephemeral=True)
            return

        role = discord.utils.get(interaction.guild.roles, name=INFLUENCER_ROLE)
        if role and role not in membro.roles:
            try:
                await membro.add_roles(role, reason="Cadastrado como influencer")
            except discord.Forbidden:
                pass

        embed = discord.Embed(title="Influencer Cadastrado", color=THEME_COLOR)
        embed.add_field(name="Membro", value=membro.mention, inline=True)
        embed.add_field(name="Canal do Invite", value=canal_convite.mention, inline=True)
        embed.add_field(name="Código", value=f"`{invite.code}`", inline=True)
        embed.add_field(name="Link do Convite", value=invite.url, inline=False)
        embed.add_field(name="Comissão", value=f"R$ {comissao:.2f} por membro", inline=True)
        embed.add_field(name="Máximo de usos", value=("Ilimitado" if max_usos == 0 else f"`{max_usos}`"), inline=True)
        embed.add_field(name="Link social", value=(saved.get("link") or "Não informado"), inline=False)
        embed.set_footer(text=utcnow().strftime("%d/%m/%Y %H:%M UTC"))
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="remove", description="Remove um influencer")
    @app_commands.describe(membro="Membro a remover")
    @app_commands.checks.has_permissions(administrator=True)
    async def remove(self, interaction: discord.Interaction, membro: discord.Member):
        await interaction.response.defer(ephemeral=True)
        from services.influencer_service import influencer_service

        ok = await influencer_service.remove_influencer(str(membro.id))

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
        if membro and membro.id != interaction.user.id:
            if not interaction.user.guild_permissions.administrator:
                await interaction.followup.send("Apenas administradores podem ver stats de outros.", ephemeral=True)
                return

        stats = await influencer_service.get_stats(str(target.id), str(interaction.guild_id))
        if not stats:
            await interaction.followup.send(f"{target.mention} não é um influencer cadastrado.", ephemeral=True)
            return

        embed = discord.Embed(title=f"Stats — {target.display_name}", color=THEME_COLOR)
        embed.set_thumbnail(url=target.display_avatar.url)
        inf = stats["influencer"]
        invite_url = inf.get("invite_url") or (f"https://discord.gg/{inf.get('invite_code')}" if inf.get("invite_code") else "—")
        embed.add_field(name="Invite", value=f"`{inf.get('invite_code','—')}`", inline=True)
        embed.add_field(name="Link do invite", value=invite_url, inline=False)
        embed.add_field(name="Membros trazidos", value=f"`{stats['total_members_brought']}`", inline=True)
        embed.add_field(name="Partidas deles", value=f"`{stats['total_matches_played']}`", inline=True)
        embed.add_field(name="Volume apostado", value=f"R$ {stats['total_wagered']:.2f}", inline=True)
        embed.add_field(name="Comissão devida", value=f"R$ {stats['commission_due']:.2f}", inline=True)
        embed.set_footer(text=utcnow().strftime("%d/%m/%Y %H:%M UTC"))
        await interaction.followup.send(embed=embed, ephemeral=True)


class InfluencerCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.bot.tree.add_command(InfluencerGroup())


async def setup(bot: commands.Bot):
    await bot.add_cog(InfluencerCog(bot))