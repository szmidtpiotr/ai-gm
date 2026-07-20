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
  PersonSimpleWalk,
  Plus,
  Minus,
  Star,
  Sun,
  Sword,
  Tent,
  Warning,
  X,
  XCircle,
} from "@phosphor-icons/react";
import { useQueryClient } from "@tanstack/react-query";
import {
  useCampaignClock,
  useCharacter,
  useSuggestedActions,
  useTravel,
  useTravelEstimate,
  useWorldMap,
} from "@/hooks/useGameData";
import { useAppStore } from "@/store/appStore";
import {
  estimateTravel,
  hexPoints,
  hexToPixel,
  regionBlockFrom,
  terrainIcon,
} from "@/lib/worldmap";
import type { WorldHex, MarchBudget, TravelResult } from "@/lib/types";
import type { TravelNotice } from "@/hooks/useGameData";
import { cn } from "@/lib/utils";
import { DayArcModal } from "./DayArcModal";

// #1381 — animacja przeskoku pina po trasie (podróż z mapy dzieje się NA mapie,
// bez pełnoekranowej cinematyki). Wartości startowe (patrz Numbers Policy #1381).
const HOP_MS = 320; // czas jednego przeskoku pina / heks
const ENCOUNTER_PAUSE_MS = 650; // pauza z ⚔ zanim gra wejdzie w walkę

const VB_W = 340;
const VB_H = 320;
// MIN 0.2 → można oddalić do widoku pełnej krainy; MAX 3.0 → bliski zoom detali.
const MIN_ZOOM = 0.2;
const MAX_ZOOM = 3.0;

interface Props {
  campaignId: number;
  characterId: number;
  /** FAZA ML: gdy hub ma mapę lokalną — pokaż przełącznik „Osada". */
  localAvailable?: boolean;
  onOpenLocal?: () => void;
  /** Akcje bieżącego heksa (kontekstowy modal): odpoczynek / obóz / wznów podróż. */
  onRest?: () => void;
  onCamp?: () => void;
  onResume?: () => void;
}

