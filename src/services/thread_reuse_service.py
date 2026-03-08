# services/thread_reuse_service.py

"""
Sistema de reuso de threads Discord para evitar o limite de 1.000 threads ativas.

Fluxo:
  1. Partida começa  → get_or_create_thread()   → busca thread arquivada no pool
                                                  → se não tem, cria nova + arquiva
  2. Partida termina → return_to_pool_after_match() → limpa + arquiva → salva no pool
  3. Partida expira  → return_to_pool_empty()        → limpa + arquiva → salva no pool
  4. ADM             → preaquecer()              → cria N threads arquivadas
  5. ADM             → validate_pool()           → remove entradas inválidas do banco
  6. ADM             → get_health()              → mostra margem do limite Discord
"""

import asyncio
import discord
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from config.database import db
from utils.logger import logger


# Limite de threads ATIVAS do Discord por servidor
DISCORD_THREAD_LIMIT = 1000

# Margem de segurança — nunca ultrapassar esse número de ativas
SAFE_ACTIVE_LIMIT = 900

# Nome sentinela usado em threads do pool
POOL_THREAD_NAME = "♻️ aguardando-partida"

# Tempo (segundos) de espera após fechar partida antes de devolver ao pool
POOL_RETURN_DELAY = 15


class ThreadReuseService:

    def __init__(self, bot: discord.Client):
        self.bot = bot

    # ─────────────────────────────────────────────
    # API pública — usada por match_queue_service
    # ─────────────────────────────────────────────

    async def get_or_create_thread(
        self,
        channel: discord.TextChannel,
        thread_name: str,
        player_ids: List[int],
        guild: discord.Guild,
    ) -> Optional[discord.Thread]:
        """
        Retorna uma thread disponível do pool (arquivada) ou cria uma nova.
        Adiciona os jogadores automaticamente.
        """
        try:
            # 1. Tenta reusar do pool
            thread = await self._get_from_pool(channel)

            if thread:
                async def _clean_and_archive(self, thread: discord.Thread, reason: str = ""):
                    try:
                        # ── NOVO: busca match vinculado e arquiva o log ────
                        col = db.get_collection("active_threads")
                        doc = await col.find_one({"thread_id": thread.id})
                        if doc and doc.get("match_id"):
                            match_col = db.get_collection("matches")
                            from bson import ObjectId
                            match = await match_col.find_one({"_id": ObjectId(doc["match_id"])})
                            if match:
                                from services.thread_log_service import get_thread_log_service
                                log_svc = get_thread_log_service()
                                if log_svc:
                                    await log_svc.archive_thread(thread, match)

                        await self._unmark_active(thread)

                        try:
                            await thread.edit(name=POOL_THREAD_NAME, archived=False)
                            await asyncio.sleep(0.5)
                            await thread.edit(archived=True)
                        except discord.HTTPException as e:
                            logger.warning(f"[ThreadPool] Falha ao arquivar thread {thread.id}: {e}")
                            return

                        parent = thread.parent
                        if parent and isinstance(parent, discord.TextChannel):
                            await self._save_to_pool(thread, parent)
                            logger.info(f"[ThreadPool] Thread {thread.id} devolvida ao pool ({reason})")

                    except Exception as e:
                        logger.error(f"[ThreadPool] _clean_and_archive erro: {e}", exc_info=True)
                # Desarquiva e renomeia
                try:
                    await thread.edit(archived=False, name=thread_name[:100])
                    logger.info(f"[ThreadPool] Reusando thread #{thread.id} em #{channel.name}")
                except discord.HTTPException as e:
                    logger.warning(f"[ThreadPool] Falha ao reativar thread do pool: {e}")
                    thread = None

            if not thread:
                # 2. Verifica margem antes de criar
                live = await self._count_live_threads(guild)
                if live >= SAFE_ACTIVE_LIMIT:
                    logger.error(
                        f"[ThreadPool] Limite seguro atingido ({live}/{SAFE_ACTIVE_LIMIT}). "
                        f"Não é possível criar nova thread em #{channel.name}."
                    )
                    return None

                thread = await channel.create_thread(
                    name=thread_name[:100],
                    type=discord.ChannelType.public_thread,
                    auto_archive_duration=60,
                )
                logger.info(f"[ThreadPool] Nova thread criada: #{thread.id} em #{channel.name}")

            # Adiciona jogadores
            for uid in player_ids:
                member = guild.get_member(uid)
                if member:
                    try:
                        await thread.add_user(member)
                    except Exception:
                        pass

            # Registra como ativa no banco
            await self._mark_active(thread, channel)
            return thread

        except Exception as e:
            logger.error(f"[ThreadPool] get_or_create_thread erro: {e}", exc_info=True)
            return None

    async def return_to_pool_after_match(self, thread: discord.Thread):
        """
        Chamado após partida finalizada (prize confirmado).
        Aguarda POOL_RETURN_DELAY, limpa mensagens recentes do bot e arquiva.
        """
        await asyncio.sleep(POOL_RETURN_DELAY)
        await self._clean_and_archive(thread, reason="match_finalizado")

    async def return_to_pool_empty(self, thread: discord.Thread):
        """
        Chamado após expiração/recusa de confirmação.
        Limpa e arquiva imediatamente (sem delay).
        """
        await self._clean_and_archive(thread, reason="queue_expirada")

    async def update_active_thread_match(self, thread_id: int, match_id: str):
        """Vincula match_id ao registro ativo do banco."""
        try:
            col = db.get_collection("active_threads")
            await col.update_one(
                {"thread_id": thread_id},
                {"$set": {"match_id": match_id, "updated_at": datetime.utcnow()}},
            )
        except Exception as e:
            logger.warning(f"[ThreadPool] update_active_thread_match erro: {e}")

    # ─────────────────────────────────────────────
    # Pré-aquecimento / Validação
    # ─────────────────────────────────────────────

    async def preaquecer(self, channel: discord.TextChannel, quantidade: int = 3) -> int:
        """
        Cria `quantidade` threads no canal, arquiva imediatamente e salva no pool.
        Retorna quantas foram criadas com sucesso.
        """
        criadas = 0
        for _ in range(quantidade):
            try:
                thread = await channel.create_thread(
                    name=POOL_THREAD_NAME,
                    type=discord.ChannelType.public_thread,
                    auto_archive_duration=60,
                )
                await asyncio.sleep(1)  # evita rate-limit
                await thread.edit(archived=True)
                await self._save_to_pool(thread, channel)
                criadas += 1
                logger.info(f"[ThreadPool] Pré-aquecida thread {thread.id} em #{channel.name}")
            except discord.HTTPException as e:
                logger.warning(f"[ThreadPool] Falha ao pré-aquecer: {e}")
                break
            except Exception as e:
                logger.error(f"[ThreadPool] Erro inesperado no pré-aquecimento: {e}")
                break

        return criadas

    async def validate_pool(self, guild: discord.Guild) -> Dict[str, int]:
        """
        Percorre o pool no banco e remove entradas cujas threads não existem
        mais ou não estão arquivadas. Retorna contagem de válidas e removidas.
        """
        col    = db.get_collection("thread_pool")
        cursor = col.find({})
        docs   = await cursor.to_list(length=None)

        valid   = 0
        removed = 0

        for doc in docs:
            thread_id  = doc.get("thread_id")
            channel_id = doc.get("channel_id")
            if not thread_id or not channel_id:
                await col.delete_one({"_id": doc["_id"]})
                removed += 1
                continue

            channel = guild.get_channel(int(channel_id))
            if not channel:
                await col.delete_one({"_id": doc["_id"]})
                removed += 1
                continue

            # Tenta buscar a thread
            thread = None
            try:
                thread = await guild.fetch_channel(int(thread_id))
            except (discord.NotFound, discord.HTTPException):
                pass

            if not thread or not isinstance(thread, discord.Thread) or not thread.archived:
                await col.delete_one({"_id": doc["_id"]})
                removed += 1
            else:
                valid += 1

        logger.info(f"[ThreadPool] validate_pool: {valid} válidas, {removed} removidas")
        return {"valid": valid, "removed": removed}

    # ─────────────────────────────────────────────
    # Health / Diagnóstico
    # ─────────────────────────────────────────────

    async def get_health(self, guild: discord.Guild) -> Dict[str, Any]:
        """Retorna snapshot do estado do sistema de threads."""
        col_pool    = db.get_collection("thread_pool")
        col_active  = db.get_collection("active_threads")

        pool_docs   = await col_pool.find({}).to_list(length=None)
        active_docs = await col_active.find({}).to_list(length=None)

        pool_total     = len(pool_docs)
        active_matches = len(active_docs)
        live_discord   = await self._count_live_threads(guild)
        margem         = DISCORD_THREAD_LIMIT - live_discord

        # Agrupa pool por canal
        pool_by_channel: Dict[str, int] = {}
        for doc in pool_docs:
            cid = str(doc.get("channel_id", "?"))
            pool_by_channel[cid] = pool_by_channel.get(cid, 0) + 1

        return {
            "pool_total":      pool_total,
            "active_matches":  active_matches,
            "live_discord":    live_discord,
            "margem":          margem,
            "pool_by_channel": pool_by_channel,
        }

    async def check_slow_mode(self, channel: discord.TextChannel) -> int:
        """Retorna o slow mode (segundos) de um canal."""
        return getattr(channel, "slowmode_delay", 0) or 0

    # ─────────────────────────────────────────────
    # Helpers internos
    # ─────────────────────────────────────────────

    async def _get_from_pool(self, channel: discord.TextChannel) -> Optional[discord.Thread]:
        """Busca e remove uma thread arquivada do pool para o canal informado."""
        col = db.get_collection("thread_pool")
        doc = await col.find_one_and_delete({"channel_id": channel.id})
        if not doc:
            return None

        try:
            thread = await channel.guild.fetch_channel(doc["thread_id"])
            if isinstance(thread, discord.Thread) and thread.archived:
                return thread
        except (discord.NotFound, discord.HTTPException):
            pass

        return None

    async def _save_to_pool(self, thread: discord.Thread, channel: discord.TextChannel):
        """Salva thread arquivada no pool do banco."""
        col = db.get_collection("thread_pool")
        await col.update_one(
            {"thread_id": thread.id},
            {"$set": {
                "thread_id":  thread.id,
                "channel_id": channel.id,
                "saved_at":   datetime.utcnow(),
            }},
            upsert=True,
        )

    async def _mark_active(self, thread: discord.Thread, channel: discord.TextChannel):
        """Registra thread como ativa (em uso por uma partida)."""
        col = db.get_collection("active_threads")
        await col.update_one(
            {"thread_id": thread.id},
            {"$set": {
                "thread_id":  thread.id,
                "channel_id": channel.id,
                "match_id":   None,
                "started_at": datetime.utcnow(),
                # TTL de segurança: remove do banco após 2h sem atualização
                "expires_at": datetime.utcnow() + timedelta(hours=2),
            }},
            upsert=True,
        )

    async def _unmark_active(self, thread: discord.Thread):
        """Remove thread do registro de ativas."""
        col = db.get_collection("active_threads")
        await col.delete_one({"thread_id": thread.id})

    async def _clean_and_archive(self, thread: discord.Thread, reason: str = ""):
        """
        1. Remove registro de ativa do banco
        2. Renomeia para sentinela
        3. Arquiva
        4. Salva no pool
        """
        try:
            await self._unmark_active(thread)

            try:
                await thread.edit(name=POOL_THREAD_NAME, archived=False)
                await asyncio.sleep(0.5)
                await thread.edit(archived=True)
            except discord.HTTPException as e:
                logger.warning(f"[ThreadPool] Falha ao arquivar thread {thread.id}: {e}")
                return

            # Descobre o canal pai
            parent = thread.parent
            if parent and isinstance(parent, discord.TextChannel):
                await self._save_to_pool(thread, parent)
                logger.info(f"[ThreadPool] Thread {thread.id} devolvida ao pool ({reason})")
            else:
                logger.warning(f"[ThreadPool] Canal pai não encontrado para thread {thread.id}")

        except Exception as e:
            logger.error(f"[ThreadPool] _clean_and_archive erro: {e}", exc_info=True)

    async def _count_live_threads(self, guild: discord.Guild) -> int:
        """
        Conta threads ATIVAS (não arquivadas) no servidor.
        Usa a API do Discord para precisão máxima.
        """
        try:
            count  = 0
            # active_threads retorna todas as threads ativas do servidor
            result = await guild.active_threads()
            count  = len(result)
            return count
        except Exception as e:
            logger.warning(f"[ThreadPool] Não foi possível contar threads ativas: {e}")
            # Fallback: conta pelo cache local
            return sum(
                1 for ch in guild.threads
                if not getattr(ch, "archived", True)
            )


# ─────────────────────────────────────────────
# Singleton global
# ─────────────────────────────────────────────

thread_reuse_service: Optional[ThreadReuseService] = None


def init_thread_reuse_service(bot: discord.Client) -> ThreadReuseService:
    global thread_reuse_service
    thread_reuse_service = ThreadReuseService(bot)
    return thread_reuse_service
