"""KN-8 (#1500) — testy smaczków Koronnych Nizin: papiery + weksle.

Źródło prawdy: docs/world/regions/koronne_niziny.md §6 (ZATWIERDZONE).

Pokrycie (dokładamy do WL-8/WL-8b, które zbudowały rdzeń mechaniki):
  * glejt kupiecki na rogatce — bonus do ukrycia vs brak papierów (LICZBY: rzut,
    conceal, paper_bonus, total, DC) — przejazd z glejtem vs bez,
  * fałszywe papiery — kontrola = test „DEX/CHA wg kontekstu" (con-artist gada
    charyzmą, gdy CHA > DEX),
  * glejt kupiecki na targach Nizin — mnożnik ceny KUPNA −10% w regionie, 1.0 poza,
  * weksel kantoru — przeżywa „śmierć" postaci: majątek w sheet_json["weksle"] jest
    nietknięty, gdy wszystkie ścieżki utraty ruszają tylko characters.gold_gp.

DB-testy używają in-memory SQLite (czysta logika, bez Dockera; test_dev.sh
uruchomi to na kopii DEV-DB).
"""

import json
import sqlite3

import pytest

from app.services import smuggling_service as sm
from app.services import kantor_service as kt
from app.services.economy_service import get_character_gold


# ── Deterministyczne rng ──────────────────────────────────────────────────────

class _Fixed:
    """rng.randint zawsze zwraca ustaloną wartość (deterministyczny rzut d20)."""

    def __init__(self, value: int):
        self._v = int(value)

    def randint(self, a, b):
        return max(a, min(b, self._v))


# ── Fixtura DB (wzorzec z test_wl8_smuggling) ────────────────────────────────

