-- Phase 8A: active combat state (solo campaign, one row per campaign)
CREATE TABLE IF NOT EXISTS active_combat (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  campaign_id INTEGER NOT NULL UNIQUE,
  character_id INTEGER NOT NULL,
  round INTEGER NOT NULL DEFAULT 1,
  turn_order TEXT NOT NULL,
  current_turn TEXT NOT NULL,
  combatants TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'active',
  ended_reason TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (campaign_id) REFERENCES campaigns(id),
  FOREIGN KEY (character_id) REFERENCES characters(id)
);
