"""
Character XP pool and skill / stat purchases (**[S10]**, **T21**).

- `sheet_json.xp_available`, `sheet_json.xp_lifetime_earned`
- Skill ranks — `game_config_meta.xp_skill_rank_costs`: {"1":100,"2":75,"3":150}
  (XP to reach rank N from rank N-1; game_mechanics.md).
- Stat bumps — `game_config_meta.xp_stat_point_costs`: {"11":50,...}
  (XP to raise a stat **to** value N from N-1). Optional ceiling:
  `xp_stat_value_ceiling` (default **19** — 19+ = Niedostępne, game_mechanics.md; #1164).
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from app.services import config_service
from app.services.dice import DICE_TEST_TO_CONFIG_SKILL_KEY, parse_character_sheet

DB_PATH = "/data/ai_gm.db"

DEFAULT_RANK_UP_COSTS: dict[int, int] = {
    1: 50,
    2: 100,
    3: 200,
    4: 400,
    5: 1200,
}

# New stat value (after +1) → XP cost per game_mechanics.md CZĘŚĆ 7.
# Ranges: current 8-10 → 50, 11-13 → 100, 14-16 → 200, 17-18 → 400; 19+ = ceiling.
DEFAULT_STAT_POINT_COSTS: dict[int, int] = {
    9: 50,    # current 8→9
    10: 50,   # current 9→10
    11: 50,   # current 10→11
    12: 100,  # current 11→12
    13: 100,  # current 12→13
    14: 100,  # current 13→14
    15: 200,  # current 14→15
    16: 200,  # current 15→16
    17: 200,  # current 16→17
    18: 400,  # current 17→18
    19: 400,  # current 18→19
}

# game_mechanics.md: current 19+ = "Niedostępne" → ceiling at 19.
DEFAULT_STAT_VALUE_CEILING = 19

# F18 (#478): non-linear XP thresholds. Keys are level numbers (as strings),
# values are cumulative lifetime XP needed to reach that level.
DEFAULT_XP_LEVEL_THRESHOLDS: dict[str, int] = {
    "2": 100,
    "3": 250,
    "4": 450,
    "5": 700,
    "6": 1000,
    "7": 1350,
    "8": 1750,
    "9": 2200,
    "10": 2700,
}


def get_xp_level_thresholds(conn: sqlite3.Connection) -> dict[str, int]:
    """Load XP level thresholds from game_config_meta or return defaults."""
    try:
        row = conn.execute(
            "SELECT value FROM game_config_meta WHERE key = 'xp_level_thresholds' LIMIT 1"
        ).fetchone()
    except Exception:
        return dict(DEFAULT_XP_LEVEL_THRESHOLDS)
    if not row or not row[0]:
        return dict(DEFAULT_XP_LEVEL_THRESHOLDS)
    try:
        raw = json.loads(row[0])
        if isinstance(raw, dict) and raw:
            return {str(k): int(v) for k, v in raw.items()}
    except (json.JSONDecodeError, TypeError, ValueError):
        pass
    return dict(DEFAULT_XP_LEVEL_THRESHOLDS)


def level_from_xp(lifetime_xp: int, thresholds: dict | None) -> int:
    """Return character level based on lifetime XP and threshold dict.

    thresholds keys are level strings ("2", "3", ...), values are cumulative XP.
    Falls back to flat 100-XP-per-level when thresholds is None or empty.
    Always returns at least 1 and caps at the highest defined level.
    """
    if not thresholds:
        # Backward-compat: flat 100 XP per level (old formula: 1 + floor(xp/100))
        return max(1, 1 + int(lifetime_xp) // 100)

    level = 1
    for level_str, required_xp in sorted(thresholds.items(), key=lambda x: int(x[0])):
        if int(lifetime_xp) >= int(required_xp):
            level = int(level_str)
        else:
            break
    return level


def _load_rank_costs(conn: sqlite3.Connection) -> dict[int, int]:
    row = conn.execute(
        "SELECT value FROM game_config_meta WHERE key = 'xp_skill_rank_costs' LIMIT 1"
    ).fetchone()
    if not row or row[0] is None or str(row[0]).strip() == "":
        return dict(DEFAULT_RANK_UP_COSTS)
    try:
        raw = json.loads(row[0])
    except (json.JSONDecodeError, TypeError):
        return dict(DEFAULT_RANK_UP_COSTS)
    if not isinstance(raw, dict):
        return dict(DEFAULT_RANK_UP_COSTS)
    out: dict[int, int] = {}
    for k, v in raw.items():
        try:
            out[int(k)] = int(v)
        except (TypeError, ValueError):
            continue
    return out if out else dict(DEFAULT_RANK_UP_COSTS)


def _load_stat_point_costs(conn: sqlite3.Connection) -> dict[int, int]:
    row = conn.execute(
        "SELECT value FROM game_config_meta WHERE key = 'xp_stat_point_costs' LIMIT 1"
    ).fetchone()
    base = dict(DEFAULT_STAT_POINT_COSTS)
    if not row or row[0] is None or str(row[0]).strip() == "":
        return base
    try:
        raw = json.loads(row[0])
    except (json.JSONDecodeError, TypeError):
        return base
    if not isinstance(raw, dict):
        return base
    for k, v in raw.items():
        try:
            base[int(k)] = int(v)
        except (TypeError, ValueError):
            continue
    return base


def _stat_value_ceiling(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        "SELECT value FROM game_config_meta WHERE key = 'xp_stat_value_ceiling' LIMIT 1"
    ).fetchone()
    if not row or row[0] is None or str(row[0]).strip() == "":
        return DEFAULT_STAT_VALUE_CEILING
    try:
        v = int(str(row[0]).strip())
        return max(3, min(99, v))
    except (TypeError, ValueError):
        return DEFAULT_STAT_VALUE_CEILING


def _cost_for_stat_target(costs: dict[int, int], new_value: int) -> int:
    if new_value in costs and int(costs[new_value]) > 0:
        return int(costs[new_value])
    if new_value in DEFAULT_STAT_POINT_COSTS:
        return int(DEFAULT_STAT_POINT_COSTS[new_value])
    # Fallback: nearest lower defined tier, scaled up (rough continuity).
    keys = sorted(costs.keys())
    if not keys:
        return int(DEFAULT_STAT_POINT_COSTS.get(new_value, 999999))
    lower = [k for k in keys if k < new_value]
    if not lower:
        return int(costs.get(keys[0], 999999))
    k0 = max(lower)
    base_cost = int(costs[k0])
    steps = new_value - k0
    c = base_cost
    for _ in range(steps):
        c = int(c * 1.35) + 25
    return c


def _stat_known_in_catalog(conn: sqlite3.Connection, stat_key: str) -> bool:
    sk = (stat_key or "").strip()
    if not sk:
        return False
    row = conn.execute(
        "SELECT key FROM game_config_stats WHERE UPPER(key) = UPPER(?) LIMIT 1", (sk,)
    ).fetchone()
    return row is not None


def _rank_ceiling_for_skill(skill_key: str) -> int:
    keys_to_try = [skill_key]
    alt = DICE_TEST_TO_CONFIG_SKILL_KEY.get(skill_key)
    if alt and alt not in keys_to_try:
        keys_to_try.append(alt)
    try:
        conn = sqlite3.connect(DB_PATH)
        try:
            for lk in keys_to_try:
                row = conn.execute(
                    "SELECT rank_ceiling FROM game_config_skills WHERE key = ?", (lk,)
                ).fetchone()
                if row is not None:
                    return int(row[0] or 5)
        finally:
            conn.close()
    except Exception:
        pass
    return 5


def _skill_known_in_catalog(skill_key: str) -> bool:
    cfg = config_service.get_runtime_config()
    keys = {
        str(s.get("key"))
        for s in (cfg.get("skills") or [])
        if isinstance(s, dict) and s.get("key")
    }
    # Strict check — no alias expansion. Legacy dice-test names (melee_attack etc.)
    # must be rejected here so they can't be accidentally re-added via XP spend (#1052).
    return skill_key in keys


CATCHUP_XP_MULTIPLIER = 1.5  # G26 #807: starting value, tune after playtest


def _apply_catchup_multiplier(
    conn: sqlite3.Connection, character_id: int, campaign_id: int, amount: int
) -> int:
    """G26 #807 — ×1.5 XP for players lagging below party max-1 level in MP campaigns."""
    try:
        party_rows = conn.execute(
            "SELECT id, sheet_json FROM characters WHERE campaign_id = ? AND is_active = 1",
            (campaign_id,),
        ).fetchall()
        if len(party_rows) < 2:
            return amount
        levels = []
        char_level = 1
        for row in party_rows:
            sheet = json.loads(row["sheet_json"] or "{}")
            lvl = max(1, int(sheet.get("level") or 1))
            levels.append(lvl)
            if row["id"] == character_id:
                char_level = lvl
        catchup_threshold = max(1, max(levels) - 1)
        if char_level < catchup_threshold:
            return round(amount * CATCHUP_XP_MULTIPLIER)
        return amount
    except Exception:
        return amount


