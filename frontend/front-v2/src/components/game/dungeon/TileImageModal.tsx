// FE16 loch (#1265) — popup obrazu kafla (parytet showTileImageModal). Pojawia się
// przy PIERWSZEJ wizycie kafla z grafiką; klik poza / ✕ zamyka. ŻAR: ramka żarowa.
import { X } from "@phosphor-icons/react";
import type { DungeonNode } from "@/lib/dungeon";

export function TileImageModal({
  node,
  onClose,
}: {
  node: DungeonNode;
  onClose: () => void;
}) {
  const content = node.content || {};
  const name = content.label || node.label || "Komnata";
  return (
    <div
      className="fixed inset-0 z-[58] flex items-center justify-center bg-bg/85 p-6 backdrop-blur-sm"
      data-testid="dungeon-tile-modal"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="relative w-full max-w-sm overflow-hidden rounded-xl border border-line-ember bg-surface shadow-modal">
        <button
          type="button"
          onClick={onClose}
          aria-label="Zamknij"
          className="absolute right-2 top-2 z-10 flex h-8 w-8 items-center justify-center rounded-md bg-bg/60 text-text-2 hover:text-text"
        >
          <X size={18} />
        </button>
        {content.image_url ? (
          <img
            src={content.image_url}
            alt={String(name)}
            className="aspect-[4/3] w-full object-cover"
          />
        ) : (
          <div className="flex aspect-[4/3] w-full items-center justify-center bg-mech-card text-text-3">
            Brak obrazu
          </div>
        )}
        <div className="border-t border-line px-4 py-2.5 text-center font-serif text-body font-semibold text-text">
          {name}
        </div>
      </div>
    </div>
  );
}
