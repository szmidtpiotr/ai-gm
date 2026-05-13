# TASK 45 — Hero Journal

**Phase:** 10 — Polish
**Status:** Not Started
**Depends on:** TASK 42 (Persistent Hero System)

---

## Overview

The Hero Journal is the cross-campaign chronicle of a persistent hero. Where the original V1 history tracked only the current campaign's turns, the Journal spans the entire hero's life — every campaign completed, every dungeon run, every rest period. It replaces per-campaign history with a coherent narrative record: chapters authored partly by the system, partly by the LLM, and searchable across the hero's full lifetime.

---

## Structure

The Journal is organised as a chapter list, where each chapter corresponds to one campaign. Dungeon runs and rest periods appear as brief interludes between chapters, not as standalone chapters.

```
📖 Kroniki Aldrica
├── Rozdział 1: "Zdrada pod Graustein"      [UKOŃCZONE]
│    AI summary: 2 paragraphs (player perspective)
│    XP earned: 340  ·  Gold brought forward: 85  ·  Level at end: 3
│    Outcome: Victory
│
├── Przerwa: Rest + Dungeon "Goblin Warren"  [PRZERWA]
│    Brief entry: "Aldric rested in Graustein, then cleared the Warren."
│
├── Rozdział 2: "Dungeon Cieni"              [AKTYWNE]
│    Running summary (updated every 10 turns, or on demand)
│    XP so far: 180  ·  Current level: 4
│
└── Rozdział 3: [Nie rozpoczęto]
```

### Chapter Title

Pulled from `campaigns.title` (set at campaign creation by LLM). If the title is blank, fallback: *"Rozdział N"* where N is the chapter number.

### Chapter Outcome

Pulled from `character_campaign_history.outcome` (victory / death / abandoned).

---

## Chapter Summary Generation

### Trigger

Chapter summary generation is triggered when a campaign ends — any outcome (victory, death, abandoned). It runs asynchronously after the campaign end sequence completes. The player sees a loading indicator in the Journal: *"GM pisze kronikę..."*

### LLM Inputs

The narrator receives:

- Last 50 turns from `campaign_turns` (turn text and narration text)
- `scene_log` from the campaign plan (list of beats visited)
- `campaign_plan.deviations` (list of player choices that diverged from the planned arc)
- `character_campaign_history.outcome` for this campaign
- Hero name, archetype, level at campaign end
- `sheet_json.bonds` and `sheet_json.weaknesses` (current values)

### LLM Output

Two paragraphs, in Polish, written from the hero's perspective (first person implied, not explicit):

- **Paragraph 1:** What happened — the key events, the main conflict, who was encountered.
- **Paragraph 2:** What it meant — the cost, the gain, the thing the hero carries forward. References at least one bond or weakness if relevant.

Tone: WFRP dark fantasy register. Terse, not triumphant. Even victories have weight.

Stored in `character_campaign_history.chapter_summary`. Max length: 800 characters.

### Regeneration

The player can regenerate the chapter summary at any time from the Journal UI. Regeneration uses the same inputs. Rate limit: once per 30 minutes per chapter. A [Przepisz] button appears on completed chapters.

---

## Running Summary (Active Campaign)

For the currently active campaign, the Journal shows a running summary instead of a completed chapter entry.

### Auto-Update

Every 10 turns, the backend triggers a running summary regeneration in the background. The running summary uses:
- Last 20 turns (not 50 — shorter context for speed)
- Current plan beat

Stored in `game_sessions.session_flags.running_summary` (not persisted to `character_campaign_history` until campaign ends).

### On-Demand Update

A "Historia" button in the game UI (left panel, below character name) triggers immediate running summary regeneration. Cooldown: 20 turns between on-demand requests. During the 20-turn window, the button is greyed with a counter: *"Historia dostępna za 8 rund"*.

On-demand request: `POST /api/campaigns/{id}/summary/refresh`.

### Two Views

The running summary has two versions:

- **Player view** (default): Narrative — what happened, written like the completed chapter summaries but in present tense.
- **GM view** (accessible via a small [GM] toggle in the Journal, admin users only): Structural — lists beats visited, current beat, deviations so far, NPC involvement.

The GM view is not visible to regular players.

---

## /mem Command — Cross-Campaign Search

The `/mem` command (already defined in TASK 36 Memory/History) is extended to search across all campaigns for the current hero, not just the active session.

### Command

