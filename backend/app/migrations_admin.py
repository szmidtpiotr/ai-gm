import json
import os
import sqlite3

from app.core.logging import get_logger


DB_PATH = "/data/ai_gm.db"
logger = get_logger(__name__)

ADMIN_MIGRATIONS = [
    """
    CREATE TABLE IF NOT EXISTS user_llm_settings (
        user_id INTEGER PRIMARY KEY,
        mode TEXT NOT NULL DEFAULT 'custom',
        provider TEXT NOT NULL,
        base_url TEXT NOT NULL,
        model TEXT NOT NULL,
        api_key TEXT NOT NULL DEFAULT '',
        api_key_set INTEGER NOT NULL DEFAULT 0,
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS llm_connection_presets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        label TEXT NOT NULL UNIQUE,
        provider TEXT NOT NULL,
        base_url TEXT NOT NULL,
        model TEXT NOT NULL,
        api_key TEXT NOT NULL DEFAULT '',
        api_key_set INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS game_config_stats (
        key TEXT PRIMARY KEY,
        label TEXT NOT NULL,
        description TEXT NOT NULL,
        sort_order INTEGER NOT NULL DEFAULT 0,
        locked_at TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS game_config_skills (
        key TEXT PRIMARY KEY,
        label TEXT NOT NULL,
        linked_stat TEXT NOT NULL,
        rank_ceiling INTEGER NOT NULL DEFAULT 5,
        sort_order INTEGER NOT NULL DEFAULT 0,
        locked_at TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS game_config_dc (
        key TEXT PRIMARY KEY,
        label TEXT NOT NULL,
        value INTEGER NOT NULL,
        sort_order INTEGER NOT NULL DEFAULT 0,
        locked_at TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS game_config_weapons (
        key TEXT PRIMARY KEY,
        label TEXT NOT NULL,
        damage_die TEXT NOT NULL,
        weapon_type TEXT NOT NULL DEFAULT 'melee',
        linked_stat TEXT NOT NULL,
        allowed_classes TEXT NOT NULL,
        two_handed INTEGER NOT NULL DEFAULT 0,
        finesse INTEGER NOT NULL DEFAULT 0,
        range_m INTEGER,
        targeting TEXT NOT NULL DEFAULT 'single',
        aoe_radius_m REAL,
        magic_school TEXT,
        weight_kg REAL NOT NULL DEFAULT 0.0,
        description TEXT NOT NULL DEFAULT '',
        note TEXT,
        value_gp INTEGER NOT NULL DEFAULT 0,
        is_active INTEGER NOT NULL DEFAULT 1,
        locked_at TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
    """
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
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS game_config_conditions (
        key TEXT PRIMARY KEY,
        label TEXT NOT NULL,
        effect_json TEXT NOT NULL,
        description TEXT,
        is_active INTEGER NOT NULL DEFAULT 1,
        locked_at TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS admin_tokens (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        token_hash TEXT NOT NULL UNIQUE,
        label TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS admin_audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        table_name TEXT NOT NULL,
        row_key TEXT,
        operation TEXT NOT NULL,
        old_values TEXT,
        new_values TEXT,
        performed_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS game_config_meta (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_game_config_skills_linked_stat
    ON game_config_skills(linked_stat)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_admin_audit_log_table_time
    ON admin_audit_log(table_name, performed_at)
    """,
    "ALTER TABLE game_config_stats ADD COLUMN locked_at TEXT",
    "ALTER TABLE game_config_skills ADD COLUMN locked_at TEXT",
    "ALTER TABLE game_config_dc ADD COLUMN locked_at TEXT",
    "ALTER TABLE game_config_skills ADD COLUMN description TEXT",
    "ALTER TABLE game_config_dc ADD COLUMN description TEXT",
    "ALTER TABLE users ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1",
    "ALTER TABLE users ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0",
    # Stage 10 A1+A4+A5 — auth security baseline columns. All idempotent.
    "ALTER TABLE users ADD COLUMN failed_login_count INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE users ADD COLUMN lockout_until TEXT",
    "ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'player'",
    # Backfill role from is_admin. Runs every startup but is idempotent (only
    # rewrites rows that don't already match the derived value).
    """
    UPDATE users SET role = 'admin'
    WHERE is_admin = 1 AND role != 'admin'
    """,
    """
    UPDATE users SET role = 'player'
    WHERE is_admin = 0 AND role NOT IN ('player','gm','admin')
    """,
    # Stage 11 R1 — Hero resurrection. Global config lives in game_config_meta
    # (key='resurrection_config'). Per-user only: uses_remaining (lives remaining).
    # The four config columns below are legacy scaffolding kept for back-compat
    # but the service now reads/writes game_config_meta instead.
    "ALTER TABLE users ADD COLUMN resurrection_enabled INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE users ADD COLUMN resurrection_cost_mode TEXT NOT NULL DEFAULT 'admin_free'",
    "ALTER TABLE users ADD COLUMN resurrection_cost_value INTEGER NOT NULL DEFAULT 25",
    "ALTER TABLE users ADD COLUMN resurrection_cost_cap_percent INTEGER NOT NULL DEFAULT 50",
    "ALTER TABLE users ADD COLUMN resurrection_uses_remaining INTEGER",
    # Seed the global default (idempotent via ON CONFLICT)
    """
    INSERT INTO game_config_meta (key, value, updated_at)
    VALUES ('resurrection_config', '{"enabled":false,"mode":"admin_free","value":25,"cap_percent":50,"default_uses":null}', datetime('now'))
    ON CONFLICT(key) DO NOTHING
    """,
    # Stage 11 R1 — mark XP grants that have been clawed back so we never
    # double-revert. NULL = still active.
    "ALTER TABLE character_xp_grants ADD COLUMN reverted_at TEXT",
    # Stage 11 R5 — stamp the level at which each spell was learned so the
    # xp_revert resurrection mode can revoke spells purchased above the new
    # level. Existing rows stay NULL ("unknown when learned") and are kept
    # by the rollback (rollback only revokes rows with learned_at_level > N).
    "ALTER TABLE character_spells ADD COLUMN learned_at_level INTEGER",
    # Stage 11 R1 — character_gold_log journal. Every gold mutation writes a
    # row; resurrection's gold_recent_days mode sums positive deltas in a
    # window. `game_clock_day` is the in-game day (clock-driven), used by the
    # recent-days lookup. `wall_clock_at` is for ops debugging.
    """
    CREATE TABLE IF NOT EXISTS character_gold_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        character_id INTEGER NOT NULL,
        delta INTEGER NOT NULL,
        source TEXT NOT NULL DEFAULT 'unknown',
        meta_json TEXT,
        game_clock_day INTEGER,
        wall_clock_at TEXT NOT NULL DEFAULT (datetime('now')),
        reverted_at TEXT
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_character_gold_log_char_day
    ON character_gold_log(character_id, game_clock_day DESC)
    """,
    """
    CREATE TABLE IF NOT EXISTS game_config_items (
        key          TEXT PRIMARY KEY,
        label        TEXT NOT NULL,
        item_type    TEXT NOT NULL DEFAULT 'misc',
        description  TEXT NOT NULL DEFAULT '',
        value_gp     INTEGER NOT NULL DEFAULT 0,
        weight       REAL NOT NULL DEFAULT 0.0,
        effect_json  TEXT,
        is_active    INTEGER NOT NULL DEFAULT 1,
        locked_at    TEXT,
        created_at   TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at   TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS game_config_loot_tables (
        key          TEXT PRIMARY KEY,
        label        TEXT NOT NULL,
        description  TEXT NOT NULL DEFAULT '',
        is_active    INTEGER NOT NULL DEFAULT 1,
        locked_at    TEXT,
        created_at   TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at   TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS game_config_loot_entries (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        loot_table_key TEXT NOT NULL REFERENCES game_config_loot_tables(key) ON DELETE CASCADE,
        item_key       TEXT NOT NULL REFERENCES game_config_items(key) ON DELETE CASCADE,
        weight         INTEGER NOT NULL DEFAULT 10,
        qty_min        INTEGER NOT NULL DEFAULT 1,
        qty_max        INTEGER NOT NULL DEFAULT 1,
        UNIQUE(loot_table_key, item_key)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_loot_entries_table
    ON game_config_loot_entries(loot_table_key)
    """,
    "ALTER TABLE game_config_loot_tables ADD COLUMN gold_min INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE game_config_loot_tables ADD COLUMN gold_max INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE game_config_weapons ADD COLUMN description TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE game_config_weapons ADD COLUMN weapon_type TEXT NOT NULL DEFAULT 'melee'",
    "ALTER TABLE game_config_weapons ADD COLUMN two_handed INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE game_config_weapons ADD COLUMN finesse INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE game_config_weapons ADD COLUMN range_m INTEGER",
    "ALTER TABLE game_config_weapons ADD COLUMN targeting TEXT NOT NULL DEFAULT 'single'",
    "ALTER TABLE game_config_weapons ADD COLUMN aoe_radius_m REAL",
    "ALTER TABLE game_config_weapons ADD COLUMN magic_school TEXT",
    "ALTER TABLE game_config_weapons ADD COLUMN weight_kg REAL NOT NULL DEFAULT 0.0",
    "ALTER TABLE game_config_weapons ADD COLUMN note TEXT",
    "ALTER TABLE game_config_weapons ADD COLUMN value_gp INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE game_config_enemies ADD COLUMN tier TEXT NOT NULL DEFAULT 'standard'",
    "ALTER TABLE game_config_enemies ADD COLUMN attacks_per_turn INTEGER NOT NULL DEFAULT 1",
    "ALTER TABLE game_config_enemies ADD COLUMN damage_bonus INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE game_config_enemies ADD COLUMN damage_type TEXT NOT NULL DEFAULT 'physical'",
    "ALTER TABLE game_config_enemies ADD COLUMN xp_award INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE game_config_enemies ADD COLUMN dex_modifier INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE game_config_enemies ADD COLUMN conditions_immune TEXT",
    "ALTER TABLE game_config_enemies ADD COLUMN skills_json TEXT",
    "ALTER TABLE game_config_enemies ADD COLUMN loot_table_key TEXT REFERENCES game_config_loot_tables(key) ON DELETE SET NULL",
    "ALTER TABLE game_config_enemies ADD COLUMN note TEXT",
    "ALTER TABLE game_config_items ADD COLUMN proficiency_classes TEXT NOT NULL DEFAULT '[]'",
    "ALTER TABLE game_config_items ADD COLUMN note TEXT",
    "ALTER TABLE game_config_items ADD COLUMN weight_kg REAL NOT NULL DEFAULT 0.0",
    "ALTER TABLE game_config_conditions ADD COLUMN stackable INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE game_config_conditions ADD COLUMN auto_remove TEXT",
    """
    CREATE TABLE IF NOT EXISTS game_config_consumables (
        key            TEXT PRIMARY KEY,
        label          TEXT NOT NULL,
        description    TEXT NOT NULL DEFAULT '',
        effect_type    TEXT NOT NULL DEFAULT 'misc',
        effect_dice    TEXT,
        effect_bonus   INTEGER NOT NULL DEFAULT 0,
        effect_target  TEXT NOT NULL DEFAULT 'self',
        weight_kg      REAL NOT NULL DEFAULT 0.0,
        charges        INTEGER NOT NULL DEFAULT 1,
        base_price     INTEGER NOT NULL DEFAULT 0,
        note           TEXT,
        is_active      INTEGER NOT NULL DEFAULT 1,
        locked_at      TEXT,
        created_at     TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at     TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
    "ALTER TABLE game_config_loot_entries ADD COLUMN consumable_key TEXT REFERENCES game_config_consumables(key) ON DELETE CASCADE",
    """
    CREATE TABLE IF NOT EXISTS combat_turns (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        combat_id    INTEGER NOT NULL,
        campaign_id  INTEGER NOT NULL,
        turn_number  REAL NOT NULL,
        actor        TEXT NOT NULL,
        event_type   TEXT NOT NULL,
        roll_value   INTEGER,
        damage       INTEGER,
        hp_after     INTEGER,
        target_id    TEXT,
        target_name  TEXT,
        hit          INTEGER,
        narrative    TEXT,
        created_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_combat_turns_campaign
        ON combat_turns(campaign_id, turn_number)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_combat_turns_combat
        ON combat_turns(combat_id, turn_number)
    """,
    """
    CREATE TABLE IF NOT EXISTS gameconfig_encounter_templates (
        key           TEXT PRIMARY KEY,
        label         TEXT NOT NULL,
        difficulty    TEXT NOT NULL CHECK(difficulty IN ('trivial','easy','medium','hard','deadly')),
        min_level     INTEGER DEFAULT 1,
        max_level     INTEGER DEFAULT 5,
        location_tags TEXT,
        enemies_json  TEXT NOT NULL,
        threat_total  INTEGER,
        is_active     INTEGER DEFAULT 1,
        note          TEXT,
        created_at    TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at    TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    INSERT OR IGNORE INTO gameconfig_encounter_templates
        (key, label, difficulty, min_level, max_level, location_tags, enemies_json, threat_total)
    VALUES
        ('enc_tavern_brawl', 'Bijatyka w tawernie', 'trivial', 1, 5, 'tavern', '[{"enemy_key":"tavernbrawler","count":2},{"enemy_key":"drunksoldier","count":1}]', 34),
        ('enc_dungeon_rats', 'Szczury w piwnicy', 'trivial', 1, 3, 'dungeon', '[{"enemy_key":"giant_rat","count":4}]', 20),
        ('enc_city_mugger', 'Napad w zaułku', 'easy', 1, 5, 'city', '[{"enemy_key":"mugger","count":2}]', 18),
        ('enc_city_thieves', 'Gang kieszonkowców', 'easy', 1, 4, 'city', '[{"enemy_key":"cutpurse","count":1},{"enemy_key":"pickpocket","count":1}]', 16),
        ('enc_city_guard_corrupt', 'Przekupny strażnik', 'medium', 1, 5, 'city', '[{"enemy_key":"corruptguard","count":1},{"enemy_key":"thug","count":1}]', 37),
        ('enc_road_bandits', 'Zasadzka na trakcie', 'medium', 1, 5, 'road,wilderness', '[{"enemy_key":"bandit","count":3},{"enemy_key":"banditarcher","count":1}]', 42),
        ('enc_dungeon_zombie', 'Nieumarły w lochach', 'medium', 2, 5, 'dungeon', '[{"enemy_key":"zombie","count":2},{"enemy_key":"skeleton","count":1}]', 54),
        ('enc_dungeon_skeletons', 'Obudzone kości', 'medium', 2, 5, 'dungeon', '[{"enemy_key":"skeletonwarrior","count":3}]', 75),
        ('enc_road_lieutenant', 'Banda z dowódcą', 'hard', 2, 5, 'road,wilderness', '[{"enemy_key":"banditlieutenant","count":1},{"enemy_key":"bandit","count":2}]', 60),
        ('enc_city_enforcer', 'Ściągacz długów', 'hard', 3, 5, 'city', '[{"enemy_key":"cityenforcer","count":1},{"enemy_key":"guildenforcer","count":1}]', 100),
        ('enc_boss_cultleader', 'Przywódca Kultu', 'deadly', 4, 5, 'dungeon', '[{"enemy_key":"cultleader","count":1},{"enemy_key":"cultzealot","count":2}]', 376),
        ('enc_boss_crimelord', 'Władca Podziemia', 'deadly', 5, 5, 'city', '[{"enemy_key":"crimelord","count":1},{"enemy_key":"cityenforcer","count":2}]', 450)
    """,
    """
    CREATE TABLE IF NOT EXISTS character_inventory (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        character_id   INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
        item_key       TEXT,
        weapon_key     TEXT,
        consumable_key TEXT,
        quantity       INTEGER NOT NULL DEFAULT 1,
        equipped       INTEGER NOT NULL DEFAULT 0,
        slot           TEXT,
        acquired_at    TEXT    NOT NULL DEFAULT (datetime('now')),
        source         TEXT,
        meta_json      TEXT,
        CONSTRAINT inv_xor CHECK (
            (CASE WHEN item_key       IS NOT NULL THEN 1 ELSE 0 END +
             CASE WHEN weapon_key     IS NOT NULL THEN 1 ELSE 0 END +
             CASE WHEN consumable_key IS NOT NULL THEN 1 ELSE 0 END) = 1
        )
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_inv_character
        ON character_inventory(character_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_inv_equipped
        ON character_inventory(character_id, equipped)
    """,
    "DROP TABLE IF EXISTS inventory_items",
    """
    CREATE TABLE IF NOT EXISTS game_config_archetypes (
        key                  TEXT PRIMARY KEY,
        label                TEXT NOT NULL,
        description          TEXT,
        starter_items_json   TEXT NOT NULL DEFAULT '[]',
        starter_gold_gp      INTEGER NOT NULL DEFAULT 0,
        is_active            INTEGER NOT NULL DEFAULT 1,
        locked_at            TEXT,
        created_at           TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at           TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
    "ALTER TABLE characters ADD COLUMN gold_gp INTEGER NOT NULL DEFAULT 0",
    """
    CREATE TABLE IF NOT EXISTS game_sessions (
        id TEXT PRIMARY KEY,
        campaign_id INTEGER,
        test_run_id TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
    "ALTER TABLE game_sessions ADD COLUMN test_run_id TEXT",
    """
    CREATE TABLE IF NOT EXISTS debug_validation_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        test_run_id TEXT NOT NULL,
        event TEXT NOT NULL,
        is_legal INTEGER NOT NULL DEFAULT 1,
        reason TEXT,
        old_state TEXT,
        new_state TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_debug_validation_log_test_run
    ON debug_validation_log(test_run_id, created_at)
    """,
    # Phase 8D — Location Integrity migrations (8D-1 to 8D-4)
    """
    CREATE TABLE IF NOT EXISTS game_locations (
        id INTEGER PRIMARY KEY,
        key TEXT UNIQUE NOT NULL,
        label TEXT NOT NULL,
        description TEXT,
        parent_id INTEGER REFERENCES game_locations(id),
        location_type TEXT DEFAULT 'macro' CHECK(location_type IN ('macro', 'sub')),
        rules TEXT,
        enemy_keys TEXT DEFAULT '[]',
        npc_keys TEXT DEFAULT '[]',
        is_active INTEGER DEFAULT 1,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_game_locations_parent
    ON game_locations(parent_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_game_locations_key
    ON game_locations(key)
    """,
    """
    CREATE TABLE IF NOT EXISTS npcs (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        key                 TEXT NOT NULL UNIQUE,
        label               TEXT NOT NULL,
        npc_type            TEXT NOT NULL DEFAULT 'neutral'
                              CHECK (npc_type IN ('neutral', 'merchant', 'quest_giver', 'ally')),
        description         TEXT,
        personality_json    TEXT NOT NULL DEFAULT '{}',
        is_shop             INTEGER NOT NULL DEFAULT 0,
        shop_inventory_json TEXT NOT NULL DEFAULT '[]',
        is_active           INTEGER NOT NULL DEFAULT 1,
        created_at          TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at          TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS npc_locations (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        npc_id       INTEGER NOT NULL REFERENCES npcs(id) ON DELETE CASCADE,
        location_key TEXT NOT NULL,
        UNIQUE(npc_id, location_key)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_npc_locations_npc_id
    ON npc_locations(npc_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_npc_locations_location_key
    ON npc_locations(location_key)
    """,
    "ALTER TABLE game_sessions ADD COLUMN current_location_id INTEGER REFERENCES game_locations(id)",
    "ALTER TABLE game_sessions ADD COLUMN session_flags TEXT DEFAULT '{}'",
    """
    CREATE TABLE IF NOT EXISTS location_integrity_log (
        id INTEGER PRIMARY KEY,
        session_id INTEGER NOT NULL REFERENCES game_sessions(id),
        character_id INTEGER,
        attempted_move TEXT NOT NULL,
        current_location_key TEXT,
        reason_blocked TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_location_integrity_log_session
    ON location_integrity_log(session_id, created_at)
    """,
    """
    INSERT OR IGNORE INTO game_config_meta (key, value) VALUES
        ('location_integrity_enabled', '1'),
        ('location_parser_json_enabled', '1'),
        ('location_parser_fallback_enabled', '1')
    """,
    # Phase 8D — Add updated_at to game_config_meta for ON CONFLICT UPDATE
    # Use constant default (epoch) because SQLite ALTER TABLE doesn't support function defaults
    "ALTER TABLE game_config_meta ADD COLUMN updated_at TEXT DEFAULT '1970-01-01T00:00:00Z'",
    # Phase 8D-5 — Location auto-create review state and DEV default flag
    "ALTER TABLE game_locations ADD COLUMN ai_generated INTEGER DEFAULT 0",
    "ALTER TABLE game_locations ADD COLUMN approved INTEGER DEFAULT 1",
    """
    INSERT OR IGNORE INTO game_config_meta (key, value)
    VALUES ('location_auto_create_enabled', '1')
    """,
    # Phase 8F-1 — economy: weapon catalog prices (rows still at 0 GP after seed)
    """
    UPDATE game_config_weapons
    SET value_gp = CASE key
        WHEN 'dagger' THEN 10
        WHEN 'longsword' THEN 30
        WHEN 'battleaxe' THEN 55
        WHEN 'spear' THEN 15
        WHEN 'longbow' THEN 40
        WHEN 'hand_crossbow' THEN 35
        WHEN 'warhammer' THEN 45
        WHEN 'greataxe' THEN 60
        WHEN 'rapier' THEN 25
        WHEN 'mace' THEN 12
        WHEN 'halberd' THEN 55
        WHEN 'heavy_crossbow' THEN 50
        WHEN 'throwing_knife' THEN 5
        WHEN 'tome_of_striking' THEN 80
        WHEN 'staff_of_flames' THEN 75
        WHEN 'orb_of_frost' THEN 90
        WHEN 'wand_of_lightning' THEN 85
        WHEN 'cursed_grimoire' THEN 120
        ELSE COALESCE(value_gp, 0)
    END
    WHERE COALESCE(value_gp, 0) = 0
      AND key IN (
        'dagger', 'longsword', 'battleaxe', 'spear', 'longbow', 'hand_crossbow',
        'warhammer', 'greataxe', 'rapier', 'mace', 'halberd', 'heavy_crossbow',
        'throwing_knife', 'tome_of_striking', 'staff_of_flames', 'orb_of_frost',
        'wand_of_lightning', 'cursed_grimoire'
      )
    """,
    # Phase 8H-1 — Item System Unification
    "ALTER TABLE game_config_items ADD COLUMN ac_bonus INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE game_config_items ADD COLUMN effect_type TEXT",
    "ALTER TABLE game_config_items ADD COLUMN effect_dice TEXT",
    "ALTER TABLE game_config_items ADD COLUMN effect_bonus INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE game_config_items ADD COLUMN effect_target TEXT NOT NULL DEFAULT 'self'",
    "ALTER TABLE game_config_items ADD COLUMN charges INTEGER NOT NULL DEFAULT 1",
    "ALTER TABLE game_config_items ADD COLUMN ai_generated INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE game_config_items ADD COLUMN approved INTEGER NOT NULL DEFAULT 1",
    "ALTER TABLE game_config_items ADD COLUMN allowed_classes TEXT NOT NULL DEFAULT '[]'",
    """
    UPDATE game_config_items
    SET allowed_classes = proficiency_classes
    WHERE proficiency_classes IS NOT NULL
      AND proficiency_classes != '[]'
      AND (allowed_classes IS NULL OR allowed_classes = '[]')
    """,
    """
    INSERT OR IGNORE INTO game_config_items (
        key, label, item_type, description,
        value_gp, weight_kg, allowed_classes,
        ac_bonus, effect_type, effect_dice, effect_bonus, effect_target, charges,
        note, is_active, locked_at, created_at, updated_at,
        ai_generated, approved
    )
    SELECT
        key, label, 'consumable', description,
        base_price, weight_kg, '[]',
        0, effect_type, effect_dice, effect_bonus, effect_target, charges,
        note, is_active, locked_at, created_at, updated_at,
        0, 1
    FROM game_config_consumables
    """,
    """
    UPDATE character_inventory
    SET item_key = consumable_key,
        consumable_key = NULL
    WHERE consumable_key IS NOT NULL
      AND item_key IS NULL
      AND weapon_key IS NULL
      AND EXISTS (
          SELECT 1 FROM game_config_items WHERE key = character_inventory.consumable_key
      )
    """,
    "ALTER TABLE game_config_weapons ADD COLUMN ai_generated INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE game_config_weapons ADD COLUMN approved INTEGER NOT NULL DEFAULT 1",
    """
    INSERT OR IGNORE INTO game_config_meta (key, value)
    VALUES ('item_integrity_enabled', '0')
    """,
    # Align game_config_items with legacy consumables catalog when INSERT OR IGNORE blocked 8H copy (wrong item_type).
    """
    UPDATE game_config_items
    SET item_type = 'consumable'
    WHERE key IN (SELECT key FROM game_config_consumables)
      AND LOWER(COALESCE(item_type, '')) NOT IN ('consumable')
    """,
    # Same keys without legacy consumables row: infer consumable from effect_type (8H unified catalog).
    """
    UPDATE game_config_items
    SET item_type = 'consumable'
    WHERE LOWER(COALESCE(item_type, '')) NOT IN ('consumable')
      AND effect_type IS NOT NULL
      AND TRIM(effect_type) != ''
      AND LOWER(TRIM(effect_type)) IN (
        'heal_hp', 'restore_mana', 'remove_condition', 'add_condition', 'stat_buff'
      )
    """,
    # [S11a] Roadmap / plan MG per campaign (JSON), inject + campaign_ai_summaries in narrative prompt
    "ALTER TABLE campaigns ADD COLUMN gm_plan_json TEXT NOT NULL DEFAULT '{}'",
    """
    CREATE TABLE IF NOT EXISTS character_xp_grants (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        character_id INTEGER NOT NULL,
        campaign_id INTEGER NOT NULL,
        amount INTEGER NOT NULL,
        reason TEXT NOT NULL,
        source TEXT NOT NULL DEFAULT 'mg_manual',
        granted_by_user_id INTEGER NOT NULL,
        meta_json TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_character_xp_grants_character
    ON character_xp_grants(character_id, created_at DESC)
    """,
    # [T12 / S10e] Konfiguracyjna tabela nagród XP (kategoria → liczba punktów)
    """
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
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_game_config_xp_rewards_cat
    ON game_config_xp_rewards(category, sort_order, key)
    """,
    """
    CREATE TABLE IF NOT EXISTS campaign_snippets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        snippet_type TEXT NOT NULL,
        title TEXT NOT NULL,
        content TEXT NOT NULL,
        tags TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        is_active INTEGER NOT NULL DEFAULT 1
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_campaign_snippets_type
    ON campaign_snippets(snippet_type, is_active)
    """,
    # Stage 5 E1 — 8-slot anatomical equipment: armor_coverage column on items.
    # Enum enforced in code (loot_service._VALID_ARMOR_COVERAGE) because SQLite
    # cannot ALTER TABLE ADD COLUMN with a CHECK constraint. Allowed values:
    # 'head' | 'torso' | 'limb_arm' | 'limb_leg' | 'full'. Default 'torso' so
    # legacy rows still equip somewhere sensible until E3 backfill runs.
    "ALTER TABLE game_config_items ADD COLUMN armor_coverage TEXT DEFAULT 'torso'",
    # Stage 5 follow-up — weapon_slot enum on game_config_weapons.
    # Allowed values: 'main_hand' | 'two_handed' | 'off_hand_only' | 'either'.
    # Default 'main_hand' is the safest for legacy rows; backfill in ADMIN_SEEDS
    # then overrides based on label/range/weapon_type heuristics.
    "ALTER TABLE game_config_weapons ADD COLUMN weapon_slot TEXT DEFAULT 'main_hand'",
    # Issue #53 — trigger_keywords on skills. Must be here (before ADMIN_SEEDS)
    # so that the UPDATE seeds below don't crash on old/restored DBs that
    # pre-date _run_v2_schema_migrations adding it there.
    "ALTER TABLE game_config_skills ADD COLUMN trigger_keywords TEXT DEFAULT NULL",
    # Stage 14 O1 — structured game event log
    """
    CREATE TABLE IF NOT EXISTS game_events (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        event_type   TEXT NOT NULL,
        severity     TEXT NOT NULL DEFAULT 'info' CHECK(severity IN ('debug','info','warning','error')),
        campaign_id  INTEGER REFERENCES campaigns(id),
        character_id INTEGER REFERENCES characters(id),
        user_id      INTEGER REFERENCES users(id),
        event_data   TEXT NOT NULL DEFAULT '{}',
        created_at   TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_game_events_type_date ON game_events (event_type, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_game_events_campaign ON game_events (campaign_id, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_game_events_severity ON game_events (severity, created_at)",
    # Stage 14 O2 — LLM call performance log
    """
    CREATE TABLE IF NOT EXISTS llm_call_log (
        id                INTEGER PRIMARY KEY AUTOINCREMENT,
        campaign_id       INTEGER REFERENCES campaigns(id),
        call_type         TEXT NOT NULL,
        model             TEXT NOT NULL DEFAULT '',
        prompt_tokens     INTEGER NOT NULL DEFAULT 0,
        completion_tokens INTEGER NOT NULL DEFAULT 0,
        latency_ms        INTEGER NOT NULL DEFAULT 0,
        cache_hit         INTEGER NOT NULL DEFAULT 0,
        error             TEXT DEFAULT NULL,
        created_at        TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_llm_log_type_date ON llm_call_log (call_type, created_at)",
    # ── Voice service hosts — swappable TTS/STT backends (local CPU vs GPU box) ──
    # The backend reverse-proxies /voice/* to whichever row has is_active=1, so an
    # admin can repoint the game at a different machine from the panel, no restart.
    """
    CREATE TABLE IF NOT EXISTS voice_hosts (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        label      TEXT    NOT NULL,
        base_url   TEXT    NOT NULL UNIQUE,
        kind       TEXT    NOT NULL DEFAULT 'cpu',
        is_active  INTEGER NOT NULL DEFAULT 0,
        created_at TEXT    NOT NULL DEFAULT (datetime('now'))
    )
    """,
    # Seed the two known hosts (idempotent — only insert when missing).
    """
    INSERT INTO voice_hosts (label, base_url, kind, is_active)
    SELECT 'Lokalny (.61, CPU)', 'http://voice-service:8300', 'cpu', 1
    WHERE NOT EXISTS (SELECT 1 FROM voice_hosts WHERE base_url = 'http://voice-service:8300')
    """,
    """
    INSERT INTO voice_hosts (label, base_url, kind, is_active)
    SELECT 'GPU (.16, GTX 1660)', 'http://192.168.1.16:8300', 'gpu', 0
    WHERE NOT EXISTS (SELECT 1 FROM voice_hosts WHERE base_url = 'http://192.168.1.16:8300')
    """,
    """
    INSERT INTO voice_hosts (label, base_url, kind, is_active)
    SELECT 'F5-TTS (.170, Desktop GPU)', 'http://192.168.1.170:8301', 'gpu', 0
    WHERE NOT EXISTS (SELECT 1 FROM voice_hosts WHERE base_url = 'http://192.168.1.170:8301')
    """,
    # ── Voice config — persisted in game DB so it survives host switches ────────
    """
    CREATE TABLE IF NOT EXISTS voice_config (
        key   TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )
    """,
    "INSERT OR IGNORE INTO voice_config (key, value) VALUES ('tts_enabled', '1')",
    "INSERT OR IGNORE INTO voice_config (key, value) VALUES ('stt_enabled', '0')",
    "INSERT OR IGNORE INTO voice_config (key, value) VALUES ('tts_speed', '1.0')",
    "INSERT OR IGNORE INTO voice_config (key, value) VALUES ('tts_voice', 'piotr')",
    "INSERT OR IGNORE INTO voice_config (key, value) VALUES ('tts_noise_scale', '0.667')",
    "INSERT OR IGNORE INTO voice_config (key, value) VALUES ('tts_nfe_step', '32')",
    "INSERT OR IGNORE INTO voice_config (key, value) VALUES ('tts_cfg_strength', '2.0')",
    "INSERT OR IGNORE INTO voice_config (key, value) VALUES ('tts_cross_fade_duration', '0.15')",
    "INSERT OR IGNORE INTO voice_config (key, value) VALUES ('tts_sway_sampling_coef', '-1.0')",
    "INSERT OR IGNORE INTO voice_config (key, value) VALUES ('tts_seed', '-1')",
    "INSERT OR IGNORE INTO voice_config (key, value) VALUES ('stt_model', 'base')",
    "INSERT OR IGNORE INTO voice_config (key, value) VALUES ('stt_language', 'pl')",
    "INSERT OR IGNORE INTO voice_config (key, value) VALUES ('stt_beam_size', '5')",
    "INSERT OR IGNORE INTO voice_config (key, value) VALUES ('vad_filter', '0')",
    "INSERT OR IGNORE INTO voice_config (key, value) VALUES ('stt_silence_auto_stop_ms', '2000')",

    # ── Kuźnia Kampanii: adventure ideas + hooks + templates + feedback ────────
    """
    CREATE TABLE IF NOT EXISTS adventure_ideas (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        title           TEXT    NOT NULL,
        premise         TEXT    NOT NULL DEFAULT '',
        tone            TEXT    NOT NULL DEFAULT '[]',
        themes          TEXT    NOT NULL DEFAULT '[]',
        difficulty      TEXT    NOT NULL DEFAULT 'medium',
        structured_data TEXT    NOT NULL DEFAULT '{}',
        status          TEXT    NOT NULL DEFAULT 'draft',
        created_by      TEXT    NOT NULL DEFAULT 'admin',
        created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS adventure_hooks (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        adventure_idea_id   INTEGER,
        hook_type           TEXT    NOT NULL,
        title               TEXT    NOT NULL,
        description         TEXT    NOT NULL DEFAULT '',
        significance        TEXT    NOT NULL DEFAULT 'minor',
        draft_data          TEXT    NOT NULL DEFAULT '{}',
        status              TEXT    NOT NULL DEFAULT 'draft',
        promoted_record_id  INTEGER,
        promoted_table      TEXT,
        quality_rating      REAL    NOT NULL DEFAULT 0,
        times_used          INTEGER NOT NULL DEFAULT 0,
        created_at          TEXT    NOT NULL DEFAULT (datetime('now'))
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_adventure_hooks_type_status ON adventure_hooks(hook_type, status)",
    """
    CREATE TABLE IF NOT EXISTS campaign_templates (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        title            TEXT    NOT NULL,
        description      TEXT    NOT NULL DEFAULT '',
        difficulty_rating INTEGER NOT NULL DEFAULT 2,
        atmosphere       TEXT    NOT NULL DEFAULT '',
        gm_plan_json     TEXT    NOT NULL DEFAULT '{}',
        hook_ids         TEXT    NOT NULL DEFAULT '[]',
        status           TEXT    NOT NULL DEFAULT 'draft',
        play_count       INTEGER NOT NULL DEFAULT 0,
        adventure_idea_id INTEGER,
        created_by       TEXT    NOT NULL DEFAULT 'admin',
        created_at       TEXT    NOT NULL DEFAULT (datetime('now'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS campaign_hook_feedback (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        campaign_id  INTEGER NOT NULL,
        character_id INTEGER NOT NULL,
        hook_id      INTEGER NOT NULL,
        encountered  INTEGER NOT NULL DEFAULT 0,
        rating       INTEGER,
        what_worked  TEXT,
        what_didnt   TEXT,
        created_at   TEXT    NOT NULL DEFAULT (datetime('now')),
        UNIQUE(campaign_id, character_id, hook_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS pending_questionnaires (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        campaign_id  INTEGER NOT NULL,
        character_id INTEGER NOT NULL,
        status       TEXT    NOT NULL DEFAULT 'pending',
        created_at   TEXT    NOT NULL DEFAULT (datetime('now')),
        completed_at TEXT
    )
    """,
    "ALTER TABLE campaigns ADD COLUMN template_id INTEGER",
    "ALTER TABLE campaigns ADD COLUMN selected_hook_ids TEXT DEFAULT '[]'",
    "ALTER TABLE campaign_templates ADD COLUMN adventure_idea_id INTEGER",
    "ALTER TABLE game_config_weapons ADD COLUMN template_id INTEGER REFERENCES campaign_templates(id) ON DELETE SET NULL",
    "ALTER TABLE game_config_items ADD COLUMN template_id INTEGER REFERENCES campaign_templates(id) ON DELETE SET NULL",
    "ALTER TABLE game_config_consumables ADD COLUMN template_id INTEGER REFERENCES campaign_templates(id) ON DELETE SET NULL",
    "ALTER TABLE game_locations ADD COLUMN image_url TEXT DEFAULT NULL",
    "ALTER TABLE game_config_enemies ADD COLUMN image_url TEXT DEFAULT NULL",
    "ALTER TABLE npcs ADD COLUMN image_url TEXT DEFAULT NULL",
]

ADMIN_SEEDS = [
    """
    INSERT OR IGNORE INTO game_config_stats (key, label, description, sort_order) VALUES
    ('STR', 'Strength', 'Physical power and melee force', 1),
    ('DEX', 'Dexterity', 'Agility, stealth, initiative', 2),
    ('CON', 'Constitution', 'Endurance and physical resilience', 3),
    ('INT', 'Intelligence', 'Arcane aptitude and knowledge', 4),
    ('WIS', 'Wisdom', 'Awareness, survival, intuition', 5),
    ('CHA', 'Charisma', 'Persuasion and intimidation presence', 6)
    """,
    """
    INSERT OR IGNORE INTO game_config_skills (key, label, linked_stat, rank_ceiling, sort_order, description) VALUES
    ('stealth', 'Skradanie', 'DEX', 5, 1, 'Ciche poruszanie się i unikanie wykrycia. Odpowiada za wymykanie się, skradanie i działanie w cieniu.'),
    ('athletics', 'Atletyka', 'STR', 5, 2, 'Wysiłek fizyczny: bieganie, skoki, wspinaczka i dźwiganie.'),
    ('initiative', 'Inicjatywa', 'DEX', 5, 3, 'Szybka reakcja i gotowość do działania. Odpowiada za tempo i pierwszeństwo w niebezpiecznych chwilach.'),
    ('attack', 'Atak', 'STR', 5, 4, 'Zdolność do skutecznego uderzenia: celowanie, siła i timing ataku.'),
    ('two_handed', 'Broń dwuręczna', 'STR', 5, 5, 'Biegłość w prowadzeniu ciężkiej broni dwuręcznej bez utraty kontroli nad ciosem.'),
    ('awareness', 'Spostrzegawczość', 'WIS', 5, 6, 'Wnikliwa obserwacja i czujność. Pomaga dostrzec zagrożenia, śledzić tropy i wyłapać drobne sygnały.'),
    ('persuasion', 'Perswazja', 'CHA', 5, 7, 'Urok, argumenty i przekonywanie innych. Odpowiada za perswazję i rozmowę prowadzącą do zgody.'),
    ('intimidation', 'Zastraszanie', 'CHA', 5, 8, 'Straszenie, stanowczość i presja psychiczna. Odpowiada za zastraszanie i wymuszanie reakcji.'),
    ('survival', 'Przetrwanie', 'WIS', 5, 9, 'Przetrwanie w trudnych warunkach. Odpowiada za orientację, instynkt i decyzje w terenie.'),
    ('lore', 'Wiedza', 'INT', 5, 10, 'Wiedza z opowieści i dawnych ksiąg. Odpowiada za rozpoznanie kultury, historii, symboli i opowieści świata.'),
    ('arcana', 'Arkana', 'INT', 5, 11, 'Rozumienie magii i zjawisk magicznych. Odpowiada za rozpoznawanie zaklęć, rytuałów i sekretów arkanów.'),
    ('medicine', 'Medycyna', 'WIS', 5, 12, 'Udzielanie pomocy i leczenie. Odpowiada za ocenę ran, dobór środków i stabilizację w walce.'),
    ('investigation', 'Dochodzenie', 'INT', 5, 13, 'Dociekliwość i analizowanie szczegółów. Odpowiada za szukanie tropów, wyciąganie wniosków i składanie faktów.'),
    ('lockpick', 'Otwieranie zamków', 'DEX', 5, 14, 'Otwieranie zamków bez klucza — wytrychem, improwizowanym narzędziem lub gołymi rękami.'),
    ('acrobatics', 'Akrobatyka', 'DEX', 5, 15, 'Zwinność i równowaga w ruchu — przewroty, balansowanie na krawędzi, łapanie się w upadku.'),
    ('insight', 'Wnikliwość', 'WIS', 5, 16, 'Czytanie intencji i emocji rozmówcy — wykrywanie kłamstwa, oceny czyichś motywów.'),
    ('deception', 'Oszustwo', 'CHA', 5, 17, 'Wprowadzanie w błąd słowem lub gestem — kłamanie, blefowanie, granie roli.')
    """,
    # Translate any pre-existing English labels to Polish (idempotent — only
    # rewrites rows still holding the English defaults so admin renames are kept).
    """
    UPDATE game_config_skills SET label = 'Skradanie'          WHERE key = 'stealth'       AND label = 'Stealth'
    """,
    """
    UPDATE game_config_skills SET label = 'Atletyka'           WHERE key = 'athletics'     AND label = 'Athletics'
    """,
    """
    UPDATE game_config_skills SET label = 'Inicjatywa'         WHERE key = 'initiative'    AND label = 'Initiative'
    """,
    """
    UPDATE game_config_skills SET label = 'Atak'               WHERE key = 'attack'        AND label = 'Attack'
    """,
    """
    UPDATE game_config_skills SET label = 'Broń dwuręczna'     WHERE key = 'two_handed'    AND label = 'Two-Handed'
    """,
    """
    UPDATE game_config_skills SET label = 'Spostrzegawczość'   WHERE key = 'awareness'     AND label = 'Awareness'
    """,
    """
    UPDATE game_config_skills SET label = 'Perswazja'          WHERE key = 'persuasion'    AND label = 'Persuasion'
    """,
    """
    UPDATE game_config_skills SET label = 'Zastraszanie'       WHERE key = 'intimidation'  AND label = 'Intimidation'
    """,
    """
    UPDATE game_config_skills SET label = 'Przetrwanie'        WHERE key = 'survival'      AND label = 'Survival'
    """,
    """
    UPDATE game_config_skills SET label = 'Wiedza'             WHERE key = 'lore'          AND label = 'Lore'
    """,
    """
    UPDATE game_config_skills SET label = 'Arkana'             WHERE key = 'arcana'        AND label = 'Arcana'
    """,
    """
    UPDATE game_config_skills SET label = 'Medycyna'           WHERE key = 'medicine'      AND label = 'Medicine'
    """,
    """
    UPDATE game_config_skills SET label = 'Dochodzenie'        WHERE key = 'investigation' AND label = 'Investigation'
    """,
    """
    UPDATE game_config_skills SET label = 'Otwieranie zamków'  WHERE key = 'lockpick'      AND label = 'Lockpick'
    """,
    """
    UPDATE game_config_skills SET label = 'Akrobatyka'         WHERE key = 'acrobatics'    AND label = 'Acrobatics'
    """,
    """
    UPDATE game_config_skills SET label = 'Wnikliwość'         WHERE key = 'insight'       AND label = 'Insight'
    """,
    """
    UPDATE game_config_skills SET label = 'Oszustwo'           WHERE key = 'deception'     AND label = 'Deception'
    """,
    # Issue #53 fix 2 — narrow trigger_keywords for skills the LLM most often
    # picks WRONG. Only set when empty so admin overrides are preserved.
    # Keywords are space-prefixed substring matches against PL→ASCII normalized
    # player text, with a min length of 5 chars (per turns.py:2657).
    # `lockpick`: LLM picks Investigation (INT) instead of lockpick (DEX) for
    # every wytrych/sforsować phrasing — see audit issue #53.
    """
    UPDATE game_config_skills
       SET trigger_keywords = 'wytrych sforsować wytrychem wytrychami'
     WHERE key = 'lockpick' AND (trigger_keywords IS NULL OR trigger_keywords = '')
    """,
    # `medicine`: LLM occasionally picks Awareness/Investigation for triage —
    # the verbs opatrzyć / opatrunek / bandażować are unambiguous.
    """
    UPDATE game_config_skills
       SET trigger_keywords = 'opatrzyć opatrunek bandażuję bandażuje'
     WHERE key = 'medicine' AND (trigger_keywords IS NULL OR trigger_keywords = '')
    """,
    # `acrobatics`: LLM picks Athletics (STR) instead of Acrobatics (DEX) for
    # salto / przewrót / balansowanie phrasings — DEX-coded movement.
    """
    UPDATE game_config_skills
       SET trigger_keywords = 'salto przewrót akrobacj balansuję balansować'
     WHERE key = 'acrobatics' AND (trigger_keywords IS NULL OR trigger_keywords = '')
    """,
    # `insight`: LLM picks Awareness (perceptual) instead of Insight (social
    # read). These stems target *reading* people, not spotting things.
    """
    UPDATE game_config_skills
       SET trigger_keywords = 'wyczytać intencj przejrzeć podstęp zamiarów'
     WHERE key = 'insight' AND (trigger_keywords IS NULL OR trigger_keywords = '')
    """,
    # `deception`: LLM picks Persuasion (honest convincing) instead of
    # Deception (lying). First-person action verbs disambiguate.
    """
    UPDATE game_config_skills
       SET trigger_keywords = 'blefuję udaję oszukać ściemniam kłamię'
     WHERE key = 'deception' AND (trigger_keywords IS NULL OR trigger_keywords = '')
    """,
    """
    INSERT OR IGNORE INTO game_config_dc (key, label, value, sort_order, description) VALUES
    ('easy', 'Łatwe', 8, 1, 'Proste, oczywiste działania. Jeśli gracz robi to sprytnie, zwykle ma dużą szansę na sukces.'),
    ('medium', 'Średnie', 12, 2, 'Wymaga skupienia i pewnej biegłości. Błędy kosztują, ale to nadal realna próba.'),
    ('hard', 'Trudne', 16, 3, 'Niepewne i wymagające. Nawet przy dobrym przygotowaniu jest sporo ryzyka.'),
    ('extreme', 'Ekstremalne', 20, 4, 'Granica możliwości. Taka próba jest ryzykowna i często wiąże się z konsekwencjami porażki.'),
    ('legendary', 'Legendarne', 24, 5, 'Działanie na poziomie legend. Tylko wyjątkowe przygotowanie, talent lub dramatyczny zryw może mieć sens.')
    """,
    """
    INSERT OR IGNORE INTO game_config_weapons
    (key, label, damage_die, linked_stat, allowed_classes, is_active, locked_at, created_at, updated_at)
    VALUES
    ('shortsword', 'Short Sword', 'd6', 'STR', '["warrior","ranger"]', 1, NULL, datetime('now'), datetime('now')),
    ('sword', 'Sword', 'd8', 'STR', '["warrior","ranger"]', 1, NULL, datetime('now'), datetime('now')),
    ('shield', 'Shield', 'd4', 'STR', '["warrior","ranger"]', 1, NULL, datetime('now'), datetime('now')),
    ('shortbow', 'Shortbow', 'd6', 'DEX', '["warrior","ranger"]', 1, NULL, datetime('now'), datetime('now')),
    ('staff', 'Staff', 'd6', 'INT', '["scholar"]', 1, NULL, datetime('now'), datetime('now')),
    -- Unarmed: every character can punch. Tiny die so it's clearly worse than any real weapon.
    ('unarmed', 'Pięści', '1d3', 'STR', '["warrior","ranger","scholar"]', 1, NULL, datetime('now'), datetime('now'))
    """,
    # Stage 5: stamp the unarmed row with the right weapon_slot/weapon_type.
    """
    UPDATE game_config_weapons SET weapon_slot = 'either', weapon_type = 'melee'
    WHERE key = 'unarmed' AND weapon_slot != 'either'
    """,
    """
    INSERT OR IGNORE INTO game_config_enemies
    (key, label, hp_base, ac_base, attack_bonus, damage_die, description, is_active, locked_at, created_at, updated_at)
    VALUES
    ('goblin', 'Goblin', 8, 11, 2, 'd6', 'Fast and opportunistic skirmisher.', 1, NULL, datetime('now'), datetime('now'))
    """,
    """
    INSERT OR IGNORE INTO game_config_enemies
    (key, label, hp_base, ac_base, attack_bonus, damage_die, description, is_active, locked_at, created_at, updated_at)
    VALUES
    ('unknown_attacker', 'Nieznany napastnik', 12, 11, 2, '1d6',
     'Generyczny przeciwnik, gdy nie znasz dokładnego typu — musi istnieć w silniku walki.', 1, NULL, datetime('now'), datetime('now')),
    ('enemy', 'Wróg', 10, 10, 1, '1d4',
     'Ogólny placeholder na wroga zgodny z tagiem [COMBAT_START:enemy].', 1, NULL, datetime('now'), datetime('now')),
    ('guard', 'Strażnik', 15, 13, 3, '1d6', 'Straż miejska lub posterunek.', 1, NULL, datetime('now'), datetime('now')),
    ('old_man', 'Starzec', 6, 8, 0, '1d3', 'Słabszy NPC (np. scena ze starcem).', 1, NULL, datetime('now'), datetime('now')),
    ('wolf', 'Wilk', 10, 12, 3, '1d6', 'Dzikie zwierzę.', 1, NULL, datetime('now'), datetime('now')),
    ('bandit', 'Bandyta', 12, 13, 3, '1d8', 'Typowy bandyta / rabuś.', 1, NULL, datetime('now'), datetime('now')),
    ('orc', 'Ork', 18, 14, 4, '1d8', 'Wojownik orków.', 1, NULL, datetime('now'), datetime('now')),
    ('skeleton', 'Szkielet', 10, 12, 2, '1d6', 'Nieumarły.', 1, NULL, datetime('now'), datetime('now')),
    ('troll', 'Troll', 35, 15, 6, '1d10', 'Duży i wytrzymały przeciwnik.', 1, NULL, datetime('now'), datetime('now'))
    """,
    """
    INSERT OR IGNORE INTO game_config_conditions
    (key, label, effect_json, description, is_active, locked_at, created_at, updated_at)
    VALUES
    ('poisoned', 'Poisoned', '{"schema_version":1,"effect_category":"character_condition","effects":[{"type":"static_stat_modifier","stat":"STR","value":-2,"expires":"duration_rounds:3"}]}', 'Temporary STR penalty.', 1, NULL, datetime('now'), datetime('now'))
    """,
    """
    INSERT OR IGNORE INTO game_config_conditions
    (key, label, effect_json, description, is_active, stackable, auto_remove, locked_at, created_at, updated_at)
    VALUES
    ('zaskoczony', 'Zaskoczony', '{"schema_version":1,"effect_category":"character_condition","grants_attacker_bonus":{"atk_bonus":2,"first_hit_doubled":true},"clear_on":"damage_taken"}', 'Cel zaskoczony — atakujący zyskuje +2 do rzutu i podwaja obrażenia pierwszego trafienia. Znika po otrzymaniu obrażeń.', 1, 0, 'on_damage', NULL, datetime('now'), datetime('now'))
    """,
    """
    UPDATE game_config_stats
    SET locked_at = COALESCE(locked_at, '2026-04-14T00:00:00Z')
    """,
    """
    UPDATE game_config_skills
    SET locked_at = COALESCE(locked_at, '2026-04-14T00:00:00Z')
    """,
    """
    UPDATE game_config_dc
    SET locked_at = COALESCE(locked_at, '2026-04-14T00:00:00Z')
    """,
    """
    INSERT OR IGNORE INTO game_config_meta (key, value)
    VALUES ('config_version', '1.0.0')
    """,
    """
    INSERT OR IGNORE INTO game_config_meta (key, value)
    VALUES ('loki_url', 'http://loki:3100')
    """,
    """
    INSERT OR IGNORE INTO game_config_meta (key, value)
    VALUES (
      'xp_skill_rank_costs',
      '{"1":50,"2":100,"3":200,"4":400,"5":1200}'
    )
    """,
    """
    INSERT OR IGNORE INTO game_config_meta (key, value)
    VALUES (
      'xp_stat_point_costs',
      '{"8":40,"9":50,"10":65,"11":85,"12":110,"13":140,"14":180,"15":230,"16":300,"17":400,"18":550,"19":750,"20":1000}'
    )
    """,
    """
    INSERT OR IGNORE INTO game_config_meta (key, value)
    VALUES ('xp_stat_value_ceiling', '20')
    """,
    """
    INSERT OR IGNORE INTO game_config_meta (key, value)
    VALUES ('summary_rollup_cooldown_turns', '20')
    """,
    """
    INSERT OR IGNORE INTO game_config_meta (key, value)
    VALUES ('summary_auto_ensure_every_n_narrative_turns', '20')
    """,
    """
    UPDATE game_config_enemies
    SET tier = 'weak', attacks_per_turn = 1, damage_bonus = 1,
        damage_type = 'physical', xp_award = 3
    WHERE key = 'goblin'
    """,
    """
    UPDATE game_config_enemies
    SET dex_modifier = CASE key
        WHEN 'bandit' THEN 1
        WHEN 'wolf' THEN 2
        WHEN 'skeleton' THEN -1
        WHEN 'orc' THEN 0
        WHEN 'troll' THEN -2
        WHEN 'unknown_attacker' THEN 0
        WHEN 'enemy' THEN 0
        ELSE COALESCE(dex_modifier, 0)
    END
    WHERE key IN ('bandit', 'wolf', 'skeleton', 'orc', 'troll', 'unknown_attacker', 'enemy')
    """,
    """
    UPDATE game_config_weapons SET weapon_type = 'ranged', range_m = 90, finesse = 1, two_handed = 0
    WHERE key = 'shortbow'
    """,
    """
    UPDATE game_config_weapons SET weapon_type = 'spell', two_handed = 0, finesse = 0
    WHERE key = 'staff'
    """,
    """
    UPDATE game_config_weapons
    SET value_gp = CASE key
        WHEN 'shortsword' THEN 15
        WHEN 'sword' THEN 25
        WHEN 'shield' THEN 12
        WHEN 'shortbow' THEN 25
        WHEN 'staff' THEN 6
        WHEN 'wooden_shield' THEN 8
        WHEN 'quarterstaff' THEN 7
        ELSE COALESCE(value_gp, 0)
    END
    WHERE key IN ('shortsword', 'sword', 'shield', 'shortbow', 'staff', 'wooden_shield', 'quarterstaff')
    """,
    """
    INSERT OR IGNORE INTO game_config_items (
        key, label, item_type, description, value_gp, weight_kg, effect_json, is_active,
        allowed_classes, note, locked_at, created_at, updated_at
    ) VALUES
    ('leatherarmor', 'Leather Armor', 'armor', 'Light body armor.', 20, 8.0, NULL, 1,
     '["warrior","ranger"]', NULL, NULL, datetime('now'), datetime('now'))
    """,
    """
    INSERT OR IGNORE INTO game_config_consumables (
        key, label, description, effect_type, effect_dice, effect_bonus, effect_target,
        weight_kg, charges, base_price, note, is_active, locked_at, created_at, updated_at
    ) VALUES
    ('health_potion_small', 'Small Health Potion', 'Restores a little HP.', 'heal_hp', '1d4', 0, 'self',
     0.2, 1, 5, NULL, 1, NULL, datetime('now'), datetime('now')),
    ('mana_potion', 'Mana Potion', 'Restores a little mana.', 'restore_mana', NULL, 0, 'self',
     0.2, 1, 8, NULL, 1, NULL, datetime('now'), datetime('now'))
    """,
    """
    INSERT OR IGNORE INTO game_config_archetypes
    (key, label, description, starter_items_json, starter_gold_gp, is_active, locked_at, created_at, updated_at)
    VALUES
    ('warrior', 'Wojownik', 'Mistrz walki wręcz i broni.',
     '[{"weapon_key":"shortsword"},{"weapon_key":"wooden_shield"},{"weapon_key":"shortbow"},{"item_key":"leatherarmor"}]',
     10, 1, NULL, datetime('now'), datetime('now')),
    ('scholar', 'Uczony', 'Mag i znawca tajemnej wiedzy.',
     '[{"weapon_key":"quarterstaff"},{"consumable_key":"health_potion_small"},{"consumable_key":"mana_potion"}]',
     15, 1, NULL, datetime('now'), datetime('now'))
    """,
    """
    INSERT OR IGNORE INTO game_config_weapons
    (key, label, damage_die, linked_stat, allowed_classes, is_active, locked_at, created_at, updated_at)
    VALUES
    ('wooden_shield', 'Drewniana Tarcza', 'd4', 'STR', '["warrior"]', 1, NULL, datetime('now'), datetime('now')),
    ('quarterstaff', 'Laska', 'd6', 'STR', '["scholar","warrior"]', 1, NULL, datetime('now'), datetime('now'))
    """,
    """
    UPDATE game_config_archetypes
    SET starter_items_json =
      '[{"weapon_key":"shortsword"},{"weapon_key":"wooden_shield"},{"weapon_key":"shortbow"},{"item_key":"leatherarmor"}]',
        updated_at = datetime('now')
    WHERE key = 'warrior'
    """,
    """
    UPDATE game_config_archetypes
    SET starter_items_json =
      '[{"weapon_key":"quarterstaff"},{"consumable_key":"health_potion_small"},{"consumable_key":"mana_potion"}]',
        updated_at = datetime('now')
    WHERE key = 'scholar'
    """,
    """
    INSERT OR IGNORE INTO npcs
    (key, label, npc_type, description, personality_json, is_shop, shop_inventory_json, is_active, created_at, updated_at)
    VALUES
    (
        'merchant_aldric', 'Aldric, kupiec', 'merchant',
        'Wędrowny kupiec z towarami pierwszej potrzeby.',
        '{"personality":"sknerski, podejrzliwy, lubi plotki o lokalnych sprawach","topics":["handel","ceny","lokalne wiadomości"],"secret":null}',
        1, '[]', 1, datetime('now'), datetime('now')
    ),
    (
        'innkeeper_marta', 'Marta, karczmarka', 'neutral',
        'Gospodyni lokalnej karczmy, zna wszystkie plotki.',
        '{"personality":"gadatliwa, serdeczna, dobra gospodyni","topics":["plotki","noclegi","jedzenie","lokalni mieszkańcy"],"secret":null}',
        0, '[]', 1, datetime('now'), datetime('now')
    ),
    (
        'quest_giver_eldran', 'Eldran, mag', 'quest_giver',
        'Tajemniczy mag szukający odważnych poszukiwaczy.',
        '{"personality":"enigmatyczny, mówi zagadkami, zna starą wiedzę","topics":["magia","zadania","artefakty","historia świata"],"secret":"szuka zaginionego tomu zaklinarzy"}',
        0, '[]', 1, datetime('now'), datetime('now')
    ),
    (
        'blacksmith_goran', 'Goran, kowal', 'merchant',
        'Kowal specjalizujący się w broni i zbroi.',
        '{"personality":"lakoniczny, konkretny, dumny ze swojego rzemiosła","topics":["broń","zbroja","naprawa ekwipunku"],"secret":null}',
        1, '[]', 1, datetime('now'), datetime('now')
    )
    """,
    """
    UPDATE npcs
    SET shop_inventory_json = json('[{"type":"weapon","key":"shortsword"},{"type":"item","key":"health_potion"},{"type":"item","key":"torch"}]'),
        updated_at = datetime('now')
    WHERE key = 'merchant_aldric'
    """,
    """
    UPDATE npcs
    SET shop_inventory_json = json('[{"type":"weapon","key":"shortsword"},{"type":"weapon","key":"shortbow"},{"type":"armor","key":"leatherarmor"}]'),
        updated_at = datetime('now')
    WHERE key = 'blacksmith_goran'
    """,
    """
    INSERT OR IGNORE INTO npc_locations (npc_id, location_key)
    SELECT id, 'inn_main'
    FROM npcs
    WHERE key = 'innkeeper_marta'
      AND EXISTS (SELECT 1 FROM game_locations WHERE key = 'inn_main')
    """,
    # Phase 8D — Location Integrity default flags (8D-3)
    # [T12 / S10e] Domyślne nagrody (widełki [S10b] — wartości środkowe pasma)
    """
    INSERT OR IGNORE INTO game_config_xp_rewards
        (key, category, label, description, xp_amount, sort_order, is_active)
    VALUES
        ('enemy_tier_weak', 'enemy_tier', 'Wróg: ślaby / tło',
         'Pas [S10b]: 2–5 XP — domyślnie 3', 3, 10, 1),
        ('enemy_tier_standard', 'enemy_tier', 'Wróg: standard',
         'Pas [S10b]: 5–12 XP — domyślnie 8', 8, 20, 1),
        ('enemy_tier_elite', 'enemy_tier', 'Wróg: elita / mały boss',
         'Pas [S10b]: 25–50 XP — domyślnie 30', 30, 30, 1),
        ('enemy_tier_boss', 'enemy_tier', 'Wróg: boss / wyjątkowe zagrożenie',
         'Pas [S10b]: 50–120 XP — domyślnie 70', 70, 40, 1),
        ('quest_minor', 'quest', 'Quest / wątek poboczny',
         'Szacunek [S10b]: 10–25 XP', 15, 50, 1),
        ('quest_main', 'quest', 'Quest / cel główny kampanii',
         'Szacunek [S10b]: 40–100 XP (po modelu questów)', 70, 60, 1),
        ('mg_grant_small', 'mg_grant', 'MG: drobny plus fabularny',
         'Pas [S10b]: 3–8 XP', 5, 100, 1),
        ('mg_grant_scene', 'mg_grant', 'MG: mini-cel / postęp sceny',
         'Pas [S10b]: 5–15 XP', 10, 110, 1),
        ('mg_grant_breakthrough', 'mg_grant', 'MG: istotny przełom',
         'Pas [S10b]: 15–35 XP', 25, 120, 1),
        ('mg_grant_exceptional', 'mg_grant', 'MG: wybitny sukces (rzadko)',
         'Pas [S10b]: 35–60 XP', 45, 130, 1)
    """,
    # Stage 2D XS1-XS15 reward keys
    """
    INSERT OR IGNORE INTO game_config_xp_rewards
        (key, category, label, description, xp_amount, sort_order, is_active)
    VALUES
        ('campaign.beat_complete',    'campaign',    'Cel bitu ukończony',           'XS1: +30 XP za ukończenie bitu narracyjnego',       30, 200, 1),
        ('campaign.side_quest',       'campaign',    'Quest poboczny ukończony',      'XS2: +40 XP za [QUEST_COMPLETE]',                   40, 210, 1),
        ('campaign.dungeon_cleared',  'campaign',    'Loch oczyszczony',             'XS3: +75 XP za [DUNGEON_CLEAR]',                    75, 220, 1),
        ('campaign.campaign_ending',  'campaign',    'Koniec kampanii',              'XS4: +200 XP za [CAMPAIGN_END]',                   200, 230, 1),
        ('exploration.location_new',  'exploration', 'Pierwsza wizyta w lokacji',    'XS5: +15 XP — pierwsza makro-lokacja',              15, 300, 1),
        ('exploration.npc_first_talk','exploration', 'Pierwsza rozmowa z NPC',       'XS6: +5 XP za DIALOGUE z nowym npc_key',             5, 310, 1),
        ('exploration.secret',        'exploration', 'Odkrycie: lore/tajemnica',     'XS7: +10 XP za [DISCOVERY:lore_key]',               10, 320, 1),
        ('exploration.hidden_room',   'exploration', 'Odkrycie: ukryta lokacja',     'XS8: +10 XP za [DISCOVERY:secret_location]',        10, 330, 1),
        ('skills.skill_dc_12',        'skills',      'Test biegłości DC 12-15',      'XS9: +3 XP za sukces DC ∈ [12-15]',                  3, 400, 1),
        ('skills.skill_dc_16',        'skills',      'Test trudny DC 16-19',         'XS10: +8 XP za sukces DC ∈ [16-19]',                 8, 410, 1),
        ('skills.skill_dc_20',        'skills',      'Test legendarny DC ≥ 20',      'XS11: +15 XP za sukces DC ≥ 20',                   15, 420, 1),
        ('narrative.free_grant',      'narrative',   'Nagroda narracyjna (LLM tag)', 'XS12: [XP_GRANT:powód:ilość] — kap 50 XP/sesja',   10, 500, 1),
        ('combat.outnumbered_victory','combat',      'Zwycięstwo w przewadze wroga', 'XS13: +20 XP — walka z 3+ wrogami',                20, 600, 1),
        ('combat.death_save_survived','combat',      'Przeżycie rzutu na śmierć',    'XS14: +15 XP za przeżycie death save',             15, 610, 1),
        ('session.start_bonus',       'session',     'Bonus za powrót do sesji',     'XS15: +10 XP za nową sesję po ≥30 min przerwie',    10, 700, 1)
    """,
    # Stage 5 E3 — backfill armor_coverage on existing armor rows.
    # Each UPDATE is gated by `IS NULL OR ''` so admin edits are never clobbered.
    # Order is specific → generic: helmet/gauntlet/greave first, then full plate,
    # finally a catch-all 'torso' for anything that didn't match.
    """
    UPDATE game_config_items SET armor_coverage = 'head'
    WHERE item_type = 'armor'
      AND (armor_coverage IS NULL OR armor_coverage = '')
      AND (
        LOWER(label) LIKE '%helm%'
        OR LOWER(label) LIKE '%hełm%'
        OR LOWER(label) LIKE '%kapelusz%'
        OR LOWER(label) LIKE '%hood%'
        OR LOWER(label) LIKE '%kaptur%'
      )
    """,
    """
    UPDATE game_config_items SET armor_coverage = 'limb_arm'
    WHERE item_type = 'armor'
      AND (armor_coverage IS NULL OR armor_coverage = '')
      AND (
        LOWER(label) LIKE '%gauntlet%'
        OR LOWER(label) LIKE '%rękawic%'
        OR LOWER(label) LIKE '%rekawic%'
        OR LOWER(label) LIKE '%naramien%'
        OR LOWER(label) LIKE '%bracer%'
      )
    """,
    """
    UPDATE game_config_items SET armor_coverage = 'limb_leg'
    WHERE item_type = 'armor'
      AND (armor_coverage IS NULL OR armor_coverage = '')
      AND (
        LOWER(label) LIKE '%greave%'
        OR LOWER(label) LIKE '%nagolen%'
        OR LOWER(label) LIKE '%spodni%'
        OR LOWER(label) LIKE '%boots%'
        OR LOWER(label) LIKE '%buty%'
      )
    """,
    """
    UPDATE game_config_items SET armor_coverage = 'full'
    WHERE item_type = 'armor'
      AND (armor_coverage IS NULL OR armor_coverage = '')
      AND (
        LOWER(label) LIKE '%pełna%'
        OR LOWER(label) LIKE '%pelna%'
        OR LOWER(label) LIKE '%plate armor%'
        OR LOWER(label) LIKE '%full plate%'
        OR LOWER(label) LIKE '%full armor%'
      )
    """,
    """
    UPDATE game_config_items SET armor_coverage = 'torso'
    WHERE item_type = 'armor'
      AND (armor_coverage IS NULL OR armor_coverage = '')
    """,
    # Migrate equipped character_inventory rows from legacy slot='armor' → 'torso'.
    # Idempotent: rows already on 'torso' don't match.
    """
    UPDATE character_inventory SET slot = 'torso' WHERE slot = 'armor' AND equipped = 1
    """,
    # Stage 5 follow-up — weapon_slot backfill on game_config_weapons.
    # The column has DEFAULT 'main_hand' so legacy rows arrive pre-stamped;
    # we still need to upgrade obvious cases (shields → off_hand_only,
    # daggers → either, bows/staves/two-handers → two_handed).
    # Gate: only override when current value is still the default 'main_hand'.
    # That way an admin who explicitly set 'main_hand' for, say, a "hand axe"
    # stays main_hand, while ranged/heavy weapons get fixed.
    """
    UPDATE game_config_weapons SET weapon_slot = 'off_hand_only'
    WHERE weapon_slot = 'main_hand'
      AND (LOWER(label) LIKE '%shield%' OR LOWER(label) LIKE '%tarcz%'
           OR LOWER(key)   LIKE '%shield%' OR LOWER(key)   LIKE '%tarcz%')
    """,
    """
    UPDATE game_config_weapons SET weapon_slot = 'either'
    WHERE weapon_slot = 'main_hand'
      AND (LOWER(label) LIKE '%dagger%' OR LOWER(label) LIKE '%sztylet%'
           OR LOWER(key)   LIKE '%dagger%' OR LOWER(key)   LIKE '%sztylet%')
    """,
    """
    UPDATE game_config_weapons SET weapon_slot = 'two_handed'
    WHERE weapon_slot = 'main_hand'
      AND (
        two_handed = 1
        OR weapon_type = 'ranged'
        OR weapon_type = 'spell'
        OR range_m IS NOT NULL
        OR LOWER(label) LIKE '%bow%'      OR LOWER(label) LIKE '%łuk%'
        OR LOWER(label) LIKE '%crossbow%' OR LOWER(label) LIKE '%kusz%'
        OR LOWER(label) LIKE '%staff%'    OR LOWER(label) LIKE '%laska%' OR LOWER(label) LIKE '%kij%'
        OR LOWER(label) LIKE '%greatsword%' OR LOWER(label) LIKE '%two-hand%'
        OR LOWER(label) LIKE '%greataxe%'   OR LOWER(label) LIKE '%halberd%'
        OR LOWER(label) LIKE '%warhammer%'  OR LOWER(label) LIKE '%spear%' OR LOWER(label) LIKE '%włóczn%'
        OR LOWER(key)   LIKE '%bow%'      OR LOWER(key)   LIKE '%staff%'
        OR LOWER(key)   LIKE '%great%'    OR LOWER(key)   LIKE '%halberd%'
      )
    """,
    # Keep the legacy `two_handed` boolean in sync — engine code may still read it.
    """
    UPDATE game_config_weapons SET two_handed = 1 WHERE weapon_slot = 'two_handed' AND two_handed = 0
    """,
    """
    UPDATE game_config_weapons SET two_handed = 0 WHERE weapon_slot != 'two_handed' AND two_handed = 1
    """,
    # KW1 — knowledge book seeds (combat / magic / exploration / mechanics / general)
    """INSERT OR IGNORE INTO knowledge_book (tip_key, category, title, body, sort_order) VALUES ('combat_turn_order','combat','Kolejność w walce','Na początku walki każda postać i przeciwnik rzuca na Inicjatywę (d20 + DEX). Wyższy wynik działa pierwszy. Twoja tura = 1 akcja (atak, zaklęcie, użycie przedmiotu, zmiana strefy) + ruch.',10)""",
    """INSERT OR IGNORE INTO knowledge_book (tip_key, category, title, body, sort_order) VALUES ('combat_attack_roll','combat','Rzut na atak','Rzucasz d20 + modyfikator STR (broń wręcz) lub DEX (broń dystansowa) + ranga umiejętności. Wynik ≥ Obronie (AC) wroga to trafienie. Obrażenia zależą od broni i twoich statystyk.',20)""",
    """INSERT OR IGNORE INTO knowledge_book (tip_key, category, title, body, sort_order) VALUES ('combat_zone','combat','Zwarcie i dystans','Każda walka ma dwie strefy: Zwarcie i Dystans. Broń wręcz działa tylko w Zwarciu — jeśli jesteś za daleko, musisz najpierw zbliżyć się (kosztuje całą turę). Łucznicy i magowie wolą Dystans.',30)""",
    """INSERT OR IGNORE INTO knowledge_book (tip_key, category, title, body, sort_order) VALUES ('combat_armor','combat','Tarcza i zbroja','Zbroja i tarcza zwiększają Obronę (AC), utrudniając wrogom trafienie. Im wyższe AC, tym rzadziej obrywa twoja postać. Sprawdź AC w karcie postaci.',40)""",
    """INSERT OR IGNORE INTO knowledge_book (tip_key, category, title, body, sort_order) VALUES ('combat_surprise','combat','Zaskoczenie','Jeśli zaatakujesz z ukrycia lub wróg cię nie wykrył, atakujesz z zaskoczenia. Ofiara traci swoją pierwszą turę i nie może reagować. Skradanie się przed walką się opłaca.',50)""",
    """INSERT OR IGNORE INTO knowledge_book (tip_key, category, title, body, sort_order) VALUES ('combat_flee','combat','Ucieczka z walki','Wpisz "uciekam" lub użyj przycisku Ucieczka, aby spróbować wydostać się z walki. Wymaga testu DEX vs. Inicjatywy wroga. Udana ucieczka kończy walkę bez zwycięstwa — tracisz też potencjalne łupy.',60)""",
    """INSERT OR IGNORE INTO knowledge_book (tip_key, category, title, body, sort_order) VALUES ('combat_healing','combat','Leczenie w walce','Mikstury zdrowia możesz użyć w swojej turze (kosztuje akcję). Zaklęcia leczące Scholar też działają podczas walki. Uważaj — przy 0 HP musisz rzucić na przeżycie.',70)""",
    """INSERT OR IGNORE INTO knowledge_book (tip_key, category, title, body, sort_order) VALUES ('magic_casting','magic','Rzucanie zaklęć','Każde zaklęcie kosztuje Manę. Rzut na atak zaklęciem: d20 + INT + ranga zaklęcia. Nat 20 = podwójne obrażenia lub efekt specjalny. Nat 1 = Miscast — coś pójdzie nie tak.',10)""",
    """INSERT OR IGNORE INTO knowledge_book (tip_key, category, title, body, sort_order) VALUES ('magic_miscast','magic','Miscast — czarodziejska porażka','Nat 1 na rzucie zaklęcia wywołuje niekontrolowany efekt. Poziomy 1–2: ogłuszenie. Poziomy 3–4: obrażenia własne (1k4). Poziomy 5–7: obrażenia + ogłuszenie. Poziomy 8+: obrażenia (1k8) + ogłuszenie + efekt wtórny.',20)""",
    """INSERT OR IGNORE INTO knowledge_book (tip_key, category, title, body, sort_order) VALUES ('magic_arcane_points','magic','Punkty Arkana','Zdobywasz 1 Punkt Arkana za każdy poziom. Wydajesz je na: nowe zaklęcie (1 PA), rangę 2 (1 PA), rangę 3 (2 PA). Zaplanuj mądrze — Punktów Arkana jest mało.',30)""",
    """INSERT OR IGNORE INTO knowledge_book (tip_key, category, title, body, sort_order) VALUES ('magic_mana_recovery','magic','Odzyskiwanie Many','Mana wraca w całości po Długim Odpoczynku. Krótki Odpoczynek przywraca tylko część HP — mana pozostaje. Zarządzaj zasobami mądrze, bo nie zawsze będzie czas na odpoczynek.',40)""",
    """INSERT OR IGNORE INTO knowledge_book (tip_key, category, title, body, sort_order) VALUES ('exploration_skill_dc','exploration','Skala trudności testów','DC 8 = Łatwy (większość zdoła). DC 12 = Średni (wymaga skupienia). DC 16 = Trudny (wymaga wprawy). DC 20 = Ekstremalny (mistrz w dziedzinie). DC 24+ = Legendarny (granica ludzkich możliwości).',10)""",
    """INSERT OR IGNORE INTO knowledge_book (tip_key, category, title, body, sort_order) VALUES ('exploration_stealth','exploration','Skradanie','Test DEX vs. Postrzeganie strażnika. Powodzenie = niezauważony. Możesz próbować ominąć walkę zupełnie albo przygotować atak z zaskoczenia. Jasne oświetlenie i głośna zbroja utrudniają skradanie.',20)""",
    """INSERT OR IGNORE INTO knowledge_book (tip_key, category, title, body, sort_order) VALUES ('exploration_lockpick','exploration','Otwieranie zamków','Test DEX. Jeśli masz wytrych — możesz próbować każdy zamknięty zamek. Bez wytrycha potrzebujesz klucza. Nat 1 przy otwieraniu = złamany wytrych lub zablokowany zamek.',30)""",
    """INSERT OR IGNORE INTO knowledge_book (tip_key, category, title, body, sort_order) VALUES ('exploration_traps','exploration','Pułapki','Pułapki wykrywasz testem Postrzegania (biernym lub aktywnym). Kiedy wykryjesz pułapkę, możesz ją rozbroić (test DEX), ominąć lub wyłączyć inaczej. Zignorowanie pułapki = obrażenia lub gorszy efekt.',40)""",
    """INSERT OR IGNORE INTO knowledge_book (tip_key, category, title, body, sort_order) VALUES ('exploration_hex_map','exploration','Mapa heksów','Świat jest podzielony na heksy. Odkrywasz je przez eksplorację i narrację. Każdy heks może mieć typ terenu, napotkane wyzwania i notatki z kampanii. Twoja mapa rośnie wraz z przygodami.',50)""",
    """INSERT OR IGNORE INTO knowledge_book (tip_key, category, title, body, sort_order) VALUES ('mechanics_rest_short','mechanics','Krótki odpoczynek','Możesz odpocząć krótko w bezpiecznym miejscu. Odzyskujesz część HP (Kość Wytrzymałości + CON). Nie przywraca many ani nie realizuje oczekujących PD. Wróg może nie dać ci czasu na odpoczynek.',10)""",
    """INSERT OR IGNORE INTO knowledge_book (tip_key, category, title, body, sort_order) VALUES ('mechanics_rest_long','mechanics','Długi odpoczynek','Pełny odpoczynek (obóz, karczma): pełna regeneracja HP i Many, realizacja Oczekujących PD (stają się Dostępnymi PD). Wymaga bezpiecznego miejsca — nie wszędzie możesz rozłożyć obóz.',20)""",
    """INSERT OR IGNORE INTO knowledge_book (tip_key, category, title, body, sort_order) VALUES ('mechanics_xp_spending','mechanics','Wydawanie PD','Dostępne PD wydajesz na: rangę umiejętności (50/100/200/400/1200 PD) lub wzrost statystyki (40–1000 PD zależnie od wartości docelowej). Otwórz kartę postaci → zakładka Statystyki → przycisk Awansuj.',30)""",
    """INSERT OR IGNORE INTO knowledge_book (tip_key, category, title, body, sort_order) VALUES ('character_stats','general','Statystyki postaci','STR: siła fizyczna i walka wręcz. DEX: zwinność, ucieczka, skradanie, dystans. CON: HP i wytrzymałość. INT: magia i wiedza. WIS: spostrzegawczość i intuicja. CHA: rozmowy i perswazja. LCK: szczęście w rzutach.',10)""",
    """INSERT OR IGNORE INTO knowledge_book (tip_key, category, title, body, sort_order) VALUES ('character_death_save','general','Rzut na przeżycie','Przy 0 HP: rzucasz d20. ≥ 10 = przeżywasz z 1 HP (i dostajesz bonus XP). < 10 = śmierć bohatera. Modyfikator CON pomaga w tym rzucie. Mikstura użyta przez kogoś innego może go zastąpić.',20)""",
    """INSERT OR IGNORE INTO knowledge_book (tip_key, category, title, body, sort_order) VALUES ('character_conditions_list','general','Stany i efekty','Zatruty: -2 do rzutów. Ogłuszony: traci turę. Krwawiący: traci HP co turę. Spowolniony: redukuje akcje. Przerażony: penalty do ataków. Stany można leczyć odpoczynkiem, zaklęciami lub miksturami.',30)""",
    """INSERT OR IGNORE INTO knowledge_book (tip_key, category, title, body, sort_order) VALUES ('inventory_slots','general','Plecak i ekwipunek','Broń trzymana w dłoni to Główna Ręka. Tarcza lub broń zapasowa to Druga Ręka. Zbroja zajmuje slot Tułów. Przedmioty, mikstury i materiały trafiają do Plecaka. Sprawdź aktualny ekwipunek w karcie postaci.',40)""",
    """INSERT OR IGNORE INTO knowledge_book (tip_key, category, title, body, sort_order) VALUES ('economy_gold','general','Złoto i handel','Złoto (sz) zdobywasz z lootów, questów i sprzedaży. Możesz kupować od kupców podczas eksploracji. Cena zależy od reputacji i CHA. Nie trać złota na rzeczy zbędne — dobre wyposażenie ratuje życie.',50)""",
    # Phase 9A-4 — Shop NPC: Borys Kowal seed + npc_locations for all 3 shop NPCs
    """
    INSERT OR IGNORE INTO npcs
    (key, label, npc_type, description, personality_json, is_shop, shop_inventory_json, is_active, created_at, updated_at)
    VALUES (
        'seed_pending_npc_borys', 'Borys Kowal', 'merchant',
        'Handlarz materiałami survivalowymi i aptekarskimi.',
        '{"personality":"spokojny, praktyczny, ceni doświadczenie survivalowe","topics":["materiały","leczenie","przetrwanie"],"secret":null}',
        1,
        '[{"type":"consumable","key":"healing_potion"},{"type":"item","key":"rope_hemp"},{"type":"consumable","key":"torch"},{"type":"item","key":"bandage"}]',
        1, datetime('now'), datetime('now')
    )
    """,
    """
    INSERT OR IGNORE INTO npc_locations (npc_id, location_key)
    SELECT id, 'volhynia_targowisko' FROM npcs WHERE key = 'merchant_aldric'
    AND EXISTS (SELECT 1 FROM game_locations WHERE key = 'volhynia_targowisko')
    """,
    """
    INSERT OR IGNORE INTO npc_locations (npc_id, location_key)
    SELECT id, 'volhynia_kupiecka' FROM npcs WHERE key = 'merchant_aldric'
    AND EXISTS (SELECT 1 FROM game_locations WHERE key = 'volhynia_kupiecka')
    """,
    """
    INSERT OR IGNORE INTO npc_locations (npc_id, location_key)
    SELECT id, 'wolanka_kuznia' FROM npcs WHERE key = 'blacksmith_goran'
    AND EXISTS (SELECT 1 FROM game_locations WHERE key = 'wolanka_kuznia')
    """,
    """
    INSERT OR IGNORE INTO npc_locations (npc_id, location_key)
    SELECT id, 'volhynia_targowisko' FROM npcs WHERE key = 'seed_pending_npc_borys'
    AND EXISTS (SELECT 1 FROM game_locations WHERE key = 'volhynia_targowisko')
    """,
    # Task 6 — Archer loot table expansion (was 1 entry → 7 entries, archer-themed)
    """
    INSERT INTO game_config_loot_entries (loot_table_key, weapon_key, weight)
    SELECT 'loot_bandit_archer', 'shortbow', 30
    WHERE NOT EXISTS (SELECT 1 FROM game_config_loot_entries WHERE loot_table_key='loot_bandit_archer' AND weapon_key='shortbow')
    """,
    """
    INSERT INTO game_config_loot_entries (loot_table_key, weapon_key, weight)
    SELECT 'loot_bandit_archer', 'dagger', 20
    WHERE NOT EXISTS (SELECT 1 FROM game_config_loot_entries WHERE loot_table_key='loot_bandit_archer' AND weapon_key='dagger')
    """,
    """
    INSERT INTO game_config_loot_entries (loot_table_key, item_key, weight)
    SELECT 'loot_bandit_archer', 'rope_hemp', 20
    WHERE NOT EXISTS (SELECT 1 FROM game_config_loot_entries WHERE loot_table_key='loot_bandit_archer' AND item_key='rope_hemp')
    """,
    """
    INSERT INTO game_config_loot_entries (loot_table_key, item_key, weight)
    SELECT 'loot_bandit_archer', 'leather_gloves', 15
    WHERE NOT EXISTS (SELECT 1 FROM game_config_loot_entries WHERE loot_table_key='loot_bandit_archer' AND item_key='leather_gloves')
    """,
    """
    INSERT INTO game_config_loot_entries (loot_table_key, item_key, weight)
    SELECT 'loot_bandit_archer', 'bandage', 15
    WHERE NOT EXISTS (SELECT 1 FROM game_config_loot_entries WHERE loot_table_key='loot_bandit_archer' AND item_key='bandage')
    """,
    """
    INSERT INTO game_config_loot_entries (loot_table_key, item_key, weight)
    SELECT 'loot_bandit_archer', 'belt_pouch', 10
    WHERE NOT EXISTS (SELECT 1 FROM game_config_loot_entries WHERE loot_table_key='loot_bandit_archer' AND item_key='belt_pouch')
    """,
]


def _rebuild_loot_entries_for_consumable_support(conn: sqlite3.Connection) -> None:
    """Allow NULL item_key when consumable_key is set (SQLite cannot relax NOT NULL via ALTER)."""
    cur = conn.execute("PRAGMA table_info(game_config_loot_entries)").fetchall()
    cols = {row[1]: row for row in cur}
    if "item_key" not in cols:
        return
    if "consumable_key" not in cols:
        return
    if cols["item_key"][3] == 0:
        return
    logger.info("admin_migration_rebuild_loot_entries_nullable_item")
    conn.execute("PRAGMA foreign_keys=OFF")
    try:
        has_weapon = "weapon_key" in cols
        conn.executescript(
            """
            DROP INDEX IF EXISTS idx_loot_entries_table;
            DROP INDEX IF EXISTS ux_loot_entries_item;
            DROP INDEX IF EXISTS ux_loot_entries_consumable;
            DROP INDEX IF EXISTS ux_loot_entries_weapon;
            CREATE TABLE game_config_loot_entries_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                loot_table_key TEXT NOT NULL REFERENCES game_config_loot_tables(key) ON DELETE CASCADE,
                item_key TEXT REFERENCES game_config_items(key) ON DELETE CASCADE,
                consumable_key TEXT REFERENCES game_config_consumables(key) ON DELETE CASCADE,
                weapon_key TEXT REFERENCES game_config_weapons(key) ON DELETE CASCADE,
                weight INTEGER NOT NULL DEFAULT 10,
                qty_min INTEGER NOT NULL DEFAULT 1,
                qty_max INTEGER NOT NULL DEFAULT 1,
                CHECK (
                    (CASE WHEN item_key IS NOT NULL THEN 1 ELSE 0 END)
                  + (CASE WHEN consumable_key IS NOT NULL THEN 1 ELSE 0 END)
                  + (CASE WHEN weapon_key IS NOT NULL THEN 1 ELSE 0 END) = 1
                )
            );
            """
        )
        if has_weapon:
            conn.execute(
                """
                INSERT INTO game_config_loot_entries_new
                    (id, loot_table_key, item_key, consumable_key, weapon_key, weight, qty_min, qty_max)
                SELECT id, loot_table_key, item_key,
                       CASE WHEN typeof(consumable_key) = 'null' THEN NULL ELSE consumable_key END,
                       CASE WHEN typeof(weapon_key) = 'null' THEN NULL ELSE weapon_key END,
                       weight, qty_min, qty_max
                FROM game_config_loot_entries
                """
            )
        else:
            conn.execute(
                """
                INSERT INTO game_config_loot_entries_new
                    (id, loot_table_key, item_key, consumable_key, weapon_key, weight, qty_min, qty_max)
                SELECT id, loot_table_key, item_key,
                       CASE WHEN typeof(consumable_key) = 'null' THEN NULL ELSE consumable_key END,
                       NULL,
                       weight, qty_min, qty_max
                FROM game_config_loot_entries
                """
            )
        conn.executescript(
            """
            DROP TABLE game_config_loot_entries;
            ALTER TABLE game_config_loot_entries_new RENAME TO game_config_loot_entries;
            CREATE INDEX IF NOT EXISTS idx_loot_entries_table
                ON game_config_loot_entries(loot_table_key);
            CREATE UNIQUE INDEX IF NOT EXISTS ux_loot_entries_item
                ON game_config_loot_entries(loot_table_key, item_key) WHERE item_key IS NOT NULL;
            CREATE UNIQUE INDEX IF NOT EXISTS ux_loot_entries_consumable
                ON game_config_loot_entries(loot_table_key, consumable_key) WHERE consumable_key IS NOT NULL;
            CREATE UNIQUE INDEX IF NOT EXISTS ux_loot_entries_weapon
                ON game_config_loot_entries(loot_table_key, weapon_key) WHERE weapon_key IS NOT NULL;
            """
        )
        conn.commit()
    finally:
        conn.execute("PRAGMA foreign_keys=ON")


def _upgrade_loot_entries_three_way_xor(conn: sqlite3.Connection) -> None:
    """If loot_entries is still 2-way only, add weapon_key and rebuild CHECK + indexes for 3-way XOR."""
    if not conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='game_config_loot_entries'"
    ).fetchone():
        return
    cols = {row[1]: row for row in conn.execute("PRAGMA table_info(game_config_loot_entries)").fetchall()}
    if "consumable_key" not in cols:
        return
    if conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='index' AND name='ux_loot_entries_weapon'"
    ).fetchone():
        return
    if "weapon_key" not in cols:
        try:
            conn.execute(
                """
                ALTER TABLE game_config_loot_entries ADD COLUMN weapon_key TEXT
                REFERENCES game_config_weapons(key) ON DELETE CASCADE
                """
            )
            conn.commit()
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e).lower():
                raise
    cols = {row[1]: row for row in conn.execute("PRAGMA table_info(game_config_loot_entries)").fetchall()}
    if "weapon_key" not in cols:
        logger.info("admin_migration_loot_entries_weapon_key_missing")
        return
    logger.info("admin_migration_upgrade_loot_entries_three_way_xor")
    conn.execute("PRAGMA foreign_keys=OFF")
    try:
        conn.executescript(
            """
            DROP INDEX IF EXISTS idx_loot_entries_table;
            DROP INDEX IF EXISTS ux_loot_entries_item;
            DROP INDEX IF EXISTS ux_loot_entries_consumable;
            DROP INDEX IF EXISTS ux_loot_entries_weapon;
            CREATE TABLE game_config_loot_entries_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                loot_table_key TEXT NOT NULL REFERENCES game_config_loot_tables(key) ON DELETE CASCADE,
                item_key TEXT REFERENCES game_config_items(key) ON DELETE CASCADE,
                consumable_key TEXT REFERENCES game_config_consumables(key) ON DELETE CASCADE,
                weapon_key TEXT REFERENCES game_config_weapons(key) ON DELETE CASCADE,
                weight INTEGER NOT NULL DEFAULT 10,
                qty_min INTEGER NOT NULL DEFAULT 1,
                qty_max INTEGER NOT NULL DEFAULT 1,
                CHECK (
                    (CASE WHEN item_key IS NOT NULL THEN 1 ELSE 0 END)
                  + (CASE WHEN consumable_key IS NOT NULL THEN 1 ELSE 0 END)
                  + (CASE WHEN weapon_key IS NOT NULL THEN 1 ELSE 0 END) = 1
                )
            );
            INSERT INTO game_config_loot_entries_new
                (id, loot_table_key, item_key, consumable_key, weapon_key, weight, qty_min, qty_max)
            SELECT id, loot_table_key, item_key,
                   CASE WHEN typeof(consumable_key) = 'null' THEN NULL ELSE consumable_key END,
                   CASE WHEN typeof(weapon_key) = 'null' THEN NULL ELSE weapon_key END,
                   weight, qty_min, qty_max
            FROM game_config_loot_entries;
            DROP TABLE game_config_loot_entries;
            ALTER TABLE game_config_loot_entries_new RENAME TO game_config_loot_entries;
            CREATE INDEX IF NOT EXISTS idx_loot_entries_table
                ON game_config_loot_entries(loot_table_key);
            CREATE UNIQUE INDEX IF NOT EXISTS ux_loot_entries_item
                ON game_config_loot_entries(loot_table_key, item_key) WHERE item_key IS NOT NULL;
            CREATE UNIQUE INDEX IF NOT EXISTS ux_loot_entries_consumable
                ON game_config_loot_entries(loot_table_key, consumable_key) WHERE consumable_key IS NOT NULL;
            CREATE UNIQUE INDEX IF NOT EXISTS ux_loot_entries_weapon
                ON game_config_loot_entries(loot_table_key, weapon_key) WHERE weapon_key IS NOT NULL;
            """
        )
        conn.commit()
    finally:
        conn.execute("PRAGMA foreign_keys=ON")


def _finalize_phase_8h_items_schema(conn: sqlite3.Connection) -> None:
    """Finalize 8H item columns after additive migrations complete."""
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='game_config_items'"
    ).fetchone()
    if not row:
        return
    cols = {r[1]: r for r in conn.execute("PRAGMA table_info(game_config_items)").fetchall()}
    if "allowed_classes" in cols and "proficiency_classes" in cols:
        conn.execute(
            """
            UPDATE game_config_items
            SET allowed_classes = proficiency_classes
            WHERE proficiency_classes IS NOT NULL
              AND proficiency_classes != '[]'
              AND (allowed_classes IS NULL OR allowed_classes = '[]')
            """
        )
        conn.commit()
        conn.execute("ALTER TABLE game_config_items DROP COLUMN proficiency_classes")
        conn.commit()
        logger.info("admin_migration_phase_8h_drop_column", table_name="game_config_items", column_name="proficiency_classes")
        cols.pop("proficiency_classes", None)
    if "weight" in cols and "weight_kg" in cols:
        conn.execute(
            """
            UPDATE game_config_items
            SET weight_kg = weight
            WHERE COALESCE(weight, 0) > 0
              AND COALESCE(weight_kg, 0.0) = 0.0
            """
        )
        conn.commit()
        conn.execute("ALTER TABLE game_config_items DROP COLUMN weight")
        conn.commit()
        logger.info("admin_migration_phase_8h_drop_column", table_name="game_config_items", column_name="weight")


def _finalize_t25_effect_json_schema(conn: sqlite3.Connection) -> None:
    """T25: once effect_json is populated, drop flat effect columns from item catalog."""
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='game_config_items'"
    ).fetchone()
    if not row:
        return
    cols = {r[1]: r for r in conn.execute("PRAGMA table_info(game_config_items)").fetchall()}
    if "effect_json" not in cols:
        return

    if "effect_type" in cols:
        pending = conn.execute(
            """
            SELECT COUNT(*) AS c
            FROM game_config_items
            WHERE COALESCE(TRIM(effect_json), '') = ''
              AND COALESCE(TRIM(effect_type), '') IN ('heal_hp', 'restore_mana', 'remove_condition', 'add_condition')
            """
        ).fetchone()
        if pending and int(pending["c"] or 0) > 0:
            logger.info(
                "admin_migration_t25_skip_drop_columns",
                reason="convertible rows still miss effect_json",
                pending_rows=int(pending["c"] or 0),
            )
            return

    for column_name in ("effect_type", "effect_dice", "effect_bonus", "effect_target"):
        if column_name not in cols:
            continue
        conn.execute(f"ALTER TABLE game_config_items DROP COLUMN {column_name}")
        conn.commit()
        logger.info("admin_migration_t25_drop_column", table_name="game_config_items", column_name=column_name)


def _finalize_phase_8h_loot_entries(conn: sqlite3.Connection) -> None:
    """No-op: superseded by _ensure_loot_entries_full_schema which keeps consumable_key."""
    return

    has_currency_code = "currency_code" in cols
    logger.info("admin_migration_phase_8h_rebuild_loot_entries")
    conn.execute("PRAGMA foreign_keys=OFF")
    try:
        conn.execute("DROP INDEX IF EXISTS idx_loot_entries_table")
        conn.execute("DROP INDEX IF EXISTS ux_loot_entries_item")
        conn.execute("DROP INDEX IF EXISTS ux_loot_entries_consumable")
        conn.execute("DROP INDEX IF EXISTS ux_loot_entries_weapon")
        conn.execute(
            f"""
            CREATE TABLE game_config_loot_entries_8h (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                loot_table_key TEXT NOT NULL REFERENCES game_config_loot_tables(key) ON DELETE CASCADE,
                item_key TEXT REFERENCES game_config_items(key) ON DELETE CASCADE,
                weapon_key TEXT REFERENCES game_config_weapons(key) ON DELETE CASCADE,
                {'currency_code TEXT,' if has_currency_code else ''}
                weight INTEGER NOT NULL DEFAULT 10,
                qty_min INTEGER NOT NULL DEFAULT 1,
                qty_max INTEGER NOT NULL DEFAULT 1,
                CONSTRAINT loot_xor CHECK (
                    (CASE WHEN item_key IS NOT NULL THEN 1 ELSE 0 END) +
                    (CASE WHEN weapon_key IS NOT NULL THEN 1 ELSE 0 END) = 1
                )
            )
            """
        )
        conn.execute(
            f"""
            INSERT OR IGNORE INTO game_config_loot_entries_8h
                (id, loot_table_key, item_key, weapon_key, {'currency_code, ' if has_currency_code else ''}weight, qty_min, qty_max)
            SELECT
                id,
                loot_table_key,
                COALESCE(
                    item_key,
                    CASE
                        WHEN consumable_key IS NOT NULL
                         AND EXISTS (SELECT 1 FROM game_config_items WHERE key = game_config_loot_entries.consumable_key)
                        THEN consumable_key
                        ELSE NULL
                    END
                ),
                weapon_key,
                {'currency_code,' if has_currency_code else ''}
                weight,
                qty_min,
                qty_max
            FROM game_config_loot_entries
            WHERE (
                CASE
                    WHEN COALESCE(
                        item_key,
                        CASE
                            WHEN consumable_key IS NOT NULL
                             AND EXISTS (SELECT 1 FROM game_config_items WHERE key = game_config_loot_entries.consumable_key)
                            THEN consumable_key
                            ELSE NULL
                        END
                    ) IS NOT NULL THEN 1 ELSE 0
                END
                +
                CASE WHEN weapon_key IS NOT NULL THEN 1 ELSE 0 END
            ) = 1
            """
        )
        conn.execute("DROP TABLE game_config_loot_entries")
        conn.execute("ALTER TABLE game_config_loot_entries_8h RENAME TO game_config_loot_entries")
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_loot_entries_table
            ON game_config_loot_entries(loot_table_key)
            """
        )
        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS ux_loot_entries_item
            ON game_config_loot_entries(loot_table_key, item_key) WHERE item_key IS NOT NULL
            """
        )
        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS ux_loot_entries_weapon
            ON game_config_loot_entries(loot_table_key, weapon_key) WHERE weapon_key IS NOT NULL
            """
        )
        conn.commit()
    finally:
        conn.execute("PRAGMA foreign_keys=ON")


def _migrate_legacy_archetype_json(conn: sqlite3.Connection) -> None:
    """One-time: normalize legacy archetype / allowed_classes JSON tokens to scholar."""
    # Check if required tables exist (for fresh/test databases)
    tables_exist = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name IN ('game_config_weapons', 'characters')"
    ).fetchall()
    if len(tables_exist) < 2:
        return  # Tables don't exist yet, skip migration
    
    _m = "ma" + "ge"
    _s = "scho" + "lar"
    q = chr(34)
    old_class = q + _m + q
    new_class = q + _s + q
    cur = conn.cursor()
    cur.execute(
        """
        SELECT COUNT(*) FROM game_config_weapons
        WHERE allowed_classes LIKE ?
        """,
        ("%" + old_class + "%",),
    )
    if cur.fetchone()[0]:
        cur.execute(
            """
            UPDATE game_config_weapons
            SET allowed_classes = REPLACE(allowed_classes, ?, ?)
            WHERE allowed_classes LIKE ?
            """,
            (old_class, new_class, "%" + old_class + "%"),
        )
        conn.commit()
        logger.info(
            "admin_migration_archetype_weapons_updated",
            updated_count=cur.rowcount,
        )

    a1_old = q + "archetype" + q + ":" + q + _m + q
    a1_new = q + "archetype" + q + ":" + q + _s + q
    a2_old = q + "archetype" + q + ": " + q + _m + q
    a2_new = q + "archetype" + q + ": " + q + _s + q
    cur.execute(
        """
        SELECT COUNT(*) FROM characters
        WHERE sheet_json LIKE ? OR sheet_json LIKE ?
        """,
        ("%" + a1_old + "%", "%" + a2_old + "%"),
    )
    if cur.fetchone()[0]:
        cur.execute(
            """
            UPDATE characters
            SET sheet_json = REPLACE(REPLACE(sheet_json, ?, ?), ?, ?)
            WHERE sheet_json LIKE ? OR sheet_json LIKE ?
            """,
            (a1_old, a1_new, a2_old, a2_new, "%" + a1_old + "%", "%" + a2_old + "%"),
        )
        conn.commit()
        logger.info(
            "admin_migration_archetype_character_sheets_updated",
            updated_count=cur.rowcount,
        )


def _ensure_active_combat_location_tag(conn: sqlite3.Connection) -> None:
    """Add location_tag to active_combat if missing (idempotent)."""
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='active_combat'"
    ).fetchone()
    if not row:
        return
    existing = [r[1] for r in conn.execute("PRAGMA table_info(active_combat)").fetchall()]
    if "location_tag" not in existing:
        conn.execute("ALTER TABLE active_combat ADD COLUMN location_tag TEXT DEFAULT NULL")
        conn.commit()
        logger.info("admin_migration_applied", sql_preview="active_combat ADD COLUMN location_tag")


def _ensure_active_combat_loot_pool(conn: sqlite3.Connection) -> None:
    """Add loot_pool to active_combat if missing (idempotent)."""
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='active_combat'"
    ).fetchone()
    if not row:
        return
    existing = [r[1] for r in conn.execute("PRAGMA table_info(active_combat)").fetchall()]
    if "loot_pool" not in existing:
        conn.execute("ALTER TABLE active_combat ADD COLUMN loot_pool TEXT DEFAULT NULL")
        conn.commit()
        logger.info("admin_migration_applied", sql_preview="active_combat ADD COLUMN loot_pool")


def _ensure_campaign_ai_summaries_audience(conn: sqlite3.Connection) -> None:
    """[T02 / S11b] Distinguish player vs GM rollup rows; legacy rows default to player."""
    try:
        conn.execute(
            "ALTER TABLE campaign_ai_summaries ADD COLUMN audience TEXT NOT NULL DEFAULT 'player'"
        )
        conn.commit()
        logger.info("admin_migration_applied", sql_preview="campaign_ai_summaries ADD audience")
    except sqlite3.OperationalError as e:
        msg = str(e).lower()
        if "duplicate column" in msg or "already exists" in msg or "no such table" in msg:
            return
        raise


def _ensure_enemy_loot_table_and_drop_chance(conn: sqlite3.Connection) -> None:
    """Add loot_table_key / drop_chance on game_config_enemies if missing (idempotent)."""
    cur = conn.cursor()
    for sql in (
        "ALTER TABLE game_config_enemies ADD COLUMN loot_table_key TEXT REFERENCES game_config_loot_tables(key) ON DELETE SET NULL",
        "ALTER TABLE game_config_enemies ADD COLUMN drop_chance REAL NOT NULL DEFAULT 1.0",
    ):
        try:
            cur.execute(sql)
            conn.commit()
            logger.info("admin_migration_applied", sql_preview=f"{sql[:72]}...")
        except sqlite3.OperationalError as e:
            msg = str(e).lower()
            if "duplicate column" in msg or "already exists" in msg:
                continue
            raise


def _backfill_enemy_loot_tables(conn: sqlite3.Connection) -> None:
    """Create and assign loot tables for active enemies that don't have one."""
    try:
        rows = conn.execute(
            """
            SELECT key, label FROM game_config_enemies
            WHERE is_active = 1
              AND (loot_table_key IS NULL OR loot_table_key = '')
            """
        ).fetchall()
        if not rows:
            return
        for row in rows:
            ek = row[0]
            label = row[1] or ek
            lt_key = f"loot_{ek}"
            exists = conn.execute(
                "SELECT key FROM game_config_loot_tables WHERE key = ?", (lt_key,)
            ).fetchone()
            if not exists:
                conn.execute(
                    "INSERT INTO game_config_loot_tables (key, label, description, is_active) VALUES (?, ?, '', 1)",
                    (lt_key, f"Łupy: {label}"),
                )
            conn.execute(
                "UPDATE game_config_enemies SET loot_table_key = ? WHERE key = ?",
                (lt_key, ek),
            )
        conn.commit()
        logger.info("admin_migration_backfill_enemy_loot_tables", count=len(rows))
    except Exception as e:
        logger.warning("admin_migration_backfill_enemy_loot_tables_failed", error=str(e))


def _ensure_user_llm_settings_mode(conn: sqlite3.Connection) -> None:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='user_llm_settings'"
    ).fetchone()
    if not row:
        return
    existing = [r[1] for r in conn.execute("PRAGMA table_info(user_llm_settings)").fetchall()]
    if "mode" not in existing:
        conn.execute("ALTER TABLE user_llm_settings ADD COLUMN mode TEXT NOT NULL DEFAULT 'custom'")
        conn.commit()
        logger.info("admin_migration_applied", sql_preview="user_llm_settings ADD COLUMN mode")
    conn.execute(
        """
        UPDATE user_llm_settings
        SET mode = 'custom'
        WHERE COALESCE(TRIM(mode), '') NOT IN ('default', 'custom')
        """
    )
    conn.commit()


def _make_character_first_migration(conn: sqlite3.Connection) -> None:
    """Task 42: make characters.campaign_id nullable + add status column.

    SQLite cannot ALTER COLUMN to drop NOT NULL, so we recreate the table.
    Idempotent: checks for 'status' column presence before running.
    """
    cursor = conn.execute("PRAGMA table_info(characters)")
    cols = {row[1] for row in cursor.fetchall()}
    if "status" in cols:
        logger.debug("v2_migration_skipped", label="v2-character-first-flow")
        return

    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        # Back-fill columns that may be absent in older DB snapshots so the
        # INSERT SELECT below works regardless of when the backup was taken.
        for _col, _default in (
            ("hero_status", "'active'"),
            ("visited_location_keys", "'[]'"),
        ):
            if _col not in cols:
                try:
                    conn.execute(
                        f"ALTER TABLE characters ADD COLUMN {_col} TEXT NOT NULL DEFAULT {_default}"
                    )
                except sqlite3.OperationalError:
                    pass

        conn.execute("DROP TABLE IF EXISTS characters_v42")
        conn.execute("""
            CREATE TABLE characters_v42 (
                id                    INTEGER PRIMARY KEY AUTOINCREMENT,
                campaign_id           INTEGER,
                user_id               INTEGER NOT NULL,
                name                  TEXT NOT NULL,
                system_id             TEXT NOT NULL,
                sheet_json            TEXT NOT NULL,
                location              TEXT,
                is_active             INTEGER NOT NULL DEFAULT 1,
                created_at            TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                backstory             TEXT,
                appearance            TEXT,
                personality           TEXT,
                motivation            TEXT,
                note                  TEXT,
                gold                  INTEGER NOT NULL DEFAULT 0,
                gold_gp               INTEGER NOT NULL DEFAULT 0,
                hero_status           TEXT NOT NULL DEFAULT 'active',
                visited_location_keys TEXT NOT NULL DEFAULT '[]',
                status                TEXT NOT NULL DEFAULT 'idle',
                FOREIGN KEY (campaign_id) REFERENCES campaigns(id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        conn.execute("""
            INSERT INTO characters_v42
                (id, campaign_id, user_id, name, system_id, sheet_json, location,
                 is_active, created_at, backstory, appearance, personality, motivation, note,
                 gold, gold_gp, hero_status, visited_location_keys, status)
            SELECT id, campaign_id, user_id, name, system_id, sheet_json, location,
                   is_active, created_at, backstory, appearance, personality, motivation, note,
                   gold, gold_gp, hero_status, visited_location_keys, 'idle'
            FROM characters
        """)
        conn.execute("DROP TABLE characters")
        conn.execute("ALTER TABLE characters_v42 RENAME TO characters")
        conn.commit()
        logger.info("v2_migration_applied", label="v2-character-first-flow")
    except Exception as e:
        logger.error("v2_migration_failed", label="v2-character-first-flow", error=str(e))
        raise
    finally:
        conn.execute("PRAGMA foreign_keys = ON")


def _run_v2_schema_migrations(conn: sqlite3.Connection) -> None:
    """V2 architecture migrations — idempotent, safe to re-run."""

    def _exec(sql: str, label: str) -> None:
        try:
            conn.execute(sql)
            conn.commit()
            logger.info("v2_migration_applied", label=label)
        except sqlite3.OperationalError as e:
            msg = str(e).lower()
            if "already exists" in msg or "duplicate column" in msg:
                logger.debug("v2_migration_skipped", label=label)
            elif "no such table" in msg:
                # Table doesn't exist in this DB (e.g. test fixtures only create admin tables).
                # Skip silently — the column will be added when the full app DB is used.
                logger.debug("v2_migration_skipped_no_table", label=label, reason=str(e))
            else:
                logger.error("v2_migration_error", label=label, error=str(e))
                raise

    # ── New tables ────────────────────────────────────────────────────────

    _exec("""
        CREATE TABLE IF NOT EXISTS action_log (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id     INTEGER NOT NULL,
            character_id    INTEGER NOT NULL,
            turn_number     INTEGER NOT NULL,
            action_type     TEXT    NOT NULL,
            action_params   TEXT    NOT NULL DEFAULT '{}',
            mechanic_result TEXT    NOT NULL DEFAULT '{}',
            narrative_text  TEXT    NOT NULL DEFAULT '',
            created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (campaign_id) REFERENCES campaigns(id) ON DELETE CASCADE
        )
    """, "v2-action-log-table")
    _exec("CREATE INDEX IF NOT EXISTS idx_action_log_campaign ON action_log (campaign_id, turn_number)", "v2-action-log-idx-campaign")
    _exec("CREATE INDEX IF NOT EXISTS idx_action_log_character ON action_log (character_id, created_at)", "v2-action-log-idx-character")

    _exec("""
        CREATE TABLE IF NOT EXISTS character_conditions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id    INTEGER NOT NULL,
            condition_type  TEXT    NOT NULL,
            severity        INTEGER NOT NULL DEFAULT 1,
            rounds_remaining INTEGER DEFAULT NULL,
            expires_at      TEXT    DEFAULT NULL,
            source          TEXT    NOT NULL DEFAULT '',
            effect_json     TEXT    NOT NULL DEFAULT '{}',
            FOREIGN KEY (character_id) REFERENCES characters(id) ON DELETE CASCADE
        )
    """, "v2-character-conditions-table")
    _exec("CREATE INDEX IF NOT EXISTS idx_char_conditions_active ON character_conditions (character_id, expires_at)", "v2-char-conditions-idx")

    _exec("""
        CREATE TABLE IF NOT EXISTS enemy_behavior_profiles (
            enemy_key                       TEXT    PRIMARY KEY,
            default_action                  TEXT    NOT NULL DEFAULT 'attack',
            hp_threshold_flee               INTEGER NOT NULL DEFAULT 0,
            special_ability_key             TEXT    DEFAULT NULL,
            special_ability_cooldown_turns  INTEGER NOT NULL DEFAULT 3,
            dialogue_on_aggro               TEXT    NOT NULL DEFAULT '',
            dialogue_on_death               TEXT    NOT NULL DEFAULT '',
            fear_aura                       INTEGER NOT NULL DEFAULT 0,
            fear_dc                         INTEGER NOT NULL DEFAULT 0
        )
    """, "v2-enemy-behavior-profiles-table")

    _exec("""
        CREATE TABLE IF NOT EXISTS combat_loot (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id         INTEGER NOT NULL,
            character_id        INTEGER NOT NULL,
            combat_location_id  TEXT    NOT NULL,
            loot_items          TEXT    NOT NULL DEFAULT '[]',
            status              TEXT    NOT NULL DEFAULT 'available',
            created_at          TEXT    NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (campaign_id) REFERENCES campaigns(id) ON DELETE CASCADE,
            FOREIGN KEY (character_id) REFERENCES characters(id)
        )
    """, "v2-combat-loot-table")
    _exec("CREATE INDEX IF NOT EXISTS idx_combat_loot_campaign ON combat_loot (campaign_id, status)", "v2-combat-loot-idx")

    _exec("""
        CREATE TABLE IF NOT EXISTS campaign_ideas (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            category        TEXT    NOT NULL,
            title           TEXT    NOT NULL,
            description     TEXT    NOT NULL DEFAULT '',
            structured_data TEXT    NOT NULL DEFAULT '{}',
            tags            TEXT    NOT NULL DEFAULT '[]',
            quality_rating  INTEGER NOT NULL DEFAULT 0,
            times_used      INTEGER NOT NULL DEFAULT 0,
            created_by      TEXT    NOT NULL DEFAULT 'system',
            created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
            review_status   TEXT    NOT NULL DEFAULT 'draft',
            cooldown_hours  INTEGER NOT NULL DEFAULT 0
        )
    """, "v2-campaign-ideas-table")
    _exec("CREATE INDEX IF NOT EXISTS idx_campaign_ideas_category ON campaign_ideas (category, review_status, quality_rating)", "v2-campaign-ideas-idx")
    _exec("ALTER TABLE campaign_ideas ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1", "v2-campaign-ideas-is-active")
    _exec("ALTER TABLE game_config_weapons ADD COLUMN effect_json TEXT DEFAULT NULL", "v2-weapon-effect-json")
    _exec("ALTER TABLE game_config_skills ADD COLUMN trigger_keywords TEXT DEFAULT NULL", "v2-skill-trigger-keywords")

    # ── Task 26: Scholar Spells ───────────────────────────────────────────────
    _exec("""
        CREATE TABLE IF NOT EXISTS game_config_spells (
            key             TEXT PRIMARY KEY,
            label           TEXT NOT NULL,
            tier            INTEGER NOT NULL DEFAULT 1,
            mana_cost       INTEGER NOT NULL DEFAULT 2,
            spell_type      TEXT NOT NULL DEFAULT 'attack',
            damage_die      TEXT,
            heal_die        TEXT,
            effect_stat     TEXT,
            effect_type     TEXT,
            effect_duration INTEGER DEFAULT 1,
            target_zone     TEXT NOT NULL DEFAULT 'any',
            aoe             INTEGER NOT NULL DEFAULT 0,
            description     TEXT,
            rank2_json      TEXT,
            rank3_json      TEXT,
            is_active       INTEGER NOT NULL DEFAULT 1
        )
    """, "v2-game-config-spells")

    _exec("""
        CREATE TABLE IF NOT EXISTS character_spells (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id    INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
            spell_key       TEXT NOT NULL REFERENCES game_config_spells(key),
            rank            INTEGER NOT NULL DEFAULT 1,
            UNIQUE(character_id, spell_key)
        )
    """, "v2-character-spells")

    _exec("""
        INSERT OR IGNORE INTO game_config_spells
            (key, label, tier, mana_cost, spell_type, damage_die, heal_die, effect_stat, effect_type, effect_duration, target_zone, aoe, description, rank2_json, rank3_json) VALUES
        ('magic_bolt',      'Błysk Magiczny',    1, 2, 'attack',      '2d6', NULL,  NULL,  NULL,       1, 'any',      0, 'Strumień magicznej energii uderzający wroga.',         '{\"mana_cost\":2,\"damage_die\":\"2d8\"}',                              '{\"mana_cost\":1,\"damage_die\":\"3d6\"}'),
        ('mend_wounds',     'Rana Uleczona',      1, 2, 'heal',        NULL,  '2d6', NULL,  NULL,       1, 'self',     0, 'Magiczne leczenie ran bohatera.',                      '{\"mana_cost\":2,\"heal_die\":\"2d8\"}',                               '{\"mana_cost\":1,\"heal_die\":\"3d6\"}'),
        ('arcane_shield',   'Tarcza Arkan',       1, 2, 'defense',     NULL,  NULL,  NULL,  NULL,       1, 'self',     0, 'Magiczna tarcza zwiększająca pancerz.',                '{\"mana_cost\":2,\"ac_bonus\":4,\"duration\":1}',                      '{\"mana_cost\":1,\"ac_bonus\":4,\"duration\":2}'),
        ('sleep',           'Sen',                2, 3, 'effect',      NULL,  NULL,  'WIS', 'sleeping', 1, 'any',      0, 'Wpędza wroga w magiczny sen.',                         '{\"mana_cost\":3,\"effect_duration\":2}',                              '{\"mana_cost\":2,\"effect_duration\":3}'),
        ('burning_arc',     'Pałająca Ścieżka',  2, 4, 'attack_aoe',  '1d6', NULL,  NULL,  NULL,       1, 'any',      1, 'Łuk ognia trafia wszystkich wrogów.',                  '{\"mana_cost\":4,\"damage_die\":\"1d8\"}',                             '{\"mana_cost\":3,\"damage_die\":\"2d6\"}'),
        ('drain_life',      'Wysysanie Życia',    3, 3, 'attack',      '2d8', NULL,  NULL,  NULL,       1, 'engaged',  0, 'Wysysa życie wroga, lecząc rzucającego.',              '{\"mana_cost\":3,\"damage_die\":\"2d10\"}',                            '{\"mana_cost\":2,\"damage_die\":\"3d6\",\"heal_pct\":100}'),
        ('chain_lightning', 'Łańcuch Błyskawic', 4, 5, 'attack_aoe',  '2d6', NULL,  NULL,  NULL,       1, 'any',      0, 'Błyskawica skacząca przez do 3 wrogów.',               NULL,                                                                  NULL),
        ('stone_skin',      'Kamienna Skóra',     4, 4, 'defense',     NULL,  NULL,  NULL,  NULL,       3, 'self',     0, 'Skóra twardnieje jak kamień.',                         '{\"mana_cost\":4,\"ac_bonus\":5,\"duration\":4}',                      '{\"mana_cost\":2,\"ac_bonus\":6,\"duration\":4}'),
        ('fireball',        'Kula Ognia',         5, 6, 'attack_aoe',  '3d6', NULL,  NULL,  NULL,       1, 'any',      1, 'Ognista eksplozja niszczy wszystkich wrogów.',         NULL,                                                                  NULL)
    """, "v2-spells-seed")
    # ─────────────────────────────────────────────────────────────────────────

    # ── Knowledge Book (tips shown during travel/rest) ───────────────────────
    _exec("""
        ALTER TABLE character_spells ADD COLUMN use_count INTEGER NOT NULL DEFAULT 0
    """, "v2-character-spells-use-count")
    _exec("""
        CREATE TABLE IF NOT EXISTS knowledge_book (
            tip_key     TEXT PRIMARY KEY,
            category    TEXT NOT NULL DEFAULT 'general',
            title       TEXT NOT NULL,
            body        TEXT NOT NULL,
            is_active   INTEGER NOT NULL DEFAULT 1,
            sort_order  INTEGER NOT NULL DEFAULT 0
        )
    """, "v2-knowledge-book")
    _exec("""
        INSERT OR IGNORE INTO knowledge_book (tip_key, category, title, body, sort_order) VALUES
        ('spell_rank_progression', 'magic', 'Mistrzostwo przez praktykę',
         'Im częściej rzucasz zaklęcie, tym sprawniej je opanujesz — mana zaczyna płynąć naturalniej, a efekty stają się silniejsze. Każde udane użycie przybliża cię do kolejnego stopnia biegłości. Tier zaklęcia wpływa na to, jak długo trwa droga do pełnego mistrzostwa.',
         10),
        ('mana_system', 'magic', 'Mana i odpoczynek',
         'Uczony regeneruje całą manę po długim odpoczynku. W walce mana to jego najcenniejszy zasób — każde zaklęcie kosztuje punkty many, a gdy skończy się mana, zostają tylko pięści.',
         20),
        ('nat20_nat1', 'combat', 'Szczęście i pech w kościach',
         'Rzut 20 na k20 to zawsze sukces — krytyczne trafienie lub spektakularny wyczyn. Rzut 1 to zawsze porażka — komplikacja fabularna albo groźna pomyłka. Żaden modyfikator tego nie zmienia.',
         30),
        ('conditions_stat_mods', 'combat', 'Stany i ich wpływ na rzuty',
         'Stany bojowe (zatrucie, oślepienie, strach) bezpośrednio obniżają atrybuty — zatrute stworzenie walczy słabiej. Efekty się kumulują, więc wróg z kilkoma stanami jest poważnie osłabiony.',
         40),
        ('dc_scale', 'mechanics', 'Skala trudności',
         'Łatwe zadania to DC 8, standardowe — DC 12, trudne — DC 16, ekstremalne — DC 20, legendarne — powyżej 24. Proficiency bonus +2 jest dodawany automatycznie gdy biegłość umiejętności wynosi 3 lub więcej.',
         50),
        ('hero_persistence', 'mechanics', 'Twój bohater żyje dalej',
         'Bohater nie jest przywiązany do jednej kampanii — przeżywa ją i wraca silniejszy. Statystyki, ekwipunek, złoto i umiejętności zostają. Po zakończeniu przygody możesz wybrać nową kampanię, wejść do lochu, lub po prostu odpocząć.',
         60)
    """, "v2-knowledge-book-seed")
    _exec("""
        INSERT OR IGNORE INTO knowledge_book (tip_key, category, title, body, sort_order) VALUES
        ('dungeon_cooldown', 'exploration', 'Lochy odradzają się',
         'Po oczyszczeniu lochu wrogowie odradzają się po pewnym czasie — każde miejsce ma swój rytm. Wróć gdy minie czas odnowienia i zmierz się z nim ponownie, silniejszy niż poprzednio.',
         70)
    """, "v2-dungeon-tip")
    # ─────────────────────────────────────────────────────────────────────────

    # ── Task 41: Dungeon Runs ─────────────────────────────────────────────────
    _exec("""
        CREATE TABLE IF NOT EXISTS game_dungeons (
            key             TEXT PRIMARY KEY,
            label           TEXT NOT NULL,
            location_key    TEXT NOT NULL,
            rooms           INTEGER NOT NULL DEFAULT 5,
            enemy_pool      TEXT NOT NULL DEFAULT '[]',
            boss_enemy      TEXT,
            loot_tier       TEXT NOT NULL DEFAULT 'standard',
            atmosphere      TEXT,
            cooldown_hours  INTEGER NOT NULL DEFAULT 72,
            min_level       INTEGER NOT NULL DEFAULT 1,
            is_active       INTEGER NOT NULL DEFAULT 1
        )
    """, "v2-game-dungeons")
    _exec("""
        INSERT OR IGNORE INTO game_dungeons (key, label, location_key, rooms, enemy_pool, boss_enemy, loot_tier, atmosphere, cooldown_hours, min_level) VALUES
        ('goblin_warren',  'Nora Goblinów',     'goblin_warren',  5, '["goblin","kobold"]', 'hobgoblin',      'standard', 'Ciasne tunele, smród gnijącego mięsa, pobrzękiwanie oręża w ciemności.',              48, 1),
        ('crypt_of_bones', 'Krypta Kości',      'crypt_of_bones', 6, '["skeleton","zombie"]',      'skeleton_warrior','rich',   'Wilgotne katakumby, fosforyzujące kości, echo kroków odbija się od kamiennych ścian.', 72, 2),
        ('rat_tunnels',    'Kanały pod Miastem','rat_tunnels',    4, '["giant_rat"]',              NULL,             'poor',     'Ciemne, zawilgocone kanały. Coś tu mieszka i nie lubi gości.',                        24, 1)
    """, "v2-game-dungeons-seed")
    # ─────────────────────────────────────────────────────────────────────────

    # ── Issue #38: backfill sheet_json.level from xp_lifetime_earned ────────
    # Older characters' sheets lost the `level` key during sheet rewrites;
    # without it, every reader fell back to L1, silently under-scaling
    # dungeons, spell tiers, and HP recompute. Fill in the canonical value
    # derived from xp_lifetime_earned (calc_level formula, cap 10).
    try:
        backfill_rows = conn.execute(
            """
            SELECT id, sheet_json FROM characters
            WHERE json_extract(sheet_json, '$.level') IS NULL
               OR CAST(json_extract(sheet_json, '$.level') AS INTEGER) < 1
            """
        ).fetchall()
        for _r in backfill_rows:
            try:
                _s = json.loads(_r[1] or "{}")
                _xp = int(_s.get("xp_lifetime_earned") or 0)
                _s["level"] = min(10, _xp // 100 + 1)
                conn.execute(
                    "UPDATE characters SET sheet_json = ? WHERE id = ?",
                    (json.dumps(_s, ensure_ascii=False), _r[0]),
                )
            except Exception:
                pass
        if backfill_rows:
            conn.commit()
            logger.info("v2_migration_applied", label="v2-backfill-hero-level", count=len(backfill_rows))
    except Exception as _bf_err:
        logger.warning("v2_migration_failed", label="v2-backfill-hero-level", error=str(_bf_err))

    # ── Task 42: Character-first flow ────────────────────────────────────────
    _make_character_first_migration(conn)

    # ─────────────────────────────────────────────────────────────────────────

    _exec("""
        CREATE TABLE IF NOT EXISTS skill_counters (
            player_skill_key TEXT PRIMARY KEY,
            counter_type     TEXT NOT NULL DEFAULT 'dc',
            counter_key      TEXT,
            default_dc       INTEGER NOT NULL DEFAULT 12
        )
    """, "v2-skill-counters-table")
    _exec("""
        INSERT OR IGNORE INTO skill_counters (player_skill_key, counter_type, counter_key, default_dc) VALUES
        ('stealth',      'opposed', 'perception', 12),
        ('lockpick',     'dc',      NULL,         14),
        ('acrobatics',   'dc',      NULL,         10),
        ('perception',   'dc',      NULL,         12),
        ('insight',      'opposed', 'deception',  12),
        ('survival',     'dc',      NULL,         12),
        ('persuasion',   'opposed', 'WIS',        12),
        ('deception',    'opposed', 'insight',    12),
        ('intimidation', 'opposed', 'WIS',        12),
        ('athletics',    'dc',      NULL,         12),
        ('arcana',       'dc',      NULL,         14),
        ('medicine',     'dc',      NULL,         12),
        ('lore',         'dc',      NULL,         14)
    """, "v2-skill-counters-seed")

    _exec("""
        CREATE TABLE IF NOT EXISTS location_connections (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            from_location_key   TEXT NOT NULL,
            to_location_key     TEXT NOT NULL,
            travel_hours        REAL NOT NULL DEFAULT 1.0,
            travel_description  TEXT,
            danger_level        TEXT NOT NULL DEFAULT 'low',
            requires_item_key   TEXT DEFAULT NULL,
            requires_flag       TEXT DEFAULT NULL,
            is_bidirectional    INTEGER NOT NULL DEFAULT 1,
            is_active           INTEGER NOT NULL DEFAULT 1,
            encounter_chance    REAL NOT NULL DEFAULT 0.1,
            created_at          TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(from_location_key, to_location_key)
        )
    """, "v2-location-connections-table")

    _exec("""
        CREATE TABLE IF NOT EXISTS location_npc_assignments (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            location_key    TEXT NOT NULL,
            npc_key         TEXT NOT NULL,
            assignment_type TEXT NOT NULL DEFAULT 'resident',
            notes           TEXT,
            is_active       INTEGER NOT NULL DEFAULT 1,
            UNIQUE(location_key, npc_key)
        )
    """, "v2-location-npc-assignments-table")

    _exec("""
        CREATE TABLE IF NOT EXISTS location_enemy_assignments (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            location_key    TEXT NOT NULL,
            enemy_key       TEXT NOT NULL,
            spawn_chance    REAL NOT NULL DEFAULT 1.0,
            max_count       INTEGER NOT NULL DEFAULT 3,
            notes           TEXT,
            is_active       INTEGER NOT NULL DEFAULT 1,
            UNIQUE(location_key, enemy_key)
        )
    """, "v2-location-enemy-assignments-table")

    _exec("""
        CREATE TABLE IF NOT EXISTS character_campaign_history (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id    INTEGER NOT NULL,
            campaign_id     INTEGER NOT NULL,
            outcome         TEXT NOT NULL DEFAULT 'active',
            chapter_summary TEXT,
            xp_earned       INTEGER NOT NULL DEFAULT 0,
            gold_at_end     INTEGER NOT NULL DEFAULT 0,
            turns_count     INTEGER NOT NULL DEFAULT 0,
            completed_at    TEXT,
            created_at      TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """, "v2-character-campaign-history-table")
    _exec("CREATE INDEX IF NOT EXISTS idx_char_campaign_history ON character_campaign_history (character_id, completed_at)", "v2-char-campaign-history-idx")

    _exec("""
        CREATE TABLE IF NOT EXISTS game_config_xp_awards (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            category    TEXT NOT NULL,
            source_key  TEXT UNIQUE NOT NULL,
            label       TEXT NOT NULL,
            description TEXT,
            xp_amount   INTEGER NOT NULL DEFAULT 0,
            is_active   INTEGER NOT NULL DEFAULT 1,
            is_locked   INTEGER NOT NULL DEFAULT 0,
            locked_at   TEXT DEFAULT NULL,
            created_at  TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """, "v2-xp-awards-table")

    _exec("""
        CREATE TABLE IF NOT EXISTS character_quests (
            id                   INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id         INTEGER NOT NULL,
            campaign_id          INTEGER NOT NULL,
            quest_type           TEXT NOT NULL DEFAULT 'main',
            title                TEXT NOT NULL,
            narrative            TEXT NOT NULL DEFAULT '',
            status               TEXT NOT NULL DEFAULT 'active',
            resolution           TEXT DEFAULT NULL,
            resolution_narrative TEXT DEFAULT NULL,
            created_turn         INTEGER,
            completed_turn       INTEGER DEFAULT NULL,
            created_at           TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at           TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (character_id) REFERENCES characters(id) ON DELETE CASCADE
        )
    """, "v2-character-quests-table")
    _exec("CREATE INDEX IF NOT EXISTS idx_character_quests_active ON character_quests (character_id, status, campaign_id)", "v2-char-quests-idx")

    _exec("""
        CREATE TABLE IF NOT EXISTS character_dungeon_runs (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id    INTEGER NOT NULL,
            location_key    TEXT NOT NULL,
            cleared_at      TEXT NOT NULL,
            cooldown_until  TEXT NOT NULL,
            run_count       INTEGER NOT NULL DEFAULT 1,
            UNIQUE(character_id, location_key)
        )
    """, "v2-character-dungeon-runs-table")

    # ── ALTER TABLE: V1 cleanup ───────────────────────────────────────────

    _exec("ALTER TABLE game_config_items ADD COLUMN ac_bonus INTEGER NOT NULL DEFAULT 0", "v2-items-ac-bonus")
    # Migrate existing armor AC from effect_json into ac_bonus
    try:
        conn.execute("""
            UPDATE game_config_items
            SET ac_bonus = CAST(json_extract(effect_json, '$.stat_mods.AC') AS INTEGER)
            WHERE item_type = 'armor'
              AND json_extract(effect_json, '$.stat_mods.AC') IS NOT NULL
              AND ac_bonus = 0
        """)
        conn.commit()
        logger.info("v2_migration_applied", label="v2-items-ac-bonus-data-migrate")
    except Exception as e:
        logger.warning("v2_migration_skipped", label="v2-items-ac-bonus-data-migrate", error=str(e))

    _exec("ALTER TABLE game_config_archetypes ADD COLUMN hp_base INTEGER NOT NULL DEFAULT 10", "v2-archetypes-hp-base")
    try:
        conn.execute("UPDATE game_config_archetypes SET hp_base = 10 WHERE key = 'warrior' AND hp_base = 10")
        conn.execute("UPDATE game_config_archetypes SET hp_base = 6  WHERE key = 'scholar'")
        conn.execute("UPDATE game_config_archetypes SET hp_base = 8  WHERE key = 'ranger'")
        conn.commit()
        logger.info("v2_migration_applied", label="v2-archetypes-hp-base-seed")
    except Exception as e:
        logger.warning("v2_migration_skipped", label="v2-archetypes-hp-base-seed", error=str(e))

    _exec("ALTER TABLE game_config_consumables ADD COLUMN ai_generated INTEGER NOT NULL DEFAULT 0", "v2-consumables-ai-generated")
    _exec("ALTER TABLE game_config_consumables ADD COLUMN approved INTEGER NOT NULL DEFAULT 1", "v2-consumables-approved")

    # ── ALTER TABLE: game_locations ───────────────────────────────────────

    _exec("ALTER TABLE game_locations ADD COLUMN map_x REAL DEFAULT NULL", "v2-locations-map-x")
    _exec("ALTER TABLE game_locations ADD COLUMN map_y REAL DEFAULT NULL", "v2-locations-map-y")
    _exec("ALTER TABLE game_locations ADD COLUMN map_icon TEXT NOT NULL DEFAULT 'town'", "v2-locations-map-icon")
    _exec("ALTER TABLE game_locations ADD COLUMN visible_before_visit INTEGER NOT NULL DEFAULT 0", "v2-locations-visible-before-visit")
    _exec("ALTER TABLE game_locations ADD COLUMN safe_for_rest INTEGER NOT NULL DEFAULT 0", "v2-locations-safe-for-rest")
    _exec("ALTER TABLE game_locations ADD COLUMN review_status TEXT NOT NULL DEFAULT 'permanent'", "v2-locations-review-status")
    _exec("ALTER TABLE game_locations ADD COLUMN parent_key TEXT DEFAULT NULL", "v2-locations-parent-key")

    # Seed parent_key from parent_id
    try:
        conn.execute("""
            UPDATE game_locations
            SET parent_key = (
                SELECT key FROM game_locations p WHERE p.id = game_locations.parent_id
            )
            WHERE parent_id IS NOT NULL AND parent_key IS NULL
        """)
        conn.commit()
        logger.info("v2_migration_applied", label="v2-locations-parent-key-seed")
    except Exception as e:
        logger.warning("v2_migration_skipped", label="v2-locations-parent-key-seed", error=str(e))

    # ── Stage 2B-Schema Phase 1: provenance + reuse fields (S1–S8) ────────
    _exec("ALTER TABLE game_locations ADD COLUMN created_by TEXT NOT NULL DEFAULT 'admin_manual'", "v2-locations-created-by")
    _exec("ALTER TABLE game_locations ADD COLUMN location_subtype TEXT DEFAULT NULL", "v2-locations-subtype")
    _exec("ALTER TABLE game_locations ADD COLUMN biome TEXT DEFAULT NULL", "v2-locations-biome")
    _exec("ALTER TABLE game_locations ADD COLUMN tier INTEGER NOT NULL DEFAULT 1", "v2-locations-tier")
    _exec("ALTER TABLE game_locations ADD COLUMN canonical INTEGER NOT NULL DEFAULT 0", "v2-locations-canonical")
    _exec("ALTER TABLE game_locations ADD COLUMN usage_count INTEGER NOT NULL DEFAULT 0", "v2-locations-usage-count")
    _exec("ALTER TABLE game_locations ADD COLUMN source_campaign_id INTEGER NULL REFERENCES campaigns(id)", "v2-locations-source-campaign")
    _exec("CREATE INDEX IF NOT EXISTS idx_game_locations_biome_subtype ON game_locations(biome, location_subtype)", "v2-locations-idx-biome-subtype")
    _exec("CREATE INDEX IF NOT EXISTS idx_game_locations_canonical ON game_locations(canonical)", "v2-locations-idx-canonical")

    # Stage 2B R4: temporary sub-locations (e.g. Rozbij obóz)
    _exec("ALTER TABLE game_locations ADD COLUMN temporary INTEGER NOT NULL DEFAULT 0", "v2-locations-temporary")

    # Backfill: derive created_by + canonical from legacy ai_generated boolean.
    # Only runs if every row still has the default value (created_by='admin_manual' AND canonical=0),
    # so re-runs of the migration are safe.
    try:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM game_locations WHERE created_by != 'admin_manual' OR canonical != 0"
        ).fetchone()
        already_backfilled = row and int(row["n"] if isinstance(row, sqlite3.Row) else row[0]) > 0
        if not already_backfilled:
            conn.execute("""
                UPDATE game_locations SET
                    created_by = CASE WHEN ai_generated = 1 THEN 'gm_runtime' ELSE 'admin_manual' END,
                    canonical  = CASE WHEN review_status = 'permanent' AND ai_generated = 0 THEN 1 ELSE 0 END
            """)
            conn.commit()
            logger.info("v2_migration_applied", label="v2-locations-provenance-backfill")
        else:
            logger.debug("v2_migration_skipped", label="v2-locations-provenance-backfill", reason="already backfilled")
    except Exception as e:
        logger.warning("v2_migration_skipped", label="v2-locations-provenance-backfill", error=str(e))

    # Stage 2B-Schema fix-up: catch rows the original backfill missed because they were
    # inserted by location_validator AFTER the migration ran with stale defaults
    # (created_by='admin_manual' + review_status='permanent' on AI-generated rows).
    # Idempotent: guarded by ai_generated=1 plus default-only stamps; skipped silently
    # once no rows match.
    try:
        cur = conn.execute("""
            UPDATE game_locations
               SET created_by = 'gm_runtime'
             WHERE ai_generated = 1 AND created_by = 'admin_manual'
        """)
        n1 = cur.rowcount or 0
        cur = conn.execute("""
            UPDATE game_locations
               SET review_status = 'pending_review'
             WHERE ai_generated = 1 AND review_status = 'permanent' AND approved = 0
        """)
        n2 = cur.rowcount or 0
        if n1 or n2:
            conn.commit()
            logger.info("v2_migration_applied",
                        label="v2-locations-provenance-fixup",
                        created_by_fixed=n1, review_status_fixed=n2)
    except Exception as e:
        logger.warning("v2_migration_skipped", label="v2-locations-provenance-fixup", error=str(e))

    # Stage 2B-Schema fix-up #2: approve_entity('location') historically only flipped
    # review_status to 'permanent' but left approved=0, so the validator's
    # COALESCE(approved, 1) = 1 filter hid the row → next "move to X" auto-created
    # a duplicate. Heal the existing rows once; the bug itself is fixed in
    # world_service.approve_entity.
    try:
        cur = conn.execute("""
            UPDATE game_locations
               SET approved = 1
             WHERE review_status = 'permanent' AND approved = 0
        """)
        n = cur.rowcount or 0
        if n:
            conn.commit()
            logger.info("v2_migration_applied",
                        label="v2-locations-approved-sync",
                        approved_set=n)
    except Exception as e:
        logger.warning("v2_migration_skipped", label="v2-locations-approved-sync", error=str(e))

    # ── ALTER TABLE: npcs ─────────────────────────────────────────────────

    _exec("ALTER TABLE npcs ADD COLUMN personality_prompt TEXT DEFAULT NULL", "v2-npcs-personality-prompt")
    _exec("ALTER TABLE npcs ADD COLUMN keyword_triggers TEXT NOT NULL DEFAULT '[]'", "v2-npcs-keyword-triggers")
    _exec("ALTER TABLE npcs ADD COLUMN review_status TEXT NOT NULL DEFAULT 'permanent'", "v2-npcs-review-status")

    # ── ALTER TABLE: game_config_enemies ──────────────────────────────────

    _exec("ALTER TABLE game_config_enemies ADD COLUMN review_status TEXT NOT NULL DEFAULT 'permanent'", "v2-enemies-review-status")
    _exec("ALTER TABLE game_config_enemies ADD COLUMN behavior_profile_key TEXT DEFAULT NULL", "v2-enemies-behavior-profile-key")
    _exec("ALTER TABLE game_config_enemies ADD COLUMN hit_location_table TEXT NOT NULL DEFAULT 'standard'", "v2-enemies-hit-location-table")
    _exec("ALTER TABLE game_config_enemies ADD COLUMN fear_aura INTEGER NOT NULL DEFAULT 0", "v2-enemies-fear-aura")
    _exec("ALTER TABLE game_config_enemies ADD COLUMN fear_dc INTEGER NOT NULL DEFAULT 12", "v2-enemies-fear-dc")
    _exec("ALTER TABLE game_config_enemies ADD COLUMN skills_json TEXT NOT NULL DEFAULT '{}'", "v2-enemies-skills-json")

    # ── ALTER TABLE: game_sessions ────────────────────────────────────────

    _exec("ALTER TABLE game_sessions ADD COLUMN ingame_hours INTEGER NOT NULL DEFAULT 9", "v2-sessions-ingame-hours")

    # ── ALTER TABLE: characters ───────────────────────────────────────────

    _exec("ALTER TABLE characters ADD COLUMN hero_status TEXT NOT NULL DEFAULT 'active'", "v2-characters-hero-status")
    _exec("ALTER TABLE characters ADD COLUMN visited_location_keys TEXT NOT NULL DEFAULT '[]'", "v2-characters-visited-locations")

    # ── ALTER TABLE: character_xp_grants ─────────────────────────────────

    _exec("ALTER TABLE character_xp_grants ADD COLUMN source_key TEXT DEFAULT NULL", "v2-xp-grants-source-key")
    _exec("ALTER TABLE character_xp_grants ADD COLUMN campaign_id INTEGER DEFAULT NULL", "v2-xp-grants-campaign-id")
    _exec("ALTER TABLE character_xp_grants ADD COLUMN turn_number INTEGER DEFAULT NULL", "v2-xp-grants-turn-number")
    _exec("ALTER TABLE character_xp_grants ADD COLUMN detail TEXT DEFAULT NULL", "v2-xp-grants-detail")

    # ── Seed: game_config_xp_awards ───────────────────────────────────────

    xp_seeds = [
        ('combat', 'kill_weak',           'Zabicie słabego wroga',            'Wróg tier=weak',                                            10),
        ('combat', 'kill_standard',       'Zabicie standardowego wroga',      'Wróg tier=standard',                                        25),
        ('combat', 'kill_elite',          'Zabicie elitarnego wroga',         'Wróg tier=elite',                                           50),
        ('combat', 'kill_boss',           'Zabicie bossa',                    'Wróg tier=boss',                                           150),
        ('combat', 'death_save_survived', 'Przeżycie rzutu na śmierć',        'Po każdym przeżytym rzucie na śmierć',                      15),
        ('combat', 'outnumbered_victory', 'Zwycięstwo w przewadze (3+ wrogów)','Wszyscy wrogowie pokonani przy 3+ na starcie',             20),
        ('campaign', 'beat_complete',     'Cel kampanii ukończony',           '[BEAT_COMPLETE] tag',                                       30),
        ('campaign', 'side_quest',        'Zlecenie poboczne ukończone',      '[QUEST_COMPLETE] tag',                                      40),
        ('campaign', 'dungeon_cleared',   'Loch wyczyszczony',                '[DUNGEON_CLEAR] tag',                                       75),
        ('campaign', 'campaign_ending',   'Zakończenie kampanii',             '[CAMPAIGN_END] tag',                                       200),
        ('exploration', 'location_new',   'Odkrycie nowej lokacji',           'Pierwsza wizyta w makrolokacji',                            15),
        ('exploration', 'npc_first_talk', 'Pierwsza rozmowa z NPC',           'Pierwszy DIALOGUE z danym kluczem NPC',                      5),
        ('exploration', 'secret',         'Odkrycie sekretu / wskazówki',     '[DISCOVERY:lore_key] tag',                                  10),
        ('exploration', 'hidden_room',    'Odkrycie ukrytego przejścia',      '[DISCOVERY:secret_location] tag',                          10),
        ('skills', 'skill_dc_12',         'Test umiejętności DC 12–15',       'Sukces w teście DC w zakresie 12-15',                        3),
        ('skills', 'skill_dc_16',         'Test umiejętności DC 16–19',       'Sukces w teście DC w zakresie 16-19',                        8),
        ('skills', 'skill_dc_20',         'Test umiejętności DC 20+',         'Wyjątkowy sukces w teście',                                 15),
        ('skills', 'opposed_major_npc',   'Wygrana w teście z ważną postacią','NPC importance=critical lub supporting',                   10),
        ('narrative', 'nonviolent_solution','Rozwiązanie bez walki',          'Konflikt zakończony bez walki',                             20),
        ('narrative', 'heroic_sacrifice', 'Bohaterskie poświęcenie',          'Obrażenia przyjęte celowo dla ochrony NPC',                 25),
        ('narrative', 'clever_environment','Kreatywne użycie otoczenia',      'Nieoczekiwane rozwiązanie z użyciem otoczenia',             10),
        ('narrative', 'moral_choice',     'Trudny wybór moralny',             'Decyzja z realnym kosztem dla bohatera',                    15),
        ('narrative', 'unexpected_ally',  'Pozyskanie niespodziewanego sojusznika','Wróg przekonany do współpracy',                      10),
        ('narrative', 'major_discovery',  'Odkrycie kluczowej prawdy',        'Ważna tajemnica kampanii ujawniona',                        15),
        ('narrative', '_cap_per_session', 'Limit narracyjnych PD / sesję',    'Maksymalna kwota z kategorii narracja na sesję',            50),
        ('session', 'session_20turns',    'Sesja 20–39 tur',                  'Przyznawane przy długim odpoczynku',                        10),
        ('session', 'session_40turns',    'Sesja 40+ tur',                    'Przyznawane przy długim odpoczynku',                        20),
    ]
    for category, source_key, label, description, xp_amount in xp_seeds:
        try:
            conn.execute(
                "INSERT OR IGNORE INTO game_config_xp_awards (category, source_key, label, description, xp_amount, is_locked) VALUES (?, ?, ?, ?, ?, 1)",
                (category, source_key, label, description, xp_amount)
            )
        except Exception:
            pass
    conn.commit()
    logger.info("v2_migration_applied", label="v2-xp-awards-seed")

    # ── ALTER TABLE: campaigns (V2 plan storage) ──────────────────────────
    _exec("ALTER TABLE campaigns ADD COLUMN engine_private_json TEXT DEFAULT NULL",
          "v2-campaigns-engine-private-json")

    # ── Seed: enemy_behavior_profiles (Phase 05) ──────────────────────────
    behavior_seeds = [
        ("goblin",         "Goblin Standard",      "attack_player", 25, "throw_rock", 3, "Goblin warczy i atakuje!", "Goblin pada z cichym świstem.", 0, 0),
        ("goblin_archer",  "Goblin Archer",         "attack_player", 20, None,         0, "Goblin łucznik naciąga cięciwę!", "Goblin pada.", 0, 0),
        ("bandit",         "Bandit",                "attack_weakest",20, None,         0, "Bandyta atakuje!", "Bandyta osunął się na ziemię.", 0, 0),
        ("wolf",           "Wolf",                  "attack_player",  15, None,         0, "Wilk warczy z nisko opuszczoną głową.", "Wilk pada.", 0, 0),
        ("skeleton",       "Skeleton",              "attack_player",   0, None,         0, "Szkielet zgrzyta kośćmi.", "Kości rozsypują się.", 0, 0),
        ("orc",            "Orc",                   "attack_weakest", 10, None,         0, "Ork ryczy i szarżuje!", "Ork pada z głuchym łoskotem.", 0, 0),
        ("troll",          "Troll",                 "attack_player",   5, "regenerate", 2, "Troll ryczy — sam widok budzi grozę!", "Troll pada.", 1, 12),
        ("vampire_master", "Vampire",               "attack_player",   0, "drain_life",  3, "Wampir uśmiecha się. Zimno.", "Wampir rozpływa się w mroku.", 1, 16),
    ]
    for (key, display_name, default_action, hp_flee, special_key, special_cd,
         aggro, death, fear_aura, fear_dc) in behavior_seeds:
        try:
            conn.execute(
                """INSERT OR IGNORE INTO enemy_behavior_profiles
                   (enemy_key, default_action, hp_threshold_flee, special_ability_key,
                    special_ability_cooldown_turns, dialogue_on_aggro, dialogue_on_death,
                    fear_aura, fear_dc)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (key, default_action, hp_flee, special_key, special_cd,
                 aggro, death, fear_aura, fear_dc)
            )
        except Exception:
            pass
    conn.commit()
    logger.info("v2_migration_applied", label="v2-behavior-profiles-seed")

    # ── Task 40: Hex World Builder ────────────────────────────────────────────
    _exec("""
        CREATE TABLE IF NOT EXISTS world_hexes (
            id                          INTEGER PRIMARY KEY AUTOINCREMENT,
            q                           INTEGER NOT NULL,
            r                           INTEGER NOT NULL,
            hex_type                    TEXT NOT NULL DEFAULT 'plains',
            label                       TEXT,
            atmosphere                  TEXT,
            encounter_chance            REAL NOT NULL DEFAULT 0.15,
            encounter_pool              TEXT NOT NULL DEFAULT '[]',
            location_key                TEXT REFERENCES game_locations(key),
            discovered_in_campaign_id   INTEGER,
            created_by_gm               INTEGER NOT NULL DEFAULT 0,
            created_by_campaign_id      INTEGER,
            is_active                   INTEGER NOT NULL DEFAULT 1,
            created_at                  TEXT DEFAULT (datetime('now'))
        )
    """, "v2-world-hexes")
    # Remove duplicate (q, r) rows before creating the unique index — keep the
    # highest rowid (latest insert) per coordinate pair.
    try:
        conn.execute("""
            DELETE FROM world_hexes WHERE rowid NOT IN (
                SELECT MAX(rowid) FROM world_hexes GROUP BY q, r
            )
        """)
        conn.commit()
    except Exception:
        pass
    _exec("CREATE UNIQUE INDEX IF NOT EXISTS idx_world_hexes_coords ON world_hexes(q, r)",
          "v2-world-hexes-idx")

    _exec("""
        CREATE TABLE IF NOT EXISTS campaign_hex_data (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id         INTEGER NOT NULL,
            hex_q               INTEGER NOT NULL,
            hex_r               INTEGER NOT NULL,
            narrative_encounter TEXT,
            campaign_label      TEXT,
            campaign_notes      TEXT,
            discovered          INTEGER NOT NULL DEFAULT 0
        )
    """, "v2-campaign-hex-data")
    _exec("CREATE UNIQUE INDEX IF NOT EXISTS idx_campaign_hex_unique ON campaign_hex_data(campaign_id, hex_q, hex_r)",
          "v2-campaign-hex-idx")
    _exec("ALTER TABLE campaign_hex_data ADD COLUMN encounter_cleared INTEGER NOT NULL DEFAULT 0",
          "v2-campaign-hex-encounter-cleared")

    _exec("""
        CREATE TABLE IF NOT EXISTS hex_type_config (
            hex_type                TEXT PRIMARY KEY,
            label                   TEXT NOT NULL,
            travel_hours            REAL NOT NULL DEFAULT 1.0,
            encounter_base_chance   REAL NOT NULL DEFAULT 0.15,
            map_color               TEXT NOT NULL DEFAULT '#4a6a4a',
            map_icon                TEXT,
            is_active               INTEGER NOT NULL DEFAULT 1
        )
    """, "v2-hex-type-config")
    _exec("""
        INSERT OR IGNORE INTO hex_type_config
            (hex_type, label, travel_hours, encounter_base_chance, map_color, map_icon) VALUES
        ('road',      'Droga',     1.0, 0.05, '#c8a86c', '🛤️'),
        ('plains',    'Równiny',   1.0, 0.15, '#7a9a4a', '🌾'),
        ('forest',    'Las',       1.0, 0.30, '#2d5a2d', '🌲'),
        ('hills',     'Wzgórza',   1.0, 0.20, '#8a7a5a', '⛰️'),
        ('mountains', 'Góry',      1.0, 0.25, '#6a6a6a', '🏔️'),
        ('swamp',     'Bagno',     1.0, 0.40, '#4a5a3a', '🌿'),
        ('river',     'Rzeka',     1.0, 0.10, '#3a6a8a', '🌊'),
        ('town',      'Miasto',    0.0, 0.00, '#c8a44a', '🏘️'),
        ('dungeon',   'Loch',      0.0, 1.00, '#5a1a1a', '⚔️'),
        ('ruins',     'Ruiny',     1.0, 0.60, '#6a5a4a', '🏚️'),
        ('castle',    'Zamek',     0.0, 0.00, '#5a5a8a', '🏰'),
        ('cave',      'Jaskinia',  1.0, 0.50, '#3a3a3a', '🕳️')
    """, "v2-hex-type-config-seed")

    _exec("""
        CREATE TABLE IF NOT EXISTS hex_teleport_connections (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            from_q              INTEGER NOT NULL,
            from_r              INTEGER NOT NULL,
            to_q                INTEGER NOT NULL,
            to_r                INTEGER NOT NULL,
            travel_type         TEXT NOT NULL DEFAULT 'boat',
            travel_hours        REAL NOT NULL DEFAULT 8.0,
            encounter_chance    REAL NOT NULL DEFAULT 0.20,
            requires_item_key   TEXT DEFAULT NULL,
            label               TEXT,
            is_bidirectional    INTEGER NOT NULL DEFAULT 1,
            is_active           INTEGER NOT NULL DEFAULT 1
        )
    """, "v2-hex-teleport-connections")

    # forge_encounter_pool: links approved adventure_hooks to specific hexes
    # for biome-aware encounter injection (Option C trigger system, issue #153)
    _exec(
        "ALTER TABLE world_hexes ADD COLUMN forge_encounter_pool TEXT DEFAULT '[]'",
        "world-hexes-forge-encounter-pool",
    )

    # Step D: local submap support — map_level + parent_hex_id columns + scoped unique index
    _exec("ALTER TABLE world_hexes ADD COLUMN map_level INTEGER NOT NULL DEFAULT 0", "world-hexes-map-level")
    _exec("ALTER TABLE world_hexes ADD COLUMN parent_hex_id INTEGER REFERENCES world_hexes(id)", "world-hexes-parent-hex-id")
    # Drop old unique index on (q,r) — conflicts when local hexes reuse coords
    _exec("DROP INDEX IF EXISTS idx_world_hexes_coords", "world-hexes-drop-old-idx")
    # New unique: (q, r, parent_hex_id) — world hexes use parent_hex_id=NULL (→ -1), local hexes each have their own parent
    _exec("CREATE UNIQUE INDEX IF NOT EXISTS idx_world_hexes_qr_scope ON world_hexes(q, r, COALESCE(parent_hex_id, -1))", "world-hexes-qr-scope-idx")

    # Step E: Kuźnia hex allocation — start_hex on campaign_templates
    _exec("ALTER TABLE campaign_templates ADD COLUMN start_hex_q INTEGER", "campaign-templates-start-hex-q")
    _exec("ALTER TABLE campaign_templates ADD COLUMN start_hex_r INTEGER", "campaign-templates-start-hex-r")

    logger.info("v2_schema_migrations_complete")


def _ensure_loot_entries_full_schema(conn: sqlite3.Connection) -> None:
    """Rebuild loot_entries with consumable_key + 3-way XOR if ux_loot_entries_consumable index is missing."""
    if not conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='game_config_loot_entries'"
    ).fetchone():
        return
    if conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='index' AND name='ux_loot_entries_consumable'"
    ).fetchone():
        return
    logger.info("admin_migration_ensure_loot_entries_full_schema")
    conn.execute("PRAGMA foreign_keys=OFF")
    try:
        conn.executescript(
            """
            DROP INDEX IF EXISTS idx_loot_entries_table;
            DROP INDEX IF EXISTS ux_loot_entries_item;
            DROP INDEX IF EXISTS ux_loot_entries_consumable;
            DROP INDEX IF EXISTS ux_loot_entries_weapon;
            CREATE TABLE game_config_loot_entries_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                loot_table_key TEXT NOT NULL REFERENCES game_config_loot_tables(key) ON DELETE CASCADE,
                item_key TEXT REFERENCES game_config_items(key) ON DELETE CASCADE,
                consumable_key TEXT REFERENCES game_config_consumables(key) ON DELETE CASCADE,
                weapon_key TEXT REFERENCES game_config_weapons(key) ON DELETE CASCADE,
                weight INTEGER NOT NULL DEFAULT 10,
                qty_min INTEGER NOT NULL DEFAULT 1,
                qty_max INTEGER NOT NULL DEFAULT 1,
                CHECK (
                    (CASE WHEN item_key IS NOT NULL THEN 1 ELSE 0 END)
                  + (CASE WHEN consumable_key IS NOT NULL THEN 1 ELSE 0 END)
                  + (CASE WHEN weapon_key IS NOT NULL THEN 1 ELSE 0 END) = 1
                )
            );
            INSERT INTO game_config_loot_entries_new
                (id, loot_table_key, item_key, consumable_key, weapon_key, weight, qty_min, qty_max)
            SELECT id, loot_table_key, item_key, NULL,
                   CASE WHEN typeof(weapon_key) = 'null' THEN NULL ELSE weapon_key END,
                   weight, qty_min, qty_max
            FROM game_config_loot_entries
            WHERE item_key IS NOT NULL OR weapon_key IS NOT NULL;
            DROP TABLE game_config_loot_entries;
            ALTER TABLE game_config_loot_entries_new RENAME TO game_config_loot_entries;
            CREATE INDEX IF NOT EXISTS idx_loot_entries_table
                ON game_config_loot_entries(loot_table_key);
            CREATE UNIQUE INDEX IF NOT EXISTS ux_loot_entries_item
                ON game_config_loot_entries(loot_table_key, item_key) WHERE item_key IS NOT NULL;
            CREATE UNIQUE INDEX IF NOT EXISTS ux_loot_entries_consumable
                ON game_config_loot_entries(loot_table_key, consumable_key) WHERE consumable_key IS NOT NULL;
            CREATE UNIQUE INDEX IF NOT EXISTS ux_loot_entries_weapon
                ON game_config_loot_entries(loot_table_key, weapon_key) WHERE weapon_key IS NOT NULL;
            """
        )
        conn.commit()
    finally:
        conn.execute("PRAGMA foreign_keys=ON")


def _ensure_dungeon_v2_schema(conn: sqlite3.Connection) -> None:
    """Dungeon V2: room types, riddle bank, loot tiers, source_exclusive on items/weapons."""
    # game_dungeons new columns
    for sql in [
        "ALTER TABLE game_dungeons ADD COLUMN chest_loot_table_key TEXT",
        "ALTER TABLE game_dungeons ADD COLUMN boss_loot_table_key TEXT",
        "ALTER TABLE game_dungeons ADD COLUMN room_loot_chance REAL NOT NULL DEFAULT 0.15",
        "ALTER TABLE game_dungeons ADD COLUMN room_types_json TEXT NOT NULL DEFAULT '{\"combat\":50,\"chest\":15,\"trap\":15,\"riddle\":10,\"rest\":10}'",
        "ALTER TABLE game_dungeons ADD COLUMN riddle_source TEXT NOT NULL DEFAULT 'database'",
        "ALTER TABLE game_dungeons ADD COLUMN riddle_max_hints INTEGER NOT NULL DEFAULT 2",
    ]:
        try:
            conn.execute(sql); conn.commit()
        except sqlite3.OperationalError as e:
            if "duplicate column" not in str(e).lower(): raise

    # source_exclusive on items and weapons
    for sql in [
        "ALTER TABLE game_config_items ADD COLUMN source_exclusive TEXT DEFAULT NULL",
        "ALTER TABLE game_config_weapons ADD COLUMN source_exclusive TEXT DEFAULT NULL",
    ]:
        try:
            conn.execute(sql); conn.commit()
        except sqlite3.OperationalError as e:
            if "duplicate column" not in str(e).lower(): raise

    # Riddle bank table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS game_config_riddles (
            key          TEXT PRIMARY KEY,
            text         TEXT NOT NULL,
            answer       TEXT NOT NULL,
            answer_alts  TEXT NOT NULL DEFAULT '[]',
            hints        TEXT NOT NULL DEFAULT '[]',
            difficulty   INTEGER NOT NULL DEFAULT 1,
            theme        TEXT NOT NULL DEFAULT 'general',
            is_active    INTEGER NOT NULL DEFAULT 1,
            created_at   TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.commit()

    # game_config_meta: dungeon settings
    conn.execute(
        "INSERT OR IGNORE INTO game_config_meta (key, value) VALUES ('dungeon_death_hp_mode', 'campaign_state')"
    )
    conn.execute(
        "INSERT OR IGNORE INTO game_config_meta (key, value) VALUES ('dungeon_riddle_max_hints', '2')"
    )
    conn.commit()

    # Seed riddles if none exist
    riddle_count = conn.execute("SELECT COUNT(*) FROM game_config_riddles").fetchone()[0]
    if riddle_count == 0:
        riddles = [
            ("riddle_shadow", "Podążam za tobą w dzień, znikam w nocy. Czym jestem?", "cień",
             '["shadow","twój cień","mój cień"]', '["Jestem czarny","Znikam gdy nie ma słońca","To twój..."]', 1, "general"),
            ("riddle_echo", "Mówię wszystko co powiesz, a nie mam ust. Czym jestem?", "echo",
             '["głos","echo głosu"]', '["Mieszkam w górach i jaskiniach","Powtarzam twoje słowa","Nie mam ciała"]', 1, "dungeon"),
            ("riddle_fire", "Jem i rosnę, ale woda mnie zabija. Czym jestem?", "ogień",
             '["płomień","fire","żar"]', '["Świecę w ciemności","Potrzebuję drewna","Gasisz mnie wodą"]', 1, "dungeon"),
            ("riddle_time", "Stale idę naprzód, nie można mnie cofnąć. Czym jestem?", "czas",
             '["upływ czasu","godziny","wieczność"]', '["Wszystko niszczę","Królowie się mnie boją","Nie mam początku ani końca"]', 2, "magic"),
            ("riddle_key", "Mam zęby, ale nie gryzę. Czym jestem?", "klucz",
             '["klucz do drzwi","zamkowy klucz"]', '["Otwieram zamki","Noszę mnie przy pasie","Bez mnie drzwi pozostają zamknięte"]', 1, "dungeon"),
            ("riddle_death", "Bogaci go pragną, biedni go mają, a zniszczy tego kto je spożyje. Czym jestem?", "nic",
             '["nicość","pustka","zero"]', '["Bogaci chcą więcej tego czego nie mają","Biedni nic nie mają","Jeśli to zjesz..."]', 3, "death"),
            ("riddle_river", "Zawsze biegnę, a nóg nie mam. Czym jestem?", "rzeka",
             '["woda","strumień","potok"]', '["Mam brzegi","Płynę do morza","Możesz mnie przepłynąć"]', 1, "nature"),
            ("riddle_mirror", "Pokazuję twarz, ale nią nie jestem. Czym jestem?", "lustro",
             '["zwierciadło","odbicie"]', '["Odbijam światło","Znajdziesz mnie w komnacie","Odwracam lewo i prawo"]', 2, "magic"),
            ("riddle_book", "Mam wiele historii, lecz ust nie mam. Czym jestem?", "księga",
             '["książka","tom","pergamin","pismo"]', '["Mam strony","Możesz mnie czytać","Noszę wiedzę"]', 1, "magic"),
            ("riddle_night", "Im więcej mnie zabierasz, tym większy się staję. Czym jestem?", "dół",
             '["dziura","jama","wykop"]', '["Kopiesz mnie w ziemi","Chowasz mnie w ziemi","Wyrasta ze mnie coraz więcej"]', 2, "dungeon"),
            ("riddle_bones", "Żywych niosę, umarłym nie służę. Czym jestem?", "statek",
             '["łódź","okręt","tratwa"]', '["Pływam po wodzie","Przewożę ludzi","Rozsypuję się gdy umrę"]', 2, "death"),
            ("riddle_sword", "Tnę bez ostrzy, jestem ostry lecz nie ze stali. Czym jestem?", "wiatr",
             '["wicher","podmuch","burza"]', '["Nie mam ciała","Możesz mnie poczuć ale nie dotknąć","Poruszam drzewami"]', 2, "nature"),
        ]
        for r in riddles:
            try:
                conn.execute(
                    "INSERT OR IGNORE INTO game_config_riddles (key,text,answer,answer_alts,hints,difficulty,theme) VALUES (?,?,?,?,?,?,?)",
                    r
                )
            except Exception:
                pass
        conn.commit()
        logger.info("admin_migration_dungeon_v2_riddles_seeded", count=len(riddles))

    logger.info("admin_migration_dungeon_v2_schema_done")


def _ensure_narrative_items_schema(conn: sqlite3.Connection) -> None:
    """T46: narrative items stored in character_inventory; narrative weapons in game_config_weapons."""
    # character_inventory.label for free-form narrative item names
    try:
        conn.execute("ALTER TABLE character_inventory ADD COLUMN label TEXT DEFAULT NULL")
        conn.commit()
        logger.info("admin_migration_t46_character_inventory_label")
    except sqlite3.OperationalError as e:
        if "duplicate column" not in str(e).lower():
            raise

    # game_config_weapons.campaign_id for campaign-scoped narrative weapons
    try:
        conn.execute(
            "ALTER TABLE game_config_weapons ADD COLUMN campaign_id INTEGER REFERENCES campaigns(id) ON DELETE SET NULL"
        )
        conn.commit()
        logger.info("admin_migration_t46_weapons_campaign_id")
    except sqlite3.OperationalError as e:
        if "duplicate column" not in str(e).lower():
            raise

    # game_config_weapons.review_status mirrors world entity review pipeline
    try:
        conn.execute("ALTER TABLE game_config_weapons ADD COLUMN review_status TEXT DEFAULT 'permanent'")
        conn.commit()
        logger.info("admin_migration_t46_weapons_review_status")
    except sqlite3.OperationalError as e:
        if "duplicate column" not in str(e).lower():
            raise

    # Migrate existing sheet_json.narrative_items → character_inventory rows
    try:
        chars = conn.execute(
            "SELECT id, sheet_json FROM characters WHERE is_active = 1"
        ).fetchall()
        migrated = 0
        for char in chars:
            try:
                sheet = __import__("json").loads(char["sheet_json"] or "{}")
            except Exception:
                continue
            old_items = sheet.get("narrative_items")
            if not old_items or not isinstance(old_items, list):
                continue
            for entry in old_items:
                if not isinstance(entry, dict):
                    continue
                label = str(entry.get("label") or "").strip()
                if not label:
                    continue
                meta = {"item_type": "narrative"}
                if entry.get("given_at"):
                    meta["given_at"] = str(entry["given_at"])
                conn.execute(
                    """INSERT OR IGNORE INTO character_inventory
                       (character_id, label, item_key, weapon_key, consumable_key,
                        quantity, equipped, source, meta_json)
                       VALUES (?, ?, NULL, NULL, NULL, 1, 0, ?, ?)""",
                    (char["id"], label, str(entry.get("source") or "gm"),
                     __import__("json").dumps(meta, ensure_ascii=False))
                )
                migrated += 1
            # Clear migrated array
            sheet["narrative_items"] = []
            conn.execute(
                "UPDATE characters SET sheet_json = ? WHERE id = ?",
                (__import__("json").dumps(sheet, ensure_ascii=False), char["id"]),
            )
        if migrated:
            conn.commit()
            logger.info("admin_migration_t46_narrative_items_migrated", count=migrated)
    except Exception as e:
        logger.warning("admin_migration_t46_narrative_items_migrate_failed", error=str(e))


def _ensure_knowledge_book_v2(conn: sqlite3.Connection) -> None:
    """KW1 — add icon and related_command columns to knowledge_book."""
    for sql in [
        "ALTER TABLE knowledge_book ADD COLUMN icon TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE knowledge_book ADD COLUMN related_command TEXT NOT NULL DEFAULT ''",
    ]:
        try:
            conn.execute(sql)
            conn.commit()
        except Exception as e:
            if "duplicate column" in str(e).lower():
                pass
            else:
                logger.warning("knowledge_book_v2_migration_warning", error=str(e))


def _ensure_auth_ux_schema(conn: sqlite3.Connection) -> None:
    """Stage 11-C — invite system, email verification, password reset, friends, onboarding."""
    stmts = [
        # New columns on users
        "ALTER TABLE users ADD COLUMN email TEXT",
        "ALTER TABLE users ADD COLUMN invited_by_user_id INTEGER REFERENCES users(id)",
        "ALTER TABLE users ADD COLUMN email_verified_at TEXT",
        "ALTER TABLE users ADD COLUMN onboarded_at TEXT",
        "ALTER TABLE users ADD COLUMN invite_weekly_limit INTEGER NOT NULL DEFAULT 3",
        "ALTER TABLE users ADD COLUMN avatar_url TEXT",
        # F1.2 — soft-delete with 7-day grace period. NULL = active account.
        "ALTER TABLE users ADD COLUMN deleted_at TEXT",
        # Invite records
        """
        CREATE TABLE IF NOT EXISTS user_invites (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            code        TEXT    NOT NULL UNIQUE,
            created_by  INTEGER NOT NULL REFERENCES users(id),
            email       TEXT,
            message     TEXT,
            accepted_by INTEGER REFERENCES users(id),
            created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
            expires_at  TEXT    NOT NULL,
            used_at     TEXT
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_user_invites_code ON user_invites(code)",
        "CREATE INDEX IF NOT EXISTS idx_user_invites_creator ON user_invites(created_by)",
        # Email verification tokens
        """
        CREATE TABLE IF NOT EXISTS email_verification_tokens (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL REFERENCES users(id),
            token      TEXT    NOT NULL UNIQUE,
            expires_at TEXT    NOT NULL,
            used_at    TEXT
        )
        """,
        # Password reset tokens
        """
        CREATE TABLE IF NOT EXISTS password_reset_tokens (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL REFERENCES users(id),
            token      TEXT    NOT NULL UNIQUE,
            expires_at TEXT    NOT NULL,
            used_at    TEXT
        )
        """,
        # Friends (foundation for multiplayer — F1.3)
        # Convention: user_a_id < user_b_id (canonical pair). requester_id is whichever
        # of the two initiated the relationship (used for pending → accept routing,
        # and to identify the blocker on status='blocked').
        """
        CREATE TABLE IF NOT EXISTS user_friendships (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_a_id  INTEGER NOT NULL REFERENCES users(id),
            user_b_id  INTEGER NOT NULL REFERENCES users(id),
            status     TEXT    NOT NULL DEFAULT 'pending',
            created_at TEXT    NOT NULL DEFAULT (datetime('now')),
            UNIQUE(user_a_id, user_b_id)
        )
        """,
        # F1.3 — extra columns on user_friendships (idempotent ALTERs)
        "ALTER TABLE user_friendships ADD COLUMN requester_id INTEGER REFERENCES users(id)",
        "ALTER TABLE user_friendships ADD COLUMN responded_at TEXT",
        # SMTP + registration config keys (seeded with empty defaults into game_config_meta)
        "INSERT OR IGNORE INTO game_config_meta(key, value) VALUES ('smtp_host', '')",
        "INSERT OR IGNORE INTO game_config_meta(key, value) VALUES ('smtp_port', '587')",
        "INSERT OR IGNORE INTO game_config_meta(key, value) VALUES ('smtp_username', '')",
        "INSERT OR IGNORE INTO game_config_meta(key, value) VALUES ('smtp_password', '')",
        "INSERT OR IGNORE INTO game_config_meta(key, value) VALUES ('smtp_from_name', 'AI-GM')",
        "INSERT OR IGNORE INTO game_config_meta(key, value) VALUES ('smtp_from_address', '')",
        "INSERT OR IGNORE INTO game_config_meta(key, value) VALUES ('smtp_use_tls', 'true')",
        "INSERT OR IGNORE INTO game_config_meta(key, value) VALUES ('registration_open', 'false')",
    ]
    for sql in stmts:
        try:
            conn.execute(sql)
            conn.commit()
        except Exception as e:
            msg = str(e).lower()
            if "already exists" in msg or "duplicate column" in msg or "unique constraint" in msg:
                pass
            else:
                logger.warning("auth_ux_migration_warning", sql_preview=sql.strip()[:80], error=str(e))


def _ensure_j3_summary_interval(conn: sqlite3.Connection) -> None:
    """J3 — lower auto-ensure summary interval from 20 → 10 narrative turns.
    Only updates when the old default (20) is still in place; admin overrides untouched."""
    try:
        conn.execute(
            "UPDATE game_config_meta SET value = '10' "
            "WHERE key = 'summary_auto_ensure_every_n_narrative_turns' AND value = '20'"
        )
        conn.commit()
    except Exception as e:
        logger.warning("j3_summary_interval_migration_failed", error=str(e))


def _ensure_campaign_known_npcs(conn: sqlite3.Connection) -> None:
    """BUG-03 — per-campaign roster of NPCs the party has met.

    Lightweight "have-met" layer linked to the global `npcs` catalog where
    possible. Stores ephemeral relationship state (notes, disposition) and
    first-meet metadata. The MG context-injector reads the most recently
    updated 10 rows per campaign to keep NPC consistency between turns.
    """
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS campaign_known_npcs (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id         INTEGER NOT NULL,
            npc_id              INTEGER,
            npc_name            TEXT NOT NULL,
            role                TEXT,
            first_met_location  TEXT,
            first_met_turn      INTEGER,
            notes               TEXT,
            relation_status     TEXT NOT NULL DEFAULT 'neutral'
                                  CHECK (relation_status IN ('friendly', 'neutral', 'hostile')),
            created_at          TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at          TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(campaign_id, npc_name)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_campaign_known_npcs_recent "
        "ON campaign_known_npcs(campaign_id, updated_at DESC)"
    )
    conn.commit()
    # Task 8: shop reputation — purchase_count column
    try:
        conn.execute(
            "ALTER TABLE campaign_known_npcs ADD COLUMN purchase_count INTEGER NOT NULL DEFAULT 0"
        )
        conn.commit()
    except sqlite3.OperationalError:
        pass  # already exists


def _ensure_hex_spawn_weights(conn: sqlite3.Connection) -> None:
    """Add spawn_weight to hex_type_config and set realistic defaults."""
    try:
        conn.execute("ALTER TABLE hex_type_config ADD COLUMN spawn_weight INTEGER NOT NULL DEFAULT 0")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # already exists
    weights = {
        "plains": 30, "forest": 25, "hills": 15, "mountains": 10,
        "swamp": 7, "ruins": 6, "river": 4, "road": 5, "cave": 3,
        "dungeon": 1, "town": 2, "castle": 1,
    }
    for hex_type, w in weights.items():
        conn.execute(
            "UPDATE hex_type_config SET spawn_weight = ? WHERE hex_type = ? AND spawn_weight = 0",
            (w, hex_type),
        )
    conn.commit()


def _ensure_rogue_archetype(conn: sqlite3.Connection) -> None:
    """BUG-08: add Rogue archetype if missing (so new rogues get a proper starter kit)."""
    starter_items = json.dumps([
        {"weapon_key": "dagger"},
        {"weapon_key": "shortbow"},
        {"item_key": "lockpicks"},
        {"item_key": "rope_10m"},
        {"item_key": "torch", "quantity": 2},
        {"item_key": "ration_trail", "quantity": 3},
        {"item_key": "leather_armor"},
    ], ensure_ascii=False)
    try:
        conn.execute(
            """INSERT OR IGNORE INTO game_config_archetypes
               (key, label, description, starter_items_json, starter_gold_gp, hp_base)
               VALUES ('rogue', 'Łotr',
                       'Mistrz skradania, podstępu i otwierania zamków. Zwinny, ostrożny, polega na łucznictwie z dystansu i sztylecie z bliska.',
                       ?, 8, 8)""",
            (starter_items,),
        )
        conn.commit()
    except sqlite3.OperationalError as e:
        logger.warning("rogue_archetype_seed_failed", error=str(e))


def _ensure_rarity_loot_scaling(conn: sqlite3.Connection) -> None:
    """Task 7 — Add rare/epic catalog items to boss/elite loot tables.

    Rare items seeded:
      - silent_guardian_blade  (rarity=3, weapon, 75gp) → boss tables w=8, elite w=5
      - silent_guardian_helm   (rarity=3, item/armor, 45gp) → boss tables w=6, elite w=4
      - ruin_explorer_cloak    (rarity=2, item/armor, 60gp) → elite tables w=6
      - umbravale_explorer_bow (rarity=2, weapon, 50gp) → elite tables w=5
      - forgotten_sage_staff   (rarity=4, weapon, 200gp) → boss tables only w=3

    Idempotent: skips if entry already exists for (loot_table_key, key).
    """
    # --- verify catalog items exist before inserting ---
    def _weapon_exists(key: str) -> bool:
        r = conn.execute(
            "SELECT 1 FROM game_config_weapons WHERE key=? AND COALESCE(is_active,1)=1",
            (key,),
        ).fetchone()
        return r is not None

    def _item_exists(key: str) -> bool:
        r = conn.execute(
            "SELECT 1 FROM game_config_items WHERE key=? AND COALESCE(is_active,1)=1",
            (key,),
        ).fetchone()
        return r is not None

    boss_weapon_guards = {
        "silent_guardian_blade": (8, _weapon_exists("silent_guardian_blade"), "weapon_key"),
        "forgotten_sage_staff": (3, _weapon_exists("forgotten_sage_staff"), "weapon_key"),
    }
    boss_item_guards = {
        "silent_guardian_helm": (6, _item_exists("silent_guardian_helm"), "item_key"),
    }
    elite_weapon_guards = {
        "silent_guardian_blade": (5, _weapon_exists("silent_guardian_blade"), "weapon_key"),
        "umbravale_explorer_bow": (5, _weapon_exists("umbravale_explorer_bow"), "weapon_key"),
    }
    elite_item_guards = {
        "silent_guardian_helm": (4, _item_exists("silent_guardian_helm"), "item_key"),
        "ruin_explorer_cloak": (6, _item_exists("ruin_explorer_cloak"), "item_key"),
    }

    boss_tables = conn.execute(
        """
        SELECT DISTINCT loot_table_key FROM game_config_enemies
        WHERE tier='boss' AND loot_table_key IS NOT NULL AND COALESCE(is_active,1)=1
        """
    ).fetchall()
    elite_tables = conn.execute(
        """
        SELECT DISTINCT loot_table_key FROM game_config_enemies
        WHERE tier='elite' AND loot_table_key IS NOT NULL AND COALESCE(is_active,1)=1
        """
    ).fetchall()

    def _seed_entry(tbl_key: str, col: str, item_key: str, weight: int) -> None:
        exists = conn.execute(
            f"SELECT 1 FROM game_config_loot_entries WHERE loot_table_key=? AND {col}=?",
            (tbl_key, item_key),
        ).fetchone()
        if exists:
            return
        conn.execute(
            f"INSERT INTO game_config_loot_entries (loot_table_key, {col}, weight) VALUES (?,?,?)",
            (tbl_key, item_key, weight),
        )

    for (tbl_key,) in boss_tables:
        for ikey, (w, ok, col) in {**boss_weapon_guards, **boss_item_guards}.items():
            if not ok:
                continue
            _seed_entry(tbl_key, col, ikey, w)

    for (tbl_key,) in elite_tables:
        for ikey, (w, ok, col) in {**elite_weapon_guards, **elite_item_guards}.items():
            if not ok:
                continue
            _seed_entry(tbl_key, col, ikey, w)

    conn.commit()
    logger.info("admin_migration_applied", label="rarity-loot-scaling-task7")


def _ensure_game_locations_hex_linkage(conn: sqlite3.Connection) -> None:
    """Add hex-linkage columns to game_locations and seed generic locations per terrain type."""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(game_locations)").fetchall()}
    new_cols = [
        ("world_hex_q", "INTEGER"),
        ("world_hex_r", "INTEGER"),
        ("local_hex_q", "INTEGER"),
        ("local_hex_r", "INTEGER"),
        ("is_generic", "INTEGER NOT NULL DEFAULT 0"),
        ("hex_type_key", "TEXT"),
    ]
    changed = False
    for col, defn in new_cols:
        if col not in cols:
            conn.execute(f"ALTER TABLE game_locations ADD COLUMN {col} {defn}")
            changed = True
    if changed:
        conn.commit()
    # Seed generic locations for all terrain types that don't have one yet
    terrain_types = conn.execute(
        "SELECT hex_type, label FROM hex_type_config"
    ).fetchall()
    for t in terrain_types:
        key = f"generic_{t['hex_type']}"
        conn.execute(
            """INSERT OR IGNORE INTO game_locations
               (key, label, description, location_type, is_active,
                review_status, is_generic, hex_type_key, created_by)
               VALUES (?, ?, ?, 'sub', 1, 'approved', 1, ?, 'seed')""",
            (key, t["label"],
             f"Domyślna lokacja terenu: {t['label']}", t["hex_type"]),
        )
    conn.commit()
    logger.info("admin_migration_applied", label="game-locations-hex-linkage")


def run_admin_migrations() -> None:
    db_dir = os.path.dirname(DB_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")

    try:
        for sql in ADMIN_MIGRATIONS:
            try:
                conn.execute(sql)
                conn.commit()
                logger.info(
                    "admin_migration_applied",
                    sql_preview=sql.strip().splitlines()[0],
                )
            except sqlite3.OperationalError as e:
                msg = str(e).lower()
                if "already exists" in msg or "duplicate column" in msg:
                    logger.info(
                        "admin_migration_skipped",
                        sql_preview=sql.strip().splitlines()[0],
                        reason=str(e),
                    )
                else:
                    logger.error(
                        "admin_migration_error",
                        sql_preview=sql.strip().splitlines()[0],
                        error_message=str(e),
                    )

        _ensure_active_combat_location_tag(conn)
        _ensure_active_combat_loot_pool(conn)

        _rebuild_loot_entries_for_consumable_support(conn)
        _upgrade_loot_entries_three_way_xor(conn)
        _ensure_loot_entries_full_schema(conn)
        _finalize_phase_8h_items_schema(conn)
        _finalize_t25_effect_json_schema(conn)
        _finalize_phase_8h_loot_entries(conn)

        for sql in ADMIN_SEEDS:
            try:
                conn.execute(sql)
                conn.commit()
                logger.info(
                    "admin_migration_seeded",
                    sql_preview=sql.strip().splitlines()[0],
                )
            except sqlite3.OperationalError as e:
                msg = str(e).lower()
                if "already exists" in msg or "duplicate column" in msg:
                    logger.info(
                        "admin_migration_seeded_skipped",
                        sql_preview=sql.strip().splitlines()[0],
                        reason=str(e),
                    )
                elif "no such table" in msg or "no such column" in msg:
                    # Schema not yet created (e.g. restored from older backup).
                    # _run_v2_schema_migrations below will create it; next
                    # startup the seed will run successfully.
                    logger.warning(
                        "admin_seed_deferred",
                        sql_preview=sql.strip().splitlines()[0],
                        reason=str(e),
                    )
                else:
                    raise

        _migrate_legacy_archetype_json(conn)
        _ensure_campaign_ai_summaries_audience(conn)
        _ensure_enemy_loot_table_and_drop_chance(conn)
        _backfill_enemy_loot_tables(conn)
        _ensure_user_llm_settings_mode(conn)
        _run_v2_schema_migrations(conn)
        _ensure_dungeon_v2_schema(conn)
        _ensure_narrative_items_schema(conn)
        _ensure_auth_ux_schema(conn)
        _ensure_knowledge_book_v2(conn)
        _ensure_j3_summary_interval(conn)
        _ensure_hex_spawn_weights(conn)
        _ensure_campaign_known_npcs(conn)
        _ensure_rogue_archetype(conn)
        _allow_nullable_campaign_model_id(conn)
        _ensure_adventure_forge_cleanup(conn)
        _ensure_rarity_loot_scaling(conn)
        _ensure_character_rentals(conn)
        _ensure_hex_has_submap(conn)
        _ensure_game_locations_hex_linkage(conn)
        _ensure_is_tester_column(conn)
        _ensure_bug_reports_table(conn)
        _ensure_bug_reports_github_status(conn)
        _ensure_bug_reports_report_type(conn)
        _ensure_push_subscriptions_table(conn)
        _ensure_campaign_rounds_tables(conn)
        _ensure_multiplayer_lobby_schema(conn)
        _ensure_party_chat_table(conn)
    finally:
        conn.close()

    logger.info("admin_migration_complete", phase="14.5")


def _ensure_character_rentals(conn: sqlite3.Connection) -> None:
    """Task 9 — per-character rental records for borrowed shop items."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS character_rentals (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id    INTEGER NOT NULL,
            campaign_id     INTEGER,
            npc_id          INTEGER NOT NULL,
            item_type       TEXT NOT NULL,
            item_key        TEXT NOT NULL,
            label           TEXT NOT NULL DEFAULT '',
            rental_fee_gp   INTEGER NOT NULL,
            total_paid_gp   INTEGER NOT NULL,
            duration_turns  INTEGER NOT NULL,
            rented_at_turn  INTEGER NOT NULL DEFAULT 0,
            expires_at_turn INTEGER NOT NULL,
            inventory_id    INTEGER,
            status          TEXT NOT NULL DEFAULT 'active'
                              CHECK (status IN ('active', 'returned', 'expired')),
            created_at      TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_character_rentals_active "
        "ON character_rentals(character_id, npc_id, status)"
    )
    conn.commit()


def _ensure_adventure_forge_cleanup(conn: sqlite3.Connection) -> None:
    """Drop legacy Projektant + Bank Pomysłów tables replaced by Kuźnia."""
    for table in ("campaign_snippets", "campaign_ideas"):
        try:
            conn.execute(f"DROP TABLE IF EXISTS {table}")
            conn.commit()
            logger.info("admin_migration_applied", label=f"drop-legacy-{table}")
        except Exception as e:
            logger.warning("admin_migration_skipped", label=f"drop-legacy-{table}", error=str(e))


def _allow_nullable_campaign_model_id(conn: sqlite3.Connection) -> None:
    """Remove NOT NULL constraint from campaigns.model_id.

    NULL means "use whatever the active global preset specifies". A non-NULL
    value pins that specific model name for the campaign (legacy / deliberate
    per-campaign override). This is an idempotent table-recreation migration
    because SQLite does not support ALTER COLUMN to drop constraints.
    """
    cols = conn.execute("PRAGMA table_info(campaigns)").fetchall()
    model_col = next((c for c in cols if c["name"] == "model_id"), None)
    if model_col is None or model_col["notnull"] == 0:
        return  # already nullable or column missing
    col_names = [c["name"] for c in cols]
    cols_csv = ", ".join(col_names)
    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS _campaigns_migration_tmp (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                system_id TEXT NOT NULL,
                model_id TEXT,
                owner_user_id INTEGER NOT NULL,
                language TEXT NOT NULL DEFAULT 'pl',
                mode TEXT NOT NULL DEFAULT 'solo',
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                death_reason TEXT,
                ended_at TEXT,
                epitaph TEXT,
                gm_plan_json TEXT NOT NULL DEFAULT '{}',
                last_rollup_narrative_turn_count INTEGER,
                engine_private_json TEXT DEFAULT NULL,
                FOREIGN KEY (owner_user_id) REFERENCES users(id)
            )
        """)
        conn.execute(f"INSERT INTO _campaigns_migration_tmp ({cols_csv}) SELECT {cols_csv} FROM campaigns")
        conn.execute("DROP TABLE campaigns")
        conn.execute("ALTER TABLE _campaigns_migration_tmp RENAME TO campaigns")
        conn.commit()
        logger.info("admin_migration_campaign_model_id_nullable")
    finally:
        conn.execute("PRAGMA foreign_keys = ON")


def _ensure_hex_has_submap(conn: sqlite3.Connection) -> None:
    """Add has_submap flag to hex_type_config and seed defaults for types that support local maps."""
    cols = [r[1] for r in conn.execute("PRAGMA table_info(hex_type_config)").fetchall()]
    if "has_submap" not in cols:
        conn.execute("ALTER TABLE hex_type_config ADD COLUMN has_submap INTEGER NOT NULL DEFAULT 0")
        # Seed has_submap=1 for types that should support local map zoom-in
        conn.execute(
            "UPDATE hex_type_config SET has_submap = 1 WHERE hex_type IN (?, ?, ?, ?, ?, ?, ?)",
            ("town", "castle", "ruins", "cave", "dungeon", "temple", "dungeon"),
        )
        conn.commit()
        logger.info("admin_migration_applied", label="hex-has-submap")


def _ensure_is_tester_column(conn: sqlite3.Connection) -> None:
    """Add is_tester flag to users table for beta tester bug reporting."""
    cols = [r[1] for r in conn.execute("PRAGMA table_info(users)").fetchall()]
    if "is_tester" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN is_tester INTEGER NOT NULL DEFAULT 0")
        conn.commit()
        logger.info("admin_migration_applied", label="users-is-tester")


def _ensure_bug_reports_table(conn: sqlite3.Connection) -> None:
    """Create bug_reports table for tester submissions."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS bug_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            campaign_id INTEGER,
            observation TEXT NOT NULL,
            reproduction TEXT,
            context_json TEXT,
            github_issue_url TEXT,
            github_issue_number INTEGER,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    logger.info("admin_migration_applied", label="bug-reports-table")


def _ensure_bug_reports_github_status(conn: sqlite3.Connection) -> None:
    cols = [r[1] for r in conn.execute("PRAGMA table_info(bug_reports)").fetchall()]
    if "github_status" not in cols:
        conn.execute("ALTER TABLE bug_reports ADD COLUMN github_status TEXT")
        conn.commit()
        logger.info("admin_migration_applied", label="bug-reports-github-status")


def _ensure_bug_reports_report_type(conn: sqlite3.Connection) -> None:
    cols = [r[1] for r in conn.execute("PRAGMA table_info(bug_reports)").fetchall()]
    if "report_type" not in cols:
        conn.execute("ALTER TABLE bug_reports ADD COLUMN report_type TEXT NOT NULL DEFAULT 'bug'")
        conn.commit()
        logger.info("admin_migration_applied", label="bug-reports-report-type")


def _ensure_campaign_rounds_tables(conn: sqlite3.Connection) -> None:
    """Multiplayer round system — collects player actions per round, stores GM narration."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS campaign_rounds (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id     INTEGER NOT NULL,
            round_number    INTEGER NOT NULL DEFAULT 1,
            status          TEXT NOT NULL DEFAULT 'collecting'
                              CHECK (status IN ('collecting', 'narrating', 'done')),
            deadline        TEXT,
            narrative_json  TEXT,
            created_at      TEXT NOT NULL DEFAULT (datetime('now')),
            closed_at       TEXT,
            UNIQUE(campaign_id, round_number)
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_campaign_rounds_campaign "
        "ON campaign_rounds(campaign_id, status)"
    )
    conn.execute("""
        CREATE TABLE IF NOT EXISTS campaign_round_actions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            round_id        INTEGER NOT NULL REFERENCES campaign_rounds(id),
            campaign_id     INTEGER NOT NULL,
            user_id         INTEGER NOT NULL,
            character_id    INTEGER NOT NULL,
            character_name  TEXT NOT NULL,
            action_text     TEXT NOT NULL,
            submitted_at    TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(round_id, user_id)
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_campaign_round_actions_round "
        "ON campaign_round_actions(round_id)"
    )
    conn.commit()
    logger.info("admin_migration_applied", label="campaign-rounds-tables")


def _ensure_push_subscriptions_table(conn: sqlite3.Connection) -> None:
    """Web Push subscription storage — one row per (user, browser endpoint)."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_push_subscriptions (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL,
            endpoint   TEXT NOT NULL,
            p256dh     TEXT NOT NULL,
            auth       TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(user_id, endpoint)
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_push_subs_user "
        "ON user_push_subscriptions(user_id)"
    )
    conn.commit()
    logger.info("admin_migration_applied", label="push-subscriptions-table")


def _ensure_multiplayer_lobby_schema(conn: sqlite3.Connection) -> None:
    """Multiplayer lobby — campaign columns + invite tokens + member status."""
    # Extra columns on campaigns
    existing = [r[1] for r in conn.execute("PRAGMA table_info(campaigns)").fetchall()]
    for col, defn in [
        ("round_timer_hours", "INTEGER NOT NULL DEFAULT 24"),
        ("max_players", "INTEGER NOT NULL DEFAULT 4"),
        ("host_user_id", "INTEGER"),
        ("lobby_status", "TEXT NOT NULL DEFAULT 'open'"),
        ("round_timer_minutes", "INTEGER"),
    ]:
        if col not in existing:
            conn.execute(f"ALTER TABLE campaigns ADD COLUMN {col} {defn}")
    # Backfill round_timer_minutes from round_timer_hours for existing rows
    conn.execute(
        "UPDATE campaigns SET round_timer_minutes = round_timer_hours * 60 WHERE round_timer_minutes IS NULL"
    )

    # Status column on campaign_members (pending/accepted/declined)
    mem_cols = [r[1] for r in conn.execute("PRAGMA table_info(campaign_members)").fetchall()]
    if "status" not in mem_cols:
        conn.execute(
            "ALTER TABLE campaign_members ADD COLUMN status TEXT NOT NULL DEFAULT 'accepted'"
        )
    if "character_id" not in mem_cols:
        conn.execute("ALTER TABLE campaign_members ADD COLUMN character_id INTEGER")

    # Invite-token table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS campaign_invites (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
            token       TEXT NOT NULL UNIQUE,
            created_by  INTEGER NOT NULL REFERENCES users(id),
            expires_at  TEXT NOT NULL,
            used_at     TEXT,
            used_by     INTEGER REFERENCES users(id)
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_campaign_invites_token ON campaign_invites(token)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_campaign_invites_campaign ON campaign_invites(campaign_id)"
    )
    conn.commit()
    logger.info("admin_migration_applied", label="multiplayer-lobby-schema")

    # host_note column on campaigns (one-time host-transfer notification delivery)
    camp_cols2 = [r[1] for r in conn.execute("PRAGMA table_info(campaigns)").fetchall()]
    if "host_note" not in camp_cols2:
        conn.execute("ALTER TABLE campaigns ADD COLUMN host_note TEXT")
    conn.commit()
    logger.info("admin_migration_applied", label="multiplayer-host-transfer")


def _ensure_party_chat_table(conn: sqlite3.Connection) -> None:
    """Party chat messages table."""
    # Party chat messages table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS party_messages (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
            user_id     INTEGER NOT NULL REFERENCES users(id),
            character_name TEXT NOT NULL,
            message     TEXT NOT NULL,
            created_at  TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_party_messages_campaign ON party_messages(campaign_id, created_at)"
    )
    conn.commit()
    logger.info("admin_migration_applied", label="party-chat-table")

    # whisper_to column for /whisper command
    pm_cols = [r[1] for r in conn.execute("PRAGMA table_info(party_messages)").fetchall()]
    if "whisper_to" not in pm_cols:
        conn.execute("ALTER TABLE party_messages ADD COLUMN whisper_to TEXT")
    conn.commit()
    logger.info("admin_migration_applied", label="party-chat-whisper")
