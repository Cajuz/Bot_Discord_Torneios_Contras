"""
tests/test_queue_model.py — Testes unitários do modelo MatchQueue.
Roda sem MongoDB: testa apenas lógica pura de fila, confirmações e expiração.
"""
import pytest
import sys, os, types
from datetime import datetime, timezone, timedelta
from unittest.mock import patch
from bson import ObjectId

# Mock das dependências externas
mod = types.ModuleType("utils.datetime_utils")
mod.utcnow = lambda: datetime.now(timezone.utc)
sys.modules["utils.datetime_utils"] = mod
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from models.queue import MatchQueue


# ── Fixtures ──────────────────────────────────────────────────

def _make_queue(**overrides) -> MatchQueue:
    base = dict(
        channel_name="x1-mob",
        bet_value=50.0,
        gel_type="normal",
        max_players=2,
        players=[101, 102],
    )
    base.update(overrides)
    return MatchQueue(**base)


# ── Testes de construção ───────────────────────────────────────

class TestMatchQueueConstruction:

    def test_status_inicial_waiting(self):
        q = _make_queue(players=[])
        assert q.status == MatchQueue.STATUS_WAITING

    def test_id_gerado_automaticamente(self):
        q = _make_queue()
        assert isinstance(q._id, ObjectId)

    def test_players_vazio_por_default(self):
        q = _make_queue(players=[])
        assert q.players == []

    def test_confirmations_vazio_por_default(self):
        q = _make_queue()
        assert q.confirmations == []

    def test_to_dict_contem_chaves_essenciais(self):
        q = _make_queue()
        d = q.to_dict()
        for key in ["_id", "channel_name", "bet_value", "gel_type",
                    "max_players", "players", "status", "created_at",
                    "expires_at", "confirmation_message_id", "confirmations",
                    "thread_id", "guild_id", "match_id"]:
            assert key in d, f"Chave '{key}' ausente em to_dict()"

    def test_from_dict_reconstroi_objeto(self):
        q = _make_queue(guild_id=999, match_id="abc123")
        d = q.to_dict()
        q2 = MatchQueue.from_dict(d)
        assert q2.channel_name == q.channel_name
        assert q2.bet_value    == q.bet_value
        assert q2.gel_type     == q.gel_type
        assert q2.guild_id     == q.guild_id
        assert q2.match_id     == q.match_id
        assert q2._id          == q._id

    def test_from_dict_aceita_id_como_string(self):
        q = _make_queue()
        d = q.to_dict()
        d["_id"] = str(d["_id"])   # simula o que vem do MongoDB via JSON
        q2 = MatchQueue.from_dict(d)
        assert isinstance(q2._id, ObjectId)


# ── Testes de is_full ─────────────────────────────────────────

class TestMatchQueueFull:

    def test_nao_cheia_com_1_de_2(self):
        q = _make_queue(players=[1], max_players=2)
        assert q.is_full() is False

    def test_cheia_com_2_de_2(self):
        q = _make_queue(players=[1, 2], max_players=2)
        assert q.is_full() is True

    def test_vazia_nao_cheia(self):
        q = _make_queue(players=[], max_players=2)
        assert q.is_full() is False


# ── Testes de add/remove player ───────────────────────────────

class TestMatchQueuePlayers:

    def test_add_player_novo(self):
        q = _make_queue(players=[])
        assert q.add_player(10) is True
        assert 10 in q.players

    def test_add_player_duplicado_retorna_false(self):
        q = _make_queue(players=[10])
        assert q.add_player(10) is False
        assert q.players.count(10) == 1

    def test_add_player_fila_cheia_retorna_false(self):
        q = _make_queue(players=[1, 2], max_players=2)
        assert q.add_player(3) is False
        assert 3 not in q.players

    def test_remove_player_existente(self):
        q = _make_queue(players=[10, 20])
        assert q.remove_player(10) is True
        assert 10 not in q.players

    def test_remove_player_inexistente_retorna_false(self):
        q = _make_queue(players=[10])
        assert q.remove_player(99) is False


# ── Testes de confirmações ─────────────────────────────────────

class TestMatchQueueConfirmations:

    def test_add_confirmation_valido(self):
        q = _make_queue(players=[1, 2])
        assert q.add_confirmation(1) is True
        assert 1 in q.confirmations

    def test_add_confirmation_duplicado_retorna_false(self):
        q = _make_queue(players=[1, 2])
        q.add_confirmation(1)
        assert q.add_confirmation(1) is False

    def test_add_confirmation_player_fora_da_fila_retorna_false(self):
        q = _make_queue(players=[1, 2])
        assert q.add_confirmation(99) is False

    def test_all_confirmed_true(self):
        q = _make_queue(players=[1, 2])
        q.add_confirmation(1)
        q.add_confirmation(2)
        assert q.all_confirmed() is True

    def test_all_confirmed_false_parcial(self):
        q = _make_queue(players=[1, 2])
        q.add_confirmation(1)
        assert q.all_confirmed() is False

    def test_pending_confirmations(self):
        q = _make_queue(players=[1, 2, 3])
        q.add_confirmation(1)
        pending = q.pending_confirmations()
        assert 2 in pending
        assert 3 in pending
        assert 1 not in pending


# ── Testes de expiração ────────────────────────────────────────

class TestMatchQueueExpiry:

    def test_nao_expirado_sem_expires_at(self):
        q = _make_queue()
        assert q.is_expired() is False

    def test_expirado_quando_expires_at_no_passado(self):
        passado = datetime.now(timezone.utc) - timedelta(seconds=10)
        q = _make_queue(expires_at=passado)
        assert q.is_expired() is True

    def test_nao_expirado_quando_expires_at_no_futuro(self):
        futuro = datetime.now(timezone.utc) + timedelta(seconds=300)
        q = _make_queue(expires_at=futuro)
        assert q.is_expired() is False


# ── Testes de mark_as_matched ─────────────────────────────────

class TestMatchQueueMatched:

    def test_mark_as_matched_muda_status(self):
        q = _make_queue()
        q.mark_as_matched("match_id_abc")
        assert q.status   == MatchQueue.STATUS_MATCHED
        assert q.match_id == "match_id_abc"

    def test_repr_contem_dados_essenciais(self):
        q = _make_queue(channel_name="x1-mob", bet_value=75.0)
        r = repr(q)
        assert "x1-mob" in r
        assert "75.0"   in r
