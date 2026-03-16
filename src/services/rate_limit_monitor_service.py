"""
F2 — RateLimitMonitorService
Registra eventos de rate limit no banco e exibe no canal #rate-limit-logs.
Integrado com o decorator @with_retry de utils/retry.py via callback.
"""
from __future__ import annotations
import discord
from discord.ext import tasks
from collections import deque
from utils.logger import logger
from utils.datetime_utils import utcnow


class RateLimitMonitorService:

    CHANNEL_NAME = "rate-limit-logs"
    MAX_MEMORY    = 50   # eventos em memória para o painel

    def __init__(self):
        self.bot: discord.Client | None = None
        self._recent: deque[dict] = deque(maxlen=self.MAX_MEMORY)
        self._total_today: int = 0

    # ── Callback chamado pelo retry.py ────────────────────────
    async def on_rate_limit_event(self, endpoint: str, retry_after: float, context: str = ""):
        """Registra e posta alerta de rate limit."""
        event = {
            "endpoint":    endpoint,
            "retry_after": retry_after,
            "context":     context,
            "timestamp":   utcnow(),
        }
        self._recent.appendleft(event)
        self._total_today += 1

        # Persiste no banco
        try:
            from config.database import db
            await db.get_collection("rate_limit_events").insert_one({**event})
        except Exception:
            pass

        # Posta no canal
        await self._post_alert(event)

    async def _post_alert(self, event: dict):
        """Envia embed de alerta no canal #rate-limit-logs."""
        if not self.bot:
            return

        for guild in self.bot.guilds:
            ch = discord.utils.get(guild.text_channels, name=self.CHANNEL_NAME)
            if not ch:
                continue
            try:
                embed = discord.Embed(
                    title="Rate Limit Detectado",
                    color=0xE74C3C
                )
                embed.add_field(name="Endpoint",  value=f"`{event['endpoint']}`",          inline=True)
                embed.add_field(name="Aguardar",  value=f"`{event['retry_after']:.1f}s`",   inline=True)
                embed.add_field(name="Contexto",  value=event["context"] or "—",              inline=False)
                embed.add_field(name="Hoje",      value=f"`{self._total_today} evento(s)`",   inline=True)
                embed.set_footer(text=event["timestamp"].strftime("%d/%m/%Y %H:%M:%S UTC"))
                await ch.send(embed=embed)
            except Exception as e:
                logger.warning(f"[RateLimitMonitor] Erro ao postar alerta: {e}")

    # ── Resumo diário (task) ──────────────────────────────────
    @tasks.loop(hours=24)
    async def daily_summary(self):
        """Posta resumo diário de rate limits às 00:00 UTC."""
        if not self.bot:
            return

        try:
            from config.database import db
            from datetime import timedelta

            since = utcnow().replace(hour=0, minute=0, second=0) - timedelta(days=1)
            count = await db.get_collection("rate_limit_events").count_documents(
                {"timestamp": {"$gte": since}}
            )

            top_cursor = db.get_collection("rate_limit_events").aggregate([
                {"$match": {"timestamp": {"$gte": since}}},
                {"$group": {"_id": "$endpoint", "total": {"$sum": 1}}},
                {"$sort":  {"total": -1}},
                {"$limit": 5}
            ])
            top = await top_cursor.to_list(length=5)

        except Exception as e:
            logger.error(f"[RateLimitMonitor] Erro no resumo diário: {e}")
            return

        for guild in self.bot.guilds:
            ch = discord.utils.get(guild.text_channels, name=self.CHANNEL_NAME)
            if not ch:
                continue
            embed = discord.Embed(
                title="Resumo de Rate Limits — Últimas 24h",
                color=0xFFA726
            )
            embed.add_field(name="Total de eventos", value=f"`{count}`", inline=True)
            if top:
                lines = [f"`{t['_id']}` — {t['total']}x" for t in top]
                embed.add_field(name="Top endpoints", value="\n".join(lines), inline=False)
            embed.set_footer(text=utcnow().strftime("%d/%m/%Y UTC"))
            await ch.send(embed=embed)

        self._total_today = 0  # reset contador

    # ── Stats para comandos ───────────────────────────────────
    async def get_stats(self, hours: int = 24) -> dict:
        from config.database import db
        from datetime import timedelta

        since = utcnow() - timedelta(hours=hours)
        count = await db.get_collection("rate_limit_events").count_documents(
            {"timestamp": {"$gte": since}}
        )
        top_cursor = db.get_collection("rate_limit_events").aggregate([
            {"$match": {"timestamp": {"$gte": since}}},
            {"$group": {"_id": "$endpoint", "total": {"$sum": 1}}},
            {"$sort":  {"total": -1}},
            {"$limit": 5}
        ])
        top = await top_cursor.to_list(length=5)
        return {"total": count, "top_endpoints": top, "recent": list(self._recent)[:5]}


rate_limit_monitor = RateLimitMonitorService()
