# Phase 12 — Implementation Master Summary

> This document is the single source of truth for implementation status.
> Update the Status column as work progresses. Each task has a dedicated file with full specification.

---

## Status Legend

| Icon | Meaning |
|------|---------|
| ❓ | Needs design decision before implementation can start |
| ❌ | Not started — decision made, ready to implement |
| 🔶 | Partially built — exists in code but incomplete or incorrect |
| ✅ | Done and tested |

---

## Implementation Table

| # | Task | Status | Blocking Decisions | File |
|---|------|--------|--------------------|------|
| 01 | HP & Mana Formulas | ❓ | N1: confirm Warrior/Scholar base HP values | [TASK_01](TASK_01_HP_MANA_FORMULAS.md) |
| 02 | Character Creation Wizard | 🔶 | None — spec complete | [TASK_02](TASK_02_CHARACTER_CREATION_WIZARD.md) |
| 03 | Opening Scene Generation | ❌ | None — spec complete | [TASK_03](TASK_03_OPENING_SCENE.md) |
| 04 | Campaign Plan v2 Schema | ❌ | None — spec complete | [TASK_04](TASK_04_CAMPAIGN_PLAN_V2.md) |
| 05 | Campaign Plan Generation | ❌ | Depends on Task 02, 04 | [TASK_05](TASK_05_CAMPAIGN_PLAN_GENERATION.md) |
| 06 | Campaign Deviation Handling | ❌ | None — spec complete | [TASK_06](TASK_06_CAMPAIGN_DEVIATION_HANDLING.md) |
| 07 | Admin Campaign Workshop + Ideas Bank | ❌ | None — spec complete | [TASK_07](TASK_07_ADMIN_CAMPAIGN_WORKSHOP.md) |
| 08 | Skill Test System | ❌ | None — spec complete | [TASK_08](TASK_08_SKILL_TEST_SYSTEM.md) |
| 09 | Location System (badge + safe_for_rest) | 🔶 | None — spec complete | [TASK_09](TASK_09_LOCATION_SYSTEM.md) |
| 10 | Data Tables Source of Truth | ❌ | None — spec complete | [TASK_10](TASK_10_DATA_TABLES_SOURCE_OF_TRUTH.md) |
| 11 | Combat Entry Cleanup | 🔶 | None — spec complete | [TASK_11](TASK_11_COMBAT_ENTRY.md) |
| 12 | Combat Round Flow (enemy auto-turn) | 🔶 | N6: auto-fire architecture decision | [TASK_12](TASK_12_COMBAT_ROUND_FLOW.md) |
| 13 | Combat Narrative (LLM flavoring) | ❌ | None — spec complete | [TASK_13](TASK_13_COMBAT_NARRATIVE.md) |
| 14 | Death Save System | 🔶 | N2: CON modifier or no modifier; N3: mid-combat heal reset | [TASK_14](TASK_14_DEATH_SAVES.md) |
| 15 | Flee Mechanic | 🔶 | None — spec complete | [TASK_15](TASK_15_FLEE_MECHANIC.md) |
| 16 | Healing System (items, rest, spells) | ❓ | N4: Mend Wounds cost (2 or 3 Mana); N5: Scholar double-dip restriction | [TASK_16](TASK_16_HEALING_SYSTEM.md) |
| 17 | Wound Narrative Labels | ❌ | Depends on Task 01 (HP formula) | [TASK_17](TASK_17_WOUND_LABELS.md) |
| 18 | Loot System (location-tied) | 🔶 | None — spec complete | [TASK_18](TASK_18_LOOT_SYSTEM.md) |
| 19 | Command Palette (/help) | ❌ | None — spec complete | [TASK_19](TASK_19_COMMAND_PALETTE.md) |
| 20 | Inventory & Shop | ❓ | Full design still needed | [TASK_20](TASK_20_INVENTORY_SHOP.md) |
| 21 | XP & Character Progression | ❓ | Full design still needed | [TASK_21](TASK_21_XP_PROGRESSION.md) |
| 22 | Memory & History | ❓ | Full design still needed | [TASK_22](TASK_22_MEMORY_HISTORY.md) |
| 23 | Campaign End & Death Screen | ❓ | Full design still needed | [TASK_23](TASK_23_CAMPAIGN_END_DEATH.md) |
| 24 | Admin & Player Settings | ❓ | Full design still needed | [TASK_24](TASK_24_ADMIN_SETTINGS.md) |
| 25 | Auth & Onboarding | ❓ | Full design still needed | [TASK_25](TASK_25_AUTH_ONBOARDING.md) |

