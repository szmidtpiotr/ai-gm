-- G19 #800: Spectators — per-player mute table
CREATE TABLE IF NOT EXISTS campaign_spectator_mutes (
    campaign_id INTEGER NOT NULL,
    user_id_player INTEGER NOT NULL,
    user_id_spectator INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (campaign_id, user_id_player, user_id_spectator)
);
