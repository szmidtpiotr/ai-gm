import { Link } from "react-router-dom";
import {
  Sun,
  MoonStars,
  MapTrifold,
  List,
  Flame,
  UserCircle,
  Scroll,
} from "@phosphor-icons/react";
import { Breadcrumb } from "./Breadcrumb";
import { useAppStore } from "@/store/appStore";
import { useCampaignClock, useCampaignDetail } from "@/hooks/useGameData";

// Poza grą: marka + breadcrumb + profil.
// W grze: kompaktowy „pasek przygody" (zegar+pora stack · tylko główny quest · mapa · menu).
// BEZ imienia bohatera; HP/Mana są nad dolnym tabbarem (sekcja 5, zamrożone reguły).
export function Topbar({ inGame }: { inGame: boolean }) {
  const gameTab = useAppStore((s) => s.gameTab);
  // F-43: zakładka Mapa niesie własny nagłówek (zegar+pora+lokacja) — chowamy
  // pasek przygody, by nie dublować zegara (parytet z makietą zar5). KROK 4 (#1235).
  if (inGame && gameTab === "map") return null;

  return (
    <header
      className="sticky top-0 z-40 shrink-0 border-b border-line bg-surface/95 backdrop-blur"
      style={{ paddingTop: "var(--sa-top)" }}
    >
      {inGame ? <GameBar /> : <NavBar />}
    </header>
  );
}

function NavBar() {
  return (
    <div className="flex h-14 items-center gap-3 px-4">
      <Link to="/bohaterowie" className="flex items-center gap-2 shrink-0">
        <Flame weight="fill" className="text-ember" size={22} />
        <span className="font-serif text-title text-text">ŻAR</span>
      </Link>
      <div className="mx-1 h-4 w-px bg-line" />
      <div className="min-w-0 flex-1">
        <Breadcrumb />
      </div>
      <Link
        to="/profil"
        aria-label="Profil"
        className="shrink-0 text-text-3 transition-colors hover:text-ember-glow"
      >
        <UserCircle size={26} />
      </Link>
    </div>
  );
}

function GameBar() {
  const campaignId = useAppStore((s) => s.currentCampaignId) ?? undefined;
  const setGameTab = useAppStore((s) => s.setGameTab);
  const clock = useCampaignClock(campaignId);
  const campaign = useCampaignDetail(campaignId);

  const period = clock.data?.period ?? "";
  const isNight = /noc/i.test(period);
  const time = clock.data?.hour_str ?? "—:—";
  const quest = campaign.data?.title ?? "Przygoda";

  return (
    <div className="flex h-12 items-center gap-3 px-3.5">
      {/* zegar + pora (stack) — z prawym separatorem */}
      <div className="flex shrink-0 items-center gap-1.5 border-r border-line pr-3">
        {isNight ? (
          <MoonStars weight="fill" className="text-mana" size={16} />
        ) : (
          <Sun weight="fill" className="text-gold" size={16} />
        )}
        <div className="leading-tight">
          <div className="font-mono text-label font-semibold text-text">{time}</div>
          <div className="font-ui text-micro text-text-3">{period || "—"}</div>
        </div>
      </div>

      {/* TYLKO główny quest (reszta w Dzienniku) */}
      <div className="flex min-w-0 flex-1 items-center gap-2">
        <Scroll className="shrink-0 text-ember" size={15} />
        <div className="min-w-0">
          <div className="font-ui text-[9px] font-semibold uppercase tracking-[0.16em] text-text-3">
            Główne zadanie
          </div>
          <div className="truncate font-serif text-label font-semibold text-text">
            {quest}
          </div>
        </div>
      </div>

      <IconBtn label="Mapa" onClick={() => setGameTab("map")}>
        <MapTrifold size={18} />
      </IconBtn>
      <IconBtn label="Menu">
        <List size={18} />
      </IconBtn>
    </div>
  );
}

function IconBtn({
  label,
  children,
  onClick,
}: {
  label: string;
  children: React.ReactNode;
  onClick?: () => void;
}) {
  return (
    <button
      aria-label={label}
      onClick={onClick}
      className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md border border-line bg-bg text-text-2 transition-colors hover:border-line-ember hover:text-ember-glow"
    >
      {children}
    </button>
  );
}
