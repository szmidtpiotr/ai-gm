# TASK 04 — Context Injector

**Phase:** 01 — Foundation  
**Depends on:** TASK_01 (DB Schema — NPC personality_prompt, keyword_triggers; location safe_for_rest), TASK_02 (Intent Parser), TASK_03 (World State Machine — produces mechanic_result)  
**Blocks:** nothing (final step in V2 pipeline before narrator LLM call)  
**New file:** `backend/app/services/context_injector.py`  
**Modified file:** `backend/app/services/game_engine.py`

---

## Overview

The Context Injector assembles the complete prompt that the LLM narrator receives on every turn. It runs after the World State Machine and mechanic resolvers have done their work — so the narrator gets a fully resolved mechanical outcome and structured world facts, never raw player text or uncertain state.

The injector is the primary anti-hallucination mechanism in V2. If the narrator hallucinates, the fix is to add the missing information to the injector — not to prompt-engineer the narrator to "be more careful."

---

## Why This Exists

### The V1 Problem

In V1, the narrator LLM received:
- A long conversation history (tokens wasted on old turns)
- The raw player message (LLM had to infer intent)
- Minimal world context (LLM filled gaps by invention)

This produced narration that invented NPCs, locations, item names, and story events not in the game's database. Players encountered "the mysterious blacksmith Jareth" even though no blacksmith NPC existed. Doors appeared in walls. Items were described as having effects they didn't have.

### The V2 Principle

> **The LLM narrates facts it was given. It does not invent facts.**

The injector provides everything the narrator needs to write a grounded, accurate turn. If something is not in the injector's output, the narrator is prohibited from inventing it.

---

## Pipeline Position

```
[World State Machine + Resolvers]
             │
             ▼ mechanic_result (structured dict)
             │
    ┌─────────────────────┐
    │   Context Injector  │  ← This task
    └─────────────────────┘
             │
             ▼ complete prompt string
             │
    ┌─────────────────────┐
    │    LLM Narrator     │  ← Second LLM call
    └─────────────────────┘
             │
             ▼ Polish narrative text
```

The injector runs synchronously in the main turn pipeline. It reads from:
- `game_sessions` (current state, location, character)
- `game_locations` (full DB record for current location)
- `npc_definitions` (for NPCs present in location)
- `game_config_enemies` (for enemies in combat)
- `character_conditions` (active conditions)
- `characters` (HP, stats — for wound label calculation)
- `campaigns` (tone flags)
- The `mechanic_result` dict passed from the resolver

---

## What the Injector Assembles

The narrator prompt is divided into named blocks. Each block has a fixed header, structured content, and a separator. The injector builds each block from DB data + mechanic result. Missing optional data results in an empty block (excluded from prompt) — never a placeholder like "unknown."

### Block 1 — WORLD BLOCK

Current location, including atmosphere description and notable features.

**Template:**
```
=== ŚWIAT ===
Lokacja: {location.name}
Typ: {location.location_type}
Opis: {location.description}
Atmosfera: {location.atmosphere}
Pora: {session.time_of_day}
Pogoda: {session.weather}
```

**Source columns:**
- `game_locations.name`
- `game_locations.location_type` (dungeon / town / wilderness / interior / etc.)
- `game_locations.description` — the main descriptive text (1-3 sentences, set by admin)
- `game_locations.atmosphere` — short mood descriptor ("Mroczna, wilgotna piwnica. Zapach gnicia.")
- `game_sessions.time_of_day` — "świt" / "południe" / "zmierzch" / "noc"
- `game_sessions.weather` — optional, omitted if null

**Example output:**
```
=== ŚWIAT ===
Lokacja: Leśna Polana
Typ: wilderness
Opis: Mała polana otoczona gęstym lasem. W centrum stoi obalony pień, porośnięty mchem.
Atmosfera: Cisza przerywana tylko przez szelest liści. Zapach wilgoci i ziemi.
Pora: zmierzch
```

---

### Block 2 — ENTITIES BLOCK

All entities present in the current scene: NPCs and enemies.