export function WorldMap({
  campaignId,
  characterId,
  localAvailable,
  onOpenLocal,
  onRest,
  onCamp,
  onResume,
}: Props) {
  const setGameTab = useAppStore((s) => s.setGameTab);
  // #1309 — heksy świeżo odsłonięte przez przedmiot-mapę: animujemy ich „wjazd".
  // Lokalny set seedowany z mapReveal.ts, kasowany po ~2,5 s (koniec animacji).
  const mapReveal = useAppStore((s) => s.mapReveal);
  const clearMapReveal = useAppStore((s) => s.clearMapReveal);
  const setTravelAnimating = useAppStore((s) => s.setTravelAnimating);
  const [revealSet, setRevealSet] = useState<Set<string>>(() => new Set());
  useEffect(() => {
    if (!mapReveal?.hexes?.length) {
      setRevealSet(new Set());
      return;
    }
    setRevealSet(new Set(mapReveal.hexes.map(([q, r]) => `${q},${r}`)));
    // #1196 — wyśrodkuj widok na pierwszym odsłoniętym heksie (skok „Użyj" mapy
    // skarbu na jego cel). Focus wchodzi wprost do transformacji zamiast pan —
    // odporne na timing: `center` przelicza się po dociągnięciu danych mapy,
    // a pan liczony względem starego center lądował poza mapą (pusty widok).
    const [fq, fr] = mapReveal.hexes[0];
    setFocusPx(hexToPixel(fq, fr));
    setZoom(1);
    setPan({ x: 0, y: 0 });
    const t = setTimeout(() => {
      setRevealSet(new Set());
      // #1196 — skonsumowane: bez tego każde kolejne otwarcie zakładki Mapa
      // re-centrowałoby na skarbie (mapReveal wisiał w store na stałe).
      clearMapReveal();
    }, 2500);
    return () => clearTimeout(t);
    // Retrigger po każdym nowym odsłonięciu (świeży ts → nowy obiekt mapReveal).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mapReveal?.ts]);
  const map = useWorldMap(campaignId, characterId);
  const clock = useCampaignClock(campaignId);
  const character = useCharacter(characterId);
  const travel = useTravel(campaignId);
  const setRegionBlock = useAppStore((s) => s.setRegionBlock);
  // Kontekstowe akcje bieżącego heksa — z bieżących suggested_actions.
  const suggested = useSuggestedActions(campaignId, characterId, true);
  const restAction = suggested.data?.suggested_actions?.find(
    (a) => (a.action || a.text) === "REST:long",
  );
  const campAction = suggested.data?.suggested_actions?.find(
    (a) => (a.action || a.text) === "BUILD_CAMP",
  );
  // Przerwana podróż = backend emituje TRAVEL_RESUME (interrupt dusk/forced_camp/encounter).
  const canResume = suggested.data?.suggested_actions?.some(
    (a) => (a.action || a.text) === "TRAVEL_RESUME",
  ) ?? false;
  // #1410 — modal ufa AUTORYTATYWNYM flagom `enabled` z suggested-actions (jedno źródło
  // prawdy). `character.safe_for_rest` (hereSafe) to OSOBNY, LAGUJĄCY endpoint — po wejściu
  // na nowy hex trzyma bezpieczeństwo POPRZEDNIEJ lokacji. Wcześniej hereSafe nadpisywał
  // akcje: na dzikim heksie chwilowo czytał true → gasił backendowy BUILD_CAMP i pokazywał
  // „Odpocznij", który przy kliknięciu leciał 409 not_safe_for_rest (#1409/#1410).
  // Teraz: enabled backendu decyduje; hereSafe TYLKO fallback dla transientu WEJŚCIA do
  // osady (#1406), gdy hex nie jest jeszcze zlinkowany i backend NIE emituje jeszcze akcji
  // REST — nigdy nie nadpisuje jawnej flagi enabled.
  const hereSafe = character.data?.safe_for_rest === true;
  const canRestHere = restAction ? restAction.enabled === true : hereSafe;
  const canCampHere = campAction?.enabled === true;

  const hexes = map.data?.hexes ?? [];
  const hexTypes = map.data?.hex_types ?? {};
  const currentHex = map.data?.current_hex ?? null;

  const period = clock.data?.period ?? "";
  const isNight = clock.data?.is_night ?? /noc/i.test(period);
  const time = clock.data?.hour_str ?? "—:—";
  const dayLabel = clock.data
    ? `Dzień ${clock.data.day} · ${period || "—"}`
    : "—";
  // #1219 — klik w zegar nagłówka Mapy otwiera popup „Łuk dnia" (parytet z paskiem gry).
  const [clockOpen, setClockOpen] = useState(false);
  const locationLabel =
    character.data?.current_location_label ?? "W drodze przez Kresy";

  // ── zoom / pan ─────────────────────────────────────────────────────────────
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
  // #1196 — punkt, na który celuje viewport zamiast pozycji gracza (skok „Użyj").
  const [focusPx, setFocusPx] = useState<{ x: number; y: number } | null>(null);
  // Śledzimy start + czy pointer się ruszył (drag vs klik). BEZ setPointerCapture —
  // capture przechwytywał `click` na desktopie → klik w heks nie działał.
  const drag = useRef<{ x: number; y: number; sx: number; sy: number } | null>(null);
  const movedRef = useRef(false);

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
    setFocusPx(null); // wróć do pozycji gracza
  }, []);

  const onPointerDown = (e: React.PointerEvent) => {
    drag.current = { x: e.clientX - pan.x, y: e.clientY - pan.y, sx: e.clientX, sy: e.clientY };
    movedRef.current = false;
    setHexTooltip(null);
  };
  const onPointerMove = (e: React.PointerEvent) => {
    if (!drag.current) return;
    if (
      Math.abs(e.clientX - drag.current.sx) > 5 ||
      Math.abs(e.clientY - drag.current.sy) > 5
    ) {
      movedRef.current = true;
    }
    setPan({ x: e.clientX - drag.current.x, y: e.clientY - drag.current.y });
  };
  const onPointerUp = () => {
    drag.current = null;
    // Reset po cyklu, aby kolejny klik nie był blokowany przez poprzedni drag.
    requestAnimationFrame(() => {
      movedRef.current = false;
    });
  };
  const onWheel = (e: React.WheelEvent) => {
    const next = zoom * (e.deltaY < 0 ? 1.12 : 0.89);
    setZoom(Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, next)));
  };

  // ── selection / travel ─────────────────────────────────────────────────────
  const qc = useQueryClient();
  const [selected, setSelected] = useState<WorldHex | null>(null);
  // #1381 — stan animacji przeskoku pina. `route` = faktycznie przebyty odcinek
  // trasy (origin → arrived_hex); `step` = indeks aktualnego heksa; `encounterHex`
  // = heks zasadzki (gdy podróż przerwał encounter).
  const [anim, setAnim] = useState<{
    route: Array<{ q: number; r: number }>;
    step: number;
    encounterHex: { q: number; r: number } | null;
    // #1417 — gdy ustawione: po dojściu na bród animacja ZAMRAŻA (pin na brodzie), czeka
    // na klik w overlay; wtedy rusza 2. etap „spływu rzeką" tą ścieżką do brzegu.
    fordSweep?: Array<{ q: number; r: number }> | null;
  } | null>(null);
  // #1417 — wynik przeprawy przez bród pokazany NA mapie (test Siły + skutek), bo
  // przeprawa dzieje się na ekranie mapy, a karta rzutu w logu Opowieści była niewidoczna.
  const [fordResult, setFordResult] = useState<TravelResult["ford_hazard"] | null>(null);

  // Klik w heks otwiera modal opcji: bieżący heks → akcje lokalne (osada/odpoczynek/
  // obóz), inny heks → podróż. „w nieznane" (outline) też dozwolone.
  // Klik (nie drag) w heks otwiera modal. Przeciąganie mapy nie ma otwierać modala.
  const selectHex = (h: WorldHex) => {
    if (movedRef.current) return;
    setSelected(h);
  };
  const selectedIsCurrent =
    !!selected && !!currentHex && selected.q === currentHex.q && selected.r === currentHex.r;

  const realLabel = (h: WorldHex | null): string | null => {
    if (!h?.label) return null;
    return /^\([-\d]+,[-\d]+\)$/.test(h.label) ? null : h.label;
  };

  const estimate = selected
    ? estimateTravel(currentHex, selected, selected.hex_type)
    : null;
  // Realny czas z backendu (suma travel_hours po trasie) — zgodny z zegarem.
  const travelEst = useTravelEstimate(
    campaignId,
    selected && !selectedIsCurrent ? { q: selected.q, r: selected.r } : undefined,
  );
  const estHours = travelEst.data?.hours ?? estimate?.hours ?? 0;
  // #1405 — czy dzienny budżet marszu skończy się PRZED celem (obóz w drodze)?
  const travelCampWarn = useMemo(() => {
    const d = travelEst.data;
    if (!d?.steps?.length || !d.march) return false;
    let cum = d.march.hours_today;
    for (const s of d.steps) {
      if (cum + s.cost > d.march.soft_cap) return true;
      cum += s.cost;
    }
    return false;
  }, [travelEst.data]);

  // #1381 — podróż z mapy: zamiast pełnoekranowej cinematyki animujemy przeskok
  // pina po trasie NA mapie. Backend zwraca `path` (pełna trasa), `arrived_hex`
  // (gdzie realnie stanął) oraz `encounter`/`encounter_hex` (zasadzka).
  const startTravel = () => {
    if (!selected || travel.isPending || anim) return;
    const destQ = selected.q;
    const destR = selected.r;
    travel.mutate(
      { characterId, q: destQ, r: destR, deferMap: true },
      {
        onSuccess: (res) => {
          // #1039 — odmowa wejścia do krainy coming/locked: modal blokady zamiast
          // cichego no-opa; nie animujemy i nie zamykamy panelu podróży.
          const blocked = regionBlockFrom(res);
          if (blocked) { setRegionBlock(blocked); return; }
          if (res.ok === false) return;
          const fullPath = Array.isArray(res.path) ? res.path : [];
          const fh = res.ford_hazard;
          // #1417 — PORWANIE z przeniesieniem: 2-etapowa animacja. Etap 1: dojdź DO brodu
          // (punkt testu) i ZAMROŹ; overlay pokazuje wynik. Klik → etap 2: spływ rzeką do
          // brzegu (fordSweep). Bez tego pin szedł całą trasą, a potem „teleportował" na brzeg.
          if (fh?.swept && fh.swept_hex && Array.isArray(fh.sweep_path) && fh.sweep_path.length >= 2) {
            setFordResult(fh);
            const sh = fh.swept_hex;
            const idx = fullPath.findIndex((h) => h.q === sh.q && h.r === sh.r);
            const route1 = idx >= 0 ? fullPath.slice(0, idx + 1) : [sh];
            setSelected(null);
            setTravelAnimating(true);
            setAnim({ route: route1, step: 0, encounterHex: null, fordSweep: fh.sweep_path });
            return;
          }
          // #1417 — przeprawa bez porwania (czysto / przemoczony): overlay auto-znika.
          if (fh) setFordResult(fh);
          const arr = res.arrived_hex ?? { q: destQ, r: destR };
          // Przytnij trasę do faktycznie przebytego odcinka (origin → arrived_hex).
          const arrIdx = fullPath.findIndex(
            (h) => h.q === arr.q && h.r === arr.r,
          );
          const route = arrIdx >= 0 ? fullPath.slice(0, arrIdx + 1) : fullPath;
          const encHex = res.encounter ? (res.encounter_hex ?? arr) : null;
          setSelected(null); // schowaj panel — animacja gra na czystej mapie
          if (route.length < 2) {
            // Trasa 0/1-heksowa (np. teleport / sąsiad) → bez animacji: odśwież
            // mapę i suggested-actions (przy zasadzce → modal zasadzki ze zdjęciem).
            qc.invalidateQueries({ queryKey: ["world-map", campaignId] });
            qc.invalidateQueries({ queryKey: ["suggested-actions", campaignId] });
            return;
          }
          setTravelAnimating(true); // #1381 — wstrzymaj modal zasadzki na czas animacji
          setAnim({ route, step: 0, encounterHex: encHex });
        },
        // onError: błąd zostaje w panelu (travel.isError) — panel wciąż otwarty.
      },
    );
  };

  // #1381 — sterownik animacji: co HOP_MS przesuwa pin o jeden heks. Po dojściu
  // do końca trasy: (a) zasadzka → pauza z ⚔, potem unieważnij suggested-actions →
  // modal zasadzki ze zdjęciem pojawia się DOPIERO teraz (nie w trakcie animacji);
  // gracz klika „Stań do walki" w modalu → onResume → /travel-resume → walka.
  // (b) cel → odśwież mapę (pin ląduje na celu, mgła wzdłuż trasy odsłonięta).
  // world-map/suggested-actions celowo NIE są unieważniane w hooku useTravel —
  // inaczej pin przeskoczyłby / modal wyskoczyłby przed końcem animacji.
  useEffect(() => {
    if (!anim) return;
    if (anim.step >= anim.route.length - 1) {
      // #1417 — dotarto DO brodu, a czeka spływ: ZAMROŹ (pin na brodzie), overlay-gate
      // czeka na klik gracza. Nie invaliduj mapy, nie czyść anim (etap 2 rusza z klika).
      if (anim.fordSweep) return;
      const t = setTimeout(
        () => {
          setAnim(null);
          setTravelAnimating(false); // odblokuj modal zasadzki (Game.tsx)
          qc.invalidateQueries({ queryKey: ["world-map", campaignId] });
          if (anim.encounterHex) {
            qc.invalidateQueries({ queryKey: ["suggested-actions", campaignId] });
          }
        },
        anim.encounterHex ? ENCOUNTER_PAUSE_MS : 220,
      );
      return () => clearTimeout(t);
    }
    const t = setTimeout(
      () => setAnim((a) => (a ? { ...a, step: a.step + 1 } : a)),
      HOP_MS,
    );
    return () => clearTimeout(t);
  }, [anim, campaignId, qc, setTravelAnimating]);

  // #1381 — bezpiecznik: jeśli gracz opuści mapę w trakcie animacji, odblokuj modal.
  useEffect(() => () => setTravelAnimating(false), [setTravelAnimating]);

  // #1417 — karta wyniku przeprawy: przy PORWANIU (jest sweep_path) to GATE — czeka na
  // klik (odpala spływ), nie auto-znika. Przy czystej/mokrej przeprawie znika po ~6 s.
  useEffect(() => {
    if (!fordResult) return;
    if (fordResult.swept && Array.isArray(fordResult.sweep_path) && fordResult.sweep_path.length >= 2) return;
    const t = setTimeout(() => setFordResult(null), 6000);
    return () => clearTimeout(t);
  }, [fordResult]);

  // Podczas animacji kamera podąża za wędrującym pinem (inaczej trasa mogłaby
  // wyjść poza kadr). Poza animacją: focus „Użyj" mapy skarbu, else pozycja gracza.
  const viewCenter = anim
    ? hexToPixel(anim.route[anim.step].q, anim.route[anim.step].r)
    : (focusPx ?? center);
  const groupTransform = `translate(${VB_W / 2 + pan.x} ${VB_H / 2 + pan.y}) scale(${zoom}) translate(${-viewCenter.x} ${-viewCenter.y})`;

  return (
    <div className="flex h-full min-h-0 min-w-0 flex-1 flex-col lg:flex-row">
      {/* #1417 — wynik przeprawy przez bród (test Siły + skutek) NA mapie. */}
      {fordResult && (() => {
        const ev = fordResult.events?.[fordResult.events.length - 1];
        const swept = fordResult.swept;
        const wet = fordResult.wet;
        const danger = swept || wet;
        const gated = swept && Array.isArray(fordResult.sweep_path) && fordResult.sweep_path.length >= 2;
        const onOverlayClick = () => {
          setFordResult(null);
          // #1417 — porwanie: klik uruchamia ETAP 2 — spływ rzeką ścieżką sweep_path do brzegu.
          const drift = anim?.fordSweep;
          if (drift && drift.length >= 2) {
            setAnim({ route: drift, step: 0, encounterHex: null });
          }
        };
        return (
          <div
            className="fixed inset-x-0 top-4 z-[60] mx-auto flex max-w-[420px] cursor-pointer justify-center px-4"
            onClick={onOverlayClick}
          >
            <div className={"w-full overflow-hidden rounded-xl border shadow-2xl " + (danger ? "border-line-danger bg-surface" : "border-line-ember bg-surface")}>
              <div className={"flex items-center gap-2.5 border-b border-line px-4 py-2.5 " + (danger ? "bg-danger/[0.10]" : "bg-ember/[0.08]")}>
                <span className="text-lg" aria-hidden>🌊</span>
                <div className="font-serif text-body font-semibold text-text">
                  Przeprawa przez bród
                </div>
              </div>
              {ev && (
                <div className="flex items-stretch px-2 pt-3">
                  <TravelStat k="k20" v={String(ev.d20)} />
                  <TravelStat k="Siła" v={(ev.mod >= 0 ? "+" : "") + ev.mod} />
                  <TravelStat k="Suma" v={String(ev.total)} />
                  <TravelStat k="Próg" v={String(ev.dc)} />
                  <TravelStat k="Wynik" v={ev.success ? "sukces" : ev.nat1 ? "pech" : "porażka"} warn={!ev.success} last />
                </div>
              )}
              <div className="px-4 py-3 text-center font-ui text-label text-text-2">
                {swept
                  ? `Nurt cię porwał — ${fordResult.swept_distance ?? 0} pól w dół rzeki, −${fordResult.damage} HP, przemoczony.`
                  : wet
                    ? "Przemoczony (−1 do testów fizycznych, aż wyschniesz przy ogniu)."
                    : "Przeprawa czysta — suchą stopą na drugi brzeg."}
              </div>
              {gated && (
                <div className="border-t border-line bg-danger/[0.06] px-4 py-2 text-center font-ui text-micro font-semibold text-danger-glow">
                  Kliknij, by popłynąć z nurtem →
                </div>
              )}
            </div>
          </div>
        );
      })()}
      {/* Nagłówek: zegar+pora+lokacja + zamknij (mobile pełna szer.) */}
      <div className="flex min-h-0 min-w-0 flex-1 flex-col">
        <header
          className="flex shrink-0 items-center gap-3 border-b border-line bg-surface px-4 py-2.5"
          style={{ paddingTop: "max(10px, var(--sa-top))" }}
        >
          <button
            type="button"
            onClick={() => setClockOpen(true)}
            aria-label="Zegar świata"
            className="flex shrink-0 flex-col items-start rounded-md border-r border-line pr-3 leading-tight transition-colors hover:bg-white/[.03]"
          >
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
          </button>
          <DayArcModal open={clockOpen} onOpenChange={setClockOpen} clock={clock.data} />
          <div className="min-w-0 flex-1">
            <div className="font-ui text-[9px] font-semibold uppercase tracking-[0.16em] text-text-3">
              Jesteś w
            </div>
            <div className="truncate font-serif text-body font-semibold text-text">
              {locationLabel}
            </div>
          </div>
          {/* #1193 — znacznik aktywnego wydarzenia regionalnego (żywy świat) */}
          {map.data?.active_event && (
            <div
              title={map.data.active_event.label ?? "Wydarzenie w regionie"}
              className="flex h-9 shrink-0 items-center gap-1.5 rounded-md border border-line-ember bg-ember/[0.08] px-2.5 font-ui text-label text-ember-glow"
            >
              <span className="text-body leading-none">
                {map.data.active_event.badge ?? "✦"}
              </span>
              <span className="hidden truncate sm:inline">
                {map.data.active_event.label}
              </span>
            </div>
          )}
          {localAvailable && onOpenLocal && (
            <button
              onClick={onOpenLocal}
              className="flex h-9 shrink-0 items-center gap-1.5 rounded-md border border-line-ember bg-ember/[0.08] px-3 font-ui text-label text-ember-glow transition-colors hover:bg-ember/[0.16]"
            >
              <MapPinSimpleArea size={15} />
              Osada
            </button>
          )}
          <button
            aria-label="Zamknij mapę"
            onClick={() => setGameTab("story")}
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md border border-line bg-bg text-text-2 transition-colors hover:border-line-ember hover:text-ember-glow"
          >
            <X size={16} />
          </button>
        </header>

        {/* #1405 — pasek wytrzymałości marszu (dzienny budżet) + zmęczenie + powód
            zatrzymania. Trwały wskaźnik nad mapą: tłumaczy „nagły stop" i „1-hex pełzanie". */}
        <MarchStaminaBar
          march={clock.data?.march ?? null}
          fatigue={character.data?.fatigue ?? null}
          notice={suggested.data?.travel_notice ?? null}
        />

        {/* Mapa — wypełnia całą dostępną wysokość (mobile: pełny ekran, desktop: lewy panel) */}
        <div className="flex min-h-0 flex-1 flex-col p-3">
          <div
            ref={containerRef}
            className="relative flex min-h-0 flex-1 overflow-hidden rounded-lg border border-line"
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
              <div className="flex h-full w-full items-center justify-center font-ui text-body text-text-3">
                Wczytywanie mapy…
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
                  <filter id="hexglow" x="-50%" y="-50%" width="200%" height="200%">
                    <feGaussianBlur stdDeviation="4" result="b" />
                    <feMerge>
                      <feMergeNode in="b" />
                      <feMergeNode in="SourceGraphic" />
                    </feMerge>
                  </filter>
                </defs>
                <g
                  transform={groupTransform}
                  // #1381 — podczas animacji kamera podąża za pinem: płynne
                  // przesunięcie transformacji o jeden heks co HOP_MS.
                  style={anim ? { transition: `transform ${HOP_MS}ms linear` } : undefined}
                >
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
                      justRevealed={revealSet.has(`${h.q},${h.r}`)}
                      terrainLabel={h.hex_type ? hexTypes[h.hex_type]?.label : undefined}
                      onHoverIn={onHexHoverIn}
                      onHoverOut={onHexHoverOut}
                      onClick={() => selectHex(h)}
                    />
                  ))}
                  {/* #1405 — podgląd trasy do wybranego celu: linia + marker „obóz
                      dziś" na ostatnim heksie osiągalnym przed progiem zmierzchu
                      (dzienny budżet). Pokazuje z góry, gdzie podróż się zatrzyma. */}
                  {selected && !selectedIsCurrent && !anim &&
                    travelEst.data?.path && travelEst.data.path.length > 1 && (() => {
                    const path = travelEst.data!.path!;
                    const steps = travelEst.data!.steps ?? [];
                    const m = travelEst.data!.march;
                    const pts = path.map((h) => hexToPixel(h.q, h.r));
                    // Ostatni heks osiągalny dziś (cum kosztów + marsz dzisiejszy ≤ próg zmierzchu).
                    let reached = path.length - 1;
                    if (m && steps.length) {
                      let cum = m.hours_today;
                      reached = 0;
                      for (let i = 0; i < steps.length; i++) {
                        if (cum + steps[i].cost > m.soft_cap) break;
                        cum += steps[i].cost;
                        reached = i + 1;
                      }
                    }
                    const campNeeded = reached < path.length - 1 && reached >= 0;
                    const reachPts = pts.slice(0, reached + 1);
                    const campPx = campNeeded ? pts[reached] : null;
                    return (
                      <g style={{ pointerEvents: "none" }}>
                        {/* cała trasa — przygaszona przerywana */}
                        <polyline
                          points={pts.map((p) => `${p.x},${p.y}`).join(" ")}
                          fill="none"
                          stroke="rgba(169,198,221,.28)"
                          strokeWidth={1.4}
                          strokeDasharray="2 4"
                        />
                        {/* odcinek osiągalny dziś — bursztyn */}
                        {reachPts.length > 1 && (
                          <polyline
                            points={reachPts.map((p) => `${p.x},${p.y}`).join(" ")}
                            fill="none"
                            stroke="var(--ember)"
                            strokeWidth={2}
                            strokeLinecap="round"
                          />
                        )}
                        {campPx && (
                          <>
                            <circle cx={campPx.x} cy={campPx.y} r={5} fill="var(--gold)" stroke="#170f09" strokeWidth={1.2} />
                            <foreignObject x={campPx.x - 11} y={campPx.y - 30} width={22} height={22}>
                              <div className="flex h-full w-full items-center justify-center">
                                <Tent size={17} color="var(--gold)" weight="fill" />
                              </div>
                            </foreignObject>
                          </>
                        )}
                      </g>
                    );
                  })()}
                  {/* #1381 — nakładka animacji podróży: linia trasy + wędrujący
                      pin + ⚔ na heksie zasadzki. */}
                  {anim && (() => {
                    const cur = anim.route[anim.step];
                    const p = hexToPixel(cur.q, cur.r);
                    const atEnd = anim.step >= anim.route.length - 1;
                    const encPx =
                      anim.encounterHex && atEnd
                        ? hexToPixel(anim.encounterHex.q, anim.encounterHex.r)
                        : null;
                    return (
                      <g style={{ pointerEvents: "none" }}>
                        <polyline
                          points={anim.route
                            .map((h) => {
                              const pp = hexToPixel(h.q, h.r);
                              return `${pp.x},${pp.y}`;
                            })
                            .join(" ")}
                          fill="none"
                          stroke="rgba(169,198,221,.45)"
                          strokeWidth={1.6}
                          strokeDasharray="3 3"
                        />
                        <circle
                          cx={p.x}
                          cy={p.y}
                          r={6.5}
                          fill="var(--ember)"
                          stroke="#fff"
                          strokeWidth={1.4}
                          filter="url(#hexglow)"
                        />
                        {encPx && (
                          <foreignObject
                            x={encPx.x - 12}
                            y={encPx.y - 32}
                            width={24}
                            height={24}
                          >
                            <div className="flex h-full w-full items-center justify-center animate-pulse">
                              <Sword size={20} color="#e8604f" weight="fill" />
                            </div>
                          </foreignObject>
                        )}
                      </g>
                    );
                  })()}
                </g>
              </svg>
            )}
            {/* Tooltip hexów — poza SVG, zero kolizji z sąsiednimi hexami */}
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

          {/* legenda — pod mapą, nie kradnie wysokości kanwy */}
          <div className="flex shrink-0 flex-wrap gap-x-4 gap-y-2 px-1 pt-3 font-ui text-micro text-text-2">
            <LegendDot className="border-ember bg-[#3a2413]" label="Twoja pozycja" />
            <LegendDot className="border-[#7fa860] bg-[#1e2716]" label="Odkryte" />
            <LegendDot className="border-mana bg-[#162530]" label="Znane z opowieści" />
            <LegendDot className="border-dashed border-line bg-[#171009]" label="Nieodkryte" />
          </div>
        </div>
      </div>

      {/* Modal opcji heksa — bieżący heks: akcje lokalne; inny heks: podróż. */}
      {selected && (
        <div className="fixed inset-0 z-[56] flex items-center justify-center p-6" data-testid="hex-modal">
          <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={() => setSelected(null)} />
          <div className="relative z-[2] w-full max-w-[400px] overflow-hidden rounded-xl border border-line-ember bg-surface shadow-2xl">
            <div className="flex items-center gap-2.5 border-b border-line px-4 py-3">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md border border-line-ember bg-[rgba(255,122,61,.12)] text-ember-glow">
                <MapPinSimpleArea size={18} />
              </div>
              <div className="min-w-0 flex-1">
                <div className="truncate font-serif text-title font-semibold text-text">
                  {realLabel(selected) ||
                    (selected.hex_type ? hexTypes[selected.hex_type]?.label : null) ||
                    "Nieznany teren"}
                </div>
                <div className="font-ui text-micro text-text-2">
                  {selectedIsCurrent
                    ? "Jesteś tutaj"
                    : (selected.hex_type ? hexTypes[selected.hex_type]?.label : "Nieznany teren") ?? "Nieznany teren"}
                  {!selectedIsCurrent && selected.status === "known" && (
                    <span className="text-ember-glow"> · cel z opowieści ⚑</span>
                  )}
                </div>
              </div>
              <button aria-label="Zamknij" onClick={() => setSelected(null)} className="text-text-3 hover:text-text">
                <X size={18} />
              </button>
            </div>

            {selectedIsCurrent ? (
              // Akcje bieżącego heksa
              <div className="flex flex-col gap-2 p-4">
                {canResume && onResume && (
                  <ModalAction
                    icon={<Path size={18} />}
                    label="Kontynuuj podróż"
                    sub="Wznów przerwaną wyprawę do celu"
                    onClick={() => { setSelected(null); onResume(); }}
                  />
                )}
                {localAvailable && onOpenLocal && (
                  <ModalAction
                    icon={<MapPinSimpleArea size={18} />}
                    label="Wejdź do osady"
                    sub="Mapa lokalna — zakątki i sub-lokacje"
                    onClick={() => { setSelected(null); onOpenLocal(); }}
                  />
                )}
                {canRestHere && onRest && (
                  <ModalAction
                    icon={<MoonStars size={18} />}
                    label="Odpocznij"
                    sub={hereSafe
                      ? "Bezpieczne miejsce — pełny odpoczynek (HP/mana), +8 h"
                      : "Długi odpoczynek — pełne HP/mana, +8 h"}
                    onClick={() => { setSelected(null); onRest(); }}
                  />
                )}
                {canCampHere && onCamp && (
                  <ModalAction
                    icon={<Path size={18} />}
                    label="Rozbij obóz"
                    sub="Tymczasowy obóz pozwoli odpocząć (więcej spotkań)"
                    onClick={() => { setSelected(null); onCamp(); }}
                  />
                )}
                {/* #1406/#1410 — komunikat czemu nie ma „Rozbij obóz": tu bezpiecznie,
                    można normalnie odpocząć, obóz (opcja dziczy) zbędny. Pokazuj tylko gdy
                    faktycznie: odpoczynek dostępny, obozu brak. */}
                {hereSafe && canRestHere && !canCampHere && (
                  <p className="rounded-md border border-line-soft bg-white/[.02] px-3 py-2 text-center font-ui text-micro text-text-3">
                    Ten teren jest bezpieczny do odpoczynku — obóz zbędny.
                  </p>
                )}
                {!canResume && !localAvailable && !canRestHere && !canCampHere && (
                  <p className="py-2 text-center font-ui text-body text-text-3">
                    Brak dostępnych akcji w tym miejscu.
                  </p>
                )}
              </div>
            ) : (
              // Podróż do wybranego heksa
              <>
                {estimate && (
                  <div className="flex px-1.5 py-2.5 font-mono">
                    <TravelStat k="Dystans" v={`${estimate.distance} ${estimate.distance === 1 ? "heks" : "heks."}`} />
                    <TravelStat k="Czas" v={travelEst.isLoading ? "…" : `~${estHours} h`} />
                    <TravelStat k="Teren" v={estimate.difficulty} />
                    <TravelStat k="Spotkanie" v={estimate.encounter} warn={estimate.encounterWarn} last />
                  </div>
                )}
                {isNight && (
                  <div className="mx-3.5 mb-3 flex items-center gap-2 rounded-md border border-line-danger bg-[rgba(232,96,79,.06)] px-3 py-2 font-ui text-micro text-text">
                    <MoonStars className="shrink-0 text-danger" size={15} />
                    Podróż nocą — zmęczenie rośnie szybciej, gorsza widoczność.
                  </div>
                )}
                {/* #1405 — budżet marszu skończy się przed celem → obóz w drodze */}
                {travelCampWarn && (
                  <div className="mx-3.5 mb-3 flex items-center gap-2 rounded-md border border-line-ember bg-ember/[0.06] px-3 py-2 font-ui text-micro text-text">
                    <Tent className="shrink-0 text-gold" size={15} weight="fill" />
                    Nie dojdziesz dziś do celu — po drodze rozbijesz obóz (❝obóz❞ na mapie).
                  </div>
                )}
                <div className="px-4 pb-4 pt-1">
                  <button
                    onClick={startTravel}
                    disabled={travel.isPending}
                    className="flex w-full items-center justify-center gap-2 rounded-md px-3 py-3 font-ui text-body font-semibold text-white disabled:opacity-60"
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
                  {travel.isError && (
                    <div className="mt-2 rounded-md border border-line-danger bg-[rgba(232,96,79,.06)] px-3 py-2 font-ui text-micro text-danger-glow">
                      {(travel.error as Error)?.message || "Błąd podróży"}
                    </div>
                  )}
                </div>
              </>
            )}
          </div>
        </div>
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
  justRevealed,
  terrainLabel,
  onHoverIn,
  onHoverOut,
  onClick,
}: {
  hex: WorldHex;
  color?: string;
  isCurrent: boolean;
  isSelected: boolean;
  /** #1309 — heks świeżo odsłonięty przedmiotem-mapą → animacja „wjazdu" (poświata). */
  justRevealed?: boolean;
  terrainLabel?: string;
  onHoverIn: (label: string, sub: string, e: React.MouseEvent) => void;
  onHoverOut: () => void;
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
    // outline / unexplored — mgła wojny. Kontur MUSI być widoczny: to jest
    // klikalna krawędź eksploracji (klik → podróż w nieznane). Przy .08/0.6 siatka
    // była praktycznie niewidoczna na ciemnym tle → gracz nie wiedział, że można
    // tam kliknąć. Wypełnienie zostaje ciemne (teren ukryty — tajemnica fog).
    fill = "#171009";
    stroke = "rgba(242,232,216,.28)";
    dash = "4 4";
    opacity = 0.9;
  }

  // Nazwane heksy (osady/landmarki) wyróżniamy: obwódka pod ikoną + jaśniejszy
  // (złoty) kolor, żeby odcinały się od generycznego terenu.
  const isNamed = !!hex.label && !/^\([-\d]+,[-\d]+\)$/.test(hex.label);
  // #1311 — lokacja (POI) i cel questa jako jawne flagi z backendu (fallback: label).
  // Bez tego heks z lokacją wyglądał jak zwykły teren (world_hexes.label = NULL).
  const isPoi = (hex.is_poi ?? isNamed) && (discovered || known);
  const isQuest = !!hex.is_quest;
  const isTreasure = !!hex.is_treasure; // #1196 — nieodkryty skarb na tym heksie

  const Icon = terrainIcon(hex.hex_type);
  const iconColor = isCurrent
    ? "var(--ember-glow)"
    : isQuest
      ? "var(--ember-glow)"
      : isPoi || isNamed
        ? "var(--gold)"
        : known
          ? "#a9c6dd"
          : "var(--text-2)";

  return (
    <g
      className={justRevealed ? "hex-just-revealed" : undefined}
      onClick={(e) => {
        e.stopPropagation();
        onClick();
      }}
      onMouseEnter={(e) => {
        const label = isNamed ? hex.label! : (terrainLabel || "Nieznany teren");
        const sub = isCurrent
          ? `Twoja pozycja${terrainLabel ? ` · ${terrainLabel}` : ""}`
          : known
            ? `${terrainLabel || "Teren"} · znane z opowieści`
            : discovered
              ? terrainLabel || "Odkryte"
              : "Nieodkryte terytorium";
        onHoverIn(label, sub, e);
      }}
      onMouseLeave={onHoverOut}
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
      {/* #1311 — obwódka pod ikoną POI: cel questa bursztynowy z poświatą, zwykła
          lokacja złota. Odcina heks z lokacją od generycznego terenu. */}
      {isPoi && hasTerrain && !isCurrent && (
        <circle
          cx={x}
          cy={y}
          r={12.5}
          fill="rgba(20,16,12,.6)"
          stroke={isQuest ? "var(--ember-glow)" : "var(--gold)"}
          strokeWidth={isQuest ? 2 : 1.4}
          filter={isQuest ? "url(#hexglow)" : undefined}
          style={{ pointerEvents: "none" }}
        />
      )}
      {hasTerrain && (
        <foreignObject x={x - 11} y={y - 11} width={22} height={22} style={{ pointerEvents: "none" }}>
          <div className="flex h-full w-full items-center justify-center">
            <Icon size={17} color={iconColor} weight={isCurrent || isPoi ? "fill" : "regular"} />
          </div>
        </foreignObject>
      )}
      {/* #1311 — badge celu questa: gwiazda nad heksem (bursztyn) */}
      {isQuest && !isCurrent && (
        <foreignObject x={x - 8} y={y - 27} width={16} height={16} style={{ pointerEvents: "none" }}>
          <div className="flex h-full w-full items-center justify-center">
            <Star size={14} color="var(--ember-glow)" weight="fill" />
          </div>
        </foreignObject>
      )}
      {/* #1196 — znacznik nieodkrytego skarbu: wyraźny ✕ nad heksem */}
      {isTreasure && (
        <foreignObject x={x - 11} y={y - 30} width={22} height={22} style={{ pointerEvents: "none" }}>
          <div className="flex h-full w-full items-center justify-center animate-pulse">
            <XCircle size={19} color="#f2c14e" weight="fill" />
          </div>
        </foreignObject>
      )}
      {/* flaga celu na NAZWANYCH heksach znanych z opowieści (fog 'known') */}
      {namedTarget && !isQuest && (
        <foreignObject x={x - 8} y={y - 26} width={16} height={16} style={{ pointerEvents: "none" }}>
          <div className="flex h-full w-full items-center justify-center">
            <FlagBanner size={13} color="var(--ember-glow)" weight="fill" />
          </div>
        </foreignObject>
      )}
      {/* #1311 — nazwa lokacji zawsze widoczna pod heksem POI (nie tylko w hoverze),
          by odkryte lokacje były czytelne na pierwszy rzut oka. */}
      {isPoi && !!hex.label && (discovered || isCurrent) && (
        <text
          x={x}
          y={y + 22}
          textAnchor="middle"
          fontSize={7.5}
          fill={isQuest ? "var(--ember-glow)" : "var(--gold)"}
          stroke="rgba(10,7,4,.85)"
          strokeWidth={0.5}
          paintOrder="stroke"
          style={{ pointerEvents: "none", fontWeight: 600 }}
        >
          {hex.label.length > 22 ? hex.label.slice(0, 21) + "…" : hex.label}
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

function ModalAction({
  icon,
  label,
  sub,
  onClick,
}: {
  icon: React.ReactNode;
  label: string;
  sub: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex w-full items-center gap-3 rounded-md border border-line-ember bg-ember/[0.06] px-3.5 py-3 text-left transition-colors hover:border-ember hover:bg-ember/[0.12]"
    >
      <span className="flex h-[38px] w-[38px] shrink-0 items-center justify-center rounded-md border border-line-ember bg-bg text-ember-glow">
        {icon}
      </span>
      <span className="min-w-0 flex-1">
        <span className="block font-ui text-body font-semibold text-text">{label}</span>
        <span className="block font-ui text-micro text-text-3">{sub}</span>
      </span>
    </button>
  );
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

// #1405 — pasek wytrzymałości marszu (A) + zmęczenie (C) + powód zatrzymania (B).
function fmtH(n: number): string {
  const r = Math.round(n * 10) / 10;
  return Number.isInteger(r) ? String(r) : r.toFixed(1);
}

function MarchStaminaBar({
  march,
  fatigue,
  notice,
}: {
  march: MarchBudget | null;
  fatigue: { level: number; max: number } | null;
  notice: TravelNotice | null;
}) {
  if (!march) return null; // stary backend bez budżetu → nic
  const hard = march.hard_cap || 12;
  const soft = march.soft_cap || 8;
  const today = Math.max(0, march.hours_today || 0);
  const used = Math.min(today, hard);
  const pct = Math.max(0, Math.min(100, (used / hard) * 100));
  const softPct = Math.max(0, Math.min(100, (soft / hard) * 100));
  const overHard = today >= hard - 0.05;
  const overSoft = today >= soft - 0.05;
  const toDusk = Math.max(0, soft - today);
  const fill = overHard ? "var(--danger)" : overSoft ? "var(--gold)" : "var(--success)";
  const status = overHard
    ? "Padasz z sił — obóz przymusowy"
    : overSoft
      ? "Zmierzch — nocny marsz ryzykowny"
      : `Do zmierzchu ~${fmtH(toDusk)} h marszu`;
  const fatLevel = fatigue?.level ?? 0;
  const fatMax = fatigue?.max ?? 3;
  const noticeDanger = notice?.severity === "danger";

  return (
    <div className="shrink-0 border-b border-line bg-surface px-4 py-2">
      <div className="flex items-center gap-3">
        <PersonSimpleWalk
          weight="fill"
          size={16}
          className={cn("shrink-0", overHard ? "text-danger" : overSoft ? "text-gold" : "text-success")}
        />
        <div className="min-w-0 flex-1">
          <div className="mb-1 flex items-baseline justify-between gap-2">
            <span className="font-ui text-[10px] font-semibold uppercase tracking-[0.14em] text-text-3">
              Wytrzymałość marszu
            </span>
            <span className="font-mono text-micro text-text-2">
              {fmtH(used)}
              <span className="text-text-3">/{fmtH(hard)} h</span>
            </span>
          </div>
          <div className="relative h-2 overflow-hidden rounded-full bg-inset shadow-[inset_0_0_0_1px_var(--line-soft)]">
            <div
              className="absolute inset-y-0 left-0 rounded-full transition-[width] duration-500"
              style={{ width: `${pct}%`, background: fill }}
            />
            {/* znacznik progu zmierzchu (soft cap) */}
            <div className="absolute inset-y-0 w-px bg-text/50" style={{ left: `${softPct}%` }} />
          </div>
        </div>
        {/* zmęczenie (C) — piktogramy poziomu */}
        {fatLevel > 0 && (
          <div
            className="flex shrink-0 items-center gap-1"
            title={`Zmęczenie ${fatLevel}/${fatMax} — kary do testów i inicjatywy, odpocznij`}
          >
            <Warning weight="fill" size={13} className="text-danger" />
            <span className="flex gap-0.5">
              {Array.from({ length: fatMax }).map((_, i) => (
                <i
                  key={i}
                  className={cn("h-1.5 w-1.5 rounded-full", i < fatLevel ? "bg-danger" : "bg-line")}
                />
              ))}
            </span>
          </div>
        )}
      </div>

      <div className="mt-1 flex items-center justify-between gap-2">
        <span
          className={cn(
            "font-ui text-[10.5px]",
            overHard ? "text-danger-glow" : overSoft ? "text-gold" : "text-text-3",
          )}
        >
          {status}
        </span>
        {march.night_march && (
          <span className="flex items-center gap-1 font-ui text-[10px] text-mana">
            <MoonStars weight="fill" size={11} /> marsz nocny
          </span>
        )}
      </div>

      {/* B — powód zatrzymania (trwałe echo modalu, widoczne na mapie) */}
      {notice && (
        <div
          className={cn(
            "mt-1.5 flex items-start gap-1.5 rounded border px-2 py-1",
            noticeDanger ? "border-line-danger bg-danger/[0.07]" : "border-line-ember bg-ember/[0.06]",
          )}
        >
          <Warning
            weight="fill"
            size={12}
            className={cn("mt-px shrink-0", noticeDanger ? "text-danger" : "text-ember-glow")}
          />
          <span
            className={cn(
              "font-ui text-[10.5px] font-semibold",
              noticeDanger ? "text-danger-glow" : "text-ember-glow",
            )}
          >
            {notice.title}
          </span>
        </div>
      )}
    </div>
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
