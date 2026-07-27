"""WL-5 (#1504/#1505) — testy pływów Wybrzeża Łez.

Pokrycie:
  * faza pływu z zegara (czysta arytmetyka) — 2 cykle/dobę, granice bloków,
  * licznik godzin do zmiany (hours_to_next_change),
  * has_tide_board — ekwipunek odsłania licznik,
  * get_tide_state — kształt, gating licznika przez tabliczkę, on_coast/on_shallows,
  * tide_blocks_entry — blokada wejścia na plycizna przy przypływie, wolno przy odpływie,
  * nearest_dry_hex — ucieczka na najbliższy suchy ląd,
  * maybe_tide_strand — łagodny wariant: przeniesienie + drobne HP (nie zabija).

Testy DB używają in-memory SQLite z minimalnym schematem (bez Dockera potrzebnego
do logiki czystej; test_dev.sh uruchomi to na kopii DEV-DB).
"""

import json
import sqlite3

import pytest

from app.services import tide_service as ts


# ── faza pływu (czysta arytmetyka — bez DB) ──────────────────────────────────

def test_phase_alternates_every_6h():
    # blok 0 (0-5) odpływ, blok 1 (6-11) przypływ, blok 2 (12-17) odpływ …
    assert ts.tide_phase(0) == "odplyw"
    assert ts.tide_phase(5) == "odplyw"
    assert ts.tide_phase(6) == "przyplyw"
    assert ts.tide_phase(11) == "przyplyw"
    assert ts.tide_phase(12) == "odplyw"
    assert ts.tide_phase(18) == "przyplyw"


def test_two_cycles_per_day():
    # 24 h / (6 h * 2 fazy) = 2 pełne cykle na dobę (wartość startowa).
    assert ts.cycles_per_day() == 2


def test_is_flood_matches_phase():
    assert ts.is_flood(6) is True
    assert ts.is_flood(0) is False
    # przejezdność jest odwrotnością przypływu
    assert ts.is_plycizna_passable(0) is True
    assert ts.is_plycizna_passable(6) is False


def test_hours_to_next_change_bounds():
    assert ts.hours_to_next_change(0) == 6   # start bloku → pełne 6 h
    assert ts.hours_to_next_change(5) == 1   # tuż przed zmianą
    assert ts.hours_to_next_change(6) == 6
    assert ts.hours_to_next_change(9) == 3
    # zawsze 1..6
    for h in range(0, 48):
        assert 1 <= ts.hours_to_next_change(h) <= ts.TIDE_PHASE_HOURS


# ── DB fixture (in-memory) ───────────────────────────────────────────────────

