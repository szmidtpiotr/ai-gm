"""TDD: Issue #366 — C12 [SPEND_GOLD:service_key] tag parser + deduction.

Tests for spend_gold_service.py:
- parse_spend_gold_tags(text) → [(service_key, cost_from_db), ...]
- can_afford_service(character, service_key, conn) → bool
- spend_gold_on_service(character_id, service_key, conn) → (success, new_gold)
"""
import sys
sys.path.insert(0, "/app")
from _fixtures_schema import table_sql

import sqlite3
import pytest
from app.services.spend_gold_service import (
    parse_spend_gold_tags,
    can_afford_service,
    spend_gold_on_service,
)

# ─── Test DB fixture ─────────────────────────────────────────────────────────

@pytest.fixture
def test_db():
    """In-memory SQLite with test data."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row

    # Create game_config_services table
    conn.execute("""
        """ + table_sql("game_config_services") + """
    """)

    # Create characters table with minimal fields
    conn.execute("""
        CREATE TABLE characters (
            id INTEGER PRIMARY KEY,
            gold_gp INTEGER NOT NULL DEFAULT 0,
            sheet_json TEXT
        )
    """)

    # Insert test services
    conn.execute("INSERT INTO game_config_services VALUES (?, ?, ?, ?)",
                 ("inn_night", "Inn: one night", 5, 1))
    conn.execute("INSERT INTO game_config_services VALUES (?, ?, ?, ?)",
                 ("healer_light", "Healer: light wounds", 10, 1))
    conn.execute("INSERT INTO game_config_services VALUES (?, ?, ?, ?)",
                 ("healer_heavy", "Healer: heavy wounds", 50, 1))

    # Insert test character with 100 gold
    conn.execute("INSERT INTO characters VALUES (?, ?, ?)",
                 (1, 100, '{}'))

    conn.commit()
    yield conn
    conn.close()


# ─── parse_spend_gold_tags ──────────────────────────────────────────────────

def test_parse_single_spend_gold_tag(test_db):
    """Extract [SPEND_GOLD:inn_night] from narrative."""
    text = "You rest at the inn. [SPEND_GOLD:inn_night]"
    tags = parse_spend_gold_tags(text, test_db)
    assert len(tags) == 1
    assert tags[0] == ("inn_night", 5)


def test_parse_multiple_spend_gold_tags(test_db):
    """Extract multiple [SPEND_GOLD:X] tags."""
    text = "Visit healer [SPEND_GOLD:healer_light] then stay at inn [SPEND_GOLD:inn_night]"
    tags = parse_spend_gold_tags(text, test_db)
    assert len(tags) == 2
    assert tags[0] == ("healer_light", 10)
    assert tags[1] == ("inn_night", 5)


def test_parse_unknown_service_ignored(test_db):
    """Unknown service key → ignored, no crash."""
    text = "Do something [SPEND_GOLD:unknown_service]"
    tags = parse_spend_gold_tags(text, test_db)
    assert len(tags) == 0  # Unknown service skipped


def test_parse_empty_text(test_db):
    """Empty text → empty list."""
    tags = parse_spend_gold_tags("", test_db)
    assert tags == []

    tags = parse_spend_gold_tags(None, test_db)
    assert tags == []


def test_parse_no_tags(test_db):
    """Text without [SPEND_GOLD:*] → empty list."""
    tags = parse_spend_gold_tags("Narrative without tags", test_db)
    assert tags == []


# ─── can_afford_service ─────────────────────────────────────────────────────

def test_can_afford_service_true(test_db):
    """Character with 100 gold can afford 5 gold service."""
    result = can_afford_service(test_db, 1, "inn_night")
    assert result is True


def test_can_afford_service_exact(test_db):
    """Character with exact gold needed can afford."""
    test_db.execute("UPDATE characters SET gold_gp = 10 WHERE id = 1")
    test_db.commit()
    result = can_afford_service(test_db, 1, "healer_light")
    assert result is True


def test_cannot_afford_service_insufficient(test_db):
    """Character with 3 gold cannot afford 5 gold service."""
    test_db.execute("UPDATE characters SET gold_gp = 3 WHERE id = 1")
    test_db.commit()
    result = can_afford_service(test_db, 1, "inn_night")
    assert result is False


def test_cannot_afford_unknown_service(test_db):
    """Unknown service → False (cannot afford)."""
    result = can_afford_service(test_db, 1, "nonexistent_service")
    assert result is False


# ─── spend_gold_on_service ──────────────────────────────────────────────────

def test_spend_gold_success(test_db):
    """Spend 5 gold from 100: new_gold = 95."""
    success, new_gold = spend_gold_on_service(test_db, 1, "inn_night")
    assert success is True
    assert new_gold == 95

    # Verify DB persisted
    row = test_db.execute("SELECT gold_gp FROM characters WHERE id = 1").fetchone()
    assert row["gold_gp"] == 95


def test_spend_gold_exact(test_db):
    """Spend exactly all gold: new_gold = 0."""
    test_db.execute("UPDATE characters SET gold_gp = 5 WHERE id = 1")
    test_db.commit()
    success, new_gold = spend_gold_on_service(test_db, 1, "inn_night")
    assert success is True
    assert new_gold == 0


def test_spend_gold_insufficient_fails(test_db):
    """Insufficient gold: success=False, gold unchanged."""
    test_db.execute("UPDATE characters SET gold_gp = 3 WHERE id = 1")
    test_db.commit()
    success, new_gold = spend_gold_on_service(test_db, 1, "inn_night")
    assert success is False
    assert new_gold is None

    # Verify DB unchanged
    row = test_db.execute("SELECT gold_gp FROM characters WHERE id = 1").fetchone()
    assert row["gold_gp"] == 3


def test_spend_gold_unknown_service_fails(test_db):
    """Unknown service: success=False."""
    success, new_gold = spend_gold_on_service(test_db, 1, "nonexistent")
    assert success is False
    assert new_gold is None


# ─── Backward compat ─────────────────────────────────────────────────────────

def test_no_spend_gold_tags_no_crash(test_db):
    """Text without tags processes fine."""
    tags = parse_spend_gold_tags("Just narration", test_db)
    assert tags == []
