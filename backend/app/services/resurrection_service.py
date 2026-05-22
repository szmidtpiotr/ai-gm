"""
Resurrection Service — Stage 11 (issue #64)

Server-side enforcement of hero resurrection from a dead state.

Each user has a per-account config (resurrection_enabled + cost mode + params)
set by an admin in the Players panel. When a player dies and tries to revive,
the configured cost is computed and applied here. Admins can force a free
resurrect via the dedicated admin endpoint.

Cost modes
----------
xp_revert         — claw back the last N XP grants until ≥ cost_value XP is
                    reverted; recompute level; revoke any skill ranks /
                    spells / arcane-point spends made above the new level.
gold_percent      — lose cost_value % of current gold.
gold_recent_days  — sum gold *gains* in the last cost_value game days, then
                    lose min(that_sum, current_gold * cap_percent / 100).
                    Only positive deltas counted; expenses are not charged.
item_loss         — remove one randomly chosen equipped functional item
                    (weapon / armor with DR>0 / consumable with effect_json).
                    Quest-marked items excluded. If pool empty → free.
admin_free        — no cost (default for new accounts).

All modes share these post-revive effects:
- HP restored to max_hp // 2
- status flips 'dead' → 'active'
- death_saves_failed, short_rests_used reset to 0
- dungeon cooldowns wiped (character_dungeon_runs rows deleted)
- resurrection_uses_remaining decremented if not NULL
"""

from __future__ import annotations

import json
import random
import sqlite3
from typing import Any

import structlog

logger = structlog.get_logger()

VALID_MODES = (
    "xp_revert",
    "gold_percent",
    "gold_recent_days",
    "item_loss",
    "admin_free",
)


# ── Config helpers ────────────────────────────────────────────────────────


def get_user_resurrection_config(user_id: int, conn: sqlite3.Connection) -> dict[str, Any]:
    row = conn.execute(
        """
        SELECT
            COALESCE(resurrection_enabled, 0) AS enabled,
            COALESCE(resurrection_cost_mode, 'admin_free') AS mode,
            COALESCE(resurrection_cost_value, 25) AS value,
            COALESCE(resurrection_cost_cap_percent, 50) AS cap_percent,
            resurrection_uses_remaining AS uses_remaining
        FROM users WHERE id = ?
        """,
        (user_id,),
    ).fetchone()
    if not row:
        raise LookupError(f"User {user_id} not found")
    return {
        "enabled": bool(row["enabled"]),
        "mode": row["mode"],
        "value": int(row["value"]),
        "cap_percent": int(row["cap_percent"]),
        "uses_remaining": row["uses_remaining"],  # may be None = unlimited
    }


def set_user_resurrection_config(
    user_id: int,
    conn: sqlite3.Connection,
    *,
    enabled: bool | None = None,
    mode: str | None = None,
    value: int | None = None,
    cap_percent: int | None = None,
    uses_remaining: int | None | str = "__noop__",  # sentinel so None means "set to NULL"
) -> dict[str, Any]:
    if mode is not None and mode not in VALID_MODES:
        raise ValueError(f"Invalid mode '{mode}'. Allowed: {VALID_MODES}")
    sets: list[str] = []
    args: list[Any] = []
    if enabled is not None:
        sets.append("resurrection_enabled = ?")
        args.append(1 if enabled else 0)
    if mode is not None:
        sets.append("resurrection_cost_mode = ?")
        args.append(mode)
    if value is not None:
        sets.append("resurrection_cost_value = ?")
        args.append(int(value))
    if cap_percent is not None:
        sets.append("resurrection_cost_cap_percent = ?")
        args.append(max(0, min(100, int(cap_percent))))
    if uses_remaining != "__noop__":
        sets.append("resurrection_uses_remaining = ?")
        args.append(uses_remaining)
    if sets:
        args.append(user_id)
        conn.execute(f"UPDATE users SET {', '.join(sets)} WHERE id = ?", args)
        conn.commit()
    return get_user_resurrection_config(user_id, conn)


# ── Per-mode cost calculators ─────────────────────────────────────────────


def _get_current_gold(character_id: int, conn: sqlite3.Connection) -> int:
    """Canonical gold lives in characters.gold_gp."""
    row = conn.execute("SELECT gold_gp FROM characters WHERE id = ?", (character_id,)).fetchone()
    return int(row["gold_gp"] or 0) if row else 0


