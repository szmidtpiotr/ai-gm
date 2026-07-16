"""TDD #1068 — FAZA G: kara XP przy wipe party w walce MP.

Do tej pory `_apply_mp_wipe` odbierał TYLKO złoto (G17 #794 / G15 #813) —
XP/poziomy były nietknięte. #1068 dodaje karę XP jako realną konsekwencję
porażki drużyny: przy wipe każdy gracz traci % swojego dostępnego XP
(`xp_available`), skalowane wg średniego poziomu party (mirror kary złota).
Historia awansów (`xp_lifetime_earned`) i poziom NIE są ruszane.
"""
import json
import os
import sqlite3
import sys
from unittest.mock import patch

sys.path.insert(0, "/app")
from _fixtures_schema import table_sql
os.environ.setdefault("AIGM_E2E_LITE", "1")

import pytest

from app.services import admin_config
from app.services import combat_service as cs


# ── Schema (mirror #794, + xp_available/xp_lifetime_earned na kartach) ─────────

def _schema_sql() -> str:
    return """
    CREATE TABLE IF NOT EXISTS users (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      username TEXT NOT NULL UNIQUE,
      password_hash TEXT NOT NULL DEFAULT '',
      display_name TEXT NOT NULL DEFAULT ''
    );
    INSERT INTO users (id, username, password_hash, display_name)
    VALUES (1, 'alice', 'x', 'Alice'), (2, 'bob', 'x', 'Bob');

    CREATE TABLE IF NOT EXISTS campaigns (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      title TEXT NOT NULL DEFAULT 'Test',
      system_id TEXT NOT NULL DEFAULT 'fantasy',
      model_id TEXT NOT NULL DEFAULT 'm',
      owner_user_id INTEGER NOT NULL DEFAULT 1,
      mode TEXT NOT NULL DEFAULT 'multiplayer',
      status TEXT NOT NULL DEFAULT 'active',
      host_user_id INTEGER,
      round_timer_minutes INTEGER NOT NULL DEFAULT 1440,
      max_players INTEGER NOT NULL DEFAULT 4
    );
    INSERT INTO campaigns (id, title, owner_user_id, mode, host_user_id)
    VALUES (1, 'MP Camp', 1, 'multiplayer', 1);

    CREATE TABLE IF NOT EXISTS campaign_members (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      campaign_id INTEGER NOT NULL,
      user_id INTEGER NOT NULL,
      role TEXT NOT NULL DEFAULT 'player',
      status TEXT NOT NULL DEFAULT 'accepted',
      character_id INTEGER,
      absence_warnings INTEGER NOT NULL DEFAULT 0,
      UNIQUE(campaign_id, user_id)
    );

    CREATE TABLE IF NOT EXISTS characters (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      campaign_id INTEGER,
      user_id INTEGER NOT NULL DEFAULT 1,
      name TEXT NOT NULL,
      system_id TEXT NOT NULL DEFAULT 'fantasy',
      sheet_json TEXT NOT NULL DEFAULT '{}',
      status TEXT NOT NULL DEFAULT 'active',
      gold_gp INTEGER NOT NULL DEFAULT 0
    );
    -- Player 1: lvl5, 1000 xp_available, 4000 lifetime, 100 gold
    INSERT INTO characters (id, campaign_id, user_id, name, system_id, sheet_json, gold_gp)
    VALUES
      (1, 1, 1, 'Aldric', 'fantasy',
       '{"archetype":"warrior","level":5,"xp_available":1000,"xp_lifetime_earned":4000,"stats":{"STR":14,"DEX":12,"CON":12,"INT":10,"WIS":10,"CHA":10,"LCK":10},"current_hp":20,"max_hp":20,"defense":{"base":15},"equipped_weapon":"sword"}',
       100),
    -- Player 2: lvl5, 500 xp_available, 30 gold (below gold floor, above xp floor)
      (2, 1, 2, 'Mira', 'fantasy',
       '{"archetype":"warrior","level":5,"xp_available":500,"xp_lifetime_earned":3000,"stats":{"STR":12,"DEX":16,"CON":10,"INT":10,"WIS":10,"CHA":10,"LCK":10},"current_hp":18,"max_hp":18,"defense":{"base":13},"equipped_weapon":"sword"}',
       30);

    INSERT INTO campaign_members (campaign_id, user_id, status, character_id)
    VALUES (1, 1, 'accepted', 1), (1, 2, 'accepted', 2);

    CREATE TABLE IF NOT EXISTS character_campaign_state (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      character_id INTEGER NOT NULL,
      campaign_id INTEGER NOT NULL,
      current_hp INTEGER NOT NULL DEFAULT 0,
      max_hp INTEGER NOT NULL DEFAULT 0,
      current_mana INTEGER NOT NULL DEFAULT 0,
      max_mana INTEGER NOT NULL DEFAULT 0,
      conditions_json TEXT NOT NULL DEFAULT '[]',
      position_json TEXT,
      updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      UNIQUE(character_id, campaign_id)
    );
    INSERT INTO character_campaign_state (character_id, campaign_id, current_hp, max_hp)
    VALUES (1, 1, 20, 20), (2, 1, 18, 18);

    """ + table_sql("game_config_weapons") + """
    INSERT INTO game_config_weapons (key, label, damage_die, linked_stat, allowed_classes)
    VALUES ('sword', 'Miecz', '1d8', 'STR', 'warrior');

    """ + table_sql("game_config_enemies") + """
    INSERT INTO game_config_enemies (key, label, hp_base, ac_base, attack_bonus, dex_modifier, damage_die, image_url)
    VALUES ('goblin', 'Goblin', 8, 12, 2, 1, '1d6', NULL);

    CREATE TABLE IF NOT EXISTS active_combat (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      campaign_id INTEGER NOT NULL UNIQUE,
      character_id INTEGER NOT NULL,
      round INTEGER NOT NULL DEFAULT 1,
      turn_order TEXT NOT NULL DEFAULT '[]',
      current_turn TEXT NOT NULL DEFAULT 'player',
      combatants TEXT NOT NULL DEFAULT '[]',
      status TEXT NOT NULL DEFAULT 'active',
      ended_reason TEXT,
      location_tag TEXT,
      loot_pool TEXT,
      loot_persisted INTEGER NOT NULL DEFAULT 0,
      post_combat_loot_json TEXT,
      boss_defeated INTEGER NOT NULL DEFAULT 0,
      created_at TEXT NOT NULL DEFAULT (datetime('now')),
      updated_at TEXT NOT NULL DEFAULT (datetime('now')),
      combat_turn_deadline TEXT
    );

    CREATE TABLE IF NOT EXISTS combat_turns (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      combat_id INTEGER NOT NULL,
      campaign_id INTEGER NOT NULL,
      turn_number REAL NOT NULL,
      actor TEXT NOT NULL,
      event_type TEXT NOT NULL,
      roll_value INTEGER,
      damage INTEGER,
      hp_after INTEGER,
      target_id TEXT,
      target_name TEXT,
      hit INTEGER,
      narrative TEXT,
      created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    """ + table_sql("game_config_conditions") + """

    """ + table_sql("game_config_skills") + """

    CREATE TABLE IF NOT EXISTS character_inventory (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      character_id INTEGER NOT NULL,
      item_key TEXT,
      weapon_key TEXT,
      consumable_key TEXT,
      quantity INTEGER NOT NULL DEFAULT 1,
      equipped INTEGER NOT NULL DEFAULT 0
    );

    """ + table_sql("game_config_spells") + """

    CREATE TABLE IF NOT EXISTS campaign_turns (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      campaign_id INTEGER NOT NULL,
      character_id INTEGER NOT NULL,
      user_text TEXT NOT NULL DEFAULT '',
      route TEXT NOT NULL DEFAULT 'combat',
      assistant_text TEXT,
      turn_number INTEGER NOT NULL DEFAULT 1,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS game_sessions (
      id TEXT PRIMARY KEY,
      campaign_id INTEGER NOT NULL,
      session_flags TEXT DEFAULT '{}',
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS game_events (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      event_type TEXT NOT NULL,
      campaign_id INTEGER,
      character_id INTEGER,
      user_id INTEGER,
      payload TEXT DEFAULT '{}',
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS dice_rolls (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      campaign_id INTEGER,
      character_id INTEGER,
      combat_id INTEGER,
      roll_type TEXT NOT NULL,
      actor TEXT,
      notation TEXT,
      raw_rolls TEXT,
      modifiers TEXT DEFAULT '{}',
      total INTEGER,
      dc INTEGER,
      outcome TEXT,
      meta TEXT DEFAULT '{}',
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS state_changes (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      campaign_id INTEGER,
      character_id INTEGER,
      combat_id INTEGER,
      resource TEXT NOT NULL,
      before_val INTEGER,
      after_val INTEGER,
      cause TEXT,
      meta TEXT DEFAULT '{}',
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS character_gold_log (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      character_id INTEGER NOT NULL,
      delta INTEGER NOT NULL,
      reason TEXT,
      campaign_id INTEGER,
      game_clock_day INTEGER NOT NULL DEFAULT 1,
      wall_clock_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS character_spells (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      character_id INTEGER NOT NULL,
      spell_key TEXT NOT NULL,
      rank INTEGER NOT NULL DEFAULT 1,
      UNIQUE(character_id, spell_key)
    );
    """


