"""F12 (#472) — Anti-farm sell price decay.

When a character sells more than ANTI_FARM_LIMIT of the same item_key within
ANTI_FARM_WINDOW_HOURS, each subsequent sale earns less:
  effective_price = floor(base_sell_price * (1 - DECAY_PER_EXTRA * extras))
  Clamped at ANTI_FARM_MIN_RATIO (10% of base) so price never hits zero.

Sales are tracked via character_gold_log (source='shop_sell', meta_json contains item_key).
Only real-wall-clock hours count — not game-clock days — so the window resets naturally.
"""
from __future__ import annotations

import json
import sqlite3

ANTI_FARM_LIMIT: int = 3
ANTI_FARM_WINDOW_HOURS: int = 24
DECAY_PER_EXTRA: float = 0.10
ANTI_FARM_MIN_RATIO: float = 0.10


def _recent_sell_count(conn: sqlite3.Connection, character_id: int, item_key: str) -> int:
    """Count sales of item_key by character in the last ANTI_FARM_WINDOW_HOURS."""
    rows = conn.execute(
        """SELECT meta_json FROM character_gold_log
           WHERE character_id = ?
             AND source = 'shop_sell'
             AND wall_clock_at >= datetime('now', ?)
             AND delta > 0
        """,
        (int(character_id), f"-{ANTI_FARM_WINDOW_HOURS} hours"),
    ).fetchall()
    count = 0
    for row in rows:
        try:
            meta = json.loads(row[0] or row["meta_json"] or "{}")
            if str(meta.get("item_key") or meta.get("key") or "").strip() == str(item_key).strip():
                count += 1
        except Exception:
            pass
    return count


def get_anti_farm_multiplier(conn: sqlite3.Connection, character_id: int, item_key: str) -> float:
    """Return sell-price multiplier [ANTI_FARM_MIN_RATIO, 1.0].

    Returns 1.0 when under the limit (no decay yet).
    Returns (1.0 - extras * DECAY_PER_EXTRA) for each extra sale beyond the limit.
    """
    sold = _recent_sell_count(conn, character_id, item_key)
    extras = max(0, sold - ANTI_FARM_LIMIT + 1)
    if extras == 0:
        return 1.0
    raw = 1.0 - extras * DECAY_PER_EXTRA
    return round(max(ANTI_FARM_MIN_RATIO, raw), 4)


def apply_anti_farm(base_sell_price: int, multiplier: float) -> int:
    """Apply multiplier to a base sell price. Minimum 1 gp for any priced item."""
    import math
    if base_sell_price <= 0:
        return base_sell_price
    return max(1, int(math.floor(base_sell_price * multiplier)))
