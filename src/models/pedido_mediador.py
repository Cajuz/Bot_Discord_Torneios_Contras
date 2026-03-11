from datetime import datetime
from typing import Optional, Dict, Any
from bson import ObjectId

class PaymentConfirmation:
    """Modelo de Confirmação de Pagamento no MongoDB"""

    def __init__(self, data: Dict[str, Any]):
        self._id                 = data.get('_id')
        self.discord_id          = data.get('discord_id')
        self.username            = data.get('username')
        self.pix_key             = data.get('pix_key')
        self.role_received_date  = data.get('role_received_date', datetime.utcnow())
        self.confirmed_by_admin  = data.get('confirmed_by_admin')
        self.confirmation_date   = data.get('confirmation_date')
        self.created_at          = data.get('created_at', datetime.utcnow())
        self.updated_at          = data.get('updated_at', datetime.utcnow())

    def mark_role_received(self):
        """Atualiza a data de recebimento do cargo"""
        self.role_received_date = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def confirm_payment(self, admin_name: str, pix_key: str):
        """Registrar confirmação do pagamento pelo ADM"""
        self.confirmed_by_admin = admin_name
        self.pix_key = pix_key
        self.confirmation_date = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        """Retorna dicionário pronto para salvar no MongoDB"""
        return {
            '_id': self._id,
            'discord_id': self.discord_id,
            'username': self.username,
            'pix_key': self.pix_key,
            'role_received_date': self.role_received_date,
            'confirmed_by_admin': self.confirmed_by_admin,
            'confirmation_date': self.confirmation_date,
            'created_at': self.created_at,
            'updated_at': datetime.utcnow()
        }

    @staticmethod
    def create_document(discord_id: str, username: str, pix_key: str = "") -> Dict[str, Any]:
        """Cria um documento inicial para o MongoDB"""
        now = datetime.utcnow()
        return {
            'discord_id': discord_id,
            'username': username,
            'pix_key': pix_key,
            'role_received_date': now,
            'confirmed_by_admin': None,
            'confirmation_date': None,
            'created_at': now,
            'updated_at': now
        }