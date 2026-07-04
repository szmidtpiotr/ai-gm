"""TDD: Issue #1152 — teleport lokacyjny na starcie kampanii z szablonu.

Trzy naprawy:
A) resolve_starting_hex: istniejący hex bez lokacji on-hex NIE może być kotwiczony
   do lokacji z name-matcha / pierwszej kanonicznej (rozjazd hex↔lokacja, #992).
B) inline opening fallback: prompt uziemiony w realnej pozycji (describe_start_position)
   + location_intent(create) z openingu jest aplikowany (lokacja powstaje i kotwiczy
   się na aktualnym hexie).
C) _require_gm_plan_before_narrative_llm honoruje source_template_id (kampanie z Kuźni).
"""
import json
import sys
import sqlite3

sys.path.insert(0, "/app")


def _make_db():
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.executescript("""
        CREATE TABLE campaigns (
            id INTEGER PRIMARY KEY, owner_user_id INTEGER,
            source_template_id INTEGER, template_id INTEGER,
            party_hex_q INTEGER, party_hex_r INTEGER
        );
        CREATE TABLE campaign_templates (
            id INTEGER PRIMARY KEY, start_hex_q INTEGER, start_hex_r INTEGER
        );
        CREATE TABLE world_hexes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            q INTEGER, r INTEGER, hex_type TEXT DEFAULT 'plains', label TEXT,
            map_level INTEGER DEFAULT 0, is_active INTEGER DEFAULT 1,
            location_key TEXT, encounter_chance REAL DEFAULT 0,
            encounter_pool TEXT DEFAULT '[]', created_by_gm INTEGER DEFAULT 0,
            created_by_campaign_id INTEGER, discovered_in_campaign_id INTEGER
        );
        CREATE TABLE campaign_hex_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER, hex_q INTEGER, hex_r INTEGER,
            campaign_label TEXT, discovered INTEGER DEFAULT 0,
            UNIQUE(campaign_id, hex_q, hex_r)
        );
        CREATE TABLE game_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER, session_flags TEXT DEFAULT '{}',
            current_location_id INTEGER,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE game_locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT, label TEXT, description TEXT,
            parent_id INTEGER, parent_key TEXT, location_type TEXT,
            world_hex_q INTEGER, world_hex_r INTEGER,
            canonical INTEGER DEFAULT 0, is_active INTEGER DEFAULT 1,
            review_status TEXT DEFAULT 'permanent', safe_for_rest INTEGER DEFAULT 0,
            created_by TEXT, approved INTEGER DEFAULT 1, ai_generated INTEGER DEFAULT 0,
            source_campaign_id INTEGER, location_subtype TEXT, biome TEXT,
            created_at TEXT DEFAULT (datetime('now')), updated_at TEXT
        );
        CREATE TABLE characters (
            id INTEGER PRIMARY KEY, campaign_id INTEGER, user_id INTEGER,
            status TEXT DEFAULT 'active', sheet_json TEXT DEFAULT '{}'
        );
    """)
    return db


# ─── Fix A — istniejący hex bez lokacji zostaje NIEzakotwiczony ───────────────

def test_existing_template_hex_without_location_stays_unanchored():
    """Scenariusz kampanii 1000017: hex szablonu = pusty las, wylosowana nazwa
    pasuje do kanonicznej lokacji po drugiej stronie mapy → sesja NIE może
    dostać current_location_id tej lokacji."""
    from app.services.hex_travel_service import resolve_starting_hex
    db = _make_db()
    # template hex: forest, no location on it
    db.execute("INSERT INTO world_hexes (q,r,hex_type) VALUES (38,7,'forest')")
    # far-away canonical location whose name matches the (random) starting name
    db.execute(
        "INSERT INTO game_locations (key,label,world_hex_q,world_hex_r,canonical,location_type) "
        "VALUES ('tundra_mrozu','Tundra Wiecznego Mrozu',0,-31,1,'macro')"
    )
    db.execute("INSERT INTO campaign_templates (id,start_hex_q,start_hex_r) VALUES (141,38,7)")
    db.execute("INSERT INTO campaigns (id,owner_user_id,source_template_id) VALUES (100,1,141)")
    db.execute("INSERT INTO game_sessions (campaign_id, session_flags) VALUES (100,'{}')")
    db.commit()

    res = resolve_starting_hex(100, 999, "Tundra Wiecznego Mrozu", db)

    assert (res["q"], res["r"]) == (38, 7)
    row = db.execute(
        "SELECT current_location_id, session_flags FROM game_sessions WHERE campaign_id=100"
    ).fetchone()
    assert row["current_location_id"] is None, \
        f"Sesja zakotwiczona w odległej lokacji (id={row['current_location_id']}) — rozjazd hex↔lokacja"
    assert json.loads(row["session_flags"])["current_hex"] == {"q": 38, "r": 7}


