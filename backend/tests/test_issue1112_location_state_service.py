"""TDD: Issue #1112 — Jeden serwis zapisu pozycji (koniec 5 źródeł prawdy).

Weryfikuje:
1. location_state_service.set_position() istnieje
2. set_position() aktualizuje atomowo WSZYSTKIE 4 pola naraz
3. sheet_json.current_hex jest aktualizowane przy ruchu (był brakujący kawałek)
4. GET /player-map czyta current_hex z session_flags (nie z sheet_json)
5. clear_local_hex czyści local_hex przy wejściu na world-travel
6. Partial write nie może się zdarzyć (atomowość)
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest


# ── In-memory DB helpers ────────────────────────────────────────────────────────

SCHEMA = """
    CREATE TABLE IF NOT EXISTS game_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        campaign_id INTEGER NOT NULL,
        session_flags TEXT NOT NULL DEFAULT '{}',
        current_location_id INTEGER
    );

    CREATE TABLE IF NOT EXISTS characters (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        campaign_id INTEGER NOT NULL,
        sheet_json TEXT NOT NULL DEFAULT '{}',
        status TEXT DEFAULT 'active'
    );

    CREATE TABLE IF NOT EXISTS game_locations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        key TEXT NOT NULL,
        label TEXT,
        is_active INTEGER DEFAULT 1
    );
"""


def _make_db(
    campaign_id: int = 1,
    current_hex: dict | None = None,
    local_hex: dict | None = None,
    current_location_id: int | None = None,
    char_sheet_hex: dict | None = None,
) -> tuple[sqlite3.Connection, int, int]:
    """Return (conn, session_id, character_id)."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)

    flags: dict = {}
    if current_hex:
        flags["current_hex"] = current_hex
    if local_hex:
        flags["local_hex"] = local_hex

    conn.execute(
        "INSERT INTO game_sessions (campaign_id, session_flags, current_location_id) VALUES (?, ?, ?)",
        (campaign_id, json.dumps(flags), current_location_id),
    )
    session_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    sheet: dict = {}
    if char_sheet_hex:
        sheet["current_hex"] = char_sheet_hex

    conn.execute(
        "INSERT INTO characters (campaign_id, sheet_json) VALUES (?, ?)",
        (campaign_id, json.dumps(sheet)),
    )
    char_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    conn.commit()
    return conn, session_id, char_id


def _read_session(conn: sqlite3.Connection, campaign_id: int) -> dict:
    row = conn.execute(
        "SELECT session_flags, current_location_id FROM game_sessions WHERE campaign_id = ?",
        (campaign_id,),
    ).fetchone()
    return {
        "flags": json.loads(row["session_flags"] or "{}"),
        "current_location_id": row["current_location_id"],
    }


def _read_sheet(conn: sqlite3.Connection, char_id: int) -> dict:
    row = conn.execute("SELECT sheet_json FROM characters WHERE id = ?", (char_id,)).fetchone()
    return json.loads(row["sheet_json"] or "{}")


# ─────────────────────────────────────────────────────────────────────────────
# TEST 1: Serwis musi istnieć
# ─────────────────────────────────────────────────────────────────────────────

def test_location_state_service_exists():
    """location_state_service.set_position musi istnieć."""
    from app.services.location_state_service import set_position  # noqa: F401


# ─────────────────────────────────────────────────────────────────────────────
# TEST 2: Atomowo aktualizuje wszystkie 4 pola
# ─────────────────────────────────────────────────────────────────────────────

