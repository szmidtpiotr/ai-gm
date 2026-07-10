// F-55/F-76/F-78 · Ekwipunek — sylwetka Diablo-overlap, plecak jako wąskie paski
// grupowane jak w starym frontendzie: Zużywalne / Sprzęt i broń / Fabularne.
// Klik na rząd → modal ze zdjęciem + opisem. Inline: Załóż/Użyj + ✕ usuń.
// Stacking: identyczne itemy (ten sam key) scalane w jeden rząd z sumą qty.
// Modal: Załóż/Zdejmij (z live listy), Użyj, Usuń.
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
  groupBackpack,
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
  useUseItem,
  useDropItem,
  type InventoryItemDetail,
} from "@/hooks/useSheetData";

// ── Stacking identycznych itemów ─────────────────────────────────────────────
interface StackedItem extends InventoryItem {
  allIds: number[];   // wszystkie inventory_id w stosie (drop usuwa pierwszy)
  totalQty: number;   // suma quantity
}

function stackItems(items: InventoryItem[]): StackedItem[] {
  const map = new Map<string, StackedItem>();
  for (const it of items) {
    // Klucz stosu: key > label (dla narrative items bez key)
    const stackKey = (it.label || it.key || String(it.id)).toLowerCase().trim();
    if (map.has(stackKey)) {
      const ex = map.get(stackKey)!;
      ex.allIds.push(it.id);
      ex.totalQty += it.quantity || 1;
    } else {
      map.set(stackKey, { ...it, allIds: [it.id], totalQty: it.quantity || 1 });
    }
  }
  return [...map.values()];
}

const DOLL_POS: Record<string, { top: string; left: string; small?: boolean }> = {
  head: { top: "11%", left: "50%" },
  amulet: { top: "25%", left: "50%", small: true },
  chest: { top: "39%", left: "50%" },
  main_hand: { top: "41%", left: "15%" },
  off_hand: { top: "41%", left: "85%" },
  hands: { top: "57%", left: "81%" },
  legs: { top: "63%", left: "50%" },
  feet: { top: "87%", left: "50%" },
  // #1302: sloty reliktów po bokach nóg (małe).
  relic1: { top: "75%", left: "19%", small: true },
  relic2: { top: "75%", left: "81%", small: true },
};

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

  const useItem = useUseItem(characterId);
  const dropItem = useDropItem(characterId);

  const v = readVitals(sheet);
  const { equipped, backpack } = splitInventory(items ?? []);
  const bag = groupBackpack(backpack);
  const defense = readDefense(sheet);
  const carry = readCarry(sheet);

  const actionBusy = busy || useItem.isPending || dropItem.isPending;

  // Equip/unequip: read state from live list item (not stale detail cache)
  function handleEquipFromModal(inventoryId: number) {
    const item = items?.find((i) => i.id === inventoryId);
    if (!item) return;
    if (item.equipped) {
      onEquip(inventoryId, null);
    } else {
      const slot = targetSlotFor(item);
      if (slot) onEquip(inventoryId, slot);
    }
    setSelectedId(null);
  }

  function handleUse(inventoryId: number) {
    useItem.mutate(inventoryId, { onSuccess: () => setSelectedId(null) });
  }

  function handleDrop(inventoryId: number) {
    dropItem.mutate(inventoryId, { onSuccess: () => setSelectedId(null) });
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

  return (
    <>
      <PanelScroll>
        {/* Sakiewka */}
        <div className="mb-4 flex gap-2">
          <Pouch icon={<Coins weight="fill" size={18} className="text-gold" />} k="Złoto" val={`${v.gold} gp`} />
          <Pouch icon={<Scales size={18} className="text-gold" />} k="Udźwig" val={carry} />
        </div>

        {/* Na ciele */}
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
            <Doll equipped={equipped} onSelect={setSelectedId} busy={actionBusy} />
          ) : (
            <EquippedList equipped={equipped} onSelect={setSelectedId} busy={actionBusy} />
          )}

          <div className="mx-auto mt-3.5 flex max-w-[340px] overflow-hidden rounded-md border border-line-mech bg-mech-card font-mono lg:max-w-none">
            <DefCell k="Redukcja" v={String(defense.reduction)} />
            <DefCell k="Obrona" v={String(defense.base)} />
            <DefCell k="Inicjat." v={fmtSigned(defense.initiative)} />
            <DefCell k="Zasięg" v={defense.zone} last />
          </div>
        </section>

        {/* Plecak */}
        <section>
          <SecHead>
            Plecak{" "}
            <span className="font-normal normal-case tracking-normal text-text-3">
              {backpack.length} rzeczy
            </span>
          </SecHead>

          {backpack.length === 0 && (
            <p className="mt-2 rounded-md border border-line-soft bg-surface px-3.5 py-3 font-serif text-label text-text-3">
              Plecak jest pusty.
            </p>
          )}

          {bag.consumables.length > 0 && (
            <BagSection
              label="Zużywalne"
              items={bag.consumables}
              onSelect={setSelectedId}
              onEquip={onEquip}
              onUse={handleUse}
              onDrop={handleDrop}
              busy={actionBusy}
            />
          )}
          {bag.gear.length > 0 && (
            <BagSection
              label="Sprzęt i broń"
              items={bag.gear}
              onSelect={setSelectedId}
              onEquip={onEquip}
              onUse={handleUse}
              onDrop={handleDrop}
              busy={actionBusy}
            />
          )}
          {bag.lore.length > 0 && (
            <LoreSection items={bag.lore} onSelect={setSelectedId} onDrop={handleDrop} />
          )}
        </section>
      </PanelScroll>

      {selectedId !== null && (
        <ItemDetailModal
          characterId={characterId}
          inventoryId={selectedId}
          listItem={items?.find((i) => i.id === selectedId)}
          busy={actionBusy}
          onClose={() => setSelectedId(null)}
          onEquip={handleEquipFromModal}
          onUse={handleUse}
          onDrop={handleDrop}
        />
      )}
    </>
  );
}

