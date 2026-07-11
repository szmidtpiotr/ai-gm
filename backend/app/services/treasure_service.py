"""Mapy skarbów (#1196) — treasure maps: fragments, completion, dig payout.

Design decisions (Piotr, 2026-07-11), see docs/PLAN_1196_MAPY_SKARBOW.md:
- D1: one-time, per hero (world_treasures.character_id).
- D3: fully automatic. Completing a map rolls loot like an enemy drop and
  FREEZES it (loot_snapshot_json) + fixes the target hex. On arrival the LLM is
  fed a deterministic hint; the player must search (percepcja test + guardian).
- D5: fragments grouped by stable treasure_id, NOT by name.
- D6: total_parts=1 = whole map at once (NPC/LLM grant). grant_map_item is the
  single dispatcher for whole / generic-fragment / authored-keyed carriers.
- D7: loot scales with total_parts (gold_mult / extra_loot_rolls / loot_tier_bonus).

Every entry point is DB-error tolerant: a failure here must not break a turn.
"""

from __future__ import annotations

import json
import random
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from app.core.logging import get_logger

logger = get_logger(__name__)

TREASURE_DB_PATH = "/data/ai_gm.db"

# Carrier item keys / prefix that route a grant into the treasure tables.
_WHOLE_MAP_KEYS = {"treasure_map"}
_GENERIC_FRAGMENT_KEYS = {"fragment_mapy_skarbow"}
_AUTHORED_PREFIX = "tm_"

