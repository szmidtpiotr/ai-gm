"""
Tests for World Service — V2 Phase 03 Tasks 08/09/10
"""
import json
import sqlite3
import pytest

from app.services.world_service import (
    process_create_tags,
    build_available_content_index,
    build_v2_npc_context_block,
    get_current_location_info,
    get_pending_review_counts,
    approve_entity,
    discard_entity,
    _parse_kv,
)


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE game_locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT UNIQUE, label TEXT, location_type TEXT DEFAULT 'sub',
            description TEXT, parent_id INTEGER, parent_key TEXT,
            rules TEXT, review_status TEXT DEFAULT 'permanent',
            ai_generated INTEGER DEFAULT 0, is_active INTEGER DEFAULT 1,
            safe_for_rest INTEGER DEFAULT 0, npc_keys TEXT DEFAULT '[]',
            enemy_keys TEXT DEFAULT '[]'
        );
        CREATE TABLE npcs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT UNIQUE, label TEXT, npc_type TEXT DEFAULT 'neutral',
            personality_prompt TEXT DEFAULT '', personality_json TEXT DEFAULT '{}',
            keyword_triggers TEXT DEFAULT '[]', review_status TEXT DEFAULT 'permanent',
            is_active INTEGER DEFAULT 1, is_shop INTEGER DEFAULT 0
        );
        CREATE TABLE game_config_enemies (
            key TEXT PRIMARY KEY, label TEXT, tier TEXT DEFAULT 'standard',
            hp_base INTEGER DEFAULT 10, ac_base INTEGER DEFAULT 10,
            attack_bonus INTEGER DEFAULT 0, damage_die TEXT DEFAULT 'd6',
            damage_bonus INTEGER DEFAULT 0, attacks_per_turn INTEGER DEFAULT 1,
            xp_award INTEGER DEFAULT 10, is_active INTEGER DEFAULT 1,
            review_status TEXT DEFAULT 'permanent'
        );
        CREATE TABLE location_npc_assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            location_key TEXT, npc_key TEXT, is_active INTEGER DEFAULT 1,
            UNIQUE(location_key, npc_key)
        );
        CREATE TABLE location_enemy_assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            location_key TEXT, enemy_key TEXT, is_active INTEGER DEFAULT 1,
            UNIQUE(location_key, enemy_key)
        );
        CREATE TABLE game_sessions (
            id TEXT PRIMARY KEY, campaign_id INTEGER, current_location_id INTEGER
        );
        CREATE TABLE campaigns (
            id INTEGER PRIMARY KEY, plan_json TEXT DEFAULT '{}'
        );

        -- Seed
        INSERT INTO game_locations (key, label, location_type, safe_for_rest, review_status)
            VALUES ('loc_tavern', 'The Tavern', 'sub', 1, 'permanent');
        INSERT INTO game_locations (key, label, location_type)
            VALUES ('loc_graustein', 'Graustein', 'macro');
        INSERT INTO npcs (key, label, npc_type, personality_prompt, keyword_triggers)
            VALUES ('innkeeper_boris', 'Boris', 'neutral',
                    'Gruff. Short sentences. Always suspicious.',
                    '[{"keyword":"guild","must_reveal_info":"Guild meets on Wednesdays.","is_secret":false},{"keyword":"murder","must_reveal_info":"Saw a cloaked figure.","is_secret":true}]');
        INSERT INTO game_config_enemies (key, label, tier)
            VALUES ('goblin_scout', 'Goblin Scout', 'weak');
        INSERT INTO location_npc_assignments (location_key, npc_key)
            VALUES ('loc_tavern', 'innkeeper_boris');
        INSERT INTO location_enemy_assignments (location_key, enemy_key)
            VALUES ('loc_graustein', 'goblin_scout');
        INSERT INTO game_sessions (id, campaign_id, current_location_id)
            VALUES ('session_1', 1, 1);
        INSERT INTO campaigns (id) VALUES (1);
    """)
    conn.commit()
    yield conn
    conn.close()


# ── _parse_kv ─────────────────────────────────────────────────────────────

def test_parse_kv_basic():
    result = _parse_kv("key=goblin_cave, label=Goblin Cave, type=sub")
    assert result["key"] == "goblin_cave"
    assert result["label"] == "Goblin Cave"
    assert result["type"] == "sub"

def test_parse_kv_empty():
    assert _parse_kv("") == {}


# ── process_create_tags ───────────────────────────────────────────────────

class TestProcessCreateTags:
    def test_create_location_tag(self, db):
        narrative = "You enter [CREATE_LOCATION: key=dark_alley, label=Dark Alley, type=sub] the alley."
        cleaned, created = process_create_tags(narrative, db, 1)
        assert "[CREATE_LOCATION" not in cleaned
        assert "You enter  the alley." in cleaned or "You enter the alley" in cleaned
        assert len(created) == 1
        assert created[0]["key"] == "dark_alley"
        # Verify DB record
        row = db.execute("SELECT review_status FROM game_locations WHERE key='dark_alley'").fetchone()
        assert row and row[0] == "pending_review"

    def test_create_npc_tag(self, db):
        narrative = "[CREATE_NPC: key=merchant_aldric, name=Aldric, role=merchant, personality=Friendly trader]"
        cleaned, created = process_create_tags(narrative, db, 1)
        assert len(created) == 1
        assert created[0]["key"] == "merchant_aldric"
        row = db.execute("SELECT npc_type, review_status FROM npcs WHERE key='merchant_aldric'").fetchone()
        assert row and row["npc_type"] == "merchant"
        assert row["review_status"] == "pending_review"

    def test_create_enemy_tag(self, db):
        narrative = "[CREATE_ENEMY: key=bog_wraith, name=Bog Wraith, tier=elite]"
        cleaned, created = process_create_tags(narrative, db, 1)
        assert len(created) == 1
        assert created[0]["tier"] == "elite"
        row = db.execute("SELECT hp_base FROM game_config_enemies WHERE key='bog_wraith'").fetchone()
        assert row and row[0] == 25  # elite tier default

    def test_create_enemy_based_on(self, db):
        narrative = "[CREATE_ENEMY: key=goblin_elder, name=Goblin Elder, based_on=goblin_scout, tier=standard]"
        cleaned, created = process_create_tags(narrative, db, 1)
        # Should inherit stats from goblin_scout
        row = db.execute("SELECT key FROM game_config_enemies WHERE key='goblin_elder'").fetchone()
        assert row is not None

    def test_npc_killed_tag(self, db):
        narrative = "Boris falls dead. [NPC_KILLED: key=innkeeper_boris]"
        cleaned, created = process_create_tags(narrative, db, 1)
        assert "[NPC_KILLED" not in cleaned
        row = db.execute("SELECT is_active FROM npcs WHERE key='innkeeper_boris'").fetchone()
        assert row and row[0] == 0

    def test_duplicate_key_ignored(self, db):
        # Creating same key twice — second should not raise
        tag = "[CREATE_LOCATION: key=loc_tavern, label=New Tavern, type=sub]"
        _, created = process_create_tags(tag, db, 1)
        # Returns existing record, no duplicate
        count = db.execute("SELECT COUNT(*) FROM game_locations WHERE key='loc_tavern'").fetchone()[0]
        assert count == 1

    def test_no_tags_unchanged(self, db):
        narrative = "The goblin attacks you with its rusty blade."
        cleaned, created = process_create_tags(narrative, db, 1)
        assert cleaned == narrative
        assert created == []


# ── build_available_content_index ────────────────────────────────────────

class TestAvailableContentIndex:
    def test_shows_npcs(self, db):
        result = build_available_content_index(db, "loc_tavern")
        assert "Boris" in result
        assert "innkeeper_boris" in result

    def test_shows_enemies(self, db):
        result = build_available_content_index(db, "loc_graustein")
        assert "goblin_scout" in result

    def test_no_location_returns_empty(self, db):
        result = build_available_content_index(db, None)
        assert result == ""

    def test_unknown_location_returns_empty(self, db):
        result = build_available_content_index(db, "loc_nowhere")
        assert result == ""


# ── build_v2_npc_context_block ────────────────────────────────────────────

class TestV2NpcContextBlock:
    def test_includes_personality(self, db):
        result = build_v2_npc_context_block(db, "loc_tavern")
        assert "Boris" in result
        assert "Gruff" in result

    def test_keyword_trigger_fires(self, db):
        result = build_v2_npc_context_block(db, "loc_tavern", player_text="ask about guild")
        assert "MUST INCLUDE" in result
        assert "Guild meets on Wednesdays" in result

    def test_secret_trigger_fires(self, db):
        result = build_v2_npc_context_block(db, "loc_tavern", player_text="what about the murder")
        assert "reluctantly" in result
        assert "cloaked figure" in result

    def test_no_match_no_must_include(self, db):
        result = build_v2_npc_context_block(db, "loc_tavern", player_text="nice weather today")
        assert "MUST INCLUDE" not in result

    def test_unknown_location_returns_none(self, db):
        result = build_v2_npc_context_block(db, "loc_nowhere")
        assert result is None


# ── get_current_location_info ─────────────────────────────────────────────

def test_get_current_location_info(db):
    result = get_current_location_info(db, 1)
    assert result is not None
    assert result["key"] == "loc_tavern"
    assert result["label"] == "The Tavern"
    assert result["safe_for_rest"] == 1

def test_get_current_location_no_session(db):
    result = get_current_location_info(db, 999)
    assert result is None


# ── Review queue ──────────────────────────────────────────────────────────

class TestReviewQueue:
    def test_pending_counts_zero_initially(self, db):
        counts = get_pending_review_counts(db)
        assert counts["locations"] == 0
        assert counts["npcs"] == 0

    def test_pending_counts_after_create(self, db):
        db.execute("UPDATE game_locations SET review_status='pending_review' WHERE key='loc_tavern'")
        db.commit()
        counts = get_pending_review_counts(db)
        assert counts["locations"] == 1

    def test_approve_entity(self, db):
        db.execute("UPDATE npcs SET review_status='pending_review' WHERE key='innkeeper_boris'")
        db.commit()
        ok = approve_entity(db, "npc", "innkeeper_boris")
        assert ok is True
        row = db.execute("SELECT review_status FROM npcs WHERE key='innkeeper_boris'").fetchone()
        assert row[0] == "permanent"

    def test_discard_entity(self, db):
        db.execute("UPDATE npcs SET review_status='pending_review' WHERE key='innkeeper_boris'")
        db.commit()
        ok = discard_entity(db, "npc", "innkeeper_boris")
        assert ok is True
        row = db.execute("SELECT review_status FROM npcs WHERE key='innkeeper_boris'").fetchone()
        assert row[0] == "discarded"

    def test_approve_unknown_type_returns_false(self, db):
        ok = approve_entity(db, "item", "sword_iron")
        assert ok is False
