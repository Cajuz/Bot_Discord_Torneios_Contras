from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from bson import ObjectId

class Mediator:
    """Modelo de Mediador"""
    
    def __init__(self, data: Dict[str, Any]):
        self._id = data.get('_id')
        self.discord_id = data.get('discord_id')
        self.username = data.get('username')
        self.position = data.get('position', 0)
        self.is_active = data.get('is_active', True)
        
        # Estatísticas
        stats = data.get('statistics', {})
        self.total_matches = stats.get('total_matches', 0)
        self.last_assigned_at = stats.get('last_assigned_at')
        self.matches_in_last_8_minutes = stats.get('matches_in_last_8_minutes', 0)
        self.last_reset_at = stats.get('last_reset_at', datetime.now())
        
        self.created_at = data.get('created_at', datetime.now())
        self.updated_at = data.get('updated_at', datetime.now())
    
    def can_mediate(self) -> bool:
        """Verificar se o mediador pode mediar (máximo 5 partidas em 8 minutos)"""
        now = datetime.now()
        eight_minutes_ago = now - timedelta(minutes=8)
        
        # Resetar contador se passou 8 minutos desde o último reset
        if self.last_reset_at < eight_minutes_ago:
            self.matches_in_last_8_minutes = 0
            self.last_reset_at = now
        
        return self.is_active and self.matches_in_last_8_minutes < 5
    
    def assign_match(self):
        """Registrar nova partida mediada"""
        self.total_matches += 1
        self.last_assigned_at = datetime.now()
        self.matches_in_last_8_minutes += 1
    
    def to_dict(self) -> Dict[str, Any]:
        """Converter para dicionário"""
        return {
            '_id': self._id,
            'discord_id': self.discord_id,
            'username': self.username,
            'position': self.position,
            'is_active': self.is_active,
            'statistics': {
                'total_matches': self.total_matches,
                'last_assigned_at': self.last_assigned_at,
                'matches_in_last_8_minutes': self.matches_in_last_8_minutes,
                'last_reset_at': self.last_reset_at
            },
            'created_at': self.created_at,
            'updated_at': datetime.now()
        }
    
    @staticmethod
    def create_document(discord_id: str, username: str, position: int = 1) -> Dict[str, Any]:
        """Criar novo documento de mediador"""
        now = datetime.now()
        return {
            'discord_id': discord_id,
            'username': username,
            'position': position,
            'is_active': True,
            'statistics': {
                'total_matches': 0,
                'last_assigned_at': None,
                'matches_in_last_8_minutes': 0,
                'last_reset_at': now
            },
            'created_at': now,
            'updated_at': now
        }