// ── Sekcja plecaka ───────────────────────────────────────────────────────────
function BagSection({
  label,
  items,
  onSelect,
  onEquip,
  onUse,
  onDrop,
  busy,
}: {
  label: string;
  items: InventoryItem[];
  onSelect: (id: number) => void;
  onEquip: (id: number, slot: string | null) => void;
  onUse: (id: number) => void;
  onDrop: (id: number) => void;
  busy: boolean;
}) {
  const stacked = stackItems(items);
  return (
    <div className="mb-4 mt-3 first:mt-2">
      <div className="mb-1.5 font-ui text-[10px] font-semibold uppercase tracking-[0.12em] text-text-3">
        {label}
      </div>
      <div className="flex flex-col gap-1">
        {stacked.map((it) => (
          <ItemRow key={it.id} it={it} onSelect={onSelect} onEquip={onEquip} onUse={onUse} onDrop={onDrop} busy={busy} />
        ))}
      </div>
    </div>
  );
}

function ItemRow({
  it,
  onSelect,
  onEquip,
  onUse,
  onDrop,
  busy,
}: {
  it: StackedItem;
  onSelect: (id: number) => void;
  onEquip: (id: number, slot: string | null) => void;
  onUse: (id: number) => void;
  onDrop: (id: number) => void;
  busy: boolean;
}) {
  const Icon = itemIcon(it);
  const dur = it.durability;
  const slot = targetSlotFor(it);
  const canEquipInline = !!slot;
  const canUseInline = !!it.can_use;
  const isQuest = it.item_type === "quest";

  return (
    <div className="flex items-center gap-1 rounded-md border border-line bg-surface transition-colors hover:border-line-ember">
      {/* Klikalna lewa strona → modal */}
      <button
        type="button"
        disabled={busy}
        onClick={() => onSelect(it.id)}
        className="flex min-w-0 flex-1 items-center gap-3 px-3 py-2 text-left disabled:opacity-50"
      >
        <span className="flex h-8 w-8 shrink-0 items-center justify-center overflow-hidden rounded border border-line bg-bg text-text-3">
          {it.image_url ? (
            <img src={it.image_url} alt="" loading="lazy" className="h-full w-full object-cover" />
          ) : (
            <Icon size={16} />
          )}
        </span>
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
        {it.totalQty > 1 && (
          <span className="shrink-0 rounded border border-line bg-bg px-1.5 py-0.5 font-mono text-[10px] font-semibold text-text-2">
            ×{it.totalQty}
          </span>
        )}
      </button>

      {/* Inline akcja */}
      {canEquipInline && (
        <button
          type="button"
          disabled={busy}
          onClick={() => onEquip(it.id, slot)}
          className="shrink-0 rounded border border-ember/50 px-2.5 py-1 font-ui text-[11px] font-semibold text-ember-glow transition-colors hover:border-ember hover:bg-[rgba(255,122,61,0.12)] disabled:opacity-50"
        >
          Załóż
        </button>
      )}
      {canUseInline && !canEquipInline && (
        <button
          type="button"
          disabled={busy}
          onClick={() => onUse(it.id)}
          className="shrink-0 rounded border border-emerald-700/50 px-2.5 py-1 font-ui text-[11px] font-semibold text-emerald-400 transition-colors hover:bg-[rgba(16,185,129,0.1)] disabled:opacity-50"
        >
          Użyj
        </button>
      )}
      {/* ✕ usuń — zawsze widoczny poza quest */}
      {!isQuest && (
        <button
          type="button"
          disabled={busy}
          onClick={() => {
            const name = it.label;
            if (window.confirm(`Wyrzucić „${name}"? Tej operacji nie można cofnąć.`)) {
              onDrop(it.id);
            }
          }}
          title="Wyrzuć przedmiot"
          className="mr-1.5 shrink-0 px-1.5 py-1 text-text-3 transition-colors hover:text-danger disabled:opacity-50"
        >
          ✕
        </button>
      )}
    </div>
  );
}

