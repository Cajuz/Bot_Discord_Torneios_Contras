# analyst_views.py — UI interativa para analistas.
from __future__ import annotations
import asyncio
import time
import discord

from utils.datetime_utils import utcnow
from utils.logger import logger
from services.channel_service import (
    CASOS_ANALISAR_CHANNEL,       # ← NOVO: cards vão para cá
    EXPOSED_CHANNEL_NAME,
    HISTORICO_EXPOSED_CHANNEL,    # ← NOVO: logs de blacklist
    # ANALYST_QUEUE_CHANNEL mantido só se houver outro uso externo
)

THEME  = 0xFFD54F
DANGER = 0xE74C3C

_case_locks: dict[str, asyncio.Lock] = {}


def _get_case_lock(case_id: str) -> asyncio.Lock:
    if case_id not in _case_locks:
        _case_locks[case_id] = asyncio.Lock()
    return _case_locks[case_id]


def _has_analyst_role(user: discord.Member) -> bool:
    if user.guild_permissions.administrator:
        return True
    return bool({r.name for r in user.roles} & {"Analyst", "Analista", "Admin"})


# ─────────────────────────────────────────────────────────────
# Helper — loga alteração na blacklist em #historico-exposed
# ─────────────────────────────────────────────────────────────

async def _log_blacklist_change(
    guild: discord.Guild,
    action: str,           # "adicionado" | "removido"
    player_id: str,
    reason: str,
    actor: discord.Member,
    case_id: str | None = None,
):
    """Posta log automático no canal #historico-exposed."""
    historico_ch = discord.utils.get(guild.text_channels, name=HISTORICO_EXPOSED_CHANNEL)
    if not historico_ch:
        return
    is_add  = action == "adicionado"
    color   = DANGER if is_add else 0x2ECC71
    emoji   = "✅" if is_add else "❌"
    embed   = discord.Embed(
        title=f"{emoji} Blacklist — Jogador {action.capitalize()}",
        color=color,
    )
    embed.add_field(name="ID Discord", value=f"`{player_id}`",      inline=True)
    embed.add_field(name="Por",        value=actor.mention,         inline=True)
    if case_id:
        embed.add_field(name="Caso",   value=f"`{case_id}`",        inline=True)
    embed.add_field(name="Motivo",     value=reason or "—",         inline=False)
    embed.set_footer(text=utcnow().strftime("%d/%m/%Y %H:%M UTC"))
    await historico_ch.send(embed=embed)


# ─────────────────────────────────────────────────────────────
# Embed do caso
# ─────────────────────────────────────────────────────────────

def build_case_embed(doc: dict) -> discord.Embed:
    status_colors = {
        "aguardando_analise": THEME,
        "em_analise":         0xFFA726,
        "confirmado":         DANGER,
        "inconclusivo":       0x95A5A6,
        "invalido":           0x7F8C8D,
    }
    status_labels = {
        "aguardando_analise": "Aguardando",
        "em_analise":         "Em análise",
        "confirmado":         "Confirmado — Blacklist",
        "inconclusivo":       "Inconclusivo",
        "invalido":           "Inválido",
    }
    status = doc.get("status", "aguardando_analise")
    embed  = discord.Embed(
        title=f"Caso {doc.get('case_id', '—')}",
        description=f"**Motivo:** {doc.get('motivo', '—')}",
        color=status_colors.get(status, THEME)
    )
    embed.add_field(name="Denunciante", value=f"<@{doc.get('reporter_id', '?')}>",  inline=True)
    embed.add_field(name="Acusado",
                    value=f"<@{doc['accused_id']}>" if doc.get("accused_id") else "—",
                    inline=True)
    embed.add_field(name="Partida",  value=f"`{doc.get('match_id', '—')}`",         inline=True)
    embed.add_field(name="Status",   value=status_labels.get(status, status),       inline=True)
    if doc.get("analyst_id"):
        embed.add_field(name="Analista", value=f"<@{doc['analyst_id']}>",           inline=True)
    if doc.get("evidencia_url"):
        embed.add_field(name="Evidência",
                        value=f"[Ver evidência]({doc['evidencia_url']})",            inline=False)
    if doc.get("decision_reason"):
        embed.add_field(name="Decisão", value=doc["decision_reason"],               inline=False)
    created = doc.get("created_at")
    if created:
        embed.set_footer(text=f"Aberto em {created.strftime('%d/%m/%Y %H:%M')} UTC")
    return embed


