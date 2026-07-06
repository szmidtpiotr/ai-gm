import { Link } from "react-router-dom";
import { Sun, MapTrifold, List, Flame, UserCircle } from "@phosphor-icons/react";
import { Breadcrumb } from "./Breadcrumb";
import { ProgressBar } from "@/components/ui/progress-bar";

// Poza grą: marka + breadcrumb + profil.
// W grze: kompaktowy „pasek przygody" (zegar+pora stack · główny quest · mapa · menu)
// + 2 cienkie paski HP/Mana (sekcja 5, zamrożone reguły mobilne).
export function Topbar({ inGame }: { inGame: boolean }) {
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
  return (
    <div>
      <div className="flex h-12 items-center gap-3 px-4">
        {/* zegar + pora (stack) */}
        <div className="flex items-center gap-1.5 shrink-0">
          <Sun weight="fill" className="text-gold" size={18} />
          <div className="leading-tight">
            <div className="font-mono text-label text-text">08:20</div>
            <div className="font-ui text-micro text-text-3">Poranek</div>
          </div>
        </div>
        {/* główny quest (tylko jeden) */}
        <div className="min-w-0 flex-1">
          <div className="truncate font-serif text-body text-text-2">
            Odnaleźć zaginionego kupca
          </div>
        </div>
        <button
          aria-label="Mapa"
          className="shrink-0 text-text-3 hover:text-ember-glow"
        >
          <MapTrifold size={22} />
        </button>
        <button
          aria-label="Menu"
          className="shrink-0 text-text-3 hover:text-ember-glow"
        >
          <List size={22} />
        </button>
      </div>
      {/* HP / Mana — 2 cienkie paski nad dolnym tabbarem (tu w topbarze gry) */}
      <div className="flex gap-2 px-4 pb-2">
        <ProgressBar kind="hp" value={24} max={30} hairline />
        <ProgressBar kind="mana" value={8} max={12} hairline />
      </div>
    </div>
  );
}
