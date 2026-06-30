"""Runtime weapon rules for attack type, finesse and two-handed handling (T16)."""

from __future__ import annotations

import sqlite3
from typing import Any

from app.services.dice import DICE_TEST_TO_CONFIG_SKILL_KEY

ATTACK_TESTS = frozenset({"melee_attack", "ranged_attack", "spell_attack"})
TWO_HANDED_SKILL_KEYS = ("two_handed", "great_weapon")

# ─── Dual-wield (#598) ───────────────────────────────────────────────────────
# Mechanika walki dwoma broniami, klasyfikowana wg PARY (main + off):
#   • dwie LEKKIE bronie + skill `dual_wield` rank≥1 → drugi atak off-hand
#   • dowolna broń + druga broń (nie-2-lekkie)        → parowanie (+obrona)
#   • pusta off-hand / tarcza (nie-broń) / 2H w main  → brak (1 atak jak dziś)
DUAL_WIELD_SKILL_KEY = "dual_wield"
PARRY_DEFENSE_BONUS = 2  # STARTING value, Sandbox-tunable (#598)


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


def _normalize_catalog_weapon_key(raw: str | None) -> str | None:
    """Inventory sometimes stores `weapon_shortbow`; catalog keys are `shortbow`."""
    if not raw:
        return None
    s = str(raw).strip()
    if not s:
        return None
    low = s.lower()
    if low.startswith("weapon_") and len(s) > 7:
        return s[7:].strip() or None
    return s


def weapon_key_from_inventory(conn: sqlite3.Connection, character_id: int) -> str | None:
    """Equipped weapon in main hand from Phase 8E inventory (not mirrored in sheet_json)."""
    try:
        row = conn.execute(
            """
            SELECT weapon_key FROM character_inventory
            WHERE character_id = ?
              AND COALESCE(equipped, 0) = 1
              AND LOWER(TRIM(COALESCE(slot, ''))) = 'main_hand'
              AND weapon_key IS NOT NULL
              AND TRIM(weapon_key) != ''
            ORDER BY id ASC
            LIMIT 1
            """,
            (int(character_id),),
        ).fetchone()
    except sqlite3.OperationalError:
        return None
    if not row or row["weapon_key"] is None:
        return None
    return str(row["weapon_key"]).strip() or None


def offhand_weapon_key_from_inventory(conn: sqlite3.Connection, character_id: int) -> str | None:
    """Equipped weapon in OFF hand (#598). Mirror of :func:`weapon_key_from_inventory`,
    slot = 'off_hand'. Zwraca None gdy off-hand pusty albo trzyma nie-broń (tarczę)."""
    try:
        row = conn.execute(
            """
            SELECT weapon_key FROM character_inventory
            WHERE character_id = ?
              AND COALESCE(equipped, 0) = 1
              AND LOWER(TRIM(COALESCE(slot, ''))) = 'off_hand'
              AND weapon_key IS NOT NULL
              AND TRIM(weapon_key) != ''
            ORDER BY id ASC
            LIMIT 1
            """,
            (int(character_id),),
        ).fetchone()
    except sqlite3.OperationalError:
        return None
    if not row or row["weapon_key"] is None:
        return None
    return str(row["weapon_key"]).strip() or None


def is_light_weapon(weapon_row: dict[str, Any] | None) -> bool:
    """Czy broń jest 'lekka' (kwalifikuje się do dual-wield jako jedna z dwóch).

    MVP #598: pochodna `finesse` (sztylet finesse=1 → lekka; miecze nie). Broń
    dwuręczna NIGDY nie jest lekka. Jawna kolumna `light` (gdy kiedyś dodana)
    nadpisuje heurystykę finesse — pozwala adminowi sterować per broń."""
    if not weapon_row:
        return False
    if _safe_int(weapon_row.get("two_handed"), 0):
        return False
    light = weapon_row.get("light")
    if light is not None:
        return bool(_safe_int(light, 0))
    return bool(_safe_int(weapon_row.get("finesse"), 0))


def dual_wield_skill_rank(sheet: dict[str, Any]) -> int:
    """Rank skilla `dual_wield` z karty (0 gdy brak)."""
    return _safe_int(_sheet_skills(sheet).get(DUAL_WIELD_SKILL_KEY, 0), 0)


def classify_dual_combo(
    main_row: dict[str, Any] | None,
    off_row: dict[str, Any] | None,
    dual_wield_rank: int,
) -> str:
    """Klasyfikacja pary broni (#598) → 'dual_attack' | 'parry' | 'none'.

    • brak off-hand (None) lub 2H w main → 'none'
    • dwie lekkie bronie → 'dual_attack' jeśli skill rank≥1, inaczej 'none'
    • każda inna para z bronią w off → 'parry'
    """
    if not off_row:
        return "none"
    if main_row and _safe_int(main_row.get("two_handed"), 0):
        return "none"
    if is_light_weapon(main_row) and is_light_weapon(off_row):
        return "dual_attack" if int(dual_wield_rank or 0) >= 1 else "none"
    return "parry"