---

## Open Decisions (Blocking)

These must be resolved before the dependent tasks can start:

| # | Question | Affects | Recommendation |
|---|---------|---------|----------------|
| N1 | Warrior base HP = 10, Scholar base HP = 6? | Task 01, 17 | Yes — creates meaningful archetype asymmetry |
| N2 | Death saves: d20 + CON modifier OR d20 no modifier? | Task 14 | Use CON modifier — consistent with system, makes CON meaningful |
| N3 | Does death save counter reset if healed back from 0 HP mid-combat? | Task 14 | No — counter is per-combat, not per-0HP-event |
| N4 | Mend Wounds Mana cost: 2 or 3? | Task 16 | Start at 2, test: if Scholar rarely dies raise to 3 |
| N5 | Can Scholar use Mend Wounds AND short rest in same rest period? | Task 16 | No double-dip — pick one per rest |
| N6 | Enemy turn auto-fire: backend resolves full round in one call, or frontend pings per enemy? | Task 12 | Backend resolves full round — simpler, no soft-lock risk |
| N7 | Deviation detection: [BRANCH_REQUIRED] tag (system-driven) or pure LLM judgment? | Task 06 | Tag system — LLM alone is unreliable for structural decisions |

---

## Implementation Notes

### Architecture Principles (Non-Negotiable)
- **Mechanics first, narration second.** Every dice roll and combat resolution is done by the strict mechanical system BEFORE the LLM is called to narrate. LLM receives the mechanical result as input and describes what happened. It never decides what happened.
- **System enforces world state, LLM describes it.** Location, loot availability, HP, Mana — all tracked in DB by backend. LLM never overrides these values.
- **DB is source of truth for world content.** GM/LLM queries DB first for Locations, NPCs, Enemies, Items. Creates only when not found. Stores new creations as `pending_review` for admin approval.

### Dependency Order (Suggested Implementation Sequence)
```
Task 01 (HP/Mana formulas)
  └─ Task 17 (Wound labels — needs HP formula)
  └─ Task 16 (Healing system — needs HP/Mana values)

Task 02 (Character wizard)
  └─ Task 03 (Opening scene — needs finalized character)
  └─ Task 05 (Campaign generation — needs bonds/weaknesses/predisposition)

Task 04 (Campaign plan schema)
  └─ Task 05 (Campaign generation — needs schema)
  └─ Task 06 (Deviation handling — needs schema)
  └─ Task 07 (Admin workshop — needs schema)

Task 09 (Location system — safe_for_rest)
  └─ Task 16 (Rest mechanics — needs safe_for_rest)
  └─ Task 18 (Loot — needs location tracking)

Task 10 (Data tables source of truth)
  └─ All world-content tasks depend on this pattern

Task 11 (Combat entry cleanup)
  └─ Task 12 (Combat round flow)
  └─ Task 13 (Combat narrative)
  └─ Task 14 (Death saves)
  └─ Task 15 (Flee)
```

---

## Complete Decision Log (D1–D35)

All decisions made during the Phase 12 design session, in order.

