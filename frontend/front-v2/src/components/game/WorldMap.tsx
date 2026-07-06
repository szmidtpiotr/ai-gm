// F-43 Mapa świata + panel podróży (makieta zar5-mapa). Nagłówek zegar+pora+
// lokacja (przeniesiony z paska gry), hex-mapa z mgłą wojny, aktualny heks glow,
// cel z flagą, zoom/centruj (ikony terenu = Phosphor przez foreignObject).
// Panel podróży: dystans/czas/teren/spotkanie + ostrzeżenie nocy + Podróżuj →
// cinematyka F-47. KROK 4 FE8 (#1235).
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Crosshair,
  FlagBanner,
  MapPinSimpleArea,
  MoonStars,
  Path,
  Plus,
  Minus,
  Sun,
  X,
} from "@phosphor-icons/react";
import {
  useCampaignClock,
  useCharacter,
  useTravel,
  useWorldMap,
} from "@/hooks/useGameData";
import { useAppStore } from "@/store/appStore";
import {
  estimateTravel,
  hexPoints,
  hexToPixel,
  terrainIcon,
} from "@/lib/worldmap";
import type { WorldHex } from "@/lib/types";
import { cn } from "@/lib/utils";
import { TravelCinematic } from "./TravelCinematic";

const VB_W = 340;
const VB_H = 320;
const MIN_ZOOM = 0.4;
const MAX_ZOOM = 2.4;

interface Props {
  campaignId: number;
  characterId: number;
}

