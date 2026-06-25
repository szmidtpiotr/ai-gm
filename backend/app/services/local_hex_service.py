"""Local hex map service — #993 FAZA ML.

Manages map_level=1 hex grids for hub locations (settlements with ≥2 sub-locs).
Local hexes are world_hexes rows with map_level=1 and parent_hex_id pointing to
the hub's map_level=0 world hex.

Numbers Policy (starting values, tunable):
  LOCAL_MAP_THRESHOLD = 2   — sub-locs needed to activate a local grid
  LOCAL_TRAVEL_MINUTES = 15 — in-game minutes per hex move on local map
  RISKY_ENCOUNTER_CHANCE = 0.20 — encounter chance for safe_for_rest=false locs
"""
from __future__ import annotations

import sqlite3
from typing import Optional

import structlog

logger = structlog.get_logger()

LOCAL_MAP_THRESHOLD = 2
LOCAL_TRAVEL_MINUTES = 15
RISKY_ENCOUNTER_CHANCE = 0.20

# Axial coords for local hex ring layout.
# Index 0 = entry hex (center). Rings expand outward.
_LOCAL_HEX_RING: list[tuple[int, int]] = [
    (0, 0),
    (1, 0), (0, 1), (-1, 1), (-1, 0), (0, -1), (1, -1),
    (2, 0), (1, 1), (0, 2), (-1, 2), (-2, 1), (-2, 0),
    (2, -1), (2, -2), (1, -2), (0, -2), (-1, -1), (-2, 2),
]


# ── Lookups ───────────────────────────────────────────────────────────────────

def get_hub_hex_id(conn: sqlite3.Connection, hub_location_key: str) -> Optional[int]:
    """Find the map_level=0 world_hexes.id for a hub location.

    Uses game_locations.world_hex_q/world_hex_r to locate the hex.
    Returns None if the hub has no world-map anchor.
    """
    loc = conn.execute(
        "SELECT world_hex_q, world_hex_r FROM game_locations WHERE key = ? AND is_active = 1",
        (hub_location_key,),
    ).fetchone()
    if not loc or loc["world_hex_q"] is None:
        return None
    row = conn.execute(
        "SELECT id FROM world_hexes WHERE q = ? AND r = ? AND map_level = 0 AND is_active = 1",
        (loc["world_hex_q"], loc["world_hex_r"]),
    ).fetchone()
    return int(row["id"]) if row else None


def count_active_sublocs(conn: sqlite3.Connection, parent_key: str) -> int:
    """Count active sub-locations whose parent_key matches hub."""
    row = conn.execute(
        "SELECT COUNT(*) AS cnt FROM game_locations WHERE parent_key = ? AND is_active = 1",
        (parent_key,),
    ).fetchone()
    return int(row["cnt"]) if row else 0