def grant_pending_xp(
    conn: sqlite3.Connection,
    character_id: int,
    campaign_id: int,
    amount: int,
    *,
    reason: str,
    source: str,
    source_key: str = "",
    turn_number: int | None = None,
) -> dict[str, Any]:
    """Stage 2D — grant XP to pending_xp (not yet spendable; flushed on long rest).

    Also increments xp_lifetime_earned for level calculations and writes an
    audit row to character_xp_grants.
    G26 #807: applies catch-up ×1.5 multiplier for lagging players in MP campaigns.
    """
    if amount <= 0:
        return {"granted": 0}

    row = conn.execute(
        "SELECT sheet_json FROM characters WHERE id = ?", (character_id,)
    ).fetchone()
    if not row:
        return {"granted": 0}

    amount = _apply_catchup_multiplier(conn, character_id, campaign_id, amount)

    sheet = parse_character_sheet(row["sheet_json"])
    pending = int(sheet.get("pending_xp") or 0) + amount
    lifetime = int(sheet.get("xp_lifetime_earned") or 0) + amount
    sheet["pending_xp"] = pending
    sheet["xp_lifetime_earned"] = lifetime

    conn.execute(
        "UPDATE characters SET sheet_json = ? WHERE id = ?",
        (json.dumps(sheet, ensure_ascii=False), character_id),
    )
    try:
        conn.execute(
            "INSERT INTO character_xp_grants "
            "(character_id, campaign_id, amount, reason, source, source_key, turn_number, granted_by_user_id) "
            "VALUES (?,?,?,?,?,?,?,0)",
            (character_id, campaign_id, amount, reason, source, source_key or "", turn_number),
        )
    except Exception:
        pass  # audit row is best-effort
    return {"granted": amount, "pending_xp": pending, "xp_lifetime_earned": lifetime}


