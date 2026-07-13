"""TDD: Issue #1375 (BL-E1) — receptury jako drop lootu + pule availability.

Pokrywa (backend):
  A. Migracja `_ensure_recipe_loot_schema`: availability + set_key na recipes
     (backfill z is_hidden), source na character_recipes, 4-way XOR recipe_key na
     loot_entries, zwoje-duplikaty, seed pilotu Wilczego Łowcy.
  B. Drop receptury: pierwszy raz = nauka (character_recipes, source='loot', NIE do
     plecaka); duplikat = sprzedawalny „Zbędny zwój receptury" do plecaka.
  C. Wykonanie: self craft receptury lootowej wymaga trade_craft≥1; usługa u
     rzemieślnika bez skilla, koszt ×1.5; nieznana receptura = 403.
  D. Lista receptur: grupowanie po secie, licznik nieodkrytych, liczniki komponentów.
"""
import json
import os
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from _fixtures_schema import table_sql

from app.migrations_admin import (  # noqa: E402
    _ensure_recipe_loot_schema,
    _upgrade_loot_entries_four_way_xor,
)
from app.services import crafting_service as cs  # noqa: E402
from app.services import loot_service as ls  # noqa: E402


# ── Pre-#1375 schemat (3-way loot XOR, recipes bez availability/set_key) ──────
def _build_pre_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE characters (
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
            race TEXT DEFAULT 'human', gold_gp INTEGER NOT NULL DEFAULT 0,
            campaign_id INTEGER, sheet_json TEXT NOT NULL DEFAULT '{}'
        );
        CREATE TABLE character_inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT, character_id INTEGER NOT NULL,
            item_key TEXT, weapon_key TEXT, consumable_key TEXT,
            quantity INTEGER NOT NULL DEFAULT 1, equipped INTEGER NOT NULL DEFAULT 0,
            slot TEXT, source TEXT, meta_json TEXT, game_item_key TEXT,
            affixes_json TEXT, durability_current INTEGER, durability_max INTEGER
        );
        CREATE TABLE game_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT, key TEXT UNIQUE NOT NULL,
            kind TEXT NOT NULL CHECK(kind IN ('weapon','armor','item','consumable')),
            label TEXT NOT NULL DEFAULT '', description TEXT DEFAULT '',
            price_gp REAL DEFAULT 0, created_by TEXT DEFAULT 'seed',
            approved INTEGER DEFAULT 1, is_active INTEGER DEFAULT 1
        );
        """ + table_sql("game_config_recipes") + """
        CREATE TABLE character_recipes (
            id INTEGER PRIMARY KEY AUTOINCREMENT, character_id INTEGER NOT NULL,
            recipe_key TEXT NOT NULL,
            discovered_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE (character_id, recipe_key)
        );
        """ + table_sql("game_config_sets") + """
        """ + table_sql("game_config_loot_tables") + """
        """ + table_sql("game_config_loot_entries") + """
        """ + table_sql("game_config_enemies") + """
        """ + table_sql("game_config_weapons") + """
        """ + table_sql("game_config_consumables") + """
        """ + table_sql("game_config_items") + """

        -- Wróg + tabela tieru standard (na nią seed dokłada receptury lootowe).
        INSERT INTO game_config_loot_tables (key, label) VALUES ('loot_tier_standard', 'Tier standard');
        INSERT INTO game_config_enemies (key, loot_table_key, drop_chance, tier)
            VALUES ('wilk', 'loot_tier_standard', 1.0, 'standard');

        -- Komponenty (game_items) do craftu pilotu.
        INSERT INTO game_items (key, kind, label) VALUES
            ('wolf_pelt', 'item', 'Skóra wilka'),
            ('kiel_wilczy', 'item', 'Kieł wilczy'),
            ('ruda_zelaza', 'item', 'Ruda żelaza'),
            ('wolf_hide_cloak', 'armor', 'Płaszcz z wilczej skóry'),
            ('wolf_fang_dagger', 'weapon', 'Sztylet z wilczego kła'),
            ('wolf_totem_charm', 'item', 'Totem wilczego ducha');

        -- Recepta jawna (crafter) + ukryta (experiment) do testu backfillu availability.
        INSERT INTO game_config_recipes (key, label, is_hidden, craft_tier) VALUES
            ('pub_recipe', 'Publiczna', 0, 'easy'),
            ('hid_recipe', 'Ukryta', 1, 'hard');
        -- Set wolf_hunter (definicja, by lista miała etykietę).
        INSERT INTO game_config_sets (key, label) VALUES ('wolf_hunter', 'Strój Wilczego Łowcy');

        INSERT INTO characters (id, name, race, gold_gp, sheet_json)
            VALUES (1, 'Hero', 'human', 500, '{"skills":{"trade_craft":2},"current_hp":20}');
        INSERT INTO characters (id, name, race, gold_gp, sheet_json)
            VALUES (2, 'Nowicjusz', 'human', 500, '{"skills":{},"current_hp":20}');
        """
    )
    conn.commit()


@pytest.fixture()
def db(tmp_path, monkeypatch):
    p = tmp_path / "t1375.db"
    conn = sqlite3.connect(str(p))
    conn.row_factory = sqlite3.Row
    _build_pre_schema(conn)
    _ensure_recipe_loot_schema(conn)  # migracja pod test
    conn.commit()
    conn.close()
    monkeypatch.setattr(ls, "LOOT_DB_PATH", str(p))
    monkeypatch.setattr(cs, "DB_PATH", str(p))
    return str(p)


def _conn(db):
    c = sqlite3.connect(db)
    c.row_factory = sqlite3.Row
    return c


# ── A. Migracja ──────────────────────────────────────────────────────────────
def test_recipes_gain_availability_and_set_key(db):
    c = _conn(db)
    cols = {r[1] for r in c.execute("PRAGMA table_info(game_config_recipes)")}
    assert {"availability", "set_key"} <= cols
    rows = {r["key"]: r["availability"] for r in c.execute(
        "SELECT key, availability FROM game_config_recipes")}
    assert rows["pub_recipe"] == "crafter"      # is_hidden=0 → crafter
    assert rows["hid_recipe"] == "experiment"   # is_hidden=1 → experiment
    c.close()


def test_character_recipes_gain_source_backfilled(db):
    c = _conn(db)
    cols = {r[1] for r in c.execute("PRAGMA table_info(character_recipes)")}
    assert "source" in cols
    c.close()


def test_loot_entries_four_way_xor(db):
    c = _conn(db)
    cols = {r[1] for r in c.execute("PRAGMA table_info(game_config_loot_entries)")}
    assert "recipe_key" in cols
    # recipe-only entry OK
    c.execute("INSERT INTO game_config_loot_tables (key, label) VALUES ('t2','t2')")
    c.execute("INSERT INTO game_config_loot_entries (loot_table_key, recipe_key) VALUES ('t2','recipe_wolf_fang_dagger')")
    # dwa klucze naraz → CHECK odrzuca
    with pytest.raises(sqlite3.IntegrityError):
        c.execute("INSERT INTO game_config_loot_entries (loot_table_key, item_key, recipe_key) "
                  "VALUES ('t2','wolf_pelt','recipe_wolf_fang_dagger')")
    c.close()


def test_pilot_loot_recipes_seeded(db):
    c = _conn(db)
    rows = c.execute(
        "SELECT key, availability, set_key FROM game_config_recipes WHERE availability='loot'"
    ).fetchall()
    assert len(rows) >= 3
    assert all(r["set_key"] == "wolf_hunter" for r in rows)
    # wpisy lootowe na tabeli tieru standard
    n = c.execute("SELECT COUNT(*) AS n FROM game_config_loot_entries "
                  "WHERE loot_table_key='loot_tier_standard' AND recipe_key IS NOT NULL").fetchone()["n"]
    assert n >= 3
    c.close()


def test_spare_scrolls_seeded(db):
    c = _conn(db)
    keys = {r["key"] for r in c.execute(
        "SELECT key FROM game_items WHERE key LIKE 'spare_recipe_scroll_%'")}
    assert keys == {"spare_recipe_scroll_easy", "spare_recipe_scroll_medium", "spare_recipe_scroll_hard"}
    c.close()


# ── B. Drop receptury: nauka / duplikat ──────────────────────────────────────
def test_recipe_drop_first_time_learns_not_backpack(db):
    granted = ls.grant_loot_to_character(1, [{"recipe_key": "recipe_wolf_fang_dagger", "quantity": 1}])
    assert granted and granted[0]["item_type"] == "recipe"
    assert granted[0].get("recipe_learned") is True
    c = _conn(db)
    known = c.execute("SELECT source FROM character_recipes WHERE character_id=1 AND recipe_key=?",
                      ("recipe_wolf_fang_dagger",)).fetchone()
    assert known is not None and known["source"] == "loot"
    # NIE trafiła do plecaka
    inv = c.execute("SELECT COUNT(*) AS n FROM character_inventory WHERE character_id=1").fetchone()["n"]
    assert inv == 0
    c.close()


def test_recipe_drop_duplicate_yields_scroll(db):
    ls.grant_loot_to_character(1, [{"recipe_key": "recipe_wolf_fang_dagger", "quantity": 1}])
    granted = ls.grant_loot_to_character(1, [{"recipe_key": "recipe_wolf_fang_dagger", "quantity": 1}])
    assert granted and granted[0]["recipe_duplicate_of"] == "recipe_wolf_fang_dagger"
    c = _conn(db)
    row = c.execute("SELECT item_key, quantity FROM character_inventory WHERE character_id=1").fetchone()
    assert row is not None and row["item_key"].startswith("spare_recipe_scroll_")
    c.close()


# ── C. Wykonanie: self vs usługa ─────────────────────────────────────────────
def _give(db, char_id, item_key, qty):
    c = _conn(db)
    c.execute("INSERT INTO character_inventory (character_id, item_key, quantity) VALUES (?,?,?)",
              (char_id, item_key, qty))
    c.commit(); c.close()


def test_unknown_loot_recipe_cannot_craft(db):
    _give(db, 1, "kiel_wilczy", 2); _give(db, 1, "ruda_zelaza", 1)
    with pytest.raises(cs.CraftError) as e:
        cs.craft(1, "recipe_wolf_fang_dagger", mode="self")
    assert e.value.status_code == 403


def test_self_craft_loot_requires_trade_craft(db):
    # Nowicjusz (char 2) zna recepturę, ale trade_craft=0 → 403 w self.
    c = _conn(db)
    c.execute("INSERT INTO character_recipes (character_id, recipe_key, source) VALUES (2,?, 'loot')",
              ("recipe_wolf_fang_dagger",)); c.commit(); c.close()
    _give(db, 2, "kiel_wilczy", 2); _give(db, 2, "ruda_zelaza", 1)
    with pytest.raises(cs.CraftError) as e:
        cs.craft(2, "recipe_wolf_fang_dagger", mode="self")
    assert e.value.status_code == 403


def test_self_craft_loot_ok_with_skill_grants_weapon(db):
    c = _conn(db)
    c.execute("INSERT INTO character_recipes (character_id, recipe_key, source) VALUES (1,?, 'loot')",
              ("recipe_wolf_fang_dagger",)); c.commit(); c.close()
    _give(db, 1, "kiel_wilczy", 2); _give(db, 1, "ruda_zelaza", 1)
    res = cs.craft(1, "recipe_wolf_fang_dagger", mode="self")
    assert res["ok"] and res["mode"] == "self"
    c = _conn(db)
    got = c.execute("SELECT COUNT(*) AS n FROM character_inventory "
                    "WHERE character_id=1 AND weapon_key='wolf_fang_dagger'").fetchone()["n"]
    assert got == 1
    c.close()


def test_service_craft_loot_no_skill_costs_markup(db):
    # Nowicjusz zna recepturę, brak skilla — usługa działa, koszt = base×1.5.
    c = _conn(db)
    c.execute("INSERT INTO character_recipes (character_id, recipe_key, source) VALUES (2,?, 'loot')",
              ("recipe_wolf_fang_dagger",)); c.commit(); c.close()
    _give(db, 2, "kiel_wilczy", 2); _give(db, 2, "ruda_zelaza", 1)
    res = cs.craft(2, "recipe_wolf_fang_dagger", mode="service")
    assert res["ok"] and res["mode"] == "service"
    # base service_cost_gold=55 → ×1.5 = 82 (round)
    assert res["service_cost_gold"] == round(55 * cs.SERVICE_MARKUP)


# ── D. Lista receptur (endpoint dane) ────────────────────────────────────────
def test_list_recipes_empty_has_any_false(db):
    out = cs.list_character_recipes(1)
    assert out["has_any"] is False and out["sets"] == [] and out["loose"] == []


def test_list_recipes_set_progress_and_components(db):
    # Uczymy 1 z 3 receptur setu + damy część komponentów.
    ls.grant_loot_to_character(1, [{"recipe_key": "recipe_wolf_fang_dagger", "quantity": 1}])
    _give(db, 1, "kiel_wilczy", 1)  # potrzeba 2 → owned 1
    out = cs.list_character_recipes(1)
    assert out["has_any"] is True
    sets = {s["set_key"]: s for s in out["sets"]}
    assert "wolf_hunter" in sets
    s = sets["wolf_hunter"]
    assert s["discovered_count"] == 1 and s["total"] == 3 and s["undiscovered"] == 2
    card = s["discovered"][0]
    kiel = next(i for i in card["inputs"] if i["item_key"] == "kiel_wilczy")
    assert kiel["owned"] == 1 and kiel["qty"] == 2 and kiel["enough"] is False
