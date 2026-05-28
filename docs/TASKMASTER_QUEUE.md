# TaskMaster Queue — Phase 2 & Beyond

Created after balance test + loot audit (2026-05-28).

## High Priority (Next Sprint)

### Task 1: Implement Shop NPC System ✓ DONE
- **Note**: System was pre-built (Phase 9A-4) using npcs.is_shop + npcs.shop_inventory_json. Not separate tables as proposed.
- **Deliverables**:
  - ✓ Backend: GET /api/shop/{npc_id}, POST buy, POST sell, GET /by-key/{key}
  - ✓ GM prompt: OPEN SHOP hard rule in system_prompt.txt
  - ✓ Admin UI: 🛒 inventory editor modal on shop NPC rows (admin_panel_v3)
  - ✓ GitHub issue #161
- **Architecture**: npcs.is_shop=1 + npcs.shop_inventory_json ([{type,key},...]) — simpler than proposed, works with existing NPC catalog

### Task 2: Seed Test Shops to DEV Database ✓ DONE
- **Deliverables**:
  - ✓ merchant_aldric: shortsword, health_potion, torch
  - ✓ blacksmith_goran: shortsword, shortbow, leatherarmor
  - ✓ seed_pending_npc_borys: healing_potion, rope_hemp, torch, bandage
- **Note**: Qty limits not implemented (Phase 2). Pricing uses catalog value_gp.

### Task 3: Audit & Tune Loot Drop Rates ✓ DONE
- **Deliverables**:
  - ✓ Fix 4 zero-gold tables (ad31b59)
  - ✓ 4 seed_pending enemies: drop_chance fixed (1.0 → tier-appropriate), gold seeded, loot entries added
  - ✓ Goblin: already had 4 items, 0 empty entries (audit doc was stale)
  - ✓ Rarity distribution verified: 77% common, 23% uncommon, 0% rare — meets target
  - ✓ 0 truly-empty entries across 93 tables / 524 total entries
  - ✓ LOOT_TABLE_AUDIT.md updated with final state + Phase 2/3 TODO
  - ✓ GitHub issue #162
- **Reference**: `docs/LOOT_TABLE_AUDIT.md`

### Task 4: Implement Difficulty Scaling (Level-based) ✓ DONE
- **Description**: Adjust enemy AC/HP/damage based on character level
- **Deliverables**:
  - ✓ Enemy AC scaling: `base_ac + (level-1) // 3`
  - ✓ Enemy HP scaling: `base_hp × (1.0 + 0.1 × (level-1))` — unchanged at L1, +10%/level
  - ✓ Enemy damage bonus: `(level-1) // 2` — flat bonus to roll (+0 L1, +1 L3, +2 L5, +4 L9)
  - ✓ GitHub issue #160
- **Note**: XP + level formula were pre-existing in `xp_service.py`. Only missing piece was wiring level into `combat_service.initiate_combat()`.
- **Impact**: Prevents late-game trivialization; keeps encounters challenging
- **Effort**: 1 hour (pre-existing XP infra saved most work)
- **Testing**: Run sandbox combat at L1, L4, L7 — verify enemy stats match formula

## Medium Priority (Later Sprint)

### Task 5: Fresh Campaign Test (Full Playthrough) ✓ DONE
- **Character**: [TEST] Kiran, Level 8 (731 XP), campaign 1115
- **Results**:
  - ✓ Difficulty scaling: L8 goblin hp=14 (base 8×1.7), defense=13 (base 11+2), damage_bonus=3 — all 3 formulas correct
  - ✓ Shop cue: `open_shop_fallback_injected` logged for merchant_aldric. Bug fixed: npc_locations entries added via SQL.
  - ✓ Loot on victory: goblin kill → 3 gold awarded inline. Gold 30→33.
  - ✓ No loot on death: combat ended player_dead → loot_persisted=0, gold unchanged.
  - ✓ XP progression: 731 XP → L8, level correctly drives all scaling formulas.
  - ✓ Narrative flow: GM coherent across exploration, merchant interaction, combat.
