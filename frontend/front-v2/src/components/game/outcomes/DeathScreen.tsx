// FE10 (#1237) — F-28 Ekran śmierci (makieta zar7-smierc). Czaszka + epitafium +
// akcje: wskrzeszenie / nowa przygoda tym bohaterem / inny bohater. Wywoływany
// zdarzeniem: combat.status='ended', reason='player_dead'.
import { Skull, Heartbeat, Scroll, UserSwitch } from "@phosphor-icons/react";

export function DeathScreen({
  heroName,
  epitaph,
  level,
  turns,
  days,
  reviveEnabled,
  reviveDesc,
  reviving,
  onRevive,
  onNewAdventure,
  onOtherHero,
}: {
  heroName: string;
  epitaph: string;
  level: number;
  turns: number;
  days: number;
  reviveEnabled: boolean;
  reviveDesc: string;
  reviving: boolean;
  onRevive: () => void;
  onNewAdventure: () => void;
  onOtherHero: () => void;
}) {
  return (
    <div
      className="fixed inset-0 z-[60] flex flex-col items-center justify-center p-[26px] text-center"
      style={{
        background:
          "radial-gradient(70% 50% at 50% 30%, rgba(194,59,48,.1), transparent 65%), #0e0b08",
      }}
      data-testid="modal-death"
    >
      <div
        className="pointer-events-none absolute inset-0"
        style={{ background: "radial-gradient(120% 90% at 50% 50%, transparent 55%, rgba(0,0,0,.6))" }}
      />
      <div className="relative z-[2] w-full max-w-[400px]">
        <Skull weight="fill" size={76} className="mx-auto text-[#c23b30] opacity-90 drop-shadow-[0_0_26px_rgba(194,59,48,.4)]" />
        <div className="mt-3.5 font-ui text-[11px] font-bold uppercase tracking-[0.32em] text-danger">
          Twoja opowieść dobiega końca
        </div>
        <div className="mt-2 font-serif text-title-xl font-semibold tracking-[0.02em] text-text">
          {heroName} {feminineFall(heroName)}
        </div>
        {epitaph && (
          <div className="mx-auto mb-1 mt-4 max-w-[340px] font-serif text-[15px] italic leading-[1.7] text-text-2">
            „{epitaph}”
          </div>
        )}

        <div className="my-[22px] flex overflow-hidden rounded-md border border-line bg-[#181310] font-mono">
          <Sm v={String(level)} k="Poziom" />
          <Sm v={String(turns)} k="Tur przeżytych" />
          <Sm v={String(days)} k="Dni w Kresach" />
        </div>

        <div className="mt-[22px] flex flex-col gap-[9px]">
          {reviveEnabled && (
            <Act
              variant="revive"
              icon={<Heartbeat weight="fill" size={20} />}
              name={reviving ? "Wskrzeszam…" : "Wskrześ bohatera"}
              desc={reviveDesc}
              onClick={onRevive}
              disabled={reviving}
              testid="death-revive"
            />
          )}
          <Act
            icon={<Scroll size={20} />}
            name="Nowa przygoda tym bohaterem"
            desc={`Kronika ${heroName} trwa dalej`}
            onClick={onNewAdventure}
            testid="death-new-adventure"
          />
          <Act
            icon={<UserSwitch size={20} />}
            name="Wybierz innego bohatera"
            onClick={onOtherHero}
            testid="death-other-hero"
          />
        </div>
      </div>
    </div>
  );
}

// Prosta polska końcówka „poległ/poległa" — heurystyka po -a w imieniu.
function feminineFall(name: string): string {
  return /a\s*$/i.test(name) ? "poległa" : "poległ";
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
  disabled,
  testid,
}: {
  variant?: "revive";
  icon: React.ReactNode;
  name: string;
  desc?: string;
  onClick: () => void;
  disabled?: boolean;
  testid?: string;
}) {
  const revive = variant === "revive";
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      data-testid={testid}
      className={
        "flex items-center gap-3 rounded-[13px] border px-4 py-3.5 text-left font-ui text-[14.5px] font-semibold text-text transition-colors disabled:opacity-60 " +
        (revive
          ? "border-line-danger bg-gradient-to-br from-[rgba(194,59,48,.1)] to-[#181310] hover:border-danger"
          : "border-line bg-[#181310] hover:border-danger")
      }
    >
      <span className={revive ? "flex-none text-danger" : "flex-none text-text-2"}>{icon}</span>
      <span>
        <span className={"block " + (revive ? "text-danger" : "text-text")}>{name}</span>
        {desc && <span className="mt-px block font-ui text-[11.5px] font-normal text-text-3">{desc}</span>}
      </span>
    </button>
  );
}
