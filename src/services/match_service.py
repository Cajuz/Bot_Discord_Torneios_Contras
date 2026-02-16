from typing import Dict, Any, List, Optional
from bson import ObjectId
from datetime import datetime

from config.database import db
from models.match import Match
from services.mediator_queue import mediator_queue
from utils.logger import logger, log_success


class MatchService:
    """Serviço de gerenciamento de partidas"""
    
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
        """
        Criar nova partida
        
        Args:
            guild_id: ID do servidor Discord
            channel_id: ID do canal
            player_ids: Lista de IDs dos jogadores
            mediator_id: ID do mediador
            bet_value: Valor da aposta
            gel_type: Tipo de GEL (normal ou infinito)
            match_type: Tipo da partida (1x1, 2x2, etc)
        
        Returns:
            Dados da partida criada
        """
        try:
            match_data = {
                "guild_id": guild_id,
                "channel_id": channel_id,
                "player_ids": [str(pid) for pid in player_ids],  # ⭐ Converter para string
                "mediator_id": str(mediator_id),  # ⭐ Converter para string
                "bet_value": bet_value,
                "gel_type": gel_type,
                "match_type": match_type,
                "status": "pending",
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            
            collection = db.get_collection('matches')
            result = await collection.insert_one(match_data)
            
            logger.info(f"Partida criada: {result.inserted_id} - {match_type} R$ {bet_value} ({gel_type})")
            
            # Adicionar o _id ao retorno
            match_data['_id'] = result.inserted_id
            
            return match_data
            
        except Exception as e:
            logger.error(f"Erro ao criar partida: {e}")
            raise
    
    async def get_match(self, match_id: str) -> Optional[Dict[str, Any]]:
        """Obter partida por ID"""
        try:
            collection = db.get_collection('matches')
            match_doc = await collection.find_one({'_id': ObjectId(match_id)})
            return match_doc
        except Exception as e:
            logger.error(f"Erro ao buscar partida {match_id}: {e}")
            return None
    
    async def start_match(self, match_id: str) -> Optional[Dict[str, Any]]:
        """Iniciar partida"""
        try:
            collection = db.get_collection('matches')
            
            match_doc = await collection.find_one({'_id': ObjectId(match_id)})
            if not match_doc:
                logger.error(f"Partida {match_id} não encontrada")
                return None
            
            await collection.update_one(
                {'_id': ObjectId(match_id)},
                {
                    '$set': {
                        'status': 'in_progress',
                        'started_at': datetime.utcnow(),
                        'updated_at': datetime.utcnow()
                    }
                }
            )
            
            logger.info(f"Partida {match_id} iniciada")
            
            # Retornar documento atualizado
            match_doc = await collection.find_one({'_id': ObjectId(match_id)})
            return match_doc
            
        except Exception as e:
            logger.error(f"Erro ao iniciar partida {match_id}: {e}")
            return None
    
    async def complete_match(self, match_id: str) -> Optional[Dict[str, Any]]:
        """Finalizar partida"""
        try:
            collection = db.get_collection('matches')
            
            match_doc = await collection.find_one({'_id': ObjectId(match_id)})
            if not match_doc:
                logger.error(f"Partida {match_id} não encontrada")
                return None
            
            await collection.update_one(
                {'_id': ObjectId(match_id)},
                {
                    '$set': {
                        'status': 'completed',
                        'completed_at': datetime.utcnow(),
                        'updated_at': datetime.utcnow()
                    }
                }
            )
            
            log_success(f"Partida {match_id} finalizada")
            
            # Retornar documento atualizado
            match_doc = await collection.find_one({'_id': ObjectId(match_id)})
            return match_doc
            
        except Exception as e:
            logger.error(f"Erro ao finalizar partida {match_id}: {e}")
            return None
    
    async def cancel_match(self, match_id: str) -> Optional[Dict[str, Any]]:
        """Cancelar partida"""
        try:
            collection = db.get_collection('matches')
            
            match_doc = await collection.find_one({'_id': ObjectId(match_id)})
            if not match_doc:
                logger.error(f"Partida {match_id} não encontrada")
                return None
            
            await collection.update_one(
                {'_id': ObjectId(match_id)},
                {
                    '$set': {
                        'status': 'cancelled',
                        'cancelled_at': datetime.utcnow(),
                        'updated_at': datetime.utcnow()
                    }
                }
            )
            
            logger.info(f"Partida {match_id} cancelada")
            
            # Retornar documento atualizado
            match_doc = await collection.find_one({'_id': ObjectId(match_id)})
            return match_doc
            
        except Exception as e:
            logger.error(f"Erro ao cancelar partida {match_id}: {e}")
            return None
    
    async def get_active_matches(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Listar partidas ativas"""
        try:
            collection = db.get_collection('matches')
            
            cursor = collection.find({
                'status': {'$in': ['pending', 'in_progress']}
            }).sort('created_at', -1).limit(limit)
            
            matches = await cursor.to_list(length=limit)
            return matches
            
        except Exception as e:
            logger.error(f"Erro ao listar partidas ativas: {e}")
            return []
    
    async def get_matches_by_player(self, player_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """Obter partidas de um jogador"""
        try:
            collection = db.get_collection('matches')
            
            cursor = collection.find({
                'player_ids': str(player_id)
            }).sort('created_at', -1).limit(limit)
            
            matches = await cursor.to_list(length=limit)
            return matches
            
        except Exception as e:
            logger.error(f"Erro ao buscar partidas do jogador {player_id}: {e}")
            return []
    
    async def get_matches_by_mediator(self, mediator_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """Obter partidas de um mediador"""
        try:
            collection = db.get_collection('matches')
            
            cursor = collection.find({
                'mediator_id': str(mediator_id)
            }).sort('created_at', -1).limit(limit)
            
            matches = await cursor.to_list(length=limit)
            return matches
            
        except Exception as e:
            logger.error(f"Erro ao buscar partidas do mediador {mediator_id}: {e}")
            return []
    
    async def get_channel_stats(self, channel_name: str) -> Dict[str, int]:
        """Obter estatísticas de um canal"""
        try:
            collection = db.get_collection('matches')
            
            total = await collection.count_documents({'match_type': channel_name})
            active = await collection.count_documents({
                'match_type': channel_name,
                'status': {'$in': ['pending', 'in_progress']}
            })
            completed = await collection.count_documents({
                'match_type': channel_name,
                'status': 'completed'
            })
            cancelled = await collection.count_documents({
                'match_type': channel_name,
                'status': 'cancelled'
            })
            
            return {
                'total': total,
                'active': active,
                'completed': completed,
                'cancelled': cancelled
            }
            
        except Exception as e:
            logger.error(f"Erro ao obter estatísticas do canal {channel_name}: {e}")
            return {
                'total': 0,
                'active': 0,
                'completed': 0,
                'cancelled': 0
            }


# Instância global
match_service = MatchService()
