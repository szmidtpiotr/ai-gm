"""TDD #1024 — level-up na długim odpoczynku: max_hp i max_mana rosną przy awansie."""
import json
import sqlite3
import sys
import os

sys.path.insert(0, "/app")
from _fixtures_schema import table_sql
os.environ.setdefault("AIGM_E2E_LITE", "1")

import pytest


# ── Minimal in-memory schema ──────────────────────────────────────────────────

def _make_db(tmp_path):
    conn = sqlite3.connect(str(tmp_path / "test_1024.db"))
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE characters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL DEFAULT 1,
            user_id INTEGER NOT NULL DEFAULT 1,
            name TEXT NOT NULL DEFAULT 'TestHero',
            system_id TEXT NOT NULL DEFAULT 'fantasy',
            sheet_json TEXT NOT NULL DEFAULT '{}',
            is_active INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE campaigns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL DEFAULT 'TestCamp',
            owner_user_id INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE game_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL,
            current_location_id INTEGER,
            session_flags TEXT DEFAULT '{}',
            ingame_hours INTEGER DEFAULT 8
        );
        CREATE TABLE game_locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT,
            label TEXT,
            safe_for_rest INTEGER DEFAULT 1,
            is_active INTEGER DEFAULT 1
        );
        CREATE TABLE world_hexes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            q INTEGER, r INTEGER, hex_type TEXT, label TEXT,
            location_key TEXT, map_level INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1
        );
        CREATE TABLE active_combat (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER,
            status TEXT DEFAULT 'inactive'
        );
        CREATE TABLE character_xp_grants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id INTEGER,
            campaign_id INTEGER,
            amount INTEGER,
            reason TEXT,
            source TEXT,
            source_key TEXT DEFAULT '',
            turn_number INTEGER,
            granted_by_user_id INTEGER DEFAULT 0
        );
        """ + table_sql("game_config_meta") + """
        INSERT INTO campaigns VALUES (1, 'TestCamp', 1);
        INSERT INTO game_locations VALUES (1, 'inn', 'Karczma', 1, 1);
        INSERT INTO game_sessions VALUES (1, 1, 1, '{}', 8);
    """)
    return conn


def _make_sheet(
    archetype="rogue",
    level=1,
    max_hp=10,
    current_hp=10,
    max_mana=0,
    current_mana=0,
    con=14,
    int_stat=10,
    pending_xp=0,
    xp_lifetime=50,
    xp_available=0,
):
    """Simulate post-grant_pending_xp state: xp_lifetime already includes pending."""
    stats = {
        "STR": 10, "DEX": 12, "CON": con, "INT": int_stat,
        "WIS": 10, "CHA": 10, "LCK": 10,
    }
    return json.dumps({
        "level": level,
        "archetype": archetype,
        "stats": stats,
        "max_hp": max_hp,
        "current_hp": current_hp,
        "max_mana": max_mana,
        "current_mana": current_mana,
        "pending_xp": pending_xp,
        "xp_lifetime_earned": xp_lifetime,
        "xp_available": xp_available,
        "short_rests_used": 0,
        "death_saves_failed": 0,
        "conditions": [],
    })


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestLevelUpOnLongRest:
    """#1024 — awans poziomu przy długim odpoczynku podnosi max_hp i max_mana."""

    def test_rogue_max_hp_grows_on_levelup(self, tmp_path):
        """Rogue lvl1→2: max_hp musi wzrosnąć o CON_mod (CON=14, mod=+2)."""
        conn = _make_db(tmp_path)
        # Rogue base=8, CON=14→mod+2: lvl1=10, lvl2=12.
        # xp_lifetime=100 (threshold lvl2=100), pending=100 (not yet flushed).
        # grant_pending_xp already updated xp_lifetime to 100.
        sheet_json = _make_sheet(
            archetype="rogue", level=1, max_hp=10, current_hp=5, con=14,
            pending_xp=100, xp_lifetime=100, xp_available=0,
        )
        conn.execute(
            "INSERT INTO characters (campaign_id, user_id, name, sheet_json) VALUES (1,1,'Rogue',?)",
            (sheet_json,),
        )
        char_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        from app.services.rest_service import perform_long_rest
        result = perform_long_rest(conn, char_id, 1)

        assert result["ok"] is True, f"Long rest failed: {result}"
        row = conn.execute("SELECT sheet_json FROM characters WHERE id = ?", (char_id,)).fetchone()
        sheet = json.loads(row["sheet_json"])

        assert sheet["level"] == 2, f"Oczekiwano level=2, dostano {sheet['level']}"
        assert sheet["max_hp"] == 12, f"Oczekiwano max_hp=12 (8+2×2), dostano {sheet['max_hp']}"
        assert sheet["current_hp"] == 12, "current_hp musi być równe nowemu max_hp po długim odpoczynku"

    def test_scholar_max_mana_grows_on_levelup(self, tmp_path):
        """Scholar lvl1→2: max_mana musi wzrosnąć o INT_mod (INT=12, mod=+1)."""
        conn = _make_db(tmp_path)
        # Scholar: HP base=6, CON=10→mod=0. Mana base=8, INT=12→mod+1.
        # lvl1 mana=9, lvl2 mana=10.
        sheet_json = _make_sheet(
            archetype="scholar", level=1, max_hp=6, current_hp=3,
            max_mana=9, current_mana=4, con=10, int_stat=12,
            pending_xp=100, xp_lifetime=100, xp_available=0,
        )
        conn.execute(
            "INSERT INTO characters (campaign_id, user_id, name, sheet_json) VALUES (1,1,'Scholar',?)",
            (sheet_json,),
        )
        char_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        from app.services.rest_service import perform_long_rest
        result = perform_long_rest(conn, char_id, 1)

        assert result["ok"] is True
        row = conn.execute("SELECT sheet_json FROM characters WHERE id = ?", (char_id,)).fetchone()
        sheet = json.loads(row["sheet_json"])

        assert sheet["level"] == 2, f"Oczekiwano level=2, dostano {sheet['level']}"
        assert sheet["max_mana"] == 10, f"Oczekiwano max_mana=10 (8+1×2), dostano {sheet['max_mana']}"
        assert sheet["current_mana"] == 10, "current_mana musi zostać przywrócona do nowego max po długim odpoczynku"

    def test_no_levelup_no_hp_change(self, tmp_path):
        """Backward compat: długi odpoczynek bez progu poziomu nie zmienia max_hp."""
        conn = _make_db(tmp_path)
        # xp_lifetime=50 (threshold lvl2=100 nie osiągnięty), pending=0.
        sheet_json = _make_sheet(
            archetype="rogue", level=1, max_hp=10, current_hp=3, con=14,
            pending_xp=0, xp_lifetime=50, xp_available=50,
        )
        conn.execute(
            "INSERT INTO characters (campaign_id, user_id, name, sheet_json) VALUES (1,1,'Rogue',?)",
            (sheet_json,),
        )
        char_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        from app.services.rest_service import perform_long_rest
        result = perform_long_rest(conn, char_id, 1)

        assert result["ok"] is True
        row = conn.execute("SELECT sheet_json FROM characters WHERE id = ?", (char_id,)).fetchone()
        sheet = json.loads(row["sheet_json"])

        assert sheet["level"] == 1, "Poziom nie może wzrosnąć bez przekroczenia progu XP"
        assert sheet["max_hp"] == 10, "max_hp nie może zmienić się bez awansu poziomu"
        assert sheet["current_hp"] == 10, "current_hp przywrócone do max_hp po długim odpoczynku"

    def test_multi_levelup_in_one_rest(self, tmp_path):
        """Awans o 2 poziomy naraz: max_hp rośnie proporcjonalnie (2× CON_mod)."""
        conn = _make_db(tmp_path)
        # Warrior base=10, CON=12→mod+1. lvl1=11, lvl2=12, lvl3=13.
        # xp_lifetime=250 (threshold lvl3=250), level stored=1.
        sheet_json = _make_sheet(
            archetype="warrior", level=1, max_hp=11, current_hp=5, con=12,
            pending_xp=250, xp_lifetime=250, xp_available=0,
        )
        conn.execute(
            "INSERT INTO characters (campaign_id, user_id, name, sheet_json) VALUES (1,1,'Warrior',?)",
            (sheet_json,),
        )
        char_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        from app.services.rest_service import perform_long_rest
        result = perform_long_rest(conn, char_id, 1)

        assert result["ok"] is True
        row = conn.execute("SELECT sheet_json FROM characters WHERE id = ?", (char_id,)).fetchone()
        sheet = json.loads(row["sheet_json"])

        assert sheet["level"] == 3, f"Oczekiwano level=3, dostano {sheet['level']}"
        assert sheet["max_hp"] == 13, f"Oczekiwano max_hp=13 (10+1×3), dostano {sheet['max_hp']}"


