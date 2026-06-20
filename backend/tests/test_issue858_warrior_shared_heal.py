"""TDD: Issue #858 — bandaż jako uniwersalne (class-agnostic) leczenie w walce.

Decyzja Piotra (korekta zakresu): wspólne mechaniki leczenia (mikstura, bandaż)
MUSZĄ być dostępne dla KAŻDEJ klasy — w tym maga. Bandaż NIE jest warrior-only.
Wojownik dostaje bandaż jako bazowe leczenie w walce (odpowiednik mikstury/spella maga),
a sam bandaż leczy SIEBIE (effect_target='self'), nie sojusznika.
"""
import json
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services import loot_service as loot_mod

# ─── Isolated DB (kontrakt mechaniki, bez żywej bazy) ────────────────────────

_BASE_SCHEMA = """
CREATE TABLE characters (
    id INTEGER PRIMARY KEY,
    campaign_id INTEGER NOT NULL DEFAULT 1,
    name TEXT NOT NULL,
    sheet_json TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE game_config_items (
    key TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    item_type TEXT NOT NULL DEFAULT 'misc',
    description TEXT NOT NULL DEFAULT '',
    effect_json TEXT,
    charges INTEGER NOT NULL DEFAULT 1,
    approved INTEGER NOT NULL DEFAULT 1,
    is_active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE game_config_conditions (
    key TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    effect_json TEXT NOT NULL DEFAULT '{}',
    stackable INTEGER NOT NULL DEFAULT 0,
    is_active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE game_config_weapons (
    key TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE game_config_consumables (
    key TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    effect_type TEXT NOT NULL DEFAULT 'misc',
    effect_dice TEXT,
    effect_bonus INTEGER NOT NULL DEFAULT 0,
    effect_target TEXT NOT NULL DEFAULT 'self',
    is_active INTEGER NOT NULL DEFAULT 1,
    effect_json TEXT
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
CREATE TABLE active_combat (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL,
    character_id INTEGER NOT NULL,
    round INTEGER NOT NULL DEFAULT 1,
    turn_order TEXT NOT NULL DEFAULT '[]',
    current_turn TEXT NOT NULL DEFAULT '',
    combatants TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'active',
    ended_reason TEXT,
    updated_at TEXT
);
"""


def _make_db(path: Path, *, archetype: str) -> int:
    """Buduje izolowaną bazę z jednym bohaterem danej klasy + bandażem w plecaku.
    Zwraca inventory_id bandaża."""
    conn = sqlite3.connect(str(path))
    conn.executescript(_BASE_SCHEMA)
    sheet = json.dumps({
        "archetype": archetype,
        "current_hp": 10,
        "max_hp": 30,
        "current_mana": 0,
        "max_mana": 0,
        "conditions": [],
    })
    conn.execute("INSERT INTO characters (id, campaign_id, name, sheet_json) VALUES (1, 1, 'Hero', ?)", (sheet,))
    # bandaż = self-heal, class-agnostic (brak kolumny allowed_classes w consumables)
    conn.execute(
        "INSERT INTO game_config_consumables (key, label, effect_type, effect_dice, effect_bonus, effect_target) "
        "VALUES ('bandage', 'Bandaż', 'heal_hp', '1d4', 0, 'self')"
    )
    row = conn.execute(
        "INSERT INTO character_inventory (character_id, consumable_key, quantity) VALUES (1, 'bandage', 1) RETURNING id"
    ).fetchone()
    inv_id = row[0]
    conn.commit()
    conn.close()
    return inv_id


# ─── FAZA 1 RED: testy na żywej bazie DEV (failują przed migracją) ───────────

def test_bandage_is_self_target_not_ally():
    """Bandaż musi leczyć SIEBIE (self), nie sojusznika (ally) — to bazowe leczenie gracza."""
    conn = sqlite3.connect("/data/ai_gm.db")
    try:
        row = conn.execute(
            "SELECT effect_type, effect_target FROM game_config_consumables WHERE key = 'bandage'"
        ).fetchone()
    finally:
        conn.close()
    assert row is not None, "Bandaż musi istnieć w katalogu konsumabli"
    assert row[0] == "heal_hp", f"Bandaż musi być heal_hp, jest {row[0]!r}"
    assert row[1] == "self", f"Bandaż effect_target musi być 'self', jest {row[1]!r} (#858)"


def test_warrior_starter_includes_bandage():
    """Wojownik musi startować z bandażem — bazowe leczenie w walce (odpowiednik mikstury maga)."""
    conn = sqlite3.connect("/data/ai_gm.db")
    try:
        row = conn.execute(
            "SELECT starter_items_json FROM game_config_archetypes WHERE key = 'warrior'"
        ).fetchone()
    finally:
        conn.close()
    assert row is not None, "Archetyp wojownika musi istnieć"
    items = json.loads(row[0] or "[]")
    keys = {str(it.get("consumable_key") or "") for it in items if isinstance(it, dict)}
    assert "bandage" in keys, f"Starter wojownika musi zawierać bandaż, ma: {sorted(keys)} (#858)"


# ─── Kontrakt: bandaż class-agnostic (NIE warrior-only) ──────────────────────

def test_warrior_can_use_bandage_to_heal(tmp_path, monkeypatch):
    """Wojownik leczy SIEBIE bandażem w walce."""
    db = tmp_path / "w858.db"
    inv_id = _make_db(db, archetype="warrior")
    monkeypatch.setattr(loot_mod, "LOOT_DB_PATH", str(db))

    result = loot_mod.use_inventory_item(1, inv_id)

    heals = [e for e in result["effects_applied"] if e.get("type") == "heal_hp"]
    assert heals and heals[0]["amount"] >= 1, "Wojownik musi odzyskać HP po użyciu bandaża"
    assert result["character_state"]["current_hp"] > 10, "HP wojownika musi wzrosnąć"


def test_scholar_can_also_use_bandage(tmp_path, monkeypatch):
    """Mag (Uczony) TAKŻE może użyć bandaża — leczenie class-agnostic, NIE warrior-only."""
    db = tmp_path / "s858.db"
    inv_id = _make_db(db, archetype="scholar")
    monkeypatch.setattr(loot_mod, "LOOT_DB_PATH", str(db))

    result = loot_mod.use_inventory_item(1, inv_id)

    heals = [e for e in result["effects_applied"] if e.get("type") == "heal_hp"]
    assert heals and heals[0]["amount"] >= 1, "Mag musi móc odzyskać HP bandażem (shared heal)"
    assert result["character_state"]["current_hp"] > 10, "HP maga musi wzrosnąć"
