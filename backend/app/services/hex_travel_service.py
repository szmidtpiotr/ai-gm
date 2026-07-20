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

from app.core.constants import DEFAULT_REGION
from app.core.text_utils import strip_pl_diacritics as _sd  # #1420 — intent bez polskich znakow (hex_travel: diakrytyki, bez phonetic — psul route-integration pm4)
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
        return {DEFAULT_REGION}
    if not rows:
        return {DEFAULT_REGION}
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
        region = h.get("region") or DEFAULT_REGION
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

# #1412 — „porwanie przez nurt": przeprawa przez BRÓD to test Obrony (SIŁA) na rzut.
# Numbers Policy — wartości STARTOWE, tunable. Za każdy przebyty hex 'brod' 1 rzut.
FORD_CROSS_DC = 12            # próg testu (Medium); d20 + SIŁA_mod ≥ DC = czysta przeprawa
FORD_SWEEP_MARGIN = 5        # pudło o ≥5 (albo Nat 1) → porwanie przez nurt
FORD_SWEEP_DAMAGE_DIE = 4    # 1d4 obrażeń przy porwaniu (potłuczenie o kamienie)
FORD_SWEEP_DISTANCE_DIE = 4  # #1417 — nurt niesie 1d4 hexów wzdłuż rzeki i wyrzuca na brzeg

# #1390 — częstotliwość spotkań w podróży (Numbers Policy — Sandbox-tunable STARTING).
# Skumulowana szansa spotkania na CAŁĄ podróż jest capowana: bez tego długa trasa
# przez las/bagno (0.3–0.4/hex) dawała ~76–90% gwarancji walki za każdym razem, bo
# rzut leci PER HEX. Cap ≈ „max 1 walka na wyprawę, długa trasa groźniejsza, ale bez
# pewniaka". Nocny marsz łamie cooldown (świadome ryzyko).
TRIP_ENCOUNTER_CAP = 0.35       # max skumulowana P(spotkanie) na jedną podróż
ENCOUNTER_DAY_COOLDOWN = True   # po walce-zasadzce brak dalszych rzutów tego dnia gry

# PM4 #1223: Route-mode tuning — Numbers Policy (Sandbox-tunable STARTING values).
# route_mode="road" biases A* onto `road` hexes (cheaper per-hex cost) and halves
# the encounter chance while ON a road hex. "direct" = classic shortest terrain path.
ROAD_COST_MULT = 0.75        # road-hex A* step-cost multiplier in route_mode="road"
ROAD_ENCOUNTER_MULT = 0.5    # encounter-chance multiplier on road hexes (road mode)
ROAD_CHOICE_MIN_HEXES = 2    # ask direct/road only when destination is farther than this
ROAD_DETOUR_RADIUS = 3       # a road within this many hexes of the direct path = viable trakt


def _encounter_chance(
    hex_data: dict, hex_type_cfg: dict[str, dict], chance_mult: float = 1.0
) -> float:
    """Finalna P(spotkanie) dla hexa (0..1). Wspólne dla rzutu i sumy trasy (#1390).

    PM4 #1223: ``chance_mult`` skaluje wynik (droga/noc/cap podróży).

    #1128: jawne ``0`` — na hexie (``encounter_chance``) LUB na terenie
    (``encounter_base_chance``, np. town/village/castle) — to świadoma *strefa
    bezpieczna* i zeruje szansę (bez tego seed-blanket wskrzeszałby ~15% w mieście).

    #1390: TEREN = źródło prawdy. ``hex_type_config`` to strojona tabela tierów
    zagrożenia (road 0.05, forest 0.3, swamp 0.4, ruins 0.6, dungeon 1.0). Per-hex
    ``encounter_chance`` to zaszumiony blanket z seeda (0.15/0.2 na WSZYSTKICH
    5000+ hexach) — dawne ``max(hex, teren)`` kasowało bezpieczne tereny (droga
    0.05 → 0.15, 3× groźniej niż w designie). Hex nadpisuje teren TYLKO gdy teren
    nie ma konfiguracji (fallback). Brak obu → 0.15.
    """
    raw_hex = hex_data.get("encounter_chance")
    ht = hex_data.get("hex_type", "plains")
    raw_type = hex_type_cfg.get(ht, {}).get("encounter_base_chance")

    # Explicit 0 anywhere = deliberate safe zone (settlements, authored refuges).
    if raw_hex == 0 or raw_type == 0:
        return 0.0

    if raw_type is not None:
        chance = float(raw_type)
    elif raw_hex is not None:
        chance = float(raw_hex)
    else:
        chance = 0.15
    return max(0.0, chance * chance_mult)


def _roll_encounter(
    hex_data: dict, hex_type_cfg: dict[str, dict], chance_mult: float = 1.0
) -> bool:
    """Roll encounter for a hex. Returns True if encounter triggers."""
    return random.random() < _encounter_chance(hex_data, hex_type_cfg, chance_mult)


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
    _sd(
        r"\b(id[ęe]|idz|wr[aó]c|wyrusz|podroz|podróż|jad[ęe]|biegn|zmierzam|ruszam|wchodz|pojd|pójd|chodz|idziemy|"
        r"szukam|kieruj|udaj|chc[ęe]|prob[uó]j|próbuj|pod[ąa]ż|maszeruj|wychodz)\w*\b"
    ),
    re.IGNORECASE | re.UNICODE,
)
_PT3_DEST_RE = re.compile(
    # #1057: przyimek „na" (idę NA Most na Bystrzycy) + łącznik małą literą w nazwie
    # („Most na Bystrzycy", „Most Czarnej Rzeki") — inaczej łapało tylko „Most".
    r"\b(?:do|ku|na)\s+([A-ZŁÓĄĘŚŹĆŃ][a-ząćęłńóśźżA-ZŁÓĄĘŚŹĆŃ]{2,}"
    r"(?:\s+[a-ząćęłńóśźżA-ZŁÓĄĘŚŹĆŃ]{2,}){0,3})",
    re.UNICODE,
)

