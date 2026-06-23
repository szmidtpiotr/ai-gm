"""Crafter NPC service — affix economy: apply / reroll / upgrade.

Gold costs (U2 #510 — reroll premium: ~1.3× apply cost):
  Apply:   T1=150, T2=500,  T3=1200
  Reroll:  T1=200, T2=650,  T3=1500
  Upgrade: T1→T2=350, T2→T3=700
"""
import json
import random

APPLY_COSTS  = {1: 150, 2: 500, 3: 1200}
REROLL_COSTS = {1: 100, 2: 350, 3: 700}
UPGRADE_COSTS = {1: 350, 2: 700}


def _get_item_type(conn, inv_id: int) -> str | None:
    row = conn.execute(
        "SELECT weapon_key, item_key, consumable_key FROM character_inventory WHERE id = ?",
        (inv_id,),
    ).fetchone()
    if not row:
        return None
    if row["weapon_key"]:
        return "weapon"
    if row["item_key"]:
        return "item"
    if row["consumable_key"]:
        return "consumable"
    return None


def _get_affixes_for_tier(conn, tier: int, item_type: str) -> list[str]:
    rows = conn.execute(
        "SELECT key FROM game_config_affixes WHERE tier = ? AND is_active = 1 AND allowed_item_types LIKE ?",
        (tier, f"%{item_type}%"),
    ).fetchall()
    return [r["key"] for r in rows]


def _get_affix_tier(conn, affix_key: str) -> int | None:
    row = conn.execute(
        "SELECT tier FROM game_config_affixes WHERE key = ?", (affix_key,)
    ).fetchone()
    return row["tier"] if row else None


def _get_char_gold(conn, char_id: int) -> int:
    row = conn.execute("SELECT gold_gp FROM characters WHERE id = ?", (char_id,)).fetchone()
    return int(row["gold_gp"] or 0) if row else 0


def _deduct_gold(conn, char_id: int, amount: int, source: str, meta: dict | None = None) -> None:
    # U26: mutate + journal through the central chokepoint.
    from app.services.economy_service import change_gold
    change_gold(conn, char_id, -amount, source, meta=meta)
    conn.commit()


def _get_current_affixes(conn, inv_id: int) -> list[str]:
    row = conn.execute("SELECT affixes_json FROM character_inventory WHERE id = ?", (inv_id,)).fetchone()
    if not row:
        return []
    return json.loads(row["affixes_json"] or "[]")


def _save_affixes(conn, inv_id: int, affixes: list[str]) -> None:
    conn.execute(
        "UPDATE character_inventory SET affixes_json = ? WHERE id = ?",
        (json.dumps(affixes), inv_id),
    )
    conn.commit()


# ─── Public API ───────────────────────────────────────────────────────────────

def get_affix_costs(conn, char_id: int, inv_id: int) -> dict:
    """U16 (#564) — read-only cost preview for the affix forge. Deducts NO gold.

    Zwraca koszty nałożenia (apply per tier) + dla każdego afiksu już na przedmiocie
    koszt rerollu i ulepszenia, plus aktualne złoto bohatera — żeby UI pokazało
    cenę i saldo PO transakcji PRZED kliknięciem.
    """
    item_type = _get_item_type(conn, inv_id)
    if not item_type:
        return {"ok": False, "reason": "item_not_found"}
    gold = _get_char_gold(conn, char_id)
    try:
        current = _get_current_affixes(conn, inv_id)
    except Exception:
        # Bazy bez kolumny affixes_json (luka migracji #462) → podgląd kosztów nadal działa.
        current = []
    affix_rows = []
    for ak in current:
        tier = _get_affix_tier(conn, ak)
        affix_rows.append({
            "affix_key": ak,
            "tier": tier,
            "reroll_cost": REROLL_COSTS.get(tier) if tier else None,
            "upgrade_cost": UPGRADE_COSTS.get(tier) if tier else None,
        })
    return {
        "ok": True,
        "item_type": item_type,
        "gold": gold,
        "apply_costs": APPLY_COSTS,
        "current_affixes": affix_rows,
    }


