"""
Hex Travel Service — Task 40.
A* pathfinding on world_hexes grid + hex_teleport_connections.
Chain travel: resolve full journey, roll encounters per hex, interrupt on trigger.
"""
from __future__ import annotations

import heapq
import json
import random
import sqlite3
from typing import Any, Optional

import structlog

logger = structlog.get_logger()

DB_PATH = "/data/ai_gm.db"


# ── Hex adjacency (flat-top) ──────────────────────────────────────────────────

_DIRECTIONS = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, -1), (-1, 1)]


def hex_distance(q1: int, r1: int, q2: int, r2: int) -> int:
    """Axial coordinate hex distance."""
    return max(abs(q1 - q2), abs(r1 - r2), abs((q1 + r1) - (q2 + r2)))


def hex_neighbors(q: int, r: int) -> list[tuple[int, int]]:
    return [(q + dq, r + dr) for dq, dr in _DIRECTIONS]


# ── Graph loading ─────────────────────────────────────────────────────────────

def _load_hex_graph(conn: sqlite3.Connection) -> dict[tuple[int, int], dict]:
    """
    Load world_hexes and hex_teleport_connections into an adjacency-aware dict.
    Returns: {(q, r): {hex_data + 'teleport_edges': [...]}}
    """
    hexes: dict[tuple[int, int], dict] = {}
    rows = conn.execute(
        "SELECT q, r, hex_type, label, encounter_chance, encounter_pool, location_key "
        "FROM world_hexes WHERE is_active = 1 AND map_level = 0"
    ).fetchall()
    for row in rows:
        q, r = int(row["q"]), int(row["r"])
        h = dict(row)
        try:
            h["encounter_pool"] = json.loads(h.get("encounter_pool") or "[]")
        except Exception:
            h["encounter_pool"] = []
        h["teleport_edges"] = []
        hexes[(q, r)] = h

    # Load teleport connections and attach to both endpoints
    trows = conn.execute(
        "SELECT * FROM hex_teleport_connections WHERE is_active = 1"
    ).fetchall()
    for t in trows:
        fk = (int(t["from_q"]), int(t["from_r"]))
        tk = (int(t["to_q"]), int(t["to_r"]))
        td = dict(t)
        if fk in hexes:
            hexes[fk]["teleport_edges"].append({**td, "_dest": tk})
        if t["is_bidirectional"] and tk in hexes:
            hexes[tk]["teleport_edges"].append({**td, "_dest": fk})

    return hexes


def _load_hex_type_config(conn: sqlite3.Connection) -> dict[str, dict]:
    rows = conn.execute("SELECT * FROM hex_type_config WHERE is_active = 1").fetchall()
    return {r["hex_type"]: dict(r) for r in rows}


# ── A* pathfinding ────────────────────────────────────────────────────────────

def find_path(
    start: tuple[int, int],
    goal: tuple[int, int],
    hexes: dict[tuple[int, int], dict],
) -> list[tuple[int, int]] | None:
    """
    A* from start to goal on hex grid + teleport connections.
    Returns ordered list of (q, r) including start and goal, or None if unreachable.
    """
    if start == goal:
        return [start]

    # Priority queue: (f_score, node)
    open_set: list[tuple[float, tuple[int, int]]] = []
    heapq.heappush(open_set, (0, start))

    came_from: dict[tuple[int, int], tuple[int, int] | None] = {start: None}
    g_score: dict[tuple[int, int], float] = {start: 0.0}

    while open_set:
        _, current = heapq.heappop(open_set)

        if current == goal:
            # Reconstruct path
            path = []
            node: tuple[int, int] | None = current
            while node is not None:
                path.append(node)
                node = came_from[node]
            path.reverse()
            return path

        # Adjacent hex neighbors
        for nq, nr in hex_neighbors(*current):
            neighbor = (nq, nr)
            if neighbor not in hexes:
                continue
            tentative_g = g_score[current] + 1.0  # 1 hex = 1 movement unit
            if tentative_g < g_score.get(neighbor, float("inf")):
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g
                f = tentative_g + hex_distance(nq, nr, *goal)
                heapq.heappush(open_set, (f, neighbor))

        # Teleport edges from current hex
        for edge in hexes.get(current, {}).get("teleport_edges", []):
            dest = edge["_dest"]
            if dest not in hexes:
                continue
            # Teleport cost = travel_hours as movement units
            tp_cost = float(edge.get("travel_hours", 8.0))
            tentative_g = g_score[current] + tp_cost
            if tentative_g < g_score.get(dest, float("inf")):
                came_from[dest] = current
                g_score[dest] = tentative_g
                f = tentative_g + hex_distance(*dest, *goal)
                heapq.heappush(open_set, (f, dest))

    return None  # No path found


