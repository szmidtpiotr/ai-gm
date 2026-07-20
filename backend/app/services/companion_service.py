"""Companion & Mount service — #1192 FAZA TW.

Single home for all towarzysz/wierzchowiec business logic:
  - hire / buy / dismiss / grant + slot enforcement (1 combat companion + 1 mount)
  - daily upkeep (deducted on march-day change / long rest)
  - travel speed multiplier gated by the `riding` skill rank (mounts)
  - encounter-chance modifier (dog warns of ambush)
  - mounted escape-from-encounter resolution (riding test)
  - combat-companion combatant builder (consumed by combat_service, B15-style)

All numbers here are STARTING values (Numbers Policy) — kept at module top,
Sandbox-tunable. Pure-ish: every function takes a caller-owned sqlite conn.
"""
from __future__ import annotations

import json
import sqlite3
from typing import Any

import structlog

from app.core.mechanics import proficiency_bonus, stat_modifier
from app.services.dice import roll_d20
from app.core.db_runtime import resolve_db_path

logger = structlog.get_logger()

DB_PATH = resolve_db_path()

# ── Numbers Policy (starting values) ────────────────────────────────────────
# Effective mount travel-time multiplier by riding skill rank. Lower = faster.
# R0 = stępa (no rank → horse helps a little); rank gates full gallop speed.
RIDING_RANK_MULT: dict[int, float] = {0: 0.85, 1: 0.75, 2: 0.70, 3: 0.65}
# Mule benefits from riding at half strength (baseline slower, less responsive).
MULE_RANK_MULT: dict[int, float] = {0: 0.95, 1: 0.90, 2: 0.88, 3: 0.85}

ESCAPE_BASE_DC = 10           # vs 10 + 2×enemy_tier
ESCAPE_DC_PER_TIER = 2
NAT1_DISMOUNT_DAMAGE = "1d4"  # fall from the saddle on a botched escape

UNPAID_DISMISS_THRESHOLD = 2  # hired companion walks after N unpaid days
UNDERFED_AFTER_DAYS = 2       # owned mount goes underfed after N unfed days

COMBAT_TYPES = ("hireling", "animal")
MOUNT_TYPE = "mount"


# ── low-level helpers ───────────────────────────────────────────────────────

def _catalog(conn: sqlite3.Connection, key: str) -> dict | None:
    row = conn.execute(
        "SELECT * FROM game_config_companions WHERE key = ? AND is_active = 1 LIMIT 1",
        (key,),
    ).fetchone()
    return dict(row) if row else None


def _passives(cat: dict) -> dict:
    try:
        return json.loads(cat.get("passive_json") or "{}") or {}
    except (ValueError, TypeError):
        return {}


def _character_sheet(conn: sqlite3.Connection, character_id: int) -> dict:
    row = conn.execute(
        "SELECT sheet_json FROM characters WHERE id = ? LIMIT 1", (character_id,)
    ).fetchone()
    if not row:
        return {}
    try:
        return json.loads(row["sheet_json"] or "{}") or {}
    except (ValueError, TypeError):
        return {}


def get_riding_rank(conn: sqlite3.Connection, character_id: int) -> int:
    sheet = _character_sheet(conn, character_id)
    skills = sheet.get("skills") or {}
    try:
        return int(skills.get("riding", 0) or 0)
    except (ValueError, TypeError):
        return 0


def _row_to_active(conn: sqlite3.Connection, row: sqlite3.Row) -> dict:
    cat = _catalog(conn, row["companion_key"]) or {}
    return {
        "id": row["id"],
        "companion_key": row["companion_key"],
        "type": cat.get("type"),
        "label": cat.get("label"),
        "name": row["custom_name"] or cat.get("label"),
        "current_hp": row["current_hp"],
        "hp_max": cat.get("hp_base"),
        "state": row["state"],
        "ownership": row["ownership"],
        "unpaid_days": row["unpaid_days"],
        "underfed": bool(row["underfed"]),
        "daily_cost": cat.get("daily_cost"),
        "upkeep_cost": cat.get("upkeep_cost"),
        "passives": _passives(cat),
        "note": cat.get("note"),
    }


def get_active_companions(conn: sqlite3.Connection, character_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM character_companions "
        "WHERE character_id = ? AND state = 'active' ORDER BY id",
        (character_id,),
    ).fetchall()
    return [_row_to_active(conn, r) for r in rows]


