import io
import discord

from datetime import datetime, timedelta, timezone
from config.database import db
from utils.logger import logger


CAMPO_PAGAMENTO_CONFIRMADO = "pagamento_confirmado"
CAMPO_MEDIADOR_ID = "mediator_id"
CAMPO_DATA_INICIO = "started_at"
CAMPO_DATA_FIM = "completed_at"
CAMPO_VALOR = "bet_value"
CAMPO_STATUS = "status"

STATUS_CONCLUIDO = "finalizado"
STATUS_CANCELADO = "cancelado"


class FaturamentoMediadorService:
    async def buscar_partidas_do_banco(self, discord_id: str):
        try:
            collection = db.get_collection("matches")
            cursor = collection.find({CAMPO_MEDIADOR_ID: str(discord_id)})

            partidas = []
            async for documento in cursor:
                partidas.append(documento)

            logger.info(f"[Faturamento] Encontradas {len(partidas)} partidas para mediator_id={discord_id}")
            return partidas

        except Exception as e:
            logger.error(f"[Faturamento] Erro ao buscar partidas no banco: {e}")
            return []


class FaturamentoView(discord.ui.View):
    def __init__(self, service: FaturamentoMediadorService, partidas: list, mediador_id: str, nome_mediador: str, avatar_url: str):
        super().__init__(timeout=180)
        self.service = service
        self.partidas = partidas
        self.mediador_id = str(mediador_id)
        self.nome_mediador = nome_mediador
        self.avatar_url = avatar_url

    async def gerar_embed(self, dias: int) -> discord.Embed:
        total_faturado = 0.0
        total_segundos_trabalhados = 0

        agora = datetime.now(timezone.utc)
        limite = agora - timedelta(days=dias)

        for partida in self.partidas:
            id_mediador_partida = str(partida.get(CAMPO_MEDIADOR_ID, ""))
            status_partida = partida.get(CAMPO_STATUS)

            status_valido = status_partida in [STATUS_CONCLUIDO, STATUS_CANCELADO]
            pagamento_ok = partida.get(CAMPO_PAGAMENTO_CONFIRMADO, False) is True

            if id_mediador_partida != self.mediador_id:
                continue
            if not pagamento_ok:
                continue
            if not status_valido:
                continue

            data_inicio = partida.get(CAMPO_DATA_INICIO)
            if not data_inicio:
                continue

            if data_inicio.tzinfo is None:
                data_inicio = data_inicio.replace(tzinfo=timezone.utc)

            if data_inicio < limite:
                continue

            valor = float(partida.get(CAMPO_VALOR, 0.0) or 0.0)
            total_faturado += valor

            data_fim = partida.get(CAMPO_DATA_FIM) or agora
            if data_fim.tzinfo is None:
                data_fim = data_fim.replace(tzinfo=timezone.utc)

            tempo_partida = data_fim - data_inicio
            if tempo_partida.total_seconds() > 0:
                total_segundos_trabalhados += int(tempo_partida.total_seconds())

        total_horas = total_segundos_trabalhados / 3600
        media_por_hora = total_faturado / total_horas if total_horas > 0 else 0.0

        valor_total = f"R$ {total_faturado:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        media_hora = f"R$ {media_por_hora:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        horas_fmt = int(total_horas)
        minutos_fmt = int((total_horas - horas_fmt) * 60)
        tempo_formatado = f"{horas_fmt}h {minutos_fmt}min"

        embed = discord.Embed(color=0xFFA500)
        embed.title = f"💰 Faturamento de @{self.nome_mediador}"

        periodo_texto = "Hoje" if dias == 1 else f"Últimos {dias} dias"
        embed.add_field(name="Período", value=f"`{periodo_texto}`", inline=False)
        embed.add_field(name="Total", value=f"`{valor_total}`", inline=False)
        embed.add_field(name="Horas trabalhadas", value=f"`{tempo_formatado}`", inline=False)
        embed.add_field(name="Média por hora", value=f"`{media_hora}`", inline=False)

        if self.avatar_url:
            embed.set_thumbnail(url=self.avatar_url)

        return embed

    async def atualizar_faturamento(self, interaction: discord.Interaction, dias: int):
        embed = await self.gerar_embed(dias)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Hoje", style=discord.ButtonStyle.primary, custom_id="faturamento_hoje")
    async def botao_hoje(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.atualizar_faturamento(interaction, 1)

    @discord.ui.button(label="3 dias", style=discord.ButtonStyle.primary, custom_id="faturamento_3dias")
    async def botao_3dias(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.atualizar_faturamento(interaction, 3)

    @discord.ui.button(label="7 dias", style=discord.ButtonStyle.primary, custom_id="faturamento_7dias")
    async def botao_7dias(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.atualizar_faturamento(interaction, 7)


class RelatorioGeralView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Gerar Relatório Geral (TXT)",
        style=discord.ButtonStyle.primary,
        custom_id="relatorio_geral_txt"
    )
    async def gerar_relatorio_txt(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)

        try:
            collection = db.get_collection("matches")
            data_atual = datetime.now(timezone.utc)
            limite_mensal = data_atual - timedelta(days=30)

            query = {
                CAMPO_STATUS: {"$in": [STATUS_CONCLUIDO, STATUS_CANCELADO]},
                CAMPO_PAGAMENTO_CONFIRMADO: True,
                CAMPO_DATA_INICIO: {"$gte": limite_mensal}
            }

            cursor = collection.find(query)

            faturamento_por_mediador = {}
            total_geral = 0.0
            partidas_encontradas = 0

            async for partida in cursor:
                partidas_encontradas += 1

                m_id = str(partida.get(CAMPO_MEDIADOR_ID, "Desconhecido"))
                valor = float(partida.get(CAMPO_VALOR, 0.0) or 0.0)

                inicio = partida.get(CAMPO_DATA_INICIO)
                fim = partida.get(CAMPO_DATA_FIM)
                segundos = 0

                if inicio:
                    if inicio.tzinfo is None:
                        inicio = inicio.replace(tzinfo=timezone.utc)

                    if fim:
                        if fim.tzinfo is None:
                            fim = fim.replace(tzinfo=timezone.utc)
                        segundos = max(0, int((fim - inicio).total_seconds()))
                    else:
                        segundos = max(0, int((datetime.now(timezone.utc) - inicio).total_seconds()))

                if m_id not in faturamento_por_mediador:
                    faturamento_por_mediador[m_id] = {"total": 0.0, "segundos": 0}

                faturamento_por_mediador[m_id]["total"] += valor
                faturamento_por_mediador[m_id]["segundos"] += segundos
                total_geral += valor

            logger.info(f"[Faturamento] Partidas mensais encontradas: {partidas_encontradas}")

            data_str = datetime.now().strftime("%d/%m/%Y %H:%M")
            linhas = [
                "============================================================",
                f"FATURAMENTO MENSAL - GERADO EM {data_str}",
                "============================================================",
                "Período: Últimos 30 dias",
                f"Total de mediadores ativos no relatório: {len(faturamento_por_mediador)}",
                f"Faturamento Total da Plataforma: R$ {total_geral:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
                "",
                "RANKING DE FATURAMENTO (POR LUCRO):",
                "------------------------------------------------------------",
                " Pos. | Mediador ID           | Faturamento   | Horas",
                "------------------------------------------------------------"
            ]

            ranking = sorted(
                faturamento_por_mediador.items(),
                key=lambda x: x[1]["total"],
                reverse=True
            )

            for i, (m_id, dados) in enumerate(ranking, 1):
                valor_fmt = f"R$ {dados['total']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                horas = int(dados["segundos"] / 3600)
                linhas.append(f"{i:3}° | {m_id:21} | {valor_fmt:13} | {horas}h")

            linhas.append("------------------------------------------------------------")
            conteudo_final = "\n".join(linhas)

            buffer = io.BytesIO(conteudo_final.encode("utf-8"))
            filename = f"relatorio_mensal_{datetime.now().strftime('%Y-%m-%d')}.txt"
            arquivo = discord.File(fp=buffer, filename=filename)

            await interaction.followup.send(
                "✅ Relatório mensal gerado com sucesso!",
                file=arquivo,
                ephemeral=True
            )

        except Exception as e:
            logger.error(f"[Faturamento] Erro ao gerar TXT: {e}")
            await interaction.followup.send(
                "❌ Ocorreu um erro ao processar os dados do banco.",
                ephemeral=True
            )
