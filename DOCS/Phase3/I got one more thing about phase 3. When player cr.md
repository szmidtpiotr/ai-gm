<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>

# I got one more thing about phase 3. When player create campaing and is creating hero, then when we create hero, there should be beside stats chanign and creation, there shoudl be system that player need to write something about a player, who he is, how he look, etc. Describe him. So based on that, GM will start a session instead of asking player what he is dooing.

Also most critical thing is that we need to shift narration from player to GM. Player is responsing to what GM is narrating. How can we put that into what we already decided to do in phase 3

You've identified two critical Phase 3 enhancements: **(1) character backstory narrative during creation** and **(2) shifting narration from player-driven to GM-driven turn structure**. Both fit cleanly into the existing spec and will improve GM immersion.

Here's the updated Phase 3 that incorporates both:

## 🔥 Updated Phase 3.1: Character Sheet + Backstory + GM-First Turns

### Character Sheet Enhancement

Add **free-text backstory field** to character JSON:

```json
{
  "level": 1,
  "stats": {
    "strength": {"value": 15, "modifier": 2}
  },
  "hp": {"current": 12, "max": 12},
  "skills": {"generic": {"stealth": 3}},
  "backstory": {
    "summary": "Býły besuchen voják, który stracił żonę w wojnie. Szuka zemsty na czarnoksiężniku, który wypalił jego wieś. Noszy starą bliznę na lewym ramieniu i unika alkoholu.",
    "appearance": "Sto lat mężczyzn, wysoki, siwe włosy, broda, blizna od ramienia do piersi, noszy przepalony płaszcz",
    "personality": "Mrukliwy, powściągliwy, nie ufa autorytetom, chroni słabych",
    "goals": ["Zemsta na czarnoksiężniku", "Znaleźć spokój", "Odkupić grzechy"],
    "fears": ["Strach", "Porzucenie", "Utrata kontroli"]
  },
  "inventory": ["miecz", "skórzany pas", "medalion"],
  "location": " Klasztor Krwawego Kamienia"
}
```

**Why this works**
Backstory provides **GM context for opening scenes** rather than asking "Who are you?" on turn 1. The GM uses appearance/personality/goals to start with relevant hooks.[^1][^2]

### GM-First Turn Structure (Critical Shift)

**Old (player-driven):**

```
User: "Jestem wojownikiem" → AI: "Co robisz?"
```

**New (GM-driven):**

```
AI: "Stoisz w ruinach klasztoru. Powietrze pachnie dymem. Co robisz?"
User (name): "Mówię: Kaelidring. Co widzę?"
AI: "Widzisz grzyby na ścianach..."
User: "Podchodzę do nich"
```

**Implementation change:**

First turn (`turn_number === 1`) triggers a **special GM opening prompt** that:

1. Reads `character.backstory` for personalization
2. Reads `campaign.sheet_json.summary` for hook
3. Narrates opening scene
4. Ends with **"Co robisz?"** question[^3]

### Updated LLM Prompt Flow

**Turn 1 (GM opening):**

```
System: Twoja rola = AI Mistrz Gry RPG
Character: Kaelidring, były wojskowy, blizna, szuka zemsty
Campaign: Klasztor Krwawego Kamienia, dzidy, ruiny

Prompt:
"Zacznij sesję opisem otoczenia. Wpleć elementy z tła postaci (blizna, wojna, zemsta).
Opisz grzyby, portal, pergamin. Zakończ pytaniem 'Co robisz?'.
Max 150 słów. Nikt nie mówi, to jest początek sesji."
```

**Subsequent turns (narration → player response):**

```
System: Upcoming turn is PLAYER responding to GM
Previous turn: GM opisał grzyby i pergamin, zapytał "Co robisz?"
Current: Player "Podchodzę do pergaminu"

Prompt:
"GM to ty. Player mówi: 'Podchodzę do pergaminu'.
Opisz konsekwencje (dzida, mapa). Co robisz dalej?
Nigdy nie cadz na gracz. Ty Mistrz Gry.
Max 150 słów."
```

See prompted turn structure for AI RPG GMs: AI acts as GM, describes scenes, presents choices, player responds.[^4][^3]

### Backend Changes

**Turn engine (`runnarrativeturn`)** updates:

