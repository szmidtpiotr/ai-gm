"""Durability service — F7 (#467).

Weapons and armor wear down as the player takes hits.
At 0 durability, attack/AC penalties apply until repaired at a merchant.

Repair costs (per missing point):
  T1 (rarity=1): 20 gp/pt
  T2 (rarity=2): 50 gp/pt
  T3 (rarity=3): 100 gp/pt

Default durability by tier:
  T1: 100 pts  T2: 150 pts  T3: 200 pts

Penalty at 0 (configurable via game_config_meta 'durability_penalty_pct', default 50):
  Weapon: -floor(WEAPON_ATTACK_BASE * pct / 100) to attack rolls
  Armor:  -floor(ac_bonus * pct / 100) to player AC
"""
import json
import math

REPAIR_COSTS_PER_PT = {1: 20, 2: 50, 3: 100}
DEFAULT_DURABILITY = {1: 100, 2: 150, 3: 200}
DEFAULT_PENALTY_PCT = 50
WEAPON_ATTACK_BASE = 4  # base weapon contribution used for broken-weapon penalty


def _get_penalty_pct(conn) -> int:
    try:
        row = conn.execute(
            "SELECT value FROM game_config_meta WHERE key = 'durability_penalty_pct'",
        ).fetchone()
        if row and row["value"] is not None:
            return max(0, min(100, int(row["value"])))
    except Exception:
        pass
    return DEFAULT_PENALTY_PCT


def _get_rarity(conn, inv_row) -> int:
    """Resolve rarity from weapon or item config table."""
    try:
        if inv_row["weapon_key"]:
            r = conn.execute(
                "SELECT rarity FROM game_config_weapons WHERE key = ?",
                (inv_row["weapon_key"],),
            ).fetchone()
            return int(r["rarity"] or 1) if r else 1
        if inv_row["item_key"]:
            r = conn.execute(
                "SELECT rarity FROM game_config_items WHERE key = ?",
                (inv_row["item_key"],),
            ).fetchone()
            return int(r["rarity"] or 1) if r else 1
    except Exception:
        pass
    return 1


def _get_equipped_durable(conn, char_id: int):
    """Return equipped inventory rows that have durability_max set."""
    try:
        rows = conn.execute(
            """
            SELECT * FROM character_inventory
            WHERE character_id = ?
              AND COALESCE(equipped, 0) = 1
              AND durability_max IS NOT NULL
            """,
            (char_id,),
        ).fetchall()
    except Exception:
        return []
    return rows


# ─── Public API ───────────────────────────────────────────────────────────────

def decrement_weapon_durability_on_attack(conn, char_id: int) -> None:
    """U2 (#510): Weapons lose 1 durability when the player lands a hit. Floors at 0."""
    rows = _get_equipped_durable(conn, char_id)
    for row in rows:
        if row["weapon_key"] is None:
            continue  # armor handled by decrement_armor_durability_on_hit
        cur = int(row["durability_current"] or 0)
        if cur > 0:
            conn.execute(
                "UPDATE character_inventory SET durability_current = MAX(0, durability_current - 1) WHERE id = ?",
                (row["id"],),
            )
    conn.commit()


def decrement_armor_durability_on_hit(conn, char_id: int) -> None:
    """U2 (#510): Armor loses 1 durability when the player receives a hit. Floors at 0."""
    rows = _get_equipped_durable(conn, char_id)
    for row in rows:
        if row["item_key"] is None:
            continue  # weapons handled by decrement_weapon_durability_on_attack
        cur = int(row["durability_current"] or 0)
        if cur > 0:
            conn.execute(
                "UPDATE character_inventory SET durability_current = MAX(0, durability_current - 1) WHERE id = ?",
                (row["id"],),
            )
    conn.commit()


def decrement_durability_on_hit(conn, char_id: int) -> None:
    """Deprecated (F7 #467) — use decrement_armor_durability_on_hit instead (U2 #510)."""
    decrement_armor_durability_on_hit(conn, char_id)


def get_ac_penalty_for_char(conn, char_id: int) -> int:
    """Return total AC penalty (negative int or 0) from broken equipped armor."""
    rows = _get_equipped_durable(conn, char_id)
    penalty = 0
    pct = _get_penalty_pct(conn)
    for row in rows:
        if row["item_key"] is None:
            continue  # weapons handled separately
        cur = int(row["durability_current"] or 0)
        mx = int(row["durability_max"] or 1)
        if cur > 0 or mx == 0:
            continue
        try:
            item = conn.execute(
                "SELECT ac_bonus FROM game_config_items WHERE key = ?",
                (row["item_key"],),
            ).fetchone()
            ac_b = int(item["ac_bonus"] or 2) if item else 2
        except Exception:
            ac_b = 2
        penalty -= max(1, math.floor(ac_b * pct / 100))
    return penalty


def get_attack_penalty_for_char(conn, char_id: int) -> int:
    """Return total attack roll penalty (negative int or 0) from broken equipped weapons."""
    rows = _get_equipped_durable(conn, char_id)
    penalty = 0
    pct = _get_penalty_pct(conn)
    for row in rows:
        if row["weapon_key"] is None:
            continue
        cur = int(row["durability_current"] or 0)
        mx = int(row["durability_max"] or 1)
        if cur > 0 or mx == 0:
            continue
        penalty -= max(1, math.floor(WEAPON_ATTACK_BASE * pct / 100))
    return penalty


def get_repair_cost(conn, inv_id: int) -> dict:
    """Return repair cost for a specific inventory item."""
    row = conn.execute(
        "SELECT * FROM character_inventory WHERE id = ?", (inv_id,)
    ).fetchone()
    if not row:
        return {"ok": False, "reason": "item_not_found"}
    if row["durability_max"] is None:
        return {"ok": False, "reason": "no_durability"}

    cur = int(row["durability_current"] or 0)
    mx = int(row["durability_max"])
    missing = mx - cur

    rarity = _get_rarity(conn, row)
    cost_per_pt = REPAIR_COSTS_PER_PT.get(rarity, REPAIR_COSTS_PER_PT[1])
    cost = missing * cost_per_pt

    return {
        "ok": True,
        "cost": cost,
        "missing_pts": missing,
        "rarity": rarity,
        "cost_per_pt": cost_per_pt,
        "durability_current": cur,
        "durability_max": mx,
    }


def repair_item(conn, char_id: int, inv_id: int) -> dict:
    """Restore durability to max and deduct gold. Returns {ok, cost}."""
    cost_info = get_repair_cost(conn, inv_id)
    if not cost_info["ok"]:
        return {"ok": False, "reason": cost_info.get("reason")}

    cost = cost_info["cost"]

    if cost > 0:
        row = conn.execute(
            "SELECT gold_gp FROM characters WHERE id = ?", (char_id,)
        ).fetchone()
        gold = int(row["gold_gp"] or 0) if row else 0
        if gold < cost:
            return {"ok": False, "reason": "insufficient_gold", "have": gold, "need": cost}

        conn.execute("UPDATE characters SET gold_gp = gold_gp - ? WHERE id = ?", (cost, char_id))
        conn.execute(
            "INSERT INTO character_gold_log (character_id, delta, source, meta_json) VALUES (?, ?, ?, ?)",
            (char_id, -cost, "repair_durability", json.dumps({"inv_id": inv_id, "cost": cost})),
        )

    conn.execute(
        "UPDATE character_inventory SET durability_current = durability_max WHERE id = ?",
        (inv_id,),
    )
    conn.commit()

    return {"ok": True, "cost": cost, "durability_restored": cost_info["missing_pts"]}
