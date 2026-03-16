"""
dashboard_service.py — F12: Analytics & Dashboards completos.

6 dashboards:
  • dashboard-partidas     — volume, apostas, modos, cancelamento, horários
  • dashboard-mediadores   — ranking, faturamento, tempo resposta
  • dashboard-jogadores    — ranking, winrate, retenção
  • dashboard-suporte      — tickets por período/categoria/atendente
  • dashboard-servidor     — membros, onboarding, crescimento, spam
  • dashboard-influencers  — ranking, comissão, conversão

Cada dashboard é um embed fixo no canal com botões Atualizar + Exportar.
"""
from __future__ import annotations

import io
import csv
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional

import discord
from discord.ext import tasks

from config.database import db
from utils.datetime_utils import utcnow
from utils.logger import logger

THEME     = 0xFFD54F
THEME2    = 0xFFA726
COLOR_OK  = 0x2ECC71
COLOR_ERR = 0xE74C3C

# Nomes dos canais
CH_PARTIDAS    = "dashboard-partidas"
CH_MEDIADORES  = "dashboard-mediadores"
CH_JOGADORES   = "ranking"
CH_SUPORTE     = "dashboard-suporte"
CH_SERVIDOR    = "status-bot"
CH_INFLUENCERS = "dashboard-influencers"


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def _now() -> datetime:
    return utcnow()

def _since(days: int) -> datetime:
    return _now() - timedelta(days=days)

def _bar(value: int, total: int, size: int = 10) -> str:
    if total == 0:
        return "░" * size
    filled = round(value / total * size)
    return "█" * filled + "░" * (size - filled)

def _pct(part: int, total: int) -> str:
    if total == 0:
        return "0%"
    return f"{part/total*100:.1f}%"

def _fmt_dur(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.0f}s"
    if seconds < 3600:
        return f"{seconds/60:.1f}min"
    return f"{seconds/3600:.1f}h"


# ─────────────────────────────────────────────────────────────
# DashboardService
# ─────────────────────────────────────────────────────────────