@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE game_sessions (campaign_id INTEGER, session_flags TEXT);
        CREATE TABLE world_hexes (q INTEGER, r INTEGER, map_level INTEGER DEFAULT 0,
                                  is_active INTEGER DEFAULT 1, hex_type TEXT);
        CREATE TABLE hex_type_config (hex_type TEXT, is_passable INTEGER, is_active INTEGER DEFAULT 1);
        CREATE TABLE characters (id INTEGER PRIMARY KEY, sheet_json TEXT);
        CREATE TABLE character_inventory (id INTEGER PRIMARY KEY, character_id INTEGER,
                                          item_key TEXT, consumable_key TEXT, weapon_key TEXT,
                                          quantity INTEGER DEFAULT 1);
        CREATE TABLE campaign_hex_data (campaign_id INTEGER, hex_q INTEGER, hex_r INTEGER,
                                        discovered INTEGER, UNIQUE(campaign_id, hex_q, hex_r));
        CREATE TABLE campaign_turns (id INTEGER PRIMARY KEY, campaign_id INTEGER,
                                     character_id INTEGER, turn_number INTEGER, user_text TEXT,
                                     assistant_text TEXT, route TEXT, created_at TEXT);
        """
    )
    # teren: plycizna passable (pływy), plains/road suche, morze/rafy nieprzejezdne
    conn.executemany(
        "INSERT INTO hex_type_config (hex_type, is_passable) VALUES (?, ?)",
        [("plycizna", 1), ("plains", 1), ("road", 1), ("morze", 0), ("rafy", 0)],
    )
    conn.commit()
    yield conn
    conn.close()


def _set_clock(conn, campaign_id, ingame_hours, current_hex=None):
    flags = {"ingame_hours": ingame_hours}
    if current_hex is not None:
        flags["current_hex"] = {"q": current_hex[0], "r": current_hex[1]}
    conn.execute("DELETE FROM game_sessions WHERE campaign_id=?", (campaign_id,))
    conn.execute(
        "INSERT INTO game_sessions (campaign_id, session_flags) VALUES (?, ?)",
        (campaign_id, json.dumps(flags)),
    )
    conn.commit()


def _hex(conn, q, r, hex_type):
    conn.execute(
        "INSERT INTO world_hexes (q, r, map_level, is_active, hex_type) VALUES (?,?,0,1,?)",
        (q, r, hex_type),
    )
    conn.commit()


# ── has_tide_board ───────────────────────────────────────────────────────────

def test_has_tide_board(db):
    assert ts.has_tide_board(db, 7) is False
    db.execute(
        "INSERT INTO character_inventory (character_id, item_key, quantity) VALUES (7, ?, 1)",
        (ts.TABLICZKA_KEY,),
    )
    db.commit()
    assert ts.has_tide_board(db, 7) is True


# ── get_tide_state ───────────────────────────────────────────────────────────

def test_tide_state_hides_counter_without_board(db):
    _hex(db, 1, 1, "plycizna")
    _set_clock(db, 100, ingame_hours=0, current_hex=(1, 1))  # odpływ
    st = ts.get_tide_state(db, 100, 7)
    assert st["phase"] == "odplyw"
    assert st["passable"] is True
    assert st["on_coast"] is True
    assert st["on_shallows"] is True
    assert st["has_board"] is False
    assert st["hours_to_change"] is None  # brak tabliczki → brak licznika


def test_tide_state_shows_counter_with_board(db):
    _hex(db, 1, 1, "plycizna")
    _set_clock(db, 100, ingame_hours=9, current_hex=(1, 1))  # przypływ, 3 h do zmiany
    db.execute(
        "INSERT INTO character_inventory (character_id, item_key, quantity) VALUES (7, ?, 1)",
        (ts.TABLICZKA_KEY,),
    )
    db.commit()
    st = ts.get_tide_state(db, 100, 7)
    assert st["phase"] == "przyplyw"
    assert st["is_flood"] is True
    assert st["has_board"] is True
    assert st["hours_to_change"] == 3
    assert st["next_phase"] == "odplyw"


def test_tide_state_off_coast(db):
    _hex(db, 2, 2, "plains")
    _set_clock(db, 100, ingame_hours=6, current_hex=(2, 2))
    st = ts.get_tide_state(db, 100, 7)
    assert st["on_coast"] is False
    assert st["on_shallows"] is False


# ── tide_blocks_entry ────────────────────────────────────────────────────────

def test_entry_blocked_at_flood_allowed_at_ebb(db):
    _hex(db, 5, 5, "plycizna")
    # przypływ → blokada
    _set_clock(db, 100, ingame_hours=6)
    assert ts.tide_blocks_entry(db, 100, 5, 5) is True
    # odpływ → wolna droga
    _set_clock(db, 100, ingame_hours=0)
    assert ts.tide_blocks_entry(db, 100, 5, 5) is False


def test_entry_never_blocks_dry_land(db):
    _hex(db, 5, 6, "plains")
    _set_clock(db, 100, ingame_hours=6)  # przypływ, ale cel suchy
    assert ts.tide_blocks_entry(db, 100, 5, 6) is False


# ── nearest_dry_hex ──────────────────────────────────────────────────────────

def test_nearest_dry_hex_finds_land(db):
    # (0,0) plycizna, sąsiedzi plycizna/morze, ale jeden plains dalej
    _hex(db, 0, 0, "plycizna")
    from app.services.hex_travel_service import hex_neighbors
    ring1 = set(hex_neighbors(0, 0))
    for (q, r) in ring1:
        _hex(db, q, r, "morze")
    # suchy ląd w drugim pierścieniu (nie pokrywa się z pierścieniem 1 ani origin)
    n2 = hex_neighbors(*list(ring1)[0])
    dry = next(c for c in n2 if c != (0, 0) and c not in ring1)
    _hex(db, dry[0], dry[1], "plains")
    found = ts.nearest_dry_hex(db, 0, 0)
    assert found is not None
    assert ts._hex_type_at(db, *found) == "plains"


# ── maybe_tide_strand (łagodny wariant) ──────────────────────────────────────

def test_strand_relocates_and_scrapes_hp(db, monkeypatch):
    # bohater stoi na plycizna, przypływ; obok suchy plains
    _hex(db, 0, 0, "plycizna")
    from app.services.hex_travel_service import hex_neighbors
    nbrs = hex_neighbors(0, 0)
    _hex(db, nbrs[0][0], nbrs[0][1], "plains")  # dokąd ucieknie
    _set_clock(db, 100, ingame_hours=6, current_hex=(0, 0))  # przypływ
    db.execute("INSERT INTO characters (id, sheet_json) VALUES (7, ?)",
               (json.dumps({"current_hp": 20, "max_hp": 20}),))
    db.commit()

    # set_position i add_condition operują na własnych połączeniach → podmieniamy
    moved = {}

    def fake_set_position(conn, campaign_id, current_hex=None, **kw):
        moved["hex"] = current_hex
        flags = json.loads(conn.execute(
            "SELECT session_flags FROM game_sessions WHERE campaign_id=?",
            (campaign_id,)).fetchone()["session_flags"])
        flags["current_hex"] = current_hex
        conn.execute("UPDATE game_sessions SET session_flags=? WHERE campaign_id=?",
                     (json.dumps(flags), campaign_id))

    monkeypatch.setattr("app.services.location_state_service.set_position", fake_set_position)
    monkeypatch.setattr("app.services.combat_service.add_condition_to_character",
                        lambda *a, **k: 1)

    result = {}
    out = ts.maybe_tide_strand(db, 100, 7, result, rng=__import__("random").Random(1))
    assert out is not None
    assert out["moved"] is True
    assert 1 <= out["damage"] <= 4
    # HP spadło, ale nigdy do 0 (pływ nie zabija)
    sheet = json.loads(db.execute("SELECT sheet_json FROM characters WHERE id=7").fetchone()["sheet_json"])
    assert sheet["current_hp"] == 20 - out["damage"]
    assert sheet["current_hp"] >= 1
    assert result["tide_strand"]["to"] == {"q": nbrs[0][0], "r": nbrs[0][1]}


def test_strand_noop_at_ebb(db):
    _hex(db, 0, 0, "plycizna")
    _set_clock(db, 100, ingame_hours=0, current_hex=(0, 0))  # odpływ — bezpiecznie
    db.execute("INSERT INTO characters (id, sheet_json) VALUES (7, ?)",
               (json.dumps({"current_hp": 20}),))
    db.commit()
    assert ts.maybe_tide_strand(db, 100, 7, {}) is None


def test_strand_noop_off_shallows(db):
    _hex(db, 0, 0, "plains")
    _set_clock(db, 100, ingame_hours=6, current_hex=(0, 0))  # przypływ, ale nie na mieliźnie
    db.execute("INSERT INTO characters (id, sheet_json) VALUES (7, ?)",
               (json.dumps({"current_hp": 20}),))
    db.commit()
    assert ts.maybe_tide_strand(db, 100, 7, {}) is None