```
/mem Co powiedział Bremer?
/mem goblin warren
/mem pierwszy akt
```

### Search Scope

V1 `/mem`: searched only the current campaign's `campaign_turns` table.
V2 `/mem` extension: searches across ALL `campaign_turns` records for ALL campaigns belonging to this hero.

Query: `SELECT * FROM campaign_turns WHERE campaign_id IN (SELECT id FROM campaigns WHERE character_id = ?) AND (turn_text ILIKE ? OR narration ILIKE ?)` with vector/FTS extension if available, fallback to LIKE.

### Response Format

Returns top 3 matching turns, each annotated with context:

```
[Rozdział 1 · Tura 14 · Graustein]
"Bremer mówi: Nie znam tego człowieka i żałuję, że kiedykolwiek..."
```

If a turn matches from a completed campaign, the chapter title is shown. If from the active campaign, just the turn number.

### Fallback

If `/mem` returns 0 results across all campaigns: *"Nie pamiętam niczego o tym w całej historii Aldrica."*

---

## GM Continuity Injection

### Problem

After a gap of 30+ minutes between sessions, the LLM starts fresh without remembering the narrative context. This causes the GM to "forget" that the hero has met a character before, or that an earlier campaign event is relevant.

### Solution

At session start (first turn after a gap of ≥30 minutes since the last turn in this campaign), the narrator context automatically includes:

1. **Previous chapter summary** — if the active campaign is not Chapter 1, inject the most recent completed `chapter_summary` as a prefix block labeled `[POPRZEDNIA KRONIKA]`.
2. **Current campaign events** — inject the last 5 turns as `[OSTATNIE ZDARZENIA]`.
3. **Active campaign running summary** — if available, inject as `[AKTUALNY STAN HISTORII]`.

The injected context is transparent to the player — no UI indication. It silently enriches the narrator's memory.

Condition check: `last_turn_at` on the session vs. `now()`. If gap ≥ 30 minutes: inject. If same session (gap < 30 min): skip injection (narrator already has full context via normal turn history).

---

## Journal UI

Accessible from the character sheet via "📖 Kroniki" button (right panel header area).

### Layout

Full-panel view (replaces character sheet content while Journal is open, with a back button to return to character sheet):

```
┌── 📖 Kroniki Aldrica ──────────────────────────────────[✕]┐
│                                                             │
│  Rozdział 1: "Zdrada pod Graustein"          [UKOŃCZONE]   │
│  ─────────────────────────────────────────────────────────  │
│  Aldric przybył do Graustein jako najemnik bez przeszłości. │
│  Klątwa na targowisku zmieniła wszystko...                  │
│                                                             │
│  XP: 340  ·  Gold: 85  ·  Poz. 3  ·  Wynik: Zwycięstwo    │
│                                  [Przepisz] [Rozwiń] [Ukryj]│
│                                                             │
│  Rozdział 2: "Dungeon Cieni"                 [AKTYWNE]     │
│  ─────────────────────────────────────────────────────────  │
│  [Historia bieżącej kampanii ładuje się...]                 │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### XP Timeline

Below the chapter list: a simple horizontal bar showing cumulative XP across all chapters, with level markers. Implemented as a `<canvas>` or SVG bar — not a third-party chart library.

### Visited Locations Map

A miniature world map (read-only Cytoscape.js, same fog-of-war logic as TASK 43) showing every location in `character.visited_location_keys` across ALL campaigns — not just the current one. This is the hero's complete cartographic memory.

---

## Test Checklist

1. **Chapter generated on campaign end:** Complete a campaign (any outcome) — verify `chapter_summary` populated in `character_campaign_history`, chapter appears in Journal UI within 30 seconds.
2. **`/mem` searches across campaigns:** Create two campaigns for same hero, place a named NPC mention in each — run `/mem [NPC name]` and verify both turns returned with correct chapter labels.
3. **GM continuity injection fires correctly:** Complete a turn, wait 31 minutes (mock `last_turn_at`), send a new turn — verify narrator context contains `[POPRZEDNIA KRONIKA]` block. Immediately follow-up turn (< 30 min) — verify block absent.
4. **Running summary auto-update:** Advance 10 turns — verify `session_flags.running_summary` updated. Advance 5 more turns, trigger on-demand — verify cooldown counter shown (5 turns remaining).
5. **Cross-campaign visited map:** Visit 3 locations across two different campaigns — open Journal → verify all 3 locations shown as visited on the miniature world map, even after starting the second campaign.
