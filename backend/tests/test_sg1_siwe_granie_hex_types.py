"""TDD: SG-1 #1481 — nowe typy terenu Siwych Grań (lodowiec, siarka, las_iglasty).

Pilnuje trzech warstw wpięcia:
  A) rejestracja + wartości startowe w ``hex_type_config``
  B) hooki w kodzie: pule spotkań, mapowanie na tagi wrogów, DC zbieractwa
  C) silnik podróży realnie liczy koszt lodowca (A* omija drogi teren)
  D) regresja: istniejące typy nietknięte

Wzór: test_issue933_kresy_hex_types.py (analogiczna rejestracja typów dla Kresów).
"""
import sqlite3
import sys

import pytest

sys.path.insert(0, "/app")

from app.core.db_runtime import resolve_db_path
from app.services.encounter_service import _normalize_hex_terrain
from app.services.herb_gathering_service import TERRAIN_DC
from app.services.hex_travel_service import (
    _WORLD_ENCOUNTER_FALLBACK_POOLS,
    find_path,
)

SG1_TYPES = ("lodowiec", "siarka", "las_iglasty")


@pytest.fixture
def conn():
    c = sqlite3.connect(resolve_db_path())
    c.row_factory = sqlite3.Row
    yield c
    c.close()


def _cfg(conn, hex_type: str) -> sqlite3.Row:
    row = conn.execute(
        "SELECT * FROM hex_type_config WHERE hex_type=?", (hex_type,)
    ).fetchone()
    assert row is not None, f"{hex_type!r} nie jest zarejestrowany w hex_type_config"
    return row


# ── A. Rejestracja + wartości startowe ───────────────────────────────────────

@pytest.mark.parametrize("hex_type,label", [
    ("lodowiec", "Lodowiec"),
    ("siarka", "Pola siarkowe"),
    ("las_iglasty", "Las iglasty"),
])
def test_typ_zarejestrowany_z_polska_etykieta(conn, hex_type, label):
    row = _cfg(conn, hex_type)
    assert row["label"] == label
    assert row["is_active"] == 1


@pytest.mark.parametrize("hex_type", SG1_TYPES)
def test_typy_sa_przechodnie(conn, hex_type):
    """Wszystkie trzy to teren do przejścia — lodowiec = przeprawa, nie ściana (grania ma 0)."""
    assert _cfg(conn, hex_type)["is_passable"] == 1


def test_lodowiec_najdrozszy_przechodni_teren(conn):
    """§5: lodowiec = wysoki koszt marszu. Drożej niż mountains, taniej niż swamp."""
    lodowiec = _cfg(conn, "lodowiec")["travel_hours"]
    mountains = _cfg(conn, "mountains")["travel_hours"]
    swamp = _cfg(conn, "swamp")["travel_hours"]

    assert lodowiec == pytest.approx(3.5)
    assert lodowiec > mountains, f"lodowiec {lodowiec} musi być droższy niż mountains {mountains}"
    assert lodowiec < swamp, f"lodowiec {lodowiec} nie powinien bić bagna {swamp}"

    # Najdroższy teren, po którym da się iść — poza bagnem.
    najdrozszy = conn.execute(
        "SELECT MAX(travel_hours) FROM hex_type_config "
        "WHERE is_passable=1 AND is_active=1 AND hex_type != 'swamp'"
    ).fetchone()[0]
    assert lodowiec == pytest.approx(najdrozszy)


def test_siarka_sredni_koszt_ale_wysokie_ryzyko(conn):
    """§5: siarka = średni marsz + ryzyko. Drugi najgroźniejszy biom po bagnie."""
    siarka = _cfg(conn, "siarka")
    assert siarka["travel_hours"] == pytest.approx(2.0)
    assert siarka["encounter_base_chance"] == pytest.approx(0.35)
    assert siarka["encounter_base_chance"] > _cfg(conn, "forest")["encounter_base_chance"]
    assert siarka["encounter_base_chance"] < _cfg(conn, "swamp")["encounter_base_chance"]


def test_las_iglasty_lagodniejszy_niz_las_lisciasty(conn):
    """§5 wprost: „łagodniejszy encounter pool" niż zwykły las, ten sam koszt marszu."""
    bor = _cfg(conn, "las_iglasty")
    las = _cfg(conn, "forest")
    assert bor["travel_hours"] == pytest.approx(las["travel_hours"])
    assert bor["encounter_base_chance"] < las["encounter_base_chance"]


def test_obozowanie_na_lodowcu_najbardziej_ryzykowne(conn):
    """§5 chce zakazu obozowania; silnik nie ma twardego hooka, więc boost = miękka bariera.

    Gdy zakaz zostanie wdrożony, ten test należy zastąpić testem twardej blokady.
    """
    lodowiec = _cfg(conn, "lodowiec")["camp_encounter_boost"]
    assert lodowiec == pytest.approx(0.60)
    najwyzszy = conn.execute(
        "SELECT MAX(camp_encounter_boost) FROM hex_type_config WHERE is_active=1"
    ).fetchone()[0]
    assert lodowiec == pytest.approx(najwyzszy)


def test_kolory_map_sa_unikalne(conn):
    """Nowy teren nie może dzielić koloru z istniejącym — inaczej mapa kłamie."""
    for hex_type in SG1_TYPES:
        kolor = _cfg(conn, hex_type)["map_color"]
        kolizje = [
            r["hex_type"] for r in conn.execute(
                "SELECT hex_type FROM hex_type_config WHERE map_color=? AND hex_type != ?",
                (kolor, hex_type),
            ).fetchall()
        ]
        assert not kolizje, f"{hex_type} dzieli kolor {kolor} z {kolizje}"


