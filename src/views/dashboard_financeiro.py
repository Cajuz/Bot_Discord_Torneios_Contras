"""
dashboard_financeiro.py
Dashboard Financeiro: Pagamentos PIX · Volume de Apostas · Receita
Gera imagem PNG → envia como embed Discord via discord.py + motor (MongoDB async)

Collections usadas: payment_confirmations, matches
"""
from __future__ import annotations

import io
from datetime import datetime, timezone, timedelta

import discord
import discord.ext.commands
import discord.app_commands
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import numpy as np
from matplotlib.patches import FancyBboxPatch

# ─── Paleta ──────────────────────────────────────────────────────────────────
BG        = "#16181d"
CARD      = "#1e2128"
CARD2     = "#252930"
ACCENT    = "#f0b429"   # ouro financeiro
GREEN     = "#57f287"
YELLOW    = "#fee75c"
RED       = "#ed4245"
CYAN      = "#00b0f4"
BLUE      = "#5865f2"
MUTED     = "#6b7280"
WHITE     = "#e8eaf0"

def _setup_rcparams():
    plt.rcParams.update({
        "figure.facecolor":  BG,
        "axes.facecolor":    CARD,
        "axes.edgecolor":    CARD2,
        "axes.labelcolor":   WHITE,
        "text.color":        WHITE,
        "xtick.color":       MUTED,
        "ytick.color":       MUTED,
        "grid.color":        CARD2,
        "grid.linewidth":    0.6,
        "font.family":       "DejaVu Sans",
        "font.size":         9,
    })

# ─── Helpers ─────────────────────────────────────────────────────────────────

def _clear_ax(ax, facecolor=CARD):
    ax.set_facecolor(facecolor)
    for sp in ax.spines.values():
        sp.set_visible(False)
    ax.set_xticks([])
    ax.set_yticks([])


def _fmt_brl(value: float) -> str:
    if value >= 1_000_000:
        return f"R${value/1_000_000:.1f}M"
    if value >= 1_000:
        return f"R${value/1_000:.1f}K"
    return f"R${value:.0f}"


def _kpi(ax, value, label, color=ACCENT, sub=None):
    _clear_ax(ax)
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    rect = FancyBboxPatch((0.05, 0.07), 0.90, 0.88,
                          boxstyle="round,pad=0.03",
                          linewidth=1.4, edgecolor=color,
                          facecolor=CARD2, zorder=0)
    ax.add_patch(rect)
    y_val = 0.58 if sub else 0.52
    ax.text(0.5, y_val, str(value),
            ha="center", va="center",
            fontsize=19, fontweight="bold", color=color, zorder=1)
    ax.text(0.5, 0.30, label,
            ha="center", va="center",
            fontsize=8, color=MUTED, zorder=1)
    if sub:
        ax.text(0.5, 0.13, sub,
                ha="center", va="center",
                fontsize=7, color=MUTED, zorder=1)


# ─── Coleta de dados ──────────────────────────────────────────────────────────

