"""test_1542_region_blocks.py — strażnik wzoru bloków kontynentu (#1542, M-30).

Kodyfikuje układ bloków krain (`scripts/region_blocks.py`) i pilnuje, by:
  1. wzór offsetów był stały (q_off=50·col, r_off=75·row−25·col),
  2. pas row=0 leżał na ekranie NA RÓWNI z Kresami (kompensacja shear),
  3. generator (`generate_region_map.py`) używał tego samego wzoru,
  4. pliki `data/regions/region_*.json` nie kolidowały (q,r) i mieściły się
     w oknie swojego bloku.

NIC nie przesuwa danych — to tylko strażnik. Dokument: docs/world/continent_layout.md.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

region_blocks = pytest.importorskip(
    "region_blocks", reason="scripts/region_blocks.py niedostępny (uruchom lokalnie)"
)
from region_blocks import (  # noqa: E402
    REGION_BLOCKS,
    REGION_OFFSETS,
    W,
    H,
    block_offsets,
    region_offsets,
    screen_y_shift,
)

# Katalog danych krain — w repo lokalnie; w kontenerze może być pod /data.
REGIONS_DIR = ROOT / "data" / "regions"
if not REGIONS_DIR.exists():
    REGIONS_DIR = Path("/data") / "regions"
REGION_FILES = sorted(REGIONS_DIR.glob("region_*.json")) if REGIONS_DIR.exists() else []

# Tabela z docs/world/continent_layout.md (nota CB-4) — oczekiwane offsety.
EXPECTED_OFFSETS = {
    "koronne_niziny":   (-50,  25),
    "kresy":            (  0,   0),
    "czarnobor":        ( 50, -25),
    "siwe_granie":      (  0, -50),
    "wybrzeze_lez":     (-50,  75),
    "martwe_pustkowia": ( 50,  25),
}

# Krainy `coming`, których pliki JSON są STARSZE niż aktualny wzór (offset sprzed
# kompensacji shear / sprzed kroku 50·row). Zostaną naprawione przy regeneracji w
# fali krain — tu tylko udokumentowane, żeby strażnik nie mylił znanego długu z regresją.
# martwe_pustkowia — NAPRAWIONE (MP-3+, offset kanoniczny (50,25), wsiane do DB #1494).
# wybrzeze_lez — NAPRAWIONE (#1542 fix: q_offset -55→-50, hexy +5, reseed DB; wyrównane do bloku SW).
_STALE_COMING_OFFSETS: set[str] = set()


# ── 1. WZÓR (czysta matematyka, bez danych) ──────────────────────────────────

def test_block_offsets_formula():
    """block_offsets = (50·col, 50·row − 25·col)."""
    assert block_offsets(0, 0) == (0, 0)
    assert block_offsets(1, 0) == (50, -25)
    assert block_offsets(-1, 0) == (-50, 25)
    assert block_offsets(0, -1) == (0, -50)
    assert block_offsets(2, 3) == (100, 100)


def test_region_offsets_match_layout_doc():
    """Każda kraina ma offset zgodny z tabelą w continent_layout.md."""
    for key, expected in EXPECTED_OFFSETS.items():
        assert region_offsets(key) == expected, (
            f"{key}: region_offsets={region_offsets(key)} ≠ doc {expected}"
        )
    assert REGION_OFFSETS == EXPECTED_OFFSETS


def test_all_regions_present():
    """Sześć krain kontynentu obecnych w bloku."""
    assert set(REGION_BLOCKS) == set(EXPECTED_OFFSETS)


# ── 2. SHEAR — pas row=0 na równi z Kresami ──────────────────────────────────

def test_screen_shift_equals_50_row():
    """screen_y_shift jest niezależne od kolumny: = 50·row (kompensacja shear).

    Krok 50·row (= wysokość bloku na ekranie) sprawia, że rzędy N-S stykają się.
    """
    for key, (col, row) in REGION_BLOCKS.items():
        q_off, r_off = block_offsets(col, row)
        assert screen_y_shift(q_off, r_off) == pytest.approx(50 * row), (
            f"{key}: shear nieskompensowany (col={col})"
        )


def test_row0_band_aligned_with_kresy():
    """Wszystkie krainy z row=0 mają to samo przesunięcie ekranowe co Kresy."""
    kresy_shift = screen_y_shift(*region_offsets("kresy"))
    assert kresy_shift == 0.0
    row0 = [k for k, (c, r) in REGION_BLOCKS.items() if r == 0]
    assert set(row0) == {"koronne_niziny", "kresy", "czarnobor"}
    for key in row0:
        assert screen_y_shift(*region_offsets(key)) == kresy_shift, (
            f"{key}: pas row=0 NIE na równi z Kresami"
        )


# ── 3. GENERATOR używa tego samego wzoru ─────────────────────────────────────

def test_generator_uses_region_blocks():
    """generate_region_map.REGION_OFFSETS pochodzi z region_blocks (bez dryfu)."""
    gen = pytest.importorskip("generate_region_map")
    assert gen.REGION_OFFSETS == REGION_OFFSETS
    assert (gen.W, gen.H) == (W, H)


# ── 4. DANE: zero kolizji + okno bloku ───────────────────────────────────────

def _load(rf):
    return json.loads(rf.read_text(encoding="utf-8"))


@pytest.mark.skipif(not REGION_FILES, reason="brak plików region_*.json")
def test_no_two_regions_share_hex():
    """Żadne dwie krainy nie dzielą pary (q, r)."""
    seen: dict[tuple[int, int], str] = {}
    collisions = []
    for rf in REGION_FILES:
        d = _load(rf)
        name = d.get("region", rf.stem)
        for h in d["hexes"]:
            key = (h["q"], h["r"])
            if key in seen:
                collisions.append(f"({h['q']},{h['r']}) '{name}' vs '{seen[key]}'")
            else:
                seen[key] = name
    assert not collisions, f"{len(collisions)} kolizji:\n" + "\n".join(collisions[:20])


@pytest.mark.parametrize("rf", REGION_FILES, ids=lambda p: p.stem)
def test_declared_offset_matches_formula(rf):
    """Plik krainy z jawnym q_offset/r_offset trzyma się wzoru bloków.

    Krainy `coming` sprzed CB-4 (martwe_pustkowia, wybrzeze_lez) mają jeszcze
    stary offset — oznaczone jako znany dług (xfail), naprawa przy regeneracji.
    """
    d = _load(rf)
    region = d.get("region", rf.stem)
    if region not in REGION_BLOCKS:
        pytest.skip(f"kraina '{region}' spoza układu bloków")
    if d.get("q_offset") is None or d.get("r_offset") is None:
        pytest.skip(f"{region}: plik bez jawnego offsetu (mapa ręczna/stub)")
    if region in _STALE_COMING_OFFSETS:
        pytest.xfail(f"{region}: plik coming sprzed CB-4 — regeneracja w fali krain")
    assert (d["q_offset"], d["r_offset"]) == region_offsets(region), (
        f"{region}: offset pliku {(d['q_offset'], d['r_offset'])} ≠ wzór "
        f"{region_offsets(region)}"
    )


@pytest.mark.parametrize("rf", REGION_FILES, ids=lambda p: p.stem)
def test_hexes_within_own_block_window(rf):
    """Heksy krainy mieszczą się w oknie 50×50 jej WŁASNEGO offsetu.

    Dowodzi, że plik powstał z maszynerii offset→axial (a nie wylądował na
    cudzym bloku). Mapy ręczne (kresy) legalnie wystają poza teoretyczne okno
    r, więc dla nich sprawdzamy tylko kolumnę q bloku.
    """
    d = _load(rf)
    region = d.get("region", rf.stem)
    if region not in REGION_BLOCKS or len(d["hexes"]) < 50:
        pytest.skip(f"{region}: stub/spoza układu — pomijam okno")

    qs = [h["q"] for h in d["hexes"]]
    rs = [h["r"] for h in d["hexes"]]

    # okno q wg WŁASNEGO offsetu pliku (jawnego albo z kolumny bloku dla map
    # ręcznych) — dowodzi, że kraina siedzi na swoim bloku, nie na cudzym.
    col, row = REGION_BLOCKS[region]
    q_off = d["q_offset"] if d.get("q_offset") is not None else 50 * col
    assert q_off <= min(qs) and max(qs) <= q_off + W - 1, (
        f"{region}: q={min(qs)}..{max(qs)} poza oknem q offsetu {q_off} "
        f"[{q_off}, {q_off + W - 1}]"
    )

    # okno r tylko dla map z jawnym offsetem (generowane); ręczne (kresy) legalnie
    # wystają poza teoretyczne okno, więc je pomijamy.
    if d.get("r_offset") is not None:
        r_off = d["r_offset"]
        assert r_off - (W // 2) <= min(rs) and max(rs) <= r_off + H - 1, (
            f"{region}: r={min(rs)}..{max(rs)} poza oknem offsetu r={r_off}"
        )
