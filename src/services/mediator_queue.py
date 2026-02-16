import asyncio
from typing import Optional, List, Dict, Any
from bson import ObjectId
from datetime import datetime

from config.database import db
from models.mediator import Mediator
from utils.logger import logger, log_success

class MediatorQueue:
    """Sistema otimizado de fila de mediadores"""
    
    def __init__(self):
        self.is_initialized = False
        self._lock = asyncio.Lock()
    
    async def initialize(self):
        """Inicializar fila ao startar o servidor"""
        try:
            await self.reorganize_queue()
            self.is_initialized = True
            log_success("Fila de mediadores inicializada")
        except Exception as e:
            logger.error(f"Erro ao inicializar fila de mediadores: {e}")
            raise
    
    async def reorganize_queue(self):
        """Reorganizar fila - ordena mediadores por posição"""
        collection = db.get_collection('mediators')
        
        # Buscar mediadores ativos ordenados
        cursor = collection.find({'is_active': True}).sort('position', 1)
        mediators = await cursor.to_list(length=None)
        
        # Reindexar posições para evitar gaps
        bulk_operations = []
        for index, mediator in enumerate(mediators, start=1):
            bulk_operations.append({
                'update_one': {
                    'filter': {'_id': mediator['_id']},
                    'update': {'$set': {'position': index, 'updated_at': datetime.now()}}
                }
            })
        
        if bulk_operations:
            # Executar bulk update
            updates = [op['update_one'] for op in bulk_operations]
            for update in updates:
                await collection.update_one(update['filter'], update['update'])
        
        logger.info(f"Fila reorganizada: {len(mediators)} mediadores ativos")
    
    async def add_mediator(self, discord_id: str, username: str) -> Mediator:
        """Adicionar mediador à fila"""
        async with self._lock:
            try:
                collection = db.get_collection('mediators')
                
                # Verificar se já existe
                existing = await collection.find_one({'discord_id': discord_id})
                
                if existing:
                    if not existing['is_active']:
                        # Reativar mediador
                        await collection.update_one(
                            {'discord_id': discord_id},
                            {'$set': {'is_active': True, 'updated_at': datetime.now()}}
                        )
                        await self.reorganize_queue()
                        logger.info(f"Mediador {username} reativado")
                        existing = await collection.find_one({'discord_id': discord_id})
                    return Mediator(existing)
                
                # Pegar última posição
                last_mediator = await collection.find_one(
                    {'is_active': True},
                    sort=[('position', -1)]
                )
                
                new_position = last_mediator['position'] + 1 if last_mediator else 1
                
                # Criar novo mediador
                mediator_doc = Mediator.create_document(discord_id, username, new_position)
                result = await collection.insert_one(mediator_doc)
                
                mediator_doc['_id'] = result.inserted_id
                log_success(f"Mediador {username} adicionado na posição {new_position}")
                
                return Mediator(mediator_doc)
                
            except Exception as e:
                logger.error(f"Erro ao adicionar mediador: {e}")
                raise
    
    async def remove_mediator(self, discord_id: str) -> Mediator:
        """Remover mediador da fila"""
        async with self._lock:
            try:
                collection = db.get_collection('mediators')
                
                mediator_doc = await collection.find_one({'discord_id': discord_id})
                if not mediator_doc:
                    raise ValueError('Mediador não encontrado')
                
                # Desativar mediador
                await collection.update_one(
                    {'discord_id': discord_id},
                    {'$set': {'is_active': False, 'updated_at': datetime.now()}}
                )
                
                await self.reorganize_queue()
                
                mediator = Mediator(mediator_doc)
                log_success(f"Mediador {mediator.username} removido da fila")
                
                return mediator
                
            except Exception as e:
                logger.error(f"Erro ao remover mediador: {e}")
                raise
    
    async def get_next_mediator(self) -> Mediator:
        """Pegar próximo mediador disponível (otimizado com lock)"""
        async with self._lock:
            try:
                collection = db.get_collection('mediators')
                
                # Buscar mediadores ativos ordenados por posição
                cursor = collection.find({'is_active': True}).sort('position', 1)
                mediators_docs = await cursor.to_list(length=None)
                
                if not mediators_docs:
                    raise ValueError('Nenhum mediador disponível na fila')
                
                # Tentar encontrar mediador que pode mediar
                for mediator_doc in mediators_docs:
                    mediator = Mediator(mediator_doc)
                    
                    if mediator.can_mediate():
                        # Atualizar estatísticas
                        mediator.assign_match()
                        
                        # Pegar máxima posição
                        max_doc = await collection.find_one(
                            {'is_active': True},
                            sort=[('position', -1)]
                        )
                        new_position = max_doc['position'] + 1 if max_doc else len(mediators_docs)
                        
                        mediator.position = new_position
                        
                        # Salvar no banco
                        await collection.update_one(
                            {'_id': mediator._id},
                            {'$set': mediator.to_dict()}
                        )
                        
                        # Reorganizar fila de forma assíncrona (não bloqueia)
                        asyncio.create_task(self.reorganize_queue())
                        
                        logger.info(
                            f"Mediador {mediator.username} selecionado "
                            f"(partidas: {mediator.matches_in_last_8_minutes}/5)"
                        )
                        
                        return mediator
                
                # Se todos atingiram o limite, pegar o primeiro e resetar
                first_mediator = Mediator(mediators_docs[0])
                first_mediator.matches_in_last_8_minutes = 0
                first_mediator.last_reset_at = datetime.now()
                first_mediator.assign_match()
                
                max_doc = await collection.find_one(
                    {'is_active': True},
                    sort=[('position', -1)]
                )
                first_mediator.position = max_doc['position'] + 1 if max_doc else len(mediators_docs)
                
                await collection.update_one(
                    {'_id': first_mediator._id},
                    {'$set': first_mediator.to_dict()}
                )
                
                asyncio.create_task(self.reorganize_queue())
                
                logger.warning(
                    f"Todos mediadores no limite. Resetando {first_mediator.username}"
                )
                
                return first_mediator
                
            except Exception as e:
                logger.error(f"Erro ao obter próximo mediador: {e}")
                raise
    
    async def list_active_mediators(self) -> List[Dict[str, Any]]:
        """Listar todos os mediadores ativos"""
        collection = db.get_collection('mediators')
        cursor = collection.find({'is_active': True}).sort('position', 1)
        return await cursor.to_list(length=None)
    
    async def get_queue_stats(self) -> Dict[str, Any]:
        """Obter estatísticas da fila"""
        mediators = await self.list_active_mediators()
        
        stats = {
            'total_active': len(mediators),
            'mediators': []
        }
        
        for m in mediators:
            stats['mediators'].append({
                'username': m['username'],
                'position': m['position'],
                'total_matches': m['statistics']['total_matches'],
                'matches_in_last_8_min': m['statistics']['matches_in_last_8_minutes'],
                'can_mediate': m['statistics']['matches_in_last_8_minutes'] < 5
            })
        
        return stats

# Instância global
mediator_queue = MediatorQueue()