**Template:**
```
=== POSTACIE NA SCENIE ===
{for each npc in npcs_present:}
NPC: {npc.name} [{npc.attitude}]
Osobowość: {npc.personality_prompt}
{endfor}
{if combat_roster is not empty:}
WROGOWIE W WALCE:
{for each enemy in combat_roster:}
- {enemy.name} (Tier: {enemy.tier}, HP: {enemy.hp}/{enemy.hp_max}) [{alive/dead}]
{endfor}
{endif}
{if entities empty:}
Brak postaci w tej lokacji.
{endif}
```

**Source columns:**
- `npc_definitions.name`
- `npc_definitions.attitude` — default_attitude field
- `npc_definitions.personality_prompt` — injected directly into narrator context
- `game_config_enemies.name`, `game_config_enemies.tier`
- `session_flags.combat_roster` (includes live HP values)

**Example output (combat scene):**
```
=== POSTACIE NA SCENIE ===
WROGOWIE W WALCE:
- Goblin Strażnik (Tier: 1, HP: 8/20) [żywy]
- Goblin Szaman (Tier: 2, HP: 18/18) [żywy]
```

**Example output (NPC dialogue scene):**
```
=== POSTACIE NA SCENIE ===
NPC: Boris Karczmarz [neutralny]
Osobowość: Mówi krótko i ostrożnie. Zawsze odwraca wzrok gdy mówi o gildii. Podaje piwo z drżącymi rękami.
```

---

### Block 3 — MECHANICAL RESULT BLOCK

What just happened, mechanically. This is the heart of the anti-hallucination system — the narrator must describe this outcome, not invent a different one.

**Template varies by action type.**

**ATTACK result template:**
```
=== WYNIK MECHANICZNY ===
Akcja: ATAK
Cel: {target_name}
Rzut: {roll} + {modifier} = {total} vs DC {dc}
Wynik: {TRAFIENIE / PUDŁO / TRAFIENIE KRYTYCZNE / AUTOMATYCZNA PORAŻKA}
{if hit:}
Obrażenia: {damage} → {target_name} HP: {hp_before} → {hp_after}
{if target dead:}
{target_name} GINIE.
{endif}
{endif}
{if crit:}
KRYTYK: podwójne obrażenia. Trafiony w: {hit_location}.
{endif}
```

**SKILL_ATTEMPT result template:**
```
=== WYNIK MECHANICZNY ===
Akcja: TEST UMIEJĘTNOŚCI ({skill_name})
Rzut: {roll} + {modifier} = {total} vs DC {dc}
Wynik: {SUKCES / PORAŻKA}
Konsekwencja: {consequence_text}
```

**FLEE result template:**
```
=== WYNIK MECHANICZNY ===
Akcja: UCIECZKA
Rzut DEX: {roll} + {modifier} = {total} vs {enemy_dex_total}
Wynik: {UCIECZKA UDANA / UCIECZKA NIEUDANA}
{if failed:}
Atak okazji: {enemy_name} zadaje {opp_damage} obrażeń.
{endif}
{if success:}
Nowa lokacja: {new_location_name}
{endif}
```

**DIALOGUE result template:**
```
=== WYNIK MECHANICZNY ===
Akcja: ROZMOWA
NPC: {npc_name}
Temat: {topic or "powitanie"}
{if must_reveal_info:}
NPC MUSI POWIEDZIEĆ (naturalnie, w kontekście): "{must_reveal_info}"
{endif}
{if secret_roll:}
Rzut Perswazji: {total} vs DC {dc} → {SUKCES / PORAŻKA}
{if failed:}
Sekret NIE zostaje ujawniony. NPC zmienia temat.
{endif}
{endif}
```

**MOVEMENT result template:**
```
=== WYNIK MECHANICZNY ===
Akcja: RUCH
Z: {from_location_name}
Do: {to_location_name}
```

**SEARCH result template:**
```
=== WYNIK MECHANICZNY ===
Akcja: PRZESZUKIWANIE (fokus: {focus or "ogólne"})
Rzut: {roll} + {modifier} = {total} vs DC {dc}
Wynik: {SUKCES / PORAŻKA}
{if success:}
Znalezione: {found_items_or_clues_list}
{else:}
Nic szczególnego nie znaleziono.
{endif}
```

**REST result template:**
```
=== WYNIK MECHANICZNY ===
Akcja: ODPOCZYNEK ({rest_type})
Status: {W TRAKCIE / ZAKOŃCZONY / PRZERWANY}
{if completed:}
HP przywrócone: {hp_before} → {hp_after}
Usunięte stany: {cleared_conditions_list or "brak"}
{endif}
```

