"""TDD: Issue #1527 (fala 4, runda 3) — podpowiedź AI musi znać KONWENCJĘ NAZW.

Podpowiadacz gospodarza (runda 2) dostawał tylko nazwę miejsca i krainę, więc
model robił to, co robi każdy model bez reguły: sypał współczesnymi polskimi
imionami („Agnieszka Kruk", „Anna Riedel"). To łamie kanon — konwencja nazw jest
ustalona od #997 i doprecyzowana per kraina w `docs/world/regions/*.md`:

* **Kresy** — MIX słowiańsko-germański, przydomek od rzemiosła (Hanka Rogowa).
* **Siwe Granie** — krasnoludy: nordyckie imię + polski przydomek
  (Balrik Siwotarczy, Helga Solnobroda).
* **Czarnobór** — elfy: miękkie, śpiewne, styl LotR bez kopiowania Tolkiena
  (Nimriel, Sylvar); ludzie na skraju boru — germańskie (Bartel, Hagen).
* **Martwe Pustkowia** — Piętnowani: brzmienie arabskie w polskiej transliteracji
  (Raszid, Lejla, Farid).
* **Koronne Niziny** — dwór: archaiczno-dworskie słowiańskie (Kanclerz Dobrogost);
  półświatek: pseudonim-urząd („Nocny Burmistrz").
* **Wybrzeże Łez** — wyspiarze: Taio, Nakea, Malua.

Ta runda daje `world_naming_service`, który zamienia ten kanon w wytyczną dla
modelu (+ przykłady z żywej bazy) i strażnika, który łapie współczesne polskie
imię, zanim trafi do świata.

Uruchomienie:
    ./scripts/test_dev.sh tests/test_issue1527c_naming_convention.py -v
"""
from __future__ import annotations

import sqlite3

import pytest

from app.services.world_naming_service import (
    REGION_NAMING,
    clean_person_label,
    looks_like_modern_polish_name,
    name_already_taken,
    naming_guidance,
    naming_prompt_block,
)

from tests.test_issue1527_world_lint import SCHEMA, _add_location  # noqa: F401


@pytest.fixture()
def conn() -> sqlite3.Connection:
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript(SCHEMA)
    c.executemany(
        "INSERT INTO world_regions (key, label, status) VALUES (?,?,?)",
        [("kresy", "Kresy", "live"), ("siwe_granie", "Siwe Granie", "live")],
    )
    c.commit()
    yield c
    c.close()


# ─── Kanon per kraina ────────────────────────────────────────────────────────

def test_every_canon_region_has_its_own_naming_rule(conn):
    """Szesc krain kanonu = szesc regul; brak wpisu = model zgaduje."""
    assert set(REGION_NAMING) >= {
        "kresy", "siwe_granie", "czarnobor", "martwe_pustkowia",
        "koronne_niziny", "wybrzeze_lez",
    }


def test_dwarf_region_asks_for_nordic_name_with_polish_epithet(conn):
    g = naming_guidance(conn, "siwe_granie")
    assert "przydom" in g["style"].lower()
    assert any("Solnobroda" in e or "Siwotarczy" in e for e in g["examples"])


def test_elf_region_uses_soft_singing_names(conn):
    g = naming_guidance(conn, "czarnobor")
    assert "Nimriel" in g["examples"] or "Sylvar" in g["examples"]
    assert "tolkien" in g["style"].lower()


def test_marked_region_uses_arabic_sounding_names(conn):
    g = naming_guidance(conn, "martwe_pustkowia")
    assert any(n in g["examples"] for n in ("Raszid", "Lejla", "Farid", "Nadira"))


def test_unknown_region_falls_back_to_kresy_mix(conn):
    """Nieznana kraina nie moze znaczyc „rob co chcesz" — spada na regule #997."""
    g = naming_guidance(conn, "nie_ma_takiej_krainy")
    assert g["style"] == REGION_NAMING["kresy"]["style"]


def test_guidance_always_forbids_modern_polish_names(conn):
    for region in REGION_NAMING:
        g = naming_guidance(conn, region)
        joined = " ".join(g["avoid"]).lower()
        assert "agnieszka" in joined or "wspó" in joined or "wspo" in joined


# ─── Przykłady z żywej bazy (few-shot) ───────────────────────────────────────

