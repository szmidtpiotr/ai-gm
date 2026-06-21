-- G18 #796: Tiered round summaries for MP campaigns
-- layer=1: per-round summary; layer=2: chapter (~10 rounds compressed)
CREATE TABLE IF NOT EXISTS campaign_round_summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL,
    layer INTEGER NOT NULL,
    round_from INTEGER NOT NULL,
    round_to INTEGER NOT NULL,
    text TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_crs_campaign_layer
    ON campaign_round_summaries(campaign_id, layer);
