"""
circuit_breaker.py — Proteção de chamadas ao MongoDB.

Estados:
  CLOSED     → operação normal, todas as chamadas passam.
  OPEN       → DB falhou muito, chamadas bloqueadas por `recovery_timeout` segundos.
  HALF_OPEN  → após timeout, testa 1 chamada; se OK → CLOSED, senão → OPEN.

Uso:
    from utils.circuit_breaker import db_circuit_breaker

    async def minha_func():
        async with db_circuit_breaker:
            result = await collection.find_one(...)
"""
from __future__ import annotations
import asyncio
from enum import Enum
from datetime import datetime, timezone
from typing import Optional, Callable
from utils.logger import logger


class CircuitState(Enum):
    CLOSED    = "closed"
    OPEN      = "open"
    HALF_OPEN = "half_open"


class CircuitBreakerOpenError(Exception):
    """Levantado quando o circuit breaker está OPEN."""
    pass


class CircuitBreaker:
    """
    Circuit breaker assíncrono para proteger chamadas ao MongoDB.

    Parâmetros:
        name              → nome para identificar no log/alertas
        failure_threshold → nº de falhas consecutivas para abrir o circuito (default: 5)
        recovery_timeout  → segundos em OPEN antes de tentar HALF_OPEN (default: 60)
        expected_errors   → tupla de exceções que contam como falha (default: Exception)
        alert_channel     → nome do canal Discord para notificar (default: alertas-adm)
    """

    def __init__(
        self,
        name: str = "db",
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_errors: tuple = (Exception,),
        alert_channel: str = "alertas-adm",
    ):
        self.name              = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout  = recovery_timeout
        self.expected_errors   = expected_errors
        self.alert_channel     = alert_channel

        self._state          = CircuitState.CLOSED
        self._failure_count  = 0
        self._last_failure   : Optional[datetime] = None
        self._lock           = asyncio.Lock()
        self._bot            = None   # injetado pelo on_ready via set_bot()

    # ── Propriedades ───────────────────────────────────────────

    @property
    def state(self) -> CircuitState:
        return self._state

    @property
    def is_open(self) -> bool:
        return self._state == CircuitState.OPEN

    @property
    def is_closed(self) -> bool:
        return self._state == CircuitState.CLOSED

    # ── Context manager ────────────────────────────────────────

    async def __aenter__(self):
        await self._before_call()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            await self._on_success()
            return False
        if issubclass(exc_type, self.expected_errors):
            await self._on_failure(exc_val)
            return False   # propaga a exceção original
        return False

    # ── Lógica central ─────────────────────────────────────────

    async def _before_call(self):
        async with self._lock:
            if self._state == CircuitState.CLOSED:
                return

            if self._state == CircuitState.OPEN:
                elapsed = (datetime.now(timezone.utc) - self._last_failure).total_seconds()
                if elapsed >= self.recovery_timeout:
                    logger.info(f"[CircuitBreaker:{self.name}] OPEN → HALF_OPEN (testando reconexão)")
                    self._state = CircuitState.HALF_OPEN
                else:
                    raise CircuitBreakerOpenError(
                        f"Circuit breaker '{self.name}' aberto. "
                        f"Tente novamente em {self.recovery_timeout - elapsed:.0f}s."
                    )

            # HALF_OPEN: deixa passar apenas 1 chamada de teste (sem lock adicional)

    async def _on_success(self):
        async with self._lock:
            if self._state in (CircuitState.HALF_OPEN, CircuitState.OPEN):
                logger.info(f"[CircuitBreaker:{self.name}] Reconexão bem-sucedida → CLOSED")
                await self._notify_recovery()
            self._state         = CircuitState.CLOSED
            self._failure_count = 0
            self._last_failure  = None

    async def _on_failure(self, exc: Exception):
        async with self._lock:
            self._failure_count += 1
            self._last_failure   = datetime.now(timezone.utc)

            if self._state == CircuitState.HALF_OPEN:
                logger.warning(
                    f"[CircuitBreaker:{self.name}] HALF_OPEN falhou → voltando para OPEN"
                )
                self._state = CircuitState.OPEN
                await self._notify_open(exc)
                return

            if (
                self._state == CircuitState.CLOSED
                and self._failure_count >= self.failure_threshold
            ):
                logger.error(
                    f"[CircuitBreaker:{self.name}] {self._failure_count} falhas → OPEN"
                )
                self._state = CircuitState.OPEN
                await self._notify_open(exc)

    # ── Notificações Discord ───────────────────────────────────

    def set_bot(self, bot):
        """Injeta o bot para poder notificar em #alertas-adm."""
        self._bot = bot

    async def _notify_open(self, exc: Exception):
        """Posta embed vermelho em #alertas-adm quando o circuito abre."""
        if not self._bot:
            return
        try:
            import discord
            from utils.datetime_utils import utcnow
            for guild in self._bot.guilds:
                ch = discord.utils.get(guild.text_channels, name=self.alert_channel)
                if ch:
                    embed = discord.Embed(
                        title=f"🔴 Circuit Breaker ABERTO — `{self.name}`",
                        description=(
                            f"**{self._failure_count} falhas consecutivas** detectadas.\n"
                            f"Chamadas ao `{self.name}` estão **bloqueadas** por "
                            f"`{self.recovery_timeout}s`.\n\n"
                            f"**Erro:** ```{exc}```"
                        ),
                        color=0xE74C3C,
                        timestamp=utcnow(),
                    )
                    embed.set_footer(text="Circuit Breaker · X1 Frifas")
                    await ch.send(embed=embed)
        except Exception as e:
            logger.warning(f"[CircuitBreaker] Falha ao notificar abertura: {e}")

    async def _notify_recovery(self):
        """Posta embed verde em #alertas-adm quando o circuito fecha."""
        if not self._bot:
            return
        try:
            import discord
            from utils.datetime_utils import utcnow
            for guild in self._bot.guilds:
                ch = discord.utils.get(guild.text_channels, name=self.alert_channel)
                if ch:
                    embed = discord.Embed(
                        title=f"🟢 Circuit Breaker RECUPERADO — `{self.name}`",
                        description=(
                            f"Conexão com `{self.name}` restaurada.\n"
                            f"Chamadas voltando ao normal."
                        ),
                        color=0x2ECC71,
                        timestamp=utcnow(),
                    )
                    embed.set_footer(text="Circuit Breaker · X1 Frifas")
                    await ch.send(embed=embed)
        except Exception as e:
            logger.warning(f"[CircuitBreaker] Falha ao notificar recuperação: {e}")

    # ── Execução direta (alternativa ao context manager) ───────

    async def call(self, coro_func: Callable, *args, **kwargs):
        """
        Executa uma coroutine protegida pelo circuit breaker.

        Exemplo:
            result = await db_circuit_breaker.call(collection.find_one, {"_id": id})
        """
        async with self:
            return await coro_func(*args, **kwargs)

    def __repr__(self) -> str:
        return (
            f"<CircuitBreaker name={self.name!r} state={self._state.value} "
            f"failures={self._failure_count}/{self.failure_threshold}>"
        )


# ── Instância global — importada pelos services ────────────────
db_circuit_breaker = CircuitBreaker(
    name="mongodb",
    failure_threshold=5,
    recovery_timeout=60,
    alert_channel="alertas-adm",
)