// ── Przedmioty fabularne — podkategorie jak w starym frontendzie ─────────────
const LORE_SUBCATS: { key: string; label: string; test: RegExp }[] = [
  {
    key: "scrolls",
    label: "Zwoje i pergaminy",
    test: /pergamin|zwój|zwoj|list|pismo|manuskrypt|skrawek|świstek|swistek|kartka|notatka|wiadomość|wiadomosc|rozkaz|ulotka|liścik|liscik|doniesienie|raport|wypis|przepustka|zezwolenie|dokument/i,
  },
  {
    key: "books",
    label: "Księgi i traktaty",
    test: /księga|ksiega|książka|ksiazka|kodeks|kronika|traktat|tome|zapis|dziennik|pamiętnik|pamietnik|grimuar|grimoire|atlas|bestiariusz/i,
  },
  { key: "keys", label: "Klucze", test: /klucz/i },
  { key: "quest", label: "Przedmioty fabularne", test: /^$/ },
  { key: "misc", label: "Inne przedmioty", test: /^$/ },
];

function loreCatKey(it: InventoryItem): string {
  const lab = it.label || it.key || "";
  if (LORE_SUBCATS[0].test.test(lab)) return "scrolls";
  if (LORE_SUBCATS[1].test.test(lab)) return "books";
  if (LORE_SUBCATS[2].test.test(lab)) return "keys";
  if (it.item_type === "quest") return "quest";
  return "misc";
}

