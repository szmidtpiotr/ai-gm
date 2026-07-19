"""S7 (#601) — Gamble: hazard z prawdziwą stawką złota.

Mechanika decyduje, LLM narruje (Zasady CZĘŚĆ 10). Gra w kości/karty to test
umiejętności ``gamble`` (CHA): jego stopień wyniku (S1) mapuje się na NETTO
przepływu złota względem zadeklarowanej stawki. Stawkę podaje GRACZ, ale waliduje
ją mechanika (≥1 gp, ≤ aktualne złoto — wzorzec [SPEND_GOLD] F4 / zasada C12/F4:
kwoty z mechaniki, nie z LLM). Złoto przelewa centralna ``change_gold`` (U26).

Stan żyje w ``session_flags`` (game_sessions):
  * licznik gier per scena/lokacja (anti-abuse, max 3) — reset automatyczny przy
    zmianie ``location_key`` (porównanie zapisanego ``gamble_scene_loc``),
  * jednorazowy sygnał ``gamble_cheat_accused`` (krytyczna porażka → narrator
    wspomina o oskarżeniu o oszustwo).

Wszystkie liczby to WARTOŚCI STARTOWE (Numbers Policy) — do tuningu po S20.
"""
from __future__ import annotations

from typing import Any

# session_flags keys
_FLAG_COUNT = "gamble_scene_count"   # int: gry rozegrane w bieżącej scenie/lokacji
_FLAG_LOC = "gamble_scene_loc"       # str: lokacja, do której licznik się odnosi
_FLAG_CHEAT = "gamble_cheat_accused" # bool: oskarżenie o oszustwo (sygnał dla narratora)
_FLAG_DAY = "gamble_day"             # int: dzień gry, do którego odnosi się dzienny licznik
_FLAG_DAY_COUNT = "gamble_day_count" # int: gry rozegrane w bieżącym dniu gry (survives bounce)

# Anti-abuse + walidacja stawki (Numbers Policy).
MAX_GAMBLES_PER_SCENE = 3
# AUDIT #1445: per-scene limit resetuje się przy zmianie location_key → chodzenie tam
# i z powrotem kasowało licznik (farm hazardu). Dzienny licznik (klucz = dzień gry,
# nie lokacja) przeżywa „location bounce”. Wartość startowa, tuner w Sandboxie.
MAX_GAMBLES_PER_DAY = 5
MIN_STAKE = 1


def _game_day(session_flags: dict) -> int:
    """Dzień gry z zegara zapisanego w session_flags (ingame_hours). Bez zależności od
    clock_service — funkcje hazardu i tak dostają session_flags."""
    try:
        return int(session_flags.get("ingame_hours", 0) or 0) // 24 + 1
    except (TypeError, ValueError):
        return 1

# Stopień testu (S1) → mnożnik NETTO względem stawki. Design doc / CZĘŚĆ AI S7:
# sukces +stawka, krytyczny +2×stawka, porażka −stawka, krytyczna porażka −stawka.
_PAYOUT_MULT: dict[str, float] = {
    "CRITICAL_SUCCESS": 2.0,
    "SUCCESS": 1.0,
    "FAILURE": -1.0,
    "CRITICAL_FAILURE": -1.0,
}


# ── Walidacja stawki ──────────────────────────────────────────────────────────

def validate_stake(raw: Any, current_gold: int) -> tuple[int, str | None]:
    """Zwaliduj zadeklarowaną stawkę. Zwraca ``(stake, error|None)``.

    Reguły (CZĘŚĆ AI S7): stawka całkowita, ≥ ``MIN_STAKE``, ≤ aktualne złoto.
    Błędy: ``invalid_stake`` / ``stake_below_min`` / ``stake_exceeds_gold``.
    """
    try:
        stake = int(raw)
    except (TypeError, ValueError):
        return 0, "invalid_stake"
    if stake < MIN_STAKE:
        return 0, "stake_below_min"
    if stake > int(current_gold or 0):
        return 0, "stake_exceeds_gold"
    return stake, None


