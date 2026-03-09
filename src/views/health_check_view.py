# src/views/health_check_view.py

from __future__ import annotations
from typing import TYPE_CHECKING

import discord

from utils.logger import logger

if TYPE_CHECKING:
    from services.health_check_service import HealthCheckService, HealthReport, CategoryHealth


# ─── Constantes visuais ─────────────────────────────────────────────────────

CATEGORY_LABELS = {
    "infra":      "🔌 Infraestrutura",
    "threads":    "🧵 Threads",
    "partidas":   "⚔️ Partidas",
    "mediadores": "🧑‍⚖️ Mediadores",
    "spam":       "🛡️ Spam & Onboard",
    "suporte":    "🎫 Suporte",
}

CATEGORY_BUTTONS_ROW0 = [
    ("infra",      "🔌 Infra"),
    ("threads",    "🧵 Threads"),
    ("partidas",   "⚔️ Partidas"),
]

CATEGORY_BUTTONS_ROW1 = [
    ("mediadores", "🧑‍⚖️ Mediadores"),
    ("spam",       "🛡️ Spam"),
    ("suporte",    "🎫 Suporte"),
]


# ─── Helpers visuais ────────────────────────────────────────────────────────

def _bar(score: float, length: int = 12) -> str:
    filled = round(score / 100 * length)
    return "🟩" * filled + "⬜" * (length - filled)


def _status_emoji(status: str) -> str:
    return {"ok": "🟢", "warning": "🟡", "critical": "🔴"}.get(status, "⚪")


def _embed_color(status: str) -> discord.Color:
    return {
        "ok":       discord.Color.green(),
        "warning":  discord.Color.yellow(),
        "critical": discord.Color.red(),
    }.get(status, discord.Color.default())


