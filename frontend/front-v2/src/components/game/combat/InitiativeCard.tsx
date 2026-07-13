// F-88 (#1356 / WALKA-T5-FIX-a) — karta inicjatywy na starcie walki. Spec 5a:
// pokazuje OBA wyniki rzutu inicjatywy (Ty vs Wróg) + kto zaczyna. Wzorzec wizualny
// = EnemyRevealCard (overlay, once-per-combat_id). Wyższy rzut podświetlony amber.
import { Lightning, Sword, X } from "@phosphor-icons/react";
import { cn } from "@/lib/utils";
import type { InitiativeData } from "./useInitiativeCard";

export function InitiativeCard({
  data,
  onClose,
}: {
  data: InitiativeData;
  onClose: () => void;
}) {
  const playerStarts = data.starter === "player";
  const playerRoll = data.player.roll;
  // Prezentujemy najgroźniejszego wroga jako wiodący rzut (najwyższa inicjatywa),
  // reszta jako „+N" — tak jak EnemyRevealCard grupuje herszta.
  const enemies = [...data.enemies].sort(
    (a, b) => Number(b.roll ?? -1) - Number(a.roll ?? -1),
  );
  const lead = enemies[0];
  const rest = Math.max(0, enemies.length - 1);
  const enemyRoll = lead?.roll ?? null;

  return (
    <div
      className="fixed inset-0 z-[59] flex items-center justify-center bg-bg/85 p-6 backdrop-blur-sm"
      data-testid="initiative-card"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="relative w-full max-w-sm overflow-hidden rounded-xl border border-line-mech bg-surface shadow-modal">
        <button
          type="button"
          onClick={onClose}
          aria-label="Zamknij"
          className="absolute right-2 top-2 z-10 flex h-8 w-8 items-center justify-center rounded-md bg-bg/60 text-text-2 hover:text-text"
        >
          <X size={18} />
        </button>

        <header className="flex items-center gap-1.5 bg-gradient-to-r from-[rgba(130,167,199,.16)] to-surface px-4 py-2.5 font-ui text-[12.5px] font-bold uppercase tracking-[0.08em] text-mana">
          <Lightning weight="fill" size={15} /> Inicjatywa
        </header>

        <div className="flex items-stretch gap-2 px-4 py-4">
          <Side
            label="Ty"
            roll={playerRoll}
            winner={playerStarts}
            tone="player"
          />
          <div className="flex shrink-0 items-center font-ui text-[11px] font-bold uppercase tracking-[0.1em] text-text-3">
            vs
          </div>
          <Side
            label={rest > 0 ? `${lead?.name ?? "Wróg"} +${rest}` : lead?.name ?? "Wróg"}
            roll={enemyRoll}
            winner={!playerStarts}
            tone="enemy"
          />
        </div>

        <p
          className={cn(
            "px-4 pb-1 text-center font-ui text-[13px] font-bold",
            playerStarts ? "text-ember-glow" : "text-danger-glow",
          )}
          data-testid="initiative-starter"
        >
          {playerStarts ? "Zaczynasz!" : "Zaczyna wróg"}
        </p>

        <button
          type="button"
          onClick={onClose}
          className="mt-2 flex w-full items-center justify-center gap-1.5 border-t border-line bg-gradient-to-r from-[rgba(232,96,79,.14)] to-surface px-4 py-2.5 font-ui text-[12.5px] font-bold uppercase tracking-[0.08em] text-danger-glow hover:from-[rgba(232,96,79,.22)]"
        >
          <Sword weight="fill" size={15} /> Do walki
        </button>
      </div>
    </div>
  );
}

function Side({
  label,
  roll,
  winner,
  tone,
}: {
  label: string;
  roll: number | null;
  winner: boolean;
  tone: "player" | "enemy";
}) {
  return (
    <div
      className={cn(
        "flex flex-1 flex-col items-center gap-1 rounded-lg border px-2 py-3",
        winner
          ? "border-ember bg-player-card shadow-[0_0_0_1px_var(--ember),0_0_10px_rgba(255,122,61,.2)]"
          : "border-line-soft bg-bg",
      )}
    >
      <span
        className={cn(
          "max-w-full truncate font-ui text-[11px] font-semibold uppercase tracking-[0.06em]",
          tone === "player" ? "text-ember-glow" : "text-text-2",
        )}
      >
        {label}
      </span>
      <span
        className={cn(
          "font-mono text-[28px] font-bold leading-none",
          winner ? "text-gold" : "text-text-2",
        )}
      >
        {roll ?? "–"}
      </span>
      <span className="font-ui text-[9px] uppercase tracking-[0.12em] text-text-3">
        rzut d20
      </span>
    </div>
  );
}
