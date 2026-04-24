import pytest

PROMPT_PATH = "backend/prompts/system_prompt.txt"


def _load_prompt() -> str:
    with open(PROMPT_PATH, encoding="utf-8") as f:
        return f.read()


def test_no_duplicate_combat_section():
    """Tylko jedna sekcja INICJOWANIE WALKI może istnieć w pliku."""
    content = _load_prompt()
    count = content.count("INICJOWANIE WALKI")
    assert count == 1, (
        f"Duplikat sekcji walki! Znaleziono {count} wystąpień 'INICJOWANIE WALKI' "
        f"w {PROMPT_PATH}. Usuń starą sekcję i zostaw tylko tę z PRZYPADKIEM 2."
    )


def test_combat_start_tag_documented():
    """Prompt musi zawierać instrukcję tagu [COMBAT_START]."""
    content = _load_prompt()
    assert "[COMBAT_START" in content, (
        f"Brak instrukcji [COMBAT_START] w {PROMPT_PATH}."
    )


def test_case2_player_initiated_attack_present():
    """Prompt musi zawierać PRZYPADEK 2 — gracz sam inicjuje atak."""
    content = _load_prompt()
    assert "PRZYPADEK 2" in content, (
        f"Brak sekcji 'PRZYPADEK 2' w {PROMPT_PATH}. "
        "Ta sekcja jest wymagana do poprawnego inicjowania walki przez gracza."
    )


def test_no_roll_initiative_as_combat_trigger():
    """
    'Roll Initiative d20' może pojawić się w liście FORMAT CUE oraz
    w sekcjach INICJOWANIE WALKI / PRZYPADEK 2 / HIERARCHIA jako
    legalny fallback gdy brak tagu [COMBAT_START] (Phase 8A).
    W bieżącym `system_prompt.txt` jest 8 literalnych wystąpień (lista cue +
    powtórne odniesienia w KLASYFIKACJI / ostrzeżeniach). Próg <= 8 łapie
    sensowny zakres Phase 8A; >8 oznacza najpewniej zduplikowaną sekcję walki.
    """
    content = _load_prompt()
    count = content.count("Roll Initiative d20")
    assert count <= 8, (
        f"Zbyt wiele wystąpień 'Roll Initiative d20' ({count}) w {PROMPT_PATH}. "
        "Prawdopodobnie sekcja walki jest zduplikowana — usuń duplikat."
    )


def test_no_roll_attack_as_combat_trigger():
    """
    Analogicznie: 'Roll Attack d20' nie może być triggerem walki.
    Dozwolone maksymalnie 2 wystąpienia (lista rzutów + przykład BŁĘDNY).
    """
    content = _load_prompt()
    count = content.count("Roll Attack d20")
    assert count <= 2, (
        f"Zbyt wiele wystąpień 'Roll Attack d20' ({count}) w {PROMPT_PATH}. "
        "Sprawdź czy stara sekcja walki nie używa go zamiast [COMBAT_START]."
    )
