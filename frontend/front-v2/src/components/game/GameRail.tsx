// KROK 5 (#1234) — desktop lewy pionowy rail: przełącznik Opowieść + 5 paneli
// karty postaci (F-21/F-54..F-58). Mobile używa dolnego tabbara + górnego scrolla.
import { cn } from "@/lib/utils";
import { useAppStore } from "@/store/appStore";
import { useUnreadRumors } from "@/hooks/useUnreadRumors";
import {
  JOURNAL_TAB,
  MAP_TAB,
  STORY_TAB,
  visibleSheetTabs,
  type GameTabDef,
} from "@/components/sheet/tabs";

export function GameRail({ hasMana, hasRecipes = false }: { hasMana: boolean; hasRecipes?: boolean }) {
  const active = useAppStore((s) => s.gameTab);
  const setGameTab = useAppStore((s) => s.setGameTab);
  const unreadRumors = useUnreadRumors();
  const tabs: GameTabDef[] = [
    STORY_TAB,
    ...visibleSheetTabs(hasMana, hasRecipes),
    MAP_TAB,
    JOURNAL_TAB,
  ];

  return (
    <nav
      className="hidden w-[196px] shrink-0 flex-col gap-1 overflow-y-auto border-r border-line bg-surface p-2.5 lg:flex"
      aria-label="Panele gry"
    >
      {tabs.map((t) => {
        const Icon = t.icon;
        const on = active === t.key;
        return (
          <button
            key={t.key}
            onClick={() => setGameTab(t.key)}
            aria-current={on ? "page" : undefined}
            className={cn(
              "flex items-center gap-2.5 rounded-md border-l-2 px-3 py-2.5 text-left font-ui text-[12px] font-semibold uppercase tracking-[0.04em] transition-colors",
              on
                ? "border-ember bg-[rgba(255,122,61,0.1)] text-ember-glow"
                : "border-transparent text-text-3 hover:text-text-2",
            )}
          >
            <Icon size={17} weight={on ? "fill" : "regular"} />
            {t.label}
            {t.key === "collections" && unreadRumors && !on && (
              <span className="ml-auto h-1.5 w-1.5 shrink-0 rounded-full bg-ember" title="Nowa plotka" />
            )}
          </button>
        );
      })}
    </nav>
  );
}
