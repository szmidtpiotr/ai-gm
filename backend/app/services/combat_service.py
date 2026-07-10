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
from app.core.mechanics import proficiency_bonus
from app.services.event_logger import write_game_event
from app.services.weapon_rules import (
    load_weapon_row,
    parry_defense_bonus,
    player_dual_combo_for_character,
    resolve_attack_roll_for_weapon,
    resolve_sheet_weapon,
    stat_modifier,
)
from app.services.wound_utils import wound_penalty
from app.services.world_state_service import set_world_state_flags

# Tests may monkeypatch this to a temp file path.
COMBAT_DB_PATH = "/data/ai_gm.db"

logger = get_logger(__name__)

# G16 (#784): per-campaign HP/mana isolation for multiplayer
_MP_STATE_FIELDS = frozenset(("current_hp", "current_mana", "conditions"))


def _save_char_sheet(
    conn: sqlite3.Connection, campaign_id: int, character_id: int, sheet: dict
) -> None:
    """Write character sheet to DB, routing battle-state fields to CCS for MP campaigns.

    For multiplayer campaigns: HP/mana/conditions go to character_campaign_state;
    sheet_json is written WITHOUT those fields so solo campaigns are unaffected.
    For solo campaigns: write full sheet_json (unchanged behaviour).
    """
    from app.services.campaign_state_service import is_mp_campaign, save_battle_state

    if is_mp_campaign(conn, campaign_id):
        save_battle_state(conn, campaign_id, int(character_id), sheet)
        dev_sheet = {k: v for k, v in sheet.items() if k not in _MP_STATE_FIELDS}
        conn.execute(
            "UPDATE characters SET sheet_json = ? WHERE id = ?",
            (json.dumps(dev_sheet, ensure_ascii=False), int(character_id)),
        )
    else:
        conn.execute(
            "UPDATE characters SET sheet_json = ? WHERE id = ?",
            (json.dumps(sheet, ensure_ascii=False), int(character_id)),
        )


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
    out: dict[str, Any] = {
        "atk_bonus": 0, "first_hit_doubled": False, "first_hit_auto": False,
        "consumed_keys": [],
    }
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
            # D2 (#780): wróg nie zdążył zareagować — pierwszy cios trafia automatycznie
            # (jak Nat20-do-trafienia, ale BEZ dodatkowego podwojenia z tego tytułu).
            out["first_hit_auto"] = True
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


# B4 (#645): łotrzyk — sneak attack jako cecha klasy (decyzja D2, Piotr 2026-06-15).
# Wartość startowa kości (Numbers Policy — tuning po B5/B13). Płaska, niezależna od poziomu.
ROGUE_SNEAK_ATTACK_DICE = "1d6"


def _rogue_sneak_dice_for_level(level: int) -> str:
    """D3 (#780): skalowanie kości sneak łotrzyka wg poziomu.

    L1-4 → 1d6, L5-8 → 2d6, L9+ → 3d6. Czysta funkcja (bez rzutu)."""
    try:
        lvl = int(level)
    except (TypeError, ValueError):
        lvl = 1
    if lvl >= 9:
        return "3d6"
    if lvl >= 5:
        return "2d6"
    return "1d6"


def _sneak_attack_bonus(sheet: dict[str, Any] | None) -> int:
    """B4 (#645) + D3 (#780): obrażenia sneak attack łotrzyka, skalowane poziomem.

    CECHA KLASY — rzut tylko dla ``archetype == 'rogue'``; każda inna klasa (oraz
    brak/niepełny sheet) → 0 bez rzutu. Kość wg poziomu (L1-4 1d6 / L5-8 2d6 / L9+
    3d6). Add ponad generyczny ``ambush_bonus`` (S19 #614). Liczy silnik
    (``roll_damage_dice``); LLM tylko opisuje."""
    if str((sheet or {}).get("archetype") or "").strip().lower() != "rogue":
        return 0
    _dice = _rogue_sneak_dice_for_level((sheet or {}).get("level", 1) or 1)
    return int(roll_damage_dice(_dice, 0))


def _should_fire_burst(target: dict[str, Any] | None, *, player_hidden: bool) -> bool:
    """burst (#780): otwarcie ze skradania daje wrogowi `zaskoczony`, ale graczowi
    NIE `hidden`. Sneak die / podwójne obrażenia mają palić się w OBU przypadkach:
    gdy gracz `hidden` LUB gdy cel `zaskoczony`. Unifikacja `hidden`(gracz) vs
    `zaskoczony`(wróg)."""
    if player_hidden:
        return True
    if not isinstance(target, dict):
        return False
    for c in (target.get("conditions") or []):
        if isinstance(c, dict) and str(c.get("key", "")).lower() == "zaskoczony":
            return True
    return False


def build_advantage_gate(source: str | None, advantage_bonus: int = 2) -> dict[str, Any] | None:
    """D1 (#780): bramka intencji po zdobyciu przewagi pozycyjnej.

    Po dowolnej przewadze (sukces Stealth, grapple, wróg ogłuszony/schwytany,
    „nóż do gardła") silnik STOP i pyta gracza zamiast cicho ustawiać flagę i
    zależeć od LLM. Zwraca strukturę 4 przycisków (atak / zastraszenie / wycofaj / dialog)
    do renderu w UI gracza. ``None`` gdy brak źródła przewagi.

    #1000: intimidate i withdraw używają prefiksu __GATE:xxx zamiast prozy —
    backend obsługuje je deterministycznie (bez LLM) i czyści pending_zaskoczony."""
    if not source or not str(source).strip():
        return None
    src = str(source).strip()
    gate = {
        "source": src,
        "title": "Masz przewagę.",
        "options": [
            {
                "id": "strike",
                "icon": "⚔️",
                "label": "Atak z zaskoczenia",
                "hint": "Zaatakuj zanim Cię zauważy — pełny cios zasadzki.",
                # Tekst tury — uruchamia normalny przepływ walki (COMBAT_START po stronie LLM).
                # pending_zaskoczony kasowane przez COMBAT_START handler (linia ~1003 turns.py).
                "action": "Atakuję z zaskoczenia, zanim zdąży zareagować.",
            },
            {
                "id": "intimidate",
                "icon": "💬",
                "label": "Zastraszenie",
                # #1054: bonus skaluje się wg jakości Skradania (+2 sukces / +4 kryt).
                "hint": f"Wymuś uległość bez zabijania — test Zastraszania z bonusem przewagi +{int(advantage_bonus)}.",
                # #1000: prefiks __GATE: → backend od razu ustawia pending_skill_test
                # dla 'intimidation' z bonusem +2 i czyści pending_zaskoczony. Bez LLM.
                "action": "__GATE:intimidate",
            },
            {
                "id": "withdraw",
                "icon": "👤",
                "label": "Wycofaj się",
                "hint": "Zniknij w cieniu, zachowując przewagę na później.",
                # #1000: prefiks __GATE: → backend czyści pending_zaskoczony i narruje odwrót.
                "action": "__GATE:withdraw",
            },
            {
                "id": "dialog",
                "icon": "🗣️",
                "label": "Porozmawiaj / zapytaj",
                "hint": "Podejdź spokojnie i zacznij rozmowę — wolne wejście tekstowe.",
                # #1000: prefiks __GATE: → backend czyści pending_zaskoczony i narruje podejście.
                # Po odpowiedzi gracz może pisać swój własny dialog dowolnym tekstem.
                "action": "__GATE:dialog",
            },
        ],
    }
    # #773 (grapple) — gdy przewaga pochodzi z deklaracji obezwładnienia, dołącz
    # deterministyczną mapę rozwiązania (3A): sukces → kondycja `schwytany` na celu,
    # porażka → COMBAT_START. Frontend/silnik używa jej zamiast zgadywania po narracji.
    if src.lower() in ("grapple", "subdue"):
        gate["subdue_resolution"] = {
            "success": subdue_outcome_to_effect("SUCCESS"),
            "failure": subdue_outcome_to_effect("FAILURE"),
        }
    return gate


def subdue_outcome_to_effect(outcome: str) -> dict[str, Any]:
    """#773 (3A): deterministyczne mapowanie wyniku obezwładnienia (grapple poza walką).

    Wzorzec _derive_outcome (S1). Sukces nakłada na cel kondycję `schwytany`
    (block_action — wróg nie atakuje ani nie ucieka); naturalna 20 dokłada `bonus`
    (np. wróg ogłuszony / mówi prawdę). Porażka ZAWSZE startuje walkę (decyzja A3=A),
    a krytyczna porażka oddaje wrogowi inicjatywę kontrataku."""
    o = str(outcome or "").strip().upper()
    if o in ("SUCCESS", "CRITICAL_SUCCESS"):
        eff: dict[str, Any] = {"apply_condition": "schwytany", "to": "target"}
        if o == "CRITICAL_SUCCESS":
            eff["bonus"] = True
        return eff
    return {"combat_start": True, "enemy_initiative": o == "CRITICAL_FAILURE"}


def combat_correction_message(reason: str, target_name: str) -> str:
    """HF-7/#780: uczciwy komunikat korekty gdy [COMBAT_START] zostaje odrzucony.

    Poprzedni tekst „Cel ataku okazuje się nieosiągalny" KŁAMAŁ — cel bywał
    osiągnięty (casus Mizela: nóż do gardła), a walka nie wybuchała z innego
    powodu. Tu komunikat nie twierdzi już, że cel jest nieosiągalny."""
    if reason == "combat_target_friendly_npc":
        return f"*({target_name} cofa się o krok, ale nie sięga po broń — to nie wróg.)*"
    return "*(Na razie nie dochodzi do otwartej walki.)*"


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

def _record_reaction_rolls(campaign_id, character_id, combat_id, round_n, out) -> None:
    """#754: zapis rzutów reakcyjnych (unik/blok) + save z 0 HP do dice_rolls. Best-effort."""
    try:
        from app.services.dice_log_service import record_dice_roll as _rec_roll
        rx = out.get("reaction") or {}
        if rx and rx.get("d20") is not None:
            rtype = "dodge" if rx.get("reaction") == "dodge" else "shield_block"
            _rec_roll(
                campaign_id=campaign_id, roll_type=rtype, character_id=character_id,
                combat_id=combat_id, actor="player", notation="1d20",
                raw_rolls=[int(rx["d20"])],
                modifiers={"dex_mod": rx.get("dex_mod"), "str_mod": rx.get("str_mod"),
                           "skill_rank": rx.get("skill_rank")},
                total=int(rx.get("dodge_total") or rx.get("block_total") or rx.get("player_total") or 0),
                dc=int(rx.get("attack_roll") or 0),
                outcome=(rx.get("outcome") or ("dodged" if rx.get("dodged") else "blocked")),
                meta={"round": round_n, "available": rx.get("available")},
            )
        save = out.get("on_zero_hp_save") or {}
        if save and save.get("raw") is not None:
            _rec_roll(
                campaign_id=campaign_id, roll_type="save", character_id=character_id,
                combat_id=combat_id, actor="player", notation="1d20",
                raw_rolls=[int(save["raw"])], total=int(save.get("total") or 0),
                dc=int(save.get("dc") or 0),
                outcome="success" if save.get("saved") else "fail",
                meta={"round": round_n, "stat": save.get("stat"),
                      "condition": save.get("condition_key")},
            )
    except Exception:
        pass


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
    proficiency = proficiency_bonus(skill_rank)
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
    proficiency = proficiency_bonus(skill_rank)
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


# ─── B16 (#822): system reakcji czarów (mirror_image / blink / globe_invulnerability).
# MVP = STAN PREWENCYJNY: czar rzucony WCZEŚNIEJ zapisuje stan na combatancie; stan
# auto-odpala się przy NASTĘPNYM trafieniu wroga, w punkcie PRZED obrażeniami —
# wcześniej niż okno dodge/block (negujący cios czar pomija okno reakcji). Bez
# prawdziwego interrupt-window między turami (poza zakresem MVP).

def _roll_d100() -> int:
    """Rzut d100 (1–100) — szansa pudła `blink`. Wydzielony, by testy mogły monkeypatchować."""
    return random.randint(1, 100)


def _try_spell_reaction(
    p: dict[str, Any],
    round_n: int,
    out: dict[str, Any],
) -> dict[str, Any] | None:
    """Auto-wyzwalana czar-reakcja PRZED aplikacją obrażeń. Wołane gdy cios wroga TRAFIŁ.

    Priorytet rozstrzygania: ``globe_invulnerability`` > ``mirror_image`` > ``blink``.
    Zwraca dict ``{"type","negated":True,...}`` gdy cios ZNEGOWANY (obrażenia → 0) i zapisuje
    go do ``out["spell_reaction"]``; zwraca ``None`` gdy żaden stan nie znegował ciosu (silnik
    idzie normalną ścieżką dodge/block/obrażeń). Mutuje stan na combatancie:
      • ``globe_invulnerability`` (``until_round``) — N rund nietykalności, BEZ zużycia ładunku;
        po wygaśnięciu rund klucz usuwany.
      • ``mirror_image`` (``charges``) — każdy cios zużywa 1 ładunek; pula 0 → klucz usuwany.
      • ``blink`` (``miss_chance``/``until_round``) — d100 ≤ miss_chance → pudło (0 dmg); trwa do
        końca rund (kolejne ciosy też losują); po wygaśnięciu rund klucz usuwany.
    """
    # 1) globe_invulnerability — okno N rund nietykalności (najwyższy priorytet)
    globe = p.get("globe_invulnerability")
    if isinstance(globe, dict):
        if int(round_n) <= int(globe.get("until_round") or 0):
            sr = {"type": "globe_invulnerability", "negated": True,
                  "until_round": int(globe.get("until_round") or 0)}
            out["spell_reaction"] = sr
            return sr
        p.pop("globe_invulnerability", None)  # wygasło

    # 2) mirror_image — pula ładunków anulowania (każdy cios = -1 ładunek)
    mi = p.get("mirror_image")
    if isinstance(mi, dict):
        charges = int(mi.get("charges") or 0)
        if charges > 0:
            charges -= 1
            if charges > 0:
                mi["charges"] = charges
            else:
                p.pop("mirror_image", None)
            sr = {"type": "mirror_image", "negated": True, "charges_remaining": charges}
            out["spell_reaction"] = sr
            return sr
        p.pop("mirror_image", None)  # pusta pula

    # 3) blink — % szansy pudła przez N rund
    bl = p.get("blink")
    if isinstance(bl, dict):
        if int(round_n) <= int(bl.get("until_round") or 0):
            chance = int(bl.get("miss_chance") or 0)
            roll = _roll_d100()
            blinked = roll <= chance
            sr = {"type": "blink", "negated": bool(blinked), "roll": int(roll),
                  "miss_chance": chance, "until_round": int(bl.get("until_round") or 0)}
            out["spell_reaction"] = sr
            return sr if blinked else None
        p.pop("blink", None)  # wygasło

    return None


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


def roll_dice_detailed(expr: str) -> dict[str, Any]:
    """Roll NdM, return per-die rolls + normalized notation.

    #661: dice-visualization needs the individual die results (not just the sum)
    so the frontend can animate the right number/type of dice landing on them.
    expr like '1d8', 'd6', '2d6'. Returns {die, rolls, sides, n}; rolls=[] if unparseable.
    """
    raw = (expr or "1d4").strip().lower()
    m = re.match(r"^(\d*)d(\d+)$", raw)
    if not m:
        return {"die": raw, "rolls": [], "sides": 0, "n": 0}
    n = max(1, int(m.group(1) or 1))
    sides = int(m.group(2))
    rolls = [random.randint(1, sides) for _ in range(n)]
    return {"die": f"{n}d{sides}", "rolls": rolls, "sides": sides, "n": n}


def roll_damage_dice(expr: str, mod: int = 0) -> int:
    """Roll NdM + mod; expr like '1d8', 'd6', '2d6'."""
    d = roll_dice_detailed(expr)
    if not d["rolls"]:
        return max(0, mod)
    return max(0, sum(d["rolls"]) + mod)


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
               loot_table_key, drop_chance, COALESCE(xp_award, 0) AS xp_award,
               COALESCE(attacks_per_turn, 1) AS attacks_per_turn,
               image_url
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
        # #1283 — same auto-loot heuristic as the [CREATE_ENEMY] tag path: this
        # combat-triggered creation is the one that actually fires in live play.
        from app.services.world_service import _auto_populate_enemy_loot
        _auto_populate_enemy_loot(conn, enemy_key, "standard", name)
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


_LOOT_LABEL_TABLE = {
    "weapon": "game_config_weapons",
    "consumable": "game_config_consumables",
    "item": "game_config_items",
}


def _lookup_loot_label(conn: sqlite3.Connection, item_type: str, key: str) -> str | None:
    """#746: pobierz polską etykietę z odpowiedniej tabeli konfiguracyjnej.
    Zwraca None gdy klucza nie ma w DB (caller degraduje do key.replace)."""
    table = _LOOT_LABEL_TABLE.get(item_type)
    if not table:
        return None
    try:
        row = conn.execute(
            f"SELECT label FROM {table} WHERE key = ? LIMIT 1", (key,)
        ).fetchone()
    except sqlite3.OperationalError:
        return None
    if not row:
        return None
    label = str(row["label"] or "").strip()
    return label or None


def _preview_loot_from_roll_items(
    loot_items: list[dict[str, Any]],
    loot_tier: str | None = None,
    conn: sqlite3.Connection | None = None,
) -> list[dict[str, Any]]:
    # #746: etykiety łupu muszą pochodzić z DB (polskie nazwy), nie z key.replace.
    # Otwórz własne połączenie gdy caller go nie podał (zamknij na końcu).
    _owns_conn = conn is None
    if _owns_conn:
        conn = _conn()
    try:
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
            label = _lookup_loot_label(conn, item_type, key) or key.replace("_", " ")
            out.append(
                {
                    "label": label,
                    "item_type": item_type,
                    "quantity": qty,
                    "source": "loot",
                    "key": key,
                    "enemy_loot_tier": loot_tier if item_type == "weapon" else None,
                }
            )
        return out
    finally:
        if _owns_conn:
            conn.close()


def _row_to_combat_dict(row: sqlite3.Row) -> dict[str, Any]:
    _combatants = json.loads(row["combatants"] or "[]")
    _ensure_zones(_combatants)  # backfill zone for pre-T34 combats; harmless if all set
    # SF10 (#633): ukryj liczbę obrażeń pending_reaction przed frontendem (wybór = zakład).
    # Zostaw flagę okna + opcje, usuń `damage` z migawki.
    for _c in _combatants:
        _pr = _c.get("pending_reaction")
        if isinstance(_pr, dict) and "damage" in _pr:
            _pr = {k: v for k, v in _pr.items() if k != "damage"}
            _c["pending_reaction"] = _pr
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

def _resolve_effect_spell_in_combat(
    conn, row, campaign_id: int, ch_id: int, sheet: dict, combatants: list,
    enemy: dict, target_id, spell_row, raw_d20, out: dict[str, Any],
) -> dict[str, Any]:
    """B9 (#656): rozlicz czar NIE-atakujący (kondycja) w aktywnej walce.

    Pojedynek przeciwny INT vs stat obrony celu (`spell_service.resolve_combat_effect_spell`):
      • łapie  → `apply_condition_to_combatant` (reużycie kondycji FAZY S), pełna mana
      • opór   → kondycja NIE nałożona, ½ many zwrócona (kara = tylko tura)
      • Nat 1  → miscast (pełna mana, bez kondycji)
    Czar kontroli NIE zadaje obrażeń. Tury NIE zaawansowujemy tu — parytet z atakiem gracza
    (turę „zużywa" pierwszy enemy-turn, jak przy zwykłym ataku).
    """
    from app.services import spell_service

    condition_key = str(spell_row["effect_type"] or "").strip().lower()
    mana_cost = int(spell_row["mana_cost"] or 0)
    label = str(spell_row["label"] or spell_row["key"])
    spell_k = str(spell_row["key"])

    out["weapon_key"] = spell_k
    out["weapon_label"] = label
    out["weapon_type"] = "spell"
    out["attack_test"] = "spell_effect"
    out["spell_type"] = "effect"
    out["condition_key"] = condition_key
    out["target_id"] = target_id
    out["target_name"] = str(enemy.get("name") or "") or None
    out["enemy_key"] = str(enemy.get("enemy_key") or "")
    out["damage"] = 0  # czar kontroli nie zadaje obrażeń

    # Mana z góry (pełny koszt; ½ wraca przy oporze). Darmowy czar (mana 0) pomija kontrolę.
    if mana_cost > 0:
        _mana_ok, _new_mana = spell_service.check_and_deduct_mana(
            sheet, mana_cost, campaign_id=campaign_id,
            character_id=row["character_id"], combat_id=int(row["id"]))
        if not _mana_ok:
            out["hit"] = False
            out["blocked"] = True
            out["mana_insufficient"] = True
            out["current_mana"] = int(sheet.get("current_mana", 0))
            out["message"] = (
                f"Brak many! Potrzebujesz {mana_cost} many, "
                f"masz {int(sheet.get('current_mana', 0))}."
            )
            out["combat_state"] = _row_to_combat_dict(row)
            return out
        _save_char_sheet(conn, campaign_id, int(row["character_id"]), sheet)
        conn.commit()

    player_raw = int(raw_d20) if raw_d20 is not None else None
    target_stats = enemy.get("stats") if isinstance(enemy.get("stats"), dict) else {}
    resolution = spell_service.resolve_combat_effect_spell(
        sheet, target_stats, condition_key, mana_cost, raw_d20=player_raw,
    )
    out["spell_effect"] = resolution
    out["player_raw_d20"] = player_raw
    out["player_nat1"] = (player_raw == 1)

    if resolution["outcome"] == "miscast":
        _char_race_row = conn.execute("SELECT race FROM characters WHERE id=?", (int(row["character_id"]),)).fetchone()
        _char_race = ((_char_race_row["race"] if _char_race_row else None) or "human")
        _miscast = spell_service.resolve_miscast(sheet, enemy, conn, race=_char_race)
        out["miscast"] = _miscast
        out["hp_after"] = _miscast.get("hp_after", int(sheet.get("current_hp", 0)))
        _save_char_sheet(conn, campaign_id, int(row["character_id"]), sheet)
        conn.commit()
        out["hit"] = False
        out["condition_applied"] = False
    elif resolution["outcome"] == "landed":
        # Persist combatants (identity/zone) PRZED apply-condition: apply_condition_to_combatant
        # czyta świeży stan z DB i dopisuje kondycję — kolejność chroni przed nadpisaniem.
        _persist_combatants(conn, row, combatants)
        conn.commit()
        target_ref = str(enemy.get("enemy_key") or enemy.get("name") or target_id)
        _ac = apply_condition_to_combatant(campaign_id, target_ref, condition_key)
        out["condition_result"] = _ac
        out["condition_applied"] = bool(_ac.get("ok")) and _ac.get("reason") in (
            "applied", "level_bumped", "level_capped", "already_present",
        )
        out["hit"] = bool(out["condition_applied"])
    else:  # resisted → zwrot ½ many, brak kondycji
        refund = int(resolution.get("mana_refund") or 0)
        if refund > 0:
            cur = int(sheet.get("current_mana", 0) or 0)
            mx = int(sheet.get("max_mana", 0) or 0)
            sheet["current_mana"] = min(mx, cur + refund) if mx > 0 else cur + refund
            _save_char_sheet(conn, campaign_id, int(row["character_id"]), sheet)
            conn.commit()
        out["mana_refund"] = refund
        out["condition_applied"] = False
        out["hit"] = False

    out["current_mana"] = int(sheet.get("current_mana", 0))

    # Progresja rangi czaru — udane rzucenie liczy się jak użycie (jak czary atakujące).
    try:
        spell_service.record_spell_use(int(row["character_id"]), spell_k, conn)
    except Exception:
        pass

    cid = int(row["id"])
    log_combat_turn(
        conn,
        combat_id=cid,
        campaign_id=campaign_id,
        turn_number=_next_combat_log_sequence(conn, cid),
        actor="player",
        event_type="spell_effect",
        roll_value=int(player_raw) if player_raw is not None else None,
        damage=0,
        hp_after=int(enemy.get("hp_current", 0) or 0),
        target_id=target_id,
        target_name=str(enemy.get("name") or "") or None,
        hit=bool(out.get("condition_applied")),
        narrative=json.dumps(
            {
                "spell_key": spell_k, "spell_label": label,
                "condition": condition_key, "outcome": resolution["outcome"],
                "save_stat": resolution.get("save_stat"),
                "mana_refund": int(out.get("mana_refund") or 0),
            },
            ensure_ascii=False,
        ),
    )
    conn.commit()
    out["combat_state"] = load_combat_snapshot(campaign_id)
    return out


