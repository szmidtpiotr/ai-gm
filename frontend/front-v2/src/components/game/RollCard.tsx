import { useState } from "react";
import { CaretDown, Sparkle, Sword } from "@phosphor-icons/react";
import { cn } from "@/lib/utils";
import type { RollCardData } from "@/lib/types";

// F-52 karta rzutu (sekcja 6): rzut gracza = prawo/ember, wróg = lewo/krwawy.
// Nat 20 = złoty flash, Nat 1 = krwawy. Stare rzuty zwijane do jednej linii (zar3).
export function RollCard({
  roll,
  collapsible = false,
}: {
  roll: RollCardData;
  collapsible?: boolean;
}) {
  const [open, setOpen] = useState(!collapsible);
  const player = roll.actor === "player";
  const res = roll.cells.find((c) => c.res);
  const sum = roll.cells.find((c) => c.sum);

  return (
    <div
      className={cn(
        "mb-3.5 overflow-hidden rounded-md border font-mono transition-shadow",
        "max-w-[88%]",
        player ? "ml-auto" : "mr-auto border-l-[3px]",
        player
          ? "border-line-ember bg-player-card"
          : "border-line border-l-danger bg-gm-bubble",
        roll.crit && "border-gold shadow-[0_0_0_1px_var(--gold),0_0_20px_rgba(232,193,90,.32)]",
        roll.fumble && "border-danger shadow-[0_0_0_1px_var(--danger),0_0_20px_rgba(232,96,79,.3)]",
      )}
    >
      {/* nagłówek */}
      <button
        type="button"
        onClick={() => collapsible && setOpen((v) => !v)}
        className={cn(
          "flex w-full items-center gap-2 border-b border-line-mech px-3 py-1.5 text-micro font-semibold uppercase tracking-wider",
          player ? "justify-end text-ember-glow" : "text-danger",
          roll.crit && "text-gold",
          collapsible && "cursor-pointer",
        )}
      >
        {roll.crit ? <Sparkle weight="fill" size={13} /> : <Sword size={13} />}
        <span className="truncate">{roll.title}</span>
      </button>

      {/* zwinięty widok — jedna linia */}
      {collapsible && !open && (
        <div className="flex items-center gap-2.5 px-3 py-1.5 text-micro text-text-3">
          {sum && (
            <span>
              <b className="font-semibold text-text-2">{sum.v}</b>
            </span>
          )}
          {res && <span className="text-mech-ok">{res.v}</span>}
          <CaretDown size={12} className="ml-auto" />
        </div>
      )}

      {/* pełna siatka */}
      {open && (
        <div className="flex">
          {roll.cells.map((c, i) => (
            <div
              key={i}
              className={cn(
                "flex-1 border-r border-[rgba(232,193,90,.1)] px-1 py-1.5 text-center last:border-r-0",
                c.sum && "bg-[rgba(255,122,61,.08)]",
                c.res && "flex-[1.2]",
              )}
            >
              <div className="text-[8px] uppercase tracking-wide text-text-3">
                {c.k}
              </div>
              <div
                className={cn(
                  "mt-0.5 text-label",
                  c.sum ? "font-semibold text-text" : "font-medium text-text-2",
                  c.res &&
                    cn(
                      "pt-0.5 text-micro font-semibold uppercase tracking-wide",
                      roll.crit ? "text-gold" : roll.fumble ? "text-danger" : player ? "text-mech-ok" : "text-danger",
                    ),
                )}
              >
                {c.v}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