# ── Backfill formula test ──────────────────────────────────────────────────────

class TestVitalityBackfill:
    """#1024: formuła calculate_hp poprawnie oblicza max_hp dla istniejących postaci."""

    def test_mizel_lvl4_rogue_con14_correct_hp(self):
        """Mizel (lvl4, rogue, CON=14) powinien mieć max_hp=16, nie 10."""
        from app.services.vitality_service import calculate_hp
        # rogue base=8, CON=14→mod+2: 8 + 2×4 = 16
        result = calculate_hp("rogue", 14, 4)
        assert result == 16, f"Mizel powinien mieć max_hp=16 przy lvl4, dostano {result}"

    def test_warrior_lvl4_con12_correct_hp(self):
        """Warrior lvl4, CON=12→mod+1: 10 + 1×4 = 14."""
        from app.services.vitality_service import calculate_hp
        result = calculate_hp("warrior", 12, 4)
        assert result == 14

    def test_scholar_lvl4_int12_correct_mana(self):
        """Scholar lvl4, INT=12→mod+1: mana = 8 + 1×4 = 12."""
        from app.services.vitality_service import calculate_mana
        result = calculate_mana("scholar", 12, 4)
        assert result == 12


class TestLevelUpFromCombatXp:
    """#1370 — XP z walk (enemy_defeat) idzie prosto do xp_lifetime_earned, bez
    pending_xp. Stary gate `pending_xp > 0` nigdy nie przeliczał poziomu takiemu
    bohaterowi — max HP/mana stały w miejscu mimo setek XP z walk."""

    def test_scholar_levels_up_from_combat_xp_without_pending(self, tmp_path):
        conn = _make_db(tmp_path)
        # Scholar INT=16 (mod +3): lvl1 mana=11. lifetime=311 (progi: lvl2=100,
        # lvl3=250) → po odpoczynku lvl 3, mana 11+3+3=17. pending_xp == 0!
        sheet_json = _make_sheet(
            archetype="scholar", level=1, max_hp=40, current_hp=30,
            max_mana=11, current_mana=5, con=12, int_stat=16,
            pending_xp=0, xp_lifetime=311, xp_available=48,
        )
        conn.execute(
            "INSERT INTO characters (campaign_id, user_id, name, sheet_json) VALUES (1,1,'Mag',?)",
            (sheet_json,),
        )
        char_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        from app.services.rest_service import perform_long_rest
        result = perform_long_rest(conn, char_id, 1)

        assert result["ok"] is True, f"Long rest failed: {result}"
        sheet = json.loads(conn.execute(
            "SELECT sheet_json FROM characters WHERE id = ?", (char_id,)
        ).fetchone()["sheet_json"])
        assert sheet["level"] == 3, f"Oczekiwano level=3, dostano {sheet['level']}"
        assert sheet["max_mana"] == 17, f"Oczekiwano max_mana=17 (11+3+3), dostano {sheet['max_mana']}"
        assert sheet["current_mana"] == 17

    def test_lifetime_not_double_counted_on_rest_with_pending(self, tmp_path):
        conn = _make_db(tmp_path)
        # grant_pending_xp doliczył lifetime przy nadaniu: lifetime=100 ZAWIERA
        # pending=100. Po odpoczynku lifetime MUSI zostać 100 (nie 200).
        sheet_json = _make_sheet(
            archetype="rogue", level=1, max_hp=10, current_hp=5, con=14,
            pending_xp=100, xp_lifetime=100, xp_available=0,
        )
        conn.execute(
            "INSERT INTO characters (campaign_id, user_id, name, sheet_json) VALUES (1,1,'Rogue',?)",
            (sheet_json,),
        )
        char_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        from app.services.rest_service import perform_long_rest
        assert perform_long_rest(conn, char_id, 1)["ok"] is True
        sheet = json.loads(conn.execute(
            "SELECT sheet_json FROM characters WHERE id = ?", (char_id,)
        ).fetchone()["sheet_json"])
        assert sheet["xp_lifetime_earned"] == 100, (
            f"lifetime podwójnie policzony: {sheet['xp_lifetime_earned']}"
        )
        assert sheet["xp_available"] == 100
        assert sheet["level"] == 2