def _resolve_aoe_effect_spell_in_combat(
    conn, row, campaign_id: int, ch_id: int, sheet: dict, combatants: list,
    enemy: dict, target_id, spell_row, raw_d20, out: dict[str, Any],
) -> dict[str, Any]:
    """B17 (#823): czar kontroli OBSZAROWY (mass_fear) — kondycja na WSZYSTKICH żywych wrogach.

    Casting stat = INT (decyzja D3, 2026-06-21: czary maga spójnie na INT, nie CHA). Model D-spell:
    pojedynek przeciwny `d20+INT_mod (mag)` vs `d20+stat_obrony (cel)` rozstrzygany OSOBNO per wróg
    (`spell_service.resolve_spell_opposed_save`, stat obrony wg kondycji — WIS umysł / CON ciało):
      • łapie na wrogu → kondycja nałożona (reużycie `_build_condition_entry` + `apply_condition_gate`)
      • opór           → ten wróg bez kondycji
      • Nat 1          → miscast (cała mana, zero kondycji)
    Mana = pełny koszt z góry, BEZ zwrotu (czar obszarowy płaci jak attack_aoe, niezależnie od trafień).
    Zero obrażeń (to czar kontroli). Operuje na dict-ach combatantów wprost (nie po enemy_key) —
    poprawnie celuje wielu wrogów o TYM SAMYM kluczu. Tury nie zaawansowujemy (parytet z effect ST).
    """
    from app.services import spell_service

    condition_key = str(spell_row["effect_type"] or "").strip().lower()
    mana_cost = int(spell_row["mana_cost"] or 0)
    label = str(spell_row["label"] or spell_row["key"])
    spell_k = str(spell_row["key"])

    out["weapon_key"] = spell_k
    out["weapon_label"] = label
    out["weapon_type"] = "spell"
    out["attack_test"] = "spell_effect_aoe"
    out["spell_type"] = "effect_aoe"
    out["condition_key"] = condition_key
    out["target_id"] = target_id
    out["target_name"] = str(enemy.get("name") or "") or None
    out["enemy_key"] = str(enemy.get("enemy_key") or "")
    out["damage"] = 0  # czar kontroli nie zadaje obrażeń

    # Mana pełny koszt z góry (AoE nie zwraca — jak attack_aoe).
    if mana_cost > 0:
        _mana_ok, _new_mana = spell_service.check_and_deduct_mana(
            sheet, mana_cost, campaign_id=campaign_id,
            character_id=row["character_id"], combat_id=int(row["id"]))
        if not _mana_ok:
            out["hit"] = False
            out["blocked"] = True
            out["mana_insufficient"] = True
            out["current_mana"] = int(sheet.get("current_mana", 0))
            out["message"] = (
                f"Brak many! Potrzebujesz {mana_cost} many, "
                f"masz {int(sheet.get('current_mana', 0))}."
            )
            out["combat_state"] = _row_to_combat_dict(row)
            return out
        out["mana_spent"] = mana_cost
        out["mana_after"] = _new_mana
        _save_char_sheet(conn, campaign_id, int(row["character_id"]), sheet)
        conn.commit()

    player_raw = int(raw_d20) if raw_d20 is not None else None
    out["player_raw_d20"] = player_raw
    out["player_nat1"] = (player_raw == 1)

    # Nat 1 → miscast (pełna mana, brak kondycji na nikim).
    if player_raw == 1:
        _char_race_row = conn.execute("SELECT race FROM characters WHERE id=?", (int(row["character_id"]),)).fetchone()
        _char_race = ((_char_race_row["race"] if _char_race_row else None) or "human")
        _miscast = spell_service.resolve_miscast(sheet, enemy, conn, race=_char_race)
        out["miscast"] = _miscast
        out["hp_after"] = _miscast.get("hp_after", int(sheet.get("current_hp", 0)))
        _save_char_sheet(conn, campaign_id, int(row["character_id"]), sheet)
        conn.commit()
        out["hit"] = False
        out["condition_applied"] = False
        out["aoe_effect_hits"] = []
        out["current_mana"] = int(sheet.get("current_mana", 0))
        out["combat_state"] = load_combat_snapshot(campaign_id)
        return out

    # Pojedynek per żywy wróg → kondycja tym, którzy przegrali save.
    cond_entry = _build_condition_entry(conn, condition_key, applied_at="spell_aoe_effect")
    effect_json = cond_entry.get("effect_json") if cond_entry else None
    aoe_hits: list[dict[str, Any]] = []
    any_applied = False
    for c in combatants:
        if not isinstance(c, dict) or c.get("type") == "player":
            continue
        if int(c.get("hp_current", 0) or 0) <= 0:
            continue
        tgt_stats = c.get("stats") if isinstance(c.get("stats"), dict) else {}
        save = spell_service.resolve_spell_opposed_save(sheet, tgt_stats, condition_key)
        landed = bool(save.get("landed")) and cond_entry is not None
        applied = False
        if landed:
            conds = c.get("conditions")
            if not isinstance(conds, list):
                conds = []
            # S14 (#609): bramka immunitetu/broken_by PRZED dopisaniem (mutuje conds w miejscu).
            allowed, _gate = apply_condition_gate(conds, condition_key, effect_json)
            c["conditions"] = conds
            already = any(
                isinstance(x, dict) and str(x.get("key", "")).lower() == condition_key
                for x in conds
            )
            if allowed and not already:
                conds.append(dict(cond_entry))
                applied = True
            if applied or already:
                any_applied = True
        aoe_hits.append({
            "target_id": str(c.get("id") or ""),
            "target_name": str(c.get("name") or c.get("enemy_key") or "Wróg"),
            "landed": landed,
            "condition_applied": applied,
            "save_stat": save.get("save_stat"),
        })

    _persist_combatants(conn, row, combatants)
    conn.commit()
    out["aoe_effect_hits"] = aoe_hits
    out["condition_applied"] = any_applied
    out["hit"] = any_applied
    out["current_mana"] = int(sheet.get("current_mana", 0))

    # Progresja rangi czaru — udane rzucenie liczy się jak użycie (jak czary effect/attack).
    try:
        spell_service.record_spell_use(int(row["character_id"]), spell_k, conn)
    except Exception:
        pass

    cid = int(row["id"])
    log_combat_turn(
        conn, combat_id=cid, campaign_id=campaign_id,
        turn_number=_next_combat_log_sequence(conn, cid),
        actor="player", event_type="spell_aoe_effect",
        roll_value=player_raw, damage=0,
        hp_after=int(enemy.get("hp_current", 0) or 0),
        target_id=target_id, target_name=str(enemy.get("name") or "") or None,
        hit=bool(any_applied),
        narrative=json.dumps({
            "spell_key": spell_k, "spell_label": label, "condition": condition_key,
            "hits": [h["target_id"] for h in aoe_hits if h["condition_applied"]],
        }, ensure_ascii=False),
    )
    conn.commit()
    out["combat_state"] = load_combat_snapshot(campaign_id)
    return out


def _apply_absorption(p: dict, dmg: int, out: dict[str, Any]) -> int:
    """B10 (#657): pula absorpcji (temp-HP tarczy) pochłania obrażenia PRZED HP.

    Wpinane w ścieżki obrażeń wroga PO uniku/bloku, PRZED `next_hp = max(0, prev-dmg)`.
    Mutuje `p["absorb_hp"]` (usuwa klucz gdy pula 0) i dopisuje `out.absorbed` /
    `out.absorb_remaining`. Zwraca obrażenia POZOSTAŁE do zadania w HP."""
    pool = int(p.get("absorb_hp", 0) or 0)
    if pool <= 0 or dmg <= 0:
        return dmg
    soaked = min(pool, dmg)
    pool -= soaked
    dmg -= soaked
    if pool > 0:
        p["absorb_hp"] = pool
    else:
        p.pop("absorb_hp", None)
    out["absorbed"] = soaked
    out["absorb_remaining"] = pool
    return dmg


def _resolve_defense_spell_in_combat(
    conn, row, campaign_id: int, ch_id: int, sheet: dict, combatants: list,
    spell_row, out: dict[str, Any], *,
    caster_comb_id: str = "player", requested_target_id: str | None = None,
    mass: bool = False,
) -> dict[str, Any]:
    """B10 (#657) + B14 (#820): czar OBRONNY (tarcza absorpcji) w aktywnej walce.

    Nakłada pulę absorpcji (temp-HP). Cel:
      • mass=True (`group_*`/`mass_*`) → wszyscy żywi przyjaźni kombatanci
      • requested_target_id = żywy sojusznik → ten WSKAZANY sojusznik
      • inaczej → rzucający (self-buff; ścieżka single-player niezmieniona)
    Reguły: odejmij PEŁNĄ manę (tarcza nie „pudłuje"); za mało → blocked;
    `absorb_hp` = wartość czaru (NIE stackuje — re-cast = świeża pula);
    ZERO obrażeń wrogowi; tury NIE zaawansowujemy. Pula combat-scoped.
    """
    from app.services import spell_service

    label = str(spell_row["label"] or spell_row["key"])
    spell_k = str(spell_row["key"])
    mana_cost = int(spell_row["mana_cost"] or 0)

    out["weapon_key"] = spell_k
    out["weapon_label"] = label
    out["weapon_type"] = "spell"
    out["attack_test"] = "spell_defense"
    out["spell_type"] = "defense"
    out["damage"] = 0  # tarcza nie zadaje obrażeń

    if mana_cost > 0:
        _mana_ok, _ = spell_service.check_and_deduct_mana(
            sheet, mana_cost, campaign_id=campaign_id,
            character_id=row["character_id"], combat_id=int(row["id"]))
        if not _mana_ok:
            out["hit"] = False
            out["blocked"] = True
            out["mana_insufficient"] = True
            out["current_mana"] = int(sheet.get("current_mana", 0))
            out["message"] = (
                f"Brak many! Potrzebujesz {mana_cost} many, "
                f"masz {int(sheet.get('current_mana', 0))}."
            )
            out["combat_state"] = _row_to_combat_dict(row)
            return out
        _save_char_sheet(conn, campaign_id, int(row["character_id"]), sheet)

    # effect_json (pula absorpcji) — osobny fetch, by detekcja nie selektowała kolumny,
    # której mogą nie mieć izolowane fikstury testowe (real schema zawsze ją ma).
    _ej_row = conn.execute(
        "SELECT effect_json FROM game_config_spells WHERE key = ? AND is_active = 1",
        (spell_k,),
    ).fetchone()
    absorb = spell_service.defense_absorb_amount(
        {"key": spell_k, "tier": int(spell_row["tier"] or 1),
         "effect_json": (_ej_row["effect_json"] if _ej_row else None)},
    )

    # ── B14: ustal cele tarczy ────────────────────────────────────────────────
    if mass:
        targets = _b14_friendly_combatants(combatants)
    else:
        rt = (
            _find_combatant(combatants, str(requested_target_id))
            if requested_target_id else None
        )
        if _b14_is_friendly(rt):
            targets = [rt]
        else:
            targets = [
                c for c in (
                    _find_combatant(combatants, caster_comb_id),
                    _find_combatant(combatants, "player"),
                ) if c
            ][:1]
    if not targets:
        raise ValueError("player combatant missing")

    cid = int(row["id"])
    shield_targets: list[dict[str, Any]] = []
    for comb in targets:
        comb["absorb_hp"] = absorb  # NIE stackuje — świeża pula = wartość czaru
        shield_targets.append({"target_id": str(comb.get("id")), "name": comb.get("name"),
                               "absorb": absorb})
        log_combat_turn(
            conn, combat_id=cid, campaign_id=campaign_id,
            turn_number=_next_combat_log_sequence(conn, cid),
            actor=str(caster_comb_id), event_type="spell_defense",
            roll_value=None, damage=0, hp_after=int(comb.get("hp_current", 0) or 0),
            target_id=str(comb.get("id")), target_name=str(comb.get("name") or "Bohater"),
            hit=True,
            narrative=json.dumps(
                {"spell_key": spell_k, "spell_label": label, "absorb": absorb,
                 "mana_cost": mana_cost, "mass": bool(mass)},
                ensure_ascii=False,
            ),
        )

    primary = targets[0]
    out["hit"] = True
    out["absorb_granted"] = absorb
    out["absorb_hp"] = absorb
    out["shield_targets"] = shield_targets
    out["target_id"] = str(primary.get("id"))
    out["mass"] = bool(mass)
    out["current_mana"] = int(sheet.get("current_mana", 0))
    if mass:
        out["message"] = (
            f"Rzucasz {label} — tarcza ({absorb}) chroni całą drużynę "
            f"({len(shield_targets)} sojuszników)."
        )
    elif str(primary.get("id") or "") != str(caster_comb_id):
        out["message"] = (
            f"Rzucasz {label} na {primary.get('name') or 'sojusznika'} — "
            f"magiczna tarcza pochłonie {absorb} obrażeń."
        )
    else:
        out["message"] = (
            f"Rzucasz {label} — magiczna tarcza pochłonie {absorb} obrażeń."
        )

    try:
        spell_service.record_spell_use(int(row["character_id"]), spell_k, conn)
    except Exception:
        pass

    _persist_combatants(conn, row, combatants)
    conn.commit()
    out["combat_state"] = load_combat_snapshot(campaign_id)
    return out


def _resolve_reaction_spell_in_combat(
    conn, row, campaign_id: int, ch_id: int, sheet: dict, combatants: list,
    spell_row, out: dict[str, Any], *, caster_comb_id: str = "player",
) -> dict[str, Any]:
    """B16 (#822): czar REAKCJI (mirror_image / blink / globe_invulnerability) w walce.

    Self-buff PREWENCYJNY: zapisuje stan na combatancie rzucającego; stan auto-odpala się
    przy następnym trafieniu wroga (``_try_spell_reaction``). Profil reakcji czytany z
    ``effect_json.reaction``. Reguły (parytet z B10): pełna mana zdjęta (reakcja nie „pudłuje"),
    za mało many → blocked; ZERO obrażeń wrogowi; tury NIE zaawansowujemy. Stan combat-scoped,
    NIE stackuje (re-cast = świeży stan).
    """
    from app.services import spell_service

    spell_k = str(spell_row["key"])
    label = str(spell_row["label"] or spell_k)
    mana_cost = int(spell_row["mana_cost"] or 0)

    out["weapon_key"] = spell_k
    out["weapon_label"] = label
    out["weapon_type"] = "spell"
    out["attack_test"] = "spell_reaction"
    out["spell_type"] = "reaction"
    out["damage"] = 0  # reakcja nie zadaje obrażeń

    # Profil reakcji z effect_json (osobny fetch — izolowane fikstury mogą nie mieć kolumny).
    _ej_row = conn.execute(
        "SELECT effect_json FROM game_config_spells WHERE key = ? AND is_active = 1",
        (spell_k,),
    ).fetchone()
    try:
        profile = json.loads(_ej_row["effect_json"]) if _ej_row and _ej_row["effect_json"] else {}
    except (TypeError, ValueError):
        profile = {}
    rtype = str(profile.get("reaction") or "").strip().lower()

    if rtype not in ("mirror_image", "blink", "globe", "globe_invulnerability"):
        # Nieznany profil reakcji — łagodne odbicie, tura nietknięta (zero pustego stanu).
        out["hit"] = False
        out["blocked"] = True
        out["block_reason"] = "unsupported_reaction"
        out["message"] = f"Czar „{label}” nie jest jeszcze wspierany w walce."
        out["combat_state"] = _row_to_combat_dict(row)
        return out

    # Mana z góry (pełny koszt; reakcja nie „pudłuje"). Darmowy czar (0) pomija kontrolę.
    if mana_cost > 0:
        _mana_ok, _ = spell_service.check_and_deduct_mana(
            sheet, mana_cost, campaign_id=campaign_id,
            character_id=row["character_id"], combat_id=int(row["id"]))
        if not _mana_ok:
            out["hit"] = False
            out["blocked"] = True
            out["mana_insufficient"] = True
            out["current_mana"] = int(sheet.get("current_mana", 0))
            out["message"] = (
                f"Brak many! Potrzebujesz {mana_cost} many, "
                f"masz {int(sheet.get('current_mana', 0))}."
            )
            out["combat_state"] = _row_to_combat_dict(row)
            return out
        _save_char_sheet(conn, campaign_id, int(row["character_id"]), sheet)

    p = _find_combatant(combatants, caster_comb_id) or _find_combatant(combatants, "player")
    if not p:
        raise ValueError("player combatant missing")

    round_n = int(row["round"] or 1)
    if rtype == "mirror_image":
        charges = max(1, int(profile.get("charges") or 3))
        p["mirror_image"] = {"charges": charges}  # NIE stackuje — świeża pula
        state = {"type": "mirror_image", "charges": charges}
        msg = (f"Rzucasz {label} — {charges} iluzorycznych kopii odciąga ciosy "
               f"(każde trafienie zużywa jedną kopię).")
    elif rtype == "blink":
        rounds = max(1, int(profile.get("rounds") or 3))
        chance = max(0, min(100, int(profile.get("miss_chance") or 50)))
        p["blink"] = {"miss_chance": chance, "until_round": round_n + rounds - 1}
        state = {"type": "blink", "miss_chance": chance, "rounds": rounds}
        msg = (f"Rzucasz {label} — migoczesz między płaszczyznami: {chance}% szansy, "
               f"że cios przejdzie przez pustkę, przez {rounds} rund.")
    else:  # globe / globe_invulnerability
        rounds = max(1, int(profile.get("rounds") or 2))
        p["globe_invulnerability"] = {"until_round": round_n + rounds - 1}
        state = {"type": "globe_invulnerability", "rounds": rounds}
        msg = f"Rzucasz {label} — kula nietykalności chroni cię przez {rounds} rund."

    cid = int(row["id"])
    log_combat_turn(
        conn, combat_id=cid, campaign_id=campaign_id,
        turn_number=_next_combat_log_sequence(conn, cid),
        actor=str(caster_comb_id), event_type="spell_reaction",
        roll_value=None, damage=0, hp_after=int(p.get("hp_current", 0) or 0),
        target_id=str(p.get("id")), target_name=str(p.get("name") or "Bohater"),
        hit=True,
        narrative=json.dumps(
            {"spell_key": spell_k, "spell_label": label, "mana_cost": mana_cost, **state},
            ensure_ascii=False,
        ),
    )

    try:
        spell_service.record_spell_use(int(row["character_id"]), spell_k, conn)
    except Exception:
        pass

    out["hit"] = True
    out["reaction_state"] = state
    out["target_id"] = str(p.get("id"))
    out["current_mana"] = int(sheet.get("current_mana", 0))
    out["message"] = msg

    _persist_combatants(conn, row, combatants)
    conn.commit()
    out["combat_state"] = load_combat_snapshot(campaign_id)
    return out


def _b14_heal_one_combatant(conn, row, campaign_id, comb, spell_stats, *,
                            caster_sheet=None, caster_chid=None):
    """B14 (#820): wylecz JEDNEGO przyjaznego combatanta. Zwraca dict z wynikiem.

    Dla rzucającego (caster_chid) reużywa już wczytany `caster_sheet` (mana zdjęta);
    dla sojusznika wczytuje jego arkusz z DB. HP combatanta jest źródłem prawdy w walce —
    synchronizujemy z nim arkusz przed leczeniem i zapisujemy zarówno combatant, jak i sheet.
    """
    from app.services import spell_service
    tid = str(comb.get("id"))
    tchid = _b14_comb_char_id(tid, row)

    if caster_chid is not None and tchid == caster_chid and caster_sheet is not None:
        tsheet = caster_sheet
    else:
        tchar = conn.execute(
            "SELECT id, sheet_json FROM characters WHERE id = ?", (tchid,),
        ).fetchone()
        tsheet = parse_character_sheet(tchar["sheet_json"]) if tchar else {}
        try:
            from app.services.campaign_state_service import overlay_sheet_from_campaign_state as _ov
            _ov(conn, campaign_id, tchid, tsheet)
        except Exception:
            pass

    # Combat HP authoritative → zsynchronizuj arkusz przed leczeniem
    tsheet["current_hp"] = int(comb.get("hp_current", tsheet.get("current_hp", 0)) or 0)
    tsheet["max_hp"] = int(
        comb.get("hp_max", tsheet.get("max_hp", tsheet.get("current_hp", 0))) or 0
    )
    hp_before = int(tsheet["current_hp"])
    res = spell_service.resolve_mend_wounds(tsheet, spell_stats)
    comb["hp_current"] = int(tsheet.get("current_hp", hp_before))
    _save_char_sheet(conn, campaign_id, tchid, tsheet)

    try:
        from app.services.state_log_service import record_state_change as _rec_state
        if int(res.get("hp_after") or hp_before) != hp_before:
            _rec_state(campaign_id=campaign_id, resource="hp", character_id=tchid,
                       combat_id=int(row["id"]), before_val=hp_before,
                       after_val=int(res.get("hp_after") or hp_before),
                       cause="heal", meta={"healed": res.get("healed")})
    except Exception:
        pass

    return {
        "target_id": tid, "name": comb.get("name"),
        "healed": res["healed"], "hp_after": res["hp_after"],
        "heal_die": res.get("heal_die"), "heal_rolls": res.get("heal_rolls"),
        "heal_modifier": res.get("heal_modifier"),
    }


