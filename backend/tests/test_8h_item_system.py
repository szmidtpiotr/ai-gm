"""
Phase 8H — Item System Unification: integration tests.

Covers:
  - DB schema: new columns, removed legacy, consumables in items
  - loot_service: item_key path for all non-weapon loot
  - Grant Item resolver: catalog hit vs miss (approved / narrative)
  - get_item_catalog_for_prompt: format and filtering
  - loot_entries XOR constraint
"""

from __future__ import annotations

import sqlite3

import pytest


def _minimal_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS game_config_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT UNIQUE NOT NULL,
            label TEXT NOT NULL,
            item_type TEXT NOT NULL DEFAULT 'misc',
            description TEXT,
            value_gp INTEGER NOT NULL DEFAULT 0,
            weight_kg REAL NOT NULL DEFAULT 0.0,
            allowed_classes TEXT NOT NULL DEFAULT '[]',
            ac_bonus INTEGER NOT NULL DEFAULT 0,
            effect_type TEXT,
            effect_dice TEXT,
            effect_bonus INTEGER NOT NULL DEFAULT 0,
            effect_target TEXT NOT NULL DEFAULT 'self',
            charges INTEGER NOT NULL DEFAULT 1,
            ai_generated INTEGER NOT NULL DEFAULT 0,
            approved INTEGER NOT NULL DEFAULT 1,
            note TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            locked_at TEXT,
            created_at TEXT,
            updated_at TEXT
        );

        CREATE TABLE IF NOT EXISTS game_config_weapons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT UNIQUE NOT NULL,
            label TEXT NOT NULL,
            damage_die TEXT NOT NULL DEFAULT '1d4',
            linked_stat TEXT NOT NULL DEFAULT 'STR',
            value_gp INTEGER NOT NULL DEFAULT 0,
            ai_generated INTEGER NOT NULL DEFAULT 0,
            approved INTEGER NOT NULL DEFAULT 1,
            is_active INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS game_config_loot_tables (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT UNIQUE NOT NULL,
            label TEXT
        );

        CREATE TABLE IF NOT EXISTS game_config_loot_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            loot_table_key TEXT NOT NULL
                REFERENCES game_config_loot_tables(key) ON DELETE CASCADE,
            item_key   TEXT REFERENCES game_config_items(key) ON DELETE CASCADE,
            weapon_key TEXT REFERENCES game_config_weapons(key) ON DELETE CASCADE,
            currency_code TEXT,
            weight INTEGER NOT NULL DEFAULT 10,
            qty_min INTEGER NOT NULL DEFAULT 1,
            qty_max INTEGER NOT NULL DEFAULT 1,
            CONSTRAINT loot_xor CHECK (
                (CASE WHEN item_key   IS NOT NULL THEN 1 ELSE 0 END +
                 CASE WHEN weapon_key IS NOT NULL THEN 1 ELSE 0 END) = 1
            )
        );

        CREATE TABLE IF NOT EXISTS characters (
            id INTEGER PRIMARY KEY,
            name TEXT,
            gold_gp INTEGER NOT NULL DEFAULT 0,
            sheet_json TEXT
        );

        CREATE TABLE IF NOT EXISTS character_inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id INTEGER NOT NULL,
            item_key TEXT,
            weapon_key TEXT,
            consumable_key TEXT,
            quantity INTEGER NOT NULL DEFAULT 1,
            source TEXT,
            equipped INTEGER NOT NULL DEFAULT 0,
            slot TEXT,
            acquired_at TEXT,
            meta_json TEXT,
            label TEXT,
            durability_max INTEGER,
            durability_current INTEGER,
            game_item_key TEXT,
            affixes_json TEXT,
            CONSTRAINT inv_xor CHECK (
                (CASE WHEN item_key       IS NOT NULL THEN 1 ELSE 0 END +
                 CASE WHEN weapon_key     IS NOT NULL THEN 1 ELSE 0 END +
                 CASE WHEN consumable_key IS NOT NULL THEN 1 ELSE 0 END) = 1
            )
        );
        """
    )


def _seed_catalog(conn: sqlite3.Connection) -> None:
    conn.executemany(
        """
        INSERT OR IGNORE INTO game_config_items
            (key, label, item_type, value_gp, ac_bonus,
             effect_type, effect_dice, effect_bonus, charges, approved, is_active)
        VALUES (?,?,?,?,?,?,?,?,?, ?,1)
        """,
        [
            ("leather_armor", "Skórzana Zbroja", "armor", 50, 2, None, None, 0, 1, 1),
            ("health_potion", "Mikstura Leczenia", "consumable", 30, 0, "heal_hp", "2d4", 2, 1, 1),
            ("rope", "Lina", "misc", 2, 0, None, None, 0, 1, 1),
            ("quest_amulet", "Amulet Fabularny", "narrative", 0, 0, None, None, 0, 1, 1),
            ("draft_item", "Roboczy Przedmiot", "misc", 0, 0, None, None, 0, 1, 0),
        ],
    )
    conn.execute(
        """
        INSERT OR IGNORE INTO game_config_weapons
            (key, label, damage_die, linked_stat, value_gp, approved, is_active)
        VALUES ('dagger', 'Sztylet', '1d4', 'DEX', 10, 1, 1)
        """
    )
    conn.execute("INSERT OR IGNORE INTO characters(id, name, gold_gp) VALUES (1, 'TestHero', 100)")
    conn.execute("INSERT OR IGNORE INTO game_config_loot_tables(key, label) VALUES ('test_table', 'Test')")
    conn.commit()


@pytest.fixture
def h8_db_path(tmp_path):
    p = str(tmp_path / "test_8h.db")
    conn = sqlite3.connect(p)
    conn.row_factory = sqlite3.Row
    _minimal_schema(conn)
    _seed_catalog(conn)
    conn.close()
    return p


@pytest.fixture
def h8_conn(h8_db_path):
    conn = sqlite3.connect(h8_db_path)
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


@pytest.fixture
def patched_loot(h8_db_path):
    from app.services import loot_service

    orig = loot_service.LOOT_DB_PATH
    loot_service.LOOT_DB_PATH = h8_db_path
    yield loot_service
    loot_service.LOOT_DB_PATH = orig


class TestSchema8H:
    REQUIRED_ITEM_COLS = {
        "ac_bonus",
        "effect_type",
        "effect_dice",
        "effect_bonus",
        "effect_target",
        "charges",
        "ai_generated",
        "approved",
        "allowed_classes",
    }
    REMOVED_ITEM_COLS = {"weight", "proficiency_classes"}

    def test_items_has_new_columns(self, h8_conn):
        cols = {r[1] for r in h8_conn.execute("PRAGMA table_info(game_config_items)")}
        missing = self.REQUIRED_ITEM_COLS - cols
        assert not missing, f"Brakujące kolumny w game_config_items: {missing}"

    def test_items_has_no_legacy_columns(self, h8_conn):
        cols = {r[1] for r in h8_conn.execute("PRAGMA table_info(game_config_items)")}
        present_legacy = self.REMOVED_ITEM_COLS & cols
        assert not present_legacy, f"Legacy kolumny nadal obecne: {present_legacy}"

    def test_weapons_has_ai_flags(self, h8_conn):
        cols = {r[1] for r in h8_conn.execute("PRAGMA table_info(game_config_weapons)")}
        assert "ai_generated" in cols
        assert "approved" in cols

    def test_loot_entries_has_no_consumable_key(self, h8_conn):
        cols = {r[1] for r in h8_conn.execute("PRAGMA table_info(game_config_loot_entries)")}
        assert "consumable_key" not in cols, "consumable_key powinien być usunięty z loot_entries"

    def test_consumables_migrated_as_item_type(self, h8_conn):
        row = h8_conn.execute(
            "SELECT COUNT(*) AS n FROM game_config_items WHERE item_type = 'consumable'"
        ).fetchone()
        assert int(row["n"]) >= 1

    def test_consumable_has_value_gp(self, h8_conn):
        row = h8_conn.execute(
            "SELECT value_gp FROM game_config_items WHERE key = 'health_potion'"
        ).fetchone()
        assert row is not None
        assert int(row["value_gp"]) > 0


class TestLootXOR:
    def test_valid_item_entry(self, h8_conn):
        h8_conn.execute(
            "INSERT INTO game_config_loot_entries(loot_table_key, item_key, weight) "
            "VALUES ('test_table','leather_armor',10)"
        )
        h8_conn.rollback()

    def test_valid_weapon_entry(self, h8_conn):
        h8_conn.execute(
            "INSERT INTO game_config_loot_entries(loot_table_key, weapon_key, weight) "
            "VALUES ('test_table','dagger',10)"
        )
        h8_conn.rollback()

    def test_both_null_violates_xor(self, h8_conn):
        with pytest.raises(sqlite3.IntegrityError):
            h8_conn.execute(
                "INSERT INTO game_config_loot_entries(loot_table_key, weight) VALUES ('test_table',10)"
            )
            h8_conn.commit()

    def test_both_not_null_violates_xor(self, h8_conn):
        with pytest.raises(sqlite3.IntegrityError):
            h8_conn.execute(
                """
                INSERT INTO game_config_loot_entries
                    (loot_table_key, item_key, weapon_key, weight)
                VALUES ('test_table','leather_armor','dagger',10)
                """
            )
            h8_conn.commit()


class TestLootServiceItemKey:
    @pytest.fixture(autouse=True)
    def _clear_inventory(self, h8_db_path, patched_loot):
        conn = sqlite3.connect(h8_db_path)
        conn.execute("DELETE FROM character_inventory")
        conn.commit()
        conn.close()
        yield

    def test_grant_armor_uses_item_key(self, patched_loot):
        loot = [{"item_key": "leather_armor", "quantity": 1}]
        out = patched_loot.grant_loot_to_character(1, loot, source="test")
        assert isinstance(out, list)
        assert len(out) >= 1

        conn = sqlite3.connect(patched_loot.LOOT_DB_PATH)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT item_key, consumable_key FROM character_inventory "
            "WHERE character_id=1 AND item_key='leather_armor'"
        ).fetchone()
        conn.close()
        assert row is not None
        assert row["item_key"] == "leather_armor"
        assert row["consumable_key"] is None

    def test_grant_consumable_uses_item_key(self, patched_loot):
        patched_loot.grant_loot_to_character(1, [{"item_key": "health_potion", "quantity": 2}], source="test")
        conn = sqlite3.connect(patched_loot.LOOT_DB_PATH)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT item_key, consumable_key, quantity FROM character_inventory "
            "WHERE character_id=1 AND item_key='health_potion'"
        ).fetchone()
        conn.close()
        assert row is not None
        assert row["consumable_key"] is None
        assert int(row["quantity"]) == 2


class TestItemCatalogForPrompt:
    def test_returns_nonempty_string(self, h8_conn):
        from app.services import combat_service

        result = combat_service.get_item_catalog_for_prompt(h8_conn)
        assert isinstance(result, str)
        assert len(result) > 10

    def test_contains_item_catalog_header(self, h8_conn):
        from app.services import combat_service

        result = combat_service.get_item_catalog_for_prompt(h8_conn)
        assert "[ITEM CATALOG]" in result

    def test_contains_approved_item(self, h8_conn):
        from app.services import combat_service

        result = combat_service.get_item_catalog_for_prompt(h8_conn)
        assert "leather_armor" in result or "Skórzana Zbroja" in result

    def test_excludes_unapproved(self, h8_conn):
        from app.services import combat_service

        result = combat_service.get_item_catalog_for_prompt(h8_conn)
        assert "draft_item" not in result

    def test_excludes_narrative_type(self, h8_conn):
        from app.services import combat_service

        result = combat_service.get_item_catalog_for_prompt(h8_conn)
        assert "quest_amulet" not in result

    def test_armor_shows_ac_bonus(self, h8_conn):
        from app.services import combat_service

        result = combat_service.get_item_catalog_for_prompt(h8_conn)
        assert "AC +2" in result

    def test_consumable_shows_effect(self, h8_conn):
        from app.services import combat_service

        result = combat_service.get_item_catalog_for_prompt(h8_conn)
        assert "heal_hp" in result or "2d4" in result

    def test_empty_catalog_returns_empty_string(self, tmp_path):
        from app.services import combat_service

        empty_db = str(tmp_path / "empty_items.db")
        conn = sqlite3.connect(empty_db)
        conn.row_factory = sqlite3.Row
        conn.execute(
            """
            CREATE TABLE game_config_items (
                key TEXT PRIMARY KEY,
                label TEXT NOT NULL,
                item_type TEXT NOT NULL DEFAULT 'misc',
                value_gp INTEGER NOT NULL DEFAULT 0,
                ac_bonus INTEGER NOT NULL DEFAULT 0,
                effect_type TEXT,
                effect_dice TEXT,
                effect_bonus INTEGER NOT NULL DEFAULT 0,
                effect_target TEXT NOT NULL DEFAULT 'self',
                charges INTEGER NOT NULL DEFAULT 1,
                approved INTEGER NOT NULL DEFAULT 1,
                is_active INTEGER NOT NULL DEFAULT 1,
                description TEXT
            )
            """
        )
        conn.commit()
        result = combat_service.get_item_catalog_for_prompt(conn)
        conn.close()
        assert result == ""


class TestGrantItemResolver:
    def _resolve(self, db_path: str, label: str):
        from app.api import turns

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            return turns._resolve_grant_catalog_item(conn, label)
        finally:
            conn.close()

    def test_hit_by_exact_label(self, h8_db_path):
        r = self._resolve(h8_db_path, "Skórzana Zbroja")
        assert r is not None
        assert r["item_key"] == "leather_armor"

    def test_hit_by_partial_label(self, h8_db_path):
        r = self._resolve(h8_db_path, "Mikstura")
        assert r is not None
        assert r["item_key"] == "health_potion"

    def test_hit_consumable_exact_label(self, h8_db_path):
        r = self._resolve(h8_db_path, "Mikstura Leczenia")
        assert r is not None
        assert r["item_key"] == "health_potion"

    def test_miss_returns_none(self, h8_db_path):
        assert self._resolve(h8_db_path, "Magiczny Miecz Burzy XXXXXX") is None

    def test_unapproved_label_not_resolved(self, h8_db_path):
        assert self._resolve(h8_db_path, "Roboczy Przedmiot") is None