# ─────────────────────────────────────────────────────────────
# Card do caso — #casos-analisar
# ─────────────────────────────────────────────────────────────

class AnalystCaseView(discord.ui.View):

    def __init__(self, case_id: str = "__persistent__"):
        super().__init__(timeout=None)
        self.case_id = case_id

    def _get_case_id(self, interaction: discord.Interaction) -> str:
        if self.case_id != "__persistent__":
            return self.case_id
        try:
            if interaction.message and interaction.message.embeds:
                title = interaction.message.embeds[0].title or ""
                parts = title.split(" ", 1)
                if len(parts) == 2:
                    return parts[1].strip()
        except Exception:
            pass
        return self.case_id

    @discord.ui.button(label="Assumir Análise", style=discord.ButtonStyle.primary,
                       emoji="🔍", custom_id="btn_assumir_caso")
    async def assumir(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not _has_analyst_role(interaction.user):
            await interaction.response.send_message(
                "Apenas analistas podem assumir casos.", ephemeral=True)
            return

        case_id = self._get_case_id(interaction)

        async with _get_case_lock(case_id):
            from config.database import db
            doc = await db.get_collection("analysis_cases").find_one({"case_id": case_id})
            if not doc:
                await interaction.response.send_message("Caso não encontrado.", ephemeral=True)
                return
            if doc["status"] != "aguardando_analise":
                await interaction.response.send_message(
                    f"Este caso já está em `{doc['status']}`.", ephemeral=True)
                return
            await db.get_collection("analysis_cases").update_one(
                {"case_id": case_id},
                {"$set": {
                    "status":       "em_analise",
                    "analyst_id":   str(interaction.user.id),
                    "analyst_name": interaction.user.name,
                    "assumed_at":   utcnow(),
                }}
            )
            doc["status"]       = "em_analise"
            doc["analyst_id"]   = str(interaction.user.id)
            doc["analyst_name"] = interaction.user.name

        _case_locks.pop(case_id, None)

        new_embed = build_case_embed(doc)
        new_view  = AnalystDecisionView(case_id=case_id)
        await interaction.response.edit_message(embed=new_embed, view=new_view)

    @discord.ui.button(label="Ver Evidência", style=discord.ButtonStyle.secondary,
                       emoji="🔗", custom_id="btn_ver_evidencia")
    async def ver_evidencia(self, interaction: discord.Interaction, button: discord.ui.Button):
        from config.database import db
        case_id = self._get_case_id(interaction)
        doc = await db.get_collection("analysis_cases").find_one({"case_id": case_id})
        url = doc.get("evidencia_url") if doc else None
        if url:
            await interaction.response.send_message(f"Evidência: {url}", ephemeral=True)
        else:
            await interaction.response.send_message("Nenhuma evidência anexada.", ephemeral=True)


# ─────────────────────────────────────────────────────────────
# Botões de decisão — aparecem após assumir o caso
# ─────────────────────────────────────────────────────────────

class AnalystDecisionView(discord.ui.View):

    def __init__(self, case_id: str = "__persistent__"):
        super().__init__(timeout=None)
        self.case_id = case_id

    def _get_case_id(self, interaction: discord.Interaction) -> str:
        if self.case_id != "__persistent__":
            return self.case_id
        try:
            if interaction.message and interaction.message.embeds:
                title = interaction.message.embeds[0].title or ""
                parts = title.split(" ", 1)
                if len(parts) == 2:
                    return parts[1].strip()
        except Exception:
            pass
        return self.case_id

    @discord.ui.button(label="Confirmar Hack → Blacklist", style=discord.ButtonStyle.danger,
                       emoji="🚫", custom_id="btn_confirmar_hack", row=0)
    async def confirmar(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not _has_analyst_role(interaction.user):
            await interaction.response.send_message("Apenas analistas.", ephemeral=True)
            return
        case_id = self._get_case_id(interaction)
        await interaction.response.send_modal(_DecisionModal(
            case_id=case_id, decisao="confirmado",
            title="Confirmar — Motivo para Blacklist"))

    @discord.ui.button(label="Inconclusivo", style=discord.ButtonStyle.secondary,
                       emoji="❓", custom_id="btn_inconclusivo", row=0)
    async def inconclusivo(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not _has_analyst_role(interaction.user):
            await interaction.response.send_message("Apenas analistas.", ephemeral=True)
            return
        case_id = self._get_case_id(interaction)
        await interaction.response.send_modal(_DecisionModal(
            case_id=case_id, decisao="inconclusivo",
            title="Inconclusivo — Justificativa"))

    @discord.ui.button(label="Denúncia Inválida", style=discord.ButtonStyle.secondary,
                       emoji="✖", custom_id="btn_invalido", row=0)
    async def invalido(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not _has_analyst_role(interaction.user):
            await interaction.response.send_message("Apenas analistas.", ephemeral=True)
            return
        case_id = self._get_case_id(interaction)
        await interaction.response.send_modal(_DecisionModal(
            case_id=case_id, decisao="invalido",
            title="Denúncia Inválida — Justificativa"))


class _DecisionModal(discord.ui.Modal):
    motivo = discord.ui.TextInput(
        label="Motivo / Justificativa",
        style=discord.TextStyle.paragraph,
        placeholder="Descreva o motivo da decisão...",
        min_length=10, max_length=500
    )

    def __init__(self, case_id: str, decisao: str, title: str):
        super().__init__(title=title)
        self.case_id = case_id
        self.decisao = decisao

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        from config.database import db

        doc = await db.get_collection("analysis_cases").find_one({"case_id": self.case_id})
        if not doc:
            await interaction.followup.send("Caso não encontrado.", ephemeral=True)
            return

        if doc.get("analyst_id") and doc["analyst_id"] != str(interaction.user.id):
            if not interaction.user.guild_permissions.administrator:
                await interaction.followup.send(
                    "Apenas o analista responsável pode encerrar este caso.", ephemeral=True)
                return

        motivo = self.motivo.value

        await db.get_collection("analysis_cases").update_one(
            {"case_id": self.case_id},
            {"$set": {
                "status":          self.decisao,
                "decision_reason": motivo,
                "closed_at":       utcnow(),
                "closed_by":       str(interaction.user.id),
            }}
        )
        doc["status"]          = self.decisao
        doc["decision_reason"] = motivo

        if self.decisao == "confirmado":
            accused = (doc.get("accused_id") or "").strip()
            if not accused:
                accused = doc.get("reporter_id", "")
                logger.warning(
                    f"[Analyst] Caso {self.case_id} sem accused_id — usando reporter como fallback")

            await db.get_collection("blacklist").update_one(
                {"discord_id": accused},
                {"$set": {
                    "discord_id":    accused,
                    "reason":        motivo,
                    "case_id":       self.case_id,
                    "added_by":      str(interaction.user.id),
                    "added_by_name": interaction.user.name,
                    "added_at":      utcnow(),
                }},
                upsert=True
            )

            # Posta no #exposed (painel de gestão)
            exposed = discord.utils.get(
                interaction.guild.text_channels, name=EXPOSED_CHANNEL_NAME)
            if exposed:
                bl_embed = discord.Embed(
                    title="Jogador adicionado à Blacklist", color=DANGER)
                bl_embed.add_field(name="ID",       value=f"`{accused}`",           inline=True)
                bl_embed.add_field(name="Caso",     value=f"`{self.case_id}`",      inline=True)
                bl_embed.add_field(name="Motivo",   value=motivo,                   inline=False)
                bl_embed.add_field(name="Analista", value=interaction.user.mention, inline=True)
                bl_embed.set_footer(text=utcnow().strftime("%d/%m/%Y %H:%M UTC"))
                await exposed.send(embed=bl_embed)

            # ← NOVO: loga no #historico-exposed
            await _log_blacklist_change(
                guild=interaction.guild,
                action="adicionado",
                player_id=accused,
                reason=motivo,
                actor=interaction.user,
                case_id=self.case_id,
            )

        # DM para o denunciante
        try:
            reporter = await interaction.client.fetch_user(int(doc["reporter_id"]))
            dm_map = {
                "confirmado":   "Suspeito confirmado — adicionado à blacklist.",
                "inconclusivo": "Análise inconclusiva — caso arquivado.",
                "invalido":     "Denúncia considerada inválida — caso encerrado.",
            }
            dm_embed = discord.Embed(
                title=f"Resultado — {self.case_id}",
                description=dm_map.get(self.decisao, self.decisao),
                color=THEME)
            dm_embed.add_field(name="Motivo", value=motivo, inline=False)
            await reporter.send(embed=dm_embed)
        except Exception:
            pass

        await interaction.message.edit(embed=build_case_embed(doc), view=discord.ui.View())
        await interaction.followup.send(
            f"Caso `{self.case_id}` encerrado como `{self.decisao}`.", ephemeral=True)


# ─────────────────────────────────────────────────────────────
# Painel fixo no #exposed
# ─────────────────────────────────────────────────────────────

def build_exposed_embed() -> discord.Embed:
    embed = discord.Embed(
        title="Painel — Blacklist",
        description=(
            "Gerencie a lista de jogadores banidos por comportamento suspeito.\n\n"
            "**Adicionar** — abre modal para inserir ID e motivo\n"
            "**Buscar** — verifica se um jogador está na lista\n"
            "**Listar** — exibe os últimos 20 adicionados\n"
            "**Remover** — remove jogador da blacklist"
        ),
        color=DANGER
    )
    embed.set_footer(text="Acesso restrito — Analyst e Admin")
    return embed


class ExposedPanelView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Adicionar à Blacklist", style=discord.ButtonStyle.danger,
                       emoji="🚫", custom_id="exposed_add", row=0)
    async def add_blacklist(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not _has_analyst_role(interaction.user):
            await interaction.response.send_message("Apenas analistas e admins.", ephemeral=True)
            return
        await interaction.response.send_modal(_BlacklistAddModal())

    @discord.ui.button(label="Buscar Jogador", style=discord.ButtonStyle.secondary,
                       emoji="🔍", custom_id="exposed_search", row=0)
    async def search_blacklist(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not _has_analyst_role(interaction.user):
            await interaction.response.send_message("Apenas analistas e admins.", ephemeral=True)
            return
        await interaction.response.send_modal(_BlacklistSearchModal())

    @discord.ui.button(label="Listar Blacklist", style=discord.ButtonStyle.secondary,
                       emoji="📋", custom_id="exposed_list", row=0)
    async def list_blacklist(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not _has_analyst_role(interaction.user):
            await interaction.response.send_message("Apenas analistas e admins.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        from config.database import db
        docs = await db.get_collection("blacklist").find({}).sort(
            "added_at", -1).limit(20).to_list(20)
        if not docs:
            await interaction.followup.send("Blacklist vazia.", ephemeral=True)
            return
        embed = discord.Embed(title="Blacklist — Últimos 20", color=DANGER)
        for doc in docs:
            ts     = doc.get("added_at")
            ts_str = ts.strftime("%d/%m/%Y") if ts else "—"
            embed.add_field(
                name=f"`{doc['discord_id']}`",
                value=(
                    f"Motivo: {doc.get('reason','—')} | "
                    f"Por: {doc.get('added_by_name','—')} | {ts_str}"
                ),
                inline=False)
        await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.ui.button(label="Remover da Blacklist", style=discord.ButtonStyle.secondary,
                       emoji="✅", custom_id="exposed_remove", row=1)
    async def remove_blacklist(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not _has_analyst_role(interaction.user):
            await interaction.response.send_message("Apenas analistas e admins.", ephemeral=True)
            return
        await interaction.response.send_modal(_BlacklistRemoveModal())


class _BlacklistAddModal(discord.ui.Modal, title="Adicionar à Blacklist"):
    player_id = discord.ui.TextInput(
        label="ID Discord do jogador",
        placeholder="Ex: 123456789012345678",
        min_length=10, max_length=20)
    motivo = discord.ui.TextInput(
        label="Motivo",
        style=discord.TextStyle.paragraph,
        placeholder="Descreva o motivo...",
        min_length=5, max_length=300)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        from config.database import db

        pid = self.player_id.value.strip()
        if not pid.isdigit():
            await interaction.followup.send(
                "ID inválido. O ID Discord deve conter apenas números.", ephemeral=True)
            return

        await db.get_collection("blacklist").update_one(
            {"discord_id": pid},
            {"$set": {
                "discord_id":    pid,
                "reason":        self.motivo.value,
                "added_by":      str(interaction.user.id),
                "added_by_name": interaction.user.name,
                "added_at":      utcnow(),
            }},
            upsert=True
        )

        # Confirmação no canal #exposed
        embed = discord.Embed(
            title="Blacklist — Jogador Adicionado",
            description=f"ID: `{pid}`\nMotivo: {self.motivo.value}",
            color=DANGER)
        embed.add_field(name="Analista", value=interaction.user.mention, inline=True)
        embed.set_footer(text=utcnow().strftime("%d/%m/%Y %H:%M UTC"))
        await interaction.channel.send(embed=embed)

        # ← NOVO: loga no #historico-exposed
        await _log_blacklist_change(
            guild=interaction.guild,
            action="adicionado",
            player_id=pid,
            reason=self.motivo.value,
            actor=interaction.user,
        )

        await interaction.followup.send("Adicionado com sucesso.", ephemeral=True)


class _BlacklistSearchModal(discord.ui.Modal, title="Buscar na Blacklist"):
    player_id = discord.ui.TextInput(
        label="ID Discord do jogador",
        placeholder="Ex: 123456789012345678",
        min_length=10, max_length=20)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        from config.database import db

        pid = self.player_id.value.strip()
        if not pid.isdigit():
            await interaction.followup.send(
                "ID inválido. O ID Discord deve conter apenas números.", ephemeral=True)
            return

        doc = await db.get_collection("blacklist").find_one({"discord_id": pid})
        if not doc:
            await interaction.followup.send(
                f"Jogador `{pid}` não está na blacklist.", ephemeral=True)
            return
        embed = discord.Embed(title="Blacklist — Encontrado", color=DANGER)
        embed.add_field(name="ID",       value=f"`{pid}`",                      inline=True)
        embed.add_field(name="Motivo",   value=doc.get("reason", "—"),          inline=False)
        embed.add_field(name="Analista", value=doc.get("added_by_name", "—"),   inline=True)
        ts = doc.get("added_at")
        if ts:
            embed.add_field(name="Adicionado", value=ts.strftime("%d/%m/%Y"),   inline=True)
        await interaction.followup.send(embed=embed, ephemeral=True)


class _BlacklistRemoveModal(discord.ui.Modal, title="Remover da Blacklist"):
    player_id = discord.ui.TextInput(
        label="ID Discord do jogador",
        placeholder="Ex: 123456789012345678",
        min_length=10, max_length=20)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        from config.database import db

        pid = self.player_id.value.strip()
        if not pid.isdigit():
            await interaction.followup.send(
                "ID inválido. O ID Discord deve conter apenas números.", ephemeral=True)
            return

        # Busca antes de deletar para guardar o motivo no log
        doc = await db.get_collection("blacklist").find_one({"discord_id": pid})

        result = await db.get_collection("blacklist").delete_one({"discord_id": pid})
        if result.deleted_count:
            await interaction.channel.send(
                f"Jogador `{pid}` removido da blacklist por {interaction.user.mention}.")

            # ← NOVO: loga no #historico-exposed
            await _log_blacklist_change(
                guild=interaction.guild,
                action="removido",
                player_id=pid,
                reason=doc.get("reason", "—") if doc else "—",
                actor=interaction.user,
            )

            await interaction.followup.send("Removido com sucesso.", ephemeral=True)
        else:
            await interaction.followup.send(
                f"Jogador `{pid}` não encontrado na blacklist.", ephemeral=True)


# ─────────────────────────────────────────────────────────────
# Painel fixo no #solicitar-analise
# ─────────────────────────────────────────────────────────────

def build_analise_panel_embed() -> discord.Embed:
    embed = discord.Embed(
        title="Solicitação de Análise de Partida",
        description=(
            "Suspeita que um jogador usou hacks na sua partida?\n\n"
            "Clique em **Solicitar Análise** e preencha as informações. "
            "Nossa equipe irá investigar e você receberá o resultado por DM.\n\n"
            "**O que você vai precisar informar:**\n"
            "• ID da partida suspeita\n"
            "• ID Discord do jogador acusado\n"
            "• Descrição do comportamento suspeito\n"
            "• Link de evidência (opcional mas recomendado)"
        ),
        color=THEME
    )
    embed.add_field(name="Tempo de resposta",
                    value="Nossa equipe analisa em até 48h.", inline=False)
    embed.set_footer(text="Denúncias falsas podem resultar em punição.")
    return embed


class AnalisePanelView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Solicitar Análise", style=discord.ButtonStyle.primary,
                       emoji="🔎", custom_id="btn_solicitar_analise")
    async def solicitar(self, interaction: discord.Interaction, _: discord.ui.Button):
        await interaction.response.send_modal(_SolicitarAnaliseModal())

    @discord.ui.button(label="Ver meus casos", style=discord.ButtonStyle.secondary,
                       emoji="📋", custom_id="btn_meus_casos")
    async def meus_casos(self, interaction: discord.Interaction, _: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        from config.database import db
        docs = await db.get_collection("analysis_cases").find(
            {"reporter_id": str(interaction.user.id)}
        ).sort("created_at", -1).limit(5).to_list(5)
        if not docs:
            await interaction.followup.send("Você não tem nenhum caso aberto.", ephemeral=True)
            return
        status_labels = {
            "aguardando_analise": "⏳ Aguardando",
            "em_analise":         "🔍 Em análise",
            "confirmado":         "🚫 Confirmado",
            "inconclusivo":       "❓ Inconclusivo",
            "invalido":           "✖ Inválido",
        }
        embed = discord.Embed(title="Seus casos", color=THEME)
        for doc in docs:
            status = status_labels.get(doc.get("status", ""), doc.get("status", "—"))
            embed.add_field(
                name=f"`{doc['case_id']}`",
                value=(
                    f"**Partida:** `{doc.get('match_id','—')}`\n"
                    f"**Status:** {status}\n"
                    f"**Motivo:** {doc.get('motivo','—')[:60]}"
                ),
                inline=False)
        await interaction.followup.send(embed=embed, ephemeral=True)


class _SolicitarAnaliseModal(discord.ui.Modal, title="Solicitar Análise de Partida"):
    match_id   = discord.ui.TextInput(
        label="ID da partida",
        placeholder="Ex: 1234567890",
        min_length=1, max_length=100)
    accused_id = discord.ui.TextInput(
        label="ID Discord do jogador acusado",
        placeholder="Ex: 123456789012345678",
        min_length=10, max_length=20)
    motivo     = discord.ui.TextInput(
        label="Descrição do comportamento suspeito",
        style=discord.TextStyle.paragraph,
        placeholder="Descreva o que aconteceu...",
        min_length=20, max_length=500)
    evidencia  = discord.ui.TextInput(
        label="Link de evidência (opcional)",
        placeholder="https://...",
        required=False, max_length=300)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        from config.database import db

        accused = self.accused_id.value.strip()
        if not accused.isdigit():
            await interaction.followup.send(
                "ID do acusado inválido. Deve conter apenas números.", ephemeral=True)
            return

        caso_ativo = await db.get_collection("analysis_cases").find_one({
            "reporter_id": str(interaction.user.id),
            "status": {"$in": ["aguardando_analise", "em_analise"]}
        })
        if caso_ativo:
            await interaction.followup.send(
                f"Você já tem um caso aberto (`{caso_ativo['case_id']}`). "
                "Aguarde a análise antes de abrir outro.",
                ephemeral=True)
            return

        case_id = (
            f"CASE-{self.match_id.value[:8].upper()}"
            f"-{str(interaction.user.id)[-4:]}"
            f"-{int(time.time())}"
        )

        doc = {
            "case_id":         case_id,
            "reporter_id":     str(interaction.user.id),
            "reporter_name":   interaction.user.name,
            "accused_id":      accused,
            "match_id":        self.match_id.value.strip(),
            "motivo":          self.motivo.value,
            "evidencia_url":   self.evidencia.value.strip() if self.evidencia.value else "",
            "analyst_id":      None,
            "status":          "aguardando_analise",
            "decision_reason": None,
            "created_at":      utcnow(),
            "closed_at":       None,
        }
        await db.get_collection("analysis_cases").insert_one(doc)

        # ← ATUALIZADO: card vai para #casos-analisar (era #fila-analistas)
        casos_ch = discord.utils.get(
            interaction.guild.text_channels, name=CASOS_ANALISAR_CHANNEL)
        if casos_ch:
            await casos_ch.send(
                embed=build_case_embed(doc),
                view=AnalystCaseView(case_id=case_id))

        await interaction.followup.send(
            embed=discord.Embed(
                title="Solicitação enviada",
                description=(
                    f"Caso `{case_id}` criado com sucesso.\n"
                    "Nossa equipe irá analisar e você receberá o resultado por DM."
                ),
                color=THEME),
            ephemeral=True)
