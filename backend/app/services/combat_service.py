"""
Phase 8A — Active combat state and resolution (solo, SQLite).

Combatant runtime JSON uses hp_current / hp_max; character sheet uses current_hp / max_hp.
"""

from __future__ import annotations

import json
import random
import re
import sqlite3
from datetime import datetime, timezone
from typing import Any

from app.core.logging import get_logger
from app.services.effect_json_migration import legacy_effect_fields_from_json
from app.services.dice import parse_character_sheet, resolve_dc_for_roll, roll_d20
from app.services.weapon_rules import (
    load_weapon_row,
    resolve_attack_roll_for_weapon,
    resolve_sheet_weapon,
    stat_modifier,
)

# Tests may monkeypatch this to a temp file path.
COMBAT_DB_PATH = "/data/ai_gm.db"

logger = get_logger(__name__)


def _log_dice_roll_combat_resolve(
    *,
    source: str,
    campaign_id: int,
    result_total: int,
    dc: int,
    hit: bool,
    raw_d20: int | None,
) -> None:
    """Loki-friendly ``dice_roll`` with DC and outcome (Combat System 2 — step 8.2)."""
    if raw_d20 is not None:
        r = int(raw_d20)
        if r == 20:
            outcome = "critical_hit"
        elif r == 1:
            outcome = "critical_miss"
        else:
            outcome = "hit" if hit else "miss"
    else:
        outcome = "hit" if hit else "miss"
    logger.info(
        "dice_roll",
        roll_type="1d20",
        result=int(result_total),
        dc=int(dc),
        outcome=outcome,
        source=source,
        campaign_id=int(campaign_id),
    )


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(COMBAT_DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def _stat_mod(sheet: dict, stat: str) -> int:
    return stat_modifier(sheet, stat)


def _player_ac_from_sheet(sheet: dict) -> int:
    dex_mod = _stat_mod(sheet, "DEX")
    archetype = str(sheet.get("archetype") or "").strip().lower()
    archetype_ac = {"warrior": 2, "rogue": 1}.get(archetype, 0)
    d = sheet.get("defense")
    if isinstance(d, dict) and d.get("base") is not None:
        # Legacy sheets with explicit base — add archetype bonus on top
        return int(d["base"]) + archetype_ac
    return 10 + dex_mod + archetype_ac


def _player_hp_pair(sheet: dict) -> tuple[int, int]:
    cur = int(sheet.get("current_hp", 0) or 0)
    mx = int(sheet.get("max_hp", cur) or cur)
    return cur, max(mx, 1)


def _sheet_conditions(sheet: dict) -> list[dict[str, Any]]:
    raw = sheet.get("conditions")
    if not isinstance(raw, list):
        return []
    return [x for x in raw if isinstance(x, dict)]


# ── Stage 3 Z2: attacker bonuses from target conditions ────────────────────

def _apply_attack_bonuses(attacker: dict, target: dict) -> dict[str, Any]:
    """Stage 3 Z2: derive attacker-side bonuses from target's conditions.

    Currently handles `zaskoczony` (surprise): +2 to attack roll, first hit
    deals doubled damage, and condition is consumed after damage (Z3).
    Returns `{atk_bonus: int, first_hit_doubled: bool, consumed_keys: list[str]}`.
    """
    out: dict[str, Any] = {"atk_bonus": 0, "first_hit_doubled": False, "consumed_keys": []}
    if not isinstance(target, dict):
        return out
    conds = target.get("conditions") or []
    if not isinstance(conds, list):
        return out
    for c in conds:
        if not isinstance(c, dict):
            continue
        if str(c.get("key", "")).lower() == "zaskoczony":
            out["atk_bonus"] += 2
            out["first_hit_doubled"] = True
            out["consumed_keys"].append("zaskoczony")
            break
    return out


def _clear_consumed_conditions(target: dict, consumed_keys: list[str]) -> None:
    """Stage 3 Z3: remove keys from target.conditions list in place."""
    if not consumed_keys or not isinstance(target, dict):
        return
    conds = target.get("conditions") or []
    if not isinstance(conds, list):
        return
    keyset = {str(k).lower() for k in consumed_keys}
    target["conditions"] = [
        c for c in conds
        if not (isinstance(c, dict) and str(c.get("key", "")).lower() in keyset)
    ]


def _apply_weapon_effects(
    weapon_row: dict | None,
    sheet: dict,
    enemy: dict,
    is_crit: bool,
    conn: Any,
) -> dict[str, Any]:
    """Evaluate weapon effect_json after a successful hit.

    Supported effect types:
      extra_damage  — roll additional dice (doubled on crit)
      on_hit_save   — enemy makes a stat save vs DC; on fail: extra_damage or apply_condition
    Modifies enemy["conditions"] in place. Returns summary dict.
    """
    raw = weapon_row.get("effect_json") if weapon_row else None
    parsed = _decode_effect_json(raw)
    if not parsed:
        return {}
    effects = parsed.get("effects")
    if not isinstance(effects, list) or not effects:
        return {}

    total_extra = 0
    cond_applied: list[str] = []
    narrative_parts: list[str] = []

    for effect in effects:
        etype = str(effect.get("type") or "")

        if etype == "extra_damage":
            dice_expr = str(effect.get("dice") or "1d4")
            dtype = str(effect.get("damage_type") or "physical")
            rolls = 2 if is_crit else 1
            extra = sum(roll_damage_dice(dice_expr) for _ in range(rolls))
            total_extra += extra
            narrative_parts.append(f"+{extra} ({dtype})")

        elif etype == "on_hit_save":
            stat = str(effect.get("stat") or "CON").upper()
            dc = int(effect.get("dc") or 12)
            enemy_stats = enemy.get("stats") or {}
            raw_val = int(enemy_stats.get(stat, 10) or 10)
            save_mod = (raw_val - 10) // 2
            save_roll = random.randint(1, 20)
            save_total = save_roll + save_mod
            success = save_total >= dc

            if not success:
                on_fail = effect.get("on_fail") or {}
                fail_type = str(on_fail.get("type") or "")

                if fail_type == "extra_damage":
                    dice_expr = str(on_fail.get("dice") or "1d6")
                    dtype = str(on_fail.get("damage_type") or "physical")
                    extra = roll_damage_dice(dice_expr)
                    total_extra += extra
                    narrative_parts.append(
                        f"Rzut obronny {stat} nieudany ({save_total}<{dc}): +{extra} ({dtype})"
                    )

                elif fail_type == "apply_condition":
                    cond_key = str(on_fail.get("condition_key") or "poisoned")
                    duration = int(on_fail.get("duration_rounds") or 2)
                    cond_label, cond_efx = cond_key, None
                    try:
                        crow = conn.execute(
                            "SELECT label, effect_json FROM game_config_conditions WHERE key = ?",
                            (cond_key,),
                        ).fetchone()
                        if crow:
                            cond_label = crow["label"] or cond_key
                            cond_efx = crow["effect_json"]
                    except Exception:
                        pass
                    existing = enemy.get("conditions") or []
                    if not any(c.get("key") == cond_key for c in existing):
                        if not isinstance(enemy.get("conditions"), list):
                            enemy["conditions"] = []
                        enemy["conditions"].append({
                            "key": cond_key,
                            "label": cond_label,
                            "effect_json": cond_efx,
                            "duration_rounds": duration,
                            "applied_at": "weapon_hit",
                            "runtime": {},
                        })
                        cond_applied.append(cond_key)
                    narrative_parts.append(
                        f"Rzut obronny {stat} nieudany ({save_total}<{dc}): {cond_label} ({duration} rundy)"
                    )
            else:
                narrative_parts.append(f"Rzut obronny {stat} udany ({save_total}≥{dc})")

    return {
        "extra_damage": total_extra,
        "conditions_applied": cond_applied,
        "weapon_effect_narrative": "; ".join(narrative_parts) if narrative_parts else "",
    }


def _decode_effect_json(raw: Any) -> dict[str, Any] | None:
    if raw is None:
        return None
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        s = raw.strip()
        if not s:
            return None
        try:
            parsed = json.loads(s)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None
    return None


def _condition_effects(condition: dict[str, Any]) -> list[dict[str, Any]]:
    parsed = _decode_effect_json(condition.get("effect_json"))
    if not parsed:
        return []
    effects = parsed.get("effects")
    if not isinstance(effects, list):
        return []
    return [entry for entry in effects if isinstance(entry, dict)]


def _condition_effect_state(condition: dict[str, Any], effect_idx: int) -> dict[str, Any]:
    runtime = condition.get("runtime")
    if not isinstance(runtime, dict):
        runtime = {}
        condition["runtime"] = runtime
    effect_state = runtime.get("effect_state")
    if not isinstance(effect_state, dict):
        effect_state = {}
        runtime["effect_state"] = effect_state
    key = str(effect_idx)
    state = effect_state.get(key)
    if not isinstance(state, dict):
        state = {}
        effect_state[key] = state
    return state


def _condition_turn_marker(round_n: int, actor_id: str) -> str:
    return f"{int(round_n)}:{str(actor_id or '').strip()}"


def _combatant_stat_modifier(
    combatant: dict[str, Any],
    *,
    sheet: dict[str, Any] | None,
    stat: str | None,
) -> int:
    stat_key = str(stat or "").strip().upper()
    if not stat_key:
        return 0

    # base modifier from raw stat value
    base = 0
    if isinstance(sheet, dict):
        stats = sheet.get("stats") if isinstance(sheet.get("stats"), dict) else {}
        try:
            base = (int(stats.get(stat_key, 10) or 10) - 10) // 2
        except (TypeError, ValueError):
            pass
    else:
        stats = combatant.get("stats") if isinstance(combatant.get("stats"), dict) else {}
        try:
            if stat_key in stats:
                base = (int(stats.get(stat_key, 10) or 10) - 10) // 2
            elif stat_key == "DEX":
                base = int(combatant.get("dex_modifier") or 0)
        except (TypeError, ValueError):
            pass

    # fold in stat_mods from every active condition
    conditions: list[dict[str, Any]] = (
        _sheet_conditions(sheet)
        if isinstance(sheet, dict)
        else [c for c in (combatant.get("conditions") or []) if isinstance(c, dict)]
    )
    for cond in conditions:
        parsed = _decode_effect_json(cond.get("effect_json"))
        if not parsed:
            continue
        sm = parsed.get("stat_mods")
        if isinstance(sm, dict) and stat_key in sm:
            try:
                base += int(sm[stat_key])
            except (TypeError, ValueError):
                pass

    return base


def _condition_duration_rounds(expires: str) -> int | None:
    raw = str(expires or "").strip().lower()
    if not raw.startswith("duration_rounds:"):
        return None
    tail = raw.split(":", 1)[1].strip()
    if not tail.isdigit():
        return None
    rounds = int(tail)
    return rounds if rounds >= 1 else None


def _ability_stats_seven(sheet: dict) -> dict[str, int]:
    """STR–CHA from sheet.stats plus speed (7 numeric fields for combat snapshot)."""
    raw = sheet.get("stats")
    stats = raw if isinstance(raw, dict) else {}
    out: dict[str, int] = {}
    for k in ("STR", "DEX", "CON", "INT", "WIS", "CHA"):
        try:
            out[k] = int(stats.get(k, 10) or 10)
        except (TypeError, ValueError):
            out[k] = 10
    try:
        out["speed"] = int(sheet.get("speed", stats.get("speed", 30)) or 30)
    except (TypeError, ValueError):
        out["speed"] = 30
    return out


def roll_damage_dice(expr: str, mod: int = 0) -> int:
    """Roll NdM + mod; expr like '1d8', 'd6', '2d6'."""
    raw = (expr or "1d4").strip().lower()
    m = re.match(r"^(\d*)d(\d+)$", raw)
    if not m:
        return max(0, mod)
    n = int(m.group(1) or 1)
    sides = int(m.group(2))
    total = sum(random.randint(1, sides) for _ in range(max(1, n)))
    return max(0, total + mod)


def _enemy_slug(key: str, index: int) -> str:
    safe = re.sub(r"[^a-z0-9_]", "_", (key or "enemy").lower())
    return f"{safe}_{index:02d}"


def _parse_enemy_skills(raw: Any) -> dict[str, int]:
    try:
        parsed = json.loads(raw) if raw else {}
    except (TypeError, ValueError):
        return {}
    if not isinstance(parsed, dict):
        return {}
    out: dict[str, int] = {}
    for k, v in parsed.items():
        key = str(k).strip().lower()
        if not key:
            continue
        try:
            out[key] = int(v)
        except (TypeError, ValueError):
            continue
    return out


# ── Zone system (T34) ───────────────────────────────────────────────────────
# Two-zone combat model per docs/V2_ARCHITECTURE/04_MAGIC_RANGE_MAP.md §4:
#   ENGAGED — front line (melee scrum)
#   RANGED  — back line (archers, casters, kiters)
# Melee attacks require attacker and target in the same zone.
# Ranged attacks/spells work regardless (spell-specific target_zone still applies).

ZONE_ENGAGED = "engaged"
ZONE_RANGED = "ranged"

_RANGED_ENEMY_KEYWORDS = (
    "archer", "arch", "bowman", "crossbow", "mage", "magus", "wizard",
    "sorcerer", "warlock", "shaman", "priest", "cleric", "caster",
    "necromancer", "warlock", "witch", "scout_ranged", "sniper", "ranger",
    "łucznik", "kusznik", "mag", "czarodziej", "kapłan", "łucznicz",
)


def _default_zone_for_player(sheet: dict) -> str:
    """Warrior/melee builds start in engaged; Scholar/casters start in ranged."""
    arch = str((sheet or {}).get("archetype") or "").strip().lower()
    if arch == "scholar":
        return ZONE_RANGED
    return ZONE_ENGAGED


def _default_zone_for_enemy(enemy_key: str, label: str | None = None) -> str:
    """Heuristic: ranged enemies have keywords like archer/mage/shaman in key or label.
    Everything else is engaged (default melee combatant).

    Follow-up: replace with explicit game_config_enemies.default_zone column.
    """
    needle = f"{enemy_key or ''} {label or ''}".lower()
    return ZONE_RANGED if any(k in needle for k in _RANGED_ENEMY_KEYWORDS) else ZONE_ENGAGED


def _opposite_zone(z: str) -> str:
    return ZONE_RANGED if str(z) == ZONE_ENGAGED else ZONE_ENGAGED


def _ensure_zones(combatants: list[dict]) -> bool:
    """Backfill `zone` on existing combatant rows that pre-date the zone system.
    Returns True if any combatant was mutated (caller should persist)."""
    mutated = False
    for c in combatants:
        if not isinstance(c, dict):
            continue
        if c.get("zone"):
            continue
        if c.get("type") == "player":
            c["zone"] = ZONE_ENGAGED
        else:
            c["zone"] = _default_zone_for_enemy(c.get("enemy_key") or c.get("id") or "", c.get("name"))
        mutated = True
    return mutated


def _fetch_enemy_row(conn: sqlite3.Connection, key: str) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT key, label, hp_base, ac_base, attack_bonus, damage_die, dex_modifier,
               skills_json,
               tier,
               loot_table_key, drop_chance, COALESCE(xp_award, 0) AS xp_award
        FROM game_config_enemies
        WHERE key = ?
        """,
        (key,),
    ).fetchone()


def _infer_template_key_from_combatant_slug(combatant_id: str) -> str | None:
    """Combatant id like bandit_01 → template key bandit (matches initiate_combat slugging)."""
    s = (combatant_id or "").strip()
    m = re.match(r"^(.+)_(\d{2})$", s, re.I)
    if not m:
        return None
    base = m.group(1).strip().strip("_")
    return base.lower() if base else None


def _roll_card_enemy_identity(
    conn: sqlite3.Connection, enemy: dict, combatant_id: str
) -> tuple[str, str]:
    """
    Canonical enemy_key + display name for API / COMBAT_ROLL cards (game_config_enemies.label).
    Repairs legacy/generic combatant.enemy_key (e.g. \"enemy\") using slug inference.
    """
    ek = str(enemy.get("enemy_key") or "").strip()
    nm = str(enemy.get("name") or "").strip()

    def from_row(r: sqlite3.Row) -> tuple[str, str]:
        k = str(r["key"])
        lab = str(r["label"] or r["key"] or "").strip() or k
        return k, lab

    candidates: list[str] = []
    if ek and ek.lower() != "enemy":
        candidates.append(ek)
    inferred = _infer_template_key_from_combatant_slug(combatant_id)
    if inferred:
        candidates.append(inferred)

    seen: set[str] = set()
    for cand in candidates:
        cl = cand.lower()
        if cl in seen:
            continue
        seen.add(cl)
        row = _fetch_enemy_row(conn, cand)
        if row:
            return from_row(row)

    if inferred:
        return inferred, nm or "Nieznany wróg"
    if ek and ek.lower() != "enemy":
        return ek, nm or "Nieznany wróg"
    return (inferred or ek or "unknown"), nm or "Nieznany wróg"


def _parse_loot_pool_column(raw: Any) -> list[dict[str, Any]]:
    if raw is None or raw == "":
        return []
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(data, list):
        return []
    return [x for x in data if isinstance(x, dict)]


def _read_loot_pool_from_row(row: sqlite3.Row) -> list[dict[str, Any]]:
    if "loot_pool" not in row.keys():
        return []
    return _parse_loot_pool_column(row["loot_pool"])


def _preview_loot_from_roll_items(loot_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for raw in loot_items or []:
        if not isinstance(raw, dict):
            continue
        qty = max(1, int(raw.get("quantity") or 1))
        key = ""
        item_type = "item"
        if raw.get("weapon_key"):
            key = str(raw.get("weapon_key") or "").strip()
            item_type = "weapon"
        elif raw.get("consumable_key"):
            key = str(raw.get("consumable_key") or "").strip()
            item_type = "consumable"
        elif raw.get("item_key"):
            key = str(raw.get("item_key") or "").strip()
            item_type = "item"
        if not key:
            continue
        out.append(
            {
                "label": key.replace("_", " "),
                "item_type": item_type,
                "quantity": qty,
                "source": "loot",
                "key": key,
            }
        )
    return out


def _row_to_combat_dict(row: sqlite3.Row) -> dict[str, Any]:
    _combatants = json.loads(row["combatants"] or "[]")
    _ensure_zones(_combatants)  # backfill zone for pre-T34 combats; harmless if all set
    d: dict[str, Any] = {
        "id": row["id"],
        "campaign_id": row["campaign_id"],
        "character_id": row["character_id"],
        "round": int(row["round"] or 1),
        "turn_order": json.loads(row["turn_order"] or "[]"),
        "current_turn": row["current_turn"],
        "combatants": _combatants,
        "status": row["status"],
        "ended_reason": row["ended_reason"],
        "location_tag": row["location_tag"] if "location_tag" in row.keys() else None,
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
    if "loot_pool" in row.keys():
        d["loot_pool"] = _read_loot_pool_from_row(row)
    if "loot_persisted" in row.keys():
        d["loot_persisted"] = bool(int(row["loot_persisted"] or 0))
    if "post_combat_loot_json" in row.keys():
        d["claimed_loot"] = _parse_loot_pool_column(row["post_combat_loot_json"])
    return d


def load_combat_snapshot(campaign_id: int) -> dict[str, Any] | None:
    """Latest combat row for campaign (any status), or None."""
    try:
        with _conn() as conn:
            row = conn.execute(
                "SELECT * FROM active_combat WHERE campaign_id = ?",
                (campaign_id,),
            ).fetchone()
            if not row:
                return None
            return _row_to_combat_dict(row)
    except sqlite3.OperationalError:
        return None


def get_active_combat(campaign_id: int) -> dict[str, Any] | None:
    try:
        with _conn() as conn:
            row = conn.execute(
                "SELECT * FROM active_combat WHERE campaign_id = ? AND status = 'active'",
                (campaign_id,),
            ).fetchone()
            if not row:
                return None
            return _row_to_combat_dict(row)
    except sqlite3.OperationalError:
        return None


# ── Stage 3 Z4: apply a condition to a combatant by enemy_key/name ─────────

def apply_condition_to_combatant(
    campaign_id: int, enemy_ref: str, condition_key: str,
) -> dict[str, Any]:
    """Find combatant by enemy_key/name (case-insensitive contains match),
    add the condition to its conditions list, persist combat row.

    Returns `{ok: bool, matched: enemy_key|None, reason: str}`.
    """
    if not enemy_ref or not condition_key:
        return {"ok": False, "matched": None, "reason": "missing_args"}
    snap = get_active_combat(campaign_id)
    if not snap:
        return {"ok": False, "matched": None, "reason": "no_active_combat"}
    combatants = snap.get("combatants") or []
    ref_lo = enemy_ref.strip().lower()
    matched = None
    for c in combatants:
        if not isinstance(c, dict) or c.get("type") == "player":
            continue
        if int(c.get("hp_current", 0) or 0) <= 0:
            continue
        ek = str(c.get("enemy_key", "")).lower()
        nm = str(c.get("name", "")).lower()
        if ref_lo == ek or ref_lo == nm or ref_lo in ek or ref_lo in nm:
            matched = c
            break
    if not matched:
        return {"ok": False, "matched": None, "reason": "enemy_not_found"}
    conds = matched.get("conditions") or []
    if not isinstance(conds, list):
        conds = []
    if any(isinstance(c, dict) and str(c.get("key", "")).lower() == condition_key.lower() for c in conds):
        return {"ok": True, "matched": matched.get("enemy_key"), "reason": "already_present"}
    # Look up label from config (best-effort)
    label = condition_key.title()
    try:
        with _conn() as _c2:
            r = _c2.execute(
                "SELECT label FROM game_config_conditions WHERE key = ? AND is_active = 1",
                (condition_key,),
            ).fetchone()
            if r and r["label"]:
                label = str(r["label"])
    except Exception:
        pass
    conds.append({"key": condition_key.lower(), "label": label, "runtime": {}})
    matched["conditions"] = conds
    # Persist
    try:
        with _conn() as conn:
            _save_combat_row(
                conn, campaign_id,
                character_id=int(snap.get("character_id") or 0),
                round_n=int(snap.get("round") or 1),
                turn_order=list(snap.get("turn_order") or []),
                current_turn=str(snap.get("current_turn") or ""),
                combatants=list(combatants),
                status=str(snap.get("status") or "active"),
                ended_reason=snap.get("ended_reason"),
                location_tag=snap.get("location_tag"),
            )
            conn.commit()
    except Exception as e:
        return {"ok": False, "matched": matched.get("enemy_key"), "reason": f"persist_error:{e}"}
    return {"ok": True, "matched": matched.get("enemy_key"), "reason": "applied"}


def get_enemy_catalog_for_prompt(conn: sqlite3.Connection) -> str:
    """
    Plain-text list of active enemies for system prompt injection (DB-driven keys).
    Returns "" if none or on read errors.
    """
    max_chars = 1500
    try:
        rows = conn.execute(
            """
            SELECT key, label, hp_base, damage_die, attack_bonus
            FROM game_config_enemies
            WHERE is_active = 1
            ORDER BY hp_base ASC, key ASC
            """
        ).fetchall()
    except sqlite3.OperationalError:
        return ""
    if not rows:
        return ""
    header = (
        "Dostępni wrogowie w tym świecie (używaj ich kluczy w [COMBAT_START:]):\n"
        "Lista pochodzi z bazy — preferuj te klucze zamiast wyłącznie przykładów ze statycznego promptu."
    )
    lines: list[str] = [header]
    for row in rows:
        key = str(row["key"])
        label = str(row["label"] or key)
        hp = int(row["hp_base"] or 0)
        die = str(row["damage_die"] or "1d4")
        atk = int(row["attack_bonus"] if row["attack_bonus"] is not None else 0)
        sign = "+" if atk >= 0 else ""
        lines.append(f"- {key} ({label}) — HP: {hp}, atak: {die}{sign}{atk}")
    out = "\n".join(lines)
    if len(out) <= max_chars:
        return out
    trimmed = out[: max_chars - 40].rstrip()
    return f"{trimmed}\n\n[... skrócono listę wrogów do {max_chars} znaków ...]"


def get_item_catalog_for_prompt(conn: sqlite3.Connection) -> str:
    """
    Plain-text [ITEM CATALOG] for system prompt injection (8H-4).
    Active + approved items only; skips narrative (campaign-specific).
    """
    max_chars = 2000
    try:
        rows = conn.execute(
            """
            SELECT key, label, item_type, value_gp,
                   effect_json, charges, ac_bonus, description
            FROM game_config_items
            WHERE is_active = 1 AND COALESCE(approved, 1) = 1
              AND item_type != 'narrative'
            ORDER BY item_type ASC, key ASC
            LIMIT 60
            """
        ).fetchall()
    except sqlite3.OperationalError:
        return ""
    if not rows:
        return ""
    lines: list[str] = ["[ITEM CATALOG]"]
    current_type: str | None = None
    for r in rows:
        t = str(r["item_type"] or "misc").strip().lower() or "misc"
        if t != current_type:
            current_type = t
            lines.append(f"  [{t.upper()}]")
        key = str(r["key"])
        label = str(r["label"] or key)
        parts: list[str] = [f"    - {key}: {label}"]

        if t == "armor" and r["ac_bonus"] is not None and int(r["ac_bonus"] or 0) > 0:
            parts.append(f"(AC +{int(r['ac_bonus'])})")

        if t == "consumable":
            legacy = legacy_effect_fields_from_json(r["effect_json"]) or {}
            eff = str(legacy.get("effect_type") or "misc")
            dice = str(legacy.get("effect_dice") or "").strip()
            bonus = int(legacy.get("effect_bonus") or 0)
            target = str(legacy.get("effect_target") or "self")
            effect_str = eff
            if dice:
                effect_str += f" {dice}"
            if bonus:
                effect_str += f" +{bonus}"
            effect_str += f" [{target}]"
            charges = int(r["charges"] or 1)
            if charges != 1:
                effect_str += f" x{charges}"
            parts.append(f"({effect_str})")

        vgp = int(r["value_gp"] or 0)
        if vgp:
            parts.append(f"{vgp} gp")

        lines.append(" ".join(parts))

    out = "\n".join(lines)
    if len(out) <= max_chars:
        return out
    trimmed = out[: max_chars - 50].rstrip()
    return f"{trimmed}\n\n[... skrócono katalog przedmiotów ...]"


def get_combat_context_for_prompt(campaign_id: int) -> str | None:
    st = get_active_combat(campaign_id)
    if not st or st.get("status") != "active":
        return None
    lines = [
        f"== ACTIVE COMBAT (Round {st['round']}) ==",
        f"Turn: {st['current_turn']}",
        "Combatants:",
    ]
    for c in st.get("combatants") or []:
        if not isinstance(c, dict):
            continue
        cid = c.get("id", "?")
        name = c.get("name", "?")
        hp_c = c.get("hp_current", 0)
        hp_m = c.get("hp_max", 0)
        df = c.get("defense", 0)
        cond = c.get("conditions") or []
        cond_s = ", ".join(str(x) for x in cond) if cond else "[]"
        lines.append(f"- {name} [{cid}]: HP {hp_c}/{hp_m}, DEF {df}, Conditions: {cond_s}")
    lines.append(
        "Rules: player attacks when it is their turn. Enemy attacks resolve after the player "
        "when using the enemy-turn endpoint. DO NOT invent HP values — use only this block."
    )
    return "\n".join(lines)


def log_combat_turn(
    conn: sqlite3.Connection,
    *,
    combat_id: int,
    campaign_id: int,
    turn_number: float,
    actor: str,
    event_type: str,
    roll_value: int | None = None,
    damage: int | None = None,
    hp_after: int | None = None,
    target_id: str | None = None,
    target_name: str | None = None,
    hit: bool | None = None,
    narrative: str | None = None,
) -> None:
    hit_sql: int | None
    if hit is None:
        hit_sql = None
    else:
        hit_sql = 1 if hit else 0
    conn.execute(
        """
        INSERT INTO combat_turns (
            combat_id, campaign_id, turn_number, actor, event_type,
            roll_value, damage, hp_after, target_id, target_name, hit, narrative
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            combat_id,
            campaign_id,
            turn_number,
            actor,
            event_type,
            roll_value,
            damage,
            hp_after,
            target_id,
            target_name,
            hit_sql,
            narrative,
        ),
    )


def _next_combat_log_sequence(conn: sqlite3.Connection, combat_id: int) -> float:
    row = conn.execute(
        "SELECT MAX(turn_number) AS m FROM combat_turns WHERE combat_id = ?",
        (combat_id,),
    ).fetchone()
    mx = row["m"]
    base = float(mx) if mx is not None else 0.0
    return base + 0.001


def _log_combat_end_event(conn: sqlite3.Connection, row: sqlite3.Row, reason: str) -> None:
    cid = int(row["id"])
    camp = int(row["campaign_id"])
    tn = _next_combat_log_sequence(conn, cid)
    evt = "flee" if reason == "fled" else "end"
    log_combat_turn(
        conn,
        combat_id=cid,
        campaign_id=camp,
        turn_number=tn,
        actor="system",
        event_type=evt,
        narrative=f"Walka zakończona: {reason}",
    )
    logger.info(
        "combat_ended",
        combat_id=cid,
        campaign_id=camp,
        ended_reason=reason,
    )


def evaluate_current_turn_conditions(campaign_id: int) -> dict[str, Any]:
    """
    T24: process runtime `effect_json` condition effects for the actor whose turn is active.

    Supported minimal set:
    - `periodic_save`
    - `block_action`

    Effects are processed once per actor-turn. Successful `periodic_save` with
    `expires=save_success` removes the condition before checking `block_action`.
    """
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM active_combat WHERE campaign_id = ? AND status = 'active'",
            (campaign_id,),
        ).fetchone()
        if not row:
            return {"blocked": False, "events": [], "combat_state": None}

        combatants: list[dict[str, Any]] = json.loads(row["combatants"] or "[]")
        actor_id = str(row["current_turn"] or "").strip()
        round_n = int(row["round"] or 1)
        actor = _find_combatant(combatants, actor_id)
        if not actor or int(actor.get("hp_current", 0) or 0) <= 0:
            return {
                "blocked": False,
                "actor_id": actor_id,
                "events": [],
                "combat_state": _row_to_combat_dict(row),
            }

        actor_type = str(actor.get("type") or "").strip().lower()
        sheet: dict[str, Any] | None = None
        if actor_type == "player":
            ch_row = conn.execute(
                "SELECT sheet_json FROM characters WHERE id = ? LIMIT 1",
                (int(row["character_id"]),),
            ).fetchone()
            if ch_row:
                sheet = parse_character_sheet(ch_row["sheet_json"])
                if not isinstance(sheet, dict):
                    sheet = {}

        source_conditions = actor.get("conditions") or []
        conditions: list[dict[str, Any]] = []
        for entry in source_conditions:
            if isinstance(entry, dict):
                conditions.append(dict(entry))

        events: list[dict[str, Any]] = []
        blocked = False
        conditions_changed = False
        runtime_changed = False
        next_conditions: list[dict[str, Any]] = []
        marker = _condition_turn_marker(round_n, actor_id)

        for condition in conditions:
            key = str(condition.get("key") or "").strip().lower()
            label = str(condition.get("label") or key or "warunek").strip() or "warunek"
            effects = _condition_effects(condition)
            remove_condition = False

            for effect_idx, effect in enumerate(effects):
                effect_type = str(effect.get("type") or "").strip().lower()
                if effect_type != "periodic_save":
                    continue
                tick = str(effect.get("tick") or "").strip().lower()
                if tick not in {"start_turn", "each_round"}:
                    continue
                state = _condition_effect_state(condition, effect_idx)
                if str(state.get("last_turn_marker") or "") == marker:
                    continue
                state["last_turn_marker"] = marker
                runtime_changed = True

                stat_key = str(effect.get("stat") or "").strip().upper() or None
                modifier = _combatant_stat_modifier(actor, sheet=sheet, stat=stat_key)
                raw_roll = int(roll_d20())
                dc_value = resolve_dc_for_roll(effect.get("dc_key") or effect.get("value"))
                dc_final = int(dc_value or 0)
                total = int(raw_roll) + int(modifier)
                success = raw_roll == 20 or (raw_roll != 1 and total >= dc_final)
                state["last_raw_roll"] = int(raw_roll)
                state["last_total"] = int(total)
                state["last_dc"] = int(dc_final)
                state["last_success"] = bool(success)

                events.append(
                    {
                        "type": "periodic_save",
                        "condition_key": key,
                        "condition_label": label,
                        "stat": stat_key,
                        "raw_roll": int(raw_roll),
                        "modifier": int(modifier),
                        "total": int(total),
                        "dc": int(dc_final),
                        "success": bool(success),
                    }
                )

                expires = str(effect.get("expires") or "").strip().lower()
                duration_rounds = _condition_duration_rounds(expires)
                if duration_rounds is not None:
                    remaining = state.get("remaining_rounds")
                    if not isinstance(remaining, int) or remaining < 1:
                        remaining = duration_rounds
                    remaining -= 1
                    state["remaining_rounds"] = remaining
                    runtime_changed = True
                    if remaining <= 0:
                        remove_condition = True

                if success and expires == "save_success":
                    remove_condition = True

                if remove_condition:
                    events.append(
                        {
                            "type": "condition_removed",
                            "condition_key": key,
                            "condition_label": label,
                            "reason": "save_success" if success and expires == "save_success" else "duration_expired",
                        }
                    )
                    conditions_changed = True
                    break

            # Duration countdown (for conditions applied via weapon effect_json)
            dur = condition.get("duration_rounds")
            if isinstance(dur, int) and dur > 0:
                leg_state = _condition_effect_state(condition, "duration_tick")
                if str(leg_state.get("last_turn_marker") or "") != marker:
                    leg_state["last_turn_marker"] = marker
                    runtime_changed = True
                    condition["duration_rounds"] = dur - 1
                    if condition["duration_rounds"] <= 0:
                        remove_condition = True
                        events.append({
                            "type": "condition_removed",
                            "condition_key": key,
                            "condition_label": label,
                        })
                        conditions_changed = True

            if remove_condition:
                continue

            for effect in effects:
                effect_type = str(effect.get("type") or "").strip().lower()
                if effect_type != "block_action":
                    continue
                blocked = True
                events.append(
                    {
                        "type": "block_action",
                        "condition_key": key,
                        "condition_label": label,
                    }
                )

            # Legacy condition format: skip_turn and damage_per_turn
            # (game_config_conditions uses {"skip_turn":true,"damage_per_turn":N,...})
            if not effects:
                legacy = _decode_effect_json(condition.get("effect_json"))
                if isinstance(legacy, dict):
                    leg_state = _condition_effect_state(condition, "legacy_tick")
                    already_ticked = str(leg_state.get("last_turn_marker") or "") == marker
                    if not already_ticked:
                        leg_state["last_turn_marker"] = marker
                        runtime_changed = True

                        if legacy.get("skip_turn"):
                            blocked = True
                            events.append({
                                "type": "block_action",
                                "condition_key": key,
                                "condition_label": label,
                            })

                        dpt = legacy.get("damage_per_turn")
                        if dpt and isinstance(dpt, (int, float)) and dpt > 0:
                            dmg = int(dpt)
                            prev_hp = int(actor.get("hp_current", 0) or 0)
                            actor["hp_current"] = max(0, prev_hp - dmg)
                            dtype = str(legacy.get("damage_type") or "physical")
                            events.append({
                                "type": "condition_damage",
                                "condition_key": key,
                                "condition_label": label,
                                "damage": dmg,
                                "damage_type": dtype,
                                "hp_after": int(actor.get("hp_current", 0)),
                            })
                            conditions_changed = True

            next_conditions.append(condition)

        if conditions_changed or runtime_changed:
            actor["conditions"] = next_conditions
            _persist_combatants(conn, row, combatants)

        if conditions_changed and actor_type == "player" and isinstance(sheet, dict):
            stripped_conditions: list[dict[str, Any]] = []
            for condition in next_conditions:
                stripped_conditions.append(
                    {
                        "key": condition.get("key"),
                        "label": condition.get("label"),
                        "effect_json": condition.get("effect_json"),
                        "source_item_key": condition.get("source_item_key"),
                        "applied_at": condition.get("applied_at"),
                    }
                )
            sheet["conditions"] = stripped_conditions
            conn.execute(
                "UPDATE characters SET sheet_json = ? WHERE id = ?",
                (json.dumps(sheet, ensure_ascii=False), int(row["character_id"])),
            )

        if events:
            combat_id = int(row["id"])
            for event in events:
                event_type = str(event.get("type") or "condition")
                narrative = ""
                if event_type == "periodic_save":
                    verdict = "sukces" if event.get("success") else "porażka"
                    stat_label = str(event.get("stat") or "save")
                    narrative = (
                        f"{event['condition_label']}: rzut obronny {stat_label} "
                        f"{event['total']} vs DC {event['dc']} ({verdict})."
                    )
                elif event_type == "condition_removed":
                    narrative = f"{event['condition_label']}: efekt ustępuje."
                elif event_type == "block_action":
                    narrative = f"{event['condition_label']}: akcja zablokowana w tej turze."
                elif event_type == "condition_damage":
                    dtype = str(event.get("damage_type") or "")
                    dtype_label = {"fire": "ogień", "poison": "trucizna", "physical": "obrażenia fizyczne", "cold": "zimno", "lightning": "błyskawica"}.get(dtype, dtype)
                    narrative = f"{event['condition_label']}: {event['damage']} obrażeń ({dtype_label}). HP po: {event['hp_after']}."
                log_combat_turn(
                    conn,
                    combat_id=combat_id,
                    campaign_id=int(campaign_id),
                    turn_number=_next_combat_log_sequence(conn, combat_id),
                    actor=actor_id or actor_type or "system",
                    event_type=event_type,
                    target_id=actor_id or None,
                    target_name=str(actor.get("name") or actor_id or "") or None,
                    hit=None,
                    narrative=narrative,
                )

        conn.commit()

    combat_state = load_combat_snapshot(campaign_id)
    message_lines: list[str] = []
    for event in events:
        event_type = str(event.get("type") or "")
        if event_type == "periodic_save":
            verdict = "sukces" if event.get("success") else "porażka"
            stat_label = str(event.get("stat") or "save")
            message_lines.append(
                f"{event['condition_label']}: rzut obronny {stat_label} "
                f"{event['total']} vs DC {event['dc']} ({verdict})."
            )
        elif event_type == "condition_removed":
            message_lines.append(f"{event['condition_label']}: efekt ustępuje.")
        elif event_type == "block_action":
            message_lines.append(f"{event['condition_label']}: nie możesz wykonać akcji w tej turze.")

    return {
        "blocked": bool(blocked),
        "actor_id": actor_id,
        "actor_type": actor_type,
        "events": events,
        "message": "\n".join(message_lines).strip(),
        "combat_state": combat_state,
    }


