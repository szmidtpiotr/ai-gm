"""Wspólne źródło schematu tabel game_config_* dla testów (#928 / 918-A1).

Jedno miejsce zamiast ~40 inline ``_schema_sql()`` rozjeżdżających się z realnym
schematem. Guard (test_issue928_schema_helper.py) porównuje to z PRAGMA realnej DB,
więc gdy migracja doda kolumnę a tu jej zabraknie — test FAILUJE, zamiast cicho
wywalać testy walki w setupie (root cause #818/#870).

Trzymaj te CREATE 1:1 z realnym schematem (kolumny; typy luźne — sqlite). Tabele
dokładać wg potrzeb migracji plików testowych (918-A2).
"""
from __future__ import annotations


def enemies_table_sql() -> str:
    """CREATE dla game_config_enemies — pełny, aktualny zestaw kolumn.

    Idempotentne (IF NOT EXISTS) — bezpieczne do wielokrotnego wywołania w setUp.
    """
    return """
    CREATE TABLE IF NOT EXISTS game_config_enemies (
      key TEXT PRIMARY KEY,
      label TEXT NOT NULL,
      hp_base INTEGER NOT NULL,
      ac_base INTEGER NOT NULL,
      attack_bonus INTEGER NOT NULL,
      dex_modifier INTEGER NOT NULL DEFAULT 0,
      damage_die TEXT NOT NULL,
      skills_json TEXT,
      description TEXT,
      is_active INTEGER NOT NULL DEFAULT 1,
      locked_at TEXT,
      created_at TEXT NOT NULL DEFAULT (datetime('now')),
      updated_at TEXT NOT NULL DEFAULT (datetime('now')),
      tier TEXT DEFAULT 'standard',
      attacks_per_turn INTEGER NOT NULL DEFAULT 1,
      damage_bonus INTEGER NOT NULL DEFAULT 0,
      damage_type TEXT,
      xp_award INTEGER NOT NULL DEFAULT 0,
      conditions_immune TEXT,
      loot_table_key TEXT,
      note TEXT,
      review_status TEXT,
      behavior_profile_key TEXT,
      hit_location_table TEXT,
      fear_aura INTEGER NOT NULL DEFAULT 0,
      fear_dc INTEGER,
      loot_tier TEXT,
      drop_chance REAL NOT NULL DEFAULT 1.0,
      stats_json TEXT,
      image_url TEXT,
      image_url_raw TEXT,
      image_gen_prompt TEXT
    );
    """


# Rejestr tabel — łatwo rozszerzać w 918-A2 (weapons, items, consumables, spells…).
_TABLE_SQL = {
    "game_config_enemies": enemies_table_sql,
}


def table_sql(name: str) -> str:
    """Zwraca CREATE dla nazwanej tabeli game_config_*."""
    try:
        return _TABLE_SQL[name]()
    except KeyError:
        raise KeyError(f"brak helpera schematu dla tabeli '{name}' (#928 _fixtures_schema)") from None


def create_tables(conn, *names: str) -> None:
    """Tworzy wskazane tabele game_config_* w połączeniu sqlite (helper dla setUp)."""
    for name in names:
        conn.executescript(table_sql(name))
