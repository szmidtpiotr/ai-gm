"""
Tests for World State Machine — V2 Phase 01 Task 03

Uses an in-memory SQLite DB so no external services are needed.
"""

import json
import sqlite3
import pytest

from app.services.world_state_machine import (
    WorldStateMachine,
    WSMResult,
    build_session_flags,
    get_session_state,
    VALID_STATES,
)


# ── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture
def db():
    """In-memory DB with minimal tables needed by WSM."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE game_locations (
            key TEXT PRIMARY KEY,
            label TEXT,
            safe_for_rest INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            parent_id INTEGER,
            parent_key TEXT,
            npc_keys TEXT DEFAULT '[]'
        );

        CREATE TABLE location_connections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_location_key TEXT,
            to_location_key TEXT,
            is_bidirectional INTEGER DEFAULT 1,
            is_active INTEGER DEFAULT 1
        );

        CREATE TABLE npcs (
            key TEXT PRIMARY KEY,
            label TEXT,
            is_active INTEGER DEFAULT 1,
            is_shop INTEGER DEFAULT 0
        );

        CREATE TABLE location_npc_assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            location_key TEXT,
            npc_key TEXT,
            is_active INTEGER DEFAULT 1
        );

        CREATE TABLE character_inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id INTEGER,
            item_key TEXT,
            weapon_key TEXT,
            consumable_key TEXT
        );

        CREATE TABLE character_conditions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id INTEGER,
            condition_type TEXT,
            expires_at TEXT
        );

        CREATE TABLE active_combat (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER,
            status TEXT DEFAULT 'active'
        );

        -- Seed data
        INSERT INTO game_locations VALUES ('loc_tavern', 'Karczma', 2, 1, NULL, NULL, '["innkeeper_boris"]');
        INSERT INTO game_locations VALUES ('loc_dungeon', 'Loch', 0, 1, NULL, NULL, '[]');
        INSERT INTO game_locations VALUES ('loc_camp', 'Obóz', 1, 1, NULL, NULL, '[]');
        INSERT INTO game_locations VALUES ('loc_market', 'Rynek', 1, 1, NULL, NULL, '[]');

        INSERT INTO location_connections (from_location_key, to_location_key) VALUES ('loc_tavern', 'loc_market');

        INSERT INTO npcs VALUES ('innkeeper_boris', 'Boris Karczmarz', 1, 0);
        INSERT INTO npcs VALUES ('merchant_aldric', 'Aldric Kupiec', 1, 1);

        INSERT INTO location_npc_assignments (location_key, npc_key) VALUES ('loc_tavern', 'innkeeper_boris');
        INSERT INTO location_npc_assignments (location_key, npc_key) VALUES ('loc_market', 'merchant_aldric');
    """)
    conn.commit()
    yield conn
    conn.close()


@pytest.fixture
def wsm(db):
    return WorldStateMachine(db)


def narrative_flags(**kwargs):
    kwargs.setdefault("current_location_key", "loc_tavern")
    return build_session_flags("NARRATIVE", **kwargs)


def combat_flags(roster=None, **kwargs):
    roster = roster or [
        {"key": "goblin_1", "name": "Goblin Strażnik", "hp": 12, "hp_max": 12},
        {"key": "goblin_2", "name": "Goblin Szaman", "hp": 18, "hp_max": 18},
    ]
    kwargs.setdefault("current_location_key", "loc_tavern")
    return build_session_flags("COMBAT", combat_roster=roster, **kwargs)


# ── get_session_state ─────────────────────────────────────────────────────

def test_get_state_default():
    assert get_session_state({}) == "NARRATIVE"

def test_get_state_combat():
    assert get_session_state({"state": "COMBAT"}) == "COMBAT"

def test_get_state_invalid_falls_back():
    assert get_session_state({"state": "FLYING_UNICORN"}) == "NARRATIVE"

def test_all_valid_states_recognized():
    for state in VALID_STATES:
        assert get_session_state({"state": state}) == state


