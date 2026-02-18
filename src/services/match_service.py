from typing import Dict, Any, List, Optional
from bson import ObjectId
from datetime import datetime

from config.database import db
from models.match import Match
from services.mediator_queue import mediator_queue
from utils.logger import logger, log_success


class MatchService:

    async def create_match(
        self,
        guild_id: int,
        channel_id: int,
        player_ids: List[int],
        mediator_id: int,
        bet_value: float,
        gel_type: str = "normal",
        match_type: str = "1x1"
    ) -> Dict[str, Any]:
        try:
            match_data = {
                "guild_id": guild_id,
                "channel_id": channel_id,
                "player_ids": [int(pid) for pid in player_ids],  # ✅ int
                "mediator_id": int(mediator_id),                  # ✅ int
                "bet_value": bet_value,
                "gel_type": gel_type,
                "match_type": match_type,
                "status": "aguardando_pagamento",
                "thread_id": None,
                "time_blue": [],
                "time_red": [],
                "vencedor": None,
                "pagamento_confirmado": False,
                "premio_entregue_mediador": False,
                "premio_confirmado_jogador": False,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }

            collection = db.get_collection('matches')
            result = await collection.insert_one(match_data)

            logger.info(f"Partida criada: {result.inserted_id} - {match_type} R$ {bet_value} ({gel_type})")

            match_data['_id'] = result.inserted_id
            return match_data

        except Exception as e:
            logger.error(f"Erro ao criar partida: {e}")
            raise

    async def get_match(self, match_id: str) -> Optional[Dict[str, Any]]:
        try:
            collection = db.get_collection('matches')
            return await collection.find_one({'_id': ObjectId(match_id)})
        except Exception as e:
            logger.error(f"Erro ao buscar partida {match_id}: {e}")
            return None

    async def start_match(self, match_id: str) -> Optional[Dict[str, Any]]:
        try:
            collection = db.get_collection('matches')
            match_doc = await collection.find_one({'_id': ObjectId(match_id)})
            if not match_doc:
                return None

            await collection.update_one(
                {'_id': ObjectId(match_id)},
                {
                    '$set': {
                        'status': 'em_andamento',
                        'started_at': datetime.utcnow(),
                        'updated_at': datetime.utcnow()
                    }
                }
            )

            logger.info(f"Partida {match_id} iniciada")
            return await collection.find_one({'_id': ObjectId(match_id)})

        except Exception as e:
            logger.error(f"Erro ao iniciar partida {match_id}: {e}")
            return None

    async def complete_match(self, match_id: str) -> Optional[Dict[str, Any]]:
        try:
            collection = db.get_collection('matches')
            match_doc = await collection.find_one({'_id': ObjectId(match_id)})
            if not match_doc:
                return None

            await collection.update_one(
                {'_id': ObjectId(match_id)},
                {
                    '$set': {
                        'status': 'concluido',
                        'completed_at': datetime.utcnow(),
                        'updated_at': datetime.utcnow()
                    }
                }
            )

            log_success(f"Partida {match_id} finalizada")
            return await collection.find_one({'_id': ObjectId(match_id)})

        except Exception as e:
            logger.error(f"Erro ao finalizar partida {match_id}: {e}")
            return None

    async def cancel_match(self, match_id: str) -> Optional[Dict[str, Any]]:
        try:
            collection = db.get_collection('matches')
            match_doc = await collection.find_one({'_id': ObjectId(match_id)})
            if not match_doc:
                return None

            await collection.update_one(
                {'_id': ObjectId(match_id)},
                {
                    '$set': {
                        'status': 'cancelado',
                        'cancelled_at': datetime.utcnow(),
                        'updated_at': datetime.utcnow()
                    }
                }
            )

            logger.info(f"Partida {match_id} cancelada")
            return await collection.find_one({'_id': ObjectId(match_id)})

        except Exception as e:
            logger.error(f"Erro ao cancelar partida {match_id}: {e}")
            return None

    async def get_active_matches(self, limit: int = 50) -> List[Dict[str, Any]]:
        try:
            collection = db.get_collection('matches')
            cursor = collection.find({
                'status': {'$in': [
                    'aguardando_pagamento',
                    'aguardando_inicio',
                    'em_andamento',
                    'aguardando_resultado',
                    'aguardando_premio'
                ]}
            }).sort('created_at', -1).limit(limit)

            return await cursor.to_list(length=limit)

        except Exception as e:
            logger.error(f"Erro ao listar partidas ativas: {e}")
            return []

    async def get_matches_by_player(self, player_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        try:
            collection = db.get_collection('matches')
            cursor = collection.find(
                {'player_ids': int(player_id)}  # ✅ int
            ).sort('created_at', -1).limit(limit)
            return await cursor.to_list(length=limit)
        except Exception as e:
            logger.error(f"Erro ao buscar partidas do jogador {player_id}: {e}")
            return []

    async def get_matches_by_mediator(self, mediator_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        try:
            collection = db.get_collection('matches')
            cursor = collection.find(
                {'mediator_id': int(mediator_id)}  # ✅ int
            ).sort('created_at', -1).limit(limit)
            return await cursor.to_list(length=limit)
        except Exception as e:
            logger.error(f"Erro ao buscar partidas do mediador {mediator_id}: {e}")
            return []

    async def get_channel_stats(self, channel_name: str) -> Dict[str, int]:
        try:
            collection = db.get_collection('matches')

            total = await collection.count_documents({'match_type': channel_name})
            active = await collection.count_documents({
                'match_type': channel_name,
                'status': {'$in': [
                    'aguardando_pagamento',
                    'aguardando_inicio',
                    'em_andamento',
                    'aguardando_resultado',
                    'aguardando_premio'
                ]}
            })
            completed = await collection.count_documents({
                'match_type': channel_name,
                'status': 'concluido'
            })
            cancelled = await collection.count_documents({
                'match_type': channel_name,
                'status': 'cancelado'
            })

            return {
                'total': total,
                'active': active,
                'completed': completed,
                'cancelled': cancelled
            }

        except Exception as e:
            logger.error(f"Erro ao obter estatísticas do canal {channel_name}: {e}")
            return {'total': 0, 'active': 0, 'completed': 0, 'cancelled': 0}


# Instância global
match_service = MatchService()
