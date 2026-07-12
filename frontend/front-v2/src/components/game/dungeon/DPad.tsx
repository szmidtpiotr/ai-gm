// FE16 loch (#1265) — przeciągany D-pad (#741) + akcje kafla. Port 1:1 z app.js:
// pozycja zapamiętana w localStorage 'dungeonNavPos', próg dragu 6px (tap vs drag),
// środek ⊕ otwiera mapę. Kierunki tylko dla otwartych drzwi. ŻAR: stalowy klaster.
import { useEffect, useRef } from "react";
import {
  CaretUp,
  CaretDown,
  CaretLeft,
  CaretRight,
  MapTrifold,
  TreasureChest,
  Campfire,
} from "@phosphor-icons/react";
import type { Dir, DungeonNode } from "@/lib/dungeon";
import { hasChest, hasRiddle, canRest } from "@/lib/dungeon";

const DPAD_POS_KEY = "dungeonNavPos"; // parytet z app.js
const DRAG_THRESHOLD = 6; // px

interface Pos {
  left: number;
  top: number;
}

function clampPos(left: number, top: number, w: number, h: number): Pos {
  const m = 4;
  const maxL = Math.max(m, window.innerWidth - w - m);
  const maxT = Math.max(m, window.innerHeight - h - m);
  return {
    left: Math.min(Math.max(m, left), maxL),
    top: Math.min(Math.max(m, top), maxT),
  };
}

