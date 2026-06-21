"""comissao_view.py — Painéis da categoria 💼 | COMISSÃO.

Três painéis:
  1. #painel-comissao   → Mediador consulta sua própria comissão via botão
  2. #historico-comissao → Cabeçalho de log (bot posta entradas automaticamente)
  3. #comissao-controle  → ADM visualiza resumo e força pagamento manual
"""
from __future__ import annotations

import discord
from discord.ui import View, button, Button
from utils.logger import logger


# ══════════════════════════════════════════════════════════
# EMBEDS
# ══════════════════════════════════════════════════════════

def build_comissao_panel_embed() -> discord.Embed:
    embed = discord.Embed(
        title="💼 Minha Comissão",
        description=(
            "Clique no botão abaixo para consultar o saldo de comissão acumulado.\n\n"
            "As comissões são calculadas automaticamente ao final de cada partida "
            "mediada e ficam disponíveis para saque conforme as regras do servidor."
        ),
        color=0xFFD54F,
    )
    embed.set_footer(text="SOLAR E-SPORTS · Comissão · Consulta disponível para Mediadores")
    return embed


def build_comissao_historico_embed() -> discord.Embed:
    embed = discord.Embed(
        title="📋 Histórico de Comissões",
        description=(
            "Registro automático de todos os pagamentos e créditos de comissão.\n\n"
            "💰 **Crédito** — comissão adicionada após partida finalizada\n"
            "✅ **Pago** — saque processado pelo ADM\n\n"
            "Apenas o bot posta neste canal."
        ),
        color=0x2ECC71,
    )
    embed.set_footer(text="Apenas leitura — logs gerados automaticamente · SOLAR E-SPORTS")
    return embed


def build_comissao_admin_embed() -> discord.Embed:
    embed = discord.Embed(
        title="🔐 Controle de Comissões — ADM",
        description=(
            "Painel administrativo para gestão de comissões dos mediadores.\n\n"
            "🔍 **Ver Pendentes** — lista mediadores com saldo a pagar\n"
            "✅ **Marcar como Pago** — registra pagamento manual para um mediador\n"
            "📊 **Relatório Geral** — exporta resumo completo de comissões"
        ),
        color=0xFF6B35,
    )
    embed.set_footer(text="SOLAR E-SPORTS · Comissão ADM · Restrito à administração")
    return embed


# ══════════════════════════════════════════════════════════
# VIEWS
# ══════════════════════════════════════════════════════════

class ComissaoPanelView(View):
    """Painel público — Mediador consulta sua própria comissão."""

    def __init__(self):
        super().__init__(timeout=None)

    @button(
        label="💼 Ver Minha Comissão",
        style=discord.ButtonStyle.primary,
        custom_id="comissao:ver_minha",
    )
    async def ver_comissao(self, interaction: discord.Interaction, btn: Button):
        await interaction.response.defer(ephemeral=True)
        try:
            from config.database import db
            mediador_id = str(interaction.user.id)
            doc = await db.get_collection("comissoes").find_one({"mediador_id": mediador_id})

            if not doc:
                await interaction.followup.send(
                    "Você não possui comissões registradas ainda.", ephemeral=True
                )
                return

            saldo_pendente = doc.get("saldo_pendente", 0.0)
            total_recebido = doc.get("total_recebido", 0.0)
            partidas       = doc.get("partidas_mediadas", 0)

            embed = discord.Embed(
                title="💼 Sua Comissão",
                color=0xFFD54F,
            )
            embed.add_field(name="Saldo Pendente",   value=f"R$ {saldo_pendente:.2f}", inline=True)
            embed.add_field(name="Total Recebido",   value=f"R$ {total_recebido:.2f}", inline=True)
            embed.add_field(name="Partidas Mediadas", value=str(partidas),              inline=True)
            embed.set_footer(text="SOLAR E-SPORTS · Dados atualizados em tempo real")
            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"[ComissaoPanelView] ver_comissao erro: {e}", exc_info=True)
            await interaction.followup.send(
                "Erro ao consultar comissão. Tente novamente.", ephemeral=True
            )


