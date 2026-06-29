"""
Tests for RM2 assign_location_regions.py.
Verifies known locations get correct region, idempotent re-run works.
Refs: issue #1029, #917.
"""
import sqlite3
import sys
from pathlib import Path
import pytest

# In container: /app/tests/ -> /app/scripts/; on host: repo/backend/tests/ -> repo/scripts/
_test_file = Path(__file__).resolve()
SCRIPTS_DIR = _test_file.parents[1] / 'scripts'
if not SCRIPTS_DIR.exists():
    SCRIPTS_DIR = _test_file.parents[2] / 'scripts'
sys.path.insert(0, str(SCRIPTS_DIR))

from assign_location_regions import run, REGION_MAP


def _make_db(tmp_path: Path) -> Path:
    db = tmp_path / 'test_rm2.db'
    conn = sqlite3.connect(str(db))
    cur = conn.cursor()

    cur.executescript("""
        CREATE TABLE game_locations (
            key TEXT PRIMARY KEY,
            label TEXT,
            placement TEXT DEFAULT 'floating',
            world_hex_q INTEGER,
            world_hex_r INTEGER,
            region TEXT
        );

        CREATE TABLE world_hexes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            q INTEGER NOT NULL,
            r INTEGER NOT NULL,
            map_level INTEGER NOT NULL DEFAULT 0,
            hex_type TEXT,
            label TEXT,
            region TEXT NOT NULL DEFAULT 'kresy'
        );

        CREATE TABLE world_regions (
            key TEXT PRIMARY KEY,
            label TEXT,
            status TEXT DEFAULT 'coming'
        );
    """)

    # Canonical locations (all regions)
    locs = [
        ('vilnograd_stolica', 'Vilnograd, Stolica', 'floating', None, None, None),
        ('volhynia_kupiecka', 'Volhynia, Miasto Kupieckie', 'floating', None, None, None),
        ('klasztor_iskry_centrum', 'Klasztor Iskry, Centrum Wiary', 'floating', None, None, None),
        ('strazyn', 'Strażyn, Twierdza Graniczna', 'placed', 33, 6, None),
        ('wolanka', 'Wolanka, Wioska Górnicza', 'placed', 21, 1, None),
        ('brzezino', 'Brzezino, Wioska Drwali', 'placed', 1, 0, None),
        ('bor_zmarlych', 'Bór Zmarłych', 'floating', None, None, None),
        ('trzesawiska_mgiel', 'Trzęsawiska Mgieł', 'floating', None, None, None),
        ('step_wilkow', 'Step Wilków', 'floating', None, None, None),
        ('kopalnia_czarnego_hutmana', 'Kopalnia Czarnego Hutmana', 'placed', 0, 0, None),
        ('krzyz_gor', 'Krzyż Gór', 'floating', None, None, None),
        ('czarne_skaly', 'Czarne Skały, Wulkan', 'floating', None, None, None),
        ('czarnogrod_port', 'Czarnogród, Port', 'floating', None, None, None),
        ('zatoka_topielcow', 'Zatoka Topielców', 'floating', None, None, None),
        ('wybrzeze_lez', 'Wybrzeże Łez', 'floating', None, None, None),
        ('pustkowie_solne', 'Pustkowie Solne', 'floating', None, None, None),
        ('swiatynia_pradawnych', 'Świątynia Pradawnych', 'floating', None, None, None),
        ('krypta_krwawego_hrabiego', 'Krypta Krwawego Hrabiego', 'floating', None, None, None),
        ('twierdza_bezimiennego', 'Twierdza Bezimiennego', 'floating', None, None, None),
        # test fixture — should stay NULL
        ('test_loc_12345', 'Test Location', 'floating', None, None, None),
        ('create_test_99999', 'Create Test', 'floating', None, None, None),
        ('temp_camp_1_1234', 'Obozowisko', 'placed', 5, 5, None),
    ]
    cur.executemany(
        'INSERT INTO game_locations (key,label,placement,world_hex_q,world_hex_r,region) VALUES (?,?,?,?,?,?)',
        locs
    )

    # Hexes for placed locations
    hexes = [
        (33, 6, 0, 'kresy'),
        (21, 1, 0, 'kresy'),
        (1, 0, 0, 'kresy'),
        (0, 0, 0, 'kresy'),
        (5, 5, 0, 'kresy'),
    ]
    cur.executemany(
        'INSERT INTO world_hexes (q,r,map_level,region) VALUES (?,?,?,?)',
        hexes
    )

    conn.commit()
    conn.close()
    return db