def get_local_hexes(conn: sqlite3.Connection, hub_location_key: str) -> list[dict]:
    """Return all map_level=1 hexes belonging to a hub.

    Queries via parent_hex_id if hub has a world hex; falls back to joining
    via location_key → game_locations.parent_key for hubs without a world hex.
    """
    hub_hex_id = get_hub_hex_id(conn, hub_location_key)
    if hub_hex_id is not None:
        rows = conn.execute(
            "SELECT * FROM world_hexes WHERE map_level = 1 AND parent_hex_id = ? AND is_active = 1",
            (hub_hex_id,),
        ).fetchall()
    else:
        # Fallback: match via sub-location keys sharing the same parent_key
        rows = conn.execute(
            """
            SELECT wh.* FROM world_hexes wh
            JOIN game_locations gl ON gl.key = wh.location_key
            WHERE wh.map_level = 1
              AND wh.is_active = 1
              AND gl.parent_key = ?
              AND gl.is_active = 1
            """,
            (hub_location_key,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_local_hex_for_subloc(conn: sqlite3.Connection, sublocation_key: str) -> Optional[dict]:
    """Get the map_level=1 hex assigned to a specific sub-location."""
    row = conn.execute(
        "SELECT * FROM world_hexes WHERE location_key = ? AND map_level = 1 AND is_active = 1 LIMIT 1",
        (sublocation_key,),
    ).fetchone()
    return dict(row) if row else None


# ── Layout helpers ────────────────────────────────────────────────────────────

def _next_local_coords(
    conn: sqlite3.Connection, parent_hex_id: Optional[int]
) -> tuple[int, int]:
    """Return the next free (q, r) for a new local hex under parent_hex_id."""
    if parent_hex_id is not None:
        existing = conn.execute(
            "SELECT q, r FROM world_hexes WHERE map_level = 1 AND parent_hex_id = ? AND is_active = 1",
            (parent_hex_id,),
        ).fetchall()
    else:
        existing = []
    taken = {(int(r["q"]), int(r["r"])) for r in existing}
    for coords in _LOCAL_HEX_RING:
        if coords not in taken:
            return coords
    # Overflow beyond predefined ring — use row index as offset
    n = len(taken)
    return (n // 5, n % 5)


# ── Core assignment ───────────────────────────────────────────────────────────

def auto_assign_local_hex(
    conn: sqlite3.Connection,
    sublocation_key: str,
    parent_key: str,
    campaign_id: Optional[int] = None,
) -> Optional[dict]:
    """Attach a local hex to sublocation_key if hub now has ≥ LOCAL_MAP_THRESHOLD sub-locs.

    When the threshold is first crossed, back-fills hexes for any existing sub-locs
    that don't have one yet.  Idempotent — won't double-assign.

    Returns the new (or existing) hex dict for sublocation_key, or None if below threshold.
    """
    count = count_active_sublocs(conn, parent_key)
    if count < LOCAL_MAP_THRESHOLD:
        logger.info(
            "local_hex_below_threshold",
            parent_key=parent_key,
            count=count,
            threshold=LOCAL_MAP_THRESHOLD,
        )
        return None

    hub_hex_id = get_hub_hex_id(conn, parent_key)

    # Load all active sub-locs ordered by creation (id ASC) for stable ring layout
    sublocs = conn.execute(
        """
        SELECT key, label, safe_for_rest FROM game_locations
        WHERE parent_key = ? AND is_active = 1
        ORDER BY id ASC
        """,
        (parent_key,),
    ).fetchall()

    assigned_hex: Optional[dict] = None

    for subloc in sublocs:
        sk = subloc["key"]

        # Skip if already has a hex
        existing_row = conn.execute(
            "SELECT * FROM world_hexes WHERE location_key = ? AND map_level = 1 AND is_active = 1 LIMIT 1",
            (sk,),
        ).fetchone()
        if existing_row:
            if sk == sublocation_key:
                assigned_hex = dict(existing_row)
            continue

        q, r = _next_local_coords(conn, hub_hex_id)
        safe = bool(subloc["safe_for_rest"])
        encounter_chance = 0.0 if safe else RISKY_ENCOUNTER_CHANCE

        cursor = conn.execute(
            """
            INSERT INTO world_hexes
                (q, r, hex_type, label, location_key, map_level, parent_hex_id,
                 encounter_chance, created_by_gm, created_by_campaign_id)
            VALUES (?, ?, 'settlement', ?, ?, 1, ?, ?, 0, ?)
            """,
            (q, r, subloc["label"], sk, hub_hex_id, encounter_chance, campaign_id),
        )
        conn.commit()

        new_row = conn.execute(
            "SELECT * FROM world_hexes WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()

        if sk == sublocation_key:
            assigned_hex = dict(new_row) if new_row else None

        logger.info(
            "local_hex_assigned",
            sublocation_key=sk,
            parent_key=parent_key,
            q=q,
            r=r,
            hub_hex_id=hub_hex_id,
        )

    return assigned_hex
