// FE10 (#1237) — F-30 Koniec walki + F-31 Popup łupu (jeden modal, makieta
// zar7-koniec). Staty (XP/złoto/HP) + pasek XP z przyrostem + siatka łupu +
// Weź wszystko / Pomiń. Wywoływany zdarzeniem: combat.status='ended', reason='victory'.
import { useEffect, useState } from "react";
import {
  Trophy,
  Star,
  Coins,
  Heart,
  TreasureChest,
  Flask,
  Sword,
  Scroll,
  HandGrabbing,
} from "@phosphor-icons/react";
import type { LootItem } from "@/lib/types";
import { lootView, xpProgress } from "@/lib/outcomes";
import { cn } from "@/lib/utils";

export function CombatEndModal({
  title,
  subtitle,
  xpGain,
  goldGain,
  hp,
  maxHp,
  lifetime,
  loot,
  claiming,
  onTake,
  onSkip,
}: {
  title: string;
  subtitle: string;
  xpGain: number;
  goldGain: number;
  hp: number;
  maxHp: number;
  lifetime: number;
  loot: LootItem[];
  claiming: boolean;
  onTake: () => void;
  onSkip: () => void;
}) {
  const xp = xpProgress(lifetime, xpGain);
  const hasLoot = loot.length > 0;
  // Animacja przyrostu: segment gain rośnie od 0 do docelowej szerokości po montażu.
  const [grown, setGrown] = useState(false);
  useEffect(() => {
    const t = window.setTimeout(() => setGrown(true), 120);
    return () => window.clearTimeout(t);
  }, []);

  return (
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center p-[18px]"
      style={{
        background:
          "radial-gradient(65% 40% at 50% 22%, rgba(232,193,90,.14), transparent 60%), rgba(8,6,4,.7)",
      }}
      data-testid="modal-combat-end"
    >
      <div className="max-h-[92vh] w-full max-w-[420px] overflow-y-auto rounded-xl border border-line-mech bg-gradient-to-b from-[#231911] to-[#170f09] shadow-modal [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
        {/* nagłówek */}
        <div className="border-b border-line-soft bg-gradient-to-b from-[rgba(232,193,90,.12)] to-transparent px-5 pb-4 pt-[22px] text-center">
          <Trophy weight="fill" size={34} className="mx-auto text-gold drop-shadow-[0_0_16px_rgba(232,193,90,.5)]" />
          <div className="mt-1.5 font-serif text-title-lg font-semibold text-text">{title}</div>
          <div className="mt-[3px] font-ui text-[12.5px] text-text-2">{subtitle}</div>
        </div>

        {/* staty */}
        <div className="flex border-b border-line-soft px-3 py-3.5">
          <StatCell icon={<Star weight="fill" size={18} />} v={`+${xpGain}`} k="Doświadczenie" tone="xp" />
          <StatCell icon={<Coins weight="fill" size={18} />} v={`+${goldGain}`} k="Złoto" tone="gold" />
          <StatCell icon={<Heart weight="fill" size={18} />} v={`${hp}/${maxHp}`} k="Zdrowie" />
        </div>

        {/* pasek XP z przyrostem */}
        <div className="border-b border-line-soft px-[18px] py-3.5">
          <div className="mb-1.5 flex justify-between font-ui text-[12px] text-text-2">
            <span>{xp.atCap ? "Doświadczenie · poziom maksymalny" : `Doświadczenie · do poziomu ${xp.level + 1}`}</span>
            <b className="font-mono text-text">
              {xp.atCap ? `${lifetime}` : `${xp.intoLevel} / ${xp.span}`}
            </b>
          </div>
          <div className="relative h-2 overflow-hidden rounded-[4px] bg-inset shadow-[inset_0_0_0_1px_var(--line-soft)]">
            <div
              className="absolute inset-y-0 left-0 rounded-[4px] bg-text-3"
              style={{ width: `${xp.basePct}%` }}
            />
            <div
              className="absolute inset-y-0 rounded-[4px] bg-gradient-to-r from-text-3 to-success shadow-[0_0_8px_rgba(168,201,131,.5)] transition-[width] duration-700 ease-out"
              style={{ left: `${xp.basePct}%`, width: grown ? `${xp.gainPct}%` : "0%" }}
            />
          </div>
        </div>

        {/* siatka łupu */}
        {hasLoot && (
          <div className="px-[18px] pb-2 pt-4">
            <div className="mb-[11px] flex items-center gap-[9px] font-ui text-[10.5px] font-bold uppercase tracking-[0.2em] text-ember">
              <TreasureChest size={14} /> Łup
              <span className="h-px flex-1 bg-line-soft" />
            </div>
            <div className="grid grid-cols-2 gap-2">
              {loot.map((it, i) => (
                <LootCell key={i} item={it} />
              ))}
            </div>
          </div>
        )}

        {/* akcje */}
        <div className="flex gap-[9px] px-[18px] pb-[18px] pt-3">
          {hasLoot ? (
            <>
              <button
                type="button"
                disabled={claiming}
                onClick={onTake}
                className="flex flex-1 items-center justify-center gap-2 rounded-md bg-gradient-to-br from-[#d1602c] to-ember py-[13px] font-ui text-[14.5px] font-semibold text-white shadow-[0_0_16px_rgba(255,122,61,.35)] disabled:opacity-60"
                data-testid="loot-take"
              >
                <HandGrabbing weight="fill" size={18} /> {claiming ? "Zabieram…" : "Weź wszystko"}
              </button>
              <button
                type="button"
                disabled={claiming}
                onClick={onSkip}
                className="rounded-md border border-line bg-[#14100c] px-[18px] py-[13px] font-ui text-[14.5px] font-semibold text-text-2 disabled:opacity-60"
                data-testid="loot-skip"
              >
                Pomiń
              </button>
            </>
          ) : (
            <button
              type="button"
              onClick={onSkip}
              className="flex flex-1 items-center justify-center gap-2 rounded-md bg-gradient-to-br from-[#d1602c] to-ember py-[13px] font-ui text-[14.5px] font-semibold text-white shadow-[0_0_16px_rgba(255,122,61,.35)]"
              data-testid="combat-end-continue"
            >
              Kontynuuj
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function StatCell({
  icon,
  v,
  k,
  tone,
}: {
  icon: React.ReactNode;
  v: string;
  k: string;
  tone?: "xp" | "gold";
}) {
  return (
    <div className="flex-1 border-r border-line-soft text-center last:border-r-0">
      <span className="text-ember-glow">{icon}</span>
      <div
        className={cn(
          "mt-[3px] font-mono text-[17px] font-semibold",
          tone === "xp" && "text-success",
          tone === "gold" && "text-gold",
          !tone && "text-text",
        )}
      >
        {v}
      </div>
      <div className="mt-0.5 font-ui text-[9px] uppercase tracking-[0.12em] text-text-3">{k}</div>
    </div>
  );
}

function LootCell({ item }: { item: LootItem }) {
  const v = lootView(item);
  const Icon = v.kind === "consumable" ? Flask : v.kind === "weapon" ? Sword : v.kind === "gold" ? Coins : Scroll;
  return (
    <div
      className={cn(
        "flex items-center gap-[11px] rounded-[11px] border p-[10px_12px]",
        v.rare
          ? "border-[rgba(181,140,240,.5)] bg-gradient-to-br from-[rgba(181,140,240,.08)] to-[#1e1811]"
          : "border-line bg-[#1e1811]",
      )}
    >
      <span
        className={cn(
          "flex h-9 w-9 flex-none items-center justify-center rounded-[9px] border text-[18px]",
          v.rare
            ? "border-[rgba(181,140,240,.4)] bg-[rgba(181,140,240,.14)] text-rare"
            : "border-line bg-[rgba(255,122,61,.1)] text-ember-glow",
        )}
      >
        <Icon weight="fill" size={18} />
      </span>
      <div className="min-w-0">
        <div className={cn("truncate font-ui text-[12.5px] font-semibold leading-tight", v.rare && "text-rare")}>
          {v.name}
          {v.rare && " ◆"}
        </div>
        <div className="mt-px font-mono text-[10px] text-text-3">{v.qtyLabel}</div>
      </div>
    </div>
  );
}