class DashboardService:

    def __init__(self):
        self.bot: Optional[discord.Client] = None

    # ══════════════════════════════════════════════════════════
    # SETUP — posta a mensagem fixa em cada canal
    # ══════════════════════════════════════════════════════════

    async def setup_all(self, guild: discord.Guild):
        """Posta/atualiza a mensagem fixa em todos os 6 canais."""
        await asyncio.gather(
            self.setup_channel(guild, CH_PARTIDAS,    self.build_partidas),
            self.setup_channel(guild, CH_MEDIADORES,  self.build_mediadores),
            self.setup_channel(guild, CH_JOGADORES,   self.build_jogadores),
            self.setup_channel(guild, CH_SUPORTE,     self.build_suporte),
            self.setup_channel(guild, CH_SERVIDOR,    self.build_servidor),
            self.setup_channel(guild, CH_INFLUENCERS, self.build_influencers),
        )

    async def setup_channel(self, guild: discord.Guild, ch_name: str, builder):
        ch = discord.utils.get(guild.text_channels, name=ch_name)
        if not ch:
            logger.warning(f"[Dashboard] Canal #{ch_name} não encontrado. Rode !setupcanais primeiro.")
            return
        embed, csv_data = await builder(guild.id)
        from views.dashboard_view import DashboardView
        view = DashboardView(ch_name=ch_name, guild_id=guild.id, builder=builder)
        # Procura mensagem fixa existente do bot
        async for msg in ch.history(limit=10):
            if msg.author == guild.me and msg.embeds:
                await msg.edit(embed=embed, view=view)
                logger.info(f"[Dashboard] #{ch_name} atualizado")
                return
        await ch.send(embed=embed, view=view)
        logger.info(f"[Dashboard] #{ch_name} postado")

    # ══════════════════════════════════════════════════════════
    # TASK — atualiza todos a cada hora
    # ══════════════════════════════════════════════════════════

    @tasks.loop(hours=1)
    async def hourly_update(self):
        if not self.bot:
            return
        for guild in self.bot.guilds:
            try:
                await self.setup_all(guild)
            except Exception as e:
                logger.error(f"[Dashboard] hourly_update erro em {guild.name}: {e}")

    @hourly_update.before_loop
    async def before_hourly(self):
        await self.bot.wait_until_ready()

    # ══════════════════════════════════════════════════════════
    # 1. DASHBOARD — PARTIDAS
    # ══════════════════════════════════════════════════════════

    async def build_partidas(self, guild_id: int) -> tuple[discord.Embed, str]:
        col = db.get_collection("matches")
        now = _now()

        # Totais por período
        total_7d  = await col.count_documents({"created_at": {"$gte": _since(7)}})
        total_30d = await col.count_documents({"created_at": {"$gte": _since(30)}})
        total_all = await col.count_documents({})

        fin_7d  = await col.count_documents({"status": "finalizado", "created_at": {"$gte": _since(7)}})
        can_7d  = await col.count_documents({"status": "cancelado",  "created_at": {"$gte": _since(7)}})

        # Volume apostado (7 dias)
        pipeline_valor = [
            {"$match": {"status": "finalizado", "created_at": {"$gte": _since(7)}}},
            {"$group": {"_id": None, "total": {"$sum": "$bet_value"}}}
        ]
        r = await col.aggregate(pipeline_valor).to_list(1)
        volume_7d = r[0]["total"] if r else 0.0

        # Modos mais jogados
        pipeline_modos = [
            {"$match": {"created_at": {"$gte": _since(30)}}},
            {"$group": {"_id": "$channel_name", "total": {"$sum": 1}}},
            {"$sort": {"total": -1}},
            {"$limit": 5}
        ]
        modos = await col.aggregate(pipeline_modos).to_list(5)

        # Faixas de valor
        pipeline_faixas = [
            {"$match": {"status": "finalizado", "created_at": {"$gte": _since(30)}}},
            {"$group": {"_id": "$bet_value", "total": {"$sum": 1}}},
            {"$sort": {"_id": 1}}
        ]
        faixas = await col.aggregate(pipeline_faixas).to_list(20)

        # Horários de pico (UTC-3 = BRT)
        pipeline_horas = [
            {"$match": {"created_at": {"$gte": _since(7)}}},
            {"$project": {"hora": {"$subtract": [{"$hour": "$created_at"}, 3]}}},
            {"$group": {"_id": "$hora", "total": {"$sum": 1}}},
            {"$sort": {"total": -1}},
            {"$limit": 3}
        ]
        pico = await col.aggregate(pipeline_horas).to_list(3)

        # Duração média (finished_at - started_at)
        pipeline_dur = [
            {"$match": {"finished_at": {"$exists": True}, "started_at": {"$exists": True},
                        "created_at": {"$gte": _since(30)}}},
            {"$project": {"dur": {"$subtract": ["$finished_at", "$started_at"]}}},
            {"$group": {"_id": None, "avg": {"$avg": "$dur"}}}
        ]
        dur_r = await col.aggregate(pipeline_dur).to_list(1)
        dur_avg = dur_r[0]["avg"] / 1000 if dur_r else None  # ms → s

        embed = discord.Embed(
            title="Dashboard — Partidas",
            color=THEME,
            timestamp=now
        )

        embed.add_field(
            name="Últimos 7 dias",
            value=(
                f"Total: **{total_7d}** | Finalizadas: **{fin_7d}** | Canceladas: **{can_7d}**\n"
                f"Taxa conclusão: **{_pct(fin_7d, total_7d)}** | Volume apostado: **R$ {volume_7d:.2f}**"
            ),
            inline=False
        )
        embed.add_field(
            name="Últimos 30 dias",
            value=f"Total: **{total_30d}** | Geral (all time): **{total_all}**",
            inline=False
        )

        if modos:
            top_total = sum(m["total"] for m in modos)
            lines = [
                f"`{m['_id'] or '—':15}` {_bar(m['total'], top_total)} **{m['total']}**"
                for m in modos
            ]
            embed.add_field(name="Modos mais jogados (30d)", value="\n".join(lines), inline=False)

        if faixas:
            lines = [f"R$ {f['_id']:.0f} — **{f['total']}** partidas" for f in faixas[:6]]
            embed.add_field(name="Partidas por valor (30d)", value="\n".join(lines), inline=True)

        if pico:
            lines = [f"`{(h['_id'] % 24):02d}h` — **{h['total']}** partidas" for h in pico]
            embed.add_field(name="Horários de pico (7d, BRT)", value="\n".join(lines), inline=True)

        if dur_avg:
            embed.add_field(name="Duração média", value=f"**{_fmt_dur(dur_avg)}** por partida", inline=True)

        embed.set_footer(text=f"Atualizado em {now.strftime('%d/%m/%Y %H:%M')} UTC")

        # CSV export
        rows = [["periodo", "total", "finalizadas", "canceladas", "volume_apostado"]]
        rows.append(["7 dias", total_7d, fin_7d, can_7d, f"{volume_7d:.2f}"])
        rows.append(["30 dias", total_30d, "-", "-", "-"])
        rows.append(["all time", total_all, "-", "-", "-"])
        for m in modos:
            rows.append([f"modo:{m['_id']}", m["total"], "-", "-", "-"])
        csv_data = _to_csv(rows)

        return embed, csv_data

    # ══════════════════════════════════════════════════════════
    # 2. DASHBOARD — MEDIADORES
    # ══════════════════════════════════════════════════════════

    async def build_mediadores(self, guild_id: int) -> tuple[discord.Embed, str]:
        col_matches = db.get_collection("matches")
        col_med     = db.get_collection("mediators")
        now = _now()

        # Ranking por partidas (30d)
        pipeline_rank = [
            {"$match": {"status": "finalizado", "created_at": {"$gte": _since(30)},
                        "mediator_id": {"$exists": True, "$ne": None}}},
            {"$group": {"_id": "$mediator_id", "total": {"$sum": 1},
                        "volume": {"$sum": "$bet_value"}}},
            {"$sort": {"total": -1}},
            {"$limit": 8}
        ]
        ranking = await col_matches.aggregate(pipeline_rank).to_list(8)

        # Canceladas por mediador (30d)
        pipeline_can = [
            {"$match": {"status": "cancelado", "created_at": {"$gte": _since(30)},
                        "mediator_id": {"$exists": True, "$ne": None}}},
            {"$group": {"_id": "$mediator_id", "canceladas": {"$sum": 1}}}
        ]
        canceladas_map = {r["_id"]: r["canceladas"] async for r in col_matches.aggregate(pipeline_can)}

        total_finalizadas_30d = await col_matches.count_documents(
            {"status": "finalizado", "created_at": {"$gte": _since(30)}}
        )
        ativos = await col_med.count_documents({"in_queue": True, "is_active": True})
        total_med = await col_med.count_documents({"is_active": True})

        embed = discord.Embed(title="Dashboard — Mediadores", color=THEME, timestamp=now)
        embed.add_field(
            name="Status atual",
            value=f"Ativos: **{total_med}** | Na fila agora: **{ativos}** | Partidas finalizadas (30d): **{total_finalizadas_30d}**",
            inline=False
        )

        if ranking:
            lines = []
            medals = ["🥇", "🥈", "🥉"]
            for i, r in enumerate(ranking):
                med_doc = await col_med.find_one({"user_id": int(r["_id"])}) if r["_id"] else None
                name    = med_doc.get("username", f"ID:{r['_id']}") if med_doc else f"ID:{r['_id']}"
                can     = canceladas_map.get(r["_id"], 0)
                prefix  = medals[i] if i < 3 else f"`{i+1}.`"
                lines.append(
                    f"{prefix} **{name}** — {r['total']} partidas | R$ {r['volume']:.0f} | {can} cancel."
                )
            embed.add_field(name="Ranking (30d)", value="\n".join(lines), inline=False)

        # Tempo médio de resposta na fila
        pipeline_resp = [
            {"$match": {"started_at": {"$exists": True}, "created_at": {"$gte": _since(30)}}},
            {"$project": {"resp": {"$subtract": ["$started_at", "$created_at"]}}},
            {"$group": {"_id": None, "avg": {"$avg": "$resp"}}}
        ]
        resp_r = await col_matches.aggregate(pipeline_resp).to_list(1)
        if resp_r and resp_r[0]["avg"]:
            avg_resp = resp_r[0]["avg"] / 1000
            embed.add_field(name="Tempo médio até início (30d)", value=f"**{_fmt_dur(avg_resp)}**", inline=True)

        embed.set_footer(text=f"Atualizado em {now.strftime('%d/%m/%Y %H:%M')} UTC")

        rows = [["posicao", "mediador_id", "partidas", "volume", "canceladas"]]
        for i, r in enumerate(ranking, 1):
            rows.append([i, r["_id"], r["total"], f"{r['volume']:.2f}", canceladas_map.get(r["_id"], 0)])
        return embed, _to_csv(rows)

    # ══════════════════════════════════════════════════════════
    # 3. DASHBOARD — JOGADORES (canal #ranking)
    # ══════════════════════════════════════════════════════════

    async def build_jogadores(self, guild_id: int) -> tuple[discord.Embed, str]:
        col = db.get_collection("matches")
        col_users = db.get_collection("users")
        now = _now()

        # Ranking por partidas
        pipeline_rank = [
            {"$match": {"status": "finalizado", "created_at": {"$gte": _since(30)}}},
            {"$unwind": "$player_ids"},
            {"$group": {"_id": "$player_ids", "total": {"$sum": 1},
                        "wins": {"$sum": {"$cond": [{"$eq": ["$winner_id", "$player_ids"]}, 1, 0]}},
                        "volume": {"$sum": "$bet_value"}}},
            {"$sort": {"total": -1}},
            {"$limit": 10}
        ]
        ranking = await col.aggregate(pipeline_rank).to_list(10)

        # Retenção (jogadores que voltaram nos últimos 7d mas já jogaram antes)
        jogaram_7d   = await col.distinct("player_ids", {"created_at": {"$gte": _since(7)}})
        jogaram_30d  = await col.distinct("player_ids", {"created_at": {"$gte": _since(30)}})
        retidos = len(set(jogaram_7d) & set(jogaram_30d))

        total_jogadores = await col_users.count_documents({"has_accepted_rules": True})
        total_ativos_30d = len(set(jogaram_30d))

        embed = discord.Embed(title="Dashboard — Jogadores / Ranking", color=THEME, timestamp=now)
        embed.add_field(
            name="Visão geral",
            value=(
                f"Total de membros: **{total_jogadores}** | "
                f"Ativos (30d): **{total_ativos_30d}** | "
                f"Retidos (voltaram em 7d): **{retidos}**"
            ),
            inline=False
        )

        if ranking:
            lines = []
            medals = ["🥇", "🥈", "🥉"]
            for i, r in enumerate(ranking):
                wr    = _pct(r["wins"], r["total"])
                user_doc = await col_users.find_one({"discord_id": r["_id"]})
                name  = user_doc.get("username", f"<@{r['_id']}>") if user_doc else f"<@{r['_id']}>"
                prefix = medals[i] if i < 3 else f"`{i+1}.`"
                lines.append(f"{prefix} **{name}** — {r['total']} partidas | WR: {wr} | R$ {r['volume']:.0f}")
            embed.add_field(name="Top 10 jogadores (30d)", value="\n".join(lines), inline=False)

        embed.set_footer(text=f"Atualizado em {now.strftime('%d/%m/%Y %H:%M')} UTC")

        rows = [["posicao", "discord_id", "partidas", "wins", "winrate", "volume"]]
        for i, r in enumerate(ranking, 1):
            rows.append([i, r["_id"], r["total"], r["wins"], _pct(r["wins"], r["total"]), f"{r['volume']:.2f}"])
        return embed, _to_csv(rows)

    # ══════════════════════════════════════════════════════════
    # 4. DASHBOARD — SUPORTE
    # ══════════════════════════════════════════════════════════

    async def build_suporte(self, guild_id: int) -> tuple[discord.Embed, str]:
        col = db.get_collection("tickets")
        now = _now()

        total_7d  = await col.count_documents({"created_at": {"$gte": _since(7)}})
        abertos   = await col.count_documents({"status": {"$in": ["aberto", "pendente"]}})
        resolvidos_7d = await col.count_documents({"status": {"$in": ["resolvido", "fechado"]},
                                                    "closed_at": {"$gte": _since(7)}})

        # Por categoria
        pipeline_cat = [
            {"$match": {"created_at": {"$gte": _since(30)}}},
            {"$group": {"_id": "$categoria", "total": {"$sum": 1}}},
            {"$sort": {"total": -1}}
        ]
        categorias = await col.aggregate(pipeline_cat).to_list(10)

        # Por atendente
        pipeline_ate = [
            {"$match": {"atendente_id": {"$exists": True, "$ne": None},
                        "created_at": {"$gte": _since(30)}}},
            {"$group": {"_id": "$atendente_id", "total": {"$sum": 1},
                        "resolvidos": {"$sum": {"$cond": [
                            {"$in": ["$status", ["resolvido", "fechado"]]}, 1, 0
                        ]}}}},
            {"$sort": {"total": -1}},
            {"$limit": 5}
        ]
        atendentes = await col.aggregate(pipeline_ate).to_list(5)

        # Tempo médio de resolução
        pipeline_tempo = [
            {"$match": {"closed_at": {"$exists": True}, "created_at": {"$gte": _since(30)}}},
            {"$project": {"dur": {"$subtract": ["$closed_at", "$created_at"]}}},
            {"$group": {"_id": None, "avg": {"$avg": "$dur"}}}
        ]
        tempo_r = await col.aggregate(pipeline_tempo).to_list(1)
        tempo_avg = tempo_r[0]["avg"] / 1000 if tempo_r else None

        embed = discord.Embed(title="Dashboard — Suporte", color=THEME, timestamp=now)
        embed.add_field(
            name="Status atual",
            value=(
                f"Abertos agora: **{abertos}** | "
                f"Criados (7d): **{total_7d}** | "
                f"Resolvidos (7d): **{resolvidos_7d}**"
            ),
            inline=False
        )

        if tempo_avg:
            embed.add_field(name="Tempo médio de resolução (30d)", value=f"**{_fmt_dur(tempo_avg)}**", inline=True)

        if categorias:
            total_cat = sum(c["total"] for c in categorias)
            lines = [f"`{c['_id'] or 'Outro':12}` {_bar(c['total'], total_cat, 8)} **{c['total']}**"
                     for c in categorias]
            embed.add_field(name="Por categoria (30d)", value="\n".join(lines), inline=False)

        if atendentes:
            lines = [f"<@{a['_id']}> — **{a['total']}** atendidos | {a['resolvidos']} resolvidos"
                     for a in atendentes]
            embed.add_field(name="Top atendentes (30d)", value="\n".join(lines), inline=False)

        embed.set_footer(text=f"Atualizado em {now.strftime('%d/%m/%Y %H:%M')} UTC")

        rows = [["categoria", "total_30d"]] + [[c["_id"], c["total"]] for c in categorias]
        return embed, _to_csv(rows)

    # ══════════════════════════════════════════════════════════
    # 5. DASHBOARD — SERVIDOR (canal #status-bot)
    # ══════════════════════════════════════════════════════════

    async def build_servidor(self, guild_id: int) -> tuple[discord.Embed, str]:
        col_users = db.get_collection("users")
        now = _now()

        total       = await col_users.count_documents({})
        ativos      = await col_users.count_documents({"is_active": True})
        aceitaram   = await col_users.count_documents({"onboarding_result": "aceito"})
        recusaram   = await col_users.count_documents({"onboarding_result": "recusado"})
        timeout     = await col_users.count_documents({"onboarding_result": "timeout"})
        bloqueados  = await col_users.count_documents({"spam_blocked": True})
        novos_7d    = await col_users.count_documents({"created_at": {"$gte": _since(7)}})
        novos_30d   = await col_users.count_documents({"created_at": {"$gte": _since(30)}})

        pending = total - aceitaram - recusaram - timeout if total > 0 else 0

        embed = discord.Embed(title="Status do Sistema", color=COLOR_OK, timestamp=now)
        embed.add_field(name="Bot", value="🟢 Online", inline=True)
        embed.add_field(name="Banco", value="🟢 Conectado", inline=True)
        embed.add_field(name="Fila", value="🟢 Ativa", inline=True)

        embed.add_field(
            name="Membros",
            value=(
                f"Total: **{total}** | Ativos: **{ativos}**\n"
                f"Novos (7d): **{novos_7d}** | Novos (30d): **{novos_30d}**\n"
                f"Bloqueados por spam: **{bloqueados}**"
            ),
            inline=False
        )
        embed.add_field(
            name="Onboarding",
            value=(
                f"Aceitaram: **{aceitaram}** ({_pct(aceitaram, total)})\n"
                f"Recusaram: **{recusaram}** | Timeout: **{timeout}**\n"
                f"Pendentes: **{pending}**"
            ),
            inline=False
        )
        embed.set_footer(text=f"Atualizado em {now.strftime('%d/%m/%Y %H:%M')} UTC")

        rows = [["metrica", "valor"],
                ["total_membros", total], ["ativos", ativos],
                ["aceitaram_regras", aceitaram], ["recusaram", recusaram],
                ["timeout", timeout], ["bloqueados_spam", bloqueados],
                ["novos_7d", novos_7d], ["novos_30d", novos_30d]]
        return embed, _to_csv(rows)

    # ══════════════════════════════════════════════════════════
    # 6. DASHBOARD — INFLUENCERS
    # ══════════════════════════════════════════════════════════

    async def build_influencers(self, guild_id: int) -> tuple[discord.Embed, str]:
        col_inf    = db.get_collection("influencers")
        col_joins  = db.get_collection("invite_joins")
        col_match  = db.get_collection("matches")
        now = _now()

        all_inf = await col_inf.find({"is_active": True}).to_list(None)

        rows_data = []
        for inf in all_inf:
            invite_code = inf.get("invite_code", "")
            members = await col_joins.count_documents({
                "invite_code": invite_code, "guild_id": str(guild_id)
            })
            member_ids = await col_joins.distinct("member_id", {
                "invite_code": invite_code, "guild_id": str(guild_id)
            })
            # Conversão: quantos jogaram pelo menos 1 partida
            jogaram = 0
            for mid in member_ids:
                c = await col_match.count_documents({"player_ids": mid})
                if c > 0:
                    jogaram += 1

            commission = members * inf.get("commission_per_member", 2.0)
            rows_data.append({
                "name":       inf.get("username", "?"),
                "discord_id": inf.get("discord_id"),
                "members":    members,
                "jogaram":    jogaram,
                "conv":       _pct(jogaram, members) if members > 0 else "0%",
                "commission": commission,
            })

        rows_data.sort(key=lambda x: x["members"], reverse=True)
        total_members  = sum(r["members"] for r in rows_data)
        total_commission = sum(r["commission"] for r in rows_data)

        embed = discord.Embed(title="Dashboard — Influencers", color=THEME, timestamp=now)
        embed.add_field(
            name="Visão geral",
            value=(
                f"Influencers ativos: **{len(all_inf)}** | "
                f"Total membros trazidos: **{total_members}** | "
                f"Comissão total: **R$ {total_commission:.2f}**"
            ),
            inline=False
        )

        if rows_data:
            medals = ["🥇", "🥈", "🥉"]
            lines  = []
            for i, r in enumerate(rows_data[:8]):
                prefix = medals[i] if i < 3 else f"`{i+1}.`"
                lines.append(
                    f"{prefix} **{r['name']}** — {r['members']} membros | "
                    f"{r['jogaram']} jogaram ({r['conv']}) | R$ {r['commission']:.2f}"
                )
            embed.add_field(name="Ranking", value="\n".join(lines), inline=False)

        embed.set_footer(text=f"Atualizado em {now.strftime('%d/%m/%Y %H:%M')} UTC")

        csv_rows = [["posicao", "nome", "discord_id", "membros", "jogaram", "conversao", "comissao"]]
        for i, r in enumerate(rows_data, 1):
            csv_rows.append([i, r["name"], r["discord_id"], r["members"], r["jogaram"], r["conv"], f"{r['commission']:.2f}"])
        return embed, _to_csv(csv_rows)


# ─────────────────────────────────────────────────────────────
# Helper CSV
# ─────────────────────────────────────────────────────────────

def _to_csv(rows: list) -> str:
    buf = io.StringIO()
    w   = csv.writer(buf)
    w.writerows(rows)
    return buf.getvalue()


dashboard_service = DashboardService()