# Numbers Policy (starting values — Sandbox-tunable).
DEFAULT_GENERIC_PARTS = 3
DEFAULT_DIG_DC = 12
GUARDIAN_CHANCE = 0.5
DIG_SKILL_KEY = "investigation"  # Dochodzenie — przeszukanie skrytki


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(TREASURE_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def is_treasure_map_key(item_key: str, item_type: str | None = None) -> bool:
    """True when a granted item is a treasure-map carrier (→ intercept)."""
    k = str(item_key or "").strip()
    if not k:
        return False
    if (item_type or "").strip().lower() == "treasure_map":
        return True
    if k in _WHOLE_MAP_KEYS or k in _GENERIC_FRAGMENT_KEYS:
        return True
    return k.startswith(_AUTHORED_PREFIX)


# Label heuristic for LLM/narrator-invented treasure maps. Narrator item names
# are too varied for a two-word pattern ("Mapa do skrytki", "Podejrzanie świeża
# mapa", …) — ANY narrative item whose label mentions a map is treated as a
# treasure map. Real fog-reveal maps are catalog items (item_type='map') and go
# through their own grant path, so they never reach this heuristic.
_MAP_WORD_RE = re.compile(r"\bmap\w*\b", re.IGNORECASE)


def looks_like_treasure_map(item_key: str = "", item_type: str | None = None,
                            label: str | None = None) -> bool:
    """Broad detector: carrier key/type OR any map-named narrator label.

    A fog-reveal map (item_type='map' + map_reveal effect) is NEVER a treasure map.
    """
    if is_treasure_map_key(item_key, item_type):
        return True
    if (item_type or "").strip().lower() == "map":
        return False
    return bool(_MAP_WORD_RE.search(str(label or "")))


# ---------------------------------------------------------------------------
# Loot rolling directly by loot_table_key (treasure loot is table-keyed, not
# enemy-keyed, so we cannot reuse loot_service.roll_loot which joins enemies).
# ---------------------------------------------------------------------------

def _roll_table(conn: sqlite3.Connection, table_key: str) -> list[dict]:
    """Roll every entry of a loot table once. Returns loot dicts (XOR shape)."""
    tk = str(table_key or "").strip()
    if not tk:
        return []
    try:
        rows = conn.execute(
            """
            SELECT e.item_key, e.weapon_key, e.consumable_key, e.weight,
                   e.qty_min, e.qty_max
            FROM game_config_loot_entries e
            JOIN game_config_loot_tables t ON t.key = e.loot_table_key
            WHERE e.loot_table_key = ? AND t.is_active = 1
            ORDER BY e.id ASC
            """,
            (tk,),
        ).fetchall()
    except sqlite3.OperationalError:
        return []
    rolled: list[dict] = []
    for r in rows:
        # never re-drop a treasure-map carrier from a treasure payout (loop guard)
        if str(r["item_key"] or "") in _GENERIC_FRAGMENT_KEYS or str(r["item_key"] or "") in _WHOLE_MAP_KEYS:
            continue
        weight = int(r["weight"] or 0)
        if random.random() > max(0.0, min(1.0, weight / 100.0)):
            continue
        qmin = max(1, int(r["qty_min"] or 1))
        qmax = max(qmin, int(r["qty_max"] or qmin))
        rolled.append(
            {
                "item_key": r["item_key"],
                "weapon_key": r["weapon_key"],
                "consumable_key": r["consumable_key"],
                "quantity": random.randint(qmin, qmax),
            }
        )
    return rolled


def _roll_gold(conn: sqlite3.Connection, table_key: str) -> int:
    tk = str(table_key or "").strip()
    if not tk:
        return 0
    try:
        row = conn.execute(
            "SELECT gold_min, gold_max FROM game_config_loot_tables "
            "WHERE key = ? AND is_active = 1 LIMIT 1",
            (tk,),
        ).fetchone()
    except sqlite3.OperationalError:
        return 0
    if not row:
        return 0
    gmin = max(0, int(row["gold_min"] or 0))
    gmax = max(gmin, int(row["gold_max"] or 0))
    if gmax <= 0:
        return 0
    return random.randint(gmin, gmax)


def _scaling_for_parts(total_parts: int) -> tuple[float, int, int]:
    """D7 default scaling → (gold_mult, extra_loot_rolls, loot_tier_bonus)."""
    p = max(1, int(total_parts or 1))
    gold_mult = 1.0 + 0.5 * (p - 1)
    extra_rolls = (p - 1) // 2
    return gold_mult, extra_rolls, 0


# ---------------------------------------------------------------------------
# Treasure generation & completion
# ---------------------------------------------------------------------------

def _current_hex(conn: sqlite3.Connection, campaign_id: int) -> Optional[tuple[int, int]]:
    try:
        row = conn.execute(
            "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
            (campaign_id,),
        ).fetchone()
    except sqlite3.OperationalError:
        return None
    if not row or not row["session_flags"]:
        return None
    try:
        flags = json.loads(row["session_flags"])
    except (TypeError, ValueError):
        return None
    ch = flags.get("current_hex") or {}
    if isinstance(ch, dict) and ch.get("q") is not None and ch.get("r") is not None:
        return int(ch["q"]), int(ch["r"])
    return None


def _hexdist(a: tuple[int, int], b: tuple[int, int]) -> int:
    dq, dr = a[0] - b[0], a[1] - b[1]
    return (abs(dq) + abs(dq + dr) + abs(dr)) // 2


# Ring around the explored world where a generated treasure is buried: far enough
# to be a real trip, close enough to sit inside the map the player knows exists.
TREASURE_RING_MIN = 3
TREASURE_RING_MAX = 12

# A dug-up treasure never pays less than this (per map part) — sparse enemy loot
# tables would otherwise leave the chest empty. STARTING value, Sandbox-tunable.
TREASURE_GOLD_FLOOR = 30


def _pick_treasure_hex(conn: sqlite3.Connection, character_id: int,
                       campaign_id: int) -> Optional[dict]:
    """Pick an empty overworld hex ANCHORED to the campaign's explored area.

    Anchors = the player's current hex + every discovered/known campaign hex. The
    treasure lands in a ring [3,12] around them so it is reachable and inside the
    known world — never a far-flung outlier (fixes the blank-map bug where a random
    stray hex at the map's edge was chosen when current_hex was unknown).
    """
    used = {
        (int(r["hex_q"]), int(r["hex_r"]))
        for r in conn.execute(
            "SELECT hex_q, hex_r FROM world_treasures WHERE character_id = ?",
            (character_id,),
        ).fetchall()
    }
    anchors: list[tuple[int, int]] = []
    cur = _current_hex(conn, campaign_id)
    if cur is not None:
        anchors.append(cur)
        used.add(cur)  # never bury under the player's feet
    try:
        for r in conn.execute(
            "SELECT hex_q, hex_r FROM campaign_hex_data "
            "WHERE campaign_id = ? AND (COALESCE(discovered,0)=1 OR COALESCE(known,0)=1)",
            (campaign_id,),
        ).fetchall():
            anchors.append((int(r["hex_q"]), int(r["hex_r"])))
    except sqlite3.OperationalError:
        pass

    rows = conn.execute(
        "SELECT q, r, region, encounter_pool FROM world_hexes "
        "WHERE map_level = 0 AND is_active = 1 AND location_key IS NULL"
    ).fetchall()
    empty = [r for r in rows if (int(r["q"]), int(r["r"])) not in used]
    if not empty:
        return None

    def _in_ring(row: sqlite3.Row, lo: int, hi: int) -> bool:
        c = (int(row["q"]), int(row["r"]))
        return any(lo <= _hexdist(c, a) <= hi for a in anchors)

    pool: list[sqlite3.Row] = []
    if anchors:
        pool = [r for r in empty if _in_ring(r, TREASURE_RING_MIN, TREASURE_RING_MAX)]
        if not pool:  # widen the ring
            pool = [r for r in empty if _in_ring(r, 1, TREASURE_RING_MAX * 2)]
        if not pool:  # anything inside the anchors' bounding box (+4 margin)
            aq = [a[0] for a in anchors]
            ar = [a[1] for a in anchors]
            qlo, qhi = min(aq) - 4, max(aq) + 4
            rlo, rhi = min(ar) - 4, max(ar) + 4
            pool = [r for r in empty
                    if qlo <= int(r["q"]) <= qhi and rlo <= int(r["r"]) <= rhi]
    if not pool:
        # No anchors / nothing nearby → prefer real map hexes (region set) over strays.
        pool = [r for r in empty if r["region"]] or empty

    chosen = random.choice(pool)
    return {
        "q": int(chosen["q"]),
        "r": int(chosen["r"]),
        "region": chosen["region"],
        "encounter_pool": chosen["encounter_pool"],
    }


def _pick_loot_table(conn: sqlite3.Connection, region: str | None) -> Optional[str]:
    """Pick a non-boss enemy loot table (region-preferred) for a generated map."""
    try:
        rows = conn.execute(
            """
            SELECT t.key FROM game_config_loot_tables t
            JOIN game_config_enemies e ON e.loot_table_key = t.key
            WHERE t.is_active = 1 AND COALESCE(e.tier, 'standard') != 'boss'
            """
        ).fetchall()
    except sqlite3.OperationalError:
        return None
    keys = [r["key"] for r in rows]
    if not keys:
        return None
    return random.choice(keys)


def _pick_guardian(conn: sqlite3.Connection, encounter_pool: str | None,
                   region: str | None) -> Optional[str]:
    if random.random() > GUARDIAN_CHANCE:
        return None
    # from the hex encounter pool first
    pool: list[str] = []
    if encounter_pool:
        try:
            pool = [str(x) for x in json.loads(encounter_pool) if x]
        except (TypeError, ValueError):
            pool = []
    if pool:
        return random.choice(pool)
    try:
        rows = conn.execute(
            "SELECT key FROM game_config_enemies WHERE COALESCE(tier,'standard')!='boss' "
            "AND is_active = 1 ORDER BY RANDOM() LIMIT 1"
        ).fetchall()
    except sqlite3.OperationalError:
        return None
    return rows[0]["key"] if rows else None


def _generate_treasure(conn: sqlite3.Connection, campaign_id: int, character_id: int, *,
                       total_parts: int, loot_table_key: str | None = None,
                       guardian: str | None = None, dc: int = DEFAULT_DIG_DC,
                       map_key: str | None = None, label: str | None = None,
                       created_by: str = "generated") -> Optional[int]:
    """Create a buried world_treasures row. Returns treasure_id or None."""
    hexinfo = _pick_treasure_hex(conn, character_id, campaign_id)
    if not hexinfo:
        logger.warning("treasure_no_free_hex", character_id=character_id, campaign_id=campaign_id)
        return None
    region = hexinfo["region"]
    if not loot_table_key:
        loot_table_key = _pick_loot_table(conn, region)
    if guardian is None:
        guardian = _pick_guardian(conn, hexinfo["encounter_pool"], region)
    gold_mult, extra_rolls, tier_bonus = _scaling_for_parts(total_parts)
    if not map_key:
        map_key = "tm_" + uuid.uuid4().hex[:8]
    if not label:
        label = "Mapa skarbu"
    cur = conn.execute(
        """
        INSERT INTO world_treasures
            (map_key, label, hex_q, hex_r, map_level, region, loot_table_key,
             guardian_enemy_key, dc, total_parts, loot_tier_bonus, gold_mult,
             extra_loot_rolls, character_id, campaign_id, state, created_by, created_at)
        VALUES (?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'buried', ?, ?)
        """,
        (map_key, label, hexinfo["q"], hexinfo["r"], region, loot_table_key,
         guardian, int(dc), int(total_parts), tier_bonus, gold_mult, extra_rolls,
         character_id, campaign_id, created_by, _now_iso()),
    )
    return int(cur.lastrowid)


def admin_place_treasure(conn: sqlite3.Connection, *, character_id: int, campaign_id: int,
                         hex_q: int, hex_r: int, label: str | None = None,
                         loot_table_key: str | None = None, guardian: str | None = None,
                         dc: int = DEFAULT_DIG_DC, total_parts: int = 1,
                         gold_bonus: int = 0, loot_tier_bonus: int | None = None,
                         gold_mult: float | None = None,
                         extra_loot_rolls: int | None = None) -> Optional[int]:
    """Admin/event: bury a treasure on a chosen hex and hand the completed map to a
    hero (fragments 1..total_parts), so it shows on their map and is diggable."""
    _gm, _ex, _tb = _scaling_for_parts(total_parts)
    gold_mult = _gm if gold_mult is None else gold_mult
    extra_loot_rolls = _ex if extra_loot_rolls is None else extra_loot_rolls
    loot_tier_bonus = _tb if loot_tier_bonus is None else loot_tier_bonus
    rrow = conn.execute(
        "SELECT region FROM world_hexes WHERE q = ? AND r = ? AND map_level = 0 LIMIT 1",
        (hex_q, hex_r),
    ).fetchone()
    region = rrow["region"] if rrow else None
    if not loot_table_key:
        loot_table_key = _pick_loot_table(conn, region)
    map_key = "tm_admin_" + uuid.uuid4().hex[:8]
    cur = conn.execute(
        """
        INSERT INTO world_treasures
            (map_key, label, hex_q, hex_r, map_level, region, loot_table_key,
             guardian_enemy_key, dc, total_parts, loot_tier_bonus, gold_mult,
             extra_loot_rolls, gold_bonus, character_id, campaign_id, state,
             created_by, created_at)
        VALUES (?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'buried', 'admin', ?)
        """,
        (map_key, label or "Mapa skarbu", hex_q, hex_r, region, loot_table_key,
         guardian, int(dc), int(total_parts), int(loot_tier_bonus), float(gold_mult),
         int(extra_loot_rolls), int(gold_bonus), character_id, campaign_id, _now_iso()),
    )
    tid = int(cur.lastrowid)
    for p in range(1, int(total_parts) + 1):
        conn.execute(
            "INSERT OR IGNORE INTO character_map_fragments "
            "(character_id, campaign_id, treasure_id, part_no, acquired_at, source) "
            "VALUES (?, ?, ?, ?, ?, 'admin')",
            (character_id, campaign_id, tid, p, _now_iso()),
        )
    _finalize_treasure(conn, tid)
    conn.commit()
    return tid


def _collected(conn: sqlite3.Connection, character_id: int, treasure_id: int) -> int:
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM character_map_fragments "
        "WHERE character_id = ? AND treasure_id = ?",
        (character_id, treasure_id),
    ).fetchone()
    return int(row["n"] or 0) if row else 0


