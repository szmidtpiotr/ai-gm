# AI-GM V2 — Quest / Objective System

> How player objectives are created, tracked, and displayed.
> GM declares quests via tags. LLM generates journal-style narrative. Displayed in the expanded journal panel.

---

## Decisions Made

| Question | Answer |
|----------|--------|
| Quest detail level | Quest log with LLM-generated narrative flavor per quest |
| Objective source | GM declares via `[QUEST_SET]` tag |
| UI location | Expanded journal panel — new "Misje" tab alongside existing "Historia" |
| Quest types | main (one at a time) + side (multiple) |
| LLM role | Writes 2-3 sentence journal-voice narrative when quest is set/resolved |

---

## Quest Tags (GM Emits)

The narrator LLM emits these tags when quest state changes. Tags are stripped from player-visible text before display.

### `[QUEST_SET:type:title:hint]`

Sets or updates a quest. If a quest with the same type+title already exists, updates the hint.

```
[QUEST_SET:main:Morderstwa w Graustein:Wotan wspomniał o ranach na szyi]
[QUEST_SET:side:Medalion dowódcy:Oddać rodzinie w Graustein]
```

- `type`: `main` or `side`
- `title`: short quest title (player sees this)
- `hint`: one-sentence hint for LLM narrative generation (player doesn't see this directly)

### `[QUEST_COMPLETE:title:resolution]`

Marks a quest as completed with a brief resolution note.

```
[QUEST_COMPLETE:Morderstwa w Graustein:Wampir zdemaskowany i pokonany]
[QUEST_COMPLETE:Medalion dowódcy:Medalion oddany rodzinie Klausa]
```

### `[QUEST_FAIL:title]`

Marks a quest as failed (optional — not all quests can fail).

```
[QUEST_FAIL:Ochrona świadka:Świadek nie żyje]
```

---

## DB Schema

```sql
CREATE TABLE IF NOT EXISTS character_quests (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    character_id    INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    campaign_id     INTEGER NOT NULL REFERENCES campaigns(id),
    quest_type      TEXT NOT NULL DEFAULT 'main'
        CHECK(quest_type IN ('main','side')),
    title           TEXT NOT NULL,
    narrative       TEXT NOT NULL DEFAULT '',
    -- LLM-generated 2-3 sentence journal-voice description
    status          TEXT NOT NULL DEFAULT 'active'
        CHECK(status IN ('active','completed','failed')),
    resolution      TEXT DEFAULT NULL,
    -- Brief note on how it ended (from QUEST_COMPLETE tag)
    resolution_narrative TEXT DEFAULT NULL,
    -- LLM-generated narrative for the completion/failure
    created_turn    INTEGER,
    completed_turn  INTEGER DEFAULT NULL,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_character_quests_active
    ON character_quests (character_id, status, campaign_id);
```

---

## Tag Processing Flow

When `[QUEST_SET:main:Morderstwa w Graustein:Wotan wspomniał o ranach na szyi]` is detected:

```python
def process_quest_set(character_id, campaign_id, turn_number, quest_type, title, hint):
    # 1. Check if quest already exists (update vs create)
    existing = db.get_quest(character_id, campaign_id, title)
    
    # 2. Generate LLM narrative (separate short call)
    narrative = generate_quest_narrative(
        character_name=character.name,
        quest_title=title,
        quest_type=quest_type,
        hint=hint,
        campaign_context=campaign_act_summary
    )
    # Returns: "Wotan wyglądał na przestraszonego gdy prosił o pomoc.
    #           Ciała ofiar mają dziwne rany na szyi — jakby ktoś wysysał krew.
    #           Nie ma żadnych dowodów, kto za tym stoi."

    if existing and existing.status == 'active':
        # Update existing quest narrative
        db.update_quest_narrative(existing.id, narrative)
    else:
        # Create new quest
        db.insert("character_quests", {
            "character_id": character_id,
            "campaign_id": campaign_id,
            "quest_type": quest_type,
            "title": title,
            "narrative": narrative,
            "status": "active",
            "created_turn": turn_number
        })
    
    # 3. XP: no XP for quest SET — only on COMPLETE
```

When `[QUEST_COMPLETE:title:resolution]` is detected:

```python
def process_quest_complete(character_id, campaign_id, turn_number, title, resolution):
    quest = db.get_active_quest(character_id, campaign_id, title)
    
    # Generate completion narrative
    resolution_narrative = generate_quest_resolution_narrative(
        character_name=character.name,
        quest_title=title,
        resolution=resolution
    )
    # Returns: "Wampir okazał się być starym kapłanem.
    #           Miasteczko jest bezpieczne, choć prawda jest gorsza niż się spodziewałeś."

    db.complete_quest(quest.id, turn_number, resolution, resolution_narrative)
    
    # Grant XP (via XP system)
    xp_type = "campaign_ending" if quest.quest_type == "main" else "side_quest"
    grant_xp(character_id, campaign_id, turn_number, xp_type, detail=title)
```

---

## LLM Narrative Generation

Two types of narrative calls — short, focused, separate from the main narrator:

### Quest Set Narrative

```
Prompt:
  Jesteś narratorem mrocznej fantasy.
  Napisz 2-3 zdania PIERWSZOOSOBOWĄ notatką w dzienniku bohatera.
  
  Bohater: {character_name}
  Nowe zlecenie: "{quest_title}"
  Kontekst: {hint}
  Ton kampanii: grim dark, mroczny, niebezpieczny świat
  
  Notatka powinna brzmieć jak myśli bohatera — co widział, co go niepokoi, co musi zrobić.
  NIE streszczaj zlecenia — opisz odczucia i obserwacje.

Example output:
  "Wotan wyglądał na przestraszonego gdy prosił o pomoc — za dużo wiedział.
   Ciała ofiar mają rany na szyi, jakby ktoś wysysał krew na sucho.
   Ktoś w tym mieście chowa tajemnicę, i nie jest gotów się nią dzielić."
```

### Quest Complete Narrative

```
Prompt:
  Bohater: {character_name}
  Zlecenie: "{quest_title}" — UKOŃCZONE
  Zakończenie: {resolution}
  
  Napisz 1-2 zdania w dzienniku — refleksja bohatera po zakończeniu zlecenia.
  Ton: zmęczenie, satysfakcja lub gorycz zależnie od rozwiązania.

Example output:
  "Koniec. Nie taki jakiego się spodziewałem, ale miasto jest bezpieczne.
   Smak zwycięstwa ma dziwną goryczę."
```

---

## UI — Expanded Journal Panel

The existing `journal-panel` in the frontend gets two tabs:

```
┌─────────────────────────────────────────┐
│  📖 Dziennik Aldrica                    │
├──────────────────┬──────────────────────┤
│  [Misje] [Historia]                     │
├─────────────────────────────────────────┤

  TAB: Misje
  ──────────────────────────────────────
  ⭐ AKTYWNE MISJE

  📜 Morderstwa w Graustein  [główne]
  "Wotan wyglądał na przestraszonego gdy
   prosił o pomoc — za dużo wiedział.
   Ciała ofiar mają rany na szyi..."
  
  📜 Medalion dowódcy  [poboczne]
  "Ten medalion ciąży mi od tygodni.
   Klaus miał rodzinę w Graustein —
   powinienem był oddać go dawno temu."

  ──────────────────────────────────────
  ✅ UKOŃCZONE  [rozwiń ▸]
  
    ✓ Spotkanie z Wotanem
      "Koniec. Nie taki jakiego oczekiwałem..."

  TAB: Historia
  ──────────────────────────────────────
  [existing AI session summaries]
```

**Misje tab details:**
- Active main quest shown first with full narrative
- Active side quests below
- Completed quests collapsed in an accordion at bottom
- Resolution narrative shown when completed quest is expanded

**Quest badge in chat header (optional):**
A small persistent indicator above the chat input showing the current main quest title. Tapping opens the journal panel. Shows when there's an active main quest.

```
[Game header]
  Aldric | Poziom 1 | 📍 Graustein
  📜 Morderstwa w Graustein                 ← tappable badge
```

---

## Narrator Prompt Integration

When the narrator is called, it receives active quests as context to maintain coherence:

```
=== AKTYWNE MISJE ===
Główne: Morderstwa w Graustein
Poboczne: Medalion dowódcy
=====================
```

This ensures the narrator doesn't contradict active objectives in narration.

---

## API Endpoints

```
GET  /api/campaigns/{id}/quests
     → Active + completed quests for this campaign

POST /api/campaigns/{id}/quests        (internal — called by tag processor)
PATCH /api/campaigns/{id}/quests/{id}  (internal)

GET  /api/characters/{id}/quests       → All quests across all campaigns
```

---

## Test Checklist

- [ ] GM narrates quest offer → [QUEST_SET] tag detected → quest record created
- [ ] LLM narrative generated in character's journal voice (Polish, first-person tone)
- [ ] Quest appears in Misje tab with title + narrative
- [ ] Multiple side quests can be active simultaneously
- [ ] [QUEST_COMPLETE] tag → quest marked complete → resolution narrative generated → XP granted
- [ ] Completed quests collapse into accordion, expandable with resolution
- [ ] Quest badge in chat header shows main quest title
- [ ] Narrator receives active quest list in context
- [ ] Quest set/complete tags stripped from player-visible text
- [ ] Quest persists if player logs off mid-session (DB-backed)

---

## Related Tasks
- Task 13 (Campaign Plan V2) — beats completion doesn't automatically set quests; GM tags do
- Task 25V2 (XP) — quest completion grants XP via standard grant_xp() call
- Task 36 (Memory/History) — Historia tab in same panel, unchanged
- Task 45 (Hero Journal) — completed campaign quests summarised in chapter summaries
