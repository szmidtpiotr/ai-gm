"""WL-8 (#1504) — testy ekonomii Wybrzeża Łez: sól morska + kontrabanda.

Pokrycie:
  * TRADE_GOODS — pętla zysku (kup u źródła taniej niż sprzedasz w Nizinach) i
    kierunkowość (u źródła nadpodaż → sprzedaż tam się nie opłaca),
  * drabina soli — sól morska = najtańsza klasa (dół drabiny), gradacja bazowa,
  * trade_good_sell_price — cena zależna od regionu (Niziny drogo / Wybrzeże tanio),
  * crossing_into_toll_region — rogatka tylko przy WJEŹDZIE do regionu z rogatkami,
  * carried_contraband — wykrycie kontrabandy w plecaku,
  * rogatka_control — kontrola: brak papierów (wpadka/przejście), list żelazny
    (bez pytań), fałszywe papiery (test + wpadka konfiskuje papiery), brak
    kontrabandy = brak kontroli, konfiskata + strata reputacji z liczbami w raporcie.

DB-testy używają in-memory SQLite (bez Dockera dla czystej logiki; test_dev.sh
uruchomi to na kopii DEV-DB).
"""

import json
import random
import sqlite3

import pytest

from app.services import smuggling_service as sm


# ── Czysta logika (bez DB) ───────────────────────────────────────────────────

def test_smuggle_loop_is_profitable():
    """Każdy towar: sprzedaż w Nizinach > kupno u źródła → loop domyka się zyskiem."""
    for key, g in sm.TRADE_GOODS.items():
        assert g.sell_demand > g.buy_at_source, f"{key}: przemyt nierentowny"


def test_selling_at_source_is_a_loss():
    """U źródła nadpodaż — sprzedaż tam, gdzie się kupiło, się nie opłaca (kierunek)."""
    for key, g in sm.TRADE_GOODS.items():
        assert g.sell_source < g.buy_at_source, f"{key}: brak kierunkowości handlu"


def test_sea_salt_is_cheapest_salt_class():
    """Sól morska = dół drabiny (najtańsza klasa), gradacja Pustkowia>Granie>Wybrzeże."""
    assert sm.cheapest_salt_key() == "sol_morska"
    region, key, real = sm.SALT_LADDER[-1]
    assert (region, key, real) == ("wybrzeze_lez", "sol_morska", True)
    # WL-8b: wszystkie trzy szczeble są realnymi towarami
    assert all(real for _r, _k, real in sm.SALT_LADDER)


def test_salt_gradation_prices_ordered():
    """Cena SPRZEDAŻY soli w Nizinach rośnie z klasą: blizna > górska > morska."""
    morska = sm.TRADE_GOODS["sol_morska"].sell_demand
    gorska = sm.TRADE_GOODS["sol_gorska"].sell_demand
    blizny = sm.TRADE_GOODS["sol_blizny"].sell_demand
    assert morska < gorska < blizny
    # każda sól ma inny region rodowy (dół drabiny = Wybrzeże)
    homes = {sm.TRADE_GOODS[k].home_region for k in ("sol_morska", "sol_gorska", "sol_blizny")}
    assert homes == {"wybrzeze_lez", "siwe_granie", "martwe_pustkowia"}
    assert all(not sm.TRADE_GOODS[k].contraband for k in ("sol_morska", "sol_gorska", "sol_blizny"))


def test_sea_salt_is_legal_contraband_is_not():
    assert sm.TRADE_GOODS["sol_morska"].contraband is False
    assert sm.CONTRABAND_KEYS == frozenset({"perla_glebin", "zywica_topielcow"})


def test_crossing_into_toll_region():
    # wjazd do Nizin z Wybrzeża → kontrola
    assert sm.crossing_into_toll_region("wybrzeze_lez", "koronne_niziny") is True
    # ruch wewnątrz Nizin → bez rogatki
    assert sm.crossing_into_toll_region("koronne_niziny", "koronne_niziny") is False
    # wyjazd z Nizin → bez rogatki
    assert sm.crossing_into_toll_region("koronne_niziny", "wybrzeze_lez") is False


# ── Fixtura DB ───────────────────────────────────────────────────────────────

@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE characters (id INTEGER PRIMARY KEY, campaign_id INTEGER, sheet_json TEXT);
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
    # bohater: ZR 10 (mod 0) — czysty rzut na progu
    conn.execute(
        "INSERT INTO characters (id, campaign_id, sheet_json) VALUES (7, 100, ?)",
        (json.dumps({"stats": {"DEX": 10}}),),
    )
    # lokacje regionów
    conn.executemany(
        "INSERT INTO game_locations (id, key, region) VALUES (?,?,?)",
        [(1, "volhynia_targowisko", "koronne_niziny"),
         (2, "czarnogrod_port", "wybrzeze_lez")],
    )
    # hexy granicy: (0,0) Wybrzeże, (1,0) Niziny
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


# ── trade_good_sell_price ─────────────────────────────────────────────────────

