// F-55/F-76/F-78 · Ekwipunek — sylwetka Diablo-overlap (itemy nachodzą na ciało),
// toggle Sylwetka/Lista, plecak jako wąskie paski groupowane wg typu (broń/zbroja /
// zużywalne / przedmioty / fabularne). Klik → modal z obrazem + opisem z backendu.
// Makieta: zar5-ekwipunek.html.
import { useState } from "react";
import {
  CaretDown,
  CircleNotch,
  Coins,
  Info,
  ListBullets,
  Person,
  Scales,
  X,
} from "@phosphor-icons/react";
import { cn } from "@/lib/utils";
import {
  DOLL_SLOTS,
  splitInventory,
  targetSlotFor,
  type EquippedMap,
  type InventoryItem,
} from "@/lib/sheet";
import { readVitals } from "@/lib/game";
import type { HeroSheet } from "@/lib/types";
import { SecHead, PanelScroll, itemIcon, SLOT_ICON } from "./sheetUi";
import {
  useInventoryDetail,
  type InventoryItemDetail,
} from "@/hooks/useSheetData";

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

// ── Grupowanie plecaka wg item_type ─────────────────────────────────────────
const WEAPON_TYPES = new Set(["weapon"]);
const ARMOR_TYPES = new Set(["armor", "shield"]);
const CONSUMABLE_TYPES = new Set(["consumable", "potion", "food"]);
const LORE_TYPES = new Set(["quest", "map", "book", "note", "key", "scroll"]);

interface BagSections {
  weapons: InventoryItem[];
  armor: InventoryItem[];
  consumables: InventoryItem[];
  items: InventoryItem[];
  lore: InventoryItem[];
}

function groupByType(backpack: InventoryItem[]): BagSections {
  const weapons: InventoryItem[] = [];
  const armor: InventoryItem[] = [];
  const consumables: InventoryItem[] = [];
  const items: InventoryItem[] = [];
  const lore: InventoryItem[] = [];
  for (const it of backpack) {
    const t = (it.item_type || "").toLowerCase();
    if (WEAPON_TYPES.has(t)) weapons.push(it);
    else if (ARMOR_TYPES.has(t)) armor.push(it);
    else if (CONSUMABLE_TYPES.has(t)) consumables.push(it);
    else if (LORE_TYPES.has(t)) lore.push(it);
    else items.push(it);
  }
  return { weapons, armor, consumables, items, lore };
}

