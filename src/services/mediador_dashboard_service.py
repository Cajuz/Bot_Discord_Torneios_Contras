import discord
from datetime import datetime, timedelta, timezone, time
import numpy as np
from config.database import db
from utils.logger import logger
import matplotlib.pyplot as plt
import io
import matplotlib
from discord.ext import tasks

matplotlib.use('Agg')

# Importa constantes do channel_service (fonte única da verdade)
from services.channel_service import (
    DASHBOARD_CHANNEL_NAME,
    CATEGORY_ANALYTICS_NAME,
    ADM_ROLE_NAME,
)

horario_brasilia = time(3, 0, 0)


class MediatorDashboardService:
    def __init__(self):
        self.bot = None  # Setado no on_ready do main.py


    # ==================== TASK DIÁRIA ====================


    @tasks.loop(time=horario_brasilia)
    async def daily_update(self):
        logger.info("Executando atualização automática de meia-noite...")
        for guild in self.bot.guilds:
            try:
                channel = await self.resolve_dashboard_channel(guild)
                if channel:
                    await self.update_dashboard_for_channel(channel)
            except Exception as e:
                logger.error(f"Erro no daily_update para guild {guild.name}: {e}")


    @daily_update.before_loop
    async def before_daily_update(self):
        await self.bot.wait_until_ready()


    # ==================== RESOLUÇÃO DO CANAL ====================


    async def resolve_dashboard_channel(self, guild: discord.Guild) -> discord.TextChannel | None:
        """
        Garante que a categoria Analytics e o canal dashboard-partidas existam
        com as permissões corretas (somente ADM visualiza).
        Usado pela task diária e como fallback independente.
        """
        try:
            # Categoria Analytics
            category = discord.utils.get(guild.categories, name=CATEGORY_ANALYTICS_NAME)
            if not category:
                category = await guild.create_category(CATEGORY_ANALYTICS_NAME)
                logger.info(f"✅ Categoria '{CATEGORY_ANALYTICS_NAME}' criada em {guild.name}")

            # Cargo ADM
            adm_role = discord.utils.get(guild.roles, name=ADM_ROLE_NAME)
            if not adm_role:
                adm_role = await guild.create_role(name=ADM_ROLE_NAME, mentionable=True)
                logger.info(f"✅ Cargo '{ADM_ROLE_NAME}' criado em {guild.name}")

            # Permissões: só ADM vê, @everyone bloqueado, bot pode tudo
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=False),
                adm_role: discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=False,
                    read_message_history=True
                ),
                guild.me: discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    manage_messages=True,
                    manage_channels=True
                ),
            }

            # Canal dashboard-partidas
            channel = discord.utils.get(guild.text_channels, name=DASHBOARD_CHANNEL_NAME)
            if not channel:
                channel = await guild.create_text_channel(
                    name=DASHBOARD_CHANNEL_NAME,
                    category=category,
                    overwrites=overwrites,
                    topic="📊 Dashboard automático de partidas — atualizado diariamente"
                )
                logger.info(f"✅ Canal '{DASHBOARD_CHANNEL_NAME}' criado em {guild.name}")
            else:
                await channel.edit(
                    category=category,
                    overwrites=overwrites,
                    topic="📊 Dashboard automático de partidas — atualizado diariamente"
                )
                logger.info(f"✅ Canal '{DASHBOARD_CHANNEL_NAME}' atualizado em {guild.name}")

            return channel

        except discord.Forbidden:
            logger.error(f"❌ Sem permissão para criar/editar canal em {guild.name}")
            return None
        except Exception as e:
            logger.error(f"Erro no resolve_dashboard_channel ({guild.name}): {e}")
            return None


    # ==================== ATUALIZAÇÃO DO DASHBOARD ====================


    async def update_dashboard_for_channel(self, channel: discord.TextChannel):
        """
        Limpa o canal e posta os 3 relatórios (mensal, semanal, diário).
        Método central — chamado pela task, pelo !dashboard e pelo setupcanais.
        """
        try:
            logger.info(f"🧹 Limpando mensagens em #{channel.name}...")
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
                        logger.info(f"✅ {titulo} enviado em #{channel.name}")
                except Exception as e:
                    logger.error(f"Erro ao enviar '{titulo}' em #{channel.name}: {e}")

            logger.info(f"✅ Dashboard de #{channel.name} concluído.")

        except discord.Forbidden:
            logger.error(f"❌ Sem permissão para postar/limpar em #{channel.name}")
        except Exception as e:
            logger.error(f"Erro crítico no update_dashboard_for_channel: {e}")


    # ==================== DADOS E GRÁFICOS ====================


    async def get_period_stats(self, days: int) -> dict | None:
        try:
            collection = db.get_collection("matches")
            start_date = datetime.now(timezone.utc) - timedelta(days=days)

            total       = await collection.count_documents({"created_at": {"$gte": start_date}})
            finalizadas = await collection.count_documents({"created_at": {"$gte": start_date}, "status": "finalizado"})
            canceladas  = await collection.count_documents({"created_at": {"$gte": start_date}, "status": "cancelado"})
            aguardando  = await collection.count_documents({
                "created_at": {"$gte": start_date},
                "status": {"$in": ["aguardando_pagamento", "aguardando_inicio", "aguardando_resultado"]}
            })

            group_format = "%Y-%m-%d %H:00" if days <= 1 else "%Y-%m-%d"
            pipeline = [
                {"$match": {
                    "created_at": {"$gte": start_date},
                    "status": "finalizado"
                }},
                {"$group": {
                    "_id":   {"$dateToString": {"format": group_format, "date": "$created_at"}},
                    "count": {"$sum": 1}
                }},
                {"$sort": {"_id": 1}}
            ]

            cursor         = collection.aggregate(pipeline)
            history_points = [doc["count"] async for doc in cursor]

            target_points = 24 if days <= 1 else days
            if len(history_points) < target_points:
                history_points = history_points + [0] * (target_points - len(history_points))
            elif len(history_points) > target_points:
                history_points = history_points[:target_points]

            taxa_conf = (finalizadas / total * 100) if total > 0 else 0
            taxa_canc = (canceladas  / total * 100) if total > 0 else 0

            return {
                "total":       total,
                "finalizadas": finalizadas,
                "canceladas":  canceladas,
                "aguardando":  aguardando,
                "taxa_conf":   round(taxa_conf, 1),
                "taxa_canc":   round(taxa_canc, 1),
                "history":     history_points,
            }

        except Exception as e:
            logger.error(f"Erro ao buscar stats de {days} dias: {e}")
            return None


    def generate_styled_graph(self, history_points: list) -> io.BytesIO:
        plt.close('all')
        plt.style.use('dark_background')

        cor_fundo         = "#2B2D31"
        cor_linha_azul    = "#0A37FF"
        cor_preenchimento = "#ECECF0"

        fig, ax = plt.subplots(figsize=(10, 4), facecolor=cor_fundo)
        ax.set_facecolor(cor_fundo)

        y = np.array(history_points)
        x = np.arange(len(y))

        horas = [f"{i:02d}" for i in range(len(y))] if len(y) <= 25 else [f"{i}" for i in range(len(y))]

        ax.plot(x, y, color=cor_linha_azul, linewidth=3, alpha=0.9, marker='o', markersize=4)
        ax.fill_between(x, y, color=cor_preenchimento, alpha=0.15)

        ax.set_xticks(x)
        ax.set_xticklabels(horas, color='white', fontsize=8, rotation=45)

        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_visible(False)
        ax.spines['bottom'].set_color('#4E5169')
        ax.get_yaxis().set_visible(False)
        ax.tick_params(axis='x', colors='gray')

        plt.subplots_adjust(left=0.05, right=0.95, top=0.9, bottom=0.2)

        buf = io.BytesIO()
        plt.savefig(buf, format="png", bbox_inches='tight', facecolor=fig.get_facecolor(), edgecolor='none')
        buf.seek(0)
        plt.close(fig)
        return buf


    async def create_embed(self, titulo: str, days: int) -> tuple:
        try:
            stats = await self.get_period_stats(days)
            if not stats:
                return None, None

            buf  = self.generate_styled_graph(stats["history"])
            file = discord.File(buf, filename=f"graph_{days}.png")

            embed             = discord.Embed(title=f"📊 {titulo}", color=0x4b0082)
            embed.description = (
                f"🎯 **Filas Finalizadas:** {stats['finalizadas']}\n"
                f"⌛ **Aguardando Fila:** {stats['aguardando']}\n"
                f"📦 **Total:** {stats['total']}\n"
                f"✅ **Taxa de Confirmação:** {stats['taxa_conf']}%\n"
                f"❌ **Taxa de Cancelamento:** {stats['taxa_canc']}%"
            )
            embed.set_image(url=f"attachment://graph_{days}.png")
            embed.set_footer(text=f"Dados reais extraídos às {datetime.now().strftime('%H:%M')}")

            return embed, file

        except Exception as e:
            logger.error(f"Erro ao criar embed de '{titulo}': {e}")
            return None, None


# Instanciação global
mediator_dashboard_service = MediatorDashboardService()
