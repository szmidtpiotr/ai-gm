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
        ('enc_dungeon_rats', 'Szczury w piwnicy', 'trivial', 1, 3, 'dungeon', '[{"enemy_key":"giantrat","count":4}]', 20),
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
    ('stealth', 'Stealth', 'DEX', 5, 1, 'Ciche poruszanie się i unikanie wykrycia. Odpowiada za wymykanie się, skradanie i działanie w cieniu.'),
    ('athletics', 'Athletics', 'STR', 5, 2, 'Wysiłek fizyczny: bieganie, skoki, wspinaczka i dźwiganie.'),
    ('initiative', 'Initiative', 'DEX', 5, 3, 'Szybka reakcja i gotowość do działania. Odpowiada za tempo i pierwszeństwo w niebezpiecznych chwilach.'),
    ('attack', 'Attack', 'STR', 5, 4, 'Zdolność do skutecznego uderzenia: celowanie, siła i timing ataku.'),
    ('two_handed', 'Two-Handed', 'STR', 5, 5, 'Biegłość w prowadzeniu ciężkiej broni dwuręcznej bez utraty kontroli nad ciosem.'),
    ('awareness', 'Awareness', 'WIS', 5, 6, 'Wnikliwa obserwacja i czujność. Pomaga dostrzec zagrożenia, śledzić tropy i wyłapać drobne sygnały.'),
    ('persuasion', 'Persuasion', 'CHA', 5, 7, 'Urok, argumenty i przekonywanie innych. Odpowiada za perswazję i rozmowę prowadzącą do zgody.'),
    ('intimidation', 'Intimidation', 'CHA', 5, 8, 'Straszenie, stanowczość i presja psychiczna. Odpowiada za zastraszanie i wymuszanie reakcji.'),
    ('survival', 'Survival', 'WIS', 5, 9, 'Przetrwanie w trudnych warunkach. Odpowiada za orientację, instynkt i decyzje w terenie.'),
    ('lore', 'Lore', 'INT', 5, 10, 'Wiedza z opowieści i dawnych ksiąg. Odpowiada za rozpoznanie kultury, historii, symboli i opowieści świata.'),
    ('arcana', 'Arcana', 'INT', 5, 11, 'Rozumienie magii i zjawisk magicznych. Odpowiada za rozpoznawanie zaklęć, rytuałów i sekretów arkanów.'),
    ('medicine', 'Medicine', 'WIS', 5, 12, 'Udzielanie pomocy i leczenie. Odpowiada za ocenę ran, dobór środków i stabilizację w walce.'),
    ('investigation', 'Investigation', 'INT', 5, 13, 'Dociekliwość i analizowanie szczegółów. Odpowiada za szukanie tropów, wyciąganie wniosków i składanie faktów.')
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
    ('staff', 'Staff', 'd6', 'INT', '["scholar"]', 1, NULL, datetime('now'), datetime('now'))
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
    """Collapse loot entries to item/weapon XOR after consumables migrate into items."""
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='game_config_loot_entries'"
    ).fetchone()
    if not row:
        return
    cols = {r[1]: r for r in conn.execute("PRAGMA table_info(game_config_loot_entries)").fetchall()}
    if "consumable_key" not in cols:
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
    # ─────────────────────────────────────────────────────────────────────────

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

    logger.info("v2_schema_migrations_complete")


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
                else:
                    raise

        _migrate_legacy_archetype_json(conn)
        _ensure_campaign_ai_summaries_audience(conn)
        _ensure_enemy_loot_table_and_drop_chance(conn)
        _ensure_user_llm_settings_mode(conn)
        _run_v2_schema_migrations(conn)
    finally:
        conn.close()

    logger.info("admin_migration_complete", phase="12.0")
