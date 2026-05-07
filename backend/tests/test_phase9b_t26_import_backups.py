"""T26 - pre-import DB backups with retention."""

from __future__ import annotations

import os
import sqlite3
import sys
import time
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
            CREATE TABLE game_config_xp_rewards (
                key TEXT PRIMARY KEY,
                category TEXT,
                label TEXT,
                description TEXT,
                xp_amount INTEGER,
                is_active INTEGER,
                sort_order INTEGER,
                locked_at TEXT,
                created_at TEXT,
                updated_at TEXT
            );
            CREATE TABLE game_config_weapons (
                key TEXT PRIMARY KEY,
                label TEXT,
                damage_die TEXT,
                weapon_type TEXT,
                linked_stat TEXT,
                allowed_classes TEXT,
                two_handed INTEGER,
                finesse INTEGER,
                range_m INTEGER,
                targeting TEXT,
                aoe_radius_m REAL,
                magic_school TEXT,
                weight_kg REAL,
                description TEXT,
                note TEXT,
                value_gp INTEGER,
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
            CREATE TABLE game_config_items (
                key TEXT PRIMARY KEY,
                label TEXT,
                item_type TEXT,
                description TEXT,
                value_gp INTEGER,
                effect_json TEXT,
                is_active INTEGER,
                locked_at TEXT,
                created_at TEXT,
                updated_at TEXT,
                note TEXT,
                weight_kg REAL,
                ac_bonus INTEGER,
                charges INTEGER,
                ai_generated INTEGER,
                approved INTEGER,
                allowed_classes TEXT
            );
            CREATE TABLE game_config_consumables (
                key TEXT PRIMARY KEY,
                label TEXT,
                description TEXT,
                effect_type TEXT,
                effect_dice TEXT,
                effect_bonus INTEGER,
                effect_target TEXT,
                weight_kg REAL,
                charges INTEGER,
                base_price INTEGER,
                note TEXT,
                is_active INTEGER,
                locked_at TEXT,
                created_at TEXT,
                updated_at TEXT
            );
            CREATE TABLE game_config_loot_tables (
                key TEXT PRIMARY KEY,
                label TEXT,
                description TEXT,
                is_active INTEGER,
                gold_min INTEGER,
                gold_max INTEGER,
                locked_at TEXT,
                created_at TEXT,
                updated_at TEXT
            );
            CREATE TABLE game_config_loot_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                loot_table_key TEXT,
                item_key TEXT,
                weapon_key TEXT,
                weight INTEGER,
                qty_min INTEGER,
                qty_max INTEGER
            );
            """
        )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def transfer_db(tmp_path, monkeypatch):
    db = tmp_path / "t26_import.db"
    _init_transfer_db(db)
    backup_dir = tmp_path / "backups"
    monkeypatch.setattr(transfer_mod, "DB_PATH", str(db))
    monkeypatch.setattr(transfer_mod, "IMPORT_BACKUP_DIR", str(backup_dir))
    monkeypatch.setattr(transfer_mod, "IMPORT_BACKUP_KEEP_LAST", 10)
    monkeypatch.setattr(transfer_mod, "IMPORT_BACKUP_MAX_AGE_DAYS", 30)
    monkeypatch.setattr(transfer_mod, "IMPORT_BACKUP_MIN_KEEP", 3)
    return db, backup_dir


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


def _minimal_snapshot_payload() -> dict:
    return {
        "export_kind": "catalog_snapshot",
        "tables": {
            "game_config_stats": [{"key": "str", "label": "STR", "description": "", "sort_order": 1}],
            "game_config_skills": [],
            "game_config_dc": [],
            "game_config_xp_rewards": [],
            "game_config_weapons": [],
            "game_config_conditions": [],
            "game_config_items": [],
            "game_config_consumables": [],
            "game_config_loot_tables": [],
            "game_config_enemies": [],
            "game_config_loot_entries": [],
        },
    }


def test_import_config_dry_run_does_not_create_backup(transfer_db):
    _db, backup_dir = transfer_db

    result = transfer_mod.import_config(_minimal_import_payload(), dry_run=True)

    assert result["ok"] is True
    assert not backup_dir.exists()


def test_import_config_commit_creates_backup_and_prunes_old_files(transfer_db):
    _db, backup_dir = transfer_db
    backup_dir.mkdir(parents=True, exist_ok=True)

    old_names: list[str] = []
    old_timestamp = time.time() - 40 * 24 * 3600
    for idx in range(5):
        path = backup_dir / f"ai_gm_pre_import_config_old_{idx}.db"
        path.write_bytes(f"old-{idx}".encode("utf-8"))
        os.utime(path, (old_timestamp + idx, old_timestamp + idx))
        old_names.append(path.name)

    result = transfer_mod.import_config(_minimal_import_payload(), dry_run=False)

    assert result["ok"] is True
    assert result["backup"]["filename"].startswith("ai_gm_pre_import_config_")
    remaining = sorted(path.name for path in backup_dir.glob("ai_gm_pre_import_*.db"))
    assert len(remaining) == 4
    assert old_names[0] not in remaining
    assert old_names[1] not in remaining
    assert sorted(result["backup"]["pruned"]) == sorted([old_names[0], old_names[1]])


def test_import_catalog_snapshot_commit_creates_backup_metadata(transfer_db):
    _db, backup_dir = transfer_db

    result = transfer_mod.import_catalog_snapshot(_minimal_snapshot_payload(), dry_run=False)

    assert result["ok"] is True
    assert result["backup"]["filename"].startswith("ai_gm_pre_import_catalog_snapshot_")
    assert (backup_dir / result["backup"]["filename"]).is_file()
