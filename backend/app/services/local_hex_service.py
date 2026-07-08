"""Local hex map service — #993 FAZA ML.

Manages map_level=1 hex grids for hub locations (settlements with ≥2 sub-locs).
Local hexes are world_hexes rows with map_level=1 and parent_hex_id pointing to
the hub's map_level=0 world hex.

Numbers Policy (starting values, tunable):
  LOCAL_MAP_THRESHOLD = 2   — sub-locs needed to activate a local grid
  LOCAL_TRAVEL_MINUTES = 15 — in-game minutes per hex move on local map
  RISKY_ENCOUNTER_CHANCE = 0.20 — encounter chance for safe_for_rest=false locs
  SAFE_ENCOUNTER_CHANCE = 0.10 — encounter chance for safe_for_rest=true locs
    (#1147: rest-safety must not zero out street events — the PT-D2 pickpocket /
    guard-check design explicitly targets markets and taverns, which are almost
    always flagged safe_for_rest. 0.0 killed the whole local-encounter system.)
"""
from __future__ import annotations

import sqlite3
from typing import Optional

from app.core.constants import DEFAULT_REGION

import structlog

logger = structlog.get_logger()

LOCAL_MAP_THRESHOLD = 2
LOCAL_TRAVEL_MINUTES = 15
RISKY_ENCOUNTER_CHANCE = 0.20
SAFE_ENCOUNTER_CHANCE = 0.10

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


