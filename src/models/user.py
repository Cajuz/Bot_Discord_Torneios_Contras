from datetime import datetime
from typing import Dict, Any, Optional
from bson import ObjectId


class User:
    """Modelo de Usuário"""

    def __init__(self, data: Dict[str, Any]):
        self._id                = data.get('_id')
        self.discord_id         = data.get('discord_id')
        self.username           = data.get('username')
        self.has_accepted_rules = data.get('has_accepted_rules', False)
        self.rules_accepted_at  = data.get('rules_accepted_at')
        self.joined_at          = data.get('joined_at', datetime.utcnow())
        self.is_active          = data.get('is_active', True)
        self.onboarding_result  = data.get('onboarding_result', 'pendente')  # ✅ novo

        stats = data.get('statistics', {})
        self.total_matches = stats.get('total_matches', 0)
        self.wins          = stats.get('wins', 0)
        self.losses        = stats.get('losses', 0)

        self.created_at = data.get('created_at', datetime.utcnow())
        self.updated_at = data.get('updated_at', datetime.utcnow())

    def accept_rules(self):
        self.has_accepted_rules = True
        self.rules_accepted_at  = datetime.utcnow()
        self.onboarding_result  = 'aceito'  # ✅ atualiza junto

    def to_dict(self) -> Dict[str, Any]:
        return {
            '_id':                  self._id,
            'discord_id':           self.discord_id,
            'username':             self.username,
            'has_accepted_rules':   self.has_accepted_rules,
            'rules_accepted_at':    self.rules_accepted_at,
            'joined_at':            self.joined_at,
            'is_active':            self.is_active,
            'onboarding_result':    self.onboarding_result,  # ✅ novo
            'statistics': {
                'total_matches': self.total_matches,
                'wins':          self.wins,
                'losses':        self.losses
            },
            'created_at': self.created_at,
            'updated_at': datetime.utcnow()
        }

    @staticmethod
    def create_document(discord_id: str, username: str) -> Dict[str, Any]:
        """Criar novo documento de usuário"""
        now = datetime.utcnow()
        return {
            'discord_id':          discord_id,
            'username':            username,
            'has_accepted_rules':  False,
            'rules_accepted_at':   None,
            'joined_at':           now,
            'is_active':           True,
            'onboarding_result':   'pendente',  # ✅ novo — padrão ao entrar
            'statistics': {
                'total_matches': 0,
                'wins':          0,
                'losses':        0
            },
            'created_at': now,
            'updated_at': now
        }
