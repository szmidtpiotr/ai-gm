"""TDD: Issue #750 — blok ŚWIAT (teren hexa) nadpisuje scenę wnętrza karczmy.

build_swiat_imperative(conn, current_location_id) wybiera imperatyw pod blok ŚWIAT:
- sub-lokacja (wnętrze) → miękki imperatyw „kontynuuj scenę wnętrza"
- macro / brak lokacji → twardy imperatyw „opisuj OBECNY teren / przemieścił się"
"""
import sqlite3

import pytest

from app.services.game_engine import build_swiat_imperative


def _make_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE game_locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT,
            label TEXT,
            location_type TEXT,
            location_subtype TEXT,
            is_active INTEGER NOT NULL DEFAULT 1
        );
        """
    )
    return conn


def _insert_loc(conn, loc_id, label, location_type, subtype=None, is_active=1):
    conn.execute(
        "INSERT INTO game_locations (id, key, label, location_type, location_subtype, is_active) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (loc_id, f"loc_{loc_id}", label, location_type, subtype, is_active),
    )
    conn.commit()


# ── inside sub-location → soft imperative ────────────────────────────────────

def test_inside_tavern_gets_soft_imperative():
    conn = _make_db()
    _insert_loc(conn, 47, "Wolanka: Szynk Górniczy", "sub", "tavern")
    imp = build_swiat_imperative(conn, 47)
    assert "WEWNĄTRZ LOKACJI" in imp
    assert "Wolanka: Szynk Górniczy" in imp
    assert "PRZEMIEŚCIŁ SIĘ" not in imp
    assert "opisuj OBECNY teren" not in imp


def test_inside_sub_without_label_still_soft():
    conn = _make_db()
    _insert_loc(conn, 5, None, "sub", "cave")
    imp = build_swiat_imperative(conn, 5)
    assert "WEWNĄTRZ LOKACJI" in imp
    assert "PRZEMIEŚCIŁ SIĘ" not in imp


# ── open terrain → hard imperative (unchanged) ───────────────────────────────

def test_macro_location_gets_hard_imperative():
    conn = _make_db()
    _insert_loc(conn, 10, "Las Brzozowy", "macro", "forest")
    imp = build_swiat_imperative(conn, 10)
    assert "PRZEMIEŚCIŁ SIĘ" in imp
    assert "WEWNĄTRZ LOKACJI" not in imp


def test_no_location_id_gets_hard_imperative():
    conn = _make_db()
    imp = build_swiat_imperative(conn, None)
    assert "PRZEMIEŚCIŁ SIĘ" in imp


def test_missing_location_row_gets_hard_imperative():
    conn = _make_db()
    imp = build_swiat_imperative(conn, 999)
    assert "PRZEMIEŚCIŁ SIĘ" in imp


def test_inactive_sub_location_falls_back_to_hard():
    conn = _make_db()
    _insert_loc(conn, 7, "Zburzona Karczma", "sub", "tavern", is_active=0)
    imp = build_swiat_imperative(conn, 7)
    assert "PRZEMIEŚCIŁ SIĘ" in imp
