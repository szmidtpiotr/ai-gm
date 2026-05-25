"""BUG-04 — gm_note / scene_advance / gm_plan_update hooks in create_turn_log."""

import json
import sqlite3

import pytest

from app.api.turns import create_turn_log
from app.services.gm_plan_schema import normalize_gm_plan

CAMPAIGN_ID = 99904
CHARACTER_ID = 99904

_INITIAL_PLAN = json.dumps({
    "schema_version": 2,
    "arcs": {
        "default": {
            "id": "default",
            "title": "Test Arc",
            "status": "active",
            "roadmap": "Gracz szuka zaginionego maga.",
            "scene_goals": ["Znajdź mapę do ruin", "Porozmawiaj z Martą"],
            "hooks": {},
            "current_scene_ordinal": 0,
        }
    },
    "active_arc_id": "default",
    "engine_private": {"last_plan_updated_turn": 0},
})


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(f"""
        CREATE TABLE campaigns (
            id INTEGER PRIMARY KEY,
            character_id INTEGER,
            status TEXT DEFAULT 'active',
            gm_plan_json TEXT DEFAULT '{{}}'
        );
        CREATE TABLE characters (
            id INTEGER PRIMARY KEY,
            campaign_id INTEGER,
            name TEXT,
            class TEXT DEFAULT 'warrior',
            level INTEGER DEFAULT 1,
            hp INTEGER DEFAULT 10,
            max_hp INTEGER DEFAULT 10,
            gold_gp INTEGER DEFAULT 0,
            sheet_json TEXT DEFAULT '{{}}'
        );
        CREATE TABLE character_inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id INTEGER NOT NULL,
            label TEXT,
            item_key TEXT DEFAULT '__narrative__',
            weapon_key TEXT,
            consumable_key TEXT,
            quantity INTEGER DEFAULT 1,
            equipped INTEGER DEFAULT 0,
            source TEXT DEFAULT 'gm',
            meta_json TEXT DEFAULT '{{}}'
        );
        CREATE TABLE campaign_turns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL,
            character_id INTEGER,
            user_text TEXT,
            assistant_text TEXT,
            route TEXT DEFAULT 'narrative',
            turn_number INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE game_config_meta (key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE npcs (id INTEGER PRIMARY KEY, key TEXT, name TEXT);
        CREATE TABLE campaign_known_npcs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL,
            npc_id INTEGER,
            npc_name TEXT NOT NULL,
            role TEXT,
            first_met_location TEXT,
            first_met_turn INTEGER,
            notes TEXT,
            relation_status TEXT DEFAULT 'neutral',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            UNIQUE(campaign_id, npc_name)
        );
        INSERT INTO campaigns (id, character_id, gm_plan_json) VALUES ({CAMPAIGN_ID}, {CHARACTER_ID}, '{_INITIAL_PLAN}');
        INSERT INTO characters (id, campaign_id) VALUES ({CHARACTER_ID}, {CAMPAIGN_ID});
    """)
    yield conn
    conn.close()


def _get_plan(conn) -> dict:
    row = conn.execute("SELECT gm_plan_json FROM campaigns WHERE id = ?", (CAMPAIGN_ID,)).fetchone()
    return normalize_gm_plan(row["gm_plan_json"])


def _response(**kwargs) -> str:
    payload = {"narrative": "Test narracja.", **kwargs}
    return json.dumps(payload, ensure_ascii=False)


def test_gm_note_stored_in_buffer(db):
    create_turn_log(db, CAMPAIGN_ID, CHARACTER_ID,
                    user_text="Idę dalej.",
                    assistant_text=_response(gm_note="Gracz zbliża się do ruin"),
                    route="narrative")
    plan = _get_plan(db)
    buf = plan["engine_private"].get("gm_note_buffer", [])
    assert len(buf) == 1
    assert buf[0]["note"] == "Gracz zbliża się do ruin"
    assert buf[0]["turn"] == 1


def test_gm_note_buffer_rolls_off_at_30(db):
    for i in range(35):
        create_turn_log(db, CAMPAIGN_ID, CHARACTER_ID,
                        user_text="Akcja",
                        assistant_text=_response(gm_note=f"Notatka {i}"),
                        route="narrative")
    plan = _get_plan(db)
    buf = plan["engine_private"].get("gm_note_buffer", [])
    assert len(buf) == 30
    assert buf[-1]["note"] == "Notatka 34"


def test_scene_advance_increments_ordinal(db):
    create_turn_log(db, CAMPAIGN_ID, CHARACTER_ID,
                    user_text="Koniec sceny.",
                    assistant_text=_response(scene_advance=True),
                    route="narrative")
    plan = _get_plan(db)
    assert plan["arcs"]["default"]["current_scene_ordinal"] == 1


def test_gm_plan_update_appends_roadmap_note(db):
    create_turn_log(db, CAMPAIGN_ID, CHARACTER_ID,
                    user_text="Akcja.",
                    assistant_text=_response(gm_plan_update={"roadmap_note": "Gracz znalazł mapę!"}),
                    route="narrative")
    plan = _get_plan(db)
    assert "Gracz znalazł mapę!" in plan["arcs"]["default"]["roadmap"]


def test_gm_plan_update_removes_done_goals(db):
    create_turn_log(db, CAMPAIGN_ID, CHARACTER_ID,
                    user_text="Akcja.",
                    assistant_text=_response(gm_plan_update={"scene_goals_done": ["Znajdź mapę do ruin"]}),
                    route="narrative")
    plan = _get_plan(db)
    goals = plan["arcs"]["default"]["scene_goals"]
    assert not any("mapę do ruin" in g.lower() for g in goals)
    assert any("Martą" in g for g in goals)


def test_gm_plan_update_adds_new_goals(db):
    create_turn_log(db, CAMPAIGN_ID, CHARACTER_ID,
                    user_text="Akcja.",
                    assistant_text=_response(gm_plan_update={"scene_goals_add": ["Wejdź do ruin"]}),
                    route="narrative")
    plan = _get_plan(db)
    assert "Wejdź do ruin" in plan["arcs"]["default"]["scene_goals"]


def test_gm_plan_update_sets_last_updated_turn(db):
    create_turn_log(db, CAMPAIGN_ID, CHARACTER_ID,
                    user_text="Akcja.",
                    assistant_text=_response(gm_plan_update={"roadmap_note": "zmiana"}),
                    route="narrative")
    plan = _get_plan(db)
    assert plan["engine_private"]["last_plan_updated_turn"] == 1


def test_no_plan_fields_leaves_plan_intact(db):
    plan_before = _get_plan(db)
    create_turn_log(db, CAMPAIGN_ID, CHARACTER_ID,
                    user_text="Akcja.",
                    assistant_text=_response(),
                    route="narrative")
    plan_after = _get_plan(db)
    assert plan_before["arcs"]["default"]["scene_goals"] == plan_after["arcs"]["default"]["scene_goals"]


def test_plan_hook_skipped_on_combat(db):
    create_turn_log(db, CAMPAIGN_ID, CHARACTER_ID,
                    user_text="Atakuję.",
                    assistant_text=_response(gm_note="Walka", scene_advance=True),
                    route="combat")
    plan = _get_plan(db)
    assert not plan["engine_private"].get("gm_note_buffer")
    assert plan["arcs"]["default"]["current_scene_ordinal"] == 0