# PM3 #1222: destination phrase for the known-hex resolver — lowercase common
# nouns allowed (most, rzeka, wioska, trakt, miasto) and the "w stronę / w
# kierunku" phrasings. Captures 1-4 words after do/ku/w stronę/w kierunku.
_KNOWN_HEX_DEST_RE = re.compile(
    r"(?:\bdo\b|\bku\b|\bna\b|\bw\s+stron[ęe]\b|\bw\s+kierunku\b)\s+"
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
    if not _PT3_MOVE_VERB_RE.search(_sd(player_text)):
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

_VOWELS = frozenset("aeiouąęó")


def _vowel_ext_ok(ext: str) -> bool:
    """True when extension looks like a Polish inflection (short, vowel-start)."""
    return not ext or (len(ext) <= 3 and ext[0] in _VOWELS)


def _fuzzy_prefix_match(cand: str, target: str) -> bool:
    """True when two Polish words share enough of a stem to be the same noun.

    Handles declension without a full stemmer: "mostu" ↔ "most", "wioski" ↔
    "wioska", "rzeki" ↔ "rzeka". Prefix either way, else a common-prefix stem of
    at least max(3, 60% of the shorter word).

    Guard: when one word is a prefix of the other, the extension must begin with
    a vowel (normal inflection like -u/-a/-i/-ą). A consonant-start extension
    indicates a different morpheme (e.g. "karczmarza" starts with "karczma" but
    the extension "rza" is a person-noun suffix, not an inflection of the
    place-noun "karczma"). Same guard applied in the fallthrough common-prefix
    path when the full shorter word is a prefix of the longer word.
    """
    a, b = _normalize(cand), _normalize(target)
    if not a or not b:
        return False
    if a.startswith(b):
        return _vowel_ext_ok(a[len(b):])
    if b.startswith(a):
        return _vowel_ext_ok(b[len(a):])
    n = 0
    for ca, cb in zip(a, b):
        if ca != cb:
            break
        n += 1
    shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
    # When the full shorter word is a common prefix → same vowel-extension guard.
    if n == len(shorter):
        return _vowel_ext_ok(longer[len(shorter):])
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
    if not _PT3_MOVE_VERB_RE.search(_sd(player_text)):
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
    if not _PT3_MOVE_VERB_RE.search(_sd(player_text)):
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
    # #1292: sub-locations are linked to their hub via ``parent_key`` (string), NOT
    # ``parent_id`` — the latter is left NULL when the campaign plan materialises
    # subs, so the old parent_id logic never matched and the #1254 hub-sub boost was
    # dead. That let a player's "idę do kuźni" resolve to a floating orphan macro
    # (e.g. another campaign's "Kuźnia") instead of the plan's "Kuźnia na skraju wsi".
    hub_key: str | None = None
    try:
        crow = conn.execute(
            "SELECT gl.key, gl.location_type, gl.parent_key "
            "FROM game_locations gl JOIN game_sessions gs ON gs.current_location_id = gl.id "
            "WHERE gs.campaign_id = ? AND gl.is_active = 1 LIMIT 1",
            (campaign_id,),
        ).fetchone()
        if crow:
            hub_key = crow["parent_key"] if (crow["location_type"] == "sub" and crow["parent_key"]) else crow["key"]
    except Exception:
        pass

    rows = conn.execute(
        "SELECT key, label, location_type, parent_key, world_hex_q FROM game_locations "
        "WHERE is_active = 1 AND label IS NOT NULL"
    ).fetchall()

    best: tuple[int, float, str, str] | None = None  # (tier, score, key, label)
    hub_sub_exists = any(
        hub_key is not None and r["parent_key"] == hub_key for r in rows
        if _label_matches_tokens(r["label"], cand_tokens)
    )
    for r in rows:
        if not _label_matches_tokens(r["label"], cand_tokens):
            continue
        is_placed = r["world_hex_q"] is not None
        is_hub_sub = hub_key is not None and r["parent_key"] == hub_key
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

    # #1411 — rzeki/woda są poza grafem (is_passable=0). Jeśli bohater STOI na takim
    # heksie (np. stara pozycja sprzed reguły „rzeka=bariera", albo zniesiony most),
    # dołącz jego origin do grafu, by mógł ZEJŚĆ na sąsiedni ląd. Sam hex-woda i tak nie
    # dostaje sąsiadów-wody (te są poza grafem), więc gracz wychodzi, ale nie brnie w głąb.
    if from_hex not in hexes:
        _orow = conn.execute(
            "SELECT q, r, hex_type, label, encounter_chance, encounter_pool, location_key, region "
            "FROM world_hexes WHERE q = ? AND r = ? AND map_level = 0 AND is_active = 1 LIMIT 1",
            (from_hex[0], from_hex[1]),
        ).fetchone()
        if _orow:
            _oh = dict(_orow)
            try:
                _oh["encounter_pool"] = json.loads(_oh.get("encounter_pool") or "[]")
            except Exception:
                _oh["encounter_pool"] = []
            _oh["teleport_edges"] = []
            hexes[from_hex] = _oh

    # #1413 Model C — łódź: jednorazowa przeprawa przez WODĘ. Gdy `session_flags.river_crossing`
    # aktywne (ustawione przez _maybe_boat_shortcut po znalezieniu łodzi), wpuść hexy wodne
    # (river/water/lake) do grafu na TĘ jedną podróż i skonsumuj flagę. Bez flagi woda dalej
    # jest barierą (#1411). Rzeki są żeglowne łodzią, więc dopuszczamy całą sieć wodną na ten ruch.
    try:
        _gs_boat = conn.execute(
            "SELECT id, session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1", (campaign_id,)
        ).fetchone()
        _sf_boat = json.loads(_gs_boat["session_flags"] or "{}") if _gs_boat else {}
        _rc = _sf_boat.get("river_crossing")
        if isinstance(_rc, dict) and _rc.get("available"):
            for _wr in conn.execute(
                "SELECT q, r, hex_type, label, encounter_chance, encounter_pool, location_key, region "
                "FROM world_hexes WHERE is_active = 1 AND map_level = 0 AND hex_type IN ('river','water','lake')"
            ).fetchall():
                _wk = (int(_wr["q"]), int(_wr["r"]))
                if _wk not in hexes:
                    _wh = dict(_wr)
                    try:
                        _wh["encounter_pool"] = json.loads(_wh.get("encounter_pool") or "[]")
                    except Exception:
                        _wh["encounter_pool"] = []
                    _wh["teleport_edges"] = []
                    hexes[_wk] = _wh
            _sf_boat.pop("river_crossing", None)  # jednorazowa
            conn.execute("UPDATE game_sessions SET session_flags = ? WHERE id = ?",
                         (json.dumps(_sf_boat, ensure_ascii=False), _gs_boat["id"]))
            conn.commit()
            logger.info("river_crossing_boat_used", campaign_id=campaign_id)
    except Exception as _rc_err:
        logger.warning("river_crossing_inject_failed", error=str(_rc_err), campaign_id=campaign_id)

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
    _cur_day = 1  # #1390: domyślny dzień gdy zegar niedostępny (używany przez cooldown spotkań)
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
            # #1192 FAZA TW: nowy dzień gry = rozliczenie utrzymania towarzyszy
            # (żołd najemnika / pasza konia). Idempotentne per dzień.
            try:
                from app.services import companion_service as _cmp
                _cmp.run_daily_upkeep(conn, int(character_id), int(_cur_day),
                                      campaign_id=campaign_id)
            except Exception as _up_err:
                logger.warning("companion_upkeep_failed", error=str(_up_err))
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

    # #1193: aktywne wydarzenie regionalne — surowa zima/susza wydłuża marsz
    # (składane z pogodą), rajdy bandytów zagęszczają spotkania na traktach.
    _event_enc_mult = 1.0
    try:
        from app.services import world_event_service as _wes
        from app.services.reputation_service import resolve_region as _resolve_region_ev
        _ev_region = _resolve_region_ev(conn, campaign_id)
        _weather_mult = _weather_mult * _wes.travel_hours_multiplier(conn, _ev_region)
        _event_enc_mult = _wes.encounter_chance_multiplier(conn, _ev_region)
    except Exception:
        pass

    # #1192 FAZA TW: aktywny wierzchowiec przyspiesza marsz (mnożnik wg rangi
    # Jeździectwa, głodny koń bez bonusu) i podnosi dzienny budżet; pies obniża
    # szansę zasadzki. Składane z pogodą/eventami — mnożymy, nie nadpisujemy.
    _companion_cap_bonus = 0.0
    _companion_enc_mult = 1.0
    try:
        from app.services import companion_service as _cmp
        _weather_mult = _weather_mult * _cmp.get_travel_multiplier(conn, character_id)
        _companion_cap_bonus = _cmp.get_daily_cap_bonus(conn, character_id)
        _companion_enc_mult = _cmp.get_encounter_chance_mult(conn, character_id)
    except Exception:
        pass

    if from_hex not in hexes and from_hex != to_hex:
        # Player is not on a hex yet — allow if destination exists
        pass

    if to_hex not in hexes:
        # Check if destination exists in a non-live region (coming/locked).
        # #1039: wspólny helper — payload niesie error_code/region_label, żeby ŻAR
        # pokazał dedykowany modal zamiast po cichu zignorować ok:false.
        from app.services.world_region_service import region_block_for_hex
        _region_block = region_block_for_hex(conn, to_hex[0], to_hex[1])
        if _region_block:
            return {
                "ok": False,
                **_region_block,
                "path": [], "total_hours": 0,
                "arrived_hex": {"q": from_hex[0], "r": from_hex[1]}, "encounter": None, "encounter_hex": None,
                "hex_data": {}, "teleport_used": None, "item_blocked": None,
            }
        # #1411 — hex istnieje, ale jest wodą/rzeką poza grafem: to fizyczna bariera,
        # nie „nieznane terytorium". Jasny komunikat kierujący na most/bród/łódź.
        _wtype_row = conn.execute(
            "SELECT hex_type FROM world_hexes WHERE q = ? AND r = ? AND map_level = 0 AND is_active = 1 LIMIT 1",
            (to_hex[0], to_hex[1]),
        ).fetchone()
        _WATER_TYPES = ("river", "water", "lake", "sea", "ocean")
        if _wtype_row and _wtype_row["hex_type"] in _WATER_TYPES:
            _is_river = _wtype_row["hex_type"] == "river"
            _msg = (
                "Rzeka zagradza drogę — przeprawisz się tylko przez most albo bród. "
                "Możesz też poszukać łodzi w pobliżu."
                if _is_river else
                "Woda zagradza drogę — bez łodzi tędy nie przejdziesz."
            )
            return {
                "ok": False,
                "error": _msg,
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
        if acc >= DAILY_HARD_CAP + _companion_cap_bonus:  # #1192: koń niesie dłużej
            return "forced_camp"
        if acc >= DAILY_SOFT_CAP + _companion_cap_bonus and not night_march:
            return "dusk"
        return None

    # #1390 Fix 2 — cooldown spotkań: po walce-zasadzce nie roluj już tego dnia gry
    # (nocny marsz łamie — świadome ryzyko). last_encounter_day stemplowany niżej.
    _last_enc_day = _sf_budget.get("last_encounter_day")
    _encounter_suppressed = bool(
        ENCOUNTER_DAY_COOLDOWN
        and not night_march
        and _last_enc_day is not None
        and int(_last_enc_day) == int(_cur_day)
    )

    # Mnożnik per-krok (noc × droga) — wspólny dla sumy trasy i rzutu.
    def _step_mult(hex_data: dict) -> float:
        m = 1.0
        if night_march:
            m *= NIGHT_ENCOUNTER_MULT
        if route_mode == "road" and hex_data.get("hex_type") == "road":
            m *= ROAD_ENCOUNTER_MULT
        m *= _event_enc_mult  # #1193: rajdy bandytów zagęszczają spotkania w regionie
        m *= _companion_enc_mult  # #1192: pies gończy ostrzega przed zasadzką
        return m

    # #1390 Fix 3 — cap na CAŁĄ podróż. Rzut leci per hex (stop na 1. trafieniu),
    # więc długa trasa kumulowała szansę do ~pewniaka. Sumujemy efektywne szanse
    # kroków (te, na których naprawdę rolujemy: nie origin, nie cleared) i jeśli
    # suma > CAP, skalujemy każdą szansę tak, by suma ≈ CAP (P(trasy) ≤ CAP, bo
    # 1−∏(1−p) ≤ Σp). Krótka trasa (< CAP) bez zmian.
    _trip_cap_mult = 1.0
    if not _encounter_suppressed:
        _base_sum = sum(
            _encounter_chance(s.data, hex_type_cfg, chance_mult=_step_mult(s.data))
            for s in steps[1:]
            if not s.cleared
        )
        if _base_sum > TRIP_ENCOUNTER_CAP:
            _trip_cap_mult = TRIP_ENCOUNTER_CAP / _base_sum

    def _world_roll_risk(step: MovementStep) -> dict | None:
        if _encounter_suppressed:
            return None
        hex_data = step.data
        _mult = _step_mult(hex_data) * _trip_cap_mult
        if _roll_encounter(hex_data, hex_type_cfg, chance_mult=_mult):
            # #1473 — moneta walka/scena społeczna po TRAFIONYM rzucie ryzyka
            # (lustro local_map: reużywa social_encounter_service, bez duplikacji).
            # Połowa społeczna NIE startuje walki — czysta scena fabularna
            # (handlarz/patrol/uchodźcy), bez enemy_key → nie wpada w bramkę
            # „walka nie odbyta" (#1455). Split 50/50 startowy, Sandbox-tunable.
            try:
                from app.services import social_encounter_service as _ses
                if _ses.classify_encounter_kind(random.random()) == "social":
                    _scene = _ses.build_travel_social_scene(conn=conn)
                    return {
                        "kind": "social",
                        "social_event": _scene.get("social_event"),
                        "subtype": _scene.get("subtype"),
                        "hex_type": hex_data.get("hex_type", "plains"),
                        "hex_label": hex_data.get("label"),
                        "atmosphere": hex_data.get("atmosphere"),
                    }
            except Exception as _soc_err:
                logger.warning("travel_social_split_failed", error=str(_soc_err))
            # BL-A7 (#1423): composer skalowany f(Power) — wataha/herszt zamiast
            # jednego wroga poz. 1-2. Pusto → legacy single-pick (zero regresji).
            try:
                from app.services import encounter_service as _enc_svc
                composed = _enc_svc.compose_travel_encounter(conn, campaign_id, hex_data)
            except Exception as _cmp_err:
                logger.warning("travel_composer_failed", error=str(_cmp_err))
                composed = None
            if composed and composed.get("enemies"):
                _enemies = composed["enemies"]
                _leader = str(_enemies[0].get("enemy_key") or "") or None
                return {
                    "enemy_key": _leader,
                    "enemies": _enemies,
                    "label": composed.get("label"),
                    "composition_pattern": composed.get("composition_pattern"),
                    "threat_budget": composed.get("threat_budget"),
                    "threat_spent": composed.get("threat_spent"),
                    "hex_type": hex_data.get("hex_type", "plains"),
                    "hex_label": hex_data.get("label"),
                    "atmosphere": hex_data.get("atmosphere"),
                }
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

    # #1390 Fix 2 / AUDIT #1455 — the day-cooldown stamp used to fire HERE, the moment
    # an encounter was DRAWN. That let a player dodge the ambush (click a new travel
    # target → encounter discarded) yet still enjoy guaranteed no-encounters for the
    # rest of the day. The stamp now lives in combat_service._persist_combatants_and_maybe_end
    # (victory hook) so the cooldown only applies once the fight is actually resolved.

    # Stage 2B R4: deactivate any temp_camp_* on the hex the player just left.
    if arrived_hex != from_hex:
        try:
            from app.services.world_service import deactivate_temporary_location_on_hex
            deactivate_temporary_location_on_hex(conn, from_hex[0], from_hex[1])
        except Exception as e:
            logger.warning("temp_camp_cleanup_failed", q=from_hex[0], r=from_hex[1], error=str(e))

    # Update character's current hex in session_flags
    _region_unlocked: dict[str, str] | None = None

    # #1381 (Bug 1) — GWARANTOWANY awans pina. Zapis pozycji MUSI nastąpić zanim
    # ruszy kruchy kod enrichmentu lokacji poniżej (SELECT-y game_locations,
    # placement engine): jeśli tamten rzuci wyjątkiem, wpada w `except: pass` i
    # `set_position` w środku bloku zostaje POMINIĘTY → bohater utyka na heksie
    # startowym. Wtedy zwycięstwo znaczy encounter_cleared dla złego heksa, a
    # kolejne `travel-resume` liczy trasę znów od startu → ta sama zasadzka w
    # kółko („Kontynuuj podróż nie działa"). Osobny, commitowany zapis pina tutaj
    # rozłącza awans pozycji od enrichmentu — enrichment dokłada tylko location_id.
    try:
        from app.services.location_state_service import set_position as _set_pos_pin
        _set_pos_pin(
            conn,
            campaign_id=campaign_id,
            current_hex={"q": arrived_hex[0], "r": arrived_hex[1]},
            clear_local_hex=True,
        )
        conn.commit()
    except Exception as _pin_err:
        logger.warning("pin_advance_failed", campaign_id=campaign_id, error=str(_pin_err))

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

            # #1408: keep the returned `hex_data` snapshot in sync with a location
            # placed/replaced JUST-IN-TIME on arrival. `hexes` was loaded at travel
            # start (before this placement), so its arrived-hex row still carries the
            # stale `location_key=None` — and the returned result["hex_data"] is that
            # same snapshot (see final return). Without this, maybe_narrate_arrival
            # sees no location_key and silently skips the LLM arrival scene, so moving
            # onto a freshly-named hex produced only the green travel pill, no prose.
            if _hex_location_key:
                arrived_data["location_key"] = _hex_location_key

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

            # #1057: podróż po świecie = wyjście z wnętrza osady → wyczyść pozycję
            # lokalną (inaczej submapa/local_hex zostawał na starej sub-lokacji).
            sf_tp.pop("local_hex", None)

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

            if encounter_result and encounter_result.get("kind") == "social" and len(path) > 1:
                # #1473 — scena społeczna: przerwa FABULARNA, nie walka. Czysty stan
                # (bez enemy_key / combat_seen) → nie wyzwala bramki #1455 ani
                # wstrzyknięcia [COMBAT_START] (turns.py gate na interrupt_reason=="encounter").
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
                    "interrupt_reason": "social",
                    "route_mode": route_mode,
                    "social_event": encounter_result.get("social_event"),
                    "age": 0,
                }
            elif encounter_result and len(path) > 1:
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
                    # BL-A7 (#1423): pełna GRUPA skomponowanego spotkania (enemies z
                    # count/rank). Injection rozwija ją do [COMBAT_START:k1,k2,…];
                    # enemy_key powyżej = lider (kompatybilność wstecz notice/fizzle).
                    "enemies": (encounter_result or {}).get("enemies"),
                    "encounter_label": (encounter_result or {}).get("label"),
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
                # BL-A7 (#1423): zapisz sygnaturę skomponowanej grupy do pamięci
                # anti-repeat (#1329/#1369), by kolejne zasadzki w podróży nie
                # powtarzały tego samego składu. Mutuje sf_tp — leci w tym samym UPDATE.
                _grp = (encounter_result or {}).get("enemies")
                if _grp:
                    try:
                        from app.services.encounter_service import record_encounter_signature
                        record_encounter_signature(conn, sf_tp, _grp)
                    except Exception as _sig_err:
                        logger.warning("travel_encounter_sig_failed", error=str(_sig_err))
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

    # #1255: resolve position IDEMPOTENTLY. A bare GET of world-map calls this with
    # starting_location_name=None; the old code randomized the start FIRST (sentinel →
    # _pick_random_start_location → label-match to a random hex) and only reused the
    # existing/prior hex much later, so every read teleported the pin and desynced
    # hex↔location (the R3/R5 rozjazd). Priority now, highest first:
    #   1. Existing session current_hex — a placed/resumed campaign never moves.
    #   2. Kuźnia template start_hex (#1110) — authoritative at creation.
    #   3. Explicit starting_location_name label-match.
    #   4. C18 reuse of the owner's prior-campaign hex.
    #   5. Sentinel random pick — ONLY for a truly new character with zero history.
    _is_sentinel = (
        not starting_location_name
        or not starting_location_name.strip()
        or starting_location_name.strip().lower() == "start"
        or (starting_location_name.strip().lower().startswith("start ") and
            starting_location_name.strip()[6:].isdigit())
    )

    matched_hex = None
    _tpl_id: "int | None" = None

    # 1. Existing session position — verbatim reuse (idempotent for resumed campaigns).
    #    This wins over the template/label/random paths so re-resolving never moves a pin.
    _existing_hex = None
    _gs_pos = conn.execute(
        "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
        (campaign_id,),
    ).fetchone()
    if _gs_pos:
        try:
            _ch = _json.loads(_gs_pos["session_flags"] or "{}").get("current_hex")
            if isinstance(_ch, dict) and _ch.get("q") is not None and _ch.get("r") is not None:
                _existing_hex = (int(_ch["q"]), int(_ch["r"]))
        except Exception:
            _existing_hex = None
    if _existing_hex:
        _ewh = conn.execute(
            "SELECT hex_type, label FROM world_hexes "
            "WHERE q = ? AND r = ? AND map_level = 0 AND is_active = 1",
            (_existing_hex[0], _existing_hex[1]),
        ).fetchone()
        if _ewh:
            matched_hex = {
                "q": _existing_hex[0], "r": _existing_hex[1],
                "hex_type": _ewh["hex_type"], "label": _ewh["label"],
            }

    # 2. #1110 — an explicit start_hex assigned in the Kuźnia (campaign_templates.start_hex)
    # is authoritative: it wins over label-matching so the campaign starts exactly where
    # the template says. Only used when that hex exists on the overworld; otherwise fall
    # through to the legacy name-match (backward compatible for campaigns without a hex).
    if matched_hex is None:
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

    # 4-precompute. C18 reuse candidate (owner's prior-campaign hex) — resolved now so it
    # can pre-empt the random sentinel pick below (a returning owner keeps their world).
    _reuse_coords = None
    if matched_hex is None:
        _owner_row = conn.execute(
            "SELECT owner_user_id FROM campaigns WHERE id = ?", (campaign_id,)
        ).fetchone()
        _owner_uid = (
            int(_owner_row["owner_user_id"])
            if _owner_row and _owner_row["owner_user_id"] is not None else None
        )
        if _owner_uid:
            _reuse_coords = _find_character_existing_hex(conn, campaign_id, _owner_uid)

    # 5. Sentinel random pick — ONLY when nothing above resolved a hex AND there is no
    #    prior-campaign hex to reuse. This is the ONLY path that may randomize, and it
    #    fires solely for a brand-new character with zero history.
    if _is_sentinel and matched_hex is None and not _reuse_coords:
        starting_location_name = _pick_random_start_location(conn) or None

    # 3. Try to match existing hex by label (fallback when no anchored/template hex)
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
        # 4. C18: prefer an already-discovered hex from same user's previous campaigns
        #    (precomputed above so it can pre-empt the random sentinel pick).
        reuse_coords = _reuse_coords
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
    _sd(r"\b(trakt\w*|drog[aąęio]\w*|gośćc\w*|gościńc\w*|bezpieczn\w*|dłuż\w*|okrężn\w*)\b"),
    re.IGNORECASE | re.UNICODE,
)
_ROUTE_DIRECT_RE = re.compile(
    _sd(r"\b(prosto|wprost|przełaj|przelaj|na\s+skróty|skrót\w*|skroty|dzicz\w*|"
        r"bezpośredni\w*|bezposredni\w*|krótsz\w*|krotsz\w*|najkrótsz\w*)\b"),
    re.IGNORECASE | re.UNICODE,
)
_ROUTE_CANCEL_RE = re.compile(
    _sd(r"\b(rezygnuj\w*|zostaj\w*|zostan\w*|anuluj\w*|odwołuj\w*|nie\s+podróżuj\w*|"
        r"nie\s+ide\w*|nie\s+idę|nie\s+wyruszam|zostań|zostaję|nie\s+teraz)\b"),
    re.IGNORECASE | re.UNICODE,
)


