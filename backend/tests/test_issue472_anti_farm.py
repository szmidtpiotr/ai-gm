"""TDD: Issue #472 — Anti-farm sell price decay for repeated item sales."""
import sqlite3
import sys
import os
import json
import math

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from app.services.anti_farm_service import (
    get_anti_farm_multiplier,
    apply_anti_farm,
    ANTI_FARM_LIMIT,
    ANTI_FARM_MIN_RATIO,
    DECAY_PER_EXTRA,
)


# ─── Fixtures ────────────────────────────────────────────────────────────────

def _make_db(sell_count: int = 0, item_key: str = "sword_rusty") -> sqlite3.Connection:
    """Create in-memory DB with N recent sells of item_key."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE character_gold_log (
            id INTEGER PRIMARY KEY,
            character_id INTEGER NOT NULL,
            delta INTEGER NOT NULL,
            source TEXT NOT NULL DEFAULT 'unknown',
            meta_json TEXT,
            game_clock_day INTEGER,
            wall_clock_at TEXT NOT NULL DEFAULT (datetime('now')),
            reverted_at TEXT
        );
    """)
    for _ in range(sell_count):
        conn.execute(
            """INSERT INTO character_gold_log (character_id, delta, source, meta_json, wall_clock_at)
               VALUES (1, -20, 'shop_sell', ?, datetime('now'))""",
            (json.dumps({"item_key": item_key}),),
        )
    conn.commit()
    return conn


# ─── get_anti_farm_multiplier ─────────────────────────────────────────────────

def test_multiplier_is_1_when_no_previous_sells():
    conn = _make_db(0)
    assert get_anti_farm_multiplier(conn, 1, "sword_rusty") == 1.0


def test_multiplier_is_1_under_limit():
    conn = _make_db(ANTI_FARM_LIMIT - 1)
    assert get_anti_farm_multiplier(conn, 1, "sword_rusty") == 1.0


def test_multiplier_is_1_at_exact_limit():
    """Exactly at the limit — the NEXT sale would be the first to decay."""
    conn = _make_db(ANTI_FARM_LIMIT - 1)
    assert get_anti_farm_multiplier(conn, 1, "sword_rusty") == 1.0


def test_multiplier_decays_on_first_over_limit():
    """One over limit (= LIMIT sales) → first decay step."""
    conn = _make_db(ANTI_FARM_LIMIT)
    m = get_anti_farm_multiplier(conn, 1, "sword_rusty")
    expected = round(1.0 - DECAY_PER_EXTRA, 4)
    assert m == expected, f"Expected {expected}, got {m}"


def test_multiplier_decays_more_with_higher_count():
    conn = _make_db(ANTI_FARM_LIMIT + 2)
    m = get_anti_farm_multiplier(conn, 1, "sword_rusty")
    expected = round(max(ANTI_FARM_MIN_RATIO, 1.0 - 3 * DECAY_PER_EXTRA), 4)
    assert m == expected


def test_multiplier_clamped_at_minimum():
    """With enough sales, multiplier never goes below ANTI_FARM_MIN_RATIO."""
    conn = _make_db(ANTI_FARM_LIMIT + 50)
    m = get_anti_farm_multiplier(conn, 1, "sword_rusty")
    assert m == ANTI_FARM_MIN_RATIO


def test_multiplier_does_not_count_different_item():
    """Selling different items resets the count."""
    conn = _make_db(ANTI_FARM_LIMIT + 5, item_key="sword_rusty")
    # Different item — should have full multiplier
    m = get_anti_farm_multiplier(conn, 1, "shield_wood")
    assert m == 1.0


def test_multiplier_does_not_count_different_character():
    """Sales by character 2 don't count for character 1."""
    conn = _make_db(0)
    for _ in range(ANTI_FARM_LIMIT + 5):
        conn.execute(
            """INSERT INTO character_gold_log (character_id, delta, source, meta_json, wall_clock_at)
               VALUES (2, -20, 'shop_sell', ?, datetime('now'))""",
            (json.dumps({"item_key": "sword_rusty"}),),
        )
    conn.commit()
    m = get_anti_farm_multiplier(conn, 1, "sword_rusty")
    assert m == 1.0


# ─── apply_anti_farm ─────────────────────────────────────────────────────────

def test_apply_anti_farm_no_decay():
    assert apply_anti_farm(100, 1.0) == 100


def test_apply_anti_farm_decay():
    """100 gp × 0.9 = 90."""
    assert apply_anti_farm(100, 0.9) == 90


def test_apply_anti_farm_floors_to_1():
    """1 gp item never rounds to 0."""
    assert apply_anti_farm(1, ANTI_FARM_MIN_RATIO) >= 1


def test_apply_anti_farm_zero_price_untouched():
    assert apply_anti_farm(0, 0.5) == 0


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_get_anti_farm_multiplier_returns_1_with_empty_log():
    conn = _make_db(0)
    assert get_anti_farm_multiplier(conn, 99, "any_item") == 1.0