**EXAMINE result template:**
```
=== WYNIK MECHANICZNY ===
Akcja: ZBADANIE
Cel: {target_name}
Dane z bazy: {target_description_from_db or "brak danych w bazie"}
```

---

### Block 4 — CHARACTER STATE BLOCK

The character's current condition, expressed in narrator-ready labels. The injector translates raw numbers (HP, conditions) into descriptive labels so the narrator doesn't do math.

**Template:**
```
=== STAN POSTACI ===
Postać: {character.name}
Stan zdrowia: {wound_label}
Aktywne stany: {conditions_list or "brak"}
Strach: {fear_label or "brak"}
```

**Wound label calculation** (HP percentage):

| HP % | Wound Label |
|---|---|
| 100% | "Zdrowy/a" |
| 75-99% | "Lekko zadrapany/a" |
| 50-74% | "Ranny/a" |
| 25-49% | "Poważnie ranny/a" |
| 10-24% | "Ciężko ranny/a — każdy ruch boli" |
| 1-9% | "Na skraju śmierci — ledwo oddycha" |
| 0% | "Nieprzytomny/a — rzuty na śmierć" |

**Fear label** (from `character_conditions` table, condition_type = fear_*):

| Condition | Fear Label |
|---|---|
| none | *(omitted)* |
| `fear_shaken` | "Zdenerwowany/a — lekki niepokój" |
| `fear_frightened` | "Przestraszony/a — trudno skupić myśli" |
| `terror` | "Opanowany/a przez terror — ciało nie słucha" |

**Conditions list:** active conditions from `character_conditions` table excluding fear states (those are in fear_label). Examples: "prone", "wound_heavy", "poisoned".

**Example output:**
```
=== STAN POSTACI ===
Postać: Aldric
Stan zdrowia: Poważnie ranny/a
Aktywne stany: wound_heavy, prone
Strach: Przestraszony/a — trudno skupić myśli
```

---

### Block 5 — CAMPAIGN TONE BLOCK

A short, consistent reminder of the campaign's narrative style. Prevents the narrator from drifting toward generic fantasy tropes.

**Template:**
```
=== TON KAMPANII ===
{campaign.tone_descriptor}
```

**Source:** `campaigns.tone_flags` JSON field (added in V2 schema if not present, default value below).

**Default tone_descriptor if not set:**
```
Mroczne fantasy. Świat jest surowy i niesprawiedliwy. Bohater nie jest wybrańcem — przeżywa dzięki sprytowi i szczęściu. Nie ma miejsca na epicki optymizm. Konsekwencje są realne.
```

Campaign-specific tones can override this entirely. Examples:
- Gothic horror: "Gotycki horror. Każde zwycięstwo jest pyrrusowe. Mroczna ironia jest mile widziana. Potwory mają motywacje, nie są tylko złem."
- Political intrigue: "Polityczna intryga w mieście. Nie ma wyraźnych złoczyńców. Każda postać ma coś do ukrycia. Przemoc jest ostatecznością."

---

### Block 6 — NARRATOR CONSTRAINTS

The final, inviolable instructions to the narrator LLM. This block is always included, always last, always in the same format.

**Template (fixed — not configurable per campaign):**
```
=== INSTRUKCJE DLA NARRATORA ===
Jesteś narratorem. Twoja rola:
1. Opisz wynik mechaniczny podany w bloku WYNIK MECHANICZNY. Nie zmieniaj go.
2. Opisy lokacji i postaci bazuj wyłącznie na danych z bloków ŚWIAT i POSTACIE NA SCENIE.
3. Nie wymyślaj nazw własnych, postaci, przedmiotów ani miejsc niewymienionych w kontekście.
4. Opisz stan zdrowia i emocje postaci zgodnie z blokiem STAN POSTACI.
5. Utrzymaj ton kampanii z bloku TON KAMPANII.
6. Pisz po polsku. Użyj 2-4 zdań. Nie zadawaj pytań graczowi.
7. Nie decyduj o kolejnych akcjach gracza.
```

---

## Complete Prompt Assembly

The injector concatenates all blocks in order, separated by newlines. Blocks with no content (e.g., ENTITIES BLOCK with no NPCs and no combat) include their header with "brak" filler.

