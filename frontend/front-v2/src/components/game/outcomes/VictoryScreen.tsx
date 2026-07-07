// F-77 (#1268) — ekran zwycięstwa po zakończeniu przygody (POST /finish). Triumfalny
// wariant ekranu śmierci (zar7): laur zamiast czaszki, ciepły blask zamiast krwi.
// Statystyki + epitafium ciągniemy z /death-summary (outcome=victory po finiszu).
import { useNavigate } from "react-router-dom";
import { Crown, Scroll, UserSwitch } from "@phosphor-icons/react";
import { useDeathSummary } from "@/hooks/useOutcomes";
import { useCampaignClock } from "@/hooks/useGameData";

export function VictoryScreen({
  campaignId,
  heroId,
  heroName,
  heroLevel,
  turnCount,
  onClose,
}: {
  campaignId: number;
  heroId: number | undefined;
  heroName: string;
  /** Fallback poziomu/tur — /death-summary bywa puste dla finiszu gracza (404). */
  heroLevel?: number;
  turnCount?: number;
  onClose: () => void;
}) {
  const navigate = useNavigate();
  const summary = useDeathSummary(campaignId, true);
  const clock = useCampaignClock(campaignId);
  const d = summary.data;

  const name = d?.character_name || heroName || "Bohater";
  const epitaph = d?.epitaph || "";
  const level = d?.level ?? heroLevel ?? 0;
  const turns = d?.stats?.turn_count ?? turnCount ?? 0;
  const days = clock.data?.day ?? 0;

  function go(path: string) {
    onClose();
    navigate(path);
  }

  return (
    <div
      className="fixed inset-0 z-[60] flex flex-col items-center justify-center p-[26px] text-center"
      style={{
        background:
          "radial-gradient(70% 50% at 50% 30%, rgba(255,122,61,.14), transparent 65%), #0e0b08",
      }}
      data-testid="modal-victory"
    >
      <div
        className="pointer-events-none absolute inset-0"
        style={{ background: "radial-gradient(120% 90% at 50% 50%, transparent 55%, rgba(0,0,0,.6))" }}
      />
      <div className="relative z-[2] w-full max-w-[400px]">
        <Crown
          weight="fill"
          size={76}
          className="mx-auto text-gold opacity-95 drop-shadow-[0_0_26px_rgba(224,168,74,.45)]"
        />
        <div className="mt-3.5 font-ui text-[11px] font-bold uppercase tracking-[0.32em] text-ember-glow">
          Przygoda ukończona
        </div>
        <div className="mt-2 font-serif text-title-xl font-semibold tracking-[0.02em] text-text">
          {name} {feminineWin(name)}
        </div>
        {epitaph && (
          <div className="mx-auto mb-1 mt-4 max-w-[340px] font-serif text-[15px] italic leading-[1.7] text-text-2">
            „{epitaph}”
          </div>
        )}

        <div className="my-[22px] flex overflow-hidden rounded-md border border-line bg-[#181310] font-mono">
          <Sm v={String(level)} k="Poziom" />
          <Sm v={String(turns)} k="Tur przygody" />
          <Sm v={String(days)} k="Dni w Kresach" />
        </div>

        <div className="mt-[22px] flex flex-col gap-[9px]">
          <Act
            variant="primary"
            icon={<Scroll size={20} />}
            name="Nowa przygoda tym bohaterem"
            desc={`Kronika ${name} trwa dalej`}
            onClick={() => go(heroId ? `/bohaterowie/${heroId}/kampanie` : "/bohaterowie")}
            testid="victory-new-adventure"
          />
          <Act
            icon={<UserSwitch size={20} />}
            name="Wybierz innego bohatera"
            onClick={() => go("/bohaterowie")}
            testid="victory-other-hero"
          />
        </div>
      </div>
    </div>
  );
}

function feminineWin(name: string): string {
  return /a\s*$/i.test(name) ? "dokonała dzieła" : "dokonał dzieła";
}

function Sm({ v, k }: { v: string; k: string }) {
  return (
    <div className="flex-1 border-r border-line-soft px-2 py-[11px] last:border-r-0">
      <div className="text-[16px] font-semibold text-text">{v}</div>
      <div className="mt-[3px] font-ui text-[8.5px] uppercase tracking-[0.12em] text-text-3">{k}</div>
    </div>
  );
}

function Act({
  variant,
  icon,
  name,
  desc,
  onClick,
  testid,
}: {
  variant?: "primary";
  icon: React.ReactNode;
  name: string;
  desc?: string;
  onClick: () => void;
  testid?: string;
}) {
  const primary = variant === "primary";
  return (
    <button
      type="button"
      onClick={onClick}
      data-testid={testid}
      className={
        "flex items-center gap-3 rounded-[13px] border px-4 py-3.5 text-left font-ui text-[14.5px] font-semibold text-text transition-colors " +
        (primary
          ? "border-line-ember bg-gradient-to-br from-[rgba(255,122,61,.1)] to-[#181310] hover:border-ember"
          : "border-line bg-[#181310] hover:border-ember")
      }
    >
      <span className={primary ? "flex-none text-ember-glow" : "flex-none text-text-2"}>{icon}</span>
      <span>
        <span className={"block " + (primary ? "text-ember-glow" : "text-text")}>{name}</span>
        {desc && <span className="mt-px block font-ui text-[11.5px] font-normal text-text-3">{desc}</span>}
      </span>
    </button>
  );
}