# ── Wypłata ───────────────────────────────────────────────────────────────────

def payout_delta(outcome: str, stake: int) -> int:
    """Netto przepływu złota dla stopnia testu (S1). Nieznany stopień = strata
    (bezpieczny default — gracz nigdy nie zyskuje na błędnym stanie)."""
    mult = _PAYOUT_MULT.get(str(outcome or "").upper(), -1.0)
    return int(round(mult * int(stake)))


def is_cheat_outcome(outcome: str) -> bool:
    """Czy stopień wyniku rodzi oskarżenie o oszustwo (krytyczna porażka)."""
    return str(outcome or "").upper() == "CRITICAL_FAILURE"


# ── Limit gier na scenę/lokację (anti-abuse) ─────────────────────────────────

def gamble_count(session_flags: dict, location_key: str | None) -> int:
    """Liczba gier rozegranych w bieżącej lokacji. Inna lokacja niż zapisana =
    nowa scena → licznik liczony od zera (reset automatyczny)."""
    if str(session_flags.get(_FLAG_LOC) or "") != str(location_key or ""):
        return 0
    try:
        return int(session_flags.get(_FLAG_COUNT) or 0)
    except (TypeError, ValueError):
        return 0


def gamble_day_count(session_flags: dict) -> int:
    """Liczba gier rozegranych w bieżącym dniu gry (0 gdy zapisany dzień jest inny)."""
    if int(session_flags.get(_FLAG_DAY) or 0) != _game_day(session_flags):
        return 0
    try:
        return int(session_flags.get(_FLAG_DAY_COUNT) or 0)
    except (TypeError, ValueError):
        return 0


def can_gamble(session_flags: dict, location_key: str | None) -> bool:
    """Czy gracz może jeszcze zagrać: limit per scena ORAZ dzienny (AUDIT #1445 —
    dzienny cap nie resetuje się przy zmianie lokacji)."""
    return (
        gamble_count(session_flags, location_key) < MAX_GAMBLES_PER_SCENE
        and gamble_day_count(session_flags) < MAX_GAMBLES_PER_DAY
    )


def record_gamble(session_flags: dict, location_key: str | None) -> int:
    """Podbij licznik gier dla bieżącej lokacji ORAZ dzienny (mutacja in-place)."""
    cur = gamble_count(session_flags, location_key)
    session_flags[_FLAG_LOC] = str(location_key or "")
    session_flags[_FLAG_COUNT] = cur + 1
    # AUDIT #1445: dzienny licznik przeżywa bounce między lokacjami.
    day = _game_day(session_flags)
    day_cur = gamble_day_count(session_flags)
    session_flags[_FLAG_DAY] = day
    session_flags[_FLAG_DAY_COUNT] = day_cur + 1
    return cur + 1


# ── Sygnał oskarżenia o oszustwo (jednorazowy, dla narratora) ────────────────

def consume_cheat_accusation(session_flags: dict) -> bool:
    """Zwróć i wyczyść sygnał oskarżenia o oszustwo (krytyczna porażka)."""
    val = bool(session_flags.get(_FLAG_CHEAT))
    session_flags.pop(_FLAG_CHEAT, None)
    return val


# ── Domknięcie wyniku gry ─────────────────────────────────────────────────────

def apply_gamble_outcome(
    session_flags: dict, outcome: str, stake: int, location_key: str | None
) -> dict:
    """Policz netto, podbij licznik i ustaw sygnał oszustwa (mutacja in-place).

    Złota NIE rusza — to robi wołający przez ``change_gold`` na podstawie
    zwróconego ``delta`` (U26 chokepoint). Zwraca podsumowanie dla logów/UI.
    """
    delta = payout_delta(outcome, stake)
    record_gamble(session_flags, location_key)
    cheat = is_cheat_outcome(outcome)
    if cheat:
        session_flags[_FLAG_CHEAT] = True
    return {"delta": delta, "stake": int(stake), "cheat_accused": cheat}