function LoreSection({ items, onSelect, onDrop }: { items: InventoryItem[]; onSelect: (id: number) => void; onDrop: (id: number) => void }) {
  // Rozdziel po podkategorii, stackuj w każdej
  const groups: Record<string, StackedItem[]> = {};
  for (const it of items) {
    const cat = loreCatKey(it);
    if (!groups[cat]) groups[cat] = [];
    const existing = groups[cat];
    const stackKey = (it.label || it.key || String(it.id)).toLowerCase().trim();
    const found = existing.find((s) => (s.label || s.key || "").toLowerCase().trim() === stackKey);
    if (found) {
      found.allIds.push(it.id);
      found.totalQty += it.quantity || 1;
    } else {
      existing.push({ ...it, allIds: [it.id], totalQty: it.quantity || 1 });
    }
  }

  const totalStacked = Object.values(groups).reduce((n, g) => n + g.length, 0);

  return (
    <div className="mb-4 mt-3">
      <div className="mb-1.5 font-ui text-[10px] font-semibold uppercase tracking-[0.12em] text-text-3">
        Fabularne <span className="font-normal normal-case tracking-normal">({totalStacked})</span>
      </div>
      <div className="flex flex-col gap-1.5">
        {LORE_SUBCATS.map(({ key, label }) => {
          const group = groups[key];
          if (!group?.length) return null;
          return (
            <details key={key} className="overflow-hidden rounded-md border border-line-soft bg-surface">
              <summary className="flex cursor-pointer list-none items-center gap-1.5 px-3 py-2.5 font-ui text-[10px] font-semibold uppercase tracking-[0.12em] text-text-3 [&::-webkit-details-marker]:hidden">
                {label}
                <span className="font-normal normal-case tracking-normal">({group.length})</span>
                <CaretDown size={11} className="ml-auto" />
              </summary>
              <div className="flex flex-col gap-0.5 p-1.5 pt-0">
                {group.map((it) => (
                  <div key={it.id} className="flex items-center gap-1 rounded border border-transparent hover:border-line-soft hover:bg-bg">
                    <button
                      type="button"
                      onClick={() => onSelect(it.id)}
                      className="flex min-w-0 flex-1 items-center gap-3 px-2.5 py-2 text-left"
                    >
                      <span className="flex h-7 w-7 shrink-0 items-center justify-center overflow-hidden rounded border border-line bg-bg text-text-3">
                        {it.image_url ? (
                          <img src={it.image_url} alt="" loading="lazy" className="h-full w-full object-cover" />
                        ) : (
                          <Info size={13} />
                        )}
                      </span>
                      <span className="min-w-0 flex-1 truncate font-serif text-[12.5px] text-text-2">{it.label}</span>
                      {it.totalQty > 1 && (
                        <span className="shrink-0 font-mono text-[10px] text-text-3">×{it.totalQty}</span>
                      )}
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        if (window.confirm(`Wyrzucić „${it.label}"? Tej operacji nie można cofnąć.`)) {
                          onDrop(it.id);
                        }
                      }}
                      title="Wyrzuć przedmiot"
                      className="mr-1 shrink-0 px-1.5 py-1 text-text-3 transition-colors hover:text-danger"
                    >
                      ✕
                    </button>
                  </div>
                ))}
              </div>
            </details>
          );
        })}
      </div>
    </div>
  );
}

// ── Modal szczegółów ─────────────────────────────────────────────────────────
function ItemDetailModal({
  characterId,
  inventoryId,
  listItem,
  busy,
  onClose,
  onEquip,
  onUse,
  onDrop,
}: {
  characterId: number | undefined;
  inventoryId: number;
  listItem: InventoryItem | undefined;
  busy: boolean;
  onClose: () => void;
  onEquip: (id: number) => void;
  onUse: (id: number) => void;
  onDrop: (id: number) => void;
}) {
  const { data: detail, isLoading } = useInventoryDetail(characterId, inventoryId);

  // isEquipped read from live list (not stale detail cache)
  const isEquipped = !!(listItem?.equipped);
  const slot = listItem ? targetSlotFor(listItem) : null;
  const canEquip = !!slot || isEquipped;
  const canUse = !!(listItem?.can_use) && !isEquipped;
  const isQuest = listItem?.item_type === "quest";

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-black/70 backdrop-blur-sm sm:items-center"
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-sm rounded-t-2xl border border-line bg-surface p-5 shadow-modal sm:rounded-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <button type="button" onClick={onClose} className="absolute right-4 top-4 text-text-3 hover:text-text">
          <X size={20} />
        </button>

        {isLoading ? (
          <div className="flex items-center justify-center gap-2 py-10 text-text-3">
            <CircleNotch className="animate-spin" size={20} />
          </div>
        ) : detail ? (
          <ItemDetailBody
            detail={detail}
            canEquip={canEquip}
            canUse={canUse}
            isEquipped={isEquipped}
            isQuest={isQuest}
            busy={busy}
            onEquip={() => onEquip(inventoryId)}
            onUse={() => onUse(inventoryId)}
            onDrop={() => onDrop(inventoryId)}
          />
        ) : (
          <p className="py-8 text-center font-serif text-body text-text-3">Brak danych o przedmiocie.</p>
        )}
      </div>
    </div>
  );
}

