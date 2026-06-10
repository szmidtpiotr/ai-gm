"""TDD: Issue #462 — F2 Affix System: loot engine rolls affixes per dungeon tier.

roll_weapon_affixes(loot_tier, conn) picks affix keys filtered by tier config.
grant_loot_to_character(... loot_tier=) writes affixes_json to weapon inventory row.
dungeon_service.generate_dungeon_instance includes loot_tier so the API can pass it through.
"""
import sys
sys.path.insert(0, '/app')

import json
import random
import sqlite3
import inspect


# ── Helpers ───────────────────────────────────────────────────────────────────

def _affix_conn():
    """In-memory DB with 3 affixes (T1/T2/T3) for isolated roll tests."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE game_config_affixes (
            key TEXT PRIMARY KEY, name TEXT, tier INTEGER DEFAULT 1,
            allowed_item_types TEXT, effect_json TEXT, is_active INTEGER DEFAULT 1
        )
    """)
    conn.executemany(
        "INSERT INTO game_config_affixes (key, name, tier, allowed_item_types, is_active) VALUES (?,?,?,?,1)",
        [("sharp","Ostry",1,"weapon"), ("keen","Wyostrzony",2,"weapon"), ("brutal","Brutalny",3,"weapon")],
    )
    conn.commit()
    return conn


# ── TestRollWeaponAffixes ─────────────────────────────────────────────────────

class TestRollWeaponAffixes:
    """Unit tests for roll_weapon_affixes — needs in-memory DB, no app infra."""

    def test_poor_loot_gives_no_affixes(self):
        from app.services.loot_service import roll_weapon_affixes
        assert roll_weapon_affixes("poor", _affix_conn()) == []

    def test_standard_at_most_one_t1_affix(self):
        from app.services.loot_service import roll_weapon_affixes
        conn = _affix_conn()
        random.seed(0)
        for _ in range(300):
            r = roll_weapon_affixes("standard", conn)
            assert len(r) <= 1, f"standard: max 1 affix, got {r}"
            for k in r:
                assert k == "sharp", f"standard: only T1 allowed, got {k}"

    def test_rich_at_most_two_t1_t2_affixes(self):
        from app.services.loot_service import roll_weapon_affixes
        conn = _affix_conn()
        random.seed(42)
        for _ in range(300):
            r = roll_weapon_affixes("rich", conn)
            assert len(r) <= 2, f"rich: max 2 affixes, got {r}"
            for k in r:
                assert k in ("sharp", "keen"), f"rich: only T1/T2 allowed, got {k}"

    def test_no_duplicate_affixes_in_one_roll(self):
        from app.services.loot_service import roll_weapon_affixes
        conn = _affix_conn()
        random.seed(7)
        for _ in range(300):
            r = roll_weapon_affixes("rich", conn)
            assert len(r) == len(set(r)), f"duplicate affix keys: {r}"

    def test_unknown_tier_gives_no_affixes(self):
        from app.services.loot_service import roll_weapon_affixes
        assert roll_weapon_affixes("legendary_ultra", _affix_conn()) == []

    def test_empty_tier_gives_no_affixes(self):
        from app.services.loot_service import roll_weapon_affixes
        assert roll_weapon_affixes("", _affix_conn()) == []

    def test_returns_list_of_strings(self):
        from app.services.loot_service import roll_weapon_affixes
        conn = _affix_conn()
        random.seed(99)
        r = roll_weapon_affixes("standard", conn)
        assert isinstance(r, list)
        for k in r:
            assert isinstance(k, str)


# ── TestGrantLootAffixSignature ───────────────────────────────────────────────

class TestGrantLootAffixSignature:
    """Signature/API contract tests — no DB calls needed."""

    def test_grant_loot_to_character_accepts_loot_tier(self):
        from app.services.loot_service import grant_loot_to_character
        sig = inspect.signature(grant_loot_to_character)
        assert "loot_tier" in sig.parameters, "grant_loot_to_character must accept loot_tier"
        p = sig.parameters["loot_tier"]
        assert p.default is not inspect.Parameter.empty, "loot_tier must be optional"

    def test_grant_dungeon_loot_accepts_loot_tier(self):
        from app.services.dungeon_service import grant_dungeon_loot
        sig = inspect.signature(grant_dungeon_loot)
        assert "loot_tier" in sig.parameters, "grant_dungeon_loot must accept loot_tier"

    def test_dungeon_instance_includes_loot_tier(self):
        from app.services.dungeon_service import generate_dungeon_instance
        instance = generate_dungeon_instance("goblin_warren", hero_level=3)
        assert "loot_tier" in instance, "dungeon run instance must include loot_tier field"
        assert isinstance(instance["loot_tier"], str), "loot_tier must be a string"
        assert instance["loot_tier"], "loot_tier must not be empty"
