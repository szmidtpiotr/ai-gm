// KROK 5 (#1234) — wspólne prymitywy paneli karty postaci (nagłówki sekcji,
// ikony przedmiotów/slotów). Tokeny wg frontend_design.md sekcja 6.
import {
  Backpack,
  Boot,
  Bread,
  Crown,
  Diamond,
  Drop,
  FireSimple,
  FirstAidKit,
  Flame,
  Flask,
  Hand,
  Key,
  Knife,
  MagicWand,
  MapTrifold,
  Pants,
  Scroll,
  Shield,
  Sword,
  TShirt,
  type Icon,
} from "@phosphor-icons/react";
import type { InventoryItem } from "@/lib/sheet";

export function SecHead({ children }: { children: React.ReactNode }) {
  return (
    <h3 className="mb-3 flex items-center gap-2.5 font-ui text-[10.5px] font-bold uppercase tracking-[0.2em] text-ember after:h-px after:flex-1 after:bg-line-soft after:content-['']">
      {children}
    </h3>
  );
}

// Panel = pełna wysokość obszaru gry, własny scroll (bez scrollbara), centrowany.
export function PanelScroll({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-0 flex-1 overflow-y-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
      <div className="mx-auto w-full max-w-[960px] px-4 py-5 pb-8 lg:px-8 lg:py-7">
        {children}
      </div>
    </div>
  );
}

// Ikona wg typu/klucza przedmiotu — mapowanie na phosphor (sylwetka + plecak).
export function itemIcon(it: InventoryItem): Icon {
  const t = (it.item_type || "").toLowerCase();
  const k = (it.key || "").toLowerCase();
  if (k.includes("mana")) return Drop;
  if (k.includes("health") || k.includes("heal") || k.includes("potion")) return Flask;
  if (k.includes("bandage") || k.includes("bandaz")) return FirstAidKit;
  if (k.includes("torch") || k.includes("pochodn")) return Flame;
  if (k.includes("map") || t === "map") return MapTrifold;
  if (k.includes("key") || t === "key") return Key;
  if (k.includes("dagger") || k.includes("sztylet") || k.includes("knife")) return Knife;
  if (k.includes("staff") || k.includes("wand") || k.includes("lask")) return MagicWand;
  if (t === "weapon") return Sword;
  if (t === "consumable" || t === "food") return Bread;
  if (t === "quest" || t === "scroll" || t === "note") return Scroll;
  if (t === "armor") return TShirt;
  if (t === "shield") return Shield;
  return Backpack;
}

// Ikona pustego/pełnego slotu sylwetki (Diablo-overlap).
export const SLOT_ICON: Record<string, Icon> = {
  head: Crown,
  amulet: Diamond,
  chest: TShirt,
  main_hand: Sword,
  off_hand: Shield,
  hands: Hand,
  legs: Pants,
  feet: Boot,
};

export const SPELL_TYPE_ICON: Record<string, Icon> = {
  attack: FireSimple,
  attack_aoe: Flame,
  heal: FirstAidKit,
  defense: Shield,
  narrative: MagicWand,
};
