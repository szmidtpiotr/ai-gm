"""TDD: Issue #1295 — deterministyczny capture NPC z narracji.

Warstwa 2: po turze skanuj narrację względem zamkniętego słownika (nazwy
plan.key_npcs + katalog npcs.label) i auto-rejestruj trafienia w
campaign_known_npcs — bez zależności od opcjonalnych tagów LLM.
"""
import sqlite3
import json

from app.services.npc_memory_service import capture_known_names_in_narration


def _mkdb() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE campaigns (id INTEGER PRIMARY KEY, gm_plan_json TEXT)")
    conn.execute(
        """CREATE TABLE campaign_known_npcs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL,
            npc_id INTEGER, npc_name TEXT, role TEXT,
            first_met_location TEXT, first_met_turn INTEGER, notes TEXT,
            relation_status TEXT, created_at TEXT, updated_at TEXT,
            purchase_count INTEGER, stats_json TEXT,
            UNIQUE(campaign_id, npc_name)
        )"""
    )
    conn.execute("CREATE TABLE npcs (id INTEGER PRIMARY KEY, key TEXT, label TEXT)")
    return conn


_PLAN = {
    "key_npcs": [
        {"key": "brunn_zelaznoreki", "name": "Brunn Żelaznoręki",
         "role": "kowal", "importance": "critical", "alive": True},
        {"key": "karczmarz_jorek", "name": "Jorek",
         "role": "karczmarz", "importance": "supporting", "alive": True},
    ]
}


def _seed(conn, cid=9998881):
    conn.execute(
        "INSERT INTO campaigns (id, gm_plan_json) VALUES (?, ?)",
        (cid, json.dumps(_PLAN)),
    )
    conn.commit()


# ─── Test główny ─────────────────────────────────────────────────────────────

def test_captures_plan_npc_mentioned_by_first_name():
    """Narracja wspomina 'Brunn' (imię z planu) → wpis bez żadnego tagu LLM."""
    conn = _mkdb()
    _seed(conn)
    text = "Brunn kiwa głową i podnosi młot. Kuźnia jest gorąca."
    captured = capture_known_names_in_narration(conn, 9998881, text, turn_num=3)
    names = {
        r["npc_name"]
        for r in conn.execute(
            "SELECT npc_name FROM campaign_known_npcs WHERE campaign_id=?", (9998881,)
        )
    }
    assert "Brunn Żelaznoręki" in names
    assert "Brunn Żelaznoręki" in captured


def test_captures_catalog_label():
    """Nazwa z katalogu npcs.label wspomniana w narracji → wpis."""
    conn = _mkdb()
    _seed(conn)
    conn.execute("INSERT INTO npcs (id, key, label) VALUES (?, ?, ?)",
                 (12, "handlarz_orin", "Orin"))
    conn.commit()
    text = "Za ladą stoi Orin i przelicza monety."
    capture_known_names_in_narration(conn, 9998881, text, turn_num=4)
    names = {
        r["npc_name"]
        for r in conn.execute(
            "SELECT npc_name FROM campaign_known_npcs WHERE campaign_id=?", (9998881,)
        )
    }
    assert "Orin" in names


def test_no_duplicate_when_already_known():
    """Znany już NPC nie jest duplikowany."""
    conn = _mkdb()
    _seed(conn)
    conn.execute(
        "INSERT INTO campaign_known_npcs (campaign_id, npc_name) VALUES (?, ?)",
        (9998881, "Brunn Żelaznoręki"),
    )
    conn.commit()
    text = "Brunn znów wita bohatera."
    capture_known_names_in_narration(conn, 9998881, text, turn_num=5)
    n = conn.execute(
        "SELECT COUNT(*) FROM campaign_known_npcs WHERE campaign_id=? AND npc_name=?",
        (9998881, "Brunn Żelaznoręki"),
    ).fetchone()[0]
    assert n == 1


def test_word_boundary_no_substring_match():
    """Token 'Brunn' nie łapie się wewnątrz innego słowa (np. Brunnhilda)."""
    conn = _mkdb()
    _seed(conn)
    text = "Brunnhilda przemierza las, nikt inny się nie pojawia."
    captured = capture_known_names_in_narration(conn, 9998881, text, turn_num=6)
    assert "Brunn Żelaznoręki" not in captured


def test_unknown_name_not_captured():
    """Nazwa spoza słownika (plan+katalog) nie tworzy wpisu (brak false-positive)."""
    conn = _mkdb()
    _seed(conn)
    text = "Tajemniczy Zdzisław znika w mroku."
    captured = capture_known_names_in_narration(conn, 9998881, text, turn_num=7)
    assert captured == []
    n = conn.execute(
        "SELECT COUNT(*) FROM campaign_known_npcs WHERE campaign_id=?", (9998881,)
    ).fetchone()[0]
    assert n == 0


def test_empty_text_noop():
    conn = _mkdb()
    _seed(conn)
    assert capture_known_names_in_narration(conn, 9998881, "", turn_num=1) == []
