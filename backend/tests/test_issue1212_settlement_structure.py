"""TDD: Issue #1212 — szablon deklaruje strukturę osady (hub + sublokacje).

key_locations dostaje scale: hub|sub|standalone + parent. Materializacja:
hub zakotwiczony na start_hexie, suby z parent_key na mapie lokalnej FAZA ML
(map_level=1) budowanej OD RAZU. Sesja startuje wewnątrz suba startowego,
beat visit_location lokacji startowej zaliczony na spawnie.
"""
import json
import sys
import sqlite3

sys.path.insert(0, "/app")


_PLAN = {
    "title": "Test",
    "start_hour": 19,
    "key_locations": [
        {"key": "wies_testowa", "name": "Wieś Testowa", "scale": "hub",
         "description": "Zabłocona osada przy trakcie."},
        {"key": "karczma_testowa", "name": "Karczma Testowa", "scale": "sub",
         "parent": "wies_testowa", "description": "Zadymiona izba."},
        {"key": "kuznia_testowa", "name": "Kuźnia Testowa", "scale": "sub",
         "parent": "wies_testowa", "description": "Warsztat kowala."},
    ],
    "acts": [
        {
            "number": 1,
            "key_beats": [
                {"beat_key": "przybycie", "objective_type": "visit_location",
                 "objective_value": "karczma_testowa", "optional": False},
                {"beat_key": "rozmowa", "objective_type": "talk_to_npc",
                 "objective_value": "npc_x", "optional": False},
            ],
        }
    ],
}


def _make_db():
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.executescript("""
        CREATE TABLE campaign_templates (
            id INTEGER PRIMARY KEY, start_hex_q INTEGER, start_hex_r INTEGER,
            gm_plan_json TEXT, required_npc_keys TEXT, required_beats TEXT
        );
        CREATE TABLE campaigns (
            id INTEGER PRIMARY KEY, owner_user_id INTEGER,
            source_template_id INTEGER, template_id INTEGER, gm_plan_json TEXT
        );
        CREATE TABLE game_locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT, label TEXT, description TEXT,
            parent_id INTEGER, parent_key TEXT, location_type TEXT DEFAULT 'macro',
            location_subtype TEXT, biome TEXT,
            world_hex_q INTEGER, world_hex_r INTEGER,
            canonical INTEGER DEFAULT 0, is_active INTEGER DEFAULT 1,
            review_status TEXT DEFAULT 'permanent', safe_for_rest INTEGER DEFAULT 0,
            created_by TEXT, approved INTEGER DEFAULT 1, ai_generated INTEGER DEFAULT 0,
            source_campaign_id INTEGER,
            created_at TEXT DEFAULT (datetime('now')), updated_at TEXT
        );
        CREATE TABLE world_hexes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            q INTEGER, r INTEGER, hex_type TEXT DEFAULT 'plains', label TEXT,
            map_level INTEGER DEFAULT 0, is_active INTEGER DEFAULT 1,
            location_key TEXT, encounter_chance REAL DEFAULT 0,
            encounter_pool TEXT DEFAULT '[]', created_by_gm INTEGER DEFAULT 0,
            created_by_campaign_id INTEGER, discovered_in_campaign_id INTEGER,
            parent_hex_id INTEGER, region TEXT
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
            current_location_id INTEGER, ingame_hours INTEGER DEFAULT 9,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE characters (
            id INTEGER PRIMARY KEY, campaign_id INTEGER, user_id INTEGER,
            status TEXT DEFAULT 'active', sheet_json TEXT DEFAULT '{}'
        );
        CREATE TABLE npcs (
            id INTEGER PRIMARY KEY AUTOINCREMENT, key TEXT, is_active INTEGER DEFAULT 1
        );
    """)
    return db


def _tpl(db, tid=132, q=38, r=6, plan=None):
    db.execute(
        "INSERT INTO campaign_templates (id, start_hex_q, start_hex_r, gm_plan_json) "
        "VALUES (?,?,?,?)",
        (tid, q, r, json.dumps(plan or _PLAN, ensure_ascii=False)),
    )
    db.execute("INSERT INTO world_hexes (q,r,hex_type,region) VALUES (?,?,'forest','kresy')", (q, r))
    db.commit()


