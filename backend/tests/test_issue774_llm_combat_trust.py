"""TDD: Issue #774 — LLM-authored COMBAT_START trusted after friendly-NPC gate.

Bug: _validate_combat_start_target(source='llm') required enemy key to exist in
game_config_enemies catalog. LLM-invented keys (e.g. 'nozownik', 'napastnik')
were rejected → correction message appended → [COMBAT_START] tag leaked to player.

Fix: after the friendly-NPC gate, source='llm' returns (True, '') unconditionally.
initiate_combat() handles unknown keys via INSERT OR IGNORE with pending_review.
"""
import sys
import os
import sqlite3
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _make_db():
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


def _validate(conn, campaign_id, enemy_key, assistant_text="", source="injected"):
    from app.api.turns import _validate_combat_start_target
    return _validate_combat_start_target(conn, campaign_id, enemy_key, assistant_text, source=source)


# ─── Test 1 (#774 regression): LLM key not in catalog → MUST be trusted ────

def test_llm_invented_key_not_in_catalog_is_trusted():
    """#774: LLM emits [COMBAT_START:nozownik] but 'nozownik' is not in game_config_enemies.
    With source='llm' the validation must return (True,'') after the friendly-NPC gate.
    Previously returned (False,'combat_target_unknown') → caused tag to leak."""
    conn = _make_db()
    conn.execute(
        "INSERT INTO game_sessions (campaign_id, scene_enemies, scene_npcs) VALUES (?, '[]', '[]')",
        (1,),
    )
    conn.commit()

    # 'nozownik' — LLM-invented key, absent from catalog and scene_enemies
    valid, reason = _validate(conn, 1, "nozownik", source="llm")
    assert valid is True, (
        f"#774: LLM-authored key 'nozownik' should be trusted (not in catalog). "
        f"Got valid={valid!r}, reason={reason!r}"
    )
    assert reason == "", f"Expected empty reason, got {reason!r}"


def test_llm_invented_key_napastnik_is_trusted():
    """#774: Another LLM-invented key 'napastnik' (no catalog entry, no scene entry)."""
    conn = _make_db()
    conn.execute(
        "INSERT INTO game_sessions (campaign_id, scene_enemies, scene_npcs) VALUES (?, '[]', '[]')",
        (1,),
    )
    conn.commit()

    valid, reason = _validate(conn, 1, "napastnik", source="llm")
    assert valid is True, f"LLM key 'napastnik' must be trusted. Got {valid!r}/{reason!r}"


# ─── Test 2: injected source with unknown key still REJECTED ────────────────

def test_injected_unknown_key_still_rejected():
    """Backward compat: source='injected' with unknown key → (False,'combat_target_unknown')."""
    conn = _make_db()
    conn.execute(
        "INSERT INTO game_sessions (campaign_id, scene_enemies, scene_npcs) VALUES (?, '[]', '[]')",
        (1,),
    )
    conn.commit()

    valid, reason = _validate(conn, 1, "nozownik", source="injected")
    assert valid is False, f"injected+unknown key must be rejected, got valid={valid!r}"
    assert reason == "combat_target_unknown", f"Expected combat_target_unknown, got {reason!r}"


# ─── Test 3: LLM source still REJECTS friendly NPCs (gate must fire first) ──

def test_llm_source_rejects_friendly_npc():
    """#774/#534: even source='llm', a friendly NPC from scene_npcs is still rejected."""
    conn = _make_db()
    scene_npcs = [{"key": "marta_karczmarkarka", "name": "Marta"}]
    conn.execute(
        "INSERT INTO game_sessions (campaign_id, scene_enemies, scene_npcs) VALUES (?, '[]', ?)",
        (1, json.dumps(scene_npcs)),
    )
    conn.commit()

    valid, reason = _validate(conn, 1, "marta_karczmarkarka", source="llm")
    assert valid is False, "LLM-authored tag targeting friendly NPC must be rejected"
    assert reason == "combat_target_friendly_npc", f"Expected combat_target_friendly_npc, got {reason!r}"


def test_llm_source_rejects_campaign_known_npc():
    """#774/#534: LLM source still rejects NPC from campaign_known_npcs."""
    conn = _make_db()
    conn.execute(
        "INSERT INTO game_sessions (campaign_id, scene_enemies, scene_npcs) VALUES (?, '[]', '[]')",
        (1,),
    )
    conn.execute(
        "INSERT INTO campaign_known_npcs (campaign_id, npc_name) VALUES (?, ?)",
        (1, "Marta"),
    )
    conn.commit()

    valid, reason = _validate(conn, 1, "marta", source="llm")
    assert valid is False, "LLM-authored tag targeting known NPC must be rejected"
    assert reason == "combat_target_friendly_npc", f"Got {reason!r}"


# ─── Test 4: scene_enemies still accepted for both sources ──────────────────

def test_llm_source_scene_enemy_accepted():
    """scene_enemies short-circuit fires before source check — both sources pass."""
    conn = _make_db()
    scene = [{"key": "bandit", "name": "Nożownik"}]
    conn.execute(
        "INSERT INTO game_sessions (campaign_id, scene_enemies, scene_npcs) VALUES (?, ?, '[]')",
        (1, json.dumps(scene)),
    )
    conn.commit()

    valid, reason = _validate(conn, 1, "bandit", source="llm")
    assert valid is True, f"scene_enemies 'bandit' must be accepted for llm. Got {valid!r}/{reason!r}"

    valid2, reason2 = _validate(conn, 1, "bandit", source="injected")
    assert valid2 is True, f"scene_enemies 'bandit' must be accepted for injected. Got {valid2!r}/{reason2!r}"