def test_guidance_pulls_live_names_from_the_same_region(conn):
    """Model uczy sie na tym, co juz stoi w tej krainie — nie na abstrakcji."""
    _add_location(conn, "kamienny_grod_kuznia", location_subtype="smithy", region="siwe_granie")
    conn.execute("INSERT INTO npcs (key, label) VALUES ('torvin', 'Torvin Rudobrody')")
    conn.execute(
        "INSERT INTO location_npc_assignments (location_key, npc_key) VALUES (?,?)",
        ("kamienny_grod_kuznia", "torvin"),
    )
    conn.commit()

    g = naming_guidance(conn, "siwe_granie")
    assert "Torvin Rudobrody" in g["live_examples"]


def test_live_examples_do_not_leak_between_regions(conn):
    _add_location(conn, "karczma", location_subtype="tavern", region="kresy")
    conn.execute("INSERT INTO npcs (key, label) VALUES ('hanka', 'Hanka Rogowa')")
    conn.execute(
        "INSERT INTO location_npc_assignments (location_key, npc_key) VALUES (?,?)",
        ("karczma", "hanka"),
    )
    conn.commit()

    assert "Hanka Rogowa" not in naming_guidance(conn, "siwe_granie")["live_examples"]


def test_live_examples_are_capped(conn):
    for i in range(20):
        _add_location(conn, f"loc_{i}", location_subtype="tavern", region="kresy")
        conn.execute("INSERT INTO npcs (key, label) VALUES (?,?)", (f"npc_{i}", f"Gospodarz {i}"))
        conn.execute(
            "INSERT INTO location_npc_assignments (location_key, npc_key) VALUES (?,?)",
            (f"loc_{i}", f"npc_{i}"),
        )
    conn.commit()

    assert len(naming_guidance(conn, "kresy")["live_examples"]) <= 8


# ─── Blok promptu ────────────────────────────────────────────────────────────

def test_prompt_block_carries_style_examples_and_bans(conn):
    block = naming_prompt_block(conn, "siwe_granie")
    assert "KONWENCJA NAZW" in block
    assert "Siwe Granie" in block or "krasnolud" in block.lower()
    assert "Agnieszka" in block, "zakaz musi byc pokazany na konkretnym przykladzie"


def test_prompt_block_of_unknown_region_still_has_rules(conn):
    assert "KONWENCJA NAZW" in naming_prompt_block(conn, "")


def test_prompt_block_forbids_copying_the_examples(conn):
    """Model dostajac przyklady kopiowal je zywcem („Hanka Rogowa" x2 w swiecie)."""
    block = naming_prompt_block(conn, "kresy")
    low = block.lower()
    assert "nie kopiuj" in low or "nie powtarzaj" in low
    assert "nowe" in low or "nową" in low or "nowa" in low


# ─── Strażnik: imię już zajęte ───────────────────────────────────────────────

def test_taken_name_is_detected_case_insensitively(conn):
    conn.execute("INSERT INTO npcs (key, label) VALUES ('hanka', 'Hanka Rogowa')")
    conn.commit()

    assert name_already_taken(conn, "hanka rogowa") is True
    assert name_already_taken(conn, "  Hanka   Rogowa ") is True
    assert name_already_taken(conn, "Hanka Solnobroda") is False


def test_taken_name_ignores_inactive_npcs(conn):
    conn.execute("INSERT INTO npcs (key, label, is_active) VALUES ('duch', 'Stary Duch', 0)")
    conn.commit()

    assert name_already_taken(conn, "Stary Duch") is False


def test_taken_name_on_empty_input(conn):
    assert name_already_taken(conn, "") is False


def test_taken_name_also_covers_canon_icons_not_yet_in_db(conn):
    """Model podal „Ravu" — imie NPC-ikony z kanonu Wybrzeza, ktorego nie ma jeszcze w DB.

    Straznik patrzacy tylko na baze przepuscilby je i swiat dostalby dwoch Ravu
    w dniu seedowania krainy.
    """
    assert name_already_taken(conn, "Ravu") is True
    assert name_already_taken(conn, "Nimriel") is True
    assert name_already_taken(conn, "Balrik Siwotarczy") is True
    assert name_already_taken(conn, "Mizgor Kamienny Szept") is False


# ─── Wariant dla MIEJSC (toponimy — rdzeń reguły #997) ──────────────────────

def test_place_variant_bans_real_polish_toponyms(conn):
    """#997 powstalo wlasnie po to: model robil „Cieszowice" i „Wolanke"."""
    block = naming_prompt_block(conn, "kresy", kind="place")
    low = block.lower()
    assert "-owice" in low and "-anka" in low
    assert "vilnograd" in low or "strzegwacht" in low


