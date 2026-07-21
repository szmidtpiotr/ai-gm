import { cn } from "@/lib/utils";
import { useAppStore } from "@/store/appStore";
import { useCharacter } from "@/hooks/useGameData";
import { useCharacterRecipes } from "@/hooks/useCrafting";
import { useUnreadRumors } from "@/hooks/useUnreadRumors";
import { readVitals } from "@/lib/game";
import { readConditions } from "@/lib/sheet";
import { VitalBars } from "@/components/game/Vitals";
import {
  JOURNAL_TAB,
  MAP_TAB,
  STORY_TAB,
  visibleSheetTabs,
  type GameTabDef,
} from "@/components/sheet/tabs";

// Panele gry = zakładki (nie osobny ekran). „Opowieść" przypięta z lewej,
// panele karty postaci przewijają się poziomo (sekcja 5). Wybór trzyma store
// (współdzielony z desktop railem + górnym scrollem karty). KROK 5 (#1234).
export function TabBar({ inGame }: { inGame: boolean }) {
  const active = useAppStore((s) => s.gameTab);
  const setGameTab = useAppStore((s) => s.setGameTab);
  const heroId = useAppStore((s) => s.currentHeroId) ?? undefined;
  const character = useCharacter(inGame ? heroId : undefined);
  const recipes = useCharacterRecipes(inGame ? heroId : undefined); // #1375 gating
  // #1517 — WSZYSTKIE hooki przed `if (!inGame) return null`. TabBar siedzi w
  // AppShell (poza <Outlet/>), więc SPA-nawigacja „poza grą → w grze" trafia w
  // TEN SAM fiber: render nr 1 kończył się na 5 hookach (early return), render
  // nr 2 wołał szósty (useUnreadRumors → zustand → useSyncExternalStore) i React
  // wywalał #310. Po F5 pierwszy render był już `inGame`, więc licznik się zgadzał
  // i błąd „znikał". Kolejność hooków musi być stała niezależnie od propsów.
  const unreadRumors = useUnreadRumors(inGame);
  if (!inGame) return null;

  const vitals = readVitals(character.data?.sheet_json);
  const scrollable = [
    ...visibleSheetTabs(vitals.hasMana, !!recipes.data?.has_any),
    MAP_TAB,
    JOURNAL_TAB,
  ];

  return (
    <nav
      className="shrink-0 border-t border-line bg-surface/95 backdrop-blur lg:hidden"
      style={{ paddingBottom: "var(--sa-bottom)" }}
      aria-label="Panele gry"
    >
      {/* HP/Mana — 2 cienkie paski nad tabbarem (sekcja 5) */}
      {character.data && <VitalBars v={vitals} conditions={readConditions(character.data?.sheet_json)} />}
      <div className="flex items-stretch">
        {/* Przypięta Opowieść */}
        <div className="flex shrink-0 border-r border-line">
          <TabButton
            tab={STORY_TAB}
            active={active === STORY_TAB.key}
            onClick={() => setGameTab(STORY_TAB.key)}
          />
        </div>
        {/* Przewijane panele karty postaci */}
        <div className="flex flex-1 overflow-x-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
          {scrollable.map((t) => (
            <TabButton
              key={t.key}
              tab={t}
              active={active === t.key}
              dot={t.key === "collections" && unreadRumors && active !== t.key}
              onClick={() => setGameTab(t.key)}
            />
          ))}
        </div>
      </div>
    </nav>
  );
}

function TabButton({
  tab,
  active,
  onClick,
  dot = false,
}: {
  tab: GameTabDef;
  active: boolean;
  onClick: () => void;
  dot?: boolean;
}) {
  const Icon = tab.icon;
  return (
    <button
      onClick={onClick}
      className={cn(
        "relative flex min-w-[68px] flex-col items-center justify-center gap-0.5 px-3 py-2 transition-colors",
        active ? "text-ember" : "text-text-3 hover:text-text-2",
      )}
      aria-current={active ? "page" : undefined}
    >
      <Icon weight={active ? "fill" : "regular"} size={22} />
      <span className="font-ui text-micro">{tab.label}</span>
      {dot && (
        <span className="absolute right-2.5 top-1.5 h-1.5 w-1.5 rounded-full bg-ember" title="Nowa plotka" />
      )}
    </button>
  );
}
