// F-55/F-76/F-78 · Ekwipunek — sylwetka Diablo-overlap (itemy nachodzą na ciało),
// toggle Sylwetka/Lista, plecak grupowany (zużywalne/sprzęt), przedmioty fabularne
// (collapsible). Equip/zdejmij przez klik. Makieta: zar5-ekwipunek.html.
import { useState } from "react";
import {
  CaretDown,
  CircleNotch,
  Coins,
  ListBullets,
  Person,
  Scales,
  Scroll,
} from "@phosphor-icons/react";
import { cn } from "@/lib/utils";
import {
  DOLL_SLOTS,
  groupBackpack,
  splitInventory,
  targetSlotFor,
  type EquippedMap,
  type InventoryItem,
} from "@/lib/sheet";
import { readVitals } from "@/lib/game";
import type { HeroSheet } from "@/lib/types";
import { SecHead, PanelScroll, itemIcon, SLOT_ICON } from "./sheetUi";

// Pozycje slotów na sylwetce (procenty wg makiety zar5) — nachodzą na figurę.
const DOLL_POS: Record<string, { top: string; left: string; small?: boolean }> = {
  head: { top: "11%", left: "50%" },
  amulet: { top: "25%", left: "50%", small: true },
  chest: { top: "39%", left: "50%" },
  main_hand: { top: "41%", left: "15%" },
  off_hand: { top: "41%", left: "85%" },
  hands: { top: "57%", left: "81%" },
  legs: { top: "63%", left: "50%" },
  feet: { top: "87%", left: "50%" },
};

export function PanelInventory({
  sheet,
  items,
  loading,
  onEquip,
  busy,
}: {
  sheet: HeroSheet | undefined;
  items: InventoryItem[] | undefined;
  loading: boolean;
  onEquip: (inventoryId: number, slot: string | null) => void;
  busy: boolean;
}) {
  const [view, setView] = useState<"doll" | "list">("doll");
  const v = readVitals(sheet);
  const { equipped, backpack } = splitInventory(items ?? []);
  const bag = groupBackpack(backpack);
  const defense = readDefense(sheet);
  const carry = readCarry(sheet);

  if (loading) {
    return (
      <PanelScroll>
        <div className="flex items-center justify-center gap-2 py-16 text-text-3">
          <CircleNotch className="animate-spin" size={20} />
          <span className="font-ui text-body">Wczytywanie ekwipunku…</span>
        </div>
      </PanelScroll>
    );
  }

  return (
    <PanelScroll>
      {/* Sakiewka: złoto + udźwig */}
      <div className="mb-4 flex gap-2">
        <Pouch icon={<Coins weight="fill" size={18} className="text-gold" />} k="Złoto" val={`${v.gold} gp`} />
        <Pouch icon={<Scales size={18} className="text-gold" />} k="Udźwig" val={carry} />
      </div>

      <div className="grid grid-cols-1 gap-x-10 lg:grid-cols-[380px_1fr]">
        {/* ── Na ciele ── */}
        <section className="mb-6">
          <div className="mb-3 flex items-center gap-2.5">
            <SecHead>Na ciele</SecHead>
            <div className="ml-auto flex gap-0.5 rounded-md border border-line bg-bg p-0.5">
              <ToggleBtn on={view === "doll"} onClick={() => setView("doll")}>
                <Person size={14} /> Sylwetka
              </ToggleBtn>
              <ToggleBtn on={view === "list"} onClick={() => setView("list")}>
                <ListBullets size={14} /> Lista
              </ToggleBtn>
            </div>
          </div>

          {view === "doll" ? (
            <Doll equipped={equipped} onEquip={onEquip} busy={busy} />
          ) : (
            <EquippedList equipped={equipped} onEquip={onEquip} busy={busy} />
          )}

          {/* Podsumowanie obrony */}
          <div className="mx-auto mt-3.5 flex max-w-[340px] overflow-hidden rounded-md border border-line-mech bg-mech-card font-mono lg:max-w-none">
            <DefCell k="Redukcja" v={String(defense.reduction)} />
            <DefCell k="Obrona" v={String(defense.base)} />
            <DefCell k="Inicjat." v={fmtSigned(defense.initiative)} />
            <DefCell k="Zasięg" v={defense.zone} last />
          </div>
        </section>

        {/* ── Plecak + fabularne ── */}
        <div>
          <section className="mb-6">
            <SecHead>
              Plecak{" "}
              <span className="font-normal normal-case tracking-normal text-text-3">
                {backpack.length} rzeczy
              </span>
            </SecHead>
            {bag.consumables.length > 0 && (
              <>
                <SubHead>Zużywalne</SubHead>
                <Bag items={bag.consumables} onEquip={onEquip} busy={busy} />
              </>
            )}
            {bag.gear.length > 0 && (
              <>
                <SubHead>Sprzęt i broń</SubHead>
                <Bag items={bag.gear} onEquip={onEquip} busy={busy} />
              </>
            )}
            {backpack.length === 0 && (
              <p className="rounded-md border border-line-soft bg-surface px-3.5 py-3 font-serif text-label text-text-3">
                Plecak jest pusty.
              </p>
            )}
          </section>

          {bag.lore.length > 0 && (
            <section>
              <SecHead>Przedmioty fabularne</SecHead>
              <LoreGroup label="Zwoje, mapy i listy" items={bag.lore} />
            </section>
          )}
        </div>
      </div>
    </PanelScroll>
  );
}

