"""#1477 (SG-8) — rasa determinuje krainę startu + archetypy zamknięte dla rasy.

Dwie reguły, jedno źródło prawdy:

  * **Archetypy zamknięte** (`RACE_BLOCKED_ARCHETYPES`) — krasnolud nie gra
    Łotrzykiem (DEX to fabularnie słaba cecha rasy; tożsamość = Wojownik +
    Uczony Rdzeń-magii). Kreator ŻAR chowa kartę, backend odrzuca zapis —
    UI nigdy nie jest jedyną bramką.
  * **Kraina startowa** (`RACE_START`) — krasnolud zaczyna w Siwych Graniach.
    Kraina jest przybita do rasy, ale *miejsce* w krainie to whitelista:
    domyślnie szynk „Pod Rdzawym Młotem" w Kamiennym Grodzie (onboarding),
    a plan LLM może wskazać wariant (Karawanseraj, Wyrobisko Srebrnej Żyły).
    Lodowiec/tundra/ruiny NIE są startami — patrz
    ``docs/world/regions/siwe_granie.md`` §9.

Człowiek nie ma kotwicy (`RACE_START` bez wpisu) → start na Kresach jak dotąd.

Każda niepewność (brak lokacji, brak heksa, świeży clone bez seedu) → ``None``
i stara ścieżka. Bramka rasy nie może wywrócić tworzenia kampanii.
"""
from __future__ import annotations

import sqlite3

#: Archetypy niedostępne dla rasy (klucz rasy → krotka archetypów).
RACE_BLOCKED_ARCHETYPES: dict[str, tuple[str, ...]] = {
    "dwarf": ("rogue",),
}

#: Powód pokazywany graczowi, gdy mimo wszystko spróbuje zapisać taką parę.
_BLOCK_REASON: dict[tuple[str, str], str] = {
    ("dwarf", "rogue"): (
        "Krasnoludy nie chodzą drogą Łotrzyka — ich droga to Wojownik "
        "albo Uczony Rdzenia."
    ),
}

#: Whitelista startowa krainy rodowej rasy. `variants` = miejsca, które może
#: wybrać plan LLM; `default` = onboarding, gdy plan nic sensownego nie poda.
RACE_START: dict[str, dict] = {
    "dwarf": {
        "region": "siwe_granie",
        "default": "grod_pod_rdzawym_mlotem",
        "variants": (
            "grod_pod_rdzawym_mlotem",
            "karawanseraj_na_trakcie",
            "wyrobisko_srebrnej_zyly",
        ),
    },
}

#: Podpowiedź do promptu planu kampanii — lore §9: pierwsze haki to spór rodów
#: (Dagna werbuje do sprawy Hutmana, Balrik płaci za coś przeciwnego).
RACE_PLAN_HINT: dict[str, str] = {
    "dwarf": (
        "KRAINA STARTOWA (obowiązkowa — bohater jest krasnoludem):\n"
        "  Siwe Granie — górska kraina rodów krasnoludzkich, sól jako materiał "
        "przeciw-Rdzeniowy, Wyssane Hołdy, zakaz wchodzenia na lodowiec.\n"
        "  Pierwsza lokacja planu (key_locations[0]) MUSI być jednym z:\n"
        "    - „Kamienny Gród: Pod Rdzawym Młotem\" (szynk — domyślny, zalecany)\n"
        "    - „Karawanseraj na Trakcie\"\n"
        "    - „Wyrobisko Srebrnej Żyły\"\n"
        "  Lodowiec, tundra i ruiny NIE są miejscem startu.\n"
        "PIERWSZE HAKI (użyj obu jako przeciwstawnych ofert w Akcie 1):\n"
        "  - Dagna Młotodzierżca (przywódczyni rewizjonistów) werbuje bohatera "
        "do sprawy Kopalni Czarnego Hutmana — chce, żeby ktoś tam zszedł.\n"
        "  - Balrik Siwotarczy (Starszy Rodów, głos zakazów) płaci za coś "
        "przeciwnego — żeby sprawa Hutmana została zamknięta i zapomniana.\n"
        "  Bohater ma wybrać stronę albo grać na dwa fronty — to napęd Aktu 1.\n"
    ),
}


# ── Archetypy ────────────────────────────────────────────────────────────────

def blocked_archetypes_for_race(race: str | None) -> list[str]:
    """Lista archetypów zamkniętych dla rasy (pusta = wszystko wolno)."""
    return list(RACE_BLOCKED_ARCHETYPES.get((race or "").strip().lower(), ()))


def archetype_block_reason(race: str | None, archetype: str | None) -> str | None:
    """Powód blokady pary rasa+archetyp albo ``None``, gdy para jest legalna."""
    r = (race or "").strip().lower()
    a = (archetype or "").strip().lower()
    if a not in RACE_BLOCKED_ARCHETYPES.get(r, ()):
        return None
    return _BLOCK_REASON.get((r, a), "Ta rasa nie gra tym archetypem.")


def archetype_allowed(race: str | None, archetype: str | None) -> bool:
    return archetype_block_reason(race, archetype) is None


