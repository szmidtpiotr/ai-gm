"""TDD #795 — G10: Per-player loot rolls (class filter) + equal gold split in MP combat."""
import json
import random
import sqlite3
import sys
import os

sys.path.insert(0, "/app")
os.environ.setdefault("AIGM_E2E_LITE", "1")

import pytest


# ── Minimal DB schema for loot tests ─────────────────────────────────────────

def _make_loot_db(tmp_path):
    """Build a temp DB with just the tables loot_service needs."""
    db_path = str(tmp_path / "test_795.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE game_config_enemies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL DEFAULT '',
            loot_table_key TEXT,
            drop_chance REAL NOT NULL DEFAULT 1.0,
            xp_award INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE game_config_loot_tables (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT NOT NULL UNIQUE,
            label TEXT NOT NULL DEFAULT '',
            gold_min INTEGER NOT NULL DEFAULT 0,
            gold_max INTEGER NOT NULL DEFAULT 0,
            is_active INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE game_config_loot_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            loot_table_key TEXT NOT NULL,
            item_key TEXT,
            weapon_key TEXT,
            consumable_key TEXT,
            weight INTEGER NOT NULL DEFAULT 100,
            qty_min INTEGER NOT NULL DEFAULT 1,
            qty_max INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE game_config_weapons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT NOT NULL UNIQUE,
            label TEXT NOT NULL DEFAULT '',
            allowed_classes TEXT NOT NULL DEFAULT '[]',
            linked_stat TEXT DEFAULT NULL,
            is_active INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE game_config_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT NOT NULL UNIQUE,
            label TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE game_config_consumables (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT NOT NULL UNIQUE,
            label TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE characters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER,
            user_id INTEGER NOT NULL DEFAULT 0,
            name TEXT NOT NULL DEFAULT '',
            system_id TEXT NOT NULL DEFAULT 'fantasy',
            sheet_json TEXT NOT NULL DEFAULT '{}'
        );
        CREATE TABLE character_inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id INTEGER NOT NULL,
            item_key TEXT NOT NULL,
            item_type TEXT NOT NULL DEFAULT 'item',
            quantity INTEGER NOT NULL DEFAULT 1,
            source TEXT NOT NULL DEFAULT 'loot',
            acquired_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            slot TEXT DEFAULT NULL,
            affixes_json TEXT DEFAULT NULL
        );
        CREATE TABLE campaign_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            role TEXT NOT NULL DEFAULT 'player',
            status TEXT NOT NULL DEFAULT 'accepted',
            character_id INTEGER,
            joined_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            absence_warnings INTEGER NOT NULL DEFAULT 0,
            UNIQUE(campaign_id, user_id)
        );
        CREATE TABLE campaigns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL DEFAULT 'Test',
            owner_user_id INTEGER NOT NULL DEFAULT 1,
            mode TEXT NOT NULL DEFAULT 'multiplayer',
            status TEXT NOT NULL DEFAULT 'active'
        );
    """)
    conn.commit()
    return db_path, conn


def _seed_test_data(conn):
    """
    Enemy 'goblin' → loot table 'loot_goblin':
      - shortsword (weapon, warrior/ranger only)
      - staff (weapon, scholar only)
      - health_potion (consumable, no class filter)
    Gold: 10-20.
    """
    conn.execute(
        "INSERT INTO game_config_weapons (key, label, allowed_classes, linked_stat) VALUES "
        "('shortsword', 'Krótki miecz', '[\"warrior\",\"ranger\"]', 'STR')"
    )
    conn.execute(
        "INSERT INTO game_config_weapons (key, label, allowed_classes, linked_stat) VALUES "
        "('staff', 'Laska', '[\"scholar\"]', 'INT')"
    )
    conn.execute(
        "INSERT INTO game_config_loot_tables (key, label, gold_min, gold_max, is_active) VALUES "
        "('loot_goblin', 'Goblin Loot', 10, 20, 1)"
    )
    conn.execute(
        "INSERT INTO game_config_enemies (key, name, loot_table_key, drop_chance) VALUES "
        "('goblin', 'Goblin', 'loot_goblin', 1.0)"
    )
    # Weapon entries — weight=100 so always drops
    conn.execute(
        "INSERT INTO game_config_loot_entries (loot_table_key, weapon_key, weight) VALUES "
        "('loot_goblin', 'shortsword', 100)"
    )
    conn.execute(
        "INSERT INTO game_config_loot_entries (loot_table_key, weapon_key, weight) VALUES "
        "('loot_goblin', 'staff', 100)"
    )
    # Classless consumable — always goes to everyone
    conn.execute(
        "INSERT INTO game_config_loot_entries (loot_table_key, consumable_key, weight) VALUES "
        "('loot_goblin', 'health_potion', 100)"
    )
    conn.commit()


def _seed_characters(conn):
    """3 characters: warrior, scholar, rogue — all members of campaign 1."""
    conn.execute("INSERT INTO campaigns (id, title, owner_user_id) VALUES (1, 'TestCamp', 1)")
    for i, arch in enumerate([('warrior', 10, 15), ('scholar', 20, 30), ('rogue', 40, 50)], start=1):
        archetype, gold, user_id = arch
        conn.execute(
            "INSERT INTO characters (id, campaign_id, user_id, name, sheet_json) VALUES "
            "(?, 1, ?, ?, ?)",
            (i, user_id, f"{archetype.title()}", json.dumps({"archetype": archetype, "gold": gold}))
        )
        conn.execute(
            "INSERT INTO campaign_members (campaign_id, user_id, character_id, status) VALUES "
            "(1, ?, ?, 'accepted')",
            (user_id, i)
        )
    conn.commit()


# ── FAZA 1 RED — Tests that MUST fail before implementation ──────────────────

class TestRollLootForClass:
    """roll_loot_for_class(enemy_key, archetype) — new function."""

    def test_scholar_gets_staff_not_shortsword(self, tmp_path, monkeypatch):
        """Scholar archetype should receive staff (INT weapon) but not shortsword (warrior)."""
        db_path, conn = _make_loot_db(tmp_path)
        _seed_test_data(conn)
        conn.close()

        import app.services.loot_service as ls
        monkeypatch.setattr(ls, "LOOT_DB_PATH", db_path)

        from app.services.loot_service import roll_loot_for_class
        # Run many times to ensure shortsword never appears for scholar
        for _ in range(20):
            items = roll_loot_for_class("goblin", "scholar")
            weapon_keys = [i["weapon_key"] for i in items if i.get("weapon_key")]
            assert "shortsword" not in weapon_keys, "Scholar should NOT receive shortsword"
            # staff is allowed for scholar
            # (may or may not appear per roll — that's fine)

    def test_warrior_gets_shortsword_not_staff(self, tmp_path, monkeypatch):
        """Warrior archetype should receive shortsword (STR weapon) but never staff (scholar)."""
        db_path, conn = _make_loot_db(tmp_path)
        _seed_test_data(conn)
        conn.close()

        import app.services.loot_service as ls
        monkeypatch.setattr(ls, "LOOT_DB_PATH", db_path)

        from app.services.loot_service import roll_loot_for_class
        for _ in range(20):
            items = roll_loot_for_class("goblin", "warrior")
            weapon_keys = [i["weapon_key"] for i in items if i.get("weapon_key")]
            assert "staff" not in weapon_keys, "Warrior should NOT receive staff"

    def test_rogue_maps_to_ranger_class(self, tmp_path, monkeypatch):
        """Rogue archetype maps to 'ranger' in allowed_classes — gets shortsword, not staff."""
        db_path, conn = _make_loot_db(tmp_path)
        _seed_test_data(conn)
        conn.close()

        import app.services.loot_service as ls
        monkeypatch.setattr(ls, "LOOT_DB_PATH", db_path)

        from app.services.loot_service import roll_loot_for_class
        for _ in range(20):
            items = roll_loot_for_class("goblin", "rogue")
            weapon_keys = [i["weapon_key"] for i in items if i.get("weapon_key")]
            assert "staff" not in weapon_keys, "Rogue should NOT receive staff (scholar-only)"

    def test_classless_items_always_included(self, tmp_path, monkeypatch):
        """Consumables/items with no class restriction go to every archetype."""
        db_path, conn = _make_loot_db(tmp_path)
        _seed_test_data(conn)
        conn.close()

        import app.services.loot_service as ls
        monkeypatch.setattr(ls, "LOOT_DB_PATH", db_path)

        from app.services.loot_service import roll_loot_for_class
        # With weight=100, health_potion should always appear
        for arch in ("warrior", "scholar", "rogue"):
            items = roll_loot_for_class("goblin", arch)
            consumable_keys = [i["consumable_key"] for i in items if i.get("consumable_key")]
            assert "health_potion" in consumable_keys, \
                f"{arch} should always receive health_potion (classless)"

    def test_empty_allowed_classes_means_all_archetypes(self, tmp_path, monkeypatch):
        """Weapon with allowed_classes=[] is not class-restricted — everyone can receive it."""
        db_path, conn = _make_loot_db(tmp_path)
        _seed_test_data(conn)
        # Add a generic weapon with empty allowed_classes
        conn.execute(
            "INSERT INTO game_config_weapons (key, label, allowed_classes) VALUES "
            "('generic_blade', 'Generic Blade', '[]')"
        )
        conn.execute(
            "INSERT INTO game_config_loot_entries (loot_table_key, weapon_key, weight) VALUES "
            "('loot_goblin', 'generic_blade', 100)"
        )
        conn.commit()
        conn.close()

        import app.services.loot_service as ls
        monkeypatch.setattr(ls, "LOOT_DB_PATH", db_path)

        from app.services.loot_service import roll_loot_for_class
        for arch in ("warrior", "scholar", "rogue"):
            items = roll_loot_for_class("goblin", arch)
            weapon_keys = [i["weapon_key"] for i in items if i.get("weapon_key")]
            assert "generic_blade" in weapon_keys, \
                f"{arch} should receive generic_blade (no class restriction)"


class TestDistributeMpLoot:
    """distribute_mp_loot(campaign_id, enemy_key, conn) — new function."""

    def test_each_member_gets_own_roll(self, tmp_path, monkeypatch):
        """Each accepted campaign member gets an independent loot roll."""
        db_path, conn = _make_loot_db(tmp_path)
        _seed_test_data(conn)
        _seed_characters(conn)
        conn.close()

        import app.services.loot_service as ls
        monkeypatch.setattr(ls, "LOOT_DB_PATH", db_path)

        from app.services.loot_service import distribute_mp_loot
        result = distribute_mp_loot(campaign_id=1, enemy_key="goblin")

        assert "per_player" in result, "distribute_mp_loot must return per_player dict"
        assert len(result["per_player"]) == 3, \
            "3 accepted members should each get a loot entry"

    def test_gold_split_equally_3_players(self, tmp_path, monkeypatch):
        """Gold is split equally; rounding remainder goes to one player (total is preserved)."""
        db_path, conn = _make_loot_db(tmp_path)
        _seed_test_data(conn)
        _seed_characters(conn)
        conn.close()

        import app.services.loot_service as ls
        monkeypatch.setattr(ls, "LOOT_DB_PATH", db_path)

        # Patch roll_gold_drop to return a fixed 10 gold
        monkeypatch.setattr(ls, "roll_gold_drop", lambda ek: 10)

        from app.services.loot_service import distribute_mp_loot
        result = distribute_mp_loot(campaign_id=1, enemy_key="goblin")

        total_distributed = sum(p["gold"] for p in result["per_player"].values())
        assert total_distributed == 10, \
            f"Total gold distributed ({total_distributed}) must equal base gold drop (10)"
        # Each share ≥ 3 (floor(10/3)=3, one gets +1=4)
        for cid, p in result["per_player"].items():
            assert p["gold"] >= 3, f"char {cid} should get at least floor(10/3)=3 gold"

    def test_gold_split_equally_2_players(self, tmp_path, monkeypatch):
        """2 players: 20 gold → each gets 10."""
        db_path, conn = _make_loot_db(tmp_path)
        _seed_test_data(conn)
        # Only 2 members
        conn.execute("INSERT INTO campaigns (id, title, owner_user_id) VALUES (1, 'TestCamp', 1)")
        for i, arch in enumerate([("warrior", 10), ("scholar", 20)], start=1):
            archetype, user_id = arch
            conn.execute(
                "INSERT INTO characters (id, campaign_id, user_id, name, sheet_json) VALUES "
                "(?, 1, ?, ?, ?)",
                (i, user_id, archetype.title(), json.dumps({"archetype": archetype, "gold": 0}))
            )
            conn.execute(
                "INSERT INTO campaign_members (campaign_id, user_id, character_id, status) VALUES "
                "(1, ?, ?, 'accepted')",
                (user_id, i)
            )
        conn.commit()
        conn.close()

        import app.services.loot_service as ls
        monkeypatch.setattr(ls, "LOOT_DB_PATH", db_path)
        monkeypatch.setattr(ls, "roll_gold_drop", lambda ek: 20)

        from app.services.loot_service import distribute_mp_loot
        result = distribute_mp_loot(campaign_id=1, enemy_key="goblin")

        total = sum(p["gold"] for p in result["per_player"].values())
        assert total == 20
        for p in result["per_player"].values():
            assert p["gold"] == 10

    def test_no_gold_lost_on_odd_split(self, tmp_path, monkeypatch):
        """Gold remainder (3 players, 10 gold → 3+3+4) sums to full amount."""
        db_path, conn = _make_loot_db(tmp_path)
        _seed_test_data(conn)
        _seed_characters(conn)
        conn.close()

        import app.services.loot_service as ls
        monkeypatch.setattr(ls, "LOOT_DB_PATH", db_path)
        monkeypatch.setattr(ls, "roll_gold_drop", lambda ek: 7)  # 7 / 3 = 2+2+3

        from app.services.loot_service import distribute_mp_loot
        result = distribute_mp_loot(campaign_id=1, enemy_key="goblin")
        total = sum(p["gold"] for p in result["per_player"].values())
        assert total == 7, f"No gold should be lost in split — expected 7, got {total}"

    def test_only_accepted_members_get_loot(self, tmp_path, monkeypatch):
        """Members with status != 'accepted' (e.g. 'invited') don't receive loot."""
        db_path, conn = _make_loot_db(tmp_path)
        _seed_test_data(conn)
        _seed_characters(conn)
        # Add pending member who should NOT get loot
        conn.execute(
            "INSERT INTO characters (id, campaign_id, user_id, name, sheet_json) VALUES "
            "(99, 1, 99, 'Pending', ?)",
            (json.dumps({"archetype": "warrior"}),)
        )
        conn.execute(
            "INSERT INTO campaign_members (campaign_id, user_id, character_id, status) VALUES "
            "(1, 99, 99, 'invited')"
        )
        conn.commit()
        conn.close()

        import app.services.loot_service as ls
        monkeypatch.setattr(ls, "LOOT_DB_PATH", db_path)

        from app.services.loot_service import distribute_mp_loot
        result = distribute_mp_loot(campaign_id=1, enemy_key="goblin")
        assert 99 not in result["per_player"], \
            "Invited (non-accepted) member should not receive loot"
        assert len(result["per_player"]) == 3  # only the 3 accepted


