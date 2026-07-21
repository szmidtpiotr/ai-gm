"""TDD: Issue #1525 — Fala 2 „jedna prawda na informacje" (koniec duplikatow kolumn).

Trzy duplikaty do likwidacji na `game_locations`:

1. „czy lokacja stoi na mapie" — `placement` (string) + `world_hex_q/r` (cache)
   + `world_hexes.location_key` (KANON #1243). Zostaje kanon + cache;
   `placement` USUNIETY, a test „czy osadzona" liczony JEDNYM helperem.
2. „kto stworzyl" — `ai_generated` (0/1) + `created_by` (enum). Zostaje
   `created_by`; `ai_generated` usuniety. Jego DRUGIE, przemycone znaczenie
   („tekst juz wzbogacony/recznie edytowany — nie nadpisuj") dostaje wlasna
   kolumne `enrichment_locked`.
3. „status recenzji" — 5 realnych wartosci w bazie, panel zna 3. Zostaja
   3 legalne (`permanent`, `pending_review`, `discarded`), wymuszone w schemacie.

Plus: `created_by` w API przestaje CICHO podmieniac `forge`/`auto_generated`
na `gm_runtime` — enum jest rozszerzony o realnie zapisywane wartosci,
a martwy `import` usuniety.

Uruchomienie:
    ./scripts/test_dev.sh tests/test_issue1525_one_truth_columns.py -v
"""
from __future__ import annotations

import os
import re
import sqlite3
from pathlib import Path

import pytest

from app.services import hex_location_link as hll


APP_DIR = Path(hll.__file__).resolve().parents[1]  # app/
LEGAL_REVIEW_STATUS = {"permanent", "pending_review", "discarded"}


# ─────────────────────────── fixtures ────────────────────────────────────────

@pytest.fixture()
def conn() -> sqlite3.Connection:
    """Minimalny schemat: kanon (world_hexes) + karta lokacji BEZ `placement`."""
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript(
        """
        CREATE TABLE game_locations (
            key TEXT PRIMARY KEY,
            id INTEGER,
            label TEXT,
            location_type TEXT DEFAULT 'macro',
            parent_key TEXT,
            parent_id INTEGER,
            location_subtype TEXT,
            biome TEXT,
            tier INTEGER DEFAULT 1,
            description TEXT,
            terrain_tags TEXT DEFAULT '[]',
            region TEXT,
            approved INTEGER DEFAULT 1,
            is_active INTEGER DEFAULT 1,
            created_by TEXT DEFAULT 'admin_manual',
            enrichment_locked INTEGER NOT NULL DEFAULT 0,
            review_status TEXT NOT NULL DEFAULT 'permanent',
            world_hex_q INTEGER,
            world_hex_r INTEGER
        );
        CREATE TABLE world_hexes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            q INTEGER, r INTEGER, map_level INTEGER DEFAULT 0,
            region TEXT, hex_type TEXT DEFAULT 'las',
            location_key TEXT, is_active INTEGER DEFAULT 1
        );
        CREATE TABLE hex_type_config (
            hex_type TEXT PRIMARY KEY,
            location_spawn_chance REAL DEFAULT 0.15
        );
        INSERT INTO hex_type_config (hex_type, location_spawn_chance) VALUES ('las', 1.0);
        INSERT INTO game_locations (key, id, label, terrain_tags, region)
             VALUES ('karczma_pod_debem', 1, 'Karczma Pod Debem', '["las"]', 'kresy'),
                    ('mlyn_nad_rzeka',    2, 'Mlyn nad Rzeka',    '["las"]', 'kresy');
        INSERT INTO world_hexes (q, r, map_level, region, hex_type)
             VALUES (5, 5, 0, 'kresy', 'las'), (6, 6, 0, 'kresy', 'las');
        """
    )
    c.commit()
    return c


