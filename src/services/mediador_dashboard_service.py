import io
import discord
import matplotlib
import matplotlib.pyplot as plt
import numpy as np

from datetime import datetime, timedelta, timezone, time
from zoneinfo import ZoneInfo
from discord.ext import tasks
from discord.errors import NotFound

from config.database import db
from config.channels_config import ChannelsConfig
from utils.logger import logger
from services.channel_service import (
    DASHBOARD_CHANNEL_NAME,
    CATEGORY_ANALYTICS_NAME,
    ADM_ROLE_NAME,
)

matplotlib.use('Agg')

horario_brasilia = time(3, 0, 0)


class MediatorDashboardService:

    def __init__(self):
        self.bot = None  # Setado no on_ready via start_task()

    # ─────────────────────────────────────────────────────────
    # Inicialização segura — chame no on_ready do main.py
    # ─────────────────────────────────────────────────────────

    def start_task(self, bot: discord.Client):
        self.bot = bot
        if not self.daily_update.is_running():
            self.daily_update.start()

    # ─────────────────────────────────────────────────────────
    # TASK DIÁRIA
    # ─────────────────────────────────────────────────────────

    @tasks.loop(time=horario_brasilia)
    async def daily_update(self):
        logger.info("[Dashboard] Executando atualização automática de meia-noite...")
        if not self.bot:
            logger.warning("[Dashboard] daily_update chamado antes do bot estar pronto.")
            return
        for guild in self.bot.guilds:
            try:
                channel = await self.resolve_dashboard_channel(guild)
                if channel:
                    await self.update_dashboard_for_channel(channel)
            except Exception as e:
                logger.error(f"[Dashboard] Erro no daily_update para guild {guild.name}: {e}")

    @daily_update.before_loop
    async def before_daily_update(self):
        if self.bot:
            await self.bot.wait_until_ready()

    # ─────────────────────────────────────────────────────────
    # RESOLUÇÃO DO CANAL
    # ─────────────────────────────────────────────────────────

    async def resolve_dashboard_channel(self, guild: discord.Guild) -> discord.TextChannel | None:
        try:
            category = discord.utils.get(guild.categories, name=CATEGORY_ANALYTICS_NAME)
            if not category:
                category = await guild.create_category(CATEGORY_ANALYTICS_NAME)
                logger.info(f"[Dashboard] Categoria '{CATEGORY_ANALYTICS_NAME}' criada em {guild.name}")

            adm_role = discord.utils.get(guild.roles, name=ADM_ROLE_NAME)
            if not adm_role:
                adm_role = await guild.create_role(name=ADM_ROLE_NAME, mentionable=True)
                logger.info(f"[Dashboard] Cargo '{ADM_ROLE_NAME}' criado em {guild.name}")

            overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=False),
                adm_role: discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=False,
                    read_message_history=True,
                ),
                guild.me: discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    manage_messages=True,
                    manage_channels=True,
                ),
            }

            channel = discord.utils.get(guild.text_channels, name=DASHBOARD_CHANNEL_NAME)
            if not channel:
                channel = await guild.create_text_channel(
                    name=DASHBOARD_CHANNEL_NAME,
                    category=category,
                    overwrites=overwrites,
                    topic="📊 Dashboard automático de partidas — atualizado diariamente",
                )
                logger.info(f"[Dashboard] Canal '{DASHBOARD_CHANNEL_NAME}' criado em {guild.name}")
            else:
                await channel.edit(
                    category=category,
                    overwrites=overwrites,
                    topic="📊 Dashboard automático de partidas — atualizado diariamente",
                )

            return channel

        except discord.Forbidden:
            logger.error(f"[Dashboard] Sem permissão para criar/editar canal em {guild.name}")
            return None
        except Exception as e:
            logger.error(f"[Dashboard] Erro no resolve_dashboard_channel ({guild.name}): {e}")
            return None

    # ─────────────────────────────────────────────────────────
    # ATUALIZAÇÃO DO DASHBOARD
    # ─────────────────────────────────────────────────────────

    async def update_dashboard_for_channel(self, channel: discord.TextChannel):
        try:
            logger.info(f"[Dashboard] Limpando mensagens em #{channel.name}...")
            await channel.purge(limit=20)

            periodos = [
                ("Relatório Mensal",  30),
                ("Relatório Semanal",  7),
                ("Relatório Diário",   1),
            ]

            for titulo, dias in periodos:
                try:
                    embed, file = await self.create_embed(titulo, dias)
                    if embed:
                        await channel.send(embed=embed, file=file)
                        logger.info(f"[Dashboard] {titulo} enviado em #{channel.name}")
                except Exception as e:
                    logger.error(f"[Dashboard] Erro ao enviar '{titulo}' em #{channel.name}: {e}")

            logger.info(f"[Dashboard] Dashboard de #{channel.name} concluído.")

        except discord.Forbidden:
            logger.error(f"[Dashboard] Sem permissão para postar/limpar em #{channel.name}")
        except Exception as e:
            logger.error(f"[Dashboard] Erro crítico no update_dashboard_for_channel: {e}")

    # ─────────────────────────────────────────────────────────
    # DADOS E ESTATÍSTICAS
    # ─────────────────────────────────────────────────────────

    async def get_period_stats(self, days: int, target_member=None) -> dict | None:
        try:
            collection = db.get_collection("matches")
            start_date = datetime.now(timezone.utc) - timedelta(days=days)

            query = {"created_at": {"$gte": start_date}}
            if target_member:
                query["user_id"] = target_member.id

            docs = await collection.find(query).to_list(length=500)
            total = len(docs)

            finalizadas = sum(1 for d in docs if d.get("status") == "aguardando_premio")
            canceladas  = sum(1 for d in docs if d.get("status") == "cancelado")

            status_aguardando = {
                "aguardando_pagamento",
                "aguardando_inicio",
                "em_andamento",
                "aguardando_resultado",
            }
            aguardando = sum(1 for d in docs if d.get("status") in status_aguardando)

            group_format = "%Y-%m-%d %H:00" if days <= 1 else "%Y-%m-%d"

            pipeline = [
                {"$match": query},
                {"$group": {
                    "_id": {"$dateToString": {"format": group_format, "date": "$created_at"}},
                    "count": {"$sum": 1},
                }},
                {"$sort": {"_id": 1}},
            ]

            cursor = collection.aggregate(pipeline)
            results_map = {doc["_id"]: doc["count"] async for doc in cursor}

            target_points = 24 if days <= 1 else days
            history_points = []

            for i in range(target_points):
                if days <= 1:
                    key = (datetime.now(timezone.utc) - timedelta(hours=(target_points - 1 - i))).strftime("%Y-%m-%d %H:00")
                else:
                    key = (datetime.now(timezone.utc) - timedelta(days=(target_points - 1 - i))).strftime("%Y-%m-%d")
                history_points.append(results_map.get(key, 0))

            taxa_conf = round(finalizadas / total * 100, 1) if total > 0 else 0.0
            taxa_canc = round(canceladas  / total * 100, 1) if total > 0 else 0.0

            return {
                "total":       total,
                "finalizadas": finalizadas,
                "canceladas":  canceladas,
                "aguardando":  aguardando,
                "taxa_conf":   taxa_conf,
                "taxa_canc":   taxa_canc,
                "history":     history_points,
            }

        except Exception as e:
            logger.error(f"[Dashboard] Erro ao buscar stats de {days} dias: {e}")
            return None

    # ─────────────────────────────────────────────────────────
    # GRÁFICO
    # ─────────────────────────────────────────────────────────

    def generate_styled_graph(self, history_points: list) -> io.BytesIO:
        plt.close('all')
        plt.style.use('dark_background')

        cor_fundo = "#2B2D31"
        cor_linha = "#0A37FF"
        cor_area  = "#ECECF0"

        fig, ax = plt.subplots(figsize=(10, 4), facecolor=cor_fundo)
        ax.set_facecolor(cor_fundo)

        y = np.array(history_points)
        x = np.arange(len(y))

        ax.plot(x, y, color=cor_linha, linewidth=2, alpha=1.0)
        ax.fill_between(x, y, color=cor_area, alpha=0.15)

        ax.set_xticks(x[::2])
        ax.set_xticklabels(
            [f"{i:02d}" for i in range(0, len(y), 2)],
            color='#4E5169', fontsize=7
        )

        for spine in ax.spines.values():
            spine.set_visible(False)
        ax.spines['bottom'].set_visible(True)
        ax.spines['bottom'].set_color('#4E5169')

        ax.yaxis.set_visible(False)
        ax.grid(True, axis='y', color='#2B2D31', linestyle='--', alpha=0.3)

        plt.subplots_adjust(left=0.02, right=0.98, top=0.9, bottom=0.15)

        buf = io.BytesIO()
        plt.savefig(buf, format="png", bbox_inches='tight', facecolor=fig.get_facecolor())
        buf.seek(0)
        plt.close(fig)
        return buf

    # ─────────────────────────────────────────────────────────
    # EMBED
    # ─────────────────────────────────────────────────────────

    async def create_embed(self, titulo: str, days: int) -> tuple[discord.Embed | None, discord.File | None]:
        try:
            stats = await self.get_period_stats(days)
            if not stats:
                return None, None

            buf  = self.generate_styled_graph(stats["history"])
            file = discord.File(buf, filename=f"graph_{days}.png")

            embed = discord.Embed(title=f"📊 {titulo}", color=0x4B0082)
            embed.description = (
                f"🎯 **Filas Finalizadas:** {stats['finalizadas']}\n"
                f"⌛ **Aguardando Fila:** {stats['aguardando']}\n"
                f"📦 **Total:** {stats['total']}\n"
                f"✅ **Taxa de Confirmação:** {stats['taxa_conf']}%\n"
                f"❌ **Taxa de Cancelamento:** {stats['taxa_canc']}%"
            )
            embed.set_image(url=f"attachment://graph_{days}.png")
            embed.set_footer(text=f"Dados extraídos às {datetime.now().strftime('%H:%M')}")

            return embed, file

        except Exception as e:
            logger.error(f"[Dashboard] Erro ao criar embed de '{titulo}': {e}")
            return None, None


# Instância global
mediator_dashboard_service = MediatorDashboardService()
