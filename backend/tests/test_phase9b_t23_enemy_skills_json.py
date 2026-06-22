import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _fixtures_schema as fx

from fastapi.testclient import TestClient

from app.main import app
from app.routers.admin import require_admin_token
from app.services import admin_config


def _seed_db(path: str) -> None:
    conn = sqlite3.connect(path)
    try:
        fx.create_tables(conn, "game_config_enemies", "game_config_loot_tables", "game_config_conditions")
        conn.executescript(
            """
            CREATE TABLE admin_audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                table_name TEXT NOT NULL,
                row_key TEXT,
                operation TEXT NOT NULL,
                old_values TEXT,
                new_values TEXT,
                performed_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            """
        )
        conn.commit()
    finally:
        conn.close()


def test_create_and_update_enemy_skills_json(tmp_path, monkeypatch):
    db = tmp_path / "t23_enemy.db"
    _seed_db(str(db))
    monkeypatch.setattr(admin_config, "DB_PATH", str(db))

    created = admin_config.create_enemy(
        key="bandit_t23",
        label="Bandit",
        hp_base=10,
        ac_base=11,
        attack_bonus=2,
        damage_die="1d6",
        skills_json={"awareness": 2, "stealth": 1},
    )
    assert created["skills_json"] == {"awareness": 2, "stealth": 1}

    updated = admin_config.update_enemy(
        "bandit_t23",
        label=None,
        hp_base=None,
        ac_base=None,
        attack_bonus=None,
        dex_modifier=None,
        damage_die=None,
        description=None,
        tier=None,
        attacks_per_turn=None,
        damage_bonus=None,
        damage_type=None,
        xp_award=None,
        conditions_immune=None,
        skills_json={"awareness": 3},
        loot_table_key=None,
        note=None,
        drop_chance=None,
        is_active=None,
        force=False,
    )
    assert updated["skills_json"] == {"awareness": 3}

    rows = admin_config.list_enemies()
    assert rows[0]["skills_json"] == {"awareness": 3}


def test_admin_api_rejects_invalid_skills_json(tmp_path, monkeypatch):
    db = tmp_path / "t23_enemy_api.db"
    _seed_db(str(db))
    monkeypatch.setattr(admin_config, "DB_PATH", str(db))

    app.dependency_overrides[require_admin_token] = lambda: None
    client = TestClient(app)
    try:
        resp = client.post(
            "/api/admin/enemies",
            json={
                "key": "bad_enemy_t23",
                "label": "Bad Enemy",
                "hp_base": 8,
                "ac_base": 10,
                "attack_bonus": 1,
                "damage_die": "1d6",
                "skills_json": {"BAD KEY!": 1},
            },
        )
        assert resp.status_code == 422
        assert "skills_json" in resp.json()["detail"]
    finally:
        client.close()
        app.dependency_overrides.pop(require_admin_token, None)
