# Playtest evaluation — Borys Strażnik, 2026-05-26

**Campaign:** 1105 "Playtest 2026-05-26 — Borys Strażnik" (now ended)
**Hero:** Borys Strażnik (id 1118), warrior L1, HP 12/12, no equipped weapon at start
**Driver:** Claude agent via MCP `submit_player_turn`, language: Polish
**Result:** 30 turns persisted (25 narrative + 5 skill_test) + 1 combat started

The playthrough cut short at ~30 turns rather than the 30–40 target because the playable path through MCP hit two hard stops: Azure OpenAI's content filter on combat phrasings (hard 502 errors), and a gap in the MCP tool surface around combat (no `resolve_attack` tool). The collected evidence is more than enough for an evaluation, so I'm publishing this rather than rerunning.

---

## What works

**Polish narration is genuinely good.** The GM writes atmospheric, varied prose with strong sensory detail ("Wilgotna mgła tłumi twoje kroki, mech chłonie dźwięki"; "słodkawy zapach rozkładu, a krople rosy zbierają się na Twojej twarzy"). It reads like a human GM trying their best, not a templated dungeon master. Description of the three bandits — three distinct silhouettes, each with their own weapon and posture — was specific and visualisable.

**Player contradictions get acknowledged.** When the GM described "brukowane uliczki miasta" on a forest scene (turn 3), I called it out on turn 5 and the GM cleanly corrected: "*Pod nogami masz wilgotne błoto … nigdzie nie ma śladu bruku ani ścian zabudowań. Wszędzie wokół ciągną się powalone pnie … to dzikie, zapomniane mokradła, nie cywilizowane miejsce.*" That's good ergonomics — players can repair drift in-fiction.

**Skill-test pre-routing fires correctly.** "Wyciągam wytrych" still triggers Lockpick correctly (from previous sessions), and the Dochodzenie / Skradanie / Medycyna skill tests fired on appropriate verbs without false positives.

**Recent fixes hold.** Reading actions don't trigger phantom Arkana (issue #134 fix). Skill test cards display correct DC + outcome label (Nat-1 detected properly). Wound effects code is live (didn't get below 25% HP to verify in this session, but the helper is exercised in unit tests).

---

## Findings — bugs and rough edges

### B1 — Skill-test narration ignores scene context (HIGH)

Turn 3 (failed Dochodzenie d20=2): GM narrated "*Mroczna mgła spowijała uliczki miasta, tłumiąc wszelkie dźwięki i ukrywając ślady … Kałuże krwi już dawno wsiąkły w bruk*" — for a character in a foggy swamp who was looking for footprints in mud. The skill-test narrator appears to generate prose from skill + outcome alone, ignoring the current scene context.

Turn 14 (failed Skradanie): narrated "*Gdy próbujesz przemknąć przez spowite cieniem **korytarze**…*" — character was outside in the swamp, not in any corridor.

The skill-test prose flow lives in `api/turns.py::resolve_skill_test_endpoint` and uses a small standalone narrator call (`build_skill_result_context` → LLM). It almost certainly isn't being passed the current campaign scene state. Fix: include 1-2 sentences of current-scene context in the narrator prompt.

### B2 — GM hallucinates inventory items the player never grabbed (HIGH)

Turn 7 I asked "Sprawdzam co mam przy sobie" and the GM volunteered: "*natrafiają tylko na jeden konkretny przedmiot: to ten sam klucz z symbolem drzewa, który właśnie podniosłeś z błota.*" I had **not** picked up any key — there was no prior action involving a key.

Worse: that ghost item now lives in `character_inventory` as `Klucz z symbolem drzewa` (item_key `__narrative__`). The grant-item path fires from the GM's JSON `grant_item` field regardless of whether the player intended to take anything. The LLM is treating "find the key" as part of the opening scene and granting it preemptively.

There are two failure modes here:
1. The GM "answer-by-creation" — when asked an open question, it invents details that satisfy the question.
2. Those inventions get auto-persisted via `grant_item` with no player confirmation.

Fix candidates: (a) require an explicit player declaration ("biorę X") before `grant_item` fires — there is already a system-prompt rule to this effect (line 415 of `system_prompt.txt`), so this is a compliance issue, not a missing rule; (b) gate `grant_item` on a heuristic — only honor it when the player's text in the same turn contains a take/grab verb.

### B3 — Concurrent or duplicate sessions on the same campaign (MEDIUM)

Listing `campaign_turns` for 1105 shows several turns I never submitted (turn 4, 6, 8, 10, 15, 20, 24, 25, 27), interleaved with my MCP submissions. Examples of foreign user_text:
- T4: "Rozglądam się wokół - gdzie się znajduję i co widzę? Jaki je…"
- T20: "Skoro mnie wykrył, prostuję się i krzyczę pewnym głosem: 'St…"
- T27: "Robię unik przed atakiem bandyty, po czym uderzam pięścią w …"

