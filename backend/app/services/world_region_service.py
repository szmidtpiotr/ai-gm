"""#1039 — dostępność krain (world_regions.status) w jednym miejscu.

Dwie odpowiedzialności:

  * ``set_region_status`` — admin flipuje krainę ``live``↔``coming``↔``locked``.
    Uwaga na warstwy: kanonem *domyślnego* statusu jest plik
    ``data/regions/region_<key>.json`` (R1 #1241) — git-committed i zamontowany
    **read-only**, więc backend go nie zapisuje. Decyzja admina jest trwałym
    **override'em w DB** (``world_regions.status_override``), którego migracja
    startowa ``_align_region_status_to_files`` celowo nie nadpisuje. Dzięki temu
    flip przeżywa restart, a kraina bez override'u nadal podąża za kanonem.
    ``reset_region_status`` zdejmuje override i wraca do kanonu.

  * ``region_block_for_hex`` — wspólna bramka travel: heks leżący w krainie
    ``coming``/``locked`` zwraca ustrukturyzowany payload blokady
    (``error_code='region_locked'`` + label/status), żeby ŻAR mógł pokazać
    dedykowany modal zamiast milczącego no-opa.
"""
from __future__ import annotations

import sqlite3

REGION_STATUSES = ("live", "coming", "locked")

#: Statusy, które zamykają granicę dla gracza (admin nadal widzi krainę).
BLOCKING_STATUSES = ("coming", "locked")

#: #1549 — sloty TŁA kontynentu: nie krainy z rosteru (lore = 6 krain), tylko
#: wypełnienie pustych bloków siatki. W plikach data/regions mają status
#: `background`; w world_regions siadają jako `locked` (globalnie nieprzechodnie),
#: ale — inaczej niż zwykłe `locked` krainy — są RYSOWANE ZAWSZE, bez mgły wojny
#: (player world-map je emituje jako status 'background'). Ciekawość = paliwo Kuźni.
BACKGROUND_REGION_KEYS = ("tlo_morze", "tlo_polnoc_nw", "tlo_polnoc_ne")


#: #1479 — rasa zakotwiczona w krainie ojczystej. Brak wpisu / None = rasa bez
#: kotwicy, dostępna zawsze (człowiek jest wszędzie). Rasy są dziś hardcode'em
#: w dwóch miejscach (characters.py, front-v2/lib/creation.ts) — gdy trafią do
#: `game_config_races`, ta mapa powinna zniknąć na rzecz kolumny.
RACE_HOME_REGION: dict[str, str | None] = {
    "human": None,
    "dwarf": "siwe_granie",
    # #1474 — elf leśny jest z Czarnoboru. Kraina ma status `coming`, więc rasa
    # jest na razie grywalna tylko dla testera (ta sama bramka co #1478/#1479);
    # po otwarciu Czarnoboru odblokowuje się sama, bez zmian w kodzie.
    "elf": "czarnobor",
    # #1475 — Piętnowani są z Martwych Pustkowi (kraina `live`, w pełni zaseedowana
    # MP-1..MP-7), więc rasa jest publicznie grywalna. Hub startowy = Solny Próg.
    "pietnowani": "martwe_pustkowia",
    # #1476 — Wyspiarze to diaspora bez ojczyzny (odcięta Sztormem Wiecznym);
    # rozproszeni po WSZYSTKICH krainach jako najemnicy, marynarze, przemytnicy.
    # Brak kotwicy krainy (None) → rasa dostępna zawsze, jak człowiek. Kraina
    # rodowa „Wybrzeże Łez" (#1504/#1505) doda później start-anchor i cechy krainowe.
    "wyspiarze": None,
}

#: Etykiety ras dla kreatora (kolejność = kolejność kart).
RACE_LABELS: dict[str, str] = {
    "human": "Człowiek",
    "dwarf": "Krasnolud",
    "elf": "Elf leśny",
    "pietnowani": "Piętnowany",
    "wyspiarze": "Wyspiarz",
}


