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

import json
import random
import sqlite3

#: Archetypy niedostępne dla rasy (klucz rasy → krotka archetypów).
RACE_BLOCKED_ARCHETYPES: dict[str, tuple[str, ...]] = {
    # #1475 — Wojownik-Mag (gish) jest EKSKLUZYWNY dla Piętnowanych (krew oswojona
    # z Rdzeniem). Każda inna rasa ma go zamkniętego.
    "human": ("wojownik_mag",),
    "dwarf": ("rogue", "wojownik_mag"),
    # #1474 — elf leśny nie gra Wojownikiem. CON −1 i lekki chód wykluczają
    # frontowe zwarcie; tożsamość rasy = Zwiadowca (łuk + odskok) i
    # Uczony-Stroiciel (kontrola/iluzje).
    "elf": ("warrior", "wojownik_mag"),
    # #1475 — Piętnowani chodzą tylko drogą magii: Uczony (pełny mag) albo
    # Wojownik-Mag (gish). Czysty Wojownik i Łotrzyk są zamknięte —
    # tożsamość rasy to krew oswojona z Rdzeniem, nie stal ani skrytobójstwo.
    "pietnowani": ("warrior", "rogue"),
    # #1476 — Wyspiarze grają Łotrzykiem-Kombinatorem (CHA-cwaniak portowy) albo
    # Wojownikiem-Zabijaką (kontrola pola + morale). Uczony zamknięty: INT −1 +
    # kultura diaspory — morza się nie studiuje, nie ma go w księgach. Wojownik-Mag
    # (gish) pozostaje ekskluzywny dla Piętnowanych.
    "wyspiarze": ("scholar", "wojownik_mag"),
}

