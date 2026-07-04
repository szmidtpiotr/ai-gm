"""TDD: Issue #1159 — gold_at_end zawsze 0 (czytane z sheet_json.gold którego nikt nie zapisuje).

Złoto trzymane WYŁĄCZNIE w kolumnie `characters.gold_gp`. Kronika/historia czytała
`sheet_json.get("gold_gp") or sheet_json.get("gold")` — klucz nigdy nie istnieje → 0.
Fix: helper `get_character_gold(conn, id)` czyta kolumnę.
"""
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.services.economy_service import get_character_gold


def _db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE characters (id INTEGER PRIMARY KEY, gold_gp INTEGER DEFAULT 0,
            sheet_json TEXT);
        """
    )
    return conn


# ─── Test główny ─────────────────────────────────────────────────────────────

def test_reads_gold_from_column_not_sheet_json():
    """gold_gp w kolumnie = 250, sheet_json bez złota → helper zwraca 250 (nie 0)."""
    conn = _db()
    conn.execute(
        "INSERT INTO characters (id, gold_gp, sheet_json) VALUES (1, 250, '{}')"
    )
    conn.commit()
    assert get_character_gold(conn, 1) == 250


def test_column_is_authoritative_over_stale_sheet_json():
    """Nawet gdy sheet_json ma stare gold_gp, źródłem prawdy jest kolumna."""
    conn = _db()
    conn.execute(
        'INSERT INTO characters (id, gold_gp, sheet_json) VALUES (1, 250, \'{"gold_gp": 99}\')'
    )
    conn.commit()
    assert get_character_gold(conn, 1) == 250


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_missing_character_returns_zero():
    conn = _db()
    assert get_character_gold(conn, 999) == 0


def test_null_gold_returns_zero():
    conn = _db()
    conn.execute("INSERT INTO characters (id, gold_gp, sheet_json) VALUES (1, NULL, '{}')")
    conn.commit()
    assert get_character_gold(conn, 1) == 0
