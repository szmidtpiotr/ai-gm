"""Phase 9A-0b — tests for Grant Gold cue parsing and gold updates."""

import sqlite3
from pathlib import Path
from unittest.mock import patch

from app.api.turns import extract_grant_cues, parse_grant_gold_cue, strip_last_grant_gold_cue
from app.services.loot_service import apply_character_gold_delta


def test_parse_returns_amount():
    assert parse_grant_gold_cue("Narracja.\nGrant Gold 50") == 50


def test_parse_case_insensitive():
    assert parse_grant_gold_cue("Narracja.\ngrant gold 20") == 20


def test_parse_zero_returns_none():
    assert parse_grant_gold_cue("Narracja.\nGrant Gold 0") is None


def test_parse_no_cue_returns_none():
    assert parse_grant_gold_cue("Zwykła narracja bez cue.") is None


def test_parse_cue_not_last_line_returns_none():
    assert parse_grant_gold_cue("Grant Gold 50\nDalszy tekst.") is None


def test_strip_removes_last_line():
    assert strip_last_grant_gold_cue("Narracja.\nGrant Gold 50") == "Narracja."


def test_strip_no_cue_unchanged():
    text = "Zwykła narracja."
    assert strip_last_grant_gold_cue(text) == text


def test_extract_grant_gold_from_json_roll_cue():
    src = '{"narrative":"Kupiec płaci.","location_intent":null,"roll_cue":"Grant Gold 7"}'
    clean, item, gold = extract_grant_cues(src)
    assert item is None
    assert gold == 7
    assert '"roll_cue": null' in clean


def test_apply_gold_delta_adds():
    tmp = Path(__file__).resolve().parent / "_grant_gold_cue.db"
    if tmp.exists():
        tmp.unlink()
    conn = sqlite3.connect(str(tmp))
    try:
        conn.executescript(
            """
            CREATE TABLE characters (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              gold_gp INTEGER NOT NULL DEFAULT 0
            );
            INSERT INTO characters (id, gold_gp) VALUES (1, 10);
            """
        )
        conn.commit()
    finally:
        conn.close()

    with patch("app.services.loot_service.LOOT_DB_PATH", str(tmp)):
        new_total = apply_character_gold_delta(1, 50, "grant_gold_cue")

    conn2 = sqlite3.connect(str(tmp))
    try:
        row = conn2.execute("SELECT gold_gp FROM characters WHERE id = 1").fetchone()
        after = int(row[0] or 0) if row else 0
    finally:
        conn2.close()
        if tmp.exists():
            tmp.unlink()

    assert new_total == 60
    assert after == 60
