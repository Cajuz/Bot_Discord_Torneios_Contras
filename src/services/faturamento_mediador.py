# FATURAMENTO DOS MEDIADORES
# Este módulo é responsável por calcular o faturamento dos mediadores com base nas partidas de X1 realizadas, 
# e gerar um relatório mensal para cada mediador.
from datetime import datetime, timedelta
from typing import List, Dict
from utils.logger import logger

FATURAMENTO='pagamento_confirmado' # Campo que indica se o pagamento foi confirmado


class FaturamentoMediadorService:
    def __init__(self):
        self.faturamento_diario = {}   # Estrutura para armazenar faturamento diário por mediador
        self.farturamento_3dias = {}    # Estrutura para armazenar faturamento dos últimos 3 dias por mediador
        self.faturamento_7dias = {}    # Estrutura para armazenar faturamento dos últimos 7 dias por mediador
        # Simulação de dados de partidas e mediadores

    async def calcular_faturamento(self, partidas: List[Dict], mediadores: List[Dict]):
        """Calcula o faturamento dos mediadores com base nas partidas realizadas"""
        try:
            # Inicializa as estruturas de faturamento
            for mediador in mediadores:
                self.faturamento_diario[mediador['id']] = 0
                self.farturamento_3dias[mediador['id']] = 0
                self.faturamento_7dias[mediador['id']] = 0

            # Data atual para comparação
            data_atual = datetime.now()

            for partida in partidas:
                if partida[FATURAMENTO]:  # Verifica se o pagamento foi confirmado
                    mediador_id = partida['mediator_id']
                    valor_partida = partida['bet_value']  # Supondo que o valor da partida seja o valor do faturamento

                    # Atualiza faturamento diário
                    if (data_atual - partida['started_at']).days < 1:
                        self.faturamento_diario[mediador_id] += valor_partida

                    # Atualiza faturamento dos últimos 3 dias
                    if (data_atual - partida['started_at']).days < 3:
                        self.farturamento_3dias[mediador_id] += valor_partida

                    # Atualiza faturamento dos últimos 7 dias
                    if (data_atual - partida['started_at']).days < 7:
                        self.faturamento_7dias[mediador_id] += valor_partida

            logger.info("Faturamento calculado com sucesso.")
        except Exception as e:
            logger.error(f"Erro ao calcular faturamento: {e}")


import discord
from discord.ext import commands
from datetime import datetime, timedelta
from typing import List, Dict

# --- CONFIGURAÇÃO DE CAMPOS ---
FATURAMENTO_CAMPO = 'pagamento_confirmado'
MEDIATOR_ID_CAMPO = 'guild_id'
DATA_CAMPO = 'started_at'
VALOR_CAMPO = 'bet_value'

# --- 1. SERVICE: Lógica de Negócio ---
class FaturamentoMediadorService:
    def __init__(self):
        pass

    async def calcular_por_periodo(self, partidas: List[Dict], mediador_id: str, dias: int) -> float:
        """Calcula o total faturado por um mediador específico dentro de um número de dias."""
        total = 0.0
        data_atual = datetime.now()
        # Define a data limite baseada nos dias solicitados
        limite = data_atual - timedelta(days=dias)

        for partida in partidas:
            # --- FILTRO CORRIGIDO ---
            # Verifica: Pagamento OK E Mediador correto E Data dentro do limite
            if (partida.get(FATURAMENTO_CAMPO, False) and 
                str(partida[MEDIATOR_ID_CAMPO]) == str(mediador_id) and 
                partida[DATA_CAMPO] >= limite):
                
                total += partida.get(VALOR_CAMPO, 0.0)
        
        return total

    async def buscar_partidas_do_banco(colecao_db, mediador_id):
    # Agora a função recebe a coleção por parâmetro
        cursor = colecao_db.find({'guild_id': mediador_id})
        partidas = []
        async for documento in cursor:
            partidas.append(documento)
        return partidas
    
# --- 2. VIEW: Interface de Botões (Interatividade) ---
class FaturamentoView(discord.ui.View):
    def __init__(self, service: FaturamentoMediadorService, partidas: List[Dict], mediador_id: str, nome_mediador: str, avatar_url: str):
        super().__init__(timeout=None) # Timeout=None faz os botões funcionarem para sempre
        self.service = service
        self.partidas = partidas
        self.mediador_id = mediador_id
        self.nome_mediador = nome_mediador
        self.avatar_url = avatar_url

    async def atualizar_faturamento(self, interaction: discord.Interaction, dias: int):
        # 1. Recalcula o valor com base no novo período
        total = await self.service.calcular_por_periodo(self.partidas, self.mediador_id, dias)

        
        # 2. Formatação para o padrão brasileiro R$ 0.000,00
        valor_formatado = f"R$ {total:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
        
        # 3. Cria o Embed
        embed = discord.Embed(color=0xffa500) # Cor Laranja
        embed.title = f"Faturamento de @{self.nome_mediador}"
        embed.set_author(name=self.nome_mediador, icon_url=self.avatar_url)

        
        periodo_texto = "Hoje" if dias == 1 else f"{dias} dias"
        
        # Adiciona campos conforme a imagem (APENAS PERÍODO E TOTAL)
        embed.add_field(name="Período", value=f"`{periodo_texto}`", inline=False)
        embed.add_field(name="Total", value=f"`{valor_formatado}`", inline=False)
        
        # --- CAMPOS DE HORAS REMOVIDOS ---
        
        embed.set_footer(text="Página 3 de 3")
        embed.set_thumbnail(url=self.avatar_url)

        # 4. Edita a mensagem original com os novos dados
        await interaction.response.edit_message(embed=embed, view=self)

    # --- Definição dos Botões ---
    @discord.ui.button(label="Hoje", style=discord.ButtonStyle.secondary)
    async def botao_hoje(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.atualizar_faturamento(interaction, 1)

    @discord.ui.button(label="3 dias", style=discord.ButtonStyle.secondary)
    async def botao_3dias(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.atualizar_faturamento(interaction, 3)

    @discord.ui.button(label="7 dias", style=discord.ButtonStyle.secondary)
    async def botao_7dias(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.atualizar_faturamento(interaction, 7)


