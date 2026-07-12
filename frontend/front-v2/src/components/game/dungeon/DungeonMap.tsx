// FE16 loch (#1265) — mapa lochu (SVG, tile-graph L11). Port 1:1 z renderDungeonMap:
// korytarze → kafle → mgła (?) → znacznik gracza; pan/zoom; klik = auto-marsz BFS (#869).
// Kolory z tokenów §6 (var(--…)) — żar dla bieżącego, stal dla znanych, krew dla bossa.
import { useMemo, useRef, useState } from "react";
import { X } from "@phosphor-icons/react";
import type { Dir, DungeonNode, DungeonRun } from "@/lib/dungeon";
import { currentNodeId, dungeonBfsPath, roomTypeLabel } from "@/lib/dungeon";

// Metryki siatki — Numbers Policy (L11 wartości startowe, tuning po playteście).
const S = 52; // rozmiar kafla px
const GAP = 28; // długość korytarza px
const PAD = 32; // padding px
const R = 8; // promień narożnika px
const STEP = S + GAP;

export function DungeonMap({
  run,
  charId,
  onClose,
  onWalk,
  onStep,
}: {
  run: DungeonRun | undefined;
  charId: number | undefined;
  onClose: () => void;
  onWalk: (path: Dir[]) => void; // ścieżka BFS przez znane kafle
  onStep: (dir: Dir) => void; // pojedynczy krok w mgłę (sąsiad)
}) {
  const svgRef = useRef<SVGSVGElement | null>(null);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const dragRef = useRef<{ active: boolean; x: number; y: number; moved: boolean }>({
    active: false,
    x: 0,
    y: 0,
    moved: false,
  });

  const model = useMemo(() => buildModel(run, charId), [run, charId]);

  function onWheel(e: React.WheelEvent) {
    e.preventDefault();
    const factor = e.deltaY < 0 ? 1.15 : 1 / 1.15;
    setZoom((z) => Math.min(4, Math.max(0.4, z * factor)));
  }
  function onPointerDown(e: React.PointerEvent) {
    dragRef.current = { active: true, x: e.clientX, y: e.clientY, moved: false };
  }
  function onPointerMove(e: React.PointerEvent) {
    const d = dragRef.current;
    if (!d.active) return;
    const dx = e.clientX - d.x;
    const dy = e.clientY - d.y;
    if (Math.hypot(dx, dy) > 3) d.moved = true;
    setPan((p) => ({ x: p.x + dx / zoom, y: p.y + dy / zoom }));
    d.x = e.clientX;
    d.y = e.clientY;
  }
  function onPointerUp() {
    dragRef.current.active = false;
  }

  // Klik kafla → BFS auto-marsz (#869) lub 1-krok w mgłę.
  function onClick(e: React.MouseEvent) {
    if (dragRef.current.moved) return;
    const svg = svgRef.current;
    if (!svg || !run || !model) return;
    const rect = svg.getBoundingClientRect();
    const scaleX = model.w / rect.width;
    const scaleY = model.h / rect.height;
    const cx = ((e.clientX - rect.left) * scaleX) / zoom - pan.x;
    const cy = ((e.clientY - rect.top) * scaleY) / zoom - pan.y;

    const nodes = run.graph?.nodes || {};
    const curId = currentNodeId(run, charId);
    const curNode = curId ? nodes[curId] : undefined;
    if (!curNode) return;

    // Najbliższy narysowany kafel w promieniu S px.
    let clickedId: string | null = null;
    let closest = 9999;
    for (const nid of model.drawIds) {
      const n = nodes[nid];
      if (!n?.position) continue;
      const tx = PAD + (n.position[0] - model.minCol) * STEP + S / 2;
      const ty = PAD + (model.maxRow - n.position[1]) * STEP + S / 2;
      const dist = Math.hypot(cx - tx, cy - ty);
      if (dist < closest && dist < S) {
        closest = dist;
        clickedId = nid;
      }
    }
    if (!clickedId || clickedId === curId) return;

    const path = dungeonBfsPath(nodes, curId, clickedId);
    if (path && path.length) {
      onWalk(path);
      return;
    }
    // Bezpośredni sąsiad w mgle → pojedynczy krok odkrywający.
    for (const [dir, targetId] of Object.entries(curNode.doors_open || {})) {
      if (targetId === clickedId) {
        onStep(dir as Dir);
        return;
      }
    }
  }

  return (
    <div
      className="fixed inset-0 z-[55] flex flex-col bg-bg/92 backdrop-blur-sm"
      data-testid="dungeon-map-overlay"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="flex items-center justify-between border-b border-line px-4 py-3">
        <span className="font-serif text-body font-semibold text-text">
          Mapa lochu · {run?.dungeon_label || ""}
        </span>
        <button
          type="button"
          onClick={onClose}
          aria-label="Zamknij mapę"
          className="flex h-8 w-8 items-center justify-center rounded-md border border-line text-text-2 hover:text-text"
        >
          <X size={18} />
        </button>
      </div>
      <div className="min-h-0 flex-1 overflow-hidden">
        {model ? (
          <svg
            ref={svgRef}
            viewBox={`0 0 ${model.w} ${model.h}`}
            width="100%"
            height="100%"
            className="touch-none"
            style={{ cursor: dragRef.current.active ? "grabbing" : "grab" }}
            onWheel={onWheel}
            onPointerDown={onPointerDown}
            onPointerMove={onPointerMove}
            onPointerUp={onPointerUp}
            onPointerLeave={onPointerUp}
            onClick={onClick}
          >
            <g transform={`translate(${pan.x},${pan.y}) scale(${zoom})`}>
              {model.elements}
            </g>
          </svg>
        ) : (
          <div className="flex h-full items-center justify-center font-ui text-label text-text-3">
            Brak danych mapy
          </div>
        )}
      </div>
      <div className="border-t border-line px-4 py-2 text-center font-ui text-micro text-text-3">
        Kliknij odkryty kafel, aby tam przejść · przeciągnij, by przesunąć · scroll = zoom
      </div>
    </div>
  );
}

