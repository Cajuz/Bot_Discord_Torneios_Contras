from typing import Dict, List, Optional


class ChannelsConfig:
    """Configuração de canais e valores de apostas"""
    
    # Estrutura de canais por categoria
    CATEGORIES = {
        "MOBILE": {
            "emoji": "📱",
            "channels": [
                {"name": "1x1-mob", "players": 2},
                {"name": "2x2-mob", "players": 4},
                {"name": "3x3-mob", "players": 6},
                {"name": "4x4-mob", "players": 8}
            ]
        },
        "EMULADOR": {
            "emoji": "🖥️",
            "channels": [
                {"name": "1x1-emu", "players": 2},
                {"name": "2x2-emu", "players": 4},
                {"name": "3x3-emu", "players": 6},
                {"name": "4x4-emu", "players": 8}
            ]
        },
        "MISTO": {
            "emoji": "🔀",
            "channels": [
                {"name": "4x4-misto", "players": 8},
                {"name": "3x3-misto", "players": 6},
                {"name": "2x2-misto", "players": 4}
            ]
        }
    }
    
    # Valores de aposta disponíveis (em reais)
    BET_VALUES = [2.00, 5.00, 10.00, 20.00, 50.00, 100.00, 200.00]
    
    # Tipos de GEL disponíveis
    GEL_TYPES = ["normal", "infinito"]
    
    # Emojis por tipo de GEL
    GEL_EMOJIS = {
        "normal": "🔥",
        "infinito": "♾️"
    }
    
    # Cores por categoria (para embeds)
    CATEGORY_COLORS = {
        "MOBILE": 0x3498db,      # Azul
        "EMULADOR": 0x9b59b6,    # Roxo
        "MISTO": 0xe67e22        # Laranja
    }
    
    @staticmethod
    def get_all_channels() -> List[Dict]:
        """Retornar lista de todos os canais"""
        channels = []
        for category_data in ChannelsConfig.CATEGORIES.values():
            channels.extend(category_data["channels"])
        return channels
    
    @staticmethod
    def get_channel_players(channel_name: str) -> int:
        """Retornar número de jogadores necessários para um canal"""
        for category_data in ChannelsConfig.CATEGORIES.values():
            for channel in category_data["channels"]:
                if channel["name"] == channel_name:
                    return channel["players"]
        return 2  # Default para 1x1
    
    @staticmethod
    def get_channel_category(channel_name: str) -> str:
        """Retornar categoria de um canal"""
        for category_name, category_data in ChannelsConfig.CATEGORIES.items():
            for channel in category_data["channels"]:
                if channel["name"] == channel_name:
                    return category_name
        return "DESCONHECIDO"
    
    @staticmethod
    def get_channel_info(channel_name: str) -> Optional[Dict]:
        """Obter informações completas de um canal"""
        for category_name, category_data in ChannelsConfig.CATEGORIES.items():
            for channel in category_data["channels"]:
                if channel["name"] == channel_name:
                    return {
                        "name": channel["name"],
                        "players": channel["players"],
                        "category": category_name,
                        "emoji": category_data["emoji"]
                    }
        return None
    
    @staticmethod
    def get_category_emoji(category_name: str) -> str:
        """Obter emoji de uma categoria"""
        category_data = ChannelsConfig.CATEGORIES.get(category_name)
        return category_data["emoji"] if category_data else ""
    
    @staticmethod
    def get_category_color(category_name: str) -> int:
        """Obter cor de uma categoria (para embeds)"""
        return ChannelsConfig.CATEGORY_COLORS.get(category_name, 0x95a5a6)
    
    @staticmethod
    def get_gel_emoji(gel_type: str) -> str:
        """Obter emoji de um tipo de GEL"""
        return ChannelsConfig.GEL_EMOJIS.get(gel_type, "❓")
    
    @staticmethod
    def is_valid_channel(channel_name: str) -> bool:
        """Verificar se um canal é válido"""
        valid_channels = [ch["name"] for ch in ChannelsConfig.get_all_channels()]
        return channel_name in valid_channels
    
    @staticmethod
    def is_valid_bet_value(bet_value: float) -> bool:
        """Verificar se um valor de aposta é válido"""
        return bet_value in ChannelsConfig.BET_VALUES
    
    @staticmethod
    def is_valid_gel_type(gel_type: str) -> bool:
        """Verificar se um tipo de GEL é válido"""
        return gel_type in ChannelsConfig.GEL_TYPES
    
    @staticmethod
    def get_channel_display_name(channel_name: str) -> str:
        """Obter nome formatado de um canal para exibição"""
        suffix_map = {
            "mob": "Mobile",
            "emu": "Emulador",
            "misto": "Misto"
        }
        
        parts = channel_name.split("-")
        if len(parts) == 2:
            match_type = parts[0].upper()
            platform = suffix_map.get(parts[1], parts[1].capitalize())
            return f"{match_type} {platform}"
        
        return channel_name.upper()
    
    @staticmethod
    def format_bet_value(bet_value: float) -> str:
        """Formatar valor de aposta para exibição"""
        return f"R$ {bet_value:.2f}".replace(".", ",")
    
    @staticmethod
    def get_match_type_from_channel(channel_name: str) -> str:
        """Extrair tipo de partida do nome do canal"""
        return channel_name.split("-")[0] if "-" in channel_name else channel_name
    
    @staticmethod
    def get_platform_from_channel(channel_name: str) -> str:
        """Extrair plataforma do nome do canal"""
        return channel_name.split("-")[1] if "-" in channel_name else "desconhecido"
    
    @staticmethod
    def get_all_channel_names() -> List[str]:
        """Obter lista com apenas os nomes dos canais"""
        return [ch["name"] for ch in ChannelsConfig.get_all_channels()]
    
    @staticmethod
    def get_channels_by_category(category_name: str) -> List[Dict]:
        """Obter todos os canais de uma categoria específica"""
        category_data = ChannelsConfig.CATEGORIES.get(category_name)
        return category_data["channels"] if category_data else []