def test_set_position_updates_all_four_fields():
    """Jedno wywołanie set_position() aktualizuje current_hex + current_location_id + local_hex + sheet_json."""
    from app.services.location_state_service import set_position

    conn, _sid, char_id = _make_db(
        campaign_id=1,
        current_hex={"q": 0, "r": 0},
        local_hex={"hex_id": 99, "q": 0, "r": 0},
        current_location_id=None,
    )
    # Seed a location
    conn.execute("INSERT INTO game_locations (id, key, label) VALUES (10, 'karczma', 'Karczma')")
    conn.commit()

    new_hex = {"q": 5, "r": 3}
    new_local = {"hex_id": 42, "q": 1, "r": 2, "location_key": "karczma"}

    set_position(
        conn,
        campaign_id=1,
        current_hex=new_hex,
        current_location_id=10,
        local_hex=new_local,
        character_id=char_id,
    )

    session = _read_session(conn, campaign_id=1)
    sheet = _read_sheet(conn, char_id)

    # session_flags.current_hex
    assert session["flags"]["current_hex"] == new_hex, (
        f"session_flags.current_hex nie zaktualizowane: {session['flags'].get('current_hex')}"
    )
    # game_sessions.current_location_id
    assert session["current_location_id"] == 10, (
        f"current_location_id nie zaktualizowane: {session['current_location_id']}"
    )
    # session_flags.local_hex
    assert session["flags"]["local_hex"] == new_local, (
        f"session_flags.local_hex nie zaktualizowane: {session['flags'].get('local_hex')}"
    )
    # sheet_json.current_hex — to był brakujący kawałek (mapa gracza)
    assert sheet.get("current_hex") == new_hex, (
        f"sheet_json.current_hex nie zaktualizowane: {sheet.get('current_hex')} "
        f"(mapa gracza pokazuje pin w złym miejscu)"
    )


# ─────────────────────────────────────────────────────────────────────────────
# TEST 3: sheet_json.current_hex musi się zaktualizować przy world-travel
# ─────────────────────────────────────────────────────────────────────────────

def test_sheet_json_current_hex_updated_on_world_travel():
    """sheet_json.current_hex musi być zsynchronizowane po każdym world-travel.

    Aktualnie hex_travel_service aktualizuje tylko session_flags.current_hex —
    sheet_json pozostaje stary, przez co mapa gracza pokazuje pin w złym miejscu.
    """
    from app.services.location_state_service import set_position

    old_hex = {"q": 1, "r": 1}
    new_hex = {"q": 7, "r": 4}

    conn, _sid, char_id = _make_db(
        campaign_id=2,
        current_hex=old_hex,
        char_sheet_hex=old_hex,  # sheet_json startuje ze starą pozycją
    )

    set_position(conn, campaign_id=2, current_hex=new_hex, character_id=char_id)

    sheet = _read_sheet(conn, char_id)
    session = _read_session(conn, campaign_id=2)

    # Oba muszą pokazywać tę samą (nową) pozycję
    assert session["flags"]["current_hex"] == new_hex, "session_flags.current_hex nie zaktualizowane"
    assert sheet.get("current_hex") == new_hex, (
        "sheet_json.current_hex wciąż pokazuje starą pozycję — bug mapy gracza (#1112)"
    )


# ─────────────────────────────────────────────────────────────────────────────
# TEST 4: clear_local_hex czyści local_hex przy wyjściu z osady
# ─────────────────────────────────────────────────────────────────────────────

def test_clear_local_hex_on_world_travel():
    """Przy world-travel clear_local_hex=True musi usunąć session_flags.local_hex."""
    from app.services.location_state_service import set_position

    local = {"hex_id": 10, "q": 0, "r": 1, "location_key": "rynek"}
    conn, _sid, _cid = _make_db(campaign_id=3, local_hex=local)

    set_position(conn, campaign_id=3, current_hex={"q": 8, "r": 2}, clear_local_hex=True)

    session = _read_session(conn, campaign_id=3)
    assert "local_hex" not in session["flags"], (
        "local_hex powinien być wyczyszczony po world-travel, a nadal istnieje"
    )


# ─────────────────────────────────────────────────────────────────────────────
# TEST 5: Wywołanie bez parametrów nie zmienia niczego
# ─────────────────────────────────────────────────────────────────────────────