def get_active_mount(conn: sqlite3.Connection, character_id: int) -> dict | None:
    for c in get_active_companions(conn, character_id):
        if c["type"] == MOUNT_TYPE:
            return c
    return None


def get_active_combat_companion(conn: sqlite3.Connection, character_id: int) -> dict | None:
    for c in get_active_companions(conn, character_id):
        if c["type"] in COMBAT_TYPES:
            return c
    return None


# ── acquisition (hire / buy / grant / dismiss) ──────────────────────────────

def _slot_of(cat_type: str) -> str:
    return "mount" if cat_type == MOUNT_TYPE else "combat"


def _occupied_slot(conn: sqlite3.Connection, character_id: int, slot: str) -> dict | None:
    for c in get_active_companions(conn, character_id):
        if _slot_of(c["type"]) == slot:
            return c
    return None


def _insert_companion(
    conn: sqlite3.Connection,
    character_id: int,
    cat: dict,
    ownership: str,
    custom_name: str | None,
    day: int | None,
) -> int:
    cur = conn.execute(
        """INSERT INTO character_companions
           (character_id, companion_key, custom_name, current_hp, state,
            ownership, last_upkeep_day)
           VALUES (?, ?, ?, ?, 'active', ?, ?)""",
        (character_id, cat["key"], custom_name, int(cat["hp_base"]), ownership, day),
    )
    return int(cur.lastrowid)


def hire(
    conn: sqlite3.Connection,
    character_id: int,
    companion_key: str,
    *,
    day: int | None = None,
    campaign_id: int | None = None,
) -> dict:
    """Hire a companion (pay first day up front). Raises ValueError codes:
    companion_not_found | not_hireable | slot_occupied | insufficient_gold."""
    cat = _catalog(conn, companion_key)
    if not cat:
        raise ValueError("companion_not_found")
    if int(cat["daily_cost"] or 0) <= 0:
        raise ValueError("not_hireable")
    slot = _slot_of(cat["type"])
    if _occupied_slot(conn, character_id, slot):
        raise ValueError("slot_occupied")

    cost = int(cat["daily_cost"])
    from app.services.economy_service import change_gold
    try:
        change_gold(conn, character_id, -cost, "companion_hire",
                    campaign_id=campaign_id, meta={"companion_key": companion_key})
    except ValueError:
        raise ValueError("insufficient_gold")

    cid = _insert_companion(conn, character_id, cat, "hired", None, day)
    conn.commit()
    logger.info("companion_hired", character_id=character_id, key=companion_key, cost=cost)
    return {"id": cid, "companion_key": companion_key, "paid_gp": cost, "ownership": "hired"}


def buy(
    conn: sqlite3.Connection,
    character_id: int,
    companion_key: str,
    *,
    custom_name: str | None = None,
    day: int | None = None,
    campaign_id: int | None = None,
) -> dict:
    """Buy a companion outright (owned). Raises ValueError codes:
    companion_not_found | not_buyable | slot_occupied | insufficient_gold."""
    cat = _catalog(conn, companion_key)
    if not cat:
        raise ValueError("companion_not_found")
    if cat.get("buy_cost") is None:
        raise ValueError("not_buyable")
    slot = _slot_of(cat["type"])
    if _occupied_slot(conn, character_id, slot):
        raise ValueError("slot_occupied")

    cost = int(cat["buy_cost"])
    from app.services.economy_service import change_gold
    try:
        change_gold(conn, character_id, -cost, "companion_buy",
                    campaign_id=campaign_id, meta={"companion_key": companion_key})
    except ValueError:
        raise ValueError("insufficient_gold")

    cid = _insert_companion(conn, character_id, cat, "owned", custom_name, day)
    conn.commit()
    logger.info("companion_bought", character_id=character_id, key=companion_key, cost=cost)
    return {"id": cid, "companion_key": companion_key, "paid_gp": cost, "ownership": "owned",
            "custom_name": custom_name}


