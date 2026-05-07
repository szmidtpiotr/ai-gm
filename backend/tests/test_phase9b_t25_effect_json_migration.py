import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services import admin_config as admin_cfg
from app.services import loot_service as loot_mod
from app.services.effect_json_migration import normalize_flat_effect_to_json


def _parse(payload: str) -> dict:
    return json.loads(payload)


def _init_admin_db_without_effect_columns(path: Path) -> None:
    conn = sqlite3.connect(str(path))
    try:
        conn.executescript(
            """
            CREATE TABLE admin_audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                table_name TEXT NOT NULL,
                row_key TEXT NOT NULL,
                operation TEXT NOT NULL,
                old_values TEXT,
                new_values TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE game_config_loot_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                loot_table_key TEXT,
                item_key TEXT,
                weapon_key TEXT
            );

            CREATE TABLE game_config_items (
                key TEXT PRIMARY KEY,
                label TEXT NOT NULL,
                item_type TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                value_gp INTEGER NOT NULL DEFAULT 0,
                weight_kg REAL NOT NULL DEFAULT 0.0,
                allowed_classes TEXT NOT NULL DEFAULT '[]',
                ac_bonus INTEGER NOT NULL DEFAULT 0,
                charges INTEGER NOT NULL DEFAULT 1,
                effect_json TEXT,
                ai_generated INTEGER NOT NULL DEFAULT 0,
                approved INTEGER NOT NULL DEFAULT 1,
                note TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                locked_at TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            """
        )
        conn.commit()
    finally:
        conn.close()


def _init_loot_db_without_effect_columns(path: Path) -> None:
    conn = sqlite3.connect(str(path))
    try:
        conn.executescript(
            """
            CREATE TABLE characters (
                id INTEGER PRIMARY KEY,
                campaign_id INTEGER NOT NULL DEFAULT 1,
                name TEXT NOT NULL,
                sheet_json TEXT NOT NULL DEFAULT '{}',
                gold_gp INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE game_config_items (
                key TEXT PRIMARY KEY,
                label TEXT NOT NULL,
                item_type TEXT NOT NULL DEFAULT 'misc',
                description TEXT NOT NULL DEFAULT '',
                value_gp INTEGER NOT NULL DEFAULT 0,
                weight_kg REAL NOT NULL DEFAULT 0.0,
                charges INTEGER NOT NULL DEFAULT 1,
                effect_json TEXT,
                approved INTEGER NOT NULL DEFAULT 1,
                is_active INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE game_config_conditions (
                key TEXT PRIMARY KEY,
                label TEXT NOT NULL,
                effect_json TEXT NOT NULL,
                description TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                stackable INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE game_config_weapons (
                key TEXT PRIMARY KEY,
                label TEXT NOT NULL,
                value_gp INTEGER NOT NULL DEFAULT 0,
                is_active INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE game_config_consumables (
                key TEXT PRIMARY KEY,
                label TEXT NOT NULL,
                description TEXT,
                base_price INTEGER NOT NULL DEFAULT 0,
                effect_type TEXT,
                effect_dice TEXT,
                effect_bonus INTEGER NOT NULL DEFAULT 0,
                effect_target TEXT NOT NULL DEFAULT 'self',
                is_active INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE character_inventory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                character_id INTEGER NOT NULL,
                item_key TEXT,
                weapon_key TEXT,
                consumable_key TEXT,
                quantity INTEGER NOT NULL DEFAULT 1,
                equipped INTEGER NOT NULL DEFAULT 0,
                slot TEXT,
                acquired_at TEXT NOT NULL DEFAULT (datetime('now')),
                source TEXT,
                meta_json TEXT
            );

            CREATE TABLE active_combat (
                campaign_id INTEGER NOT NULL,
                character_id INTEGER NOT NULL,
                combatants TEXT NOT NULL DEFAULT '[]',
                updated_at TEXT
            );
            """
        )
        conn.execute(
            "INSERT INTO characters (id, campaign_id, name, sheet_json) VALUES (?, ?, ?, ?)",
            (
                1,
                1,
                "Hero",
                json.dumps({"current_hp": 3, "max_hp": 10, "current_mana": 1, "max_mana": 4, "conditions": []}),
            ),
        )
        conn.execute(
            """
            INSERT INTO game_config_items (
                key, label, item_type, charges, effect_json, approved, is_active
            ) VALUES (?, ?, 'consumable', 1, ?, 1, 1)
            """,
            (
                "health_potion_small",
                "Small Health Potion",
                normalize_flat_effect_to_json("heal_hp", "2d4", 0, "self"),
            ),
        )
        conn.execute(
            """
            INSERT INTO character_inventory (character_id, item_key, quantity, source)
            VALUES (1, 'health_potion_small', 1, 'loot')
            """
        )
        conn.commit()
    finally:
        conn.close()


