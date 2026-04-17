"""
analytics_service_matplotlib_completo.py - Dashboards completos com matplotlib.
"""
from __future__ import annotations

import io
from datetime import timedelta
from typing import Awaitable, Callable, Optional

import discord
from discord.ext import tasks
import matplotlib

matplotlib.use("Agg")
import matplotlib.gridspec as gridspec
import matplotlib.pyplot as plt
import numpy as np

from config.database import db
from utils.datetime_utils import utcnow
from utils.logger import logger

THEME = 0xFFD54F
THEME2 = 0xFFA726
GREEN = 0x2ECC71

STATUS_FINALIZADO = "aguardando_premio"
STATUS_CANCELADO = "cancelado"

BG_COLOR = "#161925"
PANEL_COLOR = "#1f2333"
GRID_COLOR = "#31374d"
TEXT_COLOR = "#E8EAED"
MUTED = "#98A2B3"
GOLD = "#FFD54F"
ORANGE = "#FFA726"
TEAL = "#2ECC71"
RED = "#FF6B6B"
BLUE = "#4FC3F7"
PURPLE = "#8E7CFF"

MATCH_PERIODS = {
    "daily": {
        "label": "Diario",
        "embed_label": "Ultimas 24 horas",
        "delta": timedelta(hours=24),
        "bucket_format": "%Y-%m-%d %H:00",
        "tick_format": "%Hh",
        "step": timedelta(hours=1),
        "points": 24,
    },
    "weekly": {
        "label": "Semanal",
        "embed_label": "Ultimos 7 dias",
        "delta": timedelta(days=7),
        "bucket_format": "%Y-%m-%d",
        "tick_format": "%d/%m",
        "step": timedelta(days=1),
        "points": 7,
    },
    "monthly": {
        "label": "Mensal",
        "embed_label": "Ultimos 30 dias",
        "delta": timedelta(days=30),
        "bucket_format": "%Y-%m-%d",
        "tick_format": "%d/%m",
        "step": timedelta(days=1),
        "points": 30,
    },
}


def _pct(a, b) -> str:
    return f"{a / b * 100:.1f}%" if b else "0%"


def _brl(v: float) -> str:
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _save_figure(fig) -> io.BytesIO:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=135, bbox_inches="tight", facecolor=BG_COLOR)
    plt.close(fig)
    buf.seek(0)
    return buf


def _style_axis(ax):
    ax.set_facecolor(PANEL_COLOR)
    for spine in ax.spines.values():
        spine.set_color(GRID_COLOR)
    ax.tick_params(colors=MUTED, labelsize=8)
    ax.grid(color=GRID_COLOR, linestyle="--", linewidth=0.6, alpha=0.55)
    ax.set_axisbelow(True)


def _slots(now, period_key: str):
    cfg = MATCH_PERIODS[period_key]
    since = now - cfg["delta"]
    if cfg["step"] == timedelta(hours=1):
        base = since.replace(minute=0, second=0, microsecond=0)
    else:
        base = since.replace(hour=0, minute=0, second=0, microsecond=0)
    return [base + (cfg["step"] * i) for i in range(cfg["points"] + 1)]


class RefreshDashboardView(discord.ui.View):
    def __init__(
        self,
        dashboard_key: str,
        render_fn: Callable[[], Awaitable[tuple[discord.Embed, discord.File]]],
    ):
        super().__init__(timeout=None)
        self.dashboard_key = dashboard_key
        self.render_fn = render_fn

        button = discord.ui.Button(
            label="Atualizar",
            style=discord.ButtonStyle.success,
            custom_id=f"refresh_{dashboard_key}",
        )
        button.callback = self._refresh_callback
        self.add_item(button)

    async def _refresh_callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        embed, file = await self.render_fn()
        await interaction.edit_original_response(embed=embed, attachments=[file], view=self)


