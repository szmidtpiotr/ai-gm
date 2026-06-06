"""TDD: Issue #364 — C10 QUEST_SUGGEST tag parsing and active_quests update."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.services.quest_suggest_parser import parse_quest_suggest, strip_quest_suggest_tags

# ─── Test główny: parsowanie poprawnego tagu ──────────────────────────────────

def test_parse_single_quest():
    """Poprawny tag [QUEST_SUGGEST: title | objective | reward] zwraca jeden quest."""
    text = "Stary wiedźmin mruczy pod nosem.\n[QUEST_SUGGEST: Znaleźć artefakt | Przeszukaj kryptę pod zamkiem | 100 złota]"
    quests = parse_quest_suggest(text)
    assert len(quests) == 1
    q = quests[0]
    assert q["title"] == "Znaleźć artefakt"
    assert q["objective"] == "Przeszukaj kryptę pod zamkiem"
    assert q["reward"] == "100 złota"
    assert q["status"] == "active"


def test_parse_multiple_quests():
    """Wiele tagów w jednej odpowiedzi LLM → lista questów."""
    text = (
        "[QUEST_SUGGEST: Quest A | Cel A | Nagroda A]\n"
        "Jakiś tekst narracyjny.\n"
        "[QUEST_SUGGEST: Quest B | Cel B | Nagroda B]"
    )
    quests = parse_quest_suggest(text)
    assert len(quests) == 2
    assert quests[0]["title"] == "Quest A"
    assert quests[1]["title"] == "Quest B"


def test_parse_quest_case_insensitive():
    """Tag działa w dowolnej wielkości liter."""
    text = "[quest_suggest: Tytuł | Cel | Nagroda]"
    quests = parse_quest_suggest(text)
    assert len(quests) == 1


def test_parse_quest_whitespace_trimmed():
    """Spacje wokół pól są przycinane."""
    text = "[QUEST_SUGGEST:  Tytuł z spacją  |  Cel  |  100 sz  ]"
    quests = parse_quest_suggest(text)
    assert len(quests) == 1
    assert quests[0]["title"] == "Tytuł z spacją"
    assert quests[0]["reward"] == "100 sz"


# ─── Test walidacji: błędny format ignorowany ────────────────────────────────

def test_ignore_malformed_one_field():
    """Tag z jednym polem (brak pipe) → ignorowany, nie crashuje."""
    text = "[QUEST_SUGGEST: tylko_tytuł]"
    quests = parse_quest_suggest(text)
    assert quests == []


def test_ignore_malformed_two_fields():
    """Tag z dwoma polami (brak reward) → ignorowany."""
    text = "[QUEST_SUGGEST: tytuł | cel]"
    quests = parse_quest_suggest(text)
    assert quests == []


def test_ignore_empty_title():
    """Pusty tytuł → ignorowany."""
    text = "[QUEST_SUGGEST:  | cel | nagroda]"
    quests = parse_quest_suggest(text)
    assert quests == []


def test_empty_text_returns_empty():
    """Pusty tekst → [], bez wyjątku."""
    assert parse_quest_suggest("") == []
    assert parse_quest_suggest(None) == []


# ─── Test strip: tag usuwany z narracji ──────────────────────────────────────

def test_strip_removes_tag():
    """Tag [QUEST_SUGGEST:...] znika z tekstu zwróconego graczowi."""
    text = "Wiedźmin kiwa głową.\n[QUEST_SUGGEST: Szukaj miecza | Idź do kuźni | Sława]\nMożesz odejść."
    clean = strip_quest_suggest_tags(text)
    assert "[QUEST_SUGGEST" not in clean
    assert "Wiedźmin kiwa głową." in clean
    assert "Możesz odejść." in clean


def test_strip_empty_is_safe():
    assert strip_quest_suggest_tags("") == ""
    assert strip_quest_suggest_tags(None) == ""


# ─── Backward compat: tekst bez tagu przechodzi bez zmian ────────────────────

def test_no_tag_text_unchanged():
    """Tekst bez tagu wraca niezmieniony z parse i strip."""
    text = "Zwykła narracja bez żadnych tagów questów."
    assert parse_quest_suggest(text) == []
    assert strip_quest_suggest_tags(text) == text
