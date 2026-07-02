"""Reputation system — mechanical consequences of a hero's deeds (#1099).

Per-region reputation (scope_type='region'). Only 'kresy' is a live region today
(#917 FAZA RM not yet implemented), so `resolve_region` defensively falls back to it.
`scope_type` is generic so a future per-faction dimension (#1103) reuses this table.

Reputation is an integer per (character_id, scope_type, scope_key). It drives:
  * shop prices           -> shop_price_multiplier(value)     (buy_item)
  * quest access          -> quest_access_allowed(value, min) (gate mechanism)
  * NPC attitude baseline -> npc_attitude_from_reputation(v)  (narrator context)
  * anti-farm / rewards   -> apply_campaign_outcome(...)      (close/delete hooks)

All numeric thresholds are STARTING values, Sandbox-tunable (Numbers Policy).
"""
from __future__ import annotations

import sqlite3

import structlog

logger = structlog.get_logger(__name__)

# ── Region model (#917) ──────────────────────────────────────────────────────
# Only region live at launch; every hex is currently "Kresy" (region column NYI).
REGION_DEFAULT = "kresy"

# ── Campaign-outcome deltas (STARTING values) ────────────────────────────────
REP_VICTORY_REWARD = 20   # finishing a campaign builds regional standing
REP_DEATH_PENALTY = 5     # dying dents standing lightly
REP_ABANDON_PENALTY = 15  # farm-and-bail: abandonment scars regional reputation

_OUTCOME_DELTAS = {
    "victory": REP_VICTORY_REWARD,
    "completed": REP_VICTORY_REWARD,
    "death": -REP_DEATH_PENALTY,
    "abandoned": -REP_ABANDON_PENALTY,
}

# ── Tier thresholds (STARTING values) ────────────────────────────────────────
_TIER_EXALTED = 50
_TIER_FRIENDLY = 20
_TIER_DISLIKED = -20
_TIER_HATED = -50

# ── Shop-price curve (STARTING values) ───────────────────────────────────────
REP_PRICE_STEP = 0.004  # multiplier delta per reputation point
REP_PRICE_MIN = 0.75    # best possible discount (25% off)
REP_PRICE_MAX = 1.30    # worst possible surcharge (30% markup)

# ── Attitude thresholds (STARTING values) ────────────────────────────────────
_ATTITUDE_FRIENDLY = 20
_ATTITUDE_HOSTILE = -20


# ─── Schema ──────────────────────────────────────────────────────────────────

def ensure_reputation_table(conn: sqlite3.Connection) -> None:
    """Idempotently create character_reputation. Migration owns this in prod;
    tests call it directly against a scratch connection."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS character_reputation (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id INTEGER NOT NULL,
            scope_type TEXT NOT NULL DEFAULT 'region',
            scope_key TEXT NOT NULL,
            value INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(character_id, scope_type, scope_key)
        )
        """
    )
    conn.commit()


# ─── CRUD ────────────────────────────────────────────────────────────────────

def get_reputation(
    conn: sqlite3.Connection,
    character_id: int,
    scope_key: str,
    scope_type: str = "region",
) -> int:
    """Current reputation value; 0 when no row exists (neutral default)."""
    row = conn.execute(
        """
        SELECT value FROM character_reputation
        WHERE character_id = ? AND scope_type = ? AND scope_key = ?
        """,
        (int(character_id), str(scope_type), str(scope_key)),
    ).fetchone()
    if not row:
        return 0
    return int(row["value"] if isinstance(row, sqlite3.Row) else row[0])


def adjust_reputation(
    conn: sqlite3.Connection,
    character_id: int,
    scope_key: str,
    delta: int,
    scope_type: str = "region",
    reason: str | None = None,
) -> int:
    """Add `delta` to reputation (upsert). Returns the new value."""
    conn.execute(
        """
        INSERT INTO character_reputation (character_id, scope_type, scope_key, value)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(character_id, scope_type, scope_key)
        DO UPDATE SET value = value + excluded.value,
                      updated_at = CURRENT_TIMESTAMP
        """,
        (int(character_id), str(scope_type), str(scope_key), int(delta)),
    )
    conn.commit()
    new_val = get_reputation(conn, character_id, scope_key, scope_type)
    logger.info(
        "reputation_adjusted",
        character_id=int(character_id),
        scope_type=scope_type,
        scope_key=scope_key,
        delta=int(delta),
        new_value=new_val,
        reason=reason,
    )
    return new_val


