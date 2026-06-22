"""TDD: Issue #477 — F17 Hidden Trait system.

Hidden traits are character-specific passive abilities from a predefined pool.
Each trait has:
  - A key (unique), label, description
  - trigger_keywords (comma-separated, for LLM context injection)
  - effect_json (F1-style Effect Object applied passively)
  - is_active flag (inactive traits excluded from pool)

A character can hold exactly one hidden_trait (stored in sheet_json.hidden_trait).
LLM can trigger reveal via tag [HIDDEN_TRAIT_REVEAL:key] — backend records the reveal.
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from _fixtures_schema import table_sql

import json
import sqlite3
import pytest

from app.services.hidden_trait_service import (
    get_trait_pool,
    assign_trait,
    get_character_trait,
    reveal_trait,
    is_trait_revealed,
)


# ─── In-memory DB fixture ────────────────────────────────────────────────────

@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        """ + table_sql("game_config_hidden_traits") + """
        INSERT INTO game_config_hidden_traits (key, label, description, trigger_keywords, effect_json, is_active)
        VALUES
          ('berserker_rage', 'Szał Berserkera',
           'Gdy zdrowie spada poniżej 30%, ataki zadają +2 obrażeń.',
           'berserk,rage,wściekłość',
           '{"type":"damage_bonus","bonus":2,"condition":"hp_below_30pct"}',
           1),
          ('shadow_step', 'Krok Cienia',
           'Raz na walkę możesz teleportować się za wroga.',
           'shadow,cień,teleport',
           '{"type":"apply_condition","condition":"hidden","duration":1}',
           1),
          ('dead_trait', 'Nieaktywna Cecha', 'Do not include in pool', '', '{}', 0);

        CREATE TABLE characters (
            id INTEGER PRIMARY KEY,
            name TEXT,
            sheet_json TEXT DEFAULT '{}'
        );
        INSERT INTO characters (id, name, sheet_json)
        VALUES
          (1, 'Kowal Jan', '{"hp_current": 10, "hp_max": 10}'),
          (2, 'Marta Wicher', '{}');
    """)
    conn.commit()
    return conn


# ─── Pool ─────────────────────────────────────────────────────────────────────

def test_get_trait_pool_returns_active_only(db):
    """Pool must only include is_active=1 traits."""
    pool = get_trait_pool(db)
    keys = [t["key"] for t in pool]
    assert "berserker_rage" in keys
    assert "shadow_step" in keys
    assert "dead_trait" not in keys, "Inactive trait leaked into pool"


def test_get_trait_pool_has_effect_json(db):
    """Each trait in pool must have parseable effect_json."""
    pool = get_trait_pool(db)
    for t in pool:
        effect = json.loads(t["effect_json"])
        assert "type" in effect, f"Trait {t['key']} missing effect type"


def test_pool_empty_when_all_inactive(db):
    """Pool returns empty list when no active traits."""
    db.execute("UPDATE game_config_hidden_traits SET is_active = 0")
    db.commit()
    assert get_trait_pool(db) == []


# ─── Assign ──────────────────────────────────────────────────────────────────

def test_assign_trait_stores_in_sheet(db):
    """assign_trait writes trait key into sheet_json.hidden_trait."""
    assign_trait(db, character_id=1, trait_key="berserker_rage")
    row = db.execute("SELECT sheet_json FROM characters WHERE id = 1").fetchone()
    sheet = json.loads(row["sheet_json"])
    assert sheet.get("hidden_trait") == "berserker_rage"


def test_assign_trait_overwrites_previous(db):
    """Assigning a second trait replaces the first (one trait per character)."""
    assign_trait(db, character_id=1, trait_key="berserker_rage")
    assign_trait(db, character_id=1, trait_key="shadow_step")
    row = db.execute("SELECT sheet_json FROM characters WHERE id = 1").fetchone()
    sheet = json.loads(row["sheet_json"])
    assert sheet.get("hidden_trait") == "shadow_step"
    # Only one trait stored
    assert "berserker_rage" not in json.dumps(sheet)


def test_assign_unknown_trait_raises(db):
    """Assigning a non-existent trait key raises ValueError."""
    with pytest.raises((ValueError, Exception)):
        assign_trait(db, character_id=1, trait_key="nonexistent_trait")


# ─── Get ─────────────────────────────────────────────────────────────────────

def test_get_character_trait_returns_key(db):
    """get_character_trait returns the trait key assigned to character."""
    assign_trait(db, character_id=1, trait_key="berserker_rage")
    key = get_character_trait(db, character_id=1)
    assert key == "berserker_rage"


def test_character_starts_without_trait(db):
    """Character with no assigned trait returns None."""
    key = get_character_trait(db, character_id=2)
    assert key is None


# ─── Reveal ──────────────────────────────────────────────────────────────────

def test_reveal_trait_marks_revealed(db):
    """After reveal_trait(), is_trait_revealed() returns True."""
    assign_trait(db, character_id=1, trait_key="berserker_rage")
    assert not is_trait_revealed(db, character_id=1), "Trait already revealed before reveal call"
    reveal_trait(db, character_id=1)
    assert is_trait_revealed(db, character_id=1)


def test_reveal_stores_in_sheet(db):
    """reveal_trait sets sheet_json.hidden_trait_revealed = True."""
    assign_trait(db, character_id=1, trait_key="berserker_rage")
    reveal_trait(db, character_id=1)
    row = db.execute("SELECT sheet_json FROM characters WHERE id = 1").fetchone()
    sheet = json.loads(row["sheet_json"])
    assert sheet.get("hidden_trait_revealed") is True


def test_reveal_without_trait_is_noop(db):
    """reveal_trait on character with no trait does nothing (no exception)."""
    reveal_trait(db, character_id=2)  # should not raise
    assert not is_trait_revealed(db, character_id=2)


# ─── Backward compat ─────────────────────────────────────────────────────────

def test_existing_sheet_json_preserved_on_assign(db):
    """assign_trait must not erase existing sheet_json fields."""
    assign_trait(db, character_id=1, trait_key="berserker_rage")
    row = db.execute("SELECT sheet_json FROM characters WHERE id = 1").fetchone()
    sheet = json.loads(row["sheet_json"])
    assert sheet.get("hp_current") == 10, "Existing sheet fields erased by assign_trait"
    assert sheet.get("hp_max") == 10