def grant_companion(
    conn: sqlite3.Connection,
    character_id: int,
    companion_key: str,
    *,
    ownership: str = "owned",
    custom_name: str | None = None,
    day: int | None = None,
    source: str = "gm",
) -> dict:
    """Narrative/admin grant — no gold charged. Foundation for quest/loot hooks.
    Raises companion_not_found | slot_occupied (caller decides swap)."""
    cat = _catalog(conn, companion_key)
    if not cat:
        raise ValueError("companion_not_found")
    slot = _slot_of(cat["type"])
    if _occupied_slot(conn, character_id, slot):
        raise ValueError("slot_occupied")
    cid = _insert_companion(conn, character_id, cat, ownership, custom_name, day)
    conn.commit()
    logger.info("companion_granted", character_id=character_id, key=companion_key, source=source)
    return {"id": cid, "companion_key": companion_key, "ownership": ownership, "granted": True}


def dismiss(conn: sqlite3.Connection, character_id: int, companion_id: int) -> dict:
    """Release a companion (no refund in v1). Raises companion_not_found."""
    row = conn.execute(
        "SELECT * FROM character_companions "
        "WHERE id = ? AND character_id = ? AND state = 'active' LIMIT 1",
        (companion_id, character_id),
    ).fetchone()
    if not row:
        raise ValueError("companion_not_found")
    conn.execute(
        "UPDATE character_companions SET state = 'dismissed' WHERE id = ?", (companion_id,)
    )
    conn.commit()
    logger.info("companion_dismissed", character_id=character_id, id=companion_id)
    return {"id": companion_id, "state": "dismissed"}


# ── daily upkeep (TW3) ──────────────────────────────────────────────────────

def run_daily_upkeep(
    conn: sqlite3.Connection,
    character_id: int,
    day: int,
    *,
    campaign_id: int | None = None,
    stabled: bool = False,
) -> list[dict]:
    """Charge one day of upkeep for every active companion whose last_upkeep_day
    is older than `day`. Idempotent within a day. Returns a list of events.

    hired: deduct daily_cost; unpaid → unpaid_days++, dismiss at threshold.
    owned mount: deduct upkeep_cost (feed); unpaid → underfed after threshold.
    `stabled=True` (paid stable_night this rest) covers a mount's feed for free.
    """
    from app.services.economy_service import change_gold

    events: list[dict] = []
    rows = conn.execute(
        "SELECT * FROM character_companions "
        "WHERE character_id = ? AND state = 'active'",
        (character_id,),
    ).fetchall()

    for row in rows:
        if row["last_upkeep_day"] is not None and int(row["last_upkeep_day"]) >= int(day):
            continue  # already charged today
        cat = _catalog(conn, row["companion_key"])
        if not cat:
            continue

        if row["ownership"] == "hired":
            cost = int(cat["daily_cost"] or 0)
            paid = False
            if cost > 0:
                try:
                    change_gold(conn, character_id, -cost, "companion_upkeep",
                                campaign_id=campaign_id,
                                meta={"companion_key": row["companion_key"], "kind": "hire"})
                    paid = True
                except ValueError:
                    paid = False
            if paid or cost == 0:
                conn.execute(
                    "UPDATE character_companions SET last_upkeep_day = ?, unpaid_days = 0 WHERE id = ?",
                    (day, row["id"]),
                )
            else:
                new_unpaid = int(row["unpaid_days"] or 0) + 1
                if new_unpaid >= UNPAID_DISMISS_THRESHOLD:
                    conn.execute(
                        "UPDATE character_companions SET state = 'dismissed', unpaid_days = ? WHERE id = ?",
                        (new_unpaid, row["id"]),
                    )
                    events.append({"companion_key": row["companion_key"], "event": "dismissed_unpaid"})
                    _emit(f"{cat['label']} odchodzi — brak zapłaty od {new_unpaid} dni.")
                else:
                    conn.execute(
                        "UPDATE character_companions SET unpaid_days = ?, last_upkeep_day = ? WHERE id = ?",
                        (new_unpaid, day, row["id"]),
                    )
                    events.append({"companion_key": row["companion_key"], "event": "unpaid",
                                   "unpaid_days": new_unpaid})
                    _emit(f"Nie stać cię na żołd — {cat['label']} grozi odejściem.")

        else:  # owned
            if cat["type"] == MOUNT_TYPE and stabled:
                conn.execute(
                    "UPDATE character_companions SET last_upkeep_day = ?, unpaid_days = 0, underfed = 0 WHERE id = ?",
                    (day, row["id"]),
                )
                continue
            cost = int(cat["upkeep_cost"] or 0)
            paid = False
            if cost > 0:
                try:
                    change_gold(conn, character_id, -cost, "companion_upkeep",
                                campaign_id=campaign_id,
                                meta={"companion_key": row["companion_key"], "kind": "feed"})
                    paid = True
                except ValueError:
                    paid = False
            if paid or cost == 0:
                conn.execute(
                    "UPDATE character_companions SET last_upkeep_day = ?, unpaid_days = 0, underfed = 0 WHERE id = ?",
                    (day, row["id"]),
                )
            else:
                new_unpaid = int(row["unpaid_days"] or 0) + 1
                underfed = 1 if new_unpaid >= UNDERFED_AFTER_DAYS else int(row["underfed"] or 0)
                conn.execute(
                    "UPDATE character_companions SET unpaid_days = ?, underfed = ?, last_upkeep_day = ? WHERE id = ?",
                    (new_unpaid, underfed, day, row["id"]),
                )
                if underfed and not row["underfed"]:
                    events.append({"companion_key": row["companion_key"], "event": "underfed"})
                    _emit(f"{cat['label']} głodnieje — bez paszy traci siły.")

    conn.commit()
    return events


