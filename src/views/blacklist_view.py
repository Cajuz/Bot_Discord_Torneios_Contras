"""
blacklist_view.py

Painel de verificação de blacklist — disponível para todos os membros.

Botões:
  🔍 Verificar Minha Situação  — ephemeral, consulta o próprio discord_id
  🔎 Buscar por Discord ID     — abre Modal para informar qualquer ID
"""
from __future__ import annotations

import discord
from utils.logger import logger
from utils.datetime_utils import utcnow

COLOR_BLACKLISTED = 0xE74C3C  # vermelho
COLOR_CLEAN       = 0x27AE60  # verde
COLOR_PANEL       = 0x992D22  # bordô do painel


# ════════════════════════════════════════════════════════
# Helper — consulta ao banco
# ════════════════════════════════════════════════════════

async def _check_blacklist(discord_id: str) -> dict | None:
    """
    Retorna o documento da blacklist se o usuário estiver listado,
    None caso contrário.
    Verifica as coleções 'blacklist' e 'exposed' (legacy).
    """
    try:
        from config.database import db
        doc = await db.get_collection("blacklist").find_one({"discord_id": discord_id})
        if doc:
            return doc
        doc = await db.get_collection("exposed").find_one({"discord_id": discord_id})
        return doc
    except Exception as e:
        logger.warning(f"[BlacklistView] check_blacklist erro: {e}")
        return None


def _build_result_embed(target_id: str, doc: dict | None, requester: discord.User | discord.Member) -> discord.Embed:
    """Monta o embed de resultado da consulta."""
    if doc:
        motivo   = doc.get("motivo") or doc.get("reason") or "Não informado"
        added_at = doc.get("added_at") or doc.get("created_at")
        date_str = added_at.strftime("%d/%m/%Y") if added_at else "—"
        added_by = doc.get("added_by") or doc.get("reporter_id") or "—"

        embed = discord.Embed(
            title="🚫  Usuário na Blacklist",
            description=f"<@{target_id}> (`{target_id}`) **está na blacklist** deste servidor.",
            color=COLOR_BLACKLISTED,
            timestamp=utcnow(),
        )
        embed.add_field(name="Motivo",          value=motivo,          inline=False)
        embed.add_field(name="Adicionado em",   value=date_str,        inline=True)
        embed.add_field(name="Adicionado por",  value=f"<@{added_by}>" if added_by != "—" else "—", inline=True)
        embed.set_footer(text=f"Consulta por {requester} · X1 Frifas")
    else:
        embed = discord.Embed(
            title="✅  Usuário Limpo",
            description=f"<@{target_id}> (`{target_id}`) **não está na blacklist** deste servidor.",
            color=COLOR_CLEAN,
            timestamp=utcnow(),
        )
        embed.set_footer(text=f"Consulta por {requester} · X1 Frifas")
    return embed


# ════════════════════════════════════════════════════════
# Modal — busca por ID
# ════════════════════════════════════════════════════════

class BlacklistSearchModal(discord.ui.Modal, title="🔎 Buscar na Blacklist"):

    discord_id = discord.ui.TextInput(
        label="Discord ID do usuário",
        placeholder="Ex: 123456789012345678",
        min_length=17,
        max_length=20,
        required=True,
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        target_id = self.discord_id.value.strip()

        if not target_id.isdigit():
            await interaction.followup.send(
                "❌ ID inválido. Informe apenas números (ex: `123456789012345678`).",
                ephemeral=True,
            )
            return

        doc   = await _check_blacklist(target_id)
        embed = _build_result_embed(target_id, doc, interaction.user)
        await interaction.followup.send(embed=embed, ephemeral=True)


# ════════════════════════════════════════════════════════
# View — painel fixo no canal #blacklist
# ════════════════════════════════════════════════════════

class BlacklistCheckView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    # ── Botão 1: auto-verificação ─────────────────────────
    @discord.ui.button(
        label="🔍 Verificar Minha Situação",
        style=discord.ButtonStyle.secondary,
        custom_id="blacklist:check_self",
        row=0,
    )
    async def check_self(
        self, interaction: discord.Interaction, _: discord.ui.Button
    ):
        await interaction.response.defer(ephemeral=True)
        target_id = str(interaction.user.id)
        doc       = await _check_blacklist(target_id)
        embed     = _build_result_embed(target_id, doc, interaction.user)
        await interaction.followup.send(embed=embed, ephemeral=True)

    # ── Botão 2: busca por ID ─────────────────────────────
    @discord.ui.button(
        label="🔎 Buscar por Discord ID",
        style=discord.ButtonStyle.primary,
        custom_id="blacklist:search_by_id",
        row=0,
    )
    async def search_by_id(
        self, interaction: discord.Interaction, _: discord.ui.Button
    ):
        await interaction.response.send_modal(BlacklistSearchModal())
