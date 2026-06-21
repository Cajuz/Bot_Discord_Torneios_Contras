import io
import discord

from datetime import datetime, timedelta, timezone
from config.database import db
from utils.logger import logger
from utils.datetime_utils import utcnow


# ── Campos do documento ───────────────────────────────────────────────────────
CAMPO_MEDIADOR_ID       = "mediator_id"
CAMPO_DATA_INICIO       = "created_at"       # FIX: era started_at — mas created_at é o campo garantido no modelo
CAMPO_DATA_FIM          = "completed_at"
CAMPO_VALOR             = "bet_value"
CAMPO_STATUS            = "status"
CAMPO_COMISSAO_PLAYER   = "commission_per_player"
CAMPO_COMISSAO_TOTAL    = "commission_total"
CAMPO_PLAYER_IDS        = "player_ids"

# ── Status válidos ────────────────────────────────────────────────────────────
STATUS_FINALIZADO_LIST = [
    "aguardando_premio",
    "finalizado",
    "concluido",
]
STATUS_CANCELADO_LIST = [
    "cancelado",
]
STATUS_VALIDOS = STATUS_FINALIZADO_LIST + STATUS_CANCELADO_LIST


# ══════════════════════════════════════════════════════════════════════════════
# Service
# ══════════════════════════════════════════════════════════════════════════════

class FaturamentoMediadorService:

    async def buscar_partidas_do_banco(self, discord_id: str, dias: int = 30):
        """
        Busca partidas do mediador diretamente no banco já filtradas por período.
        FIX: antes buscava TODAS as partidas e filtrava em Python — muito lento.
        Agora usa query com índice.
        """
        try:
            collection = db.get_collection("matches")
            since      = utcnow() - timedelta(days=dias)

            cursor = collection.find({
                CAMPO_MEDIADOR_ID: str(discord_id),
                CAMPO_STATUS:      {"$in": STATUS_VALIDOS},
                CAMPO_DATA_INICIO: {"$gte": since},         # FIX: filtra no banco
            })

            partidas = await cursor.to_list(length=None)
            logger.info(
                f"[Faturamento] {len(partidas)} partidas para mediator_id={discord_id} "
                f"nos últimos {dias} dias"
            )
            return partidas

        except Exception as e:
            logger.error(f"[Faturamento] Erro ao buscar partidas: {e}")
            return []

    async def calcular_stats(self, partidas: list, mediador_id: str) -> dict:
        """
        Calcula todas as estatísticas de faturamento de uma lista de partidas.
        Separa finalizadas de canceladas. Inclui totais de comissão.
        """
        now = utcnow()

        total_faturado       = 0.0
        total_segundos       = 0
        finalizadas          = 0
        canceladas           = 0
        vol_canceladas       = 0.0
        total_comissao       = 0.0   # soma das comissões cobradas (finalizadas)
        total_comissao_canc  = 0.0   # comissão de canceladas (informativo)

        for p in partidas:
            if str(p.get(CAMPO_MEDIADOR_ID, "")) != str(mediador_id):
                continue

            status    = p.get(CAMPO_STATUS, "")
            valor     = float(p.get(CAMPO_VALOR, 0) or 0)
            comissao  = float(p.get(CAMPO_COMISSAO_TOTAL) or 0)

            # ── Canceladas ───────────────────────────────────────────────────
            if status in STATUS_CANCELADO_LIST:
                canceladas           += 1
                vol_canceladas       += valor
                total_comissao_canc  += comissao
                continue

            # ── Finalizadas ──────────────────────────────────────────────────
            if status not in STATUS_FINALIZADO_LIST:
                continue

            finalizadas      += 1
            total_faturado   += valor
            total_comissao   += comissao

            inicio = p.get(CAMPO_DATA_INICIO)
            fim    = p.get(CAMPO_DATA_FIM) or now
            if inicio:
                if inicio.tzinfo is None:
                    inicio = inicio.replace(tzinfo=timezone.utc)
                if fim.tzinfo is None:
                    fim = fim.replace(tzinfo=timezone.utc)
                delta = (fim - inicio).total_seconds()
                if delta > 0:
                    total_segundos += int(delta)

        total_horas    = total_segundos / 3600
        media_por_hora = total_faturado / total_horas if total_horas > 0 else 0.0

        return {
            "total_faturado":      total_faturado,
            "finalizadas":         finalizadas,
            "canceladas":          canceladas,
            "vol_canceladas":      vol_canceladas,
            "total_horas":         total_horas,
            "media_por_hora":      media_por_hora,
            "total_comissao":      total_comissao,
            "total_comissao_canc": total_comissao_canc,
        }


