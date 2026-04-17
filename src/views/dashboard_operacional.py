"""
dashboard_operacional.py
Dashboard Operacional: Mediadores · Partidas · Filas
Gera imagem PNG → envia como embed Discord via discord.py + motor (MongoDB async)

Collections usadas: mediators, matches, match_queues
"""
from __future__ import annotations

import io
from datetime import datetime, timezone, timedelta

import discord
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import numpy as np
from matplotlib.patches import FancyBboxPatch

# ─── Paleta ──────────────────────────────────────────────────────────────────
BG        = "#16181d"
CARD      = "#1e2128"
CARD2     = "#252930"
ACCENT    = "#5865f2"
GREEN     = "#57f287"
YELLOW    = "#fee75c"
RED       = "#ed4245"
CYAN      = "#00b0f4"
PURPLE    = "#9b59b6"
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
        "axes.spines.top":   False,
        "axes.spines.right": False,
    })

# ─── Helpers visuais ─────────────────────────────────────────────────────────

def _clear_ax(ax, facecolor=CARD):
    ax.set_facecolor(facecolor)
    for sp in ax.spines.values():
        sp.set_visible(False)
    ax.set_xticks([])
    ax.set_yticks([])


def _kpi(ax, value, label, color=ACCENT, sub=None, delta=None):
    _clear_ax(ax)
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)

    rect = FancyBboxPatch((0.05, 0.07), 0.90, 0.88,
                          boxstyle="round,pad=0.03",
                          linewidth=1.4, edgecolor=color,
                          facecolor=CARD2, zorder=0)
    ax.add_patch(rect)

    # valor grande
    y_val = 0.60 if (sub or delta) else 0.52
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
    if delta is not None:
        sign = "▲" if delta >= 0 else "▼"
        col  = GREEN if delta >= 0 else RED
        ax.text(0.5, 0.82, f"{sign} {abs(delta)}%",
                ha="center", va="center",
                fontsize=7.5, color=col, zorder=1)


def _section_title(fig, text, x, y, color=ACCENT):
    fig.text(x, y, text, fontsize=10, fontweight="bold",
             color=color, va="bottom")


# ─── Coleta de dados (async) ──────────────────────────────────────────────────

async def _fetch_data(db, guild_id: int | None = None,
                      periodo_dias: int = 7) -> dict:
    """Agrega dados das 3 collections."""
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=periodo_dias)

    match_filter = {}
    if guild_id:
        match_filter["guild_id"] = guild_id

    # ── Mediadores ────────────────────────────────────────────────
    med_filter = {**({"guild_id": guild_id} if guild_id else {})}
    med_total    = await db.get_collection("mediators").count_documents(med_filter)
    med_active   = await db.get_collection("mediators").count_documents({**med_filter, "is_active": True})
    med_in_queue = await db.get_collection("mediators").count_documents({**med_filter, "in_queue": True})
    med_expired  = await db.get_collection("mediators").count_documents({
        **med_filter,
        "expiration_date": {"$lt": now},
        "is_active": True,
    })

    top_mediators_cursor = db.get_collection("mediators").find(
        med_filter,
        {"username": 1, "matches_mediated": 1}
    ).sort("matches_mediated", -1).limit(5)
    top_mediators = await top_mediators_cursor.to_list(5)

    # ── Partidas ──────────────────────────────────────────────────
    m_filter_period = {**match_filter, "created_at": {"$gte": since}}

    match_total     = await db.get_collection("matches").count_documents(match_filter)
    match_period    = await db.get_collection("matches").count_documents(m_filter_period)
    match_active    = await db.get_collection("matches").count_documents({
        **match_filter, "status": {"$in": [
            "aguardando_pagamento", "aguardando_inicio",
            "em_andamento", "aguardando_premio"
        ]}
    })
    match_finished  = await db.get_collection("matches").count_documents(
        {**match_filter, "status": "finalizado"})
    match_cancelled = await db.get_collection("matches").count_documents(
        {**match_filter, "status": "cancelado"})

    # partidas por status (periodo)
    status_pipeline = [
        {"$match": m_filter_period},
        {"$group": {"_id": "$status", "count": {"$sum": 1}}},
    ]
    status_raw = await db.get_collection("matches").aggregate(status_pipeline).to_list(20)
    status_counts = {s["_id"]: s["count"] for s in status_raw}

    # partidas por dia (últimos periodo_dias)
    day_pipeline = [
        {"$match": m_filter_period},
        {"$group": {
            "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}},
            "count": {"$sum": 1}
        }},
        {"$sort": {"_id": 1}},
    ]
    day_raw  = await db.get_collection("matches").aggregate(day_pipeline).to_list(periodo_dias + 2)
    day_data = {d["_id"]: d["count"] for d in day_raw}

    # ── Filas ─────────────────────────────────────────────────────
    q_filter = {**({"guild_id": guild_id} if guild_id else {})}
    q_waiting   = await db.get_collection("match_queues").count_documents(
        {**q_filter, "status": "waiting"})
    q_confirming = await db.get_collection("match_queues").count_documents(
        {**q_filter, "status": "confirming"})
    q_matched   = await db.get_collection("match_queues").count_documents(
        {**q_filter, "status": "matched"})
    q_expired   = await db.get_collection("match_queues").count_documents(
        {**q_filter, "status": "expired"})

    return {
        "med_total": med_total, "med_active": med_active,
        "med_in_queue": med_in_queue, "med_expired": med_expired,
        "top_mediators": top_mediators,
        "match_total": match_total, "match_period": match_period,
        "match_active": match_active, "match_finished": match_finished,
        "match_cancelled": match_cancelled,
        "status_counts": status_counts, "day_data": day_data,
        "q_waiting": q_waiting, "q_confirming": q_confirming,
        "q_matched": q_matched, "q_expired": q_expired,
        "periodo_dias": periodo_dias, "now": now,
    }