class RaceUnavailable(Exception):
    """Rasa zablokowana, bo jej kraina ojczysta nie jest otwarta."""

    def __init__(self, race: str, reason: str):
        super().__init__(reason)
        self.race = race
        self.reason = reason


def user_is_tester(conn: sqlite3.Connection, user_id: int | None) -> bool:
    """#1478/#1479 — czy konto ma flagę testera. Każda niepewność → False."""
    if user_id is None:
        return False
    try:
        row = conn.execute(
            "SELECT COALESCE(is_tester, 0) AS is_tester FROM users WHERE id = ? LIMIT 1",
            (int(user_id),),
        ).fetchone()
    except (sqlite3.Error, TypeError, ValueError):
        return False
    return bool(row and int(row["is_tester"] or 0))


def campaign_viewer_is_tester(conn: sqlite3.Connection, campaign_id: int) -> bool:
    """#1478 — czy właściciel kampanii ma flagę testera (``users.is_tester``).

    Tester dostaje wstęp do krain ``coming`` (poczekalnia), żeby przetestować je
    przed udostępnieniem graczom. ``locked`` zostaje zamknięte dla wszystkich.
    Każda niepewność (brak kampanii, brak kolumny, stary schemat) → False:
    podwyższone uprawnienia nadaje się jawnie, nigdy przez pomyłkę.
    """
    try:
        row = conn.execute(
            "SELECT COALESCE(u.is_tester, 0) AS is_tester FROM campaigns c "
            "JOIN users u ON u.id = c.owner_user_id WHERE c.id = ? LIMIT 1",
            (int(campaign_id),),
        ).fetchone()
    except (sqlite3.Error, TypeError, ValueError):
        return False
    return bool(row and int(row["is_tester"] or 0))


def passable_region_keys(
    conn: sqlite3.Connection,
    include_coming: bool = False,
) -> set[str]:
    """Klucze krain, przez które wolno podróżować.

    Domyślnie same ``live``. ``include_coming`` (tester) dokłada ``coming``.
    ``locked`` nie wchodzi do puli nigdy.
    """
    wanted = ("live", "coming") if include_coming else ("live",)
    placeholders = ",".join("?" * len(wanted))
    rows = conn.execute(
        f"SELECT key FROM world_regions WHERE status IN ({placeholders})", wanted
    ).fetchall()
    return {r["key"] for r in rows}


def list_region_rows(conn: sqlite3.Connection) -> list[dict]:
    """Wszystkie krainy ze statusem — admin preview (live + coming + locked)."""
    return [dict(r) for r in conn.execute(
        "SELECT key, label, color, status, status_override, entry_q, entry_r, sort_order, note "
        "FROM world_regions ORDER BY sort_order"
    ).fetchall()]


def _region_row(conn: sqlite3.Connection, key: str) -> sqlite3.Row:
    row = conn.execute(
        "SELECT key, label, status, status_override FROM world_regions WHERE key = ?", (key,)
    ).fetchone()
    if row is None:
        raise LookupError(f"nieznana kraina: {key!r}")
    return row


def set_region_status(conn: sqlite3.Connection, key: str, status: str) -> dict:
    """Ustaw status krainy jako decyzję admina (trwały override nad kanonem plików).

    Raises:
        ValueError: status spoza ``REGION_STATUSES``.
        LookupError: nieznany klucz krainy.
    """
    if status not in REGION_STATUSES:
        raise ValueError(f"status musi być jednym z {REGION_STATUSES}, jest {status!r}")

    row = _region_row(conn, key)
    conn.execute(
        "UPDATE world_regions SET status = ?, status_override = ? WHERE key = ?",
        (status, status, key),
    )
    conn.commit()
    return {
        "key": key,
        "label": row["label"],
        "status": status,
        "previous_status": row["status"],
        "overridden": True,
    }