export function DPad({
  node,
  onMove,
  onOpenMap,
  onChest,
  onRest,
  disabled,
}: {
  node: DungeonNode | undefined;
  onMove: (dir: Dir) => void;
  onOpenMap: () => void;
  onChest: () => void;
  onRest: () => void;
  disabled: boolean;
}) {
  const navRef = useRef<HTMLDivElement | null>(null);
  const suppressClickRef = useRef(false);

  // #741: przeciąganie klastra + odtworzenie zapisanej pozycji.
  useEffect(() => {
    const nav = navRef.current;
    if (!nav) return;
    // Odtwórz zapisaną pozycję.
    try {
      const saved = JSON.parse(localStorage.getItem(DPAD_POS_KEY) || "null");
      if (saved && typeof saved.left === "number" && typeof saved.top === "number") {
        const r = nav.getBoundingClientRect();
        const { left, top } = clampPos(saved.left, saved.top, r.width || 120, r.height || 160);
        nav.style.left = `${left}px`;
        nav.style.top = `${top}px`;
        nav.style.right = "auto";
        nav.style.bottom = "auto";
      }
    } catch {
      /* brak zapisu */
    }

    const handle = nav.querySelector<HTMLElement>("[data-dpad-handle]");
    if (!handle) return;

    let startX = 0,
      startY = 0,
      baseLeft = 0,
      baseTop = 0,
      dragging = false;

    const onDown = (e: PointerEvent) => {
      if (e.button != null && e.button !== 0) return;
      const r = nav.getBoundingClientRect();
      baseLeft = r.left;
      baseTop = r.top;
      startX = e.clientX;
      startY = e.clientY;
      dragging = false;

      const onMovePtr = (ev: PointerEvent) => {
        const dx = ev.clientX - startX;
        const dy = ev.clientY - startY;
        if (!dragging && Math.hypot(dx, dy) < DRAG_THRESHOLD) return;
        if (!dragging) {
          dragging = true;
          nav.classList.add("cursor-grabbing");
          try {
            handle.setPointerCapture(ev.pointerId);
          } catch {
            /* noop */
          }
        }
        const r2 = nav.getBoundingClientRect();
        const { left, top } = clampPos(baseLeft + dx, baseTop + dy, r2.width, r2.height);
        nav.style.left = `${left}px`;
        nav.style.top = `${top}px`;
        nav.style.right = "auto";
        nav.style.bottom = "auto";
      };
      const onUp = () => {
        handle.removeEventListener("pointermove", onMovePtr);
        handle.removeEventListener("pointerup", onUp);
        handle.removeEventListener("pointercancel", onUp);
        try {
          handle.releasePointerCapture(e.pointerId);
        } catch {
          /* noop */
        }
        nav.classList.remove("cursor-grabbing");
        if (dragging) {
          const r2 = nav.getBoundingClientRect();
          try {
            localStorage.setItem(
              DPAD_POS_KEY,
              JSON.stringify({ left: r2.left, top: r2.top }),
            );
          } catch {
            /* noop */
          }
          suppressClickRef.current = true;
          setTimeout(() => {
            suppressClickRef.current = false;
          }, 0);
        }
      };
      handle.addEventListener("pointermove", onMovePtr);
      handle.addEventListener("pointerup", onUp);
      handle.addEventListener("pointercancel", onUp);
    };

    handle.addEventListener("pointerdown", onDown);
    return () => handle.removeEventListener("pointerdown", onDown);
  }, []);

  const doorsOpen = node?.doors_open || {};
  const chest = hasChest(node);
  const riddle = hasRiddle(node);
  const rest = canRest(node);

  function guard(fn: () => void) {
    if (suppressClickRef.current) {
      suppressClickRef.current = false;
      return;
    }
    fn();
  }

  const DIR_ICON: Record<Dir, React.ReactNode> = {
    N: <CaretUp weight="bold" size={18} />,
    S: <CaretDown weight="bold" size={18} />,
    W: <CaretLeft weight="bold" size={18} />,
    E: <CaretRight weight="bold" size={18} />,
  };

  function dirBtn(dir: Dir) {
    const open = !!doorsOpen[dir];
    if (!open) return <span className="h-10 w-10" />;
    const hint = node?.door_hints?.[dir];
    return (
      <button
        type="button"
        title={hint ? `${dir}: ${hint}` : dir}
        disabled={disabled}
        onClick={() => guard(() => onMove(dir))}
        className="flex h-10 w-10 items-center justify-center rounded-lg border border-line-ember/60 bg-surface text-ember-glow transition-colors hover:border-line-ember hover:bg-ember/[0.1] disabled:opacity-40"
      >
        {DIR_ICON[dir]}
      </button>
    );
  }

  return (
    <div
      ref={navRef}
      className="fixed bottom-24 right-4 z-40 flex touch-none select-none flex-col items-center gap-2"
      data-testid="dungeon-nav"
    >
      {/* akcje kafla (skrzynia / odpoczynek) nad krzyżakiem */}
      {(chest || rest) && (
        <div className="flex flex-col items-stretch gap-1.5">
          {chest && (
            <button
              type="button"
              disabled={disabled}
              onClick={() => guard(onChest)}
              className="flex items-center gap-1.5 rounded-lg border border-line-mech bg-surface px-2.5 py-1.5 font-ui text-micro font-semibold text-gold transition-colors hover:border-gold disabled:opacity-40"
            >
              <TreasureChest weight="fill" size={15} /> Skrzynia
            </button>
          )}
          {rest && (
            <button
              type="button"
              disabled={disabled}
              onClick={() => guard(onRest)}
              className="flex items-center gap-1.5 rounded-lg border border-line-ember/60 bg-surface px-2.5 py-1.5 font-ui text-micro font-semibold text-ember-glow transition-colors hover:border-line-ember disabled:opacity-40"
            >
              <Campfire weight="fill" size={15} /> Odpocznij
            </button>
          )}
        </div>
      )}
      {riddle && (
        <div className="rounded-md border border-line-mech bg-surface px-2 py-1 font-ui text-micro text-gold">
          Zagadka — odpowiedz w panelu
        </div>
      )}

      {/* krzyżak kierunków — [data-dpad-handle] = uchwyt przeciągania */}
      <div
        data-dpad-handle
        className="grid cursor-grab grid-cols-3 grid-rows-3 gap-1 rounded-2xl border border-line bg-bg/80 p-1.5 backdrop-blur-sm"
      >
        <span />
        {dirBtn("N")}
        <span />
        {dirBtn("W")}
        <button
          type="button"
          aria-label="Mapa lochu"
          onClick={() => guard(onOpenMap)}
          className="flex h-10 w-10 items-center justify-center rounded-lg border border-line-mech bg-surface text-gold transition-colors hover:border-gold hover:bg-gold/[0.08]"
        >
          <MapTrifold weight="fill" size={16} />
        </button>
        {dirBtn("E")}
        <span />
        {dirBtn("S")}
        <span />
      </div>
    </div>
  );
}