# ─── ensure_template_location_structure ───────────────────────────────────────

def test_materializes_hub_and_subs_with_local_map():
    from app.services.template_start_anchor import ensure_template_location_structure
    db = _make_db()
    _tpl(db)

    res = ensure_template_location_structure(db, 132)

    assert res["hub_key"] == "wies_testowa"
    assert res["start_key"] == "karczma_testowa"
    assert set(res["sub_keys"]) == {"karczma_testowa", "kuznia_testowa"}

    hub = db.execute("SELECT * FROM game_locations WHERE key='wies_testowa'").fetchone()
    assert (hub["world_hex_q"], hub["world_hex_r"]) == (38, 6)
    assert hub["location_type"] == "macro"

    for sk in ("karczma_testowa", "kuznia_testowa"):
        sub = db.execute("SELECT * FROM game_locations WHERE key=?", (sk,)).fetchone()
        assert sub["location_type"] == "sub"
        assert sub["parent_key"] == "wies_testowa"
        assert sub["world_hex_q"] is None, "sub żyje na mapie lokalnej, nie na mapie świata"

    local = db.execute(
        "SELECT location_key FROM world_hexes WHERE map_level=1 AND is_active=1"
    ).fetchall()
    assert {l["location_key"] for l in local} == {"karczma_testowa", "kuznia_testowa"}, \
        "mapa lokalna FAZA ML zbudowana od razu"


def test_restructures_existing_anchored_start_location():
    """Rekord z ery #1206: karczma-macro zakotwiczona na start_hexie → sub bez kotwicy."""
    from app.services.template_start_anchor import ensure_template_location_structure
    db = _make_db()
    _tpl(db)
    db.execute(
        "INSERT INTO game_locations (key,label,location_type,world_hex_q,world_hex_r,created_by) "
        "VALUES ('karczma_testowa','Karczma Testowa','macro',38,6,'manual_fix_1092')"
    )
    db.commit()

    ensure_template_location_structure(db, 132)

    rows = db.execute("SELECT * FROM game_locations WHERE key='karczma_testowa'").fetchall()
    assert len(rows) == 1, "restrukturyzacja, nie duplikat"
    assert rows[0]["location_type"] == "sub"
    assert rows[0]["parent_key"] == "wies_testowa"
    assert rows[0]["world_hex_q"] is None


def test_foreign_key_conflict_copies_and_rewrites():
    from app.services.template_start_anchor import ensure_template_location_structure
    db = _make_db()
    _tpl(db)
    db.execute(
        "INSERT INTO game_locations (key,label,world_hex_q,world_hex_r,created_by,source_campaign_id) "
        "VALUES ('karczma_testowa','Obca Karczma',5,-9,'gm_runtime',777)"
    )
    db.execute(
        "INSERT INTO campaigns (id,owner_user_id,source_template_id,gm_plan_json) "
        "VALUES (100,1,132,?)", (json.dumps(_PLAN, ensure_ascii=False),)
    )
    db.commit()

    res = ensure_template_location_structure(db, 132, campaign_id=100)

    assert res["start_key"] != "karczma_testowa"
    foreign = db.execute(
        "SELECT world_hex_q, world_hex_r, location_type FROM game_locations WHERE key='karczma_testowa'"
    ).fetchone()
    assert (foreign["world_hex_q"], foreign["world_hex_r"]) == (5, -9), "obca lokacja nietknięta"
    for table, rid in (("campaign_templates", 132), ("campaigns", 100)):
        plan = json.loads(db.execute(
            f"SELECT gm_plan_json FROM {table} WHERE id=?", (rid,)
        ).fetchone()["gm_plan_json"])
        assert plan["acts"][0]["key_beats"][0]["objective_value"] == res["start_key"]