export function WorldMap({ campaignId, characterId }: Props) {
  const setGameTab = useAppStore((s) => s.setGameTab);
  const map = useWorldMap(campaignId, characterId);
  const clock = useCampaignClock(campaignId);
  const character = useCharacter(characterId);
  const travel = useTravel(campaignId);

  const hexes = map.data?.hexes ?? [];
  const hexTypes = map.data?.hex_types ?? {};
  const currentHex = map.data?.current_hex ?? null;

  const period = clock.data?.period ?? "";
  const isNight = /noc/i.test(period);
  const time = clock.data?.hour_str ?? "—:—";
  const dayLabel = clock.data
    ? `Dzień ${clock.data.day} · ${period || "—"}`
    : "—";
  const locationLabel =
    character.data?.current_location_label ?? "W drodze przez Kresy";

  // ── zoom / pan ─────────────────────────────────────────────────────────────
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const drag = useRef<{ x: number; y: number } | null>(null);

  const center = useMemo(() => {
    if (currentHex) return hexToPixel(currentHex.q, currentHex.r);
    // Brak pozycji → środek chmury odkrytych heksów.
    const disc = hexes.filter((h) => h.status === "discovered");
    if (!disc.length) return { x: 0, y: 0 };
    const pts = disc.map((h) => hexToPixel(h.q, h.r));
    return {
      x: pts.reduce((s, p) => s + p.x, 0) / pts.length,
      y: pts.reduce((s, p) => s + p.y, 0) / pts.length,
    };
  }, [currentHex, hexes]);

  const recenter = useCallback(() => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
  }, []);

  const onPointerDown = (e: React.PointerEvent) => {
    drag.current = { x: e.clientX - pan.x, y: e.clientY - pan.y };
    (e.currentTarget as Element).setPointerCapture?.(e.pointerId);
  };
  const onPointerMove = (e: React.PointerEvent) => {
    if (!drag.current) return;
    setPan({ x: e.clientX - drag.current.x, y: e.clientY - drag.current.y });
  };
  const onPointerUp = () => {
    drag.current = null;
  };
  const onWheel = (e: React.WheelEvent) => {
    const next = zoom * (e.deltaY < 0 ? 1.12 : 0.89);
    setZoom(Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, next)));
  };

  // ── selection / travel ─────────────────────────────────────────────────────
  const [selected, setSelected] = useState<WorldHex | null>(null);
  const [cinematic, setCinematic] = useState<{
    destLabel: string;
    fromLabel: string | null;
    hours: number | null;
    atmosphere: string | null;
  } | null>(null);

  const selectHex = (h: WorldHex) => {
    if (currentHex && h.q === currentHex.q && h.r === currentHex.r) return;
    if (h.status === "outline" || h.status === "unexplored") {
      // Znany kierunek bez danych — pozwól podróżować „w nieznane".
      setSelected(h);
      return;
    }
    setSelected(h);
  };

  const realLabel = (h: WorldHex | null): string | null => {
    if (!h?.label) return null;
    return /^\([-\d]+,[-\d]+\)$/.test(h.label) ? null : h.label;
  };

  const estimate = selected
    ? estimateTravel(currentHex, selected, selected.hex_type)
    : null;

  const startTravel = () => {
    if (!selected) return;
    const terrainName = selected.hex_type
      ? hexTypes[selected.hex_type]?.label
      : null;
    setCinematic({
      destLabel: realLabel(selected) || terrainName || "celu",
      fromLabel: realLabel(
        hexes.find(
          (h) =>
            currentHex && h.q === currentHex.q && h.r === currentHex.r,
        ) ?? null,
      ),
      hours: estimate?.hours ?? null,
      atmosphere: null,
    });
    travel.mutate(
      { characterId, q: selected.q, r: selected.r },
      {
        onSuccess: (res) => {
          const atmo = res.hex_data?.atmosphere ?? null;
          setCinematic((c) => (c ? { ...c, atmosphere: atmo } : c));
        },
      },
    );
    setSelected(null);
  };

  // Auto-domknięcie cinematyki po zakończeniu podróży (min. czas na pasek).
  useEffect(() => {
    if (cinematic && !travel.isPending) {
      const t = setTimeout(() => setCinematic(null), 1300);
      return () => clearTimeout(t);
    }
  }, [cinematic, travel.isPending]);

  const groupTransform = `translate(${VB_W / 2 + pan.x} ${VB_H / 2 + pan.y}) scale(${zoom}) translate(${-center.x} ${-center.y})`;

  return (
    <div className="flex h-full min-h-0 flex-col lg:flex-row">
      {/* Nagłówek: zegar+pora+lokacja + zamknij (mobile pełna szer.) */}
      <div className="flex flex-col lg:min-w-0 lg:flex-1">
        <header
          className="flex shrink-0 items-center gap-3 border-b border-line bg-surface px-4 py-2.5"
          style={{ paddingTop: "max(10px, var(--sa-top))" }}
        >
          <div className="flex shrink-0 flex-col border-r border-line pr-3 leading-tight">
            <span className="font-mono text-body font-semibold text-text">
              {time}
            </span>
            <span className="flex items-center gap-1 font-ui text-micro text-text-2">
              {isNight ? (
                <MoonStars weight="fill" className="text-mana" size={12} />
              ) : (
                <Sun weight="fill" className="text-gold" size={12} />
              )}
              {dayLabel}
            </span>
          </div>
          <div className="min-w-0 flex-1">
            <div className="font-ui text-[9px] font-semibold uppercase tracking-[0.16em] text-text-3">
              Jesteś w
            </div>
            <div className="truncate font-serif text-body font-semibold text-text">
              {locationLabel}
            </div>
          </div>
          <button
            aria-label="Zamknij mapę"
            onClick={() => setGameTab("story")}
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md border border-line bg-bg text-text-2 transition-colors hover:border-line-ember hover:text-ember-glow"
          >
            <X size={16} />
          </button>
        </header>

        {/* Mapa */}
        <div className="min-h-0 flex-1 overflow-y-auto p-4 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
          <div
            className="relative overflow-hidden rounded-lg border border-line p-3"
            style={{
              background:
                "radial-gradient(70% 60% at 50% 40%, rgba(255,122,61,.06), transparent 70%), var(--surface)",
            }}
          >
            {/* narzędzia zoom/centruj */}
            <div className="absolute right-2.5 top-2.5 z-[3] flex flex-col gap-1.5">
              <MapTool label="Przybliż" onClick={() => setZoom((z) => Math.min(MAX_ZOOM, z * 1.2))}>
                <Plus size={14} />
              </MapTool>
              <MapTool label="Oddal" onClick={() => setZoom((z) => Math.max(MIN_ZOOM, z * 0.83))}>
                <Minus size={14} />
              </MapTool>
              <MapTool label="Wyśrodkuj" onClick={recenter}>
                <Crosshair size={14} />
              </MapTool>
            </div>

            {map.isLoading ? (
              <div className="flex h-64 items-center justify-center font-ui text-body text-text-3">
                Wczytywanie mapy…
              </div>
            ) : (
              <svg
                viewBox={`0 0 ${VB_W} ${VB_H}`}
                className="block w-full touch-none select-none"
                style={{ height: "auto", cursor: drag.current ? "grabbing" : "grab" }}
                onPointerDown={onPointerDown}
                onPointerMove={onPointerMove}
                onPointerUp={onPointerUp}
                onPointerLeave={onPointerUp}
                onWheel={onWheel}
              >
                <defs>
                  <filter id="hexglow" x="-50%" y="-50%" width="200%" height="200%">
                    <feGaussianBlur stdDeviation="4" result="b" />
                    <feMerge>
                      <feMergeNode in="b" />
                      <feMergeNode in="SourceGraphic" />
                    </feMerge>
                  </filter>
                </defs>
                <g transform={groupTransform}>
                  {hexes.map((h) => (
                    <HexTile
                      key={`${h.q},${h.r}`}
                      hex={h}
                      color={
                        h.hex_type ? hexTypes[h.hex_type]?.map_color : undefined
                      }
                      isCurrent={
                        !!currentHex &&
                        h.q === currentHex.q &&
                        h.r === currentHex.r
                      }
                      isSelected={
                        !!selected && h.q === selected.q && h.r === selected.r
                      }
                      onClick={() => selectHex(h)}
                    />
                  ))}
                </g>
              </svg>
            )}

            {/* legenda */}
            <div className="flex flex-wrap gap-x-4 gap-y-2.5 px-1 pb-1 pt-3 font-ui text-micro text-text-2">
              <LegendDot className="border-ember bg-[#3a2413]" label="Twoja pozycja" />
              <LegendDot className="border-[#7fa860] bg-[#1e2716]" label="Odkryte" />
              <LegendDot className="border-mana bg-[#162530]" label="Znane z opowieści" />
              <LegendDot className="border-dashed border-line bg-[#171009]" label="Nieodkryte" />
            </div>
          </div>
        </div>
      </div>

      {/* Panel podróży (desktop prawy słupek / mobile pod mapą) */}
      <aside className="shrink-0 border-t border-line px-4 pb-5 pt-1 lg:w-[360px] lg:overflow-y-auto lg:border-l lg:border-t-0 lg:px-4 lg:pt-4">
        {selected && estimate ? (
          <div className="overflow-hidden rounded-xl border border-line-ember bg-[var(--player-card)]">
            <div className="flex items-center gap-2.5 border-b border-line-soft px-3.5 py-3">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md border border-line-ember bg-[rgba(255,122,61,.12)] text-ember-glow">
                <MapPinSimpleArea size={18} />
              </div>
              <div className="min-w-0">
                <div className="truncate font-serif text-title font-semibold text-text">
                  {realLabel(selected) ||
                    (selected.hex_type
                      ? hexTypes[selected.hex_type]?.label
                      : null) ||
                    "Nieznany teren"}
                </div>
                <div className="font-ui text-micro text-text-2">
                  {(selected.hex_type
                    ? hexTypes[selected.hex_type]?.label
                    : "Nieznany teren") ?? "Nieznany teren"}
                  {selected.status === "known" && (
                    <span className="text-ember-glow"> · cel z opowieści ⚑</span>
                  )}
                </div>
              </div>
            </div>

            <div className="flex px-1.5 py-2.5 font-mono">
              <TravelStat k="Dystans" v={`${estimate.distance} ${estimate.distance === 1 ? "heks" : "heks."}`} />
              <TravelStat k="Czas" v={`~${estimate.hours} h`} />
              <TravelStat k="Teren" v={estimate.difficulty} />
              <TravelStat k="Spotkanie" v={estimate.encounter} warn={estimate.encounterWarn} last />
            </div>

            {isNight && (
              <div className="mx-3.5 mb-3 flex items-center gap-2 rounded-md border border-line-danger bg-[rgba(232,96,79,.06)] px-3 py-2 font-ui text-micro text-text">
                <MoonStars className="shrink-0 text-danger" size={15} />
                Podróż nocą — zmęczenie rośnie szybciej, gorsza widoczność.
              </div>
            )}

            <div className="flex gap-2 px-3.5 pb-3.5 pt-1">
              <button
                onClick={startTravel}
                disabled={travel.isPending}
                className="flex flex-1 items-center justify-center gap-2 rounded-md px-3 py-3 font-ui text-body font-semibold text-white disabled:opacity-60"
                style={{
                  background: "linear-gradient(135deg, #d1602c, var(--ember))",
                  boxShadow: "0 0 16px rgba(255,122,61,.35)",
                }}
              >
                <Path size={17} />
                {travel.isPending
                  ? "W drodze…"
                  : `Podróżuj do ${realLabel(selected) || (selected.hex_type ? hexTypes[selected.hex_type]?.label : "celu") || "celu"}`}
              </button>
              <button
                aria-label="Anuluj"
                onClick={() => setSelected(null)}
                className="flex shrink-0 items-center justify-center rounded-md border border-line bg-bg px-4 py-3 text-text-2"
              >
                <X size={16} />
              </button>
            </div>
          </div>
        ) : (
          <div className="rounded-xl border border-line bg-surface px-4 py-6 text-center font-ui text-body text-text-3">
            Dotknij heksa na mapie, aby zaplanować podróż.
          </div>
        )}
        {travel.isError && (
          <div className="mt-3 rounded-md border border-line-danger bg-[rgba(232,96,79,.06)] px-3 py-2 font-ui text-micro text-danger-glow">
            {(travel.error as Error)?.message || "Błąd podróży"}
          </div>
        )}
      </aside>

      {cinematic && (
        <TravelCinematic
          destLabel={cinematic.destLabel}
          atmosphere={cinematic.atmosphere}
          fromLabel={cinematic.fromLabel}
          hours={cinematic.hours}
          isNight={isNight}
          time={time}
          onDone={() => setCinematic(null)}
        />
      )}
    </div>
  );
}

