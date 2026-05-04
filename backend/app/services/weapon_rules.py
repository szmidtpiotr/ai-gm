"""Runtime weapon rules for attack type, finesse and two-handed handling (T16)."""

from __future__ import annotations

import sqlite3
from typing import Any

ATTACK_TESTS = frozenset({"melee_attack", "ranged_attack", "spell_attack"})
TWO_HANDED_SKILL_KEYS = ("two_handed", "great_weapon")


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _sheet_stats(sheet: dict[str, Any]) -> dict[str, Any]:
    stats = sheet.get("stats")
    return stats if isinstance(stats, dict) else {}


def _sheet_skills(sheet: dict[str, Any]) -> dict[str, Any]:
    skills = sheet.get("skills")
    return skills if isinstance(skills, dict) else {}


def stat_modifier(sheet: dict[str, Any], stat_key: str) -> int:
    stats = _sheet_stats(sheet)
    return (_safe_int(stats.get(stat_key, 10), 10) - 10) // 2


def is_attack_test(test_name: str | None) -> bool:
    return str(test_name or "").strip().lower() in ATTACK_TESTS


def attack_test_for_weapon_type(weapon_type: str | None) -> str:
    wt = str(weapon_type or "melee").strip().lower()
    if wt == "ranged":
        return "ranged_attack"
    if wt == "spell":
        return "spell_attack"
    return "melee_attack"


def weapon_key_from_sheet(sheet: dict[str, Any]) -> str | None:
    w = sheet.get("equipped_weapon")
    if w:
        return str(w).strip()
    eq = sheet.get("equipped")
    if isinstance(eq, dict) and eq.get("weapon_key"):
        return str(eq["weapon_key"]).strip()
    return None


def _normalize_weapon_row(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if not row:
        return None
    out = dict(row)
    out["weapon_type"] = str(out.get("weapon_type") or "melee").strip().lower() or "melee"
    out["linked_stat"] = str(out.get("linked_stat") or "STR").strip().upper() or "STR"
    out["damage_die"] = str(out.get("damage_die") or "1d6").strip().lower() or "1d6"
    out["finesse"] = bool(int(out.get("finesse") or 0)) if out.get("finesse") is not None else False
    out["two_handed"] = (
        bool(int(out.get("two_handed") or 0)) if out.get("two_handed") is not None else False
    )
    return out


def load_weapon_row(conn: sqlite3.Connection, key: str | None) -> dict[str, Any] | None:
    if not key:
        return None
    try:
        row = conn.execute(
            """
            SELECT key, label, damage_die, linked_stat, weapon_type, two_handed, finesse, range_m
            FROM game_config_weapons
            WHERE key = ?
            """,
            (key,),
        ).fetchone()
    except sqlite3.OperationalError:
        row = conn.execute(
            "SELECT key, label, damage_die, linked_stat FROM game_config_weapons WHERE key = ?",
            (key,),
        ).fetchone()
    return _normalize_weapon_row(row)


def default_weapon_row(conn: sqlite3.Connection) -> dict[str, Any] | None:
    try:
        row = conn.execute(
            """
            SELECT key, label, damage_die, linked_stat, weapon_type, two_handed, finesse, range_m
            FROM game_config_weapons
            ORDER BY key ASC
            LIMIT 1
            """
        ).fetchone()
    except sqlite3.OperationalError:
        row = conn.execute(
            "SELECT key, label, damage_die, linked_stat FROM game_config_weapons ORDER BY key ASC LIMIT 1"
        ).fetchone()
    return _normalize_weapon_row(row)


def resolve_sheet_weapon(conn: sqlite3.Connection, sheet: dict[str, Any]) -> dict[str, Any] | None:
    return load_weapon_row(conn, weapon_key_from_sheet(sheet)) or default_weapon_row(conn)


def effective_attack_stat_for_weapon(sheet: dict[str, Any], weapon_row: dict[str, Any] | None) -> str:
    if not weapon_row:
        return "STR"
    wt = str(weapon_row.get("weapon_type") or "melee").lower()
    if wt == "ranged":
        return "DEX"
    if wt == "spell":
        return "INT"
    if bool(weapon_row.get("finesse")):
        return "DEX" if stat_modifier(sheet, "DEX") > stat_modifier(sheet, "STR") else "STR"
    return "STR"


def effective_damage_stat_for_weapon(sheet: dict[str, Any], weapon_row: dict[str, Any] | None) -> str:
    if not weapon_row:
        return "STR"
    linked = str(weapon_row.get("linked_stat") or "STR").upper()
    if bool(weapon_row.get("finesse")) and linked in {"STR", "DEX"}:
        return "DEX" if stat_modifier(sheet, "DEX") > stat_modifier(sheet, "STR") else "STR"
    return linked


def two_handed_attack_modifier(sheet: dict[str, Any], weapon_row: dict[str, Any] | None) -> int:
    if not weapon_row or not bool(weapon_row.get("two_handed")):
        return 0
    skills = _sheet_skills(sheet)
    rank = 0
    for key in TWO_HANDED_SKILL_KEYS:
        rank = max(rank, _safe_int(skills.get(key, 0), 0))
    # Conservative MVP rule for T16:
    # - no training with 2H weapon => noticeable penalty
    # - any training => small accuracy bonus
    return 1 if rank > 0 else -2


def resolve_attack_roll_for_weapon(
    sheet: dict[str, Any],
    *,
    raw_roll: int,
    weapon_row: dict[str, Any] | None,
) -> dict[str, Any]:
    raw = max(1, min(20, _safe_int(raw_roll, 1)))
    test = attack_test_for_weapon_type(weapon_row.get("weapon_type") if weapon_row else None)
    attack_stat = effective_attack_stat_for_weapon(sheet, weapon_row)
    stat_mod = stat_modifier(sheet, attack_stat)
    skills = _sheet_skills(sheet)
    skill_rank = _safe_int(skills.get(test, 0), 0)
    proficiency = 2 if skill_rank >= 3 else 0
    weapon_bonus = two_handed_attack_modifier(sheet, weapon_row)
    modifier = stat_mod + skill_rank + proficiency + weapon_bonus
    total = raw + modifier
    return {
        "test": test,
        "raw": raw,
        "attack_stat": attack_stat,
        "stat_mod": stat_mod,
        "skill_rank": skill_rank,
        "proficiency": proficiency,
        "weapon_bonus": weapon_bonus,
        "modifier": modifier,
        "total": total,
        "roll_type": "attack",
        "is_nat20": raw == 20,
        "is_nat1": raw == 1,
        "weapon_key": str(weapon_row.get("key") or "") if weapon_row else "",
        "weapon_label": str(weapon_row.get("label") or "") if weapon_row else "",
        "weapon_type": str(weapon_row.get("weapon_type") or "melee") if weapon_row else "melee",
        "damage_stat": effective_damage_stat_for_weapon(sheet, weapon_row),
        "two_handed": bool(weapon_row.get("two_handed")) if weapon_row else False,
        "finesse": bool(weapon_row.get("finesse")) if weapon_row else False,
    }
