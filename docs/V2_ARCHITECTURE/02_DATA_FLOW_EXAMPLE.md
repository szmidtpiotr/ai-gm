# AI-GM V2 — Full Data Flow Example

> **Purpose:** A complete end-to-end trace of what happens from "player creates campaign" to "player receives first turn response." Shows exactly what data comes from where, what the LLM receives, and what the system resolves without LLM.

**Scenario:** Player creates Warrior named "Aldric", campaign set in a small dark town.

---

## STEP 1 — Campaign Created

Player fills in: Title = "Nowa Przygoda", clicks Create.

**What the system does:**
```python
campaigns table:
  id: 42
  title: "Nowa Przygoda"
  owner_user_id: 7
  status: "setup"
  gm_plan_json: "{}"   ← empty, not generated yet
```

Character creation modal opens immediately. Campaign plan is **NOT** generated yet — we don't have a character.

---

## STEP 2 — Character Wizard Step 1 (Basic Info)

Player enters:
- Name: "Aldric"
- Background: "Były żołnierz szukający pracy po tym jak jego oddział zginął w zasadzce"
- Archetype: Warrior

**System creates character with calculated defaults:**
```python
characters table:
  id: 15
  campaign_id: 42
  name: "Aldric"
  archetype: "warrior"
  level: 1

sheet_json: {
  "stats": {
    "STR": 12, "DEX": 12, "CON": 12,
    "INT": 10, "WIS": 11, "CHA": 10, "LCK": 10
  },
  "current_hp": 11,      # formula: base 10 + CON_mod(+1) × 1
  "max_hp": 11,
  "current_mana": 0,     # Warrior — always 0
  "max_mana": 0,
  "skills": {
    "combat": 2, "athletics": 1, "intimidation": 1, ...  # warrior defaults
  },
  "background_note": "Były żołnierz szukający pracy...",
  "identity": {},        # empty — filled in Step 4
  "gm_only": {}          # empty — filled in Step 4
}
```

---

## STEP 3 — Character Wizard Steps 2 & 3 (Stats + Skills)

Player redistributes: bumps STR to 14, CON drops to 10.

**System recalculates HP live:**
```
CON 10 → mod 0
max_hp = 10 + (0 × 1) = 10  ← dropped from 11
```

Player accepts. Skills stay at defaults. `PATCH /characters/15/sheet` saves changes.

---

## STEP 4 — Character Wizard Step 4 (GM Generates Identity)

**Frontend calls:** `POST /characters/15/generate-identity`

**→ LLM CALL #1: Identity Generation**

Prompt sent to LLM:
```
Stwórz tożsamość postaci na podstawie poniższych danych.

POSTAĆ:
  Imię: Aldric
  Archetype: Wojownik
  Statystyki: STR 14(+2), DEX 12(+1), CON 10(+0), INT 10, WIS 11, CHA 10, LCK 10
  Umiejętności najwyższe: Combat(2), Athletics(1), Intimidation(1)
  Historia gracza: "Były żołnierz szukający pracy po tym jak jego oddział zginął w zasadzce"

Wygeneruj:
1. Wygląd (2-3 zdania)
2. Osobowość (2-3 zdania)
3. Więzi (2 wpisy: {opis, typ: person/place/object/ideal})
4. Słabości (2 wpisy: {opis, typ: fear/flaw/addiction/trauma})
5. [UKRYTE] Ukryte predyspozycje (1-2 zdania — cecha utajona, nieznana graczowi)
```

LLM returns:
```json
{
  "appearance": "Aldric ma szerokie ramiona i twarz pokreśloną bliznami po dawnych walkach. Nosi stare, dobrze utrzymane zbroje z wyblakłym herbem kompanii, której już nie ma. Jego oczy są spokojne — zbyt spokojne jak na kogoś, który widział tyle co on.",
  "personality": "Mówi mało i tylko gdy musi. Lojalność traktuje jak religię, bo jej brak kosztował go wszystko. Pod twardą powierzchnią kryje się człowiek, który nie umie już ufać nikomu.",
  "bonds": [
    {"description": "Szuka sprawiedliwości za śmierć swojego oddziału — wierzy, że zasadzka była zdradą", "type": "ideal"},
    {"description": "Jedyna rzecz, którą zachował z dawnego życia: medalion dowódcy — obiecał go kiedyś oddać rodzinie", "type": "object"}
  ],
  "weaknesses": [
    {"description": "Nie może zostawić nikogo za sobą — nawet obcych w potrzebie, co wciąga go w kłopoty", "type": "flaw"},
    {"description": "Budzą się w nim noce pełne krzyków oddziału — alkohol to jedyna ulga", "type": "addiction"}
  ],
  "secret_predisposition": "Aldric nigdy nie przyznał, że jako dziecko uczył się czytać runy od wędrownego maga. Czasem, gdy jest bardzo zdenerwowany, metalowe przedmioty w jego pobliżu lekko drżą."
}
```