- **Balance notes**:
  - 3 gold from goblin at L8 feels low. Phase 2 loot scaling (Task 6/7) still needed.
  - L8 goblin (hp=14) takes 2 shortsword hits to kill — good pace.
- **Bug found**: npc_locations fix is DEV-only SQL. Needs seed migration for fresh deployments.
- **GitHub**: See issue #163

### Task 6: Increase Loot Item Drop Rates (Phase 2) ✓ DONE
- **Deliverables**:
  - ✓ loot_bandit_archer: 1 entry → 7 entries (shortbow 30, dagger 20, rope_hemp 20, leather_gloves 15, bandage 15, belt_pouch 10, eye_drops_clarity 35). Total weight 145.
  - ✓ shop NPC npc_locations seeded in migrations (4 entries for merchant_aldric, blacksmith_goran, seed_pending_npc_borys)
  - ✓ seed_pending_npc_borys added to ADMIN_SEEDS (was DEV-only SQL)
  - ✓ GitHub issue #164
- **Note**: Goblin and bandit tables were already fine — Task 6 description was stale (based on pre-audit state). Real gap was bandit_archer at 1 entry only.

### Task 7: Rarity-based Loot Scaling ✓ DONE
- **Deliverables**:
  - ✓ `_ensure_rarity_loot_scaling()` migration: seeds rare/epic to all boss/elite tables on startup
  - ✓ Boss tables (10): +silent_guardian_blade (r=3, w=8), +silent_guardian_helm (r=3, w=6), +forgotten_sage_staff (r=4, w=3)
    → 8.5% rare, 1.8% epic per boss drop (target: 8% / 2%)
  - ✓ Elite tables (15): +ruin_explorer_cloak (r=2, w=6), +umbravale_explorer_bow (r=2, w=5), +silent_guardian_blade (r=3, w=5), +silent_guardian_helm (r=3, w=4)
    → 6.2% rare + 7.5% uncommon
  - ✓ GitHub issue #165
- **Note**: Standard/weak tables left as-is. Global rare rate still low (boss/elite kills are infrequent). Rare drops are meaningful moments, not routine.

## Low Priority (Future)

### Task 8: Shop Keeper Dialogue & Reputation ✓ DONE
- **Deliverables**:
  - ✓ context_injector: shop NPCs visible via `npc_locations` table; `[KUPIEC]` tag + `personality_json` traits + shop wares in GM prompt
  - ✓ npc_memory_service: `purchase_count` tracking; "stały klient" label at ≥5 purchases; shop NPC personality in known-NPC block
  - ✓ shop_service: `buy_item` increments `purchase_count` on `campaign_known_npcs`
  - ✓ migrations: `purchase_count` column added to `campaign_known_npcs`
  - ✓ GitHub issue #166
- **Note**: Reputation is purchase count only. Disposition change (friendly/hostile) based on count is deferred.

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
| ad31b59 | Loot table audit + zero-reward fix | ✓ Done |
| — | Shop NPC proposal doc | ✓ Done |
| — | Task 4: Difficulty scaling (initiate_combat) | ✓ Done — issue #160 |
| — | Task 1+2: Shop NPC system + seed | ✓ Done — issue #161 |
| — | Task 3: Loot audit + pending enemy fixes | ✓ Done — issue #162 |
| — | Task 5: Playtest — shop/scaling/loot verified | ✓ Done — issue #163 |
| 9e88620 | Task 6: archer loot expansion + shop NPC seed migration | ✓ Done — issue #164 |
| 60b81ce | Task 7: rarity loot scaling — boss/elite rare+epic drops | ✓ Done — issue #165 |
| 4fb9678 | Task 8: shopkeeper dialogue + purchase_count reputation | ✓ Done — issue #166 |

---

## Success Metrics

✓ **Phase 1 complete**: AC balance validated, UI improved, loot audited
→ **Phase 2 gates**: Shop system + difficulty scaling (enables deeper economy testing)
→ **Phase 3 gates**: Rarity scaling + item drop tuning (feel-good rewards)

