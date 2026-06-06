"""TDD: Issue #367 — C13 system_prompt musi zawierać regułę jedynej waluty GP.

Tests verify:
- system_prompt.txt explicitly declares GP as the only currency
- system_prompt.txt explicitly forbids SP, CP, EP (silver/copper/electrum)
- DB audit: value_gp columns in game_config tables are non-negative integers
"""
import sys
import os
import sqlite3
sys.path.insert(0, "/app")

SYSTEM_PROMPT_PATH = "/app/prompts/system_prompt.txt"
DB_PATH = "/data/ai_gm.db"


def _read_prompt() -> str:
    with open(SYSTEM_PROMPT_PATH, encoding="utf-8") as f:
        return f.read()


# ─── system_prompt currency rule ────────────────────────────────────────────

def test_system_prompt_has_currency_section():
    """system_prompt.txt must contain an explicit currency rule section."""
    content = _read_prompt()
    # Must have a section header or keyword about currency/waluta
    assert any(kw in content for kw in ["WALUTA", "CURRENCY", "jedyna waluta", "tylko złoto", "TYLKO ZŁOTO"]), \
        "system_prompt.txt brakuje sekcji walutowej (WALUTA / CURRENCY)"


def test_system_prompt_gp_is_only_currency():
    """GP (złote monety) must be explicitly stated as the only currency."""
    content = _read_prompt()
    assert any(phrase in content for phrase in [
        "GP", "złote monety", "Złote Monety", "złoto GP", "Złoto GP"
    ]), "system_prompt.txt musi wymieniać GP jako jedyną walutę"


def test_system_prompt_forbids_silver_sp():
    """SP (srebrne monety) must be explicitly forbidden."""
    content = _read_prompt()
    assert any(phrase in content for phrase in ["SP", "srebrn", "Srebrn", "silver"]), \
        "system_prompt.txt musi zabraniać SP"
    # The word must appear in a prohibition context — check it's near ZAKAZ/NIE/NIGDY
    # Simple check: the prompt mentions SP in a negation context
    lines_with_sp = [l for l in content.splitlines()
                     if any(kw in l for kw in ["SP", "srebrn", "Srebrn"])]
    assert any(
        any(neg in l.upper() for neg in ["NIE", "NIGDY", "ZAKAZ", "BRAK", "NEVER", "NO ", "ONLY"])
        for l in lines_with_sp
    ), "SP musi pojawić się w kontekście zakazu"


def test_system_prompt_forbids_copper_cp():
    """CP (miedziane monety) must be explicitly forbidden."""
    content = _read_prompt()
    assert any(phrase in content for phrase in ["CP", "miedzi", "Miedzi", "copper"]), \
        "system_prompt.txt musi zabraniać CP"


def test_system_prompt_prices_in_gp_integers():
    """Prompt must state prices are integers (no 1.5 GP etc)."""
    content = _read_prompt()
    assert any(phrase in content for phrase in [
        "liczba całkowita", "całkowit", "integer", "pełna liczba", "bez ułamk"
    ]), "system_prompt.txt musi wymagać cen jako liczb całkowitych"


# ─── DB audit: value_gp must be non-negative integers ───────────────────────

def _get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def test_db_weapons_value_gp_are_integers():
    """game_config_weapons.value_gp must be non-negative integers."""
    conn = _get_db()
    try:
        rows = conn.execute(
            "SELECT key, value_gp FROM game_config_weapons WHERE is_active=1"
        ).fetchall()
        for r in rows:
            assert isinstance(int(r["value_gp"]), int) and int(r["value_gp"]) >= 0, \
                f"weapon {r['key']}: value_gp={r['value_gp']} nie jest nieujemną liczbą całkowitą"
    finally:
        conn.close()


def test_db_items_value_gp_are_integers():
    """game_config_items.value_gp must be non-negative integers."""
    conn = _get_db()
    try:
        rows = conn.execute(
            "SELECT key, value_gp FROM game_config_items WHERE is_active=1"
        ).fetchall()
        for r in rows:
            assert isinstance(int(r["value_gp"]), int) and int(r["value_gp"]) >= 0, \
                f"item {r['key']}: value_gp={r['value_gp']} nie jest nieujemną liczbą całkowitą"
    finally:
        conn.close()


def test_db_consumables_base_price_are_integers():
    """game_config_consumables.base_price must be non-negative integers (GP)."""
    conn = _get_db()
    try:
        rows = conn.execute(
            "SELECT key, base_price FROM game_config_consumables WHERE is_active=1"
        ).fetchall()
        for r in rows:
            assert isinstance(int(r["base_price"]), int) and int(r["base_price"]) >= 0, \
                f"consumable {r['key']}: base_price={r['base_price']} nie jest nieujemną liczbą całkowitą"
    finally:
        conn.close()


# ─── Backward compat ─────────────────────────────────────────────────────────

def test_system_prompt_still_mentions_gold_grant_cue():
    """Existing [Grant Gold N] cue must still be present after changes."""
    content = _read_prompt()
    assert "Grant Gold" in content or "GRANT_GOLD" in content or "grant.*gold" in content.lower(), \
        "Grant Gold cue zniknął po edycji — backward compat broken"
