"""
Hex Travel Service — Task 40.
A* pathfinding on world_hexes grid + hex_teleport_connections.
Chain travel: resolve full journey, roll encounters per hex, interrupt on trigger.
"""
from __future__ import annotations

import heapq
import json
import random
import re
import sqlite3
from typing import Any, Optional

import structlog

from app.services.movement_service import (
    MovementProfile,
    MovementStep,
    run_step_sequence,
)

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

def _load_live_regions(conn: sqlite3.Connection) -> set[str]:
    """Return set of region keys that are 'live' (passable).

    Falls back to {'kresy'} if the world_regions table is absent (pre-RM1 DB
    or a test fixture without it) — keeps pathfinding working on legacy schemas.
    """
    try:
        rows = conn.execute(
            "SELECT key FROM world_regions WHERE status = 'live'"
        ).fetchall()
    except sqlite3.OperationalError:
        return {"kresy"}
    if not rows:
        return {"kresy"}
    return {r["key"] for r in rows}


def _load_hex_graph(conn: sqlite3.Connection) -> dict[tuple[int, int], dict]:
    """
    Load world_hexes and hex_teleport_connections into an adjacency-aware dict.
    Only hexes in 'live' regions are included — coming/locked regions are impassable.
    PT8 #1118: hex types with is_passable=0 (water, sea) are excluded from the graph.
    Returns: {(q, r): {hex_data + 'teleport_edges': [...]}}
    """
    live_regions = _load_live_regions(conn)

    # PT8: load passable hex types; None = fallback (pre-PT8 schema — allow all)
    passable_types: set[str] | None = None
    try:
        pt_rows = conn.execute(
            "SELECT hex_type FROM hex_type_config WHERE is_passable = 1 AND is_active = 1"
        ).fetchall()
        passable_types = {r["hex_type"] for r in pt_rows}
    except Exception:
        pass

    hexes: dict[tuple[int, int], dict] = {}
    rows = conn.execute(
        "SELECT q, r, hex_type, label, encounter_chance, encounter_pool, location_key, region "
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
        region = h.get("region") or "kresy"
        hex_type = h.get("hex_type", "plains")
        if region in live_regions and (passable_types is None or hex_type in passable_types):
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
    hex_type_cfg: dict[str, dict] | None = None,
) -> list[tuple[int, int]] | None:
    """
    A* from start to goal on hex grid + teleport connections.
    PT8 #1118: step cost = travel_hours from hex_type_cfg (fallback 1.0 when cfg absent).
    Heuristic = hex_distance × 0.5 (admissible: min terrain cost = road 0.5h/hex).
    Returns ordered list of (q, r) including start and goal, or None if unreachable.
    """
    _MIN_TERRAIN_COST = 0.5  # road — keeps heuristic admissible

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
            # PT8: terrain cost from hex_type_cfg; fallback 1.0 when cfg absent
            nb_type = hexes[neighbor].get("hex_type", "plains")
            step_cost = float((hex_type_cfg or {}).get(nb_type, {}).get("travel_hours", 1.0)) or 1.0
            tentative_g = g_score[current] + step_cost
            if tentative_g < g_score.get(neighbor, float("inf")):
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g
                # PT8: admissible heuristic = dist × min_terrain_cost (road 0.5h/hex)
                f = tentative_g + hex_distance(nq, nr, *goal) * _MIN_TERRAIN_COST
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
                f = tentative_g + hex_distance(*dest, *goal) * _MIN_TERRAIN_COST
                heapq.heappush(open_set, (f, dest))

    return None  # No path found


# ── Encounter resolution ──────────────────────────────────────────────────────

# PT7 #1117: Daily march budget — Numbers Policy (Sandbox-tunable starting values)
DAILY_SOFT_CAP = 8.0        # hours — dusk prompt threshold
DAILY_HARD_CAP = 12.0       # hours — forced camp threshold
NIGHT_ENCOUNTER_MULT = 1.5  # encounter chance multiplier when night_march=True


def _roll_encounter(hex_data: dict, hex_type_cfg: dict[str, dict]) -> bool:
    """Roll encounter for a hex. Returns True if encounter triggers."""
    base_chance = float(hex_data.get("encounter_chance") or 0.15)
    # Adjust by hex type if configured
    ht = hex_data.get("hex_type", "plains")
    type_chance = float(hex_type_cfg.get(ht, {}).get("encounter_base_chance") or base_chance)
    final_chance = max(base_chance, type_chance)
    return random.random() < final_chance


