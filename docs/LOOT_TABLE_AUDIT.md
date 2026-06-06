# Loot Table Audit Report

## Summary (updated 2026-05-28)

Audited 93 active loot tables, 524 total entries (up from 509 after pending-enemy fixes). Final state:
- ✓ 0 zero-gold tables (all fixed)
- ✓ 0 truly-empty entries (item_key=NULL AND weapon_key=NULL AND consumable_key=NULL)
- ✓ Rarity distribution: ~77% common, ~23% uncommon, 0% rare/epic
- ✓ Drop chance tiers: boss/elite 1.0, standard 0.75, weak 0.5 (thematic lower: 0.1–0.3)

## Issues Found and Fixed

### CRITICAL (fixed ad31b59): Zero-reward tables
4 tables had gold_min=0 AND gold_max=0:
- `loot_ancient_vampire` → 5–15g ✓
- `loot_angry_farmer` → 5–15g ✓
- `loot_archer` → 5–15g ✓
- `loot_arena_fighter` → 5–15g ✓

### CRITICAL (fixed 2026-05-28): Empty pending-enemy loot tables
4 seed_pending enemies had drop_chance=1.0 but empty loot tables + gold=0:
- `seed_pending_enemy_bandyta_lucznik` (standard): drop_chance 1.0→0.75, gold 5–20g, 5 entries seeded (archer-themed)
- `seed_pending_enemy_pajak` (weak): drop_chance 1.0→0.5, gold 3–10g, 3 entries seeded (prey scraps)
- `seed_pending_enemy_kapitan_strazy` (elite): kept 1.0, gold 20–60g, 4 entries seeded
- `seed_pending_enemy_lich` (boss): kept 1.0, gold 50–150g, 3 entries seeded

### MINOR: Item-less tables
~10 tables are gold-only (no item entries). Intentional for thematic enemies (bandits loot purses, not gear).

### NOTE: Goblin table was already correct
Audit doc (Phase 1) described "85% nothing" for goblins. Actual DB state:
- hardtack (40), bandage (25), apple (20), rope_hemp (10) — all items, 0 empty entries
- The old description was stale or based on a pre-fix state. No action needed.

## Loot Table Structure

### Standard weak-enemy template (most standard-tier enemies)
```
35: potion_healing_small (consumable)
20: bandage (consumable)
15: dagger (weapon)
15: torch (item)
10: antitoxin_vial (consumable)
10: handaxe (weapon)
10: rope_hemp (item)
8:  leather_gloves (item)
Total: 123 weight
```
Distribution: 77% common, 23% uncommon, 0% rare → meets target

### Goblin (weak, thematic)
```
40: hardtack, 25: bandage, 20: apple, 10: rope_hemp
Total: 95 weight — scavenged food items
```

### Wolf (weak, animal)
```
50: wolf_pelt, 35: dried_meat, 15: rope_hemp
Total: 100 weight — thematic animal drops
```

## Drop Chance Tiers

| Tier | Standard drop_chance | Notes |
|------|---------------------|-------|
| weak | 0.5 | Most weak enemies |
| weak (social) | 0.1–0.3 | Angry_farmer 0.15, beggar 0.1 |
| standard | 0.75 | Most combat enemies |
| elite | 0.85–1.0 | Captain, enforcer etc. |
| boss | 1.0 | Always drops |

## Phase 2 / Phase 3 TODO

### Phase 2 (future)
- [ ] Thematic differentiation — cultist should drop ritual items, not generic bandage/dagger
- [ ] Level-scaling loot (higher-level enemies drop better items)
- [ ] Verify equipment prices match economy

### Phase 3 (polish)
- [ ] Weighted rarity system (common→uncommon→rare tags on items)
- [ ] Unique named items from bosses
- [ ] 100-enemy kill sampling test for distribution validation

## Database Queries

```sql
-- Check for zero-gold tables
SELECT key, gold_min, gold_max FROM game_config_loot_tables 
WHERE gold_min=0 AND gold_max=0 AND is_active=1;

-- Check for truly empty entries
SELECT COUNT(*) FROM game_config_loot_entries 
WHERE item_key IS NULL AND weapon_key IS NULL AND consumable_key IS NULL;

-- Distribution per table
SELECT loot_table_key, SUM(weight) as total_weight,
  COUNT(*) as entries FROM game_config_loot_entries GROUP BY loot_table_key ORDER BY total_weight;
```