def _resolve_heal_spell_in_combat(
    conn, row, campaign_id: int, ch_id: int, sheet: dict, combatants: list,
    spell_row, out: dict[str, Any], *,
    caster_comb_id: str = "player", requested_target_id: str | None = None,
    mass: bool = False,
) -> dict[str, Any]:
    """B13 (#663) + B14 (#820): czar LECZĄCY w aktywnej walce.

    Cel leczenia:
      • mass=True (`group_*`/`mass_*`) → WSZYSCY żywi przyjaźni kombatanci
      • requested_target_id = żywy sojusznik → ten WSKAZANY sojusznik
      • inaczej → rzucający (self-cast; ścieżka single-player niezmieniona)
    Procedura: odejmij PEŁNĄ manę raz; roll heal_die + INT_mod per cel (cap max_hp);
    aktualizuj sheet_json + combatant hp_current; log spell_heal per cel.
    """
    from app.services import spell_service

    spell_k = str(spell_row["key"])
    label = str(spell_row["label"] or spell_k)
    mana_cost = int(spell_row["mana_cost"] or 0)

    out["weapon_key"] = spell_k
    out["weapon_label"] = label
    out["weapon_type"] = "spell"
    out["attack_test"] = "spell_heal"
    out["spell_type"] = "heal"
    out["damage"] = 0

    if mana_cost > 0:
        _mana_ok, _ = spell_service.check_and_deduct_mana(
            sheet, mana_cost, campaign_id=campaign_id,
            character_id=row["character_id"], combat_id=int(row["id"]))
        if not _mana_ok:
            out["hit"] = False
            out["blocked"] = True
            out["mana_insufficient"] = True
            out["current_mana"] = int(sheet.get("current_mana", 0))
            out["message"] = (
                f"Brak many! Potrzebujesz {mana_cost} many, "
                f"masz {int(sheet.get('current_mana', 0))}."
            )
            out["combat_state"] = _row_to_combat_dict(row)
            return out
        _save_char_sheet(conn, campaign_id, int(row["character_id"]), sheet)

    heal_die_row = conn.execute(
        "SELECT heal_die FROM game_config_spells WHERE key = ? AND is_active = 1",
        (spell_k,),
    ).fetchone()
    spell_stats = {"heal_die": (heal_die_row["heal_die"] if heal_die_row else None) or "1d6"}

    # ── B14: ustal cele leczenia ──────────────────────────────────────────────
    caster_chid = _b14_comb_char_id(caster_comb_id, row)
    if mass:
        targets = _b14_friendly_combatants(combatants)
    else:
        rt = (
            _find_combatant(combatants, str(requested_target_id))
            if requested_target_id else None
        )
        if _b14_is_friendly(rt):
            targets = [rt]
        else:
            targets = [
                c for c in (
                    _find_combatant(combatants, caster_comb_id),
                    _find_combatant(combatants, "player"),
                ) if c
            ][:1]

    cid = int(row["id"])
    heal_targets: list[dict[str, Any]] = []
    for comb in targets:
        r = _b14_heal_one_combatant(
            conn, row, campaign_id, comb, spell_stats,
            caster_sheet=sheet, caster_chid=caster_chid,
        )
        heal_targets.append(r)
        log_combat_turn(
            conn, combat_id=cid, campaign_id=campaign_id,
            turn_number=_next_combat_log_sequence(conn, cid),
            actor=str(caster_comb_id), event_type="spell_heal",
            roll_value=None, damage=0, hp_after=int(r["hp_after"]),
            target_id=str(r["target_id"]), target_name=str(r.get("name") or "Bohater"),
            hit=True,
            narrative=json.dumps(
                {"spell_key": spell_k, "spell_label": label,
                 "healed": r["healed"], "hp_after": r["hp_after"],
                 "mana_cost": mana_cost, "mass": bool(mass)},
                ensure_ascii=False,
            ),
        )

    try:
        spell_service.record_spell_use(int(row["character_id"]), spell_k, conn)
    except Exception:
        pass

    primary = heal_targets[0] if heal_targets else {
        "healed": 0, "hp_after": 0, "target_id": None,
        "heal_die": spell_stats["heal_die"], "heal_rolls": None, "heal_modifier": None,
    }
    out["hit"] = True
    out["healed"] = primary["healed"]
    out["heal_amount"] = primary["healed"]
    out["heal_die"] = primary.get("heal_die")
    out["heal_rolls"] = primary.get("heal_rolls")
    out["heal_modifier"] = primary.get("heal_modifier")
    out["hp_after"] = primary["hp_after"]
    out["heal_targets"] = heal_targets
    out["target_id"] = primary.get("target_id")
    out["mass"] = bool(mass)
    out["current_mana"] = int(sheet.get("current_mana", 0))
    if mass:
        out["message"] = (
            f"Rzucasz {label} — leczysz całą drużynę "
            f"({len(heal_targets)} sojuszników)."
        )
    elif str(primary.get("target_id") or "") not in ("", str(caster_comb_id)):
        out["message"] = (
            f"Rzucasz {label} na {primary.get('name') or 'sojusznika'} — "
            f"leczysz {primary['healed']} HP (ma teraz {primary['hp_after']} HP)."
        )
    else:
        out["message"] = (
            f"Rzucasz {label} — leczysz {primary['healed']} HP "
            f"(masz teraz {primary['hp_after']} HP)."
        )

    _persist_combatants(conn, row, combatants)
    conn.commit()
    out["combat_state"] = load_combat_snapshot(campaign_id)
    return out


def _resolve_aoe_single_target(
    conn: Any, row: Any, campaign_id: int, ch_id: int,
    tgt: dict, enemy: dict,
    damage_die: str, int_mod: int, player_nat20: bool,
    loot_pool_accum: list[dict[str, Any]], out: dict[str, Any],
    attack_total: int = 0,
) -> dict[str, Any]:
    """Rozlicza jeden cel AoE: damage, death, loot, XP, log. Zwraca hit_info."""
    _aoe_detail = roll_dice_detailed(damage_die)
    dmg = max(0, sum(_aoe_detail["rolls"]) + int_mod) if _aoe_detail["rolls"] else max(0, int_mod)
    if player_nat20:
        dmg *= 2
    # #1160: AoE per-cel przez model obrony #826 — redukcja pancerzem + margin bonus,
    # jak każda ścieżka single-target (:5954/:7136/:7473). Wcześniej surowy dmg omijał pancerz.
    _aoe_margin = 0
    _aoe_armor = 0
    if dmg > 0:
        _dm = apply_defense_model(
            dmg, int(attack_total), int(tgt.get("defense", 0) or 0),
            ignore_armor=bool(player_nat20),
        )
        _aoe_margin = _dm["margin_bonus"]
        _aoe_armor = _dm["armor_reduction"]
        dmg = _dm["final"]
    prev_hp = int(tgt.get("hp_current", 0) or 0)
    next_hp = max(0, prev_hp - dmg)
    tgt["hp_current"] = next_hp
    dead = next_hp <= 0
    if dead:
        tgt["dead"] = True

    tgt_id = str(tgt.get("id") or "")
    tgt_name = str(tgt.get("name") or tgt.get("enemy_key") or "Wróg")
    hit_info: dict[str, Any] = {
        "target_id": tgt_id,
        "target_name": tgt_name,
        "damage": dmg,
        "hp_remaining": next_hp,
        "dead": dead,
        "gold_drop": 0,
        "loot": [],
        "margin_damage_bonus": _aoe_margin,
        "armor_reduction": _aoe_armor,
    }

    if tgt is enemy:
        out["damage"] = dmg
        out["damage_die"] = _aoe_detail["die"] or damage_die
        out["damage_rolls"] = _aoe_detail["rolls"]
        out["damage_modifier"] = int_mod
        out["target_hp_remaining"] = next_hp
        out["enemy_dead"] = dead
        if _aoe_margin:
            out["margin_damage_bonus"] = _aoe_margin
        if _aoe_armor:
            out["armor_reduction"] = _aoe_armor

    if dead:
        ek = str(tgt.get("enemy_key") or "")
        # U25 (#575): flaga boss kill (pity timer afiksów)
        if str(tgt.get("tier") or "").strip().lower() == "boss":
            try:
                conn.execute(
                    "UPDATE active_combat SET boss_defeated = 1 WHERE campaign_id = ?",
                    (campaign_id,),
                )
            except Exception:
                pass
        # Loot + złoto
        if ek and ch_id:
            try:
                from app.services.loot_service import (
                    apply_character_gold_delta, roll_gold_drop, roll_loot,
                )
                _loot_tier = str(tgt.get("loot_tier") or "") or None
                loot_items = roll_loot(ek)
                tgt_loot = (
                    _preview_loot_from_roll_items(loot_items, loot_tier=_loot_tier, conn=conn)
                    if loot_items else []
                )
                gold = int(roll_gold_drop(ek) or 0)
                if gold > 0:
                    apply_character_gold_delta(ch_id, gold, reason="combat_loot")
                hit_info["gold_drop"] = gold
                hit_info["loot"] = tgt_loot
                loot_pool_accum.extend(tgt_loot)
                # #754: strukturalny rejestr — loot + złoto
                try:
                    from app.services.dice_log_service import record_dice_roll as _rec_roll
                    _rec_roll(
                        campaign_id=campaign_id, roll_type="gold",
                        character_id=ch_id, combat_id=int(row["id"]),
                        actor=ek, total=gold, outcome="drop",
                        meta={"enemy_key": ek, "loot_tier": _loot_tier},
                    )
                    if tgt_loot:
                        _rec_roll(
                            campaign_id=campaign_id, roll_type="loot",
                            character_id=ch_id, combat_id=int(row["id"]),
                            actor=ek, total=len(tgt_loot), outcome="drop",
                            meta={"enemy_key": ek, "items": tgt_loot},
                        )
                except Exception:
                    pass
            except Exception as _loot_e:
                logger.warning("aoe_loot_error", error=str(_loot_e), enemy_key=ek)
        # XP
        try:
            from app.services import xp_service
            raw_award = int(tgt.get("xp_award") or 0)
            xpa, xp_src = xp_service.resolve_enemy_defeat_xp_amount(
                conn, catalog_xp_award=raw_award,
                tier=str(tgt.get("tier") or "") or None,
            )
            if xpa > 0 and ch_id:
                xp_service.grant_character_xp(
                    conn, ch_id, xpa, reason="enemy_defeat",
                    meta={"enemy_key": ek, "xp_source": xp_src},
                )
            hit_info["xp_granted"] = xpa
        except Exception:
            pass
        # Beat completion (#550)
        try:
            from app.services.campaign_plan_runtime import auto_complete_beats_by_event
            _beat_label = str(tgt.get("name") or tgt.get("enemy_key") or "")
            if _beat_label:
                _tn_beat = conn.execute(
                    "SELECT COALESCE(MAX(turn_number), 0) FROM campaign_turns WHERE campaign_id = ?",
                    (campaign_id,),
                ).fetchone()[0]
                auto_complete_beats_by_event(campaign_id, "kill_enemy", _beat_label, _tn_beat, conn)
                # #1011: auto-close kill quests on the same event (no [QUEST_COMPLETE] tag needed)
                from app.services.quest_persist_service import auto_complete_quests_by_event
                auto_complete_quests_by_event(conn, campaign_id, "kill_enemy", _beat_label, _tn_beat)
        except Exception:
            pass
        # Death log
        cid_d = int(row["id"])
        log_combat_turn(
            conn, combat_id=cid_d, campaign_id=campaign_id,
            turn_number=_next_combat_log_sequence(conn, cid_d),
            actor=tgt_id, event_type="death", roll_value=None,
            damage=dmg, hp_after=next_hp,
            target_id=tgt_id, target_name=tgt_name, hit=None,
            narrative=f"{tgt_name} pada — wróg nie żyje.",
        )

    return hit_info