**Full prompt structure:**
```
[WORLD BLOCK]
\n
[ENTITIES BLOCK]
\n
[MECHANICAL RESULT BLOCK]
\n
[CHARACTER STATE BLOCK]
\n
[CAMPAIGN TONE BLOCK]
\n
[NARRATOR CONSTRAINTS]
```

The injector does NOT include:
- Full campaign plan / GM plan (too long; irrelevant to single turn narration)
- Full character sheet (stats, skills, inventory) — only wound label and conditions matter
- Location data for locations not currently occupied
- Turn history beyond what is in the MECHANICAL RESULT BLOCK
- Player's raw message text (the narrator does not need to respond to it; it responds to the mechanical result)

---

## `must_reveal_info` Injection

When a DIALOGUE action resolves and the topic matches an NPC's `keyword_triggers`, the injector adds a constraint to the MECHANICAL RESULT BLOCK:

```
NPC MUSI POWIEDZIEĆ (naturalnie, w kontekście): "Gilda spotyka się w każdą środę przy dokach."
```

This string is injected verbatim (in Polish) from `npc_definitions.keyword_triggers[i].must_reveal_info`. The narrator must include this information in its response. The phrasing is up to the narrator ("naturally, in context") but the factual content is mandatory.

**Verification:** After the narrator response is generated, the injector runs a post-check: does the response contain the key noun phrases from `must_reveal_info`? If not, the narrator is called once more with the constraint emphasized:

```
WAŻNE: Twoja poprzednia odpowiedź nie zawierała wymaganej informacji.
NPC KONIECZNIE musi wspomnieć: "Gilda spotyka się w każdą środę przy dokach."
Przepisz odpowiedź uwzględniając tę informację.
```

This retry happens at most once. If the second response also omits the information, log a warning and return the second response as-is. Do not retry infinitely.

---

## Invented Proper Noun Detection

After the narrator returns its response, the injector runs a post-processing step to detect invented proper nouns.

**Algorithm:**

1. Extract all capitalized words/phrases from the narrator's response (heuristic: 2+ capital letters in sequence, or title-case words not at start of sentence)
2. Check each against a whitelist:
   - All NPC names in ENTITIES BLOCK
   - All location names (current + listed exits)
   - All enemy names in ENTITIES BLOCK
   - Character name from CHARACTER STATE BLOCK
   - Polish common words and titles (whitelist in `context_injector.py`)
3. Any proper noun not in the whitelist is flagged as potentially invented
4. Flagged nouns: substitute with generic description

**Substitution examples:**

| Invented | Substituted |
|---|---|
| "Jareth" (unknown NPC name) | "tajemniczy mężczyzna" |
| "Zamek Krasnoskała" (unknown location) | "odległa forteca" |
| "Miecz Losu" (invented item name) | "stara broń" |

**Implementation note:** This is a best-effort heuristic, not a perfect filter. Polish proper nouns are hard to distinguish from common nouns without a full NLP pipeline. The goal is to catch obvious invented names (typically single capitalized words in mid-sentence context). Over-aggressive filtering would break legitimate narrator responses.

Log all substitutions at DEBUG level with the original and substituted text.

---

## Service Structure (`context_injector.py`)

```python
class ContextInjector:
    def build(
        self,
        session: GameSession,
        mechanic_result: dict,
        action_type: str
    ) -> str:
        """Assemble the complete narrator prompt string."""
        
        blocks = []
        
        # Block 1: World
        location = self._get_location(session.location_key)
        blocks.append(self._build_world_block(location, session))
        
        # Block 2: Entities
        npcs = self._get_npcs_in_location(session.location_key)
        enemies = self._get_combat_roster(session)
        blocks.append(self._build_entities_block(npcs, enemies))
        
        # Block 3: Mechanical Result
        blocks.append(self._build_mechanic_block(action_type, mechanic_result))
        
        # Block 4: Character State
        character = self._get_character(session.character_id)
        conditions = self._get_active_conditions(session.character_id)
        blocks.append(self._build_character_state_block(character, conditions))
        
        # Block 5: Campaign Tone
        campaign = self._get_campaign(session.campaign_id)
        blocks.append(self._build_tone_block(campaign))
        
        # Block 6: Constraints (fixed)
        blocks.append(NARRATOR_CONSTRAINTS)
        
        return "\n\n".join(blocks)
    
    def post_process_response(
        self,
        narrator_response: str,
        session: GameSession,
        mechanic_result: dict,
        must_reveal_infos: list[str]
    ) -> tuple[str, bool]:
        """
        Post-process narrator response.
        Returns (processed_response, retry_needed).
        """
        # Check must_reveal_info
        for info in must_reveal_infos:
            if not self._check_info_present(narrator_response, info):
                return narrator_response, True  # retry needed
        
        # Strip invented proper nouns
        processed = self._strip_invented_nouns(narrator_response, session)
        
        return processed, False
```

