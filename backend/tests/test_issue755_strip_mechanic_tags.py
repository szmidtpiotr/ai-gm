"""TDD: Issue #755 — Frontend nie wycina tagów mechanicznych ze strumienia narracji.

Backend dostaje funkcję strip_all_mechanic_tags() w llm_tag_parser.py,
która jest wzorcem dla JS stripMechanicTags() w app.js.
Oba używają tego samego generycznego regexu: [A-Z][A-Z0-9_]+:...
"""
import sys, os
sys.path.insert(0, '/app')

import pytest
import re


# ─── Test główny ──────────────────────────────────────────────────────────────

def test_strip_all_mechanic_tags_function_exists():
    """strip_all_mechanic_tags() musi istnieć w llm_tag_parser."""
    from app.services.llm_tag_parser import strip_all_mechanic_tags  # noqa — will fail until added
    assert callable(strip_all_mechanic_tags)


def test_strip_quest_suggest_from_narrative():
    """QUEST_SUGGEST wycięty — gracz nie widzi wewnętrznych instrukcji questu."""
    from app.services.llm_tag_parser import strip_all_mechanic_tags
    raw = 'Oberżysta mówi że coś jest do zrobienia. [QUEST_SUGGEST: Nocna przesyłka | Zanieś pergamin | 10 GP] Wychodzisz.'
    result = strip_all_mechanic_tags(raw)
    assert '[QUEST_SUGGEST' not in result
    assert 'Oberżysta mówi że coś jest do zrobienia.' in result
    assert 'Wychodzisz.' in result


def test_strip_npc_memory_from_narrative():
    """NPC_MEMORY wycięty — tag pamięci NPC nie pojawia się w bąblu gracza."""
    from app.services.llm_tag_parser import strip_all_mechanic_tags
    raw = 'Marta kiwa głową. [NPC_MEMORY: Marta Karczmarka | trzyma zapłatę do powrotu] Idzie za ladę.'
    result = strip_all_mechanic_tags(raw)
    assert '[NPC_MEMORY' not in result
    assert 'Marta kiwa głową.' in result
    assert 'Idzie za ladę.' in result


def test_strip_narrative_event_from_narrative():
    """NARRATIVE_EVENT wycięty — zdarzenie narracyjne nie migota w tekście."""
    from app.services.llm_tag_parser import strip_all_mechanic_tags
    raw = 'Wymieniasz medalion. [NARRATIVE_EVENT: key=token_exchanged_at_chapel, note=wymiana] Droga wolna.'
    result = strip_all_mechanic_tags(raw)
    assert '[NARRATIVE_EVENT' not in result
    assert 'Wymieniasz medalion.' in result


def test_strip_multiple_tags_in_one_text():
    """Wiele tagów mechanicznych usuniętych w jednym przebiegu."""
    from app.services.llm_tag_parser import strip_all_mechanic_tags
    raw = '[NPC_MEMORY: x | y] Tekst pomiędzy. [QUEST_SUGGEST: z | w | 5 GP] Koniec.'
    result = strip_all_mechanic_tags(raw)
    assert '[NPC_MEMORY' not in result
    assert '[QUEST_SUGGEST' not in result
    assert 'Tekst pomiędzy.' in result
    assert 'Koniec.' in result


def test_strip_location_blocked_and_apply_condition():
    """LOCATION_BLOCKED i APPLY_CONDITION — dotąd ręcznie, teraz generycznie."""
    from app.services.llm_tag_parser import strip_all_mechanic_tags
    raw = 'Idziesz. [LOCATION_BLOCKED: wymaga klucza] Drzwi. [APPLY_CONDITION: poisoned | 3] Ranny.'
    result = strip_all_mechanic_tags(raw)
    assert '[LOCATION_BLOCKED' not in result
    assert '[APPLY_CONDITION' not in result
    assert 'Idziesz.' in result
    assert 'Ranny.' in result


def test_strip_grant_and_create_tags():
    """GRANT_ITEM, GRANT_XP, CREATE_QUEST — usuwa całe rodziny tagów GRANT_*/CREATE_*."""
    from app.services.llm_tag_parser import strip_all_mechanic_tags
    raw = 'Dostajesz nagrodę. [GRANT_ITEM: zloty_pierscien | 1] [GRANT_XP: 50] Brawo.'
    result = strip_all_mechanic_tags(raw)
    assert '[GRANT_ITEM' not in result
    assert '[GRANT_XP' not in result
    assert 'Dostajesz nagrodę.' in result
    assert 'Brawo.' in result


# ─── Backward compatibility ───────────────────────────────────────────────────

def test_normal_narrative_text_unchanged():
    """Zwykły tekst narracyjny bez tagów — bez zmian."""
    from app.services.llm_tag_parser import strip_all_mechanic_tags
    text = 'Bohater idzie przez las. Słońce zachodzi za górami.'
    result = strip_all_mechanic_tags(text)
    assert result == text


def test_lowercase_brackets_not_stripped():
    """Nawiasy kwadratowe z małymi literami (normalny tekst) — zachowane."""
    from app.services.llm_tag_parser import strip_all_mechanic_tags
    raw = 'Grasz [dobrego złodzieja] i idzie ci nieźle.'
    result = strip_all_mechanic_tags(raw)
    assert '[dobrego złodzieja]' in result


def test_tag_without_colon_not_stripped():
    """[ALLCAPS] bez dwukropka (np. [OK]) — zachowany, nie jest tagiem mechanicznym."""
    from app.services.llm_tag_parser import strip_all_mechanic_tags
    raw = 'Status: [OK] wszystko działa.'
    result = strip_all_mechanic_tags(raw)
    assert '[OK]' in result


def test_empty_and_none_input():
    """None i pusty string — bezpieczna obsługa."""
    from app.services.llm_tag_parser import strip_all_mechanic_tags
    assert strip_all_mechanic_tags('') == ''
    assert strip_all_mechanic_tags(None) == ''