# ── Encounter resolution ──────────────────────────────────────────────────────

def _roll_encounter(hex_data: dict, hex_type_cfg: dict[str, dict]) -> bool:
    """Roll encounter for a hex. Returns True if encounter triggers."""
    base_chance = float(hex_data.get("encounter_chance") or 0.15)
    # Adjust by hex type if configured
    ht = hex_data.get("hex_type", "plains")
    type_chance = float(hex_type_cfg.get(ht, {}).get("encounter_base_chance") or base_chance)
    final_chance = max(base_chance, type_chance)
    return random.random() < final_chance


def _pick_encounter_enemy(hex_data: dict) -> str | None:
    pool = hex_data.get("encounter_pool") or []
    if not pool:
        return None
    return random.choice(pool)


# ── Location → hex resolution (U30) ─────────────────────────────────────────

def resolve_location_key_to_hex(
    location_key: str,
    conn: sqlite3.Connection,
) -> tuple[int, int] | None:
    """U30: Resolve a location_key → (q, r).

    Primary: world_hexes.location_key lookup (fast, canonical).
    Fallback (#992): game_locations.world_hex_q/r when the hex's location_key
    was displaced (e.g. by a temp_camp overwrite) but game_locations still knows
    its coordinates.
    Returns None when neither path resolves.
    """
    if not location_key:
        return None
    row = conn.execute(
        "SELECT q, r FROM world_hexes WHERE location_key = ? AND is_active = 1 LIMIT 1",
        (location_key,),
    ).fetchone()
    if row:
        return (int(row["q"]), int(row["r"]))
    # #992 fallback: location may still know its hex even if world_hexes lost the pointer
    loc = conn.execute(
        "SELECT world_hex_q, world_hex_r FROM game_locations"
        " WHERE key = ? AND is_active = 1 AND world_hex_q IS NOT NULL LIMIT 1",
        (location_key,),
    ).fetchone()
    if loc:
        return (int(loc["world_hex_q"]), int(loc["world_hex_r"]))
    return None


def detect_named_destination_hex(
    target_location_key: str,
    current_hex: dict | None,
    conn: sqlite3.Connection,
) -> tuple[int, int] | None:
    """#992: Detect if a named destination is on a DIFFERENT hex than the player's current hex.

    Used to redirect named-destination movement to hex-travel when the destination
    is beyond the current hex boundary.

    Resolution order for target hex:
    1. Direct: resolve_location_key_to_hex(target_location_key)
    2. Via parent: look up game_locations.parent_key, then resolve that

    Returns (q, r) of the target hex if it differs from current_hex, else None.
    """
    if not target_location_key or not current_hex:
        return None
    cur_q = int(current_hex.get("q", 0))
    cur_r = int(current_hex.get("r", 0))

    # Direct resolution
    target = resolve_location_key_to_hex(target_location_key, conn)
    if target is None:
        # Try via parent_key (sub-location inherits its parent's hex)
        parent_row = conn.execute(
            "SELECT parent_key FROM game_locations WHERE key = ? AND is_active = 1 LIMIT 1",
            (target_location_key,),
        ).fetchone()
        if parent_row and parent_row["parent_key"]:
            target = resolve_location_key_to_hex(parent_row["parent_key"], conn)

    if target is None:
        return None
    if target == (cur_q, cur_r):
        return None  # same hex — not cross-hex travel
    return target


# ── Main travel resolver ──────────────────────────────────────────────────────