def apply_affix(conn, char_id: int, inv_id: int, tier: int) -> dict:
    """Add a random affix of the given tier to the item. Deducts gold."""
    cost = APPLY_COSTS.get(tier)
    if cost is None:
        return {"ok": False, "reason": "invalid_tier"}

    gold = _get_char_gold(conn, char_id)
    if gold < cost:
        return {"ok": False, "reason": "insufficient_gold", "have": gold, "need": cost}

    item_type = _get_item_type(conn, inv_id)
    if not item_type:
        return {"ok": False, "reason": "item_not_found"}

    pool = _get_affixes_for_tier(conn, tier, item_type)
    if not pool:
        return {"ok": False, "reason": "no_affixes_available"}

    new_key = random.choice(pool)

    affixes = _get_current_affixes(conn, inv_id)
    affixes.append(new_key)
    _save_affixes(conn, inv_id, affixes)
    _deduct_gold(conn, char_id, cost, "craft_apply_affix", {"inv_id": inv_id, "tier": tier, "affix_key": new_key})

    return {"ok": True, "affix_key": new_key, "cost": cost}


def reroll_affix(conn, char_id: int, inv_id: int, affix_key: str) -> dict:
    """Replace existing affix with a new random one of the same tier. Deducts gold."""
    affixes = _get_current_affixes(conn, inv_id)
    if affix_key not in affixes:
        return {"ok": False, "reason": "affix_not_on_item"}

    tier = _get_affix_tier(conn, affix_key)
    if tier is None:
        return {"ok": False, "reason": "unknown_affix"}

    cost = REROLL_COSTS.get(tier)
    if cost is None:
        return {"ok": False, "reason": "invalid_tier"}

    gold = _get_char_gold(conn, char_id)
    if gold < cost:
        return {"ok": False, "reason": "insufficient_gold", "have": gold, "need": cost}

    item_type = _get_item_type(conn, inv_id)
    pool = _get_affixes_for_tier(conn, tier, item_type)
    if not pool:
        return {"ok": False, "reason": "no_affixes_available"}

    # U25 (#575): reroll pity — after REROLL_PITY_THRESHOLD rerolls of this item
    # without the affix actually changing, the next reroll is forced to a different key.
    from app.services import affix_pity_service
    if affix_pity_service.reroll_guaranteed_different(conn, char_id, inv_id):
        different = [k for k in pool if k != affix_key]
        if different:
            pool = different

    new_key = random.choice(pool)

    idx = affixes.index(affix_key)
    affixes[idx] = new_key
    _save_affixes(conn, inv_id, affixes)
    _deduct_gold(conn, char_id, cost, "craft_reroll_affix", {"inv_id": inv_id, "old_key": affix_key, "new_key": new_key})

    # Track whether the key actually changed so the pity counter resets on a real change.
    affix_pity_service.record_reroll(conn, char_id, inv_id, changed=(new_key != affix_key))

    return {"ok": True, "affix_key": new_key, "cost": cost}


def upgrade_affix(conn, char_id: int, inv_id: int, affix_key: str) -> dict:
    """Replace an affix with a higher-tier random affix. Deducts gold."""
    affixes = _get_current_affixes(conn, inv_id)
    if affix_key not in affixes:
        return {"ok": False, "reason": "affix_not_on_item"}

    tier = _get_affix_tier(conn, affix_key)
    if tier is None:
        return {"ok": False, "reason": "unknown_affix"}

    cost = UPGRADE_COSTS.get(tier)
    if cost is None:
        return {"ok": False, "reason": "max_tier_reached"}

    gold = _get_char_gold(conn, char_id)
    if gold < cost:
        return {"ok": False, "reason": "insufficient_gold", "have": gold, "need": cost}

    new_tier = tier + 1
    item_type = _get_item_type(conn, inv_id)
    pool = _get_affixes_for_tier(conn, new_tier, item_type)
    if not pool:
        return {"ok": False, "reason": "no_affixes_available"}

    new_key = random.choice(pool)

    idx = affixes.index(affix_key)
    affixes[idx] = new_key
    _save_affixes(conn, inv_id, affixes)
    _deduct_gold(conn, char_id, cost, "craft_upgrade_affix", {"inv_id": inv_id, "old_key": affix_key, "new_key": new_key, "tier": new_tier})

    return {"ok": True, "affix_key": new_key, "cost": cost, "new_tier": new_tier}