def _finalize_treasure(conn: sqlite3.Connection, treasure_id: int) -> None:
    """Roll & freeze loot on the treasure (D3), scaled by parts (D7).

    A treasure is NEVER empty: sparse enemy tables often roll nothing, so we
    guarantee at least one real item and floor the gold — a dug-up chest must feel
    like a reward, not a weak-mob drop.
    """
    t = conn.execute("SELECT * FROM world_treasures WHERE id = ?", (treasure_id,)).fetchone()
    if not t or t["loot_snapshot_json"]:
        return  # already finalized
    table_key = t["loot_table_key"]
    total_parts = max(1, int(t["total_parts"] or 1))
    rolls = 1 + int(t["extra_loot_rolls"] or 0)
    loot: list[dict] = []
    gold = 0
    for _ in range(rolls):
        loot.extend(_roll_table(conn, table_key))
        gold += _roll_gold(conn, table_key)
    if not loot:  # never hand the player an empty chest
        guar = _guaranteed_item(conn, table_key)
        if guar:
            loot.append(guar)
    gold = int(round(gold * float(t["gold_mult"] or 1.0)))
    gold = max(gold, TREASURE_GOLD_FLOOR * total_parts)  # floor — treasures pay out
    conn.execute(
        "UPDATE world_treasures SET loot_snapshot_json = ?, gold_snapshot = ? WHERE id = ?",
        (json.dumps(loot), gold, treasure_id),
    )