def test_convert_heal_hp_uses_dice():
    payload = normalize_flat_effect_to_json("heal_hp", "2d4", None, None)
    assert payload is not None
    data = _parse(payload)
    assert data["effect_category"] == "consumable_immediate"
    assert data["effects"][0]["type"] == "heal_hp"
    assert data["effects"][0]["value"] == "2d4"


def test_convert_restore_mana_falls_back_to_bonus():
    payload = normalize_flat_effect_to_json("restore_mana", None, 3, None)
    assert payload is not None
    data = _parse(payload)
    assert data["effects"][0]["type"] == "restore_mana"
    assert data["effects"][0]["value"] == 3


def test_convert_remove_condition_requires_condition_key():
    assert normalize_flat_effect_to_json("remove_condition", None, None, "self") is None

    payload = normalize_flat_effect_to_json("remove_condition", None, None, "poisoned")
    assert payload is not None
    data = _parse(payload)
    assert data["effects"][0]["type"] == "remove_condition"
    assert data["effects"][0]["condition_key"] == "poisoned"


def test_convert_add_condition_normalizes_key():
    payload = normalize_flat_effect_to_json("add_condition", None, None, "PoIsOnEd")
    assert payload is not None
    data = _parse(payload)
    assert data["effects"][0]["type"] == "apply_condition"
    assert data["effects"][0]["condition_key"] == "poisoned"


def test_admin_item_legacy_fields_roundtrip_without_effect_columns(tmp_path, monkeypatch):
    db = tmp_path / "t25_admin.db"
    _init_admin_db_without_effect_columns(db)
    monkeypatch.setattr(admin_cfg, "DB_PATH", str(db))

    item = admin_cfg.create_item(
        key="health_potion_small",
        label="Small Health Potion",
        item_type="consumable",
        effect_type="heal_hp",
        effect_dice="2d4",
        charges=2,
    )

    payload = _parse(item["effect_json"])
    assert payload["effects"][0]["type"] == "heal_hp"
    assert payload["effects"][0]["value"] == "2d4"

    listed = admin_cfg.list_items()
    assert listed[0]["effect_type"] == "heal_hp"
    assert listed[0]["effect_dice"] == "2d4"
    assert listed[0]["charges"] == 2

    updated = admin_cfg.update_item(
        "health_potion_small",
        label=None,
        item_type=None,
        description=None,
        value_gp=None,
        effect_json=None,
        is_active=None,
        force=False,
        allowed_classes=None,
        weight_kg=None,
        ac_bonus=None,
        effect_type="restore_mana",
        effect_dice="",
        effect_bonus=3,
        effect_target=None,
        charges=None,
        ai_generated=None,
        approved=None,
        note=None,
    )

    updated_payload = _parse(updated["effect_json"])
    assert updated_payload["effects"][0]["type"] == "restore_mana"
    assert updated_payload["effects"][0]["value"] == 3

    consumables = admin_cfg.list_consumables()
    assert consumables[0]["effect_type"] == "restore_mana"
    assert consumables[0]["effect_bonus"] == 3


def test_loot_runtime_uses_effect_json_when_item_effect_columns_are_missing(tmp_path, monkeypatch):
    db = tmp_path / "t25_loot.db"
    _init_loot_db_without_effect_columns(db)
    monkeypatch.setattr(loot_mod, "LOOT_DB_PATH", str(db))

    result = loot_mod.use_inventory_item(1, 1)

    assert result["item"]["key"] == "health_potion_small"
    assert result["effects_applied"][0]["type"] == "heal_hp"
    assert result["effects_applied"][0]["amount"] >= 1
