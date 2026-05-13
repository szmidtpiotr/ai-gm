# TASK 25 (V2) — XP and Progression

**Phase:** 06 — Economy
**Status:** Not Started (replaces original TASK_25_XP_PROGRESSION.md)
**Related tasks:** TASK 11 (Turn Pipeline — Resolver grants XP), TASK 05 (HP/Mana formulas — magic tied to INT/WIS), TASK 42 (Persistent Hero — XP persists across campaigns)

---

## Overview

V2 replaces the level-gate system with WFRP-style direct XP spending. There are no level thresholds to cross, no automatic stat increases, and no gated abilities. Everything — stat improvements, skill ranks, spells, archetype abilities — is purchased directly from an XP pool that the player controls. Level exists as a display metric only. This makes progression feel like investment, not a treadmill.

**Supersedes:** `TASK_25_XP_PROGRESSION.md` — that document's level threshold tables, `apply_level_up` function, and gated skill/stat point system are all retired.

---

## Level — Display Only

```
level = floor(total_xp / 100)
```

- Shown on character sheet and in the hero list as context only.
- Maximum displayed level: 10 (at 1000 XP). XP continues accumulating above 1000.
- Does NOT gate any mechanic, ability, or stat. A hero at level 1 can purchase any advancement if they have the XP.
- HP and Mana are not recalculated on level-up. They scale only when the underlying stats (CON, INT) are purchased with XP.

Level is recomputed on every character load. It is not stored as a separate column — derive it from `xp_total` at runtime.

---

## XP Sources

All XP grants are issued by the **Mechanic Resolver** or **World State Updater**. The LLM narrator never decides XP values and never references XP numbers in narration.

XP sources are grouped into 6 categories. Kill-only XP would create a murder-hobo incentive — all meaningful actions must be rewarded.

### Category A — Combat (Mechanic Resolver, automatic)

| Source | XP | How Detected |
|---|---|---|
| Kill weak enemy | 10 | `enemy.tier='weak'`, hp ≤ 0 in resolver |
| Kill standard enemy | 25 | `enemy.tier='standard'` |
| Kill elite enemy | 50 | `enemy.tier='elite'` |
| Kill boss | 150 | `enemy.tier='boss'` |
| **Survive a death save** | 15 | Death save resolver outputs `success` |
| Win while outnumbered (≥3 enemies, all defeated) | 20 | VICTORY with `initial_enemy_count ≥ 3` |

**Death save XP rationale:** Surviving something that nearly killed you is growth. The character literally learned to cling to life. Rewards risky play without encouraging suicidal behavior.

In group combat, XP from kills is summed across all enemies defeated in that combat. XP is always granted by the system reading `enemy.xp_reward` from DB — it is never calculated ad hoc.

### Category B — Campaign Progress (Plan tracking, automatic)

| Source | XP | How Detected |
|---|---|---|
| Key beat completed | 30 | `[BEAT_COMPLETE:key]` tag processed by backend |
| Campaign ending reached | 200 | `[CAMPAIGN_END:ending_id]` tag |
| Side quest completed | 40 | Beat with `quest_type='side_quest'` flag |
| Dungeon fully cleared | 75 | `[DUNGEON_CLEAR]` tag or all sub-location enemies = 0 |

**Key design point:** Beat XP rewards the achievement regardless of method. Player who persuades the bandit leader instead of killing him still gets the beat XP for "bandit_confrontation_resolved". This ensures non-violent solutions are never penalised in XP terms.

### Category C — Exploration (WSM, first-time only)

| Source | XP | How Detected |
|---|---|---|
| New macro location discovered | 15 | location_key NOT in `character.visited_location_keys` |
| New NPC spoken to for first time | 5 | First `DIALOGUE` action with this npc_key ever |
| Important secret or lore discovered | 10 | `[DISCOVERY:lore_key]` tag from narrator |
| Hidden passage or secret room found | 10 | `[DISCOVERY:secret_location_key]` tag |

"First time" checks against `character.visited_location_keys` (JSON array, persists across all campaigns). A location visited in Campaign 1 does not grant XP again in Campaign 2.

### Category D — Skills & Social (Mechanic Resolver, automatic)

