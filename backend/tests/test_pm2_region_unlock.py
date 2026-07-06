"""TDD: PM2 (#1221) — Unlock gazetteera krainy przy wejściu do nowego regionu.

Dwa poziomy:
  A) czysta funkcja ``compute_known_coords`` z parametrem ``known_regions`` —
     gazetteer liczony dla KAŻDEGO odblokowanego regionu (nie tylko origin);
  B) ``unlock_region_for_hex`` na fikcyjnej bazie in-memory (NIE dotyka realnej
     mapy świata) — wejście do nowej krainy dopisuje ją do
     ``session_flags.known_regions``, kumulatywnie i idempotentnie.
"""
import json
import sqlite3
import sys

sys.path.insert(0, "/app")

from app.services.fow_service import compute_known_coords  # noqa: E402
from app.services.hex_travel_service import unlock_region_for_hex  # noqa: E402


# ── A) predykat gazetteera dla wielu regionów ────────────────────────────────

def _row(hex_type="plains", region="kresy", location_key=None):
    return {"hex_type": hex_type, "region": region, "location_key": location_key}


def _two_region_world():
    return {
        (0, 0): _row(),                                   # discovered
        (20, 0): _row(hex_type="town", region="kresy"),   # landmark starej krainy
        (30, 0): _row(hex_type="town", region="siwe_granie"),  # landmark nowej
        (31, 0): _row(hex_type="plains", region="siwe_granie"),  # zwykły teren nowej
    }


def test_new_region_landmarks_known_after_unlock():
    """Po odblokowaniu Siwych Grań ich landmark (town) staje się known."""
    known, labelable = compute_known_coords(
        _two_region_world(), discovered_coords={(0, 0)},
        origin_region="kresy", canonical_keys=set(), bubble_radius=1,
        known_regions={"kresy", "siwe_granie"},
    )
    assert (30, 0) in known and (30, 0) in labelable, "landmark nowej krainy → known+label"
    assert (31, 0) not in known, "zwykły teren nowej krainy nie wchodzi do gazetteera"


def test_old_region_kept_after_unlock():
    """Odblokowanie nowej krainy NIE gubi landmarków starej."""
    known, _ = compute_known_coords(
        _two_region_world(), discovered_coords={(0, 0)},
        origin_region="kresy", canonical_keys=set(), bubble_radius=1,
        known_regions={"kresy", "siwe_granie"},
    )
    assert (20, 0) in known, "landmark starej krainy zostaje known"


def test_unknown_region_not_gazetteered():
    """Bez unlocku landmark obcej krainy nie jest gazetteerem W1."""
    known, _ = compute_known_coords(
        _two_region_world(), discovered_coords={(0, 0)},
        origin_region="kresy", canonical_keys=set(), bubble_radius=1,
        known_regions={"kresy"},
    )
    # (30,0) to town → wpada w W3 (świat) niezależnie; sprawdzamy zwykły teren.
    assert (31, 0) not in known, "teren nieodblokowanej krainy pozostaje ukryty"


# ── B) unlock_region_for_hex na fikcyjnej bazie ──────────────────────────────

def _fixture_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE world_hexes (
            q INTEGER, r INTEGER, map_level INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1, region TEXT
        );
        CREATE TABLE world_regions (key TEXT PRIMARY KEY, label TEXT, status TEXT);
        CREATE TABLE game_sessions (
            id INTEGER PRIMARY KEY, campaign_id INTEGER, session_flags TEXT
        );
        """
    )
    conn.execute("INSERT INTO world_hexes (q,r,map_level,is_active,region) VALUES (0,-24,0,1,'kresy')")
    conn.execute("INSERT INTO world_hexes (q,r,map_level,is_active,region) VALUES (0,-25,0,1,'siwe_granie')")
    conn.execute("INSERT INTO world_hexes (q,r,map_level,is_active,region) VALUES (9,9,0,1,NULL)")
    conn.execute("INSERT INTO world_regions (key,label,status) VALUES ('kresy','Kresy','live')")
    conn.execute("INSERT INTO world_regions (key,label,status) VALUES ('siwe_granie','Siwe Granie','live')")
    conn.execute(
        "INSERT INTO game_sessions (campaign_id, session_flags) VALUES (1, ?)",
        (json.dumps({"known_regions": ["kresy"]}),),
    )
    conn.commit()
    return conn


def _known_regions(conn) -> list:
    row = conn.execute("SELECT session_flags FROM game_sessions WHERE campaign_id=1").fetchone()
    return json.loads(row["session_flags"])["known_regions"]


def test_entering_new_region_adds_it():
    conn = _fixture_db()
    res = unlock_region_for_hex(conn, 1, 0, -25)
    assert res == {"key": "siwe_granie", "label": "Siwe Granie"}
    assert _known_regions(conn) == ["kresy", "siwe_granie"], "nowa kraina dopisana"


def test_reentering_known_region_is_noop():
    conn = _fixture_db()
    assert unlock_region_for_hex(conn, 1, 0, -24) is None, "bycie w znanej krainie → brak unlocka"
    assert _known_regions(conn) == ["kresy"], "known_regions bez zmian"


def test_old_region_never_removed():
    """Po wejściu do nowej i powrocie do starej — obie zostają."""
    conn = _fixture_db()
    unlock_region_for_hex(conn, 1, 0, -25)          # wejście do Siwych Grań
    assert unlock_region_for_hex(conn, 1, 0, -24) is None  # powrót do Kresów
    assert _known_regions(conn) == ["kresy", "siwe_granie"], "stara kraina nie znika"


def test_hex_without_region_is_safe_fallback():
    """Hex bez regionu (dziki teren) → None, brak wywrotki, known_regions nietknięte."""
    conn = _fixture_db()
    assert unlock_region_for_hex(conn, 1, 9, 9) is None
    assert _known_regions(conn) == ["kresy"]


def test_missing_known_regions_key_initialised():
    """Sesja bez klucza known_regions → helper tworzy listę zamiast wywrotki."""
    conn = _fixture_db()
    conn.execute("UPDATE game_sessions SET session_flags = ? WHERE campaign_id=1", (json.dumps({}),))
    conn.commit()
    res = unlock_region_for_hex(conn, 1, 0, -25)
    assert res == {"key": "siwe_granie", "label": "Siwe Granie"}
    assert _known_regions(conn) == ["siwe_granie"]