def detect_route_choice(player_text: str) -> str | None:
    """PM4 #1223: classify a player's answer to the direct/road question.

    Returns "road", "direct", "cancel", or None when the text picks neither
    (or both, which is treated as ambiguous — caller re-hints once then cancels).
    """
    if not player_text:
        return None
    _pt = _sd(player_text)  # #1420 — dopasowanie bez polskich znaków
    if _ROUTE_CANCEL_RE.search(_pt):
        return "cancel"
    road = bool(_ROUTE_ROAD_RE.search(_pt))
    direct = bool(_ROUTE_DIRECT_RE.search(_pt))
    if road and not direct:
        return "road"
    if direct and not road:
        return "direct"
    return None


def estimate_route_hours(
    from_hex: tuple[int, int],
    to_hex: tuple[int, int],
    conn: sqlite3.Connection,
    route_mode: str = "direct",
) -> dict[str, Any]:
    """Realny szacunek podróży = suma `travel_hours` po znalezionej trasie (bez
    ruchu/commitu). Panel podróży pokazywał heurystykę `perHex×dist` (teren CELU),
    która rozjeżdżała się z narracją/zegarem. Zwraca {dist, hours}."""
    dist = hex_distance(from_hex[0], from_hex[1], to_hex[0], to_hex[1])
    out: dict[str, Any] = {"dist": dist, "hours": float(dist) * 4.0}
    try:
        hexes = _load_hex_graph(conn)
        cfg = _load_hex_type_config(conn)
        path = find_path(from_hex, to_hex, hexes, cfg, route_mode=route_mode)
        if not path or len(path) <= 1:
            return out
        total = 0.0
        steps: list[dict[str, Any]] = []
        for c in path[1:]:
            ht = hexes.get(c, {}).get("hex_type", "plains")
            cost = float((cfg or {}).get(ht, {}).get("travel_hours", 1.0)) or 1.0
            total += cost
            # #1405: per-hex koszt budżetu marszu — front liczy „dokąd dojdę dziś".
            steps.append({"q": int(c[0]), "r": int(c[1]), "cost": round(cost, 2)})
        out["hours"] = round(total, 1)
        out["dist"] = len(path) - 1
        # Ścieżka z origin (index 0) — front rysuje podgląd trasy na mapie (#1405).
        out["path"] = [{"q": int(path[0][0]), "r": int(path[0][1])}] + [
            {"q": s["q"], "r": s["r"]} for s in steps
        ]
        out["steps"] = steps
    except Exception as _er:  # never break UI over an estimate
        logger.warning("estimate_route_hours_failed", error=str(_er))
    return out


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


