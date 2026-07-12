// F-87 / #1349 — współdzielony wizerunek wroga: badge zagrożenia + portret + nazwa.
// Używany przez EnemyRevealCard (walka z narracji, #1344) ORAZ TravelInterruptModal
// (zasadzka w drodze, #1349) — jeden markup = spójny wygląd, zero dublowania. Surowa
// liczba wrogów NIGDY nie pokazana (parytet z ukrytym Power Score) — tylko "i N innych".
import { Sword } from "@phosphor-icons/react";
import type { RelativeThreat } from "@/lib/types";

export function revealOthers(n: number): string {
  // 2-4 → "inni", 5+ → "innych" (polska odmiana liczebnika)
  const last = n % 10;
  const tens = n % 100;
  if (n >= 2 && n <= 4 && !(tens >= 12 && tens <= 14)) return `i ${n} innych`;
  return `i ${n} ${last === 1 ? "inny" : "innych"}`;
}

export function EnemyRevealVisual({
  name,
  imageUrl,
  threat,
  restCount = 0,
}: {
  name: string;
  imageUrl?: string | null;
  threat?: RelativeThreat | null;
  restCount?: number;
}) {
  return (
    <div className="relative">
      {/* wskaźnik zagrożenia — glyph + label, BEZ surowej liczby */}
      {threat && (
        <div
          className="absolute left-2 top-2 z-10 flex items-center gap-1.5 rounded-pill border border-line-danger bg-bg/80 px-2.5 py-1 backdrop-blur"
          data-testid="reveal-threat"
        >
          <span className="text-[15px] leading-none">{threat.glyph}</span>
          <span className="font-ui text-[11px] font-bold uppercase tracking-[0.06em] text-text">
            {threat.label}
          </span>
        </div>
      )}

      {imageUrl ? (
        <img src={imageUrl} alt={name} className="aspect-[4/3] w-full object-cover" />
      ) : (
        <div className="flex aspect-[4/3] w-full flex-col items-center justify-center gap-2 bg-mech-card text-text-3">
          <Sword size={40} weight="duotone" />
          <span className="font-ui text-[11px] uppercase tracking-wide">Brak wizerunku</span>
        </div>
      )}

      <div className="border-t border-line px-4 py-3 text-center">
        <div className="font-serif text-body font-semibold text-text">{name}</div>
        {restCount > 0 && (
          <div className="mt-0.5 font-ui text-[12px] text-text-3">{revealOthers(restCount)}</div>
        )}
      </div>
    </div>
  );
}
