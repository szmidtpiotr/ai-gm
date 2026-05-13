# V2 — Remaining Design Decisions & Post-Implementation TODOs

> Items that were discussed but deferred, or decisions made that need no separate task file.

---

## Trap Mechanic (V2 — simple, added to skill test system)

**Decision: Yes — simple version using existing skill test infrastructure.**

Tag format: `[TRAP:skill_key:dc:damage_dice:condition]`

Examples:
```
[TRAP:perception:12:d6:leg_wound]
[TRAP:acrobatics:14:2d4:]              ← no condition, just damage
[TRAP:perception:10:d4:poisoned]       ← poison gas room
```

**Flow:**
1. GM emits [TRAP] tag in narration (stripped from player-visible text)
2. Roll popup: "Uwaga! Perception vs DC 12"
3. Pass → narrator: "Widzisz drut w poprzek korytarza" (no damage)
4. Fail → Mechanic Resolver: apply damage (d6) + optional condition (leg_wound)

**Implementation note:** This is a 3-line extension of the skill test tag processor (TASK_12). No new system — the [TRAP] tag simply pre-specifies the skill, DC, damage, and condition rather than waiting for the player to declare a search. Add handling to `process_skill_test_tag()` in game_engine.py.

**Trap disarm:** Player can declare "I try to disarm the trap" → becomes a normal skill test (Engineering/Lockpicking vs a DC set by GM). Pass = trap disarmed. Fail = trap triggers (damage + condition as above). No special mechanic needed — handled by existing [SKILL_TEST] flow.

---

## Player Notes

**Decision: Post-implementation TODO.**

User couldn't identify a clear V2 use case. To be added after implementation ships if players request it.

Suggested future design:
- Simple text area per campaign, saved in DB
- Accessible from the journal panel (third tab: "Notatki")
- No LLM involvement — pure player-written text
- Persists across sessions

---

## Gold Economy

**Decision: Define philosophy now, calibrate values after playtesting.**

**Philosophy: WFRP-tight.** A healing potion should feel like a meaningful purchase, not a trivial reflex buy. Every gold piece earned in a session should feel like progress toward something.

**Calibration targets (to validate after Phase 06 implementation):**

| Item | Target feel |
|------|-------------|
| Bandage (3gp) | Cheap, always affordable |
| Small health potion (15gp) | 1 session of light combat to afford |
| Healing potion (25gp) | Significant purchase — takes saving |
| Chainmail (75gp) | Multi-session goal for Warrior |
| Plate armor (250gp) | Long-term aspiration |

**Where to tune (all in admin panel, no code changes):**
- Starting gold → `game_config_archetypes.starter_gold_gp`
- Enemy drops → `game_config_loot_tables` (guaranteed + random drops)
- Shop prices → `value_gp` on `game_config_items/weapons/consumables`
- Quest rewards → loot tables tied to quest NPCs

**Starting values in DB are placeholders.** First playtest pass after Phase 06 should focus on:
1. Does a typical 30-turn session feel economically meaningful?
2. Can a player afford 1 healing potion every 1.5–2 sessions?
3. Is plate armor a real long-term goal, not a Week 2 purchase?

---

## Summary: All Items From Gap Analysis

| Item | Status |
|------|--------|
| Conditions lifecycle | ✅ Fully designed — `11_CONDITIONS_SYSTEM.md` |
| Poison & Bleeding definitions | ✅ Fully designed — `11_CONDITIONS_SYSTEM.md` |
| Travel between locations | ✅ Fully designed — `12_TRAVEL_SYSTEM.md` |
| Session persistence / offline HP | ✅ Fully designed — `13_SESSION_PERSISTENCE.md` |
| Equipment effects application | ✅ Fully designed — `14_EQUIPMENT_EFFECTS.md` |
| Quest / objective visibility | ✅ Fully designed — `15_QUEST_SYSTEM.md` |
| Player notes | 🔶 Post-implementation TODO |
| Trap mechanic | ✅ Designed (simple) — add to TASK_12 skill test |
| Gold economy calibration | 🔶 Philosophy set. Values calibrated after playtesting. |
| Selling price policy | ✅ 50% of buy price (confirmed earlier) |

---

## Post-Implementation Feature Backlog

Ideas discussed during planning that were deferred:

| Feature | Priority | Notes |
|---------|---------|-------|
| Player notes | Medium | Simple textarea in journal panel, 3rd tab |
| Time of day mechanical effects | Medium | Night: +10% encounter, shops closed, stealth bonus |
| Random wilderness travel events | Medium | Not just combat — find a body, meet a traveler, discover a clue |
| Reputation / faction system | Medium | NPCs remember player actions; affects dialogue options |
| Crafting system | Low | Scholar alchemist angle; combine items |
| Item durability / degradation | Low | WFRP feel — weapons need repair at blacksmith |
| Weapon condition (worn/damaged) | Low | Extends durability system |
| Darkness / light visibility | Low | Torches already in DB — give them a purpose |
| Spectator mode | Low | Watch a live session without playing |
| Dungeon room map (revealed) | Phase 11 | Room-by-room exploration map |
| Multiplayer / co-op | Future | Not in V2 scope |
| Ranger/Scout archetype | Post-V2 | DEX-focused, stealth, ranged. DB already has `allowed_classes: ["ranger"]` references. |
| Wound effects Option B | Post-V2 | Stat penalties at 50%/25% HP (currently narrative labels only) |
| NPC relationship system | Post-V2 | Trust/hostility tracking beyond alive/dead |
| Day/night mechanical effects | Post-V2 | Currently narrative only |
