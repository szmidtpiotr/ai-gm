"""TDD: RM4 (#1031) — seed/snapshot per-region (paczki DLC jako pliki).

Weryfikuje:
- split_seed_into_regions: world_map_seed.json → region_kresy.json (round-trip diff=0 w q,r,hex_type)
- seed_world_map --region: partial seed działa (tylko ta kraina zmieniona)
- stitch: zbiera wszystkie live pliki, pomija coming
- safeguard: < 50 heksów = odmowa
- snapshot_world_map --region: dump jednej krainy z DB

Testy izolowane — własna in-memory SQLite, pliki tymczasowe, nie dotykają /data/ai_gm.db.
"""
import json
import sqlite3
import sys
import tempfile
from pathlib import Path

import pytest

import importlib.util


def _load_script(name: str):
    """Załaduj skrypt host-side z katalogu scripts/. Skip gdy niedostępny."""
    _here = Path(__file__).resolve()
    candidates = [
        _here.parent.parent / "scripts" / f"{name}.py",       # kontener po docker cp
        _here.parent.parent.parent / "scripts" / f"{name}.py",  # host (repo root)
    ]
    for p in candidates:
        if p.exists():
            spec = importlib.util.spec_from_file_location(name, p)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod
    pytest.skip(
        f"Skrypt {name}.py niedostępny — skopiuj: "
        f"docker cp scripts/{name}.py ai-gm-dev-backend-1:/app/scripts/"
    )


# ─── Pomocnicze ─────────────────────────────────────────────────────────────

def _make_hex_list(n: int, region: str = "kresy", start_q: int = 0) -> list[dict]:
    return [
        {"q": start_q + i, "r": 0, "hex_type": "plains", "label": None,
         "atmosphere": None, "encounter_chance": 0.15, "region": region}
        for i in range(n)
    ]


def _make_seed_file(tmp_dir: Path, hexes: list[dict], name: str = "world_map_seed.json") -> Path:
    data = {"name": "Kresy", "note": "test", "w": 50, "h": 50, "hexes": hexes}
    p = tmp_dir / name
    json.dump(data, open(p, "w"), ensure_ascii=False, indent=1)
    return p


def _make_region_file(tmp_dir: Path, region_key: str, hexes: list[dict],
                      status: str = "live") -> Path:
    stripped = [{k: v for k, v in h.items() if k != "region"} for h in hexes]
    data = {
        "region": region_key, "label": region_key.capitalize(),
        "status": status, "w": 50, "h": 50, "hexes": stripped,
    }
    p = tmp_dir / f"region_{region_key}.json"
    json.dump(data, open(p, "w"), ensure_ascii=False, indent=1)
    return p


# ─── split_seed_into_regions ─────────────────────────────────────────────────

def test_split_creates_region_kresy_file(tmp_path):
    """split zapisuje region_kresy.json z poprawnymi polami top-level."""
    splitter = _load_script("split_seed_into_regions")

    hexes_src = _make_hex_list(100)
    _make_seed_file(tmp_path, hexes_src)

    # Patch stałych w module
    orig_data = splitter._DATA_SEED
    orig_git = splitter._GIT_SEED
    orig_dir = splitter.REGIONS_DIR
    splitter._DATA_SEED = tmp_path / "MISSING"
    splitter._GIT_SEED = tmp_path / "world_map_seed.json"
    splitter.REGIONS_DIR = tmp_path / "regions"
    try:
        result = splitter.split()
    finally:
        splitter._DATA_SEED = orig_data
        splitter._GIT_SEED = orig_git
        splitter.REGIONS_DIR = orig_dir

    out = tmp_path / "regions" / "region_kresy.json"
    assert out.exists(), "region_kresy.json powinien być stworzony"
    d = json.load(open(out))
    assert d["region"] == "kresy"
    assert d["status"] == "live"
    assert len(d["hexes"]) == 100
    assert result["hexes"] == 100


def test_split_round_trip_diff_zero(tmp_path):
    """Diff (q,r,hex_type) między starym seedem a region_kresy.json = 0."""
    splitter = _load_script("split_seed_into_regions")

    hexes_src = _make_hex_list(200, region="kresy")
    _make_seed_file(tmp_path, hexes_src)

    orig_data = splitter._DATA_SEED
    orig_git = splitter._GIT_SEED
    orig_dir = splitter.REGIONS_DIR
    splitter._DATA_SEED = tmp_path / "MISSING"
    splitter._GIT_SEED = tmp_path / "world_map_seed.json"
    splitter.REGIONS_DIR = tmp_path / "regions"
    try:
        splitter.split()
    finally:
        splitter._DATA_SEED = orig_data
        splitter._GIT_SEED = orig_git
        splitter.REGIONS_DIR = orig_dir

    out = tmp_path / "regions" / "region_kresy.json"
    d = json.load(open(out))

    old_set = {(h["q"], h["r"], h.get("hex_type", "plains")) for h in hexes_src}
    new_set = {(h["q"], h["r"], h.get("hex_type", "plains")) for h in d["hexes"]}
    assert old_set == new_set, f"Diff nie zero: {old_set.symmetric_difference(new_set)}"


