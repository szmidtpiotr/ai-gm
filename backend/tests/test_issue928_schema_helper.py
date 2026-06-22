"""TDD: Issue #928 (918-A1) — wspólny, samo-walidujący się helper schematu testowego.

Jedno źródło CREATE dla game_config_* w testach + guard, który pilnuje że helper
pokrywa REALNE kolumny (PRAGMA na DEV DB). Dryf (jak brak `stats_json` z #818/#870)
zostaje wykryty automatycznie, zamiast wywalać testy w setupie po cichu.
"""
import os
import sqlite3
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import _fixtures_schema as fx  # noqa: E402

REAL_DB = "/data/ai_gm.db"

# Kolumny, których realnie używa silnik walki (combat_service._fetch_enemy_row).
_COMBAT_QUERY_COLS = [
    "key", "label", "hp_base", "ac_base", "attack_bonus", "damage_die",
    "dex_modifier", "skills_json", "stats_json", "tier", "loot_table_key",
    "drop_chance", "xp_award", "attacks_per_turn", "image_url",
]


def _cols_from_sql(sql: str, table: str) -> set[str]:
    conn = sqlite3.connect(":memory:")
    try:
        conn.executescript(sql)
        return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
    finally:
        conn.close()


# ─── Guard: helper pokrywa realny schemat ────────────────────────────────────

def test_enemies_helper_covers_real_db_columns():
    """Helper musi zawierać KAŻDĄ kolumnę, którą ma realna tabela game_config_enemies."""
    if not os.path.exists(REAL_DB):
        pytest.skip("brak realnej DB (/data/ai_gm.db) — guard pomijany poza kontenerem")
    conn = sqlite3.connect(REAL_DB)
    try:
        real = {r[1] for r in conn.execute("PRAGMA table_info(game_config_enemies)")}
    finally:
        conn.close()
    assert real, "realna tabela game_config_enemies pusta/nieobecna"
    helper = _cols_from_sql(fx.enemies_table_sql(), "game_config_enemies")
    missing = real - helper
    assert not missing, f"helper schematu zgubił realne kolumny: {sorted(missing)}"


# ─── Helper realnie tworzy tabelę używalną przez silnik walki ────────────────

def test_enemies_helper_supports_combat_fetch_query():
    """CREATE z helpera + INSERT + dokładnie te kolumny co _fetch_enemy_row — bez OperationalError."""
    conn = sqlite3.connect(":memory:")
    try:
        conn.executescript(fx.enemies_table_sql())
        conn.execute(
            "INSERT INTO game_config_enemies (key, label, hp_base, ac_base, attack_bonus, "
            "dex_modifier, damage_die) VALUES ('bandit','Bandit',12,13,3,1,'1d8')"
        )
        cols = ", ".join(_COMBAT_QUERY_COLS)
        row = conn.execute(
            f"SELECT {cols} FROM game_config_enemies WHERE key='bandit'"
        ).fetchone()
        assert row is not None
    finally:
        conn.close()


def test_enemies_helper_sql_is_idempotent():
    """Helper można odpalić dwa razy (IF NOT EXISTS) bez błędu — bezpieczne w setUp."""
    conn = sqlite3.connect(":memory:")
    try:
        conn.executescript(fx.enemies_table_sql())
        conn.executescript(fx.enemies_table_sql())
    finally:
        conn.close()
