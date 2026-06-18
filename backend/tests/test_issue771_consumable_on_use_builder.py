"""TDD: Issue #771 — consumable on-use effect builder: damage_enemy, apply_condition(target=enemy), backfill 14 items."""
import json
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services import loot_service as loot_mod

# ─── DB setup helpers ────────────────────────────────────────────────────────

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

_ON_FIRE_COND = json.dumps({
    "schema_version": 1,
    "effect_category": "character_condition",
    "effects": [{"type": "dot", "value": "2d6", "damage_type": "fire"}],
})

_WEAKENED_COND = json.dumps({
    "schema_version": 1,
    "effect_category": "character_condition",
    "effects": [{"type": "static_stat_modifier", "stat": "STR", "value": -3}],
})


def _make_db(path: Path, *, with_combat: bool = False) -> None:
    conn = sqlite3.connect(str(path))
    conn.executescript(_BASE_SCHEMA)

    # hero
    conn.execute(
        "INSERT INTO characters (id, campaign_id, name, sheet_json) VALUES (1, 1, 'Hero', ?)",
        (json.dumps({"current_hp": 20, "max_hp": 30, "current_mana": 5, "max_mana": 10, "conditions": []}),),
    )

    # conditions catalog
    conn.execute("INSERT INTO game_config_conditions (key, label, effect_json) VALUES ('on_fire', 'Podpalony', ?)", (_ON_FIRE_COND,))
    conn.execute("INSERT INTO game_config_conditions (key, label, effect_json) VALUES ('weakened', 'Osłabiony', ?)", (_WEAKENED_COND,))

    if with_combat:
        combatants = json.dumps([
            {"id": "player", "name": "Hero", "hp_current": 20, "hp_max": 30, "conditions": []},
            {"id": "goblin_1", "name": "Goblin", "hp_current": 15, "hp_max": 15, "conditions": [], "kind": "enemy"},
        ])
        conn.execute(
            "INSERT INTO active_combat (campaign_id, character_id, combatants, status) VALUES (1, 1, ?, 'active')",
            (combatants,),
        )

    conn.commit()
    conn.close()


def _add_consumable_with_effect_json(db_path: Path, key: str, label: str, effect_json: dict) -> int:
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT INTO game_config_consumables (key, label, effect_json, effect_type) VALUES (?, ?, ?, 'misc')",
        (key, label, json.dumps(effect_json)),
    )
    row = conn.execute(
        "INSERT INTO character_inventory (character_id, consumable_key, quantity) VALUES (1, ?, 1) RETURNING id",
        (key,),
    ).fetchone()
    inv_id = row[0]
    conn.commit()
    conn.close()
    return inv_id


# ─── FAZA 1 RED: testy które muszą failować przed fixem ─────────────────────

def test_consumable_effect_json_column_exists_in_live_db():
    """Kolumna effect_json musi istnieć w game_config_consumables na żywej bazie DEV."""
    conn = sqlite3.connect("/data/ai_gm.db")
    try:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(game_config_consumables)")}
        assert "effect_json" in cols, "Brak kolumny effect_json w game_config_consumables — migracja nie przeszła"
    finally:
        conn.close()


def test_all_14_consumables_have_effect_json_after_migration():
    """Wszystkie 14 konsumabli z backfilla muszą mieć effect_json != NULL po migracji."""
    keys_14 = [
        "alchemist_fire", "holy_water", "scroll_fireball", "scroll_magic_bolt",
        "vial_of_acid", "smoke_bomb", "scroll_light",
        "potion_haste", "potion_stealth", "potion_strength", "potion_giant_strength",
        "potion_resistance", "potion_stamina", "scroll_shield",
    ]
    conn = sqlite3.connect("/data/ai_gm.db")
    try:
        # confirm column exists first
        cols = {row[1] for row in conn.execute("PRAGMA table_info(game_config_consumables)")}
        assert "effect_json" in cols, "Kolumna effect_json brak — uruchom migrację"

        rows = conn.execute(
            f"SELECT key, effect_json FROM game_config_consumables WHERE key IN ({','.join('?'*len(keys_14))})",
            keys_14,
        ).fetchall()
        missing = [k for k in keys_14 if k not in {r[0] for r in rows}]
        assert not missing, f"Brakuje konsumabli w DB: {missing}"
        no_json = [r[0] for r in rows if not r[1]]
        assert not no_json, f"Konsumable bez effect_json: {no_json}"
    finally:
        conn.close()


def test_effect_payloads_reads_damage_enemy_from_effect_json(tmp_path, monkeypatch):
    """_effect_payloads_from_item_row zwraca damage_enemy gdy effect_json go zawiera."""
    db = tmp_path / "t771.db"
    _make_db(db)
    monkeypatch.setattr(loot_mod, "LOOT_DB_PATH", str(db))

    inv_id = _add_consumable_with_effect_json(db, "vial_of_acid_test", "Fiolka kwasu", {
        "effect_category": "consumable_immediate",
        "effects": [{"type": "damage_enemy", "value": "2d6", "target": "enemy"}],
    })

    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        """
        SELECT gc.key, gc.label, gc.effect_json, gc.effect_type, gc.effect_dice,
               gc.effect_bonus, gc.effect_target
        FROM game_config_consumables gc WHERE gc.key = 'vial_of_acid_test'
        """
    ).fetchone()
    conn.close()

    payloads = loot_mod._effect_payloads_from_item_row(row)
    assert len(payloads) == 1
    assert payloads[0]["type"] == "damage_enemy"
    assert payloads[0]["value"] == "2d6"


