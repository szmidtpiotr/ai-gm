// KROK 5 (#1234) — powierzchnia karty postaci w obrębie gry. Renderuje aktywny
// panel + (mobile) górny poziomy scroll przełącznika. Desktop przełącza lewy rail
// (GameRail) — wtedy górny scroll jest ukryty (lg:hidden).
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
import { useCharacterRecipes } from "@/hooks/useCrafting";
import { visibleSheetTabs } from "./tabs";
import { PanelCharacter } from "./PanelCharacter";
import { PanelSpells } from "./PanelSpells";
import { PanelInventory } from "./PanelInventory";
import { PanelRecipes } from "./PanelRecipes";
import { PanelReputation } from "./PanelReputation";
import { PanelCollections } from "./PanelCollections";

export function CharacterSheet({ characterId }: { characterId: number | undefined }) {
  const panel = useAppStore((s) => s.gameTab);

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
  // #1375 — zakładka Receptury widoczna dopiero po nauczeniu pierwszej receptury.
  const recipes = useCharacterRecipes(characterId);
  const hasRecipes = !!recipes.data?.has_any;

  const tabs = visibleSheetTabs(hasMana, hasRecipes);
  // Panel „spells" znika dla nie-maga → cofnij na Postać.
  const active: GameTab = tabs.some((t) => t.key === panel) ? panel : "character";

  return (
    // Mobile: przełącznik paneli = dolny TabBar (wspólny store gameTab), więc górny
    // scroll usunięty — dublował się i wychodził poza szerokość ekranu. Desktop = rail.
    <div className="flex min-h-0 flex-1 flex-col">
      {active === "character" && <PanelCharacter sheet={sheet} characterId={characterId} />}
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
          characterId={characterId}
          onEquip={(id, slot) => equip.mutate({ inventoryId: id, slot })}
        />
      )}
      {active === "recipes" && <PanelRecipes characterId={characterId} />}
      {active === "reputation" && <PanelReputation sheet={sheet} reputation={reputation.data} />}
      {active === "collections" && <PanelCollections characterId={characterId} />}
    </div>
  );
}
