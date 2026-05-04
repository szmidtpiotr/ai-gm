"""T12 — game_config_xp_rewards ([S10e]); resolver XP przy pokonaniu wroga."""

import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services import xp_service as xp_mod


def _mk_conn(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE game_config_xp_rewards (
            key TEXT PRIMARY KEY,
            category TEXT NOT NULL,
            label TEXT NOT NULL,
            description TEXT,
            xp_amount INTEGER NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1,
            sort_order INTEGER NOT NULL DEFAULT 0,
            locked_at TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        INSERT INTO game_config_xp_rewards (key, category, label, xp_amount, sort_order)
        VALUES
            ('enemy_tier_weak', 'enemy_tier', 'weak', 11, 1),
            ('enemy_tier_standard', 'enemy_tier', 'std', 22, 2),
            ('mg_grant_small', 'mg_grant', 'small', 5, 3);
        """
    )
    conn.commit()
    return conn


def test_resolve_prefers_explicit_xp_award(tmp_path):
    conn = _mk_conn(tmp_path / "a.db")
    try:
        amt, src = xp_mod.resolve_enemy_defeat_xp_amount(
            conn, catalog_xp_award=99, tier="weak"
        )
        assert amt == 99 and src == "enemy_xp_award"
    finally:
        conn.close()


def test_resolve_falls_back_to_tier_row(tmp_path):
    conn = _mk_conn(tmp_path / "b.db")
    try:
        amt, src = xp_mod.resolve_enemy_defeat_xp_amount(
            conn, catalog_xp_award=0, tier="weak"
        )
        assert amt == 11 and src == "xp_reward_table"
        amt2, src2 = xp_mod.resolve_enemy_defeat_xp_amount(
            conn, catalog_xp_award=0, tier="standard"
        )
        assert amt2 == 22 and src2 == "xp_reward_table"
    finally:
        conn.close()


def test_require_xp_reward_amount(tmp_path):
    conn = _mk_conn(tmp_path / "c.db")
    try:
        assert xp_mod.require_xp_reward_amount(conn, "mg_grant_small") == 5
        with pytest.raises(ValueError, match="unknown_or_inactive"):
            xp_mod.require_xp_reward_amount(conn, "missing_key")
    finally:
        conn.close()


def test_list_categories(tmp_path):
    conn = _mk_conn(tmp_path / "d.db")
    try:
        rows = xp_mod.list_xp_rewards_for_categories(conn, ["mg_grant"])
        assert len(rows) == 1
        assert rows[0]["key"] == "mg_grant_small"
    finally:
        conn.close()