def _calc_cost_gold_percent(character_id: int, cfg: dict, conn: sqlite3.Connection) -> dict:
    cur_gold = _get_current_gold(character_id, conn)
    pct = max(0, min(100, cfg["value"]))
    lost = (cur_gold * pct) // 100
    return {"mode": "gold_percent", "gold_lost": lost, "percent": pct, "current_gold": cur_gold}


def _calc_cost_gold_recent_days(
    cfg: dict, character_id: int, current_day: int, conn: sqlite3.Connection
) -> dict:
    cur_gold = _get_current_gold(character_id, conn)
    window_days = max(1, cfg["value"])
    cap_pct = max(0, min(100, cfg["cap_percent"]))
    cutoff_day = current_day - window_days
    row = conn.execute(
        """
        SELECT COALESCE(SUM(delta), 0) AS gains
        FROM character_gold_log
        WHERE character_id = ?
          AND reverted_at IS NULL
          AND delta > 0
          AND game_clock_day > ?
        """,
        (character_id, cutoff_day),
    ).fetchone()
    recent_gains = int(row["gains"] if row else 0)
    cap = (cur_gold * cap_pct) // 100
    lost = min(recent_gains, cap)
    return {
        "mode": "gold_recent_days",
        "gold_lost": lost,
        "recent_gains_in_window": recent_gains,
        "cap": cap,
        "cap_percent": cap_pct,
        "window_days": window_days,
        "current_gold": cur_gold,
    }


def _calc_cost_xp_revert(
    cfg: dict, character_id: int, sheet: dict, conn: sqlite3.Connection
) -> dict:
    target_xp = max(1, cfg["value"])
    rows = conn.execute(
        """
        SELECT id, amount FROM character_xp_grants
        WHERE character_id = ?
          AND amount > 0
          AND reverted_at IS NULL
        ORDER BY id DESC
        """,
        (character_id,),
    ).fetchall()
    selected: list[int] = []
    reverted_amount = 0
    for r in rows:
        if reverted_amount >= target_xp:
            break
        selected.append(int(r["id"]))
        reverted_amount += int(r["amount"])
    return {
        "mode": "xp_revert",
        "xp_lost": reverted_amount,
        "target_xp": target_xp,
        "grant_ids_to_revert": selected,
        "grants_count": len(selected),
        "current_xp": int(sheet.get("xp") or 0),
    }


def _eligible_item_loss_pool(character_id: int, conn: sqlite3.Connection) -> list[dict]:
    """Equipped + has effect. Excludes quest-marked items.

    We treat 'functional' as: equipped in any anatomical slot AND either
    a weapon (any weapon is functional) OR armor with ac_bonus > 0 OR
    a consumable / item with non-empty effect_json. Cosmetic items and
    quest-marked rows are excluded.
    """
    # character_inventory uses (item_key | weapon_key | consumable_key) +
    # `equipped` boolean + `slot` text. is_quest_item lives in meta_json (if at all).
    rows = conn.execute(
        """
        SELECT ci.id AS inv_id, ci.item_key, ci.weapon_key, ci.consumable_key,
               ci.slot, ci.quantity, ci.meta_json,
               COALESCE(ci.label, w.label, i.label, c.label,
                        ci.weapon_key, ci.item_key, ci.consumable_key) AS label,
               CASE
                 WHEN ci.weapon_key IS NOT NULL THEN 'weapon'
                 WHEN ci.item_key IS NOT NULL THEN 'item'
                 WHEN ci.consumable_key IS NOT NULL THEN 'consumable'
                 ELSE 'unknown'
               END AS kind,
               i.effect_json AS item_effect,
               i.ac_bonus AS item_ac_bonus,
               c.effect_type AS cons_effect_type
        FROM character_inventory ci
        LEFT JOIN game_config_weapons w ON w.key = ci.weapon_key
        LEFT JOIN game_config_items i ON i.key = ci.item_key
        LEFT JOIN game_config_consumables c ON c.key = ci.consumable_key
        WHERE ci.character_id = ?
          AND ci.equipped = 1
          AND ci.slot IS NOT NULL
          AND ci.slot != ''
        """,
        (character_id,),
    ).fetchall()
    pool: list[dict] = []
    for r in rows:
        # Quest-marked items are flagged via meta_json — exclude them
        meta = r["meta_json"]
        if meta:
            try:
                if bool(json.loads(meta).get("is_quest_item")):
                    continue
            except Exception:
                pass
        kind = r["kind"]
        functional = False
        if kind == "weapon":
            functional = True
        elif kind == "item":
            functional = bool(r["item_effect"]) or int(r["item_ac_bonus"] or 0) > 0
        elif kind == "consumable":
            # Any non-empty effect_type means the consumable does something
            functional = bool(r["cons_effect_type"])
        if functional:
            pool.append({
                "inv_id": int(r["inv_id"]),
                "item_key": r["item_key"] or r["weapon_key"] or r["consumable_key"],
                "label": r["label"],
                "slot": r["slot"],
                "kind": kind,
            })
    return pool


