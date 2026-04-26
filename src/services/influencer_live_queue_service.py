"""
influencer_live_queue_service.py
Fila de desafiantes de uma sala do modo contra.

Cada sala tem sua própria fila isolada (keyed por influencer_id + guild_id).
Quando a fila avança, o próximo desafiante é notificado e a partida é criada.

FIX: ContraResultView NÃO é mais postada aqui.
É postada em ContraPaymentModal.on_submit (após pagamento confirmado).
"""
from __future__ import annotations
import discord
from utils.logger import logger
from utils.datetime_utils import utcnow
from config.database import db

COLLECTION = "influencer_live_queues"


class InfluencerLiveQueue:
    def __init__(self, doc: dict):
        self.influencer_id   = str(doc["influencer_id"])
        self.guild_id        = str(doc["guild_id"])
        self.players         = doc.get("players", [])
        self.status          = doc.get("status", "waiting")
        self.active_match_id = doc.get("active_match_id")
        self.updated_at      = doc.get("updated_at", utcnow())

    def size(self) -> int:
        return len(self.players)


class InfluencerLiveQueueService:

    def _col(self):
        return db.get_collection(COLLECTION)

    async def _get_or_create(self, influencer_id: str, guild_id: str) -> dict:
        doc = await self._col().find_one(
            {"influencer_id": influencer_id, "guild_id": guild_id})
        if not doc:
            doc = {
                "influencer_id":   influencer_id,
                "guild_id":        guild_id,
                "players":         [],
                "status":          "waiting",
                "active_match_id": None,
                "updated_at":      utcnow(),
            }
            await self._col().insert_one(doc)
        return doc

    async def enter_queue(
        self, influencer_id: str, guild_id: str, player_id: str
    ) -> dict:
        doc = await self._get_or_create(influencer_id, guild_id)

        if player_id in doc.get("players", []):
            pos = doc["players"].index(player_id) + 1
            return {"ok": False, "msg": f"Você já está na fila. Posição: **{pos}º**"}

        await self._col().update_one(
            {"influencer_id": influencer_id, "guild_id": guild_id},
            {"$push": {"players": player_id}, "$set": {"updated_at": utcnow()}},
        )
        doc["players"].append(player_id)
        position = len(doc["players"])

        from services.influencer_live_room_service import influencer_live_room_service
        await influencer_live_room_service.update_queue_size(influencer_id, guild_id, 1)

        logger.info(
            f"[LiveQueue] {player_id} entrou na fila — influencer {influencer_id} pos {position}")
        return {"ok": True, "position": position}

    async def leave_queue(
        self, influencer_id: str, guild_id: str, player_id: str
    ) -> dict:
        doc = await self._col().find_one(
            {"influencer_id": influencer_id, "guild_id": guild_id})
        if not doc or player_id not in doc.get("players", []):
            return {"ok": False, "msg": "Você não está na fila."}

        await self._col().update_one(
            {"influencer_id": influencer_id, "guild_id": guild_id},
            {"$pull": {"players": player_id}, "$set": {"updated_at": utcnow()}},
        )
        from services.influencer_live_room_service import influencer_live_room_service
        await influencer_live_room_service.update_queue_size(influencer_id, guild_id, -1)

        logger.info(f"[LiveQueue] {player_id} saiu da fila — influencer {influencer_id}")
        return {"ok": True}

    async def get_fila(self, influencer_id: str, guild_id: str) -> dict:
        doc = await self._get_or_create(influencer_id, guild_id)
        return {"ok": True, "queue": InfluencerLiveQueue(doc)}

    async def clear_queue(self, influencer_id: str, guild_id: str):
        await self._col().update_one(
            {"influencer_id": influencer_id, "guild_id": guild_id},
            {"$set": {"players": [], "status": "waiting",
                      "active_match_id": None, "updated_at": utcnow()}},
        )
        logger.info(f"[LiveQueue] Fila limpa — influencer {influencer_id}")

    async def advance_queue(
        self,
        influencer_id: str,
        guild_id: str,
        bot: discord.Client | None = None,
    ) -> dict:
        """
        Remove o primeiro da fila (partida encerrada/cancelada/desistência).
        Se houver próximo, cria a partida e notifica (só ContraConfirmView).
        ContraResultView é postada posteriormente pelo ContraPaymentModal.
        """
        doc = await self._col().find_one(
            {"influencer_id": influencer_id, "guild_id": guild_id})
        if not doc:
            return {"ok": False, "msg": "Fila não encontrada."}

        players    = list(doc.get("players", []))
        had_player = len(players) > 0

        if had_player:
            players.pop(0)

        await self._col().update_one(
            {"influencer_id": influencer_id, "guild_id": guild_id},
            {"$set": {
                "players":         players,
                "status":          "waiting",
                "active_match_id": None,
                "updated_at":      utcnow(),
            }},
        )

        if had_player:
            from services.influencer_live_room_service import influencer_live_room_service
            await influencer_live_room_service.update_queue_size(influencer_id, guild_id, -1)

        if not players:
            logger.info(f"[LiveQueue] Fila vazia após avanço — influencer {influencer_id}")
            return {"ok": True, "next": None}

        next_player_id = players[0]
        logger.info(f"[LiveQueue] Próximo desafiante: {next_player_id} — influencer {influencer_id}")

        if bot:
            await self._notify_next(
                bot=bot,
                guild_id=guild_id,
                influencer_id=influencer_id,
                next_player_id=next_player_id,
            )

        return {"ok": True, "next": next_player_id}

    async def _notify_next(
        self,
        bot: discord.Client,
        guild_id: str,
        influencer_id: str,
        next_player_id: str,
    ):
        """
        Posta ContraConfirmView no canal contra-<influencer>.
        ContraResultView só será postada APÓS o desafiante confirmar pagamento
        (via ContraPaymentModal.on_submit).
        """
        try:
            from services.influencer_live_room_service import influencer_live_room_service
            from services.match_service import match_service
            from services.mediator_live_queue_service import mediator_live_queue_service
            from views.influencer_live_match_view import ContraConfirmView

            guild = bot.get_guild(int(guild_id))
            if not guild:
                return

            room_result = await influencer_live_room_service.get_room(influencer_id, guild_id)
            if not room_result["ok"]:
                return
            room = room_result["room"]

            channel = guild.get_channel(int(room.channel_id)) if room.channel_id else None
            if not channel:
                return

            influencer = guild.get_member(int(influencer_id))
            challenger = guild.get_member(int(next_player_id))
            if not influencer or not challenger:
                return

            mediator_result = await mediator_live_queue_service.assign_next(
                guild_id=guild_id, match_id="pending")
            mediator_id = mediator_result.get("mediator_id") if mediator_result.get("ok") else None

            match_doc = await match_service.create_live_match(
                guild_id=guild_id,
                influencer_id=influencer_id,
                challenger_id=next_player_id,
                entry_value=room.entry_value,
                game_mode=room.game_mode,
                mediator_id=mediator_id,
                channel_id=str(room.channel_id) if room.channel_id else None,
                channel_name=room.channel_name,
            )
            match_id = str(match_doc["_id"])

            if mediator_result.get("ok"):
                from config.database import db as _db
                await _db.get_collection("mediator_live_queues").update_one(
                    {"guild_id": guild_id},
                    {"$set": {"active_match_id": match_id}},
                )

            await self._col().update_one(
                {"influencer_id": influencer_id, "guild_id": guild_id},
                {"$set": {
                    "status":          "in_match",
                    "active_match_id": match_id,
                    "updated_at":      utcnow(),
                }},
            )

            mediator_mention = f"<@{mediator_id}>" if mediator_id else "⚠️ *Nenhum Controller Live disponível*"

            embed = discord.Embed(
                title="⚔️ É a sua vez!",
                description=(
                    f"{challenger.mention}, você é o próximo desafiante!\n\n"
                    f"**Influencer:** {influencer.mention}\n"
                    f"**Modo:** `{room.game_mode}` | **Valor:** R$ `{room.entry_value:.2f}`\n"
                    f"**Controller Live:** {mediator_mention}\n\n"
                    "Confirme sua presença e pagamento abaixo."
                ),
                color=0xE91E63,
            )

            # Passa channel e mediator_id para o ContraConfirmView
            # para que ContraPaymentModal possa postar ContraResultView após pagamento
            confirm_view = ContraConfirmView(
                match_id=match_id,
                challenger_id=int(next_player_id),
                influencer_id=int(influencer_id),
                mediator_id=int(mediator_id) if mediator_id else None,
                channel=channel,
                guild_id=int(guild_id),
            )
            await channel.send(
                content=f"🚨 {challenger.mention}",
                embed=embed,
                view=confirm_view,
            )
            logger.info(
                f"[LiveQueue] ContraConfirmView postada — match {match_id} "
                f"mediator {mediator_id or 'nenhum'}"
            )
        except Exception as e:
            logger.error(f"[LiveQueue] _notify_next erro: {e}", exc_info=True)

    async def get_position(self, influencer_id: str, guild_id: str, player_id: str) -> dict:
        doc = await self._col().find_one(
            {"influencer_id": influencer_id, "guild_id": guild_id})
        if not doc or player_id not in doc.get("players", []):
            return {"ok": False, "msg": "Você não está na fila."}
        pos = doc["players"].index(player_id) + 1
        return {"ok": True, "position": pos}


influencer_live_queue_service = InfluencerLiveQueueService()
