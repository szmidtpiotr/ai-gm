"""TDD: Issue #1347 — set `wolf_hunter` musi mieć źródło zdobycia części.

Defekt: 3 części setu (`wolf_hide_cloak`, `wolf_fang_dagger`, `wolf_totem_charm`)
nie istnieją w żadnym katalogu ani jako loot/craft — pętli „farm→craft→set"
nie da się domknąć normalną grą. Silnik setów (#1340) jest sprawny; brakuje
wyłącznie WIĄZANIA ZAWARTOŚCI.

Test seeduje minimalny schemat + wywołuje `_ensure_wolf_hunter_content(conn)`
i sprawdza:
  1. każda z 3 części istnieje w katalogu (items/weapons),
  2. każda ma ≥1 źródło zdobycia (loot entry lub receptura),
  3. integracja: równie 2 zdobyte części → get_active_sets 2/3 + bonus +1 DEX.
"""
import os
import sqlite3
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.migrations_admin import (  # noqa: E402
    _ensure_sets_schema,
    _ensure_wolf_hunter_content,
)
from app.services.equipment_effects_service import (  # noqa: E402
    get_active_sets,
    get_equipment_bonuses,
)

PIECES = ("wolf_hide_cloak", "wolf_fang_dagger", "wolf_totem_charm")


def _build_schema(conn: sqlite3.Connection) -> None:
    """Minimalny schemat tabel dotykanych przez seed contentu setu."""
    conn.executescript(
        """
        CREATE TABLE game_config_items (
            key TEXT PRIMARY KEY, label TEXT NOT NULL,
            item_type TEXT NOT NULL DEFAULT 'misc',
            description TEXT NOT NULL DEFAULT '', value_gp INTEGER NOT NULL DEFAULT 0,
            effect_json TEXT, is_active INTEGER NOT NULL DEFAULT 1,
            ac_bonus INTEGER NOT NULL DEFAULT 0, armor_coverage TEXT DEFAULT 'torso',
            rarity INTEGER NOT NULL DEFAULT 1, is_component INTEGER NOT NULL DEFAULT 0,
            no_trade INTEGER NOT NULL DEFAULT 0, created_by TEXT
        );
        CREATE TABLE game_config_weapons (
            key TEXT PRIMARY KEY, label TEXT NOT NULL, damage_die TEXT NOT NULL,
            weapon_type TEXT NOT NULL DEFAULT 'melee', linked_stat TEXT NOT NULL,
            allowed_classes TEXT NOT NULL, finesse INTEGER NOT NULL DEFAULT 0,
            weapon_slot TEXT DEFAULT 'main_hand', value_gp INTEGER NOT NULL DEFAULT 0,
            description TEXT NOT NULL DEFAULT '', is_active INTEGER NOT NULL DEFAULT 1,
            rarity INTEGER NOT NULL DEFAULT 1, effect_json TEXT DEFAULT NULL
        );
        CREATE TABLE game_config_loot_tables (
            key TEXT PRIMARY KEY, label TEXT, is_active INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE game_config_loot_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            loot_table_key TEXT NOT NULL,
            item_key TEXT, consumable_key TEXT, weapon_key TEXT,
            weight INTEGER NOT NULL DEFAULT 10,
            qty_min INTEGER NOT NULL DEFAULT 1, qty_max INTEGER NOT NULL DEFAULT 1,
            CHECK (
                (CASE WHEN item_key IS NOT NULL THEN 1 ELSE 0 END)
              + (CASE WHEN consumable_key IS NOT NULL THEN 1 ELSE 0 END)
              + (CASE WHEN weapon_key IS NOT NULL THEN 1 ELSE 0 END) = 1
            )
        );
        CREATE UNIQUE INDEX ux_le_item ON game_config_loot_entries(loot_table_key, item_key) WHERE item_key IS NOT NULL;
        CREATE UNIQUE INDEX ux_le_weap ON game_config_loot_entries(loot_table_key, weapon_key) WHERE weapon_key IS NOT NULL;
        CREATE TABLE game_config_recipes (
            key TEXT PRIMARY KEY, label TEXT NOT NULL,
            inputs_json TEXT NOT NULL DEFAULT '[]',
            output_type TEXT NOT NULL DEFAULT 'consumable', output_key TEXT,
            output_qty INTEGER NOT NULL DEFAULT 1, service_cost_gold INTEGER NOT NULL DEFAULT 0,
            crafter_type TEXT NOT NULL DEFAULT 'smith', is_hidden INTEGER NOT NULL DEFAULT 0,
            is_active INTEGER NOT NULL DEFAULT 1, craft_tier TEXT NOT NULL DEFAULT 'medium',
            created_by TEXT
        );
        CREATE TABLE character_inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT, character_id INTEGER NOT NULL,
            item_key TEXT, weapon_key TEXT, consumable_key TEXT,
            slot TEXT, equipped INTEGER NOT NULL DEFAULT 0
        );
        -- Loot tables + komponenty, do których seed contentu się wpina (wilcza wataha).
        INSERT INTO game_config_loot_tables (key, label) VALUES ('loot_wolf', 'Łupy: Wilk');
        INSERT INTO game_config_loot_tables (key, label) VALUES ('loot_rykar_wilkowy', 'Łupy: Rykar Wilkowy');
        INSERT INTO game_config_items (key, label, is_component) VALUES ('wolf_pelt', 'Skóra wilka', 1);
        INSERT INTO game_config_items (key, label, is_component) VALUES ('kiel_wilczy', 'Kieł wilczy', 1);
        INSERT INTO game_config_items (key, label, is_component) VALUES ('krew_wilkolaka', 'Krew wilkołaka', 1);
        INSERT INTO game_config_items (key, label, is_component) VALUES ('ruda_zelaza', 'Ruda żelaza', 1);
        """
    )
    conn.commit()