The campaign was pinned to my MCP session and I created it fresh. Either (a) the user was also driving the same campaign from the web UI in parallel (most likely), or (b) there's an unintended replay/auto-narrate loop. Either way, *there is no per-session lock or warning when two clients drive one campaign*. Multi-player isn't a feature yet (issue #118 blocked), so concurrent writes to one campaign should be either rejected or flagged.

### B4 — Character silently deactivated mid-playtest (HIGH)

After turn 30, my next MCP call returned 404. Direct DB read showed Borys with `is_active=0` and `campaign_id=NULL` — even though the campaign was still `active` and Borys had not been killed. The `is_active=0` flag is what gates `get_character_or_404`.

I have no evidence of *what* deactivated him. Possibilities:
- The concurrent session in B3 did a "new hero" action that orphaned this one
- Some lifecycle handler triggered on a specific narrative event
- Race condition with the campaign-creation flow

Whatever the cause, **an active campaign with an `is_active=0` owner is a broken state** — the player can't take turns, can't see anything, can't recover without DB surgery. The system should either keep `is_active=1` invariant for in-campaign heroes or surface a clearer error than 404.

### B5 — Azure OpenAI content filter rejects normal RPG combat phrasing (HIGH)

Three of my combat actions hit `HTTP 502 Bad Gateway` (which surfaces as a generic MCP error). Backend logs show:

```
"content_filter_result":{"violence":{"filtered":true,"severity":"medium"}}
```

Triggers I saw:
- "atakuję go z ukrycia"
- "zacisnąć chwyt na jego szyi tak, by stracił przytomność"
- "rzucam się na niego z tasakiem"

The first one in particular ("attack from cover") is *baseline* tabletop RPG vocabulary. Players will hit this constantly. Two paths to fix:
1. **Provider:** Azure offers a content-filter severity slider per-deployment — bump from "medium" to "high" so only the worst gets blocked.
2. **Application:** Catch the `400 content_filter` from the provider, surface it as a soft error ("Zmień opis akcji"), don't 502 the whole turn.

The 502 path is the worst case — player loses their turn and has no idea why.

### B6 — Round counter renders as "?" in combat banner (LOW)

The combat-start narrative ended with:
```
⚔️ WALKA AKTYWNA
Twoje HP: 16/16 | Strefa: engaged
Żywi wrogowie:
  - Bandyta: 12HP [engaged]
Runda: ? | Tura: bandit_01
```

`active_combat.round` is 1 in the DB, so the rendering layer is dropping the value somewhere. Cosmetic but reads as a bug.

### B7 — HP shown in combat banner ≠ HP in sheet (MEDIUM)

Banner said `Twoje HP: 16/16`; Borys's sheet has `max_hp: 12`, `current_hp: 12`. Either combat is recalculating HP from a different formula, or there's a +4 modifier I'm not seeing. The HP/wound calculations all key off the sheet — if combat uses a separate value, threshold-based effects (wounds, low-HP narrative) will desync.

### B8 — Picking up enemy weapons doesn't equip them as weapons (MEDIUM)

After defeating bandit 1, "Zabieram mu tasak — mam teraz broń." landed in `character_inventory` as:
```
Tasak bandyty | item_key='__narrative__' | weapon_key=NULL
```

This is a narrative item, not a usable weapon. The combat engine reads `weapon_key` to resolve attacks; a `__narrative__` row falls back to unarmed. The intended path is `_grant_narrative_weapon()` (which creates a pending `game_config_weapons` row and sets `weapon_key`), but it only fires from specific LLM tags.

Net effect for the player: looting weapons from combat feels good narratively but does nothing mechanically. Either narrative-only items should not be described as "broń", or grab-a-weapon should route to `_grant_narrative_weapon` automatically.

### B9 — `no such column: gl.enclosed` SQL warning (LOW)

Backend logs `can_flee_error: no such column: gl.enclosed`. Some query in the flee-check path expects a `game_locations.enclosed` column that doesn't exist. The warning is non-fatal (`can_flee` falls open) but it spams logs and points to a real schema drift.

### B10 — MCP has no combat-attack tool (FEATURE GAP)

After combat starts via narrative tag, my MCP options are:
- `submit_player_turn` — but this goes to `/api/campaigns/{id}/turns`, which doesn't resolve combat
- `change_player_zone` — only changes zone, doesn't attack
- `flee_from_combat` — only flees

There's no `mcp__ai-gm__resolve_attack`. So an AI agent driving the game through MCP can *start* combat (the LLM emits `[COMBAT_START:bandit]`), can *flee* combat, but cannot *fight*. The player UI gets around this by calling `/combat/resolve-attack` directly, but MCP cannot.

If MCP is going to be a first-class agent surface, it needs an attack tool. Even better: have `submit_player_turn` auto-detect attack intents during active combat and route them to the combat API.

---

## Severity summary

| ID | Severity | Title |
|---|---|---|
| B1 | HIGH | Skill-test narration ignores scene context |
| B2 | HIGH | GM hallucinates / auto-grants inventory items |
| B4 | HIGH | Character silently deactivated mid-playtest |
| B5 | HIGH | Azure content filter 502s on baseline RPG vocabulary |
| B3 | MEDIUM | No per-session lock on a campaign |
| B7 | MEDIUM | Combat-banner HP doesn't match sheet HP |
| B8 | MEDIUM | Looted weapons not equippable |
| B6 | LOW | Round counter "?" in combat banner |
| B9 | LOW | `gl.enclosed` SQL warning |
| B10 | FEATURE | No combat-attack MCP tool |

## Recommended next bites

1. **B1 + B2** are the player-facing immersion killers. B1 is a 10-line context injection in `resolve_skill_test_endpoint`. B2 is a system-prompt compliance check or a heuristic gate on `grant_item` — both small. Both will visibly improve playtest quality immediately.
2. **B5** is the showstopper — anyone playing a fantasy RPG will hit it within a few minutes. Try raising the Azure filter severity to "high" first (one config flag), and only if that's not enough, add provider-side error handling.
3. **B4** needs a repro before fixing — search recent code for any path that toggles `characters.is_active`.
4. **B10** unblocks MCP-driven autotests of combat (related: issue #22).