---

## Turn Type Examples

### Exploration Turn (MOVEMENT)

**Input state:** Character moves from `loc_tavern` to `loc_dark_alley`. No enemies, no NPCs in alley. Night time.

**Injector output:**
```
=== ŚWIAT ===
Lokacja: Ciemna Uliczka
Typ: town_interior
Opis: Wąska uliczka między kamienicami. Błoto po kostki. Śmieci pod ścianami.
Atmosfera: Ktoś obserwuje z cienia. Zapach zepsutego jedzenia.
Pora: noc

=== POSTACIE NA SCENIE ===
Brak postaci w tej lokacji.

=== WYNIK MECHANICZNY ===
Akcja: RUCH
Z: Tawerna Pod Wiszącym Człowiekiem
Do: Ciemna Uliczka

=== STAN POSTACI ===
Postać: Aldric
Stan zdrowia: Zdrowy/a
Aktywne stany: brak
Strach: brak

=== TON KAMPANII ===
Mroczne fantasy. Świat jest surowy i niesprawiedliwy. Bohater nie jest wybrańcem — przeżywa dzięki sprytowi i szczęściu. Nie ma miejsca na epicki optymizm. Konsekwencje są realne.

=== INSTRUKCJE DLA NARRATORA ===
Jesteś narratorem. Twoja rola:
1. Opisz wynik mechaniczny podany w bloku WYNIK MECHANICZNY. Nie zmieniaj go.
2. Opisy lokacji i postaci bazuj wyłącznie na danych z bloków ŚWIAT i POSTACIE NA SCENIE.
3. Nie wymyślaj nazw własnych, postaci, przedmiotów ani miejsc niewymienionych w kontekście.
4. Opisz stan zdrowia i emocje postaci zgodnie z blokiem STAN POSTACI.
5. Utrzymaj ton kampanii z bloku TON KAMPANII.
6. Pisz po polsku. Użyj 2-4 zdań. Nie zadawaj pytań graczowi.
7. Nie decyduj o kolejnych akcjach gracza.
```

---

### Combat Turn (ATTACK — Hit)

**Input state:** Character attacks goblin_1 with sword_iron. Roll 17, total 20, DC 14. Hit. 8 damage. Goblin at 8→0 HP. Goblin dies.

**Injector output (relevant blocks only):**
```
=== POSTACIE NA SCENIE ===
WROGOWIE W WALCE:
- Goblin Strażnik (Tier: 1, HP: 0/20) [martwy]
- Goblin Szaman (Tier: 2, HP: 18/18) [żywy]

=== WYNIK MECHANICZNY ===
Akcja: ATAK
Cel: Goblin Strażnik
Rzut: 17 + 3 = 20 vs DC 14
Wynik: TRAFIENIE
Obrażenia: 8 → Goblin Strażnik HP: 8 → 0
Goblin Strażnik GINIE.

=== STAN POSTACI ===
Postać: Aldric
Stan zdrowia: Lekko zadrapany/a
Aktywne stany: brak
Strach: brak
```

---

### NPC Dialogue Turn (with must_reveal_info)

**Input state:** Character asks Boris about "guild". `keyword_triggers` has `{"keyword": "guild", "must_reveal_info": "Gilda spotyka się w każdą środę przy dokach.", "is_secret": false}`.

**Injector output (relevant blocks only):**
```
=== POSTACIE NA SCENIE ===
NPC: Boris Karczmarz [neutralny]
Osobowość: Mówi krótko i ostrożnie. Zawsze odwraca wzrok gdy mówi o gildii. Podaje piwo z drżącymi rękami.

=== WYNIK MECHANICZNY ===
Akcja: ROZMOWA
NPC: Boris Karczmarz
Temat: guild
NPC MUSI POWIEDZIEĆ (naturalnie, w kontekście): "Gilda spotyka się w każdą środę przy dokach."
```