def _guaranteed_item(conn: sqlite3.Connection, table_key: str) -> Optional[dict]:
    """A fallback item so a treasure is never empty: the table's best non-map entry,
    else a common healing consumable."""
    try:
        rows = conn.execute(
            "SELECT item_key, weapon_key, consumable_key, qty_min, qty_max "
            "FROM game_config_loot_entries WHERE loot_table_key = ? "
            "ORDER BY weight DESC", (table_key,),
        ).fetchall()
    except sqlite3.OperationalError:
        rows = []
    for r in rows:
        ik = str(r["item_key"] or "")
        if ik in _GENERIC_FRAGMENT_KEYS or ik in _WHOLE_MAP_KEYS:
            continue
        if not (r["item_key"] or r["weapon_key"] or r["consumable_key"]):
            continue
        qmin = max(1, int(r["qty_min"] or 1))
        qmax = max(qmin, int(r["qty_max"] or qmin))
        return {"item_key": r["item_key"], "weapon_key": r["weapon_key"],
                "consumable_key": r["consumable_key"], "quantity": random.randint(qmin, qmax)}
    for key in ("potion_healing_minor", "potion_healing", "bandage", "bandaz"):
        try:
            hit = conn.execute(
                "SELECT key FROM game_config_items WHERE key = ? AND is_active = 1", (key,)
            ).fetchone()
        except sqlite3.OperationalError:
            hit = None
        if hit:
            return {"item_key": key, "quantity": 1}
    return None


