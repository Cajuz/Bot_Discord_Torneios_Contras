"""
channels_config.py — Configuração dos canais de PARTIDAS.
Nomes de canais fixos do servidor estão em services/channel_service.py.
"""
from typing import Dict, List, Optional
from services.channel_service import MEMBER_ROLE_NAME, CHANNEL_STRUCTURE


class ChannelsConfig:
    # Aliases para compatibilidade com imports antigos
    MEMBER_ROLE_NAME      = MEMBER_ROLE_NAME
    INVITES_CHANNEL       = "invites"            # STATUS_BOT_CHANNEL (canal único)
    RATE_LIMIT_CHANNEL    = "rate-limit-logs"
    EXPOSED_CHANNEL       = "exposed"
    ANALYST_QUEUE_CHANNEL = "painel-analista"
    SUPORTE_CHANNEL_NAME  = "solicitar-suporte"

    # Estrutura do servidor — vem de channel_service
    CHANNEL_STRUCTURE = CHANNEL_STRUCTURE

    # ── Partidas ────────────────────────────────────────────────
CATEGORIES = {
        "MOBILE":   {"emoji": "📱", "channels": [
            {"name": "1x1-mob",  "players": 2, "gel_types": ["normal", "infinito"]},
            {"name": "2x2-mob",  "players": 2, "gel_types": ["normal"]},
            {"name": "3x3-mob",  "players": 2, "gel_types": ["normal"]},
            {"name": "4x4-mob",  "players": 2, "gel_types": ["normal"]},
        ]},
        "EMULADOR": {"emoji": "🖥️", "channels": [
            {"name": "1x1-emu",  "players": 2, "gel_types": ["normal"]},
            {"name": "2x2-emu",  "players": 2, "gel_types": ["normal"]},
            {"name": "3x3-emu",  "players": 2, "gel_types": ["normal"]},
            {"name": "4x4-emu",  "players": 2, "gel_types": ["normal"]},
        ]},
        "MISTO":    {"emoji": "🔀", "channels": [
            {"name": "4x4-misto", "players": 2, "gel_types": ["normal"]},
            {"name": "3x3-misto", "players": 2, "gel_types": ["normal"]},
            {"name": "2x2-misto", "players": 2, "gel_types": ["normal"]},
        ]},
    }

    BET_VALUES      = [2.00, 5.00, 10.00, 20.00, 50.00, 100.00, 200.00]
    GEL_TYPES       = ["normal", "infinito"]
    GEL_EMOJIS      = {"normal": "🔥", "infinito": "♾️"}
    CATEGORY_COLORS = {"MOBILE": 0xFFD54F, "EMULADOR": 0xFFA726, "MISTO": 0xFFB300}

    @staticmethod
    def get_all_channels() -> List[Dict]:
        channels = []
        for cat in ChannelsConfig.CATEGORIES.values():
            channels.extend(cat["channels"])
        return channels

    @staticmethod
    def get_all_channel_names() -> List[str]:
        return [ch["name"] for ch in ChannelsConfig.get_all_channels()]

    @staticmethod
    def get_channel_gel_types(channel_name: str) -> List[str]:
        for cat in ChannelsConfig.CATEGORIES.values():
            for ch in cat["channels"]:
                if ch["name"] == channel_name:
                    return ch.get("gel_types", ["normal"])
        return ["normal"]

    @staticmethod
    def has_gel_infinito(channel_name: str) -> bool:
        return "infinito" in ChannelsConfig.get_channel_gel_types(channel_name)

    @staticmethod
    def get_channel_category(channel_name: str) -> str:
        for cat_name, cat in ChannelsConfig.CATEGORIES.items():
            for ch in cat["channels"]:
                if ch["name"] == channel_name:
                    return cat_name
        return "DESCONHECIDO"

    @staticmethod
    def get_channel_info(channel_name: str) -> Optional[Dict]:
        for cat_name, cat in ChannelsConfig.CATEGORIES.items():
            for ch in cat["channels"]:
                if ch["name"] == channel_name:
                    return {
                        "name":      ch["name"],
                        "players":   2,
                        "gel_types": ch.get("gel_types", ["normal"]),
                        "category":  cat_name,
                        "emoji":     cat["emoji"],
                    }
        return None

    @staticmethod
    def get_channels_by_category(category_name: str) -> List[Dict]:
        cat = ChannelsConfig.CATEGORIES.get(category_name)
        return cat["channels"] if cat else []

    @staticmethod
    def get_category_emoji(category_name: str) -> str:
        cat = ChannelsConfig.CATEGORIES.get(category_name)
        return cat["emoji"] if cat else ""

    @staticmethod
    def get_category_color(category_name: str) -> int:
        return ChannelsConfig.CATEGORY_COLORS.get(category_name, 0xFFD54F)

    @staticmethod
    def get_gel_emoji(gel_type: str) -> str:
        return ChannelsConfig.GEL_EMOJIS.get(gel_type, "❓")

    @staticmethod
    def is_valid_gel_type(gel_type: str) -> bool:
        return gel_type in ChannelsConfig.GEL_TYPES

    @staticmethod
    def is_valid_channel(channel_name: str) -> bool:
        return channel_name in ChannelsConfig.get_all_channel_names()

    @staticmethod
    def is_valid_bet_value(bet_value: float) -> bool:
        return bet_value in ChannelsConfig.BET_VALUES

    @staticmethod
    def get_channel_display_name(channel_name: str) -> str:
        suffix_map = {"mob": "Mobile", "emu": "Emulador", "misto": "Misto"}
        parts = channel_name.split("-")
        if len(parts) == 2:
            return f"{parts[0].upper()} {suffix_map.get(parts[1], parts[1].capitalize())}"
        return channel_name.upper()

    @staticmethod
    def format_bet_value(bet_value: float) -> str:
        return f"R$ {bet_value:.2f}".replace(".", ",")

    @staticmethod
    def get_match_type_from_channel(channel_name: str) -> str:
        return channel_name.split("-")[0] if "-" in channel_name else channel_name

    @staticmethod
    def get_platform_from_channel(channel_name: str) -> str:
        return channel_name.split("-")[1] if "-" in channel_name else "desconhecido"
