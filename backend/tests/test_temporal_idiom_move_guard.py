"""TDD: Temporal idiom guard — 'wschód słońca' must NOT fire directional MOVE.

Reproduces the #8888931 teleport: player typed "Idę odpocząć do pokoju by stawić się
na wschód słońca w Kuzni Brunona", which contained 'wschód', causing detect_move_intent
to return MOVEMENT east and teleport the hero from the inn to the road.

Guard must also cover: zachód słońca, o północy, w południe, po południu.
Correct directional uses (idę na wschód, idę na południe) must still fire.
"""

import pytest

from app.services.turn_pipeline import detect_move_intent, detect_vague_move_intent

_HEX = {"q": 39, "r": 6}


# ── False-positive temporal idioms ───────────────────────────────────────────

class TestSolarIdiomBlocked:
    def test_wschod_slonca_no_move(self):
        txt = "Idę odpocząć do pokoju by stawić się na wschód słońca w Kuzni Brunona"
        assert detect_move_intent(txt, _HEX) is None

    def test_wschod_slonca_not_vague(self):
        # After stripping solar idiom, no direction left → vague=True is acceptable,
        # but must NOT have been triggered as a real directional MOVE (mv == None).
        txt = "Idę odpocząć do pokoju by stawić się na wschód słońca w Kuzni Brunona"
        assert detect_move_intent(txt, _HEX) is None

    def test_o_wschodzie_slonca_no_move(self):
        txt = "Stawię się o wschodzie słońca zgodnie z umową"
        assert detect_move_intent(txt, _HEX) is None

    def test_zachod_slonca_no_move(self):
        txt = "Wracam do karczmy przed zachodem słońca"
        assert detect_move_intent(txt, _HEX) is None

    def test_wschod_slonca_ascii_no_move(self):
        txt = "Ide odpoczac by stawic sie na wschod slonca w kuzni"
        assert detect_move_intent(txt, _HEX) is None

    def test_w_poludnie_no_south_move(self):
        txt = "Spotkamy się w południe przy studni"
        assert detect_move_intent(txt, _HEX) is None

    def test_po_poludniu_no_south_move(self):
        txt = "Idę do karczmy po południu odpocząć"
        assert detect_move_intent(txt, _HEX) is None

    def test_o_polnocy_no_north_move(self):
        txt = "Wyruszę stąd o północy, zanim ktoś mnie zobaczy"
        assert detect_move_intent(txt, _HEX) is None

    def test_przed_polnoca_no_north_move(self):
        txt = "Chcę wrócić przed północą"
        assert detect_move_intent(txt, _HEX) is None


# ── Correct directional uses must still fire ─────────────────────────────────

class TestDirectionalStillWorks:
    def test_ide_na_wschod(self):
        mv = detect_move_intent("Idę na wschód", _HEX)
        assert mv is not None
        assert mv["params"]["direction"] == "wschód"

    def test_ide_na_zachod(self):
        mv = detect_move_intent("Idę na zachód", _HEX)
        assert mv is not None
        assert mv["params"]["direction"] == "zachód"

    def test_ide_na_poludnie(self):
        mv = detect_move_intent("Idę na południe przez las", _HEX)
        assert mv is not None
        assert mv["params"]["direction"] == "południe"

    def test_ide_na_polnoc(self):
        mv = detect_move_intent("Ruszam na północ", _HEX)
        assert mv is not None
        assert mv["params"]["direction"] == "północ"

    def test_solar_plus_real_direction(self):
        # "o zachodzie słońca, idę na zachód" — solar stripped, real direction remains
        txt = "O zachodzie słońca ruszam na zachód w stronę gór"
        mv = detect_move_intent(txt, _HEX)
        assert mv is not None
        assert mv["params"]["direction"] == "zachód"

    def test_noon_plus_real_direction(self):
        # "w południe idę na południe" — noon stripped, directional south remains
        txt = "W południe idę na południe przez targi"
        mv = detect_move_intent(txt, _HEX)
        assert mv is not None
        assert mv["params"]["direction"] == "południe"


# ── Vague move detection ──────────────────────────────────────────────────────

class TestVagueMoveGuard:
    def test_wschod_slonca_vague_false(self):
        # After stripping solar idiom "wschód słońca", if no other direction exists
        # and no movement verb survives, vague should be False.
        # This turn has "Idę" (verb) but NO remaining direction after strip → vague=True
        # is the correct result (PM3 named-dest path runs but finds nothing; LLM handles).
        # Key: must NOT be classified as a real MOVE (det_move_intent==None checked above).
        txt = "Idę odpocząć do pokoju by stawić się na wschód słońca w Kuzni Brunona"
        mv = detect_move_intent(txt, _HEX)
        assert mv is None  # no hex move fired — that's the bug fix

    def test_real_direction_not_vague(self):
        txt = "Idę na północ"
        assert detect_vague_move_intent(txt) is False

    def test_solar_idiom_only_still_vague(self):
        # "Idę na wschód słońca" stripped → "Idę na  " → verb, no direction → vague
        txt = "Idę na wschód słońca"
        assert detect_vague_move_intent(txt) is True
