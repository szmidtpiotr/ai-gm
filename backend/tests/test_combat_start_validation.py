"""TDD: Issue #534 / HF-7 — Walidacja semantyczna celu [COMBAT_START].

_validate_combat_start_target must reject friendly NPCs and unknown targets,
and allow only scene_enemies or game_config_enemies entries.
"""
import sys
import os
import sqlite3
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _make_db():
    """Build a minimal in-memory DB with all required tables."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE game_sessions (
            campaign_id INTEGER PRIMARY KEY,
            scene_enemies TEXT NOT NULL DEFAULT '[]',
            scene_npcs   TEXT NOT NULL DEFAULT '[]'
        );
        CREATE TABLE game_config_enemies (
            key       TEXT PRIMARY KEY,
            label     TEXT,
            hp_base   INTEGER DEFAULT 10,
            ac_base   INTEGER DEFAULT 10,
            attack_bonus INTEGER DEFAULT 0,
            damage_die TEXT DEFAULT '1d6',
            dex_modifier INTEGER DEFAULT 0
        );
        CREATE TABLE campaign_known_npcs (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL,
            npc_name    TEXT NOT NULL
        );
        CREATE TABLE campaign_turns (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id    INTEGER NOT NULL,
            assistant_text TEXT
        );
        CREATE TABLE llm_tag_errors (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL,
            turn_number INTEGER NOT NULL DEFAULT 0,
            tag_raw     TEXT,
            error_type  TEXT,
            ts          TEXT DEFAULT (datetime('now'))
        );
    """)
    return conn


def _validate(conn, campaign_id, enemy_key):
    from app.api.turns import _validate_combat_start_target
    return _validate_combat_start_target(conn, campaign_id, enemy_key)


# ─── Test 1 (regression): scene_enemies target → OK ─────────────────────────

def test_scene_enemy_is_valid():
    """Enemy present in scene_enemies must be accepted (regression)."""
    conn = _make_db()
    scene = [{"key": "goblin_scout", "name": "Goblin Scout", "hp": 8}]
    conn.execute(
        "INSERT INTO game_sessions (campaign_id, scene_enemies) VALUES (?, ?)",
        (1, json.dumps(scene))
    )
    conn.commit()

    valid, reason = _validate(conn, 1, "goblin_scout")
    assert valid is True, f"Expected valid=True for scene enemy, got {valid!r} reason={reason!r}"
    assert reason == "", f"Expected empty reason, got {reason!r}"


def test_scene_enemy_name_match_is_valid():
    """Enemy matched by name (not key) in scene_enemies must be accepted."""
    conn = _make_db()
    scene = [{"key": "goblin_01", "name": "Goblin Łucznik", "hp": 6}]
    conn.execute(
        "INSERT INTO game_sessions (campaign_id, scene_enemies) VALUES (?, ?)",
        (1, json.dumps(scene))
    )
    conn.commit()

    valid, reason = _validate(conn, 1, "Goblin Łucznik")
    assert valid is True, f"Expected valid=True for scene enemy name match, got {valid!r}"


def test_catalog_enemy_is_valid():
    """Enemy present in game_config_enemies catalog must be accepted."""
    conn = _make_db()
    conn.execute(
        "INSERT INTO game_sessions (campaign_id, scene_enemies) VALUES (?, '[]')", (1,)
    )
    conn.execute(
        "INSERT INTO game_config_enemies (key, label) VALUES ('ork_wojownik', 'Ork Wojownik')"
    )
    conn.commit()

    valid, reason = _validate(conn, 1, "ork_wojownik")
    assert valid is True, f"Expected valid=True for catalog enemy, got {valid!r}"


# ─── Test 2 (RED→GREEN): campaign_known_npcs target → REJECT ─────────────────

def test_known_npc_in_campaign_known_npcs_is_rejected():
    """NPC known from campaign_known_npcs must be REJECTED with 'combat_target_friendly_npc'."""
    conn = _make_db()
    conn.execute(
        "INSERT INTO game_sessions (campaign_id, scene_enemies) VALUES (?, '[]')", (1,)
    )
    conn.execute(
        "INSERT INTO campaign_known_npcs (campaign_id, npc_name) VALUES (?, ?)",
        (1, "Starzec")
    )
    conn.commit()

    valid, reason = _validate(conn, 1, "Starzec")
    assert valid is False, f"Expected valid=False for known NPC, got {valid!r}"
    assert reason == "combat_target_friendly_npc", \
        f"Expected 'combat_target_friendly_npc', got {reason!r}"


def test_known_npc_case_insensitive():
    """NPC matching is case-insensitive (LLM may vary capitalisation)."""
    conn = _make_db()
    conn.execute(
        "INSERT INTO game_sessions (campaign_id, scene_enemies) VALUES (?, '[]')", (1,)
    )
    conn.execute(
        "INSERT INTO campaign_known_npcs (campaign_id, npc_name) VALUES (?, ?)",
        (1, "Starzec")
    )
    conn.commit()

    valid, reason = _validate(conn, 1, "starzec")
    assert valid is False, f"Case-insensitive NPC match should reject, got valid={valid!r}"
    assert reason == "combat_target_friendly_npc"


def test_scene_npc_is_rejected():
    """NPC present in scene_npcs must be REJECTED with 'combat_target_friendly_npc'."""
    conn = _make_db()
    scene_npcs = [{"key": "kupiec_jan", "name": "Kupiec Jan", "role": "merchant"}]
    conn.execute(
        "INSERT INTO game_sessions (campaign_id, scene_enemies, scene_npcs) VALUES (?, '[]', ?)",
        (1, json.dumps(scene_npcs))
    )
    conn.commit()

    valid, reason = _validate(conn, 1, "kupiec_jan")
    assert valid is False, f"Expected valid=False for scene NPC, got {valid!r}"
    assert reason == "combat_target_friendly_npc"


# ─── Test 3 (RED→GREEN): completely unknown target → REJECT ──────────────────

def test_unknown_target_is_rejected():
    """A target that is neither enemy nor NPC must be REJECTED with 'combat_target_unknown'."""
    conn = _make_db()
    conn.execute(
        "INSERT INTO game_sessions (campaign_id, scene_enemies) VALUES (?, '[]')", (1,)
    )
    conn.commit()

    valid, reason = _validate(conn, 1, "Xyzzy")
    assert valid is False, f"Expected valid=False for unknown target, got {valid!r}"
    assert reason == "combat_target_unknown", \
        f"Expected 'combat_target_unknown', got {reason!r}"


def test_unknown_target_different_campaign_does_not_affect():
    """NPC in another campaign must not block combat in ours."""
    conn = _make_db()
    # Campaign 1 has no enemies, no npcs
    conn.execute(
        "INSERT INTO game_sessions (campaign_id, scene_enemies) VALUES (?, '[]')", (1,)
    )
    # NPC 'Starzec' exists in campaign 2, NOT campaign 1
    conn.execute(
        "INSERT INTO campaign_known_npcs (campaign_id, npc_name) VALUES (?, ?)",
        (2, "Starzec")
    )
    conn.commit()

    # In campaign 1 "Starzec" is unknown — should be rejected as unknown, not friendly_npc
    valid, reason = _validate(conn, 1, "Starzec")
    assert valid is False
    assert reason == "combat_target_unknown", \
        f"Cross-campaign NPC bleed: expected 'combat_target_unknown', got {reason!r}"
