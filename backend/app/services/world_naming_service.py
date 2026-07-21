"""#1527 (fala 4, runda 3) — KONWENCJA NAZW dla generatorów AI.

Model bez reguły domyślnie sypie współczesnymi polskimi imionami („Agnieszka
Kruk", „Anna Riedel") — dokładnie tym, czego kanon zakazuje od #997. Ten moduł
zamienia ustalenia kanonu w jeden blok promptu, który każdy generator treści
może wkleić do systemowej instrukcji.

Źródła prawdy (wszystkie ZATWIERDZONE przez Piotra):

* `backend/prompts/system_prompt.txt`, sekcja NAZEWNICTWO (#997) — reguła ogólna:
  MIX słowiańsko-germański, zakaz realnych polskich toponimów.
* `docs/world/regions/*.md`, sekcje „Obsada krainy" — styl imion per kraina
  (elfy, krasnoludy, Piętnowani, dwór Korony, wyspiarze).

Reguły są tu ZAPISANE, nie czytane z plików: `docs/` nie wchodzi do obrazu
backendu, a milcząca degradacja („brak pliku → brak reguły") oznaczałaby powrót
do zgadywania. Zmiana kanonu = świadoma zmiana tego pliku.

Do wytycznej dokładamy **przykłady z żywej bazy** — imiona NPC, którzy już stoją
w tej krainie. Model uczy się na tym, co faktycznie jest w świecie, a nie na
abstrakcyjnym opisie stylu.
"""
from __future__ import annotations

import re
import sqlite3

__all__ = [
    "LIVE_EXAMPLES_LIMIT",
    "MODERN_POLISH_GIVEN_NAMES",
    "REGION_NAMING",
    "clean_person_label",
    "looks_like_modern_polish_name",
    "looks_like_real_pl_toponym",
    "name_already_taken",
    "naming_guidance",
    "naming_prompt_block",
]

#: Ile żywych przykładów dokładamy do promptu (wartość startowa).
LIVE_EXAMPLES_LIMIT = 8

#: Zakaz wspólny dla wszystkich krain — to jest ta konkretna choroba, którą
#: leczymy: model sięga po imiona z polskiej książki telefonicznej.
_COMMON_AVOID = [
    "imiona realnych świętych i patronów z naszego świata (św. Florian, "
    "św. Barbara, św. Mikołaj) — świat ma własną wiarę: Światło, Klasztor "
    "Iskry, Biała Bogini, kulty Rdzenia",
    "współczesne polskie imiona i nazwiska (Agnieszka, Anna, Piotr, Bartek, "
    "Katarzyna, Michał; Kowalski, Nowak, Wiśniewski, Kowalczyk, Zielińska)",
    "realne polskie toponimy w przydomkach (-owice, -anka, -ino)",
    "imiona skopiowane wprost z Tolkiena, Wiedźmina i innych znanych serii",
]

#: Zakaz dla NAZW MIEJSC — to jest dokładnie ta choroba, po której powstało #997.
_PLACE_AVOID = [
    "imiona realnych świętych i patronów z naszego świata (św. Florian, "
    "św. Barbara, św. Mikołaj) — świat ma własną wiarę: Światło, Klasztor "
    "Iskry, Biała Bogini, kulty Rdzenia",
    "realne polskie toponimy osadnicze: końcówki -owice (Cieszowice), -anka "
    "(Wolanka), -ino (Brzezino), -ówka, -yce",
    "nazwy będące imieniem osoby („Wieś Marka”)",
    "nazwy skopiowane wprost z Tolkiena, Wiedźmina i innych znanych serii",
]