def _calc_cost_item_loss(character_id: int, conn: sqlite3.Connection) -> dict:
    pool = _eligible_item_loss_pool(character_id, conn)
    return {
        "mode": "item_loss",
        "eligible_count": len(pool),
        "eligible_items": [{"label": p["label"], "slot": p["slot"]} for p in pool],
        "fallback_to_free": len(pool) == 0,
    }


# ── Public preview ────────────────────────────────────────────────────────


def cost_preview(
    character_id: int, user_id: int, conn: sqlite3.Connection
) -> dict[str, Any]:
    """Compute the cost of resurrecting without applying it.

    Returns a structured dict the frontend renders into the confirmation modal.
    """
    cfg = get_user_resurrection_config(user_id, conn)
    char = conn.execute(
        "SELECT id, campaign_id, sheet_json, status FROM characters WHERE id = ?",
        (character_id,),
    ).fetchone()
    if not char:
        raise LookupError(f"Character {character_id} not found")
    sheet = json.loads(char["sheet_json"] or "{}")

    if not cfg["enabled"]:
        return {"enabled": False, "reason": "resurrection_disabled_for_user", "config": cfg}
    if cfg["uses_remaining"] is not None and int(cfg["uses_remaining"]) <= 0:
        return {"enabled": False, "reason": "no_uses_remaining", "config": cfg}

    mode = cfg["mode"]
    if mode == "admin_free":
        cost = {"mode": "admin_free", "free": True}
    elif mode == "gold_percent":
        cost = _calc_cost_gold_percent(character_id, cfg, conn)
    elif mode == "gold_recent_days":
        from app.services.clock_service import get_clock_state
        day = int(get_clock_state(int(char["campaign_id"]), conn=conn)["day"]) if char["campaign_id"] else 1
        cost = _calc_cost_gold_recent_days(cfg, character_id, day, conn)
    elif mode == "xp_revert":
        cost = _calc_cost_xp_revert(cfg, character_id, sheet, conn)
    elif mode == "item_loss":
        cost = _calc_cost_item_loss(character_id, conn)
    else:
        raise ValueError(f"Unknown cost mode: {mode}")

    return {"enabled": True, "config": cfg, "cost": cost}


# ── Apply ─────────────────────────────────────────────────────────────────


