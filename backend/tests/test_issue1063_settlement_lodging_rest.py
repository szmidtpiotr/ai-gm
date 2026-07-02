"""TDD: Issue #1063 — Auto safe_for_rest w osadach (Opcja B, sub-lokacja driven).

Bug: rest_service._is_safe_for_character sprawdza WYŁĄCZNIE safe_for_rest bieżącej
lokacji (game_locations.id == current_location_id). Gracz stojący w osadzie (macro),
która MA sub-lokację karczma/gospoda (location_subtype IN ('inn','tavern')), i tak
dostaje "not_safe_for_rest" — bo sama osada nigdy nie ma safe_for_rest=1 ustawionego
ręcznie (patrz #994/#995 — dopiero sub-lokacja typu inn/tavern dostaje flagę).

Fix: settlement ma sub-lokację typu inn/tavern → traktuj bieżącą lokację jako
bezpieczną do odpoczynku, niezależnie od jej własnej kolumny safe_for_rest.
"""
import json
import sqlite3
import sys

sys.path.insert(0, "/app")


def _make_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE characters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sheet_json TEXT NOT NULL DEFAULT '{}'
        );
        CREATE TABLE game_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL,
            current_location_id INTEGER,
            session_flags TEXT DEFAULT '{}',
            ingame_hours INTEGER DEFAULT 8
        );
        CREATE TABLE world_hexes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            q INTEGER, r INTEGER, hex_type TEXT, label TEXT,
            location_key TEXT, map_level INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1
        );
        CREATE TABLE game_locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT UNIQUE NOT NULL,
            label TEXT NOT NULL,
            location_type TEXT DEFAULT 'macro',
            parent_key TEXT DEFAULT NULL,
            location_subtype TEXT,
            safe_for_rest INTEGER NOT NULL DEFAULT 0,
            is_active INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE active_combat (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER,
            status TEXT DEFAULT 'inactive'
        );
        """
    )
    return conn


def _sheet(current_hp=5, max_hp=10):
    return json.dumps({
        "current_hp": current_hp,
        "max_hp": max_hp,
        "stat_modifiers": {"CON": 1},
        "short_rests_used": 0,
    })


def _seed_character(conn, char_id=1, **sheet_kwargs):
    conn.execute(
        "INSERT INTO characters (id, sheet_json) VALUES (?, ?)",
        (char_id, _sheet(**sheet_kwargs)),
    )


def _seed_session(conn, campaign_id, current_location_id):
    conn.execute(
        "INSERT INTO game_sessions (campaign_id, current_location_id, session_flags) VALUES (?, ?, '{}')",
        (campaign_id, current_location_id),
    )


def _insert_location(conn, key, label, location_type="macro", parent_key=None,
                      location_subtype=None, safe_for_rest=0):
    cur = conn.execute(
        "INSERT INTO game_locations (key, label, location_type, parent_key, location_subtype, safe_for_rest) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (key, label, location_type, parent_key, location_subtype, safe_for_rest),
    )
    return cur.lastrowid


# ── Test główny ────────────────────────────────────────────────────────────────

def test_short_rest_allowed_in_settlement_with_tavern_subloc():
    """Gracz stoi w osadzie (macro, safe_for_rest=0) która ma sub-lokację 'tavern'.
    Rest musi przejść mimo że macro NIGDY nie miało własnej flagi ustawionej ręcznie."""
    from app.services.rest_service import perform_short_rest

    conn = _make_db()
    macro_id = _insert_location(conn, "wolanka", "Wolanka", location_type="macro", safe_for_rest=0)
    _insert_location(
        conn, "wolanka_karczma", "Wolanka: Karczma", location_type="sub",
        parent_key="wolanka", location_subtype="tavern", safe_for_rest=0,
    )
    _seed_session(conn, campaign_id=201, current_location_id=macro_id)
    _seed_character(conn, char_id=1, current_hp=5, max_hp=10)
    conn.commit()

    result = perform_short_rest(conn, character_id=1, campaign_id=201)
    assert result.get("ok") is True, result
    assert result["hp_after"] > result["hp_before"] or result["hp_after"] == 10


def test_short_rest_allowed_with_inn_subtype_too():
    """Subtype 'inn' (nie tylko 'tavern') też musi liczyć się jako nocleg."""
    from app.services.rest_service import perform_short_rest

    conn = _make_db()
    macro_id = _insert_location(conn, "wachstein", "Wachstein", location_type="macro", safe_for_rest=0)
    _insert_location(
        conn, "wachstein_inn", "Wachstein: Zajazd", location_type="sub",
        parent_key="wachstein", location_subtype="inn", safe_for_rest=0,
    )
    _seed_session(conn, campaign_id=202, current_location_id=macro_id)
    _seed_character(conn, char_id=2, current_hp=5, max_hp=10)
    conn.commit()

    result = perform_short_rest(conn, character_id=2, campaign_id=202)
    assert result.get("ok") is True, result


# ── Backward compatibility ───────────────────────────────────────────────────

def test_short_rest_blocked_in_settlement_without_lodging():
    """Osada BEZ sub-lokacji inn/tavern — stary błąd 'not_safe_for_rest' musi zostać."""
    from app.services.rest_service import perform_short_rest

    conn = _make_db()
    macro_id = _insert_location(conn, "dzika_osada", "Dzika Osada", location_type="macro", safe_for_rest=0)
    _insert_location(
        conn, "dzika_osada_stajnia", "Dzika Osada: Stajnia", location_type="sub",
        parent_key="dzika_osada", location_subtype="barn", safe_for_rest=0,
    )
    _seed_session(conn, campaign_id=203, current_location_id=macro_id)
    _seed_character(conn, char_id=3, current_hp=5, max_hp=10)
    conn.commit()

    result = perform_short_rest(conn, character_id=3, campaign_id=203)
    assert result.get("ok") is False
    assert result.get("error") == "not_safe_for_rest", result


def test_short_rest_still_works_when_location_itself_flagged_safe():
    """Lokacja z własnym safe_for_rest=1 (stary mechanizm) nadal działa bez zmian."""
    from app.services.rest_service import perform_short_rest

    conn = _make_db()
    loc_id = _insert_location(conn, "bezpieczna", "Bezpieczna Polana", location_type="macro", safe_for_rest=1)
    _seed_session(conn, campaign_id=204, current_location_id=loc_id)
    _seed_character(conn, char_id=4, current_hp=5, max_hp=10)
    conn.commit()

    result = perform_short_rest(conn, character_id=4, campaign_id=204)
    assert result.get("ok") is True, result


def test_short_rest_blocked_with_no_location_at_all():
    """Brak current_location_id i brak current_hex w session_flags — nadal blokada."""
    from app.services.rest_service import perform_short_rest

    conn = _make_db()
    _seed_session(conn, campaign_id=205, current_location_id=None)
    _seed_character(conn, char_id=5, current_hp=5, max_hp=10)
    conn.commit()

    result = perform_short_rest(conn, character_id=5, campaign_id=205)
    assert result.get("ok") is False
    assert result.get("error") == "not_safe_for_rest", result
