"""
R6 — Rate limit handler + retry com exponential backoff.
Uso:
    @with_retry(attempts=3, backoff=2.0)
    async def enviar_mensagem(channel, text):
        await channel.send(text)
"""
import asyncio
import functools
import logging
from typing import Callable, TypeVar

import discord

logger = logging.getLogger("MediatorSystem")
F = TypeVar("F")

_rate_limit_callbacks: list[Callable] = []


def on_rate_limit(callback: Callable):
    """Registra callback chamado quando rate limit ocorre (F2 — Monitor)."""
    _rate_limit_callbacks.append(callback)
    return callback


async def _notify_rate_limit(endpoint: str, retry_after: float, context: str = ""):
    for cb in _rate_limit_callbacks:
        try:
            await cb(endpoint=endpoint, retry_after=retry_after, context=context)
        except Exception as e:
            logger.warning(f"[RateLimitCallback] Erro: {e}")


def with_retry(attempts: int = 3, backoff: float = 2.0, reraise: bool = True):
    """
    Decorator de retry com backoff exponencial para chamadas Discord.
    - Trata discord.HTTPException 429 (rate limit)
    - Trata discord.HTTPException 5xx (erros transitórios do servidor)
    - Loga e notifica callbacks de monitoramento (F2)
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            for attempt in range(1, attempts + 1):
                try:
                    return await func(*args, **kwargs)

                except discord.RateLimited as e:
                    wait = e.retry_after + 0.5
                    logger.warning(
                        f"[RateLimit] {func.__name__} — aguardando {wait:.1f}s "
                        f"(tentativa {attempt}/{attempts})"
                    )
                    await _notify_rate_limit(
                        endpoint=func.__name__,
                        retry_after=wait,
                        context=f"tentativa {attempt}"
                    )
                    if attempt < attempts:
                        await asyncio.sleep(wait)
                    elif reraise:
                        raise

                except discord.HTTPException as e:
                    if e.status == 429:
                        wait = backoff ** attempt
                        logger.warning(
                            f"[HTTP429] {func.__name__} — backoff {wait:.1f}s "
                            f"(tentativa {attempt}/{attempts})"
                        )
                        await _notify_rate_limit(
                            endpoint=func.__name__,
                            retry_after=wait,
                            context=f"HTTP 429 tentativa {attempt}"
                        )
                        if attempt < attempts:
                            await asyncio.sleep(wait)
                        elif reraise:
                            raise
                    elif e.status >= 500:
                        wait = backoff ** attempt
                        logger.warning(
                            f"[HTTP{e.status}] {func.__name__} — server error, "
                            f"aguardando {wait:.1f}s (tentativa {attempt}/{attempts})"
                        )
                        if attempt < attempts:
                            await asyncio.sleep(wait)
                        elif reraise:
                            raise
                    else:
                        raise

                except Exception:
                    raise

        return wrapper
    return decorator


async def safe_send(channel, *args, **kwargs) -> discord.Message | None:
    """Envia mensagem com retry automático — utilitário direto."""
    @with_retry(attempts=3, backoff=2.0, reraise=False)
    async def _send():
        return await channel.send(*args, **kwargs)
    return await _send()


async def safe_edit(message: discord.Message, **kwargs) -> discord.Message | None:
    """Edita mensagem com retry automático."""
    @with_retry(attempts=3, backoff=2.0, reraise=False)
    async def _edit():
        return await message.edit(**kwargs)
    return await _edit()
