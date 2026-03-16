from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any

import discord

from config.database import db
from services.mediator_queue import mediator_queue
from services.match_queue_service import match_queue_service
from utils.logger import logger


# ─── Tempo de início do bot ──────────────────────────────────────────────────

_bot_start_time: Optional[datetime] = None


def set_bot_start_time(dt: datetime) -> None:
    global _bot_start_time
    _bot_start_time = dt


def _uptime_seconds() -> float:
    if _bot_start_time:
        return (datetime.now(timezone.utc) - _bot_start_time).total_seconds()
    return 0.0


# ─── Estruturas de dados ─────────────────────────────────────────────────────

@dataclass
class CategoryHealth:
    name:   str
    score:  float
    status: str
    kpis:   Dict[str, Any] = field(default_factory=dict)
    alerts: list[str]      = field(default_factory=list)


@dataclass
class HealthReport:
    timestamp:      datetime
    overall_score:  float
    overall_status: str
    categories:     Dict[str, CategoryHealth]
    uptime_seconds: float


# ─── Serviço principal ───────────────────────────────────────────────────────

class HealthCheckService:

    WEIGHTS = {
        "infra":      0.30,
        "threads":    0.20,
        "partidas":   0.20,
        "mediadores": 0.15,
        "spam":       0.10,
        "suporte":    0.05,
    }

    POOL_LOW_THRESHOLD    = 5
    MARGEM_WARN_THRESHOLD = 200
    MARGEM_CRIT_THRESHOLD = 100

    def __init__(self, bot: discord.Client):
        self.bot = bot

    @staticmethod
    def _status(score: float) -> str:
        if score >= 80:
            return "ok"
        if score >= 50:
            return "warning"
        return "critical"

    # ── Infraestrutura ────────────────────────────────────────────────────────

    async def check_infra(self) -> CategoryHealth:
        kpis:   Dict[str, Any] = {}
        alerts: list[str]      = []
        score                  = 100.0

        try:
            start  = datetime.now(timezone.utc)
            col    = db.get_collection("matches")
            await col.find_one({}, {"_id": 1})
            lat_ms = (datetime.now(timezone.utc) - start).total_seconds() * 1000
            kpis["mongo_connected"]  = True
            kpis["mongo_latency_ms"] = round(lat_ms, 1)
            if lat_ms > 500:
                score -= 40
                alerts.append("MongoDB lento (>500 ms)")
            elif lat_ms > 100:
                score -= 15
                alerts.append("MongoDB com latência elevada (>100 ms)")
        except Exception as exc:
            kpis["mongo_connected"]  = False
            kpis["mongo_latency_ms"] = -1
            score -= 50
            alerts.append(f"MongoDB indisponível: {exc}")

        gw_ms = round(self.bot.latency * 1000, 1)
        kpis["gateway_ms"] = gw_ms
        if gw_ms > 500:
            score -= 30
            alerts.append("Gateway Discord lento (>500 ms)")
        elif gw_ms > 200:
            score -= 10
            alerts.append("Gateway Discord com latência elevada (>200 ms)")

        kpis["uptime_seconds"] = _uptime_seconds()

        score = max(0.0, min(100.0, score))
        return CategoryHealth("infra", score, self._status(score), kpis, alerts)

    # ── Threads ───────────────────────────────────────────────────────────────

    async def check_threads(self, guild: discord.Guild) -> CategoryHealth:
        from services.thread_reuse_service import thread_reuse_service as trs
        kpis:   Dict[str, Any] = {}
        alerts: list[str]      = []
        score                  = 100.0

        kpis["reuse_service_ok"] = trs is not None
        if not trs:
            score -= 50
            alerts.append("ThreadReuseService não inicializado")
            return CategoryHealth(
                "threads", max(0.0, score), self._status(max(0.0, score)), kpis, alerts)

        try:
            health = await trs.get_health(guild)
            kpis["pool_total"]      = health.get("pool_total", 0)
            kpis["active_matches"]  = health.get("active_matches", 0)
            kpis["live_discord"]    = health.get("live_discord", 0)
            kpis["margem"]          = health.get("margem", 0)
            kpis["pool_by_channel"] = health.get("pool_by_channel", {})

            if kpis["pool_total"] == 0:
                score -= 30
                alerts.append("Pool vazio — rode /thread_pool preaquecer")
            elif kpis["pool_total"] < self.POOL_LOW_THRESHOLD:
                score -= 15
                alerts.append(f"Pool baixo ({kpis['pool_total']} threads disponíveis)")

            if kpis["margem"] < self.MARGEM_CRIT_THRESHOLD:
                score -= 40
                alerts.append(f"🔴 CRÍTICO — apenas {kpis['margem']} slots de thread disponíveis!")
            elif kpis["margem"] < self.MARGEM_WARN_THRESHOLD:
                score -= 20
                alerts.append(f"Margem baixa ({kpis['margem']} slots livres)")

        except Exception as exc:
            score -= 30
            alerts.append(f"Erro ao verificar threads: {exc}")

        score = max(0.0, min(100.0, score))
        return CategoryHealth("threads", score, self._status(score), kpis, alerts)

    # ── Partidas ──────────────────────────────────────────────────────────────

    async def check_partidas(self) -> CategoryHealth:
        kpis:   Dict[str, Any] = {}
        alerts: list[str]      = []
        score                  = 100.0

        try:
            col             = db.get_collection("matches")
            active_statuses = [
                "aguardando_pagamento", "aguardando_inicio",
                "em_andamento", "aguardando_premio",
            ]

            kpis["ativas"] = await col.count_documents(
                {"status": {"$in": active_statuses}})

            threshold      = datetime.now(timezone.utc) - timedelta(minutes=30)
            kpis["presas"] = await col.count_documents({
                "status":     {"$in": ["aguardando_pagamento", "aguardando_inicio"]},
                "updated_at": {"$lt": threshold},
            })
            if kpis["presas"] > 0:
                score -= min(40, kpis["presas"] * 15)
                alerts.append(f"{kpis['presas']} partida(s) presa(s) há mais de 30 min")

            kpis["sem_mediador"] = await col.count_documents({
                "status":      {"$in": active_statuses},
                "mediator_id": None,
            })
            if kpis["sem_mediador"] > 0:
                score -= min(30, kpis["sem_mediador"] * 10)
                alerts.append(f"{kpis['sem_mediador']} partida(s) sem mediador")

            kpis["filas_ativas"] = len(match_queue_service.active_queues)

            today = datetime.now(timezone.utc).replace(
                hour=0, minute=0, second=0, microsecond=0)
            kpis["finalizadas_hoje"] = await col.count_documents({
                "status": "finalizado", "updated_at": {"$gte": today}})
            kpis["canceladas_hoje"] = await col.count_documents({
                "status": "cancelado", "updated_at": {"$gte": today}})

            week_ago = datetime.now(timezone.utc) - timedelta(days=7)
            total_7d = await col.count_documents({"created_at": {"$gte": week_ago}})
            fin_7d   = await col.count_documents({
                "status": "finalizado", "created_at": {"$gte": week_ago}})
            kpis["taxa_conclusao_7d"] = round(
                (fin_7d / total_7d * 100) if total_7d > 0 else 100.0, 1)

        except Exception as exc:
            score -= 30
            alerts.append(f"Erro ao verificar partidas: {exc}")

        score = max(0.0, min(100.0, score))
        return CategoryHealth("partidas", score, self._status(score), kpis, alerts)

    # ── Mediadores ────────────────────────────────────────────────────────────

    async def check_mediadores(self) -> CategoryHealth:
        kpis:   Dict[str, Any] = {}
        alerts: list[str]      = []
        score                  = 100.0

        try:
            stats          = await mediator_queue.get_queue_stats()
            mediators_list = stats.get("mediators") or []
            kpis["total_ativos"]  = stats.get("total_active", 0)
            disponiveis           = sum(1 for m in mediators_list if m.get("can_mediate"))
            kpis["disponiveis"]   = disponiveis
            kpis["em_rate_limit"] = kpis["total_ativos"] - disponiveis

            if disponiveis == 0:
                score -= 60
                alerts.append(
                    "CRÍTICO: Nenhum mediador disponível — partidas não podem iniciar!")
            elif disponiveis < 2:
                score -= 25
                alerts.append(f"Apenas {disponiveis} mediador(es) disponível(is)")

            try:
                from services.mediador_dashboard_service import mediator_dashboard_service
                task = getattr(mediator_dashboard_service, "daily_update", None)
                kpis["daily_task_ok"] = task.is_running() if task else False
                if not kpis["daily_task_ok"]:
                    score -= 20
                    alerts.append("Daily-update task do dashboard parada")
            except Exception:
                kpis["daily_task_ok"] = False

            if mediators_list:
                ml = max(
                    mediators_list,
                    key=lambda m: m.get("matches_in_last_8_min", 0),
                    default=None,
                )
                if ml:
                    kpis["mais_sobrecarregado"] = {
                        "username":     ml.get("username"),
                        "matches_8min": ml.get("matches_in_last_8_min", 0),
                    }

        except Exception as exc:
            score -= 30
            alerts.append(f"Erro ao verificar mediadores: {exc}")

        score = max(0.0, min(100.0, score))
        return CategoryHealth("mediadores", score, self._status(score), kpis, alerts)

    # ── Spam & Onboarding ─────────────────────────────────────────────────────

    async def check_spam(
        self,
        guild:          discord.Guild,
        anti_spam_svc = None,
        onboarding_svc= None,
    ) -> CategoryHealth:
        from services.channel_service import SPAM_BLOCK_ROLE_NAME

        # ← auto-resolve singletons quando não passados
        if anti_spam_svc is None:
            try:
                from services.anti_spam_service import anti_spam_service
                anti_spam_svc = anti_spam_service
            except Exception:
                pass

        if onboarding_svc is None:
            try:
                onboarding_svc = getattr(self.bot, "_onboarding_service", None)
            except Exception:
                pass

        kpis:   Dict[str, Any] = {}
        alerts: list[str]      = []
        score                  = 100.0

        kpis["anti_spam_ok"]  = anti_spam_svc is not None
        kpis["onboarding_ok"] = onboarding_svc is not None

        if not anti_spam_svc:
            score -= 40
            alerts.append("AntiSpamService não inicializado")
        if not onboarding_svc:
            score -= 30
            alerts.append("OnboardingService não inicializado")

        spam_role = discord.utils.get(guild.roles, name=SPAM_BLOCK_ROLE_NAME)
        kpis["cargo_bloqueio_existe"] = spam_role is not None
        if not spam_role:
            score -= 15
            alerts.append(f"Cargo '{SPAM_BLOCK_ROLE_NAME}' não encontrado")
        else:
            kpis["bloqueados_ativos"] = sum(
                1 for m in guild.members if spam_role in m.roles)

        kpis["persistent_views"] = len(self.bot.persistent_views)
        if kpis["persistent_views"] < 4:
            score -= 15
            alerts.append(
                f"Views persistentes: {kpis['persistent_views']}/4 registradas")

        try:
            col     = db.get_collection("users")
            total   = await col.count_documents({})
            aceitos = await col.count_documents({"onboarding_result": "aceito"})
            kpis["total_users"]    = total
            kpis["taxa_aceitacao"] = round(
                (aceitos / total * 100) if total > 0 else 0.0, 1)
        except Exception as exc:
            alerts.append(f"Erro ao buscar stats de onboarding: {exc}")

        score = max(0.0, min(100.0, score))
        return CategoryHealth("spam", score, self._status(score), kpis, alerts)

    # ── Suporte ───────────────────────────────────────────────────────────────

    async def check_suporte(self, guild: discord.Guild) -> CategoryHealth:
        from services.channel_service import CHAMADOS_CHANNEL_NAME, SUPPORT_CHANNEL_NAME
        kpis:   Dict[str, Any] = {}
        alerts: list[str]      = []
        score                  = 100.0

        try:
            col = db.get_collection("tickets")

            kpis["abertos"]       = await col.count_documents({"status": "aberto"})
            kpis["sem_atendente"] = await col.count_documents(
                {"status": "aberto", "attendant_id": None})

            if kpis["sem_atendente"] > 0:
                score -= min(30, kpis["sem_atendente"] * 10)
                alerts.append(f"{kpis['sem_atendente']} chamado(s) sem atendente")
            if kpis["abertos"] > 10:
                score -= 20
                alerts.append(f"Muitos chamados abertos ({kpis['abertos']})")

            today = datetime.now(timezone.utc).replace(
                hour=0, minute=0, second=0, microsecond=0)
            kpis["concluidos_hoje"] = await col.count_documents({
                "status": "concluido", "updated_at": {"$gte": today}})

            canais_ok = all([
                discord.utils.get(guild.text_channels, name=CHAMADOS_CHANNEL_NAME),
                discord.utils.get(guild.text_channels, name=SUPPORT_CHANNEL_NAME),
            ])
            kpis["canais_ok"] = canais_ok
            if not canais_ok:
                score -= 25
                alerts.append("Canal(is) de suporte ausente(s)")

        except Exception as exc:
            score -= 20
            alerts.append(f"Erro ao verificar suporte: {exc}")

        score = max(0.0, min(100.0, score))
        return CategoryHealth("suporte", score, self._status(score), kpis, alerts)

    # ── Runner principal ──────────────────────────────────────────────────────

    async def run_check(
        self,
        guild:          discord.Guild,
        anti_spam_svc = None,
        onboarding_svc= None,
    ) -> HealthReport:
        # ← resolve singletons uma vez aqui — passa adiante para check_spam
        if anti_spam_svc is None:
            try:
                from services.anti_spam_service import anti_spam_service
                anti_spam_svc = anti_spam_service
            except Exception:
                pass

        if onboarding_svc is None:
            onboarding_svc = getattr(self.bot, "_onboarding_service", None)

        categories: Dict[str, CategoryHealth] = {
            "infra":      await self.check_infra(),
            "threads":    await self.check_threads(guild),
            "partidas":   await self.check_partidas(),
            "mediadores": await self.check_mediadores(),
            "spam":       await self.check_spam(guild, anti_spam_svc, onboarding_svc),
            "suporte":    await self.check_suporte(guild),
        }

        overall = sum(
            categories[k].score * w
            for k, w in self.WEIGHTS.items()
            if k in categories
        )
        overall_status = (
            "ok" if overall >= 80 else ("warning" if overall >= 50 else "critical"))

        return HealthReport(
            timestamp      = datetime.now(timezone.utc),
            overall_score  = round(overall, 1),
            overall_status = overall_status,
            categories     = categories,
            uptime_seconds = _uptime_seconds(),
        )

    # ← alias para compatibilidade com chamadas legadas de run()
    run = run_check


# ─── Singleton ───────────────────────────────────────────────────────────────

health_check_service: Optional[HealthCheckService] = None


def init_health_check_service(bot: discord.Client) -> HealthCheckService:
    global health_check_service
    health_check_service = HealthCheckService(bot)
    return health_check_service
