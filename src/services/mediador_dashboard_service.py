import discord
from datetime import datetime, timedelta, timezone, time
import numpy as np
from config.database import db
from utils.logger import logger
import matplotlib.pyplot as plt
import io
import matplotlib
from discord.ext import tasks
from urllib.parse import quote 
from discord import client
from discord import user

from discord.errors import NotFound
from discord.ext import tasks
from zoneinfo import ZoneInfo 
from discord.ext import tasks
from config.channels_config import ChannelsConfig


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


    async def get_period_stats(self, days, target_member=None):
        """Busca dados no MongoDB agrupados por tempo e status, com filtro opcional de usuário"""
        try:
            collection = db.get_collection("matches")
            start_date = datetime.now(timezone.utc) - timedelta(days=days)
            
            # Base da query: apenas filtro de data
            query = {"created_at": {"$gte": start_date}}
            if target_member:
                query["user_id"] = target_member.id 
            
            # Busca todas as partidas no período para o diagnóstico
            cursor_debug = collection.find(query)
            docs = await cursor_debug.to_list(length=100)
            
            logger.info(f"DEBUG: Encontrados {len(docs)} documentos no período.")
            
            total = len(docs)
            
            # --- CORREÇÃO BASEADA NO MODELO MATCH E LOGS ---
            
            # 1. Filas Finalizadas: De acordo com o modelo novo, 'finalizado' é o status final.
            # Mas baseado nos seus logs, o status real final é 'aguardando_premio'.
            # Vou usar 'aguardando_premio' baseado no comportamento real do log.
            finalizadas = sum(1 for d in docs if d.get("status") == 'aguardando_premio')
            
            # 2. Canceladas: Ok, alinhado com 'cancelado'
            canceladas = sum(1 for d in docs if d.get("status") == 'cancelado')
            
            # 3. Aguardando: Alinhado com o modelo
            status_aguardando = [
                'aguardando_pagamento',
                'aguardando_inicio',
                'em_andamento',
                'aguardando_resultado'
            ]
            
            # Se 'aguardando_premio' não for considerado finalizado, adicione na lista acima
            aguardando = sum(1 for d in docs if d.get("status") in status_aguardando)
            
            # Pipeline de Agregação para o Gráfico
            group_format = "%Y-%m-%d %H:00" if days <= 1 else "%Y-%m-%d"
            
            pipeline = [
                {"$match": query}, 
                {"$group": {
                    "_id": {"$dateToString": {"format": group_format, "date": "$created_at"}},
                    "count": {"$sum": 1} 
                }},
                {"$sort": {"_id": 1}}
            ]
            
            cursor = collection.aggregate(pipeline)
            results_map = {doc["_id"]: doc["count"] async for doc in cursor}

            # Preenchimento de lacunas no gráfico
            history_points = []
            target_points = 24 if days <= 1 else days
            
            for i in range(target_points):
                if days <= 1:
                    check_time = (datetime.now(timezone.utc) - timedelta(hours=(target_points-1-i))).strftime("%Y-%m-%d %H:00")
                else:
                    check_time = (datetime.now(timezone.utc) - timedelta(days=(target_points-1-i))).strftime("%Y-%m-%d")
                
                history_points.append(results_map.get(check_time, 0))
            
            # Cálculos de Taxas
            taxa_conf = (finalizadas / total * 100) if total > 0 else 0
            taxa_canc = (canceladas / total * 100) if total > 0 else 0

            return {
                "total": total,
                "finalizadas": finalizadas,
                "canceladas": canceladas,
                "aguardando": aguardando,
                "taxa_conf": round(taxa_conf, 1),
                "taxa_canc": round(taxa_canc, 1),
                "history": history_points
            }
        except Exception as e:
            logger.error(f"Erro ao buscar stats de {days} dias: {e}")
            return None


    def generate_styled_graph(self, history_points):
        """Gera o gráfico de linhas estilizado"""
        plt.close('all')
        plt.style.use('dark_background')
    
        cor_fundo = "#2B2D31" 
        cor_linha = "#0A37FF"
        cor_area = "#ECECF0"


        fig, ax = plt.subplots(figsize=(10, 4), facecolor=cor_fundo)
        ax.set_facecolor(cor_fundo)

        y = np.array(history_points)
        x = np.arange(len(y)) 

        # Plotagem: Linha suave sem marcadores (bolinhas)
        ax.plot(x, y, color=cor_linha, linewidth=2, alpha=1.0)
        
        # Preenchimento com transparência suave (estilo Glow)
        ax.fill_between(x, y, color=cor_area, alpha=0.15)

        # Ajuste de Eixos para ficar "limpo" como na imagem
        ax.set_xticks(x[::2]) # Mostra de 2 em 2 para não amontoar
        ax.set_xticklabels([f"{i:02d}" for i in range(0, len(y), 2)], color='#4E5169', fontsize=7)
        
        # Esconder bordas inúteis
        for spine in ax.spines.values():
            spine.set_visible(False)
        
        ax.spines['bottom'].set_visible(True)
        ax.spines['bottom'].set_color('#4E5169')
        
        ax.yaxis.set_visible(False) # Remove números da lateral como no original
        ax.grid(True, axis='y', color='#2B2D31', linestyle='--', alpha=0.3)

        plt.subplots_adjust(left=0.02, right=0.98, top=0.9, bottom=0.15)

        buf = io.BytesIO()
        plt.savefig(buf, format="png", bbox_inches='tight', facecolor=fig.get_facecolor())
        buf.seek(0)
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