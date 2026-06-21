"""TDD #807 — G26: Party level scaling (max-1 rule) + catch-up XP."""
import importlib
import json
import sqlite3
import sys
import os
from typing import Any

sys.path.insert(0, "/app")
os.environ.setdefault("AIGM_E2E_LITE", "1")

import pytest


# ── Minimal DB schema ────────────────────────────────────────────────────────

def _make_db(tmp_path, suffix=""):
    db_path = str(tmp_path / f"test_807{suffix}.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS campaigns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL DEFAULT 'test',
            owner_user_id INTEGER NOT NULL DEFAULT 1,
            mode TEXT NOT NULL DEFAULT 'multiplayer',
            status TEXT NOT NULL DEFAULT 'active'
        );
        CREATE TABLE IF NOT EXISTS characters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER,
            user_id INTEGER NOT NULL DEFAULT 1,
            name TEXT NOT NULL DEFAULT 'Hero',
            is_active INTEGER NOT NULL DEFAULT 1,
            sheet_json TEXT NOT NULL DEFAULT '{}'
        );
        CREATE TABLE IF NOT EXISTS game_config_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS character_xp_grants (
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
    """)
    return db_path, conn


def _add_hero(conn, campaign_id, level, is_active=1):
    conn.execute(
        "INSERT INTO characters (campaign_id, is_active, sheet_json) VALUES (?,?,?)",
        (campaign_id, is_active, json.dumps({"level": level})),
    )
    conn.commit()
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


# ── encounter_service helpers ────────────────────────────────────────────────

def _import_encounter(db_path):
    import app.services.encounter_service as m
    importlib.reload(m)
    return m


# ── FAZA 1 RED: _party_levels_for_campaign ───────────────────────────────────

class TestPartyLevelsForCampaign:
    def test_solo_returns_single_level(self, tmp_path):
        """Solo campaign: list with 1 element matching hero level."""
        db_path, conn = _make_db(tmp_path, "_solo")
        conn.execute("INSERT INTO campaigns (id, title, owner_user_id) VALUES (1,'c',1)")
        _add_hero(conn, campaign_id=1, level=5)
        conn.close()

        import app.services.encounter_service as es
        importlib.reload(es)
        test_conn = sqlite3.connect(db_path)
        test_conn.row_factory = sqlite3.Row
        levels = es._party_levels_for_campaign(test_conn, 1)
        test_conn.close()
        assert levels == [5], f"Expected [5], got {levels}"

    def test_mp_returns_all_active_levels(self, tmp_path):
        """MP campaign with 3 heroes: all 3 levels returned."""
        db_path, conn = _make_db(tmp_path, "_mp")
        conn.execute("INSERT INTO campaigns (id, title, owner_user_id) VALUES (1,'c',1)")
        _add_hero(conn, 1, level=2)
        _add_hero(conn, 1, level=4)
        _add_hero(conn, 1, level=7)
        conn.close()

        import app.services.encounter_service as es
        importlib.reload(es)
        test_conn = sqlite3.connect(db_path)
        test_conn.row_factory = sqlite3.Row
        levels = es._party_levels_for_campaign(test_conn, 1)
        test_conn.close()
        assert sorted(levels) == [2, 4, 7], f"Expected [2,4,7], got {sorted(levels)}"

    def test_inactive_heroes_excluded(self, tmp_path):
        """Inactive heroes (is_active=0) are excluded from party levels."""
        db_path, conn = _make_db(tmp_path, "_inactive")
        conn.execute("INSERT INTO campaigns (id, title, owner_user_id) VALUES (1,'c',1)")
        _add_hero(conn, 1, level=5)
        _add_hero(conn, 1, level=10, is_active=0)
        conn.close()

        import app.services.encounter_service as es
        importlib.reload(es)
        test_conn = sqlite3.connect(db_path)
        test_conn.row_factory = sqlite3.Row
        levels = es._party_levels_for_campaign(test_conn, 1)
        test_conn.close()
        assert levels == [5], f"Expected [5] (inactive excluded), got {levels}"

    def test_empty_campaign_defaults_to_1(self, tmp_path):
        """No heroes → default [1]."""
        db_path, conn = _make_db(tmp_path, "_empty")
        conn.execute("INSERT INTO campaigns (id, title, owner_user_id) VALUES (1,'c',1)")
        conn.close()

        import app.services.encounter_service as es
        importlib.reload(es)
        test_conn = sqlite3.connect(db_path)
        test_conn.row_factory = sqlite3.Row
        levels = es._party_levels_for_campaign(test_conn, 1)
        test_conn.close()
        assert levels == [1], f"Expected [1], got {levels}"


# ── FAZA 1 RED: _party_scaling_level ─────────────────────────────────────────

class TestPartyScalingLevel:
    def test_solo_returns_hero_level(self):
        """Solo (1 hero): scaling level = hero's own level (no regression)."""
        import app.services.encounter_service as es
        importlib.reload(es)
        assert es._party_scaling_level([5]) == 5

    def test_mp_two_equal_levels_max_minus_1(self):
        """2 heroes same level: scaling = max - 1."""
        import app.services.encounter_service as es
        importlib.reload(es)
        assert es._party_scaling_level([5, 5]) == 4

    def test_mp_spread_levels_max_minus_1(self):
        """3 heroes at levels 2, 4, 7: scaling = 7-1 = 6."""
        import app.services.encounter_service as es
        importlib.reload(es)
        assert es._party_scaling_level([2, 4, 7]) == 6

    def test_mp_never_below_1(self):
        """All heroes at level 1: scaling never drops below 1."""
        import app.services.encounter_service as es
        importlib.reload(es)
        assert es._party_scaling_level([1, 1, 1]) >= 1

    def test_four_player_party(self):
        """4 heroes: max-1 rule applies across all 4."""
        import app.services.encounter_service as es
        importlib.reload(es)
        assert es._party_scaling_level([3, 5, 6, 8]) == 7  # max=8, 8-1=7

    def test_empty_defaults_to_1(self):
        """Empty list → 1 (defensive)."""
        import app.services.encounter_service as es
        importlib.reload(es)
        assert es._party_scaling_level([]) == 1


# ── FAZA 1 RED: _hero_level_for_campaign backward compat ─────────────────────

class TestHeroLevelBackwardCompat:
    def test_solo_same_as_before(self, tmp_path):
        """Backward compat: solo campaign returns hero's level unchanged."""
        db_path, conn = _make_db(tmp_path, "_compat")
        conn.execute("INSERT INTO campaigns (id, title, owner_user_id) VALUES (1,'c',1)")
        _add_hero(conn, 1, level=3)
        conn.close()

        import app.services.encounter_service as es
        importlib.reload(es)
        test_conn = sqlite3.connect(db_path)
        test_conn.row_factory = sqlite3.Row
        level = es._hero_level_for_campaign(test_conn, 1)
        test_conn.close()
        assert level == 3, f"Backward compat broken: expected 3, got {level}"

    def test_mp_uses_max_minus_1(self, tmp_path):
        """MP campaign: _hero_level_for_campaign returns max(levels)-1."""
        db_path, conn = _make_db(tmp_path, "_compat_mp")
        conn.execute("INSERT INTO campaigns (id, title, owner_user_id) VALUES (1,'c',1)")
        _add_hero(conn, 1, level=2)
        _add_hero(conn, 1, level=7)
        conn.close()

        import app.services.encounter_service as es
        importlib.reload(es)
        test_conn = sqlite3.connect(db_path)
        test_conn.row_factory = sqlite3.Row
        level = es._hero_level_for_campaign(test_conn, 1)
        test_conn.close()
        assert level == 6, f"MP max-1 rule: expected 6, got {level}"


# ── FAZA 1 RED: catch-up XP in xp_service ────────────────────────────────────

class TestCatchupXp:
    def _setup_db(self, tmp_path, suffix=""):
        db_path, conn = _make_db(tmp_path, suffix)
        conn.execute("INSERT INTO campaigns (id, title, owner_user_id) VALUES (1,'c',1)")
        return db_path, conn

    def test_catchup_multiplier_applied_for_lagging_player(self, tmp_path):
        """Player at level 2 in party with max 7: gets ×1.5 XP (rounded)."""
        db_path, conn = self._setup_db(tmp_path, "_catchup_lag")
        # Party: hero 1 level 2 (lagging), hero 2 level 7 (max)
        h1 = _add_hero(conn, 1, level=2)
        _add_hero(conn, 1, level=7)
        conn.close()

        import app.services.xp_service as xs
        importlib.reload(xs)
        import app.services.config_service as _cs
        importlib.reload(_cs)
        import app.services.dice as _dice
        importlib.reload(_dice)

        test_conn = sqlite3.connect(db_path)
        test_conn.row_factory = sqlite3.Row

        # catchup threshold = max-1 = 6; char level 2 < 6 → ×1.5
        # grant 100 XP → expect 150
        result = xs.grant_pending_xp(
            test_conn, h1, campaign_id=1, amount=100,
            reason="test", source="combat",
        )
        test_conn.close()
        assert result["granted"] == 150, (
            f"Catch-up ×1.5 expected 150, got {result['granted']}. "
            "Player at level 2 is below party max-1 (6) and should get bonus XP."
        )

    def test_no_catchup_for_player_at_threshold(self, tmp_path):
        """Player at level 6 (= max-1 = catch-up threshold): no bonus."""
        db_path, conn = self._setup_db(tmp_path, "_catchup_at")
        h1 = _add_hero(conn, 1, level=6)
        _add_hero(conn, 1, level=7)
        conn.close()

        import app.services.xp_service as xs
        importlib.reload(xs)

        test_conn = sqlite3.connect(db_path)
        test_conn.row_factory = sqlite3.Row
        result = xs.grant_pending_xp(
            test_conn, h1, campaign_id=1, amount=100,
            reason="test", source="combat",
        )
        test_conn.close()
        assert result["granted"] == 100, (
            f"No bonus expected at threshold level, got {result['granted']}"
        )

    def test_no_catchup_for_leader(self, tmp_path):
        """Highest-level player: no bonus."""
        db_path, conn = self._setup_db(tmp_path, "_catchup_leader")
        h1 = _add_hero(conn, 1, level=7)
        _add_hero(conn, 1, level=2)
        conn.close()

        import app.services.xp_service as xs
        importlib.reload(xs)

        test_conn = sqlite3.connect(db_path)
        test_conn.row_factory = sqlite3.Row
        result = xs.grant_pending_xp(
            test_conn, h1, campaign_id=1, amount=100,
            reason="test", source="combat",
        )
        test_conn.close()
        assert result["granted"] == 100, (
            f"Leader should not get catch-up bonus, got {result['granted']}"
        )

    def test_no_catchup_for_solo(self, tmp_path):
        """Solo campaign (1 hero): no catch-up bonus (no party to catch up to)."""
        db_path, conn = self._setup_db(tmp_path, "_catchup_solo")
        h1 = _add_hero(conn, 1, level=2)
        conn.close()

        import app.services.xp_service as xs
        importlib.reload(xs)

        test_conn = sqlite3.connect(db_path)
        test_conn.row_factory = sqlite3.Row
        result = xs.grant_pending_xp(
            test_conn, h1, campaign_id=1, amount=100,
            reason="test", source="combat",
        )
        test_conn.close()
        assert result["granted"] == 100, (
            f"Solo player should not get catch-up bonus, got {result['granted']}"
        )

    def test_xp_accumulated_correctly(self, tmp_path):
        """Catch-up XP accumulates in sheet_json.pending_xp and xp_lifetime_earned."""
        db_path, conn = self._setup_db(tmp_path, "_catchup_acc")
        h1 = _add_hero(conn, 1, level=2)
        _add_hero(conn, 1, level=7)
        conn.close()

        import app.services.xp_service as xs
        importlib.reload(xs)

        test_conn = sqlite3.connect(db_path)
        test_conn.row_factory = sqlite3.Row
        result = xs.grant_pending_xp(
            test_conn, h1, campaign_id=1, amount=100,
            reason="test", source="combat",
        )
        # Verify sheet updated
        row = test_conn.execute(
            "SELECT sheet_json FROM characters WHERE id=?", (h1,)
        ).fetchone()
        test_conn.close()
        sheet = json.loads(row["sheet_json"])
        assert sheet["pending_xp"] == 150, f"pending_xp={sheet['pending_xp']}"
        assert sheet["xp_lifetime_earned"] == 150, f"xp_lifetime={sheet['xp_lifetime_earned']}"
