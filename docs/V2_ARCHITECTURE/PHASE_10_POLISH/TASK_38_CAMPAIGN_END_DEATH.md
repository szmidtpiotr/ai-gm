# TASK 38 — Campaign End: Death and Victory

## Overview

Two ways a campaign ends: the character dies (all death saves exhausted) or the story reaches a scripted ending (campaign plan victory condition). Both transitions have dedicated screens. Post-end options let the player carry their story forward into a new character or a new world.

---

## Death Flow

### Trigger

Three failed death saves → `campaign_status = "ended"`, `end_type = "death"`.

### Death Screen

Full-screen overlay (replaces both panels). Dark background, candle or skull aesthetic.

```
┌─────────────────────────────────────────────────┐
│                                                  │
│                    ✝                             │
│                                                  │
│          Aldric z Middenheim                     │
│                                                  │
│  "Przyszedł do Middenportu szukając fortuny.     │
│   Znalazł ciemność — i coś, co go połknęło."    │
│                                                  │
│  ─────────────────────────────────────────────  │
│  Poziom osiągnięty: 3                            │
│  Tur przeżytych: 87                              │
│  Więzi: Siostra w Altdorfie                      │
│  ─────────────────────────────────────────────  │
│  Kluczowe momenty:                               │
│  • Pokonałeś gobliniego wodza w Tura 34          │
│  • Odkryłeś spisek kupców w Turze 61             │
│  • Twoja śmierć: zamknięta piwnica, bez wyjścia  │
│  ─────────────────────────────────────────────  │
│                                                  │
│  [Nowa Przygoda — ten sam świat]                 │
│  [Nowy Świat — zacznij od nowa]                  │
│                                                  │
└─────────────────────────────────────────────────┘
```

### Epitaph Generation

The 2-sentence epitaph is LLM-generated immediately when death is confirmed.

```
Napisz po polsku epitafium dla postaci gracza — 2 zdania.
Ton: poważny, grim dark, bez patosu.
Podsumuj kim była ta postać i jak zginęła.
Używaj tylko faktów podanych poniżej.

POSTAĆ:
  Imię: {character.name}
  Archetype: {archetype}
  Poziom: {level}
  Więzi: {bonds}
  Słabości: {weaknesses}
  Ostatnia lokacja: {last_location_name}
  Ostatnia tura (co się stało): {last_narrator_output}
```

Epitaph is stored in `campaign_endings` table alongside `end_type`, `end_at`, and the stats summary.

### Death Screen Stats

| Field | Source |
|---|---|
| Poziom osiągnięty | `character.level` |
| Tur przeżytych | `COUNT(campaign_turns)` |
| Więzi | `character.bonds` |
| Kluczowe momenty | `scene_log` entries tagged `is_key_moment=true` |

"Kluczowe momenty" come from the `scene_log` table. Key moments are auto-tagged when:
- Player defeats a named enemy (boss/unique NPC)
- Player completes a campaign beat
- Player dies

If no moments are tagged yet (short campaign), fall back to the last 3 narrator outputs.

---

## Post-Death Options

**CONFIRMED post-death options (all 3 available):**
- Restart campaign — hero survives, campaign resets to turn 1 (this campaign's XP/loot lost, prior campaigns' XP permanent)
- Accept death — hero marked 'fallen', player creates new hero, fallen hero becomes world lore/NPC
- Retire — hero voluntarily exits at any time, becomes world legend/NPC

### Option A: Nowa Przygoda — Ten Sam Świat

- New character creation (archetype, name, appearance)
- Same world: all existing DB locations, NPCs, and factions carry over
- New campaign linked to the same `world_id`
- Brief intro text: "Ktoś nowy przybywa do świata, który pochłonął {previous_character_name}..."
- Previous character's story is accessible via the "Historia" button in the new campaign

### Option B: Nowy Świat — Zacznij od Nowa

- New character creation
- Fresh world state (new `world_id`)
- No inherited locations, NPCs, or factions
- Clean slate

Both options go to campaign creation flow after character creation completes.

---

## Victory Flow

### Trigger

When the World State Machine resolves an action that completes the final campaign beat, the GM prompt includes a `[CAMPAIGN_END:ending_id]` tag in its output. The backend parser detects this tag and:

1. Sets `campaign_status = "ended"`, `end_type = "victory"`, `ending_id = {id}`
2. Generates the victory narration (longer, 4 sentences — final climax narration)
3. Returns the victory screen trigger in the turn response

### Victory Screen

Full-screen overlay, lighter than death screen (dark but not pitch-black, amber/gold accents).

```
┌─────────────────────────────────────────────────┐
│                                                  │
│          ★  KONIEC KAMPANII  ★                   │
│                                                  │
│          {ending_title}                          │
│                                                  │
│  {ending_summary — 2-3 sentences from DB}        │
│                                                  │
│  ─────────────────────────────────────────────  │
│  Aldric z Middenheim                             │
│  Poziom 5  •  Tur 142  •  {ending_id: "Zdrajca  │
│  ujawniony"}                                     │
│  ─────────────────────────────────────────────  │
│                                                  │
│  [Eksploruj dalej — tryb wolny]                  │
│  [Nowa Kampania — ten sam świat]                 │
│  [Nowy Świat]                                    │
│                                                  │
└─────────────────────────────────────────────────┘
```

The `ending_title` and `ending_summary` come from the `campaign_endings_catalog` DB table (authored by the campaign creator, not LLM-generated).

### Post-Victory Options

| Option | Description |
|---|---|
| Eksploruj dalej | Campaign continues in "free mode" — no plan, no beats, just world exploration. GM responds to player actions without campaign objectives. |
| Nowa Kampania | Create a new campaign in the same world (new plan, new objectives). Character may optionally carry over or start fresh. |
| Nowy Świat | Complete fresh start. |

---

## Campaign Reset (Admin/Dev Only)

`POST /api/campaigns/{id}/reset` — admin token required.

- Resets `campaign_status` to `active`
- Clears all turns
- Resets campaign plan beat progress
- Does NOT delete character (to preserve created characters)
- Does NOT delete world state (locations, NPCs remain)

This endpoint is not shown in the player UI. It is only accessible from the admin panel. The purpose is dev testing and admin corrections. Players cannot reset their own campaigns.

---

## Testing Requirements

1. **Death trigger**: Exhaust all 3 death save failures. Verify `campaign_status = "ended"` and `end_type = "death"` in DB.
2. **Death screen render**: Verify death screen overlay appears with character name, epitaph, stats.
3. **Epitaph generation**: Verify epitaph is 2 sentences, in Polish, mentions the character's last location.
4. **Victory trigger**: Simulate a turn that triggers `[CAMPAIGN_END:ending_id]`. Verify campaign status set and victory screen displayed.
5. **Free mode after victory**: Click "Eksploruj dalej". Submit a turn. Verify turn processes normally without campaign beat checks.
6. **New adventure same world**: Click "Nowa Przygoda — ten sam świat". Verify new character creation flow, and that existing locations are available in the new campaign.
7. **Reset admin only**: Attempt campaign reset without admin token. Verify 403 response.
8. **Key moments**: Complete a campaign beat. Verify it appears in `scene_log` with `is_key_moment=true`.
