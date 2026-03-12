import discord
from datetime import datetime, timedelta, timezone
import numpy as np
import matplotlib.pyplot as plt
import io
import matplotlib
from config.database import db
from services.faturamento_mediador import RelatorioGeralView
from utils.logger import logger
from models.mediator import Mediator
from models.match import Match

matplotlib.use("Agg")


class QueueAnalysisService:

    async def get_queue_stats(self):
        try:
            collection = db.get_collection("matches")
            mediators_collection = db.get_collection("mediators")

            # ── Busca partidas das últimas 24h
            start_date = datetime.now(timezone.utc) - timedelta(hours=24)
            query = {"created_at": {"$gte": start_date}}
            docs = await collection.find(query).to_list(length=10000)

            total = len(docs)

            # ── Status das partidas
            status_confirmadas = ["aguardando_premio"]
            status_aguardando = [
                "aguardando_pagamento",
                "aguardando_inicio",
                "em_andamento",
                "aguardando_resultado"
            ]

            confirmadas = sum(1 for d in docs if d.get("status") in status_confirmadas)
            aguardando = sum(1 for d in docs if d.get("status") in status_aguardando)

            # ── TOTAL DE MEDIADORES ATIVOS (corrigido)
            mediadores_total = await mediators_collection.count_documents({"is_active": True})

            # ── MEDIADORES EM FILA (ignora duplicados e registros sem mediator_id)
            mediadores_em_fila = set(
                d.get("mediator_id")
                for d in docs
                if d.get("status") in status_aguardando and d.get("mediator_id")
            )

            # ── Histórico de partidas por hora
            pipeline = [
                {"$match": query},
                {
                    "$group": {
                        "_id": {
                            "$dateToString": {"format": "%Y-%m-%d %H:00", "date": "$created_at"}
                        },
                        "count": {"$sum": 1}
                    }
                },
                {"$sort": {"_id": 1}}
            ]

            cursor = collection.aggregate(pipeline)
            results_map = {doc["_id"]: doc["count"] async for doc in cursor}

            history = []
            for i in range(24):
                check_time = (
                    datetime.now(timezone.utc) - timedelta(hours=(23 - i))
                ).strftime("%Y-%m-%d %H:00")
                history.append(results_map.get(check_time, 0))

            return {
                "mediadores_total": mediadores_total,
                "mediadores_em_fila": len(mediadores_em_fila),
                "total": total,
                "confirmadas": confirmadas,
                "aguardando": aguardando,
                "history": history
            }

        except Exception as e:
            logger.error(f"Erro ao buscar análise de filas: {e}")
            return None

    def generate_graph(self, history):
        plt.close("all")
        plt.style.use("dark_background")

        cor_fundo = "#2B2D31"
        cor_linha = "#f59e0b"

        fig, ax = plt.subplots(figsize=(10, 4), facecolor=cor_fundo)
        ax.set_facecolor(cor_fundo)

        y = np.array(history)
        x = np.arange(len(y))

        ax.plot(x, y, color=cor_linha, linewidth=3)
        ax.fill_between(x, y, color=cor_linha, alpha=0.2)

        ax.set_xticks(x[::2])
        ax.set_xticklabels([f"{i:02d}" for i in range(0, 24, 2)], fontsize=8)
        ax.yaxis.set_visible(False)

        for spine in ax.spines.values():
            spine.set_visible(False)

        buf = io.BytesIO()
        plt.savefig(buf, format="png", bbox_inches="tight", facecolor=fig.get_facecolor())
        buf.seek(0)

        return buf

    async def create_embed(self):
        stats = await self.get_queue_stats()

        if not stats:
            return None, None

        buf = self.generate_graph(stats["history"])
        file = discord.File(buf, filename="queue_analysis.png")

        embed = discord.Embed(
            title="📊 Análises das Filas",
            color=0xf59e0b
        )

        embed.description = (
            f"**Mediadores:**\n"
            f"{stats['mediadores_total']} ativos\n"
            f"{stats['mediadores_em_fila']} em fila\n\n"
            f"**Filas Simultâneas:**\n"
            f"• Total: {stats['total']}\n"
            f"• Confirmadas: {stats['confirmadas']}\n"
            f"• Aguardando: {stats['aguardando']}\n\n"
            f"**Últimas 24h:** {sum(stats['history'])} filas"
        )

        embed.set_image(url="attachment://queue_analysis.png")
        embed.set_footer(text=f"Atualizado às {datetime.now().strftime('%H:%M')}")

        return embed, file


queue_analysis_service = QueueAnalysisService()


class AnalyticsView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    # ── BOTÃO FILAS
    @discord.ui.button(label="Filas", style=discord.ButtonStyle.secondary, emoji="📊")
    async def filas(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        embed, file = await queue_analysis_service.create_embed()
        await interaction.followup.send(embed=embed, file=file)

    # ── BOTÃO FATURAMENTO
    @discord.ui.button(label="Faturamento", style=discord.ButtonStyle.secondary, emoji="💰")
    async def faturamento(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="📊 Central de Faturamento Geral",
            description="Clique no botão abaixo para gerar o relatório de faturamento de todos os mediadores.",
            color=discord.Color.blue()
        )
        view = RelatorioGeralView()
        await interaction.response.send_message(embed=embed, view=view)