# ── State enforcement (state-level blocks) ───────────────────────────────

class TestStateBlocks:
    def test_attack_in_narrative_routes_to_combat_resolver(self, wsm):
        # ATTACK in NARRATIVE starts combat
        flags = narrative_flags()
        flags["combat_roster"] = [{"key": "goblin_1", "name": "Goblin", "hp": 12, "hp_max": 12}]
        result = wsm.validate_and_route(flags, "ATTACK", {"target": "goblin_1"}, 1, 1)
        # Routed (combat starts), not blocked
        assert result.valid is True

    def test_flee_in_narrative_blocked(self, wsm):
        result = wsm.validate_and_route(narrative_flags(), "FLEE", {}, 1, 1)
        assert result.valid is False
        assert "uciekać" in result.blocked_message.lower()

    def test_dialogue_in_combat_blocked(self, wsm):
        result = wsm.validate_and_route(combat_flags(), "DIALOGUE", {"npc_key": "innkeeper_boris"}, 1, 1)
        assert result.valid is False
        assert "walki" in result.blocked_message.lower()

    def test_movement_in_combat_blocked(self, wsm):
        result = wsm.validate_and_route(combat_flags(), "MOVEMENT", {"destination_key": "loc_market"}, 1, 1)
        assert result.valid is False

    def test_rest_in_combat_blocked(self, wsm):
        result = wsm.validate_and_route(combat_flags(), "REST", {"rest_type": "short"}, 1, 1)
        assert result.valid is False

    def test_shop_in_combat_blocked(self, wsm):
        result = wsm.validate_and_route(combat_flags(), "SHOP", {"npc_key": "merchant_aldric"}, 1, 1)
        assert result.valid is False


# ── ATTACK validation ─────────────────────────────────────────────────────

class TestAttackValidation:
    def test_attack_valid_target(self, wsm):
        result = wsm.validate_and_route(combat_flags(), "ATTACK", {"target": "goblin_1"}, 1, 1)
        assert result.valid is True
        assert result.resolver_key == "combat_resolver"

    def test_attack_dead_target_blocked(self, wsm):
        roster = [{"key": "goblin_1", "name": "Goblin", "hp": 0, "hp_max": 12}]
        result = wsm.validate_and_route(combat_flags(roster), "ATTACK", {"target": "goblin_1"}, 1, 1)
        assert result.valid is False
        assert "martwy" in result.blocked_message.lower()

    def test_attack_nonexistent_target_blocked(self, wsm):
        result = wsm.validate_and_route(combat_flags(), "ATTACK", {"target": "dragon_999"}, 1, 1)
        assert result.valid is False
        assert "nie istnieje" in result.blocked_message.lower()

    def test_attack_missing_target_blocked(self, wsm):
        result = wsm.validate_and_route(combat_flags(), "ATTACK", {}, 1, 1)
        assert result.valid is False

    def test_attack_with_valid_weapon(self, wsm, db):
        db.execute("INSERT INTO character_inventory (character_id, weapon_key) VALUES (1, 'sword_iron')")
        db.commit()
        result = wsm.validate_and_route(combat_flags(), "ATTACK",
                                         {"target": "goblin_1", "weapon": "sword_iron"}, 1, 1)
        assert result.valid is True

    def test_attack_with_missing_weapon_blocked(self, wsm):
        result = wsm.validate_and_route(combat_flags(), "ATTACK",
                                         {"target": "goblin_1", "weapon": "sword_legendary"}, 1, 1)
        assert result.valid is False
        assert "ekwipunku" in result.blocked_message.lower()

    def test_attack_while_stunned_blocked(self, wsm, db):
        db.execute("INSERT INTO character_conditions (character_id, condition_type, expires_at) VALUES (1, 'stunned', '999')")
        db.commit()
        result = wsm.validate_and_route(combat_flags(), "ATTACK", {"target": "goblin_1"}, 1, 1)
        assert result.valid is False
        assert "ogłuszony" in result.blocked_message.lower()