@pytest.fixture
def db(tmp_path):
    dbfile = str(tmp_path / "test_1068.db")
    conn = sqlite3.connect(dbfile)
    conn.row_factory = sqlite3.Row
    conn.executescript(_schema_sql())
    conn.close()
    return dbfile


def _conn(db: str) -> sqlite3.Connection:
    c = sqlite3.connect(db)
    c.row_factory = sqlite3.Row
    return c


def _xp(db: str, char_id: int) -> tuple[int, int]:
    """Return (xp_available, xp_lifetime_earned) from a character sheet."""
    conn = _conn(db)
    row = conn.execute("SELECT sheet_json FROM characters WHERE id=?", (char_id,)).fetchone()
    conn.close()
    sheet = json.loads(row["sheet_json"] or "{}")
    return int(sheet.get("xp_available") or 0), int(sheet.get("xp_lifetime_earned") or 0)


def _wipe_party(db: str, campaign_id: int = 1) -> None:
    """Initiate MP combat, knock BOTH players (goblin alive), advance_turn → wipe."""
    cs.initiate_combat_mp(campaign_id=campaign_id, character_ids=[1, 2], enemy_keys=["goblin"])
    conn = _conn(db)
    row = conn.execute(
        "SELECT combatants FROM active_combat WHERE campaign_id=?", (campaign_id,)
    ).fetchone()
    combatants = json.loads(row["combatants"])
    for c in combatants:
        if c.get("type") == "player":
            c["hp_current"] = 0
            c["knocked"] = True
    conn.execute(
        "UPDATE active_combat SET combatants=? WHERE campaign_id=?",
        (json.dumps(combatants), campaign_id),
    )
    conn.commit()
    conn.close()
    cs.advance_turn(campaign_id)