#: Powód pokazywany graczowi, gdy mimo wszystko spróbuje zapisać taką parę.
_BLOCK_REASON: dict[tuple[str, str], str] = {
    ("dwarf", "rogue"): (
        "Krasnoludy nie chodzą drogą Łotrzyka — ich droga to Wojownik "
        "albo Uczony Rdzenia."
    ),
    ("elf", "warrior"): (
        "Leśne elfy nie stają w ścianie tarcz — ich droga to Zwiadowca "
        "albo Uczony-Stroiciel."
    ),
    ("pietnowani", "warrior"): (
        "Piętnowani noszą Rdzeń we krwi — ich droga to Uczony albo "
        "Wojownik-Mag, nie czysta stal."
    ),
    ("pietnowani", "rogue"): (
        "Piętnowani noszą Rdzeń we krwi — ich droga to Uczony albo "
        "Wojownik-Mag, nie skrytobójstwo."
    ),
    ("human", "wojownik_mag"): (
        "Wojownik-Mag to droga Piętnowanych — tylko krew oswojona z Rdzeniem "
        "udźwignie stal i zaklęcie naraz."
    ),
    ("dwarf", "wojownik_mag"): (
        "Wojownik-Mag to droga Piętnowanych — Rdzeń-magia krasnoluda idzie "
        "inną ścieżką (Uczony Rdzenia)."
    ),
    ("elf", "wojownik_mag"): (
        "Wojownik-Mag to droga Piętnowanych — magia elfa to strojenie, "
        "nie krew oswojona."
    ),
    ("wyspiarze", "scholar"): (
        "Wyspiarze nie studiują ksiąg — ich droga to Łotrzyk-Kombinator "
        "albo Wojownik-Zabijaka. Mądrość morza zbiera się na pokładzie, nie w bibliotece."
    ),
    ("wyspiarze", "wojownik_mag"): (
        "Wojownik-Mag to droga Piętnowanych — krew wyspiarza pachnie solą, "
        "nie Rdzeniem."
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
    # CB-8 (#1474 §9) — hub Czarnoboru istnieje (Szept Koron w `game_locations`
    # na heksie 74,-12; 2500 heksów regionu w `world_hexes`), więc elf ma kotwicę.
    # `default` = Gościnne Drzewo (onboarding w koronach drzew, sub huba Szept
    # Koron — dziedziczy heks rodzica); `variant` = Ostęp Graniczny (osada wymiany
    # na zachodzie, własny heks 74,8). Lore §9: `docs/world/regions/czarnobor.md`.
    "elf": {
        "region": "czarnobor",
        "default": "szept_goscinne_drzewo",
        "variants": (
            "szept_goscinne_drzewo",
            "ostep_graniczny",
        ),
    },
    # #1475 / MP-8 (#1494 §8) — Piętnowani startują na Martwych Pustkowiach
    # (kraina `live`, hub „Solny Próg" w `game_locations` na heksie 64,37;
    # 2500 heksów regionu). `default` = Gospoda dla Obcych (sub huba —
    # onboarding, dziedziczy heks rodzica). Warianty planu: Dom Starszych (rada
    # enklawy, wewnątrz huba) oraz „Obóz Gorączki" (boomtown obcych na własnym
    # heksie 68,41 — twardszy start WŚRÓD obcych, którzy boją się Piętna).
    # Otwarte pustkowia (sól, ruiny, martwa ziemia) NIE są startem.
    # Lore: `docs/world/regions/martwe_pustkowia.md` §8.
    "pietnowani": {
        "region": "martwe_pustkowia",
        "default": "solny_prog_gospoda",
        "variants": (
            "solny_prog_gospoda",
            "solny_prog_dom_starszych",
            "oboz_goraczki",
        ),
    },
    # WL-9 (#1504 §10) — Wyspiarze to diaspora BEZ kotwicy krainy: w
    # `world_region_service.RACE_HOME_REGION` zostają `None`, więc rasa jest
    # dostępna WSZĘDZIE (lore §7 — „jedyna rasa obecna wszędzie"). RACE_START
    # jest OD TEGO NIEZALEŻNE — ustawia tylko *domyślne miejsce startu kampanii*,
    # nie bramkuje wyboru rasy. Kampania wyspiarza domyślnie zaczyna się u swoich:
    # Dzielnica Wyspiarzy w Czarnogrodzie (sub huba „Czarnogród, Port", heks
    # −19,65 — dziedziczy heks rodzica). `default` = Dzielnica Wyspiarzy
    # (onboarding wśród diaspory); `variant` = Nabrzeże (port, wśród obcych i
    # Korony — twardszy start, ten sam heks huba). Lore: `wybrzeze_lez.md` §7/§10.
    "wyspiarze": {
        "region": "wybrzeze_lez",
        "default": "czarnogrod_dzielnica_wyspiarzy",
        "variants": (
            "czarnogrod_dzielnica_wyspiarzy",
            "czarnogrod_nabrzeze",
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
    # CB-8 (#1474 §9) — elf leśny startuje w Czarnoborze, hub „Szept Koron".
    # Haki: Aerlin („kolejne drzewo zgasło") + spór Cathel vs Nimriel
    # (dwie strony werbują gracza do swojej wizji krainy).
    "elf": (
        "KRAINA STARTOWA (obowiązkowa — bohater jest elfem leśnym):\n"
        "  Czarnobór — mroczny, żywy las elfów; osady w koronach drzew, wardy "
        "trzymające ciemność za granicą, ludzie tolerowani tylko na skraju.\n"
        "  Pierwsza lokacja planu (key_locations[0]) MUSI być jedną z:\n"
        "    - „Szept Koron: Gościnne Drzewo\" (osada w koronach — domyślna, zalecana)\n"
        "    - „Ostęp Graniczny\" (osada wymiany na zachodniej granicy)\n"
        "  Reszta boru (Bór Zmarłych, Trzęsawiska, Step Wilków) NIE jest startem.\n"
        "PIERWSZE HAKI (użyj obu w Akcie 1):\n"
        "  - Aerlin (mistrzyni strojenia, opiekunka wardów) alarmuje: „kolejne "
        "drzewo zgasło\" — ward pęka, ciemność wchodzi głębiej; prosi bohatera, "
        "by zbadał, czemu pieśń milknie.\n"
        "  - Cathel (przywódca zwiadowców, twarz OTWARCIA) i Nimriel (Starsza "
        "Kręgu, twarz ZAMKNIĘCIA) werbują bohatera do przeciwnych wizji: Cathel "
        "chce wyjść poza wardy i szukać źródła zła, Nimriel chce zamknąć się i "
        "wzmocnić granice. Bohater wybiera stronę albo lawiruje — napęd Aktu 1.\n"
    ),
    # #1475 / MP-8 (#1494 §8) — Piętnowany startuje na Martwych Pustkowiach, hub
    # „Solny Próg" (enklawa Piętnowanych). Haki wg §8: Lejla (Przewodniczka, twarz
    # OTWARCIA — handel z obcymi) vs Raszid (Starszy enklawy, twarz UKRYCIA — chroń
    # swoich); w tle Siostra Verena (Misja Światła) węszy w enklawie za Piętnem.
    "pietnowani": (
        "KRAINA STARTOWA (obowiązkowa — bohater jest Piętnowanym):\n"
        "  Martwe Pustkowia — spopielała kraina przy płytkim Rdzeniu; sól jako "
        "waluta i tarcza, ruiny Pradawnych, nieumarli i istoty Rdzenia. "
        "Piętnowani to potomkowie ludzi, którzy NIE uciekli po Wielkim Pęknięciu "
        "— popielata skóra, blade oczy, widoczne piętno; obcy im nie ufają.\n"
        "  Pierwsza lokacja planu (key_locations[0]) MUSI być jedną z:\n"
        "    - „Solny Próg: Gospoda dla Obcych\" (enklawa Piętnowanych — domyślna, zalecana)\n"
        "    - „Solny Próg: Dom Starszych\" (rada enklawy)\n"
        "    - „Obóz Gorączki\" (boomtown obcych — twardszy start wśród nieufnych)\n"
        "  Otwarte pustkowia (Pola Szkła, Krypta, Twierdza Bezimiennego) NIE są startem.\n"
        "PIERWSZE HAKI (użyj OBU jako przeciwstawnych ofert w Akcie 1 — oś "
        "otwarcie kontra ukrycie):\n"
        "  - Lejla, Przewodniczka enklawy (twarz OTWARCIA) — chce wyprowadzać "
        "solne karawany do obcych i handlować z Obozem Gorączki; werbuje bohatera "
        "do wyprawy poza Solny Próg mimo ryzyka Piętna.\n"
        "  - Raszid, Starszy enklawy (twarz UKRYCIA) — chroni Piętnowanych i chce "
        "trzymać enklawę zamkniętą; płaci za coś przeciwnego, by swoi nie musieli "
        "kłaniać się obcym. Bohater wybiera stronę albo lawiruje — napęd Aktu 1.\n"
        "  - W TLE: Siostra Verena, inkwizytorka-obserwatorka Misji Światła, WĘSZY "
        "w enklawie — patrzy na Piętno z podejrzliwością i szuka pretekstu; jej "
        "obecność zaostrza spór Lejla↔Raszid.\n"
    ),
    # WL-9 (#1504 §10) — Wyspiarz startuje u swoich: Dzielnica Wyspiarzy w
    # Czarnogrodzie (Wybrzeże Łez), wariant Nabrzeże. Haki §10: pusty fotel w
    # Radzie (Zatoka Topielców), blokada portu przez Koronę (Kapitan Roggen),
    # Dziadek Florian szuka śmiałka. Zachowany wątek §7: diaspora obecna wszędzie
    # — wyspiarz jest u siebie tylko tam, gdzie pachnie solą.
    "wyspiarze": (
        "KRAINA STARTOWA (bohater jest wyspiarzem z diaspory):\n"
        "  Wybrzeże Łez — mgliste, deszczowe wybrzeże portów, przemytu i "
        "topielczych mitów. Czarnogród to gród portowy, w którym wyspiarze mają "
        "własną Dzielnicę Wyspiarzy — diasporę znad wysp odciętych Sztormem "
        "Wiecznym dwa pokolenia temu (nikt stamtąd nie wrócił). Wyspiarze "
        "rozeszli się po świecie jako najemnicy, marynarze i przemytnicy; są "
        "obecni WSZĘDZIE, u siebie tylko tam, gdzie pachnie solą (porty, doki).\n"
        "  Pierwsza lokacja planu (key_locations[0]) MUSI być jedną z:\n"
        "    - \"Czarnogród: Dzielnica Wyspiarzy\" (diaspora — domyślna, zalecana)\n"
        "    - \"Czarnogród: Nabrzeże\" (port, wśród obcych i Korony — twardszy start)\n"
        "  Reszta Wybrzeża (Zatoka Topielców, Latarnia, bagna) NIE jest startem.\n"
        "PIERWSZE HAKI (użyj ich w Akcie 1 — oś diaspora kontra Korona):\n"
        "  - PUSTY FOTEL W RADZIE: w Radzie Wybrzeża (Zatoka Topielców) jeden "
        "fotel stoi pusty; diaspora wyspiarzy chce, by zajął go ktoś z ich krwi "
        "— bohater jest naturalnym kandydatem albo pionkiem w tej rozgrywce.\n"
        "  - BLOKADA KORONY: Kapitan Roggen (Korona) trzyma port pod kontrolą — "
        "cła, rewizje i konfiskaty duszą przemyt i handel diaspory; ktoś musi "
        "coś z tym zrobić.\n"
        "  - FLORIAN SZUKA ŚMIAŁKA: Dziadek Florian, stary rybak z diaspory, "
        "szuka śmiałka do roboty, której nikt trzeźwy się nie tknie — pierwsza "
        "fucha wciąga bohatera w sprawy Wybrzeża.\n"
        "  Na lądzie, z dala od portów, patrzą na wyspiarza jak na obcego "
        "przybłędę — wpleć to w ton narracji poza Wybrzeżem.\n"
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


# ── KN-9 (#1500) — losowy start człowieka: Kresy vs Vilnograd ─────────────────
# Człowiek nie ma kotwicy krainy (RACE_START bez wpisu). §8 koronne_niziny.md:
# przy tworzeniu planu losujemy 50/50 miejsce startu — gospoda „Pod Złamanym
# Rogiem" na Kresach (pogranicze) ALBO Vilnograd, stolica Korony (miasto intryg).
# Wariant miejski dobiera sub-lokację do archetypu: łotrzyk → Dzielnica Złodziei
# (kanon — ludzki łotrzyk wyrasta z dzielnicy złodziei stolicy), reszta → zajazd
# przy Targu Wielkim. Losowanie pada RAZ i jest zapisane na bohaterze
# (``sheet_json.kn9_start``), więc plan-hint i fizyczny heks startu zawsze się
# zgadzają — kolejność wywołań (plan przed heksem czy odwrotnie) nie ma znaczenia.
# Aktywne DOPIERO po zaseedowaniu Vilnogradu (§8) — inaczej zawsze Kresy.

HUMAN_START_KRESY_LOC = "gospoda_pod_zlamanym_rogiem"
HUMAN_START_KRESY_REGION = "kresy"
HUMAN_START_VILNOGRAD_HUB = "vilnograd_stolica"
HUMAN_START_VILNOGRAD_MARKET = "vilnograd_rynek"  # zajazd przy Targu Wielkim
HUMAN_START_VILNOGRAD_THIEVES = "vilnograd_dzielnica_zlodziei"  # łotrzyk (kanon)
HUMAN_START_VILNOGRAD_REGION = "koronne_niziny"

#: Szansa startu w Vilnogradzie zamiast na Kresach — WARTOŚĆ STARTOWA (50/50),
#: strojona po obserwacji (KN-9 / §8).
HUMAN_VILNOGRAD_START_CHANCE = 0.5

_HUMAN_START_VARIANTS = ("kresy", "vilnograd")


def _character_sheet(conn: sqlite3.Connection, character_id: int | None) -> dict | None:
    """``sheet_json`` bohatera jako dict albo ``None`` przy braku/uszkodzeniu."""
    if not character_id:
        return None
    try:
        row = conn.execute(
            "SELECT sheet_json FROM characters WHERE id = ? LIMIT 1", (int(character_id),)
        ).fetchone()
    except (sqlite3.Error, TypeError, ValueError):
        return None
    if not row:
        return None
    raw = row["sheet_json"] if isinstance(row, sqlite3.Row) else row[0]
    try:
        data = json.loads(raw or "{}")
    except (ValueError, TypeError):
        return {}
    return data if isinstance(data, dict) else {}


def character_archetype(conn: sqlite3.Connection, character_id: int | None) -> str | None:
    """Archetyp bohatera z ``sheet_json`` (np. ``rogue``) albo ``None``."""
    sheet = _character_sheet(conn, character_id)
    if not sheet:
        return None
    return (str(sheet.get("archetype") or "").strip().lower()) or None


def _vilnograd_seeded(conn: sqlite3.Connection) -> bool:
    """Vilnograd zaseedowany, gdy jego hub ma heks overworldu (§8 aktywacja)."""
    return _hex_for_location(conn, HUMAN_START_VILNOGRAD_HUB) is not None


def _persist_human_start(conn: sqlite3.Connection, character_id: int | None, variant: str) -> None:
    """Zapisz wylosowany wariant na bohaterze (``sheet_json.kn9_start``)."""
    sheet = _character_sheet(conn, character_id)
    if sheet is None:
        return
    sheet["kn9_start"] = variant
    try:
        conn.execute(
            "UPDATE characters SET sheet_json = ? WHERE id = ?",
            (json.dumps(sheet, ensure_ascii=False), int(character_id)),
        )
    except (sqlite3.Error, TypeError, ValueError):
        pass


def resolve_human_start_variant(conn: sqlite3.Connection, character_id: int | None) -> str:
    """``'kresy'`` albo ``'vilnograd'``.

    Losuje 50/50 RAZ (przy pierwszym wywołaniu — zwykle tworzenie planu), zapisuje
    na bohaterze; kolejne wywołania czytają zapis. Vilnograd tylko, gdy kraina jest
    zaseedowana (§8) — inaczej zawsze Kresy.
    """
    sheet = _character_sheet(conn, character_id)
    stored = str((sheet or {}).get("kn9_start") or "").strip().lower()
    if stored in _HUMAN_START_VARIANTS:
        # Kraina zniknęła po zapisie → bezpieczny fallback bez nadpisywania zapisu.
        if stored == "vilnograd" and not _vilnograd_seeded(conn):
            return "kresy"
        return stored
    if not _vilnograd_seeded(conn):
        _persist_human_start(conn, character_id, "kresy")
        return "kresy"
    variant = "vilnograd" if random.random() < HUMAN_VILNOGRAD_START_CHANCE else "kresy"
    _persist_human_start(conn, character_id, variant)
    return variant


def _human_vilnograd_loc(conn: sqlite3.Connection, character_id: int | None) -> str:
    """Sub-lokacja Vilnogradu wg archetypu: łotrzyk → Dzielnica Złodziei (kanon)."""
    arch = character_archetype(conn, character_id)
    return HUMAN_START_VILNOGRAD_THIEVES if arch == "rogue" else HUMAN_START_VILNOGRAD_MARKET


def _resolve_human_random_start(
    conn: sqlite3.Connection, character_id: int | None
) -> dict | None:
    """Heks + lokacja dla losowego startu człowieka (KN-9). ``None`` → stara ścieżka."""
    variant = resolve_human_start_variant(conn, character_id)
    if variant == "vilnograd":
        loc_key = _human_vilnograd_loc(conn, character_id)
        region = HUMAN_START_VILNOGRAD_REGION
        coords = _hex_for_location(conn, loc_key)
        if coords is None:  # sub bez heksa / nie zaseedowane → Kresy
            loc_key, region = HUMAN_START_KRESY_LOC, HUMAN_START_KRESY_REGION
            coords = _hex_for_location(conn, loc_key)
    else:
        loc_key, region = HUMAN_START_KRESY_LOC, HUMAN_START_KRESY_REGION
        coords = _hex_for_location(conn, loc_key)
    if coords is None:
        return None  # brak gospody na heksie → stara ścieżka (label/random)

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
        "loc_key": loc_key,
        "variant_key": loc_key,
        "region": region,
    }


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
    # KN-9 (#1500) — człowiek ma LOSOWY start (Kresy vs Vilnograd), nie kotwicę.
    if race == "human":
        return _resolve_human_random_start(conn, character_id)
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


def _human_vilnograd_plan_hint(conn: sqlite3.Connection, character_id: int | None) -> str:
    """Podpowiedź do promptu planu dla miejskiego startu człowieka (KN-9 §8).

    Haki: drobne zlecenie gildii / dług / Nocny Burmistrz czegoś chce. Miejsce
    startu dobrane do archetypu (łotrzyk → Dzielnica Złodziei).
    """
    if _human_vilnograd_loc(conn, character_id) == HUMAN_START_VILNOGRAD_THIEVES:
        place = (
            "„Vilnograd: Dzielnica Złodziei\" (kanon — ludzki łotrzyk wyrasta "
            "z dzielnicy złodziei stolicy)"
        )
    else:
        place = "„Vilnograd: Targ Wielki\" (zajazd przy targu — serce handlu stolicy)"
    return (
        "MIEJSCE STARTU (obowiązkowe — losowy MIEJSKI start człowieka, KN-9):\n"
        "  Vilnograd — stolica Korony: gildie, Katedra Światła, Dzielnica Złodziei "
        "i cień Rady Czterech. Miasto intryg, nie pogranicze — kampania od pierwszej "
        "sceny toczy się inaczej niż na Kresach.\n"
        f"  Pierwsza lokacja planu (key_locations[0]) to {place}.\n"
        "PIERWSZE HAKI (użyj JEDNEGO–DWÓCH jako zaczep Aktu 1 — miejskie, drobne):\n"
        "  - DROBNE ZLECENIE GILDII: gildia (kupiecka/rzemieślnicza) szuka kogoś "
        "do małej, brudnej roboty — dostawa, dług do ściągnięcia, zniknięcie towaru; "
        "pierwsza fucha, która wciąga w politykę stolicy.\n"
        "  - DŁUG: bohater komuś winien (albo ktoś jemu) — lichwiarz, dawny wspólnik "
        "lub gildia upomina się o spłatę; zegar tyka od pierwszej sceny.\n"
        "  - NOCNY BURMISTRZ CZEGOŚ CHCE: „Nocny Burmistrz\", nieuchwytny władca "
        "Dzielnicy Złodziei, przez posłańca zleca bohaterowi zadanie — odmówić nie "
        "wypada. Nikt nie wie, kto nim jest.\n"
        "  Ton: intryga, gildie, cień Rady Czterech — miasto, nie trakt.\n"
    )


def race_plan_hint(conn: sqlite3.Connection, campaign_id: int | None) -> str:
    """Blok do promptu planu kampanii — kraina startowa + haki rodów (lore §9).

    KN-9 (#1500): dla człowieka losuje 50/50 miejsce startu (Kresy vs Vilnograd)
    i — tylko przy wariancie miejskim — dokłada haki stolicy. Kresy = bez zmian.
    """
    if not campaign_id:
        return ""
    try:
        row = conn.execute(
            "SELECT id, race FROM characters WHERE campaign_id = ? AND is_active = 1 "
            "ORDER BY id DESC LIMIT 1",
            (int(campaign_id),),
        ).fetchone()
    except (sqlite3.Error, TypeError, ValueError):
        return ""
    if not row:
        return ""
    race = ((row["race"] if isinstance(row, sqlite3.Row) else row[1]) or "").strip().lower()
    if race == "human":
        char_id = row["id"] if isinstance(row, sqlite3.Row) else row[0]
        try:
            variant = resolve_human_start_variant(conn, char_id)
        except Exception:  # bramka startu nigdy nie wywraca tworzenia planu
            return ""
        if variant == "vilnograd":
            return _human_vilnograd_plan_hint(conn, char_id)
        return ""  # Kresy — plan bez zmian (jak dotąd)
    return RACE_PLAN_HINT.get(race, "")