# ── DIALOGUE validation ───────────────────────────────────────────────────

class TestDialogueValidation:
    def test_dialogue_valid(self, wsm):
        flags = narrative_flags(current_location_key="loc_tavern")
        result = wsm.validate_and_route(flags, "DIALOGUE", {"npc_key": "innkeeper_boris"}, 1, 1)
        assert result.valid is True
        assert result.resolver_key == "dialogue_resolver"

    def test_dialogue_npc_not_in_location_blocked(self, wsm):
        flags = narrative_flags(current_location_key="loc_dungeon")
        result = wsm.validate_and_route(flags, "DIALOGUE", {"npc_key": "innkeeper_boris"}, 1, 1)
        assert result.valid is False
        assert "nie jest tutaj" in result.blocked_message.lower()

    def test_dialogue_nonexistent_npc_blocked(self, wsm):
        result = wsm.validate_and_route(narrative_flags(), "DIALOGUE", {"npc_key": "wizard_xyz"}, 1, 1)
        assert result.valid is False

    def test_dialogue_no_npc_key_blocked(self, wsm):
        result = wsm.validate_and_route(narrative_flags(), "DIALOGUE", {}, 1, 1)
        assert result.valid is False


# ── MOVEMENT validation ───────────────────────────────────────────────────

class TestMovementValidation:
    def test_movement_valid_connected(self, wsm):
        flags = narrative_flags(current_location_key="loc_tavern")
        result = wsm.validate_and_route(flags, "MOVEMENT", {"destination_key": "loc_market"}, 1, 1)
        assert result.valid is True
        assert result.resolver_key == "movement_resolver"

    def test_movement_unconnected_blocked(self, wsm):
        flags = narrative_flags(current_location_key="loc_tavern")
        result = wsm.validate_and_route(flags, "MOVEMENT", {"destination_key": "loc_dungeon"}, 1, 1)
        assert result.valid is False
        assert "dotrzeć" in result.blocked_message.lower()

    def test_movement_nonexistent_location_blocked(self, wsm):
        result = wsm.validate_and_route(narrative_flags(), "MOVEMENT",
                                         {"destination_key": "loc_nowhere"}, 1, 1)
        assert result.valid is False

    def test_movement_no_destination_blocked(self, wsm):
        result = wsm.validate_and_route(narrative_flags(), "MOVEMENT", {}, 1, 1)
        assert result.valid is False


# ── REST validation ───────────────────────────────────────────────────────

class TestRestValidation:
    def test_short_rest_in_safe_location(self, wsm):
        flags = narrative_flags(current_location_key="loc_tavern")
        result = wsm.validate_and_route(flags, "REST", {"rest_type": "short"}, 1, 1)
        assert result.valid is True
        assert result.resolver_key == "rest_resolver"
        assert result.new_state == "RESTING"

    def test_long_rest_in_fully_safe_location(self, wsm):
        flags = narrative_flags(current_location_key="loc_tavern")  # safe_for_rest=2
        result = wsm.validate_and_route(flags, "REST", {"rest_type": "long"}, 1, 1)
        assert result.valid is True

    def test_long_rest_in_partial_safe_blocked(self, wsm):
        flags = narrative_flags(current_location_key="loc_camp")  # safe_for_rest=1
        result = wsm.validate_and_route(flags, "REST", {"rest_type": "long"}, 1, 1)
        assert result.valid is False
        assert "krótki" in result.blocked_message.lower()

    def test_rest_in_unsafe_location_blocked(self, wsm):
        flags = narrative_flags(current_location_key="loc_dungeon")  # safe_for_rest=0
        result = wsm.validate_and_route(flags, "REST", {"rest_type": "short"}, 1, 1)
        assert result.valid is False
        assert "bezpieczne" in result.blocked_message.lower()

    def test_rest_with_active_combat_blocked(self, wsm, db):
        db.execute("INSERT INTO active_combat (campaign_id, status) VALUES (1, 'active')")
        db.commit()
        flags = narrative_flags(current_location_key="loc_tavern")
        result = wsm.validate_and_route(flags, "REST", {"rest_type": "short"}, 1, 1)
        assert result.valid is False
        assert "wrogowie" in result.blocked_message.lower()


