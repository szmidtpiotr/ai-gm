"""TDD #789 — G5: Conflict resolution — inicjatywa jako kolejność; 'Cel już martwy/zabrany'."""
import sqlite3
import sys
import os
import json

sys.path.insert(0, "/app")
os.environ.setdefault("AIGM_E2E_LITE", "1")

import pytest

# ── DB schema helper ──────────────────────────────────────────────────────────

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL DEFAULT '',
    display_name TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS campaigns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    system_id TEXT NOT NULL DEFAULT 'fantasy',
    model_id TEXT NOT NULL DEFAULT 'gpt-4',
    owner_user_id INTEGER NOT NULL DEFAULT 1,
    mode TEXT NOT NULL DEFAULT 'multiplayer',
    status TEXT NOT NULL DEFAULT 'active',
    round_timer_minutes INTEGER NOT NULL DEFAULT 1440,
    round_timer_hours INTEGER NOT NULL DEFAULT 24,
    max_players INTEGER NOT NULL DEFAULT 4,
    host_user_id INTEGER,
    lobby_status TEXT NOT NULL DEFAULT 'open',
    host_note TEXT,
    template_id INTEGER
);
CREATE TABLE IF NOT EXISTS campaign_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    role TEXT NOT NULL DEFAULT 'player',
    status TEXT NOT NULL DEFAULT 'accepted',
    character_id INTEGER,
    joined_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    absence_warnings INTEGER NOT NULL DEFAULT 0,
    UNIQUE(campaign_id, user_id)
);
CREATE TABLE IF NOT EXISTS characters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    system_id TEXT NOT NULL DEFAULT 'fantasy',
    sheet_json TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS campaign_rounds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL,
    round_number INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'collecting',
    deadline TEXT,
    closed_at TEXT,
    narrative_json TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS campaign_round_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    round_id INTEGER NOT NULL,
    campaign_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    character_id INTEGER,
    character_name TEXT NOT NULL,
    action_text TEXT NOT NULL,
    submitted_at TEXT NOT NULL DEFAULT (datetime('now')),
    initiative_roll INTEGER NOT NULL DEFAULT 0,
    UNIQUE(round_id, user_id)
);
"""


def _make_test_db(tmp_path):
    db_path = str(tmp_path / "test_789.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    conn.commit()
    return db_path, conn


def _seed_db(conn):
    conn.execute("INSERT INTO users (username) VALUES ('alice')")
    conn.execute("INSERT INTO users (username) VALUES ('bob')")
    conn.execute("INSERT INTO campaigns (title, owner_user_id, host_user_id) VALUES ('Camp', 1, 1)")
    conn.execute("INSERT INTO campaign_members (campaign_id, user_id, status) VALUES (1, 1, 'accepted')")
    conn.execute("INSERT INTO campaign_members (campaign_id, user_id, status) VALUES (1, 2, 'accepted')")
    # Alice: DEX 16 (+3 mod), Bob: DEX 8 (-1 mod)
    conn.execute(
        "INSERT INTO characters (campaign_id, user_id, name, system_id, sheet_json) "
        "VALUES (1, 1, 'Alicja', 'fantasy', '{\"stats\":{\"DEX\":16}}')"
    )
    conn.execute(
        "INSERT INTO characters (campaign_id, user_id, name, system_id, sheet_json) "
        "VALUES (1, 2, 'Robert', 'fantasy', '{\"stats\":{\"DEX\":8}}')"
    )
    conn.execute(
        "INSERT INTO campaign_rounds (campaign_id, round_number, status) VALUES (1, 1, 'collecting')"
    )
    conn.commit()


# ── Tests: resolve_initiative_conflicts (pure function) ───────────────────────

def test_conflict_enemy_lower_init_gets_note():
    """Lower-initiative player targeting same enemy as higher-init gets 'Cel już martwy'."""
    from app.services.multiplayer_round_service import resolve_initiative_conflicts

    scene_enemies = [{"key": "goblin", "name": "Goblin"}]
    actions = [
        {"user_id": 1, "character_name": "Alicja", "action_text": "Atakuję Goblina!", "initiative_roll": 18},
        {"user_id": 2, "character_name": "Robert", "action_text": "Uderzam Goblina toporem!", "initiative_roll": 7},
    ]

    resolved = resolve_initiative_conflicts(actions, scene_enemies)

    assert resolved[0]["user_id"] == 1, "Higher initiative must be first"
    assert resolved[0].get("conflict_note") is None, "Higher init has no conflict"

    assert resolved[1]["user_id"] == 2, "Lower initiative second"
    note = resolved[1].get("conflict_note", "")
    assert note, "Lower init targeting same enemy must have conflict_note"
    assert "martwy" in note.lower() or "zabrany" in note.lower()


def test_no_conflict_different_targets():
    """Two players targeting different enemies → no conflict notes."""
    from app.services.multiplayer_round_service import resolve_initiative_conflicts

    scene_enemies = [
        {"key": "goblin", "name": "Goblin"},
        {"key": "orc", "name": "Ork"},
    ]
    actions = [
        {"user_id": 1, "character_name": "Alicja", "action_text": "Atakuję Goblina!", "initiative_roll": 18},
        {"user_id": 2, "character_name": "Robert", "action_text": "Uderzam Orka!", "initiative_roll": 7},
    ]

    resolved = resolve_initiative_conflicts(actions, scene_enemies)
    for r in resolved:
        assert r.get("conflict_note") is None, f"Unexpected conflict_note: {r.get('conflict_note')}"


def test_order_by_initiative_desc():
    """Returned list always sorted by initiative_roll descending."""
    from app.services.multiplayer_round_service import resolve_initiative_conflicts

    actions = [
        {"user_id": 3, "character_name": "C", "action_text": "x", "initiative_roll": 5},
        {"user_id": 1, "character_name": "A", "action_text": "x", "initiative_roll": 20},
        {"user_id": 2, "character_name": "B", "action_text": "x", "initiative_roll": 12},
    ]
    resolved = resolve_initiative_conflicts(actions, scene_enemies=[])
    rolls = [r["initiative_roll"] for r in resolved]
    assert rolls == sorted(rolls, reverse=True), f"Expected descending order, got {rolls}"


def test_three_players_conflict_two_lose():
    """3 players targeting same enemy — only first (highest init) keeps claim; others get note."""
    from app.services.multiplayer_round_service import resolve_initiative_conflicts

    scene_enemies = [{"key": "boss", "name": "Boss"}]
    actions = [
        {"user_id": 1, "character_name": "A", "action_text": "Atakuję Bossa!", "initiative_roll": 19},
        {"user_id": 2, "character_name": "B", "action_text": "Bije Bossa!", "initiative_roll": 11},
        {"user_id": 3, "character_name": "C", "action_text": "Trafiam Bossa!", "initiative_roll": 5},
    ]
    resolved = resolve_initiative_conflicts(actions, scene_enemies)

    assert resolved[0].get("conflict_note") is None, "Highest init has no conflict"
    assert resolved[1].get("conflict_note") is not None, "Second init must have conflict"
    assert resolved[2].get("conflict_note") is not None, "Third init must have conflict"


def test_does_not_mutate_input():
    """resolve_initiative_conflicts must not modify the input list."""
    from app.services.multiplayer_round_service import resolve_initiative_conflicts

    scene_enemies = [{"key": "goblin", "name": "Goblin"}]
    actions = [
        {"user_id": 1, "character_name": "A", "action_text": "Atakuję Goblina!", "initiative_roll": 18},
        {"user_id": 2, "character_name": "B", "action_text": "Atakuję Goblina!", "initiative_roll": 5},
    ]
    original_order = [a["user_id"] for a in actions]
    resolve_initiative_conflicts(actions, scene_enemies)
    assert [a["user_id"] for a in actions] == original_order, "Input list must not be mutated"
    assert "conflict_note" not in actions[1], "Input dicts must not be mutated"


# ── Tests: initiative stored in submit_action ─────────────────────────────────

def test_initiative_stored_on_submit(tmp_path, monkeypatch):
    """submit_action stores non-zero initiative_roll derived from character DEX."""
    db_path, conn = _make_test_db(tmp_path)
    _seed_db(conn)
    conn.close()

    import app.services.multiplayer_round_service as svc
    monkeypatch.setattr(svc, "resolve_db_path", lambda: db_path)

    svc.submit_action(
        campaign_id=1, user_id=1, character_id=1,
        character_name="Alicja", action_text="Atakuję!",
    )

    check = sqlite3.connect(db_path)
    check.row_factory = sqlite3.Row
    row = check.execute(
        "SELECT initiative_roll FROM campaign_round_actions WHERE user_id=1"
    ).fetchone()
    check.close()

    assert row is not None, "Action must exist in DB"
    # Alice DEX 16 → mod +3; min d20=1 → initiative ≥ 4
    assert int(row["initiative_roll"]) >= 1, f"initiative_roll must be positive, got {row['initiative_roll']}"


def test_higher_dex_higher_initiative(tmp_path, monkeypatch):
    """Alice (DEX 16 → +3) beats Bob (DEX 8 → -1) when same d20 roll."""
    db_path, conn = _make_test_db(tmp_path)
    _seed_db(conn)
    conn.close()

    import app.services.multiplayer_round_service as svc
    monkeypatch.setattr(svc, "resolve_db_path", lambda: db_path)
    # Fixed d20=10 for determinism
    monkeypatch.setattr(svc, "_d20", lambda: 10)

    svc.submit_action(1, 1, 1, "Alicja", "Atak!")
    svc.submit_action(1, 2, 2, "Robert", "Atak!")

    check = sqlite3.connect(db_path)
    check.row_factory = sqlite3.Row
    alice = check.execute("SELECT initiative_roll FROM campaign_round_actions WHERE user_id=1").fetchone()
    bob = check.execute("SELECT initiative_roll FROM campaign_round_actions WHERE user_id=2").fetchone()
    check.close()

    # Alice: 10+3=13, Bob: 10-1=9
    assert int(alice["initiative_roll"]) > int(bob["initiative_roll"]), (
        f"Alice ({alice['initiative_roll']}) should beat Bob ({bob['initiative_roll']})"
    )
