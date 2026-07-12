// FE10 (#1237) — harness podglądu modali wyników walki dla weryfikacji 1:1 z
// makietami (Playwright). Renderuje jeden modal na fixture'ach wg ?m=. Publiczny,
// bez danych z backendu — służy TYLKO do wizualnego QA (parytet z zar7/zar9).
import { useSearchParams } from "react-router-dom";
import type { DropComparison, LootItem } from "@/lib/types";
import { CombatEndModal } from "@/components/game/outcomes/CombatEndModal";
import { DeathScreen } from "@/components/game/outcomes/DeathScreen";
import { DungeonVictoryModal } from "@/components/game/outcomes/DungeonVictoryModal";
import { DropCelebration } from "@/components/game/outcomes/DropCelebration";

const LOOT: LootItem[] = [
  { label: "24 sztuki złota", source_type: "item", qty: 1 },
  { label: "Mikstura leczenia", source_type: "consumable", qty: 1 },
  { label: "Kieł Wyjca", source_type: "weapon", is_special: true, qty: 1 },
  { label: "Zwój kusznika", source_type: "item", qty: 1 },
];

const DROP: DropComparison = {
  inventory_id: 12,
  name: "Kostur Mglistego Brodu",
  item_type: "weapon",
  rarity: 3,
  rarity_label: "Rzadki",
  is_special: true,
  suggested_slot: "main_hand",
  affixes: [{ name: "Rdzeń topielczego dębu", effects: [{ type: "damage_bonus", value: 1 }] }],
  diff: { damage: 1, attack_bonus: 0 },
  new: { damage: 8, attack_bonus: 1 },
  equipped: { damage: 6, attack_bonus: 1 },
} as DropComparison;

export default function OutcomePreview() {
  const [sp] = useSearchParams();
  const m = sp.get("m") || "combat-end";
  const noop = () => {};

  return (
    <div className="fixed inset-0 bg-bg">
      {m === "combat-end" && (
        <CombatEndModal
          title="Walka wygrana"
          subtitle="Wyjec i Kusznik pokonani · 3 rundy"
          xpGain={85}
          goldGain={24}
          hp={17}
          maxHp={28}
          lifetime={425}
          loot={LOOT}
          claiming={false}
          onTake={noop}
          onSkip={noop}
        />
      )}
      {m === "death" && (
        <DeathScreen
          heroName="Wiga"
          epitaph="Rozdarta przez Wyjca w karczmie «Pod Utopionym Dzwonem», noc dwunastego dnia. Młynarz z Wilczburga tak i pozostał nieodnaleziony."
          level={4}
          turns={48}
          days={12}
          reviveEnabled
          reviveDesc="Powrót w miejscu śmierci · kara 20% XP"
          reviving={false}
          onRevive={noop}
          onNewAdventure={noop}
          onOtherHero={noop}
        />
      )}
      {m === "dungeon" && (
        <DungeonVictoryModal
          title="Krypta Utopionego Dzwonu oczyszczona"
          subtitle="Wyjec-Matka legła u twych stóp. Krypta milknie."
          xpGain={240}
          goldGain={150}
          defeated={11}
          rooms={6}
          busy={false}
          onDeeper={noop}
          onExit={noop}
        />
      )}
      {/* levelup: modal wycofany (F-27 V2 [D12] — awans przez ekran AdvancementScreen, nie modal) */}
      {m === "drop" && (
        <DropCelebration drop={DROP} equipping={false} onEquip={noop} onClose={noop} />
      )}
    </div>
  );
}
