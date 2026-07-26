"""test_1545_border_reconcile.py — strażnik logiki płynnych granic (#1545).

Testuje CZYSTĄ logikę (bez DB/dockera): rodziny terenu, wykrywanie twardych
skoków i mostkowanie. Ładowanie regionów z DB (`load_region`) testuje smoke
ręczny na hoście — tu tylko deterministyczny rdzeń.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

br = pytest.importorskip("border_reconcile", reason="scripts/border_reconcile.py (uruchom lokalnie)")


def _hex(q, r, t, **kw):
    return {"q": q, "r": r, "hex_type": t, "location_key": kw.get("lk"), "label": kw.get("lb")}


def test_families_cover_known_types():
    """Kluczowe typy krain mają rodzinę (nie wpadają w domyślny OPEN po cichu)."""
    for t in ("snow", "lodowiec", "sol", "martwa_ziemia", "czarny_las",
              "trzesawisko", "grania", "river", "heath", "forest"):
        assert t in br.FAMILY, f"{t} bez rodziny"


def test_forbidden_matches_piotr_examples():
    """Przykłady Piotra: góry↔woda i sól/martwa↔woda = twarde skoki."""
    assert br.is_harsh("MOUNTAIN", "WATER")
    assert br.is_harsh("WASTE", "WATER")
    assert br.is_harsh("MOUNTAIN", "WASTE")
    # naturalne przejścia NIE są twarde
    assert not br.is_harsh("FOREST", "OPEN")     # las → wrzos
    assert not br.is_harsh("WETLAND", "WATER")   # bagno → woda
    assert not br.is_harsh("MOUNTAIN", "HILL")   # góra → pogórze
    assert not br.is_harsh("WASTE", "OPEN")      # martwa ziemia → wrzos


def test_reconcile_closes_mountain_water_jump():
    """Styk góra↔jezioro domyka się mostkiem (pogórze), bez skoków po."""
    A = {(0, 0): _hex(0, 0, "snow"), (1, 0): _hex(1, 0, "mountain")}
    B = {(0, 1): _hex(0, 1, "lake"), (1, 1): _hex(1, 1, "river")}
    _, harsh0 = br.analyze(A, B)
    assert harsh0, "test-setup: powinien być twardy skok"
    changes = br.reconcile(A, B, "gory", "woda")
    _, harsh1 = br.analyze(A, B)
    assert not harsh1, "reconcile nie domknął skoku"
    assert changes, "brak zmian mimo twardego skoku"


def test_reconcile_smooth_border_is_noop():
    """Płynna granica (las/bagno ↔ wrzos, jak Czarnobór↔Pustkowia) = 0 zmian."""
    A = {(0, 0): _hex(0, 0, "swamp"), (1, 0): _hex(1, 0, "forest")}
    B = {(0, 1): _hex(0, 1, "heath"), (1, 1): _hex(1, 1, "heath")}
    _, harsh = br.analyze(A, B)
    assert not harsh
    assert br.reconcile(A, B, "a", "b") == []


def test_protected_hexes_never_retyped():
    """POI (location_key), road i osady nie są retypowane nawet w twardym skoku."""
    A = {(0, 0): _hex(0, 0, "mountain", lk="twierdza")}   # chroniony POI
    B = {(0, 1): _hex(0, 1, "lake")}
    changes = br.reconcile(A, B, "a", "b")
    # mostkuje stronę wody? nie — water nie ma BRIDGE_STEP; góra chroniona → brak zmian
    assert all(not (reg == "a" and q == 0 and r == 0) for reg, q, r, *_ in changes)
    assert br.protected(_hex(0, 0, "road"))
    assert br.protected(_hex(0, 0, "plains", lk="wioska"))
    assert not br.protected(_hex(0, 0, "plains"))
