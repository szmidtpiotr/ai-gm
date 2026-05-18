# Decisions — 2026-05-18

> Resolutions to all clarification questions raised in `AUDIT_2026_05_18.md`. Canonical reference for everything that follows. Where spec and code diverged, the rationale is recorded.

---

## D1 — Equipment slot model (8 slots)

**Decision:** Adopt **8 slots total** — 6 anatomical armor slots + 2 weapon slots.

| Slot | Purpose | Example items |
|---|---|---|
| `head` | Helmets, hoods, masks | Hełm żelazny, Hood of Shadows |
| `torso` | Body armor (chest piece OR full-body covers torso) | Skórzana kurtka, Kolczuga, Plate mail |
| `l_arm` | Left-arm armor (vambrace, gauntlet) | Stalowy nararamiennik |
| `r_arm` | Right-arm armor | (mirror of l_arm) |
| `l_leg` | Left-leg armor (greaves, boots = leg armor) | Wzmocnione buty |
| `r_leg` | Right-leg armor | (mirror) |
| `main_hand` | Primary weapon | Miecz, Łuk, Laska |
| `off_hand` | Shield or secondary weapon | Tarcza, Sztylet |

**Armor variants** (controlled by `game_config_items.armor_coverage`):

| Coverage | Occupies slots |
|---|---|
| `head` | head only |
| `torso` | torso only |
| `limb_arm` | one arm slot (admin picks l_arm or r_arm at equip time, or paired) |
| `limb_leg` | one leg slot |
| `full` | torso + l_arm + r_arm + l_leg + r_leg (everything except head) |

**No gloves/boots as separate item types.** Boots are leg armor; gloves are arm armor.

