"""TDD: Issue #762 — rejestr decyzji silnika per tura (turn_decisions)."""
import sqlite3
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import migrations_admin
from app.services import decision_log_service as dls


@pytest.fixture()
def tmp_db(monkeypatch):
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    conn = sqlite3.connect(tmp.name)
    conn.execute("CREATE TABLE campaigns (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT)")
    migrations_admin._ensure_turn_decisions_table(conn)
    conn.commit(); conn.close()
    monkeypatch.setattr(dls, "DECISION_LOG_DB_PATH", tmp.name)
    yield tmp.name
    Path(tmp.name).unlink(missing_ok=True)


def test_migration_creates_turn_decisions_table(tmp_db):
    conn = sqlite3.connect(tmp_db)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(turn_decisions)").fetchall()}
    conn.close()
    assert {"action_type", "confidence", "route", "gate_blocked", "gate_reason",
            "handler", "correction_applied"}.issubset(cols)


def test_record_passed_turn_roundtrip(tmp_db):
    rid = dls.record_turn_decision(
        campaign_id=5, character_id=2, turn_number=1.0, user_text="idę na północ",
        action_type="MOVEMENT", confidence=0.8, route="narrative",
        gate_blocked=False, handler="narrative", meta={"hex": "q2r3"},
    )
    assert rid and rid > 0
    rows = dls.query_turn_decisions(5)
    assert len(rows) == 1
    r = rows[0]
    assert r["action_type"] == "MOVEMENT" and r["route"] == "narrative"
    assert r["gate_blocked"] is False          # bool, nie 0
    assert r["confidence"] == 0.8
    assert r["meta"]["hex"] == "q2r3"


def test_record_blocked_turn_keeps_reason(tmp_db):
    dls.record_turn_decision(
        campaign_id=5, user_text="atakuję karczmarza", action_type="ATTACK",
        route="blocked", gate_blocked=True, gate_reason="combat_target_friendly_npc",
        handler="gate",
    )
    rows = dls.query_turn_decisions(5)
    assert rows[0]["gate_blocked"] is True
    assert rows[0]["gate_reason"] == "combat_target_friendly_npc"


def test_record_never_raises_on_bad_db(monkeypatch):
    monkeypatch.setattr(dls, "DECISION_LOG_DB_PATH", "/nonexistent/x.db")
    assert dls.record_turn_decision(campaign_id=1, action_type="ATTACK") is None
