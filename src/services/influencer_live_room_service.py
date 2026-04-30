"""
influencer_live_room_service.py
Gerencia o ciclo de vida das salas do modo contra (InfluencerLiveRoom).
"""
from __future__ import annotations
import discord
from utils.logger import logger
from utils.datetime_utils import utcnow
from config.database import db
from models.influencer_live_room import InfluencerLiveRoom

COLLECTION = "influencer_live_rooms"

# Sentinel: distingue "não enviado" de "enviado vazio" em custom_rules
_UNSET = object()


class InfluencerLiveRoomService:

    def _col(self):
        return db.get_collection(COLLECTION)

    # ═══════════════════════════════════════════════════════
    # ATIVAR SALA
    # ═══════════════════════════════════════════════════════

    async def ativar_sala(
        self,
        guild: discord.Guild,
        influencer: discord.Member,
        platform: str,
        game_mode: str,
        entry_value: float,
        custom_rules: str | None = None,
        ctrl_channel: discord.TextChannel | None = None,
    ) -> dict:
        if not InfluencerLiveRoom.validate_platform(platform):
            return {"ok": False, "msg": f"Plataforma inválida: `{platform}`. Use: {', '.join(InfluencerLiveRoom.PLATFORMS)}"}

        if not InfluencerLiveRoom.validate_game_mode(game_mode, platform):
            allowed = InfluencerLiveRoom.MODES_BY_PLATFORM.get(platform, InfluencerLiveRoom.GAME_MODES)
            return {"ok": False, "msg": f"Modo `{game_mode}` inválido para {platform}. Disponíveis: {', '.join(allowed)}"}

        if entry_value <= 0:
            return {"ok": False, "msg": "O valor de entrada deve ser maior que zero."}

        col = self._col()
        existing = await col.find_one({
            "influencer_id": str(influencer.id),
            "guild_id":      str(guild.id),
            "status":        {"$in": ["active", "paused"]},
        })
        if existing:
            return {"ok": False, "msg": "Você já tem uma sala ativa. Desative-a primeiro."}

        from services.channel_service import permission_service

        contra_channel = await permission_service.create_contra_channel(guild, influencer)

        if ctrl_channel is None:
            ctrl_channel = await permission_service.create_control_channel(guild, influencer)

        now = utcnow()
        doc = {
            "influencer_id":        str(influencer.id),
            "guild_id":             str(guild.id),
            "influencer_username":  influencer.display_name,
            "status":               InfluencerLiveRoom.STATUS_ACTIVE,
            "platform":             platform,
            "game_mode":            game_mode,
            "entry_value":          entry_value,
            "custom_rules":         custom_rules,
            "channel_id":           str(contra_channel.id),
            "channel_name":         contra_channel.name,
            "control_channel_id":   str(ctrl_channel.id),
            "control_channel_name": ctrl_channel.name,
            "total_matches":        0,
            "queue_size":           0,
            "created_at":           now,
            "updated_at":           now,
        }
        await col.insert_one(doc)
        room = InfluencerLiveRoom(doc)

        from views.influencer_live_view import ContraRoomView, build_contra_room_embed
        embed = build_contra_room_embed(room, queue_size=0)
        view  = ContraRoomView(influencer_id=influencer.id, guild_id=guild.id)
        await contra_channel.send(embed=embed, view=view)

        from views.influencer_live_control_view import ContraControlView, build_control_embed
        ctrl_embed = build_control_embed(room)
        ctrl_view  = ContraControlView(influencer_id=influencer.id, guild_id=guild.id)
        await ctrl_channel.send(embed=ctrl_embed, view=ctrl_view)

        logger.info(
            f"[InfluencerLiveRoom] Sala ativada — {influencer.name} "
            f"guild {guild.id} {platform} {game_mode} R${entry_value:.2f}"
        )
        return {
            "ok": True, "msg": "Sala ativada.",
            "room": room,
            "channel": contra_channel,
            "control_channel": ctrl_channel,
        }

    # ═══════════════════════════════════════════════════════
    # DESATIVAR SALA
    # ═══════════════════════════════════════════════════════

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

        from services.influencer_live_queue_service import influencer_live_queue_service
        await influencer_live_queue_service.clear_queue(
            influencer_id=str(influencer.id),
            guild_id=str(guild.id),
        )

        from services.channel_service import permission_service
        await permission_service.delete_contra_channel(guild, room.channel_name)
        if room.control_channel_name:
            await permission_service.delete_control_channel(guild, room.control_channel_name)

        await col.update_one(
            {"_id": doc["_id"]},
            {"$set": {"status": InfluencerLiveRoom.STATUS_INACTIVE, "updated_at": utcnow()}},
        )

        reason = f"por ADM {forced_by.name}" if forced_by else "pelo influencer"
        logger.info(
            f"[InfluencerLiveRoom] Sala desativada {reason} — "
            f"influencer {influencer.name} guild {guild.id}"
        )
        return {"ok": True, "msg": "Sala desativada. Canais removidos e fila encerrada."}

    # ═══════════════════════════════════════════════════════
    # EDITAR SALA
    # ═══════════════════════════════════════════════════════

    async def editar_sala(
        self,
        influencer_id: str,
        guild_id: str,
        entry_value: float | None = None,
        platform: str | None = None,
        game_mode: str | None = None,
        custom_rules: object = _UNSET,  # usa sentinel para distinguir "não enviado" de "limpar"
    ) -> dict:
        col = self._col()
        doc = await col.find_one({
            "influencer_id": influencer_id,
            "guild_id":      guild_id,
            "status":        {"$in": ["active", "paused"]},
        })
        if not doc:
            return {"ok": False, "msg": "Nenhuma sala ativa ou pausada encontrada."}

        if platform is not None and not InfluencerLiveRoom.validate_platform(platform):
            return {"ok": False, "msg": f"Plataforma inválida: `{platform}`."}

        effective_platform = platform or doc.get("platform", InfluencerLiveRoom.PLATFORM_MOBILE)
        if game_mode is not None and not InfluencerLiveRoom.validate_game_mode(game_mode, effective_platform):
            allowed = InfluencerLiveRoom.MODES_BY_PLATFORM.get(effective_platform, InfluencerLiveRoom.GAME_MODES)
            return {"ok": False, "msg": f"Modo `{game_mode}` inválido para {effective_platform}. Disponíveis: {', '.join(allowed)}"}

        if entry_value is not None and entry_value <= 0:
            return {"ok": False, "msg": "O valor deve ser maior que zero."}

        updates: dict = {"updated_at": utcnow()}
        if entry_value is not None:
            updates["entry_value"] = entry_value
        if platform is not None:
            updates["platform"] = platform
        if game_mode is not None:
            updates["game_mode"] = game_mode
        if custom_rules is not _UNSET:
            # String vazia ou None → limpa as regras; qualquer texto → salva
            updates["custom_rules"] = custom_rules.strip() if isinstance(custom_rules, str) and custom_rules.strip() else None

        await col.update_one({"_id": doc["_id"]}, {"$set": updates})
        doc.update(updates)
        room = InfluencerLiveRoom(doc)

        logger.info(f"[InfluencerLiveRoom] Sala editada — influencer {influencer_id}")
        return {"ok": True, "msg": "Sala atualizada.", "room": room}

    # ═══════════════════════════════════════════════════════
    # GET / LIST
    # ═══════════════════════════════════════════════════════

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

    # ═══════════════════════════════════════════════════════
    # UPDATE QUEUE SIZE
    # ═══════════════════════════════════════════════════════

    async def update_queue_size(self, influencer_id: str, guild_id: str, delta: int):
        await self._col().update_one(
            {
                "influencer_id": influencer_id,
                "guild_id":      guild_id,
                "status":        {"$in": ["active", "paused"]},
            },
            {"$inc": {"queue_size": delta}, "$set": {"updated_at": utcnow()}},
        )

    # ═══════════════════════════════════════════════════════
    # STATS
    # ═══════════════════════════════════════════════════════

    async def get_stats(self, guild_id: str) -> dict:
        today_start = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        matches_col = db.get_collection("matches")

        active_rooms = await self._col().count_documents(
            {"guild_id": guild_id, "status": "active"})

        matches_today = await matches_col.count_documents({
            "guild_id":   guild_id,
            "flow_type":  "influencer_live",
            "status":     "finalizada",
            "created_at": {"$gte": today_start},
        })

        pipeline_today = [
            {"$match": {
                "guild_id":   guild_id,
                "flow_type":  "influencer_live",
                "status":     "finalizada",
                "created_at": {"$gte": today_start},
            }},
            {"$group": {"_id": None, "total": {"$sum": "$bet_value"}}},
        ]
        res_today    = await matches_col.aggregate(pipeline_today).to_list(1)
        volume_today = res_today[0]["total"] if res_today else 0.0

        total_matches = await matches_col.count_documents({
            "guild_id":  guild_id,
            "flow_type": "influencer_live",
            "status":    "finalizada",
        })
        pipeline_total = [
            {"$match": {"guild_id": guild_id, "flow_type": "influencer_live", "status": "finalizada"}},
            {"$group": {"_id": None, "total": {"$sum": "$bet_value"}}},
        ]
        res_total    = await matches_col.aggregate(pipeline_total).to_list(1)
        total_volume = res_total[0]["total"] if res_total else 0.0

        unique_players = await matches_col.distinct(
            "challenger_id", {"guild_id": guild_id, "flow_type": "influencer_live"})

        return {
            "ok": True,
            "stats": {
                "active_rooms":   active_rooms,
                "matches_today":  matches_today,
                "volume_today":   volume_today,
                "total_matches":  total_matches,
                "total_volume":   total_volume,
                "unique_players": len(unique_players),
            },
        }


influencer_live_room_service = InfluencerLiveRoomService()
