"""BUG-01 — remove_item JSON signal removes item from character_inventory."""

from _fixtures_schema import table_sql
import json
import sqlite3

import pytest

from app.api.turns import create_turn_log

CAMPAIGN_ID = 99901
CHARACTER_ID = 99901


@pytest.fixture
def db():
    """In-memory SQLite with the tables needed for create_turn_log."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS campaigns (
            id INTEGER PRIMARY KEY,
            character_id INTEGER,
            status TEXT DEFAULT 'active',
            session_flags TEXT DEFAULT '{}'
        );
        CREATE TABLE IF NOT EXISTS characters (
            id INTEGER PRIMARY KEY,
            campaign_id INTEGER,
            name TEXT,
            class TEXT DEFAULT 'warrior',
            level INTEGER DEFAULT 1,
            hp INTEGER DEFAULT 10,
            max_hp INTEGER DEFAULT 10,
            gold_gp INTEGER DEFAULT 0,
            sheet_json TEXT DEFAULT '{}'
        );
        CREATE TABLE IF NOT EXISTS character_inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id INTEGER NOT NULL,
            label TEXT,
            item_key TEXT DEFAULT '__narrative__',
            weapon_key TEXT,
            consumable_key TEXT,
            quantity INTEGER DEFAULT 1,
            equipped INTEGER DEFAULT 0,
            source TEXT DEFAULT 'gm',
            meta_json TEXT DEFAULT '{}'
        );
        CREATE TABLE IF NOT EXISTS campaign_turns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL,
            character_id INTEGER,
            user_text TEXT,
            assistant_text TEXT,
            route TEXT DEFAULT 'narrative',
            turn_number INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now'))
        );
        """ + table_sql("game_config_meta") + """
        CREATE TABLE IF NOT EXISTS npcs (
            id INTEGER PRIMARY KEY,
            key TEXT,
            name TEXT
        );
        CREATE TABLE IF NOT EXISTS campaign_known_npcs (
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
        INSERT INTO campaigns (id, character_id) VALUES (99901, 99901);
        INSERT INTO characters (id, campaign_id) VALUES (99901, 99901);
        """
    )
    yield conn
    conn.close()


def _insert_item(conn, label: str, qty: int = 1) -> int:
    cur = conn.execute(
        "INSERT INTO character_inventory (character_id, label, item_key, quantity) VALUES (?, ?, '__narrative__', ?)",
        (CHARACTER_ID, label, qty),
    )
    conn.commit()
    return cur.lastrowid


def _inventory_labels(conn) -> list[str]:
    rows = conn.execute(
        "SELECT label FROM character_inventory WHERE character_id = ?", (CHARACTER_ID,)
    ).fetchall()
    return [r["label"] for r in rows]


def _make_response(remove_item=None, extra: dict | None = None) -> str:
    payload = {"narrative": "Marta bierze księgę z twoich rąk i kiwa głową z zadowoleniem."}
    if remove_item is not None:
        payload["remove_item"] = remove_item
    if extra:
        payload.update(extra)
    return json.dumps(payload, ensure_ascii=False)


def test_remove_item_deletes_single_qty(db):
    _insert_item(db, "Stara Księga", qty=1)
    create_turn_log(
        db, CAMPAIGN_ID, CHARACTER_ID,
        user_text="Daję księgę Marcie.",
        assistant_text=_make_response({"label": "Stara Księga"}),
        route="narrative",
    )
    assert "Stara Księga" not in _inventory_labels(db)


def test_remove_item_decrements_stack(db):
    _insert_item(db, "Fiolka eliksiru", qty=3)
    create_turn_log(
        db, CAMPAIGN_ID, CHARACTER_ID,
        user_text="Daję fiolkę wiedźmie.",
        assistant_text=_make_response({"label": "Fiolka eliksiru"}),
        route="narrative",
    )
    row = db.execute(
        "SELECT quantity FROM character_inventory WHERE character_id = ? AND label = 'Fiolka eliksiru'",
        (CHARACTER_ID,),
    ).fetchone()
    assert row is not None
    assert int(row["quantity"]) == 2


def test_remove_item_handles_list(db):
    _insert_item(db, "Srebrny klucz")
    _insert_item(db, "Stara Mapa")
    create_turn_log(
        db, CAMPAIGN_ID, CHARACTER_ID,
        user_text="Oddaję klucz i mapę strażnikowi.",
        assistant_text=_make_response([{"label": "Srebrny klucz"}, {"label": "Stara Mapa"}]),
        route="narrative",
    )
    labels = _inventory_labels(db)
    assert "Srebrny klucz" not in labels
    assert "Stara Mapa" not in labels


def test_remove_item_case_insensitive(db):
    _insert_item(db, "Srebrny Klucz")
    create_turn_log(
        db, CAMPAIGN_ID, CHARACTER_ID,
        user_text="Kładę klucz na stole.",
        assistant_text=_make_response({"label": "srebrny klucz"}),
        route="narrative",
    )
    assert "Srebrny Klucz" not in _inventory_labels(db)


def test_remove_item_unknown_label_is_noop(db):
    _insert_item(db, "Miecz")
    create_turn_log(
        db, CAMPAIGN_ID, CHARACTER_ID,
        user_text="Coś robię.",
        assistant_text=_make_response({"label": "Nieistniejący przedmiot"}),
        route="narrative",
    )
    assert "Miecz" in _inventory_labels(db)


def test_remove_item_no_field_leaves_inventory_intact(db):
    _insert_item(db, "Talizman")
    create_turn_log(
        db, CAMPAIGN_ID, CHARACTER_ID,
        user_text="Rozmawiam z Martą.",
        assistant_text=_make_response(),
        route="narrative",
    )
    assert "Talizman" in _inventory_labels(db)


def test_remove_item_skipped_on_combat_route(db):
    _insert_item(db, "Miecz")
    create_turn_log(
        db, CAMPAIGN_ID, CHARACTER_ID,
        user_text="Atakuję!",
        assistant_text=_make_response({"label": "Miecz"}),
        route="combat",
    )
    assert "Miecz" in _inventory_labels(db)


def test_remove_item_skipped_when_no_character(db):
    _insert_item(db, "Miecz")
    create_turn_log(
        db, CAMPAIGN_ID, None,
        user_text="Coś.",
        assistant_text=_make_response({"label": "Miecz"}),
        route="narrative",
    )
    assert "Miecz" in _inventory_labels(db)
