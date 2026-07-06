// FE10 (#1237) — F-32 Drop celebration (makieta zar9-drop). Rzadki/affixed item
// + diff vs założony. Wywoływany zdarzeniem: claim-loot zwraca comparison.is_special.
import { MagicWand, Sword, Shield, Sparkle, HandGrabbing, Backpack } from "@phosphor-icons/react";
import type { DropComparison } from "@/lib/types";
import { affixEffectLabel } from "@/lib/outcomes";

type Metrics = Record<string, number> | null | undefined;

export function DropCelebration({
  drop,
  equipping,
  onEquip,
  onClose,
}: {
  drop: DropComparison;
  equipping: boolean;
  onEquip: (inventoryId: number, slot: string) => void;
  onClose: () => void;
}) {
  const isWeapon = drop.item_type === "weapon";
  const Icon = isWeapon ? Sword : drop.item_type === "armor" ? Shield : MagicWand;
  const newM = (drop as Record<string, unknown>).new as Metrics;
  const eqM = (drop as Record<string, unknown>).equipped as Metrics;
  const diff = (drop.diff ?? {}) as Record<string, number | null>;
  const canEquip = !!drop.suggested_slot && drop.inventory_id != null;

  const rows: Array<{ label: string; key: string }> = isWeapon
    ? [
        { label: "Obrażenia", key: "damage" },
        { label: "Do trafienia", key: "attack_bonus" },
      ]
    : [{ label: "Pancerz", key: "ac" }];

  return (
    <div
      className="fixed inset-0 z-[70] flex items-center justify-center p-[22px]"
      style={{
        background:
          "radial-gradient(55% 42% at 50% 34%, rgba(181,140,240,.2), transparent 60%), rgba(8,6,4,.85)",
      }}
      data-testid="modal-drop"
    >
      <div className="w-full max-w-[380px] text-center">
        <div className="relative">
          <div
            className="pointer-events-none absolute left-1/2 top-[-30px] h-[280px] w-[280px] -translate-x-1/2 animate-[spin_14s_linear_infinite] rounded-full"
            style={{
              background:
                "conic-gradient(from 0deg, transparent, rgba(181,140,240,.12) 8%, transparent 16%, rgba(181,140,240,.1) 24%, transparent 32%, rgba(181,140,240,.12) 40%, transparent 48%)",
            }}
          />
          <div className="relative mb-3.5 flex items-center justify-center gap-2 font-ui text-[11px] font-bold uppercase tracking-[0.3em] text-[#cba9f5]">
            <Sparkle weight="fill" size={13} /> Rzadka zdobycz <Sparkle weight="fill" size={13} />
          </div>
          <div className="relative mx-auto mb-4 flex h-[120px] w-[120px] items-center justify-center rounded-[26px] border-[1.5px] border-rare bg-[radial-gradient(circle_at_40%_32%,rgba(181,140,240,.35),rgba(28,20,36,.95))] text-[#cba9f5] shadow-[0_0_50px_rgba(181,140,240,.4),inset_0_2px_14px_rgba(255,255,255,.1)]">
            <Icon weight="fill" size={56} />
          </div>
        </div>

        <div className="font-serif text-title-lg font-semibold text-[#cba9f5]">{drop.name}</div>
        <div className="mt-1 font-ui text-[11px] font-semibold uppercase tracking-[0.16em] text-rare">
          ◆ {drop.rarity_label}
          {isWeapon ? " · broń" : drop.item_type === "armor" ? " · zbroja" : ""}
        </div>

        {/* afiksy jako opis */}
        {(drop.affixes ?? []).length > 0 && (
          <div className="mx-auto mt-3 max-w-[300px] font-serif text-[13.5px] italic leading-[1.6] text-text-2">
            {(drop.affixes ?? [])
              .map((a) =>
                [a.name, (a.effects ?? []).map(affixEffectLabel).filter(Boolean).join(", ")]
                  .filter(Boolean)
                  .join(" — "),
              )
              .filter(Boolean)
              .join(" · ")}
          </div>
        )}

        {/* diff vs założony */}
        <div className="my-5 overflow-hidden rounded-lg border border-line bg-[#1e1811]">
          <div className="border-b border-line-soft bg-white/[0.02] p-2 font-ui text-[9.5px] font-bold uppercase tracking-[0.14em] text-text-3">
            Porównanie z założonym
          </div>
          {rows.map((r) => (
            <DiffRow
              key={r.key}
              label={r.label}
              oldV={fmtMetric(eqM?.[r.key])}
              newV={fmtMetric(newM?.[r.key])}
              delta={diff[r.key]}
              hasEquipped={!!eqM}
            />
          ))}
        </div>

        <div className="flex gap-[9px]">
          <button
            type="button"
            disabled={equipping || !canEquip}
            onClick={() => canEquip && onEquip(drop.inventory_id, String(drop.suggested_slot))}
            data-testid="drop-equip"
            className="flex flex-1 items-center justify-center gap-2 rounded-md bg-gradient-to-br from-[#8a5fc9] to-rare py-3.5 font-ui text-[14.5px] font-semibold text-white shadow-[0_0_18px_rgba(181,140,240,.4)] disabled:opacity-50"
          >
            <HandGrabbing weight="fill" size={18} /> {equipping ? "Zakładam…" : "Załóż teraz"}
          </button>
          <button
            type="button"
            onClick={onClose}
            data-testid="drop-bag"
            className="rounded-md border border-line bg-[#1e1811] px-[18px] py-3.5 text-text-2"
            aria-label="Do plecaka"
          >
            <Backpack size={20} />
          </button>
        </div>
      </div>
    </div>
  );
}

function fmtMetric(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return "—";
  return String(Math.round(v * 10) / 10);
}

function DiffRow({
  label,
  oldV,
  newV,
  delta,
  hasEquipped,
}: {
  label: string;
  oldV: string;
  newV: string;
  delta: number | null | undefined;
  hasEquipped: boolean;
}) {
  const dir = delta == null ? "none" : delta > 0 ? "up" : delta < 0 ? "down" : "same";
  const arrow = dir === "up" ? "▲" : dir === "down" ? "▼" : dir === "same" ? "=" : "";
  const cls = dir === "up" ? "text-success" : dir === "down" ? "text-danger" : "text-text-2";
  return (
    <div className="flex items-center border-b border-line-soft px-3.5 py-[9px] font-mono text-[12.5px] last:border-b-0">
      <span className="flex-1 text-left text-text-2">{label}</span>
      {hasEquipped ? (
        <>
          <span className="w-14 text-right text-text-3">{oldV}</span>
          <span className={"w-[26px] text-center " + cls}>{arrow}</span>
          <span className={"w-14 text-right font-semibold " + cls}>{newV}</span>
        </>
      ) : (
        <span className="text-text-3">{newV} · brak porównania</span>
      )}
    </div>
  );
}
