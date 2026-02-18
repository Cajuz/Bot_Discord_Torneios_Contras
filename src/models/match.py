from datetime import datetime
from typing import Optional, Dict, Any, List
from bson import ObjectId


class Match:
    """Modelo de Partida"""

    # ✏️ Status antigos removidos, novos estados do fluxo de thread
    STATUS_AGUARDANDO_PAGAMENTO = 'aguardando_pagamento'
    STATUS_AGUARDANDO_INICIO    = 'aguardando_inicio'
    STATUS_EM_ANDAMENTO         = 'em_andamento'
    STATUS_AGUARDANDO_RESULTADO = 'aguardando_resultado'
    STATUS_AGUARDANDO_PREMIO    = 'aguardando_premio'
    STATUS_CONCLUIDO            = 'concluido'
    STATUS_CANCELADO            = 'cancelado'

    # ✏️ Lista de estados considerados "ativos" (útil para queries)
    ACTIVE_STATUSES = [
        'aguardando_pagamento',
        'aguardando_inicio',
        'em_andamento',
        'aguardando_resultado',
        'aguardando_premio'
    ]

    def __init__(self, data: Dict[str, Any]):
        self._id         = data.get('_id')
        self.guild_id    = data.get('guild_id')       # ✏️ adicionado (usado no match_service)
        self.channel_id  = data.get('channel_id')     # ✏️ adicionado
        self.channel_name = data.get('channel_name')
        self.match_type  = data.get('match_type')     # 1x1, 2x2, 3x3, 4x4
        self.platform    = data.get('platform')       # mob, emu, misto
        self.bet_value   = data.get('bet_value')
        self.gel_type    = data.get('gel_type', 'normal')  # ✏️ adicionado

        # Jogadores
        self.player_ids  = data.get('player_ids', [])  # ✏️ era "players", alinhado com match_service
        self.max_players = data.get('max_players', 2)
        self.time_blue   = data.get('time_blue', [])   # ✏️ novo
        self.time_red    = data.get('time_red', [])    # ✏️ novo

        # Mediador
        self.mediator_id = data.get('mediator_id')     # ✏️ unificado (era mediator_id + mediator_discord_id)

        # Status e controle
        self.status      = data.get('status', self.STATUS_AGUARDANDO_PAGAMENTO)  # ✏️
        self.thread_id   = data.get('thread_id')

        # Resultado
        self.vencedor    = data.get('vencedor')        # ✏️ era "winner_team" com valores "team1/team2", agora "blue"/"red"
        self.proof_url   = data.get('proof_url')

        # ✏️ Flags do fluxo de prêmio
        self.pagamento_confirmado       = data.get('pagamento_confirmado', False)
        self.premio_entregue_mediador   = data.get('premio_entregue_mediador', False)
        self.premio_confirmado_jogador  = data.get('premio_confirmado_jogador', False)

        # Timestamps
        self.started_at   = data.get('started_at')
        self.completed_at = data.get('completed_at')
        self.cancelled_at = data.get('cancelled_at')   # ✏️ novo
        self.created_at   = data.get('created_at', datetime.utcnow())   # ✏️ utcnow() consistente
        self.updated_at   = data.get('updated_at', datetime.utcnow())

    def to_dict(self) -> Dict[str, Any]:
        return {
            '_id': self._id,
            'guild_id': self.guild_id,
            'channel_id': self.channel_id,
            'channel_name': self.channel_name,
            'match_type': self.match_type,
            'platform': self.platform,
            'bet_value': self.bet_value,
            'gel_type': self.gel_type,
            'player_ids': self.player_ids,
            'max_players': self.max_players,
            'time_blue': self.time_blue,
            'time_red': self.time_red,
            'mediator_id': self.mediator_id,
            'status': self.status,
            'thread_id': self.thread_id,
            'vencedor': self.vencedor,
            'proof_url': self.proof_url,
            'pagamento_confirmado': self.pagamento_confirmado,
            'premio_entregue_mediador': self.premio_entregue_mediador,
            'premio_confirmado_jogador': self.premio_confirmado_jogador,
            'started_at': self.started_at,
            'completed_at': self.completed_at,
            'cancelled_at': self.cancelled_at,
            'created_at': self.created_at,
            'updated_at': datetime.utcnow()
        }

    # ✏️ Helpers úteis
    def is_active(self) -> bool:
        return self.status in self.ACTIVE_STATUSES

    def is_finished(self) -> bool:
        return self.status in (self.STATUS_CONCLUIDO, self.STATUS_CANCELADO)

    def get_all_player_ids(self) -> List:
        """Retorna todos os jogadores (compatível com player_ids como int ou str)"""
        return [int(pid) for pid in self.player_ids]

    def get_winner_ids(self) -> List:
        """Retorna IDs do time vencedor"""
        if self.vencedor == 'blue':
            return [int(uid) for uid in self.time_blue]
        if self.vencedor == 'red':
            return [int(uid) for uid in self.time_red]
        return []

    def __repr__(self) -> str:
        return f"<Match id={self._id} status={self.status} value={self.bet_value}>"
