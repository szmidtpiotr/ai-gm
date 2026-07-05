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
    route_mode: str = "direct",
) -> list[tuple[int, int]] | None:
    """
    A* from start to goal on hex grid + teleport connections.
    PT8 #1118: step cost = travel_hours from hex_type_cfg (fallback 1.0 when cfg absent).
    Heuristic = hex_distance × 0.5 (admissible: min terrain cost = road 0.5h/hex).
    PM4 #1223: route_mode="road" multiplies `road`-hex step cost by ROAD_COST_MULT,
    steering the optimal path onto (and along) roads when a viable one exists.
    Returns ordered list of (q, r) including start and goal, or None if unreachable.
    """
    _MIN_TERRAIN_COST = 0.5  # road — keeps heuristic admissible
    if route_mode == "road":
        # road cost drops to 0.5×0.75 → shrink the heuristic floor to stay admissible
        _MIN_TERRAIN_COST = 0.5 * ROAD_COST_MULT

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
            if route_mode == "road" and nb_type == "road":
                step_cost *= ROAD_COST_MULT  # PM4: cheaper roads pull the optimal path onto the trakt
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

# PM4 #1223: Route-mode tuning — Numbers Policy (Sandbox-tunable STARTING values).
# route_mode="road" biases A* onto `road` hexes (cheaper per-hex cost) and halves
# the encounter chance while ON a road hex. "direct" = classic shortest terrain path.
ROAD_COST_MULT = 0.75        # road-hex A* step-cost multiplier in route_mode="road"
ROAD_ENCOUNTER_MULT = 0.5    # encounter-chance multiplier on road hexes (road mode)
ROAD_CHOICE_MIN_HEXES = 2    # ask direct/road only when destination is farther than this
ROAD_DETOUR_RADIUS = 3       # a road within this many hexes of the direct path = viable trakt