REGION_NAMING: dict[str, dict] = {
    "kresy": {
        "label": "Kresy",
        "style": (
            "MIX słowiańsko-germański (#997) — pogranicze uzasadnia obie tradycje. "
            "Imię archaiczne słowiańskie ALBO germańskie, zwykle z przydomkiem od "
            "rzemiosła, cechy albo miejsca (nie od nazwiska rodowego)."
        ),
        "examples": ["Hanka Rogowa", "Mizel", "Wolfram", "Berta Twarda Pieczęć", "Grimm Rdzawy"],
        "place_style": (
            "MIX słowiańsko-germański (#997): słowiańskie fantasy, germańskie dark albo hybryda (słowiański rdzeń + germańska końcówka). Zachód/Imperium → germańskie, wschód/głębokie Kresy → słowiańskie, pas graniczny → hybrydy."
        ),
        "place_examples": ["Vilnograd", "Czarnobór", "Strzegwacht", "Rabenstein", "Czarnstein", "Wilczburg", "Bór Zmarłych"],
    },
    "siwe_granie": {
        "label": "Siwe Granie",
        "style": (
            "Krasnoludy: nordyckie, twarde imię + POLSKI PRZYDOMEK od rzemiosła, "
            "rodu albo cechy. Ludzie w krainie (pustelnicy, pielgrzymi) — imiona "
            "zakonne/germańskie bez przydomka."
        ),
        "examples": [
            "Balrik Siwotarczy", "Dagna Młotodzierżca", "Helga Solnobroda",
            "Torvin", "Grimm Rdzawy", "Kettil", "Brat Elias",
        ],
        "place_style": (
            "Krasnoludzkie hołdy, sztolnie i kuźnie: nazwy złożone, kamienno-górnicze, albo germańskie z końcówką -hold. Miejsca ludzkie w górach — sanktuaria i pielgrzymki."
        ),
        "place_examples": ["Kamienny Gród", "Wielka Kuźnia", "Echo-Wieża", "Sztolnia Umarłego Rodu", "Lodowa Brama", "Frosthold"],
    },
    "czarnobor": {
        "label": "Czarnobór",
        "style": (
            "Elfy: brzmienia miękkie i śpiewne, wymawialne po polsku, w stylu "
            "Władcy Pierścieni, ale BEZ kopiowania imion Tolkiena; bez przydomków. "
            "Ludzie na skraju boru (drwale, kupcy, łowcy) — imiona germańskie."
        ),
        "examples": ["Nimriel", "Cathel", "Aerlin", "Sylvar", "Erethil", "Bartel", "Hagen"],
        "place_style": (
            "Nazwy na mapie to LUDZKIE tłumaczenia elfich nazw — poetyckie, obrazowe, złożone z rzeczownika natury i cechy. Osady ludzkie na skraju boru: nazwy graniczne i strażnicze."
        ),
        "place_examples": ["Szept Koron", "Gościnne Drzewo", "Łukodzielnia", "Targ Wymienny", "Ostęp Graniczny", "Stanica Wilcza"],
    },
    "martwe_pustkowia": {
        "label": "Martwe Pustkowia",
        "style": (
            "Piętnowani: brzmienie arabskie w transliteracji przyjaznej polskiej "
            "wymowie (potomkowie kolonistów z południowych prowincji Imperium). "
            "Ludzie z zewnątrz (misja, obóz gorączki) — imiona germańskie/zakonne."
        ),
        "examples": ["Raszid", "Lejla", "Nadira", "Farid", "Greta", "Brat Ansgar", "Siostra Verena"],
        "place_style": (
            "Nazwy solne, popielne i porzucone: rzeczownik + funkcja albo ślad po Imperium (kolonia, wieża, misja). Nic sielskiego."
        ),
        "place_examples": ["Solny Próg", "Obóz Gorączki", "Misja Światła", "Targ Przewodników", "Solne Magazyny", "Aschfeld"],
    },
    "koronne_niziny": {
        "label": "Koronne Niziny",
        "style": (
            "Dwór i stolica: archaiczno-dworskie słowiańskie, często z tytułem "
            "(Kanclerz, Brat, Matka). Półświatek: PSEUDONIM-URZĄD w cudzysłowie, "
            "nie ksywka. Krasnoludy enklawy: wzór Grań (nordyckie + przydomek). "
            "Prowincja zachodnia: germańskie i hybrydy."
        ),
        "examples": [
            "Kanclerz Dobrogost", "Matka Urszula", "Brat Aleksy Złotnik",
            "„Nocny Burmistrz”", "„Rachmistrzyni”", "Gundrik Złota Waga", "Berta Twarda Pieczęć",
        ],
        "place_style": (
            "Cywilizacja Korony: miasta i dzielnice, urzędy, rogatki, klasztory. Archaiczno-dworskie słowiańskie; prowincja zachodnia — germańskie."
        ),
        "place_examples": ["Vilnograd", "Klasztor Iskry", "Rogatka Wschodnia", "Targ Wielki", "Dzielnica Złodziei"],
    },
    "wybrzeze_lez": {
        "label": "Wybrzeże Łez",
        "style": (
            "Wyspiarze (diaspora): imiona wyspiarsko-morskie, krótkie i otwarte "
            "samogłoskowo, bez przydomków. Miejscowi z lądu zachowują nazewnictwo "
            "słowiańsko-germańskie (#997)."
        ),
        "examples": ["Taio", "Nakea", "Malua", "Ravu"],
        "place_style": (
            "Porty, zatoki i doki: nazwy morskie, mroczne, słowiańsko-germańskie; miejsca diaspory wyspiarskiej brzmią obco na tle lądu."
        ),
        "place_examples": ["Czarnogród", "Zatoka Topielców", "Port Łez", "Mokra Grobla"],
    },
}

