-- Minimal schema extensions for isolated E2E stack (AIGM_E2E_LITE=1).
-- Keeps UX paths working without full run_admin_migrations().

-- users (auth / onboarding)
ALTER TABLE users ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1;
ALTER TABLE users ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0;
ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'player';
ALTER TABLE users ADD COLUMN failed_login_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE users ADD COLUMN lockout_until TEXT;
ALTER TABLE users ADD COLUMN email_verified_at TEXT;
ALTER TABLE users ADD COLUMN onboarded_at TEXT;
ALTER TABLE users ADD COLUMN email TEXT;
ALTER TABLE users ADD COLUMN deleted_at TEXT;
ALTER TABLE users ADD COLUMN is_tester INTEGER NOT NULL DEFAULT 0;

-- campaigns (GET /api/campaigns, multiplayer lobby helpers)
ALTER TABLE campaigns ADD COLUMN language TEXT NOT NULL DEFAULT 'pl';
ALTER TABLE campaigns ADD COLUMN death_reason TEXT;
ALTER TABLE campaigns ADD COLUMN ended_at TEXT;
ALTER TABLE campaigns ADD COLUMN epitaph TEXT;
ALTER TABLE campaigns ADD COLUMN gm_plan_json TEXT NOT NULL DEFAULT '{}';
ALTER TABLE campaigns ADD COLUMN last_rollup_narrative_turn_count INTEGER;
ALTER TABLE campaigns ADD COLUMN host_user_id INTEGER;
ALTER TABLE campaigns ADD COLUMN round_timer_hours INTEGER NOT NULL DEFAULT 24;
ALTER TABLE campaigns ADD COLUMN round_timer_minutes INTEGER;
ALTER TABLE campaigns ADD COLUMN max_players INTEGER NOT NULL DEFAULT 4;
ALTER TABLE campaigns ADD COLUMN lobby_status TEXT NOT NULL DEFAULT 'open';

-- campaign_members (multiplayer invite queries)
ALTER TABLE campaign_members ADD COLUMN status TEXT NOT NULL DEFAULT 'accepted';
ALTER TABLE campaign_members ADD COLUMN character_id INTEGER;

-- characters (hero-first)
ALTER TABLE characters ADD COLUMN status TEXT NOT NULL DEFAULT 'in_campaign';
ALTER TABLE characters ADD COLUMN gold_gp INTEGER NOT NULL DEFAULT 0;

CREATE TABLE IF NOT EXISTS character_campaign_history (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  character_id INTEGER NOT NULL,
  campaign_id INTEGER NOT NULL,
  outcome TEXT NOT NULL DEFAULT 'active',
  chapter_summary TEXT,
  xp_earned INTEGER NOT NULL DEFAULT 0,
  gold_at_end INTEGER NOT NULL DEFAULT 0,
  turns_count INTEGER NOT NULL DEFAULT 0,
  completed_at TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_char_campaign_history
  ON character_campaign_history (character_id, completed_at);

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
);

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
);

CREATE TABLE IF NOT EXISTS game_config_archetypes (
  key TEXT PRIMARY KEY,
  label TEXT NOT NULL,
  description TEXT,
  starter_items_json TEXT NOT NULL DEFAULT '[]',
  starter_gold_gp INTEGER NOT NULL DEFAULT 0,
  is_active INTEGER NOT NULL DEFAULT 1,
  locked_at TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  hp_base INTEGER NOT NULL DEFAULT 10
);

INSERT OR IGNORE INTO game_config_archetypes (key, label, description, starter_items_json, hp_base)
VALUES
  ('warrior', 'Wojownik', 'Frontowy wojownik', '[]', 12),
  ('ranger', 'Łotrzyk', 'Zwinny cień', '[]', 8),
  ('scholar', 'Uczony', 'Tkacz arkanów', '[]', 6);

INSERT OR IGNORE INTO game_locations (id, key, label, description, location_type, is_active)
VALUES (1, 'start', 'Start', 'Punkt startowy testów E2E', 'macro', 1);

CREATE TABLE IF NOT EXISTS game_sessions (
  id TEXT PRIMARY KEY,
  campaign_id INTEGER,
  test_run_id TEXT,
  session_flags TEXT DEFAULT '{}',
  current_location_id INTEGER,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS debug_validation_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  test_run_id TEXT NOT NULL,
  event TEXT NOT NULL,
  is_legal INTEGER NOT NULL DEFAULT 1,
  reason TEXT,
  old_state TEXT,
  new_state TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS campaign_invites (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  campaign_id INTEGER NOT NULL,
  token TEXT NOT NULL UNIQUE,
  created_by INTEGER NOT NULL,
  expires_at TEXT NOT NULL,
  used_at TEXT,
  used_by INTEGER
);

CREATE TABLE IF NOT EXISTS active_combat (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  campaign_id INTEGER NOT NULL,
  combatants_json TEXT NOT NULL DEFAULT '[]',
  initiative_order TEXT,
  current_turn_index INTEGER NOT NULL DEFAULT 0,
  round_number INTEGER NOT NULL DEFAULT 1,
  status TEXT NOT NULL DEFAULT 'active',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS combat_turns (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  campaign_id INTEGER NOT NULL,
  combat_id INTEGER,
  event_type TEXT,
  payload_json TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