def _emit(text: str) -> None:
    try:
        from app.services import system_events as _se
        _se.emit("companion", text, dedupe_key="companion")
    except Exception:
        pass


# ── travel speed (TW5) ──────────────────────────────────────────────────────

def get_travel_multiplier(
    conn: sqlite3.Connection,
    character_id: int,
    *,
    hex_type: str | None = None,
) -> float:
    """Effective travel-time multiplier from the character's active companions.

    Combines (multiplicatively): mount speed gated by riding rank, and any
    hireling per-terrain bonus (tracker → forest). Underfed mounts lose their
    bonus. Returns 1.0 when nothing applies. Composes with weather/event
    multipliers at the call site — callers multiply, never overwrite.
    """
    mult = 1.0
    mount = get_active_mount(conn, character_id)
    if mount and not mount["underfed"]:
        p = mount["passives"]
        base = float(p.get("travel_speed_mult", 1.0) or 1.0)
        if base < 1.0:
            rank = get_riding_rank(conn, character_id)
            rank = max(0, min(3, rank))
            table = MULE_RANK_MULT if mount["companion_key"] == "mule" else RIDING_RANK_MULT
            mult *= table.get(rank, base)
        else:
            mult *= base

    # Hireling per-terrain speed (tracker las 0.8)
    for c in get_active_companions(conn, character_id):
        if c["type"] in COMBAT_TYPES:
            terr = c["passives"].get("terrain_speed_mult")
            if isinstance(terr, dict) and hex_type and hex_type in terr:
                try:
                    mult *= float(terr[hex_type])
                except (ValueError, TypeError):
                    pass
    return mult


def get_daily_cap_bonus(conn: sqlite3.Connection, character_id: int) -> float:
    """Extra hours added to the daily march soft/hard cap from an active,
    fed mount (0.0 if none / underfed)."""
    mount = get_active_mount(conn, character_id)
    if mount and not mount["underfed"]:
        try:
            return float(mount["passives"].get("daily_cap_bonus_h", 0) or 0)
        except (ValueError, TypeError):
            return 0.0
    return 0.0


# ── encounter chance (TW6) ──────────────────────────────────────────────────

def get_encounter_chance_mult(conn: sqlite3.Connection, character_id: int) -> float:
    """Multiplier applied to travel encounter chance from active companions
    (dog warns of ambush → <1.0). Product of all contributors. 1.0 if none."""
    mult = 1.0
    for c in get_active_companions(conn, character_id):
        m = c["passives"].get("encounter_chance_mult")
        if m is not None:
            try:
                mult *= float(m)
            except (ValueError, TypeError):
                pass
    return mult


# ── mounted escape (TW7) ────────────────────────────────────────────────────

def can_escape_mounted(conn: sqlite3.Connection, character_id: int) -> bool:
    mount = get_active_mount(conn, character_id)
    return bool(mount and not mount["underfed"]
                and mount["passives"].get("escape_enabled"))