def maybe_narrate_arrival(
    conn: sqlite3.Connection,
    campaign_id: int,
    character_id: int,
    result: dict,
    arrived_full: bool,
) -> None:
    """#1393 — krótka scena LLM po dotarciu do NAZWANEJ lokacji (wieś/miasto/nazwane
    miejsce). Puste hexy dziczy zostają przy samym zielonym pillu podróży. 1–2 zdania.

    Persystuje turę BEZPOŚREDNIO (proza generowana inline) — nie idzie przez pipeline
    tur, więc nie odpali detekcji walki/skilli ani shortcutów. Wołane z map-travel
    (/travel) i z travel-resume; ścieżka opisowa („idę do wsi") narruje sama i tu NIE
    wchodzi (record_turn/ narrate_arrival=False).
    """
    if not arrived_full:
        return
    hd = result.get("hex_data") or {}
    loc_key = hd.get("location_key")
    if not loc_key:
        return  # tylko nazwane lokacje — dzicz zostaje przy zielonym pillu
    if result.get("encounter"):
        return
    # #1408: an unnamed wilderness hex carries no `label`; fall back to the linked
    # location's human label (not its raw key) so the arrival prose reads well.
    label = hd.get("label")
    if not label:
        _lbl_row = conn.execute(
            "SELECT label FROM game_locations WHERE key = ? AND COALESCE(is_active,1)=1 LIMIT 1",
            (loc_key,),
        ).fetchone()
        label = (_lbl_row["label"] if _lbl_row and _lbl_row["label"] else None) or str(loc_key)
    try:
        from app.services.user_llm_settings import get_user_llm_settings_full
        from app.services.llm_service import generate_chat
        from app.services.world_service import process_create_tags, get_current_location_info

        _row = conn.execute(
            "SELECT user_id FROM characters WHERE id = ?", (character_id,)
        ).fetchone()
        _uid = int(_row["user_id"]) if _row and _row["user_id"] is not None else 0
        llm_config = get_user_llm_settings_full(_uid)

        _desc = ""
        try:
            _loc = get_current_location_info(conn, campaign_id) or {}
            _desc = str(_loc.get("description") or hd.get("atmosphere") or "").strip()
        except Exception:
            _desc = str(hd.get("atmosphere") or "").strip()
        _ctx = f"Miejsce: {label}." + (f" Opis miejsca: {_desc[:400]}" if _desc else "")
        _prompt = (
            f"{_ctx}\n\nBohater właśnie dociera tu po podróży. Opisz krótko prozą "
            f"(1–2 zdania) samo przybycie: pierwszy widok i atmosferę miejsca. Klimat "
            f"dark fantasy, po polsku. NIE podawaj liczb ani kości, NIE używaj żadnych "
            f"tagów mechanicznych, NIE wszczynaj walki, NIE wywołuj testów, NIE decyduj "
            f"za gracza."
        )
        prose = (generate_chat(
            messages=[{"role": "user", "content": _prompt}],
            llm_config=llm_config,
            call_type="arrival_narration",
            campaign_id=campaign_id,
        ) or "").strip()
        if not prose:
            return
        try:
            prose, _ = process_create_tags(prose, conn, campaign_id)
        except Exception:
            pass
        _tn = conn.execute(
            "SELECT COALESCE(MAX(turn_number),0)+1 FROM campaign_turns WHERE campaign_id = ?",
            (campaign_id,),
        ).fetchone()[0]
        conn.execute(
            "INSERT INTO campaign_turns (campaign_id, character_id, turn_number, user_text, assistant_text, route, created_at) "
            "VALUES (?,?,?,?,?,?,datetime('now'))",
            (campaign_id, character_id, int(_tn), f"[Przybycie: {label}]",
             json.dumps({"narrative": prose}, ensure_ascii=False), "narrative"),
        )
        conn.commit()
    except Exception as _arr_err:
        logger.warning("arrival_narration_failed", error=str(_arr_err), campaign_id=campaign_id)