| # | Topic | Decision |
|---|-------|----------|
| D1 | Character creation — identity generation | Step 4: LLM/GM generates appearance + personality based on stats, background note, and skills. Player can edit before finalizing. |
| D2 | Character creation — bonds & weaknesses | GM generates bonds and weaknesses in Step 4. Visible to player AND fed into campaign plot generation. |
| D3 | Character creation — secret predisposition | GM generates a hidden "opposed archetype predisposition" (e.g., Warrior with latent magic). Stored in sheet_json.gm_only. NOT shown to player. Used as future quest hook. |
| D4 | Archetypes | Warrior + Scholar only. No expansion planned now. |
| D5 | Campaign scenario generation | GM (LLM agent) generates scenario automatically. Player does not configure it. Character background, bonds, weaknesses, secret predisposition are inputs. |
| D6 | Opening scene | There MUST be an opening scene after character creation. No blank chat. |
| D7 | GM role | Full TTRPG Game Master: storyteller, world simulator, referee, NPC controller. WFRP (gritty) + D&D (heroic). |
| D8 | Dice rolls — when | Roll popup for NON-COMBAT skill tests only. Triggers: (a) GM declares test, (b) player declares action requiring test. Combat rolls handled separately. |
| D9 | Skill test — counter-skill | Player skill action vs NPC counter-skill (e.g., Stealth vs Perception). Skill/counter-skill matrix — admin-configurable. |
| D10 | Skill test — activation | GM emits `[SKILL_TEST:skill_key:dc_or_opponent]` tag. System intercepts, triggers roll popup. Counter-skill resolved server-side. |
| D11 | Command palette | `/help` opens command palette. Admin sees all commands. Per-command toggle in admin panel for player visibility. |
| D12 | GM adaptation / campaign plan | GM adaptation is LLM-driven but Campaign Plan must be structured to help GM maintain coherence. |
| D13 | Turn pacing | Single player: always GM narrates → player responds. No waiting states. |
| D14 | Location — visibility | Player always sees current location as a persistent UI badge: `📍 Location Name`. |
| D15 | Location — system control | SYSTEM (not LLM) controls and validates location. Player cannot declare a location they are not in. |
| D16 | Loot — location-tied | Loot tied to combat location. Return to same location = can claim remaining. Move to different location = loot expires. |
| D17 | Campaign plan — structure | Every campaign has beginning + one or more possible endings. GM creates skeleton: opening scene + planned endings. GM builds branches during play. |
| D18 | Campaign plan — player deviation | Minor deviation → GM steers back gently. Major deviation (kills key NPC) → GM generates new branch. Both active. |
| D19 | Admin GM screen | Admin can view live campaign plan. New: LLM Agent for admin to discuss/edit campaign. Ideas Bank DB for saving premises/twists/NPCs. |
| D20 | Mechanics vs LLM | All dice mechanics resolved by STRICT MECHANICAL SYSTEM. LLM only narrates. Prevents hallucination of results. |
| D21 | Combat entry | Triggered by GM narrative OR player narrative declaring hostile action. No explicit `/atak` required. System detects via `[COMBAT_START]` tag. |
| D22 | Combat — enemy turn flow | Auto-fires after player turn. Full flow: GM narrative → ENEMY ATK (mechanical) → GM narrative → PLAYER TURN → repeat. No manual trigger. |
| D23 | Combat — initiative | Rolled ONCE at combat start for ALL participants. d20 + DEX modifier. Highest acts first. Order fixed for entire combat. |
| D24 | Combat — multiple enemies | All enemies act in initiative sequence. Player gets one action per round. |
| D25 | Combat — narrative | GM writes short narrative (1-2 sentences) alongside each mechanical action. Always flavored, never pure numbers. |
| D26 | Combat — fleeing | Fleeing = skill test. Player DEX vs highest enemy DEX (opposed roll). Success: escape. Fail: lose turn. |
| D27 | Combat — death at 0 HP | At 0 HP: death save roll triggered. Escalating DC per 0 HP hit in same combat. All saves exhausted → death. |
| D28 | Data tables as source of truth | GM/LLM queries DB FIRST before inventing. Priority: (1) DB lookup → use existing. (2) Not found → GM creates, stores as `pending_review`. Admin approves/rejects. |
| D29 | Auto-generated world entries | Every GM-invented Location/NPC/Enemy/Item saved to DB with `status = pending_review`. Admin review queue. Approved → permanent. |
| D30 | Wounds | Narrative labels only (HP thresholds: 76/51/26/11%). No stat penalties in v1. Option B (stat penalties) flagged for future. |
| D31 | Healing items | 2 tiers: Bandage (1d6, out-of-combat only) and Healing Potion (1d8+CON mod, in-combat). |
| D32 | Short rest | 1d6+CON mod HP + INT mod Mana (Scholar). Max 2 per long rest. Requires safe_for_rest location. Bandage can stack. |
| D33 | Long rest | Full HP + full Mana. Requires safe_for_rest location. Resets short rest counter and death save counter. |
| D34 | Scholar healing spell | "Mend Wounds": 2 Mana (starting value), heals 2d6+INT mod. Usable in combat. Short rest recovers INT mod Mana. |
| D35 | Death save specifics | DC ladder: 10/13/16/19 per 0 HP hit in same combat. CON modifier on roll (recommended). Counter resets after combat ends or on long rest. |

