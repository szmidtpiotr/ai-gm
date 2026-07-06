"""TDD: Issue #1206 — szablon Kuźni materializuje lokację startową na start_hexie.

Mechanizm `ensure_template_start_location`:
- brak lokacji → tworzy zakotwiczoną na start_hexie,
- stub własny szablonu (forge + source_campaign_id=template_id) → kotwiczy/przenosi,
- konflikt klucza z obcą lokacją → kopia pod unikalnym kluczem + rewrite planu
  szablonu (i planu kampanii przy launchu),
- idempotencja.
Plus safety net w resolve_starting_hex: kampania z szablonu bez lokacji on-hex
dostaje ją przy starcie (sesja zakotwiczona, koniec dryfu "las zamiast karczmy").
"""
import json
import sys
import sqlite3

sys.path.insert(0, "/app")


_PLAN = {
    "title": "Test",
    "key_locations": [
        {"key": "karczma_testowa", "name": "Karczma Testowa", "role": "Punkt startowy"},
        {"key": "kuznia_testowa", "name": "Kuźnia Testowa", "role": "Stawka"},
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
            gm_plan_json TEXT
        );
        CREATE TABLE campaigns (
            id INTEGER PRIMARY KEY, owner_user_id INTEGER,
            source_template_id INTEGER, template_id INTEGER,
            gm_plan_json TEXT
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
        CREATE TABLE characters (
            id INTEGER PRIMARY KEY, campaign_id INTEGER, user_id INTEGER,
            status TEXT DEFAULT 'active', sheet_json TEXT DEFAULT '{}'
        );
    """)
    return db


def _tpl(db, tid=132, q=38, r=6, plan=None):
    db.execute(
        "INSERT INTO campaign_templates (id, start_hex_q, start_hex_r, gm_plan_json) "
        "VALUES (?,?,?,?)",
        (tid, q, r, json.dumps(plan or _PLAN, ensure_ascii=False)),
    )
    db.commit()


# ─── ensure_template_start_location ───────────────────────────────────────────

def test_creates_anchored_start_location():
    from app.services.template_start_anchor import ensure_template_start_location
    db = _make_db()
    _tpl(db)

    res = ensure_template_start_location(db, 132)

    assert res == {"key": "karczma_testowa", "status": "created", "q": 38, "r": 6}
    row = db.execute("SELECT * FROM game_locations WHERE key='karczma_testowa'").fetchone()
    assert row is not None
    assert (row["world_hex_q"], row["world_hex_r"]) == (38, 6)
    assert row["label"] == "Karczma Testowa"
    assert row["created_by"] == "forge"
    assert row["source_campaign_id"] == 132


def test_anchors_own_unanchored_stub():
    """Stub z _auto_create_forge_locations (#1092) — bez kotwicy — dostaje ją."""
    from app.services.template_start_anchor import ensure_template_start_location
    db = _make_db()
    _tpl(db)
    db.execute(
        "INSERT INTO game_locations (key,label,created_by,source_campaign_id,ai_generated) "
        "VALUES ('karczma_testowa','Karczma Testowa','forge',132,1)"
    )
    db.commit()

    res = ensure_template_start_location(db, 132)

    assert res["status"] == "anchored"
    rows = db.execute("SELECT * FROM game_locations WHERE key='karczma_testowa'").fetchall()
    assert len(rows) == 1, "kotwiczy istniejący stub, nie tworzy duplikatu"
    assert (rows[0]["world_hex_q"], rows[0]["world_hex_r"]) == (38, 6)


def test_idempotent_when_already_anchored():
    from app.services.template_start_anchor import ensure_template_start_location
    db = _make_db()
    _tpl(db)
    assert ensure_template_start_location(db, 132)["status"] == "created"
    res2 = ensure_template_start_location(db, 132)
    assert res2["status"] == "ok"
    assert db.execute(
        "SELECT COUNT(*) FROM game_locations WHERE key='karczma_testowa'"
    ).fetchone()[0] == 1


def test_foreign_key_conflict_copies_and_rewrites_plans():
    """Scenariusz kampanii 1000021: klucz zajęty przez lokację innej kampanii
    zakotwiczoną gdzie indziej → kopia pod unikalnym kluczem, plan szablonu
    i plan kampanii przepisane, obca lokacja nietknięta."""
    from app.services.template_start_anchor import ensure_template_start_location
    db = _make_db()
    _tpl(db)
    db.execute(
        "INSERT INTO game_locations (key,label,world_hex_q,world_hex_r,created_by,source_campaign_id) "
        "VALUES ('karczma_testowa','Karczma Testowa',28,-49,'manual_fix_1092',999986)"
    )
    db.execute(
        "INSERT INTO campaigns (id,owner_user_id,source_template_id,gm_plan_json) "
        "VALUES (100,1,132,?)", (json.dumps(_PLAN, ensure_ascii=False),)
    )
    db.commit()

    res = ensure_template_start_location(db, 132, campaign_id=100)

    assert res["status"] == "copied"
    assert res["key"] != "karczma_testowa"
    # foreign row untouched
    foreign = db.execute(
        "SELECT world_hex_q, world_hex_r FROM game_locations WHERE key='karczma_testowa'"
    ).fetchone()
    assert (foreign["world_hex_q"], foreign["world_hex_r"]) == (28, -49)
    # copy anchored on template hex
    copy = db.execute(
        "SELECT world_hex_q, world_hex_r FROM game_locations WHERE key=?", (res["key"],)
    ).fetchone()
    assert (copy["world_hex_q"], copy["world_hex_r"]) == (38, 6)
    # both plans rewritten to the new key
    for table, row_id in (("campaign_templates", 132), ("campaigns", 100)):
        plan = json.loads(db.execute(
            f"SELECT gm_plan_json FROM {table} WHERE id=?", (row_id,)
        ).fetchone()["gm_plan_json"])
        assert plan["acts"][0]["key_beats"][0]["objective_value"] == res["key"]
        assert plan["key_locations"][0]["key"] == res["key"]
        # unrelated references untouched
        assert plan["acts"][0]["key_beats"][1]["objective_value"] == "npc_x"
        assert plan["key_locations"][1]["key"] == "kuznia_testowa"


def test_none_without_start_hex_or_plan():
    from app.services.template_start_anchor import ensure_template_start_location
    db = _make_db()
    db.execute("INSERT INTO campaign_templates (id) VALUES (7)")
    db.commit()
    assert ensure_template_start_location(db, 7) is None
    assert ensure_template_start_location(db, 999) is None


def test_fallback_to_first_key_location_without_visit_beat():
    from app.services.template_start_anchor import ensure_template_start_location
    db = _make_db()
    plan = {
        "key_locations": [{"key": "oboz_x", "name": "Obóz X"}],
        "acts": [{"number": 1, "key_beats": [
            {"beat_key": "b1", "objective_type": "talk_to_npc", "objective_value": "npc"}
        ]}],
    }
    _tpl(db, tid=50, q=10, r=-4, plan=plan)
    res = ensure_template_start_location(db, 50)
    assert res["key"] == "oboz_x"
    assert res["status"] == "created"


# ─── safety net w resolve_starting_hex ────────────────────────────────────────

def test_launch_safety_net_anchors_session_to_start_location():
    """Szablon opublikowany PRZED fixem (goły hex) → launch materializuje lokację
    i kotwiczy sesję. Koniec narracji o drzewach w karczmie."""
    from app.services.hex_travel_service import resolve_starting_hex
    db = _make_db()
    db.execute("INSERT INTO world_hexes (q,r,hex_type) VALUES (38,6,'forest')")
    _tpl(db)
    db.execute(
        "INSERT INTO campaigns (id,owner_user_id,source_template_id,gm_plan_json) "
        "VALUES (100,1,132,?)", (json.dumps(_PLAN, ensure_ascii=False),)
    )
    db.execute("INSERT INTO game_sessions (campaign_id, session_flags) VALUES (100,'{}')")
    db.commit()

    res = resolve_starting_hex(100, 999, "Karczma Testowa", db)

    assert (res["q"], res["r"]) == (38, 6)
    loc = db.execute("SELECT id FROM game_locations WHERE key='karczma_testowa'").fetchone()
    assert loc is not None, "safety net ma zmaterializować lokację startową"
    sess = db.execute(
        "SELECT current_location_id FROM game_sessions WHERE campaign_id=100"
    ).fetchone()
    assert sess["current_location_id"] == loc["id"], "sesja zakotwiczona w lokacji startowej"


def test_non_template_campaign_keeps_unanchored_rule():
    """Kampania BEZ szablonu na istniejącym pustym hexie — reguła #1152 bez zmian."""
    from app.services.hex_travel_service import resolve_starting_hex
    db = _make_db()
    db.execute("INSERT INTO world_hexes (q,r,hex_type,label) VALUES (5,5,'forest','Bór')")
    db.execute("INSERT INTO campaigns (id,owner_user_id) VALUES (100,1)")
    db.execute("INSERT INTO game_sessions (campaign_id, session_flags) VALUES (100,'{}')")
    db.commit()

    resolve_starting_hex(100, 999, "Bór", db)

    sess = db.execute(
        "SELECT current_location_id FROM game_sessions WHERE campaign_id=100"
    ).fetchone()
    assert sess["current_location_id"] is None
