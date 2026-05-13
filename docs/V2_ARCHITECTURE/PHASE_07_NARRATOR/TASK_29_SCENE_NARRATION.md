# TASK 29 — Scene Narration (Non-Combat, Non-Dialogue)

**Status:** ❌ Not Started

## Overview

Everything that isn't combat or NPC dialogue is a scene narration. This covers: exploration, movement between locations, skill test outcomes, rest, examination of objects, and ambient campaign events. Scene narrations are longer and more atmospheric than combat narrations — they are where the dark fantasy tone breathes.

---

## Scope

| action_type | Description |
|---|---|
| `SEARCH` | Player searches a location or container |
| `MOVEMENT` | Player moves from one location to another |
| `REST_SHORT` | Short rest (1 hour, recovers some HP, no scene change) |
| `REST_LONG` | Long rest (overnight, full recovery, high risk in dark fantasy) |
| `EXAMINE` | Player examines a specific object, body, inscription, etc. |
| `SKILL_TEST` | Generic skill check (Perception, Athletics, Stealth, etc.) |
| `CAMPAIGN_EVENT` | A scripted campaign beat triggers — narrate its arrival |

---

## Input Schema

```python
class SceneNarrationRequest:
    action_type:         str              # from action_type table above
    outcome:             str              # "success" / "fail" / "critical_success" / "critical_fail"
    location:            LocationContext
    time_of_day:         str | None       # "świt" / "południe" / "zmierzch" / "noc" — if tracked
    weather:             str | None       # "deszcz" / "mgła" / "bezchmurnie" / etc. — if tracked
    wound_label:         str | None       # player's current wound state, e.g. "Ranny", "Ciężko Ranny"
    campaign_act:        str | None       # e.g. "Akt 1: Zaginięcie Kupca"
    skill_used:          str | None       # for SKILL_TEST: which skill
    object_examined:     str | None       # for EXAMINE: name/description from DB
    found_items:         list[str]        # for SEARCH success: item names from DB
    destination:         LocationContext | None  # for MOVEMENT: where going
```

```python
class LocationContext:
    name:        str
    description: str   # full description from DB
    archetype:   str   # "tavern" / "dungeon" / "forest" / "city" / "ruin" / "road"
```

---

## LLM Prompt (Scene Narration)

```
Jesteś narratorem mrocznej fantasy. Opisz scenę po polsku, {sentence_limit} zdania.
Ton: grim dark, Warhammer Fantasy. Nigdy nie opisuj spokojnej, bezpiecznej idylli.
Używaj tylko nazw z bloków LOKACJA i ŚWIAT.
Nie wspominaj liczb mechanicznych.

AKCJA: {action_type}
WYNIK: {outcome}
PORA DNIA: {time_of_day or "nieznana"}
POGODA: {weather or "nieznana"}
STAN GRACZA: {wound_label or "Nieuszkodzony"}

LOKACJA:
  Nazwa: {location.name}
  Opis: {location.description}
  Typ: {location.archetype}

{if destination:}
DOCELOWA LOKACJA:
  Nazwa: {destination.name}
  Opis: {destination.description}
{/if}

{if found_items:}
ZNALEZIONE PRZEDMIOTY: {found_items — comma list}
{/if}

{if object_examined:}
BADANY OBIEKT: {object_examined}
{/if}

KONTEKST KAMPANII: {campaign_act or "—"}

PRZYPOMNIENIE: Nigdy nie opisuj spokojnego, doskonałego odpoczynku — zawsze pozostaje jakiś niepokój.

Opisz scenę.
```

---

## Length by Action Type

| action_type | Sentence limit |
|---|---|
| `SEARCH` | 3 |
| `MOVEMENT` | 3 |
| `REST_SHORT` | 2 |
| `REST_LONG` | 3 |
| `EXAMINE` | 2 |
| `SKILL_TEST` | 2 |
| `CAMPAIGN_EVENT` | 4 |

The sentence limit is injected into the prompt as `{sentence_limit}` and enforced by post-processor.

---

## SEARCH Narration

The **system decides what is found**. The narrator describes **how** it is found.

On `success`:
- `found_items` list will be populated by the World State Machine before the narrator is called
- Narrator describes the discovery: where the item was hidden, the player's physical act of finding it
- Example: if `found_items = ["Klucz do Piwnicy"]`, narrator describes hands closing around something cold, a key tucked under a loose flagstone