def _resolve_aoe_spell_in_combat(
    conn: Any, row: Any, campaign_id: int, ch_id: int, sheet: dict,
    combatants: list[dict], enemy: dict, target_id: Any, spell_row: Any,
    raw_d20: int | None, out: dict[str, Any], loot_pool_accum: list[dict[str, Any]],
) -> dict[str, Any]:
    """B11 (#659): czar AoE (attack_aoe) — multi-target attack.

    1 rzut d20 vs cel główny (honoruje #595 target_id).
    Trafienie → kość damage każdemu żywemu wrogowi:
      • aoe=1 (area): wszyscy żywi wrogowie
      • aoe=0 (chain): maks 3 cele (primary + 2 kolejnych)
    Loot/XP/death log per wróg (reuse ścieżki kill z resolve_attack).
    """
    from app.services import spell_service

    spell_k = str(spell_row["key"])
    label = str(spell_row["label"] or spell_k)
    mana_cost = int(spell_row["mana_cost"] or 0)
    damage_die = str(spell_row["damage_die"] or "1d6")
    # `aoe` w osobnym fetchu (dispatch nie selektuje jej, by nie wywracać izolowanych
    # fikstur bez tej kolumny). 1=obszar (wszyscy), 0=łańcuch (maks 3).
    _aoe_r = conn.execute(
        "SELECT aoe FROM game_config_spells WHERE key = ? AND is_active = 1",
        (spell_k,),
    ).fetchone()
    is_area = bool(int((_aoe_r["aoe"] if _aoe_r else 0) or 0))

    out["weapon_key"] = spell_k
    out["weapon_label"] = label
    out["weapon_type"] = "spell"
    out["attack_test"] = "spell_attack"
    out["spell_type"] = "attack_aoe"
    out["target_id"] = target_id
    out["target_name"] = str(enemy.get("name") or "")
    out["enemy_key"] = str(enemy.get("enemy_key") or "")

    # 1. Mana check (pełna cena z góry)
    if mana_cost > 0:
        _mana_ok, _new_mana = spell_service.check_and_deduct_mana(
            sheet, mana_cost, campaign_id=campaign_id,
            character_id=row["character_id"], combat_id=int(row["id"]))
        if not _mana_ok:
            out["hit"] = False
            out["blocked"] = True
            out["mana_insufficient"] = True
            out["current_mana"] = int(sheet.get("current_mana", 0))
            out["message"] = (
                f"Brak many! Potrzebujesz {mana_cost} many, "
                f"masz {int(sheet.get('current_mana', 0))}."
            )
            out["combat_state"] = _row_to_combat_dict(row)
            return out
        out["mana_spent"] = mana_cost
        out["mana_after"] = _new_mana
        _save_char_sheet(conn, campaign_id, int(row["character_id"]), sheet)

    player_raw = int(raw_d20) if raw_d20 is not None else None
    player_nat1 = player_raw == 1
    player_nat20 = player_raw == 20
    out["player_raw_d20"] = player_raw
    out["player_nat1"] = player_nat1
    out["player_nat20"] = player_nat20

    # 2. Nat 1 → miscast (pełna mana stracona)
    if player_nat1:
        _char_race_row = conn.execute("SELECT race FROM characters WHERE id=?", (int(row["character_id"]),)).fetchone()
        _char_race = ((_char_race_row["race"] if _char_race_row else None) or "human")
        _miscast = spell_service.resolve_miscast(sheet, enemy, conn, race=_char_race)
        out["miscast"] = _miscast
        out["hp_after"] = _miscast.get("hp_after", int(sheet.get("current_hp", 0)))
        out["hit"] = False
        out["damage"] = 0
        out["aoe_hits"] = []
        _save_char_sheet(conn, campaign_id, int(row["character_id"]), sheet)
        _persist_combatants(conn, row, combatants, loot_pool=loot_pool_accum)
        conn.commit()
        cid = int(row["id"])
        log_combat_turn(
            conn, combat_id=cid, campaign_id=campaign_id,
            turn_number=_next_combat_log_sequence(conn, cid),
            actor="player", event_type="spell_aoe",
            roll_value=player_raw, damage=0,
            hp_after=int(enemy.get("hp_current", 0) or 0),
            target_id=target_id, target_name=str(enemy.get("name") or ""),
            hit=False,
            narrative=json.dumps({"spell_key": spell_k, "outcome": "miscast"}, ensure_ascii=False),
        )
        conn.commit()
        out["current_mana"] = int(sheet.get("current_mana", 0))
        out["combat_state"] = load_combat_snapshot(campaign_id)
        return out

    # 3. Attack roll vs primary target (INT-based spell, honoruje #595 target_id)
    _spell_weapon = {
        "key": spell_k, "label": label, "weapon_type": "spell",
        "damage_die": damage_die, "mana_cost": mana_cost,
        "linked_stat": "INT", "attack_bonus": 0, "damage_bonus": 0,
    }
    attack_roll = resolve_attack_roll_for_weapon(sheet, raw_roll=player_raw, weapon_row=_spell_weapon)
    attack_total = int(attack_roll["total"])
    out["attack_roll"] = attack_roll
    out["attack_total"] = attack_total

    raw_dodge = roll_d20()
    dex_mod = int(enemy.get("dex_modifier") or 0)
    dodged, hit, dodge_total = compute_player_attack_dodge_outcome(
        attack_total, raw_dodge, dex_mod, player_raw,
    )
    out["hit"] = hit
    out["dodged"] = dodged
    out["dodge_roll"] = {
        "raw": raw_dodge, "modifier": dex_mod, "total": dodge_total,
        "dodged": dodged, "player_roll": attack_total,
        "verdict": "hit" if player_nat20 else ("dodged" if dodged else "hit"),
    }

    if not hit:
        out["damage"] = 0
        out["aoe_hits"] = []
        out["target_hp_remaining"] = int(enemy.get("hp_current", 0) or 0)
        out["enemy_dead"] = False
        cid = int(row["id"])
        log_combat_turn(
            conn, combat_id=cid, campaign_id=campaign_id,
            turn_number=_next_combat_log_sequence(conn, cid),
            actor="player", event_type="spell_aoe",
            roll_value=player_raw, damage=0,
            hp_after=int(enemy.get("hp_current", 0) or 0),
            target_id=target_id, target_name=str(enemy.get("name") or ""),
            hit=False,
            narrative=json.dumps({"spell_key": spell_k, "outcome": "miss"}, ensure_ascii=False),
        )
        _persist_combatants(conn, row, combatants, loot_pool=loot_pool_accum)
        conn.commit()
        out["current_mana"] = int(sheet.get("current_mana", 0))
        out["combat_state"] = load_combat_snapshot(campaign_id)
        return out

    # 4. HIT — wyznacz cele (helper _aoe_target_ids: area=wszyscy, chain=maks 3).
    # Cel główny (#595 target_id) zawsze pierwszy → potem reszta w kolejności living.
    living_ids = [
        str(c.get("id") or "") for c in combatants
        if c.get("type") == "enemy" and int(c.get("hp_current", 0) or 0) > 0
    ]
    ordered_ids = [str(target_id)] + [i for i in living_ids if i != str(target_id)]
    chosen_ids = _aoe_target_ids(ordered_ids, aoe_flag=1 if is_area else 0)
    targets = [t for t in (_find_combatant(combatants, i) for i in chosen_ids) if t is not None]

    # 5. Rzuć damage na każdy cel (osobna kość, ten sam die, INT mod)
    int_mod = _stat_mod(sheet, "INT")
    aoe_hits: list[dict[str, Any]] = []

    for tgt in targets:
        hit_info = _resolve_aoe_single_target(
            conn, row, campaign_id, ch_id,
            tgt, enemy,
            damage_die, int_mod, player_nat20,
            loot_pool_accum, out,
            attack_total=attack_total,
        )
        aoe_hits.append(hit_info)

    primary_damage = int(out.get("damage", 0))
    _xp_total = sum(int(h.get("xp_granted") or 0) for h in aoe_hits)

    out["aoe_hits"] = aoe_hits
    out["aoe_targets"] = len(aoe_hits)
    if _xp_total > 0:
        out["xp_granted"] = _xp_total

    # Progresja rangi czaru
    try:
        spell_service.record_spell_use(int(row["character_id"]), spell_k, conn)
    except Exception:
        pass

    # Główny log zdarzenia AoE
    cid = int(row["id"])
    log_combat_turn(
        conn, combat_id=cid, campaign_id=campaign_id,
        turn_number=_next_combat_log_sequence(conn, cid),
        actor="player", event_type="spell_aoe",
        roll_value=player_raw, damage=primary_damage,
        hp_after=int(enemy.get("hp_current", 0) or 0),
        target_id=target_id, target_name=str(enemy.get("name") or ""),
        hit=True,
        narrative=json.dumps(
            {"spell_key": spell_k, "spell_label": label,
             "targets": len(aoe_hits), "nat20": player_nat20, "aoe": is_area},
            ensure_ascii=False,
        ),
    )

    # Wygrana / kontynuacja
    if _all_enemies_dead(combatants):
        _persist_combatants_and_maybe_end(
            conn, row, combatants,
            status="ended", ended_reason="victory",
            loot_pool=loot_pool_accum,
        )
        conn.commit()
        _scholar_restore_mana_after_combat(conn, ch_id, sheet, "victory", campaign_id=campaign_id)
        # Oznacz hex cleared
        try:
            gs_hex = conn.execute(
                "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
                (campaign_id,),
            ).fetchone()
            if gs_hex:
                _sf_hex = json.loads(gs_hex["session_flags"] or "{}")
                ch_hex = _sf_hex.get("current_hex")
                if ch_hex:
                    conn.execute(
                        """INSERT INTO campaign_hex_data
                           (campaign_id, hex_q, hex_r, discovered)
                           VALUES (?,?,?,1)
                           ON CONFLICT(campaign_id, hex_q, hex_r) DO UPDATE SET
                             encounter_cleared = 1, discovered = 1""",
                        (campaign_id, int(ch_hex["q"]), int(ch_hex["r"])),
                    )
                    conn.commit()
                # PT10 #1120: clear local hex encounter after victory
                local_hex = _sf_hex.get("local_hex")
                if local_hex and local_hex.get("hex_id"):
                    _cleared = _sf_hex.get("cleared_local_hexes") or []
                    _lhid = int(local_hex["hex_id"])
                    if _lhid not in _cleared:
                        _cleared.append(_lhid)
                        _sf_hex["cleared_local_hexes"] = _cleared
                        conn.execute(
                            "UPDATE game_sessions SET session_flags = ? WHERE campaign_id = ?",
                            (json.dumps(_sf_hex, ensure_ascii=False), campaign_id),
                        )
                        conn.commit()
        except Exception:
            pass
        # XS13: outnumbered XP (3+ wrogów)
        try:
            _enemy_count = sum(1 for c in combatants if c.get("type") == "enemy")
            if _enemy_count >= 3:
                from app.services.xp_sources import grant_outnumbered_victory
                _tn13 = _next_combat_log_sequence(conn, cid)
                grant_outnumbered_victory(conn, int(ch_id), int(campaign_id), _enemy_count, _tn13)
                conn.commit()
        except Exception:
            pass
        # HF-1 (#523): wyczyść scene_enemies po zwycięstwie
        try:
            set_world_state_flags(campaign_id, scene_enemies=[])
        except Exception:
            pass
        # L4: mark current dungeon tile node cleared after victory
        try:
            from app.services.dungeon_tile_service import mark_node_cleared
            mark_node_cleared(campaign_id, int(ch_id))
        except Exception:
            pass
        # L18 (#729 follow-up): dungeon-only healing sustain drop (granted server-side).
        try:
            from app.services.dungeon_tile_service import grant_dungeon_victory_sustain
            _sustain = grant_dungeon_victory_sustain(campaign_id, int(ch_id))
            if _sustain:
                out["dungeon_sustain"] = _sustain
        except Exception:
            pass
        # L8: boss tile cleared → checkpoint + loot + boss_choice_pending flag
        try:
            from app.services.dungeon_tile_service import on_boss_tile_cleared
            _boss_result = on_boss_tile_cleared(campaign_id, int(ch_id))
            if _boss_result.get("is_boss_tile"):
                out["dungeon_boss_defeated"] = True
                out["dungeon_boss_loot"] = _boss_result.get("loot", [])
        except Exception:
            pass
    else:
        _persist_combatants(conn, row, combatants, loot_pool=loot_pool_accum)
        conn.commit()

    out["current_mana"] = int(sheet.get("current_mana", 0))
    out["combat_state"] = load_combat_snapshot(campaign_id)
    return out


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
                    _save_char_sheet(conn, campaign_id, int(character_id), sheet)
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

    # #761: rejestr zdjęcia kondycji gracza
    if removed > 0:
        try:
            from app.services.state_log_service import record_state_change
            record_state_change(
                campaign_id=campaign_id, resource="condition", character_id=character_id,
                before_val=condition_key, after_val=None, cause="condition_expire",
                meta={"removed_count": removed},
            )
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
                    _save_char_sheet(conn, campaign_id, int(character_id), sheet)
                    added += 1
    except Exception:
        pass

    # #761: rejestr nałożenia kondycji na gracza
    if added > 0:
        try:
            from app.services.state_log_service import record_state_change
            record_state_change(
                campaign_id=campaign_id, resource="condition", character_id=character_id,
                before_val=None, after_val=condition_key, cause="condition_apply",
                meta={"added_count": added},
            )
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
    # #640 — narracja walki krótka i dynamiczna. Reguła scoped: powstaje TYLKO podczas
    # aktywnej walki, więc nadpisuje globalny styl 4-6 zdań wyłącznie tu. Mechaniki nie rusza.
    lines.append(
        "NARRACJA WALKI (NADPISUJE styl 4-6 zdań dopóki trwa walka): opisz tę akcję w "
        "MAKSYMALNIE 2-3 krótkich, dynamicznych zdaniach. Bez rozwlekłych opisów otoczenia, "
        "bez dygresji, bez powtarzania znanych faktów — tylko sama akcja i jej skutek."
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
    ch_id = int(row["character_id"])
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
    if reason == "victory":
        try:
            combatants = json.loads(row["combatants"] or "[]")
        except Exception:
            combatants = []
        dead_enemies = [c for c in combatants if c.get("type") == "enemy"]
        write_game_event(
            "combat_victory",
            camp,
            ch_id,
            None,
            {
                "enemies_killed": len(dead_enemies),
                "enemy_keys": [c.get("enemy_key", "") for c in dead_enemies],
                "rounds": int(row["round"] or 1),
                "xp_awarded": 0,
            },
            conn=conn,
        )
    elif reason == "fled":
        write_game_event(
            "combat_fled",
            camp,
            ch_id,
            None,
            {"round": int(row["round"] or 1)},
            conn=conn,
        )


# ---------------------------------------------------------------------------
# R3.1 (#879): evaluate_current_turn_conditions — per-effect-type helpers
# ---------------------------------------------------------------------------


def _tick_periodic_save(
    condition: dict,
    effect: dict,
    effect_idx: int,
    actor: dict,
    sheet: "dict[str, Any] | None",
    marker: str,
    key: str,
    label: str,
) -> "tuple[bool, list[dict[str, Any]], bool, bool]":
    """Returns (remove_condition, new_events, runtime_changed, conditions_changed)."""
    tick = str(effect.get("tick") or "").strip().lower()
    if tick not in {"start_turn", "each_round"}:
        return False, [], False, False
    state = _condition_effect_state(condition, effect_idx)
    if str(state.get("last_turn_marker") or "") == marker:
        return False, [], False, False
    state["last_turn_marker"] = marker

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

    new_events: list[dict[str, Any]] = [
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
    ]

    remove_condition = False
    expires = str(effect.get("expires") or "").strip().lower()
    duration_rounds = _condition_duration_rounds(expires)
    if duration_rounds is not None:
        remaining = state.get("remaining_rounds")
        if not isinstance(remaining, int) or remaining < 1:
            remaining = duration_rounds
        remaining -= 1
        state["remaining_rounds"] = remaining
        if remaining <= 0:
            remove_condition = True

    if success and expires == "save_success":
        remove_condition = True

    if remove_condition:
        new_events.append(
            {
                "type": "condition_removed",
                "condition_key": key,
                "condition_label": label,
                "reason": "save_success" if success and expires == "save_success" else "duration_expired",
            }
        )

    return remove_condition, new_events, True, remove_condition


def _tick_duration_countdown(
    condition: dict,
    marker: str,
    key: str,
    label: str,
) -> "tuple[bool, list[dict[str, Any]], bool, bool]":
    """Returns (remove_condition, new_events, runtime_changed, conditions_changed)."""
    dur = condition.get("duration_rounds")
    if not isinstance(dur, int) or dur <= 0:
        return False, [], False, False
    leg_state = _condition_effect_state(condition, "duration_tick")
    if str(leg_state.get("last_turn_marker") or "") == marker:
        return False, [], False, False
    leg_state["last_turn_marker"] = marker
    condition["duration_rounds"] = dur - 1
    remove_condition = condition["duration_rounds"] <= 0
    new_events: list[dict[str, Any]] = []
    if remove_condition:
        new_events.append(
            {
                "type": "condition_removed",
                "condition_key": key,
                "condition_label": label,
            }
        )
    return remove_condition, new_events, True, remove_condition


def _tick_block_action(key: str, label: str) -> "tuple[bool, list[dict[str, Any]]]":
    """Returns (blocked, new_events)."""
    return True, [{"type": "block_action", "condition_key": key, "condition_label": label}]


def _tick_skip_turn(
    effect: dict,
    key: str,
    label: str,
) -> "tuple[bool, list[dict[str, Any]]]":
    """Returns (blocked, new_events)."""
    try:
        chance = float(effect.get("chance", 1.0))
    except (TypeError, ValueError):
        chance = 1.0
    if chance >= 1.0 or random.random() < chance:
        return True, [
            {
                "type": "block_action",
                "condition_key": key,
                "condition_label": label,
                "via": "skip_turn",
            }
        ]
    return False, []


def _tick_stacking_levels(
    condition: dict,
    effect: dict,
    actor: dict,
    key: str,
    label: str,
) -> "tuple[bool, list[dict[str, Any]]]":
    """Returns (blocked, new_events)."""
    level = _condition_level(condition)
    thresholds = effect.get("threshold_effects")
    if not isinstance(thresholds, dict):
        return False, []
    blocked = False
    new_events: list[dict[str, Any]] = []
    for thr_key, thr_eff in thresholds.items():
        try:
            thr = int(thr_key)
        except (TypeError, ValueError):
            continue
        if level < thr or not isinstance(thr_eff, dict):
            continue
        if str(thr_eff.get("type") or "").strip().lower() == "block_action":
            blocked = True
            new_events.append(
                {"type": "block_action", "condition_key": key, "condition_label": label}
            )
    return blocked, new_events


def _tick_dot(
    condition: dict,
    effect: dict,
    effect_idx: int,
    actor: dict,
    marker: str,
    key: str,
    label: str,
) -> "tuple[list[dict[str, Any]], bool, bool]":
    """Returns (new_events, conditions_changed, runtime_changed). Mutates actor hp_current."""
    tick = str(effect.get("tick") or "start_turn").strip().lower()
    if tick not in {"start_turn", "each_round"}:
        return [], False, False
    dstate = _condition_effect_state(condition, f"dot_{effect_idx}")
    if str(dstate.get("last_turn_marker") or "") == marker:
        return [], False, False
    dstate["last_turn_marker"] = marker
    raw_val = effect.get("value")
    dmg = int(raw_val) if isinstance(raw_val, (int, float)) else roll_damage_dice(str(raw_val or "1d4"))
    if dmg <= 0:
        return [], False, True
    prev_hp = int(actor.get("hp_current", 0) or 0)
    actor["hp_current"] = max(0, prev_hp - dmg)
    return (
        [
            {
                "type": "condition_damage",
                "condition_key": key,
                "condition_label": label,
                "damage": dmg,
                "damage_type": str(effect.get("damage_type") or "physical"),
                "hp_after": int(actor.get("hp_current", 0)),
            }
        ],
        True,
        True,
    )


def _tick_escalating_dot(
    condition: dict,
    effect: dict,
    effect_idx: int,
    actor: dict,
    marker: str,
    key: str,
    label: str,
) -> "tuple[list[dict[str, Any]], bool, bool]":
    """Returns (new_events, conditions_changed, runtime_changed). Mutates actor hp_current."""
    tick = str(effect.get("tick") or "start_turn").strip().lower()
    if tick not in {"start_turn", "each_round"}:
        return [], False, False
    estate = _condition_effect_state(condition, f"edot_{effect_idx}")
    if str(estate.get("last_turn_marker") or "") == marker:
        return [], False, False
    estate["last_turn_marker"] = marker
    ticks_done = int(estate.get("ticks", 0) or 0)
    dmg = _escalating_dot_damage(effect, ticks_done)
    estate["ticks"] = ticks_done + 1
    if dmg <= 0:
        return [], False, True
    prev_hp = int(actor.get("hp_current", 0) or 0)
    actor["hp_current"] = max(0, prev_hp - dmg)
    return (
        [
            {
                "type": "condition_damage",
                "condition_key": key,
                "condition_label": label,
                "damage": dmg,
                "damage_type": str(effect.get("damage_type") or "physical"),
                "hp_after": int(actor.get("hp_current", 0)),
            }
        ],
        True,
        True,
    )


def _tick_legacy(
    condition: dict,
    actor: dict,
    marker: str,
    key: str,
    label: str,
) -> "tuple[bool, list[dict[str, Any]], bool, bool]":
    """Returns (blocked, new_events, conditions_changed, runtime_changed). Mutates actor hp_current."""
    legacy = _decode_effect_json(condition.get("effect_json"))
    if not isinstance(legacy, dict):
        return False, [], False, False
    leg_state = _condition_effect_state(condition, "legacy_tick")
    if str(leg_state.get("last_turn_marker") or "") == marker:
        return False, [], False, False
    leg_state["last_turn_marker"] = marker

    new_events: list[dict[str, Any]] = []
    blocked = False
    conditions_changed = False

    if legacy.get("skip_turn"):
        blocked = True
        new_events.append(
            {"type": "block_action", "condition_key": key, "condition_label": label}
        )

    dpt = legacy.get("damage_per_turn")
    if dpt and isinstance(dpt, (int, float)) and dpt > 0:
        dmg = int(dpt)
        prev_hp = int(actor.get("hp_current", 0) or 0)
        actor["hp_current"] = max(0, prev_hp - dmg)
        dtype = str(legacy.get("damage_type") or "physical")
        new_events.append(
            {
                "type": "condition_damage",
                "condition_key": key,
                "condition_label": label,
                "damage": dmg,
                "damage_type": dtype,
                "hp_after": int(actor.get("hp_current", 0)),
            }
        )
        conditions_changed = True

    return blocked, new_events, conditions_changed, True


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
                else:
                    from app.services.campaign_state_service import overlay_sheet_from_campaign_state as _ov_etc
                    _ov_etc(conn, campaign_id, int(row["character_id"]), sheet)

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
                rm, evts, rt, cc = _tick_periodic_save(
                    condition, effect, effect_idx, actor, sheet, marker, key, label
                )
                events.extend(evts)
                runtime_changed = runtime_changed or rt
                conditions_changed = conditions_changed or cc
                if rm:
                    remove_condition = True
                    break

            # Duration countdown (for conditions applied via weapon effect_json)
            rm, evts, rt, cc = _tick_duration_countdown(condition, marker, key, label)
            events.extend(evts)
            runtime_changed = runtime_changed or rt
            conditions_changed = conditions_changed or cc
            if rm:
                remove_condition = True

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
                if effect_type == "block_action":
                    blk, evts = _tick_block_action(key, label)
                    blocked = blocked or blk
                    events.extend(evts)
                elif effect_type == "skip_turn":
                    # #621: strukturalny skip_turn (slowed/stunned). Honoruj `chance`
                    # (domyślnie 1.0 = zawsze pomija, jak stunned); slowed=0.5 losuje co turę.
                    # Czas trwania ogarnia osobny mechanizm wygasania kondycji — nie duplikuj.
                    blk, evts = _tick_skip_turn(effect, key, label)
                    blocked = blocked or blk
                    events.extend(evts)

            # S9 (#604): stacking_levels — progi (threshold_effects) odpalają się,
            # gdy runtime poziom kondycji ≥ próg (np. exhausted poziom 2 → omdlenie).
            for effect in effects:
                if str(effect.get("type") or "").strip().lower() != "stacking_levels":
                    continue
                blk, evts = _tick_stacking_levels(condition, effect, actor, key, label)
                blocked = blocked or blk
                events.extend(evts)

            # S8 (#603): `dot` — damage-over-time po kości (np. on_fire 2d6/turę).
            # Schema-zgodny prymityw; tyka raz na turę aktora (dedup po markerze).
            for effect_idx, effect in enumerate(effects):
                if str(effect.get("type") or "").strip().lower() != "dot":
                    continue
                evts, cc, rt = _tick_dot(condition, effect, effect_idx, actor, marker, key, label)
                events.extend(evts)
                conditions_changed = conditions_changed or cc
                runtime_changed = runtime_changed or rt

            # S10 (#605): `escalating_dot` — DOT narastający w czasie (hemorrhage 1d4/turę,
            # +1d4 co 3 tury). Licznik tyknięć w effect_state przeżywa między rundami.
            for effect_idx, effect in enumerate(effects):
                if str(effect.get("type") or "").strip().lower() != "escalating_dot":
                    continue
                evts, cc, rt = _tick_escalating_dot(
                    condition, effect, effect_idx, actor, marker, key, label
                )
                events.extend(evts)
                conditions_changed = conditions_changed or cc
                runtime_changed = runtime_changed or rt

            # Legacy condition format: skip_turn and damage_per_turn
            # (game_config_conditions uses {"skip_turn":true,"damage_per_turn":N,...})
            if not effects:
                blk, evts, cc, rt = _tick_legacy(condition, actor, marker, key, label)
                blocked = blocked or blk
                events.extend(evts)
                conditions_changed = conditions_changed or cc
                runtime_changed = runtime_changed or rt

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
            _save_char_sheet(conn, campaign_id, int(row["character_id"]), sheet)

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


def initiate_combat(
    campaign_id: int,
    character_id: int,
    enemy_keys: list[str],
    _dungeon_enemy_overrides: "dict[str, dict] | None" = None,
    _dungeon_first_combat: bool = False,
) -> dict[str, Any]:
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
        from app.services.campaign_state_service import overlay_sheet_from_campaign_state as _ov_sc
        _ov_sc(conn, campaign_id, int(character_id), sheet)
        hp_cur, hp_max = _player_hp_pair(sheet)
        ac = _player_ac_from_sheet(sheet)
        # #1302: passive bonuses from ALL equipped items (armour/relic/amulet/off-hand)
        # — AC + stats work in combat exactly like out of combat. Main-hand weapon is
        # EXCLUDED here because it's applied separately below (avoid double-count).
        # Applied to AC, the seven ability stats, and DEX-driven initiative.
        try:
            from app.services.equipment_effects_service import get_equipment_bonuses as _get_equip_bonuses
            _relic = _get_equip_bonuses(int(character_id), conn, exclude_slots=("main_hand",))
        except Exception:
            _relic = {"stats": {}, "skills": {}, "ac": 0}
        _relic_ac = int(_relic.get("ac") or 0)
        if _relic_ac:
            ac += _relic_ac
        _relic_stats = _relic.get("stats") or {}
        dex_mod = (int(_ability_stats_seven(sheet).get("DEX", 10) or 10)
                   + int(_relic_stats.get("DEX", 0) or 0) - 10) // 2
        # PT-D1 (#1124): od 2 stacków zmęczenia gorsza inicjatywa.
        from app.services.fatigue_service import compute_initiative_penalty
        init_player = roll_d20() + dex_mod + compute_initiative_penalty(_sheet_conditions(sheet), race=sheet.get("race"))
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
        # #1302: relic static_stat_modifier — equipped relic-slot items raise stats in combat.
        if _relic_stats:
            for _st, _delta in _relic_stats.items():
                if _st in ability_stats:
                    ability_stats[_st] = int(ability_stats.get(_st, 10) or 10) + int(_delta or 0)

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
            # L5: apply dungeon tier stat overrides when provided (absolute D1–D5 scaling)
            _ov = (_dungeon_enemy_overrides or {}).get(ek) if _dungeon_enemy_overrides else None
            hp_max_e = int((_ov.get("hp_base") if _ov else None) or er["hp_base"] or 1)
            ac_e = int((_ov.get("ac_base") if _ov else None) or er["ac_base"] or 10)
            _atk_override = _ov.get("attack_bonus") if _ov else None
            _atk = int(_atk_override if _atk_override is not None else (er["attack_bonus"] or 0))
            # L18 (#729): honor tier-softened boss damage die from the override (else
            # boss burst — e.g. lich 2d8 — stays full power regardless of dungeon tier).
            _die_override = (_ov.get("damage_die") if _ov else None)
            _dmg_dice = str(_die_override or er["damage_die"] or "1d6").strip().lower()
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
                    "attack_bonus": _atk,
                    "dex_modifier": int(er["dex_modifier"] or 0),
                    "damage_dice": _dmg_dice,
                    "damage_stat": "STR",
                    # #864: ożyw martwe pole — wróg z attacks_per_turn>1 atakuje N razy/turę
                    # (pętla w resolve_enemy_followup_attacks). Default 1 = zero regresji.
                    "attacks_per_turn": int(
                        (er["attacks_per_turn"] if "attacks_per_turn" in er.keys() else 1) or 1
                    ),
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
                    # L20b (#724): portrait URL for player-facing modal + initiative chip thumbnail.
                    "image_url": er["image_url"] if "image_url" in er.keys() else None,
                }
            )
            turn_slots.append((slug, init_e, idx))

        # Sort: highest initiative first; ties: player wins (lower tie-break value sorts first after negating init)
        turn_slots.sort(key=lambda t: (-t[1], 0 if t[0] == "player" else 1))
        # LB2: first combat of the dungeon run — hero always acts first (soft-init)
        if _dungeon_first_combat:
            player_idx = next((i for i, t in enumerate(turn_slots) if t[0] == "player"), 0)
            if player_idx > 0:
                turn_slots.insert(0, turn_slots.pop(player_idx))
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
    write_game_event(
        "combat_start",
        int(campaign_id),
        int(character_id),
        None,
        {"enemy_keys": started_keys, "enemy_count": len(started_keys)},
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


# ── B14 (#820) — Ally-target support spells (heal/shield + mass_*/group_*) ─────

def _b14_is_friendly(comb: dict | None) -> bool:
    """True jeśli combatant jest przyjaznym slotem gracza ('player' lub 'player:N')."""
    if not comb:
        return False
    cid = str(comb.get("id") or "")
    return cid == "player" or cid.startswith("player:")


def _b14_friendly_combatants(combatants: list[dict]) -> list[dict]:
    """Wszyscy żywi przyjaźni kombatanci (cel `mass_*`/`group_*`)."""
    return [
        c for c in combatants
        if _b14_is_friendly(c) and int(c.get("hp_current", 0) or 0) > 0
    ]


def _b14_comb_char_id(comb_id: str, row: Any) -> int:
    """character_id dla przyjaznego combatanta: 'player:N'→N, 'player'→row.character_id."""
    chid = _mp_player_char_id(str(comb_id))
    return chid if chid is not None else int(row["character_id"])


def _b14_is_mass_spell(spell_k: str) -> bool:
    """Wariant grupowy rozpoznawany po prefiksie klucza (`mass_`/`group_`) — bez migracji."""
    k = str(spell_k or "").strip().lower()
    return k.startswith("mass_") or k.startswith("group_")


# ── B15 (#821) — Summony jako kombatant-towarzysz ─────────────────────────────
# Decyzja projektowa (#821): auto-atak najbliższego wroga; 1 aktywny summon
# (nowy zastępuje starego); czas życia = lifetime_rounds z effect_json (default 3)
# + znika po śmierci; gdy gracz pada → summon znika; shadow_clone = stały profil.
# Wszystkie liczby = wartości STARTOWE (Numbers Policy), strojone w Sandboxie.

_B15_DEFAULT_LIFETIME = 3
_B15_DEFAULT_HP = 8
_B15_DEFAULT_ATTACK_BONUS = 2
_B15_DEFAULT_DAMAGE_DIE = "1d6"
_B15_SUMMON_ID = "summon:1"  # limit 1 aktywny → stały id


def _b15_is_summon(comb: dict | None) -> bool:
    """True jeśli combatant jest przywołanym towarzyszem (type=='summon')."""
    return bool(comb) and str((comb or {}).get("type") or "") == "summon"


def _b15_summon_combatants(combatants: list[dict]) -> list[dict]:
    """Wszystkie summony w walce (żywe i martwe — do sprzątania)."""
    return [c for c in combatants if _b15_is_summon(c)]


def _b15_parse_summon_profile(spell_row: Any) -> dict[str, Any]:
    """Profil towarzysza z `effect_json` czaru (z fallbackami startowymi)."""
    prof: dict[str, Any] = {}
    raw = None
    try:
        if "effect_json" in spell_row.keys():
            raw = spell_row["effect_json"]
    except Exception:
        raw = None
    if raw:
        try:
            prof = json.loads(raw) or {}
        except Exception:
            prof = {}
    _ab = prof.get("attack_bonus")
    return {
        "hp": int(prof.get("hp") or _B15_DEFAULT_HP),
        "attack_bonus": int(_ab if _ab is not None else _B15_DEFAULT_ATTACK_BONUS),
        "damage_die": str(prof.get("damage_die") or _B15_DEFAULT_DAMAGE_DIE),
        "lifetime_rounds": int(prof.get("lifetime_rounds") or _B15_DEFAULT_LIFETIME),
        "zone": str(prof.get("zone") or ZONE_ENGAGED),
        "name": str(prof.get("name") or "").strip(),
    }


def _b15_persist_with_turn_order(
    conn: sqlite3.Connection, row: sqlite3.Row,
    combatants: list[dict], turn_order: list[str],
) -> None:
    """B15: zapis combatants ORAZ turn_order — summon dołącza/odłącza się w trakcie walki
    (zwykły `_persist_combatants` nie rusza turn_order, więc tu osobny helper)."""
    conn.execute(
        """
        UPDATE active_combat
        SET combatants = ?, turn_order = ?, updated_at = ?
        WHERE campaign_id = ?
        """,
        (
            json.dumps(combatants, ensure_ascii=False),
            json.dumps(turn_order, ensure_ascii=False),
            _now_iso(),
            row["campaign_id"],
        ),
    )


def _b15_pick_summon_target(combatants: list[dict], summon: dict) -> dict | None:
    """Cel auto-ataku summona: najbliższy żywy WRÓG (preferuj tę samą strefę)."""
    enemies = [
        c for c in combatants
        if c.get("type") == "enemy" and int(c.get("hp_current", 0) or 0) > 0
    ]
    if not enemies:
        return None
    s_zone = str(summon.get("zone") or ZONE_ENGAGED)
    same_zone = [c for c in enemies if str(c.get("zone") or ZONE_ENGAGED) == s_zone]
    return (same_zone or enemies)[0]


def _resolve_summon_spell_in_combat(
    conn, row, campaign_id: int, ch_id: int, sheet: dict, combatants: list,
    spell_row, out: dict[str, Any], *, caster_comb_id: str = "player",
) -> dict[str, Any]:
    """B15 (#821): czar PRZYWOŁANIA w aktywnej walce.

    Odejmuje manę, czyta profil z `effect_json`, usuwa poprzedni summon (limit 1),
    wstawia nowego kombatanta `type=='summon'` do combatants I do turn_order zaraz za
    rzucającym, persystuje oba pola. Tura summona (auto-atak) → :func:`resolve_summon_turn`.
    """
    from app.services import spell_service

    spell_k = str(spell_row["key"])
    label = str(spell_row["label"] or spell_k)
    mana_cost = int(spell_row["mana_cost"] or 0)

    out["weapon_key"] = spell_k
    out["weapon_label"] = label
    out["weapon_type"] = "spell"
    out["attack_test"] = "spell_summon"
    out["spell_type"] = "summon"
    out["damage"] = 0

    if mana_cost > 0:
        _mana_ok, _ = spell_service.check_and_deduct_mana(
            sheet, mana_cost, campaign_id=campaign_id,
            character_id=row["character_id"], combat_id=int(row["id"]))
        if not _mana_ok:
            out["hit"] = False
            out["blocked"] = True
            out["mana_insufficient"] = True
            out["current_mana"] = int(sheet.get("current_mana", 0))
            out["message"] = (
                f"Brak many! Potrzebujesz {mana_cost} many, "
                f"masz {int(sheet.get('current_mana', 0))}."
            )
            out["combat_state"] = _row_to_combat_dict(row)
            return out
        _save_char_sheet(conn, campaign_id, int(row["character_id"]), sheet)

    prof = _b15_parse_summon_profile(spell_row)
    order: list[str] = json.loads(row["turn_order"] or "[]")

    # Limit 1 aktywny — usuń poprzednie summony z combatants I turn_order.
    old_ids = {str(c.get("id")) for c in _b15_summon_combatants(combatants)}
    if old_ids:
        combatants[:] = [c for c in combatants if str(c.get("id")) not in old_ids]
        order = [t for t in order if str(t) not in old_ids]

    summon_name = prof["name"] or label
    summon = {
        "id": _B15_SUMMON_ID,
        "type": "summon",
        "owner_id": str(caster_comb_id),
        "summon_key": spell_k,
        "name": summon_name,
        "hp_current": prof["hp"],
        "hp_max": prof["hp"],
        "defense": 10,
        "attack_bonus": prof["attack_bonus"],
        "damage_dice": prof["damage_die"],
        "damage_stat": "STR",
        "lifetime_remaining": prof["lifetime_rounds"],
        "conditions": [],
        "zone": prof["zone"],
        "stats": {"STR": 10, "DEX": 10, "CON": 10, "INT": 10, "WIS": 10, "CHA": 10},
    }
    combatants.append(summon)

    # Wstaw do kolejki zaraz za rzucającym (zadziała szybko, idealnie w tej rundzie).
    order_str = [str(t) for t in order]
    if str(caster_comb_id) in order_str:
        order.insert(order_str.index(str(caster_comb_id)) + 1, _B15_SUMMON_ID)
    else:
        order.append(_B15_SUMMON_ID)

    _b15_persist_with_turn_order(conn, row, combatants, order)

    cid = int(row["id"])
    log_combat_turn(
        conn, combat_id=cid, campaign_id=campaign_id,
        turn_number=_next_combat_log_sequence(conn, cid),
        actor=str(caster_comb_id), event_type="summon",
        roll_value=None, damage=0, hp_after=prof["hp"],
        target_id=_B15_SUMMON_ID, target_name=summon_name, hit=True,
        narrative=json.dumps(
            {"spell_key": spell_k, "spell_label": label, "summon_id": _B15_SUMMON_ID,
             "hp": prof["hp"], "lifetime_rounds": prof["lifetime_rounds"],
             "mana_cost": mana_cost}, ensure_ascii=False,
        ),
    )
    try:
        spell_service.record_spell_use(int(row["character_id"]), spell_k, conn)
    except Exception:
        pass
    conn.commit()

    out["hit"] = True
    out["summon"] = {
        "id": _B15_SUMMON_ID, "name": summon_name, "hp": prof["hp"],
        "lifetime_rounds": prof["lifetime_rounds"], "zone": prof["zone"],
    }
    out["current_mana"] = int(sheet.get("current_mana", 0))
    out["message"] = (
        f"Przywołujesz {summon_name} ({prof['hp']} HP) — staje u twego boku "
        f"na {prof['lifetime_rounds']} rund."
    )
    out["combat_state"] = load_combat_snapshot(campaign_id)
    return out


def resolve_summon_turn(campaign_id: int) -> dict[str, Any]:
    """B15 (#821) — tura summona: auto-atak najbliższego żywego wroga.

    Czas życia: ``lifetime_remaining`` spada o 1 po akcji; gdy wchodzi z 0 → summon znika.
    Gdy gracz nie żyje → summon znika (``owner_down``). Brak wrogów → tura jałowa, ale
    licznik życia i tak spada. Wzorzec ataku skopiowany z forced-behavior AI wroga."""
    out: dict[str, Any] = {"actor": "summon"}
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM active_combat WHERE campaign_id = ? AND status = 'active'",
            (campaign_id,),
        ).fetchone()
        if not row:
            raise ValueError("no active combat")
        combatants: list[dict] = json.loads(row["combatants"] or "[]")
        order: list[str] = json.loads(row["turn_order"] or "[]")
        cur = str(row["current_turn"])
        summon = _find_combatant(combatants, cur)
        if not _b15_is_summon(summon):
            raise ValueError("current turn is not a summon")
        out["summon_id"] = cur
        out["summon_name"] = str(summon.get("name") or "Towarzysz")

        def _vanish(reason: str) -> dict[str, Any]:
            new_combatants = [c for c in combatants if str(c.get("id")) != cur]
            new_order = [t for t in order if str(t) != cur]
            _b15_persist_with_turn_order(conn, row, new_combatants, new_order)
            conn.commit()
            out["hit"] = False
            out["damage"] = 0
            out["vanished"] = True
            out["vanish_reason"] = reason
            out["combat_state"] = load_combat_snapshot(campaign_id)
            return out

        # Gracz padł → summon znika (decyzja #821).
        if _find_active_player_combatant(combatants) is None:
            return _vanish("owner_down")
        # Czas życia wygasł → summon znika bez akcji.
        if int(summon.get("lifetime_remaining", 0) or 0) <= 0:
            return _vanish("expired")

        _ensure_zones(combatants)
        target = _b15_pick_summon_target(combatants, summon)
        if target is None:
            # Brak żywych wrogów — tura jałowa; licznik i tak spada.
            summon["lifetime_remaining"] = int(summon.get("lifetime_remaining", 0) or 0) - 1
            out["hit"] = False
            out["damage"] = 0
            out["no_target"] = True
            out["lifetime_remaining"] = summon["lifetime_remaining"]
            _persist_combatants(conn, row, combatants)
            conn.commit()
            out["combat_state"] = load_combat_snapshot(campaign_id)
            return out

        raw_b = roll_d20()
        atk_b = int(summon.get("attack_bonus") or 0)
        attack_roll_b = raw_b + atk_b
        tgt_ac = int(target.get("defense", 10) or 10)
        hit_b = raw_b == 20 or (raw_b != 1 and attack_roll_b >= tgt_ac)
        dmg_b = 0
        if hit_b:
            dmg_b = roll_damage_dice((summon.get("damage_dice") or "1d6").strip().lower(), 0)
            target["hp_current"] = max(0, int(target.get("hp_current", 0) or 0) - dmg_b)

        # Czas życia spada PO akcji (lifetime_rounds rund = tyle ataków).
        summon["lifetime_remaining"] = int(summon.get("lifetime_remaining", 0) or 0) - 1

        out["hit"] = bool(hit_b)
        out["damage"] = int(dmg_b)
        out["attack_roll"] = int(attack_roll_b)
        out["raw_d20"] = int(raw_b)
        out["target_id"] = str(target.get("id"))
        out["target_name"] = str(target.get("name") or target.get("id"))
        out["target_hp_remaining"] = int(target.get("hp_current", 0) or 0)
        out["target_incapacitated"] = int(target.get("hp_current", 0) or 0) <= 0
        out["lifetime_remaining"] = summon["lifetime_remaining"]

        cid = int(row["id"])
        log_combat_turn(
            conn, combat_id=cid, campaign_id=campaign_id,
            turn_number=_next_combat_log_sequence(conn, cid),
            actor="summon", event_type="summon_attack",
            roll_value=int(attack_roll_b), damage=int(dmg_b),
            hp_after=int(target.get("hp_current", 0) or 0),
            target_id=str(target.get("id")), target_name=out["target_name"], hit=bool(hit_b),
            narrative=json.dumps(
                {"summon_id": cur, "summon_name": out["summon_name"],
                 "attack_roll": int(attack_roll_b), "raw_d20": int(raw_b),
                 "damage": int(dmg_b), "hit": bool(hit_b)}, ensure_ascii=False,
            ),
        )
        _persist_combatants(conn, row, combatants)
        conn.commit()
        out["combat_state"] = load_combat_snapshot(campaign_id)
        return out


