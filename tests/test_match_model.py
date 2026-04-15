"""
tests/test_match_model.py — Testes unitários do modelo Match.
Roda sem MongoDB: testa apenas lógica pura de estado e helpers.
"""
import pytest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

# Mock das dependências externas antes de importar o modelo
with patch.dict("sys.modules", {
    "utils.datetime_utils": MagicMock(utcnow=lambda: datetime.now(timezone.utc)),
}):
    import sys, types
    # Garante que o módulo mockado está disponível
    mod = types.ModuleType("utils.datetime_utils")
    mod.utcnow = lambda: datetime.now(timezone.utc)
    sys.modules["utils.datetime_utils"] = mod

    import importlib, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
    from models.match import Match


# ── Fixtures ──────────────────────────────────────────────────

def _make_match(**overrides) -> Match:
    base = {
        "guild_id":    "123",
        "channel_id":  "456",
        "channel_name": "x1-mob",
        "match_type":  "x1",
        "platform":    "mob",
        "bet_value":   50.0,
        "gel_type":    "normal",
        "player_ids":  ["111", "222"],
        "max_players": 2,
        "time_blue":   ["111"],
        "time_red":    ["222"],
        "mediator_id": "999",
        "status":      Match.STATUS_AGUARDANDO_PAGAMENTO,
    }
    base.update(overrides)
    return Match(base)


# ── Testes de construção ───────────────────────────────────────

class TestMatchConstruction:

    def test_default_status_aguardando_pagamento(self):
        m = _make_match()
        assert m.status == Match.STATUS_AGUARDANDO_PAGAMENTO

    def test_player_ids_convertidos_para_str(self):
        m = _make_match(player_ids=[111, 222])
        assert m.player_ids == ["111", "222"]

    def test_mediator_id_como_str(self):
        m = _make_match(mediator_id=999)
        assert m.mediator_id == "999"

    def test_mediator_id_none_quando_ausente(self):
        m = _make_match(mediator_id=None)
        assert m.mediator_id is None

    def test_gel_type_default_normal(self):
        m = Match({"gel_type": None})
        assert m.gel_type == "normal"

    def test_to_dict_contem_todas_as_chaves(self):
        m = _make_match()
        d = m.to_dict()
        expected_keys = [
            "_id", "guild_id", "channel_id", "channel_name", "match_type",
            "platform", "bet_value", "gel_type", "player_ids", "max_players",
            "time_blue", "time_red", "mediator_id", "status", "thread_id",
            "vencedor", "winner_id", "proof_url", "pagamento_confirmado",
            "premio_entregue_mediador", "premio_confirmado_jogador",
            "cancelled_by", "cancel_reason", "created_at", "updated_at",
            "started_at", "completed_at", "cancelled_at", "finished_at",
        ]
        for key in expected_keys:
            assert key in d, f"Chave '{key}' ausente em to_dict()"


# ── Testes de estado ───────────────────────────────────────────

class TestMatchStatus:

    def test_is_active_aguardando_pagamento(self):
        m = _make_match(status=Match.STATUS_AGUARDANDO_PAGAMENTO)
        assert m.is_active() is True

    def test_is_active_em_andamento(self):
        m = _make_match(status=Match.STATUS_EM_ANDAMENTO)
        assert m.is_active() is True

    def test_is_active_false_quando_finalizado(self):
        m = _make_match(status=Match.STATUS_FINALIZADO)
        assert m.is_active() is False

    def test_is_active_false_quando_cancelado(self):
        m = _make_match(status=Match.STATUS_CANCELADO)
        assert m.is_active() is False

    def test_is_finished_finalizado(self):
        m = _make_match(status=Match.STATUS_FINALIZADO)
        assert m.is_finished() is True

    def test_is_finished_cancelado(self):
        m = _make_match(status=Match.STATUS_CANCELADO)
        assert m.is_finished() is True

    def test_is_finished_false_em_andamento(self):
        m = _make_match(status=Match.STATUS_EM_ANDAMENTO)
        assert m.is_finished() is False


# ── Testes de transição ────────────────────────────────────────

class TestMatchTransition:

    def test_transicao_valida_pagamento_para_inicio(self):
        m = _make_match(status=Match.STATUS_AGUARDANDO_PAGAMENTO)
        assert m.can_transition_to(Match.STATUS_AGUARDANDO_INICIO) is True

    def test_transicao_valida_inicio_para_andamento(self):
        m = _make_match(status=Match.STATUS_AGUARDANDO_INICIO)
        assert m.can_transition_to(Match.STATUS_EM_ANDAMENTO) is True

    def test_transicao_valida_andamento_para_premio(self):
        m = _make_match(status=Match.STATUS_EM_ANDAMENTO)
        assert m.can_transition_to(Match.STATUS_AGUARDANDO_PREMIO) is True

    def test_transicao_valida_premio_para_finalizado(self):
        m = _make_match(status=Match.STATUS_AGUARDANDO_PREMIO)
        assert m.can_transition_to(Match.STATUS_FINALIZADO) is True

    def test_transicao_invalida_pula_estado(self):
        m = _make_match(status=Match.STATUS_AGUARDANDO_PAGAMENTO)
        assert m.can_transition_to(Match.STATUS_EM_ANDAMENTO) is False

    def test_transicao_invalida_retroativa(self):
        m = _make_match(status=Match.STATUS_EM_ANDAMENTO)
        assert m.can_transition_to(Match.STATUS_AGUARDANDO_PAGAMENTO) is False

    def test_cancelar_sempre_possivel_quando_ativo(self):
        for status in Match.ACTIVE_STATUSES:
            m = _make_match(status=status)
            assert m.can_transition_to(Match.STATUS_CANCELADO) is True

    def test_cancelar_impossivel_quando_ja_finalizado(self):
        m = _make_match(status=Match.STATUS_FINALIZADO)
        assert m.can_transition_to(Match.STATUS_CANCELADO) is False


# ── Testes de helpers de times ─────────────────────────────────

class TestMatchTeamHelpers:

    def test_get_winner_ids_blue(self):
        m = _make_match(vencedor="blue", time_blue=["111"], time_red=["222"])
        assert m.get_winner_ids() == ["111"]

    def test_get_winner_ids_red(self):
        m = _make_match(vencedor="red", time_blue=["111"], time_red=["222"])
        assert m.get_winner_ids() == ["222"]

    def test_get_winner_ids_none_sem_vencedor(self):
        m = _make_match(vencedor=None)
        assert m.get_winner_ids() == []

    def test_get_loser_ids_blue_vence(self):
        m = _make_match(vencedor="blue", time_blue=["111"], time_red=["222"])
        assert m.get_loser_ids() == ["222"]

    def test_get_loser_ids_red_vence(self):
        m = _make_match(vencedor="red", time_blue=["111"], time_red=["222"])
        assert m.get_loser_ids() == ["111"]

    def test_get_all_player_ids(self):
        m = _make_match(player_ids=["111", "222"])
        assert sorted(m.get_all_player_ids()) == ["111", "222"]

    def test_repr_contem_status_e_valor(self):
        m = _make_match(bet_value=100.0, status=Match.STATUS_EM_ANDAMENTO)
        r = repr(m)
        assert "em_andamento" in r
        assert "100.0" in r