---

### Fear Test Result Turn

**Input state:** Character failed WIS save (roll 4, total 6 vs DC 14) against goblin fear aura. Applied condition: `fear_frightened` (severity 2).

**Injector output (relevant blocks only):**
```
=== WYNIK MECHANICZNY ===
Akcja: TEST STRACHU
Źródło: Aura strachu Goblina Szamana
Rzut WIS: 4 + 2 = 6 vs DC 14
Wynik: PORAŻKA
Zastosowany stan: Przestraszony/a (stopień 2)

=== STAN POSTACI ===
Postać: Aldric
Stan zdrowia: Lekko zadrapany/a
Aktywne stany: brak
Strach: Przestraszony/a — trudno skupić myśli
```

---

## Edge Cases

1. **Location description is empty in DB:** The WORLD BLOCK omits the `Opis:` line rather than injecting an empty string. The narrator should not notice — the atmosphere line and location type provide enough context. Log a warning so an admin can fill in the description.

2. **NPC `personality_prompt` is empty:** The `Osobowość:` line is omitted from the ENTITIES BLOCK. The narrator falls back to its own NPC archetype knowledge — which is fine for generic characters but undesirable for important story NPCs. Admin should fill personality_prompt for all key NPCs.

3. **Multiple NPCs in location:** All NPCs in the location are listed in the ENTITIES BLOCK. The narrator must reference only NPCs who are relevant to the current action. The NARRATOR CONSTRAINTS block does not filter by "most relevant NPC" — that would require another LLM call. Instead, accept that minor NPCs in the background may be ignored by the narrator.

4. **`mechanic_result` missing expected fields:** If a resolver returns an incomplete dict (e.g., no `damage` field on an ATTACK result), the injector must log an error and substitute `"[dane niedostępne]"` for missing values. Do not crash — return a degraded but valid prompt.

5. **Character HP is exactly 0 (death-save state):** The wound label must be "Nieprzytomny/a — rzuty na śmierć". The narrator should describe the character as unconscious — this is in the CHARACTER STATE BLOCK. The MECHANICAL RESULT BLOCK also describes the death-save outcome.

6. **`must_reveal_info` post-check false positive:** The noun-matching check might fail to detect the info if the narrator paraphrases. E.g., `must_reveal_info = "Gilda spotyka się w środy przy dokach."` but narrator says "Boris wspomina, że gildia zbiera się co środę przy nabrzeżu." — semantically correct, string match fails. The check is therefore fuzzy: extract 2-3 key words from `must_reveal_info` (e.g., "gilda", "środa", "doki") and require at least 2 of them to appear (case-insensitive) in the narrator response.

7. **Invented noun detection over-aggressive on Polish titles:** Words like "Mistrz", "Pani", "Kapitan" are Polish honorifics commonly used as informal names. These must be in the whitelist. "Kapitan straży" is not an invented NPC; "Kapitan Jareth" is. The detection algorithm must look for multi-word capitalized sequences, not single words.

8. **Campaign tone_descriptor not set (legacy campaigns):** Use the default dark fantasy tone descriptor. Do not error. Migrate existing campaigns to add a default value via the V2 schema migration (add `DEFAULT` in `ALTER TABLE campaigns ADD COLUMN tone_descriptor ...` if this column is not present — this may require a TASK_01 amendment).

9. **Very long `personality_prompt`:** Admin-entered personality prompts could be excessively long. Truncate to 200 characters in the injector, not in the DB. Log a warning if truncation occurs. Long personality prompts waste tokens and dilute narrator attention.

10. **Combat with 0 living enemies (post-combat edge case):** If the WSM handled combat resolution correctly, this state should not reach the injector. But if it does, the ENTITIES BLOCK should list all enemies as `[martwy]` and the MECHANICAL RESULT BLOCK should note "WALKA ZAKOŃCZONA." The narrator should describe the aftermath.

11. **Narrator response in wrong language:** If the narrator responds in English (model sometimes drifts under certain prompts), add a post-check: if >50% of words in the response are non-Polish-alphabet characters, re-call with an added constraint: `WAŻNE: Odpowiedz WYŁĄCZNIE po polsku.` Log the drift event.

