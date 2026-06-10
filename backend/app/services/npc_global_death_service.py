"""F19 (#479) — Global NPC death states.

When an NPC is killed, is_dead=1 on the npcs table persists globally.
This means the NPC is absent from future campaigns in the same world.
"""
from typing import Any


def mark_npc_dead_global(conn, npc_key: str) -> None:
    """Set is_dead=1 for the NPC globally. No-op if NPC not found."""
    try:
        conn.execute(
            "UPDATE npcs SET is_dead = 1 WHERE key = ?", (npc_key,)
        )
        conn.commit()
    except Exception:
        pass


def is_npc_dead_global(conn, npc_key: str) -> bool:
    """Return True if the NPC has is_dead=1, False otherwise (including missing NPC)."""
    try:
        row = conn.execute(
            "SELECT is_dead FROM npcs WHERE key = ?", (npc_key,)
        ).fetchone()
        if not row:
            return False
        return bool(row["is_dead"] if hasattr(row, "keys") else row[0])
    except Exception:
        return False


def get_living_npcs(conn) -> list[dict]:
    """Return all NPCs where is_dead = 0 (or column doesn't exist → all NPCs)."""
    try:
        rows = conn.execute(
            "SELECT * FROM npcs WHERE is_dead = 0 OR is_dead IS NULL"
        ).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        # Fallback for old schema without is_dead column
        try:
            rows = conn.execute("SELECT * FROM npcs").fetchall()
            return [dict(r) for r in rows]
        except Exception:
            return []


def revive_npc(conn, npc_key: str) -> None:
    """Reset is_dead=0 for the NPC (admin/narrative resurrection)."""
    try:
        conn.execute(
            "UPDATE npcs SET is_dead = 0 WHERE key = ?", (npc_key,)
        )
        conn.commit()
    except Exception:
        pass
