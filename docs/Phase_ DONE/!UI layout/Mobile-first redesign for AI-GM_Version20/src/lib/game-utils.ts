/**
 * AI-GM Game Utilities
 * Helper functions for game mechanics
 */

/**
 * Roll a dice with format "NdX" (e.g., "1d20", "2d6")
 */
export function rollDice(notation: string): number {
  const [numDice, sides] = notation.split("d").map(Number);
  let total = 0;
  for (let i = 0; i < numDice; i++) {
    total += Math.floor(Math.random() * sides) + 1;
  }
  return total;
}

/**
 * Calculate ability modifier from ability score
 */
export function getModifier(abilityScore: number): number {
  return Math.floor((abilityScore - 10) / 2);
}

/**
 * Format modifier for display (e.g., +3, -1)
 */
export function formatModifier(modifier: number): string {
  return modifier >= 0 ? `+${modifier}` : modifier.toString();
}

/**
 * Calculate HP color based on percentage
 */
export function getHpColor(hp: number, maxHp: number): string {
  const percent = (hp / maxHp) * 100;
  if (percent > 60) return "var(--hp-high)";
  if (percent > 30) return "var(--hp-mid)";
  return "var(--hp-low)";
}

/**
 * Generate random enemy encounter
 */
export function generateEnemy(level: number) {
  const enemies = [
    { name: "Goblin Łotrzyk", hpMultiplier: 1.0, armorBonus: 0 },
    { name: "Wilk Szary", hpMultiplier: 1.2, armorBonus: 1 },
    { name: "Szkielet Wojownika", hpMultiplier: 1.4, armorBonus: 2 },
    { name: "Ork Łupieżca", hpMultiplier: 1.6, armorBonus: 3 },
    { name: "Troglodyta", hpMultiplier: 1.3, armorBonus: 1 },
    { name: "Zombie", hpMultiplier: 1.5, armorBonus: 0 },
  ];

  const template = enemies[Math.floor(Math.random() * enemies.length)];
  const baseHp = 10 + level * 5;
  const maxHp = Math.floor(baseHp * template.hpMultiplier);
  const armor = 10 + level + template.armorBonus;

  return {
    name: template.name,
    hp: maxHp,
    maxHp,
    level,
    armor,
  };
}

/**
 * Generate loot after combat
 */
export function generateLoot(enemyLevel: number) {
  const gold = Math.floor(Math.random() * (enemyLevel * 20)) + 10;

  const itemPool = [
    { name: "Zardzewiały miecz", type: "weapon" as const, rarity: "common" as const },
    { name: "Skórzana zbroja", type: "armor" as const, rarity: "common" as const },
    { name: "Eliksir leczenia", type: "item" as const, rarity: "common" as const },
    { name: "Srebrny sztylet", type: "weapon" as const, rarity: "uncommon" as const },
    { name: "Magiczny amulet", type: "item" as const, rarity: "rare" as const },
    { name: "Zwój teleportacji", type: "item" as const, rarity: "rare" as const },
  ];

  const numItems = Math.floor(Math.random() * 3) + 1;
  const items = [];

  for (let i = 0; i < numItems; i++) {
    const item = itemPool[Math.floor(Math.random() * itemPool.length)];
    items.push({
      id: `${Date.now()}-${i}`,
      ...item,
      amount: item.type === "item" ? Math.floor(Math.random() * 3) + 1 : undefined,
    });
  }

  return { items, gold };
}

/**
 * Vibration feedback for mobile devices
 */
export function vibrate(pattern: number | number[] = 10) {
  if (typeof navigator !== "undefined" && navigator.vibrate) {
    navigator.vibrate(pattern);
  }
}

/**
 * Play sound effect (placeholder for future implementation)
 */
export function playSound(soundId: string) {
  // Future: Load and play audio file
  console.log(`[Sound] ${soundId}`);
}

/**
 * Format timestamp
 */
export function formatTime(date: Date = new Date()): string {
  return date.toLocaleTimeString("pl-PL", {
    hour: "2-digit",
    minute: "2-digit",
  });
}

/**
 * Check if attack hits
 */
export function checkHit(
  attackRoll: number,
  attackModifier: number,
  targetArmor: number
): boolean {
  return attackRoll + attackModifier >= targetArmor;
}

/**
 * Calculate damage
 */
export function calculateDamage(
  baseDice: string,
  modifier: number = 0
): { roll: number; modifier: number; total: number } {
  const roll = rollDice(baseDice);
  const total = roll + modifier;
  return { roll, modifier, total };
}
