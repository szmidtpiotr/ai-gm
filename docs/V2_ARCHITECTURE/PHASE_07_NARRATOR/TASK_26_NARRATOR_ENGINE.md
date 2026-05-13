# TASK 26 — Narrator Engine (Core Architecture)

**Status:** ✅ Done — `narrator_service.py`, 51 tests passing

## Overview

The LLM has exactly two jobs in this system: **Intent Parsing** and **Narration**. This task covers narration only. The narrator is a pure prose renderer — it receives structured mechanical facts and returns Polish prose. It does not decide what happens. It never invents facts.

## Narrator's Role

The system controls the world. The LLM narrates it.

| System responsibility | Narrator responsibility |
|---|---|
| Decide if attack hits | Describe the hit |
| Decide damage value | Describe the wound |
| Decide what NPC says | Voice the NPC |
| Decide if search succeeds | Describe finding or not finding |
| Decide campaign state | Describe the scene |

The narrator receives a structured **narration request** from the Context Injector and returns Polish prose. Nothing more.

---

## System Prompt (Exact Template)

```
Jesteś narratorem mrocznej fantasy. Opisujesz tylko to, co ci podano — nigdy nie wymyślasz faktów ze świata gry.

ZASADY:
- Pisz po polsku, 2-4 zdania (krótsze w walce, dłuższe w eksploracji)
- Opisuj wynik mechaniczny, który otrzymałeś — nie zmieniaj go
- Używaj tylko nazw postaci/miejsc/przedmiotów z bloku ŚWIAT
- Nie decyduj co się stanie — opisz co się stało
- Ton: mroczna fantasy, grim, bez wybranego-przez-los bohatera
```

This prompt is injected at the top of every narrator call. It is not modified at runtime. It is not player-visible.

---

## Input Format (from Context Injector)

Every narrator call receives a structured block:

```
MECHANIKA:
  akcja: ATTACK_HIT
  aktor: Gracz
  cel: Goblin Wartownik
  broń: Krótki Miecz
  obrażenia: 7
  HP_celu_po_ataku: 3
  stan: COMBAT

ŚWIAT:
  lokacja: Ciemny korytarz pod zamkiem Grunholt
  opis_lokacji: Wąski, wilgotny korytarz z kamienia. Pochodnie co kilka metrów — połowa zgasła.
  obecne_postacie: [Goblin Wartownik, Gracz]

POPRZEDNI_KONTEKST: (opcjonalnie)
  Gracz wszedł do korytarza z zachodu. Goblin krzyknął alarm.

ZADANIE: Opisz wynik ataku w 1-2 zdaniach.
```

The `ŚWIAT` block is the only source of proper nouns the narrator may use. Every NPC name, location name, and item name used in the prose must appear in this block.

---

## Narrator Constraints Enforcement

After the LLM returns prose, the system applies post-processing validation before delivering the text to the player.

### 1. Invented Mechanical Outcomes (strip)

Remove any damage numbers, dice roll results, or HP values the LLM generates that were not in the input.

```python
# Regex patterns to detect invented numbers in combat narration
DAMAGE_PATTERN = re.compile(r'\b\d+\s*(obrażeń|dmg|damage|hp|HP)\b', re.IGNORECASE)
DICE_PATTERN   = re.compile(r'\b(rzucam|wyrzuca|wynik)\s*\d+\b', re.IGNORECASE)
```

If invented numbers are found: strip the sentence containing them and log a warning. Do not pass invented mechanical outcomes to the player.

### 2. Invented Proper Nouns (strip/flag)

Extract all capitalized sequences from the narrator output. Cross-reference against the `ŚWIAT` block. If a name appears in the output but not in `ŚWIAT`, the sentence is stripped and a warning is logged.

Exception: generic dark-fantasy atmospheric words (e.g., "Bóg", "Śmierć", "Chaos" used as concepts) are allowed.

### 3. Length Enforcement

| Context | Max sentences |
|---|---|
| COMBAT action | 2 |
| EXPLORATION / MOVEMENT | 4 |
| DIALOGUE (NPC voice) | 4 |
| REST | 3 |
| SCENE description | 4 |

Enforcement: split by sentence boundary. Keep the first N sentences. Discard the rest silently.

---

## Two Types of Narrator Calls

### 1. Main Turn Narrator

Called once per player turn, after the World State Machine has resolved all outcomes.

- Receives full context: action taken, all mechanical outcomes, full location description, NPC state
- Returns a complete turn narration (2-4 sentences depending on action type)
- This is the primary narrative output delivered to the player

### 2. Combat Action Narrator

Called once per combat action within a round (one attack, one flee attempt, one item use).

- Receives minimal context: just the action, outcome, and relevant combatant info
- Returns 1-2 sentences, punchy and visceral
- Multiple calls in one round are assembled in order and displayed sequentially
- Detailed specification: see TASK_27_COMBAT_NARRATION.md

---

## Fallback Behavior

If the LLM call fails (timeout, error, malformed response), the system uses template-based narration:

```python
FALLBACK_TEMPLATES = {
    "ATTACK_HIT":   "Cios trafia w cel. Wróg cofa się z bólem.",
    "ATTACK_MISS":  "Atak chybia o włos. Wróg jest jeszcze na nogach.",
    "ATTACK_CRIT":  "Druzgocący cios. Wróg runął na ziemię.",
    "ATTACK_KILL":  "Wróg pada martwy.",
    "SEARCH_PASS":  "Twoje przeszukiwanie przynosi efekty.",
    "SEARCH_FAIL":  "Nie znajdujesz niczego wartego uwagi.",
    "MOVEMENT":     "Przemieszczasz się w wyznaczone miejsce.",
    "REST_SHORT":   "Odpoczywasz przez chwilę.",
    "REST_LONG":    "Noc mija powoli. Budzisz się zmęczony.",
    "SKILL_PASS":   "Twoje działanie przynosi efekt.",
    "SKILL_FAIL":   "Próba kończy się niepowodzeniem.",
    "FLEE_SUCCESS": "Udaje ci się uciec z walki.",
    "FLEE_FAIL":    "Ucieczka jest niemożliwa.",
}
```

Fallback does NOT use LLM. It is always available. Log fallback activations for monitoring.

---

## Context Injector Contract

The narrator depends on the Context Injector (see TASK_25, not yet written) to prepare the input block. The narrator itself never queries the database. It receives everything it needs in the structured input.

Injector responsibilities:
- Resolve location description from DB
- Resolve NPC names and states
- Format the `MECHANIKA` block from World State Machine output
- Inject `POPRZEDNI_KONTEKST` if relevant (last 1-2 turns, abridged)

---

## Testing Requirements

1. **No invented facts**: Feed narrator an input with known entities. Verify output contains no proper nouns outside the `ŚWIAT` block.
2. **Polish output**: All narrator responses must be in Polish. Add language detection assertion to test suite (simple heuristic: presence of Polish diacritics and absence of English keywords).
3. **Length constraints**: For each action type, verify the returned text does not exceed the sentence limit.
4. **Fallback activation**: Simulate LLM timeout. Verify fallback template is returned and no exception surfaces to the caller.
5. **Mechanical integrity**: Provide an input with `obrażenia: 7`. Verify narrator output does not mention any damage number not equal to 7 (or better: mentions no numbers at all, since numbers are for UI).
