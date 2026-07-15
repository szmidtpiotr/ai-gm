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
    """CREATE dla game_config_enemies — pełny, aktualny zestaw kolumn."""
    return """
    CREATE TABLE IF NOT EXISTS game_config_enemies (
      key TEXT PRIMARY KEY,
      label TEXT NOT NULL DEFAULT '',
      hp_base INTEGER NOT NULL DEFAULT 10,
      ac_base INTEGER NOT NULL DEFAULT 10,
      attack_bonus INTEGER NOT NULL DEFAULT 0,
      dex_modifier INTEGER NOT NULL DEFAULT 0,
      damage_die TEXT NOT NULL DEFAULT '1d6',
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
      image_gen_prompt TEXT,
      min_level INTEGER DEFAULT 1,
      created_by TEXT,
      template_id TEXT,
      lore_text TEXT,
      terrain_tags TEXT,
      max_level INTEGER,
      world_scope TEXT
    );
    """


def weapons_table_sql() -> str:
    """CREATE dla game_config_weapons — pełny, aktualny zestaw kolumn."""
    return """
    CREATE TABLE IF NOT EXISTS game_config_weapons (
      key TEXT PRIMARY KEY,
      label TEXT NOT NULL DEFAULT '',
      damage_die TEXT NOT NULL DEFAULT '1d6',
      weapon_type TEXT DEFAULT 'melee',
      linked_stat TEXT NOT NULL DEFAULT 'STR',
      allowed_classes TEXT,
      two_handed INTEGER DEFAULT 0,
      finesse INTEGER DEFAULT 0,
      light INTEGER DEFAULT NULL,
      range_m INTEGER,
      targeting TEXT DEFAULT 'single',
      aoe_radius_m REAL,
      magic_school TEXT,
      weight_kg REAL DEFAULT 0.0,
      description TEXT DEFAULT '',
      note TEXT,
      value_gp INTEGER DEFAULT 0,
      is_active INTEGER DEFAULT 1,
      locked_at TEXT,
      created_at TEXT DEFAULT (datetime('now')),
      updated_at TEXT DEFAULT (datetime('now')),
      ai_generated INTEGER DEFAULT 0,
      approved INTEGER DEFAULT 1,
      weapon_slot TEXT DEFAULT 'main_hand',
      rarity INTEGER DEFAULT 1,
      effect_json TEXT,
      source_exclusive TEXT,
      campaign_id INTEGER,
      review_status TEXT DEFAULT 'permanent',
      min_level INTEGER DEFAULT 1,
      location_tags TEXT,
      price_gp INTEGER,
      durability_base INTEGER,
      ammo_key TEXT
    );
    """


def items_table_sql() -> str:
    """CREATE dla game_config_items — pełny, aktualny zestaw kolumn."""
    return """
    CREATE TABLE IF NOT EXISTS game_config_items (
      key TEXT PRIMARY KEY,
      label TEXT NOT NULL DEFAULT '',
      item_type TEXT DEFAULT 'misc',
      description TEXT DEFAULT '',
      value_gp INTEGER DEFAULT 0,
      effect_json TEXT,
      is_active INTEGER DEFAULT 1,
      locked_at TEXT,
      created_at TEXT DEFAULT (datetime('now')),
      updated_at TEXT DEFAULT (datetime('now')),
      note TEXT,
      weight_kg REAL DEFAULT 0.0,
      ac_bonus INTEGER DEFAULT 0,
      charges INTEGER DEFAULT 1,
      ai_generated INTEGER DEFAULT 0,
      approved INTEGER DEFAULT 1,
      allowed_classes TEXT DEFAULT '[]',
      armor_coverage TEXT DEFAULT 'torso',
      rarity INTEGER DEFAULT 1,
      effect_type TEXT,
      effect_dice TEXT,
      effect_bonus INTEGER DEFAULT 0,
      effect_target TEXT DEFAULT 'self',
      source_exclusive TEXT,
      campaign_id INTEGER,
      review_status TEXT DEFAULT 'permanent',
      min_level INTEGER DEFAULT 1,
      location_tags TEXT,
      price_gp INTEGER,
      pending_category TEXT
    );
    """


