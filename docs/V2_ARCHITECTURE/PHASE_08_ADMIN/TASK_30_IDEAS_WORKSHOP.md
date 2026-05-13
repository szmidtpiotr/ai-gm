# TASK 30 — Ideas Workshop (AI Agent for Admin)

**Status:** ❌ Not Started
**Phase:** 08 — Admin Tools
**Depends on:** Phase 01 DB Schema (campaign_ideas table), Phase 03 Data Tables

---

## Overview

The Ideas Workshop is a conversational AI agent embedded in the admin panel. Admin sends a rough idea in chat — the agent asks clarifying questions, proposes structure, and together they build a complete scenario seed, scene module, NPC concept, or location sketch. When finished, the agent converts the conversation into a structured JSON record that the game engine can directly use.

This is not a form. It's a creative collaboration tool.

---

## Design Context

### Why conversational, not a form?
Game masters think in stories, not schemas. "I want a campaign where the villain turns out to be the player's long-lost father" is a concept — it shouldn't require filling out 15 fields. The agent takes the concept and asks the right questions to build the structure. Admin stays creative; the system handles the formalization.

### Why does the game engine need structured output?
Campaign generation draws from the Ideas Bank. The LLM that generates campaigns needs structured seeds it can reliably use — not vague text blobs. A seed must have: premise, tone, antagonist type, setting hints, possible endings. The agent ensures every saved idea meets the game engine's expectations before it goes into the bank.

### What kinds of ideas can be created?

| Category | Description | Game engine use |
|----------|-------------|----------------|
| `seed` | Full campaign concept — premise, conflict, 2 endings | Campaign generation draws from seeds as inspiration |
| `scene_module` | A specific encounter/event that can drop into any campaign | GM can insert as a side quest, complication, or ambush |
| `npc_concept` | An NPC archetype with personality/secrets/goals | Campaign generation can instantiate as a specific NPC |
| `location` | A place with atmosphere, history, typical inhabitants | GM uses when player enters an unspecified area |
| `plot_twist` | A single surprising development | GM can deploy as a deviation recovery or complication |
| `encounter` | A specific combat encounter with setup and context | GM can trigger when tone/setting matches |

---

## The Workshop Flow

```
Admin opens Ideas Workshop panel
        ↓
Admin types rough idea:
"I have an idea about a plague spreading in a city — people 
 think it's natural but it's actually being spread deliberately
 by a cult worshipping a chaos god"
        ↓
Agent responds with clarifying questions:
"Interesting — a few questions to build this properly:
 1. Is this a full campaign seed, or a scene module (like 
    a mid-campaign complication)?
 2. What kind of player character fits this best — someone 
    connected to the city, or an outsider?
 3. How grim should this be? Can the cult be stopped, or 
    does the city fall regardless?"
        ↓
Admin answers (free text, conversational)
        ↓
Agent proposes structured draft:
"Based on what you described, here's a structured draft:
 Title: Plaga Bogów
 Category: seed
 Premise: A plague ravages a city — outwardly natural, 
  actually spread by a cult of [chaos deity]. 
 Hook: Player discovers a pattern in who gets sick...
 [full structured preview shown]
 Shall I save this, or would you like to change anything?"
        ↓
Admin: "Change the ending — I want the cult leader to be 
        someone the player met earlier in the campaign"
        ↓
Agent: updates structured draft, confirms
        ↓
Admin approves → agent saves to campaign_ideas table
```

---

## Agent Architecture

### Endpoint
`POST /api/admin/ideas/workshop` — sends admin message, returns agent response

### Session State
Workshop conversation stored in a workshop_session (in-memory or lightweight DB table). Includes:
- `conversation_history: list[{role, content}]`
- `current_draft: dict | None` — the in-progress structured idea
- `category: str | None` — what kind of idea is being built

### Agent System Prompt

```
Jesteś kreatywnym asystentem projektowania kampanii do mrocznego fantasy RPG.
Pomagasz administratorowi zbudować ustrukturyzowany pomysł do bazy danych gry.

TWOJE ZADANIE:
1. Zrozum pomysł admina (zadaj max 3-4 pytania, nie za dużo)
2. Zaproponuj ustrukturyzowany szkic w formacie JSON (patrz schemat)
3. Dostosuj szkic na podstawie feedbacku admina
4. Zapisz gdy admin zatwierdzi

TON: Kreatywny, entuzjastyczny, traktuj admina jak współautora.
ŚWIAT: Mroczna fantasy (WFRP-inspired) — grim, niebezpieczny, moralnie niejednoznaczny.

SCHEMAT do wypełnienia (zależy od kategorii):
[schema injected based on detected category]
```

### Category Detection
Agent infers category from the first message. Can ask to confirm if unclear:
- Mentions "campaign", "adventure", "story" → likely `seed`
- Mentions "encounter", "fight", "ambush" → likely `scene_module` or `encounter`
- Describes a person/character → likely `npc_concept`
- Describes a place → likely `location`
- "What if..." twist → likely `plot_twist`

---

## Structured Output Schemas

