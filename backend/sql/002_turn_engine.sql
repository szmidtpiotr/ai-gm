CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    display_name TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS campaigns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    system_id TEXT NOT NULL,
    model_id TEXT NOT NULL,
    owner_user_id INTEGER NOT NULL,
    mode TEXT NOT NULL DEFAULT 'solo',
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (owner_user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS campaign_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    role TEXT NOT NULL DEFAULT 'player',
    joined_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(campaign_id, user_id),
    FOREIGN KEY (campaign_id) REFERENCES campaigns(id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS characters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    system_id TEXT NOT NULL,
    sheet_json TEXT NOT NULL,
    location TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (campaign_id) REFERENCES campaigns(id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Inventory: catalog tables (game_config_*) are applied later via admin migrations.
-- Keys are validated in application; XOR CHECK enforces exactly one line type.
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
);

CREATE INDEX IF NOT EXISTS idx_inv_character
    ON character_inventory(character_id);
CREATE INDEX IF NOT EXISTS idx_inv_equipped
    ON character_inventory(character_id, equipped);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL,
    room_id TEXT,
    actor_character_id INTEGER,
    event_type TEXT NOT NULL,
    visibility TEXT NOT NULL DEFAULT 'campaign',
    content TEXT NOT NULL,
    payload_json TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (campaign_id) REFERENCES campaigns(id),
    FOREIGN KEY (actor_character_id) REFERENCES characters(id)
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL,
    character_id INTEGER,
    speaker_name TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    event_id INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (campaign_id) REFERENCES campaigns(id),
    FOREIGN KEY (character_id) REFERENCES characters(id),
    FOREIGN KEY (event_id) REFERENCES events(id)
);
