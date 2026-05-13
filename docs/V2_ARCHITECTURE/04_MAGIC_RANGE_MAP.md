# AI-GM V2 — Magic, Range & Map Systems

> Covers: Scholar magic mechanics, spell progression, miscast, range zones, ranged weapons, and map system scope.

---

## 1. Scholar Magic System

### Core Philosophy

WFRP risk philosophy + D&D Mana structure. Magic works reliably unless you roll a natural 1 — then something goes wrong (miscast). The danger of magic scales with the Scholar's power: a level 1 Scholar learning their first spell is clumsy, a level 5 Scholar who miscasts faces real consequences.

### Spell Resolution — Two Types

**Type A: Offensive spells (attack roll)**
```
Roll: d20 + INT modifier vs enemy AC
Hit:   spell damage applied
Miss:  nothing (Mana still spent)
Nat 20: double damage + secondary effect (stun, knockback — LLM narrates)
Nat 1:  MISCAST (see table below)
```

**Type B: Effect spells (saving throw)**
```
Enemy rolls: d20 + relevant stat vs DC = 10 + Scholar's INT modifier
Fail save:   full effect applied
Pass save:   effect reduced or negated
Nat 1 on Scholar's INT check to cast: MISCAST
```

The DC scales with Scholar's INT investment. INT 14 (mod +2) → DC 12. INT 18 (mod +4) → DC 14. High INT Scholar is harder to resist.

### Miscast Table (Nat 1 on any spell cast)

| Scholar Level | Result |
|---|---|
| 1–2 | Spell fails. Mana wasted. Skip next action (stunned). **No HP loss** — Scholar is still learning. |
| 3–4 | Spell fails. Mana wasted. 1d4 self-damage. |
| 5–7 | Spell fails. Mana wasted. 1d6 self-damage + stunned 1 round. |
| 8–10 | Spell fails. Mana wasted. 1d8 self-damage + stunned 1 round + random secondary effect (d4: 1=enemy healed 1d4, 2=nearby ally also takes 1d4, 3=spell hits scholar, 4=just the base penalty). |

Design rationale: Scholar at level 1 has 6 HP. A 1d4 miscast at that HP would be disproportionately punishing. The stun-only penalty still makes Nat 1 feel bad without being potentially lethal.

### Nat 20 Secondary Effects (d6 per spell type)

The system rolls d6, Mechanic Resolver determines effect, LLM narrates it:

| Roll | Effect |
|---|---|
| 1–2 | Double damage only |
| 3–4 | Double damage + target stunned 1 round |
| 5 | Double damage + target knocked to RANGED zone (or ENGAGED if already ranged) |
| 6 | Double damage + enemy condition applied (Burning, Bleeding, etc.) |

---

## 2. Spell List

### Available Spells by Tier

Tier determines when spells can be learned. Each tier unlocks at specific levels:
- **Tier 1** — available at Scholar creation (level 1)
- **Tier 2** — available from level 2
- **Tier 3** — available from level 3
- **Tier 4** — available from level 4
- **Tier 5** — available from level 5

| Spell | Tier | Mana Cost | Type | Base Effect | Range |
|---|---|---|---|---|---|
| Mend Wounds | 1 | 2 | Heal | 2d6+INT HP (self) | Self |
| Magic Bolt | 1 | 2 | Attack | 2d6+INT damage | Any zone |
| Arcane Shield | 1 | 2 | Defense | +3 AC for 1 round | Self |
| Sleep | 2 | 3 | Effect (WIS save) | Skip 1 turn | Any zone |
| Burning Arc | 2 | 4 | AoE Attack | 1d6+INT to ALL enemies | Ignores zones |
| Drain Life | 3 | 3 | Attack | 2d8+INT, heal 50% of damage | **ENGAGED only** |
| Chain Lightning | 4 | 5 | AoE Attack | 2d6+INT to up to 3 targets | Any zone |
| Stone Skin | 4 | 4 | Defense | +5 AC for 3 rounds | Self |
| Fireball | 5 | 6 | AoE Attack | 3d6+INT to ALL enemies | Ignores zones |

Starting spells (level 1 Scholar picks 2 from Tier 1): Mend Wounds, Magic Bolt, Arcane Shield.

---

## 3. Spell Progression — Learn or Upgrade

### Arcane Points

On each level-up, Scholar gains **1 Arcane Point**.

Spend Arcane Points on:
- **Learn** a new spell from the available tier pool → costs **1 pt**
- **Upgrade** a known spell to Rank 2 → costs **1 pt**
- **Upgrade** a known spell to Rank 3 → costs **2 pts**

### The Specialist vs Generalist Choice

A level 5 Scholar has earned 4 Arcane Points total. Examples:

| Build | Spells | How they spent pts |
|---|---|---|
| Bolt Specialist | Magic Bolt (Rank 3) + Sleep (Rank 1) | Bolt R2(1pt), Bolt R3(2pt), Sleep(1pt) |
| Battle Mage | Magic Bolt R1, Burning Arc R1, Drain Life R1, Chain Lightning R1 | 4 × learn(1pt each) |
| Healer | Mend Wounds (Rank 3) + Magic Bolt R1 | Mend R2(1pt), Mend R3(2pt), Bolt(1pt) |

### Spell Upgrade Tiers

Each upgrade improves effectiveness and/or reduces Mana cost. Rank 3 always gives Mana efficiency reward.

| Spell | Rank 1 | Rank 2 | Rank 3 |
|---|---|---|---|
| Magic Bolt | 2d6+INT, 2M | 2d8+INT, 2M | 3d6+INT, **1M** |
| Mend Wounds | 2d6+INT, 2M | 2d8+INT, 2M | 3d6+INT, **1M** |
| Arcane Shield | +3 AC 1 round, 2M | +4 AC 1 round, 2M | +4 AC **2 rounds**, 1M |
| Sleep | DC 10+INT, 1 turn, 3M | DC 12+INT, 2 turns, 3M | DC 14+INT, 3 turns, **2M** |
| Burning Arc | 1d6+INT all, 4M | 1d8+INT all, 4M | 2d6+INT all, **3M** |
| Drain Life | 2d8+INT, heal 50%, 3M | 2d10+INT, heal 50%, 3M | 3d6+INT, **heal 100%**, 2M |
| Stone Skin | +5 AC 3 rounds, 4M | +5 AC 4 rounds, 4M | +6 AC 4 rounds, **2M** |

---

## 4. Range System

### Two Combat Zones

```
┌──────────────────┬───────────────────┐
│   RANGED ZONE    │   ENGAGED ZONE    │
│                  │                   │
│  👤 Scholar(auto)│  👤 Warrior(auto) │
│  🏹 Goblin Archer│  ⚔️ Goblin Scout  │
│                  │  🐺 Wolf          │
└──────────────────┴───────────────────┘
```

### Default Positioning

| Entity | Starts in |
|---|---|
| Warrior | ENGAGED |
| Scholar | RANGED |
| Melee enemies (goblin, wolf, troll) | ENGAGED |
| Ranged enemies (archer, mage) | RANGED |

### Zone Change Rules

- Costs the combat turn action (no attack that turn)
- Frontend button: Scholar sees `[→ Close in]`, Warrior sees `[← Step back]`
- Enemies can charge: melee enemy uses action to move RANGED→ENGAGED
- Fast enemies (wolf, vampire): may charge as FREE action (defined in behavior profile: `free_charge: true`)
- Enclosed location (sealed room, narrow corridor): RANGED zone may be unavailable — flee button also disabled

### Attack Rules by Zone

| Weapon / Spell | Hits RANGED enemies | Hits ENGAGED enemies | Notes |
|---|---|---|---|
| Sword / Axe / Fist | ❌ | ✅ | Melee only |
| Spear / Polearm | ❌ | ✅ | +1 ATK (reach advantage) |
| Dagger (melee) | ❌ | ✅ | — |
| Dagger (thrown) | ✅ | ✅ | Short range, works both |
| Bow | ✅ RANGED | ⚠️ ENGAGED | -2 ATK penalty in ENGAGED |
| Crossbow | ✅ RANGED | ⚠️ ENGAGED | -3 ATK in ENGAGED, reload every 2nd turn |
| Magic Bolt / Chain Lightning | ✅ | ✅ | Full power regardless of zone |
| Burning Arc / Fireball (AoE) | ✅ | ✅ | Hits ALL enemies ignoring zones |
| Drain Life | ❌ | ✅ | Touch spell — must be ENGAGED |
| Sleep / Effect spells | ✅ | ✅ | Range irrelevant for saving throw spells |
| Arcane Shield / Stone Skin | — | — | Self-cast, no targeting |

### Ranged Weapons — Archetype Neutral

Crossbows and bows do the same damage regardless of who uses them. It's a mechanical device — aim and shoot.

```
Crossbow:
  Damage:    1d8
  ATK roll:  d20 + DEX modifier
  Reload:    Every 2nd turn (can't fire two rounds in a row)
  ENGAGED penalty: -3 ATK

Bow:
  Damage:    1d6
  ATK roll:  d20 + DEX modifier
  Reload:    None (fire every round)
  ENGAGED penalty: -2 ATK

Thrown dagger:
  Damage:    1d4 + STR modifier
  ATK roll:  d20 + DEX modifier
  No penalty in either zone
  Limited ammo (3 daggers per inventory slot)
```