def _roll_encounter(
    hex_data: dict, hex_type_cfg: dict[str, dict], chance_mult: float = 1.0
) -> bool:
    """Roll encounter for a hex. Returns True if encounter triggers.

    PM4 #1223: ``chance_mult`` scales the final chance (road mode passes
    ROAD_ENCOUNTER_MULT on road hexes to make the trakt safer).
    """
    base_chance = float(hex_data.get("encounter_chance") or 0.15)
    # Adjust by hex type if configured
    ht = hex_data.get("hex_type", "plains")
    type_chance = float(hex_type_cfg.get(ht, {}).get("encounter_base_chance") or base_chance)
    final_chance = max(base_chance, type_chance) * chance_mult
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

    #1243: delegates to the canonical reader. Primary = world_hexes.location_key
    (hex canon); fallback = game_locations.world_hex_q/r derived cache (log-only —
    the #992 fallback, kept one phase to catch residual drift).
    Returns None when neither path resolves.
    """
    from app.services.hex_location_link import resolve_location_to_hex
    return resolve_location_to_hex(conn, location_key)


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

# PM3 #1222: descriptive-travel verbs. Beyond the classic movement verbs we add
# "szukam (drogi)", "kieruję się", "udaję się", "chcę dotrzeć", "próbuję dojść",
# "podążam". These soft verbs (esp. "udaj*" — the "udaję głupiego" idiom, #763)
# are ALWAYS paired with a destination preposition (do/ku/w stronę/w kierunku)
# by the caller, so they never fire on their own → no false move-intent.
_PT3_MOVE_VERB_RE = re.compile(
    r"\b(id[ęe]|idz|wr[aó]c|wyrusz|podroz|podróż|jad[ęe]|biegn|zmierzam|ruszam|wchodz|pojd|pójd|chodz|idziemy|"
    r"szukam|kieruj|udaj|chc[ęe]|prob[uó]j|próbuj|pod[ąa]ż|maszeruj|wychodz)\w*\b",
    re.IGNORECASE | re.UNICODE,
)
_PT3_DEST_RE = re.compile(
    r"\b(?:do|ku)\s+([A-ZŁÓĄĘŚŹĆŃ][a-ząćęłńóśźżA-ZŁÓĄĘŚŹĆŃ]{2,}"
    r"(?:\s+[A-ZŁÓĄĘŚŹĆŃ][a-ząćęłńóśźżA-ZŁÓĄĘŚŹĆŃ]{2,})*)",
    re.UNICODE,
)

# PM3 #1222: destination phrase for the known-hex resolver — lowercase common
# nouns allowed (most, rzeka, wioska, trakt, miasto) and the "w stronę / w
# kierunku" phrasings. Captures 1-4 words after do/ku/w stronę/w kierunku.
_KNOWN_HEX_DEST_RE = re.compile(
    r"(?:\bdo\b|\bku\b|\bw\s+stron[ęe]\b|\bw\s+kierunku\b)\s+"
    r"([a-ząćęłńóśźżA-ZŁÓĄĘŚŹĆŃ]{3,}(?:\s+[a-ząćęłńóśźżA-ZŁÓĄĘŚŹĆŃ]{2,}){0,3})",
    re.UNICODE | re.IGNORECASE,
)

# Sentinel: a destination phrase was present but nothing known matches it — the
# hero should ask around rather than wander off (#1222 point 4, deadlock #1050).
KNOWN_HEX_UNKNOWN = "__KNOWN_HEX_UNKNOWN__"


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


# ── PM3 #1222: known-hex descriptive-travel resolver ──────────────────────────

def _fuzzy_prefix_match(cand: str, target: str) -> bool:
    """True when two Polish words share enough of a stem to be the same noun.

    Handles declension without a full stemmer: "mostu" ↔ "most", "wioski" ↔
    "wioska", "rzeki" ↔ "rzeka". Prefix either way, else a common-prefix stem of
    at least max(3, 60% of the shorter word).
    """
    a, b = _normalize(cand), _normalize(target)
    if not a or not b:
        return False
    if a.startswith(b) or b.startswith(a):
        return True
    n = 0
    for ca, cb in zip(a, b):
        if ca != cb:
            break
        n += 1
    return n >= max(3, int(0.6 * min(len(a), len(b))))


def resolve_player_text_to_known_hex(
    player_text: str,
    conn: sqlite3.Connection,
    campaign_id: int,
    character_id: int,
) -> "tuple[int, int] | str | None":
    """PM3 #1222: resolve a descriptive travel phrase to a KNOWN/discovered hex.

    Extends the #1113 canonical resolver to lowercase common-noun destinations
    ("szukam drogi do mostu", "udaję się w stronę wioski"). The target is matched
    — with Polish-declension-tolerant prefix matching — against every hex the
    campaign already *knows* (FOW ``known`` ∪ ``discovered``, #1220), by both the
    hex ``label`` and the Polish name of its ``hex_type`` (hex_type_config.label).

    Returns:
      (q, r)               — nearest known hex matching the phrase (≠ current hex),
      KNOWN_HEX_UNKNOWN    — a destination phrase was present but nothing known
                             matches it (caller must NOT move — ask around),
      None                 — no descriptive travel phrase at all (not our case).
    """
    # TODO (#1222 pt.5): LLM fallback for target extraction when the regex/fuzzy
    # path misses a paraphrased destination. turn_intent.py has no target
    # classifier yet — see to_do_ideas.md. No dedicated extra LLM call for now.
    if not _PT3_MOVE_VERB_RE.search(player_text):
        return None
    m = _KNOWN_HEX_DEST_RE.search(player_text)
    if not m:
        return None
    cand_tokens = [t for t in _normalize(m.group(1)).split() if len(t) >= 3]
    if not cand_tokens:
        return None

    try:
        from app.services.fow_service import compute_campaign_known_discovered
        known, discovered, all_hexes = compute_campaign_known_discovered(
            conn, campaign_id, character_id
        )
    except Exception as _fow_err:
        logger.warning("pm3_known_compute_failed", error=str(_fow_err), campaign_id=campaign_id)
        return KNOWN_HEX_UNKNOWN
    visible = known | discovered
    if not visible:
        return KNOWN_HEX_UNKNOWN

    # Polish hex-type labels (hex_type → label), e.g. bridge → "Most", river → "Rzeka".
    htcfg: dict[str, str] = {}
    try:
        for row in conn.execute(
            "SELECT hex_type, label FROM hex_type_config WHERE is_active = 1"
        ).fetchall():
            htcfg[row["hex_type"]] = row["label"] or ""
    except Exception:
        pass

    gs = conn.execute(
        "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
        (campaign_id,),
    ).fetchone()
    cur = json.loads((gs["session_flags"] if gs else None) or "{}").get("current_hex") or {"q": 0, "r": 0}
    cq, cr = int(cur.get("q", 0)), int(cur.get("r", 0))

    matches: list[tuple[int, int]] = []
    for coord in visible:
        row = all_hexes.get(coord)
        if not row:
            continue
        names: list[str] = []
        if row.get("label"):
            names.append(row["label"])
        ht = row.get("hex_type")
        if ht:
            names.append(htcfg.get(ht, ht))  # Polish label
            names.append(ht)                 # english key fallback
        hit = False
        for name in names:
            for nt in _normalize(name).split():
                if any(_fuzzy_prefix_match(ct, nt) for ct in cand_tokens):
                    hit = True
                    break
            if hit:
                break
        if hit:
            matches.append(coord)

    matches = [c for c in matches if c != (cq, cr)]
    if not matches:
        return KNOWN_HEX_UNKNOWN
    matches.sort(key=lambda c: hex_distance(cq, cr, c[0], c[1]))
    return matches[0]


def resolve_declared_move_target(
    player_text: str,
    conn: sqlite3.Connection,
    campaign_id: int,
) -> "tuple[str, str] | None":
    """#1253: resolve a player's *declared* move ("idę/ruszam do X") to a PLACED
    game_location, independently of whether the LLM emitted a location_intent.

    Used as a post-LLM safety net: when the narrator describes a march in prose
    but returns ``location_intent: null``, we still need to know where the hero
    said they were going so the move can be committed mechanically.

    Preference order (also the #1254 rule): sub-locations of the CURRENT hub win
    over anything, then locations physically placed on a hex; floating macros with
    no ``world_hex`` are excluded when a hub sub-location matches.

    Returns ``(location_key, label)`` or None.
    """
    if not _PT3_MOVE_VERB_RE.search(player_text):
        return None
    m = _PT3_DEST_RE.search(player_text) or _KNOWN_HEX_DEST_RE.search(player_text)
    if not m:
        return None
    cand = m.group(1).strip()
    cand_tokens = [t for t in _normalize(cand).split() if len(t) >= 3]
    if not cand_tokens:
        return None

    # Current hub: the settlement the hero is in (parent of current sub-loc, or the
    # current macro itself). Sub-locations of this hub are the strongest match.
    hub_id: int | None = None
    try:
        crow = conn.execute(
            "SELECT gl.id, gl.location_type, gl.parent_id "
            "FROM game_locations gl JOIN game_sessions gs ON gs.current_location_id = gl.id "
            "WHERE gs.campaign_id = ? AND gl.is_active = 1 LIMIT 1",
            (campaign_id,),
        ).fetchone()
        if crow:
            hub_id = int(crow["parent_id"]) if (crow["location_type"] == "sub" and crow["parent_id"]) else int(crow["id"])
    except Exception:
        pass

    rows = conn.execute(
        "SELECT key, label, location_type, parent_id, world_hex_q FROM game_locations "
        "WHERE is_active = 1 AND label IS NOT NULL"
    ).fetchall()

    best: tuple[int, float, str, str] | None = None  # (tier, score, key, label)
    hub_sub_exists = any(
        hub_id is not None and r["parent_id"] == hub_id for r in rows
        if _label_matches_tokens(r["label"], cand_tokens)
    )
    for r in rows:
        if not _label_matches_tokens(r["label"], cand_tokens):
            continue
        is_placed = r["world_hex_q"] is not None
        is_hub_sub = hub_id is not None and r["parent_id"] == hub_id
        is_floating_no_hex = (r["location_type"] == "macro") and not is_placed
        # #1254: inside a settlement, never fall onto a floating macro-without-hex.
        if hub_sub_exists and is_floating_no_hex:
            continue
        tier = 3 if is_hub_sub else (2 if is_placed else 1)
        score = _label_similarity(cand, r["label"])
        cur_best = best
        if cur_best is None or (tier, score) > (cur_best[0], cur_best[1]):
            best = (tier, score, r["key"], r["label"])

    if best is None:
        return None
    return (best[2], best[3])


def _label_matches_tokens(label: str, cand_tokens: list[str]) -> bool:
    """True when any candidate token fuzzy-prefix-matches any label token."""
    if not label:
        return False
    label_tokens = _normalize(label).split()
    return any(
        _fuzzy_prefix_match(ct, lt) for ct in cand_tokens for lt in label_tokens
    )


# ── PM2 (#1221): region gazetteer unlock ──────────────────────────────────────

def _region_of_hex(conn: sqlite3.Connection, q: int, r: int) -> str | None:
    """Overworld region tag of hex (q, r), or None if unplaced/unregioned."""
    row = conn.execute(
        "SELECT region FROM world_hexes WHERE q = ? AND r = ? AND map_level = 0 "
        "AND is_active = 1 LIMIT 1",
        (q, r),
    ).fetchone()
    return (row["region"] if row and row["region"] else None)


def unlock_region_for_hex(
    conn: sqlite3.Connection, campaign_id: int, q: int, r: int
) -> dict[str, str] | None:
    """PM2 (#1221): mark the region containing hex (q, r) as *known* for this
    campaign so its gazetteer (main landmarks/roads/settlements) becomes visible.

    Cumulative: ``session_flags.known_regions`` only ever grows — a region once
    unlocked never disappears (return trip to the old land keeps the new one).

    Returns ``{"key", "label"}`` when this call newly unlocks a region (so the
    caller can fire a narrator hint), else ``None`` (no region, already known, or
    no session row).
    """
    region = _region_of_hex(conn, q, r)
    if not region:
        return None
    gs = conn.execute(
        "SELECT id, session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
        (campaign_id,),
    ).fetchone()
    if not gs:
        return None
    sf = json.loads(gs["session_flags"] or "{}")
    known = sf.get("known_regions")
    if not isinstance(known, list):
        known = []
    if region in known:
        return None
    known.append(region)
    sf["known_regions"] = known
    conn.execute(
        "UPDATE game_sessions SET session_flags = ? WHERE id = ?",
        (json.dumps(sf, ensure_ascii=False), gs["id"]),
    )
    label_row = conn.execute(
        "SELECT label FROM world_regions WHERE key = ? LIMIT 1", (region,)
    ).fetchone()
    label = (label_row["label"] if label_row and label_row["label"] else region)
    logger.info("pm2_region_unlocked", campaign_id=campaign_id, region=region)
    return {"key": region, "label": label}


# ── Main travel resolver ──────────────────────────────────────────────────────

def resolve_chain_travel(
    campaign_id: int,
    character_id: int,
    from_hex: tuple[int, int],
    to_hex: tuple[int, int],
    character_sheet: dict,
    conn: sqlite3.Connection,
    route_mode: str = "direct",
) -> dict[str, Any]:
    """
    Chain travel from from_hex to to_hex.

    PM4 #1223: ``route_mode`` ∈ {"direct","road"}. "road" biases the A* path onto
    roads (ROAD_COST_MULT) and halves encounter chance on road hexes
    (ROAD_ENCOUNTER_MULT). The mode is persisted into ``travel_plan`` so an
    interrupted trip resumes in the same mode (PT6 #1116).

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

    path = find_path(from_hex, to_hex, hexes, hex_type_cfg, route_mode=route_mode)
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
        # PM4 #1223: on a road in road mode the hero moves faster per hex (ROAD_COST_MULT),
        # matching the discounted A* cost so total_hours reflects the trakt's speed.
        if route_mode == "road" and _cur_data.get("hex_type") == "road":
            _terrain_cost *= ROAD_COST_MULT
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
        # PM4 #1223: travelling by road (route_mode="road") halves encounters on road hexes.
        _road_mult = (
            ROAD_ENCOUNTER_MULT
            if route_mode == "road" and hex_data.get("hex_type") == "road"
            else 1.0
        )
        if _roll_encounter(_enc_hex_data, hex_type_cfg, chance_mult=_road_mult):
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
    _region_unlocked: dict[str, str] | None = None
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
                    _prev_location_key = _hex_location_key
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
                    # R7 #1247 leak #3: we already NULLed the hex's location_key
                    # above. If the replacement placement failed, restore the
                    # previous key — otherwise the hero arrives on a hex (and a
                    # session) with no location at all ("przybycie donikąd").
                    if not _hex_location_key:
                        conn.execute(
                            "UPDATE world_hexes SET location_key = ?"
                            " WHERE q = ? AND r = ? AND is_active = 1",
                            (_prev_location_key, _aq, _ar),
                        )
                        _hex_location_key = _prev_location_key

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

        # R6 (#1246): hexy faktycznie przebyte trasą (bez celu, który dostaje
        # discovered wyżej) → status 'known'. Obejmuje kroki wykonane przed
        # przerwaniem podróży (arrived_index < len(steps)-1). Nie degraduje hexów
        # już discovered (walka/nocleg zostają odkryte).
        try:
            _travelled = {
                steps[_i].key for _i in range(0, _outcome.arrived_index + 1)
            } - {arrived_hex}
            for _tq, _tr in _travelled:
                conn.execute(
                    """INSERT INTO campaign_hex_data (campaign_id, hex_q, hex_r, known)
                       VALUES (?,?,?,1)
                       ON CONFLICT(campaign_id, hex_q, hex_r) DO UPDATE SET known = 1""",
                    (campaign_id, _tq, _tr),
                )
        except Exception:
            pass

        # PM2 (#1221): entering a new region unlocks its gazetteer. Runs on every
        # arrival (this is the single choke every travel path funnels through).
        try:
            _region_unlocked = unlock_region_for_hex(
                conn, campaign_id, arrived_hex[0], arrived_hex[1]
            )
        except Exception as _ru_err:
            logger.warning("pm2_region_unlock_failed", error=str(_ru_err))

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
                    # PM4 #1223: resume the trip in the same route mode (direct/road).
                    "route_mode": route_mode,
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
                    # PM4 #1223: resume the trip in the same route mode (direct/road).
                    "route_mode": route_mode,
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
        # PM2 #1221: {"key","label"} gdy ten ruch odblokował nową krainę, else None
        "region_unlocked": _region_unlocked,
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

    #1243: delegates to the canonical reader (hex canon first, derived cache
    fallback with drift logging).
    """
    try:
        from app.services.hex_location_link import location_on_hex
        return location_on_hex(conn, q, r, level=0)
    except sqlite3.OperationalError:
        return None


def _template_start_hex(conn: sqlite3.Connection, campaign_id: int) -> "tuple[int, int, int] | None":
    """#1110 — the start_hex assigned to the campaign's source template in the Kuźnia.

    Returns (q, r, template_id) when the campaign was launched from a template that
    has an explicit start_hex_q/r set, else None. Prefers `template_id`, falls back
    to `source_template_id` (create_campaign stamps the latter).
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
        return (int(trow["start_hex_q"]), int(trow["start_hex_r"]), int(tid))
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
    _tpl_id: "int | None" = None
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
            _tpl_id = _tpl_hex[2]

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

    # #1206/#1212 — template launch: materialize the template's locations (settlement
    # hub + sub-locations with a FAZA ML local map, or the flat start location) and
    # anchor the session at the story's start location instead of raw hex terrain.
    # Runs even when an on-hex location was already paired: for a settlement the
    # on-hex location is the HUB, but the session must start INSIDE the start
    # sub-location (karczma), not "in the village" generically.
    if not is_new and _tpl_id is not None:
        try:
            from app.services.template_start_anchor import ensure_template_locations
            _tsl = ensure_template_locations(conn, _tpl_id, campaign_id=campaign_id)
            if _tsl and int(_tsl["q"]) == sq and int(_tsl["r"]) == sr:
                loc_key = _tsl["key"]
                logger.info(
                    "s17_template_start_location_materialized",
                    campaign_id=campaign_id, loc_key=loc_key, q=sq, r=sr,
                    status=_tsl["status"],
                )
        except Exception as _tsl_err:
            logger.warning("template_start_location_error", error=str(_tsl_err))

    # #1152: for an EXISTING hex with no on-hex location, never anchor the session
    # to a name-matched or first-canonical location — starting_location_name may be
    # a random pick (sentinel) or a label from a different hex, and anchoring to it
    # recreates the location↔hex rozjazd #992 removed (session at "Tundra" while
    # current_hex is a forest on the other side of the map). Leave the location
    # unanchored: the opening scene's location_intent creates and anchors the real
    # start location on this hex.
    if not loc_key and not is_new:
        logger.info(
            "s17_existing_hex_left_unanchored",
            campaign_id=campaign_id,
            q=sq, r=sr,
            starting_name=starting_location_name,
        )

    if not loc_key and is_new:
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

    if is_new and loc_key:
        # #1243: single writer — sets hex canon + refreshes the derived cache.
        from app.services.hex_location_link import link_location_to_hex
        link_location_to_hex(conn, loc_key, sq, sr)

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

        # PM2 (#1221): seed known_regions with the start hex's region so the
        # origin land's gazetteer is unlocked from turn 0 (idempotent — only sets
        # it when absent, never shrinks it on a resumed campaign).
        try:
            _sf_row = conn.execute(
                "SELECT id, session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
                (campaign_id,),
            ).fetchone()
            if _sf_row:
                _sf_kr = json.loads(_sf_row["session_flags"] or "{}")
                if not isinstance(_sf_kr.get("known_regions"), list):
                    _origin = _region_of_hex(conn, sq, sr)
                    _sf_kr["known_regions"] = [_origin] if _origin else []
                    conn.execute(
                        "UPDATE game_sessions SET session_flags = ? WHERE id = ?",
                        (json.dumps(_sf_kr, ensure_ascii=False), _sf_row["id"]),
                    )
        except Exception as _kr_err:
            logger.warning("pm2_known_regions_seed_failed", campaign_id=campaign_id, error=str(_kr_err))

        # #1212 — start inside a settlement sub-location: seed the local-map
        # position (session_flags.local_hex), mirroring #1057's narrative sync.
        if _start_loc_id is not None and loc_key:
            try:
                _sub_row = conn.execute(
                    "SELECT location_type, parent_key FROM game_locations WHERE id = ?",
                    (_start_loc_id,),
                ).fetchone()
                if _sub_row and (_sub_row["location_type"] or "") == "sub" and _sub_row["parent_key"]:
                    from app.services.local_hex_service import (
                        get_local_hex_for_subloc, auto_assign_local_hex,
                    )
                    _lh = get_local_hex_for_subloc(conn, loc_key) or auto_assign_local_hex(
                        conn, loc_key, _sub_row["parent_key"], campaign_id=campaign_id
                    )
                    if _lh:
                        set_position(
                            conn,
                            campaign_id=campaign_id,
                            local_hex={
                                "hex_id": _lh["id"], "q": _lh["q"], "r": _lh["r"],
                                "location_key": _lh.get("location_key"),
                            },
                        )
            except Exception as _lh_err:
                logger.warning("start_local_hex_error", campaign_id=campaign_id, error=str(_lh_err))

        # #1212 — spawning at the start location IS visiting it: close the act-1
        # visit_location beat that targets it (przybycie_do_karczmy class).
        if _start_loc_id is not None and loc_key:
            try:
                from app.services.campaign_plan_runtime import auto_complete_beats_by_event
                auto_complete_beats_by_event(campaign_id, "visit_location", loc_key, 1, conn)
            except Exception as _bt_err:
                logger.warning("start_visit_beat_error", campaign_id=campaign_id, error=str(_bt_err))

    # #1208 — plan-declared starting hour (evening tavern scene ≠ 09:00). Runs once
    # here because every campaign-start flow passes through resolve_starting_hex;
    # init_clock_from_plan itself refuses to touch an already-running clock.
    try:
        from app.services.clock_service import init_clock_from_plan
        _sh = init_clock_from_plan(campaign_id, conn=conn)
        if _sh is not None:
            logger.info("clock_start_hour_applied", campaign_id=campaign_id, start_hour=_sh)
    except Exception as _clk_err:
        logger.warning("clock_start_hour_error", campaign_id=campaign_id, error=str(_clk_err))

    conn.commit()

    return {"q": sq, "r": sr, "hex_type": hex_type, "label": label or starting_location_name, "is_new": is_new}


# ── #1244 (R4): single travel executor shared by every travel endpoint ────────


def open_conn() -> sqlite3.Connection:
    """Canonical sqlite opener for the travel endpoints (#1244 item 3).

    All three travel routes now open/commit the DB the same way — this helper +
    `execute_travel` (which owns every commit) so there is one open/commit path.
    Caller owns closing the connection (wrap in try/finally).
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _record_travel_turn(
    conn: sqlite3.Connection, campaign_id: int, character_id: int, result: dict
) -> None:
    """Insert a synthetic narrative turn for a completed map move.

    Without this the LLM conversation history has no trace of the move and the
    narrator keeps describing the previous location/terrain. Extracted verbatim
    from the old /travel endpoint so every travel route now records it (#1244).
    """
    _hd = result.get("hex_data") or {}
    _terrain = _hd.get("hex_type") or "nieznany"
    _tcfg = conn.execute(
        "SELECT label FROM hex_type_config WHERE hex_type = ?", (_terrain,)
    ).fetchone()
    _terrain_pl = (_tcfg["label"] if _tcfg else None) or _terrain
    _place = _hd.get("label") or ""
    _hours = result.get("total_hours") or 0
    _narr = f"Podróżujesz przez świat i docierasz do nowego miejsca. Teren: {_terrain_pl}."
    if _place:
        _narr += f" Miejsce: {_place}."
    if _hours:
        _narr += f" Droga zajęła {_hours} h."
    _tn_row = conn.execute(
        "SELECT COALESCE(MAX(turn_number),0)+1 AS n FROM campaign_turns WHERE campaign_id = ?",
        (campaign_id,),
    ).fetchone()
    conn.execute(
        "INSERT INTO campaign_turns (campaign_id, character_id, user_text, route, assistant_text, turn_number) "
        "VALUES (?,?,?,?,?,?)",
        (
            campaign_id, character_id,
            "[Podróż mapą — przemieszczam się na nowy teren]",
            "narrative",
            json.dumps({"narrative": _narr}, ensure_ascii=False),
            int(_tn_row["n"]),
        ),
    )
    conn.commit()


# ── PM4 #1223: route-mode analysis + player choice detection ──────────────────

# Road-choice cue words in the player's answer. "road" → follow the trakt;
# "direct" → cut straight across the wilds.
_ROUTE_ROAD_RE = re.compile(
    r"\b(trakt\w*|drog[aąęio]\w*|gośćc\w*|gościńc\w*|bezpieczn\w*|dłuż\w*|okrężn\w*)\b",
    re.IGNORECASE | re.UNICODE,
)
_ROUTE_DIRECT_RE = re.compile(
    r"\b(prosto|wprost|przełaj|przelaj|na\s+skróty|skrót\w*|skroty|dzicz\w*|"
    r"bezpośredni\w*|bezposredni\w*|krótsz\w*|krotsz\w*|najkrótsz\w*)\b",
    re.IGNORECASE | re.UNICODE,
)


def detect_route_choice(player_text: str) -> str | None:
    """PM4 #1223: classify a player's answer to the direct/road question.

    Returns "road", "direct", or None when the text picks neither (or both,
    which is treated as ambiguous — the caller re-hints once then defaults).
    """
    if not player_text:
        return None
    road = bool(_ROUTE_ROAD_RE.search(player_text))
    direct = bool(_ROUTE_DIRECT_RE.search(player_text))
    if road and not direct:
        return "road"
    if direct and not road:
        return "direct"
    return None


def analyze_route(
    from_hex: tuple[int, int],
    to_hex: tuple[int, int],
    conn: sqlite3.Connection,
) -> dict[str, Any]:
    """PM4 #1223: decide whether the direct/road question is worth asking.

    Returns ``{"dist", "road_alt", "terrain_label"}``:
      * ``dist``          — hex distance from→to,
      * ``road_alt``      — a `road` hex sits within ROAD_DETOUR_RADIUS of the
                            direct A* path (a viable trakt exists),
      * ``terrain_label`` — Polish label of the dominant non-road terrain the
                            direct route crosses (for the question text).
    """
    dist = hex_distance(from_hex[0], from_hex[1], to_hex[0], to_hex[1])
    out = {"dist": dist, "road_alt": False, "terrain_label": "dzicz"}
    try:
        hexes = _load_hex_graph(conn)
        cfg = _load_hex_type_config(conn)
        path = find_path(from_hex, to_hex, hexes, cfg, route_mode="direct")
        if not path or len(path) <= 1:
            return out
        # dominant non-road terrain along the route
        counts: dict[str, int] = {}
        for c in path[1:]:
            ht = hexes.get(c, {}).get("hex_type", "plains")
            if ht != "road":
                counts[ht] = counts.get(ht, 0) + 1
        if counts:
            top = max(counts, key=counts.get)
            out["terrain_label"] = cfg.get(top, {}).get("label") or top
        # is there a road within reach of the direct path?
        road_coords = [c for c, d in hexes.items() if d.get("hex_type") == "road"]
        if road_coords:
            for pc in path:
                if any(
                    hex_distance(pc[0], pc[1], rc[0], rc[1]) <= ROAD_DETOUR_RADIUS
                    for rc in road_coords
                ):
                    out["road_alt"] = True
                    break
    except Exception as _ar_err:  # never break a turn over the offer
        logger.warning("pm4_analyze_route_failed", error=str(_ar_err))
    return out


class TravelError(Exception):
    """Raised by execute_travel; `code` maps to an HTTP status in the wrappers."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def execute_travel(
    conn: sqlite3.Connection,
    campaign_id: int,
    target: dict,
    *,
    actor: int,
    record_turn: bool = True,
    route_mode: str = "direct",
) -> dict[str, Any]:
    """#1244 (R4): the single travel pipeline every endpoint delegates to.

    One canonical sequence so /travel, /hex-travel (player) and the admin
    hex-travel route all produce IDENTICAL state (position, scene, turn row,
    discovered fog):
      1. resolve origin (session_flags.current_hex, else resolve_starting_hex)
      2. resolve destination (target hex OR location_key → hex)
      3. resolve_chain_travel (movement + fog + encounters)
      4. advance in-game clock by hours travelled
      5. dungeon_prompt flag for the destination hex
      6. exit old / enter new location scene
      7. record a synthetic narrative turn (narrator sees the move)

    Args:
      conn: open sqlite connection (caller owns open/close; this fn owns commits).
      campaign_id: campaign.
      target: {"hex": {"q","r"}} OR {"location_key": str}.
      actor: character_id performing the travel.

    Returns the resolve_chain_travel result dict enriched with `clock`,
    `dungeon_prompt` and `scene_loaded`.

    Raises TravelError(code) — code ∈ {character_not_found, no_target,
    location_not_placed}.
    """
    character_id = actor

    char = conn.execute(
        "SELECT sheet_json FROM characters WHERE id = ? AND campaign_id = ?",
        (character_id, campaign_id),
    ).fetchone()
    if char is None:
        raise TravelError("character_not_found", "Character not found")
    sheet = json.loads(char["sheet_json"] or "{}")

    # (2) resolve destination hex
    dest: "tuple[int, int] | None" = None
    _th = target.get("hex")
    _lk = target.get("location_key")
    if _th:
        dest = (int(_th["q"]), int(_th["r"]))
    elif _lk:
        dest = resolve_location_key_to_hex(_lk, conn)
        if dest is None:
            raise TravelError(
                "location_not_placed",
                f"Location '{_lk}' not placed on any hex yet.",
            )
    if dest is None:
        raise TravelError("no_target", "Provide target hex or location_key")
    dest_q, dest_r = dest

    # (1) resolve origin — current_hex if present, else canonical fallback via
    # resolve_starting_hex (consistent across all endpoints — replaces the old
    # (0,0)/dest ad-hoc fallbacks in turns.py).
    gs = conn.execute(
        "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
        (campaign_id,),
    ).fetchone()
    flags = json.loads((gs["session_flags"] if gs else None) or "{}")
    ch = flags.get("current_hex")
    if ch:
        from_hex = (int(ch["q"]), int(ch["r"]))
    else:
        _start = resolve_starting_hex(campaign_id, character_id, None, conn)
        from_hex = (int(_start["q"]), int(_start["r"]))

    # (3) movement + fog + encounters
    result = resolve_chain_travel(
        campaign_id=campaign_id, character_id=character_id,
        from_hex=from_hex, to_hex=(dest_q, dest_r),
        character_sheet=sheet, conn=conn,
        route_mode=route_mode,  # PM4 #1223
    )

    # (4) advance in-game clock by hours travelled
    try:
        from app.services.clock_service import advance_clock as _advance_clock
        travel_hours = float(result.get("total_hours") or 0.0)
        if travel_hours > 0:
            clock_state = _advance_clock(campaign_id, travel_hours, "travel", conn=conn)
            conn.commit()
            result["clock"] = clock_state
    except Exception as _clk_err:  # noqa: BLE001 — log + degrade gracefully
        logger.warning("clock_advance_travel_failed", error=str(_clk_err), campaign_id=campaign_id)

    # (5) dungeon hex flag — check destination (not arrived_hex): travel may fail
    # but the hex is still a dungeon.
    hex_row = conn.execute(
        "SELECT hex_type FROM world_hexes WHERE q=? AND r=? AND is_active=1 LIMIT 1",
        (dest_q, dest_r),
    ).fetchone()
    result["dungeon_prompt"] = bool(hex_row and hex_row["hex_type"] == "dungeon")

    # (6) exit old scene, enter new scene if destination hex has a location
    try:
        from app.services.world_state_service import enter_location_scene, exit_location_scene
        exit_location_scene(campaign_id)
        dest_location_key = (result.get("hex_data") or {}).get("location_key")
        if dest_location_key:
            result["scene_loaded"] = enter_location_scene(campaign_id, dest_location_key)
    except Exception as _scene_err:  # noqa: BLE001
        logger.warning("enter_location_scene_failed", error=str(_scene_err), campaign_id=campaign_id)

    # (7) record the move as a synthetic narrative turn.
    # PM3 #1222: the pre-LLM descriptive-travel path passes record_turn=False —
    # run_narrative_turn records the real (narrated) turn right after, so a synthetic
    # "[Podróż mapą]" row here would duplicate it.
    if result.get("ok") and record_turn:
        try:
            _record_travel_turn(conn, campaign_id, character_id, result)
        except Exception as _trec_err:  # noqa: BLE001
            logger.warning("travel_turn_record_failed", error=str(_trec_err), campaign_id=campaign_id)

    return result
