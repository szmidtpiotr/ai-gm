import os
import sqlite3


DB_PATH = "/data/ai_gm.db"

ADMIN_MIGRATIONS = [
    """
    CREATE TABLE IF NOT EXISTS game_config_stats (
        key TEXT PRIMARY KEY,
        label TEXT NOT NULL,
        description TEXT NOT NULL,
        sort_order INTEGER NOT NULL DEFAULT 0
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS game_config_skills (
        key TEXT PRIMARY KEY,
        label TEXT NOT NULL,
        linked_stat TEXT NOT NULL,
        rank_ceiling INTEGER NOT NULL DEFAULT 5,
        sort_order INTEGER NOT NULL DEFAULT 0
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS game_config_dc (
        key TEXT PRIMARY KEY,
        label TEXT NOT NULL,
        value INTEGER NOT NULL,
        sort_order INTEGER NOT NULL DEFAULT 0
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
    CREATE INDEX IF NOT EXISTS idx_game_config_skills_linked_stat
    ON game_config_skills(linked_stat)
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
    INSERT OR IGNORE INTO game_config_skills (key, label, linked_stat, rank_ceiling, sort_order) VALUES
    ('stealth', 'Stealth', 'DEX', 5, 1),
    ('athletics', 'Athletics', 'STR', 5, 2),
    ('initiative', 'Initiative', 'DEX', 5, 3),
    ('attack', 'Attack', 'STR', 5, 4),
    ('awareness', 'Awareness', 'WIS', 5, 5),
    ('persuasion', 'Persuasion', 'CHA', 5, 6),
    ('intimidation', 'Intimidation', 'CHA', 5, 7),
    ('survival', 'Survival', 'WIS', 5, 8),
    ('lore', 'Lore', 'INT', 5, 9),
    ('arcana', 'Arcana', 'INT', 5, 10),
    ('medicine', 'Medicine', 'WIS', 5, 11),
    ('investigation', 'Investigation', 'INT', 5, 12)
    """,
    """
    INSERT OR IGNORE INTO game_config_dc (key, label, value, sort_order) VALUES
    ('easy', 'Łatwe', 8, 1),
    ('medium', 'Średnie', 12, 2),
    ('hard', 'Trudne', 16, 3),
    ('extreme', 'Ekstremalne', 20, 4),
    ('legendary', 'Legendarne', 24, 5)
    """,
]


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
                print(f"[admin_migration] applied: {sql.strip().splitlines()[0]}")
            except sqlite3.OperationalError as e:
                msg = str(e).lower()
                if "already exists" in msg:
                    print(f"[admin_migration] skipped ({e}): {sql.strip().splitlines()[0]}")
                else:
                    print(f"[admin_migration] ERROR ({e}): {sql.strip().splitlines()[0]}")

        for sql in ADMIN_SEEDS:
            conn.execute(sql)
            conn.commit()
            print(f"[admin_migration] seeded: {sql.strip().splitlines()[0]}")
    finally:
        conn.close()

    print("[admin_migration] Phase 11.0 done.")
