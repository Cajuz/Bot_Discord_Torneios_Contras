import discord
from datetime import datetime, timedelta, timezone, time 
from urllib.parse import quote 
import numpy as np
from config.database import db
from utils.logger import logger
import matplotlib.pyplot as plt
import io
import matplotlib
from views.mediator_dashboard_view import MediatorDashboardView
from discord.errors import NotFound
from discord.ext import tasks
from zoneinfo import ZoneInfo 
from discord.ext import tasks
from config.channels_config import ChannelsConfig

# ✏️ Importar o modelo para usar as constantes de status
# from models.match import Match 
# Se não puder importar, usaremos as strings literais baseadas no seu modelo

matplotlib.use('Agg')
horario_brasilia = time(3, 0, 0) # 03:00 UTC é 00:00 em Brasília

# ID do canal onde o dashboard será enviado
ID_DO_CANAL = 1473728494503596084 

class MediatorDashboardService:
    def __init__(self):
        self.channel_id_dashboard = ID_DO_CANAL 
        self.bot = None  

    @tasks.loop(time=horario_brasilia)
    async def daily_update(self):
        logger.info("Executando atualização automática de meia-noite...")
        if self.bot:
            await self.update_dashboard(self.bot)

    @daily_update.before_loop
    async def before_daily_update(self):
        await self.bot.wait_until_ready()

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

    def generate_styled_graph(self, history_points):
        """Gera o gráfico de linhas estilizado"""
        plt.close('all')
        plt.style.use('dark_background')

        cor_fundo         = "#2B2D31"
        cor_linha_azul    = "#0A37FF"
        cor_preenchimento = "#ECECF0"

        fig, ax = plt.subplots(figsize=(10, 4), facecolor=cor_fundo)
        ax.set_facecolor(cor_fundo)

        y = np.array(history_points)
        x = np.arange(len(y)) 

        if len(y) <= 25:
            horas = [f"{i:02d}" for i in range(len(y))]
        else:
            horas = [f"{i}" for i in range(len(y))]

        ax.plot(x, y, color=cor_linha_azul, linewidth=3, alpha=0.9, marker='o', markersize=4)
        ax.fill_between(x, y, color=cor_preenchimento, alpha=0.15)

        # Configuração do visual
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
    
    async def create_embed(self, titulo, days, target_member=None):
        """Cria o embed com as estatísticas e o gráfico"""
        try:
            stats = await self.get_period_stats(days, target_member)
            if not stats: return None, None

            # Gera o gráfico
            buf = self.generate_styled_graph(stats["history"])
            file = discord.File(buf, filename=f"graph_{days}.png")

            embed = discord.Embed(title=f"📊 {titulo}", color=0x4b0082)
            
            if target_member:
                embed.title += f" - {target_member.display_name}"
            
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

    async def update_dashboard(self, bot, target_member=None):
        """Executa a limpeza, gera e envia os novos dashboards"""
        
        try:
            # 1. Busca o objeto Canal
            canal_objeto = bot.get_channel(self.channel_id_dashboard)
            
            if not canal_objeto:
                for guild in bot.guilds:
                    canal_objeto = guild.get_channel(self.channel_id_dashboard)
                    if canal_objeto: break
            
            if not canal_objeto:
                logger.error(f"❌ Canal {self.channel_id_dashboard} NÃO ENCONTRADO.")
                return

            logger.info(f"✅ Canal encontrado: {canal_objeto.name}. Iniciando atualização...")

            # --- LIMPEZA: Apaga as mensagens antigas ---
            await canal_objeto.purge(limit=20) 

            # --- ENVIO: Posta os novos cards ---
            periodos = [
                ("Relatório Mensal", 30),
                ("Relatório Semanal", 7), 
                ("Relatório Diário", 1)
            ]
            
            for titulo, dias in periodos:
                try:
                    embed, file = await self.create_embed(titulo, dias, target_member)
                    if embed:
                        await canal_objeto.send(embed=embed, file=file)
                        logger.info(f"✅ {titulo} enviado.")
                except Exception as e:
                    logger.error(f"Erro ao criar/enviar {titulo}: {e}")
            
            logger.info("✅ Processo de atualização concluído.")
            
        except Exception as e:
            logger.error(f"Erro crítico no update_dashboard: {e}")

# Instanciação global
mediator_dashboard_service = MediatorDashboardService()