# #1146: hex-level pools are data-authored and mostly empty (the canonical seed
# carries none), so an empty pool falls back to a terrain-typed default instead
# of silently dropping the encounter. Keys must exist in game_config_enemies.
_WORLD_ENCOUNTER_FALLBACK_POOLS: dict[str, list[str]] = {
    "forest": ["wolf", "goblin", "bandit"],
    "mountain": ["goblin", "unknown_attacker"],
    "hills": ["wolf", "bandit"],
    "swamp": ["giant_rat", "unknown_attacker"],
    "road": ["bandit"],
    "bridge": ["bandit"],
    "ruins": ["unknown_attacker", "goblin"],
}
_WORLD_ENCOUNTER_FALLBACK_DEFAULT = ["bandit", "unknown_attacker", "wolf"]


def _pick_encounter_enemy(hex_data: dict) -> str | None:
    pool = hex_data.get("encounter_pool") or []
    if not pool:
        ht = str(hex_data.get("hex_type") or "plains")
        pool = _WORLD_ENCOUNTER_FALLBACK_POOLS.get(ht, _WORLD_ENCOUNTER_FALLBACK_DEFAULT)
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


# ── PT3/#1113: named-destination text resolver ────────────────────────────────

_PT3_MOVE_VERB_RE = re.compile(
    r"\b(id[ęe]|idz|wr[aó]c|wyrusz|podroz|podróż|jad[ęe]|biegn|zmierzam|ruszam|wchodz|pojd|pójd|chodz|idziemy)\w*\b",
    re.IGNORECASE | re.UNICODE,
)
_PT3_DEST_RE = re.compile(
    r"\b(?:do|ku)\s+([A-ZŁÓĄĘŚŹĆŃ][a-ząćęłńóśźżA-ZŁÓĄĘŚŹĆŃ]{2,}"
    r"(?:\s+[A-ZŁÓĄĘŚŹĆŃ][a-ząćęłńóśźżA-ZŁÓĄĘŚŹĆŃ]{2,})*)",
    re.UNICODE,
)


