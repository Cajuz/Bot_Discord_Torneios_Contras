"""
blacklist_view.py

Painel fixo postado em #blacklist.
Dois botões:
  1. 🔍 Verificar Minha Situação  — ephemeral, mostra status do próprio usuário
  2. 🔎 Buscar por Discord ID     — abre modal, qualquer membro pode checar outro

O bot consulta as coleções:
  - "blacklist"  (campo discord_id, motivo, added_at, added_by)
  - "exposed"    (campo discord_id, motivo, created_at)
Se encontrar em qualquer uma delas, retorna ❌ BLOQUEADO; caso contrário ✅ LIMPO.
"""
from __future__ import annotations

import discord
from utils.logger import logger
from utils.datetime_utils import utcnow

THEME_COLOR   = 0xFFD54F
DANGER_COLOR  = 0xE74C3C
SUCCESS_COLOR = 0x27AE60


# ═══════════════════════════════════════════════════════════════
# Helper — consulta unificada nas coleções blacklist + exposed
# ═══════════════════════════════════════════════════════════════

async def _check_blacklist(discord_id: str) -> dict | None:
    """
    Retorna o documento de blacklist/exposed ou None se o usuário estiver limpo.
    Prioridade: blacklist primeiro, depois exposed.
    """
    try:
        from config.database import db

        # 1. Verifica coleção blacklist
        doc = await db.get_collection("blacklist").find_one(
            {"discord_id": str(discord_id)}
        )
        if doc:
            doc["_source"] = "blacklist"
            return doc

        # 2. Verifica coleção exposed
        doc = await db.get_collection("exposed").find_one(
            {"discord_id": str(discord_id)}
        )
        if doc:
            doc["_source"] = "exposed"
            return doc

        return None
    except Exception as e:
        logger.error(f"[blacklist_view] _check_blacklist error: {e}")
        return None


def _build_result_embed(target_id: str, doc: dict | None, display_name: str | None = None) -> discord.Embed:
    """Monta o embed de resultado da verificação."""
    mention = f"<@{target_id}>"
    name_str = f" ({display_name})" if display_name else ""

    if doc is None:
        embed = discord.Embed(
            title="✅  Usuário Limpo",
            description=f"{mention}{name_str} **não consta** na blacklist do servidor.",
            color=SUCCESS_COLOR,
            timestamp=utcnow(),
        )
        embed.set_footer(text="X1 Frifas · Verificação de Blacklist")
        return embed

    source  = doc.get("_source", "blacklist")
    motivo  = doc.get("motivo") or doc.get("reason") or "Não informado"
    added_at = doc.get("added_at") or doc.get("created_at")
    date_str = added_at.strftime("%d/%m/%Y") if added_at else "—"
    added_by = doc.get("added_by") or doc.get("reported_by") or "—"

    source_label = "🚫 Blacklist" if source == "blacklist" else "⚠️ Exposed"

    embed = discord.Embed(
        title="❌  Usuário Bloqueado",
        description=f"{mention}{name_str} **consta** na lista de restrições.",
        color=DANGER_COLOR,
        timestamp=utcnow(),
    )
    embed.add_field(name="Origem",      value=source_label, inline=True)
    embed.add_field(name="Registrado",  value=date_str,     inline=True)
    embed.add_field(name="Por",         value=f"<@{added_by}>" if str(added_by).isdigit() else str(added_by), inline=True)
    embed.add_field(name="Motivo",      value=motivo,        inline=False)
    embed.set_footer(text="X1 Frifas · Verificação de Blacklist")
    return embed


# ═══════════════════════════════════════════════════════════════
# Modal — busca por Discord ID
# ═══════════════════════════════════════════════════════════════

class BlacklistIdModal(discord.ui.Modal, title="🔎 Buscar na Blacklist"):

    discord_id = discord.ui.TextInput(
        label="Discord ID do usuário",
        placeholder="Ex: 123456789012345678",
        min_length=17,
        max_length=20,
        required=True,
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        raw_id = self.discord_id.value.strip()

        if not raw_id.isdigit():
            await interaction.followup.send(
                "❌ ID inválido. Informe apenas números (ex: `123456789012345678`).",
                ephemeral=True,
            )
            return

        doc = await _check_blacklist(raw_id)

        # Tenta resolver o nome do usuário via guild
        display_name = None
        try:
            member = interaction.guild.get_member(int(raw_id))
            if member:
                display_name = member.display_name
        except Exception:
            pass

        embed = _build_result_embed(raw_id, doc, display_name)
        await interaction.followup.send(embed=embed, ephemeral=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        logger.error(f"[BlacklistIdModal] {error}")
        await interaction.response.send_message(
            "❌ Erro ao processar. Tente novamente.", ephemeral=True
        )


# ═══════════════════════════════════════════════════════════════
# View principal — postada no canal #blacklist
# ═══════════════════════════════════════════════════════════════

class BlacklistCheckView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="🔍 Verificar Minha Situação",
        style=discord.ButtonStyle.success,
        custom_id="blacklist:self_check",
    )
    async def self_check(self, interaction: discord.Interaction, _: discord.ui.Button):
        """Verifica o status do próprio usuário que clicou."""
        await interaction.response.defer(ephemeral=True, thinking=True)
        doc   = await _check_blacklist(str(interaction.user.id))
        embed = _build_result_embed(
            str(interaction.user.id),
            doc,
            interaction.user.display_name,
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.ui.button(
        label="🔎 Buscar por Discord ID",
        style=discord.ButtonStyle.primary,
        custom_id="blacklist:search_by_id",
    )
    async def search_by_id(self, interaction: discord.Interaction, _: discord.ui.Button):
        """Abre modal para informar um Discord ID e verificar qualquer usuário."""
        await interaction.response.send_modal(BlacklistIdModal())


# ═══════════════════════════════════════════════════════════════
# Embed fixo do painel
# ═══════════════════════════════════════════════════════════════

def build_blacklist_panel_embed() -> discord.Embed:
    embed = discord.Embed(
        title="🚫  Verificação de Blacklist — X1 Frifas",
        description=(
            "Use os botões abaixo para verificar se um usuário está na lista de restrições do servidor.\n\n"
            "**🔍 Verificar Minha Situação** — Checa automaticamente o seu próprio perfil.\n"
            "**🔎 Buscar por Discord ID** — Informe o ID de qualquer membro para consultar."
        ),
        color=THEME_COLOR,
    )
    embed.add_field(
        name="📌 Como encontrar o Discord ID?",
        value=(
            "Ative o Modo Desenvolvedor em `Configurações → Avançado → Modo Desenvolvedor`.\n"
            "Depois clique com o botão direito no perfil do usuário e selecione **Copiar ID**."
        ),
        inline=False,
    )
    embed.set_footer(text="X1 Frifas · As respostas são privadas e visíveis apenas para você.")
    return embed
