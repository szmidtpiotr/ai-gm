"""TDD: Issue #572 — U20 Onboarding: poprawki triggerów kart.

Covers:
  - death_save card RETARGETED: triggers on first HP < 25% (not on first death roll)
  - xp_gained card content: includes HOW to spend XP (Odpoczynek → Długi → Ucz się)
  - dice_roll card content: includes "Biegłość" (proficiency) to match the UI roll card
  - NEW cards: durability (<50%), raids (wild hex + gold>100), crafter (is_crafter NPC dialogue)
  - backward compatibility: injector still works without the new `character` arg
"""
import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import sqlite3
import pytest

from app.services.onboarding_service import (
    MECHANIC_CARDS,
    inject_onboarding_to_out,
)


# ─── fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE seen_mechanics (
            user_id INTEGER NOT NULL,
            mechanic_key TEXT NOT NULL,
            seen_at TEXT DEFAULT (datetime('now')),
            PRIMARY KEY (user_id, mechanic_key)
        );
        CREATE TABLE character_inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id INTEGER,
            weapon_key TEXT,
            item_key TEXT,
            equipped INTEGER DEFAULT 0,
            durability_max INTEGER,
            durability_current INTEGER
        );
        CREATE TABLE npcs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT UNIQUE,
            label TEXT,
            is_crafter INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE game_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER,
            current_location_id INTEGER,
            session_flags TEXT DEFAULT '{}',
            scene_npcs TEXT DEFAULT '[]'
        );
        CREATE TABLE game_locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            safe_for_rest INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1
        );
        """
    )
    conn.commit()
    return conn


def _char(hp_cur=100, hp_max=100, gold=0, char_id=1, campaign_id=10):
    return {
        "id": char_id,
        "campaign_id": campaign_id,
        "gold_gp": gold,
        "sheet_json": json.dumps({"current_hp": hp_cur, "max_hp": hp_max}),
    }


# ─── Card registry ──────────────────────────────────────────────────────────

def test_new_cards_in_registry():
    for key in ("durability", "raids", "crafter"):
        assert key in MECHANIC_CARDS, f"brak karty '{key}' w MECHANIC_CARDS"
        assert MECHANIC_CARDS[key]["title"]
        assert MECHANIC_CARDS[key]["content"]


def test_dice_roll_card_mentions_proficiency():
    """Karta rzutu musi wymieniać Biegłość (proficiency) jak roll card w UI."""
    assert "Biegłość" in MECHANIC_CARDS["dice_roll"]["content"]


def test_xp_card_explains_how_to_spend():
    """Karta XP musi mówić JAK wydać PD, etykietami 1:1 z UI."""
    content = MECHANIC_CARDS["xp_gained"]["content"]
    assert "Ucz się" in content
    assert "Odpoczynek" in content or "Długi" in content


# ─── death_save retarget ──────────────────────────────────────────────────────

def test_death_save_triggers_on_low_hp(db):
    """HP < 25% → karta death_save (PRZED pierwszym rzutem na śmierć)."""
    out = {"result": {}}
    inject_onboarding_to_out(out, user_id=1, conn=db, character=_char(hp_cur=20, hp_max=100))
    keys = [c["mechanic_key"] for c in out["onboarding_cards"]]
    assert "death_save" in keys


def test_death_save_not_triggered_at_healthy_hp(db):
    """HP zdrowe → brak karty death_save, nawet gdy w turze padł rzut na śmierć (stary trigger usunięty)."""
    out = {"result": {"test": "death_save"}}
    inject_onboarding_to_out(out, user_id=1, conn=db, character=_char(hp_cur=100, hp_max=100))
    keys = [c["mechanic_key"] for c in out["onboarding_cards"]]
    assert "death_save" not in keys


# ─── durability ────────────────────────────────────────────────────────────────

def test_durability_triggers_below_50pct(db):
    db.execute(
        "INSERT INTO character_inventory (character_id, weapon_key, equipped, durability_max, durability_current) "
        "VALUES (1, 'short_sword', 1, 100, 40)"
    )
    db.commit()
    out = {"result": {}}
    inject_onboarding_to_out(out, user_id=1, conn=db, character=_char())
    keys = [c["mechanic_key"] for c in out["onboarding_cards"]]
    assert "durability" in keys


def test_durability_not_triggered_above_50pct(db):
    db.execute(
        "INSERT INTO character_inventory (character_id, weapon_key, equipped, durability_max, durability_current) "
        "VALUES (1, 'short_sword', 1, 100, 80)"
    )
    db.commit()
    out = {"result": {}}
    inject_onboarding_to_out(out, user_id=1, conn=db, character=_char())
    keys = [c["mechanic_key"] for c in out["onboarding_cards"]]
    assert "durability" not in keys


# ─── raids (napady) ─────────────────────────────────────────────────────────────

def test_raids_triggers_on_wild_hex_with_gold(db):
    """Dziki hex (brak bezpiecznej lokacji) + złoto > 100 → karta napadów."""
    out = {"result": {}, "current_hex": {"q": 3, "r": -1}}
    inject_onboarding_to_out(out, user_id=1, conn=db, character=_char(gold=150))
    keys = [c["mechanic_key"] for c in out["onboarding_cards"]]
    assert "raids" in keys


def test_raids_not_triggered_with_low_gold(db):
    out = {"result": {}, "current_hex": {"q": 3, "r": -1}}
    inject_onboarding_to_out(out, user_id=1, conn=db, character=_char(gold=50))
    keys = [c["mechanic_key"] for c in out["onboarding_cards"]]
    assert "raids" not in keys


# ─── crafter ─────────────────────────────────────────────────────────────────

def test_crafter_triggers_on_dialogue_with_crafter_npc(db):
    db.execute("INSERT INTO npcs (key, label, is_crafter) VALUES ('blacksmith', 'Kowal', 1)")
    db.execute(
        "INSERT INTO game_sessions (campaign_id, scene_npcs) VALUES (10, ?)",
        (json.dumps([{"key": "blacksmith", "name": "Kowal"}]),),
    )
    db.commit()
    out = {"result": {}, "npc_dialogue": True}
    inject_onboarding_to_out(out, user_id=1, conn=db, character=_char())
    keys = [c["mechanic_key"] for c in out["onboarding_cards"]]
    assert "crafter" in keys


def test_crafter_not_triggered_for_non_crafter_npc(db):
    db.execute("INSERT INTO npcs (key, label, is_crafter) VALUES ('boris', 'Boris', 0)")
    db.execute(
        "INSERT INTO game_sessions (campaign_id, scene_npcs) VALUES (10, ?)",
        (json.dumps([{"key": "boris", "name": "Boris"}]),),
    )
    db.commit()
    out = {"result": {}, "npc_dialogue": True}
    inject_onboarding_to_out(out, user_id=1, conn=db, character=_char())
    keys = [c["mechanic_key"] for c in out["onboarding_cards"]]
    assert "crafter" not in keys


# ─── backward compatibility ─────────────────────────────────────────────────────

def test_injector_works_without_character_arg(db):
    """Stary sposób wołania (bez character) nadal działa — żaden nowy trigger nie odpala."""
    out = {"result": {}, "current_hex": {"q": 0, "r": 0}}
    inject_onboarding_to_out(out, user_id=1, conn=db)
    keys = [c["mechanic_key"] for c in out["onboarding_cards"]]
    assert "world_map" in keys
    assert "death_save" not in keys
    assert "durability" not in keys


def test_seen_card_not_returned(db):
    db.execute("INSERT INTO seen_mechanics (user_id, mechanic_key) VALUES (1, 'death_save')")
    db.commit()
    out = {"result": {}}
    inject_onboarding_to_out(out, user_id=1, conn=db, character=_char(hp_cur=10, hp_max=100))
    keys = [c["mechanic_key"] for c in out["onboarding_cards"]]
    assert "death_save" not in keys