def _sweep_along_river(conn: sqlite3.Connection, start: tuple[int, int], distance: int):
    """#1417 — nurt niesie bohatera `distance` hexów wzdłuż rzeki od hexa brodu, po czym
    wyrzuca na LOSOWY przyległy przechodni brzeg. Śledzi linię rzeki (preferuje kontynuację
    kierunku, nie zawraca).

    Zwraca {"bank": (q,r), "river_path": [(q,r)...]} — river_path to hexy RZEKI przez które
    spływasz (bez hexa brodu; kończy na hexie rzeki przy brzegu), bank = losowy przyległy
    ląd. None gdy brak rzeki obok brodu / brak lądu przy rzece (→ fallback bez przeniesienia).
    """
    _WATER = ("river", "water", "lake", "sea", "ocean")

    def _htype(q, r):
        row = conn.execute(
            "SELECT hex_type FROM world_hexes WHERE q=? AND r=? AND map_level=0 AND is_active=1 LIMIT 1",
            (q, r),
        ).fetchone()
        return row["hex_type"] if row else None

    def _river_nb(q, r):
        return [(nq, nr) for (nq, nr) in hex_neighbors(q, r) if _htype(nq, nr) == "river"]

    def _land_nb(q, r):
        out = []
        for (nq, nr) in hex_neighbors(q, r):
            t = _htype(nq, nr)
            if t and t not in _WATER and t != "brod":
                out.append((nq, nr))
        return out

    riv = _river_nb(*start)
    if not riv:
        return None
    prev = start
    cur = random.choice(riv)
    river_path = [cur]
    last_dir = (cur[0] - start[0], cur[1] - start[1])
    for _ in range(max(0, distance - 1)):
        cands = [h for h in _river_nb(*cur) if h != prev]
        if not cands:
            break
        cands.sort(key=lambda h: 0 if (h[0] - cur[0], h[1] - cur[1]) == last_dir else 1)
        nxt = cands[0]
        last_dir = (nxt[0] - cur[0], nxt[1] - cur[1])
        prev, cur = cur, nxt
        river_path.append(nxt)
    # wyrzut na losowy brzeg: od końcowego hexa rzeki cofaj wzdłuż trasy aż znajdziesz ląd
    for i in range(len(river_path) - 1, -1, -1):
        lands = _land_nb(*river_path[i])
        if lands:
            return {"bank": random.choice(lands), "river_path": river_path[:i + 1]}
    return None


