from __future__ import annotations
import asyncio
from datetime import timedelta
from typing import Optional, Dict, Any, List

import discord

from config.database import db
from utils.datetime_utils import utcnow
from utils.logger import logger

DISCORD_THREAD_LIMIT = 1000
SAFE_ACTIVE_LIMIT    = 900
POOL_THREAD_NAME     = "♻️ aguardando-partida"
POOL_RETURN_DELAY    = 15
POOL_MAX_DOCS        = 500
ACTIVE_THREAD_TTL    = timedelta(hours=2)


class ThreadReuseService:

    def __init__(self, bot: discord.Client):
        self.bot = bot

    # ── Ponto de entrada ────────────────────────────────────────

    async def get_or_create_thread(
        self,
        channel: discord.TextChannel,
        thread_name: str,
        player_ids: List[int],
        guild: discord.Guild,
    ) -> Optional[discord.Thread]:
        try:
            thread = await self._get_from_pool(channel)

            if thread:
                try:
                    await thread.edit(archived=False, name=thread_name[:100])
                    logger.info(f"[ThreadPool] Reusando thread {thread.id} em {channel.name}")
                except discord.HTTPException as e:
                    logger.warning(f"[ThreadPool] Falha ao reativar thread do pool {thread.id}: {e}")
                    thread = None

            if not thread:
                live = await self._count_live_threads(guild)
                if live >= SAFE_ACTIVE_LIMIT:
                    logger.error(
                        f"[ThreadPool] Limite seguro atingido {live}/{SAFE_ACTIVE_LIMIT}. "
                        f"Não é possível criar nova thread em {channel.name}."
                    )
                    return None
                thread = await channel.create_thread(
                    name=thread_name[:100],
                    type=discord.ChannelType.public_thread,
                    auto_archive_duration=60,
                )
                logger.info(f"[ThreadPool] Nova thread criada {thread.id} em {channel.name}")

            for uid in player_ids:
                member = guild.get_member(uid)
                if member:
                    try:
                        await thread.add_user(member)
                    except Exception:
                        pass

            await self._mark_active(thread, channel)
            return thread

        except Exception as e:
            logger.error(f"[ThreadPool] get_or_create_thread erro: {e}", exc_info=True)
            return None

    # ── Devolução ao pool ────────────────────────────────────────

    async def return_to_pool_after_match(self, thread: discord.Thread):
        """
        Sequência garantida:
          1. Arquiva o log HTML/ZIP em #logs-partidas (ANTES de apagar mensagens)
          2. Aguarda POOL_RETURN_DELAY segundos
          3. Limpa e devolve a thread ao pool
        """
        try:
            # 1. Gera o log da thread ANTES de qualquer limpeza
            await self._archive_thread_log(thread)

            # 2. Aguarda o delay configurado
            await asyncio.sleep(POOL_RETURN_DELAY)

            # 3. Limpa mensagens, remove membros, arquiva e salva no pool
            await self._clean_and_archive(thread, reason="match_finalizado")

        except Exception as e:
            logger.error(
                f"[ThreadPool] return_to_pool_after_match erro {thread.id}: {e}",
                exc_info=True,
            )

    async def return_to_pool_empty(self, thread: discord.Thread):
        try:
            await self._clean_and_archive(thread, reason="queue_expirada")
        except Exception as e:
            logger.error(f"[ThreadPool] return_to_pool_empty erro {thread.id}: {e}", exc_info=True)

    # ── Log da thread (integração com thread_log_service) ────────

    async def _archive_thread_log(self, thread: discord.Thread):
        """Busca o match vinculado à thread e chama thread_log_service.archive_thread()."""
        try:
            from services.thread_log_service import get_thread_log_service
            log_svc = get_thread_log_service()
            if not log_svc:
                logger.warning(f"[ThreadPool] thread_log_service não inicializado — log ignorado para thread {thread.id}")
                return

            match_doc = await self._get_match_for_thread(thread.id)
            if not match_doc:
                logger.warning(f"[ThreadPool] Nenhum match encontrado para thread {thread.id} — log ignorado")
                return

            logger.info(f"[ThreadPool] Gerando log para match {match_doc.get('_id')} (thread {thread.id})")
            await log_svc.archive_thread(thread, match_doc)

        except Exception as e:
            logger.error(f"[ThreadPool] _archive_thread_log erro thread {thread.id}: {e}", exc_info=True)

    async def _get_match_for_thread(self, thread_id: int) -> Optional[Dict[str, Any]]:
        """
        Tenta encontrar o match via active_threads (match_id) e depois na collection matches.
        Fallback: busca direta em matches por thread_id.
        """
        try:
            # Caminho 1: via active_threads (tem match_id salvo)
            col_active = db.get_collection("active_threads")
            active_doc = await col_active.find_one({"thread_id": thread_id})
            if active_doc and active_doc.get("match_id"):
                from bson import ObjectId
                col_matches = db.get_collection("matches")
                match_doc = await col_matches.find_one(
                    {"_id": ObjectId(active_doc["match_id"])}
                )
                if match_doc:
                    return match_doc

            # Caminho 2: fallback direto por thread_id
            col_matches = db.get_collection("matches")
            match_doc = await col_matches.find_one({"thread_id": thread_id})
            if not match_doc:
                match_doc = await col_matches.find_one({"thread_id": str(thread_id)})
            return match_doc

        except Exception as e:
            logger.error(f"[ThreadPool] _get_match_for_thread erro thread {thread_id}: {e}")
            return None

    # ── Atualização de match ativo ───────────────────────────────

    async def update_active_thread_match(self, thread_id: int, match_id: str):
        try:
            col = db.get_collection("active_threads")
            await col.update_one(
                {"thread_id": thread_id},
                {"$set": {"match_id": match_id, "updated_at": utcnow()}},
            )
        except Exception as e:
            logger.warning(f"[ThreadPool] update_active_thread_match erro: {e}")

    # ── Admin ────────────────────────────────────────────────────

    async def preaquecer(self, channel: discord.TextChannel, quantidade: int = 3) -> int:
        criadas = 0
        for _ in range(quantidade):
            try:
                thread = await channel.create_thread(
                    name=POOL_THREAD_NAME,
                    type=discord.ChannelType.public_thread,
                    auto_archive_duration=60,
                )
                await asyncio.sleep(1)
                await thread.edit(archived=True)

                fresh = await channel.guild.fetch_channel(thread.id)
                if isinstance(fresh, discord.Thread) and fresh.archived:
                    await self._save_to_pool(thread, channel)
                    criadas += 1
                    logger.info(f"[ThreadPool] Pré-aquecida thread {thread.id} em {channel.name}")
                else:
                    logger.warning(f"[ThreadPool] Thread {thread.id} não arquivou, descartada do pool.")
            except discord.HTTPException as e:
                logger.warning(f"[ThreadPool] Falha ao pré-aquecer: {e}")
                break
            except Exception as e:
                logger.error(f"[ThreadPool] Erro inesperado no pré-aquecimento: {e}")
                break
        return criadas

    async def validate_pool(self, guild: discord.Guild) -> Dict[str, int]:
        col  = db.get_collection("thread_pool")
        docs = await col.find().to_list(length=POOL_MAX_DOCS)
        valid = removed = 0

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

    async def get_health(self, guild: discord.Guild) -> Dict[str, Any]:
        col_pool   = db.get_collection("thread_pool")
        col_active = db.get_collection("active_threads")

        pool_docs   = await col_pool.find().to_list(length=POOL_MAX_DOCS)
        active_docs = await col_active.find().to_list(length=POOL_MAX_DOCS)

        pool_total     = len(pool_docs)
        active_matches = len(active_docs)
        live_discord   = await self._count_live_threads(guild)
        margem         = DISCORD_THREAD_LIMIT - live_discord

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

    # ── Internos ─────────────────────────────────────────────────

    async def _check_slowmode(self, channel: discord.TextChannel) -> int:
        return getattr(channel, "slowmode_delay", 0) or 0

    async def _get_from_pool(self, channel: discord.TextChannel) -> Optional[discord.Thread]:
        col = db.get_collection("thread_pool")
        doc = await col.find_one({"channel_id": channel.id})
        if not doc:
            return None

        try:
            thread = await channel.guild.fetch_channel(doc["thread_id"])
        except (discord.NotFound, discord.HTTPException):
            await col.delete_one({"_id": doc["_id"]})
            logger.warning(f"[ThreadPool] Thread {doc['thread_id']} não existe mais, removida do pool.")
            return None

        if not isinstance(thread, discord.Thread) or not thread.archived:
            await col.delete_one({"_id": doc["_id"]})
            logger.warning(f"[ThreadPool] Thread {doc['thread_id']} inválida/não arquivada, removida.")
            return None

        await col.delete_one({"_id": doc["_id"]})
        return thread

    async def _save_to_pool(self, thread: discord.Thread, channel: discord.TextChannel):
        col = db.get_collection("thread_pool")
        await col.update_one(
            {"thread_id": thread.id},
            {"$set": {"thread_id": thread.id, "channel_id": channel.id, "saved_at": utcnow()}},
            upsert=True,
        )

    async def _mark_active(self, thread: discord.Thread, channel: discord.TextChannel):
        col = db.get_collection("active_threads")
        now = utcnow()
        await col.update_one(
            {"thread_id": thread.id},
            {"$set": {
                "thread_id":  thread.id,
                "channel_id": channel.id,
                "match_id":   None,
                "started_at": now,
                "expires_at": now + ACTIVE_THREAD_TTL,
            }},
            upsert=True,
        )

    async def _unmark_active(self, thread: discord.Thread):
        col = db.get_collection("active_threads")
        await col.delete_one({"thread_id": thread.id})

    async def _clean_and_archive(self, thread: discord.Thread, reason: str = ""):
        try:
            await self._unmark_active(thread)

            # 1. Remove todos os membros (exceto o bot)
            try:
                members = await thread.fetch_members()
                for m in members:
                    if m.id != thread.guild.me.id:
                        try:
                            await thread.remove_user(discord.Object(id=m.id))
                        except Exception:
                            pass
            except Exception as e:
                logger.warning(f"[ThreadPool] Erro ao remover membros {thread.id}: {e}")

            # 2. Apaga mensagens (bulk_delete para as < 14 dias, individual para antigas)
            try:
                to_delete = [msg async for msg in thread.history(limit=200)]
                if len(to_delete) >= 2:
                    await thread.delete_messages(to_delete)
                elif len(to_delete) == 1:
                    await to_delete[0].delete()
            except discord.HTTPException as e:
                logger.warning(f"[ThreadPool] Erro ao limpar mensagens {thread.id}: {e}")

            # 3. Renomeia e arquiva
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
            else:
                logger.warning(f"[ThreadPool] Canal pai não encontrado para thread {thread.id}")

        except Exception as e:
            logger.error(
                f"[ThreadPool] _clean_and_archive erro thread {thread.id}: {e}",
                exc_info=True,
            )

    async def _count_live_threads(self, guild: discord.Guild) -> int:
        try:
            result = await guild.active_threads()
            return len(result)
        except Exception as e:
            logger.warning(f"[ThreadPool] active_threads falhou: {e}, usando estimativa conservadora")
            return SAFE_ACTIVE_LIMIT


# ── Singleton ────────────────────────────────────────────────────

thread_reuse_service: Optional[ThreadReuseService] = None


def init_thread_reuse_service(bot: discord.Client) -> ThreadReuseService:
    global thread_reuse_service
    thread_reuse_service = ThreadReuseService(bot)
    return thread_reuse_service