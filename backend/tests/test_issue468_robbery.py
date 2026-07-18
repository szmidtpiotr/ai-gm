"""TDD: Issue #468 — F8 Napady (robbery encounter): gold steal, config, narrative.

Acceptance:
- get_robbery_config(conn) → {enabled, gold_percent}; default enabled=True, 20%
- apply_robbery(conn, char_id) → deducts floor(gold * pct / 100), returns result
- Gold journal written with source='robbery'
- 0 gold → 0 stolen (no negative)
- Config changeable via set_robbery_config()
- Disabled → ok=False, gold unchanged
- is_robbery_encounter(enc) → True when encounter has encounter_type='robbery'
"""
import sys
sys.path.insert(0, "/app")
from _fixtures_schema import table_sql

import json
import sqlite3
import pytest
from app.services.robbery_service import (
    DEFAULT_ROBBERY_PCT,
    get_robbery_config,
    set_robbery_config,
    apply_robbery,
    is_robbery_encounter,
)


# ─── Fixture ─────────────────────────────────────────────────────────────────

@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE characters (
            id INTEGER PRIMARY KEY,
            gold_gp INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE character_gold_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id INTEGER,
            delta INTEGER,
            source TEXT,
            meta_json TEXT,
            game_clock_day INTEGER DEFAULT 1,
            reverted_at TEXT
        );
        """ + table_sql("game_config_meta") + """

        -- Character with 200 gold
        INSERT INTO characters VALUES (1, 200);
        -- Character with 0 gold
        INSERT INTO characters VALUES (2, 0);
        -- Character with 55 gold (odd number for floor test)
        INSERT INTO characters VALUES (3, 55);
    """)
    conn.commit()
    yield conn
    conn.close()


def _get_gold(db, char_id=1):
    return db.execute("SELECT gold_gp FROM characters WHERE id = ?", (char_id,)).fetchone()["gold_gp"]


# ─── Constants ────────────────────────────────────────────────────────────────

def test_default_robbery_pct():
    """Default robbery percent is 20."""
    assert DEFAULT_ROBBERY_PCT == 20


# ─── get_robbery_config ───────────────────────────────────────────────────────

def test_robbery_enabled_by_default(db):
    """Robbery encounter is enabled by default."""
    cfg = get_robbery_config(db)
    assert cfg["enabled"] is True


def test_robbery_default_percent(db):
    """Default gold_percent is 20."""
    cfg = get_robbery_config(db)
    assert cfg["gold_percent"] == 20


# ─── set_robbery_config ───────────────────────────────────────────────────────

def test_set_robbery_percent(db):
    """Admin can change the robbery percent."""
    set_robbery_config(db, gold_percent=30)
    cfg = get_robbery_config(db)
    assert cfg["gold_percent"] == 30


def test_set_robbery_disabled(db):
    """Admin can disable robbery encounters."""
    set_robbery_config(db, enabled=False)
    cfg = get_robbery_config(db)
    assert cfg["enabled"] is False


def test_set_robbery_config_persists(db):
    """Config survives a read-back cycle."""
    set_robbery_config(db, enabled=True, gold_percent=15)
    cfg = get_robbery_config(db)
    assert cfg["gold_percent"] == 15
    assert cfg["enabled"] is True


# ─── apply_robbery ────────────────────────────────────────────────────────────

def test_apply_robbery_deducts_correct_amount(db):
    """20% of 200 gold = 40 gold stolen."""
    result = apply_robbery(db, 1)
    assert result["ok"] is True
    assert result["gold_stolen"] == 40
    assert _get_gold(db, 1) == 160


def test_apply_robbery_floors_to_int(db):
    """20% of 55 gold = floor(11) = 11 gold stolen."""
    result = apply_robbery(db, 3)
    assert result["ok"] is True
    assert result["gold_stolen"] == 11
    assert _get_gold(db, 3) == 44


def test_apply_robbery_zero_gold(db):
    """Character with 0 gold loses 0 — no negative balance."""
    result = apply_robbery(db, 2)
    assert result["ok"] is True
    assert result["gold_stolen"] == 0
    assert _get_gold(db, 2) == 0


def test_apply_robbery_journals_loss(db):
    """Gold deduction written to character_gold_log with source='robbery'."""
    apply_robbery(db, 1)
    log = db.execute(
        "SELECT delta, source FROM character_gold_log WHERE character_id = 1 ORDER BY id DESC LIMIT 1"
    ).fetchone()
    assert log["delta"] == -40
    assert "robbery" in log["source"]


def test_apply_robbery_disabled(db):
    """When disabled, ok=False, gold unchanged."""
    set_robbery_config(db, enabled=False)
    result = apply_robbery(db, 1)
    assert result["ok"] is False
    assert _get_gold(db, 1) == 200


def test_apply_robbery_custom_percent(db):
    """Custom 50% config steals half the gold."""
    set_robbery_config(db, gold_percent=50)
    result = apply_robbery(db, 1)
    assert result["gold_stolen"] == 100
    assert _get_gold(db, 1) == 100


def test_apply_robbery_returns_narrative_hint(db):
    """Result contains narrative_hint for LLM context."""
    result = apply_robbery(db, 1)
    assert "narrative_hint" in result
    assert len(result["narrative_hint"]) > 10  # non-empty Polish narration


def test_apply_robbery_journals_only_when_gold_stolen(db):
    """No log entry written when gold_stolen = 0."""
    before = db.execute("SELECT COUNT(*) AS c FROM character_gold_log WHERE character_id = 2").fetchone()["c"]
    apply_robbery(db, 2)
    after = db.execute("SELECT COUNT(*) AS c FROM character_gold_log WHERE character_id = 2").fetchone()["c"]
    assert before == after  # no new log when nothing stolen


# ─── is_robbery_encounter ─────────────────────────────────────────────────────

def test_is_robbery_encounter_true(db):
    """Encounter dict with encounter_type='robbery' → True."""
    enc = {"encounter_type": "robbery", "label": "Napad bandytów"}
    assert is_robbery_encounter(enc) is True


def test_is_robbery_encounter_false_for_combat(db):
    """Normal combat encounter → False."""
    enc = {"label": "Atak wilków", "enemies": [{"enemy_key": "wolf"}]}
    assert is_robbery_encounter(enc) is False


def test_is_robbery_encounter_none(db):
    """None → False (safe to call with no encounter active)."""
    assert is_robbery_encounter(None) is False


def test_is_robbery_encounter_empty(db):
    """Empty dict → False."""
    assert is_robbery_encounter({}) is False