On `fail`:
- `found_items` is empty
- Two sub-outcomes: clean fail ("nothing here") or disturbed fail ("you find nothing but disturb something in the process")
- The World State Machine sets an `atmosphere_disturbed` flag when relevant — inject into prompt if true

```
{if atmosphere_disturbed:}
Przeszukując, gracz coś porusza/niepokoi. Opisz atmosferyczny niepokojący szczegół — nie bezpośrednie niebezpieczeństwo.
{/if}
```

---

## MOVEMENT Narration

Describes the transition from one location to another.

Rules:
- Reference leaving the source location (use its description from DB)
- Reference arriving at the destination (use its description from DB)
- Describe what the journey is like (brief — this is not the "arriving" scene, just the transition)
- If `time_of_day` and `weather` are tracked, use them to color the travel

Example: leaving a cramped tavern in rain to enter a dark alley — the narrator uses both location descriptions to create the transition.

For MOVEMENT within a location (room to room in a dungeon), the transition is still narrated but the "journey" element is omitted.

---

## REST Narration

### Short Rest

2 sentences. The character catches their breath. The world doesn't stop.

Dark fantasy note: a short rest in a dungeon feels different from a short rest in a locked room in a city inn. The location archetype shapes the narration. Inject:

```
{if location.archetype in ["dungeon", "ruin", "forest"]:}
Odpoczynek jest niespokojny — gracz jest w niebezpiecznym miejscu.
{elif location.archetype in ["tavern", "inn"]:}
Odpoczynek jest względnie bezpieczny, ale nawet tu nie ma prawdziwego spokoju.
{/if}
```

### Long Rest

3 sentences. More vivid. The night passes but the world's grim tone seeps in.

Standard elements to include at least one of:
- Distant howls, screams, or unidentifiable sounds
- Uneasy dreams (vague, atmospheric — not prophetic)
- The fire burning low, the cold creeping in
- Waking with a sense something has changed

The "no perfect peaceful rest" rule is always enforced — injected into every rest prompt. Even in the safest location, something is slightly wrong.

---

## EXAMINE Narration

2 sentences. Describes what the player perceives when examining the object. The object's description from DB is the source of truth.

If the object has a `hidden_detail` field in DB that has been unlocked by a successful Perception check, the `outcome=success` narration describes perceiving that detail. On `fail`, only the surface description is narrated.

---

## Time and Weather as Enrichment

When `time_of_day` and `weather` are tracked in the campaign (not all campaigns will track them), they enrich the narration. They are never mandatory — the prompt instructs the narrator to use them "if provided."

Examples:
- `noc` + `mgła` → "W tej gęstej, wilgotnej mgle..." 
- `świt` + `deszcz` → "Deszcz o świcie pada bez przerwy..."
- `południe` + `bezchmurnie` → Even a clear noon in dark fantasy has menace — the sun reveals too much

The narrator should never describe weather as pleasant unless it is plot-relevant and the system explicitly flags it.

---

## Dark Fantasy Tone Reminders (Context Injection)

Always injected into scene narration prompts:

```
STYL:
- Nigdy nie opisuj doskonałego, spokojnego odpoczynku — zawsze pozostaje jakiś niepokój
- Świat jest wrogi i obojętny — nie sprzyja graczowi
- Piękno jest zimne lub złowrogie
- Gracz nie jest wybrańcem losu — jest tylko człowiekiem w ciemnym miejscu
```

These are permanent fixtures in the scene narration system prompt. They are never removed.

---

## Testing Requirements

1. **SEARCH success**: Provide `found_items=["Stary Sztylet"]`. Verify narrator mentions "sztylet" (or the item name) in the output.
2. **SEARCH fail**: Provide empty `found_items`. Verify narrator does not mention any item being found.
3. **MOVEMENT**: Provide `location` + `destination`. Verify narrator references both location names.
4. **REST long**: Verify output includes at least one atmospheric unease element (keyword list: "wycie", "sny", "zimno", "cisza", "niepokój", "cień", "ogień").
5. **No perfect rest**: Feed a REST prompt with a safe location (tavern archetype). Verify output does not use pure positive language without any unease.
6. **Length**: Verify all action types respect their sentence limits.
7. **Time/weather enrichment**: Provide `time_of_day="noc"` and `weather="mgła"`. Verify output references night or fog.
8. **No numbers**: Verify no digit appears in scene narration output.
