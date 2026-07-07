import { useNavigate } from "react-router-dom";
import {
  PencilSimple,
  UsersThree,
  Crown,
  Clock,
  Scroll,
  Users,
  Envelope,
  Brain,
  Palette,
  ShieldCheck,
  CaretRight,
  SignOut,
  type Icon,
} from "@phosphor-icons/react";
import { useAppStore } from "@/store/appStore";
import { useHeroes, useLlmSettings } from "@/hooks/useGameData";
import { useToast } from "@/components/ui/toast";
import { PushButton } from "@/components/PushButton";

// F-07 Profil gracza. Makieta 1:1 → zar8-profil.html.
export default function Profile() {
  const navigate = useNavigate();
  const { toast } = useToast();
  const user = useAppStore((s) => s.currentUser);
  const logout = useAppStore((s) => s.logout);
  const { data: heroes } = useHeroes();
  const { data: llm } = useLlmSettings(user?.id);

  const name = user?.displayName || user?.username || "Gracz";
  const email = user?.email || "—";
  const initial = name.charAt(0).toUpperCase();

  const heroCount = heroes?.length ?? 0;
  const completed = (heroes ?? []).reduce((n, h) => n + (h.campaigns_completed || 0), 0);
  const legends = (heroes ?? []).filter((h) => (h.campaigns_completed || 0) > 0).length;

  function onLogout() {
    logout();
    navigate("/login", { replace: true });
  }

  const soon = () => toast("Ta sekcja pojawi się wkrótce.", "info");

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-4">
      {/* nagłówek tożsamości */}
      <div className="relative flex items-center gap-4 overflow-hidden rounded-xl border border-line bg-mech-card p-[18px]">
        <div
          className="relative z-10 flex h-[72px] w-[72px] shrink-0 items-center justify-center rounded-pill border-2 border-line-ember font-serif text-[30px] text-ember-glow"
          style={{ background: "radial-gradient(circle at 35% 30%,#553d2b,#241c13 70%)" }}
        >
          {initial}
        </div>
        <div className="relative z-10 min-w-0 flex-1">
          <div className="truncate font-serif text-title-lg font-semibold text-text">{name}</div>
          <div className="mt-0.5 truncate font-mono text-label text-text-2">{email}</div>
          <button
            onClick={soon}
            className="mt-2 inline-flex items-center gap-1.5 rounded-pill border border-line-ember bg-ember/[0.08] px-3 py-1 font-ui text-micro text-ember-glow"
          >
            <PencilSimple size={13} /> Edytuj profil
          </button>
        </div>
      </div>

      {/* kafle kroniki */}
      <div className="grid grid-cols-4 gap-2">
        <ChronTile icon={UsersThree} value={heroCount} label="Bohaterów" />
        <ChronTile icon={Crown} value={completed} label="Ukończonych" />
        <ChronTile icon={Clock} value="—" label="W grze" />
        <ChronTile icon={Scroll} value={legends} label="Legendy" />
      </div>

      <div className="grid gap-x-8 lg:grid-cols-2">
        <section>
          <SectionHead>Społeczność</SectionHead>
          <div className="flex flex-col gap-2">
            <Row icon={Users} title="Znajomi" sub="Wspólne przygody" onClick={soon} />
            <Row icon={Envelope} title="Zaproszenia" sub="Zaproś do gry" onClick={soon} />
          </div>
        </section>

        <section>
          <SectionHead>Ustawienia konta</SectionHead>
          <div className="flex flex-col gap-2">
            <Row
              icon={Brain}
              title="Konfiguracja LLM"
              sub="Model narracji"
              badge={llm?.model}
              onClick={soon}
            />
            <Row icon={Palette} title="Wygląd" sub="Motyw, czcionka, rozmiar" onClick={soon} />
            <Row icon={ShieldCheck} title="Bezpieczeństwo" sub="Hasło, sesje" onClick={soon} />
            <PushButton />
          </div>
        </section>
      </div>

      <button
        onClick={onLogout}
        className="mt-2 flex w-full items-center justify-center gap-2.5 rounded-md border border-line-danger bg-danger/[0.06] py-3.5 font-ui text-body font-semibold text-danger"
      >
        <SignOut size={18} /> Wyloguj się
      </button>
    </div>
  );
}

function ChronTile({
  icon: I,
  value,
  label,
}: {
  icon: Icon;
  value: number | string;
  label: string;
}) {
  return (
    <div className="rounded-md border border-line bg-surface px-1.5 py-3.5 text-center">
      <I weight="fill" size={18} className="mx-auto text-ember-glow" />
      <div className="mt-1 font-mono text-title font-semibold text-text">{value}</div>
      <div className="mt-0.5 font-ui text-[9.5px] uppercase tracking-wide text-text-3">
        {label}
      </div>
    </div>
  );
}

function SectionHead({ children }: { children: React.ReactNode }) {
  return (
    <div className="mb-2.5 mt-4 flex items-center gap-2.5 font-ui text-[10.5px] font-bold uppercase tracking-[0.2em] text-ember">
      {children}
      <span className="h-px flex-1 bg-line-soft" />
    </div>
  );
}

function Row({
  icon: I,
  title,
  sub,
  badge,
  onClick,
}: {
  icon: Icon;
  title: string;
  sub: string;
  badge?: string;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className="flex items-center gap-3.5 rounded-md border border-line-soft bg-surface px-3.5 py-3 text-left transition-colors hover:border-line"
    >
      <span className="flex h-[38px] w-[38px] shrink-0 items-center justify-center rounded-md border border-line bg-bg text-text-2">
        <I size={18} />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block truncate font-ui text-body font-semibold text-text">{title}</span>
        <span className="block truncate font-ui text-micro text-text-3">{sub}</span>
      </span>
      {badge && (
        <span className="shrink-0 rounded-pill border border-mana/30 px-2.5 py-1 font-mono text-[9.5px] uppercase tracking-wide text-mana">
          {badge}
        </span>
      )}
      <CaretRight size={15} className="shrink-0 text-text-3" />
    </button>
  );
}
