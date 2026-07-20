"""TDD: Issue #1484 — badge krainy na wizytówce idzie za statusem krainy w grze.

Wizytówka trzyma treść w `frontend/showcase/data/swiat.json`. Pole `available` było
ustawiane ręcznie i rozjechało się ze stanem gry (Siwe Granie: `live` w grze,
„WKRÓTCE" na wizytówce). Teraz:

  * ``available``          — LUSTRO stanu gry, utrzymywane automatycznie,
  * ``available_override`` — ręczna decyzja, wygrywa ze wszystkim,
  * ``GET /api/showcase/regions`` — świeża prawda dla strony.

Uruchom w kontenerze:
    docker exec ai-gm-dev-backend-1 pytest tests/test_issue1484_showcase_region_mirror.py -v
"""
import json
import sqlite3
import sys

import pytest

sys.path.insert(0, "/app")

from app.services import showcase_region_mirror as srm  # noqa: E402


# ── Fixtures ─────────────────────────────────────────────────────────────────

def _mem_db(**statuses) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE world_regions (
            key TEXT PRIMARY KEY, label TEXT NOT NULL,
            color TEXT NOT NULL DEFAULT '#888888',
            status TEXT NOT NULL DEFAULT 'coming'
                   CHECK(status IN ('live','coming','locked')),
            status_override TEXT DEFAULT NULL,
            entry_q INTEGER, entry_r INTEGER,
            sort_order INTEGER NOT NULL DEFAULT 0, note TEXT
        )
    """)
    defaults = {"kresy": "live", "siwe_granie": "coming", "czarnobor": "locked"}
    defaults.update(statuses)
    labels = {"kresy": "Kresy", "siwe_granie": "Siwe Granie", "czarnobor": "Czarnobór"}
    conn.executemany(
        "INSERT INTO world_regions(key,label,status,sort_order) VALUES (?,?,?,?)",
        [(k, labels[k], v, i) for i, (k, v) in enumerate(defaults.items())],
    )
    conn.commit()
    return conn


@pytest.fixture()
def swiat(tmp_path):
    path = tmp_path / "swiat.json"
    path.write_text(json.dumps({
        "intro": "Świat stygnie.",
        "krainy": [
            {"key": "kresy", "name": "Kresy", "tag": "Pogranicze", "available": False},
            {"key": "siwe_granie", "name": "Siwe Granie", "tag": "Północ", "available": False},
            {"key": "czarnobor", "name": "Czarnobór", "tag": "Bór", "available": True},
        ],
        "rdzen": {"title": "Rdzeń", "body": "…"},
    }, ensure_ascii=False), encoding="utf-8")
    return str(path)


def _krainy(path) -> dict:
    with open(path, encoding="utf-8") as f:
        return {k["key"]: k for k in json.load(f)["krainy"]}


# ── Lustro stanu gry ─────────────────────────────────────────────────────────

def test_mirror_marks_live_region_available(swiat):
    conn = _mem_db()
    try:
        srm.sync_region_mirror(conn, path=swiat)
        assert _krainy(swiat)["kresy"]["available"] is True
    finally:
        conn.close()


def test_mirror_marks_coming_and_locked_unavailable(swiat):
    conn = _mem_db()
    try:
        srm.sync_region_mirror(conn, path=swiat)
        k = _krainy(swiat)
        assert k["siwe_granie"]["available"] is False
        assert k["czarnobor"]["available"] is False, "locked też nie jest grywalne"
    finally:
        conn.close()


def test_mirror_follows_status_flip(swiat):
    """Odblokowanie krainy w grze zmienia badge bez ręcznej edycji JSON-a."""
    conn = _mem_db(siwe_granie="live")
    try:
        srm.sync_region_mirror(conn, path=swiat)
        assert _krainy(swiat)["siwe_granie"]["available"] is True
    finally:
        conn.close()


def test_mirror_keeps_other_content(swiat):
    """Sync dotyka wyłącznie pola `available` — reszta treści zostaje."""
    conn = _mem_db()
    try:
        srm.sync_region_mirror(conn, path=swiat)
        with open(swiat, encoding="utf-8") as f:
            data = json.load(f)
        assert data["intro"] == "Świat stygnie."
        assert data["rdzen"]["title"] == "Rdzeń"
        assert _krainy(swiat)["kresy"]["tag"] == "Pogranicze"
    finally:
        conn.close()


def test_mirror_ignores_override(swiat):
    """Ręczne nadpisanie nie jest kasowane przez sync."""
    with open(swiat, encoding="utf-8") as f:
        data = json.load(f)
    data["krainy"][1]["available_override"] = True  # siwe_granie wymuszone „grywalne"
    with open(swiat, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)

    conn = _mem_db()
    try:
        srm.sync_region_mirror(conn, path=swiat)
        entry = _krainy(swiat)["siwe_granie"]
        assert entry["available_override"] is True, "sync skasował ręczną decyzję"
        assert entry["available"] is False, "lustro nadal ma odbijać stan gry"
    finally:
        conn.close()


def test_mirror_leaves_unknown_region_alone(swiat):
    """Kraina z wizytówki bez odpowiednika w world_regions zostaje bez zmian."""
    with open(swiat, encoding="utf-8") as f:
        data = json.load(f)
    data["krainy"].append({"key": "atlantyda", "name": "Atlantyda", "available": True})
    with open(swiat, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)

    conn = _mem_db()
    try:
        srm.sync_region_mirror(conn, path=swiat)
        assert _krainy(swiat)["atlantyda"]["available"] is True
    finally:
        conn.close()


def test_mirror_matches_by_name_when_key_missing(tmp_path):
    """Stary JSON bez `key` — dopasowanie po nazwie, żeby sync działał od razu."""
    path = tmp_path / "swiat.json"
    path.write_text(json.dumps({
        "krainy": [{"name": "Kresy", "available": False}],
    }, ensure_ascii=False), encoding="utf-8")
    conn = _mem_db()
    try:
        srm.sync_region_mirror(conn, path=str(path))
        with open(path, encoding="utf-8") as f:
            assert json.load(f)["krainy"][0]["available"] is True
    finally:
        conn.close()


# ── Odporność ────────────────────────────────────────────────────────────────

def test_missing_file_is_noop(tmp_path):
    conn = _mem_db()
    try:
        assert srm.sync_region_mirror(conn, path=str(tmp_path / "nie_ma.json")) is False
    finally:
        conn.close()


def test_broken_json_is_noop(tmp_path):
    path = tmp_path / "swiat.json"
    path.write_text("{ to nie jest json", encoding="utf-8")
    conn = _mem_db()
    try:
        assert srm.sync_region_mirror(conn, path=str(path)) is False
    finally:
        conn.close()


def test_missing_regions_table_is_noop(swiat):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    try:
        assert srm.sync_region_mirror(conn, path=swiat) is False
        assert _krainy(swiat)["czarnobor"]["available"] is True, "plik nietknięty"
    finally:
        conn.close()


# ── Publiczny endpoint ───────────────────────────────────────────────────────

def test_public_regions_payload(swiat):
    conn = _mem_db()
    try:
        out = srm.public_region_states(conn)
        by_key = {r["key"]: r for r in out}
        assert by_key["kresy"]["available"] is True
        assert by_key["siwe_granie"]["available"] is False
        assert by_key["kresy"]["label"] == "Kresy"
    finally:
        conn.close()


def test_public_regions_route_registered():
    from app.routers.showcase import router
    paths = {getattr(r, "path", "") for r in router.routes}
    assert "/api/showcase/regions" in paths, f"brak trasy; jest: {sorted(paths)}"
