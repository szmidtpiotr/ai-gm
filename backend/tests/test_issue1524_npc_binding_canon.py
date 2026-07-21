"""TDD: Issue #1524 — kanon wiazania NPC<->lokacja (fala 1 "Sprzatania lokacji").

Decyzje Piotra (2026-07-21, komentarz w #1524):
  1. Zrodlo prawdy = `location_npc_assignments`. `npc_keys` w `game_locations` to
     kopia pochodna (lustro dla mapy admina), `npc_locations` idzie do likwidacji.
  2. Gospodarze siedza WYLACZNIE w sub-lokacjach. Makro, ktore ma sub-lokacje,
     musi miec zero przypisan (spojne z modelem osady #1212: hub + suby).
  6. Gospoda "Pod Zlamanym Rogiem" trafia do kanonu tresci i wiaze sie z heksem
     (24,13), ktory juz nosi te nazwe w kanonie mapy (fala 0, #1528).

Testy czytaja wylacznie pliki repo (bez DB), wzorem test_issue1528_map_canon_links.py:
    ./scripts/test_local.sh backend/tests/test_issue1524_npc_binding_canon.py -v
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest


def _find_root() -> Path:
    """Katalog repo = pierwszy przodek zawierajacy data/seeds/content."""
    for cand in Path(__file__).resolve().parents:
        if (cand / "data" / "seeds" / "content").is_dir():
            return cand
    return Path(__file__).resolve().parents[2]


ROOT = _find_root()
CONTENT = ROOT / "data" / "seeds" / "content"
LOCATIONS = CONTENT / "game_locations.json"
ASSIGNMENTS = CONTENT / "location_npc_assignments.json"
NPCS = CONTENT / "npcs.json"
LEGACY_NPC_LOCATIONS = CONTENT / "npc_locations.json"
REGIONS = ROOT / "data" / "regions"

pytestmark = pytest.mark.skipif(
    not (LOCATIONS.exists() and ASSIGNMENTS.exists()),
    reason="brak plikow kanonu tresci (data/seeds/content) — uruchom z repo",
)

JUNK_KEY = re.compile(r"(_u31$|^test_|^__test|^issue[0-9])", re.IGNORECASE)

# Gospoda z heksa (24,13) — fala 0 zostawila heks pusty, bo lokacji nie bylo w kanonie.
INN_MACRO = "gospoda_pod_zlamanym_rogiem"
INN_HEX = (24, 13)


def _load(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def _locations() -> dict[str, dict]:
    return {row["key"]: row for row in _load(LOCATIONS)}


def _assignments() -> list[dict]:
    return _load(ASSIGNMENTS)


def _subs_by_parent(locs: dict[str, dict]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for row in locs.values():
        parent = row.get("parent_key")
        if parent:
            out.setdefault(parent, []).append(row)
    return out


def _npc_keys_field(row: dict) -> list[str]:
    raw = row.get("npc_keys") or "[]"
    if isinstance(raw, list):
        return [str(k) for k in raw]
    try:
        return [str(k) for k in json.loads(raw)]
    except (json.JSONDecodeError, TypeError):
        return []


# ─── Test glowny: jedno zrodlo prawdy, zero rozjazdow ────────────────────────

def test_zero_przypisan_do_nieistniejacej_lokacji():
    """Widmowe przypisanie (np. gospoda_pod_z_amanym_rogiem) = lokacja bez karty."""
    locs = _locations()
    ghosts = [
        (a["location_key"], a["npc_key"])
        for a in _assignments()
        if a["location_key"] not in locs
    ]
    assert ghosts == [], f"przypisania do nieistniejacych lokacji: {ghosts}"


def test_zero_przypisan_do_nieistniejacego_npc():
    npc_keys = {n["key"] for n in _load(NPCS)}
    orphans = [
        (a["location_key"], a["npc_key"])
        for a in _assignments()
        if a["npc_key"] not in npc_keys
    ]
    assert orphans == [], f"przypisania do nieistniejacych NPC: {orphans}"


def test_zero_smieci_testowych_w_przypisaniach():
    """`locked_inn_u31`, `tavern_u31`, `parent_inn_u31`, `sub_cellar_u31` — smieci po U31."""
    junk = [
        (a["location_key"], a["npc_key"])
        for a in _assignments()
        if JUNK_KEY.search(a["location_key"]) or JUNK_KEY.search(a["npc_key"])
    ]
    assert junk == [], f"smieci testowe w kanonie przypisan: {junk}"


def test_makro_z_sublokacjami_nie_ma_gospodarzy():
    """Decyzja 2: gospodarz siedzi w subie; makro-hub zawsze puste."""
    locs = _locations()
    subs = _subs_by_parent(locs)
    bad = []
    for a in _assignments():
        loc = locs.get(a["location_key"])
        if not loc or loc.get("location_type") != "macro":
            continue
        if subs.get(a["location_key"]):
            bad.append((a["location_key"], a["npc_key"]))
    assert bad == [], f"NPC przypisani do makro majacego sub-lokacje: {bad}"


def test_npc_keys_jest_lustrem_przypisan():
    """`npc_keys` = kopia pochodna. Kazdy rozjazd = drugie zrodlo prawdy."""
    locs = _locations()
    expected: dict[str, set[str]] = {}
    for a in _assignments():
        if int(a.get("is_active", 1) or 0) != 1:
            continue
        expected.setdefault(a["location_key"], set()).add(a["npc_key"])
    drift = []
    for key, row in locs.items():
        mirror = set(_npc_keys_field(row))
        want = expected.get(key, set())
        if mirror != want:
            drift.append((key, sorted(mirror), sorted(want)))
    assert drift == [], f"npc_keys rozjechane z przypisaniami: {drift[:10]}"


def test_legacy_npc_locations_nie_jest_kanonem():
    """`npc_locations` zlikwidowany — seed nie moze go dalej wozic."""
    assert not LEGACY_NPC_LOCATIONS.exists(), (
        "data/seeds/content/npc_locations.json wciaz istnieje — legacy nie zlikwidowany"
    )


# ─── Gospoda "Pod Zlamanym Rogiem" (Problem 2 z issue) ───────────────────────

def test_gospoda_pod_zlamanym_rogiem_jest_w_kanonie():
    locs = _locations()
    inn = locs.get(INN_MACRO)
    assert inn is not None, f"brak lokacji {INN_MACRO} w kanonie tresci"
    assert inn.get("canonical") == 1 and inn.get("is_active") == 1
    assert inn.get("location_type") == "macro"
    assert inn.get("region") == "kresy"


def test_gospoda_ma_gospodarza_w_sublokacji():
    locs = _locations()
    subs = _subs_by_parent(locs).get(INN_MACRO, [])
    assert subs, f"{INN_MACRO} nie ma sub-lokacji"
    hosts = [
        a["npc_key"]
        for a in _assignments()
        if a["location_key"] in {s["key"] for s in subs}
    ]
    assert hosts, f"zadna sub-lokacja {INN_MACRO} nie ma gospodarza"


def test_heks_24_13_wskazuje_gospode():
    """Kanon mapy: heks (24,13) nazywa sie 'Pod Zlamanym Rogiem' — ma wskazac lokacje."""
    kresy = json.loads((REGIONS / "region_kresy.json").read_text(encoding="utf-8"))
    hexes = [h for h in kresy["hexes"] if (h.get("q"), h.get("r")) == INN_HEX]
    assert hexes, "brak heksa (24,13) w kanonie mapy Kresow"
    assert hexes[0].get("location_key") == INN_MACRO, (
        f"heks (24,13) wskazuje {hexes[0].get('location_key')!r}, oczekiwano {INN_MACRO!r}"
    )


# ─── Backward compatibility ─────────────────────────────────────────────────

def test_zaden_kanoniczny_npc_nie_zniknal():
    """Przenosiny makro->sub nie moga zgubic ani jednego gospodarza."""
    placed = {a["npc_key"] for a in _assignments() if int(a.get("is_active", 1) or 0) == 1}
    must_keep = {
        "karczmarz_krukow", "innkeeper_marta", "blacksmith_goran", "celnik_pius",
        "kowal_vilnograd", "kupiec_vilnograd", "kowal_wolanka", "komendant_strazyn",
        "znachorka_cieszowice", "torvin_mistrz_kuzni", "wiedzma_jaga",
    }
    missing = sorted(must_keep - placed)
    assert missing == [], f"NPC stracili przypisanie do lokacji: {missing}"


def test_kazda_sublokacja_z_npc_keys_ma_rodzica_w_kanonie():
    locs = _locations()
    broken = [
        row["key"]
        for row in locs.values()
        if row.get("parent_key") and row["parent_key"] not in locs
    ]
    assert broken == [], f"sub-lokacje z martwym rodzicem: {broken}"
