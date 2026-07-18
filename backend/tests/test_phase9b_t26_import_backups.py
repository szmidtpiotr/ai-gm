"""T26 - pre-import DB backups with retention."""

from __future__ import annotations

import os
import sqlite3
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _fixtures_schema import table_sql

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

            """ + table_sql("game_config_meta") + """
            INSERT INTO game_config_meta(key, value) VALUES ('config_version', '1.0.0');

            """ + table_sql("game_config_stats") + """
            """ + table_sql("game_config_skills") + """
            """ + table_sql("game_config_dc") + """
            """ + table_sql("game_config_xp_rewards") + """
            """ + table_sql("game_config_weapons") + """
            """ + table_sql("game_config_enemies") + """
            """ + table_sql("game_config_conditions") + """
            """ + table_sql("game_config_items") + """
            """ + table_sql("game_config_consumables") + """
            """ + table_sql("game_config_loot_tables") + """
            """ + table_sql("game_config_loot_entries") + """
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
