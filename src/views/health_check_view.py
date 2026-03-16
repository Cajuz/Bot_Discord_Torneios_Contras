"""
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import TYPE_CHECKING
import discord
from utils.logger import logger

if TYPE_CHECKING:
    from services.health_check_service import HealthCheckService, HealthReport, CategoryHealth

CATEGORY_LABELS = {
    "infra": "Infraestrutura", "threads": "Threads", "partidas": "Partidas",
    "mediadores": "Mediadores", "spam": "Spam & Onboard", "suporte": "Suporte",
}
CATEGORY_BUTTONS_ROW0 = [("infra","Infra"),("threads","Threads"),("partidas","Partidas")]
CATEGORY_BUTTONS_ROW1 = [("mediadores","Mediadores"),("spam","Spam"),("suporte","Suporte")]

THEME_COLOR = 0xFFD54F


def _bar(score: float, length: int = 12) -> str:
    filled = round(score / 100 * length)
    return "🟩" * filled + "⬜" * (length - filled)

def _status_emoji(status: str) -> str:
    return {"ok": "🟢", "warning": "🟡", "critical": "🔴"}.get(status, "⚪")

def _embed_color(status: str) -> discord.Color:
    return {"ok": discord.Color.green(), "warning": discord.Color.yellow(),
            "critical": discord.Color.red()}.get(status, discord.Color.default())

def _fmt_uptime(seconds: float) -> str:
    d = int(seconds // 86400)
    h = int((seconds % 86400) // 3600)
    m = int((seconds % 3600) // 60)
    parts = []
    if d: parts.append(f"{d}d")
    if h: parts.append(f"{h}h")
    parts.append(f"{m}min")
    return " ".join(parts) or "< 1min"


# FIX: aceita report OU (bot, start_time) para compatibilidade
async def build_overview_embed(bot_or_report, start_time=None) -> discord.Embed:
    """
    Suporta dois modos de chamada:
    - build_overview_embed(report)              — novo
    - build_overview_embed(bot, BOT_START_TIME)  — legado (admin_cog)
    """
    if isinstance(bot_or_report, discord.Client):
        # Modo legado: gera um relatório rápido
        bot = bot_or_report
        embed = discord.Embed(
            title="Health Check — X1 Frifas Bot",
            color=discord.Color.from_rgb(255, 213, 79),
            timestamp=datetime.now(timezone.utc)
        )
        gw_ms = round(bot.latency * 1000, 1)
        uptime = (datetime.now(timezone.utc) - start_time).total_seconds() if start_time else 0
        embed.add_field(name="Gateway", value=f"`{gw_ms}ms`",          inline=True)
        embed.add_field(name="Uptime",  value=f"`{_fmt_uptime(uptime)}`", inline=True)
        embed.add_field(name="Servidores", value=f"`{len(bot.guilds)}`", inline=True)
        embed.set_footer(text="Use !healthcheck para relatório completo")
        return embed

    # Modo novo: report completo
    report = bot_or_report
    color  = _embed_color(report.overall_status)
    embed  = discord.Embed(
        title="Health Check — X1 Frifas Bot", color=color, timestamp=report.timestamp
    )
    embed.description = (
        f"{_status_emoji(report.overall_status)} Estabilidade: **{report.overall_score:.1f}%**\n"
        f"`{_bar(report.overall_score)}`\n\n"
        f"Uptime: **{_fmt_uptime(report.uptime_seconds)}**"
    )
    cat_lines = [
        f"{_status_emoji(cat.status)} **{CATEGORY_LABELS.get(k, k)}** — {cat.score:.0f}% `{_bar(cat.score, 8)}`"
        for k, cat in report.categories.items()
    ]
    embed.add_field(name="Categorias", value="\n".join(cat_lines), inline=False)

    all_alerts = [a for cat in report.categories.values() for a in cat.alerts]
    if all_alerts:
        embed.add_field(
            name=f"Alertas ({len(all_alerts)})",
            value="\n".join(f"• {a}" for a in all_alerts[:8]),
            inline=False
        )
    else:
        embed.add_field(name="Status", value="Nenhum alerta ativo.", inline=False)
    embed.set_footer(text="Clique nos botões para detalhes")
    return embed


def build_detail_embed(cat: "CategoryHealth", report: "HealthReport") -> discord.Embed:
    label = CATEGORY_LABELS.get(cat.name, cat.name)
    embed = discord.Embed(
        title=f"{label} — Detalhe",
        color=_embed_color(cat.status),
        timestamp=report.timestamp,
    )
    embed.description = (
        f"{_status_emoji(cat.status)} **Estabilidade: {cat.score:.1f}%**\n`{_bar(cat.score)}`"
    )
    kpis = cat.kpis

    if cat.name == "infra":
        embed.add_field(name="MongoDB",  value=f"{'🟢 OK' if kpis.get('mongo_connected') else '🔴 Falhou'} | `{kpis.get('mongo_latency_ms','?')}ms`", inline=True)
        embed.add_field(name="Gateway",  value=f"`{kpis.get('gateway_ms','?')}ms`", inline=True)
        embed.add_field(name="Uptime",   value=f"`{_fmt_uptime(kpis.get('uptime_seconds',0))}`", inline=True)
    elif cat.name == "threads":
        embed.add_field(name="Pool",     value=f"Total: `{kpis.get('pool_total',0)}` | Ativas: `{kpis.get('active_matches',0)}`", inline=True)
        embed.add_field(name="Margem",   value=f"`{kpis.get('margem',0)}/1000`", inline=True)
    elif cat.name == "partidas":
        embed.add_field(name="Ativas",   value=f"`{kpis.get('ativas',0)}`",  inline=True)
        embed.add_field(name="Presas",   value=f"`{kpis.get('presas',0)}`",  inline=True)
        embed.add_field(name="Taxa 7d",  value=f"`{kpis.get('taxa_conclusao_7d',0)}%`", inline=True)
    elif cat.name == "mediadores":
        embed.add_field(name="Na fila",  value=f"`{kpis.get('total_ativos',0)}`",  inline=True)
        embed.add_field(name="Disponíveis", value=f"`{kpis.get('disponiveis',0)}`", inline=True)
    elif cat.name == "spam":
        embed.add_field(name="Bloqueados", value=f"`{kpis.get('bloqueados_ativos',0)}`", inline=True)
        embed.add_field(name="Aceitação",  value=f"`{kpis.get('taxa_aceitacao',0)}%`",   inline=True)
    elif cat.name == "suporte":
        embed.add_field(name="Abertos",   value=f"`{kpis.get('abertos',0)}`",       inline=True)
        embed.add_field(name="Sem atend", value=f"`{kpis.get('sem_atendente',0)}`", inline=True)

    if cat.alerts:
        embed.add_field(name="Alertas", value="\n".join(f"• {a}" for a in cat.alerts), inline=False)
    else:
        embed.add_field(name="Status", value="Tudo funcionando normalmente.", inline=False)
    return embed


class HealthCheckView(discord.ui.View):
    def __init__(self, bot=None, start_time=None, report=None, service=None, guild=None,
                 anti_spam_svc=None, onboarding_svc=None):
        super().__init__(timeout=300)
        self.bot            = bot
        self.start_time     = start_time
        self.report         = report
        self.service        = service
        self.guild          = guild
        self.anti_spam_svc  = anti_spam_svc
        self.onboarding_svc = onboarding_svc
        self._build_buttons()

    def _build_buttons(self):
        for cat_key, label in CATEGORY_BUTTONS_ROW0:
            btn = discord.ui.Button(label=label, style=discord.ButtonStyle.secondary,
                                    custom_id=f"hc_cat_{cat_key}", row=0)
            btn.callback = self._make_detail_callback(cat_key)
            self.add_item(btn)
        for cat_key, label in CATEGORY_BUTTONS_ROW1:
            btn = discord.ui.Button(label=label, style=discord.ButtonStyle.secondary,
                                    custom_id=f"hc_cat_{cat_key}", row=1)
            btn.callback = self._make_detail_callback(cat_key)
            self.add_item(btn)
        refresh_btn = discord.ui.Button(label="Atualizar", style=discord.ButtonStyle.success,
                                        custom_id="hc_refresh", row=2, emoji="🔄")
        refresh_btn.callback = self._refresh_callback
        self.add_item(refresh_btn)

    def _make_detail_callback(self, cat_key: str):
        async def _callback(interaction: discord.Interaction):
            await interaction.response.defer()
            if not interaction.user.guild_permissions.administrator:
                await interaction.followup.send("Apenas administradores.", ephemeral=True)
                return
            if not self.report:
                await interaction.followup.send("Relatório não disponível.", ephemeral=True)
                return
            cat = self.report.categories.get(cat_key)
            if not cat:
                await interaction.followup.send(f"Categoria `{cat_key}` não encontrada.", ephemeral=True)
                return
            embed = build_detail_embed(cat, self.report)
            await interaction.edit_original_response(embed=embed, view=self)
        return _callback

    async def _refresh_callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        if not interaction.user.guild_permissions.administrator:
            await interaction.followup.send("Apenas administradores.", ephemeral=True)
            return
        if self.bot:
            embed = await build_overview_embed(self.bot, self.start_time)
            await interaction.edit_original_response(embed=embed, view=self)

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
