"""Fatigue (zmęczenie) — PT-D1 (#1124).

Podróż nabija zmęczenie na istniejącej, stackowalnej kondycji `exhausted`.
Wszystkie liczby (progi, kary) żyją w game_config_conditions.exhausted.effect_json
(Numbers Policy — wartości startowe, Sandbox-tunable). Ten serwis TYLKO je czyta.

Data-driven (Zasada 1 FAZY S): żadnego ``if key == "exhausted"``. Kondycja „zmęczeniowa"
= dowolna kondycja z efektem ``stacking_levels``, którego ``per_level_effects`` zawiera
prymityw ``test_penalty``. Nowe prymitywy (czytane wyłącznie tutaj + w miejscach użycia):

- ``test_penalty``      (per_level_effects)  — kara do sumy testu umiejętności, ×poziom.
- ``initiative_penalty`` (threshold_effects)  — kara do rzutu inicjatywy od danego poziomu.
- ``regen_multiplier``   (threshold_effects)  — mnożnik regeneracji HP/many przy odpoczynku.

Krasnolud („twardy jak kamień", #969) ignoruje kary 1. stacka: dla wyliczenia kar
poziom efektywny = poziom − 1 (min 0). Stacki liczą się normalnie (nabijanie/czyszczenie).
"""
from __future__ import annotations

import json
from typing import Any

# Klucze prymitywów zmęczenia — publiczne, żeby migracja/silnik używały tych samych stringów.
TEST_PENALTY = "test_penalty"
INITIATIVE_PENALTY = "initiative_penalty"
REGEN_MULTIPLIER = "regen_multiplier"

_DWARF_RACES = {"dwarf", "krasnolud"}


def _decode(effect_json: Any) -> dict:
    if isinstance(effect_json, dict):
        return effect_json
    try:
        parsed = json.loads(effect_json or "{}")
        return parsed if isinstance(parsed, dict) else {}
    except (TypeError, ValueError):
        return {}


def _stacking_effect(cond: dict) -> dict | None:
    """Zwraca efekt ``stacking_levels`` niosący prymityw ``test_penalty`` (kondycja zmęczeniowa)."""
    if not isinstance(cond, dict):
        return None
    for ef in _decode(cond.get("effect_json")).get("effects") or []:
        if not isinstance(ef, dict):
            continue
        if str(ef.get("type") or "").lower() != "stacking_levels":
            continue
        for ple in ef.get("per_level_effects") or []:
            if isinstance(ple, dict) and str(ple.get("type") or "").lower() == TEST_PENALTY:
                return ef
    return None


def _level(cond: dict) -> int:
    try:
        return max(1, int((cond.get("runtime") or {}).get("level", 1)))
    except (TypeError, ValueError):
        return 1


def _is_dwarf(race: Any) -> bool:
    return str(race or "").strip().lower() in _DWARF_RACES


def _effective_level(level: int, race: Any) -> int:
    """Poziom efektywny do WYLICZENIA KAR (krasnolud ignoruje 1. stack)."""
    if _is_dwarf(race):
        return max(0, level - 1)
    return max(0, level)


# ── Odczyt stanu ─────────────────────────────────────────────────────────────

def read_fatigue_level(conditions: list[dict] | None) -> int:
    """Najwyższy poziom aktywnej kondycji zmęczeniowej (0 = brak)."""
    best = 0
    for cond in conditions or []:
        if _stacking_effect(cond) is not None:
            best = max(best, _level(cond))
    return best


# ── Kary ─────────────────────────────────────────────────────────────────────

def compute_test_penalty(conditions: list[dict] | None, race: Any = None) -> int:
    """Suma kar do testów umiejętności (≤0). ×poziom efektywny."""
    total = 0
    for cond in conditions or []:
        ef = _stacking_effect(cond)
        if ef is None:
            continue
        lvl = _effective_level(_level(cond), race)
        if lvl <= 0:
            continue
        for ple in ef.get("per_level_effects") or []:
            if isinstance(ple, dict) and str(ple.get("type") or "").lower() == TEST_PENALTY:
                try:
                    total += int(ple.get("value") or 0) * lvl
                except (TypeError, ValueError):
                    pass
    return total


def _threshold_values(conditions: list[dict] | None, primitive: str, race: Any) -> list[float]:
    """Zbiera wartości prymitywu ``primitive`` z progów spełnionych przez poziom efektywny."""
    vals: list[float] = []
    for cond in conditions or []:
        ef = _stacking_effect(cond)
        if ef is None:
            continue
        lvl = _effective_level(_level(cond), race)
        thresholds = ef.get("threshold_effects")
        if not isinstance(thresholds, dict):
            continue
        for k, spec in thresholds.items():
            try:
                need = int(k)
            except (TypeError, ValueError):
                continue
            if lvl < need or not isinstance(spec, dict):
                continue
            if str(spec.get("type") or "").lower() == primitive:
                try:
                    vals.append(float(spec.get("value")))
                except (TypeError, ValueError):
                    pass
    return vals


