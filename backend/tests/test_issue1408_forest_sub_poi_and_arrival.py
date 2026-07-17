"""TDD: Issue #1408 — leśny hex z etykietą sub-lokacji + brak narracji przybycia.

Dwa defekty zgłoszone z gry (ruch Strzegwacht → sąsiedni leśny hex pokazał
"Brzezino: Święta Polanka" i ŻADNEJ narracji):

  #1  placement_engine osadzał sub-lokacje (dzieci huba, np. "Brzezino: Święta
      Polanka" pod wioską Brzezino) jako samodzielne POI overworld na losowym
      leśnym hexie daleko od rodzica. Sub-lokacje należą do LOKALNEJ mapy huba,
      nie do mapy świata → muszą być wykluczone z puli placementu.

  #2  po dotarciu na nazwaną lokację nie było prozy LLM. Powód: lokacja bywa
      osadzana JUST-IN-TIME przy dotarciu, a `maybe_narrate_arrival` bramkuje
      na `hex_data.location_key`. Tu testujemy konsumenta: przy ustawionym
      location_key powstaje wpis [Przybycie: <label>] (z ładną etykietą z
      game_locations, nie surowym kluczem); bez location_key / przy zasadzce —
      nie powstaje.
"""
import json
import sqlite3

import pytest

from app.services.placement_engine import try_place_location_on_hex
from app.services import hex_travel_service


# ─────────────────────────── #1 — placement wyklucza sub ───────────────────────

@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE world_hexes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            q INTEGER NOT NULL, r INTEGER NOT NULL,
            hex_type TEXT NOT NULL DEFAULT 'plains',
            map_level INTEGER NOT NULL DEFAULT 0,
            region TEXT NOT NULL DEFAULT 'kresy',
            label TEXT, location_key TEXT, is_active INTEGER DEFAULT 1
        );
        CREATE TABLE hex_type_config (
            hex_type TEXT PRIMARY KEY,
            location_spawn_chance REAL NOT NULL DEFAULT 0.15
        );
        CREATE TABLE game_locations (
            id INTEGER PRIMARY KEY, key TEXT UNIQUE,
            label TEXT, placement TEXT DEFAULT 'floating',
            terrain_tags TEXT DEFAULT '[]',
            approved INTEGER DEFAULT 1, is_active INTEGER DEFAULT 1,
            location_type TEXT DEFAULT 'macro',
            world_hex_q INTEGER, world_hex_r INTEGER,
            region TEXT, parent_key TEXT
        );
        INSERT INTO hex_type_config VALUES ('forest', 1.0);
        INSERT INTO world_hexes (q,r,hex_type,map_level,region,is_active) VALUES (33,5,'forest',0,'kresy',1);
    """)
    return conn


def _add_loc(conn, key, tags, location_type='macro', placement='floating', parent_key=None):
    conn.execute(
        "INSERT INTO game_locations (key,label,placement,terrain_tags,location_type,parent_key)"
        " VALUES (?,?,?,?,?,?)",
        (key, key, placement, json.dumps(tags), location_type, parent_key),
    )
    conn.commit()


def test_sub_location_never_placed_on_overworld_hex(db):
    """Sub-lokacja (dziecko huba) z pasującym tagiem terenu NIE trafia na overworld hex."""
    # oba pasują do 'forest', spawn_chance=1.0 gwarantuje osadzenie CZEGOŚ
    _add_loc(db, 'brzezino_swieta_polanka', ['forest'], location_type='sub', parent_key='brzezino')
    _add_loc(db, 'samotna_kaplica', ['forest'], location_type='macro')

    result = try_place_location_on_hex(db, 33, 5, 'forest', campaign_seed=7)

    assert result == 'samotna_kaplica', "overworld POI musi być top-level, nie sub"
    sub = db.execute("SELECT placement FROM game_locations WHERE key='brzezino_swieta_polanka'").fetchone()
    assert sub['placement'] == 'floating', "sub-lokacja musi zostać floating (nietknięta)"


def test_only_sub_candidates_leaves_hex_empty(db):
    """Gdy w puli są SAME sub-lokacje → hex zostaje pusty (None), nic nie wycieka."""
    _add_loc(db, 'brzezino_tartak', ['forest'], location_type='sub', parent_key='brzezino')
    _add_loc(db, 'zgliszcza_kosciol', ['forest'], location_type='sub', parent_key='zgliszcza')

    result = try_place_location_on_hex(db, 33, 5, 'forest', campaign_seed=7)

    assert result is None
    row = db.execute("SELECT location_key FROM world_hexes WHERE q=33 AND r=5").fetchone()
    assert row['location_key'] is None


def test_macro_location_still_placed(db):
    """Regresja: top-level (macro) lokacja nadal jest osadzana normalnie."""
    _add_loc(db, 'stara_wieza', ['forest'], location_type='macro')
    result = try_place_location_on_hex(db, 33, 5, 'forest', campaign_seed=7)
    assert result == 'stara_wieza'


# ─────────────────────── #2 — narracja przybycia + etykieta ────────────────────

@pytest.fixture
def ndb():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE characters (id INTEGER PRIMARY KEY, user_id INTEGER);
        CREATE TABLE game_locations (
            id INTEGER PRIMARY KEY, key TEXT UNIQUE, label TEXT, is_active INTEGER DEFAULT 1
        );
        CREATE TABLE campaign_turns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER, character_id INTEGER, turn_number INTEGER,
            user_text TEXT, assistant_text TEXT, route TEXT, created_at TEXT
        );
        INSERT INTO characters (id,user_id) VALUES (500,1);
        INSERT INTO game_locations (key,label) VALUES ('brzezino_swieta_polanka','Brzezino: Święta Polanka');
    """)
    return conn


