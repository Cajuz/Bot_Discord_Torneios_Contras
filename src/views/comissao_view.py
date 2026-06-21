"""comissao_view.py — Painéis da categoria 💼 | COMISSÃO.

Dois painéis (painel-comissao foi removido):
  1. #historico-comissao  → Log automático de pagamentos (somente ADM/bot)
  2. #comissao-controle   → ADM: config atual de comissão + edição + ver pendentes + pagar
"""
from __future__ import annotations

import discord
from discord.ui import View, button, Button
from utils.logger import logger


# ══════════════════════════════════════════════════════════
# EMBEDS
# ══════════════════════════════════════════════════════════

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


async def build_comissao_admin_embed(guild_id: str | None = None) -> discord.Embed:
    """Monta o embed do painel de controle com a config atual de comissão."""
    from services.commission_service import commission_service, DEFAULT_MATCH, DEFAULT_LIVE

    if guild_id:
        cfg = await commission_service.get_config(guild_id)
        match = cfg["match"]
        live  = cfg["live"]
    else:
        match = DEFAULT_MATCH
        live  = DEFAULT_LIVE

    def fmt(scheme: dict) -> str:
        threshold = scheme.get("fixed_threshold", 20.0)
        fee       = scheme.get("fixed_fee", 2.0)
        pct       = scheme.get("pct", 0.10)
        return (
            f"Limite taxa fixa: **R$ {threshold:.2f}**\n"
            f"Taxa fixa (por jogador): **R$ {fee:.2f}**\n"
            f"Percentual (aposta > limite): **{pct * 100:.1f}%**"
        )

    embed = discord.Embed(
        title="🔐 Controle de Comissões — ADM",
        description="Configuração atual e gestão de pagamentos dos mediadores.",
        color=0xFF6B35,
    )
    embed.add_field(name="⚔️ Stand (partidas normais)", value=fmt(match), inline=False)
    embed.add_field(name="🎥 Influencer Live",           value=fmt(live),  inline=False)
    embed.add_field(
        name="Ações disponíveis",
        value=(
            "✏️ **Editar Stand** — altera taxa das partidas normais\n"
            "✏️ **Editar Live** — altera taxa das partidas de live\n"
            "🔍 **Ver Pendentes** — mediadores com saldo a pagar\n"
            "✅ **Marcar como Pago** — registra pagamento manual"
        ),
        inline=False,
    )
    embed.set_footer(text="SOLAR E-SPORTS · Comissão ADM · Restrito à administração")
    return embed


# ══════════════════════════════════════════════════════════
# VIEW — CONTROLE ADM
# ══════════════════════════════════════════════════════════