@pytest.fixture(scope="module")
def live_db() -> sqlite3.Connection:
    """ZYWA baza DEV, otwarta READ-ONLY — asercje o realnym stanie swiata.

    Celowo NIE uzywa `resolve_db_path()`: pod `test_dev.sh` wskazywalby kopie,
    ktora inne testy w tym samym przebiegu zdazyly zmodyfikowac (asercje
    „trzy liczby sa spojne" byly wtedy zalezne od kolejnosci testow). Tryb `ro`
    gwarantuje, ze zywa baza pozostaje nietkniete zrodlo prawdy.
    """
    path = os.environ.get("AIGM_LIVE_DB", "/data/ai_gm.db")
    if not os.path.exists(path):
        pytest.skip(f"brak bazy {path} — test danych tylko na DEV")
    c = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    yield c
    c.close()


def _cols(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}


# ═══════════════ 1. „czy stoi na mapie" — jeden helper, jeden kanon ══════════

def test_helper_is_location_placed_czyta_kanon_heksa(conn):
    """`is_location_placed` = JEDYNY test osadzenia; zrodlo = world_hexes."""
    assert hll.is_location_placed(conn, "karczma_pod_debem") is False
    hll.link_location_to_hex(conn, "karczma_pod_debem", 5, 5)
    assert hll.is_location_placed(conn, "karczma_pod_debem") is True
    assert hll.is_location_placed(conn, "mlyn_nad_rzeka") is False


def test_helper_ignoruje_klamiacy_cache(conn):
    """Cache `world_hex_q/r` bez pokrycia w kanonie NIE czyni lokacji osadzona."""
    conn.execute(
        "UPDATE game_locations SET world_hex_q = 9, world_hex_r = 9 WHERE key = 'mlyn_nad_rzeka'"
    )
    conn.commit()
    assert hll.is_location_placed(conn, "mlyn_nad_rzeka") is False


def test_placed_location_keys_zwraca_komplet_kanonu(conn):
    hll.link_location_to_hex(conn, "karczma_pod_debem", 5, 5)
    hll.link_location_to_hex(conn, "mlyn_nad_rzeka", 6, 6)
    assert hll.placed_location_keys(conn) == {"karczma_pod_debem", "mlyn_nad_rzeka"}


def test_pula_floating_liczona_z_kanonu_nie_z_kolumny(conn):
    """Silnik osadzania bierze pule z kanonu — nie z przelacznika `placement`."""
    from app.services.placement_engine import get_floating_locations

    keys = {r["key"] for r in get_floating_locations(conn)}
    assert keys == {"karczma_pod_debem", "mlyn_nad_rzeka"}
    hll.link_location_to_hex(conn, "karczma_pod_debem", 5, 5)
    keys = {r["key"] for r in get_floating_locations(conn)}
    assert keys == {"mlyn_nad_rzeka"}, "osadzona lokacja nie moze wrocic do puli"


def test_silnik_osadzania_nie_wybiera_juz_osadzonej(conn):
    """try_place_location_on_hex bierze kandydatow wylacznie spoza kanonu."""
    from app.services.placement_engine import try_place_location_on_hex

    hll.link_location_to_hex(conn, "karczma_pod_debem", 5, 5)
    chosen = try_place_location_on_hex(
        conn, q=6, r=6, hex_type="las", region="kresy", campaign_seed=1
    )
    assert chosen == "mlyn_nad_rzeka"


def test_kolumna_placement_usunieta(conn):
    assert "placement" not in _cols(conn, "game_locations")


def _module_lines(skip: set[str] | None = None):
    """(rel_path, nr, tekst) dla kazdej linii kodu aplikacji."""
    skip = skip or set()
    for path in sorted(APP_DIR.rglob("*.py")):
        rel = path.relative_to(APP_DIR).as_posix()
        if rel in skip:
            continue
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        for i, line in enumerate(lines, 1):
            yield rel, i, line, lines


