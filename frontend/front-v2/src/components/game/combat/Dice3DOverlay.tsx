// F-70 / F-20 · overlay kości 3D. Makieta: zar7-kosc.html. Owija silnik three.js/cannon
// (lib/dice3d.ts, recreate-per-roll) — po zatrzymaniu odsłania kartę rzutu, potem zwija
// się do feedu (wołający dostaje `onDone`). Fallback 2D gdy WebGL/silnik padnie.
import { useEffect, useRef, useState } from "react";
import { Sparkle, Cube } from "@phosphor-icons/react";
import { cn } from "@/lib/utils";
import type { RollCardData } from "@/lib/types";
import { rollDice3D, type Dice3DConfig } from "@/lib/dice3d";
import { RollCard } from "../RollCard";

export interface DiceJob {
  id: number;
  notation: string; // "1d20"
  forced: number[] | null; // [15]
  card: RollCardData;
  crit?: boolean;
  fumble?: boolean;
  face: number; // wartość do pokazania w kości fallback 2D
  actor?: "player" | "enemy"; // kto rzuca — decyduje czy busy=false po animacji
}

const MOUNT_ID = "dice3d-mount";
const DWELL_MS = 1600; // czas na odczyt karty przed auto-zwinięciem

export function Dice3DOverlay({
  job,
  config,
  onDone,
}: {
  job: DiceJob;
  config?: Dice3DConfig;
  onDone: () => void;
}) {
  const [phase, setPhase] = useState<"rolling" | "result">("rolling");
  const [fallback, setFallback] = useState(false);
  const doneRef = useRef(false);

  // Sekwencja rzutu — nowy `job.id` startuje od nowa.
  useEffect(() => {
    doneRef.current = false;
    setPhase("rolling");
    setFallback(false);
    let cancelled = false;

    rollDice3D(MOUNT_ID, job.notation, job.forced, config ?? {}, () => {
      if (!cancelled) setPhase("result");
    }).then((ok) => {
      if (cancelled) return;
      if (!ok) {
        // Silnik/WebGL padł — pokaż wynik od razu (kość 2D w tle stage).
        setFallback(true);
        window.setTimeout(() => !cancelled && setPhase("result"), 700);
      }
    });

    return () => {
      cancelled = true;
    };
  }, [job.id]); // eslint-disable-line react-hooks/exhaustive-deps

  // Po odsłonięciu karty — dwell, potem zwiń do feedu.
  useEffect(() => {
    if (phase !== "result") return;
    const t = window.setTimeout(() => finish(), DWELL_MS);
    return () => window.clearTimeout(t);
  }, [phase]); // eslint-disable-line react-hooks/exhaustive-deps

  function finish() {
    if (doneRef.current) return;
    doneRef.current = true;
    onDone();
  }

  const critLine = job.crit
    ? "KRYTYCZNE TRAFIENIE!"
    : job.fumble
      ? "PECH — KOMPLIKACJA"
      : null;

  return (
    <div
      className="fixed inset-0 z-50 overflow-hidden"
      style={{
        background:
          "radial-gradient(60% 45% at 50% 38%, rgba(232,193,90,.14), transparent 62%), rgba(8,6,4,.86)",
      }}
      onClick={() => phase === "result" && finish()}
    >
      {/* scena 3D na CAŁY ekran (kanwa dice-box montuje się w #dice3d-mount) —
          kość leci przez pełny obszar, jak w starym froncie. */}
      <div id={MOUNT_ID} className="absolute inset-0" />
      {fallback && (
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center gap-3">
          {(job.forced && job.forced.length > 1 ? job.forced : [job.face]).map((f, i) => (
            <Fallback2D key={i} face={f} sides={sidesOf(job.notation)} />
          ))}
        </div>
      )}

      {/* Warstwa treści nad sceną — nie przechwytuje kliknięć (root łapie „dotknij"). */}
      <div className="pointer-events-none absolute inset-x-0 bottom-0 flex flex-col items-center gap-0 px-6 pb-[max(1.5rem,var(--sa-bottom))]">
        {critLine && phase === "result" && (
          <div
            className={cn(
              "my-1 flex items-center gap-2.5 font-serif text-title-lg font-semibold",
              job.crit ? "text-gold" : "text-danger",
            )}
            style={{ textShadow: "0 0 20px rgba(232,193,90,.4)" }}
          >
            {job.crit && <Sparkle weight="fill" size={20} />} {critLine}
            {job.crit && <Sparkle weight="fill" size={20} />}
          </div>
        )}

        {/* karta wyniku — zwija się do feedu */}
        {phase === "result" && (
          <div className="w-full max-w-[360px] animate-fade-in">
            <RollCard roll={job.card} />
          </div>
        )}

        <div className="mt-3 flex items-center gap-1.5 font-ui text-[11.5px] text-text-3">
          <Cube size={13} className="text-ember" />
          {phase === "rolling" ? "Kość leci…" : "Dotknij, aby kontynuować"}
        </div>
      </div>
    </div>
  );
}

function sidesOf(notation: string): number {
  return Math.max(2, parseInt(notation.split("d")[1] || "20", 10) || 20);
}

// Fallback 2D (pure DOM) — silnik 3D padł. Ląduje na zadanej wartości.
function Fallback2D({ face, sides }: { face: number; sides: number }) {
  const [n, setN] = useState(1);
  useEffect(() => {
    let ticks = 0;
    const iv = window.setInterval(() => {
      setN(1 + Math.floor(Math.random() * sides));
      if (++ticks >= 12) {
        window.clearInterval(iv);
        setN(face);
      }
    }, 60);
    return () => window.clearInterval(iv);
  }, [face, sides]);
  return (
    <div
      className="relative flex h-[132px] w-[132px] items-center justify-center border-2 border-gold"
      style={{
        clipPath: "polygon(50% 0,93% 25%,93% 75%,50% 100%,7% 75%,7% 25%)",
        background: "linear-gradient(150deg,#3a2a17,#241a10)",
        boxShadow: "0 0 34px rgba(232,193,90,.4)",
        transform: "rotate(-9deg)",
      }}
    >
      <span
        className="font-mono text-[52px] font-semibold text-gold"
        style={{ textShadow: "0 0 20px rgba(232,193,90,.7)" }}
      >
        {n}
      </span>
    </div>
  );
}
