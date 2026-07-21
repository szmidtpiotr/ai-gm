"""TDD: Issue #1528 — kanon mapy (data/regions/region_*.json) musi byc spojny z kanonem tresci.

Fala 0 "Sprzatania lokacji". Kod uznaje heks za jedyne zrodlo prawdy o polozeniu lokacji
(#1243, `hex_location_link.py`), wiec plik krainy w gicie JEST geografia gry. Dzis ten plik
zawiera smieci runtime (temp_camp_*, rekord testowy) oraz wiaze lokacje, ktorych nie ma
w kanonie tresci (`data/seeds/content/game_locations.json`) — po pelnym reseedzie heks
wskazuje ducha.

Testy czytaja wylacznie pliki repo (bez DB):
    ./scripts/test_local.sh backend/tests/test_issue1528_map_canon_links.py -v
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

def _find_root() -> Path:
    """Katalog repo = pierwszy przodek zawierajacy data/regions.

    Lokalnie to repo root; w kontenerze backendu (test w /app/tests/) to /app,
    o ile pliki kanonu zostaly tam skopiowane przez docker cp.
    """
    for cand in Path(__file__).resolve().parents:
        if (cand / "data" / "regions").is_dir():
            return cand
    return Path(__file__).resolve().parents[2]


ROOT = _find_root()
REGIONS_DIR = ROOT / "data" / "regions"
CONTENT_SEED = ROOT / "data" / "seeds" / "content" / "game_locations.json"
LEGACY_SEED = ROOT / "docs" / "world" / "world_map_seed.json"

# Testy czytaja kanon z repo. W kontenerze backendu (kod baked, bez data/ i docs/)
# nie ma czego sprawdzac — pomijamy zamiast falszywie failowac.
pytestmark = pytest.mark.skipif(
    not (REGIONS_DIR.is_dir() and CONTENT_SEED.exists()),
    reason="brak plikow kanonu (data/regions, data/seeds/content) — uruchom z repo",
)

# Klucze, ktore nigdy nie powinny trafic do kanonu — twory runtime i testow.
JUNK_KEY = re.compile(r"^(temp_camp_|parent_immut|test_|sbx_|scn_)", re.IGNORECASE)


def _live_region_files() -> list[Path]:
    if not REGIONS_DIR.is_dir():
        return []
    out = []
    for f in sorted(REGIONS_DIR.glob("region_*.json")):
        if json.loads(f.read_text(encoding="utf-8")).get("status") == "live":
            out.append(f)
    return out


def _links(path: Path) -> list[dict]:
    """Wszystkie heksy tego pliku, ktore wiaza lokacje."""
    data = json.loads(path.read_text(encoding="utf-8"))
    return [h for h in data.get("hexes", []) if h.get("location_key")]


def _content_keys() -> set[str]:
    locs = json.loads(CONTENT_SEED.read_text(encoding="utf-8"))
    return {l["key"] for l in locs if l.get("key")}


# --- Test glowny 1 — kanon mapy bez smieci runtime ---------------------------

@pytest.mark.parametrize("region_file", _live_region_files(), ids=lambda p: p.stem)
def test_map_canon_has_no_runtime_junk(region_file: Path):
    """Kanon krainy live nie moze wiazac obozowisk ani rekordow testowych."""
    junk = [h for h in _links(region_file) if JUNK_KEY.match(h["location_key"])]
    assert not junk, (
        f"{region_file.name}: {len(junk)} smieciowych wiazan w kanonie mapy — "
        + ", ".join(f"({h['q']},{h['r']})->{h['location_key']}" for h in junk)
    )


# --- Test glowny 2 — spojnosc dwoch kanonow (mapa <-> tresc) -----------------

@pytest.mark.parametrize("region_file", _live_region_files(), ids=lambda p: p.stem)
def test_map_canon_links_resolve_in_content_canon(region_file: Path):
    """Kazde wiazanie w kanonie mapy musi wskazywac lokacje istniejaca w kanonie tresci.

    Inaczej pelny reseed (tresc + mapa) zostawia heks wskazujacy ducha — to jest
    mechanizm, ktory wyprodukowal "Gospode Pod Zlamanym Rogiem" z #1524.
    """
    known = _content_keys()
    dangling = [h for h in _links(region_file) if h["location_key"] not in known]
    assert not dangling, (
        f"{region_file.name}: {len(dangling)} wiazan wskazuje lokacje spoza "
        f"data/seeds/content/game_locations.json — "
        + ", ".join(f"({h['q']},{h['r']})->{h['location_key']}" for h in dangling)
    )


# --- Test glowny 3 — nazwana osada wiaze swoja lokacje, nie duplikat ---------

def test_named_settlement_hex_binds_its_own_location():
    """Heks nazwany "Karczma Pod Trzema Krukami" ma wiazac kanoniczna karczme.

    Dzis wiaze wygenerowany duplikat `trzech_krukow_2`, a kanoniczny `trzech_krukow`
    (canonical=1, seed) wisi na bezimiennym heksie (0,6) przy krawedzi mapy.
    """
    kresy = REGIONS_DIR / "region_kresy.json"
    by_label = {
        (h.get("label") or "").strip(): h
        for h in _links(kresy)
        if h.get("label")
    }
    hex_karczma = by_label.get("Karczma Pod Trzema Krukami")
    assert hex_karczma is not None, "brak wiazania na heksie 'Karczma Pod Trzema Krukami'"
    assert hex_karczma["location_key"] == "trzech_krukow", (
        f"heks ({hex_karczma['q']},{hex_karczma['r']}) 'Karczma Pod Trzema Krukami' wiaze "
        f"{hex_karczma['location_key']!r} zamiast kanonicznej 'trzech_krukow'"
    )


# --- Test glowny 4 — legacy fallback nie moze po cichu wyzerowac geografii ---

def test_legacy_fallback_seed_carries_links_or_is_disarmed():
    """`docs/world/world_map_seed.json` jest fallbackiem seeda (seed_world_map.py:111).

    Ma 0 wiazan — gdyby live region-pliki znikly, fallback wsialby mape BEZ geografii,
    po cichu. Albo plik niesie wiazania, albo skrypt musi miec jawny guard.
    """
    from importlib import util as _util

    spec = _util.spec_from_file_location("seed_world_map", ROOT / "scripts" / "seed_world_map.py")
    mod = _util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    legacy_links = len(_links(LEGACY_SEED)) if LEGACY_SEED.exists() else 0
    has_guard = hasattr(mod, "assert_links_not_lost")
    assert legacy_links > 0 or has_guard, (
        "legacy seed nie ma wiazan, a scripts/seed_world_map.py nie ma guardu "
        "`assert_links_not_lost` — fallback moze po cichu wyzerowac geografie"
    )


# --- Backward compatibility -------------------------------------------------

def test_live_regions_still_have_full_hex_maps():
    """Sprzatanie wiazan nie moze uszczuplic samej mapy (MIN_HEX=50 w seedzie)."""
    for f in _live_region_files():
        hexes = json.loads(f.read_text(encoding="utf-8")).get("hexes", [])
        assert len(hexes) >= 50, f"{f.name}: tylko {len(hexes)} heksow"


def test_canonical_settlements_keep_their_links():
    """Znane, poprawne wiazania Kresow musza przetrwac sprzatanie."""
    links = {h["location_key"]: (h["q"], h["r"]) for h in _links(REGIONS_DIR / "region_kresy.json")}
    for key, coords in {
        "cieszowice": (13, 22),
        "wolanka": (21, 1),
        "brzezino": (39, 9),
        "strazyn": (33, 6),
        "zgliszcza": (37, 18),
    }.items():
        assert links.get(key) == coords, f"{key} mial stac na {coords}, jest na {links.get(key)}"


# --- Guard seeda: zachowanie, nie tylko istnienie ----------------------------

def _load_seed_module():
    from importlib import util as _util

    spec = _util.spec_from_file_location("seed_world_map", ROOT / "scripts" / "seed_world_map.py")
    mod = _util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _FakeProc:
    def __init__(self, out): self.stdout = out; self.stderr = ""; self.returncode = 0


def test_guard_refuses_seed_that_would_wipe_geography(monkeypatch):
    """Plik bez wiazan + mapa z wiazaniami = odmowa (a nie ciche wyzerowanie)."""
    mod = _load_seed_module()
    monkeypatch.setattr(mod, "dexec", lambda *a, **k: _FakeProc("39\n"))

    hexes_without_links = [{"q": 0, "r": 0, "hex_type": "plains"}]
    with pytest.raises(SystemExit) as exc:
        mod.assert_links_not_lost(hexes_without_links, "c", "/data/ai_gm.db")
    assert exc.value.code == 1


def test_guard_allows_seed_carrying_links(monkeypatch):
    """Normalny seed (plik niesie wiazania) przechodzi bez przeszkod."""
    mod = _load_seed_module()
    monkeypatch.setattr(mod, "dexec", lambda *a, **k: _FakeProc("11\n"))

    hexes = [{"q": i, "r": 0, "location_key": f"loc_{i}"} for i in range(11)]
    mod.assert_links_not_lost(hexes, "c", "/data/ai_gm.db", region="kresy")


def test_guard_allows_seeding_empty_map(monkeypatch):
    """Pusta mapa (swiezy start) — guard nie moze blokowac pierwszego seeda."""
    mod = _load_seed_module()
    monkeypatch.setattr(mod, "dexec", lambda *a, **k: _FakeProc("0\n"))

    mod.assert_links_not_lost([{"q": 0, "r": 0, "hex_type": "plains"}], "c", "/data/ai_gm.db")
