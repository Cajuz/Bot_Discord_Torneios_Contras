"""
mediator_live_queue_service.py
Fila de Controllers Live disponíveis para mediar partidas no modo contra.

Uma única fila global por guild (não por sala).
Quando uma partida live começa, o primeiro Controller Live disponível é escalado.
"""
from __future__ import annotations
from utils.logger import logger
from utils.datetime_utils import utcnow
from config.database import db

COLLECTION = "mediator_live_queues"


class MediatorLiveQueue:
    def __init__(self, doc: dict):
        self.guild_id        = str(doc["guild_id"])
        self.mediators       = doc.get("mediators", [])      # list[str] — discord_ids
        self.status          = doc.get("status", "waiting")  # waiting | in_match
        self.active_match_id = doc.get("active_match_id")
        self.updated_at      = doc.get("updated_at", utcnow())

    def size(self) -> int:
        return len(self.mediators)


class MediatorLiveQueueService:

    def _col(self):
        return db.get_collection(COLLECTION)

    async def _get_or_create(self, guild_id: str) -> dict:
        doc = await self._col().find_one({"guild_id": guild_id})
        if not doc:
            doc = {
                "guild_id":        guild_id,
                "mediators":       [],
                "status":          "waiting",
                "active_match_id": None,
                "updated_at":      utcnow(),
            }
            await self._col().insert_one(doc)
        return doc

    # ── Entrar na fila ────────────────────────────────────────────────────
    async def enter_queue(self, guild_id: str, mediator_id: int) -> dict:
        mid = str(mediator_id)
        doc = await self._get_or_create(guild_id)

        if mid in doc.get("mediators", []):
            pos = doc["mediators"].index(mid) + 1
            return {"ok": False, "msg": f"Você já está na fila. Posição: **{pos}º**"}

        await self._col().update_one(
            {"guild_id": guild_id},
            {
                "$push": {"mediators": mid},
                "$set":  {"updated_at": utcnow()},
            },
        )
        doc["mediators"].append(mid)
        position = len(doc["mediators"])
        logger.info(f"[MediatorLiveQueue] {mid} entrou na fila — guild {guild_id} pos {position}")
        return {"ok": True, "position": position}

    # ── Sair da fila ──────────────────────────────────────────────────────
    async def leave_queue(self, guild_id: str, mediator_id: int) -> dict:
        mid = str(mediator_id)
        doc = await self._col().find_one({"guild_id": guild_id})
        if not doc or mid not in doc.get("mediators", []):
            return {"ok": False, "msg": "Você não está na fila Controller Live."}

        await self._col().update_one(
            {"guild_id": guild_id},
            {
                "$pull": {"mediators": mid},
                "$set":  {"updated_at": utcnow()},
            },
        )
        logger.info(f"[MediatorLiveQueue] {mid} saiu da fila — guild {guild_id}")
        return {"ok": True}

    # ── Ver fila ──────────────────────────────────────────────────────────
    async def get_fila(self, guild_id: str) -> dict:
        doc = await self._get_or_create(guild_id)
        return {"ok": True, "queue": MediatorLiveQueue(doc)}

    # ── Posição de um mediador ────────────────────────────────────────────
    async def get_position(self, guild_id: str, mediator_id: int) -> dict:
        mid = str(mediator_id)
        doc = await self._col().find_one({"guild_id": guild_id})
        if not doc or mid not in doc.get("mediators", []):
            return {"ok": False, "msg": "Você não está na fila Controller Live."}
        pos = doc["mediators"].index(mid) + 1
        return {"ok": True, "position": pos}

    # ── Escalar próximo Controller Live ───────────────────────────────────
    async def assign_next(self, guild_id: str, match_id: str) -> dict:
        """
        Retira o primeiro da fila, marca como in_match e retorna o mediator_id.
        Chamado pelo influencer_live_queue_service._notify_next.
        """
        doc = await self._col().find_one({"guild_id": guild_id})
        if not doc or not doc.get("mediators"):
            return {"ok": False, "msg": "Nenhum Controller Live disponível na fila."}

        mediators = doc["mediators"]
        assigned  = mediators.pop(0)

        await self._col().update_one(
            {"guild_id": guild_id},
            {"$set": {
                "mediators":       mediators,
                "status":          "in_match",
                "active_match_id": match_id,
                "updated_at":      utcnow(),
            }},
        )
        logger.info(
            f"[MediatorLiveQueue] {assigned} escalado para match {match_id} — guild {guild_id}")
        return {"ok": True, "mediator_id": assigned}

    # ── Liberar após fim da partida ───────────────────────────────────────
    async def release(self, guild_id: str, mediator_id: str | None = None) -> dict:
        """
        Após partida encerrada, volta status para waiting.
        Se mediator_id for fornecido, o recoloca no final da fila.
        """
        updates: dict = {
            "status":          "waiting",
            "active_match_id": None,
            "updated_at":      utcnow(),
        }
        push = {}
        if mediator_id:
            push = {"$push": {"mediators": mediator_id}}

        await self._col().update_one(
            {"guild_id": guild_id},
            {**{"$set": updates}, **push},
        )
        logger.info(
            f"[MediatorLiveQueue] Fila liberada — guild {guild_id} "
            f"mediator reinserido: {mediator_id or 'nenhum'}"
        )
        return {"ok": True}


mediator_live_queue_service = MediatorLiveQueueService()