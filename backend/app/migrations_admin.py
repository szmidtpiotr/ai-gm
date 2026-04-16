import os
import sqlite3


DB_PATH = "/data/ai_gm.db"

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
                if "already exists" in msg or "duplicate column" in msg:
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
