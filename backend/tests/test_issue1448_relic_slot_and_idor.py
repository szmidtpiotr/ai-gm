"""AUDIT #1448 — Relic slot cap bypass + affix/repair IDOR + dwarf-repair no-op.

Covers:
  1. test_relic_slot_cap_enforced      — equip_item rejects a relic-class item
     (non-weapon/non-armor with passive effect_json) into a body slot; only relic
     slots accept it, so the 2-slot cap can't be bypassed to stack +CHA.
  2. test_repair_foreign_inventory_404 — durability_service scopes by character_id:
     repairing another hero's inventory_id → item_not_found, no gold spent, victim
     durability untouched.
  3. test_reroll_foreign_inventory_404 — crafter_service scopes by character_id:
     rerolling another hero's inventory_id → item_not_found, no gold spent, victim
     affixes untouched.
  4. test_dwarf_repair_ownership_and_effect — dwarf-repair endpoint enforces hero
     ownership (403 on foreign), charges nothing on a no-op, and actually restores
     durability_current = durability_max on a real repair.
"""
import sys
sys.path.insert(0, "/app")

import json
import sqlite3

import pytest


# ─────────────────────────────────────────────────────────────────────────────
# 1. Relic slot cap — equip_item guard
# ─────────────────────────────────────────────────────────────────────────────

_RELIC_EFFECT = json.dumps(
    {"schema_version": 1, "effects": [{"type": "static_stat_modifier", "stat": "CHA", "value": 2}]}
)


def _seed_equip_db(path: str):
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE characters (id INTEGER PRIMARY KEY);
        CREATE TABLE character_inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id INTEGER NOT NULL,
            weapon_key TEXT, item_key TEXT,
            equipped INTEGER DEFAULT 0, slot TEXT
        );
        CREATE TABLE game_config_items (
            key TEXT PRIMARY KEY, item_type TEXT, armor_coverage TEXT, effect_json TEXT
        );
        CREATE TABLE game_config_weapons (key TEXT PRIMARY KEY, weapon_slot TEXT);
        INSERT INTO characters (id) VALUES (1);
        """
    )
    # relic-class: non-weapon, non-armor item carrying a passive +CHA effect
    conn.execute(
        "INSERT INTO game_config_items (key, item_type, armor_coverage, effect_json) VALUES (?, ?, ?, ?)",
        ("amulet_cha", "trinket", None, _RELIC_EFFECT),
    )
    conn.execute(
        "INSERT INTO character_inventory (id, character_id, item_key, equipped, slot) VALUES (10, 1, 'amulet_cha', 0, NULL)"
    )
    conn.commit()
    conn.close()


def test_relic_slot_cap_enforced(tmp_path, monkeypatch):
    from app.services import loot_service

    db = str(tmp_path / "equip.db")
    _seed_equip_db(db)
    monkeypatch.setattr(loot_service, "LOOT_DB_PATH", db)

    # A relic-class item forced into any body slot must be rejected — that is what
    # keeps the effect stack capped at the 2 dedicated relic slots (#1302).
    for body_slot in ("head", "torso", "l_arm", "hands", "feet", "back"):
        with pytest.raises(ValueError) as ei:
            loot_service.equip_item(1, 10, body_slot)
        assert "relic" in str(ei.value).lower()

    # Unit-level: the relic-class detector recognises a passive worn effect and
    # ignores non-passive / empty payloads.
    assert loot_service._has_worn_passive_effect(_RELIC_EFFECT) is True
    assert loot_service._has_worn_passive_effect(None) is False
    assert loot_service._has_worn_passive_effect("{}") is False
    assert loot_service._has_worn_passive_effect(
        json.dumps({"effects": [{"type": "heal", "value": 5}]})
    ) is False


# ─────────────────────────────────────────────────────────────────────────────
# 2. Repair IDOR — durability_service
# ─────────────────────────────────────────────────────────────────────────────

def _dur_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE characters (id INTEGER PRIMARY KEY, gold_gp INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE character_inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id INTEGER NOT NULL,
            weapon_key TEXT, item_key TEXT, consumable_key TEXT,
            equipped INTEGER DEFAULT 0, slot TEXT,
            durability_current INTEGER, durability_max INTEGER
        );
        CREATE TABLE character_gold_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT, character_id INTEGER, delta INTEGER,
            source TEXT, meta_json TEXT, game_clock_day INTEGER DEFAULT 1, reverted_at TEXT
        );
        CREATE TABLE game_config_weapons (key TEXT PRIMARY KEY, rarity INTEGER DEFAULT 1);
        INSERT INTO game_config_weapons (key, rarity) VALUES ('sword', 1);

        INSERT INTO characters VALUES (1, 1000);   -- attacker
        INSERT INTO characters VALUES (2, 1000);   -- victim
        -- inv_id 1 belongs to victim (char 2), damaged
        INSERT INTO character_inventory (character_id, weapon_key, equipped, slot, durability_current, durability_max)
            VALUES (2, 'sword', 1, 'main_hand', 40, 100);
        """
    )
    conn.commit()
    return conn


