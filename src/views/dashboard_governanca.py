"""
dashboard_governanca.py
Dashboard de Governança & Auditoria: Tickets · Usuários · Segurança
Gera imagem PNG → envia como embed Discord via discord.py + motor (MongoDB async)

Collections usadas: tickets, users
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
ACCENT    = "#9b59b6"   # roxo auditoria
GREEN     = "#57f287"
YELLOW    = "#fee75c"
RED       = "#ed4245"
CYAN      = "#00b0f4"
BLUE      = "#5865f2"
ORANGE    = "#e67e22"
MUTED     = "#6b7280"
WHITE     = "#e8eaf0"

STATUS_COLORS = {
    "aberto":    YELLOW,
    "pendente":  CYAN,
    "resolvido": GREEN,
    "fechado":   MUTED,
}

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
        "font.family":       ["DejaVu Sans", "Segoe UI Emoji", "Noto Color Emoji"],
        "font.size":         9,
        "axes.spines.top":   False,
        "axes.spines.right": False,
    })

# ─── Helpers ─────────────────────────────────────────────────────────────────

def _clear_ax(ax, facecolor=CARD):
    ax.set_facecolor(facecolor)
    for sp in ax.spines.values():
        sp.set_visible(False)
    ax.set_xticks([])
    ax.set_yticks([])


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
            fontsize=21, fontweight="bold", color=color, zorder=1)
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
    gf    = {"guild_id": guild_id} if guild_id else {}

    # ── Tickets ───────────────────────────────────────────────────
    tk_total    = await db.get_collection("tickets").count_documents(gf)
    tk_aberto   = await db.get_collection("tickets").count_documents({**gf, "status": "aberto"})
    tk_pendente = await db.get_collection("tickets").count_documents({**gf, "status": "pendente"})
    tk_resolvido= await db.get_collection("tickets").count_documents({**gf, "status": "resolvido"})
    tk_fechado  = await db.get_collection("tickets").count_documents({**gf, "status": "fechado"})
    tk_period   = await db.get_collection("tickets").count_documents(
        {**gf, "created_at": {"$gte": since}})

    # tickets por categoria
    cat_pipeline = [
        {"$match": gf},
        {"$group": {"_id": "$categoria", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]
    cat_raw = await db.get_collection("tickets").aggregate(cat_pipeline).to_list(20)

    # tickets por dia
    tk_day_pipeline = [
        {"$match": {**gf, "created_at": {"$gte": since}}},
        {"$group": {
            "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}},
            "count": {"$sum": 1}
        }},
        {"$sort": {"_id": 1}},
    ]
    tk_day_raw  = await db.get_collection("tickets").aggregate(tk_day_pipeline).to_list(periodo_dias + 2)
    tk_day_data = {d["_id"]: d["count"] for d in tk_day_raw}

    # tempo médio de resolução (resolved_at - created_at) em horas
    resolve_pipeline = [
        {"$match": {**gf, "resolved_at": {"$ne": None}, "created_at": {"$ne": None}}},
        {"$project": {
            "duration_h": {
                "$divide": [
                    {"$subtract": ["$resolved_at", "$created_at"]},
                    3_600_000  # ms → horas
                ]
            }
        }},
        {"$group": {"_id": None, "avg_h": {"$avg": "$duration_h"}}},
    ]
    resolve_raw = await db.get_collection("tickets").aggregate(resolve_pipeline).to_list(1)
    avg_resolve_h = resolve_raw[0]["avg_h"] if resolve_raw else None

    # top atendentes
    atend_pipeline = [
        {"$match": {**gf, "atendente_id": {"$ne": None}}},
        {"$group": {"_id": "$atendente_id", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 5},
    ]
    atend_raw = await db.get_collection("tickets").aggregate(atend_pipeline).to_list(5)

    # ── Usuários ──────────────────────────────────────────────────
    u_total       = await db.get_collection("users").count_documents({})
    u_active      = await db.get_collection("users").count_documents({"is_active": True})
    u_rules_ok    = await db.get_collection("users").count_documents({"has_accepted_rules": True})
    u_captcha_ok  = await db.get_collection("users").count_documents({"captcha_status": "aprovado"})
    u_spam        = await db.get_collection("users").count_documents({"spam_blocked": True})
    u_new_period  = await db.get_collection("users").count_documents({"created_at": {"$gte": since}})

    # onboarding status
    ob_pipeline = [
        {"$group": {"_id": "$onboarding_result", "count": {"$sum": 1}}},
    ]
    ob_raw = await db.get_collection("users").aggregate(ob_pipeline).to_list(10)
    ob_data = {o["_id"]: o["count"] for o in ob_raw}

    # novos usuários por dia
    u_day_pipeline = [
        {"$match": {"created_at": {"$gte": since}}},
        {"$group": {
            "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}},
            "count": {"$sum": 1}
        }},
        {"$sort": {"_id": 1}},
    ]
    u_day_raw  = await db.get_collection("users").aggregate(u_day_pipeline).to_list(periodo_dias + 2)
    u_day_data = {d["_id"]: d["count"] for d in u_day_raw}

    return {
        "tk_total": tk_total, "tk_aberto": tk_aberto,
        "tk_pendente": tk_pendente, "tk_resolvido": tk_resolvido,
        "tk_fechado": tk_fechado, "tk_period": tk_period,
        "cat_raw": cat_raw, "tk_day_data": tk_day_data,
        "avg_resolve_h": avg_resolve_h, "atend_raw": atend_raw,
        "u_total": u_total, "u_active": u_active,
        "u_rules_ok": u_rules_ok, "u_captcha_ok": u_captcha_ok,
        "u_spam": u_spam, "u_new_period": u_new_period,
        "ob_data": ob_data, "u_day_data": u_day_data,
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
    fig.text(0.04, 0.96, "[GOV] Dashboard Governanca 🛡️  Dashboard Governança & Auditoria Auditoria",
             fontsize=16, fontweight="bold", color=WHITE, va="top")
    fig.text(0.04, 0.91, f"Atualizado em {now_str}  •  últimos {data['periodo_dias']} dias",
             fontsize=8.5, color=MUTED, va="top")
    fig.add_artist(plt.Line2D(
        [0.04, 0.97], [0.895, 0.895],
        transform=fig.transFigure,
        color=ACCENT, linewidth=1.2, alpha=0.5
    ))

    # ══ LINHA 0 — KPIs Tickets ════════════════════════════════════
    resolve_str = (f"{data['avg_resolve_h']:.1f}h"
                   if data["avg_resolve_h"] else "N/A")
    kpi_defs = [
        (data["tk_total"],    "Tickets Total",          ACCENT),
        (data["tk_aberto"],   "Abertos",                YELLOW),
        (data["tk_pendente"], "Pendentes",               CYAN),
        (data["tk_resolvido"],"Resolvidos",              GREEN),
        (data["tk_fechado"],  "Fechados",                MUTED),
        (resolve_str,         "Tempo Médio Resolução",  ORANGE),
    ]
    for col, (val, lbl, clr) in enumerate(kpi_defs):
        ax = fig.add_subplot(gs[0, col])
        _kpi(ax, val, lbl, color=clr)

    # ══ LINHA 1 — Tickets por dia + Donut categorias ══════════════
    period  = data["periodo_dias"]
    dates   = [(data["now"] - timedelta(days=period - 1 - i)).strftime("%Y-%m-%d")
               for i in range(period)]
    dlabels = [(data["now"] - timedelta(days=period - 1 - i)).strftime("%d/%m")
               for i in range(period)]
    tk_vals = [data["tk_day_data"].get(d, 0) for d in dates]

    ax_tk = fig.add_subplot(gs[1, :4])
    _clear_ax(ax_tk, CARD)
    for sp in ax_tk.spines.values():
        sp.set_visible(False)
    x = np.arange(period)
    ax_tk.fill_between(x, tk_vals, alpha=0.18, color=ACCENT)
    ax_tk.plot(x, tk_vals, color=ACCENT, linewidth=2,
               marker="o", markersize=4, markerfacecolor=WHITE)
    ax_tk.set_xticks(x)
    ax_tk.set_xticklabels(dlabels, fontsize=7.5, color=MUTED)
    ax_tk.set_yticks([])
    ax_tk.tick_params(left=False, bottom=False)
    ax_tk.set_title("Tickets Abertos por Dia", fontsize=9,
                    color=MUTED, loc="left", pad=6)
    ax_tk.grid(axis="y", alpha=0.3)

    # Donut categorias
    ax_cat = fig.add_subplot(gs[1, 4:])
    _clear_ax(ax_cat, CARD)
    cats = data["cat_raw"]
    if cats:
        c_labels = [c["_id"] or "Outro" for c in cats]
        c_values = [c["count"] for c in cats]
        c_colors = [ACCENT, CYAN, YELLOW, GREEN, RED][:len(c_values)]
        wedges, _ = ax_cat.pie(
            c_values, labels=None, colors=c_colors,
            startangle=90, wedgeprops={"width": 0.55, "edgecolor": BG, "linewidth": 1.5}
        )
        ax_cat.legend(
            wedges, [f"{l} ({v})" for l, v in zip(c_labels, c_values)],
            loc="center left", bbox_to_anchor=(0.88, 0.5),
            fontsize=6.8, frameon=False, labelcolor=WHITE,
        )
    ax_cat.set_title("Tickets por Categoria", fontsize=9,
                     color=MUTED, loc="left", pad=6)

    # ══ LINHA 2 — KPIs Usuários + Onboarding donut ═══════════════
    u_kpis = [
        (data["u_total"],      "Usuários Total",     BLUE),
        (data["u_active"],     "Ativos",             GREEN),
        (data["u_rules_ok"],   "Regras Aceitas",     CYAN),
        (data["u_captcha_ok"], "Captcha Aprovado",   ACCENT),
        (data["u_spam"],       "Bloqueados Spam",    RED),
        (data["u_new_period"], f"Novos ({period}d)", YELLOW),
    ]
    for col, (val, lbl, clr) in enumerate(u_kpis):
        ax = fig.add_subplot(gs[2, col])
        _kpi(ax, val, lbl, color=clr)

    # ══ LINHA 3 — Novos usuários/dia + Top atendentes + Onboarding ══
    u_vals = [data["u_day_data"].get(d, 0) for d in dates]

    ax_u = fig.add_subplot(gs[3, :3])
    _clear_ax(ax_u, CARD)
    for sp in ax_u.spines.values():
        sp.set_visible(False)
    bars_u = ax_u.bar(x, u_vals, color=BLUE, alpha=0.8, width=0.6, edgecolor="none")
    ax_u.set_xticks(x)
    ax_u.set_xticklabels(dlabels, fontsize=7.5, color=MUTED)
    ax_u.set_yticks([])
    ax_u.tick_params(left=False, bottom=False)
    ax_u.set_title("Novos Usuários por Dia", fontsize=9,
                   color=MUTED, loc="left", pad=6)

    # Top atendentes
    ax_atend = fig.add_subplot(gs[3, 3:5])
    _clear_ax(ax_atend, CARD)
    for sp in ax_atend.spines.values():
        sp.set_visible(False)
    atends = data["atend_raw"]
    if atends:
        anames  = [str(a["_id"])[:12] for a in reversed(atends)]
        acounts = [a["count"] for a in reversed(atends)]
        ya      = np.arange(len(anames))
        abars   = ax_atend.barh(ya, acounts, color=ACCENT, height=0.5, edgecolor="none")
        abars[-1].set_color(YELLOW)
        for bar, val in zip(abars, acounts):
            ax_atend.text(
                val + max(acounts) * 0.03,
                bar.get_y() + bar.get_height() / 2,
                str(val), va="center", fontsize=7.5, color=WHITE
            )
        ax_atend.set_yticks(ya)
        ax_atend.set_yticklabels(anames, fontsize=8, color=WHITE)
        ax_atend.set_xticks([])
    else:
        ax_atend.text(0.5, 0.5, "Sem dados", ha="center", va="center",
                      color=MUTED, fontsize=9)
    ax_atend.set_title("Top Atendentes", fontsize=9,
                       color=MUTED, loc="left", pad=6)

    # Onboarding donut
    ax_ob = fig.add_subplot(gs[3, 5])
    _clear_ax(ax_ob, CARD)
    ob = data["ob_data"]
    ob_clean = {k: v for k, v in ob.items() if v > 0 and k}
    if ob_clean:
        ob_labels = list(ob_clean.keys())
        ob_values = list(ob_clean.values())
        ob_colors = [GREEN, YELLOW, RED, MUTED][:len(ob_values)]
        ax_ob.pie(
            ob_values, labels=None, colors=ob_colors,
            startangle=90,
            wedgeprops={"width": 0.55, "edgecolor": BG, "linewidth": 1.5}
        )
        ax_ob.text(0, -1.35,
                   "\n".join([f"{l}: {v}" for l, v in zip(ob_labels, ob_values)]),
                   ha="center", fontsize=6.5, color=MUTED)
    ax_ob.set_title("Onboarding", fontsize=9, color=MUTED, loc="left", pad=6)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110,
                facecolor=BG, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


# ─── Função pública ───────────────────────────────────────────────────────────

async def build_governanca_image(
    db,
    guild_id: int | None = None,
    periodo_dias: int = 7,
) -> io.BytesIO:
    data = await _fetch_data(db, guild_id=guild_id, periodo_dias=periodo_dias)
    return _render(data)


# ─── Cog Discord ─────────────────────────────────────────────────────────────

class DashboardGovernancaCog(discord.ext.commands.Cog):

    def __init__(self, bot, db):
        self.bot = bot
        self.db  = db

    @discord.app_commands.command(
        name="dashboard_governanca",
        description="Exibe o dashboard de governança, auditoria e usuários",
    )
    @discord.app_commands.describe(
        periodo="Período em dias (padrão: 7)",
        guild_id="ID do servidor (deixe vazio para todos)",
    )
    async def dashboard_governanca(
        self,
        interaction: discord.Interaction,
        periodo: int = 7,
        guild_id: str | None = None,
    ):
        await interaction.response.defer(thinking=True)
        gid = int(guild_id) if guild_id else None
        buf = await build_governanca_image(self.db, guild_id=gid,
                                           periodo_dias=periodo)
        file  = discord.File(buf, filename="dashboard_governanca.png")
        embed = discord.Embed(
            title="[GOV] Dashboard Governanca 🛡️  Dashboard Governança & Auditoria Auditoria",
            description=f"Tickets · Usuários · Segurança  •  últimos **{periodo}** dias",
            color=0x9B59B6,
            timestamp=discord.utils.utcnow(),
        )
        embed.set_image(url="attachment://dashboard_governanca.png")
        embed.set_footer(text="Atualizado agora • use /dashboard_governanca para refresh")
        await interaction.followup.send(embed=embed, file=file)


async def setup(bot):
    from motor.motor_asyncio import AsyncIOMotorClient  # type: ignore
    client = AsyncIOMotorClient(bot.mongo_uri)
    db     = client[bot.mongo_db_name]
    await bot.add_cog(DashboardGovernancaCog(bot, db))