function ItemDetailBody({
  detail,
  canEquip,
  canUse,
  isEquipped,
  isQuest,
  busy,
  onEquip,
  onUse,
  onDrop,
}: {
  detail: InventoryItemDetail;
  canEquip: boolean;
  canUse: boolean;
  isEquipped: boolean;
  isQuest: boolean;
  busy: boolean;
  onEquip: () => void;
  onUse: () => void;
  onDrop: () => void;
}) {
  return (
    <div className="flex flex-col gap-4">
      {/* Obraz + nagłówek */}
      <div className="flex gap-4">
        {detail.image_url ? (
          <img src={detail.image_url} alt={detail.name} className="h-24 w-24 shrink-0 rounded-lg border border-line object-cover shadow-md" />
        ) : (
          <div className="flex h-24 w-24 shrink-0 items-center justify-center rounded-lg border border-line bg-bg text-text-3">
            <Info size={32} />
          </div>
        )}
        <div className="min-w-0">
          <h2 className="font-serif text-title text-text">{detail.name}</h2>
          <div className="mt-1 flex flex-wrap gap-1.5">
            <KindBadge kind={detail.kind} />
            {detail.value_gp > 0 && (
              <span className="rounded border border-line bg-bg px-1.5 py-0.5 font-mono text-[10px] text-gold">{detail.value_gp} gp</span>
            )}
            {detail.quantity > 1 && (
              <span className="rounded border border-line bg-bg px-1.5 py-0.5 font-mono text-[10px] text-text-2">×{detail.quantity}</span>
            )}
          </div>
          {detail.weapon && (
            <div className="mt-2 font-mono text-[11px] text-text-2">
              {detail.weapon.damage_die && <span>obrażenia: <strong className="text-ember-glow">{detail.weapon.damage_die}</strong></span>}
              {detail.weapon.linked_stat && <span className="ml-2">cecha: {detail.weapon.linked_stat}</span>}
              {!!detail.weapon.attack_bonus && (
                <span className="ml-2">trafienie: {detail.weapon.attack_bonus > 0 ? "+" : ""}{detail.weapon.attack_bonus}</span>
              )}
            </div>
          )}
        </div>
      </div>

      {detail.description && (
        <p className="rounded-md border border-line-soft bg-bg px-3.5 py-3 font-serif text-[13px] leading-relaxed text-text-2">
          {detail.description}
        </p>
      )}

      {detail.note && (
        <div className="rounded-md border border-line-ember bg-[rgba(255,122,61,0.06)] px-3.5 py-3">
          <div className="mb-1 font-ui text-[9px] font-bold uppercase tracking-[0.12em] text-ember">Zdolności specjalne</div>
          <p className="font-serif text-[13px] leading-relaxed text-text-2">{detail.note}</p>
        </div>
      )}

      {detail.affixes && detail.affixes.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {detail.affixes.map((a) => (
            <span key={a.key} className="rounded border border-line bg-bg px-2 py-1 font-mono text-[10px] text-ember-glow">{a.label}</span>
          ))}
        </div>
      )}

      {detail.durability && (
        <div>
          <div className="mb-1 font-ui text-[9px] font-bold uppercase tracking-[0.12em] text-text-3">Trwałość</div>
          <div className="h-1.5 overflow-hidden rounded-full bg-line">
            <div className={cn("h-full rounded-full", detail.durability.pct < 40 ? "bg-danger" : "bg-ember")} style={{ width: `${detail.durability.pct}%` }} />
          </div>
          <div className="mt-1 font-mono text-[10px] text-text-3">
            {detail.durability.current}/{detail.durability.max}
            {detail.durability.broken && <span className="ml-2 text-danger">zepsuta</span>}
          </div>
        </div>
      )}

      {/* Akcje */}
      <div className="mt-1 flex flex-col gap-2">
        {canEquip && (
          <button
            type="button"
            disabled={busy}
            onClick={onEquip}
            className={cn(
              "w-full rounded-lg border px-4 py-2.5 font-ui text-[13px] font-semibold transition-colors disabled:opacity-50",
              isEquipped
                ? "border-line text-text-2 hover:border-ember hover:text-ember-glow"
                : "border-ember bg-[rgba(255,122,61,0.12)] text-ember-glow hover:bg-[rgba(255,122,61,0.2)]",
            )}
          >
            {isEquipped ? "Zdejmij" : "Załóż"}
          </button>
        )}
        {canUse && (
          <button
            type="button"
            disabled={busy}
            onClick={onUse}
            className="w-full rounded-lg border border-emerald-700/50 bg-[rgba(16,185,129,0.08)] px-4 py-2.5 font-ui text-[13px] font-semibold text-emerald-400 transition-colors hover:bg-[rgba(16,185,129,0.15)] disabled:opacity-50"
          >
            Użyj
          </button>
        )}
        {!isQuest && (
          <button
            type="button"
            disabled={busy}
            onClick={onDrop}
            className="w-full rounded-lg border border-line px-4 py-2.5 font-ui text-[13px] text-text-3 transition-colors hover:border-danger hover:text-danger disabled:opacity-50"
          >
            Usuń z ekwipunku
          </button>
        )}
      </div>
    </div>
  );
}

