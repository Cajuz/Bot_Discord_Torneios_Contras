# alerts_cog.py — Loop de alertas automáticos para #alertas-adm.
from __future__ import annotations
import discord
from discord.ext import commands, tasks
from utils.logger import logger
from utils.datetime_utils import utcnow

ALERTAS_ADM_CHANNEL = "alertas-adm"
LATENCY_THRESHOLD_MS = 300
FILA_IDLE_MINUTES = 30


class AlertsCog(commands.Cog, name="Alertas"):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._loop_started = False

    # ─────────────────────────────────────────
    # LIFECYCLE
    # ─────────────────────────────────────────

    @commands.Cog.listener()
    async def on_ready(self):
        if not self._loop_started:
            self._loop_started = True
            self.alerts_loop.start()
            logger.info("[AlertsCog] Loop de alertas iniciado")

    def cog_unload(self):
        self.alerts_loop.cancel()

    # ─────────────────────────────────────────
    # LOOP PRINCIPAL — a cada 5 minutos
    # ─────────────────────────────────────────

    @tasks.loop(minutes=5)
    async def alerts_loop(self):
        await self.bot.wait_until_ready()
        for guild in self.bot.guilds:
            ch = discord.utils.get(guild.text_channels, name=ALERTAS_ADM_CHANNEL)
            if not ch:
                continue
            await self._check_latency(ch)
            await self._check_contracts(ch, guild)
            await self._check_fila(ch, guild)
            await self._check_afk_mediators(ch, guild)

    @alerts_loop.before_loop
    async def before_loop(self):
        await self.bot.wait_until_ready()

    # ─────────────────────────────────────────
    # VERIFICAÇÕES
    # ─────────────────────────────────────────

    async def _check_latency(self, ch: discord.TextChannel):
        latency_ms = round(self.bot.latency * 1000)
        if latency_ms > LATENCY_THRESHOLD_MS:
            embed = discord.Embed(
                title="⚠️ Latência Alta",
                description=f"Latência atual: **{latency_ms} ms** (limite: {LATENCY_THRESHOLD_MS} ms)",
                color=0xFF6B35,
                timestamp=utcnow(),
            )
            embed.set_footer(text="Alertas Automáticos · X1 Frifas")
            try:
                await ch.send(embed=embed)
            except Exception as e:
                logger.warning(f"[AlertsCog] latency alert: {e}")

    async def _check_contracts(self, ch: discord.TextChannel, guild: discord.Guild):
        """Alerta mediadores cujo contrato vence nos próximos 3 dias ou já venceu."""
        try:
            from config.database import db
            from datetime import timedelta
            col = db.get_collection("mediator_contracts")
            now = utcnow()
            warning_date = now + timedelta(days=3)
            # vencidos
            expired = await col.count_documents({
                "status": "active",
                "expires_at": {"$lt": now},
            })
            # próximos de vencer
            expiring = await col.count_documents({
                "status": "active",
                "expires_at": {"$gte": now, "$lte": warning_date},
            })
            if expired == 0 and expiring == 0:
                return
            embed = discord.Embed(
                title="📋 Contratos — Atenção",
                color=0xFF0000 if expired else 0xFFD54F,
                timestamp=utcnow(),
            )
            if expired:
                embed.add_field(name="❌ Contratos Vencidos", value=str(expired), inline=True)
            if expiring:
                embed.add_field(name="⏰ Vencem em até 3 dias", value=str(expiring), inline=True)
            embed.set_footer(text="Alertas Automáticos · X1 Frifas")
            await ch.send(embed=embed)
        except Exception as e:
            logger.warning(f"[AlertsCog] contracts: {e}")

    async def _check_fila(self, ch: discord.TextChannel, guild: discord.Guild):
        """Alerta se a fila de mediadores está parada há mais de FILA_IDLE_MINUTES."""
        try:
            from services.mediator_queue import mediator_queue
            info = await mediator_queue.get_queue_info()
            # info pode ser dict ou objeto com atributo last_activity
            last = None
            if isinstance(info, dict):
                last = info.get("last_activity") or info.get("updated_at")
            else:
                last = getattr(info, "last_activity", None) or getattr(info, "updated_at", None)
            if not last:
                return
            idle_minutes = (utcnow() - last).total_seconds() / 60
            if idle_minutes > FILA_IDLE_MINUTES:
                embed = discord.Embed(
                    title="🔇 Fila Parada",
                    description=(
                        f"A fila de mediadores está inativa há "
                        f"**{int(idle_minutes)} min** (limite: {FILA_IDLE_MINUTES} min)."
                    ),
                    color=0x95A5A6,
                    timestamp=utcnow(),
                )
                embed.set_footer(text="Alertas Automáticos · X1 Frifas")
                await ch.send(embed=embed)
        except Exception as e:
            logger.warning(f"[AlertsCog] fila check: {e}")

    async def _check_afk_mediators(self, ch: discord.TextChannel, guild: discord.Guild):
        """Alerta se há mediadores marcados como AFK há mais de 2 horas."""
        try:
            from config.database import db
            from datetime import timedelta
            col = db.get_collection("mediator_status")
            now = utcnow()
            threshold = now - timedelta(hours=2)
            count = await col.count_documents({
                "status": "afk",
                "afk_since": {"$lt": threshold},
            })
            if count == 0:
                return
            embed = discord.Embed(
                title="💤 Mediadores AFK Prolongado",
                description=f"**{count}** mediador(es) AFK há mais de 2 horas.",
                color=0x95A5A6,
                timestamp=utcnow(),
            )
            embed.set_footer(text="Alertas Automáticos · X1 Frifas")
            await ch.send(embed=embed)
        except Exception as e:
            logger.warning(f"[AlertsCog] afk check: {e}")

    # ─────────────────────────────────────────
    # ALERTA MANUAL — chamado por outros cogs
    # ─────────────────────────────────────────

    async def send_alert(
        self,
        guild: discord.Guild,
        title: str,
        description: str,
        color: int = 0xFF6B35,
    ):
        """Envia um alerta manual para #alertas-adm. Use em outros cogs."""
        ch = discord.utils.get(guild.text_channels, name=ALERTAS_ADM_CHANNEL)
        if not ch:
            logger.warning("[AlertsCog] Canal #alertas-adm não encontrado")
            return
        embed = discord.Embed(
            title=title,
            description=description,
            color=color,
            timestamp=utcnow(),
        )
        embed.set_footer(text="Alertas Automáticos · X1 Frifas")
        try:
            await ch.send(embed=embed)
        except Exception as e:
            logger.warning(f"[AlertsCog] send_alert: {e}")


async def setup(bot: commands.Bot):
    await bot.add_cog(AlertsCog(bot))
