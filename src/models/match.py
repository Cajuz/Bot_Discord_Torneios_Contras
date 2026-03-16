from datetime import datetime
from utils.datetime_utils import utcnow
from typing import Optional, Dict, Any, List


class Match:

    STATUS_AGUARDANDO_PAGAMENTO = 'aguardando_pagamento'
    STATUS_AGUARDANDO_INICIO    = 'aguardando_inicio'
    STATUS_EM_ANDAMENTO         = 'em_andamento'
    STATUS_AGUARDANDO_PREMIO    = 'aguardando_premio'
    STATUS_FINALIZADO           = 'finalizado'
    STATUS_CANCELADO            = 'cancelado'

    ACTIVE_STATUSES = [
        'aguardando_pagamento',
        'aguardando_inicio',
        'em_andamento',
        'aguardando_premio',
    ]

    FLOW = [
        'aguardando_pagamento',
        'aguardando_inicio',
        'em_andamento',
        'aguardando_premio',
        'finalizado',
    ]

    def __init__(self, data: Dict[str, Any]):
        self._id          = data.get('_id')
        self.guild_id     = data.get('guild_id')
        self.channel_id   = data.get('channel_id')
        self.channel_name = data.get('channel_name')
        self.match_type   = data.get('match_type')
        self.platform     = data.get('platform')
        self.bet_value    = data.get('bet_value')
        self.gel_type     = data.get('gel_type', 'normal')

        self.player_ids  = [str(p) for p in data.get('player_ids', [])]
        self.max_players = data.get('max_players', 2)
        self.time_blue   = [str(p) for p in data.get('time_blue', [])]
        self.time_red    = [str(p) for p in data.get('time_red', [])]

        self.mediator_id = str(data['mediator_id']) if data.get('mediator_id') else None

        self.status    = data.get('status', self.STATUS_AGUARDANDO_PAGAMENTO)
        self.thread_id = data.get('thread_id')

        self.vencedor  = data.get('vencedor')    # 'blue' | 'red' | None
        self.winner_id = data.get('winner_id')   # ID do jogador vencedor (para analytics)
        self.proof_url = data.get('proof_url')

        self.pagamento_confirmado      = data.get('pagamento_confirmado', False)
        self.premio_entregue_mediador  = data.get('premio_entregue_mediador', False)
        self.premio_confirmado_jogador = data.get('premio_confirmado_jogador', False)

        self.cancelled_by  = str(data['cancelled_by']) if data.get('cancelled_by') else None
        self.cancel_reason = data.get('cancel_reason')

        self.created_at   = data.get('created_at', utcnow())
        self.updated_at   = data.get('updated_at', utcnow())
        self.started_at   = data.get('started_at')
        self.completed_at = data.get('completed_at')
        self.cancelled_at = data.get('cancelled_at')
        self.finished_at  = data.get('finished_at')

    def to_dict(self) -> Dict[str, Any]:
        return {
            '_id':                        self._id,
            'guild_id':                   self.guild_id,
            'channel_id':                 self.channel_id,
            'channel_name':               self.channel_name,
            'match_type':                 self.match_type,
            'platform':                   self.platform,
            'bet_value':                  self.bet_value,
            'gel_type':                   self.gel_type,
            'player_ids':                 self.player_ids,
            'max_players':                self.max_players,
            'time_blue':                  self.time_blue,
            'time_red':                   self.time_red,
            'mediator_id':                self.mediator_id,
            'status':                     self.status,
            'thread_id':                  self.thread_id,
            'vencedor':                   self.vencedor,
            'winner_id':                  self.winner_id,
            'proof_url':                  self.proof_url,
            'pagamento_confirmado':       self.pagamento_confirmado,
            'premio_entregue_mediador':   self.premio_entregue_mediador,
            'premio_confirmado_jogador':  self.premio_confirmado_jogador,
            'cancelled_by':               self.cancelled_by,
            'cancel_reason':              self.cancel_reason,
            'created_at':                 self.created_at,
            'updated_at':                 utcnow(),
            'started_at':                 self.started_at,
            'completed_at':               self.completed_at,
            'cancelled_at':               self.cancelled_at,
            'finished_at':                self.finished_at,
        }

    def is_active(self) -> bool:
        return self.status in self.ACTIVE_STATUSES

    def is_finished(self) -> bool:
        return self.status in (self.STATUS_FINALIZADO, self.STATUS_CANCELADO)

    def can_transition_to(self, new_status: str) -> bool:
        if new_status == self.STATUS_CANCELADO:
            return not self.is_finished()
        try:
            current_idx = self.FLOW.index(self.status)
            new_idx     = self.FLOW.index(new_status)
            return new_idx == current_idx + 1
        except ValueError:
            return False

    def get_all_player_ids(self) -> List[str]:
        return list(self.player_ids)

    def get_winner_ids(self) -> List[str]:
        if self.vencedor == 'blue':
            return list(self.time_blue)
        if self.vencedor == 'red':
            return list(self.time_red)
        return []

    def get_loser_ids(self) -> List[str]:
        if self.vencedor == 'blue':
            return list(self.time_red)
        if self.vencedor == 'red':
            return list(self.time_blue)
        return []

    def __repr__(self) -> str:
        return f"<Match id={self._id} status={self.status} value={self.bet_value}>"