def consumables_table_sql() -> str:
    """CREATE dla game_config_consumables — pełny, aktualny zestaw kolumn."""
    return """
    CREATE TABLE IF NOT EXISTS game_config_consumables (
      key TEXT PRIMARY KEY,
      label TEXT NOT NULL DEFAULT '',
      description TEXT DEFAULT '',
      effect_type TEXT DEFAULT 'misc',
      effect_dice TEXT,
      effect_bonus INTEGER DEFAULT 0,
      effect_target TEXT DEFAULT 'self',
      weight_kg REAL DEFAULT 0.0,
      charges INTEGER DEFAULT 1,
      base_price INTEGER DEFAULT 0,
      note TEXT,
      is_active INTEGER DEFAULT 1,
      locked_at TEXT,
      created_at TEXT DEFAULT (datetime('now')),
      updated_at TEXT DEFAULT (datetime('now')),
      rarity INTEGER DEFAULT 1,
      ai_generated INTEGER DEFAULT 0,
      approved INTEGER DEFAULT 1,
      min_level INTEGER DEFAULT 1,
      location_tags TEXT,
      price_gp INTEGER,
      effect_json TEXT
    );
    """


def spells_table_sql() -> str:
    """CREATE dla game_config_spells — pełny, aktualny zestaw kolumn."""
    return """
    CREATE TABLE IF NOT EXISTS game_config_spells (
      key TEXT PRIMARY KEY,
      label TEXT NOT NULL DEFAULT '',
      tier INTEGER DEFAULT 1,
      mana_cost INTEGER DEFAULT 2,
      spell_type TEXT DEFAULT 'attack',
      damage_die TEXT,
      heal_die TEXT,
      effect_stat TEXT,
      effect_type TEXT,
      effect_duration INTEGER DEFAULT 1,
      target_zone TEXT DEFAULT 'any',
      aoe INTEGER DEFAULT 0,
      description TEXT,
      rank2_json TEXT,
      rank3_json TEXT,
      is_active INTEGER DEFAULT 1,
      effect_json TEXT
    );
    """


def conditions_table_sql() -> str:
    """CREATE dla game_config_conditions — pełny, aktualny zestaw kolumn."""
    return """
    CREATE TABLE IF NOT EXISTS game_config_conditions (
      key TEXT PRIMARY KEY,
      label TEXT NOT NULL DEFAULT '',
      effect_json TEXT,
      description TEXT,
      is_active INTEGER DEFAULT 1,
      locked_at TEXT,
      created_at TEXT DEFAULT (datetime('now')),
      updated_at TEXT DEFAULT (datetime('now')),
      stackable INTEGER DEFAULT 0,
      auto_remove TEXT
    );
    """


def skills_table_sql() -> str:
    """CREATE dla game_config_skills — pełny, aktualny zestaw kolumn."""
    return """
    CREATE TABLE IF NOT EXISTS game_config_skills (
      key TEXT PRIMARY KEY,
      label TEXT NOT NULL DEFAULT '',
      linked_stat TEXT,
      rank_ceiling INTEGER DEFAULT 5,
      sort_order INTEGER DEFAULT 0,
      locked_at TEXT,
      description TEXT,
      trigger_keywords TEXT
    );
    """


def affixes_table_sql() -> str:
    """CREATE dla game_config_affixes — pełny, aktualny zestaw kolumn."""
    return """
    CREATE TABLE IF NOT EXISTS game_config_affixes (
      key TEXT PRIMARY KEY,
      name TEXT NOT NULL,
      tier INTEGER DEFAULT 1,
      allowed_item_types TEXT DEFAULT 'weapon',
      effect_json TEXT,
      is_active INTEGER DEFAULT 1,
      created_at TEXT DEFAULT (datetime('now')),
      updated_at TEXT DEFAULT (datetime('now'))
    );
    """


def meta_table_sql() -> str:
    """CREATE dla game_config_meta — tabela runtime-metadata silnika."""
    return """
    CREATE TABLE IF NOT EXISTS game_config_meta (
      key TEXT PRIMARY KEY,
      value TEXT NOT NULL,
      updated_at TEXT DEFAULT (datetime('now'))
    );
    """