# ── SHOP validation ───────────────────────────────────────────────────────

class TestShopValidation:
    def test_shop_with_merchant_npc(self, wsm):
        flags = narrative_flags(current_location_key="loc_market")
        result = wsm.validate_and_route(flags, "SHOP", {"npc_key": "merchant_aldric"}, 1, 1)
        assert result.valid is True
        assert result.resolver_key == "shop_resolver"
        assert result.new_state == "SHOPPING"

    def test_shop_with_non_merchant_blocked(self, wsm):
        flags = narrative_flags(current_location_key="loc_tavern")
        result = wsm.validate_and_route(flags, "SHOP", {"npc_key": "innkeeper_boris"}, 1, 1)
        assert result.valid is False
        assert "kupcem" in result.blocked_message.lower()


# ── Routing tests ─────────────────────────────────────────────────────────

class TestRouting:
    def test_flee_in_combat_routes_to_flee_resolver(self, wsm):
        flags = combat_flags(current_location_key="loc_tavern")
        result = wsm.validate_and_route(flags, "FLEE", {}, 1, 1)
        assert result.valid is True
        assert result.resolver_key == "flee_resolver"

    def test_search_in_narrative_routes_to_search_resolver(self, wsm):
        result = wsm.validate_and_route(narrative_flags(), "SEARCH", {"focus": "clues"}, 1, 1)
        assert result.valid is True
        assert result.resolver_key == "search_resolver"

    def test_examine_in_narrative_routes_to_examine_resolver(self, wsm):
        result = wsm.validate_and_route(narrative_flags(), "EXAMINE", {"target": "old_chest"}, 1, 1)
        assert result.valid is True
        assert result.resolver_key == "examine_resolver"

    def test_skill_attempt_routes_to_skill_resolver(self, wsm):
        result = wsm.validate_and_route(narrative_flags(), "SKILL_ATTEMPT",
                                         {"skill_key": "lockpicking"}, 1, 1)
        assert result.valid is True
        assert result.resolver_key == "skill_resolver"


# ── Pending state intercepts ──────────────────────────────────────────────

class TestPendingStateIntercepts:
    def test_death_save_pending_blocks_non_save_actions(self, wsm):
        flags = build_session_flags("DEATH_SAVE_PENDING")
        result = wsm.validate_and_route(flags, "ATTACK", {"target": "goblin_1"}, 1, 1)
        assert result.valid is False
        assert "nieprzytomny" in result.blocked_message.lower()

    def test_fear_test_pending_auto_routes_to_fear_resolver(self, wsm):
        flags = build_session_flags("FEAR_TEST_PENDING")
        result = wsm.validate_and_route(flags, "ATTACK", {"target": "goblin_1"}, 1, 1)
        assert result.valid is True
        assert result.resolver_key == "fear_resolver"

    def test_skill_test_pending_auto_routes_to_skill_resolver(self, wsm):
        flags = build_session_flags("SKILL_TEST_PENDING")
        result = wsm.validate_and_route(flags, "MOVEMENT", {"destination_key": "loc_market"}, 1, 1)
        assert result.valid is True
        assert result.resolver_key == "skill_resolver"


# ── build_session_flags ───────────────────────────────────────────────────

def test_build_session_flags_defaults():
    flags = build_session_flags()
    assert flags["state"] == "NARRATIVE"
    assert flags["combat_roster"] == []
    assert flags["death_save_successes"] == 0

def test_build_session_flags_combat():
    flags = build_session_flags("COMBAT", combat_roster=[{"key": "g1"}])
    assert flags["state"] == "COMBAT"
    assert flags["combat_roster"][0]["key"] == "g1"