def test_set_position_no_args_is_noop():
    """set_position() bez argumentów nie zmienia istniejących danych."""
    from app.services.location_state_service import set_position

    initial_hex = {"q": 3, "r": 3}
    conn, _sid, char_id = _make_db(
        campaign_id=4,
        current_hex=initial_hex,
        current_location_id=5,
        char_sheet_hex=initial_hex,
    )

    set_position(conn, campaign_id=4)  # bez żadnych opcjonalnych argumentów

    session = _read_session(conn, campaign_id=4)
    sheet = _read_sheet(conn, char_id)

    assert session["flags"]["current_hex"] == initial_hex, "current_hex zmieniony bez powodu"
    assert session["current_location_id"] == 5, "current_location_id zmieniony bez powodu"
    assert sheet.get("current_hex") == initial_hex, "sheet_json.current_hex zmieniony bez powodu"


# ─────────────────────────────────────────────────────────────────────────────
# TEST 6: set_position z current_location_id=None czyści lokalizację
# ─────────────────────────────────────────────────────────────────────────────

def test_set_position_clears_location_id_when_none_explicit():
    """set_position z clear_location_id=True kasuje current_location_id."""
    from app.services.location_state_service import set_position

    conn, _sid, _cid = _make_db(campaign_id=5, current_location_id=99)

    set_position(conn, campaign_id=5, current_hex={"q": 10, "r": 0}, clear_location_id=True)

    session = _read_session(conn, campaign_id=5)
    assert session["current_location_id"] is None, (
        f"current_location_id powinien być NULL, jest: {session['current_location_id']}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# TEST 7: Backward compat — istniejące pola w session_flags nie są kasowane
# ─────────────────────────────────────────────────────────────────────────────

def test_set_position_preserves_other_session_flags():
    """set_position nie kasuje innych pól w session_flags (np. combat_state, fatigue)."""
    from app.services.location_state_service import set_position

    conn, _sid, _cid = _make_db(campaign_id=6, current_hex={"q": 1, "r": 1})
    # Wstaw dodatkowe flagi
    conn.execute(
        "UPDATE game_sessions SET session_flags = ? WHERE campaign_id = 6",
        (json.dumps({"current_hex": {"q": 1, "r": 1}, "fatigue": 3, "combat_state": "active"}),),
    )
    conn.commit()

    set_position(conn, campaign_id=6, current_hex={"q": 2, "r": 2})

    session = _read_session(conn, campaign_id=6)
    assert session["flags"].get("fatigue") == 3, "fatigue skasowany przez set_position"
    assert session["flags"].get("combat_state") == "active", "combat_state skasowany przez set_position"
    assert session["flags"]["current_hex"] == {"q": 2, "r": 2}, "current_hex nie zaktualizowany"


# ── PT-F2 #1136: current_location_key stays in sync with current_location_id ────

def test_ptf2_location_key_synced_on_move():
    """PT-F7 #1141: current location key is DERIVED from current_location_id (single
    source), not stored in session_flags. get_current_location_key follows the move.
    """
    from app.services.location_state_service import set_position, get_current_location_key
    conn, session_id, _ = _make_db(campaign_id=1)
    conn.execute("INSERT INTO game_locations (id, key, label) VALUES (10, 'wilczy_las', 'Wilczy Las')")
    conn.execute("INSERT INTO game_locations (id, key, label) VALUES (11, 'vilnograd', 'Vilnograd')")
    conn.commit()

    set_position(conn, campaign_id=1, current_location_id=10)
    conn.commit()
    assert get_current_location_key(conn, 1) == "wilczy_las"
    # and it is NOT mirrored into session_flags anymore (single source)
    flags = json.loads(conn.execute("SELECT session_flags FROM game_sessions WHERE id=?", (session_id,)).fetchone()[0])
    assert "current_location_key" not in flags

    # moving again — derived key follows the new location, still no staleness
    set_position(conn, campaign_id=1, current_location_id=11)
    conn.commit()
    assert get_current_location_key(conn, 1) == "vilnograd", "derived key must follow the new location"


def test_ptf2_location_key_cleared_with_location():
    """PT-F2: clear_location_id also removes the stale key."""
    from app.services.location_state_service import set_position
    conn, session_id, _ = _make_db(campaign_id=1)
    conn.execute("INSERT INTO game_locations (id, key, label) VALUES (10, 'wilczy_las', 'Wilczy Las')")
    conn.commit()
    set_position(conn, campaign_id=1, current_location_id=10)
    conn.commit()
    set_position(conn, campaign_id=1, clear_location_id=True)
    conn.commit()
    flags = json.loads(conn.execute("SELECT session_flags FROM game_sessions WHERE id=?", (session_id,)).fetchone()[0])
    assert "current_location_key" not in flags, "key must be dropped when location is cleared"


def test_ptf2_missing_characters_table_no_crash():
    """PT-F2: a position write must not crash when the characters table is absent."""
    from app.services.location_state_service import set_position
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        "CREATE TABLE game_sessions (id INTEGER PRIMARY KEY AUTOINCREMENT, campaign_id INTEGER, session_flags TEXT DEFAULT '{}' , current_location_id INTEGER);"
    )
    conn.execute("INSERT INTO game_sessions (campaign_id, session_flags) VALUES (1, '{}')")
    conn.commit()
    # no characters table, no game_locations table -> must be tolerant
    set_position(conn, campaign_id=1, current_hex={"q": 3, "r": 1})
    conn.commit()
    flags = json.loads(conn.execute("SELECT session_flags FROM game_sessions WHERE campaign_id=1").fetchone()[0])
    assert flags["current_hex"] == {"q": 3, "r": 1}, "current_hex must persist even without characters table"