_FALLBACK_REGION = "kresy"

#: Współczesne polskie imiona, po które model sięga najczęściej. Lista jest
#: krótka i celowo nie próbuje być kompletna — łapie typowe wpadki, a reszta
#: zostaje w rękach człowieka, który i tak zatwierdza propozycję.
MODERN_POLISH_GIVEN_NAMES = {
    "agnieszka", "anna", "aneta", "barbara", "bartek", "bartosz", "beata",
    "dorota", "ewa", "grzegorz", "jacek", "jakub", "joanna", "justyna",
    "karolina", "katarzyna", "krzysztof", "kasia", "magdalena", "malgorzata",
    "małgorzata", "marcin", "marek", "mateusz", "michal", "michał", "monika",
    "pawel", "paweł", "piotr", "rafal", "rafał", "robert", "sylwia", "tomek",
    "wojciech", "zbigniew", "łukasz", "lukasz", "sebastian", "damian",
}

#: Końcówki realnych polskich nazwisk — „Kowalczyk", „Zielińska", „Nowakowski".
_POLISH_SURNAME_SUFFIXES = (
    "ski", "ska", "cki", "cka", "czyk", "czak", "wicz", "kowski", "kowska",
)

#: Kanoniczne wyjątki: imiona z kanonu, które przypadkiem wpadają w regułę
#: (np. zakonne „Brat Elias" nie jest nazwiskiem, „Aleksy" jest dworskie).
_CANON_ALLOWED = {"aleksy", "urszula", "tomasz", "dobrogost", "elias", "ansgar", "verena"}


def _norm(text: str) -> str:
    return " ".join(str(text or "").strip().split())


def looks_like_modern_polish_name(name: str) -> bool:
    """Czy to brzmi jak imię z polskiej książki telefonicznej, a nie z Kresów?

    Strażnik dla propozycji AI — nie blokuje zapisu (człowiek zatwierdza), ale
    pozwala poprosić model o drugie podejście, zanim propozycja trafi na ekran.
    """
    clean = _norm(name)
    if not clean:
        return False
    tokens = [t.strip("„”\"'.,()") for t in clean.split()]
    for token in tokens:
        low = token.lower()
        if low in _CANON_ALLOWED:
            continue
        if low in MODERN_POLISH_GIVEN_NAMES:
            return True
        if len(low) > 5 and low.endswith(_POLISH_SURNAME_SUFFIXES):
            return True
    return False


def clean_person_label(label: str) -> str:
    """Utnij rolę doklejoną do imienia („Sorea, gospodyni karczmy" → „Sorea").

    Model bywa uczynny i wpisuje zawód do pola imienia; do bazy ma iść sama
    postać, bo rola i opis mają własne pola.
    """
    clean = _norm(label)
    if not clean:
        return ""
    for sep in (",", " — ", " – ", " - "):
        if sep in clean:
            clean = clean.split(sep, 1)[0].strip()
    return clean


def _region_rule(region: str) -> dict:
    return REGION_NAMING.get(_norm(region).lower(), REGION_NAMING[_FALLBACK_REGION])


def live_name_examples(
    conn: sqlite3.Connection | None, region: str, limit: int = LIVE_EXAMPLES_LIMIT
) -> list[str]:
    """Imiona NPC, którzy JUŻ stoją w tej krainie (kanon = tabela przypisań, #1524)."""
    key = _norm(region).lower()
    if conn is None or not key:
        return []
    try:
        rows = conn.execute(
            "SELECT DISTINCT n.label FROM npcs n "
            "JOIN location_npc_assignments a ON a.npc_key = n.key "
            "  AND COALESCE(a.is_active, 1) = 1 "
            "JOIN game_locations l ON l.key = a.location_key AND l.is_active = 1 "
            "WHERE n.is_active = 1 AND l.region = ? "
            "ORDER BY n.label LIMIT ?",
            (key, int(limit)),
        ).fetchall()
    except sqlite3.Error:
        return []
    return [r[0] for r in rows if r[0]]


