// KROK 5 (#1234) — powierzchnia karty postaci w obrębie gry. Renderuje aktywny
// panel + (mobile) górny poziomy scroll przełącznika. Desktop przełącza lewy rail
// (GameRail) — wtedy górny scroll jest ukryty (lg:hidden).
import { cn } from "@/lib/utils";
import { useAppStore, type GameTab } from "@/store/appStore";
import { useCharacter } from "@/hooks/useGameData";
import {
  useInventory,
  useReputation,
  useSpellCatalog,
  useSpells,
  useEquipItem,
} from "@/hooks/useSheetData";
import { readVitals } from "@/lib/game";
import { visibleSheetTabs } from "./tabs";
import { PanelCharacter } from "./PanelCharacter";
import { PanelSkills } from "./PanelSkills";
import { PanelSpells } from "./PanelSpells";
import { PanelInventory } from "./PanelInventory";
import { PanelReputation } from "./PanelReputation";

export function CharacterSheet({ characterId }: { characterId: number | undefined }) {
  const panel = useAppStore((s) => s.gameTab);
  const setGameTab = useAppStore((s) => s.setGameTab);

  const character = useCharacter(characterId);
  const sheet = character.data?.sheet_json;
  const race = character.data?.race;
  const hasMana = readVitals(sheet).hasMana;
  const level = readVitals(sheet).level;

  // Server-state per panel (leniwie via enabled — pobiera tylko potrzebny panel).
  const inventory = useInventory(panel === "inventory" ? characterId : undefined);
  const spells = useSpells(panel === "spells" ? characterId : undefined);
  const catalog = useSpellCatalog(panel === "spells");
  const reputation = useReputation(panel === "reputation" ? characterId : undefined);
  const equip = useEquipItem(characterId);

  const tabs = visibleSheetTabs(hasMana);
  // Panel „spells" znika dla nie-maga → cofnij na Postać.
  const active: GameTab = tabs.some((t) => t.key === panel) ? panel : "character";

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      {/* Mobile: górny poziomy scroll przełącznika paneli (desktop = rail) */}
      <div className="flex gap-0.5 overflow-x-auto border-b border-line bg-surface px-2 [scrollbar-width:none] lg:hidden [&::-webkit-scrollbar]:hidden">
        {tabs.map((t) => {
          const Icon = t.icon;
          const on = active === t.key;
          return (
            <button
              key={t.key}
              onClick={() => setGameTab(t.key)}
              className={cn(
                "flex shrink-0 items-center gap-1.5 whitespace-nowrap border-b-2 px-3 pb-2.5 pt-3 font-ui text-[11.5px] font-semibold uppercase tracking-[0.06em] transition-colors",
                on ? "border-ember text-ember-glow" : "border-transparent text-text-3 hover:text-text-2",
              )}
            >
              <Icon size={14} weight={on ? "fill" : "regular"} />
              {t.label}
            </button>
          );
        })}
      </div>

      {active === "character" && <PanelCharacter sheet={sheet} />}
      {active === "skills" && <PanelSkills sheet={sheet} />}
      {active === "spells" && (
        <PanelSpells
          sheet={sheet}
          race={race}
          known={spells.data}
          catalog={catalog.data}
          level={level}
          loading={spells.isLoading || catalog.isLoading}
        />
      )}
      {active === "inventory" && (
        <PanelInventory
          sheet={sheet}
          items={inventory.data}
          loading={inventory.isLoading}
          busy={equip.isPending}
          onEquip={(id, slot) => equip.mutate({ inventoryId: id, slot })}
        />
      )}
      {active === "reputation" && <PanelReputation sheet={sheet} reputation={reputation.data} />}
    </div>
  );
}