def test_repair_foreign_inventory_404():
    from app.services.durability_service import get_repair_cost, repair_item

    conn = _dur_conn()
    # attacker = char 1, victim's inv_id = 1 (owned by char 2)
    cost = get_repair_cost(conn, 1, 1)
    assert cost["ok"] is False and cost["reason"] == "item_not_found"

    res = repair_item(conn, 1, 1)
    assert res["ok"] is False and res["reason"] == "item_not_found"

    # Victim untouched, attacker not charged.
    dur = conn.execute("SELECT durability_current FROM character_inventory WHERE id = 1").fetchone()[0]
    assert dur == 40
    gold1 = conn.execute("SELECT gold_gp FROM characters WHERE id = 1").fetchone()[0]
    assert gold1 == 1000

    # Sanity: the real owner CAN read the cost.
    ok = get_repair_cost(conn, 2, 1)
    assert ok["ok"] is True and ok["missing_pts"] == 60
    conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# 3. Reroll IDOR — crafter_service
# ─────────────────────────────────────────────────────────────────────────────

def _craft_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE characters (id INTEGER PRIMARY KEY, gold_gp INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE character_inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id INTEGER NOT NULL,
            weapon_key TEXT, item_key TEXT, consumable_key TEXT,
            affixes_json TEXT NOT NULL DEFAULT '[]'
        );
        CREATE TABLE character_gold_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT, character_id INTEGER, delta INTEGER,
            source TEXT, meta_json TEXT, game_clock_day INTEGER DEFAULT 1, reverted_at TEXT
        );
        CREATE TABLE game_config_affixes (
            key TEXT PRIMARY KEY, name TEXT, tier INTEGER, allowed_item_types TEXT,
            effect_json TEXT, is_active INTEGER DEFAULT 1
        );
        INSERT INTO game_config_affixes VALUES ('sharp', 'Ostry', 1, 'weapon', '{}', 1);
        INSERT INTO game_config_affixes VALUES ('swift', 'Zwinny', 1, 'weapon', '{}', 1);

        INSERT INTO characters VALUES (1, 2000);   -- attacker
        INSERT INTO characters VALUES (2, 2000);   -- victim
        -- inv_id 1 belongs to victim (char 2) with a T1 affix
        INSERT INTO character_inventory (character_id, weapon_key, affixes_json)
            VALUES (2, 'axe', '["sharp"]');
        """
    )
    conn.commit()
    return conn


def test_reroll_foreign_inventory_404():
    from app.services.crafter_service import reroll_affix, apply_affix

    conn = _craft_conn()
    # attacker char 1 targets victim's inv_id 1
    res = reroll_affix(conn, 1, 1, "sharp")
    assert res["ok"] is False and res["reason"] == "item_not_found"

    res2 = apply_affix(conn, 1, 1, 1)
    assert res2["ok"] is False and res2["reason"] == "item_not_found"

    # Victim's affixes + attacker gold untouched.
    affx = conn.execute("SELECT affixes_json FROM character_inventory WHERE id = 1").fetchone()[0]
    assert json.loads(affx) == ["sharp"]
    gold1 = conn.execute("SELECT gold_gp FROM characters WHERE id = 1").fetchone()[0]
    assert gold1 == 2000
    conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# 4. dwarf-repair — ownership + charge-on-effect only + durability restore
# ─────────────────────────────────────────────────────────────────────────────

def _seed_dwarf_db(path: str):
    """Victim hero owned by user 2 (dwarf), with a damaged weapon (10/100)."""
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE characters (
            id INTEGER PRIMARY KEY, name TEXT, race TEXT, user_id INTEGER,
            gold_gp INTEGER DEFAULT 0, campaign_id INTEGER
        );
        CREATE TABLE character_inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT, character_id INTEGER NOT NULL,
            weapon_key TEXT, equipped INTEGER DEFAULT 0, meta_json TEXT,
            durability_current INTEGER, durability_max INTEGER
        );
        CREATE TABLE game_config_weapons (key TEXT PRIMARY KEY, label TEXT);
        CREATE TABLE character_gold_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT, character_id INTEGER, delta INTEGER,
            source TEXT, campaign_id INTEGER, game_clock_day INTEGER DEFAULT 1, meta_json TEXT
        );
        INSERT INTO game_config_weapons (key, label) VALUES ('sword', 'Miecz');
        INSERT INTO characters (id, name, race, user_id, gold_gp) VALUES (77, '[TEST] Victim 1448', 'dwarf', 2, 100);
        INSERT INTO character_inventory (character_id, weapon_key, equipped, durability_current, durability_max)
            VALUES (77, 'sword', 1, 10, 100);
        """
    )
    conn.commit()
    conn.close()


