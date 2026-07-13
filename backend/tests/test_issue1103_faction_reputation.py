"""TDD: Issue #1103 — reputacja per-frakcja (gildie/rody/zakony) jako rozszerzenie #1099."""
import json
import sqlite3
import sys
import os

sys.path.insert(0, "/app")
from _fixtures_schema import table_sql

import pytest

# ─── Helpers ────────────────────────────────────────────────────────────────

def _scratch_conn():
    """In-memory SQLite with full schema for unit tests."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row

    # character_reputation (from #1099)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS character_reputation (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id INTEGER NOT NULL,
            scope_type TEXT NOT NULL DEFAULT 'region',
            scope_key TEXT NOT NULL,
            value INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(character_id, scope_type, scope_key)
        )
    """)

    # game_config_factions — new table for #1103
    conn.execute("""
        """ + table_sql("game_config_factions") + """
    """)

    # npcs with faction_key column
    conn.execute("""
        CREATE TABLE IF NOT EXISTS npcs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT NOT NULL UNIQUE,
            label TEXT NOT NULL,
            npc_type TEXT NOT NULL DEFAULT 'neutral',
            faction_key TEXT REFERENCES game_config_factions(key),
            is_active INTEGER NOT NULL DEFAULT 1
        )
    """)

    # characters (for shop tests)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS characters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            campaign_id INTEGER
        )
    """)

    conn.commit()
    return conn


def _seed_faction(conn, key="gildia_kupcow", name="Gildia Kupców", ftype="guild"):
    conn.execute(
        "INSERT OR IGNORE INTO game_config_factions (key, name, faction_type) VALUES (?,?,?)",
        (key, name, ftype),
    )
    conn.commit()


def _seed_npc(conn, key="handlarz_jan", label="Jan Handlarz", faction_key=None):
    conn.execute(
        "INSERT OR IGNORE INTO npcs (key, label, faction_key) VALUES (?,?,?)",
        (key, label, faction_key),
    )
    conn.commit()


# ─── Test 1: game_config_factions table exists with correct columns ──────────

def test_faction_table_columns():
    """game_config_factions must have key/name/faction_type/description/is_active."""
    from app.services import reputation_service as rep
    conn = _scratch_conn()

    # table exists + seed works
    _seed_faction(conn, key="zakon_straznikow", name="Zakon Strażników", ftype="order")

    row = conn.execute(
        "SELECT key, name, faction_type, is_active FROM game_config_factions WHERE key = ?",
        ("zakon_straznikow",),
    ).fetchone()
    assert row is not None, "game_config_factions row not found"
    assert row["key"] == "zakon_straznikow"
    assert row["faction_type"] == "order"
    assert row["is_active"] == 1


# ─── Test 2: npcs.faction_key column exists ──────────────────────────────────

def test_npc_faction_key_column():
    """npcs must have faction_key column referencing game_config_factions."""
    conn = _scratch_conn()
    _seed_faction(conn, key="gildia_kupcow")
    _seed_npc(conn, key="kupiec_adam", label="Adam Kupiec", faction_key="gildia_kupcow")

    row = conn.execute(
        "SELECT faction_key FROM npcs WHERE key = ?", ("kupiec_adam",)
    ).fetchone()
    assert row is not None
    assert row["faction_key"] == "gildia_kupcow"


def test_npc_without_faction_is_nullable():
    """npcs.faction_key nullable — NPC without faction must still insert fine."""
    conn = _scratch_conn()
    _seed_npc(conn, key="wolny_npc", label="Wolny NPC", faction_key=None)
    row = conn.execute("SELECT faction_key FROM npcs WHERE key = ?", ("wolny_npc",)).fetchone()
    assert row is not None
    assert row["faction_key"] is None


# ─── Test 3: faction reputation CRUD ─────────────────────────────────────────

def test_faction_reputation_set_and_get():
    """adjust_reputation + get_reputation work for scope_type='faction'."""
    from app.services import reputation_service as rep
    conn = _scratch_conn()

    rep.ensure_reputation_table(conn)
    new_val = rep.adjust_reputation(conn, 1, "gildia_kupcow", 30, scope_type="faction")
    assert new_val == 30

    fetched = rep.get_reputation(conn, 1, "gildia_kupcow", scope_type="faction")
    assert fetched == 30


def test_faction_reputation_independent_of_region():
    """faction rep and region rep for same character are independent rows."""
    from app.services import reputation_service as rep
    conn = _scratch_conn()
    rep.ensure_reputation_table(conn)

    rep.adjust_reputation(conn, 1, "kresy", 10, scope_type="region")
    rep.adjust_reputation(conn, 1, "gildia_kupcow", 40, scope_type="faction")

    region_val = rep.get_reputation(conn, 1, "kresy", scope_type="region")
    faction_val = rep.get_reputation(conn, 1, "gildia_kupcow", scope_type="faction")

    assert region_val == 10
    assert faction_val == 40


def test_get_all_reputation_returns_faction_rows():
    """get_all_reputation must include faction-scope rows alongside region rows."""
    from app.services import reputation_service as rep
    conn = _scratch_conn()
    rep.ensure_reputation_table(conn)

    rep.adjust_reputation(conn, 5, "kresy", 15, scope_type="region")
    rep.adjust_reputation(conn, 5, "gildia_kupcow", 35, scope_type="faction")
    rep.adjust_reputation(conn, 5, "wolni_najemnicy", -10, scope_type="faction")

    all_rep = rep.get_all_reputation(conn, 5)
    scope_types = {r["scope_type"] for r in all_rep}
    assert "region" in scope_types
    assert "faction" in scope_types

    faction_rows = [r for r in all_rep if r["scope_type"] == "faction"]
    assert len(faction_rows) == 2
    guild_row = next(r for r in faction_rows if r["scope_key"] == "gildia_kupcow")
    assert guild_row["value"] == 35
    assert guild_row["tier"] == "friendly"


# ─── Test 4: faction shop multiplier applies when NPC has faction ─────────────

def test_faction_shop_multiplier_function_exists():
    """reputation_service must expose get_faction_shop_multiplier(conn, char_id, faction_key)."""
    from app.services import reputation_service as rep
    conn = _scratch_conn()
    rep.ensure_reputation_table(conn)

    # no faction rep yet → neutral → 1.0
    mult = rep.get_faction_shop_multiplier(conn, 1, "gildia_kupcow")
    assert mult == 1.0

    # build positive faction rep → discount
    rep.adjust_reputation(conn, 1, "gildia_kupcow", 50, scope_type="faction")
    mult_pos = rep.get_faction_shop_multiplier(conn, 1, "gildia_kupcow")
    assert mult_pos < 1.0, "positive faction rep should give discount"

    # build negative faction rep → surcharge
    rep.adjust_reputation(conn, 2, "gildia_kupcow", -50, scope_type="faction")
    mult_neg = rep.get_faction_shop_multiplier(conn, 2, "gildia_kupcow")
    assert mult_neg > 1.0, "negative faction rep should give surcharge"


def test_combined_buy_multiplier_uses_best_price():
    """combined_buy_multiplier picks the better deal of region or faction rep."""
    from app.services import reputation_service as rep
    conn = _scratch_conn()
    rep.ensure_reputation_table(conn)

    # region neutral (1.0), faction positive (discount) → should use faction discount
    rep.adjust_reputation(conn, 10, "gildia_kupcow", 50, scope_type="faction")
    combined = rep.combined_buy_multiplier(conn, 10, "kresy", "gildia_kupcow")
    assert combined < 1.0

    # region positive (discount), faction negative (surcharge) → should use region discount
    rep.adjust_reputation(conn, 11, "kresy", 50, scope_type="region")
    rep.adjust_reputation(conn, 11, "gildia_kupcow", -50, scope_type="faction")
    combined2 = rep.combined_buy_multiplier(conn, 11, "kresy", "gildia_kupcow")
    assert combined2 < 1.0, "should use region discount, not faction surcharge"


# ─── Test 5: faction context line for narrator ───────────────────────────────

def test_faction_context_line_non_neutral():
    """faction_context_line returns non-empty string when standing is non-neutral."""
    from app.services import reputation_service as rep

    line = rep.faction_context_line(40, "Gildia Kupców")
    assert line != "", "should produce context when non-neutral"
    assert "Gildia Kupców" in line or "frakcj" in line.lower() or "gildi" in line.lower()


def test_faction_context_line_neutral_is_empty():
    """faction_context_line returns empty string when standing is neutral (no noise)."""
    from app.services import reputation_service as rep
    line = rep.faction_context_line(0, "Gildia Kupców")
    assert line == "", "neutral faction standing should produce no context line"


# ─── Test 6: backward compatibility — existing region behavior unchanged ──────

def test_region_reputation_still_works():
    """All existing region reputation functions unchanged by #1103."""
    from app.services import reputation_service as rep
    conn = _scratch_conn()
    rep.ensure_reputation_table(conn)

    rep.adjust_reputation(conn, 99, "kresy", 25, scope_type="region")
    val = rep.get_reputation(conn, 99, "kresy", scope_type="region")
    assert val == 25

    assert rep.reputation_tier(25) == "friendly"
    assert rep.shop_price_multiplier(25) < 1.0
    assert rep.npc_attitude_from_reputation(25) == "friendly"
    assert rep.reputation_context_line(25, "kresy") != ""