**Player sees and can edit:** appearance, personality, bonds, weaknesses.
**Player NEVER sees:** secret_predisposition.

**Saved to DB:**
```python
sheet_json["identity"] = {appearance, personality, bonds, weaknesses}
sheet_json["gm_only"]  = {
  "secret_predisposition": "Aldric nigdy nie przyznał..."
}
```

---

## STEP 5 — Finalize → Campaign Plan Generation

Player clicks "Zatwierdź". `POST /characters/15/finalize-sheet`.

**Immediately triggers:** `generate_campaign_plan(campaign_id=42, character_id=15)`

### 5a — Ideas Bank Query (system, no LLM)
```sql
SELECT * FROM campaign_ideas
WHERE category = 'seed'
  AND quality_rating >= 3
  AND is_active = 1
ORDER BY quality_rating DESC, times_used ASC
LIMIT 3
```
Returns (example): "Plaga Bogów" seed (rating 4), "Zdrajca w Murach" seed (rating 3).

### 5b — Campaign Plan Generation

**→ LLM CALL #2: Campaign Plan**

Prompt sent to LLM:
```
Stwórz plan kampanii mrocznej fantasy dla tej postaci.
Świat: grim, niebezpieczny, moralnie niejednoznaczny. Brak wybrańców losu.

POSTAĆ:
  Imię: Aldric, Wojownik poz. 1
  Historia: Były żołnierz, zgubił oddział w zasadzce
  Więzi:
    - Szuka sprawiedliwości za zdradę (ideal)
    - Medalion dowódcy do oddania rodzinie (object)
  Słabości:
    - Nie może zostawić nikogo za sobą (flaw)
    - Alkohol jako ucieczka od koszmarów (addiction)

INSPIRACJE Z BANKU POMYSŁÓW:
  1. "Plaga Bogów": Zaraza w mieście rozsiewana przez kult
  2. "Zdrajca w Murach": Ktoś bliski okazuje się winny zbrodni

ZASADY:
- 3 akty, 2+ zakończenia (oba moralnie niejednoznaczne)
- Akt 1 MUSI nawiązywać do przynajmniej jednej więzi
- Antagonista MUSI dotykać słabości
- Odpowiedź TYLKO jako JSON wg schematu CampaignPlan
```

LLM returns validated `CampaignPlan` JSON:
```json
{
  "title": "Zdrada pod Graustein",
  "premise": "Aldric trafia do miasteczka Graustein — i odkrywa, że człowiek który zdradził jego oddział żyje tu jako szanowany obywatel.",
  "acts": [
    {
      "number": 1, "title": "Znajoma twarz",
      "summary": "Aldric przybywa szukając pracy. W karczmie rozpoznaje twarz — Hans Bremer, którego uważał za zabitego, siedzi przy piwie i śmieje się.",
      "key_beats": ["arrival_graustein", "recognize_bremer", "first_info_gathering"],
      "completed": false
    },
    {
      "number": 2, "title": "Cena prawdy",
      "summary": "Aldric zbiera dowody. Bremer jest teraz bogatym kupcem z ochroną i wpływami.",
      "key_beats": ["bremer_confronted", "discover_conspiracy", "aldric_tempted_by_drink"],
      "completed": false
    },
    {
      "number": 3, "title": "Rozliczenie",
      "summary": "Aldric wybiera: publiczne oskarżenie, cicha zemsta, albo układ.",
      "key_beats": ["final_evidence_found", "confrontation_bremer"],
      "completed": false
    }
  ],
  "endings": [
    {
      "id": "ending_a", "title": "Sprawiedliwość", "type": "primary",
      "description": "Aldric demaskuje Bremera publicznie. Prawda okazuje się bardziej skomplikowana.",
      "requirements": ["conspiracy_exposed", "public_accusation"]
    },
    {
      "id": "ending_b", "title": "Milczenie za cenę", "type": "alternate",
      "description": "Bremer oferuje pieniądze i adres rodziny dowódcy. Aldric wychodzi z medalionem spełnionym — ale Bremer żyje.",
      "requirements": ["confrontation_bremer", "player_chose_deal"]
    }
  ],
  "key_npcs": [
    {
      "key": "hans_bremer", "name": "Hans Bremer", "role": "antagonist",
      "importance": "critical", "deviation_consequence": "branch", "alive": true
    },
    {
      "key": "innkeeper_graustein", "name": "Karczmiarz Wotan", "role": "ally",
      "importance": "supporting", "deviation_consequence": "steer", "alive": true
    }
  ],
  "key_locations": [
    {"key": "graustein_town",   "name": "Graustein",            "role": "starting_point", "visited": false},
    {"key": "graustein_tavern", "name": "Karczma 'Pod Krzyżem'", "role": "hub",           "visited": false}
  ],
  "active_act": 1,
  "engine_private": {
    "secret_predisposition_hint": "Aldric's magical sensitivity — przydatne gdy odkryje runy na medalionie",
    "hidden_twist": "Bremer nie działał sam — był szantażowany przez kogoś wyżej",
    "contingency": "Jeśli Bremer zginie w Akcie 1: wprowadź jego mocodawcę jako nowego antagonistę"
  }
}
```