# ── PT-F7 #1141: current_location_key is never persisted; location is single-source ──

def test_ptf7_key_never_persisted_in_flags():
    """PT-F7: set_position must NOT write session_flags.current_location_key, and must
    strip any stale mirror left by older rows."""
    from app.services.location_state_service import set_position, get_current_location_key
    conn, session_id, _ = _make_db(campaign_id=1)
    conn.execute("INSERT INTO game_locations (id, key, label) VALUES (10, 'wilczy_las', 'Wilczy Las')")
    # simulate a legacy row that still had the mirror
    conn.execute("UPDATE game_sessions SET session_flags = ? WHERE id = ?",
                 (json.dumps({"current_location_key": "STALE"}), session_id))
    conn.commit()

    set_position(conn, campaign_id=1, current_location_id=10)
    conn.commit()

    flags = json.loads(conn.execute("SELECT session_flags FROM game_sessions WHERE id=?", (session_id,)).fetchone()[0])
    assert "current_location_key" not in flags, "stale mirror must be stripped, never re-written"
    assert get_current_location_key(conn, 1) == "wilczy_las", "key derived from current_location_id"


def test_ptf7_get_current_location_full_shape():
    """PT-F7: get_current_location returns the full derived record."""
    from app.services.location_state_service import set_position, get_current_location
    conn, session_id, _ = _make_db(campaign_id=1)
    # richer game_locations for this test
    conn.execute("ALTER TABLE game_locations ADD COLUMN location_type TEXT")
    conn.execute("ALTER TABLE game_locations ADD COLUMN safe_for_rest INTEGER DEFAULT 0")
    conn.execute("ALTER TABLE game_locations ADD COLUMN parent_key TEXT")
    conn.execute("INSERT INTO game_locations (id, key, label, location_type, safe_for_rest, parent_key) "
                 "VALUES (10, 'karczma', 'Karczma', 'sub', 1, 'wolanka')")
    conn.commit()
    set_position(conn, campaign_id=1, current_location_id=10)
    conn.commit()
    loc = get_current_location(conn, 1)
    assert loc["key"] == "karczma"
    assert loc["safe_for_rest"] == 1
    assert loc["parent_key"] == "wolanka"
    assert loc["location_type"] == "sub"
