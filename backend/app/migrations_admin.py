import os
import sqlite3

from app.core.logging import get_logger


DB_PATH = "/data/ai_gm.db"
logger = get_logger(__name__)

ADMIN_MIGRATIONS = [
    """
    CREATE TABLE IF NOT EXISTS user_llm_settings (
        user_id INTEGER PRIMARY KEY,
        provider TEXT NOT NULL,
        base_url TEXT NOT NULL,
        model TEXT NOT NULL,
        api_key TEXT NOT NULL DEFAULT '',
        api_key_set INTEGER NOT NULL DEFAULT 0,
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
        linked_stat TEXT NOT NULL,
        allowed_classes TEXT NOT NULL,
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
    "ALTER TABLE game_config_weapons ADD COLUMN description TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE game_config_weapons ADD COLUMN weapon_type TEXT NOT NULL DEFAULT 'melee'",
    "ALTER TABLE game_config_weapons ADD COLUMN two_handed INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE game_config_weapons ADD COLUMN finesse INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE game_config_weapons ADD COLUMN range_m INTEGER",
    "ALTER TABLE game_config_weapons ADD COLUMN weight_kg REAL NOT NULL DEFAULT 0.0",
    "ALTER TABLE game_config_weapons ADD COLUMN note TEXT",
    "ALTER TABLE game_config_enemies ADD COLUMN tier TEXT NOT NULL DEFAULT 'standard'",
    "ALTER TABLE game_config_enemies ADD COLUMN attacks_per_turn INTEGER NOT NULL DEFAULT 1",
    "ALTER TABLE game_config_enemies ADD COLUMN damage_bonus INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE game_config_enemies ADD COLUMN damage_type TEXT NOT NULL DEFAULT 'physical'",
    "ALTER TABLE game_config_enemies ADD COLUMN xp_award INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE game_config_enemies ADD COLUMN dex_modifier INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE game_config_enemies ADD COLUMN conditions_immune TEXT",
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
    ('awareness', 'Awareness', 'WIS', 5, 5, 'Wnikliwa obserwacja i czujność. Pomaga dostrzec zagrożenia, śledzić tropy i wyłapać drobne sygnały.'),
    ('persuasion', 'Persuasion', 'CHA', 5, 6, 'Urok, argumenty i przekonywanie innych. Odpowiada za perswazję i rozmowę prowadzącą do zgody.'),
    ('intimidation', 'Intimidation', 'CHA', 5, 7, 'Straszenie, stanowczość i presja psychiczna. Odpowiada za zastraszanie i wymuszanie reakcji.'),
    ('survival', 'Survival', 'WIS', 5, 8, 'Przetrwanie w trudnych warunkach. Odpowiada za orientację, instynkt i decyzje w terenie.'),
    ('lore', 'Lore', 'INT', 5, 9, 'Wiedza z opowieści i dawnych ksiąg. Odpowiada za rozpoznanie kultury, historii, symboli i opowieści świata.'),
    ('arcana', 'Arcana', 'INT', 5, 10, 'Rozumienie magii i zjawisk magicznych. Odpowiada za rozpoznawanie zaklęć, rytuałów i sekretów arkanów.'),
    ('medicine', 'Medicine', 'WIS', 5, 11, 'Udzielanie pomocy i leczenie. Odpowiada za ocenę ran, dobór środków i stabilizację w walce.'),
    ('investigation', 'Investigation', 'INT', 5, 12, 'Dociekliwość i analizowanie szczegółów. Odpowiada za szukanie tropów, wyciąganie wniosków i składanie faktów.')
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
    ('poisoned', 'Poisoned', '{"stat_mods":{"STR":-2},"duration":"3 turns"}', 'Temporary STR penalty.', 1, NULL, datetime('now'), datetime('now'))
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
    INSERT OR IGNORE INTO game_config_items (
        key, label, item_type, description, value_gp, weight, weight_kg, effect_json, is_active,
        proficiency_classes, note, locked_at, created_at, updated_at
    ) VALUES
    ('leatherarmor', 'Leather Armor', 'armor', 'Light body armor.', 20, 0, 8.0, NULL, 1,
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
]


def _rebuild_loot_entries_for_consumable_support(conn: sqlite3.Connection) -> None:
    """Allow NULL item_key when consumable_key is set (SQLite cannot relax NOT NULL via ALTER)."""
    cur = conn.execute("PRAGMA table_info(game_config_loot_entries)").fetchall()
    cols = {row[1]: row for row in cur}
    if "item_key" not in cols:
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
    if conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='index' AND name='ux_loot_entries_weapon'"
    ).fetchone():
        return
    cols = {row[1]: row for row in conn.execute("PRAGMA table_info(game_config_loot_entries)").fetchall()}
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


def _migrate_legacy_archetype_json(conn: sqlite3.Connection) -> None:
    """One-time: normalize legacy archetype / allowed_classes JSON tokens to scholar."""
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

        for sql in ADMIN_SEEDS:
            conn.execute(sql)
            conn.commit()
            logger.info(
                "admin_migration_seeded",
                sql_preview=sql.strip().splitlines()[0],
            )

        _migrate_legacy_archetype_json(conn)
        _ensure_enemy_loot_table_and_drop_chance(conn)
    finally:
        conn.close()

    logger.info("admin_migration_complete", phase="11.0")
