"""T19 — warnings and guidance for config import vs catalog snapshot."""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services import admin_config_transfer as transfer_mod


def _init_transfer_db(path: Path) -> None:
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

            CREATE TABLE game_config_meta (
                key TEXT PRIMARY KEY,
                value TEXT
            );
            INSERT INTO game_config_meta(key, value) VALUES ('config_version', '1.0.0');

            CREATE TABLE game_config_stats (
                key TEXT PRIMARY KEY,
                label TEXT,
                description TEXT,
                sort_order INTEGER,
                locked_at TEXT
            );
            CREATE TABLE game_config_skills (
                key TEXT PRIMARY KEY,
                label TEXT,
                linked_stat TEXT,
                rank_ceiling INTEGER,
                sort_order INTEGER,
                locked_at TEXT,
                description TEXT
            );
            CREATE TABLE game_config_dc (
                key TEXT PRIMARY KEY,
                label TEXT,
                value INTEGER,
                sort_order INTEGER,
                locked_at TEXT,
                description TEXT
            );
            CREATE TABLE game_config_weapons (
                key TEXT PRIMARY KEY,
                label TEXT,
                damage_die TEXT,
                linked_stat TEXT,
                allowed_classes TEXT,
                is_active INTEGER,
                locked_at TEXT,
                created_at TEXT,
                updated_at TEXT
            );
            CREATE TABLE game_config_enemies (
                key TEXT PRIMARY KEY,
                label TEXT,
                hp_base INTEGER,
                ac_base INTEGER,
                attack_bonus INTEGER,
                dex_modifier INTEGER,
                damage_die TEXT,
                description TEXT,
                is_active INTEGER,
                locked_at TEXT,
                created_at TEXT,
                updated_at TEXT
            );
            CREATE TABLE game_config_conditions (
                key TEXT PRIMARY KEY,
                label TEXT,
                effect_json TEXT NOT NULL,
                description TEXT,
                is_active INTEGER,
                locked_at TEXT,
                created_at TEXT,
                updated_at TEXT
            );
            """
        )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def transfer_db(tmp_path, monkeypatch):
    db = tmp_path / "t19_import.db"
    _init_transfer_db(db)
    monkeypatch.setattr(transfer_mod, "DB_PATH", str(db))
    return db


def _minimal_import_payload() -> dict:
    return {
        "config_version": "1.0.0",
        "tables": {
            "game_config_stats": [{"key": "str", "label": "STR", "description": "", "sort_order": 1}],
            "game_config_skills": [
                {
                    "key": "attack",
                    "label": "Attack",
                    "linked_stat": "STR",
                    "rank_ceiling": 5,
                    "sort_order": 1,
                    "description": "",
                }
            ],
            "game_config_dc": [{"key": "easy", "label": "Easy", "value": 10, "sort_order": 1, "description": ""}],
        },
    }


def test_export_config_marks_narrow_bundle(transfer_db):
    payload = transfer_mod.export_config()
    assert payload["export_kind"] == "config_bundle"
    assert "catalog-snapshot" in str(payload["notes"])


def test_import_config_dry_run_warns_for_catalog_snapshot_file(transfer_db):
    payload = _minimal_import_payload()
    payload["export_kind"] = "catalog_snapshot"
    payload["tables"]["game_config_items"] = [{"key": "health_potion", "label": "Potion"}]
    payload["tables"]["game_config_loot_entries"] = [{"item_key": "health_potion"}]

    result = transfer_mod.import_config(payload, dry_run=True)

    assert result["ok"] is True
    assert any("catalog_snapshot" in msg for msg in result["warnings"])
    assert any("game_config_items" in msg and "game_config_loot_entries" in msg for msg in result["warnings"])


def test_import_config_dry_run_warns_about_narrow_weapon_schema(transfer_db):
    payload = _minimal_import_payload()
    payload["tables"]["game_config_weapons"] = [
        {
            "key": "rapier",
            "label": "Rapier",
            "damage_die": "1d8",
            "linked_stat": "DEX",
            "allowed_classes": "[]",
            "weapon_type": "melee",
            "finesse": 1,
            "range_m": 2,
            "targeting_profile_json": {"shape": "cone"},
        }
    ]

    result = transfer_mod.import_config(payload, dry_run=True)

    assert result["ok"] is True
    joined = " ".join(result["warnings"])
    assert "targeting_profile_json" in joined


def test_import_catalog_snapshot_dry_run_warns_that_meta_is_ignored():
    payload = {
        "export_kind": "catalog_snapshot",
        "tables": {
            "game_config_meta": [{"key": "config_version", "value": "9.9.9"}],
            "game_config_stats": [{"key": "str", "label": "STR"}],
        },
    }

    result = transfer_mod.import_catalog_snapshot(payload, dry_run=True)

    assert result["ok"] is True
    assert any("game_config_meta" in msg for msg in result["warnings"])