---

## Code Reference

### Backend API Surface (Player-Facing)

| Endpoint | Purpose |
|----------|---------|
| `POST /api/auth/login` | Login |
| `GET /api/campaigns` | List campaigns |
| `POST /api/campaigns` | Create campaign |
| `GET /api/campaigns/{id}` | Campaign details |
| `DELETE /api/campaigns/{id}` | Delete (cascade) |
| `POST /api/campaigns/{id}/reset` | Clear turns, keep campaign |
| `POST /api/campaigns/{id}/gm-plan` | Update GM plan |
| `POST /api/campaigns/{id}/gm-plan/generate-initial` | Generate initial plan |
| `POST /api/campaigns/{id}/gm-plan/advance-scene` | Advance scene |
| `GET /api/campaigns/{id}/characters` | List characters |
| `POST /api/campaigns/{id}/characters` | Create character |
| `GET /characters/{id}/sheet` | Get sheet |
| `PATCH /characters/{id}/sheet` | Update sheet |
| `POST /characters/{id}/generate-identity` | LLM identity draft |
| `POST /characters/{id}/finalize-sheet` | Confirm identity |
| `POST /characters/{id}/narrative-item` | GM grants plot item |
| `GET/POST /characters/{id}/xp` | XP balance & grant |
| `POST /characters/{id}/xp/spend-skill` | Spend XP on skill |
| `POST /characters/{id}/xp/spend-stat` | Spend XP on stat |
| `GET /characters/{id}/gold` | Gold balance |
| `POST /characters/{id}/gold` | Grant gold |
| `GET /api/campaigns/{id}/turns` | Turn history |
| `POST /api/campaigns/{id}/turns/stream` | SSE streaming (main gameplay) |
| `GET /api/campaigns/{id}/combat` | Combat status |
| `POST /api/campaigns/{id}/combat/start` | Start combat |
| `POST /api/campaigns/{id}/combat/resolve-attack` | Player attack |
| `POST /api/campaigns/{id}/combat/enemy-turn` | Enemy turn (to be removed, Task 12) |
| `POST /api/campaigns/{id}/combat/flee` | Flee |
| `POST /api/campaigns/{id}/combat/loot/claim` | Claim loot |
| `GET /api/campaigns/{id}/combat/turns` | Combat turn log |
| `GET /api/inventory/{char_id}` | Inventory |
| `POST /api/inventory/{char_id}/equip` | Equip item |
| `POST /api/inventory/{char_id}/use` | Use item |
| `DELETE /api/inventory/{char_id}/{inv_id}` | Delete item |
| `GET /api/shop/{npc_id}` | Shop inventory |
| `POST /api/shop/{npc_id}/buy` | Buy from shop |
| `POST /api/shop/{npc_id}/sell` | Sell to shop |
| `POST /api/campaigns/{id}/memory/ask` | Memory search |
| `POST /api/campaigns/{id}/helpme` | Help |
| `GET /api/mechanics/slash-commands` | Available commands |
| `POST /api/commands/execute` | Execute command |
| `POST /api/campaigns/{id}/history/summary` | Generate summary |
| `POST /api/campaigns/{id}/history/summary/ensure` | Ensure summary exists |
| `GET /api/campaigns/{id}/history/summary` | Get summary |
| `GET /api/campaigns/{id}/death-summary` | Death/tombstone summary |

