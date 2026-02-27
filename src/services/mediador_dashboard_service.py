import discord
from datetime import datetime, timedelta, timezone, time 
from urllib.parse import quote # Importante para tratar caracteres especiais no link
import numpy as np
from discord import client
from discord import user
from config.database import db
from utils.logger import logger
import matplotlib.pyplot as plt
import io
import matplotlib
from views.mediator_dashboard_view import MediatorDashboardView
from discord.errors import NotFound
from discord.ext import tasks
from zoneinfo import ZoneInfo # Disponível no Python 3.9+
from discord.ext import tasks

# Configuração para rodar em ambiente Docker/Linux
matplotlib.use('Agg')
horario_brasilia = time(3, 0, 0) 
channel_id_dashboard = 1473728494503596084 # Coloque o ID do canal aqui
class MediatorDashboardService:
    def __init__(self):
        # ID do canal onde o dashboard será enviado
        self.channel_id_dashboard = channel_id_dashboard
        self.bot = None  # Será setado no setup_hook do bot


    # Define o loop para rodar às 00:00 (Horário de SP)
    @tasks.loop(time=horario_brasilia)
    async def daily_update(self):
        """Task que roda automaticamente à meia-noite"""
        logger.info("Executando atualização automática de meia-noite...")
        await self.update_dashboard(self.bot)

    @daily_update.before_loop
    async def before_daily_update(self):
        """Garante que o bot esteja logado antes de começar a contar o tempo"""
        await self.bot.wait_until_ready()

    async def get_period_stats(self, days):
        """Busca dados no MongoDB agrupados por tempo para gerar os pontos do gráfico"""
        try:
            # Substitua 'db' pela sua instância de conexão com o MongoDB
            collection = db.get_collection("matches")
            start_date = datetime.now(timezone.utc) - timedelta(days=days)
            
            # 1. Busca totais para os textos do Embed
            total = await collection.count_documents({"created_at": {"$gte": start_date}})
            finalizadas = await collection.count_documents({"created_at": {"$gte": start_date}, "status": "finalizado"})
            canceladas = await collection.count_documents({"created_at": {"$gte": start_date}, "status": "cancelado"})
            
            aguardando = await collection.count_documents({
                "created_at": {"$gte": start_date}, 
                "status": {"$in": ["aguardando_pagamento", "aguardando_inicio", "aguardando_resultado"]}
            })

            # 2. Pipeline de Agregação para gerar os pontos do gráfico (Histórico)
            # Se for Relatório Diário (1 dia), agrupa por hora. Se for mais, agrupa por dia.
            group_format = "%Y-%m-%d %H:00" if days <= 1 else "%Y-%m-%d"
            
            pipeline = [
                {"$match": {
                    "created_at": {"$gte": start_date},
                    "status": "finalizado"
                }},
                {"$group": {
                    "_id": {"$dateToString": {"format": group_format, "date": "$created_at"}},
                    "count": {"$sum": 1}
                }},
                {"$sort": {"_id": 1}} # Garante que os pontos estejam na ordem cronológica
            ]
            
            cursor = collection.aggregate(pipeline)
            # Extrai apenas os números para formar a lista de pontos do gráfico
            history_points = [doc["count"] async for doc in cursor]

           # Define o alvo de pontos: 24 se for diário (days=1), 
            # senão usa o próprio número de dias (7 ou 30)
            target_points = 24 if days <= 1 else days
            
            if len(history_points) < target_points:
                # Preenche com zeros os pontos faltantes à direita
                history_points = history_points + [0] * (target_points - len(history_points))
            elif len(history_points) > target_points:
                # Se tiver mais dados que o esperado, limita
                history_points = history_points[:target_points]
            # ---------------------            

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
        plt.close('all')
        plt.style.use('dark_background')
    
        cor_fundo = "#2B2D31" 
        cor_linha_azul = "#0A37FF"
        cor_preenchimento = "#ECECF0"

        fig, ax = plt.subplots(figsize=(10, 4), facecolor=cor_fundo)
        ax.set_facecolor(cor_fundo)

        # 1. TRATAR OS DADOS (history_points já vem do stats)
        y = np.array(history_points)
        x = np.arange(len(y)) # Gera o X com base no tamanho dos dados

        # 2. CRIAR AS LEGENDAS DE HORAS (00:00, 01:00...)
        # Se for diário, mostra horas, se for mensal, mostra dias.
        # Simplifiquei para mostrar apenas o eixo X conforme os dados disponíveis.
        if len(y) <= 25:
            # Mostra índices (horas ou dias dependendo do que foi agrupado)
            horas = [f"{i:02d}" for i in range(len(y))]
        else:
            horas = [f"{i}" for i in range(len(y))]

        # Plotagem
        ax.plot(x, y, color=cor_linha_azul, linewidth=3, alpha=0.9, marker='o', markersize=4)
        ax.fill_between(x, y, color=cor_preenchimento, alpha=0.15)

        # 3. CONFIGURAR O EIXO X
        ax.set_xticks(x)
        ax.set_xticklabels(horas, color='white', fontsize=8, rotation=45)
        
        # Customização de visual
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_visible(False)
        ax.spines['bottom'].set_color('#4E5169')
        
        ax.get_yaxis().set_visible(False)
        ax.tick_params(axis='x', colors='gray')

        plt.subplots_adjust(left=0.05, right=0.95, top=0.9, bottom=0.2)

        buf = io.BytesIO()
        plt.savefig(
            buf, 
            format="png", 
            bbox_inches='tight', 
            facecolor=fig.get_facecolor(),
            edgecolor='none'
        )
        buf.seek(0)
        plt.close(fig)
        return buf
    
    async def create_embed(self, titulo, days):
        """Cria o embed com as estatísticas e o gráfico dinâmico"""
        try:
            stats = await self.get_period_stats(days)
            if not stats: return None, None

            # Gera o gráfico usando a lista de pontos do histórico
            buf = self.generate_styled_graph(stats["history"])
            file = discord.File(buf, filename=f"graph_{days}.png")

            embed = discord.Embed(title=f"📊 {titulo}", color=0x4b0082)
            
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
            logger.error(f"Erro ao criar embed de {titulo}: {e}")
            return None, None

    async def update_dashboard(self, bot):
        """Executa a limpeza, gera e envia os novos dashboards"""
        
        # 1. Defina o ID em uma constante separada
        ID_DO_CANAL = 1473728494503596084
        
        try:
            # 2. Tente buscar o objeto Canal
            canal_objeto = bot.get_channel(ID_DO_CANAL)
            
            
            if not canal_objeto:
                # 3. Se não achar, procura em todos os servidores
                for guild in bot.guilds:
                    canal_objeto = guild.get_channel(ID_DO_CANAL)
                    if canal_objeto: 
                        break
            
            # 4. Verificação de segurança
            if not canal_objeto:
                logger.error(f"❌ Canal {ID_DO_CANAL} NÃO ENCONTRADO em nenhum servidor.")
                return
            #canal existente 
            if canal_objeto:
                logger.info("✅ Canal encontrado no servidor Prosseguindo com a atualização.")

            # --- LIMPEZA: Apaga as mensagens antigas ---
            logger.info(f"🧹 Limpando mensagens antigas no canal: {canal_objeto.name}...")
            await canal_objeto.purge(limit=20) 

            # --- ENVIO: Posta os novos cards ---
            periodos = [
                ("Relatório Mensal", 30),
                ("Relatório Semanal", 7), 
                ("Relatório Diário", 1)
            ]
            
            for titulo, dias in periodos:
                try:
                    embed, file = await self.create_embed(titulo, dias)
                    if embed:
                        # 5. USE canal_objeto AQUI
                        await canal_objeto.send(embed=embed, file=file)
                        logger.info(f"✅ {titulo} enviado.")
                except Exception as e:
                    logger.error(f"Erro ao criar/enviar {titulo}: {e}")
            
            logger.info("✅ Processo de atualização concluído.")
            
        except Exception as e:
            logger.error(f"Erro crítico no update_dashboard: {e}")
# Instanciação global
mediator_dashboard_service = MediatorDashboardService()

