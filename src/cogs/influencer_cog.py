from __future__ import annotations
import discord
from discord.ext import commands
from discord import app_commands
from utils.logger import logger
from utils.datetime_utils import utcnow

THEME_COLOR    = 0xFFD54F
THEME_LIVE     = 0xE91E63
INFLUENCER_ROLE = "Influencer"


class InfluencerGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="influencer", description="Gestão de influencers")

    # ── /influencer add ───────────────────────────────────────────────────
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
                "Não tenho permissão para criar convite nesse canal.", ephemeral=True)
            return
        except discord.HTTPException as e:
            await interaction.followup.send(f"Erro ao criar convite: {e}", ephemeral=True)
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
        embed.add_field(name="Membro",          value=membro.mention,        inline=True)
        embed.add_field(name="Canal do Invite", value=canal_convite.mention, inline=True)
        embed.add_field(name="Código",          value=f"`{invite.code}`",    inline=True)
        embed.add_field(name="Link do Convite", value=invite.url,            inline=False)
        embed.add_field(name="Comissão",        value=f"R$ {comissao:.2f} por membro", inline=True)
        embed.add_field(name="Máximo de usos",  value=("Ilimitado" if max_usos == 0 else f"`{max_usos}`"), inline=True)
        embed.add_field(name="Link social",     value=(saved.get("link") or "Não informado"), inline=False)
        embed.set_footer(text=utcnow().strftime("%d/%m/%Y %H:%M UTC"))
        await interaction.followup.send(embed=embed, ephemeral=True)

    # ── /influencer remove ─────────────────────────────────────────────────
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

    # ── /influencer stats ──────────────────────────────────────────────────
    @app_commands.command(name="stats", description="Estatísticas de um influencer")
    @app_commands.describe(membro="Influencer a consultar (Admin) ou deixe vazio para ver o seu")
    async def stats(self, interaction: discord.Interaction, membro: discord.Member = None):
        await interaction.response.defer(ephemeral=True)
        from services.influencer_service import influencer_service

        target = membro or interaction.user
        if membro and membro.id != interaction.user.id:
            if not interaction.user.guild_permissions.administrator:
                await interaction.followup.send(
                    "Apenas administradores podem ver stats de outros.", ephemeral=True)
                return

        stats = await influencer_service.get_stats(str(target.id), str(interaction.guild_id))
        if not stats:
            await interaction.followup.send(
                f"{target.mention} não é um influencer cadastrado.", ephemeral=True)
            return

        embed = discord.Embed(title=f"Stats — {target.display_name}", color=THEME_COLOR)
        embed.set_thumbnail(url=target.display_avatar.url)
        inf        = stats["influencer"]
        invite_url = inf.get("invite_url") or (
            f"https://discord.gg/{inf.get('invite_code')}" if inf.get("invite_code") else "—"
        )
        embed.add_field(name="Invite",           value=f"`{inf.get('invite_code','—')}`", inline=True)
        embed.add_field(name="Link do invite",   value=invite_url,                        inline=False)
        embed.add_field(name="Membros trazidos", value=f"`{stats['total_members_brought']}`", inline=True)
        embed.add_field(name="Partidas deles",   value=f"`{stats['total_matches_played']}`",  inline=True)
        embed.add_field(name="Volume apostado",  value=f"R$ {stats['total_wagered']:.2f}",    inline=True)
        embed.add_field(name="Comissão devida",  value=f"R$ {stats['commission_due']:.2f}",   inline=True)
        embed.set_footer(text=utcnow().strftime("%d/%m/%Y %H:%M UTC"))
        await interaction.followup.send(embed=embed, ephemeral=True)

    # ══════════════════════════════════════════════════════════════════════
    # MODO CONTRA — Sala Live
    # ══════════════════════════════════════════════════════════════════════

    # ── /influencer live_ativar ────────────────────────────────────────────
    @app_commands.command(name="live_ativar", description="[Influencer] Ativa sua sala no modo contra")
    @app_commands.describe(
        valor="Valor de entrada da sala (R$)",
        modo="Modo de jogo: 1v1 ou 2v2",
        regras="Regras customizadas da sala (opcional)",
    )
    @app_commands.checks.has_any_role("Influencer", "ADM")
    async def live_ativar(
        self,
        interaction: discord.Interaction,
        valor: float,
        modo: str = "1v1",
        regras: str = None,
    ):
        await interaction.response.defer(ephemeral=True)
        from services.influencer_live_room_service import influencer_live_room_service

        if modo not in ("1v1", "2v2"):
            await interaction.followup.send("Modo inválido. Use `1v1` ou `2v2`.", ephemeral=True)
            return

        if valor <= 0:
            await interaction.followup.send("O valor de entrada deve ser maior que zero.", ephemeral=True)
            return

        result = await influencer_live_room_service.ativar_sala(
            guild=interaction.guild,
            influencer=interaction.user,
            entry_value=valor,
            game_mode=modo,
            custom_rules=regras,
        )

        if not result["ok"]:
            await interaction.followup.send(f"❌ {result['msg']}", ephemeral=True)
            return

        room = result["room"]
        embed = discord.Embed(
            title="⚔️ Sala Contra Ativada!",
            description=(
                f"Sua sala foi aberta com sucesso.\n\n"
                f"Jogadores podem entrar em {result['channel'].mention} e clicar em **Jogar Contra**."
            ),
            color=THEME_LIVE,
        )
        embed.add_field(name="Modo",            value=f"`{room.game_mode}`",          inline=True)
        embed.add_field(name="Valor de Entrada", value=f"R$ `{room.entry_value:.2f}`", inline=True)
        embed.add_field(name="Regras",           value=(room.custom_rules or "Padrão do servidor"), inline=False)
        embed.set_footer(text=utcnow().strftime("%d/%m/%Y %H:%M UTC"))
        await interaction.followup.send(embed=embed, ephemeral=True)
        logger.info(f"[InfluencerLive] Sala ativada por {interaction.user.name} — {modo} R${valor:.2f}")

    # ── /influencer live_desativar ─────────────────────────────────────────
    @app_commands.command(name="live_desativar", description="[Influencer] Desativa sua sala no modo contra")
    @app_commands.checks.has_any_role("Influencer", "ADM")
    async def live_desativar(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        from services.influencer_live_room_service import influencer_live_room_service

        result = await influencer_live_room_service.desativar_sala(
            guild=interaction.guild,
            influencer=interaction.user,
        )

        if not result["ok"]:
            await interaction.followup.send(f"❌ {result['msg']}", ephemeral=True)
            return

        await interaction.followup.send(
            "✅ Sala desativada. O canal foi removido e a fila encerrada.", ephemeral=True)
        logger.info(f"[InfluencerLive] Sala desativada por {interaction.user.name}")

    # ── /influencer live_editar ────────────────────────────────────────────
    @app_commands.command(name="live_editar", description="[Influencer] Edita valor, regras ou modo da sala")
    @app_commands.describe(
        valor="Novo valor de entrada (R$) — deixe em branco para não alterar",
        modo="Novo modo de jogo: 1v1 ou 2v2 — deixe em branco para não alterar",
        regras="Novas regras da sala — deixe em branco para não alterar",
    )
    @app_commands.checks.has_any_role("Influencer", "ADM")
    async def live_editar(
        self,
        interaction: discord.Interaction,
        valor: float = None,
        modo: str = None,
        regras: str = None,
    ):
        await interaction.response.defer(ephemeral=True)
        from services.influencer_live_room_service import influencer_live_room_service

        if modo is not None and modo not in ("1v1", "2v2"):
            await interaction.followup.send("Modo inválido. Use `1v1` ou `2v2`.", ephemeral=True)
            return

        if valor is not None and valor <= 0:
            await interaction.followup.send("O valor de entrada deve ser maior que zero.", ephemeral=True)
            return

        result = await influencer_live_room_service.editar_sala(
            influencer_id=str(interaction.user.id),
            guild_id=str(interaction.guild_id),
            entry_value=valor,
            game_mode=modo,
            custom_rules=regras,
        )

        if not result["ok"]:
            await interaction.followup.send(f"❌ {result['msg']}", ephemeral=True)
            return

        room = result["room"]
        embed = discord.Embed(title="⚔️ Sala Atualizada", color=THEME_LIVE)
        embed.add_field(name="Modo",             value=f"`{room.game_mode}`",          inline=True)
        embed.add_field(name="Valor de Entrada", value=f"R$ `{room.entry_value:.2f}`", inline=True)
        embed.add_field(name="Regras",           value=(room.custom_rules or "Padrão do servidor"), inline=False)
        embed.set_footer(text=utcnow().strftime("%d/%m/%Y %H:%M UTC"))
        await interaction.followup.send(embed=embed, ephemeral=True)
        logger.info(f"[InfluencerLive] Sala editada por {interaction.user.name}")

    # ── /influencer live_fila ──────────────────────────────────────────────
    @app_commands.command(name="live_fila", description="[Influencer] Veja a fila atual da sua sala")
    @app_commands.checks.has_any_role("Influencer", "ADM")
    async def live_fila(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        from services.influencer_live_queue_service import influencer_live_queue_service

        result = await influencer_live_queue_service.get_fila(
            influencer_id=str(interaction.user.id),
            guild_id=str(interaction.guild_id),
        )

        if not result["ok"]:
            await interaction.followup.send(f"❌ {result['msg']}", ephemeral=True)
            return

        queue   = result["queue"]
        players = queue.players

        embed = discord.Embed(title="⚔️ Fila da Sala — Modo Contra", color=THEME_LIVE)
        embed.add_field(name="Total na fila", value=f"`{len(players)}`", inline=True)
        embed.add_field(name="Status",        value=f"`{queue.status}`", inline=True)

        if players:
            lines = [f"`{i+1}.` <@{pid}>" for i, pid in enumerate(players)]
            embed.add_field(name="Jogadores", value="\n".join(lines), inline=False)
        else:
            embed.add_field(name="Jogadores", value="Nenhum na fila.", inline=False)

        embed.set_footer(text=utcnow().strftime("%d/%m/%Y %H:%M UTC"))
        await interaction.followup.send(embed=embed, ephemeral=True)


class InfluencerCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.bot.tree.add_command(InfluencerGroup())


async def setup(bot: commands.Bot):
    await bot.add_cog(InfluencerCog(bot))