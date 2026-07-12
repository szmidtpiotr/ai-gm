"""Power Score — deterministyczna miara siły postaci (BL-A5 #1331).

Ekwiwalent "item level" liczony z DANYCH, które już mamy: poziom + wyekwipowana
broń + pancerz + rangi umiejętności bojowych + czary + relikty (#1302). Poziom sam
w sobie to zły miernik (spotkania raz za łatwe, raz za trudne) — budżet spotkań
BL-A2 (#1328) przechodzi z f(level) na f(power).

    power = level
          + avg_weapon_damage / 2         (wyekwipowana broń głównej ręki)
          + armor_reduction               (suma ac_bonus wyekwipowanego pancerza)
          + sum(combat_skill_ranks) / 3   (attack, dodge, two_handed, initiative)
          + max_spell_tier                (najwyższy tier znanego czaru)
          + relic_bonus / 2               (statyczne modyfikatory statów #1302)

Wszystkie składniki mnożone przez wagi z `game_config_meta` (klucz
`power_score_weights`, JSON) — strojenie bez deployu. Wagi domyślne = 1.0
(Numbers Policy: startowe, tuning w Sandboxie na klonach [SBX]).

Power NIE jest pokazywany graczowi (v1) — tylko admin (monitor kampanii → Przegląd)
i raport Sandboxa dla tuningu.
"""
from __future__ import annotations

import json
import sqlite3
from typing import Any

import structlog

logger = structlog.get_logger()

# Umiejętności bojowe wliczane do power (sheet_json.skills → rangi 0..N).
COMBAT_SKILL_KEYS = ("attack", "dodge", "two_handed", "initiative")

# Wagi domyślne (STARTING VALUES) — nadpisywalne z game_config_meta.power_score_weights.
DEFAULT_WEIGHTS: dict[str, float] = {
    "level": 1.0,
    "weapon": 1.0,   # × (avg_weapon_damage / 2)
    "armor": 1.0,    # × armor_reduction
    "skills": 1.0,   # × (sum_combat_ranks / 3)
    "spell": 1.0,    # × max_spell_tier
    "relic": 1.0,    # × (relic_stat_points / 2)
}


def _avg_die(die_str: Any) -> float:
    """Średni wynik zapisu kości 'NdM(+K)' (np. '2d6+1' → 8.0). '' / błąd → 0."""
    s = str(die_str or "").strip().lower()
    if not s:
        return 0.0
    bonus = 0
    if "+" in s:
        s, _, b = s.partition("+")
        try:
            bonus = int(b)
        except ValueError:
            bonus = 0
    try:
        n, _, m = s.partition("d")
        n_i = int(n) if n else 1
        m_i = int(m) if m else 0
    except (ValueError, TypeError):
        return float(bonus)
    if m_i <= 0:
        return float(bonus)
    return n_i * (m_i + 1) / 2.0 + bonus


def get_power_weights(conn: sqlite3.Connection) -> dict[str, float]:
    """Wagi z game_config_meta.power_score_weights (JSON) scalone z domyślnymi."""
    weights = dict(DEFAULT_WEIGHTS)
    try:
        row = conn.execute(
            "SELECT value FROM game_config_meta WHERE key = 'power_score_weights' LIMIT 1"
        ).fetchone()
    except sqlite3.OperationalError:
        return weights
    if not row or not row[0]:
        return weights
    try:
        raw = json.loads(row[0])
    except (ValueError, TypeError):
        return weights
    if isinstance(raw, dict):
        for k in weights:
            if k in raw:
                try:
                    weights[k] = float(raw[k])
                except (TypeError, ValueError):
                    pass
    return weights


def _equipped_weapon_avg_damage(conn: sqlite3.Connection, character_id: int) -> float:
    """Średnie obrażenia wyekwipowanej broni głównej ręki (fallback: dowolna założona)."""
    for where in (
        "AND LOWER(TRIM(COALESCE(ci.slot, ''))) = 'main_hand'",
        "",
    ):
        try:
            row = conn.execute(
                f"""
                SELECT gcw.damage_die
                FROM character_inventory ci
                JOIN game_config_weapons gcw ON gcw.key = ci.weapon_key
                WHERE ci.character_id = ? AND ci.equipped = 1 {where}
                ORDER BY ci.id LIMIT 1
                """,
                (character_id,),
            ).fetchone()
        except sqlite3.OperationalError:
            return 0.0
        if row and row[0]:
            return _avg_die(row[0])
    return 0.0


