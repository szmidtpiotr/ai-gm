"""MP-8 (#1494 §8 / #1475) — Start kampanii Piętnowanego w Martwych Pustkowiach.

Pokrywa:
  * whitelist startowa: default Gospoda w Solnym Progu + wariant Obóz Gorączki,
  * haki plan-hinta: Lejla vs Raszid (otwarcie/ukrycie) + Siostra Verena węszy,
  * piętno społeczne swój/obcy: +10% u obcych (Obóz Gorączki, Misja), 0% we
    własnej enklawie (Solny Próg i jego suby).
"""
import sqlite3

from app.services import race_start_service as rss
from app.services import shop_service


# ─── Whitelist startowa (§8: default gospoda, wariant Obóz Gorączki) ──────────

def test_mp8_start_default_is_solny_prog_gospoda():
    spec = rss.RACE_START["pietnowani"]
    assert spec["region"] == "martwe_pustkowia"
    assert spec["default"] == "solny_prog_gospoda"


def test_mp8_oboz_goraczki_is_a_start_variant():
    spec = rss.RACE_START["pietnowani"]
    assert "oboz_goraczki" in spec["variants"]
    # enklawa (gospoda + rada) nadal dostępna jako wariant
    assert "solny_prog_gospoda" in spec["variants"]
    assert "solny_prog_dom_starszych" in spec["variants"]


# ─── Haki startowe (§8: Lejla vs Raszid + Verena) ────────────────────────────

def test_mp8_plan_hint_lejla_vs_raszid_axis():
    hint = rss.RACE_PLAN_HINT["pietnowani"]
    assert "Lejla" in hint
    assert "Raszid" in hint
    # oś otwarcie/ukrycie (wielkość liter dowolna w prozie)
    low = hint.lower()
    assert "otwarci" in low and "ukryci" in low


def test_mp8_plan_hint_verena_sniffs_the_enclave():
    hint = rss.RACE_PLAN_HINT["pietnowani"]
    assert "Verena" in hint
    assert "enklaw" in hint.lower()


def test_mp8_plan_hint_offers_oboz_goraczki_as_option():
    assert "Obóz Gorączki" in rss.RACE_PLAN_HINT["pietnowani"]


# ─── Piętno społeczne swój/obcy (§3 zadania) ─────────────────────────────────
# Helpery liczą narzut z jawnego location_key → nie dotykają DB (conn pusty OK).

_CONN = sqlite3.connect(":memory:")
_CID = 1  # nieużywany, bo location_key podajemy wprost


def test_mp8_enclave_detection_solny_prog_is_home():
    assert shop_service._pietnowani_in_home_enclave(_CONN, _CID, "solny_prog_gospoda") is True
    assert shop_service._pietnowani_in_home_enclave(_CONN, _CID, "solny_prog_dom_starszych") is True
    assert shop_service._pietnowani_in_home_enclave(_CONN, _CID, "solny_prog_targ_przewodnikow") is True


def test_mp8_enclave_detection_outside_is_foreign():
    assert shop_service._pietnowani_in_home_enclave(_CONN, _CID, "oboz_goraczki") is False
    assert shop_service._pietnowani_in_home_enclave(_CONN, _CID, "misja_swiatla") is False
    assert shop_service._pietnowani_in_home_enclave(_CONN, _CID, "kresy_wioska") is False


def test_mp8_no_markup_inside_enclave():
    # Solny Próg = swoi → brak narzutu piętna.
    assert shop_service._pietnowani_markup(_CONN, _CID, "solny_prog_gospoda") == 1.0
    assert shop_service._pietnowani_markup(_CONN, _CID, "solny_prog_solne_magazyny") == 1.0


def test_mp8_markup_applies_in_oboz_goraczki():
    # Obóz Gorączki = obcy → +10%.
    expected = 1.0 + shop_service.PIETNOWANI_SHOP_MARKUP
    assert shop_service._pietnowani_markup(_CONN, _CID, "oboz_goraczki") == expected
    assert shop_service._pietnowani_markup(_CONN, _CID, "misja_swiatla") == expected


def test_mp8_markup_constant_is_ten_percent():
    assert shop_service.PIETNOWANI_SHOP_MARKUP == 0.10
