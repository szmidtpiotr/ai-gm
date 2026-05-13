# TASK 21 — XP & Character Progression

**Status:** ❓ Needs Design
**Blocking:** Full design discussion needed
**Depends on:** Task 01 (HP/Mana formulas — level-up must recalculate these)

---

## What Needs to Be Designed

1. **XP sources** — Combat victory, quest completion, narrative milestones, skill checks? Which grant XP and how much?
2. **XP grant method** — Automatically by system after qualifying events, or manually by GM? Or both? Currently unclear — `character_xp_grants` table exists but grant logic is opaque.
3. **XP thresholds** — How much XP per level? Flat (e.g. 100 per level) or scaling (e.g. level² × 50)?
4. **Level-up effects** — What changes on level up: max HP recalculated (CON_mod × new level), max Mana recalculated, stat point(s), skill point(s)?
5. **When to level up** — Immediately when threshold hit, only at long rest, or player-triggered?
6. **XP UI** — Where does the player see XP? Progress bar in character sheet? Notification banner when level-up available?
7. **Skill spending** — `POST /characters/{id}/xp/spend-skill` already exists. Can players spend at ANY time or only at level up? What does spending XP on skills cost (currently no GET for costs)?
8. **Stat spending** — `POST /characters/{id}/xp/spend-stat` exists. Same timing question. Caps per stat?
9. **Max level** — Level cap? Or unlimited?
10. **XP loss on death** — Does character death wipe XP progress or is it purely a campaign-end event?

## Current State

- `character_xp_grants` table exists with XP history
- `GET/POST /characters/{id}/xp` endpoints exist
- `POST /characters/{id}/xp/spend-skill` and `/xp/spend-stat` exist
- Character has `level` field (starts at 1)
- No XP UI in player frontend
- XP awarded after combat exists in code but unclear how much

## Related Tasks
- Task 01 — level-up recalculates HP/Mana
- Task 08 — skill tests make skill progression meaningful

---

*This file will be filled with full specification after the design discussion.*