def test_use_damage_enemy_outside_combat_returns_narrative(tmp_path, monkeypatch):
    """damage_enemy poza walką → efekt narrative_only (fallback), nie crash."""
    db = tmp_path / "t771_nc.db"
    _make_db(db, with_combat=False)
    monkeypatch.setattr(loot_mod, "LOOT_DB_PATH", str(db))

    inv_id = _add_consumable_with_effect_json(db, "vial_acid_nc", "Fiolka kwasu (test)", {
        "effect_category": "consumable_immediate",
        "effects": [{"type": "damage_enemy", "value": "2d6", "target": "enemy"}],
    })

    result = loot_mod.use_inventory_item(1, inv_id)
    applied = result["effects_applied"]
    assert len(applied) == 1
    assert applied[0]["type"] == "narrative_only"
    assert applied[0].get("reason") == "no_active_combat"


def test_use_damage_enemy_in_combat_reduces_enemy_hp(tmp_path, monkeypatch):
    """damage_enemy w walce → HP wroga maleje; wynik zawiera damage_dealt."""
    db = tmp_path / "t771_combat.db"
    _make_db(db, with_combat=True)
    monkeypatch.setattr(loot_mod, "LOOT_DB_PATH", str(db))

    inv_id = _add_consumable_with_effect_json(db, "vial_acid_c", "Fiolka kwasu (walka)", {
        "effect_category": "consumable_immediate",
        "effects": [{"type": "damage_enemy", "value": "2d6", "target": "enemy"}],
    })

    result = loot_mod.use_inventory_item(1, inv_id)
    applied = result["effects_applied"]
    assert len(applied) == 1
    dmg_effect = applied[0]
    assert dmg_effect["type"] == "damage_enemy"
    assert "damage_dealt" in dmg_effect
    assert int(dmg_effect["damage_dealt"]) >= 2  # min 2d6=2

    # enemy HP in active_combat must be reduced
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT combatants FROM active_combat WHERE campaign_id=1").fetchone()
    conn.close()
    combatants = json.loads(row["combatants"])
    enemy = next(c for c in combatants if c["id"] == "goblin_1")
    assert enemy["hp_current"] < 15, "HP wroga nie zmniejszyło się po damage_enemy"


def test_apply_condition_target_enemy_updates_combat_state(tmp_path, monkeypatch):
    """apply_condition z target=enemy → kondycja trafia na wroga w active_combat."""
    db = tmp_path / "t771_cond.db"
    _make_db(db, with_combat=True)
    monkeypatch.setattr(loot_mod, "LOOT_DB_PATH", str(db))

    inv_id = _add_consumable_with_effect_json(db, "holy_water_t", "Woda święcona (test)", {
        "effect_category": "consumable_immediate",
        "effects": [{"type": "apply_condition", "condition_key": "on_fire", "target": "enemy"}],
    })

    result = loot_mod.use_inventory_item(1, inv_id)
    applied = result["effects_applied"]
    assert len(applied) == 1
    assert applied[0]["type"] == "apply_condition"
    assert applied[0]["target"] == "enemy"
    assert applied[0]["applied"] is True

    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT combatants FROM active_combat WHERE campaign_id=1").fetchone()
    conn.close()
    combatants = json.loads(row["combatants"])
    enemy = next(c for c in combatants if c["id"] == "goblin_1")
    cond_keys = [c.get("key") for c in enemy.get("conditions", [])]
    assert "on_fire" in cond_keys, f"Kondycja on_fire nie trafiła na wroga: {enemy}"


def test_apply_condition_target_self_still_works(tmp_path, monkeypatch):
    """apply_condition z target=self nadal trafia na gracza (backward compat)."""
    db = tmp_path / "t771_self.db"
    _make_db(db, with_combat=False)
    monkeypatch.setattr(loot_mod, "LOOT_DB_PATH", str(db))

    inv_id = _add_consumable_with_effect_json(db, "debuff_potion_t", "Mikstura osłabienia (test)", {
        "effect_category": "consumable_immediate",
        "effects": [{"type": "apply_condition", "condition_key": "weakened", "target": "self"}],
    })

    result = loot_mod.use_inventory_item(1, inv_id)
    applied = result["effects_applied"]
    assert len(applied) == 1
    assert applied[0]["type"] == "apply_condition"
    assert applied[0]["applied"] is True

    conds = result["character_state"]["conditions"]
    cond_keys = [c.get("key") for c in conds]
    assert "weakened" in cond_keys


def test_heal_hp_consumable_via_effect_json_still_works(tmp_path, monkeypatch):
    """heal_hp przez effect_json nadal działa (backward compat)."""
    db = tmp_path / "t771_heal.db"
    _make_db(db, with_combat=False)
    monkeypatch.setattr(loot_mod, "LOOT_DB_PATH", str(db))

    inv_id = _add_consumable_with_effect_json(db, "healing_pot_t", "Mikstura leczenia (test)", {
        "effect_category": "consumable_immediate",
        "effects": [{"type": "heal_hp", "value": "2d4"}],
    })

    result = loot_mod.use_inventory_item(1, inv_id)
    applied = result["effects_applied"]
    assert len(applied) == 1
    assert applied[0]["type"] == "heal_hp"
    assert applied[0]["amount"] >= 2