class TestSoloCompatibility:
    """roll_loot() (no class filter) must behave exactly as before — no regression."""

    def test_solo_roll_loot_unchanged(self, tmp_path, monkeypatch):
        """roll_loot(enemy_key) returns all entries regardless of class — solo behavior."""
        db_path, conn = _make_loot_db(tmp_path)
        _seed_test_data(conn)
        conn.close()

        import app.services.loot_service as ls
        monkeypatch.setattr(ls, "LOOT_DB_PATH", db_path)

        from app.services.loot_service import roll_loot
        # With weight=100 all three entries should roll
        found_weapon_keys: set[str] = set()
        for _ in range(30):
            items = roll_loot("goblin")
            for item in items:
                if item.get("weapon_key"):
                    found_weapon_keys.add(item["weapon_key"])

        # Both weapons appear in solo rolls (no filter)
        assert "shortsword" in found_weapon_keys, "Solo should include shortsword"
        assert "staff" in found_weapon_keys, "Solo should include staff"


class TestMpLootWeightScale:
    """MP_LOOT_WEIGHT_SCALE flag — sandbox-tunable (default 1.0, value changes drop rate)."""

    def test_mp_loot_weight_scale_constant_exists(self):
        """MP_LOOT_WEIGHT_SCALE must exist in loot_service as a module-level constant."""
        from app.services import loot_service
        assert hasattr(loot_service, "MP_LOOT_WEIGHT_SCALE"), \
            "MP_LOOT_WEIGHT_SCALE constant must exist in loot_service"
        # Default value 1.0 = no scaling
        assert loot_service.MP_LOOT_WEIGHT_SCALE == 1.0

    def test_mp_loot_weight_scale_affects_chance(self, tmp_path, monkeypatch):
        """Setting MP_LOOT_WEIGHT_SCALE=0.0 makes nothing drop (extreme test for wiring)."""
        db_path, conn = _make_loot_db(tmp_path)
        _seed_test_data(conn)
        conn.close()

        import app.services.loot_service as ls
        monkeypatch.setattr(ls, "LOOT_DB_PATH", db_path)
        monkeypatch.setattr(ls, "MP_LOOT_WEIGHT_SCALE", 0.0)

        from app.services.loot_service import roll_loot_for_class
        # With scale=0.0 all chances become 0 → nothing drops
        for _ in range(10):
            items = roll_loot_for_class("goblin", "warrior")
            assert items == [], \
                "MP_LOOT_WEIGHT_SCALE=0.0 should prevent all drops"
