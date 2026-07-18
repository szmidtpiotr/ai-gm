"""TDD: Issue #751 — brak usługi gastronomicznej (posiłek/napój) w game_config_services.

LLM wyceniał jedzenie na 2 GP, ale nie miał klucza usługi → wstawiał [SPEND_GOLD:inn_night]
i silnik pobierał 5 GP (cena noclegu). Fix: dodać usługi `tavern_meal` (2 GP) i
`tavern_drink` (1 GP) do seeda game_config_services, żeby cena<->płatność były spójne.

Test sprawdza dane seeda (migracja) + parser SPEND_GOLD na świeżej bazie.
"""
import sys
sys.path.insert(0, "/app")
from _fixtures_schema import table_sql

import sqlite3
import pytest
from app.services.spend_gold_service import parse_spend_gold_tags
from app.migrations_admin import ADMIN_SEEDS


def _fresh_services_db():
    """In-memory DB z tabelą game_config_services + zaaplikowanym seedem usług gastronomicznych."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("""
        """ + table_sql("game_config_services") + """
    """)
    # Znajdź seed zawierający tavern_meal i zaaplikuj go (RED: nie istnieje dopóki fix nie wejdzie).
    seed = next(
        s for s in ADMIN_SEEDS
        if isinstance(s, str) and "tavern_meal" in s
    )
    conn.executescript(seed)
    conn.commit()
    return conn


# ─── Test główny ─────────────────────────────────────────────────────────────

def test_tavern_meal_service_exists_with_2gp():
    """Usługa `tavern_meal` istnieje w seedzie z ceną 2 GP."""
    conn = _fresh_services_db()
    try:
        row = conn.execute(
            "SELECT cost_gp, is_active FROM game_config_services WHERE key = 'tavern_meal'"
        ).fetchone()
        assert row is not None, "brak usługi tavern_meal w game_config_services"
        assert int(row["cost_gp"]) == 2, "posiłek musi kosztować 2 GP, nie inn_night (5 GP)"
        assert int(row["is_active"]) == 1
    finally:
        conn.close()


def test_tavern_drink_service_exists_with_1gp():
    """Usługa `tavern_drink` istnieje w seedzie z ceną 1 GP."""
    conn = _fresh_services_db()
    try:
        row = conn.execute(
            "SELECT cost_gp FROM game_config_services WHERE key = 'tavern_drink'"
        ).fetchone()
        assert row is not None, "brak usługi tavern_drink"
        assert int(row["cost_gp"]) == 1
    finally:
        conn.close()


def test_spend_gold_tavern_meal_resolves_to_2gp():
    """[SPEND_GOLD:tavern_meal] → silnik pobiera 2 GP (kwota z bazy, zgodna z narracją)."""
    conn = _fresh_services_db()
    try:
        tags = parse_spend_gold_tags(
            "Karczmarka zgarnia monety. [SPEND_GOLD:tavern_meal]", conn
        )
        assert tags == [("tavern_meal", 2)], (
            "posiłek powinien rozwiązać się do 2 GP, nie 5 GP (inn_night)"
        )
    finally:
        conn.close()


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_inn_night_still_5gp():
    """Stara usługa noclegu nadal kosztuje 5 GP — niezmieniona."""
    conn = _fresh_services_db()
    try:
        tags = parse_spend_gold_tags("[SPEND_GOLD:inn_night]", conn)
        assert tags == [("inn_night", 5)]
    finally:
        conn.close()
