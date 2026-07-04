"""In-flight turn lock (#1186) — jedna spójna ochrona przed podwójną turą na serwerze.

Problem: `turns.py` / `gate.py` nie miały żadnego locka in-flight → dwa równoległe
`POST /turns/stream` na tę samą kampanię odpalały dwa calle LLM (podwójny koszt) i
potrafiły zapisać dwie tury. Frontendowy guard (#1171) nie wystarcza — inny tab /
inny klient / mobile / restore go omija.

Model wykonania: backend to POJEDYNCZY worker uvicorn (`Dockerfile`: brak `--workers`).
Endpointy tur to synchroniczne `def` → Starlette uruchamia je w threadpoolu W JEDNYM
procesie. Dlatego wystarczy in-process rejestr chroniony `threading.Lock` — wszystkie
równoległe POSTy tej samej kampanii lądują na wątkach tego samego procesu.

Klucz locka:
  * solo  → per campaign_id                (jedna narracja na kampanię naraz)
  * MP    → per (campaign_id, character_id) (gracze grają równolegle; blokujemy tylko
                                             double-submit tej samej postaci / podwójną
                                             narrację współdzieloną)

Bezpieczeństwo: lock starszy niż `STALE_LOCK_SECONDS` jest uznawany za osierocony
(crash streamu) i odzyskiwany — błąd nie może zabrickować kampanii na zawsze.
Zwolnienie zawsze w `finally` (endpoint) / generator `finally` (ścieżka streamująca).
"""
from __future__ import annotations

import threading
import time

from app.core.logging import get_logger

logger = get_logger(__name__)

# Lock uznany za osierocony po tylu sekundach (crash/zerwany stream) → reclaim.
# Turn LLM + zapis rzadko przekracza kilkadziesiąt s; 180 s to bezpieczny bufor.
STALE_LOCK_SECONDS = 180.0

# key -> monotoniczny znacznik czasu zdobycia locka
_registry: dict[str, float] = {}
_guard = threading.Lock()


class TurnLockBusy(Exception):
    """Tura już w toku dla tej kampanii/postaci — drugi równoległy POST → 409."""

    def __init__(self, key: str):
        self.key = key
        super().__init__(f"turn already in flight: {key}")


def _key(campaign_id: int, character_id: int | None) -> str:
    if character_id is None:
        return f"c:{int(campaign_id)}"
    return f"c:{int(campaign_id)}:ch:{int(character_id)}"


def acquire(campaign_id: int, character_id: int | None = None) -> str:
    """Zdobądź lock. Zwraca klucz (podaj go do `release`).

    Rzuca `TurnLockBusy`, jeśli świeży lock już istnieje. Osierocony (stale) lock
    jest po cichu odzyskiwany — kampania nigdy nie zostaje zabrickowana.
    """
    key = _key(campaign_id, character_id)
    now = time.monotonic()
    with _guard:
        held_at = _registry.get(key)
        if held_at is not None and (now - held_at) < STALE_LOCK_SECONDS:
            raise TurnLockBusy(key)
        if held_at is not None:
            logger.warning("turn_lock_stale_reclaimed", key=key,
                           age_s=round(now - held_at, 1))
        _registry[key] = now
    return key


def acquire_or_409(campaign_id: int, character_id: int | None = None) -> str:
    """Jak `acquire`, ale busy → `HTTPException(409)` (wprost do endpointu)."""
    from fastapi import HTTPException

    try:
        return acquire(campaign_id, character_id)
    except TurnLockBusy:
        raise HTTPException(
            status_code=409,
            detail="Tura już trwa — poczekaj na zakończenie odpowiedzi.",
        )


def release(key: str | None) -> None:
    """Zwolnij lock. Idempotentne (bezpieczne w podwójnym finally)."""
    if not key:
        return
    with _guard:
        _registry.pop(key, None)


# ─── Hooki testowe ───────────────────────────────────────────────────────────

def _reset_for_tests() -> None:
    with _guard:
        _registry.clear()


def _force_age_for_tests(key: str, age_seconds: float) -> None:
    """Cofnij znacznik czasu locka, by udawać osierocony lock (test stale-reclaim)."""
    with _guard:
        if key in _registry:
            _registry[key] = time.monotonic() - age_seconds
