"""
Character XP pool and skill rank purchases (**[S10]**).

- `sheet_json.xp_available`, `sheet_json.xp_lifetime_earned`
- Costs: `game_config_meta.xp_skill_rank_costs` JSON object: {"1":50,"2":100,...}
  meaning XP to reach rank N from rank N-1.
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


def _rank_ceiling_for_skill(skill_key: str) -> int:
    cfg = config_service.get_runtime_config()
    skills_list = cfg.get("skills") if isinstance(cfg.get("skills"), list) else []
    keys_to_try = [skill_key]
    alt = DICE_TEST_TO_CONFIG_SKILL_KEY.get(skill_key)
    if alt and alt not in keys_to_try:
        keys_to_try.append(alt)
    for lk in keys_to_try:
        for s in skills_list:
            if isinstance(s, dict) and s.get("key") == lk:
                return int(s.get("rank_ceiling") or 5)
    return 5


def _skill_known_in_catalog(skill_key: str) -> bool:
    cfg = config_service.get_runtime_config()
    keys = {
        str(s.get("key"))
        for s in (cfg.get("skills") or [])
        if isinstance(s, dict) and s.get("key")
    }
    if skill_key in keys:
        return True
    alt = DICE_TEST_TO_CONFIG_SKILL_KEY.get(skill_key)
    return bool(alt and alt in keys)


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


def get_xp_snapshot(conn: sqlite3.Connection, character_id: int) -> dict[str, Any]:
    row = conn.execute(
        "SELECT sheet_json FROM characters WHERE id = ?",
        (character_id,),
    ).fetchone()
    if not row:
        raise ValueError("character not found")
    sheet = parse_character_sheet(row["sheet_json"])
    costs = _load_rank_costs(conn)
    return {
        "xp_available": int(sheet.get("xp_available") or 0),
        "xp_lifetime_earned": int(sheet.get("xp_lifetime_earned") or 0),
        "rank_up_costs": {str(k): costs[k] for k in sorted(costs.keys())},
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