def _gold(path, cid):
    conn = sqlite3.connect(path)
    g = conn.execute("SELECT gold_gp FROM characters WHERE id = ?", (cid,)).fetchone()[0]
    conn.close()
    return int(g or 0)


def _token(uid: int) -> str:
    from app.services import jwt_service
    return "Bearer " + jwt_service.issue_access_token(
        user_id=uid, username="u", role="player", is_admin=0
    )


def test_dwarf_repair_ownership_and_effect(tmp_path, monkeypatch):
    from fastapi import HTTPException
    from app.api import characters as ch

    db = str(tmp_path / "dwarf.db")
    _seed_dwarf_db(db)
    monkeypatch.setattr(ch, "DB_PATH", db)
    monkeypatch.setenv("JWT_SECRET", "unit-test-secret-key-32-characters-long")
    monkeypatch.delenv("ALLOW_LEGACY_USERID", raising=False)
    victim = 77

    # (a) IDOR: attacker (user 1) tries to drain the victim's (user 2) hero → 403, no gold lost.
    with pytest.raises(HTTPException) as ei:
        ch.dwarf_repair(victim, user_id=None, authorization=_token(1))
    assert ei.value.status_code == 403
    assert _gold(db, victim) == 100

    # (b) Owner (user 2) repairs own hero → 20 gp charged, durability restored, tag set.
    out = ch.dwarf_repair(victim, user_id=None, authorization=_token(2))
    assert out["cost_gp"] == 20 and out["repaired_weapon"] is not None
    assert _gold(db, victim) == 80

    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT durability_current, durability_max, meta_json FROM character_inventory WHERE character_id = ? LIMIT 1",
        (victim,),
    ).fetchone()
    conn.close()
    assert row["durability_current"] == row["durability_max"]  # actually restored
    assert json.loads(row["meta_json"] or "{}").get("repaired_by_dwarf") is True

    # (c) No-op (already repaired) → charge nothing.
    out2 = ch.dwarf_repair(victim, user_id=None, authorization=_token(2))
    assert out2["cost_gp"] == 0
    assert _gold(db, victim) == 80