**Warrior with crossbow vs Scholar with crossbow:** Identical roll and damage. Only DEX modifier differs. Warrior default DEX 12 (+1), Scholar default DEX 11 (+0). Warrior is marginally better by default, Scholar better if they invested DEX points.

**Proficiency note:** No special proficiency needed for crossbow (mechanical — anyone can use it). Bow benefits from Archery skill rank — +1 ATK per 2 ranks (rank 2 = +1, rank 4 = +2).

---

## 5. Map System

### Map A — World/Campaign Map (Build in Phase 09)

Shows macro-locations as nodes connected by travel routes. Admin defines the map layout in the admin panel. Player sees their current position and visited/unvisited locations.

**DB additions needed:**
```sql
-- Add to game_locations:
ALTER TABLE game_locations ADD COLUMN map_x REAL DEFAULT NULL;
ALTER TABLE game_locations ADD COLUMN map_y REAL DEFAULT NULL;
ALTER TABLE game_locations ADD COLUMN map_icon TEXT DEFAULT 'town'; -- town/dungeon/forest/ruin/etc

-- New table for explicit connections:
CREATE TABLE location_connections (
    id INTEGER PRIMARY KEY,
    from_location_key TEXT NOT NULL,
    to_location_key TEXT NOT NULL,
    travel_hours REAL DEFAULT 1.0,
    travel_description TEXT,   -- "Forest road, moderately dangerous"
    requires_item_key TEXT DEFAULT NULL,  -- locked gate, boat needed, etc.
    is_active INTEGER DEFAULT 1
);
```

**Frontend display:**
- SVG node-edge graph
- Visited locations: full colour
- Unvisited: greyed out / fog (admin can configure whether world is pre-revealed or fog-of-war)
- Player marker: 📍 on current location
- Hover on edge: shows travel time + description
- Click on accessible location: attempts MOVEMENT action (goes through WSM validation)

**Admin panel:**
- Drag locations to set coordinates
- Draw connections between them
- Set travel time and description per connection
- Toggle fog-of-war per location (some locations might be known to everyone, others discovered)

### Map B — Combat Zone Display (Build in Phase 05)

Simple two-panel indicator in the combat UI. Not a spatial grid — just zone assignment.

```
┌─────────────────────────────────────┐
│ ⚔️ COMBAT — Round 2                 │
├──────────────┬──────────────────────┤
│   RANGED     │      ENGAGED         │
│              │                      │
│  👤 Aldric   │   ⚔️ Goblin Scout    │
│              │   🐺 Wolf (charging!)│
├──────────────┴──────────────────────┤
│ [⚔ Attack] [🏃 Flee] [🧪 Item]     │
│ [→ Close in]                        │
└─────────────────────────────────────┘
```

Updates live after each action. "Charging!" indicator when enemy spends action to close distance. Zone change button always visible (greyed out if costs would be wasted).

### Map C — Dungeon/Room Map (Phase 11+, Future)

Room-by-room exploration map revealed as player visits sub-locations within a dungeon macro.

- Each `game_locations` record with `location_type = 'sub'` becomes a room
- Rooms connected via `location_connections` (same table as world map)
- Revealed when player visits (fog of war on unexplored rooms)
- Shows: current room (📍), visited rooms, connections/doors, known enemy presence, loot markers
- Admin draws the dungeon layout in admin panel using the same drag-and-connect interface as the world map

---

## Summary of Decisions Made

| Topic | Decision |
|---|---|
| Spell attack type | Offensive = attack roll (INT vs AC), Effect = saving throw (DC = 10+INT) |
| Miscast trigger | Nat 1 on any spell cast |
| Miscast level 1-2 | Stun only, no HP loss |
| Miscast level 3-4 | 1d4 self-damage |
| Miscast level 5+ | 1d6 self-damage + stun |
| Spell progression | Arcane Points — learn new OR upgrade existing (choose each level-up) |
| Upgrade tiers | 3 ranks. Rank 3 always gives Mana efficiency reward |
| Ranged weapon damage | Same regardless of archetype — DEX modifier determines accuracy |
| Crossbow | d8 damage, -3 in ENGAGED, 2-turn reload |
| Bow | d6 damage, -2 in ENGAGED, fire every turn |
| Combat zones | ENGAGED / RANGED. Scholar auto-RANGED, Warrior auto-ENGAGED |
| Zone change | Costs combat action, button in UI |
| AoE spells | Hit all enemies, ignore zones |
| Touch spells (Drain Life) | ENGAGED only |
| Maps to build | World map (Phase 09), Combat zones (Phase 05), Dungeon map (Phase 11+) |