def _touches_game_locations(lines: list[str], idx: int, window: int = 14) -> bool:
    """Czy linia nalezy do instrukcji SQL dotykajacej `game_locations`.

    Kolumny `ai_generated`/`review_status` istnieja tez na tabelach tresci
    (`game_config_*`) i tam ZOSTAJA — fala 2 dotyczy wylacznie lokacji.
    """
    lo, hi = max(0, idx - 1 - window), min(len(lines), idx + window)
    return "game_locations" in "\n".join(lines[lo:hi])


def test_zaden_modul_nie_odwoluje_sie_do_placement():
    """Zero czytelnikow/pisarzy kolumny `placement` w kodzie aplikacji.

    Lapiemy uzycie KOLUMNY (SQL / klucz slownika / atrybut wiersza), nie slowo
    „placement" w prozie („starting hex placement failed").
    """
    col = re.compile(
        r"""['"`]placement['"`]"""          # 'placement' w SQL / kluczu slownika
        r"""|\bplacement\s*=\s*['"]"""      # placement = 'placed'
        r"""|\[\s*['"]placement['"]\s*\]"""  # row["placement"]
        r"""|\.placement\b"""               # row.placement
    )
    hits = [
        f"{rel}:{nr}: {line.strip()}"
        for rel, nr, line, _ in _module_lines(skip={"migrations_admin.py"})
        if col.search(line.split("#", 1)[0])
    ]
    assert hits == [], f"kolumna `placement` wciaz uzywana: {hits}"


# ═══════════════ 2. „kto stworzyl" — created_by, koniec ai_generated ═════════

def test_kolumna_ai_generated_usunieta_zostaje_enrichment_locked(conn):
    cols = _cols(conn, "game_locations")
    assert "ai_generated" not in cols
    assert "enrichment_locked" in cols, "blokada lazy-enrichment musi miec wlasna nazwe"


def test_zaden_modul_nie_odwoluje_sie_do_ai_generated_lokacji():
    """`ai_generated` na `game_locations` znika (inne tabele tresci zostaja)."""
    word = re.compile(r"(?<![_a-zA-Z])ai_generated(?![_a-zA-Z])")
    hits = [
        f"{rel}:{nr}: {line.strip()}"
        for rel, nr, line, lines in _module_lines(skip={"migrations_admin.py"})
        if word.search(line.split("#", 1)[0]) and _touches_game_locations(lines, nr)
    ]
    assert hits == [], f"`ai_generated` wciaz uzywany w modulach lokacji: {hits}"


def test_created_by_przepuszcza_forge_bez_cichej_podmiany():
    """`forge` wychodzi z API jako `forge` — koniec podmiany na `gm_runtime`."""
    from app.routers.locations import row_to_location_dict

    out = row_to_location_dict({"key": "x", "label": "X", "created_by": "forge"})
    assert out["created_by"] == "forge"
    out = row_to_location_dict({"key": "x", "label": "X", "created_by": "auto_generated"})
    assert out["created_by"] == "auto_generated"


def test_enum_created_by_zna_realnie_zapisywane_wartosci():
    """Enum = to, co kod naprawde pisze; martwy `import` wypada."""
    from app.routers.locations import ALLOWED_CREATED_BY

    assert ALLOWED_CREATED_BY == {
        "seed", "admin_manual", "admin_kreator", "gm_runtime", "forge", "auto_generated",
    }


def test_model_locationcreate_akceptuje_forge():
    from app.routers.locations import LocationCreate

    assert LocationCreate(key="k", label="L", created_by="forge").created_by == "forge"
    with pytest.raises(Exception):
        LocationCreate(key="k", label="L", created_by="import")


# ═══════════════ 3. status recenzji — 3 legalne wartosci ═════════════════════

def test_schemat_odrzuca_status_spoza_trzech(conn):
    """Po migracji baza sama pilnuje enuma (CHECK/trigger)."""
    from app.migrations_admin import enforce_location_review_status

    enforce_location_review_status(conn)
    conn.execute(
        "INSERT INTO game_locations (key, label, review_status) VALUES ('a','A','permanent')"
    )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO game_locations (key, label, review_status) VALUES ('b','B','approved')"
        )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE game_locations SET review_status='pending' WHERE key='a'")


