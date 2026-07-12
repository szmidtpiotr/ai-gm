// FE16 loch (#1265) — wynik otwarcia skrzyni (parytet showChestResultModal). Rzut
// DEX vs DC, przyznany łup, pułapka. ŻAR: karta mechaniki (złoto/krew).
import { X, TreasureChest, Package, Warning } from "@phosphor-icons/react";
import type { DungeonTileResult } from "@/hooks/useDungeon";

export function ChestResultModal({
  resp,
  onClose,
}: {
  resp: DungeonTileResult;
  onClose: () => void;
}) {
  const loot = Array.isArray(resp.loot) ? resp.loot : [];
  const success = !!resp.success;
  const rollLine =
    typeof resp.roll === "number"
      ? `d20: ${resp.roll} ${(resp.dex_mod ?? 0) >= 0 ? "+" : ""}${resp.dex_mod ?? 0} = ${resp.total} vs DC ${resp.dc}`
      : "";

  let body: React.ReactNode;
  if (resp.chest_locked_forever && !success) {
    body = (
      <p className="font-ui text-label text-danger-glow">
        Mechanizm zablokował skrzynię na zawsze.
      </p>
    );
  } else if (success) {
    body = loot.length ? (
      <ul className="flex flex-col gap-1">
        {loot.map((l, i) => (
          <li key={i} className="flex items-center gap-2 font-ui text-label text-text">
            <Package weight="fill" size={15} className="text-gold" />
            {l.label || l.key || "?"} ×{l.quantity || 1}
          </li>
        ))}
      </ul>
    ) : (
      <p className="font-ui text-label text-text-3">Skrzynia była pusta.</p>
    );
  } else {
    const left = (resp.max_attempts ?? 3) - (resp.attempt ?? 0);
    body = (
      <p className="font-ui text-label text-text-2">
        Nie udało się otworzyć. Pozostało prób: {Math.max(0, left)}.
      </p>
    );
  }

  return (
    <div
      className="fixed inset-0 z-[58] flex items-center justify-center bg-bg/85 p-6 backdrop-blur-sm"
      data-testid="dungeon-chest-modal"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="relative w-full max-w-xs rounded-xl border border-line-mech bg-surface p-4 shadow-modal">
        <button
          type="button"
          onClick={onClose}
          aria-label="Zamknij"
          className="absolute right-3 top-3 text-text-3 hover:text-text"
        >
          <X size={18} />
        </button>
        <div className="mb-2 flex items-center gap-2 font-serif text-body font-semibold text-text">
          <TreasureChest weight="fill" size={18} className="text-gold" />
          {success ? "Skrzynia otwarta" : "Skrzynia"}
        </div>
        {rollLine && (
          <div className="mb-2 font-mono text-micro text-text-3">{rollLine}</div>
        )}
        {body}
        {resp.trap?.triggered && (
          <p className="mt-2.5 flex items-start gap-1.5 rounded-md border border-line-danger bg-danger/[0.08] px-2.5 py-1.5 font-ui text-micro text-danger-glow">
            <Warning weight="fill" size={14} className="mt-0.5 flex-none" />
            Pułapka! {resp.trap.description || ""} (−{resp.trap.damage} HP)
          </p>
        )}
      </div>
    </div>
  );
}