def resolve_chain_travel(
    campaign_id: int,
    character_id: int,
    from_hex: tuple[int, int],
    to_hex: tuple[int, int],
    character_sheet: dict,
    conn: sqlite3.Connection,
) -> dict[str, Any]:
    """
    Chain travel from from_hex to to_hex.

    Returns:
        {
          "ok": bool,
          "error": str | None,           # if unreachable
          "path": [(q, r), ...],
          "total_hours": float,
          "encounter": dict | None,      # if travel interrupted by encounter
          "encounter_hex": (q, r) | None,
          "arrived_hex": (q, r),         # where player ended up
          "teleport_used": dict | None,  # teleport connection used if any
          "item_blocked": str | None,    # if teleport requires missing item
          "hex_data": dict,              # data for arrived_hex
        }
    """
    hexes = _load_hex_graph(conn)
    hex_type_cfg = _load_hex_type_config(conn)

    if from_hex not in hexes and from_hex != to_hex:
        # Player is not on a hex yet — allow if destination exists
        pass

    if to_hex not in hexes:
        return {
            "ok": False,
            "error": "Nie ma tam nic — to nieznane terytorium.",
            "path": [], "total_hours": 0,
            "arrived_hex": {"q": from_hex[0], "r": from_hex[1]}, "encounter": None, "encounter_hex": None,
            "hex_data": {}, "teleport_used": None, "item_blocked": None,
        }

    if from_hex == to_hex:
        dest_data = hexes.get(to_hex, {})
        return {
            "ok": True, "error": None,
            "path": [{"q": to_hex[0], "r": to_hex[1]}],
            "total_hours": 0,
            "arrived_hex": {"q": to_hex[0], "r": to_hex[1]},
            "encounter": None, "encounter_hex": None,
            "hex_data": dest_data, "teleport_used": None, "item_blocked": None,
        }

    path = find_path(from_hex, to_hex, hexes)
    if path is None:
        return {
            "ok": False,
            "error": "Nie ma drogi do tego miejsca. Potrzebujesz łodzi lub innego sposobu.",
            "path": [], "total_hours": 0,
            "arrived_hex": {"q": from_hex[0], "r": from_hex[1]}, "encounter": None, "encounter_hex": None,
            "hex_data": hexes.get(from_hex, {}), "teleport_used": None, "item_blocked": None,
        }

    # Check teleport item requirements along the path
    # (simplified: check only direct teleport edges, not mid-path)
    teleport_used = None
    for edge in hexes.get(from_hex, {}).get("teleport_edges", []):
        if edge["_dest"] == to_hex:
            req = edge.get("requires_item_key")
            if req:
                has_item = conn.execute(
                    "SELECT 1 FROM character_inventory WHERE character_id = ? AND item_key = ?",
                    (character_id, req),
                ).fetchone()
                if not has_item:
                    item_row = conn.execute(
                        "SELECT label FROM game_config_items WHERE key = ?", (req,)
                    ).fetchone()
                    item_label = item_row["label"] if item_row else req
                    return {
                        "ok": False,
                        "error": f"Potrzebujesz {item_label} aby tędy przejść.",
                        "path": [], "total_hours": 0,
                        "arrived_hex": {"q": from_hex[0], "r": from_hex[1]}, "encounter": None, "encounter_hex": None,
                        "hex_data": hexes.get(from_hex, {}), "teleport_used": None,
                        "item_blocked": item_label,
                    }
            teleport_used = dict(edge)
            break

    # Compute total travel hours along path
    total_hours = 0.0
    for i in range(1, len(path)):
        prev, cur = path[i - 1], path[i]
        # Check if this step is a teleport
        is_tp = False
        for edge in hexes.get(prev, {}).get("teleport_edges", []):
            if edge["_dest"] == cur:
                total_hours += float(edge.get("travel_hours", 8.0))
                is_tp = True
                if not teleport_used:
                    teleport_used = dict(edge)
                break
        if not is_tp:
            total_hours += 1.0  # 1 hour per hex

    # Roll encounters along path (skip start hex)
    encounter_result = None
    encounter_hex = None
    arrived_hex = to_hex  # assume full travel unless interrupted

    # Load cleared encounters for this campaign (won't re-trigger)
    cleared_coords: set[tuple[int, int]] = set()
    try:
        cleared_rows = conn.execute(
            "SELECT hex_q, hex_r FROM campaign_hex_data WHERE campaign_id = ? AND encounter_cleared = 1",
            (campaign_id,),
        ).fetchall()
        cleared_coords = {(int(r["hex_q"]), int(r["hex_r"])) for r in cleared_rows}
    except Exception:
        pass

    for step_hex in path[1:]:
        hex_data = hexes.get(step_hex, {})
        # Skip encounter if already cleared at this hex
        if step_hex in cleared_coords:
            continue
        if _roll_encounter(hex_data, hex_type_cfg):
            enemy_key = _pick_encounter_enemy(hex_data)
            if enemy_key:
                encounter_result = {
                    "enemy_key": enemy_key,
                    "hex_type": hex_data.get("hex_type", "plains"),
                    "hex_label": hex_data.get("label"),
                    "atmosphere": hex_data.get("atmosphere"),
                }
                encounter_hex = step_hex
                arrived_hex = step_hex  # interrupted here
                # Recalculate hours to interruption point
                total_hours = 0.0
                interrupted_path = path[:path.index(step_hex) + 1]
                for i in range(1, len(interrupted_path)):
                    prev, cur = interrupted_path[i - 1], interrupted_path[i]
                    is_tp = any(e["_dest"] == cur for e in hexes.get(prev, {}).get("teleport_edges", []))
                    total_hours += (next(
                        e.get("travel_hours", 8.0) for e in hexes.get(prev, {}).get("teleport_edges", [])
                        if e["_dest"] == cur
                    ) if is_tp else 1.0)
                break

    # Stage 2B R4: deactivate any temp_camp_* on the hex the player just left.
    if arrived_hex != from_hex:
        try:
            from app.services.world_service import deactivate_temporary_location_on_hex
            deactivate_temporary_location_on_hex(conn, from_hex[0], from_hex[1])
        except Exception as e:
            logger.warning("temp_camp_cleanup_failed", q=from_hex[0], r=from_hex[1], error=str(e))

    # Update character's current hex in session_flags
    try:
        gs = conn.execute(
            "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
            (campaign_id,),
        ).fetchone()
        if gs:
            flags = json.loads(gs["session_flags"] or "{}")
            flags["current_hex"] = {"q": arrived_hex[0], "r": arrived_hex[1]}
            # Also update location context for narrator if arrived hex has a linked location
            arrived_data = hexes.get(arrived_hex, {})
            _hex_location_key = arrived_data.get("location_key")

            # #549: Replace ai_generated legacy locations with DB-seeded ones on arrival
            if _hex_location_key:
                _ai_check = conn.execute(
                    "SELECT ai_generated FROM game_locations"
                    " WHERE key = ? AND COALESCE(is_active,1)=1 LIMIT 1",
                    (_hex_location_key,),
                ).fetchone()
                if _ai_check and _ai_check["ai_generated"] == 1:
                    _aq, _ar = arrived_hex[0], arrived_hex[1]
                    _hex_type = arrived_data.get("hex_type", "plains")
                    conn.execute(
                        "UPDATE world_hexes SET location_key = NULL"
                        " WHERE q = ? AND r = ? AND is_active = 1",
                        (_aq, _ar),
                    )
                    try:
                        from app.services.placement_engine import try_place_location_on_hex
                        _hex_location_key = try_place_location_on_hex(
                            conn, _aq, _ar, _hex_type, campaign_seed=campaign_id
                        )
                    except Exception:
                        _hex_location_key = None

            # Try placement engine for hexes that have no DB-seeded location
            if not _hex_location_key and arrived_hex != from_hex:
                _aq, _ar = arrived_hex[0], arrived_hex[1]
                _hex_type = arrived_data.get("hex_type", "plains")
                try:
                    from app.services.placement_engine import try_place_location_on_hex
                    _hex_location_key = try_place_location_on_hex(
                        conn, _aq, _ar, _hex_type, campaign_seed=campaign_id
                    )
                except Exception:
                    _hex_location_key = None

            if _hex_location_key:
                flags["current_location_key"] = _hex_location_key
                _loc_row = conn.execute(
                    "SELECT id FROM game_locations WHERE key = ? AND COALESCE(is_active,1)=1",
                    (_hex_location_key,),
                ).fetchone()
                if _loc_row:
                    conn.execute(
                        "UPDATE game_sessions SET current_location_id = ? WHERE campaign_id = ?",
                        (int(_loc_row["id"]), campaign_id),
                    )
                # HF-11 (#553): visit_location beat auto-complete on mechanical arrival
                # (same dead-code root cause as talk_to_npc — process_v2_turn unreachable).
                if arrived_hex != from_hex:
                    try:
                        from app.services.campaign_plan_runtime import auto_complete_beats_by_event
                        _tn_loc = conn.execute(
                            "SELECT COALESCE(MAX(turn_number), 0) FROM campaign_turns"
                            " WHERE campaign_id = ?",
                            (campaign_id,),
                        ).fetchone()[0]
                        auto_complete_beats_by_event(
                            campaign_id, "visit_location", _hex_location_key, _tn_loc, conn
                        )
                        # #1011: auto-close visit quests on mechanical arrival (no tag needed)
                        from app.services.quest_persist_service import auto_complete_quests_by_event
                        auto_complete_quests_by_event(
                            conn, campaign_id, "visit_location", _hex_location_key, _tn_loc
                        )
                    except Exception:
                        pass
            elif arrived_hex != from_hex:
                # Arrived at a hex with no linked location — clear stale location context
                flags.pop("current_location_key", None)
                conn.execute(
                    "UPDATE game_sessions SET current_location_id = NULL WHERE campaign_id = ?",
                    (campaign_id,),
                )
            conn.execute(
                "UPDATE game_sessions SET session_flags = ? WHERE campaign_id = ?",
                (json.dumps(flags, ensure_ascii=False), campaign_id),
            )

        # Mark hex as discovered for this campaign
        q, r = arrived_hex
        conn.execute(
            """INSERT INTO campaign_hex_data (campaign_id, hex_q, hex_r, discovered)
               VALUES (?,?,?,1)
               ON CONFLICT(campaign_id, hex_q, hex_r) DO UPDATE SET discovered = 1""",
            (campaign_id, q, r),
        )
        conn.commit()
    except Exception:
        pass

    return {
        "ok": True,
        "error": None,
        "path": [{"q": q, "r": r} for q, r in path],
        "total_hours": total_hours,
        "encounter": encounter_result,
        "encounter_hex": {"q": encounter_hex[0], "r": encounter_hex[1]} if encounter_hex else None,
        "arrived_hex": {"q": arrived_hex[0], "r": arrived_hex[1]},
        "teleport_used": teleport_used,
        "item_blocked": None,
        "hex_data": hexes.get(arrived_hex, {}),
    }


