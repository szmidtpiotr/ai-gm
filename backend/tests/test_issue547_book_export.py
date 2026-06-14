"""TDD: Issue #547 (G20) — eksport kampanii do powieści (Bielik/Ollama na .170).

Testujemy DETERMINISTYCZNY rdzeń skryptu eksportu:
  - pobranie historii kampanii z DB (kolejność tur),
  - podział materiału na rozdziały (~N tur na rozdział),
  - budowę promptu nowelizacji (kontrakt: polski, 3. osoba, proza+dialogi,
    twardy zakaz halucynacji, materiał źródłowy w treści),
  - składanie pliku Markdown (tytuł H1 + rozdziały H2, kolejność),
  - orkiestrator z mockowanym Ollama (max_chapters dla pilota).

Jakość samej prozy ocenia Piotr w pilocie — to NIE jest testowane tutaj.
"""
import os
import sqlite3
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services import book_export_service as bx


# ─── Pomocnik: turn dict ──────────────────────────────────────────────────────

def _turn(n, user="", assistant="opis MG"):
    return {"turn_number": n, "user_text": user, "assistant_text": assistant, "route": "narrative"}


# ─── Test główny: podział na rozdziały ─────────────────────────────────────────

def test_chunk_into_chapters_groups_by_size():
    """7 tur, 3 na rozdział → 3 rozdziały (3+3+1)."""
    turns = [_turn(i) for i in range(1, 8)]
    chapters = bx.chunk_into_chapters(turns, turns_per_chapter=3)
    assert len(chapters) == 3
    assert [len(c) for c in chapters] == [3, 3, 1]


def test_chunk_preserves_turn_order():
    """Kolejność tur w obrębie i między rozdziałami zachowana."""
    turns = [_turn(i) for i in range(1, 7)]
    chapters = bx.chunk_into_chapters(turns, turns_per_chapter=2)
    flat = [t["turn_number"] for ch in chapters for t in ch]
    assert flat == [1, 2, 3, 4, 5, 6]


def test_chunk_empty_returns_empty():
    """Brak tur → brak rozdziałów (kampania bez historii)."""
    assert bx.chunk_into_chapters([], turns_per_chapter=5) == []


# ─── Test główny: prompt nowelizacji (kontrakt) ────────────────────────────────

def test_build_chapter_prompt_has_constraints():
    """Prompt MUSI wymuszać: polski, 3. osoba, proza+dialogi, zakaz halucynacji,
    oraz zawierać materiał źródłowy (tekst tur)."""
    chapter = [_turn(1, user="Wchodzę do jaskini", assistant="Mrok pochłania korytarz")]
    prompt = bx.build_chapter_prompt(chapter, chapter_index=0, total_chapters=3)
    low = prompt.lower()
    # polski + proza literacka + 3. osoba + dialogi
    assert "pol" in low  # język polski wymuszony
    assert "trzeci" in low or "3" in low  # trzecia osoba
    assert "dialog" in low
    # twardy zakaz wymyślania zdarzeń spoza materiału
    assert "nie wymyśl" in low or "nie dodawaj" in low or "wyłącznie" in low
    # materiał źródłowy obecny w treści promptu
    assert "Wchodzę do jaskini" in prompt
    assert "Mrok pochłania korytarz" in prompt


def test_build_chapter_prompt_threads_previous_summary():
    """Dla rozdziału >1 prompt dostaje kontekst poprzedniego (stały styl/ciągłość)."""
    chapter = [_turn(7)]
    prompt = bx.build_chapter_prompt(
        chapter, chapter_index=1, total_chapters=3, prev_summary="Bohater dotarł do wioski."
    )
    assert "Bohater dotarł do wioski." in prompt


# ─── Test główny: składanie Markdown ───────────────────────────────────────────

def test_assemble_book_markdown_structure():
    """# tytuł na górze, ## Rozdział N dla każdego rozdziału, w kolejności."""
    md = bx.assemble_book_markdown("Kronika Demo", ["Treść pierwsza.", "Treść druga."])
    lines = md.splitlines()
    assert lines[0] == "# Kronika Demo"
    assert md.count("\n## ") == 2  # dwa nagłówki rozdziałów
    assert md.index("Treść pierwsza.") < md.index("Treść druga.")


# ─── Integracja: pobranie historii z realnej bazy DEV ──────────────────────────

def test_fetch_campaign_history_returns_ordered_turns():
    """Kampania 61 (#546, Demo) ma >8 tur, posortowanych po turn_number rosnąco."""
    if not os.path.exists(bx.DB_PATH):
        pytest.skip("DB only available inside DEV backend container")
    data = bx.fetch_campaign_history(61)
    assert data["title"]
    assert len(data["turns"]) >= 8
    nums = [t["turn_number"] for t in data["turns"]]
    assert nums == sorted(nums)
    # tury narracyjne mają tekst MG
    assert any(t["assistant_text"] for t in data["turns"])


# ─── Orkiestrator z mockowanym Ollama (bez realnego LLM) ───────────────────────

def test_export_campaign_book_respects_max_chapters(monkeypatch):
    """Pilot: max_chapters=2 → tylko 2 wywołania LLM i 2 rozdziały w wyjściu."""
    if not os.path.exists(bx.DB_PATH):
        pytest.skip("DB only available inside DEV backend container")

    calls = {"n": 0}

    def fake_novelize(prompt, **kw):
        calls["n"] += 1
        return f"ROZDZIAL_PROZA_{calls['n']}"

    monkeypatch.setattr(bx, "novelize_chapter", fake_novelize)
    md = bx.export_campaign_book(61, turns_per_chapter=4, max_chapters=2)
    assert calls["n"] == 2  # dokładnie 2 rozdziały znowelizowane
    assert md.count("\n## ") == 2
    assert "ROZDZIAL_PROZA_1" in md and "ROZDZIAL_PROZA_2" in md


# ─── Backward / odporność ──────────────────────────────────────────────────────

def test_novelize_chapter_is_callable():
    """Klient Ollama istnieje jako funkcja (mockowalna w testach/pilocie)."""
    assert callable(bx.novelize_chapter)