def test_existing_hex_with_on_hex_location_still_anchors():
    """On-hex lokacja pozostaje jedyną poprawną kotwicą (regresja #992)."""
    from app.services.hex_travel_service import resolve_starting_hex
    db = _make_db()
    db.execute("INSERT INTO world_hexes (q,r,hex_type,location_key) VALUES (5,5,'town','osada_x')")
    db.execute(
        "INSERT INTO game_locations (key,label,world_hex_q,world_hex_r,canonical,location_type) "
        "VALUES ('osada_x','Osada X',5,5,1,'macro')"
    )
    db.execute("INSERT INTO campaign_templates (id,start_hex_q,start_hex_r) VALUES (77,5,5)")
    db.execute("INSERT INTO campaigns (id,owner_user_id,source_template_id) VALUES (100,1,77)")
    db.execute("INSERT INTO game_sessions (campaign_id, session_flags) VALUES (100,'{}')")
    db.commit()

    resolve_starting_hex(100, 999, "Osada X", db)
    row = db.execute("SELECT current_location_id FROM game_sessions WHERE campaign_id=100").fetchone()
    loc = db.execute("SELECT id FROM game_locations WHERE key='osada_x'").fetchone()
    assert row["current_location_id"] == loc["id"]


def test_new_origin_hex_keeps_canonical_fallback():
    """Ścieżka is_new (świeży świat, hex 0,0) zachowuje stare zachowanie."""
    from app.services.hex_travel_service import resolve_starting_hex
    db = _make_db()
    db.execute(
        "INSERT INTO game_locations (key,label,canonical,location_type) "
        "VALUES ('brzezino','Brzezino',1,'macro')"
    )
    db.execute("INSERT INTO campaigns (id,owner_user_id) VALUES (100,1)")
    db.execute("INSERT INTO game_sessions (campaign_id, session_flags) VALUES (100,'{}')")
    db.commit()

    res = resolve_starting_hex(100, 999, "Zupełnie Nowe Miejsce", db)
    assert res["is_new"] is True
    row = db.execute("SELECT current_location_id FROM game_sessions WHERE campaign_id=100").fetchone()
    assert row["current_location_id"] is not None, "is_new: kanoniczny fallback ma nadal kotwiczyć"


# ─── Fix B(1) — describe_start_position ───────────────────────────────────────

def test_describe_start_position_uses_hex_terrain():
    from app.services.location_state_service import describe_start_position
    db = _make_db()
    db.execute("INSERT INTO world_hexes (q,r,hex_type) VALUES (38,7,'forest')")
    db.execute(
        "INSERT INTO game_sessions (campaign_id, session_flags) "
        "VALUES (100,'{\"current_hex\": {\"q\": 38, \"r\": 7}}')"
    )
    db.commit()
    desc = describe_start_position(db, 100)
    assert desc and "las" in desc, f"Opis ma oddawać teren hexa: {desc!r}"
    assert "bez zabudowań" in desc


