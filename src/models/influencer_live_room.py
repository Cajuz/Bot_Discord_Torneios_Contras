"""
influencer_live_room.py — Model da sala persistente do modo contra (Influencer Live).

Schema da collection 'influencer_live_rooms':
  _id                 ObjectId
  guild_id            int     — ID do servidor Discord
  influencer_id       int     — ID Discord do influencer (dono da sala)
  influencer_username str
  channel_id          int     — canal contra-username criado
  channel_name        str
  is_active           bool    — sala aberta/fechada
  entry_value         float   — valor de entrada padrão da sala
  custom_rules        str     — regras customizadas (texto livre)
  game_mode           str     — ex: "1v1", "2v2"
  total_matches       int     — partidas realizadas na sala
  created_at          datetime
  updated_at          datetime
"""
from __future__ import annotations
from typing import Dict, Any, Optional
from bson import ObjectId
from utils.datetime_utils import utcnow


class InfluencerLiveRoom:

    GAME_MODE_1V1 = "1v1"
    GAME_MODE_2V2 = "2v2"
    GAME_MODES    = [GAME_MODE_1V1, GAME_MODE_2V2]

    def __init__(self, data: Dict[str, Any]):
        self._id                  = data.get("_id") or ObjectId()
        self.guild_id             = data.get("guild_id")
        self.influencer_id        = data.get("influencer_id")
        self.influencer_username  = data.get("influencer_username", "")
        self.channel_id           = data.get("channel_id")
        self.channel_name         = data.get("channel_name", "")
        self.is_active            = data.get("is_active", False)
        self.entry_value          = data.get("entry_value", 0.0)
        self.custom_rules         = data.get("custom_rules")
        self.game_mode            = data.get("game_mode", self.GAME_MODE_1V1)
        self.total_matches        = data.get("total_matches", 0)
        self.created_at           = data.get("created_at", utcnow())
        self.updated_at           = data.get("updated_at", utcnow())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "_id":                 self._id,
            "guild_id":            self.guild_id,
            "influencer_id":       self.influencer_id,
            "influencer_username": self.influencer_username,
            "channel_id":          self.channel_id,
            "channel_name":        self.channel_name,
            "is_active":           self.is_active,
            "entry_value":         self.entry_value,
            "custom_rules":        self.custom_rules,
            "game_mode":           self.game_mode,
            "total_matches":       self.total_matches,
            "created_at":          self.created_at,
            "updated_at":          utcnow(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "InfluencerLiveRoom":
        raw_id = data.get("_id")
        if isinstance(raw_id, str):
            data = {**data, "_id": ObjectId(raw_id)}
        return cls(data)

    @staticmethod
    def create_document(
        guild_id: int,
        influencer_id: int,
        influencer_username: str,
        channel_id: int,
        channel_name: str,
        entry_value: float = 0.0,
        game_mode: str = "1v1",
        custom_rules: Optional[str] = None,
    ) -> Dict[str, Any]:
        now = utcnow()
        return {
            "_id":                 ObjectId(),
            "guild_id":            guild_id,
            "influencer_id":       influencer_id,
            "influencer_username": influencer_username,
            "channel_id":          channel_id,
            "channel_name":        channel_name,
            "is_active":           False,
            "entry_value":         entry_value,
            "custom_rules":        custom_rules,
            "game_mode":           game_mode,
            "total_matches":       0,
            "created_at":          now,
            "updated_at":          now,
        }

    # ── Helpers ──────────────────────────────────────────────────

    def open(self):
        """Abre a sala para receber desafiantes."""
        self.is_active = True

    def close(self):
        """Fecha a sala."""
        self.is_active = False

    def increment_matches(self):
        self.total_matches += 1

    def __repr__(self) -> str:
        return (
            f"<InfluencerLiveRoom influencer={self.influencer_username} "
            f"mode={self.game_mode} active={self.is_active} "
            f"value=R${self.entry_value}>"
        )