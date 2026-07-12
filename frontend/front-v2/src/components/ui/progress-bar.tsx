import * as React from "react";
import { cn } from "@/lib/utils";

type Kind = "hp" | "mana" | "xp";

const FILLS: Record<Kind, string> = {
  hp: "bg-gradient-to-r from-danger to-danger-glow",
  mana: "bg-gradient-to-r from-mana to-[#a9c6de]",
  xp: "bg-gradient-to-r from-gold to-gold-glow",
};

export interface ProgressBarProps
  extends React.HTMLAttributes<HTMLDivElement> {
  value: number;
  max?: number;
  kind?: Kind;
  /** Thin hairline variant (topbar HP/Mana over tabbar). */
  hairline?: boolean;
  showLabel?: boolean;
}

// HP/Mana/XP — inset tło + ciepły fill. Sekcja 6: paski nad dolnym tabbarem.
export function ProgressBar({
  value,
  max = 100,
  kind = "hp",
  hairline = false,
  showLabel = false,
  className,
  ...props
}: ProgressBarProps) {
  const pct = Math.max(0, Math.min(100, max > 0 ? (value / max) * 100 : 0));
  return (
    <div className={cn("w-full", className)} {...props}>
      {showLabel && (
        <div className="mb-1 flex justify-between font-mono text-micro text-text-3">
          <span className="uppercase tracking-wide">{kind}</span>
          <span>
            {value}
            <span className="text-text-3/60">/{max}</span>
          </span>
        </div>
      )}
      <div
        role="progressbar"
        aria-valuenow={value}
        aria-valuemax={max}
        className={cn(
          "w-full overflow-hidden rounded-pill bg-inset border border-line-soft",
          hairline ? "h-1" : "h-2.5",
        )}
      >
        <div
          className={cn("h-full rounded-pill transition-all duration-500", FILLS[kind])}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