// ── Sylwetka (Diablo-overlap) ────────────────────────────────────────────────
function Doll({
  equipped,
  onEquip,
  busy,
}: {
  equipped: EquippedMap;
  onEquip: (id: number, slot: string | null) => void;
  busy: boolean;
}) {
  return (
    <div
      className="relative mx-auto w-full max-w-[340px] overflow-hidden rounded-lg border border-line lg:max-w-none"
      style={{
        aspectRatio: "1 / 1.28",
        background:
          "radial-gradient(58% 42% at 50% 26%, rgba(255,122,61,.14), transparent 68%), linear-gradient(180deg,#241a11,#171009)",
      }}
    >
      {/* figura */}
      <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
        <Person weight="fill" size={260} className="max-h-[80%] max-w-[80%] text-[rgba(255,190,140,0.16)]" />
      </div>
      {DOLL_SLOTS.map(({ slot, label }) => {
        const pos = DOLL_POS[slot];
        const it = equipped[slot];
        return (
          <DollSlot
            key={slot}
            label={label}
            item={it}
            slot={slot}
            pos={pos}
            onEquip={onEquip}
            busy={busy}
          />
        );
      })}
    </div>
  );
}

function DollSlot({
  label,
  item,
  slot,
  pos,
  onEquip,
  busy,
}: {
  label: string;
  item: InventoryItem | undefined;
  slot: string;
  pos: { top: string; left: string; small?: boolean };
  onEquip: (id: number, slot: string | null) => void;
  busy: boolean;
}) {
  const Icon = item ? itemIcon(item) : SLOT_ICON[slot];
  const dur = item?.durability;
  const size = pos.small ? 42 : 56;
  return (
    <button
      type="button"
      disabled={!item || busy}
      onClick={() => item && onEquip(item.id, null)}
      title={item ? `${item.label} — kliknij, by zdjąć` : `${label} (pusty)`}
      className={cn(
        "absolute flex -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-[11px] border shadow-[0_3px_12px_rgba(0,0,0,.55)] backdrop-blur-[1px] transition-colors",
        item
          ? "border-line bg-[rgba(20,15,10,0.72)] text-ember-glow hover:border-ember"
          : "border-dashed border-line bg-[rgba(20,15,10,0.4)] text-text-3",
        !item && "cursor-default",
      )}
      style={{ top: pos.top, left: pos.left, width: size, height: size }}
    >
      <span className="absolute -top-2 left-1/2 -translate-x-1/2 whitespace-nowrap bg-bg px-1 text-[7px] font-bold uppercase tracking-[0.1em] text-text-3">
        {label}
      </span>
      {Icon && <Icon size={pos.small ? 18 : 24} weight={item ? "regular" : "regular"} />}
      {dur && (
        <span className="absolute inset-x-1.5 -bottom-[3px] h-[3px] overflow-hidden rounded-[2px] bg-[#3a2a1a]">
          <span
            className={cn("block h-full", dur.pct < 40 ? "bg-danger" : "bg-ember")}
            style={{ width: `${dur.pct}%` }}
          />
        </span>
      )}
    </button>
  );
}