def grant_character_xp(
    conn: sqlite3.Connection,
    character_id: int,
    amount: int,
    *,
    reason: str,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if amount <= 0:
        row = conn.execute(
            "SELECT sheet_json FROM characters WHERE id = ?",
            (character_id,),
        ).fetchone()
        if not row:
            raise ValueError("character not found")
        sheet = parse_character_sheet(row["sheet_json"])
        return {
            "granted": 0,
            "xp_available": int(sheet.get("xp_available") or 0),
            "xp_lifetime_earned": int(sheet.get("xp_lifetime_earned") or 0),
        }

    row = conn.execute(
        "SELECT sheet_json FROM characters WHERE id = ?",
        (character_id,),
    ).fetchone()
    if not row:
        raise ValueError("character not found")

    sheet = parse_character_sheet(row["sheet_json"])
    cur = int(sheet.get("xp_available") or 0)
    life = int(sheet.get("xp_lifetime_earned") or 0)
    amt = int(amount)
    cur += amt
    life += amt
    sheet["xp_available"] = cur
    sheet["xp_lifetime_earned"] = life

    conn.execute(
        "UPDATE characters SET sheet_json = ? WHERE id = ?",
        (json.dumps(sheet, ensure_ascii=False), character_id),
    )
    out = {
        "granted": amt,
        "xp_available": cur,
        "xp_lifetime_earned": life,
        "reason": reason,
    }
    if meta:
        out["meta"] = meta
    return out


def spend_skill_rank_up(
    conn: sqlite3.Connection,
    character_id: int,
    skill_key: str,
) -> dict[str, Any]:
    sk = (skill_key or "").strip().lower()
    if not sk:
        raise ValueError("skill_key_required")

    if not _skill_known_in_catalog(sk):
        raise ValueError("unknown_skill")

    row = conn.execute(
        "SELECT sheet_json FROM characters WHERE id = ?",
        (character_id,),
    ).fetchone()
    if not row:
        raise ValueError("character not found")

    sheet = parse_character_sheet(row["sheet_json"])
    skills = dict(sheet.get("skills") or {})
    current = int(skills.get(sk, 0) or 0)
    ceiling = _rank_ceiling_for_skill(sk)
    if current >= ceiling:
        raise ValueError("skill_at_ceiling")

    new_rank = current + 1
    costs = _load_rank_costs(conn)
    cost = int(costs.get(new_rank, 0))
    if cost <= 0:
        cost = int(DEFAULT_RANK_UP_COSTS.get(new_rank, 999999))

    xp = int(sheet.get("xp_available") or 0)
    if xp < cost:
        raise ValueError("insufficient_xp")

    skills[sk] = new_rank
    sheet["skills"] = skills
    sheet["xp_available"] = xp - cost

    conn.execute(
        "UPDATE characters SET sheet_json = ? WHERE id = ?",
        (json.dumps(sheet, ensure_ascii=False), character_id),
    )

    return {
        "skill_key": sk,
        "previous_rank": current,
        "new_rank": new_rank,
        "xp_spent": cost,
        "xp_available": int(sheet["xp_available"]),
        "rank_ceiling": ceiling,
    }


def spend_stat_point_up(
    conn: sqlite3.Connection,
    character_id: int,
    stat_key: str,
) -> dict[str, Any]:
    """Raise one configured core stat by 1; cost from meta `xp_stat_point_costs` (**T21**)."""
    raw_key = (stat_key or "").strip()
    if not raw_key:
        raise ValueError("stat_key_required")

    if not _stat_known_in_catalog(conn, raw_key):
        raise ValueError("unknown_stat")

    row = conn.execute(
        "SELECT sheet_json FROM characters WHERE id = ?",
        (character_id,),
    ).fetchone()
    if not row:
        raise ValueError("character not found")

    ceiling = _stat_value_ceiling(conn)
    costs = _load_stat_point_costs(conn)

    sheet = parse_character_sheet(row["sheet_json"])
    stats = dict(sheet.get("stats") or {})
    # Find canonical key (sheet may use STR/str/Str — match case-insensitively)
    sk = raw_key
    for k in stats:
        if k.upper() == raw_key.upper():
            sk = k
            break
    current = int(stats.get(sk, 10) or 10)
    if current >= ceiling:
        raise ValueError("stat_at_ceiling")

    new_value = current + 1
    if new_value > ceiling:
        raise ValueError("stat_at_ceiling")

    cost = _cost_for_stat_target(costs, new_value)
    if cost <= 0:
        raise ValueError("stat_cost_not_configured")

    xp = int(sheet.get("xp_available") or 0)
    if xp < cost:
        raise ValueError("insufficient_xp")

    stats[sk] = new_value
    sheet["stats"] = stats
    sheet["xp_available"] = xp - cost

    # CON change → recalculate hp_max: delta_mod × level
    if sk.upper() == "CON":
        level = int(sheet.get("level") or 1)
        old_mod = (current - 10) // 2
        new_mod = (new_value - 10) // 2
        delta = new_mod - old_mod
        if delta:
            old_max = int(sheet.get("max_hp") or 0)
            sheet["max_hp"] = old_max + delta * level

    conn.execute(
        "UPDATE characters SET sheet_json = ? WHERE id = ?",
        (json.dumps(sheet, ensure_ascii=False), character_id),
    )

    return {
        "stat_key": sk,
        "previous_value": current,
        "new_value": new_value,
        "xp_spent": cost,
        "xp_available": int(sheet["xp_available"]),
        "stat_value_ceiling": ceiling,
    }


def get_xp_snapshot(conn: sqlite3.Connection, character_id: int) -> dict[str, Any]:
    row = conn.execute(
        "SELECT sheet_json FROM characters WHERE id = ?",
        (character_id,),
    ).fetchone()
    if not row:
        raise ValueError("character not found")
    sheet = parse_character_sheet(row["sheet_json"])
    costs = _load_rank_costs(conn)
    st_costs = _load_stat_point_costs(conn)
    st_ceil = _stat_value_ceiling(conn)
    # Read skill rank ceiling from DB (C7 migration set rank_ceiling=3 for all skills)
    sk_ceil_row = conn.execute(
        "SELECT MIN(rank_ceiling) FROM game_config_skills WHERE rank_ceiling > 0"
    ).fetchone()
    sk_ceil = int(sk_ceil_row[0] or 3) if sk_ceil_row and sk_ceil_row[0] else 3
    return {
        "xp_available": int(sheet.get("xp_available") or 0),
        "xp_lifetime_earned": int(sheet.get("xp_lifetime_earned") or 0),
        "rank_up_costs": {str(k): costs[k] for k in sorted(costs.keys())},
        "stat_point_costs": {str(k): st_costs[k] for k in sorted(st_costs.keys())},
        "stat_value_ceiling": st_ceil,
        "skill_rank_ceiling": sk_ceil,
    }


def fetch_character_campaign_owner(conn: sqlite3.Connection, character_id: int) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT c.id AS character_id, c.campaign_id, camp.owner_user_id
        FROM characters c
        JOIN campaigns camp ON camp.id = c.campaign_id
        WHERE c.id = ?
        """,
        (character_id,),
    ).fetchone()
    return dict(row) if row else None


def insert_mg_xp_grant_audit(
    conn: sqlite3.Connection,
    *,
    character_id: int,
    campaign_id: int,
    amount: int,
    reason: str,
    granted_by_user_id: int,
    meta: dict[str, Any] | None = None,
) -> int:
    """Append row to `character_xp_grants` (**[S10d]**)."""
    cur = conn.execute(
        """
        INSERT INTO character_xp_grants (
            character_id, campaign_id, amount, reason, source, granted_by_user_id, meta_json
        ) VALUES (?, ?, ?, ?, 'mg_manual', ?, ?)
        """,
        (
            character_id,
            campaign_id,
            amount,
            (reason or "").strip(),
            granted_by_user_id,
            json.dumps(meta or {}, ensure_ascii=False),
        ),
    )
    return int(cur.lastrowid or 0)


def _normalize_enemy_tier(tier: str | None) -> str:
    t = (tier or "standard").strip().lower()
    if t in ("weak", "standard", "elite", "boss"):
        return t
    return "standard"


def enemy_tier_reward_key(tier: str | None) -> str:
    """Klucz wiersza `game_config_xp_rewards` dla poziomu zagrożenia wroga ([T12])."""
    return f"enemy_tier_{_normalize_enemy_tier(tier)}"


def get_xp_reward_amount(conn: sqlite3.Connection, key: str) -> int | None:
    """Aktywny wpis `game_config_xp_rewards` po `key` ([S10e] / T12)."""
    k = (key or "").strip()
    if not k:
        return None
    try:
        row = conn.execute(
            """
            SELECT xp_amount FROM game_config_xp_rewards
            WHERE key = ? AND is_active = 1
            LIMIT 1
            """,
            (k,),
        ).fetchone()
    except sqlite3.OperationalError:
        return None
    if not row:
        return None
    try:
        return int(row["xp_amount"] if hasattr(row, "keys") else row[0])
    except (TypeError, ValueError):
        return None


def require_xp_reward_amount(conn: sqlite3.Connection, key: str) -> int:
    amt = get_xp_reward_amount(conn, key)
    if amt is None or amt < 1:
        raise ValueError("unknown_or_inactive_xp_reward_key")
    return amt


def resolve_enemy_defeat_xp_amount(
    conn: sqlite3.Connection,
    *,
    catalog_xp_award: int,
    tier: str | None,
) -> tuple[int, str]:
    """
    Zwraca (punkty XP, źródło).
    Priorytet: jawne `game_config_enemies.xp_award` > 0, inaczej tabela `game_config_xp_rewards` wg `tier`.
    """
    try:
        explicit = int(catalog_xp_award or 0)
    except (TypeError, ValueError):
        explicit = 0
    if explicit > 0:
        return explicit, "enemy_xp_award"
    rk = enemy_tier_reward_key(tier)
    amt = get_xp_reward_amount(conn, rk)
    if amt is not None and amt > 0:
        return amt, "xp_reward_table"
    return 0, "none"


def list_xp_rewards_for_categories(
    conn: sqlite3.Connection, categories: list[str]
) -> list[dict[str, Any]]:
    """Odczyt katalogu nagród (np. grant MG — kategorie `mg_grant`, `quest`)."""
    cats = [c.strip() for c in categories if c and str(c).strip()]
    if not cats:
        return []
    placeholders = ",".join("?" * len(cats))
    try:
        rows = conn.execute(
            f"""
            SELECT key, category, label, description, xp_amount, sort_order
            FROM game_config_xp_rewards
            WHERE is_active = 1 AND category IN ({placeholders})
            ORDER BY category ASC, sort_order ASC, key ASC
            """,
            tuple(cats),
        ).fetchall()
    except sqlite3.OperationalError:
        return []
    return [dict(r) for r in rows]


def list_xp_grants_for_character(
    conn: sqlite3.Connection, character_id: int, *, limit: int = 50
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT id, character_id, campaign_id, amount, reason, source,
               granted_by_user_id, meta_json, created_at
        FROM character_xp_grants
        WHERE character_id = ?
        ORDER BY id DESC
        LIMIT ?
        """,
        (character_id, max(1, min(limit, 200))),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        meta_raw = d.get("meta_json")
        if meta_raw:
            try:
                d["meta"] = json.loads(meta_raw)
            except (json.JSONDecodeError, TypeError):
                d["meta"] = {}
        else:
            d["meta"] = {}
        del d["meta_json"]
        out.append(d)
    return out