function KindBadge({ kind }: { kind: string }) {
  const labels: Record<string, string> = { weapon: "Broń", consumable: "Zużywalne", item: "Przedmiot", armor: "Zbroja" };
  return (
    <span className="rounded border border-line bg-bg px-1.5 py-0.5 font-ui text-[10px] text-text-3">{labels[kind] ?? kind}</span>
  );
}

// ── Sylwetka ─────────────────────────────────────────────────────────────────
function Doll({ equipped, onSelect, busy }: { equipped: EquippedMap; onSelect: (id: number) => void; busy: boolean }) {
  return (
    <div
      className="relative mx-auto w-full max-w-[340px] overflow-hidden rounded-lg border border-line lg:max-w-none"
      style={{ aspectRatio: "1 / 1.28", background: "radial-gradient(58% 42% at 50% 26%, rgba(255,122,61,.14), transparent 68%), linear-gradient(180deg,#241a11,#171009)" }}
    >
      <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
        <Person weight="fill" size={260} className="max-h-[80%] max-w-[80%] text-[rgba(255,190,140,0.16)]" />
      </div>
      {DOLL_SLOTS.map(({ slot, label }) => (
        <DollSlot key={slot} label={label} item={equipped[slot]} slot={slot} pos={DOLL_POS[slot]} onSelect={onSelect} busy={busy} />
      ))}
    </div>
  );
}