function EquippedList({
  equipped,
  onEquip,
  busy,
}: {
  equipped: EquippedMap;
  onEquip: (id: number, slot: string | null) => void;
  busy: boolean;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      {DOLL_SLOTS.map(({ slot, label }) => {
        const it = equipped[slot];
        const Icon = it ? itemIcon(it) : SLOT_ICON[slot];
        return (
          <div
            key={slot}
            className={cn(
              "flex items-center gap-3 rounded-md border px-3 py-2.5",
              it ? "border-line-soft bg-surface" : "border-dashed border-line-soft bg-transparent opacity-60",
            )}
          >
            <span className="flex h-8 w-8 items-center justify-center rounded-md border border-line bg-bg text-ember-glow">
              {Icon && <Icon size={16} />}
            </span>
            <div className="min-w-0 flex-1">
              <div className="text-[9px] font-bold uppercase tracking-[0.14em] text-text-3">{label}</div>
              <div className="truncate text-label font-medium text-text">{it?.label ?? "— pusty —"}</div>
            </div>
            {it && (
              <button
                type="button"
                disabled={busy}
                onClick={() => onEquip(it.id, null)}
                className="shrink-0 rounded-md border border-line px-2.5 py-1 font-ui text-[11px] text-text-2 hover:border-line-ember hover:text-ember-glow disabled:opacity-50"
              >
                Zdejmij
              </button>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ── Plecak (siatka) ──────────────────────────────────────────────────────────
function Bag({
  items,
  onEquip,
  busy,
}: {
  items: InventoryItem[];
  onEquip: (id: number, slot: string | null) => void;
  busy: boolean;
}) {
  return (
    <div className="mb-3 grid grid-cols-4 gap-1.5 sm:grid-cols-5">
      {items.map((it) => {
        const Icon = itemIcon(it);
        const slot = targetSlotFor(it);
        const equippable = !!slot;
        return (
          <button
            key={it.id}
            type="button"
            disabled={!equippable || busy}
            onClick={() => slot && onEquip(it.id, slot)}
            title={equippable ? `${it.label} — kliknij, by założyć` : it.label}
            className={cn(
              "relative flex aspect-square flex-col items-center justify-center gap-1 rounded-md border border-line bg-surface p-1 text-center transition-colors",
              equippable ? "cursor-pointer hover:border-line-ember" : "cursor-default",
            )}
          >
            {it.quantity > 1 && (
              <span className="absolute right-0.5 top-0.5 rounded border border-line bg-[rgba(20,16,12,0.9)] px-1 font-mono text-[8.5px] font-semibold text-text">
                ×{it.quantity}
              </span>
            )}
            <Icon size={19} className="text-text-2" />
            <span className="line-clamp-2 text-[8.5px] font-medium leading-tight text-text-3">
              {it.label}
            </span>
          </button>
        );
      })}
    </div>
  );
}

function LoreGroup({ label, items }: { label: string; items: InventoryItem[] }) {
  return (
    <details className="mb-1.5 overflow-hidden rounded-md border border-line-soft bg-surface" open>
      <summary className="flex cursor-pointer list-none items-center gap-2.5 px-3.5 py-2.5 text-label font-semibold text-text-2 [&::-webkit-details-marker]:hidden">
        <Scroll size={15} className="text-ember" />
        {label} ({items.length})
        <CaretDown size={11} className="ml-auto text-text-3" />
      </summary>
      {items.map((it) => (
        <div
          key={it.id}
          className="flex items-center gap-2.5 border-t border-line-soft px-3.5 py-2 text-[12.5px] text-text-2"
        >
          {it.label}
          {it.quantity > 1 && <em className="ml-auto text-[11px] not-italic text-text-3">×{it.quantity}</em>}
        </div>
      ))}
    </details>
  );
}

// ── drobne prymitywy ─────────────────────────────────────────────────────────
function Pouch({ icon, k, val }: { icon: React.ReactNode; k: string; val: string }) {
  return (
    <div className="flex flex-1 items-center gap-2.5 rounded-md border border-line bg-surface px-3.5 py-2.5">
      {icon}
      <div>
        <div className="text-[10px] font-semibold uppercase tracking-[0.14em] text-text-3">{k}</div>
        <div className="mt-0.5 font-mono text-body font-semibold text-ember-glow">{val}</div>
      </div>
    </div>
  );
}

function ToggleBtn({
  on,
  onClick,
  children,
}: {
  on: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "flex items-center gap-1.5 rounded px-2.5 py-1.5 font-ui text-[11.5px] font-semibold transition-colors",
        on ? "bg-[rgba(255,122,61,0.14)] text-ember-glow" : "text-text-3 hover:text-text-2",
      )}
    >
      {children}
    </button>
  );
}

function SubHead({ children }: { children: React.ReactNode }) {
  return (
    <div className="mb-2 mt-3.5 font-ui text-[10px] font-semibold uppercase tracking-[0.12em] text-text-3 first:mt-0">
      {children}
    </div>
  );
}

function DefCell({ k, v, last }: { k: string; v: string; last?: boolean }) {
  return (
    <div className={cn("flex-1 px-1 py-2 text-center", !last && "border-r border-[rgba(232,193,90,0.1)]")}>
      <div className="text-[8px] uppercase tracking-[0.1em] text-text-3">{k}</div>
      <div className="mt-0.5 text-label font-medium text-gold">{v}</div>
    </div>
  );
}

// ── odczyty z arkusza ────────────────────────────────────────────────────────
function fmtSigned(n: number) {
  return (n >= 0 ? "+" : "") + n;
}
function readDefense(sheet: HeroSheet | undefined): {
  base: number;
  reduction: number;
  initiative: number;
  zone: string;
} {
  const s = (sheet ?? {}) as Record<string, unknown>;
  const def = (s.defense ?? {}) as Record<string, unknown>;
  const base = Number(def.base ?? def.ac ?? 10) || 10;
  const mods = ((s.stat_modifiers ?? {}) as Record<string, unknown>) || {};
  const dex = Number(mods.DEX ?? 0) || 0;
  return {
    base,
    reduction: Math.max(0, base - 10),
    initiative: dex,
    zone: String(s.zone ?? "").toUpperCase() === "RANGED" ? "DYSTANS" : "ZWARCIE",
  };
}
function readCarry(sheet: HeroSheet | undefined): string {
  const s = (sheet ?? {}) as Record<string, unknown>;
  const cur = s.carry_weight ?? s.weight_current;
  const max = s.carry_capacity ?? s.weight_max;
  if (cur == null && max == null) return "—";
  return `${Number(cur ?? 0)}/${Number(max ?? 0)}`;
}