def resolve_player_text_to_location_key(
    player_text: str,
    conn: sqlite3.Connection,
) -> str | None:
    """PT3/#1113: Extract 'idę do <City>' from player text and resolve to a location key.

    Only fires when text contains a movement verb to avoid false positives like
    'mapa do Vilnogradu'. Returns the DB key of the best matching canonical location,
    or None when no match is found.

    Handles Polish inflection via prefix matching: 'Vilnogradu' starts with 'Vilnograd'.
    """
    if not _PT3_MOVE_VERB_RE.search(player_text):
        return None

    m = _PT3_DEST_RE.search(player_text)
    if not m:
        return None
    candidate = m.group(1).strip()
    if not candidate:
        return None

    norm_cand = _normalize(candidate)

    rows = conn.execute(
        "SELECT key, label FROM game_locations WHERE canonical = 1 AND is_active = 1"
    ).fetchall()

    best_score = 0.0
    best_key: str | None = None
    for row in rows:
        norm_label = _normalize(row["label"] or "")
        if not norm_label or len(norm_label) < 3:
            continue
        # Prefix check handles genitive inflection ("vilnogradu" starts with "vilnograd")
        if norm_cand.startswith(norm_label) or norm_label.startswith(norm_cand):
            score = 1.0
        else:
            score = _label_similarity(candidate, row["label"])
        if score > best_score:
            best_score = score
            best_key = row["key"]

    return best_key if best_score >= 0.4 else None


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

    # PT7 #1117: Load daily march budget from session_flags
    _gs_budget = conn.execute(
        "SELECT id, session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
        (campaign_id,),
    ).fetchone()
    _sf_budget = json.loads((_gs_budget["session_flags"] if _gs_budget else None) or "{}")
    hours_marched_today = float(_sf_budget.get("hours_marched_today", 0.0))
    night_march = bool(_sf_budget.get("night_march", False))

    # PT-F3 #1137: reset the daily march budget on a new day (dawn). Without this,
    # hours_marched_today was only ever reset by a long rest — a hero who hit 8h and
    # kept playing without sleeping got an immediate dusk-interrupt on EVERY later
    # trip, crawling 1 hex per command forever. A new in-game day = fresh budget and
    # night_march cleared (morning is no longer a night march).
    try:
        from app.services.clock_service import get_clock_state as _get_clock
        _cur_day = int(_get_clock(campaign_id, conn=conn).get("day", 1))
        _march_day = _sf_budget.get("march_day")
        if _march_day is not None and int(_march_day) != _cur_day:
            hours_marched_today = 0.0
            night_march = False
            _sf_budget["hours_marched_today"] = 0.0
            _sf_budget["night_march"] = False
            _sf_budget["march_day"] = _cur_day
            conn.execute(
                "UPDATE game_sessions SET session_flags = ? WHERE id = ?",
                (json.dumps(_sf_budget, ensure_ascii=False), _gs_budget["id"]),
            )
            conn.commit()
    except Exception as _budget_day_err:
        logger.warning("march_budget_day_reset_failed", error=str(_budget_day_err))

    # PT15 #1128: pogoda spowalnia marsz — mnożnik kosztu godzinowego kroku wg
    # stanu pogody (session_flags.weather.type / weather_override). NIE zmienia
    # trasy A* (tylko czas), więc gorsza pogoda = mniej hexów przed zmierzchem (PT7).
    try:
        from app.services.weather_service import get_march_multiplier
        _weather_mult, _weather_type = get_march_multiplier(campaign_id, conn)
    except Exception:
        _weather_mult, _weather_type = 1.0, None

    if from_hex not in hexes and from_hex != to_hex:
        # Player is not on a hex yet — allow if destination exists
        pass

    if to_hex not in hexes:
        # Check if destination exists in a non-live region (coming/locked)
        blocked_row = conn.execute(
            "SELECT wh.region, wr.status, wr.label FROM world_hexes wh "
            "LEFT JOIN world_regions wr ON wr.key = wh.region "
            "WHERE wh.q = ? AND wh.r = ? AND wh.map_level = 0 AND wh.is_active = 1 LIMIT 1",
            (to_hex[0], to_hex[1]),
        ).fetchone()
        if blocked_row and blocked_row["status"] in ("coming", "locked"):
            region_label = blocked_row["label"] or blocked_row["region"]
            return {
                "ok": False,
                "error": f"Kraina niedostępna — {region_label} jest za zamkniętą granicą.",
                "path": [], "total_hours": 0,
                "arrived_hex": {"q": from_hex[0], "r": from_hex[1]}, "encounter": None, "encounter_hex": None,
                "hex_data": {}, "teleport_used": None, "item_blocked": None,
            }
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

    path = find_path(from_hex, to_hex, hexes, hex_type_cfg)
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

    # PT11 #1121: build the movement step sequence from the A* path, then run it
    # through the shared movement core with the WORLD profile.
    #   cost        = teleport-aware trip time (returned as total_hours),
    #   budget_cost = terrain travel_hours (charged to the daily march budget).
    steps: list[MovementStep] = [
        MovementStep(key=from_hex, cost=0.0, data=hexes.get(from_hex, {}))
    ]
    for _i in range(1, len(path)):
        _prev, _cur = path[_i - 1], path[_i]
        _cur_data = hexes.get(_cur, {})
        _tp_cost: float | None = None
        for edge in hexes.get(_prev, {}).get("teleport_edges", []):
            if edge["_dest"] == _cur:
                _tp_cost = float(edge.get("travel_hours", 8.0))
                if not teleport_used:
                    teleport_used = dict(edge)
                break
        _terrain_cost = float(
            hex_type_cfg.get(_cur_data.get("hex_type", "plains"), {}).get("travel_hours", 1.0)
        ) * _weather_mult  # PT15 #1128: pogoda podnosi koszt godzinowy marszu (teren, nie teleport)
        steps.append(
            MovementStep(
                key=_cur,
                cost=_tp_cost if _tp_cost is not None else _terrain_cost,
                budget_cost=_terrain_cost,  # PT7: budget always terrain cost, even on teleport steps
                data=_cur_data,
                cleared=(_cur in cleared_coords),
            )
        )

    def _world_budget_interrupt(acc: float, step: MovementStep) -> str | None:
        # PT7: hard cap forced_camp (any time), soft cap dusk (unless already night_march)
        if acc >= DAILY_HARD_CAP:
            return "forced_camp"
        if acc >= DAILY_SOFT_CAP and not night_march:
            return "dusk"
        return None

    def _world_roll_risk(step: MovementStep) -> dict | None:
        hex_data = step.data
        # PT7: apply night_march encounter multiplier before rolling
        _enc_hex_data = hex_data
        if night_march:
            _orig_chance = float(hex_data.get("encounter_chance") or 0.15)
            _enc_hex_data = {**hex_data, "encounter_chance": min(1.0, _orig_chance * NIGHT_ENCOUNTER_MULT)}
        if _roll_encounter(_enc_hex_data, hex_type_cfg):
            enemy_key = _pick_encounter_enemy(hex_data)
            if enemy_key:
                return {
                    "enemy_key": enemy_key,
                    "hex_type": hex_data.get("hex_type", "plains"),
                    "hex_label": hex_data.get("label"),
                    "atmosphere": hex_data.get("atmosphere"),
                }
        return None

    _outcome = run_step_sequence(
        steps,
        MovementProfile(
            name="world",
            roll_risk=_world_roll_risk,
            budget_interrupt=_world_budget_interrupt,
        ),
        budget_start=hours_marched_today,
    )

    # Map the shared outcome back onto the world result variables.
    arrived_hex = steps[_outcome.arrived_index].key
    total_hours = _outcome.total_cost
    hours_marched_today = _outcome.budget_total
    encounter_result = _outcome.encounter
    encounter_hex = arrived_hex if _outcome.interrupt_reason == "encounter" else None
    _budget_interrupt = _outcome.interrupt_reason in ("dusk", "forced_camp")
    _budget_reason = _outcome.interrupt_reason if _budget_interrupt else None

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

            # Resolve location_id from key (if any)
            _loc_id: int | None = None
            if _hex_location_key:
                _loc_row = conn.execute(
                    "SELECT id FROM game_locations WHERE key = ? AND COALESCE(is_active,1)=1",
                    (_hex_location_key,),
                ).fetchone()
                if _loc_row:
                    _loc_id = int(_loc_row["id"])
                # HF-11 (#553): visit_location beat auto-complete on mechanical arrival
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

            # #1112: atomic position write via canonical service
            from app.services.location_state_service import set_position
            set_position(
                conn,
                campaign_id=campaign_id,
                current_hex={"q": arrived_hex[0], "r": arrived_hex[1]},
                current_location_id=_loc_id,
                clear_location_id=(not _hex_location_key and arrived_hex != from_hex),
                clear_local_hex=True,
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

    # PT6 #1116 + PT7 #1117: save travel_plan on interrupt; clear on full arrival; persist march budget
    try:
        gs_tp = conn.execute(
            "SELECT id, session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
            (campaign_id,),
        ).fetchone()
        if gs_tp:
            sf_tp = json.loads(gs_tp["session_flags"] or "{}")

            # PT7: Persist updated daily march budget (always, even on full arrival)
            sf_tp["hours_marched_today"] = hours_marched_today
            # PT-F3 #1137: stamp the day this march belongs to so the dawn reset above
            # knows when a new day has begun.
            try:
                from app.services.clock_service import get_clock_state as _gcs_stamp
                sf_tp["march_day"] = int(_gcs_stamp(campaign_id, conn=conn).get("day", 1))
            except Exception:
                pass
            if _budget_reason == "forced_camp":
                sf_tp["night_march"] = True  # flag for PT9 nocturnal attack bonus
                # PT-F3 #1137: a forced collapse in the wild must still arm the PT9
                # night-ambush roll. build_camp set camp_encounter_boost; forced_camp
                # never did, so /rest skipped the roll (boost==0) exactly when the
                # hero is most exposed. Set it here from terrain + the night_march bonus.
                try:
                    _fc_hex = hexes.get(arrived_hex, {})
                    _fc_terrain = _fc_hex.get("hex_type", "plains")
                    _fc_cfg = hex_type_cfg.get(_fc_terrain, {})
                    _fc_base = _fc_cfg.get("camp_encounter_boost")
                    _fc_base = float(_fc_base) if _fc_base is not None else 0.20
                    sf_tp["camp_encounter_boost"] = round(_fc_base + 0.10, 4)
                except Exception as _fc_err:
                    logger.warning("forced_camp_boost_failed", error=str(_fc_err))
                    sf_tp["camp_encounter_boost"] = 0.30

            # PT-D1 (#1124): zmęczenie z podróży (nabija istniejącą kondycję exhausted, max 3).
            # (1) marsz >8h w dniu → +1 (raz na dzień, reset przez pełny nocleg);
            # (2) doba bez pełnego noclegu → +1 gdy marsz przekracza granicę dnia (raz na dobę).
            # Aktywność poza podróżą (walki) NIE nabija stacków w tej iteracji (decyzja Piotra #1124).
            try:
                _stacks = 0
                if hours_marched_today >= DAILY_SOFT_CAP and not sf_tp.get("fatigue_march_charged"):
                    sf_tp["fatigue_march_charged"] = True
                    _stacks += 1
                _ing = float(sf_tp.get("ingame_hours", 9) or 9)
                _day_before = int(_ing // 24) + 1
                _day_after = int((_ing + float(total_hours)) // 24) + 1
                if _day_after > _day_before and int(sf_tp.get("fatigue_last_day_charged", 0) or 0) < _day_after:
                    sf_tp["fatigue_last_day_charged"] = _day_after
                    _stacks += 1
                if _stacks and character_id:
                    from app.services.fatigue_service import charge_fatigue
                    _fat_level = 0
                    for _ in range(_stacks):
                        _fat_level = charge_fatigue(conn, int(character_id), campaign_id=campaign_id, reason="travel_fatigue")
                    logger.info("travel_fatigue_charged", campaign_id=campaign_id, stacks=_stacks, level=_fat_level)
            except Exception as _fat_err:
                logger.warning("fatigue_charge_failed", error=str(_fat_err))

            def _resolve_dest_label() -> tuple[str | None, str]:
                d = hexes.get(to_hex, {})
                lk = d.get("location_key")
                lbl = None
                if lk:
                    _r = conn.execute(
                        "SELECT label FROM game_locations WHERE key = ? LIMIT 1", (lk,)
                    ).fetchone()
                    if _r:
                        lbl = _r["label"]
                if not lbl:
                    lbl = d.get("label") or f"hex ({to_hex[0]},{to_hex[1]})"
                return lk, lbl

            if encounter_result and len(path) > 1:
                dest_loc_key, dest_label = _resolve_dest_label()
                enc_idx = path.index(encounter_hex)
                remaining_hexes = max(0, len(path) - 1 - enc_idx)
                sf_tp["travel_plan"] = {
                    "destination_hex": {"q": to_hex[0], "r": to_hex[1]},
                    "destination_key": dest_loc_key,
                    "destination_label": dest_label,
                    "path": [{"q": h[0], "r": h[1]} for h in path],
                    "step_index": enc_idx,
                    "hours_remaining": float(remaining_hexes),
                    "interrupt_reason": "encounter",
                    # #1146: persist the rolled enemy so the deterministic
                    # [COMBAT_START] injection (turns.py) knows whom to spawn even
                    # when the narrator ignores the encounter fact.
                    "enemy_key": (encounter_result or {}).get("enemy_key"),
                    # PT-F1 #1135: the encounter combat spawns POST-LLM (from the
                    # narrator's [COMBAT_START] tag or the #1146 injection), so on
                    # this very turn no active_combat row exists yet. These fields let
                    # pop_travel_plan_hint defer the continue/rest/camp prompt until
                    # the combat has actually happened and ended (combat_seen), with a
                    # fizzle-guard (wait_turns) for when the narrator never fights.
                    "combat_seen": False,
                    "wait_turns": 0,
                    # PT-F1 #1135: age counter for TTL — a stale plan left in
                    # *_prompted state is dropped after PLAN_TTL_TURNS turns.
                    "age": 0,
                }
            elif _budget_interrupt and _budget_reason:
                # PT7: dusk or forced_camp interrupt
                dest_loc_key, dest_label = _resolve_dest_label()
                b_idx = path.index(arrived_hex)
                remaining_hexes = max(0, len(path) - 1 - b_idx)
                sf_tp["travel_plan"] = {
                    "destination_hex": {"q": to_hex[0], "r": to_hex[1]},
                    "destination_key": dest_loc_key,
                    "destination_label": dest_label,
                    "path": [{"q": h[0], "r": h[1]} for h in path],
                    "step_index": b_idx,
                    "hours_remaining": float(remaining_hexes),
                    "interrupt_reason": _budget_reason,
                    # PT-F1 #1135: TTL age counter (see encounter branch above).
                    "age": 0,
                }
            elif arrived_hex == to_hex:
                sf_tp.pop("travel_plan", None)

            conn.execute(
                "UPDATE game_sessions SET session_flags = ? WHERE id = ?",
                (json.dumps(sf_tp, ensure_ascii=False), gs_tp["id"]),
            )
            conn.commit()
    except Exception as _tp_err:
        logger.warning("travel_plan_update_failed", error=str(_tp_err))

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
        # PT15 #1128: sygnał dla narratora, gdy pogoda spowalniała marsz
        "weather_multiplier": _weather_mult,
        "weather_slowdown": _weather_type,  # typ pogody, tylko gdy mnożnik > 1.0
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


def _template_start_hex(conn: sqlite3.Connection, campaign_id: int) -> "tuple[int, int] | None":
    """#1110 — the start_hex assigned to the campaign's source template in the Kuźnia.

    Returns (q, r) when the campaign was launched from a template that has an explicit
    start_hex_q/r set, else None. Prefers `template_id`, falls back to `source_template_id`
    (create_campaign stamps the latter).
    """
    try:
        crow = conn.execute(
            "SELECT COALESCE(template_id, source_template_id) AS tid FROM campaigns WHERE id = ?",
            (campaign_id,),
        ).fetchone()
    except Exception:
        return None
    tid = crow["tid"] if crow else None
    if not tid:
        return None
    trow = conn.execute(
        "SELECT start_hex_q, start_hex_r FROM campaign_templates WHERE id = ?", (tid,)
    ).fetchone()
    if trow and trow["start_hex_q"] is not None and trow["start_hex_r"] is not None:
        return (int(trow["start_hex_q"]), int(trow["start_hex_r"]))
    return None


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

    # #1110 — an explicit start_hex assigned in the Kuźnia (campaign_templates.start_hex)
    # is authoritative: it wins over label-matching so the campaign starts exactly where
    # the template says. Only used when that hex exists on the overworld; otherwise fall
    # through to the legacy name-match (backward compatible for campaigns without a hex).
    matched_hex = None
    _tpl_hex = _template_start_hex(conn, campaign_id)
    if _tpl_hex:
        _twh = conn.execute(
            "SELECT hex_type, label FROM world_hexes "
            "WHERE q = ? AND r = ? AND map_level = 0 AND is_active = 1",
            (_tpl_hex[0], _tpl_hex[1]),
        ).fetchone()
        if _twh:
            matched_hex = {
                "q": _tpl_hex[0], "r": _tpl_hex[1],
                "hex_type": _twh["hex_type"], "label": _twh["label"],
            }

    # Try to match existing hex by label (fallback when no template hex applied)
    if matched_hex is None and starting_location_name and starting_location_name.strip():
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

    # Check if session exists (needed for downstream loc_id write)
    gs = conn.execute(
        "SELECT id, session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
        (campaign_id,),
    ).fetchone()
    # Note: set_position() called below after loc_key resolved (combines current_hex + loc_id)

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
                   ORDER BY id ASC LIMIT 1"""
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

    # #1112: atomic position write via canonical service (current_hex + loc_id in one tx)
    if gs:
        _start_loc_id: int | None = None
        if loc_key:
            _loc_row = conn.execute(
                "SELECT id FROM game_locations WHERE key = ? AND is_active = 1", (loc_key,)
            ).fetchone()
            # Only anchor if session has no location yet (don't overwrite resumed campaigns)
            if _loc_row and not conn.execute(
                "SELECT current_location_id FROM game_sessions "
                "WHERE campaign_id = ? AND current_location_id IS NOT NULL",
                (campaign_id,),
            ).fetchone():
                _start_loc_id = int(_loc_row["id"])
        from app.services.location_state_service import set_position
        set_position(
            conn,
            campaign_id=campaign_id,
            current_hex={"q": sq, "r": sr},
            current_location_id=_start_loc_id,
        )

    conn.commit()

    return {"q": sq, "r": sr, "hex_type": hex_type, "label": label or starting_location_name, "is_new": is_new}
