"""TDD: Issue #766 — Trade-intent regex matches word fragments (skUPiam, przygLADam) + keys[0] fallback opens random shop."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.api.turns import _TRADE_USER_INTENT_RE, _pick_shop_npc_key

# ─── RED tests: currently pass (bug exists), must stay GREEN after fix ────────


def test_skupiam_does_not_match_trade_intent():
    """'skupiam się' musi NIE pasować do intencji handlu (fragment 'kup' w s-KUP-iam)."""
    assert not _TRADE_USER_INTENT_RE.search("skupiam się na szczegole")


def test_przygladam_does_not_match_trade_intent():
    """'przyglądam się' musi NIE pasować (fragment 'lad' w przyg-LAD-am)."""
    assert not _TRADE_USER_INTENT_RE.search("przyglądam sie uważnie")


def test_scena_does_not_match_trade_intent():
    """'scena' musi NIE pasować (fragment 'cen' w s-CEN-a)."""
    assert not _TRADE_USER_INTENT_RE.search("scena rozgrywa się w lesie")


def test_ukladam_does_not_match_trade_intent():
    """'układam' musi NIE pasować (fragment 'lad' w uk-ŁAD-am)."""
    assert not _TRADE_USER_INTENT_RE.search("układam plan ataku")


def test_nasluchuję_does_not_match_trade_intent():
    """'nasłuchuję' musi NIE pasować."""
    assert not _TRADE_USER_INTENT_RE.search("nasłuchuję i uważnie się przyglądam")


# ─── GREEN tests: real trade intents MUST still match ────────────────────────


def test_kupuje_matches_trade_intent():
    """'kupuję' musi pasować do intencji handlu."""
    assert _TRADE_USER_INTENT_RE.search("kupuję miecz od kowala")


def test_handel_matches_trade_intent():
    """'handel' musi pasować."""
    assert _TRADE_USER_INTENT_RE.search("chcę porozmawiać o handlu")


def test_sklep_matches_trade_intent():
    """'sklep' musi pasować."""
    assert _TRADE_USER_INTENT_RE.search("wchodzę do sklepu")


def test_cena_matches_trade_intent():
    """'cena' jako osobne słowo musi pasować."""
    assert _TRADE_USER_INTENT_RE.search("jaka jest cena tego miecza?")


def test_sprzedaje_matches_trade_intent():
    """'sprzedaję' musi pasować."""
    assert _TRADE_USER_INTENT_RE.search("sprzedaję zbroję")


def test_kupiec_matches_trade_intent():
    """'kupiec' musi pasować."""
    assert _TRADE_USER_INTENT_RE.search("szukam kupca w mieście")


# ─── _pick_shop_npc_key: no blanket fallback ─────────────────────────────────


def test_pick_shop_npc_key_returns_none_when_no_match():
    """Gdy narracja nie wskazuje kupca z listy, zwróć None (nie keys[0])."""
    keys = ["kowal_wolanka", "grubas_miron"]
    narrative = "Bohater skrada się przez las, nasłuchuje szelestów."
    result = _pick_shop_npc_key(narrative, keys)
    assert result is None, f"Oczekiwano None, dostałem: {result!r}"


def test_pick_shop_npc_key_returns_match_when_present():
    """Gdy narracja zawiera nazwę kupca, zwróć właściwy klucz."""
    keys = ["kowal_wolanka", "grubas_miron"]
    narrative = "Miron wita cię serdecznie za ladą."
    result = _pick_shop_npc_key(narrative, keys)
    assert result == "grubas_miron", f"Oczekiwano grubas_miron, dostałem: {result!r}"


def test_pick_shop_npc_key_returns_none_for_empty_list():
    """Pusta lista → zawsze None."""
    assert _pick_shop_npc_key("kupuję miecz", []) is None
