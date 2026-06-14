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
from app.services.actor_stats import parse_stats_json
from app.services.effect_json_migration import legacy_effect_fields_from_json
from app.services.dice import parse_character_sheet, resolve_dc_for_roll, roll_d20
from app.services.weapon_rules import (
    load_weapon_row,
    resolve_attack_roll_for_weapon,
    resolve_sheet_weapon,
    stat_modifier,
)
from app.services.wound_utils import wound_penalty
from app.services.world_state_service import set_world_state_flags

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
    d = sheet.get("defense")
    if isinstance(d, dict) and d.get("base") is not None:
        return int(d["base"])
    return 10 + _stat_mod(sheet, "DEX")


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


def _weapon_effects_of_type(weapon_row: dict | None, effect_type: str) -> list[dict[str, Any]]:
    """F1 (#461): return typed Effect Objects of a given `type` from weapon effect_json.

    Shared extractor for gear combat effects (damage_bonus, ac_bonus, heal_on_hit, …).
    Returns [] when the weapon has no effect_json or no matching effects.
    """
    raw = weapon_row.get("effect_json") if weapon_row else None
    parsed = _decode_effect_json(raw)
    if not parsed:
        return []
    effects = parsed.get("effects")
    if not isinstance(effects, list):
        return []
    wanted = str(effect_type or "").strip().lower()
    return [
        e for e in effects
        if isinstance(e, dict) and str(e.get("type") or "").strip().lower() == wanted
    ]


def _sum_damage_bonus(effect_source: dict | None) -> int:
    """Sum flat `damage_bonus` values from one effect_json carrier (weapon or affix).

    `effect_source` is any dict exposing an `effect_json` key. Returns 0 when
    absent or malformed. Shared by weapon (F1 #461) and affix (F2 #462) paths.
    """
    total = 0
    for effect in _weapon_effects_of_type(effect_source, "damage_bonus"):
        try:
            total += int(effect.get("value") or 0)
        except (TypeError, ValueError):
            continue
    return total


def _weapon_flat_damage_bonus(weapon_row: dict | None) -> int:
    """F1 (#461): sum flat `damage_bonus` effects from weapon effect_json.

    Flat bonus is gear-derived → added once (not multiplied by crit/surprise).
    """
    return _sum_damage_bonus(weapon_row)


def _weapon_heal_on_hit(weapon_row: dict | None) -> int:
    """F1 (#461): sum `heal_on_hit` effects from weapon effect_json (life-steal)."""
    total = 0
    for e in _weapon_effects_of_type(weapon_row, "heal_on_hit"):
        try:
            total += int(e.get("value") or 0)
        except (TypeError, ValueError):
            continue
    return total


def _weapon_ac_bonus(weapon_row: dict | None) -> int:
    """F1 (#461): sum ac_bonus effects from weapon effect_json (applied at combat-start)."""
    total = 0
    for e in _weapon_effects_of_type(weapon_row, "ac_bonus"):
        try:
            total += int(e.get("value") or 0)
        except (TypeError, ValueError):
            continue
    return total


def _weapon_stat_modifiers(weapon_row: dict | None) -> dict[str, int]:
    """F1 (#461): collect static_stat_modifier effects from weapon effect_json.

    Returns {STAT: bonus} dict. Applied to combatant stats at combat-start.
    """
    mods: dict[str, int] = {}
    for e in _weapon_effects_of_type(weapon_row, "static_stat_modifier"):
        stat = str(e.get("stat") or "").strip().upper()
        if not stat:
            continue
        try:
            val = int(e.get("value") or 0)
        except (TypeError, ValueError):
            continue
        mods[stat] = mods.get(stat, 0) + val
    return mods


def _weapon_apply_conditions(
    weapon_row: dict | None, enemy: dict, conn: Any
) -> list[str]:
    """F1 (#461): apply conditions from typed apply_condition Effects on weapon hit.

    Reuses gear_bonus / apply_condition type. Looks up condition label/effect from
    game_config_conditions if available; falls back to key as label. Skips duplicates.
    Returns list of applied condition keys.
    """
    applied: list[str] = []
    for e in _weapon_effects_of_type(weapon_row, "apply_condition"):
        cond_key = str(e.get("condition_key") or "").strip()
        if not cond_key:
            continue
        duration = int(e.get("duration_rounds") or 2)
        existing = enemy.get("conditions")
        if isinstance(existing, list) and any(c.get("key") == cond_key for c in existing):
            continue
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
        if not isinstance(enemy.get("conditions"), list):
            enemy["conditions"] = []
        # S14 (#609): bramka immunitetu/broken_by przy nakładaniu kondycji bronią (F1).
        allowed, _gr = apply_condition_gate(enemy["conditions"], cond_key, cond_efx)
        if not allowed:
            continue
        enemy["conditions"].append({
            "key": cond_key,
            "label": cond_label,
            "effect_json": cond_efx,
            "duration_rounds": duration,
            "applied_at": "weapon_hit",
            "runtime": {},
        })
        applied.append(cond_key)
    return applied


def _load_equipped_affix_rows(conn: Any, character_id: int | None) -> list[dict]:
    """F2 (#462/#495): load effect_json rows for all affixes on the equipped main-hand weapon.

    Returns list of dicts with `effect_json` key. Returns [] when no weapon is
    equipped, no affixes set, or the affix table is absent.
    """
    if not character_id:
        return []
    try:
        inv = conn.execute(
            """
            SELECT affixes_json FROM character_inventory
            WHERE character_id = ?
              AND COALESCE(equipped, 0) = 1
              AND LOWER(TRIM(COALESCE(slot, ''))) = 'main_hand'
              AND weapon_key IS NOT NULL AND TRIM(weapon_key) != ''
            ORDER BY id ASC LIMIT 1
            """,
            (int(character_id),),
        ).fetchone()
    except sqlite3.OperationalError:
        return []
    if not inv:
        return []

    raw = inv["affixes_json"] if "affixes_json" in inv.keys() else None
    try:
        affix_keys = json.loads(raw) if isinstance(raw, str) and raw.strip() else (raw or [])
    except (json.JSONDecodeError, TypeError):
        return []
    affix_keys = [str(k).strip() for k in affix_keys if str(k or "").strip()]
    if not affix_keys:
        return []

    placeholders = ",".join("?" for _ in affix_keys)
    try:
        rows = conn.execute(
            f"SELECT effect_json FROM game_config_affixes WHERE key IN ({placeholders})",
            tuple(affix_keys),
        ).fetchall()
    except sqlite3.OperationalError:
        return []
    return [{"effect_json": r["effect_json"]} for r in rows]


def _inventory_affix_damage_bonus(conn: Any, character_id: int | None) -> int:
    """F2 (#462): sum `damage_bonus` from affixes on the equipped main-hand weapon."""
    return sum(_sum_damage_bonus(r) for r in _load_equipped_affix_rows(conn, character_id))


def _inventory_affix_heal_on_hit(conn: Any, character_id: int | None) -> int:
    """F2 (#495): sum `heal_on_hit` from affixes on the equipped main-hand weapon."""
    total = 0
    for r in _load_equipped_affix_rows(conn, character_id):
        for e in _weapon_effects_of_type(r, "heal_on_hit"):
            try:
                total += int(e.get("value") or 0)
            except (TypeError, ValueError):
                continue
    return total


def _inventory_affix_ac_bonus(conn: Any, character_id: int | None) -> int:
    """F2 (#495): sum `ac_bonus` from affixes on the equipped main-hand weapon."""
    total = 0
    for r in _load_equipped_affix_rows(conn, character_id):
        for e in _weapon_effects_of_type(r, "ac_bonus"):
            try:
                total += int(e.get("value") or 0)
            except (TypeError, ValueError):
                continue
    return total


def _inventory_affix_stat_modifiers(conn: Any, character_id: int | None) -> dict[str, int]:
    """F2 (#495): collect `static_stat_modifier` effects from affixes on the equipped weapon."""
    mods: dict[str, int] = {}
    for r in _load_equipped_affix_rows(conn, character_id):
        for e in _weapon_effects_of_type(r, "static_stat_modifier"):
            stat = str(e.get("stat") or "").strip().upper()
            if not stat:
                continue
            try:
                val = int(e.get("value") or 0)
            except (TypeError, ValueError):
                continue
            mods[stat] = mods.get(stat, 0) + val
    return mods


def _inventory_affix_apply_conditions(
    conn: Any, character_id: int | None, enemy: dict
) -> list[str]:
    """F2 (#495): apply `apply_condition` effects from affixes on the equipped weapon."""
    applied: list[str] = []
    for r in _load_equipped_affix_rows(conn, character_id):
        for e in _weapon_effects_of_type(r, "apply_condition"):
            cond_key = str(e.get("condition_key") or "").strip()
            if not cond_key:
                continue
            duration = int(e.get("duration_rounds") or 2)
            existing = enemy.get("conditions")
            if isinstance(existing, list) and any(c.get("key") == cond_key for c in existing):
                continue
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
            if not isinstance(enemy.get("conditions"), list):
                enemy["conditions"] = []
            # S14 (#609): bramka immunitetu/broken_by przy nakładaniu kondycji afiksem (F2).
            allowed, _gr = apply_condition_gate(enemy["conditions"], cond_key, cond_efx)
            if not allowed:
                continue
            enemy["conditions"].append({
                "key": cond_key,
                "label": cond_label,
                "effect_json": cond_efx,
                "duration_rounds": duration,
                "applied_at": "affix_hit",
                "runtime": {},
            })
            applied.append(cond_key)
    return applied


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


# ─── S19 (#614): hidden — untargetable + ambush_bonus. Prymitywy raz, kondycja danymi. ──