def test_kazdy_typ_ma_ikone(conn):
    for hex_type in SG1_TYPES:
        assert (_cfg(conn, hex_type)["map_icon"] or "").strip(), f"{hex_type} bez map_icon"


# ── B. Hooki w kodzie ────────────────────────────────────────────────────────

@pytest.mark.parametrize("hex_type", SG1_TYPES)
def test_pula_spotkan_fallback_istnieje(hex_type):
    """Bez puli fallback spotkanie na nowym biomie cicho przepada (#1146)."""
    pula = _WORLD_ENCOUNTER_FALLBACK_POOLS.get(hex_type)
    assert pula, f"{hex_type} nie ma puli fallback"


@pytest.mark.parametrize("hex_type", SG1_TYPES)
def test_klucze_wrogow_z_puli_istnieja_w_bazie(conn, hex_type):
    """Klucz spoza game_config_enemies = spotkanie, którego nie da się zmaterializować."""
    for klucz in _WORLD_ENCOUNTER_FALLBACK_POOLS[hex_type]:
        row = conn.execute(
            "SELECT 1 FROM game_config_enemies WHERE key=?", (klucz,)
        ).fetchone()
        assert row is not None, f"pula {hex_type} wskazuje na nieistniejącego wroga {klucz!r}"


@pytest.mark.parametrize("hex_type,tag", [
    ("lodowiec", "mountain"),
    ("siarka", "mountain"),
    ("las_iglasty", "forest"),
])
def test_mapowanie_na_tagi_wrogow(hex_type, tag):
    """Bez mapowania filtr terenu zwraca pustkę → relax-to-all → off-theme wrogowie (#1369)."""
    assert _normalize_hex_terrain(hex_type) == tag


def test_dc_zbieractwa_ziol():
    """Lód i siarka = jałowizna (Hard 16); bór iglasty uboższy w runo niż las liściasty."""
    assert TERRAIN_DC["lodowiec"] == 16
    assert TERRAIN_DC["siarka"] == 16
    assert TERRAIN_DC["las_iglasty"] > TERRAIN_DC["forest"]


# ── C. Silnik podróży realnie liczy koszt ────────────────────────────────────

def test_astar_omija_lodowiec_wybierajac_dluzsza_tania_trase(conn):
    """Dowód, że koszt lodowca trafia do wyznaczania trasy, a nie tylko do UI.

    Krótsza trasa (2 kroki) prowadzi przez lodowiec, dłuższa (3 kroki) przez równiny.
    Przy travel_hours 3.5 vs 1.0 A* musi wybrać dłuższą.
    """
    hex_type_cfg = {
        r["hex_type"]: dict(r) for r in conn.execute(
            "SELECT * FROM hex_type_config WHERE is_active=1"
        ).fetchall()
    }
    hexes = {
        (q, r): {"hex_type": t, "teleport_edges": [], "encounter_pool": [], "encounter_chance": 0.0}
        for q, r, t in [
            (0, 0, "plains"),
            (1, 0, "lodowiec"),   # skrót przez lód
            (2, 0, "plains"),     # cel
            (1, -1, "plains"),    # objazd
            (2, -1, "plains"),
        ]
    }

    sciezka = find_path((0, 0), (2, 0), hexes, hex_type_cfg)

    assert sciezka is not None, "A* nie znalazł żadnej trasy"
    assert (1, 0) not in sciezka, f"A* poszedł przez lodowiec mimo kosztu 3.5: {sciezka}"
    assert sciezka[-1] == (2, 0)


def test_lodowiec_nie_wypada_z_grafu_podrozy(conn):
    """is_passable=1 ⇒ da się wejść, gdy nie ma tańszej alternatywy (przeprawa, nie ściana)."""
    hex_type_cfg = {
        r["hex_type"]: dict(r) for r in conn.execute(
            "SELECT * FROM hex_type_config WHERE is_active=1"
        ).fetchall()
    }
    hexes = {
        (q, r): {"hex_type": t, "teleport_edges": [], "encounter_pool": [], "encounter_chance": 0.0}
        for q, r, t in [(0, 0, "plains"), (1, 0, "lodowiec"), (2, 0, "plains")]
    }

    sciezka = find_path((0, 0), (2, 0), hexes, hex_type_cfg)

    assert sciezka == [(0, 0), (1, 0), (2, 0)], f"lodowiec zablokował jedyną trasę: {sciezka}"


# ── D. Regresja ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("hex_type,godziny,kolor", [
    ("forest", 2.0, "#2d5a2d"),
    ("mountains", 3.0, "#6a6a6a"),
    ("snow", 1.5, "#d8e8e8"),
    ("grania", 3.0, "#5a5a66"),
])
def test_istniejace_typy_nietkniete(conn, hex_type, godziny, kolor):
    row = _cfg(conn, hex_type)
    assert row["travel_hours"] == pytest.approx(godziny)
    assert row["map_color"] == kolor


def test_kazdy_typ_uzyty_na_mapie_ma_konfiguracje(conn):
    """Teren na hexie bez wpisu w hex_type_config = dziura w kosztach i w legendzie."""
    uzyte = {
        r["hex_type"] for r in conn.execute(
            "SELECT DISTINCT hex_type FROM world_hexes WHERE map_level=0"
        ).fetchall()
    }
    znane = {
        r["hex_type"] for r in conn.execute(
            "SELECT hex_type FROM hex_type_config"
        ).fetchall()
    }
    assert not (uzyte - znane), f"typy na mapie bez konfiguracji: {sorted(uzyte - znane)}"
