# TaskMaster Queue — Phase 2 & Beyond

Created after balance test + loot audit (2026-05-28).

## High Priority (Next Sprint)

### Task 1: Implement Shop NPC System
- **Description**: Create `game_config_shops` + `game_shop_inventory` DB tables
- **Deliverables**:
  - Schema: shops table (key, label, npc_type, location_key, base_markup, stock_reset_hours)
  - Schema: inventory table (shop_key, item_key, qty_available, qty_base, sell_price, buy_price)
  - Endpoints: `GET /api/shop/{key}/inventory`, `POST /api/shop/{key}/buy`, `POST /api/shop/{key}/sell`
  - GM prompt integration: suggest shops, render keeper dialogue
  - Admin UI: shop inventory browser in admin_panel_v3
- **Reference**: `docs/SHOP_NPC_PROPOSAL.md`
- **Dependency**: None (can run in parallel)
- **Effort**: 6-8 hours

### Task 2: Seed Test Shops to DEV Database
- **Description**: Add 3 starter shops + baseline inventory
- **Deliverables**:
  - Tavern Czarnogrodu: healing potions (5×50g), bread (10×5g)
  - Blacksmith Halafarda: longsword (2×300g), chainmail (1×500g)
  - General Store: rope (qty 3), torches (qty 8), herbs (qty 4)
  - Set base_markup=1.15–1.5, stock_reset_hours=24
  - Link to existing campaign locations
- **Dependency**: Task 1 (tables must exist)
- **Effort**: 1 hour

### Task 3: Audit & Tune Loot Drop Rates
- **Description**: Review all 93 loot tables, optimize weak-enemy drops
- **Deliverables**:
  - ✓ Fix 4 zero-gold tables (DONE)
  - ✓ Document in `LOOT_TABLE_AUDIT.md` (DONE)
  - Reduce goblin empty weight: 85% → 65% (increase item drop 10% → 25%)
  - Review other weak-enemy tables (bandit, cultist, etc.)
  - Verify rarity distribution (common should be 70%+, rare <5%)
- **Reference**: `docs/LOOT_TABLE_AUDIT.md`
- **Dependency**: None
- **Effort**: 3 hours
- **Testing**: Rerun balance test after changes

### Task 4: Implement Difficulty Scaling (Level-based)
- **Description**: Adjust enemy AC/HP/damage based on character level
- **Deliverables**:
  - Enemy AC scaling: base_ac + (level / 3)
  - Enemy HP scaling: base_hp × (0.8 + 0.1 × level)
  - Enemy damage scaling: base_dmg × (1.0 + 0.05 × level)
  - Document scaling in `system_prompt.txt`
- **Impact**: Prevents late-game trivialization; keeps encounters challenging
- **Dependency**: None (independent feature)
- **Effort**: 4 hours
- **Testing**: Run campaign through levels 3, 5, 7+

## Medium Priority (Later Sprint)

### Task 5: Fresh Campaign Test (Full Playthrough)
- **Description**: New hero from start, play through 3+ acts, validate economy + balance
- **Goals**:
  - Verify XP/level-up curve (when does level-up happen?)
  - Test shop system once live
  - Confirm loot drop tuning feels rewarding
  - Document balance signals
- **Effort**: 4-6 hours (manual play)
- **Success criteria**: Campaign reaches level 5+ with meaningful progression

### Task 6: Increase Loot Item Drop Rates (Phase 2)
- **Description**: Post-tuning, increase item drop chances for weak enemies
- **Deliverables**:
  - Goblin: 85% empty → 65% empty (10% item → 25% item)
  - Bandit: Reduce empty weight, add equipment drops
  - Verify distribution still feels random (not predictable)
- **Dependency**: Task 3 (audit must be complete)
- **Effort**: 2 hours

### Task 7: Rarity-based Loot Scaling
- **Description**: Rare/epic items should be scarce; common items common
- **Deliverables**:
  - Review all 93 tables: tag entries by rarity (common/uncommon/rare/epic)
  - Adjust weights: common 70%, uncommon 20%, rare 8%, epic 2%
  - Test distribution via 100-enemy kill sampling
- **Dependency**: Task 3
- **Effort**: 5 hours

## Low Priority (Future)

### Task 8: Shop Keeper Dialogue & Reputation
- **Description**: Dynamic NPC personality + player reputation system
- **Effort**: 8+ hours (involves GM prompt tuning)

### Task 9: Rental System (Borrow gear, pay daily)
- **Description**: Allow players to rent expensive items instead of buying
- **Effort**: 4 hours

### Task 10: Trade-in System (Old equipment → discount)
- **Description**: Sell old sword, get discount on new one
- **Effort**: 2 hours

---

## Commit Log

| Commit | Task | Status |
|---|---|---|
| f783f00 | AC balance + biome mapping | ✓ Done |
| c167fbb | Admin UI: foldable arcs + uncovered hexes | ✓ Done |
| — | Loot table audit + zero-reward fix | ✓ Done (inline) |
| — | Shop NPC proposal doc | ✓ Done |

---

## Success Metrics

✓ **Phase 1 complete**: AC balance validated, UI improved, loot audited
→ **Phase 2 gates**: Shop system + difficulty scaling (enables deeper economy testing)
→ **Phase 3 gates**: Rarity scaling + item drop tuning (feel-good rewards)

