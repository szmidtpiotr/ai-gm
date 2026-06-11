"""Campaign hub modes — D9 (#384).

The 5 ways to start play. Each mode reports an `available` flag based on whether
its backing data exists, so the hub never routes a player into a broken/empty
flow (e.g. "Gotowa kampania" is hidden/disabled when no template is published).

Admin can also force-disable any mode via System → Tryby gry (game_mode_flags
stored in game_config_meta). A disabled flag always wins over data availability.
"""
from __future__ import annotations

import json
import sqlite3

# (key, label, description) — order = display order in the hub.
_MODES = [
    ("nowa", "Nowa kampania", "Stwórz świeżą przygodę od zera"),
    ("gotowa", "Gotowa kampania", "Wybierz gotowy scenariusz (szablon)"),
    ("loch", "Loch", "Farmowalny loch solo"),
    ("loch_kafelki", "Loch z kafelkami", "Loch budowany z kafelków"),
    ("multiplayer", "Multiplayer", "Graj z innymi"),
]

# Maps mode key → game_mode_flags field. Default True = enabled by default.
_FLAG_MAP = {
    "nowa":        ("ai_campaign_enabled",   True),
    "gotowa":      ("prebuilt_enabled",      True),
    "loch":        ("dungeon_enabled",       True),
    "loch_kafelki":("dungeon_tiles_enabled", True),
    "multiplayer": ("multiplayer_enabled",   False),
}


def _count(conn: sqlite3.Connection, sql: str) -> int:
    try:
        row = conn.execute(sql).fetchone()
        return int((row[0] if row else 0) or 0)
    except sqlite3.OperationalError:
        return 0


def _load_mode_flags(conn: sqlite3.Connection) -> dict:
    """Read admin-controlled game_mode_flags from game_config_meta."""
    try:
        row = conn.execute(
            "SELECT value FROM game_config_meta WHERE key = 'game_mode_flags'"
        ).fetchone()
        if row and row[0]:
            return json.loads(row[0])
    except Exception:
        pass
    return {}


def get_available_modes(conn: sqlite3.Connection) -> list[dict]:
    """Return the 5 hub modes with availability + a count where relevant."""
    published = _count(conn, "SELECT COUNT(*) FROM campaign_templates WHERE status = 'published' AND COALESCE(player_visible, 1) = 1")
    dungeons = _count(conn, "SELECT COUNT(*) FROM game_dungeons WHERE COALESCE(is_active, 1) = 1")
    tiles = _count(conn, "SELECT COUNT(*) FROM dungeon_tiles WHERE is_active = 1")

    data_availability = {
        "nowa":        (True, None),
        "gotowa":      (published > 0, published),
        "loch":        (dungeons > 0, dungeons),
        "loch_kafelki":(tiles > 0, tiles),
        "multiplayer": (True, None),
    }

    flags = _load_mode_flags(conn)

    out: list[dict] = []
    for key, label, desc in _MODES:
        flag_field, flag_default = _FLAG_MAP[key]
        admin_enabled = bool(flags.get(flag_field, flag_default))
        data_avail, count = data_availability[key]
        out.append({
            "key": key,
            "label": label,
            "description": desc,
            "available": admin_enabled and bool(data_avail),
            "count": count,
        })
    return out