12. **Prompt token budget:** If the full assembled prompt exceeds the model's context window (e.g., very long location description + many NPCs + long mechanic result), the injector must trim in priority order: first trim enemy list to alive enemies only, then trim NPC list to NPCs directly interacted with, then truncate atmosphere/description to 1 sentence. Never trim MECHANICAL RESULT BLOCK or NARRATOR CONSTRAINTS.

---

## Test Checklist

Each test verifies that the injector produces correct, non-hallucinatory context for a given turn type.

### Exploration Turn Test

**Setup:** NARRATIVE state, location `loc_dark_alley` (safe_for_rest=0, description set), no NPCs, no combat, movement action completed.

- [ ] WORLD BLOCK contains correct location name, description, atmosphere
- [ ] ENTITIES BLOCK contains "Brak postaci w tej lokacji."
- [ ] MECHANICAL RESULT BLOCK shows RUCH with correct from/to location names
- [ ] CHARACTER STATE BLOCK shows correct wound label (100% HP = "Zdrowy/a")
- [ ] CAMPAIGN TONE BLOCK contains the campaign's tone_descriptor
- [ ] NARRATOR CONSTRAINTS block is present and unmodified
- [ ] No empty or null values leaked into prompt (all missing optional fields omitted cleanly)

### Combat Turn Test

**Setup:** COMBAT state, 2 enemies (one alive, one just killed), ATTACK action, hit, 8 damage, target dead.

- [ ] ENTITIES BLOCK lists both enemies — dead enemy marked `[martwy]`, alive marked `[żywy]`
- [ ] MECHANICAL RESULT BLOCK shows correct roll, total, DC, hit verdict
- [ ] MECHANICAL RESULT BLOCK shows correct HP transition and "GINIE" marker
- [ ] CHARACTER STATE BLOCK reflects correct wound label (character took damage last turn)
- [ ] No invented proper nouns in injector output (only injector content, not narrator response — that's tested separately)

### NPC Dialogue Turn Test (with must_reveal_info, no secret roll)

**Setup:** NARRATIVE state, NPC `innkeeper_boris` present, DIALOGUE action, topic="guild", `is_secret=false`, `must_reveal_info` set.

- [ ] ENTITIES BLOCK contains Boris with correct `personality_prompt`
- [ ] MECHANICAL RESULT BLOCK contains `NPC MUSI POWIEDZIEĆ` line with correct Polish text
- [ ] No secret roll section (is_secret=false)
- [ ] Post-process check: if narrator includes the key words from must_reveal_info, `retry_needed=False`
- [ ] Post-process check: if narrator omits them, `retry_needed=True` and retry prompt is formatted correctly

### NPC Dialogue Turn Test (with must_reveal_info, secret roll failed)

**Setup:** Same NPC, `is_secret=true`, secret roll failed.

- [ ] MECHANICAL RESULT BLOCK shows roll, DC, "PORAŻKA" verdict
- [ ] MECHANICAL RESULT BLOCK shows "Sekret NIE zostaje ujawniony."
- [ ] `must_reveal_info` is NOT injected (secret was not unlocked)

### Fear Test Result Turn

**Setup:** Character failed WIS save against fear aura. Condition `fear_frightened` applied.

- [ ] MECHANICAL RESULT BLOCK shows fear test action, source, roll, result, applied condition
- [ ] CHARACTER STATE BLOCK shows correct fear label "Przestraszony/a — trudno skupić myśli"
- [ ] CONDITIONS list does NOT include fear state (fear is in its own field)

### Invented Noun Post-Processing Test

**Setup:** Narrator response contains `"Jareth"` (invented name not in ENTITIES BLOCK).

- [ ] `_strip_invented_nouns()` detects "Jareth" as not in whitelist
- [ ] Response is returned with "Jareth" replaced by "tajemniczy mężczyzna"
- [ ] Substitution logged at DEBUG level

### Token Budget Test

**Setup:** Prompt assembly would exceed 3000 tokens (simulated with a very long location description + 10 NPCs + long mechanic result).

- [ ] Injector trims NPC list to directly-interacted NPCs first
- [ ] MECHANICAL RESULT BLOCK remains complete
- [ ] NARRATOR CONSTRAINTS block remains complete
- [ ] Final prompt is within token budget
