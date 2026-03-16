"""
MatchCog — Comandos de partidas.
Registra também os comandos de texto da match_thread_view.
"""
import discord
from discord.ext import commands
from discord import app_commands
from utils.logger import logger
from utils.datetime_utils import utcnow

THEME_COLOR = 0xFFD54F


class MatchCog(commands.Cog, name="Partidas"):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        try:
            from services.analise_fila import analise_fila_service
            self.analise_fila = analise_fila_service
            self.analise_fila.bot = bot
        except Exception:
            self.analise_fila = None

    # ── !cancelar ──────────────────────────────────────────────
    @commands.command(name="cancelar")
    async def cancelar(self, ctx: commands.Context):
        from services.match_queue_service import match_queue_service
        success, msg = await match_queue_service.cancel_match_for_user(str(ctx.author.id))
        embed = discord.Embed(description=msg, color=THEME_COLOR if success else 0xE74C3C)
        await ctx.reply(embed=embed)

    # ── Comandos mediador dentro de thread ──────────────────────
    @commands.command(name="menu_partida")
    async def menu_partida(self, ctx: commands.Context):
        from views.match_thread_view import cmd_menu_partida
        await cmd_menu_partida(ctx)

    @commands.command(name="confirmar_pagamento")
    async def confirmar_pagamento(self, ctx: commands.Context):
        from views.match_thread_view import cmd_confirmar_pagamento
        await cmd_confirmar_pagamento(ctx)

    @commands.command(name="iniciar_partida")
    async def iniciar_partida(self, ctx: commands.Context):
        from views.match_thread_view import cmd_iniciar_partida
        await cmd_iniciar_partida(ctx)

    @commands.command(name="winner_team")
    async def winner_team(self, ctx: commands.Context, team: str = ""):
        from views.match_thread_view import cmd_winner_team
        await cmd_winner_team(ctx, team)

    @commands.command(name="prize")
    async def prize(self, ctx: commands.Context):
        from views.match_thread_view import cmd_prize
        await cmd_prize(ctx)

    @commands.command(name="cancelar_match")
    async def cancelar_match(self, ctx: commands.Context, *, reason: str = None):
        from views.match_thread_view import cmd_cancelar_match
        await cmd_cancelar_match(ctx, reason)

    # ── /perfil ─────────────────────────────────────────────────
    @app_commands.command(name="perfil", description="Suas estatísticas de partidas")
    async def perfil(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        from config.database import db
        user_doc = await db.get_collection("users").find_one({"discord_id": str(interaction.user.id)})
        col      = db.get_collection("matches")
        total = await col.count_documents({"player_ids": str(interaction.user.id)})
        wins  = await col.count_documents({"player_ids": str(interaction.user.id), "winner_id": str(interaction.user.id)})
        wr = f"{(wins/total*100):.1f}%" if total else "N/A"
        embed = discord.Embed(title=f"Perfil — {interaction.user.display_name}", color=THEME_COLOR)
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.add_field(name="Partidas",  value=f"`{total}`", inline=True)
        embed.add_field(name="Vitórias",  value=f"`{wins}`",  inline=True)
        embed.add_field(name="Win Rate",  value=f"`{wr}`",    inline=True)
        if user_doc:
            last = user_doc.get("last_played_at")
            embed.add_field(
                name="Última Partida",
                value=last.strftime("%d/%m/%Y %H:%M") if last else "N/A",
                inline=False
            )
        await interaction.followup.send(embed=embed, ephemeral=True)

    # ── /solicitar_analise ─────────────────────────────────────
    @app_commands.command(name="solicitar_analise", description="Solicita análise de suspeita de hack")
    @app_commands.describe(match_id="ID da partida suspeita", motivo="Comportamento suspeito", evidencia="Link de vídeo/imagem (opcional)")
    async def solicitar_analise(
        self, interaction: discord.Interaction,
        match_id: str, motivo: str, evidencia: str = ""
    ):
        await interaction.response.defer(ephemeral=True)
        try:
            from config.database import db
            from config.channels_config import ChannelsConfig
            case_id = f"CASE-{match_id}-{str(interaction.user.id)[-4:]}"
            doc = {
                "case_id": case_id, "reporter_id": str(interaction.user.id),
                "reporter_name": interaction.user.name, "match_id": match_id,
                "motivo": motivo, "evidencia_url": evidencia,
                "analyst_id": None, "status": "aguardando_analise",
                "decision_reason": None, "created_at": utcnow(), "closed_at": None,
            }
            await db.get_collection("analysis_cases").insert_one(doc)
            fila_ch = discord.utils.get(
                interaction.guild.text_channels,
                name=getattr(ChannelsConfig, "ANALYST_QUEUE_CHANNEL", "fila-analistas")
            )
            if fila_ch:
                from views.analyst_views import build_case_embed, AnalystCaseView
                embed = build_case_embed(doc)
                view  = AnalystCaseView(case_id=case_id)
                await fila_ch.send(embed=embed, view=view)
            await interaction.followup.send(
                f"✅ Caso `{case_id}` enviado para análise. Aguarde resultado por DM.", ephemeral=True
            )
        except Exception as e:
            logger.error(f"[solicitar_analise] {e}")
            await interaction.followup.send("Erro ao criar solicitação.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(MatchCog(bot))