def player_dual_combo_for_character(
    conn: sqlite3.Connection,
    character_id: int,
    sheet: dict[str, Any],
) -> tuple[str, dict[str, Any] | None, dict[str, Any] | None]:
    """Rozwiąż parę broni gracza z karty+ekwipunku → (combo, main_row, off_row)."""
    main_key = weapon_key_from_sheet(sheet)
    if not main_key:
        main_key = _normalize_catalog_weapon_key(weapon_key_from_inventory(conn, int(character_id)))
    off_key = _normalize_catalog_weapon_key(offhand_weapon_key_from_inventory(conn, int(character_id)))
    main_row = load_weapon_row(conn, main_key) if main_key else None
    off_row = load_weapon_row(conn, off_key) if off_key else None
    combo = classify_dual_combo(main_row, off_row, dual_wield_skill_rank(sheet))
    return combo, main_row, off_row


def parry_defense_bonus(
    conn: sqlite3.Connection,
    character_id: int,
    sheet: dict[str, Any],
) -> int:
    """Bonus do obrony gracza z parowania (#598). PARRY_DEFENSE_BONUS gdy combo=='parry', inaczej 0."""
    combo, _, _ = player_dual_combo_for_character(conn, int(character_id), sheet)
    return PARRY_DEFENSE_BONUS if combo == "parry" else 0


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
    from app.services.game_items_service import get_weapon_row
    row = get_weapon_row(conn, key)
    if row:
        return _normalize_weapon_row(row)
    # Fallback: stara tabela (dla broni stworzonych przez LLM jeszcze nie backfillowanych — U11c naprawi)
    try:
        old = conn.execute(
            "SELECT key, label, damage_die, linked_stat, weapon_type, two_handed, finesse, range_m, effect_json FROM game_config_weapons WHERE key = ?",
            (key,),
        ).fetchone()
    except sqlite3.OperationalError:
        try:
            old = conn.execute(
                "SELECT key, label, damage_die, linked_stat, weapon_type, two_handed, finesse, range_m FROM game_config_weapons WHERE key = ?",
                (key,),
            ).fetchone()
        except sqlite3.OperationalError:
            old = conn.execute(
                "SELECT key, label, damage_die, linked_stat FROM game_config_weapons WHERE key = ?",
                (key,),
            ).fetchone()
    return _normalize_weapon_row(old)


def default_weapon_row(conn: sqlite3.Connection) -> dict[str, Any] | None:
    """Fallback weapon used when nothing is equipped — barehand strike.

    Prefers a catalog row keyed 'unarmed' (so admins can balance the die / linked_stat).
    Falls back to a hardcoded d3 STR melee strike if no row exists.
    """
    from app.services.game_items_service import get_weapon_row
    row = get_weapon_row(conn, "unarmed")
    if row:
        return _normalize_weapon_row(row)
    # Fallback: stara tabela lub hardcoded
    try:
        old = conn.execute(
            """
            SELECT key, label, damage_die, linked_stat, weapon_type, two_handed, finesse, range_m
            FROM game_config_weapons
            WHERE key = 'unarmed' AND is_active = 1
            LIMIT 1
            """
        ).fetchone()
    except sqlite3.OperationalError:
        old = conn.execute(
            "SELECT key, label, damage_die, linked_stat FROM game_config_weapons WHERE key = 'unarmed' LIMIT 1"
        ).fetchone()
    if old:
        return _normalize_weapon_row(old)
    # Hardcoded last-ditch fallback (kept tiny so it's clearly worse than any real weapon).
    return _normalize_weapon_row({
        "key": "unarmed",
        "label": "Pięści",
        "damage_die": "1d3",
        "linked_stat": "STR",
        "weapon_type": "melee",
        "two_handed": 0,
        "finesse": 0,
        "range_m": None,
    })


def resolve_sheet_weapon(
    conn: sqlite3.Connection,
    sheet: dict[str, Any],
    character_id: int | None = None,
) -> dict[str, Any] | None:
    key = weapon_key_from_sheet(sheet)
    if not key and character_id is not None:
        inv_raw = weapon_key_from_inventory(conn, int(character_id))
        key = _normalize_catalog_weapon_key(inv_raw)
    row = load_weapon_row(conn, key) if key else None
    return row or default_weapon_row(conn)


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
    _canon = DICE_TEST_TO_CONFIG_SKILL_KEY.get(test, test)
    skill_rank = _safe_int(skills.get(test) or skills.get(_canon, 0), 0)
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