# ── Starting hex resolution ───────────────────────────────────────────────────

def _normalize(s: str) -> str:
    """Lowercase, strip Polish diacritics, keep only alnum."""
    _PL = str.maketrans("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ", "acelnoszzACELNOSZZ")
    return s.lower().translate(_PL).replace("-", " ")


def _label_similarity(a: str, b: str) -> float:
    """Word-overlap score between two location label strings (0.0–1.0)."""
    wa = set(_normalize(a).split())
    wb = set(_normalize(b).split())
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / max(len(wa), len(wb))


def _pick_random_start_location(conn: sqlite3.Connection) -> str:
    """
    Pick a starting location from canonical game_locations.
    50% settlement (town/city/village), 50% wilderness — prevents always-wilderness starts.
    Called when no explicit starting_location_name is provided.
    """
    if random.random() < 0.5:
        row = conn.execute(
            """SELECT label FROM game_locations
               WHERE is_active=1 AND canonical=1 AND location_type='macro'
                 AND map_icon IN ('town','city','village','castle')
                 AND label NOT LIKE 'Start %' AND label NOT LIKE 'Test %'
                 AND review_status='permanent'
               ORDER BY RANDOM() LIMIT 1"""
        ).fetchone()
        if row:
            return row["label"]
    row = conn.execute(
        """SELECT label FROM game_locations
           WHERE is_active=1 AND canonical=1 AND location_type='macro'
             AND map_icon IN ('forest','road','wilderness','plains','mountain','cave','swamp')
             AND label NOT LIKE 'Start %' AND label NOT LIKE 'Test %'
             AND review_status='permanent'
           ORDER BY RANDOM() LIMIT 1"""
    ).fetchone()
    return row["label"] if row else ""


