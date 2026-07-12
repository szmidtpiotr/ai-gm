// FE16 loch (#1265) — model danych biegu lochu + helpery. Port 1:1 z
// frontend/front/js/app.js (tile-graph L11/L12/L13, BFS #869, d-pad #741).
// Silnik i mechanika bez zmian — to tylko warstwa prezentacji ŻAR.

// ── Kształt danych biegu (graph L2) ─────────────────────────────────────────

export interface DungeonRiddle {
  text?: string | null;
  solved?: boolean;
  [k: string]: unknown;
}

export interface DungeonTileContent {
  enemies?: unknown[] | null;
  riddle?: DungeonRiddle | string | null;
  items?: Array<{ type?: string; [k: string]: unknown }> | null;
  image_url?: string | null;
  label?: string | null;
  room_description?: string | null;
  is_boss_tile?: boolean;
  [k: string]: unknown;
}

export interface DungeonNode {
  position?: [number, number];
  visited?: boolean;
  cleared?: boolean;
  is_boss?: boolean;
  doors_open?: Partial<Record<Dir, string>>;
  door_hints?: Partial<Record<Dir, string>>;
  content?: DungeonTileContent;
  chest_state?: { opened?: boolean; locked_forever?: boolean };
  riddle_state?: { failed_permanently?: boolean };
  label?: string | null;
  [k: string]: unknown;
}

export interface DungeonGraph {
  entry_node?: string;
  nodes?: Record<string, DungeonNode>;
}

export interface DungeonRun {
  dungeon_key?: string;
  dungeon_label?: string | null;
  graph?: DungeonGraph;
  positions?: Record<string, string>;
  checkpoints?: Array<{ loot?: LootLine[]; [k: string]: unknown }>;
  current_cycle?: number;
  cooldown_hours?: number | null;
  at_checkpoint?: boolean;
  completed?: boolean;
  failed?: boolean;
  boss_choice_pending?: boolean;
  current_room?: number;
  character_id?: number;
  [k: string]: unknown;
}

export interface LootLine {
  label?: string | null;
  key?: string | null;
  quantity?: number | null;
}

export type Dir = "N" | "S" | "E" | "W";
export const DIRS: Dir[] = ["N", "S", "E", "W"];

// ── Odczyt bieżącego węzła ────────────────────────────────────────────────────

export function currentNodeId(
  run: DungeonRun | undefined | null,
  charId: number | undefined,
): string | undefined {
  if (!run) return undefined;
  const positions = run.positions || {};
  return (charId != null && positions[String(charId)]) || run.graph?.entry_node;
}

export function currentNode(
  run: DungeonRun | undefined | null,
  charId: number | undefined,
): DungeonNode | undefined {
  const id = currentNodeId(run, charId);
  if (!id) return undefined;
  return run?.graph?.nodes?.[id];
}

// Typ komnaty do etykiety HUD (parytet updateDungeonHUD).
export function roomTypeLabel(node: DungeonNode | undefined): string {
  if (!node) return "Komnata";
  const c = node.content || {};
  if (node.is_boss) return "BOSS";
  if (c.enemies?.length) return "Walka";
  if (c.riddle) return "Zagadka";
  if ((c.items || []).some((i) => String(i.type || "").toLowerCase() === "chest"))
    return "Skrzynia";
  return "Komnata";
}

// #869: BFS po OTWARTYCH drzwiach → najkrótsza lista kierunków z `from` do `to`.
// Pośrednie skoki tylko przez ODKRYTE (visited) kafle; CEL może być kaflem mgły
// (pierwsza warstwa) — ostatni skok to krok odkrywający. Głęboka mgła → null.
// Port verbatim z app.js `dungeonBfsPath`.
export function dungeonBfsPath(
  nodes: Record<string, DungeonNode> | undefined,
  fromNodeId: string | undefined,
  toNodeId: string | undefined,
): Dir[] | null {
  if (!nodes || !fromNodeId || !toNodeId) return null;
  if (fromNodeId === toNodeId) return [];
  if (!nodes[toNodeId]) return null;
  const prev: Record<string, { from: string; dir: Dir } | null> = {
    [fromNodeId]: null,
  };
  const queue: string[] = [fromNodeId];
  while (queue.length) {
    const cur = queue.shift()!;
    const node = nodes[cur];
    if (!node) continue;
    for (const [dir, nbId] of Object.entries(node.doors_open || {})) {
      if (!nbId || nbId in prev) continue;
      const nb = nodes[nbId];
      if (!nb) continue;
      if (nbId !== toNodeId && !nb.visited) continue;
      prev[nbId] = { from: cur, dir: dir as Dir };
      if (nbId === toNodeId) {
        const path: Dir[] = [];
        let n: string = toNodeId;
        while (prev[n]) {
          path.unshift(prev[n]!.dir);
          n = prev[n]!.from;
        }
        return path;
      }
      queue.push(nbId);
    }
  }
  return null;
}

// Czy w bieżącym węźle jest nieotwarta skrzynia (parytet updateDungeonNav).
export function hasChest(node: DungeonNode | undefined): boolean {
  if (!node) return false;
  const content = node.content || {};
  const chestState = node.chest_state || {};
  const hasChestItem = (content.items || []).some(
    (i) => String(i.type || "").toLowerCase() === "chest",
  );
  return hasChestItem && !chestState.opened && !chestState.locked_forever;
}

// Czy w bieżącym węźle jest nierozwiązana zagadka (parytet updateDungeonNav).
export function hasRiddle(node: DungeonNode | undefined): boolean {
  if (!node) return false;
  const content = node.content || {};
  const riddle = content.riddle;
  const solved =
    typeof riddle === "object" && riddle != null ? !!riddle.solved : false;
  const riddleState = node.riddle_state || {};
  return (
    !!riddle &&
    !solved &&
    !riddleState.failed_permanently &&
    !node.cleared
  );
}

export function riddleText(node: DungeonNode | undefined): string {
  const r = node?.content?.riddle;
  if (!r) return "…";
  if (typeof r === "string") return r;
  return r.text || "…";
}

// Odpoczynek na bezpiecznym (wyczyszczonym) kaflu walki (LB1 #735).
export function canRest(node: DungeonNode | undefined): boolean {
  if (!node) return false;
  return (node.content?.enemies?.length || 0) > 0 && !!node.cleared;
}

// Walka trwa (są wrogowie, kafel nieczyszczony) — chowa nav.
export function inCombatTile(node: DungeonNode | undefined): boolean {
  if (!node) return false;
  return (node.content?.enemies?.length || 0) > 0 && !node.cleared;
}

export function visitedCount(run: DungeonRun | undefined | null): number {
  const nodes = run?.graph?.nodes || {};
  return Object.values(nodes).filter((n) => n.visited).length;
}

export function totalNodes(run: DungeonRun | undefined | null): number {
  return Object.keys(run?.graph?.nodes || {}).length || 1;
}
