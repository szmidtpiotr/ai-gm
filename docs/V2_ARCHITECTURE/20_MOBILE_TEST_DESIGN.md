# AIGM Mobile Test Design

**Last updated:** 2026-05-24
**Status:** Design approved — skill implementation in progress

---

## How the skill works

`/mobile-game-test` is a **Claude Code conversational skill** (same pattern as `/game-design`).

**Flow:**
1. User types `/mobile-game-test`
2. Claude presents the scenario menu **in the conversation** as a markdown table
3. Claude asks: *"What would you like to test?"*
4. User replies with IDs or a suite name (e.g. `smoke`, `B1 C2`, `warrior`)
5. Claude runs the corresponding Python test script(s) via Bash on the Claude VM
6. Claude streams output and formats the final summary in the conversation

**There is no Python menu UI.** The menu lives in the Claude conversation. The Python scripts only handle test execution.

---

## To add a new scenario

Tell Claude: *"Add scenario X to the mobile test"*

Claude will:
1. Add the entry to `scenarios.yaml` (source of truth for IDs, scripts, descriptions)
2. Create the script at `/home/claude/.claude/skills/mobile-game-test/scripts/scenarios/<id>_<name>.py`
3. Add it to the relevant suite(s)

The skill's menu is generated from the tables in this document — so also update this doc.

---

## Pre-built Suites

| Suite | Scenarios | Estimated time | Purpose |
|-------|-----------|----------------|---------|
| `smoke` | A1, A2, B1, C1 | ~5 min | Quick pass/fail — is the game broken? |
| `warrior` | A1, B1, B3, B5, C1, C2, E1 | ~15 min | Full warrior flow with loot + inventory check |
| `scholar` | A1, D1, D2, D3 | ~12 min | Scholar archetype + mana + miscast |
| `combat` | B1, B2, B3, B4, B5 | ~20 min | All combat variants |
| `full` | All scenarios | ~60 min | Complete regression |

---

## Testable Scenarios

### Group A — Core Loop Integrity
*Tests whether the basic gameplay loop is coherent from the player's perspective.*

| ID | Name | What it verifies | Weak 5C component |
|----|------|-----------------|-------------------|
| A1 | Hero Creation (all archetypes) | Wizard steps 1–4, archetype gating, stat generation, landing on campaigns-screen | Clarity |
| A2 | First Turn Narrative | GM responds to first exploration turn, screen stays on game-screen, location assigned | Clarity |
| A3 | Skill Check Trigger | Keyword in message triggers pre-LLM scanner, auto-roll UI fires, result feeds back to GM | Response |

### Group B — Combat System
*The most complex system with the most failure modes.*

| ID | Name | What it verifies | Weak 5C component |
|----|------|-----------------|-------------------|
| B1 | Basic Combat Loop | Round counter, attack resolution, enemy turns, `[COMBAT_END]` detected, `Zwycięstwo!` overlay | Response |
| B2 | Zone Change | `out_of_range` block when melee from wrong zone, Zbliż się button, zone-change endpoint | Clarity |
| B3 | Health Potion in Combat | Potion consumed from inventory, HP restored, `character_inventory` row decremented | Satisfaction |
| B4 | Death & Resurrection | Let hero die (no potions), death screen visible, resurrect button, HP reset to max | Fit |
| B5 | Combat → Loot Drop | Enemy dies, loot overlay appears BEFORE combat-end overlay, claim → DB `source='loot'` | Satisfaction |
| B-warrior | Full Warrior Flow (legacy) | `test_warrior_full.py` — 7 exploration turns + combat + loot + inventory hallucination check | — |

### Group C — Inventory & Items
*Catches hallucination bugs: GM narrates item found but it was never created in DB.*

| ID | Name | What it verifies | Weak 5C component |
|----|------|-----------------|-------------------|
| C1 | Start Inventory | Starting items present in DB with `source='start'`, correct slots | Clarity |
| C2 | Loot Hallucination Check | Items claimed via loot overlay match DB rows with `source='loot'` — no phantom grants | Satisfaction |
| C3 | Pending Weapons Review | GM narrates new weapon found → `game_config_weapons` has `pending_review=1` row | — |

### Group D — Scholar Magic
*Isolated archetype testing — only runs with a Scholar hero.*

| ID | Name | What it verifies | Weak 5C component |
|----|------|-----------------|-------------------|
| D1 | Mana Consumption | Cast 2 spells in combat, `current_mana` in sheet_json decremented correctly after each | Response |
| D2 | Miscast (Nat 1) | Force or wait for Nat 1, verify stun/self-damage penalty applied at correct tier | Satisfaction |
| D3 | Mana Lock | Cast until 0 mana, verify further spells blocked in combat UI | Clarity |

### Group E — Location & World
*Tests the canonical location fix and hex state.*

| ID | Name | What it verifies | Weak 5C component |
|----|------|-----------------|-------------------|
| E1 | No New Start Locations | Create campaign, verify no `start_N` entry created in `game_locations` | — |
| E2 | Hex Movement | 3 exploration turns, check `session_location_hexes` updates in DB, fog-of-war in admin map | Motivation |

### Group F — Progression
*Long-path tests. Expensive to run, only in the `full` suite.*

| ID | Name | What it verifies | Weak 5C component |
|----|------|-----------------|-------------------|
| F1 | XP from Skill Check | Trigger skill check, pass it, verify XP entry created, total updated | Motivation |
| F2 | Level Up | Fight enough enemies, verify `level` incremented in sheet_json, HP recalculated | Satisfaction |
| F3 | Dungeon Run | Enter dungeon, advance 3 rooms, reach boss encounter, verify cooldown set | Fit |

---

## Test Script Contract

Each scenario script lives at:
```
/home/claude/.claude/skills/mobile-game-test/scripts/scenarios/<id>_<name>.py
```

It must:
- Import `MobileSession` from `aigm_mobile`
- Print one JSON line to stdout on completion:
```json
{
  "scenario": "B1",
  "passed": true,
  "errors": [],
  "warnings": ["Explore turn 2 timed out"],
  "data": { "hero_id": 1096, "rounds": 8, "dice_rolls": 3 },
  "duration_s": 142
}
```
- Exit code 0 on pass, 1 on fail

---

## Known Constraints

- Phone must be connected via ADB before any test: `adb -s 192.168.1.179:42569 shell true`
- Appium must be running: `systemctl --user is-active appium.service`
- Scholar scenarios require a fresh Scholar hero — cannot reuse a Warrior session
- Group F tests take 15–30 min each and require a fresh level 1 hero
- `keep_campaign: true` scenarios leave the campaign alive at `https://aigm-dev.studio-colorbox.com/` for manual inspection
