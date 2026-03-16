"""
health_check_view.py — Painel de saúde do bot + pool de threads.

Botões persistentes (custom_id fixo):
  Row 0: Infra | Threads | Partidas
  Row 1: Mediadores | Spam | Suporte
  Row 2: 🔄 Atualizar | 👁️ Ver Tópicos
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

import discord

from utils.logger import logger

if TYPE_CHECKING:
    from services.health_check_service import HealthCheckService, HealthReport, CategoryHealth

CATEGORY_LABELS = {
    "infra":      "Infraestrutura",
    "threads":    "Threads",
    "partidas":   "Partidas",
    "mediadores": "Mediadores",
    "spam":       "Spam & Onboard",
    "suporte":    "Suporte",
}

THEME_COLOR    = 0xFFD54F
VIEW_ROLE_NAME = "Ver Tópicos"


# ─────────────────────────────────────────────────────────────
# Helpers visuais
# ─────────────────────────────────────────────────────────────

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
    if d: parts.append(f"{d}d")
    if h: parts.append(f"{h}h")
    parts.append(f"{m}min")
    return " ".join(parts) or "< 1min"


# ─────────────────────────────────────────────────────────────
# Builders de embed
# ─────────────────────────────────────────────────────────────

async def build_overview_embed(bot_or_report, start_time=None) -> discord.Embed:
    """
    Dois modos:
    - build_overview_embed(report)               — novo (service completo)
    - build_overview_embed(bot, BOT_START_TIME)  — legado (admin_cog)
    """
    if isinstance(bot_or_report, discord.Client):
        bot    = bot_or_report
        gw_ms  = round(bot.latency * 1000, 1)
        uptime = (datetime.now(timezone.utc) - start_time).total_seconds() if start_time else 0
        embed  = discord.Embed(
            title="Health Check — X1 Frifas Bot",
            color=discord.Color.from_rgb(255, 213, 79),
            timestamp=datetime.now(timezone.utc),
        )
        embed.add_field(name="Gateway",    value=f"`{gw_ms}ms`",              inline=True)
        embed.add_field(name="Uptime",     value=f"`{_fmt_uptime(uptime)}`",  inline=True)
        embed.add_field(name="Servidores", value=f"`{len(bot.guilds)}`",      inline=True)
        embed.set_footer(text="Use /healthcheck para relatório completo")
        return embed

    report = bot_or_report
    color  = _embed_color(report.overall_status)
    embed  = discord.Embed(
        title="Health Check — X1 Frifas Bot",
        color=color,
        timestamp=report.timestamp,
    )
    embed.description = (
        f"{_status_emoji(report.overall_status)} Estabilidade: "
        f"**{report.overall_score:.1f}%**\n"
        f"`{_bar(report.overall_score)}`\n\n"
        f"Uptime: **{_fmt_uptime(report.uptime_seconds)}**"
    )

    cat_lines = [
        f"{_status_emoji(cat.status)} **{CATEGORY_LABELS.get(k, k)}** "
        f"— {cat.score:.0f}% `{_bar(cat.score, 8)}`"
        for k, cat in report.categories.items()
    ]
    embed.add_field(name="Categorias", value="\n".join(cat_lines), inline=False)

    all_alerts = [a for cat in report.categories.values() for a in cat.alerts]
    if all_alerts:
        embed.add_field(
            name=f"Alertas ({len(all_alerts)})",
            value="\n".join(f"• {a}" for a in all_alerts[:8]),
            inline=False,
        )
    else:
        embed.add_field(name="Status", value="Nenhum alerta ativo.", inline=False)

    embed.set_footer(text="Clique nos botões para detalhes | 👁️ Ver Tópicos para acesso às threads")
    return embed


def build_detail_embed(cat: "CategoryHealth", report: "HealthReport") -> discord.Embed:
    label = CATEGORY_LABELS.get(cat.name, cat.name)
    embed = discord.Embed(
        title=f"{label} — Detalhe",
        color=_embed_color(cat.status),
        timestamp=report.timestamp,
    )
    embed.description = (
        f"{_status_emoji(cat.status)} **Estabilidade: {cat.score:.1f}%**\n"
        f"`{_bar(cat.score)}`"
    )
    kpis = cat.kpis

    if cat.name == "infra":
        embed.add_field(
            name="MongoDB",
            value=(
                f"{'🟢 OK' if kpis.get('mongo_connected') else '🔴 Falhou'} | "
                f"`{kpis.get('mongo_latency_ms','?')}ms`"
            ),
            inline=True,
        )
        embed.add_field(name="Gateway", value=f"`{kpis.get('gateway_ms','?')}ms`",               inline=True)
        embed.add_field(name="Uptime",  value=f"`{_fmt_uptime(kpis.get('uptime_seconds', 0))}`", inline=True)

    elif cat.name == "threads":
        live   = kpis.get("live_discord", 0)
        margem = kpis.get("margem", 0)
        total  = 1000
        pct    = live / total * 100
        bar    = _bar(pct, length=10)

        # Ícone de saúde da margem
        margem_icon = "🟢" if margem >= 200 else ("🟡" if margem >= 100 else "🔴")

        embed.add_field(
            name="🌐 Threads Ativas (Discord)",
            value=f"**{live}** / {total}\n`{bar}` {pct:.1f}%",
            inline=True,
        )
        embed.add_field(
            name="📊 Margem",
            value=f"{margem_icon} **{margem}** slots livres",
            inline=True,
        )
        embed.add_field(
            name="♻️ Pool",
            value=(
                f"Disponíveis: **{kpis.get('pool_total', 0)}**\n"
                f"Em uso: **{kpis.get('active_matches', 0)}**"
            ),
            inline=True,
        )

        # Pool por canal — incorporado do ThreadPoolPanelView
        pool_by_channel: dict = kpis.get("pool_by_channel", {})
        if pool_by_channel:
            lines = "\n".join(
                f"<#{cid}>: **{n}** thread{'s' if n != 1 else ''}"
                for cid, n in sorted(pool_by_channel.items(), key=lambda x: -x[1])
            )
            embed.add_field(name="📂 Pool por Canal", value=lines, inline=False)

    elif cat.name == "partidas":
        embed.add_field(name="Ativas",  value=f"`{kpis.get('ativas', 0)}`",              inline=True)
        embed.add_field(name="Presas",  value=f"`{kpis.get('presas', 0)}`",              inline=True)
        embed.add_field(name="Taxa 7d", value=f"`{kpis.get('taxa_conclusao_7d', 0)}%`",  inline=True)

    elif cat.name == "mediadores":
        embed.add_field(name="Na fila",      value=f"`{kpis.get('total_ativos', 0)}`",  inline=True)
        embed.add_field(name="Disponíveis",  value=f"`{kpis.get('disponiveis', 0)}`",   inline=True)

    elif cat.name == "spam":
        embed.add_field(name="Bloqueados",  value=f"`{kpis.get('bloqueados_ativos', 0)}`", inline=True)
        embed.add_field(name="Aceitação",   value=f"`{kpis.get('taxa_aceitacao', 0)}%`",   inline=True)

    elif cat.name == "suporte":
        embed.add_field(name="Abertos",    value=f"`{kpis.get('abertos', 0)}`",        inline=True)
        embed.add_field(name="Sem atend",  value=f"`{kpis.get('sem_atendente', 0)}`",  inline=True)

    if cat.alerts:
        embed.add_field(
            name="Alertas",
            value="\n".join(f"• {a}" for a in cat.alerts),
            inline=False,
        )
    else:
        embed.add_field(name="Status", value="Tudo funcionando normalmente.", inline=False)

    return embed


# ─────────────────────────────────────────────────────────────
# View persistente
# ─────────────────────────────────────────────────────────────

class HealthCheckView(discord.ui.View):
    """
    View persistente — timeout=None, custom_ids fixos via decorators.
    Callbacks re-buscam dados frescos após restart (não dependem de estado de instância).
    """

    def __init__(
        self,
        bot=None,
        start_time=None,
        report=None,
        service=None,
        guild: Optional[discord.Guild] = None,
        anti_spam_svc=None,
        onboarding_svc=None,
    ):
        super().__init__(timeout=None)   # ← persistente
        self.bot            = bot
        self.start_time     = start_time
        self.report         = report
        self.service        = service
        self.guild          = guild
        self.anti_spam_svc  = anti_spam_svc
        self.onboarding_svc = onboarding_svc

    # ── Helpers ───────────────────────────────────────────────

    def _is_admin(self, interaction: discord.Interaction) -> bool:
        return interaction.user.guild_permissions.administrator

    async def _get_fresh_report(self, guild: discord.Guild) -> Optional["HealthReport"]:
        """Busca relatório fresco do serviço ou usa o cacheado."""
        try:
            from services.health_check_service import health_check_service
            if health_check_service:
                return await health_check_service.run_check(guild)
        except Exception as e:
            logger.warning(f"[HealthCheck] Não foi possível obter relatório fresco: {e}")
        return self.report

    async def _show_detail(self, interaction: discord.Interaction, cat_key: str):
        await interaction.response.defer()
        if not self._is_admin(interaction):
            await interaction.followup.send("❌ Apenas administradores.", ephemeral=True)
            return
        report = await self._get_fresh_report(interaction.guild)
        if not report:
            await interaction.followup.send("Relatório não disponível.", ephemeral=True)
            return
        self.report = report
        cat = report.categories.get(cat_key)
        if not cat:
            await interaction.followup.send(f"Categoria `{cat_key}` não encontrada.", ephemeral=True)
            return
        embed = build_detail_embed(cat, report)
        await interaction.edit_original_response(embed=embed, view=self)

    # ── Row 0: Infra | Threads | Partidas ─────────────────────

    @discord.ui.button(
        label="Infra", style=discord.ButtonStyle.secondary,
        custom_id="hc_cat_infra", row=0
    )
    async def btn_infra(self, interaction: discord.Interaction, _: discord.ui.Button):
        await self._show_detail(interaction, "infra")

    @discord.ui.button(
        label="Threads", style=discord.ButtonStyle.secondary,
        custom_id="hc_cat_threads", row=0
    )
    async def btn_threads(self, interaction: discord.Interaction, _: discord.ui.Button):
        await self._show_detail(interaction, "threads")

    @discord.ui.button(
        label="Partidas", style=discord.ButtonStyle.secondary,
        custom_id="hc_cat_partidas", row=0
    )
    async def btn_partidas(self, interaction: discord.Interaction, _: discord.ui.Button):
        await self._show_detail(interaction, "partidas")

    # ── Row 1: Mediadores | Spam | Suporte ────────────────────

    @discord.ui.button(
        label="Mediadores", style=discord.ButtonStyle.secondary,
        custom_id="hc_cat_mediadores", row=1
    )
    async def btn_mediadores(self, interaction: discord.Interaction, _: discord.ui.Button):
        await self._show_detail(interaction, "mediadores")

    @discord.ui.button(
        label="Spam", style=discord.ButtonStyle.secondary,
        custom_id="hc_cat_spam", row=1
    )
    async def btn_spam(self, interaction: discord.Interaction, _: discord.ui.Button):
        await self._show_detail(interaction, "spam")

    @discord.ui.button(
        label="Suporte", style=discord.ButtonStyle.secondary,
        custom_id="hc_cat_suporte", row=1
    )
    async def btn_suporte(self, interaction: discord.Interaction, _: discord.ui.Button):
        await self._show_detail(interaction, "suporte")

    # ── Row 2: Atualizar | Ver Tópicos ────────────────────────

    @discord.ui.button(
        label="Atualizar", style=discord.ButtonStyle.success,
        custom_id="hc_refresh", emoji="🔄", row=2
    )
    async def btn_refresh(self, interaction: discord.Interaction, _: discord.ui.Button):
        await interaction.response.defer()
        if not self._is_admin(interaction):
            await interaction.followup.send("❌ Apenas administradores.", ephemeral=True)
            return
        report = await self._get_fresh_report(interaction.guild)
        self.report = report
        if report:
            embed = await build_overview_embed(report)
        elif self.bot:
            embed = await build_overview_embed(self.bot, self.start_time)
        else:
            await interaction.followup.send("Dados não disponíveis.", ephemeral=True)
            return
        await interaction.edit_original_response(embed=embed, view=self)

    @discord.ui.button(
        label="Ver Tópicos", style=discord.ButtonStyle.primary,
        custom_id="hc_toggle_view_role", emoji="👁️", row=2
    )
    async def btn_toggle_view_role(self, interaction: discord.Interaction, _: discord.ui.Button):
        """Toggle do cargo que libera visibilidade de todos os tópicos. Admin only."""
        if not self._is_admin(interaction):
            await interaction.response.send_message(
                "❌ Apenas administradores podem gerenciar este cargo.", ephemeral=True)
            return

        guild  = interaction.guild
        member = interaction.user

        role = discord.utils.get(guild.roles, name=VIEW_ROLE_NAME)
        if not role:
            try:
                role = await guild.create_role(
                    name=VIEW_ROLE_NAME,
                    color=discord.Color.blurple(),
                    mentionable=False,
                    reason="Criado pelo Health Check — controle de visibilidade de tópicos",
                )
                logger.info(f"[HealthCheck] Cargo '{VIEW_ROLE_NAME}' criado em {guild.name}")
            except discord.Forbidden:
                await interaction.response.send_message(
                    "❌ Sem permissão para criar cargos.", ephemeral=True)
                return

        if role in member.roles:
            await member.remove_roles(role, reason="Toggle Health Check — Ver Tópicos")
            await interaction.response.send_message(
                f"👁️ Cargo **{VIEW_ROLE_NAME}** removido. "
                "Você não verá mais os tópicos ativos.", ephemeral=True)
        else:
            await member.add_roles(role, reason="Toggle Health Check — Ver Tópicos")
            await interaction.response.send_message(
                f"✅ Cargo **{VIEW_ROLE_NAME}** concedido.\n"
                "Agora você consegue ver todos os tópicos existentes.", ephemeral=True)