// ── heks ─────────────────────────────────────────────────────────────────────
function HexTile({
  hex,
  color,
  isCurrent,
  isSelected,
  onClick,
}: {
  hex: WorldHex;
  color?: string;
  isCurrent: boolean;
  isSelected: boolean;
  onClick: () => void;
}) {
  const { x, y } = hexToPixel(hex.q, hex.r);
  const known = hex.status === "known";
  const discovered = hex.status === "discovered";
  const hasTerrain = (discovered || known) && !!hex.hex_type;
  // Flaga celu tylko na NAZWANYCH heksach znanych z opowieści (nie na każdym
  // heksie mgły „known" — inaczej mapa tonie w chorągiewkach).
  const namedTarget =
    known && !!hex.label && !/^\([-\d]+,[-\d]+\)$/.test(hex.label);

  // Kolor wypełnienia — odkryte pełny kolor, znane przytłumione, mgła ciemna.
  let fill = "#171009";
  let stroke = "rgba(242,232,216,.14)";
  let dash: string | undefined;
  let opacity = 1;
  if (isCurrent) {
    fill = "#3a2413";
    stroke = "var(--ember)";
  } else if (discovered) {
    fill = color ? mix(color) : "#251b11";
  } else if (known) {
    fill = color ? mix(color, 0.42) : "#1a2028";
    stroke = "rgba(130,167,199,.35)";
  } else {
    // outline / unexplored — mgła wojny
    fill = "#171009";
    stroke = "rgba(242,232,216,.08)";
    dash = "4 4";
    opacity = 0.6;
  }

  const Icon = terrainIcon(hex.hex_type);
  const iconColor = isCurrent
    ? "var(--ember-glow)"
    : known
      ? "#a9c6dd"
      : "var(--text-2)";

  return (
    <g
      onClick={(e) => {
        e.stopPropagation();
        onClick();
      }}
      style={{ cursor: "pointer" }}
    >
      <polygon
        points={hexPoints(x, y)}
        fill={fill}
        stroke={isSelected ? "var(--ember-glow)" : stroke}
        strokeWidth={isCurrent ? 2.5 : isSelected ? 2.5 : 1.4}
        strokeDasharray={isSelected ? "5 3" : dash}
        opacity={opacity}
        filter={isCurrent ? "url(#hexglow)" : undefined}
      />
      {hasTerrain && (
        <foreignObject x={x - 11} y={y - 11} width={22} height={22} style={{ pointerEvents: "none" }}>
          <div className="flex h-full w-full items-center justify-center">
            <Icon size={17} color={iconColor} weight={isCurrent ? "fill" : "regular"} />
          </div>
        </foreignObject>
      )}
      {/* flaga celu na NAZWANYCH heksach znanych z opowieści */}
      {namedTarget && (
        <foreignObject x={x - 8} y={y - 26} width={16} height={16} style={{ pointerEvents: "none" }}>
          <div className="flex h-full w-full items-center justify-center">
            <FlagBanner size={13} color="var(--ember-glow)" weight="fill" />
          </div>
        </foreignObject>
      )}
      {isCurrent && (
        <text
          x={x}
          y={y + 26}
          textAnchor="middle"
          className="font-ui"
          style={{ fill: "var(--ember-glow)", fontSize: 9, fontWeight: 700 }}
        >
          ▸ TU
        </text>
      )}
      {!isCurrent && hex.label && !/^\([-\d]+,[-\d]+\)$/.test(hex.label) && (
        <text
          x={x}
          y={y + 24}
          textAnchor="middle"
          className="font-ui"
          style={{ fill: "var(--text-2)", fontSize: 8, fontWeight: 600 }}
        >
          {hex.label.length > 16 ? `${hex.label.slice(0, 16)}…` : hex.label}
        </text>
      )}
    </g>
  );
}