// ── Główny panel ─────────────────────────────────────────────────────────────
export function PanelInventory({
  sheet,
  items,
  loading,
  onEquip,
  busy,
  characterId,
}: {
  sheet: HeroSheet | undefined;
  items: InventoryItem[] | undefined;
  loading: boolean;
  onEquip: (inventoryId: number, slot: string | null) => void;
  busy: boolean;
  characterId: number | undefined;
}) {
  const [view, setView] = useState<"doll" | "list">("doll");
  const [selectedId, setSelectedId] = useState<number | null>(null);

  const v = readVitals(sheet);
  const { equipped, backpack } = splitInventory(items ?? []);
  const sections = groupByType(backpack);
  const defense = readDefense(sheet);
  const carry = readCarry(sheet);

  function handleEquipFromModal(detail: InventoryItemDetail) {
    if (detail.equipped) {
      onEquip(detail.id, null);
    } else {
      const item = items?.find((i) => i.id === detail.id);
      const slot = item ? targetSlotFor(item) : null;
      if (slot) onEquip(detail.id, slot);
    }
    setSelectedId(null);
  }

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

  const backpackCount = backpack.length;

  return (
    <>
      <PanelScroll>
        {/* Sakiewka: złoto + udźwig */}
        <div className="mb-4 flex gap-2">
          <Pouch icon={<Coins weight="fill" size={18} className="text-gold" />} k="Złoto" val={`${v.gold} gp`} />
          <Pouch icon={<Scales size={18} className="text-gold" />} k="Udźwig" val={carry} />
        </div>

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
            <Doll equipped={equipped} onSelect={setSelectedId} busy={busy} />
          ) : (
            <EquippedList equipped={equipped} onSelect={setSelectedId} busy={busy} />
          )}

          {/* Podsumowanie obrony */}
          <div className="mx-auto mt-3.5 flex max-w-[340px] overflow-hidden rounded-md border border-line-mech bg-mech-card font-mono lg:max-w-none">
            <DefCell k="Redukcja" v={String(defense.reduction)} />
            <DefCell k="Obrona" v={String(defense.base)} />
            <DefCell k="Inicjat." v={fmtSigned(defense.initiative)} />
            <DefCell k="Zasięg" v={defense.zone} last />
          </div>
        </section>

        {/* ── Plecak ── */}
        <section>
          <SecHead>
            Plecak{" "}
            <span className="font-normal normal-case tracking-normal text-text-3">
              {backpackCount} {backpackCount === 1 ? "rzecz" : "rzeczy"}
            </span>
          </SecHead>

          {backpackCount === 0 && (
            <p className="mt-2 rounded-md border border-line-soft bg-surface px-3.5 py-3 font-serif text-label text-text-3">
              Plecak jest pusty.
            </p>
          )}

          {sections.weapons.length > 0 && (
            <ItemSection label="Broń" items={sections.weapons} onSelect={setSelectedId} busy={busy} />
          )}
          {sections.armor.length > 0 && (
            <ItemSection label="Zbroja i tarcze" items={sections.armor} onSelect={setSelectedId} busy={busy} />
          )}
          {sections.consumables.length > 0 && (
            <ItemSection label="Zużywalne" items={sections.consumables} onSelect={setSelectedId} busy={busy} />
          )}
          {sections.items.length > 0 && (
            <ItemSection label="Przedmioty" items={sections.items} onSelect={setSelectedId} busy={busy} />
          )}
          {sections.lore.length > 0 && (
            <LoreSection items={sections.lore} onSelect={setSelectedId} />
          )}
        </section>
      </PanelScroll>

      {selectedId !== null && (
        <ItemDetailModal
          characterId={characterId}
          inventoryId={selectedId}
          items={items}
          busy={busy}
          onClose={() => setSelectedId(null)}
          onEquip={handleEquipFromModal}
        />
      )}
    </>
  );
}

// ── Sekcja plecaka (wąskie paski) ────────────────────────────────────────────
function ItemSection({
  label,
  items,
  onSelect,
  busy,
}: {
  label: string;
  items: InventoryItem[];
  onSelect: (id: number) => void;
  busy: boolean;
}) {
  return (
    <div className="mb-4">
      <div className="mb-1.5 mt-3 font-ui text-[10px] font-semibold uppercase tracking-[0.12em] text-text-3 first:mt-0">
        {label}
      </div>
      <div className="flex flex-col gap-1">
        {items.map((it) => (
          <ItemRow key={it.id} it={it} onSelect={onSelect} busy={busy} />
        ))}
      </div>
    </div>
  );
}

function ItemRow({
  it,
  onSelect,
  busy,
}: {
  it: InventoryItem;
  onSelect: (id: number) => void;
  busy: boolean;
}) {
  const Icon = itemIcon(it);
  const dur = it.durability;
  return (
    <button
      type="button"
      disabled={busy}
      onClick={() => onSelect(it.id)}
      title={it.label}
      className="flex w-full cursor-pointer items-center gap-3 rounded-md border border-line bg-surface px-3 py-2 text-left transition-colors hover:border-line-ember hover:bg-[rgba(255,122,61,0.04)] disabled:opacity-50"
    >
      {/* Miniaturka 32×32 */}
      <span className="flex h-8 w-8 shrink-0 items-center justify-center overflow-hidden rounded border border-line bg-bg text-text-3">
        {it.image_url ? (
          <img src={it.image_url} alt="" loading="lazy" className="h-full w-full object-cover" />
        ) : (
          <Icon size={16} />
        )}
      </span>

      {/* Nazwa */}
      <span className="min-w-0 flex-1">
        <span className="block truncate font-ui text-[13px] font-medium text-text">
          {it.label}
        </span>
        {dur && (
          <span className="mt-1 block h-[3px] w-full overflow-hidden rounded-full bg-line">
            <span
              className={cn("block h-full rounded-full", dur.pct < 40 ? "bg-danger" : "bg-ember-glow")}
              style={{ width: `${dur.pct}%` }}
            />
          </span>
        )}
      </span>

      {/* Liczba sztuk */}
      {it.quantity > 1 && (
        <span className="shrink-0 rounded border border-line bg-bg px-1.5 py-0.5 font-mono text-[10px] font-semibold text-text-2">
          ×{it.quantity}
        </span>
      )}
    </button>
  );
}