@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE characters (id INTEGER PRIMARY KEY, campaign_id INTEGER,
                                 gold_gp INTEGER DEFAULT 0, sheet_json TEXT);
        CREATE TABLE character_inventory (id INTEGER PRIMARY KEY, character_id INTEGER,
                                          item_key TEXT, consumable_key TEXT, weapon_key TEXT,
                                          quantity INTEGER DEFAULT 1);
        CREATE TABLE character_reputation (id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id INTEGER, scope_type TEXT DEFAULT 'region', scope_key TEXT,
            value INTEGER DEFAULT 0, updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(character_id, scope_type, scope_key));
        CREATE TABLE game_sessions (campaign_id INTEGER, current_location_id INTEGER,
                                    session_flags TEXT);
        CREATE TABLE game_locations (id INTEGER PRIMARY KEY, key TEXT, region TEXT,
                                     parent_key TEXT, world_hex_q INTEGER, world_hex_r INTEGER);
        CREATE TABLE world_hexes (q INTEGER, r INTEGER, map_level INTEGER DEFAULT 0,
                                  is_active INTEGER DEFAULT 1, region TEXT);
        CREATE TABLE campaign_turns (id INTEGER PRIMARY KEY, campaign_id INTEGER,
                                     character_id INTEGER, turn_number INTEGER, user_text TEXT,
                                     assistant_text TEXT, route TEXT, created_at TEXT);
        """
    )
    # bohater: DEX 10 (mod 0), CHA 10 (mod 0) — czysty rzut na progu; kampania w Nizinach
    conn.execute(
        "INSERT INTO characters (id, campaign_id, gold_gp, sheet_json) VALUES (7, 100, 0, ?)",
        (json.dumps({"stats": {"DEX": 10, "CHA": 10}}),),
    )
    conn.executemany(
        "INSERT INTO game_locations (id, key, region) VALUES (?,?,?)",
        [(1, "volhynia_targowisko", "koronne_niziny"),
         (2, "czarnogrod_port", "wybrzeze_lez")],
    )
    conn.executemany(
        "INSERT INTO world_hexes (q, r, region) VALUES (?,?,?)",
        [(0, 0, "wybrzeze_lez"), (1, 0, "koronne_niziny")],
    )
    conn.commit()
    yield conn
    conn.close()


def _stand_in(conn, location_id):
    conn.execute("DELETE FROM game_sessions WHERE campaign_id=100")
    conn.execute(
        "INSERT INTO game_sessions (campaign_id, current_location_id) VALUES (100, ?)",
        (location_id,),
    )
    conn.commit()


def _give(conn, item_key, qty=1):
    conn.execute(
        "INSERT INTO character_inventory (character_id, item_key, quantity) VALUES (7, ?, ?)",
        (item_key, qty),
    )
    conn.commit()


def _set_stats(conn, **stats):
    conn.execute("UPDATE characters SET sheet_json=? WHERE id=7",
                 (json.dumps({"stats": stats}),))
    conn.commit()


# ── 1) Glejt na rogatce: przejazd z glejtem vs bez (LICZBY) ──────────────────

def test_rogatka_glejt_vs_bez_numbers(db):
    """Ten sam rzut d20=10, 1 szt kontrabandy (DC 12): bez glejtu wpada, z glejtem
    (+4 conceal) przechodzi — pełne liczby w raporcie."""
    # --- bez papierów ---
    _give(db, "perla_glebin", 1)
    bez = sm.rogatka_control(db, 100, 7, from_hex=(0, 0), to_hex=(1, 0),
                             rng=_Fixed(10))
    assert bez["dc"] == 12
    assert bez["roll"] == 10
    assert bez["conceal_mod"] == 0
    assert bez["paper_bonus"] == 0
    assert bez["total"] == 10           # 10 + 0 + 0 < 12
    assert bez["passed"] is False       # wpadka → konfiskata
    assert bez["reason"] == "brak_papierow"

    # --- z glejtem (świeży towar, bo poprzedni skonfiskowano) ---
    _give(db, "perla_glebin", 1)
    _give(db, sm.PERMIT_ITEM)
    glejt = sm.rogatka_control(db, 100, 7, from_hex=(0, 0), to_hex=(1, 0),
                               rng=_Fixed(10))
    assert glejt["dc"] == 12
    assert glejt["roll"] == 10
    assert glejt["paper_bonus"] == sm.PERMIT_CONCEAL_BONUS   # +4
    assert glejt["total"] == 14         # 10 + 0 + 4 >= 12
    assert glejt["passed"] is True      # glejt przeprowadza przez rogatkę
    assert glejt["reason"] == "glejt"
    # towar zostaje — nic nie skonfiskowano
    assert len(sm.carried_contraband(db, 7)) == 1


def test_rogatka_list_zelazny_bez_pytan(db):
    """List żelazny = przejście bez rzutu (interakcja z Rogatką Berty)."""
    _give(db, "perla_glebin", 2)
    _give(db, sm.PASS_ITEM)
    rep = sm.rogatka_control(db, 100, 7, from_hex=(0, 0), to_hex=(1, 0),
                             rng=_Fixed(1))
    assert rep["passed"] is True
    assert rep["reason"] == "list_zelazny"
    assert rep["roll"] is None
    assert len(sm.carried_contraband(db, 7)) == 1  # towar nietknięty


# ── 2) Fałszywe papiery: test DEX/CHA wg kontekstu ───────────────────────────

def test_forged_uses_cha_when_higher(db):
    """Łotrzyk z niską DEX ale wysoką CHA (mod +3): fałszywe papiery pozwalają
    zagadać celnika — conceal liczony z CHA, nie DEX."""
    _set_stats(db, DEX=8, CHA=16)   # DEX mod −1, CHA mod +3
    _give(db, "perla_glebin", 1)
    _give(db, sm.FORGED_ITEM)
    rep = sm.rogatka_control(db, 100, 7, from_hex=(0, 0), to_hex=(1, 0),
                             rng=_Fixed(10))
    assert rep["conceal_mod"] == 3      # max(DEX −1, CHA +3) = +3
    assert rep["reason"] == "falszywe_papiery"


def test_conceal_uses_dex_without_forged(db):
    """Bez fałszywych papierów liczy się DEX (schowanie towaru), nie CHA."""
    _set_stats(db, DEX=8, CHA=16)
    _give(db, "perla_glebin", 1)
    rep = sm.rogatka_control(db, 100, 7, from_hex=(0, 0), to_hex=(1, 0),
                             rng=_Fixed(10))
    assert rep["conceal_mod"] == -1     # tylko DEX mod


def test_forged_bust_seizes_papers_and_extra_rep(db):
    """Wpadka z fałszywymi papierami: konfiskata towaru + papierów + większa kara."""
    _give(db, "zywica_topielcow", 1)
    _give(db, sm.FORGED_ITEM)
    rep = sm.rogatka_control(db, 100, 7, from_hex=(0, 0), to_hex=(1, 0),
                             rng=_Fixed(1))
    assert rep["passed"] is False
    assert rep.get("forged_seized") is True
    assert rep["reputation_delta"] == -(sm.TOLL_REP_PENALTY + sm.TOLL_FORGERY_REP_PENALTY)
    # papiery skonfiskowane
    assert sm._has_item(db, 7, sm.FORGED_ITEM) is False


# ── 3) Glejt na targach: −10% ceny kupna w Nizinach ──────────────────────────

def test_glejt_market_discount_in_niziny(db):
    _stand_in(db, 1)  # Volhynia (koronne_niziny)
    _give(db, sm.PERMIT_ITEM)
    assert sm.glejt_market_multiplier(db, 7) == pytest.approx(1.0 - sm.GLEJT_MARKET_DISCOUNT)


def test_glejt_no_discount_outside_niziny(db):
    _stand_in(db, 2)  # Czarnogród (wybrzeze_lez)
    _give(db, sm.PERMIT_ITEM)
    assert sm.glejt_market_multiplier(db, 7) == 1.0


def test_no_glejt_no_discount(db):
    _stand_in(db, 1)  # w Nizinach, ale bez glejtu
    assert sm.glejt_market_multiplier(db, 7) == 1.0


# ── 4) Weksel przeżywa śmierć postaci ────────────────────────────────────────

def test_weksel_survives_death(db):
    """Weksel w sheet_json["weksle"] przeżywa utratę całego złota (śmierć/napad/
    wskrzeszenie ruszają tylko characters.gold_gp — sheet_json jest nietknięty)."""
    db.execute("UPDATE characters SET gold_gp=200 WHERE id=7")
    db.commit()

    # wpłata: 100 do weksla (+ prowizja 2)
    out = kt.buy_weksel(db, 7, 100)
    db.commit()
    fee = out["fee"]
    assert fee == max(kt.KANTOR_MIN_FEE, 2)
    assert get_character_gold(db, 7) == 200 - 100 - fee
    assert kt.total_weksle_value(db, 7) == 100

    # SYMULACJA ŚMIERCI/NAPADU: każda ścieżka utraty majątku zeruje TYLKO gold_gp
    db.execute("UPDATE characters SET gold_gp=0 WHERE id=7")
    db.commit()
    assert get_character_gold(db, 7) == 0

    # majątek w wekslu nietknięty
    assert kt.total_weksle_value(db, 7) == 100

    # da się go wymienić z powrotem na złoto (pełny nominał)
    red = kt.redeem_weksel(db, 7, out["weksel"]["id"])
    db.commit()
    assert red["amount"] == 100
    assert get_character_gold(db, 7) == 100
    assert kt.total_weksle_value(db, 7) == 0