// Przyciemnij kolor terenu do sadzy (czytelność na ciemnym tle).
function mix(hex: string, factor = 0.32): string {
  const m = /^#?([0-9a-f]{6})$/i.exec(hex.trim());
  if (!m) return "#251b11";
  const n = parseInt(m[1], 16);
  const r = Math.round((n >> 16) * factor);
  const g = Math.round(((n >> 8) & 0xff) * factor);
  const b = Math.round((n & 0xff) * factor);
  return `rgb(${r}, ${g}, ${b})`;
}

function MapTool({
  label,
  onClick,
  children,
}: {
  label: string;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      aria-label={label}
      onClick={onClick}
      className="flex h-7 w-7 items-center justify-center rounded-md border border-line bg-[rgba(20,16,12,.8)] text-text-2 transition-colors hover:border-line-ember hover:text-ember-glow"
    >
      {children}
    </button>
  );
}

function LegendDot({ className, label }: { className: string; label: string }) {
  return (
    <span className="flex items-center gap-1.5">
      <i className={cn("h-2.5 w-2.5 rounded-[3px] border", className)} />
      {label}
    </span>
  );
}

function TravelStat({
  k,
  v,
  warn,
  last,
}: {
  k: string;
  v: string;
  warn?: boolean;
  last?: boolean;
}) {
  return (
    <div className={cn("flex-1 text-center", !last && "border-r border-line-soft")}>
      <div className="font-ui text-[8.5px] uppercase tracking-[0.1em] text-text-3">
        {k}
      </div>
      <div className={cn("mt-1 text-label font-medium", warn ? "text-danger" : "text-text")}>
        {v}
      </div>
    </div>
  );
}
