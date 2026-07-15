"""TDD: Issue #1397 — rozdzielenie Broń dwuręczna (two_handed) vs Oburęczność (dual_wield)
i jawne oznaczanie broni kolumną `light`.

Silnik JUŻ rozdziela oba skille (#598). Ta zmiana dokłada:
  • jawną kolumnę `game_config_weapons.light` (NULL=fallback na finesse, 0/1=decyzja admina),
    przepiętą przez dual-write do game_items.weapon_data.light i honorowaną przez is_light_weapon,
  • pola `light` w modelach admin (WeaponCreateReq/WeaponPatchReq),
  • rename labelu dual_wield → "Oburęczność".
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _fixtures_schema as fx

from app.services import admin_config
from app.services.game_items_service import get_weapon_row
from app.services.weapon_rules import is_light_weapon


# ─── Seed: game_config_weapons(+light) + game_items + stats + audit ───────────

_GAME_ITEMS_SQL = """
CREATE TABLE game_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  key TEXT UNIQUE NOT NULL,
  kind TEXT NOT NULL,
  label TEXT NOT NULL DEFAULT '',
  description TEXT DEFAULT '',
  price_gp REAL DEFAULT 0,
  effect_json TEXT DEFAULT NULL,
  equip_slot TEXT DEFAULT NULL,
  rarity INTEGER DEFAULT 1,
  min_level INTEGER DEFAULT 1,
  location_tags TEXT DEFAULT '[]',
  created_by TEXT DEFAULT 'seed',
  approved INTEGER DEFAULT 1,
  is_active INTEGER DEFAULT 1,
  weapon_data TEXT DEFAULT '{}',
  item_data TEXT DEFAULT '{}',
  weight_kg REAL DEFAULT 0,
  note TEXT DEFAULT NULL,
  locked_at TEXT DEFAULT NULL,
  created_at TEXT DEFAULT (datetime('now')),
  updated_at TEXT DEFAULT (datetime('now'))
);
"""


def _seed_db(path: str) -> None:
    conn = sqlite3.connect(path)
    try:
        fx.create_tables(conn, "game_config_stats", "game_config_weapons")
        conn.executescript(
            _GAME_ITEMS_SQL
            + """
            CREATE TABLE admin_audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                table_name TEXT NOT NULL,
                row_key TEXT,
                operation TEXT NOT NULL,
                old_values TEXT,
                new_values TEXT,
                performed_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            INSERT INTO game_config_stats (key, label) VALUES ('STR','Strength'),('DEX','Dexterity');
            """
        )
        conn.commit()
    finally:
        conn.close()


def _make_db(tmp_path, monkeypatch) -> str:
    db = str(tmp_path / "issue1397.db")
    _seed_db(db)
    monkeypatch.setattr(admin_config, "DB_PATH", str(db))
    return db


# ─── Pydantic model gate (extra="forbid") ─────────────────────────────────────

def test_weapon_patch_req_accepts_light():
    from app.routers.admin import WeaponPatchReq
    req = WeaponPatchReq(light=True)
    assert req.light is True
    assert WeaponPatchReq().light is None  # domyślnie None → brak zmiany


def test_weapon_create_req_accepts_light():
    from app.routers.admin import WeaponCreateReq
    req = WeaponCreateReq(
        key="lightblade", label="Lekkie Ostrze", damage_die="1d6",
        linked_stat="DEX", allowed_classes=["warrior"], light=True,
    )
    assert req.light is True


# ─── Write plumbing: update_weapon persists light → game_config_weapons ────────

def test_update_weapon_persists_light(tmp_path, monkeypatch):
    db = _make_db(tmp_path, monkeypatch)
    admin_config.create_weapon(
        key="shortsword_x", label="Krótki Miecz", damage_die="1d6",
        linked_stat="STR", allowed_classes=["warrior"], weapon_type="melee",
    )
    admin_config.update_weapon(
        "shortsword_x", label=None, damage_die=None, linked_stat=None,
        allowed_classes=None, is_active=None, force=False, light=True,
    )
    conn = sqlite3.connect(db)
    row = conn.execute("SELECT light FROM game_config_weapons WHERE key='shortsword_x'").fetchone()
    conn.close()
    assert row[0] == 1


# ─── Read plumbing: game_items.weapon_data.light → get_weapon_row → is_light ──

def test_light_reaches_is_light_weapon_via_game_items(tmp_path, monkeypatch):
    db = _make_db(tmp_path, monkeypatch)
    # ciężki miecz (finesse=0) jawnie oznaczony jako lekki → oburęczność mimo braku finesse
    admin_config.create_weapon(
        key="featherblade", label="Piórowe Ostrze", damage_die="1d6",
        linked_stat="STR", allowed_classes=["warrior"], weapon_type="melee",
        light=True,
    )
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    row = get_weapon_row(conn, "featherblade")
    conn.close()
    assert row is not None
    assert row.get("light") == 1
    assert is_light_weapon(row) is True  # jawny light wygrywa z finesse=0


def test_light_null_falls_back_to_finesse(tmp_path, monkeypatch):
    db = _make_db(tmp_path, monkeypatch)
    # finezyjny sztylet BEZ jawnego light → fallback: lekki
    admin_config.create_weapon(
        key="dagger_x", label="Sztylet", damage_die="1d4",
        linked_stat="DEX", allowed_classes=["warrior"], weapon_type="melee",
        finesse=True,
    )
    # ciężki miecz BEZ light i BEZ finesse → NIE lekki
    admin_config.create_weapon(
        key="heavy_x", label="Ciężki Miecz", damage_die="1d10",
        linked_stat="STR", allowed_classes=["warrior"], weapon_type="melee",
    )
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    dagger = get_weapon_row(conn, "dagger_x")
    heavy = get_weapon_row(conn, "heavy_x")
    conn.close()
    assert dagger.get("light") in (None,)      # brak jawnej decyzji
    assert is_light_weapon(dagger) is True      # fallback finesse
    assert is_light_weapon(heavy) is False


def test_explicit_light_zero_blocks_finesse_weapon(tmp_path, monkeypatch):
    db = _make_db(tmp_path, monkeypatch)
    # rapier: finesse=1 ale admin jawnie mówi light=0 → NIE kwalifikuje się do oburęczności
    admin_config.create_weapon(
        key="rapier_x", label="Rapier", damage_die="1d8",
        linked_stat="DEX", allowed_classes=["warrior"], weapon_type="melee",
        finesse=True, light=False,
    )
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    row = get_weapon_row(conn, "rapier_x")
    conn.close()
    assert row.get("light") == 0
    assert is_light_weapon(row) is False


# ─── Label rename dual_wield → Oburęczność ────────────────────────────────────

def test_dual_wield_label_renamed_to_oburecznosc():
    src = Path(__file__).resolve().parent.parent / "app" / "migrations_admin.py"
    text = src.read_text(encoding="utf-8")
    assert "Oburęczność" in text
    # stary mylący label nie jest już seedowany jako wartość początkowa
    assert "'dual_wield', 'Walka dwoma broniami'" not in text