def list_combat_turns_for_campaign(campaign_id: int, limit: int = 50) -> list[dict[str, Any]]:
    snap = load_combat_snapshot(campaign_id)
    if not snap:
        return []
    combat_id = int(snap["id"])
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT * FROM combat_turns
            WHERE combat_id = ?
            ORDER BY turn_number ASC, id ASC
            LIMIT ?
            """,
            (combat_id, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def list_all_combat_turns_for_campaign(campaign_id: int, limit: int = 500) -> list[dict[str, Any]]:
    """All combat_turns rows for the campaign across every combat (active + ended).
    Used by the player UI to rehydrate roll bubbles after F5."""
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT * FROM combat_turns
            WHERE campaign_id = ?
            ORDER BY id ASC
            LIMIT ?
            """,
            (campaign_id, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def get_combat_turns_context_for_prompt(campaign_id: int, last_n: int = 8) -> str | None:
    """Last N combat log rows for LLM (active combat only — caller should gate)."""
    st = get_active_combat(campaign_id)
    if not st or str(st.get("status") or "") != "active":
        return None
    combat_id = int(st["id"])
    with _conn() as conn:
        try:
            rows = conn.execute(
                """
                SELECT actor, event_type, roll_value, damage, hp_after, target_name, hit, narrative
                FROM combat_turns
                WHERE combat_id = ?
                ORDER BY turn_number DESC, id DESC
                LIMIT ?
                """,
                (combat_id, last_n),
            ).fetchall()
        except sqlite3.OperationalError:
            return None
    if not rows:
        return None
    lines = ["== HISTORIA WALKI (ostatnie zdarzenia w silniku) =="]
    for r in reversed(rows):
        h = r["hit"]
        if h == 1:
            hit_str = "TRAFIENIE"
        elif h == 0:
            hit_str = "PUDŁO"
        else:
            hit_str = ""
        dmg = r["damage"]
        hp_a = r["hp_after"]
        dmg_part = ""
        if dmg is not None and hp_a is not None:
            dmg_part = f", {dmg} obrażeń → HP po: {hp_a}"
        elif dmg is not None:
            dmg_part = f", {dmg} obrażeń"
        rv = r["roll_value"]
        rv_s = f"roll={rv}" if rv is not None else ""
        tgt = r["target_name"] or "?"
        lines.append(
            f"[{str(r['actor'] or '').upper()}] {r['event_type']} {rv_s} {hit_str}{dmg_part} cel={tgt}".strip()
        )
    return "\n".join(lines)


def _save_combat_row(
    conn: sqlite3.Connection,
    campaign_id: int,
    *,
    character_id: int,
    round_n: int,
    turn_order: list[str],
    current_turn: str,
    combatants: list[dict],
    status: str = "active",
    ended_reason: str | None = None,
    location_tag: str | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO active_combat (
          campaign_id, character_id, round, turn_order, current_turn, combatants,
          status, ended_reason, location_tag, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(campaign_id) DO UPDATE SET
          character_id = excluded.character_id,
          round = excluded.round,
          turn_order = excluded.turn_order,
          current_turn = excluded.current_turn,
          combatants = excluded.combatants,
          status = excluded.status,
          ended_reason = excluded.ended_reason,
          location_tag = excluded.location_tag,
          updated_at = excluded.updated_at
        """,
        (
            campaign_id,
            character_id,
            round_n,
            json.dumps(turn_order, ensure_ascii=False),
            current_turn,
            json.dumps(combatants, ensure_ascii=False),
            status,
            ended_reason,
            location_tag,
            _now_iso(),
        ),
    )


def initiate_combat(campaign_id: int, character_id: int, enemy_keys: list[str]) -> dict[str, Any]:
    if not enemy_keys:
        raise ValueError("enemy_keys required")

    with _conn() as conn:
        camp = conn.execute("SELECT id FROM campaigns WHERE id = ?", (campaign_id,)).fetchone()
        if not camp:
            raise ValueError("campaign not found")

        ch = conn.execute(
            "SELECT id, name, sheet_json FROM characters WHERE id = ? AND campaign_id = ?",
            (character_id, campaign_id),
        ).fetchone()
        if not ch:
            raise ValueError("character not found")

        sheet = parse_character_sheet(ch["sheet_json"])
        from app.services.xp_service import get_hero_level
        player_level = get_hero_level(sheet)
        hp_cur, hp_max = _player_hp_pair(sheet)
        ac = _player_ac_from_sheet(sheet)
        # Add equipped armor AC bonus from inventory
        try:
            armor_row = conn.execute(
                """SELECT gi.ac_bonus FROM character_inventory ci
                   JOIN game_config_items gi ON gi.key = ci.item_key
                   WHERE ci.character_id = ? AND ci.equipped = 1
                     AND gi.item_type = 'armor' AND gi.ac_bonus > 0
                   ORDER BY gi.ac_bonus DESC LIMIT 1""",
                (character_id,),
            ).fetchone()
            if armor_row:
                ac += int(armor_row[0] or 0)
        except Exception:
            pass
        dex_mod = _stat_mod(sheet, "DEX")
        init_player = roll_d20() + dex_mod
        ability_stats = _ability_stats_seven(sheet)

        combatants: list[dict[str, Any]] = [
            {
                "id": "player",
                "type": "player",
                "name": (ch["name"] or "Hero").strip(),
                "hp_current": hp_cur,
                "hp_max": hp_max,
                "defense": ac,
                "stats": ability_stats,
                "initiative_roll": init_player,
                "conditions": _sheet_conditions(sheet),
                "zone": _default_zone_for_player(sheet),
            }
        ]

        resolved_enemies: list[tuple[str, sqlite3.Row]] = []
        for ek in enemy_keys:
            er = _fetch_enemy_row(conn, ek)
            if not er:
                logger.warning(
                    "combat_unknown_enemy_key",
                    enemy_key=ek,
                    campaign_id=campaign_id,
                    message="[COMBAT] unknown enemy key, skipping",
                )
                continue
            resolved_enemies.append((ek, er))

        if not resolved_enemies:
            raise ValueError("no valid enemy keys after filtering unknown templates")

        turn_slots: list[tuple[str, int, int]] = [("player", init_player, 0)]
        idx = 0
        for ek, er in resolved_enemies:
            idx += 1
            slug = _enemy_slug(ek, idx)
            hp_max_e = max(1, round(int(er["hp_base"] or 1) * (1.0 + 0.1 * (player_level - 1))))
            ac_e = int(er["ac_base"] or 10) + (player_level - 1) // 3
            dex_e_mod = int(er["dex_modifier"] or 0)
            init_e = roll_d20() + dex_e_mod
            xp_award_e = 0
            try:
                xp_award_e = int(er["xp_award"] or 0)
            except (KeyError, IndexError, TypeError, ValueError):
                xp_award_e = 0
            combatants.append(
                {
                    "id": slug,
                    "type": "enemy",
                    "enemy_key": er["key"],
                    "name": (er["label"] or er["key"]).strip(),
                    "hp_current": hp_max_e,
                    "hp_max": hp_max_e,
                    "defense": ac_e,
                    "attack_bonus": int(er["attack_bonus"] or 0),
                    "dex_modifier": int(er["dex_modifier"] or 0),
                    "damage_dice": (er["damage_die"] or "1d6").strip().lower(),
                    "damage_stat": "STR",
                    "initiative_roll": init_e,
                    "conditions": [],
                    "loot_table_key": er["loot_table_key"],
                    "drop_chance": float(er["drop_chance"] if er["drop_chance"] is not None else 1.0),
                    "xp_award": xp_award_e,
                    "tier": str(er["tier"] or "standard"),
                    "zone": _default_zone_for_enemy(er["key"], er["label"]),
                    "damage_bonus": (player_level - 1) // 2,
                    # Stored now for opposed checks in upcoming [S1b] formulas (T30).
                    "skills": _parse_enemy_skills(er["skills_json"]),
                }
            )
            turn_slots.append((slug, init_e, idx))

        # Sort: highest initiative first; ties: player wins (lower tie-break value sorts first after negating init)
        turn_slots.sort(key=lambda t: (-t[1], 0 if t[0] == "player" else 1))
        turn_order = [t[0] for t in turn_slots]
        current = turn_order[0] if turn_order else "player"

        conn.execute("DELETE FROM active_combat WHERE campaign_id = ?", (campaign_id,))
        _save_combat_row(
            conn,
            campaign_id,
            character_id=character_id,
            round_n=1,
            turn_order=turn_order,
            current_turn=current,
            combatants=combatants,
            status="active",
            ended_reason=None,
            location_tag=None,
        )
        conn.commit()

        id_row = conn.execute(
            "SELECT id FROM active_combat WHERE campaign_id = ?",
            (campaign_id,),
        ).fetchone()
        if id_row:
            combat_id_int = int(id_row["id"])
            log_combat_turn(
                conn,
                combat_id=combat_id_int,
                campaign_id=campaign_id,
                turn_number=0.0,
                actor="system",
                event_type="start",
                narrative=f"Walka rozpoczęta. Wrogowie: {', '.join(k for k, _ in resolved_enemies)}",
            )
            for actor_id, init_total, _tie in turn_slots:
                tn = _next_combat_log_sequence(conn, combat_id_int)
                log_combat_turn(
                    conn,
                    combat_id=combat_id_int,
                    campaign_id=campaign_id,
                    turn_number=tn,
                    actor=str(actor_id),
                    event_type="initiative",
                    roll_value=int(init_total),
                    narrative=f"Inicjatywa: {actor_id} → wynik {int(init_total)}",
                )
        conn.commit()

    out = get_active_combat(campaign_id)
    if not out:
        raise RuntimeError("failed to load combat after insert")
    started_keys = [k for k, _ in resolved_enemies]
    logger.info(
        "combat_start",
        campaign_id=campaign_id,
        enemy=",".join(started_keys),
        enemy_keys=started_keys,
        combat_id=out.get("id"),
    )
    return out


def _find_combatant(combatants: list[dict], cid: str) -> dict | None:
    for c in combatants:
        if c.get("id") == cid:
            return c
    return None


def _living_enemy_ids(combatants: list[dict]) -> list[str]:
    out = []
    for c in combatants:
        if c.get("type") != "enemy":
            continue
        if int(c.get("hp_current", 0) or 0) > 0:
            out.append(str(c["id"]))
    return out


def _all_enemies_dead(combatants: list[dict]) -> bool:
    for c in combatants:
        if c.get("type") != "enemy":
            continue
        if int(c.get("hp_current", 0) or 0) > 0:
            return False
    return True


def compute_player_attack_dodge_outcome(
    attack_total: int,
    dodge_roll_raw: int,
    dex_modifier: int,
    player_raw_d20: int | None,
) -> tuple[bool, bool, int]:
    """
    Player attack total vs enemy d20+dex dodge. Returns (dodged, hit, dodge_total).
    nat1: auto miss (no hit). nat20: auto hit (not dodged). Else: defender wins ties
    (dodged when dodge_total >= attack_total).
    """
    dodge_total = int(dodge_roll_raw) + int(dex_modifier or 0)
    atk = int(attack_total)
    if player_raw_d20 is not None:
        pr = int(player_raw_d20)
        if pr == 1:
            return True, False, dodge_total
        if pr == 20:
            return False, True, dodge_total
    dodged = dodge_total >= atk
    return dodged, (not dodged), dodge_total


def resolve_attack(
    campaign_id: int,
    roll_result: int | None,
    attacker: str = "player",
    raw_d20: int | None = None,
    spell_key: str | None = None,
) -> dict[str, Any]:
    """
    attacker: 'player' uses roll_result as total attack vs enemy dodge roll.
    attacker: 'enemy' ignores roll_result; rolls d20+attack_bonus internally vs player AC.
    """
    turn_effects = evaluate_current_turn_conditions(campaign_id)
    if turn_effects.get("blocked"):
        blocked_actor = str(turn_effects.get("actor_id") or "").strip()
        blocked_for_attacker = (attacker == "player" and blocked_actor == "player") or (
            attacker == "enemy" and blocked_actor and blocked_actor != "player"
        )
        if blocked_for_attacker:
            return {
                "attacker": attacker,
                "hit": False,
                "blocked": True,
                "message": str(turn_effects.get("message") or "Akcja zablokowana."),
                "condition_events": turn_effects.get("events") or [],
                "combat_state": turn_effects.get("combat_state"),
            }

    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM active_combat WHERE campaign_id = ? AND status = 'active'",
            (campaign_id,),
        ).fetchone()
        if not row:
            raise ValueError("no active combat")

        combatants: list[dict] = json.loads(row["combatants"] or "[]")
        loot_pool_accum: list[dict[str, Any]] = _read_loot_pool_from_row(row)
        ch_id = int(row["character_id"])
        character = conn.execute(
            "SELECT id, sheet_json FROM characters WHERE id = ?",
            (ch_id,),
        ).fetchone()
        if not character:
            raise ValueError("character missing")

        sheet = parse_character_sheet(character["sheet_json"])
        out: dict[str, Any] = {"attacker": attacker, "hit": False}

        if attacker == "player":
            living = _living_enemy_ids(combatants)
            if not living:
                out["message"] = "no living enemies"
                out["combat_state"] = _row_to_combat_dict(row)
                return out

            # ── Zone gating: prefer same-zone targets for melee, any-zone for ranged ──
            _ensure_zones(combatants)
            p_zone = str((_find_combatant(combatants, "player") or {}).get("zone") or ZONE_ENGAGED)
            _resolved_weapon_for_zone = (
                "spell" if spell_key else (
                    "spell" if str(sheet.get("archetype") or "").strip().lower() == "scholar"
                    else str((resolve_sheet_weapon(conn, sheet, ch_id) or {}).get("weapon_type") or "melee").lower()
                )
            )
            _melee = _resolved_weapon_for_zone == "melee"

            order = json.loads(row["turn_order"] or "[]")
            target_id = None
            if _melee:
                for tid in order:
                    if tid not in living:
                        continue
                    c = _find_combatant(combatants, tid)
                    if c and str(c.get("zone") or ZONE_ENGAGED) == p_zone:
                        target_id = tid
                        break
                if not target_id:
                    out["hit"] = False
                    out["blocked"] = True
                    out["block_reason"] = "out_of_range"
                    out["message"] = "Cele są poza zasięgiem walki wręcz. Zbliż się lub użyj broni dystansowej."
                    out["combat_state"] = _row_to_combat_dict(row)
                    return out
            else:
                for tid in order:
                    if tid in living:
                        target_id = tid
                        break
                if not target_id:
                    target_id = living[0]

            enemy = _find_combatant(combatants, target_id)
            if not enemy:
                raise ValueError("enemy combatant missing")

            card_key, card_name = _roll_card_enemy_identity(conn, enemy, str(target_id))
            old_ek = str(enemy.get("enemy_key") or "").strip().lower()
            if old_ek in ("", "enemy"):
                enemy["enemy_key"] = card_key
            old_nm = str(enemy.get("name") or "").strip().lower()
            if old_nm in ("", "wróg", "wrog", "enemy"):
                enemy["name"] = card_name

            # If spell_key provided, override weapon with spell stats
            if spell_key:
                spell_weapon = conn.execute(
                    "SELECT key, label, mana_cost, damage_die, spell_type, tier FROM game_config_spells WHERE key = ? AND is_active = 1",
                    (spell_key,),
                ).fetchone()
                if spell_weapon:
                    weapon_row = {
                        "key": spell_weapon["key"],
                        "label": spell_weapon["label"],
                        "weapon_type": "spell",
                        "damage_die": spell_weapon["damage_die"] or "2d6",
                        "mana_cost": spell_weapon["mana_cost"] or 2,
                        "linked_stat": "INT",
                        "attack_bonus": 0,
                        "damage_bonus": 0,
                    }
                else:
                    weapon_row = resolve_sheet_weapon(conn, sheet, ch_id)
            elif str(sheet.get("archetype") or "").strip().lower() == "scholar":
                # Scholar cantrip: free basic magic attack (1d4, INT-based, no mana cost)
                weapon_row = {
                    "key": "scholar_cantrip",
                    "label": "Atak Magiczny (kant.)",
                    "weapon_type": "spell",
                    "damage_die": "1d4",
                    "mana_cost": 0,        # FREE — this is the key balance fix
                    "linked_stat": "INT",
                    "attack_bonus": 0,
                    "damage_bonus": 0,
                }
            else:
                weapon_row = resolve_sheet_weapon(conn, sheet, ch_id)
            attack_roll: dict[str, Any] | None = None
            player_raw = int(raw_d20) if raw_d20 is not None else None
            if player_raw is not None:
                attack_roll = resolve_attack_roll_for_weapon(
                    sheet,
                    raw_roll=player_raw,
                    weapon_row=weapon_row,
                )
                out["attack_roll"] = attack_roll
                out["attack_test"] = str(attack_roll.get("test") or "")
                out["weapon_key"] = str(attack_roll.get("weapon_key") or "")
                out["weapon_label"] = str(attack_roll.get("weapon_label") or "")
                out["weapon_type"] = str(attack_roll.get("weapon_type") or "melee")
                if roll_result is None:
                    roll_result = int(attack_roll["total"])
            elif roll_result is None:
                raise ValueError("missing player attack roll")
            # Stage 3 Z2: surprise (zaskoczony) → +2 to attack total
            _surprise_fx = _apply_attack_bonuses(sheet, enemy)
            if _surprise_fx.get("atk_bonus"):
                roll_result = int(roll_result) + int(_surprise_fx["atk_bonus"])
                out["surprise_atk_bonus"] = int(_surprise_fx["atk_bonus"])
            player_nat20 = player_raw == 20
            player_nat1 = player_raw == 1
            dodge_roll: dict[str, Any] | None = None
            dodged = False
            hit = False
            if player_nat1:
                hit = False
                dodged = True
            else:
                raw_dodge = roll_d20()
                dex_mod = int(enemy.get("dex_modifier") or 0)
                dodged, hit, dodge_total = compute_player_attack_dodge_outcome(
                    int(roll_result or 0),
                    int(raw_dodge),
                    dex_mod,
                    player_raw,
                )
                dodge_roll = {
                    "raw": raw_dodge,
                    "modifier": dex_mod,
                    "total": dodge_total,
                    "dodged": dodged,
                    "player_roll": int(roll_result or 0),
                    "verdict": (
                        "hit"
                        if player_nat20
                        else (
                            "perfect_dodge"
                            if raw_dodge == 20
                            else (
                                "fumble_dodge"
                                if raw_dodge == 1
                                else ("dodged" if dodged else "hit")
                            )
                        )
                    ),
                }
            out["hit"] = hit
            out["dodged"] = dodged
            out["target_id"] = target_id
            out["target_name"] = card_name
            out["enemy_key"] = card_key
            out["attack_total"] = int(roll_result or 0)
            out["player_raw_d20"] = player_raw
            out["player_nat20"] = player_nat20
            out["player_nat1"] = player_nat1
            if dodge_roll is not None:
                out["dodge_roll"] = dodge_roll

            enemy_ac = int(enemy.get("defense", 0) or 0)
            _log_dice_roll_combat_resolve(
                source="combat_attack",
                campaign_id=campaign_id,
                result_total=int(roll_result or 0),
                dc=enemy_ac,
                hit=bool(hit),
                raw_d20=player_raw,
            )

            loot: list[dict] = []
            out["gold_drop"] = 0
            dmg = 0
            player_attack_log_meta = None
            if attack_roll:
                _meta: dict = {
                    "raw_d20": int(player_raw) if player_raw is not None else None,
                    "attack_test": str(attack_roll.get("test") or ""),
                    "attack_stat": str(attack_roll.get("attack_stat") or ""),
                    "attack_label": {
                        "melee_attack": "ATAK WRĘCZ",
                        "ranged_attack": "ATAK DYSTANSOWY",
                        "spell_attack": "KANTRYP MAGICZNY" if (weapon_row or {}).get("key") == "scholar_cantrip" else "ATAK MAGICZNY",
                    }.get(str(attack_roll.get("test") or ""), "ATAK"),
                    "modifier": int(attack_roll.get("modifier") or 0),
                    "total": int(attack_roll.get("total") or roll_result or 0),
                    "weapon_key": str(attack_roll.get("weapon_key") or ""),
                    "weapon_label": str(attack_roll.get("weapon_label") or ""),
                    "weapon_type": str(attack_roll.get("weapon_type") or ""),
                }
                if dodge_roll is not None:
                    _meta["dodged"] = bool(dodge_roll.get("dodged"))
                    _meta["dodge_total"] = int(dodge_roll.get("total") or 0)
                    _meta["dodge_raw"] = int(dodge_roll.get("raw") or 0)
                player_attack_log_meta = json.dumps(_meta, ensure_ascii=False)

            # ── Spell: detect spell_attack weapon + mana deduction ────────────
            _is_spell = str(
                (attack_roll or {}).get("weapon_type")
                or (str(weapon_row.get("weapon_type")) if weapon_row else "")
            ).lower() == "spell"
            # Cantrip (mana_cost=0) is free — skip mana check entirely
            _spell_mana_cost = int(weapon_row.get("mana_cost") or 0) if (_is_spell and weapon_row) else 0
            _is_free_cantrip = _is_spell and _spell_mana_cost == 0
            _mana_ok = True
            if _is_spell and not _is_free_cantrip:
                from app.services.spell_service import check_and_deduct_mana
                _mana_ok, _new_mana = check_and_deduct_mana(sheet, _spell_mana_cost)
                if not _mana_ok:
                    _persist_combatants(conn, row, combatants)
                    conn.execute(
                        "UPDATE characters SET sheet_json = ? WHERE id = ?",
                        (json.dumps(sheet, ensure_ascii=False), int(row["character_id"])),
                    )
                    conn.commit()
                    return {
                        "attacker": attacker,
                        "hit": False,
                        "damage": 0,
                        "blocked": True,
                        "message": (
                            f"Brak many! Potrzebujesz {_spell_mana_cost} many, "
                            f"masz {int(sheet.get('current_mana', 0))}."
                        ),
                        "mana_insufficient": True,
                        "current_mana": int(sheet.get("current_mana", 0)),
                    }
                out["mana_spent"] = _spell_mana_cost
                out["mana_after"] = _new_mana
                # Persist mana deduction immediately
                conn.execute(
                    "UPDATE characters SET sheet_json = ? WHERE id = ?",
                    (json.dumps(sheet, ensure_ascii=False), int(row["character_id"])),
                )
            # ─────────────────────────────────────────────────────────────────

            if hit:
                wrow = weapon_row
                die = "1d6"
                stat = "STR"
                if wrow:
                    die = str(wrow.get("damage_die") or "1d6").strip().lower()
                    stat = str(
                        (attack_roll or {}).get("damage_stat")
                        or wrow.get("linked_stat")
                        or "STR"
                    ).upper()
                mod = _stat_mod(sheet, stat)
                dmg = roll_damage_dice(die, mod)
                # Stage 3 Z2/Z6: ×2 on crit, ×2 on surprise → ×4 if both
                _dmg_mult = 1
                if player_nat20:
                    _dmg_mult *= 2
                if _surprise_fx.get("first_hit_doubled"):
                    _dmg_mult *= 2
                if _dmg_mult > 1:
                    dmg = dmg * _dmg_mult
                    out["damage_multiplier"] = _dmg_mult
                out["damage"] = dmg
                prev_hp = int(enemy.get("hp_current", 0) or 0)
                next_hp = max(0, prev_hp - dmg)
                enemy["hp_current"] = next_hp
                out["target_hp_remaining"] = next_hp
                # Stage 3 Z3: clear `zaskoczony` (or any consumed condition) after damage
                if _surprise_fx.get("consumed_keys"):
                    _clear_consumed_conditions(enemy, _surprise_fx["consumed_keys"])
                    out["consumed_conditions"] = _surprise_fx["consumed_keys"]

                # ── Weapon effect_json (extra damage, save-or-condition) ──────
                _wfx = _apply_weapon_effects(
                    wrow, sheet, enemy, is_crit=(player_raw == 20), conn=conn
                )
                if _wfx.get("extra_damage"):
                    _extra = int(_wfx["extra_damage"])
                    enemy["hp_current"] = max(0, int(enemy.get("hp_current", 0) or 0) - _extra)
                    dmg += _extra
                    out["damage"] = dmg
                    out["target_hp_remaining"] = int(enemy.get("hp_current", 0) or 0)
                if _wfx.get("weapon_effect_narrative"):
                    out["weapon_effect_narrative"] = _wfx["weapon_effect_narrative"]
                if _wfx.get("conditions_applied"):
                    out["weapon_conditions_applied"] = _wfx["conditions_applied"]
                # ─────────────────────────────────────────────────────────────

                dead = int(enemy.get("hp_current", 0) or 0) <= 0
                out["enemy_dead"] = dead

                # ── Spell Nat 20 secondary effects ────────────────────────────
                if _is_spell and player_nat20 and hit:
                    from app.services.spell_service import resolve_spell_nat20_secondary
                    _nat20_fx = resolve_spell_nat20_secondary(enemy, dmg)
                    out["spell_nat20_secondary"] = _nat20_fx
                    if _nat20_fx.get("condition"):
                        _cond = _nat20_fx["condition"]
                        existing_conds = enemy.get("conditions") or []
                        if not any(c.get("key") == _cond for c in existing_conds):
                            if not isinstance(enemy.get("conditions"), list):
                                enemy["conditions"] = []
                            enemy["conditions"].append({
                                "key": _cond,
                                "label": _cond.title(),
                                "duration_rounds": 2,
                                "runtime": {},
                            })
                # ─────────────────────────────────────────────────────────────

                # ── Spell rank progression: record successful use ─────────────
                if _is_spell and _mana_ok:
                    _spell_key = str((attack_roll or {}).get("weapon_key") or "")
                    if _spell_key:
                        try:
                            from app.services.spell_service import record_spell_use
                            _use_result = record_spell_use(
                                int(row["character_id"]), _spell_key, conn
                            )
                            if _use_result.get("ranked_up"):
                                out["spell_rank_up"] = {
                                    "spell_key": _spell_key,
                                    "new_rank": _use_result["rank"],
                                }
                        except Exception:
                            pass
                # ─────────────────────────────────────────────────────────────

                if dead:
                    enemy["dead"] = True
                    ek = str(enemy.get("enemy_key") or "")
                    if ek and ch_id:
                        try:
                            from app.services.loot_service import (
                                apply_character_gold_delta,
                                roll_gold_drop,
                                roll_loot,
                            )

                            loot_items = roll_loot(ek)
                            if loot_items:
                                loot = _preview_loot_from_roll_items(loot_items)
                            else:
                                loot = []
                            gold_drop = int(roll_gold_drop(ek) or 0)
                            if gold_drop > 0:
                                apply_character_gold_delta(ch_id, gold_drop, reason="combat_loot")
                            out["gold_drop"] = max(0, gold_drop)
                        except Exception as e:
                            logger.warning(
                                "combat_loot_grant_failed",
                                campaign_id=campaign_id,
                                character_id=ch_id,
                                enemy_key=ek,
                                error_message=str(e),
                            )
                            loot = []
                            out["gold_drop"] = 0
                    else:
                        loot = []
                        out["gold_drop"] = 0
                    xpa = 0
                    xp_src = "none"
                    try:
                        raw_award = int(enemy.get("xp_award") or 0)
                    except (TypeError, ValueError):
                        raw_award = 0
                    from app.services import xp_service

                    try:
                        xpa, xp_src = xp_service.resolve_enemy_defeat_xp_amount(
                            conn,
                            catalog_xp_award=raw_award,
                            tier=str(enemy.get("tier") or "") or None,
                        )
                    except Exception:
                        xpa = 0
                        xp_src = "none"
                    if xpa > 0 and ch_id:
                        try:
                            grant = xp_service.grant_character_xp(
                                conn,
                                ch_id,
                                xpa,
                                reason="enemy_defeat",
                                meta={
                                    "enemy_key": ek,
                                    "xp_source": xp_src,
                                    "enemy_template_xp_award": raw_award,
                                    "enemy_tier": str(enemy.get("tier") or ""),
                                },
                            )
                            out["xp_granted"] = xpa
                            out["xp_source"] = xp_src
                            out["xp_available"] = grant.get("xp_available")
                        except Exception as e:
                            logger.warning(
                                "combat_xp_grant_failed",
                                campaign_id=campaign_id,
                                character_id=ch_id,
                                enemy_key=ek,
                                error_message=str(e),
                            )
                    out["loot"] = loot
                    loot_pool_accum.extend(loot)
                    cid_death = int(row["id"])
                    death_tn = _next_combat_log_sequence(conn, cid_death)
                    ename = str(enemy.get("name") or card_name or "Wróg")
                    log_combat_turn(
                        conn,
                        combat_id=cid_death,
                        campaign_id=campaign_id,
                        turn_number=death_tn,
                        actor=str(target_id),
                        event_type="death",
                        roll_value=None,
                        damage=int(out.get("damage") or 0),
                        hp_after=int(enemy.get("hp_current", 0) or 0),
                        target_id=target_id,
                        target_name=str(enemy.get("name") or "") or None,
                        hit=None,
                        narrative=f"{ename} pada — wróg nie żyje.",
                    )
                    if _all_enemies_dead(combatants):
                        cid = int(row["id"])
                        tn = _next_combat_log_sequence(conn, cid)
                        log_combat_turn(
                            conn,
                            combat_id=cid,
                            campaign_id=campaign_id,
                            turn_number=tn,
                            actor="player",
                            event_type="attack",
                            roll_value=int(roll_result),
                            damage=int(out.get("damage") or 0),
                            hp_after=int(enemy.get("hp_current", 0) or 0),
                            target_id=target_id,
                            target_name=str(enemy.get("name") or "") or None,
                            hit=True,
                            narrative=player_attack_log_meta,
                        )
                        _persist_combatants_and_maybe_end(
                            conn,
                            row,
                            combatants,
                            status="ended",
                            ended_reason="victory",
                            loot_pool=loot_pool_accum,
                        )
                        conn.commit()
                        # Scholar mana regen on victory: max(1, INT_mod * 2)
                        _scholar_restore_mana_after_combat(conn, ch_id, sheet, "victory")
                        # Mark current hex encounter as cleared for this campaign
                        try:
                            gs_hex = conn.execute(
                                "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
                                (campaign_id,),
                            ).fetchone()
                            if gs_hex:
                                _sf_hex = json.loads(gs_hex["session_flags"] or "{}")
                                ch = _sf_hex.get("current_hex")
                                if ch:
                                    conn.execute(
                                        """INSERT INTO campaign_hex_data
                                           (campaign_id, hex_q, hex_r, discovered)
                                           VALUES (?,?,?,1)
                                           ON CONFLICT(campaign_id, hex_q, hex_r) DO UPDATE SET
                                             encounter_cleared = 1, discovered = 1""",
                                        (campaign_id, int(ch["q"]), int(ch["r"])),
                                    )
                                    conn.commit()
                        except Exception:
                            pass
                        # XS13: outnumbered victory (3+ enemies)
                        try:
                            _enemy_count = sum(
                                1 for c in combatants if c.get("type") == "enemy"
                            )
                            if _enemy_count >= 3:
                                from app.services.xp_sources import grant_outnumbered_victory
                                _tn13 = _next_combat_log_sequence(conn, cid)
                                grant_outnumbered_victory(
                                    conn, int(ch_id), int(campaign_id),
                                    _enemy_count, _tn13,
                                )
                                conn.commit()
                        except Exception:
                            pass
                        # O1 — log combat victory event (best-effort)
                        try:
                            _enemies_killed = sum(
                                1 for _ec in combatants
                                if _ec.get("type") == "enemy"
                            )
                            _xp_so_far = int(out.get("xp", 0) or 0)
                            _round_count = int(row.get("round", 0) or 0) if row else 0
                            _char_user_id = None
                            try:
                                _cu_row = conn.execute(
                                    "SELECT user_id FROM characters WHERE id = ?", (ch_id,)
                                ).fetchone()
                                if _cu_row:
                                    _char_user_id = int(_cu_row[0] or 0) or None
                            except Exception:
                                pass
                            from app.services.event_logger import write_game_event
                            write_game_event(
                                "combat_victory",
                                int(campaign_id),
                                int(ch_id),
                                _char_user_id,
                                {
                                    "enemies_killed": _enemies_killed,
                                    "xp_awarded": _xp_so_far,
                                    "rounds": _round_count,
                                },
                                conn=conn,
                            )
                            conn.commit()
                        except Exception:
                            pass
                        out["combat_state"] = load_combat_snapshot(campaign_id)
                        return out
            else:
                out["damage"] = 0
                out["target_hp_remaining"] = int(enemy.get("hp_current", 0) or 0)
                out["enemy_dead"] = False
                out["loot"] = []
                out["gold_drop"] = 0

            # ── Spell Miscast (Nat 1 on spell attack) ─────────────────────────
            if _is_spell and player_nat1:
                from app.services.spell_service import resolve_miscast
                _miscast = resolve_miscast(sheet, enemy, conn)
                out["miscast"] = _miscast
                out["hp_after"] = _miscast.get("hp_after", int(sheet.get("current_hp", 0)))
                conn.execute(
                    "UPDATE characters SET sheet_json = ? WHERE id = ?",
                    (json.dumps(sheet, ensure_ascii=False), int(row["character_id"])),
                )
            # ─────────────────────────────────────────────────────────────────

            if _is_spell and _mana_ok:
                out["current_mana"] = int(sheet.get("current_mana", 0))

            cid = int(row["id"])
            tn = _next_combat_log_sequence(conn, cid)
            log_combat_turn(
                conn,
                combat_id=cid,
                campaign_id=campaign_id,
                turn_number=tn,
                actor="player",
                event_type="attack",
                roll_value=int(roll_result),
                damage=int(out.get("damage") or 0),
                hp_after=int(enemy.get("hp_current", 0) or 0),
                target_id=target_id,
                target_name=str(enemy.get("name") or "") or None,
                hit=bool(hit),
                narrative=player_attack_log_meta,
            )

            _persist_combatants(conn, row, combatants, loot_pool=loot_pool_accum)
            conn.commit()
            advance_turn(campaign_id)  # rotate to next actor (enemy turn)
            out["combat_state"] = load_combat_snapshot(campaign_id)
            return out

        # enemy attacks player
        if attacker != "enemy":
            raise ValueError("invalid attacker")

        order = json.loads(row["turn_order"] or "[]")
        cur = row["current_turn"]
        if str(cur) == "player":
            out["message"] = "enemy attack only when current turn is an enemy"
            out["combat_state"] = _row_to_combat_dict(row)
            return out

        enemy = _find_combatant(combatants, str(cur))
        if not enemy or enemy.get("type") != "enemy":
            raise ValueError("current turn is not a valid enemy")

        # ── Zone AI: melee enemy in different zone charges instead of attacking ──
        _ensure_zones(combatants)
        player_c = _find_combatant(combatants, "player") or {}
        p_zone_e = str(player_c.get("zone") or ZONE_ENGAGED)
        e_zone = str(enemy.get("zone") or ZONE_ENGAGED)
        _prefers_ranged = _default_zone_for_enemy(
            str(enemy.get("enemy_key") or ""), str(enemy.get("name") or "")
        ) == ZONE_RANGED
        if not _prefers_ranged and e_zone != p_zone_e:
            # Melee enemy charges to player's zone — consumes the turn, no attack
            old_zone = e_zone
            enemy["zone"] = p_zone_e
            out["hit"] = False
            out["damage"] = 0
            out["zone_change"] = {"actor_id": str(cur), "from": old_zone, "to": p_zone_e, "charged": True}
            out["enemy_name"] = str(enemy.get("name") or enemy.get("enemy_key") or "Wróg").strip()
            cid_zc = int(row["id"])
            tn_zc = _next_combat_log_sequence(conn, cid_zc)
            log_combat_turn(
                conn,
                combat_id=cid_zc,
                campaign_id=campaign_id,
                turn_number=tn_zc,
                actor="enemy",
                event_type="zone_change",
                roll_value=None,
                damage=None,
                hp_after=int(enemy.get("hp_current", 0) or 0),
                target_id=str(cur),
                target_name=out["enemy_name"],
                hit=None,
                narrative=json.dumps(
                    {"enemy_name": out["enemy_name"], "from": old_zone, "to": p_zone_e, "charged": True},
                    ensure_ascii=False,
                ),
            )
            _persist_combatants(conn, row, combatants, loot_pool=loot_pool_accum)
            conn.commit()
            # NOTE: do NOT advance_turn here. The enemy-attack path also relies on
            # the caller (post_enemy_turn) to advance. Advancing here too caused a
            # double-advance (enemy→player→enemy), letting the same enemy charge AND
            # attack in one round, skipping the player's turn. (#232)
            out["combat_state"] = load_combat_snapshot(campaign_id)
            return out

        raw = roll_d20()
        atk_b = int(enemy.get("attack_bonus") or 0)
        attack_roll = raw + atk_b
        p = _find_combatant(combatants, "player")
        if not p:
            raise ValueError("player combatant missing")
        pac = int(p.get("defense", _player_ac_from_sheet(sheet)))
        p["defense"] = pac
        hit = attack_roll >= pac
        out["hit"] = hit
        out["attack_roll"] = attack_roll
        out["raw_d20"] = raw
        out["enemy_name"] = str(enemy.get("name") or enemy.get("enemy_key") or "Wróg").strip()
        out["target_ac"] = pac

        _log_dice_roll_combat_resolve(
            source="combat_enemy",
            campaign_id=campaign_id,
            result_total=int(attack_roll),
            dc=int(pac),
            hit=bool(hit),
            raw_d20=int(raw),
        )

        dmg = 0
        if hit:
            expr = (enemy.get("damage_dice") or "1d6").strip().lower()
            dmg = roll_damage_dice(expr, enemy.get("damage_bonus", 0))
            out["damage"] = dmg
            prev = int(p.get("hp_current", 0) or 0)
            next_hp = max(0, prev - dmg)
            p["hp_current"] = next_hp
            sheet["current_hp"] = next_hp
            out["player_hp_remaining"] = next_hp
            incap = next_hp <= 0
            out["player_incapacitated"] = incap
            conn.execute(
                "UPDATE characters SET sheet_json = ? WHERE id = ?",
                (json.dumps(sheet, ensure_ascii=False), ch_id),
            )
        else:
            out["damage"] = 0
            out["player_hp_remaining"] = int(p.get("hp_current", 0) or 0)
            out["player_incapacitated"] = False

        cid = int(row["id"])
        tn = _next_combat_log_sequence(conn, cid)
        log_combat_turn(
            conn,
            combat_id=cid,
            campaign_id=campaign_id,
            turn_number=tn,
            actor="enemy",
            event_type="attack",
            roll_value=int(attack_roll),
            damage=int(out.get("damage") or 0),
            hp_after=int(p.get("hp_current", 0) or 0),
            target_id="player",
            target_name=str(p.get("name") or "Gracz"),
            hit=bool(hit),
            narrative=json.dumps(
                {
                    "raw_d20": int(raw),
                    "attack_roll": int(attack_roll),
                    "target_ac": int(pac),
                    "enemy_name": str(enemy.get("name") or enemy.get("enemy_key") or "Wróg"),
                },
                ensure_ascii=False,
            ),
        )

        _persist_combatants(conn, row, combatants)
        conn.commit()
        out["combat_state"] = load_combat_snapshot(campaign_id)

    if attacker == "enemy" and out.get("player_incapacitated"):
        end_combat(campaign_id, "player_dead", defeated_by=out.get("enemy_name"))
        out["defeated_by"] = out.get("enemy_name")
        out["combat_state"] = load_combat_snapshot(campaign_id)
    return out


def resolve_player_attack(
    campaign_id: int,
    roll_result: int,
    raw_d20: int | None = None,
) -> dict[str, Any]:
    """Step 4.1 — alias for :func:`resolve_attack` with ``attacker='player'`` (dodge, damage, HP)."""
    return resolve_attack(campaign_id, roll_result, attacker="player", raw_d20=raw_d20)


def resolve_enemy_attack(
    campaign_id: int,
    roll_result: int | None = None,
    raw_d20: int | None = None,
) -> dict[str, Any]:
    """Step 4.2 — alias for :func:`resolve_attack` with ``attacker='enemy'``. ``roll_result`` / ``raw_d20`` ignored."""
    _ = (roll_result, raw_d20)
    return resolve_attack(campaign_id, 0, attacker="enemy", raw_d20=None)


def change_player_zone(campaign_id: int) -> dict[str, Any]:
    """T34 — Player zone-change action. Toggles engaged ↔ ranged and consumes the turn.

    Returns dict with from/to zones and the updated combat_state."""
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM active_combat WHERE campaign_id = ? AND status = 'active'",
            (campaign_id,),
        ).fetchone()
        if not row:
            raise ValueError("no active combat")
        if str(row["current_turn"]) != "player":
            raise ValueError("zone change only on player's turn")

        combatants: list[dict] = json.loads(row["combatants"] or "[]")
        _ensure_zones(combatants)
        p = _find_combatant(combatants, "player")
        if not p:
            raise ValueError("player combatant missing")
        old = str(p.get("zone") or ZONE_ENGAGED)
        new = _opposite_zone(old)
        p["zone"] = new

        cid = int(row["id"])
        tn = _next_combat_log_sequence(conn, cid)
        log_combat_turn(
            conn,
            combat_id=cid,
            campaign_id=campaign_id,
            turn_number=tn,
            actor="player",
            event_type="zone_change",
            roll_value=None,
            damage=None,
            hp_after=int(p.get("hp_current", 0) or 0),
            target_id="player",
            target_name=str(p.get("name") or "Bohater"),
            hit=None,
            narrative=json.dumps({"from": old, "to": new}, ensure_ascii=False),
        )
        _persist_combatants(conn, row, combatants)
        conn.commit()

    advance_turn(campaign_id)
    return {
        "ok": True,
        "from": old,
        "to": new,
        "combat_state": load_combat_snapshot(campaign_id),
    }


def _persist_combatants(
    conn: sqlite3.Connection,
    row: sqlite3.Row,
    combatants: list[dict],
    *,
    loot_pool: list[dict[str, Any]] | None = None,
) -> None:
    if loot_pool is not None and "loot_pool" in row.keys():
        conn.execute(
            """
            UPDATE active_combat
            SET combatants = ?, loot_pool = ?, updated_at = ?
            WHERE campaign_id = ?
            """,
            (
                json.dumps(combatants, ensure_ascii=False),
                json.dumps(loot_pool, ensure_ascii=False),
                _now_iso(),
                row["campaign_id"],
            ),
        )
    else:
        conn.execute(
            """
            UPDATE active_combat
            SET combatants = ?, updated_at = ?
            WHERE campaign_id = ?
            """,
            (json.dumps(combatants, ensure_ascii=False), _now_iso(), row["campaign_id"]),
        )


def _persist_combatants_and_maybe_end(
    conn: sqlite3.Connection,
    row: sqlite3.Row,
    combatants: list[dict],
    *,
    status: str,
    ended_reason: str | None,
    loot_pool: list[dict[str, Any]] | None = None,
) -> None:
    if loot_pool is not None and "loot_pool" in row.keys():
        conn.execute(
            """
            UPDATE active_combat
            SET combatants = ?, status = ?, ended_reason = ?, loot_pool = ?, updated_at = ?
            WHERE campaign_id = ?
            """,
            (
                json.dumps(combatants, ensure_ascii=False),
                status,
                ended_reason,
                json.dumps(loot_pool, ensure_ascii=False),
                _now_iso(),
                row["campaign_id"],
            ),
        )
    else:
        conn.execute(
            """
            UPDATE active_combat
            SET combatants = ?, status = ?, ended_reason = ?, updated_at = ?
            WHERE campaign_id = ?
            """,
            (
                json.dumps(combatants, ensure_ascii=False),
                status,
                ended_reason,
                _now_iso(),
                row["campaign_id"],
            ),
        )
    if str(status) == "ended":
        _log_combat_end_event(conn, row, str(ended_reason or "ended"))


def get_current_actor(conn: sqlite3.Connection | None, campaign_id: int) -> str | None:
    """Step 3.2 — whose turn: ``active_combat.current_turn`` (conn unused; combat DB is separate)."""
    _ = conn
    st = get_active_combat(campaign_id)
    if not st:
        return None
    ct = st.get("current_turn")
    if ct is None or str(ct).strip() == "":
        return None
    return str(ct)


def is_combat_active(conn: sqlite3.Connection | None, campaign_id: int) -> bool:
    """Step 3.2 — True if there is active combat for this campaign."""
    _ = conn
    return get_active_combat(campaign_id) is not None


def _advance_turn_impl(campaign_id: int) -> str:
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM active_combat WHERE campaign_id = ? AND status = 'active'",
            (campaign_id,),
        ).fetchone()
        if not row:
            raise ValueError("no active combat")

        combatants: list[dict] = json.loads(row["combatants"] or "[]")
        order: list[str] = json.loads(row["turn_order"] or "[]")
        if _all_enemies_dead(combatants):
            _persist_combatants_and_maybe_end(conn, row, combatants, status="ended", ended_reason="victory")
            conn.commit()
            return "ended"

        living: list[str] = []
        for tid in order:
            c = _find_combatant(combatants, tid)
            if not c:
                continue
            if int(c.get("hp_current", 0) or 0) <= 0:
                continue
            living.append(tid)

        if len(living) <= 1:
            _persist_combatants_and_maybe_end(conn, row, combatants, status="ended", ended_reason="victory")
            conn.commit()
            return "ended"

        cur = row["current_turn"]
        rnd = int(row["round"] or 1)
        cur_s = str(cur)
        if cur_s in living:
            i = living.index(cur_s)
        else:
            i = -1
        next_i = (i + 1) % len(living)
        new_turn = living[next_i]
        first_in_order = order[0] if order else living[0]
        if str(cur) != str(first_in_order) and str(new_turn) == str(first_in_order):
            rnd += 1

        conn.execute(
            """
            UPDATE active_combat
            SET current_turn = ?, round = ?, updated_at = ?
            WHERE campaign_id = ?
            """,
            (new_turn, rnd, _now_iso(), campaign_id),
        )
        conn.commit()
        return str(new_turn)


def advance_turn(
    first: int | sqlite3.Connection | None,
    second: int | None = None,
) -> str | None:
    """
    Step 3.2 — advance to next living actor; bump ``round`` after a full cycle.

    - Legacy: ``advance_turn(campaign_id: int) -> str`` (raises ``ValueError`` if no combat).
    - Doc API: ``advance_turn(conn, campaign_id) -> str | None`` — ``conn`` is reserved for
      callers sharing a narrative DB handle; combat state still uses ``COMBAT_DB_PATH``.
      Returns ``None`` if there is no active combat (instead of raising).
    """
    if second is None:
        if not isinstance(first, int):
            raise TypeError("advance_turn(campaign_id): campaign_id must be int")
        return _advance_turn_impl(first)
    if not isinstance(second, int):
        raise TypeError("advance_turn(conn, campaign_id): campaign_id must be int")
    if first is not None and not isinstance(first, sqlite3.Connection):
        raise TypeError("advance_turn(conn, campaign_id): conn must be sqlite3.Connection or None")
    try:
        return _advance_turn_impl(second)
    except ValueError:
        return None


def _scholar_restore_mana_after_combat(
    conn: sqlite3.Connection, character_id: int, sheet: dict, reason: str
) -> None:
    """Layer 2 balance fix: Scholar recovers mana after each combat (victory or flee)."""
    try:
        archetype = str(sheet.get("archetype") or "").strip().lower()
        if archetype != "scholar":
            return
        current = int(sheet.get("current_mana", 0) or 0)
        maximum = int(sheet.get("max_mana", 0) or 0)
        if maximum <= 0 or current >= maximum:
            return
        int_stat = int((sheet.get("stats") or {}).get("INT", 10) or 10)
        int_mod = (int_stat - 10) // 2
        restore = max(1, int_mod * 2)
        new_mana = min(maximum, current + restore)
        sheet["current_mana"] = new_mana
        conn.execute(
            "UPDATE characters SET sheet_json = ? WHERE id = ?",
            (json.dumps(sheet, ensure_ascii=False), int(character_id)),
        )
        conn.commit()
        logger.info("scholar_mana_restored_after_combat",
                    character_id=character_id, restored=new_mana - current,
                    new_mana=new_mana, max_mana=maximum, reason=reason)
    except Exception as e:
        logger.warning("scholar_mana_restore_failed", error=str(e))


def end_combat(campaign_id: int, reason: str, *, defeated_by: str | None = None) -> None:
    """End combat row (``status='ended'``, ``ended_reason``). For ``player_dead``, also ends solo campaign via :func:`solo_death_service.end_solo_campaign_on_death`."""
    char_id: int | None = None
    with _conn() as conn:
        row = conn.execute(
            """
            SELECT * FROM active_combat
            WHERE campaign_id = ? AND status = 'active'
            """,
            (campaign_id,),
        ).fetchone()
        if row:
            _log_combat_end_event(conn, row, reason)
            char_id = int(row["character_id"])
        conn.execute(
            """
            UPDATE active_combat
            SET status = 'ended', ended_reason = ?, updated_at = ?
            WHERE campaign_id = ?
            """,
            (reason, _now_iso(), campaign_id),
        )
        conn.commit()
        # Scholar mana regen on flee
        if reason == "fled" and char_id:
            try:
                ch_row = conn.execute(
                    "SELECT sheet_json FROM characters WHERE id = ?", (char_id,)
                ).fetchone()
                if ch_row:
                    _sh = json.loads(ch_row["sheet_json"] or "{}")
                    _scholar_restore_mana_after_combat(conn, char_id, _sh, "fled")
            except Exception:
                pass

    if reason != "player_dead" or char_id is None:
        return

    from app.services.admin_config import DB_PATH
    from app.services.solo_death_service import end_solo_campaign_on_death

    label = (defeated_by or "").strip() or "wróg"
    death_reason = f"Poległ w walce z: {label}"

    nconn: sqlite3.Connection | None = None
    try:
        nconn = sqlite3.connect(DB_PATH)
        nconn.row_factory = sqlite3.Row
        ch = nconn.execute(
            """
            SELECT id, name, sheet_json, user_id FROM characters
            WHERE id = ? AND campaign_id = ?
            """,
            (char_id, campaign_id),
        ).fetchone()
        if not ch:
            logger.warning(
                "combat_player_dead_no_character",
                campaign_id=campaign_id,
                character_id=char_id,
            )
            return
        camp = nconn.execute(
            "SELECT status FROM campaigns WHERE id = ?",
            (campaign_id,),
        ).fetchone()
        if camp and str(camp["status"] or "").lower() == "ended":
            return
        end_solo_campaign_on_death(
            nconn,
            campaign_id=campaign_id,
            character_row=ch,
            death_reason=death_reason,
        )
    except Exception as e:
        logger.error(
            "combat_player_dead_solo_death_failed",
            campaign_id=campaign_id,
            error_message=str(e),
            exc_info=True,
        )
    finally:
        if nconn is not None:
            nconn.close()


def claim_post_combat_loot(
    campaign_id: int,
    *,
    character_id: int,
    selected_indexes: list[int],
) -> dict[str, Any]:
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM active_combat WHERE campaign_id = ?",
            (campaign_id,),
        ).fetchone()
        if not row:
            raise ValueError("combat not found")
        if int(row["character_id"] or 0) != int(character_id):
            raise ValueError("character mismatch")
        if str(row["status"] or "") != "ended" or str(row["ended_reason"] or "") != "victory":
            raise ValueError("combat not in victory state")

        pool = _read_loot_pool_from_row(row)
        if not pool:
            return {"claimed": [], "available": [], "selected_indexes": []}

        selected_set = {int(i) for i in (selected_indexes or [])}
        chosen_rows: list[dict[str, Any]] = []
        for idx, entry in enumerate(pool):
            if idx in selected_set:
                chosen_rows.append(entry)

        to_grant: list[dict[str, Any]] = []
        for entry in chosen_rows:
            e = dict(entry or {})
            qty = max(1, int(e.get("quantity") or 1))
            key = str(e.get("key") or "").strip()
            t = str(e.get("item_type") or "").strip().lower()
            if not key:
                continue
            if t == "weapon":
                to_grant.append({"weapon_key": key, "quantity": qty})
            else:
                to_grant.append({"item_key": key, "quantity": qty})

        from app.services.loot_service import grant_loot_to_character

        claimed = grant_loot_to_character(character_id, to_grant, source="loot") if to_grant else []

        updates: list[str] = []
        params: list[Any] = []
        if "loot_pool" in row.keys():
            updates.append("loot_pool = ?")
            params.append(json.dumps([], ensure_ascii=False))
        if "loot_persisted" in row.keys():
            updates.append("loot_persisted = ?")
            params.append(1)
        if "post_combat_loot_json" in row.keys():
            updates.append("post_combat_loot_json = ?")
            params.append(json.dumps(claimed, ensure_ascii=False))
        updates.append("updated_at = ?")
        params.append(_now_iso())
        params.append(campaign_id)
        conn.execute(
            f"UPDATE active_combat SET {', '.join(updates)} WHERE campaign_id = ?",
            tuple(params),
        )
        conn.commit()
        return {
            "claimed": claimed,
            "available": pool,
            "selected_indexes": sorted(selected_set),
        }
