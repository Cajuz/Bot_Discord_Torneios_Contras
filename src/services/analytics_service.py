"""
analytics_service.py - Dashboards completos com matplotlib.
"""
from __future__ import annotations

import io
from datetime import timedelta
from functools import partial
from time import monotonic
from typing import Awaitable, Callable, Optional

import discord
from discord.ext import tasks
import matplotlib

matplotlib.use("Agg")
import matplotlib.gridspec as gridspec
import matplotlib.pyplot as plt
import numpy as np
from scipy.interpolate import make_interp_spline

from config.database import db
from utils.datetime_utils import utcnow
from utils.logger import logger

# ── Cores do embed ────────────────────────────────────────────────────────────
THEME  = 0xFFD54F
THEME2 = 0xFFA726
GREEN  = 0x2ECC71

# ── Status das partidas ───────────────────────────────────────────────────────
STATUS_FINALIZADO_LIST = [
    "aguardando_premio",
    "finalizado",
    "concluido",
]
STATUS_CANCELADO_LIST = [
    "cancelado",
]

# ── Paleta de cores dos gráficos ──────────────────────────────────────────────
BG_COLOR    = "#161925"
PANEL_COLOR = "#1f2333"
GRID_COLOR  = "#31374d"
TEXT_COLOR  = "#E8EAED"
MUTED       = "#98A2B3"
GOLD        = "#FFD54F"
ORANGE      = "#FFA726"
TEAL        = "#2ECC71"
RED         = "#FF6B6B"
BLUE        = "#4FC3F7"
PURPLE      = "#8E7CFF"

# ── Configurações centralizadas ───────────────────────────────────────────────
class AnalyticsConfig:
    TOP_MEDIATORS     = 8
    TOP_PLAYERS       = 10
    TOP_INFLUENCERS   = 10
    TOP_CATEGORIES    = 6
    TOP_AGENTS        = 5
    LOOKBACK_DAYS     = 30
    CACHE_TTL_SECONDS = 300
    CHART_DPI         = 135


# ── Cache em memória ──────────────────────────────────────────────────────────
_render_cache: dict[str, tuple[float, discord.Embed, bytes]] = {}


async def _cached_render(
    key: str,
    render_fn: Callable,
    *args,
    ttl: float = AnalyticsConfig.CACHE_TTL_SECONDS,
) -> tuple[discord.Embed, discord.File]:
    now_mono = monotonic()
    if key in _render_cache:
        ts, embed, png_bytes = _render_cache[key]
        if now_mono - ts < ttl:
            filename = key.split(":")[0] + ".png"
            file = discord.File(io.BytesIO(png_bytes), filename=filename)
            return embed, file

    embed, file = await render_fn(*args)

    file.fp.seek(0)
    png_bytes = file.fp.read()
    file.fp.seek(0)
    _render_cache[key] = (now_mono, embed, png_bytes)
    return embed, file


# ── Períodos dos gráficos ─────────────────────────────────────────────────────
MATCH_PERIODS = {
    "daily": {
        "label":         "Diario",
        "embed_label":   "Ultimas 24 horas",
        "delta":         timedelta(hours=24),
        "bucket_format": "%Y-%m-%d %H:00",
        "tick_format":   "%Hh",
        "step":          timedelta(hours=1),
        "points":        24,
    },
    "weekly": {
        "label":         "Semanal",
        "embed_label":   "Ultimos 7 dias",
        "delta":         timedelta(days=7),
        "bucket_format": "%Y-%m-%d",
        "tick_format":   "%d/%m",
        "step":          timedelta(days=1),
        "points":        7,
    },
    "monthly": {
        "label":         "Mensal",
        "embed_label":   "Ultimos 30 dias",
        "delta":         timedelta(days=30),
        "bucket_format": "%Y-%m-%d",
        "tick_format":   "%d/%m",
        "step":          timedelta(days=1),
        "points":        30,
    },
}


# ── Helpers de formatação ─────────────────────────────────────────────────────
def _pct(a, b) -> str:
    return f"{a / b * 100:.1f}%" if b else "0%"


def _brl(v: float) -> str:
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


# ── Helpers de gráfico ────────────────────────────────────────────────────────
def _save_figure(fig) -> io.BytesIO:
    buf = io.BytesIO()
    try:
        fig.savefig(buf, format="png", dpi=AnalyticsConfig.CHART_DPI,
                    bbox_inches="tight", facecolor=BG_COLOR)
        buf.seek(0)
        return buf
    finally:
        plt.close(fig)


def _style_axis(ax):
    ax.set_facecolor(PANEL_COLOR)
    for spine in ax.spines.values():
        spine.set_color(GRID_COLOR)
    ax.tick_params(colors=MUTED, labelsize=10)
    ax.grid(color=GRID_COLOR, linestyle="--", linewidth=0.6, alpha=0.55)
    ax.set_axisbelow(True)


def _add_fig_header(fig, title: str, subtitle: str = "") -> None:
    fig.text(0.02, 0.98, title, color=TEXT_COLOR, fontsize=13, fontweight="bold", va="top")
    if subtitle:
        fig.text(0.02, 0.92, subtitle, color=MUTED, fontsize=8.5, va="top")


def _slots(now, period_key: str):
    cfg = MATCH_PERIODS[period_key]
    since = now - cfg["delta"]
    if cfg["step"] == timedelta(hours=1):
        base = since.replace(minute=0, second=0, microsecond=0)
    else:
        base = since.replace(hour=0, minute=0, second=0, microsecond=0)
    return [base + cfg["step"] * i for i in range(cfg["points"])]


def _plot_smooth_line(ax, x, y_vals, color, label=None):
    ax.fill_between(x, y_vals, color=color, alpha=0.18)
    ax.plot(x, y_vals, color=color, linewidth=2.5, marker="o", markersize=4, label=label)


# ── Helpers de queries ────────────────────────────────────────────────────────
async def _safe_count(collection, query: dict, fallback: int = 0) -> int:
    try:
        return await collection.count_documents(query)
    except Exception as e:
        logger.error(f"[Analytics] count_documents falhou: {e}")
        return fallback


async def _safe_aggregate(collection, pipeline: list, limit: int, fallback=None):
    if fallback is None:
        fallback = []
    try:
        return await collection.aggregate(pipeline).to_list(limit)
    except Exception as e:
        logger.error(f"[Analytics] aggregate falhou: {e}")
        return fallback


async def _debug_status_values() -> list[str]:
    col = db.get_collection("matches")
    try:
        result = await col.distinct("status")
        logger.info(f"[Analytics][DEBUG] Status encontrados: {result}")
        return result
    except Exception as e:
        logger.error(f"[Analytics][DEBUG] Erro ao buscar status: {e}")
        return []


# ══════════════════════════════════════════════════════════════════════════════
# Views do Discord
# ══════════════════════════════════════════════════════════════════════════════

