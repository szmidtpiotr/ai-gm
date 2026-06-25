"""TDD: Issue #989 — dialogi NPC w polskiej konwencji (myslnik od nowej linii).

Bug: system_prompt.txt:21 kaze LLM stosowac cudzyslow dla wypowiedzi NPC
(regula "dialog w cudzyslowie"), wiec kwestie wyswietlaja sie wplecione inline.
Powinno byc po polsku - kazda kwestia od NOWEJ LINII, od myslnika U+2014, bez cudzyslowow:
    EM Nie wiem, jak sie nazywal EM mowi nisko.   (EM = myslnik)

Fix (glowne): przepisac regule :21 na polska konwencje dialogowa + przyklad.
Cudzyslowy zostaja TYLKO dla tresci pisanej (list, pergamin, inskrypcja).
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.system_prompt_loader import load_system_prompt_text

DASH = "—"  # myslnik / em-dash


# --- Test glowny - prompt kaze uzywac myslnika, nie cudzyslowu ----------------

def test_prompt_drops_quote_rule_for_npc_dialogue():
    """Stara regula 'dialog w cudzyslowie' MUSI zniknac - to ona psula format."""
    low = load_system_prompt_text().lower()
    assert "dialog w cudzysłowie" not in low, (
        "Regula 'dialog w cudzyslowie' wciaz w system_prompt.txt - LLM nadal "
        "bedzie wplatal kwestie NPC w cudzyslowach zamiast od myslnika."
    )


def test_prompt_instructs_dash_dialogue_from_new_line():
    """Prompt MUSI instruowac: kwestia NPC od nowej linii, zaczyna sie od myslnika."""
    prompt = load_system_prompt_text()
    low = prompt.lower()
    assert DASH in prompt, "Brak znaku myslnika (U+2014) w system_prompt.txt."
    assert "nowej linii" in low, "Prompt nie mowi, ze kwestia NPC ma byc od NOWEJ LINII."
    assert "myślnik" in low, "Prompt nie wspomina o mysliku jako znaku dialogu."


def test_prompt_has_dash_dialogue_example():
    """Prompt MUSI zawierac konkretny przyklad linii dialogu od mysliika."""
    prompt = load_system_prompt_text()
    has_example = any(
        line.lstrip().startswith(DASH + " ")
        for line in prompt.splitlines()
    )
    assert has_example, (
        "Brak przykladu '<dash> <kwestia>' w system_prompt.txt - LLM uczy sie "
        "formatu z przykladu; bez niego konwencja jest pusta."
    )


def test_prompt_keeps_quotes_for_written_text():
    """Cudzyslowy maja ZOSTAC dla tresci pisanej (list/pergamin)."""
    low = load_system_prompt_text().lower()
    assert ("list" in low or "pergamin" in low or "inskrypcj" in low), (
        "Prompt nie wskazuje wyjatku - cudzyslowy dla tresci pisanej (list/pergamin)."
    )


# --- Backward compatibility - reszta bloku FORMATU nietknieta -----------------

def test_format_block_structure_intact():
    """Blok 'FORMAT ODPOWIEDZI' i zasada osobnych akapitow musza zostac."""
    prompt = load_system_prompt_text()
    assert "## FORMAT ODPOWIEDZI" in prompt, "Usunieto naglowek bloku FORMAT ODPOWIEDZI."
    assert "oddzielny akapit" in prompt.lower(), (
        "Zasada 'oddzielny akapit' dla NPC zniknela."
    )
    assert "NIGDY nie łącz narracji" in prompt, (
        "Zasada zakazujaca laczenia narracji/dialogu/opisu w jeden blok zniknela."
    )