class MatchesDashboardView(discord.ui.View):
    def __init__(self, service: "AnalyticsService", period_key: str = "daily"):
        super().__init__(timeout=None)
        self.service = service
        self.period_key = period_key
        self.btn_daily._period_key = "daily"
        self.btn_weekly._period_key = "weekly"
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

    @discord.ui.button(label="Hoje", style=discord.ButtonStyle.primary, custom_id="matches_daily")
    async def btn_daily(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._update_period(interaction, "daily")

    @discord.ui.button(label="Semanal", style=discord.ButtonStyle.secondary, custom_id="matches_weekly")
    async def btn_weekly(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._update_period(interaction, "weekly")

    @discord.ui.button(label="Mensal", style=discord.ButtonStyle.secondary, custom_id="matches_monthly")
    async def btn_monthly(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._update_period(interaction, "monthly")

    @discord.ui.button(label="Atualizar", style=discord.ButtonStyle.success, custom_id="matches_refresh")
    async def btn_refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._update_period(interaction, self.period_key)


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

    async def publish_all_now(self, guild: discord.Guild):
        """Forca o envio/atualizacao imediata de todas as dashboards.

        Use este metodo no comando !setupcanais logo apos criar os canais.
        """
        await self.update_all(guild)

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
            logger.warning(f"[Analytics] Sem permissao em #{ch_name}")
        except Exception as e:
            logger.warning(f"[Analytics] #{ch_name}: {e}")

    async def _render_matches_dashboard(self, period_key: str) -> tuple[discord.Embed, discord.File]:
        cfg = MATCH_PERIODS[period_key]
        col = db.get_collection("matches")
        now = utcnow()
        since = now - cfg["delta"]
        query = {"created_at": {"$gte": since}}

        total = await col.count_documents(query)
        finalizadas = await col.count_documents({**query, "status": STATUS_FINALIZADO})
        canceladas = await col.count_documents({**query, "status": STATUS_CANCELADO})

        vol_agg = await col.aggregate(
            [
                {"$match": query},
                {"$group": {"_id": None, "s": {"$sum": "$bet_value"}}},
            ]
        ).to_list(1)
        volume = vol_agg[0]["s"] if vol_agg else 0.0

        modos = await col.aggregate(
            [
                {"$match": query},
                {"$group": {"_id": "$channel_name", "c": {"$sum": 1}}},
                {"$sort": {"c": -1}},
                {"$limit": 5},
            ]
        ).to_list(5)

        group_expr = {
            "$dateToString": {"format": cfg["bucket_format"], "date": "$created_at"}
        }
        fin_rows = await col.aggregate(
            [
                {"$match": {**query, "status": STATUS_FINALIZADO}},
                {"$group": {"_id": group_expr, "c": {"$sum": 1}}},
                {"$sort": {"_id": 1}},
            ]
        ).to_list(cfg["points"] + 1)
        canc_rows = await col.aggregate(
            [
                {"$match": {**query, "status": STATUS_CANCELADO}},
                {"$group": {"_id": group_expr, "c": {"$sum": 1}}},
                {"$sort": {"_id": 1}},
            ]
        ).to_list(cfg["points"] + 1)

        slot_rows = _slots(now, period_key)
        slot_keys = [slot.strftime(cfg["bucket_format"]) for slot in slot_rows]
        x_labels = [slot.strftime(cfg["tick_format"]) for slot in slot_rows]
        fin_map = {row["_id"]: row["c"] for row in fin_rows}
        canc_map = {row["_id"]: row["c"] for row in canc_rows}
        y_fin = [fin_map.get(key, 0) for key in slot_keys]
        y_canc = [canc_map.get(key, 0) for key in slot_keys]

        fig, ax1 = plt.subplots(figsize=(14, 6), facecolor=BG_COLOR)
        _style_axis(ax1)
        x = np.arange(len(slot_keys))
        ax1.fill_between(x, y_fin, color=TEAL, alpha=0.2)
        ax1.fill_between(x, y_canc, color=RED, alpha=0.16)
        ax1.plot(x, y_fin, color=TEAL, linewidth=2.3, marker="o", markersize=4)
        ax1.plot(x, y_canc, color=RED, linewidth=2.3, marker="o", markersize=4)
        ax1.set_xticks(x)
        ax1.set_xticklabels(x_labels, rotation=40, ha="right", color=MUTED, fontsize=7)
        ax1.set_title(f"Partidas - {cfg['label']}", color=TEXT_COLOR, fontsize=11, fontweight="bold")

        fig.text(
            0.02,
            0.98,
            f"Dashboard de Partidas - {cfg['embed_label']}",
            color=TEXT_COLOR,
            fontsize=13,
            fontweight="bold",
            va="top",
        )
        fig.text(
            0.02,
            0.92,
            f"Total: {total} | Finalizadas: {finalizadas} ({_pct(finalizadas, total)}) | "
            f"Canceladas: {canceladas} ({_pct(canceladas, total)}) | Volume: {_brl(volume)}",
            color=MUTED,
            fontsize=8.5,
            va="top",
        )
        file = discord.File(_save_figure(fig), filename=f"matches_{period_key}.png")
        embed = discord.Embed(title=f"Partidas - {cfg['embed_label']}", color=THEME)
        embed.add_field(name="Total", value=f"`{total}`", inline=True)
        embed.add_field(
            name="Finalizadas",
            value=f"`{finalizadas}` ({_pct(finalizadas, total)})",
            inline=True,
        )
        embed.add_field(
            name="Canceladas",
            value=f"`{canceladas}` ({_pct(canceladas, total)})",
            inline=True,
        )
        embed.add_field(name="Volume", value=f"**{_brl(volume)}**", inline=False)
        embed.set_image(url=f"attachment://matches_{period_key}.png")
        embed.set_footer(
            text=f"Atualizado {now.strftime('%d/%m/%Y %H:%M')} UTC | matplotlib [matches_dashboard]"
        )
        return embed, file

    async def _matches(self, guild: discord.Guild):
        period_key = "daily"
        embed, file = await self._render_matches_dashboard(period_key)
        view = MatchesDashboardView(self, period_key=period_key)
        await self._post_dashboard(
            guild,
            "dashboard-partidas",
            "matches_dashboard",
            embed,
            file,
            view,
        )

    async def _render_mediators_dashboard(self) -> tuple[discord.Embed, discord.File]:
        matches = db.get_collection("matches")
        mediators = db.get_collection("mediators")
        now = utcnow()
        since = now - timedelta(days=30)

        ranking = await matches.aggregate(
            [
                {"$match": {"created_at": {"$gte": since}, "mediator_id": {"$ne": None}}},
                {
                    "$group": {
                        "_id": "$mediator_id",
                        "total": {"$sum": 1},
                        "fin": {"$sum": {"$cond": [{"$eq": ["$status", STATUS_FINALIZADO]}, 1, 0]}},
                        "canc": {"$sum": {"$cond": [{"$eq": ["$status", STATUS_CANCELADO]}, 1, 0]}},
                        "vol": {"$sum": "$bet_value"},
                    }
                },
                {"$sort": {"total": -1}},
                {"$limit": 8},
            ]
        ).to_list(8)

        names = []
        totals = []
        volumes = []
        lines = []
        medals = ["🥇", "🥈", "🥉"]

        for i, row in enumerate(ranking):
            mediator = await mediators.find_one({"discord_id": str(row["_id"])}) if row["_id"] else None
            name = mediator.get("username", str(row["_id"])) if mediator else str(row["_id"])
            names.append(name[:18])
            totals.append(row["total"])
            volumes.append(row.get("vol", 0))
            icon = medals[i] if i < 3 else f"`{i + 1}.`"
            lines.append(
                f"{icon} **{name}** - `{row['total']}` | fin:`{row['fin']}` canc:`{row['canc']}` | {_brl(row.get('vol', 0))}"
            )

        ativos = await mediators.count_documents({"in_queue": True, "is_active": True})
        total_mes = await matches.count_documents({"created_at": {"$gte": since}})

        fig, ax1 = plt.subplots(figsize=(14, 6), facecolor=BG_COLOR)
        _style_axis(ax1)

        if ranking:
            y = np.arange(len(names))
            ax1.barh(y, totals, color=GOLD, alpha=0.9)
            ax1.set_yticks(y)
            ax1.set_yticklabels(names, color=TEXT_COLOR, fontsize=8)
            ax1.invert_yaxis()
            ax1.set_title("Top mediadores por partidas", color=TEXT_COLOR, fontsize=11, fontweight="bold")
        else:
            ax1.text(0.5, 0.5, "Nenhum dado", color=MUTED, ha="center", va="center", transform=ax1.transAxes)

        fig.text(0.02, 0.98, "Mediadores - Ultimos 30 dias", color=TEXT_COLOR, fontsize=13, fontweight="bold", va="top")
        fig.text(0.02, 0.92, f"Na fila agora: {ativos} | Partidas no mes: {total_mes}", color=MUTED, fontsize=8.5, va="top")
        file = discord.File(_save_figure(fig), filename="mediators_30d.png")
        embed = discord.Embed(title="Mediadores - Ultimos 30 dias", color=THEME2)
        embed.description = "\n".join(lines) if lines else "Nenhuma partida mediada ainda."
        embed.add_field(name="Na fila agora", value=f"`{ativos}`", inline=True)
        embed.add_field(name="Partidas no mes", value=f"`{total_mes}`", inline=True)
        embed.add_field(name="Top mediador", value=f"`{totals[0] if totals else 0}`", inline=True)
        embed.add_field(
            name="Valor total",
            value=f"**{_brl(volumes[0]) if volumes else _brl(0)}**",
            inline=True,
        )
        embed.set_image(url="attachment://mediators_30d.png")
        embed.set_footer(text=f"Atualizado {now.strftime('%d/%m/%Y %H:%M')} UTC | matplotlib [mediators_30d]")
        return embed, file

    async def _mediators(self, guild: discord.Guild):
        embed, file = await self._render_mediators_dashboard()
        view = RefreshDashboardView("mediators_30d", self._render_mediators_dashboard)
        await self._post_dashboard(guild, "dashboard-mediadores", "mediators_30d", embed, file, view)

    async def _render_players_dashboard(self) -> tuple[discord.Embed, discord.File]:
        col = db.get_collection("matches")
        now = utcnow()
        since = now - timedelta(days=30)

        top = await col.aggregate(
            [
                {"$match": {"created_at": {"$gte": since}}},
                {"$unwind": "$player_ids"},
                {
                    "$group": {
                        "_id": "$player_ids",
                        "total": {"$sum": 1},
                        "wins": {"$sum": {"$cond": [{"$eq": ["$winner_id", "$player_ids"]}, 1, 0]}},
                        "vol": {"$sum": "$bet_value"},
                    }
                },
                {"$sort": {"total": -1}},
                {"$limit": 10},
            ]
        ).to_list(10)

        labels = [f"@{str(row['_id'])[:8]}" for row in top]
        totals = [row["total"] for row in top]
        wrs = [(row["wins"] / row["total"] * 100) if row["total"] else 0 for row in top]

        fig, ax1 = plt.subplots(figsize=(13, 6), facecolor=BG_COLOR)
        _style_axis(ax1)
        if top:
            x = np.arange(len(labels))
            ax1.bar(x, totals, color=GOLD, alpha=0.88)
            ax1.set_xticks(x)
            ax1.set_xticklabels(labels, rotation=35, ha="right", color=MUTED, fontsize=7)
            ax1.set_title("Top jogadores por partidas", color=TEXT_COLOR, fontsize=11, fontweight="bold")
            ax2 = ax1.twinx()
            ax2.plot(x, wrs, color=TEAL, marker="o", linewidth=2)
            ax2.tick_params(colors=MUTED, labelsize=8)
            for spine in ax2.spines.values():
                spine.set_color(GRID_COLOR)
            ax2.set_ylim(0, max(100, max(wrs) + 10 if wrs else 100))
            ax2.set_ylabel("Win rate (%)", color=MUTED, fontsize=8)
        else:
            ax1.text(0.5, 0.5, "Nenhuma partida disputada", color=MUTED, ha="center", va="center", transform=ax1.transAxes)

        fig.text(0.02, 0.98, "Top Jogadores - Ultimos 30 dias", color=TEXT_COLOR, fontsize=13, fontweight="bold", va="top")
        total_partidas = sum(totals)
        top_wr = max(wrs) if wrs else 0
        medals = ["🥇", "🥈", "🥉"]
        lines = []
        for i, row in enumerate(top):
            icon = medals[i] if i < 3 else f"`{i + 1}.`"
            lines.append(
                f"{icon} <@{row['_id']}> - `{row['total']}` partidas | WR:`{_pct(row['wins'], row['total'])}` | {_brl(row.get('vol', 0))}"
            )

        file = discord.File(_save_figure(fig), filename="players_30d.png")
        embed = discord.Embed(title="Top Jogadores - Ultimos 30 dias", color=THEME)
        embed.description = "\n".join(lines) if lines else "Nenhuma partida disputada ainda."
        embed.add_field(name="Jogadores ativos (30d)", value=f"`{len(top)}`", inline=True)
        embed.add_field(name="Partidas", value=f"`{total_partidas}`", inline=True)
        embed.add_field(name="Melhor WR", value=f"`{top_wr:.1f}%`", inline=True)
        embed.add_field(
            name="Maior volume",
            value=f"**{_brl(max((row.get('vol', 0) for row in top), default=0))}**",
            inline=True,
        )
        embed.set_image(url="attachment://players_30d.png")
        embed.set_footer(text=f"Atualizado {now.strftime('%d/%m/%Y %H:%M')} UTC | matplotlib [players_30d]")
        return embed, file

    async def _players(self, guild: discord.Guild):
        embed, file = await self._render_players_dashboard()
        view = RefreshDashboardView("players_30d", self._render_players_dashboard)
        await self._post_dashboard(guild, "ranking", "players_30d", embed, file, view)

    async def _render_support_dashboard(self) -> tuple[discord.Embed, discord.File]:
        tickets = db.get_collection("tickets")
        now = utcnow()
        since = now - timedelta(days=30)

        total = await tickets.count_documents({"created_at": {"$gte": since}})
        abertos = await tickets.count_documents({"status": "aberto"})
        atend = await tickets.count_documents({"status": "pendente"})
        fechados = await tickets.count_documents(
            {"created_at": {"$gte": since}, "status": {"$in": ["resolvido", "fechado"]}}
        )

        cats = await tickets.aggregate(
            [
                {"$match": {"created_at": {"$gte": since}}},
                {"$group": {"_id": "$categoria", "c": {"$sum": 1}}},
                {"$sort": {"c": -1}},
                {"$limit": 6},
            ]
        ).to_list(6)

        agents = await tickets.aggregate(
            [
                {"$match": {"created_at": {"$gte": since}, "atendente_id": {"$ne": None}}},
                {
                    "$group": {
                        "_id": "$atendente_id",
                        "res": {"$sum": {"$cond": [{"$in": ["$status", ["resolvido", "fechado"]]}, 1, 0]}},
                        "total": {"$sum": 1},
                    }
                },
                {"$sort": {"res": -1}},
                {"$limit": 5},
            ]
        ).to_list(5)

        fig = plt.figure(figsize=(14, 6), facecolor=BG_COLOR)
        gs = gridspec.GridSpec(1, 2, width_ratios=[1.5, 1], wspace=0.24)

        ax1 = fig.add_subplot(gs[0])
        _style_axis(ax1)

        status_labels = ["Abertos", "Em atendimento", "Resolvidos"]
        status_values = [abertos, atend, fechados]
        ax1.bar(status_labels, status_values, color=[RED, ORANGE, TEAL], alpha=0.88)
        ax1.set_title("Situacao atual", color=TEXT_COLOR, fontsize=11, fontweight="bold")

        ax2 = fig.add_subplot(gs[1])
        ax2.set_facecolor(PANEL_COLOR)
        if cats:
            labels = [row["_id"] or "?" for row in cats]
            sizes = [row["c"] for row in cats]
            ax2.pie(
                sizes,
                labels=labels,
                colors=[GOLD, BLUE, TEAL, ORANGE, PURPLE, RED][: len(cats)],
                autopct="%1.1f%%",
                startangle=90,
                textprops={"color": TEXT_COLOR, "fontsize": 8},
            )
            ax2.set_title("Categorias", color=TEXT_COLOR, fontsize=11, fontweight="bold")
        else:
            ax2.text(0.5, 0.5, "Sem categorias", color=MUTED, ha="center", va="center", transform=ax2.transAxes)
            ax2.set_xticks([])
            ax2.set_yticks([])

        fig.text(0.02, 0.98, "Suporte - Ultimos 30 dias", color=TEXT_COLOR, fontsize=13, fontweight="bold", va="top")
        fig.text(0.02, 0.92, f"Tickets no periodo: {total}", color=MUTED, fontsize=8.5, va="top")
        file = discord.File(_save_figure(fig), filename="support_30d.png")
        embed = discord.Embed(title="Suporte - Ultimos 30 dias", color=THEME2)
        embed.add_field(name="Abertos no periodo", value=f"`{total}`", inline=True)
        embed.add_field(name="Em aberto agora", value=f"`{abertos}`", inline=True)
        embed.add_field(name="Em atendimento", value=f"`{atend}`", inline=True)
        embed.add_field(name="Resolvidos", value=f"`{fechados}` ({_pct(fechados, total)})", inline=True)
        if cats:
            embed.add_field(
                name="Por categoria",
                value="\n".join(f"`{row['_id'] or '?'}` - {row['c']}" for row in cats),
                inline=True,
            )
        if agents:
            embed.add_field(
                name="Por atendente",
                value="\n".join(f"<@{row['_id']}> - `{row['res']}` res / `{row['total']}` total" for row in agents),
                inline=False,
            )
        embed.set_image(url="attachment://support_30d.png")
        embed.set_footer(text=f"Atualizado {now.strftime('%d/%m/%Y %H:%M')} UTC | matplotlib [support_30d]")
        return embed, file

    async def _support(self, guild: discord.Guild):
        embed, file = await self._render_support_dashboard()
        view = RefreshDashboardView("support_30d", self._render_support_dashboard)
        await self._post_dashboard(guild, "dashboard-suporte", "support_30d", embed, file, view)

    async def _render_server_dashboard(self, guild: discord.Guild) -> tuple[discord.Embed, discord.File]:
        users = db.get_collection("users")
        now = utcnow()

        try:
            await db.client.admin.command("ping")
            db_status = "Conectado"
        except Exception:
            db_status = "Erro"

        total_db = await users.count_documents({})
        accepted = await users.count_documents({"rules_accepted": True})
        blocked = await users.count_documents({"spam_blocked": True})
        novos_7 = await users.count_documents({"joined_at": {"$gte": now - timedelta(days=7)}})
        novos_30 = await users.count_documents({"joined_at": {"$gte": now - timedelta(days=30)}})

        labels = ["Discord", "DB", "Onboarding", "Bloqueados", "Novos 7d", "Novos 30d"]
        values = [guild.member_count or 0, total_db, accepted, blocked, novos_7, novos_30]

        fig, ax = plt.subplots(figsize=(12, 5.8), facecolor=BG_COLOR)
        _style_axis(ax)
        ax.bar(labels, values, color=[BLUE, GOLD, TEAL, RED, ORANGE, PURPLE], alpha=0.88)
        ax.set_title("Status geral do servidor", color=TEXT_COLOR, fontsize=11, fontweight="bold")
        for tick in ax.get_xticklabels():
            tick.set_color(MUTED)
            tick.set_fontsize(8)
        file = discord.File(_save_figure(fig), filename="server_status.png")
        embed = discord.Embed(title="Status do Servidor", color=GREEN)
        embed.add_field(name="Bot", value="Online", inline=True)
        embed.add_field(name="Banco", value=db_status, inline=True)
        embed.add_field(name="Membros Discord", value=f"`{guild.member_count}`", inline=True)
        embed.add_field(name="Cadastrados", value=f"`{total_db}`", inline=True)
        embed.add_field(name="Onboarding OK", value=f"`{accepted}` ({_pct(accepted, total_db)})", inline=True)
        embed.add_field(name="Bloqueados", value=f"`{blocked}`", inline=True)
        embed.add_field(name="Novos (7 dias)", value=f"`{novos_7}`", inline=True)
        embed.add_field(name="Novos (30 dias)", value=f"`{novos_30}`", inline=True)
        embed.set_image(url="attachment://server_status.png")
        embed.set_footer(text=f"Atualizado {now.strftime('%d/%m/%Y %H:%M')} UTC | matplotlib [server_status]")
        return embed, file

    async def _server(self, guild: discord.Guild):
        embed, file = await self._render_server_dashboard(guild)
        view = RefreshDashboardView(
            "server_status",
            lambda guild=guild: self._render_server_dashboard(guild),
        )
        await self._post_dashboard(guild, "status-bot", "server_status", embed, file, view)

    async def _render_influencers_dashboard(self, guild: discord.Guild) -> tuple[discord.Embed, discord.File]:
        now = utcnow()
        influencers = db.get_collection("influencers")
        invites = db.get_collection("invite_joins")
        matches = db.get_collection("matches")

        infs = await influencers.find({"is_active": True}).to_list(None)
        rows = []
        for inf in infs:
            members = await invites.find(
                {"guild_id": str(guild.id), "invite_code": inf.get("invite_code")}
            ).to_list(None)
            member_ids = [member["member_id"] for member in members]
            match_count = (
                await matches.count_documents({"player_ids": {"$in": member_ids}, "status": STATUS_FINALIZADO})
                if member_ids
                else 0
            )
            rows.append(
                {
                    "username": inf.get("username", "?"),
                    "members": len(member_ids),
                    "matches": match_count,
                    "commission": len(member_ids) * inf.get("commission_per_member", 2.0),
                }
            )

        rows.sort(key=lambda row: row["members"], reverse=True)
        labels = [row["username"][:14] for row in rows[:8]]
        members = [row["members"] for row in rows[:8]]
        match_totals = [row["matches"] for row in rows[:8]]

        fig, ax1 = plt.subplots(figsize=(13, 6), facecolor=BG_COLOR)
        _style_axis(ax1)
        if rows:
            x = np.arange(len(labels))
            ax1.bar(x, members, color=PURPLE, alpha=0.9)
            ax1.set_xticks(x)
            ax1.set_xticklabels(labels, rotation=35, ha="right", color=MUTED, fontsize=7)
            ax1.set_title("Influencers por membros indicados", color=TEXT_COLOR, fontsize=11, fontweight="bold")
            ax2 = ax1.twinx()
            ax2.plot(x, match_totals, color=GOLD, marker="o", linewidth=2.2)
            ax2.tick_params(colors=MUTED, labelsize=8)
            for spine in ax2.spines.values():
                spine.set_color(GRID_COLOR)
            ax2.set_ylabel("Partidas", color=MUTED, fontsize=8)
        else:
            ax1.text(0.5, 0.5, "Nenhum influencer ativo", color=MUTED, ha="center", va="center", transform=ax1.transAxes)

        total_comm = sum(row["commission"] for row in rows)
        total_members = sum(row["members"] for row in rows)
        total_matches = sum(row["matches"] for row in rows)
        medals = ["🥇", "🥈", "🥉"]
        lines = []
        for i, row in enumerate(rows[:10]):
            icon = medals[i] if i < 3 else f"`{i + 1}.`"
            lines.append(
                f"{icon} **{row['username']}** - `{row['members']}` membros | `{row['matches']}` partidas | {_brl(row['commission'])}"
            )
        file = discord.File(_save_figure(fig), filename="influencers.png")
        embed = discord.Embed(title="Influencers", color=THEME)
        embed.description = "\n".join(lines) if lines else "Nenhum influencer ativo."
        embed.add_field(name="Influencers", value=f"`{len(rows)}`", inline=True)
        embed.add_field(name="Membros", value=f"`{total_members}`", inline=True)
        embed.add_field(name="Partidas", value=f"`{total_matches}`", inline=True)
        embed.add_field(name="Comissao total acumulada", value=f"**{_brl(total_comm)}**", inline=False)
        embed.set_image(url="attachment://influencers.png")
        embed.set_footer(text=f"Atualizado {now.strftime('%d/%m/%Y %H:%M')} UTC | matplotlib [influencers]")
        return embed, file

    async def _influencers(self, guild: discord.Guild):
        embed, file = await self._render_influencers_dashboard(guild)
        view = RefreshDashboardView(
            "influencers",
            lambda guild=guild: self._render_influencers_dashboard(guild),
        )
        await self._post_dashboard(guild, "dashboard-influencers", "influencers", embed, file, view)


analytics_service = AnalyticsService()
