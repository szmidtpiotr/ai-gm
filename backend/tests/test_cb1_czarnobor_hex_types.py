"""TDD: CB-1 (umbrella Czarnobór) — nowe typy terenu (czarny_las, trzesawisko, step).

Pilnuje wpięcia trzech nowych terenów Czarnoboru (docs/world/regions/czarnobor.md §5):
  A) rejestracja + wartości startowe marszu/ryzyka w ``hex_type_config``
  B) hooki w kodzie: pule spotkań, mapowanie na tagi wrogów, DC zbieractwa
  C) regresja: istniejące typy (w tym maks SG-1) nietknięte

Wzór: test_sg1_siwe_granie_hex_types.py (analogiczna rejestracja typów dla Grań).
CB-1 NIE seeduje regionu (to CB-3) — sprawdzamy więc tylko konfigurację, nie world_hexes.
"""
import sqlite3
import sys

import pytest

sys.path.insert(0, "/app")

from app.core.db_runtime import resolve_db_path
from app.services.encounter_service import _normalize_hex_terrain
from app.services.herb_gathering_service import TERRAIN_DC, DEFAULT_DC
from app.services.hex_travel_service import _WORLD_ENCOUNTER_FALLBACK_POOLS

CB1_TYPES = ("czarny_las", "trzesawisko", "step")


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
    ("czarny_las", "Czarny las"),
    ("trzesawisko", "Trzęsawisko"),
    ("step", "Step"),
])
def test_typ_zarejestrowany_z_polska_etykieta(conn, hex_type, label):
    row = _cfg(conn, hex_type)
    assert row["label"] == label
    assert row["is_active"] == 1


@pytest.mark.parametrize("hex_type", CB1_TYPES)
def test_typy_sa_przechodnie(conn, hex_type):
    """Wszystkie trzy to teren do przejścia — nie ściany (grania ma is_passable 0)."""
    assert _cfg(conn, hex_type)["is_passable"] == 1


def test_czarny_las_wysoki_koszt_marszu(conn):
    """§5: Bór Zmarłych spowalnia — koszt wysoki (jak góry), powyżej zwykłego lasu."""
    czarny = _cfg(conn, "czarny_las")["travel_hours"]
    forest = _cfg(conn, "forest")["travel_hours"]
    assert czarny == pytest.approx(3.0)
    assert czarny > forest


def test_trzesawisko_wysoki_koszt_ale_nie_bije_maksa_przechodniego(conn):
    """§5: trzęsawisko wysoki koszt; nie przekracza lodowca (maks przechodni z SG-1) ani bagna."""
    trz = _cfg(conn, "trzesawisko")["travel_hours"]
    lodowiec = _cfg(conn, "lodowiec")["travel_hours"]
    swamp = _cfg(conn, "swamp")["travel_hours"]
    assert trz == pytest.approx(3.5)
    assert trz <= lodowiec, "trzęsawisko nie może zdetronizować lodowca z testu SG-1"
    assert trz < swamp


def test_step_niski_koszt_marszu(conn):
    """§5: step — trawy po horyzont, szybki marsz (jak równiny)."""
    step = _cfg(conn, "step")["travel_hours"]
    plains = _cfg(conn, "plains")["travel_hours"]
    assert step == pytest.approx(1.0)
    assert step == pytest.approx(plains)


def test_ryzyko_spotkan_zgodne_z_lore(conn):
    """§5: czarny_las i trzęsawisko groźne (> forest); step spokojny (< forest)."""
    forest = _cfg(conn, "forest")["encounter_base_chance"]
    assert _cfg(conn, "czarny_las")["encounter_base_chance"] > forest
    assert _cfg(conn, "trzesawisko")["encounter_base_chance"] > forest
    assert _cfg(conn, "step")["encounter_base_chance"] < forest


def test_kolory_map_sa_unikalne(conn):
    """Nowy teren nie może dzielić koloru z istniejącym — inaczej mapa kłamie."""
    for hex_type in CB1_TYPES:
        kolor = _cfg(conn, hex_type)["map_color"]
        kolizje = [
            r["hex_type"] for r in conn.execute(
                "SELECT hex_type FROM hex_type_config WHERE map_color=? AND hex_type != ?",
                (kolor, hex_type),
            ).fetchall()
        ]
        assert not kolizje, f"{hex_type} dzieli kolor {kolor} z {kolizje}"


def test_kazdy_typ_ma_ikone(conn):
    for hex_type in CB1_TYPES:
        assert (_cfg(conn, hex_type)["map_icon"] or "").strip(), f"{hex_type} bez map_icon"


# ── B. Hooki w kodzie ────────────────────────────────────────────────────────

@pytest.mark.parametrize("hex_type", CB1_TYPES)
def test_pula_spotkan_fallback_istnieje(hex_type):
    """Bez puli fallback spotkanie na nowym biomie cicho przepada (#1146)."""
    assert _WORLD_ENCOUNTER_FALLBACK_POOLS.get(hex_type), f"{hex_type} bez puli fallback"


@pytest.mark.parametrize("hex_type", CB1_TYPES)
def test_klucze_wrogow_z_puli_istnieja_w_bazie(conn, hex_type):
    """Klucz spoza game_config_enemies = spotkanie, którego nie da się zmaterializować."""
    for klucz in _WORLD_ENCOUNTER_FALLBACK_POOLS[hex_type]:
        row = conn.execute(
            "SELECT 1 FROM game_config_enemies WHERE key=?", (klucz,)
        ).fetchone()
        assert row is not None, f"pula {hex_type} wskazuje na nieistniejącego wroga {klucz!r}"


@pytest.mark.parametrize("hex_type,tag", [
    ("czarny_las", "forest"),
    ("trzesawisko", "swamp"),
    ("step", "plains"),
])
def test_mapowanie_na_tagi_wrogow(hex_type, tag):
    """Bez mapowania filtr terenu zwraca pustkę → relax-to-all → off-theme wrogowie (#1369)."""
    assert _normalize_hex_terrain(hex_type) == tag


def test_dc_zbieractwa_ziol():
    """Martwy bór skąpy (Medium 12); trzęsawisko wilgotne jak bagno (Easy 8); step = default."""
    assert TERRAIN_DC["czarny_las"] == 12
    assert TERRAIN_DC["trzesawisko"] == 8
    assert TERRAIN_DC["trzesawisko"] == TERRAIN_DC["swamp"]
    assert TERRAIN_DC.get("step", DEFAULT_DC) == DEFAULT_DC


# ── C. Regresja ──────────────────────────────────────────────────────────────

def test_lodowiec_wciaz_najdrozszy_przechodni_teren(conn):
    """CB-1 nie może złamać niezmiennika SG-1: lodowiec = maks travel_hours (poza bagnem)."""
    najdrozszy = conn.execute(
        "SELECT MAX(travel_hours) FROM hex_type_config "
        "WHERE is_passable=1 AND is_active=1 AND hex_type != 'swamp'"
    ).fetchone()[0]
    assert _cfg(conn, "lodowiec")["travel_hours"] == pytest.approx(najdrozszy)


@pytest.mark.parametrize("hex_type,godziny,kolor", [
    ("forest", 2.0, "#2d5a2d"),
    ("plains", 1.0, "#7a9a4a"),
    ("las_iglasty", 2.0, "#1f4536"),
])
def test_istniejace_typy_nietkniete(conn, hex_type, godziny, kolor):
    row = _cfg(conn, hex_type)
    assert row["travel_hours"] == pytest.approx(godziny)
    assert row["map_color"] == kolor