def test_migracja_przenosi_sieroce_statusy(conn):
    """`approved`→`permanent`, `pending`→`pending_review`."""
    from app.migrations_admin import migrate_location_review_status_values

    conn.execute(
        "INSERT INTO game_locations (key,label,review_status) VALUES ('s1','S1','approved')"
    )
    conn.execute(
        "INSERT INTO game_locations (key,label,review_status) VALUES ('s2','S2','pending')"
    )
    conn.commit()
    migrate_location_review_status_values(conn)
    got = dict(conn.execute("SELECT key, review_status FROM game_locations").fetchall())
    assert got["s1"] == "permanent"
    assert got["s2"] == "pending_review"


def test_zaden_modul_nie_pisze_statusu_spoza_trzech():
    """Sieroce writery (`approved` w hex_travel, `pending` w Kuzni) naprawione."""
    pat = re.compile(r"review_status\s*(?:=|==)\s*'([a-z_]+)'", re.I)
    hits = []
    for rel, nr, line, lines in _module_lines(skip={"migrations_admin.py"}):
        code = line.split("#", 1)[0]
        for m in pat.finditer(code):
            if m.group(1) not in LEGAL_REVIEW_STATUS and _touches_game_locations(lines, nr):
                hits.append(f"{rel}:{nr}: {line.strip()}")
    assert hits == [], f"status recenzji spoza 3 legalnych wartosci: {hits}"


# ═══════════════ 3b. rodzic — dwa pola, zawsze w komplecie ══════════════════

def test_baza_dopelnia_brakujaca_polowke_rodzica(conn):
    """`parent_id` i `parent_key` zostaja, ale nigdy nie rozjezdzaja sie."""
    from app.migrations_admin import enforce_location_parent_pair

    enforce_location_parent_pair(conn)

    # podane samo `parent_key` -> baza dokleja `parent_id`
    conn.execute(
        "INSERT INTO game_locations (id, key, label, parent_key) "
        "VALUES (3, 'izba', 'Izba', 'karczma_pod_debem')"
    )
    row = conn.execute("SELECT parent_id FROM game_locations WHERE key='izba'").fetchone()
    assert row["parent_id"] == 1

    # podane samo `parent_id` -> baza dokleja `parent_key`
    conn.execute(
        "INSERT INTO game_locations (id, key, label, parent_id) VALUES (4, 'stajnia', 'Stajnia', 2)"
    )
    row = conn.execute("SELECT parent_key FROM game_locations WHERE key='stajnia'").fetchone()
    assert row["parent_key"] == "mlyn_nad_rzeka"


def test_backfill_uzupelnia_polowiczne_rekordy(conn):
    """Rekordy sprzed fali 2 (sam `parent_key`) dostaja brakujacy `parent_id`."""
    from app.migrations_admin import enforce_location_parent_pair

    conn.execute(
        "INSERT INTO game_locations (id, key, label, parent_key) "
        "VALUES (9, 'sierota', 'Sierota', 'karczma_pod_debem')"
    )
    conn.commit()
    assert enforce_location_parent_pair(conn) >= 1
    row = conn.execute("SELECT parent_id FROM game_locations WHERE key='sierota'").fetchone()
    assert row["parent_id"] == 1


def test_dane_rodzic_zawsze_w_komplecie(live_db):
    rows = live_db.execute(
        "SELECT key FROM game_locations WHERE is_active = 1 AND ("
        "  (parent_key IS NOT NULL AND parent_id IS NULL AND EXISTS ("
        "     SELECT 1 FROM game_locations p WHERE p.key = game_locations.parent_key))"
        "  OR (parent_id IS NOT NULL AND parent_key IS NULL))"
    ).fetchall()
    assert [r["key"] for r in rows] == []


