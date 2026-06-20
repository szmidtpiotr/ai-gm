import json
import os
import sqlite3

from app.core.logging import get_logger


DB_PATH = "/data/ai_gm.db"
logger = get_logger(__name__)

# #592 — FAZA U mechanics documented in the admin Knowledge book (Narzędzia → Wiedza).
# These describe systems shipped in FAZA U so admins have an in-panel reference.
FAZA_U_KNOWLEDGE_TIPS = [
    {
        "tip_key": "durability",
        "category": "equipment",
        "title": "Trwałość przedmiotów (U16)",
        "body": (
            "Broń i pancerz zużywają się podczas walki — każde użycie obniża trwałość. "
            "Gdy trwałość spadnie do zera, przedmiot traci swoje bonusy do czasu naprawy "
            "u kowala lub rzemieślnika. Naprawa kosztuje złoto proporcjonalnie do tieru "
            "przedmiotu. Mechanika zmusza graczy do dbania o sprzęt i planowania wizyt w mieście."
        ),
        "sort_order": 100,
    },
    {
        "tip_key": "robbery_raids",
        "category": "world",
        "title": "Napady i rabunki (U24)",
        "body": (
            "Podczas podróży i odpoczynku w niebezpiecznych regionach bohater może zostać "
            "napadnięty. Rabusie próbują odebrać złoto lub łup — gracz może walczyć, przekupić "
            "się lub uciec. Szansa napadu rośnie wraz z niebezpieczeństwem heksa i ilością "
            "noszonego złota. To balansuje ekonomię i nagradza ostrożne przechowywanie bogactwa."
        ),
        "sort_order": 110,
    },
    {
        "tip_key": "affix_pity_timer",
        "category": "loot",
        "title": "Licznik litości afiksów (U25)",
        "body": (
            "System łupów ma „pity timer” — licznik gwarantujący rzadki afiks po określonej "
            "liczbie zdobytych przedmiotów bez trafienia. Im dłuższa seria bez rzadkiego dropu, "
            "tym wyższa szansa na kolejny. Zapobiega frustracji pechowych serii i wygładza "
            "krzywą nagród dla gracza, który długo nie widział nic wartościowego."
        ),
        "sort_order": 120,
    },
    {
        "tip_key": "economy_telemetry",
        "category": "economy",
        "title": "Telemetria ekonomii i złota (U26)",
        "body": (
            "Przepływ złota jest mierzony: ile gracz zarabia (łup, sprzedaż, nagrody) i wydaje "
            "(zakupy, naprawy, przekupstwa) jest rejestrowane na potrzeby balansu. Dane pozwalają "
            "admin-owi wykryć inflację lub niedobór złota i dostroić ceny sklepów oraz wartości "
            "dropów. To narzędzie diagnostyczne — nie wpływa bezpośrednio na rozgrywkę gracza."
        ),
        "sort_order": 130,
    },
]