def resolve_mount_escape(
    conn: sqlite3.Connection,
    character_id: int,
    enemy_tier: int,
) -> dict:
    """Resolve a riding test to flee an encounter before combat.
    DC = ESCAPE_BASE_DC + ESCAPE_DC_PER_TIER × tier. Returns roll breakdown +
    escaped flag; nat 1 = fall from saddle (self damage, forced combat)."""
    sheet = _character_sheet(conn, character_id)
    stats = sheet.get("stats") or {}
    skills = sheet.get("skills") or {}
    dex_mod = stat_modifier(int(stats.get("DEX", 10) or 10))
    rank = int(skills.get("riding", 0) or 0)
    prof = proficiency_bonus(rank)

    roll = roll_d20()
    total = roll + dex_mod + rank + prof
    dc = ESCAPE_BASE_DC + ESCAPE_DC_PER_TIER * int(enemy_tier or 0)

    nat20 = roll == 20
    nat1 = roll == 1
    escaped = nat20 or (not nat1 and total >= dc)

    result: dict[str, Any] = {
        "escaped": escaped,
        "roll": roll,
        "modifier": dex_mod + rank + prof,
        "total": total,
        "dc": dc,
        "nat20": nat20,
        "nat1": nat1,
        "self_damage": 0,
    }
    if nat1:
        result["self_damage"] = _roll_simple(NAT1_DISMOUNT_DAMAGE)
        result["dismount"] = True
    return result


# ── admin CRUD (TW10) ───────────────────────────────────────────────────────

_COMPANION_TYPES = ("mount", "hireling", "animal")
_COMPANION_COLS = (
    "key", "label", "type", "hp_base", "attack_json", "daily_cost", "buy_cost",
    "upkeep_cost", "passive_json", "region_tags", "description", "note", "is_active",
)


def admin_list(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM game_config_companions ORDER BY type, COALESCE(buy_cost, 9999), key"
    ).fetchall()
    return [dict(r) for r in rows]


def _validate_admin_payload(p: dict, *, require_key: bool = True) -> None:
    import re as _re
    if require_key:
        key = str(p.get("key") or "").strip()
        if not _re.match(r"^[a-z0-9_]{1,40}$", key):
            raise ValueError("invalid_key")
    if "type" in p and p["type"] is not None and str(p["type"]) not in _COMPANION_TYPES:
        raise ValueError("invalid_type")
    if p.get("hp_base") is not None and int(p["hp_base"]) < 1:
        raise ValueError("invalid_hp_base")
    for jf in ("attack_json", "passive_json"):
        v = p.get(jf)
        if v:
            try:
                json.loads(v)
            except (ValueError, TypeError):
                raise ValueError(f"invalid_{jf}")


def admin_create(conn: sqlite3.Connection, payload: dict) -> dict:
    _validate_admin_payload(payload, require_key=True)
    key = str(payload["key"]).strip()
    exists = conn.execute(
        "SELECT 1 FROM game_config_companions WHERE key = ?", (key,)
    ).fetchone()
    if exists:
        raise ValueError("companion_exists")
    vals = {c: payload.get(c) for c in _COMPANION_COLS}
    vals["key"] = key
    vals["type"] = vals.get("type") or "hireling"
    vals["hp_base"] = int(vals.get("hp_base") or 10)
    # NOT NULL DEFAULT 0 columns — never pass NULL.
    vals["daily_cost"] = int(vals.get("daily_cost") or 0)
    vals["upkeep_cost"] = int(vals.get("upkeep_cost") or 0)
    vals["is_active"] = 1 if vals.get("is_active", 1) in (1, True, "1", None) else 0
    cols = list(_COMPANION_COLS)
    conn.execute(
        f"INSERT INTO game_config_companions ({','.join(cols)}, created_by) "
        f"VALUES ({','.join('?' for _ in cols)}, 'admin')",
        [vals[c] for c in cols],
    )
    conn.commit()
    return _catalog(conn, key) or vals