@pytest.fixture()
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    _build_schema(c)
    _ensure_sets_schema(c)  # #1340 — set wolf_hunter (definicja pieces_json/bonuses_json)
    _ensure_wolf_hunter_content(c)  # #1347 — treść części + źródła zdobycia
    yield c
    c.close()


# ─── Test główny 1: części istnieją w katalogu ────────────────────────────────

def test_all_three_pieces_exist_in_catalog(conn):
    """Każda z 3 części setu ma rekord w items/weapons (is_active=1)."""
    items = {r["key"] for r in conn.execute(
        "SELECT key FROM game_config_items WHERE is_active = 1")}
    weapons = {r["key"] for r in conn.execute(
        "SELECT key FROM game_config_weapons WHERE is_active = 1")}
    catalog = items | weapons
    for piece in PIECES:
        assert piece in catalog, f"{piece} brak w katalogu items/weapons"


# ─── Test główny 2: każda część ma ≥1 źródło zdobycia ─────────────────────────

def test_every_piece_has_acquisition_source(conn):
    """Każda część ma ≥1 wpis w loot LUB recepturę z tym output_key."""
    for piece in PIECES:
        loot = conn.execute(
            "SELECT COUNT(*) FROM game_config_loot_entries "
            "WHERE item_key = ? OR weapon_key = ?", (piece, piece)
        ).fetchone()[0]
        recipe = conn.execute(
            "SELECT COUNT(*) FROM game_config_recipes WHERE output_key = ?", (piece,)
        ).fetchone()[0]
        assert (loot + recipe) >= 1, f"{piece} nie ma żadnego źródła (drop/craft)"


# ─── Test główny 3: 2 części z farmy pospolitego wilka (loot_wolf) ────────────

def test_two_pieces_droppable_from_common_wolf(conn):
    """Nowy bohater farmiąc pospolite wilki może zdobyć ≥2 części (loot_wolf)."""
    dropped = {
        (r["item_key"] or r["weapon_key"])
        for r in conn.execute(
            "SELECT item_key, weapon_key FROM game_config_loot_entries "
            "WHERE loot_table_key = 'loot_wolf'")
    }
    from_wolf = dropped & set(PIECES)
    assert len(from_wolf) >= 2, (
        f"loot_wolf daje tylko {from_wolf} części — trzeba ≥2 dla '2/3' bez bossa")


# ─── Test integracyjny: 2 zdobyte części → set 2/3 + bonus +1 DEX ─────────────

def test_wearing_two_seeded_pieces_grants_set_bonus(conn):
    """Założenie 2 SEEDOWANYCH części → get_active_sets 2/3 + get_equipment_bonuses DEX +1."""
    cid = 4242
    two = list(PIECES)[:2]  # wolf_hide_cloak (item), wolf_fang_dagger (weapon)
    conn.execute(
        "INSERT INTO character_inventory (character_id, item_key, slot, equipped) "
        "VALUES (?, 'wolf_hide_cloak', 'back', 1)", (cid,))
    conn.execute(
        "INSERT INTO character_inventory (character_id, weapon_key, slot, equipped) "
        "VALUES (?, 'wolf_fang_dagger', 'main_hand', 1)", (cid,))
    conn.commit()

    sets = get_active_sets(cid, conn)
    wolf = next((s for s in sets if s["key"] == "wolf_hunter"), None)
    assert wolf is not None, "set wolf_hunter niewidoczny mimo 2 założonych części"
    assert wolf["worn"] == 2, f"worn={wolf['worn']}, oczekiwano 2"
    assert wolf["active_threshold"] == 2

    bonuses = get_equipment_bonuses(cid, conn)
    assert bonuses["stats"].get("DEX", 0) == 1, (
        f"bonus 2cz +1 DEX nie zadziałał: {bonuses['stats']}")
    _ = two  # noqa


# ─── Backward compatibility: idempotencja + nietknięcie istniejącej treści ────

def test_seed_is_idempotent(conn):
    """Ponowne wywołanie seedu nie duplikuje ani nie wywala się."""
    before_items = conn.execute("SELECT COUNT(*) FROM game_config_items").fetchone()[0]
    before_loot = conn.execute("SELECT COUNT(*) FROM game_config_loot_entries").fetchone()[0]
    _ensure_wolf_hunter_content(conn)
    _ensure_wolf_hunter_content(conn)
    after_items = conn.execute("SELECT COUNT(*) FROM game_config_items").fetchone()[0]
    after_loot = conn.execute("SELECT COUNT(*) FROM game_config_loot_entries").fetchone()[0]
    assert before_items == after_items, "seed zduplikował itemy"
    assert before_loot == after_loot, "seed zduplikował wpisy loot"
