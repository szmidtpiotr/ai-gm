import type { ReactNode } from "react";
import { PaperPlaneRight, Microphone } from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

// F-12 placeholder — pełny ekran gry (narracja/composer/rzuty) w KROKU 4/8 (#1233).
// Tu tylko demonstracja konwencji dymków ŻAR (sekcja 6).
export default function Game() {
  return (
    <div className="flex flex-col gap-3">
      {/* Narracja GM — lewo, tło, serif */}
      <Bubble side="gm" header="MISTRZ GRY · tura 12">
        Mgła wstaje znad traktu. Z oddali dobiega skrzypienie kół — ktoś nadjeżdża,
        choć droga miała być pusta o tej porze.
      </Bubble>

      {/* Akcja gracza — prawo, ember, serif italic */}
      <Bubble side="player" header="TWOJA AKCJA ◀">
        Chowam się za pniem i obserwuję nadjeżdżający wóz.
      </Bubble>

      {/* Rzut gracza — prawo, mono */}
      <Bubble side="roll" header="SKRADANIE · DEX">
        d20 (14) + 3 + 2 = 19 vs DC 12 — sukces
      </Bubble>

      {/* Systemowe — wyśrodkowane, kreskowane */}
      <div className="mx-auto rounded-md border border-dashed border-line-mech px-3 py-1.5 font-mono text-micro text-gold">
        Zapadł zmierzch — pora nocna
      </div>

      {/* Composer */}
      <div className="sticky bottom-2 mt-2 flex items-end gap-2 rounded-lg border border-line bg-surface p-2">
        <textarea
          rows={1}
          placeholder="Co robisz?"
          className="max-h-32 min-h-[44px] flex-1 resize-none bg-transparent px-2 py-2.5 text-body text-text placeholder:text-text-3 focus:outline-none"
        />
        <Button variant="ghost" size="icon" aria-label="Głos">
          <Microphone size={20} />
        </Button>
        <Button size="icon" aria-label="Wyślij">
          <PaperPlaneRight weight="fill" size={20} />
        </Button>
      </div>
    </div>
  );
}

function Bubble({
  side,
  header,
  children,
}: {
  side: "gm" | "player" | "roll";
  header: string;
  children: ReactNode;
}) {
  const isRight = side !== "gm";
  return (
    <div className={cn("flex", isRight ? "justify-end" : "justify-start")}>
      <div
        className={cn(
          "max-w-[88%] rounded-lg px-3.5 py-2.5",
          side === "gm" &&
            "border-l-2 border-line-ember bg-gm-bubble font-serif text-prose text-text",
          side === "player" &&
            "border-r-2 border-line-ember bg-player-card font-serif italic text-prose text-text",
          side === "roll" &&
            "border border-line-ember bg-player-card font-mono text-label text-text",
        )}
      >
        <div
          className={cn(
            "mb-1 font-ui text-micro uppercase tracking-wide",
            side === "roll" ? "text-gold" : "text-ember-glow",
          )}
        >
          {header}
        </div>
        {children}
      </div>
    </div>
  );
}