def reset_region_status(conn: sqlite3.Connection, key: str) -> dict:
    """Zdejmij override — kraina wraca pod kanon z pliku przy najbliższym starcie."""
    row = _region_row(conn, key)
    conn.execute("UPDATE world_regions SET status_override = NULL WHERE key = ?", (key,))
    conn.commit()
    return {
        "key": key,
        "label": row["label"],
        "status": row["status"],
        "overridden": False,
    }


def region_block_for_hex(
    conn: sqlite3.Connection,
    q: int,
    r: int,
    include_coming: bool = False,
) -> dict | None:
    """Blokada travel dla heksa w niedostępnej krainie, albo None.

    None znaczy „ta bramka nie ma nic do powiedzenia" — heks jest w krainie
    ``live`` albo w ogóle nie istnieje (inne komunikaty travel go obsłużą).
    ``include_coming=True`` (tester, #1478) przepuszcza ``coming``; ``locked``
    blokuje zawsze.
    """
    blocking = ("locked",) if include_coming else BLOCKING_STATUSES
    try:
        row = conn.execute(
            "SELECT wh.region, wr.status, wr.label FROM world_hexes wh "
            "LEFT JOIN world_regions wr ON wr.key = wh.region "
            "WHERE wh.q = ? AND wh.r = ? AND wh.map_level = 0 AND wh.is_active = 1 LIMIT 1",
            (int(q), int(r)),
        ).fetchone()
    except sqlite3.Error:
        return None
    if not row or row["status"] not in blocking:
        return None
    label = row["label"] or row["region"]
    return {
        "error": f"Kraina niedostępna — {label} jest za zamkniętą granicą.",
        "error_code": "region_locked",
        "region": row["region"],
        "region_label": label,
        "region_status": row["status"],
    }


# ── #1479: dostępność ras zależna od krainy ojczystej ────────────────────────

def race_availability(
    conn: sqlite3.Connection,
    include_coming: bool = False,
) -> list[dict]:
    """Lista ras z informacją, czy da się nimi teraz zagrać.

    Rasa bez kotwicy (``RACE_HOME_REGION[...] is None``) jest dostępna zawsze.
    Rasa z kotwicą wymaga, by jej kraina była przechodnia — `live`, a dla testera
    (``include_coming``) także `coming`.

    Brak danych NIE blokuje: nieznana kraina albo brak tabeli `world_regions`
    (świeży clone) → rasa dostępna. Kreator postaci nie może paść przez to, że
    ktoś nie zaseedował mapy.
    """
    try:
        rows = conn.execute("SELECT key, label, status FROM world_regions").fetchall()
        regions = {r["key"]: {"label": r["label"], "status": r["status"]} for r in rows}
    except sqlite3.Error:
        regions = {}

    passable = ("live", "coming") if include_coming else ("live",)

    from app.services.race_start_service import blocked_archetypes_for_race

    out: list[dict] = []
    for key, label in RACE_LABELS.items():
        home = RACE_HOME_REGION.get(key)
        region = regions.get(home) if home else None
        available = True
        reason = None
        if home and region is not None and region["status"] not in passable:
            available = False
            reason = f"{region['label']} — te ziemie są jeszcze zamknięte."
        out.append({
            "key": key,
            "label": label,
            "available": available,
            "reason": reason,
            "home_region": home,
            # #1477 — archetypy zamknięte dla rasy; kreator chowa te karty.
            "blocked_archetypes": blocked_archetypes_for_race(key),
        })
    return out


def assert_race_available(
    conn: sqlite3.Connection,
    race: str,
    user_id: int | None = None,
) -> None:
    """Bramka po stronie zapisu — UI wyszarza kartę, backend nie ufa UI.

    Raises:
        RaceUnavailable: kraina ojczysta rasy jest zamknięta dla tego konta.
    """
    entry = next(
        (r for r in race_availability(conn, include_coming=user_is_tester(conn, user_id))
         if r["key"] == race),
        None,
    )
    if entry is None:
        return  # nieznana rasa → sprawa walidacji rasy, nie bramki krain
    if not entry["available"]:
        raise RaceUnavailable(race, entry["reason"] or "Kraina tej rasy jest zamknięta.")