// ── Przedmioty fabularne (collapsible) ───────────────────────────────────────
function LoreSection({
  items,
  onSelect,
}: {
  items: InventoryItem[];
  onSelect: (id: number) => void;
}) {
  return (
    <div className="mb-4">
      <details className="overflow-hidden rounded-md border border-line-soft bg-surface">
        <summary className="flex cursor-pointer list-none items-center gap-2.5 px-3 py-2.5 font-ui text-[10px] font-semibold uppercase tracking-[0.12em] text-text-3 [&::-webkit-details-marker]:hidden">
          Fabularne
          <span className="ml-1 font-normal normal-case tracking-normal text-text-3">
            ({items.length})
          </span>
          <CaretDown size={11} className="ml-auto text-text-3" />
        </summary>
        <div className="flex flex-col gap-1 p-1.5 pt-0">
          {items.map((it) => (
            <button
              key={it.id}
              type="button"
              onClick={() => onSelect(it.id)}
              className="flex items-center gap-3 rounded border border-transparent px-2.5 py-2 text-left hover:border-line-soft hover:bg-bg"
            >
              <span className="flex h-7 w-7 shrink-0 items-center justify-center overflow-hidden rounded border border-line bg-bg text-text-3">
                {it.image_url ? (
                  <img src={it.image_url} alt="" loading="lazy" className="h-full w-full object-cover" />
                ) : (
                  <Info size={13} />
                )}
              </span>
              <span className="min-w-0 flex-1 truncate font-serif text-[12.5px] text-text-2">
                {it.label}
              </span>
              {it.quantity > 1 && (
                <span className="shrink-0 font-mono text-[10px] text-text-3">×{it.quantity}</span>
              )}
            </button>
          ))}
        </div>
      </details>
    </div>
  );
}

// ── Modal szczegółów przedmiotu ──────────────────────────────────────────────
function ItemDetailModal({
  characterId,
  inventoryId,
  items,
  busy,
  onClose,
  onEquip,
}: {
  characterId: number | undefined;
  inventoryId: number;
  items: InventoryItem[] | undefined;
  busy: boolean;
  onClose: () => void;
  onEquip: (detail: InventoryItemDetail) => void;
}) {
  const { data: detail, isLoading } = useInventoryDetail(characterId, inventoryId);
  const item = items?.find((i) => i.id === inventoryId);
  const slot = item ? targetSlotFor(item) : null;
  const isEquipped = !!(detail?.equipped);
  const canEquip = !!slot || isEquipped;

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-black/70 backdrop-blur-sm sm:items-center"
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-sm rounded-t-2xl border border-line bg-surface p-5 shadow-modal sm:rounded-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <button
          type="button"
          onClick={onClose}
          className="absolute right-4 top-4 text-text-3 hover:text-text"
          aria-label="Zamknij"
        >
          <X size={20} />
        </button>

        {isLoading ? (
          <div className="flex items-center justify-center gap-2 py-10 text-text-3">
            <CircleNotch className="animate-spin" size={20} />
            <span className="font-ui text-body">Ładowanie…</span>
          </div>
        ) : detail ? (
          <ItemDetailBody
            detail={detail}
            canEquip={canEquip}
            isEquipped={isEquipped}
            busy={busy}
            onEquip={onEquip}
          />
        ) : (
          <p className="py-8 text-center font-serif text-body text-text-3">
            Brak danych o przedmiocie.
          </p>
        )}
      </div>
    </div>
  );
}

