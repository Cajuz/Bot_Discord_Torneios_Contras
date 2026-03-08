from typing import Dict, Any, List, Optional
from bson import ObjectId
from datetime import datetime

from config.database import db
from models.match import Match
from utils.logger import logger, log_success


class MatchService:

    # ── Helper interno ───────────────────────────────────────────

    async def _get_collection(self):
        return db.get_collection('matches')

    async def _find(self, match_id: str) -> Optional[Dict[str, Any]]:
        col = await self._get_collection()
        return await col.find_one({'_id': ObjectId(match_id)})

    async def _update(self, match_id: str, fields: dict) -> Optional[Dict[str, Any]]:
        col = await self._get_collection()
        fields['updated_at'] = datetime.utcnow()
        await col.update_one({'_id': ObjectId(match_id)}, {'$set': fields})
        return await col.find_one({'_id': ObjectId(match_id)})

    def _validate_transition(self, match_doc: dict, new_status: str) -> bool:
        """Usa a lógica de transição do modelo Match."""
        match = Match(match_doc)
        return match.can_transition_to(new_status)

    # ── Criação ──────────────────────────────────────────────────

    async def create_match(
        self,
        guild_id: int,
        channel_id: int,
        channel_name: str,
        player_ids: List[int],
        mediator_id: int,
        bet_value: float,
        gel_type: str = "normal",
        match_type: str = "1x1",
        platform: str = "mob",
    ) -> Dict[str, Any]:
        try:
            match_data = {
                "guild_id":                   str(guild_id),
                "channel_id":                 str(channel_id),
                "channel_name":               channel_name,
                "match_type":                 match_type,
                "platform":                   platform,
                "bet_value":                  bet_value,
                "gel_type":                   gel_type,
                "player_ids":                 [str(pid) for pid in player_ids],
                "max_players":                len(player_ids),
                "mediator_id":                str(mediator_id),
                "status":                     Match.STATUS_AGUARDANDO_PAGAMENTO,
                "thread_id":                  None,
                "time_blue":                  [],
                "time_red":                   [],
                "vencedor":                   None,
                "pagamento_confirmado":       False,
                "premio_entregue_mediador":   False,
                "premio_confirmado_jogador":  False,
                "cancelled_by":               None,
                "cancel_reason":              None,
                "created_at":                 datetime.utcnow(),
                "updated_at":                 datetime.utcnow(),
                "started_at":                 None,
                "completed_at":               None,
                "cancelled_at":               None,
            }

            col = await self._get_collection()
            result = await col.insert_one(match_data)
            match_data['_id'] = result.inserted_id

            logger.info(f"✅ Partida criada: {result.inserted_id} | {match_type} R${bet_value} ({gel_type})")
            return match_data

        except Exception as e:
            logger.error(f"Erro ao criar partida: {e}")
            raise

    # ── Leitura ──────────────────────────────────────────────────

    async def get_match(self, match_id: str) -> Optional[Dict[str, Any]]:
        try:
            return await self._find(match_id)
        except Exception as e:
            logger.error(f"Erro ao buscar partida {match_id}: {e}")
            return None

    async def get_active_matches(self, limit: int = 50) -> List[Dict[str, Any]]:
        try:
            col = await self._get_collection()
            cursor = col.find(
                {'status': {'$in': Match.ACTIVE_STATUSES}}
            ).sort('created_at', -1).limit(limit)
            return await cursor.to_list(length=limit)
        except Exception as e:
            logger.error(f"Erro ao listar partidas ativas: {e}")
            return []

    async def get_matches_by_player(self, player_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        try:
            col = await self._get_collection()
            cursor = col.find(
                {'player_ids': str(player_id)}
            ).sort('created_at', -1).limit(limit)
            return await cursor.to_list(length=limit)
        except Exception as e:
            logger.error(f"Erro ao buscar partidas do jogador {player_id}: {e}")
            return []

    async def get_matches_by_mediator(self, mediator_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        try:
            col = await self._get_collection()
            cursor = col.find(
                {'mediator_id': str(mediator_id)}
            ).sort('created_at', -1).limit(limit)
            return await cursor.to_list(length=limit)
        except Exception as e:
            logger.error(f"Erro ao buscar partidas do mediador {mediator_id}: {e}")
            return []

    async def get_channel_stats(self, channel_name: str) -> Dict[str, int]:
        try:
            col = await self._get_collection()
            total     = await col.count_documents({'channel_name': channel_name})
            active    = await col.count_documents({'channel_name': channel_name, 'status': {'$in': Match.ACTIVE_STATUSES}})
            completed = await col.count_documents({'channel_name': channel_name, 'status': Match.STATUS_FINALIZADO})
            cancelled = await col.count_documents({'channel_name': channel_name, 'status': Match.STATUS_CANCELADO})
            return {'total': total, 'active': active, 'completed': completed, 'cancelled': cancelled}
        except Exception as e:
            logger.error(f"Erro ao obter estatísticas do canal {channel_name}: {e}")
            return {'total': 0, 'active': 0, 'completed': 0, 'cancelled': 0}

    # ── Fluxo linear ─────────────────────────────────────────────

    async def update_thread_id(self, match_id: str, thread_id: int) -> Optional[Dict[str, Any]]:
        """Salva o thread_id logo após criar a thread no Discord."""
        try:
            return await self._update(match_id, {'thread_id': thread_id})
        except Exception as e:
            logger.error(f"Erro ao atualizar thread_id da partida {match_id}: {e}")
            return None

    async def confirm_payment(self, match_id: str) -> Optional[Dict[str, Any]]:
        """aguardando_pagamento → aguardando_inicio"""
        try:
            match_doc = await self._find(match_id)
            if not match_doc:
                return None
            if not self._validate_transition(match_doc, Match.STATUS_AGUARDANDO_INICIO):
                logger.warning(f"Transição inválida: {match_doc['status']} → aguardando_inicio")
                return None
            result = await self._update(match_id, {
                'status':                  Match.STATUS_AGUARDANDO_INICIO,
                'pagamento_confirmado':    True,
            })
            logger.info(f"💰 Pagamento confirmado: {match_id}")
            return result
        except Exception as e:
            logger.error(f"Erro ao confirmar pagamento {match_id}: {e}")
            return None

    async def start_match(self, match_id: str) -> Optional[Dict[str, Any]]:
        """aguardando_inicio → em_andamento"""
        try:
            match_doc = await self._find(match_id)
            if not match_doc:
                return None
            if not self._validate_transition(match_doc, Match.STATUS_EM_ANDAMENTO):
                logger.warning(f"Transição inválida: {match_doc['status']} → em_andamento")
                return None
            result = await self._update(match_id, {
                'status':     Match.STATUS_EM_ANDAMENTO,
                'started_at': datetime.utcnow(),
            })
            logger.info(f"▶️ Partida iniciada: {match_id}")
            return result
        except Exception as e:
            logger.error(f"Erro ao iniciar partida {match_id}: {e}")
            return None

    async def set_winner(
        self,
        match_id: str,
        vencedor: str,
        time_blue: List[int],
        time_red: List[int],
    ) -> Optional[Dict[str, Any]]:
        """em_andamento → aguardando_premio"""
        try:
            if vencedor not in ('blue', 'red'):
                logger.error(f"Vencedor inválido: {vencedor}")
                return None
            match_doc = await self._find(match_id)
            if not match_doc:
                return None
            if not self._validate_transition(match_doc, Match.STATUS_AGUARDANDO_PREMIO):
                logger.warning(f"Transição inválida: {match_doc['status']} → aguardando_premio")
                return None
            result = await self._update(match_id, {
                'status':    Match.STATUS_AGUARDANDO_PREMIO,
                'vencedor':  vencedor,
                'time_blue': [str(p) for p in time_blue],
                'time_red':  [str(p) for p in time_red],
            })
            logger.info(f"🏆 Vencedor declarado ({vencedor}): {match_id}")
            return result
        except Exception as e:
            logger.error(f"Erro ao declarar vencedor {match_id}: {e}")
            return None

    async def confirm_prize_delivery(self, match_id: str) -> Optional[Dict[str, Any]]:
        """Mediador confirma que entregou o prêmio (ainda em aguardando_premio)."""
        try:
            match_doc = await self._find(match_id)
            if not match_doc:
                return None
            if match_doc.get('status') != Match.STATUS_AGUARDANDO_PREMIO:
                logger.warning(f"confirm_prize_delivery: status inválido {match_doc['status']}")
                return None
            result = await self._update(match_id, {'premio_entregue_mediador': True})
            logger.info(f"🎁 Prêmio entregue confirmado pelo mediador: {match_id}")
            return result
        except Exception as e:
            logger.error(f"Erro ao confirmar entrega de prêmio {match_id}: {e}")
            return None

    async def confirm_prize_received(self, match_id: str) -> Optional[Dict[str, Any]]:
        """Jogador confirma recebimento → finaliza a partida."""
        try:
            match_doc = await self._find(match_id)
            if not match_doc:
                return None
            if match_doc.get('status') != Match.STATUS_AGUARDANDO_PREMIO:
                logger.warning(f"confirm_prize_received: status inválido {match_doc['status']}")
                return None
            result = await self._update(match_id, {
                'status':                     Match.STATUS_FINALIZADO,
                'premio_confirmado_jogador':  True,
                'completed_at':               datetime.utcnow(),
            })
            log_success(f"✅ Partida finalizada: {match_id}")
            return result
        except Exception as e:
            logger.error(f"Erro ao confirmar recebimento de prêmio {match_id}: {e}")
            return None

    # ── Cancelamento (qualquer status) ───────────────────────────

    async def cancel_match(
        self,
        match_id: str,
        cancelled_by: int = None,
        reason: str = None,
    ) -> Optional[Dict[str, Any]]:
        """Cancela partida em qualquer status ativo. Registra quem cancelou."""
        try:
            match_doc = await self._find(match_id)
            if not match_doc:
                return None
            match = Match(match_doc)
            if not match.can_transition_to(Match.STATUS_CANCELADO):
                logger.warning(f"Partida {match_id} já está finalizada/cancelada")
                return None
            result = await self._update(match_id, {
                'status':        Match.STATUS_CANCELADO,
                'cancelled_by':  str(cancelled_by) if cancelled_by else None,
                'cancel_reason': reason,
                'cancelled_at':  datetime.utcnow(),
            })
            logger.info(f"🚫 Partida {match_id} cancelada por {cancelled_by} | motivo: {reason}")
            return result
        except Exception as e:
            logger.error(f"Erro ao cancelar partida {match_id}: {e}")
            return None

    # ── Force (admin) ─────────────────────────────────────────────

    async def force_complete(self, match_id: str, admin_id: int = None) -> Optional[Dict[str, Any]]:
        """Admin força finalização independente do status atual."""
        try:
            match_doc = await self._find(match_id)
            if not match_doc:
                return None
            result = await self._update(match_id, {
                'status':       Match.STATUS_FINALIZADO,
                'completed_at': datetime.utcnow(),
                'cancelled_by': str(admin_id) if admin_id else None,
                'cancel_reason': 'force_complete_admin',
            })
            log_success(f"⚡ Partida {match_id} forçada para finalizado por admin {admin_id}")
            return result
        except Exception as e:
            logger.error(f"Erro ao forçar conclusão {match_id}: {e}")
            return None


# Instância global
match_service = MatchService()
