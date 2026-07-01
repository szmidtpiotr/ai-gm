"""TDD: Issue #1075 — Loot balance: boosted weights + filled empty tables + krypta_opiekun fix."""

import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import _fixtures_schema as fx

MIGRATION_FILE = Path(__file__).resolve().parent.parent / "app" / "db" / "migrations" / "017_loot_table_balance.sql"


def _build_db(path: Path) -> sqlite3.Connection:
    """Create test DB with PRE-MIGRATION state (old weights, empty tables, NULL loot key)."""
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    fx.create_tables(conn, "game_config_loot_tables", "game_config_loot_entries", "game_config_enemies")

    conn.executescript("""
    -- Shared tier tables
    INSERT INTO game_config_loot_tables (key, label, is_active, gold_min, gold_max)
    VALUES
      ('loot_poor',     'Poor',     1, 1, 5),
      ('loot_standard', 'Standard', 1, 3, 10),
      ('loot_rich',     'Rich',     1, 5, 20),
      ('loot_treasure', 'Treasure', 1, 10, 50),
      ('loot_goblin',   'Goblin',   1, 1, 4),
      ('loot_goblin_u31', 'Goblin U31', 1, 0, 0);

    -- PRE-MIGRATION: old/low weights
    INSERT INTO game_config_loot_entries (loot_table_key, item_key, weapon_key, consumable_key, weight, qty_min, qty_max)
    VALUES
      ('loot_poor',     'healing_herb', NULL, NULL, 50, 1, 2),
      ('loot_poor',     'bandage',      NULL, NULL, 40, 1, 1),
      ('loot_poor',     'torch',        NULL, NULL, 55, 1, 2),
      ('loot_poor',     'leather_cap',  NULL, NULL, 10, 1, 1),
      ('loot_poor',      NULL, 'dagger', NULL, 8,  1, 1),

      ('loot_goblin',   'healing_herb', NULL, NULL, 40, 1, 2),
      ('loot_goblin',   'torch',        NULL, NULL, 45, 1, 2),
      ('loot_goblin',   NULL, 'dagger', NULL, 20, 1, 1);

    -- PRE-MIGRATION: goblin_u31 is EMPTY (no entries)
    -- PRE-MIGRATION: krypta_opiekun has NULL loot_table_key
    INSERT INTO game_config_enemies (key, label, loot_table_key, drop_chance)
    VALUES
      ('goblin',         'Goblin',         'loot_goblin',  1.0),
      ('goblin_u31',     'Goblin (U31)',    'loot_goblin_u31', 1.0),
      ('krypta_opiekun', 'Krypta Opiekun', NULL,           0.0);
    """)
    conn.commit()
    return conn


def _apply_migration(conn: sqlite3.Connection) -> None:
    sql = MIGRATION_FILE.read_text()
    conn.executescript(sql)


# ─── RED: verify tests fail BEFORE migration ──────────────────────────────────

class TestLootBalancePreMigration:
    """These tests document the broken state BEFORE migration (#1075)."""

    def setup_method(self):
        self._path = Path(__file__).parent / "_test_loot1075_pre.db"
        if self._path.exists():
            self._path.unlink()
        self._conn = _build_db(self._path)

    def teardown_method(self):
        self._conn.close()
        if self._path.exists():
            self._path.unlink()

    def test_pre_goblin_u31_is_empty(self):
        """PRE-migration: goblin_u31 has 0 loot entries — only gold, never items."""
        count = self._conn.execute(
            "SELECT COUNT(*) FROM game_config_loot_entries WHERE loot_table_key='loot_goblin_u31'"
        ).scalar() if hasattr(self._conn.execute("SELECT 1"), 'scalar') else \
            self._conn.execute(
                "SELECT COUNT(*) FROM game_config_loot_entries WHERE loot_table_key='loot_goblin_u31'"
            ).fetchone()[0]
        assert count == 0, "PRE-migration: goblin_u31 must be empty for RED phase to be valid"

    def test_pre_krypta_opiekun_no_loot(self):
        """PRE-migration: krypta_opiekun has no loot table."""
        row = self._conn.execute(
            "SELECT loot_table_key FROM game_config_enemies WHERE key='krypta_opiekun'"
        ).fetchone()
        assert row["loot_table_key"] is None, "PRE-migration: krypta_opiekun must have NULL loot_table_key"

    def test_pre_low_weapon_weight_loot_poor(self):
        """PRE-migration: dagger in loot_poor has old low weight (8)."""
        row = self._conn.execute(
            "SELECT weight FROM game_config_loot_entries WHERE loot_table_key='loot_poor' AND weapon_key='dagger'"
        ).fetchone()
        assert row["weight"] == 8, f"PRE-migration: expected weight=8, got {row['weight']}"