| Source | XP | How Detected |
|---|---|---|
| Skill test success vs DC 12–15 | 3 | Resolver: `success=true`, `dc` in range |
| Skill test success vs DC 16–19 | 8 | Resolver: `success=true`, `dc` in range |
| Skill test success vs DC 20+ | 15 | Resolver: exceptional success |
| Opposed skill test win vs important NPC | 10 | Resolver: opposed success, target NPC `importance ∈ {critical, supporting}` |

DC 12–15 successes grant only 3 XP — routine successes are not heavily rewarded. Exceptional skill (DC 20+) grants 15 XP because it was a genuine achievement.

### Category E — Narrative Moments (Tag-based, narrator emits)

The narrator LLM can emit `[XP_GRANT:reason:amount]` for moments the mechanical system cannot detect.

| Reason tag | XP | Example situation |
|---|---|---|
| `nonviolent_solution` | 20 | Solved a conflict through roleplay entirely |
| `heroic_sacrifice` | 25 | Took damage intentionally to protect an NPC |
| `clever_environment` | 10 | Used location features in a creative way |
| `moral_difficult_choice` | 15 | Made a hard decision with real personal cost |
| `unexpected_ally` | 10 | Turned an enemy into an ally through roleplay |
| `discovery_major` | 15 | Uncovered a major hidden truth about the campaign |

**Hard cap: 50 XP maximum from `[XP_GRANT]` tags per session** (per long-rest cycle). System tracks running total of narrative grants; ignores any grant that would exceed the cap.

**Narrator prompt instruction:** *"Use [XP_GRANT] only for genuinely exceptional player decisions — moments you would specifically highlight in a post-session recap. If in doubt, don't emit it. Maximum 3 grants per session."*

### Category F — Session Completion (Granted on long rest)

| Source | XP | How Detected |
|---|---|---|
| Session participation: 20–39 turns played | 10 | `turns_since_last_rest` count |
| Session participation: 40+ turns played | 20 | `turns_since_last_rest` count |

This is the WFRP "just showing up" award. Every session that ends in a long rest provides baseline XP for engagement, regardless of what happened.

---

## XP Timing — Pending Until Long Rest

**CONFIRMED:** XP spending happens at long rest only. XP accumulates as 'pending' during play. On long rest: pending converts to spendable → advancement screen appears. See `10_ALL_OPEN_DECISIONS_RESOLVED.md`.

**All XP is accumulated as "pending" until the character takes a long rest.**

```
Player kills goblin:          "+25 XP pending" notification
Beat completed:               "+30 XP pending" notification
New location discovered:      "+15 XP pending" notification

[Character sheet XP bar shows: "Earned: 70 XP (pending)"]

Player takes long rest:
  → Session XP (Category F) calculated and added to pending
  → All pending XP converts to available XP
  → Advancement screen: "Zdobyłeś 80 PD. Jak chcesz je wydać?"
  → Player spends or saves
```

**Exceptions — immediate availability:**
- Campaign ending (200 XP): granted immediately. Campaign is done; player should advance before starting the next adventure.
- Death save survived (15 XP): granted immediately after combat ends (player should feel the reward of survival).

**Why deferred to long rest?**
1. Natural session rhythm: play → earn → rest → grow
2. Prevents spending XP mid-combat on stats that immediately affect the ongoing fight
3. Thematic: you process experiences during sleep, not mid-battle
4. Long rest becomes a meaningful moment: recovery AND advancement

---

## Non-Violent vs Combat XP Comparison

Player confronts 3 bandits at a bridge:

| Approach | XP breakdown | Total | Risk |
|---|---|---|---|
| **Fight** | 3 kills × 25 + beat 30 + outnumbered bonus 20 | **125 XP** | High — real damage/death risk |
| **Negotiate** | beat 30 + opposed persuasion 10 + [nonviolent_solution] 20 | **60 XP** | Low |
| **Sneak past** | beat 30 + Stealth DC16 success 8 | **38 XP** | Low |

Combat earns more XP — but costs HP and resources. The XP spread is intentional: risk should be rewarded. However, non-combat solutions are never zero — a smart player who negotiates consistently will advance at a slower but still viable rate, and won't burn through healing potions.

---

## Typical Session XP Budget

*30 turns, 2 combats, some exploration:*

| Source | XP |
|---|---|
| 2 × standard enemy kills | 50 |
| 1 key beat completed | 30 |
| 1 new location discovered | 15 |
| 2 new NPCs met | 10 |
| 1 skill test DC 16+ success | 8 |
| 1 narrative moment | 15 |
| Session participation (30 turns) | 10 |
| **Total** | **138 XP** |

