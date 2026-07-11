"""Bestiariusz (#1191) — per-character kill counters per enemy type.

Kills are aggregated per (character_id, enemy_key) across ALL campaigns of a
hero (Hero-First model). Unlocked knowledge tier is derived from the kill count:

    tier 0 — unknown (0 kills)
    tier 1 — basic entry unlocked (name + description + portrait)      @ 1 kill
    tier 2 — "wiedza łowcy": HP preview in combat for this type        @ 5 kills
    tier 3 — additionally +1 to-hit against this type                  @ 15 kills

Thresholds are STARTING values (Numbers Policy) — Sandbox-tunable via the
BESTIARY_TIER_KILLS map below, mirroring MARGIN_DAMAGE_STEP etc.

Design contract: recording a kill MUST NEVER raise into the combat pipeline.
Every public entry point is wrapped so a bestiary failure logs and no-ops
rather than aborting a turn.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

BESTIARY_DB_PATH = "/data/ai_gm.db"

# kills required to reach each tier — startowe, Sandbox-tunable (#1191 Numbers Policy)
BESTIARY_TIER_KILLS: dict[int, int] = {1: 1, 2: 5, 3: 15}

# tier that grants the +1 to-hit ("wiedza łowcy") mechanical bonus
HUNTER_BONUS_TIER = 3
HUNTER_BONUS = 1
# tier that unlocks in-combat HP preview
HP_VISIBLE_TIER = 2


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(BESTIARY_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def tier_for_kills(kills: int) -> int:
    """Derive unlocked tier from a kill count (highest satisfied threshold)."""
    tier = 0
    for t in sorted(BESTIARY_TIER_KILLS):
        if kills >= BESTIARY_TIER_KILLS[t]:
            tier = t
    return tier


def record_kill(
    character_id: Any,
    enemy_key: Any,
    conn: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    """Increment the kill counter for (character, enemy type).

    Returns {kills, unlocked_tier, tier_up}. On any bad input or DB error this
    no-ops and returns {} — it must not break the combat turn.

    If `conn` is supplied the caller owns the transaction (no commit here);
    otherwise a private connection is opened and committed.
    """
    try:
        cid = int(character_id)
    except (TypeError, ValueError):
        return {}
    if not enemy_key or not isinstance(enemy_key, str):
        return {}

    own = conn is None
    c = conn or _conn()
    try:
        now = _now_iso()
        row = c.execute(
            "SELECT kills, unlocked_tier FROM character_bestiary "
            "WHERE character_id = ? AND enemy_key = ?",
            (cid, enemy_key),
        ).fetchone()
        prev_tier = int(row["unlocked_tier"]) if row else 0
        new_kills = (int(row["kills"]) if row else 0) + 1
        new_tier = tier_for_kills(new_kills)

        if row is None:
            c.execute(
                "INSERT INTO character_bestiary "
                "(character_id, enemy_key, kills, first_kill_at, last_kill_at, unlocked_tier) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (cid, enemy_key, new_kills, now, now, new_tier),
            )
        else:
            c.execute(
                "UPDATE character_bestiary "
                "SET kills = ?, last_kill_at = ?, unlocked_tier = ? "
                "WHERE character_id = ? AND enemy_key = ?",
                (new_kills, now, new_tier, cid, enemy_key),
            )
        if own:
            c.commit()
        return {
            "kills": new_kills,
            "unlocked_tier": new_tier,
            "tier_up": new_tier > prev_tier,
        }
    except Exception as e:  # never propagate into combat
        logger.warning("bestiary_record_kill_failed", character_id=character_id,
                       enemy_key=enemy_key, error=str(e))
        return {}
    finally:
        if own:
            c.close()


def get_entry_tier(character_id: Any, enemy_key: Any,
                   conn: sqlite3.Connection | None = None) -> int:
    """Cheap tier lookup for combat gating. Returns 0 on any failure."""
    try:
        cid = int(character_id)
    except (TypeError, ValueError):
        return 0
    if not enemy_key or not isinstance(enemy_key, str):
        return 0
    own = conn is None
    c = conn or _conn()
    try:
        row = c.execute(
            "SELECT unlocked_tier FROM character_bestiary "
            "WHERE character_id = ? AND enemy_key = ?",
            (cid, enemy_key),
        ).fetchone()
        return int(row["unlocked_tier"]) if row else 0
    except Exception as e:
        logger.warning("bestiary_get_tier_failed", error=str(e))
        return 0
    finally:
        if own:
            c.close()


def get_entry_tiers(character_id: Any, enemy_keys: list[str],
                    conn: sqlite3.Connection | None = None) -> dict[str, int]:
    """Batch tier lookup for a set of enemy keys (one query, combat serialization).

    Returns {enemy_key: tier}; missing keys map to 0.
    """
    try:
        cid = int(character_id)
    except (TypeError, ValueError):
        return {}
    keys = [k for k in dict.fromkeys(enemy_keys) if k and isinstance(k, str)]
    if not keys:
        return {}
    own = conn is None
    c = conn or _conn()
    try:
        placeholders = ",".join("?" for _ in keys)
        rows = c.execute(
            f"SELECT enemy_key, unlocked_tier FROM character_bestiary "
            f"WHERE character_id = ? AND enemy_key IN ({placeholders})",
            (cid, *keys),
        ).fetchall()
        out = {k: 0 for k in keys}
        for r in rows:
            out[r["enemy_key"]] = int(r["unlocked_tier"])
        return out
    except Exception as e:
        logger.warning("bestiary_get_tiers_failed", error=str(e))
        return {}
    finally:
        if own:
            c.close()


def hunter_hit_bonus(character_id: Any, enemy_key: Any,
                     conn: sqlite3.Connection | None = None) -> int:
    """+1 to-hit once the hero has reached HUNTER_BONUS_TIER against this type."""
    return HUNTER_BONUS if get_entry_tier(character_id, enemy_key, conn) >= HUNTER_BONUS_TIER else 0


def get_bestiary(character_id: Any) -> dict[str, Any]:
    """Full catalogue join for the player endpoint (#1191 E3).

    Every enemy in game_config_enemies appears. Unlocked entries (kills >= 1)
    expose name/description/lore/portrait/kills/tier; locked entries expose
    ONLY {locked: true} — no name, no key leak. Includes a summary.
    """
    try:
        cid = int(character_id)
    except (TypeError, ValueError):
        return {"entries": [], "summary": {"unlocked": 0, "total": 0, "pct": 0}}
    c = _conn()
    try:
        enemies = c.execute(
            "SELECT key, label, description, lore_text, image_url, hp_base, tier "
            "FROM game_config_enemies ORDER BY COALESCE(tier, 0), label"
        ).fetchall()
        prog = {
            r["enemy_key"]: r
            for r in c.execute(
                "SELECT enemy_key, kills, unlocked_tier, first_kill_at "
                "FROM character_bestiary WHERE character_id = ?",
                (cid,),
            ).fetchall()
        }
        entries: list[dict[str, Any]] = []
        unlocked = 0
        for e in enemies:
            p = prog.get(e["key"])
            if not p or int(p["kills"]) < 1:
                entries.append({"locked": True})
                continue
            unlocked += 1
            tier = int(p["unlocked_tier"])
            entry: dict[str, Any] = {
                "locked": False,
                "enemy_key": e["key"],
                "name": e["label"],
                "description": e["description"],
                "lore_text": e["lore_text"] or e["description"],
                "image_url": e["image_url"],
                "kills": int(p["kills"]),
                "unlocked_tier": tier,
                "first_kill_at": p["first_kill_at"],
                "next_threshold": _next_threshold(int(p["kills"])),
            }
            if tier >= HP_VISIBLE_TIER:
                entry["hp_max"] = e["hp_base"]
            entries.append(entry)
        total = len(enemies)
        pct = round(100 * unlocked / total) if total else 0
        return {"entries": entries,
                "summary": {"unlocked": unlocked, "total": total, "pct": pct}}
    except Exception as e:
        logger.warning("bestiary_get_failed", error=str(e))
        return {"entries": [], "summary": {"unlocked": 0, "total": 0, "pct": 0}}
    finally:
        c.close()


def _next_threshold(kills: int) -> int | None:
    """Kills needed for the next tier, or None if maxed."""
    for t in sorted(BESTIARY_TIER_KILLS):
        need = BESTIARY_TIER_KILLS[t]
        if kills < need:
            return need
    return None


def _first_sentence(text: str | None) -> str:
    """First sentence of a lore/description string, for the public teaser."""
    if not text:
        return ""
    t = text.strip()
    for sep in (". ", "! ", "? "):
        i = t.find(sep)
        if i != -1:
            return t[: i + 1].strip()
    # single sentence — trim to a safe length
    return (t[:160].rstrip() + "…") if len(t) > 160 else t


def get_showcase_bestiary(user_id: Any = None) -> dict[str, Any]:
    """#1191 / #915 — bestiary for the public showcase page.

    Anonymous: every enemy that has a portrait, exposing name + portrait + a
    one-sentence teaser (NO full lore/description/stats). When a logged-in game
    account is supplied (unified auth, #915), enemies that account's heroes have
    defeated are enriched with full description + lore + total kill count and
    flagged `defeated: true` (aggregated across ALL the account's heroes).
    """
    c = _conn()
    try:
        enemies = c.execute(
            "SELECT key, label, description, lore_text, image_url, tier "
            "FROM game_config_enemies "
            "WHERE image_url IS NOT NULL AND image_url != '' "
            "ORDER BY COALESCE(tier, 0), label"
        ).fetchall()

        defeated: dict[str, int] = {}
        uid = None
        if user_id is not None:
            try:
                uid = int(user_id)
            except (TypeError, ValueError):
                uid = None
        if uid is not None:
            try:
                rows = c.execute(
                    "SELECT b.enemy_key, SUM(b.kills) AS kills "
                    "FROM character_bestiary b "
                    "JOIN characters ch ON ch.id = b.character_id "
                    "WHERE ch.user_id = ? AND b.kills >= 1 "
                    "GROUP BY b.enemy_key",
                    (uid,),
                ).fetchall()
                defeated = {r["enemy_key"]: int(r["kills"]) for r in rows}
            except Exception as e:
                logger.warning("showcase_bestiary_user_join_failed", error=str(e))

        entries: list[dict[str, Any]] = []
        for e in enemies:
            base = {
                "enemy_key": e["key"],
                "name": e["label"],
                "image_url": e["image_url"],
                "teaser": _first_sentence(e["lore_text"] or e["description"]),
                "defeated": False,
            }
            if e["key"] in defeated:
                base["defeated"] = True
                base["kills"] = defeated[e["key"]]
                base["description"] = e["description"]
                base["lore_text"] = e["lore_text"] or e["description"]
            entries.append(base)

        total = len(entries)
        defeated_count = len(defeated)
        return {
            "entries": entries,
            "authenticated": uid is not None,
            "summary": {
                "total": total,
                "defeated": defeated_count,
                "pct": round(100 * defeated_count / total) if total else 0,
            },
        }
    except Exception as e:
        logger.warning("showcase_bestiary_failed", error=str(e))
        return {"entries": [], "authenticated": False,
                "summary": {"total": 0, "defeated": 0, "pct": 0}}
    finally:
        c.close()
