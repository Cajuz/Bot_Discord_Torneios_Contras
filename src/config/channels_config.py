from typing import Dict, List, Optional


class ChannelsConfig:
    """Configuração de canais e valores de apostas"""

    # Todos os modos usam 2 jogadores (1 por time/lado)
    # 1x1-mob: tem fila gel normal + gel infinito
    # Demais: apenas fila gel normal
    CATEGORIES = {
        "MOBILE": {
            "emoji": "📱",
            "channels": [
                {"name": "1x1-mob",  "players": 2, "gel_types": ["normal", "infinito"]},
                {"name": "2x2-mob",  "players": 2, "gel_types": ["normal"]},
                {"name": "3x3-mob",  "players": 2, "gel_types": ["normal"]},
                {"name": "4x4-mob",  "players": 2, "gel_types": ["normal"]},
            ]
        },
        "EMULADOR": {
            "emoji": "🖥️",
            "channels": [
                {"name": "1x1-emu",  "players": 2, "gel_types": ["normal"]},
                {"name": "2x2-emu",  "players": 2, "gel_types": ["normal"]},
                {"name": "3x3-emu",  "players": 2, "gel_types": ["normal"]},
                {"name": "4x4-emu",  "players": 2, "gel_types": ["normal"]},
            ]
        },
        "MISTO": {
            "emoji": "🔀",
            "channels": [
                {"name": "4x4-misto", "players": 2, "gel_types": ["normal"]},
                {"name": "3x3-misto", "players": 2, "gel_types": ["normal"]},
                {"name": "2x2-misto", "players": 2, "gel_types": ["normal"]},
            ]
        }
    }

    # Valores de aposta disponíveis (em reais)
    BET_VALUES = [2.00, 5.00, 10.00, 20.00, 50.00, 100.00, 200.00]

    # Tipos de GEL disponíveis globalmente
    GEL_TYPES = ["normal", "infinito"]

    # Emojis por tipo de GEL
    GEL_EMOJIS = {
        "normal":   "🔥",
        "infinito": "♾️"
    }

    # Cores por categoria (para embeds)
    CATEGORY_COLORS = {
        "MOBILE":   0x3498db,  # Azul
        "EMULADOR": 0x9b59b6,  # Roxo
        "MISTO":    0xe67e22   # Laranja
    }

    # ─────────────────────────────────────────────
    # Canais
    # ─────────────────────────────────────────────

    @staticmethod
    def get_all_channels() -> List[Dict]:
        channels = []
        for category_data in ChannelsConfig.CATEGORIES.values():
            channels.extend(category_data["channels"])
        return channels

    @staticmethod
    def get_all_channel_names() -> List[str]:
        return [ch["name"] for ch in ChannelsConfig.get_all_channels()]

    @staticmethod
    def get_channel_players(channel_name: str) -> int:
        """Sempre retorna 2 — todos os modos usam 2 jogadores na fila"""
        return 2

    @staticmethod
    def get_channel_gel_types(channel_name: str) -> List[str]:
        """Retorna os tipos de GEL disponíveis para o canal"""
        for category_data in ChannelsConfig.CATEGORIES.values():
            for channel in category_data["channels"]:
                if channel["name"] == channel_name:
                    return channel.get("gel_types", ["normal"])
        return ["normal"]

    @staticmethod
    def has_gel_infinito(channel_name: str) -> bool:
        """Verifica se o canal tem fila de gel infinito (só 1x1-mob)"""
        return "infinito" in ChannelsConfig.get_channel_gel_types(channel_name)

    @staticmethod
    def get_channel_category(channel_name: str) -> str:
        for category_name, category_data in ChannelsConfig.CATEGORIES.items():
            for channel in category_data["channels"]:
                if channel["name"] == channel_name:
                    return category_name
        return "DESCONHECIDO"

    @staticmethod
    def get_channel_info(channel_name: str) -> Optional[Dict]:
        for category_name, category_data in ChannelsConfig.CATEGORIES.items():
            for channel in category_data["channels"]:
                if channel["name"] == channel_name:
                    return {
                        "name":      channel["name"],
                        "players":   2,
                        "gel_types": channel.get("gel_types", ["normal"]),
                        "category":  category_name,
                        "emoji":     category_data["emoji"]
                    }
        return None

    @staticmethod
    def get_channels_by_category(category_name: str) -> List[Dict]:
        category_data = ChannelsConfig.CATEGORIES.get(category_name)
        return category_data["channels"] if category_data else []

    # ─────────────────────────────────────────────
    # Categorias
    # ─────────────────────────────────────────────

    @staticmethod
    def get_category_emoji(category_name: str) -> str:
        category_data = ChannelsConfig.CATEGORIES.get(category_name)
        return category_data["emoji"] if category_data else ""

    @staticmethod
    def get_category_color(category_name: str) -> int:
        return ChannelsConfig.CATEGORY_COLORS.get(category_name, 0x95a5a6)

    # ─────────────────────────────────────────────
    # GEL
    # ─────────────────────────────────────────────

    @staticmethod
    def get_gel_emoji(gel_type: str) -> str:
        return ChannelsConfig.GEL_EMOJIS.get(gel_type, "❓")

    @staticmethod
    def is_valid_gel_type(gel_type: str) -> bool:
        return gel_type in ChannelsConfig.GEL_TYPES

    # ─────────────────────────────────────────────
    # Validações
    # ─────────────────────────────────────────────

    @staticmethod
    def is_valid_channel(channel_name: str) -> bool:
        return channel_name in ChannelsConfig.get_all_channel_names()

    @staticmethod
    def is_valid_bet_value(bet_value: float) -> bool:
        return bet_value in ChannelsConfig.BET_VALUES

    # ─────────────────────────────────────────────
    # Formatação / Display
    # ─────────────────────────────────────────────

    @staticmethod
    def get_channel_display_name(channel_name: str) -> str:
        suffix_map = {
            "mob":   "Mobile",
            "emu":   "Emulador",
            "misto": "Misto"
        }
        parts = channel_name.split("-")
        if len(parts) == 2:
            match_type = parts[0].upper()
            platform   = suffix_map.get(parts[1], parts[1].capitalize())
            return f"{match_type} {platform}"
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
