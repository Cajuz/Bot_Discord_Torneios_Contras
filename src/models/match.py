from datetime import datetime
from typing import Optional, Dict, Any, List
from bson import ObjectId

class Match:
    """Modelo de Partida (Atualizado)"""
    
    STATUS_WAITING = 'waiting_players'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_COMPLETED = 'completed'
    STATUS_CANCELLED = 'cancelled'
    
    def __init__(self, data: Dict[str, Any]):
        self._id = data.get('_id')
        self.creator_id = data.get('creator_id')
        self.channel_name = data.get('channel_name')
        self.match_type = data.get('match_type')  # 1x1, 2x2, 3x3, 4x4
        self.platform = data.get('platform')  # mob, emu, misto
        self.bet_value = data.get('bet_value')  # 2, 5, 10, 20, 50, 100, 200
        self.mediator_id = data.get('mediator_id')
        self.mediator_discord_id = data.get('mediator_discord_id')
        self.status = data.get('status', self.STATUS_WAITING)
        self.players = data.get('players', [])
        self.max_players = data.get('max_players', 2)
        self.thread_id = data.get('thread_id')
        self.started_at = data.get('started_at')
        self.completed_at = data.get('completed_at')
        self.created_at = data.get('created_at', datetime.now())
        self.updated_at = data.get('updated_at', datetime.now())
        
        # Resultado
        self.winner_team = data.get('winner_team')  # 'team1' ou 'team2'
        self.proof_url = data.get('proof_url')  # Screenshot/vídeo da vitória
    
    def to_dict(self) -> Dict[str, Any]:
        """Converter para dicionário"""
        return {
            '_id': self._id,
            'creator_id': self.creator_id,
            'channel_name': self.channel_name,
            'match_type': self.match_type,
            'platform': self.platform,
            'bet_value': self.bet_value,
            'mediator_id': self.mediator_id,
            'mediator_discord_id': self.mediator_discord_id,
            'status': self.status,
            'players': self.players,
            'max_players': self.max_players,
            'thread_id': self.thread_id,
            'started_at': self.started_at,
            'completed_at': self.completed_at,
            'created_at': self.created_at,
            'updated_at': datetime.now(),
            'winner_team': self.winner_team,
            'proof_url': self.proof_url
        }
