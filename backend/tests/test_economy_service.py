"""
Tests for Economy Service — Phase 06 Tasks 20-26
"""
import json
import sqlite3
import pytest

from app.services.economy_service import (
    get_wound_label, grant_xp, get_total_xp, get_level_display,
    get_xp_log, equip_item, unequip_item, get_equipped_items,
    get_inventory, add_to_inventory, apply_healing_item, apply_rest, get_xp_award_amount,
)


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE characters (id INTEGER PRIMARY KEY, sheet_json TEXT DEFAULT '{}');
        CREATE TABLE character_inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id INTEGER, item_key TEXT, weapon_key TEXT,
            consumable_key TEXT, quantity INTEGER DEFAULT 1,
            equipped INTEGER DEFAULT 0, slot TEXT, source TEXT, acquired_at TEXT DEFAULT '2026-01-01'
        );
        CREATE TABLE character_xp_grants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id INTEGER, campaign_id INTEGER,
            amount INTEGER, source_key TEXT, detail TEXT,
            turn_number INTEGER, created_at TEXT DEFAULT '2026-01-01'
        );
        CREATE TABLE game_config_xp_awards (
            id INTEGER PRIMARY KEY, category TEXT, source_key TEXT UNIQUE,
            label TEXT, xp_amount INTEGER DEFAULT 0, is_active INTEGER DEFAULT 1
        );
        CREATE TABLE game_config_items (
            key TEXT PRIMARY KEY, label TEXT, item_type TEXT DEFAULT 'misc',
            effect_json TEXT, value_gp INTEGER DEFAULT 0, ac_bonus INTEGER DEFAULT 0
        );
        CREATE TABLE game_config_weapons (
            key TEXT PRIMARY KEY, label TEXT, damage_die TEXT DEFAULT 'd6',
            weapon_type TEXT DEFAULT 'melee', value_gp INTEGER DEFAULT 0
        );
        CREATE TABLE game_config_consumables (
            key TEXT PRIMARY KEY, label TEXT,
            effect_type TEXT, effect_dice TEXT, effect_bonus INTEGER DEFAULT 0,
            base_price INTEGER DEFAULT 0
        );
        CREATE TABLE game_config_enemies (
            key TEXT PRIMARY KEY, label TEXT, tier TEXT DEFAULT 'standard',
            loot_table_key TEXT, drop_chance REAL DEFAULT 1.0
        );
        CREATE TABLE game_config_loot_tables (
            key TEXT PRIMARY KEY, label TEXT, gold_min INTEGER DEFAULT 0, gold_max INTEGER DEFAULT 5
        );
        CREATE TABLE game_config_loot_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            loot_table_key TEXT, item_key TEXT, weapon_key TEXT,
            consumable_key TEXT, weight INTEGER DEFAULT 100, qty_min INTEGER DEFAULT 1, qty_max INTEGER DEFAULT 1
        );
        CREATE TABLE game_locations (id INTEGER PRIMARY KEY, key TEXT UNIQUE, label TEXT);
        CREATE TABLE combat_loot (
            id INTEGER PRIMARY KEY AUTOINCREMENT, campaign_id INTEGER, character_id INTEGER,
            combat_location_id INTEGER, loot_items TEXT DEFAULT '[]',
            status TEXT DEFAULT 'available'
        );

        -- Seeds
        INSERT INTO characters VALUES (1, '{"stats":{"CON":12,"INT":12},"current_hp":8,"max_hp":12,"current_mana":6,"max_mana":9,"archetype":"warrior","gold":10}');
        INSERT INTO characters VALUES (2, '{"stats":{"CON":10,"INT":14},"current_hp":5,"max_hp":6,"current_mana":8,"max_mana":14,"archetype":"scholar","gold":5}');

        INSERT INTO game_config_xp_awards (category, source_key, label, xp_amount, is_active)
            VALUES ('combat','kill_weak','Kill weak',10,1),
                   ('combat','kill_standard','Kill standard',25,1),
                   ('campaign','beat_complete','Beat complete',30,1);

        INSERT INTO game_config_weapons VALUES ('sword_iron','Iron Sword','d8','melee',20);
        INSERT INTO game_config_items VALUES ('leather_armor','Leather Armor','armor','{"stat_mods":{"AC":2}}',30,2);
        INSERT INTO game_config_consumables VALUES ('health_potion','Health Potion','heal_hp','1d8',2,25);
        INSERT INTO game_config_consumables VALUES ('bandage','Bandage','heal_hp','1d6',0,3);

        INSERT INTO game_config_enemies VALUES ('goblin','Goblin','weak','goblin_loot',0.8);
        INSERT INTO game_config_loot_tables VALUES ('goblin_loot','Goblin Loot',2,8);
        INSERT INTO game_config_loot_entries (loot_table_key, item_key, weight, qty_min, qty_max)
            VALUES ('goblin_loot','health_potion',30,1,1);
    """)
    conn.commit()
    yield conn
    conn.close()


# ── TASK_24: Wound Labels ─────────────────────────────────────────────────

class TestWoundLabels:
    def test_full_hp_no_label(self):
        r = get_wound_label(12, 12)
        assert r["label"] is None
        assert r["color"] == "#4caf50"

    def test_ranny_threshold(self):
        r = get_wound_label(7, 12)  # 58%
        assert r["label"] == "Ranny"

    def test_ciezko_ranny(self):
        r = get_wound_label(4, 12)  # 33%
        assert r["label"] == "Ciężko Ranny"

    def test_powazanie_ranny(self):
        r = get_wound_label(2, 12)  # 16%
        assert r["label"] == "Poważnie Ranny"

    def test_na_skraju_smierci(self):
        r = get_wound_label(1, 12)  # 8%
        assert r["label"] == "Na Skraju Śmierci"
        assert r["color"] == "#7f0000"

    def test_zero_max_hp(self):
        r = get_wound_label(0, 0)
        assert r["label"] is None


# ── TASK_25V2: XP System ─────────────────────────────────────────────────

class TestXPSystem:
    def test_grant_xp_reads_from_table(self, db):
        amount = grant_xp(1, 1, "kill_weak", db, "goblin_scout", 5)
        assert amount == 10

    def test_grant_xp_inactive_returns_zero(self, db):
        db.execute("UPDATE game_config_xp_awards SET is_active = 0 WHERE source_key = 'kill_weak'")
        db.commit()
        amount = grant_xp(1, 1, "kill_weak", db)
        assert amount == 0

    def test_grant_xp_unknown_returns_zero(self, db):
        amount = grant_xp(1, 1, "nonexistent_source", db)
        assert amount == 0

    def test_get_total_xp(self, db):
        grant_xp(1, 1, "kill_weak", db)
        grant_xp(1, 1, "kill_standard", db)
        total = get_total_xp(1, db)
        assert total == 35  # 10 + 25

    def test_level_display(self, db):
        for _ in range(4):
            grant_xp(1, 1, "kill_standard", db)  # 25 each = 100 total
        level = get_level_display(1, db)
        assert level == 1

    def test_level_display_zero_xp(self, db):
        assert get_level_display(1, db) == 0

    def test_xp_log(self, db):
        grant_xp(1, 1, "kill_weak", db, "goblin", 3)
        grant_xp(1, 1, "beat_complete", db, "meet_informant", 7)
        log = get_xp_log(1, db)
        assert len(log) == 2
        assert any(e["source_key"] == "beat_complete" for e in log)


# ── TASK_20: Inventory & Equipment ───────────────────────────────────────

class TestInventory:
    def test_add_weapon_to_inventory(self, db):
        ok = add_to_inventory(1, "sword_iron", 1, "loot", db, "weapon")
        assert ok is True
        inv = get_inventory(1, db)
        assert any(i["weapon_key"] == "sword_iron" for i in inv)

    def test_equip_weapon(self, db):
        add_to_inventory(1, "sword_iron", 1, "start", db, "weapon")
        inv = get_inventory(1, db)
        inv_id = next(i["id"] for i in inv if i["weapon_key"] == "sword_iron")
        result = equip_item(1, inv_id, "main_hand", db)
        assert result["ok"] is True
        equipped = get_equipped_items(1, db)
        assert equipped.get("main_hand") == "sword_iron"

    def test_equip_replaces_existing(self, db):
        # Equip first sword
        add_to_inventory(1, "sword_iron", 1, "start", db, "weapon")
        inv = get_inventory(1, db)
        inv_id1 = next(i["id"] for i in inv if i["weapon_key"] == "sword_iron")
        equip_item(1, inv_id1, "main_hand", db)
        # Add and equip second sword
        add_to_inventory(1, "sword_iron", 1, "shop", db, "weapon")
        inv = get_inventory(1, db)
        inv_id2 = max(i["id"] for i in inv if i["weapon_key"] == "sword_iron")
        result = equip_item(1, inv_id2, "main_hand", db)
        assert result["ok"] is True
        assert result["unequipped_key"] == "sword_iron"

    def test_equip_invalid_slot(self, db):
        add_to_inventory(1, "sword_iron", 1, "start", db, "weapon")
        inv = get_inventory(1, db)
        inv_id = inv[0]["id"]
        result = equip_item(1, inv_id, "boots", db)
        assert result["ok"] is False

    def test_unequip(self, db):
        add_to_inventory(1, "sword_iron", 1, "start", db, "weapon")
        inv = get_inventory(1, db)
        inv_id = inv[0]["id"]
        equip_item(1, inv_id, "main_hand", db)
        result = unequip_item(1, "main_hand", db)
        assert result["ok"] is True
        assert get_equipped_items(1, db).get("main_hand") is None


# ── TASK_23: Healing ──────────────────────────────────────────────────────

class TestHealing:
    def test_apply_potion(self, db):
        # Add potion to inventory
        db.execute(
            "INSERT INTO character_inventory (character_id, item_key, quantity, source) VALUES (1, 'health_potion', 1, 'test')"
        )
        db.commit()
        result = apply_healing_item(1, "health_potion", db)
        assert result["ok"] is True
        assert result["hp_after"] > result["hp_before"]
        assert result["hp_after"] <= 12

    def test_apply_potion_not_in_inventory(self, db):
        result = apply_healing_item(1, "health_potion", db)
        assert result["ok"] is False

    def test_short_rest_heals(self, db):
        result = apply_rest(1, "short", db)
        assert result["ok"] is True
        assert result["hp_after"] > result["hp_before"]

    def test_long_rest_full_heal(self, db):
        result = apply_rest(1, "long", db)
        assert result["ok"] is True
        assert result["hp_after"] == 12  # max_hp
        assert result["mana_after"] == 9  # long rest → max_mana

    def test_long_rest_scholar_restores_mana(self, db):
        result = apply_rest(2, "long", db)  # Scholar with max_mana=14
        assert result["mana_after"] == 14

    def test_short_rest_scholar_recovers_mana(self, db):
        result = apply_rest(2, "short", db)
        # INT 14 → mod +2, so recover 2 mana (or more with CON roll)
        assert result["mana_after"] >= result["mana_before"]