# ── mp_balance: nowa flaga + helper (unit, bez DB) ────────────────────────────

def test_wipe_xp_pct_flag_exists():
    from app.services import mp_balance as mb
    assert hasattr(mb, "WIPE_XP_PCT_BY_LEVEL"), "WIPE_XP_PCT_BY_LEVEL missing"
    d = mb.WIPE_XP_PCT_BY_LEVEL
    assert isinstance(d, dict)
    assert "1-3" in d and "4-7" in d and "8+" in d, "must have all three level brackets"


def test_wipe_xp_floor_exists():
    from app.services import mp_balance as mb
    assert hasattr(mb, "WIPE_XP_FLOOR"), "WIPE_XP_FLOOR missing"
    assert isinstance(mb.WIPE_XP_FLOOR, int)


def test_get_wipe_xp_pct_brackets():
    from app.services.mp_balance import get_wipe_xp_pct
    assert get_wipe_xp_pct(2) == get_wipe_xp_pct(3)   # same 1-3 bracket
    assert get_wipe_xp_pct(5) == get_wipe_xp_pct(7)   # same 4-7 bracket
    # level 4-7 must be 20% per issue #1068 ("uprość do flat 20%")
    assert get_wipe_xp_pct(5) == 0.20, "avg level 5 → 20% XP penalty"


def test_get_wipe_xp_pct_reads_flag(monkeypatch):
    from app.services import mp_balance as mb
    monkeypatch.setitem(mb.WIPE_XP_PCT_BY_LEVEL, "4-7", 0.15)
    assert mb.get_wipe_xp_pct(5) == 0.15, "helper must read from the flag (sandbox-tunable)"