def normalize_hub_local_hexes(conn: sqlite3.Connection, hub_key: str) -> int:
    """Self-heal legacy local hexes sitting outside their hub's coordinate namespace.

    Before 2026-07-07, `_next_local_coords` always used offset 0 (no `base_q`
    namespacing). Hubs that got some local hexes assigned before that fix and more
    after it end up with siblings tens of thousands of pixels apart on the local
    map (one cluster near origin, one in the hub's namespace) — the map then
    renders as if only one sub-location exists. Idempotent + safe to call on every
    read: hex_id (and thus every FK / session_flags.local_hex.hex_id reference) is
    preserved, only q/r are rewritten in place.

    Returns the number of hexes fixed.
    """
    hub_hex_id = get_hub_hex_id(conn, hub_key)
    if hub_hex_id is None:
        return 0  # hub not anchored to the world map yet — nothing to normalize against

    base_q = (int(hub_hex_id) % 2000) * 30
    rows = conn.execute(
        "SELECT id, q, r, location_key FROM world_hexes "
        "WHERE map_level = 1 AND parent_hex_id = ? AND is_active = 1",
        (hub_hex_id,),
    ).fetchall()
    if not rows:
        return 0

    ring_dqs = [dq for dq, _dr in _LOCAL_HEX_RING]
    min_dq, max_dq = min(ring_dqs), max(ring_dqs)

    taken = {(int(r["q"]), int(r["r"])) for r in rows}
    fixed = 0
    for row in rows:
        q, r = int(row["q"]), int(row["r"])
        if min_dq <= (q - base_q) <= max_dq:
            continue  # already inside the hub's namespace

        taken.discard((q, r))
        new_coords: Optional[tuple[int, int]] = None
        for dq, dr in _LOCAL_HEX_RING:
            cand = (base_q + dq, dr)
            if cand not in taken:
                new_coords = cand
                break
        if new_coords is None:
            n = len(taken)
            new_coords = (base_q + n // 5, n % 5)
        taken.add(new_coords)
        new_q, new_r = new_coords

        conn.execute("UPDATE world_hexes SET q = ?, r = ? WHERE id = ?", (new_q, new_r, row["id"]))
        conn.execute(
            """UPDATE game_sessions
               SET session_flags = json_set(session_flags, '$.local_hex.q', ?, '$.local_hex.r', ?)
               WHERE json_extract(session_flags, '$.local_hex.hex_id') = ?""",
            (new_q, new_r, row["id"]),
        )
        logger.info(
            "local_hex_renamespaced",
            hub_key=hub_key, hex_id=row["id"], location_key=row["location_key"],
            old_q=q, old_r=r, new_q=new_q, new_r=new_r,
        )
        fixed += 1

    if fixed:
        conn.commit()
    return fixed


def get_local_hex_for_subloc(conn: sqlite3.Connection, sublocation_key: str) -> Optional[dict]:
    """Get the map_level=1 hex assigned to a specific sub-location."""
    row = conn.execute(
        "SELECT * FROM world_hexes WHERE location_key = ? AND map_level = 1 AND is_active = 1 LIMIT 1",
        (sublocation_key,),
    ).fetchone()
    return dict(row) if row else None


# ── Layout helpers ────────────────────────────────────────────────────────────

def _next_local_coords(
    conn: sqlite3.Connection, parent_hex_id: Optional[int], parent_key: Optional[str] = None
) -> tuple[int, int]:
    """Return the next free (q, r) for a new local hex under parent_hex_id.

    When parent_hex_id is None (hub has no world-map anchor), falls back to
    querying by parent_key via game_locations join so sibling sub-locs don't
    all collide at (0,0).
    """
    if parent_hex_id is not None:
        existing = conn.execute(
            "SELECT q, r FROM world_hexes WHERE map_level = 1 AND parent_hex_id = ? AND is_active = 1",
            (parent_hex_id,),
        ).fetchall()
    elif parent_key is not None:
        existing = conn.execute(
            """SELECT wh.q, wh.r FROM world_hexes wh
               JOIN game_locations gl ON gl.key = wh.location_key
               WHERE wh.map_level = 1 AND wh.is_active = 1
                 AND gl.parent_key = ? AND gl.is_active = 1""",
            (parent_key,),
        ).fetchall()
    else:
        existing = []
    taken = {(int(r["q"]), int(r["r"])) for r in existing}
    # UNIQUE(q,r,map_level,region) jest region-szeroki, a wiele hubów dzieli region
    # (RM3: region dziedziczy po hexie-rodzicu). Bez separacji dwa huby kolidowałyby
    # na (0,0) itd. Namespace per hub = offset q o parent_hex_id*100 (id unikat →
    # gridy się nie nakładają; LocalMap i tak centruje na heksach, więc absolutne
    # współrzędne nie mają znaczenia dla renderu).
    base_q = ((int(parent_hex_id) % 2000) * 30) if parent_hex_id is not None else 0
    for dq, dr in _LOCAL_HEX_RING:
        coords = (base_q + dq, dr)
        if coords not in taken:
            return coords
    # Overflow beyond predefined ring — indeksowy fallback w tym samym namespace.
    n = len(taken)
    return (base_q + n // 5, n % 5)


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
    # Heal any legacy hexes (pre-namespace) before assigning new ones — otherwise
    # a fresh sub-loc would land correctly-namespaced next to scattered old ones.
    normalize_hub_local_hexes(conn, parent_key)

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

        q, r = _next_local_coords(conn, hub_hex_id, parent_key=parent_key)
        safe = bool(subloc["safe_for_rest"])
        encounter_chance = SAFE_ENCOUNTER_CHANCE if safe else RISKY_ENCOUNTER_CHANCE

        parent_region = DEFAULT_REGION
        if hub_hex_id is not None:
            parent_row = conn.execute(
                "SELECT region FROM world_hexes WHERE id = ?", (hub_hex_id,)
            ).fetchone()
            if parent_row and parent_row["region"]:
                parent_region = parent_row["region"]

        cursor = conn.execute(
            """
            INSERT INTO world_hexes
                (q, r, hex_type, label, location_key, map_level, parent_hex_id,
                 encounter_chance, created_by_gm, created_by_campaign_id, region)
            VALUES (?, ?, 'settlement', ?, ?, 1, ?, ?, 0, ?, ?)
            """,
            (q, r, subloc["label"], sk, hub_hex_id, encounter_chance, campaign_id, parent_region),
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


def backfill_local_hex_regions(conn: sqlite3.Connection) -> int:
    """RM3: align region on map_level=1 hexes to their parent map_level=0 hex.

    Project rule: ML sub-maps ALWAYS inherit the region of their parent hex
    (via parent_hex_id). Because world_hexes.region is NOT NULL DEFAULT 'kresy',
    existing ML hexes default to 'kresy' rather than NULL, so this aligns any ML
    hex whose region differs from its parent (NULL-region rows covered too).
    Returns count of updated rows.
    """
    rows = conn.execute(
        "SELECT id, parent_hex_id, region FROM world_hexes WHERE map_level = 1"
    ).fetchall()
    updated = 0
    for row in rows:
        if not row["parent_hex_id"]:
            continue
        parent = conn.execute(
            "SELECT region FROM world_hexes WHERE id = ?", (row["parent_hex_id"],)
        ).fetchone()
        if parent and parent["region"] and parent["region"] != row["region"]:
            conn.execute(
                "UPDATE world_hexes SET region = ? WHERE id = ?",
                (parent["region"], row["id"]),
            )
            updated += 1
    if updated:
        conn.commit()
    return updated