def test_split_safeguard_refuses_small_seed(tmp_path):
    """Split odmawia gdy < 50 heksów."""
    splitter = _load_script("split_seed_into_regions")

    hexes_src = _make_hex_list(10)
    _make_seed_file(tmp_path, hexes_src)

    orig_data = splitter._DATA_SEED
    orig_git = splitter._GIT_SEED
    orig_dir = splitter.REGIONS_DIR
    splitter._DATA_SEED = tmp_path / "MISSING"
    splitter._GIT_SEED = tmp_path / "world_map_seed.json"
    splitter.REGIONS_DIR = tmp_path / "regions"
    try:
        with pytest.raises(SystemExit):
            splitter.split()
    finally:
        splitter._DATA_SEED = orig_data
        splitter._GIT_SEED = orig_git
        splitter.REGIONS_DIR = orig_dir


# ─── seed_world_map stitch logic ─────────────────────────────────────────────

def test_stitch_collects_live_regions_only(tmp_path):
    """_stitch_hexes zbiera heksy tylko z live plików, pomija coming."""
    seeder = _load_script("seed_world_map")

    regions_dir = tmp_path / "regions"
    regions_dir.mkdir()

    _make_region_file(regions_dir, "kresy", _make_hex_list(60), status="live")
    _make_region_file(regions_dir, "siwe_granie", _make_hex_list(60, region="siwe_granie", start_q=100), status="coming")

    orig_rd = seeder.REGIONS_DIR
    orig_ds = seeder._DATA_SEED
    orig_gs = seeder._GIT_SEED
    seeder.REGIONS_DIR = regions_dir
    seeder._DATA_SEED = tmp_path / "MISSING"
    seeder._GIT_SEED = tmp_path / "MISSING"
    try:
        hexes = seeder._stitch_hexes()
    finally:
        seeder.REGIONS_DIR = orig_rd
        seeder._DATA_SEED = orig_ds
        seeder._GIT_SEED = orig_gs

    regions_in_result = {h.get("region") for h in hexes}
    assert "kresy" in regions_in_result
    assert "siwe_granie" not in regions_in_result
    assert len(hexes) == 60


def test_stitch_combines_multiple_live_regions(tmp_path):
    """Stitch łączy heksy z wielu live krain."""
    seeder = _load_script("seed_world_map")

    regions_dir = tmp_path / "regions"
    regions_dir.mkdir()

    _make_region_file(regions_dir, "kresy", _make_hex_list(60), status="live")
    _make_region_file(regions_dir, "siwe_granie",
                      _make_hex_list(70, region="siwe_granie", start_q=100), status="live")

    orig_rd = seeder.REGIONS_DIR
    orig_ds = seeder._DATA_SEED
    orig_gs = seeder._GIT_SEED
    seeder.REGIONS_DIR = regions_dir
    seeder._DATA_SEED = tmp_path / "MISSING"
    seeder._GIT_SEED = tmp_path / "MISSING"
    try:
        hexes = seeder._stitch_hexes()
    finally:
        seeder.REGIONS_DIR = orig_rd
        seeder._DATA_SEED = orig_ds
        seeder._GIT_SEED = orig_gs

    assert len(hexes) == 130
    regions_in = {h.get("region") for h in hexes}
    assert "kresy" in regions_in and "siwe_granie" in regions_in


def test_stitch_fallback_to_legacy_seed(tmp_path):
    """Gdy brak plików region_*.json → stitch fallback do legacy world_map_seed.json."""
    seeder = _load_script("seed_world_map")

    regions_dir = tmp_path / "regions"
    regions_dir.mkdir()  # pusty katalog

    legacy = tmp_path / "world_map_seed.json"
    legacy_hexes = _make_hex_list(55)
    json.dump({"name": "Kresy", "w": 50, "h": 50, "hexes": legacy_hexes},
              open(legacy, "w"), ensure_ascii=False)

    orig_rd = seeder.REGIONS_DIR
    orig_ds = seeder._DATA_SEED
    orig_gs = seeder._GIT_SEED
    seeder.REGIONS_DIR = regions_dir
    seeder._DATA_SEED = tmp_path / "MISSING"
    seeder._GIT_SEED = legacy
    try:
        hexes = seeder._stitch_hexes()
    finally:
        seeder.REGIONS_DIR = orig_rd
        seeder._DATA_SEED = orig_ds
        seeder._GIT_SEED = orig_gs

    assert len(hexes) == 55
    assert all(h.get("region") == "kresy" for h in hexes)


