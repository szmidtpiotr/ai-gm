import { useState } from "react";
import {
  BookOpen,
  UserSquare,
  Backpack,
  MapTrifold,
  Scroll,
  Sword,
  type Icon,
} from "@phosphor-icons/react";
import { cn } from "@/lib/utils";

interface Tab {
  key: string;
  label: string;
  icon: Icon;
  pinned?: boolean;
}

// Panele gry = zakładki (nie osobny ekran). „Opowieść" przypięta z lewej,
// reszta przewija się poziomo (sekcja 5, zamrożone reguły mobilne).
const TABS: Tab[] = [
  { key: "story", label: "Opowieść", icon: BookOpen, pinned: true },
  { key: "character", label: "Postać", icon: UserSquare },
  { key: "inventory", label: "Ekwipunek", icon: Backpack },
  { key: "map", label: "Mapa", icon: MapTrifold },
  { key: "journal", label: "Dziennik", icon: Scroll },
  { key: "combat", label: "Walka", icon: Sword },
];

export function TabBar({ inGame }: { inGame: boolean }) {
  const [active, setActive] = useState("story");
  if (!inGame) return null;

  const pinned = TABS.filter((t) => t.pinned);
  const scrollable = TABS.filter((t) => !t.pinned);

  return (
    <nav
      className="shrink-0 border-t border-line bg-surface/95 backdrop-blur lg:hidden"
      style={{ paddingBottom: "var(--sa-bottom)" }}
      aria-label="Panele gry"
    >
      <div className="flex items-stretch">
        {/* Przypięta Opowieść */}
        <div className="flex shrink-0 border-r border-line">
          {pinned.map((t) => (
            <TabButton
              key={t.key}
              tab={t}
              active={active === t.key}
              onClick={() => setActive(t.key)}
            />
          ))}
        </div>
        {/* Przewijana reszta */}
        <div className="flex flex-1 overflow-x-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
          {scrollable.map((t) => (
            <TabButton
              key={t.key}
              tab={t}
              active={active === t.key}
              onClick={() => setActive(t.key)}
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
}: {
  tab: Tab;
  active: boolean;
  onClick: () => void;
}) {
  const Icon = tab.icon;
  return (
    <button
      onClick={onClick}
      className={cn(
        "flex min-w-[68px] flex-col items-center justify-center gap-0.5 px-3 py-2 transition-colors",
        active ? "text-ember" : "text-text-3 hover:text-text-2",
      )}
      aria-current={active ? "page" : undefined}
    >
      <Icon weight={active ? "fill" : "regular"} size={22} />
      <span className="font-ui text-micro">{tab.label}</span>
    </button>
  );
}