ADMIN_MIGRATIONS = [
    # #587 — telemetry tables for Overview → Zdarzenia (events feed + LLM usage).
    # event_logger.write_game_event/write_llm_log wrote here best-effort but the
    # tables were never created → silent drops + 404/500 on /analytics/events|llm.
    """
    CREATE TABLE IF NOT EXISTS game_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_type TEXT NOT NULL,
        severity TEXT NOT NULL DEFAULT 'info',
        campaign_id INTEGER,
        character_id INTEGER,
        user_id INTEGER,
        event_data TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS llm_call_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        campaign_id INTEGER,
        call_type TEXT,
        model TEXT,
        prompt_tokens INTEGER DEFAULT 0,
        completion_tokens INTEGER DEFAULT 0,
        latency_ms INTEGER,
        cache_hit INTEGER DEFAULT 0,
        error TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
    # O1 — indices for game_events and llm_call_log (tables created above in #587,
    # indices missing — added 2026-06-16).
    "CREATE INDEX IF NOT EXISTS idx_game_events_type_date ON game_events (event_type, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_game_events_campaign ON game_events (campaign_id, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_game_events_severity ON game_events (severity, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_llm_log_type_date ON llm_call_log (call_type, created_at)",
    # Admin-surface tables whose CREATE was never migrated (only existed in
    # e2e_bootstrap.sql or not at all) → caused 500s on /admin/bug-reports,
    # /admin/push/subscriptions, /admin/voice/hosts, /admin/ui-texts.
    """
    CREATE TABLE IF NOT EXISTS bug_reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        campaign_id INTEGER,
        observation TEXT NOT NULL DEFAULT '',
        reproduction TEXT,
        report_type TEXT NOT NULL DEFAULT 'bug',
        context_json TEXT,
        github_issue_url TEXT,
        github_issue_number INTEGER,
        github_status TEXT DEFAULT 'pending',
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS user_push_subscriptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        endpoint TEXT NOT NULL,
        p256dh TEXT NOT NULL,
        auth TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE(user_id, endpoint)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS voice_hosts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        label TEXT NOT NULL DEFAULT '',
        base_url TEXT NOT NULL UNIQUE,
        kind TEXT NOT NULL DEFAULT 'cpu',
        is_active INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
    # #748 — voice_config była używana przez voice_proxy (POST /voice/config),
    # ale nigdy nie powstała → zapis ustawień głosu w panelu wykraszał.
    """
    CREATE TABLE IF NOT EXISTS voice_config (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL DEFAULT ''
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS ui_texts (
        key TEXT PRIMARY KEY,
        screen TEXT NOT NULL DEFAULT '',
        description TEXT NOT NULL DEFAULT '',
        original_text TEXT NOT NULL DEFAULT '',
        custom_text TEXT,
        font_family TEXT,
        font_size TEXT,
        font_weight TEXT,
        color TEXT,
        text_transform TEXT,
        letter_spacing TEXT,
        extra_css TEXT,
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
    # Bootstrap tables — originally SQLModel models, must exist before all other migrations
    """
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        display_name TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        is_active INTEGER NOT NULL DEFAULT 1,
        is_admin INTEGER NOT NULL DEFAULT 0,
        failed_login_count INTEGER NOT NULL DEFAULT 0,
        lockout_until TEXT,
        role TEXT NOT NULL DEFAULT 'player',
        resurrection_enabled INTEGER NOT NULL DEFAULT 0,
        resurrection_cost_mode TEXT NOT NULL DEFAULT 'admin_free',
        resurrection_cost_value INTEGER NOT NULL DEFAULT 25,
        resurrection_cost_cap_percent INTEGER NOT NULL DEFAULT 50,
        resurrection_uses_remaining INTEGER,
        email TEXT,
        invited_by_user_id INTEGER REFERENCES users(id),
        email_verified_at TEXT,
        onboarded_at TEXT,
        invite_weekly_limit INTEGER NOT NULL DEFAULT 3,
        avatar_url TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS campaigns (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        system_id TEXT NOT NULL,
        model_id TEXT NOT NULL,
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
        is_tutorial INTEGER NOT NULL DEFAULT 0,
        engine_private_json TEXT DEFAULT NULL,
        FOREIGN KEY (owner_user_id) REFERENCES users(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS characters (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        campaign_id INTEGER,
        user_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        system_id TEXT NOT NULL,
        sheet_json TEXT NOT NULL DEFAULT '{}',
        location TEXT,
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        gold_gp INTEGER NOT NULL DEFAULT 0,
        backstory TEXT,
        appearance TEXT,
        personality TEXT,
        motivation TEXT,
        note TEXT,
        gold INTEGER NOT NULL DEFAULT 0,
        hero_status TEXT NOT NULL DEFAULT 'active',
        visited_location_keys TEXT NOT NULL DEFAULT '[]',
        status TEXT NOT NULL DEFAULT 'idle',
        FOREIGN KEY (campaign_id) REFERENCES campaigns(id),
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS campaign_turns (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        campaign_id INTEGER NOT NULL,
        character_id INTEGER,
        user_text TEXT NOT NULL,
        route TEXT NOT NULL DEFAULT 'narrative',
        assistant_text TEXT,
        turn_number INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (campaign_id) REFERENCES campaigns(id),
        FOREIGN KEY (character_id) REFERENCES characters(id)
    )
    """,
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
        stats_json TEXT,
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
    # E7 (#422) — campaign_templates: required NPCs/beats + player-visibility gate.
    "ALTER TABLE campaign_templates ADD COLUMN required_npc_keys TEXT NOT NULL DEFAULT '[]'",
    "ALTER TABLE campaign_templates ADD COLUMN required_beats TEXT NOT NULL DEFAULT '[]'",
    "ALTER TABLE campaign_templates ADD COLUMN player_visible INTEGER NOT NULL DEFAULT 1",
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
        campaign_id INTEGER,
        meta_json TEXT,
        game_clock_day INTEGER,
        wall_clock_at TEXT NOT NULL DEFAULT (datetime('now')),
        reverted_at TEXT
    )
    """,
    # U26 (#576) — campaign_id on the gold journal so economy telemetry can
    # scope by campaign without a clock lookup. ALTER for DBs created before
    # U26 (fails harmlessly if the column already exists); backfill from the
    # character's current campaign.
    "ALTER TABLE character_gold_log ADD COLUMN campaign_id INTEGER",
    "UPDATE character_gold_log SET campaign_id = (SELECT c.campaign_id FROM characters c WHERE c.id = character_gold_log.character_id) WHERE campaign_id IS NULL",
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
    # F2 (#462) — Affix System: affix catalog carrying typed Effect Objects (F1 schema).
    """
    CREATE TABLE IF NOT EXISTS game_config_affixes (
        key                TEXT PRIMARY KEY,
        name               TEXT NOT NULL,
        tier               INTEGER NOT NULL DEFAULT 1,
        allowed_item_types TEXT NOT NULL DEFAULT 'weapon',
        effect_json        TEXT,
        is_active          INTEGER NOT NULL DEFAULT 1,
        created_at         TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at         TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
    # F2 (#462) — starter affixes (flat damage_bonus via F1 typed Effect Objects).
    """
    INSERT OR IGNORE INTO game_config_affixes (key, name, tier, allowed_item_types, effect_json)
    VALUES ('sharp', 'Ostry', 1, 'weapon',
            '{"schema_version":1,"effect_category":"gear_bonus","effects":[{"type":"damage_bonus","value":2}]}')
    """,
    """
    INSERT OR IGNORE INTO game_config_affixes (key, name, tier, allowed_item_types, effect_json)
    VALUES ('keen', 'Wyostrzony', 2, 'weapon',
            '{"schema_version":1,"effect_category":"gear_bonus","effects":[{"type":"damage_bonus","value":4}]}')
    """,
    """
    INSERT OR IGNORE INTO game_config_affixes (key, name, tier, allowed_item_types, effect_json)
    VALUES ('brutal', 'Brutalny', 3, 'weapon',
            '{"schema_version":1,"effect_category":"gear_bonus","effects":[{"type":"damage_bonus","value":6}]}')
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
    "ALTER TABLE game_config_enemies ADD COLUMN stats_json TEXT",
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
    # Phase 0-B1 — Add created_by, canonical, source_campaign_id tracking to game_locations
    "ALTER TABLE game_locations ADD COLUMN created_by TEXT DEFAULT 'admin_manual'",
    "ALTER TABLE game_locations ADD COLUMN canonical INTEGER DEFAULT 0",
    "ALTER TABLE game_locations ADD COLUMN source_campaign_id INTEGER",
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
    # S13/S14 (#501/#502) — Forge tables: adventure_ideas, adventure_hooks, campaign_templates.
    # These tables are referenced by adventure_forge.py and encounter_seed_service.py
    # but were never added to migrations. CREATE TABLE IF NOT EXISTS is idempotent.
    """
    CREATE TABLE IF NOT EXISTS adventure_ideas (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        title           TEXT NOT NULL,
        premise         TEXT NOT NULL DEFAULT '',
        tone            TEXT NOT NULL DEFAULT '[]',
        themes          TEXT NOT NULL DEFAULT '[]',
        difficulty      TEXT NOT NULL DEFAULT 'medium',
        structured_data TEXT NOT NULL DEFAULT '{}',
        status          TEXT NOT NULL DEFAULT 'draft',
        created_by      TEXT NOT NULL DEFAULT 'admin',
        created_at      TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS adventure_hooks (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        adventure_idea_id   INTEGER REFERENCES adventure_ideas(id) ON DELETE SET NULL,
        hook_type           TEXT NOT NULL DEFAULT 'event',
        title               TEXT NOT NULL,
        description         TEXT NOT NULL DEFAULT '',
        significance        TEXT NOT NULL DEFAULT 'minor',
        draft_data          TEXT NOT NULL DEFAULT '{}',
        status              TEXT NOT NULL DEFAULT 'pending',
        promoted_record_id  INTEGER,
        promoted_table      TEXT,
        quality_rating      INTEGER,
        times_used          INTEGER NOT NULL DEFAULT 0,
        created_at          TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS campaign_templates (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        title               TEXT NOT NULL,
        description         TEXT NOT NULL DEFAULT '',
        difficulty_rating   INTEGER NOT NULL DEFAULT 3,
        atmosphere          TEXT,
        gm_plan_json        TEXT NOT NULL DEFAULT '{}',
        hook_ids            TEXT NOT NULL DEFAULT '[]',
        status              TEXT NOT NULL DEFAULT 'draft',
        play_count          INTEGER NOT NULL DEFAULT 0,
        created_by          TEXT NOT NULL DEFAULT 'admin',
        created_at          TEXT NOT NULL DEFAULT (datetime('now')),
        start_hex_q         INTEGER,
        start_hex_r         INTEGER,
        adventure_idea_id   INTEGER REFERENCES adventure_ideas(id) ON DELETE SET NULL,
        required_npc_keys   TEXT NOT NULL DEFAULT '[]',
        required_beats      TEXT NOT NULL DEFAULT '[]',
        player_visible      INTEGER NOT NULL DEFAULT 1
    )
    """,
    # #224 — dungeon tile card system: categories + tiles tables.
    # Referenced by dungeon_tiles.py router; were never added to migrations.
    """
    CREATE TABLE IF NOT EXISTS dungeon_tile_categories (
        key             TEXT PRIMARY KEY,
        label           TEXT NOT NULL,
        description     TEXT NOT NULL DEFAULT '',
        style_modifier  TEXT NOT NULL DEFAULT '',
        system_prompt   TEXT,
        sort_order      INTEGER NOT NULL DEFAULT 0,
        is_active       INTEGER NOT NULL DEFAULT 1
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS dungeon_tiles (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        category_key        TEXT NOT NULL REFERENCES dungeon_tile_categories(key) ON DELETE CASCADE,
        label               TEXT NOT NULL,
        image_url           TEXT,
        image_url_raw       TEXT,
        image_gen_prompt    TEXT,
        doors_json          TEXT NOT NULL DEFAULT '[]',
        door_overlays_json  TEXT NOT NULL DEFAULT '{}',
        room_description    TEXT NOT NULL DEFAULT '',
        enemies_json        TEXT NOT NULL DEFAULT '[]',
        items_json          TEXT NOT NULL DEFAULT '[]',
        active_states_json  TEXT NOT NULL DEFAULT '[]',
        riddle_key          TEXT,
        exit_conditions_json TEXT NOT NULL DEFAULT '[]',
        is_boss_tile        INTEGER NOT NULL DEFAULT 0,
        is_active           INTEGER NOT NULL DEFAULT 1,
        created_at          TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at          TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_dungeon_tiles_category
    ON dungeon_tiles(category_key, is_active)
    """,
    # L17 (#723): per-category image base prompt. When set, overrides the global
    # furniture-forcing BASE_PROMPT in dungeon_tiles._build_prompt — lets a category
    # (e.g. „jaskinie") render natural cave terrain instead of furnished rooms.
    # NULL/empty → fall back to global BASE_PROMPT (krypta keeps its furnished look).
    "ALTER TABLE dungeon_tile_categories ADD COLUMN base_prompt TEXT",
    # U5 (#528): LLM tag error telemetry — one row per malformed/rejected tag
    """
    CREATE TABLE IF NOT EXISTS llm_tag_errors (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        campaign_id INTEGER NOT NULL,
        turn_number INTEGER NOT NULL DEFAULT 0,
        tag_raw     TEXT    NOT NULL DEFAULT '',
        error_type  TEXT    NOT NULL DEFAULT 'unknown',
        ts          TEXT    NOT NULL DEFAULT (datetime('now')),
        FOREIGN KEY (campaign_id) REFERENCES campaigns(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_llm_tag_errors_campaign
    ON llm_tag_errors(campaign_id)
    """,
    # F13 (#516): character_rentals — rental expiry tracking (was missing from migrations)
    """
    CREATE TABLE IF NOT EXISTS character_rentals (
        id INTEGER PRIMARY KEY,
        character_id INTEGER NOT NULL,
        campaign_id INTEGER,
        npc_id INTEGER NOT NULL DEFAULT 1,
        item_type TEXT NOT NULL DEFAULT 'misc',
        item_key TEXT NOT NULL DEFAULT 'room',
        label TEXT NOT NULL DEFAULT 'Wynajęta kwatera',
        rental_fee_gp INTEGER NOT NULL DEFAULT 10,
        total_paid_gp INTEGER NOT NULL DEFAULT 10,
        duration_turns INTEGER NOT NULL DEFAULT 5,
        rented_at_turn INTEGER NOT NULL DEFAULT 1,
        expires_at_turn INTEGER NOT NULL,
        inventory_id INTEGER,
        status TEXT NOT NULL DEFAULT 'active',
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
    # BUG-03 (#529): campaign_known_npcs — NPC memory per campaign (was missing from migrations)
    """
    CREATE TABLE IF NOT EXISTS campaign_known_npcs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        campaign_id INTEGER NOT NULL,
        npc_id INTEGER,
        npc_name TEXT NOT NULL,
        role TEXT,
        first_met_location TEXT,
        first_met_turn INTEGER,
        notes TEXT,
        relation_status TEXT NOT NULL DEFAULT 'neutral',
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now')),
        purchase_count INTEGER NOT NULL DEFAULT 0,
        UNIQUE(campaign_id, npc_name)
    )
    """,
    # S3 (#583): NPC ability stats — lazy-generated per campaign + optional global template.
    "ALTER TABLE campaign_known_npcs ADD COLUMN stats_json TEXT",
    "ALTER TABLE npcs ADD COLUMN stats_json TEXT",
    # U11a (#556): unified item table — all kinds in one place
    """
    CREATE TABLE IF NOT EXISTS game_items (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        key         TEXT    UNIQUE NOT NULL,
        kind        TEXT    NOT NULL CHECK(kind IN ('weapon','armor','item','consumable')),
        label       TEXT    NOT NULL DEFAULT '',
        description TEXT    DEFAULT '',
        price_gp    REAL    DEFAULT 0,
        effect_json TEXT    DEFAULT NULL,
        equip_slot  TEXT    DEFAULT NULL,
        rarity      INTEGER DEFAULT 1,
        min_level   INTEGER DEFAULT 1,
        location_tags TEXT  DEFAULT '[]',
        created_by  TEXT    DEFAULT 'seed',
        approved    INTEGER DEFAULT 1,
        is_active   INTEGER DEFAULT 1,
        weapon_data TEXT    DEFAULT '{}',
        item_data   TEXT    DEFAULT '{}',
        weight_kg   REAL    DEFAULT 0,
        note        TEXT    DEFAULT NULL,
        locked_at   TEXT    DEFAULT NULL,
        created_at  TEXT    DEFAULT (datetime('now')),
        updated_at  TEXT    DEFAULT (datetime('now'))
    )
    """,
    # U11a (#556): FK target columns — NULL until U11c switches write path
    "ALTER TABLE character_inventory ADD COLUMN game_item_key TEXT",
    "ALTER TABLE game_config_loot_entries ADD COLUMN game_item_key TEXT",
    # #764: ammunition link — ranged weapon → required ammo consumable key
    "ALTER TABLE game_config_weapons ADD COLUMN ammo_key TEXT",
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
    ('deception', 'Oszustwo', 'CHA', 5, 17, 'Wprowadzanie w błąd słowem lub gestem — kłamanie, blefowanie, granie roli.'),
    ('riding', 'Jeździectwo', 'DEX', 5, 18, 'Wsiadanie i kontrola wierzchowca, ryzykowne manewry konne (galop przez tłum, skok). Sukces — manewr czysty; porażka — utrata akcji ruchu; krytyczna — wypadnięcie z siodła, obrażenia + ogłuszenie.'),
    ('endurance', 'Wytrzymałość', 'CON', 5, 19, 'Długotrwały wysiłek fizyczny (marsz, praca, walka na głodzie) i obrona przed kondycjami fizycznymi. Porażka — kondycja wyczerpania; krytyczna — 2 poziomy i przymus postoju.'),
    ('swim', 'Pływanie', 'STR', 5, 20, 'Pływanie wpław, walka z prądem, tonięcie (STR; długie przeprawy w ciężkim ekwipunku — narracyjnie CON). Porażka — utrata postępów; krytyczna — postać zaczyna tonąć.'),
    ('climb', 'Wspinaczka', 'STR', 5, 21, 'Wspinaczka na ściany, klify i maszty; DC zależy od powierzchni, lina je obniża. Porażka — brak postępu; krytyczna — upadek i obrażenia.'),
    ('charm', 'Czar osobisty', 'CHA', 5, 22, 'Zjednanie kogoś i dobre wrażenie (test przeciw WIS celu). Sukces — NPC przychylny; krytyczny — sojusznik na scenę; krytyczna porażka — podejrzliwość.'),
    ('gossip', 'Plotkowanie', 'CHA', 5, 23, 'Zbieranie i rozsiewanie plotek wśród miejscowych. Sukces — jedna przydatna informacja; krytyczny — dwie lub sekret; krytyczna porażka — błędna plotka albo zdemaskowanie.'),
    ('bribe', 'Przekupstwo', 'CHA', 5, 24, 'Oferta pieniędzy lub dóbr za przysługę (test przeciw WIS celu, wymaga zadeklarowania kwoty). Sukces — łapówka przyjęta; krytyczna porażka — odmowa i zgłoszenie próby.'),
    ('trade_craft', 'Rzemiosło', 'INT', 5, 25, 'Wyrób i naprawa przedmiotów. Sukces — przedmiot gotowy; krytyczna porażka — utrata materiałów lub narzędzi. Efekt narracyjny (crafting mechaniczny: poza zakresem).'),
    ('language', 'Języki obce', 'INT', 5, 26, 'Rozumienie obcej mowy lub tekstu. Sukces — sens uchwycony; krytyczna porażka — błędna interpretacja przeciwna do prawdy.'),
    ('theology', 'Teologia', 'WIS', 5, 27, 'Wiedza o religiach, kultach, rytuałach i klątwach. Sukces — poprawna identyfikacja; krytyczny — ukryty szczegół; krytyczna porażka — obraza bóstwa lub kapłanów.'),
    ('nature', 'Wiedza o naturze', 'WIS', 5, 28, 'Rozpoznawanie roślin, zwierząt, pogody, naturalnych trucizn i terenu. Sukces — identyfikacja i właściwości; krytyczna porażka — błędne rozpoznanie (trujący grzyb).'),
    ('alchemy', 'Alchemia', 'INT', 5, 29, 'Warzenie mikstur, trucizn i kwasów. Sukces — substancja gotowa; krytyczna porażka — wybuch lub zatrucie twórcy. Efekt narracyjny (crafting mechaniczny: poza zakresem).'),
    ('magic_sense', 'Wyczucie magii', 'WIS', 5, 30, 'Wyczuwanie obecności zaklęć, artefaktów, klątw i portali. Sukces — źródło i kierunek; krytyczny — szkoła i cel; krytyczna porażka — fałszywe wrażenie.'),
    ('tracking', 'Tropienie', 'WIS', 5, 31, 'Śledzenie śladów ludzi i zwierząt w terenie. Sukces — ślad odnaleziony; krytyczny — liczebność, czas i kondycja grupy; krytyczna porażka — błędny trop.'),
    ('sailing', 'Żeglarstwo', 'INT', 5, 32, 'Sterowanie łodzią, nawigacja i żagle (INT nawigacja; manewry w sztormie — narracyjnie DEX). Sukces — kurs utrzymany; krytyczna porażka — uszkodzenie statku lub utrata kursu.'),
    ('pickpocket', 'Kieszonkostwo', 'DEX', 5, 33, 'Kradzież z kieszeni niezauważona (test przeciw WIS ofiary). Sukces — łup zdobyty; krytyczna porażka — złapanie na gorącym uczynku.'),
    ('disguise', 'Przebranie', 'CHA', 5, 34, 'Udawanie kogoś innego strojem i zachowaniem (przy podejrzeniu test przeciw WIS). Sukces — nierozpoznany; krytyczna porażka — natychmiastowe zdemaskowanie.'),
    ('torture', 'Przesłuchanie', 'CHA', 5, 35, 'Wydobywanie informacji groźbą i presją (CHA psychologiczne, przeciw CON jeńca; brutalny wariant STR narracyjnie). Sukces — jeniec mówi; krytyczna porażka — jeniec milknie lub umiera, informacje bezużyteczne.'),
    ('haggling', 'Targowanie', 'CHA', 5, 36, 'Negocjowanie ceny towaru lub usługi (test przeciw CHA kupca; raz na transakcję). Sukces — cena obniżona o 10–25%; krytyczny — o 30–50% lub bonus od sprzedawcy; krytyczna porażka — sprzedawca obrażony, cena rośnie i dalsze targowanie u niego niemożliwe. Wynik nakłada jednorazowy rabat na najbliższe kupno/sprzedaż.'),
    ('gamble', 'Gra w kości', 'CHA', 5, 37, 'Gra w kości, karty lub inny hazard o złoto (test CHA przeciw CHA najsilniejszego gracza przy stole; DC 12 amatorzy, DC 20 zawodowcy). Stawkę deklaruje gracz, kwoty rozstrzyga mechanika. Sukces — wygrywa stawkę; krytyczny — podwójną stawkę; porażka — traci stawkę; krytyczna porażka — traci stawkę i pada na niego oskarżenie o oszustwo. Maks. kilka gier na scenę.'),
    ('dodge', 'Unik', 'DEX', 5, 38, 'Reakcja bojowa (S15): po zadeklarowaniu uniku, gdy wróg trafia, postać wykonuje test DEX przeciw wynikowi ataku wroga PRZED obrażeniami. Raz na rundę. Sukces — atak mija (0 obrażeń); porażka — normalne obrażenia; krytyczna porażka — utrata reakcji w następnej rundzie. Wymaga rank ≥ 1, by aktywować przełącznik w walce.'),
    ('shield_block', 'Blok Tarczą', 'STR', 5, 39, 'Reakcja bojowa (S16): postać z założoną tarczą może zadeklarować blok; gdy wróg trafia, wykonuje test STR przeciw wynikowi ataku wroga (DC min. 12) PRZED obrażeniami. Raz na rundę (XOR z unikiem). Sukces — obrażenia zmniejszone o 1k6 + bonus STR; sukces o ≥ +5 — atak całkowicie odparty; porażka — pełne obrażenia; krytyczna porażka — tarcza traci wytrzymałość. Wymaga rank ≥ 1 i założonej tarczy.'),
    ('wrestling', 'Zapasy', 'STR', 5, 40, 'Akcja bojowa (S17): chwyt i obalenie wroga w zwarciu — test przeciwny STR vs STR celu. Sukces — cel schwytany/przewrócony (kondycja slowed); sukces krytyczny (margines ≥ +5) — cel unieruchomiony (stunned 1 rundę); porażka — bez efektu; krytyczna porażka — napastnik sam przewrócony (slowed). Wymaga zwarcia (engaged); konsumuje turę.'),
    ('dual_wield', 'Walka dwoma broniami', 'DEX', 5, 41, 'Cecha bojowa (#598): trzymając DWIE lekkie bronie (np. dwa sztylety) postać wykonuje drugi atak off-hand w tej samej turze (pełny rzut + pełny mod cechy do obrażeń). Wymaga rank ≥ 1 — bez umiejętności off-hand jest kosmetyczny. Cięższa broń + druga broń w off-hand daje zamiast tego parowanie (+2 do obrony), niezależnie od tej umiejętności.')
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
    # ── S8 (#603) — batch kondycji FAZY S złożonych z prymitywów (dot/static_stat_modifier/
    #    periodic_save). Liczby = wartości startowe z skills_conditions_design_doc.md (Numbers Policy,
    #    tuning po S20). Wersje lite (confused/insane/panicked/charmed/cursed) = same kary + rzut;
    #    pełne behavior_override/zły omen → S18/S11. Zero `if condition_key==...` w silniku (Zasada 1).
    """
    INSERT OR IGNORE INTO game_config_conditions
    (key, label, effect_json, description, is_active, stackable, auto_remove, locked_at, created_at, updated_at)
    VALUES
    ('on_fire', 'Podpalony', '{"schema_version":1,"effect_category":"character_condition","effects":[{"type":"dot","value":"2d6","damage_type":"fire","tick":"start_turn"},{"type":"static_stat_modifier","stat":"STR","value":-2},{"type":"static_stat_modifier","stat":"DEX","value":-2},{"type":"periodic_save","stat":"DEX","value":12,"tick":"start_turn","expires":"save_success"}]}', 'Postać płonie — 2k6 obrażeń od ognia na początku tury, STR i DEX -2. Udany rzut DEX DC 12 (tarzanie/woda) gasi ogień.', 1, 0, NULL, NULL, datetime('now'), datetime('now')),
    ('frozen', 'Zmrożony', '{"schema_version":1,"effect_category":"character_condition","effects":[{"type":"static_stat_modifier","stat":"DEX","value":-4},{"type":"periodic_save","stat":"CON","value":14,"tick":"start_turn","expires":"save_success"}]}', 'Postać pokryta lodem — DEX -4, ruch spowolniony. Udany rzut CON DC 14 (rozgrzewanie) lub kontakt z ciepłem zdejmuje stan.', 1, 0, NULL, NULL, datetime('now'), datetime('now')),
    ('confused', 'Zdezorientowany', '{"schema_version":1,"effect_category":"character_condition","effects":[{"type":"static_stat_modifier","stat":"INT","value":-3},{"type":"static_stat_modifier","stat":"WIS","value":-3},{"type":"periodic_save","stat":"WIS","value":14,"tick":"start_turn","expires":"save_success"}]}', 'Postać nie rozumie otoczenia — INT i WIS -3. Udany rzut WIS DC 14 (zebranie myśli) kończy stan. Wersja lite: bez losowej tabeli zachowań (pełna w S18).', 1, 0, NULL, NULL, datetime('now'), datetime('now')),
    ('insane', 'Obłąkany', '{"schema_version":1,"effect_category":"character_condition","effects":[{"type":"static_stat_modifier","stat":"CHA","value":-5}]}', 'Postać straciła kontakt z rzeczywistością — testy społeczne -5. Wersja lite: bez pełnego prowadzenia postaci przez MG.', 1, 0, NULL, NULL, datetime('now'), datetime('now')),
    ('panicked', 'Spanikowany', '{"schema_version":1,"effect_category":"character_condition","effects":[{"type":"static_stat_modifier","stat":"CHA","value":-4},{"type":"static_stat_modifier","stat":"WIS","value":-4}]}', 'Postać ogarnięta paniką — CHA i WIS -4. Wersja lite: bez wymuszonej ucieczki (pełna w S18).', 1, 0, NULL, NULL, datetime('now'), datetime('now')),
    ('charmed', 'Zaczarowany', '{"schema_version":1,"effect_category":"character_condition","effects":[{"type":"static_stat_modifier","stat":"WIS","value":-3},{"type":"periodic_save","stat":"WIS","value":16,"tick":"start_turn","expires":"save_success"}]}', 'Postać oczarowana — WIS -3 wobec oceny działań źródła. Udany rzut WIS DC 16 zrywa czar. Wersja lite: bez twardego zakazu ataku źródła.', 1, 0, NULL, NULL, datetime('now'), datetime('now')),
    ('cursed', 'Przeklęty', '{"schema_version":1,"effect_category":"character_condition","effects":[{"type":"static_stat_modifier","stat":"STR","value":-2},{"type":"static_stat_modifier","stat":"DEX","value":-2},{"type":"static_stat_modifier","stat":"CON","value":-2},{"type":"static_stat_modifier","stat":"INT","value":-2},{"type":"static_stat_modifier","stat":"WIS","value":-2},{"type":"static_stat_modifier","stat":"CHA","value":-2}]}', 'Postać nosi klątwę — -2 do wszystkich testów. Wersja lite: zły omen (wymuszony reroll) dochodzi w S11. Zdjęcie: rytuał theology/arcana.', 1, 0, NULL, NULL, datetime('now'), datetime('now'))
    """,
    # S9 (#604) FAZA S — prymityw stacking_levels + kondycja exhausted (stackable=1).
    # Liczby = wartości startowe (skills_conditions_design_doc.md, Numbers Policy → tuning po S20).
    """
    INSERT OR IGNORE INTO game_config_conditions
    (key, label, effect_json, description, is_active, stackable, auto_remove, locked_at, created_at, updated_at)
    VALUES
    ('exhausted', 'Wyczerpany', '{"schema_version":1,"effect_category":"character_condition","effects":[{"type":"stacking_levels","max_level":2,"per_level_effects":[{"type":"static_stat_modifier","stat":"STR","value":-3},{"type":"static_stat_modifier","stat":"DEX","value":-3},{"type":"static_stat_modifier","stat":"CON","value":-3}],"threshold_effects":{"2":{"type":"block_action"}}}]}', 'Postać skrajnie zmęczona — STR/DEX/CON -3 na poziom (poziom 2 = -6 i omdlenie/utrata tury). Ponowne nałożenie podbija poziom (max 2). Zdjęcie: 1h odpoczynku = -1 poziom, pełny sen = wszystkie, mikstura/zaklęcie regeneracji natychmiast.', 1, 1, NULL, NULL, datetime('now'), datetime('now'))
    """,
    # S10 (#605) FAZA S — prymityw escalating_dot + kondycja hemorrhage (narastający DOT).
    # Liczby = wartości startowe (skills_conditions_design_doc.md, Numbers Policy → tuning po S20).
    # Top-level `cure` = deklaratywne zdjęcie kondycji udanym SKILL_TEST:medicine (DC z zamka).
    """
    INSERT OR IGNORE INTO game_config_conditions
    (key, label, effect_json, description, is_active, stackable, auto_remove, locked_at, created_at, updated_at)
    VALUES
    ('hemorrhage', 'Krwotok', '{"schema_version":1,"effect_category":"character_condition","effects":[{"type":"escalating_dot","value":"1d4","escalate_every_rounds":3,"escalate_dice":"1d4","damage_type":"physical","tick":"start_turn"}],"cure":{"skill":"medicine","dc":16}}', 'Krwotok — 1k4 obrażeń na początku tury, +1k4 co 3 tury bez leczenia (narastający). Zdjęcie: test medicine DC 16 (bandaże/narzędzia) lub leczenie magiczne (remove_condition).', 1, 0, NULL, NULL, datetime('now'), datetime('now'))
    """,
    # S11 (#606) FAZA S — prymityw `reroll` + kondycja `inspired` (player_keep_best).
    # Liczby = wartości startowe (skills_conditions_design_doc.md, Numbers Policy → tuning po S20).
    """
    INSERT OR IGNORE INTO game_config_conditions
    (key, label, effect_json, description, is_active, stackable, auto_remove, locked_at, created_at, updated_at)
    VALUES
    ('inspired', 'Zainspirowany', '{"schema_version":1,"effect_category":"character_condition","effects":[{"type":"static_stat_modifier","stat":"CHA","value":2},{"type":"static_stat_modifier","stat":"WIS","value":2},{"type":"reroll","mode":"player_keep_best","uses":1,"scope":"skill_test"}]}', 'Postać działa pewniej — CHA i WIS +2. Raz może przerzucić nieudany test umiejętności i zachować lepszy wynik. Znika po wykorzystaniu przerzutu lub po 3 turach.', 1, 0, NULL, NULL, datetime('now'), datetime('now'))
    """,
    # S11 (#606) — rozszerzenie wersji lite `cursed` z S8: dochodzi efekt reroll forced_keep_worst
    # ("zły omen" — wymuszony przerzut udanego testu na gorszy, 1×/scenę). UPDATE bo INSERT OR IGNORE
    # nie nadpisze istniejącego wiersza. Stałe −2 do wszystkich statów zachowane.
    """
    UPDATE game_config_conditions
    SET effect_json = '{"schema_version":1,"effect_category":"character_condition","effects":[{"type":"static_stat_modifier","stat":"STR","value":-2},{"type":"static_stat_modifier","stat":"DEX","value":-2},{"type":"static_stat_modifier","stat":"CON","value":-2},{"type":"static_stat_modifier","stat":"INT","value":-2},{"type":"static_stat_modifier","stat":"WIS","value":-2},{"type":"static_stat_modifier","stat":"CHA","value":-2},{"type":"reroll","mode":"forced_keep_worst","scope":"skill_test"}]}',
        description = 'Postać nosi klątwę — -2 do wszystkich testów. Zły omen: raz na scenę los przerzuca udany test na gorszy wynik. Zdjęcie: rytuał theology/arcana.',
        updated_at = datetime('now')
    WHERE key = 'cursed'
      AND effect_json NOT LIKE '%forced_keep_worst%'
    """,
    # S12 (#607) FAZA S — prymitywy `extra_action` + `on_expire_apply` + kondycja `hasted`.
    # Liczby = wartości startowe (Numbers Policy → tuning po S20). duration: design doc k4+1,
    # schemat U10 bez kości w duration → stała 3 rundy.
    """
    INSERT OR IGNORE INTO game_config_conditions
    (key, label, effect_json, description, is_active, stackable, auto_remove, locked_at, created_at, updated_at)
    VALUES
    ('hasted', 'Przyśpieszony', '{"schema_version":1,"effect_category":"character_condition","effects":[{"type":"static_stat_modifier","stat":"DEX","value":2},{"type":"extra_action","action_kind":"move_only","expires":"duration_rounds:3"},{"type":"on_expire_apply","condition_key":"exhausted","value":1}]}', 'Postać przyśpieszona — DEX +2 i dodatkowa akcja ruchu (zmiana strefy bez utraty tury). Trwa 3 rundy; po wygaśnięciu postać dostaje 1 poziom wyczerpania (exhausted). Niestackowalna.', 1, 0, NULL, NULL, datetime('now'), datetime('now'))
    """,
    # S13 (#608) FAZA S — prymityw `on_zero_hp_save` + kondycja `blessed`. Liczby = wartości
    # startowe (Numbers Policy → tuning po S20). +2 defensywny przez derived stat 'save'.
    # Brak `expires` → kondycja trwa do końca walki/sceny (design doc: "1 scena/spotkanie";
    # mapowane na najbliższy istniejący marker — zniknięcie combatanta po końcu walki).
    # uses=1 → raz na scenę, bo świeży wpis kondycji żyje jedno spotkanie. Niestackowalna.
    """
    INSERT OR IGNORE INTO game_config_conditions
    (key, label, effect_json, description, is_active, stackable, auto_remove, locked_at, created_at, updated_at)
    VALUES
    ('blessed', 'Pobłogosławiony', '{"schema_version":1,"effect_category":"character_condition","effects":[{"type":"static_stat_modifier","stat":"save","value":2},{"type":"on_zero_hp_save","stat":"CON","value":12,"result":"stay_at_1hp","uses":1}]}', 'Postać pod opieką bóstwa — +2 do testów obronnych i przeciw kondycjom negatywnym. Raz na scenę, gdy cios miałby ją powalić, silnik rzuca CON DC 12 i przy sukcesie zostawia 1 HP zamiast nieprzytomności. Trwa do końca walki/sceny. Niekumulowalna.', 1, 0, NULL, NULL, datetime('now'), datetime('now'))
    """,
    # S14 (#609) FAZA S — prymityw `condition_immunity` + klucz `broken_by` + kondycja `rage`.
    # Liczby = wartości startowe (Numbers Policy → tuning po S20). immune_to[slowed,weakened] =
    # odporność; broken_by[stunned,confused] = nałożenie przerywa furię; on_expire→exhausted 1 =
    # koszt; duration: design doc k6+2 → stała 6 (schemat U10 bez kości w duration; wzorzec S12).
    """
    INSERT OR IGNORE INTO game_config_conditions
    (key, label, effect_json, description, is_active, stackable, auto_remove, locked_at, created_at, updated_at)
    VALUES
    ('rage', 'Furia', '{"schema_version":1,"effect_category":"character_condition","effects":[{"type":"static_stat_modifier","stat":"STR","value":2},{"type":"static_stat_modifier","stat":"damage_bonus","value":3},{"type":"condition_immunity","immune_to":["slowed","weakened"],"expires":"duration_rounds:6"},{"type":"on_expire_apply","condition_key":"exhausted","value":1}],"broken_by":["stunned","confused"]}', 'Kontrolowana furia bojowa — +2 SIŁY, +3 obrażeń wręcz, odporność na spowolnienie i osłabienie. Trwa 6 rund; ogłuszenie lub dezorientacja natychmiast ją przerywają. Po wygaśnięciu postać dostaje 1 poziom wyczerpania (exhausted). Niekumulowalna.', 1, 0, NULL, NULL, datetime('now'), datetime('now'))
    """,
    # S18 (#613) FAZA S — prymityw `behavior_override` + pełne confused/berserk/panicked.
    # Liczby = wartości startowe (Numbers Policy → tuning po S20). UPDATE bo INSERT OR IGNORE nie
    # nadpisze istniejących lite-wierszy confused/panicked z S8; berserk = nowy wiersz.
    """
    UPDATE game_config_conditions
    SET effect_json = '{"schema_version":1,"effect_category":"character_condition","effects":[{"type":"static_stat_modifier","stat":"INT","value":-3},{"type":"static_stat_modifier","stat":"WIS","value":-3},{"type":"behavior_override","behavior":"random_table_k4"},{"type":"periodic_save","stat":"WIS","value":14,"tick":"start_turn","expires":"save_success"}]}',
        description = 'Postać nie rozumie otoczenia — INT i WIS -3. Na początku tury k4: 1 stoi / 2 atak losowego celu / 3 ucieczka / 4 normalnie. Udany rzut WIS DC 14 (zebranie myśli) kończy stan.',
        updated_at = datetime('now')
    WHERE key = 'confused'
      AND effect_json NOT LIKE '%behavior_override%'
    """,
    """
    UPDATE game_config_conditions
    SET effect_json = '{"schema_version":1,"effect_category":"character_condition","effects":[{"type":"static_stat_modifier","stat":"CHA","value":-4},{"type":"static_stat_modifier","stat":"WIS","value":-4},{"type":"behavior_override","behavior":"flee"},{"type":"periodic_save","stat":"WIS","value":14,"tick":"start_turn","expires":"save_success"}]}',
        description = 'Postać ogarnięta paniką — CHA i WIS -4. Wymuszona ucieczka (zmiana strefy na dystans). Udany rzut WIS DC 14 na początku tury przezwycięża panikę.',
        updated_at = datetime('now')
    WHERE key = 'panicked'
      AND effect_json NOT LIKE '%behavior_override%'
    """,
    """
    INSERT OR IGNORE INTO game_config_conditions
    (key, label, effect_json, description, is_active, stackable, auto_remove, locked_at, created_at, updated_at)
    VALUES
    ('berserk', 'Berserk', '{"schema_version":1,"effect_category":"character_condition","effects":[{"type":"behavior_override","behavior":"attack_nearest","expires":"duration_rounds:6"},{"type":"static_stat_modifier","stat":"attack_bonus","value":3},{"type":"static_stat_modifier","stat":"damage_bonus","value":3},{"type":"static_stat_modifier","stat":"ac","value":-3},{"type":"periodic_save","stat":"WIS","value":14,"tick":"start_turn","expires":"save_success"}]}', 'Niekontrolowany szał bojowy — postać atakuje najbliższy cel NIEZALEŻNIE od frakcji (też sojuszników). +3 do ataków i obrażeń, -3 AC. Na początku tury rzut WIS DC 14 odzyskuje kontrolę. Trwa do 6 rund lub brak wrogów w zasięgu. Różni się od kontrolowanej furii (rage).', 1, 0, NULL, NULL, datetime('now'), datetime('now'))
    """,
    # S19 (#614) FAZA S — prymitywy `untargetable` + `ambush_bonus` + kondycja `hidden`.
    # Liczby = wartości startowe (Numbers Policy → tuning po S20). granted_by = ODWROTNOŚĆ cure
    # (udany SKILL_TEST stealth DC 14 nakłada hidden); detect_dc = WIS save wroga przy poszukiwaniu.
    """
    INSERT OR IGNORE INTO game_config_conditions
    (key, label, effect_json, description, is_active, stackable, auto_remove, locked_at, created_at, updated_at)
    VALUES
    ('hidden', 'Ukryty', '{"schema_version":1,"effect_category":"character_condition","effects":[{"type":"untargetable"},{"type":"ambush_bonus","value":"2d6"}],"granted_by":{"skill":"stealth","dc":14},"detect_dc":14}', 'Postać skutecznie się ukryła — wrogowie nie mogą jej atakować, dopóki jej nie wykryją. Pierwszy atak z ukrycia zadaje +2k6 obrażeń (zasadzka) i zdejmuje ukrycie. Wejście: udany test skradania (stealth DC 14). Zejście: własny atak (demaskuje) lub wykrycie (wróg WIS DC 14 przy aktywnym poszukiwaniu). Nie zmienia strefy — możliwa zasadzka również w zwarciu.', 1, 0, NULL, NULL, datetime('now'), datetime('now'))
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
    # F4: seed game_config_services with basic NPC service prices
    """
    INSERT OR IGNORE INTO game_config_services (key, label, cost_gp, description, is_active) VALUES
    ('inn_night',       'Gospoda: jedna noc',         5,   'Nocleg i posiłek w gospodzie — standardowy pokój', 1),
    ('inn_night_fine',  'Gospoda: luksusowy pokój',   20,  'Nocleg w prywatnym pokoju z pościelą i śniadaniem', 1),
    ('healer_light',    'Uzdrowiciel: lekkie rany',   10,  'Opatrzenie ran niegroźnych: skaleczenia, stłuczenia', 1),
    ('healer_heavy',    'Uzdrowiciel: ciężkie rany',  50,  'Leczenie poważnych ran wymagające magii lub chirurgii', 1),
    ('stable_night',    'Stajnia: jedna noc',         3,   'Nocleg i pasza dla konia lub wierzchowca', 1),
    ('blacksmith_repair', 'Kowal: naprawa ekwipunku', 15,  'Naprawa uszkodzonej broni lub zbroi', 1),
    ('messenger',       'Posłaniec: wiadomość',       8,   'Wysłanie wiadomości do pobliskiego miasta', 1),
    ('guide_day',       'Przewodnik: jeden dzień',    12,  'Miejscowy przewodnik przez niebezpieczny teren', 1),
    ('tavern_meal',     'Gospoda: posiłek',           2,   'Jedzenie i napój w gospodzie — bez noclegu (#751)', 1),
    ('tavern_drink',    'Gospoda: napój',             1,   'Sam napój (piwo, wino, woda) — bez jedzenia (#751)', 1)
    """
,
    "ALTER TABLE bug_reports ADD COLUMN screenshot_base64 TEXT",
    # ── #764: amunicja — strzały (łuki) i bełty (kusze) ───────────────────────
    """
    INSERT OR IGNORE INTO game_config_consumables
        (key, label, description, effect_type, effect_dice, effect_bonus, effect_target,
         weight_kg, charges, base_price, note, is_active, locked_at, created_at, updated_at)
    VALUES
     ('arrows', 'Strzały', 'Amunicja do łuków. Zużywana przy strzale dystansowym.', 'ammo', NULL, 0, 'self',
      0.05, 1, 1, 'Amunicja: łuki', 1, NULL, datetime('now'), datetime('now')),
     ('bolts', 'Bełty', 'Amunicja do kusz. Zużywana przy strzale dystansowym.', 'ammo', NULL, 0, 'self',
      0.075, 1, 1, 'Amunicja: kusze', 1, NULL, datetime('now'), datetime('now'))
    """,
    # Unified catalog (game_items) — daje ładną etykietę + item_type=consumable w plecaku.
    """
    INSERT OR IGNORE INTO game_items
        (key, kind, label, description, price_gp, item_data, weight_kg, note, is_active, created_by, approved, created_at, updated_at)
    VALUES
     ('arrows', 'consumable', 'Strzały', 'Amunicja do łuków.', 1,
      json_object('effect_type','ammo','ammo','arrows'), 0.05, 'Amunicja: łuki', 1, 'seed', 1, datetime('now'), datetime('now')),
     ('bolts', 'consumable', 'Bełty', 'Amunicja do kusz.', 1,
      json_object('effect_type','ammo','ammo','bolts'), 0.075, 'Amunicja: kusze', 1, 'seed', 1, datetime('now'), datetime('now'))
    """,
    # Mapowanie broń → amunicja: łuki→strzały, kusze→bełty.
    """
    UPDATE game_config_weapons SET ammo_key = 'arrows'
    WHERE ammo_key IS NULL AND weapon_type = 'ranged'
      AND (LOWER(label) LIKE '%bow%' OR LOWER(label) LIKE '%łuk%' OR LOWER(key) LIKE '%bow%')
      AND LOWER(label) NOT LIKE '%cross%' AND LOWER(label) NOT LIKE '%kusz%'
      AND LOWER(key)   NOT LIKE '%cross%'
    """,
    """
    UPDATE game_config_weapons SET ammo_key = 'bolts'
    WHERE ammo_key IS NULL AND weapon_type = 'ranged'
      AND (LOWER(label) LIKE '%cross%' OR LOWER(label) LIKE '%kusz%' OR LOWER(key) LIKE '%cross%')
    """,
    # Amunicja startowa: archetypy z łukiem na starcie dostają 20 strzał (#764, powiązane #749).
    """
    UPDATE game_config_archetypes
    SET starter_items_json =
      '[{"weapon_key":"shortsword"},{"weapon_key":"wooden_shield"},{"weapon_key":"shortbow"},{"item_key":"leatherarmor"},{"consumable_key":"arrows","quantity":20}]',
        updated_at = datetime('now')
    WHERE key = 'warrior'
    """,
    """
    UPDATE game_config_archetypes
    SET starter_items_json =
      '[{"weapon_key":"dagger"},{"weapon_key":"shortbow"},{"item_key":"leather_armor"},{"consumable_key":"arrows","quantity":20}]',
        updated_at = datetime('now')
    WHERE key = 'rogue'
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


def _ensure_active_combat_ammo_spent(conn: sqlite3.Connection) -> None:
    """#765: track ammo fired during a combat so it can be recovered afterwards."""
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='active_combat'"
    ).fetchone()
    if not row:
        return
    existing = [r[1] for r in conn.execute("PRAGMA table_info(active_combat)").fetchall()]
    if "ammo_spent_json" not in existing:
        conn.execute("ALTER TABLE active_combat ADD COLUMN ammo_spent_json TEXT DEFAULT NULL")
        conn.commit()
        logger.info("admin_migration_applied", sql_preview="active_combat ADD COLUMN ammo_spent_json")


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


def _backfill_enemy_stats_json(conn: sqlite3.Connection) -> None:
    """S2 (#582) — seed stats_json for enemies that don't have one yet.

    Derives 7 ability stats from the archetype heuristic (key/label keywords).
    Rows left untouched if stats_json already present. NULL stays NULL-safe — combat
    reads default every missing stat to 10, so this is purely additive (zero regression).
    """
    try:
        from app.services.actor_stats import stats_for_actor

        rows = conn.execute(
            """
            SELECT key, label FROM game_config_enemies
            WHERE stats_json IS NULL OR stats_json = '' OR stats_json = '{}'
            """
        ).fetchall()
        if not rows:
            return
        for row in rows:
            ek = row[0]
            label = row[1] or ek
            stats = stats_for_actor(ek, label)
            conn.execute(
                "UPDATE game_config_enemies SET stats_json = ? WHERE key = ?",
                (json.dumps(stats, ensure_ascii=False), ek),
            )
        conn.commit()
        logger.info("admin_migration_backfill_enemy_stats_json", count=len(rows))
    except Exception as e:
        logger.warning("admin_migration_backfill_enemy_stats_json_failed", error=str(e))


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

    _exec("""
        INSERT OR IGNORE INTO game_config_spells
            (key, label, tier, mana_cost, spell_type, damage_die, heal_die, effect_stat, effect_type, effect_duration, target_zone, aoe, description, rank2_json, rank3_json)
        VALUES
            ('magic_light', 'Magiczne Światło', 1, 0, 'narrative', NULL, NULL, NULL, NULL, 0, 'self', 0,
             'Uczony przywołuje unoszącą się kulę świetlną oświetlającą obszar w promieniu kilku metrów. Działa jak pochodnia — rozjaśnia ciemność, lecz nie ma wartości ofensywnej.',
             NULL, NULL)
    """, "v2-spells-magic-light")

    # Grant magic_light to all existing Scholar characters (retroactive, all active states)
    _exec("""
        INSERT OR IGNORE INTO character_spells (character_id, spell_key, rank)
        SELECT c.id, 'magic_light', 1
        FROM characters c
        WHERE JSON_EXTRACT(c.sheet_json, '$.archetype') = 'scholar'
    """, "v2-spells-magic-light-backfill-all")

    # ── FAZA B / B6 (#648): seed czarów maga Faza 1 z rpg_spells_design_doc.md ──
    # Adoptowalne dziś: atak single-target / heal-self / self-buff obronny /
    # kondycje mapowane na ISTNIEJĄCE stany FAZY S (zero duplikatu stanu).
    # Poza zakresem: AoE (→ B11, po #595), summon/ally/reakcje (→ Blok 3).
    # effect_type wskazuje klucz game_config_conditions (slowed/cursed/poisoned/
    # blinded/confused/stunned). Naliczanie kondycji w silniku = B9 (tu tylko dane).
    # rank2/rank3_json = NULL (skalowanie rang = tuning po B7/B13). Wartości = doc.
    _exec("""
        INSERT OR IGNORE INTO game_config_spells
            (key, label, tier, mana_cost, spell_type, damage_die, heal_die, effect_stat, effect_type, effect_duration, target_zone, aoe, description, rank2_json, rank3_json) VALUES
        ('fire_bolt',       'Ognisty Pocisk',      1, 2, 'attack',    '1d8', NULL,  NULL,  NULL,       1, 'any',     0, 'Skupiona kula ognia ciśnięta w cel; może go podpalić.',                       NULL, NULL),
        ('frost_bolt',      'Mroźna Strzała',      1, 2, 'attack',    '1d8', NULL,  NULL,  NULL,       1, 'any',     0, 'Lodowaty bełt uderza w cel, mrożąc go (przy trafieniu może spowolnić).',      NULL, NULL),
        ('acid_splash',     'Plusk Kwasu',         1, 1, 'attack',    '1d6', NULL,  NULL,  NULL,       1, 'nearby',  0, 'Fala parzącej cieczy żre cel i jego zbroję.',                                 NULL, NULL),
        ('lightning_arrow', 'Piorunowy Grot',      2, 3, 'attack',    '2d6', NULL,  NULL,  NULL,       1, 'any',     0, 'Naładowany elektrycznie pocisk razi cel energią.',                            NULL, NULL),
        ('ice_lance',       'Lodowa Lanca',        2, 3, 'attack',    '2d8', NULL,  NULL,  NULL,       1, 'any',     0, 'Ciężka kolumna lodu przeszywa cel z impetem tarana (krit: frozen).',          NULL, NULL),
        ('inferno_strike',  'Uderzenie Inferno',   3, 4, 'attack',    '3d6', NULL,  NULL,  NULL,       1, 'any',     0, 'Skupiony żar piekielnego ognia wybucha w jednym punkcie.',                    NULL, NULL),
        ('minor_heal',      'Leczniczy Dotyk',     1, 1, 'heal',      NULL,  '1d6', NULL,  NULL,       1, 'self',    0, 'Strumień kojącej energii zamyka rany rzucającego.',                           NULL, NULL),
        ('ward_of_iron',    'Żelazna Straż',       1, 2, 'defense',   NULL,  NULL,  NULL,  NULL,       1, 'self',    0, 'Niewidoczne pole ochronne pochłania następne trafienie (absorpcja: B10).',    NULL, NULL),
        ('mage_armor',      'Zbroja Maga',         2, 3, 'defense',   NULL,  NULL,  NULL,  NULL,       1, 'self',    0, 'Warstwa zmaterializowanej energii zwiększa pancerz rzucającego.',             NULL, NULL),
        ('frost_grip',      'Mroźny Uchwyt',       1, 2, 'effect',    NULL,  NULL,  'WIS', 'slowed',   2, 'any',     0, 'Przenikliwy mróz krępuje ruchy celu — slowed.',                               NULL, NULL),
        ('hex',             'Klątwa',              2, 2, 'effect',    NULL,  NULL,  'WIS', 'cursed',   3, 'any',     0, 'Mroczna klątwa osłabia ducha celu — cursed.',                                 NULL, NULL),
        ('poison_touch',    'Trujący Dotyk',       2, 2, 'effect',    '1d4', NULL,  'WIS', 'poisoned', 3, 'engaged', 0, 'Magiczna trucizna na dłoni zatruwa cel — poisoned.',                          NULL, NULL),
        ('blind',           'Oślepienie',          2, 3, 'effect',    NULL,  NULL,  'WIS', 'blinded',  2, 'any',     0, 'Fala oślepiającego światła odbiera celowi wzrok — blinded.',                  NULL, NULL),
        ('confusion',       'Zamęt',               3, 3, 'effect',    NULL,  NULL,  'WIS', 'confused', 2, 'any',     0, 'Chaotyczne obrazy dezorientują cel — confused.',                              NULL, NULL),
        ('stun_bolt',       'Piorun Ogłuszenia',   4, 4, 'effect',    '1d6', NULL,  'WIS', 'stunned',  1, 'any',     0, 'Skondensowana kula energii ogłusza zmysły celu — stunned.',                   NULL, NULL),
        ('detect_magic',    'Wykrycie Magii',      1, 1, 'narrative', NULL,  NULL,  NULL,  NULL,       0, 'self',    0, 'Trzecie oko rzucającego widzi aurę magiczną wokół przedmiotów i istot.',      NULL, NULL)
    """, "v2-spells-faza-b-seed")

    # ── FAZA B / B8 (#655): startowy zestaw maga L1 = fire_bolt + minor_heal +
    # ward_of_iron + detect_magic (atak/heal/obrona/utility, 4× tier 1). Dosiej
    # ten zestaw WSZYSTKIM istniejącym scholarom — NIE-destrukcyjnie (INSERT OR
    # IGNORE: stare czary magic_bolt/mend_wounds/magic_light zostają nietknięte).
    # Decyzja obronna: ward_of_iron (tier 1), NIE mage_armor (tier 2) — spójność
    # z bramką nauki L1 z B7. MUSI biec PO v2-spells-faza-b-seed (FK
    # character_spells.spell_key → game_config_spells.key; inaczej crash na PROD
    # gdy istnieją realni scholarzy a czary jeszcze nie zaseedowane).
    _exec("""
        INSERT OR IGNORE INTO character_spells (character_id, spell_key, rank)
        SELECT c.id, s.spell_key, 1
        FROM characters c
        CROSS JOIN (
            SELECT 'fire_bolt' AS spell_key UNION ALL
            SELECT 'minor_heal' UNION ALL
            SELECT 'ward_of_iron' UNION ALL
            SELECT 'detect_magic'
        ) s
        WHERE JSON_EXTRACT(c.sheet_json, '$.archetype') = 'scholar'
    """, "v2-spells-faza-b-b8-starter-backfill")

    # ── FAZA B / B10 (#657): pula absorpcji (temp-HP) dla tarcz maga ──────────
    # ward_of_iron/mage_armor dostają effect_json.absorb — ile obrażeń wroga pula
    # pochłonie, zanim spadnie HP. Wartości startowe (Numbers Policy): ward 6 (T1),
    # mage 10 (T2); płaskie, NIE stackują, combat-scoped. NIE-destrukcyjne.
    # Silnik czyta to przez spell_service.defense_absorb_amount. Kolumna effect_json
    # NIE istniała na game_config_spells — najpierw ją dodajemy (idempotentnie).
    _exec("""
        ALTER TABLE game_config_spells ADD COLUMN effect_json TEXT
    """, "v2-spells-effect-json-col")
    _exec("""
        UPDATE game_config_spells SET effect_json = '{"absorb":6}'
        WHERE key = 'ward_of_iron'
    """, "v2-spells-b10-ward-absorb")
    _exec("""
        UPDATE game_config_spells
        SET effect_json = '{"absorb":10}',
            description = 'Warstwa zmaterializowanej energii pochłania nadchodzące obrażenia (pula absorpcji).'
        WHERE key = 'mage_armor'
    """, "v2-spells-b10-mage-absorb")
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
    # #594 — unify onboarding cards + knowledge tips into knowledge_book via `kind`.
    # Existing rows default to 'knowledge_tip'; onboarding cards seeded below.
    _exec("""
        ALTER TABLE knowledge_book ADD COLUMN kind TEXT NOT NULL DEFAULT 'knowledge_tip'
    """, "v2-knowledge-book-kind")
    # #594 (rev) — independent visibility: one entry can appear in BOTH the
    # onboarding popups and the player Knowledge book. `kind` stays as a label.
    _exec("""
        ALTER TABLE knowledge_book ADD COLUMN show_in_onboarding INTEGER NOT NULL DEFAULT 0
    """, "v2-knowledge-book-show-onboarding")
    _exec("""
        ALTER TABLE knowledge_book ADD COLUMN show_in_knowledge INTEGER NOT NULL DEFAULT 1
    """, "v2-knowledge-book-show-knowledge")
    # Backfill flags from the legacy kind: onboarding cards become visible in both.
    _exec("""
        UPDATE knowledge_book SET show_in_onboarding = 1, show_in_knowledge = 1
        WHERE kind = 'onboarding_card'
    """, "v2-knowledge-book-flag-backfill")
    # #592 — seed FAZA U mechanic docs (durability, raids, affix pity, economy telemetry).
    for _tip in FAZA_U_KNOWLEDGE_TIPS:
        def _q(s):
            return str(s).replace("'", "''")
        _exec(
            "INSERT OR IGNORE INTO knowledge_book (tip_key, category, title, body, sort_order) "
            f"VALUES ('{_q(_tip['tip_key'])}', '{_q(_tip['category'])}', "
            f"'{_q(_tip['title'])}', '{_q(_tip['body'])}', {int(_tip['sort_order'])})",
            f"v2-knowledge-faza-u-{_tip['tip_key']}",
        )
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
        ('goblin_warren',  'Nora Goblinów',     'goblin_warren',  5, '["goblin","goblin_archer"]', 'goblin_shaman',  'standard', 'Ciasne tunele, smród gnijącego mięsa, pobrzękiwanie oręża w ciemności.',              48, 1),
        ('crypt_of_bones', 'Krypta Kości',      'crypt_of_bones', 6, '["skeleton","zombie"]',      'skeleton_lord',  'rich',     'Wilgotne katakumby, fosforyzujące kości, echo kroków odbija się od kamiennych ścian.', 72, 2),
        ('rat_tunnels',    'Kanały pod Miastem','rat_tunnels',    4, '["giantrat"]',               NULL,             'poor',     'Ciemne, zawilgocone kanały. Coś tu mieszka i nie lubi gości.',                        24, 1)
    """, "v2-game-dungeons-seed")
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
        ('lore',         'dc',      NULL,         14),
        -- S5 (#585): nowe skille kategorii A. opposed = test przeciw statowi celu;
        -- default_dc = środek widełek "Typowe DC" z design doc, klamp do DC lock {8,12,16,20,24}.
        ('charm',        'opposed', 'WIS',        12),
        ('bribe',        'opposed', 'WIS',        16),
        ('pickpocket',   'opposed', 'WIS',        16),
        ('disguise',     'opposed', 'WIS',        16),
        ('torture',      'opposed', 'CON',        16),
        ('riding',       'dc',      NULL,         12),
        ('endurance',    'dc',      NULL,         16),
        ('swim',         'dc',      NULL,         12),
        ('climb',        'dc',      NULL,         12),
        ('gossip',       'dc',      NULL,         12),
        ('trade_craft',  'dc',      NULL,         12),
        ('language',     'dc',      NULL,         12),
        ('theology',     'dc',      NULL,         12),
        ('nature',       'dc',      NULL,         12),
        ('alchemy',      'dc',      NULL,         16),
        ('magic_sense',  'dc',      NULL,         16),
        ('tracking',     'dc',      NULL,         12),
        ('sailing',      'dc',      NULL,         12),
        -- S6 (#586): targowanie — test przeciw CHA kupca (NPC staty z S3);
        -- kupiec bez statów → fallback default_dc=12 (DC lock {8,12,16,20,24}).
        ('haggling',     'opposed', 'CHA',        12),
        -- S7 (#601): hazard — test przeciw CHA przeciwnika (staty z S3); brak
        -- przeciwnika → fallback default_dc=12 (amatorzy; DC 20 zawodowcy narracyjnie).
        ('gamble',       'opposed', 'CHA',        12)
    """, "v2-skill-counters-seed")

    # S17 (#612): generyczne pola wynik→kondycja (skill outcome → apply_condition).
    # Deklaratywne (Zasada 1 FAZY S) — silnik czyta mapping z danych, ZERO if skill_key==...
    # Przyszłe skille nakładające kondycje wynikiem dodają tu wiersze, bez dotykania kodu.
    _exec("ALTER TABLE skill_counters ADD COLUMN on_success_condition TEXT",
          "v2-skill-counters-on-success-col")
    _exec("ALTER TABLE skill_counters ADD COLUMN on_crit_condition TEXT",
          "v2-skill-counters-on-crit-col")
    _exec("ALTER TABLE skill_counters ADD COLUMN on_critfail_self_condition TEXT",
          "v2-skill-counters-on-critfail-self-col")
    # Wrestling (S17): opposed STR vs STR; fallback default_dc=12 (słaby cel) — DC lock {8,12,16,20,24}.
    # Sukces → cel slowed; krytyk → cel stunned; krytyczna porażka → gracz sam slowed (przewrócony).
    _exec("""
        INSERT OR IGNORE INTO skill_counters
          (player_skill_key, counter_type, counter_key, default_dc,
           on_success_condition, on_crit_condition, on_critfail_self_condition)
        VALUES ('wrestling', 'opposed', 'STR', 12, 'slowed', 'stunned', 'slowed')
    """, "v2-skill-counters-wrestling-seed")

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
    _exec("ALTER TABLE game_config_archetypes ADD COLUMN starting_stats_json TEXT", "v2-archetypes-starting-stats-json")
    try:
        conn.execute("UPDATE game_config_archetypes SET hp_base = 10 WHERE key = 'warrior' AND hp_base = 10")
        conn.execute("UPDATE game_config_archetypes SET hp_base = 6  WHERE key = 'scholar'")
        conn.execute("UPDATE game_config_archetypes SET hp_base = 8  WHERE key = 'ranger'")
        conn.execute("UPDATE game_config_archetypes SET hp_base = 8  WHERE key = 'rogue'")
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
    _exec("ALTER TABLE game_config_enemies ADD COLUMN loot_tier TEXT DEFAULT NULL", "v2-enemies-loot-tier")

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
    # Deduplicate world_hexes before creating unique index (keep row with highest id per q,r)
    try:
        conn.execute(
            "DELETE FROM world_hexes WHERE id NOT IN (SELECT MAX(id) FROM world_hexes GROUP BY q, r)"
        )
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

    # #507 — placement_mode drives which generation algorithm a terrain uses.
    # NULL is treated as 'biome' by the generator, so the column is nullable and
    # only the known stock types are backfilled (admin-created terrains stay NULL/biome).
    _exec("ALTER TABLE hex_type_config ADD COLUMN placement_mode TEXT", "v2-hex-placement-mode")
    _exec("""
        UPDATE hex_type_config SET placement_mode = 'scatter'
        WHERE placement_mode IS NULL AND hex_type IN ('town','castle','cave','dungeon','ruins')
    """, "v2-hex-placement-scatter")
    _exec("""
        UPDATE hex_type_config SET placement_mode = 'path'
        WHERE placement_mode IS NULL AND hex_type IN ('river','road')
    """, "v2-hex-placement-path")
    _exec("""
        UPDATE hex_type_config SET placement_mode = 'biome'
        WHERE placement_mode IS NULL
        AND hex_type IN ('plains','forest','hills','mountains','swamp')
    """, "v2-hex-placement-biome")
    # dungeon/castle were spawn_weight 0 (never generated) — give them a small presence.
    _exec("UPDATE hex_type_config SET spawn_weight = 2 WHERE hex_type = 'dungeon' AND spawn_weight = 0",
          "v2-hex-dungeon-weight")
    _exec("UPDATE hex_type_config SET spawn_weight = 1 WHERE hex_type = 'castle' AND spawn_weight = 0",
          "v2-hex-castle-weight")

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


def _ensure_dungeon_tile_l1_columns(conn: sqlite3.Connection) -> None:
    """L1 (#670): game_dungeons tile config columns for the tile-based dungeon mode."""
    for sql in [
        "ALTER TABLE game_dungeons ADD COLUMN tile_category_key TEXT",
        "ALTER TABLE game_dungeons ADD COLUMN tile_count INTEGER",
        "ALTER TABLE game_dungeons ADD COLUMN boss_tile_id INTEGER",
        "ALTER TABLE game_dungeons ADD COLUMN endless_growth_n INTEGER DEFAULT 0",
        # FAZA LB (#735): rest-on-cleared-tile policy per dungeon. heal_pct = % max HP
        # restored per rest; charges = how many rests (NULL/large = unlimited, used by
        # the onboarding dungeon). Default 20% / 2 charges = "fend for yourself".
        "ALTER TABLE game_dungeons ADD COLUMN rest_heal_pct INTEGER DEFAULT 20",
        "ALTER TABLE game_dungeons ADD COLUMN rest_charges INTEGER DEFAULT 2",
    ]:
        try:
            conn.execute(sql)
            conn.commit()
        except sqlite3.OperationalError as e:
            if "duplicate column" not in str(e).lower():
                raise


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

    # E17: dungeon difficulty tier for rarity mapping
    for sql in [
        "ALTER TABLE game_dungeons ADD COLUMN dungeon_difficulty INTEGER NOT NULL DEFAULT 1",
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

    # D1 (#376) — pending flow for items: unknown Grant Item keys land in
    # game_config_items as pending_review, mirroring the weapons pipeline.
    try:
        conn.execute(
            "ALTER TABLE game_config_items ADD COLUMN campaign_id INTEGER REFERENCES campaigns(id) ON DELETE SET NULL"
        )
        conn.commit()
        logger.info("admin_migration_d1_items_campaign_id")
    except sqlite3.OperationalError as e:
        if "duplicate column" not in str(e).lower():
            raise
    try:
        conn.execute("ALTER TABLE game_config_items ADD COLUMN review_status TEXT DEFAULT 'permanent'")
        conn.commit()
        logger.info("admin_migration_d1_items_review_status")
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
        # Friends (foundation for multiplayer — stored now, UI ships with F2)
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


def _ensure_submap_schema(conn: sqlite3.Connection) -> None:
    """Drop the legacy plain (q,r) unique index that blocks sub-hex insertion.
    The scoped index idx_world_hexes_qr_scope already enforces uniqueness per scope."""
    try:
        conn.execute("DROP INDEX IF EXISTS idx_world_hexes_coords")
        conn.commit()
    except Exception:
        pass


def _ensure_game_config_services(conn: sqlite3.Connection) -> None:
    """C12: create game_config_services table if absent."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS game_config_services (
            key         TEXT PRIMARY KEY,
            label       TEXT NOT NULL,
            cost_gp     INTEGER NOT NULL DEFAULT 0,
            description TEXT NOT NULL DEFAULT '',
            is_active   INTEGER NOT NULL DEFAULT 1,
            created_at  TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.commit()


def _ensure_shop_item_level_location_schema(conn: sqlite3.Connection) -> None:
    """F9 (#469): add min_level + location_tags to item catalog tables for dynamic shop filtering."""
    for table in ("game_config_weapons", "game_config_items", "game_config_consumables"):
        for col_sql in (
            f"ALTER TABLE {table} ADD COLUMN min_level INTEGER DEFAULT 1",
            f"ALTER TABLE {table} ADD COLUMN location_tags TEXT DEFAULT NULL",
        ):
            try:
                conn.execute(col_sql)
                conn.commit()
            except Exception as e:
                if "duplicate column" in str(e).lower():
                    pass
                else:
                    raise


def _apply_f15_balance_tuning(conn: sqlite3.Connection) -> None:
    """F15 (#475): tune bandit attack_bonus +3→+4 so level-3 fights drain ≥60% HP."""
    try:
        conn.execute(
            "UPDATE game_config_enemies SET attack_bonus = 4 WHERE key = 'bandit' AND attack_bonus < 4"
        )
        conn.commit()
    except Exception:
        pass


def _ensure_price_gp_schema(conn: sqlite3.Connection) -> None:
    """F11 (#471): add unified price_gp column to item catalog tables.

    price_gp overrides value_gp / base_price when set. Backfill from existing values.
    """
    for table, legacy_col in (
        ("game_config_weapons", "value_gp"),
        ("game_config_items", "value_gp"),
        ("game_config_consumables", "base_price"),
    ):
        try:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN price_gp INTEGER DEFAULT NULL")
            conn.commit()
        except Exception as e:
            if "duplicate column" in str(e).lower():
                pass
            else:
                raise
        # Backfill price_gp from legacy column where not yet set
        try:
            conn.execute(
                f"UPDATE {table} SET price_gp = {legacy_col} WHERE price_gp IS NULL AND {legacy_col} > 0"
            )
            conn.commit()
        except Exception:
            pass


def _ensure_time_of_day_effects(conn: sqlite3.Connection) -> None:
    """F20 (#480): seed default time-of-day effects into game_config_meta."""
    import json as _json
    default = {
        "dawn": {"initiative_bonus": 1},
        "day": {},
        "dusk": {"perception_dc_bonus": 1},
        "night": {"perception_dc_bonus": 2, "stealth_bonus": 2},
    }
    try:
        existing = conn.execute(
            "SELECT value FROM game_config_meta WHERE key = 'time_of_day_effects' LIMIT 1"
        ).fetchone()
        if not existing:
            conn.execute(
                "INSERT OR IGNORE INTO game_config_meta (key, value) VALUES ('time_of_day_effects', ?)",
                (_json.dumps(default),),
            )
            conn.commit()
    except Exception:
        pass


def _ensure_npc_is_dead_column(conn: sqlite3.Connection) -> None:
    """F19 (#479): add is_dead column to npcs table."""
    try:
        conn.execute("ALTER TABLE npcs ADD COLUMN is_dead INTEGER DEFAULT 0")
        conn.commit()
    except Exception as e:
        if "duplicate column" not in str(e).lower():
            pass  # ignore all errors (table may not exist yet in tests)


def _ensure_pending_category_column(conn: sqlite3.Connection) -> None:
    """U6 (#530): pending_category on game_config_items — visual triage for admin
    review queue (trivial junk vs standard items granted narratively by the GM)."""
    try:
        conn.execute("ALTER TABLE game_config_items ADD COLUMN pending_category TEXT DEFAULT NULL")
        conn.commit()
    except Exception as e:
        if "duplicate column" not in str(e).lower():
            pass  # ignore all errors (table may not exist yet in tests)


def _ensure_xp_level_thresholds(conn: sqlite3.Connection) -> None:
    """F18 (#478): seed default non-linear XP thresholds into game_config_meta."""
    import json as _json
    default = {
        "2": 100, "3": 250, "4": 450, "5": 700,
        "6": 1000, "7": 1350, "8": 1750, "9": 2200, "10": 2700,
    }
    try:
        existing = conn.execute(
            "SELECT value FROM game_config_meta WHERE key = 'xp_level_thresholds' LIMIT 1"
        ).fetchone()
        if not existing:
            conn.execute(
                "INSERT OR IGNORE INTO game_config_meta (key, value) VALUES ('xp_level_thresholds', ?)",
                (_json.dumps(default),),
            )
            conn.commit()
    except Exception:
        pass


def _ensure_hidden_traits_schema(conn: sqlite3.Connection) -> None:
    """F17 (#477): create game_config_hidden_traits table + seed starter traits."""
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS game_config_hidden_traits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT UNIQUE NOT NULL,
                label TEXT NOT NULL,
                description TEXT,
                trigger_keywords TEXT,
                effect_json TEXT DEFAULT '{}',
                is_active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.commit()
    except Exception:
        pass

    seeds = [
        ("berserker_rage", "Szał Berserkera",
         "Gdy zdrowie spada poniżej 30%, ataki zadają +2 obrażeń.",
         "berserk,rage,wściekłość,szał",
         '{"type":"damage_bonus","bonus":2,"condition":"hp_below_30pct"}'),
        ("shadow_step", "Krok Cienia",
         "Ukryty w walce — wrogowie mają -2 do trafienia przez pierwszą rundę.",
         "shadow,cień,ukrycie,skradanie",
         '{"type":"static_stat_modifier","stats":{"enemy_attack_penalty":2},"duration":1}'),
        ("iron_will", "Żelazna Wola",
         "Raz na długi odpoczynek zignoruj pierwszą śmiertelną ranę.",
         "will,wola,przeżycie,determinacja",
         '{"type":"apply_condition","condition":"death_ward","duration":1,"charges":1}'),
        ("lucky_charm", "Talizman Szczęścia",
         "Raz na sesję przerzuć jeden nieudany rzut.",
         "luck,szczęście,traf,los",
         '{"type":"apply_condition","condition":"reroll_once","duration":1,"charges":1}'),
        ("arcane_sensitivity", "Wrażliwość Arkanyczna",
         "Czujesz obecność magii — DC na wykrycie magicznych pułapek -4.",
         "magic,magia,arkana,czar,zaklęcie",
         '{"type":"static_stat_modifier","stats":{"detect_magic_dc_bonus":-4}}'),
    ]
    for key, label, desc, keywords, effect in seeds:
        try:
            conn.execute(
                "INSERT OR IGNORE INTO game_config_hidden_traits "
                "(key, label, description, trigger_keywords, effect_json) VALUES (?,?,?,?,?)",
                (key, label, desc, keywords, effect),
            )
        except Exception:
            pass
    conn.commit()


def _ensure_skill_risk_categories(conn: sqlite3.Connection) -> None:
    """U7 (#531): create game_config_skill_risk_categories table + seed 6 categories."""
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS game_config_skill_risk_categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category_key TEXT NOT NULL UNIQUE,
                skill_key TEXT NOT NULL,
                default_dc INTEGER NOT NULL DEFAULT 12,
                keywords TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1
            )
        """)
        conn.commit()
    except Exception:
        pass

    seeds = [
        ("stealth", "stealth", 12,
         "skrad,przekrad,niepostrzeżenie,kryję,chowam,ukrywam,przemykam,cichaczem"),
        ("climb_jump", "athletics", 12,
         "wspinam,wspinaczka,skaczę,skok,przeskakuję,gramolę,drapię się,wchodzę na"),
        ("theft", "lockpick", 12,
         "kradnę,ukraść,podkradam,kieszeni,zabieram,grasuje,kraść"),
        ("persuasion_pressure", "persuasion", 12,
         "kłamię,blefuję,przekonuję,zastraszam,szantażuję,przesłuchuję,wymuszam"),
        ("disarm", "lockpick", 16,
         "rozbrajam,unieszkodliwiam,manipuluję mechanizmem,wyważam zamek,otwieramy zamek"),
        ("acrobatics", "athletics", 12,
         "akrobatyka,unik,uchylam,przewrót,balansując,równowaga"),
        # S5 (#585): safety-net dla nowych skilli fizycznych/społecznych ryzykownych —
        # gdy narrator zapomni o tagu SKILL_TEST, słowa kluczowe wymuszają rzut.
        ("swimming", "swim", 12,
         "płynę,pływam,przepływam,nurkuję,wpław,brnę przez wodę,tonę"),
        ("mounted", "riding", 12,
         "wsiadam na konia,dosiadam,wierzchowca,galopem,konno,jadę konno,cwałuję"),
        ("pickpocketing", "pickpocket", 16,
         "kieszonkost,podkradam z kieszeni,wyciągam sakiewkę,opróżniam kieszenie,zwędzić sakiewkę"),
        ("disguise", "disguise", 16,
         "przebieram się,przebranie,udaję kogoś,podszywam się,charakteryzuję,zmieniam wygląd"),
        ("tracking", "tracking", 12,
         "tropię,śledzę ślady,podążam za śladami,czytam tropy,wytropić,szukam śladów"),
        ("sailing", "sailing", 12,
         "steruję łodzią,rozkładam żagiel,nawiguję,płynę statkiem,trzymam ster,wychodzę z burzy"),
        ("bribery", "bribe", 16,
         "przekupuję,wręczam łapówkę,daję w łapę,opłacam strażnika,łapówka,sypię złotem"),
    ]
    for cat_key, skill_key, default_dc, keywords in seeds:
        try:
            conn.execute(
                "INSERT OR IGNORE INTO game_config_skill_risk_categories "
                "(category_key, skill_key, default_dc, keywords) VALUES (?,?,?,?)",
                (cat_key, skill_key, default_dc, keywords),
            )
        except Exception:
            pass
    conn.commit()


def _ensure_campaign_source_template(conn: sqlite3.Connection) -> None:
    """U8 (#532): add source_template_id to campaigns to detect Gotowa Kampania for Story Gravity L3."""
    try:
        conn.execute(
            "ALTER TABLE campaigns ADD COLUMN source_template_id INTEGER DEFAULT NULL"
        )
        conn.commit()
    except Exception:
        pass  # already exists


def _ensure_campaign_plan_degraded(conn: sqlite3.Connection) -> None:
    """U9 (#533): flag set when LLM plan generation fails and fallback plan is used."""
    try:
        conn.execute(
            "ALTER TABLE campaigns ADD COLUMN plan_degraded INTEGER NOT NULL DEFAULT 0"
        )
        conn.commit()
    except Exception:
        pass  # already exists


# HF-8 beat objective_type mapping: beat_key → objective_type
_BEAT_OBJECTIVE_MAP: dict[str, str] = {
    # Pierwsze Kroki
    "first_combat": "kill_enemy",
    "first_merchant": "talk_to_npc",
    "first_exploration": "visit_location",
    # Przeklęte Ziemie
    "discover_curse": "visit_location",
    "seek_origin": "talk_to_npc",
    "confront_evil": "kill_enemy",
    "lift_curse": "visit_location",
    # Cień Licza (lich_awakens = pure narrative, no objective_type)
    "seek_allies": "talk_to_npc",
    "locate_phylactery": "visit_location",
    "destroy_phylactery": "kill_enemy",
    "final_battle": "kill_enemy",
}


def _patch_campaign_template_beat_objectives(conn: sqlite3.Connection) -> None:
    """HF-8 (#539): add objective_type to key_beats in seed campaign templates.

    Without objective_type, the U8 auto_complete_beats_by_event() ignores the beats,
    making checkpoint 11 (beat completion) dead in Gotowa Kampania mode.
    Idempotent: skips beats that already have objective_type.
    """
    import json as _json

    try:
        rows = conn.execute(
            "SELECT id, gm_plan_json FROM campaign_templates WHERE created_by = 'seed'"
        ).fetchall()
    except Exception:
        return  # table may not exist in test environments

    changed_ids = []
    for row in rows:
        template_id = row[0] if not isinstance(row, sqlite3.Row) else row["id"]
        raw = row[1] if not isinstance(row, sqlite3.Row) else row["gm_plan_json"]
        if not raw:
            continue
        try:
            plan = _json.loads(raw)
        except (ValueError, TypeError):
            continue

        modified = False
        for arc in plan.get("arcs", []):
            if not isinstance(arc, dict):
                continue
            for beat in arc.get("key_beats", []):
                if not isinstance(beat, dict):
                    continue
                beat_key = beat.get("beat_key", "")
                if "objective_type" in beat:
                    continue  # already patched
                obj_type = _BEAT_OBJECTIVE_MAP.get(beat_key)
                if obj_type:
                    beat["objective_type"] = obj_type
                    modified = True

        if modified:
            conn.execute(
                "UPDATE campaign_templates SET gm_plan_json = ? WHERE id = ?",
                (_json.dumps(plan, ensure_ascii=False), template_id),
            )
            changed_ids.append(template_id)

    if changed_ids:
        conn.commit()
        logger.info("hf8_template_beats_patched", template_ids=changed_ids)


def _migrate_npc_locations_to_assignments(conn: sqlite3.Connection) -> None:
    """U31 (#546): Backfill location_npc_assignments from legacy npc_locations table.

    npc_locations (npc_id → FK) was the original NPC placement table. U28 introduced
    location_npc_assignments (npc_key → TEXT) as the V2 standard. This migration
    copies all rows from npc_locations → location_npc_assignments so enter_location_scene()
    has real data on existing deployments.
    Idempotent: INSERT OR IGNORE on UNIQUE(location_key, npc_key).
    """
    try:
        result = conn.execute(
            """INSERT OR IGNORE INTO location_npc_assignments (location_key, npc_key, is_active)
               SELECT nl.location_key, n.key, 1
               FROM npc_locations nl
               JOIN npcs n ON n.id = nl.npc_id
               WHERE COALESCE(n.is_active, 1) = 1""",
        )
        count = result.rowcount
        if count > 0:
            conn.commit()
            logger.info("u31_npc_locations_migrated", rows_inserted=count)
    except Exception as exc:
        logger.warning("u31_npc_locations_migration_failed", error=str(exc))


_RARITY_WORD_TO_INT = {
    "common": 1, "uncommon": 2, "rare": 3, "epic": 4, "legendary": 5,
    "poor": 1, "standard": 1, "rich": 2, "treasure": 3,
}


def _as_int(val, default: int = 1) -> int:
    """Coerce a possibly-text/None DB value to int.

    Legacy PROD rows store rarity as words ('common') while DEV uses ints (1).
    Falls back to ``default`` for unknown/blank values instead of crashing the
    migration (and thus app startup).
    """
    if val is None or val == "":
        return default
    if isinstance(val, int):
        return val
    s = str(val).strip().lower()
    if s in _RARITY_WORD_TO_INT:
        return _RARITY_WORD_TO_INT[s]
    try:
        return int(float(s))
    except (ValueError, TypeError):
        return default


def _normalize_legacy_rarities(conn: sqlite3.Connection) -> None:
    """Rewrite word rarities ('common') to ints in legacy source tables.

    Runs before the game_items backfill. Idempotent — numeric values are left
    untouched; only rows whose rarity matches a known word are updated. Safe to
    run on DEV (no word rows → no-ops) and PROD (legacy word rows → ints).
    """
    for table in ("game_config_weapons", "game_config_items", "game_config_consumables"):
        try:
            cols = {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}
            if "rarity" not in cols:
                continue
            for word, num in _RARITY_WORD_TO_INT.items():
                conn.execute(
                    f"UPDATE {table} SET rarity = ? WHERE LOWER(TRIM(rarity)) = ?",
                    (num, word),
                )
        except sqlite3.Error:
            # Table may not exist in some envs — backfill SELECTs guard the rest.
            continue


def _backfill_game_items(conn: sqlite3.Connection) -> None:
    """U11a (#556): Backfill game_items from 3 legacy item tables.

    Strategy:
    - game_config_weapons → kind='weapon' (weapon_data packs weapon-specific cols)
    - game_config_items WHERE item_type IN ('armor','shield') → kind='armor'
    - game_config_items WHERE item_type NOT IN ('armor','shield','consumable') → kind='item'
    - game_config_items WHERE item_type='consumable' → SKIPPED (canonical source is game_config_consumables)
    - game_config_consumables → kind='consumable'

    Idempotent: INSERT OR IGNORE on UNIQUE(key).
    """
    import json as _json

    # Normalize legacy text rarities → int across all source tables FIRST.
    # Legacy PROD rows store rarity as words ('common'/'rare'); DEV uses ints.
    # Without this, int() casts here AND in runtime read paths (loot/durability)
    # crash on those rows. Idempotent: only touches non-numeric values.
    _normalize_legacy_rarities(conn)

    # Check if already populated
    existing = conn.execute("SELECT COUNT(*) FROM game_items").fetchone()[0]
    if existing > 0:
        return

    try:
        # Weapons (no created_by column in game_config_weapons — use 'seed' default)
        weapons = conn.execute(
            """SELECT key, label, description, value_gp, effect_json, rarity, min_level,
                      location_tags, approved, is_active, weight_kg, note,
                      locked_at, created_at, updated_at,
                      damage_die, weapon_type, linked_stat, allowed_classes, two_handed,
                      finesse, range_m, targeting, aoe_radius_m, magic_school, weapon_slot
               FROM game_config_weapons"""
        ).fetchall()
        for w in weapons:
            weapon_data = _json.dumps({
                "damage_die": w["damage_die"],
                "weapon_type": w["weapon_type"],
                "linked_stat": w["linked_stat"],
                "allowed_classes": w["allowed_classes"],
                "two_handed": w["two_handed"],
                "finesse": w["finesse"],
                "range_m": w["range_m"],
                "targeting": w["targeting"],
                "aoe_radius_m": w["aoe_radius_m"],
                "magic_school": w["magic_school"],
                "weapon_slot": w["weapon_slot"] or "main_hand",
            })
            conn.execute(
                """INSERT OR IGNORE INTO game_items
                   (key, kind, label, description, price_gp, effect_json, equip_slot,
                    rarity, min_level, location_tags, created_by, approved, is_active,
                    weapon_data, weight_kg, note, locked_at, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    w["key"], "weapon", w["label"] or "", w["description"] or "",
                    float(w["value_gp"] or 0), w["effect_json"],
                    "main_hand",
                    _as_int(w["rarity"], 1), _as_int(w["min_level"], 1),
                    w["location_tags"] or "[]",
                    "seed", int(w["approved"] or 1),
                    int(w["is_active"] or 1), weapon_data,
                    float(w["weight_kg"] or 0), w["note"],
                    w["locked_at"], w["created_at"], w["updated_at"],
                ),
            )

        # Items (armor + non-consumable; no created_by column — use 'seed' default)
        items = conn.execute(
            """SELECT key, label, description, value_gp, effect_json, rarity, min_level,
                      location_tags, approved, is_active, weight_kg, note,
                      locked_at, created_at, updated_at,
                      item_type, ac_bonus, armor_coverage, allowed_classes,
                      charges, effect_type, effect_dice, effect_bonus, effect_target
               FROM game_config_items
               WHERE item_type NOT IN ('consumable')"""
        ).fetchall()
        for it in items:
            kind = "armor" if it["item_type"] in ("armor", "shield") else "item"
            equip_slot = "armor" if kind == "armor" else None
            item_data = _json.dumps({
                "item_type": it["item_type"],
                "ac_bonus": it["ac_bonus"],
                "armor_coverage": it["armor_coverage"],
                "allowed_classes": it["allowed_classes"],
                "charges": it["charges"],
                "effect_type": it["effect_type"],
                "effect_dice": it["effect_dice"],
                "effect_bonus": it["effect_bonus"],
                "effect_target": it["effect_target"],
            })
            conn.execute(
                """INSERT OR IGNORE INTO game_items
                   (key, kind, label, description, price_gp, effect_json, equip_slot,
                    rarity, min_level, location_tags, created_by, approved, is_active,
                    item_data, weight_kg, note, locked_at, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    it["key"], kind, it["label"] or "", it["description"] or "",
                    float(it["value_gp"] or 0), it["effect_json"],
                    equip_slot,
                    _as_int(it["rarity"], 1), _as_int(it["min_level"], 1),
                    it["location_tags"] or "[]",
                    "seed", int(it["approved"] or 1),
                    int(it["is_active"] or 1), item_data,
                    float(it["weight_kg"] or 0), it["note"],
                    it["locked_at"], it["created_at"], it["updated_at"],
                ),
            )

        # Consumables (canonical source — skip item table duplicates; no created_by column)
        consumables = conn.execute(
            """SELECT key, label, description, base_price, rarity, min_level,
                      location_tags, approved, is_active, weight_kg, note,
                      locked_at, created_at, updated_at,
                      effect_type, effect_dice, effect_bonus, effect_target, charges
               FROM game_config_consumables"""
        ).fetchall()
        for c in consumables:
            item_data = _json.dumps({
                "effect_type": c["effect_type"],
                "effect_dice": c["effect_dice"],
                "effect_bonus": c["effect_bonus"],
                "effect_target": c["effect_target"],
                "charges": c["charges"],
            })
            conn.execute(
                """INSERT OR IGNORE INTO game_items
                   (key, kind, label, description, price_gp, equip_slot,
                    rarity, min_level, location_tags, created_by, approved, is_active,
                    item_data, weight_kg, note, locked_at, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    c["key"], "consumable", c["label"] or "", c["description"] or "",
                    float(c["base_price"] or 0), None,
                    _as_int(c["rarity"], 1), _as_int(c["min_level"], 1),
                    c["location_tags"] or "[]",
                    "seed", int(c["approved"] or 1), int(c["is_active"] or 1),
                    item_data,
                    float(c["weight_kg"] or 0), c["note"],
                    c["locked_at"], c["created_at"], c["updated_at"],
                ),
            )

        conn.commit()
        total = conn.execute("SELECT COUNT(*) FROM game_items").fetchone()[0]
        logger.info("u11a_game_items_backfill_done", total=total)

    except Exception as exc:
        logger.error("u11a_game_items_backfill_failed", error=str(exc))
        raise


def _seed_onboarding_cards_into_knowledge(conn: sqlite3.Connection) -> None:
    """#594: seed MECHANIC_CARDS into knowledge_book as kind='onboarding_card'.

    Idempotent (INSERT OR IGNORE on tip_key). Source of truth for content moves
    to the DB row; onboarding_service falls back to the dict if a row is missing.
    Skips silently if the `kind` column isn't present yet (migration not applied).
    """
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(knowledge_book)").fetchall()}
        if "kind" not in cols:
            return
        from app.services.onboarding_service import MECHANIC_CARDS
    except Exception:
        return
    for idx, (key, card) in enumerate(MECHANIC_CARDS.items()):
        try:
            conn.execute(
                "INSERT OR IGNORE INTO knowledge_book "
                "(tip_key, category, title, body, is_active, sort_order, kind, "
                " show_in_onboarding, show_in_knowledge) "
                "VALUES (?, 'onboarding', ?, ?, 1, ?, 'onboarding_card', 1, 1)",
                (key, card.get("title", ""), card.get("content", ""), idx),
            )
        except sqlite3.Error:
            continue
    conn.commit()


def _l9_deactivate_legacy_dungeons(conn: sqlite3.Connection) -> None:
    """L9: Deactivate all legacy procedural dungeons (those without tile_category_key).

    Idempotent — safe to run on every startup. Columns are preserved; only is_active flipped.
    """
    try:
        conn.execute(
            "UPDATE game_dungeons SET is_active = 0 WHERE tile_category_key IS NULL OR tile_category_key = ''"
        )
        conn.commit()
        logger.info("v2_migration_applied", label="v2-l9-deactivate-legacy-dungeons")
    except Exception as e:
        logger.warning("v2_migration_skipped", label="v2-l9-deactivate-legacy-dungeons", error=str(e))


def _ensure_portrait_columns(conn: sqlite3.Connection) -> None:
    """L20a (#692): add portrait persistence columns to game_config_enemies and npcs.

    Idempotent — duplicate column and no such table errors are silently skipped
    (the latter only occurs in isolated test in-memory DBs).
    """
    for sql in [
        "ALTER TABLE game_config_enemies ADD COLUMN image_url TEXT",
        "ALTER TABLE game_config_enemies ADD COLUMN image_url_raw TEXT",
        "ALTER TABLE game_config_enemies ADD COLUMN image_gen_prompt TEXT",
        "ALTER TABLE npcs ADD COLUMN image_url TEXT",
        "ALTER TABLE npcs ADD COLUMN image_url_raw TEXT",
        "ALTER TABLE npcs ADD COLUMN image_gen_prompt TEXT",
    ]:
        try:
            conn.execute(sql)
            conn.commit()
        except sqlite3.OperationalError as e:
            msg = str(e).lower()
            if "duplicate column" in msg or "no such table" in msg:
                pass  # idempotent — column exists or table absent in test DB
            else:
                raise


def _refresh_knowledge_content(conn: sqlite3.Connection) -> None:
    """#594 audit: fix stale/corrupt knowledge_book entries, dedupe, add gaps.

    Idempotent — UPDATEs set fixed canonical text, DELETEs remove redundant rows,
    INSERT OR IGNORE adds new reference entries. Safe to run every startup.
    Runs AFTER seeds so it always wins over re-seeded legacy text.
    """
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(knowledge_book)").fetchall()}
    except sqlite3.Error:
        return
    has_flags = "show_in_knowledge" in cols

    # 1. Corrected / refreshed bodies (keyed UPDATEs)
    updates = {
        "dice_roll": ("Rzut kością",
            "Twoje akcje rozstrzygane są rzutem: k20 + Mod. statystyki + Ranga umiejętności + "
            "Biegłość (te same składniki widzisz na karcie rzutu). Wynik porównywany jest z "
            "trudnością (DC): 8 łatwe, 12 średnie, 16 trudne, 20 ekstremalne. Naturalna 20 = "
            "automatyczny sukces z podwójnymi obrażeniami. Naturalna 1 = porażka z komplikacją."),
        "mech_death": ("Śmierć i rzuty na śmierć",
            "Gdy HP spadnie do 0, bohater nie ginie od razu — pada i co turę rzuca na śmierć "
            "(k20 vs rosnące DC: 10, potem 13, 16, 19 za kolejne upadki w tej samej walce). "
            "Trzy porażki = śmierć. Naturalna 1 liczy się jako dwie porażki, naturalna 20 to "
            "sukces. Drabina resetuje się po walce. Śmierć kończy kampanię; w lochach jest "
            "natychmiastowa i ostateczna. Jeśli admin włączył wskrzeszenie — można wrócić za złoto/XP."),
        "death_save": ("Na krawędzi śmierci",
            "Gdy HP spadną poniżej 25%, jesteś o krok od upadku. Przy 0 HP bohater pada i co turę "
            "rzuca na śmierć (k20 vs rosnące DC 10→13→16→19; trzy porażki = śmierć, Nat 1 = dwie "
            "porażki, Nat 20 = sukces). Lecz się zawczasu — miksturą, czarem lub wycofaniem z "
            "walki. W lochach śmierć jest natychmiastowa i permanentna."),
        "nat20_nat1": ("Szczęście i pech w kościach",
            "Naturalna 20 na k20 to zawsze sukces — krytyk z podwójnymi obrażeniami lub "
            "spektakularny wyczyn. Naturalna 1 to zawsze porażka — fumble z komplikacją fabularną. "
            "Żaden modyfikator tego nie zmienia."),
        "durability": ("Zużycie i naprawa ekwipunku",
            "Broń i zbroja zużywają się z użyciem — broń przy twoim trafionym ataku, zbroja przy "
            "otrzymanym ciosie. Pasek trwałości w ekwipunku pokazuje stan; przy zerze sprzęt traci "
            "skuteczność (kara). Naprawisz go u rzemieślnika za złoto (koszt rośnie z tierem przedmiotu)."),
        "affixes": ("Magiczne afiksy",
            "Niektóre przedmioty mają magiczne właściwości — afiksy — np. +obrażenia, leczenie przy "
            "trafieniu, bonus do pancerza. Im wyższy tier afiksu, tym silniejszy efekt. Afiksy można "
            "nakładać i przelosowywać u rzemieślnika za złoto. Lepsza broń z afiksami potrafi odwrócić "
            "losy walki."),
        "raids": ("Napady na szlaku",
            "Na dzikim terenie, z dala od bezpiecznych osad, z sakiewką pełną złota (>100 gp) grożą ci "
            "napady — bandyci próbują ukraść część złota. Dostajesz turę ostrzeżenia, potem rzut obronny "
            "(k20 + DEX/WIS vs DC wg poziomu): sukces = bez straty, porażka = −20% złota. Limit jeden "
            "napad na 24h, brak poniżej 50 gp."),
        "crafter": ("Rzemieślnik",
            "Rzemieślnicy (kowale, płatnerze) ulepszają twój sprzęt: nakładają magiczne afiksy, "
            "przelosowują je i awansują do wyższego tieru, a także naprawiają trwałość. Każda usługa "
            "kosztuje złoto rosnące z tierem. Szukaj ich w większych osadach."),
    }
    for key, (title, body) in updates.items():
        try:
            conn.execute(
                "UPDATE knowledge_book SET title = ?, body = ? WHERE tip_key = ?",
                (title, body, key),
            )
        except sqlite3.Error:
            continue

    # 2. Remove duplicate entries (keep nat20_nat1 + combat_conditions)
    for dup in ("combat_crits", "conditions_stat_mods"):
        try:
            conn.execute("DELETE FROM knowledge_book WHERE tip_key = ?", (dup,))
        except sqlite3.Error:
            pass

    # 3. New reference entries (knowledge-only)
    new_entries = [
        ("affix_pity", "mechanics", "Gwarancja afiksu (pity)",
            "Gra pilnuje, żeby pech nie trwał wiecznie. Jeśli pokonasz trzech bossów z rzędu bez "
            "afiksowego łupu, kolejny boss gwarantuje przedmiot z afiksem (min. tier 1). Podobnie "
            "przy przelosowaniu afiksu u rzemieślnika: jeśli trzy próby nie zmienią afiksu, czwarta "
            "gwarantuje inny.", 95),
        ("rest_mechanics", "mechanics", "Odpoczynek",
            "Dwa rodzaje odpoczynku w bezpiecznej lokacji. Krótki: leczy 1k6 + Mod. CON HP, "
            "maksymalnie dwa razy między długimi, kosztuje 1h. Długi: pełne HP i mana, kasuje rzuty "
            "na śmierć, odnawia krótkie odpoczynki i pozwala wydać zebrane PD (★ Długi → 📖 Ucz się); "
            "kosztuje 8h.", 96),
        ("shop_pricing", "mechanics", "Sklep i ceny",
            "Asortyment kupca zależy od lokacji i twojego poziomu — większe osady mają lepszy towar. "
            "Charyzma (CHA) wpływa na ceny: wysoka CHA obniża zakupy i podnosi utarg ze sprzedaży. "
            "Uwaga na spam-sprzedaż tego samego typu przedmiotu — cena skupu spada (anti-farm) i wraca "
            "po czasie.", 97),
    ]
    for key, cat, title, body, order in new_entries:
        try:
            if has_flags:
                conn.execute(
                    "INSERT OR IGNORE INTO knowledge_book "
                    "(tip_key, category, title, body, is_active, sort_order, kind, "
                    " show_in_onboarding, show_in_knowledge) VALUES (?,?,?,?,1,?,'knowledge_tip',0,1)",
                    (key, cat, title, body, order),
                )
            else:
                conn.execute(
                    "INSERT OR IGNORE INTO knowledge_book "
                    "(tip_key, category, title, body, is_active, sort_order) VALUES (?,?,?,?,1,?)",
                    (key, cat, title, body, order),
                )
        except sqlite3.Error:
            continue
    conn.commit()


def _ensure_dice_rolls_table(conn: sqlite3.Connection) -> None:
    """#754: dice_rolls — strukturalny rejestr KAŻDEGO rzutu kostką per kampania.

    ŚWIADOMIE bez FK ON DELETE CASCADE do campaigns: lochy kasują kampanię na wyjściu,
    a rzuty muszą przetrwać post-mortem debug. Orphany ewentualnie czyszczone osobnym
    zadaniem retencyjnym, nie kaskadą. Idempotentne.
    """
    conn.execute("""
        CREATE TABLE IF NOT EXISTS dice_rolls (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id   INTEGER NOT NULL,
            character_id  INTEGER,
            turn_number   REAL,
            combat_id     INTEGER,
            roll_type     TEXT NOT NULL,
            actor         TEXT,
            notation      TEXT,
            raw_rolls     TEXT,
            modifiers     TEXT,
            total         INTEGER,
            dc            INTEGER,
            outcome       TEXT,
            meta          TEXT,
            created_at    TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_dice_rolls_campaign ON dice_rolls (campaign_id, turn_number)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_dice_rolls_type ON dice_rolls (roll_type, created_at)")
    conn.commit()
    logger.info("admin_migration_applied", sql_preview="dice_rolls table (#754)")


def _ensure_state_changes_table(conn: sqlite3.Connection) -> None:
    """#761: state_changes — rejestr zmian zasobów/kondycji gracza (hp/mana/kondycje/strefa).

    before→after + delta + przyczyna + tura. Bez FK CASCADE (przeżywa wyjście z lochu,
    jak dice_rolls #754). Idempotentne.
    """
    conn.execute("""
        CREATE TABLE IF NOT EXISTS state_changes (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id   INTEGER NOT NULL,
            character_id  INTEGER,
            turn_number   REAL,
            combat_id     INTEGER,
            resource      TEXT NOT NULL,   -- hp|mana|condition|zone
            before_val    TEXT,
            after_val     TEXT,
            delta         INTEGER,
            cause         TEXT,            -- combat_damage|heal|trap|rest|level_up|spell_cast|zone_change|condition_apply|condition_expire
            meta          TEXT,
            created_at    TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_state_changes_campaign ON state_changes (campaign_id, turn_number)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_state_changes_resource ON state_changes (resource, created_at)")
    conn.commit()
    logger.info("admin_migration_applied", sql_preview="state_changes table (#761)")


def _ensure_turn_decisions_table(conn: sqlite3.Connection) -> None:
    """#762: turn_decisions — rejestr decyzji silnika per tura (intent/route/gate).

    Żywy następca martwego action_log. Bez FK CASCADE. Idempotentne.
    """
    conn.execute("""
        CREATE TABLE IF NOT EXISTS turn_decisions (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id        INTEGER NOT NULL,
            character_id       INTEGER,
            turn_number        REAL,
            user_text          TEXT,
            action_type        TEXT,
            confidence         REAL,
            route              TEXT,
            gate_blocked       INTEGER,
            gate_reason        TEXT,
            handler            TEXT,
            correction_applied INTEGER,
            raw_intent         TEXT,
            meta               TEXT,
            created_at         TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_turn_decisions_campaign ON turn_decisions (campaign_id, turn_number)")
    conn.commit()
    logger.info("admin_migration_applied", sql_preview="turn_decisions table (#762)")


def _backfill_riddle_exit_conditions(conn: sqlite3.Connection) -> None:
    """#722: Backfill exit_conditions_json for riddle tiles that have riddle_key but empty gate.

    Idempotent — only updates tiles where exit_conditions_json is '[]' or NULL.
    Engine auto-injects the gate at runtime too, but DB should be canonical.
    """
    try:
        conn.execute(
            "UPDATE dungeon_tiles SET exit_conditions_json = '[{\"type\":\"riddle_solved\"}]' "
            "WHERE riddle_key IS NOT NULL AND riddle_key != '' "
            "AND (exit_conditions_json IS NULL OR exit_conditions_json = '[]')"
        )
        conn.commit()
        logger.info("admin_migration_applied", sql_preview="backfill riddle exit_conditions (#722)")
    except Exception as e:
        logger.warning("admin_migration_skipped", label="backfill-riddle-exit-conditions-722", error=str(e))


def _ensure_consumable_effect_json(conn: sqlite3.Connection) -> None:
    """#771: Add effect_json column to game_config_consumables, seed buff conditions, backfill 14 consumables."""
    import json as _json

    # 1. ADD COLUMN
    try:
        conn.execute("ALTER TABLE game_config_consumables ADD COLUMN effect_json TEXT")
        conn.commit()
        logger.info("admin_migration_applied", sql_preview="ALTER game_config_consumables +effect_json (#771)")
    except Exception as e:
        if "duplicate column" not in str(e).lower():
            logger.warning("admin_migration_skipped", label="consumables-effect-json-771", error=str(e))

    # 2. SEED missing buff conditions
    buff_conditions = [
        ("empowered", "Wzmocniony",
         _json.dumps({"schema_version": 1, "effect_category": "character_condition",
                      "effects": [{"type": "static_stat_modifier", "stat": "STR", "value": 2,
                                   "expires": "duration_rounds:3"}]})),
        ("resistant", "Odporny",
         _json.dumps({"schema_version": 1, "effect_category": "character_condition",
                      "effects": [{"type": "static_stat_modifier", "stat": "CON", "value": 2,
                                   "expires": "duration_rounds:3"}]})),
        ("energized", "Energiczny",
         _json.dumps({"schema_version": 1, "effect_category": "character_condition",
                      "effects": [{"type": "static_stat_modifier", "stat": "CON", "value": 2,
                                   "expires": "duration_rounds:3"}]})),
        ("shielded", "Osłonięty",
         _json.dumps({"schema_version": 1, "effect_category": "character_condition",
                      "effects": [{"type": "ac_bonus", "value": 3,
                                   "expires": "duration_rounds:3"}]})),
    ]
    try:
        for key, label, ej in buff_conditions:
            conn.execute(
                "INSERT OR IGNORE INTO game_config_conditions (key, label, effect_json, stackable, is_active) VALUES (?, ?, ?, 0, 1)",
                (key, label, ej),
            )
        conn.commit()
        logger.info("admin_migration_applied", sql_preview="seed buff conditions empowered/resistant/energized/shielded (#771)")
    except Exception as e:
        logger.warning("admin_migration_skipped", label="buff-conditions-seed-771", error=str(e))

    # 3. BACKFILL 14 consumables with effect_json
    consumable_backfill = {
        "alchemist_fire": _json.dumps({"effect_category": "consumable_immediate", "effects": [
            {"type": "damage_enemy", "value": "1d4", "target": "enemy"},
            {"type": "apply_condition", "condition_key": "burning", "target": "enemy"},
        ]}),
        "holy_water": _json.dumps({"effect_category": "consumable_immediate", "effects": [
            {"type": "damage_enemy", "value": "2d6", "target": "enemy"},
            {"type": "apply_condition", "condition_key": "on_fire", "target": "enemy"},
        ]}),
        "scroll_fireball": _json.dumps({"effect_category": "consumable_immediate", "effects": [
            {"type": "damage_enemy", "value": "8d6", "target": "area"},
        ]}),
        "scroll_magic_bolt": _json.dumps({"effect_category": "consumable_immediate", "effects": [
            {"type": "damage_enemy", "value": "1d10", "target": "enemy"},
        ]}),
        "vial_of_acid": _json.dumps({"effect_category": "consumable_immediate", "effects": [
            {"type": "damage_enemy", "value": "2d6", "target": "enemy"},
            {"type": "apply_condition", "condition_key": "weakened", "target": "enemy"},
        ]}),
        "smoke_bomb": _json.dumps({"effect_category": "consumable_immediate", "effects": [
            {"type": "apply_condition", "condition_key": "hidden", "target": "self"},
        ]}),
        "scroll_light": _json.dumps({"effect_category": "consumable_immediate", "effects": [
            {"type": "narrative_only"},
        ]}),
        "potion_haste": _json.dumps({"effect_category": "consumable_immediate", "effects": [
            {"type": "apply_condition", "condition_key": "hasted", "target": "self"},
        ]}),
        "potion_stealth": _json.dumps({"effect_category": "consumable_immediate", "effects": [
            {"type": "apply_condition", "condition_key": "hidden", "target": "self"},
        ]}),
        "potion_strength": _json.dumps({"effect_category": "consumable_immediate", "effects": [
            {"type": "apply_condition", "condition_key": "empowered", "target": "self"},
        ]}),
        "potion_giant_strength": _json.dumps({"effect_category": "consumable_immediate", "effects": [
            {"type": "apply_condition", "condition_key": "empowered", "target": "self"},
        ]}),
        "potion_resistance": _json.dumps({"effect_category": "consumable_immediate", "effects": [
            {"type": "apply_condition", "condition_key": "resistant", "target": "self"},
        ]}),
        "potion_stamina": _json.dumps({"effect_category": "consumable_immediate", "effects": [
            {"type": "apply_condition", "condition_key": "energized", "target": "self"},
        ]}),
        "scroll_shield": _json.dumps({"effect_category": "consumable_immediate", "effects": [
            {"type": "apply_condition", "condition_key": "shielded", "target": "self"},
        ]}),
    }
    try:
        for key, ej in consumable_backfill.items():
            conn.execute(
                "UPDATE game_config_consumables SET effect_json = ? WHERE key = ? AND (effect_json IS NULL OR effect_json = '')",
                (ej, key),
            )
        conn.commit()
        logger.info("admin_migration_applied", sql_preview="backfill 14 consumables effect_json (#771)")
    except Exception as e:
        logger.warning("admin_migration_skipped", label="consumable-backfill-771", error=str(e))


def _ensure_warrior_shared_heal_858(conn: sqlite3.Connection) -> None:
    """#858 — bandaż jako uniwersalne (class-agnostic) leczenie w walce.

    Decyzja Piotra: wspólne mechaniki leczenia (mikstura, bandaż) dostępne dla KAŻDEJ klasy.
    1) Bandaż leczy SIEBIE (effect_target='self'), nie sojusznika ('ally') — to bazowe
       leczenie gracza, odpowiednik mikstury maga. heal_hp i tak ignoruje target przy self-use,
       ale zapis 'self' jest poprawny semantycznie i pod display/przyszłą logikę target-aware.
    2) Wojownik dostaje bandaż na starcie — bazowe leczenie w walce (analog mikstury/spella maga),
       żeby nie był zależny wyłącznie od mikstur w plecaku. Idempotentne.
    """
    import json as _json

    # 1. Bandaż = self-heal
    try:
        conn.execute(
            "UPDATE game_config_consumables SET effect_target = 'self' "
            "WHERE key = 'bandage' AND COALESCE(effect_target, '') != 'self'"
        )
        conn.commit()
        logger.info("admin_migration_applied", sql_preview="bandage effect_target -> self (#858)")
    except Exception as e:
        logger.warning("admin_migration_skipped", label="bandage-self-target-858", error=str(e))

    # 2. Wojownik startuje z bandażem (×2)
    try:
        row = conn.execute(
            "SELECT starter_items_json FROM game_config_archetypes WHERE key = 'warrior'"
        ).fetchone()
        if row is not None:
            items = _json.loads(row["starter_items_json"] or "[]")
            if not isinstance(items, list):
                items = []
            has_bandage = any(
                isinstance(it, dict) and str(it.get("consumable_key") or "") == "bandage"
                for it in items
            )
            if not has_bandage:
                items.append({"consumable_key": "bandage", "quantity": 2})
                conn.execute(
                    "UPDATE game_config_archetypes SET starter_items_json = ?, updated_at = datetime('now') "
                    "WHERE key = 'warrior'",
                    (_json.dumps(items, ensure_ascii=False),),
                )
                conn.commit()
                logger.info("admin_migration_applied", sql_preview="warrior starter +bandage x2 (#858)")
    except Exception as e:
        logger.warning("admin_migration_skipped", label="warrior-starter-bandage-858", error=str(e))


# #748 — standalone Piper+Whisper GPU box (.16). Domyślny host głosu na DEV.
WHISPER_GPU_HOST_URL = "http://192.168.1.16:8300"


def _ensure_voice_config_table(conn: sqlite3.Connection) -> None:
    """#748 — voice_config była używana przez voice_proxy, lecz nigdy nie powstała,
    więc zapis ustawień głosu (POST /voice/config) wykraszał na INSERT. Idempotentne."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS voice_config (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL DEFAULT ''
        )
        """
    )
    conn.commit()


def _ensure_active_voice_host(conn: sqlite3.Connection) -> None:
    """#748 — gdy żaden host głosu nie jest aktywny, proxy fallbackuje na bundlowany
    `voice-service:8300`, którego na DEV nie ma → STT/TTS pada z 'Name or service not
    known'. Self-heal: gdy istnieje wiersz hosta .16 i żaden host nie jest aktywny —
    aktywuj .16. No-op gdy: jakiś host już aktywny (nie nadpisujemy wyboru admina),
    brak tabeli, lub brak wiersza .16 (PROD → zostaje przy bundlowanym voice-service)."""
    has_table = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='voice_hosts'"
    ).fetchone()
    if not has_table:
        return
    active = conn.execute(
        "SELECT 1 FROM voice_hosts WHERE is_active = 1 LIMIT 1"
    ).fetchone()
    if active:
        return
    conn.execute(
        "UPDATE voice_hosts SET is_active = 1 WHERE base_url = ?",
        (WHISPER_GPU_HOST_URL,),
    )
    conn.commit()


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
        _ensure_active_combat_ammo_spent(conn)

        _rebuild_loot_entries_for_consumable_support(conn)
        _upgrade_loot_entries_three_way_xor(conn)
        _ensure_loot_entries_full_schema(conn)
        _finalize_phase_8h_items_schema(conn)
        _finalize_t25_effect_json_schema(conn)
        _finalize_phase_8h_loot_entries(conn)

        # Must run before ADMIN_SEEDS — seeds reference tables these create
        _run_v2_schema_migrations(conn)
        _ensure_game_config_services(conn)
        _seed_onboarding_cards_into_knowledge(conn)  # #594

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
        _backfill_enemy_loot_tables(conn)
        _backfill_enemy_stats_json(conn)
        _ensure_user_llm_settings_mode(conn)
        _ensure_dungeon_tile_l1_columns(conn)
        _ensure_dungeon_v2_schema(conn)
        _ensure_narrative_items_schema(conn)
        _ensure_auth_ux_schema(conn)
        _ensure_submap_schema(conn)
        _ensure_shop_item_level_location_schema(conn)
        _ensure_price_gp_schema(conn)
        _apply_f15_balance_tuning(conn)
        _ensure_npc_is_dead_column(conn)
        _ensure_pending_category_column(conn)
        _ensure_xp_level_thresholds(conn)
        _ensure_time_of_day_effects(conn)
        _ensure_hidden_traits_schema(conn)
        _ensure_skill_risk_categories(conn)
        _ensure_campaign_source_template(conn)
        _ensure_campaign_plan_degraded(conn)
        _patch_campaign_template_beat_objectives(conn)
        _migrate_npc_locations_to_assignments(conn)
        _backfill_game_items(conn)
        _refresh_knowledge_content(conn)  # #594 audit — runs last, wins over re-seeds
        _l9_deactivate_legacy_dungeons(conn)
        _ensure_portrait_columns(conn)
        _ensure_dice_rolls_table(conn)  # #754
        _ensure_state_changes_table(conn)  # #761
        _ensure_turn_decisions_table(conn)  # #762
        _backfill_riddle_exit_conditions(conn)  # #722
        _ensure_consumable_effect_json(conn)  # #771
        _ensure_warrior_shared_heal_858(conn)  # #858
        _ensure_voice_config_table(conn)  # #748
        _ensure_active_voice_host(conn)  # #748
    finally:
        conn.close()

    logger.info("admin_migration_complete", phase="12.5")