def test_place_variant_differs_from_person_variant(conn):
    assert naming_prompt_block(conn, "kresy", kind="place") != naming_prompt_block(conn, "kresy")


def test_place_variant_is_region_aware(conn):
    granie = naming_prompt_block(conn, "siwe_granie", kind="place").lower()
    assert "gród" in granie or "grod" in granie or "sztolnia" in granie or "hold" in granie


def test_place_variant_for_every_region_has_examples(conn):
    for region in REGION_NAMING:
        g = naming_guidance(conn, region, kind="place")
        assert g["examples"], f"{region}: brak wzorów nazw miejsc"


def test_person_variant_stays_the_default(conn):
    assert naming_guidance(conn, "kresy")["examples"] == REGION_NAMING["kresy"]["examples"]


def test_place_toponym_guard_catches_real_pl_endings():
    from app.services.world_naming_service import looks_like_real_pl_toponym

    assert looks_like_real_pl_toponym("Cieszowice") is True
    assert looks_like_real_pl_toponym("Wolanka") is True
    assert looks_like_real_pl_toponym("Brzezino") is True
    assert looks_like_real_pl_toponym("Vilnograd") is False
    assert looks_like_real_pl_toponym("Strzegwacht") is False
    assert looks_like_real_pl_toponym("") is False


# ─── Religia: świat ma własny kult, nie naszych świętych ────────────────────

def test_naming_bans_real_world_saints(conn):
    """Model zaproponowal „Kaplice Swietego Floriana" — patrona z NASZEGO swiata.

    Kanon ma wlasna religie (Swiatlo, Klasztor Iskry, Biala Bogini, kulty
    Rdzenia). Realny swiety wyrywa gracza z fikcji.
    """
    for kind in ("person", "place"):
        block = naming_prompt_block(conn, "kresy", kind=kind).lower()
        assert "florian" in block or "świętych z naszego" in block or "swietych z naszego" in block
        assert "iskr" in block or "światł" in block or "swiatl" in block


# ─── Wołanie bez połączenia (generatory, które nie mają conn w zasięgu) ──────

def test_block_works_without_a_db_connection():
    """15 z 19 generatorow nie ma conn w zasiegu — brak polaczenia nie moze
    znaczyc „brak konwencji"."""
    block = naming_prompt_block(None, "kresy")
    assert "KONWENCJA" in block and "Agnieszka" in block


def test_guidance_without_connection_has_no_live_examples():
    assert naming_guidance(None, "siwe_granie")["live_examples"] == []


def test_taken_name_without_connection_still_checks_canon():
    assert name_already_taken(None, "Nimriel") is True
    assert name_already_taken(None, "Mizgor Kamienny Szept") is False


# ─── Sprzątanie etykiety ─────────────────────────────────────────────────────

def test_role_glued_to_the_name_is_trimmed():
    """Model zwraca „Sorea, gospodyni karczmy" — do pola Imie ma isc sama Sorea."""
    assert clean_person_label("Sorea, gospodyni karczmy") == "Sorea"
    assert clean_person_label("Balrik Siwotarczy — starszy rodow") == "Balrik Siwotarczy"
    assert clean_person_label("  Hanka Rogowa  ") == "Hanka Rogowa"


def test_clean_label_keeps_canon_pseudonyms():
    assert clean_person_label("„Nocny Burmistrz”") == "„Nocny Burmistrz”"


def test_clean_label_on_empty_input():
    assert clean_person_label("") == ""


# ─── Strażnik: współczesne polskie imię ──────────────────────────────────────

@pytest.mark.parametrize("name", [
    "Agnieszka Kruk", "Anna Riedel", "Piotr Nowak", "Bartek Kowalski",
    "Katarzyna", "Michał Wiśniewski",
])
def test_guard_catches_modern_polish_names(name):
    assert looks_like_modern_polish_name(name) is True


@pytest.mark.parametrize("name", [
    "Hanka Rogowa", "Balrik Siwotarczy", "Nimriel", "Raszid", "Grimm Rdzawy",
    "Berta Twarda Pieczęć", "Wolfram", "Taio", "Kanclerz Dobrogost",
])
def test_guard_passes_canon_names(name):
    assert looks_like_modern_polish_name(name) is False


def test_guard_ignores_empty_input():
    assert looks_like_modern_polish_name("") is False


def test_guard_catches_real_polish_surname_endings():
    assert looks_like_modern_polish_name("Dobrogost Kowalczyk") is True
    assert looks_like_modern_polish_name("Marta Zielińska") is True