class ComissaoAdminView(View):
    """Painel ADM — Ver pendentes, marcar como pago, relatório."""

    def __init__(self):
        super().__init__(timeout=None)

    # ── Ver pendentes ─────────────────────────────────────────
    @button(
        label="🔍 Ver Pendentes",
        style=discord.ButtonStyle.secondary,
        custom_id="comissao:ver_pendentes",
    )
    async def ver_pendentes(self, interaction: discord.Interaction, btn: Button):
        await interaction.response.defer(ephemeral=True)
        try:
            from config.database import db
            cursor = db.get_collection("comissoes").find(
                {"saldo_pendente": {"$gt": 0}}
            ).sort("saldo_pendente", -1).limit(20)
            docs = await cursor.to_list(length=20)

            if not docs:
                await interaction.followup.send("Nenhum mediador com saldo pendente.", ephemeral=True)
                return

            linhas = []
            for d in docs:
                mid  = d.get("mediador_id", "?")
                nome = d.get("nome", mid)
                val  = d.get("saldo_pendente", 0.0)
                linhas.append(f"<@{mid}> — **R$ {val:.2f}**")

            embed = discord.Embed(
                title="🔍 Comissões Pendentes",
                description="\n".join(linhas),
                color=0xFFD54F,
            )
            embed.set_footer(text=f"{len(docs)} mediador(es) com saldo a pagar")
            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"[ComissaoAdminView] ver_pendentes erro: {e}", exc_info=True)
            await interaction.followup.send("Erro ao buscar pendentes.", ephemeral=True)

    # ── Marcar como pago ──────────────────────────────────────
    @button(
        label="✅ Marcar como Pago",
        style=discord.ButtonStyle.success,
        custom_id="comissao:marcar_pago",
    )
    async def marcar_pago(self, interaction: discord.Interaction, btn: Button):
        await interaction.response.send_modal(_MarcarPagoModal())

    # ── Relatório geral ───────────────────────────────────────
    @button(
        label="📊 Relatório Geral",
        style=discord.ButtonStyle.primary,
        custom_id="comissao:relatorio",
    )
    async def relatorio(self, interaction: discord.Interaction, btn: Button):
        await interaction.response.defer(ephemeral=True)
        try:
            from config.database import db
            from utils.datetime_utils import utcnow

            cursor = db.get_collection("comissoes").find({}).sort("saldo_pendente", -1).limit(50)
            docs   = await cursor.to_list(length=50)

            if not docs:
                await interaction.followup.send("Nenhuma comissão registrada.", ephemeral=True)
                return

            total_pendente  = sum(d.get("saldo_pendente", 0.0)  for d in docs)
            total_pago      = sum(d.get("total_recebido", 0.0)  for d in docs)
            total_partidas  = sum(d.get("partidas_mediadas", 0) for d in docs)

            embed = discord.Embed(
                title="📊 Relatório Geral de Comissões",
                color=0xFF6B35,
            )
            embed.add_field(name="Total Pendente",    value=f"R$ {total_pendente:.2f}",  inline=True)
            embed.add_field(name="Total Já Pago",     value=f"R$ {total_pago:.2f}",      inline=True)
            embed.add_field(name="Partidas Mediadas", value=str(total_partidas),          inline=True)
            embed.add_field(name="Mediadores",        value=str(len(docs)),               inline=True)
            embed.set_footer(text=f"Gerado em {utcnow().strftime('%d/%m/%Y %H:%M')} UTC · SOLAR E-SPORTS")
            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"[ComissaoAdminView] relatorio erro: {e}", exc_info=True)
            await interaction.followup.send("Erro ao gerar relatório.", ephemeral=True)


# ══════════════════════════════════════════════════════════
# MODAL — Marcar como Pago
# ══════════════════════════════════════════════════════════

class _MarcarPagoModal(discord.ui.Modal, title="Marcar Comissão como Paga"):
    discord_id = discord.ui.TextInput(
        label="Discord ID do Mediador",
        placeholder="Ex: 123456789012345678",
        min_length=17,
        max_length=20,
    )
    valor = discord.ui.TextInput(
        label="Valor Pago (R$)",
        placeholder="Ex: 50.00",
        min_length=1,
        max_length=10,
    )
    observacao = discord.ui.TextInput(
        label="Observação (opcional)",
        placeholder="Ex: Pix enviado às 14h",
        required=False,
        max_length=200,
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            from config.database import db
            from utils.datetime_utils import utcnow

            mediador_id = self.discord_id.value.strip()
            try:
                valor_float = float(self.valor.value.replace(",", "."))
            except ValueError:
                await interaction.followup.send("Valor inválido. Use ponto ou vírgula decimal.", ephemeral=True)
                return

            col = db.get_collection("comissoes")
            doc = await col.find_one({"mediador_id": mediador_id})
            if not doc:
                await interaction.followup.send("Mediador não encontrado na base de comissões.", ephemeral=True)
                return

            agora = utcnow()
            await col.update_one(
                {"mediador_id": mediador_id},
                {
                    "$inc": {"total_recebido": valor_float, "saldo_pendente": -valor_float},
                    "$push": {
                        "pagamentos": {
                            "valor": valor_float,
                            "pago_por": str(interaction.user.id),
                            "data": agora,
                            "obs": self.observacao.value or "",
                        }
                    },
                    "$set": {"updated_at": agora},
                },
            )

            # Log no canal historico-comissao
            from services.channel_service import COMISSAO_HISTORICO_CHANNEL
            ch = discord.utils.get(interaction.guild.text_channels, name=COMISSAO_HISTORICO_CHANNEL)
            if ch:
                log_embed = discord.Embed(
                    title="✅ Comissão Paga",
                    color=0x2ECC71,
                )
                log_embed.add_field(name="Mediador", value=f"<@{mediador_id}>",           inline=True)
                log_embed.add_field(name="Valor",    value=f"R$ {valor_float:.2f}",       inline=True)
                log_embed.add_field(name="Pago por", value=interaction.user.mention,      inline=True)
                if self.observacao.value:
                    log_embed.add_field(name="Obs", value=self.observacao.value, inline=False)
                log_embed.set_footer(text=agora.strftime("%d/%m/%Y %H:%M") + " UTC")
                await ch.send(embed=log_embed)

            await interaction.followup.send(
                f"✅ Pagamento de **R$ {valor_float:.2f}** registrado para <@{mediador_id}>.",
                ephemeral=True,
            )

        except Exception as e:
            logger.error(f"[_MarcarPagoModal] on_submit erro: {e}", exc_info=True)
            await interaction.followup.send("Erro ao registrar pagamento.", ephemeral=True)
