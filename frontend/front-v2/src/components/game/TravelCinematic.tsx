// F-47 Cinematyka podróży — pełnoekranowy overlay podczas podróży (makieta
// zar9-podroz). Ikona ścieżki, tytuł „Ku …", proza atmosfery, pasek postępu,
// zegar. Klik = pomiń. KROK 4 FE8 (#1235).
import { useEffect, useState } from "react";
import { MoonStars, Path } from "@phosphor-icons/react";

export interface TravelCinematicProps {
  destLabel: string;
  atmosphere?: string | null;
  fromLabel?: string | null;
  hours?: number | null;
  isNight?: boolean;
  time?: string;
  /** Progress bar fill duration in ms. Default 6000. Use 2000 for local travel. */
  progressMs?: number;
  onDone: () => void;
}

export function TravelCinematic({
  destLabel,
  atmosphere,
  fromLabel,
  hours,
  isNight,
  time,
  progressMs = 6000,
  onDone,
}: TravelCinematicProps) {
  // Pasek 0→100% w tle podróży (wizualny, nie mierzy realnego czasu backendu).
  const [progress, setProgress] = useState(6);
  useEffect(() => {
    const t = setTimeout(() => setProgress(100), 60);
    return () => clearTimeout(t);
  }, []);

  const hoursStr =
    hours != null && hours > 0 ? `~${hours} h do celu` : "u celu";

  return (
    <div
      role="dialog"
      aria-label="Podróż w toku"
      onClick={onDone}
      className="fixed inset-0 z-[60] flex animate-fade-in cursor-pointer flex-col items-center justify-center overflow-hidden px-8 text-center"
      style={{
        background:
          "radial-gradient(70% 50% at 50% 24%, rgba(130,167,199,.14), transparent 60%), radial-gradient(80% 60% at 50% 120%, rgba(255,122,61,.1), transparent 70%), linear-gradient(180deg, #141a24, var(--bg))",
      }}
    >
      <div className="relative z-[2] w-full max-w-[420px]">
        <div
          className="mx-auto mb-5 flex h-24 w-24 items-center justify-center rounded-[26px] border text-[#a9c6dd]"
          style={{
            borderColor: "rgba(130,167,199,.3)",
            background:
              "radial-gradient(circle at 40% 35%, rgba(130,167,199,.25), rgba(20,26,36,.9))",
            boxShadow: "0 0 40px rgba(130,167,199,.25)",
          }}
        >
          <Path weight="fill" size={46} />
        </div>

        <div className="font-ui text-[11px] font-bold uppercase tracking-[0.32em] text-text-3">
          Podróż w toku
        </div>
        <h2 className="mt-2 font-serif text-title-lg font-semibold text-text">
          Ku {destLabel}
        </h2>

        {atmosphere && (
          <p className="mx-auto mt-4 max-w-[360px] font-serif text-body italic leading-[1.7] text-text-2">
            {atmosphere}
          </p>
        )}

        <div className="mt-7">
          <div
            className="h-1.5 overflow-hidden rounded-[4px]"
            style={{
              background: "rgba(255,255,255,.06)",
              boxShadow: "inset 0 0 0 1px var(--line)",
            }}
          >
            <div
              className="h-full rounded-[4px] ease-linear transition-[width]"
              style={{
                transitionDuration: `${progressMs}ms`,
                width: `${progress}%`,
                background: "linear-gradient(90deg, #5f8fb0, #a9c6dd)",
                boxShadow: "0 0 10px rgba(130,167,199,.5)",
              }}
            />
          </div>
          <div className="mt-2.5 flex justify-between font-mono text-[11.5px] text-text-3">
            <span>{fromLabel || "Skąd"}</span>
            <span className="text-text-2">{hoursStr}</span>
            <span className="text-text-2">{destLabel}</span>
          </div>
        </div>

        <div className="mt-5 flex items-center justify-center gap-2 font-ui text-[12.5px] text-text-2">
          {isNight ? (
            <>
              <MoonStars weight="fill" className="text-mana" size={15} />
              Mija noc · zmęczenie rośnie
            </>
          ) : (
            "W drodze…"
          )}
          {time && <span className="text-ember-glow">· {time}</span>}
        </div>
        <div className="mt-6 font-ui text-micro text-text-3">Dotknij, aby pominąć</div>
      </div>
    </div>
  );
}
