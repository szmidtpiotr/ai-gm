// FE12 Sklep / NPC (#1261 / F-57) — overlay handlu wg makiety zar9-sklep.html.
// Nagłówek kupca (imię + kwestia + złoto gracza), zakładki Kup/Sprzedaj, siatka
// towarów (ikona/nazwa/opis/cena/rzadkość), blokada „Za mało" gdy brak złota.
// Otwierany narracyjnie (store.shop) — integruje się z ekwipunkiem (invalidacja).
import { useState } from "react";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import {
  Bread,
  CircleNotch,
  Coins,
  Drop,
  Flask,
  Knife,
  MagicWand,
  Scroll,
  Shield,
  ShieldStar,
  Sword,
  User,
  X,
  type Icon,
} from "@phosphor-icons/react";
import { cn } from "@/lib/utils";
import { useAppStore } from "@/store/appStore";
import { useShop, useBuyItem, useSellItem } from "@/hooks/useShop";
import { isRareGood, type ShopBuyItem, type ShopSellItem } from "@/lib/shop";
import { useToast } from "@/components/ui/toast";

export function ShopOverlay() {
  const shop = useAppStore((s) => s.shop);
  const closeShop = useAppStore((s) => s.closeShop);
  const characterId = useAppStore((s) => s.currentHeroId) ?? undefined;

  const open = !!shop;
  return (
    <DialogPrimitive.Root open={open} onOpenChange={(o) => !o && closeShop()}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm animate-fade-in" />
        <DialogPrimitive.Content
          className="fixed left-1/2 top-1/2 z-50 flex max-h-[92vh] w-[calc(100%-1.5rem)] max-w-[820px] -translate-x-1/2 -translate-y-1/2 flex-col overflow-hidden rounded-xl border border-line bg-bg shadow-modal animate-fade-in"
          aria-describedby={undefined}
        >
          {shop && characterId ? (
            <ShopBody npcKey={shop.npcKey} greeting={shop.greeting} characterId={characterId} onClose={closeShop} />
          ) : (
            <div className="flex items-center justify-center gap-2 p-10 text-text-3">
              <CircleNotch className="animate-spin" size={20} />
            </div>
          )}
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}

function ShopBody({
  npcKey,
  greeting,
  characterId,
  onClose,
}: {
  npcKey: string;
  greeting?: string | null;
  characterId: number;
  onClose: () => void;
}) {
  const [tab, setTab] = useState<"buy" | "sell">("buy");
  const { toast } = useToast();
  const shop = useShop(npcKey, characterId);
  const buy = useBuyItem(npcKey, characterId);
  const sell = useSellItem(npcKey, characterId);

  const data = shop.data;
  const gold = data?.character_gold ?? 0;
  const haggle = Number(data?.haggle_discount ?? 0);

  function onBuy(it: ShopBuyItem) {
    if (!data) return;
    buy.mutate(
      { npcId: data.npc.id, characterId, itemType: it.type, itemKey: it.key },
      {
        onSuccess: (r) => toast(`Kupiono: ${it.label} za ${r.data.paid_gp} zł`, "success"),
        onError: (e) => toast(e instanceof Error ? e.message : "Błąd zakupu", "danger"),
      },
    );
  }
  function onSell(it: ShopSellItem) {
    if (!data) return;
    sell.mutate(
      { npcId: data.npc.id, characterId, inventoryId: it.inventory_id },
      {
        onSuccess: (r) =>
          r.data.oversupply
            ? toast(`Cena obniżona (nadpodaż): ${it.label} za ${r.data.earned_gp} zł`, "info")
            : toast(`Sprzedano: ${it.label} za ${r.data.earned_gp} zł`, "success"),
        onError: (e) => toast(e instanceof Error ? e.message : "Błąd sprzedaży", "danger"),
      },
    );
  }

  return (
    <>
      {/* ── Nagłówek kupca ── */}
      <header className="flex items-center gap-3 border-b border-line bg-gradient-to-r from-[rgba(255,122,61,0.08)] to-surface px-4 py-3.5">
        <div className="flex h-12 w-12 flex-none items-center justify-center rounded-xl border border-line-ember bg-[radial-gradient(circle_at_40%_35%,rgba(255,122,61,0.25),#241c13)] text-ember-glow">
          <User weight="fill" size={24} />
        </div>
        <div className="min-w-0 flex-1">
          <DialogPrimitive.Title className="truncate font-serif text-title font-semibold text-text">
            {data?.npc.label ?? "Kupiec"}
          </DialogPrimitive.Title>
          {greeting && (
            <div className="mt-0.5 truncate font-serif text-micro italic text-text-2">„{greeting}"</div>
          )}
        </div>
        <div className="flex flex-none items-center gap-1.5 rounded-pill border border-line bg-bg px-3 py-1.5 font-mono text-label font-semibold text-gold">
          <Coins weight="fill" size={14} /> {gold}
        </div>
        <button
          onClick={onClose}
          aria-label="Zamknij"
          className="flex h-9 w-9 flex-none items-center justify-center rounded-md border border-line bg-bg text-text-2 hover:border-line-ember hover:text-ember-glow"
        >
          <X size={16} />
        </button>
      </header>

      {/* badge targowania (jednorazowy rabat/narzut) */}
      {haggle !== 0 && (
        <div
          className={cn(
            "mx-4 mt-2.5 rounded-md border px-2.5 py-1.5 text-micro font-semibold",
            haggle > 0
              ? "border-[rgba(168,201,131,0.35)] bg-[rgba(168,201,131,0.12)] text-success"
              : "border-line-danger bg-[rgba(232,96,79,0.12)] text-danger",
          )}
        >
          {haggle > 0
            ? `Utargowano −${Math.round(haggle * 100)}% (jednorazowo)`
            : `+${Math.round(-haggle * 100)}% — kupiec urażony`}
        </div>
      )}

      {/* ── Zakładki Kup / Sprzedaj ── */}
      <div className="flex gap-0.5 border-b border-line bg-surface px-3">
        <TabBtn on={tab === "buy"} onClick={() => setTab("buy")}>
          Kup
        </TabBtn>
        <TabBtn on={tab === "sell"} onClick={() => setTab("sell")}>
          Sprzedaj
        </TabBtn>
      </div>

      {/* ── Treść ── */}
      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-3.5 [scrollbar-width:thin]">
        {shop.isLoading ? (
          <Loading />
        ) : shop.isError || !data ? (
          <Empty>Handlarz nie ma teraz nic dla Ciebie.</Empty>
        ) : tab === "buy" ? (
          <BuyGrid items={data.items} gold={gold} busy={buy.isPending} onBuy={onBuy} />
        ) : (
          <SellList items={data.sell_items} busy={sell.isPending} onSell={onSell} />
        )}
      </div>
    </>
  );
}

// ── Zakładka Kup — siatka towarów ────────────────────────────────────────────
function BuyGrid({
  items,
  gold,
  busy,
  onBuy,
}: {
  items: ShopBuyItem[];
  gold: number;
  busy: boolean;
  onBuy: (it: ShopBuyItem) => void;
}) {
  if (!items.length) return <Empty>Handlarz nie ma nic na sprzedaż.</Empty>;
  return (
    <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3">
      {items.map((it) => {
        const rare = isRareGood(it);
        const Ico = goodsIcon(it.type, it.key);
        const afford = gold >= it.buy_price_gp;
        return (
          <div
            key={`${it.type}:${it.key}`}
            className={cn(
              "flex flex-col rounded-xl border bg-mech-card p-3",
              rare ? "border-[rgba(181,140,240,0.5)]" : "border-line",
            )}
          >
            <div className="flex items-center gap-2.5">
              <span
                className={cn(
                  "flex h-10 w-10 flex-none items-center justify-center rounded-lg border",
                  rare
                    ? "border-[rgba(181,140,240,0.4)] bg-[rgba(181,140,240,0.12)] text-rare"
                    : "border-line bg-[rgba(255,122,61,0.08)] text-ember-glow",
                )}
              >
                <Ico weight="fill" size={20} />
              </span>
              <div className={cn("min-w-0 text-label font-semibold leading-tight", rare && "text-rare")}>
                {it.label}
                {rare && " ◆"}
              </div>
            </div>
            {it.description && (
              <div className="mt-2.5 font-mono text-[10px] leading-relaxed text-text-3 line-clamp-2">
                {it.description}
              </div>
            )}
            <div className="mt-auto flex items-center gap-2 pt-3">
              <div className="flex flex-1 items-center gap-1.5 font-mono text-label font-semibold text-gold">
                <Coins weight="fill" size={14} />
                {it.buy_price_gp}
              </div>
              <button
                type="button"
                disabled={!afford || busy}
                onClick={() => onBuy(it)}
                className={cn(
                  "rounded-md px-3.5 py-2 font-ui text-micro font-semibold transition-colors",
                  afford
                    ? "bg-gradient-to-br from-[#d1602c] to-ember text-white hover:brightness-110"
                    : "cursor-not-allowed border border-line bg-bg text-text-3",
                  busy && "opacity-60",
                )}
              >
                {afford ? "Kup" : "Za mało"}
              </button>
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ── Zakładka Sprzedaj — lista rzeczy gracza ──────────────────────────────────
function SellList({
  items,
  busy,
  onSell,
}: {
  items: ShopSellItem[];
  busy: boolean;
  onSell: (it: ShopSellItem) => void;
}) {
  if (!items.length) return <Empty>Nie masz nic do sprzedania.</Empty>;
  return (
    <div className="flex flex-col gap-2">
      {items.map((it) => {
        const Ico = goodsIcon(it.item_type, it.key);
        const canSell = it.sell_price_gp > 0;
        return (
          <div
            key={it.inventory_id}
            className="flex items-center gap-3 rounded-xl border border-line bg-mech-card p-3"
          >
            <span className="flex h-10 w-10 flex-none items-center justify-center rounded-lg border border-line bg-[rgba(255,122,61,0.08)] text-ember-glow">
              <Ico weight="fill" size={20} />
            </span>
            <div className="min-w-0 flex-1">
              <div className="truncate text-label font-semibold text-text">
                {it.label}
                {it.quantity > 1 && <span className="text-text-3"> ×{it.quantity}</span>}
              </div>
              <div className="mt-0.5 flex items-center gap-1 font-mono text-[11px] text-gold">
                <Coins weight="fill" size={12} /> +{it.sell_price_gp}
              </div>
            </div>
            <button
              type="button"
              disabled={!canSell || busy}
              onClick={() => onSell(it)}
              className={cn(
                "flex-none rounded-md border px-3.5 py-2 font-ui text-micro font-semibold transition-colors",
                canSell
                  ? "border-line text-text-2 hover:border-line-ember hover:text-ember-glow"
                  : "cursor-not-allowed border-line text-text-3",
                busy && "opacity-60",
              )}
            >
              {canSell ? "Sprzedaj" : "—"}
            </button>
          </div>
        );
      })}
    </div>
  );
}

// ── prymitywy ────────────────────────────────────────────────────────────────
function TabBtn({ on, onClick, children }: { on: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "flex-1 border-b-2 px-1 pb-2.5 pt-3 text-center font-ui text-label font-semibold transition-colors",
        on ? "border-ember text-ember-glow" : "border-transparent text-text-3 hover:text-text-2",
      )}
    >
      {children}
    </button>
  );
}

function Loading() {
  return (
    <div className="flex items-center justify-center gap-2 py-14 text-text-3">
      <CircleNotch className="animate-spin" size={20} />
      <span className="font-ui text-body">Kupiec rozkłada towar…</span>
    </div>
  );
}

function Empty({ children }: { children: React.ReactNode }) {
  return (
    <p className="rounded-md border border-line-soft bg-surface px-4 py-8 text-center font-serif text-body text-text-3">
      {children}
    </p>
  );
}

// Ikona towaru z type/key (sklep nie zwraca ikon) — parytet z makietą.
function goodsIcon(type: string, key: string): Icon {
  const t = (type || "").toLowerCase();
  const k = (key || "").toLowerCase();
  if (k.includes("mana")) return Drop;
  if (k.includes("heal") || k.includes("health") || k.includes("potion") || k.includes("lecz")) return Flask;
  if (k.includes("amulet") || k.includes("ring") || k.includes("talizman")) return ShieldStar;
  if (k.includes("scroll") || k.includes("zwoj") || k.includes("zwój")) return Scroll;
  if (k.includes("dagger") || k.includes("sztylet") || k.includes("knife")) return Knife;
  if (k.includes("staff") || k.includes("wand") || k.includes("lask")) return MagicWand;
  if (k.includes("ration") || k.includes("racj") || k.includes("bread") || k.includes("food")) return Bread;
  if (t === "weapon") return Sword;
  if (t === "armor" || t === "shield") return Shield;
  if (t === "consumable") return Flask;
  return Scroll;
}