def compute_initiative_penalty(conditions: list[dict] | None, race: Any = None) -> int:
    """Kara do inicjatywy (≤0). Suma progów spełnionych przez poziom efektywny."""
    vals = _threshold_values(conditions, INITIATIVE_PENALTY, race)
    try:
        return int(sum(vals))
    except (TypeError, ValueError):
        return 0


def compute_regen_multiplier(conditions: list[dict] | None, race: Any = None) -> float:
    """Mnożnik regeneracji HP/many przy odpoczynku (1.0 = pełna). Bierze najgorszy próg."""
    vals = _threshold_values(conditions, REGEN_MULTIPLIER, race)
    return min(vals) if vals else 1.0


# ── Nabijanie / czyszczenie stacków ──────────────────────────────────────────

def bump_fatigue_stack(
    conditions: list[dict] | None, entry_template: dict, *, max_level: int = 3
) -> tuple[list[dict], int]:
    """Podbija poziom kondycji zmęczeniowej o 1 (max ``max_level``) lub nakłada od nowa.

    ``entry_template`` = świeży wpis kondycji (klucz/label/effect_json), zwykle z
    ``combat_service._build_condition_entry(conn, "exhausted", level=1)``.
    Zwraca (nowa_lista_kondycji, poziom_po).
    """
    conds = [c for c in (conditions or []) if isinstance(c, dict)]
    key = str(entry_template.get("key") or "").strip().lower()

    for cond in conds:
        if str(cond.get("key") or "").strip().lower() == key:
            new_level = min(int(max_level), _level(cond) + 1)
            cond.setdefault("runtime", {})["level"] = new_level
            # Upgrade ewentualnego starego wpisu (S9 effect_json) do aktualnego kontraktu PT-D1,
            # żeby kary/progi liczyły się z bieżącej definicji katalogu.
            if entry_template.get("effect_json"):
                cond["effect_json"] = entry_template["effect_json"]
            return conds, new_level

    # brak → nakładamy świeży wpis (poziom z template, min 1)
    fresh = dict(entry_template)
    lvl = _level(fresh)
    fresh.setdefault("runtime", {})["level"] = min(int(max_level), max(1, lvl))
    conds.append(fresh)
    return conds, fresh["runtime"]["level"]


def clear_all_fatigue(conditions: list[dict] | None) -> list[dict]:
    """Usuwa WSZYSTKIE kondycje zmęczeniowe (pełny nocleg). Reszta nietknięta."""
    return [
        c for c in (conditions or [])
        if not (isinstance(c, dict) and _stacking_effect(c) is not None)
    ]


def _max_level_from(entry: dict, fallback: int = 3) -> int:
    ef = _stacking_effect(entry)
    if ef:
        try:
            return int(ef.get("max_level") or fallback)
        except (TypeError, ValueError):
            pass
    return fallback


# ── Wiring: nabicie zmęczenia postaci w DB ───────────────────────────────────

def charge_fatigue(conn, character_id: int, *, campaign_id: int | None = None, reason: str = "") -> int:
    """Nabija +1 stack zmęczenia (exhausted) na postaci i zapisuje sheet. Zwraca poziom po (0 = fail).

    Liczby (max_level, kary) czytane z katalogu game_config_conditions — Numbers Policy.
    """
    import json as _json
    from app.services.combat_service import _build_condition_entry, _conn as _cat_conn

    if not character_id:
        return 0
    try:
        row = conn.execute(
            "SELECT sheet_json FROM characters WHERE id = ? LIMIT 1", (int(character_id),)
        ).fetchone()
    except Exception:
        return 0
    if not row:
        return 0
    raw = row[0] if not hasattr(row, "keys") else row["sheet_json"]
    try:
        sheet = _json.loads(raw or "{}")
    except (TypeError, ValueError):
        return 0
    if not isinstance(sheet, dict):
        return 0

    with _cat_conn() as _cat:
        template = _build_condition_entry(_cat, "exhausted", applied_at=reason or "travel_fatigue")
    if template is None:
        return 0

    conds, level = bump_fatigue_stack(
        sheet.get("conditions") or [], template, max_level=_max_level_from(template)
    )
    sheet["conditions"] = conds
    try:
        conn.execute(
            "UPDATE characters SET sheet_json = ? WHERE id = ?",
            (_json.dumps(sheet, ensure_ascii=False), int(character_id)),
        )
    except Exception:
        return 0
    return level
