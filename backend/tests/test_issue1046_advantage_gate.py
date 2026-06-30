"""TDD: Issue #1046 — EPIC bramka przewagi: guard na wroga (#1044) + boot-restore (#1045)."""
import json
import sqlite3
import sys
from unittest.mock import MagicMock

sys.path.insert(0, "/app")


# ─── #1044: Guard na wroga ────────────────────────────────────────────────────

def test_stealth_gate_not_set_without_scene_enemies():
    """#1044: stealth success z pustą sceną → _stealth_should_emit_gate zwraca False.
    Brak wroga = skradanie czysto narracyjne, bramka nie potrzebna.
    """
    from app.api.turns import _stealth_should_emit_gate

    conn = MagicMock()
    row = MagicMock()
    row.__getitem__ = lambda s, k: "[]"
    conn.execute.return_value.fetchone.return_value = row

    assert _stealth_should_emit_gate(conn, campaign_id=99) is False


def test_stealth_gate_set_with_scene_enemies():
    """#1044: stealth success gdy wrogowie w scenie → _stealth_should_emit_gate zwraca True."""
    from app.api.turns import _stealth_should_emit_gate

    conn = MagicMock()
    row = MagicMock()
    row.__getitem__ = lambda s, k: '[{"key": "goblin", "hp_current": 12}]'
    conn.execute.return_value.fetchone.return_value = row

    assert _stealth_should_emit_gate(conn, campaign_id=99) is True


def test_stealth_gate_set_when_scene_enemies_is_null():
    """#1044: NULL scene_enemies traktowane jak [] → brak bramki."""
    from app.api.turns import _stealth_should_emit_gate

    conn = MagicMock()
    row = MagicMock()
    row.__getitem__ = lambda s, k: None  # NULL w bazie
    conn.execute.return_value.fetchone.return_value = row

    assert _stealth_should_emit_gate(conn, campaign_id=99) is False


# ─── #1045: Boot-restore ─────────────────────────────────────────────────────

def test_campaign_surfaces_pending_gate_when_flag_set():
    """#1045: gdy session_flags.pending_zaskoczony=True, kampania eksponuje pending_advantage_gate."""
    from app.api.campaigns import _maybe_add_pending_advantage_gate

    row_dict: dict = {}
    sf: dict = {"pending_zaskoczony": True}
    _maybe_add_pending_advantage_gate(row_dict, sf)

    assert "pending_advantage_gate" in row_dict, "kampania powinna zwracać pending_advantage_gate"
    gate = row_dict["pending_advantage_gate"]
    assert isinstance(gate, dict)
    assert "options" in gate
    option_ids = [o["id"] for o in gate["options"]]
    assert "strike" in option_ids
    assert "intimidate" in option_ids
    assert "withdraw" in option_ids
    assert "dialog" in option_ids


def test_campaign_no_gate_when_flag_absent():
    """#1045 backward compat: brak pending_zaskoczony → brak pending_advantage_gate w payloadzie."""
    from app.api.campaigns import _maybe_add_pending_advantage_gate

    row_dict: dict = {}
    sf: dict = {}
    _maybe_add_pending_advantage_gate(row_dict, sf)

    assert "pending_advantage_gate" not in row_dict


def test_campaign_no_gate_when_flag_false():
    """#1045 backward compat: pending_zaskoczony=False → brak bramki."""
    from app.api.campaigns import _maybe_add_pending_advantage_gate

    row_dict: dict = {}
    sf: dict = {"pending_zaskoczony": False}
    _maybe_add_pending_advantage_gate(row_dict, sf)

    assert "pending_advantage_gate" not in row_dict


# ─── Regresja: build_advantage_gate ma 4 opcje ───────────────────────────────

def test_build_advantage_gate_has_all_options():
    """Regresja: build_advantage_gate('stealth') musi mieć 4 opcje (strike/intimidate/withdraw/dialog)."""
    from app.services.combat_service import build_advantage_gate

    gate = build_advantage_gate("stealth")
    assert gate is not None
    ids = [o["id"] for o in gate["options"]]
    assert ids == ["strike", "intimidate", "withdraw", "dialog"]