function DollSlot({ label, item, slot, pos, onSelect, busy }: {
  label: string; item: InventoryItem | undefined; slot: string;
  pos: { top: string; left: string; small?: boolean };
  onSelect: (id: number) => void; busy: boolean;
}) {
  const Icon = item ? itemIcon(item) : SLOT_ICON[slot];
  const dur = item?.durability;
  const size = pos.small ? 42 : 56;
  return (
    <button
      type="button"
      disabled={!item || busy}
      onClick={() => item && onSelect(item.id)}
      title={item ? `${item.label} — szczegóły` : `${label} (pusty)`}
      className={cn(
        "absolute flex -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-[11px] border shadow-[0_3px_12px_rgba(0,0,0,.55)] backdrop-blur-[1px] transition-colors",
        item ? "border-line bg-[rgba(20,15,10,0.72)] text-ember-glow hover:border-ember" : "border-dashed border-line bg-[rgba(20,15,10,0.4)] text-text-3 cursor-default",
      )}
      style={{ top: pos.top, left: pos.left, width: size, height: size }}
    >
      <span className="absolute -top-2 left-1/2 -translate-x-1/2 whitespace-nowrap bg-bg px-1 text-[7px] font-bold uppercase tracking-[0.1em] text-text-3">{label}</span>
      {item?.image_url ? (
        <img src={item.image_url} alt={item.label} className="h-full w-full rounded-[10px] object-cover" />
      ) : (
        Icon && <Icon size={pos.small ? 18 : 24} />
      )}
      {dur && (
        <span className="absolute inset-x-1.5 -bottom-[3px] h-[3px] overflow-hidden rounded-[2px] bg-[#3a2a1a]">
          <span className={cn("block h-full", dur.pct < 40 ? "bg-danger" : "bg-ember")} style={{ width: `${dur.pct}%` }} />
        </span>
      )}
    </button>
  );
}

function EquippedList({ equipped, onSelect, busy }: { equipped: EquippedMap; onSelect: (id: number) => void; busy: boolean }) {
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
              it ? "cursor-pointer border-line-soft bg-surface hover:border-line-ember" : "border-dashed border-line-soft bg-transparent opacity-50",
            )}
            onClick={() => it && !busy && onSelect(it.id)}
            role={it ? "button" : undefined}
          >
            <span className="flex h-8 w-8 shrink-0 items-center justify-center overflow-hidden rounded border border-line bg-bg text-ember-glow">
              {it?.image_url ? <img src={it.image_url} alt={it.label} className="h-full w-full object-cover" /> : Icon && <Icon size={16} />}
            </span>
            <div className="min-w-0 flex-1">
              <div className="text-[9px] font-bold uppercase tracking-[0.14em] text-text-3">{label}</div>
              <div className="truncate font-ui text-[13px] font-medium text-text">{it?.label ?? "— pusty —"}</div>
            </div>
            {it && <span className="shrink-0 font-ui text-[10px] text-text-3">›</span>}
          </div>
        );
      })}
    </div>
  );
}

// ── prymitywy ────────────────────────────────────────────────────────────────
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

function ToggleBtn({ on, onClick, children }: { on: boolean; onClick: () => void; children: React.ReactNode }) {
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

function fmtSigned(n: number) { return (n >= 0 ? "+" : "") + n; }

function readDefense(sheet: HeroSheet | undefined) {
  const s = (sheet ?? {}) as Record<string, unknown>;
  const def = (s.defense ?? {}) as Record<string, unknown>;
  // #1302: pasywne AC z założonego ekwipunku (equipment_bonuses.ac) — w walce i na karcie.
  const eq = (s.equipment_bonuses ?? {}) as Record<string, unknown>;
  const relicAc = Number(eq.ac ?? 0) || 0;
  const base = (Number(def.base ?? def.ac ?? 10) || 10) + relicAc;
  const mods = (s.stat_modifiers ?? {}) as Record<string, unknown>;
  const dex = Number(mods.DEX ?? 0) || 0;
  return { base, reduction: Math.max(0, base - 10), initiative: dex, relicAc, zone: String(s.zone ?? "").toUpperCase() === "RANGED" ? "DYSTANS" : "ZWARCIE" };
}

function readCarry(sheet: HeroSheet | undefined): string {
  const s = (sheet ?? {}) as Record<string, unknown>;
  const cur = s.carry_weight ?? s.weight_current;
  const max = s.carry_capacity ?? s.weight_max;
  if (cur == null && max == null) return "—";
  return `${Number(cur ?? 0)}/${Number(max ?? 0)}`;
}
