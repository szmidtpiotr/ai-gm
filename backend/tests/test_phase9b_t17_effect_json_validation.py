"""T17 — effect_json v0 ([S13]) validation for admin save/import."""

import json
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services import admin_config as admin_cfg
from app.services import admin_config_transfer as transfer_mod


def _init_admin_db(path: Path) -> None:
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

            CREATE TABLE game_config_conditions (
                key TEXT PRIMARY KEY,
                label TEXT NOT NULL,
                effect_json TEXT NOT NULL,
                description TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                stackable INTEGER NOT NULL DEFAULT 0,
                auto_remove TEXT,
                locked_at TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
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
                effect_type TEXT,
                effect_dice TEXT,
                effect_bonus INTEGER NOT NULL DEFAULT 0,
                effect_target TEXT NOT NULL DEFAULT 'self',
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


def _valid_condition_effect() -> dict:
    return {
        "schema_version": 1,
        "effect_category": "character_condition",
        "effects": [
            {
                "type": "periodic_save",
                "dc_key": "fear_easy",
                "tick": "each_round",
                "expires": "save_success",
            }
        ],
    }


def _valid_item_effect() -> dict:
    return {
        "schema_version": 1,
        "effect_category": "gear_bonus",
        "effects": [
            {
                "type": "static_stat_modifier",
                "stat": "DEX",
                "value": 2,
            }
        ],
    }


@pytest.fixture
def admin_db(tmp_path, monkeypatch):
    db = tmp_path / "t17_admin.db"
    _init_admin_db(db)
    monkeypatch.setattr(admin_cfg, "DB_PATH", str(db))
    yield db


def test_create_condition_accepts_effect_json_v1(admin_db):
    item = admin_cfg.create_condition(
        key="fear_test",
        label="Strach testowy",
        effect_json=json.dumps(_valid_condition_effect()),
        description="test",
    )

    assert item["key"] == "fear_test"
    assert json.loads(item["effect_json"]) == _valid_condition_effect()


def test_create_condition_rejects_effect_json_without_schema_v1(admin_db):
    bad = {
        "effect_category": "character_condition",
        "effects": [{"type": "narrative_only"}],
    }

    with pytest.raises(ValueError, match="invalid_effect_json_schema"):
        admin_cfg.create_condition(
            key="bad_condition",
            label="Bad",
            effect_json=json.dumps(bad),
        )


def test_create_item_accepts_effect_json_v1(admin_db):
    item = admin_cfg.create_item(
        key="ring_of_swiftness",
        label="Pierścień Zwinności",
        item_type="misc",
        effect_json=json.dumps(_valid_item_effect()),
    )

    assert item["key"] == "ring_of_swiftness"
    assert json.loads(item["effect_json"]) == _valid_item_effect()


def test_update_item_rejects_category_type_mismatch(admin_db):
    admin_cfg.create_item(
        key="simple_ring",
        label="Prosty pierścień",
        item_type="misc",
    )
    bad = {
        "schema_version": 1,
        "effect_category": "gear_bonus",
        "effects": [{"type": "heal_hp", "value": 5}],
    }

    with pytest.raises(ValueError, match="invalid_effect_json_schema"):
        admin_cfg.update_item(
            "simple_ring",
            label=None,
            item_type=None,
            description=None,
            value_gp=None,
            effect_json=json.dumps(bad),
            is_active=None,
            force=False,
        )


def test_import_catalog_snapshot_dry_run_rejects_invalid_condition_and_item_effects():
    payload = {
        "export_kind": "catalog_snapshot",
        "tables": {
            "game_config_stats": [{"key": "str", "label": "STR"}],
            "game_config_conditions": [
                {
                    "key": "fear_bad",
                    "label": "Fear",
                    "effect_json": {"schema_version": 1, "effect_category": "character_condition", "effects": []},
                }
            ],
            "game_config_items": [
                {
                    "key": "ring_bad",
                    "label": "Ring",
                    "effect_json": {
                        "schema_version": 1,
                        "effect_category": "gear_bonus",
                        "effects": [{"type": "heal_hp", "value": 3}],
                    },
                }
            ],
        },
    }

    result = transfer_mod.import_catalog_snapshot(payload, dry_run=True)

    assert result["ok"] is False
    assert any("game_config_conditions[0].effect_json" in err for err in result["errors"])
    assert any("game_config_items[0].effect_json" in err for err in result["errors"])


def test_import_config_dry_run_rejects_invalid_condition_effect_json():
    payload = {
        "config_version": "1.0.0",
        "tables": {
            "game_config_stats": [{"key": "str", "label": "STR", "description": "", "sort_order": 1}],
            "game_config_skills": [
                {
                    "key": "melee_attack",
                    "label": "Melee",
                    "linked_stat": "str",
                    "rank_ceiling": 5,
                    "sort_order": 1,
                    "description": "",
                }
            ],
            "game_config_dc": [{"key": "easy", "label": "Easy", "value": 10, "sort_order": 1, "description": ""}],
            "game_config_conditions": [
                {
                    "key": "fear_bad",
                    "label": "Fear",
                    "effect_json": {
                        "schema_version": 1,
                        "effect_category": "character_condition",
                        "effects": [{"type": "static_stat_modifier", "value": 2}],
                    },
                    "description": "",
                    "is_active": 1,
                }
            ],
        },
    }

    result = transfer_mod.import_config(payload, dry_run=True)

    assert result["ok"] is False
    assert any("game_config_conditions[0].effect_json" in err for err in result["errors"])