@pytest.fixture
def stub_llm(monkeypatch):
    """Zestub warstwy LLM/świata, by testować samą bramkę narracji przybycia."""
    import app.services.user_llm_settings as uls
    import app.services.llm_service as llm
    import app.services.world_service as ws

    monkeypatch.setattr(uls, "get_user_llm_settings_full", lambda uid: {}, raising=False)
    monkeypatch.setattr(llm, "generate_chat", lambda **kw: "Docierasz na cichą, świętą polanę.", raising=False)
    monkeypatch.setattr(ws, "process_create_tags", lambda prose, conn, cid: (prose, []), raising=False)
    monkeypatch.setattr(ws, "get_current_location_info", lambda conn, cid: {}, raising=False)


def _arrival_turn(conn):
    return conn.execute(
        "SELECT user_text, assistant_text FROM campaign_turns"
        " WHERE user_text LIKE '[Przybycie:%' ORDER BY id DESC LIMIT 1"
    ).fetchone()


def test_arrival_narration_written_for_named_hex(ndb, stub_llm):
    """Hex z location_key → powstaje wpis [Przybycie: <ładna etykieta>] z prozą LLM."""
    result = {"hex_data": {"location_key": "brzezino_swieta_polanka", "label": None}}
    hex_travel_service.maybe_narrate_arrival(ndb, 42, 500, result, arrived_full=True)

    row = _arrival_turn(ndb)
    assert row is not None, "brak wpisu przybycia mimo nazwanego hexa"
    # etykieta z game_locations, nie surowy klucz
    assert row["user_text"] == "[Przybycie: Brzezino: Święta Polanka]"
    assert "polan" in json.loads(row["assistant_text"])["narrative"].lower()


def test_no_arrival_narration_for_wilderness(ndb, stub_llm):
    """Hex bez location_key (dzicz) → BRAK wpisu przybycia (tylko zielony pill podróży)."""
    result = {"hex_data": {"location_key": None}}
    hex_travel_service.maybe_narrate_arrival(ndb, 42, 500, result, arrived_full=True)
    assert _arrival_turn(ndb) is None


def test_no_arrival_narration_on_encounter(ndb, stub_llm):
    """Zasadzka przerywa dotarcie → BRAK narracji przybycia."""
    result = {"hex_data": {"location_key": "brzezino_swieta_polanka"}, "encounter": {"enemy_key": "wilk"}}
    hex_travel_service.maybe_narrate_arrival(ndb, 42, 500, result, arrived_full=True)
    assert _arrival_turn(ndb) is None
