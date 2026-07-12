// F-87 (#1344) — karta pojawienia wroga. Wzorzec TileImageModal (loch): przy WEJŚCIU
// w walkę (once per combat_id, jak seenTiles w DungeonView) pokazuje portret herszta,
// nazwę i relatywny wskaźnik zagrożenia 🟢/🟡/🔴/💀 — by gracz zdecydował walczyć czy
// uciekać. Grupa = obrazek pierwszego + "i N innych" + sumaryczny wskaźnik. Surowa
// liczba NIGDY nie pokazana (parytet z ukrytym Power Score). Fallback gdy brak image_url.
import { Sword, X } from "@phosphor-icons/react";
import type { Combatant, RelativeThreat } from "@/lib/types";
import { EnemyRevealVisual } from "./EnemyRevealVisual";

export function EnemyRevealCard({
  enemies,
  threat,
  onClose,
}: {
  enemies: Combatant[];
  threat: RelativeThreat | null;
  onClose: () => void;
}) {
  const lead = enemies[0];
  const name = lead?.name || lead?.enemy_key || "Wróg";
  const rest = Math.max(0, enemies.length - 1);
  const img = lead?.image_url;

  return (
    <div
      className="fixed inset-0 z-[59] flex items-center justify-center bg-bg/85 p-6 backdrop-blur-sm"
      data-testid="enemy-reveal-card"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="relative w-full max-w-sm overflow-hidden rounded-xl border border-line-danger bg-surface shadow-modal">
        <button
          type="button"
          onClick={onClose}
          aria-label="Zamknij"
          className="absolute right-2 top-2 z-10 flex h-8 w-8 items-center justify-center rounded-md bg-bg/60 text-text-2 hover:text-text"
        >
          <X size={18} />
        </button>

        <EnemyRevealVisual
          name={String(name)}
          imageUrl={img}
          threat={threat}
          restCount={rest}
        />

        <button
          type="button"
          onClick={onClose}
          className="flex w-full items-center justify-center gap-1.5 border-t border-line bg-gradient-to-r from-[rgba(232,96,79,.14)] to-surface px-4 py-2.5 font-ui text-[12.5px] font-bold uppercase tracking-[0.08em] text-danger-glow hover:from-[rgba(232,96,79,.22)]"
        >
          <Sword weight="fill" size={15} /> Stań do walki
        </button>
      </div>
    </div>
  );
}
