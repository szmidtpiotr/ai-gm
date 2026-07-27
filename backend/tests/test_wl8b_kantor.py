"""WL-8b (#1504) — testy weksli kantorów.

Pokrycie:
  * buy_weksel — zdejmuje nominał + prowizję z gold_gp, dokłada weksel do sheet_json,
  * prowizja (2% min 1) i minimalny nominał,
  * redeem_weksel — zwraca pełny nominał, usuwa weksel,
  * KLUCZOWE: weksel przeżywa utratę złota (śmierć/napad zerują gold_gp, weksel w
    sheet_json zostaje → wymiana nadal działa) — strukturalna odporność majątku,
  * kantor_available — bramka lokacji (enklawa krasnoludzka = kantor).

In-memory SQLite; change_gold/get_character_gold operują na gold_gp (log opcjonalny).
"""

import json
import sqlite3

import pytest

from app.services import kantor_service as ks


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        "CREATE TABLE characters (id INTEGER PRIMARY KEY, gold_gp INTEGER DEFAULT 0, sheet_json TEXT);"
        "CREATE TABLE game_locations (id INTEGER PRIMARY KEY, key TEXT, label TEXT, "
        "location_subtype TEXT, is_active INTEGER DEFAULT 1);"
    )
    conn.execute("INSERT INTO characters (id, gold_gp, sheet_json) VALUES (7, 500, ?)",
                 (json.dumps({"stats": {}}),))
    conn.commit()
    yield conn
    conn.close()


def _gold(db):
    return int(db.execute("SELECT gold_gp FROM characters WHERE id=7").fetchone()[0])


# ── buy ───────────────────────────────────────────────────────────────────────

def test_buy_deducts_amount_plus_fee_and_stores_weksel(db):
    out = ks.buy_weksel(db, 7, 100)
    assert out["fee"] == 2                       # 2% z 100
    assert _gold(db) == 500 - 100 - 2            # nominał + prowizja z gold_gp
    assert out["weksel"]["amount"] == 100
    weksle = ks.list_weksle(db, 7)
    assert len(weksle) == 1 and weksle[0]["amount"] == 100
    assert ks.total_weksle_value(db, 7) == 100


def test_buy_min_fee_is_one(db):
    out = ks.buy_weksel(db, 7, 10)   # 2% z 10 = 0.2 → min 1
    assert out["fee"] == ks.KANTOR_MIN_FEE == 1


def test_buy_rejects_tiny_amount(db):
    with pytest.raises(ValueError, match="amount_too_small"):
        ks.buy_weksel(db, 7, ks.MIN_WEKSEL_AMOUNT - 1)


def test_buy_rejects_insufficient_gold(db):
    with pytest.raises(ValueError, match="insufficient_gold"):
        ks.buy_weksel(db, 7, 1000)   # tylko 500 w kiesie
    assert _gold(db) == 500          # nic nie zdjęte


def test_buy_ids_increment(db):
    a = ks.buy_weksel(db, 7, 50)["weksel"]["id"]
    b = ks.buy_weksel(db, 7, 50)["weksel"]["id"]
    assert b == a + 1                # seq rośnie, brak kolizji po usunięciu


# ── redeem ────────────────────────────────────────────────────────────────────

def test_redeem_returns_full_nominal(db):
    wid = ks.buy_weksel(db, 7, 200)["weksel"]["id"]
    gold_after_buy = _gold(db)       # 500 - 200 - 4 = 296
    out = ks.redeem_weksel(db, 7, wid)
    assert out["amount"] == 200
    assert _gold(db) == gold_after_buy + 200    # pełny nominał wraca (prowizja tylko przy wystawieniu)
    assert ks.list_weksle(db, 7) == []


def test_redeem_unknown_raises(db):
    with pytest.raises(ValueError, match="weksel_not_found"):
        ks.redeem_weksel(db, 7, 999)


# ── kluczowa własność: weksel przeżywa utratę złota ──────────────────────────

def test_weksel_survives_gold_wipe(db):
    """Śmierć/napad zerują gold_gp; weksel w sheet_json zostaje → majątek ocalony."""
    wid = ks.buy_weksel(db, 7, 300)["weksel"]["id"]
    # symuluj napad/śmierć: całe złoto znika (ale sheet_json nietknięty)
    db.execute("UPDATE characters SET gold_gp = 0 WHERE id = 7")
    db.commit()
    assert _gold(db) == 0
    # weksel nadal jest — wymiana odzyskuje nominał
    assert ks.total_weksle_value(db, 7) == 300
    ks.redeem_weksel(db, 7, wid)
    assert _gold(db) == 300


# ── bramka lokacji ────────────────────────────────────────────────────────────

def test_kantor_available_by_location(db, monkeypatch):
    db.execute("INSERT INTO game_locations (key, label, location_subtype) VALUES "
               "('vilnograd_enklawa_krasnoludzka', 'Vilnograd: Enklawa Krasnoludzka', 'kantor')")
    db.execute("INSERT INTO game_locations (key, label, location_subtype) VALUES "
               "('vilnograd_rynek', 'Vilnograd: Rynek', 'market')")
    db.commit()

    import app.services.location_state_service as lss
    def fake_key(conn, cid):
        return {1: "vilnograd_enklawa_krasnoludzka", 2: "vilnograd_rynek"}.get(cid)
    monkeypatch.setattr(lss, "get_current_location_key", fake_key)

    assert ks.kantor_available(db, 1) is True    # enklawa = kantor
    assert ks.kantor_available(db, 2) is False   # rynek ≠ kantor
