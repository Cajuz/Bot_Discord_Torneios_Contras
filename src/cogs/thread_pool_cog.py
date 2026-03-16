"""
thread_pool_cog.py — Comandos admin para gerenciamento do pool de threads.

Comandos:
  /thread_pool setup      — posta/atualiza o painel no canal atual
  /thread_pool preaquecer — cria N threads arquivadas no canal atual
  /thread_pool status     — resposta ephemeral rápida com o health
"""
from __future__ import annotations
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands, tasks

from config.database import db
from utils.logger import logger
from utils.datetime_utils import utcnow

# ← imports corrigidos: vêm de health_check_view agora
from views.health_check_view import HealthCheckView, build_overview_embed

REFRESH_INTERVAL = 5   # minutos entre auto-refreshes


class ThreadPoolCog(commands.Cog):

    def __init__(self, bot: discord.Client):
        self.bot = bot
        self._auto_refresh.start()

    def cog_unload(self):
        self._auto_refresh.cancel()

    def _is_admin(self, interaction: discord.Interaction) -> bool:
        return (
            interaction.user.guild_permissions.administrator
            or any(r.name == "ADM" for r in interaction.user.roles)
        )

    # ── Grupo de comandos /thread_pool ────────────────────────

    group = app_commands.Group(
        name="thread_pool",
        description="[ADM] Gerenciamento do pool de threads",
        default_permissions=discord.Permissions(administrator=True),
    )

    @group.command(name="setup", description="[ADM] Posta o painel de monitoramento no canal atual")
    async def setup(self, interaction: discord.Interaction):
        if not self._is_admin(interaction):
            await interaction.response.send_message("❌ Apenas administradores.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        channel = interaction.channel

        # Tenta buscar relatório completo do service
        report = await self._get_report(interaction.guild)
        if report:
            embed = await build_overview_embed(report)
            view  = HealthCheckView(report=report, guild=interaction.guild)
        else:
            from main import BOT_START_TIME
            embed = await build_overview_embed(self.bot, BOT_START_TIME)
            view  = HealthCheckView(bot=self.bot)

        existing = await self._get_panel_message(interaction.guild.id, channel.id)
        if existing:
            try:
                await existing.edit(embed=embed, view=view)
                await interaction.followup.send(
                    "✅ Painel atualizado na mensagem existente.", ephemeral=True)
                return
            except (discord.NotFound, discord.HTTPException):
                pass

        msg = await channel.send(embed=embed, view=view)
        await self._save_panel_message(interaction.guild.id, channel.id, msg.id)
        await interaction.followup.send(
            f"✅ Painel postado em {channel.mention}.\n"
            f"Auto-atualização a cada **{REFRESH_INTERVAL} minutos**.",
            ephemeral=True,
        )
        logger.info(f"[ThreadPool] Painel criado em #{channel.name} — msg {msg.id}")

    @group.command(name="preaquecer", description="[ADM] Cria threads arquivadas no canal atual")
    @app_commands.describe(quantidade="Número de threads a criar (padrão: 3, máx: 10)")
    async def preaquecer(self, interaction: discord.Interaction, quantidade: int = 3):
        if not self._is_admin(interaction):
            await interaction.response.send_message("❌ Apenas administradores.", ephemeral=True)
            return
        quantidade = max(1, min(quantidade, 10))
        await interaction.response.defer(ephemeral=True)

        from services.thread_reuse_service import thread_reuse_service
        if not thread_reuse_service:
            await interaction.followup.send("❌ Serviço não inicializado.", ephemeral=True)
            return

        criadas = await thread_reuse_service.preaquecer(
            interaction.channel, quantidade=quantidade)
        await interaction.followup.send(
            f"♻️ **{criadas}/{quantidade}** threads arquivadas criadas no pool.",
            ephemeral=True,
        )

    @group.command(name="status", description="[ADM] Resumo rápido do pool (ephemeral)")
    async def status(self, interaction: discord.Interaction):
        if not self._is_admin(interaction):
            await interaction.response.send_message("❌ Apenas administradores.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        report = await self._get_report(interaction.guild)
        if report:
            embed = await build_overview_embed(report)
        else:
            from main import BOT_START_TIME
            embed = await build_overview_embed(self.bot, BOT_START_TIME)
        await interaction.followup.send(embed=embed, ephemeral=True)

    # ── Auto-refresh ──────────────────────────────────────────

    @tasks.loop(minutes=REFRESH_INTERVAL)
    async def _auto_refresh(self):
        for guild in self.bot.guilds:
            try:
                await self._refresh_panel_for_guild(guild)
            except Exception as e:
                logger.warning(f"[ThreadPool] Auto-refresh falhou em {guild.id}: {e}")

    @_auto_refresh.before_loop
    async def _before_refresh(self):
        await self.bot.wait_until_ready()

    async def _refresh_panel_for_guild(self, guild: discord.Guild):
        col  = db.get_collection("thread_pool_panels")
        docs = await col.find({"guild_id": str(guild.id)}).to_list(length=20)
        if not docs:
            return

        report = await self._get_report(guild)
        if report:
            embed = await build_overview_embed(report)
            view  = HealthCheckView(report=report, guild=guild)
        else:
            from main import BOT_START_TIME
            embed = await build_overview_embed(self.bot, BOT_START_TIME)
            view  = HealthCheckView(bot=self.bot)

        for doc in docs:
            try:
                channel = guild.get_channel(int(doc["channel_id"]))
                if not channel:
                    continue
                msg = await channel.fetch_message(int(doc["message_id"]))
                await msg.edit(embed=embed, view=view)
            except (discord.NotFound, discord.HTTPException):
                await col.delete_one({"_id": doc["_id"]})
                logger.info("[ThreadPool] Painel removido do banco (mensagem deletada)")
            except Exception as e:
                logger.warning(f"[ThreadPool] Falha ao auto-refresh: {e}")

    # ── Helpers ───────────────────────────────────────────────

    async def _get_report(self, guild: discord.Guild):
        try:
            from services.health_check_service import health_check_service
            if health_check_service:
                return await health_check_service.run_check(guild)
        except Exception as e:
            logger.warning(f"[ThreadPool] Não foi possível obter relatório: {e}")
        return None

    async def _save_panel_message(self, guild_id: int, channel_id: int, message_id: int):
        col = db.get_collection("thread_pool_panels")
        await col.update_one(
            {"guild_id": str(guild_id), "channel_id": str(channel_id)},
            {"$set": {
                "guild_id":   str(guild_id),
                "channel_id": str(channel_id),
                "message_id": str(message_id),
                "updated_at": utcnow(),
            }},
            upsert=True,
        )

    async def _get_panel_message(
        self, guild_id: int, channel_id: int
    ) -> Optional[discord.Message]:
        col = db.get_collection("thread_pool_panels")
        doc = await col.find_one({
            "guild_id":   str(guild_id),
            "channel_id": str(channel_id),
        })
        if not doc:
            return None
        guild   = self.bot.get_guild(guild_id)
        channel = guild.get_channel(channel_id) if guild else None
        if not channel:
            return None
        try:
            return await channel.fetch_message(int(doc["message_id"]))
        except (discord.NotFound, discord.HTTPException):
            return None


async def setup(bot: discord.Client):
    await bot.add_cog(ThreadPoolCog(bot))
