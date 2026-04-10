CREATE TABLE IF NOT EXISTS campaign_turns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL,
    character_id INTEGER NOT NULL,
    user_text TEXT NOT NULL,
    route TEXT NOT NULL,
    assistant_text TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (campaign_id) REFERENCES campaigns(id),
    FOREIGN KEY (character_id) REFERENCES characters(id)
);