# ─── Renderização ─────────────────────────────────────────────────────────────

def _render(data: dict) -> io.BytesIO:
    _setup_rcparams()
    fig = plt.figure(figsize=(14, 9), dpi=110)
    fig.patch.set_facecolor(BG)

    # ── Grid: 4 linhas × 6 colunas ───────────────────────────────
    gs = gridspec.GridSpec(
        4, 6,
        figure=fig,
        hspace=0.55, wspace=0.35,
        top=0.88, bottom=0.06,
        left=0.04, right=0.97,
    )

    now_str = data["now"].strftime("%d/%m/%Y %H:%M UTC")

    # ── Cabeçalho ─────────────────────────────────────────────────
    fig.text(0.04, 0.96, "[OP] Dashboard Operacional",
             fontsize=16, fontweight="bold", color=WHITE, va="top")
    fig.text(0.04, 0.91, f"Atualizado em {now_str}  •  últimos {data['periodo_dias']} dias",
             fontsize=8.5, color=MUTED, va="top")
    # linha decorativa
    fig.add_artist(plt.Line2D(
        [0.04, 0.97], [0.895, 0.895],
        transform=fig.transFigure,
        color=ACCENT, linewidth=1.2, alpha=0.5
    ))

    # ══ LINHA 0 — KPIs Mediadores (6 cards) ══════════════════════
    _section_title(fig, "MEDIADORES", 0.04, 0.885, CYAN)
    kpi_defs = [
        (data["med_total"],    "Total",         ACCENT),
        (data["med_active"],   "Ativos",         GREEN),
        (data["med_in_queue"], "Na Fila",        YELLOW),
        (data["med_expired"],  "Licença Vencida",RED),
        (data["match_total"],  "Partidas Total", PURPLE),
        (data["match_active"], "Partidas Ativas",CYAN),
    ]
    for col, (val, lbl, clr) in enumerate(kpi_defs):
        ax = fig.add_subplot(gs[0, col])
        _kpi(ax, val, lbl, color=clr)

    # ══ LINHA 1 — Gráfico linha partidas/dia + donut status ═══════
    # Linha de partidas por dia
    ax_line = fig.add_subplot(gs[1, :4])
    _clear_ax(ax_line, CARD)
    ax_line.set_facecolor(CARD)
    for sp in ax_line.spines.values():
        sp.set_visible(False)

    # Gerar eixo de datas completo
    period = data["periodo_dias"]
    dates  = [(data["now"] - timedelta(days=period - 1 - i)).strftime("%Y-%m-%d")
              for i in range(period)]
    counts = [data["day_data"].get(d, 0) for d in dates]
    labels = [(data["now"] - timedelta(days=period - 1 - i)).strftime("%d/%m")
              for i in range(period)]

    x = np.arange(len(dates))
    ax_line.fill_between(x, counts, alpha=0.18, color=ACCENT)
    ax_line.plot(x, counts, color=ACCENT, linewidth=2, marker="o",
                 markersize=4, markerfacecolor=WHITE)
    ax_line.set_xticks(x)
    ax_line.set_xticklabels(labels, fontsize=7.5, color=MUTED)
    ax_line.set_yticks([])
    ax_line.tick_params(left=False, bottom=False)
    ax_line.set_title("Partidas por Dia", fontsize=9, color=MUTED,
                      loc="left", pad=6)
    ax_line.grid(axis="y", alpha=0.3)

    # Donut status partidas
    ax_donut = fig.add_subplot(gs[1, 4:])
    _clear_ax(ax_donut, CARD)
    status_labels_pt = {
        "aguardando_pagamento": "Ag. Pagto",
        "aguardando_inicio":    "Ag. Início",
        "em_andamento":         "Em Andamento",
        "aguardando_premio":    "Ag. Prêmio",
        "finalizado":           "Finalizado",
        "cancelado":            "Cancelado",
    }
    sc = data["status_counts"]
    valid = {k: v for k, v in sc.items() if v > 0}
    if valid:
        s_labels = [status_labels_pt.get(k, k) for k in valid]
        s_values = list(valid.values())
        s_colors = [YELLOW, CYAN, GREEN, PURPLE, ACCENT, RED][:len(s_values)]
        wedges, _ = ax_donut.pie(
            s_values, labels=None, colors=s_colors,
            startangle=90, wedgeprops={"width": 0.55, "edgecolor": BG, "linewidth": 1.5}
        )
        ax_donut.legend(
            wedges, [f"{l} ({v})" for l, v in zip(s_labels, s_values)],
            loc="center left", bbox_to_anchor=(0.92, 0.5),
            fontsize=6.8, frameon=False, labelcolor=WHITE,
        )
    ax_donut.set_title("Status Partidas (período)", fontsize=9,
                       color=MUTED, loc="left", pad=6)

    # ══ LINHA 2 — Top Mediadores + KPIs Filas ════════════════════
    # Barras horizontais top mediadores
    ax_bar = fig.add_subplot(gs[2, :3])
    _clear_ax(ax_bar, CARD)
    ax_bar.set_facecolor(CARD)
    for sp in ax_bar.spines.values():
        sp.set_visible(False)

    top = data["top_mediators"]
    if top:
        names  = [m.get("username", "?")[:14] for m in reversed(top)]
        values = [m.get("matches_mediated", 0) for m in reversed(top)]
        y = np.arange(len(names))
        bars = ax_bar.barh(y, values, color=ACCENT, height=0.55,
                           edgecolor="none")
        for i, (bar, val) in enumerate(zip(bars, values)):
            ax_bar.text(val + max(values) * 0.02, i, str(val),
                        va="center", fontsize=7.5, color=WHITE)
        ax_bar.set_yticks(y)
        ax_bar.set_yticklabels(names, fontsize=8, color=WHITE)
        ax_bar.set_xticks([])
        ax_bar.set_title("Top 5 Mediadores (partidas)", fontsize=9,
                         color=MUTED, loc="left", pad=6)
        # Colorir o 1º lugar
        bars[-1].set_color(YELLOW)
    else:
        ax_bar.text(0.5, 0.5, "Sem dados", ha="center", va="center",
                    color=MUTED, fontsize=9)

    # KPIs filas (3 colunas direitas)
    fila_kpis = [
        (data["q_waiting"],    "Aguardando", YELLOW),
        (data["q_confirming"], "Confirmando", CYAN),
        (data["q_matched"],    "Convertidas", GREEN),
    ]
    for i, (val, lbl, clr) in enumerate(fila_kpis):
        ax = fig.add_subplot(gs[2, 3 + i])
        _kpi(ax, val, lbl, color=clr)

    # ══ LINHA 3 — Barras de status filas + stats finais ══════════
    ax_fila = fig.add_subplot(gs[3, :3])
    _clear_ax(ax_fila, CARD)
    ax_fila.set_facecolor(CARD)
    for sp in ax_fila.spines.values():
        sp.set_visible(False)

    fila_cats  = ["Waiting", "Confirming", "Matched", "Expired"]
    fila_vals  = [data["q_waiting"], data["q_confirming"],
                  data["q_matched"], data["q_expired"]]
    fila_clrs  = [YELLOW, CYAN, GREEN, RED]
    xb = np.arange(len(fila_cats))
    bars2 = ax_fila.bar(xb, fila_vals, color=fila_clrs,
                        width=0.55, edgecolor="none")
    for bar, val in zip(bars2, fila_vals):
        ax_fila.text(bar.get_x() + bar.get_width() / 2,
                     bar.get_height() + max(fila_vals, default=1) * 0.03,
                     str(val), ha="center", fontsize=8, color=WHITE)
    ax_fila.set_xticks(xb)
    ax_fila.set_xticklabels(fila_cats, fontsize=8, color=MUTED)
    ax_fila.set_yticks([])
    ax_fila.set_title("Filas por Status", fontsize=9, color=MUTED,
                      loc="left", pad=6)

    # Stats finalizados / cancelados
    stats_kpis = [
        (data["match_finished"],  "Finalizadas", GREEN),
        (data["match_cancelled"], "Canceladas",  RED),
        (data["match_period"],    f"Novas ({data['periodo_dias']}d)", ACCENT),
    ]
    for i, (val, lbl, clr) in enumerate(stats_kpis):
        ax = fig.add_subplot(gs[3, 3 + i])
        _kpi(ax, val, lbl, color=clr)

    # ── Salvar ────────────────────────────────────────────────────
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110,
                facecolor=BG, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