System validates with Pydantic `CampaignPlan`. Saves to `campaigns.gm_plan_json`.

### 5c — World Content Created (system, no LLM)

Plan references locations and NPCs that don't exist in DB yet:

```python
# Locations
get_or_create_location("graustein_town")   → not found → CREATE, review_status='pending_review'
get_or_create_location("graustein_tavern") → not found → CREATE, review_status='pending_review'

# NPCs — small LLM call each to generate personality_prompt
get_or_create_npc("hans_bremer")
  → personality_prompt: "Pozornie spokojny kupiec, pod spodem nerwowy.
     Nigdy nie patrzy w oczy przy rozmowie o wojsku. Ukrywa poczucie winy."

get_or_create_npc("innkeeper_graustein")
  → personality_prompt: "Wotan — stary, obserwujący, wie wszystko o wszystkich.
     Mówi mało, ale słucha dużo."
```

### 5d — Game Session Created

```python
game_sessions:
  campaign_id: 42
  character_id: 15
  current_location_id: graustein_tavern.id   ← starting location from plan
  session_flags: {
    "game_state": "NARRATIVE",
    "short_rest_count": 0,
    "death_save_state": null
  }
```

---

## STEP 6 — Opening Scene Generation

Triggered immediately after plan saves. No player input.

**→ LLM CALL #3: Opening Scene Narration**

Context Injector assembles:
```
=== ŚWIAT ===
Lokacja: Karczma "Pod Krzyżem", Graustein
Opis: [graustein_tavern.description from DB]
Atmosfera: Zadymiona, głośna, zapach piwa i mokrego drewna
Obecne postacie:
  - Wotan (Karczmiarz): stary, obserwujący, wie wszystko o wszystkich
========================

=== POSTAĆ ===
Imię: Aldric | Wojownik poz.1 | Stan: Bez ran
Więź 1: Szuka sprawiedliwości za zdradę
Więź 2: Medalion dowódcy do oddania rodzinie
Słabość 1: Nie może zostawić nikogo za sobą
Słabość 2: Alkohol jako ucieczka od koszmarów
========================

=== MECHANIKA ===
Typ tury: opening_scene (GM inicjuje, gracz nic nie zrobił)
========================

=== TON ===
Mroczna fantasy. Grim. Świat jest niebezpieczny i niesprawiedliwy.
Napisz 100-200 słów po polsku. Nie mów graczowi co ma robić.
========================
```

LLM writes:
```
Karczma "Pod Krzyżem" pachnie starym dymem i tańszym piwem niż byś chciał.
Wotan za ladą wyciera kufle szmatą, która nie jest zbyt czysta, i mierzy cię
wzrokiem handlarza oceniającego towar.

Usiadłeś przy ścianie — stary nawyk. Stamtąd widać drzwi.

I wtedy go zobaczyłeś.

Przy dalekim stole, z kuflem w ręku i śmiechem na ustach, siedzi człowiek,
którego twarz wyryła się w twoją pamięć tamtej nocy. Hans Bremer. Żywy.
Śmiejący się. W czystych ubraniach.

Medalion dowódcy jest zimny przy twoim sercu.
```

**Stored as:**
```python
campaign_turns:
  campaign_id: 42, character_id: 15, turn_number: 1
  user_text: NULL       ← no player input
  assistant_text: "Karczma Pod Krzyżem pachnie..."
  route: "narrative"
  metadata: {"turn_type": "opening_scene"}
```

**Frontend receives:**
- Opening scene prose in chat
- Location badge: `📍 Karczma "Pod Krzyżem"`
- HP bar: 10/10 (green, no wound label)
- Text input: **enabled** — player can now act

---

## STEP 7 — Player's First Action

Player types: *"Czy to naprawdę Bremer? Przyglądam mu się uważnie."*

### 7a — Intent Parser

**→ LLM CALL #4: Intent Parsing**

Prompt:
```
Stan gry: NARRATIVE
Lokacja: graustein_tavern
Wiadomość gracza: "Czy to naprawdę Bremer? Przyglądam mu się uważnie."

Zwróć JEDNĄ akcję jako tag [ACTION:TYP:parametry].
Dostępne typy: ATTACK, FLEE, STEALTH_ATTEMPT, DIALOGUE, MOVEMENT,
               SEARCH, ITEM_USE, REST, EXAMINE, SKILL_ATTEMPT, SHOP
```