# ---------------------------------------------------------------------------
# Grant dispatcher (D6) — called from loot_service.grant_loot_to_character
# ---------------------------------------------------------------------------

def _lookup_effect_json(conn: sqlite3.Connection, item_key: str) -> Optional[dict]:
    for tbl, col in (("game_items", "effect_json"), ("game_config_items", "effect_json")):
        try:
            row = conn.execute(
                f"SELECT {col} AS ej FROM {tbl} WHERE key = ? LIMIT 1", (item_key,)
            ).fetchone()
        except sqlite3.OperationalError:
            continue
        if row and row["ej"]:
            try:
                data = json.loads(row["ej"])
                if isinstance(data, dict):
                    return data
            except (TypeError, ValueError):
                pass
    return None


def grant_map_item(conn: sqlite3.Connection, character_id: int, campaign_id: int,
                   item_key: str, effect_json: dict | None = None,
                   source: str = "loot", label: str | None = None) -> Optional[dict]:
    """Route a treasure-map carrier grant into the treasure tables (D6).

    `label` overrides the displayed map name (used for LLM/narrator whole maps).
    Returns a toast dict {treasure_id, map_label, part_no, collected,
    total_parts, complete, hex?} or None on failure.
    """
    try:
        cid = int(character_id)
        camp = int(campaign_id or 0)
        key = str(item_key or "").strip()
        if effect_json is None:
            effect_json = _lookup_effect_json(conn, key)
        tm_payload = (effect_json or {}).get("treasure_map") if isinstance(effect_json, dict) else None

        treasure_id: Optional[int] = None
        part_no: Optional[int] = None
        total_parts = 1

        if isinstance(tm_payload, dict) and tm_payload.get("map_key"):
            # (c) authored / multi-part keyed map
            map_key = str(tm_payload["map_key"])
            total_parts = max(1, int(tm_payload.get("total_parts") or 1))
            part_no = int(tm_payload.get("part_no") or 0) or None
            row = conn.execute(
                "SELECT id, total_parts FROM world_treasures "
                "WHERE map_key = ? AND character_id = ? AND state = 'buried' LIMIT 1",
                (map_key, cid),
            ).fetchone()
            if row:
                treasure_id = int(row["id"])
                total_parts = int(row["total_parts"] or total_parts)
            else:
                treasure_id = _generate_treasure(
                    conn, camp, cid, total_parts=total_parts,
                    loot_table_key=tm_payload.get("loot_table_key"),
                    guardian=tm_payload.get("guardian"),
                    dc=int(tm_payload.get("dc") or DEFAULT_DIG_DC),
                    map_key=map_key, label=tm_payload.get("label"),
                )
        elif key in _GENERIC_FRAGMENT_KEYS:
            # (b) generic fragment → fill an incomplete auto-map or make a new one
            row = conn.execute(
                """
                SELECT wt.id, wt.total_parts,
                       (SELECT COUNT(*) FROM character_map_fragments f
                        WHERE f.treasure_id = wt.id AND f.character_id = wt.character_id) AS coll
                FROM world_treasures wt
                WHERE wt.character_id = ? AND wt.state = 'buried'
                  AND wt.map_key LIKE 'tm_%'
                  AND (SELECT COUNT(*) FROM character_map_fragments f
                       WHERE f.treasure_id = wt.id AND f.character_id = wt.character_id) < wt.total_parts
                ORDER BY wt.id ASC LIMIT 1
                """,
                (cid,),
            ).fetchone()
            if row:
                treasure_id = int(row["id"])
                total_parts = int(row["total_parts"] or DEFAULT_GENERIC_PARTS)
            else:
                total_parts = DEFAULT_GENERIC_PARTS
                treasure_id = _generate_treasure(conn, camp, cid, total_parts=total_parts)
        else:
            # (a) whole map (NPC/LLM bare treasure_map) → one part, instant complete
            total_parts = 1
            treasure_id = _generate_treasure(
                conn, camp, cid, total_parts=1, created_by="npc", label=label,
            )

        if treasure_id is None:
            return None

        # assign next part number if not fixed by an authored payload
        if part_no is None:
            existing = {
                int(r["part_no"])
                for r in conn.execute(
                    "SELECT part_no FROM character_map_fragments "
                    "WHERE character_id = ? AND treasure_id = ?",
                    (cid, treasure_id),
                ).fetchall()
            }
            part_no = next(n for n in range(1, total_parts + 1) if n not in existing) \
                if len(existing) < total_parts else total_parts

        try:
            conn.execute(
                "INSERT INTO character_map_fragments "
                "(character_id, campaign_id, treasure_id, part_no, acquired_at, source) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (cid, camp, treasure_id, int(part_no), _now_iso(), source),
            )
        except sqlite3.IntegrityError:
            pass  # duplicate part — ignore

        collected = _collected(conn, cid, treasure_id)
        t = conn.execute(
            "SELECT map_key, label, total_parts, hex_q, hex_r, region FROM world_treasures WHERE id = ?",
            (treasure_id,),
        ).fetchone()
        total_parts = int(t["total_parts"] or total_parts)
        complete = collected >= total_parts
        if complete:
            _finalize_treasure(conn, treasure_id)
        conn.commit()

        out = {
            "treasure_id": treasure_id,
            "map_label": t["label"] or "Mapa skarbu",
            "part_no": int(part_no),
            "collected": collected,
            "total_parts": total_parts,
            "complete": complete,
        }
        if complete:
            out["hex"] = {"q": int(t["hex_q"]), "r": int(t["hex_r"])}
            out["region"] = t["region"]
        return out
    except Exception as e:  # never break a turn
        logger.warning("grant_map_item_failed", error=str(e), item_key=item_key)
        try:
            conn.rollback()
        except Exception:
            pass
        return None