def hidden_traits_table_sql() -> str:
    """CREATE dla game_config_hidden_traits (#918-A2 character batch)."""
    return """
    CREATE TABLE IF NOT EXISTS game_config_hidden_traits (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      key TEXT UNIQUE NOT NULL,
      label TEXT NOT NULL DEFAULT '',
      description TEXT,
      trigger_keywords TEXT,
      effect_json TEXT DEFAULT '{}',
      is_active INTEGER DEFAULT 1,
      created_at TEXT DEFAULT (datetime('now'))
    );
    """


def archetypes_table_sql() -> str:
    """CREATE dla game_config_archetypes (#918-A2 character batch)."""
    return """
    CREATE TABLE IF NOT EXISTS game_config_archetypes (
      key TEXT PRIMARY KEY,
      label TEXT NOT NULL DEFAULT '',
      description TEXT,
      starter_items_json TEXT NOT NULL DEFAULT '[]',
      starter_gold_gp INTEGER NOT NULL DEFAULT 0,
      is_active INTEGER NOT NULL DEFAULT 1,
      locked_at TEXT,
      created_at TEXT NOT NULL DEFAULT (datetime('now')),
      updated_at TEXT NOT NULL DEFAULT (datetime('now')),
      hp_base INTEGER NOT NULL DEFAULT 10,
      starting_stats_json TEXT
    );
    """


def stats_table_sql() -> str:
    """CREATE dla game_config_stats (#918-A2 character batch)."""
    return """
    CREATE TABLE IF NOT EXISTS game_config_stats (
      key TEXT PRIMARY KEY,
      label TEXT NOT NULL DEFAULT '',
      description TEXT NOT NULL DEFAULT '',
      sort_order INTEGER NOT NULL DEFAULT 0,
      locked_at TEXT
    );
    """


def loot_tables_table_sql() -> str:
    """CREATE dla game_config_loot_tables (#918-A2 character batch)."""
    return """
    CREATE TABLE IF NOT EXISTS game_config_loot_tables (
      key TEXT PRIMARY KEY,
      label TEXT NOT NULL DEFAULT '',
      description TEXT NOT NULL DEFAULT '',
      is_active INTEGER NOT NULL DEFAULT 1,
      locked_at TEXT,
      created_at TEXT NOT NULL DEFAULT (datetime('now')),
      updated_at TEXT NOT NULL DEFAULT (datetime('now')),
      gold_min INTEGER NOT NULL DEFAULT 0,
      gold_max INTEGER NOT NULL DEFAULT 0
    );
    """


def loot_entries_table_sql() -> str:
    """CREATE dla game_config_loot_entries (#918-A2 character batch)."""
    return """
    CREATE TABLE IF NOT EXISTS game_config_loot_entries (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      loot_table_key TEXT NOT NULL,
      item_key TEXT,
      consumable_key TEXT,
      weapon_key TEXT,
      weight INTEGER NOT NULL DEFAULT 10,
      qty_min INTEGER NOT NULL DEFAULT 1,
      qty_max INTEGER NOT NULL DEFAULT 1,
      game_item_key TEXT
    );
    """


def skill_risk_categories_table_sql() -> str:
    """CREATE dla game_config_skill_risk_categories (#918-A2 character batch)."""
    return """
    CREATE TABLE IF NOT EXISTS game_config_skill_risk_categories (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      category_key TEXT NOT NULL UNIQUE,
      skill_key TEXT NOT NULL DEFAULT '',
      default_dc INTEGER NOT NULL DEFAULT 12,
      keywords TEXT NOT NULL DEFAULT '',
      enabled INTEGER NOT NULL DEFAULT 1
    );
    """


def riddles_table_sql() -> str:
    """CREATE dla game_config_riddles."""
    return """
    CREATE TABLE IF NOT EXISTS game_config_riddles (
      key TEXT PRIMARY KEY,
      text TEXT NOT NULL,
      answer TEXT NOT NULL,
      answer_alts TEXT NOT NULL DEFAULT '[]',
      hints TEXT NOT NULL DEFAULT '[]',
      difficulty INTEGER NOT NULL DEFAULT 1,
      theme TEXT NOT NULL DEFAULT 'general',
      is_active INTEGER NOT NULL DEFAULT 1,
      created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );
    """


def services_table_sql() -> str:
    """CREATE dla game_config_services."""
    return """
    CREATE TABLE IF NOT EXISTS game_config_services (
      key TEXT PRIMARY KEY,
      label TEXT NOT NULL,
      cost_gp INTEGER NOT NULL DEFAULT 0,
      description TEXT NOT NULL DEFAULT '',
      is_active INTEGER NOT NULL DEFAULT 1,
      created_at TEXT NOT NULL DEFAULT (datetime('now')),
      updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    );
    """