class MatchesDashboardView(discord.ui.View):
    def __init__(self, service: "AnalyticsService", period_key: str = "daily"):
        super().__init__(timeout=None)
        self.service    = service
        self.period_key = period_key
        self.btn_daily._period_key   = "daily"
        self.btn_weekly._period_key  = "weekly"
        self.btn_monthly._period_key = "monthly"
        self._sync_styles()

    def _sync_styles(self):
        for child in self.children:
            if not isinstance(child, discord.ui.Button):
                continue
            key = getattr(child, "_period_key", None)
            if key:
                child.style = (
                    discord.ButtonStyle.primary
                    if key == self.period_key
                    else discord.ButtonStyle.secondary
                )

    async def _update_period(self, interaction: discord.Interaction, period_key: str):
        self.period_key = period_key
        self._sync_styles()
        await interaction.response.defer()
        embed, file = await self.service._render_matches_dashboard(period_key)
        await interaction.edit_original_response(embed=embed, attachments=[file], view=self)

    @discord.ui.button(label="Hoje",      style=discord.ButtonStyle.primary,   custom_id="matches_daily")
    async def btn_daily(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._update_period(interaction, "daily")

    @discord.ui.button(label="Semanal",   style=discord.ButtonStyle.secondary, custom_id="matches_weekly")
    async def btn_weekly(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._update_period(interaction, "weekly")

    @discord.ui.button(label="Mensal",    style=discord.ButtonStyle.secondary, custom_id="matches_monthly")
    async def btn_monthly(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._update_period(interaction, "monthly")

    @discord.ui.button(label="Atualizar", style=discord.ButtonStyle.success,   custom_id="matches_refresh")
    async def btn_refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._update_period(interaction, self.period_key)


class MediatorsDashboardView(discord.ui.View):
    def __init__(self, service: "AnalyticsService", period_key: str = "monthly"):
        super().__init__(timeout=None)
        self.service    = service
        self.period_key = period_key
        self.btn_daily._period_key   = "daily"
        self.btn_weekly._period_key  = "weekly"
        self.btn_monthly._period_key = "monthly"
        self._sync_styles()

    def _sync_styles(self):
        for child in self.children:
            if not isinstance(child, discord.ui.Button):
                continue
            key = getattr(child, "_period_key", None)
            if key:
                child.style = (
                    discord.ButtonStyle.primary
                    if key == self.period_key
                    else discord.ButtonStyle.secondary
                )

    async def _update_period(self, interaction: discord.Interaction, period_key: str):
        self.period_key = period_key
        self._sync_styles()
        await interaction.response.defer()
        embed, file = await self.service._render_mediators_dashboard(period_key)
        await interaction.edit_original_response(embed=embed, attachments=[file], view=self)

    @discord.ui.button(label="Hoje",      style=discord.ButtonStyle.secondary, custom_id="mediators_daily")
    async def btn_daily(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._update_period(interaction, "daily")

    @discord.ui.button(label="Semanal",   style=discord.ButtonStyle.secondary, custom_id="mediators_weekly")
    async def btn_weekly(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._update_period(interaction, "weekly")

    @discord.ui.button(label="Mensal",    style=discord.ButtonStyle.primary,   custom_id="mediators_monthly")
    async def btn_monthly(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._update_period(interaction, "monthly")

    @discord.ui.button(label="Atualizar", style=discord.ButtonStyle.success,   custom_id="mediators_refresh")
    async def btn_refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._update_period(interaction, self.period_key)


class PlayersDashboardView(discord.ui.View):
    def __init__(self, service: "AnalyticsService", period_key: str = "weekly"):
        super().__init__(timeout=None)
        self.service    = service
        self.period_key = period_key
        self._sync_styles()

    def _sync_styles(self):
        pass

    @discord.ui.button(label="🏆 Rank",       style=discord.ButtonStyle.primary,   custom_id="players_open_rank")
    async def btn_rank(self, interaction: discord.Interaction, button: discord.ui.Button):
        view  = _RankGeralEphemeralView(self.service, interaction.user.id, "weekly")
        embed = await view._render()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label="👤 Meu Perfil", style=discord.ButtonStyle.secondary, custom_id="players_open_perfil")
    async def btn_perfil(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = await _render_perfil_embed(interaction.user)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Atualizar",     style=discord.ButtonStyle.success,   custom_id="players_refresh")
    async def btn_refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        embed = await self.service._render_players_dashboard(self.period_key)
        await interaction.edit_original_response(embed=embed, view=self)


class _RankGeralEphemeralView(discord.ui.View):
    def __init__(self, service: "AnalyticsService", user_id: int, period_key: str = "weekly"):
        super().__init__(timeout=180)
        self.service    = service
        self.user_id    = user_id
        self.period_key = period_key
        self._sync_styles()

    def _sync_styles(self):
        for child in self.children:
            if not isinstance(child, discord.ui.Button):
                continue
            if child.custom_id == "rank_ep_7d":
                child.style = discord.ButtonStyle.primary if self.period_key == "weekly" else discord.ButtonStyle.secondary
            elif child.custom_id == "rank_ep_30d":
                child.style = discord.ButtonStyle.primary if self.period_key == "monthly" else discord.ButtonStyle.secondary

    async def _render(self) -> discord.Embed:
        return await self.service._render_players_dashboard(
            self.period_key, highlight_id=self.user_id
        )

    async def _update(self, interaction: discord.Interaction):
        self._sync_styles()
        embed = await self._render()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="7 dias",    style=discord.ButtonStyle.primary,   custom_id="rank_ep_7d")
    async def btn_7d(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.period_key = "weekly"
        await self._update(interaction)

    @discord.ui.button(label="30 dias",   style=discord.ButtonStyle.secondary, custom_id="rank_ep_30d")
    async def btn_30d(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.period_key = "monthly"
        await self._update(interaction)

    @discord.ui.button(label="Atualizar", style=discord.ButtonStyle.success,   custom_id="rank_ep_refresh")
    async def btn_refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._update(interaction)


class SupportDashboardView(discord.ui.View):
    def __init__(self, service: "AnalyticsService", period_key: str = "monthly"):
        super().__init__(timeout=None)
        self.service    = service
        self.period_key = period_key
        self.btn_daily._period_key   = "daily"
        self.btn_weekly._period_key  = "weekly"
        self.btn_monthly._period_key = "monthly"
        self._sync_styles()

    def _sync_styles(self):
        for child in self.children:
            if not isinstance(child, discord.ui.Button):
                continue
            key = getattr(child, "_period_key", None)
            if key:
                child.style = (
                    discord.ButtonStyle.primary
                    if key == self.period_key
                    else discord.ButtonStyle.secondary
                )

    async def _update_period(self, interaction: discord.Interaction, period_key: str):
        self.period_key = period_key
        self._sync_styles()
        await interaction.response.defer()
        embed, file = await self.service._render_support_dashboard(period_key)
        await interaction.edit_original_response(embed=embed, attachments=[file], view=self)

    @discord.ui.button(label="Hoje",      style=discord.ButtonStyle.secondary, custom_id="support_daily")
    async def btn_daily(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._update_period(interaction, "daily")

    @discord.ui.button(label="Semanal",   style=discord.ButtonStyle.secondary, custom_id="support_weekly")
    async def btn_weekly(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._update_period(interaction, "weekly")

    @discord.ui.button(label="Mensal",    style=discord.ButtonStyle.primary,   custom_id="support_monthly")
    async def btn_monthly(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._update_period(interaction, "monthly")

    @discord.ui.button(label="Atualizar", style=discord.ButtonStyle.success,   custom_id="support_refresh")
    async def btn_refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._update_period(interaction, self.period_key)


class ServerDashboardView(discord.ui.View):
    def __init__(self, service: "AnalyticsService", guild: discord.Guild, period_key: str = "monthly"):
        super().__init__(timeout=None)
        self.service    = service
        self.guild      = guild
        self.period_key = period_key
        self.btn_daily._period_key   = "daily"
        self.btn_weekly._period_key  = "weekly"
        self.btn_monthly._period_key = "monthly"
        self._sync_styles()

    def _sync_styles(self):
        for child in self.children:
            if not isinstance(child, discord.ui.Button):
                continue
            key = getattr(child, "_period_key", None)
            if key:
                child.style = (
                    discord.ButtonStyle.primary
                    if key == self.period_key
                    else discord.ButtonStyle.secondary
                )

    async def _update_period(self, interaction: discord.Interaction, period_key: str):
        self.period_key = period_key
        self._sync_styles()
        await interaction.response.defer()
        embed, file = await self.service._render_server_dashboard(self.guild, period_key)
        await interaction.edit_original_response(embed=embed, attachments=[file], view=self)

    @discord.ui.button(label="Hoje",      style=discord.ButtonStyle.secondary, custom_id="server_daily")
    async def btn_daily(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._update_period(interaction, "daily")

    @discord.ui.button(label="Semanal",   style=discord.ButtonStyle.secondary, custom_id="server_weekly")
    async def btn_weekly(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._update_period(interaction, "weekly")

    @discord.ui.button(label="Mensal",    style=discord.ButtonStyle.primary,   custom_id="server_monthly")
    async def btn_monthly(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._update_period(interaction, "monthly")

    @discord.ui.button(label="Atualizar", style=discord.ButtonStyle.success,   custom_id="server_refresh")
    async def btn_refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._update_period(interaction, self.period_key)


class InfluencersDashboardView(discord.ui.View):
    def __init__(self, service: "AnalyticsService", guild: discord.Guild, period_key: str = "monthly"):
        super().__init__(timeout=None)
        self.service    = service
        self.guild      = guild
        self.period_key = period_key
        self.btn_daily._period_key   = "daily"
        self.btn_weekly._period_key  = "weekly"
        self.btn_monthly._period_key = "monthly"
        self._sync_styles()

    def _sync_styles(self):
        for child in self.children:
            if not isinstance(child, discord.ui.Button):
                continue
            key = getattr(child, "_period_key", None)
            if key:
                child.style = (
                    discord.ButtonStyle.primary
                    if key == self.period_key
                    else discord.ButtonStyle.secondary
                )

    async def _update_period(self, interaction: discord.Interaction, period_key: str):
        self.period_key = period_key
        self._sync_styles()
        await interaction.response.defer()
        embed, file = await self.service._render_influencers_dashboard(self.guild, period_key)
        await interaction.edit_original_response(embed=embed, attachments=[file], view=self)

    @discord.ui.button(label="Hoje",      style=discord.ButtonStyle.secondary, custom_id="influencers_daily")
    async def btn_daily(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._update_period(interaction, "daily")

    @discord.ui.button(label="Semanal",   style=discord.ButtonStyle.secondary, custom_id="influencers_weekly")
    async def btn_weekly(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._update_period(interaction, "weekly")

    @discord.ui.button(label="Mensal",    style=discord.ButtonStyle.primary,   custom_id="influencers_monthly")
    async def btn_monthly(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._update_period(interaction, "monthly")

    @discord.ui.button(label="Atualizar", style=discord.ButtonStyle.success,   custom_id="influencers_refresh")
    async def btn_refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._update_period(interaction, self.period_key)


class ApostasDashboardView(discord.ui.View):
    def __init__(self, service: "AnalyticsService", period_key: str = "daily"):
        super().__init__(timeout=None)
        self.service    = service
        self.period_key = period_key
        self.btn_daily._period_key   = "daily"
        self.btn_weekly._period_key  = "weekly"
        self.btn_monthly._period_key = "monthly"
        self._sync_styles()

    def _sync_styles(self):
        for child in self.children:
            if not isinstance(child, discord.ui.Button):
                continue
            key = getattr(child, "_period_key", None)
            if key:
                child.style = (
                    discord.ButtonStyle.primary
                    if key == self.period_key
                    else discord.ButtonStyle.secondary
                )

    async def _update_period(self, interaction: discord.Interaction, period_key: str):
        self.period_key = period_key
        self._sync_styles()
        await interaction.response.defer()
        embed, file = await self.service._render_apostas_dashboard(period_key)
        await interaction.edit_original_response(embed=embed, attachments=[file], view=self)

    @discord.ui.button(label="Hoje",      style=discord.ButtonStyle.primary,   custom_id="apostas_daily")
    async def btn_daily(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._update_period(interaction, "daily")

    @discord.ui.button(label="Semanal",   style=discord.ButtonStyle.secondary, custom_id="apostas_weekly")
    async def btn_weekly(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._update_period(interaction, "weekly")

    @discord.ui.button(label="Mensal",    style=discord.ButtonStyle.secondary, custom_id="apostas_monthly")
    async def btn_monthly(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._update_period(interaction, "monthly")

    @discord.ui.button(label="Atualizar", style=discord.ButtonStyle.success,   custom_id="apostas_refresh")
    async def btn_refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._update_period(interaction, self.period_key)


class MembrosMovDashboardView(discord.ui.View):
    def __init__(self, service: "AnalyticsService", period_key: str = "monthly"):
        super().__init__(timeout=None)
        self.service    = service
        self.period_key = period_key
        self.btn_daily._period_key   = "daily"
        self.btn_weekly._period_key  = "weekly"
        self.btn_monthly._period_key = "monthly"
        self._sync_styles()

    def _sync_styles(self):
        for child in self.children:
            if not isinstance(child, discord.ui.Button):
                continue
            key = getattr(child, "_period_key", None)
            if key:
                child.style = (
                    discord.ButtonStyle.primary
                    if key == self.period_key
                    else discord.ButtonStyle.secondary
                )

    async def _update_period(self, interaction: discord.Interaction, period_key: str):
        self.period_key = period_key
        self._sync_styles()
        await interaction.response.defer()
        embed, file = await self.service._render_membros_mov_dashboard(interaction.guild, period_key)
        await interaction.edit_original_response(embed=embed, attachments=[file], view=self)

    @discord.ui.button(label="Hoje",      style=discord.ButtonStyle.secondary, custom_id="membros_mov_daily")
    async def btn_daily(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._update_period(interaction, "daily")

    @discord.ui.button(label="Semanal",   style=discord.ButtonStyle.secondary, custom_id="membros_mov_weekly")
    async def btn_weekly(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._update_period(interaction, "weekly")

    @discord.ui.button(label="Mensal",    style=discord.ButtonStyle.primary,   custom_id="membros_mov_monthly")
    async def btn_monthly(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._update_period(interaction, "monthly")

    @discord.ui.button(label="Atualizar", style=discord.ButtonStyle.success,   custom_id="membros_mov_refresh")
    async def btn_refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._update_period(interaction, self.period_key)


# ══════════════════════════════════════════════════════════════════════════════
# Helper: embed de perfil pessoal
# ══════════════════════════════════════════════════════════════════════════════

async def _render_perfil_embed(user: discord.Member | discord.User) -> discord.Embed:
    col = db.get_collection("matches")

    total  = await _safe_count(col, {"player_ids": str(user.id)})
    wins   = await _safe_count(col, {"player_ids": str(user.id), "winner_id": str(user.id)})
    losses = total - wins

    vol_agg = await _safe_aggregate(col, [
        {"$match": {"player_ids": str(user.id)}},
        {"$group": {"_id": None, "s": {"$sum": "$bet_value"}}},
    ], 1)
    volume = vol_agg[0]["s"] if vol_agg else 0.0

    recent = await _safe_aggregate(col, [
        {"$match": {"player_ids": str(user.id)}},
        {"$sort": {"created_at": -1}},
        {"$limit": 20},
        {"$project": {"winner_id": 1}},
    ], 20)
    streak = 0
    for r in recent:
        if str(r.get("winner_id")) == str(user.id):
            streak += 1
        else:
            break

    all_players = await _safe_aggregate(col, [
        {"$unwind": "$player_ids"},
        {"$group": {
            "_id":  "$player_ids",
            "wins": {"$sum": {"$cond": [{"$eq": ["$winner_id", "$player_ids"]}, 1, 0]}},
        }},
        {"$sort": {"wins": -1}},
        {"$limit": 500},
    ], 500)
    position = next(
        (i + 1 for i, r in enumerate(all_players) if str(r["_id"]) == str(user.id)),
        None,
    )

    last5 = await _safe_aggregate(col, [
        {"$match": {"player_ids": str(user.id)}},
        {"$sort": {"created_at": -1}},
        {"$limit": 5},
        {"$project": {"winner_id": 1, "bet_value": 1, "created_at": 1}},
    ], 5)
    history_lines = []
    for r in last5:
        won  = str(r.get("winner_id")) == str(user.id)
        icon = "✅" if won else "❌"
        val  = _brl(r.get("bet_value", 0))
        history_lines.append(f"{icon} {val}")

    embed = discord.Embed(title=f"📊 Perfil — {user.display_name}", color=THEME)
    embed.set_thumbnail(url=user.display_avatar.url)
    embed.add_field(name="Vitórias",        value=f"`{wins}`",              inline=True)
    embed.add_field(name="Derrotas",        value=f"`{losses}`",            inline=True)
    embed.add_field(name="Win Rate",        value=f"`{_pct(wins, total)}`", inline=True)
    embed.add_field(name="Total Partidas",  value=f"`{total}`",             inline=True)
    embed.add_field(name="Volume Total",    value=f"**{_brl(volume)}**",    inline=True)
    embed.add_field(name="Sequência atual", value=f"`{streak}` vitórias",   inline=True)

    if position:
        medals  = {1: "🥇", 2: "🥈", 3: "🥉"}
        pos_str = medals.get(position, f"#{position}")
        embed.add_field(name="Posição Geral", value=f"**{pos_str}**", inline=True)

    if history_lines:
        embed.add_field(name="Últimas partidas", value="  ".join(history_lines), inline=False)

    embed.set_footer(text="Histórico completo · Só você pode ver isso")
    return embed


# ══════════════════════════════════════════════════════════════════════════════
# Serviço principal
# ══════════════════════════════════════════════════════════════════════════════

class AnalyticsService:
    def __init__(self):
        self.bot: Optional[discord.Client] = None

    def start_task(self, bot: discord.Client):
        self.bot = bot
        if not self.hourly_update.is_running():
            self.hourly_update.start()

    @tasks.loop(hours=1)
    async def hourly_update(self):
        if not self.bot:
            return
        for guild in self.bot.guilds:
            try:
                await self.update_all(guild)
            except Exception as e:
                logger.error(f"[Analytics] Erro em {guild.name}: {e}")

    @hourly_update.before_loop
    async def before_hourly(self):
        if self.bot:
            await self.bot.wait_until_ready()

    async def update_all(self, guild: discord.Guild):
        await self._matches(guild)
        await self._mediators(guild)
        await self._players(guild)
        await self._support(guild)
        await self._server(guild)
        await self._influencers(guild)
        await self._apostas(guild)
        await self._membros_mov(guild)

    async def publish_all_now(self, guild: discord.Guild):
        await self.update_all(guild)

    # ── Postagem ──────────────────────────────────────────────────────────────

    async def _post_dashboard(
        self,
        guild: discord.Guild,
        ch_name: str,
        message_key: str,
        embed: discord.Embed,
        file: discord.File,
        view: Optional[discord.ui.View] = None,
    ):
        ch = discord.utils.get(guild.text_channels, name=ch_name)
        if not ch:
            return

        try:
            target = None
            async for message in ch.history(limit=50):
                if message.author != guild.me or not message.embeds:
                    continue
                footer = message.embeds[0].footer.text if message.embeds[0].footer else ""
                if f"[{message_key}]" in footer:
                    target = message
                    break

            if target:
                await target.edit(embed=embed, attachments=[file], view=view)
            else:
                await ch.send(embed=embed, file=file, view=view)

        except discord.Forbidden:
            logger.warning(f"[Analytics] Sem permissão em #{ch_name}")
        except Exception as e:
            logger.warning(f"[Analytics] #{ch_name}: {e}")

    # ── Dashboard: Partidas ───────────────────────────────────────────────────

    async def _render_matches_dashboard(self, period_key: str) -> tuple[discord.Embed, discord.File]:
        cfg   = MATCH_PERIODS[period_key]
        col   = db.get_collection("matches")
        now   = utcnow()
        since = now - cfg["delta"]
        query = {"created_at": {"$gte": since}}

        total       = await _safe_count(col, query)
        finalizadas = await _safe_count(col, {**query, "status": {"$in": STATUS_FINALIZADO_LIST}})
        canceladas  = await _safe_count(col, {**query, "status": {"$in": STATUS_CANCELADO_LIST}})

        vol_agg = await _safe_aggregate(col, [
            {"$match": query},
            {"$group": {"_id": None, "s": {"$sum": "$bet_value"}}},
        ], 1)
        volume = vol_agg[0]["s"] if vol_agg else 0.0

        # ── DEBUG: inspeciona canceladas no período ───────────────────────────
        try:
            docs_canceladas = await col.find(
                {**query, "status": {"$in": STATUS_CANCELADO_LIST}}
            ).to_list(length=50)

            logger.info(
                f"[Analytics][DEBUG] Canceladas | período: {cfg['embed_label']} | "
                f"since: {since.strftime('%d/%m/%Y %H:%M')} UTC | "
                f"encontradas: {len(docs_canceladas)}"
            )

            if docs_canceladas:
                for i, doc in enumerate(docs_canceladas, 1):
                    logger.info(
                        f"[Analytics][DEBUG] Cancelada #{i} | "
                        f"_id: {doc.get('_id')} | "
                        f"status: {doc.get('status')} | "
                        f"created_at: {doc.get('created_at')} | "
                        f"cancelled_at: {doc.get('cancelled_at')} | "
                        f"bet_value: {doc.get('bet_value')} | "
                        f"cancelled_by: {doc.get('cancelled_by')} | "
                        f"cancel_reason: {doc.get('cancel_reason')}"
                    )
            else:
                # Nenhuma no período — verifica se existem no banco sem filtro de data
                total_sem_filtro = await _safe_count(col, {"status": {"$in": STATUS_CANCELADO_LIST}})
                logger.warning(
                    f"[Analytics][DEBUG] Nenhuma cancelada no período. "
                    f"Total SEM filtro de data: {total_sem_filtro}"
                )
                if total_sem_filtro > 0:
                    exemplo = await col.find_one({"status": {"$in": STATUS_CANCELADO_LIST}})
                    logger.warning(
                        f"[Analytics][DEBUG] Exemplo de cancelada no banco | "
                        f"_id: {exemplo.get('_id')} | "
                        f"status: {exemplo.get('status')} | "
                        f"created_at: {exemplo.get('created_at')} | "
                        f"cancelled_at: {exemplo.get('cancelled_at')}"
                    )
                else:
                    # Mostra todos os status existentes para confirmar o valor real
                    todos_status = await col.distinct("status")
                    logger.warning(
                        f"[Analytics][DEBUG] Nenhuma cancelada no banco. "
                        f"Status existentes: {todos_status}"
                    )
        except Exception as e:
            logger.error(f"[Analytics][DEBUG] Erro ao inspecionar canceladas: {e}")
        # ── FIM DEBUG ─────────────────────────────────────────────────────────

        group_expr = {"$dateToString": {"format": cfg["bucket_format"], "date": "$created_at"}}
        fin_rows   = await _safe_aggregate(col, [
            {"$match": {**query, "status": {"$in": STATUS_FINALIZADO_LIST}}},
            {"$group": {"_id": group_expr, "c": {"$sum": 1}}},
            {"$sort": {"_id": 1}},
        ], cfg["points"])
        canc_rows  = await _safe_aggregate(col, [
            {"$match": {**query, "status": {"$in": STATUS_CANCELADO_LIST}}},
            {"$group": {"_id": group_expr, "c": {"$sum": 1}}},
            {"$sort": {"_id": 1}},
        ], cfg["points"])

        slot_rows = _slots(now, period_key)
        slot_keys = [s.strftime(cfg["bucket_format"]) for s in slot_rows]
        x_labels  = [s.strftime(cfg["tick_format"])   for s in slot_rows]
        y_fin     = [({r["_id"]: r["c"] for r in fin_rows}).get(k, 0)  for k in slot_keys]
        y_canc    = [({r["_id"]: r["c"] for r in canc_rows}).get(k, 0) for k in slot_keys]

        fig, ax1 = plt.subplots(figsize=(14, 6), facecolor=BG_COLOR)
        _style_axis(ax1)
        x = np.arange(len(slot_keys))
        ax1.fill_between(x, y_fin,  color=TEAL, alpha=0.2)
        ax1.fill_between(x, y_canc, color=GOLD, alpha=0.16)
        ax1.plot(x, y_fin,  color=TEAL, linewidth=2.3, marker="o", markersize=4, label="Finalizadas")
        ax1.plot(x, y_canc, color=GOLD, linewidth=2.3, marker="o", markersize=4, label="Canceladas")
        ax1.set_xticks(x)
        ax1.set_xticklabels(x_labels, rotation=40, ha="right", color=MUTED, fontsize=10)
        ax1.set_ylabel("Partidas", color=MUTED, fontsize=9)
        ax1.set_title(f"Partidas - {cfg['label']}", color=TEXT_COLOR, fontsize=11, fontweight="bold")
        ax1.legend(facecolor=PANEL_COLOR, labelcolor=TEXT_COLOR, fontsize=8, framealpha=0.7)

        max_y = max(max(y_fin, default=0), max(y_canc, default=0))
        ax1.set_ylim(bottom=0, top=max(max_y * 1.2, 1))

        _add_fig_header(
            fig,
            f"Dashboard de Partidas - {cfg['embed_label']}",
            f"Total: {total} | Finalizadas: {finalizadas} ({_pct(finalizadas, total)}) | "
            f"Canceladas: {canceladas} ({_pct(canceladas, total)}) | Volume: {_brl(volume)}",
        )

        file  = discord.File(_save_figure(fig), filename=f"matches_{period_key}.png")
        embed = discord.Embed(title=f"Partidas - {cfg['embed_label']}", color=THEME)
        embed.add_field(name="Total",       value=f"`{total}`",                                    inline=True)
        embed.add_field(name="Finalizadas", value=f"`{finalizadas}` ({_pct(finalizadas, total)})", inline=True)
        embed.add_field(name="Canceladas",  value=f"`{canceladas}` ({_pct(canceladas, total)})",   inline=True)
        embed.add_field(name="Volume",      value=f"**{_brl(volume)}**",                           inline=False)
        embed.set_image(url=f"attachment://matches_{period_key}.png")
        embed.set_footer(text=f"Atualizado {now.strftime('%d/%m/%Y %H:%M')} UTC | matplotlib [matches_dashboard]")
        return embed, file

    async def _matches(self, guild: discord.Guild):
        period_key  = "daily"
        embed, file = await self._render_matches_dashboard(period_key)
        view        = MatchesDashboardView(self, period_key=period_key)
        await self._post_dashboard(guild, "dashboard-partidas", "matches_dashboard", embed, file, view)

    # ── Dashboard: Mediadores ─────────────────────────────────────────────────

    async def _render_mediators_dashboard(self, period_key: str = "monthly") -> tuple[discord.Embed, discord.File]:
        cfg       = MATCH_PERIODS[period_key]
        matches   = db.get_collection("matches")
        mediators = db.get_collection("mediators")
        now       = utcnow()
        since     = now - cfg["delta"]

        ranking = await _safe_aggregate(matches, [
            {"$match": {"created_at": {"$gte": since}, "mediator_id": {"$ne": None}}},
            {"$group": {
                "_id":   "$mediator_id",
                "total": {"$sum": 1},
                "fin":   {"$sum": {"$cond": [{"$in": ["$status", STATUS_FINALIZADO_LIST]}, 1, 0]}},
                "canc":  {"$sum": {"$cond": [{"$in": ["$status", STATUS_CANCELADO_LIST]},  1, 0]}},
                "vol":   {"$sum": "$bet_value"},
            }},
            {"$sort": {"fin": -1}},
            {"$limit": AnalyticsConfig.TOP_MEDIATORS},
        ], AnalyticsConfig.TOP_MEDIATORS)

        names, totals, fins, volumes, lines = [], [], [], [], []
        medals = ["🥇", "🥈", "🥉"]

        for i, row in enumerate(ranking):
            mediator = await mediators.find_one({"discord_id": str(row["_id"])}) if row["_id"] else None
            name = mediator.get("username", str(row["_id"])) if mediator else str(row["_id"])
            names.append(name)
            totals.append(row["total"])
            fins.append(row["fin"])
            volumes.append(row.get("vol", 0))
            icon = medals[i] if i < 3 else f"`{i + 1}.`"
            lines.append(
                f"{icon} **{name}** - `{row['total']}` | fin:`{row['fin']}` canc:`{row['canc']}` | {_brl(row.get('vol', 0))}"
            )

        ativos    = await _safe_count(mediators, {"in_queue": True, "is_active": True})
        total_mes = await _safe_count(matches,   {"created_at": {"$gte": since}})

        fig, ax1 = plt.subplots(figsize=(14, 6), facecolor=BG_COLOR)
        _style_axis(ax1)
        if ranking:
            positions = [f"{i + 1}." for i in range(len(totals))]
            y    = np.arange(len(positions))
            bars = ax1.barh(y, totals, color=GOLD, alpha=0.9)
            ax1.set_yticks(y)
            ax1.set_yticklabels(positions, color=TEXT_COLOR, fontsize=10)
            ax1.set_xlabel("Partidas mediadas", color=MUTED, fontsize=9)
            ax1.invert_yaxis()
            for bar, val in zip(bars, totals):
                ax1.text(bar.get_width() + 0.1, bar.get_y() + bar.get_height() / 2,
                         str(val), va="center", color=TEXT_COLOR, fontsize=9)
            ax1.set_title("Top mediadores por partidas", color=TEXT_COLOR, fontsize=11, fontweight="bold")
        else:
            ax1.text(0.5, 0.5, "Nenhum dado", color=MUTED, ha="center", va="center", transform=ax1.transAxes)

        _add_fig_header(fig, f"Mediadores - {cfg['embed_label']}",
                        f"Na fila agora: {ativos} | Partidas no periodo: {total_mes}")

        file  = discord.File(_save_figure(fig), filename="mediators_dashboard.png")
        embed = discord.Embed(title=f"Mediadores - {cfg['embed_label']}", color=THEME2)
        embed.description = "\n".join(lines) if lines else "Nenhuma partida mediada ainda."
        embed.add_field(name="Na fila agora",   value=f"`{ativos}`",                                     inline=True)
        embed.add_field(name="Partidas",        value=f"`{total_mes}`",                                  inline=True)
        embed.add_field(name="Top mediador",    value=f"`{names[0] if names else 'N/A'}`",               inline=True)
        embed.add_field(name="Valor total",     value=f"**{_brl(volumes[0]) if volumes else _brl(0)}**", inline=True)
        embed.set_image(url="attachment://mediators_dashboard.png")
        embed.set_footer(text=f"Atualizado {now.strftime('%d/%m/%Y %H:%M')} UTC | matplotlib [mediators_dashboard]")
        return embed, file

    async def _mediators(self, guild: discord.Guild):
        period_key  = "monthly"
        embed, file = await self._render_mediators_dashboard(period_key)
        view        = MediatorsDashboardView(self, period_key=period_key)
        await self._post_dashboard(guild, "dashboard-mediadores", "mediators_dashboard", embed, file, view)

    # ── Dashboard: Jogadores ──────────────────────────────────────────────────

    async def _render_players_dashboard(
        self,
        period_key: str = "weekly",
        highlight_id: Optional[int] = None,
    ) -> discord.Embed:
        cfg   = MATCH_PERIODS[period_key]
        col   = db.get_collection("matches")
        now   = utcnow()
        since = now - cfg["delta"]

        top = await _safe_aggregate(col, [
            {"$match": {"created_at": {"$gte": since}}},
            {"$unwind": "$player_ids"},
            {"$group": {
                "_id":   "$player_ids",
                "total": {"$sum": 1},
                "wins":  {"$sum": {"$cond": [{"$eq": ["$winner_id", "$player_ids"]}, 1, 0]}},
                "vol":   {"$sum": "$bet_value"},
            }},
            {"$sort": {"wins": -1}},
            {"$limit": AnalyticsConfig.TOP_PLAYERS},
        ], AnalyticsConfig.TOP_PLAYERS)

        totals         = [row["total"] for row in top]
        wrs            = [(row["wins"] / row["total"] * 100) if row["total"] else 0 for row in top]
        total_partidas = sum(totals)
        top_wr         = max(wrs) if wrs else 0

        medals = ["🥇", "🥈", "🥉"]
        lines  = []
        for i, row in enumerate(top):
            pos    = medals[i] if i < 3 else f"`{i + 1}º`"
            wins   = row["wins"]
            tot    = row["total"]
            wr     = _pct(wins, tot)
            vol    = _brl(row.get("vol", 0))
            marker = " ◀" if highlight_id and str(row["_id"]) == str(highlight_id) else ""
            lines.append(
                f"{pos} <@{row['_id']}> ｜ **{wins}** vitórias ｜ `{wr}` ｜ {vol}{marker}"
            )

        embed = discord.Embed(
            title       = f"🏆 Ranking de Vitórias — {cfg['embed_label']}",
            description = "\n".join(lines) if lines else "Nenhuma partida disputada ainda.",
            color       = THEME,
        )
        embed.add_field(name="Jogadores ativos", value=f"`{len(top)}`",       inline=True)
        embed.add_field(name="Partidas",         value=f"`{total_partidas}`", inline=True)
        embed.add_field(name="Melhor WR",        value=f"`{top_wr:.1f}%`",   inline=True)
        embed.add_field(
            name  = "Maior volume",
            value = f"**{_brl(max((row.get('vol', 0) for row in top), default=0))}**",
            inline=True,
        )
        footer_suffix = " · Só você pode ver isso" if highlight_id else ""
        embed.set_footer(text=f"Atualizado {now.strftime('%d/%m/%Y %H:%M')} UTC | [players_dashboard]{footer_suffix}")
        return embed

    async def _players(self, guild: discord.Guild):
        period_key = "weekly"
        embed      = await self._render_players_dashboard(period_key)
        view       = PlayersDashboardView(self, period_key=period_key)

        ch = discord.utils.get(guild.text_channels, name="ranking")
        if not ch:
            return
        try:
            target = None
            async for message in ch.history(limit=50):
                if message.author != guild.me or not message.embeds:
                    continue
                footer = message.embeds[0].footer.text if message.embeds[0].footer else ""
                if "[players_dashboard]" in footer:
                    target = message
                    break
            if target:
                await target.edit(embed=embed, attachments=[], view=view)
            else:
                await ch.send(embed=embed, view=view)
        except discord.Forbidden:
            logger.warning("[Analytics] Sem permissao em #ranking")
        except Exception as e:
            logger.warning(f"[Analytics] #ranking: {e}")

    # ── Dashboard: Suporte ────────────────────────────────────────────────────

    async def _render_support_dashboard(self, period_key: str = "monthly") -> tuple[discord.Embed, discord.File]:
        cfg     = MATCH_PERIODS[period_key]
        tickets = db.get_collection("tickets")
        now     = utcnow()
        since   = now - cfg["delta"]

        total    = await _safe_count(tickets, {"created_at": {"$gte": since}})
        abertos  = await _safe_count(tickets, {"status": "aberto"})
        atend    = await _safe_count(tickets, {"status": "pendente"})
        fechados = await _safe_count(tickets, {
            "created_at": {"$gte": since},
            "status": {"$in": ["resolvido", "fechado"]},
        })

        cats = await _safe_aggregate(tickets, [
            {"$match": {"created_at": {"$gte": since}}},
            {"$group": {"_id": "$categoria", "c": {"$sum": 1}}},
            {"$sort": {"c": -1}},
            {"$limit": AnalyticsConfig.TOP_CATEGORIES},
        ], AnalyticsConfig.TOP_CATEGORIES)

        agents = await _safe_aggregate(tickets, [
            {"$match": {"created_at": {"$gte": since}, "atendente_id": {"$ne": None}}},
            {"$group": {
                "_id":   "$atendente_id",
                "res":   {"$sum": {"$cond": [{"$in": ["$status", ["resolvido", "fechado"]]}, 1, 0]}},
                "total": {"$sum": 1},
            }},
            {"$sort": {"res": -1}},
            {"$limit": AnalyticsConfig.TOP_AGENTS},
        ], AnalyticsConfig.TOP_AGENTS)

        fig = plt.figure(figsize=(14, 12), facecolor=BG_COLOR)
        gs  = gridspec.GridSpec(2, 1, hspace=0.55, height_ratios=[1, 1.1], top=0.91, bottom=0.06)

        fig.text(0.02, 0.97, f"Suporte — {cfg['embed_label']}",
                 color=TEXT_COLOR, fontsize=13, fontweight="bold", va="top")
        fig.text(0.02, 0.93,
                 f"Tickets no periodo: {total}  |  Abertos: {abertos}  |  "
                 f"Em atendimento: {atend}  |  Resolvidos: {fechados} ({_pct(fechados, total)})",
                 color=MUTED, fontsize=8.5, va="top")

        ax1 = fig.add_subplot(gs[0])
        _style_axis(ax1)
        ax1.bar(["Abertos", "Em atendimento", "Resolvidos"], [abertos, atend, fechados],
                color=[RED, ORANGE, TEAL], alpha=0.88)
        ax1.set_ylabel("Tickets", color=MUTED, fontsize=9)
        ax1.set_title("Situacao atual", color=TEXT_COLOR, fontsize=11, fontweight="bold")
        ax1.set_ylim(bottom=0, top=max(max(abertos, atend, fechados) * 1.2, 1))

        fig.text(0.02, 0.485, "Distribuicao por Categoria",
                 color=TEXT_COLOR, fontsize=11, fontweight="bold", va="top")
        if cats:
            fig.text(0.02, 0.455,
                     "  |  ".join(f"{row['_id'] or '?'}: {row['c']}" for row in cats),
                     color=MUTED, fontsize=8.5, va="top")

        ax2 = fig.add_subplot(gs[1])
        ax2.set_facecolor(PANEL_COLOR)
        if cats:
            cat_labels = [row["_id"] or "?" for row in cats]
            sizes      = [row["c"]          for row in cats]
            palette    = [GOLD, BLUE, TEAL, ORANGE, PURPLE, RED][: len(cats)]
            wedges, _, _ = ax2.pie(
                sizes, labels=None, colors=palette, autopct="%1.1f%%",
                startangle=90, pctdistance=0.75,
                wedgeprops={"width": 0.48, "edgecolor": BG_COLOR, "linewidth": 1.5},
                textprops={"color": TEXT_COLOR, "fontsize": 9},
            )
            ax2.legend(wedges, [f"{lbl} ({sz})" for lbl, sz in zip(cat_labels, sizes)],
                       loc="lower center", bbox_to_anchor=(0.5, -0.15), ncol=3,
                       facecolor=PANEL_COLOR, labelcolor=TEXT_COLOR, fontsize=8, framealpha=0.7)
            ax2.set_title("Tickets por Categoria", color=TEXT_COLOR, fontsize=11, fontweight="bold")
        else:
            ax2.text(0.5, 0.5, "Sem categorias", color=MUTED,
                     ha="center", va="center", transform=ax2.transAxes)
            ax2.set_xticks([])
            ax2.set_yticks([])

        file  = discord.File(_save_figure(fig), filename="support_dashboard.png")
        embed = discord.Embed(title=f"Suporte - {cfg['embed_label']}", color=THEME2)
        embed.add_field(name="Tickets no periodo", value=f"`{total}`",                              inline=True)
        embed.add_field(name="Em aberto agora",    value=f"`{abertos}`",                            inline=True)
        embed.add_field(name="Em atendimento",     value=f"`{atend}`",                              inline=True)
        embed.add_field(name="Resolvidos",         value=f"`{fechados}` ({_pct(fechados, total)})", inline=True)
        if agents:
            embed.add_field(
                name="Por atendente",
                value="\n".join(f"<@{row['_id']}> - `{row['res']}` res / `{row['total']}` total" for row in agents),
                inline=False,
            )
        if cats:
            embed.add_field(
                name="Por categoria",
                value="\n".join(f"`{row['_id'] or '?'}` - {row['c']}" for row in cats),
                inline=False,
            )
        embed.set_image(url="attachment://support_dashboard.png")
        embed.set_footer(text=f"Atualizado {now.strftime('%d/%m/%Y %H:%M')} UTC | matplotlib [support_dashboard]")
        return embed, file

    async def _support(self, guild: discord.Guild):
        period_key  = "monthly"
        embed, file = await self._render_support_dashboard(period_key)
        view        = SupportDashboardView(self, period_key=period_key)
        await self._post_dashboard(guild, "dashboard-suporte", "support_dashboard", embed, file, view)

    # ── Dashboard: Servidor ───────────────────────────────────────────────────

    async def _render_server_dashboard(self, guild: discord.Guild, period_key: str = "monthly") -> tuple[discord.Embed, discord.File]:
        cfg   = MATCH_PERIODS[period_key]
        users = db.get_collection("users")
        now   = utcnow()

        try:
            await db.client.admin.command("ping")
            db_status = "Conectado"
        except Exception:
            db_status = "Erro"

        total_db = await _safe_count(users, {})
        accepted = await _safe_count(users, {"rules_accepted": True})
        blocked  = await _safe_count(users, {"spam_blocked": True})
        novos_7  = await _safe_count(users, {"joined_at": {"$gte": now - timedelta(days=7)}})
        novos_30 = await _safe_count(users, {"joined_at": {"$gte": now - timedelta(days=30)}})

        labels = ["Discord", "Cadastrados", "Onboarding", "Bloqueados", "Novos 7d", "Novos 30d"]
        values = [guild.member_count or 0, total_db, accepted, blocked, novos_7, novos_30]

        fig, ax = plt.subplots(figsize=(12, 5.8), facecolor=BG_COLOR)
        _style_axis(ax)
        ax.bar(labels, values, color=[BLUE, GOLD, TEAL, RED, ORANGE, PURPLE], alpha=0.88)
        ax.set_ylabel("Quantidade", color=MUTED, fontsize=9)
        ax.set_title("Status geral do servidor", color=TEXT_COLOR, fontsize=11, fontweight="bold")
        ax.set_ylim(bottom=0, top=max(max(values) * 1.2, 1))
        for tick in ax.get_xticklabels():
            tick.set_color(MUTED)
            tick.set_fontsize(10)
        _add_fig_header(fig, f"Servidor - {cfg['embed_label']}")

        file  = discord.File(_save_figure(fig), filename="server_dashboard.png")
        embed = discord.Embed(title="Status do Servidor", color=GREEN)
        embed.add_field(name="Bot",             value="Online",                                     inline=True)
        embed.add_field(name="Banco",           value=db_status,                                    inline=True)
        embed.add_field(name="Membros Discord", value=f"`{guild.member_count}`",                    inline=True)
        embed.add_field(name="Cadastrados",     value=f"`{total_db}`",                              inline=True)
        embed.add_field(name="Onboarding OK",   value=f"`{accepted}` ({_pct(accepted, total_db)})", inline=True)
        embed.add_field(name="Bloqueados",      value=f"`{blocked}`",                               inline=True)
        embed.add_field(name="Novos (7 dias)",  value=f"`{novos_7}`",                               inline=True)
        embed.add_field(name="Novos (30 dias)", value=f"`{novos_30}`",                              inline=True)
        embed.set_image(url="attachment://server_dashboard.png")
        embed.set_footer(text=f"Atualizado {now.strftime('%d/%m/%Y %H:%M')} UTC | matplotlib [server_dashboard]")
        return embed, file

    async def _server(self, guild: discord.Guild):
        period_key  = "monthly"
        embed, file = await self._render_server_dashboard(guild, period_key)
        view        = ServerDashboardView(self, guild, period_key=period_key)
        await self._post_dashboard(guild, "status-bot", "server_dashboard", embed, file, view)

    # ── Dashboard: Influencers ────────────────────────────────────────────────

    async def _render_influencers_dashboard(self, guild: discord.Guild, period_key: str = "monthly") -> tuple[discord.Embed, discord.File]:
        cfg         = MATCH_PERIODS[period_key]
        now         = utcnow()
        since       = now - cfg["delta"]
        influencers = db.get_collection("influencers")
        invites     = db.get_collection("invite_joins")
        matches     = db.get_collection("matches")

        infs = await influencers.find({"is_active": True}).to_list(None)
        rows = []
        for inf in infs:
            members = await invites.find(
                {"guild_id": str(guild.id), "invite_code": inf.get("invite_code")}
            ).to_list(None)
            member_ids  = [m["member_id"] for m in members]
            match_count = (
                await _safe_count(matches, {
                    "player_ids": {"$in": member_ids},
                    "created_at": {"$gte": since},
                })
                if member_ids else 0
            )
            rows.append({
                "username":   inf.get("username", "?"),
                "members":    len(member_ids),
                "matches":    match_count,
                "commission": len(member_ids) * inf.get("commission_per_member", 2.0),
            })

        rows.sort(key=lambda r: r["members"], reverse=True)
        top_rows     = rows[:AnalyticsConfig.TOP_INFLUENCERS]
        labels       = [f"{i + 1}." for i in range(len(top_rows))]
        members_list = [r["members"] for r in top_rows]
        match_totals = [r["matches"] for r in top_rows]

        fig, ax1 = plt.subplots(figsize=(13, 6), facecolor=BG_COLOR)
        _style_axis(ax1)

        if rows:
            x = np.arange(len(labels))
            ax1.bar(x, members_list, color=PURPLE, alpha=0.9)
            ax1.set_xticks(x)
            ax1.set_xticklabels(labels, color=MUTED, fontsize=10)
            ax1.set_ylabel("Membros indicados", color=MUTED, fontsize=9)
            ax1.set_xlabel("Posicao no ranking", color=MUTED, fontsize=9)
            ax1.set_title("Influencers por membros indicados", color=TEXT_COLOR, fontsize=11, fontweight="bold")
            ax1.set_ylim(bottom=0, top=max(max(members_list, default=0) * 1.2, 1))

            ax2 = ax1.twinx()
            ax2.tick_params(colors=MUTED, labelsize=8)
            for spine in ax2.spines.values():
                spine.set_color(GRID_COLOR)
            ax2.set_ylabel("Partidas", color=MUTED, fontsize=8)

            if len(x) >= 4 and max(match_totals) > 0:
                x_smooth = np.linspace(x.min(), x.max(), 400)
                spline   = make_interp_spline(x, match_totals, k=3)
                y_smooth = np.clip(spline(x_smooth), 0, None)
                ax2.plot(x_smooth, y_smooth, color=GOLD, linewidth=2.2)
            else:
                ax2.plot(x, match_totals, color=GOLD, marker="o", linewidth=2.2)

            ax2.scatter(x, match_totals, color=TEXT_COLOR, s=30, zorder=5)
            for i, v in enumerate(match_totals):
                if v > 0:
                    ax2.annotate(
                        str(v), xy=(i, v), xytext=(0, 8),
                        textcoords="offset points", ha="center",
                        color=TEXT_COLOR, fontsize=8, fontweight="bold",
                    )
        else:
            ax1.text(0.5, 0.5, "Nenhum influencer ativo", color=MUTED,
                     ha="center", va="center", transform=ax1.transAxes)

        total_comm    = sum(r["commission"] for r in rows)
        total_members = sum(r["members"]    for r in rows)
        total_matches = sum(r["matches"]    for r in rows)

        _add_fig_header(fig, f"Influencers - {cfg['embed_label']}")

        medals = ["🥇", "🥈", "🥉"]
        lines  = []
        for i, row in enumerate(top_rows):
            icon = medals[i] if i < 3 else f"`{i + 1}.`"
            lines.append(
                f"{icon} **{row['username']}** - `{row['members']}` membros | `{row['matches']}` partidas | {_brl(row['commission'])}"
            )

        file  = discord.File(_save_figure(fig), filename="influencers_dashboard.png")
        embed = discord.Embed(title=f"Influencers - {cfg['embed_label']}", color=THEME)
        embed.description = "\n".join(lines) if lines else "Nenhum influencer ativo."
        embed.add_field(name="Influencers",              value=f"`{len(rows)}`",          inline=True)
        embed.add_field(name="Membros",                  value=f"`{total_members}`",      inline=True)
        embed.add_field(name="Partidas",                 value=f"`{total_matches}`",      inline=True)
        embed.add_field(name="Comissao total acumulada", value=f"**{_brl(total_comm)}**", inline=False)
        embed.set_image(url="attachment://influencers_dashboard.png")
        embed.set_footer(text=f"Atualizado {now.strftime('%d/%m/%Y %H:%M')} UTC | matplotlib [influencers_dashboard]")
        return embed, file

    async def _influencers(self, guild: discord.Guild):
        period_key  = "monthly"
        embed, file = await self._render_influencers_dashboard(guild, period_key)
        view        = InfluencersDashboardView(self, guild, period_key=period_key)
        await self._post_dashboard(guild, "dashboard-influencers", "influencers_dashboard", embed, file, view)

    # ── Dashboard: Apostas ────────────────────────────────────────────────────

    async def _render_apostas_dashboard(self, period_key: str = "daily") -> tuple[discord.Embed, discord.File]:
        cfg       = MATCH_PERIODS[period_key]
        col       = db.get_collection("matches")
        mediators = db.get_collection("mediators")
        now       = utcnow()
        since     = now - cfg["delta"]
        query     = {"created_at": {"$gte": since}}

        total      = await _safe_count(col, query)
        ativas     = await _safe_count(col, {"status": {"$in": [
            "aguardando_pagamento", "aguardando_inicio", "em_andamento",
            "aguardando_partida", "partida_iniciada", "aguardando_premio",
        ]}})
        aguardando = await _safe_count(col, {"status": {"$in": [
            "aguardando_pagamento", "aguardando_partida",
        ]}})

        val_agg = await _safe_aggregate(col, [
            {"$match": query},
            {"$group": {"_id": "$bet_value", "c": {"$sum": 1}}},
            {"$sort": {"c": -1}},
            {"$limit": 1},
        ], 1)
        top_val       = val_agg[0]["_id"] if val_agg else 0
        top_val_count = val_agg[0]["c"]   if val_agg else 0

        med_agg = await _safe_aggregate(col, [
            {"$match": {**query, "mediator_id": {"$ne": None}}},
            {"$group": {"_id": "$mediator_id", "c": {"$sum": 1}}},
            {"$sort": {"c": -1}},
            {"$limit": 1},
        ], 1)
        if not med_agg:
            med_agg = await _safe_aggregate(col, [
                {"$match": {"mediator_id": {"$ne": None}}},
                {"$group": {"_id": "$mediator_id", "c": {"$sum": 1}}},
                {"$sort": {"c": -1}},
                {"$limit": 1},
            ], 1)
        top_med_id    = med_agg[0]["_id"] if med_agg else None
        top_med_count = med_agg[0]["c"]   if med_agg else 0

        group_expr = {"$dateToString": {"format": cfg["bucket_format"], "date": "$created_at"}}
        rows = await _safe_aggregate(col, [
            {"$match": query},
            {"$group": {"_id": group_expr, "c": {"$sum": 1}}},
            {"$sort": {"_id": 1}},
        ], cfg["points"])

        slot_rows = _slots(now, period_key)
        slot_keys = [s.strftime(cfg["bucket_format"]) for s in slot_rows]
        x_labels  = [s.strftime(cfg["tick_format"])   for s in slot_rows]
        row_map   = {r["_id"]: r["c"] for r in rows}
        y_vals    = [row_map.get(k, 0) for k in slot_keys]

        fig, ax = plt.subplots(figsize=(14, 6), facecolor=BG_COLOR)
        _style_axis(ax)
        x = np.arange(len(slot_keys))

        ax.fill_between(x, y_vals, color=BLUE, alpha=0.18)
        ax.plot(x, y_vals, color=BLUE, linewidth=2.5, marker="o", markersize=5, zorder=4)

        for i, v in enumerate(y_vals):
            if v > 0:
                ax.annotate(
                    str(v), xy=(i, v), xytext=(0, 8),
                    textcoords="offset points", ha="center",
                    color=TEXT_COLOR, fontsize=8, fontweight="bold",
                )

        max_y = max(y_vals) if max(y_vals) > 0 else 10
        ax.set_yticks(np.linspace(0, max_y, 6))
        ax.set_yticklabels([f"{int(v)} Apostas" for v in np.linspace(0, max_y, 6)], color=MUTED, fontsize=8)
        ax.set_xticks(x)
        ax.set_xticklabels(x_labels, rotation=40, ha="right", color=MUTED, fontsize=9)
        ax.set_title("Apostas", color=TEXT_COLOR, fontsize=11, fontweight="bold")
        ax.set_ylim(bottom=0)

        _add_fig_header(fig, f"Apostas no Servidor - {cfg['embed_label']}")

        file  = discord.File(_save_figure(fig), filename="apostas_dashboard.png")
        embed = discord.Embed(title="Apostas no Servidor", color=THEME2)
        embed.description = "Veja as analytics do servidor."
        embed.add_field(
            name="Apostas Totais",
            value=f"Total: {total} apostas\nAtivas: {ativas} apostas\nAguardando: {aguardando} apostas",
            inline=False,
        )
        embed.add_field(
            name="Valor Mais Jogado",
            value=f"{_brl(top_val)} | {top_val_count} vezes" if top_val else "N/A",
            inline=False,
        )
        med_line = f"\nMediador Mais Frequente: <@{top_med_id}> com **{top_med_count}** apostas" if top_med_id else ""
        embed.add_field(
            name=f"Apostas — {cfg['embed_label']}",
            value=f"{total} Apostas{med_line}",
            inline=False,
        )
        embed.set_image(url="attachment://apostas_dashboard.png")
        embed.set_footer(text=f"Atualizado {now.strftime('%d/%m/%Y %H:%M')} UTC | matplotlib [apostas_dashboard]")
        return embed, file

    async def _apostas(self, guild: discord.Guild):
        period_key  = "daily"
        embed, file = await self._render_apostas_dashboard(period_key)
        view        = ApostasDashboardView(self, period_key=period_key)
        await self._post_dashboard(guild, "dashboard-apostas", "apostas_dashboard", embed, file, view)

    # ── Dashboard: Membros Join/Leave ─────────────────────────────────────────

    async def _render_membros_mov_dashboard(self, guild: discord.Guild, period_key: str = "monthly") -> tuple[discord.Embed, discord.File]:
        cfg   = MATCH_PERIODS[period_key]
        users = db.get_collection("users")
        now   = utcnow()
        since = now - cfg["delta"]

        joins_hoje  = await _safe_count(users, {"joined_at": {"$gte": now - timedelta(hours=24)}})
        joins_7d    = await _safe_count(users, {"joined_at": {"$gte": now - timedelta(days=7)}})
        joins_30d   = await _safe_count(users, {"joined_at": {"$gte": now - timedelta(days=30)}})
        leaves_hoje = await _safe_count(users, {"left_at":   {"$gte": now - timedelta(hours=24)}})
        leaves_7d   = await _safe_count(users, {"left_at":   {"$gte": now - timedelta(days=7)}})
        leaves_30d  = await _safe_count(users, {"left_at":   {"$gte": now - timedelta(days=30)}})

        net_hoje = joins_hoje - leaves_hoje
        net_7d   = joins_7d   - leaves_7d
        net_30d  = joins_30d  - leaves_30d

        group_expr = {"$dateToString": {"format": cfg["bucket_format"], "date": "$joined_at"}}
        join_rows  = await _safe_aggregate(users, [
            {"$match": {"joined_at": {"$gte": since, "$ne": None}}},
            {"$group": {"_id": group_expr, "c": {"$sum": 1}}},
            {"$sort": {"_id": 1}},
        ], cfg["points"])
        leave_rows = await _safe_aggregate(users, [
            {"$match": {"left_at": {"$gte": since, "$ne": None}}},
            {"$group": {
                "_id": {"$dateToString": {"format": cfg["bucket_format"], "date": "$left_at"}},
                "c": {"$sum": 1},
            }},
            {"$sort": {"_id": 1}},
        ], cfg["points"])

        slot_rows = _slots(now, period_key)
        slot_keys = [s.strftime(cfg["bucket_format"]) for s in slot_rows]
        x_labels  = [s.strftime(cfg["tick_format"])   for s in slot_rows]
        y_joins   = [({r["_id"]: r["c"] for r in join_rows}).get(k, 0)  for k in slot_keys]
        y_leaves  = [({r["_id"]: r["c"] for r in leave_rows}).get(k, 0) for k in slot_keys]

        fig, ax = plt.subplots(figsize=(14, 6), facecolor=BG_COLOR)
        _style_axis(ax)
        x = np.arange(len(slot_keys))

        _plot_smooth_line(ax, x, y_joins,  TEAL, label="Entradas")
        _plot_smooth_line(ax, x, y_leaves, RED,  label="Saidas")

        ax.set_xticks(x)
        ax.set_xticklabels(x_labels, rotation=40, ha="right", color=MUTED, fontsize=9)
        ax.set_ylabel("Membros", color=MUTED, fontsize=9)
        ax.set_title("Member Joins and Leaves History", color=TEXT_COLOR, fontsize=11, fontweight="bold")
        ax.legend(facecolor=PANEL_COLOR, labelcolor=TEXT_COLOR, fontsize=8, framealpha=0.7)
        ax.set_ylim(bottom=0, top=max(max(max(y_joins, default=0), max(y_leaves, default=0)) * 1.2, 1))

        sign = lambda n: f"+{n}" if n >= 0 else str(n)
        _add_fig_header(
            fig,
            "Join and Leave Members Server Stats",
            f"Hoje: {sign(net_hoje)} (+{joins_hoje}, -{leaves_hoje})  |  "
            f"7 dias: {sign(net_7d)} (+{joins_7d}, -{leaves_7d})  |  "
            f"30 dias: {sign(net_30d)} (+{joins_30d}, -{leaves_30d})",
        )

        file  = discord.File(_save_figure(fig), filename="membros_mov_dashboard.png")
        embed = discord.Embed(title="Join and Leave Members Server Stats", color=THEME)
        embed.add_field(name="Hoje",          value=f"`{sign(net_hoje)}` (+{joins_hoje}, -{leaves_hoje})", inline=True)
        embed.add_field(name="Ultimos 7d",    value=f"`{sign(net_7d)}` (+{joins_7d}, -{leaves_7d})",       inline=True)
        embed.add_field(name="Ultimos 30d",   value=f"`{sign(net_30d)}` (+{joins_30d}, -{leaves_30d})",    inline=True)
        embed.add_field(name="Total Discord", value=f"`{guild.member_count}`",                             inline=True)
        embed.set_image(url="attachment://membros_mov_dashboard.png")
        embed.set_footer(text=f"Atualizado {now.strftime('%d/%m/%Y %H:%M')} UTC | matplotlib [membros_mov_dashboard]")
        return embed, file

    async def _membros_mov(self, guild: discord.Guild):
        period_key  = "monthly"
        embed, file = await self._render_membros_mov_dashboard(guild, period_key)
        view        = MembrosMovDashboardView(self, period_key=period_key)
        await self._post_dashboard(guild, "dashboard-entradas", "membros_mov_dashboard", embed, file, view)


analytics_service = AnalyticsService()
