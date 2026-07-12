// FAZA ML — mapa lokalna osady (sub-lokacje jako hex-grid map_level=1).
// Parytet ze starym UI (app.js _lmRefresh/initLocalMap): nagłówek huba, hex-grid
// sub-lokacji, aktualna pozycja glow, klik = przejdź (+15 min), „← Świat" wraca
// na mapę świata. Endpoint: GET /local-map + POST /local-travel.
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Crosshair, Globe, MapPinSimpleArea, Minus, Plus, X } from "@phosphor-icons/react";
import { useLocalMap, useLocalTravel } from "@/hooks/useGameData";
import type { LocalHex } from "@/hooks/useGameData";
import { useAppStore } from "@/store/appStore";
import { hexPoints, hexToPixel, terrainIcon } from "@/lib/worldmap";
import { useToast } from "@/components/ui/toast";
import { TravelCinematic } from "./TravelCinematic";

const VB_W = 340;
const VB_H = 320;
const MIN_ZOOM = 0.3;
const MAX_ZOOM = 3.0;

export function LocalMap({
  campaignId,
  onWorld,
}: {
  campaignId: number;
  onWorld: () => void;
}) {
  const setGameTab = useAppStore((s) => s.setGameTab);
  const map = useLocalMap(campaignId, true);
  const travel = useLocalTravel(campaignId);
  const { toast } = useToast();

  const hexes = map.data?.hexes ?? [];
  const cur = map.data?.current_local_hex ?? null;
  const hubLabel = map.data?.hub_label ?? "Osada";

  const containerRef = useRef<HTMLDivElement>(null);
  type HexTooltip = { label: string; sub: string; x: number; y: number; flipX: boolean; flipY: boolean };
  const [hexTooltip, setHexTooltip] = useState<HexTooltip | null>(null);

  const onHexHoverIn = useCallback((label: string, sub: string, e: React.MouseEvent) => {
    if (!containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    setHexTooltip({ label, sub, x, y, flipX: x > rect.width * 0.62, flipY: y < 60 });
  }, []);

  const onHexHoverOut = useCallback(() => setHexTooltip(null), []);

  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const drag = useRef<{ x: number; y: number; sx: number; sy: number } | null>(null);
  const movedRef = useRef(false);

  const center = useMemo(() => {
    if (cur) return hexToPixel(cur.q, cur.r);
    if (!hexes.length) return { x: 0, y: 0 };
    const pts = hexes.map((h) => hexToPixel(h.q, h.r));
    return {
      x: pts.reduce((s, p) => s + p.x, 0) / pts.length,
      y: pts.reduce((s, p) => s + p.y, 0) / pts.length,
    };
  }, [cur, hexes]);

  const recenter = useCallback(() => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
  }, []);

  const onPointerDown = (e: React.PointerEvent) => {
    drag.current = { x: e.clientX - pan.x, y: e.clientY - pan.y, sx: e.clientX, sy: e.clientY };
    movedRef.current = false;
    setHexTooltip(null);
  };
  const onPointerMove = (e: React.PointerEvent) => {
    if (!drag.current) return;
    if (Math.abs(e.clientX - drag.current.sx) > 5 || Math.abs(e.clientY - drag.current.sy) > 5) {
      movedRef.current = true;
    }
    setPan({ x: e.clientX - drag.current.x, y: e.clientY - drag.current.y });
  };
  const onPointerUp = () => {
    drag.current = null;
    requestAnimationFrame(() => { movedRef.current = false; });
  };
  const onWheel = (e: React.WheelEvent) => {
    const next = zoom * (e.deltaY < 0 ? 1.12 : 0.89);
    setZoom(Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, next)));
  };

  const isCurrent = (h: LocalHex) => !!cur && h.q === cur.q && h.r === cur.r;

  const [cinematic, setCinematic] = useState<{ from: string; dest: string } | null>(null);

  useEffect(() => {
    if (cinematic && !travel.isPending) {
      const t = setTimeout(() => setCinematic(null), 1200);
      return () => clearTimeout(t);
    }
  }, [cinematic, travel.isPending]);

  const go = (h: LocalHex) => {
    if (movedRef.current || travel.isPending) return;
    if (isCurrent(h)) return;
    const fromHex = hexes.find((x) => isCurrent(x));
    setCinematic({
      from: fromHex?.label || hubLabel,
      dest: h.label || "Zakątek osady",
    });
    travel.mutate(h.id, {
      onSuccess: () => {},
      onError: (e) => {
        setCinematic(null);
        toast(e instanceof Error ? e.message : "Nie można tam przejść.", "danger");
      },
    });
  };

  const groupTransform = `translate(${VB_W / 2 + pan.x} ${VB_H / 2 + pan.y}) scale(${zoom}) translate(${-center.x} ${-center.y})`;

  return (
    <div className="flex h-full min-h-0 min-w-0 flex-1 flex-col lg:flex-row">
      <div className="flex min-h-0 min-w-0 flex-1 flex-col">
        {/* nagłówek huba */}
        <header
          className="flex shrink-0 items-center gap-3 border-b border-line bg-surface px-4 py-2.5"
          style={{ paddingTop: "max(10px, var(--sa-top))" }}
        >
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md border border-line-ember bg-[rgba(255,122,61,.1)] text-ember-glow">
            <MapPinSimpleArea size={18} />
          </div>
          <div className="min-w-0 flex-1">
            <div className="font-ui text-[9px] font-semibold uppercase tracking-[0.16em] text-text-3">
              Mapa osady
            </div>
            <div className="truncate font-serif text-body font-semibold text-text">{hubLabel}</div>
          </div>
          <button
            onClick={onWorld}
            className="flex h-9 shrink-0 items-center gap-1.5 rounded-md border border-line bg-bg px-3 font-ui text-label text-text-2 transition-colors hover:border-line-ember hover:text-ember-glow"
          >
            <Globe size={15} />
            Świat
          </button>
          <button
            aria-label="Zamknij mapę"
            onClick={() => setGameTab("story")}
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md border border-line bg-bg text-text-2 transition-colors hover:border-line-ember hover:text-ember-glow"
          >
            <X size={16} />
          </button>
        </header>

        {/* kanwa */}
        <div className="flex min-h-0 flex-1 flex-col p-3">
          <div
            ref={containerRef}
            className="relative flex min-h-0 flex-1 overflow-hidden rounded-lg border border-line"
            style={{
              background:
                "radial-gradient(70% 60% at 50% 40%, rgba(255,122,61,.06), transparent 70%), var(--surface)",
            }}
          >
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
              <div className="flex h-full w-full items-center justify-center font-ui text-body text-text-3">
                Wczytywanie mapy osady…
              </div>
            ) : hexes.length === 0 ? (
              <div className="flex h-full w-full items-center justify-center px-6 text-center font-serif text-prose text-text-3">
                Ta osada nie ma jeszcze rozrysowanych zakątków.
              </div>
            ) : (
              <svg
                viewBox={`0 0 ${VB_W} ${VB_H}`}
                preserveAspectRatio="xMidYMid meet"
                className="block h-full w-full touch-none select-none"
                style={{ cursor: drag.current ? "grabbing" : "grab" }}
                onPointerDown={onPointerDown}
                onPointerMove={onPointerMove}
                onPointerUp={onPointerUp}
                onPointerLeave={onPointerUp}
                onWheel={onWheel}
              >
                <defs>
                  <filter id="lhexglow" x="-50%" y="-50%" width="200%" height="200%">
                    <feGaussianBlur stdDeviation="4" result="b" />
                    <feMerge>
                      <feMergeNode in="b" />
                      <feMergeNode in="SourceGraphic" />
                    </feMerge>
                  </filter>
                </defs>
                <g transform={groupTransform}>
                  {hexes.map((h) => (
                    <LocalTile
                      key={h.id}
                      hex={h}
                      current={isCurrent(h)}
                      onHoverIn={onHexHoverIn}
                      onHoverOut={onHexHoverOut}
                      onClick={() => go(h)}
                    />
                  ))}
                </g>
              </svg>
            )}
            {hexTooltip && (
              <div
                className="pointer-events-none absolute z-[50] max-w-[200px] rounded-lg border border-line px-3 py-2 shadow-xl"
                style={{
                  background: "rgba(30,24,17,0.97)",
                  left: hexTooltip.x,
                  top: hexTooltip.y,
                  transform: [
                    hexTooltip.flipX ? "translateX(calc(-100% - 12px))" : "translateX(12px)",
                    hexTooltip.flipY ? "translateY(12px)" : "translateY(calc(-100% - 12px))",
                  ].join(" "),
                }}
              >
                <div className="font-ui text-label font-semibold text-text">{hexTooltip.label}</div>
                {hexTooltip.sub && (
                  <div className="font-ui text-micro text-text-3">{hexTooltip.sub}</div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* panel — aktualna lokacja + podpowiedź */}
      <aside className="shrink-0 border-t border-line px-4 pb-5 pt-1 lg:w-[300px] lg:overflow-y-auto lg:border-l lg:border-t-0 lg:pt-4">
        {(() => {
          const curHex = hexes.find((h) => isCurrent(h));
          return curHex ? (
            <div className="rounded-xl border border-line-ember bg-[var(--player-card)] px-3.5 py-3">
              <div className="flex items-center gap-2.5">
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-line-ember bg-[rgba(255,122,61,.12)] text-ember-glow">
                  <MapPinSimpleArea size={16} />
                </div>
                <div className="min-w-0">
                  <div className="font-ui text-[9px] font-semibold uppercase tracking-widest text-text-3">Jesteś w</div>
                  <div className="truncate font-serif text-body font-semibold text-text">
                    {curHex.label || "Zakątek osady"}
                  </div>
                </div>
              </div>
              <p className="mt-2.5 font-ui text-micro text-text-3">
                {travel.isPending ? "Przemieszczam się…" : "Kliknij zakątek na mapie, aby tam przejść (+15 min)."}
              </p>
            </div>
          ) : (
            <div className="rounded-xl border border-line bg-surface px-4 py-6 text-center font-ui text-body text-text-3">
              Kliknij zakątek osady, aby tam przejść.
            </div>
          );
        })()}
      </aside>

      {cinematic && (
        <TravelCinematic
          fromLabel={cinematic.from}
          destLabel={cinematic.dest}
          progressMs={2000}
          onDone={() => setCinematic(null)}
        />
      )}
    </div>
  );
}

function LocalTile({
  hex,
  current,
  onHoverIn,
  onHoverOut,
  onClick,
}: {
  hex: LocalHex;
  current: boolean;
  onHoverIn: (label: string, sub: string, e: React.MouseEvent) => void;
  onHoverOut: () => void;
  onClick: () => void;
}) {
  const { x, y } = hexToPixel(hex.q, hex.r);
  const Icon = terrainIcon(hex.hex_type);
  const fill = current ? "#3a2413" : "#241a10";
  const stroke = current ? "var(--ember)" : "rgba(242,232,216,.16)";
  const label = hex.label && !/^\([-\d]+,[-\d]+\)$/.test(hex.label) ? hex.label : null;
  return (
    <g
      onClick={(e) => { e.stopPropagation(); onClick(); }}
      onMouseEnter={(e) => onHoverIn(label || "Zakątek osady", current ? "Twoja pozycja" : "Sub-lokacja (+15 min)", e)}
      onMouseLeave={onHoverOut}
      style={{ cursor: current ? "default" : "pointer" }}
    >
      <polygon
        points={hexPoints(x, y)}
        fill={fill}
        stroke={stroke}
        strokeWidth={current ? 2.5 : 1.4}
        filter={current ? "url(#lhexglow)" : undefined}
      />
      <foreignObject x={x - 11} y={y - 11} width={22} height={22} style={{ pointerEvents: "none" }}>
        <div className="flex h-full w-full items-center justify-center">
          <Icon size={17} color={current ? "var(--ember-glow)" : "var(--text-2)"} weight={current ? "fill" : "regular"} />
        </div>
      </foreignObject>
    </g>
  );
}

function MapTool({ label, onClick, children }: { label: string; onClick: () => void; children: React.ReactNode }) {
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
