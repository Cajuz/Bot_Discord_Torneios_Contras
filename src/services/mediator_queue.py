from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from utils.datetime_utils import utcnow as _utcnow
import discord

from config.database import db
from utils.logger import logger, log_success


class MediatorQueue:
    """Gerenciador da fila de mediadores com auto-cadastro"""

    def __init__(self):
        self.queue: List[int] = []
        self._initialized = False

    async def initialize(self):
        if self._initialized:
            return
        try:
            collection = db.get_collection('mediators')
            cursor = collection.find({'is_active': True, 'in_queue': True})
            mediators = await cursor.to_list(length=None)
            self.queue = [m['user_id'] for m in mediators]
            self._initialized = True
            logger.info(f"Fila de mediadores inicializada: {len(self.queue)} ativos")
        except Exception as e:
            logger.error(f"Erro ao inicializar fila de mediadores: {e}")

    async def sync_mediators_by_role(self, guild: discord.Guild, role_name: str = "Controller"):
        try:
            role = discord.utils.get(guild.roles, name=role_name)
            if not role:
                logger.warning(f"Cargo '{role_name}' não encontrado em {guild.name}")
                return

            collection = db.get_collection('mediators')
            members_with_role = [member.id for member in role.members]
            synced_count = 0
            new_count = 0

            for user_id in members_with_role:
                # ✅ ignora user_id inválido antes de qualquer operação
                if not user_id:
                    logger.warning("sync_mediators_by_role: user_id inválido ignorado")
                    continue

                existing = await collection.find_one({'user_id': user_id})
                if not existing:
                    member = guild.get_member(user_id)
                    await self.register_mediator(
                        user_id=user_id,
                        username=member.name if member else f"User_{user_id}",
                        guild_id=guild.id
                    )
                    new_count += 1
                else:
                    if not existing.get('is_active', False):
                        await collection.update_one(
                            {'user_id': user_id},
                            {'$set': {'is_active': True, 'updated_at': _utcnow()}}
                        )
                        synced_count += 1

            all_mediators = await collection.find({'guild_id': guild.id}).to_list(length=None)
            for mediator in all_mediators:
                if mediator['user_id'] not in members_with_role and mediator.get('is_active', False):
                    await collection.update_one(
                        {'user_id': mediator['user_id']},
                        {'$set': {'is_active': False, 'in_queue': False, 'updated_at': _utcnow()}}
                    )
                    if mediator['user_id'] in self.queue:
                        self.queue.remove(mediator['user_id'])

            log_success(f"Sync completo: {new_count} novos, {synced_count} reativados")

        except Exception as e:
            logger.error(f"Erro ao sincronizar mediadores por cargo: {e}")

    async def register_mediator(self, user_id: int, username: str, guild_id: int) -> bool:
        # ✅ guarda contra user_id nulo — evita o E11000 com discord_id: null
        if not user_id:
            logger.warning("register_mediator: user_id inválido (None/0), ignorado")
            return False

        try:
            collection = db.get_collection('mediators')
            existing = await collection.find_one({'user_id': user_id})
            if existing:
                return False

            await collection.insert_one({
                'user_id':          user_id,
                'discord_id':       str(user_id),   # ✅ campo que o índice único exige
                'username':         username,
                'guild_id':         guild_id,
                'is_active':        True,
                'in_queue':         False,
                'matches_mediated': 0,
                'created_at':       _utcnow(),
                'updated_at':       _utcnow(),
                'last_match_at':    None
            })
            log_success(f"Mediador cadastrado: {username} (ID: {user_id})")
            return True
        except Exception as e:
            logger.error(f"Erro ao cadastrar mediador: {e}")
            return False

    async def add_to_queue(self, user_id: int) -> bool:
        if not user_id:
            logger.warning("add_to_queue: user_id inválido ignorado")
            return False
        try:
            collection = db.get_collection('mediators')
            mediator = await collection.find_one({'user_id': user_id})

            if not mediator or not mediator.get('is_active', False):
                return False
            if user_id in self.queue:
                return False

            self.queue.append(user_id)
            await collection.update_one(
                {'user_id': user_id},
                {'$set': {'in_queue': True, 'updated_at': _utcnow()}}
            )
            log_success(f"Mediador {user_id} entrou na fila (Posição: {len(self.queue)})")
            return True
        except Exception as e:
            logger.error(f"Erro ao adicionar mediador à fila: {e}")
            return False

    async def remove_from_queue(self, user_id: int) -> bool:
        try:
            if user_id not in self.queue:
                return False
            self.queue.remove(user_id)
            collection = db.get_collection('mediators')
            await collection.update_one(
                {'user_id': user_id},
                {'$set': {'in_queue': False, 'updated_at': _utcnow()}}
            )
            logger.info(f"Mediador {user_id} saiu da fila")
            return True
        except Exception as e:
            logger.error(f"Erro ao remover mediador da fila: {e}")
            return False

    async def get_next_mediator(self) -> Optional[int]:
        """Retorna o user_id (int) do próximo mediador via round-robin"""
        if not self.queue:
            logger.warning("Fila de mediadores vazia!")
            return None

        mediator_id = self.queue.pop(0)
        self.queue.append(mediator_id)

        try:
            collection = db.get_collection('mediators')
            await collection.update_one(
                {'user_id': mediator_id},
                {
                    '$set': {'last_match_at': _utcnow()},
                    '$inc': {'matches_mediated': 1}
                }
            )
        except Exception as e:
            logger.error(f"Erro ao atualizar estatísticas do mediador: {e}")

        logger.info(f"Mediador {mediator_id} selecionado para partida")
        return mediator_id

    async def get_queue_info(self) -> Dict[str, Any]:
        try:
            collection = db.get_collection('mediators')
            total = await collection.count_documents({'is_active': True})
            cursor = collection.find({'is_active': True}).sort('matches_mediated', -1).limit(5)
            top_mediators = await cursor.to_list(length=5)
            return {
                'total_active': total,
                'in_queue': len(self.queue),
                'queue': self.queue,
                'top_mediators': top_mediators
            }
        except Exception as e:
            logger.error(f"Erro ao obter info da fila: {e}")
            return {'total_active': 0, 'in_queue': 0, 'queue': [], 'top_mediators': []}

    async def get_mediator_position(self, user_id: int) -> Optional[int]:
        try:
            if user_id not in self.queue:
                return None
            return self.queue.index(user_id) + 1
        except Exception as e:
            logger.error(f"Erro ao obter posição na fila: {e}")
            return None

    def is_in_queue(self, user_id: int) -> bool:
        return user_id in self.queue

    def has_available_mediators(self) -> bool:
        return len(self.queue) > 0

    # ✏️ Aliases usados pelo admin_cog e main.py

    async def add_mediator(self, user_id: str, username: str):
        """Alias para register + add_to_queue"""
        # ✅ valida antes de converter
        if not user_id:
            logger.warning("add_mediator: user_id vazio ignorado")
            return None

        uid = int(user_id)
        if not uid:
            logger.warning("add_mediator: uid == 0 ignorado")
            return None

        collection = db.get_collection('mediators')
        existing = await collection.find_one({'user_id': uid})
        if not existing:
            await self.register_mediator(uid, username, guild_id=0)

        await self.add_to_queue(uid)

        pos = await self.get_mediator_position(uid)

        class _Result:
            pass
        r = _Result()
        r.position = pos or len(self.queue)
        return r

    async def remove_mediador(self, user_id: str):
        """Alias para remove_from_queue"""
        if not user_id:
            return
        await self.remove_from_queue(int(user_id))

    async def get_queue_stats(self) -> Dict[str, Any]:
        """Stats formatados para o comando !fila"""
        try:
            collection = db.get_collection('mediators')
            now = _utcnow()
            eight_min_ago = now - timedelta(minutes=8)

            mediators_info = []
            for uid in self.queue:
                doc = await collection.find_one({'user_id': uid})
                if not doc:
                    continue

                matches_recent = await db.get_collection('matches').count_documents({
                    'mediator_id': str(uid),
                    'created_at': {'$gte': eight_min_ago}
                })

                mediators_info.append({
                    'position':              self.queue.index(uid) + 1,
                    'username':              doc.get('username', f'User_{uid}'),
                    'total_matches':         doc.get('matches_mediated', 0),
                    'matches_in_last_8_min': matches_recent,
                    'can_mediate':           matches_recent < 5
                })

            total = await collection.count_documents({'is_active': True})

            return {
                'total_active': total,
                'mediators':    mediators_info
            }
        except Exception as e:
            logger.error(f"Erro ao obter stats da fila: {e}")
            return {'total_active': 0, 'mediators': []}


# Instância global
mediator_queue = MediatorQueue()
