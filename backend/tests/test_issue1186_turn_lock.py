"""TDD: Issue #1186 — serwerowy in-flight turn-lock (blokada podwójnej tury).

Sedno buga: `POST /turns/stream` nie ma żadnego locka in-flight → dwa równoległe
POSTy na tę samą kampanię odpalają dwa calle LLM i potrafią zapisać dwie tury.

Ten plik testuje sam prymityw locka (`app.services.turn_lock`), bo tam żyje cała
nowa logika. Kontrakt:
  * per campaign_id (solo) — drugi acquire tej samej kampanii = busy → 409
  * per (campaign_id, character_id) w MP — różne postaci = niezależne klucze
  * zwolnienie w `finally` NIE zawiesza kampanii (re-acquire działa)
  * stale-reclaim: crash streamu nie brickuje kampanii na zawsze
"""
import sys
import os
import threading

sys.path.insert(0, "/app")
os.environ.setdefault("AIGM_E2E_LITE", "1")

import pytest

from app.services import turn_lock


@pytest.fixture(autouse=True)
def _clean_registry():
    """Każdy test startuje z czystym rejestrem locków."""
    turn_lock._reset_for_tests()
    yield
    turn_lock._reset_for_tests()


# ─── Test główny — druga równoległa tura odbita ──────────────────────────────

def test_second_acquire_same_campaign_is_busy():
    """Solo: drugi acquire tej samej kampanii = TurnLockBusy (→ 409)."""
    key = turn_lock.acquire(1001)
    assert key
    with pytest.raises(turn_lock.TurnLockBusy):
        turn_lock.acquire(1001)


def test_acquire_or_409_raises_http_409_when_busy():
    """Mapowanie na HTTP: drugi równoległy POST → HTTPException 409, nie 200."""
    from fastapi import HTTPException

    turn_lock.acquire_or_409(1001)
    with pytest.raises(HTTPException) as ei:
        turn_lock.acquire_or_409(1001)
    assert ei.value.status_code == 409


def test_two_parallel_threads_exactly_one_wins():
    """2 wątki wyścigują o tę samą kampanię (jak 2 równoległe POSTy):
    dokładnie jeden dostaje lock, drugi = busy. Żaden nie może przejść podwójnie.
    """
    barrier = threading.Barrier(2)
    results: list[str] = []
    errors: list[Exception] = []
    lock = threading.Lock()

    def worker():
        barrier.wait()  # zsynchronizuj start — realny wyścig
        try:
            k = turn_lock.acquire(2002)
            with lock:
                results.append(k)
        except turn_lock.TurnLockBusy as e:
            with lock:
                errors.append(e)

    t1 = threading.Thread(target=worker)
    t2 = threading.Thread(target=worker)
    t1.start(); t2.start()
    t1.join(); t2.join()

    assert len(results) == 1, "dokładnie jeden wątek zdobywa lock (jeden 200)"
    assert len(errors) == 1, "drugi wątek odbity (jeden 409)"


# ─── MP — per character ──────────────────────────────────────────────────────

def test_mp_different_characters_independent():
    """MP: różne postaci w tej samej kampanii = niezależne klucze (grają równolegle)."""
    turn_lock.acquire(3003, character_id=11)
    # inna postać tej samej kampanii — musi przejść (MP round collecting)
    turn_lock.acquire(3003, character_id=22)
    # ta sama postać drugi raz — busy (double-submit tej samej postaci)
    with pytest.raises(turn_lock.TurnLockBusy):
        turn_lock.acquire(3003, character_id=11)


def test_solo_and_mp_keys_do_not_collide():
    """Klucz solo (per-campaign) jest niezależny od klucza MP (per-character)."""
    turn_lock.acquire(4004)                      # solo campaign lock
    turn_lock.acquire(4004, character_id=99)     # MP per-character — inny klucz, przechodzi


# ─── Zwolnienie w finally — kampania nie zawieszona ──────────────────────────

def test_release_frees_lock_no_brick():
    """Po zwolnieniu (finally) tę samą kampanię można znów zablokować."""
    key = turn_lock.acquire(5005)
    turn_lock.release(key)
    # nie zawieszone — kolejna tura startuje normalnie
    turn_lock.acquire(5005)


def test_release_is_idempotent():
    """Podwójne release nie wybucha (bezpieczne w finally + generator finally)."""
    key = turn_lock.acquire(6006)
    turn_lock.release(key)
    turn_lock.release(key)  # no-op, bez wyjątku


def test_stale_lock_reclaimed():
    """Crash streamu (lock nigdy nie zwolniony) → po STALE_LOCK_SECONDS
    kampania odblokowuje się sama, nie brickuje na zawsze."""
    turn_lock.acquire(7007)
    # udawany stary lock — cofnij znacznik czasu poza próg
    turn_lock._force_age_for_tests(turn_lock._key(7007, None),
                                   turn_lock.STALE_LOCK_SECONDS + 1)
    # stale → reclaim, nowy acquire przechodzi
    turn_lock.acquire(7007)


# ─── Wiring — refaktor endpointów/MP nie zepsuł importów ─────────────────────

def test_turn_endpoints_import_and_use_lock():
    """Sanity: turns.py importuje się (wiring _lock_key/_lock_handed_off bez NameError)
    i faktycznie odwołuje się do turn_lock."""
    import inspect
    from app.api import turns as turns_mod

    assert hasattr(turns_mod, "create_turn")
    assert hasattr(turns_mod, "create_turn_stream")
    src = inspect.getsource(turns_mod.create_turn_stream)
    assert "acquire_or_409" in src, "stream endpoint musi zdobywać in-flight lock"
    assert "_lock_handed_off" in src, "stream musi oddać lock generatorowi"


def test_mp_trigger_narration_wrapped_with_lock():
    """MP: trigger_narration owinięty per-campaign lockiem, impl wydzielony."""
    import inspect
    from app.services import multiplayer_round_service as mp

    assert hasattr(mp, "trigger_narration")
    assert hasattr(mp, "_trigger_narration_impl")
    src = inspect.getsource(mp.trigger_narration)
    assert "turn_lock" in src, "MP narracja musi używać wspólnego turn_lock"
