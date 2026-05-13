# V2 DB Cleanup & Column Decisions

> Decisions made during schema audit session. All items resolved.
> See TASK_01_DB_SCHEMA.md for the actual SQL migrations.

---

## Format / Type Decisions

| # | Table | Column | Decision |
|---|-------|--------|---------|
| 1 | game_config_items | `weight` vs `weight_kg` | Keep `weight_kg`, drop `weight` |
| 2 | game_config_items | `effect_json` vs `ac_bonus` | Add `ac_bonus` as direct column. Migrate armor AC from effect_json. Keep effect_json for complex multi-effect items. |

## Architecture Migrations (JSON arrays → join tables)

| # | Table | Column | Decision |
|---|-------|--------|---------|
| 3 | game_locations | `enemy_keys` (JSON) | Migrate to `location_enemy_assignments` join table, drop JSON column |
| 4 | game_locations | `npc_keys` (JSON) | Migrate to `location_npc_assignments` join table, drop JSON column |
| 5 | game_locations | `parent_id` vs `parent_key` | Add `parent_key` string column. Seed from parent_id. V2 uses parent_key. Keep parent_id for FK integrity. |
| 6 | npcs | `location_keys` mismatch | Migrate `npc_locations` join table + `npc_keys` JSON → unified `location_npc_assignments`. npc_locations table dropped. |

## Forgotten / Dead Columns

| # | Table | Column | Decision |
|---|-------|--------|---------|
| 7 | game_config_enemies | `dex_modifier` | Was forgotten from admin panel. Add as editable field — critical for V2 initiative and flee. |
| 8 | game_config_items | `proficiency_classes` | Drop — V2 uses `allowed_classes` on weapons instead |
| 9 | game_config_loot_entries | `currency_code` | Drop — V2 uses unified gold |
| 10 | stats/skills/dc | `sort_order` | Keep — lightweight, no harm, future manual ordering |

## New Columns Confirmed

| # | Table | New Column | Type | Default | Purpose |
|---|-------|-----------|------|---------|---------|
| 11 | game_config_archetypes | `hp_base` | INTEGER | 10 | Admin-configurable base HP per archetype. warrior=10, scholar=6, ranger=8 (future) |
| 12 | game_config_enemies | `dex_modifier` | INTEGER | 0 | **Already in DB** — expose in admin panel as editable |
| 13 | game_config_enemies | `skills_json` | TEXT | '{}' | Enemy skill ranks for opposed tests. `{"perception":2,"stealth":1}`. Resolver checks this before falling back to tier defaults. |
| 14 | game_config_enemies | `behavior_profile_key` | TEXT | NULL | FK to enemy_behavior_profiles — V2 rule-based enemy AI |
| 15 | game_config_enemies | `fear_aura` | INTEGER | 0 | Bool — triggers Fear test when combat starts |
| 16 | game_config_enemies | `fear_dc` | INTEGER | 12 | WIS save DC for the fear test |
| 17 | game_config_enemies | `hit_location_table` | TEXT | 'standard' | standard/undead/beast/construct/humanoid_armored |
| 18 | game_config_enemies | `review_status` | TEXT | 'permanent' | permanent/pending_review/discarded |
| 19 | game_locations | `safe_for_rest` | INTEGER | 0 | Bool — player can short/long rest here |
| 20 | game_locations | `review_status` | TEXT | 'permanent' | permanent/pending_review/discarded |
| 21 | game_locations | `map_x` | REAL | NULL | World Builder node X position |
| 22 | game_locations | `map_y` | REAL | NULL | World Builder node Y position |
| 23 | game_locations | `map_icon` | TEXT | 'town' | town/dungeon/forest/ruin/castle/cave/road/camp/port |
| 24 | game_locations | `visible_before_visit` | INTEGER | 0 | Bool — show on player map before visiting |
| 25 | npcs | `personality_prompt` | TEXT | NULL | Short LLM roleplay string: "Gruff innkeeper. Suspicious of strangers." |
| 26 | npcs | `keyword_triggers` | TEXT | '[]' | JSON: [{keyword, must_reveal_info, is_secret}] |
| 27 | npcs | `review_status` | TEXT | 'permanent' | permanent/pending_review/discarded |
| 28 | game_config_consumables | `ai_generated` | INTEGER | 0 | Bool — created by GM during session |
| 29 | game_config_consumables | `approved` | INTEGER | 1 | Bool — admin-approved for permanent use |

## New Join Tables

| Table | Replaces | Purpose |
|-------|---------|---------|
| `location_npc_assignments` | `game_locations.npc_keys` + `npc_locations` | Links NPCs to locations with assignment_type |
| `location_enemy_assignments` | `game_locations.enemy_keys` | Links enemies to locations with spawn_chance + max_count |

## Archetype: Ranger/Scout (Issue 3 clarification)

Not just a "ranged warrior" — distinct archetype with stealth identity:
- Focus: stealth, ranged weapons, light armor
- Natural evolution toward Thief archetype later
- Base HP: 8 (between Warrior 10 and Scholar 6)
- DEX primary stat (vs STR for Warrior, INT for Scholar)
- Weapons: bows, crossbows, throwing weapons, short swords
- Armor: light (leather, studded leather — no chain/plate)
- **Not in V2 initial launch** — Warrior and Scholar ship first. Ranger/Scout added in a future update once the two-archetype system is proven.
- The `allowed_classes: ["ranger"]` references already in weapon DB are forward-compatible.

## Enemy Skills System (Issue 13)

Enemy `skills_json` enables realistic opposed skill tests:

```
Player attempts Stealth:
  → Resolver checks enemy.skills_json.perception
  → If present: use that rank as the enemy's counter-roll bonus
  → If absent: use tier default (weak=0, standard=1, elite=2, boss=3)

Player attempts Persuasion vs NPC who is also enemy:
  → Resolver checks skills_json.insight (or fallback)

Goblin Scout example:
  skills_json: {"perception": 1, "stealth": 2, "athletics": 1}
  → Player sneaking past: Stealth vs Perception(1)
  → Goblin sneaking: admin can flag this in encounters

Vampire Lord example:
  skills_json: {"perception": 4, "insight": 3, "persuasion": 4}
  → Player trying to read vampire's intentions: Insight vs Perception(4)
```

Admin sets skills_json in the enemies panel. Empty `{}` = use tier defaults everywhere.