# ─── Função pública ───────────────────────────────────────────────────────────

async def build_operacional_image(
    db,
    guild_id: int | None = None,
    periodo_dias: int = 7,
) -> io.BytesIO:
    """
    Retorna BytesIO com a imagem PNG do dashboard operacional.

    Parâmetros
    ----------
    db           : banco motor (AsyncIOMotorDatabase)
    guild_id     : filtrar por servidor (None = todos)
    periodo_dias : janela de tempo para gráficos (padrão 7)
    """
    data = await _fetch_data(db, guild_id=guild_id, periodo_dias=periodo_dias)
    return _render(data)


# ─── Comando Discord (Cog) ────────────────────────────────────────────────────

class DashboardOperacionalCog(discord.ext.commands.Cog):
    """
    Cog com slash command /dashboard_operacional
    Registre no bot com: await bot.add_cog(DashboardOperacionalCog(bot, db))
    """

    def __init__(self, bot: discord.ext.commands.Bot, db):
        self.bot = bot
        self.db  = db

    @discord.app_commands.command(
        name="dashboard_operacional",
        description="Exibe o dashboard operacional de mediadores e partidas",
    )
    @discord.app_commands.describe(
        periodo="Período em dias (padrão: 7)",
        guild_id="ID do servidor (deixe vazio para todos)",
    )
    async def dashboard_operacional(
        self,
        interaction: discord.Interaction,
        periodo: int = 7,
        guild_id: str | None = None,
    ):
        await interaction.response.defer(thinking=True)

        gid = int(guild_id) if guild_id else None
        buf = await build_operacional_image(self.db, guild_id=gid,
                                            periodo_dias=periodo)

        file   = discord.File(buf, filename="dashboard_operacional.png")
        embed  = discord.Embed(
            title="[OP] Dashboard Operacional",
            description=f"Mediadores · Partidas · Filas  •  últimos **{periodo}** dias",
            color=0x5865F2,
            timestamp=discord.utils.utcnow(),
        )
        embed.set_image(url="attachment://dashboard_operacional.png")
        embed.set_footer(text="Atualizado agora • use /dashboard_operacional para refresh")

        await interaction.followup.send(embed=embed, file=file)


async def setup(bot):
    """Chamado pelo bot.load_extension('dashboard_operacional')"""
    from motor.motor_asyncio import AsyncIOMotorClient  # type: ignore
    # Ajuste a URI e nome do banco conforme seu projeto
    client = AsyncIOMotorClient(bot.mongo_uri)
    db     = client[bot.mongo_db_name]
    await bot.add_cog(DashboardOperacionalCog(bot, db))