class ComissaoAdminView(View):
    """Painel ADM — config de comissão, ver pendentes, marcar como pago."""

    def __init__(self):
        super().__init__(timeout=None)

    # ── Editar Stand ──────────────────────────────────────
    @button(
        label="✏️ Editar Stand",
        style=discord.ButtonStyle.primary,
        custom_id="comissao:editar_match",
        row=0,
    )
    async def editar_match(self, interaction: discord.Interaction, btn: Button):
        from services.commission_service import commission_service
        cfg = await commission_service.get_match_config(str(interaction.guild_id))
        await interaction.response.send_modal(_EditarComissaoModal(
            tipo="match",
            current_threshold=cfg.get("fixed_threshold", 20.0),
            current_fee=cfg.get("fixed_fee", 2.0),
            current_pct=cfg.get("pct", 0.10),
        ))

    # ── Editar Live ───────────────────────────────────────
    @button(
        label="✏️ Editar Live",
        style=discord.ButtonStyle.primary,
        custom_id="comissao:editar_live",
        row=0,
    )
    async def editar_live(self, interaction: discord.Interaction, btn: Button):
        from services.commission_service import commission_service
        cfg = await commission_service.get_live_config(str(interaction.guild_id))
        await interaction.response.send_modal(_EditarComissaoModal(
            tipo="live",
            current_threshold=cfg.get("fixed_threshold", 20.0),
            current_fee=cfg.get("fixed_fee", 2.0),
            current_pct=cfg.get("pct", 0.10),
        ))

    # ── Ver pendentes ─────────────────────────────────────
    @button(
        label="🔍 Ver Pendentes",
        style=discord.ButtonStyle.secondary,
        custom_id="comissao:ver_pendentes",
        row=1,
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
                mid = d.get("mediador_id", "?")
                val = d.get("saldo_pendente", 0.0)
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

    # ── Marcar como pago ──────────────────────────────────
    @button(
        label="✅ Marcar como Pago",
        style=discord.ButtonStyle.success,
        custom_id="comissao:marcar_pago",
        row=1,
    )
    async def marcar_pago(self, interaction: discord.Interaction, btn: Button):
        await interaction.response.send_modal(_MarcarPagoModal())


# ══════════════════════════════════════════════════════════
# MODAL — Editar configuração de comissão
# ══════════════════════════════════════════════════════════

class _EditarComissaoModal(discord.ui.Modal):
    def __init__(
        self,
        tipo: str,           # "match" ou "live"
        current_threshold: float,
        current_fee: float,
        current_pct: float,
    ):
        label_tipo = "Stand (partidas normais)" if tipo == "match" else "Influencer Live"
        super().__init__(title=f"✏️ Editar Comissão — {label_tipo}")
        self.tipo = tipo

        self.threshold = discord.ui.TextInput(
            label="Limite taxa fixa (R$)",
            placeholder="Ex: 20.00",
            default=str(current_threshold),
            min_length=1,
            max_length=10,
        )
        self.fee = discord.ui.TextInput(
            label="Taxa fixa por jogador (R$)",
            placeholder="Ex: 2.00",
            default=str(current_fee),
            min_length=1,
            max_length=10,
        )
        self.pct = discord.ui.TextInput(
            label="Percentual (aposta > limite, ex: 10 = 10%)",
            placeholder="Ex: 10",
            default=str(round(current_pct * 100, 4)),
            min_length=1,
            max_length=10,
        )
        self.add_item(self.threshold)
        self.add_item(self.fee)
        self.add_item(self.pct)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            def parse(val: str) -> float:
                return float(val.strip().replace(",", "."))

            threshold_val = parse(self.threshold.value)
            fee_val       = parse(self.fee.value)
            pct_raw       = parse(self.pct.value)
            pct_val       = pct_raw / 100  # converte % para decimal

            if threshold_val < 0 or fee_val < 0 or pct_val < 0:
                await interaction.followup.send("❌ Valores não podem ser negativos.", ephemeral=True)
                return

            from services.commission_service import commission_service
            guild_id = str(interaction.guild_id)

            if self.tipo == "match":
                await commission_service.update_match(guild_id, threshold_val, fee_val, pct_val)
                tipo_label = "Stand (partidas normais)"
            else:
                await commission_service.update_live(guild_id, threshold_val, fee_val, pct_val)
                tipo_label = "Influencer Live"

            # Atualiza o embed do painel no canal comissao-controle
            from services.channel_service import COMISSAO_ADMIN_CHANNEL
            ch = discord.utils.get(interaction.guild.text_channels, name=COMISSAO_ADMIN_CHANNEL)
            if ch:
                novo_embed = await build_comissao_admin_embed(guild_id)
                async for msg in ch.history(limit=10):
                    if msg.author == interaction.guild.me and msg.embeds:
                        await msg.edit(embed=novo_embed)
                        break

            await interaction.followup.send(
                f"✅ **{tipo_label}** atualizado:\n"
                f"— Limite taxa fixa: **R$ {threshold_val:.2f}**\n"
                f"— Taxa fixa/jogador: **R$ {fee_val:.2f}**\n"
                f"— Percentual: **{pct_raw:.2f}%**",
                ephemeral=True,
            )

        except ValueError:
            await interaction.followup.send(
                "❌ Valor inválido. Use números com ponto ou vírgula (ex: 2.50 ou 2,50).",
                ephemeral=True,
            )
        except Exception as e:
            logger.error(f"[_EditarComissaoModal] on_submit erro: {e}", exc_info=True)
            await interaction.followup.send("Erro ao salvar configuração.", ephemeral=True)


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

            from services.channel_service import COMISSAO_HISTORICO_CHANNEL
            ch = discord.utils.get(interaction.guild.text_channels, name=COMISSAO_HISTORICO_CHANNEL)
            if ch:
                log_embed = discord.Embed(
                    title="✅ Comissão Paga",
                    color=0x2ECC71,
                )
                log_embed.add_field(name="Mediador", value=f"<@{mediador_id}>",      inline=True)
                log_embed.add_field(name="Valor",    value=f"R$ {valor_float:.2f}",  inline=True)
                log_embed.add_field(name="Pago por", value=interaction.user.mention, inline=True)
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
