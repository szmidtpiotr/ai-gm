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
        fx.create_tables(conn, "game_config_stats", "game_config_weapons")
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
            INSERT INTO game_config_stats (key, label) VALUES ('STR', 'Strength'), ('DEX', 'Dexterity');
            """
        )
        conn.commit()
    finally:
        conn.close()


def test_create_weapon_aoe_and_single_validation(tmp_path, monkeypatch):
    db = tmp_path / "t22.db"
    _seed_db(str(db))
    monkeypatch.setattr(admin_config, "DB_PATH", str(db))

    row = admin_config.create_weapon(
        key="fire_bolt",
        label="Fire Bolt",
        damage_die="1d8",
        linked_stat="DEX",
        allowed_classes=["scholar"],
        weapon_type="spell",
        targeting="aoe_radius",
        aoe_radius_m=3.5,
        magic_school="fire",
        value_gp=125,
    )
    assert row["targeting"] == "aoe_radius"
    assert float(row["aoe_radius_m"]) == 3.5
    assert row["magic_school"] == "fire"
    assert int(row["value_gp"]) == 125

    row2 = admin_config.create_weapon(
        key="shortsword_t22",
        label="Shortsword",
        damage_die="1d6",
        linked_stat="STR",
        allowed_classes=["warrior"],
        weapon_type="melee",
        targeting="single",
        aoe_radius_m=10.0,
    )
    assert row2["targeting"] == "single"
    assert row2["aoe_radius_m"] is None


def test_update_weapon_targeting_clears_aoe(tmp_path, monkeypatch):
    db = tmp_path / "t22_update.db"
    _seed_db(str(db))
    monkeypatch.setattr(admin_config, "DB_PATH", str(db))
    admin_config.create_weapon(
        key="storm_wave",
        label="Storm Wave",
        damage_die="1d10",
        linked_stat="DEX",
        allowed_classes=["scholar"],
        weapon_type="spell",
        targeting="aoe_radius",
        aoe_radius_m=4.0,
    )

    updated = admin_config.update_weapon(
        "storm_wave",
        label=None,
        damage_die=None,
        linked_stat=None,
        allowed_classes=None,
        is_active=None,
        force=False,
        targeting="single",
        aoe_radius_m=None,
    )
    assert updated["targeting"] == "single"
    assert updated["aoe_radius_m"] is None


def test_admin_api_rejects_invalid_aoe(tmp_path, monkeypatch):
    db = tmp_path / "t22_api.db"
    _seed_db(str(db))
    monkeypatch.setattr(admin_config, "DB_PATH", str(db))

    app.dependency_overrides[require_admin_token] = lambda: None
    client = TestClient(app)
    try:
        resp = client.post(
            "/api/admin/weapons",
            json={
                "key": "bad_aoe",
                "label": "Bad AOE",
                "damage_die": "1d6",
                "linked_stat": "DEX",
                "allowed_classes": ["scholar"],
                "weapon_type": "spell",
                "targeting": "aoe_radius",
                "aoe_radius_m": None,
            },
        )
        assert resp.status_code == 422
        assert "aoe_radius_m must be > 0" in resp.json()["detail"]
    finally:
        client.close()
        app.dependency_overrides.pop(require_admin_token, None)


def test_admin_api_accepts_value_gp(tmp_path, monkeypatch):
    db = tmp_path / "t22_api_price.db"
    _seed_db(str(db))
    monkeypatch.setattr(admin_config, "DB_PATH", str(db))

    app.dependency_overrides[require_admin_token] = lambda: None
    client = TestClient(app)
    try:
        create = client.post(
            "/api/admin/weapons",
            json={
                "key": "priced_wand",
                "label": "Priced Wand",
                "damage_die": "1d6",
                "linked_stat": "DEX",
                "allowed_classes": ["scholar"],
                "weapon_type": "spell",
                "targeting": "single",
                "value_gp": 77,
            },
        )
        assert create.status_code == 200, create.text
        assert int(create.json()["item"]["value_gp"]) == 77
    finally:
        client.close()
        app.dependency_overrides.pop(require_admin_token, None)
