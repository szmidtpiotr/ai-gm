"""TDD: Issue #1391 — bramka intercept usług + hybrydowa dostępność rzemiosła.

Dwa fixy:
1. `_maybe_services_shortcut` — naturalna narracja („idę do kowala",
   „chciałbym naprawić sprzęt") otwiera modal Usług. Dotąd wymagała czasownika
   ZAKUPU (kupuję/zamawiam), więc narrator (który modala nie otwiera) przejmował turę.
2. `crafting_service` — crafter_type wyprowadzany z lokacji/osady (hybryda per-osada),
   bez ręcznie przypisanego NPC: kuźnia-sublokacja → kowal; prawdziwa osada → kowal+zielarka;
   dzicz → nic. Nazwane NPC dalej działają.
"""
import os
import sqlite3
import sys

import pytest

sys.path.insert(0, "/app")

from app.migrations_admin import _ensure_recipes_schema
from app.services import crafting_service

TEST_DB = f"/tmp/avail_test_{os.getpid()}.db"


def _conn():
    c = sqlite3.connect(TEST_DB, timeout=30)
    c.row_factory = sqlite3.Row
    return c


@pytest.fixture(autouse=True)
def _isolated_db(monkeypatch):
    for p in (TEST_DB, TEST_DB + "-wal", TEST_DB + "-shm"):
        if os.path.exists(p):
            os.remove(p)
    src = sqlite3.connect("/data/ai_gm.db", timeout=30)
    try:
        src.execute("VACUUM INTO ?", (TEST_DB,))
    finally:
        src.close()
    monkeypatch.setattr(crafting_service, "DB_PATH", TEST_DB)
    c = _conn()
    try:
        _ensure_recipes_schema(c)
    finally:
        c.close()
    yield
    for p in (TEST_DB, TEST_DB + "-wal", TEST_DB + "-shm"):
        if os.path.exists(p):
            os.remove(p)


# ─── 1. Bramka intercept usług ──────────────────────────────────────────────

def _intercept(text, loc_key="rudnik_smithy"):
    """Wywołaj _maybe_services_shortcut z podstawioną bieżącą lokacją."""
    from app.api import turns
    conn = _conn()
    try:
        orig = turns._current_location_key
        turns._current_location_key = lambda c, cid: loc_key  # noqa: E731
        try:
            return turns._maybe_services_shortcut(conn, 1, text)
        finally:
            turns._current_location_key = orig
    finally:
        conn.close()


@pytest.mark.parametrize("text", [
    "ide do kowala",
    "idę do kowala",
    "chcialbym naprawic swoj sprzet",
    "chciałbym naprawić sprzęt",
    "chcę naprawić broń",
    "potrzebuję noclegu",
    "podchodzę do kowala",
])
def test_intent_verb_opens_services_modal(text):
    res = _intercept(text)
    assert res is not None, f"intercept milczał dla: {text!r}"
    assert res["route"] == "services_shortcut"
    assert res["open_services"] == "rudnik_smithy"


def test_order_verb_still_opens():
    # Regres: dotychczasowa ścieżka zakupu nie może przestać działać.
    assert _intercept("kupuję nocleg") is not None
    assert _intercept("co masz do zaoferowania") is not None  # browse-ask


def test_no_service_noun_falls_through():
    # Sama chęć bez rzeczownika-usługi → narrator, nie modal.
    assert _intercept("idę przed siebie") is None
    assert _intercept("opowiadam strażnikowi legendę") is None


def test_wilderness_guarded():
    # Nawet z poprawną frazą: brak usług w lokacji → None (bramka lokalizacji).
    assert _intercept("idę do kowala", loc_key=None) is None


# ─── 2. Hybrydowa dostępność rzemiosła ──────────────────────────────────────

def test_smithy_sublocation_infers_smith():
    data = crafting_service.get_location_crafting("rudnik_smithy")
    assert "smith" in data["crafters"], data["crafters"]
    # skoro jest crafter_type smith, muszą być receptury smithowe
    assert any(r["crafter_type"] == "smith" for r in data["recipes"])


def test_real_settlement_infers_both():
    data = crafting_service.get_location_crafting("rudnik")
    assert "smith" in data["crafters"] and "herbalist" in data["crafters"], data["crafters"]
    assert crafting_service.location_has_crafting("rudnik") is True


def test_named_npc_location_still_works():
    # brzezino ma nazwane NPC (kowal + zielarka) — regres.
    data = crafting_service.get_location_crafting("brzezino")
    assert "smith" in data["crafters"] and "herbalist" in data["crafters"]


def test_wilderness_macro_has_no_crafting():
    """Znajdź dziki macro (nie osada, brak słów kowal/zielarz) → zero rzemiosła."""
    conn = _conn()
    try:
        SMITH = crafting_service._SMITH_KW
        HERB = crafting_service._HERBALIST_KW
        wild = None
        for r in conn.execute(
            "SELECT key,label,location_subtype FROM game_locations "
            "WHERE location_type='macro' AND is_active=1"
        ).fetchall():
            full = crafting_service._loc_full(conn, r["key"])
            if crafting_service._is_real_settlement(conn, full):
                continue
            hay = ((r["label"] or "") + " " + (r["location_subtype"] or "")).lower()
            if any(k in hay for k in SMITH) or any(k in hay for k in HERB):
                continue
            wild = r["key"]
            break
    finally:
        conn.close()
    if wild is None:
        pytest.skip("brak dzikiego macro w danych snapshotu")
    data = crafting_service.get_location_crafting(wild)
    assert data["crafters"] == [], f"{wild} nie powinien mieć rzemiosła: {data['crafters']}"
    assert crafting_service.location_has_crafting(wild) is False