**Why this model:**
- Anatomical UI reads clearly to players (point at the body part to see what's there).
- 8 slots is enough variety without exploding inventory complexity.
- `full` armor is a single record with `armor_coverage='full'` that the system expands to fill 5 slots at equip time.

**Migration cost:**
- Existing 3-slot data (`main_hand`, `off_hand`, `armor`) maps cleanly: `armor` rows become `torso` (90% of cases) or `full` (heavy armor). One-shot data migration on startup.
- New columns on `game_config_items`: `armor_coverage`.
- New constants on backend (`loot_service._SLOT_VALUES`).

**Spec impact:** Update `TASK_35_CHARACTER_SHEET_UI.md` § 7 from "L Hand / R Hand / Feet / Hands" to the 8-slot model.

---

## D2 — Condition naming aligned to spec

**Decision:** Rename code values to match spec.

| Current code | New (spec) |
|---|---|
| `fear_shaken` | `FRIGHTENED` |
| `terror` | `PANICKED` |
| `break` | `BREAK` |

**Migration:**
- Idempotent UPDATE in `RAW_MIGRATIONS` on `character_conditions.condition_key` and `game_config_conditions.key`.
- Backend service rename in `combat_service.py`.
- Frontend label refs in chat bubble + character sheet condition pills.
- ~30 minutes total work.

---

## D3 — Enemy HP visibility

**Decision:** Show **both** the bar and the exact `current/max` number on enemy combatant rows.

Spec wanted bar-only for atmosphere. Reality (functional info parity with player) wins. Spec updated.

---

## D4 — T42 Persistent Hero scope

**Decision:** Implement endpoints + UI **now**. Schema is already done.

| Item | Status after decision |
|---|---|
| `characters.hero_status` column | ✅ exists |
| `characters.visited_location_keys` | ✅ exists |
| `character_campaign_history` table | ✅ exists |
| `GET /api/heroes` | ❌ → ship |
| `GET /api/characters/{id}/history` | ❌ → ship |
| `POST /api/characters/{id}/rest` | ❌ → ship |
| REST state UI ("between campaigns") | ❌ → ship |
| Hero Journal full UI | overlaps with T45 — partial in T42, full in T45 |

T42 covers the **between-campaigns REST flow** and **hero status endpoints**. T45 stays separate as the full chronicle / cross-campaign journal experience.

---

## D5 — T44 Debug System scope

**Decision:** Implement **both** player-facing and admin-side.

**Player side:**
- Debug drawer (right panel, 420 px, collapsible).
- Section tabs: game_state, last_intent, mechanic_result, llm_prompts, narrator_output.
- Slash commands: `/debug set-hp <n>`, `/debug set-state <state>`, `/debug reset-cooldowns`.
- Toggle visible only when user has `is_admin = true` OR feature flag is set.

**Admin side:**
- Existing `routers/debug.py` endpoints (`/player_state`, `/gm_decisions`, `/validation_flags`, `/settings/feature_flags`, `/reset_test_env`) stay.
- Add a new Admin Panel v2 section "🐛 Debug" that surfaces them in UI.

---

## D6 — Auth model

**Decision:** Full security baseline — **JWT + bcrypt + lockout + role-based access + onboarding overlay**, shipped together.

| Component | Detail |
|---|---|
| **JWT** | HS256, 7-day expiry, refresh endpoint. Replaces current cookie/bearer. |
| **Password hashing** | bcrypt with cost factor 12. Verify current hashing first; migrate if different. |
| **Brute-force lockout** | 10 failed logins → account locked 15 min. Counter resets on success. |
| **Roles** | `player` (default), `gm` (campaign owner), `admin`. Multiplayer future: GM controls scene, players control hero only. |
| **Multi-device sessions** | Natural via JWT. Token works on phone + desktop simultaneously. |
| **Onboarding overlay** | First-login modal: welcome text, theme picker (dark/light), accept rules, [Zaczynam przygodę]. Shown once per user, flag stored on user record. |

**Migration:** existing user records keep their hashed passwords if bcrypt is detected. If not bcrypt, force re-set on next login.

---

## D7 — XP loop is next priority

**Decision:** Earning works; spending UI completely missing. Ship the player-facing loop next.

**Minimum viable XP loop:**
1. XP progress bar in character sheet (current XP → next level visible).
2. Level display (computed: `floor(xp_total / 100)`).
3. `POST /api/characters/{id}/rest` long-rest endpoint that flips pending XP to spendable.
4. Player UI "Awansuj" (level up) button that opens a panel:
   - Skill rank-up cards (cost shown, click → spend → confirm).
   - Stat point-up cards (same UX).
   - Spell learn/upgrade for Scholar.
5. Level-up notification banner per spec.

**Order:** progress bar → level display → rest endpoint → spending UI → banner.

---

## D8 — Smart Entry workflow

**Decision:** Keep form-first as the default. Improve the **parallel AI chat-loop** so admin can iterate with the AI until the item is exactly right, then save.

**Flow:**
1. Admin opens AI Kreator on any content tab.
2. Form on the right is empty (NEW) or pre-filled (EDIT).
3. Chat on the left starts the conversation.
4. Admin: "Sword that bleeds enemies."
5. AI fills entire form, posts a brief summary in chat.
6. Admin: "Make it deal 1d10 instead, and add a chance of intimidation."
7. AI updates form, summarizes changes.
8. Loop until admin clicks **Zapisz rekord**.

**What's already in place:** the chat-loop architecture exists. Improvements needed:
- AI must keep state of the current draft and apply incremental edits, not regenerate from scratch each turn.
- Form fields should highlight which ones changed in the last AI response.
- Clear "what changed" delta line in chat ("Zmieniłem: damage 1d6 → 1d10").

**No Q&A wizard mode.** Updates spec to reflect this.

---

## D9 — Condition DB migration — confirmed

Already covered in D2. Worth the ~30 min cost.

---

## D10 — Spec drift policy

**Case-by-case.** Where reality won, update the spec to record the rationale. Where the spec was right, mark the code as a partial implementation to be completed.

| Where reality won (update spec) | Where spec wins (update code) |
|---|---|
| Equipment 8-slot model (was 6 with hands/feet) | Condition names (`FRIGHTENED` etc.) |
| Enemy HP shows numbers | Wound label rendering on player HP bar |
| Smart Entry form-first (no Q&A wizard) | XP spending UI / long rest endpoint |
| Honeycomb.js library not used (custom geometry) | T35 character sheet items in #24 |

---

## D11 — New condition: `zaskoczony` (Surprised)

**Decision:** Add to `game_config_conditions` table.

| Field | Value |
|---|---|
| `key` | `zaskoczony` |
| `label_pl` | `Zaskoczony` |
| `label_en` | `Surprised` |
| `category` | `tactical` |
| `applies_to` | `enemy` (player can also be subject in future — out of scope now) |
| `effect` | Attackers gain **+2 ATK** against the subject. First successful hit deals **×2 damage**. |
| `duration` | 1 round OR until the subject takes any damage (whichever comes first). |
| `triggered_by` | Successful player Stealth skill test that meets surprise-ambush criteria. |
| `cleared_by` | Round counter reaches 0 OR `combatant.hp_current` decreases. |

**Surprise-ambush criteria** (when stealth → applies zaskoczony):
- Player is in `ranged` zone with stealth advantage.
- Stealth DC: Easy (8) if alone enemy, Hard (16) if multiple enemies.
- LLM narrator emits `[APPLY_CONDITION:zaskoczony:enemy_key]` tag on successful stealth narrative.

**Backend changes:**
- `combat_service._apply_attack_bonuses()` — read `zaskoczony` on target, apply +2 ATK + ×2 damage on first hit.
- `combat_service` — clear `zaskoczony` after target takes damage.

**Frontend changes:**
- Initiative chip + combatant row show ⚡ badge with tooltip "Zaskoczony — pierwszy cios trafia podwójnie".

---

## Implementation order proposed

Once the docs are updated to reflect these decisions, the implementation order is:

1. **Condition rename** (D2) — small, low-risk, unblocks naming consistency.
2. **XP loop** (D7) — biggest gameplay impact, dormant economy.
3. **8-slot equipment** (D1) — UI rework + armor_coverage data column.
4. **Wound label** (drift) — quick win.
5. **Enemy HP both bar+number** (D3) — small.
6. **`zaskoczony` condition** (D11) — small backend + frontend.
7. **T42 endpoints** (D4) — Hero list + history + rest endpoint.
8. **T44 Debug** (D5) — player drawer + admin panel section.
9. **Auth refactor** (D6) — significant; JWT migration + onboarding modal.
10. **T45 Hero Journal** — full chronicle UI.
11. **Smart Entry chat-loop polish** (D8) — incremental editing fix.

Each step gets its own implementation-record issue per the CLAUDE.md workflow.