def _actor_conditions(combatant: dict[str, Any], sheet: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    if isinstance(sheet, dict):
        return _sheet_conditions(sheet)
    return [c for c in (combatant.get("conditions") or []) if isinstance(c, dict)]


def _combatant_is_untargetable(combatant: dict[str, Any], *, sheet: dict[str, Any] | None = None) -> bool:
    """True, gdy aktor ma aktywną kondycję niosącą efekt `untargetable` (np. hidden).
    Data-driven — żaden ``if condition_key == "hidden"``."""
    for cond in _actor_conditions(combatant, sheet):
        for eff in _condition_effects(cond):
            if str(eff.get("type") or "").strip().lower() == "untargetable":
                return True
    return False


def _actor_detect_dc(combatant: dict[str, Any], *, sheet: dict[str, Any] | None = None, default: int = 14) -> int:
    """DC rzutu WIS wroga przy poszukiwaniu — top-level `detect_dc` pierwszej kondycji untargetable."""
    for cond in _actor_conditions(combatant, sheet):
        parsed = _decode_effect_json(cond.get("effect_json"))
        if not parsed:
            continue
        if any(str(e.get("type") or "").strip().lower() == "untargetable" for e in _condition_effects(cond)):
            try:
                dc = int(parsed.get("detect_dc"))
                if dc >= 1:
                    return dc
            except (TypeError, ValueError):
                pass
    return default


def _hidden_conditions(combatant: dict[str, Any], *, sheet: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Kondycje aktora niosące `untargetable` lub `ambush_bonus` (definicja stanu ukrycia)."""
    out: list[dict[str, Any]] = []
    for cond in _actor_conditions(combatant, sheet):
        if any(str(e.get("type") or "").strip().lower() in ("untargetable", "ambush_bonus")
               for e in _condition_effects(cond)):
            out.append(cond)
    return out


def _roll_ambush_bonus(conditions: list[dict[str, Any]]) -> int:
    """Suma rzutów `ambush_bonus` (value = kość, np. 2d6) z podanych kondycji. RAZ na atak."""
    total = 0
    for cond in conditions:
        for eff in _condition_effects(cond):
            if str(eff.get("type") or "").strip().lower() != "ambush_bonus":
                continue
            val = eff.get("value")
            if isinstance(val, str) and val.strip():
                total += int(roll_damage_dice(val.strip().lower(), 0))
            else:
                try:
                    total += int(val or 0)
                except (TypeError, ValueError):
                    pass
    return total


def _remove_combatant_conditions(combatant: dict[str, Any], conditions: list[dict[str, Any]]) -> None:
    """Zdejmij wskazane (po tożsamości obiektu lub kluczu) kondycje z combatanta in-memory."""
    keys = {str(c.get("key") or "").strip().lower() for c in conditions if isinstance(c, dict)}
    if not keys:
        return
    combatant["conditions"] = [
        c for c in (combatant.get("conditions") or [])
        if not (isinstance(c, dict) and str(c.get("key") or "").strip().lower() in keys)
    ]


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


# ─── S9 (#604): poziomy stackowania (stacking_levels) — prymityw raz, kondycja danymi ──

def _condition_level(condition: dict[str, Any]) -> int:
    """Runtime poziom kondycji stackowalnej (domyślnie 1)."""
    runtime = condition.get("runtime")
    if isinstance(runtime, dict):
        try:
            return max(1, int(runtime.get("level", 1) or 1))
        except (TypeError, ValueError):
            return 1
    return 1


def _set_condition_level(condition: dict[str, Any], level: int) -> None:
    runtime = condition.get("runtime")
    if not isinstance(runtime, dict):
        runtime = {}
        condition["runtime"] = runtime
    runtime["level"] = max(1, int(level))


def _stacking_levels_effects(condition: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        e for e in _condition_effects(condition)
        if str(e.get("type") or "").strip().lower() == "stacking_levels"
    ]


def _condition_max_level(condition: dict[str, Any]) -> int:
    cap = 1
    for eff in _stacking_levels_effects(condition):
        try:
            cap = max(cap, int(eff.get("max_level") or 1))
        except (TypeError, ValueError):
            pass
    return cap


# ─── S12 (#607): prymitywy extra_action + on_expire_apply — prymityw raz, kondycja danymi ──

def _duration_rounds_from_effects(effects: list[dict[str, Any]]) -> int | None:
    """Czas trwania kondycji wyprowadzony z effect.expires='duration_rounds:N'
    (pierwszy taki efekt). Używane przy nakładaniu kondycji-buffa (np. hasted 3 rundy)."""
    for ef in effects:
        if not isinstance(ef, dict):
            continue
        dur = _condition_duration_rounds(str(ef.get("expires") or ""))
        if dur is not None:
            return dur
    return None


def _actor_extra_action_kind(combatant: dict[str, Any]) -> str | None:
    """Zwraca action_kind pierwszej aktywnej, danymi opisanej `extra_action`
    (np. hasted → 'move_only'), albo None gdy aktor nie ma dodatkowej akcji."""
    for cond in (combatant.get("conditions") or []):
        if not isinstance(cond, dict):
            continue
        for ef in _condition_effects(cond):
            if str(ef.get("type") or "").strip().lower() == "extra_action":
                return str(ef.get("action_kind") or "move_only").strip().lower() or "move_only"
    return None


def _build_condition_entry(
    conn: sqlite3.Connection, condition_key: str, *, applied_at: str, level: int = 1,
) -> dict[str, Any] | None:
    """Zbuduj wpis kondycji z katalogu (effect_json/label/stackable + duration z expires).

    Wspólny budowniczy dla apply_condition_to_player i on_expire_apply — prymityw raz,
    żaden ``if condition_key == ...``. Zwraca None gdy kondycji nie ma w katalogu (invalid_reference).
    """
    key_lo = str(condition_key or "").strip().lower()
    if not key_lo:
        return None
    try:
        r = conn.execute(
            "SELECT * FROM game_config_conditions WHERE key = ? AND is_active = 1",
            (key_lo,),
        ).fetchone()
    except Exception:
        r = None
    if not r:
        return None
    cols = r.keys()
    label = str(r["label"]) if "label" in cols and r["label"] else key_lo.title()
    effect_json = r["effect_json"] if "effect_json" in cols else None
    stackable = False
    if "stackable" in cols:
        try:
            stackable = bool(int(r["stackable"] or 0))
        except (TypeError, ValueError):
            stackable = False
    entry: dict[str, Any] = {
        "key": key_lo,
        "label": label,
        "effect_json": effect_json,
        "applied_at": applied_at,
        "runtime": {"level": max(1, int(level))} if stackable else {},
    }
    dur = _duration_rounds_from_effects(_condition_effects(entry))
    if dur is not None:
        entry["duration_rounds"] = dur
    return entry


def reduce_stacking_conditions(
    conditions: list[dict[str, Any]], *, remove_all: bool,
) -> tuple[list[dict[str, Any]], bool]:
    """Zdejmuje poziomy kondycji stackowalnych (np. exhausted) przy odpoczynku.

    - `remove_all=False` (krótki odpoczynek 1h): −1 poziom; kondycja znika przy 0.
    - `remove_all=True`  (długi sen): kondycja stackowalna usuwana w całości.

    Kondycje bez efektu `stacking_levels` zostają nietknięte. Data-driven — żadnego
    `if key == "exhausted"` (Zasada projektowa FAZY S).
    """
    out: list[dict[str, Any]] = []
    changed = False
    for cond in conditions:
        if not isinstance(cond, dict) or not _stacking_levels_effects(cond):
            out.append(cond)
            continue
        if remove_all:
            changed = True
            continue
        new_level = _condition_level(cond) - 1
        if new_level <= 0:
            changed = True
            continue
        _set_condition_level(cond, new_level)
        changed = True
        out.append(cond)
    return out, changed


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
        # S8 (#603): schema-zgodny static_stat_modifier (effects[]) — prymityw raz.
        # Dotąd silnik czytał TYLKO legacy `stat_mods`; seedy U10 (effects[]) były martwe.
        eff = parsed.get("effects")
        if isinstance(eff, list):
            for ef in eff:
                if not isinstance(ef, dict):
                    continue
                if str(ef.get("type") or "").strip().lower() != "static_stat_modifier":
                    continue
                if str(ef.get("stat") or "").strip().upper() != stat_key:
                    continue
                try:
                    base += int(ef.get("value") or 0)
                except (TypeError, ValueError):
                    pass
            # S9 (#604): stacking_levels — kary per_level_effects skalowane ×poziom.
            for ef in eff:
                if not isinstance(ef, dict):
                    continue
                if str(ef.get("type") or "").strip().lower() != "stacking_levels":
                    continue
                level = _condition_level(cond)
                for ple in (ef.get("per_level_effects") or []):
                    if not isinstance(ple, dict):
                        continue
                    if str(ple.get("type") or "").strip().lower() != "static_stat_modifier":
                        continue
                    if str(ple.get("stat") or "").strip().upper() != stat_key:
                        continue
                    try:
                        base += int(ple.get("value") or 0) * level
                    except (TypeError, ValueError):
                        pass

    return base


# ─── S13 (#608): on_zero_hp_save — rzut ratunkowy przy 0 HP (np. blessed). Prymityw raz, kondycja danymi.

def _on_zero_hp_save(
    combatant: dict[str, Any], *, sheet: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Gdy obrażenia sprowadziłyby HP aktora do ≤0: pierwsza aktywna kondycja z efektem
    `on_zero_hp_save` i pozostałym budżetem `uses` wykonuje rzut d20 + stat_mod(stat) + save
    vs DC. Sukces → zwraca {saved:True, hp:1, ...} i dekrementuje budżet w runtime kondycji.
    Porażka → {saved:False, ...} (próba zużyta). Brak takiej kondycji / brak budżetu → None
    (silnik idzie normalną ścieżką nieprzytomności). Data-driven — żaden ``if key == "blessed"``.
    """
    conditions = (
        _sheet_conditions(sheet) if isinstance(sheet, dict)
        else [c for c in (combatant.get("conditions") or []) if isinstance(c, dict)]
    )
    for cond in conditions:
        for eff in _condition_effects(cond):
            if str(eff.get("type") or "").strip().lower() != "on_zero_hp_save":
                continue
            try:
                budget = int(eff.get("uses")) if eff.get("uses") is not None else 1
            except (TypeError, ValueError):
                budget = 1
            runtime = cond.get("runtime")
            if not isinstance(runtime, dict):
                runtime = {}
                cond["runtime"] = runtime
            used = int(runtime.get("on_zero_hp_save_used", 0) or 0)
            if used >= max(1, budget):
                return None  # budżet wyczerpany (np. drugi śmiertelny cios w tej samej scenie)
            stat_key = str(eff.get("stat") or "CON").strip().upper() or "CON"
            dc = int(resolve_dc_for_roll(eff.get("dc_key") or eff.get("value")) or 0)
            raw = int(roll_d20())
            mod = _combatant_stat_modifier(combatant, sheet=sheet, stat=stat_key)
            # +2 defensywny (derived stat 'save', np. blessed) dolicza się do rzutu ratunkowego.
            mod += _combatant_stat_modifier(combatant, sheet=sheet, stat="save")
            total = raw + mod
            success = raw == 20 or (raw != 1 and total >= dc)
            runtime["on_zero_hp_save_used"] = used + 1  # próba (rzut) zużywa budżet sceny
            result = str(eff.get("result") or "stay_at_1hp").strip().lower()
            out: dict[str, Any] = {
                "saved": bool(success),
                "condition_key": str(cond.get("key") or "").strip().lower(),
                "condition_label": str(cond.get("label") or "").strip(),
                "stat": stat_key, "raw": raw, "total": total, "dc": dc,
            }
            if success and result == "stay_at_1hp":
                out["hp"] = 1
            return out
    return None


# ─── S15 (#610): system reakcji + skill `dodge`. Okno reakcji PRZED aplikacją obrażeń.

def _try_dodge_reaction(
    p: dict[str, Any],
    sheet: dict[str, Any] | None,
    attack_roll: int,
    round_n: int,
) -> dict[str, Any] | None:
    """Okno reakcji uniku — wywoływane gdy cios wroga TRAFIŁ, PRZED aplikacją obrażeń.

    Pre-deklaracja (``p['reaction_declared'] == 'dodge'``) konsumowana przy pierwszym
    trafieniu w rundzie (raz/rundę). Skill-gated: ``dodge`` rank ≥ 1 (skill żyje na sheet,
    kondycje na combatancie). Test DEX (d20 + DEX_mod + skill_rank + proficiency) przeciwko
    WYNIKOWI ATAKU wroga (``attack_roll`` jako DC). Stopień liczony silnikiem S1
    (``_derive_outcome``):
      • sukces (margines ≥ 0)        → ``dodged=True`` (atak mija)
      • porażka (margines < 0)        → ``dodged=False``
      • krytyczna porażka (≤ −5)      → ``reaction_locked_round = round_n + 1``

    Zwraca ``None`` (silnik idzie normalną ścieżką obrażeń), gdy: brak deklaracji / brak
    skilla. Gdy reakcja zablokowana w tej rundzie — zwraca dict ``available=False``.

    Rzut ataku wroga (nat 20/nat 1, podwójne obrażenia) NIETKNIĘTY — to osobny rzut;
    margines dotyczy wyłącznie testu uniku (sam jest testem umiejętności).
    """
    if str(p.get("reaction_declared") or "") != "dodge":
        return None
    skills = (sheet.get("skills") if isinstance(sheet, dict) else None) or {}
    try:
        skill_rank = int(skills.get("dodge", 0) or 0)
    except (TypeError, ValueError):
        skill_rank = 0
    if skill_rank < 1:
        p.pop("reaction_declared", None)
        return None
    # Lockout po wcześniejszej krytycznej porażce — deklaracja i tak skonsumowana.
    if int(p.get("reaction_locked_round") or 0) == int(round_n):
        p.pop("reaction_declared", None)
        return {"reaction": "dodge", "available": False, "locked": True, "dodged": False}
    # Konsumuj pre-deklarację (raz/rundę — niezależnie od wyniku).
    p.pop("reaction_declared", None)
    dex_mod = _combatant_stat_modifier(p, sheet=None, stat="DEX")  # kondycje (np. hasted) na combatancie
    proficiency = 2 if skill_rank >= 3 else 0
    mod_total = int(dex_mod) + skill_rank + proficiency
    d20 = roll_d20()
    from app.services.skill_service import _derive_outcome  # S1 — jeden silnik stopnia wyniku
    outcome = _derive_outcome(d20, mod_total, int(attack_roll))
    dodged = bool(outcome["success"])
    locked_next = outcome["outcome"] == "CRITICAL_FAILURE"
    if locked_next:
        p["reaction_locked_round"] = int(round_n) + 1
    return {
        "reaction": "dodge",
        "available": True,
        "dodged": dodged,
        "d20": int(d20),
        "dodge_total": int(outcome["player_total"]),
        "attack_roll": int(attack_roll),
        "margin": int(outcome["margin"]),
        "outcome": outcome["outcome"],
        "locked_next_round": locked_next,
        "dex_mod": int(dex_mod),
        "skill_rank": skill_rank,
    }


# ─── S16 (#611): reakcja `shield_block` — druga reakcja w systemie (reużywa frameworku S15).

def _player_has_shield_equipped(conn: Any, char_id: int | None) -> tuple[bool, int | None]:
    """Czy gracz ma ZAŁOŻONĄ tarczę? Tarcza = założona (`equipped=1`) broń z
    ``game_config_weapons``, której ``key`` zawiera ``shield`` lub ``label`` zawiera
    ``tarcz`` (catches shield/wooden_shield/tower_shield + przyszłe). Zwraca
    ``(has_shield, inventory_id)`` — ``inventory_id`` służy do hitu durability przy crit-fail.
    """
    if not char_id:
        return False, None
    try:
        row = conn.execute(
            """
            SELECT ci.id AS inv_id
            FROM character_inventory ci
            JOIN game_config_weapons w ON w.key = ci.weapon_key
            WHERE ci.character_id = ?
              AND COALESCE(ci.equipped, 0) = 1
              AND ci.weapon_key IS NOT NULL AND TRIM(ci.weapon_key) != ''
              AND (LOWER(w.key) LIKE '%shield%' OR LOWER(w.label) LIKE '%tarcz%')
            LIMIT 1
            """,
            (int(char_id),),
        ).fetchone()
    except Exception as err:  # tabela ekwipunku/broni może nie istnieć w skrajnych setupach
        logger.warning("shield_equipped_lookup_error", error=str(err))
        return False, None
    if not row:
        return False, None
    try:
        return True, int(row["inv_id"])
    except (TypeError, KeyError, IndexError):
        return True, int(row[0])


def _try_shield_block_reaction(
    conn: Any,
    char_id: int | None,
    p: dict[str, Any],
    sheet: dict[str, Any] | None,
    attack_roll: int,
    round_n: int,
    dmg: int,
) -> dict[str, Any] | None:
    """Okno reakcji bloku — wołane gdy cios wroga TRAFIŁ, PRZED aplikacją obrażeń.

    Pre-deklaracja (``p['reaction_declared'] == 'shield_block'``) konsumowana przy
    pierwszym trafieniu w rundzie (raz/rundę — XOR z dodge, bo flaga trzyma jedną wartość).
    Skill-gated: ``shield_block`` rank ≥ 1 (skill na sheet) + założona tarcza (gate).
    Test STR (d20 + STR_mod + skill_rank + proficiency) przeciw DC = ``max(attack_roll, 12)``,
    stopień liczony silnikiem S1 (``_derive_outcome``):
      • sukces (margines ≥ 0)              → obrażenia − (1d6 + STR_mod, min 0)
      • sukces o ≥ +5 / CRITICAL_SUCCESS   → pełne odparcie (0 obrażeń)
      • porażka (margines < 0)             → pełne obrażenia
      • CRITICAL_FAILURE (margines ≤ −5)   → pełne obrażenia + tarcza traci durability ×3

    Zwraca ``None`` (silnik idzie normalną ścieżką), gdy brak deklaracji / brak skilla.
    Brak tarczy mimo deklaracji → dict ``available=False`` (gate, obrażenia bez zmian).

    Rzut ataku wroga (nat 20/nat 1, podwójne obrażenia) NIETKNIĘTY — to osobny rzut;
    margines dotyczy wyłącznie testu bloku (sam jest testem umiejętności).
    """
    if str(p.get("reaction_declared") or "") != "shield_block":
        return None
    skills = (sheet.get("skills") if isinstance(sheet, dict) else None) or {}
    try:
        skill_rank = int(skills.get("shield_block", 0) or 0)
    except (TypeError, ValueError):
        skill_rank = 0
    if skill_rank < 1:
        p.pop("reaction_declared", None)
        return None
    # Konsumuj pre-deklarację (raz/rundę — niezależnie od wyniku/gate'u).
    p.pop("reaction_declared", None)
    has_shield, inv_id = _player_has_shield_equipped(conn, char_id)
    if not has_shield:
        return {"reaction": "shield_block", "available": False, "reason": "no_shield",
                "damage_before": int(dmg), "damage_after": int(dmg)}
    str_mod = _combatant_stat_modifier(p, sheet=None, stat="STR")  # kondycje (np. rage) na combatancie
    proficiency = 2 if skill_rank >= 3 else 0
    mod_total = int(str_mod) + skill_rank + proficiency
    dc = max(int(attack_roll), 12)
    d20 = roll_d20()
    from app.services.skill_service import _derive_outcome  # S1 — jeden silnik stopnia wyniku
    outcome = _derive_outcome(d20, mod_total, dc)
    success = bool(outcome["success"])
    margin = int(outcome["margin"])
    oc = str(outcome["outcome"])
    full_block = success and (margin >= 5 or oc == "CRITICAL_SUCCESS")
    durability_hit = False
    if full_block:
        reduction = int(dmg)
        damage_after = 0
    elif success:
        reduction = max(0, roll_damage_dice("1d6", 0) + int(str_mod))
        damage_after = max(0, int(dmg) - reduction)
    else:
        reduction = 0
        damage_after = int(dmg)
        if oc == "CRITICAL_FAILURE" and inv_id is not None:
            try:
                conn.execute(
                    "UPDATE character_inventory SET durability_current = MAX(0, durability_current - 3) "
                    "WHERE id = ? AND durability_max IS NOT NULL",
                    (int(inv_id),),
                )
                durability_hit = True
            except Exception as err:
                logger.warning("shield_durability_hit_error", error=str(err))
    return {
        "reaction": "shield_block",
        "available": True,
        "d20": int(d20),
        "block_total": int(outcome["player_total"]),
        "attack_roll": int(attack_roll),
        "dc": int(dc),
        "margin": margin,
        "outcome": oc,
        "str_mod": int(str_mod),
        "skill_rank": skill_rank,
        "reduction": int(reduction),
        "damage_before": int(dmg),
        "damage_after": int(damage_after),
        "full_block": bool(full_block),
        "durability_hit": bool(durability_hit),
    }


# ─── S14 (#609): condition_immunity + broken_by — odporność na kondycje. Prymityw raz, kondycja danymi.

def _condition_immunity_keys(conditions: list[dict[str, Any]]) -> set[str]:
    """Klucze kondycji, na które aktor jest aktualnie ODPORNY — suma `immune_to` ze wszystkich
    aktywnych efektów `condition_immunity`. Data-driven, żaden ``if key == 'rage'``."""
    out: set[str] = set()
    for cond in conditions:
        if not isinstance(cond, dict):
            continue
        for eff in _condition_effects(cond):
            if str(eff.get("type") or "").strip().lower() != "condition_immunity":
                continue
            for k in (eff.get("immune_to") or []):
                kk = str(k).strip().lower()
                if kk:
                    out.add(kk)
    return out


def _condition_broken_by(cond: dict[str, Any]) -> set[str]:
    """Klucze kondycji, których nałożenie zdejmuje `cond` (top-level `broken_by` w effect_json)."""
    parsed = _decode_effect_json(cond.get("effect_json"))
    bb = parsed.get("broken_by") if isinstance(parsed, dict) else None
    if not isinstance(bb, list):
        return set()
    return {str(k).strip().lower() for k in bb if str(k or "").strip()}


def _effect_json_immune_to(effect_json: Any) -> set[str]:
    """`immune_to` nowej kondycji (z jej effect_json) — kondycje, które jej nałożenie czyści."""
    parsed = _decode_effect_json(effect_json)
    out: set[str] = set()
    if not isinstance(parsed, dict):
        return out
    for eff in (parsed.get("effects") or []):
        if isinstance(eff, dict) and str(eff.get("type") or "").strip().lower() == "condition_immunity":
            for k in (eff.get("immune_to") or []):
                kk = str(k).strip().lower()
                if kk:
                    out.add(kk)
    return out


def apply_condition_gate(
    conditions: list[dict[str, Any]], new_key: str, new_effect_json: Any,
) -> tuple[bool, str | None]:
    """S14 — generyczna bramka nakładania kondycji. MUTUJE `conditions` w miejscu.
    Wołać PRZED dopisaniem nowej kondycji do listy.

    1. Immunitet: jeśli aktor ma aktywną kondycję dającą odporność na `new_key` → (False, 'immune');
       nowej kondycji NIE dopisujemy, lista bez zmian.
    2. broken_by: aktywne kondycje, których `broken_by` zawiera `new_key`, są usuwane
       (np. nałożenie stunned/confused zdejmuje rage).
    3. immune_to nowej kondycji: aktywne kondycje pasujące do jej `immune_to` są usuwane
       (np. założenie rage czyści aktywne slowed/weakened).

    Zwraca (allowed, reason). reason='immune' przy bloku, inaczej None. Prymityw raz —
    żaden ``if new_key == ...``; wszystkie ścieżki nakładania kondycji wołają tę bramkę.
    """
    new_lo = str(new_key or "").strip().lower()
    if new_lo in _condition_immunity_keys(conditions):
        return False, "immune"
    new_immune = _effect_json_immune_to(new_effect_json)
    kept: list[dict[str, Any]] = []
    for cond in conditions:
        if not isinstance(cond, dict):
            kept.append(cond)
            continue
        ckey = str(cond.get("key") or "").strip().lower()
        if new_lo in _condition_broken_by(cond):
            continue  # broken_by — nałożenie new_key zdejmuje tę kondycję
        if ckey in new_immune:
            continue  # nowa kondycja (immune_to) czyści tę
        kept.append(cond)
    conditions[:] = kept
    return True, None


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


# ─── S18 (#613): behavior_override — kondycja steruje turą aktora. Prymityw raz. ──

_K4_ACTION = {1: "stand", 2: "attack_random", 3: "flee", 4: "normal"}


def _roll_k4() -> int:
    """Rzut k4 dla behavior=random_table_k4 (confused). Osobna funkcja → testowalna (patch)."""
    return random.randint(1, 4)


def _behavior_override_effect(cond: dict[str, Any]) -> dict[str, Any] | None:
    for ef in _condition_effects(cond):
        if str(ef.get("type") or "").strip().lower() == "behavior_override":
            return ef
    return None


def _resolve_forced_behavior(
    actor: dict[str, Any], actor_id: str, round_n: int, *, roll: bool,
) -> dict[str, Any] | None:
    """Wymuszone zachowanie aktora z PIERWSZEJ aktywnej kondycji niosącej `behavior_override`.

    Prymityw raz, kondycja danymi — żaden ``if condition_key == ...``.
    - ``roll=True`` (evaluate_current_turn_conditions): dla random_table_k4 rzuca k4 RAZ na turę
      i PERSYSTUJE decyzję w runtime kondycji (dedup po markerze rundy+aktora). attack_nearest/flee
      są deterministyczne.
    - ``roll=False`` (resolve_attack enemy branch): czyta zapisaną decyzję bez ponownego rzutu,
      żeby wykonanie zgadzało się z tym, co wyznaczyło evaluate w tej samej turze.

    Zwraca ``{actor_id, condition_key, condition_label, behavior, action, k4}`` albo None.
    """
    marker = _condition_turn_marker(round_n, actor_id)
    conditions = [c for c in (actor.get("conditions") or []) if isinstance(c, dict)]
    for idx, cond in enumerate(conditions):
        ef = _behavior_override_effect(cond)
        if not ef:
            continue
        behavior = str(ef.get("behavior") or "").strip().lower()
        if behavior not in _BEHAVIOR_KINDS:
            continue
        if behavior == "random_table_k4":
            state = _condition_effect_state(cond, f"behavior_{idx}")
            if str(state.get("last_turn_marker") or "") == marker and state.get("action"):
                action, k4 = str(state["action"]), state.get("k4")
            elif roll:
                k4 = int(_roll_k4())
                action = _K4_ACTION.get(k4, "normal")
                state["last_turn_marker"] = marker
                state["action"] = action
                state["k4"] = k4
            else:
                continue  # decyzja jeszcze nie wyznaczona (evaluate nie wołane) → pomiń
        else:
            action = "attack_nearest" if behavior == "attack_nearest" else "flee"
            k4 = None
        return {
            "actor_id": actor_id,
            "condition_key": str(cond.get("key") or ""),
            "condition_label": str(cond.get("label") or cond.get("key") or ""),
            "behavior": behavior,
            "action": action,
            "k4": k4,
        }
    return None


_BEHAVIOR_KINDS = {"random_table_k4", "attack_nearest", "flee"}


# ─── S10 (#605): escalating_dot — DOT narastający w czasie (np. hemorrhage) ─────

def _escalating_dot_damage(effect: dict[str, Any], ticks: int) -> int:
    """Obrażenia escalating_dot na danym tyknięciu.

    Poziom eskalacji = ``ticks // escalate_every_rounds``. Obrażenia tury =
    rzut kości bazowej (``value``) + (poziom × rzut kości przyrostu ``escalate_dice``).
    Prymityw raz, kondycja danymi — żadnego ``if condition_key == ...`` (Zasada 1 FAZY S).
    """
    base = effect.get("value")
    base_dmg = int(base) if isinstance(base, (int, float)) else roll_damage_dice(str(base or "1d4"))
    try:
        every = int(effect.get("escalate_every_rounds") or 3)
    except (TypeError, ValueError):
        every = 3
    every = max(1, every)
    level = max(0, int(ticks)) // every
    inc_expr = str(effect.get("escalate_dice") or "").strip()
    total = base_dmg
    for _ in range(level):
        total += roll_damage_dice(inc_expr) if inc_expr else 0
    return max(0, total)


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
               stats_json,
               tier,
               loot_table_key, drop_chance, COALESCE(xp_award, 0) AS xp_award
        FROM game_config_enemies
        WHERE key = ?
        """,
        (key,),
    ).fetchone()


def _create_pending_combat_enemy(
    conn: sqlite3.Connection, enemy_key: str
) -> sqlite3.Row | None:
    """D2 (#377) — Pending flow for enemies.

    When combat starts with an unknown enemy key (LLM emitted
    `[COMBAT_START:goblin_szaman]` but `goblin_szaman` isn't in the catalog),
    create a `review_status='pending_review'` template with standard-tier
    defaults so the fight can proceed immediately AND the enemy lands in the
    admin review queue. Mirrors the D1 item flow (`_grant_pending_item`).

    INSERT OR IGNORE: if the key already exists (race / known enemy) the existing
    row is left untouched. Returns the fetched enemy row, or None on failure.
    """
    # #567: generic/unknown fallback gets a neutral Polish name, not "Unknown Attacker"
    # or the literal "Wróg" placeholder. A real key (e.g. goblin_szaman) keeps its title.
    if enemy_key.strip().lower() in ("unknown_attacker", "enemy", "przeciwnik"):
        name = "Napastnik"
    else:
        name = enemy_key.replace("_", " ").title()
    try:
        # Standard-tier defaults — same baseline as world_service._get_or_create_enemy.
        conn.execute(
            """INSERT OR IGNORE INTO game_config_enemies
               (key, label, tier, hp_base, ac_base, attack_bonus, damage_die,
                damage_bonus, attacks_per_turn, xp_award, is_active, review_status)
               VALUES (?, ?, 'standard', 12, 11, 2, 'd6', 0, 1, 25, 1, 'pending_review')""",
            (enemy_key, name),
        )
        logger.info("combat_pending_enemy_created", enemy_key=enemy_key)
    except Exception as e:  # pragma: no cover - defensive
        logger.warning("combat_pending_enemy_create_failed", enemy_key=enemy_key, error=str(e))
        return None
    return _fetch_enemy_row(conn, enemy_key)


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

    # #567: generic placeholder labels never reach the player as the literal "Wróg".
    _GENERIC_LABELS = {"wróg", "wrog", "enemy", "przeciwnik", "unknown attacker", "unknown_attacker"}

    def from_row(r: sqlite3.Row) -> tuple[str, str]:
        k = str(r["key"])
        lab = str(r["label"] or r["key"] or "").strip() or k
        if lab.lower() in _GENERIC_LABELS:
            lab = "Napastnik"
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


def _preview_loot_from_roll_items(
    loot_items: list[dict[str, Any]],
    loot_tier: str | None = None,
) -> list[dict[str, Any]]:
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
                "enemy_loot_tier": loot_tier if item_type == "weapon" else None,
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
    # S8 (#603): kondycja MUSI istnieć w katalogu — inaczej invalid_reference (U6/llm_tag_errors).
    # Dociągamy też effect_json, żeby tag-applied kondycja była MECHANICZNA (dot/stat_mods/periodic_save
    # tykają w T24), a nie tylko kosmetyczną etykietą. S9 (#604): + flaga stackable.
    label = condition_key.title()
    effect_json = None
    stackable = False
    found = False
    try:
        with _conn() as _c2:
            # SELECT * → odporne na bazy testowe bez kolumny `stackable` (kolumna istnieje na DEV od U10).
            r = _c2.execute(
                "SELECT * FROM game_config_conditions WHERE key = ? AND is_active = 1",
                (condition_key,),
            ).fetchone()
            if r:
                found = True
                cols = r.keys()
                label = str(r["label"]) if "label" in cols and r["label"] else label
                effect_json = r["effect_json"] if "effect_json" in cols else None
                if "stackable" in cols:
                    try:
                        stackable = bool(int(r["stackable"] or 0))
                    except (TypeError, ValueError):
                        stackable = False
    except Exception:
        pass
    if not found:
        return {"ok": False, "matched": matched.get("enemy_key"), "reason": "invalid_reference"}

    # S14 (#609): bramka immunitetu/broken_by PRZED dopisaniem — odporność blokuje (nic nie zmienia),
    # broken_by/immune_to czyści aktywne kondycje. Bramka mutuje `conds` w miejscu.
    _pre_gate_len = len(conds)
    allowed, gate_reason = apply_condition_gate(conds, condition_key, effect_json)
    matched["conditions"] = conds
    if not allowed:
        return {"ok": True, "matched": matched.get("enemy_key"), "reason": gate_reason}
    _gate_changed = len(conds) != _pre_gate_len

    existing = next(
        (c for c in conds if isinstance(c, dict) and str(c.get("key", "")).lower() == condition_key.lower()),
        None,
    )
    if existing is not None:
        # S9 (#604): stackable=1 → podbij runtime.level (klamp max_level) zamiast duplikować.
        # S14: jeśli bramka coś zdjęła (broken_by/immune_to), trzeba zapisać mimo already_present.
        if not stackable and not _gate_changed:
            return {"ok": True, "matched": matched.get("enemy_key"), "reason": "already_present"}
        if not stackable:
            reason = "already_present"
            matched["conditions"] = conds
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
            return {"ok": True, "matched": matched.get("enemy_key"), "reason": reason}
        cap = _condition_max_level(existing)
        new_level = min(cap, _condition_level(existing) + 1)
        _set_condition_level(existing, new_level)
        matched["conditions"] = conds
        if new_level == _condition_level(existing) and new_level == cap:
            reason = "level_capped"
        else:
            reason = "level_bumped"
    else:
        conds.append({
            "key": condition_key.lower(),
            "label": label,
            "effect_json": effect_json,
            "applied_at": "apply_condition_tag",
            "runtime": {"level": 1} if stackable else {},
        })
        matched["conditions"] = conds
        reason = "applied"
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
    return {"ok": True, "matched": matched.get("enemy_key"), "reason": reason}


def apply_condition_to_player(campaign_id: int, condition_key: str) -> dict[str, Any]:
    """S12 (#607): nałóż kondycję z katalogu na combatanta GRACZA w aktywnej walce.

    Buff (np. hasted) jest celowany w gracza — tag [APPLY_CONDITION] (apply_condition_to_combatant)
    celuje wyłącznie we wrogów, więc to osobna, jawnie gracz-celująca ścieżka (Sandbox, mikstury).
    Czas trwania pochodzi z effect.expires (duration_rounds:N), poziom z runtime. Data-driven —
    żadnego ``if condition_key == ...``.

    Zwraca ``{ok, reason}``. reason: applied / level_bumped / level_capped / invalid_reference /
    no_active_combat / player_not_found.
    """
    if not condition_key:
        return {"ok": False, "reason": "missing_args"}
    snap = get_active_combat(campaign_id)
    if not snap:
        return {"ok": False, "reason": "no_active_combat"}
    combatants = snap.get("combatants") or []
    player = next((c for c in combatants if isinstance(c, dict) and c.get("type") == "player"), None)
    if not player:
        return {"ok": False, "reason": "player_not_found"}
    conds = player.get("conditions")
    if not isinstance(conds, list):
        conds = []

    with _conn() as conn:
        entry = _build_condition_entry(conn, condition_key, applied_at="apply_condition_player")
        if entry is None:
            return {"ok": False, "reason": "invalid_reference"}
        key_lo = str(condition_key).strip().lower()
        # S14 (#609): bramka immunitetu/broken_by PRZED dopisaniem (np. rage immune na slowed;
        # stunned/confused zdejmuje rage; rage czyści aktywne slowed/weakened). Mutuje `conds`.
        allowed, gate_reason = apply_condition_gate(conds, key_lo, entry.get("effect_json"))
        player["conditions"] = conds
        if not allowed:
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
            return {"ok": True, "reason": gate_reason}
        existing = next(
            (c for c in conds if isinstance(c, dict) and str(c.get("key") or "").strip().lower() == key_lo),
            None,
        )
        if existing is not None:
            # Stackowalna (runtime obecne) → podbij poziom (klamp), inaczej już aktywna.
            if not isinstance(entry.get("runtime"), dict) or "level" not in entry["runtime"]:
                reason = "already_present"
            else:
                cap = _condition_max_level(existing)
                before = _condition_level(existing)
                _set_condition_level(existing, min(cap, before + 1))
                reason = "level_capped" if _condition_level(existing) == cap and before == cap else "level_bumped"
        else:
            conds.append(entry)
            player["conditions"] = conds
            reason = "applied"
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
    return {"ok": True, "reason": reason}


def remove_condition_from_character(
    conn: sqlite3.Connection,
    character_id: int,
    campaign_id: int,
    condition_key: str,
) -> int:
    """S10 (#605): zdejmij kondycję z postaci (sheet_json.conditions) i — jeśli trwa
    walka — z combatanta gracza. Deklaratywne (klucz danymi), żadnego ``if key==...``.

    Zwraca liczbę usuniętych wystąpień (sheet + combat). 0 = nie było czego zdjąć.
    """
    key_lo = str(condition_key or "").strip().lower()
    if not key_lo or not character_id:
        return 0
    removed = 0

    # 1) sheet_json.conditions (źródło prawdy poza walką)
    try:
        row = conn.execute(
            "SELECT sheet_json FROM characters WHERE id = ? LIMIT 1", (int(character_id),)
        ).fetchone()
        if row:
            raw = row[0] if not hasattr(row, "keys") else row["sheet_json"]
            sheet = json.loads(raw or "{}")
            if isinstance(sheet, dict):
                conds = [c for c in (sheet.get("conditions") or []) if isinstance(c, dict)]
                kept = [c for c in conds if str(c.get("key") or "").strip().lower() != key_lo]
                if len(kept) != len(conds):
                    removed += len(conds) - len(kept)
                    sheet["conditions"] = kept
                    conn.execute(
                        "UPDATE characters SET sheet_json = ? WHERE id = ?",
                        (json.dumps(sheet, ensure_ascii=False), int(character_id)),
                    )
    except Exception:
        pass

    # 2) aktywny combatant gracza (jeśli walka trwa) — combat state w COMBAT_DB_PATH
    try:
        snap = get_active_combat(int(campaign_id)) if campaign_id else None
    except Exception:
        snap = None
    if snap:
        combatants = snap.get("combatants") or []
        changed = False
        for c in combatants:
            if not isinstance(c, dict) or c.get("type") != "player":
                continue
            conds = [x for x in (c.get("conditions") or []) if isinstance(x, dict)]
            kept = [x for x in conds if str(x.get("key") or "").strip().lower() != key_lo]
            if len(kept) != len(conds):
                removed += len(conds) - len(kept)
                c["conditions"] = kept
                changed = True
        if changed:
            try:
                with _conn() as cc:
                    _save_combat_row(
                        cc, int(campaign_id),
                        character_id=int(snap.get("character_id") or 0),
                        round_n=int(snap.get("round") or 1),
                        turn_order=list(snap.get("turn_order") or []),
                        current_turn=str(snap.get("current_turn") or ""),
                        combatants=list(combatants),
                        status=str(snap.get("status") or "active"),
                        ended_reason=snap.get("ended_reason"),
                        location_tag=snap.get("location_tag"),
                    )
                    cc.commit()
            except Exception:
                pass

    return removed


def add_condition_to_character(
    conn: sqlite3.Connection,
    character_id: int,
    campaign_id: int,
    condition_key: str,
) -> int:
    """S19 (#614): ODWROTNOŚĆ remove_condition_from_character — nałóż kondycję na postać
    (sheet_json.conditions) i — jeśli trwa walka — na combatanta gracza. Deklaratywne
    (klucz danymi, np. udany SKILL_TEST stealth → hidden), żadnego ``if key==...``.

    Zwraca liczbę nałożonych wystąpień (sheet + combat). 0 = nie nałożono (brak w katalogu / już aktywna).
    """
    key_lo = str(condition_key or "").strip().lower()
    if not key_lo or not character_id:
        return 0
    # Katalog czytamy osobnym połączeniem (Row factory gwarantowane) — passed conn bywa tuple-owy.
    with _conn() as _cat:
        entry = _build_condition_entry(_cat, key_lo, applied_at="skill_test_grant")
    if entry is None:
        return 0
    added = 0

    # 1) aktywny combatant gracza (jeśli walka trwa) — robione PRZED zapisem sheet, żeby nie
    #    trzymać niezatwierdzonego writu na `conn` podczas osobnego writu combatu (uniknięcie locka).
    try:
        snap = get_active_combat(int(campaign_id)) if campaign_id else None
    except Exception:
        snap = None
    if snap:
        combatants = snap.get("combatants") or []
        changed = False
        for c in combatants:
            if not isinstance(c, dict) or c.get("type") != "player":
                continue
            conds = [x for x in (c.get("conditions") or []) if isinstance(x, dict)]
            if not any(str(x.get("key") or "").strip().lower() == key_lo for x in conds):
                conds.append(dict(entry))
                c["conditions"] = conds
                changed = True
                added += 1
        if changed:
            try:
                with _conn() as cc:
                    _save_combat_row(
                        cc, int(campaign_id),
                        character_id=int(snap.get("character_id") or 0),
                        round_n=int(snap.get("round") or 1),
                        turn_order=list(snap.get("turn_order") or []),
                        current_turn=str(snap.get("current_turn") or ""),
                        combatants=list(combatants),
                        status=str(snap.get("status") or "active"),
                        ended_reason=snap.get("ended_reason"),
                        location_tag=snap.get("location_tag"),
                    )
                    cc.commit()
            except Exception:
                pass

    # 2) sheet_json.conditions (źródło prawdy poza walką) — na końcu, na passed conn.
    try:
        row = conn.execute(
            "SELECT sheet_json FROM characters WHERE id = ? LIMIT 1", (int(character_id),)
        ).fetchone()
        if row:
            raw = row[0] if not hasattr(row, "keys") else row["sheet_json"]
            sheet = json.loads(raw or "{}")
            if isinstance(sheet, dict):
                conds = [c for c in (sheet.get("conditions") or []) if isinstance(c, dict)]
                if not any(str(c.get("key") or "").strip().lower() == key_lo for c in conds):
                    conds.append(dict(entry))
                    sheet["conditions"] = conds
                    conn.execute(
                        "UPDATE characters SET sheet_json = ? WHERE id = ?",
                        (json.dumps(sheet, ensure_ascii=False), int(character_id)),
                    )
                    added += 1
    except Exception:
        pass

    return added


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
    # U11b (#557): czyta z game_items; fallback do game_config_items dla testowych baz
    max_chars = 2000
    try:
        rows = conn.execute(
            """
            SELECT key, label, kind,
                   price_gp AS value_gp,
                   effect_json,
                   json_extract(item_data, '$.item_type')    AS item_type,
                   json_extract(item_data, '$.ac_bonus')     AS ac_bonus,
                   json_extract(item_data, '$.charges')      AS charges,
                   json_extract(item_data, '$.effect_type')  AS effect_type,
                   json_extract(item_data, '$.effect_dice')  AS effect_dice,
                   json_extract(item_data, '$.effect_bonus') AS effect_bonus,
                   json_extract(item_data, '$.effect_target') AS effect_target,
                   description
            FROM game_items
            WHERE is_active = 1 AND COALESCE(approved, 1) = 1
              AND kind != 'weapon'
            ORDER BY kind ASC, key ASC
            LIMIT 60
            """
        ).fetchall()
    except sqlite3.OperationalError:
        # Fallback: stara tabela (testowe bazy bez game_items, przed U11c)
        try:
            rows = conn.execute(
                """
                SELECT key, label, item_type,
                       COALESCE(value_gp, 0) AS value_gp,
                       NULL AS effect_json, charges, ac_bonus, description,
                       item_type AS kind,
                       effect_type, effect_dice,
                       COALESCE(effect_bonus, 0) AS effect_bonus,
                       effect_target
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
        # Resolve display type: kind dla armor/consumable, item_type dla pozostałych
        kind = str(r["kind"] or "item").strip().lower()
        item_type_raw = str(r["item_type"] or "").strip().lower()
        t = kind if kind in ("armor", "consumable") else (item_type_raw or kind or "misc")
        if t == "narrative":
            continue
        if t != current_type:
            current_type = t
            lines.append(f"  [{t.upper()}]")
        key = str(r["key"])
        label = str(r["label"] or key)
        parts: list[str] = [f"    - {key}: {label}"]

        if t == "armor":
            ac_b = r["ac_bonus"]
            if ac_b is not None and int(ac_b or 0) > 0:
                parts.append(f"(AC +{int(ac_b)})")

        if t == "consumable":
            legacy = legacy_effect_fields_from_json(r["effect_json"]) or {}
            eff = str(legacy.get("effect_type") or r["effect_type"] or "misc")
            dice = str(legacy.get("effect_dice") or r["effect_dice"] or "").strip()
            bonus = int(legacy.get("effect_bonus") or r["effect_bonus"] or 0)
            target = str(legacy.get("effect_target") or r["effect_target"] or "self")
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
        # S12 (#607): kondycje do nałożenia, gdy bieżąca wygasa (on_expire_apply, np. hasted→exhausted).
        pending_on_expire: list[tuple[str, int]] = []
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
                # S13 (#608): +2 defensywny (derived stat 'save', np. blessed) dolicza się do
                # rzutów obronnych (periodic_save). Data-driven — żaden if key == "blessed".
                modifier += _combatant_stat_modifier(actor, sheet=sheet, stat="save")
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
                # S12 (#607): kondycja wygasła → zbierz on_expire_apply (np. hasted → exhausted 1).
                for ef in effects:
                    if str(ef.get("type") or "").strip().lower() != "on_expire_apply":
                        continue
                    tgt = str(ef.get("condition_key") or "").strip().lower()
                    if not tgt:
                        continue
                    try:
                        lvl = int(ef.get("value") or 1)
                    except (TypeError, ValueError):
                        lvl = 1
                    pending_on_expire.append((tgt, max(1, lvl)))
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

            # S9 (#604): stacking_levels — progi (threshold_effects) odpalają się,
            # gdy runtime poziom kondycji ≥ próg (np. exhausted poziom 2 → omdlenie).
            for effect in effects:
                if str(effect.get("type") or "").strip().lower() != "stacking_levels":
                    continue
                level = _condition_level(condition)
                thresholds = effect.get("threshold_effects")
                if not isinstance(thresholds, dict):
                    continue
                for thr_key, thr_eff in thresholds.items():
                    try:
                        thr = int(thr_key)
                    except (TypeError, ValueError):
                        continue
                    if level < thr or not isinstance(thr_eff, dict):
                        continue
                    if str(thr_eff.get("type") or "").strip().lower() == "block_action":
                        blocked = True
                        events.append({
                            "type": "block_action",
                            "condition_key": key,
                            "condition_label": label,
                        })

            # S8 (#603): `dot` — damage-over-time po kości (np. on_fire 2d6/turę).
            # Schema-zgodny prymityw; tyka raz na turę aktora (dedup po markerze).
            for effect_idx, effect in enumerate(effects):
                if str(effect.get("type") or "").strip().lower() != "dot":
                    continue
                tick = str(effect.get("tick") or "start_turn").strip().lower()
                if tick not in {"start_turn", "each_round"}:
                    continue
                dstate = _condition_effect_state(condition, f"dot_{effect_idx}")
                if str(dstate.get("last_turn_marker") or "") == marker:
                    continue
                dstate["last_turn_marker"] = marker
                runtime_changed = True
                raw_val = effect.get("value")
                dmg = int(raw_val) if isinstance(raw_val, (int, float)) else roll_damage_dice(str(raw_val or "1d4"))
                if dmg > 0:
                    prev_hp = int(actor.get("hp_current", 0) or 0)
                    actor["hp_current"] = max(0, prev_hp - dmg)
                    events.append({
                        "type": "condition_damage",
                        "condition_key": key,
                        "condition_label": label,
                        "damage": dmg,
                        "damage_type": str(effect.get("damage_type") or "physical"),
                        "hp_after": int(actor.get("hp_current", 0)),
                    })
                    conditions_changed = True

            # S10 (#605): `escalating_dot` — DOT narastający w czasie (hemorrhage 1d4/turę,
            # +1d4 co 3 tury). Licznik tyknięć w effect_state przeżywa między rundami.
            for effect_idx, effect in enumerate(effects):
                if str(effect.get("type") or "").strip().lower() != "escalating_dot":
                    continue
                tick = str(effect.get("tick") or "start_turn").strip().lower()
                if tick not in {"start_turn", "each_round"}:
                    continue
                estate = _condition_effect_state(condition, f"edot_{effect_idx}")
                if str(estate.get("last_turn_marker") or "") == marker:
                    continue
                estate["last_turn_marker"] = marker
                ticks_done = int(estate.get("ticks", 0) or 0)
                dmg = _escalating_dot_damage(effect, ticks_done)
                estate["ticks"] = ticks_done + 1
                runtime_changed = True
                if dmg > 0:
                    prev_hp = int(actor.get("hp_current", 0) or 0)
                    actor["hp_current"] = max(0, prev_hp - dmg)
                    events.append({
                        "type": "condition_damage",
                        "condition_key": key,
                        "condition_label": label,
                        "damage": dmg,
                        "damage_type": str(effect.get("damage_type") or "physical"),
                        "hp_after": int(actor.get("hp_current", 0)),
                    })
                    conditions_changed = True

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

        # S12 (#607): nałóż kondycje z on_expire_apply wygasłych kondycji (np. hasted → exhausted 1).
        for tgt_key, tgt_level in pending_on_expire:
            existing = next(
                (c for c in next_conditions if str(c.get("key") or "").strip().lower() == tgt_key),
                None,
            )
            if existing is not None:
                cap = _condition_max_level(existing)
                _set_condition_level(existing, min(cap, _condition_level(existing) + tgt_level))
                conditions_changed = True
                events.append({"type": "condition_applied", "condition_key": tgt_key,
                               "condition_label": existing.get("label"), "reason": "on_expire"})
                continue
            entry = _build_condition_entry(conn, tgt_key, applied_at="on_expire", level=tgt_level)
            if entry is None:
                continue
            next_conditions.append(entry)
            conditions_changed = True
            events.append({"type": "condition_applied", "condition_key": tgt_key,
                           "condition_label": entry.get("label"), "reason": "on_expire"})

        # S18 (#613): wymuszone zachowanie aktora bieżącej tury (behavior_override).
        # Liczone z kondycji, które PRZEŻYŁY tę turę (po ewentualnym save_success/expire) — udany
        # rzut WIS „otrzeźwia" i znosi wymuszenie. roll=True → k4 (confused) wyznaczone RAZ na turę
        # i zapisane w runtime, żeby resolve_attack odczytał tę samą decyzję.
        actor["conditions"] = next_conditions
        forced_behavior = _resolve_forced_behavior(actor, actor_id, round_n, roll=True)
        if forced_behavior is not None and forced_behavior.get("behavior") == "random_table_k4":
            runtime_changed = True  # k4 zapisane w runtime → wymuś persist

        if conditions_changed or runtime_changed:
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
                        # S9 (#604): zachowaj runtime (poziom stackowania) — inaczej kara
                        # ×poziom ginie przy synchronizacji combatant → sheet gracza.
                        "runtime": condition.get("runtime") if isinstance(condition.get("runtime"), dict) else {},
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

    # S18 (#613): banner dla gracza — tura NIE jest przejmowana w całości (UX).
    if forced_behavior is not None and actor_type == "player":
        _banner = {
            "stand": "stoisz otępiały — nie możesz działać w tej turze.",
            "attack_random": "atakujesz na oślep losowy cel.",
            "flee": "instynkt każe ci się cofnąć.",
            "normal": "na chwilę odzyskujesz jasność — działaj normalnie.",
        }
        if forced_behavior.get("behavior") == "random_table_k4":
            message_lines.append(
                f"{forced_behavior.get('condition_label') or 'Zdezorientowany'} (k4="
                f"{forced_behavior.get('k4')}): "
                f"{_banner.get(forced_behavior.get('action'), 'los decyduje o twoim ruchu.')}"
            )
        elif forced_behavior.get("action") == "flee":
            message_lines.append(
                f"{forced_behavior.get('condition_label') or 'Spanikowany'}: musisz uciekać od zagrożenia."
            )

    return {
        "blocked": bool(blocked),
        "actor_id": actor_id,
        "actor_type": actor_type,
        "events": events,
        "forced_behavior": forced_behavior,
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
        hp_cur, hp_max = _player_hp_pair(sheet)
        ac = _player_ac_from_sheet(sheet)
        dex_mod = _stat_mod(sheet, "DEX")
        init_player = roll_d20() + dex_mod
        ability_stats = _ability_stats_seven(sheet)
        # F1 (#461): weapon Effect Objects applied at combat-start
        _wrow_init = resolve_sheet_weapon(conn, sheet, int(character_id))
        _wac = _weapon_ac_bonus(_wrow_init)
        if _wac:
            ac += _wac
        # F2 (#495): affix ac_bonus on equipped weapon instance
        _aac = _inventory_affix_ac_bonus(conn, int(character_id))
        if _aac:
            ac += _aac
        # F7 (#467): broken armor reduces AC at combat start
        try:
            from app.services.durability_service import get_ac_penalty_for_char as _dur_ac_pen_fn
            _dur_ac_pen = _dur_ac_pen_fn(conn, int(character_id))
            if _dur_ac_pen:
                ac += _dur_ac_pen
        except Exception:
            pass
        _wmods = _weapon_stat_modifiers(_wrow_init)
        if _wmods:
            for _st, _delta in _wmods.items():
                if _st in ability_stats:
                    ability_stats[_st] = int(ability_stats.get(_st, 10) or 10) + _delta
        # F2 (#495): affix static_stat_modifier on equipped weapon instance
        _amods = _inventory_affix_stat_modifiers(conn, int(character_id))
        if _amods:
            for _st, _delta in _amods.items():
                if _st in ability_stats:
                    ability_stats[_st] = int(ability_stats.get(_st, 10) or 10) + _delta

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
                # D2 (#377) — unknown enemy key → create a pending_review template so
                # the fight proceeds and the enemy lands in the admin review queue,
                # instead of silently dropping it (mirrors D1 item pending flow).
                logger.info(
                    "combat_unknown_enemy_key_pending",
                    enemy_key=ek,
                    campaign_id=campaign_id,
                    message="[COMBAT] unknown enemy key → creating pending_review template",
                )
                er = _create_pending_combat_enemy(conn, ek)
                if not er:
                    logger.warning("combat_pending_enemy_unavailable", enemy_key=ek, campaign_id=campaign_id)
                    continue
            resolved_enemies.append((ek, er))

        if not resolved_enemies:
            raise ValueError("no valid enemy keys after filtering unknown templates")

        turn_slots: list[tuple[str, int, int]] = [("player", init_player, 0)]
        idx = 0
        for ek, er in resolved_enemies:
            idx += 1
            slug = _enemy_slug(ek, idx)
            hp_max_e = int(er["hp_base"] or 1)
            ac_e = int(er["ac_base"] or 10)
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
                    "loot_tier": er["loot_tier"] if "loot_tier" in er.keys() else None,
                    "zone": _default_zone_for_enemy(er["key"], er["label"]),
                    # Stored now for opposed checks in upcoming [S1b] formulas (T30).
                    "skills": _parse_enemy_skills(er["skills_json"]),
                    # S2 (#582): 7 ability stats for opposed skill checks (S4). NULL/missing
                    # → every stat defaults to 10 (parse_stats_json), zero combat regression.
                    "stats": parse_stats_json(er["stats_json"] if "stats_json" in er.keys() else None),
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

    # Sync scene_enemies world-state column from active combatants.
    # gate_service reads `hp` (not hp_current) and `key` fields.
    enemy_entries = [
        {"key": c["enemy_key"], "name": c["name"], "hp": c["hp_current"]}
        for c in out.get("combatants", [])
        if c.get("type") == "enemy"
    ]
    try:
        set_world_state_flags(campaign_id, scene_enemies=enemy_entries)
    except Exception:
        pass

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


def _choose_behavior_target(
    combatants: list[dict], attacker: dict, action: str,
) -> dict[str, Any] | None:
    """S18 (#613): wybór celu dla wymuszonego ataku (attack_nearest/attack_random).

    Kandydaci = WSZYSTKIE żywe inne combatanty (gracz I wrogowie) — berserk/confused bije
    niezależnie od frakcji. attack_nearest: preferuj cel w tej samej strefie (zwarcie/dystans);
    przy braku — pierwszy z brzegu. attack_random: losowy spośród kandydatów. Zwraca dict albo None.
    """
    aid = str(attacker.get("id") or "")
    candidates = [
        c for c in combatants
        if isinstance(c, dict) and str(c.get("id") or "") != aid
        and int(c.get("hp_current", 0) or 0) > 0
    ]
    if not candidates:
        return None
    if action == "attack_random":
        return random.choice(candidates)
    # attack_nearest — preferuj tę samą strefę co atakujący.
    a_zone = str(attacker.get("zone") or ZONE_ENGAGED)
    same_zone = [c for c in candidates if str(c.get("zone") or ZONE_ENGAGED) == a_zone]
    return (same_zone or candidates)[0]


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
            # F7 (#467): broken weapon reduces attack roll
            try:
                from app.services.durability_service import get_attack_penalty_for_char as _dur_atk_fn
                _dur_atk_pen = _dur_atk_fn(conn, ch_id)
                if _dur_atk_pen:
                    roll_result = int(roll_result) + _dur_atk_pen
                    out["durability_attack_penalty"] = _dur_atk_pen
            except Exception:
                pass
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
                player_attack_log_meta = json.dumps(
                    {
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
                    },
                    ensure_ascii=False,
                )

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
                # U2 (#510): weapon wears down when player lands a hit
                try:
                    from app.services.durability_service import decrement_weapon_durability_on_attack as _decr_wpn
                    _decr_wpn(conn, ch_id)
                except Exception as _dur_err:
                    logger.warning("weapon_durability_decrement_error", error=str(_dur_err))
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
                # F1 (#461) + F2 (#462): flat damage_bonus from weapon effect_json
                # and from affixes on the equipped weapon instance (added once,
                # post-multiplier — gear bonus is flat, not doubled on crit)
                _flat_bonus = _weapon_flat_damage_bonus(wrow)
                _flat_bonus += _inventory_affix_damage_bonus(conn, ch_id)
                # S14 (#609): kondycje gracza z stat_target `damage_bonus` (np. rage +3) doliczają
                # płaski bonus do obrażeń (post-mnożnik, jak gear — nie podwajany na cricie).
                _pc_for_dmg = _find_combatant(combatants, "player")
                if _pc_for_dmg is not None:
                    _flat_bonus += _combatant_stat_modifier(_pc_for_dmg, sheet=None, stat="damage_bonus")
                if _flat_bonus:
                    dmg += _flat_bonus
                    out["damage_bonus"] = _flat_bonus
                # S19 (#614): zasadzka — pierwszy atak z ukrycia (ambush_bonus) dolicza +Nk6 RAZ
                # jako oddzielny add PO mnożniku (jak gear — nie podwajany na cricie/nat20). Rzut
                # ataku gracza (nat 20/nat 1) NIETKNIĘTY. Atak zdejmuje hidden (demaskuje).
                if _pc_for_dmg is not None:
                    _hidden = _hidden_conditions(_pc_for_dmg)
                    if _hidden:
                        _ambush = _roll_ambush_bonus(_hidden)
                        if _ambush:
                            dmg += _ambush
                            out["ambush_bonus"] = _ambush
                        _remove_combatant_conditions(_pc_for_dmg, _hidden)
                out["damage"] = dmg
                prev_hp = int(enemy.get("hp_current", 0) or 0)
                next_hp = max(0, prev_hp - dmg)
                enemy["hp_current"] = next_hp
                out["target_hp_remaining"] = next_hp
                # F1 (#461) + F2 (#495): heal_on_hit from weapon effect_json and affixes
                _heal = _weapon_heal_on_hit(wrow) + _inventory_affix_heal_on_hit(conn, ch_id)
                if _heal:
                    _pc = _find_combatant(combatants, "player")
                    if _pc is not None:
                        _pc_max = int(_pc.get("hp_max", 0) or 0)
                        _pc_cur = int(_pc.get("hp_current", 0) or 0)
                        _pc["hp_current"] = min(_pc_max, _pc_cur + _heal) if _pc_max > 0 else _pc_cur + _heal
                        out["heal_on_hit"] = _heal
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
                # F1 (#461): typed apply_condition Effects (gear_bonus schema)
                _f1_conds = _weapon_apply_conditions(wrow, enemy, conn)
                if _f1_conds:
                    _prev_conds = list(out.get("weapon_conditions_applied") or [])
                    out["weapon_conditions_applied"] = _prev_conds + _f1_conds
                # F2 (#495): apply_condition from affixes on equipped weapon instance
                _a_conds = _inventory_affix_apply_conditions(conn, ch_id, enemy)
                if _a_conds:
                    _prev_conds = list(out.get("weapon_conditions_applied") or [])
                    out["weapon_conditions_applied"] = _prev_conds + _a_conds
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
                    # U25 (#575): flag boss kills so post-combat loot claim can drive
                    # the affix pity timer (guaranteed affix after a dry streak).
                    if str(enemy.get("tier") or "").strip().lower() == "boss":
                        try:
                            conn.execute(
                                "UPDATE active_combat SET boss_defeated = 1 WHERE campaign_id = ?",
                                (campaign_id,),
                            )
                        except sqlite3.OperationalError:
                            pass
                    if ek and ch_id:
                        try:
                            from app.services.loot_service import (
                                apply_character_gold_delta,
                                roll_gold_drop,
                                roll_loot,
                            )

                            loot_items = roll_loot(ek)
                            _enemy_loot_tier = str(enemy.get("loot_tier") or "") or None
                            if loot_items:
                                loot = _preview_loot_from_roll_items(loot_items, loot_tier=_enemy_loot_tier)
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
                    # #550: Auto-complete kill_enemy beats — resolve_attack bypasses turn_pipeline
                    try:
                        from app.services.campaign_plan_runtime import auto_complete_beats_by_event
                        _enemy_label = str(enemy.get("name") or enemy.get("enemy_key") or ek or "")
                        if _enemy_label:
                            _tn_beat = conn.execute(
                                "SELECT COALESCE(MAX(turn_number), 0) FROM campaign_turns"
                                " WHERE campaign_id = ?",
                                (campaign_id,),
                            ).fetchone()[0]
                            auto_complete_beats_by_event(
                                campaign_id, "kill_enemy", _enemy_label, _tn_beat, conn
                            )
                    except Exception:
                        pass
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
                        # HF-1 (#523): clear scene_enemies after victory — bypass end_combat() path
                        try:
                            set_world_state_flags(campaign_id, scene_enemies=[])
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
                # S19 (#614): nawet nieudany atak demaskuje — zdejmij hidden (brak bonusu na pudle).
                _pc_miss = _find_combatant(combatants, "player")
                if _pc_miss is not None:
                    _hidden_miss = _hidden_conditions(_pc_miss)
                    if _hidden_miss:
                        _remove_combatant_conditions(_pc_miss, _hidden_miss)

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

        # ── S18 (#613): behavior_override — kondycja steruje turą wroga (confused/berserk/panicked).
        # evaluate_current_turn_conditions (wołane na początku resolve_attack) już rzuciło k4 i
        # zapisało decyzję; tu ją tylko ODCZYTUJEMY (roll=False) i wykonujemy. Zastępuje normalne AI.
        _ensure_zones(combatants)
        _fb = _resolve_forced_behavior(enemy, str(cur), int(row["round"] or 1), roll=False)
        if _fb is not None:
            _action = str(_fb.get("action") or "")
            out["forced_behavior"] = _fb
            out["enemy_name"] = str(enemy.get("name") or enemy.get("enemy_key") or "Wróg").strip()
            cid_b = int(row["id"])

            def _log_behavior(extra: dict) -> None:
                payload = {"behavior": _fb.get("behavior"), "action": _action,
                           "condition": _fb.get("condition_key"), "enemy_name": out["enemy_name"]}
                payload.update(extra)
                log_combat_turn(
                    conn, combat_id=cid_b, campaign_id=campaign_id,
                    turn_number=_next_combat_log_sequence(conn, cid_b), actor="enemy",
                    event_type="behavior", roll_value=extra.get("attack_roll"),
                    damage=extra.get("damage"), hp_after=int(enemy.get("hp_current", 0) or 0),
                    target_id=extra.get("target_id") or str(cur),
                    target_name=extra.get("target_name") or out["enemy_name"], hit=extra.get("hit"),
                    narrative=json.dumps(payload, ensure_ascii=False),
                )

            if _action == "stand":
                out["hit"] = False
                out["damage"] = 0
                _log_behavior({"target_id": str(cur)})
                _persist_combatants(conn, row, combatants, loot_pool=loot_pool_accum)
                conn.commit()
                out["combat_state"] = load_combat_snapshot(campaign_id)
                return out

            if _action == "flee":
                old_zone = str(enemy.get("zone") or ZONE_ENGAGED)
                enemy["zone"] = ZONE_RANGED
                out["hit"] = False
                out["damage"] = 0
                out["zone_change"] = {"actor_id": str(cur), "from": old_zone, "to": ZONE_RANGED, "fled": True}
                _log_behavior({"target_id": str(cur), "from": old_zone, "to": ZONE_RANGED})
                _persist_combatants(conn, row, combatants, loot_pool=loot_pool_accum)
                conn.commit()
                out["combat_state"] = load_combat_snapshot(campaign_id)
                return out

            if _action in ("attack_nearest", "attack_random"):
                target = _choose_behavior_target(combatants, enemy, _action)
                # Cel = gracz (lub brak celu) → normalna ścieżka ataku na gracza (przelot niżej).
                if target is not None and str(target.get("id") or "") != "player":
                    raw_b = roll_d20()
                    atk_b = (int(enemy.get("attack_bonus") or 0)
                             + _combatant_stat_modifier(enemy, sheet=None, stat="attack_bonus"))
                    wp_b = wound_penalty(int(enemy.get("hp_current", 0) or 0), int(enemy.get("hp_max", 0) or 0))
                    attack_roll_b = raw_b + atk_b + wp_b
                    tgt_ac = (int(target.get("defense", 10) or 10)
                              + _combatant_stat_modifier(target, sheet=None, stat="ac"))
                    hit_b = attack_roll_b >= tgt_ac
                    dmg_b = 0
                    if hit_b:
                        dmg_b = roll_damage_dice((enemy.get("damage_dice") or "1d6").strip().lower(),
                                                 _combatant_stat_modifier(enemy, sheet=None, stat="damage_bonus"))
                        target["hp_current"] = max(0, int(target.get("hp_current", 0) or 0) - dmg_b)
                    out["hit"] = bool(hit_b)
                    out["damage"] = int(dmg_b)
                    out["attack_roll"] = int(attack_roll_b)
                    out["raw_d20"] = int(raw_b)
                    out["target_id"] = str(target.get("id"))
                    out["target_name"] = str(target.get("name") or target.get("id"))
                    out["target_hp_remaining"] = int(target.get("hp_current", 0) or 0)
                    out["target_incapacitated"] = int(target.get("hp_current", 0) or 0) <= 0
                    _log_behavior({"target_id": str(target.get("id")),
                                   "target_name": out["target_name"], "attack_roll": int(attack_roll_b),
                                   "damage": int(dmg_b), "hit": bool(hit_b)})
                    _persist_combatants(conn, row, combatants, loot_pool=loot_pool_accum)
                    conn.commit()
                    out["combat_state"] = load_combat_snapshot(campaign_id)
                    return out
            # _action == "normal" (k4=4) lub cel=gracz → przelot do normalnej ścieżki ataku na gracza.

        # ── Zone AI: melee enemy in different zone charges instead of attacking ──
        _ensure_zones(combatants)
        player_c = _find_combatant(combatants, "player") or {}

        # ── S19 (#614): gracz z kondycją hidden jest UNTARGETABLE — wróg nie może go zaatakować.
        # Zamiast ataku próbuje wykryć: rzut WIS (staty wroga z S2) vs detect_dc (z effect_json hidden).
        # Sukces = zdejmuje hidden (gracz wykryty); porażka = gracz pozostaje ukryty. Tura zużyta.
        # Data-driven — żaden ``if condition_key == "hidden"``. Rzut ataku wroga nietknięty.
        if _combatant_is_untargetable(player_c):
            detect_dc = _actor_detect_dc(player_c)
            raw_det = roll_d20()
            wis_mod = _combatant_stat_modifier(enemy, sheet=None, stat="WIS")
            det_total = raw_det + wis_mod
            detected = raw_det == 20 or (raw_det != 1 and det_total >= detect_dc)
            out["hit"] = False
            out["damage"] = 0
            out["enemy_name"] = str(enemy.get("name") or enemy.get("enemy_key") or "Wróg").strip()
            out["detection"] = {
                "dc": int(detect_dc), "roll": int(raw_det), "wis_mod": int(wis_mod),
                "total": int(det_total), "detected": bool(detected),
            }
            if detected:
                _remove_combatant_conditions(player_c, _hidden_conditions(player_c))
                out["detection"]["revealed"] = True
            cid_d = int(row["id"])
            log_combat_turn(
                conn, combat_id=cid_d, campaign_id=campaign_id,
                turn_number=_next_combat_log_sequence(conn, cid_d), actor="enemy",
                event_type="detection", roll_value=int(raw_det), damage=None,
                hp_after=int(enemy.get("hp_current", 0) or 0), target_id="player",
                target_name=out["enemy_name"], hit=None,
                narrative=json.dumps(out["detection"], ensure_ascii=False),
            )
            _persist_combatants(conn, row, combatants, loot_pool=loot_pool_accum)
            conn.commit()
            advance_turn(campaign_id)
            out["combat_state"] = load_combat_snapshot(campaign_id)
            return out

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
            advance_turn(campaign_id)
            out["combat_state"] = load_combat_snapshot(campaign_id)
            return out

        raw = roll_d20()
        # S18 (#613): kondycje wroga z static_stat_modifier attack_bonus (np. berserk +3) foldują
        # się generycznie w atak. Zero regresji — żaden istniejący wróg nie ma tego modyfikatora.
        atk_b = int(enemy.get("attack_bonus") or 0) + _combatant_stat_modifier(enemy, sheet=None, stat="attack_bonus")
        wp = wound_penalty(
            int(enemy.get("hp_current", 0) or 0),
            int(enemy.get("hp_max", 0) or 0),
        )
        attack_roll = raw + atk_b + wp
        out["wound_penalty"] = wp
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
        _dodge = None
        _block = None  # S18 (#613): init przed `if hit` — log reakcji (S16) czyta _block też przy pudle
        if hit:
            # U2 (#510): armor wears down on received hit (weapon decay is on player attack)
            try:
                from app.services.durability_service import decrement_armor_durability_on_hit as _decr_arm
                _decr_arm(conn, ch_id)
            except Exception as _dur_err:
                logger.warning("armor_durability_decrement_error", error=str(_dur_err))
            expr = (enemy.get("damage_dice") or "1d6").strip().lower()
            # S18 (#613): berserk damage_bonus (+3) foldowane generycznie.
            dmg = roll_damage_dice(expr, _combatant_stat_modifier(enemy, sheet=None, stat="damage_bonus"))
            # S15 (#610): okno reakcji — unik PRZED aplikacją obrażeń. Rzut ataku wroga już
            # rozliczony (nat 20/nat 1 nietknięte); reakcja działa tylko na obrażenia po trafieniu.
            _dodge = _try_dodge_reaction(p, sheet, attack_roll, int(row["round"] or 1))
            if _dodge is not None:
                out["reaction"] = _dodge
                if _dodge.get("dodged"):
                    dmg = 0
            else:
                # S16 (#611): jeśli unik nie zadeklarowany, sprawdź blok tarczą (XOR — jedna
                # reakcja/rundę). Redukcja/odparcie obrażeń PRZED aplikacją; rzut ataku wroga
                # nietknięty. Crit-fail bije durability tarczy (hook czyta character_inventory).
                _block = _try_shield_block_reaction(
                    conn, ch_id, p, sheet, attack_roll, int(row["round"] or 1), dmg)
                if _block is not None:
                    out["reaction"] = _block
                    if _block.get("available"):
                        dmg = int(_block.get("damage_after", dmg))
            out["damage"] = dmg
            prev = int(p.get("hp_current", 0) or 0)
            next_hp = max(0, prev - dmg)
            # S13 (#608): jeśli cios sprowadziłby HP do ≤0, kondycja z efektem on_zero_hp_save
            # (np. blessed CON DC 12) może wykonać rzut ratunkowy i zostawić 1 HP zamiast
            # nieprzytomności. Rzut ataku/obrażenia wroga BEZ ZMIAN — hook tylko w momencie HP≤0.
            if next_hp <= 0:
                # Kondycje gracza w walce żyją na combatancie (`p`), nie na sheet → sheet=None,
                # by helper czytał p.conditions (blessed) i p.stats.
                save_res = _on_zero_hp_save(p, sheet=None)
                if save_res is not None:
                    out["on_zero_hp_save"] = save_res
                    if save_res.get("saved") and save_res.get("hp"):
                        next_hp = int(save_res["hp"])
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

        # S15 (#610): osobny wpis reakcji uniku — Sandbox/UI pokazuje test DEX i wynik.
        if _dodge is not None and _dodge.get("available"):
            tn_r = _next_combat_log_sequence(conn, cid)
            log_combat_turn(
                conn,
                combat_id=cid,
                campaign_id=campaign_id,
                turn_number=tn_r,
                actor="player",
                event_type="reaction",
                roll_value=int(_dodge.get("dodge_total") or 0),
                damage=None,
                hp_after=int(p.get("hp_current", 0) or 0),
                target_id="player",
                target_name=str(p.get("name") or "Bohater"),
                hit=bool(_dodge.get("dodged")),
                narrative=json.dumps(
                    {
                        "reaction": "dodge",
                        "d20": _dodge.get("d20"),
                        "dodge_total": _dodge.get("dodge_total"),
                        "attack_roll": _dodge.get("attack_roll"),
                        "margin": _dodge.get("margin"),
                        "outcome": _dodge.get("outcome"),
                        "dodged": _dodge.get("dodged"),
                        "locked_next_round": _dodge.get("locked_next_round"),
                    },
                    ensure_ascii=False,
                ),
            )

        # S16 (#611): osobny wpis reakcji bloku — Sandbox/UI pokazuje test STR, redukcję i wynik.
        if _block is not None and _block.get("available"):
            tn_b = _next_combat_log_sequence(conn, cid)
            log_combat_turn(
                conn,
                combat_id=cid,
                campaign_id=campaign_id,
                turn_number=tn_b,
                actor="player",
                event_type="reaction",
                roll_value=int(_block.get("block_total") or 0),
                damage=int(_block.get("damage_after") or 0),
                hp_after=int(p.get("hp_current", 0) or 0),
                target_id="player",
                target_name=str(p.get("name") or "Bohater"),
                hit=bool(_block.get("full_block") or (_block.get("reduction") or 0) > 0),
                narrative=json.dumps(
                    {
                        "reaction": "shield_block",
                        "d20": _block.get("d20"),
                        "block_total": _block.get("block_total"),
                        "attack_roll": _block.get("attack_roll"),
                        "dc": _block.get("dc"),
                        "margin": _block.get("margin"),
                        "outcome": _block.get("outcome"),
                        "reduction": _block.get("reduction"),
                        "damage_before": _block.get("damage_before"),
                        "damage_after": _block.get("damage_after"),
                        "full_block": _block.get("full_block"),
                        "durability_hit": _block.get("durability_hit"),
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


def declare_player_reaction(campaign_id: int, reaction_type: str = "dodge") -> dict[str, Any]:
    """S15 (#610) — pre-deklaracja reakcji (toggle). NIE zużywa tury.

    UX solo: zamiast modala przerywającego auto-procesowane tury wroga, gracz z góry
    deklaruje „Unikaj następnego ataku". Flaga ``reaction_declared`` żyje na combatancie
    gracza i jest konsumowana przy pierwszym trafieniu wroga (patrz ``_try_dodge_reaction``).
    Ponowne wywołanie tego samego typu = anulowanie (toggle off). Wymaga tury gracza oraz
    odpowiedniego skilla rank ≥ 1 (skill-gated feature)."""
    rt = str(reaction_type or "dodge").strip().lower()
    if rt not in {"dodge", "shield_block"}:
        raise ValueError(f"unknown reaction_type: {rt}")
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM active_combat WHERE campaign_id = ? AND status = 'active'",
            (campaign_id,),
        ).fetchone()
        if not row:
            raise ValueError("no active combat")
        if str(row["current_turn"]) != "player":
            raise ValueError("reaction can only be declared on player's turn")
        combatants: list[dict] = json.loads(row["combatants"] or "[]")
        p = _find_combatant(combatants, "player")
        if not p:
            raise ValueError("player combatant missing")
        ch_id = int(row["character_id"])
        ch = conn.execute("SELECT sheet_json FROM characters WHERE id = ?", (ch_id,)).fetchone()
        sheet = json.loads(ch["sheet_json"] or "{}") if ch and ch["sheet_json"] else {}
        try:
            skill_rank = int((sheet.get("skills") or {}).get(rt, 0) or 0)
        except (TypeError, ValueError):
            skill_rank = 0
        if skill_rank < 1:
            raise ValueError(f"skill '{rt}' rank >= 1 required to declare this reaction")
        # S16 (#611): blok tarczą wymaga ZAŁOŻONEJ tarczy (gate ekwipunku).
        if rt == "shield_block":
            has_shield, _ = _player_has_shield_equipped(conn, ch_id)
            if not has_shield:
                raise ValueError("shield_block requires an equipped shield")
        if str(p.get("reaction_declared") or "") == rt:
            p.pop("reaction_declared", None)
            declared = None
        else:
            p["reaction_declared"] = rt
            declared = rt
        _persist_combatants(conn, row, combatants)
        conn.commit()
    return {
        "ok": True,
        "reaction_declared": declared,
        "combat_state": load_combat_snapshot(campaign_id),
    }


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

        # S12 (#607): jeśli gracz ma aktywną, niewykorzystaną w tej turze `extra_action`
        # (np. hasted → move_only), zmiana strefy jest DARMOWA — nie zużywa tury. Drugą
        # zmianę w tej samej turze już rozliczamy normalnie (advance_turn). Marker = runda+aktor
        # → flaga resetuje się sama, gdy gracz znów dostanie turę w kolejnej rundzie.
        round_n = int(row["round"] or 1)
        marker = _condition_turn_marker(round_n, "player")
        free_action = False
        if _actor_extra_action_kind(p) in {"move_only"}:
            if str(p.get("extra_action_used_marker") or "") != marker:
                p["extra_action_used_marker"] = marker
                free_action = True

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

    if not free_action:
        advance_turn(campaign_id)
    return {
        "ok": True,
        "from": old,
        "to": new,
        "extra_action_used": free_action,
        "combat_state": load_combat_snapshot(campaign_id),
    }


# ─── S17 (#612): Wrestling — akcja bojowa, opposed STR vs STR, wynik → kondycja.

def _apply_skill_outcome_conditions(
    campaign_id: int,
    mapping: dict[str, Any],
    outcome: str,
    target_ref: str | None,
) -> list[dict[str, Any]]:
    """Stopień testu (S1) → kondycja nakładana na CEL lub na GRACZA — w pełni DANYMI.

    ``mapping`` = ``{on_success_condition, on_crit_condition, on_critfail_self_condition}``.
    Prymityw raz (Zasada 1 FAZY S): ZERO ``if skill_key == ...`` / ``if condition_key == ...``
    — wrestling (i przyszłe skille nakładające kondycje wynikiem) podają mapping jako dane.
    Reużywa istniejących ścieżek: cel → ``apply_condition_to_combatant``; gracz (samo-
    przewrócenie przy krytycznej porażce) → ``apply_condition_to_player``. Sukces krytyczny
    woła ``on_crit_condition`` (mocniejsza), z fallbackiem na ``on_success_condition``."""
    oc = str(outcome or "").strip().upper()
    applied: list[dict[str, Any]] = []
    if oc == "CRITICAL_SUCCESS":
        key = mapping.get("on_crit_condition") or mapping.get("on_success_condition")
        if key and target_ref:
            applied.append({"who": "target", "condition": key,
                            "result": apply_condition_to_combatant(campaign_id, target_ref, key)})
    elif oc == "SUCCESS":
        key = mapping.get("on_success_condition")
        if key and target_ref:
            applied.append({"who": "target", "condition": key,
                            "result": apply_condition_to_combatant(campaign_id, target_ref, key)})
    elif oc == "CRITICAL_FAILURE":
        key = mapping.get("on_critfail_self_condition")
        if key:
            applied.append({"who": "self", "condition": key,
                            "result": apply_condition_to_player(campaign_id, key)})
    # FAILURE → nic (cel zachowuje swobodę ruchów)
    return applied


def _load_skill_outcome_mapping(conn: Any, skill_key: str) -> dict[str, Any]:
    """Wczytaj generyczne pola wynik→kondycja ze ``skill_counters`` (S17, data-driven).

    Brak kolumn (stary schemat) lub rekordu → mapping bez kondycji (bezpieczny no-op).
    Przyszłe skille deklaratywnie dodają wiersze — bez dotykania silnika."""
    try:
        r = conn.execute(
            "SELECT counter_key, on_success_condition, on_crit_condition, on_critfail_self_condition "
            "FROM skill_counters WHERE player_skill_key = ? LIMIT 1",
            (skill_key,),
        ).fetchone()
    except sqlite3.OperationalError:
        return {"counter_key": "STR"}
    if not r:
        return {"counter_key": "STR"}
    return {
        "counter_key": str(r[0] or "STR").upper(),
        "on_success_condition": r[1],
        "on_crit_condition": r[2],
        "on_critfail_self_condition": r[3],
    }


def resolve_wrestling(campaign_id: int, target_ref: str | None = None) -> dict[str, Any]:
    """S17 (#612) — Zapasy: akcja bojowa. Test przeciwny STR vs STR; wynik nakłada kondycję.

    Gate: tura gracza + ZWARCIE (gracz i cel w strefie ``engaged``). Cel poza zwarciem →
    ``{ok:False, blocked:True, block_reason:'out_of_range'}`` BEZ konsumpcji tury (wzorzec
    melee out_of_range). Silnik rzuca obie strony (``d20 + STR_mod`` [+ rank + proficiency
    gracza]); stopień liczy S1 (``_derive_outcome``). Mapowanie wynik→kondycja jest DANYMI
    ze ``skill_counters`` (Zasada 1). Sukces → kondycja na wrogu; krytyk → mocniejsza;
    krytyczna porażka → kondycja na graczu. Konsumuje turę (``advance_turn``).

    RZUTY ATAKU W WALCE (nat 20/nat 1, podwójne obrażenia) NIETKNIĘTE — wrestling to test
    umiejętności; margines dotyczy wyłącznie jego."""
    ref_lo = str(target_ref or "").strip().lower()
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM active_combat WHERE campaign_id = ? AND status = 'active'",
            (campaign_id,),
        ).fetchone()
        if not row:
            raise ValueError("no active combat")
        if str(row["current_turn"]) != "player":
            raise ValueError("wrestling only on player's turn")
        combatants: list[dict] = json.loads(row["combatants"] or "[]")
        _ensure_zones(combatants)
        p = _find_combatant(combatants, "player")
        if not p:
            raise ValueError("player combatant missing")

        # Rozwiąż cel: po referencji (key/name contains) albo pierwszy żywy wróg w zwarciu.
        target = None
        for c in combatants:
            if not isinstance(c, dict) or c.get("type") != "enemy":
                continue
            if int(c.get("hp_current", 0) or 0) <= 0:
                continue
            if ref_lo:
                ek = str(c.get("enemy_key", "")).lower()
                nm = str(c.get("name", "")).lower()
                if ref_lo == ek or ref_lo == nm or ref_lo in ek or ref_lo in nm:
                    target = c
                    break
            elif str(c.get("zone") or ZONE_ENGAGED) == ZONE_ENGAGED:
                target = c
                break
        if target is None and not ref_lo:
            target = next((c for c in combatants if isinstance(c, dict)
                           and c.get("type") == "enemy" and int(c.get("hp_current", 0) or 0) > 0), None)
        if target is None:
            raise ValueError("no living enemy target")

        # Gate zwarcia — gracz i cel muszą być engaged. Blok bez konsumpcji tury.
        if str(p.get("zone") or ZONE_ENGAGED) != ZONE_ENGAGED or \
           str(target.get("zone") or ZONE_ENGAGED) != ZONE_ENGAGED:
            return {"ok": False, "blocked": True, "block_reason": "out_of_range",
                    "target": str(target.get("name") or target.get("enemy_key") or ""),
                    "combat_state": load_combat_snapshot(campaign_id)}

        # Skill rank gracza z sheet (proficiency +2 od rank ≥ 3 — spójnie z testami umiejętności).
        ch = conn.execute(
            "SELECT sheet_json FROM characters WHERE id = ?", (int(row["character_id"]),)
        ).fetchone()
        sheet = json.loads(ch["sheet_json"] or "{}") if ch and ch["sheet_json"] else {}
        try:
            skill_rank = int((sheet.get("skills") or {}).get("wrestling", 0) or 0)
        except (TypeError, ValueError):
            skill_rank = 0
        proficiency = 2 if skill_rank >= 3 else 0

        mapping = _load_skill_outcome_mapping(conn, "wrestling")
        stat = str(mapping.get("counter_key") or "STR").upper()

        # Test przeciwny: obie strony rzucają (kondycje fold-ują się w stat_mod).
        player_mod = _combatant_stat_modifier(p, sheet=None, stat=stat) + skill_rank + proficiency
        enemy_mod = _combatant_stat_modifier(target, sheet=None, stat=stat)
        player_d20 = roll_d20()
        enemy_d20 = roll_d20()
        opponent_total = enemy_d20 + enemy_mod
        from app.services.skill_service import _derive_outcome  # S1 — jeden silnik stopnia wyniku
        derived = _derive_outcome(player_d20, player_mod, opponent_total)

        target_key = str(target.get("enemy_key") or target.get("name") or target.get("id"))
        target_name = str(target.get("name") or target.get("enemy_key") or "Wróg")

        cid = int(row["id"])
        tn = _next_combat_log_sequence(conn, cid)
        log_combat_turn(
            conn,
            combat_id=cid,
            campaign_id=campaign_id,
            turn_number=tn,
            actor="player",
            event_type="wrestling",
            roll_value=int(derived["player_total"]),
            damage=None,
            hp_after=int(p.get("hp_current", 0) or 0),
            target_id=str(target.get("id")),
            target_name=target_name,
            hit=bool(derived["success"]),
            narrative=json.dumps({
                "outcome": derived["outcome"], "margin": derived["margin"],
                "player_roll": player_d20, "player_total": derived["player_total"],
                "enemy_roll": enemy_d20, "enemy_total": opponent_total, "stat": stat,
            }, ensure_ascii=False),
        )
        _persist_combatants(conn, row, combatants)
        conn.commit()

    # Nakładanie kondycji PO zamknięciu conn (apply_* otwierają własne połączenia).
    applied = _apply_skill_outcome_conditions(campaign_id, mapping, derived["outcome"], target_key)
    advance_turn(campaign_id)
    return {
        "ok": True,
        "outcome": derived["outcome"],
        "margin": derived["margin"],
        "success": derived["success"],
        "player_roll": player_d20,
        "player_total": derived["player_total"],
        "enemy_roll": enemy_d20,
        "enemy_total": opponent_total,
        "stat": stat,
        "target": target_name,
        "applied": applied,
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
            # HF-1 (#523): clear scene_enemies — this path bypasses end_combat()
            try:
                set_world_state_flags(campaign_id, scene_enemies=[])
            except Exception:
                pass
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
            # HF-1 (#523): clear scene_enemies — this path bypasses end_combat()
            try:
                set_world_state_flags(campaign_id, scene_enemies=[])
            except Exception:
                pass
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

    # Clear scene_enemies when combat ends (any reason).
    try:
        set_world_state_flags(campaign_id, scene_enemies=[])
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
        loot_tier_for_grant: str | None = None
        for entry in chosen_rows:
            e = dict(entry or {})
            qty = max(1, int(e.get("quantity") or 1))
            key = str(e.get("key") or "").strip()
            t = str(e.get("item_type") or "").strip().lower()
            if not key:
                continue
            if t == "weapon":
                enemy_loot_tier = str(e.get("enemy_loot_tier") or "") or None
                if enemy_loot_tier and not loot_tier_for_grant:
                    loot_tier_for_grant = enemy_loot_tier
                to_grant.append({"weapon_key": key, "quantity": qty})
            else:
                to_grant.append({"item_key": key, "quantity": qty})

        from app.services.loot_service import grant_loot_to_character, build_drop_comparison

        # U25 (#575): was a boss defeated this combat? Drives the affix pity timer.
        boss_killed = bool(row["boss_defeated"]) if "boss_defeated" in row.keys() else False

        claimed = grant_loot_to_character(
            character_id, to_grant, source="loot", loot_tier=loot_tier_for_grant,
            is_boss_kill=boss_killed,
        ) if (to_grant or boss_killed) else []

        # U17 (#565): attach a drop-comparison block to each claimed weapon/armor so the
        # player UI can celebrate affixed/rare drops and show a diff vs the equipped item.
        for entry in claimed:
            inv_id = entry.get("inventory_id")
            if inv_id is None:
                continue
            try:
                comparison = build_drop_comparison(character_id, int(inv_id))
                if comparison:
                    entry["comparison"] = comparison
            except Exception:
                # Celebration is best-effort cosmetics — never block a loot claim on it.
                pass

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