def maybe_ford_hazard(
    conn: sqlite3.Connection,
    campaign_id: int,
    character_id: int,
    result: dict,
) -> None:
    """#1412 — „porwanie przez nurt". Za każdy hex `brod` faktycznie przebyty w tej
    podróży: rzut Obrony d20 + SIŁA_mod vs FORD_CROSS_DC. Nat 20 = auto-sukces, Nat 1 =
    auto-porwanie. Porażka → `przemoczony` + strata czasu; porażka o ≥FORD_SWEEP_MARGIN
    lub Nat 1 → porwanie: 1d6 obrażeń. Skutki nakładane na sheet; wynik ląduje w
    result["ford_hazard"] i osobnej turze narracyjnej [Bród] (bez LLM — pokazuje rzut).
    """
    if not result.get("ok"):
        return
    path = result.get("path") or []
    if len(path) < 2:
        return
    coords = [(int(p["q"]), int(p["r"])) for p in path]
    _arr = result.get("arrived_hex") or {}
    try:
        _aidx = coords.index((int(_arr["q"]), int(_arr["r"])))
    except (ValueError, KeyError, TypeError):
        _aidx = len(coords) - 1
    traversed = coords[1:_aidx + 1]  # bez origin
    if not traversed:
        return
    ford_hexes = [
        (q, r) for (q, r) in traversed
        if (conn.execute(
            "SELECT hex_type FROM world_hexes WHERE q=? AND r=? AND map_level=0 AND is_active=1 LIMIT 1",
            (q, r),
        ).fetchone() or {"hex_type": None})["hex_type"] == "brod"
    ]
    if not ford_hexes:
        return
    try:
        _ch = conn.execute("SELECT sheet_json FROM characters WHERE id=?", (character_id,)).fetchone()
        sheet = json.loads(_ch["sheet_json"] or "{}") if _ch else {}
        _str = int((sheet.get("stats") or {}).get("STR", 10) or 10)
        str_mod = (_str - 10) // 2

        events: list[dict] = []
        total_dmg = 0
        swept = False
        wet = False
        swept_hex: tuple[int, int] | None = None
        for (q, r) in ford_hexes:
            d20 = random.randint(1, 20)
            nat1, nat20 = d20 == 1, d20 == 20
            total = d20 + str_mod
            success = (not nat1) and (nat20 or total >= FORD_CROSS_DC)
            ev = {"hex": {"q": q, "r": r}, "d20": d20, "mod": str_mod,
                  "total": total, "dc": FORD_CROSS_DC, "success": success,
                  "nat1": nat1, "nat20": nat20, "damage": 0}
            if not success:
                wet = True
                if nat1 or (FORD_CROSS_DC - total) >= FORD_SWEEP_MARGIN:
                    dmg = random.randint(1, FORD_SWEEP_DAMAGE_DIE)
                    ev["damage"] = dmg
                    total_dmg += dmg
                    swept = True
                    swept_hex = (q, r)
            events.append(ev)

        # skutki: obrażenia + przemoczony
        if total_dmg > 0:
            _hp_row = conn.execute("SELECT sheet_json FROM characters WHERE id=?", (character_id,)).fetchone()
            _sh = json.loads(_hp_row["sheet_json"] or "{}") if _hp_row else {}
            _cur = int(_sh.get("current_hp", _sh.get("max_hp", 0)) or 0)
            _sh["current_hp"] = max(0, _cur - total_dmg)
            conn.execute("UPDATE characters SET sheet_json=? WHERE id=?",
                         (json.dumps(_sh, ensure_ascii=False), character_id))

        # #1417 — PORWANIE: nurt niesie bohatera 1d4 hexów wzdłuż rzeki i wyrzuca na LOSOWY
        # przechodni brzeg → PRZENIESIENIE PINA (bardziej narracyjne niż same obrażenia).
        displaced_to = None
        swept_distance = 0
        sweep_path: list[dict] | None = None
        if swept and swept_hex is not None:
            swept_distance = random.randint(1, FORD_SWEEP_DISTANCE_DIE)
            sweep = _sweep_along_river(conn, swept_hex, swept_distance)
            if sweep is not None:
                bank = sweep["bank"]
                from app.services.location_state_service import set_position
                set_position(conn, campaign_id, current_hex={"q": bank[0], "r": bank[1]},
                             clear_location_id=True, clear_local_hex=True, character_id=character_id)
                conn.execute(
                    "INSERT INTO campaign_hex_data (campaign_id, hex_q, hex_r, discovered) VALUES (?,?,?,1) "
                    "ON CONFLICT(campaign_id, hex_q, hex_r) DO UPDATE SET discovered = 1",
                    (campaign_id, bank[0], bank[1]),
                )
                displaced_to = {"q": bank[0], "r": bank[1]}
                # #1417 — ścieżka SPŁYWU dla animacji na mapie: bród → hexy rzeki → brzeg
                # (front zatrzymuje podróż na brodzie, po kliknięciu animuje spływ tą trasą).
                sweep_path = ([{"q": swept_hex[0], "r": swept_hex[1]}]
                              + [{"q": q, "r": r} for (q, r) in sweep["river_path"]]
                              + [{"q": bank[0], "r": bank[1]}])
                # pin/travel-result kieruj na miejsce wyrzucenia
                result["arrived_hex"] = {"q": bank[0], "r": bank[1]}
                _bt = conn.execute(
                    "SELECT hex_type FROM world_hexes WHERE q=? AND r=? AND map_level=0 AND is_active=1 LIMIT 1",
                    (bank[0], bank[1]),
                ).fetchone()
                result["hex_data"] = {"q": bank[0], "r": bank[1],
                                      "hex_type": (_bt["hex_type"] if _bt else "plains")}
        conn.commit()  # utrwal HP + przeniesienie pina PRZED add_condition (nested conn →
        # inaczej „database is locked" gubił zapis pozycji, klasa #1390).

        if wet:
            try:
                from app.services.combat_service import add_condition_to_character
                add_condition_to_character(conn, character_id, campaign_id, "przemoczony")
                conn.commit()
            except Exception as _cond_err:
                logger.warning("ford_wet_condition_failed", error=str(_cond_err))

        result["ford_hazard"] = {
            "events": events, "damage": total_dmg, "swept": swept, "wet": wet,
            "displaced_to": displaced_to, "swept_distance": swept_distance,
            "swept_hex": ({"q": swept_hex[0], "r": swept_hex[1]} if swept_hex else None),
            "sweep_path": sweep_path,
        }

        # narracja mechaniczna (bez LLM) — proza skutku
        if swept and displaced_to is not None:
            _msg = (f"Rwący nurt zrywa ci grunt spod nóg i porywa cię {swept_distance} "
                    f"{'pole' if swept_distance == 1 else 'pola' if swept_distance < 5 else 'pól'} "
                    f"w dół rzeki (−{total_dmg} HP). Wyrzuca cię wreszcie na brzeg — przemoczonego "
                    f"i posiniaczonego, z dala od miejsca, gdzie wszedłeś do wody.")
        elif swept:
            _msg = (f"Rwący nurt brodu porywa cię i ciska o kamienie (−{total_dmg} HP). "
                    f"Wygrzebujesz się na brzeg przemoczony i posiniaczony.")
        elif wet:
            _msg = ("Nurt szarpie nogami przy przeprawie. Poślizgujesz się i przemakasz "
                    "do suchej nitki, ale docierasz na drugi brzeg.")
        else:
            _msg = ("Brodzisz przez rzekę — zimna woda sięga pasa, lecz trzymasz się mocno "
                    "i przechodzisz suchą stopą na drugi brzeg.")
        # #1416 — rzut jako KARTA w logu: user_text w formacie „[Rzut: … — d20 ±mod = suma
        # vs DC — wynik]" (rollFromRzutLine → karta rzutu, parytet z testami umiejętności).
        # Wcześniej rzut był doklejony do prozy w nawiasie [ ] i cleanProse go WYCINAŁ →
        # gracz nie widział żadnego testu („0 widocznych testów").
        _roll = events[-1]
        _outcome_word = ("naturalny 20" if _roll["nat20"] else "naturalny 1" if _roll["nat1"]
                         else "sukces" if _roll["success"] else "porażka")
        _m = int(_roll["mod"])
        _rzut = (f"[Rzut: Przeprawa (Siła) — {_roll['d20']} {'+' if _m >= 0 else '-'}{abs(_m)} "
                 f"= {_roll['total']} vs {FORD_CROSS_DC} — {_outcome_word}]")
        _tn = conn.execute(
            "SELECT COALESCE(MAX(turn_number),0)+1 FROM campaign_turns WHERE campaign_id = ?",
            (campaign_id,),
        ).fetchone()[0]
        conn.execute(
            "INSERT INTO campaign_turns (campaign_id, character_id, turn_number, user_text, assistant_text, route, created_at) "
            "VALUES (?,?,?,?,?,?,datetime('now'))",
            (campaign_id, character_id, int(_tn), _rzut,
             json.dumps({"narrative": _msg}, ensure_ascii=False), "narrative"),
        )
        conn.commit()
    except Exception as _ford_err:
        logger.warning("ford_hazard_failed", error=str(_ford_err), campaign_id=campaign_id)


