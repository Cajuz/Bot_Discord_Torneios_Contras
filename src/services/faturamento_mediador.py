import discord
import io

from discord.ext import commands
from models import match, mediator,queue,user 
from datetime import datetime, timedelta, timezone
from config.database import db 
from utils.logger import logger
from datetime import datetime, timezone
from bson import ObjectId # Necessário para converter IDs se precisar

# --- 1. CONFIGURAÇÃO DE CAMPOS (Mapeado para o modelo Match fornecido) ---
CAMPO_PAGAMENTO_CONFIRMADO = 'pagamento_confirmado' 
CAMPO_MEDIADOR_ID = 'mediator_id'
CAMPO_DATA_INICIO = 'started_at' # Data em que a partida começou de fato
CAMPO_DATA_FIM = 'completed_at'  # Data em que a partida foi finalizada
CAMPO_VALOR = 'bet_value'
CAMPO_STATUS = 'status'
STATUS_CONCLUIDO = 'finalizado' # STATUS_CONCLUIDO do modelo

# --- 2. SERVICE: Lógica de Negócio ---
class FaturamentoMediadorService:
    def __init__(self):
        pass
    
    async def buscar_partidas_do_banco(self, discord_id: str):
        """Busca todas as partidas de um mediador no banco de dados"""
        try:
            collection = db.get_collection("matches")
            
            # 🔍 --- DEPURAR UM DOCUMENTO ---
            # Busca um único documento para logar e verificar a estrutura
            documento_exemplo = await collection.find_one({})
            if documento_exemplo:
                logger.info(f"🔍 DEBUG: Estrutura real de UM documento no banco: {documento_exemplo}")
            else:
                logger.warning("⚠️ DEBUG: A coleção 'matches' está vazia!")
            # -------------------------------

            # 🛡️ CORREÇÃO CRÍTICA: Força conversão para string na query
            # Nota: Se o log acima mostrar que o ID é número, altere para int(discord_id)
            query = {CAMPO_MEDIADOR_ID: int(discord_id)}
            
            logger.info(f"DEBUG: Buscando partidas com query: {query}")
            
            cursor = collection.find(query)
            
            partidas = []
            async for documento in cursor:
                partidas.append(documento)
            
            logger.info(f"DEBUG: Encontradas {len(partidas)} partidas para o ID {discord_id}.")
            return partidas
        except Exception as e:
            logger.error(f"Erro ao buscar partidas no banco: {e}")
            return []