async def _fetch_data(db, guild_id: int | None, periodo_dias: int) -> dict:
    now   = datetime.now(timezone.utc)
    since = now - timedelta(days=periodo_dias)
    mf    = {"guild_id": guild_id} if guild_id else {}

    # ── Pagamentos ────────────────────────────────────────────────
    pay_total    = await db.get_collection("payment_confirmations").count_documents({})
    pay_confirmed = await db.get_collection("payment_confirmations").count_documents(
        {"confirmation_date": {"$ne": None}})
    pay_pending  = pay_total - pay_confirmed
    pay_period   = await db.get_collection("payment_confirmations").count_documents(
        {"created_at": {"$gte": since}})

    # pagamentos confirmados por admin (top 5)
    admin_pipeline = [
        {"$match": {"confirmed_by_admin": {"$ne": None}}},
        {"$group": {"_id": "$confirmed_by_admin", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 5},
    ]
    admin_raw = await db.get_collection("payment_confirmations").aggregate(admin_pipeline).to_list(5)

    # pagamentos por dia (período)
    pay_day_pipeline = [
        {"$match": {"created_at": {"$gte": since}}},
        {"$group": {
            "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}},
            "count": {"$sum": 1}
        }},
        {"$sort": {"_id": 1}},
    ]
    pay_day_raw = await db.get_collection("payment_confirmations").aggregate(pay_day_pipeline).to_list(periodo_dias + 2)
    pay_day_data = {d["_id"]: d["count"] for d in pay_day_raw}

    # ── Apostas / Volume financeiro ───────────────────────────────
    vol_pipeline = [
        {"$match": {**mf, "bet_value": {"$ne": None}, "status": "finalizado"}},
        {"$group": {"_id": None,
                    "total": {"$sum": "$bet_value"},
                    "avg":   {"$avg": "$bet_value"},
                    "count": {"$sum": 1}}},
    ]
    vol_raw    = await db.get_collection("matches").aggregate(vol_pipeline).to_list(1)
    vol_total  = vol_raw[0]["total"] if vol_raw else 0
    vol_avg    = vol_raw[0]["avg"]   if vol_raw else 0
    vol_count  = vol_raw[0]["count"] if vol_raw else 0

    vol_period_pipeline = [
        {"$match": {**mf,
                    "bet_value": {"$ne": None},
                    "status": "finalizado",
                    "created_at": {"$gte": since}}},
        {"$group": {"_id": None, "total": {"$sum": "$bet_value"}}},
    ]
    vp_raw       = await db.get_collection("matches").aggregate(vol_period_pipeline).to_list(1)
    vol_period   = vp_raw[0]["total"] if vp_raw else 0

    # volume por faixa de aposta
    faixa_pipeline = [
        {"$match": {**mf, "bet_value": {"$ne": None}}},
        {"$bucket": {
            "groupBy": "$bet_value",
            "boundaries": [0, 10, 25, 50, 100, 250, 500, 99999],
            "default": "500+",
            "output": {"count": {"$sum": 1}, "total": {"$sum": "$bet_value"}},
        }},
    ]
    faixa_raw = await db.get_collection("matches").aggregate(faixa_pipeline).to_list(20)

    # volume por dia (período)
    vol_day_pipeline = [
        {"$match": {**mf,
                    "bet_value": {"$ne": None},
                    "created_at": {"$gte": since}}},
        {"$group": {
            "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}},
            "total": {"$sum": "$bet_value"},
        }},
        {"$sort": {"_id": 1}},
    ]
    vol_day_raw  = await db.get_collection("matches").aggregate(vol_day_pipeline).to_list(periodo_dias + 2)
    vol_day_data = {d["_id"]: d["total"] for d in vol_day_raw}

    return {
        "pay_total": pay_total, "pay_confirmed": pay_confirmed,
        "pay_pending": pay_pending, "pay_period": pay_period,
        "admin_raw": admin_raw, "pay_day_data": pay_day_data,
        "vol_total": vol_total, "vol_avg": vol_avg,
        "vol_count": vol_count, "vol_period": vol_period,
        "faixa_raw": faixa_raw, "vol_day_data": vol_day_data,
        "periodo_dias": periodo_dias, "now": now,
    }


# ─── Renderização ─────────────────────────────────────────────────────────────

def _render(data: dict) -> io.BytesIO:
    _setup_rcparams()
    fig = plt.figure(figsize=(14, 9), dpi=110)
    fig.patch.set_facecolor(BG)

    gs = gridspec.GridSpec(
        4, 6,
        figure=fig,
        hspace=0.55, wspace=0.38,
        top=0.88, bottom=0.06,
        left=0.04, right=0.97,
    )

    now_str = data["now"].strftime("%d/%m/%Y %H:%M UTC")
    fig.text(0.04, 0.96, "[FIN] Dashboard Financeiro",
             fontsize=16, fontweight="bold", color=WHITE, va="top")
    fig.text(0.04, 0.91, f"Atualizado em {now_str}  •  últimos {data['periodo_dias']} dias",
             fontsize=8.5, color=MUTED, va="top")
    fig.add_artist(plt.Line2D(
        [0.04, 0.97], [0.895, 0.895],
        transform=fig.transFigure,
        color=ACCENT, linewidth=1.2, alpha=0.5
    ))

    # ══ LINHA 0 — KPIs pagamentos ═════════════════════════════════
    kpi_defs = [
        (data["pay_total"],              "Pagamentos Total",      ACCENT),
        (data["pay_confirmed"],          "Confirmados",           GREEN),
        (data["pay_pending"],            "Pendentes",             YELLOW),
        (data["pay_period"],             f"Novos ({data['periodo_dias']}d)", BLUE),
        (_fmt_brl(data["vol_total"]),    "Volume Total",          ACCENT),
        (_fmt_brl(data["vol_period"]),   f"Volume ({data['periodo_dias']}d)", GREEN),
    ]
    for col, (val, lbl, clr) in enumerate(kpi_defs):
        ax = fig.add_subplot(gs[0, col])
        _kpi(ax, val, lbl, color=clr)

    # ══ LINHA 1 — Volume apostas por dia + Avg / Count ═══════════
    period   = data["periodo_dias"]
    dates    = [(data["now"] - timedelta(days=period - 1 - i)).strftime("%Y-%m-%d")
                for i in range(period)]
    vlabels  = [(data["now"] - timedelta(days=period - 1 - i)).strftime("%d/%m")
                for i in range(period)]
    vols     = [data["vol_day_data"].get(d, 0) for d in dates]

    ax_vol = fig.add_subplot(gs[1, :4])
    _clear_ax(ax_vol, CARD)
    for sp in ax_vol.spines.values():
        sp.set_visible(False)
    x = np.arange(period)
    ax_vol.fill_between(x, vols, alpha=0.20, color=ACCENT)
    ax_vol.plot(x, vols, color=ACCENT, linewidth=2,
                marker="o", markersize=4, markerfacecolor=WHITE)
    ax_vol.set_xticks(x)
    ax_vol.set_xticklabels(vlabels, fontsize=7.5, color=MUTED)
    ax_vol.set_yticks([])
    ax_vol.tick_params(left=False, bottom=False)
    ax_vol.set_title("Volume de Apostas por Dia (R$)", fontsize=9,
                     color=MUTED, loc="left", pad=6)
    ax_vol.grid(axis="y", alpha=0.3)

    # KPIs avg e total partidas
    avg_kpis = [
        (_fmt_brl(data["vol_avg"]), "Aposta Média",     CYAN),
        (data["vol_count"],         "Partidas Pagas",   BLUE),
    ]
    for i, (val, lbl, clr) in enumerate(avg_kpis):
        ax = fig.add_subplot(gs[1, 4 + i])
        _kpi(ax, val, lbl, color=clr)

    # ══ LINHA 2 — Pagamentos por dia + Top admins ════════════════
    p_days  = [data["pay_day_data"].get(d, 0) for d in dates]
    ax_pay  = fig.add_subplot(gs[2, :3])
    _clear_ax(ax_pay, CARD)
    for sp in ax_pay.spines.values():
        sp.set_visible(False)

    ax_pay.bar(x, p_days, color=GREEN, alpha=0.8, width=0.6, edgecolor="none")
    ax_pay.set_xticks(x)
    ax_pay.set_xticklabels(vlabels, fontsize=7.5, color=MUTED)
    ax_pay.set_yticks([])
    ax_pay.tick_params(left=False, bottom=False)
    ax_pay.set_title("Pagamentos Recebidos por Dia", fontsize=9,
                     color=MUTED, loc="left", pad=6)

    # Top admins confirmadores
    ax_admin = fig.add_subplot(gs[2, 3:])
    _clear_ax(ax_admin, CARD)
    for sp in ax_admin.spines.values():
        sp.set_visible(False)

    admins = data["admin_raw"]
    if admins:
        anames  = [a["_id"][:14] for a in reversed(admins)]
        acounts = [a["count"] for a in reversed(admins)]
        ya      = np.arange(len(anames))
        abars   = ax_admin.barh(ya, acounts, color=BLUE, height=0.5, edgecolor="none")
        abars[-1].set_color(ACCENT)
        for bar, val in zip(abars, acounts):
            ax_admin.text(val + max(acounts) * 0.02, bar.get_y() + bar.get_height() / 2,
                          str(val), va="center", fontsize=7.5, color=WHITE)
        ax_admin.set_yticks(ya)
        ax_admin.set_yticklabels(anames, fontsize=8, color=WHITE)
        ax_admin.set_xticks([])
    else:
        ax_admin.text(0.5, 0.5, "Sem dados", ha="center", va="center",
                      color=MUTED, fontsize=9)
    ax_admin.set_title("Top Admins Confirmadores", fontsize=9,
                       color=MUTED, loc="left", pad=6)

    # ══ LINHA 3 — Faixas de aposta ═══════════════════════════════
    ax_faixa = fig.add_subplot(gs[3, :4])
    _clear_ax(ax_faixa, CARD)
    for sp in ax_faixa.spines.values():
        sp.set_visible(False)

    faixas = data["faixa_raw"]
    if faixas:
        fnames = []
        fcounts = []
        ftotals = []
        for f in faixas:
            bid = f["_id"]
            if isinstance(bid, (int, float)):
                fnames.append(f"R${int(bid)}+")
            else:
                fnames.append(str(bid))
            fcounts.append(f["count"])
            ftotals.append(f.get("total", 0))

        xf   = np.arange(len(fnames))
        clrs = [ACCENT if i % 2 == 0 else BLUE for i in range(len(fnames))]
        fbars = ax_faixa.bar(xf, fcounts, color=clrs, width=0.6, edgecolor="none")
        for bar, val in zip(fbars, fcounts):
            ax_faixa.text(bar.get_x() + bar.get_width() / 2,
                          bar.get_height() + max(fcounts, default=1) * 0.03,
                          str(val), ha="center", fontsize=7.5, color=WHITE)
        ax_faixa.set_xticks(xf)
        ax_faixa.set_xticklabels(fnames, fontsize=8, color=MUTED)
        ax_faixa.set_yticks([])
        ax_faixa.set_title("Partidas por Faixa de Aposta (R$)", fontsize=9,
                           color=MUTED, loc="left", pad=6)
    else:
        ax_faixa.text(0.5, 0.5, "Sem dados de apostas",
                      ha="center", va="center", color=MUTED, fontsize=9)

    # KPIs finais
    tax_est = data["vol_total"] * 0.05  # exemplo: 5% fee estimado
    fin_kpis = [
        (_fmt_brl(tax_est), "Fee Est. (5%)", ACCENT),
        (f"{(data['pay_confirmed'] / max(data['pay_total'], 1) * 100):.0f}%",
         "Taxa Confirmação", GREEN),
    ]
    for i, (val, lbl, clr) in enumerate(fin_kpis):
        ax = fig.add_subplot(gs[3, 4 + i])
        _kpi(ax, val, lbl, color=clr)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110,
                facecolor=BG, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


# ─── Função pública ───────────────────────────────────────────────────────────

async def build_financeiro_image(
    db,
    guild_id: int | None = None,
    periodo_dias: int = 7,
) -> io.BytesIO:
    data = await _fetch_data(db, guild_id=guild_id, periodo_dias=periodo_dias)
    return _render(data)


# ─── Cog Discord ─────────────────────────────────────────────────────────────

class DashboardFinanceiroCog(discord.ext.commands.Cog):

    def __init__(self, bot, db):
        self.bot = bot
        self.db  = db

    @discord.app_commands.command(
        name="dashboard_financeiro",
        description="Exibe o dashboard financeiro de pagamentos e apostas",
    )
    @discord.app_commands.describe(
        periodo="Período em dias (padrão: 7)",
        guild_id="ID do servidor (deixe vazio para todos)",
    )
    async def dashboard_financeiro(
        self,
        interaction: discord.Interaction,
        periodo: int = 7,
        guild_id: str | None = None,
    ):
        await interaction.response.defer(thinking=True)
        gid = int(guild_id) if guild_id else None
        buf = await build_financeiro_image(self.db, guild_id=gid,
                                           periodo_dias=periodo)
        file  = discord.File(buf, filename="dashboard_financeiro.png")
        embed = discord.Embed(
            title="[FIN] Dashboard Financeiro",
            description=f"Pagamentos PIX · Volume de Apostas  •  últimos **{periodo}** dias",
            color=0xF0B429,
            timestamp=discord.utils.utcnow(),
        )
        embed.set_image(url="attachment://dashboard_financeiro.png")
        embed.set_footer(text="Atualizado agora • use /dashboard_financeiro para refresh")
        await interaction.followup.send(embed=embed, file=file)


async def setup(bot):
    from motor.motor_asyncio import AsyncIOMotorClient  # type: ignore
    client = AsyncIOMotorClient(bot.mongo_uri)
    db     = client[bot.mongo_db_name]
    await bot.add_cog(DashboardFinanceiroCog(bot, db))