def naming_guidance(conn: sqlite3.Connection | None, region: str, kind: str = "person") -> dict:
    """Wytyczna nazewnicza dla krainy: styl + przykłady kanonu + przykłady żywe.

    `kind="person"` — imiona postaci; `kind="place"` — nazwy miejsc (toponimy,
    czyli rdzeń reguły #997: to po nich model najczęściej robił „Cieszowice").
    """
    rule = _region_rule(region)
    is_place = kind == "place"
    return {
        "region": _norm(region).lower() or _FALLBACK_REGION,
        "region_label": rule["label"],
        "kind": "place" if is_place else "person",
        "style": rule["place_style"] if is_place else rule["style"],
        "examples": list(rule["place_examples"] if is_place else rule["examples"]),
        "live_examples": [] if is_place else live_name_examples(conn, region),
        "avoid": list(_PLACE_AVOID if is_place else _COMMON_AVOID),
    }


def naming_prompt_block(conn: sqlite3.Connection | None, region: str = "", kind: str = "person") -> str:
    """Gotowy fragment instrukcji systemowej — do wklejenia w prompt generatora."""
    g = naming_guidance(conn, region, kind=kind)
    what = "NAZW MIEJSC" if g["kind"] == "place" else "NAZW"
    lines = [
        f"KONWENCJA {what} — kraina „{g['region_label']}” (kanon #997 + rozdział krainy):",
        g["style"],
        "Wzory z kanonu: " + ", ".join(g["examples"]) + ".",
    ]
    if g["live_examples"]:
        lines.append("Tak brzmią postacie, które już tam stoją: "
                     + ", ".join(g["live_examples"]) + ".")
    lines.append("BEZWZGLĘDNIE UNIKAJ: " + "; ".join(g["avoid"]) + ".")
    lines.append(
        "Przykłady pokazują STYL — NIE KOPIUJ ich i nie powtarzaj żadnego z tych "
        "imion. Postać ma mieć imię NOWE, którego w świecie jeszcze nie ma."
    )
    if g["kind"] == "place":
        lines.append(
            "Pytanie kontrolne przed odpowiedzią: „Czy ta nazwa mogłaby być prawdziwą "
            "wsią w Polsce?" " Jeśli tak — przerób ją na archaiczną albo wymyśloną."
        )
    else:
        lines.append(
            "Pytanie kontrolne przed odpowiedzią: „Czy ta osoba mogłaby figurować "
            "w polskiej książce telefonicznej?" " Jeśli tak — wymyśl imię od nowa."
        )
    return "\n".join(lines)


def _canon_icon_names() -> tuple[set[str], set[str]]:
    """Imiona NPC-ikon z kanonu krain — także tych, których nie ma jeszcze w DB.

    Kraina bywa zaseedowana później niż napisany rozdział (Czarnobór, Pustkowia).
    Strażnik patrzący tylko na bazę przepuściłby „Ravu" i w dniu seedowania
    Wybrzeża świat dostałby dwóch Ravu.
    """
    full: set[str] = set()
    single: set[str] = set()
    for rule in REGION_NAMING.values():
        for example in rule["examples"]:
            clean = _norm(example).strip("„”\"'").lower()
            if not clean:
                continue
            full.add(clean)
            # Ikona o jednoczłonowym imieniu (Ravu, Nimriel, Torvin): „Ravu
            # Smołoząb" to wciąż TA postać z dopiskiem. Przy ikonach dwuczłonowych
            # (Hanka Rogowa) samo imię jest wolne — imiona wolno powtarzać.
            if " " not in clean:
                single.add(clean)
    return full, single


def name_already_taken(conn: sqlite3.Connection | None, label: str) -> bool:
    """Czy taka postać już stoi w świecie albo w kanonie? (few-shot kusi do kopiowania)."""
    clean = _norm(label).lower()
    if not clean:
        return False
    canon_full, canon_single = _canon_icon_names()
    if clean in canon_full or clean.split()[0] in canon_single:
        return True
    if conn is None:
        return False
    try:
        row = conn.execute(
            "SELECT 1 FROM npcs WHERE is_active = 1 AND LOWER(TRIM(label)) = ? LIMIT 1",
            (clean,),
        ).fetchone()
    except sqlite3.Error:
        return False
    return row is not None


#: Końcówki realnych polskich toponimów osadniczych (#997).
REAL_PL_TOPONYM_SUFFIXES = re.compile(r"(owice|ówka|owka|anka|ino|yce)$", re.IGNORECASE)


def looks_like_real_pl_toponym(name: str) -> bool:
    """Czy ta nazwa miejsca mogłaby być prawdziwą polską wsią? (strażnik #997)"""
    clean = _norm(name)
    if not clean:
        return False
    return any(REAL_PL_TOPONYM_SUFFIXES.search(token) for token in clean.split())
