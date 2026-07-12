// #1219 (B) — popup „Łuk dnia": klik w zegar topbaru otwiera wizualizację doby.
// Półokrąg horyzontu ze słońcem/księżycem wędrującym wg godziny, gradient nieba
// zależny od pory dnia, pogoda (ikona + etykieta + wpływ na marsz), pora roku
// oraz podpowiedź nocnej ekonomii. Dane w całości z GET /campaigns/{id}/clock.
import { useEffect, useState } from "react";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import {
  Sun,
  MoonStars,
  Cloud,
  CloudRain,
  CloudFog,
  CloudSnow,
  CloudLightning,
  ThermometerHot,
  X,
} from "@phosphor-icons/react";
import type { ClockState, WeatherState } from "@/lib/types";
import {
  arcPoint,
  arcProgress,
  phaseTheme,
  SEASON_ICON,
  SEASON_PL,
} from "@/lib/worldClock";

const WEATHER_ICON: Record<string, typeof Cloud> = {
  clear: Sun,
  clouds: Cloud,
  rain: CloudRain,
  storm: CloudLightning,
  fog: CloudFog,
  snow: CloudSnow,
  heat: ThermometerHot,
};

export function DayArcModal({
  open,
  onOpenChange,
  clock,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  clock: ClockState | null | undefined;
}) {
  if (!clock) return null;
  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-black/[.66] animate-fade-in" />
        <DialogPrimitive.Content
          aria-describedby={undefined}
          className="fixed left-1/2 top-1/2 z-50 flex w-[calc(100%-2rem)] max-w-[420px] -translate-x-1/2 -translate-y-1/2 flex-col overflow-hidden rounded-xl border border-line-ember bg-gradient-to-b from-[#211811] to-[#171009] shadow-modal animate-fade-in"
        >
          <ArcBody clock={clock} onClose={() => onOpenChange(false)} />
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}

function ArcBody({ clock, onClose }: { clock: ClockState; onClose: () => void }) {
  const theme = phaseTheme(clock.hour);
  const { t, body } = arcProgress(clock.hour);
  const weather = clock.weather ?? null;

  // Animacja wejścia: dysk startuje na wschodnim horyzoncie (t=0) i dojeżdża
  // na właściwą pozycję po zamontowaniu (transition na transform).
  const [drawn, setDrawn] = useState(false);
  useEffect(() => {
    const id = requestAnimationFrame(() => setDrawn(true));
    return () => cancelAnimationFrame(id);
  }, []);

  // Geometria łuku (viewBox 0 0 320 172).
  const CX = 160,
    CY = 150,
    R = 128;
  const pos = arcPoint(drawn ? t : 0, CX, CY, R);
  const gradId = `sky-${theme.phase}`;

  return (
    <>
      <DialogPrimitive.Title className="sr-only">
        Zegar świata — {clock.display}
      </DialogPrimitive.Title>

      {/* Scena nieba + łuk */}
      <div className="relative">
        <svg viewBox="0 0 320 172" className="block w-full">
          <defs>
            <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={theme.sky[0]} />
              <stop offset="55%" stopColor={theme.sky[1]} />
              <stop offset="100%" stopColor={theme.sky[2]} />
            </linearGradient>
            <radialGradient id="body-glow" cx="50%" cy="50%" r="50%">
              <stop
                offset="0%"
                stopColor={body === "sun" ? "#ffd27a" : "#cdd6ff"}
                stopOpacity="0.9"
              />
              <stop offset="100%" stopColor="#000" stopOpacity="0" />
            </radialGradient>
          </defs>

          {/* Wypełnienie nieba pod łukiem */}
          <path
            d={`M ${CX - R} ${CY} A ${R} ${R} 0 0 1 ${CX + R} ${CY} Z`}
            fill={`url(#${gradId})`}
          />
          {/* Łuk (ścieżka doby) */}
          <path
            d={`M ${CX - R} ${CY} A ${R} ${R} 0 0 1 ${CX + R} ${CY}`}
            fill="none"
            stroke="rgba(255,255,255,0.18)"
            strokeWidth="1.5"
            strokeDasharray="3 5"
          />
          {/* Linia horyzontu */}
          <line
            x1={CX - R - 8}
            y1={CY}
            x2={CX + R + 8}
            y2={CY}
            stroke="rgba(255,255,255,0.28)"
            strokeWidth="1.5"
          />

          {/* Poświata + dysk słońca/księżyca — animowany po X/Y */}
          <g
            style={{
              transform: `translate(${pos.x - CX}px, ${pos.y - CY}px)`,
              transition: "transform 900ms cubic-bezier(.22,1,.36,1)",
            }}
          >
            <circle cx={CX} cy={CY} r="30" fill="url(#body-glow)" />
            <circle
              cx={CX}
              cy={CY}
              r="13"
              fill={body === "sun" ? "#ffcf6b" : "#e6ebff"}
              stroke={body === "sun" ? "#ffe6a8" : "#ffffff"}
              strokeWidth="1"
            />
            {body === "moon" && (
              <circle cx={CX + 5} cy={CY - 3} r="11" fill={theme.sky[0]} />
            )}
          </g>
        </svg>

        {/* Ambient pogody nad sceną (deszcz/śnieg/mgła) */}
        {weather && <WeatherAmbient type={weather.type} />}

        {/* Zamknięcie */}
        <button
          aria-label="Zamknij"
          onClick={onClose}
          className="absolute right-2.5 top-2.5 flex h-8 w-8 items-center justify-center rounded-md bg-black/30 text-text-2 backdrop-blur transition-colors hover:text-ember-glow"
        >
          <X size={16} />
        </button>
      </div>

      {/* Odczyt: dzień · godzina · pora dnia · pora roku */}
      <div className="border-t border-line px-5 pt-4">
        <div className="flex items-baseline gap-2">
          <span className="font-serif text-title-lg font-semibold text-text">
            {clock.hour_str}
          </span>
          <span
            className="font-ui text-label font-semibold uppercase tracking-wide"
            style={{ color: theme.accent }}
          >
            {theme.label}
          </span>
        </div>
        <div className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-micro text-text-3">
          <span>Dzień {clock.day}</span>
          {clock.season && (
            <>
              <span className="opacity-40">·</span>
              <span>
                {SEASON_ICON[clock.season] ?? ""}{" "}
                {SEASON_PL[clock.season] ?? clock.season}
              </span>
            </>
          )}
        </div>
      </div>

      {/* Pogoda */}
      {weather && (
        <div className="px-5 pt-3">
          <WeatherRow weather={weather} />
        </div>
      )}

      {/* Podpowiedź nocnej ekonomii */}
      {clock.night_hint && (
        <div className="mx-5 mt-3 flex items-start gap-2 rounded-md border border-line-ember bg-[rgba(255,122,61,0.08)] px-3 py-2">
          <MoonStars
            weight="fill"
            size={16}
            className="mt-0.5 flex-none text-ember-glow"
          />
          <p className="font-ui text-micro leading-snug text-text-2">
            {clock.night_hint}
          </p>
        </div>
      )}

      <div className="h-5" />
    </>
  );
}