### seed
```json
{
  "category": "seed",
  "title": "Plaga Bogów",
  "premise": "Zaraza dziesiątkuje miasto — pozornie naturalna, w rzeczywistości rozsiewana przez kult.",
  "hook": "Gracz dostrzega wzorzec — tylko pobożni mieszkańcy chorują jako ostatni.",
  "setting_hints": ["duże miasto", "kult", "korupcja władzy"],
  "antagonist_type": "cult_leader",
  "tone": "paranoia, horror, urban",
  "act_suggestions": {
    "act1": "Gracz trafia do miasta, zaraza już trwa. Ludzie umierają.",
    "act2": "Odkrycie kultu. Kto jest zamieszany? Jak daleko sięga korupcja?",
    "act3": "Konfrontacja. Kultystów nie można pokonać siłą — trzeba ich zdemaskować."
  },
  "endings": [
    {"title": "Kult zniszczony", "type": "primary", "description": "Gracz ujawnia kult. Miasto przeżywa, ale nigdy nie będzie takie samo."},
    {"title": "Za późno", "type": "alternate", "description": "Kult zostaje pokonany, ale zaraza już się rozprzestrzeniła poza miasto."}
  ],
  "character_fit": "outsider lub ktoś z osobistym połączeniem z miastem",
  "suggested_enemies": ["cult_guard", "plague_zombie", "chaos_priest"],
  "suggested_npcs": ["corrupt_priest", "dying_witness", "plague_doctor"]
}
```

### scene_module
```json
{
  "category": "scene_module",
  "title": "Zasadzka na Skrzyżowaniu",
  "setup": "Bandyci kontrolują most na granicy dwóch terytoriów.",
  "trigger_condition": "player is traveling between locations",
  "location_key_suggestion": "road_crossroads",
  "enemies": [{"key": "bandit", "count": 3}],
  "twist_optional": "Jeden z bandytów to dezerter szukający ucieczki — można go przechytrzyć zamiast walczyć.",
  "tone": "tense, moral choice",
  "outcome_options": [
    "Walka: bandyci pokonani, gracz kontynuuje",
    "Negocjacje: gracz płaci myto lub przekonuje ich do odejścia",
    "Dezerter: gracz pomaga dezerterowi, bandyci się rozchodzą"
  ]
}
```

### npc_concept
```json
{
  "category": "npc_concept",
  "name_suggestion": "Stary Żebrak",
  "role": "świadek",
  "personality": "Paranoiczny, mówi zagadkami, ukrywa coś ważnego. Dawniej był kapłanem.",
  "secret": "Widział jak kult dokonał pierwszego morderstwa. Boi się, że go cisza nie ochroni.",
  "dialogue_hooks": [
    {"keyword": "kult", "reveal": "Widziałem ich twarze. Modlili się do czegoś starego."},
    {"keyword": "morderstwo", "reveal": "Nie pytaj mnie o to. Nie jeśli chcesz żyć."}
  ],
  "npc_type": "quest_giver",
  "appears_in": "urban, slums, tavern"
}
```

---

## Frontend: Ideas Workshop Panel

**Location:** Admin panel → new tab "Warsztat Pomysłów"

**Layout:**
```
┌─────────────────────────────────────────┐
│ 💡 Warsztat Pomysłów                    │
├─────────────────────────────────────────┤
│ [Chat area: admin ↔ agent]              │
│                                         │
│ Agent: Cześć! Opisz swój pomysł...      │
│ Admin: Chcę kampanię o plagach...       │
│ Agent: Kilka pytań...                   │
│                                         │
│ [Current Draft Preview] (right panel)  │
│  Category: seed                         │
│  Title: Plaga Bogów                     │
│  [full JSON preview — collapsible]      │
│                                         │
├─────────────────────────────────────────┤
│ [_________________________] [Wyślij]    │
│ [💾 Zapisz do Banku] (when draft ready) │
└─────────────────────────────────────────┘
```

When admin clicks "Zapisz do Banku" → `POST /api/admin/ideas` with structured_data → saved to `campaign_ideas` table. Workshop session cleared. Ready for new idea.

---

## Ideas Bank Browser

Separate panel: "Bank Pomysłów" — browse, filter, rate, tag, delete.

- Filter by category, rating, tags
- Quality rating: 0-5 stars (admin-assigned)
- Times used counter (incremented when a campaign generation draws from this seed)
- [Edit] opens Workshop chat with this idea loaded for revision
- [Delete] soft-delete (is_active=0)

---

## Integration with Campaign Generation

When generating a new campaign plan (Phase 02, TASK_07):
```python
relevant_seeds = db.execute("""
    SELECT * FROM campaign_ideas 
    WHERE category = 'seed' 
    AND quality_rating >= 3
    AND is_active = 1
    ORDER BY quality_rating DESC, times_used ASC
    LIMIT 3
""").fetchall()
```

These top 3 seeds are injected into the campaign generation prompt as inspiration:
```
Inspiracje z Banku Pomysłów (możesz z nich skorzystać):
1. [seed title]: [premise]
2. ...

Stwórz kampanię spersonalizowaną pod postać gracza, czerpiąc inspirację z powyższych jeśli pasują.
```

---

## Edge Cases

- **Admin sends very vague idea** ("I want something about a dungeon"): Agent asks 3 targeted questions before proposing structure
- **Admin rejects the draft multiple times**: After 3 rejections, agent offers to save as a rough note (unstructured) and refine later
- **Generated idea conflicts with existing world canon**: Agent cannot detect this — admin's responsibility to check consistency
- **Category ambiguity**: Agent proposes the most likely category and asks to confirm before building the full structure

---

## Test Checklist

- [ ] Admin sends idea → agent asks clarifying questions (max 3-4)
- [ ] Agent proposes structured draft matching the detected category's schema
- [ ] Admin edits draft via conversation → agent updates the draft
- [ ] Admin approves → idea saved to campaign_ideas table with correct fields
- [ ] Campaign generation query returns top-rated seeds
- [ ] Ideas Bank browser shows saved idea with correct category and rating
- [ ] [Edit] in Ideas Bank loads the idea into Workshop for revision
- [ ] Workshop session cleared after save (ready for new idea)

---

## Related Tasks
- Task 01 (DB Schema) — campaign_ideas table
- Task 07 (Campaign Plan Generation) — queries Ideas Bank as input
- Task 31 (Campaign Workshop) — different tool: edits live campaigns, not the Ideas Bank
