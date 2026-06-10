"""TDD: Issue #442 — E27 Onboarding cards for new mechanics (affixes, crafting).

Adds "affixes" and "crafting" card definitions to MECHANIC_CARDS.
Adds trigger heuristics in inject_onboarding_to_out:
  - affixes  → when loot contains items with non-empty affixes list
  - crafting → via get_unseen_cards_for_mechanics helper (called by craft endpoints)
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import sqlite3
import pytest

from app.services.onboarding_service import (
    MECHANIC_CARDS,
    inject_onboarding_to_out,
    check_onboarding_triggers,
    get_unseen_cards_for_mechanics,
)


# ─── fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE seen_mechanics (
            user_id INTEGER NOT NULL,
            mechanic_key TEXT NOT NULL,
            seen_at TEXT DEFAULT (datetime('now')),
            PRIMARY KEY (user_id, mechanic_key)
        );
    """)
    conn.commit()
    return conn


# ─── Card registry ────────────────────────────────────────────────────────────

def test_affixes_card_in_registry():
    """'affixes' card must exist in MECHANIC_CARDS."""
    assert "affixes" in MECHANIC_CARDS


def test_crafting_card_in_registry():
    """'crafting' card must exist in MECHANIC_CARDS."""
    assert "crafting" in MECHANIC_CARDS


def test_affixes_card_has_required_fields():
    """Affixes card must have title and content fields."""
    card = MECHANIC_CARDS["affixes"]
    assert "title" in card and card["title"]
    assert "content" in card and card["content"]


def test_crafting_card_has_required_fields():
    """Crafting card must have title and content fields."""
    card = MECHANIC_CARDS["crafting"]
    assert "title" in card and card["title"]
    assert "content" in card and card["content"]


# ─── inject_onboarding_to_out — affix trigger ────────────────────────────────

def test_inject_triggers_affixes_when_loot_has_affixes(db):
    """When turn result.loot has items with non-empty affixes, inject affix card."""
    out = {
        "result": {
            "loot": [
                {"name": "Sword of Fire", "affixes": [{"key": "flaming", "label": "Płomienny"}]},
            ]
        }
    }
    inject_onboarding_to_out(out, user_id=1, conn=db)
    card_keys = [c["mechanic_key"] for c in out.get("onboarding_cards", [])]
    assert "affixes" in card_keys


def test_inject_no_affixes_card_when_loot_empty_affixes(db):
    """Loot with empty affixes list does NOT trigger affix card."""
    out = {
        "result": {
            "loot": [
                {"name": "Plain Sword", "affixes": []},
            ]
        }
    }
    inject_onboarding_to_out(out, user_id=1, conn=db)
    card_keys = [c["mechanic_key"] for c in out.get("onboarding_cards", [])]
    assert "affixes" not in card_keys


def test_inject_no_affixes_card_when_no_loot(db):
    """No loot in result → no affix card."""
    out = {"result": {"xp_granted": 10}}
    inject_onboarding_to_out(out, user_id=1, conn=db)
    card_keys = [c["mechanic_key"] for c in out.get("onboarding_cards", [])]
    assert "affixes" not in card_keys


def test_inject_no_affixes_card_when_already_seen(db):
    """If user already saw 'affixes' card, don't inject it again."""
    db.execute("INSERT INTO seen_mechanics (user_id, mechanic_key) VALUES (1, 'affixes')")
    db.commit()
    out = {
        "result": {
            "loot": [{"name": "Sword", "affixes": [{"key": "flaming"}]}]
        }
    }
    inject_onboarding_to_out(out, user_id=1, conn=db)
    card_keys = [c["mechanic_key"] for c in out.get("onboarding_cards", [])]
    assert "affixes" not in card_keys


# ─── get_unseen_cards_for_mechanics ──────────────────────────────────────────

def test_get_unseen_returns_crafting_card(db):
    """get_unseen_cards_for_mechanics returns crafting card for user who hasn't seen it."""
    cards = get_unseen_cards_for_mechanics(db, user_id=1, mechanic_keys=["crafting"])
    assert any(c["mechanic_key"] == "crafting" for c in cards)


def test_get_unseen_returns_empty_if_all_seen(db):
    """Returns empty list if user already saw all requested cards."""
    db.execute("INSERT INTO seen_mechanics (user_id, mechanic_key) VALUES (1, 'crafting')")
    db.commit()
    cards = get_unseen_cards_for_mechanics(db, user_id=1, mechanic_keys=["crafting"])
    assert cards == []


def test_get_unseen_only_returns_known_keys(db):
    """Unknown mechanic keys are ignored gracefully."""
    cards = get_unseen_cards_for_mechanics(db, user_id=1, mechanic_keys=["crafting", "multiplayer", "unknown_xyz"])
    keys = [c["mechanic_key"] for c in cards]
    assert "unknown_xyz" not in keys


def test_get_unseen_per_user(db):
    """Seen status is per user — user 1 seeing crafting doesn't affect user 2."""
    db.execute("INSERT INTO seen_mechanics (user_id, mechanic_key) VALUES (1, 'crafting')")
    db.commit()
    cards_u1 = get_unseen_cards_for_mechanics(db, user_id=1, mechanic_keys=["crafting"])
    cards_u2 = get_unseen_cards_for_mechanics(db, user_id=2, mechanic_keys=["crafting"])
    assert cards_u1 == []
    assert any(c["mechanic_key"] == "crafting" for c in cards_u2)
