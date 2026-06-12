"""E9 (#424) — Story Gravity.

When the GM plan's next required beat stalls (no beat fired for N turns), nudge
the narrator with escalating pressure so the story keeps moving:

  level 1 (>= turns_l1)  → soft hint added to GM context
  level 2 (>= turns_l2)  → explicit narrative instruction
  level 3 (>= turns_l3)  → forced scene  (default OFF — opt-in via config)

Thresholds + the L3 toggle are admin-configurable, stored in game_config_meta
under the single JSON key `story_gravity_config`.
"""
from __future__ import annotations

import json
import sqlite3

DB_PATH = "/data/ai_gm.db"
_CONFIG_KEY = "story_gravity_config"

_DEFAULTS = {
    "enabled": True,
    "turns_l1": 5,
    "turns_l2": 10,
    "turns_l3": 15,
    "l3_enabled": False,          # forced scene OFF for Nowa Kampania (free exploration)
    "l3_enabled_gotowa": True,    # U8: L3 ON by default for Gotowa Kampania (player chose the story)
}

# Per-level GM context nudges (Polish — injected into the narrator prompt).
_HINTS = {
    1: "[STORY GRAVITY L1] Fabuła zwalnia — delikatnie przypomnij graczowi o niezałatwionym wątku głównym.",
    2: "[STORY GRAVITY L2] Wątek główny utknął — wprowadź wyraźny bodziec narracyjny kierujący ku następnemu kluczowemu beatowi.",
    3: "[STORY GRAVITY L3] Wymuszona scena — rozpocznij wydarzenie, które bezpośrednio popycha fabułę do następnego wymaganego beatu.",
}


def get_story_gravity_config() -> dict:
    """Read config from game_config_meta, falling back to defaults."""
    cfg = dict(_DEFAULTS)
    try:
        conn = sqlite3.connect(DB_PATH)
        try:
            row = conn.execute(
                "SELECT value FROM game_config_meta WHERE key = ?", (_CONFIG_KEY,)
            ).fetchone()
        finally:
            conn.close()
        if row and row[0]:
            stored = json.loads(row[0])
            if isinstance(stored, dict):
                cfg.update({k: stored[k] for k in _DEFAULTS if k in stored})
    except Exception:
        pass
    return cfg


def set_story_gravity_config(**kwargs) -> dict:
    """Patch one or more config fields. Unknown keys ignored."""
    cfg = get_story_gravity_config()
    for k, v in kwargs.items():
        if k in _DEFAULTS:
            cfg[k] = v
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            "INSERT OR REPLACE INTO game_config_meta (key, value) VALUES (?, ?)",
            (_CONFIG_KEY, json.dumps(cfg, ensure_ascii=False)),
        )
        conn.commit()
    finally:
        conn.close()
    return cfg


def _max_visited_at_turn(node) -> int:
    """Deep-scan a plan structure for the highest `visited_at_turn` value."""
    best = 0
    if isinstance(node, dict):
        v = node.get("visited_at_turn")
        if isinstance(v, int):
            best = max(best, v)
        for val in node.values():
            best = max(best, _max_visited_at_turn(val))
    elif isinstance(node, list):
        for item in node:
            best = max(best, _max_visited_at_turn(item))
    return best


def compute_story_gravity(campaign_id: int, conn: sqlite3.Connection) -> dict:
    """Return {level, turns_since_beat, hint} for the campaign's current state.

    level 0 means no escalation (disabled, too few turns, dungeon active, or no plan).
    U8: dungeon_run in session_flags pauses escalation. Gotowa Kampania (template_key set)
    uses l3_enabled_gotowa for L3 check instead of the global l3_enabled.
    """
    out = {"level": 0, "turns_since_beat": 0, "hint": ""}
    cfg = get_story_gravity_config()
    if not cfg.get("enabled", True):
        return out

    # U8: pause Story Gravity while player is in a dungeon run
    try:
        sf_row = conn.execute(
            "SELECT session_flags FROM game_sessions WHERE campaign_id = ?",
            (campaign_id,),
        ).fetchone()
        if sf_row:
            sf_raw = sf_row[0] if not isinstance(sf_row, sqlite3.Row) else sf_row["session_flags"]
            sf = json.loads(sf_raw or "{}")
            if sf.get("dungeon_run"):
                return out  # paused — player is consciously farming
    except Exception:
        pass

    try:
        row = conn.execute(
            "SELECT gm_plan_json, source_template_id FROM campaigns WHERE id = ?", (campaign_id,)
        ).fetchone()
    except Exception:
        # Fallback: column may not exist yet — read plan only
        try:
            row2 = conn.execute(
                "SELECT gm_plan_json FROM campaigns WHERE id = ?", (campaign_id,)
            ).fetchone()
        except Exception:
            return out
        if not row2:
            return out
        plan_raw = row2[0] if not isinstance(row2, sqlite3.Row) else row2["gm_plan_json"]
        template_key = None
        row = None

    if row is not None:
        if not row:
            return out
        plan_raw = row[0] if not isinstance(row, sqlite3.Row) else row["gm_plan_json"]
        template_key = row[1] if not isinstance(row, sqlite3.Row) else row["source_template_id"]
    try:
        plan = json.loads(plan_raw or "{}")
    except Exception:
        plan = {}

    cur_row = conn.execute(
        "SELECT COALESCE(MAX(turn_number), 0) FROM campaign_turns WHERE campaign_id = ?",
        (campaign_id,),
    ).fetchone()
    current_turn = int(cur_row[0]) if cur_row and cur_row[0] is not None else 0

    last_beat_turn = _max_visited_at_turn(plan)
    turns_since = max(0, current_turn - last_beat_turn)
    out["turns_since_beat"] = turns_since

    # U8: Gotowa Kampania uses l3_enabled_gotowa; Nowa Kampania uses l3_enabled
    is_gotowa = bool(template_key)
    l3_active = cfg.get("l3_enabled_gotowa", True) if is_gotowa else cfg.get("l3_enabled", False)

    level = 0
    if turns_since >= int(cfg["turns_l3"]) and l3_active:
        level = 3
    elif turns_since >= int(cfg["turns_l2"]):
        level = 2
    elif turns_since >= int(cfg["turns_l1"]):
        level = 1
    out["level"] = level
    out["hint"] = _HINTS.get(level, "")
    return out