# ── Integracja: wipe odejmuje XP z xp_available ───────────────────────────────

def test_wipe_deducts_xp_from_available(db):
    """#1068: wipe → gracz traci % xp_available wg średniego poziomu (lvl5 → 20%)."""
    with patch.object(cs, "COMBAT_DB_PATH", db), \
         patch.object(admin_config, "DB_PATH", db):
        _wipe_party(db)

    xp1, _ = _xp(db, 1)
    xp2, _ = _xp(db, 2)
    # Player 1: 1000 → -20% (200) → 800
    assert xp1 == 800, f"Player 1 (1000 xp, lvl5) should lose 20% → 800, got {xp1}"
    # Player 2: 500 → -20% (100) → 400
    assert xp2 == 400, f"Player 2 (500 xp, lvl5) should lose 20% → 400, got {xp2}"


def test_wipe_does_not_touch_lifetime_xp(db):
    """#1068: kara XP zdejmuje TYLKO xp_available — historia awansów (lifetime) nietknięta."""
    with patch.object(cs, "COMBAT_DB_PATH", db), \
         patch.object(admin_config, "DB_PATH", db):
        _wipe_party(db)

    _, life1 = _xp(db, 1)
    _, life2 = _xp(db, 2)
    assert life1 == 4000, f"Player 1 lifetime XP must be unchanged (4000), got {life1}"
    assert life2 == 3000, f"Player 2 lifetime XP must be unchanged (3000), got {life2}"


def test_wipe_xp_floor_exempts_low_xp_player(db, monkeypatch):
    """#1068: gracz z xp_available < WIPE_XP_FLOOR jest zwolniony z kary XP."""
    from app.services import mp_balance as mb
    # Raise floor above player 2's 500 xp so only player 1 is penalised
    monkeypatch.setattr(mb, "WIPE_XP_FLOOR", 600)

    with patch.object(cs, "COMBAT_DB_PATH", db), \
         patch.object(admin_config, "DB_PATH", db):
        _wipe_party(db)

    xp1, _ = _xp(db, 1)
    xp2, _ = _xp(db, 2)
    assert xp1 == 800, f"Player 1 (1000 xp ≥ floor 600) should still lose 20% → 800, got {xp1}"
    assert xp2 == 500, f"Player 2 (500 xp < floor 600) should be exempt → 500, got {xp2}"


# ── Backward compat: kara złota nadal działa obok kary XP ─────────────────────

def test_wipe_still_applies_gold_penalty(db):
    """#1068: dodanie kary XP nie psuje istniejącej kary złota (G17/#794)."""
    with patch.object(cs, "COMBAT_DB_PATH", db), \
         patch.object(admin_config, "DB_PATH", db):
        _wipe_party(db)

    conn = _conn(db)
    gold1 = conn.execute("SELECT gold_gp FROM characters WHERE id=1").fetchone()["gold_gp"]
    gold2 = conn.execute("SELECT gold_gp FROM characters WHERE id=2").fetchone()["gold_gp"]
    conn.close()
    assert gold1 == 80, f"Player 1 (100gp, lvl5) still loses 20% gold → 80, got {gold1}"
    assert gold2 == 30, f"Player 2 (<50gp) still exempt from gold penalty → 30, got {gold2}"


def test_wipe_still_ends_combat_and_revives(db):
    """#1068: wipe nadal kończy walkę 'wipe' i budzi graczy z 50% HP (bez regresji)."""
    with patch.object(cs, "COMBAT_DB_PATH", db), \
         patch.object(admin_config, "DB_PATH", db):
        _wipe_party(db)

    conn = _conn(db)
    row = conn.execute(
        "SELECT status, ended_reason, combatants FROM active_combat WHERE campaign_id=1"
    ).fetchone()
    conn.close()
    assert row["status"] == "ended"
    assert row["ended_reason"] == "wipe"
    combatants = json.loads(row["combatants"] or "[]")
    p1 = next((c for c in combatants if c.get("id") == "player:1"), None)
    assert p1 and p1["hp_current"] == 10, f"player:1 should wake at 50% of 20 HP → 10, got {p1}"
