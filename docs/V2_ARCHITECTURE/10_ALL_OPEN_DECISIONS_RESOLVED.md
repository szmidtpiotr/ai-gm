# V2 — All Open Decisions Resolved

> Every blocking decision from the implementation plan is now confirmed.
> Use this as the canonical reference before implementation begins.

---

## Combat Mechanics

| Decision | Answer |
|----------|--------|
| Death save roll modifier | **Pure d20, no modifier.** The escalating DC (10→13→16→19) is the "gets harder" mechanic — no CON modifier needed on top. |
| Death save DC ladder | **DC 10 / 13 / 16 / 19** per 0-HP hit in same combat. |
| Death save counter reset on mid-combat heal | **No reset.** Drinking a potion heals HP but doesn't "un-nearly-die". Counter persists for the entire combat. Resets after combat ends or on long rest. |
| Critical hit threshold | **5 over AC.** Total − AC ≥ 5 triggers hit location roll. Nat 20 always crits regardless. |
| Fear DC per enemy | **Admin-configurable per enemy** via `game_config_enemies.fear_dc` column. Starting seeds: Troll=12, Vampire=16, Demon=18. |

---

## Character & Progression

| Decision | Answer |
|----------|--------|
| Warrior base HP | **10** (in `game_config_archetypes.hp_base`) |
| Scholar base HP | **6** (in `game_config_archetypes.hp_base`) |
| Ranger/Scout base HP | **8** (future archetype, seeded in advance) |
| Mana formula | `8 + (INT_modifier × 3)` — Scholar only |
| XP spending timing | **Long rest only.** XP accumulates as "pending" during play. Converts to spendable when hero takes a long rest → advancement screen appears. |
| Mend Wounds mana cost | **2 Mana** (starting value — raise to 3 if Scholar feels unkillable in testing) |
| Scholar double-dip | **No.** Cannot use Mend Wounds AND take short rest in same rest period. Pick one. |

---

## Companions

| Decision | Answer |
|----------|--------|
| Max companions | **Dynamic / story-driven.** Campaign plan decides — solo quests have 0, main arcs have 1, battle scenes can have 2-3. Controlled by key_npcs with role='companion' in campaign plan. |
| Companion combat | Auto-resolves turns (same engine as enemy AI, but allied side). Player can give orders via free text. |
| AoE friendly fire | Player AoE spells never hit allies. Exception: miscast AoE (Nat 1 on AoE spell) CAN hit allies. |

---

## Hero Architecture (KEY DECISION — Inverted from V1)

**Heroes are the primary entity. Campaigns/adventures are attached TO heroes.**

This is the opposite of V1 where campaigns were primary.

```
PLAYER
  └── Heroes (multiple)
        ├── Aldric (Warrior, Level 3) [ACTIVE]
        │     └── Current adventure: "Zdrada pod Graustein" (campaign)
        ├── Mira (Scholar, Level 1) [ACTIVE]
        │     └── No active adventure — at rest
        └── Bogdan (Warrior) [FALLEN]
              └── Legacy NPC in the world
```

**Rules:**
- Player can create multiple heroes
- A hero can have **one active adventure** at a time (campaign, dungeon run, side quest)
- A hero without an active adventure is "at rest" — can visit the world map, spend XP, access shops
- Starting a new adventure assigns it to the hero, not the other way around
- Dungeon runs found inside a campaign scenario link to that campaign's hero automatically

**Frontend implication:** The main navigation shows **heroes first** (hero selection screen), then adventure selection per hero. Not "campaigns with a character attached."

---

## Campaign End / Death

| Decision | Answer |
|----------|--------|
| Post-death options | **All 3 available:** (a) Restart campaign — hero survives, campaign resets; (b) Accept death — hero marked fallen, create new hero; (c) Retire — hero voluntarily exits, becomes world NPC/legend |
| Hero death legacy | Fallen/retired heroes become world lore. Admin can promote to NPC (ghost, ancestor, historical figure). |
| Campaign reset scope | Restart loses THIS campaign's XP and loot. XP from previous campaigns is permanent — never lost. |

---

## Dungeon Runs

| Decision | Answer |
|----------|--------|
| Cooldown | **Admin-configurable per dungeon seed.** Set in `campaign_ideas.cooldown_hours`. Suggested defaults: easy dungeon 48h, standard 72h, hard/rare 168h (7 days). |

---

## Auth & Registration

| Decision | Answer |
|----------|--------|
| Default | **Admin creates accounts** via admin panel. Closed system by default. |
| Self-registration toggle | Admin panel has a setting to **enable self-registration** when needed (demo mode, public launch, etc.). Disabled by default. |
| Invite codes | Option for self-registration with invite codes — admin generates codes, players register with them. Lower risk than fully open. |

---

## Summary: All Blocking Decisions Cleared

The implementation plan listed 7 blocking decisions. All are now resolved:

| # | Decision | Status |
|---|----------|--------|
| 1 | HP base values | ✅ Warrior=10, Scholar=6 (DB column) |
| 2 | Death save modifier | ✅ Pure d20, escalating DC |
| 3 | Death save counter reset | ✅ No reset mid-combat |
| 4 | Fear DC values | ✅ Admin-configurable, seeds set |
| 5 | Crit threshold | ✅ 5 over AC |
| 6 | Max companions | ✅ Dynamic/story-driven |
| 7 | XP spending timing | ✅ Long rest only |
| + | Post-death options | ✅ All 3 (restart/accept/retire) |
| + | Dungeon cooldown | ✅ Admin-configurable per dungeon |
| + | Registration | ✅ Admin-only + toggleable self-reg |
| + | Hero-centric architecture | ✅ Heroes primary, adventures assigned to heroes |

**No blocking decisions remain. Implementation can start with Phase 01.**
