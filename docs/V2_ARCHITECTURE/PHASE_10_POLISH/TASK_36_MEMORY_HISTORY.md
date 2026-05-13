# TASK 36 — Memory, History, and Campaign Continuity

**Status:** ❌ Not Started

## Overview

Players accumulate a lot of story. The `/mem` command lets them search their own campaign history. The "Historia" button generates a narrative summary. The GM uses session continuity context to stay consistent between sessions. The `/helpme` command provides hints without spoilers.

**Journal panel expansion:** The existing `journal-panel` in the frontend gains a **"Misje"** tab alongside the existing "Historia" tab. Misje shows active quests (with LLM-generated journal-voice narrative) and completed quests (collapsed). Full quest system spec in `15_QUEST_SYSTEM.md`. This task handles the Historia tab; TASK_15 (Quest System) handles the Misje tab. Both live in the same panel.

---

## `/mem` — Semantic Search Over Campaign History

### Player Usage

```
/mem <query>
/mem gdzie znalazłem klucz
/mem co powiedział Heinz
/mem kto zaatakował nas w lesie
```

Returns the 3 most relevant past turns as brief summaries.

### Implementation

Source table: `campaign_turns`. Each turn has: `turn_id`, `campaign_id`, `player_input`, `narrator_output`, `timestamp`, `game_state`, `location_id`.

Semantic search options (in order of preference):
1. Vector embeddings via SQLite vector extension (if available in deployment)
2. TF-IDF BM25 via SQLite FTS5 extension (lighter, always available)
3. Keyword substring fallback

For V2 launch: implement FTS5 full-text search over `player_input` + `narrator_output`. Build the FTS5 virtual table at DB init. Vector search is a Phase 12+ enhancement.

### Result Format

```
[Tura 14 — Karczma Pod Czarnym Krukiem]
Heinz szepnął ci do ucha, że skrzynka jest w piwnicy za wejściem od strony stajni.

[Tura 23 — Ciemny Zaułek]
Znalazłeś klucz ukryty pod kamieniem, tuż przy studni.

[Tura 31 — Piwnica]
Skrzynka była otwarta. Dokumenty zniknęły.
```

Each result: location name + turn number as label, then a 1-sentence summary of the turn.

Summary generation: truncate `narrator_output` to first sentence for display. No additional LLM call for `/mem` results.

### API Endpoint

```
GET /api/campaigns/{id}/memory/search?q={query}&limit=3
```

Response:
```json
{
    "results": [
        {
            "turn_id": 14,
            "location_name": "Karczma Pod Czarnym Krukiem",
            "summary": "Heinz szepnął ci do ucha...",
            "timestamp": "2026-04-15T21:33:00Z"
        }
    ]
}
```

---

## Historia — Campaign Narrative Summary

### Player-Visible Summary

Accessible via a "Historia" button in the UI (placed near the top of the narrative panel or in a campaign info modal).

```
POST /api/campaigns/{id}/history/summary/ensure
```

This endpoint:
1. Checks if a summary exists and is still valid (not past cooldown)
2. If valid: returns cached summary
3. If expired or missing: generates a new one

### Cooldown

Regeneration cooldown: **20 turns** since last generation. If player clicks "Historia" before 20 new turns have passed, return the cached summary with a note: "Ostatnia aktualizacja: {N} tur temu."

### Generation

Source: last 20 `campaign_turns` for this campaign.

LLM prompt:
```
Napisz po polsku krótkie streszczenie (3-5 zdań) wydarzeń z poniższych tur kampanii.
Pisz w drugiej osobie ("Przybyłeś do..."). Ton: mroczna fantasy, grim, obiektywny.
Zaznacz ważne odkrycia, decyzje i spotkania.

TURY:
{last_20_turns — player_input + narrator_output condensed, one line per turn}
```

### Dual Audience Summaries

Two versions are generated and stored:

| Version | Audience | Content |
|---|---|---|
| `player_summary` | Player-visible | "What happened to you" — narrative, second person, atmospheric |
| `gm_summary` | GM context only | Structural: beats completed, deviations from plan, current active plot threads, last known NPC states |

The `gm_summary` is never shown to the player. It is injected into the GM context at session start (see Session Continuity below).

The GM summary prompt:
```
Jesteś asystentem Mistrza Gry. Przeanalizuj poniższe tury kampanii i napisz po angielsku:
1. Beats completed (from campaign plan): list
2. Player deviations from plan: list
3. Active plot threads: list
4. Last known NPC states: list

TURY: {condensed turns}
PLAN KAMPANII: {campaign plan key beats}
```

---

## GM Continuity — Session Start Context

### Problem

Between sessions (player logs out and returns hours/days later), the GM has no memory of what happened. The narrator and World State Machine are stateless beyond the DB. Without context, narration becomes inconsistent.

### Solution

At session start (defined as: first turn after a gap of >30 minutes since last turn in this campaign), the system automatically injects a condensed summary into the GM context block.

The injected block:
```
KONTEKST SESJI (automatyczny):
Ostatnia sesja: {N} godzin temu
Ostatnie miejsce: {last_location_name}
Stan kampanii: {gm_summary — most recent, condensed to 100 words}
Aktywne wątki: {active_plot_threads}
Stany NPC: {last_npc_states}
```

This block is invisible to the player. It prepends the turn's context before the narrator and Intent Parser receive it.

The `gm_summary` used here is the most recently generated one (from the Historia endpoint). If no summary has ever been generated, a basic context block is constructed from the last 3 turns only.

---

## `/helpme` — Hint System

### Player Usage

```
/helpme
```

Returns a vague hint about what to do next. Does not spoil specific outcomes. Does not reveal keyword triggers or exact beat requirements.

### Implementation

1. Query campaign plan for next unvisited `key_beat`
2. If the beat has a `hint_text` field: return it directly (pre-written by campaign author)
3. If no `hint_text`: generate via LLM

LLM prompt for hint generation:
```
Gracz potrzebuje wskazówki. Następny cel kampanii to: "{beat_description}"
Napisz po polsku jedną wskazówkę (1-2 zdania) która:
- Sugeruje kierunek bez zdradzania wyniku
- Brzmi jak rada mentora, nie instrukcja
- Nie ujawnia konkretnych nazw przedmiotów ani NPC jeśli nie są jeszcze znani graczowi
Ton: mroczna fantasy, powściągliwy
```

Example output:
```
"Karczmarz wydaje się wiedzieć więcej, niż chce powiedzieć. Może warto nawiązać z nim rozmowę przy odpowiedniej okazji."
```

The hint system never says "Go to X and ask Y about Z." It implies direction.

### Cooldown

`/helpme` can be used once per turn (anti-spam). No other cooldown.

---

## Testing Requirements

1. **`/mem` returns results**: Index 20 turns. Search for a word that appears in turn 7. Verify turn 7 appears in results.
2. **`/mem` limit**: Verify response contains at most 3 results.
3. **Historia cooldown**: Generate a summary. Submit 5 turns. Request summary again. Verify cached summary returned with "N tur temu" note.
4. **Historia regeneration**: Submit 20 turns after last generation. Request summary. Verify new generation triggers.
5. **Dual summaries**: Verify `player_summary` and `gm_summary` are both stored after generation.
6. **Session continuity injection**: Simulate a 31-minute gap between last turn and new turn. Verify GM context block is injected in the new turn's processing.
7. **`/helpme` hint**: Verify hint references the campaign's next unvisited beat without naming specific items/NPCs not yet encountered.
8. **`/helpme` anti-spam**: Submit `/helpme` twice in one turn. Verify second request returns an error or the cached hint.