def _infer_hex_type_from_name(name: str) -> str:
    """Guess terrain type from a location name."""
    n = _normalize(name)
    for word, htype in [
        ("miasto", "town"), ("wioska", "town"), ("wies", "town"), ("osada", "town"),
        ("zamek", "castle"), ("twierdza", "castle"), ("fort", "castle"),
        ("las", "forest"), ("puszcza", "forest"), ("bor", "forest"),
        ("ruiny", "ruins"), ("ruina", "ruins"), ("zgliszcza", "ruins"),
        ("jaskinia", "cave"), ("grota", "cave"),
        ("dungeon", "dungeon"), ("loch", "dungeon"), ("podziemia", "dungeon"),
        ("gory", "mountains"), ("szczyt", "mountains"),
        ("bagno", "swamp"), ("trzesawisko", "swamp"),
        ("droga", "road"), ("trakt", "road"),
    ]:
        if word in n:
            return htype
    return "plains"


# Stage 2B-Schema S17: subtype keywords used to match canonical game_locations
_SUBTYPE_KEYWORDS: dict[str, list[str]] = {
    "tavern":  ["karczma", "tawerna", "tavern", "inn", "gospoda"],
    "city":    ["miasto", "city", "town"],
    "village": ["wioska", "wies", "village", "osada"],
    "castle":  ["zamek", "castle", "twierdza", "fort"],
    "cave":    ["jaskinia", "grota", "cave"],
    "dungeon": ["loch", "lochy", "dungeon", "podziemia"],
    "forest":  ["las", "forest", "puszcza"],
    "camp":    ["oboz", "camp"],
    "ruins":   ["ruiny", "ruins", "ruina"],
    "port":    ["port", "przystan", "harbor"],
}