# ── G17 (#794) — Knockdown helpers ───────────────────────────────────────────

def _find_active_player_combatant(combatants: list[dict]) -> dict | None:
    """G17: first non-knocked, hp>0 player combatant ('player' or 'player:N')."""
    for c in combatants:
        cid = str(c.get("id") or "")
        if cid != "player" and not cid.startswith("player:"):
            continue
        if int(c.get("hp_current", 0) or 0) <= 0:
            continue
        if c.get("knocked"):
            continue
        return c
    return None


def _all_players_knocked(combatants: list[dict]) -> bool:
    """G17: True when every player combatant has hp<=0 (knocked or dead)."""
    players = [
        c for c in combatants
        if str(c.get("id") or "") == "player" or str(c.get("id") or "").startswith("player:")
    ]
    return bool(players) and all(int(c.get("hp_current", 0) or 0) <= 0 for c in players)


def _is_mp_combat(combatants: list[dict]) -> bool:
    """G17: True if this is MP combat (players use 'player:N' ids)."""
    return any(
        str(c.get("id") or "").startswith("player:") and c.get("type") == "player"
        for c in combatants
    )


# ── G7 (#791) — Multiplayer combat helpers ────────────────────────────────────

def _mp_player_char_id(actor_id: str) -> int | None:
    """Extract character_id from 'player:N' format. Returns None for plain 'player'."""
    if not isinstance(actor_id, str) or not actor_id.startswith("player:"):
        return None
    try:
        return int(actor_id.split(":", 1)[1])
    except (ValueError, IndexError):
        return None


def initiate_combat_mp(
    campaign_id: int,
    character_ids: list[int],
    enemy_keys: list[str],
) -> dict[str, Any]:
    """G7 (#791) — Start MP combat with all players in turn_order as 'player:{character_id}'.

    Each player gets a separate combatant slot with their own HP/stats from sheet.
    active_combat.character_id stores character_ids[0] for schema compatibility.
    """
    if not character_ids:
        raise ValueError("character_ids required for MP combat")
    if not enemy_keys:
        raise ValueError("enemy_keys required")

    with _conn() as conn:
        camp = conn.execute("SELECT id FROM campaigns WHERE id = ?", (campaign_id,)).fetchone()
        if not camp:
            raise ValueError("campaign not found")

        combatants: list[dict[str, Any]] = []
        turn_slots: list[tuple[str, int, int]] = []

        # Build player combatants
        for idx, ch_id in enumerate(character_ids):
            ch = conn.execute(
                "SELECT id, name, sheet_json FROM characters WHERE id = ?",
                (ch_id,),
            ).fetchone()
            if not ch:
                logger.warning("mp_combat_character_missing", character_id=ch_id)
                continue

            sheet = parse_character_sheet(ch["sheet_json"])
            from app.services.campaign_state_service import overlay_sheet_from_campaign_state as _ov_sc
            _ov_sc(conn, campaign_id, int(ch_id), sheet)

            hp_cur, hp_max = _player_hp_pair(sheet)
            ac = _player_ac_from_sheet(sheet)
            dex_mod = _stat_mod(sheet, "DEX")
            # PT-D1 (#1124): od 2 stacków zmęczenia gorsza inicjatywa.
            from app.services.fatigue_service import compute_initiative_penalty
            init_roll = roll_d20() + dex_mod + compute_initiative_penalty(_sheet_conditions(sheet), race=sheet.get("race"))
            ability_stats = _ability_stats_seven(sheet)

            # Apply weapon AC bonus (same as solo)
            _wrow = resolve_sheet_weapon(conn, sheet, int(ch_id))
            _wac = _weapon_ac_bonus(_wrow)
            if _wac:
                ac += _wac
            _aac = _inventory_affix_ac_bonus(conn, int(ch_id))
            if _aac:
                ac += _aac

            actor_id = f"player:{ch_id}"
            combatants.append({
                "id": actor_id,
                "type": "player",
                "name": (ch["name"] or "Hero").strip(),
                "hp_current": hp_cur,
                "hp_max": hp_max,
                "defense": ac,
                "stats": ability_stats,
                "initiative_roll": init_roll,
                "conditions": _sheet_conditions(sheet),
                "zone": _default_zone_for_player(sheet),
            })
            # Tie-break: lower list index wins (first player in list wins ties)
            turn_slots.append((actor_id, init_roll, idx))

        if not combatants:
            raise ValueError("no valid characters for MP combat")

        primary_ch_id = character_ids[0]

        # Build enemy combatants (same logic as initiate_combat)
        resolved_enemies: list[tuple[str, sqlite3.Row]] = []
        for ek in enemy_keys:
            er = _fetch_enemy_row(conn, ek)
            if not er:
                er = _create_pending_combat_enemy(conn, ek)
                if not er:
                    continue
            resolved_enemies.append((ek, er))

        if not resolved_enemies:
            raise ValueError("no valid enemy keys after filtering")

        e_idx = 0
        for ek, er in resolved_enemies:
            e_idx += 1
            slug = _enemy_slug(ek, e_idx)
            hp_max_e = int(er["hp_base"] or 1)
            ac_e = int(er["ac_base"] or 10)
            atk = int(er["attack_bonus"] or 0)
            dmg_dice = str(er["damage_die"] or "1d6").strip().lower()
            dex_e_mod = int(er["dex_modifier"] or 0)
            init_e = roll_d20() + dex_e_mod
            xp_e = int(er["xp_award"] or 0) if "xp_award" in er.keys() else 0
            combatants.append({
                "id": slug,
                "type": "enemy",
                "enemy_key": er["key"],
                "name": (er["label"] or er["key"]).strip(),
                "hp_current": hp_max_e,
                "hp_max": hp_max_e,
                "defense": ac_e,
                "attack_bonus": atk,
                "dex_modifier": dex_e_mod,
                "damage_dice": dmg_dice,
                "damage_stat": "STR",
                "attacks_per_turn": int((er["attacks_per_turn"] if "attacks_per_turn" in er.keys() else 1) or 1),
                "initiative_roll": init_e,
                "conditions": [],
                "loot_table_key": er["loot_table_key"],
                "drop_chance": float(er["drop_chance"] if er["drop_chance"] is not None else 1.0),
                "xp_award": xp_e,
                "tier": str(er["tier"] or "standard"),
                "loot_tier": er["loot_tier"] if "loot_tier" in er.keys() else None,
                "zone": _default_zone_for_enemy(er["key"], er["label"]),
                "skills": _parse_enemy_skills(er["skills_json"]),
                "stats": parse_stats_json(er["stats_json"] if "stats_json" in er.keys() else None),
                "image_url": er["image_url"] if "image_url" in er.keys() else None,
            })
            turn_slots.append((slug, init_e, 1000 + e_idx))

        # Sort by initiative DESC; among equal, players before enemies
        turn_slots.sort(key=lambda t: (-t[1], t[2]))
        turn_order = [t[0] for t in turn_slots]
        current = turn_order[0] if turn_order else f"player:{primary_ch_id}"

        conn.execute("DELETE FROM active_combat WHERE campaign_id = ?", (campaign_id,))
        _save_combat_row(
            conn,
            campaign_id,
            character_id=primary_ch_id,
            round_n=1,
            turn_order=turn_order,
            current_turn=current,
            combatants=combatants,
            status="active",
        )
        conn.commit()

        id_row = conn.execute("SELECT id FROM active_combat WHERE campaign_id = ?", (campaign_id,)).fetchone()
        if id_row:
            combat_id_int = int(id_row["id"])
            log_combat_turn(conn, combat_id=combat_id_int, campaign_id=campaign_id,
                            turn_number=0.0, actor="system", event_type="start",
                            narrative=f"Walka MP rozpoczęta. Gracze: {len(combatants) - len(resolved_enemies)}, "
                                      f"wrogowie: {', '.join(k for k, _ in resolved_enemies)}")
            for actor_id, init_total, _tie in turn_slots:
                tn = _next_combat_log_sequence(conn, combat_id_int)
                log_combat_turn(conn, combat_id=combat_id_int, campaign_id=campaign_id,
                                turn_number=tn, actor=str(actor_id), event_type="initiative",
                                roll_value=int(init_total),
                                narrative=f"Inicjatywa MP: {actor_id} → {int(init_total)}")
        conn.commit()

    out = get_active_combat(campaign_id)
    if not out:
        raise RuntimeError("failed to load MP combat after insert")

    logger.info("mp_combat_start", campaign_id=campaign_id,
                players=character_ids, enemies=[k for k, _ in resolved_enemies])
    return out


def apply_mp_default_defense(campaign_id: int, character_id: int) -> dict[str, Any]:
    """G7 (#791) — Timeout action: player defends in place, turn advances.

    Hero stays in initiative order and can still take damage from enemies on their turn.
    This prevents the anti-exploit 'go AFK to avoid dying'.
    """
    actor_id = f"player:{character_id}"
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM active_combat WHERE campaign_id = ? AND status = 'active'",
            (campaign_id,),
        ).fetchone()
        if not row:
            raise ValueError("no active combat")
        if str(row["current_turn"]) != actor_id:
            raise ValueError(f"not {actor_id}'s turn (current: {row['current_turn']})")

        combatants: list[dict] = json.loads(row["combatants"] or "[]")
        p = _find_combatant(combatants, actor_id)
        if not p:
            raise ValueError(f"combatant {actor_id} not found")

        combat_id_int = int(row["id"])
        tn = _next_combat_log_sequence(conn, combat_id_int)
        log_combat_turn(
            conn,
            combat_id=combat_id_int,
            campaign_id=campaign_id,
            turn_number=tn,
            actor=actor_id,
            event_type="defense",
            hp_after=int(p.get("hp_current", 0) or 0),
            target_id=actor_id,
            target_name=str(p.get("name") or "Bohater"),
            hit=False,
            narrative=json.dumps({"action": "default_defense", "reason": "timeout"}, ensure_ascii=False),
        )
        conn.commit()

    advance_turn(campaign_id)
    return {"ok": True, "actor": actor_id, "combat_state": get_active_combat(campaign_id)}


def _living_enemy_ids(combatants: list[dict]) -> list[str]:
    out = []
    for c in combatants:
        if c.get("type") != "enemy":
            continue
        if int(c.get("hp_current", 0) or 0) > 0:
            out.append(str(c["id"]))
    return out


def _select_player_target(
    combatants: list[dict],
    order: list[str],
    living: list[str],
    p_zone: str,
    is_melee: bool,
    requested_target_id: str | None = None,
) -> tuple[str | None, str | None]:
    """#595: wybór celu ataku gracza w walce z wieloma wrogami.

    Zwraca ``(target_id, block_reason)``. ``block_reason='out_of_range'`` gdy melee nie
    sięga żadnego dopuszczalnego celu (cel w innej strefie). Honoruje ``requested_target_id``
    gdy to ŻYWY wróg w bieżącej walce; nieprawidłowy/martwy cel → fallback do starego
    auto-wyboru (pierwszy żywy w turn_order). Melee dalej bramkowane strefą; dystans/czar
    celuje dowolną strefę.
    """
    chosen = (
        str(requested_target_id)
        if requested_target_id is not None and str(requested_target_id) in living
        else None
    )
    if is_melee:
        if chosen:
            c = _find_combatant(combatants, chosen)
            if c and str(c.get("zone") or ZONE_ENGAGED) == p_zone:
                return chosen, None
            return None, "out_of_range"
        for tid in order:
            if tid not in living:
                continue
            c = _find_combatant(combatants, tid)
            if c and str(c.get("zone") or ZONE_ENGAGED) == p_zone:
                return tid, None
        return None, "out_of_range"
    # Dystans / czar — dowolna strefa.
    if chosen:
        return chosen, None
    for tid in order:
        if tid in living:
            return tid, None
    return (living[0] if living else None), None


def _all_enemies_dead(combatants: list[dict]) -> bool:
    for c in combatants:
        if c.get("type") != "enemy":
            continue
        if int(c.get("hp_current", 0) or 0) > 0:
            return False
    return True


# B11 (#659): łańcuchowe AoE (chain_lightning) skacze przez do 3 wrogów; obszar (aoe=1)
# trafia wszystkich. Wartość startowa limitu łańcucha = 3 (Numbers Policy — tuning po B13).
_AOE_CHAIN_MAX_TARGETS = 3


def _aoe_target_ids(living: list[str], *, aoe_flag: int) -> list[str]:
    """B11 (#659): które żywe cele obejmuje czar AoE.

    ``aoe_flag=1`` (obszar — burning_arc/fireball) → wszyscy żywi wrogowie.
    ``aoe_flag=0`` (łańcuch — chain_lightning „skacze przez do 3") → maks
    ``_AOE_CHAIN_MAX_TARGETS`` celów w kolejności ``living`` (turn_order)."""
    if int(aoe_flag or 0) == 1:
        return list(living)
    return list(living)[:_AOE_CHAIN_MAX_TARGETS]


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


# ─── #826: Spójny model obrony — jeden rzut obronny + pancerz=redukcja + margines→dmg ───
# Wszystkie wartości STARTOWE (Numbers Policy #826) — do strojenia na Sandboxie. Symetria
# gracz↔wróg: ten sam silnik obrażeń po trafieniu w obie strony.
MARGIN_DAMAGE_STEP = 5        # co ile pełnych pkt ataku ponad obronę → bonus obrażeń (PRIMARY)
MARGIN_DAMAGE_BONUS = 1       # +1 dmg za próg (BACKUP w #826: +1 KOŚĆ — gdy +1 dmg za słabe na Sandboxie)
ARMOR_REDUCTION_OFFSET = 10   # pancerz = max(0, ac_base − OFFSET); 10 = część `ac_base`/AC ponad
                              # nieopancerzony próg (AC 10). OFFSET=0 → literalne ac_base ze spec #826
                              # (zeruje słabe ciosy → ratuje min 1 dmg). Strój na Sandboxie.


def _armor_value(defense_stat: int) -> int:
    """#826 pkt.2: pancerz jako liczba redukcji obrażeń (część `ac_base`/AC ponad nieopancerzony próg)."""
    return max(0, int(defense_stat or 0) - ARMOR_REDUCTION_OFFSET)


