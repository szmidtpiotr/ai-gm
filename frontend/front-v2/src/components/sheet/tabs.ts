// KROK 5 (#1234) — wspólna definicja zakładek gry (Opowieść + 5 paneli karty).
// Używane przez: desktop lewy rail (GameRail), mobile górny scroll (CharacterSheet),
// mobile dolny tabbar (TabBar). Jedno źródło = spójne etykiety/ikony.
import {
  Backpack,
  BookOpen,
  BookOpenText,
  FlagBanner,
  MapTrifold,
  Shield,
  Sparkle,
  Target,
  type Icon,
} from "@phosphor-icons/react";
import type { GameTab } from "@/store/appStore";

export interface GameTabDef {
  key: GameTab;
  label: string;
  icon: Icon;
  /** true = wymaga puli many (Czary — tylko klasy magiczne). */
  manaOnly?: boolean;
}

export const STORY_TAB: GameTabDef = { key: "story", label: "Opowieść", icon: BookOpen };

// 5 paneli karty postaci (kolejność jak w makiecie zar5 lewego railu).
export const SHEET_TABS: GameTabDef[] = [
  { key: "character", label: "Postać", icon: Shield },
  { key: "skills", label: "Umiejętności", icon: Target },
  { key: "spells", label: "Czary", icon: Sparkle, manaOnly: true },
  { key: "inventory", label: "Ekwipunek", icon: Backpack },
  { key: "reputation", label: "Reputacja & opis", icon: FlagBanner },
];

export function visibleSheetTabs(hasMana: boolean): GameTabDef[] {
  return SHEET_TABS.filter((t) => !t.manaOnly || hasMana);
}

// F-43 Mapa świata — zakładka na poziomie gry (po panelach karty, jak w makiecie
// zar5). Otwierana też z ikony 🗺 w pasku przygody (Topbar). KROK 4 FE8 (#1235).
export const MAP_TAB: GameTabDef = { key: "map", label: "Mapa", icon: MapTrifold };

// FE13 Dziennik + Kronika (#1262 / F-23/F-58/F-79) — zakładka gry: zadania,
// wątki, recap „Poprzednio…", kronika bohatera. Po Mapie w railu/tabbarze.
export const JOURNAL_TAB: GameTabDef = { key: "journal", label: "Dziennik", icon: BookOpenText };