def test_describe_start_position_prefers_anchored_location():
    from app.services.location_state_service import describe_start_position
    db = _make_db()
    db.execute(
        "INSERT INTO game_locations (id,key,label,location_subtype) "
        "VALUES (9,'karczma_x','Karczma Pod Kołem','tavern')"
    )
    db.execute(
        "INSERT INTO game_sessions (campaign_id, session_flags, current_location_id) "
        "VALUES (100,'{}',9)"
    )
    db.commit()
    desc = describe_start_position(db, 100)
    assert desc == "Karczma Pod Kołem (tavern)"


def test_describe_start_position_none_without_position():
    from app.services.location_state_service import describe_start_position
    db = _make_db()
    db.execute("INSERT INTO game_sessions (campaign_id, session_flags) VALUES (100,'{}')")
    db.commit()
    assert describe_start_position(db, 100) is None


# ─── Fix B(2) — _apply_opening_location_intent ────────────────────────────────

_OPENING_JSON = json.dumps({
    "narrative": "Deszcz bębni o gonty gospody...",
    "location_intent": {
        "action": "create",
        "target_label": "Gospoda Pod Testowym Rogiem",
        "description": "Przydrożna gospoda.",
        "biome": "urban",
        "location_subtype": "tavern",
    },
}, ensure_ascii=False)


def test_opening_intent_creates_and_anchors_location_on_current_hex():
    from app.api.turns import _apply_opening_location_intent
    db = _make_db()
    db.execute("INSERT INTO world_hexes (q,r,hex_type) VALUES (38,7,'forest')")
    db.execute(
        "INSERT INTO game_sessions (campaign_id, session_flags) "
        "VALUES (100,'{\"current_hex\": {\"q\": 38, \"r\": 7}}')"
    )
    db.commit()

    _apply_opening_location_intent(db, 100, _OPENING_JSON)

    loc = db.execute(
        "SELECT * FROM game_locations WHERE label='Gospoda Pod Testowym Rogiem'"
    ).fetchone()
    assert loc is not None, "location_intent(create) z openingu ma tworzyć lokację"
    assert (loc["world_hex_q"], loc["world_hex_r"]) == (38, 7), "lokacja kotwiczy na aktualnym hexie"
    sess = db.execute("SELECT current_location_id FROM game_sessions WHERE campaign_id=100").fetchone()
    assert sess["current_location_id"] == loc["id"]
    wh = db.execute("SELECT location_key FROM world_hexes WHERE q=38 AND r=7").fetchone()
    assert wh["location_key"] == loc["key"]


def test_opening_intent_skips_reused_location_on_other_hex():
    """Reużyta lokacja o tym samym kluczu, zakotwiczona GDZIE INDZIEJ,
    nie może zostać current_location (to byłby ten sam teleport)."""
    from app.api.turns import _apply_opening_location_intent
    db = _make_db()
    db.execute("INSERT INTO world_hexes (q,r,hex_type) VALUES (38,7,'forest')")
    db.execute(
        "INSERT INTO game_locations (key,label,world_hex_q,world_hex_r,location_type) "
        "VALUES ('gospoda_pod_testowym_rogiem','Gospoda Pod Testowym Rogiem',0,22,'macro')"
    )
    db.execute(
        "INSERT INTO game_sessions (campaign_id, session_flags) "
        "VALUES (100,'{\"current_hex\": {\"q\": 38, \"r\": 7}}')"
    )
    db.commit()

    _apply_opening_location_intent(db, 100, _OPENING_JSON)

    sess = db.execute("SELECT current_location_id FROM game_sessions WHERE campaign_id=100").fetchone()
    assert sess["current_location_id"] is None, \
        "Sesja nie może być kotwiczona do lokacji z innego hexa"


def test_opening_intent_noop_without_create_intent():
    from app.api.turns import _apply_opening_location_intent
    db = _make_db()
    db.execute("INSERT INTO game_sessions (campaign_id, session_flags) VALUES (100,'{}')")
    db.commit()
    _apply_opening_location_intent(db, 100, '{"narrative": "Zwykły opis.", "location_intent": null}')
    sess = db.execute("SELECT current_location_id FROM game_sessions WHERE campaign_id=100").fetchone()
    assert sess["current_location_id"] is None
