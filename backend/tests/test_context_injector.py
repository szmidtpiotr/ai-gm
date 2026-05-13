"""
Tests for Context Injector — V2 Phase 01 Task 04
"""
import json
import sqlite3
import pytest

from app.services.context_injector import (
    ContextInjector, PostProcessResult,
    _wound_label, _time_of_day,
    DEFAULT_TONE, NARRATOR_CONSTRAINTS,
)


# ── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE game_locations (
            key TEXT PRIMARY KEY, label TEXT, description TEXT,
            location_type TEXT, rules TEXT, safe_for_rest INTEGER DEFAULT 0,
            npc_keys TEXT DEFAULT '[]'
        );
        CREATE TABLE npcs (
            key TEXT PRIMARY KEY, label TEXT, npc_type TEXT DEFAULT 'neutral',
            personality_prompt TEXT, is_active INTEGER DEFAULT 1
        );
        CREATE TABLE location_npc_assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            location_key TEXT, npc_key TEXT, is_active INTEGER DEFAULT 1
        );
        CREATE TABLE characters (
            id INTEGER PRIMARY KEY, name TEXT, sheet_json TEXT
        );
        CREATE TABLE character_conditions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id INTEGER, condition_type TEXT, severity INTEGER DEFAULT 1,
            expires_at TEXT, source TEXT DEFAULT ''
        );
        CREATE TABLE campaigns (
            id INTEGER PRIMARY KEY, gm_plan_json TEXT DEFAULT '{}'
        );

        -- Seed
        INSERT INTO game_locations VALUES ('loc_tavern', 'Karczma Pod Krzyżem',
            'Ciepła tawerna z niskim stropem.', 'interior',
            '{"atmosphere": "Dym papierosów i zapach piwa."}', 2, '[]');
        INSERT INTO game_locations VALUES ('loc_dungeon', 'Loch', NULL, 'dungeon', NULL, 0, '[]');

        INSERT INTO npcs VALUES ('innkeeper_boris', 'Boris Karczmarz', 'neutral',
            'Mówi krótko. Zawsze podejrzliwy.', 1);
        INSERT INTO location_npc_assignments (location_key, npc_key) VALUES ('loc_tavern', 'innkeeper_boris');

        INSERT INTO characters VALUES (1, 'Aldric',
            '{"current_hp": 12, "max_hp": 12, "archetype": "warrior"}');
        INSERT INTO characters VALUES (2, 'Aldric Ranny',
            '{"current_hp": 3, "max_hp": 12}');
        INSERT INTO characters VALUES (3, 'Aldric Nieprzytomny',
            '{"current_hp": 0, "max_hp": 12}');

        INSERT INTO campaigns VALUES (1, '{}');
        INSERT INTO campaigns VALUES (2, '{"tone_descriptor": "Gotycki horror."}');
    """)
    conn.commit()
    yield conn
    conn.close()


@pytest.fixture
def inj(db):
    return ContextInjector(db)


def flags(location="loc_tavern", state="NARRATIVE", hours=9, roster=None):
    return {
        "state": state,
        "current_location_key": location,
        "ingame_hours": hours,
        "combat_roster": roster or [],
    }


# ── _wound_label ─────────────────────────────────────────────────────────

class TestWoundLabel:
    def test_full_hp(self):     assert _wound_label(12, 12) == "Zdrowy/a"
    def test_75pct(self):       assert _wound_label(9, 12) == "Lekko zadrapany/a"
    def test_50pct(self):       assert _wound_label(6, 12) == "Ranny/a"
    def test_25pct(self):       assert _wound_label(3, 12) == "Poważnie ranny/a"
    def test_10pct(self):       assert _wound_label(1, 12) == "Na skraju śmierci — ledwo oddycha"
    def test_zero_hp(self):     assert _wound_label(0, 12) == "Nieprzytomny/a — rzuty na śmierć"
    def test_zero_max(self):    assert "nieznany" in _wound_label(0, 0).lower()


# ── _time_of_day ─────────────────────────────────────────────────────────

class TestTimeOfDay:
    def test_dawn(self):        assert _time_of_day(6) == "świt"
    def test_morning(self):     assert _time_of_day(10) == "rano"
    def test_noon(self):        assert _time_of_day(14) == "południe"
    def test_evening(self):     assert _time_of_day(21) == "zmierzch"
    def test_night(self):       assert _time_of_day(23) == "noc"
    def test_wraps(self):       assert _time_of_day(33) == "rano"  # 33%24=9


# ── World Block ───────────────────────────────────────────────────────────

class TestWorldBlock:
    def test_has_location_name(self, inj):
        loc = inj._get_location("loc_tavern")
        block = inj._build_world_block(loc, 9)
        assert "Karczma Pod Krzyżem" in block

    def test_has_description(self, inj):
        loc = inj._get_location("loc_tavern")
        block = inj._build_world_block(loc, 9)
        assert "niskim stropem" in block

    def test_has_atmosphere_from_rules(self, inj):
        loc = inj._get_location("loc_tavern")
        block = inj._build_world_block(loc, 9)
        assert "piwa" in block

    def test_no_description_omits_opis_line(self, inj):
        loc = inj._get_location("loc_dungeon")
        assert loc is not None
        assert not (loc.get("description") or "").strip()  # confirm description is empty/null
        block = inj._build_world_block(loc, 22)
        assert "Opis:" not in block

    def test_time_of_day(self, inj):
        loc = inj._get_location("loc_tavern")
        block = inj._build_world_block(loc, 22)
        assert "zmierzch" in block or "noc" in block

    def test_none_location_graceful(self, inj):
        block = inj._build_world_block(None, 9)
        assert "nieznana" in block


# ── Entities Block ────────────────────────────────────────────────────────

class TestEntitiesBlock:
    def test_npc_shown(self, inj):
        npcs = inj._get_npcs_in_location("loc_tavern")
        block = inj._build_entities_block(npcs, [])
        assert "Boris Karczmarz" in block
        assert "Mówi krótko" in block

    def test_no_entities(self, inj):
        block = inj._build_entities_block([], [])
        assert "Brak postaci" in block

    def test_combat_enemies_listed(self, inj):
        roster = [
            {"key": "goblin_1", "name": "Goblin Strażnik", "hp": 8, "hp_max": 20, "tier": 1},
            {"key": "goblin_2", "name": "Goblin Szaman", "hp": 0, "hp_max": 18, "tier": 2},
        ]
        block = inj._build_entities_block([], roster)
        assert "Goblin Strażnik" in block
        assert "żywy" in block
        assert "Goblin Szaman" in block
        assert "martwy" in block

    def test_personality_truncated(self, inj, db):
        db.execute("UPDATE npcs SET personality_prompt = ? WHERE key = 'innkeeper_boris'",
                   ("x" * 300,))
        db.commit()
        npcs = inj._get_npcs_in_location("loc_tavern")
        block = inj._build_entities_block(npcs, [])
        personality_line = next(l for l in block.split("\n") if "Osobowość" in l)
        assert len(personality_line) <= 215  # "Osobowość: " + 200 chars


# ── Mechanic Blocks ───────────────────────────────────────────────────────

class TestMechanicBlocks:
    def test_attack_hit(self, inj):
        r = {"roll":17, "modifier":3, "total":20, "dc":14, "hit":True,
             "damage":8, "target_name":"Goblin", "target_hp_before":8, "target_hp_after":0, "target_dead":True}
        block = inj._mechanic_attack(r)
        assert "TRAFIENIE" in block
        assert "GINIE" in block
        assert "8" in block

    def test_attack_miss(self, inj):
        r = {"roll":5, "modifier":3, "total":8, "dc":14, "hit":False, "target_name":"Goblin"}
        block = inj._mechanic_attack(r)
        assert "PUDŁO" in block
        assert "GINIE" not in block

    def test_attack_crit(self, inj):
        r = {"roll":20, "modifier":3, "total":23, "dc":14, "hit":True, "crit":True,
             "damage":16, "target_name":"Goblin", "target_hp_before":8, "target_hp_after":0,
             "hit_location":"głowa"}
        block = inj._mechanic_attack(r)
        assert "KRYTYK" in block
        assert "głowa" in block

    def test_movement(self, inj):
        r = {"from_location_name": "Tawerna", "to_location_name": "Uliczka"}
        block = inj._mechanic_movement(r)
        assert "Tawerna" in block
        assert "Uliczka" in block

    def test_dialogue_must_reveal(self, inj):
        r = {"npc_name":"Boris", "topic":"guild",
             "must_reveal_info":"Gilda spotyka się przy dokach."}
        block = inj._mechanic_dialogue(r)
        assert "MUSI POWIEDZIEĆ" in block
        assert "dokach" in block

    def test_dialogue_secret_failed(self, inj):
        r = {"npc_name":"Boris", "topic":"morderstwo", "secret_roll":True,
             "roll":4, "modifier":1, "total":5, "dc":14, "success":False}
        block = inj._mechanic_dialogue(r)
        assert "PORAŻKA" in block
        assert "NIE zostaje ujawniony" in block
        assert "MUSI POWIEDZIEĆ" not in block

    def test_flee_success(self, inj):
        r = {"roll":15, "modifier":2, "total":17, "enemy_total":10,
             "success":True, "new_location_name":"Boczna uliczka"}
        block = inj._mechanic_flee(r)
        assert "UDANA" in block
        assert "Boczna uliczka" in block

    def test_rest_completed(self, inj):
        r = {"rest_type":"krótki", "status":"ZAKOŃCZONY",
             "hp_before":6, "hp_after":10, "cleared_conditions":[]}
        block = inj._mechanic_rest(r)
        assert "ZAKOŃCZONY" in block
        assert "6 → 10" in block


# ── Character State Block ─────────────────────────────────────────────────

class TestCharacterStateBlock:
    def test_full_hp_label(self, inj):
        char = inj._get_character(1)  # 12/12
        block = inj._build_character_state_block(char, [])
        assert "Zdrowy/a" in block

    def test_wounded_label(self, inj):
        char = inj._get_character(2)  # 3/12 = 25%
        block = inj._build_character_state_block(char, [])
        assert "Poważnie ranny" in block

    def test_unconscious_label(self, inj):
        char = inj._get_character(3)  # 0/12
        block = inj._build_character_state_block(char, [])
        assert "Nieprzytomny" in block

    def test_fear_condition_separate(self, inj):
        conditions = [{"condition_type": "fear_frightened", "severity": 2, "expires_at": None, "source": "test"}]
        char = inj._get_character(1)
        block = inj._build_character_state_block(char, conditions)
        assert "Przestraszony/a" in block
        assert "Strach:" in block
        # Fear NOT in aktywne stany
        active_line = next(l for l in block.split("\n") if "Aktywne" in l)
        assert "fear_frightened" not in active_line

    def test_other_conditions_listed(self, inj):
        conditions = [{"condition_type": "poisoned", "severity": 1, "expires_at": None, "source": "test"}]
        char = inj._get_character(1)
        block = inj._build_character_state_block(char, conditions)
        assert "poisoned" in block


# ── Campaign Tone Block ───────────────────────────────────────────────────

def test_default_tone(inj):
    tone = inj._get_campaign_tone(1)
    assert "mroczne" in tone.lower() or "Mroczne" in tone

def test_custom_tone(inj):
    tone = inj._get_campaign_tone(2)
    assert "Gotycki" in tone


# ── Full build() ─────────────────────────────────────────────────────────

class TestBuildFull:
    def test_all_blocks_present(self, inj):
        result = inj.build(
            session_flags=flags("loc_tavern"),
            mechanic_result={"from_location_name":"Wejście", "to_location_name":"Karczma"},
            action_type="MOVEMENT",
            character_id=1,
            campaign_id=1,
        )
        assert "=== ŚWIAT ===" in result
        assert "=== POSTACIE NA SCENIE ===" in result
        assert "=== WYNIK MECHANICZNY ===" in result
        assert "=== STAN POSTACI ===" in result
        assert "=== TON KAMPANII ===" in result
        assert "=== INSTRUKCJE DLA NARRATORA ===" in result

    def test_no_null_or_none_leaked(self, inj):
        result = inj.build(
            session_flags=flags("loc_dungeon"),
            mechanic_result={"focus": "clues", "roll":10, "modifier":2, "total":12, "dc":14, "success":False},
            action_type="SEARCH",
            character_id=1,
            campaign_id=1,
        )
        assert "None" not in result
        assert "null" not in result.lower().replace("neutralny", "")  # 'neutral' is valid

    def test_combat_turn_full(self, inj):
        roster = [{"key":"g1","name":"Goblin","hp":5,"hp_max":12,"tier":1}]
        result = inj.build(
            session_flags=flags("loc_tavern", state="COMBAT", roster=roster),
            mechanic_result={"roll":15,"modifier":3,"total":18,"dc":11,"hit":True,
                             "damage":6,"target_name":"Goblin","target_hp_before":11,
                             "target_hp_after":5,"target_dead":False},
            action_type="ATTACK",
            character_id=1,
            campaign_id=1,
        )
        assert "Goblin" in result
        assert "TRAFIENIE" in result
        assert "=== INSTRUKCJE DLA NARRATORA ===" in result


# ── Post-processing ───────────────────────────────────────────────────────

class TestPostProcess:
    def test_must_reveal_present(self, inj):
        response = "Boris wspomina, że gilda spotyka się przy dokach w środy."
        r = inj.post_process(
            narrator_response=response,
            session_flags=flags(),
            mechanic_result={},
            must_reveal_infos=["Gilda spotyka się w środy przy dokach."],
        )
        assert r.retry_needed is False

    def test_must_reveal_missing(self, inj):
        response = "Boris mruczy coś pod nosem i odwraca wzrok."
        r = inj.post_process(
            narrator_response=response,
            session_flags=flags(),
            mechanic_result={},
            must_reveal_infos=["Gilda spotyka się w środy przy dokach."],
        )
        assert r.retry_needed is True

    def test_no_must_reveal_no_retry(self, inj):
        r = inj.post_process(
            narrator_response="Goblin pada martwy na ziemię.",
            session_flags=flags(),
            mechanic_result={},
        )
        assert r.retry_needed is False

    def test_build_retry_prompt(self, inj):
        retry = inj.build_retry_prompt(
            "original prompt",
            reason="must_reveal",
            must_reveal_info="Gilda spotyka się przy dokach.",
        )
        assert "KONIECZNIE" in retry
        assert "dokach" in retry
        assert "original prompt" in retry