def admin_update(conn: sqlite3.Connection, key: str, payload: dict) -> dict:
    row = conn.execute(
        "SELECT 1 FROM game_config_companions WHERE key = ?", (key,)
    ).fetchone()
    if not row:
        raise ValueError("companion_not_found")
    _validate_admin_payload(payload, require_key=False)
    fields = [c for c in _COMPANION_COLS if c != "key" and c in payload]
    if not fields:
        return _catalog(conn, key) or {}
    conn.execute(
        f"UPDATE game_config_companions SET {', '.join(f'{c}=?' for c in fields)}, "
        f"updated_at=datetime('now') WHERE key = ?",
        [payload[c] for c in fields] + [key],
    )
    conn.commit()
    return dict(conn.execute(
        "SELECT * FROM game_config_companions WHERE key = ?", (key,)
    ).fetchone())


def admin_delete(conn: sqlite3.Connection, key: str) -> dict:
    row = conn.execute(
        "SELECT 1 FROM game_config_companions WHERE key = ?", (key,)
    ).fetchone()
    if not row:
        raise ValueError("companion_not_found")
    conn.execute("DELETE FROM game_config_companions WHERE key = ?", (key,))
    conn.commit()
    return {"deleted": key}


def campaign_companions(conn: sqlite3.Connection, campaign_id: int) -> list[dict]:
    """TW10 monitor: aktywni towarzysze wszystkich postaci w kampanii."""
    rows = conn.execute(
        "SELECT id FROM characters WHERE campaign_id = ?", (campaign_id,)
    ).fetchall()
    out: list[dict] = []
    for r in rows:
        for c in get_active_companions(conn, int(r["id"])):
            c["character_id"] = int(r["id"])
            out.append(c)
    return out


_ENEMY_TIER_INT = {"weak": 1, "standard": 2, "elite": 3, "boss": 4}


def resolve_travel_escape(
    conn: sqlite3.Connection, campaign_id: int, character_id: int
) -> dict:
    """TW7: rozlicz próbę ucieczki konno z aktywnego spotkania w podróży.

    Czyta `session_flags.travel_plan` (pending encounter), mapuje tier wroga
    TEXT→int, sprawdza `can_escape_mounted`, rozlicza `resolve_mount_escape`.
    Sukces → stempluje `travel_plan.combat_seen=True` (następny TRAVEL_RESUME
    NIE wstrzyknie [COMBAT_START] — walki nie ma). Porażka → nie rusza planu
    (walka ruszy normalnie). Raises ValueError: no_encounter | no_mount."""
    row = conn.execute(
        "SELECT id, session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
        (campaign_id,),
    ).fetchone()
    sf = json.loads((row["session_flags"] if row else None) or "{}")
    tp = sf.get("travel_plan") or {}
    enemy_key = tp.get("enemy_key")
    if not (tp.get("interrupt_reason") == "encounter" and not tp.get("combat_seen") and enemy_key):
        raise ValueError("no_encounter")

    if not can_escape_mounted(conn, character_id):
        raise ValueError("no_mount")

    tier_txt = "standard"
    er = conn.execute(
        "SELECT tier FROM game_config_enemies WHERE key = ? LIMIT 1", (enemy_key,)
    ).fetchone()
    if er and er["tier"]:
        tier_txt = str(er["tier"]).strip().lower()
    tier = _ENEMY_TIER_INT.get(tier_txt, 2)

    res = resolve_mount_escape(conn, character_id, tier)
    res["enemy_key"] = enemy_key
    res["enemy_tier"] = tier

    if res["escaped"]:
        tp["combat_seen"] = True
        sf["travel_plan"] = tp
        conn.execute(
            "UPDATE game_sessions SET session_flags = ? WHERE id = ?",
            (json.dumps(sf, ensure_ascii=False), row["id"]),
        )
        conn.commit()
        _emit("Spinasz wierzchowca i wyrywasz się przed walką.")
    return res


def _roll_simple(dice: str) -> int:
    """Minimal NdM roller for self-damage (e.g. '1d4'). No modifiers."""
    import random as _r
    try:
        n, m = dice.lower().split("d")
        n_i = int(n) if n else 1
        m_i = int(m)
        return sum(_r.randint(1, m_i) for _ in range(n_i))
    except (ValueError, AttributeError):
        return 1


# ── combat companion builder (TW8) ──────────────────────────────────────────