def _margin_damage_bonus(attack_total: int, defense_stat: int) -> int:
    """#826 pkt.3: +MARGIN_DAMAGE_BONUS za każde pełne MARGIN_DAMAGE_STEP pkt ataku ponad obronę.
    Margines liczony względem STAŁEJ obrony celu (deterministyczny, strojny), nie rzutu uniku."""
    margin = int(attack_total or 0) - int(defense_stat or 0)
    if margin < MARGIN_DAMAGE_STEP:
        return 0
    return (margin // MARGIN_DAMAGE_STEP) * MARGIN_DAMAGE_BONUS


# #972 R3: Twardy jak kamień — damage types reduced for dwarves (STARTING value, tunable).
DWARF_TOUGHNESS_TYPES = {"poison", "dark", "rdzen"}
DWARF_TOUGHNESS_REDUCTION = 2


def apply_defense_model(
    base_damage: int,
    attack_total: int,
    defense_stat: int,
    *,
    ignore_armor: bool,
    race: str = "human",
    damage_type: str = "physical",
) -> dict[str, int]:
    """#826: JEDEN punkt wejścia obrażeń PO TRAFIENIU (symetria gracz↔wróg).

    1) margines→dmg: +bonus za każde MARGIN_DAMAGE_STEP pkt ataku ponad obronę,
    2) pancerz→redukcja: −armor, ale **min 1 dmg na trafienie**; Nat 20 (`ignore_armor`) pomija pancerz.
    3) #972 Twardy jak kamień: krasnolud −2 dmg od trucizny/mroku/Rdzenia (min 1).

    Zwraca {final, margin_bonus, armor_reduction}. Nat 20 ×2 liczone OSOBNO (po stronie wywołującej)."""
    base = int(base_damage or 0)
    if base <= 0:
        return {"final": 0, "margin_bonus": 0, "armor_reduction": 0}
    bonus = _margin_damage_bonus(attack_total, defense_stat)
    pre_armor = base + bonus
    if ignore_armor:
        raw_final = pre_armor
    else:
        armor = _armor_value(defense_stat)
        raw_final = max(1, pre_armor - armor)
    # Twardy jak kamień: racial DR for dwarf on qualifying damage types
    toughness_reduction = 0
    if str(race or "human").strip().lower() == "dwarf" and str(damage_type or "physical").strip().lower() in DWARF_TOUGHNESS_TYPES:
        toughness_reduction = DWARF_TOUGHNESS_REDUCTION
        raw_final = max(1, raw_final - toughness_reduction)
    if ignore_armor:
        return {"final": raw_final, "margin_bonus": bonus, "armor_reduction": 0, "toughness_reduction": toughness_reduction}
    return {"final": raw_final, "margin_bonus": bonus, "armor_reduction": pre_armor - raw_final - toughness_reduction, "toughness_reduction": toughness_reduction}


def compute_enemy_attack_hit(
    attack_roll: int,
    raw_d20: int,
    player_evasion_total: int,
) -> bool:
    """#826: enemy→player to-hit = POJEDYNCZY test (symetria z player→enemy, koniec double jeopardy).

    AC NIE jest już progiem trafienia (przeszło na redukcję obrażeń). Nat 1 = auto-pudło,
    Nat 20 = auto-trafienie; inaczej trafienie gdy ``attack_roll > evasion`` (obrońca wygrywa remis)."""
    if int(raw_d20) == 1:
        return False
    if int(raw_d20) == 20:
        return True
    return int(attack_roll) > int(player_evasion_total)


def _enemy_attack_narrative_dict(
    out: dict,
    raw: int,
    attack_roll: int,
    pac: int,
    enemy: dict,
    atk_b: int = 0,
) -> dict:
    """#828: narrative JSON dla log_combat_turn (atak wroga na gracza).

    Zawiera player_evasion gdy pasywny unik był użyty (brak okna reakcji), None gdy
    gracze mieli otwarte okno reakcji. Frontend używa tego do pokazania 'vs Unik' zamiast 'vs AC'.
    """
    d: dict = {
        "raw_d20": int(raw),
        "attack_bonus": int(atk_b),
        "attack_roll": int(attack_roll),
        "target_ac": int(pac),
        "enemy_name": str(enemy.get("name") or enemy.get("enemy_key") or "Wróg"),
        "player_evasion": out.get("player_evasion") or None,
        # #861: parowanie (#598) — gracz z cięższą main + drugą bronią w off odbija cios
        # (+N obrona → redukcja obrażeń). UI rysuje badge „Parujesz +N" z tej flagi.
        "parry_bonus": int(out.get("parry_bonus") or 0),
    }
    return d


def _player_attack_narrative_dict(
    attack_roll: dict,
    player_raw: int | None,
    roll_result: int | None,
    weapon_row: dict | None,
    offhand: bool = False,
) -> dict:
    """#861: narrative JSON dla log_combat_turn (atak gracza na wroga).

    `offhand=True` oznacza drugi cios off-hand (#598 dual-wield) — UI rysuje go jako
    osobną kartę „drugi cios", a nie powtórzony atak główny.
    """
    return {
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
        "offhand": bool(offhand),
    }


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


def _reaction_options(conn: Any, ch_id: int, p: dict, sheet: dict, round_n: int) -> list[str]:
    """SF10 (#633) — które reakcje są DOSTĘPNE dla gracza w tej chwili (model reaktywny).

    Zwraca listę opcji do okna reakcji: ``dodge`` (skill dodge ≥ 1), ``shield_block``
    (skill shield_block ≥ 1 + tarcza założona). Pusta lista = brak okna (obrażenia
    naliczane od razu). Respektuje 1 reakcję/rundę (``reaction_used_round``) i lockout
    po krytycznej porażce uniku (``reaction_locked_round``)."""
    if int(p.get("reaction_used_round") or 0) == int(round_n):
        return []
    if int(p.get("reaction_locked_round") or 0) == int(round_n):
        return []
    skills = sheet.get("skills") or {}
    opts: list[str] = []
    try:
        if int(skills.get("dodge", 0) or 0) >= 1:
            opts.append("dodge")
    except (TypeError, ValueError):
        pass
    try:
        if int(skills.get("shield_block", 0) or 0) >= 1:
            has_shield, _ = _player_has_shield_equipped(conn, ch_id)
            if has_shield:
                opts.append("shield_block")
    except (TypeError, ValueError):
        pass
    return opts


def _record_ammo_spent(conn, campaign_id: int, ammo_key: str, n: int = 1) -> None:
    """#765: accumulate ammo fired this combat on active_combat.ammo_spent_json.

    Idempotent against schema drift — silently no-ops if the column is absent
    (e.g. isolated test DBs without the migration).
    """
    if not ammo_key or n <= 0:
        return
    try:
        row = conn.execute(
            "SELECT ammo_spent_json FROM active_combat WHERE campaign_id = ? AND status = 'active'",
            (int(campaign_id),),
        ).fetchone()
    except sqlite3.OperationalError:
        return
    if not row:
        return
    try:
        spent = json.loads(row["ammo_spent_json"] or "{}")
        if not isinstance(spent, dict):
            spent = {}
    except (TypeError, ValueError):
        spent = {}
    spent[ammo_key] = int(spent.get(ammo_key, 0) or 0) + int(n)
    conn.execute(
        "UPDATE active_combat SET ammo_spent_json = ? WHERE campaign_id = ? AND status = 'active'",
        (json.dumps(spent), int(campaign_id)),
    )
    conn.commit()


def _read_ammo_spent_row(conn, campaign_id: int):
    """Latest combat row for the campaign carrying an ammo-spent ledger (or None)."""
    try:
        return conn.execute(
            "SELECT id, character_id, ammo_spent_json FROM active_combat "
            "WHERE campaign_id = ? ORDER BY id DESC LIMIT 1",
            (int(campaign_id),),
        ).fetchone()
    except sqlite3.OperationalError:
        return None


def get_ammo_spent(campaign_id: int) -> dict[str, Any]:
    """#765: ile sztuk amunicji wystrzelono w (ostatniej) walce — dla pilla szansy odzysku."""
    from app.services import ammo_service as _ammo
    with _conn() as conn:
        row = _read_ammo_spent_row(conn, campaign_id)
        spent: dict[str, int] = {}
        if row and row["ammo_spent_json"]:
            try:
                raw = json.loads(row["ammo_spent_json"] or "{}")
                if isinstance(raw, dict):
                    spent = {str(k): int(v or 0) for k, v in raw.items() if int(v or 0) > 0}
            except (TypeError, ValueError):
                spent = {}
    return {
        "fired": spent,
        "total": sum(spent.values()),
        "chance": _ammo.DEFAULT_RECOVER_CHANCE,
        "can_recover": bool(spent),
    }


def recover_combat_ammo(
    campaign_id: int,
    chance: float | None = None,
    rng=None,
) -> dict[str, Any]:
    """#765: odzyskaj część wystrzelonej amunicji (rzut per sztuka, 40% startowo).

    Po odzysku kasuje rejestr, by ponowne wywołanie nie dublowało zwrotu.
    """
    from app.services import ammo_service as _ammo
    c = _ammo.DEFAULT_RECOVER_CHANCE if chance is None else float(chance)
    with _conn() as conn:
        row = _read_ammo_spent_row(conn, campaign_id)
        if not row or not row["ammo_spent_json"]:
            return {"recovered": {}, "total": 0, "chance": c, "fired": {}}
        try:
            spent = json.loads(row["ammo_spent_json"] or "{}")
            if not isinstance(spent, dict):
                spent = {}
        except (TypeError, ValueError):
            spent = {}
        ch_id = int(row["character_id"])
        recovered: dict[str, int] = {}
        for ammo_key, fired in spent.items():
            got = _ammo.recover_ammo(conn, ch_id, str(ammo_key), int(fired or 0), chance=c, rng=rng)
            if got:
                recovered[str(ammo_key)] = got
        conn.execute("UPDATE active_combat SET ammo_spent_json = NULL WHERE id = ?", (row["id"],))
        conn.commit()
    return {
        "recovered": recovered,
        "total": sum(recovered.values()),
        "chance": c,
        "fired": {str(k): int(v or 0) for k, v in spent.items()},
    }


def _attack_target_select(
    combatants: list[dict],
    _player_comb_id: str,
    spell_key: str | None,
    sheet: dict,
    conn,
    ch_id: int,
    row,
    target_id: str | None,
    out: dict,
) -> tuple[str | None, dict | None, dict | None]:
    """Zone gating + target selection for player attack path.

    Returns (target_id, enemy, early_return).
    If early_return is not None the caller must return it immediately.
    """
    living = _living_enemy_ids(combatants)
    if not living:
        out["message"] = "no living enemies"
        out["combat_state"] = _row_to_combat_dict(row)
        return None, None, out

    # ── Zone gating: prefer same-zone targets for melee, any-zone for ranged ──
    _ensure_zones(combatants)
    p_zone = str((_find_combatant(combatants, _player_comb_id) or {}).get("zone") or ZONE_ENGAGED)
    _resolved_weapon_for_zone = (
        "spell" if spell_key else (
            "spell" if str(sheet.get("archetype") or "").strip().lower() == "scholar"
            else str((resolve_sheet_weapon(conn, sheet, ch_id) or {}).get("weapon_type") or "melee").lower()
        )
    )
    _melee = _resolved_weapon_for_zone == "melee"

    order = json.loads(row["turn_order"] or "[]")
    target_id, _block_reason = _select_player_target(
        combatants, order, living, p_zone, _melee, requested_target_id=target_id,
    )
    if _block_reason == "out_of_range":
        out["hit"] = False
        out["blocked"] = True
        out["block_reason"] = "out_of_range"
        out["message"] = "Cele są poza zasięgiem walki wręcz. Zbliż się lub użyj broni dystansowej."
        out["combat_state"] = _row_to_combat_dict(row)
        return None, None, out

    enemy = _find_combatant(combatants, target_id)
    if not enemy:
        raise ValueError("enemy combatant missing")

    return target_id, enemy, None


def _attack_resolve_defense(
    attack_roll: int,
    raw: int,
    pac: int,
    conn,
    ch_id: int,
    p: dict,
    sheet: dict,
    row,
    enemy: dict,
    out: dict,
) -> bool:
    """Hit determination for enemy attack path.

    Uses compute_enemy_attack_hit or reaction-window shortcut.
    Mutates out (hit, attack_roll, raw_d20, enemy_name, target_ac).
    Returns hit bool.
    """
    _round_now826 = int(row["round"] or 1)
    if _reaction_options(conn, ch_id, p, sheet, _round_now826):
        hit = raw != 1  # tylko Nat 1 wroga pudłuje; resztę rozstrzyga okno reakcji
        out["target_evasion"] = None
    else:
        _player_dex_mod = _stat_mod(sheet, "DEX")
        _ev_raw = roll_d20()
        _ev_total = int(_ev_raw) + int(_player_dex_mod)
        hit = compute_enemy_attack_hit(attack_roll, raw, _ev_total)
        out["player_evasion"] = {"raw": int(_ev_raw), "dex_mod": int(_player_dex_mod),
                                 "total": _ev_total}
    out["hit"] = hit
    out["attack_roll"] = attack_roll
    out["raw_d20"] = raw
    out["enemy_name"] = str(enemy.get("name") or enemy.get("enemy_key") or "Wróg").strip()
    out["target_ac"] = pac
    return hit


def _attack_try_reaction(
    p: dict,
    row,
    out: dict,
    conn,
    ch_id: int,
    sheet: dict,
    attack_roll: int,
    raw: int,
    enemy: dict,
    combatants: list[dict],
    campaign_id: int,
    dmg: int,
) -> tuple[int, dict | None, dict | None, dict | None]:
    """B16 spell-reaction + reaction window + S15/S16 dodge/block for enemy attack path.

    Returns (dmg_after, _dodge, _block, early_return).
    If early_return is not None the caller must return it immediately.
    """
    _b16 = _try_spell_reaction(p, int(row["round"] or 1), out)
    _b16_negated = bool(_b16 and _b16.get("negated"))
    if _b16_negated:
        dmg = 0
    # SF10 (#633): MODEL REAKTYWNY. Gdy gracz ma dostępną reakcję (skill/tarcza,
    # niezużytą w rundzie), NIE naliczamy obrażeń — otwieramy OKNO REAKCJI: zapisujemy
    # `pending_reaction` na combatancie i PAUZUJEMY (frontend pokaże modal Przyjmij/
    # Unik/Blok). Rozliczenie w `resolve_reaction`. Rzut ataku wroga już rozstrzygnięty
    # (nat 20/nat 1 nietknięte). Brak opcji → spada niżej do natychmiastowego naliczenia.
    _round_now = int(row["round"] or 1)
    _opts = _reaction_options(conn, ch_id, p, sheet, _round_now)
    if _opts and not p.get("pending_reaction") and not _b16_negated:
        p["pending_reaction"] = {
            "damage": int(dmg),
            "attack_roll": int(attack_roll),
            "round": _round_now,
            "options": _opts,
            "nat20": bool(raw == 20),  # #826: Nat 20 pomija pancerz przy rozliczeniu reakcji
            "enemy_name": str(enemy.get("name") or enemy.get("enemy_key") or "Wróg"),
        }
        cid = int(row["id"])
        tn = _next_combat_log_sequence(conn, cid)
        log_combat_turn(
            conn, combat_id=cid, campaign_id=campaign_id, turn_number=tn,
            actor="enemy", event_type="attack", roll_value=int(attack_roll),
            damage=0, hp_after=int(p.get("hp_current", 0) or 0),
            target_id="player", target_name=str(p.get("name") or "Gracz"),
            hit=True,
            narrative=json.dumps({
                "raw_d20": int(raw), "attack_roll": int(attack_roll),
                "target_ac": int(out.get("target_ac") or 0), "reaction_window": True, "options": _opts,
                "enemy_name": str(enemy.get("name") or enemy.get("enemy_key") or "Wróg"),
            }, ensure_ascii=False),
        )
        _persist_combatants(conn, row, combatants)
        conn.commit()
        out["hit"] = True
        out["reaction_window"] = True
        out["reaction_options"] = _opts
        out["enemy_name"] = str(enemy.get("name") or enemy.get("enemy_key") or "Wróg")
        out["combat_state"] = load_combat_snapshot(campaign_id)
        return dmg, None, None, out
    # S15 (#610): okno reakcji — unik PRZED aplikacją obrażeń. Rzut ataku wroga już
    # rozliczony (nat 20/nat 1 nietknięte); reakcja działa tylko na obrażenia po trafieniu.
    # B16: pominięte gdy czar-reakcja już znegował cios (jedna reakcja/rundę).
    _dodge: dict | None = None
    _block: dict | None = None
    if not _b16_negated:
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
    return dmg, _dodge, _block, None


def _attack_compute_damage(
    weapon_row,
    sheet: dict,
    enemy: dict,
    combatants: list[dict],
    player_comb_id: str,
    player_nat20: bool,
    player_raw,
    _surprise_fx: dict,
    roll_result: int,
    conn,
    ch_id: int,
    campaign_id: int,
    row,
    card_key: str,
    out: dict,
) -> int:
    """Crit ×2, surprise ×2, gear flat bonus, S14 conditions, armor reduction, dice log.

    Mutates out (damage_die, damage_rolls, damage_stat, damage_modifier, damage_multiplier,
    damage_bonus, ambush_bonus, sneak_attack, margin_damage_bonus, armor_reduction, damage).
    Returns final dmg after defense model.
    """
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
            (out.get("attack_roll") or {}).get("damage_stat")
            or wrow.get("linked_stat")
            or "STR"
        ).upper()
    mod = _stat_mod(sheet, stat)
    # #661: roll detailed so the response carries the individual die
    # results (damage_rolls) for the frontend NdX damage animation.
    _dmg_detail = roll_dice_detailed(die)
    dmg = max(0, sum(_dmg_detail["rolls"]) + mod) if _dmg_detail["rolls"] else max(0, mod)
    out["damage_die"] = _dmg_detail["die"] or die
    out["damage_rolls"] = _dmg_detail["rolls"]
    out["damage_stat"] = stat
    out["damage_modifier"] = mod
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
    _pc_for_dmg = _find_combatant(combatants, player_comb_id)
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
        # burst (#780): unifikacja — sneak die / zasadzka palą się gdy gracz
        # `hidden` LUB gdy cel `zaskoczony` (otwarcie ze skradania, bez hidden).
        _fire_burst = _should_fire_burst(enemy, player_hidden=bool(_hidden))
        if _hidden:
            _ambush = _roll_ambush_bonus(_hidden)
            if _ambush:
                dmg += _ambush
                out["ambush_bonus"] = _ambush
        # B4 (#645) + D3 (#780): łotrzyk — sneak attack PONAD ambush, oddzielny
        # add PO mnożniku (jak ambush/gear — NIE podwajany na cricie/nat20).
        # Cecha klasy: rzut tylko dla rogue (inni → 0). Pali się też przy
        # otwarciu ze skradania (cel zaskoczony), nie tylko gdy gracz hidden.
        if _fire_burst:
            _sneak = _sneak_attack_bonus(sheet)
            if _sneak:
                dmg += _sneak
                out["sneak_attack"] = _sneak
        if _hidden:
            _remove_combatant_conditions(_pc_for_dmg, _hidden)
    # #826: margines→dmg + pancerz=redukcja (po wszystkich bonusach, przed HP).
    # Obrona celu = `ac_base` wroga (już nie próg trafienia — to liczy unik d20+DEX).
    # Nat 20 pomija pancerz (×2 obrażeń policzone wyżej, osobno).
    if dmg > 0:
        _dm826 = apply_defense_model(
            dmg, roll_result, int(enemy.get("defense", 0) or 0),
            ignore_armor=bool(player_nat20),
        )
        if _dm826["margin_bonus"]:
            out["margin_damage_bonus"] = _dm826["margin_bonus"]
        if _dm826["armor_reduction"]:
            out["armor_reduction"] = _dm826["armor_reduction"]
        dmg = _dm826["final"]
    out["damage"] = dmg
    # #754: strukturalny rejestr — obrażenia gracza (per-kość)
    try:
        from app.services.dice_log_service import record_dice_roll as _rec_roll
        _rec_roll(
            campaign_id=campaign_id,
            roll_type="damage",
            character_id=ch_id,
            combat_id=int(row["id"]),
            actor="player",
            notation=str(out.get("damage_die") or die),
            raw_rolls=_dmg_detail.get("rolls") or [],
            modifiers={"stat_mod": mod, "stat": stat,
                       "multiplier": out.get("damage_multiplier", 1),
                       "flat_bonus": out.get("damage_bonus", 0)},
            total=dmg,
            outcome="crit_success" if player_nat20 else "hit",
            meta={"weapon_key": out.get("weapon_key"), "enemy_key": card_key,
                  "round": int(row["round"] or 1),
                  "armor_reduction": out.get("armor_reduction", 0),
                  "nat20_ignored_armor": bool(player_nat20),
                  "margin_damage": out.get("margin_damage_bonus", 0)},
        )
    except Exception:
        pass
    return dmg


def _attack_apply_effects(
    weapon_row,
    sheet: dict,
    enemy: dict,
    combatants: list[dict],
    player_comb_id: str,
    player_raw,
    _surprise_fx: dict,
    conn,
    ch_id: int,
    out: dict,
    dmg: int,
) -> int:
    """Apply computed damage to enemy HP, heal_on_hit, clear consumed conditions, weapon effects.

    Mutates enemy (hp_current, conditions) and out (target_hp_remaining, heal_on_hit,
    consumed_conditions, weapon_effect_narrative, weapon_conditions_applied, damage).
    Returns dmg (may increase from extra_damage weapon effects).
    """
    wrow = weapon_row
    prev_hp = int(enemy.get("hp_current", 0) or 0)
    next_hp = max(0, prev_hp - dmg)
    enemy["hp_current"] = next_hp
    out["target_hp_remaining"] = next_hp
    # F1 (#461) + F2 (#495): heal_on_hit from weapon effect_json and affixes
    _heal = _weapon_heal_on_hit(wrow) + _inventory_affix_heal_on_hit(conn, ch_id)
    if _heal:
        _pc = _find_combatant(combatants, player_comb_id)
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
    return dmg


def _attack_spell_secondary(
    is_spell: bool,
    player_nat20: bool,
    player_nat1: bool,
    hit: bool,
    enemy: dict,
    dmg: int,
    out: dict[str, Any],
    sheet: dict,
    conn,
    campaign_id: int,
    row,
) -> None:
    """R2.3 (#878): Nat20 secondary effects + Nat1 miscast for spell attacks."""
    if is_spell and player_nat20 and hit:
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
    if is_spell and player_nat1:
        from app.services.spell_service import resolve_miscast
        _char_race_row = conn.execute("SELECT race FROM characters WHERE id=?", (int(row["character_id"]),)).fetchone()
        _char_race = ((_char_race_row["race"] if _char_race_row else None) or "human")
        _miscast = resolve_miscast(sheet, enemy, conn, race=_char_race)
        out["miscast"] = _miscast
        out["hp_after"] = _miscast.get("hp_after", int(sheet.get("current_hp", 0)))
        _save_char_sheet(conn, campaign_id, int(row["character_id"]), sheet)


