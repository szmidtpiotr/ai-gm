// FE12 Sklep / NPC (#1261 / F-57) — kształty odpowiedzi handlu.
// Kontrakt: backend/app/api/shop.py + shop_service.py. Sklep zwraca `type`
// (weapon/armor/consumable/item), NIE zwraca rarity/ikony — ikonę wyliczamy
// z type/key, „rzadki" tylko gdy backend kiedyś dołoży rarity/is_special.

export interface ShopNpc {
  id: number;
  key: string;
  label: string;
}

export interface ShopBuyItem {
  type: string; // weapon | armor | consumable | item
  key: string;
  label: string;
  description?: string | null;
  value_gp?: number;
  buy_price_gp: number; // faktyczna cena (z mnożnikiem CHA/targ/reputacji)
  min_level?: number;
  // opcjonalne — backend dziś nie zwraca, ale honorujemy jeśli się pojawią
  rarity?: number | null;
  is_special?: boolean | null;
}

export interface ShopSellItem {
  inventory_id: number;
  item_type: string;
  key: string;
  label: string;
  quantity: number;
  value_gp?: number;
  sell_price_gp: number;
}

export interface ShopData {
  npc: ShopNpc;
  items: ShopBuyItem[];
  sell_items: ShopSellItem[];
  character_gold: number;
  haggle_discount?: number; // ujemne = narzut (kupiec urażony)
  shop_open?: boolean;
  shop_closed_reason?: string | null;
  shop_closed_message?: string | null;
  is_black_market?: boolean;
}

/** „Rzadki" towar — fioletowa ramka/nazwa w makiecie. Tylko gdy backend poda. */
export function isRareGood(it: { rarity?: number | null; is_special?: boolean | null }): boolean {
  return !!it.is_special || (it.rarity != null && it.rarity >= 3);
}