def build_companion_combatant(conn: sqlite3.Connection, character_id: int) -> dict | None:
    """Return a combatant dict for the active combat companion (hireling/animal),
    shaped like a B15 summon so combat_service can splice it into `combatants`
    and `turn_order`. None if no combat companion. Mounts never combat."""
    comp = get_active_combat_companion(conn, character_id)
    if not comp:
        return None
    cat = _catalog(conn, comp["companion_key"]) or {}
    try:
        atk = json.loads(cat.get("attack_json") or "{}") or {}
    except (ValueError, TypeError):
        atk = {}
    if not atk:
        return None
    return {
        "id": f"companion_{comp['id']}",
        "type": "companion",
        "owner_id": "player",
        "companion_row_id": comp["id"],
        "companion_key": comp["companion_key"],
        "name": comp["name"],
        "hp_current": int(comp["current_hp"]),
        "hp_max": int(comp["hp_max"]),
        "defense": int(atk.get("defense", 11)),
        "attack_bonus": int(atk.get("attack_bonus", 2)),
        "damage_dice": str(atk.get("damage_dice", "1d4")),
        "conditions": [],
        "zone": str(atk.get("zone", "engaged")),
        "stats": {"STR": 12, "DEX": 12, "CON": 12, "INT": 8, "WIS": 10, "CHA": 8},
    }


def sync_companion_hp(
    conn: sqlite3.Connection, character_id: int, companion_row_id: int, hp: int
) -> None:
    """Write post-combat HP back; hp<=0 → permanent death (no resurrection)."""
    if hp <= 0:
        conn.execute(
            "UPDATE character_companions SET current_hp = 0, state = 'dead' WHERE id = ?",
            (companion_row_id,),
        )
        row = conn.execute(
            "SELECT companion_key FROM character_companions WHERE id = ?", (companion_row_id,)
        ).fetchone()
        if row:
            cat = _catalog(conn, row["companion_key"]) or {}
            _emit(f"{cat.get('label', 'Towarzysz')} pada martwy. Nie ma powrotu.")
    else:
        conn.execute(
            "UPDATE character_companions SET current_hp = ? WHERE id = ?",
            (int(hp), companion_row_id),
        )
    conn.commit()


# ── availability at a location (TW4) ────────────────────────────────────────

def companions_at_location(
    conn: sqlite3.Connection, location_key: str | None, *, character_id: int | None = None
) -> dict:
    """Recruitable companions offered at a location. Stables → mounts; taverns/
    inns → hirelings & animals. Filtered by region_tags when the location carries
    a region. Returns {items, character_gold, has_stable, has_tavern}."""
    from app.services.location_services import get_available_service_keys

    if not location_key:
        return {"items": [], "character_gold": 0, "has_stable": False, "has_tavern": False}

    svc_keys = get_available_service_keys(conn, location_key)
    has_stable = "stable_night" in svc_keys
    has_tavern = any(k in svc_keys for k in ("inn_night", "tavern_meal", "tavern_drink"))

    loc = conn.execute(
        "SELECT region FROM game_locations WHERE key = ? LIMIT 1", (location_key,)
    ).fetchone()
    region = (loc["region"] if loc and "region" in loc.keys() else None) or None

    types: list[str] = []
    if has_stable:
        types.append("mount")
    if has_tavern:
        types += ["hireling", "animal"]

    items: list[dict] = []
    if types:
        placeholders = ",".join("?" * len(types))
        rows = conn.execute(
            f"SELECT * FROM game_config_companions "
            f"WHERE type IN ({placeholders}) AND is_active = 1 ORDER BY type, buy_cost",
            types,
        ).fetchall()
        for r in rows:
            tags = (r["region_tags"] or "").strip()
            if tags and region and region not in [t.strip() for t in tags.split(",")]:
                continue
            items.append({
                "key": r["key"], "label": r["label"], "type": r["type"],
                "hp_base": r["hp_base"], "daily_cost": r["daily_cost"],
                "buy_cost": r["buy_cost"], "upkeep_cost": r["upkeep_cost"],
                "passives": _passives(dict(r)), "description": r["description"],
                "note": r["note"],
            })

    gold = 0
    if character_id is not None:
        g = conn.execute(
            "SELECT gold_gp FROM characters WHERE id = ? LIMIT 1", (character_id,)
        ).fetchone()
        gold = int(g["gold_gp"] or 0) if g else 0

    return {"items": items, "character_gold": gold,
            "has_stable": has_stable, "has_tavern": has_tavern}