First level display milestone (100 XP): ~1 session.
First stat purchase (30–50 XP): half a session.
Scholar's first spell upgrade (50 XP): ~1 session.

Pacing feels right — meaningful growth every session without trivialising progression over a 10-session campaign.

### No XP Loss

XP is never deducted — not on death, not on failure, not on campaign abandonment.
```python
# XP is permanent — no deduction on death or failure by design.
```

---

## XP Cost Table

### Stats

Stat improvements follow an escalating cost curve based on the current modifier before the purchase:

```
cost = max(30, 50 × current_modifier_before_purchase)
```

Current modifier before purchase means the modifier of the stat as it stands now, before the point is applied.

| Example | Current Stat | Current Mod | Cost to +1 |
|---|---|---|---|
| STR 10 → 11 | 10 | 0 | max(30, 50×0) = 30 |
| STR 12 → 13 | 12 | +1 | max(30, 50×1) = 50 |
| STR 14 → 15 | 14 | +2 | max(30, 50×2) = 100 |
| STR 16 → 17 | 16 | +3 | max(30, 50×3) = 150 |
| STR 18 → 19 | 18 | +4 | max(30, 50×4) = 200 |

No stat can exceed 20 (modifier cap +5). Each purchase increments the stat by 1. Modifier is always `floor((stat - 10) / 2)`.

### Skills

```
cost = max(30, 30 × current_rank_before_purchase)
```

| Current Rank | Cost to +1 |
|---|---|
| 0 → 1 | max(30, 30×0) = 30 |
| 1 → 2 | max(30, 30×1) = 30 |
| 2 → 3 | max(30, 30×2) = 60 |
| 3 → 4 | max(30, 30×3) = 90 |
| 4 → 5 | max(30, 30×4) = 120 |

Maximum skill rank: 5. Proficiency bonus (+2 to rolls) applies at rank ≥ 3, per system prompt mechanics.

### Spells and Abilities (Scholar / Archetype)

| Purchase | XP Cost |
|---|---|
| New spell learned — Scholar | 75 |
| Upgrade existing spell Rank 1 → 2 | 50 |
| Upgrade existing spell Rank 2 → 3 | 100 |
| New archetype ability (Warrior or Scholar unlock) | 150 |

Spell availability: determined by spell list in admin configuration, not by level. Any spell can be purchased at any level if the XP is available.

---

## Magic Scaling — Tied to INT, Not Level

Magic power scales directly with the INT stat. Purchasing INT with XP directly improves all three magic metrics:

| Metric | Formula |
|---|---|
| `max_mana` | `8 + (INT_modifier × 3)` |
| `spell_dc` | `10 + INT_modifier` |
| `spell_attack_bonus` | `INT_modifier` |

A Scholar who invests XP in INT gains compounding returns: higher mana pool, harder-to-resist spells, and better attack rolls simultaneously. This is intentional — INT investment is the primary Scholar progression path.

Example progression:
- INT 10 (mod 0): max_mana=8, spell_dc=10, spell_attack=+0
- INT 14 (mod +2): max_mana=14, spell_dc=12, spell_attack=+2
- INT 18 (mod +4): max_mana=20, spell_dc=14, spell_attack=+4

Recalculate `max_mana`, `spell_dc`, and `spell_attack_bonus` immediately whenever INT is modified by a stat purchase.

---

## Spending Mechanics

### When to Spend

XP is available to spend:
- **Recommended:** During long rest (between sessions, or when the hero enters rest state between campaigns — see TASK 42). Most immersive timing.
- **Available:** Any time outside active combat. The spending panel can be opened whenever `character.in_combat = False`.

### Spending Blocked During Combat

Both spend endpoints return `400` with message `"Nie możesz awansować podczas walki."` if `character.in_combat = True`.

### Pending Advancement Badge

When `pending_xp >= 30` (minimum stat cost): show a ⬆️ badge on the character sheet icon in the UI toolbar.

The badge is a soft nudge, not a blocking gate. The player can ignore it indefinitely.

### Spend Endpoints

**Stat purchase:**
```
POST /api/characters/{character_id}/spend-xp/stat
Body: { "stat_key": "STR" }
```
Backend: verify `xp_total >= cost`, deduct XP, increment stat, recalculate modifier, recalculate max_hp if CON changed, recalculate mana/dc/attack if INT changed.

