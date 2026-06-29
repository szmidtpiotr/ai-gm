"""TDD: Issue #1023 — enemy level gating: narrator must not spawn over-leveled enemies."""
import sqlite3
import json
import sys
import pytest

sys.path.insert(0, '/app')

DB_PATH = "/data/ai_gm.db"


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _live_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _mem_enemies(enemies):
    """Minimal in-memory DB with the tables needed for level-gate tests.

    enemies: list of (key, label, tier, min_level)
    """
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE game_config_enemies (
            key TEXT PRIMARY KEY,
            label TEXT NOT NULL,
            tier TEXT NOT NULL DEFAULT 'standard',
            min_level INTEGER NOT NULL DEFAULT 1,
            is_active INTEGER NOT NULL DEFAULT 1
        )
    """)
    conn.execute("""
        CREATE TABLE characters (
            id INTEGER PRIMARY KEY,
            sheet_json TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE game_locations (
            key TEXT PRIMARY KEY,
            enemy_keys TEXT,
            npc_keys TEXT,
            biome TEXT,
            location_subtype TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE location_npc_assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            location_key TEXT,
            npc_key TEXT,
            is_active INTEGER NOT NULL DEFAULT 1
        )
    """)
    conn.execute("""
        CREATE TABLE npcs (
            key TEXT PRIMARY KEY,
            label TEXT,
            npc_type TEXT,
            is_active INTEGER DEFAULT 1
        )
    """)
    conn.execute("""
        CREATE TABLE location_enemy_assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            location_key TEXT,
            enemy_key TEXT,
            is_active INTEGER NOT NULL DEFAULT 1
        )
    """)
    for e in enemies:
        conn.execute(
            "INSERT INTO game_config_enemies (key, label, tier, min_level, is_active) VALUES (?,?,?,?,1)",
            e,
        )
    conn.commit()
    return conn


def _add_char(conn, char_id, level):
    conn.execute(
        "INSERT OR REPLACE INTO characters (id, sheet_json) VALUES (?, ?)",
        (char_id, json.dumps({"level": level})),
    )
    conn.commit()


def _add_location_enemy(conn, loc_key, enemy_key):
    conn.execute(
        "INSERT OR IGNORE INTO game_locations (key, enemy_keys) VALUES (?, '[]')",
        (loc_key,),
    )
    conn.execute(
        "INSERT INTO location_enemy_assignments (location_key, enemy_key, is_active) VALUES (?, ?, 1)",
        (loc_key, enemy_key),
    )
    conn.commit()


# ─── FAZA 1 RED — schema & backfill (fail before migration) ──────────────────

def test_min_level_column_exists():
    """game_config_enemies must have min_level column after #1023 migration."""
    conn = _live_conn()
    try:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(game_config_enemies)").fetchall()]
        assert "min_level" in cols, f"min_level missing. Columns: {cols}"
    finally:
        conn.close()


def test_elite_enemies_backfilled_ge_6():
    """Active elite enemies must have min_level >= 6 after backfill."""
    conn = _live_conn()
    try:
        rows = conn.execute(
            "SELECT key, min_level FROM game_config_enemies WHERE tier='elite' AND is_active=1"
        ).fetchall()
        assert rows, "No active elite enemies"
        bad = [r["key"] for r in rows if r["min_level"] < 6]
        assert not bad, f"Elite enemies with min_level < 6: {bad}"
    finally:
        conn.close()


def test_boss_enemies_backfilled_ge_10():
    """Active boss enemies must have min_level >= 10 after backfill."""
    conn = _live_conn()
    try:
        rows = conn.execute(
            "SELECT key, min_level FROM game_config_enemies WHERE tier='boss' AND is_active=1"
        ).fetchall()
        assert rows, "No active boss enemies"
        bad = [r["key"] for r in rows if r["min_level"] < 10]
        assert not bad, f"Boss enemies with min_level < 10: {bad}"
    finally:
        conn.close()


# ─── Content index filtering ──────────────────────────────────────────────────

def test_content_index_hides_elite_from_low_level_hero():
    """build_available_content_index must NOT show elite (min_level=6) to a level-3 hero."""
    from app.services.world_service import build_available_content_index

    conn = _mem_enemies([
        ("goblin", "Goblin", "weak", 1),
        ("bandit", "Bandyta", "standard", 1),
        ("undead_champion", "Nieumarły Mistrz", "elite", 6),
    ])
    _add_char(conn, 1, level=3)
    for ek in ("goblin", "bandit", "undead_champion"):
        _add_location_enemy(conn, "crypt", ek)

    result = build_available_content_index(conn, "crypt", character_id=1)
    assert "undead_champion" not in result, "Elite must not appear for level-3 hero"
    assert "goblin" in result
    assert "bandit" in result


def test_content_index_shows_elite_to_high_level_hero():
    """build_available_content_index MUST show elite (min_level=6) to a level-8 hero."""
    from app.services.world_service import build_available_content_index

    conn = _mem_enemies([
        ("undead_champion", "Nieumarły Mistrz", "elite", 6),
    ])
    _add_char(conn, 2, level=8)
    _add_location_enemy(conn, "crypt", "undead_champion")

    result = build_available_content_index(conn, "crypt", character_id=2)
    assert "undead_champion" in result, "Elite must appear for level-8 hero"


# ─── _resolve_enemy_key_from_context level filter ────────────────────────────

def _resolve_conn():
    """In-memory DB for _resolve_enemy_key_from_context tests."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE game_sessions (campaign_id INTEGER, session_flags TEXT)
    """)
    conn.execute("""
        CREATE TABLE campaign_turns (id INTEGER, campaign_id INTEGER, assistant_text TEXT)
    """)
    conn.execute("""
        CREATE TABLE game_config_enemies (
            key TEXT PRIMARY KEY,
            label TEXT,
            is_active INTEGER DEFAULT 1,
            min_level INTEGER DEFAULT 1
        )
    """)
    conn.execute("INSERT INTO game_config_enemies VALUES ('undead_champion', 'Nieumarły Mistrz', 1, 6)")
    conn.execute("INSERT INTO game_config_enemies VALUES ('bandit', 'Bandyta', 1, 1)")
    conn.commit()
    return conn


def test_resolve_skips_overlevel_enemy():
    """_resolve_enemy_key_from_context must not match elite (min_level=6) for hero level 3."""
    from app.api.turns import _resolve_enemy_key_from_context

    conn = _resolve_conn()
    result = _resolve_enemy_key_from_context(
        conn, 999, "Nieumarły Mistrz atakuje!", hero_level=3
    )
    assert result != "undead_champion", "Must not resolve over-leveled enemy"


def test_resolve_matches_at_adequate_level():
    """_resolve_enemy_key_from_context must match elite at hero level >= min_level."""
    from app.api.turns import _resolve_enemy_key_from_context

    conn = _resolve_conn()
    result = _resolve_enemy_key_from_context(
        conn, 999, "Nieumarły Mistrz atakuje!", hero_level=6
    )
    assert result == "undead_champion", "Must resolve enemy at adequate level"


# ─── Backward compat — no character_id ──────────────────────────────────────

def test_content_index_no_char_id_shows_all():
    """Without character_id, all active enemies shown (no filtering — backwards compat)."""
    from app.services.world_service import build_available_content_index

    conn = _mem_enemies([
        ("undead_champion", "Nieumarły Mistrz", "elite", 6),
    ])
    _add_location_enemy(conn, "crypt", "undead_champion")

    result = build_available_content_index(conn, "crypt", character_id=None)
    assert "undead_champion" in result, "Must show all enemies when no character_id"