# --- 3. VIEW: Interface de Botões (Interatividade) ---
class FaturamentoView(discord.ui.View):
    def __init__(self, service: FaturamentoMediadorService, partidas: list, mediador_id: str, nome_mediador: str, avatar_url: str):
        super().__init__(timeout=180)
        self.service = service
        self.partidas = partidas
        self.mediador_id = str(mediador_id) 
        self.nome_mediador = nome_mediador
        self.avatar_url = avatar_url
    
    # --- 🛠️ BOTÃO DE TXT REMOVIDO ---

    async def gerar_embed(self, dias: int) -> discord.Embed:
        """Calcula os dados com base na lógica do relatório (finalizadas + canceladas)"""
        total_faturado = 0.0
        total_segundos_trabalhados = 0
        
        # --- 🛡️ CORREÇÃO DE TIMEZONE ---
        data_atual = datetime.now(timezone.utc)
        limite = data_atual - timedelta(days=dias)

        # 📋 LOG: Validação inicial
        logger.info(f"📊 DEBUG: Analisando {len(self.partidas)} partidas do mediador {self.mediador_id}. Limite: {limite}")

        partidas_processadas = 0
        for partida in self.partidas:
            # 🛡️ Proteção: Garante que o ID do mediador é string
            id_mediador_partida = str(partida.get(CAMPO_MEDIADOR_ID, ''))
            
            # --- 🛠️ CORREÇÃO 1: STATUS FLEXÍVEL (Finalizado ou Cancelado) ---
            status_partida = partida.get(CAMPO_STATUS)
            
            # 📢 A LÓGICA APLICADA AQUI: status_valido aceita "finalizado" ou "cancelado"
            status_valido = status_partida in [STATUS_CONCLUIDO, "cancelado"]
            
            # Filtro: Mediador correto, Pago E Status Válido
            if (id_mediador_partida == self.mediador_id and 
                partida.get(CAMPO_PAGAMENTO_CONFIRMADO, False) is True and
                status_valido): 
                
                # --- 🛠️ CORREÇÃO 2: CÁLCULO DE TEMPO ROBUSTO ---
                data_inicio = partida.get(CAMPO_DATA_INICIO)
                if not data_inicio:
                    continue

                # Normaliza para UTC
                if data_inicio.tzinfo is None:
                    data_inicio = data_inicio.replace(tzinfo=timezone.utc)
                
                # Verifica se a partida está dentro do período de dias solicitado
                if data_inicio >= limite:
                    partidas_processadas += 1
                    
                    # 4. SOMA O VALOR
                    try:
                        valor = float(partida.get(CAMPO_VALOR, 0.0))
                        total_faturado += valor
                    except (ValueError, TypeError):
                        logger.warning(f"DEBUG: Valor inválido na partida {partida.get('_id')}")
                    
                    # 5. CÁLCULO DE TEMPO (usa completed_at se existir, senão usa agora)
                    data_fim = partida.get(CAMPO_DATA_FIM)
                    if not data_fim:
                        # Se não finalizou/cancelou oficialmente, usa o horário atual
                        data_fim = datetime.now(timezone.utc) 
                    
                    if data_fim.tzinfo is None:
                        data_fim = data_fim.replace(tzinfo=timezone.utc)
                    
                    tempo_partida = data_fim - data_inicio
                    
                    # 🛡️ PROTEÇÃO: Evita tempos negativos
                    if tempo_partida.total_seconds() > 0:
                        total_segundos_trabalhados += tempo_partida.total_seconds()
        
        logger.info(f"📊 DEBUG: {partidas_processadas} partidas somadas ao faturamento.")

        # --- Formatação ---
        total_horas = total_segundos_trabalhados / 3600
        media_por_hora = (total_faturado / total_horas) if total_horas > 0 else 0.0
        
        # Formatação brasileira de moeda (R$ 1.000,00)
        valor_total = f"R$ {total_faturado:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
        media_hora = f"R$ {media_por_hora:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
        
        horas_fmt = int(total_horas)
        minutos_fmt = int((total_horas - horas_fmt) * 60)
        tempo_formatado = f"{horas_fmt}h {minutos_fmt}min"
        
        # --- Criação do Embed ---
        embed = discord.Embed(color=0xffa500)
        embed.title = f"💰 Faturamento de @{self.nome_mediador}"
        
        periodo_texto = "Hoje" if dias == 1 else f"{dias} dias"
        
        embed.add_field(name="Periodo", value=f"`{periodo_texto}`", inline=False)
        embed.add_field(name="Total", value=f"`{valor_total}`", inline=False)
        embed.add_field(name="Horas trabalhadas", value=f"`{tempo_formatado}`", inline=False)
        embed.add_field(name="Média por hora", value=f"`{media_hora}`", inline=False)
        
        embed.set_thumbnail(url=self.avatar_url)
        return embed
    
    async def atualizar_faturamento(self, interaction: discord.Interaction, dias: int):
        embed = await self.gerar_embed(dias)
        await interaction.response.edit_message(embed=embed, view=self)

    # --- Botões ---
    @discord.ui.button(label="Hoje", style=discord.ButtonStyle.primary)
    async def botao_hoje(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.atualizar_faturamento(interaction, 1)

    @discord.ui.button(label="3 dias", style=discord.ButtonStyle.primary)
    async def botao_3dias(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.atualizar_faturamento(interaction, 3)

    @discord.ui.button(label="7 dias", style=discord.ButtonStyle.primary)
    async def botao_7dias(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.atualizar_faturamento(interaction, 7)




class RelatorioGeralView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Gerar Relatório Geral (TXT)", style=discord.ButtonStyle.primary)
    async def gerar_relatorio_txt(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        
        try:
            collection = db.get_collection("matches")
            
            # 🔍 --- DEPURAR UM DOCUMENTO ---
            documento_exemplo = await collection.find_one({})
            if documento_exemplo:
                logger.info(f"🔍 DEBUG: Estrutura real no banco: {documento_exemplo}")
            else:
                logger.warning("⚠️ DEBUG: A coleção 'matches' está vazia!")
            # -------------------------------

            # 🛠️ Define o limite de 30 dias atrás para relatório MENSAL
            data_atual = datetime.now(timezone.utc)
            limite_mensal = data_atual - timedelta(days=30)
            
            # Busca partidas finalizadas/canceladas, pagas E nos últimos 30 dias
            query = {
                "status": {"$in": ["finalizado", "cancelado"]},
                "pagamento_confirmado": True,
                "started_at": {"$gte": limite_mensal} # Filtro de data adicionado
            }
            
            cursor = collection.find(query)
            
            faturamento_por_mediador = {}
            total_geral = 0.0
            partidas_encontradas = 0

            async for partida in cursor:
                partidas_encontradas += 1
                # 🛡️ Pega como int para garantir consistência
                m_id = str(partida.get("mediator_id", "Desconhecido"))
                valor = float(partida.get("bet_value", 0.0))
                
                # Cálculo de tempo robusto
                inicio = partida.get("started_at")
                fim = partida.get("completed_at")
                segundos = 0
                
                if inicio:
                    if inicio.tzinfo is None:
                        inicio = inicio.replace(tzinfo=timezone.utc)
                    
                    if fim:
                        if fim.tzinfo is None:
                            fim = fim.replace(tzinfo=timezone.utc)
                        tempo = fim - inicio
                        segundos = max(0, tempo.total_seconds())
                    else:
                        # Se não finalizou oficialmente, calcula até agora
                        tempo = datetime.now(timezone.utc) - inicio
                        segundos = max(0, tempo.total_seconds())

                if m_id not in faturamento_por_mediador:
                    faturamento_por_mediador[m_id] = {"total": 0.0, "segundos": 0}
                
                faturamento_por_mediador[m_id]["total"] += valor
                faturamento_por_mediador[m_id]["segundos"] += segundos
                total_geral += valor

            logger.info(f"📊 DEBUG: Partidas mensais encontradas: {partidas_encontradas}")

            # --- Formatação do Arquivo TXT ---
            data_str = datetime.now().strftime("%d/%m/%Y %H:%M")
            linhas = [
                "============================================================",
                f"FATURAMENTO MENSAL - GERADO EM {data_str}",
                "============================================================",
                f"Período: Últimos 30 dias",
                f"Total de mediadores ativos: {len(faturamento_por_mediador)}",
                f"Faturamento Total da Plataforma: R$ {total_geral:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                "",
                "RANKING DE FATURAMENTO (POR LUCRO):",
                "------------------------------------------------------------",
                " Pos. | Mediador ID           | Faturamento   | Horas",
                "------------------------------------------------------------"
            ]

            # Ordena pelo faturamento
            ranking = sorted(faturamento_por_mediador.items(), key=lambda x: x[1]['total'], reverse=True)

            for i, (m_id, dados) in enumerate(ranking, 1):
                valor_fmt = f"R$ {dados['total']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
                horas = int(dados['segundos'] / 3600)
    
                # 🛠️ Formata a linha alinhada
                linhas.append(f"{i:3}° | {m_id:21} | {valor_fmt:13} | {horas}h")

            linhas.append("------------------------------------------------------------")
            conteudo_final = "\n".join(linhas)

            # --- Envio do Arquivo ---
            buffer = io.BytesIO(conteudo_final.encode('utf-8'))
            filename = f"relatorio_mensal_{datetime.now().strftime('%Y-%m-%d')}.txt"
            arquivo = discord.File(fp=buffer, filename=filename)
            
            await interaction.followup.send("✅ Relatório mensal gerado com sucesso!", file=arquivo, ephemeral=True)

        except Exception as e:
            logger.error(f"❌ Erro ao gerar TXT: {e}")
            await interaction.followup.send("❌ Ocorreu um erro ao processar os dados do banco.", ephemeral=True)