def _find_canonical_location_for_name(
    name: str,
    conn: sqlite3.Connection,
) -> sqlite3.Row | None:
    """
    Find a canonical game_location matching `name` by:
    1. Label similarity ≥ 0.4
    2. Subtype keyword match (Polish / English terms)
    Returns the best matching row or None.
    """
    if not name or not name.strip():
        return None

    rows = conn.execute(
        "SELECT id, key, label, location_subtype, biome "
        "FROM game_locations WHERE canonical = 1 AND is_active = 1"
    ).fetchall()
    if not rows:
        return None

    # Pass 1 — label similarity
    best_score, best_row = 0.0, None
    for row in rows:
        score = _label_similarity(name, row["label"] or "")
        if score > best_score:
            best_score = score
            best_row = row
    if best_score >= 0.4:
        return best_row

    # Pass 2 — subtype keyword in name
    norm = _normalize(name)
    for subtype, keywords in _SUBTYPE_KEYWORDS.items():
        if any(kw in norm for kw in keywords):
            for row in rows:
                if (row["location_subtype"] or "").lower() == subtype:
                    return row

    return None


def _find_nearby_empty_hex(
    conn: sqlite3.Connection,
    max_distance: int = 4,
    avoid: set | None = None,
) -> tuple[int, int]:
    """
    Find an empty hex coordinate near the existing world (within max_distance).
    Returns (q, r) that is not yet in world_hexes.
    """
    rows = conn.execute(
        "SELECT q, r FROM world_hexes WHERE is_active = 1 AND map_level = 0"
    ).fetchall()
    if not rows:
        return (0, 0)

    occupied = {(int(r["q"]), int(r["r"])) for r in rows}
    if avoid:
        occupied |= avoid

    # Try candidates adjacent to existing hexes at increasing distance
    for dist in range(1, max_distance + 1):
        candidates = set()
        for (q, r) in occupied:
            for dq, dr in _DIRECTIONS:
                nb = (q + dist * dq, r + dist * dr)
                if nb not in occupied:
                    candidates.add(nb)
        if candidates:
            return random.choice(list(candidates))

    # Fallback: just use (0,0) or (-max_distance, 0)
    for q in range(-max_distance, max_distance + 1):
        for r in range(-max_distance, max_distance + 1):
            if (q, r) not in occupied:
                return (q, r)
    return (0, 0)


def _find_character_existing_hex(
    conn: sqlite3.Connection,
    new_campaign_id: int,
    user_id: int,
) -> "tuple[int, int] | None":
    """C18: Return (q, r) of a previously discovered hex for this user, or None.

    #992-ii: only reuse a hex that is a valid OVERWORLD travel node (world_hexes
    map_level=0, active). Past runs polluted campaign_hex_data with map_level=1 local
    coords (e.g. (1,0)); reusing one stranded the player off the travel graph so every
    directional MOVE refused "nieznane terytorium". The JOIN filters those out.
    """
    row = conn.execute(
        """SELECT chd.hex_q, chd.hex_r
           FROM campaign_hex_data chd
           JOIN campaigns c ON c.id = chd.campaign_id
           JOIN world_hexes wh
                ON wh.q = chd.hex_q AND wh.r = chd.hex_r
               AND wh.map_level = 0 AND wh.is_active = 1
           WHERE c.owner_user_id = ? AND c.id != ? AND chd.discovered = 1
           ORDER BY chd.id DESC
           LIMIT 1""",
        (user_id, new_campaign_id),
    ).fetchone()
    if row:
        return (int(row["hex_q"]), int(row["hex_r"]))
    return None


def _find_location_on_hex(conn: sqlite3.Connection, q: int, r: int) -> str | None:
    """#992: return the key of the game_location physically placed on hex (q, r).

    Resolution order:
      1. The canonical world_hexes.location_key for the overworld (map_level=0) hex —
         the authoritative hex→location pairing (game_locations.world_hex_q/r can be
         stale, e.g. brzezino stamped (1,0) while world_hexes maps it at (39,9)).
      2. Fallback: a game_location stamped with this hex via world_hex_q/r, preferring
         a top-level macro/settlement over a child sub-location.
    Returns None when no active location is mapped to the hex.
    """
    # 1. Canonical world_hexes pairing.
    try:
        wh = conn.execute(
            "SELECT location_key FROM world_hexes "
            "WHERE q = ? AND r = ? AND map_level = 0 AND is_active = 1 "
            "AND location_key IS NOT NULL AND location_key != '' LIMIT 1",
            (q, r),
        ).fetchone()
    except sqlite3.OperationalError:
        wh = None
    if wh:
        wh_key = wh["location_key"] if isinstance(wh, sqlite3.Row) else wh[0]
        loc = conn.execute(
            "SELECT key FROM game_locations WHERE key = ? AND COALESCE(is_active, 1) = 1 LIMIT 1",
            (wh_key,),
        ).fetchone()
        if loc:
            return loc["key"] if isinstance(loc, sqlite3.Row) else loc[0]

    # 2. Fallback: game_location stamped with this hex.
    try:
        row = conn.execute(
            "SELECT key FROM game_locations "
            "WHERE world_hex_q = ? AND world_hex_r = ? AND COALESCE(is_active, 1) = 1 "
            "ORDER BY (location_type = 'macro') DESC, (parent_key IS NULL) DESC, id "
            "LIMIT 1",
            (q, r),
        ).fetchone()
    except sqlite3.OperationalError:
        return None
    if not row:
        return None
    return row["key"] if isinstance(row, sqlite3.Row) else row[0]