def _equipped_armor_reduction(conn: sqlite3.Connection, character_id: int) -> float:
    """Redukcja z wyekwipowanego pancerza = suma ac_bonus założonych itemów.

    Broń/relikty gracza używają `ac_bonus` (płaska redukcja ponad nieopancerzony
    próg AC 10) — to bezpośredni odpowiednik `max(0, ac_base − 10)` ze spec #1331.
    """
    try:
        row = conn.execute(
            """
            SELECT COALESCE(SUM(gci.ac_bonus), 0)
            FROM character_inventory ci
            JOIN game_config_items gci ON gci.key = ci.item_key
            WHERE ci.character_id = ? AND ci.equipped = 1
            """,
            (character_id,),
        ).fetchone()
    except sqlite3.OperationalError:
        return 0.0
    return max(0.0, float(row[0] or 0)) if row else 0.0


def _max_spell_tier(conn: sqlite3.Connection, character_id: int) -> int:
    """Najwyższy tier znanego czaru (character_spells ⋈ game_config_spells)."""
    try:
        row = conn.execute(
            """
            SELECT COALESCE(MAX(gs.tier), 0)
            FROM character_spells cs
            JOIN game_config_spells gs ON gs.key = cs.spell_key
            WHERE cs.character_id = ?
            """,
            (character_id,),
        ).fetchone()
    except sqlite3.OperationalError:
        return 0
    try:
        return int(row[0] or 0) if row else 0
    except (TypeError, ValueError):
        return 0


def _relic_stat_points(conn: sqlite3.Connection, character_id: int) -> int:
    """Suma statycznych modyfikatorów statów z założonych reliktów (#1302)."""
    try:
        from app.services.equipment_effects_service import get_effective_stat_bonuses
        bonuses = get_effective_stat_bonuses(character_id, conn)
    except Exception:
        return 0
    return sum(int(v or 0) for v in bonuses.values())


def _combat_skill_ranks(sheet: dict) -> int:
    """Suma rang umiejętności bojowych z karty (attack/dodge/two_handed/initiative)."""
    skills = sheet.get("skills") if isinstance(sheet, dict) else None
    if not isinstance(skills, dict):
        return 0
    total = 0
    for k in COMBAT_SKILL_KEYS:
        try:
            total += int(skills.get(k, 0) or 0)
        except (TypeError, ValueError):
            continue
    return total


def compute_power_score(
    conn: sqlite3.Connection, character_id: int, sheet: dict | None = None
) -> dict:
    """Power Score bohatera + rozbicie na składniki (BL-A5 #1331).

    `sheet` opcjonalne — gdy None, wczytywane z characters.sheet_json. Zwraca
    ``{"score": float, "breakdown": {...}, "weights": {...}}``. Nigdy nie rzuca —
    braki danych → składnik 0 (goły bohater lvl 1 → power ≈ 1).
    """
    if sheet is None:
        try:
            row = conn.execute(
                "SELECT sheet_json FROM characters WHERE id = ?", (character_id,)
            ).fetchone()
            sheet = json.loads((row[0] if row else None) or "{}")
        except Exception:
            sheet = {}

    try:
        level = max(1, int(sheet.get("level") or 1))
    except (TypeError, ValueError):
        level = 1

    avg_wpn = _equipped_weapon_avg_damage(conn, character_id)
    armor = _equipped_armor_reduction(conn, character_id)
    skill_ranks = _combat_skill_ranks(sheet)
    max_tier = _max_spell_tier(conn, character_id)
    relic_pts = _relic_stat_points(conn, character_id)

    w = get_power_weights(conn)
    parts = {
        "level": w["level"] * level,
        "weapon": w["weapon"] * (avg_wpn / 2.0),
        "armor": w["armor"] * armor,
        "skills": w["skills"] * (skill_ranks / 3.0),
        "spell": w["spell"] * max_tier,
        "relic": w["relic"] * (relic_pts / 2.0),
    }
    score = round(sum(parts.values()), 1)
    return {
        "score": score,
        "breakdown": {
            "level": level,
            "avg_weapon_damage": round(avg_wpn, 2),
            "armor_reduction": round(armor, 2),
            "combat_skill_ranks": skill_ranks,
            "max_spell_tier": max_tier,
            "relic_stat_points": relic_pts,
            "weighted": {k: round(v, 2) for k, v in parts.items()},
        },
        "weights": w,
    }


def power_score_value(
    conn: sqlite3.Connection, character_id: int, sheet: dict | None = None
) -> float:
    """Sama liczba Power Score (dla ścieżek, którym rozbicie jest zbędne)."""
    return compute_power_score(conn, character_id, sheet)["score"]