def test_sell_price_dear_in_niziny_cheap_at_coast(db):
    _stand_in(db, 1)  # Niziny
    assert sm.trade_good_sell_price(db, 7, "perla_glebin") == sm.TRADE_GOODS["perla_glebin"].sell_demand
    _stand_in(db, 2)  # Wybrzeże (źródło)
    assert sm.trade_good_sell_price(db, 7, "perla_glebin") == sm.TRADE_GOODS["perla_glebin"].sell_source


def test_sell_price_none_for_ordinary_item(db):
    _stand_in(db, 1)
    assert sm.trade_good_sell_price(db, 7, "torch") is None


def test_niziny_price_beats_coast_buy(db):
    """Konkret pętli: sprzedaż perły w Nizinach > cena kupna na Czarnym Targu."""
    _stand_in(db, 1)
    niziny = sm.trade_good_sell_price(db, 7, "perla_glebin")
    assert niziny > sm.TRADE_GOODS["perla_glebin"].buy_at_source


# ── carried_contraband ────────────────────────────────────────────────────────

def test_carried_contraband_detects_only_contraband(db):
    _give(db, "perla_glebin", 2)
    _give(db, "sol_morska", 5)   # legalne — nie kontrabanda
    _give(db, "torch")
    found = sm.carried_contraband(db, 7)
    keys = {f["item_key"] for f in found}
    assert keys == {"perla_glebin"}
    assert found[0]["quantity"] == 2


# ── rogatka_control ───────────────────────────────────────────────────────────

def test_rogatka_none_when_not_crossing(db):
    _give(db, "perla_glebin")
    # ruch wewnątrz Nizin (region→ten sam) — brak rogatki
    assert sm.rogatka_control(db, 100, 7, from_region="koronne_niziny",
                              to_region="koronne_niziny") is None


def test_rogatka_none_without_contraband(db):
    assert sm.rogatka_control(db, 100, 7, from_hex=(0, 0), to_hex=(1, 0)) is None


def test_rogatka_report_shape(db):
    """Kontrola z kontrabandą zawsze zwraca raport z liczbami (rzut/DC/units)."""
    _give(db, "perla_glebin", 1)
    report = sm.rogatka_control(db, 100, 7, from_hex=(0, 0), to_hex=(1, 0),
                                rng=random.Random(0))
    assert report is not None and report["checked"] is True
    assert "dc" in report and "roll" in report and "units" in report


def test_rogatka_forced_bust_numbers(db):
    """Deterministyczna wpadka przez podstawienie rng zawsze zwracającego 1."""
    _give(db, "perla_glebin", 3)

    class _Low:
        def randint(self, a, b):
            return a  # zawsze minimum → gwarantowana wpadka

    report = sm.rogatka_control(db, 100, 7, from_hex=(0, 0), to_hex=(1, 0), rng=_Low())
    assert report["passed"] is False
    assert report["roll"] == 1
    assert report["units"] == 3
    assert report["dc"] == sm.TOLL_DC_BASE + 2 * sm.TOLL_DC_PER_EXTRA_UNIT
    # konfiskata: perła zniknęła z plecaka
    assert sm.carried_contraband(db, 7) == []
    assert len(report["confiscated"]) == 1
    assert report["confiscated"][0]["quantity"] == 3
    # reputacja regionu spadła o karę
    assert report["reputation_delta"] == -sm.TOLL_REP_PENALTY
    from app.services.reputation_service import get_reputation
    assert get_reputation(db, 7, "koronne_niziny") == -sm.TOLL_REP_PENALTY


def test_rogatka_list_zelazny_passes_without_check(db):
    _give(db, "perla_glebin", 2)
    _give(db, sm.PASS_ITEM)

    class _Low:
        def randint(self, a, b):
            return a

    report = sm.rogatka_control(db, 100, 7, from_hex=(0, 0), to_hex=(1, 0), rng=_Low())
    assert report["passed"] is True
    assert report["reason"] == "list_zelazny"
    assert report["roll"] is None
    # towar zostaje — nic nie skonfiskowano
    assert len(sm.carried_contraband(db, 7)) == 1


def test_rogatka_forged_papers_seized_on_bust(db):
    """Fałszywe papiery: wpadka konfiskuje towar I papiery + większa kara reputacji."""
    _give(db, "zywica_topielcow", 1)
    _give(db, sm.FORGED_ITEM)

    class _Low:
        def randint(self, a, b):
            return a  # minimum — nawet z bonusem papierów poniżej DC

    report = sm.rogatka_control(db, 100, 7, from_hex=(0, 0), to_hex=(1, 0), rng=_Low())
    assert report["passed"] is False
    assert report.get("forged_seized") is True
    assert report["reputation_delta"] == -(sm.TOLL_REP_PENALTY + sm.TOLL_FORGERY_REP_PENALTY)
    # fałszywe papiery skonfiskowane
    assert sm._has_item(db, 7, sm.FORGED_ITEM) is False


def test_rogatka_high_roll_passes(db):
    _give(db, "perla_glebin", 1)

    class _High:
        def randint(self, a, b):
            return b  # zawsze 20 → na pewno przejdzie

    report = sm.rogatka_control(db, 100, 7, from_hex=(0, 0), to_hex=(1, 0), rng=_High())
    assert report["passed"] is True
    assert report["confiscated"] == []
    # towar zostaje
    assert len(sm.carried_contraband(db, 7)) == 1