interface Model {
  w: number;
  h: number;
  minCol: number;
  maxRow: number;
  drawIds: string[];
  elements: React.ReactNode[];
}

function buildModel(
  run: DungeonRun | undefined,
  charId: number | undefined,
): Model | null {
  const nodes = run?.graph?.nodes || {};
  if (!Object.keys(nodes).length) return null;
  const curId = currentNodeId(run, charId);

  const visitedIds = new Set(
    Object.entries(nodes)
      .filter(([, n]) => n.visited)
      .map(([id]) => id),
  );
  const fogIds = new Set<string>();
  for (const [, node] of Object.entries(nodes)) {
    if (!node.visited) continue;
    for (const nb of Object.values(node.doors_open || {})) {
      if (nb && !visitedIds.has(nb)) fogIds.add(nb);
    }
  }
  const drawIds = [...visitedIds, ...fogIds];

  let minCol = Infinity,
    maxCol = -Infinity,
    minRow = Infinity,
    maxRow = -Infinity;
  for (const nid of drawIds) {
    const pos = nodes[nid]?.position;
    if (!pos) continue;
    minCol = Math.min(minCol, pos[0]);
    maxCol = Math.max(maxCol, pos[0]);
    minRow = Math.min(minRow, pos[1]);
    maxRow = Math.max(maxRow, pos[1]);
  }
  if (!isFinite(minCol)) {
    minCol = 0;
    maxCol = 0;
    minRow = 0;
    maxRow = 0;
  }

  const w = (maxCol - minCol + 1) * STEP + GAP + PAD * 2;
  const h = (maxRow - minRow + 1) * STEP + GAP + PAD * 2;
  const tileX = (col: number) => PAD + (col - minCol) * STEP;
  const tileY = (row: number) => PAD + (maxRow - row) * STEP;
  const cxFn = (col: number) => tileX(col) + S / 2;
  const cyFn = (row: number) => tileY(row) + S / 2;

  const els: React.ReactNode[] = [];
  let key = 0;

  // Korytarze (za kaflami).
  const drawn = new Set<string>();
  for (const [nid, node] of Object.entries(nodes)) {
    if (!drawIds.includes(nid) || !node.visited || !node.position) continue;
    for (const [, nb] of Object.entries(node.doors_open || {})) {
      if (!nb || !drawIds.includes(nb)) continue;
      const k = [nid, nb].sort().join("|");
      if (drawn.has(k)) continue;
      drawn.add(k);
      const nPos = nodes[nb]?.position;
      if (!nPos) continue;
      const neighborVisited = visitedIds.has(nb);
      els.push(
        <line
          key={`c${key++}`}
          x1={cxFn(node.position[0])}
          y1={cyFn(node.position[1])}
          x2={cxFn(nPos[0])}
          y2={cyFn(nPos[1])}
          stroke="var(--line-ember)"
          strokeWidth={4}
          opacity={neighborVisited ? 0.65 : 0.3}
        />,
      );
    }
  }

  // Kafle.
  for (const nid of drawIds) {
    const node = nodes[nid];
    if (!node?.position) continue;
    const [col, row] = node.position;
    const x = tileX(col);
    const y = tileY(row);
    const isCurrent = nid === curId;
    const isVisited = visitedIds.has(nid);
    const isBoss = !!node.is_boss;
    const isCleared = !!node.cleared;

    if (isVisited) {
      let fill = "var(--surface)";
      let stroke = "var(--line)";
      let strokeW = 1.5;
      let textColor = "var(--text-2)";
      if (isCurrent) {
        fill = "var(--mech-card)";
        stroke = "var(--ember)";
        strokeW = 2.5;
        textColor = "var(--ember-glow)";
      } else if (isCleared) {
        fill = "var(--bg)";
        stroke = "var(--line-soft)";
        strokeW = 1;
        textColor = "var(--text-3)";
      }
      if (isBoss) {
        stroke = "var(--danger)";
        fill = "var(--mech-card)";
      }
      if (isCurrent) {
        els.push(
          <rect
            key={`g${key++}`}
            x={x - 3}
            y={y - 3}
            width={S + 6}
            height={S + 6}
            rx={R + 3}
            fill="none"
            stroke="var(--ember)"
            strokeWidth={1}
            opacity={0.3}
          />,
        );
      }
      els.push(
        <rect
          key={`t${key++}`}
          x={x}
          y={y}
          width={S}
          height={S}
          rx={R}
          fill={fill}
          stroke={stroke}
          strokeWidth={strokeW}
        />,
      );
      const label = isBoss ? "BOSS" : roomTypeLabel(node);
      els.push(
        <text
          key={`l${key++}`}
          x={cxFn(col)}
          y={y + S - 9}
          textAnchor="middle"
          fontSize={7}
          fill={textColor}
          style={{
            pointerEvents: "none",
            textTransform: "uppercase",
            letterSpacing: "0.06em",
          }}
        >
          {label}
        </text>,
      );
      if (isCleared && !isCurrent) {
        els.push(
          <text
            key={`v${key++}`}
            x={x + S - 9}
            y={y + 13}
            textAnchor="middle"
            fontSize={9}
            fill="var(--mech-ok)"
            style={{ pointerEvents: "none" }}
          >
            ✓
          </text>,
        );
      }
      if (isCurrent) {
        els.push(
          <circle
            key={`p${key++}`}
            cx={cxFn(col)}
            cy={cyFn(row)}
            r={6}
            fill="var(--ember)"
            stroke="var(--ember-glow)"
            strokeWidth={1.5}
            style={{ pointerEvents: "none" }}
          />,
        );
      }
    } else {
      // Kafel mgły: obrys przerywany + "?".
      const hint = fogHint(nodes, visitedIds, nid);
      els.push(
        <rect
          key={`f${key++}`}
          x={x}
          y={y}
          width={S}
          height={S}
          rx={R}
          fill="var(--bg)"
          stroke="var(--line)"
          strokeWidth={1}
          opacity={0.7}
          strokeDasharray="4,3"
        >
          {hint ? <title>{hint}</title> : null}
        </rect>,
      );
      els.push(
        <text
          key={`q${key++}`}
          x={cxFn(col)}
          y={cyFn(row)}
          textAnchor="middle"
          dominantBaseline="middle"
          fontSize={20}
          fill="var(--text-3)"
          style={{ pointerEvents: "none" }}
        >
          ?
        </text>,
      );
    }
  }

  return { w, h, minCol, maxRow, drawIds, elements: els };
}

function fogHint(
  nodes: Record<string, DungeonNode>,
  visitedIds: Set<string>,
  fogId: string,
): string {
  for (const [vnid, vnode] of Object.entries(nodes)) {
    if (!visitedIds.has(vnid)) continue;
    for (const [dir, nbId] of Object.entries(vnode.doors_open || {})) {
      if (nbId === fogId) return vnode.door_hints?.[dir as Dir] || "";
    }
  }
  return "";
}
