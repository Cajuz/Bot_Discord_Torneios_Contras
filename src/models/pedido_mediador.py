from datetime import datetime
from utils.datetime_utils import utcnow
from typing import Dict, Any
from bson import ObjectId

class PaymentConfirmation:

    def __init__(self, data: Dict[str, Any]):

        self._id = data.get('_id') if isinstance(data.get('_id'), ObjectId) else None
        self.discord_id = data.get('discord_id')
        self.username = data.get('username')
        self.pix_key = data.get('pix_key')

        self.role_received_date = data.get('role_received_date', utcnow())
        self.confirmed_by_admin = data.get('confirmed_by_admin')
        self.confirmation_date = data.get('confirmation_date')

        self.created_at = data.get('created_at', utcnow())
        self.updated_at = data.get('updated_at', utcnow())

    def mark_role_received(self):
        self.role_received_date = utcnow()
        self.updated_at = utcnow()

    def confirm_payment(self, admin_name: str, pix_key: str):

        self.confirmed_by_admin = admin_name
        self.pix_key = pix_key
        self.confirmation_date = utcnow()
        self.updated_at = utcnow()

    def to_dict(self) -> Dict[str, Any]:

        data = {
            'discord_id': self.discord_id,
            'username': self.username,
            'pix_key': self.pix_key,
            'role_received_date': self.role_received_date,
            'confirmed_by_admin': self.confirmed_by_admin,
            'confirmation_date': self.confirmation_date,
            'created_at': self.created_at,
            'updated_at': utcnow()
        }

        if self._id:
            data['_id'] = self._id

        return data

    @staticmethod
    def create_document(discord_id: str, username: str, pix_key: str = "") -> Dict[str, Any]:

        now = utcnow()

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
    