# ─── GREEN: verify correct state AFTER migration ──────────────────────────────

class TestLootBalancePostMigration:
    """After migration: weights boosted, goblin_u31 filled, krypta_opiekun fixed."""

    def setup_method(self):
        self._path = Path(__file__).parent / "_test_loot1075_post.db"
        if self._path.exists():
            self._path.unlink()
        self._conn = _build_db(self._path)
        _apply_migration(self._conn)

    def teardown_method(self):
        self._conn.close()
        if self._path.exists():
            self._path.unlink()

    def _scalar(self, sql: str, *args) -> int | None:
        row = self._conn.execute(sql, args).fetchone()
        return row[0] if row else None

    # ── goblin_u31 filled ────────────────────────────────────────────────────

    def test_goblin_u31_has_three_entries(self):
        """goblin_u31 now has 3 entries: healing_herb, torch, dagger."""
        count = self._scalar(
            "SELECT COUNT(*) FROM game_config_loot_entries WHERE loot_table_key='loot_goblin_u31'"
        )
        assert count == 3, f"Expected 3 entries in loot_goblin_u31, got {count}"

    def test_goblin_u31_has_healing_herb(self):
        row = self._conn.execute(
            "SELECT weight FROM game_config_loot_entries WHERE loot_table_key='loot_goblin_u31' AND item_key='healing_herb'"
        ).fetchone()
        assert row is not None, "healing_herb missing from loot_goblin_u31"
        assert row["weight"] == 55

    def test_goblin_u31_has_torch(self):
        row = self._conn.execute(
            "SELECT weight FROM game_config_loot_entries WHERE loot_table_key='loot_goblin_u31' AND item_key='torch'"
        ).fetchone()
        assert row is not None, "torch missing from loot_goblin_u31"
        assert row["weight"] == 60

    def test_goblin_u31_has_dagger(self):
        row = self._conn.execute(
            "SELECT weight FROM game_config_loot_entries WHERE loot_table_key='loot_goblin_u31' AND weapon_key='dagger'"
        ).fetchone()
        assert row is not None, "dagger missing from loot_goblin_u31"
        assert row["weight"] == 30

    def test_goblin_u31_gold_range_set(self):
        row = self._conn.execute(
            "SELECT gold_min, gold_max FROM game_config_loot_tables WHERE key='loot_goblin_u31'"
        ).fetchone()
        assert row["gold_min"] == 1
        assert row["gold_max"] == 6

    # ── krypta_opiekun loot fix ──────────────────────────────────────────────

    def test_krypta_opiekun_has_loot_table(self):
        row = self._conn.execute(
            "SELECT loot_table_key, drop_chance FROM game_config_enemies WHERE key='krypta_opiekun'"
        ).fetchone()
        assert row["loot_table_key"] == "loot_treasure", \
            f"krypta_opiekun should use loot_treasure, got {row['loot_table_key']}"
        assert row["drop_chance"] == 1.0, \
            f"krypta_opiekun drop_chance should be 1.0, got {row['drop_chance']}"

    # ── boosted weapon weights ───────────────────────────────────────────────

    def test_loot_poor_dagger_weight_boosted(self):
        row = self._conn.execute(
            "SELECT weight FROM game_config_loot_entries WHERE loot_table_key='loot_poor' AND weapon_key='dagger'"
        ).fetchone()
        assert row["weight"] == 18, f"loot_poor dagger: expected 18, got {row['weight']}"

    def test_loot_goblin_dagger_weight_boosted(self):
        row = self._conn.execute(
            "SELECT weight FROM game_config_loot_entries WHERE loot_table_key='loot_goblin' AND weapon_key='dagger'"
        ).fetchone()
        assert row["weight"] == 35, f"loot_goblin dagger: expected 35, got {row['weight']}"

    # ── idempotency: running migration twice doesn't duplicate entries ────────

    def test_migration_is_idempotent_no_duplicate_entries(self):
        """Running migration twice must not create duplicate goblin_u31 entries."""
        _apply_migration(self._conn)
        count = self._scalar(
            "SELECT COUNT(*) FROM game_config_loot_entries WHERE loot_table_key='loot_goblin_u31'"
        )
        assert count == 3, f"After 2nd run: expected 3 entries, got {count} (duplicate!)"

    # ── backward compat: existing goblin table still functional ──────────────

    def test_loot_goblin_healing_herb_still_present(self):
        """loot_goblin base entries not wiped by migration."""
        row = self._conn.execute(
            "SELECT weight FROM game_config_loot_entries WHERE loot_table_key='loot_goblin' AND item_key='healing_herb'"
        ).fetchone()
        assert row is not None, "healing_herb removed from loot_goblin — migration broke existing data"