```python
def runnarrativeturn(conn, campaign, character, usertext, model):
    # Turn 1: GM opening
    if turn_number == 1:
        system_prompt = f"""
        Jesteś Mistrzem Gry. Game Master.
        Postać: {character['backstory']['summary']}
        Wygląd: {character['backstory']['appearance']}
        
        Zacznij sesję w {campaign['world_state']['current_location']}.
        Opisz otoczenie. Wpleć tło postaci. Sztuka "Co robisz?".
        """
    else:
        # Normal turn: GM responds to player
        system_prompt = f"""
        Jesteś Mistrzem Gry. Ty narrujesz, gracz odpowiada.
        Poprzednie: GM opisał {last_assistant_text[:200]}
        Gracz: {usertext}
        
        Odpowiedz jako GM. Nie gadaj za gracza.
        """
    
    # Feed character sheet + backstory + world state to context
    context = {
        "character": character["sheet_json"],
        "campaign": campaign["sheet_json"],
        "backstory": character["backstory"]
    }
```

**Why this works**
Game Master describes the situation, players describe PC actions (standard TTRPG flow). AI GM should remain adaptive but center narrative on player agency.[^3][^4]

## 📋 Updated Phase 3 Timeline

### Phase 3.1: Schemas + Backstory + GM Server (Week 1)

**Deliverables:**

- Add `backstory` field to `CharacterCreateRequest`
- Validate backstory fields: summary, appearance, personality, goals, fears
- Store in `character.sheet_json`
- Modify `runnarrativeturn()` to check `turn_number == 1`
- Create GM opening prompt using backstory + location
- Feed entire sheet + backstory + campaign state to LLM context[^5]


### Phase 3.2: Dice Parser (Week 2)

No change.

### Phase 3.3: Combat State (Week 3)

No change.

### Phase 3.4: Progression (Week 4)

Add backstory evolution:

```json
"backstory": {
  "summary": "...",
  "threads": [
    {"thread": "Zemsta na czarnoksiężniku", "status": "active", "progress": 1}
  ]
}
```

GM should be able to use backstory to build personal arcs.[^2]

### Phase 3.5: UI Integration (Week 5)

**Add backstory form during character creation:**

- Field 1: summary (50–100 words)
- Field 2: appearance (physical description)
- Field 3: personality (3–5 traits)
- Field 4: goals (1–3 goals)
- Field 5: fears (1–2 fears)
- Optional: upload character art placeholder

**GM opening preview:**
Before starting campaign, show player preview of GM opening line based on their backstory.

## ✅ Updated Success Criteria

```
[ ] Character creation → backstory form + validation
[ ] Turn 1 = GM opening monologue (not player intro)
[ ] GM opening uses backstory elements
[ ] Turn 2+ = GM responds to player (not player describes)
[ ] Dice rolls parsed
[ ] Combat initiative
[ ] XP spendable
[ ] Campaign summary window
```


## Key Architecture Decision

**Shift from:**

```
Player input → AI responds
```

**To:**

```
Turn 1: System → GM opening (auto-generated, no player input)
Turn 2+: Player → GM response → Player
       GM → Player response²
```

GM describes scene → player responds → GM narrates outcome → GM asks next question. This is standard TTRPG flow.[^4]

Update the spec file with these changes and start **Phase 3.1** with backstory + GM-first logic combined. That's your anchor for week 1.
<span style="display:none">[^10][^11][^12][^13][^14][^15][^6][^7][^8][^9]</span>

<div align="center">⁂</div>

[^1]: https://www.youtube.com/watch?v=6eTMYqQoqg0

[^2]: https://keith-baker.com/sz-prompts/

[^3]: https://docsbot.ai/prompts/creative/rpg-game-master-prompt

[^4]: https://arxiv.org/html/2503.20623v1

[^5]: https://dev.to/austin_amento_860aebb9f55/prompt-architecture-for-a-reliable-ai-dungeon-master-d99

[^6]: https://www.reddit.com/r/rpg/comments/broigt/what_are_your_character_creation_prompts/

[^7]: https://www.reddit.com/r/osr/comments/1jm5nox/i_feel_character_background_should_evolve_through/

[^8]: https://www.reddit.com/r/DnDBehindTheScreen/comments/6xbq3q/steal_my_idea_interactive_backstory_session/

[^9]: https://arxiv.org/pdf/2502.19519.pdf

[^10]: https://www.dndbeyond.com/forums/dungeons-dragons-discussion/dungeon-masters-only/110164-how-do-i-get-new-players-to-create-backstories-for

[^11]: https://www.reddit.com/r/rpg/comments/1kb6gwx/im_running_a_multiagent_ttrpg_simulation_with/

[^12]: https://www.youtube.com/watch?v=0j43ukEIFUM

[^13]: https://arxiv.org/html/2502.19519v2

[^14]: https://www.reddit.com/r/rpg/comments/163dws/my_character_backstory_template/

[^15]: https://forum.rpg.net/index.php