# ── Kraina startowa ──────────────────────────────────────────────────────────

def character_race(conn: sqlite3.Connection, character_id: int | None) -> str | None:
    """Rasa bohatera z DB. Brak danych → ``None`` (traktowane jak człowiek)."""
    if not character_id:
        return None
    try:
        row = conn.execute(
            "SELECT race FROM characters WHERE id = ? LIMIT 1", (int(character_id),)
        ).fetchone()
    except (sqlite3.Error, TypeError, ValueError):
        return None
    if not row:
        return None
    race = (row["race"] if isinstance(row, sqlite3.Row) else row[0]) or ""
    return race.strip().lower() or None


def _normalize(text: str) -> str:
    """Uproszczenie do porównań: małe litery bez polskich znaków (#PL-diacritics)."""
    out = (text or "").lower()
    for src, dst in (
        ("ą", "a"), ("ć", "c"), ("ę", "e"), ("ł", "l"), ("ń", "n"),
        ("ó", "o"), ("ś", "s"), ("ź", "z"), ("ż", "z"),
    ):
        out = out.replace(src, dst)
    return " ".join(out.split())


def _location_row(conn: sqlite3.Connection, key: str):
    try:
        return conn.execute(
            "SELECT key, label, location_type, parent_key, world_hex_q, world_hex_r "
            "FROM game_locations WHERE key = ? AND is_active = 1 LIMIT 1",
            (key,),
        ).fetchone()
    except sqlite3.Error:
        return None


def _hex_for_location(conn: sqlite3.Connection, key: str) -> tuple[int, int] | None:
    """Heks overworldu dla lokacji. Sub-lokacja dziedziczy heks rodzica (hub)."""
    row = _location_row(conn, key)
    if row is None:
        return None
    q, r = row["world_hex_q"], row["world_hex_r"]
    if q is None or r is None:
        parent = row["parent_key"]
        if not parent:
            return None
        prow = _location_row(conn, parent)
        if prow is None:
            return None
        q, r = prow["world_hex_q"], prow["world_hex_r"]
    if q is None or r is None:
        return None
    return int(q), int(r)


def _pick_variant(conn: sqlite3.Connection, spec: dict, requested: str | None) -> str:
    """Wariant wskazany przez plan (po nazwie) albo domyślny szynk.

    Dopasowanie po *znormalizowanej* etykiecie lub kluczu — plan LLM pisze
    „Pod Rdzawym Młotem", a nie `grod_pod_rdzawym_mlotem`. Nazwa spoza
    whitelisty (np. wioska z Kresów) → default, nie wyjątek.
    """
    want = _normalize(requested or "")
    if not want:
        return spec["default"]
    for key in spec["variants"]:
        row = _location_row(conn, key)
        label = _normalize(row["label"] if row is not None else "")
        if key == want or (label and (label in want or want in label)):
            return key
        # „Pod Rdzawym Młotem" bez prefiksu huba („Kamienny Gród: …")
        tail = label.split(":")[-1].strip() if ":" in label else ""
        if tail and (tail in want or want in tail):
            return key
    return spec["default"]


def resolve_race_start(
    conn: sqlite3.Connection,
    character_id: int | None,
    requested_location_name: str | None = None,
) -> dict | None:
    """Startowy heks + lokacja wymuszone przez rasę bohatera.

    Zwraca ``{"q", "r", "hex_type", "label", "loc_key", "variant_key", "region"}``
    albo ``None``, gdy rasa nie ma kotwicy lub danych brakuje (fail-open).
    """
    race = character_race(conn, character_id)
    spec = RACE_START.get(race or "")
    if not spec:
        return None

    variant = _pick_variant(conn, spec, requested_location_name)
    coords = _hex_for_location(conn, variant)
    if coords is None and variant != spec["default"]:
        variant = spec["default"]
        coords = _hex_for_location(conn, variant)
    if coords is None:
        return None

    q, r = coords
    try:
        hrow = conn.execute(
            "SELECT hex_type, label FROM world_hexes "
            "WHERE q = ? AND r = ? AND map_level = 0 AND is_active = 1 LIMIT 1",
            (q, r),
        ).fetchone()
    except sqlite3.Error:
        return None
    if hrow is None:
        return None

    return {
        "q": q,
        "r": r,
        "hex_type": hrow["hex_type"],
        "label": hrow["label"],
        "loc_key": variant,
        "variant_key": variant,
        "region": spec["region"],
    }


def race_plan_hint(conn: sqlite3.Connection, campaign_id: int | None) -> str:
    """Blok do promptu planu kampanii — kraina startowa + haki rodów (lore §9)."""
    if not campaign_id:
        return ""
    try:
        row = conn.execute(
            "SELECT race FROM characters WHERE campaign_id = ? AND is_active = 1 "
            "ORDER BY id DESC LIMIT 1",
            (int(campaign_id),),
        ).fetchone()
    except (sqlite3.Error, TypeError, ValueError):
        return ""
    race = ((row["race"] if row else "") or "").strip().lower()
    return RACE_PLAN_HINT.get(race, "")
