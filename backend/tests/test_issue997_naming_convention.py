"""TDD: Issue #997 — Konwencja nazewnicza Kresów MIX słowiańsko-germański."""
import pytest
import pathlib

PROMPTS_DIR = pathlib.Path("/app/prompts")
SYSTEM_PROMPT = PROMPTS_DIR / "system_prompt.txt"
WORLD_BIBLE = PROMPTS_DIR / "world_bible.txt"

# ─── Test główny: reguła nazewnicza w prompcie systemowym ────────────────────

def test_system_prompt_contains_naming_rule():
    """system_prompt.txt musi mieć sekcję z regułą nazewniczą."""
    text = SYSTEM_PROMPT.read_text(encoding="utf-8")
    assert "Nazewnictwo" in text or "NAZEWNICTWO" in text, (
        "Brak sekcji nazewniczej w system_prompt.txt — #997"
    )

def test_system_prompt_naming_examples_present():
    """Prompt musi zawierać przykłady dobry/zły styl nazw."""
    text = SYSTEM_PROMPT.read_text(encoding="utf-8")
    # Musi być chociaż jeden wzorzec germański (hybrid lub czysty)
    has_germanic = any(s in text for s in ["-burg", "-stein", "-wacht", "Wilczburg", "Czarnstein", "Strzegwacht"])
    assert has_germanic, (
        "Prompt nie zawiera przykładów germańskich nazw (#997). "
        "Dodaj przykłady a/b/c w regule nazewniczej."
    )

def test_system_prompt_prohibits_polish_toponyms():
    """Prompt musi zakazywać realnych polskich toponimów."""
    text = SYSTEM_PROMPT.read_text(encoding="utf-8")
    # Musi być jawna reguła zakazu -owice/-anka/-ino
    has_prohibition = any(s in text for s in ["-owice", "-anka", "polskich", "toponi"])
    assert has_prohibition, (
        "Prompt nie zakazuje polskich toponimów (#997). "
        "Dodaj regułę 'unikaj -owice/-anka/-ino'."
    )

# ─── Test główny: reguła nazewnicza w world_bible ────────────────────────────

def test_world_bible_contains_naming_rule():
    """world_bible.txt musi mieć notatkę o konwencji nazewniczej."""
    text = WORLD_BIBLE.read_text(encoding="utf-8")
    has_rule = any(s in text for s in ["MIX", "nazewnicza", "germańsk", "-burg", "hybrid"])
    assert has_rule, (
        "world_bible.txt nie zawiera konwencji nazewniczej (#997)."
    )

def test_world_bible_no_cieszowice():
    """world_bible.txt nie może zawierać 'Cieszowice' — offender zastąpiony."""
    text = WORLD_BIBLE.read_text(encoding="utf-8")
    assert "Cieszowice" not in text, (
        "world_bible.txt nadal zawiera 'Cieszowice' — zmień na Cieszburg (#997)."
    )

def test_world_bible_no_wolanka():
    """world_bible.txt nie może zawierać 'Wolanka' — offender zastąpiony."""
    text = WORLD_BIBLE.read_text(encoding="utf-8")
    assert "Wolanka" not in text, (
        "world_bible.txt nadal zawiera 'Wolanka' — zmień na Wolfsmark (#997)."
    )

def test_world_bible_no_brzezino():
    """world_bible.txt nie może zawierać 'Brzezino' — offender zastąpiony."""
    text = WORLD_BIBLE.read_text(encoding="utf-8")
    assert "Brzezino" not in text, (
        "world_bible.txt nadal zawiera 'Brzezino' — zmień na Birkenwald (#997)."
    )

def test_world_bible_no_strazyn():
    """world_bible.txt nie może zawierać 'Strażyn' jako osadę — zastąpione Strzegwacht."""
    text = WORLD_BIBLE.read_text(encoding="utf-8")
    # Strażyn jako stara nazwa twierdzy → zmieniona na Strzegwacht
    assert "Strażyn" not in text, (
        "world_bible.txt nadal zawiera 'Strażyn' — zmień na Strzegwacht (#997)."
    )

# ─── Backward compatibility ──────────────────────────────────────────────────

def test_world_bible_canonical_names_preserved():
    """Kanonicze nazwy (w odmianach) muszą zostać w world_bible."""
    text = WORLD_BIBLE.read_text(encoding="utf-8")
    # Vilnograd → pojawia się jako Vilnogradu itp.
    assert "Vilnograd" in text, "Kanon: 'Vilnograd' usunięty z world_bible (#997)."
    # Czarnobór → pojawia się jako Czarnoborze (lokativus) w world_bible
    assert "Czarno" in text, "Kanon: odniesienie do Czarnoboru usunięte (#997)."

def test_system_prompt_location_create_still_works():
    """Sekcja action:create w prompcie nadal istnieje po zmianie."""
    text = SYSTEM_PROMPT.read_text(encoding="utf-8")
    assert "action: create" in text, "Usunięto sekcję action:create z promptu (#997 side-effect)."
    assert "target_label" in text, "Usunięto target_label z promptu (#997 side-effect)."