# ══════════════════════════════════════════════════════════════════════════════
# Helpers de formatação
# ══════════════════════════════════════════════════════════════════════════════

def _brl(v: float) -> str:
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def _horas(total_horas: float) -> str:
    h = int(total_horas)
    m = int((total_horas - h) * 60)
    return f"{h}h {m}min"


# ══════════════════════════════════════════════════════════════════════════════
# View
# ══════════════════════════════════════════════════════════════════════════════

class FaturamentoView(discord.ui.View):
    def __init__(
        self,
        service:       FaturamentoMediadorService,
        mediador_id:   str,
        nome_mediador: str,
        avatar_url:    str,
    ):
        super().__init__(timeout=180)
        self.service       = service
        self.mediador_id   = str(mediador_id)
        self.nome_mediador = nome_mediador
        self.avatar_url    = avatar_url

    async def gerar_embed(self, dias: int) -> discord.Embed:
        # FIX: busca já filtrada no banco pelo período correto
        partidas = await self.service.buscar_partidas_do_banco(self.mediador_id, dias)
        stats    = await self.service.calcular_stats(partidas, self.mediador_id)

        periodo_texto = "Hoje" if dias == 1 else f"Últimos {dias} dias"

        embed = discord.Embed(
            title = f"💰 Faturamento — @{self.nome_mediador}",
            color = 0xFFA500,
        )
        if self.avatar_url:
            embed.set_thumbnail(url=self.avatar_url)

        embed.add_field(name="📅 Período",           value=f"`{periodo_texto}`",                     inline=False)
        embed.add_field(name="✅ Finalizadas",        value=f"`{stats['finalizadas']} partidas`",     inline=True)
        embed.add_field(name="❌ Canceladas",         value=f"`{stats['canceladas']} partidas`",      inline=True)
        embed.add_field(name="\u200b",               value="\u200b",                                 inline=True)  # spacer
        embed.add_field(name="💵 Total faturado",    value=f"`{_brl(stats['total_faturado'])}`",     inline=True)
        embed.add_field(name="🏦 Comissão arrecadada", value=f"`{_brl(stats['total_comissao'])}`",   inline=True)
        embed.add_field(name="🚫 Vol. canceladas",   value=f"`{_brl(stats['vol_canceladas'])}`",     inline=True)
        embed.add_field(name="⏱️ Horas trabalhadas", value=f"`{_horas(stats['total_horas'])}`",      inline=True)
        embed.add_field(name="📈 Média por hora",    value=f"`{_brl(stats['media_por_hora'])}`",     inline=True)
        if stats["total_comissao_canc"] > 0:
            embed.add_field(
                name="🏦 Comissão s/ canceladas",
                value=f"`{_brl(stats['total_comissao_canc'])}`",
                inline=True,
            )

        embed.set_footer(text=f"Atualizado {utcnow().strftime('%d/%m/%Y %H:%M')} UTC")
        return embed

    async def _atualizar(self, interaction: discord.Interaction, dias: int):
        await interaction.response.defer()
        embed = await self.gerar_embed(dias)
        await interaction.edit_original_response(embed=embed, view=self)

    @discord.ui.button(label="Hoje",   style=discord.ButtonStyle.primary,   custom_id="fat_hoje")
    async def botao_hoje(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._atualizar(interaction, 1)

    @discord.ui.button(label="3 dias", style=discord.ButtonStyle.secondary, custom_id="fat_3dias")
    async def botao_3dias(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._atualizar(interaction, 3)

    @discord.ui.button(label="7 dias", style=discord.ButtonStyle.secondary, custom_id="fat_7dias")
    async def botao_7dias(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._atualizar(interaction, 7)

    @discord.ui.button(label="30 dias", style=discord.ButtonStyle.secondary, custom_id="fat_30dias")
    async def botao_30dias(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._atualizar(interaction, 30)


# ══════════════════════════════════════════════════════════════════════════════
# Relatório Geral (TXT)
# ══════════════════════════════════════════════════════════════════════════════

class RelatorioGeralView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label     = "Gerar Relatório Geral (TXT)",
        style     = discord.ButtonStyle.secondary,
        custom_id = "relatorio_geral_txt",
    )
    async def gerar_relatorio_txt(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)

        try:
            collection = db.get_collection("matches")
            since      = utcnow() - timedelta(days=30)

            # FIX: não filtra mais por pagamento_confirmado (campo removido do modelo)
            # FIX: inclui canceladas no relatório separadas
            cursor = collection.find({
                CAMPO_STATUS:      {"$in": STATUS_VALIDOS},
                CAMPO_DATA_INICIO: {"$gte": since},
            })

            faturamento_por_mediador: dict[str, dict] = {}
            total_geral           = 0.0
            total_canceladas      = 0
            total_fin             = 0
            total_comissao_geral  = 0.0

            async for p in cursor:
                m_id     = str(p.get(CAMPO_MEDIADOR_ID) or "Desconhecido")
                valor    = float(p.get(CAMPO_VALOR, 0) or 0)
                status   = p.get(CAMPO_STATUS, "")
                comissao = float(p.get(CAMPO_COMISSAO_TOTAL) or 0)

                if m_id not in faturamento_por_mediador:
                    faturamento_por_mediador[m_id] = {
                        "total":      0.0,
                        "segundos":   0,
                        "fin":        0,
                        "canc":       0,
                        "vol_canc":   0.0,
                        "comissao":   0.0,
                    }

                entry = faturamento_por_mediador[m_id]

                if status in STATUS_CANCELADO_LIST:
                    entry["canc"]     += 1
                    entry["vol_canc"] += valor
                    total_canceladas  += 1
                    continue

                # finalizadas
                entry["fin"]     += 1
                entry["total"]   += valor
                entry["comissao"] += comissao
                total_geral      += valor
                total_fin        += 1
                total_comissao_geral += comissao

                inicio = p.get(CAMPO_DATA_INICIO)
                fim    = p.get(CAMPO_DATA_FIM)
                now    = utcnow()
                if inicio:
                    if inicio.tzinfo is None:
                        inicio = inicio.replace(tzinfo=timezone.utc)
                    fim = fim or now
                    if fim.tzinfo is None:
                        fim = fim.replace(tzinfo=timezone.utc)
                    delta = (fim - inicio).total_seconds()
                    if delta > 0:
                        entry["segundos"] += int(delta)

            logger.info(
                f"[Faturamento] Relatório: {total_fin} finalizadas, "
                f"{total_canceladas} canceladas, {len(faturamento_por_mediador)} mediadores"
            )

            data_str = datetime.now().strftime("%d/%m/%Y %H:%M")
            linhas = [
                "=" * 76,
                f"FATURAMENTO MENSAL — GERADO EM {data_str}",
                "=" * 76,
                f"Período:              Últimos 30 dias",
                f"Mediadores ativos:    {len(faturamento_por_mediador)}",
                f"Partidas finalizadas: {total_fin}",
                f"Partidas canceladas:  {total_canceladas}",
                f"Faturamento total:    {_brl(total_geral)}",
                f"Comissão total:       {_brl(total_comissao_geral)}",
                "",
                "RANKING POR FATURAMENTO:",
                "-" * 76,
                f"{'Pos':>3} | {'Mediador ID':<22} | {'Faturado':>13} | {'Comissão':>12} | {'Fin':>4} | {'Canc':>4} | {'Horas':>6}",
                "-" * 76,
            ]

            ranking = sorted(
                faturamento_por_mediador.items(),
                key=lambda x: x[1]["total"],
                reverse=True,
            )

            for i, (m_id, d) in enumerate(ranking, 1):
                horas        = int(d["segundos"] / 3600)
                valor_fmt    = _brl(d["total"])
                comissao_fmt = _brl(d["comissao"])
                linhas.append(
                    f"{i:3}° | {m_id:<22} | {valor_fmt:>13} | {comissao_fmt:>12} | {d['fin']:>4} | {d['canc']:>4} | {horas:>5}h"
                )

            linhas += [
                "-" * 76,
                "",
                "DETALHES DE CANCELAMENTOS:",
                "-" * 76,
            ]
            for m_id, d in ranking:
                if d["canc"] > 0:
                    linhas.append(
                        f"  {m_id} — {d['canc']} canceladas | Vol: {_brl(d['vol_canc'])}"
                    )

            conteudo = "\n".join(linhas)
            buffer   = io.BytesIO(conteudo.encode("utf-8"))
            filename = f"relatorio_mensal_{datetime.now().strftime('%Y-%m-%d')}.txt"

            await interaction.followup.send(
                "✅ Relatório mensal gerado!",
                file    = discord.File(fp=buffer, filename=filename),
                ephemeral = True,
            )

        except Exception as e:
            logger.error(f"[Faturamento] Erro ao gerar TXT: {e}")
            await interaction.followup.send(
                "❌ Erro ao processar os dados do banco.",
                ephemeral=True,
            )
