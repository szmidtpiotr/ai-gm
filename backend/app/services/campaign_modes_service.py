"""Campaign hub modes — D9 (#384).

The 5 ways to start play. Each mode reports an `available` flag based on whether
its backing data exists, so the hub never routes a player into a broken/empty
flow (e.g. "Gotowa kampania" is hidden/disabled when no template is published).
"""
from __future__ import annotations

import sqlite3

# (key, label, description) — order = display order in the hub.
_MODES = [
    ("nowa", "Nowa kampania", "Stwórz świeżą przygodę od zera"),
    ("gotowa", "Gotowa kampania", "Wybierz gotowy scenariusz (szablon)"),
    ("loch", "Loch", "Farmowalny loch solo"),
    ("loch_kafelki", "Loch z kafelkami", "Loch budowany z kafelków"),
    ("multiplayer", "Multiplayer", "Graj z innymi"),
]


def _count(conn: sqlite3.Connection, sql: str) -> int:
    try:
        row = conn.execute(sql).fetchone()
        return int((row[0] if row else 0) or 0)
    except sqlite3.OperationalError:
        return 0


def get_available_modes(conn: sqlite3.Connection) -> list[dict]:
    """Return the 5 hub modes with availability + a count where relevant."""
    published = _count(conn, "SELECT COUNT(*) FROM campaign_templates WHERE status = 'published'")
    dungeons = _count(conn, "SELECT COUNT(*) FROM game_dungeons WHERE COALESCE(is_active, 1) = 1")
    tiles = _count(conn, "SELECT COUNT(*) FROM dungeon_tiles")

    availability = {
        "nowa": (True, None),
        "gotowa": (published > 0, published),
        "loch": (dungeons > 0, dungeons),
        "loch_kafelki": (tiles > 0, tiles),
        "multiplayer": (True, None),
    }

    out: list[dict] = []
    for key, label, desc in _MODES:
        avail, count = availability[key]
        out.append({
            "key": key,
            "label": label,
            "description": desc,
            "available": bool(avail),
            "count": count,
        })
    return out