### Database Tables (Key)

| Table | Purpose |
|-------|---------|
| `users` | Login credentials, is_admin flag |
| `campaigns` | Metadata, gm_plan_json, status, mode, owner_user_id |
| `characters` | sheet_json (stats, skills, inventory, identity), location, level |
| `campaign_turns` | All turns: user_text, assistant_text, route, turn_number |
| `active_combat` | Current combat state: combatants JSON, initiative, status |
| `combat_turns` | Log of each combat action |
| `campaign_ai_summaries` | Stored AI summaries (player/admin audience) |
| `character_xp_grants` | XP history per character |
| `game_sessions` | Links character↔campaign, current_location_id, session_flags |
| `game_locations` | Locations: key, label, description, parent_id, type, enemy_keys, npc_keys |
| `npc_definitions` | NPC keys, personality, shop inventory, is_shop, npc_type |
| `game_config_items` | Item catalog: type, effects, ac_bonus, allowed_classes, ai_generated, approved |
| `character_inventory` | Character inventory: equipped, slot, source |
| `game_config_skills` | Skill definitions |
| `game_config_stats` | Stat definitions |
| `game_config_weapons` | Weapon catalog |
| `game_config_enemies` | Enemy stat blocks: ac_base, hp, dex_modifier, tier, loot_table |
| `location_integrity_log` | Log of movement validations |

### Key Services

| Service | File | Responsibility |
|---------|------|----------------|
| Game engine | `app/services/game_engine.py` | Narrative turn pipeline: context → LLM → location → combat tag |
| Combat | `app/services/combat_service.py` | Combat state machine: init, attack, enemy turn, flee, victory |
| Character | `app/services/character_service.py` | Creation, stat rolling, identity generation, finalization |
| Loot | `app/services/loot_service.py` | Inventory: equip, use, grant loot post-combat |
| Shop | `app/services/shop_service.py` | NPC shops: browse, buy, sell |
| Death | `app/services/solo_death_service.py` | Death saves, campaign-end, tombstone |
| LLM | `app/services/llm_service.py` | LLM resolution: admin preset → env vars → user override |
| System prompt | `app/system_prompt_loader.py` | Loads `backend/prompts/system_prompt.txt` |

### Known Code Issues (Pre-Phase 12)

| Issue | Location | Task |
|-------|----------|------|
| Wizard back+resubmit creates duplicate character | `actions.js:697` — mitigated via `_wizardPendingCharacter` reuse | Task 02 |
| Abandoned modal leaves orphan campaign/character | `actions.js:310` | Task 02 |
| Equipment drag-drop not implemented | `frontend/inventory` — slot containers exist, no DnD | Task 20 |
| Shop modal exists but no navigation entry point | `frontend/#shop-modal` | Task 20 |
| Voice TTS/STT partially implemented | `frontend/voice.js` — toggles visible, integration incomplete | Task 24 |
| Location not visible to player | Backend — `game_locations` table exists, no public badge | Task 09 |
| Combat victory narrative flow unclear | `game_engine.py` — auto-insertion of victory stub implicit | Task 12/13 |
| XP reward catalog structure opaque | Backend — no GET for individual skill costs before spending | Task 21 |

---

### Migration Strategy
- All new DB fields must be added via migration (not direct schema change)
- Add to `backend/app/migrations_admin.py` for admin/system tables
- Add to `RAW_MIGRATIONS` list in `backend/app/main.py` for core tables
- Never edit production DB directly

### Testing
- Mechanical changes (HP formula, combat, death saves): test with `docker exec ai-gm-dev-backend-1 pytest`
- End-to-end game flow: verify at `https://aigm-dev.studio-colorbox.com/`
- Admin-facing features: verify in admin panel at same URL `/admin`