function WeatherRow({ weather }: { weather: WeatherState }) {
  const Icon = WEATHER_ICON[weather.type] ?? Cloud;
  return (
    <div className="flex items-center gap-3 rounded-lg border border-line bg-black/20 px-3.5 py-3">
      <div className="flex h-10 w-10 flex-none items-center justify-center rounded-lg border border-line bg-surface text-text">
        <Icon weight="fill" size={22} />
      </div>
      <div className="min-w-0 flex-1">
        <div className="font-serif text-body font-semibold lowercase text-text first-letter:uppercase">
          {weather.label}
        </div>
        <div className="font-ui text-micro text-text-3">Pogoda w okolicy</div>
      </div>
      {weather.effect && (
        <span className="flex-none rounded-pill border border-line-ember bg-[rgba(255,122,61,0.1)] px-2.5 py-1 font-ui text-micro font-semibold text-ember-glow">
          {weather.effect}
        </span>
      )}
    </div>
  );
}

// Efekt atmosferyczny — kilka animowanych elementów CSS. Świadomie skromny
// (wydajność mobile). Wyłączony dla clear/clouds/heat.
function WeatherAmbient({ type }: { type: string }) {
  if (type === "rain" || type === "storm") {
    const drops = Array.from({ length: 16 });
    return (
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <style>{RAIN_CSS}</style>
        {drops.map((_, i) => (
          <span
            key={i}
            className="dac-rain"
            style={{
              left: `${(i * 6.3 + 3) % 100}%`,
              animationDelay: `${(i % 5) * 0.18}s`,
              animationDuration: `${0.7 + (i % 3) * 0.15}s`,
            }}
          />
        ))}
      </div>
    );
  }
  if (type === "snow") {
    const flakes = Array.from({ length: 14 });
    return (
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <style>{SNOW_CSS}</style>
        {flakes.map((_, i) => (
          <span
            key={i}
            className="dac-snow"
            style={{
              left: `${(i * 7.1 + 2) % 100}%`,
              animationDelay: `${(i % 6) * 0.4}s`,
              animationDuration: `${2.6 + (i % 4) * 0.5}s`,
            }}
          />
        ))}
      </div>
    );
  }
  if (type === "fog") {
    return (
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <style>{FOG_CSS}</style>
        <span className="dac-fog" style={{ top: "38%" }} />
        <span className="dac-fog" style={{ top: "62%", animationDelay: "-6s" }} />
      </div>
    );
  }
  return null;
}

const RAIN_CSS = `
.dac-rain{position:absolute;top:-12%;width:1px;height:14px;background:linear-gradient(rgba(180,205,255,0),rgba(180,205,255,.55));animation-name:dac-fall;animation-timing-function:linear;animation-iteration-count:infinite;}
@keyframes dac-fall{from{transform:translateY(0);opacity:0}10%{opacity:1}to{transform:translateY(200px);opacity:.2}}
`;
const SNOW_CSS = `
.dac-snow{position:absolute;top:-8%;width:4px;height:4px;border-radius:50%;background:rgba(255,255,255,.85);animation-name:dac-drift;animation-timing-function:linear;animation-iteration-count:infinite;}
@keyframes dac-drift{from{transform:translate(0,0);opacity:0}12%{opacity:1}to{transform:translate(10px,190px);opacity:.15}}
`;
const FOG_CSS = `
.dac-fog{position:absolute;left:-30%;width:160%;height:34px;border-radius:50%;background:radial-gradient(closest-side,rgba(200,205,220,.22),rgba(200,205,220,0));filter:blur(6px);animation:dac-fog-drift 14s ease-in-out infinite alternate;}
@keyframes dac-fog-drift{from{transform:translateX(-8%)}to{transform:translateX(8%)}}
`;