def _resolve_player_attack_turn(
    conn,
    row,
    campaign_id: int,
    combatants: list,
    loot_pool_accum: list,
    ch_id: int,
    sheet: dict,
    attacker: str,
    roll_result,
    raw_d20,
    spell_key,
    target_id,
    weapon_override,
    out: dict,
    _mp_ch_id,
    _player_comb_id: str,
    _b14_req_target,
) -> dict:
    """R2.3 (#878): player attack path extracted from resolve_attack."""
    target_id, enemy, _tgt_early = _attack_target_select(
        combatants, _player_comb_id, spell_key, sheet, conn, ch_id, row, target_id, out,
    )
    if _tgt_early is not None:
        return _tgt_early

    # ── B9 (#656): czar NIE-atakujący (kondycja) — pojedynek INT vs WIS/CON, NIE unik ──
    # Wykrywamy PRZED ścieżką ataku/obrażeń: czar `effect` w walce nakłada kondycję
    # FAZY S testem przeciwnym (decyzja D-spell), zamiast zadawać obrażenia jak broń.
    if spell_key:
        _eff_row = conn.execute(
            "SELECT key, label, spell_type, effect_type, effect_duration, mana_cost, tier "
            "FROM game_config_spells WHERE key = ? AND is_active = 1",
            (spell_key,),
        ).fetchone()
        if _eff_row and str(_eff_row["spell_type"] or "").strip().lower() == "effect":
            _cond_k = str(_eff_row["effect_type"] or "").strip().lower()
            _has_cond = conn.execute(
                "SELECT 1 FROM game_config_conditions WHERE key = ? AND is_active = 1",
                (_cond_k,),
            ).fetchone()
            if _has_cond:
                return _resolve_effect_spell_in_combat(
                    conn, row, campaign_id, ch_id, sheet, combatants,
                    enemy, target_id, _eff_row, raw_d20, out,
                )
            # Efekt bez kondycji w katalogu FAZY S (np. sleep→sleeping): nie wspieramy
            # w Fazie 1 — łagodne odbicie, tura nietknięta (zero duplikatu stanów).
            out["hit"] = False
            out["blocked"] = True
            out["block_reason"] = "unsupported_effect"
            out["message"] = (
                f"Czar „{_eff_row['label']}” nie jest jeszcze wspierany w walce."
            )
            out["combat_state"] = _row_to_combat_dict(row)
            return out

    # ── B17 (#823): czar kontroli OBSZAROWY (mass_fear) — kondycja na WSZYSTKICH wrogach ──
    # Wykrywamy PRZED attack_aoe: spell_type='effect_aoe' nakłada kondycję FAZY S pojedynkiem
    # przeciwnym INT per wróg (decyzja D3 — casting INT), zamiast zadawać obrażenia.
    if spell_key:
        _eaoe_row = conn.execute(
            "SELECT key, label, spell_type, effect_type, effect_duration, mana_cost, tier "
            "FROM game_config_spells WHERE key = ? AND is_active = 1",
            (spell_key,),
        ).fetchone()
        if _eaoe_row and str(_eaoe_row["spell_type"] or "").strip().lower() == "effect_aoe":
            _cond_k = str(_eaoe_row["effect_type"] or "").strip().lower()
            _has_cond = conn.execute(
                "SELECT 1 FROM game_config_conditions WHERE key = ? AND is_active = 1",
                (_cond_k,),
            ).fetchone()
            if _has_cond:
                return _resolve_aoe_effect_spell_in_combat(
                    conn, row, campaign_id, ch_id, sheet, combatants,
                    enemy, target_id, _eaoe_row, raw_d20, out,
                )
            out["hit"] = False
            out["blocked"] = True
            out["block_reason"] = "unsupported_effect"
            out["message"] = (
                f"Czar „{_eaoe_row['label']}” nie jest jeszcze wspierany w walce."
            )
            out["combat_state"] = _row_to_combat_dict(row)
            return out

    # ── B10 (#657): czar OBRONNY (ward_of_iron/mage_armor) — pula absorpcji ──
    # Self-buff: nakłada temp-HP na combatanta gracza, NIE atakuje wroga.
    # Wykrywany PRZED ścieżką ataku (inaczej wpadał w fallback 2d6 — ukryty bug).
    if spell_key:
        _def_row = conn.execute(
            "SELECT key, label, spell_type, mana_cost, tier "
            "FROM game_config_spells WHERE key = ? AND is_active = 1",
            (spell_key,),
        ).fetchone()
        if _def_row and str(_def_row["spell_type"] or "").strip().lower() == "defense":
            return _resolve_defense_spell_in_combat(
                conn, row, campaign_id, ch_id, sheet, combatants, _def_row, out,
                caster_comb_id=_player_comb_id,
                requested_target_id=_b14_req_target,
                mass=_b14_is_mass_spell(str(_def_row["key"])),
            )

    # ── B16 (#822): czar REAKCJI (mirror_image/blink/globe) — stan prewencyjny ──
    # Self-buff: zapisuje stan auto-wyzwalany przy następnym trafieniu wroga
    # (_try_spell_reaction). Wykrywany PRZED ścieżką ataku (inaczej wpadał w fallback).
    if spell_key:
        _react_row = conn.execute(
            "SELECT key, label, spell_type, mana_cost, tier "
            "FROM game_config_spells WHERE key = ? AND is_active = 1",
            (spell_key,),
        ).fetchone()
        if _react_row and str(_react_row["spell_type"] or "").strip().lower() == "reaction":
            return _resolve_reaction_spell_in_combat(
                conn, row, campaign_id, ch_id, sheet, combatants, _react_row, out,
                caster_comb_id=_player_comb_id,
            )

    # ── B11 (#659): czar AoE (attack_aoe) — multi-target ──────────────
    # Wykrywamy PRZED ścieżką ST ataku: czar AoE uderza w WSZYSTKICH żywych
    # wrogów (aoe=1) lub maks 3 (aoe=0, chain). Reużywa tego samego d20.
    if spell_key:
        # Detekcja BEZ kolumny `aoe` — izolowane fikstury testowe mogą jej
        # nie mieć (real schema zawsze ma). Handler dociąga `aoe` osobno.
        _aoe_row = conn.execute(
            "SELECT key, label, spell_type, mana_cost, damage_die, tier "
            "FROM game_config_spells WHERE key = ? AND is_active = 1",
            (spell_key,),
        ).fetchone()
        if _aoe_row and str(_aoe_row["spell_type"] or "").strip().lower() == "attack_aoe":
            return _resolve_aoe_spell_in_combat(
                conn, row, campaign_id, ch_id, sheet, combatants,
                enemy, target_id, _aoe_row, raw_d20, out, loot_pool_accum,
            )
    # ── B13 (#663): czar LECZĄCY (heal) — self-heal w walce ──────────
    if spell_key:
        _heal_row = conn.execute(
            "SELECT key, label, spell_type, mana_cost, tier "
            "FROM game_config_spells WHERE key = ? AND is_active = 1",
            (spell_key,),
        ).fetchone()
        if _heal_row and str(_heal_row["spell_type"] or "").strip().lower() == "heal":
            return _resolve_heal_spell_in_combat(
                conn, row, campaign_id, ch_id, sheet, combatants, _heal_row, out,
                caster_comb_id=_player_comb_id,
                requested_target_id=_b14_req_target,
                mass=_b14_is_mass_spell(str(_heal_row["key"])),
            )
    # ── B15 (#821): czar PRZYWOŁANIA (summon) — dodaj towarzysza-kombatanta ──
    # Wykrywamy PRZED ścieżką ataku: summon nie atakuje wroga rzutem gracza,
    # tylko wstawia nowego kombatanta type=='summon' do walki (własna tura niżej).
    if spell_key:
        _sum_row = conn.execute(
            "SELECT key, label, spell_type, mana_cost, tier, effect_json "
            "FROM game_config_spells WHERE key = ? AND is_active = 1",
            (spell_key,),
        ).fetchone()
        if _sum_row and str(_sum_row["spell_type"] or "").strip().lower() == "summon":
            return _resolve_summon_spell_in_combat(
                conn, row, campaign_id, ch_id, sheet, combatants, _sum_row, out,
                caster_comb_id=_player_comb_id,
            )
    # ─────────────────────────────────────────────────────────────────

    card_key, card_name = _roll_card_enemy_identity(conn, enemy, str(target_id))
    old_ek = str(enemy.get("enemy_key") or "").strip().lower()
    if old_ek in ("", "enemy"):
        enemy["enemy_key"] = card_key
    old_nm = str(enemy.get("name") or "").strip().lower()
    if old_nm in ("", "wróg", "wrog", "enemy"):
        enemy["name"] = card_name

    # #598: dual-wield off-hand — wymuszona broń (pomija sheet/spell/scholar)
    if weapon_override is not None:
        weapon_row = weapon_override
    # If spell_key provided, override weapon with spell stats
    elif spell_key:
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
    # ── #764: amunicja — broń dystansowa zużywa strzały/bełty ──────────
    # Brak amunicji → blokada strzału BEZ konsumpcji tury (jak out_of_range).
    # Off-hand (#598) i czary pomijamy — liczy się broń główna dystansowa.
    if weapon_override is None and not spell_key:
        from app.services import ammo_service as _ammo
        _ammo_key = _ammo.ammo_key_for_weapon(weapon_row)
        if _ammo_key:
            _have = _ammo.get_ammo_quantity(conn, ch_id, _ammo_key)
            if _have <= 0:
                out["hit"] = False
                out["blocked"] = True
                out["block_reason"] = "no_ammo"
                out["ammo_key"] = _ammo_key
                out["ammo_remaining"] = 0
                out["message"] = (
                    "Brak amunicji — nie masz czym wystrzelić. "
                    "Zdobądź strzały/bełty lub użyj innej broni."
                )
                out["combat_state"] = _row_to_combat_dict(row)
                return out
            _ammo.consume_ammo(conn, ch_id, _ammo_key, 1)
            out["ammo_key"] = _ammo_key
            out["ammo_remaining"] = max(0, _have - 1)
            _record_ammo_spent(conn, campaign_id, _ammo_key, 1)
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
    # D2 (#780): pierwszy cios w `zaskoczony` = auto-trafienie. Wróg nie zdążył
    # zareagować — uniki nie liczą się (poza Nat1 gracza, który zawsze pudłuje).
    if _surprise_fx.get("first_hit_auto") and not player_nat1 and not hit:
        hit = True
        dodged = False
        out["surprise_auto_hit"] = True
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
    # #754: strukturalny rejestr — atak gracza
    try:
        from app.services.dice_log_service import record_dice_roll as _rec_roll
        _rec_roll(
            campaign_id=campaign_id,
            roll_type="attack_player",
            character_id=ch_id,
            combat_id=int(row["id"]),
            actor="player",
            notation="1d20",
            raw_rolls=[player_raw] if player_raw is not None else None,
            modifiers={"total_bonus": int(roll_result or 0) - int(player_raw or 0)},
            total=int(roll_result or 0),
            dc=enemy_ac,
            outcome=("crit_success" if player_nat20 else "crit_fail" if player_nat1
                     else "hit" if hit else "dodged" if dodged else "miss"),
            meta={"weapon_key": out.get("weapon_key"), "enemy_key": card_key,
                  "round": int(row["round"] or 1)},
        )
    except Exception:
        pass

    loot: list[dict] = []
    out["gold_drop"] = 0
    dmg = 0
    player_attack_log_meta = None
    if attack_roll:
        # #861: weapon_override (dual-wield off-hand) → oznacz kartę jako 'drugi cios'.
        player_attack_log_meta = json.dumps(
            _player_attack_narrative_dict(
                attack_roll, player_raw, roll_result, weapon_row,
                offhand=weapon_override is not None,
            ),
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
        _mana_ok, _new_mana = check_and_deduct_mana(
            sheet, _spell_mana_cost,
            campaign_id=campaign_id, character_id=ch_id, combat_id=int(row["id"]),
        )
        if not _mana_ok:
            _persist_combatants(conn, row, combatants)
            _save_char_sheet(conn, campaign_id, int(row["character_id"]), sheet)
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
        _save_char_sheet(conn, campaign_id, int(row["character_id"]), sheet)
    # ─────────────────────────────────────────────────────────────────

    if hit:
        dmg = _attack_compute_damage(
            weapon_row, sheet, enemy, combatants, _player_comb_id,
            bool(player_nat20), player_raw, _surprise_fx, int(roll_result or 0),
            conn, ch_id, campaign_id, row, card_key, out,
        )
        dmg = _attack_apply_effects(
            weapon_row, sheet, enemy, combatants, _player_comb_id,
            player_raw, _surprise_fx, conn, ch_id, out, dmg,
        )
        # ─────────────────────────────────────────────────────────────

        dead = int(enemy.get("hp_current", 0) or 0) <= 0
        out["enemy_dead"] = dead


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
                        distribute_mp_loot,
                        grant_loot_to_character,
                        roll_gold_drop,
                        roll_loot,
                    )
                    _enemy_loot_tier = str(enemy.get("loot_tier") or "") or None

                    # G10 (#795): MP path — each player gets own class-filtered roll;
                    # gold split equally. Solo path unchanged.
                    if _is_mp_combat(combatants):
                        mp_result = distribute_mp_loot(campaign_id, ek)
                        loot = []
                        gold_drop = mp_result.get("total_gold", 0)
                        out["gold_drop"] = max(0, gold_drop)
                        out["mp_loot"] = {}
                        for _cid, _pdata in mp_result.get("per_player", {}).items():
                            _cid_int = int(_cid)
                            _ploot = _pdata.get("loot") or []
                            _pgold = int(_pdata.get("gold") or 0)
                            if _pgold > 0:
                                apply_character_gold_delta(_cid_int, _pgold, reason="combat_loot_mp")
                            if _ploot:
                                try:
                                    grant_loot_to_character(
                                        _cid_int, _ploot,
                                        source="loot",
                                        loot_tier=_enemy_loot_tier,
                                    )
                                except Exception:
                                    pass
                            out["mp_loot"][_cid_int] = {"gold": _pgold, "items": _ploot}
                            loot.extend(_ploot)
                    else:
                        # Solo path — unchanged
                        loot_items = roll_loot(ek)
                        if loot_items:
                            loot = _preview_loot_from_roll_items(loot_items, loot_tier=_enemy_loot_tier, conn=conn)
                        else:
                            loot = []
                        gold_drop = int(roll_gold_drop(ek) or 0)
                        if gold_drop > 0:
                            apply_character_gold_delta(ch_id, gold_drop, reason="combat_loot")
                        out["gold_drop"] = max(0, gold_drop)
                    # #754: strukturalny rejestr — loot + złoto (ścieżka pojedynczego ubicia)
                    try:
                        from app.services.dice_log_service import record_dice_roll as _rec_roll
                        _rec_roll(
                            campaign_id=campaign_id, roll_type="gold",
                            character_id=ch_id, combat_id=int(row["id"]),
                            actor=ek, total=max(0, gold_drop), outcome="drop",
                            meta={"enemy_key": ek, "loot_tier": _enemy_loot_tier,
                                  "round": int(row["round"] or 1)},
                        )
                        if loot:
                            _rec_roll(
                                campaign_id=campaign_id, roll_type="loot",
                                character_id=ch_id, combat_id=int(row["id"]),
                                actor=ek, total=len(loot), outcome="drop",
                                meta={"enemy_key": ek, "items": loot,
                                      "round": int(row["round"] or 1)},
                            )
                    except Exception:
                        pass
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
                    # #1011: auto-close kill quests on the same event
                    from app.services.quest_persist_service import auto_complete_quests_by_event
                    auto_complete_quests_by_event(
                        conn, campaign_id, "kill_enemy", _enemy_label, _tn_beat
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
                _scholar_restore_mana_after_combat(conn, ch_id, sheet, "victory", campaign_id=campaign_id)
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
                        # PT10 #1120: clear local hex encounter after victory
                        local_hex = _sf_hex.get("local_hex")
                        if local_hex and local_hex.get("hex_id"):
                            _cleared2 = _sf_hex.get("cleared_local_hexes") or []
                            _lhid2 = int(local_hex["hex_id"])
                            if _lhid2 not in _cleared2:
                                _cleared2.append(_lhid2)
                                _sf_hex["cleared_local_hexes"] = _cleared2
                                conn.execute(
                                    "UPDATE game_sessions SET session_flags = ? WHERE campaign_id = ?",
                                    (json.dumps(_sf_hex, ensure_ascii=False), campaign_id),
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
                # L4: mark current dungeon tile node cleared after victory
                try:
                    from app.services.dungeon_tile_service import mark_node_cleared
                    mark_node_cleared(campaign_id, int(ch_id))
                except Exception:
                    pass
                # L18 (#729 follow-up): dungeon-only healing sustain drop (server-side).
                try:
                    from app.services.dungeon_tile_service import grant_dungeon_victory_sustain
                    _sustain = grant_dungeon_victory_sustain(campaign_id, int(ch_id))
                    if _sustain:
                        out["dungeon_sustain"] = _sustain
                except Exception:
                    pass
                # L8: boss tile cleared → checkpoint + loot + boss_choice_pending flag
                try:
                    from app.services.dungeon_tile_service import on_boss_tile_cleared
                    _boss_result = on_boss_tile_cleared(campaign_id, int(ch_id))
                    if _boss_result.get("is_boss_tile"):
                        out["dungeon_boss_defeated"] = True
                        out["dungeon_boss_loot"] = _boss_result.get("loot", [])
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
        _pc_miss = _find_combatant(combatants, _player_comb_id)
        if _pc_miss is not None:
            _hidden_miss = _hidden_conditions(_pc_miss)
            if _hidden_miss:
                _remove_combatant_conditions(_pc_miss, _hidden_miss)

    _attack_spell_secondary(
        _is_spell, player_nat20, player_nat1, hit, enemy, dmg, out, sheet,
        conn, campaign_id, row,
    )

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


def _resolve_enemy_attack_turn(
    conn,
    row,
    campaign_id: int,
    combatants: list,
    loot_pool_accum: list,
    ch_id: int,
    sheet: dict,
    out: dict,
) -> dict:
    """R2.3 (#878): enemy attack path extracted from resolve_attack."""
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
    player_c = _find_active_player_combatant(combatants) or {}

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
    # G17 (#794): use first active (non-knocked) player; reload sheet for MP target
    p = _find_active_player_combatant(combatants)
    if not p:
        # All players knocked — enemy has no valid target; advance turn
        _persist_combatants(conn, row, combatants, loot_pool=loot_pool_accum)
        conn.commit()
        advance_turn(campaign_id)
        out["combat_state"] = load_combat_snapshot(campaign_id)
        return out
    _target_mp_ch_id = _mp_player_char_id(str(p.get("id") or ""))
    if _target_mp_ch_id is not None and _target_mp_ch_id != ch_id:
        ch_id = _target_mp_ch_id
        _tchar = conn.execute(
            "SELECT id, sheet_json FROM characters WHERE id=?", (ch_id,)
        ).fetchone()
        if _tchar:
            sheet = parse_character_sheet(_tchar["sheet_json"])
            from app.services.campaign_state_service import overlay_sheet_from_campaign_state as _ov_cs
            _ov_cs(conn, campaign_id, ch_id, sheet)
    pac = int(p.get("defense", _player_ac_from_sheet(sheet)))
    p["defense"] = pac  # przechowujemy BAZOWĄ obronę (bez parowania)
    # #598: parowanie (cięższa main + druga broń w off) → +obrona dla TEGO ciosu,
    # czyli redukcja obrażeń wg #826. Nie zapisywane na combatancie (brak stackowania).
    try:
        _parry598 = int(parry_defense_bonus(conn, ch_id, sheet) or 0)
    except Exception:
        _parry598 = 0
    if _parry598:
        pac += _parry598
        out["parry_bonus"] = _parry598
    # #826: KONIEC double jeopardy. AC NIE jest progiem trafienia (przeszło na redukcję
    # obrażeń niżej). Jeden test obronny:
    #  • gracz ma reakcję (dodge/shield + tarcza) → cios dosięga, jedyny test = OKNO REAKCJI
    #    (rozliczane w resolve_reaction / _try_dodge_reaction poniżej); AC pominięte.
    #  • brak reakcji → pojedynczy pasywny unik d20+DEX (symetria z wrogiem).
    hit = _attack_resolve_defense(attack_roll, raw, pac, conn, ch_id, p, sheet, row, enemy, out)

    _log_dice_roll_combat_resolve(
        source="combat_enemy",
        campaign_id=campaign_id,
        result_total=int(attack_roll),
        dc=int(pac),
        hit=bool(hit),
        raw_d20=int(raw),
    )
    # #754: strukturalny rejestr — atak wroga
    try:
        from app.services.dice_log_service import record_dice_roll as _rec_roll
        _rec_roll(
            campaign_id=campaign_id,
            roll_type="attack_enemy",
            character_id=ch_id,
            combat_id=int(row["id"]),
            actor=str(enemy.get("enemy_key") or "enemy"),
            notation="1d20",
            raw_rolls=[int(raw)],
            modifiers={"attack_bonus": int(atk_b), "wound_penalty": int(wp)},
            total=int(attack_roll),
            dc=int(pac),
            outcome=("crit_success" if raw == 20 else "crit_fail" if raw == 1
                     else "hit" if hit else "miss"),
            meta={"enemy_name": out.get("enemy_name"), "round": int(row["round"] or 1)},
        )
    except Exception:
        pass

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
        dmg, _dodge, _block, _react_early = _attack_try_reaction(
            p, row, out, conn, ch_id, sheet, attack_roll, raw, enemy, combatants, campaign_id, dmg,
        )
        if _react_early is not None:
            return _react_early
        # #826: margines→dmg + pancerz=redukcja na obrażeniach wroga (po uniku/bloku,
        # przed absorpcją/HP). Obrona gracza = pac (AC) — już nie próg trafienia. Nat 20 wroga
        # pomija pancerz. Symetria z player→enemy (ten sam apply_defense_model).
        if dmg > 0:
            _dm826p = apply_defense_model(dmg, int(attack_roll), int(pac), ignore_armor=bool(raw == 20))
            if _dm826p["margin_bonus"]:
                out["margin_damage_bonus"] = _dm826p["margin_bonus"]
            if _dm826p["armor_reduction"]:
                out["armor_reduction"] = _dm826p["armor_reduction"]
            dmg = _dm826p["final"]
        # B10 (#657): pula absorpcji tarczy pochłania obrażenia PRZED HP (po uniku/bloku).
        dmg = _apply_absorption(p, dmg, out)
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
        _record_reaction_rolls(campaign_id, ch_id, int(row["id"]), int(row["round"] or 1), out)
        # #853: strukturalny rejestr — obrażenia wroga na graczu
        try:
            from app.services.dice_log_service import record_dice_roll as _rec_roll
            _rec_roll(
                campaign_id=campaign_id,
                roll_type="damage",
                character_id=ch_id,
                combat_id=int(row["id"]),
                actor=str(enemy.get("enemy_key") or "enemy"),
                notation=str(enemy.get("damage_dice") or "1d6"),
                raw_rolls=[],
                total=int(out.get("damage", 0)),
                outcome="crit_success" if raw == 20 else "hit",
                meta={"enemy_key": str(enemy.get("enemy_key") or "enemy"),
                      "enemy_name": out.get("enemy_name"),
                      "round": int(row["round"] or 1),
                      "armor_reduction": out.get("armor_reduction", 0),
                      "nat20_ignored_armor": bool(raw == 20),
                      "margin_damage": out.get("margin_damage_bonus", 0)},
            )
        except Exception:
            pass
        # #761: rejestr zmiany HP gracza (cios wroga)
        if next_hp != prev:
            try:
                from app.services.state_log_service import record_state_change as _rec_state
                _rec_state(campaign_id=campaign_id, resource="hp", character_id=ch_id,
                           combat_id=int(row["id"]), before_val=prev, after_val=next_hp,
                           cause="combat_damage", meta={"round": int(row["round"] or 1),
                                                        "enemy_name": out.get("enemy_name")})
            except Exception:
                pass
        p["hp_current"] = next_hp
        sheet["current_hp"] = next_hp
        out["player_hp_remaining"] = next_hp
        incap = next_hp <= 0
        out["player_incapacitated"] = incap
        _save_char_sheet(conn, campaign_id, ch_id, sheet)
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
            _enemy_attack_narrative_dict(out, raw, attack_roll, pac, enemy, atk_b),
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
    return out


def resolve_attack(
    campaign_id: int,
    roll_result: int | None,
    attacker: str = "player",
    raw_d20: int | None = None,
    spell_key: str | None = None,
    target_id: str | None = None,
    weapon_override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    attacker: 'player' uses roll_result as total attack vs enemy dodge roll.
    attacker: 'enemy' ignores roll_result; rolls d20+attack_bonus internally vs player AC.
    weapon_override: #598 dual-wield — force this weapon row (off-hand) instead of the
      sheet/inventory main weapon. Used by :func:`resolve_offhand_followup`.
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

        # G7 (#791): MP player — attacker="player:N" → use that character's sheet
        _mp_ch_id = _mp_player_char_id(str(attacker))
        if _mp_ch_id is not None:
            ch_id = _mp_ch_id

        character = conn.execute(
            "SELECT id, sheet_json FROM characters WHERE id = ?",
            (ch_id,),
        ).fetchone()
        if not character:
            raise ValueError("character missing")

        sheet = parse_character_sheet(character["sheet_json"])
        from app.services.campaign_state_service import overlay_sheet_from_campaign_state
        overlay_sheet_from_campaign_state(conn, campaign_id, ch_id, sheet)
        out: dict[str, Any] = {"attacker": attacker, "hit": False}

        # G7 (#791): MP players use 'player:N' as combatant id; solo uses 'player'
        _player_comb_id = str(attacker) if _mp_ch_id is not None else "player"

        # B14 (#820): zapamiętaj cel WSKAZANY przez gracza zanim _select_player_target
        # nadpisze go celem-wrogiem (czary wsparcia kierują na przyjazny slot).
        _b14_req_target = str(target_id) if target_id is not None else None

        if attacker == "player" or _mp_ch_id is not None:
            return _resolve_player_attack_turn(
                conn, row, campaign_id, combatants, loot_pool_accum, ch_id, sheet,
                attacker, roll_result, raw_d20, spell_key, target_id, weapon_override,
                out, _mp_ch_id, _player_comb_id, _b14_req_target,
            )

        if attacker != "enemy":
            raise ValueError("invalid attacker")

        out = _resolve_enemy_attack_turn(
            conn, row, campaign_id, combatants, loot_pool_accum, ch_id, sheet, out,
        )

    if attacker == "enemy" and out.get("player_incapacitated"):
        _snap_chk = load_combat_snapshot(campaign_id)
        _combatants_chk: list[dict] = (_snap_chk or {}).get("combatants") or []
        if _is_mp_combat(_combatants_chk):
            # G17 (#794): MP — knocked, not dead
            _handle_mp_player_knocked(campaign_id, out)
        else:
            end_combat(campaign_id, "player_dead", defeated_by=out.get("enemy_name"))
            out["defeated_by"] = out.get("enemy_name")
            out["combat_state"] = load_combat_snapshot(campaign_id)
    return out



def resolve_reaction(campaign_id: int, choice: str = "take") -> dict[str, Any]:
    """SF10 (#633) — rozlicza okno reakcji otwarte przez `resolve_attack` (enemy hit).

    ``choice``:
      • take  → pełne obrażenia z `pending_reaction` (bez rzutu),
      • dodge → test DEX vs trafienie (reuse `_try_dodge_reaction`); sukces = 0 dmg,
      • block / shield_block → test STR (reuse `_try_shield_block_reaction`); redukcja/odparcie.

    Czyści `pending_reaction`, oznacza reakcję zużytą w rundzie (`reaction_used_round`),
    nalicza wynikowe obrażenia (z `on_zero_hp_save`), wznawia walkę. Timeout po stronie
    frontendu wysyła `take`. RZUT ATAKU WROGA NIETKNIĘTY — działamy tylko na obrażenia."""
    ch = str(choice or "take").strip().lower()
    if ch == "block":
        ch = "shield_block"
    if ch not in {"take", "dodge", "shield_block"}:
        raise ValueError(f"unknown reaction choice: {choice}")

    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM active_combat WHERE campaign_id = ? AND status = 'active'",
            (campaign_id,),
        ).fetchone()
        if not row:
            raise ValueError("no active combat")
        combatants: list[dict] = json.loads(row["combatants"] or "[]")
        p = _find_combatant(combatants, "player")
        if not p:
            raise ValueError("player combatant missing")
        pending = p.get("pending_reaction")
        if not pending:
            raise ValueError("no pending reaction")

        ch_id = int(row["character_id"])
        character = conn.execute(
            "SELECT id, sheet_json FROM characters WHERE id = ?", (ch_id,)
        ).fetchone()
        if not character:
            raise ValueError("character missing")
        sheet = parse_character_sheet(character["sheet_json"])
        from app.services.campaign_state_service import overlay_sheet_from_campaign_state as _ov_react
        _ov_react(conn, campaign_id, ch_id, sheet)

        attack_roll = int(pending.get("attack_roll") or 0)
        round_n = int(pending.get("round") or row["round"] or 1)
        dmg = int(pending.get("damage") or 0)
        out: dict[str, Any] = {"attacker": "enemy", "hit": True, "reaction_resolved": True,
                               "enemy_name": str(pending.get("enemy_name") or "Wróg")}
        _dodge = None
        _block = None

        if ch == "dodge":
            p["reaction_declared"] = "dodge"
            _dodge = _try_dodge_reaction(p, sheet, attack_roll, round_n)
            if _dodge is not None:
                out["reaction"] = _dodge
                if _dodge.get("dodged"):
                    dmg = 0
        elif ch == "shield_block":
            p["reaction_declared"] = "shield_block"
            _block = _try_shield_block_reaction(conn, ch_id, p, sheet, attack_roll, round_n, dmg)
            if _block is not None:
                out["reaction"] = _block
                if _block.get("available"):
                    dmg = int(_block.get("damage_after", dmg))
        # ch == "take": dmg bez zmian

        # zużycie reakcji w rundzie + zamknięcie okna
        p.pop("pending_reaction", None)
        p.pop("reaction_declared", None)
        p["reaction_used_round"] = round_n

        # #826: margines→dmg + pancerz=redukcja na obrażeniach wroga (ścieżka reakcji — take/blok
        # po nieudanym uniku). Obrona gracza = pac (AC). Nat 20 wroga (z pending) pomija pancerz.
        if dmg > 0:
            _pac826 = int(p.get("defense", _player_ac_from_sheet(sheet)))
            # #598: parowanie dolicza obronę także na ścieżce reakcji (take/blok)
            try:
                _parry598r = int(parry_defense_bonus(conn, ch_id, sheet) or 0)
            except Exception:
                _parry598r = 0
            if _parry598r:
                _pac826 += _parry598r
                out["parry_bonus"] = _parry598r
            _dm826r = apply_defense_model(dmg, int(attack_roll), _pac826,
                                          ignore_armor=bool(pending.get("nat20")))
            if _dm826r["margin_bonus"]:
                out["margin_damage_bonus"] = _dm826r["margin_bonus"]
            if _dm826r["armor_reduction"]:
                out["armor_reduction"] = _dm826r["armor_reduction"]
            dmg = _dm826r["final"]

        # B10 (#657): pula absorpcji tarczy pochłania obrażenia PRZED HP (po uniku/bloku).
        dmg = _apply_absorption(p, dmg, out)
        out["damage"] = dmg
        prev = int(p.get("hp_current", 0) or 0)
        next_hp = max(0, prev - dmg)
        if next_hp <= 0:
            save_res = _on_zero_hp_save(p, sheet=None)
            if save_res is not None:
                out["on_zero_hp_save"] = save_res
                if save_res.get("saved") and save_res.get("hp"):
                    next_hp = int(save_res["hp"])
        _record_reaction_rolls(campaign_id, ch_id, int(row["id"]), round_n, out)
        # #761: rejestr zmiany HP gracza (cios wroga — ścieżka reakcji)
        if next_hp != prev:
            try:
                from app.services.state_log_service import record_state_change as _rec_state
                _rec_state(campaign_id=campaign_id, resource="hp", character_id=ch_id,
                           combat_id=int(row["id"]), before_val=prev, after_val=next_hp,
                           cause="combat_damage", meta={"round": round_n,
                                                        "enemy_name": out.get("enemy_name")})
            except Exception:
                pass
        p["hp_current"] = next_hp
        sheet["current_hp"] = next_hp
        out["player_hp_remaining"] = next_hp
        incap = next_hp <= 0
        out["player_incapacitated"] = incap
        _save_char_sheet(conn, campaign_id, ch_id, sheet)

        cid = int(row["id"])
        # log reakcji (unik/blok) — Sandbox/UI pokazuje test i wynik
        _react = _dodge if _dodge is not None else _block
        if _react is not None and _react.get("available"):
            tn_r = _next_combat_log_sequence(conn, cid)
            log_combat_turn(
                conn, combat_id=cid, campaign_id=campaign_id, turn_number=tn_r,
                actor="player", event_type="reaction",
                roll_value=int(_react.get("dodge_total") or _react.get("block_total") or 0),
                damage=int(out.get("damage") or 0), hp_after=next_hp,
                target_id="player", target_name=str(p.get("name") or "Bohater"),
                hit=bool(_react.get("dodged") or _react.get("full_block") or (_react.get("reduction") or 0) > 0),
                narrative=json.dumps({**_react, "choice": ch}, ensure_ascii=False),
            )
        else:
            # take — log decyzji „przyjmuję cios"
            tn_r = _next_combat_log_sequence(conn, cid)
            log_combat_turn(
                conn, combat_id=cid, campaign_id=campaign_id, turn_number=tn_r,
                actor="player", event_type="reaction", roll_value=0,
                damage=int(out.get("damage") or 0), hp_after=next_hp,
                target_id="player", target_name=str(p.get("name") or "Bohater"),
                hit=False,
                narrative=json.dumps({"reaction": "take", "choice": ch,
                                      "damage": int(out.get("damage") or 0)}, ensure_ascii=False),
            )

        _persist_combatants(conn, row, combatants)
        conn.commit()
        out["combat_state"] = load_combat_snapshot(campaign_id)

    if out.get("player_incapacitated"):
        _snap_chk2 = load_combat_snapshot(campaign_id)
        _combatants_chk2: list[dict] = (_snap_chk2 or {}).get("combatants") or []
        if _is_mp_combat(_combatants_chk2):
            # G17 (#794): MP — knocked, not dead
            _handle_mp_player_knocked(campaign_id, out)
        else:
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


def resolve_offhand_followup(campaign_id: int) -> dict[str, Any] | None:
    """#598 — drugi atak OFF-HAND w tej samej turze gracza.

    Wołane po głównym ataku gracza, PRZED `advance_turn` (oba ataki = jedna tura).
    Strzela tylko gdy para broni klasyfikuje się jako 'dual_attack' (dwie lekkie
    bronie + skill `dual_wield` rank≥1) i walka wciąż trwa z żywym wrogiem.
    Zwraca wynik off-hand `resolve_attack` (pełny: unik/obrażenia/#826/loot/XP) albo
    None gdy brak dual-wield / brak żywych wrogów / nie tura gracza."""
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM active_combat WHERE campaign_id = ? AND status = 'active'",
            (campaign_id,),
        ).fetchone()
        if not row or str(row["current_turn"]) != "player":
            return None
        ch_id = int(row["character_id"])
        ch = conn.execute("SELECT sheet_json FROM characters WHERE id = ?", (ch_id,)).fetchone()
        sheet = parse_character_sheet(ch["sheet_json"]) if ch and ch["sheet_json"] else {}
        combatants: list[dict] = json.loads(row["combatants"] or "[]")
        combo, _main_row, off_row = player_dual_combo_for_character(conn, ch_id, sheet)
        if combo != "dual_attack" or not off_row:
            return None
        if not _living_enemy_ids(combatants):
            return None
    off_raw = roll_d20()
    return resolve_attack(
        campaign_id, None, attacker="player", raw_d20=off_raw, weapon_override=off_row,
    )


def resolve_enemy_followup_attacks(campaign_id: int) -> list[dict[str, Any]]:
    """#864 — dodatkowe ataki wroga w TEJ SAMEJ turze, gdy ``attacks_per_turn`` > 1.

    Wołane PO pierwszym ataku wroga, PRZED ``advance_turn`` (wszystkie ciosy = jedna tura).
    Pętla reużywa istniejącą ścieżkę ``resolve_attack(attacker='enemy')`` (rzut + #826 redukcja
    + okno reakcji gracza per cios). Każdy cios = osobny wpis w ``combat_turns`` (robi to
    ``resolve_attack``).

    RE-ENTRANT: liczbę wykonanych ciosów trzyma marker ``mattack_marker`` (runda+id wroga)
    z licznikiem ``mattack_done`` na combatancie wroga — dzięki temu można wołać tę funkcję
    ponownie po rozliczeniu okna reakcji (``resolve_reaction``) i dokończyć resztę ciosów.

    Przerywa, gdy: gracz padł (brak dobijania trupa), walka skończona, otwarte okno reakcji
    (pauza — wznawia ``resolve_reaction``), bieżąca tura przestała należeć do tego wroga
    (ścieżka szarży/detekcji sama zaawansowała turę), albo wykonano już N ciosów.

    Zwraca listę wyników kolejnych ataków (pusta gdy brak multi-attack lub przerwano od razu)."""
    results: list[dict[str, Any]] = []
    while True:
        with _conn() as conn:
            row = conn.execute(
                "SELECT * FROM active_combat WHERE campaign_id = ? AND status = 'active'",
                (campaign_id,),
            ).fetchone()
            if not row:
                break
            cur = str(row["current_turn"] or "").strip()
            if not cur or cur == "player":
                break  # tura już zaawansowana / nie należy do wroga
            combatants: list[dict] = json.loads(row["combatants"] or "[]")
            enemy = _find_combatant(combatants, cur)
            if not enemy or enemy.get("type") != "enemy":
                break
            n = int(enemy.get("attacks_per_turn") or 1)
            if n <= 1:
                break  # brak multi-attack → zero zmian względem dziś
            # nie dobijamy powalonego gracza
            p = _find_combatant(combatants, "player")
            if not p or int(p.get("hp_current", 0) or 0) <= 0:
                break
            marker = f"{int(row['round'] or 1)}:{cur}"
            if str(enemy.get("mattack_marker") or "") == marker:
                done = int(enemy.get("mattack_done") or 0)
            else:
                done = 0
            # pierwszy atak wykonano POZA tą funkcją (endpoint/resolve_reaction) — liczy się jako 1
            if done < 1:
                done = 1
            if done >= n:
                break
            # zapis markera+licznika PRZED ciosem → przetrwa ewentualną pauzę okna reakcji
            enemy["mattack_marker"] = marker
            enemy["mattack_done"] = done
            _persist_combatants(conn, row, combatants)
            conn.commit()

        res = resolve_attack(campaign_id, 0, attacker="enemy")
        results.append(res)

        # zlicz ten cios jako wykonany (nawet przy otwartym oknie reakcji — cios padł)
        with _conn() as conn:
            row = conn.execute(
                "SELECT * FROM active_combat WHERE campaign_id = ? AND status = 'active'",
                (campaign_id,),
            ).fetchone()
            if row:
                cur2 = str(row["current_turn"] or "").strip()
                combatants2: list[dict] = json.loads(row["combatants"] or "[]")
                enemy2 = _find_combatant(combatants2, cur2)
                if enemy2 and enemy2.get("type") == "enemy":
                    enemy2["mattack_done"] = int(enemy2.get("mattack_done") or 1) + 1
                    _persist_combatants(conn, row, combatants2)
                    conn.commit()

        if res.get("reaction_window"):
            break  # pauza — resztę ciosów dokończy resolve_reaction
        if res.get("player_incapacitated"):
            break  # gracz padł w trakcie — nie dobijamy
        snap = res.get("combat_state") or load_combat_snapshot(campaign_id)
        if not snap or snap.get("status") != "active":
            break
    return results


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
        # #761: rejestr zmiany strefy gracza
        try:
            from app.services.state_log_service import record_state_change as _rec_state
            _rec_state(campaign_id=campaign_id, resource="zone",
                       character_id=row["character_id"], combat_id=int(row["id"]),
                       before_val=old, after_val=new, cause="zone_change",
                       meta={"round": int(row["round"] or 1)})
        except Exception:
            pass

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


def use_consumable_in_combat(campaign_id: int, inventory_id: int) -> dict[str, Any]:
    """#734 — Gracz używa leczniczej (lub innej usable) mikstury z plecaka jako AKCJI walki.

    Domyka pętlę sustain #732: drop → wypij w groźnej walce. Delegacja do
    ``loot_service.use_inventory_item`` (leczy sheet, zmniejsza stack i syncuje PŻ do
    ``active_combat``), log zdarzenia ``use_item`` w combat_turns, po czym KONSUMUJE turę.

    Wymaga aktywnej walki i tury gracza. Poza walką / poza turą → ValueError.
    """
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM active_combat WHERE campaign_id = ? AND status = 'active'",
            (campaign_id,),
        ).fetchone()
        if not row:
            raise ValueError("no active combat")
        if str(row["current_turn"]) != "player":
            raise ValueError("consumable use only on player's turn")
        character_id = int(row["character_id"])
        combat_id = int(row["id"])

    # Faktyczna konsumpcja: leczenie + dekrement stacka + sync PŻ do active_combat.
    from app.services import loot_service
    use_result = loot_service.use_inventory_item(character_id, int(inventory_id))

    # Log zdarzenia + odczyt PŻ po wyleczeniu (sync już zapisał combatants).
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM active_combat WHERE campaign_id = ? AND status = 'active'",
            (campaign_id,),
        ).fetchone()
        combatants: list[dict] = json.loads(row["combatants"] or "[]") if row else []
        p = _find_combatant(combatants, "player")
        hp_after = int((p or {}).get("hp_current", 0) or 0)
        item = use_result.get("item") or {}
        tn = _next_combat_log_sequence(conn, combat_id)
        log_combat_turn(
            conn,
            combat_id=combat_id,
            campaign_id=campaign_id,
            turn_number=tn,
            actor="player",
            event_type="use_item",
            roll_value=None,
            damage=None,
            hp_after=hp_after,
            target_id="player",
            target_name=str((p or {}).get("name") or "Bohater"),
            hit=None,
            narrative=json.dumps(
                {"item": item.get("key"), "label": item.get("label"),
                 "effects": use_result.get("effects_applied")},
                ensure_ascii=False,
            ),
        )
        conn.commit()

    advance_turn(campaign_id)
    return {
        "ok": True,
        "use_result": use_result,
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
        proficiency = proficiency_bonus(skill_rank)

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

        # S17-EXT (#622) Część A (solo): udane zapasy gracza z wrestling rank ≥ 3 nagradzają
        # SŁABSZYM darmowym ciosem w tej samej turze. Rank 1–2 = czysta kontrola (baza nietknięta
        # = balans chroniony; darmowy atak bezwarunkowo obsoletowałby „Atak"). Reuse ekonomii
        # `extra_action` (S12): follow-up NIE konsumuje kolejnej akcji — wrestling i tak woła
        # advance_turn() RAZ. Jeden cios na zapasy (inline event, brak pętli/rekurencji), obrażenia
        # ÷2 (floor, min 1), BEZ nat-20-double, BEZ ponownego wyzwalania zapasów. RZUTY ATAKU w
        # walce (nat 20/nat 1) NIETKNIĘTE — follow-up to osobny, słabszy cios. Część B (MP przewaga
        # sojusznika) ⛔ FAZA 5. Liczby = wartości startowe (Numbers Policy → tuning po B5/B13).
        followup: dict[str, Any] | None = None
        _oc = str(derived["outcome"]).strip().upper()
        if skill_rank >= 3 and _oc in ("SUCCESS", "CRITICAL_SUCCESS"):
            try:
                _fw = resolve_sheet_weapon(conn, sheet, int(row["character_id"])) or {}
                _die = str(_fw.get("damage_die") or "1d6").strip().lower()
                _dstat = str(_fw.get("linked_stat") or "STR").upper()
                _wlabel = str(_fw.get("label") or "broń")
            except Exception:
                _die, _dstat, _wlabel = "1d6", "STR", "broń"
            _raw = roll_damage_dice(_die, _stat_mod(sheet, _dstat))
            _half = max(1, _raw // 2)  # ÷2 floor, min 1 — słabszy cios
            _prev_hp = int(target.get("hp_current", 0) or 0)
            _new_hp = max(0, _prev_hp - _half)
            target["hp_current"] = _new_hp
            _fdead = _new_hp <= 0
            tn2 = _next_combat_log_sequence(conn, cid)
            log_combat_turn(
                conn,
                combat_id=cid,
                campaign_id=campaign_id,
                turn_number=tn2,
                actor="player",
                event_type="wrestling_followup",
                roll_value=None,
                damage=_half,
                hp_after=_new_hp,
                target_id=str(target.get("id")),
                target_name=target_name,
                hit=True,
                narrative=json.dumps({
                    "raw_damage": _raw, "damage": _half, "halved": True,
                    "weapon_label": _wlabel, "enemy_dead": _fdead, "skill_rank": skill_rank,
                }, ensure_ascii=False),
            )
            followup = {
                "damage": _half, "raw_damage": _raw, "weapon_label": _wlabel,
                "target_hp_remaining": _new_hp, "enemy_dead": _fdead,
            }

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
        "followup": followup,
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


# ── G17 (#794) — MP knockdown / wipe / revive ────────────────────────────────

def _handle_mp_player_knocked(campaign_id: int, out: dict) -> None:
    """G17: Mark the incapacitated player as knocked in MP; advance turn; check wipe."""
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM active_combat WHERE campaign_id=? AND status='active'",
            (campaign_id,),
        ).fetchone()
        if not row:
            return
        combatants: list[dict] = json.loads(row["combatants"] or "[]")
        for c in combatants:
            cid = str(c.get("id") or "")
            if (cid == "player" or cid.startswith("player:")) and int(c.get("hp_current", 0) or 0) <= 0:
                c["knocked"] = True
        _persist_combatants(conn, row, combatants)
        conn.commit()
    out["player_knocked"] = True
    out["player_incapacitated"] = False
    advance_turn(campaign_id)
    out["combat_state"] = load_combat_snapshot(campaign_id)


def _apply_mp_wipe(campaign_id: int, conn: Any, combatants: list[dict], row: Any) -> None:
    """G17: Wipe — gold penalty + revive; end combat 'wipe'.

    Penalty table and revival HP controlled by mp_balance flags (G15 #813).
    Players with < WIPE_GOLD_FLOOR gold are exempt. Items/XP/levels untouched.
    """
    from app.services.economy_service import change_gold
    from app.services import mp_balance as _mb

    player_combs = [
        c for c in combatants
        if str(c.get("id") or "") == "player" or str(c.get("id") or "").startswith("player:")
    ]

    # Avg level → wipe gold penalty %
    levels: list[int] = []
    for c in player_combs:
        cid = _mp_player_char_id(str(c.get("id") or ""))
        char_id = cid if cid is not None else (
            int(row["character_id"]) if row else None
        )
        if char_id:
            try:
                ch = conn.execute(
                    "SELECT sheet_json FROM characters WHERE id=?", (char_id,)
                ).fetchone()
                if ch:
                    lvl = int((parse_character_sheet(ch["sheet_json"]) or {}).get("level") or 1)
                    levels.append(max(1, lvl))
            except Exception:
                levels.append(1)
    avg_level = int(sum(levels) / len(levels)) if levels else 1
    pct = _mb.get_wipe_gold_pct(avg_level)
    gold_floor = int(_mb.WIPE_GOLD_FLOOR)
    hp_pct = float(_mb.WIPE_HP_PCT)

    for c in player_combs:
        cid = _mp_player_char_id(str(c.get("id") or ""))
        char_id = cid if cid is not None else (
            int(row["character_id"]) if row else None
        )
        # Revive at WIPE_HP_PCT of max HP
        max_hp = int(c.get("hp_max") or 1)
        revival_hp = max(1, int(max_hp * hp_pct))
        c["hp_current"] = revival_hp
        c["knocked"] = False

        if char_id:
            # Sync revival HP to campaign_character_state so post-combat turns see correct HP
            try:
                ch_row = conn.execute(
                    "SELECT sheet_json FROM characters WHERE id=?", (char_id,)
                ).fetchone()
                if ch_row:
                    wipe_sheet = parse_character_sheet(ch_row["sheet_json"])
                    from app.services.campaign_state_service import overlay_sheet_from_campaign_state as _ov
                    _ov(conn, campaign_id, char_id, wipe_sheet)
                    wipe_sheet["current_hp"] = revival_hp
                    _save_char_sheet(conn, campaign_id, char_id, wipe_sheet)
            except Exception:
                pass

            # Gold penalty (skip if below floor)
            try:
                gr = conn.execute("SELECT gold_gp FROM characters WHERE id=?", (char_id,)).fetchone()
                if gr:
                    gold = int(gr["gold_gp"] or 0)
                    if gold >= gold_floor:
                        penalty = max(1, int(gold * pct))
                        change_gold(conn, char_id, -penalty, "wipe_penalty", campaign_id=campaign_id)
            except Exception:
                pass

    _persist_combatants(conn, row, combatants)
    conn.execute(
        "UPDATE active_combat SET status='ended', ended_reason='wipe', updated_at=? WHERE campaign_id=?",
        (_now_iso(), campaign_id),
    )
    conn.commit()


def revive_knocked_mp_player(campaign_id: int, target_char_id: int) -> dict[str, Any] | None:
    """G17: Revive a knocked MP player to ~25% HP. Called on companion 'revive' action."""
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM active_combat WHERE campaign_id=? AND status='active'",
            (campaign_id,),
        ).fetchone()
        if not row:
            return None
        combatants: list[dict] = json.loads(row["combatants"] or "[]")
        target_actor_id = f"player:{target_char_id}"
        target = _find_combatant(combatants, target_actor_id)
        if not target:
            return None
        if not target.get("knocked"):
            return None
        max_hp = int(target.get("hp_max") or 1)
        target["hp_current"] = max(1, int(max_hp * 0.25))
        target["knocked"] = False
        _persist_combatants(conn, row, combatants)
        conn.commit()
    return {"revived": target_actor_id, "hp_restored": target["hp_current"]}


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
        _is_mp = _is_mp_combat(combatants)

        if _all_enemies_dead(combatants):
            # G17 (#794): auto-revive knocked players at 1 HP before victory
            if _is_mp:
                for c in combatants:
                    cid = str(c.get("id") or "")
                    if (cid == "player" or cid.startswith("player:")) and c.get("knocked"):
                        c["knocked"] = False
                        c["hp_current"] = max(1, c.get("hp_current") or 1)
            _persist_combatants_and_maybe_end(conn, row, combatants, status="ended", ended_reason="victory")
            conn.commit()
            # HF-1 (#523): clear scene_enemies — this path bypasses end_combat()
            try:
                set_world_state_flags(campaign_id, scene_enemies=[])
            except Exception:
                pass
            # L4: mark current dungeon tile node cleared after victory
            try:
                from app.services.dungeon_tile_service import mark_node_cleared
                mark_node_cleared(campaign_id, int(row["character_id"]))
            except Exception:
                pass
            return "ended"

        # G17 (#794): in MP, check wipe BEFORE building living list
        if _is_mp and _all_players_knocked(combatants):
            _apply_mp_wipe(campaign_id, conn, combatants, row)
            try:
                set_world_state_flags(campaign_id, scene_enemies=[])
            except Exception:
                pass
            return "wipe"

        # Build living: skip hp<=0 actors AND knocked players
        living: list[str] = []
        for tid in order:
            c = _find_combatant(combatants, tid)
            if not c:
                continue
            if int(c.get("hp_current", 0) or 0) <= 0:
                continue
            if c.get("knocked"):
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
    conn: sqlite3.Connection, character_id: int, sheet: dict, reason: str,
    campaign_id: int | None = None,
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
        if campaign_id is not None:
            _save_char_sheet(conn, campaign_id, int(character_id), sheet)
        else:
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
                    _scholar_restore_mana_after_combat(conn, char_id, _sh, "fled", campaign_id=campaign_id)
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