LLM returns: `[ACTION:EXAMINE:target=hans_bremer:focus=identity_confirmation]`

### 7b — World State Machine (system, no LLM)

```python
state = "NARRATIVE"         → EXAMINE valid ✓
target = "hans_bremer"      → exists in npc_definitions ✓
target in current location? → graustein_tavern.npc_keys contains "hans_bremer" ✓
→ VALID. Route to EXAMINE resolver.
```

### 7c — Mechanic Resolver (system, no LLM)

```python
action: EXAMINE
target: hans_bremer (known to player — personal history)
→ No dice roll required for recognising a known person

result = {
  "outcome": "success",
  "certainty": "high",
  "mechanical_note": "No roll — Aldric knows Bremer personally"
}
```

### 7d — World State Update (system, no LLM)

```python
# Beat completed
plan.acts[0].key_beats["recognize_bremer"].visited = True
campaigns.gm_plan_json updated

# Action logged
action_log: {
  campaign_id: 42, turn_number: 2,
  action_type: "EXAMINE",
  action_params: {"target": "hans_bremer", "focus": "identity_confirmation"},
  mechanic_result: {"outcome": "success", "certainty": "high"}
}
```

### 7e — Context Injector

```
=== ŚWIAT ===
Lokacja: Karczma "Pod Krzyżem"
Atmosfera: Zadymiona, głośna
Obecne NPC:
  - hans_bremer: Pozornie spokojny kupiec, pod spodem nerwowy.
    Nigdy nie patrzy w oczy przy rozmowie o wojsku. Ukrywa poczucie winy.
  - innkeeper_graustein: Stary, obserwujący, wie wszystko.
========================

=== POSTAĆ ===
Imię: Aldric | Stan: Bez ran
Kontekst: Szuka sprawiedliwości za zdradę — Bremer to kluczowy antagonista
========================

=== MECHANIKA ===
Akcja: EXAMINE (obserwacja)
Cel: Hans Bremer (antagonista krytyczny, żywy)
Wynik: SUKCES — Aldric rozpoznaje go z całkowitą pewnością
Nota: Znają się osobiście z wojska
========================

=== TON ===
Mroczna fantasy. To jest moment dramatyczny — pisz z napięciem.
2-3 zdania po polsku. Nie pytaj co gracz zrobi dalej.
========================
```

### 7f — Narrator

**→ LLM CALL #5: Narration**

LLM writes:
```
To Bremer. Nie ma wątpliwości.

Te same oczy, ten sam sposób trzymania kufla lewą ręką.
Tylko że teraz ma na sobie porządny płaszcz i śmieje się z czymś
co powiedział mu siedzący naprzeciwko gruby kupiec.

Medalion w twojej kieszeni nagle waży tyle co wyrzut sumienia.
```

**Player receives:**
- Polish prose in chat
- No HP/location change (same state)
- Campaign plan internally: beat `recognize_bremer` = ✓ visited

---

## Summary: Who Did What

| Data / Decision | Source | LLM involved? |
|---|---|---|
| Character stat defaults | System (archetype lookup) | No |
| HP = 10 + CON_mod × level | System (formula) | No |
| Character appearance, personality, bonds, weaknesses | LLM Call #1 | Yes |
| Secret predisposition | LLM Call #1 (hidden from player) | Yes |
| Campaign plan (acts, endings, key NPCs) | LLM Call #2 from character + Ideas Bank | Yes |
| Ideas Bank seeds queried | System (SQL query) | No |
| Location records created | System (get_or_create) | No |
| NPC personality_prompt generated | Small LLM call per NPC | Yes |
| Starting location assigned | System (from plan.key_locations[0]) | No |
| Opening scene prose | LLM Call #3 (given location + character) | Yes |
| "przyglądam się" → EXAMINE tag | LLM Call #4 (intent parser) | Yes |
| EXAMINE valid in NARRATIVE state? | World State Machine | No |
| Bremer recognised (no roll needed) | Mechanic Resolver | No |
| Beat "recognize_bremer" marked visited | System (plan schema update) | No |
| Final prose narration | LLM Call #5 (given mechanical result) | Yes |

**5 LLM calls total. Zero game outcomes decided by LLM.**

---

## What This Example Validates

- ✅ LLM generates creative content (identity, plan, prose) but never decides mechanics
- ✅ DB is source of truth for all world facts (locations, NPCs fed into context)
- ✅ Intent Parser keeps player input structured without restricting it
- ✅ Campaign plan is machine-readable (system detects beat completion automatically)
- ✅ Pending world entries (Graustein, Bremer) work immediately in-session, admin reviews later
- ✅ Character bonds/weaknesses directly shape the campaign narrative
