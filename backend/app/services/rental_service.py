"""F13 (#473) — Rental expiry sweep.

Checks `character_rentals` for active rentals whose `expires_at_turn` <=
the current turn number and marks them expired. If the rental placed an
item in `character_inventory` (via `inventory_id`), removes it.

Call `expire_rentals(conn, campaign_id, current_turn)` once per turn,
before the main LLM call, so players don't benefit from expired bonuses.
"""
from __future__ import annotations

import sqlite3


def expire_rentals(conn: sqlite3.Connection, campaign_id: int, current_turn: int) -> int:
    """Mark expired rentals as 'expired' and remove their inventory items.

    Returns count of newly-expired rentals.
    """
    rows = conn.execute(
        """SELECT id, inventory_id
           FROM character_rentals
           WHERE campaign_id = ? AND status = 'active' AND expires_at_turn <= ?""",
        (int(campaign_id), int(current_turn)),
    ).fetchall()

    if not rows:
        return 0

    for row in rows:
        conn.execute(
            "UPDATE character_rentals SET status = 'expired' WHERE id = ?",
            (row["id"],),
        )
        inv_id = row["inventory_id"]
        if inv_id:
            conn.execute(
                "DELETE FROM character_inventory WHERE id = ?",
                (int(inv_id),),
            )

    conn.commit()
    return len(rows)


def get_current_turn(conn: sqlite3.Connection, campaign_id: int) -> int:
    """Return the latest turn_number for a campaign (0 if none)."""
    row = conn.execute(
        "SELECT COALESCE(MAX(turn_number), 0) FROM campaign_turns WHERE campaign_id = ?",
        (int(campaign_id),),
    ).fetchone()
    return int(row[0]) if row else 0
