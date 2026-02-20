import discord
from datetime import datetime, timedelta
from config.database import db
import models.match
import models.mediator
import models.queue

from utils.logger import logger
import matplotlib.pyplot as plt
import io


class MediatorDashboardService:
    def __init__(self):
        self.channel_id_dashboard = 1473728494503596084
        self.message_id = None

    async def get_stats(self):
        try:
            collection = db.get_collection("matches")
            now = datetime.utcnow()
            today = now.replace(hour=0, minute=0, second=0, microsecond=0)
            week = now - timedelta(days=7)
            month = now - timedelta(days=30)

            return {
                "today": await collection.count_documents({"created_at": {"$gte": today}}),
                "week": await collection.count_documents({"created_at": {"$gte": week}}),
                "month": await collection.count_documents({"created_at": {"$gte": month}}),
            }
        except Exception as e:
            logger.error(f"Erro ao buscar stats: {e}")
            return None

    async def create_embed(self):
        stats = await self.get_stats()
        if not stats: return None, None

        # Dados do gráfico
        data = [stats["today"], stats["week"] // 7, stats["month"] // 30]
        labels = ["Hoje", "Média/Sem", "Média/Mês"]

        # Configuração do Matplotlib
        plt.figure(figsize=(6, 4))
        plt.plot(labels, data, marker="o", color="orange")
        plt.fill_between(labels, data, alpha=0.3, color="orange")
        plt.grid(True, linestyle='--', alpha=0.6)
        
        buffer = io.BytesIO()
        plt.savefig(buffer, format="png", bbox_inches='tight')
        buffer.seek(0)
        plt.close() # Limpa a memória

        file = discord.File(buffer, filename="grafico.png")
        embed = discord.Embed(title="📊 Relatório de Mediação", color=discord.Color.orange())
        embed.add_field(name="Hoje", value=f"**{stats['today']}**", inline=True)
        embed.add_field(name="Semana", value=f"**{stats['week']}**", inline=True)
        embed.add_field(name="Mês", value=f"**{stats['month']}**", inline=True)
        embed.set_image(url="attachment://grafico.png")

        return embed, file

    async def update_dashboard(self, bot):
        try:
            channel = bot.get_channel(self.channel_id_dashboard)
            if not channel: return

            embed, file = await self.create_embed()
            if not embed: return

            # Evita import circular se necessário
            from views.mediator_dashboard_view import MediatorDashboardView
            view = MediatorDashboardView(bot)

            if self.message_id:
                try:
                    message = await channel.fetch_message(self.message_id)
                    # No edit, passamos o novo arquivo
                    await message.edit(embed=embed, attachments=[file], view=view)
                    return
                except Exception:
                    pass # Se a mensagem foi deletada, envia uma nova

            message = await channel.send(embed=embed, file=file, view=view)
            self.message_id = message.id

        except Exception as e:
            logger.error(f"Erro update dashboard: {e}")

mediator_dashboard_service = MediatorDashboardService()