function ItemDetailBody({
  detail,
  canEquip,
  isEquipped,
  busy,
  onEquip,
}: {
  detail: InventoryItemDetail;
  canEquip: boolean;
  isEquipped: boolean;
  busy: boolean;
  onEquip: (d: InventoryItemDetail) => void;
}) {
  return (
    <div className="flex flex-col gap-4">
      {/* Obrazek + tytuł */}
      <div className="flex gap-4">
        {detail.image_url ? (
          <img
            src={detail.image_url}
            alt={detail.name}
            className="h-24 w-24 shrink-0 rounded-lg border border-line object-cover shadow-md"
          />
        ) : (
          <div className="flex h-24 w-24 shrink-0 items-center justify-center rounded-lg border border-line bg-bg text-text-3">
            <Info size={32} />
          </div>
        )}
        <div className="min-w-0">
          <h2 className="font-serif text-title text-text">{detail.name}</h2>
          <div className="mt-1 flex flex-wrap gap-1.5">
            <ItemKindBadge kind={detail.kind} />
            {detail.value_gp > 0 && (
              <span className="rounded border border-line bg-bg px-1.5 py-0.5 font-mono text-[10px] text-gold">
                {detail.value_gp} gp
              </span>
            )}
            {detail.quantity > 1 && (
              <span className="rounded border border-line bg-bg px-1.5 py-0.5 font-mono text-[10px] text-text-2">
                ×{detail.quantity}
              </span>
            )}
          </div>
          {detail.weapon && (
            <div className="mt-2 font-mono text-[11px] text-text-2">
              {detail.weapon.damage_die && (
                <span>obrażenia: <strong className="text-ember-glow">{detail.weapon.damage_die}</strong></span>
              )}
              {detail.weapon.linked_stat && (
                <span className="ml-2">cecha: {detail.weapon.linked_stat}</span>
              )}
              {!!detail.weapon.attack_bonus && (
                <span className="ml-2">
                  trafienie: {detail.weapon.attack_bonus > 0 ? "+" : ""}{detail.weapon.attack_bonus}
                </span>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Opis fabularny */}
      {detail.description && (
        <p className="rounded-md border border-line-soft bg-bg px-3.5 py-3 font-serif text-[13px] leading-relaxed text-text-2">
          {detail.description}
        </p>
      )}

      {/* Nota (zdolności specjalne) */}
      {detail.note && (
        <div className="rounded-md border border-line-ember bg-[rgba(255,122,61,0.06)] px-3.5 py-3">
          <div className="mb-1 font-ui text-[9px] font-bold uppercase tracking-[0.12em] text-ember">
            Zdolności specjalne
          </div>
          <p className="font-serif text-[13px] leading-relaxed text-text-2">{detail.note}</p>
        </div>
      )}

      {/* Afiksy */}
      {detail.affixes && detail.affixes.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {detail.affixes.map((a) => (
            <span
              key={a.key}
              className="rounded border border-line bg-bg px-2 py-1 font-mono text-[10px] text-ember-glow"
            >
              {a.label}
            </span>
          ))}
        </div>
      )}

      {/* Trwałość */}
      {detail.durability && (
        <div>
          <div className="mb-1 font-ui text-[9px] font-bold uppercase tracking-[0.12em] text-text-3">
            Trwałość
          </div>
          <div className="h-1.5 overflow-hidden rounded-full bg-line">
            <div
              className={cn(
                "h-full rounded-full transition-all",
                detail.durability.pct < 40 ? "bg-danger" : "bg-ember",
              )}
              style={{ width: `${detail.durability.pct}%` }}
            />
          </div>
          <div className="mt-1 font-mono text-[10px] text-text-3">
            {detail.durability.current}/{detail.durability.max}
            {detail.durability.broken && (
              <span className="ml-2 text-danger">zepsuta</span>
            )}
          </div>
        </div>
      )}

      {/* Akcja */}
      {canEquip && (
        <button
          type="button"
          disabled={busy}
          onClick={() => onEquip(detail)}
          className={cn(
            "mt-1 w-full rounded-lg border px-4 py-2.5 font-ui text-[13px] font-semibold transition-colors disabled:opacity-50",
            isEquipped
              ? "border-line text-text-2 hover:border-ember hover:text-ember-glow"
              : "border-ember bg-[rgba(255,122,61,0.12)] text-ember-glow hover:bg-[rgba(255,122,61,0.2)]",
          )}
        >
          {isEquipped ? "Zdejmij" : "Załóż"}
        </button>
      )}
    </div>
  );
}

function ItemKindBadge({ kind }: { kind: string }) {
  const labels: Record<string, string> = {
    weapon: "Broń",
    consumable: "Zużywalne",
    item: "Przedmiot",
    armor: "Zbroja",
  };
  return (
    <span className="rounded border border-line bg-bg px-1.5 py-0.5 font-ui text-[10px] text-text-3">
      {labels[kind] ?? kind}
    </span>
  );
}

// ── Sylwetka (Diablo-overlap) ────────────────────────────────────────────────
function Doll({
  equipped,
  onSelect,
  busy,
}: {
  equipped: EquippedMap;
  onSelect: (id: number) => void;
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
            onSelect={onSelect}
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
  onSelect,
  busy,
}: {
  label: string;
  item: InventoryItem | undefined;
  slot: string;
  pos: { top: string; left: string; small?: boolean };
  onSelect: (id: number) => void;
  busy: boolean;
}) {
  const Icon = item ? itemIcon(item) : SLOT_ICON[slot];
  const dur = item?.durability;
  const size = pos.small ? 42 : 56;
  return (
    <button
      type="button"
      disabled={!item || busy}
      onClick={() => item && onSelect(item.id)}
      title={item ? `${item.label} — kliknij, by zobaczyć szczegóły` : `${label} (pusty)`}
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
      {item?.image_url ? (
        <img src={item.image_url} alt={item.label} className="h-full w-full rounded-[10px] object-cover" />
      ) : (
        Icon && <Icon size={pos.small ? 18 : 24} weight="regular" />
      )}
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
  onSelect,
}: {
  equipped: EquippedMap;
  onSelect: (id: number) => void;
  busy: boolean;
}) {
  return (
    <div className="flex flex-col gap-1">
      {DOLL_SLOTS.map(({ slot, label }) => {
        const it = equipped[slot];
        const Icon = it ? itemIcon(it) : SLOT_ICON[slot];
        return (
          <div
            key={slot}
            className={cn(
              "flex items-center gap-3 rounded-md border px-3 py-2",
              it
                ? "cursor-pointer border-line-soft bg-surface hover:border-line-ember"
                : "border-dashed border-line-soft bg-transparent opacity-50",
            )}
            onClick={() => it && onSelect(it.id)}
            role={it ? "button" : undefined}
          >
            <span className="flex h-8 w-8 shrink-0 items-center justify-center overflow-hidden rounded border border-line bg-bg text-ember-glow">
              {it?.image_url ? (
                <img src={it.image_url} alt={it.label} className="h-full w-full object-cover" />
              ) : (
                Icon && <Icon size={16} />
              )}
            </span>
            <div className="min-w-0 flex-1">
              <div className="text-[9px] font-bold uppercase tracking-[0.14em] text-text-3">{label}</div>
              <div className="truncate font-ui text-[13px] font-medium text-text">{it?.label ?? "— pusty —"}</div>
            </div>
            {it && (
              <span className="shrink-0 font-ui text-[10px] text-text-3">›</span>
            )}
          </div>
        );
      })}
    </div>
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