# ---------------------------------------------------------------------------
# Read model
# ---------------------------------------------------------------------------

def get_treasure_maps(conn: sqlite3.Connection, character_id: int) -> dict:
    """Maps grouped per treasure_id for the inventory 'Mapy skarbów' section."""
    try:
        rows = conn.execute(
            """
            SELECT wt.id, wt.label, wt.total_parts, wt.state, wt.hex_q, wt.hex_r,
                   wt.region, wt.campaign_id,
                   (SELECT COUNT(*) FROM character_map_fragments f
                    WHERE f.treasure_id = wt.id AND f.character_id = ?) AS collected
            FROM world_treasures wt
            WHERE wt.character_id = ? AND wt.state = 'buried'
              AND EXISTS (SELECT 1 FROM character_map_fragments f
                          WHERE f.treasure_id = wt.id AND f.character_id = ?)
            ORDER BY wt.id DESC
            """,
            (character_id, character_id, character_id),
        ).fetchall()
    except sqlite3.OperationalError:
        return {"maps": []}
    maps = []
    for r in rows:
        total = int(r["total_parts"] or 1)
        collected = int(r["collected"] or 0)
        complete = collected >= total
        entry = {
            "treasure_id": int(r["id"]),
            "map_label": r["label"] or "Mapa skarbu",
            "collected": collected,
            "total_parts": total,
            "complete": complete,
            "state": r["state"],
            # kraina widoczna od pierwszego fragmentu (wskazówka dokąd);
            # dokładny heks zdradza dopiero komplet (mapa świata po „Użyj").
            "region": r["region"],
        }
        if complete and r["state"] == "buried":
            entry["hex"] = {"q": int(r["hex_q"]), "r": int(r["hex_r"])}
            # distance from the hero's position — the map view centres on the
            # treasure, so without this the goal can look deceptively close.
            cur = _current_hex(conn, int(r["campaign_id"] or 0))
            if cur is not None:
                entry["distance_hexes"] = _hexdist(
                    cur, (int(r["hex_q"]), int(r["hex_r"]))
                )
        maps.append(entry)
    return {"maps": maps}


