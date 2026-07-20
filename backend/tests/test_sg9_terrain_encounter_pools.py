"""TDD: SG-9 #1481 — domyślne pule spotkań per teren jako DANE, nie kod.

Do tej pory pule dla terenów bez własnego `encounter_pool` na heksie siedziały
w słowniku `_WORLD_ENCOUNTER_FALLBACK_POOLS` w `hex_travel_service`. Skutek: żeby
zmienić, kto zaczepia na lodowcu, trzeba było wydać kod. Teraz pula domyślna stoi
w `hex_type_config.default_encounter_pool` — tam, gdzie reszta parametrów terenu
(koszt marszu, szansa spotkania, ryzyko obozu).

Kolejność źródeł: pula na heksie → pula terenu z konfiguracji → stałe w kodzie.
"""
import json
import sqlite3

import pytest

from app.services import hex_travel_service as hts


@pytest.fixture()
def conn():
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.executescript(
        """
        CREATE TABLE hex_type_config (
            hex_type TEXT PRIMARY KEY, label TEXT, travel_hours REAL,
            encounter_base_chance REAL, default_encounter_pool TEXT
        );
        """
    )
    db.executemany(
        "INSERT INTO hex_type_config (hex_type,label,travel_hours,encounter_base_chance,"
        "default_encounter_pool) VALUES (?,?,?,?,?)",
        [
            ("lodowiec", "Lodowiec", 3.5, 0.25,
             json.dumps(["widmo_lodowe", "zamarzniety_pielgrzym"])),
            ("las_iglasty", "Las iglasty", 2.0, 0.22, json.dumps(["wolf", "bandit", "goblin"])),
            ("siarka", "Pola siarkowe", 2.0, 0.35, None),
        ],
    )
    db.commit()
    return db


def test_pula_z_konfiguracji_terenu(conn):
    pool = hts.terrain_default_pool(conn, "lodowiec")
    assert pool == ["widmo_lodowe", "zamarzniety_pielgrzym"]


def test_teren_bez_puli_w_danych_spada_do_stalych_w_kodzie(conn):
    """siarka ma NULL w konfiguracji → bierzemy to, co zna kod."""
    pool = hts.terrain_default_pool(conn, "siarka")
    assert pool == hts._WORLD_ENCOUNTER_FALLBACK_POOLS["siarka"]


def test_nieznany_teren_daje_pule_awaryjna(conn):
    assert hts.terrain_default_pool(conn, "nie_ma_takiego") == hts._WORLD_ENCOUNTER_FALLBACK_DEFAULT


def test_brak_kolumny_nie_wywraca_odczytu():
    """Stara baza sprzed migracji — degradacja do stałych, bez wyjątku."""
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.execute("CREATE TABLE hex_type_config (hex_type TEXT PRIMARY KEY, label TEXT)")
    db.execute("INSERT INTO hex_type_config VALUES ('lodowiec','Lodowiec')")
    db.commit()
    assert hts.terrain_default_pool(db, "lodowiec") == hts._WORLD_ENCOUNTER_FALLBACK_POOLS["lodowiec"]


def test_pula_na_heksie_ma_pierwszenstwo_przed_terenem(conn):
    """Heks z własną pulą (np. okolice Sanktuarium) nie daje się nadpisać terenowi."""
    hex_data = {"hex_type": "lodowiec", "encounter_pool": ["straznik_rdzenia"]}
    assert hts._pick_encounter_enemy(hex_data, conn=conn) == "straznik_rdzenia"


def test_heks_bez_puli_bierze_z_terenu(conn):
    hex_data = {"hex_type": "lodowiec", "encounter_pool": []}
    assert hts._pick_encounter_enemy(hex_data, conn=conn) in (
        "widmo_lodowe", "zamarzniety_pielgrzym")


def test_stary_wywolanie_bez_polaczenia_dalej_dziala():
    """`_pick_encounter_enemy` bywa wołane bez conn — musi działać jak dawniej."""
    hex_data = {"hex_type": "las_iglasty", "encounter_pool": []}
    assert hts._pick_encounter_enemy(hex_data) in hts._WORLD_ENCOUNTER_FALLBACK_POOLS["las_iglasty"]
