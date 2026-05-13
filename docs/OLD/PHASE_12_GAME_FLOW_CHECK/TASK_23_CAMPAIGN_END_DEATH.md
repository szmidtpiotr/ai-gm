# TASK 23 — Campaign End & Death Screen

**Status:** ❓ Needs Design
**Blocking:** Design discussion needed; N2/N3 from Task 14 must be resolved first
**Depends on:** Task 14 (Death Saves — death triggers campaign end)

---

## What Needs to Be Designed

1. **Death screen content** — Current tombstone is AI-generated text. What else should it show? Time survived (turns/sessions), character level reached, notable events from scene_log, bonds and weaknesses summary?
2. **Post-death options** — Three possible paths: (a) restart same campaign with new character, (b) continue same world with new character (existing locations/NPCs remembered), (c) start completely fresh. Which should be offered?
3. **Campaign completion (non-death)** — When player reaches an ending (via campaign plan), what happens? Victory screen? Can they keep exploring the world post-ending? Can they start a new campaign in the same world?
4. **Campaign reset** — `POST /campaigns/{id}/reset` currently clears turns but keeps campaign + character. Is this intended as a "retry" for development/testing, or a player feature? Should it be exposed to players at all?
5. **Legacy system** — Does a dead character leave anything? Items dropped in world at death location? A gravestone NPC? A reputation with factions? Entry in a "Hall of the Fallen" admin view?
6. **Death trigger specifics** — Currently triggered by HTTP 410 from turns endpoint OR `campaign.status = ended`. Death save failures → `end_solo_campaign_on_death()`. This chain needs verification against the new escalating DC system (Task 14).
7. **Victory trigger** — How does the system know the player has reached an ending? GM emits a `[CAMPAIGN_END:ending_id]` tag? Admin manually marks complete? Player-triggered?

## Current State

- `death_saves` → `end_solo_campaign_on_death()` service exists
- `GET /campaigns/{id}/death-summary` returns tombstone message
- Death screen (`death_screen.js`) shows tombstone overlay
- `POST /campaigns/{id}/reset` clears turns, keeps campaign + characters
- Campaign status can be `active` or `ended`

---

*This file will be filled with full specification after the design discussion.*