def test_flat_plan_falls_back_to_single_anchor():
    from app.services.template_start_anchor import ensure_template_locations
    db = _make_db()
    flat = {
        "key_locations": [{"key": "oboz_x", "name": "Obóz X"}],
        "acts": [{"number": 1, "key_beats": []}],
    }
    _tpl(db, tid=50, q=10, r=-4, plan=flat)
    res = ensure_template_locations(db, 50)
    assert res["status"] == "created"
    assert res["key"] == "oboz_x"
    row = db.execute("SELECT world_hex_q, world_hex_r FROM game_locations WHERE key='oboz_x'").fetchone()
    assert (row["world_hex_q"], row["world_hex_r"]) == (10, -4)


# ─── launch e2e przez resolve_starting_hex ────────────────────────────────────

def test_launch_starts_inside_start_sub_with_local_hex_and_beat():
    from app.services.hex_travel_service import resolve_starting_hex
    db = _make_db()
    _tpl(db)
    db.execute(
        "INSERT INTO campaigns (id,owner_user_id,source_template_id,gm_plan_json) "
        "VALUES (100,1,132,?)", (json.dumps(_PLAN, ensure_ascii=False),)
    )
    db.execute("INSERT INTO game_sessions (campaign_id, session_flags) VALUES (100,'{}')")
    db.commit()

    res = resolve_starting_hex(100, 999, "Karczma Testowa", db)
    assert (res["q"], res["r"]) == (38, 6)

    sess = db.execute(
        "SELECT current_location_id, session_flags FROM game_sessions WHERE campaign_id=100"
    ).fetchone()
    karczma = db.execute("SELECT id FROM game_locations WHERE key='karczma_testowa'").fetchone()
    assert sess["current_location_id"] == karczma["id"], "start WEWNĄTRZ suba, nie w hubie"

    flags = json.loads(sess["session_flags"])
    assert flags.get("local_hex", {}).get("location_key") == "karczma_testowa", \
        "pozycja na mapie lokalnej ustawiona od startu"
    assert flags.get("ingame_hours") == 19, "start_hour z planu zastosowany"

    plan = json.loads(db.execute(
        "SELECT gm_plan_json FROM campaigns WHERE id=100"
    ).fetchone()["gm_plan_json"])
    beats = {b["beat_key"]: b for b in plan["acts"][0]["key_beats"]}
    assert beats["przybycie"].get("visited") is True, "spawn w karczmie zalicza beat przybycia"
    assert not beats["rozmowa"].get("visited")


# ─── Kuźnia: stuby + walidacja publish ────────────────────────────────────────

def test_forge_stubs_honor_scale_and_parent():
    from app.routers.adventure_forge import _auto_create_forge_locations
    db = _make_db()
    created = _auto_create_forge_locations(db, 99, _PLAN["key_locations"])
    assert {c["key"] for c in created} == {"wies_testowa", "karczma_testowa", "kuznia_testowa"}
    hub = db.execute("SELECT location_type, parent_key FROM game_locations WHERE key='wies_testowa'").fetchone()
    assert hub["location_type"] == "macro" and hub["parent_key"] is None
    sub = db.execute("SELECT location_type, parent_key FROM game_locations WHERE key='kuznia_testowa'").fetchone()
    assert sub["location_type"] == "sub" and sub["parent_key"] == "wies_testowa"


def test_validate_publish_rejects_sub_without_hub():
    from app.routers.adventure_forge import validate_template_publish
    db = _make_db()
    bad = json.loads(json.dumps(_PLAN))
    bad["key_locations"] = [l for l in bad["key_locations"] if l.get("scale") != "hub"]
    _tpl(db, tid=60, plan=bad)
    vres = validate_template_publish(60, db)
    assert vres["ok"] is False
    assert vres["structure_errors"], "sub bez huba musi blokować publish"


def test_validate_publish_accepts_legacy_flat_plan():
    from app.routers.adventure_forge import validate_template_publish
    db = _make_db()
    flat = {"key_locations": [{"key": "a"}, {"key": "b"}], "acts": []}
    _tpl(db, tid=61, plan=flat)
    vres = validate_template_publish(61, db)
    assert vres["structure_errors"] == []
