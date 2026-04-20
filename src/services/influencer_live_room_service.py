"""
influencer_live_room_service.py
Gerencia o ciclo de vida das salas do modo contra (InfluencerLiveRoom).

Responsabilidades:
  - ativar_sala        → cria room no DB + canal Discord
  - desativar_sala     → encerra room + deleta canal
  - editar_sala        → atualiza entry_value / game_mode / custom_rules
  - get_room           → busca room por influencer_id + guild_id
  - list_active_rooms  → lista todas as rooms ativas de uma guild
  - get_stats          → estatísticas agregadas do modo contra
"""
from __future__ import annotations
import discord
from utils.logger import logger
from utils.datetime_utils import utcnow
from config.database import db


# ── Coleção MongoDB ──────────────────────────────────────────────────────────
COLLECTION = "influencer_live_rooms"


class InfluencerLiveRoom:
    """Representação leve de um documento da coleção influencer_live_rooms."""

    def __init__(self, doc: dict):
        self.influencer_id  = int(doc["influencer_id"])
        self.guild_id       = str(doc["guild_id"])
        self.status         = doc.get("status", "inactive")       # active | paused | inactive
        self.game_mode      = doc.get("game_mode", "1v1")         # 1v1 | 2v2
        self.entry_value    = float(doc.get("entry_value", 0.0))
        self.custom_rules   = doc.get("custom_rules")
        self.channel_name   = doc.get("channel_name", "")
        self.channel_id     = doc.get("channel_id")
        self.queue_size     = int(doc.get("queue_size", 0))
        self.created_at     = doc.get("created_at", utcnow())
        self.updated_at     = doc.get("updated_at", utcnow())

    def to_dict(self) -> dict:
        return {
            "influencer_id": str(self.influencer_id),
            "guild_id":      self.guild_id,
            "status":        self.status,
            "game_mode":     self.game_mode,
            "entry_value":   self.entry_value,
            "custom_rules":  self.custom_rules,
            "channel_name":  self.channel_name,
            "channel_id":    str(self.channel_id) if self.channel_id else None,
            "queue_size":    self.queue_size,
            "created_at":    self.created_at,
            "updated_at":    self.updated_at,
        }