**Skill purchase:**
```
POST /api/characters/{character_id}/spend-xp/skill
Body: { "skill_key": "stealth" }
```
Backend: verify `xp_total >= cost`, deduct XP, increment skill rank.

**Spell purchase:**
```
POST /api/characters/{character_id}/spend-xp/spell
Body: { "spell_key": "firebolt", "action": "learn" }
// action: 'learn' | 'upgrade'
```

**Archetype ability purchase:**
```
POST /api/characters/{character_id}/spend-xp/ability
Body: { "ability_key": "second_wind" }
```

All endpoints return the updated character sheet on success.

---

## HP and Mana After Stat Purchase

Unlike V1 where `apply_level_up` granted HP automatically, V2 HP and Mana only increase when the player purchases the relevant stats:

- CON +1 → `max_hp += 1` (using standard D&D modifier math: `floor((new_CON - 10) / 2) - floor((old_CON - 10) / 2)` × level, but simplified to +1 per CON point for clarity at lower levels — designer's call to confirm).
- INT +1 (Scholar) → `max_mana` recalculated from formula `8 + (new_INT_modifier × 3)`.

`current_hp` and `current_mana` are NOT automatically topped up when max increases. The new max takes effect; the player heals via normal means.

---

## XP UI

### Character Sheet — XP Display

Location: right panel, below HP/Mana bars.

```
XP  ████████████░░░░░░  340 / 400  (Poz. 3)
```

- Progress bar fills based on `xp_total mod 100` (progress toward next display level).
- Label: `{xp_total} XP  (Poz. {level})`
- On hover: tooltip showing `"Poziom {level} — {xp_total} XP łącznie"`.

On XP gain this turn: briefly flash the bar yellow, with `+25 XP` indicator appearing for 2 seconds. Uses `xp_delta` from the turn response payload.

### Advancement Screen

Accessible via: [⬆️ Awansuj] button (shown when badge is active) OR character sheet → [Awans] tab.

Three sub-tabs:

1. **Statystyki** — 7-stat grid. Each stat shows current value, modifier, cost to +1, and resulting value after purchase. [+] button per stat (disabled if XP < cost or stat at max).
2. **Umiejętności** — skill list with current rank, rank pips (0–5 filled), cost to next rank, [+] button.
3. **Magia / Zdolności** — (Scholar/Warrior) list of purchaseable spells and abilities, with XP cost and [Kup] button.

All tabs show remaining XP prominently at top: `Dostępne XP: 340`.

Purchases confirm immediately — no confirmation dialog. XP is deducted and advancement applied in real time.

---

## Migration from V1

V1 characters have `level`, `unspent_skill_points`, and `unspent_stat_points` fields. Migration:

1. Compute `xp_total` from old level using reverse-engineered approximation: `xp_total = XP_THRESHOLDS[old_level]` (from V1 threshold table, see old TASK_25).
2. Convert `unspent_skill_points` and `unspent_stat_points` to XP: each unspent skill point → 30 XP, each unspent stat point → 50 XP. Add to `xp_total`.
3. Drop columns `unspent_skill_points`, `unspent_stat_points`, `level` from characters table (level is now computed).

Write as a DB migration in `backend/app/migrations_admin.py` or a new `.sql` file.

---

## Test Checklist

1. **XP granted by Resolver only:** Simulate a combat kill and a beat completion — verify XP in `character.xp_total` increases by the correct amounts, verify LLM narration contains no XP mentions.
2. **Stat cost scaling:** Purchase STR at modifier +1 — verify 50 XP deducted. Purchase STR again at modifier +2 — verify 100 XP deducted.
3. **Magic improves with INT:** Purchase INT when at modifier +1 — verify `max_mana`, `spell_dc`, and `spell_attack_bonus` all update according to formula.
4. **Spending blocked during combat:** Set `character.in_combat = True`, POST to any spend endpoint — verify 400 response with correct Polish message.
5. **Persistence across campaigns:** Grant XP in campaign 1, end campaign, start campaign 2 — verify `xp_total` carries forward unchanged, advancement screen shows correct available XP.
6. **Level display correct:** Set `xp_total = 350` — verify level shown as 3. Set to 1000 — verify level shown as 10 (cap). Set to 1500 — verify level still shown as 10 (no rollover above cap).
