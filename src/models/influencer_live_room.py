"""
influencer_live_room.py — Model da sala persistente do modo contra (Influencer Live).

Schema da collection 'influencer_live_rooms':
  _id                   ObjectId
  guild_id              str     — ID do servidor Discord
  influencer_id         str     — ID Discord do influencer (dono da sala)
  influencer_username   str
  status                str     — active | paused | inactive
  platform              str     — Mobile | Emulador | Misto
  game_mode             str     — 1x1 | 2x2 | 3x3 | 4x4
  entry_value           float   — valor de entrada padrão da sala
  custom_rules          str     — regras customizadas (texto livre)
  channel_id            str     — canal contra-<username>
  channel_name          str
  control_channel_id    str     — canal control-contra-<username>
  control_channel_name  str
  total_matches         int     — partidas realizadas na sala
  queue_size            int     — cache do tamanho da fila
  created_at            datetime
  updated_at            datetime
"""
from __future__ import annotations
from typing import Dict, Any, Optional
from bson import ObjectId
from utils.datetime_utils import utcnow


class InfluencerLiveRoom:

    # ── Status ────────────────────────────────────────────────
    STATUS_ACTIVE   = "active"
    STATUS_PAUSED   = "paused"
    STATUS_INACTIVE = "inactive"
    STATUSES        = [STATUS_ACTIVE, STATUS_PAUSED, STATUS_INACTIVE]

    # ── Plataformas ───────────────────────────────────────────
    PLATFORM_MOBILE    = "Mobile"
    PLATFORM_EMULADOR  = "Emulador"
    PLATFORM_MISTO     = "Misto"
    PLATFORMS          = [PLATFORM_MOBILE, PLATFORM_EMULADOR, PLATFORM_MISTO]

    # ── Modos (tipo de partida) ───────────────────────────────
    GAME_MODE_1X1  = "1x1"
    GAME_MODE_2X2  = "2x2"
    GAME_MODE_3X3  = "3x3"
    GAME_MODE_4X4  = "4x4"
    GAME_MODES     = [GAME_MODE_1X1, GAME_MODE_2X2, GAME_MODE_3X3, GAME_MODE_4X4]

    # Modos compatíveis por plataforma
    MODES_BY_PLATFORM: Dict[str, list] = {
        PLATFORM_MOBILE:   [GAME_MODE_1X1, GAME_MODE_2X2, GAME_MODE_3X3, GAME_MODE_4X4],
        PLATFORM_EMULADOR: [GAME_MODE_1X1, GAME_MODE_2X2, GAME_MODE_3X3, GAME_MODE_4X4],
        PLATFORM_MISTO:    [GAME_MODE_2X2, GAME_MODE_3X3, GAME_MODE_4X4],
    }

    def __init__(self, data: Dict[str, Any]):
        self._id                  = data.get("_id") or ObjectId()
        self.guild_id             = str(data.get("guild_id", ""))
        self.influencer_id        = str(data.get("influencer_id", ""))
        self.influencer_username  = data.get("influencer_username", "")
        self.status               = data.get("status", self.STATUS_INACTIVE)
        self.platform             = data.get("platform", self.PLATFORM_MOBILE)
        self.game_mode            = data.get("game_mode", self.GAME_MODE_1X1)
        self.entry_value          = float(data.get("entry_value", 0.0))
        self.custom_rules         = data.get("custom_rules")
        self.channel_id           = data.get("channel_id")
        self.channel_name         = data.get("channel_name", "")
        self.control_channel_id   = data.get("control_channel_id")
        self.control_channel_name = data.get("control_channel_name", "")
        self.total_matches        = int(data.get("total_matches", 0))
        self.queue_size           = int(data.get("queue_size", 0))
        self.created_at           = data.get("created_at", utcnow())
        self.updated_at           = data.get("updated_at", utcnow())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "_id":                  self._id,
            "guild_id":             self.guild_id,
            "influencer_id":        self.influencer_id,
            "influencer_username":  self.influencer_username,
            "status":               self.status,
            "platform":             self.platform,
            "game_mode":            self.game_mode,
            "entry_value":          self.entry_value,
            "custom_rules":         self.custom_rules,
            "channel_id":           self.channel_id,
            "channel_name":         self.channel_name,
            "control_channel_id":   self.control_channel_id,
            "control_channel_name": self.control_channel_name,
            "total_matches":        self.total_matches,
            "queue_size":           self.queue_size,
            "created_at":           self.created_at,
            "updated_at":           utcnow(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "InfluencerLiveRoom":
        raw_id = data.get("_id")
        if isinstance(raw_id, str):
            data = {**data, "_id": ObjectId(raw_id)}
        return cls(data)

    @staticmethod
    def create_document(
        guild_id: str,
        influencer_id: str,
        influencer_username: str,
        platform: str,
        game_mode: str,
        channel_id: str,
        channel_name: str,
        control_channel_id: str,
        control_channel_name: str,
        entry_value: float = 0.0,
        custom_rules: Optional[str] = None,
    ) -> Dict[str, Any]:
        now = utcnow()
        return {
            "_id":                  ObjectId(),
            "guild_id":             guild_id,
            "influencer_id":        influencer_id,
            "influencer_username":  influencer_username,
            "status":               InfluencerLiveRoom.STATUS_INACTIVE,
            "platform":             platform,
            "game_mode":            game_mode,
            "entry_value":          entry_value,
            "custom_rules":         custom_rules,
            "channel_id":           channel_id,
            "channel_name":         channel_name,
            "control_channel_id":   control_channel_id,
            "control_channel_name": control_channel_name,
            "total_matches":        0,
            "queue_size":           0,
            "created_at":           now,
            "updated_at":           now,
        }

    # ── Helpers ──────────────────────────────────────────────────

    @property
    def is_active(self) -> bool:
        return self.status == self.STATUS_ACTIVE

    def open(self):
        self.status = self.STATUS_ACTIVE

    def pause(self):
        self.status = self.STATUS_PAUSED

    def close(self):
        self.status = self.STATUS_INACTIVE

    def increment_matches(self):
        self.total_matches += 1

    @classmethod
    def validate_platform(cls, platform: str) -> bool:
        return platform in cls.PLATFORMS

    @classmethod
    def validate_game_mode(cls, game_mode: str, platform: str | None = None) -> bool:
        if game_mode not in cls.GAME_MODES:
            return False
        if platform:
            return game_mode in cls.MODES_BY_PLATFORM.get(platform, cls.GAME_MODES)
        return True

    @classmethod
    def get_label(cls, platform: str, game_mode: str) -> str:
        """Retorna label legível: ex. 'Mobile · 1x1'"""
        return f"{platform} · {game_mode}"

    def __repr__(self) -> str:
        return (
            f"<InfluencerLiveRoom influencer={self.influencer_username} "
            f"platform={self.platform} mode={self.game_mode} "
            f"status={self.status} value=R${self.entry_value}>"
        )
