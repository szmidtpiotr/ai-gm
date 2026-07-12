// FE16 loch (#1265) — pasek HUD lochu (parytet updateDungeonHUD). Etykieta lochu,
// postęp odkrytych/wszystkich, typ komnaty + skrót do mapy. ŻAR: żar na stali.
import { MapTrifold, Skull, SignOut } from "@phosphor-icons/react";
import type { DungeonRun } from "@/lib/dungeon";
import { currentNode, roomTypeLabel, visitedCount, totalNodes } from "@/lib/dungeon";

export function DungeonHud({
  run,
  charId,
  onOpenMap,
  onExit,
}: {
  run: DungeonRun | undefined;
  charId: number | undefined;
  onOpenMap: () => void;
  onExit: () => void;
}) {
  const node = currentNode(run, charId);
  const label = run?.dungeon_label || "Loch";
  const type = roomTypeLabel(node);
  const isBoss = type === "BOSS";

  return (
    <div className="flex shrink-0 items-center gap-2 border-b border-line-ember/50 bg-surface px-3 py-2">
      <Skull
        weight="fill"
        size={16}
        className={isBoss ? "text-danger" : "text-ember-glow"}
      />
      <span className="min-w-0 flex-1 truncate font-serif text-label font-semibold text-text">
        {label}
      </span>
      <span
        className={
          "rounded-full border px-2 py-0.5 font-mono text-micro uppercase tracking-[0.08em] " +
          (isBoss
            ? "border-line-danger text-danger-glow"
            : "border-line-mech text-gold")
        }
      >
        {type}
      </span>
      <span className="font-mono text-micro text-text-3">
        {visitedCount(run)}/{totalNodes(run)}
      </span>
      <button
        type="button"
        onClick={onOpenMap}
        aria-label="Mapa lochu"
        className="flex h-7 w-7 items-center justify-center rounded-md border border-line text-text-2 transition-colors hover:border-line-ember hover:text-ember-glow"
      >
        <MapTrifold size={16} />
      </button>
      <button
        type="button"
        onClick={onExit}
        aria-label="Wyjdź z lochu"
        className="flex h-7 w-7 items-center justify-center rounded-md border border-line text-text-2 transition-colors hover:border-line-danger hover:text-danger-glow"
      >
        <SignOut size={16} />
      </button>
    </div>
  );
}
