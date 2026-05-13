# TASK 28 — NPC Dialogue Narration

**Status:** ❌ Not Started

## Overview

When the player initiates dialogue with an NPC, the narrator voices that NPC in first person. The NPC's words come entirely from the LLM — but constrained by their personality, their knowledge set, and any mandatory disclosures triggered by the player's input.

The system decides what the NPC knows and is willing to share. The LLM decides how they say it.

---

## Input Schema

```python
class NPCDialogueRequest:
    npc_id:             str                  # DB id
    npc_name:           str                  # display name
    personality_prompt: str                  # from DB npc.personality_prompt
    knowledge_set:      list[str]            # topics/facts this NPC knows (from DB)
    must_reveal_info:   str | None           # if keyword triggered, what must be revealed
    is_secret:          bool                 # whether must_reveal_info is reluctantly shared
    player_input:       str                  # what the player said or asked
    tone_context:       str                  # always "WFRP grim dark"
    recent_exchanges:   list[DialogueTurn]   # last N turns this session (max 5)
```

```python
class DialogueTurn:
    speaker:  str   # "Gracz" or npc_name
    text:     str
```

---

## LLM Prompt (NPC Dialogue)

```
Wciel się w postać {npc_name}.
Osobowość: {personality_prompt}
Styl: {tone_context}

Wiesz tylko to, co jest poniżej. Nie odpowiadaj na pytania spoza tej wiedzy.
WIEDZA POSTACI:
{knowledge_set — bulleted list}

{if must_reveal_info:}
OBOWIĄZKOWO WSPOMNIJ: {must_reveal_info}
Włącz tę informację naturalnie w swoją odpowiedź.
{/if}

{if is_secret:}
UJAWNIJ TĘ INFORMACJĘ NIECHĘTNIE. Zachowuj się, jakbyś wolał/a zachować ją dla siebie — może po dłuższym nacisku, może ze wstydem, może ze strachem.
{/if}

OSTATNIA ROZMOWA:
{recent_exchanges — formatted as: Gracz: "..." / {npc_name}: "..."}

Gracz mówi: "{player_input}"

Odpowiedz w pierwszej osobie, jako {npc_name}. Maksymalnie 4 zdania.
```

---

## Knowledge Enforcement

The NPC's `knowledge_set` defines what they can speak to. If the player asks about something outside this set, the NPC should deflect, express ignorance, or change the subject — in character.

The system does NOT inject a hard "you cannot answer" override. Instead, the personality prompt and knowledge_set together guide the LLM. If the LLM still answers beyond its knowledge, post-processing can be added later (Phase 10 polish). For now: trust the prompt + monitor.

---

## Keyword Triggers and `must_reveal_info`

When a player's input matches a keyword associated with the NPC (see NPC DB schema), the system populates `must_reveal_info`. Example:

```
Player input: "Gdzie jest skrzynka z dokumentami?"
NPC keyword trigger: "skrzynka" → must_reveal_info = "Skrzynka jest w skrytce za portretem w jadalni."
```

The narrator must weave this fact into the NPC's response. It cannot omit it. The LLM is instructed to include it naturally — not drop it bluntly.

---

## Secret Information (`is_secret = true`)

When `is_secret = true`, the LLM is additionally instructed to reveal the information reluctantly. The tone changes:

- NPC pauses, hesitates, looks around
- Phrases like "nie powinienem/powinnam ci tego mówić..." or "tylko między nami..."
- May require two exchanges before fully revealing (though the reveal still happens in this single response per the `must_reveal_info` contract)

Example personality interaction: a cowardly innkeeper revealing a bandit hideout behaves differently from a stoic blacksmith revealing forge secrets. Both are reluctant, but the texture is different. The personality_prompt handles this distinction.

---

## NPC Memory

### Within Session

The `recent_exchanges` list (max 5 dialogue turns) is injected directly into the prompt. The NPC "remembers" what was said in this conversation.

If the player asks "You mentioned the blacksmith earlier — where is he?", the NPC can refer back to what they said, as long as it's within the last 5 exchanges.

### Between Sessions

There is no cross-session NPC memory in V2. When a session ends:

- `recent_exchanges` is discarded
- The NPC's "memory" resets to only: `personality_prompt` + `knowledge_set` + `keyword_triggers`

If a player revisits an NPC across sessions and references a previous conversation, the NPC will not remember the details. This is a known limitation. Players may find it immersion-breaking if they rely heavily on NPC conversations. Mitigations:

1. The player's `/mem` command (TASK_36) can recall what the NPC said — the player remembers even if the NPC doesn't.
2. NPCs may have persistent facts in `knowledge_set` that always apply ("I know about the hidden cellar"), even if they don't remember the specific exchange.

---

## NPC Death Handling

If the player asks about or tries to speak with a dead NPC:

1. The World State Machine rejects the DIALOGUE action and returns `npc_dead=true`
2. Other NPCs who knew the deceased may reference the death differently, based on their relationship:
   - `relationship: ally` → grief, anger, suspicion about who did it
   - `relationship: enemy` → cold, dismissive, may hint at satisfaction
   - `relationship: neutral` → matter-of-fact, perhaps uncomfortable
3. The relationship data comes from the NPC DB schema (`npc_relationships` field — if not implemented yet, default to neutral)

The system injects a `deceased_npc_context` field into the dialogue request when relevant:

```
UWAGA: {deceased_npc_name} jest martwy/a.
Twój stosunek do tej postaci: {relationship}
Jeśli gracz pyta o {deceased_npc_name}, zareaguj zgodnie z tym stosunkiem.
```

---

## Length and Tone Constraints

- Maximum 4 sentences per NPC response
- Tone: WFRP grim dark — NPCs are not cheerful, not exposition-machines, not modern in speech
- NPCs use period-appropriate language (no slang, no anachronisms)
- Polish throughout — no English phrases in NPC speech

---

## Testing Requirements

1. **In-character**: Feed a gruff blacksmith personality with a question about flowers. Verify response is dismissive/gruff, not helpful.
2. **must_reveal_info**: Provide a must_reveal_info string. Verify it appears verbatim or paraphrased in the output.
3. **is_secret reluctance**: Compare two outputs — one with `is_secret=false`, one with `is_secret=true`. Verify the second includes hedging/reluctance language (keyword list: "nie powinienem", "między nami", "nikomu nie mów", "wolałbym", "muszę ci powiedzieć").
4. **Session memory**: Provide 3 previous exchanges in `recent_exchanges`. Ask a question that references them. Verify the NPC's response is consistent with what was said.
5. **Knowledge boundary**: Ask about a topic not in knowledge_set. Verify NPC deflects rather than inventing an answer.
6. **Length**: All responses <= 4 sentences.