def _apply_xp_revert(
    character_id: int, sheet: dict, grant_ids: list[int], reverted_amount: int,
    conn: sqlite3.Connection
) -> dict:
    """Mark grants as reverted, subtract XP, recompute level, revoke purchases.

    Purchases revoked: any character_spells row with `purchased_after_xp_total`
    > the new total. We also reset arcane_points_spent_after to match.
    """
    if not grant_ids:
        return {"xp_subtracted": 0, "new_level": int(sheet.get("level") or 1), "revoked": {}}

    placeholders = ",".join("?" * len(grant_ids))
    conn.execute(
        f"UPDATE character_xp_grants SET reverted_at = datetime('now') WHERE id IN ({placeholders})",
        grant_ids,
    )

    old_xp = int(sheet.get("xp") or 0)
    new_xp = max(0, old_xp - reverted_amount)
    sheet["xp"] = new_xp

    # Recompute level — simple curve: level = 1 + floor(xp / 100)
    old_level = int(sheet.get("level") or 1)
    new_level = max(1, 1 + (new_xp // 100))
    level_dropped = max(0, old_level - new_level)
    sheet["level"] = new_level

    # Recompute max_hp at the new level (archetype_base + CON_mod × level)
    try:
        from app.services.vitality_service import calculate_hp, calculate_mana
        arc = str(sheet.get("archetype") or "warrior")
        stats = sheet.get("stats") or {}
        con = int(stats.get("CON") or stats.get("con") or 10)
        int_stat = int(stats.get("INT") or stats.get("int") or 10)
        sheet["max_hp"] = calculate_hp(arc, con, new_level)
        sheet["max_mana"] = calculate_mana(arc, int_stat, new_level)
    except Exception as e:
        logger.warning("recompute_max_hp_failed", error=str(e))

    revoked: dict[str, Any] = {"levels_lost": level_dropped}

    # Revoke spells / skill ranks bought above the new level.
    # Skill ranks are stored in sheet.skills as dicts {rank: N}. We can't track
    # per-rank purchase history retroactively without a journal, so for now we
    # clamp every skill rank to <= new_level (since you can buy at most 1 rank
    # per level for free advancement). This is a coarse but safe rollback.
    skills_revoked: list[dict] = []
    skills = sheet.get("skills") or {}
    if isinstance(skills, dict):
        for skill_key, sk_data in list(skills.items()):
            if not isinstance(sk_data, dict):
                continue
            cur_rank = int(sk_data.get("rank") or 0)
            if cur_rank > new_level:
                skills_revoked.append({"skill": skill_key, "old_rank": cur_rank, "new_rank": new_level})
                sk_data["rank"] = new_level
    revoked["skills"] = skills_revoked

    # Spells: remove character_spells rows that have learned_at_level > new_level.
    try:
        spell_rows = conn.execute(
            """
            SELECT id, spell_key, rank, learned_at_level
            FROM character_spells
            WHERE character_id = ?
            """,
            (character_id,),
        ).fetchall()
        spells_revoked = []
        for sr in spell_rows:
            if sr["learned_at_level"] is not None and int(sr["learned_at_level"]) > new_level:
                spells_revoked.append({"spell": sr["spell_key"], "learned_at": int(sr["learned_at_level"])})
                conn.execute("DELETE FROM character_spells WHERE id = ?", (sr["id"],))
        revoked["spells"] = spells_revoked
    except sqlite3.OperationalError:
        # character_spells table may not exist on bare-bones test DBs
        revoked["spells"] = []

    return {
        "xp_subtracted": reverted_amount,
        "new_xp": new_xp,
        "new_level": new_level,
        "old_level": old_level,
        "revoked": revoked,
    }


def _apply_gold_loss(
    character_id: int, amount: int, source: str,
    current_day: int, conn: sqlite3.Connection
) -> int:
    """Subtract `amount` from characters.gold_gp and journal it. Returns actual lost."""
    cur = _get_current_gold(character_id, conn)
    lost = max(0, min(cur, amount))
    if lost == 0:
        return 0
    conn.execute(
        "UPDATE characters SET gold_gp = gold_gp - ? WHERE id = ?",
        (lost, character_id),
    )
    conn.execute(
        """
        INSERT INTO character_gold_log
            (character_id, delta, source, game_clock_day, meta_json)
        VALUES (?, ?, ?, ?, ?)
        """,
        (character_id, -lost, source, current_day, json.dumps({"resurrection": True})),
    )
    return lost


def _apply_item_loss(
    character_id: int, conn: sqlite3.Connection
) -> dict | None:
    """Pick one functional item at random and remove it. Returns the lost item or None."""
    pool = _eligible_item_loss_pool(character_id, conn)
    if not pool:
        return None
    pick = random.choice(pool)
    # Column is `quantity`, not `qty`
    row = conn.execute(
        "SELECT quantity FROM character_inventory WHERE id = ?",
        (pick["inv_id"],),
    ).fetchone()
    qty = int(row["quantity"] if row else 1)
    if qty <= 1:
        conn.execute("DELETE FROM character_inventory WHERE id = ?", (pick["inv_id"],))
    else:
        conn.execute(
            "UPDATE character_inventory SET quantity = quantity - 1 WHERE id = ?",
            (pick["inv_id"],),
        )
    return pick


def apply_resurrection(
    character_id: int,
    user_id: int,
    conn: sqlite3.Connection,
    *,
    force: bool = False,
) -> dict[str, Any]:
    """Run the configured cost mode (or free if force=True) and revive the hero.

    Raises:
        PermissionError if disabled and not force
        RuntimeError    if no uses remaining and not force
    """
    cfg = get_user_resurrection_config(user_id, conn)
    char = conn.execute(
        "SELECT id, campaign_id, sheet_json, status FROM characters WHERE id = ?",
        (character_id,),
    ).fetchone()
    if not char:
        raise LookupError(f"Character {character_id} not found")

    if not force:
        if not cfg["enabled"]:
            raise PermissionError("Resurrection is disabled for this user")
        if cfg["uses_remaining"] is not None and int(cfg["uses_remaining"]) <= 0:
            raise RuntimeError("No resurrection uses remaining")

    sheet = json.loads(char["sheet_json"] or "{}")
    campaign_id = int(char["campaign_id"]) if char["campaign_id"] else None
    from app.services.clock_service import get_clock_state
    current_day = int(get_clock_state(campaign_id, conn=conn)["day"]) if campaign_id else 1

    cost_applied: dict[str, Any] = {"mode": "admin_free" if force else cfg["mode"]}

    if force or cfg["mode"] == "admin_free":
        cost_applied["free"] = True
    elif cfg["mode"] == "gold_percent":
        calc = _calc_cost_gold_percent(character_id, cfg, conn)
        lost = _apply_gold_loss(character_id, calc["gold_lost"], "resurrection_gold_percent", current_day, conn)
        cost_applied.update({"gold_lost": lost, "percent": calc["percent"]})
    elif cfg["mode"] == "gold_recent_days":
        calc = _calc_cost_gold_recent_days(cfg, character_id, current_day, conn)
        lost = _apply_gold_loss(character_id, calc["gold_lost"], "resurrection_gold_recent", current_day, conn)
        cost_applied.update({
            "gold_lost": lost,
            "window_days": calc["window_days"],
            "cap_percent": calc["cap_percent"],
        })
    elif cfg["mode"] == "xp_revert":
        calc = _calc_cost_xp_revert(cfg, character_id, sheet, conn)
        result = _apply_xp_revert(character_id, sheet, calc["grant_ids_to_revert"], calc["xp_lost"], conn)
        cost_applied.update(result)
    elif cfg["mode"] == "item_loss":
        lost_item = _apply_item_loss(character_id, conn)
        if lost_item is None:
            cost_applied.update({"fell_back_to_free": True, "reason": "no_eligible_items"})
        else:
            cost_applied.update({"item_lost": {"label": lost_item["label"], "slot": lost_item["slot"]}})
    else:
        raise ValueError(f"Unknown cost mode: {cfg['mode']}")

    # ── Revive: HP, status, death flags, cooldowns ───────────────────────
    max_hp = int(sheet.get("max_hp") or 1)
    revive_hp = max(1, max_hp // 2)
    sheet["current_hp"] = revive_hp
    sheet["death_saves_failed"] = 0
    sheet["short_rests_used"] = 0
    # Clear any death-tagged conditions
    if isinstance(sheet.get("conditions"), list):
        sheet["conditions"] = [c for c in sheet["conditions"] if c not in ("dead", "unconscious", "dying")]

    conn.execute(
        "UPDATE characters SET sheet_json = ?, status = 'active' WHERE id = ?",
        (json.dumps(sheet, ensure_ascii=False), character_id),
    )

    # Wipe dungeon cooldown rows
    try:
        conn.execute("DELETE FROM character_dungeon_runs WHERE character_id = ?", (character_id,))
    except sqlite3.OperationalError:
        pass

    # Decrement uses_remaining (only when not force-bypass)
    if not force and cfg["uses_remaining"] is not None:
        conn.execute(
            "UPDATE users SET resurrection_uses_remaining = MAX(0, resurrection_uses_remaining - 1) WHERE id = ?",
            (user_id,),
        )

    conn.commit()
    logger.info(
        "hero_resurrected",
        character_id=character_id,
        user_id=user_id,
        force=force,
        mode=cost_applied.get("mode"),
        revived_hp=revive_hp,
    )

    return {
        "character_id": character_id,
        "force": force,
        "cost_applied": cost_applied,
        "revived_hp": revive_hp,
        "max_hp": max_hp,
        "uses_remaining_after": (
            cfg["uses_remaining"] - 1 if (not force and cfg["uses_remaining"] is not None) else cfg["uses_remaining"]
        ),
    }