def get_treasure_hexes_for_map(conn: sqlite3.Connection, character_id: int) -> list[dict]:
    """Hexes to mark with ✕ on the player world map: buried, complete maps."""
    try:
        rows = conn.execute(
            """
            SELECT wt.hex_q, wt.hex_r FROM world_treasures wt
            WHERE wt.character_id = ? AND wt.state = 'buried'
              AND (SELECT COUNT(*) FROM character_map_fragments f
                   WHERE f.treasure_id = wt.id AND f.character_id = ?) >= wt.total_parts
            """,
            (character_id, character_id),
        ).fetchall()
    except sqlite3.OperationalError:
        return []
    return [{"q": int(r["hex_q"]), "r": int(r["hex_r"])} for r in rows]


# ---------------------------------------------------------------------------
# Arrival hint + dig flow
# ---------------------------------------------------------------------------

def _complete_treasure_at(conn: sqlite3.Connection, character_id: int,
                          q: int, r: int) -> Optional[sqlite3.Row]:
    """A buried, fully-collected treasure of this hero sitting on (q,r)."""
    try:
        return conn.execute(
            """
            SELECT wt.* FROM world_treasures wt
            WHERE wt.character_id = ? AND wt.state = 'buried'
              AND wt.hex_q = ? AND wt.hex_r = ? AND wt.map_level = 0
              AND (SELECT COUNT(*) FROM character_map_fragments f
                   WHERE f.treasure_id = wt.id AND f.character_id = wt.character_id) >= wt.total_parts
            LIMIT 1
            """,
            (character_id, q, r),
        ).fetchone()
    except sqlite3.OperationalError:
        return None


def maybe_treasure_arrival_hint(conn: sqlite3.Connection, campaign_id: int,
                                character_id: int, q: int, r: int) -> Optional[str]:
    """Narrator hint when the hero arrives on a hex holding their treasure (D3)."""
    t = _complete_treasure_at(conn, character_id, q, r)
    if not t:
        return None
    return (
        "[WSKAZÓWKA MG] Wedle mapy skarbu bohatera właśnie w tym miejscu ukryto "
        "skrytkę. Poprowadź scenę tak, by bohater mógł jej poszukać — opisz "
        "podejrzane ślady, kopiec, stary głaz — ale NIE ujawniaj wprost, gdzie "
        "dokładnie kopać. Skarb odsłoni się dopiero, gdy gracz zacznie szukać."
    )


def maybe_treasure_arrival_cue(conn: sqlite3.Connection, campaign_id: int,
                               character_id: int, q: int, r: int) -> Optional[str]:
    """Player-facing cue appended on arriving at a hex holding their treasure (D3).
    Nudges the player to search without revealing the exact spot."""
    t = _complete_treasure_at(conn, character_id, q, r)
    if not t:
        return None
    return ("*Wyjmujesz mapę — znak ✕ wypada właśnie tutaj. Gdzieś w pobliżu "
            "ukryto skrytkę. Rozejrzyj się i zacznij kopać albo przeszukiwać teren.*")


def attempt_dig(conn: sqlite3.Connection, campaign_id: int, character_id: int) -> dict:
    """Deterministic dig attempt (D4). Returns eligibility / a pending skill test."""
    cur = _current_hex(conn, campaign_id)
    if not cur:
        return {"eligible": False, "reason": "no_position"}
    t = _complete_treasure_at(conn, character_id, cur[0], cur[1])
    if not t:
        return {"eligible": False, "reason": "no_treasure_here"}
    return {
        "eligible": True,
        "treasure_id": int(t["id"]),
        "dc": int(t["dc"] or DEFAULT_DIG_DC),
        "skill_key": DIG_SKILL_KEY,
    }