def get_all_reputation(conn: sqlite3.Connection, character_id: int) -> list[dict]:
    """All reputation rows for a character (for the player-facing exposure/UI)."""
    rows = conn.execute(
        """
        SELECT scope_type, scope_key, value
        FROM character_reputation
        WHERE character_id = ?
        ORDER BY scope_type, scope_key
        """,
        (int(character_id),),
    ).fetchall()
    out = []
    for r in rows:
        val = int(r["value"])
        out.append({
            "scope_type": r["scope_type"],
            "scope_key": r["scope_key"],
            "value": val,
            "tier": reputation_tier(val),
        })
    return out


# ─── Pure effect functions ───────────────────────────────────────────────────

def reputation_tier(value: int) -> str:
    """Map a reputation value to a named standing tier."""
    v = int(value)
    if v >= _TIER_EXALTED:
        return "exalted"
    if v >= _TIER_FRIENDLY:
        return "friendly"
    if v <= _TIER_HATED:
        return "hated"
    if v <= _TIER_DISLIKED:
        return "disliked"
    return "neutral"


def shop_price_multiplier(value: int) -> float:
    """Buy-price multiplier from reputation. Higher standing → cheaper (mult < 1)."""
    mult = 1.0 - int(value) * REP_PRICE_STEP
    return max(REP_PRICE_MIN, min(REP_PRICE_MAX, round(mult, 4)))


def quest_access_allowed(value: int, min_reputation: int) -> bool:
    """Reputation gate for content that demands a minimum regional standing."""
    return int(value) >= int(min_reputation)


def npc_attitude_from_reputation(value: int) -> str:
    """Baseline NPC disposition suggested by the hero's regional reputation."""
    v = int(value)
    if v >= _ATTITUDE_FRIENDLY:
        return "friendly"
    if v <= _ATTITUDE_HOSTILE:
        return "hostile"
    return "neutral"


_ATTITUDE_PL = {"friendly": "przyjazny", "neutral": "neutralny", "hostile": "wrogi"}


def reputation_context_line(value: int, region: str = REGION_DEFAULT) -> str:
    """One-line standing summary injected into the narrator context so NPCs react
    to the hero's regional reputation. Empty when neutral (nothing to say)."""
    v = int(value)
    if npc_attitude_from_reputation(v) == "neutral":
        # neutral standing -> nothing worth telling the narrator
        return ""
    tier = reputation_tier(v)
    attitude_pl = _ATTITUDE_PL[npc_attitude_from_reputation(v)]
    sign = "+" if v >= 0 else ""
    return (
        f"=== REPUTACJA W REGIONIE ({region}) ===\n"
        f"Bohater ma reputację {sign}{v} ({tier}). "
        f"Miejscowi i NPC domyślnie odnoszą się do niego jako: {attitude_pl}. "
        f"Wpleć tę postawę w reakcje mieszkańców, kupców i zleceniodawców."
    )


# ─── Region resolution (defensive — region column NYI, #917) ─────────────────

def resolve_region(conn: sqlite3.Connection, campaign_id: int) -> str:
    """Region key of a campaign's current location. Until FAZA RM adds the
    `region` column everything is 'kresy'; any lookup failure falls back to it."""
    try:
        row = conn.execute(
            """
            SELECT wh.region AS region
            FROM game_sessions gs
            JOIN game_locations gl ON gl.id = gs.current_location_id
            JOIN world_hexes wh ON wh.q = gl.world_hex_q AND wh.r = gl.world_hex_r
            WHERE gs.campaign_id = ?
            LIMIT 1
            """,
            (int(campaign_id),),
        ).fetchone()
        if row and row["region"]:
            return str(row["region"])
    except Exception:
        # region column / tables not present yet -> default region
        pass
    return REGION_DEFAULT


# ─── Campaign-outcome hook ───────────────────────────────────────────────────

def apply_campaign_outcome(
    conn: sqlite3.Connection,
    character_id: int,
    campaign_id: int,
    outcome: str,
) -> int | None:
    """Apply the regional reputation delta for a campaign outcome.

    outcome in {'victory'/'completed', 'death', 'abandoned'}. Unknown -> no-op (None).
    Returns the new reputation value, or None if the outcome carries no delta.
    """
    delta = _OUTCOME_DELTAS.get(str(outcome).strip().lower())
    if not delta:
        return None
    region = resolve_region(conn, campaign_id)
    return adjust_reputation(
        conn, character_id, region, delta,
        scope_type="region", reason=f"campaign_{outcome}",
    )
