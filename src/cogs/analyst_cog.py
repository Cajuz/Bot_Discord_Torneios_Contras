"""
AnalystCog — Comandos de analistas + gestão da blacklist no #exposed.
"""
from __future__ import annotations
import discord
from discord.ext import commands
from discord import app_commands

from utils.logger import logger
from utils.datetime_utils import utcnow
from services.channel_service import EXPOSED_CHANNEL_NAME, ANALYST_QUEUE_CHANNEL

THEME_COLOR = 0xFFD54F
DANGER      = 0xE74C3C


def _is_in_exposed(interaction: discord.Interaction) -> bool:
    return getattr(interaction.channel, "name", "") == EXPOSED_CHANNEL_NAME


def _valid_discord_id(value: str) -> bool:
    return value.strip().isdigit() and len(value.strip()) >= 10


# ─────────────────────────────────────────────────────────────


class AnalystCog(commands.Cog, name="Analista"):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── /assumir_caso ─────────────────────────────────────────────

    @app_commands.command(name="assumir_caso", description="Assume um caso de análise pelo ID")
    @app_commands.describe(case_id="ID do caso (ex: CASE-ABCD1234-5678-...)")
    @app_commands.checks.has_any_role("Analyst", "Analista", "Admin")
    async def assumir_caso(self, interaction: discord.Interaction, case_id: str):
        """Comando slash — alternativa ao botão do card quando o card não estiver acessível."""
        await interaction.response.defer(ephemeral=True)
        from config.database import db
        from views.analyst_views import _get_case_lock, build_case_embed, AnalystDecisionView

        async with _get_case_lock(case_id):
            doc = await db.get_collection("analysis_cases").find_one({"case_id": case_id})
            if not doc:
                await interaction.followup.send("Caso não encontrado.", ephemeral=True)
                return
            if doc["status"] != "aguardando_analise":
                await interaction.followup.send(
                    f"Caso já em estado `{doc['status']}`.", ephemeral=True)
                return
            await db.get_collection("analysis_cases").update_one(
                {"case_id": case_id},
                {"$set": {
                    "status":       "em_analise",
                    "analyst_id":   str(interaction.user.id),
                    "analyst_name": interaction.user.name,
                    "assumed_at":   utcnow(),
                }}
            )
            doc["status"]       = "em_analise"
            doc["analyst_id"]   = str(interaction.user.id)
            doc["analyst_name"] = interaction.user.name

        # Tenta atualizar o card no canal de fila
        fila_ch = discord.utils.get(interaction.guild.text_channels, name=ANALYST_QUEUE_CHANNEL)
        if fila_ch:
            async for msg in fila_ch.history(limit=50):
                if (msg.author == interaction.guild.me
                        and msg.embeds
                        and case_id in (msg.embeds[0].title or "")):
                    await msg.edit(
                        embed=build_case_embed(doc),
                        view=AnalystDecisionView(case_id=case_id)
                    )
                    break

        await interaction.followup.send(f"✅ Caso `{case_id}` assumido.", ephemeral=True)

    # ── /decidir_caso ─────────────────────────────────────────────

    @app_commands.command(name="decidir_caso", description="Registra decisão de análise")
    @app_commands.describe(
        case_id="ID do caso",
        decisao="Decisão final",
        motivo="Justificativa detalhada"
    )
    @app_commands.choices(decisao=[
        app_commands.Choice(name="Confirmado — Blacklist",   value="confirmado"),
        app_commands.Choice(name="Inconclusivo — Arquivado", value="inconclusivo"),
        app_commands.Choice(name="Inválido — Fechado",       value="invalido"),
    ])
    @app_commands.checks.has_any_role("Analyst", "Analista", "Admin")
    async def decidir_caso(
        self,
        interaction: discord.Interaction,
        case_id: str,
        decisao: str,
        motivo: str
    ):
        await interaction.response.defer(ephemeral=True)
        from config.database import db

        doc = await db.get_collection("analysis_cases").find_one({"case_id": case_id})
        if not doc:
            await interaction.followup.send("Caso não encontrado.", ephemeral=True)
            return

        # Só permite fechar caso que está em análise
        if doc["status"] != "em_analise":
            await interaction.followup.send(
                f"O caso precisa estar `em_analise` para ser decidido. "
                f"Status atual: `{doc['status']}`.", ephemeral=True)
            return

        # Só o analista responsável ou admin pode decidir
        if doc.get("analyst_id") and doc["analyst_id"] != str(interaction.user.id):
            if not interaction.user.guild_permissions.administrator:
                await interaction.followup.send(
                    "Apenas o analista responsável pode encerrar este caso.", ephemeral=True)
                return

        await db.get_collection("analysis_cases").update_one(
            {"case_id": case_id},
            {"$set": {
                "status":          decisao,
                "decision_reason": motivo,
                "closed_at":       utcnow(),
                "closed_by":       str(interaction.user.id),
            }}
        )
        doc["status"]          = decisao
        doc["decision_reason"] = motivo

        if decisao == "confirmado":
            # Garante que o acusado (não denunciante) vai para blacklist
            accused = (doc.get("accused_id") or "").strip()
            if not accused:
                accused = doc.get("reporter_id", "")
                logger.warning(
                    f"[AnalystCog] Caso {case_id} sem accused_id — usando reporter como fallback")

            await db.get_collection("blacklist").update_one(
                {"discord_id": accused},
                {"$set": {
                    "discord_id":    accused,
                    "reason":        motivo,
                    "case_id":       case_id,
                    "added_by":      str(interaction.user.id),
                    "added_by_name": interaction.user.name,
                    "added_at":      utcnow(),
                }},
                upsert=True
            )
            exposed = discord.utils.get(
                interaction.guild.text_channels, name=EXPOSED_CHANNEL_NAME)
            if exposed:
                embed = discord.Embed(title="Jogador adicionado à Blacklist", color=DANGER)
                embed.add_field(name="ID",      value=f"`{accused}`",            inline=True)
                embed.add_field(name="Caso",    value=f"`{case_id}`",            inline=True)
                embed.add_field(name="Motivo",  value=motivo,                    inline=False)
                embed.add_field(name="Analista", value=interaction.user.mention, inline=True)
                embed.set_footer(text=utcnow().strftime("%d/%m/%Y %H:%M UTC"))
                await exposed.send(embed=embed)

        # Notifica denunciante por DM
        try:
            reporter = await self.bot.fetch_user(int(doc["reporter_id"]))
            msg_map = {
                "confirmado":   "Suspeito confirmado — adicionado à blacklist.",
                "inconclusivo": "Análise inconclusiva — caso arquivado.",
                "invalido":     "Denúncia inválida — caso fechado.",
            }
            dm_embed = discord.Embed(
                title=f"Resultado da Análise — {case_id}",
                description=msg_map.get(decisao, decisao),
                color=THEME_COLOR
            )
            dm_embed.add_field(name="Motivo", value=motivo, inline=False)
            await reporter.send(embed=dm_embed)
        except Exception:
            pass

        await interaction.followup.send(
            f"✅ Caso `{case_id}` encerrado como `{decisao}`.", ephemeral=True)

    # ── /blacklist_add ─────────────────────────────────────────────

    @app_commands.command(name="blacklist_add",
                          description="Adiciona jogador à blacklist [somente #exposed]")
    @app_commands.describe(player_id="ID Discord do jogador", motivo="Motivo")
    @app_commands.checks.has_any_role("Analyst", "Admin")
    async def blacklist_add(
        self, interaction: discord.Interaction, player_id: str, motivo: str
    ):
        if not _is_in_exposed(interaction):
            await interaction.response.send_message(
                f"Este comando só pode ser usado no canal `#{EXPOSED_CHANNEL_NAME}`.",
                ephemeral=True)
            return
        if not _valid_discord_id(player_id):
            await interaction.response.send_message(
                "ID inválido. O ID Discord deve conter apenas números.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        from config.database import db

        pid = player_id.strip()
        await db.get_collection("blacklist").update_one(
            {"discord_id": pid},
            {"$set": {
                "discord_id":    pid,
                "reason":        motivo,
                "added_by":      str(interaction.user.id),
                "added_by_name": interaction.user.name,
                "added_at":      utcnow(),
            }},
            upsert=True
        )
        embed = discord.Embed(
            title="Blacklist — Jogador Adicionado",
            description=f"ID: `{pid}`\nMotivo: {motivo}",
            color=DANGER
        )
        embed.add_field(name="Analista", value=interaction.user.mention, inline=True)
        embed.set_footer(text=utcnow().strftime("%d/%m/%Y %H:%M UTC"))
        await interaction.channel.send(embed=embed)
        await interaction.followup.send("✅ Adicionado.", ephemeral=True)

    # ── /blacklist_remove ──────────────────────────────────────────

    @app_commands.command(name="blacklist_remove",
                          description="Remove jogador da blacklist [somente #exposed]")
    @app_commands.describe(player_id="ID Discord do jogador")
    @app_commands.checks.has_any_role("Analyst", "Admin")
    async def blacklist_remove(self, interaction: discord.Interaction, player_id: str):
        if not _is_in_exposed(interaction):
            await interaction.response.send_message(
                f"Este comando só pode ser usado no canal `#{EXPOSED_CHANNEL_NAME}`.",
                ephemeral=True)
            return
        if not _valid_discord_id(player_id):
            await interaction.response.send_message(
                "ID inválido. O ID Discord deve conter apenas números.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        from config.database import db

        result = await db.get_collection("blacklist").delete_one(
            {"discord_id": player_id.strip()})
        if result.deleted_count:
            await interaction.channel.send(
                f"Jogador `{player_id.strip()}` removido da blacklist "
                f"por {interaction.user.mention}.")
            await interaction.followup.send("✅ Removido.", ephemeral=True)
        else:
            await interaction.followup.send(
                "Jogador não encontrado na blacklist.", ephemeral=True)

    # ── /blacklist_check ───────────────────────────────────────────

    @app_commands.command(name="blacklist_check",
                          description="Verifica se jogador está na blacklist")
    @app_commands.describe(player_id="ID Discord do jogador")
    @app_commands.checks.has_any_role("Analyst", "Admin", "Support")
    async def blacklist_check(self, interaction: discord.Interaction, player_id: str):
        if not _valid_discord_id(player_id):
            await interaction.response.send_message(
                "ID inválido. O ID Discord deve conter apenas números.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        from config.database import db

        doc = await db.get_collection("blacklist").find_one(
            {"discord_id": player_id.strip()})
        if not doc:
            await interaction.followup.send(
                f"Jogador `{player_id.strip()}` não está na blacklist.", ephemeral=True)
            return
        embed = discord.Embed(title="Blacklist — Resultado", color=DANGER)
        embed.add_field(name="ID",       value=f"`{player_id.strip()}`",          inline=True)
        embed.add_field(name="Motivo",   value=doc.get("reason", "—"),            inline=False)
        embed.add_field(name="Analista", value=doc.get("added_by_name", "—"),     inline=True)
        added = doc.get("added_at")
        if added:
            embed.add_field(name="Adicionado em",
                            value=added.strftime("%d/%m/%Y"), inline=True)
        await interaction.followup.send(embed=embed, ephemeral=True)

    # ── /blacklist_list ────────────────────────────────────────────

    @app_commands.command(name="blacklist_list",
                          description="Lista jogadores na blacklist [somente #exposed]")
    @app_commands.checks.has_any_role("Analyst", "Admin")
    async def blacklist_list(self, interaction: discord.Interaction):
        if not _is_in_exposed(interaction):
            await interaction.response.send_message(
                f"Este comando só pode ser usado no canal `#{EXPOSED_CHANNEL_NAME}`.",
                ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        from config.database import db

        docs = await db.get_collection("blacklist").find({}).sort(
            "added_at", -1).limit(20).to_list(20)
        if not docs:
            await interaction.followup.send("Blacklist vazia.", ephemeral=True)
            return
        embed = discord.Embed(title="Blacklist — Últimos 20", color=DANGER)
        for doc in docs:
            ts     = doc.get("added_at")
            ts_str = ts.strftime("%d/%m/%Y") if ts else "—"
            embed.add_field(
                name=f"`{doc['discord_id']}`",
                value=f"Motivo: {doc.get('reason','—')} | "
                      f"Por: {doc.get('added_by_name','—')} | {ts_str}",
                inline=False
            )
        await interaction.followup.send(embed=embed, ephemeral=True)

    # ── !setup_analise ─────────────────────────────────────────────

    @commands.command(name="setup_analise")
    @commands.has_permissions(administrator=True)
    async def setup_analise(self, ctx: commands.Context):
        from views.analyst_views import build_analise_panel_embed, AnalisePanelView
        from services.channel_service import ANALYST_REQUEST_CHANNEL

        ch = discord.utils.get(ctx.guild.text_channels, name=ANALYST_REQUEST_CHANNEL)
        if not ch:
            await ctx.reply(
                f"Canal `#{ANALYST_REQUEST_CHANNEL}` não encontrado. "
                "Rode `!setupcanais` primeiro.")
            return
        await ch.send(embed=build_analise_panel_embed(), view=AnalisePanelView())
        await ctx.reply(f"✅ Painel de análise enviado em {ch.mention}.")

    # ── !setup_exposed ─────────────────────────────────────────────

    @commands.command(name="setup_exposed")
    @commands.has_permissions(administrator=True)
    async def setup_exposed(self, ctx: commands.Context):
        from views.analyst_views import build_exposed_embed, ExposedPanelView

        ch = discord.utils.get(ctx.guild.text_channels, name=EXPOSED_CHANNEL_NAME)
        if not ch:
            await ctx.reply(
                f"Canal `#{EXPOSED_CHANNEL_NAME}` não encontrado. "
                "Rode `!setupcanais` primeiro.")
            return
        await ch.send(embed=build_exposed_embed(), view=ExposedPanelView())
        await ctx.reply(f"✅ Painel de blacklist enviado em {ch.mention}.")


async def setup(bot: commands.Bot):
    await bot.add_cog(AnalystCog(bot))
