"""
analytics_service.py — F12: Analytics & Dashboards completos.

Dashboards:
  • Partidas   — volume, apostas, modos, pico, cancelamentos
  • Mediadores — ranking, partidas, volume
  • Jogadores  — top ativos, winrate, volume (postado em #ranking)
  • Suporte    — tickets por período, categoria, atendente
  • Servidor   — membros, onboarding, crescimento (#status-bot)
  • Influencers — ranking, comissão, partidas

Atualização automática a cada hora via task.
"""
from __future__ import annotations
from datetime import timedelta
from typing import Optional

import discord
from discord.ext import tasks

from config.database import db
from utils.datetime_utils import utcnow
from utils.logger import logger

THEME  = 0xFFD54F
THEME2 = 0xFFA726
GREEN  = 0x2ECC71


def _pct(a, b) -> str:
    return f"{a/b*100:.1f}%" if b else "0%"

def _brl(v: float) -> str:
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


class AnalyticsService:

    def __init__(self):
        self.bot: Optional[discord.Client] = None

    @tasks.loop(hours=1)
    async def hourly_update(self):
        if not self.bot:
            return
        for guild in self.bot.guilds:
            try:
                await self.update_all(guild)
            except Exception as e:
                logger.error(f"[Analytics] Erro: {e}")

    @hourly_update.before_loop
    async def before_hourly(self):
        await self.bot.wait_until_ready()

    async def update_all(self, guild: discord.Guild):
        await self._matches(guild)
        await self._mediators(guild)
        await self._players(guild)
        await self._support(guild)
        await self._server(guild)
        await self._influencers(guild)

    async def _post(self, guild: discord.Guild, ch_name: str, embeds: list):
        ch = discord.utils.get(guild.text_channels, name=ch_name)
        if not ch:
            return
        try:
            msgs = []
            async for m in ch.history(limit=20):
                if m.author == guild.me and m.embeds:
                    msgs.append(m)
            msgs.reverse()
            for i, embed in enumerate(embeds):
                if i < len(msgs):
                    await msgs[i].edit(embed=embed)
                else:
                    await ch.send(embed=embed)
            for m in msgs[len(embeds):]:
                await m.delete()
        except Exception as e:
            logger.warning(f"[Analytics] #{ch_name}: {e}")

    # ── Dashboard de Partidas ─────────────────
    async def _matches(self, guild: discord.Guild):
        col = db.get_collection("matches")
        now = utcnow()
        embeds = []

        for label, days in [("7 dias", 7), ("30 dias", 30)]:
            since = now - timedelta(days=days)
            q = {"created_at": {"$gte": since}}

            total       = await col.count_documents(q)
            finalizadas = await col.count_documents({**q, "status": "finalizado"})
            canceladas  = await col.count_documents({**q, "status": "cancelado"})

            vol_agg = await col.aggregate([
                {"$match": q}, {"$group": {"_id": None, "s": {"$sum": "$bet_value"}}}
            ]).to_list(1)
            volume = vol_agg[0]["s"] if vol_agg else 0.0

            modos = await col.aggregate([
                {"$match": q}, {"$group": {"_id": "$channel_name", "c": {"$sum": 1}}},
                {"$sort": {"c": -1}}, {"$limit": 5}
            ]).to_list(5)

            picos = await col.aggregate([
                {"$match": q},
                {"$project": {"h": {"$hour": "$created_at"}}},
                {"$group": {"_id": "$h", "c": {"$sum": 1}}},
                {"$sort": {"c": -1}}, {"$limit": 3}
            ]).to_list(3)

            faixas = await col.aggregate([
                {"$match": q}, {"$group": {"_id": "$bet_value", "c": {"$sum": 1}}},
                {"$sort": {"c": -1}}, {"$limit": 5}
            ]).to_list(5)

            e = discord.Embed(title=f"Partidas — Últimos {label}", color=THEME)
            e.add_field(name="Total",       value=f"`{total}`",                                    inline=True)
            e.add_field(name="Finalizadas", value=f"`{finalizadas}` ({_pct(finalizadas,total)})",  inline=True)
            e.add_field(name="Canceladas",  value=f"`{canceladas}` ({_pct(canceladas,total)})",    inline=True)
            e.add_field(name="Volume apostado", value=f"**{_brl(volume)}**",                       inline=False)
            if modos:
                e.add_field(name="Modos mais jogados",
                    value="\n".join(f"`{m['_id'] or '?'}` — {m['c']}x" for m in modos), inline=True)
            if picos:
                e.add_field(name="Horários de pico",
                    value="\n".join(f"`{p['_id']:02d}h` — {p['c']} partidas" for p in picos), inline=True)
            if faixas:
                e.add_field(name="Valores apostados",
                    value="\n".join(f"`R${f['_id']:.0f}` — {f['c']}x" for f in faixas), inline=True)
            e.set_footer(text=f"Atualizado {now.strftime('%d/%m/%Y %H:%M')} UTC")
            embeds.append(e)

        await self._post(guild, "dashboard-partidas", embeds)

    # ── Dashboard de Mediadores ───────────────
    async def _mediators(self, guild: discord.Guild):
        col     = db.get_collection("matches")
        med_col = db.get_collection("mediators")
        now     = utcnow()
        since   = now - timedelta(days=30)

        ranking = await col.aggregate([
            {"$match": {"created_at": {"$gte": since}, "mediator_id": {"$ne": None}}},
            {"$group": {
                "_id":   "$mediator_id",
                "total": {"$sum": 1},
                "fin":   {"$sum": {"$cond": [{"$eq": ["$status", "finalizado"]}, 1, 0]}},
                "canc":  {"$sum": {"$cond": [{"$eq": ["$status", "cancelado"]}, 1, 0]}},
                "vol":   {"$sum": "$bet_value"}
            }},
            {"$sort": {"total": -1}}, {"$limit": 10}
        ]).to_list(10)

        e = discord.Embed(title="Mediadores — Últimos 30 dias", color=THEME2)
        medals = ["🥇","🥈","🥉"]

        if not ranking:
            e.description = "Nenhuma partida mediada ainda."
        else:
            lines = []
            for i, r in enumerate(ranking):
                med  = await med_col.find_one({"user_id": int(r["_id"])}) if r["_id"] else None
                name = med.get("username", r["_id"]) if med else str(r["_id"])
                icon = medals[i] if i < 3 else f"`{i+1}.`"
                lines.append(
                    f"{icon} **{name}** — `{r['total']}` | fin:`{r['fin']}` "
                    f"canc:`{r['canc']}` | {_brl(r.get('vol',0))}"
                )
            e.description = "\n".join(lines)

        ativos = await med_col.count_documents({"in_queue": True, "is_active": True})
        e.add_field(name="Na fila agora",   value=f"`{ativos}`", inline=True)
        e.add_field(name="Partidas no mês", value=f"`{await col.count_documents({'created_at':{'$gte':since}})}`", inline=True)
        e.set_footer(text=f"Atualizado {now.strftime('%d/%m/%Y %H:%M')} UTC")
        await self._post(guild, "dashboard-mediadores", [e])

    # ── Dashboard de Jogadores (#ranking) ─────
    async def _players(self, guild: discord.Guild):
        col   = db.get_collection("matches")
        now   = utcnow()
        since = now - timedelta(days=30)

        top = await col.aggregate([
            {"$match": {"created_at": {"$gte": since}}},
            {"$unwind": "$player_ids"},
            {"$group": {
                "_id":   "$player_ids",
                "total": {"$sum": 1},
                "wins":  {"$sum": {"$cond": [{"$eq": ["$winner_id","$player_ids"]}, 1, 0]}},
                "vol":   {"$sum": "$bet_value"}
            }},
            {"$sort": {"total": -1}}, {"$limit": 10}
        ]).to_list(10)

        e = discord.Embed(title="Top Jogadores — Últimos 30 dias", color=THEME)
        medals = ["🥇","🥈","🥉"]
        if not top:
            e.description = "Nenhuma partida disputada ainda."
        else:
            lines = []
            for i, p in enumerate(top):
                icon = medals[i] if i < 3 else f"`{i+1}.`"
                wr   = _pct(p["wins"], p["total"])
                lines.append(
                    f"{icon} <@{p['_id']}> — `{p['total']}` partidas | WR:`{wr}` | {_brl(p.get('vol',0))}"
                )
            e.description = "\n".join(lines)
        e.add_field(name="Jogadores ativos (30d)", value=f"`{len(top)}`", inline=True)
        e.set_footer(text=f"Atualizado {now.strftime('%d/%m/%Y %H:%M')} UTC")
        await self._post(guild, "ranking", [e])

    # ── Dashboard de Suporte ──────────────────
    async def _support(self, guild: discord.Guild):
        col   = db.get_collection("tickets")
        now   = utcnow()
        since = now - timedelta(days=30)

        total    = await col.count_documents({"created_at": {"$gte": since}})
        abertos  = await col.count_documents({"status": "aberto"})
        atend    = await col.count_documents({"status": "pendente"})
        fechados = await col.count_documents({
            "created_at": {"$gte": since},
            "status": {"$in": ["resolvido","fechado"]}
        })

        cats = await col.aggregate([
            {"$match": {"created_at": {"$gte": since}}},
            {"$group": {"_id": "$categoria", "c": {"$sum": 1}}},
            {"$sort": {"c": -1}}, {"$limit": 6}
        ]).to_list(6)

        agents = await col.aggregate([
            {"$match": {"created_at": {"$gte": since}, "atendente_id": {"$ne": None}}},
            {"$group": {
                "_id":   "$atendente_id",
                "res":   {"$sum": {"$cond": [{"$in": ["$status",["resolvido","fechado"]]}, 1, 0]}},
                "total": {"$sum": 1}
            }},
            {"$sort": {"res": -1}}, {"$limit": 5}
        ]).to_list(5)

        e = discord.Embed(title="Suporte — Últimos 30 dias", color=THEME2)
        e.add_field(name="Abertos no período", value=f"`{total}`",                              inline=True)
        e.add_field(name="Em aberto agora",    value=f"`{abertos}`",                            inline=True)
        e.add_field(name="Em atendimento",     value=f"`{atend}`",                              inline=True)
        e.add_field(name="Resolvidos",         value=f"`{fechados}` ({_pct(fechados,total)})",  inline=True)
        if cats:
            e.add_field(name="Por categoria",
                value="\n".join(f"`{c['_id'] or '?'}` — {c['c']}" for c in cats), inline=True)
        if agents:
            e.add_field(name="Por atendente",
                value="\n".join(
                    f"<@{a['_id']}> — `{a['res']}` res / `{a['total']}` total"
                    for a in agents),
                inline=False)
        e.set_footer(text=f"Atualizado {now.strftime('%d/%m/%Y %H:%M')} UTC")
        await self._post(guild, "dashboard-suporte", [e])

    # ── Dashboard do Servidor (#status-bot) ───
    async def _server(self, guild: discord.Guild):
        now   = utcnow()
        users = db.get_collection("users")

        total_db = await users.count_documents({})
        accepted = await users.count_documents({"rules_accepted": True})
        blocked  = await users.count_documents({"spam_blocked": True})
        novos_7  = await users.count_documents({"joined_at": {"$gte": now - timedelta(days=7)}})
        novos_30 = await users.count_documents({"joined_at": {"$gte": now - timedelta(days=30)}})

        e = discord.Embed(title="Status do Servidor", color=GREEN)
        e.add_field(name="Bot",             value="🟢 Online",                                 inline=True)
        e.add_field(name="Banco",           value="🟢 Conectado",                              inline=True)
        e.add_field(name="Membros Discord", value=f"`{guild.member_count}`",                   inline=True)
        e.add_field(name="Cadastrados",     value=f"`{total_db}`",                             inline=True)
        e.add_field(name="Onboarding OK",   value=f"`{accepted}` ({_pct(accepted,total_db)})", inline=True)
        e.add_field(name="Bloqueados",      value=f"`{blocked}`",                              inline=True)
        e.add_field(name="Novos (7 dias)",  value=f"`{novos_7}`",                              inline=True)
        e.add_field(name="Novos (30 dias)", value=f"`{novos_30}`",                             inline=True)
        e.set_footer(text=f"Atualizado {now.strftime('%d/%m/%Y %H:%M')} UTC")
        await self._post(guild, "status-bot", [e])

    # ── Dashboard de Influencers ──────────────
    async def _influencers(self, guild: discord.Guild):
        now = utcnow()
        col = db.get_collection("influencers")
        inv = db.get_collection("invite_joins")
        mat = db.get_collection("matches")

        infs = await col.find({"is_active": True}).to_list(None)
        if not infs:
            return

        rows = []
        for inf in infs:
            members = await inv.find({
                "guild_id":    str(guild.id),
                "invite_code": inf.get("invite_code")
            }).to_list(None)
            mids        = [m["member_id"] for m in members]
            match_count = 0
            for mid in mids:
                match_count += await mat.count_documents({
                    "player_ids": mid,
                    "status":     "finalizado"
                })
            rows.append({
                "username":   inf.get("username", "?"),
                "members":    len(mids),
                "matches":    match_count,
                "commission": len(mids) * inf.get("commission_per_member", 2.0),
            })
        rows.sort(key=lambda x: x["members"], reverse=True)

        e = discord.Embed(title="Influencers", color=THEME)
        medals = ["🥇","🥈","🥉"]
        lines  = []
        for i, r in enumerate(rows[:10]):
            icon = medals[i] if i < 3 else f"`{i+1}.`"
            lines.append(
                f"{icon} **{r['username']}** — `{r['members']}` membros "
                f"| `{r['matches']}` partidas | {_brl(r['commission'])}"
            )
        e.description = "\n".join(lines) if lines else "Nenhum influencer ativo."
        total_comm = sum(r["commission"] for r in rows)
        e.add_field(name="Comissão total acumulada", value=f"**{_brl(total_comm)}**", inline=False)
        e.set_footer(text=f"Atualizado {now.strftime('%d/%m/%Y %H:%M')} UTC")
        await self._post(guild, "dashboard-influencers", [e])


analytics_service = AnalyticsService()