# ─── safeguard ───────────────────────────────────────────────────────────────

def test_load_region_file_raises_on_missing(tmp_path):
    """_load_region_file sys.exit gdy plik nie istnieje."""
    seeder = _load_script("seed_world_map")

    with pytest.raises(SystemExit):
        seeder._load_region_file(tmp_path / "nonexistent.json")


# ─── snapshot_world_map logic ────────────────────────────────────────────────

def test_save_region_writes_correct_format(tmp_path):
    """_save_region zapisuje poprawny format JSON z top-level region/label/status."""
    snapper = _load_script("snapshot_world_map")

    orig_dir = snapper.REGIONS_DIR
    snapper.REGIONS_DIR = tmp_path / "regions"
    try:
        hexes = [{"q": i, "r": 0, "hex_type": "plains", "label": None,
                  "atmosphere": None, "encounter_chance": 0.15, "region": "kresy"}
                 for i in range(60)]
        out = snapper._save_region(hexes, "kresy")
    finally:
        snapper.REGIONS_DIR = orig_dir

    d = json.load(open(out))
    assert d["region"] == "kresy"
    assert d["status"] == "live"
    assert len(d["hexes"]) == 60
    # region nie powinien być w każdym heksie (jest top-level)
    assert "region" not in d["hexes"][0]


def test_save_region_strips_region_from_hex_rows(tmp_path):
    """_save_region usuwa pole 'region' z każdego heksa (jest w top-level)."""
    snapper = _load_script("snapshot_world_map")

    orig_dir = snapper.REGIONS_DIR
    snapper.REGIONS_DIR = tmp_path / "regions"
    try:
        hexes = [{"q": 0, "r": 0, "hex_type": "forest", "label": "las",
                  "atmosphere": None, "encounter_chance": 0.2, "region": "czarnobor"}]
        out = snapper._save_region(hexes, "czarnobor")
    finally:
        snapper.REGIONS_DIR = orig_dir

    d = json.load(open(out))
    assert "region" not in d["hexes"][0]
    assert d["region"] == "czarnobor"
    assert d["hexes"][0]["hex_type"] == "forest"


# ─── full round-trip (split → stitch) ────────────────────────────────────────

def test_split_stitch_round_trip(tmp_path):
    """Split → stitch zachowuje wszystkie heksy Kresów (round-trip kompletny)."""
    splitter = _load_script("split_seed_into_regions")
    seeder = _load_script("seed_world_map")

    hexes_src = _make_hex_list(100)
    _make_seed_file(tmp_path, hexes_src)

    # Split
    orig_data = splitter._DATA_SEED
    orig_git = splitter._GIT_SEED
    orig_dir = splitter.REGIONS_DIR
    splitter._DATA_SEED = tmp_path / "MISSING"
    splitter._GIT_SEED = tmp_path / "world_map_seed.json"
    splitter.REGIONS_DIR = tmp_path / "regions"
    try:
        splitter.split()
    finally:
        splitter._DATA_SEED = orig_data
        splitter._GIT_SEED = orig_git
        splitter.REGIONS_DIR = orig_dir

    # Stitch
    orig_rd = seeder.REGIONS_DIR
    orig_ds = seeder._DATA_SEED
    orig_gs = seeder._GIT_SEED
    seeder.REGIONS_DIR = tmp_path / "regions"
    seeder._DATA_SEED = tmp_path / "MISSING"
    seeder._GIT_SEED = tmp_path / "MISSING"
    try:
        stitched = seeder._stitch_hexes()
    finally:
        seeder.REGIONS_DIR = orig_rd
        seeder._DATA_SEED = orig_ds
        seeder._GIT_SEED = orig_gs

    assert len(stitched) == 100
    src_set = {(h["q"], h["r"], h.get("hex_type", "plains")) for h in hexes_src}
    res_set = {(h["q"], h["r"], h.get("hex_type", "plains")) for h in stitched}
    assert src_set == res_set, f"Round-trip diff: {src_set.symmetric_difference(res_set)}"