def resolve_starting_hex(
    campaign_id: int,
    character_id: int,
    starting_location_name: str | None,
    conn: sqlite3.Connection,
) -> dict:
    """
    Find or create the starting hex for a new campaign character.

    Priority:
    1. Match starting_location_name to an existing global hex by label similarity
    2. No match → create new hex near existing world (within 3-5 hexes)
    3. No world at all → create default town at (0,0)

    Always adds a campaign_hex_data row (discovered=1) and updates session_flags.
    Returns the hex dict {q, r, hex_type, label, is_new}.
    """
    import json as _json

    # When no starting location is given (or sentinel "Start" from reset-progress),
    # pick one randomly (50% settlement, 50% wilderness) to avoid always-wilderness starts.
    _is_sentinel = (
        not starting_location_name
        or not starting_location_name.strip()
        or starting_location_name.strip().lower() == "start"
        or (starting_location_name.strip().lower().startswith("start ") and
            starting_location_name.strip()[6:].isdigit())
    )
    if _is_sentinel:
        starting_location_name = _pick_random_start_location(conn) or None

    # Try to match existing hex by label
    matched_hex = None
    if starting_location_name and starting_location_name.strip():
        # #992-ii: ONLY overworld hexes (map_level=0) are valid start/travel nodes.
        # Without this filter the label match could resolve to a map_level=1 LOCAL
        # sub-map hex (FAZA ML) — e.g. "Wolanka: Kościół" at (1,0) — placing the
        # player on coords absent from the travel graph (_load_hex_graph loads only
        # map_level=0), so every directional MOVE refused "nieznane terytorium".
        rows = conn.execute(
            "SELECT q, r, hex_type, label FROM world_hexes "
            "WHERE is_active = 1 AND map_level = 0 AND label IS NOT NULL"
        ).fetchall()
        best_score, best_row = 0.0, None
        for row in rows:
            score = _label_similarity(starting_location_name, row["label"] or "")
            if score > best_score:
                best_score = score
                best_row = row
        if best_score >= 0.4:
            matched_hex = dict(best_row)

    is_new = False
    if matched_hex:
        sq, sr = int(matched_hex["q"]), int(matched_hex["r"])
        hex_type = matched_hex["hex_type"]
        label = matched_hex["label"]
    else:
        # C18: prefer an already-discovered hex from same user's previous campaigns
        owner_row = conn.execute(
            "SELECT owner_user_id FROM campaigns WHERE id = ?", (campaign_id,)
        ).fetchone()
        owner_user_id = int(owner_row["owner_user_id"]) if owner_row else None
        reuse_coords = (
            _find_character_existing_hex(conn, campaign_id, owner_user_id)
            if owner_user_id else None
        )

        if reuse_coords:
            sq, sr = reuse_coords
            wh = conn.execute(
                "SELECT hex_type, label FROM world_hexes "
                "WHERE q = ? AND r = ? AND map_level = 0 AND is_active = 1",
                (sq, sr),
            ).fetchone()
            hex_type = wh["hex_type"] if wh else "plains"
            label = wh["label"] if wh else None
            is_new = False
        else:
            # Fallback: (0,0) — fresh start, no prior history
            sq, sr = 0, 0
            hex_type = _infer_hex_type_from_name(starting_location_name or "")
            label = None
            is_new = True
            conn.execute(
                """INSERT OR IGNORE INTO world_hexes
                   (q, r, hex_type, label, encounter_chance, encounter_pool,
                    created_by_gm, created_by_campaign_id, discovered_in_campaign_id)
                   VALUES (?,?,?,?,?,?,0,?,?)""",
                (sq, sr, hex_type, label, 0.15 if hex_type not in ("town", "castle") else 0.0,
                 "[]", campaign_id, campaign_id),
            )

    # Campaign-specific overlay: store the specific location name as campaign_label
    campaign_label = starting_location_name if is_new or starting_location_name else None
    conn.execute(
        """INSERT INTO campaign_hex_data
           (campaign_id, hex_q, hex_r, campaign_label, discovered)
           VALUES (?,?,?,?,1)
           ON CONFLICT(campaign_id, hex_q, hex_r) DO UPDATE SET
             discovered = 1,
             campaign_label = COALESCE(excluded.campaign_label, campaign_label)""",
        (campaign_id, sq, sr, campaign_label),
    )

    # Update session_flags with current_hex
    gs = conn.execute(
        "SELECT id, session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
        (campaign_id,),
    ).fetchone()
    if gs:
        flags = _json.loads(gs["session_flags"] or "{}")
        flags["current_hex"] = {"q": sq, "r": sr}
        conn.execute(
            "UPDATE game_sessions SET session_flags = ? WHERE id = ?",
            (_json.dumps(flags, ensure_ascii=False), gs["id"]),
        )

    # Stage 2B-Schema S17: pair the hex with a canonical game_location (or create minimal one)
    loc_key: str | None = None

    # #992: a game_location physically sitting on this hex (world_hex_q/r) is the
    # ONLY correct anchor. For an already-existing matched hex the old code skipped
    # straight to name-matching and then a RANDOM canonical fallback, anchoring the
    # session at an unrelated location while current_hex pointed elsewhere — the
    # location↔hex rozjazd that broke rest (safe_for_rest read off the wrong loc)
    # and fed wrong location context to the narrator. Prefer the on-hex location.
    if not is_new:
        on_hex_key = _find_location_on_hex(conn, sq, sr)
        if on_hex_key:
            loc_key = on_hex_key
            logger.info(
                "s17_hex_location_paired",
                campaign_id=campaign_id, loc_key=loc_key, q=sq, r=sr,
            )

    # U28: try placement engine first (for new hexes only — existing hexes keep their location)
    if not loc_key and is_new:
        try:
            from app.services.placement_engine import try_place_location_on_hex
            placed_key = try_place_location_on_hex(conn, sq, sr, hex_type, campaign_seed=campaign_id)
            if placed_key:
                loc_key = placed_key
                logger.info(
                    "u28_placement_engine_placed",
                    campaign_id=campaign_id,
                    loc_key=loc_key,
                    hex_type=hex_type,
                    q=sq, r=sr,
                )
        except Exception as _pe:
            logger.warning("u28_placement_engine_error", error=str(_pe))

    if not loc_key:
        canonical_loc = _find_canonical_location_for_name(starting_location_name or "", conn)
        if canonical_loc:
            loc_key = canonical_loc["key"]
            logger.info(
                "s17_canonical_location_matched",
                campaign_id=campaign_id,
                loc_key=loc_key,
                starting_name=starting_location_name,
            )
        else:
            # Fallback: pick any permanent canonical location rather than creating
            # a meaningless "Start {campaign_id}" placeholder that pollutes the location table.
            fallback_row = conn.execute(
                """SELECT key, label FROM game_locations
                   WHERE canonical=1 AND is_active=1 AND review_status='permanent'
                   ORDER BY RANDOM() LIMIT 1"""
            ).fetchone()
            if fallback_row:
                loc_key = fallback_row["key"]
                logger.info(
                    "s17_canonical_location_fallback",
                    campaign_id=campaign_id,
                    loc_key=loc_key,
                    starting_name=starting_location_name,
                )
            else:
                # World has no canonical locations at all — create one-time placeholder.
                loc_key = f"start_{campaign_id}"
                conn.execute(
                    """INSERT OR IGNORE INTO game_locations
                       (key, label, safe_for_rest, canonical, created_by, is_active,
                        approved, review_status, ai_generated, source_campaign_id)
                       VALUES (?,?,1,0,'gm_runtime',1,1,'approved',0,?)""",
                    (loc_key, starting_location_name or f"Start {campaign_id}", campaign_id),
                )
            logger.info(
                "s17_start_location_created",
                campaign_id=campaign_id,
                loc_key=loc_key,
                starting_name=starting_location_name,
            )

    if is_new:
        conn.execute(
            "UPDATE world_hexes SET location_key = ? WHERE q = ? AND r = ?",
            (loc_key, sq, sr),
        )

    # Also anchor the session at the resolved location so context injection works from turn 1
    if gs:
        loc_row = conn.execute(
            "SELECT id FROM game_locations WHERE key = ? AND is_active = 1", (loc_key,)
        ).fetchone()
        if loc_row and not conn.execute(
            "SELECT current_location_id FROM game_sessions "
            "WHERE campaign_id = ? AND current_location_id IS NOT NULL",
            (campaign_id,),
        ).fetchone():
            conn.execute(
                "UPDATE game_sessions SET current_location_id = ? WHERE campaign_id = ?",
                (loc_row["id"], campaign_id),
            )

    conn.commit()

    return {"q": sq, "r": sr, "hex_type": hex_type, "label": label or starting_location_name, "is_new": is_new}
