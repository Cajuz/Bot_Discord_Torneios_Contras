from datetime import datetime
from typing import Optional, Dict, Any, List


class Match:
    """Modelo de Partida"""

    # ── Status (nome = valor, sem ambiguidade) ──────────────────
    STATUS_AGUARDANDO_PAGAMENTO = 'aguardando_pagamento'
    STATUS_AGUARDANDO_INICIO    = 'aguardando_inicio'
    STATUS_EM_ANDAMENTO         = 'em_andamento'
    STATUS_AGUARDANDO_PREMIO    = 'aguardando_premio'
    STATUS_FINALIZADO           = 'finalizado'
    STATUS_CANCELADO            = 'cancelado'

    # ── Estados considerados "ativos" ───────────────────────────
    ACTIVE_STATUSES = [
        'aguardando_pagamento',
        'aguardando_inicio',
        'em_andamento',
        'aguardando_premio',
    ]

    # ── Fluxo linear para validação de transição ────────────────
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
        self.match_type   = data.get('match_type')   # 1x1, 2x2, 3x3, 4x4
        self.platform     = data.get('platform')     # mob, emu, misto
        self.bet_value    = data.get('bet_value')
        self.gel_type     = data.get('gel_type', 'normal')

        # Jogadores — IDs sempre salvos como str
        self.player_ids  = [str(p) for p in data.get('player_ids', [])]
        self.max_players = data.get('max_players', 2)
        self.time_blue   = [str(p) for p in data.get('time_blue', [])]
        self.time_red    = [str(p) for p in data.get('time_red', [])]

        # Mediador
        self.mediator_id = str(data['mediator_id']) if data.get('mediator_id') else None

        # Status e controle
        self.status    = data.get('status', self.STATUS_AGUARDANDO_PAGAMENTO)
        self.thread_id = data.get('thread_id')

        # Resultado
        self.vencedor  = data.get('vencedor')    # 'blue' | 'red' | None
        self.proof_url = data.get('proof_url')

        # Flags do fluxo
        self.pagamento_confirmado      = data.get('pagamento_confirmado', False)
        self.premio_entregue_mediador  = data.get('premio_entregue_mediador', False)
        self.premio_confirmado_jogador = data.get('premio_confirmado_jogador', False)

        # Auditoria
        self.cancelled_by = str(data['cancelled_by']) if data.get('cancelled_by') else None
        self.cancel_reason = data.get('cancel_reason')

        # Timestamps
        self.created_at   = data.get('created_at', datetime.utcnow())
        self.updated_at   = data.get('updated_at', datetime.utcnow())
        self.started_at   = data.get('started_at')
        self.completed_at = data.get('completed_at')
        self.cancelled_at = data.get('cancelled_at')

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
            'proof_url':                  self.proof_url,
            'pagamento_confirmado':       self.pagamento_confirmado,
            'premio_entregue_mediador':   self.premio_entregue_mediador,
            'premio_confirmado_jogador':  self.premio_confirmado_jogador,
            'cancelled_by':               self.cancelled_by,
            'cancel_reason':              self.cancel_reason,
            'created_at':                 self.created_at,
            'updated_at':                 datetime.utcnow(),
            'started_at':                 self.started_at,
            'completed_at':               self.completed_at,
            'cancelled_at':               self.cancelled_at,
        }

    # ── Helpers ─────────────────────────────────────────────────

    def is_active(self) -> bool:
        return self.status in self.ACTIVE_STATUSES

    def is_finished(self) -> bool:
        return self.status in (self.STATUS_FINALIZADO, self.STATUS_CANCELADO)

    def can_transition_to(self, new_status: str) -> bool:
        """Valida se a transição de status é permitida no fluxo linear."""
        if new_status == self.STATUS_CANCELADO:
            return not self.is_finished()
        try:
            current_idx = self.FLOW.index(self.status)
            new_idx     = self.FLOW.index(new_status)
            return new_idx == current_idx + 1
        except ValueError:
            return False

    def get_all_player_ids(self) -> List[str]:
        """Retorna todos os jogadores como str."""
        return list(self.player_ids)

    def get_winner_ids(self) -> List[str]:
        """Retorna IDs do time vencedor como str."""
        if self.vencedor == 'blue':
            return list(self.time_blue)
        if self.vencedor == 'red':
            return list(self.time_red)
        return []

    def get_loser_ids(self) -> List[str]:
        """Retorna IDs do time perdedor como str."""
        if self.vencedor == 'blue':
            return list(self.time_red)
        if self.vencedor == 'red':
            return list(self.time_blue)
        return []

    def __repr__(self) -> str:
        return f"<Match id={self._id} status={self.status} value={self.bet_value}>"
