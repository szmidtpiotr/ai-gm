# Loot Table Audit Report

## Summary

Audited 93 active loot tables, 509 total entries. Found:
- ✓ Most tables properly configured (gold + items)
- ⚠️ 10+ tables have NO item/weapon/consumable entries (gold-only)
- ⚠️ 4 tables have gold_min=0 AND gold_max=0 (no rewards at all!)
- ✓ No tables with excessive empty weight (>75%)

## Issues Found

### CRITICAL: Zero-reward tables
4 tables with no gold range:
- `loot_ancient_vampire`
- `loot_angry_farmer`
- `loot_archer`
- `loot_arena_fighter`

**Fix**: Set gold_min=5, gold_max=15 for consistency with similar enemies.

### MINOR: Item-less tables
~10 tables exist as gold-only drops (no weapons/armor/consumables):
- `loot_bandit` — only gold (5-25g)
- `loot_assassin` — only gold
- etc.

**Assessment**: OK for weak/thematic enemies (bandits loot purses, not gear). Document intent.

### MINOR: Goblin drop rate (revisited)
`loot_goblin` structure:
```
40% nothing
25% nothing
20% nothing
10% rope_hemp (qty 1)
5% ? (check if more items exist)
```

Result: 85% "nothing" → 10% item drop. Sparse but intentional for weak enemies. 

**Tuning option**: Reduce empty weight from 40+25+20 → 30+20+15 = 65%, giving 25% item drop instead of 10%.

## Recommendations

### Phase 1 (Critical)
- [ ] Fix 4 zero-gold tables → set gold_min=5, gold_max=15
- [ ] Verify all enemies have valid loot_table_key assignment

### Phase 2 (Enhancement)
- [ ] Review weak-enemy drop rates (goblin 10% → 25% item drop)
- [ ] Audit rarity distribution (are epics dropping too often?)
- [ ] Verify equipment prices match economy (100g sword vs 30g gold drop = 3+ kills to afford)

### Phase 3 (Polish)
- [ ] Weighted rarity in rolls (common→uncommon→rare progression)
- [ ] Level-scaling loot (higher-level enemies drop better items)
- [ ] Unique named items from bosses

## Database Queries

Check all tables for zero-reward:
```sql
SELECT key, gold_min, gold_max FROM game_config_loot_tables 
WHERE gold_min=0 AND gold_max=0 AND is_active=1;
```

Review goblin table:
```sql
SELECT e.weight, e.item_key, e.weapon_key, e.consumable_key
FROM game_config_loot_entries e
WHERE e.loot_table_key='loot_goblin'
ORDER BY e.weight DESC;
```

## Next Steps

1. Fix 4 zero-gold tables (5-min work)
2. Re-test loot drops with fixed tables
3. Document loot philosophy in game design wiki
4. Plan Phase 2 tuning (after shop system live)