def execute_travel(
    conn: sqlite3.Connection,
    campaign_id: int,
    target: dict,
    *,
    actor: int,
    record_turn: bool = True,
    route_mode: str = "direct",
    narrate_arrival: bool = False,
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

    # AUDIT #1443: travel is the single pipeline every travel endpoint delegates to,
    # so it must honour the same gates create_turn does. Without these guards a dead
    # hero could keep wandering the map and a hero could stroll away from an active
    # fight via /travel (neither passes through create_turn's dead/combat checks).
    _status_row = conn.execute(
        "SELECT status FROM characters WHERE id = ?", (character_id,)
    ).fetchone()
    _char_status = str((_status_row["status"] if _status_row else "") or "")
    _hp = sheet.get("current_hp")
    if (
        _char_status == "dead"
        or sheet.get("status") == "dead"
        or (isinstance(_hp, (int, float)) and _hp <= 0)
    ):
        raise TravelError("dead", "Bohater nie żyje — nie może podróżować.")
    from app.services.combat_service import get_active_combat as _get_active_combat
    if _get_active_combat(campaign_id):
        raise TravelError("in_combat", "Nie można podróżować w trakcie walki.")

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

    # AUDIT #1455: a fresh /travel must not be able to discard a pending ambush.
    # resolve_chain_travel pops travel_plan, so starting a new trip while an unresolved
    # encounter is parked would erase it (and, combined with the day-cooldown, guarantee
    # no further encounters). Force the fight to be resolved first.
    _tp_pre = flags.get("travel_plan")
    if (
        isinstance(_tp_pre, dict)
        and str(_tp_pre.get("interrupt_reason") or "").replace("_prompted", "") == "encounter"
        and not _tp_pre.get("combat_seen")
    ):
        raise TravelError("pending_encounter", "Zasadzka zagradza drogę — najpierw stocz walkę lub uciekaj.")

    # AUDIT #1455: 12h daily march hard-cap must gate BEFORE any step is taken.
    # run_step_sequence walks one hex then interrupts with forced_camp, so a fresh
    # /travel could crawl 1 hex per request forever past the cap (travel-resume already
    # 409s). Pre-check the persisted budget here (only when it's for the current day —
    # a new day resets it inside resolve_chain_travel).
    try:
        from app.services.clock_service import get_clock_state as _gcs_pre
        _cur_day_pre = int(_gcs_pre(campaign_id, conn=conn).get("day", 1))
    except Exception:
        _cur_day_pre = None
    _march_day_pre = flags.get("march_day")
    if _cur_day_pre is not None and _march_day_pre is not None and int(_march_day_pre) == _cur_day_pre:
        _march_hrs_pre = float(flags.get("hours_marched_today", 0.0) or 0.0)
        try:
            from app.services import companion_service as _cmp_pre
            _cap_bonus_pre = float(_cmp_pre.get_daily_cap_bonus(conn, character_id) or 0.0)
        except Exception:
            _cap_bonus_pre = 0.0
        if not flags.get("night_march") and _march_hrs_pre >= DAILY_HARD_CAP + _cap_bonus_pre:
            raise TravelError("forced_camp", "Bohater padł ze zmęczenia — najpierw rozbij obóz i odpocznij.")

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

    # #1393 — po pełnym dotarciu do nazwanej lokacji: krótka scena LLM (tylko dla
    # map-travel/resume; opisowa podróż narruje sama). Pełne dojście = arrived_hex
    # == cel i brak zasadzki.
    if narrate_arrival and result.get("ok"):
        _arr = result.get("arrived_hex") or {}
        _arrived_full = (
            int(_arr.get("q", dest_q + 1)) == dest_q
            and int(_arr.get("r", dest_r + 1)) == dest_r
            and not result.get("encounter")
        )
        maybe_narrate_arrival(conn, campaign_id, character_id, result, _arrived_full)

    # #1412 — ryzyko przeprawy przez bród (niezależnie od narracji przybycia; też przy
    # podróży przerwanej — liczy tylko faktycznie przebyte hexy 'brod').
    if result.get("ok") and record_turn:
        maybe_ford_hazard(conn, campaign_id, character_id, result)

    return result
