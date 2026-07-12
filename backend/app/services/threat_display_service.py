"""BL-A7 (#1344) — relatywny wskaźnik zagrożenia dla gracza.

Companion Power Score (#1331) + Bestiariusza (#1191). Przy pojawieniu się wrogów
w walce ŻAR pokazuje graczowi kartę: obrazek + nazwa + wskaźnik 🟢/🟡/🔴/💀 — by
świadomie zdecydował walczyć czy uciekać.

Zasada projektowa (utrwalona #1344): staty wroga są STAŁE — wskaźnik NIE jest
rubber-bandingiem. Porównuje stały statblock grupy (bazowy rekord
`game_config_enemies`, nie ranked combatant) do rosnącego Power Score gracza:

    ratio = Σ enemy_threat_value(base_stat) × liczebność  /  threat_budget_for_power(power)

Reużywa `encounter_service.enemy_threat_value` + `threat_budget_for_power` +
`power_service.compute_power_score` (przez `_hero_power_for_campaign`).

Zwraca glyph + label + tier; **surowy ratio/threat NIE trafia do gracza** (parytet
z ukrytym Power Score). Progi to STARTING VALUES w
`game_config_meta.threat_indicator_bands` — strojenie w Sandboxie bez deployu.
"""
from __future__ import annotations

import json
import sqlite3

import structlog

from app.services.encounter_service import (
    _hero_power_for_campaign,
    enemy_threat_value,
    threat_budget_for_power,
)

logger = structlog.get_logger()

# Pasma STARTOWE (Numbers Policy) — nadpisywalne z game_config_meta.threat_indicator_bands.
# `max` = górna granica ratio (wyłączna); None = ostatnie pasmo (bez sufitu).
DEFAULT_BANDS: list[dict] = [
    {"tier": "trivial", "max": 0.5, "glyph": "🟢", "label": "słaby"},
    {"tier": "even", "max": 0.9, "glyph": "🟡", "label": "wyrównany"},
    {"tier": "dangerous", "max": 1.4, "glyph": "🔴", "label": "groźny"},
    {"tier": "deadly", "max": None, "glyph": "💀", "label": "zabójczy"},
]


def get_threat_bands(conn: sqlite3.Connection) -> list[dict]:
    """Pasma wskaźnika z game_config_meta.threat_indicator_bands (JSON) lub domyślne.

    Znormalizowane i posortowane rosnąco po `max` (None = na końcu). Każdy błąd /
    brak → DEFAULT_BANDS (zero regresji przy pustej / zepsutej konfiguracji).
    """
    bands: list[dict] | None = None
    try:
        row = conn.execute(
            "SELECT value FROM game_config_meta WHERE key = 'threat_indicator_bands' LIMIT 1"
        ).fetchone()
    except sqlite3.OperationalError:
        row = None
    if row and row[0]:
        try:
            raw = json.loads(row[0])
        except (ValueError, TypeError):
            raw = None
        if isinstance(raw, list) and raw:
            parsed = []
            for b in raw:
                if not isinstance(b, dict):
                    continue
                mx = b.get("max")
                if mx in (None, "", "inf", "null"):
                    mx = None
                else:
                    try:
                        mx = float(mx)
                    except (TypeError, ValueError):
                        continue
                parsed.append(
                    {
                        "tier": str(b.get("tier") or "?"),
                        "max": mx,
                        "glyph": str(b.get("glyph") or "❓"),
                        "label": str(b.get("label") or ""),
                    }
                )
            if parsed:
                bands = parsed
    if bands is None:
        bands = [dict(b) for b in DEFAULT_BANDS]
    # Sortuj rosnąco po `max`; None (brak sufitu) zawsze ostatnie.
    bands.sort(key=lambda b: (b["max"] is None, b["max"] if b["max"] is not None else 0.0))
    return bands


def _band_for_ratio(bands: list[dict], ratio: float) -> dict:
    for b in bands:
        mx = b.get("max")
        if mx is None or ratio < mx:
            return b
    return bands[-1]


def _stable_enemy_stat(conn: sqlite3.Connection, combatant: dict) -> dict:
    """STAŁY statblock wroga do wyceny zagrożenia.

    Preferuj bazowy rekord `game_config_enemies` po `enemy_key` (niezmienny —
    wskaźnik nie rubber-banduje z rangami/buffami combatanta). Fallback: pola
    combatanta gdy brak klucza/rekordu (lepiej zaniżyć niż wywrócić kartę).
    """
    key = str(combatant.get("enemy_key") or "").strip()
    if key:
        try:
            row = conn.execute(
                "SELECT hp_base, ac_base, attack_bonus, damage_die, "
                "COALESCE(damage_bonus, 0) AS damage_bonus, "
                "COALESCE(attacks_per_turn, 1) AS attacks_per_turn "
                "FROM game_config_enemies WHERE key = ? LIMIT 1",
                (key,),
            ).fetchone()
        except sqlite3.OperationalError:
            row = None
        if row:
            return {
                "hp_base": row["hp_base"],
                "ac_base": row["ac_base"],
                "attack_bonus": row["attack_bonus"],
                "damage_die": row["damage_die"],
                "damage_bonus": row["damage_bonus"],
                "attacks_per_turn": row["attacks_per_turn"],
            }
    return {
        "hp_base": combatant.get("hp_max") or combatant.get("hp_current") or 1,
        "ac_base": combatant.get("defense") or 10,
        "attack_bonus": combatant.get("attack_bonus") or 0,
        "damage_die": combatant.get("damage_dice") or combatant.get("damage_die") or "d6",
        "damage_bonus": combatant.get("damage_bonus") or 0,
        "attacks_per_turn": combatant.get("attacks_per_turn") or 1,
    }


def relative_threat(
    conn: sqlite3.Connection, campaign_id: int, enemies: list[dict]
) -> dict | None:
    """Sumaryczny relatywny wskaźnik zagrożenia grupy wrogów (BL-A7 #1344).

    `enemies` = lista combatantów-wrogów (dict, jak w snapshotcie walki). Liczy
    całą grupę (sumaryczny wskaźnik, nie per-sztuka). Zwraca:

        {glyph, label, tier, ratio, enemy_threat, budget, count}

    `ratio/enemy_threat/budget` służą TYLKO backendowi / Sandboxowi / testom —
    caller (snapshot walki) MUSI je odfiltrować przed wysłaniem graczowi. None gdy
    lista pusta. Nigdy nie rzuca — błąd danych → składnik 0.
    """
    total_threat = 0.0
    count = 0
    for e in enemies or []:
        if not isinstance(e, dict):
            continue
        count += 1
        total_threat += enemy_threat_value(_stable_enemy_stat(conn, e))
    if count == 0:
        return None

    power = _hero_power_for_campaign(conn, campaign_id, fallback_level=1)
    if power is None:
        power = 1.0
    budget = max(1.0, float(threat_budget_for_power(conn, power)))
    ratio = total_threat / budget

    bands = get_threat_bands(conn)
    band = _band_for_ratio(bands, ratio)
    return {
        "glyph": band["glyph"],
        "label": band["label"],
        "tier": band["tier"],
        "ratio": round(ratio, 3),
        "enemy_threat": round(total_threat, 2),
        "budget": round(budget, 2),
        "count": count,
    }
