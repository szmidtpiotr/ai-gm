"""TDD: Issue #760 — czytniki MCP/API: world-snapshots + llm-calls (debug bez replayu)."""
import json
import sqlite3
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.api import campaigns as camp


@pytest.fixture()
def tmp_db(monkeypatch):
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    conn = sqlite3.connect(tmp.name)
    conn.executescript("""
        CREATE TABLE world_state_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT, campaign_id INTEGER, turn_number INTEGER,
            snapshot_json TEXT, snapshot_source TEXT, created_at TEXT DEFAULT (datetime('now')));
        CREATE TABLE llm_call_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT, campaign_id INTEGER, call_type TEXT, model TEXT,
            prompt_tokens INTEGER, completion_tokens INTEGER, latency_ms INTEGER, cache_hit INTEGER,
            error TEXT, created_at TEXT DEFAULT (datetime('now')));
    """)
    snap = {
        "scene_enemies": [{"key": "skeleton", "name": "Szkielet", "hp": 12}],
        "scene_npcs": [{"name": "Karczmarz"}],
        "active_quests": [{"title": "Znajdź miecz"}],
        "player_conditions": [{"key": "blessed"}],
        "scene_cleared": False,
    }
    conn.execute(
        "INSERT INTO world_state_snapshots (campaign_id, turn_number, snapshot_json, snapshot_source) VALUES (?,?,?,?)",
        (5, 3, json.dumps(snap), "auto_save"),
    )
    conn.execute(
        "INSERT INTO llm_call_log (campaign_id, call_type, model, prompt_tokens, completion_tokens, latency_ms, cache_hit, error) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (5, "narrative", "gpt-5.4", 1200, 300, 850, 0, None),
    )
    conn.commit()
    conn.close()
    monkeypatch.setattr(camp, "DB_PATH", tmp.name)
    yield tmp.name
    Path(tmp.name).unlink(missing_ok=True)


# ─── Test główny — world-snapshots przycina surowy JSON do kluczowych pól ──────

def test_world_snapshots_trimmed(tmp_db):
    res = camp.get_campaign_world_snapshots(campaign_id=5, from_turn=None, to_turn=None, limit=50)
    assert res["count"] == 1
    s = res["snapshots"][0]
    assert s["turn_number"] == 3
    assert s["enemy_count"] == 1
    assert s["enemies"][0]["name"] == "Szkielet" and s["enemies"][0]["hp"] == 12
    assert s["npcs"] == ["Karczmarz"]
    assert s["quests"] == ["Znajdź miecz"]
    assert s["conditions"] == ["blessed"]
    assert s["scene_cleared"] is False
    # przycięcie: brak surowego narrative_state / pełnego JSON-a
    assert "narrative_state" not in s


def test_world_snapshots_empty_for_other_campaign(tmp_db):
    res = camp.get_campaign_world_snapshots(campaign_id=999, from_turn=None, to_turn=None, limit=50)
    assert res["count"] == 0 and res["snapshots"] == []


# ─── Test główny — llm-calls zwraca telemetrię per call ────────────────────────

def test_llm_calls_returns_telemetry(tmp_db):
    res = camp.get_campaign_llm_calls(campaign_id=5, call_type=None, limit=50)
    assert res["count"] == 1
    c = res["llm_calls"][0]
    assert c["call_type"] == "narrative" and c["model"] == "gpt-5.4"
    assert c["prompt_tokens"] == 1200 and c["latency_ms"] == 850


def test_llm_calls_filter_by_type(tmp_db):
    assert camp.get_campaign_llm_calls(campaign_id=5, call_type="summary", limit=50)["count"] == 0
    assert camp.get_campaign_llm_calls(campaign_id=5, call_type="narrative", limit=50)["count"] == 1