class InfluencerLiveRoomService:

    def _col(self):
        return db.get_collection(COLLECTION)

    # ══════════════════════════════════════════════════════════
    # ATIVAR SALA
    # ══════════════════════════════════════════════════════════

    async def ativar_sala(
        self,
        guild: discord.Guild,
        influencer: discord.Member,
        entry_value: float,
        game_mode: str = "1v1",
        custom_rules: str | None = None,
    ) -> dict:
        col = self._col()

        # Verifica se já existe sala ativa
        existing = await col.find_one({
            "influencer_id": str(influencer.id),
            "guild_id":      str(guild.id),
            "status":        "active",
        })
        if existing:
            return {"ok": False, "msg": "Você já tem uma sala ativa. Use `/influencer live_desativar` primeiro."}

        # Cria canal Discord
        from services.channel_service import permission_service
        channel = await permission_service.create_contra_channel(guild, influencer)

        channel_name = channel.name

        # Persiste no DB
        now = utcnow()
        doc = {
            "influencer_id": str(influencer.id),
            "guild_id":      str(guild.id),
            "status":        "active",
            "game_mode":     game_mode,
            "entry_value":   entry_value,
            "custom_rules":  custom_rules,
            "channel_name":  channel_name,
            "channel_id":    str(channel.id),
            "queue_size":    0,
            "created_at":    now,
            "updated_at":    now,
        }
        await col.insert_one(doc)
        room = InfluencerLiveRoom(doc)

        # Posta painel público no canal
        from views.influencer_live_view import ContraRoomView, build_contra_room_embed
        embed = build_contra_room_embed(room, queue_size=0)
        view  = ContraRoomView(influencer_id=influencer.id, guild_id=guild.id)
        await channel.send(embed=embed, view=view)

        logger.info(
            f"[InfluencerLiveRoom] Sala ativada — influencer {influencer.name} "
            f"guild {guild.id} canal #{channel_name}"
        )
        return {"ok": True, "msg": "Sala ativada.", "room": room, "channel": channel}

    # ══════════════════════════════════════════════════════════
    # DESATIVAR SALA
    # ══════════════════════════════════════════════════════════

    async def desativar_sala(
        self,
        guild: discord.Guild,
        influencer: discord.Member,
        forced_by: discord.Member | None = None,
    ) -> dict:
        col = self._col()

        doc = await col.find_one({
            "influencer_id": str(influencer.id),
            "guild_id":      str(guild.id),
            "status":        {"$in": ["active", "paused"]},
        })
        if not doc:
            return {"ok": False, "msg": "Nenhuma sala ativa encontrada para este influencer."}

        room = InfluencerLiveRoom(doc)

        # Cancela fila pendente
        from services.influencer_live_queue_service import influencer_live_queue_service
        await influencer_live_queue_service.clear_queue(
            influencer_id=str(influencer.id),
            guild_id=str(guild.id),
        )

        # Deleta canal Discord
        from services.channel_service import permission_service
        await permission_service.delete_contra_channel(guild, room.channel_name)

        # Atualiza status no DB
        await col.update_one(
            {"_id": doc["_id"]},
            {"$set": {"status": "inactive", "updated_at": utcnow()}},
        )

        reason = f"por ADM {forced_by.name}" if forced_by else "pelo influencer"
        logger.info(
            f"[InfluencerLiveRoom] Sala desativada {reason} — "
            f"influencer {influencer.name} guild {guild.id}"
        )
        return {"ok": True, "msg": "Sala desativada."}

    # ══════════════════════════════════════════════════════════
    # EDITAR SALA
    # ══════════════════════════════════════════════════════════

    async def editar_sala(
        self,
        influencer_id: str,
        guild_id: str,
        entry_value: float | None = None,
        game_mode: str | None = None,
        custom_rules: str | None = None,
    ) -> dict:
        col = self._col()

        doc = await col.find_one({
            "influencer_id": influencer_id,
            "guild_id":      guild_id,
            "status":        "active",
        })
        if not doc:
            return {"ok": False, "msg": "Nenhuma sala ativa encontrada."}

        updates: dict = {"updated_at": utcnow()}
        if entry_value is not None:
            updates["entry_value"] = entry_value
        if game_mode is not None:
            updates["game_mode"] = game_mode
        if custom_rules is not None:
            updates["custom_rules"] = custom_rules

        await col.update_one({"_id": doc["_id"]}, {"$set": updates})
        doc.update(updates)
        room = InfluencerLiveRoom(doc)

        logger.info(f"[InfluencerLiveRoom] Sala editada — influencer {influencer_id}")
        return {"ok": True, "msg": "Sala atualizada.", "room": room}

    # ══════════════════════════════════════════════════════════
    # GET / LIST
    # ══════════════════════════════════════════════════════════

    async def get_room(self, influencer_id: str, guild_id: str) -> dict:
        doc = await self._col().find_one({
            "influencer_id": influencer_id,
            "guild_id":      guild_id,
            "status":        {"$in": ["active", "paused"]},
        })
        if not doc:
            return {"ok": False, "msg": "Sala não encontrada."}
        return {"ok": True, "room": InfluencerLiveRoom(doc)}

    async def list_active_rooms(self, guild_id: str) -> dict:
        cursor = self._col().find({"guild_id": guild_id, "status": "active"})
        rooms  = [InfluencerLiveRoom(d) async for d in cursor]
        return {"ok": True, "rooms": rooms}

    # ══════════════════════════════════════════════════════════
    # STATS
    # ══════════════════════════════════════════════════════════

    async def get_stats(self, guild_id: str) -> dict:
        from services.match_service import match_service
        import datetime

        today_start = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

        active_rooms = await self._col().count_documents(
            {"guild_id": guild_id, "status": "active"})

        # Partidas live hoje
        matches_col = db.get_collection("matches")
        matches_today = await matches_col.count_documents({
            "guild_id":   guild_id,
            "flow_type":  "influencer_live",
            "status":     "finalizada",
            "created_at": {"$gte": today_start},
        })

        # Volume hoje
        pipeline_today = [
            {"$match": {
                "guild_id":   guild_id,
                "flow_type":  "influencer_live",
                "status":     "finalizada",
                "created_at": {"$gte": today_start},
            }},
            {"$group": {"_id": None, "total": {"$sum": "$bet_value"}}},
        ]
        res_today = await matches_col.aggregate(pipeline_today).to_list(1)
        volume_today = res_today[0]["total"] if res_today else 0.0

        # Totais
        total_matches = await matches_col.count_documents({
            "guild_id":  guild_id,
            "flow_type": "influencer_live",
            "status":    "finalizada",
        })
        pipeline_total = [
            {"$match": {"guild_id": guild_id, "flow_type": "influencer_live", "status": "finalizada"}},
            {"$group": {"_id": None, "total": {"$sum": "$bet_value"}}},
        ]
        res_total = await matches_col.aggregate(pipeline_total).to_list(1)
        total_volume = res_total[0]["total"] if res_total else 0.0

        # Jogadores únicos
        unique_players = await matches_col.distinct(
            "challenger_id", {"guild_id": guild_id, "flow_type": "influencer_live"})

        return {
            "ok": True,
            "stats": {
                "active_rooms":    active_rooms,
                "matches_today":   matches_today,
                "volume_today":    volume_today,
                "total_matches":   total_matches,
                "total_volume":    total_volume,
                "unique_players":  len(unique_players),
            },
        }

    # ══════════════════════════════════════════════════════════
    # UPDATE QUEUE SIZE (chamado pelo queue service)
    # ══════════════════════════════════════════════════════════

    async def update_queue_size(self, influencer_id: str, guild_id: str, delta: int):
        await self._col().update_one(
            {"influencer_id": influencer_id, "guild_id": guild_id, "status": "active"},
            {"$inc": {"queue_size": delta}, "$set": {"updated_at": utcnow()}},
        )


influencer_live_room_service = InfluencerLiveRoomService()