def _get_region(db: Path, key: str) -> str | None:
    conn = sqlite3.connect(str(db))
    row = conn.execute('SELECT region FROM game_locations WHERE key=?', (key,)).fetchone()
    conn.close()
    return row[0] if row else None


def _get_hex_region(db: Path, q: int, r: int) -> str | None:
    conn = sqlite3.connect(str(db))
    row = conn.execute(
        'SELECT region FROM world_hexes WHERE q=? AND r=? AND map_level=0', (q, r)
    ).fetchone()
    conn.close()
    return row[0] if row else None


# ── Known-location assertions (as named in issue #1029 acceptance) ─────────

def test_strazyn_is_kresy(tmp_path):
    db = _make_db(tmp_path)
    run(db)
    assert _get_region(db, 'strazyn') == 'kresy'


def test_wolanka_is_kresy(tmp_path):
    """Wolfsmark rename → wolanka key."""
    db = _make_db(tmp_path)
    run(db)
    assert _get_region(db, 'wolanka') == 'kresy'


def test_vilnograd_is_koronne_niziny(tmp_path):
    db = _make_db(tmp_path)
    run(db)
    assert _get_region(db, 'vilnograd_stolica') == 'koronne_niziny'


def test_kopalnia_czarnego_hutmana_is_siwe_granie(tmp_path):
    db = _make_db(tmp_path)
    run(db)
    assert _get_region(db, 'kopalnia_czarnego_hutmana') == 'siwe_granie'


def test_bor_zmarlych_is_czarnobor(tmp_path):
    db = _make_db(tmp_path)
    run(db)
    assert _get_region(db, 'bor_zmarlych') == 'czarnobor'


def test_czarnogrod_is_wybrzeze_lez(tmp_path):
    db = _make_db(tmp_path)
    run(db)
    assert _get_region(db, 'czarnogrod_port') == 'wybrzeze_lez'


def test_pustkowie_is_martwe_pustkowia(tmp_path):
    db = _make_db(tmp_path)
    run(db)
    assert _get_region(db, 'pustkowie_solne') == 'martwe_pustkowia'


def test_swiatynia_pradawnych_is_martwe_pustkowia(tmp_path):
    db = _make_db(tmp_path)
    run(db)
    assert _get_region(db, 'swiatynia_pradawnych') == 'martwe_pustkowia'


# ── Test fixtures stay NULL ─────────────────────────────────────────────────

def test_test_fixture_stays_null(tmp_path):
    db = _make_db(tmp_path)
    run(db)
    assert _get_region(db, 'test_loc_12345') is None
    assert _get_region(db, 'create_test_99999') is None


# ── Hex sync ────────────────────────────────────────────────────────────────

def test_placed_kresy_hex_unchanged(tmp_path):
    """Kresy placed location hex stays kresy."""
    db = _make_db(tmp_path)
    run(db)
    assert _get_hex_region(db, 33, 6) == 'kresy'  # strazyn
    assert _get_hex_region(db, 21, 1) == 'kresy'   # wolanka


def test_placed_nonkresy_hex_updated(tmp_path):
    """siwe_granie location updates hex from default kresy."""
    db = _make_db(tmp_path)
    run(db)
    assert _get_hex_region(db, 0, 0) == 'siwe_granie'  # kopalnia_czarnego_hutmana


def test_temp_camp_hex_stays_kresy(tmp_path):
    """Unmapped temp_camp location does not change its hex."""
    db = _make_db(tmp_path)
    run(db)
    assert _get_hex_region(db, 5, 5) == 'kresy'


# ── Idempotency ─────────────────────────────────────────────────────────────

def test_rerun_idempotent(tmp_path):
    """Running script twice produces same result, no crash."""
    db = _make_db(tmp_path)
    run(db)
    stats1 = {'vilnograd': _get_region(db, 'vilnograd_stolica')}
    run(db)
    stats2 = {'vilnograd': _get_region(db, 'vilnograd_stolica')}
    assert stats1 == stats2


def test_rerun_zero_updates(tmp_path):
    """Second run updates 0 locations (already assigned)."""
    db = _make_db(tmp_path)
    run(db)
    result = run(db)
    assert result['updated_locs'] == 0
    assert result['updated_hexes'] == 0


# ── Coverage: all REGION_MAP keys map to valid region values ────────────────

VALID_REGIONS = {
    'koronne_niziny', 'kresy', 'czarnobor',
    'siwe_granie', 'wybrzeze_lez', 'martwe_pustkowia',
}


def test_region_map_values_valid():
    invalid = {k: v for k, v in REGION_MAP.items() if v not in VALID_REGIONS}
    assert invalid == {}, f'Invalid region values: {invalid}'
