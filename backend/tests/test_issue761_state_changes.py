"""TDD: Issue #761 — rejestr zmian zasobów/kondycji gracza (state_changes)."""
import sqlite3
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import migrations_admin
from app.services import state_log_service as sls


@pytest.fixture()
def tmp_db(monkeypatch):
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    conn = sqlite3.connect(tmp.name)
    conn.execute("CREATE TABLE campaigns (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT)")
    migrations_admin._ensure_state_changes_table(conn)
    conn.commit(); conn.close()
    monkeypatch.setattr(sls, "STATE_LOG_DB_PATH", tmp.name)
    yield tmp.name
    Path(tmp.name).unlink(missing_ok=True)


def test_migration_creates_state_changes_table(tmp_db):
    conn = sqlite3.connect(tmp_db)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(state_changes)").fetchall()}
    conn.close()
    assert {"resource", "before_val", "after_val", "delta", "cause", "turn_number"}.issubset(cols)


def test_record_computes_delta_and_roundtrip(tmp_db):
    rid = sls.record_state_change(
        campaign_id=7, resource="hp", character_id=3, turn_number=2.0, combat_id=9,
        before_val=20, after_val=13, cause="combat_damage", meta={"enemy_name": "Szkielet"},
    )
    assert rid and rid > 0
    rows = sls.query_state_changes(7)
    assert len(rows) == 1
    r = rows[0]
    assert r["resource"] == "hp" and r["delta"] == -7        # 13-20 auto-policzone
    assert r["before_val"] == "20" and r["after_val"] == "13"
    assert r["cause"] == "combat_damage" and r["meta"]["enemy_name"] == "Szkielet"


def test_filter_by_resource(tmp_db):
    sls.record_state_change(campaign_id=1, resource="hp", before_val=10, after_val=5)
    sls.record_state_change(campaign_id=1, resource="zone", before_val="engaged", after_val="ranged")
    sls.record_state_change(campaign_id=1, resource="mana", before_val=8, after_val=4)
    assert len(sls.query_state_changes(1, resource="hp")) == 1
    assert len(sls.query_state_changes(1, resource="zone")) == 1
    assert len(sls.query_state_changes(1)) == 3


def test_survives_campaign_delete(tmp_db):
    conn = sqlite3.connect(tmp_db)
    cid = conn.execute("INSERT INTO campaigns (name) VALUES ('loch')").lastrowid
    conn.commit(); conn.close()
    sls.record_state_change(campaign_id=cid, resource="hp", before_val=10, after_val=0, cause="combat_damage")
    conn = sqlite3.connect(tmp_db)
    conn.execute("DELETE FROM campaigns WHERE id=?", (cid,)); conn.commit(); conn.close()
    assert len(sls.query_state_changes(cid)) == 1


def test_record_never_raises_on_bad_db(monkeypatch):
    monkeypatch.setattr(sls, "STATE_LOG_DB_PATH", "/nonexistent/x.db")
    assert sls.record_state_change(campaign_id=1, resource="hp", before_val=1, after_val=0) is None
