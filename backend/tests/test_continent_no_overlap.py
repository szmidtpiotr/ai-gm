"""test_continent_no_overlap.py — RM5 (FAZA RM, #1032)

Weryfikuje, że żadne dwa pliki region_*.json nie dzielą tej samej pary (q, r).
Dokument referencyjny: docs/world/continent_layout.md
"""
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
# W kontenerze data/ jest bind-mountowana jako /data/
REGIONS_DIR = ROOT / "data" / "regions"
if not REGIONS_DIR.exists():
    REGIONS_DIR = Path("/data") / "regions"

ALL_REGION_FILES = sorted(REGIONS_DIR.glob("region_*.json")) if REGIONS_DIR.exists() else []


@pytest.mark.parametrize("region_file", ALL_REGION_FILES, ids=lambda p: p.stem)
def test_region_file_exists_and_valid(region_file):
    """Każdy plik region istnieje, ma wymagane pola i >50 heksów."""
    assert region_file.exists(), f"Brak pliku: {region_file}"
    data = json.loads(region_file.read_text(encoding="utf-8"))
    assert "region" in data, "Brak pola 'region'"
    assert "status" in data, "Brak pola 'status'"
    assert "hexes" in data, "Brak pola 'hexes'"
    assert len(data["hexes"]) >= 50, f"Zbyt mało heksów: {len(data['hexes'])}"


def test_no_two_regions_share_hex():
    """Zero kolizji (q,r) między wszystkimi plikami krain."""
    if not REGIONS_DIR.exists():
        pytest.skip(f"Katalog {REGIONS_DIR} nie istnieje")

    region_files = ALL_REGION_FILES
    if not region_files:
        pytest.skip("Brak plików region_*.json")

    seen: dict[tuple[int, int], str] = {}
    collisions: list[str] = []

    for rf in region_files:
        data = json.loads(rf.read_text(encoding="utf-8"))
        region_name = data.get("region", rf.stem)
        for h in data["hexes"]:
            key = (h["q"], h["r"])
            if key in seen:
                collisions.append(
                    f"({h['q']},{h['r']}) w '{region_name}' już zajęte przez '{seen[key]}'"
                )
            else:
                seen[key] = region_name

    assert not collisions, (
        f"{len(collisions)} kolizji heksów:\n" + "\n".join(collisions[:20])
    )


def test_kresy_region_in_expected_bounds():
    """Kresy mieści się w q=0..49, r=-24..49 (istniejące dane)."""
    kresy_file = REGIONS_DIR / "region_kresy.json"
    if not kresy_file.exists():
        pytest.skip("region_kresy.json nie istnieje")
    data = json.loads(kresy_file.read_text(encoding="utf-8"))
    qs = [h["q"] for h in data["hexes"]]
    rs = [h["r"] for h in data["hexes"]]
    assert min(qs) >= 0 and max(qs) <= 49, f"Kresy q poza 0..49: {min(qs)}..{max(qs)}"
    assert min(rs) >= -25 and max(rs) <= 50, f"Kresy r poza -25..50: {min(rs)}..{max(rs)}"


def test_coming_regions_have_correct_status():
    """Krainy live = kresy + siwe_granie (RM7 pilot). Reszta = coming."""
    live_regions = {"kresy", "siwe_granie"}  # siwe_granie odblokowane w RM7
    for rf in ALL_REGION_FILES:
        data = json.loads(rf.read_text(encoding="utf-8"))
        region = data.get("region")
        status = data.get("status")
        if region in live_regions:
            assert status == "live", (
                f"{rf.name}: region '{region}' powinien mieć status='live', ma '{status}'."
            )
        else:
            assert status == "coming", (
                f"{rf.name}: region '{region}' powinien mieć status='coming', ma '{status}'."
            )


@pytest.mark.parametrize("expected_region,expected_biomes", [
    ("siwe_granie",      {"snow", "mountain", "tundra"}),
    ("czarnobor",        {"forest", "swamp"}),
    ("koronne_niziny",   {"plains"}),
    ("wybrzeze_lez",     {"sea", "coast", "swamp"}),
    ("martwe_pustkowia", {"heath", "ruins"}),
])
def test_biome_profile_present(expected_region, expected_biomes):
    """Każda kraina zawiera co najmniej jeden heks każdego wymaganego biomu."""
    rf = REGIONS_DIR / f"region_{expected_region}.json"
    if not rf.exists():
        pytest.skip(f"Brak pliku: {rf}")
    data = json.loads(rf.read_text(encoding="utf-8"))
    found = {h["hex_type"] for h in data["hexes"]}
    missing = expected_biomes - found
    assert not missing, (
        f"{expected_region}: brakuje biomów {missing}. "
        f"Dostępne: {sorted(found)}"
    )
