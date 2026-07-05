"""R1 (#1241) — status krain: jedno źródło prawdy (pliki data/regions/*.json).

Weryfikuje łańcuch: plik krainy ↔ DB (world_regions) ↔ endpoint/writer:
  * migracja wyrównuje world_regions.status do statusu z plików,
  * snapshot writer (router + skrypt) czyta status z pliku, nie z hardcode'u,
  * seed_world_map.py --force bez --region odmawia (ochrona przed pełnym wipe'em).

Uruchom w kontenerze:
    docker exec ai-gm-dev-backend-1 pytest tests/test_r1_region_status.py -v
"""
import glob
import json
import os
import sqlite3
import subprocess
import sys

import pytest

REGIONS_DIR = "/data/regions"
APP_ROOT = "/app"


def _find_script(name):
    """Skrypty seed/snapshot NIE są bakowane do obrazu (chodzą na hoście .61).
    Szukamy ich w /app/scripts (gdy ktoś docker-cp) lub repo-relatywnie."""
    for cand in (
        os.path.join(APP_ROOT, "scripts", name),
        os.path.join(os.path.dirname(__file__), "..", "..", "scripts", name),
    ):
        if os.path.exists(cand):
            return os.path.abspath(cand)
    return None


def _region_files():
    return sorted(glob.glob(os.path.join(REGIONS_DIR, "region_*.json")))


def _load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ── Kanon plików ────────────────────────────────────────────────────────────

def test_region_files_present_and_valid():
    files = _region_files()
    assert files, f"brak plików krain w {REGIONS_DIR}"
    for p in files:
        d = _load(p)
        assert d.get("region"), f"{p}: brak klucza 'region'"
        assert d.get("status") in ("live", "coming", "locked"), f"{p}: zły status {d.get('status')!r}"


def test_kresy_and_siwe_granie_are_live():
    """Odblokowane krainy (RM7) — plik = źródło prawdy."""
    for key in ("kresy", "siwe_granie"):
        d = _load(os.path.join(REGIONS_DIR, f"region_{key}.json"))
        assert d["status"] == "live", f"{key}: plik mówi {d['status']!r}, oczekiwano 'live'"


# ── Brak hardcode'ów statusu ────────────────────────────────────────────────

def test_no_region_meta_hardcode_in_router():
    from app.routers import hex_world
    assert not hasattr(hex_world, "_REGION_META"), "router wciąż ma hardcode _REGION_META"


def test_no_region_meta_hardcode_in_snapshot_script():
    path = _find_script("snapshot_world_map.py")
    if path is None:
        pytest.skip("snapshot_world_map.py niebakowany do obrazu — sprawdź na hoście .61")
    src = open(path, encoding="utf-8").read()
    assert "REGION_META = {" not in src, "skrypt snapshotu wciąż ma hardcode REGION_META"


# ── Writer snapshotu czyta status z pliku ───────────────────────────────────

def test_router_reads_status_from_file():
    from app.routers.hex_world import _region_file_meta
    meta = _region_file_meta("siwe_granie")
    assert meta is not None and meta["status"] == "live", "writer nie czyta statusu 'live' z pliku siwe_granie"
    assert _region_file_meta("nieistniejaca_kraina_xyz") is None, "brak pliku → oczekiwano None (nowa kraina)"


# ── Migracja wyrównuje DB do plików (idempotentna) ──────────────────────────

def test_migration_aligns_db_status_to_files(tmp_path):
    from app.migrations_admin import _align_region_status_to_files, _ensure_region_schema

    db = tmp_path / "t.db"
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    _ensure_region_schema(conn)  # seed z domyślnymi statusami (siwe_granie=coming)

    # przed: seed twierdzi siwe_granie=coming, plik mówi live → rozjazd
    pre = conn.execute("SELECT status FROM world_regions WHERE key='siwe_granie'").fetchone()
    assert pre["status"] == "coming"

    _align_region_status_to_files(conn, regions_dir=REGIONS_DIR)

    # po: DB == plik dla każdej krainy z plikiem
    for p in _region_files():
        d = _load(p)
        row = conn.execute("SELECT status FROM world_regions WHERE key=?", (d["region"],)).fetchone()
        if row is not None:
            assert row["status"] == d["status"], f"{d['region']}: DB={row['status']} != plik={d['status']}"

    # idempotencja: drugi przebieg nic nie zmienia
    _align_region_status_to_files(conn, regions_dir=REGIONS_DIR)
    row = conn.execute("SELECT status FROM world_regions WHERE key='siwe_granie'").fetchone()
    assert row["status"] == "live"
    conn.close()


def test_migration_missing_dir_is_noop(tmp_path):
    from app.migrations_admin import _align_region_status_to_files, _ensure_region_schema

    db = tmp_path / "t.db"
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    _ensure_region_schema(conn)
    # brak katalogu → no-op, seed defaults zostają
    _align_region_status_to_files(conn, regions_dir=str(tmp_path / "nope"))
    row = conn.execute("SELECT status FROM world_regions WHERE key='kresy'").fetchone()
    assert row["status"] == "live"
    conn.close()


# ── Seed: --force bez --region odmawia ──────────────────────────────────────

def test_seed_force_without_region_refuses():
    path = _find_script("seed_world_map.py")
    if path is None:
        pytest.skip("seed_world_map.py niebakowany do obrazu — sprawdź na hoście .61")
    r = subprocess.run(
        [sys.executable, path, "--force"],
        text=True, capture_output=True,
    )
    assert r.returncode == 2, f"oczekiwano exit 2, było {r.returncode}. stderr={r.stderr!r}"
    assert "--region" in r.stderr, f"komunikat nie wspomina --region: {r.stderr!r}"
