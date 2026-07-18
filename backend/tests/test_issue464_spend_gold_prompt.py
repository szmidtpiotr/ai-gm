"""TDD: Issue #464 (F4) — system prompt musi instruować LLM o tagu [SPEND_GOLD:key].

Bug: parser spend_gold_service.py istnieje i działa, ale LLM nigdy nie wstawia tagu,
bo system_prompt.txt go nie opisuje. Skutek: bohater "płaci" w narracji, ale złoto
nie jest odejmowane (gold 38 -> 38 zamiast 38 -> 33).

Fix: dodać sekcję SPEND_GOLD do system_prompt.txt z listą kluczy usług.
Kwota nadal pochodzi z DB (game_config_services) — LLM wskazuje tylko klucz.
"""
import os
import sqlite3
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from _fixtures_schema import table_sql

from app.system_prompt_loader import load_system_prompt_text
from app.services.spend_gold_service import apply_spend_gold_to_narrative

# Klucze usług zasiane w migrations_admin.py (F4 seed)
SEEDED_SERVICE_KEYS = [
    "inn_night", "inn_night_fine", "healer_light", "healer_heavy",
    "stable_night", "blacksmith_repair", "messenger", "guide_day",
]


# ─── Test główny — prompt dokumentuje tag ────────────────────────────────────

def test_system_prompt_documents_spend_gold_tag():
    """System prompt MUSI opisać tag [SPEND_GOLD:key], inaczej LLM go nie wstawi."""
    prompt = load_system_prompt_text()
    assert "[SPEND_GOLD:" in prompt, (
        "Brak formatu tagu [SPEND_GOLD:...] w system_prompt.txt — "
        "LLM nie wie, że ma go wstawiać przy płatnościach za usługi."
    )
    assert "SPEND_GOLD" in prompt
    # nagłówek sekcji (## SPEND_GOLD ...)
    assert "## SPEND_GOLD" in prompt, "Brak sekcji nagłówkowej ## SPEND_GOLD."


def test_system_prompt_lists_service_keys():
    """Prompt MUSI wymieniać klucze usług, żeby LLM wybrał właściwy (nie zmyślał)."""
    prompt = load_system_prompt_text()
    missing = [k for k in SEEDED_SERVICE_KEYS if k not in prompt]
    assert not missing, (
        f"Klucze usług nieobecne w system_prompt.txt: {missing}. "
        "LLM nie będzie wiedział jakiego klucza użyć dla danej usługi."
    )


def test_system_prompt_forbids_llm_choosing_amount():
    """Prompt MUSI jasno mówić, że kwota pochodzi z bazy, nie od LLM (anty-cheat)."""
    prompt = load_system_prompt_text().lower()
    # przynajmniej jeden z sygnałów: "kwot", "cen", "z bazy", "z tabeli", "system"
    # w kontekście że LLM nie podaje liczby
    assert "spend_gold" in prompt
    # Klucz, nie kwota — instrukcja musi zawierać słowo "klucz"
    section_start = prompt.find("## spend_gold")
    assert section_start != -1
    section = prompt[section_start:section_start + 1200]
    assert "klucz" in section, (
        "Sekcja SPEND_GOLD musi podkreślać, że LLM wstawia KLUCZ, nie kwotę."
    )
    # Musi zaznaczyć, że nie wpisujemy liczby/kwoty samodzielnie
    assert ("nie podawaj" in section or "nie wpisuj" in section
            or "nie decyduj" in section or "nie zmyśl" in section), (
        "Sekcja musi wprost zabronić LLM podawania własnej kwoty."
    )


# ─── Backward compatibility — parser nadal działa ────────────────────────────

def _mk_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        """ + table_sql("game_config_services") + """
        CREATE TABLE characters (id INTEGER PRIMARY KEY, gold_gp INTEGER);
        INSERT INTO game_config_services (key, label, cost_gp, is_active)
            VALUES ('inn_night', 'Gospoda', 5, 1);
        INSERT INTO characters (id, gold_gp) VALUES (1, 8);
        """
    )
    return conn


def test_parser_still_deducts_gold_on_affordable_tag():
    """Stary kontrakt: tag w narracji odejmuje złoto i znika z tekstu."""
    conn = _mk_conn()
    out = apply_spend_gold_to_narrative(
        "Nocleg [SPEND_GOLD:inn_night] zapłacony.", conn, 1
    )
    assert "[SPEND_GOLD" not in out
    gold = conn.execute("SELECT gold_gp FROM characters WHERE id=1").fetchone()[0]
    assert gold == 3, f"oczekiwano 3 (8-5), jest {gold}"


def test_parser_refuses_when_insufficient():
    """Stary kontrakt: za mało złota → komunikat odmowy, złoto bez zmian."""
    conn = _mk_conn()
    conn.execute("UPDATE characters SET gold_gp = 2 WHERE id = 1")
    out = apply_spend_gold_to_narrative("[SPEND_GOLD:inn_night]", conn, 1)
    assert "Nie masz wystarczająco złota" in out
    gold = conn.execute("SELECT gold_gp FROM characters WHERE id=1").fetchone()[0]
    assert gold == 2
