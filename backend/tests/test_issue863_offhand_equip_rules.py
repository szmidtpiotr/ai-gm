"""TDD: Issue #863 — reguły equip off-hand spójne z mechaniką dual-wield (#598).

Decyzja Piotra (zakres pkt 1-3):
  1. Ręka pomocnicza przyjmuje TYLKO lekkie bronie (finesse) 'either' + tarcze
     (off_hand_only). Ciężka broń 'either' (np. długi miecz) → odrzucona.
  2. Broń dwuręczna (two_handed) w głównej ręce → off-hand zablokowany z komunikatem.
  3. Te same reguły na froncie (app.js) i w backendzie (loot_service.equip_item).

Backend gate testowany na realnym `loot_service.equip_item` (tmp DB, patch LOOT_DB_PATH).
Frontend mirror testowany jako reimplementacja predykatów app.js w Pythonie (jak #770).
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services import loot_service as ls


# ─── Schemat + seed ──────────────────────────────────────────────────────────

def _schema_sql() -> str:
    return """
    CREATE TABLE characters (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL
    );
    INSERT INTO characters (id, name) VALUES (1, 'Hero');

    CREATE TABLE game_config_items (
      key TEXT PRIMARY KEY,
      label TEXT NOT NULL,
      item_type TEXT NOT NULL DEFAULT 'misc',
      armor_coverage TEXT,
      is_active INTEGER NOT NULL DEFAULT 1
    );
    CREATE TABLE game_config_weapons (
      key TEXT PRIMARY KEY,
      label TEXT NOT NULL,
      damage_die TEXT,
      linked_stat TEXT,
      weapon_type TEXT,
      weapon_slot TEXT NOT NULL DEFAULT 'main_hand',
      two_handed INTEGER NOT NULL DEFAULT 0,
      finesse INTEGER NOT NULL DEFAULT 0,
      range_m INTEGER,
      effect_json TEXT,
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
      slot TEXT
    );

    -- Bronie testowe
    INSERT INTO game_config_weapons (key, label, weapon_slot, two_handed, finesse) VALUES
      ('longsword',  'Długi Miecz', 'either',        0, 0),  -- ciężka 'either'
      ('dagger',     'Sztylet',     'either',        0, 1),  -- lekka 'either' (finesse)
      ('greataxe',   'Topór 2H',    'two_handed',    1, 0),  -- dwuręczna
      ('buckler',    'Buklerz',     'off_hand_only', 0, 0);  -- broń-tarcza off_hand_only

    -- Tarcza jako pancerz (off_hand)
    INSERT INTO game_config_items (key, label, item_type, armor_coverage) VALUES
      ('shield_wood', 'Drewniana Tarcza', 'armor', NULL);

    -- Ekwipunek bohatera
    INSERT INTO character_inventory (id, character_id, weapon_key) VALUES
      (10, 1, 'longsword'),
      (11, 1, 'dagger'),
      (12, 1, 'greataxe'),
      (13, 1, 'buckler');
    INSERT INTO character_inventory (id, character_id, item_key) VALUES
      (14, 1, 'shield_wood');
    """


@pytest.fixture
def db(tmp_path, monkeypatch):
    p = str(tmp_path / "issue863.db")
    conn = sqlite3.connect(p)
    conn.executescript(_schema_sql())
    conn.commit()
    conn.close()
    monkeypatch.setattr(ls, "LOOT_DB_PATH", p)
    # equip_item kończy się get_character_inventory() — odetnij od game_items, zwróć stub.
    monkeypatch.setattr(
        ls, "get_character_inventory",
        lambda cid: [{"id": iid, "slot": s, "equipped": 1}
                     for (iid, s) in _equipped_rows(p)]
    )
    return p


def _equipped_rows(db_path: str):
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(
            "SELECT id, slot FROM character_inventory WHERE equipped = 1"
        ).fetchall()
    finally:
        conn.close()


def _equip_main(db_path: str, inv_id: int, slot: str = "main_hand") -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "UPDATE character_inventory SET equipped = 1, slot = ? WHERE id = ?",
            (slot, inv_id),
        )
        conn.commit()
    finally:
        conn.close()


# ─── Test główny — backend gate (pkt 1) ──────────────────────────────────────

def test_heavy_either_rejected_in_offhand(db):
    """Ciężka broń 'either' (długi miecz) w ręce pomocniczej → odrzucona."""
    with pytest.raises(ValueError) as exc:
        ls.equip_item(1, 10, "off_hand")  # longsword
    assert "ciężka" in str(exc.value).lower() or "lekkie" in str(exc.value).lower()


def test_light_either_allowed_in_offhand(db):
    """Lekka broń 'either' (sztylet/finesse) w ręce pomocniczej → przyjęta."""
    out = ls.equip_item(1, 11, "off_hand")  # dagger
    assert int(out["id"]) == 11 and out["slot"] == "off_hand"


def test_buckler_off_hand_only_allowed(db):
    """Broń-tarcza (off_hand_only) w ręce pomocniczej → przyjęta jak dotąd."""
    out = ls.equip_item(1, 13, "off_hand")  # buckler
    assert int(out["id"]) == 13 and out["slot"] == "off_hand"


# ─── Test — backend gate (pkt 2) ─────────────────────────────────────────────

def test_two_handed_main_blocks_offhand(db):
    """Broń dwuręczna w głównej ręce → off-hand zablokowany z komunikatem."""
    _equip_main(db, 12)  # greataxe (two_handed) w main_hand
    with pytest.raises(ValueError) as exc:
        ls.equip_item(1, 11, "off_hand")  # próba: lekki sztylet do off
    assert "dwuręczn" in str(exc.value).lower()


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_either_in_main_hand_still_works(db):
    """Stare zachowanie: 'either' do głównej ręki działa bez zmian (także ciężka)."""
    out = ls.equip_item(1, 10, "main_hand")  # longsword main
    assert int(out["id"]) == 10 and out["slot"] == "main_hand"


def test_off_hand_only_cannot_go_main_hand(db):
    """Backward compat: broń off_hand_only nadal nie wchodzi do głównej ręki."""
    with pytest.raises(ValueError):
        ls.equip_item(1, 13, "main_hand")  # buckler → main → błąd


# ─── Frontend mirror — reimplementacja predykatów app.js (#770 wzór) ──────────

def _fits_offhand(item: dict, slot: str) -> bool:
    """Mirror app.js _itemFitsSlot__weapon (post-#863)."""
    ws = str(item.get("weapon_slot") or "main_hand").lower()
    if slot == "main_hand":
        return ws in ("main_hand", "two_handed", "either")
    if slot == "off_hand":
        return ws == "off_hand_only" or (ws == "either" and item.get("is_light") is True)
    return False


def _pick_slot(item: dict, occupied: dict) -> str:
    """Mirror app.js _invPickEquipSlot weapon branch (post-#863)."""
    ws = str(item.get("weapon_slot") or "main_hand").lower()
    if ws == "two_handed":
        return "main_hand"
    if ws == "off_hand_only":
        return "off_hand"
    if ws == "either":
        return "off_hand" if (occupied.get("main_hand") and item.get("is_light") is True) else "main_hand"
    return "main_hand"


def test_front_fits_offhand_light_either_true():
    assert _fits_offhand({"weapon_slot": "either", "is_light": True}, "off_hand") is True


def test_front_fits_offhand_heavy_either_false():
    assert _fits_offhand({"weapon_slot": "either", "is_light": False}, "off_hand") is False


def test_front_fits_offhand_shield_true():
    assert _fits_offhand({"weapon_slot": "off_hand_only"}, "off_hand") is True


def test_front_pick_heavy_either_goes_main_when_occupied():
    """Ciężka 'either' przy zajętej głównej ręce → nadal main (zastąpi), nie off."""
    slot = _pick_slot({"weapon_slot": "either", "is_light": False}, {"main_hand": True})
    assert slot == "main_hand"


def test_front_pick_light_either_goes_off_when_occupied():
    slot = _pick_slot({"weapon_slot": "either", "is_light": True}, {"main_hand": True})
    assert slot == "off_hand"