def _fmt_uptime(seconds: float) -> str:
    d = int(seconds // 86400)
    h = int((seconds % 86400) // 3600)
    m = int((seconds % 3600) // 60)
    parts = []
    if d:
        parts.append(f"{d}d")
    if h:
        parts.append(f"{h}h")
    parts.append(f"{m}min")
    return " ".join(parts) or "< 1min"


# ─── Embed: Visão Geral ──────────────────────────────────────────────────────

def build_overview_embed(report: "HealthReport") -> discord.Embed:
    color = _embed_color(report.overall_status)
    embed = discord.Embed(
        title="🏥 Health Check — X1 Frifas Bot",
        color=color,
        timestamp=report.timestamp,
    )

    embed.description = (
        f"## {_status_emoji(report.overall_status)}  Estabilidade Geral: **{report.overall_score:.1f}%**\n"
        f"`{_bar(report.overall_score)}`\n\n"
        f"⏱️ Uptime: **{_fmt_uptime(report.uptime_seconds)}**  │  "
        f"🕐 Atualizado: <t:{int(report.timestamp.timestamp())}:R>"
    )

    # Linha resumida por categoria
    cat_lines = []
    for key, cat in report.categories.items():
        label = CATEGORY_LABELS.get(key, key)
        emoji = _status_emoji(cat.status)
        cat_lines.append(
            f"{emoji} **{label}** — {cat.score:.0f}%  `{_bar(cat.score, 8)}`"
        )
    embed.add_field(name="📊 Estabilidade por Categoria", value="\n".join(cat_lines), inline=False)

    # KPIs rápidos
    kpi_lines = []
    cats = report.categories

    if "infra" in cats:
        inf = cats["infra"].kpis
        kpi_lines.append(
            f"🔌 MongoDB: `{inf.get('mongo_latency_ms', '?')}ms`  │  Gateway: `{inf.get('gateway_ms', '?')}ms`"
        )
    if "threads" in cats:
        th = cats["threads"].kpis
        kpi_lines.append(
            f"🧵 Pool: `{th.get('pool_total', '?')}`  │  Margem Discord: `{th.get('margem', '?')}/1000`"
        )
    if "partidas" in cats:
        pt = cats["partidas"].kpis
        kpi_lines.append(
            f"⚔️ Ativas: `{pt.get('ativas', '?')}`  │  Presas: `{pt.get('presas', '?')}`  │  Taxa 7d: `{pt.get('taxa_conclusao_7d', '?')}%`"
        )
    if "mediadores" in cats:
        med = cats["mediadores"].kpis
        kpi_lines.append(
            f"🧑‍⚖️ Na fila: `{med.get('total_ativos', '?')}`  │  Disponíveis: `{med.get('disponiveis', '?')}`"
        )
    if "spam" in cats:
        sp = cats["spam"].kpis
        kpi_lines.append(
            f"🛡️ Bloqueados: `{sp.get('bloqueados_ativos', 0)}`  │  Aceitação: `{sp.get('taxa_aceitacao', '?')}%`"
        )
    if "suporte" in cats:
        sup = cats["suporte"].kpis
        kpi_lines.append(
            f"🎫 Abertos: `{sup.get('abertos', '?')}`  │  Sem atendente: `{sup.get('sem_atendente', '?')}`"
        )

    embed.add_field(name="📌 KPIs Rápidos", value="\n".join(kpi_lines), inline=False)

    # Alertas ativos
    all_alerts = [
        alert
        for cat in report.categories.values()
        for alert in cat.alerts
    ]
    if all_alerts:
        embed.add_field(
            name=f"🚨 Alertas Ativos ({len(all_alerts)})",
            value="\n".join(f"⚠️ {a}" for a in all_alerts[:8]),
            inline=False,
        )
    else:
        embed.add_field(name="✅ Alertas", value="Nenhum alerta ativo.", inline=False)

    embed.set_footer(text="Clique nos botões para ver detalhes de cada categoria")
    return embed


# ─── Embed: Detalhe por categoria ───────────────────────────────────────────

def build_detail_embed(cat: "CategoryHealth", report: "HealthReport") -> discord.Embed:
    label = CATEGORY_LABELS.get(cat.name, cat.name)
    embed = discord.Embed(
        title=f"{label} — Detalhe",
        color=_embed_color(cat.status),
        timestamp=report.timestamp,
    )
    embed.description = (
        f"{_status_emoji(cat.status)}  **Estabilidade: {cat.score:.1f}%**\n"
        f"`{_bar(cat.score)}`"
    )

    kpis = cat.kpis

    # ── Infraestrutura ───────────────────────────────────────────────────────
    if cat.name == "infra":
        embed.add_field(
            name="🗄️ MongoDB",
            value=(
                f"**Status:** {'🟢 Conectado' if kpis.get('mongo_connected') else '🔴 Desconectado'}\n"
                f"**Latência:** `{kpis.get('mongo_latency_ms', '?')} ms`"
            ),
            inline=True,
        )
        embed.add_field(
            name="🌐 Discord Gateway",
            value=f"**Latência:** `{kpis.get('gateway_ms', '?')} ms`",
            inline=True,
        )
        embed.add_field(
            name="⏱️ Uptime",
            value=f"`{_fmt_uptime(kpis.get('uptime_seconds', 0))}`",
            inline=True,
        )

    # ── Threads ──────────────────────────────────────────────────────────────
    elif cat.name == "threads":
        pool_total     = kpis.get("pool_total", 0)
        active_matches = kpis.get("active_matches", 0)
        live_discord   = kpis.get("live_discord", 0)
        margem         = kpis.get("margem", 0)
        reuse_ok       = kpis.get("reuse_service_ok", False)

        embed.add_field(
            name="📦 Pool",
            value=(
                f"**Total disponível:** `{pool_total}`\n"
                f"**Em partida agora:** `{active_matches}`"
            ),
            inline=True,
        )
        embed.add_field(
            name="📊 Limite Discord",
            value=(
                f"**Ativas:** `{live_discord}/1.000`\n"
                f"**Margem livre:** `{margem}`"
            ),
            inline=True,
        )
        embed.add_field(
            name="🔧 Serviços",
            value=f"**ThreadReuseService:** {'🟢 OK' if reuse_ok else '🔴 Falhou'}",
            inline=True,
        )

        pool_by_ch = kpis.get("pool_by_channel") or {}
        if pool_by_ch:
            lines = [f"• `{ch}`: {n}" for ch, n in pool_by_ch.items()]
            embed.add_field(
                name="📋 Pool por Canal",
                value="\n".join(lines) or "—",
                inline=False,
            )

    # ── Partidas ─────────────────────────────────────────────────────────────
    elif cat.name == "partidas":
        ativas         = kpis.get("ativas", 0)
        presas         = kpis.get("presas", 0)
        sem_mediador   = kpis.get("sem_mediador", 0)
        filas_ativas   = kpis.get("filas_ativas", 0)
        fin_hoje       = kpis.get("finalizadas_hoje", 0)
        can_hoje       = kpis.get("canceladas_hoje", 0)
        taxa           = kpis.get("taxa_conclusao_7d", 0)

        embed.add_field(
            name="⚔️ Situação Atual",
            value=(
                f"**Ativas:** `{ativas}`\n"
                f"**Presas (>30 min):** `{presas}`\n"
                f"**Sem mediador:** `{sem_mediador}`\n"
                f"**Filas abertas:** `{filas_ativas}`"
            ),
            inline=True,
        )
        embed.add_field(
            name="📅 Hoje",
            value=(
                f"**Finalizadas:** `{fin_hoje}`\n"
                f"**Canceladas:** `{can_hoje}`"
            ),
            inline=True,
        )
        embed.add_field(
            name="📈 Taxa Conclusão (7d)",
            value=f"**{float(taxa):.1f}%**",
            inline=True,
        )

    # ── Mediadores ───────────────────────────────────────────────────────────
    elif cat.name == "mediadores":
        total_ativos  = kpis.get("total_ativos", 0)
        disponiveis   = kpis.get("disponiveis", 0)
        em_rate_limit = kpis.get("em_rate_limit", 0)
        daily_ok      = kpis.get("daily_task_ok", False)

        embed.add_field(
            name="👥 Fila",
            value=(
                f"**Na fila:** `{total_ativos}`\n"
                f"**Disponíveis:** `{disponiveis}`\n"
                f"**Em rate-limit:** `{em_rate_limit}`"
            ),
            inline=True,
        )
        embed.add_field(
            name="⚙️ Serviços",
            value=f"**Daily task:** {'🟢 Rodando' if daily_ok else '🔴 Parada'}",
            inline=True,
        )
        ml = kpis.get("mais_sobrecarregado")
        if ml and isinstance(ml, dict):
            embed.add_field(
                name="🔥 Mais Sobrecarregado",
                value=f"**{ml.get('username', '?')}** — {ml.get('matches_8min', 0)}/5 nos últimos 8 min",
                inline=False,
            )

    # ── Spam & Onboard ───────────────────────────────────────────────────────
    elif cat.name == "spam":
        anti_ok     = kpis.get("anti_spam_ok", False)
        onboard_ok  = kpis.get("onboarding_ok", False)
        cargo_ok    = kpis.get("cargo_bloqueio_existe", False)
        bloqueados  = kpis.get("bloqueados_ativos", 0)
        total_users = kpis.get("total_users", 0)
        taxa_ac     = kpis.get("taxa_aceitacao", 0)
        views_reg   = kpis.get("persistent_views", 0)

        embed.add_field(
            name="🛡️ Serviços",
            value=(
                f"**AntiSpam:** {'🟢 OK' if anti_ok else '🔴 Falhou'}\n"
                f"**Onboarding:** {'🟢 OK' if onboard_ok else '🔴 Falhou'}\n"
                f"**Cargo bloqueio:** {'🟢 Existe' if cargo_ok else '🔴 Ausente'}"
            ),
            inline=True,
        )
        embed.add_field(
            name="👥 Membros",
            value=(
                f"**Bloqueados ativos:** `{bloqueados}`\n"
                f"**Total no sistema:** `{total_users}`\n"
                f"**Taxa aceitação:** `{taxa_ac}%`"
            ),
            inline=True,
        )
        embed.add_field(
            name="🔧 Views Persistentes",
            value=f"**Registradas:** `{views_reg}/4`",
            inline=True,
        )

    # ── Suporte ──────────────────────────────────────────────────────────────
    elif cat.name == "suporte":
        abertos      = kpis.get("abertos", 0)
        sem_atend    = kpis.get("sem_atendente", 0)
        concl_hoje   = kpis.get("concluidos_hoje", 0)
        canais_ok    = kpis.get("canais_ok", False)

        embed.add_field(
            name="🎫 Chamados",
            value=(
                f"**Abertos:** `{abertos}`\n"
                f"**Sem atendente:** `{sem_atend}`\n"
                f"**Concluídos hoje:** `{concl_hoje}`"
            ),
            inline=True,
        )
        embed.add_field(
            name="🏗️ Infraestrutura",
            value=f"**Canais:** {'🟢 OK' if canais_ok else '🔴 Ausentes — use !setupcanais'}",
            inline=True,
        )

    # Alertas desta categoria
    if cat.alerts:
        embed.add_field(
            name="⚠️ Alertas",
            value="\n".join(f"• {a}" for a in cat.alerts),
            inline=False,
        )
    else:
        embed.add_field(name="✅ Status", value="Tudo funcionando normalmente.", inline=False)

    embed.set_footer(text="← Visão Geral  •  Dados coletados em tempo real")
    return embed


# ─── View com botões ─────────────────────────────────────────────────────────

class HealthCheckView(discord.ui.View):

    def __init__(
        self,
        report:          "HealthReport",
        service:         "HealthCheckService",
        guild:           discord.Guild,
        anti_spam_svc  = None,
        onboarding_svc = None,
    ):
        super().__init__(timeout=300)
        self.report         = report
        self.service        = service
        self.guild          = guild
        self.anti_spam_svc  = anti_spam_svc
        self.onboarding_svc = onboarding_svc
        self._build_buttons()

    # ── Construção dinâmica dos botões ───────────────────────────────────────

    def _build_buttons(self) -> None:
        # Linha 0 — primeiras 3 categorias
        for cat_key, label in CATEGORY_BUTTONS_ROW0:
            btn = discord.ui.Button(
                label     = label,
                style     = discord.ButtonStyle.secondary,
                custom_id = f"hc_cat_{cat_key}",
                row       = 0,
            )
            btn.callback = self._make_detail_callback(cat_key)
            self.add_item(btn)

        # Linha 1 — últimas 3 categorias
        for cat_key, label in CATEGORY_BUTTONS_ROW1:
            btn = discord.ui.Button(
                label     = label,
                style     = discord.ButtonStyle.secondary,
                custom_id = f"hc_cat_{cat_key}",
                row       = 1,
            )
            btn.callback = self._make_detail_callback(cat_key)
            self.add_item(btn)

        # Linha 2 — controles
        overview_btn = discord.ui.Button(
            label     = "📋 Visão Geral",
            style     = discord.ButtonStyle.primary,
            custom_id = "hc_overview",
            row       = 2,
        )
        overview_btn.callback = self._overview_callback
        self.add_item(overview_btn)

        refresh_btn = discord.ui.Button(
            label     = "🔄 Atualizar",
            style     = discord.ButtonStyle.success,
            custom_id = "hc_refresh",
            row       = 2,
        )
        refresh_btn.callback = self._refresh_callback
        self.add_item(refresh_btn)

    # ── Callbacks ────────────────────────────────────────────────────────────

    def _make_detail_callback(self, cat_key: str):
        async def _callback(interaction: discord.Interaction) -> None:
            # Responde imediatamente para evitar timeout do Discord
            await interaction.response.defer()
            try:
                if not interaction.user.guild_permissions.administrator:
                    await interaction.followup.send("❌ Apenas administradores.", ephemeral=True)
                    return

                cat = self.report.categories.get(cat_key)
                if not cat:
                    await interaction.followup.send(
                        f"❌ Categoria `{cat_key}` não encontrada no relatório.",
                        ephemeral=True
                    )
                    return

                embed = build_detail_embed(cat, self.report)
                await interaction.edit_original_response(embed=embed, view=self)

            except Exception as exc:
                logger.error(f"Erro no detail callback ({cat_key}): {exc}", exc_info=True)
                try:
                    await interaction.followup.send(
                        f"❌ Erro ao exibir detalhe de `{cat_key}`: {exc}",
                        ephemeral=True
                    )
                except Exception:
                    pass

        return _callback

    async def _overview_callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        try:
            if not interaction.user.guild_permissions.administrator:
                await interaction.followup.send("❌ Apenas administradores.", ephemeral=True)
                return
            embed = build_overview_embed(self.report)
            await interaction.edit_original_response(embed=embed, view=self)
        except Exception as exc:
            logger.error(f"Erro no overview callback: {exc}", exc_info=True)
            try:
                await interaction.followup.send(f"❌ Erro: {exc}", ephemeral=True)
            except Exception:
                pass

    async def _refresh_callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        try:
            if not interaction.user.guild_permissions.administrator:
                await interaction.followup.send("❌ Apenas administradores.", ephemeral=True)
                return

            new_report  = await self.service.run(
                self.guild,
                self.anti_spam_svc,
                self.onboarding_svc,
            )
            self.report = new_report
            embed       = build_overview_embed(new_report)
            await interaction.edit_original_response(embed=embed, view=self)

        except Exception as exc:
            logger.error(f"Erro no refresh callback: {exc}", exc_info=True)
            try:
                await interaction.followup.send(f"❌ Erro ao atualizar: {exc}", ephemeral=True)
            except Exception:
                pass

    # ── Timeout ──────────────────────────────────────────────────────────────

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True