# ═══════════════ 4. dane na zywej bazie — trzy liczby schodza do jednej ══════

def test_dane_trzy_liczby_sa_spojne(live_db):
    """Kanon = cache = brak trzeciej kopii (kolumna `placement` juz nie istnieje)."""
    assert "placement" not in _cols(live_db, "game_locations")
    canon = live_db.execute(
        "SELECT COUNT(*) FROM world_hexes WHERE map_level=0 AND is_active=1 "
        "AND location_key IS NOT NULL AND location_key != ''"
    ).fetchone()[0]
    cache = live_db.execute(
        "SELECT COUNT(*) FROM game_locations WHERE is_active=1 AND world_hex_q IS NOT NULL"
    ).fetchone()[0]
    assert canon == cache, f"kanon={canon} != cache={cache}"


def test_dane_zadna_sublokacja_nie_stoi_na_mapie_swiata(live_db):
    rows = live_db.execute(
        "SELECT l.key FROM game_locations l JOIN world_hexes h ON h.location_key = l.key "
        "WHERE h.map_level=0 AND l.location_type='sub'"
    ).fetchall()
    assert [r["key"] for r in rows] == []
    rows = live_db.execute(
        "SELECT key FROM game_locations WHERE location_type='sub' AND world_hex_q IS NOT NULL"
    ).fetchall()
    assert [r["key"] for r in rows] == []


def test_dane_zero_statusow_spoza_trzech(live_db):
    rows = live_db.execute(
        "SELECT DISTINCT review_status FROM game_locations"
    ).fetchall()
    bad = [r[0] for r in rows if r[0] not in LEGAL_REVIEW_STATUS]
    assert bad == [], f"nielegalne statusy recenzji w bazie: {bad}"


def test_dane_zero_created_by_spoza_enuma(live_db):
    from app.routers.locations import ALLOWED_CREATED_BY

    rows = live_db.execute("SELECT DISTINCT created_by FROM game_locations").fetchall()
    bad = [r[0] for r in rows if r[0] not in ALLOWED_CREATED_BY]
    assert bad == [], f"`created_by` spoza enuma: {bad}"


def test_dane_zaden_heks_nie_wskazuje_martwej_lokacji(live_db):
    rows = live_db.execute(
        "SELECT h.q, h.r, h.location_key FROM world_hexes h "
        "WHERE h.map_level=0 AND h.location_key IS NOT NULL AND h.location_key != '' "
        "AND NOT EXISTS (SELECT 1 FROM game_locations g "
        "                WHERE g.key = h.location_key AND g.is_active = 1)"
    ).fetchall()
    assert [(r[0], r[1], r[2]) for r in rows] == []


# ═══════════════ 5. backward compatibility ═══════════════════════════════════

def test_link_location_to_hex_nadal_odswieza_cache(conn):
    """Stare zachowanie #1243: kanon + cache w jednym zapisie."""
    assert hll.link_location_to_hex(conn, "karczma_pod_debem", 5, 5) is True
    row = conn.execute(
        "SELECT world_hex_q, world_hex_r FROM game_locations WHERE key='karczma_pod_debem'"
    ).fetchone()
    assert (row["world_hex_q"], row["world_hex_r"]) == (5, 5)
    assert hll.location_on_hex(conn, 5, 5) == "karczma_pod_debem"


def test_reconcile_nadal_czysci_sierocy_pin(conn):
    """Reconcile bez kolumny `placement` dalej gasi pin bez pokrycia w kanonie."""
    conn.execute(
        "UPDATE game_locations SET world_hex_q=9, world_hex_r=9 WHERE key='mlyn_nad_rzeka'"
    )
    conn.commit()
    hll.reconcile_location_hex_links(conn)
    row = conn.execute(
        "SELECT world_hex_q FROM game_locations WHERE key='mlyn_nad_rzeka'"
    ).fetchone()
    assert row["world_hex_q"] is None