def xp_rewards_table_sql() -> str:
    """CREATE dla game_config_xp_rewards."""
    return """
    CREATE TABLE IF NOT EXISTS game_config_xp_rewards (
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
    """


def dc_table_sql() -> str:
    """CREATE dla game_config_dc."""
    return """
    CREATE TABLE IF NOT EXISTS game_config_dc (
      key TEXT PRIMARY KEY,
      label TEXT NOT NULL,
      value INTEGER NOT NULL,
      sort_order INTEGER NOT NULL DEFAULT 0,
      locked_at TEXT,
      description TEXT
    );
    """


def xp_awards_table_sql() -> str:
    """CREATE dla game_config_xp_awards."""
    return """
    CREATE TABLE IF NOT EXISTS game_config_xp_awards (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      category TEXT NOT NULL,
      source_key TEXT UNIQUE NOT NULL,
      label TEXT NOT NULL,
      description TEXT,
      xp_amount INTEGER NOT NULL DEFAULT 0,
      is_active INTEGER NOT NULL DEFAULT 1,
      is_locked INTEGER NOT NULL DEFAULT 0,
      locked_at TEXT DEFAULT NULL,
      created_at TEXT NOT NULL DEFAULT (datetime('now')),
      updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    );
    """


def recipes_table_sql() -> str:
    """CREATE dla game_config_recipes."""
    return """
    CREATE TABLE IF NOT EXISTS game_config_recipes (
      key TEXT PRIMARY KEY,
      label TEXT NOT NULL,
      inputs_json TEXT NOT NULL DEFAULT '[]',
      output_type TEXT NOT NULL DEFAULT 'consumable',
      output_key TEXT,
      output_qty INTEGER NOT NULL DEFAULT 1,
      service_cost_gold INTEGER NOT NULL DEFAULT 0,
      crafter_type TEXT NOT NULL DEFAULT 'smith',
      requires_upgrade TEXT,
      is_hidden INTEGER NOT NULL DEFAULT 0,
      is_active INTEGER NOT NULL DEFAULT 1,
      created_by TEXT,
      created_at TEXT NOT NULL DEFAULT (datetime('now')),
      updated_at TEXT NOT NULL DEFAULT (datetime('now')),
      craft_tier TEXT NOT NULL DEFAULT 'medium'
    );
    """


def factions_table_sql() -> str:
    """CREATE dla game_config_factions."""
    return """
    CREATE TABLE IF NOT EXISTS game_config_factions (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      key TEXT NOT NULL UNIQUE,
      name TEXT NOT NULL,
      faction_type TEXT NOT NULL DEFAULT 'guild',
      description TEXT,
      is_active INTEGER NOT NULL DEFAULT 1,
      created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );
    """


# Rejestr tabel — rozszerzony w 918-A2 o weapons, items, consumables, spells, conditions, skills, affixes, meta.
_TABLE_SQL = {
    "game_config_enemies": enemies_table_sql,
    "game_config_weapons": weapons_table_sql,
    "game_config_items": items_table_sql,
    "game_config_consumables": consumables_table_sql,
    "game_config_spells": spells_table_sql,
    "game_config_conditions": conditions_table_sql,
    "game_config_skills": skills_table_sql,
    "game_config_affixes": affixes_table_sql,
    "game_config_meta": meta_table_sql,
    "game_config_hidden_traits": hidden_traits_table_sql,
    "game_config_archetypes": archetypes_table_sql,
    "game_config_stats": stats_table_sql,
    "game_config_loot_tables": loot_tables_table_sql,
    "game_config_loot_entries": loot_entries_table_sql,
    "game_config_skill_risk_categories": skill_risk_categories_table_sql,
    "game_config_riddles": riddles_table_sql,
    "game_config_services": services_table_sql,
    "game_config_xp_rewards": xp_rewards_table_sql,
    "game_config_dc": dc_table_sql,
    "game_config_xp_awards": xp_awards_table_sql,
    "game_config_recipes": recipes_table_sql,
    "game_config_factions": factions_table_sql,
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
