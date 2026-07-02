"""TDD: Issue #1100 — Ustrukturyzowana pamięć bohatera (key_decisions_json).

Zamknięcie kampanii zapisuje kluczowe decyzje jako STRUKTURĘ obok prozy.
get_hero_chronicle potrafi wstrzyknąć relevantny podzbiór (region/NPC).
Stare wiersze bez struktury → fallback do prozy (zero regresji).
"""
import os
import sqlite3

import pytest

from app.services import chapter_summary_service as css


# ─── in-memory DB helper ─────────────────────────────────────────────────────

def _mem_db(with_decisions_col: bool = True) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    decisions_col = "key_decisions_json TEXT," if with_decisions_col else ""
    conn.execute(f"""
        CREATE TABLE character_campaign_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id INTEGER NOT NULL,
            campaign_id INTEGER NOT NULL,
            outcome TEXT NOT NULL DEFAULT 'active',
            chapter_summary TEXT,
            abandonment_note TEXT,
            {decisions_col}
            completed_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE characters (
            id INTEGER PRIMARY KEY,
            name TEXT,
            legend_digest TEXT,
            legend_digest_count INTEGER DEFAULT 0
        )
    """)
    conn.execute("CREATE TABLE campaigns (id INTEGER PRIMARY KEY, title TEXT)")
    conn.execute("INSERT INTO characters (id, name) VALUES (7, 'Grimm')")
    conn.execute("INSERT INTO campaigns (id, title) VALUES (100, 'Upadek Vilnogradu')")
    conn.commit()
    return conn


# ─── Test główny: normalizacja struktury ─────────────────────────────────────

def test_normalize_key_decisions_validates_structure():
    """Ekstraktor zwraca listę wpisów o ustalonym kształcie, waga zaciśnięta."""
    raw = {
        "decisions": [
            {"typ": "sojusz", "opis": "Uratował kupca Aldera",
             "konsekwencja": "Alder otworzył sklep", "npc": "Alder",
             "region": "kresy", "waga": 4},
            {"typ": "wrogosc", "opis": "Zdradził barona",
             "konsekwencja": "Baron wysłał zabójców", "npc": "Baron Wolf",
             "waga": 99},                      # waga poza zakresem → zaciśnięta
            {"opis": "brak typu i konsekwencji"},   # niepełny → uzupełniony/odrzucony
            "nie-dict",                              # śmieć → pominięty
        ]
    }
    out = css.normalize_key_decisions(raw)
    assert isinstance(out, list)
    assert len(out) >= 2                        # dwa poprawne wpisy przetrwały
    first = out[0]
    for k in ("typ", "opis", "konsekwencja", "npc", "region", "waga"):
        assert k in first                       # kształt kanoniczny
    wagi = [d["waga"] for d in out]
    assert all(1 <= w <= 5 for w in wagi)       # waga 1..5


def test_normalize_key_decisions_accepts_bare_list():
    """LLM może zwrócić samą listę (bez klucza 'decisions')."""
    out = css.normalize_key_decisions([
        {"typ": "moralna", "opis": "Oszczędził jeńca", "konsekwencja": "..."},
    ])
    assert len(out) == 1
    assert out[0]["typ"] == "moralna"


# ─── Filtrowanie po regionie / NPC ───────────────────────────────────────────

def test_filter_key_decisions_by_region_and_npc():
    """Wstrzykiwany jest tylko relevantny podzbiór (region lub NPC)."""
    decisions = [
        {"typ": "sojusz", "opis": "A", "konsekwencja": "", "npc": "Alder",
         "region": "kresy", "waga": 5},
        {"typ": "wrogosc", "opis": "B", "konsekwencja": "", "npc": "Zula",
         "region": "pustkowia", "waga": 3},
        {"typ": "moralna", "opis": "C", "konsekwencja": "", "npc": "",
         "region": "gory", "waga": 2},
    ]
    by_region = css.filter_key_decisions(decisions, region="kresy")
    assert len(by_region) == 1 and by_region[0]["opis"] == "A"

    by_npc = css.filter_key_decisions(decisions, npcs=["Zula"])
    assert len(by_npc) == 1 and by_npc[0]["opis"] == "B"

    # brak kryteriów → nic nie filtruje (pusta lista = brak wstrzyknięcia)
    none = css.filter_key_decisions(decisions)
    assert none == []


# ─── get_hero_chronicle: wstrzyknięcie podzbioru ─────────────────────────────

def test_get_hero_chronicle_injects_relevant_subset():
    """Podanie region/NPC dokłada sekcję KLUCZOWE DECYZJE tylko z pasującymi wpisami."""
    import json
    conn = _mem_db(with_decisions_col=True)
    decisions = [
        {"typ": "sojusz", "opis": "Uratował Aldera", "konsekwencja": "wdzięczny",
         "npc": "Alder", "region": "kresy", "waga": 5},
        {"typ": "wrogosc", "opis": "Zdradził Zulę", "konsekwencja": "wróg",
         "npc": "Zula", "region": "pustkowia", "waga": 4},
    ]
    conn.execute(
        "UPDATE character_campaign_history SET key_decisions_json = ? WHERE id = ?",
        (json.dumps(decisions, ensure_ascii=False), 0),
    )
    conn.execute(
        """INSERT INTO character_campaign_history
           (character_id, campaign_id, outcome, chapter_summary, key_decisions_json, completed_at)
           VALUES (7, 100, 'victory', 'Grimm zwyciężył.', ?, datetime('now'))""",
        (json.dumps(decisions, ensure_ascii=False),),
    )
    conn.commit()

    out = css.get_hero_chronicle(conn, 7, relevant_region="kresy")
    assert "KLUCZOWE DECYZJE" in out
    assert "Aldera" in out          # region kresy dopasowany
    assert "Zulę" not in out        # pustkowia odfiltrowane


# ─── Backward compat: stare wiersze bez struktury → proza ────────────────────

def test_get_hero_chronicle_backward_compat_prose_only():
    """Wiersz bez key_decisions_json → zwraca prozę, brak sekcji struktury, brak crasha."""
    conn = _mem_db(with_decisions_col=True)
    conn.execute(
        """INSERT INTO character_campaign_history
           (character_id, campaign_id, outcome, chapter_summary, completed_at)
           VALUES (7, 100, 'death', 'Grimm padł w boju.', datetime('now'))""",
    )
    conn.commit()
    out = css.get_hero_chronicle(conn, 7, relevant_region="kresy")
    assert "Grimm padł w boju." in out       # proza obecna
    assert "KLUCZOWE DECYZJE" not in out      # brak struktury → brak sekcji


def test_get_hero_chronicle_missing_column_fallback():
    """DB bez kolumny key_decisions_json → nadal proza, zero crasha."""
    conn = _mem_db(with_decisions_col=False)
    conn.execute(
        """INSERT INTO character_campaign_history
           (character_id, campaign_id, outcome, chapter_summary, completed_at)
           VALUES (7, 100, 'victory', 'Grimm zwyciężył ponownie.', datetime('now'))""",
    )
    conn.commit()
    out = css.get_hero_chronicle(conn, 7, relevant_region="kresy")
    assert "Grimm zwyciężył ponownie." in out
    assert "KLUCZOWE DECYZJE" not in out