def resolve_dig_success(conn: sqlite3.Connection, campaign_id: int,
                        character_id: int, treasure_id: int) -> dict:
    """After a successful search test: guardian fight or immediate payout."""
    t = conn.execute(
        "SELECT * FROM world_treasures WHERE id = ? AND state = 'buried'",
        (treasure_id,),
    ).fetchone()
    if not t:
        return {"resolved": False, "reason": "gone"}
    guardian = t["guardian_enemy_key"]
    if guardian:
        try:
            from app.services import combat_service
            combat_service.initiate_combat(campaign_id, character_id, [str(guardian)])
            # mark payout pending on victory
            _set_pending_treasure_loot(conn, campaign_id, treasure_id)
            conn.commit()
            return {"resolved": True, "guardian": str(guardian), "combat": True,
                    "treasure_id": treasure_id}
        except Exception as e:
            logger.warning("treasure_guardian_spawn_failed", error=str(e))
            # fall through to direct payout so the treasure is never stuck
    return _payout(conn, campaign_id, character_id, treasure_id)


def _set_pending_treasure_loot(conn: sqlite3.Connection, campaign_id: int,
                               treasure_id: int) -> None:
    row = conn.execute(
        "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
        (campaign_id,),
    ).fetchone()
    try:
        flags = json.loads(row["session_flags"]) if row and row["session_flags"] else {}
    except (TypeError, ValueError):
        flags = {}
    flags["pending_treasure_loot"] = {"treasure_id": int(treasure_id)}
    conn.execute(
        "UPDATE game_sessions SET session_flags = ? WHERE campaign_id = ?",
        (json.dumps(flags), campaign_id),
    )


def consume_pending_treasure_loot(conn: sqlite3.Connection, campaign_id: int,
                                  character_id: int) -> Optional[dict]:
    """Called when a combat ends in victory — pay out a treasure guarded fight."""
    row = conn.execute(
        "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
        (campaign_id,),
    ).fetchone()
    if not row or not row["session_flags"]:
        return None
    try:
        flags = json.loads(row["session_flags"])
    except (TypeError, ValueError):
        return None
    pend = flags.get("pending_treasure_loot")
    if not isinstance(pend, dict) or not pend.get("treasure_id"):
        return None
    tid = int(pend["treasure_id"])
    del flags["pending_treasure_loot"]
    conn.execute(
        "UPDATE game_sessions SET session_flags = ? WHERE campaign_id = ?",
        (json.dumps(flags), campaign_id),
    )
    return _payout(conn, campaign_id, character_id, tid)


def _payout(conn: sqlite3.Connection, campaign_id: int, character_id: int,
            treasure_id: int) -> dict:
    """Grant the frozen loot snapshot, mark found, confirm rumors."""
    t = conn.execute(
        "SELECT * FROM world_treasures WHERE id = ? AND state = 'buried'",
        (treasure_id,),
    ).fetchone()
    if not t:
        return {"resolved": False, "reason": "gone"}
    try:
        loot = json.loads(t["loot_snapshot_json"]) if t["loot_snapshot_json"] else []
    except (TypeError, ValueError):
        loot = []
    gold = int(t["gold_snapshot"] or 0) + int(t["gold_bonus"] or 0)

    granted: list[dict] = []
    if loot:
        try:
            from app.services import loot_service
            granted = loot_service.grant_loot_to_character(
                character_id, loot, source="treasure"
            )
        except Exception as e:
            logger.warning("treasure_payout_grant_failed", error=str(e))
    if gold > 0:
        try:
            conn.execute(
                "UPDATE characters SET gold = COALESCE(gold, 0) + ? WHERE id = ?",
                (gold, character_id),
            )
        except sqlite3.OperationalError:
            pass

    conn.execute(
        "UPDATE world_treasures SET state = 'found', found_at = ?, "
        "found_by_character_id = ? WHERE id = ?",
        (_now_iso(), character_id, treasure_id),
    )
    # confirm any treasure_site rumors pointing at this treasure
    try:
        from app.services import rumor_service
        rumor_service.confirm_rumors_for(campaign_id, "treasure_site", str(treasure_id), conn)
    except Exception:
        pass
    conn.commit()
    return {
        "resolved": True,
        "treasure_id": treasure_id,
        "gold": gold,
        "items": granted,
        "map_label": t["label"] or "Mapa skarbu",
    }
